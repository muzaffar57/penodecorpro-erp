#!/usr/bin/env python3
"""
test_ish_davri_ui.py — kech141 (zip 169): hodim ishdan ketish / qaytish oynalari va «Tayyor» summasi tuzatishlari — HAQIQIY brauzerda
(Chromium, Playwright), HAQIQIY lokal server bilan (uvicorn, test bazasi) O'LCHANADI.

NIMA UCHUN KERAK (egasi QARORLARI 11.10 / 12.10 — `tools/test_audit_pul2.py` server tomonini tekshiradi; bu — sahifalar):
  * «Ustalar KPI»: hodimni o'chirish — oddiy «o'chirilsinmi?» edi (sana so'ralmasdi, hodim hamma oylardan yo'qolardi). Endi oyna
    «Ishdan ketgan sana» (oldindan bugun, kelajak / ishga kirgandan oldin — tanlanmaydi, server rad etsa — sabab oynada), ikki bosish —
    bitta so'rov; yangi hodim oynasida «Ishga kirgan sana» (oldindan bugun; o'tgan oy — ogohlantirish); saqlash rad etilsa — server
    sababi (ilgari «❌ Xato yuz berdi»); oylik hisob-kitobda ishdan ketgan hodim — belgi bilan.
  * «O'chirilganlar»: ishdan ketgan sana ko'rinadi; tiklash — «Ishga qaytdi» (sana) yoki «Xato o'chirilgan edi» (ish uzilmagan);
    ketgan sana bugun / noma'lum — oynasiz; «Butunlay o'chirish» oynasi — «O'tgan oylar hisobotida qoladi».
  * «Qarzdorlar»: ishdan ketgan hodim qarzi — «ishdan ketgan» belgisi bilan.
  * «Moliya»: «✏️ Narx tuzatishlari (N ta, shu oyda)» guruhi; «Buyurtmalar» ✏️: «Tayyor» buyurtmada — qaysi oy hisobotiga yozilishi va
    «Mijozga N so'm qaytarish kerak».
  * Telefon (390 px): oynalar ekranga sig'adi.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan PostgreSQL. Asl kodga (zip 168) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_ish_davri_ui.py
"""
import os
import re
import io
import sys
import glob
import time
import socket
import tempfile
import calendar
import threading
import contextlib
from datetime import datetime, date, timedelta
from urllib.parse import urlparse, parse_qs

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OK = FAIL = 0
FAILED = []
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
YORLIQ = "[PG] " if PG_URL else ""


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
        print(f"  ✗ {label}   {str(detail)[:1500]}")


def section(t):
    print(f"\n--- {t} ---")


try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_xato = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_xato = False, f"{type(_e).__name__}: {_e}"

PG_BAZA = "ish_davri_ui169_test"
_T = tempfile.mkdtemp(prefix="id_ui_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'id_ui_test.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import models                                  # noqa: E402
from database import SessionLocal, tashkent_date   # noqa: E402
from models import UserRole, Employee, Project, Inventory, Order, OrderItem, Master  # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

HodimIshDavri = getattr(models, "HodimIshDavri", None)
PAROL = "Parol123!"
BUGUN = tashkent_date()
Y, M = BUGUN.year, BUGUN.month


def oy_oldin(y, m, n=1):
    k = y * 12 + (m - 1) - n
    return k // 12, k % 12 + 1


Y0, M0 = oy_oldin(Y, M)
D0 = calendar.monthrange(Y0, M0)[1]
OYLAR = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]
KETGAN = date(Y0, M0, 15)

with TestClient(main.app, base_url="https://testserver") as _c0:
    _c0.get("/login")
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "id_a", PAROL, UserRole.ADMIN, "ID Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="ID Penoplast", unit="blok", stock_quantity=100_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
s.add(PENO)
s.commit()
PENO_ID = PENO.id
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
assert C.post("/login", data={"username": "id_a", "password": PAROL}, follow_redirects=False).status_code == 302


