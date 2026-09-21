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
os.environ["TELEGRAM_WEBHOOK_SECRET"] = "WH_SECRET"

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


PM = []          # har yuborilgan xabarning parse_mode i (SENT bilan parallel)
ATTEMPTS = []    # har urinish (rad etilganlari ham): (chat, parse_mode)


def _fake_urlopen(req, timeout=5):
    import urllib.error as _ue
    url = req.full_url
    if isinstance(getattr(req, "data", None), (bytes, bytearray)):
        try:
            _d = json.loads(req.data.decode("utf-8"))
            _pm = _d.get("parse_mode")
            ATTEMPTS.append((str(_d.get("chat_id")), _pm))
            _tx = _d.get("text", "")
            if _pm and "MD_BUZUQ" in _tx:
                raise _ue.HTTPError(url, 400, "Bad Request: can't parse entities", {}, None)
            if "MD_403" in _tx:
                raise _ue.HTTPError(url, 403, "Forbidden", {}, None)
            PM.append(_pm)
        except (ValueError, UnicodeDecodeError):
            pass
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


def _src_now():
    return _src
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


# ══════════════════════════════════════════════════════════════
section("6. Brend: har korxona xabarida faqat O'Z nomi (2026-09-21)")
# ══════════════════════════════════════════════════════════════
# BIZNES QARORI: boshqa korxonalar xabarida "🏗 PenoDecorPro — Andijon"
# chiqmasligi kerak. A (1) ning ma'lumoti 1-korxonaning HAQIQIY
# qiymatiga tenglashtiriladi — shunda A matni ESKI qattiq matn bilan
# harfma-harf bir xil bo'lishi tekshiriladi. B da manzil/shior BO'SH —
# platforma egasining manzili sizib chiqmasligi ham tekshiriladi.
def _M(name):
    # mutatsiyada (eski kodda) yordamchi yo'q — skript qulamasin, qulf yiqilsin
    return getattr(main, name, None)


A_FOOT = "🏗 *PenoDecorPro* — Andijon"
_ca = db.query(Company).filter(Company.id == 1).first()
_ca.name, _ca.address, _ca.slogan = "PenoDecorPro", "Andijon", "Fasad bezaklari"
_cb = db.query(Company).filter(Company.id == 2).first()
_cb.name, _cb.address, _cb.slogan = "BBB_BREND", None, None
db.commit()


def _clean_b(label, texts):
    blob = " | ".join(texts)
    check(f"{label}: B nomi bor", "BBB_BREND" in blob, blob[:300])
    check(f"{label}: 'PenoDecorPro' YO'Q", "PenoDecorPro" not in blob, blob[:300])
    check(f"{label}: 'Andijon' YO'Q (bo'sh manzil bo'sh qoladi)",
          "Andijon" not in blob, blob[:300])


# 6.1 Ildiz yordamchilari
check("_tg_footer(1) — eski matn bilan aynan bir xil",
      safe(_M("_tg_footer"), db, 1) == A_FOOT, repr(safe(_M("_tg_footer"), db, 1)))
check("_tg_footer(None) — tizim xabari: 1-korxona zaxirasi",
      safe(_M("_tg_footer"), db, None) == A_FOOT, repr(safe(_M("_tg_footer"), db, None)))
check("_tg_footer(2) — manzil bo'sh: ' — ' qismi yo'q",
      safe(_M("_tg_footer"), db, 2) == "🏗 *BBB_BREND*", repr(safe(_M("_tg_footer"), db, 2)))
check("_tg_footer(2, tail) — manzil o'rniga tail",
      safe(_M("_tg_footer"), db, 2, tail="Ali") == "🏗 *BBB_BREND* — Ali")
check("_tg_footer(1, bold=False, emoji=📞) — eski 'topilmadingiz' imzosi",
      safe(_M("_tg_footer"), db, 1, bold=False, emoji="📞") == "📞 PenoDecorPro — Andijon")
check("_tg_title(2) — B sarlavhasi",
      safe(_M("_tg_title"), db, 2, "Yangi buyurtma") == "🏗 *BBB_BREND — Yangi buyurtma*")
check("_tg_title(1) — eski sarlavha bilan bir xil",
      safe(_M("_tg_title"), db, 1, "Buyurtma tayyor") == "🏗 *PenoDecorPro — Buyurtma tayyor*")
