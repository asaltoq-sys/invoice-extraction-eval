"""
Builds the synthetic test documents as PDFs (with invented layouts and logos).
One is turned into a scanned, image-only PDF and another into a JPG photo,
because real inboxes get both.

Usage: python build_docs.py
"""
import random
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

OUT = Path("data/docs")
LOGOS = Path("data/logos")
SCANNED = {"inv_04"}        # image-only PDF, like a scanner output
PHOTOS = {"inv_09"}         # JPG, like a phone photo sent by email
W, H = A4

# ---------------------------------------------------------------- documents
DOCS = {
 "inv_01": dict(style="classic", color="#1F4E79", logo="SL",
   issuer=["SUMINISTROS LEVANTE S.L.", "CIF: B12345670", "C/ Industria 12, 46000 Valencia"],
   title="FACTURA", meta=[("Nº Factura", "F-2026-0142"), ("Fecha", "04/02/2026"), ("Nº Pedido", "PO-7781"), ("Nº Albarán", "AL-3321")],
   customer=["Construcciones Ejemplo S.A.", "CIF: A11111111"],
   cols=["Descripción", "Cantidad", "Precio", "Importe"],
   rows=[["Tornillo M8", "100", "0,12", "12,00"], ["Tuerca M8", "100", "0,08", "8,00"], ["Brida acero 50mm", "20", "3,45", "69,00"]],
   totals=[("Base imponible", "89,00"), ("IVA 21%", "18,69"), ("TOTAL FACTURA", "107,69 €")]),
 "inv_02": dict(style="modern", color="#2E7D32", logo="PC",
   issuer=["PAPELERÍA CENTRAL S.L.", "CIF B23456781"],
   title="FACTURA", meta=[("Factura", "2026/318"), ("Fecha factura", "11/03/2026")],
   customer=["Oficinas Ejemplo S.L.", "CIF B87654321"],
   cols=["Albarán", "Fecha albarán", "Pedido", "Descripción", "Cant", "Precio", "Importe"],
   rows=[["45872", "09/03/2026", "P-5510", "Papel A4 caja", "10", "21,50", "215,00"],
         ["45872", "09/03/2026", "P-5510", "Tóner negro", "2", "64,90", "129,80"]],
   totals=[("Base imponible", "344,80"), ("IVA 21%", "72,41"), ("Total", "417,21 EUR")]),
 "inv_03": dict(style="classic", color="#8B4513", logo="TM",
   issuer=["TRANSPORTES MANCHA S.L.", "CIF: B34567892"],
   title="FACTURA", meta=[("Factura", "T-0977"), ("Fecha", "20/03/2026"), ("Nº Albarán", "")],
   customer=["Distribuciones Ejemplo S.L.", "CIF: B98765432"],
   cols=["Concepto", "Uds", "Precio", "Total"],
   rows=[["Alb. 88123 - Porte Albacete-Madrid", "1", "380,00", "380,00"],
         ["Alb. 88124 - Porte Madrid-Zaragoza", "1", "450,00", "450,00"]],
   totals=[("Base", "830,00"), ("IVA (21%)", "174,30"), ("Total", "1.004,30 €")]),
 "inv_04": dict(style="minimal", color="#E65100", logo="FR",
   issuer=["FRUTAS HERMANOS RUIZ S.L.", "CIF B45678903"],
   title="FACTURA", meta=[("Factura nº", "FR-2211"), ("Fecha", "02/04/2026"), ("Albarán", "7781")],
   customer=["Distribuciones Ejemplo S.L."],
   cols=["Descripción", "Kg", "Cajas", "Precio/caja", "Importe"],
   rows=[["Naranja", "180,50", "10", "14,20", "142,00"], ["Limón", "95,00", "5", "18,60", "93,00"]],
   totals=[("Base imponible", "235,00"), ("IVA 4%", "9,40"), ("TOTAL", "244,40")]),
 "inv_05": dict(style="modern", color="#37474F", logo="FN",
   issuer=["FERRETERÍA NORTE S.L.", "CIF: B56789014"],
   title="FACTURA", meta=[("Factura", "FN-560"), ("Fecha", "05/04/2026"), ("Su pedido", "2026-PED-44"), ("Albarán", "A-9912")],
   customer=["Distribuciones Ejemplo S.L."],
   cols=["Artículo", "Cant.", "P. unit.", "Importe"],
   rows=[["Taladro percutor 800W", "2", "125,00", "250,00"], ["      Dto. 5%", "", "", "-12,50"], ["Set brocas HSS", "5", "18,00", "90,00"]],
   totals=[("Base imponible", "327,50"), ("IVA 21%", "68,78"), ("TOTAL", "396,28 €")]),
 "inv_06": dict(style="classic", color="#006064", logo="EL",
   issuer=["EMBALAGENS LUSAS LDA", "NIF: PT509876543", "Rua do Porto 45, 4000 Porto"],
   title="FATURA", meta=[("Fatura", "FT 2026/1204"), ("Data", "07/04/2026")],
   customer=["Distribuciones Ejemplo S.L.", "ES B98765432"],
   cols=["Documento de venda", "Conhecimento de embarque", "Descrição", "Qtd", "Preço unit.", "Total"],
   rows=[["DV-3381", "CE-55120", "Caixa cartão 40x30", "500", "0,42", "210,00"],
         ["DV-3381", "CE-55120", "Fita adesiva", "48", "1,15", "55,20"]],
   totals=[("Total ilíquido", "265,20"), ("IVA 0% (Isento art. 14 RITI)", "0,00"), ("Total", "265,20 EUR")]),
 "inv_07": dict(style="modern", color="#4A148C", logo="NL",
   issuer=["NORDIC LABELS LTD", "VAT No: GB123456789", "12 Harbour Road, Leeds"],
   title="INVOICE", meta=[("Invoice", "INV-88410"), ("Date", "2026-04-09"), ("PO Nr.", "4500123987"), ("Delivery note", "DN-7710")],
   customer=["Bill to: Distribuciones Ejemplo S.L."],
   cols=["Item", "Qty", "Unit price", "Amount"],
   rows=[["Thermal labels 100x150 roll", "1,200", "0.85", "1,020.00"], ["Wax ribbon 110mm", "24", "6.40", "153.60"]],
   totals=[("Subtotal", "1,173.60"), ("VAT 0% (reverse charge)", "0.00"), ("Total due", "EUR 1,173.60")]),
 "inv_08": dict(style="classic", color="#1F4E79", logo="SL",
   issuer=["SUMINISTROS LEVANTE S.L.", "CIF: B12345670", "C/ Industria 12, 46000 Valencia"],
   title="FACTURA RECTIFICATIVA (ABONO)", meta=[("Nº", "R-2026-0009"), ("Fecha", "15/04/2026"), ("Rectifica a", "F-2026-0142"), ("Pedido original", "PO-7781")],
   customer=["Construcciones Ejemplo S.A.", "CIF: A11111111"],
   cols=["Descripción", "Cantidad", "Precio", "Importe"],
   rows=[["Brida acero 50mm (devolución)", "-5", "3,45", "-17,25"]],
   totals=[("Base imponible", "-17,25"), ("IVA 21%", "-3,62"), ("TOTAL", "-20,87 €")]),
 "inv_09": dict(style="minimal", color="#2E7D32", logo="PC",
   issuer=["PAPELERÍA CENTRAL S.L.", "CIF B23456781"],
   title="ALBARÁN DE ENTREGA", meta=[("Nº", "45901"), ("Fecha", "16/04/2026"), ("Su pedido", "P-5530")],
   customer=["Oficinas Ejemplo S.L."],
   cols=["Descripción", "Cantidad"],
   rows=[["Papel A4 caja", "5"]],
   totals=[], footer="Recibí conforme: ______________________"),
 "inv_10": dict(style="modern", color="#AD1457", logo="HA",
   issuer=["HOSTELERÍA ALBA S.L.", "CIF B67890125"],
   title="FACTURA", meta=[("Factura", "HA-1502"), ("Fecha", "18/04/2026"), ("Albarán", "3302")],
   customer=["Distribuciones Ejemplo S.L."],
   cols=["Descripción", "Cant.", "Precio", "IVA", "Importe"],
   rows=[["Agua mineral (caja)", "24", "6,00", "10%", "144,00"], ["Detergente 5L", "6", "12,50", "21%", "75,00"]],
   totals=[("Base 10%", "144,00"), ("IVA 10%", "14,40"), ("Base 21%", "75,00"), ("IVA 21%", "15,75"), ("TOTAL", "249,15 €")]),
}

