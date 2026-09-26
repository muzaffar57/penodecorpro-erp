#!/usr/bin/env python3
"""test_naqd_kassa.py — kech88 darvozasi (2026-09-26, 105 / 107 / 108-band).

105-band (O'LCHANGAN — probe105, SQLite = PG): kirim hujjatining qo'shimcha xarajatlari (transport / tushirish /
yuklash / boshqa) oylik hisobotning "Naqd xarajatlar" ko'rsatkichiga (`naqd_xarajat_jami`) KIRMASDI; "tannarxga
qo'shish" bilan yozilganlari bosh sahifa "Chiqim" ida ham UMUMAN yo'q edi (kunlik xarajatda esa bor). Endi:
`kirim_xarajatlari` (ikkala manba — `KIRIM_XARAJAT_MANBA` va `KIRIM_TANNARX_MANBA`) naqdga qo'shiladi,
`kirim_xarajatlari_jamida` — shulardan `jami_xarajat` ichida ham bor qismi (bosh sahifa ikki marta sanamaydi).
Qo'lda yozilgan xarajat ("manual", kategoriyasi "transport_kirim" bo'lsa ham) — kirim hujjati EMAS.

107-band (O'LCHANGAN — probe105b C4 / C5; 104-band QARORI): korxona to'lagan yetkazish transporti
(`Delivery.company_transport_cost`) kassa balansidan chiqib ketgan pul sifatida ayriladi (ilgari yo'q edi).
108-band (O'LCHANGAN — probe105b C7): eski oylik forma (`services.save_monthly_expense`) arenda / elektr / tushlik /
soliqni `MonthlyExpense` VA `monthly_form` tranzaksiyasiga yozadi — kassa ikkalasini ham ayirardi. Endi oylik
hisobot qoidasi: shu oy / kategoriya uchun tranzaksiya bo'lsa — faqat tranzaksiya, bo'lmasa — `MonthlyExpense`.

Bo'limlar: A naqd xarajat · B bosh sahifa "Chiqim" (node) · C kassa · K boshqa korxona · U Moliya sahifasi (node) ·
H kod (statik).
Ishga tushirish (repo ildizidan):
    python3 tools/test_naqd_kassa.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_naqd_kassa.py
"""
import os
import re
import sys
import json
import shutil
import inspect
import tempfile
import subprocess
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "naqd_kassa_test"
_T = tempfile.mkdtemp(prefix="naqd_kassa_")
_DB = os.path.join(_T, "naqd_kassa_test.db")

if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres",
               isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import services                                # noqa: E402
    import models                                  # noqa: E402

from database import SessionLocal                  # noqa: E402
from models import (                               # noqa: E402
    UserRole, Project, Inventory, ExpenseTransaction, MonthlyExpense, Order, OrderType, Delivery,
)
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
        print(f"  ✗ {label}   {str(detail)[:400]}")


def section(t):
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"
        self.headers = {}

    def json(self):
        return {}


def req(c, metod, url, **k):
    try:
        return getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        return _Xato(e)


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def tartibda(src, *qismlar):
    """Qismlar src ichida AYNAN shu tartibda uchraydimi (find — topilmasa False)."""
    i = 0
    for q in qismlar:
        j = src.find(q, i)
        if j < 0:
            return False
        i = j + len(q)
    return True


def teng(a, b, tol=0.005):
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:                      # noqa: BLE001
        return False


def ayir(a, b):
    try:
        return float(b) - float(a)
    except Exception:                      # noqa: BLE001
        return None


NOW = datetime.now()
Y, M = NOW.year, NOW.month


def oy_oldin(k):
    y, m = Y, M - k
    while m <= 0:
        m += 12
        y -= 1
    return y, m


_db = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "NK88_admin", "Parol123!", UserRole.ADMIN, "NK88 Admin", company_id=1)
if not _db.get(Company, 2):
    _db.add(Company(id=2, name="NK88 Korxona B"))
    _db.commit()


def material(nom, peno=False, qoldiq=0.0, cid=1):
    it = Inventory(company_id=cid, item_name=nom, unit=("blok" if peno else "kg"), stock_quantity=qoldiq,
                   price_per_unit=1000, volume_per_unit=(1.0 if peno else None), is_penoplast=peno,
                   category=("Penoplast" if peno else "Akril"))
    _db.add(it)
    _db.commit()
    return it.id