check("_tg_signature(2) — shior/manzil bo'sh: faqat nom qatori",
      safe(_M("_tg_signature"), db, 2) == "🏗 *BBB_BREND*", repr(safe(_M("_tg_signature"), db, 2)))
check("_tg_footer(999) — mavjud bo'lmagan korxona: platforma nomi chiqmaydi",
      "Andijon" not in str(safe(_M("_tg_footer"), db, 999)),
      repr(safe(_M("_tg_footer"), db, 999)))

# 6.2 HTTP: buyurtma (ombor ogohlantirishi) + qoplama + to'liq ombor hisoboti
BR_TXT = {1: [], 2: []}
for cid in (1, 2):
    SENT.clear()
    with contextlib.redirect_stdout(_quiet):
        r = CL[cid].post("/api/orders", json={
            "project_id": PROJ[cid], "order_type": "service", "items": [],
            "agreed_amount": 7000 + cid, "notes": f"brand_probe_{cid}"})
        oid = r.json().get("id") if r.status_code == 200 else 0
        CL[cid].post(f"/api/orders/{oid}/coating-notify", params={"loy_kg": 7})
        CL[cid].post("/api/inventory/low-stock-alert")
        CL[cid].post("/api/inventory/full-stock-report")
    BR_TXT[cid] = [t for _, _, t in SENT]
    check(f"[{cid}] brend probasi: kamida 5 xabar", len(SENT) >= 5,
          str([(a, b) for a, b, _ in SENT]))
_clean_b("[2] buyurtma/qoplama/ombor", BR_TXT[2])
check("[2] qoplama sarlavhasi B nomi bilan",
      any(t.startswith("🏗 *BBB_BREND — Yangi buyurtma*\n\n") for t in BR_TXT[2]),
      str([t[:40] for t in BR_TXT[2]]))
check("[1] A: ombor xabarlari eski imzo bilan tugaydi (o'zgarmagan)",
      sum(t.endswith("\n\n" + A_FOOT) for t in BR_TXT[1]) >= 3,
      str([t[-40:] for t in BR_TXT[1]]))
check("[1] A: qoplama sarlavhasi eski matn bilan bir xil",
      any(t.startswith("🏗 *PenoDecorPro — Yangi buyurtma*\n\n") for t in BR_TXT[1]),
      str([t[:40] for t in BR_TXT[1]]))

# 6.3 Ustaga salom (POST /api/masters)
for cid, tg in ((1, "700001"), (2, "700002")):
    SENT.clear()
    with contextlib.redirect_stdout(_quiet):
        r = CL[cid].post("/api/masters", json={
            "name": f"USTA_{cid}", "phone": f"+99890000000{cid}",
            "telegram_id": tg, "cashback_percent": 5})
    check(f"[{cid}] POST /api/masters → 200", r.status_code == 200,
          f"{r.status_code} {r.text[:150]}")
    _w = [t for _, ch, t in SENT if ch == tg]
    check(f"[{cid}] ustaga salom yuborildi", len(_w) == 1, str(SENT)[:200])
    if cid == 2:
        _clean_b("[2] ustaga salom", _w)
        check("[2] salom oxirida faqat nom qatori (shior/manzil bo'sh)",
              _w and _w[0].endswith("🌟\n\n🏗 *BBB_BREND*"), repr(_w[0][-60:]) if _w else "")
    else:
        check("[1] A salomi: eski matn (nom va manzil DB dan, shior sozlamadan)",
              _w and _w[0].endswith("🌟\n\n🏗 *PenoDecorPro* — Zamonaviy fasad dekorlari\n📍 Andijon"),
              repr(_w[0][-80:]) if _w else "")

