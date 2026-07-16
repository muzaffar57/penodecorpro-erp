"""
PenoDecorPro ERP — Yetkazish nakladnoyi (PDF)
==============================================
Bosqichma-bosqich topshirish uchun isbot hujjati.
"""

import io
from datetime import datetime, timezone, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)

DARK = colors.HexColor("#1A252F")
GOLD = colors.HexColor("#C9A55A")
GREEN = colors.HexColor("#2E7D52")
RED = colors.HexColor("#C0392B")
GRAY = colors.HexColor("#8E8E93")
LIGHT = colors.HexColor("#F6F4F0")

UZB_TZ = timezone(timedelta(hours=5))


def _fmt(n):
    """1234567 -> 1 234 567"""
    try:
        return f"{int(round(float(n))):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def _num(n, digits=2):
    """Kasr bo'lmasa butun: 12.0 -> 12, 12.5 -> 12.5, 13.1313 -> 13.13"""
    try:
        f = float(n)
        if f == int(f):
            return str(int(f))
        return f"{round(f, digits):g}"
    except (TypeError, ValueError):
        return "0"


def generate_delivery_pdf(delivery, db=None) -> bytes:
    """Bitta yetkazish uchun nakladnoy PDF."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.2*cm, bottomMargin=1.2*cm,
        title=f"Nakladnoy {delivery.delivery_number}"
    )

    order = delivery.order
    project = order.project if order else None

    st_title = ParagraphStyle('t', fontName='Helvetica-Bold', fontSize=16,
                              textColor=colors.white, alignment=TA_CENTER, leading=20)
    st_sub = ParagraphStyle('s', fontName='Helvetica', fontSize=9,
                            textColor=GOLD, alignment=TA_CENTER, leading=12)
    st_norm = ParagraphStyle('n', fontName='Helvetica', fontSize=9,
                             textColor=DARK, leading=13)
    st_small = ParagraphStyle('sm', fontName='Helvetica', fontSize=8,
                              textColor=GRAY, leading=11)
    st_right = ParagraphStyle('r', fontName='Helvetica-Bold', fontSize=9,
                              textColor=DARK, alignment=TA_RIGHT)

    el = []

    # ---- Sarlavha ----
    header = Table([[
        Paragraph("PENODECORPRO", st_title),
    ], [
        Paragraph("Fasad bezaklari  ·  Andijon  ·  +998 97 999 57 57", st_sub),
    ]], colWidths=[18*cm])
    header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), DARK),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
    ]))
    el.append(header)
    el.append(Spacer(1, 6))

    # ---- Hujjat nomi ----
    title2 = Table([[
        Paragraph(
            f"<font size=13><b>YUK XATI (NAKLADNOY)</b></font>  "
            f"<font size=11 color='#8E8E93'>№ {delivery.delivery_number}</font>",
            ParagraphStyle('x', fontName='Helvetica', fontSize=12,
                           textColor=DARK, alignment=TA_CENTER)
        )
    ]], colWidths=[18*cm])
    title2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LINEBELOW', (0, 0), (-1, -1), 2, GOLD),
    ]))
    el.append(title2)
    el.append(Spacer(1, 10))

    # ---- Ma'lumotlar ----
    dt = delivery.delivered_at or datetime.now(UZB_TZ)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc).astimezone(UZB_TZ)
    date_str = dt.strftime("%d.%m.%Y  %H:%M")

    info_rows = [
        ["Buyurtma:", order.order_number if order else "—",
         "Sana:", date_str],
        ["Mijoz:", (project.client_name if project else "—"),
         "Telefon:", (project.client_phone if project and project.client_phone else "—")],
        ["Loyiha:", (project.project_name if project else "—"),
         "Topshirdi:", delivery.delivered_by or "—"],
    ]
    if delivery.received_by:
        info_rows.append(["Manzil:", (project.client_address if project and project.client_address else "—"),
                          "Qabul qildi:", delivery.received_by])

    info = Table(info_rows, colWidths=[2.3*cm, 6.7*cm, 2.5*cm, 6.5*cm])
    info.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
        ('FONTNAME', (3, 0), (3, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), GRAY),
        ('TEXTCOLOR', (2, 0), (2, -1), GRAY),
        ('TEXTCOLOR', (1, 0), (1, -1), DARK),
        ('TEXTCOLOR', (3, 0), (3, -1), DARK),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    el.append(info)
    el.append(Spacer(1, 12))

    # ---- Yetkazilgan mahsulotlar ----
    el.append(Paragraph("<b>Topshirilgan mahsulotlar</b>", st_norm))
    el.append(Spacer(1, 5))

    data = [["№", "Mahsulot nomi", "O'lcham", "Miqdor", "Birlik narxi", "Summa", "Jami bo'yicha", "Qoldi"]]

    delivery_total = 0.0

    for i, di in enumerate(delivery.items, 1):
        oi = di.order_item
        if not oi:
            continue

        # O'lcham matni
        cat = (oi.category or '').lower()
        if cat in ('profil', 'panel'):
            olcham = f"{_num(oi.width)}×{_num(oi.thickness)} sm"
        else:
            olcham = "—"

        ordered = oi.order_qty_normalized
        delivered_total = oi.delivered_qty
        remaining = max(ordered - delivered_total, 0)
        qty = float(di.quantity or 0)

        # Birlik narxi: buyurtma summasini miqdorga bo'lamiz
        total_price = float(oi.total_price or 0)
        unit_p = (total_price / ordered) if ordered > 0 else 0.0
        line_sum = unit_p * qty
        delivery_total += line_sum

        data.append([
            str(i),
            oi.name or "—",
            olcham,
            f"{_num(qty)} {di.unit}",
            _fmt(unit_p),
            _fmt(line_sum),
            f"{_num(delivered_total)} / {_num(ordered)}",
            f"{_num(remaining)}" if remaining > 0.001 else "tugadi",
        ])

    # Shu yuk uchun jami
    data.append(["", "", "", "", "SHU YUK JAMI:", _fmt(delivery_total), "", ""])

    tbl = Table(
        data,
        colWidths=[0.8*cm, 4.5*cm, 2.2*cm, 2.1*cm, 2.3*cm, 2.5*cm, 2.1*cm, 1.5*cm],
        repeatRows=1
    )
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7.5),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 8),
        ('TEXTCOLOR', (0, 1), (-1, -2), DARK),
        ('FONTNAME', (3, 1), (3, -2), 'Helvetica-Bold'),
        ('TEXTCOLOR', (3, 1), (3, -2), GREEN),
        ('FONTNAME', (5, 1), (5, -2), 'Helvetica-Bold'),
        ('TEXTCOLOR', (5, 1), (5, -2), DARK),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (4, 1), (5, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -2), 0.4, colors.HexColor("#E5E1D8")),
        ('TOPPADDING', (0, 0), (-1, -1), 4.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor("#FAFAF8")]),
        # Oxirgi qator — jami
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#F0EBE0")),
        ('FONTNAME', (4, -1), (5, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (4, -1), (5, -1), 9),
        ('TEXTCOLOR', (5, -1), (5, -1), GOLD),
        ('LINEABOVE', (0, -1), (-1, -1), 1.2, DARK),
        ('SPAN', (0, -1), (3, -1)),
        ('ALIGN', (4, -1), (4, -1), 'RIGHT'),
    ]
    tbl.setStyle(TableStyle(style))
    el.append(tbl)
    el.append(Spacer(1, 9))

    # ---- Umumiy moliyaviy holat ----
    if order:
        total_amount = float(order.total_amount or 0)
        agreed = float(order.agreed_amount or total_amount)
        disc_pct = float(order.discount_percent or 0)
        paid = order.paid_amount
        debt = order.debt_amount

        fin_rows = [["Buyurtma jami:", _fmt(total_amount) + " so'm"]]
        if disc_pct > 0:
            fin_rows.append([f"Chegirma ({disc_pct:g}%):", "-" + _fmt(total_amount - agreed) + " so'm"])
            fin_rows.append(["Kelishilgan summa:", _fmt(agreed) + " so'm"])
        fin_rows.append(["To'langan:", _fmt(paid) + " so'm"])
        fin_rows.append(["QARZ QOLDI:", _fmt(debt) + " so'm"])

        fin = Table(fin_rows, colWidths=[4.2*cm, 4*cm], hAlign='RIGHT')
        fin_style = [
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5),
            ('TEXTCOLOR', (0, 0), (0, -1), GRAY),
            ('TEXTCOLOR', (1, 0), (1, -1), DARK),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LINEBELOW', (0, 0), (-1, -2), 0.3, colors.HexColor("#EEEEEE")),
            # Qarz qatori
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 9.5),
            ('TEXTCOLOR', (0, -1), (0, -1), DARK),
            ('TEXTCOLOR', (1, -1), (1, -1), RED if debt > 0 else GREEN),
            ('LINEABOVE', (0, -1), (-1, -1), 1, DARK),
            ('TOPPADDING', (0, -1), (-1, -1), 5),
        ]
        if disc_pct > 0:
            fin_style.append(('TEXTCOLOR', (1, 1), (1, 1), colors.HexColor("#E67E22")))
        fin.setStyle(TableStyle(fin_style))
        el.append(fin)
        el.append(Spacer(1, 9))

    # ---- Umumiy holat ----
    pct = order.delivery_percent if order else 0
    done = order.is_fully_delivered if order else False

    status_color = GREEN if done else GOLD
    status_txt = "BUYURTMA TO'LIQ TOPSHIRILDI" if done else f"Buyurtma bajarilishi: {pct}%"

    stat = Table([[Paragraph(
        f"<b>{status_txt}</b>",
        ParagraphStyle('st', fontName='Helvetica-Bold', fontSize=10,
                       alignment=TA_CENTER, textColor=status_color)
    )]], colWidths=[18*cm])
    stat.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F0F9F4") if done else colors.HexColor("#FEF9E7")),
        ('BOX', (0, 0), (-1, -1), 1, status_color),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    el.append(stat)

    # ---- Izoh ----
    if delivery.notes:
        el.append(Spacer(1, 8))
        note = Table([[Paragraph(f"<b>Izoh:</b> {delivery.notes}", st_small)]], colWidths=[18*cm])
        note.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ]))
        el.append(note)

    # ---- Imzo ----
    el.append(Spacer(1, 22))
    sign = Table([
        ["Topshirdi:", "_" * 28, "", "Qabul qildi:", "_" * 28],
        ["", Paragraph("imzo / F.I.Sh.", st_small), "", "", Paragraph("imzo / F.I.Sh.", st_small)],
    ], colWidths=[2.2*cm, 6*cm, 1.6*cm, 2.4*cm, 5.8*cm])
    sign.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, 0), GRAY),
        ('TEXTCOLOR', (3, 0), (3, 0), GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('ALIGN', (1, 1), (1, 1), 'CENTER'),
        ('ALIGN', (4, 1), (4, 1), 'CENTER'),
    ]))
    el.append(sign)

    # ---- Footer ----
    el.append(Spacer(1, 16))
    footer = Table([[Paragraph(
        f"PenoDecorPro ERP  ·  {datetime.now(UZB_TZ).strftime('%d.%m.%Y %H:%M')}  ·  "
        f"Ushbu hujjat mahsulot topshirilganini tasdiqlaydi",
        ParagraphStyle('f', fontName='Helvetica', fontSize=7,
                       textColor=GRAY, alignment=TA_CENTER)
    )]], colWidths=[18*cm])
    footer.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E1D8")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
    ]))
    el.append(footer)

    doc.build(el)
    pdf = buf.getvalue()
    buf.close()
    return pdf