_pr = Project(company_id=1, client_name="NK88 mijoz", project_name="NK88 loyiha", total_budget=0, total_paid=0)
_db.add(_pr)
_db.commit()
PRJ = _pr.id
_db.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = C.post("/login", data={"username": "NK88_admin", "password": "Parol123!"}, follow_redirects=False)
check("0 login", _lr.status_code in (200, 302, 303), _lr.status_code)


def hisobot(y=None, m=None):
    d = js(req(C, "get", "/api/finance/report", params={"year": y or Y, "month": m or M}))
    return d if isinstance(d, dict) else {}


def tarix(y=None, m=None):
    d = js(req(C, "get", "/api/finance/history"))
    if not isinstance(d, list):
        return {}
    return next((h for h in d if isinstance(h, dict) and h.get("year") == (y or Y) and h.get("month") == (m or M)), {})


def kassa():
    d = js(req(C, "get", "/api/finance/cash-balance"))
    return d if isinstance(d, dict) else {}


_n = [0]


def kirim(qatorlar, extra=None, add=False, **kw):
    _n[0] += 1
    tana = {"items": qatorlar, "add_to_cost": add, "document_number": f"NK88-{_n[0]}", "notes": f"NK88 kirim {_n[0]}"}
    if extra:
        tana.update({"transport_cost": extra[0], "tushirish_cost": extra[1], "yuklash_cost": extra[2],
                     "boshqa_cost": extra[3]})
    tana.update(kw)
    return req(C, "post", "/api/inventory/receipt", json=tana)


def q(mid, n=10, narx=1000, **kw):
    d = {"inventory_id": mid, "quantity": n, "price_per_unit": narx}
    d.update(kw)
    return d


def tranzaksiya(summa, kat="boshqa", sana=None, manba="manual", cid=1, izoh="NK88"):
    s = SessionLocal()
    try:
        t = ExpenseTransaction(company_id=cid, date=sana or NOW, category=kat, amount=summa, notes=izoh,
                               created_by="NK88", source=manba)
        s.add(t)
        s.commit()
        return t.id
    finally:
        s.close()