# 6.4 Nasiya xarid: imzo + literal "\n" xatosi
for cid in (1, 2):
    _sup = crud.create_supplier(db, schemas.SupplierCreate(name=f"SUPP_{cid}X"),
                                company_id=cid)
    _inv = db.query(Inventory).filter(Inventory.company_id == cid).first()
    SENT.clear()
    with contextlib.redirect_stdout(_quiet):
        r = CL[cid].post(f"/api/inventory/{_inv.id}/purchase", json={
            "quantity": 1, "price_per_unit": 100, "supplier_id": _sup.id,
            "paid_now": 30})
    check(f"[{cid}] nasiya xarid → 200", r.status_code == 200,
          f"{r.status_code} {r.text[:150]}")
    _n = [t for _, _, t in SENT if "Nasiya xarid" in t]
    check(f"[{cid}] nasiya xabari yuborildi", len(_n) == 1, str(SENT)[:200])
    check(f"[{cid}] nasiya xabarida literal '\\n' YO'Q (qator uzilishi to'g'ri)",
          _n and "\\n" not in _n[0], repr(_n[0][:200]) if _n else "")
    _exp = {1: "🏗 *PenoDecorPro* — AAA", 2: "🏗 *BBB_BREND* — BBB"}[cid]
    check(f"[{cid}] nasiya imzosi: {_exp}", _n and _n[0].endswith(_exp),
          repr(_n[0][-50:]) if _n else "")

# 6.5 Mijozga "tayyor" (api_mark_order_ready) — B mijozi B nomini ko'radi
for cid, tg in ((1, "600001"), (2, "600002")):
    with contextlib.redirect_stdout(_quiet):
        _pid = crud.create_project(db, schemas.ProjectCreate(
            project_name=f"RDY_{cid}_LOYIHA", client_name=f"RDY{cid}_MIJOZ",
            notes=f"tg_id={tg}"), company_id=cid).id
        r = CL[cid].post("/api/orders", json={
            "project_id": _pid, "order_type": "service", "items": [],
            "agreed_amount": 9100 + cid, "notes": f"rdy_probe_{cid}"})
        oid = r.json().get("id") if r.status_code == 200 else 0
        SENT.clear()
        r2 = CL[cid].post(f"/api/orders/{oid}/ready", params={"loy_kg": 3})
    check(f"[{cid}] /ready → 200", r2.status_code == 200,
          f"{r2.status_code} {r2.text[:150]}")
    _c = [t for _, ch, t in SENT if ch == tg and "Buyurtmangiz" in t]
    _h = [t for _, _, t in SENT if "Buyurtma tayyor" in t]
    check(f"[{cid}] mijozga xabar ketdi", len(_c) == 1, str([(a, b) for a, b, _ in SENT]))
    if cid == 2:
        _clean_b("[2] mijozga 'tayyor' + ichki 'Buyurtma tayyor'", _c + _h)
    else:
        check("[1] A mijoz xabari eski imzo bilan (qalin emas)",
              _c and "\n🏗 PenoDecorPro — Andijon\n\n" in _c[0], repr(_c[0][:200]) if _c else "")

# 6.6 Webhook — bot global (1-korxonaniki); usta topilsa — o'z korxonasi
WH = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)


def _wh(chat, text):
    SENT.clear()
    with contextlib.redirect_stdout(_quiet):
        r = WH.post("/telegram/webhook", json={"message": {
            "chat": {"id": int(chat)}, "text": text}},
            headers={"X-Telegram-Bot-Api-Secret-Token": "WH_SECRET"})
    return r.status_code, [t for _, ch, t in SENT if ch == str(chat)]


_st, _t = _wh("700002", "/start")
check("[wh] B ustasi /start → 200 + javob", _st == 200 and len(_t) == 1, f"{_st} {_t}")
_clean_b("[wh] B ustasi /start", _t)
_st, _t = _wh("700002", "/bonus")
check("[wh] B ustasi /bonus → javob (xatosiz)",
      _st == 200 and len(_t) == 1 and "Xatolik" not in _t[0], f"{_st} {_t}")
_clean_b("[wh] B ustasi /bonus", _t)
_st, _t = _wh("700002", "/sovgalar")
check("[wh] B ustasi /sovgalar → javob", _st == 200 and len(_t) == 1, f"{_st} {_t}")
_clean_b("[wh] B ustasi /sovgalar", _t)
_st, _t = _wh("700001", "/start")
check("[wh] A ustasi /start — eski matn",
      _t == ["Assalomu alaykum! 👋\n\n*PenoDecorPro* bot ga xush kelibsiz!\n\n"
             "Quyidagi tugmalardan foydalaning:"], str(_t))
