#!/usr/bin/env python3
"""
test_css_tartib.py — kech136 (zip 162): HAMMA shablonlarda yozilgan, lekin HECH QACHON ishlamaydigan uslub qoidalari yo'q (statik).

NIMA UCHUN KERAK (O'LCHANGAN — work/k162/olchov162.py, work/k162/inline_skan.py, zip 161 kodi, haqiqiy Chromium)
  * Dashboard: telefon blokidagi `#topGridDots{display:flex}` dan KEYIN `#topGridDots{display:none}` — karusel nuqtalari hech qachon
    ko'rinmasdi (320 … 768 px da `display: none`).
  * Dashboard: `#topGrid` ning o'z `style="…gap:14px…grid-template-columns:1fr 1fr"` atributi ustun — telefon blokidagi `gap:12px`
    va alohida `<style>` dagi `@media(max-width:900px){ #topGrid{grid-template-columns:1fr} }` hech qachon ishlamagan (769–900 px da
    ikki ustun, kartalar orasi 14px) — JS esa 12px deb hisoblardi.
  * Buyurtmalar: telefon blokidagi `.ord-list{max-height:280px}` va `.right-panel{flex-direction:column-reverse}` — keyingi asosiy
    qoidalar doim bekor qilardi (ro'yxat balandligi — keyingi telefon blokida; panellar tartibi — `order`).
  Avvalgi skaner (work/k157/css_tartib_skan.py) har `<style>` blokini ALOHIDA ko'rardi va inline `style` ni hisobga olmasdi.

QOIDA (kech133 / kech136): telefon (@media) qoidasi shu selektorning asosiy qoidasidan KEYIN yoziladi; elementning o'z `style`
  atributidagi xususiyatni `<style>` dan o'zgartirish kerak bo'lsa — `!important` yoki xususiyat inline dan olinadi.

BO'LIMLAR
  T1  skanerning o'zi — soxta kirishlar (topadi / topmaydi: tartib, !important, izoh, Jinja izohi, bir nechta <style> bloki, vergulli
      selektor, inline style, inline !important, boshqa xususiyat);
  T2  HAMMA shablonlar: @media qoidasini KEYINGI media'siz qoida bekor qilmaydi (sahifaning hamma <style> bloklari BIRGA);
  T3  HAMMA shablonlar: `#id` qoidasi o'sha elementning o'z `style` atributi bilan bekor bo'lmaydi;
  T4  Dashboard / Buyurtmalar — aniq joylar (nuqtalar asosiy qoidasi media blokidan OLDIN, telefonda `display:flex`; eskirgan
      qoidalar yo'q).
REJIMLAR: statik (baza kerak emas). Asl kodga (zip 161) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_css_tartib.py
"""
import os
import re
import sys
import glob

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:1500]}")


def section(t):
    print(f"\n--- {t} ---")


