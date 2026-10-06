#!/usr/bin/env python3
"""
test_d122.py — kech118 D BOSQICHI 2-qism (zip 122): TUNGI REJIM TO'LIQ (audit U-02; egasi QARORI «To'liq tuzatilsin — har
sahifa ranglari umumiy ranglar ro'yxatiga», tugmali, QAYTA SO'RALMAYDI).

NIMA UCHUN KERAK
  Tungi rejimda sahifalarning o'z ranglari (shablonlarga to'g'ridan-to'g'ri yozilgan #hex: och fonli belgilar, kartalar,
  ustunlar, to'q yozuvlar) o'zgarmasdi: qorong'i sahifada oq / och kartalar, qorong'i kartada to'q yozuv (o'qilmasdi).
  HAQIQIY brauzerda o'lchandi (work/k114/audit, 1440 va 390 px): tungi rejimda 562 / 516 kontrast xatosi (yorug'da — 0).
  YECHIM: shablonlardagi CSS ranglari XOSSASIGA qarab umumiy ro'yxatga (static/ranglar.css) o'tkazildi:
    --f-<hex>  — FON (yorug' tus)      tungi: qorong'i tus (shu rang turi)
    --m-<hex>  — MATN (to'q tus)       tungi: yorug' tus (kartada ≥ 4.5:1)
    --ch-<hex> — CHEGARA (yorug' tus)  tungi: qorong'i chiziq
  <hex> — yorug' rejimdagi AYNAN o'sha rang: yorug' ko'rinish O'ZGARMAYDI (piksel solishtirildi). JS chizgan ranglar
  (holat yozuvlari — `matnRangi`, grafiklar) tungi rejimga moslanadi, rejim almashtirilganda sahifa qayta yuklanadi.
BO'LIMLAR:
  P — ro'yxat (static/ranglar.css): tuzilishi, har ishlatilgan rang bor, ortiqchasi yo'q, yorug' qiymat = nomdagi rang,
      tungi qiymatlar kontrasti (matn kartada / sahifada / och-tusli fonda ≥ 4.5:1; standart yozuv har fonda ≥ 4.5:1).
  G — darvoza: shablonlarga YANGI xom rang (och fon / to'q yozuv / och chegara) yozilmagan — ro'yxatdan olinadi.
  S — sahifalar ro'yxatni ulaydi (base.html va mustaqil sahifalar: style.css dan KEYIN), server faylni beradi, kesh
      yangilangan, chizilgan sahifalardagi har rang ro'yxatda bor.
  T — kod bo'yicha / oynalar auditida topilgan joylar: KPI medal raqami, Dashboard belgisi, Retsept kategoriyalari, tungi
      rejimdagi asosiy tugma, oq yozuvli yashil tugma, xabar oynasi sarlavhasi.
  JS xatti-harakati (matnRangi, grafiklar, rejim tugmasi) — tools/test_d122_ui.js.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16; `TENANT_FILTER=1` bilan ham.
ISHLATISH: python3 tools/test_d122.py
"""
import os
import re
import sys
import glob
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "d122_test"
_T = tempfile.mkdtemp(prefix="d122_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'd122_test.db')}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF] " if os.environ.get("TENANT_FILTER") else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e}"
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def fayl(nom):
    try:
        with open(os.path.join(ROOT, nom), encoding="utf-8") as f:
            return f.read()
    except Exception:                      # noqa: BLE001
        return ""