_st, _t = _wh("700001", "/bonus")
check("[wh] A ustasi /bonus — eski imzo",
      len(_t) == 1 and _t[0].endswith("so'm*\n\n🏗 PenoDecorPro — Andijon"), str(_t)[:200])
_st, _t = _wh("799999", "/bonus")
check("[wh] noma'lum chat /bonus — bot egasi imzosi (eski matn)",
      _t == ["❌ Siz ustalar ro'yxatida topilmadingiz.\n\nIltimos, administrator "
             "bilan bog'laning.\n\n📞 PenoDecorPro — Andijon"], str(_t))

# 6.7 STATIK: main.py dagi satrlarda qattiq brend qolmagan
_ALLOWED = {"PenoDecorProBoundary1234567890", "PenoDecorPro ERP",
            "PenoDecorPro ERP ishlamoqda!"}
_doc_ids = set()
for _n in ast.walk(_tree):
    if isinstance(_n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        if (_n.body and isinstance(_n.body[0], ast.Expr)
                and isinstance(_n.body[0].value, ast.Constant)):
            _doc_ids.add(id(_n.body[0].value))
_hard = []
for _n in ast.walk(_tree):
    if (isinstance(_n, ast.Constant) and isinstance(_n.value, str)
            and id(_n) not in _doc_ids
            and ("PenoDecorPro" in _n.value or "Andijon" in _n.value)
            and _n.value not in _ALLOWED
            # ishga tushish migratsiyasi: ENG ESKI korxonaning O'Z bo'sh
            # maydonlarini to'ldiradi (xabar matni emas)
            and not _n.value.startswith("UPDATE companies SET")):
        _hard.append(f"{_n.lineno}: {_n.value[:50]!r}")
# Marshrutdagi har brend chaqiruvi korxonani current_user dan oladi
# (HTTP sinalmagan api_produce / api_add_production / api_update_order ham)
_BR = {"_tg_footer", "_tg_title", "_tg_signature", "_tg_brand"}
_want = ast.dump(ast.parse("auth.company_id_of(current_user)", mode="eval").body)
_bb, _bt = [], 0
for fn in ast.walk(_tree):
    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        continue
    if "current_user" not in {a.arg for a in fn.args.args + fn.args.kwonlyargs}:
        continue
    for node in ast.walk(fn):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in _BR):
            _bt += 1
            if len(node.args) < 2 or ast.dump(node.args[1]) != _want:
                _bb.append(f"{fn.name}:{node.lineno} {node.func.id}")
check(f"marshrutlardagi {_bt} brend chaqiruvi — hammasi auth.company_id_of(current_user)",
      _bt >= 12 and not _bb, f"jami={_bt} xato: {_bb}")
check("main.py: xabar matnlarida qattiq 'PenoDecorPro'/'Andijon' YO'Q", not _hard, str(_hard))

# ══════════════════════════════════════════════════════════════
section("7. Ustaga salom shiori — sozlamadan (2026-09-21)")
# ══════════════════════════════════════════════════════════════
# Foydalanuvchi: "Zamonaviy fasad dekorlari" qolsin, lekin sozlamada
# istalgan matnni yozsa — o'sha chiqsin. Bo'sh — shior qatori yo'q.
_TK = "tg_welcome_tagline"
with contextlib.redirect_stdout(_quiet):
    safe(_M("_seed_tg_tagline"))            # qayta ishga tushish (import paytida ham ishlagan)
check("seed: 1-korxonaga eski shior yozildi",
      crud.get_setting(db, _TK, None, company_id=1) == "Zamonaviy fasad dekorlari",
      repr(crud.get_setting(db, _TK, None, company_id=1)))
check("seed: boshqa korxonaga yozilmadi",
      crud.get_setting(db, _TK, None, company_id=2) is None
      and crud.get_setting(db, _TK, None, company_id=3) is None)


def _welcome(cid, tg, nm):
    SENT.clear()
    with contextlib.redirect_stdout(_quiet):
        r = CL[cid].post("/api/masters", json={
            "name": nm, "phone": f"+99891{abs(hash(nm)) % 10**7:07d}",
            "telegram_id": tg, "cashback_percent": 1})
    w = [t for _, ch, t in SENT if ch == tg]
    return r.status_code, (w[0] if len(w) == 1 else repr(w))


