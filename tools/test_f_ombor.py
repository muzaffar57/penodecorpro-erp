#!/usr/bin/env python3
"""
test_f_ombor.py — kech120, F BOSQICH 2-qism (OMBOR, KIRIM, TA'MINOTCHILAR, RETSEPTLAR — audit G4 qolgan bandlari).

NIMA UCHUN KERAK (audit kech114; 2026-10-01 da JORIY kodda qayta tekshirildi — work/f/tekshiruv_kech120.md; O'LCHANGAN work/f/f1_probe.py):
  G4-15  Kirim HUJJATIDAN bitta qator o'chirilsa — hujjat bilan qilingan to'lov va qo'shimcha xarajatlar joyida qolardi (to'lov ortiqcha,
         qolgan materiallar narxi noto'g'ri).
  G4-23  Ishlatilgan retseptni o'chirish — PG da 500 (tashqi kalit), SQLite da detal yetim; tarkib miqdori har material uchun «kg» yozilardi.
  G4-07  «SMS» tugmalari Telegram sozlanmagan bo'lsa ham «yuborildi» derdi.
  G4-08  Ruxsatsizga (Menejer) server rad etadigan tugmalar ko'rinardi (rasm, toifa, chegara, «Asosiy qilish», SMS).
  G4-09  Material o'chirish tasdig'i nomsiz, xabar o'qilmay sahifa yangilanardi.
  G4-10 / G4-13  Kompyuterda ustun nomlari yo'q, tugmalar mayda; Omborxonadan kirimga yo'l va bo'sh holat yo'riqnomasi yo'q.
  G4-12  Toifa filtri qattiq uchta, bitta toifa uch xil nom bilan; toifa — erkin matn.
  G4-16  Ta'minotchi tarixida har kirim «Nasiya» (hujjat bilan to'langan bo'lsa ham); «Jami nasiya».
  G4-18  Penoplast blok hajmi tanlanganda yozilmasdi (namuna — boshqa materialniki), yangi penoplastda bo'sh qolsa — jim 1,0 m³.
  G4-21  «Hujjat fayli (hozircha saqlanmaydi)» maydoni; «Qarzni to'lash» — qaysi qarz ekani noaniq.
  G4-04  Ta'minotchiga to'lovlar tarixi (ko'rish / bekor qilish) oynasiga yo'l yo'q; tez to'lov tasdiqsiz.
  G4-25  Chiqim oynasida xom son («8.253333333333332»), «Nomi bo'yicha» saralash qaytmasdi.
BO'LIMLAR: S — statik; A — API (kirim qatori qulfi, retsept o'chirish, ta'minotchi tarixi holati, Telegram natijasi); B — HAQIQIY
  Chromium (Omborxona — Admin va Menejer, bo'sh korxona, telefon 390 px; Kirim sahifasi; Ta'minotchilar; Retseptlar).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 131) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` + Chromium (B bo'limi).
ISHLATISH: python3 tools/test_f_ombor.py
"""
import os
import re
import io
import sys
import glob
import json
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
PG_BAZA = "f_ombor_test"
_T = tempfile.mkdtemp(prefix="fomb_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'f_ombor_test.db')}"
os.environ.pop("TENANT_FILTER", None)
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("BACKUP_TELEGRAM_CHAT_ID", None)

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Inventory, Supplier, Recipe, Project, Order, OrderItem, OrderType, OrderStatus,   # noqa: E402
                    InventoryPurchase, InventoryReceipt, ActivityLog)
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
MAIN = oqi("main.py")
INV = oqi("templates/inventory.html")
SR = oqi("templates/supplier_receive.html")
SUP = oqi("templates/suppliers.html")
REC = oqi("templates/recipes.html")
check("S1 server: kirim qatori qulfi (`receipt_line_locked`), retsept — ishlatilgan bo'lsa 409, `_send_telegram` — natija qaytaradi",
      '"type": "receipt_line_locked"' in MAIN and "Bu retsept ishlatilgan" in MAIN and "TELEGRAM_YUBORILMADI_XABARI" in MAIN
      and "    return _ketdi" in MAIN)