# ── Rang hisoblari (WCAG nisbiy yorqinlik, CIE L*) — work/k122/rang.py bilan bir usul ──
def hex_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lin(v):
    v /= 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def lum(h):
    r, g, b = (_lin(x) for x in hex_rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def kontrast(a, b):
    x, y = lum(a), lum(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


def L_yulduz(h):
    y = lum(h)
    return 116 * (y ** (1 / 3)) - 16 if y > 0.008856 else 903.3 * y


def norm(h):
    h = h.lstrip("#").upper()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h


def blok(css, bosh):
    """`bosh {` dan keyingi birinchi `}` gacha — `--nom: #hex;` lar lug'ati (blok yo'q — None)."""
    i = css.find(bosh)
    if i < 0:
        return None
    j = css.find("}", i)
    return {k: norm(v) for k, v in re.findall(r"--([\w-]+)\s*:\s*(#[0-9A-Fa-f]{3,6})\s*;", css[i:j])}


TOKEN = re.compile(r"var\(--((?:f|m|ch|doim)-([0-9a-f]{6}))\)")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P — umumiy ranglar ro'yxati (static/ranglar.css)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
RANG = fayl("static/ranglar.css")
STYLE = fayl("static/style.css")
YORUG = blok(RANG, ":root {") or {}
TUNGI = blok(RANG, 'html[data-theme="dark"] {') or {}
_DOIM = {k for k in YORUG if k.startswith("doim-")}
check("P1 static/ranglar.css bor: `:root` (yorug') va `html[data-theme=\"dark\"]` (tungi) bloklari, IKKALASIDA bir xil "
      "nomlar (--doim-… — o'zgarmas rang — faqat :root da), kamida 100 rang",
      RANG and YORUG and TUNGI and set(YORUG) - _DOIM == set(TUNGI) and len(TUNGI) >= 100
      and all(re.fullmatch(r"(f|m|ch|doim)-[0-9a-f]{6}", k) for k in YORUG),
      (len(YORUG), len(TUNGI), sorted((set(YORUG) - _DOIM) ^ set(TUNGI))[:10],
       [k for k in YORUG if not re.fullmatch(r"(f|m|ch|doim)-[0-9a-f]{6}", k)][:10]))
_noto = {k: v for k, v in YORUG.items() if v != "#" + k.split("-", 1)[1].upper()}
check("P2 yorug' rejim O'ZGARMAYDI: har rangning yorug' qiymati — nomidagi AYNAN rang (--f-fef3c7: #FEF3C7)",
      YORUG and not _noto, list(_noto.items())[:10])

SHABLONLAR = sorted(glob.glob(os.path.join(ROOT, "templates", "*.html")))
_ishlatilgan = {}
for _f in SHABLONLAR + [os.path.join(ROOT, "static", "style.css")]:
    for _m in TOKEN.finditer(open(_f, encoding="utf-8").read()):
        _ishlatilgan.setdefault(_m.group(1), set()).add(os.path.relpath(_f, ROOT))
_yoq = {k: sorted(v) for k, v in _ishlatilgan.items() if k not in YORUG or (k not in TUNGI and not k.startswith("doim-"))}
check("P3 shablonlar va style.css dagi HAR `var(--f-/m-/ch-/doim-…)` ro'yxatda bor (yo'q bo'lsa fon / yozuv rangsiz qolardi)",
      _ishlatilgan and not _yoq, list(_yoq.items())[:10])
_ortiq = sorted(set(YORUG) - set(_ishlatilgan))
check("P4 ro'yxatda ishlatilmaydigan (eskirgan) rang yo'q", YORUG and not _ortiq, _ortiq[:20])

_D = blok(STYLE, 'html[data-theme="dark"] {') or {}
KARTA, SAHIFA, MATN = _D.get("white"), _D.get("bg"), _D.get("text")
check("P5 style.css tungi bloki: karta (--white), sahifa (--bg), yozuv (--text) — o'qildi",
      KARTA and SAHIFA and MATN, _D)
KARTA, SAHIFA, MATN = KARTA or "#1E212A", SAHIFA or "#16181F", MATN or "#ECEAE6"
_past = [(k, v, round(kontrast(v, KARTA), 2), round(kontrast(v, SAHIFA), 2)) for k, v in TUNGI.items()
         if k.startswith("m-") and min(kontrast(v, KARTA), kontrast(v, SAHIFA)) < 4.5]
check(f"P6 tungi: har MATN rangi qorong'i kartada ({KARTA}) va sahifada ({SAHIFA}) ≥ 4.5:1",
      TUNGI and not _past, _past[:10])
_past = [(k, v, round(kontrast(v, MATN), 2)) for k, v in TUNGI.items() if k.startswith("f-") and kontrast(v, MATN) < 4.5]
check(f"P7 tungi: har FON rangi ustida standart yozuv ({MATN}) ≥ 4.5:1 (fon qorong'i tusga o'tgan)",
      TUNGI and not _past, _past[:10])
_ochf = {k: v for k, v in TUNGI.items() if k.startswith("f-") and L_yulduz("#" + k[2:]) >= 80}
_past = sorted((round(kontrast(mv, fv), 2), mk, fk) for mk, mv in TUNGI.items() if mk.startswith("m-")
               for fk, fv in _ochf.items() if kontrast(mv, fv) < 4.5)
check("P8 tungi: har MATN rangi har och-tusli belgi FONIDA (yorug' rejimda L* ≥ 80 — «Qisman», «Kam», holat belgilari) "
      "≥ 4.5:1", _ochf and not _past, (len(_ochf), _past[:10]))
_yomon = [(k, v, round(L_yulduz(v), 1)) for k, v in TUNGI.items()
          if (k.startswith("f-") and L_yulduz(v) > 35) or (k.startswith("ch-") and L_yulduz(v) > 40)
          or (k.startswith("m-") and L_yulduz(v) < 60)]
check("P9 tungi qiymatlar haqiqatan almashgan: fon — qorong'i (L* ≤ 35), chegara — qorong'i chiziq (L* ≤ 40), "
      "matn — yorug' (L* ≥ 60)", TUNGI and not _yomon, _yomon[:10])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("G — darvoza: shablonlarga yangi XOM rang yozilmagan (work/k122/palitra.py qoidasi)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
XOSSA = re.compile(r'(?<![\w-])(background-color|background|color|border-color|border-top-color|border-bottom-color|'
                   r'border-left-color|border-right-color|border-top|border-bottom|border-left|border-right|border|outline-color|'
                   r'outline)(\s*:\s*)([^;"\'`}>{]*)')
HEX = re.compile(r'#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b')
QHEX = re.compile(r"""(['"])(#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3}))\1""")
JSXOSSA = re.compile(r'(?<![\w-])(background-color|background|color|border-color|border-top|border-bottom|border-left|'
                     r'border-right|border|outline)\s*:\s*[^;"\'`$]*\$\{')
JINJAXOSSA = re.compile(r'(?<![\w-])(background-color|background|color|border-color|border-top|border-bottom|border-left|'
                        r'border-right|border|outline)\s*:\s*[^;"\'`{]*\{\{(.*?)\}\}')
JSFON = re.compile(r"""(?<![\w-])(?:bg|fon|bgColor|background)\s*:\s*['"](#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3}))['"]""")
STYLEJS = re.compile(r'\.style\.(color|background|backgroundColor|borderColor|borderTopColor|borderBottomColor|'
                     r'borderLeftColor|borderRightColor|outlineColor)\s*=\s*([^;\n]+)')


def rol(x):
    if x.startswith("background"):
        return "f"
    return "m" if x == "color" else "ch"


def kerak(r, h):
    """Shu xossa uchun ro'yxatdan olinishi SHART bo'lgan rangmi (och fon — #fff dan tashqari, to'q yozuv, och chegara)."""
    L = L_yulduz(h)
    if r == "f":
        return h != "#FFFFFF" and L >= 70
    if r == "m":
        return L < 70
    return L >= 75


def xom_ranglar(matn):
    topildi = []

    def qiymat(r, q, joy):
        if "url(" in q:
            return
        q = re.sub(r"var\([^()]*\)", "", q)       # var(--x, #zaxira) — zaxira qiymat hisobga olinmaydi
        for m in HEX.finditer(q):
            h = norm(m.group(0))
            if kerak(r, h):
                topildi.append((joy, r, h))

    for m in XOSSA.finditer(matn):
        qiymat(rol(m.group(1)), m.group(3), m.start())
    for m in JSXOSSA.finditer(matn):
        r, k, d = rol(m.group(1)), m.end(), 1
        while k < len(matn) and d:
            d += {"{": 1, "}": -1}.get(matn[k], 0)
            k += 1
        for q in QHEX.finditer(matn[m.end():k]):
            h = norm(q.group(2))
            if kerak(r, h):
                topildi.append((m.start(), r, h))
    # Jinja ifodasidagi rang: style="background:{{ '#FEF2F2' if … else '#FFFBEB' }}"
    for m in JINJAXOSSA.finditer(matn):
        for q in QHEX.finditer(m.group(2)):
            h = norm(q.group(2))
            if kerak(rol(m.group(1)), h):
                topildi.append((m.start(), rol(m.group(1)), h))
    # JS rang jadvali: { bg: '#EDE9FE', … } (keyin `background:${st.bg}`) — fon
    for m in JSFON.finditer(matn):
        h = norm(m.group(1))
        if kerak("f", h):
            topildi.append((m.start(), "f", h))
    for m in STYLEJS.finditer(matn):
        r = {"color": "m", "background": "f", "backgroundColor": "f"}.get(m.group(1), "ch")
        for q in QHEX.finditer(m.group(2)):
            h = norm(q.group(2))
            if kerak(r, h):
                topildi.append((m.start(), r, h))
    return topildi


_xom = []
for _f in SHABLONLAR:
    _s = open(_f, encoding="utf-8").read()
    for _j, _r, _h in xom_ranglar(_s):
        _xom.append(f"{os.path.basename(_f)}:{_s.count(chr(10), 0, _j) + 1} {_r} {_h}")
_i = STYLE.find('html[data-theme="dark"] {')
_j0 = STYLE.find("}", _i) + 1
for _j, _r, _h in xom_ranglar(STYLE[_j0:]):
    _xom.append(f"static/style.css:{STYLE.count(chr(10), 0, _j0 + _j) + 1} {_r} {_h}")
check("G1 shablonlar va style.css komponentlarida och FON / to'q YOZUV / och CHEGARA uchun xom #hex YO'Q (tungi rejimda "
      "o'zgarmay qolardi) — rang ro'yxatdan olinadi (var(--f-…), var(--m-…), var(--ch-…))", not _xom, _xom[:15])
# darvoza o'zi ishlaydimi — namunada topishi kerak (darvoza «hech narsa topmaydigan» bo'lib qolmasin)
_namuna = ('<div style="background:#FEF3C7;color:#92400E;border:1px solid #FDE68A">x</div>'
           '<style>.a{background:var(--white,#fff);color:#fff;background:#B9783F}</style>'
           "<script>el.innerHTML = `<b style=\"color:${ok ? '#15803D' : '#FCA5A5'}\">`; el.style.background = '#F0FDF4';"
           "const S = {a: {bg: '#EDE9FE', fg: '#7C3AED'}};</script>"
           "<span style=\"background:{{ '#FEE2E2' if x else '#B9783F' }};color:{{ '#991B1B' if x else '#fff' }}\">j</span>")
_t = sorted((r, h) for _, r, h in xom_ranglar(_namuna))
check("G2 darvoza namunada ishlaydi: ichki uslub (och fon, to'q yozuv, och chegara), JS shablon satri, el.style, JS rang "
      "jadvali (bg:), Jinja ifodasi ({{ '#…' if … }}) — topiladi; #fff fon, oq yozuv, to'q (to'yingan) tugma foni, var() "
      "zaxirasi — topilmaydi",
      _t == [("ch", "#FDE68A"), ("f", "#EDE9FE"), ("f", "#F0FDF4"), ("f", "#FEE2E2"), ("f", "#FEF3C7"), ("m", "#15803D"),
             ("m", "#92400E"), ("m", "#991B1B")], _t)

# var(--nom, #zaxira) — nom HECH QAYERDA belgilanmagan bo'lsa ikkala rejimda zaxira (oq / och) rang chiqardi (MRP mahsulot
# tanlash oynasi: `var(--card-bg,#fff)` — tungi rejimda oq oyna, yorug' yozuv 1.2:1)
_belgilangan = set()
for _f in SHABLONLAR + [os.path.join(ROOT, "static", "style.css"), os.path.join(ROOT, "static", "ranglar.css")]:
    _s = fayl(os.path.relpath(_f, ROOT))            # asl kodda ranglar.css yo'q — qulamaydi
    _belgilangan |= set(re.findall(r"(--[\w-]+)\s*:", _s)) | set(re.findall(r"setProperty\(\s*['\"](--[\w-]+)", _s))
_zaxirali = []
for _f in SHABLONLAR + [os.path.join(ROOT, "static", "style.css")]:
    _s = open(_f, encoding="utf-8").read()
    for _m in re.finditer(r"var\((--[\w-]+)\s*,\s*[^()]*#[0-9A-Fa-f]{3,6}[^()]*\)", _s):
        if _m.group(1) not in _belgilangan:
            _zaxirali.append(f"{os.path.basename(_f)}:{_s.count(chr(10), 0, _m.start()) + 1} {_m.group(0)}")
check("G3 rang zaxirasi bilan ishlatilgan har o'zgaruvchi (var(--x, #…)) belgilangan — belgilanmagani har rejimda zaxira "
      "rangni berardi", not _zaxirali, _zaxirali[:10])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — sahifalar ro'yxatni ulaydi, server beradi, kesh yangilangan")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_ulanmagan = []
for _f in SHABLONLAR:
    _s = open(_f, encoding="utf-8").read()
    if not TOKEN.search(_s) or re.search(r'{%\s*extends\s+"base\.html"\s*%}', _s):
        continue
    # kech118 (zip 123, MOSLANDI): «_» bilan boshlanuvchi qism (`_brak_oyna.html`) — o'zi sahifa emas, base.html ni kengaytiruvchi
    # sahifalarga `{% include %}` qilinadi (ro'yxat o'sha sahifada ulangan)
    if os.path.basename(_f).startswith("_"):
        _ulovchi = [g for g in SHABLONLAR if f'{{% include "{os.path.basename(_f)}" %}}' in open(g, encoding="utf-8").read()]
        if _ulovchi and all(re.search(r'{%\s*extends\s+"base\.html"\s*%}', open(g, encoding="utf-8").read()) for g in _ulovchi):
            continue
    _a = _s.find('href="/static/style.css?v={{ static_version }}"')
    _b = _s.find('href="/static/ranglar.css?v={{ static_version }}"')
    if _a < 0 or _b < 0 or _b < _a:
        _ulanmagan.append((os.path.basename(_f), _a, _b))
_bs = fayl("templates/base.html")
_a, _b = _bs.find('href="/static/style.css?v={{ static_version }}"'), _bs.find('href="/static/ranglar.css?v={{ static_version }}"')
check("S1 base.html ro'yxatni style.css dan KEYIN ulaydi (?v= kesh belgisi bilan)", 0 <= _a < _b, (_a, _b))
check("S2 base.html ni kengaytirmaydigan, ranglardan foydalanadigan HAR sahifa (kirish, hodim kirishi / paneli, xato "
      "sahifasi) ham ro'yxatni style.css dan KEYIN ulaydi", not _ulanmagan, _ulanmagan)
_v = main.templates.env.globals.get("static_version")
check("S3 kesh belgisi yangilangan (eski «20260930-3» — brauzer eski style.css ni ushlab qolmasin)",
      _v and _v != "20260930-3", _v)

s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t122_admin", "Parol123!", UserRole.ADMIN, "T122 Admin", company_id=1)
s.commit()
s.close()
C0 = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_r = C0.get("/static/ranglar.css")
check("S4 /static/ranglar.css — 200, text/css, fayl bilan bir xil",
      _r.status_code == 200 and "text/css" in _r.headers.get("content-type", "") and _r.text == RANG,
      (_r.status_code, _r.headers.get("content-type")))
CA = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_rl = CA.post("/login", data={"username": "t122_admin", "password": "Parol123!"}, follow_redirects=False)
check("S5 admin kirdi (302)", _rl.status_code == 302, _rl.status_code)
_havola = f'/static/ranglar.css?v={_v}'
for _kl, _yol, _kut in ((C0, "/login", 200), (C0, "/hodim/login", 200), (C0, "/yoq-sahifa-d122", 404),
                        (CA, "/dashboard", 200), (CA, "/finance", 200), (CA, "/reports", 200), (CA, "/debts", 200),
                        (CA, "/finished", 200), (CA, "/orders", 200), (CA, "/", 200), (CA, "/suppliers/receive", 200)):
    _x = _kl.get(_yol, follow_redirects=False, headers={"Accept": "text/html"})   # brauzer kabi (xato sahifasi — HTML)
    _ish = {m.group(1) for m in TOKEN.finditer(_x.text)}
    _yoqlar = sorted(t for t in _ish if t not in YORUG)
    check(f"S6 {_yol} — {_kut}, ro'yxat ulangan, sahifadagi har rang ro'yxatda bor",
          _x.status_code == _kut and _havola in _x.text and _x.text.find("/static/style.css?v=") < _x.text.find(_havola)
          and not _yoqlar, (_x.status_code, _havola in _x.text, _yoqlar[:10]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T — tekshiruvda topilgan joylar (sinov ma'lumotida ko'rinmagan, kod bo'yicha topildi)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_kpi = fayl("templates/kpi.html")
check("T1 KPI medal raqami (oltin / kumush / bronza doira) — yozuv IKKALA rejimda to'q (var(--doim-1f2937)): doira rangi "
      "o'zgarmaydi, tungi rejimda yorug' yozuv unda o'qilmasdi (1.6:1)",
      "background:${medalColors[rank]};color:var(--doim-1f2937);" in _kpi
      and "const medalColors = {1:'#F5B301', 2:'#B0B7C3', 3:'#C97F3D'};" in _kpi)
_dash = fayl("templates/dashboard.html")
check("T2 Dashboard majburiyat belgisi — noma'lum holatda ham fon ro'yxatdan (var(--f-fef2f2))",
      "const badgeBg = STATUS_BG[it.status] || 'var(--f-fef2f2)';" in _dash
      and re.search(r"const STATUS_BG = \{(?:\w+:'var\(--f-[0-9a-f]{6}\)',? ?)+\};", _dash))
_rec = fayl("templates/recipes.html")
_qat = re.findall(r"\{ icon: 'ti-[\w-]+', bg: '([^']*)', fg: '([^']*)', ic: '([^']*)'", _rec)
check("T3 Retsept tarkibi kategoriyalari: fon (bg) va belgi rangi (ic) — ro'yxatdan, yozuv — matnRangi(fg) (6 kategoriya); "
      "belgi `color:${st.ic}`",
      len(_qat) == 6 and all(re.fullmatch(r"var\(--f-[0-9a-f]{6}\)", b) and re.fullmatch(r"#[0-9A-F]{6}", f)
                             and i == f"var(--m-{f[1:].lower()})" for b, f, i in _qat)
      and _rec.count('style="background:${st.bg};color:${st.ic}"') == 2 and "color:${st.fg}" not in _rec, _qat)

_d = STYLE[STYLE.find('html[data-theme="dark"] {'):]
check("T4 tungi rejimda asosiy (qora) tugma — YORUG' fon, to'q yozuv (--doim-…); o'z fon rangi yozilgan tugmada (qizil, "
      "oltin) — oq yozuv",
      'html[data-theme="dark"] .btn-dark { background: var(--doim-eceae6); color: var(--doim-16181f); }' in _d
      and 'html[data-theme="dark"] .btn-dark[style*="background"] { color: #fff; }' in _d
      and kontrast("#ECEAE6", "#16181F") >= 4.5 and min(kontrast("#FFFFFF", x) for x in ("#9A6231", "#DC2626")) >= 4.5)
_yashil = []
for _f in SHABLONLAR:
    _s = open(_f, encoding="utf-8").read()
    for _m in re.finditer(r'style="([^"]*)"', _s):
        if re.search(r"background:\s*#16A34A", _m.group(1), re.I) and re.search(r"color:\s*#fff\b", _m.group(1), re.I):
            _yashil.append(f"{os.path.basename(_f)}:{_s.count(chr(10), 0, _m.start()) + 1}")
    for _m in re.finditer(r"(okBtn|arModal-ok'\))\.style\.background\s*=[^;\n]*#16A34A", _s, re.I):
        _yashil.append(f"{os.path.basename(_f)}:{_s.count(chr(10), 0, _m.start()) + 1} {_m.group(0)[:60]}")
check("T5 oq yozuvli yashil tugma (Sotish, Tasdiqlash, Saqlash) — #15803D (oq yozuv 5.0:1; #16A34A — 3.3:1, ikkala rejimda)",
      not _yashil and kontrast("#FFFFFF", "#15803D") >= 4.5
      # kech123 (U-13): «Sotish» — inline uslub YOKI umumiy `.btn-green` (style.css: #15803D, oq yozuv)
      and ("background:#15803D;color:#fff" in fayl("templates/finished.html")
           or ('class="btn btn-green"' in fayl("templates/finished.html")
               and ".btn-green { background: #15803D; color: #fff; }" in fayl("static/style.css"))),
      _yashil)
check("T6 xabar oynasi sarlavhasi rangi (Xatolik / Bajarildi / Diqqat) — ro'yxatdan (tungi rejimda yorug' tus)",
      "var _XO_RANG = {xato: 'var(--m-b91c1c)', ok: 'var(--m-15803d)', ogoh: 'var(--m-b45309)', info: ''};" in _bs)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  - " + f)
sys.exit(1 if FAIL else 0)