_st, _w = _welcome(1, "710001", "USTA_A_S1")
check("[1] A salomi: eski matn — 'Zamonaviy fasad dekorlari' + manzil",
      _st == 200 and _w.endswith("🌟\n\n🏗 *PenoDecorPro* — Zamonaviy fasad dekorlari\n📍 Andijon"),
      repr(_w[-80:]))


def _get_co(cid):
    r = CL[cid].get("/api/settings/company")
    return r.json() if r.status_code == 200 else {}


def _put_co(cid, name, tl, slogan=""):
    with contextlib.redirect_stdout(_quiet):
        return CL[cid].put("/api/settings/company", data={
            "name": name, "slogan": slogan, "phone": "", "address": "",
            "tg_tagline": tl}).status_code


check("[1] GET: tg_tagline = amaldagi matn",
      _get_co(1).get("tg_tagline") == "Zamonaviy fasad dekorlari", str(_get_co(1)))
check("[2] GET: kalit yo'q — shior maydoni (bo'sh)",
      _get_co(2).get("tg_tagline") == "", str(_get_co(2)))

# B o'z matnini yozadi
check("[2] PUT o'z shiori → 200", _put_co(2, "BBB_BREND", "BBB_SHIOR_X") == 200)
_st, _w = _welcome(2, "710002", "USTA_B_S1")
check("[2] B salomi: aynan kiritilgan matn",
      _st == 200 and _w.endswith("🌟\n\n🏗 *BBB_BREND* — BBB_SHIOR_X"), repr(_w[-60:]))
check("[2] GET: kiritilgan matn qaytadi", _get_co(2).get("tg_tagline") == "BBB_SHIOR_X")
_st, _w = _welcome(1, "710003", "USTA_A_S2")
check("[1] B ning shiori A ga ta'sir qilmadi",
      _w.endswith("— Zamonaviy fasad dekorlari\n📍 Andijon") and "BBB" not in _w, repr(_w[-60:]))

# bo'sh — shior qatori yo'q; shior maydoni to'la bo'lsa ham qaytmaydi
check("[2] PUT bo'sh shior (shior maydoni to'la) → 200",
      _put_co(2, "BBB_BREND", "", slogan="BBB_SLOGAN_PDF") == 200)
_st, _w = _welcome(2, "710004", "USTA_B_S2")
check("[2] bo'sh: salom oxirida faqat nom (PDF shiori ham chiqmaydi)",
      _w.endswith("🌟\n\n🏗 *BBB_BREND*"), repr(_w[-60:]))
check("[2] GET: bo'sh qaytadi", _get_co(2).get("tg_tagline") == "", str(_get_co(2)))

# kalit yo'q bo'lsa — shior maydoni (C)
_cc = db.query(Company).filter(Company.id == 3).first()
_cc.slogan = "CCC_SLOGAN"
db.commit()
check("[3] kalit yo'q: _tg_tagline = shior maydoni",
      safe(_M("_tg_tagline"), db, 3) == "CCC_SLOGAN", repr(safe(_M("_tg_tagline"), db, 3)))
check("_tg_tagline(None) — sozlama o'qilmaydi (1-korxona zaxira shiori)",
      safe(_M("_tg_tagline"), db, None) == "Fasad bezaklari",
      repr(safe(_M("_tg_tagline"), db, None)))

# chegaralar va idempotentlik
check("[2] 151 belgi → 400", _put_co(2, "BBB_BREND", "x" * 151) == 400)
check("[2] 150 belgi → 200", _put_co(2, "BBB_BREND", "y" * 150) == 200)
check("[1] A o'zgartiradi → 200", _put_co(1, "PenoDecorPro", "AAA_YANGI_SHIOR", slogan="Fasad bezaklari") == 200)
with contextlib.redirect_stdout(_quiet):
    safe(_M("_seed_tg_tagline"))
check("seed qayta ishga tushishda A ning matnini QAYTA YOZMADI",
      crud.get_setting(db, _TK, None, company_id=1) == "AAA_YANGI_SHIOR",
      repr(crud.get_setting(db, _TK, None, company_id=1)))
check("[1] A bo'sh qiladi → 200", _put_co(1, "PenoDecorPro", "", slogan="Fasad bezaklari") == 200)
with contextlib.redirect_stdout(_quiet):
    safe(_M("_seed_tg_tagline"))
