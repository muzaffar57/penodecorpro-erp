#!/usr/bin/env python3
"""
test_fon_xabar201.py — kech154 (zip 201 «Saqlash tezroq — Telegram xabarlari orqa fonda»; egasi TANLOVI 22.10 00:5x): xodim saqlash
tugmasini bosganda javob Telegram xabari ketishini KUTMAYDI — xabar javobdan KEYIN (FastAPI fon vazifasi, `main._fonda`).

NIMA UCHUN KERAK (O'LCHANGAN — `work/k201/` jurnali): Telegram sekin bo'lsa (har bo'lak / chat 5 s gacha, 400 da yana bir urinish) buyurtma
tahriri, qoralamani faollashtirish, tayyor mahsulot ishlab chiqarish / «+», nasiya kirim, qoplama xabari, usta qo'shish, murojaat —
javob shuncha kechikardi (xabar so'rov ichida sinxron).
BO'LIMLAR:
  S — manba (AST): o'zgartirilgan 12 marshrutda xabar funksiyalari (`_send_telegram`, `_send_telegram_to`, `_send_telegram_to_qoplamachi`,
      `_tm_minus_xabari`, `_mj_telegram`) to'g'ridan-to'g'ri CHAQIRILMAYDI — faqat `_fonda(background_tasks, …)`, marshrutda
      `background_tasks` parametri bor; S2 — BUTUN `main.py` marshrutlarida sinxron xabar (to'g'ridan-to'g'ri yoki Telegramga
      yuboruvchi modul yordamchisi orqali — tranzitiv: `run_daily_backup`, `_send_delivery_pdf_to_customer` va h.k.) faqat ataylab qoldirilganlarda
      (natijasi javobda kerak yoki amalning o'zi xabar: to'liq ombor hisoboti, kam qoldiq xabari tugmasi, cron, platforma admin parolini
      tiklash, zaxira nusxani hozir yuborish).
  D — HAQIQIY lokal server (uvicorn), Telegram 1,5 s ga sekinlashtirilgan (yozib olinadi, tarmoqqa chiqmaydi): har amalning javobi
      < 1 s keladi va xabar baribir yuboriladi (javobdan keyin, 5 s ichida); xabar yuborilayotganda so'rov bazaga ulanishni USHLAMAYDI
      (hovuzda band ulanish 0 — mustaqil tekshiruv F1: FastAPI 0.141 da `get_db` fon vazifalaridan KEYIN yopiladi); D10 — saqlagandan
      keyin darhol sahifa so'rovi (xuddi shu keep-alive ulanish) ham fon xabarini kutmaydi; D11 — ketma-ket 6 ta tez saqlash: hammasi
      tez, 6 xabar, hovuz bo'sh.
  S4 — HAR `_fonda(background_tasks, …)` — `sessiya=db` bilan (navbat boshida so'rov sessiyasi yopiladi); `background_tasks.add_task`
      faqat `_fonda` ichida; `_tm_minus_xabari` matni so'rov ichida (`_fonda_tayyorla`).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 200) qarshi QULAMAYDI — S va D yiqiladi.
ISHLATISH: python3 tools/test_fon_xabar201.py
"""
import os
import io
import ast
import sys
import time
import socket
import tempfile
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = os.environ.get("K201_PG_BAZA") or "fon_xabar201_test"
_T = tempfile.mkdtemp(prefix="k201_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k201.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import httpx                                       # noqa: E402
import database                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Project, Inventory, Recipe, RecipeIngredient, FinishedProduct, StockSource,   # noqa: E402
                    ProductionStatus)

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"


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
        if callable(detail):
            try:
                detail = detail()
            except Exception as e:         # noqa: BLE001
                detail = f"{type(e).__name__}: {e}"
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba (AST): xabarlar fon vazifasida")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
XABAR_FN = {"_send_telegram", "_send_telegram_to", "_send_telegram_to_qoplamachi", "_tm_minus_xabari", "_mj_telegram"}
# ataylab SINXRON (bot sozlamalari — Telegram so'rovining o'zi, natijasi javobda): webhook holati, xavfsizlik webhooki, bot tokenini
# saqlash (eski botni uzish), «Botni ulash» — `_tg_api` orqali (mustaqil tekshiruv F7.1)
FONDA = {"api_restore_order", "api_restore_project", "api_create_master", "api_purchase_stock", "api_update_order", "api_coating_notify",
         "api_update_order_item", "api_activate_draft", "api_produce", "api_add_production", "api_murojaat_yarat", "api_murojaat_xabar",
         "api_create_order"}
