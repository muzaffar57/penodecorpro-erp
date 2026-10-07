"""
PenoDecorPro ERP — PDF hujjatlar shrifti
=========================================
kech106 (K106-1, O'LCHANGAN — `work/probe106f.py`, HAQIQIY chizish `pdftoppm` bilan): ReportLab standart shrifti
Helvetica (Type1, WinAnsi / cp1252 kodlash) da Kirill harflari (o'zbek: қ ғ ў ҳ ham), "№" va emoji YO'Q — ReportLab
ularni ZapfDingbats "■" (QORA KVADRAT) bilan almashtirardi. Natija: mijozga Telegram'da boradigan yuk xati sarlavhasi
"YUK XATI (NAKLADNOY) ■ ORD-001-1/Y-1", jadval ustuni "■", Kirill yozilgan mijoz / loyiha / mahsulot nomi — butunlay
"■■■■■■ ■■■■■", moliya hisobotida "■ Arenda"; 7 PDF ning hammasida (yuk xati, nakladnoy, hisob-kitob varaqasi, TM
sotuvi yakka / guruh, oylik moliya, foyda ulushi).

YECHIM:
  * Shrift — Liberation Sans 2.1.5 (`fonts/`, SIL Open Font License 1.1 — `fonts/OFL.txt`). Helvetica / Arial bilan
    METRIKASI BIR XIL (har harf kengligi AYNAN) — jadval ustunlari, satr ko'chishi, sahifa joylashuvi O'ZGARMAYDI;
    Lotin + Kirill (o'zbek harflari bilan) + "№" + "−" + tipografik qo'shtirnoqlar bor.
  * ReportLab'ga STANDART NOMLAR bilan ro'yxatga olinadi: 'Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique',
    'Helvetica-BoldOblique'. Shu sababli PDF kodidagi ~125 ta `fontName='Helvetica…'`, jadval va paragraf STANDART
    shrifti (ReportLab standarti — 'Helvetica') hamda `<b>` / `<i>` belgilari o'zgarishsiz shu TTF ni oladi.
  * Shriftda YO'Q belgi (masalan ma'lumotdagi emoji) bo'sh kvadrat (.notdef) bo'lib chizilmaydi — TASHLAB yuboriladi
    (`_XavfsizShrift`), kenglikka ham qo'shilmaydi. Kod matnlaridagi emoji olib tashlangan (kech106).

Ishlatish: har PDF moduli boshida `from pdf_shrift import shriftlarni_ulash` va `shriftlarni_ulash()` (takroriy
chaqiruv — hech narsa qilmaydi). Test: `tools/test_pdf_shrift.py`.
"""
import os

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

PAPKA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
SHRIFTLAR = {
    "Helvetica": "LiberationSans-Regular.ttf",
    "Helvetica-Bold": "LiberationSans-Bold.ttf",
    "Helvetica-Oblique": "LiberationSans-Italic.ttf",
    "Helvetica-BoldOblique": "LiberationSans-BoldItalic.ttf",
}
# Shriftda yo'qligi uchun chizilmagan belgilar (diagnostika va test uchun; jarayon davomida to'planadi).
TASHLANGAN = set()
_ULANGAN = False


class _XavfsizShrift(TTFont):
    """TTF shrift: shriftda YO'Q belgi chizilmaydi (bo'sh kvadrat o'rniga) va satr kengligiga qo'shilmaydi."""

    def _tozala(self, matn):
        if not isinstance(matn, str):
            matn = matn.decode("utf-8")
        bor = self.face.charToGlyph
        if all(ord(b) in bor for b in matn):
            return matn
        toza = []
        for b in matn:
            if ord(b) in bor or b == "\u00a0":      # NBSP — ReportLab o'zi bo'shliqqa aylantiradi
                toza.append(b)
            else:
                TASHLANGAN.add(b)
        return "".join(toza)

    def splitString(self, text, doc, encoding="utf-8"):
        return TTFont.splitString(self, self._tozala(text), doc, encoding)

    def stringWidth(self, text, size, encoding="utf8"):
        return TTFont.stringWidth(self, self._tozala(text), size, encoding)


def shriftlarni_ulash():
    """Liberation Sans ni standart Helvetica nomlari bilan ReportLab'ga ro'yxatga oladi (jarayonda bir marta)."""
    global _ULANGAN
    if _ULANGAN:
        return
    for nom, fayl in SHRIFTLAR.items():
        shrift = _XavfsizShrift(nom, os.path.join(PAPKA, fayl))
        pdfmetrics.registerFont(shrift)
        # ReportLab 4.2 (`requirements.txt` — 4.2.2): nom allaqachon band bo'lsa (standart Type1 Helvetica shu jarayonda
        # avval ishlatilgan bo'lsa) `registerFont` TTF ni JIM o'tkazib yuboradi — almashtirish majburiy.
        if pdfmetrics.getFont(nom) is not shrift:
            pdfmetrics._fonts[nom] = shrift
    # `registerFont` har TTF uchun o'zini "oila" qilib yozadi va `<b>` / `<i>` xaritasini buzadi (O'LCHANGAN:
    # 'Helvetica' + `<b>` → yana 'Helvetica' — qalin matn oddiy chiqardi) — oila qayta tiklanadi.
    pdfmetrics.registerFontFamily("Helvetica", normal="Helvetica", bold="Helvetica-Bold", italic="Helvetica-Oblique",
                                  boldItalic="Helvetica-BoldOblique")
    _ULANGAN = True
