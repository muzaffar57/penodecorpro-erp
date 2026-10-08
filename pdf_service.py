"""
PenoDecorPro ERP — PDF Nakladnoy generatsiyasi
================================================
ReportLab yordamida chiroyli nakladnoy (hisob-faktura) chiqaradi.

Ishlatilishi:
    pdf_bytes = generate_nakladnoy(order, db)
    # PDF ni brauzerga yuborish uchun FastAPI Response ishlatiladi
"""

from company_brand import get_brand, company_id_of  # 2026-09-20: korxona brendi

import io
from typing import Optional
# kech106 (9 + 50-band B qismi): hujjatdagi sana-vaqt — Toshkent devor soati (ilgari `datetime.now()` — Railway da
# UTC, "Sana" va "Chiqarilgan" Toshkent 00:00–05:00 da KECHAGI kun; "Yaratilgan sana" — bazadagi UTC sanasi).
from database import tashkent_vaqt as _tashkent_vaqt
# kech106 (K106-1): PDF shrifti — Liberation Sans (Kirill, "№", "−"; Helvetica metrikasi) standart Helvetica NOMLARI
# bilan (`pdf_shrift.py`). Ilgari Kirill yozilgan nom, "№" va emoji QORA KVADRAT (■) bo'lib chiqardi.
from pdf_shrift import shriftlarni_ulash as _shriftlarni_ulash
_shriftlarni_ulash()
# kech106 (K106-3): foydalanuvchi matni (nom, izoh, telefon, korxona ma'lumoti) Paragraph ga XAVFSIZ — "<" / "&"
# belgilash deb o'qilmaydi (ilgari "Karniz <A>" kabi nom yoki "<b>izoh" bo'lsa PDF 500 edi).
from xml.sax.saxutils import escape as _xml_escape


def _x(qiymat):
    return _xml_escape("" if qiymat is None else str(qiymat))


# kech129 (zip 153): logotip sarlavhadagi 32 × 18 mm QUTIGA o'z nisbati bilan sig'diriladi. Ilgari QAT'IY 32 × 18 mm chizilardi
# (standart logotip nisbati 1,78 uchun yozilgan) — kvadrat logotip 1,78 marta, tik (1 : 2) — 3,6 marta cho'zilardi (O'LCHANGAN,
# `tools/test_logo_pdf.py`). Standart logotip (998 × 561) — AYNAN 32 × 18 mm (nisbat farqi 1 % dan kam — qutining o'zi).
LOGO_QUTI_MM = (32, 18)


def _logo_olcham(yol):
    """(eni, bo'yi) — PDF birligida (nuqta), logotip qutiga nisbati bilan sig'diriladi; fayl TO'LIQ o'qilmasa — None (PDF yiqilmasin:
    logotip o'rniga korxona nomi chiqadi; ilgari buzilgan logotip HAR «Buyurtma hisobi» / «Taklif» PDF ini 500 qilardi)."""
    try:
        from PIL import Image as _PilImage
        with _PilImage.open(yol) as _im:
            _im.load()
            w, h = _im.size
    except Exception:
        return None
    if not w or not h:
        return None
    qe, qb = LOGO_QUTI_MM[0] * mm, LOGO_QUTI_MM[1] * mm
    nisbat = w / float(h)
    if abs(nisbat / (qe / qb) - 1) < 0.01:
        return qe, qb
    if nisbat > qe / qb:
        return qe, qe / nisbat
    return qb * nisbat, qb


from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable
)
from reportlab.lib import colors

# ============================================================
# Ranglar (kompaniya uslubi)
# ============================================================
DARK   = colors.HexColor("#1A252F")
GOLD   = colors.HexColor("#C9A55A")
LIGHT  = colors.HexColor("#F4F6F8")
WHITE  = colors.white
RED    = colors.HexColor("#E74C3C")
GREEN  = colors.HexColor("#27AE60")
GRAY   = colors.HexColor("#7F8C8D")
LGRAY  = colors.HexColor("#BDC3C7")
# kech120 (zip 136 — F bosqichi 5-qism, audit G6-12): shior, kontakt va «Imzo / Sana» — LGRAY (#BDC3C7, oq qog'ozda ~1,8:1) chop
# etilganda deyarli ko'rinmasdi; endi to'qroq kulrang (~7,5:1)
IZOH_RANG = colors.HexColor("#4B5563")


