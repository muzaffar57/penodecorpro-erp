#!/usr/bin/env python3
"""
test_e_hodim_kod.py — kech120, E BOSQICH 5-qism (HODIM KIRISHI: korxona kodi va QR, audit G6-07).

NIMA UCHUN KERAK (audit kech114; kodda va rasmda ko'rilgan):
  G6-07  Hodim kirishida «Korxona kodi» maydoni bor; ikkinchi korxona ulangan kundan kod MAJBURIY, lekin admin o'z kodini dasturda hech
         qayerda ko'rmaydi (faqat platforma korxona yaratganda bir marta). QR — begona saytdan rasm (`api.qrserver.com` — sinovda
         chiqmadi) va faqat «/hodim» manzili (kodsiz). «Chop etish» butun sahifani (menyu, loginlar ro'yxati) chop etadi.
         YO'LDA TOPILGAN: birinchi korxona (id=1) KODSIZ yaratiladi — ikkinchi korxona paydo bo'lgach uning hodimlari umuman kira
         olmaydi (kiritadigan kod yo'q).
BO'LIMLAR: S — statik; K — kodsiz korxonalarga kod (ishga tushishdagi to'ldirish: nomdan, yagona, kodi borga tegilmaydi; platforma
  bilan bitta qoida); H — hodim kirishi (ikki korxona: kodsiz — rad, kod bilan — kiradi; `/hodim?k=` → kirish sahifasi kod bilan;
  xatoda kiritilgan kod saqlanadi); Q — QR (`/api/hodim-qr.svg` — SVG, ichida `…/hodim?k=KOD` — brauzerda chizib, OpenCV bilan
  O'QILADI; begona manzil qabul qilinmaydi; boshqa korxona — o'z kodi); P — chop etish sahifasi (`/users/hodim-qr`: faqat QR, nom,
  kod, yo'riqnoma; menyusiz); U — Foydalanuvchilar sahifasi QR oynasi (begona sayt yo'q, kod ko'rinadi, «Chop etish» — alohida sahifa)
  va KPI «Panel kirishi» oynasi (kod, manzil); T — telefon 390 px; X — xatolar.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 129) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` + Chromium (Q / P / U / T), `cv2` (OpenCV — QR ni o'qish; yo'q bo'lsa o'sha tekshiruv yiqiladi).
ISHLATISH: python3 tools/test_e_hodim_kod.py
"""
import os
import re
import sys
import io
import glob
import time
import socket
import tempfile
import threading
import contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "e_hodim_kod_test"
_T = tempfile.mkdtemp(prefix="ehkod_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'e_hodim_kod_test.db')}"
os.environ.pop("TENANT_FILTER", None)

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Employee              # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
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


def oqi(yol):
    try:
        with open(os.path.join(ROOT, yol), encoding="utf-8") as f:
            return f.read()
    except Exception:                      # noqa: BLE001
        return ""


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
MAIN = oqi("main.py")
USR = oqi("templates/users.html")
KPI = oqi("templates/kpi.html")
HL = oqi("templates/hodim_login.html")
check("S1 begona QR sayti (`api.qrserver.com`) YO'Q; QR — serverda (`/api/hodim-qr.svg`, reportlab), chop etish — alohida sahifa",
      "qrserver" not in USR and "qrserver" not in KPI and '@app.get("/api/hodim-qr.svg")' in MAIN
      and "from reportlab.graphics.barcode import qrencoder" in MAIN and '@app.get("/users/hodim-qr"' in MAIN
      and "window.print()" not in USR)
check("S2 kodsiz korxonalarga kod — ishga tushishda (`_korxona_kodlarini_toldir`), qoida platforma bilan BITTA (`crud.korxona_kodi_yarat`)",
      "_korxona_kodlarini_toldir()\n" in MAIN and "kod = crud.korxona_kodi_yarat(db, nom)" in MAIN and hasattr(crud, "korxona_kodi_yarat"))
check("S3 hodim kirishi: `?k=` — maydon qiymati; `/hodim` kirishsiz → `/hodim/login?k=`; KPI «Panel kirishi» oynasida kod",
      'value="{{ kod or \'\' }}"' in HL and '"/hodim/login" + (f"?k={_q131(_k)}" if _k else "")' in MAIN
      and 'id="pa-korxona-kod"' in KPI and 'id="hodimQrKod"' in USR)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Kodsiz korxonalarga kod")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_db = SessionLocal()
_c1 = _db.query(Company).filter(Company.id == 1).first()
_kod1_import = _c1.code if _c1 else "YO'Q"         # ilova yuklanganda (seed → to'ldirish) olgan kodi
if _c1 is not None:
    _c1.code = None                                 # ishga tushishdagi holat: 1-korxona KODSIZ yaratilgan
for _cid, _nom, _kod in ((2, "Andijon Dekor", None), (3, "andijon dekor", ""), (4, "Bor Kodli", "BOR-KOD-7"), (5, "ANDIJON DEKOR", None)):
    if not _db.query(Company).filter(Company.id == _cid).first():
        _db.add(Company(id=_cid, name=_nom, code=_kod))
_db.commit()
_db.close()
_toldir = getattr(main, "_korxona_kodlarini_toldir", None)      # asl kodda yo'q — test qulamaydi, yiqiladi
with contextlib.redirect_stdout(_quiet):
    if _toldir:
        _toldir()
        _toldir()                              # ikkinchi marta — hech narsa o'zgarmaydi
_db = SessionLocal()
KOD = {c.id: (c.code or "") for c in _db.query(Company).all()}       # kodsiz — "" (asl kod: test qulamaydi)
_db.close()
check("K1 1-korxona (ishga tushishda kodsiz yaratiladi) — ilova yuklanganda kod oldi; kodsiz holatdan to'ldirish — nomdan (PENODECORPRO)",
      _kod1_import == "PENODECORPRO" and KOD.get(1) == "PENODECORPRO", (_kod1_import, KOD.get(1)))
check("K2 bir xil nomli kodsizlar — YAGONA kodlar (ANDIJON-DEKOR, -2, -3); kodi bor korxona — o'zgarmadi; takror ishga tushish — o'zgarmaydi",
      [KOD.get(2), KOD.get(3), KOD.get(5)] == ["ANDIJON-DEKOR", "ANDIJON-DEKOR-2", "ANDIJON-DEKOR-3"] and KOD.get(4) == "BOR-KOD-7"
      and len(set(KOD.values())) == len(KOD), KOD)
_db = SessionLocal()
_kyar = getattr(crud, "korxona_kodi_yarat", None)
_k3 = _kyar(_db, "Andijon Dekor") if _kyar else None
check("K3 platforma bilan bitta qoida: «Andijon Dekor» uchun keyingi kod — ANDIJON-DEKOR-4", _k3 == "ANDIJON-DEKOR-4", _k3)
_db.close()

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H. Hodim kirishi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ADMIN, PAROL = "ehk_admin", "Parol123!"
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, ADMIN, PAROL, UserRole.ADMIN, "Kod Admin", company_id=1)
    auth.create_user(_db, "ehk_b", PAROL, UserRole.ADMIN, "B Admin", company_id=2)