check("S2 Omborxona: ustun nomlari, «Kirim qilish», Telegram tugmalari (SMS emas), ruxsat bo'yicha boshqaruvlar, toifa filtri ma'lumotdan",
      'class="mat-bosh"' in INV and 'href="/suppliers/receive"' in INV and "→ Telegram" in INV and "SMS</button>" not in INV
      and "{% set mat_tahrir = current_user.ruxsat('material', 'tahrirlash') %}" in INV and "⛱️ Minerallar" not in INV
      and "function toifaKodi(" in INV)
check("S3 Kirim: «Hujjat fayli» yo'q, «Eski qarzni to'lash», «Jami xarid», blok hajmi «necha» (nechchi emas), yangi penoplastda majburiy",
      "(hozircha saqlanmaydi)</span>" not in SR and 'class="rcv-upload"' not in SR and "Eski qarzni to'lash" in SR and ">Jami xarid<" in SR and "nechchi" not in SR
      and "Yangi penoplast: «1 blok necha m³?» ni kiriting" in SR)
check("S4 Ta'minotchilar — qatorda «Tarix»; Retseptlar — o'chirishda server sababi, tarkib birligi materialniki",
      "openHistory(${s.id})" in SUP and "serverXatoSababi(res, 'Xato yuz berdi')" in REC and "<span>kg</span>" not in REC)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. Ma'lumot")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ADMIN, MENEJER, PAROL = "fomb_admin", "fomb_menejer", "Parol123!"
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="FO B korxona", code="FO-B"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, ADMIN, PAROL, UserRole.ADMIN, "FO Admin", company_id=1)
    auth.create_user(_db, MENEJER, PAROL, UserRole.MANAGER, "FO Menejer", company_id=1)
    auth.create_user(_db, "fomb_b", PAROL, UserRole.ADMIN, "FO B", company_id=2)
_n = uuid.uuid4().hex[:5]
M = {
    "m1": Inventory(company_id=1, item_name=f"FO Akril {_n}", unit="kg", price_per_unit=3000, category="Kimyoviy qo'shimchalar"),
    "m2": Inventory(company_id=1, item_name=f"FO Mel {_n}", unit="kg", price_per_unit=1000, category="Qattiq qotishmalar"),
    "m3": Inventory(company_id=1, item_name=f"FO Penoplast 25 {_n}", unit="dona", price_per_unit=500000, category="Penoplast",
                    is_penoplast=True, volume_per_unit=1.4),
    "m4": Inventory(company_id=1, item_name=f"FO Lenta {_n}", unit="metr", price_per_unit=200, stock_quantity=8.253333333333332),
}
_sup = Supplier(company_id=1, name=f"FO Ta'minotchi {_n}")
_rc1 = Recipe(company_id=1, name=f"FO retsept band {_n}")
_rc2 = Recipe(company_id=1, name=f"FO retsept bo'sh {_n}")
_prj = Project(company_id=1, project_number=f"FO-{_n}", project_name="FO loyiha", client_name="FO mijoz")
_db.add_all(list(M.values()) + [_sup, _rc1, _rc2, _prj])
_db.commit()
_ord = Order(company_id=1, project_id=_prj.id, order_number=f"FO-{_n}-1", order_type=OrderType.PRODUCT, status=OrderStatus.IN_PROGRESS)
_db.add(_ord)
_db.commit()
_db.add(OrderItem(company_id=1, order_id=_ord.id, name="FO detal", recipe_id=_rc1.id))
_db.commit()
ID = {k: v.id for k, v in M.items()}
ID.update({"sup": _sup.id, "rc1": _rc1.id, "rc2": _rc2.id})
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_l = C.post("/login", data={"username": ADMIN, "password": PAROL}, follow_redirects=False).status_code