def _pul_matni(n) -> str:
    """kech120 (zip 136 — G6-12): buyurtma hisobidagi summa — boshqa hujjatlardagidek ming ajratgich BO'SHLIQ («900 000»;
    ilgari «900,000» — vergul, yuk xati / hisob-kitob / moliya PDF larida bo'shliq). Butun so'mgacha yaxlitlanadi (avvalgidek)."""
    try:
        return f"{float(n or 0):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def get_styles(cx: float = 0.0):
    """cx — siqilish darajasi (0.0 = oddiy, 1.0 = eng siqilgan).
    Ko'p detalli buyurtmalarda hujjat 1 sahifaga sig'ishi uchun."""
    def L(a, b):
        return a + (b - a) * cx

    return {
        "company": ParagraphStyle("company", fontName="Helvetica-Bold", fontSize=L(20,14), textColor=GOLD, leading=L(24,16)),
        "company_sub": ParagraphStyle("company_sub", fontName="Helvetica", fontSize=L(9,6.5), textColor=IZOH_RANG, leading=L(12,8)),
        "imzo": ParagraphStyle("imzo", fontName="Helvetica", fontSize=L(8,6), textColor=IZOH_RANG, leading=L(10,7), spaceAfter=L(2,0.5)),
        "doc_title": ParagraphStyle("doc_title", fontName="Helvetica-Bold", fontSize=L(14,10), textColor=DARK, leading=L(18,12), alignment=TA_RIGHT),
        "doc_num": ParagraphStyle("doc_num", fontName="Helvetica", fontSize=L(10,7), textColor=GRAY, leading=L(14,9), alignment=TA_RIGHT),
        "section_label": ParagraphStyle("section_label", fontName="Helvetica", fontSize=L(8,6), textColor=GRAY, leading=L(10,7), spaceAfter=L(2,0.5)),
        "section_value": ParagraphStyle("section_value", fontName="Helvetica-Bold", fontSize=L(10,7), textColor=DARK, leading=L(13,9)),
        "section_value_sm": ParagraphStyle("section_value_sm", fontName="Helvetica", fontSize=L(9,6.5), textColor=DARK, leading=L(12,8)),
        "table_header": ParagraphStyle("table_header", fontName="Helvetica-Bold", fontSize=L(9,6), textColor=WHITE, leading=L(11,7), alignment=TA_CENTER),
        "table_cell": ParagraphStyle("table_cell", fontName="Helvetica", fontSize=L(9,5.8), textColor=DARK, leading=L(11,7)),
        "table_cell_c": ParagraphStyle("table_cell_c", fontName="Helvetica", fontSize=L(9,5.8), textColor=DARK, leading=L(11,7), alignment=TA_CENTER),
        "table_cell_r": ParagraphStyle("table_cell_r", fontName="Helvetica", fontSize=L(9,5.8), textColor=DARK, leading=L(11,7), alignment=TA_RIGHT),
        "total_label": ParagraphStyle("total_label", fontName="Helvetica-Bold", fontSize=L(11,8), textColor=DARK, leading=L(14,10), alignment=TA_RIGHT),
        "total_value": ParagraphStyle("total_value", fontName="Helvetica-Bold", fontSize=L(13,9), textColor=GOLD, leading=L(16,11), alignment=TA_RIGHT),
        "footer": ParagraphStyle("footer", fontName="Helvetica", fontSize=L(8,6), textColor=GRAY, leading=L(10,7), alignment=TA_CENTER),
        "note": ParagraphStyle("note", fontName="Helvetica", fontSize=L(9,6.5), textColor=GRAY, leading=L(12,8)),
        "status_ok": ParagraphStyle("status_ok", fontName="Helvetica-Bold", fontSize=L(9,6.5), textColor=GREEN, leading=L(11,7), alignment=TA_CENTER),
        "status_new": ParagraphStyle("status_new", fontName="Helvetica-Bold", fontSize=L(9,6.5), textColor=GRAY, leading=L(11,7), alignment=TA_CENTER),
    }


STATUS_UZ = {
    "new": "Yangi",
    "in_progress": "Jarayonda",
    "coating": "Qoplama",
    "ready": "Tayyor",
    "delivered": "Yetkazildi",
    "cancelled": "Bekor qilindi",
}

ORDER_TYPE_UZ = {
    "service": "Xizmat",
    "product": "Mahsulot",
}


