#!/usr/bin/env python3
"""
test_narx_yaxlit269.py — kech204 (zip 269): buyurtma oynasida 1 m / 1 dona narxini yaxlitlash (egasi so'rovi 07.11 14:28; QARORLARI:
qadam Sozlamalarda tanlanadi — 100 / 500 / 1 000, standart 500; yo'nalish — faqat «+» (doim yuqoriga) va «−» (doim pastga)).

NIMA UCHUN KERAK
  Formula chiqargan 1 m narxi (masalan 12 340 so'm) «yumaloq» emas edi — korxona o'z odatiga ko'ra yaxlitlay olmasdi. Endi Sozlamalarda
  «🔢 Narxni yaxlitlash»: «+» — 12 340 → 12 500, 12 650 → 13 000; «−» — 12 340 → 12 000, 12 650 → 12 500. Profil, Panel, Donalik (yangi
  usul) va Blokda ishlaydi; tayyor mahsulotdan olingan / qo'lda yozilgan narxga tegilmaydi. Qoida buyurtma (va taklif) bilan birga
  saqlanadi — sozlama keyin o'zgarsa ham eski buyurtma tahrirda o'z qoidasi bilan hisoblanadi (narx jimgina o'zgarmaydi).
BO'LIMLAR
  S — sozlama API: standart (o'chiq, 500), saqlash, noto'g'ri qiymat (400, hech narsa saqlanmaydi), jurnal, ruxsat, korxonalar ajralgan.
  B — server: buyurtmaga qoida saqlanadi / qaytadi, noto'g'ri qoida — 422, tahrir qoidani o'zgartirmaydi, taklif → rasmiylashtirish,
      ustun bor, Buyurtmalar sahifasi joriy qoidani beradi.
  U — HAQIQIY brauzer (Playwright, SQLite / TF1): Sozlamalar bo'limi; formada 4 tur «+» / «−» / 100 / 1 000, qoplama, qo'lda narx,
      tayyor narx yaxlitlanmaydi; saqlash → server; sozlama o'zgargach tahrir — o'z qoidasi; eski buyurtma — yaxlitlanmaydi; JS xatosi yo'q.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` (U bo'limi faqat SQLite / TF1 da).
Asl kodga (77fbc14 — zip 268) qarshi YIQILADI, QULAMAYDI.
ISHLATISH: python3 tools/test_narx_yaxlit269.py
"""
import os
import io
import sys
import time
import tempfile
import datetime
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "yaxlit269_test"
_T = tempfile.mkdtemp(prefix="k269_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k269.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "ADMIN_PASSWORD", "RESET_ADMIN_PASSWORD"):
    os.environ.pop(_k, None)

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
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


def yaqin(a, b, eps=0.005):
    try:
        return abs(float(a) - float(b)) <= eps
    except (TypeError, ValueError):
        return False


_MIG = io.StringIO()
with contextlib.redirect_stdout(_MIG):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal, engine          # noqa: E402
from models import (UserRole, Inventory, Project, Order, OrderItem, OrderType, OrderStatus, ActivityLog,  # noqa: E402
                    CompanySetting)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from sqlalchemy import inspect as _sa_inspect      # noqa: E402

YANGI = hasattr(Order, "narx_yaxlit")
PAROL = "Kuchli-Sinov-Parol-269"
s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="K269 B korxona"))
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k269_a", PAROL, UserRole.ADMIN, "K269 Admin", company_id=1)
    auth.create_user(s, "k269_m", PAROL, UserRole.MANAGER, "K269 Menejer", company_id=1)
    auth.create_user(s, "k269_b", PAROL, UserRole.ADMIN, "K269 B Admin", company_id=2)