_e1 = Employee(company_id=1, name="Hodim Bir", phone="+998901112233")
_e2 = Employee(company_id=2, name="Hodim Ikki", phone="+998901112233")
_db.add_all([_e1, _e2])
_db.commit()
E1, E2 = _e1.id, _e2.id
_db.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
CB = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_l1 = C.post("/login", data={"username": ADMIN, "password": PAROL}, follow_redirects=False).status_code
_l2 = CB.post("/login", data={"username": "ehk_b", "password": PAROL}, follow_redirects=False).status_code
_p1 = C.post(f"/api/employees/{E1}/set-login", data={"phone": "+998901112233", "pin": "1234"})
_p2 = CB.post(f"/api/employees/{E2}/set-login", data={"phone": "+998901112233", "pin": "5678"})
check("H0 adminlar kirdi, ikki korxonada bir xil telefonli hodimga panel kirishi berildi", (_l1, _l2) == (302, 302)
      and _p1.status_code == 200 and _p2.status_code == 200, (_l1, _l2, _p1.status_code, _p1.text[:200], _p2.status_code))
H = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_r0 = H.post("/hodim/login", data={"phone": "+998901112233", "pin": "1234", "korxona": ""}, follow_redirects=False)
_r1 = H.post("/hodim/login", data={"phone": "+998901112233", "pin": "1234", "korxona": KOD.get(1, "").lower()}, follow_redirects=False)
H2 = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_r2 = H2.post("/hodim/login", data={"phone": "+998901112233", "pin": "5678", "korxona": KOD.get(2, "")}, follow_redirects=False)
check("H1 bir nechta korxona: kodsiz — «Korxona kodi topilmadi»; 1-korxona kodi (kichik harf bilan ham) — kirdi; 2-korxona kodi — o'z hodimi",
      _r0.status_code == 200 and "Korxona kodi topilmadi" in _r0.text and _r1.status_code == 302 and _r1.headers.get("location") == "/hodim"
      and _r2.status_code == 302, (_r0.status_code, _r1.status_code, _r2.status_code))