def kirim(qatorlar, paid=0, transport=0, hujjat="FO"):
    r = C.post("/api/inventory/receipt", json={
        "items": [{"inventory_id": ID[k], "quantity": q, "price_per_unit": p} for k, q, p in qatorlar],
        "supplier_id": ID["sup"], "document_number": hujjat, "paid_now": paid, "transport_cost": transport, "tushirish_cost": 0,
        "yuklash_cost": 0, "boshqa_cost": 0, "add_to_cost": True, "notes": hujjat, "production_type": "umumiy"})
    return r.status_code, js(r)


K = {
    "R1": kirim([("m1", 10, 3000), ("m2", 10, 1000)], paid=40000, hujjat="R1"),
    "R2": kirim([("m1", 2, 3000), ("m2", 4, 1000)], paid=3000, hujjat="R2"),
    "R3": kirim([("m1", 1, 3000), ("m2", 1, 1000)], transport=2000, hujjat="R3"),
    "R4": kirim([("m2", 3, 1000)], hujjat="R4"),
    "R5": kirim([("m1", 1, 3000), ("m2", 2, 1000)], hujjat="R5"),
}
check("D0 kirdi; beshta kirim hujjati (to'langan, qisman, xarajatli, yagona qatorli to'lovsiz, oddiy)", _l == 302
      and all(v[0] == 200 for v in K.values()), {k: (v[0], str(v[1])[:100]) for k, v in K.items()})


def xaridlar():
    s = SessionLocal()
    try:
        return {p.id: (p.receipt_id, p.inventory_id, float(p.quantity)) for p in s.query(InventoryPurchase).filter(
            InventoryPurchase.supplier_id == ID["sup"]).all()}
    finally:
        s.close()


def qarz():
    s = SessionLocal()
    try:
        return crud.get_supplier_debt(s, ID["sup"], company_id=1)
    finally:
        s.close()


X0 = xaridlar()
RID = {}
for _pid, (_rid, _iid, _q) in sorted(X0.items()):
    RID.setdefault(_rid, []).append(_pid)
_rids = sorted(RID)
R = dict(zip(["R1", "R2", "R3", "R4", "R5"], _rids))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. API")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_q0 = qarz()
_a = {}
for _k in ("R1", "R3"):
    _r = C.delete(f"/api/inventory/purchases/{RID[R[_k]][0]}")
    _a[_k] = (_r.status_code, (js(_r) or {}).get("detail") if isinstance(js(_r), dict) else js(_r))
check("A1 to'langan hujjat qatori — 409 `receipt_line_locked` (sababi: to'lov 40 000), hujjat raqami bilan",
      _a["R1"][0] == 409 and isinstance(_a["R1"][1], dict) and _a["R1"][1].get("type") == "receipt_line_locked"
      and _a["R1"][1].get("receipt_id") == R["R1"] and "40 000 so'm to'langan" in _a["R1"][1].get("message", "").replace("\xa0", " ")
      and "Kirim hujjatini bekor qilish" in _a["R1"][1].get("message", ""), _a["R1"])
check("A2 qo'shimcha xarajatli hujjat — 409 (qo'shimcha xarajatlar 2 000)",
      _a["R3"][0] == 409 and "qo'shimcha xarajatlar bor (2 000" in (_a["R3"][1] or {}).get("message", "").replace("\xa0", " "), _a["R3"])
check("A3 rad etilgach hech narsa o'zgarmadi (xaridlar, ta'minotchi qarzi)", xaridlar() == X0 and qarz() == _q0, (qarz(), _q0))
_s = SessionLocal()
_m2_r4 = float(_s.query(Inventory.stock_quantity).filter(Inventory.id == ID["m2"]).scalar())
_s.close()
_r4 = C.delete(f"/api/inventory/purchases/{RID[R['R4']][0]}")
_s = SessionLocal()
_r4_keyin = (float(_s.query(Inventory.stock_quantity).filter(Inventory.id == ID["m2"]).scalar()),
             _s.query(InventoryReceipt.id).filter(InventoryReceipt.id == R["R4"]).scalar(),
             _s.query(InventoryPurchase.id).filter(InventoryPurchase.receipt_id == R["R4"]).count(),
             _s.query(ActivityLog.id).filter(ActivityLog.entity_type == "inventory_receipt", ActivityLog.entity_id == R["R4"],
                                             ActivityLog.action == "deleted").count())
