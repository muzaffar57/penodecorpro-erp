#!/usr/bin/env python3
"""
test_telegram_tenant.py — Telegram xabarnomalari va dashboard o'qishlari
bo'yicha korxonalararo darvoza (9-sizish).

NIMA UCHUN KERAK (2026-09-21, hammasi asl kodda HTTP orqali O'LCHANGAN)
-----------------------------------------------------------------------
1. TELEGRAM (filtr YONIQ holatda HAM): `main._tenant_telegram()` korxonani
   YANGI ochilgan sessiyadan (`tenant_context.get_current_company(_db)`)
   o'qirdi — u doim bo'sh. `company_id` bermagan 13 marshrutda korxona
   hech qachon aniqlanmas va xabar muhit o'zgaruvchisidagi (1-korxona)
   chatga ketardi. O'lchov: B o'z botini sozlagan bo'lsa ham B ning
   buyurtma raqami va ombor qoldiqlari A ning chatiga, A ning boti orqali
   ketdi. `_send_telegram_to_qoplamachi` da xuddi shu nuqson — B ning
   qoplama topshirig'i (mijoz, loy kg) A ning qoplamachisiga.
2. MUHIT ZAXIRASI: o'z boti yo'q HAR QANDAY korxona xabari tizim egasining
   chatiga tushardi (hatto `company_id` berilsa ham, masalan cron).
   Boti bor-u chati yo'q korxona — qattiq yozilgan `TELEGRAM_COATING_ID` ga.
3. O'QISH (filtr o'chiq): `check_low_stock`, `get_today_tasks`,
   `get_dashboard_stats` sanoqlari va `crud.get_low_stock_items(db)` —
   korxona filtrisiz. B `/api/warnings/low-stock`, `/api/dashboard/*` da
   A ning xomashyo nomlarini ko'rardi; Telegram ogohlantirishiga BARCHA
   korxonalarning qoldig'i aralashardi.

QAMROV
------
1. Ildiz: `_tenant_telegram` qoidasi (None / 1-korxona / boti bor / yo'q)
2. HTTP: A, B (boti bor), C (boti yo'q) — buyurtma + qoplama xabari
3. Yuk xati (mijoz/usta) — buyurtma korxonasining boti
4. O'qish marshrutlari — begona nom yo'q, sanoqlar faqat o'ziniki
5. Statik: `current_user` bor har bir funksiyadagi har bir Telegram
   chaqiruvi `company_id=` ni aniq beradi

ISHLATISH
---------
    python tools/test_telegram_tenant.py
    TENANT_FILTER=1 python tools/test_telegram_tenant.py

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_DB = os.path.join(tempfile.gettempdir(), "telegram_tenant_test.db")
if os.path.exists(_DB):
    os.remove(_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["TELEGRAM_BOT_TOKEN"] = "ENV_TOKEN"
os.environ["BACKUP_TELEGRAM_CHAT_ID"] = "ENV_CHAT"
os.environ["QOPLAMACHI_TELEGRAM_CHAT_ID"] = "ENV_QOP"

import io                                          # noqa: E402
import ast                                         # noqa: E402
import json                                        # noqa: E402
import types                                       # noqa: E402
import contextlib                                  # noqa: E402
import urllib.request                              # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402,F401
    import crud, auth, schemas, services           # noqa: E402

from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import UserRole, Inventory             # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

db = SessionLocal()
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  \u2713 {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  \u2717 {label}   {detail}")


def section(t):
    print(f"\n--- {t} ---")


def safe(fn, *a, **k):
    """Chaqiruv xato bersa — ("XATO", matn): tekshiruv yiqiladi, lekin
    skript to'xtamaydi, keyingi qulflar ham ishlaydi."""
    try:
        return fn(*a, **k)
    except Exception as e:                 # noqa: BLE001
        return ("XATO", f"{type(e).__name__}: {e}")


# Telegram API ga hech narsa chiqmaydi — hamma so'rov shu yerda ushlanadi.
SENT = []


class _Resp:
    def read(self):
        return b'{"ok": true}'