H3 = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_r3 = H3.get(f"/hodim?k={KOD.get(1)}", follow_redirects=False)
_r4 = H3.get(f"/hodim/login?k={KOD.get(1)}")
_r5 = H3.get("/hodim/login?k=%22%3E%3Cscript%3Ex%3C%2Fscript%3E")
_r6 = H3.post("/hodim/login", data={"phone": "+998900000000", "pin": "0000", "korxona": KOD.get(1)})
check("H2 QR manzili `/hodim?k=KOD` (kirmagan) → `/hodim/login?k=KOD`; kirish sahifasida kod maydonda; xavfli matn — escape; noto'g'ri "
      "PIN dan keyin kiritilgan kod saqlanadi",
      _r3.status_code == 302 and _r3.headers.get("location") == f"/hodim/login?k={KOD.get(1)}"
      and f'name="korxona" value="{KOD.get(1)}"' in _r4.text and "<script>x</script>" not in _r5.text and "&#34;&gt;&lt;script&gt;" in _r5.text
      and "PIN noto" in _r6.text and f'name="korxona" value="{KOD.get(1)}"' in _r6.text,
      (_r3.status_code, _r3.headers.get("location"), re.findall(r'name="korxona" value="[^"]*"', _r4.text + _r6.text)))
_r7 = H3.get("/hodim/login")
# kech120 (zip 137 — G6-20, MOSLANDI): namuna qisqa — «Admindan so'rang» (telefonda «Administratordan so'rang (QR kodda bor)» kesilardi)
check("H3 kodsiz ochilganda maydon bo'sh, ko'rsatma «Admindan so'rang»", 'name="korxona" value=""' in _r7.text
      and "Admindan so'rang" in _r7.text, re.findall(r'name="korxona"[^>]*>', _r7.text))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Q. QR kod (server)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_q1 = C.get("/api/hodim-qr.svg?manzil=https%3A%2F%2Fweb-sinov.up.railway.app")
_q2 = C.get("/api/hodim-qr.svg?manzil=javascript%3Aalert(1)")
_q3 = CB.get("/api/hodim-qr.svg?manzil=https%3A%2F%2Fweb-sinov.up.railway.app")
_q4 = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False).get("/api/hodim-qr.svg", follow_redirects=False)
check("Q1 `/api/hodim-qr.svg`: SVG (image/svg+xml, bitta `path`, oq fon), kirmagan — rad (401 / kirishga)",
      _q1.status_code == 200 and _q1.headers.get("content-type", "").startswith("image/svg+xml") and _q1.text.startswith("<svg")
      and _q1.text.count("<path") == 1 and _q4.status_code in (401, 302, 303), (_q1.status_code, _q1.headers.get("content-type"), _q4.status_code))