PENO = Inventory(company_id=1, item_name="K269 Penoplast 15", unit="blok", stock_quantity=1_000, price_per_unit=500_000,
                 volume_per_unit=2.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
P1 = Project(company_id=1, client_name="Sardor K269", project_name="Andijon K269", client_phone="+998901112269", total_budget=0,
             total_paid=0)
s.add_all([PENO, P1])
s.commit()
ID = {"PENO": PENO.id, "P1": P1.id}
s.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    return c


A, M, B = mijoz("k269_a"), mijoz("k269_m"), mijoz("k269_b")


def js(r):
    try:
        return r.json()
    except Exception:                   # noqa: BLE001
        return {}


def sozla(c, yon, qadam):
    return c.put("/api/settings/narx-yaxlit", data={"yonalish": yon, "qadam": str(qadam)})


def sozlama(cid, kalit):
    _s = SessionLocal()
    try:
        r = _s.query(CompanySetting).filter(CompanySetting.company_id == cid, CompanySetting.key == kalit).first()
        return None if r is None else r.value
    finally:
        _s.close()


def jurnal_soni(cid):
    _s = SessionLocal()
    try:
        return _s.query(ActivityLog).filter(ActivityLog.company_id == cid, ActivityLog.entity_type == "company_settings").count()
    finally:
        _s.close()


def profil(nom, narx, l=3.0):
    return {"name": nom, "category": "profil", "width": 10, "thickness": 10, "length": l, "quantity": 1, "unit_price": narx * l,
            "is_coated": False, "penoplast_id": ID["PENO"]}


def buyurtma(items, **kw):
    b = {"project_id": ID["P1"], "order_type": "product", "items": items, "base_price": 2_468_000,
         "deadline": (datetime.date.today() + datetime.timedelta(days=10)).isoformat() + "T00:00:00"}
    b.update(kw)
    return b


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Sozlama API — «🔢 Narxni yaxlitlash»")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_g = js(A.get("/api/settings/narx-yaxlit"))
check("S1 standart: o'chiq, qadam 500, qoida bo'sh, qadamlar 100 / 500 / 1 000, matn «o'chiq» (asl: marshrut yo'q)",
      _g.get("yonalish") == "" and _g.get("qadam") == 500 and _g.get("qoida") == "" and _g.get("qadamlar") == [100, 500, 1000]
      and _g.get("matn") == "o'chiq", _g)
_j0 = jurnal_soni(1)
_r = sozla(A, "+", 500)
check("S2 «+», 500 — 200; qoida «+500»; matn «yuqoriga, 500 so'm qadam bilan»; bazada ikki kalit", _r.status_code == 200
      and js(_r).get("qoida") == "+500" and js(_r).get("matn") == "yuqoriga, 500 so'm qadam bilan"
      and sozlama(1, "narx_yaxlit_yonalish") == "+" and sozlama(1, "narx_yaxlit_qadam") == "500", (_r.status_code, _r.text[:200]))
check("S3 o'zgarish «Audit jurnali» ga BITTA yozuv", jurnal_soni(1) == _j0 + 1, (jurnal_soni(1), _j0))
_r = sozla(A, "+", 500)
check("S4 o'zgarishsiz saqlash — jurnalga yozilmaydi", _r.status_code == 200 and jurnal_soni(1) == _j0 + 1, jurnal_soni(1))
for _yon, _q, _nima in (("x", 500, "noma'lum yo'nalish"), ("++", 500, "ikki belgi"), ("+", 250, "qadam 250"), ("+", "abc", "qadam matn"),
                        ("-", "", "qadam bo'sh"), ("+", "500.0", "qadam kasr ko'rinishi"), ("+", -500, "manfiy qadam")):
    _r = sozla(A, _yon, _q)
    check(f"S5 rad: {_nima} — 400, sozlama o'zgarmadi", _r.status_code == 400 and js(A.get("/api/settings/narx-yaxlit")).get("qoida") == "+500",
          (_r.status_code, _r.text[:160]))
_r = sozla(A, "", 1000)
_g = js(A.get("/api/settings/narx-yaxlit"))
check("S6 o'chirish — qoida bo'sh, tanlangan qadam (1 000) SAQLANADI (keyin yoqilsa o'sha)", _r.status_code == 200 and _g.get("yonalish") == ""
      and _g.get("qadam") == 1000 and _g.get("qoida") == "", _g)
_r = sozla(A, "-", 1000)
check("S7 «−», 1 000 — qoida «-1000», matn «pastga, 1 000 so'm qadam bilan»", js(_r).get("qoida") == "-1000"
      and js(_r).get("matn") == "pastga, 1 000 so'm qadam bilan", _r.text[:200])
check("S8 B korxona — o'zgarmadi (o'chiq, 500)", js(B.get("/api/settings/narx-yaxlit")).get("qoida") == ""
      and js(B.get("/api/settings/narx-yaxlit")).get("qadam") == 500, B.get("/api/settings/narx-yaxlit").text[:200])
_r = sozla(M, "+", 100)
check("S9 Menejer («Korxona sozlamalari» ruxsatisiz) — PUT 403, GET 403; sozlama o'zgarmadi", _r.status_code == 403
      and M.get("/api/settings/narx-yaxlit").status_code == 403 and js(A.get("/api/settings/narx-yaxlit")).get("qoida") == "-1000",
      (_r.status_code, M.get("/api/settings/narx-yaxlit").status_code))
_kir = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
check("S10 kirmagan — 401 (GET va PUT)", _kir.get("/api/settings/narx-yaxlit").status_code == 401
      and _kir.put("/api/settings/narx-yaxlit", data={"yonalish": "+", "qadam": "500"}).status_code == 401,
      _kir.get("/api/settings/narx-yaxlit").status_code)
# buzilgan qiymat bazada — sahifa yiqilmaydi
_s = SessionLocal()
for _k, _v in (("narx_yaxlit_yonalish", "?"), ("narx_yaxlit_qadam", "7")):
    _row = _s.query(CompanySetting).filter(CompanySetting.company_id == 2, CompanySetting.key == _k).first()
    if _row is None:
        _s.add(CompanySetting(company_id=2, key=_k, value=_v))
    else:
        _row.value = _v
_s.commit()
_s.close()
_g = js(B.get("/api/settings/narx-yaxlit"))
check("S11 bazada buzilgan qiymat («?», «7») — o'chiq, standart 500 (yiqilmaydi)", _g.get("yonalish") == "" and _g.get("qadam") == 500
      and _g.get("qoida") == "", _g)
sozla(B, "", 500)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Server — buyurtma va taklif qoidani saqlaydi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_ust = {c["name"] for c in _sa_inspect(engine).get_columns("orders")}
check("B1 `orders.narx_yaxlit` ustuni bor (migratsiya)", "narx_yaxlit" in _ust, sorted(_ust)[:5])
_r = A.post("/api/orders", json=buyurtma([profil("K269 profil yaxlit", 12_500)], narx_yaxlit="+500"))
O1 = js(_r).get("id")
_d1 = js(A.get(f"/api/orders/{O1}")) if O1 else {}
check("B2 yaratish «+500» bilan — 200, GET da narx_yaxlit «+500», narx — yuborilgani (12 500 × 3 = 37 500)", _r.status_code == 200
      and _d1.get("narx_yaxlit") == "+500" and yaqin((_d1.get("items") or [{}])[0].get("total_price"), 37_500), (_r.status_code, _r.text[:200]))
_r = A.post("/api/orders", json=buyurtma([profil("K269 profil oddiy", 12_340)]))
O2 = js(_r).get("id")
_d2 = js(A.get(f"/api/orders/{O2}")) if O2 else {}
check("B3 qoidasiz yaratish — narx_yaxlit null (eski xulq; asl kodda ham kalit yo'q emas — YANGI kodda null)", _r.status_code == 200
      and "narx_yaxlit" in _d2 and _d2.get("narx_yaxlit") is None, (_r.status_code, {k: _d2.get(k) for k in ("id", "narx_yaxlit")}))
_n0 = len(js(A.get("/api/orders")) or [])
for _q in ("+250", "500", "*500", "+500 ", "-0", "+5000", ""):
    _r = A.post("/api/orders", json=buyurtma([profil("K269 rad", 12_340)], narx_yaxlit=_q))
    # bo'sh matn ham rad (forma qoidasiz holatda `null` yuboradi — bo'sh matn yubormaydi)
    check(f"B4 noto'g'ri qoida «{_q}» — rad (422 / 400)", _r.status_code in (400, 422), (_r.status_code, _r.text[:160]))
check("B4b rad etilgan so'rovlardan buyurtma yaratilmadi", len(js(A.get("/api/orders")) or []) == _n0, (len(js(A.get("/api/orders")) or []), _n0))
_r = A.put(f"/api/orders/{O1}", json=buyurtma([profil("K269 profil yaxlit", 13_000)], narx_yaxlit="-1000"))
_d1b = js(A.get(f"/api/orders/{O1}"))
check("B5 tahrir boshqa qoida bilan — buyurtmaning qoidasi O'ZGARMADI («+500»), narx — yangisi", _r.status_code == 200
      and _d1b.get("narx_yaxlit") == "+500" and yaqin((_d1b.get("items") or [{}])[0].get("total_price"), 39_000), (_r.status_code, _r.text[:200]))
_r = A.put(f"/api/orders/{O2}", json=buyurtma([profil("K269 profil oddiy", 12_340)], narx_yaxlit="+500"))
check("B6 eski (qoidasiz) buyurtma tahriri qoida bilan — baribir null (eski buyurtma qoidasiz qoladi)", _r.status_code == 200
      and js(A.get(f"/api/orders/{O2}")).get("narx_yaxlit") is None, (_r.status_code, _r.text[:200]))
_r = A.post("/api/takliflar", json={"mijoz": "Taklif mijoz", "telefon": "+998901234567",
                                    "buyurtma": {k: v for k, v in buyurtma([profil("K269 taklif profil", 12_000)], narx_yaxlit="-500").items()
                                                 if k != "project_id"}})
T1 = (js(_r).get("taklif") or {}).get("id")
_t1 = js(A.get(f"/api/takliflar/{T1}")) if T1 else {}
check("B7 taklif «-500» bilan — taklif oynasi uchun javobda narx_yaxlit «-500»", _r.status_code == 200 and _t1.get("narx_yaxlit") == "-500",
      (_r.status_code, _r.text[:200], _t1.get("narx_yaxlit")))
_r = A.post(f"/api/takliflar/{T1}/rasmiylashtir",
            json={"loyiha_id": ID["P1"], "buyurtma": {k: v for k, v in buyurtma([profil("K269 taklif profil", 12_000)],
                                                                               narx_yaxlit=_t1.get("narx_yaxlit")).items()
                                                     if k != "project_id"}})
O3 = js(_r).get("id")
check("B8 taklif rasmiylashtirildi — buyurtmada qoida «-500» (taklifniki)", _r.status_code == 200 and O3
      and js(A.get(f"/api/orders/{O3}")).get("narx_yaxlit") == "-500", (_r.status_code, _r.text[:200]))
# eski taklif (tanasida qoida yo'q)
from models import Taklif                         # noqa: E402
import json as _json                              # noqa: E402
_s = SessionLocal()
_tk = Taklif(company_id=1, seq=999, raqam="T-0999", mijoz="Eski taklif", telefon=None, holat="yangi", jami=36_000, kelishilgan=36_000,
             tana=_json.dumps({"order_type": "product", "items": [profil("Eski taklif profil", 12_000)], "base_price": 2_400_000}),
             amal_muddati=datetime.date.today() + datetime.timedelta(days=3), yaratilgan=datetime.datetime.utcnow(), yaratgan="test")
_s.add(_tk)
_s.commit()
T_ESKI = _tk.id
_s.close()
_te = js(A.get(f"/api/takliflar/{T_ESKI}"))
check("B9 eski taklif (qoidasiz tana) — narx_yaxlit null (yaxlitlanmaydi)", "narx_yaxlit" in _te and _te.get("narx_yaxlit") is None,
      {k: _te.get(k) for k in ("id", "narx_yaxlit")})
_h = A.get("/orders").text
check("B10 Buyurtmalar sahifasi — joriy korxona qoidasi («-1000») va hisob funksiyasi bor", 'const KORXONA_NARX_YAXLIT = "-1000";' in _h
      and "function narxYaxlit(" in _h, _h[_h.find("KORXONA_NARX_YAXLIT") - 10:_h.find("KORXONA_NARX_YAXLIT") + 60] if "KORXONA_NARX_YAXLIT" in _h else "yo'q")
check("B11 B korxona sahifasi — bo'sh qoida (o'chiq)", 'const KORXONA_NARX_YAXLIT = "";' in B.get("/orders").text)
import crud                                       # noqa: E402
import tenant_context                             # noqa: E402
_s = SessionLocal()
with tenant_context.system_context(_s):
    _zx = crud.export_full_backup(_s, company_id=1)
_s.close()
_zx_or = [r for v in (_zx.values() if isinstance(_zx, dict) else []) if isinstance(v, list)
          for r in v if isinstance(r, dict) and r.get("id") == O1 and "order_number" in r]
_zx_or = _zx_or or [r for r in ((_zx.get("tables") or {}).get("orders") or []) if isinstance(r, dict) and r.get("id") == O1]
check("B13 zaxira nusxada buyurtma qoidasi bor (narx_yaxlit «+500»)", bool(_zx_or) and _zx_or[0].get("narx_yaxlit") == "+500",
      (list(_zx)[:6] if isinstance(_zx, dict) else type(_zx), _zx_or[:1]))
check("B12 Sozlamalar sahifasida «🔢 Narxni yaxlitlash» bo'limi (yo'nalish, qadam, misol, Saqlash)", all(x in A.get("/sozlamalar").text for x in (
      "🔢 Narxni yaxlitlash", 'name="yx-yon"', 'id="yx-qadam"', 'id="yx-misol"', 'id="yx-save-btn"')))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    print("  (PG rejimida UI bo'limi o'tkazib yuboriladi — SQLite / TF1 da)")
else:
    import glob
    import socket
    import threading
    import uvicorn
    from playwright.sync_api import sync_playwright
    # hamma turlar yoqiq (Blok standartda yashirin)
    A.put("/api/settings/categories", data={"codes": "profil,panel,dona,blok,loy_sotish,mrp_product", "v": "2"})
    _sk = socket.socket()
    _sk.bind(("127.0.0.1", 0))
    PORT = _sk.getsockname()[1]
    _sk.close()
    _srv = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=PORT, log_level="error", lifespan="off"))
    threading.Thread(target=_srv.run, daemon=True).start()
    while not _srv.started:
        time.sleep(0.1)
    BASE = f"http://127.0.0.1:{PORT}"
    _exe = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
    XATOLAR = []
    bosh = lambda x: str(x).replace(" ", " ").replace(" ", " ")   # noqa: E731

    # Bitta detal: yangi qator, tur, maydonlar → {perm, jami, up}. Qiymatlar `input` hodisasi bilan (forma o'zi hisoblaydi).
    DETAL_JS = """([tur, maydon, qoplama]) => {
        addItem();
        const rs = document.querySelectorAll('#items .detal'); const r = rs[rs.length - 1];
        selectTypeOpt(r.querySelector('.type-opt[data-value="' + tur + '"]'), tur);
        for (const [sel, v] of Object.entries(maydon)) {
          const e = sel.startsWith('#') ? document.querySelector(sel) : r.querySelector(sel);
          e.value = v; e.dispatchEvent(new Event('input', {bubbles: true}));
        }
        r.querySelector(qoplama ? '.coat-yes' : '.coat-no').click();   // yangi qator oldingisining qoplamasini olishi mumkin
        calculateItem(r);
        return {perm: r.querySelector('.i-perm').value, jami: r.querySelector('.i-price').value,
                up: (r.querySelector('.i-unitprice') || {}).value || ''};
    }"""

    def _ui():
        with sync_playwright() as pw:
            br = pw.chromium.launch(executable_path=_exe[-1] if _exe else None)
            ctx = br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent")
            ctx.route("**/*", lambda r: r.fulfill(status=204, body="") if not r.request.url.startswith(BASE) else r.continue_())
            pg = ctx.new_page()
            pg.set_default_timeout(10000)
            pg.on("pageerror", lambda e: XATOLAR.append(str(e)[:200]))
            pg.on("dialog", lambda d: d.accept())
            pg.goto(BASE + "/login")
            pg.fill("input[name=username]", "k269_a")
            pg.fill("input[name=password]", PAROL)
            pg.press("input[name=password]", "Enter")
            pg.wait_for_load_state("networkidle")

            # ── Sozlamalar sahifasi
            pg.goto(BASE + "/sozlamalar", wait_until="networkidle")
            pg.evaluate("() => { const d = document.querySelector('details[data-sht=\"soz-yaxlit\"]'); if (d) d.open = true; }")
            pg.wait_for_timeout(500)
            _h = pg.evaluate("""() => ({yon: (document.querySelector('input[name="yx-yon"]:checked') || {}).value,
                qadam: document.getElementById('yx-qadam').value, misol: document.getElementById('yx-misol').textContent,
                yopiq: document.getElementById('yx-save-btn').disabled,
                holat: (document.querySelector('details[data-sht="soz-yaxlit"] .sht-holat') || {}).textContent})""")
            check("U1 Sozlamalar: joriy qiymat yuklandi («−», 1 000), misol «12 340 → 12 000; 12 650 → 12 000», sarlavhada holat, «Saqlash» ochiq",
                  _h["yon"] == "-" and _h["qadam"] == "1000" and "12 340 → 12 000" in bosh(_h["misol"]) and "12 650 → 12 000" in bosh(_h["misol"])
                  and not _h["yopiq"] and "pastga" in (_h["holat"] or ""), _h)
            pg.check('input[name="yx-yon"][value="+"]')
            pg.select_option("#yx-qadam", "500")
            _m = bosh(pg.inner_text("#yx-misol"))
            pg.click("#yx-save-btn")
            pg.wait_for_timeout(700)
            _g = js(A.get("/api/settings/narx-yaxlit"))
            check("U2 «Yuqoriga (+)», 500 → misol «12 340 → 12 500; 12 650 → 13 000», «Saqlash» → serverda «+500», «✓ Saqlandi»",
                  "12 340 → 12 500" in _m and "12 650 → 13 000" in _m and _g.get("qoida") == "+500"
                  and "Saqlandi" in pg.inner_text("#yx-status"), (_m, _g, pg.inner_text("#yx-status")))
            pg.check('input[name="yx-yon"][value=""]')
            check("U3 «O'chiq» tanlansa misol — «yaxlitlanmaydi»", "yaxlitlanmaydi" in pg.inner_text("#yx-misol"), pg.inner_text("#yx-misol"))

            # ── Buyurtma formasi, «+500»
            pg.goto(BASE + "/orders", wait_until="networkidle")
            pg.evaluate("() => { localStorage.clear(); showNewForm(); document.getElementById('items').innerHTML = ''; }")
            pg.wait_for_timeout(300)
            _iz = pg.evaluate("() => { const e = document.getElementById('narx_yaxlit_izoh'); return {k: e.offsetParent !== null, t: e.textContent}; }")
            check("U4 yangi forma — izoh ko'rinadi: «yuqoriga yaxlitlanadi — 500 so'm qadam bilan»", _iz["k"]
                  and "yuqoriga" in _iz["t"] and "500" in _iz["t"], _iz)
            pg.evaluate("() => { const e = document.getElementById('base_price'); e.value = '2 468 000'; e.dispatchEvent(new Event('input', {bubbles: true}));"
                        " const b = document.getElementById('blok_base_price'); b.value = '123 400'; b.dispatchEvent(new Event('input', {bubbles: true})); }")
            pf = pg.evaluate(DETAL_JS, ["profil", {".i-name": "U profil", ".i-h": "10", ".i-w": "10", ".i-l": "3"}, False])
            pn = pg.evaluate(DETAL_JS, ["panel", {".i-name": "U panel", ".i-h": "5", ".i-t": "10", ".i-q": "2"}, False])
            dn = pg.evaluate(DETAL_JS, ["dona", {".i-name": "U dona", ".i-h": "10", ".i-t": "10", ".i-donayield": "1", ".i-q": "4"}, False])
            bl = pg.evaluate(DETAL_JS, ["blok", {".i-name": "U blok", ".i-l": "10", ".i-q": "6"}, False])
            check("U5 Profil: 1 m 12 340 → 12 500, jami × 3 m = 37 500 (asl: 12 340 / 37 020)", bosh(pf["perm"]) == "12 500" and bosh(pf["jami"]) == "37 500", pf)
            check("U6 Panel: 1 m 12 340 → 12 500, jami × 2 = 25 000", bosh(pn["perm"]) == "12 500" and bosh(pn["jami"]) == "25 000", pn)
            check("U7 Donalik (yangi usul): 1 dona 12 340 → 12 500 (maydonda ham), jami × 4 = 50 000", bosh(dn["perm"]) == "12 500"
                  and bosh(dn["jami"]) == "50 000" and bosh(dn["up"]) == "12 500", dn)
            check("U8 Blok: 123 400 ÷ 10 = 12 340 → 12 500, jami × 6 m = 75 000", bosh(bl["perm"]) == "12 500" and bosh(bl["jami"]) == "75 000", bl)
            pq = pg.evaluate(DETAL_JS, ["profil", {".i-name": "U profil q", ".i-h": "10", ".i-w": "10", ".i-l": "1"}, True])
            pq2 = pg.evaluate(DETAL_JS, ["profil", {".i-name": "U profil q2", "#base_price": "2 530 000", ".i-h": "10", ".i-w": "10", ".i-l": "1"}, True])
            pg.evaluate("() => { const e = document.getElementById('base_price'); e.value = '2 468 000'; e.dispatchEvent(new Event('input', {bubbles: true})); }")
            check("U9 qoplamali Profil: 12 340 × 2 = 24 680 → 25 000; 12 650 × 2 = 25 300 → 25 500 (yaxlitlash qoplamadan KEYIN — oldin "
                  "bo'lsa 26 000)", bosh(pq["perm"]) == "25 000" and bosh(pq2["perm"]) == "25 500", (pq, pq2))
            p65 = pg.evaluate(DETAL_JS, ["profil", {".i-name": "U profil 65", "#base_price": "2 530 000", ".i-h": "10", ".i-w": "10", ".i-l": "1"}, False])
            check("U10 12 650 → 13 000 (egasi misoli)", bosh(p65["perm"]) == "13 000", p65)
            p_aniq = pg.evaluate(DETAL_JS, ["profil", {".i-name": "U profil aniq", "#base_price": "2 500 000", ".i-h": "10", ".i-w": "10", ".i-l": "1"}, False])
            check("U11 qadamga teng narx (12 500) — o'zgarmaydi (suzuvchi xato 13 000 ga sakratmaydi)", bosh(p_aniq["perm"]) == "12 500", p_aniq)
            qd = pg.evaluate(DETAL_JS, ["dona", {".i-name": "U dona qo'lda", ".i-unitprice": "12 340", ".i-q": "2"}, False])
            check("U12 Donalik — o'lchamsiz, narx QO'LDA 12 340 — yaxlitlanmaydi (jami 24 680)", bosh(qd["perm"]) == "12 340"
                  and bosh(qd["jami"]) == "24 680", qd)
            # «−» va qadamlar — shu formada qoida almashtirib (hisob funksiyasi)
            _px = pg.evaluate("""() => { const t = (q, n) => { narxYaxlitOrnat(q); return narxYaxlit(n); };
                const r = {m500a: t('-500', 12340), m500b: t('-500', 12650), m1000: t('-1000', 12650), p100: t('+100', 12340.01),
                           m100: t('-100', 12399.99), kichik: t('-500', 340), nol: t('+500', 0), yoq: t('', 12340), buzuq: t('+250', 12340),
                           tiyin: t('+500', 12500.004)};
                narxYaxlitOrnat('+500'); return r; }""")
            check("U13 «−» 500: 12 340 → 12 000, 12 650 → 12 500; «−» 1 000: 12 650 → 12 000; «+» 100: 12 340,01 → 12 400; «−» 100: 12 399,99 → 12 300",
                  _px["m500a"] == 12000 and _px["m500b"] == 12500 and _px["m1000"] == 12000 and _px["p100"] == 12400 and _px["m100"] == 12300, _px)
            check("U14 «−» qadamdan kichik narx (340) — 0 ga tushmaydi (aniq qoladi); 0 — 0; qoidasiz / buzuq qoida — o'zgarmaydi; "
                  "12 500,004 (tiyinda 12 500) «+» — 12 500", _px["kichik"] == 340 and _px["nol"] == 0 and _px["yoq"] == 12340
                  and _px["buzuq"] == 12340 and _px["tiyin"] == 12500, _px)

            # ── Saqlash (haqiqiy `saveOrder`) → server
            pg.evaluate("() => { document.getElementById('items').innerHTML = ''; }")
            pg.evaluate("() => { const e = document.getElementById('base_price'); e.value = '2 468 000'; e.dispatchEvent(new Event('input', {bubbles: true})); }")
            pg.evaluate(DETAL_JS, ["profil", {".i-name": "Saqlanadigan profil", ".i-h": "10", ".i-w": "10", ".i-l": "3"}, False])
            pg.evaluate(f"() => {{ document.getElementById('project_id').value = '{ID['P1']}'; document.getElementById('deadline_input').value = '2026-12-20'; }}")
            _oldin = {o["id"] for o in (js(A.get("/api/orders")) or [])}
            pg.evaluate("() => { saveOrder(); }")
            for _ in range(4):
                pg.wait_for_timeout(500)
                if not pg.evaluate("() => { const b = document.getElementById('genericConfirmOk'); if (b && b.offsetParent !== null) { b.click(); return true; } return false; }"):
                    break
            pg.wait_for_timeout(1500)
            _yangi = [o for o in (js(A.get("/api/orders")) or []) if o["id"] not in _oldin]
            OU = _yangi[0]["id"] if _yangi else None
            _du = js(A.get(f"/api/orders/{OU}")) if OU else {}
            _iu = (_du.get("items") or [{}])[0]
            check("U15 forma saqladi: buyurtmada qoida «+500», detal 1 m 12 500 × 3 = 37 500", _du.get("narx_yaxlit") == "+500"
                  and yaqin(_iu.get("total_price"), 37_500), (OU, _du.get("narx_yaxlit"), _iu.get("unit_price"), _iu.get("total_price")))

            # ── Sozlama «−1000» ga o'zgardi → eski buyurtma tahriri o'z qoidasi bilan
            sozla(A, "-", 1000)
            if OU:
                pg.goto(f"{BASE}/orders?order={OU}", wait_until="networkidle")
                pg.wait_for_timeout(700)
                pg.evaluate("() => { editSelected(); }")
                pg.wait_for_timeout(1300)
                _e = pg.evaluate("""() => { const r = document.querySelector('#items .detal');
                    return {perm: r.querySelector('.i-perm').value, jami: r.querySelector('.i-price').value, q: NARX_YAXLIT,
                            iz: document.getElementById('narx_yaxlit_izoh').textContent}; }""")
                check("U16 sozlama «−1 000» ga o'zgardi — saqlangan buyurtma tahriri O'Z qoidasi bilan («+500»): 1 m 12 500, jami 37 500; izoh «yuqoriga … 500»",
                      _e["q"] == "+500" and bosh(_e["perm"]) == "12 500" and bosh(_e["jami"]) == "37 500" and "yuqoriga" in _e["iz"], _e)
                pg.evaluate("() => { const e = document.getElementById('base_price'); e.value = '2 530 000'; e.dispatchEvent(new Event('input', {bubbles: true})); }")
                pg.wait_for_timeout(200)
                _e2 = pg.evaluate("() => document.querySelector('#items .detal .i-perm').value")
                check("U17 tahrirda asosiy narx o'zgarsa — buyurtmaning qoidasi bilan: 12 650 → 13 000 (Sozlamalardagi «−1 000» EMAS)",
                      bosh(_e2) == "13 000", _e2)
            # eski (qoidasiz) buyurtma — B3 dagi O2 (12 340)
            pg.goto(f"{BASE}/orders?order={O2}", wait_until="networkidle")
            pg.wait_for_timeout(700)
            pg.evaluate("() => { editSelected(); }")
            pg.wait_for_timeout(1300)
            _o = pg.evaluate("""() => { const r = document.querySelector('#items .detal');
                return {perm: r.querySelector('.i-perm').value, q: NARX_YAXLIT, izk: document.getElementById('narx_yaxlit_izoh').offsetParent !== null}; }""")
            check("U18 eski (qoidasiz) buyurtma tahriri — yaxlitlanmaydi (12 340), izoh yashirin", _o["q"] == "" and bosh(_o["perm"]) == "12 340"
                  and not _o["izk"], _o)
            pg.evaluate("() => { hideNewForm(); showNewForm(); }")
            pg.wait_for_timeout(300)
            _n = pg.evaluate("() => ({q: NARX_YAXLIT, iz: document.getElementById('narx_yaxlit_izoh').textContent})")
            check("U19 tahrirdan keyin «+ Yangi buyurtma» — yana Sozlamalardagi qoida («−1000», «pastga … 1 000»)", _n["q"] == "-1000"
                  and "pastga" in _n["iz"] and "1 000" in bosh(_n["iz"]), _n)
            # taklif «−500» (rasmiylashtirilmagan — tahrirlanadi) — taklif oynasida o'z qoidasi
            _rt = A.post("/api/takliflar", json={"mijoz": "UI taklif", "telefon": "+998901234568",
                                                 "buyurtma": {k: v for k, v in buyurtma([profil("UI taklif profil", 12_000)],
                                                                                        narx_yaxlit="-500").items() if k != "project_id"}})
            T2 = (js(_rt).get("taklif") or {}).get("id")
            pg.evaluate(f"() => taklifTahrir({T2})")
            pg.wait_for_timeout(1500)
            _t = pg.evaluate("() => ({q: NARX_YAXLIT})")
            check("U20 taklifni ochish — taklifning O'Z qoidasi («-500»)", _t["q"] == "-500", _t)
            ctx.close()
            br.close()

    try:
        _ui()
        check("U0 brauzer bo'limi oxirigacha yurdi", True)
    except Exception as e:                 # noqa: BLE001 — asl kodda (maydonlar yo'q) test QULAMAYDI, yiqiladi
        check("U0 brauzer bo'limi oxirigacha yurdi", False, f"{type(e).__name__}: {str(e)[:400]}")
    check("U21 sahifalarda JS xatosi yo'q", not XATOLAR, XATOLAR[:5])
    _srv.should_exit = True

print(f"\nNATIJA: o'tdi = {OK}, yiqildi = {FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
