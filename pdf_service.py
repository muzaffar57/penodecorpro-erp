"""
PenoDecorPro ERP — PDF Nakladnoy generatsiyasi
================================================
ReportLab yordamida chiroyli nakladnoy (hisob-faktura) chiqaradi.

Ishlatilishi:
    pdf_bytes = generate_nakladnoy(order, db)
    # PDF ni brauzerga yuborish uchun FastAPI Response ishlatiladi
"""

import io
from datetime import datetime
from typing import Optional

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
DARK   = colors.HexColor("#1A252F")   # Sarlavha foni
GOLD   = colors.HexColor("#C9A55A")   # Urg'u rangi
LIGHT  = colors.HexColor("#F4F6F8")   # Jadval qatori foni
WHITE  = colors.white
RED    = colors.HexColor("#E74C3C")
GREEN  = colors.HexColor("#27AE60")
GRAY   = colors.HexColor("#7F8C8D")
LGRAY  = colors.HexColor("#BDC3C7")


# ============================================================
# Shriftlar va uslublar
# ============================================================

def get_styles():
    return {
        "company": ParagraphStyle(
            "company", fontName="Helvetica-Bold",
            fontSize=20, textColor=GOLD, leading=24
        ),
        "company_sub": ParagraphStyle(
            "company_sub", fontName="Helvetica",
            fontSize=9, textColor=LGRAY, leading=12
        ),
        "doc_title": ParagraphStyle(
            "doc_title", fontName="Helvetica-Bold",
            fontSize=14, textColor=DARK, leading=18,
            alignment=TA_RIGHT
        ),
        "doc_num": ParagraphStyle(
            "doc_num", fontName="Helvetica",
            fontSize=10, textColor=GRAY, leading=14,
            alignment=TA_RIGHT
        ),
        "section_label": ParagraphStyle(
            "section_label", fontName="Helvetica",
            fontSize=8, textColor=GRAY, leading=10,
            spaceAfter=2
        ),
        "section_value": ParagraphStyle(
            "section_value", fontName="Helvetica-Bold",
            fontSize=10, textColor=DARK, leading=13
        ),
        "section_value_sm": ParagraphStyle(
            "section_value_sm", fontName="Helvetica",
            fontSize=9, textColor=DARK, leading=12
        ),
        "table_header": ParagraphStyle(
            "table_header", fontName="Helvetica-Bold",
            fontSize=9, textColor=WHITE, leading=11,
            alignment=TA_CENTER
        ),
        "table_cell": ParagraphStyle(
            "table_cell", fontName="Helvetica",
            fontSize=9, textColor=DARK, leading=11
        ),
        "table_cell_c": ParagraphStyle(
            "table_cell_c", fontName="Helvetica",
            fontSize=9, textColor=DARK, leading=11,
            alignment=TA_CENTER
        ),
        "table_cell_r": ParagraphStyle(
            "table_cell_r", fontName="Helvetica",
            fontSize=9, textColor=DARK, leading=11,
            alignment=TA_RIGHT
        ),
        "total_label": ParagraphStyle(
            "total_label", fontName="Helvetica-Bold",
            fontSize=11, textColor=DARK, leading=14,
            alignment=TA_RIGHT
        ),
        "total_value": ParagraphStyle(
            "total_value", fontName="Helvetica-Bold",
            fontSize=13, textColor=GOLD, leading=16,
            alignment=TA_RIGHT
        ),
        "footer": ParagraphStyle(
            "footer", fontName="Helvetica",
            fontSize=8, textColor=GRAY, leading=10,
            alignment=TA_CENTER
        ),
        "note": ParagraphStyle(
            "note", fontName="Helvetica",
            fontSize=9, textColor=GRAY, leading=12
        ),
        "status_ok": ParagraphStyle(
            "status_ok", fontName="Helvetica-Bold",
            fontSize=9, textColor=GREEN, leading=11,
            alignment=TA_CENTER
        ),
        "status_new": ParagraphStyle(
            "status_new", fontName="Helvetica-Bold",
            fontSize=9, textColor=GRAY, leading=11,
            alignment=TA_CENTER
        ),
    }