# ataylab SINXRON: natijasi javobda kerak yoki amalning o'zi — xabar yuborish
SINXRON = {"api_full_stock_report", "api_low_stock_alert", "api_cron_low_stock_check", "api_platform_reset_admin_password",
           "api_backup_send_now", "api_telegram_webhook_info", "api_telegram_setup_webhook_security", "api_set_telegram_bot",
           "api_telegram_bot_ulash"}
_src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
_tree = ast.parse(_src)


def _marshrutmi(n):
    return any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr in ("get", "post", "put", "patch", "delete")
               for d in n.decorator_list)


_MARSHRUT = {n.name: n for n in _tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and _marshrutmi(n)}


def _chaqiruvlar(n):
    return {c.func.id for c in ast.walk(n) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}


# Telegramga yuboruvchi YORDAMCHILAR (modul darajasi, tranzitiv): marshrut ularni to'g'ridan-to'g'ri chaqirsa ham — sinxron xabar.
# `_fonda(background_tasks, f, …)` dagi `f` — chaqiruv emas (argument), hisobga kirmaydi.
_YUB = set(XABAR_FN) | {"_tg_post_message", "_send_telegram_document", "_tg_api"}
_MODUL_FN = {n.name: n for n in _tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not _marshrutmi(n)}
while True:
    _yangi = {nm for nm, n in _MODUL_FN.items() if nm not in _YUB and _chaqiruvlar(n) & _YUB}
    if not _yangi:
        break
    _YUB |= _yangi


def _sinxron_xabarlar(n):
    return sorted(_chaqiruvlar(n) & _YUB)


def _fonda_xabarlar(n):
    out = set()
    for c in ast.walk(n):
        if (isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "_fonda" and len(c.args) >= 2
                and isinstance(c.args[0], ast.Name) and c.args[0].id == "background_tasks" and isinstance(c.args[1], ast.Name)):
            out.add(c.args[1].id)
    return sorted(out & XABAR_FN)


_s1 = {nm: (_sinxron_xabarlar(_MARSHRUT[nm]) if nm in _MARSHRUT else "YO'Q",
            _fonda_xabarlar(_MARSHRUT[nm]) if nm in _MARSHRUT else [],
            "background_tasks" in [a.arg for a in _MARSHRUT[nm].args.args] if nm in _MARSHRUT else False) for nm in sorted(FONDA)}
_tk = _MARSHRUT.get("api_taklif_rasmiylashtir")
check("S1 13 marshrutda (buyurtma tahriri, faollashtirish, tiklash ×2, detal tahriri, kirim, ishlab chiqarish / «+», qoplama, usta, "
      "murojaat ×2, yaratish) xabar faqat `_fonda(background_tasks, …)` — to'g'ridan-to'g'ri (yoki yuboruvchi yordamchi orqali) "
      "chaqiruv yo'q, `background_tasks` bor; taklifni rasmiylashtirish o'z `background_tasks` ini buyurtma yaratishga uzatadi",
      all(v[0] == [] and v[1] and v[2] for v in _s1.values()) and _tk is not None and not _sinxron_xabarlar(_tk)
      and "background_tasks=background_tasks" in (ast.get_source_segment(_src, _tk) or ""),
      {k: v for k, v in _s1.items() if not (v[0] == [] and v[1] and v[2])})