def _fake_urlopen(req, timeout=5):
    url = req.full_url
    token = url.split("/bot", 1)[1].split("/", 1)[0]
    body = req.data or b""
    try:
        d = json.loads(body.decode("utf-8"))
        chat, text = str(d.get("chat_id")), d.get("text", "")
    except Exception:                      # multipart (hujjat)
        s = body.decode("utf-8", "replace")
        chat = "?"
        if 'name="chat_id"' in s:
            chat = s.split('name="chat_id"', 1)[1].split("\r\n\r\n", 1)[1].split("\r\n", 1)[0]
        text = s
    SENT.append((token, chat, text))
    return _Resp()


urllib.request.urlopen = _fake_urlopen

# ══════════════════════════════════════════════════════════════
# Tayyorgarlik: A (1, o'z boti YO'Q — muhit), B (2, o'z boti BOR),
# C (3, o'z boti YO'Q)
# ══════════════════════════════════════════════════════════════
for _cid, _nm in ((2, "Test B"), (3, "Test C")):
    if not db.query(Company).filter(Company.id == _cid).first():
        db.add(Company(id=_cid, name=_nm))
db.commit()

with contextlib.redirect_stdout(_quiet):
    for u, c in (("AAA_user", 1), ("BBB_user", 2), ("CCC_user", 3)):
        auth.create_user(db, u, "Parol123!", UserRole.ADMIN, u[:3], company_id=c)
    crud.set_setting(db, "telegram_bot_token", "B_TOKEN", company_id=2)
    crud.set_setting(db, "telegram_chat_id", "B_CHAT", company_id=2)
    crud.set_setting(db, "telegram_qoplamachi_chat_id", "B_QOP", company_id=2)

MARK = {1: "AAA_KAM", 2: "BBB_KAM", 3: "CCC_KAM"}
for _cid, _m in MARK.items():
    db.add(Inventory(company_id=_cid, item_name=f"{_m}_XOMASHYO", unit="kg",
                     stock_quantity=1.0, min_stock=50.0, price_per_unit=1))
db.commit()

PROJ = {}
with contextlib.redirect_stdout(_quiet):
    for _cid, _p in ((1, "AAA"), (2, "BBB"), (3, "CCC")):
        PROJ[_cid] = crud.create_project(db, schemas.ProjectCreate(
            project_name=f"{_p}_LOYIHA", client_name=f"{_p}_MIJOZ"),
            company_id=_cid).id


def login(user):
    c = TestClient(main.app, base_url="https://testserver",
                   raise_server_exceptions=False)
    r = c.post("/login", data={"username": user, "password": "Parol123!"},
               follow_redirects=False)
    assert r.status_code == 302, f"{user} login bo'lmadi: {r.status_code}"
    return c


CL = {1: login("AAA_user"), 2: login("BBB_user"), 3: login("CCC_user")}
FOREIGN = {1: ("BBB", "CCC"), 2: ("AAA", "CCC"), 3: ("AAA", "BBB")}


def has_foreign(cid, text):
    return any(f in text for f in FOREIGN[cid])


# ══════════════════════════════════════════════════════════════
section("1. Ildiz: _tenant_telegram qoidasi")
# ══════════════════════════════════════════════════════════════
_T = {c: safe(main._tenant_telegram, c) for c in (None, 1, 2, 3)}
check("company_id=None (tizim xabari) → muhit sozlamasi",
      _T[None] == ("ENV_TOKEN", ["ENV_CHAT"]), str(_T[None]))
check("1-korxona, o'z boti yo'q → muhit sozlamasi",
      _T[1] == ("ENV_TOKEN", ["ENV_CHAT"]), str(_T[1]))
check("B, o'z boti bor → B boti va chati",
      _T[2] == ("B_TOKEN", ["B_CHAT"]), str(_T[2]))
check("C, o'z boti yo'q → HECH NARSA (muhitga tushmaydi)",
      _T[3] == ("", []), str(_T[3]))

SENT.clear()
with contextlib.redirect_stdout(_quiet):
    _r = [safe(main._send_telegram, "C_SIRLI_XABAR", company_id=3),
          safe(main._send_telegram_to, "12345", "C_SIRLI_XABAR", company_id=3),
          safe(main._send_telegram_to_qoplamachi, "C_SIRLI_XABAR", company_id=3)]