def generate_nakladnoy(order, db=None, taklif=None) -> bytes:
    """Buyurtma uchun PDF nakladnoy yaratadi.

    MUHIM: hujjat 1 sahifaga sig'ishi uchun, detallar soniga qarab
    shrift/bo'sh joy AVTOMATIK siqiladi (Yuk xatidagi bilan bir xil
    tamoyil).

    kech126 (zip 148 — EGASI QARORI 07.10 «Tez hisob / Taklif»: hujjat «Buyurtma hisobi» ko'rinishida, sarlavha «TAKLIF
    (HISOB-KITOB)», pastida «Narxlar 3 kun amal qiladi»): `taklif` berilsa — o'sha shablon TAKLIF hujjati sifatida
    (`generate_taklif`): sarlavha, raqam («T-0001»), sana — taklif sanasi; mijoz bloki — mijoz, telefon, taklif raqami va
    sanasi (loyiha / holat / usta yo'q); jadval AYNAN; summa qatorlari — o'sha `crud.buyurtma_hisob_qatorlari` qoidasi (taklifda
    to'lov / qarz qatori yo'q); imzo o'rniga «Narxlar 3 kun amal qiladi». `taklif` = {"sana": UTC vaqt, "hisob": qatorlar}."""
    n_items = len(order.items or [])
    cx = max(0.0, min(1.0, (n_items - 6) / 14.0))

    buf = io.BytesIO()
    st  = get_styles(cx)

    margin_v = (15 - cx * 8) * mm
    # 2026-09-20: logotip va nomlar korxonanikidan olinadi (bo'lmasa — umumiy)
    _brand = get_brand(db, company_id_of(order, db))
    # kech120 (zip 136 — G6-12): fayl xususiyatlarida sarlavha (ilgari «(anonymous)») va muallif — korxona
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=margin_v, bottomMargin=margin_v,
        title=f"Buyurtma hisobi {order.order_number or order.id}", author=_brand["name"] or "", subject="Buyurtma hisobi",
    )
    # kech126 (zip 148): taklif hujjati — fayl xususiyatlarida ham «Taklif»
    _hujjat_vaqti = None
    if taklif:
        doc.title, doc.subject = f"Taklif {order.order_number}", "Taklif (hisob-kitob)"
        _hujjat_vaqti = taklif.get("sana")

    W = A4[0] - 36*mm
    story = []

    # ── SARLAVHA ──────────────────────────────────────────────
    import os
    from reportlab.platypus import Image as RLImage
    # 2026-09-20: zaxira yo'l ATAYLAB olib tashlandi. Ilgari bu yerda
    # `or os.path.join(..., "logo_transparent.png")` bor edi — ya'ni
    # korxonaning logotipi bo'lmasa, PLATFORMA EGASINING logotipi
    # qo'yilardi va yangi mijozning nakladnoyida begona logotip chiqardi
    # (jonli sinovda aniqlandi). Logotip bo'lmasa — pastdagi `else`
    # tarmog'i korxona NOMINI yozadi.
    # 2026-09-20: nakladnoyda TELEFON ham chiqadi — u mijozga
    # beriladigan hujjat va savol chiqsa qaerga murojaat qilishni
    # bilishi kerak. Manzil va telefon bitta qatorda, joy tejash uchun.
    _kontakt = "  ·  ".join([x for x in (_brand["address"], _brand["phone"]) if x])

    logo_path = _brand["logo"]
    # kech129 (zip 153): o'lcham — fayl nisbatidan (`_logo_olcham`); fayl o'qilmasa — logotipsiz sarlavha (korxona nomi)
    _lo = _logo_olcham(logo_path) if logo_path and os.path.exists(logo_path) else None

    if _lo:
        # MUHIM (2026-08-29): endi haqiqiy shaffof fonli PNG ishlatiladi
        # (nisbati 1.779) — shu nisbatga mos o'lcham berilmasa, logotip
        # cho'zilib/torayib, buzilib ko'rinardi.
        logo_img = RLImage(logo_path, width=_lo[0], height=_lo[1])
        logo_img.hAlign = 'LEFT'
        header_left = [
            logo_img,
            Paragraph(_x(_brand["slogan"]), st["company_sub"]),
            Paragraph(_x(_kontakt), st["company_sub"]),
        ]
    else:
        header_left = [
            Paragraph(_x(_brand["name"]), st["company"]),
            Paragraph(_x(_brand["slogan"]), st["company_sub"]),
            Paragraph(_x(_kontakt), st["company_sub"]),
        ]
    # Bo'sh qatorlarni olib tashlaymiz (maydon to'ldirilmagan bo'lsa,
    # hujjatda bo'sh joy qolib ketmasin).
    header_left = [x for x in header_left
                   if not (hasattr(x, "text") and not str(x.text).strip())]

    header_data = [[
        header_left,
        [
            # kech118 (D-1, G6-11 — egasi QARORI «Taklif qilingan lug'at»): «Buyurtma hisobi» (ilgari «NAKLADNOY» — yuk xati va
            # sotuv hujjati bilan bir xil nomda edi, mijoz qog'ozni sarlavhasidan ajrata olmasdi)
            # kech126 (zip 148): taklif — «TAKLIF (HISOB-KITOB)» (egasi qarori), sana — taklif sanasi (narxlar shu kundan 3 kun)
            Paragraph("TAKLIF (HISOB-KITOB)", st["doc_title"]) if taklif else Paragraph("BUYURTMA HISOBI", st["doc_title"]),
            Paragraph(f"# {_x(order.order_number)}", st["doc_num"]),
            Paragraph(f"Sana: {_tashkent_vaqt(_hujjat_vaqti).strftime('%d.%m.%Y')}", st["doc_num"]),
        ],
    ]]

    header_tbl = Table(header_data, colWidths=[W*0.6, W*0.4])
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ALIGN", (1,0), (1,0), "RIGHT"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8*(1-cx*0.75)),
    ]))
    story.append(header_tbl)
    story.append(HRFlowable(width="100%", thickness=2, color=GOLD, spaceAfter=10))

    # ── MIJOZ MA'LUMOTLARI ────────────────────────────────────
    project = order.project
    status_val = order.status.value if hasattr(order.status, 'value') else str(order.status)
    status_txt = STATUS_UZ.get(status_val, status_val)

    info_data = [[
        [
            Paragraph("MIJOZ", st["section_label"]),
            Paragraph(_x(project.client_name if project else "—"), st["section_value"]),
            Spacer(1, 4*(1-cx*0.7)),
            Paragraph("TELEFON", st["section_label"]),
            Paragraph(_x(project.client_phone or "—"), st["section_value_sm"]),
            Spacer(1, 4*(1-cx*0.7)),
            Paragraph("MANZIL", st["section_label"]),
            Paragraph(_x(project.client_address or "—"), st["section_value_sm"]),
        ],
        [
            Paragraph("LOYIHA", st["section_label"]),
            Paragraph(_x(project.project_name if project else "—"), st["section_value"]),
            Spacer(1, 4*(1-cx*0.7)),
            Paragraph("BUYURTMA RAQAMI", st["section_label"]),
            Paragraph(order.order_number, st["section_value_sm"]),
            Spacer(1, 4*(1-cx*0.7)),
            Paragraph("YARATILGAN SANA", st["section_label"]),
            Paragraph(_tashkent_vaqt(order.created_at).strftime("%d.%m.%Y") if order.created_at else "—", st["section_value_sm"]),
        ],
        [
            Paragraph("HOLATI", st["section_label"]),
            Paragraph(status_txt, st["section_value"]),
            Spacer(1, 4*(1-cx*0.7)),
            # kech120 (zip 136 — G6-12): «TURI: Mahsulot / Xizmat» — mijozga ma'nosiz, olib tashlandi
            Paragraph("USTA", st["section_label"]),
            Paragraph(_x(order.master.name if order.master else "Belgilanmagan"), st["section_value_sm"]),
        ],
    ]]

    if taklif:
        # kech126 (zip 148): taklifda loyiha, buyurtma holati va usta yo'q — mijoz va taklif ma'lumoti (ikki ustun)
        info_data = [[
            [
                Paragraph("MIJOZ", st["section_label"]),
                Paragraph(_x(project.client_name if project else "—"), st["section_value"]),
                Spacer(1, 4*(1-cx*0.7)),
                Paragraph("TELEFON", st["section_label"]),
                Paragraph(_x(project.client_phone or "—"), st["section_value_sm"]),
            ],
            [
                Paragraph("TAKLIF RAQAMI", st["section_label"]),
                Paragraph(_x(order.order_number), st["section_value"]),
                Spacer(1, 4*(1-cx*0.7)),
                Paragraph("SANA", st["section_label"]),
                Paragraph(f"{_tashkent_vaqt(_hujjat_vaqti).strftime('%d.%m.%Y')}", st["section_value_sm"]),
            ],
        ]]
    info_tbl = Table(info_data, colWidths=([W/2, W/2] if taklif else [W/3, W/3, W/3]))
    info_tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("BACKGROUND", (0,0), (-1,-1), LIGHT),
        ("TOPPADDING", (0,0), (-1,-1), 10*(1-cx*0.75)),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10*(1-cx*0.75)),
        ("LEFTPADDING", (0,0), (-1,-1), 12),
        ("RIGHTPADDING", (0,0), (-1,-1), 12),
        ("LINEAFTER", (0,0), ((0 if taklif else 1),-1), 0.5, LGRAY),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 12*(1-cx*0.7)))

    # ── MAHSULOTLAR JADVALI ───────────────────────────────────
    # kech120 (zip 136 — F bosqichi 5-qism, audit G6-12): birlik — boshqa hujjatlar va sahifalardagidek umumiy qoida
    # (`services.birlik_korinish`: «m», «m²», «dona», «kg», «qop» …); ilgari katta harf va «TA» («M», «TA», «KG» — yuk xatida «30 metr»,
    # hisob-kitobda «30 m»). Yangi (MRP) mahsulot — o'z turining birligi (zip 133).
    from services import birlik_korinish as _bk136, son_korinish as _sk136

    def get_unit(item):
        cat = (item.category or '').lower()
        if cat in ('profil', 'panel', 'blok'): return 'm'
        elif cat == 'termopanel': return 'm²'
        elif cat == 'dona': return 'dona'
        elif cat == 'loy_sotish': return 'kg'
        elif cat == 'gips':
            gu = (getattr(item, 'gips_unit', None) or 'metr').lower()
            return 'm²' if gu == 'm2' else ('m' if gu == 'metr' else 'dona')
        elif cat == 'mrp_product':
            try:
                return _bk136(getattr(item, 'delivery_unit', None))
            except Exception:
                return 'dona'
        else: return 'dona'

    col_widths = [W*0.05, W*0.35, W*0.10, W*0.12, W*0.19, W*0.19]

    table_data = [[
        Paragraph("#", st["table_header"]),
        Paragraph("Mahsulot nomi", st["table_header"]),
        Paragraph("O'lchov\nbirligi", st["table_header"]),
        Paragraph("Miqdori", st["table_header"]),
        Paragraph("Birlik narxi\n(so'm)", st["table_header"]),
        Paragraph("Jami\n(so'm)", st["table_header"]),
    ]]

    items = order.items if order.items else []
    row_bg = [DARK]

    for i, item in enumerate(items):
        unit_price  = float(item.unit_price  or 0)
        total_price = float(item.total_price or 0)
        unit = get_unit(item)
        bg = WHITE if i % 2 == 0 else LIGHT
        row_bg.append(bg)

        # Miqdor: profil uchun uzunlik, panel uchun miqdor, donali uchun dona
        item_cat = (item.category or "").lower()
        if item_cat == "profil":
            miqdor = float(item.length or 0)
        elif item_cat == "panel":
            miqdor = float(item.quantity or 0)
        else:
            miqdor = float(item.quantity or 0)
        # kech120 (zip 136 — G6-12): kasrli miqdor yaxlitlanmaydi (ilgari «2.5 m» → «2», narx × miqdor ≠ jami ko'rinardi);
        # son — umumiy qoida (`son_korinish`: «2,5», «1 234»)
        miqdor_txt = _sk136(miqdor, 3)

        # MUHIM: item.unit_price ba'zi turlarda (masalan Profil) DETALNING
        # UMUMIY narxini saqlaydi (miqdor=1 bo'lgani uchun), 1 birlik narxini
        # emas. Shuning uchun haqiqiy "1 birlik narxi"ni Jami ÷ Miqdor orqali
        # qayta hisoblaymiz — shunda jadvaldagi 3 ustun (Birlik × Miqdor = Jami)
        # doim bir-biriga mos keladi.
        true_unit_price = (total_price / miqdor) if miqdor > 0 else unit_price

        if (item.category or '').lower() == 'gips':
            item_label = f"{item.name} (GIPS)"
        elif item.is_coated:
            item_label = f"{item.name} (qoplamali)"
        else:
            item_label = str(item.name)

        table_data.append([
            Paragraph(str(i+1), st["table_cell_c"]),
            Paragraph(_x(item_label), st["table_cell"]),
            Paragraph(_x(unit), st["table_cell_c"]),
            Paragraph(_x(miqdor_txt), st["table_cell_c"]),
            Paragraph(_x(_pul_matni(true_unit_price)), st["table_cell_r"]),
            Paragraph(_x(_pul_matni(total_price)), st["table_cell_r"]),
        ])

    if not items:
        row_bg.append(WHITE)
        table_data.append([
            Paragraph("—", st["table_cell_c"]),
            Paragraph("Mahsulotlar yo'q", st["table_cell"]),
            "", "", "", "",
        ])

    items_tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl_style = [
        ("BACKGROUND", (0,0), (-1,0), DARK),
        ("TEXTCOLOR", (0,0), (-1,0), WHITE),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 8*(1-cx*0.3)),
        ("TOPPADDING", (0,0), (-1,-1), 5*(1-cx*0.75)),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5*(1-cx*0.75)),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("GRID", (0,0), (-1,-1), 0.3, LGRAY),
        ("LINEBELOW", (0,0), (-1,0), 1.5, GOLD),
        ("ALIGN", (4,1), (-1,-1), "RIGHT"),
    ]
    for idx, bg in enumerate(row_bg):
        tbl_style.append(("BACKGROUND", (0,idx), (-1,idx), bg))
    items_tbl.setStyle(TableStyle(tbl_style))
    story.append(items_tbl)
    story.append(Spacer(1, 10*(1-cx*0.7)))

    # ── JAMI HISOB ────────────────────────────────────────────
    # MUHIM: Yetkazib berishda mijoz o'z ulushini (masalan 50/50 holatda)
    # to'g'ridan-to'g'ri HAYDOVCHIGA naqd beradi — kompaniyaning bu pulga
    # aloqasi yo'q, shuning uchun bu HECH QACHON "qarz" yoki "to'lov
    # summasi"ga qo'shilmaydi. Faqat kompaniya o'z zimmasiga olgan ulush
    # (company_transport_cost) — bu alohida, Moliya xarajati sifatida
    # hisoblanadi (bu yerga umuman aloqasi yo'q).
    #
    # kech116 (G2-04, O'LCHANGAN — audit kech114): ilgari «Chegirma» = jami − kelishilgan edi — qaytgan mahsulot
    # (36 000) va kechirilgan qarz ham «Chegirma» bo'lib yozilardi (buyurtma oynasida ular alohida), qarz esa o'z
    # formulasi bilan (`max(0, kelishilgan − to'langan)`, yarim so'm bardoshisiz). Endi qatorlar — YAGONA qoida
    # (`crud.buyurtma_hisob_qatorlari`; yuk xati, hisob-kitob varaqasi va buyurtma oynasi ham shundan; qaytarish —
    # alohida qator):
    # Umumiy jami − Chegirma − Qaytarish = TO'LOV SUMMASI (kelishilgan); − To'langan = QARZ QOLDI. To'lovda kechirilgan qarz —
    # «Chegirma» ichida (foizsiz; egasi QARORI kech116 — mijoz hujjatida «Kechirilgan qarz» so'zi chiqmaydi).
    import crud as _crud_nak
    # kech126 (zip 148): taklif — qatorlar `generate_taklif` da o'sha qoida bilan hisoblangan (to'lov yo'q)
    _hisob = taklif["hisob"] if taklif else _crud_nak.buyurtma_hisob_qatorlari(db, order, mijoz_hujjati=True)
    _NOMI = {"jami": "Umumiy jami:", "kelishilgan": "TO'LOV SUMMASI:"}
    totals_data = []
    grand_total_row = None
    for q in _hisob["qatorlar"]:
        if taklif and q["kalit"] in ("tolangan", "qarz", "ortiqcha"):
            continue                                  # taklif — hali to'lov / qarz yo'q
        if q["kalit"] == "tolangan" and q["summa"] == 0:
            continue                                  # to'lov yo'q — qator ko'rsatilmaydi (avvalgidek)
        if q["kalit"] == "qarz" and q["summa"] == 0:
            continue                                  # qarz yo'q — qator ko'rsatilmaydi (avvalgidek)
        if q["kalit"] == "tolangan":
            totals_data.append([
                Paragraph("To'langan:", st["doc_num"]),
                Paragraph(f"{_pul_matni(q['summa'])} so'm", st["doc_num"]),
            ])
            continue
        belgi = {"-": "- ", "+": "+ "}.get(q["ishora"], "")
        nom = _NOMI.get(q["kalit"], q["nom"] + ":")
        katta = q["kalit"] in ("kelishilgan", "qarz", "ortiqcha")
        totals_data.append([
            Paragraph(_x(nom), st["total_label"]),
            Paragraph(f"{_x(belgi)}{_pul_matni(q['summa'])} so'm", st["total_value"] if katta else st["total_label"]),
        ])
        if q["kalit"] == "kelishilgan":
            grand_total_row = len(totals_data) - 1
    if grand_total_row is None:
        # kech120 (zip 136 — F bosqichi 5-qism, audit G6-12): chegirma / qaytarish / kechirilgan yo'q — kelishilgan = jami. Ilgari
        # «Umumiy jami» va «TO'LOV SUMMASI» — bir xil raqam, ketma-ket ikki qator edi; endi BITTA qator «TO'LOV SUMMASI».
        totals_data[0] = [
            Paragraph("TO'LOV SUMMASI:", st["total_label"]),
            Paragraph(f"{_pul_matni(_hisob['korinish']['kelishilgan'])} so'm", st["total_value"]),
        ]
        grand_total_row = 0

    totals_tbl = Table(totals_data, colWidths=[W*0.7, W*0.3])
    totals_tbl.setStyle(TableStyle([
        ("ALIGN", (0,0), (-1,-1), "RIGHT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 4*(1-cx*0.75)),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4*(1-cx*0.75)),
        ("GRID", (0,0), (-1,-1), 0.3, LGRAY),
        ("BACKGROUND", (0,0), (-1,0), LIGHT),
        ("LINEABOVE", (0,grand_total_row), (-1,grand_total_row), 1.5, GOLD),
        ("BACKGROUND", (0,grand_total_row), (-1,grand_total_row), colors.HexColor("#FDF8F0")),
    ]))
    story.append(totals_tbl)
    story.append(Spacer(1, 16*(1-cx*0.7)))

    # ── IZOH ──────────────────────────────────────────────────
    if order.notes:
        # loy_kg, planned_loy va [WRITEOFF:...] kabi ICHKI (tizim uchun)
        # belgilarni izohdan chiqarib tashlaymiz — mijozga ko'rinadigan
        # hujjatda bunday texnik yozuvlar bo'lishi kerak emas.
        # MUHIM: "[WRITEOFF:...]" ni ALOHIDA, regex bilan tozalaymiz (faqat
        # o'sha bitta belgini olib tashlaydi, atrofidagi haqiqiy mijoz
        # matniga tegmaydi) — chunki u har doim ham "loy_kg=" bilan bitta
        # vergul-segmentida bo'lavermaydi (masalan Loysiz buyurtmada
        # yolg'iz o'zi qolishi mumkin edi).
        import re as _re_pdf_notes
        _notes_no_writeoff = _re_pdf_notes.sub(r'\s*\[WRITEOFF:[\d.]+\]', '', order.notes or '')
        notes_clean = ', '.join([
            p for p in _notes_no_writeoff.split(',')
            if 'loy_kg=' not in p and 'planned_loy=' not in p
        ]).strip(', ')
        if notes_clean:
            story.append(HRFlowable(width="100%", thickness=0.5, color=LGRAY, spaceAfter=6))
            story.append(Paragraph("Izoh:", st["section_label"]))
            story.append(Paragraph(_x(notes_clean), st["note"]))
            story.append(Spacer(1, 10*(1-cx*0.7)))

    if taklif:
        # kech126 (zip 148 — egasi qarori): taklif hujjati pastida — «Narxlar 3 kun amal qiladi» (imzo qatori yo'q: hali
        # topshirish yo'q). Muddat `crud.TAKLIF_MUDDAT_KUN` bilan bir xil (tools/test_taklif.py tekshiradi).
        story.append(Spacer(1, 10*(1-cx*0.7)))
        story.append(HRFlowable(width="100%", thickness=1, color=GOLD, spaceAfter=6))
        story.append(Paragraph("Narxlar 3 kun amal qiladi", st["total_label"]))
        story.append(Spacer(1, 16*(1-cx*0.7)))
        story.append(HRFlowable(width="100%", thickness=0.5, color=LGRAY, spaceAfter=6))
        story.append(Paragraph(
            f"{_x(_brand['name'])} · Chiqarilgan: {_tashkent_vaqt().strftime('%d.%m.%Y %H:%M')} · "
            f"Taklif: {_x(order.order_number)}",
            st["footer"]
        ))
        doc.build(story)
        return buf.getvalue()

    # ── IMZO QATORI ───────────────────────────────────────────
    story.append(Spacer(1, 20*(1-cx*0.7)))
    sign_data = [[
        [
            Paragraph("Berdi:", st["imzo"]),
            Spacer(1, 20*(1-cx*0.7)),
            HRFlowable(width="80%", thickness=0.5, color=IZOH_RANG),
            Paragraph("Imzo / Sana", st["imzo"]),
        ],
        [
            Paragraph("Qabul qildi:", st["imzo"]),
            Spacer(1, 20*(1-cx*0.7)),
            HRFlowable(width="80%", thickness=0.5, color=IZOH_RANG),
            Paragraph("Imzo / Sana", st["imzo"]),
        ],
    ]]
    sign_tbl = Table(sign_data, colWidths=[W/2, W/2])
    sign_tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "BOTTOM"),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(sign_tbl)

    # ── PASTKI QISM ───────────────────────────────────────────
    story.append(Spacer(1, 16*(1-cx*0.7)))
    story.append(HRFlowable(width="100%", thickness=0.5, color=LGRAY, spaceAfter=6))
    story.append(Paragraph(
        f"{_x(_brand['name'])} · Chiqarilgan: {_tashkent_vaqt().strftime('%d.%m.%Y %H:%M')} · "
        f"Buyurtma: {_x(order.order_number)}",
        st["footer"]
    ))

    doc.build(story)
    return buf.getvalue()