_s2 = {nm: _sinxron_xabarlar(n) for nm, n in _MARSHRUT.items() if _sinxron_xabarlar(n)}
check("S2 BUTUN `main.py`: sinxron xabar (to'g'ridan-to'g'ri yoki yuboruvchi yordamchi orqali) faqat ataylab qoldirilgan marshrutlarda "
      "(to'liq ombor hisoboti, kam qoldiq tugmasi, cron, admin parolini tiklash, zaxira nusxani hozir yuborish, bot sozlamalari — `_tg_api`) "
      "— yangi marshrut xabarni sinxron yuborsa test yiqiladi",
      set(_s2) <= SINXRON and {"_send_telegram", "_tg_post_message", "run_daily_backup", "_send_delivery_pdf_to_customer"} <= _YUB,
      (sorted(set(_s2) - SINXRON), sorted(_YUB)))
_s3 = [n.name for n in _tree.body if isinstance(n, ast.FunctionDef) and n.name == "_fonda"]
check("S3 `_fonda`: `background_tasks` bo'lmasa (marshrut to'g'ridan-to'g'ri chaqirilsa) — darhol; bo'lsa — `add_task`",
      _s3 and "background_tasks.add_task(fn, *a, **k)" in ast.get_source_segment(_src, next(
          n for n in _tree.body if isinstance(n, ast.FunctionDef) and n.name == "_fonda")), _s3)

_s4_yoq = []
_s4_jami = 0
for _fn in ast.walk(_tree):
    if not isinstance(_fn, (ast.FunctionDef, ast.AsyncFunctionDef)) or _fn.name == "_fonda":
        continue
    for _c in ast.walk(_fn):
        if not isinstance(_c, ast.Call):
            continue
        if (isinstance(_c.func, ast.Name) and _c.func.id == "_fonda" and _c.args and isinstance(_c.args[0], ast.Name)
                and _c.args[0].id == "background_tasks"):
            _s4_jami += 1
            _kw = {k.arg: k.value for k in _c.keywords}
            if not (isinstance(_kw.get("sessiya"), ast.Name) and _kw["sessiya"].id == "db"):
                _s4_yoq.append(f"{_fn.name}:{_c.lineno}")
        if isinstance(_c.func, ast.Attribute) and _c.func.attr == "add_task":
            _s4_yoq.append(f"{_fn.name}:{_c.lineno} add_task")
