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


def generate_split_profit_pdf(split: dict, year: int, month: int) -> bytes:
    """Gips va Penoplast uchun MUSTAQIL sof foyda hisoboti — PDF.
    split — services.calculate_split_profit_report() natijasi."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.3*cm, rightMargin=1.3*cm,
        topMargin=1*cm, bottomMargin=1*cm,
        title=f"Gips-Penoplast hisobot {MONTH_NAMES[month]} {year}"
    )
    W = A4[0] - 2.6*cm

    st_title = ParagraphStyle('t', fontName='Helvetica-Bold', fontSize=16,
                              textColor=colors.white, alignment=TA_CENTER, leading=20)
    st_sub = ParagraphStyle('s', fontName='Helvetica', fontSize=9,
                            textColor=GOLD, alignment=TA_CENTER, leading=12)
    st_sec = ParagraphStyle('sec', fontName='Helvetica-Bold', fontSize=13,
                            textColor=colors.white, alignment=TA_CENTER, leading=16)
    st_small = ParagraphStyle('sm', fontName='Helvetica', fontSize=9,
                              textColor=GRAY, alignment=TA_CENTER)

    el = []

    header = Table([[Paragraph("PENODECORPRO", st_title)],
                     [Paragraph("Gips va Penoplast — mustaqil sof foyda hisoboti", st_sub)]], colWidths=[W])
    header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), DARK),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
    ]))
    el.append(header)
    el.append(Spacer(1, 4))
    el.append(Paragraph(f"<b>{MONTH_NAMES[month]} {year}</b>", ParagraphStyle('m', fontName='Helvetica-Bold', fontSize=12, alignment=TA_CENTER, textColor=DARK)))
    el.append(Spacer(1, 10))

    du = split.get("daromad_ulushi", {})
    el.append(Paragraph(
        f"Daromad ulushi: 🏭 Penoplast {du.get('penoplast_foiz',0)}% · 🧱 Gips {du.get('gips_foiz',0)}%"
        f" &nbsp;&nbsp;|&nbsp;&nbsp; Umumiy xarajatlar (arenda/svet/soliq/Ehson/brak) shu nisbatda taqsimlangan",
        st_small
    ))
    el.append(Spacer(1, 14))

    def section(title, bg, data):
        rows = [
            ["Daromad", f"{_fmt(data['daromad'])} so'm"],
            ["Xomashyo va belgilangan xarajatlar (Yo'nalish tanlanganlar)", f"-{_fmt(data['xomashyo_xarajati'])} so'm"],
            ["Hodim to'lovi", f"-{_fmt(data['hodim_xarajati'])} so'm"],
            ["Brak/yo'qotish (aniq)", f"-{_fmt(data['brak_xarajati'])} so'm"],
            ["Umumiy xarajat ulushi (arenda/svet/soliq/Ehson) — taxminiy", f"-{_fmt(data['umumiy_xarajat_ulushi'])} so'm"],
            ["Jami xarajat", f"-{_fmt(data['jami_xarajat'])} so'm"],
        ]
        tbl_data = [[Paragraph(r[0], ParagraphStyle('c1', fontName='Helvetica', fontSize=9.5, textColor=DARK)),
                     Paragraph(r[1], ParagraphStyle('c2', fontName='Helvetica', fontSize=9.5, textColor=DARK, alignment=TA_RIGHT))]
                    for r in rows]
        foyda_color = GREEN if data['sof_foyda'] >= 0 else RED
        tbl_data.append([
            Paragraph("SOF FOYDA", ParagraphStyle('f1', fontName='Helvetica-Bold', fontSize=11, textColor=DARK)),
            Paragraph(f"{_fmt(data['sof_foyda'])} so'm", ParagraphStyle('f2', fontName='Helvetica-Bold', fontSize=11, textColor=foyda_color, alignment=TA_RIGHT))
        ])
        tbl_data.append([
            Paragraph("Rentabellik", ParagraphStyle('r1', fontName='Helvetica', fontSize=9, textColor=GRAY)),
            Paragraph(f"{data['foyda_foiz']}%", ParagraphStyle('r2', fontName='Helvetica', fontSize=9, textColor=foyda_color, alignment=TA_RIGHT))
        ])

        tbl = Table(tbl_data, colWidths=[W*0.62, W*0.38])
        tbl.setStyle(TableStyle([
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LINEBELOW', (0, 0), (-1, -3), 0.4, colors.HexColor("#E5E1D8")),
            ('LINEABOVE', (0, -2), (-1, -2), 1.2, DARK),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ]))

        head = Table([[Paragraph(title, st_sec)]], colWidths=[W])
        head.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), bg),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        return KeepTogether([head, tbl, Spacer(1, 16)])

    el.append(section("🏭 PENOPLAST VA BOSHQA", colors.HexColor("#1E40AF"), split["penoplast"]))
    el.append(section("🧱 GIPS", colors.HexColor("#9D174D"), split["gips"]))

    el.append(Spacer(1, 6))
    el.append(Paragraph(
        "⚠️ Eslatma: Yo'nalishi aniq belgilanmagan hodimlar va umumiy xarajatlar (arenda, svet, soliq, Ehson) — "
        "ikkala yo'nalish ham bitta joyda faoliyat yuritgani uchun, daromad nisbatiga qarab taxminiy taqsimlangan. "
        "Xomashyo va Brak/yo'qotish — aniq, materialning o'z turi bo'yicha hisoblangan.",
        ParagraphStyle('note', fontName='Helvetica-Oblique', fontSize=8, textColor=GRAY, leading=11)
    ))

    doc.build(el)
    return buf.getvalue()


def generate_finance_report_pdf(report: dict, expense_transactions: list,
                                 brak_by_material: list, year: int, month: int,
                                 debt_summary: dict = None) -> bytes:
    """Bir oylik to'liq moliyaviy hisobot — PDF.

    report — services.get_monthly_report() natijasi.
    expense_transactions — shu oydagi barcha ExpenseTransaction yozuvlari
        (Arenda, Soliq, Tushlik, qo'shimcha xarajatlar — nomma-nom).
    brak_by_material — services (crud).get_brak_material_summary()["by_material"].
    debt_summary — services.get_full_debt_summary() natijasi (ixtiyoriy —
        berilmasa, "Qarzlar" bo'limi PDF'da chiqmaydi).
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

    # ── QARZLAR VA MAJBURIYATLAR ──
    if debt_summary:
        el.append(Paragraph("Qarzlar va majburiyatlar", st_section))
        el.append(Spacer(1, 6))

        def _debt_cell(label, value, count_label, color):
            return [
                Paragraph(label, ParagraphStyle('dl', fontName='Helvetica-Bold', fontSize=7.5, textColor=color, alignment=TA_CENTER)),
                Paragraph(f"{_fmt(value)} so'm", ParagraphStyle('dv', fontName='Helvetica-Bold', fontSize=10.5, textColor=color, alignment=TA_CENTER)),
                Paragraph(count_label, ParagraphStyle('dc', fontName='Helvetica', fontSize=7, textColor=GRAY, alignment=TA_CENTER)),
            ]

        RED_BG = colors.HexColor("#FDF2F2")
        GREEN_BG = colors.HexColor("#F0FDF4")
        AMBER = colors.HexColor("#D97706")
        AMBER_BG = colors.HexColor("#FFFBEB")

        debt_tbl = Table([[
            _debt_cell("BIZGA QARZDORLAR", debt_summary["customer_debt"], f"{debt_summary['customer_debt_count']} ta loyiha", GREEN),
            _debt_cell("YETKAZUVCHIGA QARZ", debt_summary["supplier_debt"], f"{debt_summary['supplier_debt_count']} ta yetkazuvchi", RED),
            _debt_cell("HODIMLARGA QARZ", debt_summary["employee_debt"], "oxirgi 3 oy", AMBER),
            _debt_cell("ARENDA/SOLIQ/KOMMUNAL", debt_summary["recurring_debt"], f"{debt_summary['recurring_debt_count']} ta muddati o'tgan", RED),
        ]], colWidths=[W/4]*4)
        debt_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), GREEN_BG),
            ('BACKGROUND', (1, 0), (1, -1), RED_BG),
            ('BACKGROUND', (2, 0), (2, -1), AMBER_BG),
            ('BACKGROUND', (3, 0), (3, -1), RED_BG),
            ('BOX', (0, 0), (0, -1), 0.5, colors.HexColor("#BBF7D0")),
            ('BOX', (1, 0), (1, -1), 0.5, colors.HexColor("#FECACA")),
            ('BOX', (2, 0), (2, -1), 0.5, colors.HexColor("#FDE68A")),
            ('BOX', (3, 0), (3, -1), 0.5, colors.HexColor("#FECACA")),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        el.append(debt_tbl)
        el.append(Spacer(1, 6))

        net = debt_summary["net_position"]
        net_color = GREEN if net >= 0 else RED
        net_sign = "+" if net >= 0 else "−"
        net_row = Table([[
            Paragraph("Sof holat (bizga qarz − bizdan qarz)", ParagraphStyle('nl', fontName='Helvetica-Bold', fontSize=9, textColor=DARK)),
            Paragraph(f"{net_sign} {_fmt(abs(net))} so'm", ParagraphStyle('nv', fontName='Helvetica-Bold', fontSize=11, textColor=net_color, alignment=TA_RIGHT)),
        ]], colWidths=[W*0.6, W*0.4])
        net_row.setStyle(TableStyle([
            ('LINEABOVE', (0, 0), (-1, 0), 0.7, colors.HexColor("#E5E1D8")),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        el.append(net_row)
        el.append(Spacer(1, 16))

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

    # 1b) Arenda/Elektr/Tushlik/Soliqlar — eski (asosiy maydonlar) mexanizmi
    # orqali kiritilgan bo'lsa (Xarajat qo'shish oynasidagi "asosiy" turlar)
    x = report.get("xarajatlar", {}) or {}
    _add_row("🏠 Arenda", x.get("arenda", 0))
    _add_row("💡 Elektr", x.get("elektr", 0))
    _add_row("🍽️ Tushlik", x.get("tushlik", 0))
    _add_row("🧾 Soliqlar", x.get("soliqlar", 0))

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
    # MUHIM (2026-08-18): "Boshqa" va "Kutilmagan xarajat" — bular UMUMIY
    # turkumlar, shuning uchun ular ICHIDA, alohida IZOH (masalan "Texnik
    # ko'rik" yoki "Tozalik xizmati") bo'yicha, YANA batafsil ajratiladi —
    # aks holda, turli xil xarajatlar bitta "Boshqa: 110 000" qatorida
    # yashirinib, pul qayerga ketayotgani noaniq bo'lib qolardi. Aniq
    # turkumlar (Arenda, Elektr va h.k.) esa, avvalgidek, oddiy jamlanadi.
    CAT_LABELS = {"arenda": "Arenda", "elektr": "Elektr", "tushlik": "Tushlik",
                  "soliqlar": "Soliqlar", "reklama": "Reklama",
                  "kutilmagan": "Kutilmagan xarajat", "boshqa": "Boshqa"}
    GENERIC_CATS = {"boshqa", "kutilmagan"}

    tx_by_cat = {}       # aniq turkumlar uchun — {cat: jami_summa}
    tx_by_detail = {}    # umumiy turkumlar uchun — {(cat, izoh): jami_summa}
    for tx in (expense_transactions or []):
        cat = getattr(tx, 'category', None) or 'boshqa'
        amt = float(getattr(tx, 'amount', 0) or 0)
        if cat in GENERIC_CATS:
            note = (getattr(tx, 'notes', None) or 'Izohsiz').strip() or 'Izohsiz'
            key = (cat, note)
            tx_by_detail[key] = tx_by_detail.get(key, 0) + amt
        else:
            tx_by_cat[cat] = tx_by_cat.get(cat, 0) + amt

    for cat, amt in sorted(tx_by_cat.items(), key=lambda x: -x[1]):
        _add_row(f"📋 {CAT_LABELS.get(cat, cat)}", amt)
    for (cat, note), amt in sorted(tx_by_detail.items(), key=lambda x: -x[1]):
        _add_row(f"📋 {CAT_LABELS.get(cat, cat)} — {note}", amt)

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