_s.close()
check("A3b to'lovsiz, xarajatsiz hujjatning YAGONA qatori — 200, butun hujjat bekor (`receipt_cancelled`): qoldiq −3, hujjat qatori "
      "qolmaydi, audit yozildi; boshqa hujjatlar tegilmadi",
      _r4.status_code == 200 and (js(_r4) or {}).get("receipt_cancelled") == R["R4"]
      and abs(_m2_r4 - _r4_keyin[0] - 3) < 1e-9 and _r4_keyin[1:] == (None, 0, 1)
      and {k: v for k, v in xaridlar().items() if v[0] != R["R4"]} == {k: v for k, v in X0.items() if v[0] != R["R4"]},
      (_r4.status_code, js(_r4), _m2_r4, _r4_keyin))
_s = SessionLocal()
_m2_oldin = float(_s.query(Inventory.stock_quantity).filter(Inventory.id == ID["m2"]).scalar())
_s.close()
_r5 = C.delete(f"/api/inventory/purchases/{RID[R['R5']][1]}")
_s = SessionLocal()
_m2_keyin = float(_s.query(Inventory.stock_quantity).filter(Inventory.id == ID["m2"]).scalar())
_s.close()
check("A4 to'lovsiz, xarajatsiz, ko'p qatorli hujjatdan qator — avvalgidek o'chadi (200), qoldiq −2",
      _r5.status_code == 200 and abs(_m2_oldin - _m2_keyin - 2) < 1e-9, (_r5.status_code, js(_r5), _m2_oldin, _m2_keyin))
_rd1 = C.delete(f"/api/recipes/{ID['rc1']}")
_rd2 = C.delete(f"/api/recipes/{ID['rc2']}")
_s = SessionLocal()
_rb = (_s.query(Recipe.id).filter(Recipe.id == ID["rc1"]).scalar(), _s.query(Recipe.id).filter(Recipe.id == ID["rc2"]).scalar())
_s.close()
check("A5 ishlatilgan retsept — 409 (sababi: «1 ta buyurtma detalida»), bazada qoladi; ishlatilmagan — o'chadi (200)",
      _rd1.status_code == 409 and "1 ta buyurtma detalida" in str(js(_rd1)) and _rd2.status_code == 200 and _rb == (ID["rc1"], None),
      (_rd1.status_code, js(_rd1), _rd2.status_code, _rb))
_h = js(C.get(f"/api/suppliers/{ID['sup']}/history?page=1&page_size=50")) or {}
_hol = {}
for _p in _h.get("purchases", []):
    _hol.setdefault(_p.get("receipt_id"), set()).add(_p.get("kirimda_tolangan"))
check("A6 ta'minotchi tarixi: qatorda `receipt_id` va kirimda to'langan holati — R1 «tolangan», R2 «qisman», R3 / R5 «nasiya» (R4 — bekor)",
      _hol.get(R["R1"]) == {"tolangan"} and _hol.get(R["R2"]) == {"qisman"} and _hol.get(R["R3"]) == {"nasiya"}
      and R["R4"] not in _hol and _hol.get(R["R5"]) == {"nasiya"}, _hol)
_t1 = js(C.post("/api/inventory/low-stock-alert")) or {}
_t2 = js(C.post("/api/inventory/full-stock-report")) or {}
check("A7 Telegram sozlanmagan: «kam qoldiq» va «ombor hisoboti» — `sent: false`, «YUBORILMADI» va qayerda sozlanadi",
      _t2.get("sent") is False and "YUBORILMADI" in _t2.get("message", "") and "Telegram bot" in _t2.get("message", "")
      and (_t1.get("sent") is False), (_t1, _t2))