check("S4 HAR `_fonda(background_tasks, …)` (24 ta) — `sessiya=db` bilan (fon vazifalaridan OLDIN so'rov sessiyasi yopiladi — ulanish "
      "hovuzga qaytadi); `background_tasks.add_task` faqat `_fonda` ichida; `_tm_minus_xabari` matni so'rov ichida (`_fonda_tayyorla`)",
      _s4_jami == 24 and not _s4_yoq and callable(getattr(main, "_tm_minus_xabari", None))
      and callable(getattr(main._tm_minus_xabari, "_fonda_tayyorla", None)) and callable(getattr(main, "_sessiyani_yop", None)),
      (_s4_jami, _s4_yoq[:10]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# D — tayyorgarlik
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
TG = []                                            # (funksiya, matn, vaqt, yuborish paytida hovuzda band ulanishlar)
TG_QULF = threading.Lock()
KECH = 1.5


def _stub(nomi):
    def f(*a, **k):
        try:
            _band = database.engine.pool.checkedout()
        except Exception:                  # noqa: BLE001
            _band = -1
        time.sleep(KECH)
        matn = next((x for x in a if isinstance(x, str) and len(x) > 15), "") or str(a[:1])
        with TG_QULF:
            TG.append((nomi, matn, time.time(), _band))
        return True
    return f


main._send_telegram = _stub("_send_telegram")
main._send_telegram_to = _stub("_send_telegram_to")
main._send_telegram_to_qoplamachi = _stub("_send_telegram_to_qoplamachi")
main._mj_telegram = _stub("_mj_telegram")

s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k201_admin", PAROL, UserRole.ADMIN, "K201 Admin", company_id=1)
PRJ = Project(company_id=1, client_name="K201 Mijoz", project_name="K201 loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="K201 PENO", unit="blok", stock_quantity=100000, min_stock=0, is_penoplast=True,
                 volume_per_unit=1, price_per_unit=120000, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="K201 KLEY", unit="kg", stock_quantity=100000, min_stock=0, price_per_unit=2000, category="Kimyo")
KAM = Inventory(company_id=1, item_name="K201 KAM", unit="kg", stock_quantity=1, min_stock=10, price_per_unit=1000, category="Kimyo")
s.add_all([PRJ, PENO, KLEY, KAM])
s.flush()
REC = Recipe(company_id=1, name="K201 retsept", batch_size_kg=100.0)
s.add(REC)
s.flush()
s.add(RecipeIngredient(recipe_id=REC.id, inventory_id=KLEY.id, quantity_kg=100.0))
FP = FinishedProduct(company_id=1, name="K201 Karniz", category="profil", is_coated=False, width=20, thickness=10, quantity=1,
                     produced_quantity=1, unit="metr", unit_price=0, cost_price=1000, unit_cost_stable=1000, source=StockSource.PRODUCED,
                     penoplast_id=PENO.id, unit_volume_m3=0.01, volume_m3=0.01, production_status=ProductionStatus.READY,
                     reserved_quantity=0)
s.add(FP)
s.commit()
ID = {"PRJ": PRJ.id, "PENO": PENO.id, "KLEY": KLEY.id, "KAM": KAM.id, "REC": REC.id, "FP": FP.id}
s.close()

# ── server
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
check("T0 lokal server", server.started)
_lg = httpx.post(B + "/login", data={"username": "k201_admin", "password": PAROL}, follow_redirects=False)
TOKEN = _lg.cookies.get("session_token")
H = {"Cookie": f"session_token={TOKEN}"}
check("T1 kirish (sessiya cookie)", _lg.status_code in (302, 303) and TOKEN, (_lg.status_code, _lg.text[:200]))
CL = httpx.Client(base_url=B, headers=H, timeout=30)
_n = {"d": 0}


def d(uz=2, fid=None, qoplama=False):
    _n["d"] += 1
    x = {"name": f"K201 detal {_n['d']}", "category": "profil", "width": 20, "thickness": 10, "length": uz, "quantity": 1,
         "unit_price": 20000, "is_coated": qoplama, "penoplast_id": ID["PENO"]}
    if fid:
        x["finished_product_id"] = fid
    return x


def tana(*items, loy=0, qoralama=False):
    t = {"project_id": ID["PRJ"], "order_type": "product", "loy_kg": loy, "items": list(items)}
    if loy:
        t["recipe_id"] = ID["REC"]
    if qoralama:
        t["is_draft"] = True
    return t


def kut_xabar(n0, fn_nomi, muddat=5.0):
    """`n0` dan keyin `fn_nomi` yozuvi `muddat` s ichida paydo bo'ladimi — (bormi, birinchisi)."""
    t0 = time.time()
    while time.time() - t0 < muddat:
        with TG_QULF:
            yangi = [x for x in TG[n0:] if x[0] == fn_nomi]
        if yangi:
            return True, yangi[0]
        time.sleep(0.1)
    return False, None


def amal(metod, yol, **k):
    """(status, javob vaqti s, json, so'rov oldidan TG uzunligi)."""
    time.sleep(0.2)
    with TG_QULF:
        n0 = len(TG)
    t0 = time.time()
    r = CL.request(metod, yol, **k)
    dt = time.time() - t0
    try:
        j = r.json()
    except Exception:                      # noqa: BLE001
        j = {}
    return r.status_code, round(dt, 3), j, n0, r.text[:200]


def tekshir(nom, izoh, natija, fn_nomi, matn_bor=None):
    st, dt, _j, n0, txt = natija
    bor, yozuv = kut_xabar(n0, fn_nomi)
    check(f"{nom} {izoh}: 200, javob {KECH} s lik Telegramni KUTMAYDI (< 1 s), xabar baribir yuborildi"
          + (f" («{matn_bor}»)" if matn_bor else "") + "; yuborilayotganda bazaga ulanish ushlanmaydi (hovuzda band 0)",
          st == 200 and dt < 1.0 and bor and (not matn_bor or matn_bor in (yozuv[1] if yozuv else "")) and yozuv[3] == 0,
          (st, dt, bor, f"band ulanish {yozuv[3] if yozuv else None}", (yozuv[1][:120] if yozuv else None), txt))
    time.sleep(KECH + 0.3)                 # fon vazifasi tugasin (keyingi amalni kechiktirmasin)


section("D — haqiqiy server: javob Telegramdan OLDIN, xabar keyin (fonda)")
if server.started and TOKEN:
    # D1 buyurtma tahriri («kam qoldiq» — K201 KAM 1 < 10)
    _r = CL.post("/api/orders?confirm_shortage=true", json=tana(d()))
    time.sleep(KECH + 0.5)
    O1 = (_r.json() or {}).get("id")
    _o = CL.get(f"/api/orders/{O1}").json()
    _it = [{k: v for k, v in {kk: it.get(kk) for kk in ("id", "name", "category", "quantity", "length", "width", "thickness",
                                                        "unit_price", "is_coated", "penoplast_id")}.items() if v is not None}
           for it in (_o.get("items") or [])]
    _it[0]["length"] = 3
    tekshir("D1", "buyurtma tahriri", amal("PUT", f"/api/orders/{O1}?confirm_shortage=true",
                                           json={"project_id": ID["PRJ"], "order_type": "product", "loy_kg": 0, "items": _it,
                                                 "notes": _o.get("notes")}),
            "_send_telegram", "Ombor ogohlantirishlari")
    # D2 qoralamani faollashtirish — tayyor mahsulot minusga tushadi (1 − 3) — minus xabari
    _rq = CL.post("/api/orders?confirm_shortage=true", json=tana(d(3, ID["FP"]), qoralama=True))
    OQ = (_rq.json() or {}).get("id")
    tekshir("D2", "qoralamani faollashtirish (tayyor mahsulot minusga)", amal("POST", f"/api/orders/{OQ}/activate?confirm_shortage=true"),
            "_send_telegram")
    # D3 tayyor mahsulot ishlab chiqarish («kam qoldiq»)
    _pt = {"name": "K201 prof", "category": "profil", "width": 20, "thickness": 10, "length": 5, "is_coated": True,
           "penoplast_id": ID["PENO"], "recipe_id": ID["REC"], "loy_kg": 5, "unit_price": 10000}
    _rp = amal("POST", "/api/finished/produce", json=_pt)
    F = (_rp[2] or {}).get("product_id")
    tekshir("D3", "tayyor mahsulot ishlab chiqarish", _rp, "_send_telegram", "Ombor ogohlantirishlari")
    # D4 «+» (tayyorga o'tkazilgach)
    CL.post(f"/api/finished/{F}/complete")
    tekshir("D4", "tayyor mahsulotga «+»", amal("POST", f"/api/finished/{F}/add", json={"quantity": 1}), "_send_telegram",
            "Ombor ogohlantirishlari")
    # D5 nasiya xarid (ta'minotchiga qarz xabari)
    _sup = CL.post("/api/suppliers", json={"name": "K201 ta'minotchi", "phone": "+998901112233"}).json().get("id")
    tekshir("D5", "nasiya xarid", amal("POST", f"/api/inventory/{ID['KLEY']}/purchase",
                                      json={"quantity": 5, "price_per_unit": 1000, "paid_now": 0, "supplier_id": _sup, "notes": "K201"}),
            "_send_telegram")
    # D6 qoplama xabari (qoplamali buyurtma, loy 5 kg) — admin bot va qoplamachiga
    _rc = CL.post("/api/orders?confirm_shortage=true", json=tana(d(qoplama=True), loy=5))
    time.sleep(KECH * 2 + 0.5)
    OC = (_rc.json() or {}).get("id")
    _r6 = amal("POST", f"/api/orders/{OC}/coating-notify?loy_kg=5")
    tekshir("D6", "qoplama xabari (admin bot)", _r6, "_send_telegram", "Loy tayyorlang")
    _b6, _y6 = kut_xabar(_r6[3], "_send_telegram_to_qoplamachi")
    check("D6b qoplama xabari qoplamachiga ham yuborildi (fonda; bazaga ulanish ushlanmaydi)", _b6 and _y6[3] == 0, _y6)
    # D7 yangi usta (Telegram ID bor — salomlashuv xabari)
    tekshir("D7", "yangi usta (salomlashuv xabari)", amal("POST", "/api/masters", json={"name": "K201 Usta", "phone": "+998901234567",
                                                                                        "telegram_id": "123456789"}),
            "_send_telegram_to")
    # D8 murojaat (platforma egasiga)
    tekshir("D8", "murojaat yuborish", amal("POST", "/api/murojaatlar", data={"turi": "savol", "matn": "K201 sinov murojaati matni"}),
            "_mj_telegram")
    # D10 saqlagandan keyin DARHOL sahifa so'rovi XUDDI SHU keep-alive ulanishda — fon vazifasi (1,5 s) tugashini kutmaydi
    # (uvicorn javob tugagach keyingi so'rovni darhol o'qiydi — O'LCHANGAN; xabar hali yuborilmagan paytda javob keladi)
    _r10 = amal("POST", f"/api/finished/{F}/add", json={"quantity": 1})
    _t10 = time.time()
    _g10 = CL.get(f"/api/orders/{O1}")
    _d10 = round(time.time() - _t10, 3)
    with TG_QULF:
        _hali10 = len([x for x in TG[_r10[3]:] if x[0] == "_send_telegram"])
    _b10, _ = kut_xabar(_r10[3], "_send_telegram")
    check("D10 saqlagandan keyin darhol sahifa so'rovi (xuddi shu ulanish) fon xabarini KUTMAYDI (ikkalasi < 1 s, xabar hali "
          "yuborilmagan) — xabar keyin baribir yuborildi",
          _r10[0] == 200 and _r10[1] < 1.0 and _g10.status_code == 200 and _d10 < 1.0 and _hali10 == 0 and _b10,
          (_r10[0], _r10[1], _g10.status_code, _d10, _hali10, _b10))
    time.sleep(KECH + 0.3)
    # D11 ketma-ket 6 ta tez «+» (har biri 1,5 s lik xabar navbatga qo'yadi) — hammasi tez, 6 xabar, hech biri yuborilayotganda ulanish
    # ushlamaydi (mustaqil tekshiruv F1: zip 201 ning birinchi variantida bitta foydalanuvchi butun hovuzni band qilardi)
    time.sleep(KECH + 0.5)
    with TG_QULF:
        _n11 = len(TG)
    _v11 = []
    for _ in range(6):
        _t = time.time()
        _r = CL.post(f"/api/finished/{F}/add", json={"quantity": 1})
        _v11.append((_r.status_code, round(time.time() - _t, 3)))
    _t11 = time.time()
    while time.time() - _t11 < 6 * KECH + 5:
        with TG_QULF:
            _y11 = [x for x in TG[_n11:] if x[0] == "_send_telegram"]
        if len(_y11) >= 6:
            break
        time.sleep(0.2)
    check("D11 ketma-ket 6 ta tez saqlash — hammasi 200 va < 1 s, 6 xabar yuborildi; yuborilayotganda hovuzda band ulanish ≤ 1 (faqat o'sha "
          "paytda ishlanayotgan navbatdagi so'rov; avval xabarlar soni bilan o'sardi)",
          all(s_ == 200 and t_ < 1.0 for s_, t_ in _v11) and len(_y11) == 6 and all(0 <= x[3] <= 1 for x in _y11),
          (_v11, len(_y11), [x[3] for x in _y11]))
    with TG_QULF:
        _soni = len(TG)
    check("D9 hamma xabarlar haqiqatan yuborildi (yo'qolmadi) — kamida 9 ta yozuv", _soni >= 9, _soni)

server.should_exit = True
print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
