"""
PenoDecorPro ERP — Oylik moliyaviy hisobot (PDF)
==================================================
Bir oy davomidagi barcha moliyaviy harakatlarni — daromad, har bir
xarajat turi (nomma-nom), brak (yaroqsiz xomashyo), va yakuniy sof
foydani — bitta, tartibli hujjatga birlashtiradi.
"""

from company_brand import get_brand  # 2026-09-20: korxona brendi

import io
# kech106 (9 + 50-band B qismi): "Yaratildi" vaqti — `database.tashkent_vaqt` (yagona manba; ilgari alohida `UZB_TZ`).
from database import tashkent_vaqt as _tashkent_vaqt
# kech106 (K106-2): tannarxga qo'shilgan kirim xarajatlari manbasi — hisobot JAMI XARAJAT ga kirmaydi (kech87, 104-band).
from models import KIRIM_TANNARX_MANBA as _KIRIM_TANNARX_MANBA
from xml.sax.saxutils import escape as _xml_escape
# kech106 (K106-1): PDF shrifti — Liberation Sans (Kirill, "№", "−"; Helvetica metrikasi) standart Helvetica NOMLARI
# bilan (`pdf_shrift.py`). Ilgari Kirill yozilgan nom, "№" va emoji QORA KVADRAT (■) bo'lib chiqardi.
from pdf_shrift import shriftlarni_ulash as _shriftlarni_ulash
_shriftlarni_ulash()
# kech106 (K106-3): foydalanuvchi matni (nom, izoh, telefon, korxona ma'lumoti) Paragraph ga XAVFSIZ — "<" / "&"
# belgilash deb o'qilmaydi (ilgari "Karniz <A>" kabi nom yoki "<b>izoh" bo'lsa PDF 500 edi).

def _x(qiymat):
    return _xml_escape("" if qiymat is None else str(qiymat))


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

MONTH_NAMES = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
               "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]


def _fmt(n):
    """1234567 -> 1 234 567"""
    try:
        return f"{int(round(float(n))):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def _fmt_ishora(n):
    """kech117 (G6-09): manfiy summa — BITTA ko'rinish: "−2 618 028" (U+2212, bo'shliqsiz; ilgari bir hujjatda
    "− 5 731 000" va "-2 618 028" ikki xil)."""
    try:
        v = int(round(float(n)))
    except (TypeError, ValueError):
        return "0"
    return ("\u2212" if v < 0 else "") + f"{abs(v):,}".replace(",", " ")


def _fmt_natija(n):
    """kech118: natija (yo'nalishlar hisoboti) — musbat «+1 234», manfiy «−1 234» (U+2212), 0 — «0». Faqat son."""
    try:
        v = int(round(float(n)))
    except (TypeError, ValueError):
        return "0"
    return ("+" if v > 0 else ("\u2212" if v < 0 else "")) + f"{abs(v):,}".replace(",", " ")


def _foiz_uz(f, belgi=False):
    """kech118 (U-05): foiz — 1 xona, kasr VERGUL, manfiy «−»: 12.5 → «12,5», -247.8 → «−247,8», None → «—» (`belgi` —
    oxiriga «%», «—» ga emas). Faqat son."""
    if f is None:
        return "\u2014"
    try:
        v = round(float(f), 1)
    except (TypeError, ValueError):
        return "\u2014"
    t = f"{abs(v):g}".replace(".", ",")
    return ("\u2212" if v < 0 else "") + t + ("%" if belgi else "")


def _ozgarish_matni(f):
    """kech118: oldingi davrga nisbatan o'zgarish — « (+12,5%)» / « (−3%)»; None — bo'sh. Faqat son."""
    if f is None:
        return ""
    return f" ({'+' if float(f) > 0 else ''}{_foiz_uz(f, True)})"


