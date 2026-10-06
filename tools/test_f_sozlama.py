#!/usr/bin/env python3
"""
test_f_sozlama.py — kech120, F BOSQICH 5-qism 3-bo'lagi (USTALAR, MENYU, KIRISH, SOZLAMALAR — audit G6-16, G6-18, G6-20, G6-22, G6-24).

NIMA UCHUN KERAK (audit kech114; 2026-10-01 da JORIY kodda qayta tekshirildi — work/f/tekshiruv_kech120.md):
  G6-16  «Ustalar» sahifasida telefon formati tekshirilmaydi (server ham) — «abcdefg» saqlanadi; xabar «'phone' kamida 7 belgidan …»;
         nofaol qilish rad etilsa — umumiy xabar.
  G6-18  Menyu: ostida band yo'q «Asosiy» sarlavhasi; «Hisobot» ostida «Xarajat qo'shish», «Qaytarishlar», «Ustalar»; admin «/ustalar» da
         hech bir band belgilanmaydi; Moliyachi «/kunlik-xarajat» da — ham.
  G6-20  Hodim kirishi: xatoda telefon tozalanadi, keyin nima qilish aytilmaydi; namuna kesiladi; brend rangi ko'k.
  G6-22  Korxona sozlamalari «Tizim jurnallari» ning 4-yorlig'ida; `.input-field` uslubsiz; «Choose File»; «Blok har doim yoqiq» noto'g'ri;
         Telegram matni ziddiyatli; «MRP».
  G6-24  Kirish sahifasida «Parolni unutdingizmi?» yo'q; telefonda dastur nomi yo'q; «03 MOLIYA» rasm ustida o'qilmaydi.
BO'LIMLAR: S — statik; A — API; R — server chizgan sahifalar (menyu — har rol); B — HAQIQIY Chromium.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 136) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` + Chromium (B).
ISHLATISH: python3 tools/test_f_sozlama.py
"""
import os
import re
import io
import sys
import glob
import time
import uuid
import socket
import tempfile
import threading
import contextlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "f_sozlama_test"
_T = tempfile.mkdtemp(prefix="fsoz_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'f_sozlama_test.db')}"
os.environ.pop("TENANT_FILTER", None)

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Master                # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
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
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def oqi(yol):
    try:
        with open(os.path.join(ROOT, yol), encoding="utf-8") as f:
            return f.read()
    except Exception:                      # noqa: BLE001
        return ""


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return r.text[:300]


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
CRUD = oqi("crud.py")
MAIN = oqi("main.py")
BASE = oqi("templates/base.html")
USTA = oqi("templates/masters_manage.html")
HL = oqi("templates/hodim_login.html")
LG = oqi("templates/login.html")
LOGS = oqi("templates/logs.html")
CSS = oqi("static/style.css")
check("S1 server: usta telefoni qoidasi (`usta_telefoni_xatosi` — yaratish va tahrirda), xabarda maydon nomi o'zbekcha; Ustalar sahifasi — "
      "o'sha qoida, server sababi, nofaol qilish rad sababi", "def usta_telefoni_xatosi(telefon):" in CRUD
      and CRUD.count("usta_telefoni_xatosi(toza.get(\"phone\"))") >= 4 and "raise ValueError(f\"'{key}' kamida" not in CRUD.split("def _clean_create")[1][:1500]
      and "raqam.length < 7 || raqam.length > 15" in USTA and "Nofaol qilishda xato yuz berdi. Iltimos, qayta urinib ko'ring.\");" not in USTA
      and "await serverXatoSababi(res, \"Nofaol qilishda" in USTA and "xatoSababi(e, 'Xato yuz berdi')" in USTA)
check("S2 menyu: «Asosiy» — shartli, «Kundalik ish» guruhi, admin «/ustalar» va Moliyachi «/kunlik-xarajat» belgisi, «Sozlamalar» bandi",
      "{% if m_bosh or m_loyiha or m_buyurtma %}\n      <div class=\"nav-label\">Asosiy</div>" in BASE and '<div class="nav-label">Kundalik ish</div>' in BASE
      and "(active_page == 'ustalar' and not m_usta)" in BASE and "(active_page == 'kunlik_xarajat' and not m_kunlik)" in BASE
      and '<a href="/sozlamalar"' in BASE)
check("S3 hodim kirishi: telefon saqlanadi, brend — oltin; kirish sahifasi: «Parolni unutdingizmi?», telefonda nom; Sozlamalar — alohida "
      "sahifa, `.input-field` umumiy, o'zbekcha fayl tanlash, ziddiyatsiz matnlar", 'value="{{ telefon or \'\' }}"' in HL and "m-2563eb" not in HL
      and "#2563EB" not in HL and "Parolni unutdingizmi?" in LG and 'class="mobil-brend"' in LG and '@app.get("/sozlamalar"' in MAIN
      and ".input-field {" in CSS and ">Fayl tanlash</label>" in LOGS and "(Profil, Panel, Donali, Blok)" not in LOGS
      and "MRP mahsulot turi, hodim" not in LOGS)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. API")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
PAROL = "Parol123!"
_n = uuid.uuid4().hex[:4]
FOYD = {"admin": (f"fsoz_admin_{_n}", UserRole.ADMIN), "menejer": (f"fsoz_men_{_n}", UserRole.MANAGER),
        "omborchi": (f"fsoz_omb_{_n}", UserRole.WAREHOUSE), "moliyachi": (f"fsoz_mol_{_n}", UserRole.ACCOUNTANT)}
_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    for _k, (_u, _r) in FOYD.items():
        auth.create_user(_db, _u, PAROL, _r, f"FS {_k}", company_id=1)
_mst = Master(company_id=1, name=f"FS Usta {_n}", phone=f"+99890{_n}11")
_db.add(_mst)
_db.commit()
MID = _mst.id
_kod = (_db.query(Company).filter(Company.id == 1).first().code or "")
_db.close()


def mijoz(rol):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    st = c.post("/login", data={"username": FOYD[rol][0], "password": PAROL}, follow_redirects=False).status_code
    return c, st


C, _l = mijoz("admin")
_a1 = C.post("/api/masters", json={"name": f"FS Harf {_n}", "phone": "abcdefg"})
_a2 = C.post("/api/masters", json={"name": f"FS Qisqa {_n}", "phone": "12345"})
_a3 = C.post("/api/masters", json={"name": f"FS To'g'ri {_n}", "phone": f"+998 90 {str(int(_n, 16) % 1000).zfill(3)} 45 67"})
_a4 = C.put(f"/api/masters/{MID}", json={"phone": "tel: 9012"})
_a5 = C.post("/api/masters", json={"name": "F", "phone": "+998901234567"})
_d = lambda r: str((js(r) or {}).get("detail") if isinstance(js(r), dict) else js(r))     # noqa: E731
check("A1 usta telefoni: «abcdefg» — 400 sababi bilan (ilgari SAQLANARDI), «12345» — ««Telefon» kamida 7 …» (ilgari «'phone' …»), "
      "to'g'ri «+998 90 … 45 67» — 200; tahrirda noto'g'ri — 400; qisqa ism — «Ism»", _l == 302 and _a1.status_code == 400
      and "Telefon raqami noto'g'ri" in _d(_a1) and _a2.status_code == 400 and "«Telefon» kamida 7" in _d(_a2) and "'phone'" not in _d(_a2)
      and _a3.status_code == 200 and _a4.status_code == 400 and "Telefon raqami noto'g'ri" in _d(_a4)
      and _a5.status_code == 400 and "«Ism» kamida 2" in _d(_a5),
      (_a1.status_code, _d(_a1), _a2.status_code, _d(_a2), _a3.status_code, _d(_a3), _a4.status_code, _d(_a4), _a5.status_code, _d(_a5)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. Server chizgan sahifalar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def menyu(html):
    """Yon menyu: [(turi, matn, faolmi)] — `nav-label` va `nav-item`."""
    nav = html.split("<nav", 1)[1].split("</nav>", 1)[0] if "<nav" in html else ""
    natija = []
    for m in re.finditer(r'<div class="nav-label">([^<]*)</div>|<a href="([^"]*)" class="nav-item ?(active)?\s*">\s*<i[^>]*></i>\s*<span class="n-txt">([^<]*)</span>', nav):
        if m.group(1) is not None:
            natija.append(("sarlavha", m.group(1).strip(), False))
        else:
            natija.append(("band", m.group(4).strip(), bool(m.group(3)), m.group(2)))
    return natija


def bosh_sarlavhalar(mn):
    """Ostida birorta band bo'lmagan sarlavhalar."""
    return [x[1] for i, x in enumerate(mn) if x[0] == "sarlavha" and (i + 1 >= len(mn) or mn[i + 1][0] == "sarlavha")]


_mn = {}
for _rol in FOYD:
    _c, _st = mijoz(_rol)
    _sah = "/" if _rol != "omborchi" else "/inventory"
    _r = _c.get(_sah)
    _mn[_rol] = menyu(_r.text) if _r.status_code == 200 else []
check("R1 har rolda: ostida bandi yo'q menyu sarlavhasi YO'Q (Omborchida bo'sh «Asosiy» edi)",
      all(_mn[r] and not bosh_sarlavhalar(_mn[r]) for r in _mn), {r: bosh_sarlavhalar(_mn[r]) for r in _mn})


def guruh(mn, nom):
    out, ich = [], False
    for x in mn:
        if x[0] == "sarlavha":
            ich = x[1] == nom
        elif ich:
            out.append(x[1])
    return out


_mk = guruh(_mn["menejer"], "Kundalik ish")
_mh = guruh(_mn["menejer"], "Hisobot")
check("R2 Menejer: «Xarajat qo'shish» / «Qaytarishlar» / «Ustalar» — «Kundalik ish» guruhida, «Hisobot» ostida emas",
      _mk and set(_mk) <= {"Xarajat qo'shish", "Qaytarishlar", "Ustalar"} and not (set(_mh) & {"Xarajat qo'shish", "Qaytarishlar", "Ustalar"}),
      (_mk, _mh, _mn["menejer"]))
_ua = menyu(C.get("/ustalar").text)
_cm, _ = mijoz("moliyachi")
_km = _cm.get("/kunlik-xarajat")
_kmm = menyu(_km.text) if _km.status_code == 200 else []
check("R3 belgilangan band: admin «/ustalar» — «Ustalar KPI / Hodimlar»; Moliyachi «/kunlik-xarajat» — «Moliya» (ilgari hech biri)",
      [x[1] for x in _ua if x[0] == "band" and x[2]] == ["Ustalar KPI / Hodimlar"]
      and (_km.status_code != 200 or [x[1] for x in _kmm if x[0] == "band" and x[2]] == ["Moliya"]),
      ([x for x in _ua if x[0] == "band" and x[2]], _km.status_code, [x for x in _kmm if x[0] == "band" and x[2]]))
_s = C.get("/sozlamalar")
_lr = C.get("/logs?tab=settings", follow_redirects=False)
_lg = C.get("/logs").text
_sm = menyu(_s.text) if _s.status_code == 200 else []
check("R4 «/sozlamalar» — alohida sahifa «Korxona sozlamalari» (menyuda «Sozlamalar» belgilangan, jurnallar yorliqlari yashirin); eski "
      "`/logs?tab=settings` → /sozlamalar; jurnallarda — havola", _s.status_code == 200 and "Korxona sozlamalari" in _s.text
      and [x[1] for x in _sm if x[0] == "band" and x[2]] == ["Sozlamalar"] and 'id="tab-settings"' in _s.text
      and _lr.status_code == 302 and _lr.headers.get("location") == "/sozlamalar" and 'href="/sozlamalar"' in _lg,
      (_s.status_code, [x for x in _sm if x[0] == "band" and x[2]], _lr.status_code, _lr.headers.get("location")))
_h = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False).post(
    "/hodim/login", data={"phone": "+998 90 111 22 33", "pin": "0000", "korxona": _kod})
import html as _html                               # noqa: E402
check("R5 hodim kirishi xatosi: telefon maydonda QOLADI (ilgari tozalanardi), PIN — bo'sh; xabarda nima qilish («administratoridan "
      "so'rang»)", _h.status_code == 200 and 'value="+998 90 111 22 33"' in _h.text and "administratoridan so'rang" in _html.unescape(_h.text)
      and re.search(r'name="pin"[^>]*value=', _h.text) is None, _h.text[_h.text.find("error-box"):][:300])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Brauzer (HAQIQIY Chromium)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
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
check("B0 lokal server va Chromium", bool(server.started and br), _pw_x)
JS_XATO, SOROV = [], []


def kontekst(user=None, w=1440, h=900):
    ctx = br.new_context(viewport={"width": w, "height": h}, timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
    pg = ctx.new_page()
    pg.set_default_timeout(10000)
    pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
    pg.on("request", lambda q: SOROV.append((q.method, q.url.replace(B, ""))) if "/api/" in q.url else None)
    if user:
        pg.goto(B + "/login")
        pg.fill("input[name=username]", user)
        pg.fill("input[name=password]", PAROL)
        pg.press("input[name=password]", "Enter")
        pg.wait_for_load_state("networkidle")
    return ctx, pg


if br:
    ctx, pg = kontekst(FOYD["admin"][0])
    try:
        pg.goto(B + "/sozlamalar", wait_until="networkidle")
        pg.wait_for_timeout(500)
        _sz = pg.evaluate("""() => { const i = document.getElementById('co-name'), f = document.getElementById('co-logo-file');
            const lb = document.querySelector('label[for="co-logo-file"]'); const cs = getComputedStyle(i);
            return {chegara: cs.borderTopWidth + ' ' + cs.borderTopStyle, radius: cs.borderTopLeftRadius, padding: cs.paddingLeft, fayl: getComputedStyle(f).display,
                    tugma: lb ? lb.textContent.trim() : null, nomi: document.getElementById('co-logo-nomi').textContent,
                    tabbar: getComputedStyle(document.querySelector('.tab-bar')).display,
                    korin: getComputedStyle(document.getElementById('tab-settings')).display}; }""")
        # kech123 (zip 139 — U-13, MOSLANDI): `.input-field` — yagona maydon qoidasi (`.maydon` bilan bir: 12 px ichki joy, 8 px burchak)
        check("B1 Sozlamalar sahifasi: maydonlar umumiy uslubda (tekis chegara, 8 px burchak, 12 px ichki joy — ilgari brauzer standarti), fayl — «Fayl tanlash» / "
              "«Fayl tanlanmagan» (inglizcha «Choose File» yo'q), jurnallar yorliqlari ko'rinmaydi", _sz["chegara"] in ("1px solid", "1.5px solid")
              and _sz["radius"] == "8px" and _sz["padding"] == "12px" and _sz["fayl"] == "none" and _sz["tugma"] == "Fayl tanlash"
              and _sz["nomi"] == "Fayl tanlanmagan" and _sz["tabbar"] == "none" and _sz["korin"] == "block", _sz)
        pg.goto(B + "/ustalar", wait_until="networkidle")
        pg.wait_for_timeout(500)
        pg.evaluate("() => { const b = [...document.querySelectorAll('button')].find(x => /Yangi usta/.test(x.textContent)); if (b) b.click(); else openMasterModal(); }")
        pg.wait_for_timeout(300)
        pg.fill("#m-name", f"FS Brauzer {_n}")
        pg.fill("#m-phone", "abcdefg")
        del SOROV[:]
        pg.evaluate("() => saveMaster()")
        pg.wait_for_timeout(500)
        _x1 = pg.evaluate("() => document.getElementById('master-error').textContent")
        _p1 = [u for m, u in SOROV if m == "POST" and u.startswith("/api/masters")]
        check("B2 Ustalar sahifasi: «abcdefg» — oynada «Telefon raqami noto'g'ri …», so'rov YUBORILMAYDI (ilgari saqlanardi)",
              "Telefon raqami noto'g'ri" in _x1 and not _p1, (_x1, _p1))
        pg.route(re.compile(r".*/api/masters/\d+$"), lambda r: r.fulfill(status=409, content_type="application/json",
                                                                        body='{"detail": "Sinov sababi: ochiq buyurtmasi bor"}')
                 if r.request.method == "DELETE" else r.continue_())
        pg.evaluate(f"() => {{ window.customConfirm = async () => true; window.__d = deactivateMaster({MID}, 'FS'); }}")
        pg.wait_for_timeout(700)
        _x2 = pg.evaluate("() => [...document.querySelectorAll('body *')].filter(e => e.children.length === 0 && /Sinov sababi/.test(e.textContent)).map(e => e.textContent)")
        check("B3 nofaol qilish rad etilsa — server SABABI ko'rsatiladi (ilgari umumiy «Nofaol qilishda xato yuz berdi»)",
              any("Sinov sababi: ochiq buyurtmasi bor" in x for x in _x2), _x2)
    except Exception as _e:                # noqa: BLE001
        check("B! admin ssenariysi", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    ctx, pg = kontekst(w=390, h=844)
    try:
        pg.goto(B + "/login", wait_until="networkidle")
        _lt = pg.evaluate("""() => { const m = document.querySelector('.mobil-brend'); const u = document.getElementById('parolUnutdim');
            return {nom: m ? getComputedStyle(m).display : null, unut: (u && u.offsetHeight > 0 && getComputedStyle(u).display !== 'none') ? u.innerText : null}; }""")
        pg.set_viewport_size({"width": 1440, "height": 900})
        pg.wait_for_timeout(200)
        _lk = pg.evaluate("""() => { const s = document.querySelector('.side-stats'); const l = document.querySelector('.side-stat .l');
            return {fon: s ? getComputedStyle(s).backgroundColor : null, rang: l ? getComputedStyle(l).color : null,
                    nom: getComputedStyle(document.querySelector('.mobil-brend')).display}; }""")
        check("B4 kirish sahifasi: «Parolni unutdingizmi? … administratoriga …»; telefonda (390) dastur nomi tepada, kompyuterda yashirin; "
              "pastki yozuvlar qoramtir fonda, och rangda (ilgari rasm ustida o'qilmasdi)", _lt["nom"] == "flex" and _lt["unut"]
              and "Parolni unutdingizmi?" in _lt["unut"] and "administratoriga" in _lt["unut"] and _lk["nom"] == "none"
              and _lk["fon"] == "rgba(17, 17, 17, 0.62)" and _lk["rang"] == "rgb(229, 231, 235)", (_lt, _lk))
        pg.set_viewport_size({"width": 390, "height": 844})
        pg.goto(B + "/hodim/login", wait_until="networkidle")
        _hk = pg.evaluate("""() => { const k = document.querySelector('input[name=korxona]'); const c = document.createElement('canvas').getContext('2d');
            c.font = getComputedStyle(k).font; const cs = getComputedStyle(k);
            return {ph: k.placeholder, sigadi: c.measureText(k.placeholder).width <= k.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight),
                    brend: getComputedStyle(document.querySelector('.h-logo .name span')).color}; }""")
        check("B5 hodim kirishi 390 px: korxona kodi namunasi to'liq sig'adi (ilgari «… bo'sh qo…» kesilardi); brend rangi oltin (ko'k emas)",
              _hk["sigadi"] and _hk["brend"] != "rgb(37, 99, 235)", _hk)
    except Exception as _e:                # noqa: BLE001
        check("B! kirish sahifalari", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    check("B6 JS xatosi yo'q", not JS_XATO, JS_XATO)
if br:
    br.close()
if pw_ctx:
    pw_ctx.stop()
server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