# ============================================================
# Status tarjimasi
# ============================================================
STATUS_UZ = {
    "new":         "Yangi",
    "in_progress": "Jarayonda",
    "coating":     "Qoplama",
    "ready":       "Tayyor",
    "delivered":   "Yetkazildi",
    "cancelled":   "Bekor qilindi",
}

ORDER_TYPE_UZ = {
    "service": "Xizmat",
    "product": "Mahsulot",
}


# ============================================================
# Asosiy funksiya
# ============================================================

def generate_nakladnoy(order, db=None) -> bytes:
    """
    Buyurtma uchun PDF nakladnoy yaratadi.
    Qaytaradi: PDF baytlari (io.BytesIO content).
    """
    buf = io.BytesIO()
    st  = get_styles()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=15*mm,  bottomMargin=15*mm,
    )

    W = A4[0] - 36*mm   # Ish kengligi
    story = []

    # ── SARLAVHA QATORI ──────────────────────────────────────
    import os
    from reportlab.platypus import Image as RLImage

    # Logo fayl yo'li
    logo_path = os.path.join(os.path.dirname(__file__), "static", "logo_wide.jpg")

    # Logo mavjud bo'lsa ishlatamiz
    if os.path.exists(logo_path):
        logo_img = RLImage(logo_path, width=50*mm, height=18*mm)
        logo_img.hAlign = 'LEFT'
        header_left = [
            logo_img,
            Paragraph("Dekorativ fasad materiallari ishlab chiqaruvchi", st["company_sub"]),
            Paragraph("Andijon, O'zbekiston", st["company_sub"]),
        ]
    else:
        header_left = [
            Paragraph("PenoDecorPro", st["company"]),
            Paragraph("Dekorativ fasad materiallari ishlab chiqaruvchi", st["company_sub"]),
            Paragraph("Andijon, O'zbekiston", st["company_sub"]),
        ]

    header_data = [[
        header_left,
        [
            Paragraph("NAKLADNOY", st["doc_title"]),
            Paragraph(f"# {order.order_number}", st["doc_num"]),
            Paragraph(f"Sana: {datetime.now().strftime('%d.%m.%Y')}", st["doc_num"]),
        ],
    ]]

    header_tbl = Table(header_data, colWidths=[W*0.6, W*0.4])
    header_tbl.setStyle(TableStyle([
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
        ("ALIGN",        (1,0), (1,0),   "RIGHT"),
        ("BOTTOMPADDING",(0,0), (-1,-1), 8),
    ]))
    story.append(header_tbl)

    # Oltin chiziq
    story.append(HRFlowable(width="100%", thickness=2,
                            color=GOLD, spaceAfter=10))

    # ── MIJOZ VA BUYURTMA MA'LUMOTLARI ───────────────────────
    project = order.project

    # Status belgisi
    status_val = order.status.value if hasattr(order.status, 'value') else str(order.status)
    status_txt = STATUS_UZ.get(status_val, status_val)
    order_type  = ORDER_TYPE_UZ.get(
        order.order_type.value if hasattr(order.order_type, 'value') else str(order.order_type),
        "—"
    )

    info_data = [[
        # Mijoz ma'lumotlari
        [
            Paragraph("MIJOZ", st["section_label"]),
            Paragraph(project.client_name if project else "—", st["section_value"]),
            Spacer(1, 4),
            Paragraph("TELEFON", st["section_label"]),
            Paragraph(project.client_phone or "—", st["section_value_sm"]),
            Spacer(1, 4),
            Paragraph("MANZIL", st["section_label"]),
            Paragraph(project.client_address or "—", st["section_value_sm"]),
        ],
        # Loyiha ma'lumotlari
        [
            Paragraph("LOYIHA", st["section_label"]),
            Paragraph(project.project_name if project else "—", st["section_value"]),
            Spacer(1, 4),
            Paragraph("BUYURTMA RAQAMI", st["section_label"]),
            Paragraph(order.order_number, st["section_value_sm"]),
            Spacer(1, 4),
            Paragraph("YARATILGAN SANA", st["section_label"]),
            Paragraph(
                order.created_at.strftime("%d.%m.%Y") if order.created_at else "—",
                st["section_value_sm"]
            ),
        ],
        # Qo'shimcha
        [
            Paragraph("HOLATI", st["section_label"]),
            Paragraph(status_txt, st["section_value"]),
            Spacer(1, 4),
            Paragraph("TURI", st["section_label"]),
            Paragraph(order_type, st["section_value_sm"]),
            Spacer(1, 4),
            Paragraph("USTA", st["section_label"]),
            Paragraph(
                order.master.name if order.master else "Belgilanmagan",
                st["section_value_sm"]
            ),
        ],
    ]]

    info_tbl = Table(info_data, colWidths=[W/3, W/3, W/3])
    info_tbl.setStyle(TableStyle([
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
        ("BACKGROUND",   (0,0), (-1,-1), LIGHT),
        ("ROUNDEDCORNERS", (0,0), (-1,-1), [4]),
        ("TOPPADDING",   (0,0), (-1,-1), 10),
        ("BOTTOMPADDING",(0,0), (-1,-1), 10),
        ("LEFTPADDING",  (0,0), (-1,-1), 12),
        ("RIGHTPADDING", (0,0), (-1,-1), 12),
        ("LINEAFTER",    (0,0), (1,-1),  0.5, LGRAY),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 12))

    # ── MAHSULOTLAR JADVALI ──────────────────────────────────
    def get_unit(item):
        cat = (item.category or '').lower()
        if cat == 'profil': return 'M'
        elif cat == 'panel': return 'M'
        elif cat == 'dona': return 'TA'
        else: return 'TA'

    col_widths = [W*0.05, W*0.35, W*0.10, W*0.12, W*0.19, W*0.19]

    table_data = [[
        Paragraph("#",                    st["table_header"]),
        Paragraph("Mahsulot nomi",        st["table_header"]),
        Paragraph("O'lchov\nbirligi",   st["table_header"]),
        Paragraph("Miqdori",              st["table_header"]),
        Paragraph("Birlik narxi\n(so'm)", st["table_header"]),
        Paragraph("Jami\n(so'm)",       st["table_header"]),
    ]]

    items = order.items if order.items else []
    row_bg = [DARK]

    for i, item in enumerate(items):
        unit_price  = float(item.unit_price  or 0)
        total_price = float(item.total_price or 0)
        unit = get_unit(item)
        bg = WHITE if i % 2 == 0 else LIGHT
        row_bg.append(bg)
        table_data.append([
            Paragraph(str(i+1),                    st["table_cell_c"]),
            Paragraph(str(item.name),              st["table_cell"]),
            Paragraph(unit,                        st["table_cell_c"]),
            Paragraph(f"{item.quantity:.0f} {unit}", st["table_cell_c"]),
            Paragraph(f"{unit_price:,.0f}",        st["table_cell_r"]),
            Paragraph(f"{total_price:,.0f}",       st["table_cell_r"]),
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
        ("BACKGROUND",    (0,0), (-1,0),  DARK),
        ("TEXTCOLOR",     (0,0), (-1,0),  WHITE),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,0),  8),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ("RIGHTPADDING",  (0,0), (-1,-1), 4),
        ("GRID",          (0,0), (-1,-1), 0.3, LGRAY),
        ("LINEBELOW",     (0,0), (-1,0),  1.5, GOLD),
        ("ALIGN",         (4,1), (-1,-1), "RIGHT"),
    ]
    for idx, bg in enumerate(row_bg):
        tbl_style.append(("BACKGROUND", (0,idx), (-1,idx), bg))
    items_tbl.setStyle(TableStyle(tbl_style))
    story.append(items_tbl)
    story.append(Spacer(1, 10))

    # ── JAMI HISOB ───────────────────────────────────────────
    subtotal = sum(float(i.total_price or 0) for i in items)
    total    = float(order.total_amount or 0)
    discount = subtotal - total  # chegirma summasi
    paid     = float(project.total_paid or 0) if project else 0
    qarz     = max(0, total - paid)

    totals_data = []
    totals_data.append([
        Paragraph("Umumiy jami:", st["total_label"]),
        Paragraph(f"{subtotal:,.0f} so'm", st["total_label"]),
    ])
    if discount > 1:
        totals_data.append([
            Paragraph("Chegirma:", st["total_label"]),
            Paragraph(f"- {discount:,.0f} so'm", st["total_label"]),
        ])
    totals_data.append([
        Paragraph("TO'LOV SUMMASI:", st["total_label"]),
        Paragraph(f"{total:,.0f} so'm", st["total_value"]),
    ])
    if paid > 0:
        totals_data.append([
            Paragraph("Zaklat (to'langan):", st["doc_num"]),
            Paragraph(f"{paid:,.0f} so'm", st["doc_num"]),
        ])
    if qarz > 0:
        totals_data.append([
            Paragraph("QZR QOLDI:", st["total_label"]),
            Paragraph(f"{qarz:,.0f} so'm", st["total_value"]),
        ])

    totals_tbl = Table(totals_data, colWidths=[W*0.7, W*0.3])
    totals_tbl.setStyle(TableStyle([
        ("ALIGN",        (0,0), (-1,-1), "RIGHT"),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
        ("GRID",         (0,0), (-1,-1), 0.3, LGRAY),
        ("BACKGROUND",   (0,0), (-1,0),  LIGHT),
        ("LINEABOVE",    (0,2), (-1,2),  1.5, GOLD),
        ("BACKGROUND",   (0,2), (-1,2),  colors.HexColor("#FDF8F0")),
    ]))
    story.append(totals_tbl)
    story.append(Spacer(1, 16))

    # ── IZOH ─────────────────────────────────────────────────
    if order.notes:
        story.append(HRFlowable(width="100%", thickness=0.5,
                                color=LGRAY, spaceAfter=6))
        story.append(Paragraph("Izoh:", st["section_label"]))
        story.append(Paragraph(order.notes, st["note"]))
        story.append(Spacer(1, 10))

    # ── IMZO QATORI ──────────────────────────────────────────
    story.append(Spacer(1, 20))
    sign_data = [[
        [
            Paragraph("Berdi:", st["section_label"]),
            Spacer(1, 20),
            HRFlowable(width="80%", thickness=0.5, color=LGRAY),
            Paragraph("Imzo / Sana", st["section_label"]),
        ],
        [
            Paragraph("Qabul qildi:", st["section_label"]),
            Spacer(1, 20),
            HRFlowable(width="80%", thickness=0.5, color=LGRAY),
            Paragraph("Imzo / Sana", st["section_label"]),
        ],
    ]]
    sign_tbl = Table(sign_data, colWidths=[W/2, W/2])
    sign_tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "BOTTOM"),
        ("LEFTPADDING",  (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(sign_tbl)

    # ── PASTKI QISM ──────────────────────────────────────────
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5,
                            color=LGRAY, spaceAfter=6))
    story.append(Paragraph(
        f"PenoDecorPro ERP · Chiqarilgan: {datetime.now().strftime('%d.%m.%Y %H:%M')} · "
        f"Buyurtma: {order.order_number}",
        st["footer"]
    ))

    doc.build(story)
    return buf.getvalue()