def _yaxlit_butun(x) -> int:
    """HALF_UP butun so'mga (manfiyda simmetrik) — `services._yaxlit` bilan bir qoida."""
    from decimal import Decimal, ROUND_HALF_UP
    return int((Decimal(repr(float(x or 0)))).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _qatorlarni_taqsimla(qatorlar, jami_butun):
    """kech117 (G6-09): [(nom, summa)] ni butun so'mga — yig'indisi AYNAN `jami_butun` (eng katta qoldiq usuli), shunda
    hujjat qatorlari qo'shilsa jami chiqadi."""
    import math
    if not qatorlar:
        return []
    past = [math.floor(float(v) + 1e-9) for _n, v in qatorlar]
    farq = int(jami_butun) - sum(past)
    tartib = sorted(range(len(qatorlar)), key=lambda i: -(float(qatorlar[i][1]) - past[i]))
    for i in range(abs(farq)):
        j = tartib[i % len(tartib)] if farq > 0 else tartib[-1 - (i % len(tartib))]
        past[j] += 1 if farq > 0 else -1
    return [(qatorlar[i][0], past[i]) for i in range(len(qatorlar))]


def generate_split_profit_pdf(split: dict, year: int, month: int,
                              db=None, company_id=None) -> bytes:
    """YO'NALISHLAR bo'yicha moliyaviy natija — PDF (kech117 A2; kech118 — egasi QARORI 15:23: umumiy xarajat
    TAQSIMLANMAYDI, oyliklar alohida, oxirida NATIJA +/−; davr — bir yoki bir necha oy). `split` —
    `services.calculate_split_profit_report()` natijasi (Moliya sahifasidagi jadval bilan AYNAN). Har yo'nalish ustunida
    Daromad − Tannarx − Oyliklar − Xarajatlar = Natija; JAMI ustunida yo'nalishsiz (umumiy) oylik va xarajatlar ham —
    JAMI natija = Moliya hisobotidagi sof foyda (tepada solishtirma qatori)."""
    _brand = get_brand(db, company_id)
    davr = split.get("davr") or {}
    davr_nomi = davr.get("nom") or f"{MONTH_NAMES[month]} {year}"
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.3*cm, rightMargin=1.3*cm,
        topMargin=1*cm, bottomMargin=1*cm,
        title=f"Yo'nalishlar bo'yicha moliyaviy natija — {davr_nomi}"
    )
    W = A4[0] - 2.6*cm

    st_title = ParagraphStyle('t', fontName='Helvetica-Bold', fontSize=16,
                              textColor=colors.white, alignment=TA_CENTER, leading=20)
    st_sub = ParagraphStyle('s', fontName='Helvetica', fontSize=9,
                            textColor=GOLD, alignment=TA_CENTER, leading=12)
    st_small = ParagraphStyle('sm', fontName='Helvetica', fontSize=8.5,
                              textColor=GRAY, alignment=TA_CENTER, leading=11)
    st_note = ParagraphStyle('note', fontName='Helvetica-Oblique', fontSize=8, textColor=GRAY, leading=11)
    st_warn = ParagraphStyle('warn', fontName='Helvetica-Bold', fontSize=8.5, textColor=RED, leading=11)

    el = []
    header = Table([[Paragraph(_x(_brand["name"].upper()), st_title)],   # kech106 (K106-4): korxona nomi
                    [Paragraph("Yo'nalishlar bo'yicha moliyaviy natija", st_sub)]], colWidths=[W])
    header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), DARK),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
    ]))
    el.append(header)
    el.append(Spacer(1, 4))
    el.append(Paragraph(f"<b>{_x(davr_nomi)}</b>", ParagraphStyle('m', fontName='Helvetica-Bold', fontSize=12,
                                                                 alignment=TA_CENTER, textColor=DARK)))
    el.append(Spacer(1, 8))

    yonalishlar = split.get("yonalishlar", []) or []
    jami = split.get("jami", {}) or {}
    moliya = split.get("moliya_sof_foyda", 0)

    el.append(Paragraph(
        f"Moliya hisobotidagi sof foyda: <b>{_fmt_ishora(moliya)} so'm</b> = JAMI natija "
        f"(<b>{_fmt_natija(jami.get('natija', 0))} so'm</b>). Umumiy (yo'nalishsiz) oylik va xarajatlar yo'nalishlarga "
        "taqsimlanmaydi — faqat JAMI ustunida.", st_small))
    _jx = float(jami.get("tannarx", 0) or 0) + float(jami.get("oylik", 0) or 0) + float(jami.get("xarajat", 0) or 0)
    _ren = split.get("rentabellik")
    el.append(Paragraph(
        f"Daromad: <b>{_fmt(jami.get('daromad', 0))} so'm</b> · Xarajatlar (tannarx bilan): <b>{_fmt(_jx)} so'm</b> · "
        f"Natija: <b>{_fmt_natija(jami.get('natija', 0))} so'm</b> · Rentabellik: <b>{_foiz_uz(_ren, True)}</b>", st_small))
    _old, _oz = split.get("oldingi"), split.get("ozgarish") or {}
    if _old:
        el.append(Paragraph(
            f"Oldingi davr ({_x((_old.get('davr') or {}).get('nom', ''))}): daromad {_fmt(_old.get('daromad', 0))} so'm"
            f"{_ozgarish_matni(_oz.get('daromad'))}, xarajatlar {_fmt(_old.get('xarajat', 0))} so'm"
            f"{_ozgarish_matni(_oz.get('xarajat'))}, natija {_fmt_natija(_old.get('natija', 0))} so'm"
            f"{_ozgarish_matni(_oz.get('natija'))}", st_small))
    for iz in split.get("izohlar", []) or []:
        el.append(Paragraph(_x(iz), st_warn))
    if split.get("belgilanmagan_turlar"):
        el.append(Paragraph(f"Yo'nalishi belgilanmagan MRP mahsulot turlari: {_x(', '.join(split['belgilanmagan_turlar']))}"
                            " — Ishlab chiqarish sahifasida yo'nalish biriktiring", st_warn))
    if split.get("belgilanmagan_manbalar"):
        # kech117 (zip 115 jonli sinovi): «Belgilanmagan» daromadning boshqa manbalari (nomi va summasi)
        _bm = "; ".join(f"{b.get('nom', '')} — {_fmt_ishora(b.get('summa', 0))} so'm" for b in split["belgilanmagan_manbalar"])
        el.append(Paragraph(f"«Belgilanmagan» ustunidagi boshqa daromad (yo'nalishini aniqlab bo'lmadi): {_x(_bm)}", st_warn))
    el.append(Spacer(1, 10))

    qnomlar = split.get("xarajat_qism_nomlari") or {k: v for k, v in (split.get("xarajat_nomlari") or {}).items()
                                                   if k != "hodimlar"}

    def _jadval(ustunlar, jami_bilan):
        n = len(ustunlar) + (1 if jami_bilan else 0)
        shr = 9 if n <= 3 else 8
        c_nom = ParagraphStyle('cn', fontName='Helvetica-Bold', fontSize=shr, textColor=DARK, leading=shr + 2)
        c_kic = ParagraphStyle('ck', fontName='Helvetica', fontSize=shr - 1, textColor=GRAY, leading=shr + 1,
                               leftIndent=8)
        c_son = ParagraphStyle('cs', fontName='Helvetica-Bold', fontSize=shr, textColor=DARK, alignment=TA_RIGHT)
        c_kson = ParagraphStyle('cks', fontName='Helvetica', fontSize=shr - 1, textColor=GRAY, alignment=TA_RIGHT)
        c_bosh = ParagraphStyle('cb', fontName='Helvetica-Bold', fontSize=shr, textColor=colors.white,
                                alignment=TA_RIGHT, leading=shr + 2)
        c_bold = ParagraphStyle('cbo', fontName='Helvetica-Bold', fontSize=shr + 0.5, textColor=DARK)
        ustun_som = [y["som"] for y in ustunlar] + ([jami] if jami_bilan else [])
        sar = [Paragraph("", c_nom)] + [Paragraph(_x(y["nom"] + (" (!)" if y.get("belgilanmagan") else "")), c_bosh)
                                        for y in ustunlar] + ([Paragraph("JAMI", c_bosh)] if jami_bilan else [])
        qatorlar = [sar]
        uslub = [('BACKGROUND', (0, 0), (-1, 0), DARK)]

        def _ayir(v):
            """Ayiriladigan summa: musbat — "−N", manfiy (masalan qaytgan tannarx) — "+N", 0 — "0"."""
            v = int(round(float(v or 0)))
            return ("\u2212" + _fmt(v)) if v > 0 else (("+" + _fmt(-v)) if v < 0 else "0")

        def qator(nom, olish, ayir=False, kichik=False, faqat_jami=False):
            vals = []
            for d in ustun_som:
                if faqat_jami and d is not jami:
                    vals.append(None)
                else:
                    vals.append(olish(d))
            if kichik and not any(v for v in vals if v is not None):
                return
            qatorlar.append([Paragraph(_x(nom), c_kic if kichik else c_nom)]
                            + [Paragraph("\u2014" if v is None else (_ayir(v) if ayir else _fmt_ishora(v)),
                                         c_kson if kichik else c_son) for v in vals])

        qator("1. DAROMAD", lambda d: d.get("daromad", 0))
        qator("2. TANNARX (sotilgan mahsulot)", lambda d: d.get("tannarx", 0), ayir=True)
        qator("3. OYLIKLAR", lambda d: d.get("oylik", 0), ayir=True)
        qator("yo'nalishsiz hodimlar (umumiy)", lambda d: d.get("umumiy_oylik", 0), ayir=True, kichik=True,
              faqat_jami=True)
        qator("4. XARAJATLAR", lambda d: d.get("xarajat", 0), ayir=True)
        for k, nm in qnomlar.items():
            qator(nm, lambda d, k=k: (d.get("xarajat_qismlari") or {}).get(k, 0), ayir=True, kichik=True)
        qator("shundan umumiy (yo'nalishsiz)", lambda d: d.get("umumiy_xarajat", 0), ayir=True, kichik=True,
              faqat_jami=True)
        i_nat = len(qatorlar)
        nat_q = [Paragraph("NATIJA (+ / \u2212)", c_bold)]
        for d in ustun_som:
            v = d.get("natija", 0)
            nat_q.append(Paragraph(_fmt_natija(v), ParagraphStyle(
                'nf', fontName='Helvetica-Bold', fontSize=shr + 1, textColor=(GREEN if v >= 0 else RED),
                alignment=TA_RIGHT)))
        qatorlar.append(nat_q)
        ren = [Paragraph("Rentabellik", c_kic)]
        for d in ustun_som:
            dr = d.get("daromad", 0)
            f = round(d.get("natija", 0) / dr * 100, 1) if dr else None
            ren.append(Paragraph(f"{_foiz_uz(f, True)}", ParagraphStyle(
                'rf', fontName='Helvetica', fontSize=shr - 1, textColor=(GREEN if (f or 0) >= 0 else RED),
                alignment=TA_RIGHT)))
        qatorlar.append(ren)
        nom_kengligi = W * (0.36 if n <= 3 else 0.30)
        tbl = Table(qatorlar, colWidths=[nom_kengligi] + [(W - nom_kengligi) / n] * n, repeatRows=1)
        uslub += [
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('LINEBELOW', (0, 1), (-1, -1), 0.3, colors.HexColor("#E5E1D8")),
            ('LINEABOVE', (0, i_nat), (-1, i_nat), 1.2, DARK),
            ('BACKGROUND', (0, i_nat), (-1, i_nat), LIGHT),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        if jami_bilan:
            uslub.append(('BACKGROUND', (-1, 1), (-1, -1), colors.HexColor("#F0EBE0")))
        tbl.setStyle(TableStyle(uslub))
        return tbl

    # 4 tadan ko'p yo'nalish — bir necha jadval (har birida 4 ustun); JAMI — oxirgisida.
    guruhlar = [yonalishlar[i:i + 4] for i in range(0, len(yonalishlar), 4)] or [[]]
    for gi, guruh in enumerate(guruhlar):
        el.append(KeepTogether([_jadval(guruh, gi == len(guruhlar) - 1), Spacer(1, 12)]))

    tarkib = split.get("tarkib") or []
    if tarkib:
        st_h = ParagraphStyle('th', fontName='Helvetica-Bold', fontSize=9, textColor=DARK, leading=12)
        st_c = ParagraphStyle('tc', fontName='Helvetica', fontSize=8.5, textColor=DARK, leading=11)
        st_cr = ParagraphStyle('tcr', fontName='Helvetica', fontSize=8.5, textColor=DARK, alignment=TA_RIGHT)
        tq = [[Paragraph("Xarajatlar tarkibi (tannarxsiz)", st_h), Paragraph("", st_c), Paragraph("", st_c)]]
        for r in tarkib:
            tq.append([Paragraph(_x(r.get("nom", "")), st_c), Paragraph(f"{_fmt_ishora(r.get('summa', 0))} so'm", st_cr),
                       Paragraph(f"{_foiz_uz(r.get('foiz', 0), True)}", st_cr)])
        tt = Table(tq, colWidths=[W * 0.5, W * 0.3, W * 0.2])
        tt.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E1D8")),
                                ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
        el.append(KeepTogether([tt, Spacer(1, 10)]))

    el.append(Spacer(1, 4))
    el.append(Paragraph(
        "Qoida: daromad va tannarx — sotilgan mahsulot yo'nalishiga aniq (profil, panel, donali, blok, loy sotish — "
        "asosiy yo'nalish; MRP mahsuloti — mahsulot turining yo'nalishi). Oyliklar — yo'nalishi belgilangan hodimlar "
        "o'z ustunida, yo'nalishsizlari faqat JAMI da. Xarajatlar — yo'nalishi belgilangan xarajat, transport, kirim "
        "xarajati, brak va tayyor mahsulot yo'qotishi o'z ustunida; umumiy xarajatlar (arenda, svet, soliq, tushlik, "
        "Ehson, usta bonusi va boshqalar) TAQSIMLANMAYDI — faqat JAMI da. Kassa bo'linmaydi.", st_note))

    doc.build(el)
    return buf.getvalue()


def generate_finance_report_pdf(report: dict, expense_transactions: list,
                                 brak_by_material: list, year: int, month: int,
                                 debt_summary: dict = None,
                                 db=None, company_id=None) -> bytes:
    """Bir oylik to'liq moliyaviy hisobot — PDF.

    report — services.get_monthly_report() natijasi.
    expense_transactions — shu oydagi barcha ExpenseTransaction yozuvlari
        (Arenda, Soliq, Tushlik, qo'shimcha xarajatlar — nomma-nom).
    brak_by_material — services (crud).get_brak_material_summary()["by_material"].
    debt_summary — services.get_full_debt_summary() natijasi (ixtiyoriy —
        berilmasa, "Qarzlar" bo'limi PDF'da chiqmaydi).
    """
    _brand = get_brand(db, company_id)
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
        Paragraph(_x(_brand["name"].upper()), st_title),   # kech106 (K106-4): ilgari qattiq "PENODECORPRO"
    ], [
        Paragraph(_x(_brand["subtitle"]), st_sub),
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
    # kech117 (G6-09, O'LCHANGAN audit kech114: 1 674 000 − 4 288 944 = −2 614 944, SOF FOYDA esa −2 618 028 — tayyor
    # mahsulot sotuvi tannarxi (3 084) hech qaysi qatorda yo'q edi). Endi: JAMI XARAJAT = sotilgan mahsulot tannarxi
    # (buyurtmalar + tayyor mahsulot sotuvi) + sof foydadan ayriladigan xarajatlar — butun so'mda JAMI DAROMAD − JAMI
    # XARAJAT = SOF FOYDA AYNAN; qatorlar (daromad tarkibi va xarajatlar) qo'shilsa o'z jamisi chiqadi.
    _t = report.get("sof_foyda_tarkibi") or {}
    sof_foyda = float(report.get("sof_foyda", 0))
    foyda_foiz = report.get("foyda_foiz", 0)
    if _t:
        _daromad_aniq = float(_t.get("daromad_buyurtmalar", 0)) + float(_t.get("daromad_tm", 0))
    else:
        _daromad_aniq = float(report.get("daromad", 0))
    daromad = _yaxlit_butun(_daromad_aniq)
    sof_foyda_butun = _yaxlit_butun(sof_foyda)
    jami_xarajat_full = daromad - sof_foyda_butun
    _xarajat_aniq = _daromad_aniq - sof_foyda

    def _summary_card(label, value, color):
        return [
            Paragraph(label, ParagraphStyle('cl', fontName='Helvetica', fontSize=8, textColor=GRAY, alignment=TA_CENTER)),
            Paragraph(f"{_fmt_ishora(value)} so'm", ParagraphStyle('cv', fontName='Helvetica-Bold', fontSize=12.5, textColor=color, alignment=TA_CENTER)),
        ]

    # kech117 (G6-09): zarar — qizil, foyda — yashil (ilgari sof foyda binafsha, rentabellik sariq — zararda ham)
    _sof_rang = GREEN if sof_foyda_butun >= 0 else RED
    cards = Table([[
        _summary_card("JAMI DAROMAD", daromad, GREEN),
        _summary_card("JAMI XARAJAT", jami_xarajat_full, RED),
        _summary_card("SOF FOYDA", sof_foyda_butun, _sof_rang),
        [Paragraph("RENTABELLIK", ParagraphStyle('cl2', fontName='Helvetica', fontSize=8, textColor=GRAY, alignment=TA_CENTER)),
         Paragraph(f"{foyda_foiz}%", ParagraphStyle('cv2', fontName='Helvetica-Bold', fontSize=12.5,
                                                    textColor=(GREEN if float(foyda_foiz or 0) >= 0 else RED),
                                                    alignment=TA_CENTER))],
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
        # kech117 (G6-09): ishora hujjat bo'ylab BIR xil ("+N" / "−N", bo'shliqsiz)
        net_row = Table([[
            Paragraph("Sof holat (bizga qarz − bizdan qarz)", ParagraphStyle('nl', fontName='Helvetica-Bold', fontSize=9, textColor=DARK)),
            Paragraph(f"{'+' if _yaxlit_butun(net) > 0 else ''}{_fmt_ishora(net)} so'm", ParagraphStyle('nv', fontName='Helvetica-Bold', fontSize=11, textColor=net_color, alignment=TA_RIGHT)),
        ]], colWidths=[W*0.6, W*0.4])
        net_row.setStyle(TableStyle([
            ('LINEABOVE', (0, 0), (-1, 0), 0.7, colors.HexColor("#E5E1D8")),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        el.append(net_row)
        el.append(Spacer(1, 16))

    # ── DAROMAD TARKIBI (kech117, G6-09) ──
    # Buyurtmalardan (shu oy «Tayyor», qaytarishlar ayirilgan) + tayyor mahsulot sotuvi (buyurtmasiz) = JAMI DAROMAD.
    el.append(Paragraph("Daromad tarkibi", st_section))
    el.append(Spacer(1, 6))
    _d_qatorlar = [(n, v) for n, v in (
        ("Buyurtmalardan (shu oy «Tayyor», qaytarishlar ayirilgan)",
         float(_t.get("daromad_buyurtmalar", report.get("daromad_buyurtmalardan", 0)) if _t else report.get("daromad_buyurtmalardan", 0))),
        ("Tayyor mahsulot sotuvi (buyurtmasiz)",
         float(_t.get("daromad_tm", 0)) if _t else float(report.get("fp_sales_daromad", 0) or 0)),
    ) if float(v or 0) != 0]
    _d_rows = [[Paragraph("Daromad manbai", st_th), Paragraph("Summa", st_th)]]
    for _n, _v in _qatorlarni_taqsimla(_d_qatorlar, daromad):
        _d_rows.append([Paragraph(_x(_n), st_cell), Paragraph(f"{_fmt_ishora(_v)} so'm", st_cell_r)])
    _d_rows.append([Paragraph("<b>JAMI DAROMAD</b>", ParagraphStyle('tdf', fontName='Helvetica-Bold', fontSize=9.5, textColor=DARK)),
                    Paragraph(f"<b>{_fmt_ishora(daromad)} so'm</b>", ParagraphStyle('tdr', fontName='Helvetica-Bold', fontSize=9.5, textColor=GREEN, alignment=TA_RIGHT))])
    _dt = Table(_d_rows, colWidths=[W*0.72, W*0.28])
    _dt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK),
        ('GRID', (0, 0), (-1, -2), 0.4, colors.HexColor("#E5E1D8")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, len(_d_rows) - 1), (-1, len(_d_rows) - 1), colors.HexColor("#F0FDF4")),
        ('LINEABOVE', (0, len(_d_rows) - 1), (-1, len(_d_rows) - 1), 1.2, DARK),
    ]))
    el.append(_dt)
    el.append(Spacer(1, 14))

    # ── XARAJATLAR — NOMMA-NOM ──
    el.append(Paragraph("Xarajatlar tafsiloti (nomma-nom)", st_section))
    el.append(Spacer(1, 6))

    rows = [[Paragraph("Xarajat nomi", st_th), Paragraph("Summa", st_th)]]
    row_colors = [DARK]
    _xarajat_qatorlari = []      # kech117 (G6-09): avval yig'iladi, keyin butun so'mga (yig'indi = JAMI XARAJAT)

    def _add_row(name, amount, bg=colors.white):
        if amount and float(amount) != 0:
            _xarajat_qatorlari.append((name, float(amount), bg))

    # 1) Sotilgan mahsulot tannarxi: buyurtmalar (xomashyo tan narxi) va tayyor mahsulot sotuvi (kech117, G6-09 — ilgari
    #    YO'Q edi: 3 084 so'm farq)
    _add_row("Ishlab chiqarish xarajati (xomashyo tan narxi)", report.get("ishlab_chiqarish_xarajat", 0))
    _add_row("Tayyor mahsulot sotuvi tannarxi", float(_t.get("tannarx_tm", 0)) if _t else report.get("fp_sales_tannarx", 0))

    # 1b) Arenda/Elektr/Tushlik/Soliqlar — eski (asosiy maydonlar) mexanizmi
    # orqali kiritilgan bo'lsa (Xarajat qo'shish oynasidagi "asosiy" turlar)
    x = report.get("xarajatlar", {}) or {}
    _add_row("Arenda", x.get("arenda", 0))
    _add_row("Elektr", x.get("elektr", 0))
    _add_row("Tushlik", x.get("tushlik", 0))
    _add_row("Soliqlar", x.get("soliqlar", 0))

    # 2) Usta yillik KPI — har bir usta
    for b in report.get("usta_kpi_breakdown", []):
        _add_row(f"Usta KPI — {b['master_name']} ({b['kpi_percent']}% × foyda {_fmt(b['monthly_profit'])})", b['kpi_amount'])

    # 3) Hodimlar (moslashuvchan) — har biri
    for b in report.get("hodimlar_moslashuvchan_breakdown", []):
        nm = b['name'] + (f" ({b['position']})" if b.get('position') else "")
        _add_row(f"{nm} — {b['detail']}", b['amount'])

    # 4) Ehson
    _add_row("Ehson (xayriya)", report.get("ehson_xarajat", 0))

    # 5) Brak — har bir xomashyo turi bo'yicha, so'ng jami
    for m in (brak_by_material or []):
        _add_row(f"Brak — {m.get('item_name', '—')}", m.get('value', 0))
    if not brak_by_material and report.get("brak_xarajat", 0):
        _add_row("Brak (yaroqsiz xomashyo)", report.get("brak_xarajat", 0))
    # kech107 (49-band, "Bitta raqam"): omborda tayyor turgan mahsulot yo'qotishi — "Brak" dan ALOHIDA qator (jami
    # xarajat ichida; ilgari "Brak" ichida edi, bu jadvalda qatori YO'Q edi — qatorlar yig'indisi JAMI dan kam chiqardi).
    _add_row("Tayyor mahsulot yo'qotishi (omborda)", report.get("fp_loss_xarajat", 0))

    # 5b) kech106 (K106-2, O'LCHANGAN — `work/probe106m.py`): korxona to'lagan TRANSPORT — hisobotning JAMI XARAJAT i
    # ichida (kech87, 104-band), lekin bu jadvalda YO'Q edi (qatorlar yig'indisi JAMI dan kam chiqardi).
    _add_row("Transport — xomashyo xaridi (kirish)", report.get("transport_xarajat_kirish", 0))
    _add_row("Transport — yuk yetkazish (korxona hisobidan)", report.get("transport_xarajat_yetkazish", 0))

    # 6) Qo'shimcha xarajatlar — hisobotning `qoshimcha_xarajatlar` i (JAMI XARAJAT bilan BIR manba).
    # kech106 (K106-2): ilgari shu oyning HAMMA tranzaksiyasi qayta sanalardi — asosiy 4 turkum (Arenda, Elektr, Tushlik,
    # Soliqlar — yuqorida, 1b) IKKINCHI marta chiqardi, tannarxga qo'shilgan kirim xarajatlari (JAMI ga kirmaydi) ham
    # ro'yxatda edi, kirim turkumlari xom kalit bilan ("transport_kirim"), tranzaksiyalar 200 ta bilan cheklangan edi.
    # MUHIM (2026-08-18): "Boshqa" va "Kutilmagan xarajat" — bular UMUMIY
    # turkumlar, shuning uchun ular ICHIDA, alohida IZOH (masalan "Texnik
    # ko'rik" yoki "Tozalik xizmati") bo'yicha, YANA batafsil ajratiladi —
    # aks holda, turli xil xarajatlar bitta "Boshqa: 110 000" qatorida
    # yashirinib, pul qayerga ketayotgani noaniq bo'lib qolardi. Izohlar yig'indisi
    # turkum jamidan farq qilsa (masalan tranzaksiyalar to'liq berilmagan bo'lsa) — qoldiq alohida qator.
    CAT_LABELS = {"arenda": "Arenda", "elektr": "Elektr", "tushlik": "Tushlik",
                  "soliqlar": "Soliqlar", "reklama": "Reklama",
                  "kutilmagan": "Kutilmagan xarajat", "boshqa": "Boshqa",
                  "transport_kirim": "Kirim hujjati — transport",
                  "tushirish_kirim": "Kirim hujjati — tushirish (grushchik)",
                  "yuklash_kirim": "Kirim hujjati — yuklash",
                  "kirim_boshqa": "Kirim hujjati — boshqa xarajat"}
    GENERIC_CATS = {"boshqa", "kutilmagan"}
    qoshimcha = report.get("qoshimcha_xarajatlar", {}) or {}

    tx_by_detail = {}    # umumiy turkumlar uchun — {(cat, izoh): jami_summa}
    for tx in (expense_transactions or []):
        cat = getattr(tx, 'category', None) or 'boshqa'
        if cat not in GENERIC_CATS or cat not in qoshimcha or getattr(tx, 'source', None) == _KIRIM_TANNARX_MANBA:
            continue
        amt = float(getattr(tx, 'amount', 0) or 0)
        note = (getattr(tx, 'notes', None) or 'Izohsiz').strip() or 'Izohsiz'
        key = (cat, note)
        tx_by_detail[key] = tx_by_detail.get(key, 0) + amt

    for cat, amt in sorted(((c, float(a or 0)) for c, a in qoshimcha.items() if c not in GENERIC_CATS),
                           key=lambda x: -x[1]):
        _add_row(f"{CAT_LABELS.get(cat, cat)}", amt)
    for (cat, note), amt in sorted(tx_by_detail.items(), key=lambda x: -x[1]):
        _add_row(f"{CAT_LABELS.get(cat, cat)} — {note}", amt)
    for cat in sorted(c for c in qoshimcha if c in GENERIC_CATS):
        qoldiq = float(qoshimcha[cat] or 0) - sum(a for (c, _), a in tx_by_detail.items() if c == cat)
        if abs(qoldiq) >= 0.5:
            _add_row(f"{CAT_LABELS.get(cat, cat)} — boshqa yozuvlar", qoldiq)

    # kech117 (G6-09): qatorlar butun so'mga — yig'indisi AYNAN JAMI XARAJAT. Yig'ilgan qatorlar hisobot xarajatidan 1
    # so'mdan ko'p farq qilsa (bo'lmasligi kerak — test tekshiradi) — farq ALOHIDA qatorda ko'rinadi, yashirilmaydi.
    _farq = _xarajat_aniq - sum(v for _n, v, _b in _xarajat_qatorlari)
    if abs(_farq) >= 1:
        _xarajat_qatorlari.append(("Hisob farqi (qatorlarda ko'rinmagan)", _farq, colors.white))
    for (_n, _v), (_n2, _v2, _bg) in zip(_qatorlarni_taqsimla([(n, v) for n, v, _b in _xarajat_qatorlari],
                                                              jami_xarajat_full), _xarajat_qatorlari):
        # kech106 (K106-2): nom — foydalanuvchi matni (turkum, izoh, usta / hodim ismi) bo'lishi mumkin; ReportLab
        # Paragraph uni belgilash sifatida o'qimasin ("a<b>c" — qalin "c", "&amp;" — "&") — matn AYNAN ko'rinadi.
        rows.append([Paragraph(_x(_n), st_cell), Paragraph(f"{_fmt_ishora(_v)} so'm", st_cell_r)])
        row_colors.append(_bg)

    # Jami xarajat qatori
    rows.append([Paragraph("<b>JAMI XARAJAT</b>", ParagraphStyle('tf', fontName='Helvetica-Bold', fontSize=9.5, textColor=DARK)),
                 Paragraph(f"<b>{_fmt_ishora(jami_xarajat_full)} so'm</b>", ParagraphStyle('tfr', fontName='Helvetica-Bold', fontSize=9.5, textColor=RED, alignment=TA_RIGHT))])
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
        [Paragraph(f"{_fmt_ishora(sof_foyda_butun)} so'm",
                   ParagraphStyle('fv', fontName='Helvetica-Bold', fontSize=20,
                                  textColor=(GREEN if sof_foyda_butun >= 0 else RED), alignment=TA_CENTER)),
         Paragraph(f"{foyda_foiz}% rentabellik",
                   ParagraphStyle('fp', fontName='Helvetica', fontSize=9,
                                  textColor=(GREEN if float(foyda_foiz or 0) >= 0 else RED), alignment=TA_CENTER))],
    ], colWidths=[W*0.6, W*0.4])
    final.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F0FDF4") if sof_foyda_butun >= 0 else colors.HexColor("#FDF2F2")),
        ('BOX', (0, 0), (-1, -1), 1, GREEN if sof_foyda_butun >= 0 else RED),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    el.append(KeepTogether(final))

    # ── FOOTER ──
    el.append(Spacer(1, 12))
    footer = Table([[Paragraph(
        f"{_x(_brand['name'])}  ·  Yaratildi: {_tashkent_vaqt().strftime('%d.%m.%Y %H:%M')}  ·  "
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
