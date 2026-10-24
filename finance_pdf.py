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


def _sarlavha_osti(brand):
    """kech155 (zip 211g — egasi QARORI 24.10): sarlavha ostidagi qator(lar) — `company_brand.get_brand` → `subtitle_qatorlar` (bitta
    telefon — avvalgidek bitta qator; 2–3 telefon — keyingi qatorda «Tel: …»), XAVFSIZ (`_x`), qatorlar `<br/>` bilan."""
    _q = brand.get("subtitle_qatorlar")
    if _q is None:
        _q = [brand.get("subtitle") or ""]
    return "<br/>".join(_x(q) for q in _q)


from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether, PageBreak
)
# kech154 (zip 205): oylik hisobotda har sahifa pastida «1 / 2» (jami sahifalar soni hujjat tugagach ma'lum); pastki qator eni
from reportlab.pdfgen import canvas as _canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

DARK = colors.HexColor("#1A252F")
GOLD = colors.HexColor("#C9A55A")
GREEN = colors.HexColor("#2E7D52")
RED = colors.HexColor("#C0392B")
GRAY = colors.HexColor("#8E8E93")
LIGHT = colors.HexColor("#F6F4F0")

MONTH_NAMES = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
               "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]


# kech118 (ROLLAR 2-qism — egasi QARORI): «Tannarx va foyda» ruxsati yo'q foydalanuvchi uchun tannarx / foyda qiymatlari
# None keladi (`ruxsatlar.tannarx_tozala`) — son o'rnida «—» (U+2014).
_YOQ = "\u2014"


def _fmt(n):
    """1234567 -> 1 234 567; None -> «—» (yashirin qiymat)"""
    if n is None:
        return _YOQ
    try:
        return f"{int(round(float(n))):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def _fmt_ishora(n):
    """kech117 (G6-09): manfiy summa — BITTA ko'rinish: "−2 618 028" (U+2212, bo'shliqsiz; ilgari bir hujjatda
    "− 5 731 000" va "-2 618 028" ikki xil). None — «—» (yashirin qiymat)."""
    if n is None:
        return _YOQ
    try:
        v = int(round(float(n)))
    except (TypeError, ValueError):
        return "0"
    return ("\u2212" if v < 0 else "") + f"{abs(v):,}".replace(",", " ")


def _fmt_natija(n):
    """kech118: natija (yo'nalishlar hisoboti) — musbat «+1 234», manfiy «−1 234» (U+2212), 0 — «0». Faqat son. None —
    «—» (yashirin qiymat)."""
    if n is None:
        return _YOQ
    try:
        v = int(round(float(n)))
    except (TypeError, ValueError):
        return "0"
    return ("+" if v > 0 else ("\u2212" if v < 0 else "")) + f"{abs(v):,}".replace(",", " ")