QR_SVG = {"a": _q1.text if _q1.status_code == 200 else "", "begona": _q2.text if _q2.status_code == 200 else "",
          "b": _q3.text if _q3.status_code == 200 else ""}

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
try:
    import cv2                                     # noqa: E402
    import numpy as _np                            # noqa: E402
    CV, _cv_x = True, ""
except Exception as _e:                    # noqa: BLE001
    CV, _cv_x = False, f"{type(_e).__name__}: {_e}"
check("B0 OpenCV (`cv2`) bor — QR ni o'qish uchun", CV, _cv_x)
try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_x = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_x = False, f"{type(_e).__name__}: {_e}"
import uvicorn                                     # noqa: E402


def _port():
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    p = so.getsockname()[1]
    so.close()
    return p


port = _port()
server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
threading.Thread(target=server.run, daemon=True).start()
for _ in range(150):
    if server.started:
        break
    time.sleep(0.1)
B = f"http://127.0.0.1:{port}"
pw_ctx = br = None
if PW_BOR and server.started:
    pw_ctx = sync_playwright().start()
    _exe = None
    for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*", "chrome-linux", "chrome"))):
        _exe = _yol
    try:
        br = pw_ctx.chromium.launch(executable_path=_exe) if _exe else pw_ctx.chromium.launch()
    except Exception as _e:                # noqa: BLE001
        br = None
        _pw_x = f"{type(_e).__name__}: {_e}"
check("B1 lokal server va Chromium", bool(server.started and br), _pw_x)
JS_XATO, AMAL_XATO, TASHQI = [], [], []


def kontekst(w=1280, h=900, tel=False, user=ADMIN):
    ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, is_mobile=tel, has_touch=tel,
                         timezone_id="Asia/Tashkent", locale="uz-UZ")

    def _yonalish(route):
        TASHQI.append(route.request.url)
        return route.fulfill(status=204, body="")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), _yonalish)
    pg = ctx.new_page()
    pg.set_default_timeout(8000)
    pg.on("pageerror", lambda e: JS_XATO.append((w, str(e)[:200])))
    try:
        pg.goto(B + "/login")
        pg.fill("input[name=username]", user)
        pg.fill("input[name=password]", PAROL)
        pg.press("input[name=password]", "Enter")
        pg.wait_for_load_state("networkidle")
    except Exception as ex:                # noqa: BLE001
        AMAL_XATO.append(("login", f"{type(ex).__name__}: {str(ex)[:160]}"))
    return ctx, pg


def jsq(pg, kod, arg=None):
    try:
        return pg.evaluate(kod, arg) if arg is not None else pg.evaluate(kod)
    except Exception as ex:                # noqa: BLE001
        return {"js_xato": f"{type(ex).__name__}: {str(ex)[:300]}"}


def qr_oqi(pg, svg):
    """SVG ni brauzerda chizib (oq fon, 4x), PNG ni OpenCV bilan o'qiydi → matn yoki None."""
    if not (CV and svg):
        return None
    try:
        _katta = re.sub(r'width="\d+" height="\d+"', 'width="440" height="440"', svg, count=1)
        pg.set_content('<html><body style="margin:0;background:#fff"><div id="q" style="display:inline-block;padding:20px;background:#fff">'
                       + _katta + '</div></body></html>')
        png = pg.locator("#q").screenshot()
        img = cv2.imdecode(_np.frombuffer(png, _np.uint8), cv2.IMREAD_COLOR)
        matn, _nuq, _ = cv2.QRCodeDetector().detectAndDecode(img)
        return matn or None
    except Exception as ex:                # noqa: BLE001
        AMAL_XATO.append(("qr_oqi", f"{type(ex).__name__}: {str(ex)[:160]}"))
        return None