_TG = []
_asl_post = main._tg_post_message
main._tg_post_message = lambda token, chat, text, *a, **k: _TG.append((token, chat, text[:40]))
_s = SessionLocal()
crud.set_setting(_s, "telegram_bot_token", "123:FO", company_id=1)
crud.set_setting(_s, "telegram_chat_id", "-100777", company_id=1)
_s.close()
try:
    _t3 = js(C.post("/api/inventory/full-stock-report")) or {}

    def _xato(*a, **k):
        raise RuntimeError("Telegram javob bermadi")
    main._tg_post_message = _xato
    _t4 = js(C.post("/api/inventory/full-stock-report")) or {}
finally:
    main._tg_post_message = _asl_post
check("A8 Telegram sozlangan: yuborildi — `sent: true` («Telegramga yuborildi»); Telegram xato qaytarsa — `sent: false`",
      _t3.get("sent") is True and "Telegramga yuborildi" in _t3.get("message", "") and len(_TG) == 1 and _t4.get("sent") is False,
      (_t3, _t4, _TG))

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


def kontekst(user=ADMIN, w=1440, h=900, tel=False):
    ctx = br.new_context(viewport={"width": w, "height": h}, is_mobile=tel, has_touch=tel, timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
    pg = ctx.new_page()
    pg.set_default_timeout(10000)
    pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
    pg.on("request", lambda q: SOROV.append((q.method, q.url.replace(B, ""), q.post_data)) if "/api/" in q.url else None)
    pg.goto(B + "/login")
    pg.fill("input[name=username]", user)
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    return ctx, pg


def tasdiq_matni(pg):
    pg.wait_for_function("() => { const m = document.getElementById('ccModal'); return m && getComputedStyle(m).display !== 'none'; }")
    return pg.evaluate("() => document.getElementById('ccModalMessage').textContent").replace("\xa0", " ")


def tasdiqla(pg, ha=True):
    pg.click("#ccModalOk" if ha else "#ccModalCancel")
    pg.wait_for_timeout(150)


def qatorlar(pg):
    return pg.evaluate("() => [...document.querySelectorAll('#matList .mat-row')].filter(r => r.style.display !== 'none').map(r => r.dataset.name)")


if br:
    ctx, pg = kontekst()
    try:
        pg.goto(B + "/inventory", wait_until="networkidle")
        _b1 = pg.evaluate("""() => ({bosh: (document.querySelector('.mat-bosh') || {}).innerText || '',
            boshKor: document.querySelector('.mat-bosh') ? getComputedStyle(document.querySelector('.mat-bosh')).display : 'yoq',
            kirim: !!document.querySelector('a[href="/suppliers/receive"]'),
            tg: [...document.querySelectorAll('button')].filter(b => /Telegram/.test(b.textContent)).length,
            sms: [...document.querySelectorAll('button')].filter(b => /SMS/.test(b.textContent)).length,
            tugma: Math.round(document.querySelector('.mat-col-min .btn-xs').getBoundingClientRect().height)})""")
        check("B1 Omborxona (1440): ustun nomlari (Material, Qoldiq, Minimal chegara, Holat, 1 birlik narxi), «Kirim qilish», Telegram tugmalari "
              "(SMS yo'q), chegara tugmasi ≥ 32 px", _b1["boshKor"] == "grid" and all(x in _b1["bosh"].upper() for x in
              ("MATERIAL", "QOLDIQ", "MINIMAL CHEGARA", "HOLAT", "1 BIRLIK NARXI")) and _b1["kirim"] and _b1["tg"] == 2 and _b1["sms"] == 0
              and _b1["tugma"] >= 32, _b1)
        _f = pg.evaluate("() => [...document.querySelectorAll('#catFilter option')].map(o => [o.value, o.textContent.trim()])")
        check("B2 toifa filtri — omborda BOR toifalar: Penoplast, Kimyoviy, «Mineral qo'shimchalar» (kodi «Qattiq qotishmalar»), toifasiz",
              ["Qattiq qotishmalar", "⛱️ Mineral qo'shimchalar"] in _f and ["Penoplast", "🧊 Penoplast"] in _f
              and any(v == "__yoq" for v, t in _f) and not any("Minerallar" in t for v, t in _f), _f)
        pg.select_option("#catFilter", "__yoq")
        _yoq = qatorlar(pg)
        pg.select_option("#catFilter", "Qattiq qotishmalar")
        _min = qatorlar(pg)
        _badge = pg.evaluate("""(n) => { const r = [...document.querySelectorAll('#matList .mat-row')].find(x => x.dataset.name === n);
                                        return r.querySelector('.cat-badge').textContent.trim(); }""", M["m2"].item_name.lower())
        pg.select_option("#catFilter", "")
        check("B3 filtr ishlaydi: «toifasiz» — Lenta, «Mineral» — Mel; belgi ham «Mineral qo'shimchalar»",
              M["m4"].item_name.lower() in _yoq and M["m2"].item_name.lower() not in _yoq and _min == [M["m2"].item_name.lower()]
              and _badge == "Mineral qo'shimchalar", (_yoq, _min, _badge))
        _asl = qatorlar(pg)
        pg.select_option("#sortFilter", "qty_asc")
        _q = qatorlar(pg)
        pg.select_option("#sortFilter", "name")
        _nm = qatorlar(pg)
        pg.select_option("#sortFilter", "tur")
        _tur = qatorlar(pg)
        check("B4 saralash: «Nomi bo'yicha» — alifbo; «Turi bo'yicha» — asl tartib QAYTADI (ilgari qoldiq bo'yicha saralangach qaytmasdi)",
              _q != _asl and _nm == sorted(_asl) and _tur == _asl, (_asl, _q, _nm, _tur))
        pg.evaluate("""(n) => { const r = [...document.querySelectorAll('#matList .mat-row')].find(x => x.dataset.name === n);
                              r.querySelector('.act-btn.out').click(); }""", M["m4"].item_name.lower())
        _cq = pg.evaluate("() => document.getElementById('chiqim-current').textContent").replace("\xa0", " ")
        pg.evaluate("() => closeChiqimModal()")
        check("B5 chiqim oynasida qoldiq — son qoidasi bilan («8,253 metr», xom «8.253333333333332» emas)", _cq == "8,253 metr", _cq)
        pg.evaluate("""(n) => { const r = [...document.querySelectorAll('#matList .mat-row')].find(x => x.dataset.name === n);
                              r.querySelector('.act-btn.danger').click(); }""", M["m4"].item_name.lower())
        _m = tasdiq_matni(pg)
        tasdiqla(pg, False)
        check("B6 material o'chirish tasdig'i — NOMI va qoldiq ogohlantirishi («Omborda hali 8,253 metr bor»); «Bekor» — so'rov yo'q",
              M["m4"].item_name in _m and "Omborda hali 8,253 metr bor" in _m and not any(x[0] == "DELETE" for x in SOROV), _m)
        del SOROV[:]
        pg.evaluate("""(n) => { const r = [...document.querySelectorAll('#matList .mat-row')].find(x => x.dataset.name === n);
                              r.querySelector('.cat-badge').click(); }""", M["m4"].item_name.lower())
        pg.wait_for_timeout(300)
        _pr = pg.evaluate("""() => { const i = [...document.querySelectorAll('input')].find(x => x.offsetParent && x.closest('[id*="rompt"], .cp-modal, #customPromptOverlay'));
                                    return i ? i.id : null; }""")
        pg.keyboard.press("Control+A")
        pg.keyboard.type("minerallar")
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(700)
        pg.wait_for_load_state("load")
        _put = [json.loads(x[2] or "{}") for x in SOROV if x[0] == "PUT" and re.match(r"^/api/inventory/\d+$", x[1])]
        check("B7 toifani o'zgartirish: «minerallar» → kod «Qattiq qotishmalar» (yangi, uchinchi nom paydo bo'lmaydi)",
              _put == [{"category": "Qattiq qotishmalar"}], (_pr, _put, SOROV[-3:]))
        # kirim hujjati — qatorni o'chirish (to'langan hujjat)
        pg.goto(B + "/inventory", wait_until="load")
        pg.wait_for_timeout(500)
        pg.evaluate("() => openPurchaseHistory()")
        pg.wait_for_timeout(800)
        pg.evaluate(f"() => openPhDrawer({R['R1']})")
        del SOROV[:]
        pg.evaluate("() => document.querySelector('#phDrawerBody .mv-row button').click()")
        _m1 = tasdiq_matni(pg)
        tasdiqla(pg, True)
        _m2 = tasdiq_matni(pg)
        tasdiqla(pg, False)
        pg.wait_for_timeout(300)
        check("B8 to'langan hujjat qatorini o'chirish: server sababi oynada («to'langan … butun hujjatni bekor qiling») va «Kirim hujjatini "
              "bekor qilish» taklifi; «Yopish» — hech narsa o'chmaydi", "bekor qilasizmi" in _m1 and "to'langan" in _m2
              and "butun hujjatni bekor qiling" in _m2 and xaridlar() == {k: v for k, v in X0.items() if k != RID[R["R5"]][1] and v[0] != R["R4"]}, (_m1, _m2))
    except Exception as _e:                # noqa: BLE001
        check("B! Omborxona ssenariysi", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    # ── Menejer: ruxsatsiz boshqaruvlar yo'q ──
    ctx, pg = kontekst(MENEJER)
    try:
        pg.goto(B + "/inventory", wait_until="networkidle")
        _mn = pg.evaluate("""() => ({fayl: document.querySelectorAll('.mat-thumb input[type=file]').length,
            chegara: document.querySelectorAll('button[onclick*="editMinStock"]').length,
            toifa: document.querySelectorAll('.cat-badge[onclick]').length,
            asosiy: document.querySelectorAll('button[onclick*="setDefaultPenoplast"]').length,
            tg: [...document.querySelectorAll('button')].filter(b => /Telegram|SMS/.test(b.textContent)).length,
            qator: document.querySelectorAll('#matList .mat-row').length})""")
        check("B9 Menejer (material — faqat ko'rish): rasm yuklash, chegara, toifa, «Asosiy qilish», Telegram tugmalari YO'Q",
              _mn["qator"] >= 4 and _mn["fayl"] == 0 and _mn["chegara"] == 0 and _mn["toifa"] == 0 and _mn["asosiy"] == 0 and _mn["tg"] == 0, _mn)
    except Exception as _e:                # noqa: BLE001
        check("B! Menejer ssenariysi", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    # ── bo'sh korxona ──
    ctx, pg = kontekst("fomb_b")
    try:
        pg.goto(B + "/inventory", wait_until="networkidle")
        _bo = pg.evaluate("() => ({t: (document.getElementById('invBosh') || {}).innerText || '', bosh: !!document.querySelector('.mat-bosh')})")
        check("B10 bo'sh korxona Omborxonasi — yo'riqnoma («Omborda hali material yo'q … Kirim qilish → Yangi material yozaman»)",
              "Omborda hali material yo'q" in _bo["t"] and "Yangi material yozaman" in _bo["t"] and not _bo["bosh"], _bo)
    except Exception as _e:                # noqa: BLE001
        check("B! bo'sh korxona ssenariysi", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    # ── Kirim sahifasi, Ta'minotchilar, Retseptlar ──
    ctx, pg = kontekst()
    try:
        pg.goto(B + f"/suppliers/receive?supplier_id={ID['sup']}", wait_until="networkidle")
        pg.wait_for_timeout(800)
        _sr = pg.evaluate("""() => ({jami: [...document.querySelectorAll('.rcv-stat-label')].map(x => x.textContent.trim()),
            fayl: document.body.innerText.includes('Hujjat fayli'),
            holat: [...document.querySelectorAll('#rcv-history-body td.kirim-holat')].map(x => x.textContent.trim())})""")
        check("B11 Kirim sahifasi: «Jami xarid» (nasiya emas), «Hujjat fayli» yo'q, tarixda «To'langan» / «Qisman» / «Nasiya»",
              "Jami xarid" in _sr["jami"] and "Jami nasiya" not in _sr["jami"] and not _sr["fayl"]
              and {"To'langan", "Qisman", "Nasiya"} <= set(_sr["holat"]), _sr)
        # ta'minotchi filtri (shu ta'minotchidan olinganlar) — o'chiriladi: penoplast hali undan olinmagan
        pg.evaluate(f"""() => {{ supplierFilterActive = false; renderInvDropdown(); const s = document.getElementById('ap-item');
                                s.value = '{ID["m3"]}'; s.dispatchEvent(new Event('change')); }}""")
        _vol = pg.evaluate("() => ({v: document.getElementById('ap-volume').value, kor: getComputedStyle(document.getElementById('ap-volume-wrap')).display})")
        check("B12 penoplast tanlansa blok hajmi O'ZI yoziladi (1,4 m³ — shu materialniki)", _vol == {"v": "1,4", "kor": "block"}, _vol)
        pg.fill("#sup-quickpay-amount", "5000")
        del SOROV[:]
        pg.evaluate("() => { window.__qp = quickPaySupplier(); }")
        _qm = tasdiq_matni(pg)
        tasdiqla(pg, False)
        pg.wait_for_timeout(300)
        check("B13 eski qarzni tez to'lash — tasdiq (ta'minotchi nomi va summa); «Bekor» — to'lov yozilmaydi",
              M and "FO Ta'minotchi" in _qm and "5 000 so'm eski qarz to'lovi" in _qm
              and not any(x[0] == "POST" and "/payment" in x[1] for x in SOROV), (_qm, SOROV))
        pg.goto(B + "/suppliers", wait_until="networkidle")
        pg.wait_for_timeout(500)
        pg.evaluate("() => document.querySelector('.sup-row .sup-tarix').click()")
        pg.wait_for_function("() => getComputedStyle(document.getElementById('historyModal')).display !== 'none'")
        _hm = pg.evaluate("() => document.getElementById('historyModal').innerText.length > 50")
        check("B14 Ta'minotchilar: qatordagi «Tarix» — xaridlar va to'lovlar oynasi ochiladi (sahifa almashmaydi)",
              _hm and pg.url.endswith("/suppliers"), pg.url)
        pg.goto(B + "/recipes", wait_until="networkidle")
        pg.evaluate(f"""() => document.querySelector('button[onclick^="deleteRecipe({ID["rc1"]},"]').click()""")
        _rm = tasdiq_matni(pg)
        tasdiqla(pg, True)
        pg.wait_for_timeout(700)
        _rt = pg.evaluate("() => { const o = document.getElementById('recpToastOverlay'); return o ? o.innerText : ''; }")
        check("B15 ishlatilgan retseptni o'chirish: tasdiqda nomi, server rad etsa — SABABI («ishlatilgan (1 ta buyurtma detalida)»)",
              "FO retsept band" in _rm and "ishlatilgan (1 ta buyurtma detalida)" in _rt, (_rm, _rt))
    except Exception as _e:                # noqa: BLE001
        check("B! Kirim / Ta'minotchi / Retsept ssenariysi", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    # ── telefon 390 px: Omborxona ──
    ctx, pg = kontekst(w=390, h=844, tel=True)
    try:
        pg.goto(B + "/inventory", wait_until="networkidle")
        pg.wait_for_timeout(400)
        _ph = pg.evaluate("""() => ({birinchi: Math.round(document.querySelector('#matList .mat-row').getBoundingClientRect().top),
            bosh: getComputedStyle(document.querySelector('.mat-bosh')).display, kenglik: document.documentElement.scrollWidth})""")
        check("B16 telefon (390 px): birinchi material birinchi ekranda (yuqori chegarasi < 844), ustun nomlari yashirin, gorizontal toshish yo'q",
              0 < _ph["birinchi"] < 844 and _ph["bosh"] == "none" and _ph["kenglik"] <= 390, _ph)
    except Exception as _e:                # noqa: BLE001
        check("B! telefon ssenariysi", False, f"{type(_e).__name__}: {_e}")
    finally:
        ctx.close()
    check("B17 JS xatosi yo'q", not JS_XATO, JS_XATO)
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