check("C nomidan _send_telegram / _to / _qoplamachi — xatosiz, hech narsa yuborilmadi",
      SENT == [] and not any(isinstance(x, tuple) for x in _r),
      f"{SENT} {_r}")

# B boti bor-u, chati kiritilmagan: qattiq yozilgan zaxira chatga TUSHMAYDI
with contextlib.redirect_stdout(_quiet):
    crud.set_setting(db, "telegram_chat_id", "", company_id=2)
SENT.clear()
with contextlib.redirect_stdout(_quiet):
    safe(main._send_telegram, "B_CHATSIZ", company_id=2)
check("B boti bor, chati yo'q → TELEGRAM_COATING_ID ga yuborilmadi",
      SENT == [], str(SENT))
with contextlib.redirect_stdout(_quiet):
    crud.set_setting(db, "telegram_chat_id", "B_CHAT", company_id=2)
# B boti bor-u, qoplamachi chati kiritilmagan: B ning boti tizim egasining
# qoplamachisiga (muhit QOPLAMACHI_TELEGRAM_CHAT_ID) YOZMASLIGI kerak.
with contextlib.redirect_stdout(_quiet):
    crud.set_setting(db, "telegram_qoplamachi_chat_id", "", company_id=2)
SENT.clear()
with contextlib.redirect_stdout(_quiet):
    safe(main._send_telegram_to_qoplamachi, "B_QOPSIZ", company_id=2)
check("B boti bor, qoplamachi chati yo'q → muhit qoplamachisiga yuborilmadi",
      SENT == [], str(SENT))
with contextlib.redirect_stdout(_quiet):
    crud.set_setting(db, "telegram_qoplamachi_chat_id", "B_QOP", company_id=2)
SENT.clear()
with contextlib.redirect_stdout(_quiet):
    safe(main._send_telegram_to_qoplamachi, "A_QOP", company_id=1)
check("1-korxona qoplamachisi (sozlamasiz) avvalgidek muhit chatiga",
      [(t, c) for t, c, _ in SENT] == [("ENV_TOKEN", "ENV_QOP")], str(SENT))
SENT.clear()
with contextlib.redirect_stdout(_quiet):
    safe(main._send_telegram, "TIZIM", company_id=None)
check("Tizim xabari (None) avvalgidek muhit chatiga",
      SENT == [("ENV_TOKEN", "ENV_CHAT", "TIZIM")], str(SENT))


# ══════════════════════════════════════════════════════════════
section("2. HTTP: buyurtma + qoplama xabari (A, B, C)")
# ══════════════════════════════════════════════════════════════
EXPECT_TOKEN = {1: "ENV_TOKEN", 2: "B_TOKEN"}
EXPECT_CHATS = {1: {"ENV_CHAT", "ENV_QOP"}, 2: {"B_CHAT", "B_QOP"}}
ORDER_ID = {}
for cid in (1, 2, 3):
    SENT.clear()
    with contextlib.redirect_stdout(_quiet):
        r = CL[cid].post("/api/orders", json={
            "project_id": PROJ[cid], "order_type": "service", "items": [],
            "agreed_amount": 1000 + cid, "notes": f"tg_probe_{cid}"})
    check(f"[{cid}] POST /api/orders → 200", r.status_code == 200,
          f"{r.status_code} {r.text[:200]}")
    ORDER_ID[cid] = r.json().get("id") if r.status_code == 200 else 0
    with contextlib.redirect_stdout(_quiet):
        r2 = CL[cid].post(f"/api/orders/{ORDER_ID[cid]}/coating-notify",
                          params={"loy_kg": 10})
    check(f"[{cid}] coating-notify → 200", r2.status_code == 200,
          f"{r2.status_code} {r2.text[:200]}")
    blob = " | ".join(t for _, _, t in SENT)
    if cid == 3:
        check("[3] C (boti yo'q) — HECH QANDAY xabar yuborilmadi",
              SENT == [], str([(a, b) for a, b, _ in SENT]))
        continue
    check(f"[{cid}] kamida 3 xabar (ombor, qoplama guruhi, qoplamachi)",
          len(SENT) >= 3, str([(a, b) for a, b, _ in SENT]))
    check(f"[{cid}] hammasi o'z boti orqali ({EXPECT_TOKEN[cid]})",
          SENT and all(tok == EXPECT_TOKEN[cid] for tok, _, _ in SENT),
          str([(a, b) for a, b, _ in SENT]))
    check(f"[{cid}] hammasi o'z chatlariga {sorted(EXPECT_CHATS[cid])}",
          SENT and {ch for _, ch, _ in SENT} == EXPECT_CHATS[cid],
          str({ch for _, ch, _ in SENT}))
    check(f"[{cid}] o'z qoldig'i xabarda bor ({MARK[cid]})",
          MARK[cid] in blob, blob[:200])
    check(f"[{cid}] begona korxona nomi xabarlarda YO'Q",
          not has_foreign(cid, blob), blob[:300])
    check(f"[{cid}] qoplamachiga o'z mijozi ketdi",
          any(f"{('AAA', 'BBB')[cid - 1]}_MIJOZ" in t
              for _, ch, t in SENT if ch in ("ENV_QOP", "B_QOP")),
          str([(b, t[:60]) for _, b, t in SENT]))