# ══════════════════════════════════════════════════════════════
# Skaner
# ══════════════════════════════════════════════════════════════
def css_qoidalar(css):
    """[(selektor, {xususiyat: (qiymat, important)}, (media, …))] — hujjat tartibida; vergulli selektor bo'linadi; CSS izohlari
    (ichida `{` bo'lsa ham) oldin olib tashlanadi."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    res = []

    def tahlil(s, med):
        j = 0
        while j < len(s):
            k = s.find("{", j)
            if k < 0:
                break
            sel = re.sub(r"/\*.*?\*/", "", s[j:k], flags=re.S).strip()
            d, e = 1, k + 1
            while e < len(s) and d:
                if s[e] == "{":
                    d += 1
                elif s[e] == "}":
                    d -= 1
                e += 1
            ich = s[k + 1:e - 1]
            if sel.startswith("@media"):
                tahlil(ich, med + [re.sub(r"\s+", " ", sel)])
            elif sel and not sel.startswith("@"):
                dek = {}
                for p in re.sub(r"/\*.*?\*/", "", ich, flags=re.S).split(";"):
                    if ":" in p:
                        a, b = p.split(":", 1)
                        dek[a.strip().lower()] = (re.sub(r"\s+", " ", b.replace("!important", "")).strip(), "!important" in b)
                for s1 in sel.split(","):
                    res.append((re.sub(r"\s+", " ", s1.strip()), dek, tuple(med)))
            j = e
    tahlil(css, [])
    return res


def tozala(h):
    """Jinja izohi {# … #} va HTML izohi <!-- … --> — hisobga olinmaydi."""
    h = re.sub(r"\{#.*?#\}", "", h, flags=re.S)
    return re.sub(r"<!--.*?-->", "", h, flags=re.S)


def sahifa_css(h):
    """Sahifaning HAMMA <style> bloklari, hujjat tartibida, BIRGA (Jinja teglari olib tashlanadi)."""
    bloklar = re.findall(r"<style[^>]*>(.*?)</style>", tozala(h), re.S)
    return "\n".join(re.sub(r"\{\{.*?\}\}", "X", re.sub(r"\{%.*?%\}", "", b, flags=re.S), flags=re.S) for b in bloklar)


def media_ziddiyat(h):
    """(media, selektor, xususiyat, media qiymati, keyingi asosiy qiymat) — @media qoidasini KEYINGI media'siz qoida bekor qiladi."""
    q = css_qoidalar(sahifa_css(h))
    res = []
    for i, (sel, dek, med) in enumerate(q):
        if not med:
            continue
        for sel2, dek2, med2 in q[i + 1:]:
            if sel2 != sel or med2:
                continue
            for x, (v, imp) in dek.items():
                if x in dek2 and not imp and dek2[x][0] != v:
                    res.append((med[-1], sel, x, v, dek2[x][0]))
    return res


def inline_ziddiyat(h):
    """(media, #id, xususiyat, qoida qiymati, inline qiymati) — `<style>` dagi `#id` qoidasi elementning o'z `style` atributi bilan
    bekor bo'ladi (inline ustun; qoida !important siz)."""
    t = tozala(h)
    inl = {}
    for m in re.finditer(r"<[a-zA-Z][^>]*>", t):
        teg = m.group(0)
        mi = re.search(r'\bid="([\w-]+)"', teg)
        ms = re.search(r'\bstyle="([^"]*)"', teg)
        if mi and ms:
            d = {}
            for p in ms.group(1).split(";"):
                if ":" in p:
                    a, b = p.split(":", 1)
                    d[a.strip().lower()] = b.strip()
            inl[mi.group(1)] = d
    res = []
    for sel, dek, med in css_qoidalar(sahifa_css(h)):
        m = re.fullmatch(r"#([\w-]+)", sel)
        if not m or m.group(1) not in inl:
            continue
        for x, (v, imp) in dek.items():
            iv = inl[m.group(1)].get(x)
            if iv is not None and not imp and "!important" not in iv and iv != v:
                res.append((" ".join(med) or "-", sel, x, v, iv))
    return res


# ══════════════════════════════════════════════════════════════
section("T1. Skanerning o'zi — soxta kirishlar")
# ══════════════════════════════════════════════════════════════
_m1 = media_ziddiyat("<style>@media (max-width:600px){ .a{position:static;color:red} }\n.a{position:absolute;color:red}</style>")
_m2 = media_ziddiyat("<style>.a{position:absolute}\n@media (max-width:600px){ .a{position:static} }</style>")
_m3 = media_ziddiyat("<style>@media (max-width:600px){ .a{position:static !important} }\n.a{position:absolute}</style>")
_m4 = media_ziddiyat("<style>@media (max-width:600px){ .a, .b{max-height:60vh} }\n/* eski: .a{max-height:1px} */\n.b{max-height:340px}</style>")
_m5 = media_ziddiyat("<style>@media(max-width:768px){ #d{display:flex} }</style>\n<div></div>\n<style>#d{display:none}</style>")
_m6 = media_ziddiyat("{# <style>.a{color:red}</style> #}<style>@media (max-width:600px){ .a{color:blue} }</style>"
                     "<!-- <style>.a{color:green}</style> -->")
_m7 = media_ziddiyat("<style>@media (max-width:600px){ .a{display:flex} }\n.a{color:red}</style>")
check("T1a media qoidasini KEYINGI asosiy qoida bekor qilsa — topadi (faqat farqli xususiyat); asosiy qoidadan KEYINGI media — "
      "ziddiyat emas; `!important` — emas; vergulli selektor; CSS izohidagi qoida hisobga olinmaydi",
      _m1 == [("@media (max-width:600px)", ".a", "position", "static", "absolute")] and _m2 == [] and _m3 == []
      and _m4 == [("@media (max-width:600px)", ".b", "max-height", "60vh", "340px")], (_m1, _m2, _m3, _m4))
check("T1b bir sahifadagi IKKI <style> bloki birga ko'riladi (avvalgi skaner ko'rmasdi); Jinja / HTML izohidagi <style> — hisobga "
      "olinmaydi; boshqa xususiyat — ziddiyat emas",
      _m5 == [("@media(max-width:768px)", "#d", "display", "flex", "none")] and _m6 == [] and _m7 == [], (_m5, _m6, _m7))
_i1 = inline_ziddiyat('<style>@media(max-width:900px){ #g{grid-template-columns:1fr} }</style>'
                      '<div id="g" style="display:grid;grid-template-columns:1fr 1fr;gap:14px"></div>')
_i2 = inline_ziddiyat('<style>@media(max-width:900px){ #g{grid-template-columns:none !important;gap:12px} }</style>'
                      '<div style="gap:14px;grid-template-columns:1fr 1fr" id="g"></div>')
_i3 = inline_ziddiyat('<style>#g{color:red;padding:4px}</style><div id="g" style="margin:0"></div><div id="h" style="color:blue"></div>')
_i4 = inline_ziddiyat('<style>#g{color:red}</style><div id="g" style="color:blue !important"></div>')
_i5 = inline_ziddiyat('{# <style>#g{gap:2px}</style> #}<div id="g" style="gap:14px"></div>')
check("T1c inline `style` ustun bo'lgan `#id` qoidasi — topadi (atributlar tartibi farq qilmaydi, !important li qoida — emas); "
      "boshqa xususiyat / boshqa id — emas; izohdagi qoida — emas",
      _i1 == [("@media(max-width:900px)", "#g", "grid-template-columns", "1fr", "1fr 1fr")]
      and _i2 == [("@media(max-width:900px)", "#g", "gap", "12px", "14px")] and _i3 == [] and _i4 == [] and _i5 == [],
      (_i1, _i2, _i3, _i4, _i5))

# ══════════════════════════════════════════════════════════════
section("T2 / T3. Hamma shablonlar")
# ══════════════════════════════════════════════════════════════
SHABLON = sorted(glob.glob(os.path.join(ROOT, "templates", "*.html")))
check("T2a shablonlar topildi (≥ 30)", len(SHABLON) >= 30, len(SHABLON))
_A, _B = [], []
for _f in SHABLON:
    _h = open(_f, encoding="utf-8").read()
    _A += [(os.path.basename(_f),) + x for x in media_ziddiyat(_h)]
    _B += [(os.path.basename(_f),) + x for x in inline_ziddiyat(_h)]
check("T2 HAMMA shablonlarda telefon (@media) qoidasini KEYINGI asosiy qoida bekor qilmaydi (sahifaning hamma <style> bloklari "
      "birga; ilgari: dashboard `#topGridDots` display, orders `.ord-list` max-height, `.right-panel` flex-direction)", not _A, _A)
check("T3 HAMMA shablonlarda `#id` qoidasi elementning o'z `style` atributi bilan bekor bo'lmaydi (ilgari: dashboard `#topGrid` "
      "gap 12px va 900px dagi bitta ustun)", not _B, _B)

# ══════════════════════════════════════════════════════════════
section("T4. Dashboard va Buyurtmalar — aniq joylar")
# ══════════════════════════════════════════════════════════════
D = open(os.path.join(ROOT, "templates", "dashboard.html"), encoding="utf-8").read()
O = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
_dq = css_qoidalar(sahifa_css(D))
_nuq = [(dek.get("display", ("",))[0], med) for sel, dek, med in _dq if sel == "#topGridDots" and "display" in dek]
check("T4a Dashboard: nuqtalar — asosiy qoida `display:none` (media'siz) BIRINCHI, keyin telefon blokida (`max-width:768px`) "
      "`display:flex`; boshqa `#topGridDots` display qoidasi yo'q",
      len(_nuq) == 2 and _nuq[0] == ("none", ()) and _nuq[1][0] == "flex" and "768px" in " ".join(_nuq[1][1]), _nuq)
_grid_med = [dek for sel, dek, med in _dq if sel == "#topGrid" and med]
check("T4b Dashboard: `#topGrid` telefon qoidalarida inline dagi xususiyatlar faqat `!important` bilan (display, grid-template-columns); "
      "`gap` — inline dagi 14px (telefon blokida yo'q)",
      _grid_med and all(("gap" not in d) for d in _grid_med)
      and all(d[x][1] for d in _grid_med for x in ("display", "grid-template-columns") if x in d), _grid_med)
_oq = css_qoidalar(sahifa_css(O))
check("T4c Buyurtmalar: `.right-panel` uchun `column-reverse` yo'q; `.ord-list{max-height:280px}` telefon qoidasi BITTA (keyingi "
      "telefon blokida — asosiy qoidadan KEYIN)",
      not [1 for sel, dek, med in _oq if sel == ".right-panel" and "column-reverse" in dek.get("flex-direction", ("",))[0]]
      and len([1 for sel, dek, med in _oq if sel == ".ord-list" and med and dek.get("max-height", ("",))[0] == "280px"]) == 1,
      [(sel, dek, med) for sel, dek, med in _oq if sel in (".right-panel", ".ord-list")])

print("\n" + "=" * 70)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