def hodim(ism):
    r = C.post("/api/employees", json={"name": ism, "pay_type": "fixed", "fixed_amount": 3_100_000})
    eid = r.json()["id"]
    s = SessionLocal()
    s.get(Employee, eid).hire_date = datetime(Y - 1, 1, 1, 4, 0)
    s.commit()
    s.close()
    return eid


E_OCHIR = hodim("ID Ochiriladi")
E_KETGAN = hodim("ID Ketgan")
C.delete(f"/api/employees/{E_KETGAN}", params={"ketgan_sana": KETGAN.isoformat()})
E_BUGUN = hodim("ID Bugun ketgan")
C.delete(f"/api/employees/{E_BUGUN}")
E_BUTUN = hodim("ID Butunlay")
C.delete(f"/api/employees/{E_BUTUN}", params={"ketgan_sana": KETGAN.isoformat()})
E_TAHRIR = hodim("ID Tahrir")
E_XATO = hodim("ID Xato oyna")

s = SessionLocal()
_m = Master(company_id=1, name="ID Usta", phone="+998901690201", kpi_percent=10.0, is_active=True)
_p = Project(company_id=1, client_name="ID Mijoz", project_name="ID loyiha", total_budget=0, total_paid=0)
s.add_all([_m, _p])
s.commit()
MID, PID = _m.id, _p.id
s.close()
_ro = C.post("/api/orders", params={"confirm_shortage": "true"}, json={
    "project_id": PID, "order_type": "product", "loy_kg": 0, "master_id": MID, "is_draft": False,
    "items": [{"name": "ID detal", "category": "profil", "width": 20, "thickness": 10, "length": 10, "quantity": 10,
               "unit_price": 100_000, "is_coated": False, "penoplast_id": PENO_ID}]})
OID = (_ro.json() or {}).get("id")
s = SessionLocal()
IID = s.query(OrderItem.id).filter(OrderItem.order_id == OID).first()[0]
s.close()
C.post("/api/payments", json={"order_id": OID, "amount": 1_000_000, "payment_type": "partial", "payment_method": "naqd", "notes": "id"})
C.post("/api/deliveries", json={"order_id": OID, "items": [{"order_item_id": IID, "quantity": 10}], "notes": "id",
                                "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"})
C.post(f"/api/orders/{OID}/ready")
s = SessionLocal()
s.get(Order, OID).completed_at = datetime(Y0, M0, 15, 7, 0)
s.commit()
s.close()
# ikkinchi «Tayyor» buyurtma — Moliya guruhi uchun (✏️ API orqali), birinchisi — «Buyurtmalar» oynasi orqali
_ro2 = C.post("/api/orders", params={"confirm_shortage": "true"}, json={
    "project_id": PID, "order_type": "product", "loy_kg": 0, "master_id": MID, "is_draft": False,
    "items": [{"name": "ID detal 2", "category": "profil", "width": 20, "thickness": 10, "length": 10, "quantity": 10,
               "unit_price": 100_000, "is_coated": False, "penoplast_id": PENO_ID}]})
OID2 = (_ro2.json() or {}).get("id")
s = SessionLocal()
IID2 = s.query(OrderItem.id).filter(OrderItem.order_id == OID2).first()[0]
s.close()
C.post("/api/deliveries", json={"order_id": OID2, "items": [{"order_item_id": IID2, "quantity": 10}], "notes": "id2",
                                "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd"})
C.post(f"/api/orders/{OID2}/ready")
s = SessionLocal()
s.get(Order, OID2).completed_at = datetime(Y0, M0, 16, 7, 0)
s.commit()
s.close()
C.put(f"/api/orders/{OID2}/agreed-amount", json={"agreed_amount": 900_000})


def davrlar(eid):
    if HodimIshDavri is None:
        return []
    s = SessionLocal()
    try:
        return [(d.boshlangan, d.tugagan) for d in s.query(HodimIshDavri).filter(HodimIshDavri.employee_id == eid)
                .order_by(HodimIshDavri.id)]
    finally:
        s.close()