if br:
    CTX, PG = kontekst()
    _qa, _qbeg, _qb = qr_oqi(PG, QR_SVG["a"]), qr_oqi(PG, QR_SVG["begona"]), qr_oqi(PG, QR_SVG["b"])
    check(f"Q2 QR O'QILDI: «https://web-sinov.up.railway.app/hodim?k={KOD.get(1)}»; begona manzil (`javascript:`) — QABUL QILINMAYDI "
          f"(so'rov manzili); B korxona admini — o'z kodi ({KOD.get(2)})",
          _qa == f"https://web-sinov.up.railway.app/hodim?k={KOD.get(1)}" and (_qbeg or "").endswith(f"/hodim?k={KOD.get(1)}")
          and not (_qbeg or "").startswith("javascript") and _qb == f"https://web-sinov.up.railway.app/hodim?k={KOD.get(2)}", [_qa, _qbeg, _qb])

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("P. Chop etish sahifasi")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    try:
        PG.goto(B + "/users/hodim-qr?manzil=" + B.replace(":", "%3A").replace("/", "%2F"), wait_until="networkidle")
    except Exception as ex:                # noqa: BLE001
        AMAL_XATO.append(("chop", str(ex)[:160]))
    _p = jsq(PG, """() => ({kod: document.getElementById('korxonaKodi')?.textContent.trim(), manzil: document.getElementById('kirishManzili')?.textContent.trim(),
        svg: !!document.querySelector('#qrRasm svg'), menyu: !!document.querySelector('.sidebar, nav, .nav-item'), yoriqnoma: document.querySelectorAll('ol li').length,
        sarlavha: document.title})""")
    _psvg = jsq(PG, "() => document.querySelector('#qrRasm').innerHTML")
    _pqr = qr_oqi(PG, _psvg if isinstance(_psvg, str) else "")
    check("P1 `/users/hodim-qr`: QR (o'qiladi — manzil + kod), korxona kodi katta, manzil, 3 bandli yo'riqnoma; menyu / ro'yxatlar YO'Q",
          isinstance(_p, dict) and _p.get("kod") == KOD.get(1) and _p.get("manzil") == f"{B}/hodim?k={KOD.get(1)}" and _p.get("svg")
          and not _p.get("menyu") and _p.get("yoriqnoma") == 3 and _pqr == f"{B}/hodim?k={KOD.get(1)}", [_p, _pqr])
    try:
        PG.goto(B + "/users/hodim-qr", wait_until="networkidle")
        PG.emulate_media(media="print")
        _pp = jsq(PG, """() => ({tugmalar: getComputedStyle(document.querySelector('.tugmalar')).display,
            qr: getComputedStyle(document.getElementById('qrRasm')).display, kod: getComputedStyle(document.getElementById('korxonaKodi')).display})""")
        PG.emulate_media(media="screen")
    except Exception as ex:                # noqa: BLE001
        _pp = {"xato": str(ex)[:160]}
    check("P2 chop etishda (print) — tugmalar YASHIRIN, QR va kod ko'rinadi", isinstance(_pp, dict) and _pp.get("tugmalar") == "none"
          and _pp.get("qr") not in (None, "none") and _pp.get("kod") not in (None, "none"), _pp)

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("U. Foydalanuvchilar — QR oynasi; KPI — «Panel kirishi»")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    TASHQI.clear()
    try:
        PG.goto(B + "/users", wait_until="networkidle")
        PG.click("text=QR kodni ko'rsatish")
        PG.wait_for_function("() => document.getElementById('hodimQrKod').textContent !== '—' && document.getElementById('hodimQrImg').complete", timeout=6000)
    except Exception as ex:                # noqa: BLE001
        AMAL_XATO.append(("users qr", str(ex)[:160]))
    _u = jsq(PG, """() => { const i = document.getElementById('hodimQrImg'); return {src: i.getAttribute('src'), w: i.naturalWidth,
        kod: document.getElementById('hodimQrKod').textContent, url: document.getElementById('hodimQrUrl').textContent}; }""")
    check("U1 QR oynasi: rasm o'z serverimizdan (`/api/hodim-qr.svg`, yuklandi), begona saytga so'rov YO'Q; korxona kodi va manzil `?k=KOD` bilan",
          isinstance(_u, dict) and (_u.get("src") or "").startswith("/api/hodim-qr.svg?manzil=") and _u.get("w", 0) > 0
          and _u.get("kod") == KOD.get(1) and _u.get("url") == f"{B}/hodim?k={KOD.get(1)}"
          and not [t for t in TASHQI if "qrserver" in t], [_u, TASHQI[:3]])
    try:
        with PG.context.expect_page(timeout=6000) as _yangi:
            PG.click("#hodimQrModal button:has-text('Chop etish')")
        _yp = _yangi.value
        _yp.wait_for_load_state("networkidle")
        _yurl = _yp.url
        _ykod = _yp.evaluate("() => document.getElementById('korxonaKodi')?.textContent.trim()")
        _yp.close()
    except Exception as ex:                # noqa: BLE001
        _yurl, _ykod = None, None
        AMAL_XATO.append(("chop tugma", str(ex)[:160]))
    check("U2 «Chop etish» — YANGI oynada `/users/hodim-qr` (faqat QR va yo'riqnoma; ilgari butun sahifa chop etilardi)",
          (_yurl or "").startswith(B + "/users/hodim-qr?manzil=") and _ykod == KOD.get(1), (_yurl, _ykod))
    try:
        PG.goto(B + "/kpi", wait_until="networkidle")
        PG.evaluate("() => openPanelAccessModal(1, 'Hodim Bir', '+998901112233')")
        PG.wait_for_function("() => document.getElementById('pa-korxona-kod').textContent !== '—'", timeout=6000)
    except Exception as ex:                # noqa: BLE001
        AMAL_XATO.append(("kpi", str(ex)[:160]))
    _k = jsq(PG, """() => ({kod: document.getElementById('pa-korxona-kod')?.textContent, manzil: document.getElementById('pa-kirish-manzil')?.textContent,
        qr: document.getElementById('pa-qr-havola')?.getAttribute('href')})""")
    check("U3 KPI «Panel kirishi» oynasida korxona kodi, kirish manzili (`?k=KOD`) va «QR kod (chop etish)» havolasi",
          isinstance(_k, dict) and _k.get("kod") == KOD.get(1) and _k.get("manzil") == f"{B}/hodim?k={KOD.get(1)}"
          and (_k.get("qr") or "").startswith("/users/hodim-qr?manzil="), _k)
    CTX.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("T. Telefon 390 px")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    CTX, PG = kontekst(390, 844, True)
    try:
        PG.goto(B + "/users/hodim-qr", wait_until="networkidle")
    except Exception as ex:                # noqa: BLE001
        AMAL_XATO.append(("tel chop", str(ex)[:160]))
    _t = jsq(PG, """() => { const vw = document.documentElement.clientWidth; const q = document.querySelector('#qrRasm').getBoundingClientRect();
        return {vw, sahifa: document.documentElement.scrollWidth, ql: Math.round(q.left), qr: Math.round(q.right),
                tugma: Math.round(document.querySelector('.tugmalar button').getBoundingClientRect().height)}; }""")
    try:
        PG.goto(B + "/hodim/login?k=" + KOD.get(1, ""), wait_until="networkidle")
    except Exception as ex:                # noqa: BLE001
        AMAL_XATO.append(("tel kirish", str(ex)[:160]))
    _t2 = jsq(PG, "() => document.querySelector('input[name=korxona]')?.value")
    check("T1 390 px: chop etish sahifasi ekranga sig'adi (QR ekranda, sahifa kengaymaydi, tugma ≥ 44 px); telefondan QR orqali "
          "ochilgan kirish sahifasida kod yozilgan",
          isinstance(_t, dict) and "vw" in _t and _t["sahifa"] <= _t["vw"] and _t["ql"] >= 0 and _t["qr"] <= _t["vw"] and _t["tugma"] >= 44
          and _t2 == KOD.get(1), [_t, _t2])
    CTX.close()
if br:
    br.close()
if pw_ctx:
    pw_ctx.stop()
server.should_exit = True

section("X. Xatolar")
check("X1 brauzerda JS xatosi (pageerror) yo'q", not JS_XATO, JS_XATO[:5])
check("X2 brauzer amallari bajarildi", not AMAL_XATO, AMAL_XATO[:5])

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