# ---------------------------------------------------------------- logos
def make_logo(initials, color, path):
    img = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((10, 10, 230, 230), fill=color)
    d.ellipse((40, 40, 200, 200), outline="white", width=8)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 80)
    except OSError:
        font = ImageFont.load_default()
    d.text((120, 122), initials, fill="white", font=font, anchor="mm")
    img.save(path)

# ---------------------------------------------------------------- pdf
def draw_doc(doc_id, s, path):
    c = canvas.Canvas(str(path), pagesize=A4)
    col = colors.HexColor(s["color"])
    mono = s["style"] == "minimal"
    reg, bold = ("Courier", "Courier-Bold") if mono else ("Helvetica", "Helvetica-Bold")
    logo = LOGOS / f"{s['logo']}.png"
    top = H - 20 * mm

    if s["style"] == "modern":
        c.setFillColor(col); c.rect(0, H - 45 * mm, W, 45 * mm, fill=1, stroke=0)
        c.drawImage(str(logo), 15 * mm, H - 38 * mm, 28 * mm, 28 * mm, mask="auto")
        c.setFillColor(colors.white)
        y = H - 18 * mm
        for i, line in enumerate(s["issuer"]):
            c.setFont(bold if i == 0 else reg, 13 if i == 0 else 9); c.drawString(48 * mm, y, line); y -= 5.5 * mm
        c.setFont(bold, 20); c.drawRightString(W - 15 * mm, H - 22 * mm, s["title"])
        c.setFillColor(colors.black)
        y = H - 58 * mm
    else:
        c.drawImage(str(logo), 15 * mm, top - 22 * mm, 22 * mm, 22 * mm, mask="auto")
        y = top - 4 * mm
        for i, line in enumerate(s["issuer"]):
            c.setFont(bold if i == 0 else reg, 12 if i == 0 else 9); c.drawString(42 * mm, y, line); y -= 5 * mm
        c.setFont(bold, 16 if len(s["title"]) < 20 else 12); c.setFillColor(col)
        c.drawRightString(W - 15 * mm, top - 4 * mm, s["title"]); c.setFillColor(colors.black)
        y = top - 32 * mm

    # meta box (right) and customer (left)
    box_top = y
    c.setFont(bold, 9); c.drawString(15 * mm, y, "Cliente / Customer" if doc_id == "inv_07" else "Cliente")
    c.setFont(reg, 9)
    cy = y - 5 * mm
    for line in s["customer"]:
        c.drawString(15 * mm, cy, line); cy -= 4.5 * mm
    my = y
    if s["style"] == "classic":
        c.setStrokeColor(col); c.rect(W - 85 * mm, y - len(s["meta"]) * 5 * mm - 2 * mm, 70 * mm, len(s["meta"]) * 5 * mm + 6 * mm)
    for label, value in s["meta"]:
        c.setFont(bold, 9); c.drawString(W - 82 * mm, my, f"{label}:")
        c.setFont(reg, 9); c.drawString(W - 50 * mm, my, value); my -= 5 * mm
    y = min(cy, my) - 10 * mm

    # table
    cols, rows = s["cols"], s["rows"]
    usable = W - 30 * mm
    widths = [max(len(h), *(len(r[i]) for r in rows)) + 3 for i, h in enumerate(cols)]
    widths = [w / sum(widths) * usable for w in widths]
    x0 = 15 * mm
    fs = 7.5 if len(cols) > 5 else 9
    c.setFillColor(col if s["style"] != "minimal" else colors.HexColor("#DDDDDD"))
    c.rect(x0, y - 2 * mm, usable, 7 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white if s["style"] != "minimal" else colors.black); c.setFont(bold, fs)
    num = re.compile(r"^-?[\d.,]+%?$")
    numeric = [i > 0 and all(num.match(r[i]) or r[i] == "" for r in rows) for i in range(len(cols))]
    x = x0
    for i, (h, w) in enumerate(zip(cols, widths)):
        if numeric[i]:
            c.drawRightString(x + w - 1.5 * mm, y, h)
        else:
            c.drawString(x + 1.5 * mm, y, h)
        x += w
    c.setFillColor(colors.black); c.setFont(reg, fs)
    y -= 8 * mm
    for n, r in enumerate(rows):
        if s["style"] == "modern" and n % 2:
            c.setFillColor(colors.HexColor("#F2F2F2")); c.rect(x0, y - 2 * mm, usable, 7 * mm, fill=1, stroke=0); c.setFillColor(colors.black)
        x = x0
        for i, (v, w) in enumerate(zip(r, widths)):
            if numeric[i]:
                c.drawRightString(x + w - 1.5 * mm, y, v)
            else:
                c.drawString(x + 1.5 * mm, y, v)
            x += w
        if s["style"] == "classic":
            c.setStrokeColor(colors.HexColor("#BBBBBB")); c.line(x0, y - 2.5 * mm, x0 + usable, y - 2.5 * mm)
        y -= 7 * mm

    # totals
    y -= 6 * mm
    for i, (label, value) in enumerate(s["totals"]):
        last = i == len(s["totals"]) - 1
        c.setFont(bold if last else reg, 11 if last else 9)
        c.drawRightString(W - 50 * mm, y, label)
        c.drawRightString(W - 15 * mm, y, value)
        y -= 6 * mm
    if s.get("footer"):
        c.setFont(reg, 10); c.drawString(15 * mm, y - 20 * mm, s["footer"])

    c.setFont(reg, 7); c.setFillColor(colors.grey)
    c.drawString(15 * mm, 12 * mm, "Documento de prueba sintético / Synthetic test document")
    c.save()