# ══════════════════════════════════════════════════════════════
section("3. Yuk xati — buyurtma korxonasining boti")
# ══════════════════════════════════════════════════════════════
def _stub_delivery(cid, tg):
    proj = types.SimpleNamespace(notes=f"tg_id={tg}", client_name=f"{cid}_MIJOZ")
    order = types.SimpleNamespace(company_id=cid, project=proj, master=None,
                                  order_number=f"ORD-{cid}")
    return types.SimpleNamespace(order=order, items=[], delivery_number=f"D-{cid}")


_orig_get_delivery = crud.get_delivery
try:
    for cid, tg, exp in ((2, "900002", "B_TOKEN"), (1, "900001", "ENV_TOKEN"),
                         (3, "900003", None)):
        crud.get_delivery = (lambda _c, _t: (lambda _db, _id, **k: _stub_delivery(_c, _t)))(cid, tg)
        SENT.clear()
        with contextlib.redirect_stdout(_quiet):
            safe(main._send_delivery_pdf_to_customer, db, 1)
        if exp is None:
            check(f"[{cid}] yuk xati — boti yo'q korxona: hech narsa yuborilmadi",
                  SENT == [], str([(a, b) for a, b, _ in SENT]))
        else:
            check(f"[{cid}] yuk xati mijozga {exp} orqali",
                  SENT and all(t == exp and ch == tg for t, ch, _ in SENT),
                  str([(a, b) for a, b, _ in SENT]))
finally:
    crud.get_delivery = _orig_get_delivery


# ══════════════════════════════════════════════════════════════
section("4. O'qish marshrutlari — begona nom yo'q")
# ══════════════════════════════════════════════════════════════
# "Bugungi vazifalar" uchun muddatlar: har korxonada 1 ta bugungi
# buyurtma; A da qo'shimcha 2 ta MUDDATI O'TGAN buyurtma (faqat A da).
from datetime import timedelta as _td            # noqa: E402
from database import tashkent_today_start_utc    # noqa: E402
from models import Order as _Order               # noqa: E402
_t0 = tashkent_today_start_utc()
for cid in (1, 2, 3):
    _o = db.query(_Order).get(ORDER_ID[cid]) if ORDER_ID[cid] else None
    if _o is not None:
        _o.deadline = _t0 + _td(hours=2)
db.commit()
for n in (1, 2):
    with contextlib.redirect_stdout(_quiet):
        _r = CL[1].post("/api/orders", json={
            "project_id": PROJ[1], "order_type": "service", "items": [],
            "agreed_amount": 5000 + n, "notes": f"kechikkan_{n}"})
    _oid = _r.json().get("id") if _r.status_code == 200 else None
    if _oid:
        _o = db.query(_Order).get(_oid)
        _o.deadline = _t0 - _td(days=3)
