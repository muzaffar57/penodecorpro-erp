#!/usr/bin/env python3
"""
test_kirim_xarajat226.py — kech162 (zip 226 «Kirim xarajati ko'rinsin»; egasi 30.10 16:32, tanlov «Kirim xarajati ko'rinsin (Tavsiya)»).

NIMA UCHUN KERAK
  Egasi kirim hujjatidagi transport 600 000 ni topolmadi: Moliya «Xarajatlar ro'yxati» qatorida faqat «Transport (kirim) — Kirim #80» (qaysi
  material uchunligi yo'q), Omborxona «Xaridlar tarixi» → «📦 Kirim #80» oynasida transport summasi umuman yo'q (O'LCHANGAN —
  `work/k226/probe226.py`, asl = staging e8247f8: ro'yxatda material nomi yo'q, `GET /api/inventory/receipts/{id}` — 404, oyna xarajatni
  so'ramaydi).
QOIDA: Moliya ro'yxati kirim xarajatida `kirim_id` + `kirim_materiallar` (shu korxona hujjati; bir xil nom + birlik — jamlanadi; qo'lda
  kiritilgan «transport_kirim» — yo'q); sahifada izoh ostida «📦 Nom (miqdor birlik)», 3 tadan ko'pi — «… yana N ta». `GET
  /api/inventory/receipts/{id}` («Xomashyo kirimi: Ko'rish»): Moliyadagi xarajatlar (yo'q bo'lsa — hujjat maydonlari, `moliyada: false`),
  `tannarxda`, ta'minotchi, hujjat raqami, `boshlangich`; summa — «Xomashyo narxlari» ruxsatisiz null; faqat o'qish. Oynada «Qo'shimcha
  xarajatlar» bloki va «Hujjat jami (materiallar + xarajatlar)».
BO'LIMLAR
  A — Moliya ro'yxati (API): materiallar, jamlash, tartib, qo'lda kiritilgan tur, hujjat raqamidagi «Kirim #N», begona korxona, katta raqam,
      bekor qilingan hujjat, oddiy xarajat.
  B — `GET /api/inventory/receipts/{id}`: tannarxda / Moliyada / boshlang'ich ombor (tannarxli va tannarxsiz) / xarajatsiz, tartib, 404 / 422,
      begona korxona, faqat o'qish (baza o'zgarmaydi), Menejer — summa null, Moliyachi — 403.
  C — haqiqiy Chromium: Moliya qatori (matn, «… yana N ta», escape, telefon 390 px), «📦 Kirim #N» oynasi (xarajat, holat, hujjat jami,
      ta'minotchi, xarajatsiz, boshlang'ich ombor, Menejer «—», 502 / tarmoq — sabab, oyna tez almashtirilsa eski javob chizilmaydi,
      390 / 320 px toshish yo'q, tungi rejim).
  D — ESKI nuqson (O'LCHANGAN `work/k226/probe226b.py`): hujjat raqami «Kirim #1 nusxa» bo'lgan hujjat xarajati Kirim #1 bekor qilinganda
      o'chardi — endi izohdagi BIRINCHI «Kirim #N» (reja, bekor qilish, oyna).
  S — manba (`yukBlok`, `typeof` himoyasi, NARX_YOLLAR).
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL` — HAQIQIY PostgreSQL (A / B; C ham).
Asl kodga (zip 225) qarshi QULAMAYDI — yiqiladi (har bo'lim `bolim` bilan himoyalangan).
ISHLATISH: python3 tools/test_kirim_xarajat226.py
"""
import os
import io
import re
import sys
import json
import time
import socket
import tempfile
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "kirim_xarajat226_test"
_T = tempfile.mkdtemp(prefix="k226_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k226.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
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


@contextlib.contextmanager
def bolim(nom):
    """Bo'lim xatosi (asl kodda yo'q marshrut / element) — sinov qulamasin: bo'lim «yiqildi» deb yoziladi, keyingisi davom etadi."""
    try:
        yield
    except Exception as e:                 # noqa: BLE001
        check(f"{nom} — bo'lim oxirigacha bajarildi", False, f"{type(e).__name__}: {e}")


with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal, tashkent_date   # noqa: E402
from models import (UserRole, ExpenseTransaction, InventoryReceipt, InventoryPurchase, Inventory,  # noqa: E402
                    SupplierPayment, InventoryMovement)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from datetime import datetime as _dt226             # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    with TestClient(main.app):
        pass
crud.PUL_TAKROR_SONIYA = 0
PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    if s.get(Company, 2) is None:
        s.add(Company(id=2, name="K226 Korxona B"))
        s.commit()
    auth.create_user(s, "k226_ad", PAROL, UserRole.ADMIN, "K226 Admin", company_id=1)
    auth.create_user(s, "k226_men", PAROL, UserRole.MANAGER, "K226 Menejer", company_id=1)
    auth.create_user(s, "k226_mol", PAROL, UserRole.ACCOUNTANT, "K226 Moliyachi", company_id=1)
    auth.create_user(s, "k226_b", PAROL, UserRole.ADMIN, "K226 B admin", company_id=2)
    # o'zi yaratilgan rol: Xomashyo kirimi — ko'rish + o'chirish, «Xomashyo narxlari» YO'Q (review226 P1)
    auth.create_user(s, "k226_kn", PAROL, UserRole.MANAGER, "K226 Kirim narxsiz", company_id=1)
from models import Rol, User                        # noqa: E402
_rol = Rol(company_id=1, nom="K226 Kirim narxsiz", kod=None, ruxsatlar=json.dumps({"kirim": ["korish", "ochirish"], "material": ["korish"]}),
           tavsif="")
s.add(_rol)
s.flush()
s.query(User).filter(User.username == "k226_kn").first().rol_id = _rol.id
s.commit()
s.close()


def klient(u):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    c.post("/login", data={"username": u, "password": PAROL}, follow_redirects=False)
    return c


C, CM, CF, CB = klient("k226_ad"), klient("k226_men"), klient("k226_mol"), klient("k226_b")
CKN = klient("k226_kn")
BUGUN = tashkent_date()
YIL, OY = BUGUN.year, BUGUN.month


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def taminotchi(c, nom):
    r = c.post("/api/suppliers", json={"name": nom, "phone": "+998901112233"})
    return (js(r) or {}).get("id") if r.status_code == 200 else None


def material(c, nom, unit="dona"):
    r = c.post("/api/inventory", json={"item_name": nom, "unit": unit, "category": "Kimyoviy qo'shimchalar",
                                       "stock_quantity": 0, "price_per_unit": 0, "min_stock": 0})
    return (js(r) or {}).get("id") if r.status_code == 200 else None


def kirim(c, sup, qatorlar, add_to_cost=False, transport=0.0, tushirish=0.0, yuklash=0.0, boshqa=0.0, hujjat="", paid_now=0.0):
    """qatorlar: [(material, miqdor, narx, boshlangich?)]"""
    r = c.post("/api/inventory/receipt", json={
        "items": [{"inventory_id": q[0], "quantity": q[1], "price_per_unit": q[2], "is_opening_stock": bool(q[3]) if len(q) > 3 else False}
                  for q in qatorlar],
        "transport_cost": transport, "tushirish_cost": tushirish, "yuklash_cost": yuklash, "boshqa_cost": boshqa,
        "add_to_cost": add_to_cost, "supplier_id": sup, "document_number": hujjat, "paid_now": paid_now, "notes": ""})
    return r.status_code, (js(r) or {}).get("receipt_id")


def royxat(c):
    r = c.get("/api/finance/transactions", params={"year": YIL, "month": OY})
    return r.status_code, (js(r) if isinstance(js(r), list) else [])


def hujjat_qatorlari(rows, rid):
    return [t for t in rows if re.search(rf"Kirim #{rid}(?!\d)", t.get("notes") or "")]


def baza_holati():
    s = SessionLocal()
    try:
        return {"tx": sorted((t.id, t.category, float(t.amount), t.source, t.notes) for t in s.query(ExpenseTransaction).all()),
                "rc": sorted((r.id, float(r.transport_cost or 0), float(r.tushirish_cost or 0)) for r in s.query(InventoryReceipt).all()),
                "xarid": s.query(InventoryPurchase).count(), "harakat": s.query(InventoryMovement).count(),
                "tolov": s.query(SupplierPayment).count(),
                "mat": sorted((i.id, float(i.stock_quantity or 0), float(i.price_per_unit or 0)) for i in s.query(Inventory).all())}
    finally:
        s.close()


# ── Fikstura ───────────────────────────────────────────────────────────────────────────────────────────────────────
SUP = taminotchi(C, "K226 Ta'minotchi")
M10 = material(C, "K226 Penoplast 10P")
MK = [material(C, f"K226 M{i}", "kg") for i in range(4)]
MB = material(C, "K226 Boshlang'ich")
MB2 = material(C, "K226 Boshlang'ich 2")
MX = material(C, "K226 Xarajatsiz")
MESC = material(C, "K226 <b>qalin</b> & \"q\"")
st1, R1 = kirim(C, SUP, [(M10, 12, 624000)], add_to_cost=True, transport=600000)
# 4 material + bir materialning ikkinchi partiyasi (bir xil nom va birlik — jamlanadi); hujjat raqami ichida boshqa «Kirim #1»
st2, R2 = kirim(C, SUP, [(MK[0], 10, 100), (MK[1], 11, 100), (MK[0], 2.5, 120), (MK[2], 12, 100), (MK[3], 13, 100)],
                tushirish=50000, yuklash=20000, hujjat=f"Kirim #{R1} nusxa")
st3, R3 = kirim(C, None, [(MB, 5, 1000, True)], add_to_cost=True, transport=7000)
st4, R4 = kirim(C, None, [(MB2, 4, 500, True)], add_to_cost=False, tushirish=3000)
st5, R5 = kirim(C, SUP, [(MX, 3, 2000)])
st6, R6 = kirim(C, SUP, [(MESC, 1, 1000)], boshqa=1500, hujjat="<i>K226</i>")
st7, R7 = kirim(C, SUP, [(MK[0], 1, 100)], transport=999)       # bekor qilinadi
SUPB = taminotchi(CB, "K226 B ta'minotchi")
MBB = material(CB, "K226 B material")
st8, RB = kirim(CB, SUPB, [(MBB, 2, 3000)], transport=4444)
MLONG = material(C, "K226Uzun" + "X" * 92)
st9, RL = kirim(C, SUP, [(MLONG, 2, 1000)], transport=111)
check("0 fikstura: 9 kirim hujjati yaratildi", all(x == 200 for x in (st1, st2, st3, st4, st5, st6, st7, st8, st9))
      and all((R1, R2, R3, R4, R5, R6, R7, RB, RL)), (st1, st2, st3, st4, st5, st6, st7, st8, st9, R1, R2, R3, R4, R5, R6, R7, RB, RL))
_rc7 = C.post(f"/api/inventory/receipts/{R7}/cancel")
# qo'lda kiritilgan «transport_kirim» (izohida «Kirim #R1») — hujjatga TEGISHLI EMAS
_qolda = C.post("/api/finance/transactions", json={"date": BUGUN.isoformat() + "T00:00:00", "category": "transport_kirim", "amount": 321,
                                                    "notes": f"Qo'lda — Kirim #{R1}"})
_oddiy = C.post("/api/finance/transactions", json={"date": BUGUN.isoformat() + "T00:00:00", "category": "tushlik", "amount": 5000,
                                                    "notes": "K226 tushlik"})
# begona korxona hujjatiga ishora qiluvchi (soxta) yozuv va juda katta raqam — bazaga to'g'ridan-to'g'ri
s = SessionLocal()
s.add(ExpenseTransaction(company_id=1, date=_dt226.utcnow(), category="transport_kirim",
                         amount=77, notes=f"Transport (kirim) — Kirim #{RB}", source="inventory_receipt", created_by="K226"))
s.add(ExpenseTransaction(company_id=1, date=_dt226.utcnow(), category="transport_kirim",
                         amount=78, notes="Transport (kirim) — Kirim #99999999999", source="inventory_receipt", created_by="K226"))
# eski, qo'lda o'zgartirilgan izoh — boshida BOSHQA hujjat raqami, yorliqda (« — Kirim #N») — o'zi (review226 №2)
s.add(ExpenseTransaction(company_id=1, date=_dt226.utcnow(), category="transport_kirim",
                         amount=222, notes=f"Kirim #{R5} uchun; Transport (kirim) — Kirim #{RL}", source="inventory_receipt", created_by="K226"))
s.commit()
s.close()
check("0b fikstura: R7 bekor qilindi, qo'lda va oddiy xarajat yozildi", _rc7.status_code == 200 and _qolda.status_code == 200
      and _oddiy.status_code == 200, (_rc7.status_code, _qolda.text[:200], _oddiy.text[:200]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A — Moliya «Xarajatlar ro'yxati» (GET /api/finance/transactions)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
with bolim("A"):
    _st, ROWS = royxat(C)
    _a1 = hujjat_qatorlari(ROWS, R1)
    _a1 = [t for t in _a1 if t.get("source") == "kirim_tannarx"]
    check("A1 10P hujjati: transport qatori — `kirim_id` = hujjat, `kirim_materiallar` = [Penoplast 10P, 12 dona]",
          _st == 200 and len(_a1) == 1 and _a1[0].get("kirim_id") == R1
          and _a1[0].get("kirim_materiallar") == [{"nomi": "K226 Penoplast 10P", "miqdor": 12.0, "birlik": "dona"}], (_st, _a1))
    _a2 = hujjat_qatorlari(ROWS, R2)
    _kut2 = [{"nomi": "K226 M0", "miqdor": 12.5, "birlik": "kg"}, {"nomi": "K226 M1", "miqdor": 11.0, "birlik": "kg"},
             {"nomi": "K226 M2", "miqdor": 12.0, "birlik": "kg"}, {"nomi": "K226 M3", "miqdor": 13.0, "birlik": "kg"}]
    check("A2 4 materialli hujjat (tushirish + yuklash): ikkala qatorda — xarid tartibida, M0 ikki partiyasi jamlangan (10 + 2,5 = 12,5)",
          len(_a2) == 2 and all(t.get("kirim_id") == R2 and t.get("kirim_materiallar") == _kut2 for t in _a2),
          [(t.get("category"), t.get("kirim_id"), t.get("kirim_materiallar")) for t in _a2])
    check("A3 hujjat raqamida boshqa «Kirim #R1» — birinchi «Kirim #N» (hujjat o'zi) olinadi",
          all(t.get("kirim_id") == R2 for t in _a2) and f"Kirim #{R1} nusxa" in (_a2[0].get("notes") or "") if _a2 else False,
          [t.get("notes") for t in _a2])
    _q = [t for t in ROWS if (t.get("notes") or "") == f"Qo'lda — Kirim #{R1}"]
    check("A4 qo'lda kiritilgan «transport_kirim» (izohda «Kirim #R1») — hujjatga bog'lanmaydi (kirim_id / materiallar yo'q)",
          len(_q) == 1 and _q[0].get("kirim_id") is None and _q[0].get("kirim_materiallar") is None and "kirim_id" in _q[0], _q)
    _b = [t for t in ROWS if (t.get("notes") or "") == f"Transport (kirim) — Kirim #{RB}"]
    _k = [t for t in ROWS if (t.get("notes") or "") == "Transport (kirim) — Kirim #99999999999"]
    check("A5 begona korxona hujjati raqami — bog'lanmaydi (B materiali ko'rinmaydi); juda katta raqam — xatosiz, bog'lanmaydi",
          len(_b) == 1 and _b[0].get("kirim_id") is None and _b[0].get("kirim_materiallar") is None and "K226 B material" not in json.dumps(ROWS, ensure_ascii=False)
          and len(_k) == 1 and _k[0].get("kirim_id") is None, (_b, _k))
    _o = [t for t in ROWS if (t.get("notes") or "") == "K226 tushlik"]
    check("A6 oddiy xarajat — kalitlar bor, qiymati None", len(_o) == 1 and "kirim_materiallar" in _o[0] and _o[0].get("kirim_id") is None
          and _o[0].get("kirim_materiallar") is None, _o)
    check("A7 bekor qilingan hujjat (R7) — Moliyada qatori yo'q; boshlang'ich ombor (R3, R4) — Moliyada qatori yo'q",
          not hujjat_qatorlari(ROWS, R7) and not hujjat_qatorlari(ROWS, R3) and not hujjat_qatorlari(ROWS, R4))
    _sb, ROWS_B = royxat(CB)
    _bb = hujjat_qatorlari(ROWS_B, RB)
    check("A8 B korxona — o'z hujjati materiali bilan, A korxona materiallari yo'q",
          _sb == 200 and len(_bb) == 1 and _bb[0].get("kirim_materiallar") == [{"nomi": "K226 B material", "miqdor": 2.0, "birlik": "dona"}]
          and "K226 Penoplast" not in json.dumps(ROWS_B, ensure_ascii=False), (_sb, _bb))
    _sf, ROWS_F = royxat(CF)
    _f1 = [t for t in hujjat_qatorlari(ROWS_F, R1) if t.get("source") == "kirim_tannarx"]
    check("A9 Moliyachi (Moliya ro'yxatini ko'radi) — materiallar ham bor (narx yo'q — faqat nom, miqdor, birlik)",
          _sf == 200 and len(_f1) == 1 and _f1[0].get("kirim_materiallar") == _a1[0].get("kirim_materiallar")
          and set(_f1[0]["kirim_materiallar"][0]) == {"nomi", "miqdor", "birlik"}, (_sf, _f1))
    _ss = C.get("/api/finance/transactions", params={"year": YIL, "month": OY, "category": "transport_kirim"})
    _s1 = [t for t in (js(_ss) or []) if t.get("kirim_id") == R1]
    check("A10 turkum filtri bilan ham (transport_kirim) — materiallar bor", _ss.status_code == 200 and len(_s1) == 1, _ss.text[:300])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B — GET /api/inventory/receipts/{id} («📦 Kirim #N» oynasi)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════


def hujjat(c, rid):
    r = c.get(f"/api/inventory/receipts/{rid}")
    return r.status_code, js(r)


def xq(d):
    return [(x.get("turi"), x.get("summa"), x.get("tannarxda"), x.get("moliyada")) for x in (d or {}).get("xarajatlar") or []]


with bolim("B"):
    _h0 = baza_holati()
    st, d1 = hujjat(C, R1)
    check("B1 10P: transport 600 000 — tannarxda, Moliyada; jami 600 000; ta'minotchi; hujjat raqami yo'q; boshlang'ich emas",
          st == 200 and d1.get("id") == R1 and xq(d1) == [("transport_kirim", 600000.0, True, True)] and d1.get("xarajatlar_jami") == 600000
          and d1.get("taminotchi") == "K226 Ta'minotchi" and d1.get("hujjat_raqami") is None and d1.get("boshlangich") is False
          and d1.get("sana") and d1["xarajatlar"][0].get("sana"), (st, d1))
    st, d2 = hujjat(C, R2)
    check("B2 tannarxsiz: tushirish 50 000, yuklash 20 000 — Moliyada alohida (tannarxda emas), tartib tushirish → yuklash; hujjat raqami",
          st == 200 and xq(d2) == [("tushirish_kirim", 50000.0, False, True), ("yuklash_kirim", 20000.0, False, True)]
          and d2.get("xarajatlar_jami") == 70000 and d2.get("hujjat_raqami") == f"Kirim #{R1} nusxa", (st, d2))
    st, d3 = hujjat(C, R3)
    check("B3 boshlang'ich ombor + tannarxga: transport 7 000 — tannarxda, Moliyada YO'Q; boshlangich; ta'minotchisiz",
          st == 200 and xq(d3) == [("transport_kirim", 7000.0, True, False)] and d3.get("boshlangich") is True and d3.get("taminotchi") is None,
          (st, d3))
    st, d4 = hujjat(C, R4)
    check("B4 boshlang'ich ombor, tannarxsiz: tushirish 3 000 — tannarxda emas, Moliyada yo'q",
          st == 200 and xq(d4) == [("tushirish_kirim", 3000.0, False, False)] and d4.get("boshlangich") is True, (st, d4))
    st, d5 = hujjat(C, R5)
    check("B5 xarajatsiz hujjat — bo'sh ro'yxat, jami 0", st == 200 and d5.get("xarajatlar") == [] and d5.get("xarajatlar_jami") == 0, (st, d5))
    st, d6 = hujjat(C, R6)
    check("B6 boshqa xarajat (kirim) 1 500 — `kirim_boshqa`", st == 200 and xq(d6) == [("kirim_boshqa", 1500.0, False, True)], (st, d6))
    _r = [C.get(f"/api/inventory/receipts/{x}").status_code for x in (R7, 987654, RB)]
    check("B7 bekor qilingan / yo'q / begona korxona hujjati — 404", _r == [404, 404, 404], _r)
    _r = [C.get(f"/api/inventory/receipts/{x}").status_code for x in ("0", "-1", "2147483648", "99999999999", "abc")]
    check("B8 noto'g'ri raqam (0, −1, 2³¹, juda katta, matn) — 422 (500 emas)", _r == [422] * 5, _r)
    _r = C.get(f"/api/inventory/receipts/{2147483647}")
    check("B8b eng katta to'g'ri raqam — 404", _r.status_code == 404, _r.status_code)
    stb, db_ = hujjat(CB, RB)
    check("B9 B korxona — o'z hujjati (transport 4 444), A hujjati — 404",
          stb == 200 and xq(db_) == [("transport_kirim", 4444.0, False, True)] and CB.get(f"/api/inventory/receipts/{R1}").status_code == 404,
          (stb, db_))
    stm, dm = hujjat(CM, R1)
    check("B10 Menejer («Xomashyo narxlari» yo'q) — summa va jami null, tur / holat bor",
          stm == 200 and [(x.get("turi"), x.get("summa"), x.get("tannarxda")) for x in dm.get("xarajatlar") or []] == [("transport_kirim", None, True)]
          and dm.get("xarajatlar_jami") is None and "600000" not in json.dumps(dm), (stm, dm))
    _f = CF.get(f"/api/inventory/receipts/{R1}")
    check("B11 Moliyachi («Xomashyo kirimi: Ko'rish» yo'q) — 403", _f.status_code == 403, (_f.status_code, _f.text[:200]))
    _anon = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False).get(f"/api/inventory/receipts/{R1}")
    check("B12 kirmagan — 401", _anon.status_code == 401, _anon.status_code)
    check("B13 faqat o'qish — baza (xarajat, hujjat, xarid, harakat, to'lov, material) o'zgarmadi", baza_holati() == _h0)
    _pl = C.get(f"/api/inventory/receipts/{R1}/cancel-plan")
    check("B14 bekor qilish rejasi (eski marshrut) — ishlaydi", _pl.status_code == 200 and (js(_pl) or {}).get("xarajatlar_jami") == 600000,
          (_pl.status_code, _pl.text[:200]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D — ESKI nuqson: hujjat raqamida boshqa hujjatning «Kirim #N» i (bekor qilish boshqa hujjat xarajatini o'chirardi)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
with bolim("D"):
    MD = material(C, "K226 D material", "kg")
    _sd1, RD1 = kirim(C, None, [(MD, 10, 100)], transport=600000)
    _sd2, RD2 = kirim(C, None, [(MD, 5, 100)], tushirish=50000, hujjat=f"Kirim #{RD1} nusxa")
    _pl = js(C.get(f"/api/inventory/receipts/{RD1}/cancel-plan")) or {}
    check("D1 Kirim #D1 bekor rejasi — faqat o'z transporti 600 000 (asl: 650 000 — D2 tushirishi ham)",
          _sd1 == 200 and _sd2 == 200 and _pl.get("xarajatlar_jami") == 600000, (_sd1, _sd2, _pl.get("xarajatlar_jami")))
    _c = C.post(f"/api/inventory/receipts/{RD1}/cancel")
    s = SessionLocal()
    _qoldi = sorted((t.category, float(t.amount)) for t in s.query(ExpenseTransaction).all()
                    if re.search(rf"Kirim #({RD1}|{RD2})(?!\d)", t.notes or ""))
    s.close()
    check("D2 Kirim #D1 bekor qilindi — Kirim #D2 ning tushirish 50 000 xarajati Moliyada QOLDI (asl: o'chardi)",
          _c.status_code == 200 and _qoldi == [("tushirish_kirim", 50000.0)], (_c.status_code, _qoldi))
    _st, _d = hujjat(C, RD2)
    check("D3 Kirim #D2 oynasi — o'z tushirishi (Moliyada), Kirim #D1 — 404",
          _st == 200 and xq(_d) == [("tushirish_kirim", 50000.0, False, True)] and C.get(f"/api/inventory/receipts/{RD1}").status_code == 404,
          (_st, _d))
    _src = open(os.path.join(ROOT, "crud.py"), encoding="utf-8").read()
    _f = _src[_src.find("def _kirim_hujjati_qismlari("):_src.find("def _kirim_tolov_savoli(")]
    check("D4 manba: `_kirim_hujjati_qismlari` — birinchi «Kirim #N» (`_kirim_izoh_raqami`), `findall` yo'q",
          "_kirim_izoh_raqami(t.notes) == receipt.id" in _f and "findall" not in _f)
    _st, _dl = hujjat(C, RL)
    _st5, _d5 = hujjat(C, R5)
    _rl = [t for t in ROWS if (t.get("notes") or "").startswith(f"Kirim #{R5} uchun;")]
    check("D5 eski qo'lda o'zgartirilgan izoh («Kirim #R5 uchun; Transport (kirim) — Kirim #RL») — yorliqdagi RL ga (Moliya ro'yxati, oyna),"
          " R5 ga emas (review226 №2)",
          len(_rl) == 1 and _rl[0].get("kirim_id") == RL and _st == 200 and sorted(x[1] for x in xq(_dl)) == [111.0, 222.0]
          and _st5 == 200 and _d5.get("xarajatlar") == [], (_rl, _dl, _d5))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E — ESKI (review226 P1 / P2): bekor qilish rejasi narxi va katta raqam")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
with bolim("E"):
    _pa = js(C.get(f"/api/inventory/receipts/{R1}/cancel-plan")) or {}
    _rk = CKN.get(f"/api/inventory/receipts/{R1}/cancel-plan")
    _pk = js(_rk) or {}
    _m = (_pk.get("materiallar") or [{}])[0]
    check("E1 Admin — rejada narx bor; «Xomashyo narxlari» siz rol — xarid narxi, summa, material narxi, xarajatlar null, 624 000 / 600 000 yo'q",
          ((_pa.get("materiallar") or [{}])[0].get("xarid_narxi") == 624000 and _rk.status_code == 200
           and all(_m.get(k, "yo'q") is None for k in ("joriy_narx", "yangi_narx", "xarid_narxi", "summa"))
           and _m.get("miqdor") == 12 and all(x.get("summa") is None for x in _pk.get("xarajatlar") or [{}])
           and _pk.get("xarajatlar_jami") is None and "624000" not in _rk.text and "600000" not in _rk.text), (_pa, _rk.text[:500]))
    _ok = CKN.get(f"/api/inventory/receipts/{R1}")
    check("E1b o'sha rol — oyna marshruti 200, summa null", _ok.status_code == 200 and (js(_ok) or {}).get("xarajatlar_jami") is None, _ok.text[:300])
    _r = [C.get("/api/inventory/receipts/2147483648/cancel-plan").status_code, C.post("/api/inventory/receipts/2147483648/cancel").status_code,
          C.get("/api/inventory/receipts/0/cancel-plan").status_code, C.get("/api/inventory/receipts/987654/cancel-plan").status_code]
    check("E2 bekor qilish rejasi / bekor qilish: 2³¹ va 0 — 422 (PG da 500 edi), yo'q hujjat — 404", _r == [422, 422, 422, 404], _r)
    _se, RE = kirim(C, SUP, [(MX, 1, 100)], transport=5)
    _rk = js(CKN.post(f"/api/inventory/receipts/{RE}/cancel")) or {}
    check("E3 o'sha rol bekor qildi — javobda ham narx / summa null, hujjat bekor qilindi",
          _se == 200 and _rk.get("bekor_qilindi") is True and all(m.get("xarid_narxi") is None for m in _rk.get("materiallar") or [{}])
          and _rk.get("xarajatlar_jami") is None and C.get(f"/api/inventory/receipts/{RE}").status_code == 404, _rk)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
_IV = open(os.path.join(ROOT, "templates", "inventory.html"), encoding="utf-8").read()
_FI = open(os.path.join(ROOT, "templates", "finance.html"), encoding="utf-8").read()
import ruxsatlar as _RX                             # noqa: E402
check("S1 oyna: `yukBlok('phKirim', …)`, chaqiruv `typeof phKirimXarajatYukla === 'function'` bilan; Moliya — `typeof kirimMateriallarHtml`",
      "yukBlok('phKirim'" in _IV and "typeof phKirimXarajatYukla === 'function'" in _IV and "typeof kirimMateriallarHtml === 'function'" in _FI)
check("S2 NARX_YOLLAR: oyna summasi va jami — «Xomashyo narxlari» siri",
      getattr(_RX, "NARX_YOLLAR", {}).get("/api/inventory/receipts/{receipt_id}") == ("xarajatlar[].summa", "xarajatlar_jami"))
check("S3 matnlar `escapeHtml` / `textContent` orqali: oyna va Moliya yordamchilarida xom `${x.nomi}` HTML ga yozilmaydi",
      "escapeHtml(s)" in _FI and "escapeHtml(nom[x.turi] || x.turi)" in _IV and "escapeHtml(meta)" in _IV)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("C — haqiqiy Chromium")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
import uvicorn                                      # noqa: E402
from playwright.sync_api import sync_playwright     # noqa: E402
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
JSXATO = []


def kontekst(br, w=1440, h=900, tel=False, tungi=False):
    c = br.new_context(viewport={"width": w, "height": h}, timezone_id="Asia/Tashkent", locale="uz-UZ", is_mobile=tel, has_touch=tel)
    c.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda r: r.fulfill(status=204, body=""))
    if tungi:
        c.add_init_script("try { localStorage.setItem('theme', 'dark'); } catch (e) {}")
    return c


def kirish(pg, u="k226_ad"):
    pg.goto(BU + "/login")
    pg.fill("input[name=username]", u)
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")


def sahifa(ctx, u="k226_ad"):
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: JSXATO.append(str(e)[:200]))
    kirish(pg, u)
    return pg


OYNA = """() => { const o = document.getElementById('phDrawerOverlay'); const x = document.getElementById('phKirimXarajat');
  const b = document.querySelector('#phDrawerOverlay .mv-drawer');
  return {ochiq: !!o && getComputedStyle(o).display !== 'none', sarl: (document.getElementById('phDrawerTitle') || {}).textContent || '',
    blok: x ? x.innerText.replace(/\\u00a0/g, ' ') : null, html: x ? x.innerHTML : null,
    qatorlar: x ? [...x.querySelectorAll('.ph-kx-qator')].map(q => q.dataset.turi) : [],
    toshish: b ? [...b.querySelectorAll('*')].filter(e => e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflowX !== 'auto'
                  && getComputedStyle(e).overflowX !== 'scroll' && e.clientWidth > 0).map(e => e.className || e.tagName).slice(0, 5) : null,
    oyna_w: b ? b.getBoundingClientRect().width : 0, sahifa_toshdi: document.documentElement.scrollWidth > window.innerWidth + 1};
}"""


def tarix_och(pg):
    pg.goto(BU + "/inventory")
    pg.wait_for_load_state("networkidle")
    pg.evaluate("() => { openPurchaseHistory(); }")
    pg.wait_for_function("() => document.querySelectorAll('#hist-list .mv-order-row').length > 0", timeout=15000)


def hujjat_och(pg, rid, kut=True):
    pg.evaluate(f"() => {{ openPhDrawer('{rid}'); }}")
    if kut:
        try:
            pg.wait_for_function("() => { const x = document.getElementById('phKirimXarajat'); return x && !x.querySelector('.ph-kx-yuk'); }",
                                 timeout=8000)
        except Exception:                  # noqa: BLE001
            pg.wait_for_timeout(300)
    return pg.evaluate(OYNA)


with sync_playwright() as pw:
    br = pw.chromium.launch()
    ctx = kontekst(br)
    pg = sahifa(ctx)
    with bolim("C1–C9 oyna"):
        tarix_och(pg)
        o1 = hujjat_och(pg, R1)
        check("C1 «📦 Kirim #R1» oynasi: «Qo'shimcha xarajatlar», «🚚 Transport» 600 000 so'm, «tannarxga qo'shilgan»",
              o1["ochiq"] and f"Kirim #{R1}" in o1["sarl"] and o1["blok"] and "Qo'shimcha xarajatlar" in o1["blok"]
              and "🚚 Transport" in o1["blok"] and "600 000 so'm" in o1["blok"] and "tannarxga qo'shilgan" in o1["blok"]
              and o1["qatorlar"] == ["transport_kirim"], o1)
        check("C2 hujjat jami (materiallar + xarajatlar) = 12 × 624 000 + 600 000 = 8 088 000 so'm; ta'minotchi ko'rinadi",
              o1["blok"] and "Hujjat jami (materiallar + xarajatlar)" in o1["blok"] and "8 088 000 so'm" in o1["blok"]
              and "Ta'minotchi: K226 Ta'minotchi" in o1["blok"], o1["blok"])
        o2 = hujjat_och(pg, R2)
        check("C3 R2: tushirish → yuklash, «Moliyada alohida xarajat», hujjat №; jami 4 900 + 70 000 = 74 900 so'm",
              o2["qatorlar"] == ["tushirish_kirim", "yuklash_kirim"] and o2["blok"].count("Moliyada alohida xarajat") == 2
              and f"Hujjat №: Kirim #{R1} nusxa" in o2["blok"] and "74 900 so'm" in o2["blok"], o2["blok"])
        o3 = hujjat_och(pg, R3)
        check("C4 boshlang'ich ombor + tannarxga: «tannarxga qo'shilgan · Moliyada xarajat sifatida yo'q» + izoh",
              "tannarxga qo'shilgan · Moliyada xarajat sifatida yo'q" in (o3["blok"] or "")
              and "Boshlang'ich ombor — qo'shimcha xarajat Moliyaga yozilmaydi" in (o3["blok"] or ""), o3["blok"])
        o4 = hujjat_och(pg, R4)
        check("C5 boshlang'ich ombor, tannarxsiz — «Moliyaga yozilmagan»", "Moliyaga yozilmagan" in (o4["blok"] or ""), o4["blok"])
        o5 = hujjat_och(pg, R5)
        check("C6 xarajatsiz — «Qo'shimcha xarajat yo'q», hujjat jami yozilmaydi",
              "Qo'shimcha xarajat yo'q" in (o5["blok"] or "") and "Hujjat jami" not in (o5["blok"] or ""), o5["blok"])
        o6 = hujjat_och(pg, R6)
        check("C7 «➕ Boshqa xarajat» 1 500 so'm", "➕ Boshqa xarajat" in (o6["blok"] or "") and "1 500 so'm" in (o6["blok"] or ""), o6["blok"])

        # C8 — sekin javob: R1 ochilib (javob ushlangan), darhol R2 ochilsa — R1 javobi R2 oynasiga chizilmaydi
        _ush = []

        def _sekin(r):
            if r.request.url.endswith(f"/api/inventory/receipts/{R1}"):
                _ush.append(r)
            else:
                r.continue_()
        pg.route("**/api/inventory/receipts/*", _sekin)
        hujjat_och(pg, R1, kut=False)
        pg.wait_for_timeout(300)
        o8 = hujjat_och(pg, R2)
        for _r in _ush:
            _r.continue_()
        pg.wait_for_timeout(800)
        o8b = pg.evaluate(OYNA)
        pg.unroute("**/api/inventory/receipts/*", _sekin)
        check("C8 oyna tez almashtirildi (R1 javobi kechikdi) — R2 oynasida R1 transporti chizilmadi",
              len(_ush) == 1 and f"Kirim #{R2}" in o8b["sarl"] and "600 000" not in (o8b["blok"] or "") and o8b["qatorlar"] == ["tushirish_kirim", "yuklash_kirim"],
              (len(_ush), o8b["sarl"], o8b["blok"]))

        # C9 — xato: 502 HTML va tarmoq — sabab bilan, eski matn qolmaydi
        def _x502(r):
            r.fulfill(status=502, content_type="text/html", body="<html>Bad gateway</html>")
        pg.route("**/api/inventory/receipts/*", _x502)
        o9 = hujjat_och(pg, R1)
        pg.unroute("**/api/inventory/receipts/*", _x502)

        def _xtarmoq(r):
            r.abort()
        pg.route("**/api/inventory/receipts/*", _xtarmoq)
        o9b = hujjat_och(pg, R1)
        pg.unroute("**/api/inventory/receipts/*", _xtarmoq)
        check("C9 502 — «⚠️ Qo'shimcha xarajatlar yuklanmadi — server javob bermadi…», tarmoq — «internet aloqasi yo'q»; summa yo'q",
              "Qo'shimcha xarajatlar yuklanmadi — server javob bermadi" in (o9["blok"] or "") and "600 000" not in (o9["blok"] or "")
              and "internet aloqasi yo'q" in (o9b["blok"] or ""), (o9["blok"], o9b["blok"]))

        # C9b — escape: material nomi `<b>` — matn sifatida (Moliya qatorida ham — C11)
        o9c = hujjat_och(pg, R6)
        _tana = pg.evaluate("() => document.getElementById('phDrawerBody').innerHTML")
        check("C9b oyna — material nomi `<b>` va hujjat raqami `<i>` matn sifatida (escape), blok chizildi, JS xatosi yo'q",
              "<b>qalin</b>" not in _tana and "&lt;b&gt;qalin" in _tana and "➕ Boshqa xarajat" in (o9c["blok"] or "")
              and "Hujjat №: <i>K226</i>" in (o9c["blok"] or "") and "<i>K226" not in (o9c["html"] or "") and not JSXATO,
              (_tana[:300], o9c["html"], JSXATO))

    with bolim("C10–C12 Moliya"):
        pg.goto(BU + "/finance")
        pg.wait_for_load_state("networkidle")
        pg.wait_for_function("() => document.querySelectorAll('#tx-body tr td[data-label=\"Izoh\"]').length > 3", timeout=15000)
        _mt = pg.evaluate("""() => [...document.querySelectorAll('#tx-body tr')].map(tr => {
            const iz = tr.querySelector('td[data-label="Izoh"]'); const m = iz && iz.querySelector('.tx-kirim-mat');
            return {iz: iz ? iz.innerText.replace(/\\u00a0/g, ' ') : '', mat: m ? m.textContent.replace(/\\u00a0/g, ' ') : null,
                    mat_html: m ? m.innerHTML : null}; })""")
        _r1 = [x for x in _mt if f"Transport (kirim) — Kirim #{R1}" in x["iz"] and not x["iz"].startswith("Qo'lda")]
        check("C10 Moliya qatori: «Transport (kirim) — Kirim #R1» ostida «📦 K226 Penoplast 10P (12 dona)»",
              len(_r1) == 1 and _r1[0]["mat"] == "📦 K226 Penoplast 10P (12 dona)", _r1)
        _r2 = [x for x in _mt if f"— Kirim #{R2} (" in x["iz"]]
        check("C11 4 materialli hujjat: «📦 K226 M0 (12,5 kg), K226 M1 (11 kg), K226 M2 (12 kg) … yana 1 ta» (ikkala qatorda)",
              len(_r2) == 2 and all(x["mat"] == "📦 K226 M0 (12,5 kg), K226 M1 (11 kg), K226 M2 (12 kg) … yana 1 ta" for x in _r2), _r2)
        _r6 = [x for x in _mt if f"— Kirim #{R6}" in x["iz"]]
        check("C11b escape: material nomi `<b>` — matn («&lt;b&gt;»), HTML emas",
              len(_r6) == 1 and "K226 <b>qalin</b> & \"q\" (1 dona)" in (_r6[0]["mat"] or "") and "<b>" not in (_r6[0]["mat_html"] or ""), _r6)
        _qo = [x for x in _mt if x["iz"].startswith("Qo'lda — Kirim #")]
        _od = [x for x in _mt if x["iz"].startswith("K226 tushlik")]
        check("C12 qo'lda kiritilgan va oddiy xarajat — materiallar qatori yo'q",
              len(_qo) == 1 and _qo[0]["mat"] is None and len(_od) == 1 and _od[0]["mat"] is None, (_qo, _od))
    ctx.close()

    with bolim("C13 Menejer"):
        ctxm = kontekst(br)
        pgm = sahifa(ctxm, "k226_men")
        tarix_och(pgm)
        om = hujjat_och(pgm, R1)
        check("C13 Menejer — transport bor, summa «—», hujjat jami «—», 600 000 yo'q",
              "🚚 Transport" in (om["blok"] or "") and "600 000" not in (om["blok"] or "") and "8 088 000" not in (om["blok"] or "")
              and (om["blok"] or "").count("—") >= 2, om["blok"])
        ctxm.close()

    with bolim("C14 telefon / tungi"):
        for w, tungi in ((390, False), (320, False), (390, True)):
            ctxt = kontekst(br, w=w, h=800, tel=True, tungi=tungi)
            pgt = sahifa(ctxt)
            tarix_och(pgt)
            ot = hujjat_och(pgt, R2)
            # uzun (bo'shliqsiz) material nomi — summa ustiga tushmaydi (review226 P3)
            hujjat_och(pgt, RL)
            _uz = pgt.evaluate("""() => [...document.querySelectorAll('#phDrawerBody .mv-row')].map(r => {
                const a = r.children[0].getBoundingClientRect(), b = r.children[1].getBoundingClientRect();
                return {ust: a.right > b.left + 1 && a.bottom > b.top && a.top < b.bottom, toshdi: r.children[0].scrollWidth > r.children[0].clientWidth + 1}; })""")
            _mol = None
            pgt.goto(BU + "/finance")
            pgt.wait_for_load_state("networkidle")
            pgt.wait_for_timeout(800)
            _mol = pgt.evaluate("""() => { const m = [...document.querySelectorAll('.tx-kirim-mat')];
                return {soni: m.length, toshdi: m.filter(e => e.scrollWidth > e.clientWidth + 1).length,
                        sahifa: document.documentElement.scrollWidth > window.innerWidth + 1,
                        rang: m.length ? getComputedStyle(m[0]).color : null, fon: getComputedStyle(document.body).backgroundColor,
                        // materiallar — izoh OSTIDA (telefon kartasida `td` flex qator; review226 №1): o'z blokining chap chetida, birinchi qatordan pastda
                        ostida: m.length > 0 && m.every(e => { const p = e.parentElement.getBoundingClientRect(), r = e.getBoundingClientRect();
                                  return Math.abs(r.left - p.left) <= 1 && r.top >= p.top + 8; })}; }""")
            check(f"C14 {w} px{' tungi' if tungi else ''}: oyna ichida toshish yo'q, sahifa gorizontal toshmaydi; Moliya materiallar qatori toshmaydi",
                  ot["ochiq"] and ot["blok"] and not ot["toshish"] and not ot["sahifa_toshdi"] and ot["oyna_w"] <= w
                  and _mol["soni"] >= 3 and _mol["toshdi"] == 0 and not _mol["sahifa"] and _mol["rang"] != _mol["fon"], (ot, _mol))
            check(f"C14b {w} px{' tungi' if tungi else ''}: Moliya — materiallar izoh ostida; oynada uzun material nomi summa ustiga tushmaydi",
                  _mol["ostida"] and _uz and not any(x["ust"] or x["toshdi"] for x in _uz), (_mol, _uz))
            ctxt.close()
    with bolim("C16 bekor qilish oynasi matni"):
        ctxr = kontekst(br)
        pgr = sahifa(ctxr)
        pgr.goto(BU + "/inventory")
        pgr.wait_for_load_state("networkidle")
        _mt = pgr.evaluate("""() => [kirimBekorRejaMatni({materiallar: [{nomi: 'A', miqdor: 2, birlik: 'kg', joriy_qoldiq: 5, yangi_qoldiq: 3,
              joriy_narx: null, yangi_narx: null, narx_qaytdi: true}], xarajatlar: [{turi: 'transport_kirim', summa: null}], xarajatlar_jami: null, manfiy: []}),
            kirimBekorRejaMatni({materiallar: [{nomi: 'A', miqdor: 2, birlik: 'kg', joriy_qoldiq: 5, yangi_qoldiq: 3,
              joriy_narx: 1500, yangi_narx: 1000, narx_qaytdi: true}], xarajatlar: [{turi: 'transport_kirim', summa: 600}], xarajatlar_jami: 600, manfiy: []})]""")
        _mt = [str(x).replace("\xa0", " ") for x in (_mt or [])]
        check("C16 bekor qilish oynasi: narx null — narx qismi va «0 so'm» yo'q; narx bor — avvalgidek («narx 1 500 → 1 000 so'm», «600 so'm»)",
              _mt[0] == "• A: −2 kg (qoldiq 5 → 3)\n• Moliyadagi qo'shimcha xarajatlar o'chadi"
              and _mt[1] == "• A: −2 kg (qoldiq 5 → 3), narx 1 500 → 1 000 so'm\n• Moliyadagi qo'shimcha xarajatlar o'chadi: 600 so'm", _mt)
        ctxr.close()
    br.close()
check("C15 sinov davomida sahifada JS xatosi yo'q", not JSXATO, JSXATO[:5])

server.should_exit = True
print(f"\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
