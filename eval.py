"""
Invoice extraction eval.

Runs a prompt over the test documents (PDFs or images) with Claude, compares each answer
with the ground truth and writes a field-by-field report.

Usage:
    python eval.py --prompt prompts/v1_baseline.txt
    python eval.py --prompt prompts/v2_refined.txt --runs 3
    python eval.py --dry-run          # checks the scoring code without calling the API
"""
import argparse
import base64
import json
import re
from datetime import datetime
from pathlib import Path

DOCS_DIR = Path("data/docs")
TRUTH_FILE = Path("data/ground_truth.json")
RESULTS_DIR = Path("results")
HEADER_FIELDS = ["doc_type", "supplier_name", "supplier_tax_id", "document_number",
                 "document_date", "delivery_note_numbers", "order_number", "vat_rates", "total"]
LINE_FIELDS = ["quantity", "unit_price", "line_total"]


# ---------- calling Claude ----------

MEDIA_TYPES = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def find_document(doc_id):
    for suffix in MEDIA_TYPES:
        path = DOCS_DIR / f"{doc_id}{suffix}"
        if path.exists():
            return path
    raise FileNotFoundError(f"No PDF or image found for {doc_id}")


def document_block(path):
    """PDFs go as 'document' blocks, pictures as 'image' blocks."""
    data = base64.standard_b64encode(path.read_bytes()).decode()
    media_type = MEDIA_TYPES[path.suffix.lower()]
    kind = "document" if media_type == "application/pdf" else "image"
    return {"type": kind, "source": {"type": "base64", "media_type": media_type, "data": data}}


def extract(client, model, prompt, path):
    response = client.messages.create(
        model=model,
        max_tokens=8000,  # leaves room if the model thinks before answering
        system=prompt,
        messages=[{"role": "user", "content": [
            document_block(path),
            {"type": "text", "text": "Extract the data from this document."},
        ]}],
    )
    # The answer can include thinking blocks before the text; keep only the text.
    raw = "".join(block.text for block in response.content if block.type == "text")
    if response.stop_reason == "max_tokens":
        raw += "\n[TRUNCATED: hit max_tokens]"
    return parse_json(raw), raw


def parse_json(raw):
    cleaned = re.sub(r"```(json)?", "", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None  # counted as a failure for every field


# ---------- comparing answers ----------

def to_number(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace("€", "").replace("%", "").strip()
    if "," in text and "." in text:          # 1.004,30 -> 1004.30
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:                          # 12,50 -> 12.50
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return text


def normalize_text(value):
    if value is None:
        return None
    return re.sub(r"\s+", " ", str(value)).strip().lower().rstrip(".")


def same(field, expected, got):
    """True if Claude's value matches the ground truth.
    Any answer in an unexpected shape (a dict instead of a number, etc.) counts as wrong."""
    try:
        return _same(field, expected, got)
    except (TypeError, ValueError, AttributeError):
        return False


def _same(field, expected, got):
    if field in ("total", "quantity", "unit_price", "line_total"):
        e, g = to_number(expected), to_number(got)
        if e is None or g is None:
            return e is None and g is None
        return isinstance(g, float) and abs(e - g) <= 0.01
    if field == "vat_rates":
        if not isinstance(got, list):
            got = [] if got is None else [got]
        return sorted(float(x) for x in expected) == sorted(float(to_number(x)) for x in got)
    if field == "delivery_note_numbers":
        if isinstance(got, str):
            got = [got]
        return {normalize_text(x) for x in expected} == {normalize_text(x) for x in (got or [])}
    return normalize_text(expected) == normalize_text(got)


def score_document(truth, answer):
    if not isinstance(answer, dict):
        answer = {}
    result = {f: same(f, truth[f], answer.get(f)) for f in HEADER_FIELDS}
    got_lines = answer.get("lines")
    if not isinstance(got_lines, list):
        got_lines = []
    got_lines = [l if isinstance(l, dict) else {} for l in got_lines]
    result["line_count"] = len(got_lines) == len(truth["lines"])
    for field in LINE_FIELDS:
        hits = [i < len(got_lines) and same(field, t[field], got_lines[i].get(field))
                for i, t in enumerate(truth["lines"])]
        result["lines." + field] = all(hits)
    return result


# ---------- report ----------

def write_report(prompt_path, model, runs, all_scores, raw_answers):
    fields = list(next(iter(all_scores.values()))[0].keys())
    lines = [f"# Results: {prompt_path.name}", "",
             f"- Model: `{model}`", f"- Runs per document: {runs}",
             f"- Date: {datetime.now():%Y-%m-%d %H:%M}", "",
             "| Field | Accuracy |", "|---|---|"]
    for f in fields:
        hits = [s[f] for doc in all_scores.values() for s in doc]
        lines.append(f"| {f} | {100 * sum(hits) / len(hits):.0f}% |")

    perfect = [all(s.values()) for doc in all_scores.values() for s in doc]
    lines += ["", f"**Documents fully correct: {100 * sum(perfect) / len(perfect):.0f}%**", "",
              "## Failures", ""]
    for doc_id, runs_scores in all_scores.items():
        failed = sorted({f for s in runs_scores for f, ok in s.items() if not ok})
        if failed:
            lines.append(f"- {doc_id}: {', '.join(failed)}")

    RESULTS_DIR.mkdir(exist_ok=True)
    stem = prompt_path.stem
    (RESULTS_DIR / f"{stem}.md").write_text("\n".join(lines), encoding="utf-8")
    (RESULTS_DIR / f"{stem}_raw.json").write_text(
        json.dumps(raw_answers, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default="prompts/v2_refined.txt")
    parser.add_argument("--model", default="claude-sonnet-5")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    truth = json.loads(TRUTH_FILE.read_text(encoding="utf-8"))
    prompt_path = Path(args.prompt)
    prompt = prompt_path.read_text(encoding="utf-8")

    client = None
    if not args.dry_run:
        import anthropic
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY

    all_scores, raw_answers = {}, {}
    for doc_id, expected in truth.items():
        path = find_document(doc_id)
        all_scores[doc_id], raw_answers[doc_id] = [], []
        for _ in range(args.runs):
            if args.dry_run:
                answer, raw = expected, "dry-run"
            else:
                answer, raw = extract(client, args.model, prompt, path)
            all_scores[doc_id].append(score_document(expected, answer))
            raw_answers[doc_id].append(raw)

    write_report(prompt_path, "dry-run" if args.dry_run else args.model,
                 args.runs, all_scores, raw_answers)


if __name__ == "__main__":
    main()