check("seed: bo'sh qiymat ham qayta yozilmaydi (foydalanuvchi tanlovi)",
      crud.get_setting(db, _TK, None, company_id=1) == "",
      repr(crud.get_setting(db, _TK, None, company_id=1)))
_put_co(1, "PenoDecorPro", "Zamonaviy fasad dekorlari", slogan="Fasad bezaklari")
# Andijon manzilini qaytarish (PUT manzilni bo'shatgan edi)
_ca = db.query(Company).filter(Company.id == 1).first()
db.refresh(_ca)
_ca.address = "Andijon"
db.commit()

# ── Markdown 400 → oddiy matn bilan qayta ─────────────────────
check("[2] PUT 'MD_BUZUQ' shior → 200", _put_co(2, "BBB_BREND", "MD_BUZUQ *belgi") == 200)
ATTEMPTS.clear(); PM.clear()
_st, _w = _welcome(2, "710005", "USTA_B_S3")
check("[2] Markdown rad etildi → xabar baribir YETDI (1 marta)",
      _st == 200 and "MD_BUZUQ" in _w, repr(_w[-60:]))
check("[2] ikkinchi urinish parse_mode SIZ",
      [a for a in ATTEMPTS if a[0] == "710005"] == [("710005", "Markdown"), ("710005", None)],
      str(ATTEMPTS))
_put_co(2, "BBB_BREND", "")

# webhook (klaviaturali yuborish) — usta ismida buzuq belgi
from models import Master as _Mst                  # noqa: E402
_mb = db.query(_Mst).filter(_Mst.telegram_id == "700002").first()
_mb.name = "MD_BUZUQ_USTA"
db.commit()
ATTEMPTS.clear()
_st, _t = _wh("700002", "/bonus")
check("[wh] Markdown rad etildi → javob baribir yetdi",
      _st == 200 and len(_t) == 1 and "MD_BUZUQ_USTA" in _t[0], str(_t)[:150])
check("[wh] ikkinchi urinish parse_mode SIZ",
      [a[1] for a in ATTEMPTS if a[0] == "700002"] == ["Markdown", None], str(ATTEMPTS))
_mb.name = "USTA_2"
db.commit()

# 403 (bot bloklangan) — qayta urinilmaydi, xato jim yutiladi
ATTEMPTS.clear(); SENT.clear()
with contextlib.redirect_stdout(_quiet):
    _r = safe(main._send_telegram_to, "720001", "MD_403 test", company_id=2)
check("403 — faqat BITTA urinish, xato ko'tarilmadi",
      [a for a in ATTEMPTS if a[0] == "720001"] == [("720001", "Markdown")]
      and not (isinstance(_r, tuple) and _r[:1] == ("XATO",)), f"{ATTEMPTS} {_r}")

# ── Bot holati: "umumiy bot" faqat 1-korxonada rost ──────────
_b1 = CL[1].get("/api/settings/telegram-bot").json()
_b3 = CL[3].get("/api/settings/telegram-bot").json()
check("[1] telegram-bot: uses_system_bot = True", _b1.get("uses_system_bot") is True, str(_b1))
check("[3] telegram-bot: uses_system_bot = False (xabar yuborilmaydi)",
      _b3.get("uses_system_bot") is False, str(_b3))

# ── Interfeys (statik) ───────────────────────────────────────
_ui = open(os.path.join(ROOT, "templates", "logs.html"), encoding="utf-8").read()
check("logs.html: shior maydoni bor, yuklanadi va yuboriladi",
      'id="co-tg-tagline"' in _ui
      and "d.tg_tagline" in _ui
      and "fd.append('tg_tagline'" in _ui)
check("logs.html: boti yo'q korxonaga to'g'ri ogohlantirish",
      "d.uses_system_bot" in _ui and "YUBORILMAYDI" in _ui)
check("main.py: sendMessage to'g'ridan-to'g'ri faqat _tg_post_message ichida",
      _src_now().count("/sendMessage") == 1, str(_src_now().count("/sendMessage")))

print("\n" + "=" * 66)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
print("=" * 66)
db.close()
sys.exit(1 if FAIL else 0)
