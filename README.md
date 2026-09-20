# Measuring invoice extraction with Claude: a small eval

I sell and help deploy document management at DocuWare. Most of the projects I work on start with the same request: "read my supplier invoices and put the data where it belongs." This repo is how I test whether a prompt is good enough before a customer relies on it.

All documents here are synthetic. No customer or employer data is included.

## Why I built it

In my projects the extraction usually runs on a dedicated IDP tool. Refining its prompts with Claude taught me where invoices break: dates read as document numbers, the customer's tax ID taken for the supplier's, discount rows counted as products. This eval asks a different question. If a customer builds the extraction directly on Claude, how do we prove it works before they go live?

"Refining the prompt until it works" is easy to fool yourself with. You fix the invoice in front of you and break two others. The eval is my answer to that.

## What the eval does

1. `data/docs/` holds 10 invented supplier documents, each with its own layout and logo. Eight are digital PDFs, `inv_04` is a scanned image-only PDF and `inv_09` is a phone photo (JPG), because real AP inboxes get all three. They reproduce failures I've hit in real projects:

| Doc | What it tests |
|---|---|
| inv_01 | Clean invoice, baseline |
| inv_02 | Delivery note number and delivery note date in adjacent columns |
| inv_03 | Empty delivery note field in the header, customer tax ID right below it, real delivery notes inside the line descriptions |
| inv_04 | Weight column next to the quantity column, on a scanned page |
| inv_05 | Discount sub-row under a product line |
| inv_06 | Portuguese invoice: "Conhecimento de embarque" is the delivery note, "Documento de venda" is not |
| inv_07 | English invoice with "PO Nr." and US number format (1,200 = one thousand two hundred) |
| inv_08 | Credit note with negative amounts |
| inv_09 | Photo of a delivery note with no prices, to test document classification |
| inv_10 | Two VAT rates on one invoice |

2. `data/ground_truth.json` has the correct answer for each document.
3. `eval.py` sends every document to Claude (PDFs as document blocks, the photo as an image block) with a prompt, compares the answer field by field and writes a report to `results/`. Numbers are compared with a 0.01 tolerance, and number formats are normalised so "1.004,30" and 1004.3 count as the same value.
4. `prompts/` has two versions:
   - `v1_baseline.txt`: the kind of prompt people write on day one.
   - `v2_refined.txt`: the rules I ended up adding after real failures. It defines a search order (line, then header, then footer), synonyms per language, the list of valid Spanish VAT rates, the quantity x price = total check, and what is not a line.

## How to run it

```bash
pip install -r requirements.txt
python build_docs.py          # optional: rebuilds the documents
export ANTHROPIC_API_KEY=...
python eval.py --prompt prompts/v1_baseline.txt --runs 3
python eval.py --prompt prompts/v2_refined.txt --runs 3
```

`--runs 3` repeats each document three times, because a prompt that is right once and wrong twice is not ready for production. `--dry-run` checks the scoring code without calling the API.

## Results

<!-- Fill in after running both prompts. Copy the tables from results/*.md -->

| Field | v1 baseline | v2 refined |
|---|---|---|
| doc_type | 10% | 100% |
| supplier_name | 100% | 100% |
| supplier_tax_id | 100% | 100% |
| document_number | 100% | 100% |
| document_date | 10% | 100% |
| delivery_note_numbers | 90% | 100% |
| order_number | 100% | 100% |
| vat_rates | 80% | 100% |
| total | 83% | 100% |
| line_count | 90% | 100% |
| lines.quantity | 90% | 100% |
| lines.unit_price | 90% | 100% |
| lines.line_total | 90% | 100% |
| **Documents fully correct** | **10%** | **100%** |

Model: `claude-sonnet-5`, 3 runs per document.

## What I take from it

The biggest gain came from being specific. Once v2 defined the document types and told Claude exactly where to look for each field, documents fully correct went from 10% to 100%.

What surprised me most was the scanned invoice and the phone photo. They were slightly crooked and noisy, and Claude read them perfectly.

Still, I don't trust the 100%. We got there because I knew these documents in advance, and it's easy to tune a prompt until it passes a test you've already seen. Real life is much harder. With real volumes there will always be invoices that don't fit the rules, and some fields won't be found or will be read wrong.

If a customer asked me whether this is ready for production, I'd say yes, as long as there is a control layer on top. For me that layer has five checks: the taxable base plus VAT must equal the total, the item quantities must add up to the total units printed on the invoice when it shows one, every invoice is matched against its purchase order, a second agent reviews the extraction, and any invoice above an amount the customer sets goes to a person for approval.

The failure I'd worry about most is amounts. Reading 10.00 as 1,000, or 100,000.00 as 1,000,000, is the kind of error that can cost a company thousands of euros if nobody catches it.

## How I'd use this with a customer

- Ask the customer for 30 to 50 real documents per supplier type, including the ugly ones, and build the ground truth with their AP team.
- Agree on the acceptance bar per field before testing. A wrong total costs more than a wrong order number.
- Run the eval every time the prompt, the model or the document mix changes.
- If a field stays below the bar and the supplier layout never changes, a template-based extractor may be the better tool for that field. Picking the right tool per field is part of the advice.