db.commit()
EXPECT_DUE = {1: 1, 2: 1, 3: 1}
EXPECT_OVERDUE = {1: 2, 2: 0, 3: 0}
for cid in (1, 2, 3):
    _r = CL[cid].get("/api/dashboard/today-tasks")
    _tasks = _r.json() if _r.status_code == 200 else []
    _due = sum(1 for t in _tasks if t.get("icon") == "\U0001f69a")
    _ov = [t["text"] for t in _tasks if "muddati o'tgan" in t.get("text", "")]
    _ov_n = int(_ov[0].split()[0]) if _ov else 0
    check(f"[{cid}] bugungi vazifalar: bugungi buyurtma = {EXPECT_DUE[cid]}, "
          f"kechikkan = {EXPECT_OVERDUE[cid]} (faqat o'ziniki)",
          _r.status_code == 200 and _due == EXPECT_DUE[cid]
          and _ov_n == EXPECT_OVERDUE[cid],
          f"{_r.status_code} due={_due} overdue={_ov_n} {_tasks}")

for cid in (1, 2, 3):
    for p in ("/api/warnings/low-stock", "/api/dashboard/today-tasks",
              "/api/dashboard/stats", "/api/dashboard/charts"):
        r = CL[cid].get(p)
        check(f"[{cid}] {p} → 200, begona nom yo'q, o'ziniki bor",
              r.status_code == 200 and not has_foreign(cid, r.text)
              and MARK[cid] in r.text,
              f"{r.status_code} {r.text[:200]}")
    _rs = CL[cid].get("/api/dashboard/stats")
    st = _rs.json() if _rs.status_code == 200 else {}
    _eo = 3 if cid == 1 else 1
    check(f"[{cid}] stats sanoqlari faqat o'ziniki (1 loyiha, {_eo} buyurtma, 1 xomashyo)",
          (st.get("total_projects"), st.get("total_orders"),
           st.get("total_inventory_items"), st.get("low_stock_count")) == (1, _eo, 1, 1),
          str({k: st.get(k) for k in ("total_projects", "total_orders",
                                      "total_inventory_items", "low_stock_count")}))

# Ildiz funksiyalar: korxona noma'lum → bo'sh (zaxira yo'q)
check("services.check_low_stock(db) — korxonasiz → []",
      safe(services.check_low_stock, db) == [])
check("crud.get_low_stock_items(db) — korxonasiz → []",
      safe(crud.get_low_stock_items, db) == [])
_tt = safe(services.get_today_tasks, db)
check("services.get_today_tasks(db) — korxonasiz: hech qaysi korxona nomi yo'q",
      not any(m in str(_tt) for m in MARK.values()), str(_tt))
_l2 = safe(services.check_low_stock, db, 2)
check("services.check_low_stock(db, 2) — faqat B",
      isinstance(_l2, list) and [x["item_name"] for x in _l2] == ["BBB_KAM_XOMASHYO"],
      str(_l2))


# ══════════════════════════════════════════════════════════════
section("5. Statik: marshrutlardagi Telegram chaqiruvlari company_id beradi")
# ══════════════════════════════════════════════════════════════
_TG = {"_send_telegram", "_send_telegram_to", "_send_telegram_document",
       "_send_telegram_to_qoplamachi"}
_src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
_tree = ast.parse(_src)
_bad, _total = [], 0
for fn in ast.walk(_tree):
    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        continue
    argnames = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
    if "current_user" not in argnames:
        continue
    for node in ast.walk(fn):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in _TG):
            _total += 1
            if not any(k.arg == "company_id" for k in node.keywords):
                _bad.append(f"{fn.name}:{node.lineno} {node.func.id}")
check(f"current_user bor funksiyalardagi {_total} Telegram chaqiruvi — hammasida company_id=",
      _total >= 13 and not _bad, f"jami={_total} yo'q: {_bad}")
_helpers = {"_send_delivery_pdf_to_customer": 0, "_send_telegram_to_qoplamachi": 0}
for fn in ast.walk(_tree):
    if isinstance(fn, ast.FunctionDef) and fn.name in _helpers:
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in _TG):
                if any(k.arg == "company_id" for k in node.keywords):
                    _helpers[fn.name] += 1
                else:
                    _helpers[fn.name] = -999
check("yordamchilar (yuk xati, qoplamachi) ichki chaqiruvlari company_id beradi",
      all(v > 0 for v in _helpers.values()), str(_helpers))


print("\n" + "=" * 66)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
print("=" * 66)
db.close()
sys.exit(1 if FAIL else 0)
