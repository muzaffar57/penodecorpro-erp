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
DARK   = colors.HexColor("#1A252F")
GOLD   = colors.HexColor("#C9A55A")
LIGHT  = colors.HexColor("#F4F6F8")
WHITE  = colors.white
RED    = colors.HexColor("#E74C3C")
GREEN  = colors.HexColor("#27AE60")
GRAY   = colors.HexColor("#7F8C8D")
LGRAY  = colors.HexColor("#BDC3C7")


def get_styles(cx: float = 0.0):
    """cx — siqilish darajasi (0.0 = oddiy, 1.0 = eng siqilgan).
    Ko'p detalli buyurtmalarda hujjat 1 sahifaga sig'ishi uchun."""
    def L(a, b):
        return a + (b - a) * cx

    return {
        "company": ParagraphStyle("company", fontName="Helvetica-Bold", fontSize=L(20,14), textColor=GOLD, leading=L(24,16)),
        "company_sub": ParagraphStyle("company_sub", fontName="Helvetica", fontSize=L(9,6.5), textColor=LGRAY, leading=L(12,8)),
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


def generate_nakladnoy(order, db=None) -> bytes:
    """Buyurtma uchun PDF nakladnoy yaratadi.

    MUHIM: hujjat 1 sahifaga sig'ishi uchun, detallar soniga qarab
    shrift/bo'sh joy AVTOMATIK siqiladi (Yuk xatidagi bilan bir xil
    tamoyil)."""
    n_items = len(order.items or [])
    cx = max(0.0, min(1.0, (n_items - 6) / 14.0))

    buf = io.BytesIO()
    st  = get_styles(cx)

    margin_v = (15 - cx * 8) * mm
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=margin_v, bottomMargin=margin_v,
    )

    W = A4[0] - 36*mm
    story = []

    # ── SARLAVHA ──────────────────────────────────────────────
    import os
    from reportlab.platypus import Image as RLImage

    logo_path = os.path.join(os.path.dirname(__file__), "static", "logo_wide.jpg")

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
    order_type = ORDER_TYPE_UZ.get(
        order.order_type.value if hasattr(order.order_type, 'value') else str(order.order_type), "—"
    )

    info_data = [[
        [
            Paragraph("MIJOZ", st["section_label"]),
            Paragraph(project.client_name if project else "—", st["section_value"]),
            Spacer(1, 4*(1-cx*0.7)),
            Paragraph("TELEFON", st["section_label"]),
            Paragraph(project.client_phone or "—", st["section_value_sm"]),
            Spacer(1, 4*(1-cx*0.7)),
            Paragraph("MANZIL", st["section_label"]),
            Paragraph(project.client_address or "—", st["section_value_sm"]),
        ],
        [
            Paragraph("LOYIHA", st["section_label"]),
            Paragraph(project.project_name if project else "—", st["section_value"]),
            Spacer(1, 4*(1-cx*0.7)),
            Paragraph("BUYURTMA RAQAMI", st["section_label"]),
            Paragraph(order.order_number, st["section_value_sm"]),
            Spacer(1, 4*(1-cx*0.7)),
            Paragraph("YARATILGAN SANA", st["section_label"]),
            Paragraph(order.created_at.strftime("%d.%m.%Y") if order.created_at else "—", st["section_value_sm"]),
        ],
        [
            Paragraph("HOLATI", st["section_label"]),
            Paragraph(status_txt, st["section_value"]),
            Spacer(1, 4*(1-cx*0.7)),
            Paragraph("TURI", st["section_label"]),
            Paragraph(order_type, st["section_value_sm"]),
            Spacer(1, 4*(1-cx*0.7)),
            Paragraph("USTA", st["section_label"]),
            Paragraph(order.master.name if order.master else "Belgilanmagan", st["section_value_sm"]),
        ],
    ]]

    info_tbl = Table(info_data, colWidths=[W/3, W/3, W/3])
    info_tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("BACKGROUND", (0,0), (-1,-1), LIGHT),
        ("TOPPADDING", (0,0), (-1,-1), 10*(1-cx*0.75)),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10*(1-cx*0.75)),
        ("LEFTPADDING", (0,0), (-1,-1), 12),
        ("RIGHTPADDING", (0,0), (-1,-1), 12),
        ("LINEAFTER", (0,0), (1,-1), 0.5, LGRAY),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 12*(1-cx*0.7)))

    # ── MAHSULOTLAR JADVALI ───────────────────────────────────
    def get_unit(item):
        cat = (item.category or '').lower()
        if cat == 'profil': return 'M'
        elif cat == 'panel': return 'M'
        elif cat == 'blok': return 'M'
        elif cat == 'termopanel': return 'M²'
        elif cat == 'dona': return 'TA'
        elif cat == 'loy_sotish': return 'KG'
        elif cat == 'gips':
            gu = (getattr(item, 'gips_unit', None) or 'metr').lower()
            return 'M²' if gu == 'm2' else ('M' if gu == 'metr' else 'TA')
        else: return 'TA'

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
        miqdor_txt = f"{miqdor:.0f}"

        # MUHIM: item.unit_price ba'zi turlarda (masalan Profil) DETALNING
        # UMUMIY narxini saqlaydi (miqdor=1 bo'lgani uchun), 1 birlik narxini
        # emas. Shuning uchun haqiqiy "1 birlik narxi"ni Jami ÷ Miqdor orqali
        # qayta hisoblaymiz — shunda jadvaldagi 3 ustun (Birlik × Miqdor = Jami)
        # doim bir-biriga mos keladi.
        true_unit_price = (total_price / miqdor) if miqdor > 0 else unit_price

        if (item.category or '').lower() == 'gips':
            item_label = f"🧱 {item.name} (GIPS)"
        elif item.is_coated:
            item_label = f"{item.name} (qoplamali)"
        else:
            item_label = str(item.name)

        table_data.append([
            Paragraph(str(i+1), st["table_cell_c"]),
            Paragraph(item_label, st["table_cell"]),
            Paragraph(unit, st["table_cell_c"]),
            Paragraph(miqdor_txt, st["table_cell_c"]),
            Paragraph(f"{true_unit_price:,.0f}", st["table_cell_r"]),
            Paragraph(f"{total_price:,.0f}", st["table_cell_r"]),
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
    subtotal = sum(float(i.total_price or 0) for i in items)
    total    = float(order.total_amount or subtotal or 0)
    agreed   = float(order.agreed_amount or total)
    discount = max(total - agreed, 0)

    # MUHIM: Yetkazib berishda mijoz o'z ulushini (masalan 50/50 holatda)
    # to'g'ridan-to'g'ri HAYDOVCHIGA naqd beradi — kompaniyaning bu pulga
    # aloqasi yo'q, shuning uchun bu HECH QACHON "qarz" yoki "to'lov
    # summasi"ga qo'shilmaydi. Faqat kompaniya o'z zimmasiga olgan ulush
    # (company_transport_cost) — bu alohida, Moliya xarajati sifatida
    # hisoblanadi (bu yerga umuman aloqasi yo'q).
    grand_total = agreed
    paid  = order.paid_amount if hasattr(order, 'paid_amount') else 0
    qarz  = max(0, grand_total - paid)

    totals_data = []
    totals_data.append([
        Paragraph("Umumiy jami:", st["total_label"]),
        Paragraph(f"{total:,.0f} so'm", st["total_label"]),
    ])
    if discount > 1:
        totals_data.append([
            Paragraph("Chegirma:", st["total_label"]),
            Paragraph(f"- {discount:,.0f} so'm", st["total_label"]),
        ])
        totals_data.append([
            Paragraph("Kelishilgan summa:", st["total_label"]),
            Paragraph(f"{agreed:,.0f} so'm", st["total_label"]),
        ])
    grand_total_row = len(totals_data)
    totals_data.append([
        Paragraph("TO'LOV SUMMASI:", st["total_label"]),
        Paragraph(f"{grand_total:,.0f} so'm", st["total_value"]),
    ])
    if paid > 0:
        totals_data.append([
            Paragraph("To'langan:", st["doc_num"]),
            Paragraph(f"{paid:,.0f} so'm", st["doc_num"]),
        ])
    if qarz > 0:
        totals_data.append([
            Paragraph("QARZ QOLDI:", st["total_label"]),
            Paragraph(f"{qarz:,.0f} so'm", st["total_value"]),
        ])

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
        # loy_kg va planned_loy kabi ICHKI (tizim uchun) belgilarni
        # izohdan chiqarib tashlaymiz — mijozga ko'rinadigan hujjatda
        # bunday texnik yozuvlar bo'lishi kerak emas.
        notes_clean = ', '.join([
            p for p in (order.notes or '').split(',')
            if 'loy_kg=' not in p and 'planned_loy=' not in p
        ]).strip(', ')
        if notes_clean:
            story.append(HRFlowable(width="100%", thickness=0.5, color=LGRAY, spaceAfter=6))
            story.append(Paragraph("Izoh:", st["section_label"]))
            story.append(Paragraph(notes_clean, st["note"]))
            story.append(Spacer(1, 10*(1-cx*0.7)))

    # ── IMZO QATORI ───────────────────────────────────────────
    story.append(Spacer(1, 20*(1-cx*0.7)))
    sign_data = [[
        [
            Paragraph("Berdi:", st["section_label"]),
            Spacer(1, 20*(1-cx*0.7)),
            HRFlowable(width="80%", thickness=0.5, color=LGRAY),
            Paragraph("Imzo / Sana", st["section_label"]),
        ],
        [
            Paragraph("Qabul qildi:", st["section_label"]),
            Spacer(1, 20*(1-cx*0.7)),
            HRFlowable(width="80%", thickness=0.5, color=LGRAY),
            Paragraph("Imzo / Sana", st["section_label"]),
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
        f"PenoDecorPro ERP · Chiqarilgan: {datetime.now().strftime('%d.%m.%Y %H:%M')} · "
        f"Buyurtma: {order.order_number}",
        st["footer"]
    ))

    doc.build(story)
    return buf.getvalue()
