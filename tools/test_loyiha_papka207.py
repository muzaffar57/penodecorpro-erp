#!/usr/bin/env python3
"""
test_loyiha_papka207.py — kech155 (zip 207 «Loyiha papkasi»; EGASI SO'ROVI 23.10 03:57 va o'z maketi «2 · Yaxshilangan · Oltin papka»,
04:31: «rangi juda tilla — yumshat; ochilganda buyurtmalar hammasi oq fonda, tanlaganim ajralib tursin; qizil fonli „Muddati o'tgan“ va
katta qarz yozuvi qo'pol — fonsiz, ixcham»; tasdiq rasmi — «Ha, shunday qilinsin») + «Tizim salomatligi» — miqdori 0 detal.

NIMA UCHUN KERAK (O'LCHANGAN — `work/k207/ekran207.py`, zip 206 kodi, haqiqiy Chromium; sinov saytida «UMAR AKA DOM»):
  * ochiq loyiha sarlavhasi foni yopiq bilan AYNAN (#F8F8F6), tana #FCFCFB — oqdan deyarli farqsiz, chap chiziq / chegara / bo'shliq
    yo'q — ochilgan buyurtmalar qaysi loyihaniki ekani bilinmasdi;
  * qator belgilari — «Muddati o'tgan» to'q qizil FON oq yozuv, «Qarz: …» pushti fon — egasi: «qo'pol, chalg'itadi»;
  * «Tizim salomatligi»: qisman «Tayyor» qilingan buyurtmaning topshirilmagan detali miqdori 0 (jami 0) bo'ladi, tekshiruv esa
    `float(it.quantity or 1)` bilan 0 ni 1 deb olib, «order_total_mismatch» (yolg'on) chiqarardi (sinovda ORD-067-4).
BO'LIMLAR:
  S — manba (`templates/orders.html`, `crud.check_financial_consistency`).
  F — moliyaviy tekshiruv (ilovaning O'Z API si: buyurtma, yuk xati, qisman «Tayyor», /api/system/health-check).
  D — HAQIQIY Chromium (Playwright) + lokal server, ma'lumot API orqali: ochiq loyiha — och qum papka (quloq, chegara, yumaloq, bo'shliq),
      sarlavhasi yopiqdan farqli; ichidagi buyurtmalar — oq kartochka, tanlangani — och oltin + 3 px oltin ramka + «▶ OCHIQ» + oltin
      chegara; yopiq guruh — o'zgarmagan; qator belgilari fonsiz (matn — o'sha, rang kontrasti ≥ 4,5:1); loyiha sarlavhasi belgilari —
      o'sha; yopish / qayta ochish; tungi rejim; 1100 px va telefon 390 px — toshmaydi; JS xatosi yo'q.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL. Asl kodga (zip 206) qarshi
QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_loyiha_papka207.py
"""
import os
import io
import re
import sys
import glob
import time
import socket
import inspect
import tempfile
import datetime
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "loyiha_papka207_test"
_T = tempfile.mkdtemp(prefix="k207_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k207.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
OK = FAIL = 0
FAILED = []
NB = "\u00a0"                                     # son ko'rinishi — bo'linmas bo'shliq (`services.son_korinish`)


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


def xav(f, *a, standart=None, **k):
    try:
        return f(*a, **k)
    except Exception as e:                 # noqa: BLE001
        print(f"    (bajarilmadi: {getattr(f, '__name__', f)} — {type(e).__name__}: {str(e)[:200]})")
        return standart


def rgb(s):
    m = re.findall(r"[\d.]+", s or "")
    return tuple(float(x) for x in m[:3]) if len(m) >= 3 else None


def shaffof(s):
    """`rgba(0, 0, 0, 0)` / `transparent` — fon YO'Q"""
    s = (s or "").replace(" ", "")
    return s in ("rgba(0,0,0,0)", "transparent")


def _lum(c):
    def k(v):
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * k(c[0]) + 0.7152 * k(c[1]) + 0.0722 * k(c[2])


def kontrast(a, b):
    if not a or not b:
        return 0
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(float(int(h[i:i + 2], 16)) for i in (0, 2, 4))


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ORD = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
_STYLE = ORD[:ORD.find("</style>")]


def qoida(sel):
    """`sel{…}` qoidasining tanasi (birinchi aynan moslik) yoki None"""
    i = _STYLE.find(sel + "{")
    if i < 0:
        return None
    return _STYLE[i + len(sel) + 1:_STYLE.find("}", i)]


_pg = qoida(".proj-group.open")
check("S1 OCHIQ loyiha — papka: och qum fon (`--f-f3eee0`), 1 px chegara, yumaloq burchak, soya, atrofida bo'shliq; tepada «quloq» "
      "(`::before`); sarlavha `--f-ede6d8`",
      _pg is not None and "background:var(--f-f3eee0)" in _pg and "border:1px solid var(--ch-e5dfd3)" in _pg and "border-radius:" in _pg
      and "box-shadow:var(--shadow-card)" in _pg and "margin:20px 8px 12px" in _pg
      and 'content:""' in (qoida(".proj-group.open::before") or "")
      and "background:var(--f-ede6d8)" in (qoida(".proj-group.open > .proj-head, .proj-group.open > .proj-head:hover") or ""), _pg)
_kart = qoida(".proj-group.open > .proj-body .ord-item, .proj-group.open > .proj-body .ord-item:last-child")
check("S2 papka ichidagi buyurtma — OQ kartochka (`--white`, chegara, 10 px burchak, oraliq); tanlangani — `--gold-tint` + oltin chegara",
      _kart is not None and "background:var(--white)" in _kart and "border-radius:10px" in _kart and "margin-top:6px" in _kart
      and "background:var(--gold-tint);border-color:var(--gold)" in (qoida(".proj-group.open > .proj-body .ord-item.active") or ""), _kart)
_bel = re.findall(r"(\.oi-belgi[^{]*|\.oi-belgilar \.ort-qaytarish)\{([^}]*)\}", _STYLE)
check("S3 qator belgilari (`.oi-belgi*`, `.ort-qaytarish`) — FONSIZ, yumaloq chekkasiz, ichki chekka 0 (rang — matnda)",
      len(_bel) >= 8 and not [b for b in _bel if "background" in b[1] or "border-radius" in b[1]]
      and "padding:0;" in (qoida(".oi-belgi, .oi-belgilar .ort-qaytarish") or "")
      and qoida(".oi-belgi.qizil") == "color:var(--m-b91c1c)", [b for b in _bel if "background" in b[1] or "border-radius" in b[1]] or _bel)
check("S4 loyiha SARLAVHASI belgilari — o'sha (pushti / sariq / yashil fon): `.proj-debt`, `.pg-belgi.qizil`, `.pg-belgi.sariq`, `.proj-paid`",
      qoida(".proj-debt, .pg-belgi.qizil") == "background:var(--f-fee2e2);color:var(--m-b91c1c)"
      and qoida(".pg-belgi.sariq") == "background:var(--f-fef3c7);color:var(--m-92400e)"
      and qoida(".proj-paid") == "background:var(--f-dcfce7);color:var(--m-15803d)")
_tp = ORD[ORD.find("function toggleProject(pid)"):ORD.find("}", ORD.find("ordHolatSaqla();", ORD.find("function toggleProject(pid)"))) + 1]
check("S5 HTML / JS o'sha: `toggleProject` (klass `open` + tana ko'rinishi), qator `onclick` / `data-*`, guruh `data-urgency`",
      "const open = g.classList.toggle('open');" in _tp and "body.style.display = open ? 'block' : 'none';" in _tp
      and 'id="oi-{{ o.id }}" onclick="selectOrder({{ o.id }}, this)"' in ORD and 'data-urgency="{{ g_urgency }}"' in ORD
      and '<span class="oi-belgi qizil">Muddati o\'tgan</span>' in ORD and '<span class="oi-belgi qarz">Qarz: {{ (debt)|son(0) }} so\'m</span>' in ORD, _tp)
check("S6 ranglar — umumiy belgilar (xom hex YO'Q): yangi papka qoidalari va belgilar", not re.search(
    r"#[0-9A-Fa-f]{3,6}\b", "".join(x[1] for x in _bel) + (_pg or "") + (_kart or "") + (qoida(".proj-group.open::before") or "")))
with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import crud                                        # noqa: E402
_FC = inspect.getsource(crud.check_financial_consistency)
_FCK = "\n".join(re.sub(r"(?:^|\s)#(?:\s.*)?$", "", q) for q in _FC.splitlines())
check("S7 izchillik tekshiruvi: detallar yig'indisida miqdor `or 1` EMAS — 0 → 0, NULL → 1",
      "float(it.quantity or 1)" not in _FCK and "(1.0 if it.quantity is None else float(it.quantity))" in _FCK)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# tayyorgarlik — ma'lumot API orqali (xodim bosadigan amallar)
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, Project, Master, Order   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k207_a", PAROL, UserRole.ADMIN, "K207 Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="K207 Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
P1 = Project(company_id=1, client_name="Sardor K207", project_name="Andijon kottej K207", client_phone="+998901112207", total_budget=0,
             total_paid=0)
P2 = Project(company_id=1, client_name="Aziz K207", project_name="Yunusobod hovli K207", client_phone="+998935554207", total_budget=0,
             total_paid=0)
P3 = Project(company_id=1, client_name="Malika K207", project_name="Namangan uy K207", client_phone="+998977774207", total_budget=0,
             total_paid=0)
P4 = Project(company_id=1, client_name="Tekshiruv K207", project_name="Izchillik K207", client_phone="+998977770207", total_budget=0,
             total_paid=0)
US = Master(company_id=1, name="K207 Usta", phone="+998900002070")
s.add_all([PENO, P1, P2, P3, P4, US])
s.commit()
ID = {"PENO": PENO.id, "P1": P1.id, "P2": P2.id, "P3": P3.id, "P4": P4.id, "US": US.id}
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lg = C.post("/login", data={"username": "k207_a", "password": PAROL}, follow_redirects=False)
TK = (datetime.datetime.utcnow() + datetime.timedelta(hours=5)).date()


def kun(n):
    return (TK + datetime.timedelta(days=n)).isoformat()


def buyurtma(pid, muddat, detallar, qoralama=False):
    """detallar: [(nom, miqdor, narx), …] — panel"""
    tana = {"project_id": pid, "order_type": "product", "recipe_id": None, "master_id": ID["US"], "deadline": muddat, "is_draft": qoralama,
            "base_price": 600000, "loy_kg": None,
            "items": [{"name": n, "category": "panel", "width": 60, "thickness": 5, "length": 0, "quantity": q, "unit_price": p,
                       "is_coated": False, "penoplast_id": ID["PENO"], "price_per_m3": None, "finished_product_id": None}
                      for n, q, p in detallar]}
    r = C.post("/api/orders", json=tana)
    if r.status_code == 409:
        r = C.post("/api/orders?confirm_shortage=true", json=tana)
    return (r.json() or {}).get("id") if r.status_code == 200 else None


def tolov(oid, summa, tur="partial"):
    return C.post("/api/payments", json={"order_id": oid, "amount": summa, "payment_type": tur, "payment_method": "naqd", "notes": "K207"})


def topshir(oid, ulush, faqat=None):
    """faqat — detal nomi: faqat shu detal topshiriladi"""
    h = ((C.get(f"/api/orders/{oid}/delivery-status").json() or {}).get("items")) or []
    items = [{"order_item_id": x["id"], "quantity": round(x["remaining"] * ulush, 2)} for x in h
             if x.get("remaining", 0) > 0.0001 and (faqat is None or x.get("name") == faqat)]
    return C.post("/api/deliveries", json={"order_id": oid, "items": items, "received_by": "Qabul K207", "notes": "",
                                           "transport_carrier": "", "transport_cost": 0, "transport_payer": "client"})


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("F — «Tizim salomatligi»: miqdori 0 detal")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
def tekshiruv():
    r = C.get("/api/system/health-check")
    return r.status_code, ((r.json() if r.status_code == 200 else {}).get("financial") or {}).get("issues", [])


def mos_emas(iss, raqam):
    return [x for x in iss if x["type"] == "order_total_mismatch" and x["label"] == f"Buyurtma {raqam}"]


QIS = buyurtma(ID["P4"], kun(3), [("K207 karniz A", 4, 5000), ("K207 karniz B", 6, 20000)])     # 20 000 + 120 000
_am = []
if QIS:
    _am.append(topshir(QIS, 1, faqat="K207 karniz A").status_code)
    _am.append(C.post(f"/api/orders/{QIS}/ready").status_code)
_s = SessionLocal()
try:
    _o = _s.get(Order, QIS) if QIS else None
    _det = {it.name: (float(it.quantity) if it.quantity is not None else None, float(it.total_price or 0)) for it in (_o.items if _o else [])}
    _jami, _raqam_q = (float(_o.total_amount or 0), _o.order_number) if _o else (None, None)
finally:
    _s.close()
check("F0 fikstura: 2 detalli buyurtma (20 000 + 120 000), faqat birinchisi topshirildi, «Tayyor» (qisman) — 200; ikkinchi detal miqdori 0, "
      "jami 0; buyurtma jami 20 000 (= detallar)",
      _am == [200, 200] and _det.get("K207 karniz B") == (0.0, 0.0) and _det.get("K207 karniz A") == (4.0, 20000.0) and _jami == 20000.0,
      (_am, _det, _jami))
_st, ISS = tekshiruv()
check("F1 qisman «Tayyor» buyurtmasi — «Buyurtma summasi mos emas» YO'Q (ilgari detallar yig'indisi 140 000 deb chiqardi)",
      _st == 200 and not mos_emas(ISS, _raqam_q), (_st, mos_emas(ISS, _raqam_q)))
# F2 — haqiqiy nomuvofiqlik hali ham topiladi: miqdori 0 detal bor, lekin buyurtma jami uni ham hisoblagan (140 000)
BUZ = buyurtma(ID["P4"], kun(3), [("K207 buzuq A", 4, 5000), ("K207 buzuq B", 6, 20000)])
_s = SessionLocal()
try:
    _o = _s.get(Order, BUZ)
    _b = [it for it in _o.items if it.name == "K207 buzuq B"][0]
    _b.quantity, _b.total_price = 0, 0
    _o.total_amount = 140000                                   # detallar 20 000 — jami noto'g'ri
    _s.commit()
    _raqam_b = _o.order_number
finally:
    _s.close()
_st, ISS = tekshiruv()
_mb = mos_emas(ISS, _raqam_b)
check("F2 haqiqiy nomuvofiqlik topiladi: miqdori 0 detalli buyurtma jami 140 000, detallar 20 000 — «mos emas», matn aniq",
      len(_mb) == 1 and _mb[0]["detail"] == f"Jami summa: 140{NB}000 so'm, lekin detallar yig'indisi: 20{NB}000 so'm" and abs(_mb[0]["diff"] - 120000) < 1e-6,
      _mb)
# F3 — miqdor NULL — 1 deb olinadi (avvalgidek)
NUL = buyurtma(ID["P4"], kun(3), [("K207 nul", 1, 7000)])
_s = SessionLocal()
try:
    _o = _s.get(Order, NUL)
    _o.items[0].quantity = None
    _s.commit()
    _raqam_n, _jn = _o.order_number, float(_o.total_amount or 0)
finally:
    _s.close()
_st, ISS = tekshiruv()
check("F3 miqdori yo'q (NULL) detal — 1 dona deb olinadi (avvalgidek): jami 7 000 = narx × 1, «mos emas» YO'Q",
      _jn == 7000.0 and not mos_emas(ISS, _raqam_n), (_jn, mos_emas(ISS, _raqam_n)))
_s = SessionLocal()
try:
    _o = _s.get(Order, NUL)
    _o.total_amount = 5000
    _s.commit()
finally:
    _s.close()
_st, ISS = tekshiruv()
_mn = mos_emas(ISS, _raqam_n)
check("F3b … va NULL miqdorli buyurtma jami noto'g'ri bo'lsa (5 000) — topiladi (detallar 7 000)",
      len(_mn) == 1 and _mn[0]["detail"] == f"Jami summa: 5{NB}000 so'm, lekin detallar yig'indisi: 7{NB}000 so'm", _mn)
# tozalash — UI ro'yxatiga xalaqit bermasin (P4 — alohida loyiha, yopiq qoladi)

# ── UI fiksturasi
O = {}
O["otgan"] = buyurtma(ID["P1"], kun(-4), [("K207 panel", 20, 22000)])          # 440 000 — muddati o'tgan, qisman to'langan, yarmi topshirilgan
O["tolangan"] = buyurtma(ID["P1"], kun(5), [("K207 panel", 12, 25000)])        # to'liq to'langan, topshirilgan, «Tayyor»
O["qoralama"] = buyurtma(ID["P1"], kun(9), [("K207 panel", 8, 18000)], qoralama=True)
O["bugun"] = buyurtma(ID["P2"], kun(0), [("K207 panel", 10, 15000)])           # bugun muddati
O["qarzli"] = buyurtma(ID["P2"], kun(6), [("K207 panel", 15, 20000)])          # topshirilgan, «Tayyor», qarzi bor
O["yopiq"] = buyurtma(ID["P3"], kun(7), [("K207 panel", 6, 30000)])            # YOPIQ guruh
O["katta"] = buyurtma(ID["P1"], kun(-2), [("K207 panel", 20, 6200000)])        # 124 mln — 2-muddati o'tgan (sarlavha belgisi uzun)
O["ortiqcha"] = buyurtma(ID["P2"], kun(8), [("K207 panel", 1000, 25000)])     # 25 mln to'langan, 10 % topshirilib qisman «Tayyor» →
#                                                                                  jami 2,5 mln → «↩ Qaytarish kerak: 22 500 000 so'm»
_am = []
if all(O.values()):
    _am.append(tolov(O["otgan"], 200000, "zaklat").status_code)
    _am.append(topshir(O["otgan"], 0.5).status_code)
    _am.append(tolov(O["tolangan"], 300000, "final").status_code)
    _am.append(topshir(O["tolangan"], 1).status_code)
    _am.append(C.post(f"/api/orders/{O['tolangan']}/ready").status_code)
    _am.append(topshir(O["qarzli"], 1).status_code)
    _am.append(tolov(O["qarzli"], 100000).status_code)
    _am.append(C.post(f"/api/orders/{O['qarzli']}/ready").status_code)
    _am.append(tolov(O["ortiqcha"], 25000000, "final").status_code)
    _am.append(topshir(O["ortiqcha"], 0.1).status_code)
    _am.append(C.post(f"/api/orders/{O['ortiqcha']}/ready").status_code)
check("T0 fikstura: kirish, 8 buyurtma (3 loyihada), to'lov / topshirish / «Tayyor» / ortiqcha to'lov — hammasi 200",
      _lg.status_code in (302, 303) and all(O.values()) and _am and all(x == 200 for x in _am), (O, _am))

# ── lokal server
import uvicorn                                     # noqa: E402
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
BU = f"http://127.0.0.1:{port}"

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D — HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
PW_BOR = True
try:
    from playwright.sync_api import sync_playwright
except Exception:                          # noqa: BLE001
    PW_BOR = False
check("D0 Python `playwright` bor", PW_BOR)

OLCH = r"""() => {
  const cs = (e, p) => e ? getComputedStyle(e)[p] : null;
  const r = (e) => { if (!e) return null; const b = e.getBoundingClientRect(); return {x: b.left, y: b.top, w: b.width, h: b.height, b: b.bottom, o: b.right}; };
  const gr = {};
  document.querySelectorAll('.ord-list .proj-group').forEach(g => {
    const nom = (g.querySelector('.proj-name') || {}).textContent || '';
    const h = g.querySelector('.proj-head'), b = g.querySelector('.proj-body'), q = getComputedStyle(g, '::before');
    gr[nom] = {ochiq: g.classList.contains('open'), fon: cs(g, 'backgroundColor'), chegara: cs(g, 'borderTopWidth') + ' ' + cs(g, 'borderTopColor'),
      burchak: cs(g, 'borderBottomRightRadius'), soya: cs(g, 'boxShadow'), mt: cs(g, 'marginTop'), mb: cs(g, 'marginBottom'), r: r(g),
      quloq: q.content, quloq_fon: q.backgroundColor, quloq_h: q.height, quloq_d: q.display,
      sarlavha_fon: cs(h, 'backgroundColor'), nom_rang: cs(g.querySelector('.proj-name'), 'color'), tana_fon: cs(b, 'backgroundColor'),
      tana_korinadi: !!b && b.offsetParent !== null, sarlavha_r: r(h),
      belgilar: [...g.querySelectorAll('.proj-head .pg-belgi, .proj-head .proj-debt, .proj-head .proj-paid')].map(x => ({k: x.className, fon: cs(x, 'backgroundColor'), t: x.innerText.trim(), r: r(x)})),
      son_rang: cs(g.querySelector('.proj-count'), 'color'), faol_rang: cs(g.querySelector('.proj-faol'), 'color'),
      faol_inline: (g.querySelector('.proj-count span') || {getAttribute: () => null}).getAttribute('style'),
      qatorlar: [...g.querySelectorAll('.proj-body .ord-item')].filter(x => x.offsetParent !== null).map(x => {
        const bf = getComputedStyle(x, '::before');
        return {id: Number(x.dataset.orderId), fon: cs(x, 'backgroundColor'), chegara: cs(x, 'borderTopWidth') + ' ' + cs(x, 'borderTopColor'),
          chap: cs(x, 'borderLeftColor'), burchak: cs(x, 'borderTopRightRadius'), soya: cs(x, 'boxShadow'), faol: x.classList.contains('active'),
          yorliq: bf.content, r: r(x),
          raqam_kesik: (() => { const e = x.querySelector('.ord-num'); return e ? e.scrollWidth - e.clientWidth : null; })(),
          sana_kesik: (() => { const e = x.querySelector('.oi-sana'); return e ? e.scrollWidth - e.clientWidth : null; })(),
          ort: (() => { const e = x.querySelector('.ort-qaytarish'); return e ? r(e) : null; })()};
      })};
  });
  const bel = [...document.querySelectorAll('.ord-list .oi-belgilar > *')].filter(x => x.offsetParent !== null).map(x => {
    const q = x.closest('.ord-item');
    return {t: x.innerText.trim(), k: x.className, fon: cs(x, 'backgroundColor'), rang: cs(x, 'color'), pad: cs(x, 'paddingLeft') + ' ' + cs(x, 'paddingRight'),
      radius: cs(x, 'borderTopLeftRadius'), h: x.getBoundingClientRect().height, qator_fon: cs(q, 'backgroundColor'), qator: Number(q.dataset.orderId),
      iz: x.querySelector('.oi-mini') ? cs(x.querySelector('.oi-mini'), 'backgroundColor') : null, r: r(x)};
  });
  const L = document.querySelector('.ord-list'), C = document.querySelector('.ord-chap');
  return {gr, bel, ro_toshma: L ? L.scrollWidth - L.clientWidth : null, chap_toshma: C ? C.scrollWidth - C.clientWidth : null,
          sahifa_toshma: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          tema: document.documentElement.getAttribute('data-theme')};
}"""
OCH = "(ids) => ids.forEach(pid => { const g = document.querySelector(`.proj-group[data-project-id=\"${pid}\"]`); if (g && !g.classList.contains('open')) toggleProject(pid); })"
YOP = "(ids) => ids.forEach(pid => { const g = document.querySelector(`.proj-group[data-project-id=\"${pid}\"]`); if (g && g.classList.contains('open')) toggleProject(pid); })"
NAT = {}
XATO = []

if PW_BOR and all(O.values()):
    with sync_playwright() as pw:
        _exe = None
        for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                "chrome-linux", "chrome"))):
            _exe = _y
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()

        def sahifa(w, h, tel=False, tungi=False):
            ctx = br.new_context(viewport={"width": w, "height": h}, timezone_id="Asia/Tashkent", locale="uz-UZ", is_mobile=tel, has_touch=tel)
            ctx.set_default_timeout(20000)
            ctx.route(re.compile(r"^https://.*"), lambda r: r.fulfill(status=204, body=""))
            if tungi:
                ctx.add_init_script("try { localStorage.setItem('theme', 'dark'); } catch (e) {}")
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: XATO.append(str(e)[:300]))
            xav(pg.goto, BU + "/login")
            xav(pg.fill, "input[name=username]", "k207_a")
            xav(pg.fill, "input[name=password]", PAROL)
            xav(pg.press, "input[name=password]", "Enter")
            xav(pg.wait_for_load_state, "networkidle")
            xav(pg.goto, BU + "/orders")
            xav(pg.wait_for_load_state, "networkidle")
            xav(pg.evaluate, YOP, [ID["P1"], ID["P2"], ID["P3"], ID["P4"]])
            xav(pg.evaluate, OCH, [ID["P1"], ID["P2"]])
            return ctx, pg

        def tanla(pg, id):
            xav(pg.evaluate, f"() => {{ const e = document.querySelector('.ord-list .ord-item[data-order-id=\"{id}\"]'); if (e) e.click(); }}")
            xav(pg.wait_for_load_state, "networkidle")
            xav(pg.wait_for_timeout, 500)

        # ── kompyuter 1440 × 1100
        ctx, pg = sahifa(1440, 1100)
        tanla(pg, O["otgan"])
        NAT["k"] = xav(pg.evaluate, OLCH)
        # yopish → qayta ochish
        xav(pg.evaluate, YOP, [ID["P1"]])
        xav(pg.wait_for_timeout, 200)
        NAT["yopildi"] = xav(pg.evaluate, OLCH)
        xav(pg.evaluate, OCH, [ID["P1"]])
        xav(pg.wait_for_timeout, 200)
        NAT["qayta"] = xav(pg.evaluate, OLCH)
        # sichqoncha oq kartochka ustida — fon deyarli oq (`--f-fcfbf9`), tanlanganniki o'zgarmaydi
        xav(pg.hover, f'.ord-list .ord-item[data-order-id="{O["tolangan"]}"]')
        xav(pg.wait_for_timeout, 250)
        NAT["hover"] = xav(pg.evaluate, f"() => getComputedStyle(document.querySelector('.ord-list .ord-item[data-order-id=\"{O['tolangan']}\"]')).backgroundColor")
        ctx.close()

        # ── tor ekran 901–1150 (ro'yxat ustuni 260 px) va telefon 390 / 320
        NAT["tor"] = {}
        for _w, _tel in ((1150, False), (1100, False), (1000, False), (901, False), (390, True), (320, True)):
            ctx, pg = sahifa(_w, 900, tel=_tel)
            tanla(pg, O["otgan"])
            xav(pg.evaluate, "() => { const w = document.getElementById('ordPageWrap'); if (w) w.scrollTop = 0; window.scrollTo(0, 0); }")
            NAT["tor"][_w] = xav(pg.evaluate, OLCH)
            ctx.close()

        # ── tungi rejim
        ctx, pg = sahifa(1440, 1100, tungi=True)
        tanla(pg, O["otgan"])
        NAT["t"] = xav(pg.evaluate, OLCH)
        ctx.close()
        br.close()

    def nom(n):
        return n + " K207"

    K = NAT.get("k") or {}
    G = K.get("gr") or {}
    A, Y, N = G.get(nom("Andijon kottej")) or {}, G.get(nom("Yunusobod hovli")) or {}, G.get(nom("Namangan uy")) or {}
    QUM, QUM_SARLAVHA, QUM_CHEG = hexrgb("#F3EEE0"), hexrgb("#EDE6D8"), hexrgb("#E5DFD3")
    OQ, OLTIN, OLTIN_OCH, BG = (255.0, 255.0, 255.0), (185.0, 120.0, 63.0), (248.0, 242.0, 235.0), hexrgb("#F8F8F6")
    check("D1 OCHIQ loyiha — papka: fon och qum (#F3EEE0, ilgari #FCFCFB), 1 px chegara (#E5DFD3), yumaloq (12 px), soya, tepada 20 px "
          "bo'shliq, «quloq» (#EDE6D8)",
          A.get("ochiq") and rgb(A.get("fon")) == QUM and A.get("chegara") == "1px rgb(229, 223, 211)" and A.get("burchak") == "12px"
          and (A.get("soya") or "none") != "none" and A.get("mt") == "20px" and A.get("quloq") == '""' and rgb(A.get("quloq_fon")) == QUM_SARLAVHA
          and A.get("quloq_d") == "block" and A.get("quloq_h") == "11px",
          {k: A.get(k) for k in ("ochiq", "fon", "chegara", "burchak", "soya", "mt", "quloq", "quloq_fon", "quloq_d", "quloq_h")})
    check("D2 ochiq loyiha SARLAVHASI yopiqdan farqli (#EDE6D8 ↔ yopiq #F8F8F6 — ilgari AYNAN bir xil), nomi oltin matn",
          rgb(A.get("sarlavha_fon")) == QUM_SARLAVHA and rgb(N.get("sarlavha_fon")) == BG and rgb(A.get("nom_rang")) == (143.0, 91.0, 42.0)
          and rgb(N.get("nom_rang")) != (143.0, 91.0, 42.0), (A.get("sarlavha_fon"), N.get("sarlavha_fon"), A.get("nom_rang"), N.get("nom_rang")))
    _qa = {q["id"]: q for q in A.get("qatorlar") or []}
    _oq = [q for q in (A.get("qatorlar") or []) + (Y.get("qatorlar") or []) if not q["faol"]]
    check("D3 papka ichidagi TANLANMAGAN buyurtmalar — OQ kartochka (fon #FFF, 1 px #E5DFD3 chegara, 10 px burchak)",
          len(_oq) == 6 and all(rgb(q["fon"]) == OQ and q["chegara"] == "1px rgb(229, 223, 211)" and q["burchak"] == "10px" for q in _oq),
          _oq)
    _f = _qa.get(O["otgan"]) or {}
    check("D4 TANLANGAN buyurtma ajralib turadi: och oltin fon, 3 px oltin ramka (+ muddat chizig'i), «▶ OCHIQ», oltin chegara",
          _f.get("faol") and rgb(_f.get("fon")) == OLTIN_OCH and "rgb(185, 120, 63) 0px 0px 0px 3px inset" in (_f.get("soya") or "")
          and "rgb(220, 38, 38) 7px 0px 0px 0px inset" in (_f.get("soya") or "") and _f.get("yorliq") == '"▶ OCHIQ"'
          and _f.get("chegara") == "1px rgb(185, 120, 63)", _f)
    _ichida = all(A["r"]["x"] + 7 <= q["r"]["x"] and q["r"]["o"] <= A["r"]["o"] - 7 and A["sarlavha_r"]["b"] <= q["r"]["y"] and q["r"]["b"] <= A["r"]["b"] - 7
                  for q in A.get("qatorlar") or []) if A.get("r") else False
    _qr = sorted((q["r"] for q in A.get("qatorlar") or []), key=lambda r: r["y"])
    check("D5 kartochkalar papka ICHIDA (har chetdan ≥ 8 px), orasida bo'shliq (≥ 5 px); papkalar orasida ≥ 12 px",
          len(_qr) == 4 and _ichida and all(_qr[i + 1]["y"] - _qr[i]["b"] >= 5 for i in range(3))
          and Y.get("r") and A.get("r") and Y["r"]["y"] - A["r"]["b"] >= 12, (A.get("r"), _qr, Y.get("r")))
    check("D6 YOPIQ guruh o'zgarmagan: fon / chegara / bo'shliq yo'q, sarlavha #F8F8F6, tana yashirin",
          not N.get("ochiq") and shaffof(N.get("fon")) and N.get("chegara", "").startswith("0px") and N.get("mt") == "0px"
          and N.get("quloq") in ("none", "normal") and not N.get("tana_korinadi"), N)
    _bl = K.get("bel") or []
    _matn = {b["t"] for b in _bl}

    def _oraliqlar(bl):
        """bir qatordagi (bir satrdagi) qo'shni belgilar orasidagi gorizontal bo'shliq"""
        q = {}
        for x in bl:
            q.setdefault(x["qator"], []).append(x)
        g = []
        for v in q.values():
            v = sorted(v, key=lambda x: (round(x["r"]["y"]), x["r"]["x"]))
            for i in range(len(v) - 1):
                if abs(v[i + 1]["r"]["y"] - v[i]["r"]["y"]) < 2:
                    g.append(round(v[i + 1]["r"]["x"] - v[i]["r"]["o"], 1))
        return g
    _or = _oraliqlar(_bl)
    check("D7 qator belgilari FONSIZ (shaffof), ichki chekka 0, yumaloqsiz, balandligi ≤ 18 px — oq va tanlangan kartochkada ham",
          len(_bl) >= 8 and all(shaffof(b["fon"]) and b["pad"] == "0px 0px" and b["radius"] == "0px" and b["h"] <= 18.5 for b in _bl),
          [b for b in _bl if not (shaffof(b["fon"]) and b["pad"] == "0px 0px" and b["h"] <= 18.5)] or _bl)
    check("D7c belgilar fonsiz bo'lgach bir-biriga yopishmaydi: bir satrdagi qo'shni belgilar orasida ≥ 10 px (12 px)",
          _or and all(x >= 10 for x in _or), _or)
    check("D7b belgilar matni o'sha: «Muddati o'tgan», «Qarz: …», «✓ To'langan», «To'liq topshirildi», «Bugun muddati», topshirish %",
          {"Muddati o'tgan", "✓ To'langan", "To'liq topshirildi", "Bugun muddati"} <= _matn and any(t.startswith("Qarz: ") for t in _matn)
          and any(t.endswith("%") for t in _matn), _matn)
    _qz = [b for b in _bl if "qizil" in b["k"]]
    check("D8 «Muddati o'tgan» — qizil MATN (#B91C1C, ilgari oq yozuv to'q qizil fonda), «Qarz» ham qizil; har belgi o'z kartochkasida "
          "≥ 4,5:1 kontrast",
          _qz and all(rgb(b["rang"]) == (185.0, 28.0, 28.0) for b in _qz)
          and all(rgb(b["rang"]) == (185.0, 28.0, 28.0) for b in _bl if "qarz" in b["k"])
          and all(kontrast(rgb(b["rang"]), rgb(b["qator_fon"])) >= 4.5 for b in _bl),
          [(b["t"], b["rang"], b["qator_fon"], round(kontrast(rgb(b["rang"]), rgb(b["qator_fon"])), 2)) for b in _bl])
    _iz = [b["iz"] for b in _bl if b["iz"]]
    check("D8b topshirish chizig'ining izi ko'rinadi — och ko'k (#DBEAFE; fon olingach oq iz oq kartochkada yo'qolardi)",
          _iz and all(rgb(x) == (219.0, 234.0, 254.0) for x in _iz), _iz)
    _sb = A.get("belgilar") or []
    check("D9 loyiha SARLAVHASI belgilari o'sha: «Muddati o'tgan» va «Qarz: …» — pushti fon (#FEE2E2)",
          any(b["t"].startswith("Muddati o'tgan") and rgb(b["fon"]) == (254.0, 226.0, 226.0) for b in _sb)
          and any(b["t"].startswith("Qarz:") and rgb(b["fon"]) == (254.0, 226.0, 226.0) for b in _sb), _sb)
    _yp = ((NAT.get("yopildi") or {}).get("gr") or {}).get(nom("Andijon kottej")) or {}
    _qy = ((NAT.get("qayta") or {}).get("gr") or {}).get(nom("Andijon kottej")) or {}
    check("D10 yopilganda papka uslubi ketadi (fon / chegara / bo'shliq yo'q, sarlavha #F8F8F6), qayta ochilganda qaytadi; tanlov saqlanadi",
          not _yp.get("ochiq") and shaffof(_yp.get("fon")) and _yp.get("mt") == "0px" and rgb(_yp.get("sarlavha_fon")) == BG
          and _qy.get("ochiq") and rgb(_qy.get("fon")) == QUM and any(q["faol"] and q["id"] == O["otgan"] for q in _qy.get("qatorlar") or []),
          (_yp, _qy.get("fon")))
    check("D10b sichqoncha oq kartochka ustida — fon deyarli oq (#FCFBF9), tanlanganga o'xshamaydi",
          rgb(NAT.get("hover")) == hexrgb("#FCFBF9"), NAT.get("hover"))
    _T = NAT.get("t") or {}
    _TG = _T.get("gr") or {}
    _ta = _TG.get(nom("Andijon kottej")) or {}
    _tq = {q["id"]: q for q in _ta.get("qatorlar") or []}
    check("D11 tungi rejim: papka (#2F2B1E) va sarlavha (#332D1F) qorong'i, kartochkalar qorong'i karta (#1E212A), tanlangani #2E2418",
          _T.get("tema") == "dark" and rgb(_ta.get("fon")) == hexrgb("#2F2B1E") and rgb(_ta.get("sarlavha_fon")) == hexrgb("#332D1F")
          and all(rgb(q["fon"]) == hexrgb("#1E212A") for q in _tq.values() if not q["faol"])
          and rgb((_tq.get(O["otgan"]) or {}).get("fon")) == hexrgb("#2E2418"), (_T.get("tema"), _ta.get("fon"), _ta.get("sarlavha_fon"), _tq))
    _tb = _T.get("bel") or []
    check("D11b tungi rejim: hamma belgi fonsiz, o'z kartochkasida ≥ 4,5:1",
          len(_tb) >= 8 and all(shaffof(b["fon"]) and kontrast(rgb(b["rang"]), rgb(b["qator_fon"])) >= 4.5 for b in _tb),
          [(b["t"], b["rang"], b["qator_fon"], round(kontrast(rgb(b["rang"]), rgb(b["qator_fon"])), 2)) for b in _tb])
    _tor = NAT.get("tor") or {}
    def _chekka(w):
        return 4 if 901 <= w <= 1150 else 7          # 901–1150 px: papka chekkalari ataylab torroq (U1)

    check("D12 901–1150 px (ro'yxat 260 px), telefon 390 va 320 px: papka ochiq, kartochkalar ichida, ro'yxat / chap ustun / sahifa yon "
          "tomonga toshmaydi",
          set(_tor) == {1150, 1100, 1000, 901, 390, 320} and all(
              v and (v.get("gr") or {}).get(nom("Andijon kottej"), {}).get("ochiq") and v.get("ro_toshma", 9) <= 0
              and (v.get("chap_toshma") or 0) <= 1 and v.get("sahifa_toshma", 9) <= 1
              and all(g["r"]["x"] + _chekka(w) <= q["r"]["x"] and q["r"]["o"] <= g["r"]["o"] - _chekka(w)
                      for g in [(v.get("gr") or {}).get(nom("Andijon kottej"))] for q in g.get("qatorlar") or [])
              for w, v in _tor.items()),
          {w: (v.get("ro_toshma"), v.get("chap_toshma"), v.get("sahifa_toshma")) for w, v in _tor.items() if v})

    def _kartochkalar(v):
        return [q for g in (v.get("gr") or {}).values() if g.get("ochiq") for q in g.get("qatorlar") or []]

    _kesik = {w: [(q["id"], q["raqam_kesik"], q["sana_kesik"]) for q in _kartochkalar(v) if (q["raqam_kesik"] or 0) > 0 or (q["sana_kesik"] or 0) > 0]
              for w, v in list(_tor.items()) + [(1440, K)] if v}
    check("D14 (mustaqil tekshiruv U1) HAMMA kenglikda (1440, 1150, 1100, 1000, 901, 390, 320) ochiq papkadagi buyurtma RAQAMI va SANASI "
          "kesilmaydi (ilgari 901–1150 px da 14 / 14 «ORD-0…»)",
          len(_kesik) == 7 and not any(_kesik.values()) and all(len(_kartochkalar(v)) == 7 for v in list(_tor.values()) + [K]), _kesik)

    def _ort(v):
        return [(q["ort"], q["r"]) for q in _kartochkalar(v) if q.get("ort")]

    _ortlar = {w: _ort(v) for w, v in list(_tor.items()) + [(1440, K)] if v}
    check("D15 (mustaqil tekshiruv U3) «↩ Qaytarish kerak: 22 500 000 so'm» kartochka ICHIDA (ilgari 901–1150 px da 12 px, 320 px da 8 px "
          "chiqardi)",
          len(_ortlar) == 7 and all(len(x) == 1 and x[0][0]["o"] <= x[0][1]["o"] - 1 for x in _ortlar.values()), _ortlar)

    def _ustma(v):
        out = []
        for g in (v.get("gr") or {}).values():
            bl = g.get("belgilar") or []
            for a in bl:
                for b in bl:
                    if a is not b and a["r"]["x"] < b["r"]["x"] and a["r"]["o"] > b["r"]["x"] + 0.5 and a["r"]["y"] < b["r"]["b"] and b["r"]["y"] < a["r"]["b"]:
                        out.append((a["t"], b["t"], round(a["r"]["o"] - b["r"]["x"], 1)))
        return out

    _ust = {w: _ustma(v) for w, v in list(_tor.items()) + [(1440, K), ("tungi", NAT.get("t") or {})] if v}
    check("D16 (mustaqil tekshiruv U4) loyiha sarlavhasida «Muddati o'tgan · 2 ta buyurtma» va «Qarz: …» bir-birining ustiga chiqmaydi (ilgari "
          "50–107 px)",
          len(_ust) == 8 and not any(_ust.values())
          and any(b["t"].startswith("Muddati o'tgan · 2 ta") for b in (A.get("belgilar") or [])), _ust)
    _son = [(nm, g.get("son_rang"), g.get("faol_rang"), g.get("sarlavha_fon")) for v in (K, NAT.get("t") or {})
            for nm, g in (v.get("gr") or {}).items() if g.get("ochiq")]
    check("D17 (mustaqil tekshiruv U2) ochiq papka sarlavhasida «N ta ·» va «N faol» ≥ 4,5:1 (yorug' va tungi; ilgari 4,17 / 4,04); «faol» "
          "rangi INLINE emas (klass)",
          len(_son) == 4 and all(kontrast(rgb(a), rgb(f)) >= 4.5 and kontrast(rgb(b), rgb(f)) >= 4.5 for _, a, b, f in _son)
          and not any(g.get("faol_inline") for v in (K, NAT.get("t") or {}) for g in (v.get("gr") or {}).values()),
          [(nm, a, b, f, round(kontrast(rgb(a), rgb(f)), 2), round(kontrast(rgb(b), rgb(f)), 2)) for nm, a, b, f in _son])
    check("D13 sahifada JS xatosi yo'q (kompyuter, tor, telefon, tungi)", not XATO, XATO)
server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