def _som(v, tur="som"):
    """kech118 (ROLLAR 2-qism): summa ko'rinishi yoki «—» (yashirin — None). `tur`: «som» — `_fmt` + « so'm», «ishora» —
    `_fmt_ishora` + « so'm», «natija» — `_fmt_natija` + « so'm», «foiz» — son + «%» (hisobotdagi `foyda_foiz` kabi, AYNAN).
    Natija — FAQAT son / «—» (foydalanuvchi matni emas)."""
    if v is None:
        return _YOQ
    if tur == "foiz":
        return f"{v}%" if isinstance(v, (int, float)) and not isinstance(v, bool) else _YOQ
    return f"{ {'ishora': _fmt_ishora, 'natija': _fmt_natija}.get(tur, _fmt)(v)} so'm"


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
        f"Moliya hisobotidagi sof foyda: <b>{_som(moliya, 'ishora')}</b> = JAMI natija "
        f"(<b>{_som(jami.get('natija', 0), 'natija')}</b>). Umumiy (yo'nalishsiz) oylik va xarajatlar yo'nalishlarga "
        "taqsimlanmaydi — faqat JAMI ustunida.", st_small))
    _jx = (None if jami.get("tannarx", 0) is None else
           float(jami.get("tannarx", 0) or 0) + float(jami.get("oylik", 0) or 0) + float(jami.get("xarajat", 0) or 0))
    _ren = split.get("rentabellik")
    el.append(Paragraph(
        f"Daromad: <b>{_som(jami.get('daromad', 0))}</b> · Xarajatlar (tannarx bilan): <b>{_som(_jx)}</b> · "
        f"Natija: <b>{_som(jami.get('natija', 0), 'natija')}</b> · Rentabellik: <b>{_foiz_uz(_ren, True)}</b>", st_small))
    _old, _oz = split.get("oldingi"), split.get("ozgarish") or {}
    if _old:
        el.append(Paragraph(
            f"Oldingi davr ({_x((_old.get('davr') or {}).get('nom', ''))}): daromad {_som(_old.get('daromad', 0))}"
            f"{_ozgarish_matni(_oz.get('daromad'))}, xarajatlar {_som(_old.get('xarajat', 0))}"
            f"{_ozgarish_matni(_oz.get('xarajat'))}, natija {_som(_old.get('natija', 0), 'natija')}"
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
            # kichik qator — hamma qiymati 0 bo'lsa chiqmaydi; yashirin (None — tannarx ruxsati yo'q) qiymat bo'lsa — «—» bilan chiqadi
            haqiqiy = [v for v, d in zip(vals, ustun_som) if not (faqat_jami and d is not jami)]
            if kichik and not any(v for v in vals if v is not None) and not any(v is None for v in haqiqiy):
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
                'nf', fontName='Helvetica-Bold', fontSize=shr + 1,
                textColor=(DARK if v is None else (GREEN if v >= 0 else RED)), alignment=TA_RIGHT)))
        qatorlar.append(nat_q)
        ren = [Paragraph("Rentabellik", c_kic)]
        for d in ustun_som:
            dr = d.get("daromad", 0)
            f = round(d.get("natija", 0) / dr * 100, 1) if dr and d.get("natija", 0) is not None else None
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
            tq.append([Paragraph(_x(r.get("nom", "")), st_c),
                       Paragraph(f"{_som(r.get('summa', 0), 'ishora')}", st_cr),
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


# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
# kech154 (zip 205) — OYLIK MOLIYAVIY HISOBOT, YANGI KO'RINISH (EGASI so'rovi 22.10 09:42 «oylik hisob PDF ni tartiblash»; 09:5x
# «Ha, qo'shilsin» — oldingi oy bilan solishtirish; tanlovi «B · Ixcham 2 sahifa» — namunalar `work/k205/namuna/`). RAQAMLAR VA
# FORMULALAR O'ZGARMAYDI (`services.get_monthly_report` qanday bo'lsa — shunday; JAMI XARAJAT = daromad − sof foyda, butun so'mda).
#   1-sahifa: 4 ko'rsatkich (oldingi oy bilan), qisqa xulosa (faqat raqamlar), qarzlar, daromad tarkibi, xarajat GURUHLARI (summa,
#             ulush chizig'i, oldingi oy, o'zgarish); 2-sahifa: guruhlangan tafsilot (guruh jamisi bilan), JAMI XARAJAT,
#             «DAROMAD − XARAJAT = SOF FOYDA». Har sahifa pastida hisobot nomi, yaratilgan vaqt va «1 / 2».
#   Ko'rinish xatolari (O'LCHANGAN — egasining Sentabr 2026 PDF i, `work/k205/namuna/yasash.py` eski kod bilan AYNAN qaytardi):
#   * doimiy majburiyat turkumi XOM KOD bilan chiqardi («bosh_offic_arenda_8477») — endi «Biz qarzdormiz» dagi nomi
#     (`RecurringObligation.label`, `crud.majburiyat_nomlari`);
#   * «Hisob farqi (qatorlarda ko'rinmagan) −1 so'm» — brak xomashyo bo'yicha HAR BIRI alohida yaxlitlanib keladi
#     (`crud.get_brak_material_summary`: `round(m["value"])`), 7 qatorning yaxlitlash qoldig'i 1 so'mdan oshardi (pul yo'qolmagan).
#     Endi har guruh qatorlari o'sha guruhning AYNAN summasiga keltiriladi (`_moslash`); «Hisob farqi» faqat haqiqiy nomuvofiqlikda;
#   * rentabellik «-21.6%» → «−21,6%» (hujjatdagi boshqa foizlar kabi);
#   * bir xil izoh har xil harf / bo'shliq bilan («Jilvir» / «JILVIR») — bitta qator (birinchi yozilishi bilan).
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
XARAJAT_GURUHLARI = (
    ("tannarx", "Sotilgan mahsulot tannarxi"),
    ("oylik", "Oyliklar va usta bonusi"),
    ("doimiy", "Doimiy xarajatlar"),
    ("brak", "Brak va yo'qotishlar"),
    ("transport", "Transport va yuk ishlari"),
    ("boshqa", "Boshqa xarajatlar"),
    ("kutilmagan", "Kutilmagan xarajatlar"),
    ("ehson", "Ehson"),
)
_GURUH_NOMI = dict(XARAJAT_GURUHLARI)
TURKUM_NOMLARI = {"arenda": "Arenda", "elektr": "Elektr", "tushlik": "Tushlik", "soliqlar": "Soliqlar",
                  "reklama": "Reklama", "kutilmagan": "Kutilmagan xarajat", "boshqa": "Boshqa",
                  "transport_kirim": "Kirim hujjati — transport",
                  "tushirish_kirim": "Kirim hujjati — tushirish (grushchik)",
                  "yuklash_kirim": "Kirim hujjati — yuklash",
                  "kirim_boshqa": "Kirim hujjati — boshqa xarajat"}
# «Boshqa» va «Kutilmagan xarajat» — UMUMIY turkumlar (2026-08-18 qoidasi): ichida IZOH bo'yicha ajratiladi, aks holda turli xarajatlar
# bitta «Boshqa: 110 000» qatorida yashirinardi. Izohlar yig'indisi turkum jamidan farq qilsa — qoldiq alohida qator.
UMUMIY_TURKUMLAR = ("boshqa", "kutilmagan")
YUK_TURKUMLARI = ("transport_kirim", "tushirish_kirim", "yuklash_kirim")
HISOB_FARQI_NOMI = "Hisob farqi (qatorlarda ko'rinmagan)"
# guruh sarlavhasi nomi qator nomidan FARQ qiladi (tafsilotda sarlavha va qator adashmasin: «Ehson» / «Ehson (xayriya)»)
_FARQ_GURUHI = "Hisob farqi"
_BOSHQA_YOZUVLAR = "— boshqa yozuvlar"


def _koddan_nom(cat):
    """«Biz qarzdormiz» dan O'CHIRILGAN majburiyat turkumi (kodi bor, nomi yo'q — xarajat tarixi qoladi): koddan nom
    (`crud.majburiyat_kodidan_nom`); majburiyat kodi bo'lmasa — None."""
    if cat in TURKUM_NOMLARI:
        return None
    import crud as _crud_kod
    return _crud_kod.majburiyat_kodidan_nom(cat)


def _turkum_guruhi(cat, majburiyat):
    """Qo'shimcha xarajat turkumining guruhi: umumiy turkum — o'z guruhi; doimiy majburiyat («Biz qarzdormiz»; o'chirilgani ham —
    kodidan) — «Doimiy»; kirim hujjatining transport / tushirish / yuklash xarajati — «Transport»; qolgani (Reklama, kirimning boshqa
    xarajati, erkin turkum) — «Boshqa»."""
    if cat in UMUMIY_TURKUMLAR:
        return cat
    if cat in (majburiyat or {}) or _koddan_nom(cat):
        return "doimiy"
    if cat in YUK_TURKUMLARI:
        return "transport"
    return "boshqa"


def _turkum_nomi(cat, majburiyat):
    return (majburiyat or {}).get(cat) or TURKUM_NOMLARI.get(cat) or _koddan_nom(cat) or cat


def _xarajat_qismlari(report):
    """Sof foydadan ayriladigan xarajatlarning AYNAN (yaxlitlanmagan) qismlari — `sof_foyda_tarkibi` (bo'lmasa — hisobotning o'z
    maydonlari). None — yashirin («Tannarx va foyda» ruxsati yo'q)."""
    t = report.get("sof_foyda_tarkibi") or {}

    def _f(v):
        return None if v is None else float(v or 0)
    if t:
        return {k: _f(t.get(k, 0)) for k in ("tannarx_buyurtmalar", "tannarx_tm", "doimiy", "qoshimcha", "transport", "brak",
                                             "tm_yoqotish", "usta_kpi", "ehson", "hodimlar")}
    x = report.get("xarajatlar") or {}
    return {
        "tannarx_buyurtmalar": _f(report.get("ishlab_chiqarish_xarajat", 0)),
        "tannarx_tm": _f(report.get("fp_sales_tannarx", 0)),
        "doimiy": sum(float(x.get(k, 0) or 0) for k in ("arenda", "elektr", "tushlik", "soliqlar")),
        "qoshimcha": sum(float(v or 0) for v in (report.get("qoshimcha_xarajatlar") or {}).values()),
        "transport": float(report.get("transport_xarajat_kirish", 0) or 0) + float(report.get("transport_xarajat_yetkazish", 0) or 0),
        "brak": _f(report.get("brak_xarajat", 0)), "tm_yoqotish": _f(report.get("fp_loss_xarajat", 0)),
        "usta_kpi": _f(report.get("usta_kpi_xarajat", 0)), "ehson": _f(report.get("ehson_xarajat", 0)),
        "hodimlar": _f(report.get("hodimlar_moslashuvchan_xarajat", 0)),
    }


def _yigindi(*qiymatlar):
    return None if any(v is None for v in qiymatlar) else float(sum(qiymatlar))


def xarajat_guruhlari_jami(report, majburiyat=None):
    """{guruh: AYNAN summa | None} — faqat hisobotning o'zidan (oldingi oy uchun ham). Yig'indisi = daromad − sof foyda."""
    q = _xarajat_qismlari(report)
    g = {"tannarx": _yigindi(q["tannarx_buyurtmalar"], q["tannarx_tm"]), "oylik": _yigindi(q["usta_kpi"], q["hodimlar"]),
         "doimiy": q["doimiy"], "brak": _yigindi(q["brak"], q["tm_yoqotish"]), "transport": q["transport"],
         "boshqa": 0.0, "kutilmagan": 0.0, "ehson": q["ehson"]}
    for cat, v in (report.get("qoshimcha_xarajatlar") or {}).items():
        k = _turkum_guruhi(cat, majburiyat)
        g[k] = None if g[k] is None else g[k] + float(v or 0)
    return g


def _moslash(qatorlar, jami, umumiy_nom):
    """Bo'lak qatorlari (manbada har biri ALOHIDA yaxlitlangan bo'lishi mumkin — brak xomashyo bo'yicha, usta KPI, hodim oyligi)
    yig'indisini qismning AYNAN jamisiga keltiradi: farq yaxlitlash qoldig'i (har qatorga ≤ 0,5 so'm) bo'lsa — eng katta qatorga;
    qator yo'q bo'lsa — bitta umumiy qator; farq kattaroq (qatorlar to'liq emas) — alohida «… — boshqa yozuvlar» qatori. Jami
    yashirin (None) — qatorlar «—» bilan."""
    if jami is None:
        return [(n, None) for n, _v in qatorlar]
    qat = [(n, float(v)) for n, v in qatorlar if v is not None and float(v) != 0]
    if not qat:
        return [(umumiy_nom, float(jami))] if abs(float(jami)) >= 0.005 else []
    farq = float(jami) - sum(v for _n, v in qat)
    # chegara — HAMMA berilgan qator bo'yicha (0 ga yaxlitlanib tushib qolganlari ham: 0,5 so'mlik bo'lak 0 bo'ladi)
    if abs(farq) <= 0.5 * sum(1 for _n, v in qatorlar if v is not None) + 1e-6:
        i = max(range(len(qat)), key=lambda j: abs(qat[j][1]))
        qat[i] = (qat[i][0], qat[i][1] + farq)
    else:
        qat.append((f"{umumiy_nom} {_BOSHQA_YOZUVLAR}", farq))
    return qat


def xarajat_tafsiloti(report, expense_transactions, brak_by_material, majburiyat=None):
    """{guruh: [(nom, AYNAN summa | None)]} — qatorlar guruh ichida kamayish tartibida («… — boshqa yozuvlar» — oxirida); har guruh
    qatorlari yig'indisi = o'sha guruhning `xarajat_guruhlari_jami` dagi summasi."""
    q = _xarajat_qismlari(report)
    x = report.get("xarajatlar") or {}
    qx = report.get("qoshimcha_xarajatlar") or {}
    gr = {k: [] for k, _n in XARAJAT_GURUHLARI}

    def qosh(g, nom, v):
        if v is None:
            gr[g].append((nom, None))
        elif float(v) != 0:
            gr[g].append((nom, float(v)))

    # 1) sotilgan mahsulot tannarxi: buyurtmalar (xomashyo tan narxi) va tayyor mahsulot sotuvi (kech117, G6-09)
    qosh("tannarx", "Ishlab chiqarish xarajati (xomashyo tan narxi)", q["tannarx_buyurtmalar"])
    qosh("tannarx", "Tayyor mahsulot sotuvi tannarxi", q["tannarx_tm"])
    # 2) oyliklar va usta bonusi — har usta / hodim (KPI asosi — ustaning shu oydagi buyurtmalari foydasi)
    gr["oylik"] += _moslash([(f"Usta KPI — {b.get('master_name', '')} ({_foiz_uz(b.get('kpi_percent'), True)} × ustaning "
                              f"buyurtmalari foydasi {_fmt(b.get('monthly_profit'))})", b.get("kpi_amount"))
                             for b in (report.get("usta_kpi_breakdown") or [])], q["usta_kpi"], "Usta KPI")
    gr["oylik"] += _moslash([(f"{b.get('name', '')}{(' (' + str(b['position']) + ')') if b.get('position') else ''} — "
                              f"{b.get('detail', '')}", b.get("amount"))
                             for b in (report.get("hodimlar_moslashuvchan_breakdown") or [])], q["hodimlar"], "Hodimlar oyligi")
    # 3) doimiy: asosiy 4 tur; «Biz qarzdormiz» dagi doimiy majburiyat turkumlari — pastda (6), nomi bilan
    for k in ("arenda", "elektr", "tushlik", "soliqlar"):
        qosh("doimiy", TURKUM_NOMLARI[k], x.get(k, 0))
    # 4) brak — xomashyo bo'yicha (yig'indisi brakning AYNAN summasiga keltiriladi); omborda tayyor mahsulot yo'qotishi (kech107)
    gr["brak"] += _moslash([(f"Brak — {m.get('item_name', '—')}", m.get("value")) for m in (brak_by_material or [])],
                           q["brak"], "Brak (yaroqsiz xomashyo)")
    qosh("brak", "Tayyor mahsulot yo'qotishi (omborda)", q["tm_yoqotish"])
    # 5) korxona to'lagan transport (kech106, K106-2)
    qosh("transport", "Transport — xomashyo xaridi (kirish)", report.get("transport_xarajat_kirish", 0))
    qosh("transport", "Transport — yuk yetkazish (korxona hisobidan)", report.get("transport_xarajat_yetkazish", 0))
    # 6) qo'shimcha turkumlar — hisobotning `qoshimcha_xarajatlar` i (JAMI XARAJAT bilan BIR manba; tannarxga qo'shilgan kirim
    #    xarajati — kirmaydi). «Boshqa» / «Kutilmagan» — izoh bo'yicha; bir xil izoh har xil harf / bo'shliq bilan — bitta qator.
    izohlar = {}

    def _yozilish_tartibi(tx):
        # bir xil izohning har xil yozilishidan — BIRINCHI yozilgani (sana, keyin id; sanasiz — berilgan tartibda)
        sana = getattr(tx, "date", None)
        return (0, sana.isoformat(), getattr(tx, "id", 0) or 0) if sana is not None else (1, "", 0)
    for tx in sorted(expense_transactions or [], key=_yozilish_tartibi):
        cat = getattr(tx, "category", None) or "boshqa"
        if cat not in UMUMIY_TURKUMLAR or cat not in qx or getattr(tx, "source", None) == _KIRIM_TANNARX_MANBA:
            continue
        izoh = " ".join(((getattr(tx, "notes", None) or "").strip() or "Izohsiz").split())
        kalit = (cat, izoh.casefold())
        nom, summa = izohlar.get(kalit, (izoh, 0.0))
        izohlar[kalit] = (nom, summa + float(getattr(tx, "amount", 0) or 0))
    for cat, v in qx.items():
        g = _turkum_guruhi(cat, majburiyat)
        if cat not in UMUMIY_TURKUMLAR:
            qosh(g, _turkum_nomi(cat, majburiyat), v)
            continue
        ichki = [(nom, summa) for (c, _k), (nom, summa) in izohlar.items() if c == cat]
        if not ichki:
            qosh(g, _turkum_nomi(cat, majburiyat), v)
            continue
        boshi = len(gr[g])
        for nom, summa in ichki:
            qosh(g, nom, summa)
        qoldiq = float(v or 0) - sum(summa for _n, summa in ichki)
        if abs(qoldiq) >= 0.5:
            qosh(g, f"{_turkum_nomi(cat, majburiyat)} {_BOSHQA_YOZUVLAR}", qoldiq)
        elif qoldiq and len(gr[g]) > boshi:
            # tiyin qoldig'i — eng katta izoh qatoriga (guruh summasi AYNAN qolsin)
            i = max(range(boshi, len(gr[g])), key=lambda j: abs(gr[g][j][1] or 0))
            gr[g][i] = (gr[g][i][0], gr[g][i][1] + qoldiq)
    qosh("ehson", "Ehson (xayriya)", q["ehson"])
    for k in gr:
        if k != "tannarx":
            gr[k].sort(key=lambda r: (r[0].endswith(_BOSHQA_YOZUVLAR), -(r[1] or 0)))
    return gr


def oldingi_oy_xulosasi(report, majburiyat=None):
    """Oldingi oy hisobotidan (`services.get_monthly_report`) solishtirish uchun: daromad, jami xarajat (tannarx bilan), sof foyda,
    rentabellik va guruhlar — butun so'mda (guruhlar yig'indisi = jami xarajat). Yashirin — None. O'sha oyda hech qanday daromad va
    xarajat bo'lmagan bo'lsa (korxonaning birinchi oyi) — None: solishtiriladigan narsa yo'q."""
    if not report:
        return None
    # guruhlar — o'sha oyning O'Z PDF idagi kabi (`hisobot_raqamlari`: faqat ko'rsatiladigan guruhlar orasida butun so'mga), shunda
    # ustun o'sha oy PDF i bilan AYNAN; yashirin hisobot (`sof_foyda` None) — o'sha tozalash bilan
    d = hisobot_raqamlari(report, [], [], majburiyat, report.get("sof_foyda") is None)
    gi = {k: 0 for k, _n in XARAJAT_GURUHLARI}
    gi.update({r["kalit"]: r["summa"] for r in d["guruhlar"]})
    if not d["daromad"] and not d["jami"] and all(not v for v in gi.values()):
        return None
    return {"year": report.get("year"), "month": report.get("month"), "daromad": d["daromad"], "jami_xarajat": d["jami"],
            "sof_foyda": d["sof"], "foyda_foiz": report.get("foyda_foiz"), "guruhlar": gi}


def _ozgarish_foiz(joriy, oldingi):
    if joriy is None or oldingi is None or not oldingi:
        return None
    return (float(joriy) - float(oldingi)) / abs(float(oldingi)) * 100


def hisobot_raqamlari(report, expense_transactions, brak_by_material, majburiyat=None, tannarx_yoq=False):
    """PDF ning hamma raqamlari: daromad, JAMI XARAJAT = daromad − sof foyda (butun so'mda; kech117, G6-09), sof foyda, rentabellik,
    daromad qatorlari va xarajat guruhlari — har guruh summasi, ulushi va qatorlari butun so'mda (qatorlar yig'indisi = guruh,
    guruhlar yig'indisi = JAMI XARAJAT). Guruhlar AYNAN summasi hisobot xarajatidan 1 so'mdan ko'p farq qilsa (bo'lmasligi kerak —
    test tekshiradi) — farq ALOHIDA «Hisob farqi» qatorida ko'rinadi, yashirilmaydi."""
    _t = report.get("sof_foyda_tarkibi") or {}
    sof_foyda = None if tannarx_yoq else float(report.get("sof_foyda", 0))
    foyda_foiz = None if tannarx_yoq else report.get("foyda_foiz", 0)
    _daromad_aniq = (float(_t.get("daromad_buyurtmalar", 0)) + float(_t.get("daromad_tm", 0))) if _t else float(report.get("daromad", 0))
    daromad = _yaxlit_butun(_daromad_aniq)
    sof_butun = None if tannarx_yoq else _yaxlit_butun(sof_foyda)
    jami = None if tannarx_yoq else daromad - sof_butun
    guruh_aniq = xarajat_guruhlari_jami(report, majburiyat)
    tafsil = xarajat_tafsiloti(report, expense_transactions, brak_by_material, majburiyat)
    tartib = [k for k, _n in XARAJAT_GURUHLARI if tafsil[k] or (guruh_aniq[k] or 0) != 0]
    for k in tartib:
        if not tafsil[k]:
            tafsil[k] = [(_GURUH_NOMI[k], guruh_aniq[k])]
    if not tannarx_yoq:
        farq = (_daromad_aniq - sof_foyda) - sum(guruh_aniq[k] for k in tartib)
        if abs(farq) >= 1:
            guruh_aniq["farq"] = farq
            tafsil["farq"] = [(HISOB_FARQI_NOMI, farq)]
            tartib.append("farq")
    if tannarx_yoq:
        gi = {k: (None if guruh_aniq[k] is None else _yaxlit_butun(guruh_aniq[k])) for k in tartib}
    else:
        gi = dict(_qatorlarni_taqsimla([(k, guruh_aniq[k]) for k in tartib], jami))
    guruhlar = []
    for k in tartib:
        qat = tafsil[k]
        if gi[k] is not None and all(v is not None for _n, v in qat):
            qi = _qatorlarni_taqsimla(qat, gi[k])
        else:
            qi = [(n, None if v is None else _yaxlit_butun(v)) for n, v in qat]
        ulush = None if (not jami or gi[k] is None) else gi[k] / jami * 100
        guruhlar.append({"kalit": k, "nom": _GURUH_NOMI.get(k, _FARQ_GURUHI), "summa": gi[k], "ulush": ulush, "qatorlar": qi})
    # kech117 (G6-09): buyurtmalardan (shu oy «Tayyor», qaytarishlar ayirilgan) + tayyor mahsulot sotuvi (buyurtmasiz) = JAMI DAROMAD
    d_qat = [(n, v) for n, v in (
        ("Buyurtmalardan (shu oy «Tayyor», qaytarishlar ayirilgan)",
         float(_t.get("daromad_buyurtmalar", report.get("daromad_buyurtmalardan", 0)) if _t else report.get("daromad_buyurtmalardan", 0))),
        ("Tayyor mahsulot sotuvi (buyurtmasiz)",
         float(_t.get("daromad_tm", 0)) if _t else float(report.get("fp_sales_daromad", 0) or 0)),
    ) if float(v or 0) != 0]
    return {"daromad": daromad, "jami": jami, "sof": sof_butun, "foiz": foyda_foiz,
            "daromad_qatorlari": _qatorlarni_taqsimla(d_qat, daromad), "guruhlar": guruhlar}


def _xulosa_gaplari(d, oy_nomi, old, old_nomi):
    """Qisqa xulosa — FAQAT hisobot raqamlaridan (baho / maslahat emas): [(sarlavha, matn)]."""
    g = []
    if d["sof"] is not None:
        g.append(("Natija", f"{oy_nomi}: {_fmt(abs(d['sof']))} so'm {'foyda' if d['sof'] >= 0 else 'zarar'} "
                            f"(rentabellik {_foiz_uz(d['foiz'], True)})."))
        if d["jami"] and d["jami"] > 0:
            g.append(("Qoplash", f"Daromad xarajatlarning {_foiz_uz(d['daromad'] / d['jami'] * 100, True)} ini qopladi."))
    kat = [r for r in d["guruhlar"] if r["summa"] is not None and r["kalit"] != "farq"]
    # yashirin («—») guruh bo'lsa — «eng katta» / «eng ko'p o'sgan» aytilmaydi (ko'rinmaydigan guruhsiz xulosa noto'g'ri bo'lardi)
    if any(r["summa"] is None for r in d["guruhlar"]) or (old and any(v is None for v in old["guruhlar"].values())):
        kat = []
    if kat:
        e = max(kat, key=lambda r: r["summa"])
        if e["summa"] > 0:
            g.append(("Eng katta xarajat", f"{e['nom']} — {_fmt(e['summa'])} so'm"
                      + (f" ({_foiz_uz(e['ulush'], True)})." if e["ulush"] is not None else ".")))
    if old:
        bo = []
        fd = _ozgarish_foiz(d["daromad"], old["daromad"])
        if fd is not None:
            bo.append(f"daromad {'+' if fd > 0 else ''}{_foiz_uz(fd, True)}")
        fx = _ozgarish_foiz(d["jami"], old["jami_xarajat"])
        if fx is not None:
            bo.append(f"xarajat {'+' if fx > 0 else ''}{_foiz_uz(fx, True)}")
        matn = (", ".join(bo) + ".") if bo else ""
        osish = [(r["nom"], r["summa"] - (old["guruhlar"].get(r["kalit"]) or 0)) for r in kat
                 if old["guruhlar"].get(r["kalit"], 0) is not None]
        osish = [o for o in osish if o[1] > 0]
        if osish:
            o = max(osish, key=lambda z: z[1])
            matn += f" Eng ko'p o'sgan: {o[0]} (+{_fmt(o[1])} so'm)."
        if matn.strip():
            g.append((f"{old_nomi} bilan", matn.strip()))
    return g


def _raqamli_canvas(chap_matn):
    """Har sahifa pastida: chapda hisobot nomi va yaratilgan vaqt, o'ngda «1 / 2» (jami sahifalar soni — hujjat tugagach ma'lum)."""
    class _SahifaRaqamli(_canvas.Canvas):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._sahifalar = []

        def showPage(self):
            self._sahifalar.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            jami = len(self._sahifalar)
            for holat in self._sahifalar:
                self.__dict__.update(holat)
                self.saveState()
                self.setStrokeColor(colors.HexColor("#E5E1D8"))
                self.setLineWidth(0.5)
                self.line(1.3 * cm, 1.0 * cm, A4[0] - 1.3 * cm, 1.0 * cm)
                self.setFont("Helvetica", 7.5)
                self.setFillColor(GRAY)
                self.drawString(1.3 * cm, 0.62 * cm, chap_matn)
                self.drawRightString(A4[0] - 1.3 * cm, 0.62 * cm, f"{self._pageNumber} / {jami}")
                self.restoreState()
                _canvas.Canvas.showPage(self)
            _canvas.Canvas.save(self)
    return _SahifaRaqamli


def _qisqartir(matn, en, shrift, olcham):
    """`matn` `en` (pt) ga sig'masa — oxiri «…» bilan qisqartiriladi."""
    matn = matn or ""
    if stringWidth(matn, shrift, olcham) <= en:
        return matn
    while matn and stringWidth(matn + "…", shrift, olcham) > en:
        matn = matn[:-1]
    return matn.rstrip() + "…"


def _ulush_chizigi(ulush, en, rang=GOLD, fon=colors.HexColor("#EEEAE2"), balandlik=6):
    """Ulush chizig'i — bir qatorli jadval (rangli qism va fon). ReportLab grafikasi (`Drawing`) EMAS: u hujjatga «Times-Roman» Type1
    shriftini qo'shardi (Kirill / «№» yo'q — `pdf_shrift`, `test_pdf_shrift` B6)."""
    u = max(0.0, min(float(ulush or 0), 100.0))
    w1 = en * u / 100
    if 0 < w1 < 1.5:
        w1 = 1.5
    nol = [("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
           ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]
    if w1 <= 0 or en - w1 < 0.5:
        t = Table([[""]], colWidths=[en], rowHeights=[balandlik])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), rang if w1 > 0 else fon)] + nol))
        return t
    t = Table([["", ""]], colWidths=[w1, en - w1], rowHeights=[balandlik])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), rang), ("BACKGROUND", (1, 0), (1, 0), fon)] + nol))
    return t