def hodim_db(eid):
    s = SessionLocal()
    try:
        e = s.get(Employee, eid)
        return None if e is None else {"deleted": bool(e.is_deleted), "butunlay": bool(getattr(e, "butunlay_ochirilgan", False)),
                                       "hire": tashkent_date(e.hire_date) if e.hire_date else None}
    finally:
        s.close()


section("0. Tayyorgarlik")
check("0a Python `playwright` bor; ma'lumot tayyor (hodimlar, «Tayyor» buyurtmalar)", PW_BOR and OID and OID2, _pw_xato)

import uvicorn                                     # noqa: E402

if PW_BOR and OID and OID2:
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    port = so.getsockname()[1]
    so.close()
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(150):
        if server.started:
            break
        time.sleep(0.1)
    check("0b lokal server ishga tushdi", server.started)
    BU = f"http://127.0.0.1:{port}"

    with sync_playwright() as pw:
        _exe = None
        for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                "chrome-linux", "chrome"))):
            _exe = _y
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()

        def xav(f, *a, **k):
            try:
                return f(*a, **k)
            except Exception as ex:        # noqa: BLE001
                print(f"    (amal bajarilmadi: {getattr(f, '__name__', f)} {a[:1]} — {type(ex).__name__})")
                return None

        def kontekst(w=1440, h=900):
            tel = w < 700
            ctx = br.new_context(viewport={"width": w, "height": h}, is_mobile=tel, has_touch=tel, timezone_id="Asia/Tashkent",
                                 locale="uz-UZ")
            ctx.set_default_timeout(20000)

            def tashqi(r):
                u = r.request.url
                if re.search(r"chart(\.umd)?(\.min)?\.js", u, re.I):
                    return r.fulfill(status=200, content_type="application/javascript",
                                     body="window.Chart = function () { return {destroy() {}, update() {}}; };")
                return r.fulfill(status=204, body="")
            ctx.route(re.compile(r"^https://.*"), tashqi)
            pg = ctx.new_page()
            xav(pg.goto, BU + "/login")
            xav(pg.fill, "input[name=username]", "id_a")
            xav(pg.fill, "input[name=password]", PAROL)
            xav(pg.press, "input[name=password]", "Enter")
            xav(pg.wait_for_load_state, "networkidle")
            pg.close()
            return ctx

        def sahifa(ctx, url, kut=1200):
            pg = ctx.new_page()
            pg.__xato, pg.__sorov = [], []
            pg.on("pageerror", lambda e: pg.__xato.append(str(e)[:300]))
            pg.on("request", lambda r: pg.__sorov.append((r.method, r.url.replace(BU, ""))) if "/api/" in r.url else None)
            xav(pg.goto, BU + url, wait_until="networkidle")
            pg.wait_for_timeout(kut)
            return pg

        def ev(pg, kod, arg=None):
            try:
                return pg.evaluate(kod, arg) if arg is not None else pg.evaluate(kod)
            except Exception as ex:        # noqa: BLE001
                return {"js_xato": str(ex)[:300]}

        KORIN = r"""(id) => { const e = document.getElementById(id); if (!e) return null;
          const cs = getComputedStyle(e); let v = cs.display !== 'none' && cs.visibility !== 'hidden';
          for (let p = e; p && p.nodeType === 1; p = p.parentElement) if (getComputedStyle(p).display === 'none') v = false;
          return {v, t: (e.innerText || e.textContent || '').replace(/\s+/g, ' ').trim(), val: e.value, min: e.min, max: e.max,
                  dis: !!e.disabled, ch: !!e.checked}; }"""

        def el(pg, i):
            o = ev(pg, KORIN, i)
            return o if isinstance(o, dict) and "v" in o else {}

        ctx = kontekst()

        # ══════════════════════════════════════════════════════════════
        section("K. «Ustalar KPI» — yangi hodim «Ishga kirgan sana»")
        pg = sahifa(ctx, "/kpi")
        ev(pg, "() => { openEmpModal(); }")
        _k = el(pg, "e-kirgan")
        check("K1 yangi hodim oynasida «Ishga kirgan sana» ko'rinadi, oldindan BUGUN, kelajak tanlanmaydi (`max`)",
              el(pg, "e-kirgan-wrap").get("v") and _k.get("val") == BUGUN.isoformat() and _k.get("max") == BUGUN.isoformat(), _k)
        xav(pg.fill, "#e-kirgan", date(Y0, M0, 11).isoformat())
        ev(pg, "() => { if (typeof kirganSanaIzoh === 'function') kirganSanaIzoh(); }")
        check("K2 o'tgan oy tanlansa — ogohlantirish (o'sha oydan hisobotlarga ham oylik qo'shiladi)",
              "o'tgan oyda" in (el(pg, "e-kirgan-izoh").get("t") or ""), el(pg, "e-kirgan-izoh"))
        xav(pg.fill, "#e-name", "ID Yangi UI")
        ev(pg, "() => { setProdType('umumiy'); }")
        xav(pg.fill, "#e-fixed", "2 000 000")
        pg.__sorov.clear()
        with contextlib.suppress(Exception):
            with pg.expect_request(lambda r: r.method == "POST" and urlparse(r.url).path == "/api/employees", timeout=8000) as _rq:
                ev(pg, "() => { saveEmployee(); }")
            _tana = _rq.value.post_data or ""
        pg.wait_for_timeout(900)
        s = SessionLocal()
        _yangi = s.query(Employee).filter(Employee.name == "ID Yangi UI").first()
        _yangi_hire = tashkent_date(_yangi.hire_date) if _yangi is not None else None
        _yangi_id = _yangi.id if _yangi is not None else None
        s.close()
        check("K3 saqlash: so'rovda `ishga_kirgan_sana`, hodim o'sha kun bilan yaratildi, oyna yopildi",
              _yangi_hire == date(Y0, M0, 11) and not el(pg, "empModal").get("v"), [_yangi_hire, el(pg, "empModal").get("v")])
        ev(pg, "() => { openEmpModal(); }")
        xav(pg.fill, "#e-name", "ID Kelajak UI")
        ev(pg, "() => { setProdType('umumiy'); }")
        xav(pg.fill, "#e-fixed", "1 000 000")
        ev(pg, f"() => {{ document.getElementById('e-kirgan').value = '{(BUGUN + timedelta(days=3)).isoformat()}'; }}")
        ev(pg, "() => { saveEmployee(); }")
        pg.wait_for_timeout(1200)
        _err = el(pg, "emp-error")
        s = SessionLocal()
        _kel = s.query(Employee).filter(Employee.name == "ID Kelajak UI").count()
        s.close()
        check("K4 server rad etsa (kelajakdagi sana) — oynada SERVER SABABI (ilgari «❌ Xato yuz berdi»), hodim yaratilmadi",
              _err.get("v") and "kelajak" in (_err.get("t") or "") and _kel == 0 and el(pg, "empModal").get("v"), [_err, _kel])
        ev(pg, "() => { closeEmpModal(); }")
        ev(pg, f"() => {{ editEmployee({E_TAHRIR}); }}")
        _kw = el(pg, "e-kirgan-wrap")
        check("K5 tahrirlash oynasida «Ishga kirgan sana» YO'Q (faqat yangi hodimda)", bool(_kw) and not _kw.get("v")
              and el(pg, "empModal").get("v"), [_kw, el(pg, "empModal")])
        ev(pg, "() => { closeEmpModal(); }")

        # ══════════════════════════════════════════════════════════════
        section("K. «Ustalar KPI» — hodimni o'chirish = ishdan ketish (sana oynasi)")
        ev(pg, f"() => {{ deleteEmployee({E_OCHIR}); }}")
        pg.wait_for_timeout(300)
        _s = el(pg, "ek-sana")
        check("K6 o'chirish oynasi: hodim nomi, «Ishdan ketgan sana» oldindan BUGUN, `max` bugun, `min` — ishga kirgan kun",
              el(pg, "empKetishModal").get("v") and "ID Ochiriladi" in (el(pg, "ek-sarlavha").get("t") or "")
              and _s.get("val") == BUGUN.isoformat() and _s.get("max") == BUGUN.isoformat() and _s.get("min") == f"{Y - 1}-01-01",
              [el(pg, "empKetishModal"), el(pg, "ek-sarlavha"), _s])
        check("K7 izoh: shu oy oyligi shu kungacha, keyingi oylarda yo'q, o'tgan oylar hisobotida qoladi",
              f"{OYLAR[M]} {Y} oyligi shu kungacha" in (el(pg, "ek-izoh").get("t") or "")
              and "O'tgan oylar hisobotida" in (el(pg, "ek-izoh").get("t") or ""), el(pg, "ek-izoh"))
        xav(pg.fill, "#ek-sana", KETGAN.isoformat())
        check("K8 o'tgan oy tanlansa — «⚠️ Sana o'tgan oyda — … oyligi ham kamayadi»",
              f"Sana o'tgan oyda — {OYLAR[M0]} {Y0} oyligi ham kamayadi" in (el(pg, "ek-izoh").get("t") or ""), el(pg, "ek-izoh"))
        _dl = []

        def _ush(r):
            _dl.append(r.request.url)
            pg.wait_for_timeout(700)
            r.continue_()
        pg.route(re.compile(r".*/api/employees/\d+(\?.*)?$"), lambda r: _ush(r) if r.request.method == "DELETE" else r.continue_())
        ev(pg, "() => { ketishTasdiq(); ketishTasdiq(); }")
        pg.wait_for_timeout(2500)
        pg.unroute(re.compile(r".*/api/employees/\d+(\?.*)?$"))
        _q = parse_qs(urlparse(_dl[0]).query) if _dl else {}
        check("K9 «O'chirish»: BITTA DELETE (ikki bosish), `ketgan_sana` tanlangan kun; oyna yopildi; bazada davr shu kun bilan yopildi",
              len(_dl) == 1 and _q.get("ketgan_sana") == [KETGAN.isoformat()] and not el(pg, "empKetishModal").get("v")
              and davrlar(E_OCHIR) == [(None, KETGAN)], [_dl, el(pg, "empKetishModal").get("v"), davrlar(E_OCHIR)])
        ev(pg, f"() => {{ deleteEmployee({E_XATO}); }}")
        pg.route(re.compile(r".*/api/employees/\d+(\?.*)?$"),
                 lambda r: r.fulfill(status=400, content_type="application/json",
                                     body='{"detail": "SERVER-SABABI-169"}') if r.request.method == "DELETE" else r.continue_())
        ev(pg, "() => { ketishTasdiq(); }")
        pg.wait_for_timeout(1200)
        pg.unroute(re.compile(r".*/api/employees/\d+(\?.*)?$"))
        _ex = el(pg, "ek-xato")
        check("K10 server rad etsa — oyna OCHIQ qoladi, sabab oynada («❌ O'chirilmadi: …»), tugma yana bosiladi",
              el(pg, "empKetishModal").get("v") and _ex.get("v") and "O'chirilmadi: SERVER-SABABI-169" in (_ex.get("t") or "")
              and not el(pg, "ek-ok").get("dis") and not (hodim_db(E_XATO) or {}).get("deleted"), [_ex, el(pg, "ek-ok")])
        ev(pg, "() => { if (typeof ketishYop === 'function') ketishYop(); }")
        ev(pg, f"() => {{ document.getElementById('emp-report-year').value = '{Y0}'; document.getElementById('emp-report-month').value = '{M0}'; loadEmpMonthlyReport(); }}")
        pg.wait_for_timeout(1500)
        _rep = el(pg, "empMonthlyReport").get("t") or ""
        # belgi — `.hodim-ketgan-belgi` elementi (izohdagi «(ishdan ketgan …)» matni bilan adashmasin): matni va qatori
        _bk11 = ev(pg, "() => Array.from(document.querySelectorAll('#empMonthlyReport .hodim-ketgan-belgi')).map(e => "
                       "[e.textContent.trim(), (e.closest('tr') ? e.closest('tr').innerText : '').replace(/\\s+/g, ' ')])")
        check(f"K11 oylik hisob-kitob ({OYLAR[M0]}): ishdan ketgan hodim — «ishdan ketgan {KETGAN.strftime('%d.%m.%Y')}» belgisi va "
              f"«15/{D0} kun ishlagan»",
              isinstance(_bk11, list) and any(b == f"ishdan ketgan {KETGAN.strftime('%d.%m.%Y')}" and "ID Ochiriladi" in q
                                              and f"15/{D0} kun ishlagan" in q for b, q in _bk11), [_bk11, _rep[:600]])
        check("K12 sahifada JS xatosi yo'q", not pg.__xato, pg.__xato)
        pg.close()

        # ══════════════════════════════════════════════════════════════
        section("O. «O'chirilganlar» — tiklash oynasi, butunlay o'chirish")
        pg = sahifa(ctx, "/trash")
        _qator = ev(pg, f"() => (document.getElementById('row-employee-{E_KETGAN}') || {{}}).innerText || ''")
        check("O1 o'chirilgan hodim qatorida «ishdan ketgan DD.MM.YYYY»", f"ishdan ketgan {KETGAN.strftime('%d.%m.%Y')}" in str(_qator), _qator)
        ev(pg, f"() => {{ document.querySelector('#row-employee-{E_KETGAN} button.btn-dark').click(); }}")
        pg.wait_for_timeout(400)
        _hs = el(pg, "ht-sana")
        check("O2 «Tiklash» — oyna: ketgan sana, «Ishga qaytdi» tanlangan, sana oldindan bugun (min — ketgan kun, max — bugun)",
              el(pg, "hodimTiklashModal").get("v") and KETGAN.strftime("%d.%m.%Y") in (el(pg, "ht-ketgan").get("t") or "")
              and el(pg, "ht-qaytdi").get("ch") and _hs.get("val") == BUGUN.isoformat() and _hs.get("min") == KETGAN.isoformat()
              and _hs.get("max") == BUGUN.isoformat(), [el(pg, "hodimTiklashModal"), el(pg, "ht-ketgan"), _hs])
        xav(pg.click, "#ht-xato")
        _hw = el(pg, "ht-sana-wrap")
        check("O3 «Xato o'chirilgan edi» tanlansa — sana maydoni yashirinadi", bool(_hw) and not _hw.get("v") and el(pg, "ht-xato").get("ch"),
              [_hw, el(pg, "ht-xato")])
        _rs = []
        pg.on("request", lambda r: _rs.append(r.url) if "/restore" in r.url else None)
        xav(pg.click, "#ht-ok")
        pg.wait_for_timeout(2000)
        _rq = parse_qs(urlparse(_rs[0]).query) if _rs else {}
        check("O4 tiklash: so'rovda `qaytgan_sana` = ketgan kun (ish uzilmagan) — bazada davr qayta ochildi, hodim tiklandi",
              _rq.get("qaytgan_sana") == [KETGAN.isoformat()] and davrlar(E_KETGAN) == [(None, None)]
              and not (hodim_db(E_KETGAN) or {}).get("deleted"), [_rs, davrlar(E_KETGAN), hodim_db(E_KETGAN)])
        pg.close()
        pg = sahifa(ctx, "/trash")
        _rs2 = []
        pg.on("request", lambda r: _rs2.append(r.url) if "/restore" in r.url else None)
        ev(pg, f"() => {{ document.querySelector('#row-employee-{E_BUGUN} button.btn-dark').click(); }}")
        pg.wait_for_timeout(1800)
        check("O5 ketgan sana BUGUN — oynasiz, darhol tiklanadi (sanasiz so'rov)",
              len(_rs2) == 1 and "qaytgan_sana" not in _rs2[0] and not (hodim_db(E_BUGUN) or {}).get("deleted"),
              [_rs2, hodim_db(E_BUGUN)])
        pg.close()
        pg = sahifa(ctx, "/trash")
        ev(pg, f"() => {{ document.querySelector('#row-employee-{E_BUTUN} button.btn-danger').click(); }}")
        pg.wait_for_timeout(400)
        _cc = ev(pg, "() => (document.getElementById('ccModalMessage') || {}).innerText || ''")
        check("O6 «Butunlay o'chirish» oynasi: ro'yxatdan yo'qoladi, tiklanmaydi, telefon / PIN o'chadi, O'TGAN OYLAR HISOBOTIDA QOLADI",
              "O'tgan oylar hisobotida ismi, oyligi va avanslari qoladi" in str(_cc) and "tiklab bo'lmaydi" in str(_cc), _cc)
        xav(pg.click, "#ccModalOk")
        pg.wait_for_timeout(400)
        xav(pg.click, "#ccModalOk")
        pg.wait_for_timeout(2000)
        _bdb = hodim_db(E_BUTUN) or {}
        check("O7 butunlay o'chirildi: bazada qator QOLDI (`butunlay_ochirilgan`), sahifa qayta yuklangach ro'yxatda yo'q",
              _bdb.get("butunlay") is True and ev(pg, f"() => !document.getElementById('row-employee-{E_BUTUN}')") is True,
              [_bdb, ev(pg, f"() => !document.getElementById('row-employee-{E_BUTUN}')")])
        check("O8 sahifada JS xatosi yo'q", not pg.__xato, pg.__xato)
        pg.close()

        # ══════════════════════════════════════════════════════════════
        section("Q. «Qarzdorlar» — ishdan ketgan hodim belgisi")
        pg = sahifa(ctx, "/debts")
        _bq = ev(pg, "() => Array.from(document.querySelectorAll('.hodim-ketgan-belgi')).map(e => e.closest('.oblig-item, .hodim-qarzdor-qator') ? e.closest('.oblig-item, .hodim-qarzdor-qator').innerText.replace(/\\s+/g, ' ') : '')")
        check(f"Q1 «Hodimlarga qarzimiz»: ishdan ketgan hodim (ID Ochiriladi, {OYLAR[M0]}) — «ishdan ketgan {KETGAN.strftime('%d.%m.%Y')}»",
              isinstance(_bq, list) and any("ID Ochiriladi" in x and f"ishdan ketgan {KETGAN.strftime('%d.%m.%Y')}" in x for x in _bq), _bq)
        pg.close()

        # ══════════════════════════════════════════════════════════════
        section("M. «Moliya» — ✏️ Narx tuzatishlari guruhi (shu oyda)")
        pg = sahifa(ctx, "/finance", kut=2000)
        _fx = ev(pg, "() => ((document.getElementById('expDetail') || {}).textContent || '').replace(/\\s+/g, ' ')")
        check("M1 joriy oy: «✏️ Narx tuzatishlari (1 ta, shu oyda)», «Kelishilgan summa o'zgarishi» −100 000",
              "Narx tuzatishlari (1 ta, shu oyda)" in str(_fx) and "Kelishilgan summa o'zgarishi" in str(_fx)
              and re.search(r"-\s?100\s?000", str(_fx)) is not None, str(_fx)[:900])
        check("M2 sahifada JS xatosi yo'q", not pg.__xato, pg.__xato)
        pg.close()

        # ══════════════════════════════════════════════════════════════
        section("B. «Buyurtmalar» — «Tayyor» buyurtmada ✏️ kelishilgan summa")
        pg = sahifa(ctx, "/orders", kut=1500)
        ev(pg, "() => { window.__msg = []; const _o = showMsg; showMsg = (t, ty) => { window.__msg.push(String(t)); return _o(t, ty); }; }")
        ev(pg, f"() => {{ selectedOrderId = {OID}; editAgreedAmount(); }}")
        xav(pg.wait_for_selector, "#genericPromptInput", timeout=8000)
        _pm = ev(pg, "() => (document.getElementById('genericConfirmMsg') || {}).innerText || ''")
        check(f"B1 so'rov oynasida: «Buyurtma «Tayyor» — o'zgarish {OYLAR[M]} hisobotiga yoziladi (yakunlangan oy o'zgarmaydi)»",
              f"o'zgarish {OYLAR[M]} hisobotiga yoziladi" in str(_pm), _pm)
        xav(pg.fill, "#genericPromptInput", "900 000")
        xav(pg.click, "#genericConfirmOk")
        pg.wait_for_timeout(1500)
        _msg = ev(pg, "() => window.__msg")
        check(f"B2 xabar: «{OYLAR[M]} {Y} hisobotiga yozildi» va «↩ Mijozga 100 000 so'm qaytarish kerak»",
              isinstance(_msg, list) and any(f"{OYLAR[M]} {Y} hisobotiga yozildi" in x and "Mijozga 100 000 so'm qaytarish kerak" in x
                                             for x in _msg), _msg)
        check("B3 sahifada JS xatosi yo'q", not pg.__xato, pg.__xato)
        pg.close()
        ctx.close()

        # ══════════════════════════════════════════════════════════════
        section("T. Telefon 390 px — oynalar ekranga sig'adi")
        ctx2 = kontekst(390, 844)
        pg = sahifa(ctx2, "/kpi")
        ev(pg, f"() => {{ deleteEmployee({E_TAHRIR}); }}")
        pg.wait_for_timeout(400)
        _o1 = ev(pg, "() => { const m = document.querySelector('#empKetishModal > div'); if (!m) return null; const r = m.getBoundingClientRect(); return {chap: Math.round(r.left), ong: Math.round(r.right), vw: innerWidth, sw: document.documentElement.scrollWidth}; }")
        check("T1 o'chirish oynasi 390 px ichida (gorizontal toshish yo'q)",
              isinstance(_o1, dict) and _o1.get("chap", -1) >= 0 and _o1.get("ong", 9999) <= _o1.get("vw", 0) and _o1.get("sw", 9999) <= _o1.get("vw", 0), _o1)
        pg.close()
        C.delete(f"/api/employees/{E_TAHRIR}", params={"ketgan_sana": KETGAN.isoformat()})
        pg = sahifa(ctx2, "/trash")
        ev(pg, f"() => {{ document.querySelector('#row-employee-{E_TAHRIR} button.btn-dark').click(); }}")
        pg.wait_for_timeout(400)
        _o2 = ev(pg, "() => { const m = document.querySelector('#hodimTiklashModal > div'); if (!m) return null; const r = m.getBoundingClientRect(); return {chap: Math.round(r.left), ong: Math.round(r.right), vw: innerWidth, sw: document.documentElement.scrollWidth, v: getComputedStyle(document.getElementById('hodimTiklashModal')).display}; }")
        check("T2 tiklash oynasi 390 px ichida (gorizontal toshish yo'q)",
              isinstance(_o2, dict) and _o2.get("v") == "flex" and _o2.get("chap", -1) >= 0 and _o2.get("ong", 9999) <= _o2.get("vw", 0)
              and _o2.get("sw", 9999) <= _o2.get("vw", 0), _o2)
        pg.close()
        ctx2.close()
        br.close()
    server.should_exit = True

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
os._exit(1 if FAIL else 0)