# ---------------------------------------------------------------- scan effect
def make_scanned(pdf_path, seed):
    random.seed(seed)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["pdftoppm", "-r", "150", "-png", "-singlefile", str(pdf_path), f"{tmp}/p"], check=True)
        img = Image.open(f"{tmp}/p.png").convert("L")
    img = img.rotate(random.uniform(-1.5, 1.5), expand=False, fillcolor=250, resample=Image.BICUBIC)
    px = img.load()
    for _ in range(img.width * img.height // 60):
        x, y = random.randrange(img.width), random.randrange(img.height)
        px[x, y] = random.choice([90, 140, 200])
    img = img.filter(ImageFilter.GaussianBlur(0.6)).point(lambda v: min(255, int(v * 0.97 + 6)))
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True); LOGOS.mkdir(parents=True, exist_ok=True)
    for s in DOCS.values():
        make_logo(s["logo"], s["color"], LOGOS / f"{s['logo']}.png")
    for i, (doc_id, s) in enumerate(DOCS.items()):
        path = OUT / f"{doc_id}.pdf"
        draw_doc(doc_id, s, path)
        if doc_id in SCANNED:
            make_scanned(path, seed=i).save(path, "PDF", resolution=150)
        elif doc_id in PHOTOS:
            img = make_scanned(path, seed=i).rotate(3, expand=True, fillcolor=120)
            path.unlink()
            path = path.with_suffix(".jpg")
            img.save(path, quality=75)
        print("built", path)


if __name__ == "__main__":
    main()