def generate_taklif(t, db=None) -> bytes:
    """kech126 (zip 148 — EGASI QARORLARI 07.10 «Tez hisob / Taklif»): taklif PDF i — `generate_nakladnoy` shablonining O'ZI
    («Buyurtma hisobi» ko'rinishida). Taklif bazada PDF bo'lib saqlanmaydi — har safar saqlangan tanadan yasaladi (sana —
    oxirgi saqlash vaqti: narxlar shu kundan 3 kun). Detal qatorlari — buyurtma saqlaydigan qiymatlar (`crud.taklif_hisobi` —
    `create_order` bilan bir qoida), summa qatorlari — `crud.buyurtma_hisob_qatorlari` (mijoz hujjati) qoidasi."""
    from types import SimpleNamespace as _NS
    import crud as _crud_tk
    _sh = _crud_tk.taklif_buyurtma_shakli(t)
    _items = []
    for _d in _sh["items"]:
        _items.append(_NS(
            name=str(_d.get("name") or ""), category=_d.get("category"), is_coated=bool(_d.get("is_coated")),
            length=_d.get("length"), quantity=_d.get("quantity"), width=_d.get("width"), thickness=_d.get("thickness"),
            unit_price=_d.get("unit_price"), total_price=_d.get("total_price"), delivery_unit=None,
            gips_unit=_d.get("gips_unit"),
        ))
    _jami, _kel = float(_sh["total_amount"] or 0), float(_sh["kelishilgan"] or 0)
    # summa qatorlari — buyurtma hujjati qoidasi: to'lov 0, qarz = kelishilgan (qatorlari hujjatda ko'rsatilmaydi)
    _ord = _NS(total_amount=_jami, kechirilgan=0.0, kelishilgan_summa=_kel, paid_amount=0.0, debt_amount=_kel,
               ortiqcha_tolov=0.0)
    _hisob = _crud_tk.buyurtma_hisob_qatorlari(None, _ord, qaytarish=0.0, mijoz_hujjati=True)
    _hujjat = _NS(
        id=t.id, company_id=t.company_id, order_number=t.raqam, items=_items, notes=_sh.get("notes"),
        created_at=t.yaratilgan, status=None, master=None,
        project=_NS(client_name=t.mijoz, client_phone=t.telefon, client_address=None, project_name=None),
    )
    return generate_nakladnoy(_hujjat, db, taklif={"sana": t.tahrirlangan or t.yaratilgan, "hisob": _hisob})