# ── node yordamchisi: shablondagi funksiyani HAQIQIY hisobot / kassa ma'lumoti bilan yurgizish ──
_NODE = shutil.which("node")
_JS_YURGIZ = os.path.join(_T, "yurgiz.js")
with open(_JS_YURGIZ, "w", encoding="utf-8") as _f:
    _f.write(r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const data = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const els = {};
global.document = { getElementById: id => (els[id] = els[id] || { id, style: {}, textContent: '', innerHTML: '' }) };
global.fetch = async () => ({ ok: true, json: async () => data });
global.fmt = n => String(Math.round(Number(n || 0) * 100) / 100);
global.fmtFull = global.fmt;
global.escapeHtml = s => String(s == null ? '' : s);
const f = eval('(' + src + ')');
(async () => {
  await f(data);
  const o = {};
  for (const [k, v] of Object.entries(els)) o[k] = { t: String(v.textContent), h: String(v.innerHTML) };
  console.log('NATIJA_JS:' + JSON.stringify(o));
})().catch(e => console.log('NATIJA_JS:' + JSON.stringify({ xato: String(e) })));
""")


def shablon_funksiya(fayl, bosh):
    try:
        with open(os.path.join(ROOT, "templates", fayl), encoding="utf-8") as f:
            src = f.read()
    except Exception:                      # noqa: BLE001
        return ""
    i = src.find(bosh)
    if i < 0:
        return ""
    j = src.find("\n}\n", i)
    return src[i:j + 2] if j > 0 else ""


def js_yurgiz(fn_src, data):
    if not _NODE or not fn_src:
        return {"xato": "node yoki funksiya yo'q"}
    fs = os.path.join(_T, "fn.js")
    fd = os.path.join(_T, "data.json")
    with open(fs, "w", encoding="utf-8") as f:
        f.write(fn_src)
    with open(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    try:
        out = subprocess.run([_NODE, _JS_YURGIZ, fs, fd], capture_output=True, text=True, timeout=60).stdout
    except Exception as e:                 # noqa: BLE001
        return {"xato": str(e)}
    for line in out.splitlines():
        if line.startswith("NATIJA_JS:"):
            try:
                return json.loads(line[len("NATIJA_JS:"):])
            except Exception as e:         # noqa: BLE001
                return {"xato": str(e)}
    return {"xato": out[:300]}


_CASHFLOW = shablon_funksiya("dashboard.html", "async function loadCashFlow(")


def bosh_sahifa(rep):
    """Bosh sahifa "Kirim / Chiqim / Balans" — sahifaning O'Z `loadCashFlow` funksiyasi bilan."""
    o = js_yurgiz(_CASHFLOW, rep)
    h = ((o.get("cashFlow") or {}).get("h")) if isinstance(o, dict) else None
    if not h:
        return None
    sonlar = re.findall(r">(-?\d+(?:\.\d+)?)</span>", h)
    return [float(x) for x in sonlar] if len(sonlar) == 3 else None


def bosh_chiqim(rep):
    b = bosh_sahifa(rep)
    return b[1] if b else None


# ═══════════════════════════════════════════════════════════════════════════
section("A — \"Naqd xarajatlar\": kirim hujjatining qo'shimcha xarajatlari (105-band)")
MA = {k: material(f"NK88 {k}") for k in ("A1", "A2", "A3", "A4", "A5a", "A5b", "A7", "C6")}

h0 = hisobot()
r = kirim([q(MA["A1"])])
h1 = hisobot()
check("A1 qo'shimchasiz kirim: naqd +10 000, kirim_xarajatlari 0 (nazorat)",
      r.status_code == 200 and teng(ayir(h0.get("naqd_xarajat_jami"), h1.get("naqd_xarajat_jami")), 10000)
      and teng(h1.get("kirim_xarajatlari"), 0), [r.status_code, h0.get("naqd_xarajat_jami"), h1.get("naqd_xarajat_jami"),
                                               h1.get("kirim_xarajatlari")])
b0, b1 = bosh_chiqim(h0), bosh_chiqim(h1)
check("A1b ... bosh sahifa Chiqim +10 000", teng(ayir(b0, b1), 10000), [b0, b1])

r = kirim([q(MA["A2"])], (500, 200, 100, 50), False)
h2 = hisobot()
check("A2 tannarxga QO'SHILMAGAN 850 (500 + 200 + 100 + 50): naqd +10 850 (ilgari 10 000)",
      r.status_code == 200 and teng(ayir(h1.get("naqd_xarajat_jami"), h2.get("naqd_xarajat_jami")), 10850),
      [r.status_code, ayir(h1.get("naqd_xarajat_jami"), h2.get("naqd_xarajat_jami"))])
check("A2b ... kirim_xarajatlari +850, kirim_xarajatlari_jamida +850",
      teng(ayir(h1.get("kirim_xarajatlari"), h2.get("kirim_xarajatlari")), 850)
      and teng(ayir(h1.get("kirim_xarajatlari_jamida"), h2.get("kirim_xarajatlari_jamida")), 850),
      [h2.get("kirim_xarajatlari"), h2.get("kirim_xarajatlari_jamida")])
check("A2c ... sof foyda −850 va jami_xarajat +850 (o'zgarmagan qoida — qo'shimcha xarajat)",
      teng(ayir(h1.get("sof_foyda"), h2.get("sof_foyda")), -850) and teng(ayir(h1.get("jami_xarajat"), h2.get("jami_xarajat")), 850),
      [ayir(h1.get("sof_foyda"), h2.get("sof_foyda")), ayir(h1.get("jami_xarajat"), h2.get("jami_xarajat"))])
b2 = bosh_chiqim(h2)
check("A2d ... bosh sahifa Chiqim +10 850 — BIR marta (jami va naqd ikkalasida bo'lsa ham)", teng(ayir(b1, b2), 10850), [b1, b2])

r = kirim([q(MA["A3"])], (500, 200, 100, 50), True)
h3 = hisobot()
check("A3 tannarxga QO'SHILGAN 850: naqd +10 850 (ilgari 10 000)",
      r.status_code == 200 and teng(ayir(h2.get("naqd_xarajat_jami"), h3.get("naqd_xarajat_jami")), 10850),
      [r.status_code, ayir(h2.get("naqd_xarajat_jami"), h3.get("naqd_xarajat_jami"))])
check("A3b ... kirim_xarajatlari +850, kirim_xarajatlari_jamida O'ZGARMAYDI (jami_xarajat da yo'q)",
      teng(ayir(h2.get("kirim_xarajatlari"), h3.get("kirim_xarajatlari")), 850)
      and teng(ayir(h2.get("kirim_xarajatlari_jamida"), h3.get("kirim_xarajatlari_jamida")), 0),
      [h3.get("kirim_xarajatlari"), h3.get("kirim_xarajatlari_jamida")])
check("A3c ... sof foyda va jami_xarajat O'ZGARMAYDI (xomashyo tannarxida — 104-band)",
      teng(h2.get("sof_foyda"), h3.get("sof_foyda")) and teng(h2.get("jami_xarajat"), h3.get("jami_xarajat")),
      [h2.get("sof_foyda"), h3.get("sof_foyda")])
b3 = bosh_chiqim(h3)
check("A3d ... bosh sahifa Chiqim +10 850 (ilgari 850 HECH QAYERDA yo'q edi)", teng(ayir(b2, b3), 10850), [b2, b3])

r = kirim([q(MA["A4"], is_opening_stock=True)], (500, 200, 100, 50), False)
h4 = hisobot()
check("A4 HAMMA qatori boshlang'ich ombor — qo'shimcha Moliyaga yozilmaydi: naqd, kirim_xarajatlari O'ZGARMAYDI",
      r.status_code == 200 and teng(h3.get("naqd_xarajat_jami"), h4.get("naqd_xarajat_jami"))
      and teng(h3.get("kirim_xarajatlari"), h4.get("kirim_xarajatlari")),
      [r.status_code, h3.get("naqd_xarajat_jami"), h4.get("naqd_xarajat_jami")])

r = kirim([q(MA["A5a"], is_opening_stock=True), q(MA["A5b"])], (500, 200, 100, 50), False)
h5 = hisobot()
check("A5 aralash hujjat (boshlang'ich + yangi): naqd +10 850 (yangi qator + qo'shimcha)",
      r.status_code == 200 and teng(ayir(h4.get("naqd_xarajat_jami"), h5.get("naqd_xarajat_jami")), 10850),
      [r.status_code, ayir(h4.get("naqd_xarajat_jami"), h5.get("naqd_xarajat_jami"))])

r = req(C, "post", "/api/finance/transactions", json={"category": "transport_kirim", "amount": 300, "notes": "NK88 qo'lda"})
h6 = hisobot()
check("A6 qo'lda xarajat (kategoriya transport_kirim, manba manual) — kirim hujjati EMAS: naqd va kirim_xarajatlari O'ZGARMAYDI",
      r.status_code == 200 and teng(h5.get("naqd_xarajat_jami"), h6.get("naqd_xarajat_jami"))
      and teng(h5.get("kirim_xarajatlari"), h6.get("kirim_xarajatlari")),
      [r.status_code, h5.get("naqd_xarajat_jami"), h6.get("naqd_xarajat_jami")])
check("A6b ... jami_xarajat +300, bosh sahifa Chiqim +300",
      teng(ayir(h5.get("jami_xarajat"), h6.get("jami_xarajat")), 300) and teng(ayir(bosh_chiqim(h5), bosh_chiqim(h6)), 300),
      [ayir(h5.get("jami_xarajat"), h6.get("jami_xarajat")), bosh_chiqim(h5), bosh_chiqim(h6)])

tranzaksiya(120, kat="transport_kirim", manba=None, izoh="NK88 manbasiz")
h7 = hisobot()
check("A7 manbasiz (NULL) eski yozuv — kirim hujjati EMAS: kirim_xarajatlari O'ZGARMAYDI, jami +120",
      teng(h6.get("kirim_xarajatlari"), h7.get("kirim_xarajatlari")) and teng(ayir(h6.get("jami_xarajat"), h7.get("jami_xarajat")), 120),
      [h7.get("kirim_xarajatlari"), ayir(h6.get("jami_xarajat"), h7.get("jami_xarajat"))])

r = kirim([q(MA["A7"])], (333.33, 0.33, 0, 0), False)
h8 = hisobot()
check("A8 kasrli qo'shimcha 333.66: kirim_xarajatlari butun so'mga (+334), jamida aniq (+333.66), naqd +10 334",
      r.status_code == 200 and teng(ayir(h7.get("kirim_xarajatlari"), h8.get("kirim_xarajatlari")), 334)
      and teng(ayir(h7.get("kirim_xarajatlari_jamida"), h8.get("kirim_xarajatlari_jamida")), 333.66)
      and teng(ayir(h7.get("naqd_xarajat_jami"), h8.get("naqd_xarajat_jami")), 10334),
      [r.status_code, h8.get("kirim_xarajatlari"), h8.get("kirim_xarajatlari_jamida"), h8.get("naqd_xarajat_jami")])
check("A8b ... kalit turlari: kirim_xarajatlari butun, kirim_xarajatlari_jamida son",
      isinstance(h8.get("kirim_xarajatlari"), int) and isinstance(h8.get("kirim_xarajatlari_jamida"), (int, float)),
      [type(h8.get("kirim_xarajatlari")).__name__, type(h8.get("kirim_xarajatlari_jamida")).__name__])

_OY1 = oy_oldin(1)
_ho0 = hisobot(*_OY1)
tranzaksiya(700, kat="tushirish_kirim", sana=datetime(_OY1[0], _OY1[1], 15, 12, 0, 0),
            manba=getattr(models, "KIRIM_XARAJAT_MANBA", "inventory_receipt"), izoh="NK88 o'tgan oy kirimi")
h9, _ho1 = hisobot(), hisobot(*_OY1)
check("A9 o'tgan oy sanali kirim xarajati — SHU oy naqdiga kirmaydi, o'tgan oyda +700",
      teng(h8.get("naqd_xarajat_jami"), h9.get("naqd_xarajat_jami"))
      and teng(ayir(_ho0.get("naqd_xarajat_jami"), _ho1.get("naqd_xarajat_jami")), 700)
      and teng(ayir(_ho0.get("kirim_xarajatlari"), _ho1.get("kirim_xarajatlari")), 700),
      [h9.get("naqd_xarajat_jami"), _ho0.get("naqd_xarajat_jami"), _ho1.get("naqd_xarajat_jami")])
_t9 = tarix()
check("A10 tarix (/api/finance/history) shu oy — hisobot bilan AYNAN (naqd, kirim_xarajatlari, sof)",
      teng(_t9.get("naqd_xarajat_jami"), h9.get("naqd_xarajat_jami")) and teng(_t9.get("kirim_xarajatlari"), h9.get("kirim_xarajatlari"))
      and teng(_t9.get("sof_foyda"), h9.get("sof_foyda")),
      [_t9.get("naqd_xarajat_jami"), h9.get("naqd_xarajat_jami"), _t9.get("kirim_xarajatlari")])
_bs = bosh_sahifa(h9)
_kut = (h9.get("jami_xarajat") or 0) + (h9.get("naqd_xarajat_jami") or 0) - (h9.get("transport_xarajat") or 0) \
    - (h9.get("kirim_xarajatlari_jamida") or 0)
check("A11 bosh sahifa: Chiqim = jami + naqd − transport − kirim_xarajatlari_jamida; Balans = Kirim − Chiqim",
      _bs is not None and teng(_bs[1], round(_kut, 2), 0.011) and teng(_bs[2], round(_bs[0] - _bs[1], 2), 0.011),
      [_bs, _kut])

# ═══════════════════════════════════════════════════════════════════════════
section("B — bosh sahifa \"Chiqim\": transport ikki marta sanalmaydi (104-band bilan birga)")
hb0 = hisobot()
r = req(C, "post", "/api/transport-expenses", json={"amount": 700, "materials_note": "NK88", "notes": "NK88 B1"})
hb1 = hisobot()
check("B1 alohida kirish transporti 700: bosh sahifa Chiqim +700 (1 400 EMAS)",
      r.status_code == 200 and teng(ayir(bosh_chiqim(hb0), bosh_chiqim(hb1)), 700), [r.status_code, bosh_chiqim(hb0), bosh_chiqim(hb1)])

# ═══════════════════════════════════════════════════════════════════════════
section("C — kassa balansi: korxona to'lagan yetkazish transporti (107) va eski oylik forma (108)")
PENO = material("NK88 peno", peno=True, qoldiq=50)
_ro = req(C, "post", "/api/orders?confirm_shortage=true", json={
    "project_id": PRJ, "order_type": "product",
    "items": [{"name": "NK88 profil", "category": "profil", "width": 50, "thickness": 50, "length": 20,
               "quantity": 1, "unit_price": 50_000, "is_coated": False, "penoplast_id": PENO}]})
OID = (js(_ro) or {}).get("id") if isinstance(js(_ro), dict) else None
_oi = js(req(C, "get", f"/api/orders/{OID}")) or {}
IID = ((_oi.get("items") or [{}])[0]).get("id") if isinstance(_oi, dict) else None
check("C0 buyurtma (jarayonda) yaratildi", _ro.status_code == 200 and OID and IID, [_ro.status_code, OID, IID])


def yuk(payer, summa):
    _n[0] += 1
    r = req(C, "post", "/api/deliveries", json={"order_id": OID, "items": [{"order_item_id": IID, "quantity": 0.2}],
                                                "notes": f"NK88 yuk {_n[0]}", "transport_cost": summa,
                                                "transport_payer": payer})
    d = js(r) or {}
    return r.status_code, (d.get("delivery_id") if isinstance(d, dict) else None)


k0 = kassa()
st, D1 = yuk("company", 300)
k1 = kassa()
check("C1 yuk, transport \"company\" 300: kassa −300, chiqim_yetkazish_transport +300 (ilgari 0)",
      st == 200 and teng(ayir(k0.get("balance"), k1.get("balance")), -300)
      and teng(ayir(k0.get("chiqim_yetkazish_transport"), k1.get("chiqim_yetkazish_transport")), 300),
      [st, ayir(k0.get("balance"), k1.get("balance")), k1.get("chiqim_yetkazish_transport")])
st, D2 = yuk("split", 601)
k2 = kassa()
check("C2 \"split\" 601: kassa −300 (korxona qismi — model qoidasi round(601 / 2))",
      st == 200 and teng(ayir(k1.get("balance"), k2.get("balance")), -300), [st, ayir(k1.get("balance"), k2.get("balance"))])
st, D3 = yuk("client", 400)
k3 = kassa()
check("C3 \"client\" 400: kassa O'ZGARMAYDI", st == 200 and teng(k2.get("balance"), k3.get("balance")),
      [st, k2.get("balance"), k3.get("balance")])
st, D4 = yuk("none", 250)
k4 = kassa()
check("C4 \"none\" 250: kassa O'ZGARMAYDI", st == 200 and teng(k3.get("balance"), k4.get("balance")),
      [st, k3.get("balance"), k4.get("balance")])
_hr = hisobot()
check("C5 kassadagi yetkazish transporti = oylik hisobot transport_xarajat_yetkazish (bir qoida, 600)",
      teng(k4.get("chiqim_yetkazish_transport"), 600) and teng(_hr.get("transport_xarajat_yetkazish"), 600),
      [k4.get("chiqim_yetkazish_transport"), _hr.get("transport_xarajat_yetkazish")])
r = req(C, "delete", f"/api/deliveries/{D1}")
k5 = kassa()
check("C6 \"company\" 300 li yuk xati o'chirildi: kassa +300 (pul qaytdi)",
      r.status_code == 200 and teng(ayir(k4.get("balance"), k5.get("balance")), 300),
      [r.status_code, ayir(k4.get("balance"), k5.get("balance"))])

r = kirim([q(MA["C6"])], (500, 200, 100, 50), True)
k6 = kassa()
check("C7 ta'minotchisiz kirim + 850 (tannarxga): kassa −10 850 (o'zgarmagan qoida — regressiya nazorati)",
      r.status_code == 200 and teng(ayir(k5.get("balance"), k6.get("balance")), -10850),
      [r.status_code, ayir(k5.get("balance"), k6.get("balance"))])

_OY2, _OY3, _OY4 = oy_oldin(2), oy_oldin(3), oy_oldin(4)
_s = SessionLocal()
try:
    services.save_monthly_expense(_s, _OY1[0], _OY1[1], {"arenda": 1000}, performed_by="NK88", company_id=1)
finally:
    _s.close()
k7 = kassa()
check("C8 ESKI oylik forma: o'tgan oy arenda 1 000 (MonthlyExpense + monthly_form) — kassa −1 000 (ilgari −2 000)",
      teng(ayir(k6.get("balance"), k7.get("balance")), -1000), [ayir(k6.get("balance"), k7.get("balance")),
                                                                 k7.get("chiqim_oylik"), k7.get("chiqim_qoshimcha")])
_s = SessionLocal()
_s.add(MonthlyExpense(company_id=1, year=_OY2[0], month=_OY2[1], elektr=700))
_s.commit()
_s.close()
k8 = kassa()
check("C9 tranzaksiyasiz ESKI MonthlyExpense (elektr 700) — kassa −700 (bir marta)",
      teng(ayir(k7.get("balance"), k8.get("balance")), -700), ayir(k7.get("balance"), k8.get("balance")))
_s = SessionLocal()
_s.add(MonthlyExpense(company_id=1, year=_OY3[0], month=_OY3[1], tushlik=500))
_s.commit()
_s.close()
k9a = kassa()
tranzaksiya(200, kat="tushlik", sana=datetime(_OY3[0], _OY3[1], 10, 12, 0, 0), izoh="NK88 qo'lda tushlik")
k9 = kassa()
_s = SessionLocal()
try:
    _h3 = services.get_monthly_report(_s, _OY3[0], _OY3[1], company_id=1)
finally:
    _s.close()
check("C10 o'sha oyda qo'lda tushlik 200 yozilgach — oylik hisobot 200, kassa ham faqat 200 (−500 → −200, Δ +300)",
      teng(ayir(k8.get("balance"), k9a.get("balance")), -500) and teng(ayir(k9a.get("balance"), k9.get("balance")), 300)
      and teng((_h3.get("xarajatlar") or {}).get("tushlik"), 200),
      [ayir(k8.get("balance"), k9a.get("balance")), ayir(k9a.get("balance"), k9.get("balance")),
       (_h3.get("xarajatlar") or {}).get("tushlik")])
_kk = kassa()
_chiqim_kalit = ("chiqim_xomashyo_naqd", "chiqim_yetkazib_beruvchi", "chiqim_oylik", "chiqim_qoshimcha",
                 "chiqim_transport", "chiqim_avans", "chiqim_yetkazish_transport")
try:
    _hisob = (_kk["kirim_tolov"] + _kk["kirim_tayyor_sotuv"] - sum(_kk[k] for k in _chiqim_kalit) + _kk["qolda_jami"])
except Exception:                          # noqa: BLE001
    _hisob = None
check("C11 kassa balansi = kirim − HAMMA chiqim qismlari + qo'lda (yaxlitlash ±4)",
      _hisob is not None and abs(_hisob - _kk.get("balance", 0)) <= 4, [_hisob, _kk.get("balance")])

# ═══════════════════════════════════════════════════════════════════════════
section("K — boshqa korxona ma'lumoti bu korxona naqdi / kassasiga TEGMAYDI")
hk0, kk0 = hisobot(), kassa()
_s = SessionLocal()
try:
    _pB = Project(company_id=2, client_name="NK88 B mijoz", project_name="NK88 B loyiha", total_budget=0, total_paid=0)
    _s.add(_pB)
    _s.commit()
    _oB = Order(company_id=2, project_id=_pB.id, order_type=OrderType.PRODUCT, order_number="NK88-B-1")
    _s.add(_oB)
    _s.commit()
    _s.add(Delivery(order_id=_oB.id, delivered_at=datetime.utcnow(), transport_cost=9000, transport_payer="company",
                    notes="NK88 B yuk"))
    _s.commit()
    _kB = services.get_cash_balance(_s, company_id=2)
finally:
    _s.close()
tranzaksiya(4000, kat="transport_kirim", manba=getattr(models, "KIRIM_XARAJAT_MANBA", "inventory_receipt"), cid=2,
            izoh="NK88 B kirim")
tranzaksiya(6000, kat="arenda", sana=datetime(_OY4[0], _OY4[1], 5, 12, 0, 0), cid=2, izoh="NK88 B arenda")
hk1, kk1 = hisobot(), kassa()
check("K1 B korxonaning yuk transporti (company 9 000) — A kassasi O'ZGARMAYDI",
      teng(kk0.get("balance"), kk1.get("balance")) and teng(kk0.get("chiqim_yetkazish_transport"), kk1.get("chiqim_yetkazish_transport")),
      [kk0.get("balance"), kk1.get("balance")])
check("K2 ... B korxona kassasida chiqim_yetkazish_transport 9 000", teng(_kB.get("chiqim_yetkazish_transport"), 9000),
      _kB.get("chiqim_yetkazish_transport"))
check("K3 B korxonaning kirim xarajati (4 000) — A naqdi va kirim_xarajatlari O'ZGARMAYDI",
      teng(hk0.get("naqd_xarajat_jami"), hk1.get("naqd_xarajat_jami")) and teng(hk0.get("kirim_xarajatlari"), hk1.get("kirim_xarajatlari")),
      [hk0.get("naqd_xarajat_jami"), hk1.get("naqd_xarajat_jami")])
_s = SessionLocal()
_s.add(MonthlyExpense(company_id=1, year=_OY4[0], month=_OY4[1], arenda=900))
_s.commit()
_s.close()
kk2 = kassa()
check("K4 A ning ESKI MonthlyExpense (arenda 900) — o'sha oyda B ning arenda tranzaksiyasi bo'lsa ham A kassasi −900",
      teng(ayir(kk1.get("balance"), kk2.get("balance")), -900), ayir(kk1.get("balance"), kk2.get("balance")))

# ═══════════════════════════════════════════════════════════════════════════
section("U — Moliya sahifasi: \"Kirim hujjati xarajatlari\" qatori (sahifaning O'Z funksiyasi)")
try:
    with open(os.path.join(ROOT, "templates", "finance.html"), encoding="utf-8") as _f:
        _fin = _f.read()
except Exception:                          # noqa: BLE001
    _fin = ""
_hu = hisobot()
_o = js_yurgiz(shablon_funksiya("finance.html", "function buildCashSection("), _hu)
_tk = ((_o.get("cash-kirim") or {}).get("t")) if isinstance(_o, dict) else None
_tt = ((_o.get("cash-total") or {}).get("t")) if isinstance(_o, dict) else None
check("U1 buildCashSection: \"cash-kirim\" = kirim_xarajatlari", _tk is not None and _tk.startswith(str(_hu.get("kirim_xarajatlari")) + " "),
      [_tk, _hu.get("kirim_xarajatlari"), (_o or {}).get("xato") if isinstance(_o, dict) else _o])
check("U2 ... \"cash-total\" = naqd_xarajat_jami (kirim xarajatlari bilan)",
      _tt is not None and _tt.startswith(str(_hu.get("naqd_xarajat_jami")) + " "), [_tt, _hu.get("naqd_xarajat_jami")])
check("U3 sahifada \"cash-kirim\" qatori (nomi bilan) BOR", 'id="cash-kirim"' in _fin and "Kirim hujjati xarajatlari" in _fin)
check("U4 izoh: \"Sof foydaga kirmaydi\" ESKI umumiy da'vosi yo'q (transport endi sof foydada)",
      "Bu ko'rsatkich <b>Sof foyda</b>ga kirmaydi" not in _fin and "chiqib ketgan</b> pul" in _fin)

# ═══════════════════════════════════════════════════════════════════════════
section("H — kod (statik)")
try:
    _srcr = inspect.getsource(services.get_monthly_report)
except Exception:                          # noqa: BLE001
    _srcr = ""
try:
    _srck = inspect.getsource(services.get_cash_balance)
except Exception:                          # noqa: BLE001
    _srck = ""
try:
    with open(os.path.join(ROOT, "templates", "dashboard.html"), encoding="utf-8") as _f:
        _dash = _f.read()
except Exception:                          # noqa: BLE001
    _dash = ""
check("H1 models.KIRIM_XARAJAT_MANBA == \"inventory_receipt\" (crud.create_inventory_receipt yozadigan qiymat)",
      getattr(models, "KIRIM_XARAJAT_MANBA", None) == "inventory_receipt")
check("H2 hisobot: naqd = xarid + transport kirish + transport chiqish + kirim_xarajatlari (ikkala manba)",
      tartibda(_srcr, "ExpenseTransaction.source.in_([_KXM_nq, _KTM_nq])", "kirim_xarajatlari = round(sum(_kx.values()))",
               "kirim_xarajatlari_jamida = float(_kx.get(_KXM_nq, 0.0))",
               "naqd_xarajat_jami = xomashyo_xaridi + transport_kirish + transport_chiqish + kirim_xarajatlari"))
check("H3 kassa: yetkazish transporti korxona filtri bilan va jami chiqimda",
      tartibda(_srck, "_dvq = db.query(_Dlv_cash).filter(_Dlv_cash.transport_cost > 0)", "_Ord_cash.company_id == company_id",
               "chiqim_yetkazish_transport = ", "jami_chiqim = ", "chiqim_yetkazish_transport)"))
check("H4 kassa: eski MonthlyExpense faqat tranzaksiyasi yo'q oy / kategoriya uchun (korxona filtri bilan)",
      tartibda(_srck, "_mtq = db.query(", "_mtq = _mtq.filter(ExpenseTransaction.company_id == company_id)",
               "_tranzaksiyali = ", "if (int(m.year), int(m.month), cat) not in _tranzaksiyali"))
check("H5 bosh sahifa: chiqimJami = chiqim − kirim_xarajatlari_jamida, balans va ko'rinish shundan",
      tartibda(_dash, "const chiqim = (d.jami_xarajat||0)+(d.naqd_xarajat_jami||0)-(d.transport_xarajat||0);",
               "const chiqimJami = chiqim-(d.kirim_xarajatlari_jamida||0);", "const balans = kirim-chiqimJami;",
               "${fmt(chiqimJami)}"))
check("H6 node mavjud (B / U bo'limlari sahifa funksiyasini yurgizadi)", bool(_NODE) and bool(_CASHFLOW))

print(f"\nNATIJA: o'tdi = {OK} yiqildi = {FAIL} jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for _x in FAILED:
        print("  -", _x)
sys.exit(1 if FAIL else 0)
