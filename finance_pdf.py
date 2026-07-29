"""
PenoDecorPro ERP — Oylik moliyaviy hisobot (PDF)
==================================================
Bir oy davomidagi barcha moliyaviy harakatlarni — daromad, har bir
xarajat turi (nomma-nom), brak (yaroqsiz xomashyo), va yakuniy sof
foydani — bitta, tartibli hujjatga birlashtiradi.
"""

import io
from datetime import datetime, timezone, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether
)

DARK = colors.HexColor("#1A252F")
GOLD = colors.HexColor("#C9A55A")
GREEN = colors.HexColor("#2E7D52")
RED = colors.HexColor("#C0392B")
GRAY = colors.HexColor("#8E8E93")
LIGHT = colors.HexColor("#F6F4F0")

UZB_TZ = timezone(timedelta(hours=5))

MONTH_NAMES = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
               "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]


def _fmt(n):
    """1234567 -> 1 234 567"""
    try:
        return f"{int(round(float(n))):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def generate_finance_report_pdf(report: dict, expense_transactions: list,
                                 brak_by_material: list, year: int, month: int) -> bytes:
    """Bir oylik to'liq moliyaviy hisobot — PDF.

    report — services.get_monthly_report() natijasi.
    expense_transactions — shu oydagi barcha ExpenseTransaction yozuvlari
        (Arenda, Soliq, Tushlik, qo'shimcha xarajatlar — nomma-nom).
    brak_by_material — services (crud).get_brak_material_summary()["by_material"].
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.3*cm, rightMargin=1.3*cm,
        topMargin=1*cm, bottomMargin=1*cm,
        title=f"Moliyaviy hisobot {MONTH_NAMES[month]} {year}"
    )
    W = A4[0] - 2.6*cm

    st_title = ParagraphStyle('t', fontName='Helvetica-Bold', fontSize=16,
                              textColor=colors.white, alignment=TA_CENTER, leading=20)
    st_sub = ParagraphStyle('s', fontName='Helvetica', fontSize=9,
                            textColor=GOLD, alignment=TA_CENTER, leading=12)
    st_section = ParagraphStyle('sec', fontName='Helvetica-Bold', fontSize=11,
                                textColor=DARK, leading=14)
    st_th = ParagraphStyle('th', fontName='Helvetica-Bold', fontSize=8.5, textColor=colors.white)
    st_cell = ParagraphStyle('c', fontName='Helvetica', fontSize=9, textColor=DARK)
    st_cell_r = ParagraphStyle('cr', fontName='Helvetica-Bold', fontSize=9, textColor=DARK, alignment=TA_RIGHT)
    st_small = ParagraphStyle('sm', fontName='Helvetica', fontSize=7.5, textColor=GRAY)

    el = []

    # ── SARLAVHA ──
    header = Table([[
        Paragraph("PENODECORPRO", st_title),
    ], [
        Paragraph("Fasad bezaklari  ·  Andijon  ·  +998 97 999 57 57", st_sub),
    ]], colWidths=[W])
    header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), DARK),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
    ]))
    el.append(header)
    el.append(Spacer(1, 8))

    title2 = Table([[
        Paragraph(
            f"<font size=13><b>OYLIK MOLIYAVIY HISOBOT</b></font>  "
            f"<font size=11 color='#8E8E93'>{MONTH_NAMES[month]} {year}</font>",
            ParagraphStyle('x', fontName='Helvetica', fontSize=12, textColor=DARK, alignment=TA_CENTER)
        )
    ]], colWidths=[W])
    title2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LINEBELOW', (0, 0), (-1, -1), 2, GOLD),
    ]))
    el.append(title2)
    el.append(Spacer(1, 10))

    # ── UMUMIY KO'RSATKICHLAR (4 karta) ──
    daromad = float(report.get("daromad", 0))
    jami_xarajat_full = float(report.get("jami_xarajat", 0)) + float(report.get("ishlab_chiqarish_xarajat", 0))
    sof_foyda = float(report.get("sof_foyda", 0))
    foyda_foiz = report.get("foyda_foiz", 0)

    def _summary_card(label, value, color):
        return [
            Paragraph(label, ParagraphStyle('cl', fontName='Helvetica', fontSize=8, textColor=GRAY, alignment=TA_CENTER)),
            Paragraph(f"{_fmt(value)} so'm", ParagraphStyle('cv', fontName='Helvetica-Bold', fontSize=12.5, textColor=color, alignment=TA_CENTER)),
        ]

    cards = Table([[
        _summary_card("JAMI DAROMAD", daromad, GREEN),
        _summary_card("JAMI XARAJAT", jami_xarajat_full, RED),
        _summary_card("SOF FOYDA", sof_foyda, colors.HexColor("#7C3AED")),
        [Paragraph("RENTABELLIK", ParagraphStyle('cl2', fontName='Helvetica', fontSize=8, textColor=GRAY, alignment=TA_CENTER)),
         Paragraph(f"{foyda_foiz}%", ParagraphStyle('cv2', fontName='Helvetica-Bold', fontSize=12.5, textColor=GOLD, alignment=TA_CENTER))],
    ]], colWidths=[W/4]*4)
    cards.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT),
        ('BOX', (0, 0), (0, -1), 0.5, colors.HexColor("#E5E1D8")),
        ('BOX', (1, 0), (1, -1), 0.5, colors.HexColor("#E5E1D8")),
        ('BOX', (2, 0), (2, -1), 0.5, colors.HexColor("#E5E1D8")),
        ('BOX', (3, 0), (3, -1), 0.5, colors.HexColor("#E5E1D8")),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    el.append(cards)
    el.append(Spacer(1, 14))

    # ── XARAJATLAR — NOMMA-NOM ──
    el.append(Paragraph("Xarajatlar tafsiloti (nomma-nom)", st_section))
    el.append(Spacer(1, 6))

    rows = [[Paragraph("Xarajat nomi", st_th), Paragraph("Summa", st_th)]]
    row_colors = [DARK]

    def _add_row(name, amount, bg=colors.white):
        if amount and float(amount) != 0:
            rows.append([Paragraph(name, st_cell), Paragraph(f"{_fmt(amount)} so'm", st_cell_r)])
            row_colors.append(bg)

    # 1) Ishlab chiqarish xarajati (tan narx)
    _add_row("🏭 Ishlab chiqarish xarajati (xomashyo tan narxi)", report.get("ishlab_chiqarish_xarajat", 0))

    # 2) Usta yillik KPI — har bir usta
    for b in report.get("usta_kpi_breakdown", []):
        _add_row(f"🏆 Usta KPI — {b['master_name']} ({b['kpi_percent']}% × foyda {_fmt(b['monthly_profit'])})", b['kpi_amount'])

    # 3) Hodimlar (moslashuvchan) — har biri
    for b in report.get("hodimlar_moslashuvchan_breakdown", []):
        nm = b['name'] + (f" ({b['position']})" if b.get('position') else "")
        _add_row(f"👷 {nm} — {b['detail']}", b['amount'])

    # 4) Ehson
    _add_row("🤲 Ehson (xayriya)", report.get("ehson_xarajat", 0))

    # 5) Brak — har bir xomashyo turi bo'yicha, so'ng jami
    for m in (brak_by_material or []):
        _add_row(f"🗑️ Brak — {m.get('item_name', '—')}", m.get('value', 0))
    if not brak_by_material and report.get("brak_xarajat", 0):
        _add_row("🗑️ Brak (yaroqsiz xomashyo)", report.get("brak_xarajat", 0))

    # 6) Kunlik xarajat tranzaksiyalari — nomma-nom (Arenda, Soliq va h.k.)
    tx_by_cat = {}
    for tx in (expense_transactions or []):
        cat = getattr(tx, 'category', None) or getattr(tx, 'label', None) or 'Boshqa'
        amt = float(getattr(tx, 'amount', 0) or 0)
        tx_by_cat[cat] = tx_by_cat.get(cat, 0) + amt
    for cat, amt in sorted(tx_by_cat.items(), key=lambda x: -x[1]):
        _add_row(f"📋 {cat}", amt)

    # Jami xarajat qatori
    rows.append([Paragraph("<b>JAMI XARAJAT</b>", ParagraphStyle('tf', fontName='Helvetica-Bold', fontSize=9.5, textColor=DARK)),
                 Paragraph(f"<b>{_fmt(jami_xarajat_full)} so'm</b>", ParagraphStyle('tfr', fontName='Helvetica-Bold', fontSize=9.5, textColor=RED, alignment=TA_RIGHT))])
    row_colors.append(RED)

    tbl = Table(rows, colWidths=[W*0.72, W*0.28], repeatRows=1)
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), DARK),
        ('GRID', (0, 0), (-1, -2), 0.4, colors.HexColor("#E5E1D8")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]
    for i, bg in enumerate(row_colors):
        if i == 0 or i == len(row_colors) - 1:
            continue
        style.append(('BACKGROUND', (0, i), (-1, i), colors.white if i % 2 == 1 else LIGHT))
    style.append(('BACKGROUND', (0, len(row_colors)-1), (-1, len(row_colors)-1), colors.HexColor("#F0EBE0")))
    style.append(('LINEABOVE', (0, len(row_colors)-1), (-1, len(row_colors)-1), 1.2, DARK))
    tbl.setStyle(TableStyle(style))
    el.append(tbl)
    el.append(Spacer(1, 14))

    # ── YAKUNIY SOF FOYDA ──
    final = Table([
        [Paragraph("SOF FOYDA (barcha xarajat va brak ayirilgandan keyin)",
                   ParagraphStyle('fl', fontName='Helvetica-Bold', fontSize=10, textColor=DARK, alignment=TA_CENTER)), ""],
        [Paragraph(f"{_fmt(sof_foyda)} so'm",
                   ParagraphStyle('fv', fontName='Helvetica-Bold', fontSize=20,
                                  textColor=(GREEN if sof_foyda >= 0 else RED), alignment=TA_CENTER)),
         Paragraph(f"{foyda_foiz}% rentabellik",
                   ParagraphStyle('fp', fontName='Helvetica', fontSize=9, textColor=GRAY, alignment=TA_CENTER))],
    ], colWidths=[W*0.6, W*0.4])
    final.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F5F0FA") if sof_foyda >= 0 else colors.HexColor("#FDF2F2")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#7C3AED") if sof_foyda >= 0 else RED),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    el.append(KeepTogether(final))

    # ── FOOTER ──
    el.append(Spacer(1, 12))
    footer = Table([[Paragraph(
        f"PenoDecorPro ERP  ·  Yaratildi: {datetime.now(UZB_TZ).strftime('%d.%m.%Y %H:%M')}  ·  "
        f"Ushbu hisobot {MONTH_NAMES[month]} {year} oyi uchun avtomatik yaratildi",
        ParagraphStyle('f', fontName='Helvetica', fontSize=7, textColor=GRAY, alignment=TA_CENTER)
    )]], colWidths=[W])
    footer.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E1D8")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
    ]))
    el.append(footer)

    doc.build(el)
    pdf = buf.getvalue()
    buf.close()
    return pdf