def _ps(nom, **k):
    k.setdefault("fontName", "Helvetica")
    k.setdefault("textColor", DARK)
    k.setdefault("fontSize", 9)
    k.setdefault("leading", k["fontSize"] + 2.5)
    return ParagraphStyle(nom, **k)


def _ozgarish_rangi(farq, osish_yaxshi):
    """O'zgarish rangi: yaxshi tomonga — yashil, yomon tomonga — qizil, o'zgarmagan — kulrang."""
    if farq is None or abs(farq) < 0.05:
        return GRAY
    return GREEN if (farq > 0) == osish_yaxshi else RED


def _strelka(v):
    return "▲" if v > 0 else ("▼" if v < 0 else "")


def generate_finance_report_pdf(report: dict, expense_transactions: list,
                                 brak_by_material: list, year: int, month: int,
                                 debt_summary: dict = None,
                                 db=None, company_id=None, tannarx_yoq: bool = False,
                                 oldingi: dict = None, majburiyat_nomlari: dict = None) -> bytes:
    """Bir oylik to'liq moliyaviy hisobot — PDF (kech154, zip 205 — ixcham 2 sahifa; yuqoridagi izoh).

    report — services.get_monthly_report() natijasi.
    expense_transactions — shu oydagi barcha ExpenseTransaction yozuvlari («Boshqa» / «Kutilmagan» izoh bo'yicha ajratiladi).
    brak_by_material — crud.get_brak_material_summary()["by_material"].
    debt_summary — services.get_full_debt_summary() natijasi (ixtiyoriy — berilmasa, «Qarzlar» bo'limi chiqmaydi).
    tannarx_yoq — kech118 (ROLLAR 2-qism): «Tannarx va foyda» ruxsati yo'q foydalanuvchi — `report` va `brak_by_material`
        allaqachon tozalangan (tannarx / foyda / brak qiymati None); JAMI XARAJAT (tannarx bilan), SOF FOYDA, rentabellik, tannarx
        va brak qatorlari «—», qolgan xarajatlar — o'z summasi bilan.
    oldingi — kech154: `oldingi_oy_xulosasi(<oldingi oy hisoboti>)` (ixtiyoriy — berilmasa, solishtirish chiqmaydi).
    majburiyat_nomlari — {doimiy majburiyat turkumi: nomi}; berilmasa va `db` bor bo'lsa — `crud.majburiyat_nomlari`.
    """
    _brand = get_brand(db, company_id)
    if majburiyat_nomlari is None:
        majburiyat_nomlari = {}
        if db is not None:
            import crud as _crud_mj
            majburiyat_nomlari = _crud_mj.majburiyat_nomlari(db, company_id)
    oy_nomi = f"{MONTH_NAMES[month]} {year}"
    old = oldingi or None
    old_nomi = f"{MONTH_NAMES[old['month']]} {old['year']}" if old and old.get("month") else None
    if old_nomi is None:
        old = None
    d = hisobot_raqamlari(report, expense_transactions, brak_by_material, majburiyat_nomlari, tannarx_yoq)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.3*cm, rightMargin=1.3*cm,
        topMargin=1*cm, bottomMargin=1.4*cm,
        title=f"Moliyaviy hisobot {MONTH_NAMES[month]} {year}"
    )
    W = A4[0] - 2.6*cm
    CHIZIQ = colors.HexColor("#E5E1D8")
    st_section = _ps('sec', fontName='Helvetica-Bold', fontSize=11, leading=14)
    st_th = _ps('th', fontName='Helvetica-Bold', fontSize=7.5, textColor=colors.white, leading=9.5)
    st_th_r = _ps('thr', fontName='Helvetica-Bold', fontSize=7.5, textColor=colors.white, alignment=TA_RIGHT, leading=9.5)
    el = []

    # ── SARLAVHA ──
    header = Table([[Paragraph(_x(_brand["name"].upper()), _ps('t', fontName='Helvetica-Bold', fontSize=15, textColor=colors.white,
                                                               leading=18)),
                     Paragraph(f"OYLIK MOLIYAVIY HISOBOT<br/><font size=12 color='#FFFFFF'><b>{_x(oy_nomi)}</b></font>",
                               _ps('t2', fontSize=8, textColor=GOLD, alignment=TA_RIGHT, leading=13))],
                    [Paragraph(_sarlavha_osti(_brand), _ps('s', fontSize=8, textColor=GOLD)), ""]],
                   colWidths=[W * 0.62, W * 0.38])
    header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), DARK), ('SPAN', (1, 0), (1, 1)), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 9), ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 12), ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('LINEBELOW', (0, -1), (-1, -1), 2, GOLD),
    ]))
    el.append(header)
    el.append(Spacer(1, 10))

    # ── UMUMIY KO'RSATKICHLAR (4 karta; oldingi oy bilan) ──
    def _karta(nom, qiymat, rang, solishtirish):
        q = [Paragraph(_x(nom), _ps('kl', fontSize=7.5, textColor=GRAY, alignment=TA_CENTER, leading=9)),
             Paragraph(_x(qiymat), _ps('kv', fontName='Helvetica-Bold', fontSize=13, textColor=rang, alignment=TA_CENTER, leading=16))]
        if solishtirish:
            _oldingi_matn, _ozgarish, _rang = solishtirish
            q.append(Paragraph(_x(_oldingi_matn), _ps('ks', fontSize=7.5, textColor=GRAY, alignment=TA_CENTER, leading=9.5)))
            if _ozgarish:
                q.append(Paragraph(_x(_ozgarish), _ps('ko', fontSize=7.5, textColor=_rang, alignment=TA_CENTER, leading=9.5)))
        return q

    def _solishtirish(joriy, eski, osish_yaxshi, foizda=True):
        """(«Avgust 2026: 53 200 000», «▼ 10,8%» | None, rang) — oldingi oy qiymati va o'zgarish (yaxshi tomonga yashil)."""
        if old is None:
            return None
        if eski is None:
            return (f"{old_nomi}: {_YOQ}", None, GRAY)
        eski_m = _fmt_ishora(eski) if foizda else _fmt_natija(eski)
        if joriy is None:
            return (f"{old_nomi}: {eski_m}", None, GRAY)
        if foizda:
            f = _ozgarish_foiz(joriy, eski)
            if f is None:
                return (f"{old_nomi}: {eski_m}", None, GRAY)
            return (f"{old_nomi}: {eski_m}", f"{_strelka(f)} {_foiz_uz(abs(f), True)}".strip(), _ozgarish_rangi(f, osish_yaxshi))
        farq = joriy - eski
        return (f"{old_nomi}: {eski_m}", f"{_strelka(farq)} {_fmt(abs(farq))}".strip(), _ozgarish_rangi(farq, osish_yaxshi))

    sof_foyda_butun = d["sof"]
    foyda_foiz = d["foiz"]
    _sof_rang = DARK if sof_foyda_butun is None else (GREEN if sof_foyda_butun >= 0 else RED)
    _foiz_rang = DARK if foyda_foiz is None else (GREEN if float(foyda_foiz or 0) >= 0 else RED)
    if old is not None and foyda_foiz is not None and old.get("foyda_foiz") is not None:
        _pp = float(foyda_foiz) - float(old["foyda_foiz"])
        _ren_sol = (f"{old_nomi}: {_foiz_uz(old['foyda_foiz'], True)}", f"{_strelka(_pp)} {_foiz_uz(abs(_pp))} punkt".strip(),
                    _ozgarish_rangi(_pp, True))
    else:
        _ren_sol = None if old is None else (f"{old_nomi}: {_foiz_uz(old.get('foyda_foiz'), True)}", None, GRAY)
    cards = Table([[
        _karta("JAMI DAROMAD", _som(d["daromad"], "ishora"), GREEN, _solishtirish(d["daromad"], old and old["daromad"], True)),
        _karta("JAMI XARAJAT", _som(d["jami"], "ishora"), RED, _solishtirish(d["jami"], old and old["jami_xarajat"], False)),
        _karta("SOF FOYDA", _som(sof_foyda_butun, "ishora"), _sof_rang,
               _solishtirish(sof_foyda_butun, old and old["sof_foyda"], True, foizda=False)),
        _karta("RENTABELLIK", _foiz_uz(foyda_foiz, True), _foiz_rang, _ren_sol),
    ]], colWidths=[W / 4] * 4)
    cards.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), LIGHT), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                               ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7)]
                              + [('BOX', (i, 0), (i, 0), 0.5, CHIZIQ) for i in range(4)]))
    el.append(cards)
    el.append(Spacer(1, 10))

    # ── QISQA XULOSA (faqat raqamlar) ──
    gaplar = _xulosa_gaplari(d, oy_nomi, old, old_nomi)
    if gaplar:
        el.append(Paragraph("Qisqa xulosa", st_section))
        el.append(Spacer(1, 3))
        xt = Table([[Paragraph(_x(s), _ps('xs', fontName='Helvetica-Bold', fontSize=8.5, textColor=GRAY)),
                     Paragraph(_x(m), _ps('xm', fontSize=9))] for s, m in gaplar], colWidths=[W * 0.2, W * 0.8])
        xt.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 2.5),
                                ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5), ('LEFTPADDING', (0, 0), (-1, -1), 4),
                                ('LINEBELOW', (0, 0), (-1, -2), 0.3, CHIZIQ)]))
        el.append(xt)
        el.append(Spacer(1, 10))

    # ── QARZLAR VA MAJBURIYATLAR ──
    if debt_summary:
        el.append(Paragraph("Qarzlar va majburiyatlar", st_section))
        el.append(Spacer(1, 4))

        def _debt_cell(label, value, count_label, color):
            return [
                Paragraph(label, _ps('dl', fontName='Helvetica-Bold', fontSize=7, textColor=color, alignment=TA_CENTER, leading=9)),
                Paragraph(f"{_fmt(value)} so'm", _ps('dv', fontName='Helvetica-Bold', fontSize=10, textColor=color, alignment=TA_CENTER,
                                                     leading=12.5)),
                Paragraph(count_label, _ps('dc', fontSize=7, textColor=GRAY, alignment=TA_CENTER, leading=9)),
            ]

        AMBER = colors.HexColor("#B45309")
        debt_tbl = Table([[
            _debt_cell("BIZGA QARZDORLAR", debt_summary["customer_debt"], f"{debt_summary['customer_debt_count']} ta loyiha", GREEN),
            _debt_cell("TA'MINOTCHIGA QARZ", debt_summary["supplier_debt"], f"{debt_summary['supplier_debt_count']} ta ta'minotchi", RED),
            _debt_cell("HODIMLARGA QARZ", debt_summary["employee_debt"], "oxirgi 3 oy", AMBER),
            _debt_cell("ARENDA/SOLIQ/KOMMUNAL", debt_summary["recurring_debt"], f"{debt_summary['recurring_debt_count']} ta muddati o'tgan", RED),
        ]], colWidths=[W/4]*4)
        debt_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#F0FDF4")),
            ('BACKGROUND', (1, 0), (1, -1), colors.HexColor("#FDF2F2")),
            ('BACKGROUND', (2, 0), (2, -1), colors.HexColor("#FFFBEB")),
            ('BACKGROUND', (3, 0), (3, -1), colors.HexColor("#FDF2F2")),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ] + [('BOX', (i, 0), (i, 0), 0.5, CHIZIQ) for i in range(4)]))
        el.append(debt_tbl)
        net = debt_summary["net_position"]
        # kech117 (G6-09): ishora hujjat bo'ylab BIR xil ("+N" / "−N", bo'shliqsiz)
        net_row = Table([[
            Paragraph("Sof holat (bizga qarz − bizdan qarz)", _ps('nl', fontName='Helvetica-Bold', fontSize=9)),
            Paragraph(f"{'+' if _yaxlit_butun(net) > 0 else ''}{_fmt_ishora(net)} so'm",
                      _ps('nv', fontName='Helvetica-Bold', fontSize=10, textColor=GREEN if net >= 0 else RED, alignment=TA_RIGHT)),
        ]], colWidths=[W*0.6, W*0.4])
        net_row.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 5),
                                     ('BOTTOMPADDING', (0, 0), (-1, -1), 2), ('LINEBELOW', (0, 0), (-1, -1), 0.5, CHIZIQ)]))
        el.append(net_row)
        el.append(Spacer(1, 10))

    # ── DAROMAD TARKIBI (kech117, G6-09) ──
    el.append(Paragraph("Daromad tarkibi", st_section))
    el.append(Spacer(1, 3))
    _d_rows = [[Paragraph(_x(n), _ps('dn', fontSize=9)), Paragraph(f"{_fmt_ishora(v)} so'm", _ps('dvr', fontSize=9, alignment=TA_RIGHT))]
               for n, v in d["daromad_qatorlari"]]
    _d_rows.append([Paragraph("JAMI DAROMAD", _ps('tdf', fontName='Helvetica-Bold', fontSize=9)),
                    Paragraph(f"{_fmt_ishora(d['daromad'])} so'm", _ps('tdr', fontName='Helvetica-Bold', fontSize=9.5, textColor=GREEN,
                                                                     alignment=TA_RIGHT))])
    _dt = Table(_d_rows, colWidths=[W*0.72, W*0.28])
    _dt.setStyle(TableStyle([('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                             ('LINEBELOW', (0, 0), (-1, -2), 0.3, CHIZIQ), ('LINEABOVE', (0, -1), (-1, -1), 1, DARK),
                             ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#F0FDF4"))]))
    el.append(_dt)
    el.append(Spacer(1, 10))

    # ── XARAJATLAR TARKIBI (guruhlar: summa, ulush, oldingi oy, o'zgarish) ──
    el.append(Paragraph("Xarajatlar tarkibi", st_section))
    el.append(Spacer(1, 3))
    _bar = W * 0.13
    if old is not None:
        _en = [0, W * 0.17, W * 0.08, _bar + 8, W * 0.14, W * 0.13]
        _sar = [Paragraph("Guruh", st_th), Paragraph(_x(MONTH_NAMES[month]), st_th_r), Paragraph("Ulush", st_th_r), Paragraph("", st_th),
                Paragraph(_x(MONTH_NAMES[old["month"]]), st_th_r), Paragraph("O'zgarish", st_th_r)]
    else:
        _en = [0, W * 0.2, W * 0.1, _bar + 8]
        _sar = [Paragraph("Guruh", st_th), Paragraph("Summa", st_th_r), Paragraph("Ulush", st_th_r), Paragraph("", st_th)]
    _en[0] = W - sum(_en[1:])
    _gq = [_sar]
    _tarkib = list(d["guruhlar"])
    if old is not None:
        # o'tgan oyda bo'lib, shu oyda YO'Q guruh ham (shu oy 0) — aks holda o'tgan oy ustuni o'z JAMI siga teng bo'lmasdi
        _bor = {r["kalit"] for r in _tarkib}
        _tartib = [k for k, _n in XARAJAT_GURUHLARI] + ["farq"]
        for k, v in old["guruhlar"].items():
            if k not in _bor and (v is None or v != 0):
                _tarkib.append({"kalit": k, "nom": _GURUH_NOMI.get(k, _FARQ_GURUHI), "summa": 0, "ulush": 0.0 if d["jami"] else None,
                                "qatorlar": []})
        _tarkib.sort(key=lambda r: _tartib.index(r["kalit"]) if r["kalit"] in _tartib else len(_tartib))
    for r in _tarkib:
        q = [Paragraph(_x(r["nom"]), _ps('gn', fontSize=9)),
             Paragraph(f"{_som(r['summa'], 'ishora')}", _ps('gs', fontName='Helvetica-Bold', fontSize=9, alignment=TA_RIGHT)),
             Paragraph(f"{_foiz_uz(r['ulush'], True)}", _ps('gu', fontSize=8.5, textColor=GRAY, alignment=TA_RIGHT)),
             _ulush_chizigi(r["ulush"], _bar)]
        if old is not None:
            e = old["guruhlar"].get(r["kalit"], 0)
            q.append(Paragraph(_x(_YOQ if e is None else _fmt_ishora(e)), _ps('go', fontSize=8.5, textColor=GRAY, alignment=TA_RIGHT)))
            if r["summa"] is None or e is None:
                q.append(Paragraph(_x(_YOQ), _ps('gz0', fontSize=8.5, textColor=GRAY, alignment=TA_RIGHT)))
            else:
                q.append(Paragraph(f"{_fmt_natija(r['summa'] - e)}", _ps('gz', fontName='Helvetica-Bold', fontSize=8.5, alignment=TA_RIGHT,
                                                                   textColor=_ozgarish_rangi(r["summa"] - e, False))))
        _gq.append(q)
    _jq = [Paragraph("JAMI XARAJAT", _ps('gj', fontName='Helvetica-Bold', fontSize=9.5)),
           Paragraph(f"{_som(d['jami'], 'ishora')}", _ps('gjv', fontName='Helvetica-Bold', fontSize=9.5, textColor=RED, alignment=TA_RIGHT)),
           Paragraph(_x("100%" if d["jami"] else _YOQ), _ps('gju', fontSize=8.5, textColor=GRAY, alignment=TA_RIGHT)), ""]
    if old is not None:
        _jq.append(Paragraph(_x(_YOQ if old["jami_xarajat"] is None else _fmt_ishora(old["jami_xarajat"])),
                             _ps('gjo', fontName='Helvetica-Bold', fontSize=8.5, textColor=GRAY, alignment=TA_RIGHT)))
        if d["jami"] is None or old["jami_xarajat"] is None:
            _jq.append(Paragraph(_x(_YOQ), _ps('gjz0', fontSize=8.5, textColor=GRAY, alignment=TA_RIGHT)))
        else:
            _jq.append(Paragraph(f"{_fmt_natija(d['jami'] - old['jami_xarajat'])}",
                                 _ps('gjz', fontName='Helvetica-Bold', fontSize=8.5, alignment=TA_RIGHT,
                                     textColor=_ozgarish_rangi(d["jami"] - old["jami_xarajat"], False))))
    _gq.append(_jq)
    _gt = Table(_gq, colWidths=_en)
    _gt.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), DARK), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                             ('TOPPADDING', (0, 0), (-1, -1), 3.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
                             ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                             ('LINEBELOW', (0, 1), (-1, -2), 0.3, CHIZIQ), ('LINEABOVE', (0, -1), (-1, -1), 1, DARK),
                             ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#F0EBE0"))]))
    el.append(_gt)
    if old is not None:
        el.append(Spacer(1, 3))
        el.append(Paragraph(f"O'zgarish — {_x(old_nomi)} ga nisbatan (so'm): qizil — xarajat oshgan, yashil — kamaygan.",
                            _ps('gizoh', fontSize=7.5, textColor=GRAY)))

    # ── 2-SAHIFA: XARAJATLAR TAFSILOTI (guruhlangan; guruh jamisi bilan) ──
    # kech106 (K106-2): nom — foydalanuvchi matni (turkum, izoh, usta / hodim ismi, majburiyat nomi) bo'lishi mumkin; ReportLab
    # Paragraph uni belgilash sifatida o'qimasin ("a<b>c" — qalin "c", "&amp;" — "&") — matn AYNAN ko'rinadi (`_x`).
    el.append(PageBreak())
    el.append(Paragraph("Xarajatlar tafsiloti", st_section))
    el.append(Spacer(1, 4))
    rows = [[Paragraph("Xarajat nomi", st_th), Paragraph("Summa", st_th_r)]]
    style = [('BACKGROUND', (0, 0), (-1, 0), DARK)]
    for r in d["guruhlar"]:
        i = len(rows)
        if r["ulush"] is not None:
            _sarlavha = Paragraph(f"<b>{_x(r['nom'])}</b>  <font color='#8E8E93' size=8>· {_foiz_uz(r['ulush'], True)}</font>",
                                  _ps('tg', fontSize=9))
        else:
            _sarlavha = Paragraph(f"<b>{_x(r['nom'])}</b>", _ps('tg0', fontSize=9))
        rows.append([_sarlavha,
                     Paragraph(f"<b>{_som(r['summa'], 'ishora')}</b>", _ps('tgv', fontSize=9, alignment=TA_RIGHT))])
        style += [('BACKGROUND', (0, i), (-1, i), colors.HexColor("#F0EBE0")),
                  ('LINEABOVE', (0, i), (-1, i), 0.6, colors.HexColor("#CFC6B4")),
                  ('TOPPADDING', (0, i), (-1, i), 4), ('BOTTOMPADDING', (0, i), (-1, i), 4)]
        if r["qatorlar"]:
            # guruh sarlavhasi sahifa oxirida yolg'iz qolmasin — birinchi qatori bilan bir sahifada
            style.append(('NOSPLIT', (0, i), (-1, i + 1)))
        for n, v in r["qatorlar"]:
            rows.append([Paragraph(_x(n), _ps('tn', fontSize=8.5, leftIndent=10, leading=10.5)),
                         Paragraph(f"{_som(v, 'ishora')}", _ps('tv', fontSize=8.5, alignment=TA_RIGHT, leading=10.5))])
    rows.append([Paragraph("JAMI XARAJAT", _ps('tf', fontName='Helvetica-Bold', fontSize=9.5)),
                 Paragraph(f"{_som(d['jami'], 'ishora')}", _ps('tfr', fontName='Helvetica-Bold', fontSize=9.5, textColor=RED, alignment=TA_RIGHT))])
    style += [('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 2.2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.2),
              ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
              ('LINEBELOW', (0, 1), (-1, -2), 0.25, CHIZIQ), ('LINEABOVE', (0, -1), (-1, -1), 1.2, DARK),
              ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#F0EBE0")),
              ('TOPPADDING', (0, -1), (-1, -1), 5), ('BOTTOMPADDING', (0, -1), (-1, -1), 5)]
    tbl = Table(rows, colWidths=[W*0.76, W*0.24], repeatRows=1)
    tbl.setStyle(TableStyle(style))
    el.append(tbl)
    el.append(Spacer(1, 10))

    # ── YAKUN: JAMI DAROMAD − JAMI XARAJAT = SOF FOYDA ──
    def _yk(matn):
        return Paragraph(_x(matn), _ps('yk', fontSize=7.5, textColor=GRAY, alignment=TA_CENTER))

    final = Table([
        [_yk("JAMI DAROMAD"), "", _yk("JAMI XARAJAT"), "", _yk("SOF FOYDA"), _yk("RENTABELLIK")],
        [Paragraph(f"{_som(d['daromad'], 'ishora')}", _ps('yd', fontName='Helvetica-Bold', fontSize=11, textColor=GREEN, alignment=TA_CENTER)),
         Paragraph("−", _ps('ym', fontName='Helvetica-Bold', fontSize=12, alignment=TA_CENTER)),
         Paragraph(f"{_som(d['jami'], 'ishora')}", _ps('yx', fontName='Helvetica-Bold', fontSize=11, textColor=RED, alignment=TA_CENTER)),
         Paragraph("=", _ps('yt', fontName='Helvetica-Bold', fontSize=12, alignment=TA_CENTER)),
         Paragraph(f"{_som(sof_foyda_butun, 'ishora')}", _ps('fv', fontName='Helvetica-Bold', fontSize=13, textColor=_sof_rang,
                                                        alignment=TA_CENTER)),
         Paragraph(f"{_foiz_uz(foyda_foiz, True)}", _ps('fp', fontName='Helvetica-Bold', fontSize=11, textColor=_foiz_rang, alignment=TA_CENTER))],
    ], colWidths=[W * 0.24, W * 0.04, W * 0.24, W * 0.04, W * 0.27, W * 0.17])
    final.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT if sof_foyda_butun is None else (
            colors.HexColor("#F0FDF4") if sof_foyda_butun >= 0 else colors.HexColor("#FDF2F2"))),
        ('BOX', (0, 0), (-1, -1), 1, _sof_rang),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    el.append(KeepTogether(final))

    # ── PASTKI QATOR (har sahifada; kech106 — "Yaratildi" Toshkent vaqti) ──
    _qolgan = f" · Oylik moliyaviy hisobot · {oy_nomi} · Yaratildi: {_tashkent_vaqt().strftime('%d.%m.%Y %H:%M')}"
    # uzun korxona nomi (200 belgigacha) — qisqartiriladi: pastki qator sahifa raqamiga («N / jami») chiqib ketmasin
    pastki = _qisqartir(_brand["name"], W - 2 * cm - stringWidth(_qolgan, "Helvetica", 7.5), "Helvetica", 7.5) + _qolgan
    doc.build(el, canvasmaker=_raqamli_canvas(pastki))
    pdf = buf.getvalue()
    buf.close()
    return pdf
