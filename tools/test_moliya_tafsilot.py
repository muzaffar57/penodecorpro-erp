#!/usr/bin/env python3
"""
test_moliya_tafsilot.py — kech106, K106-2 darvozasi: oylik moliya hisobotining xarajatlar ro'yxati (PDF "Xarajatlar
tafsiloti" jadvali va Moliya sahifasidagi ro'yxat) JAMI XARAJAT bilan BIR xil bo'lsin.

NIMA UCHUN (zip 101 kodida O'LCHANGAN — `work/probe106m.py`, `work/probe106mw.js`, `natija/k106/probe106m*_d108.txt`)
---------------------------------------------------------------------------------------------------------------
PDF jadvali shu oyning HAMMA tranzaksiyasini qayta sanardi: asosiy 4 turkum (Arenda, Elektr, Tushlik, Soliqlar) IKKI
marta chiqardi, tannarxga qo'shilgan kirim xarajatlari (JAMI ga kirmaydi) ro'yxatda edi, korxona to'lagan transport (xarid
va yuk) JAMI da bor, ro'yxatda YO'Q edi, kirim turkumlari xom kalit bilan ("transport_kirim"), tranzaksiyalar 200 ta bilan
cheklangan edi — qatorlar 5 251 550, JAMI 3 151 600. Moliya sahifasi esa faqat 4 ta kirim turkumini ko'rsatardi (Reklama,
Boshqa va boshqalar yo'q) — ko'rsatilgan 2 701 600, "Jami xarajat" 3 151 600.

BO'LIMLAR (fikstura — joriy Toshkent oyi: asosiy turkumlar tranzaksiya sifatida (arenda 2 ta), reklama, "boshqa" 3 izoh +
izohsiz + 205 ta mayda (200 cheklovidan ko'p), kutilmagan, erkin turkum "internet" va "a<b>c", kirim hujjati — tannarxga
qo'shilgan va qo'shilmagan, xarid transporti, yuk — korxona transporti, «Tayyor» buyurtma (ishlab chiqarish xarajati, usta
KPI, Ehson 5 %), hodim; o'tgan oy — eski oylik shakl (MonthlyExpense), tranzaksiyasiz)
  A — PDF: qatorlar yig'indisi = JAMI = hisobot; takror yo'q; asosiy turkumlar bir marta; transport; kirim turkumlari
      nomi bilan, tannarxga qo'shilgani yo'q; "Boshqa" izohlar bo'yicha (205 ta mayda — TO'LIQ); erkin turkum; matn AYNAN
  B — Moliya sahifasi (`buildExpDetail`, node): ko'rsatilgan yig'indi = "Jami xarajat"; HAMMA qo'shimcha turkum; escapeHtml
  C — o'tgan oy (eski oylik shakl): PDF qatorlari = JAMI
  D — statik: PDF marshruti tranzaksiyalarni cheklovsiz beradi
PDF matni — kutubxonasiz (ASCII85 + Flate; TTF ToUnicode / Type1 WinAnsi).

REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_moliya_tafsilot.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_moliya_tafsilot.py
"""
import os
import re
import sys
import json
import zlib
import base64
import tempfile
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "moliya_tafsilot_test"
_DB = os.path.join(tempfile.gettempdir(), "moliya_tafsilot_test.db")

if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    if os.path.exists(_DB):
        os.remove(_DB)
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ.pop("TENANT_FILTER", None)
os.environ.pop("TELEGRAM_BOT_TOKEN", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402
from datetime import datetime, timedelta           # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from sqlalchemy import text                        # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Project, Inventory, Master, MonthlyExpense  # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

for _n in ("_send_telegram", "_send_telegram_to", "_send_telegram_document", "_send_telegram_to_qoplamachi"):
    if hasattr(main, _n):
        setattr(main, _n, lambda *a, **k: False)

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
        self.content = b""

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


# ── PDF o'quvchi (kutubxonasiz; `tools/test_pdf_shrift.py` bilan bir xil usul) ──────────────────────────────────────
def _oqim(tana):
    lugat, _, qolgan = tana.partition(b"stream")
    data = qolgan[2:] if qolgan.startswith(b"\r\n") else qolgan[1:]
    m = re.search(rb"/Length\s+(\d+)(?!\s+\d+\s+R)", lugat)
    data = data[:int(m.group(1))] if m else data[:data.rfind(b"endstream")].rstrip(b"\r\n")
    if b"ASCII85Decode" in lugat:
        # kech106: tugatuvchi "~>" FAQAT bir marta olinadi — ">" ASCII85 ning oddiy belgisi (29); ilgari `rstrip(b"~>")`
        # ma'lumotning oxirgi ">" ini ham o'chirib Flate ni buzardi (~1-2 % oqim — vaqt sayohatida tasodifiy yiqilish)
        data = re.sub(rb"\s", b"", data)
        if data.startswith(b"<~"):
            data = data[2:]
        if data.endswith(b"~>"):
            data = data[:-2]
        data = base64.a85decode(data)
    if b"FlateDecode" in lugat:
        data = zlib.decompress(data)
    return lugat, data


def _satr(b):
    chiq, i = bytearray(), 0
    while i < len(b):
        c = b[i]
        if c == 0x5C and i + 1 < len(b):
            n = b[i + 1]
            if 0x30 <= n <= 0x37:
                j = i + 1
                while j < len(b) and j < i + 4 and 0x30 <= b[j] <= 0x37:
                    j += 1
                chiq.append(int(b[i + 1:j], 8) & 0xFF)
                i = j
                continue
            chiq.append({ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12}.get(n, n))
            i += 2
            continue
        chiq.append(c)
        i += 1
    return bytes(chiq)


# PDF kontent tokenlari (kech106): satr `( … )` — BUTUN token, shuning uchun uning ichidagi "ET" / "BT" ("YETKAZISH",
# "(BT)") `BT … ET` blokini uzmaydi (ilgari `re.finditer(rb"BT(.*?)ET", …)` blokni satr ichida uzib, qatorni tashlardi).
_PDF_TOKEN = re.compile(rb"%[^\r\n]*|\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>|\[|\]|/[^\s/\[\]()<>{}%]*|[^\s/\[\]()<>{}%]+", re.S)


def _bt_bloklar(data):
    """Kontent oqimidagi `BT … ET` bloklari — har biri tokenlar ro'yxati (satr tokeni qavslari bilan: `(…)`)."""
    blok = None
    for m in _PDF_TOKEN.finditer(data):
        tok = m.group(0)
        if tok.startswith(b"%"):
            continue
        if tok == b"BT":
            blok = []
        elif tok == b"ET":
            if blok is not None:
                yield blok
            blok = None
        elif blok is not None:
            blok.append(tok)


def pdf_matn(bayt):
    """PDF matni: har `BT … ET` bloki alohida qator (jadval katagi — bitta qator)."""
    obyektlar = {int(n): tana for n, tana in re.findall(rb"(\d+) 0 obj\s*(.*?)\s*endobj", bayt, re.S)}
    shriftlar = {}
    for tana in obyektlar.values():
        nom = re.search(rb"/Name\s*/([^\s/>\[]+)", tana)
        if b"/Type /Font" not in tana or not nom:
            continue
        cmap = None
        tu = re.search(rb"/ToUnicode\s+(\d+)\s+0\s+R", tana)
        if tu and int(tu.group(1)) in obyektlar:
            _, cm = _oqim(obyektlar[int(tu.group(1))])
            cmap = {}
            for blok in re.findall(rb"beginbfchar(.*?)endbfchar", cm, re.S):
                for k, v in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blok):
                    cmap[int(k, 16)] = bytes.fromhex(v.decode()).decode("utf-16-be")
        shriftlar[nom.group(1).decode()] = cmap
    satrlar = []
    for tana in obyektlar.values():
        if b"stream" not in tana or b"/Type /Font" in tana:
            continue
        try:
            _, data = _oqim(tana)
        except Exception:                  # noqa: BLE001
            continue
        if b" Tf" not in data:
            continue
        for blok in _bt_bloklar(data):
            cmap, qism = None, []
            for j, tok in enumerate(blok):
                if tok == b"Tf" and j >= 2 and blok[j - 2].startswith(b"/"):
                    cmap = shriftlar.get(blok[j - 2][1:].decode())
                elif tok == b"Tj" and j >= 1 and blok[j - 1].startswith(b"("):
                    kodlar = _satr(blok[j - 1][1:-1])
                    qism.append("".join(cmap.get(k, "■") for k in kodlar) if cmap is not None else kodlar.decode("cp1252", "replace"))
            if qism:
                satrlar.append(" ".join(qism).strip())
    return satrlar


def jadval(satrlar):
    """"Xarajatlar tafsiloti" jadvali: [(nom, summa)] va JAMI XARAJAT."""
    try:
        i = next(k for k, q in enumerate(satrlar) if q.startswith("Xarajatlar tafsiloti"))
        j = next(k for k in range(i, len(satrlar)) if satrlar[k] == "JAMI XARAJAT")
    except StopIteration:
        return [], None
    qatorlar = []
    q = satrlar[i + 1:j]
    k = 0
    while k < len(q):
        m = re.fullmatch(r"(-?[\d ]+) so'm", q[k + 1]) if k + 1 < len(q) else None
        if m and q[k] not in ("Xarajat nomi", "Summa"):
            qatorlar.append((q[k], int(m.group(1).replace(" ", ""))))
            k += 2
        else:
            k += 1
    jm = re.fullmatch(r"(-?[\d ]+) so'm", satrlar[j + 1]) if j + 1 < len(satrlar) else None
    return qatorlar, (int(jm.group(1).replace(" ", "")) if jm else None)


# ── fikstura ────────────────────────────────────────────────────────────────────────────────────────────────────
_tk = datetime.utcnow() + timedelta(hours=5)
YIL, OY = _tk.year, _tk.month
O_YIL, O_OY = (YIL, OY - 1) if OY > 1 else (YIL - 1, 12)

s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "mt_admin", "Parol123!", UserRole.ADMIN, "MT admin", company_id=1)
PRJ = Project(company_id=1, client_name="MT Mijoz", project_name="MT loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="MT Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
MAT = Inventory(company_id=1, item_name="MT Akril", unit="kg", stock_quantity=100, price_per_unit=1000,
                category="Kimyoviy qo'shimchalar")
MAT2 = Inventory(company_id=1, item_name="MT Setka", unit="dona", stock_quantity=100, price_per_unit=1000, category="Boshqa")
USTA = Master(company_id=1, name="MT Usta", phone="+998900001073", kpi_percent=10)
s.add_all([PRJ, PENO, MAT, MAT2, USTA])
s.commit()
ID = {"PRJ": PRJ.id, "PENO": PENO.id, "MAT": MAT.id, "MAT2": MAT2.id, "USTA": USTA.id}
s.add(MonthlyExpense(company_id=1, year=O_YIL, month=O_OY, arenda=1_000_000, elektr=150_000, tushlik=0, soliqlar=0))
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    crud.set_setting(s, "ehson_percent", "5", company_id=1)
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "mt_admin", "password": "Parol123!"}, follow_redirects=False)
if _lr.status_code != 302:
    print("LOGIN BO'LMADI", _lr.status_code)
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

XARAJATLAR = [("arenda", 1_000_000, "Ijara 1"), ("arenda", 500_000, "Ijara 2"), ("elektr", 300_000, None),
              ("tushlik", 200_000, None), ("soliqlar", 400_000, None), ("reklama", 250_000, "Instagram"),
              ("boshqa", 120_000, "Tozalik"), ("boshqa", 80_000, "Texnik ko'rik"), ("boshqa", 30_000, None),
              ("kutilmagan", 60_000, "Zapchast"), ("internet", 90_000, "Provayder"), ("a<b>c", 15_000, "Belgi sinovi")]
# 205 ta mayda — AVVAL (eskiroq): "oxirgi 200 ta" cheklovi bo'lsa asosiy turkumlar ro'yxatga kiradi (takror ko'rinadi),
# "Mayda" esa to'liq kirmaydi — ikkala nuqson ham asl kodda ko'rinsin.
_st_mayda = [req(C, "post", "/api/finance/transactions", json={"category": "boshqa", "amount": 1000.0, "notes": "Mayda"}).status_code
             for _ in range(205)]
_st = [req(C, "post", "/api/finance/transactions", json={"category": k, "amount": float(v), "notes": iz}).status_code
       for k, v, iz in XARAJATLAR]
_r1 = req(C, "post", "/api/inventory/receipt", json={"items": [{"inventory_id": ID["MAT"], "quantity": 10, "price_per_unit": 1000}],
                                                     "transport_cost": 500, "tushirish_cost": 200, "yuklash_cost": 100,
                                                     "boshqa_cost": 50, "add_to_cost": True, "notes": "MT kirim (tannarxga)"})
_r2 = req(C, "post", "/api/inventory/receipt", json={"items": [{"inventory_id": ID["MAT2"], "quantity": 10, "price_per_unit": 1000}],
                                                     "transport_cost": 700, "add_to_cost": False, "notes": "MT kirim (xarajat)"})
_r3 = req(C, "post", f"/api/inventory/{ID['MAT']}/purchase", json={"quantity": 5, "price_per_unit": 1000,
                                                                    "transport_payer": "self", "transport_cost": 900})
_ro = req(C, "post", "/api/orders", params={"confirm_shortage": "true"}, json={
    "project_id": ID["PRJ"], "order_type": "product", "master_id": ID["USTA"],
    "items": [{"name": "MT detal", "category": "profil", "width": 20, "thickness": 10, "length": 10, "quantity": 1,
               "unit_price": 1_000_000, "is_coated": False, "penoplast_id": ID["PENO"]}]})
ID["O1"] = (js(_ro) or {}).get("id") if _ro.status_code == 200 else None
s = SessionLocal()
try:
    ID["IT1"] = s.execute(text("SELECT id FROM order_items WHERE order_id = :o"), {"o": ID["O1"] or 0}).scalar()
finally:
    s.close()
_rd = req(C, "post", "/api/deliveries", json={"order_id": ID["O1"], "items": [{"order_item_id": ID["IT1"], "quantity": 10}],
                                              "transport_cost": 300_000, "transport_payer": "company", "payment_method": "naqd",
                                              "payment_amount": 1_000_000})
_rt = req(C, "post", f"/api/orders/{ID['O1']}/ready", params={"loy_kg": "0"})
_re = req(C, "post", "/api/employees", json={"name": "MT Hodim", "pay_type": "fixed", "fixed_amount": 3_000_000})

section("0. Tayyorgarlik")
check("0.1 fikstura: 12 + 205 xarajat, 2 kirim hujjati, xarid transporti, buyurtma → yuk (korxona transporti) → «Tayyor», hodim",
      _st == [200] * 12 and _st_mayda == [200] * 205 and _r1.status_code == _r2.status_code == _r3.status_code == 200
      and _rd.status_code == 200 and _rt.status_code == 200 and _re.status_code == 200 and ID.get("IT1"),
      [_st, sorted(set(_st_mayda)), _r1.status_code, _r2.status_code, _r3.status_code, _rd.status_code, _rt.status_code,
       _re.status_code, _rt.text[:200] if _rt.status_code != 200 else ""])

REP = js(req(C, "get", "/api/finance/report", params={"year": YIL, "month": OY})) or {}
_rp = req(C, "get", "/api/finance/report-pdf", params={"year": YIL, "month": OY})
try:
    SATRLAR = pdf_matn(_rp.content) if _rp.status_code == 200 else []
except Exception as e:                     # noqa: BLE001
    SATRLAR = [f"{type(e).__name__}: {e}"]
QATOR, JAMI = jadval(SATRLAR)
NOMLAR = [n for n, _ in QATOR]
QD = {}
for _n, _v in QATOR:
    QD[_n] = QD.get(_n, 0) + _v
JAMI_HISOBOT = round(float(REP.get("jami_xarajat", 0) or 0) + float(REP.get("ishlab_chiqarish_xarajat", 0) or 0))
QX = REP.get("qoshimcha_xarajatlar", {}) or {}

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. PDF \"Xarajatlar tafsiloti\" — JAMI bilan bir manba")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("A1 hisobot va PDF 200; hisobotda usta KPI, Ehson, hodim, ishlab chiqarish, transport (fikstura qamrovi)",
      _rp.status_code == 200 and REP.get("usta_kpi_xarajat", 0) > 0 and REP.get("ehson_xarajat", 0) > 0
      and REP.get("hodimlar_moslashuvchan_xarajat", REP.get("hodimlar_xarajat", 0)) > 0
      and REP.get("ishlab_chiqarish_xarajat", 0) > 0 and REP.get("transport_xarajat", 0) > 0,
      [_rp.status_code, {k: REP.get(k) for k in ("usta_kpi_xarajat", "ehson_xarajat", "hodimlar_moslashuvchan_xarajat",
                                                  "ishlab_chiqarish_xarajat", "transport_xarajat")}])
check("A2 jadval qatorlari yig'indisi = PDF JAMI XARAJAT = hisobot (jami_xarajat + ishlab chiqarish), ±1 so'm",
      QATOR and JAMI is not None and abs(sum(v for _, v in QATOR) - JAMI) <= 1 and abs(JAMI - JAMI_HISOBOT) <= 1,
      [sum(v for _, v in QATOR), JAMI, JAMI_HISOBOT, QATOR])
check("A3 takrorlangan qator nomi yo'q (ilgari asosiy 4 turkum IKKI marta)",
      QATOR and len(NOMLAR) == len(set(NOMLAR)), sorted({n for n in NOMLAR if NOMLAR.count(n) > 1}))
_x = REP.get("xarajatlar", {}) or {}
check("A4 Arenda 1 500 000 (2 tranzaksiya), Elektr, Tushlik, Soliqlar — bir martadan, hisobot qiymati bilan",
      all(NOMLAR.count(k) == 1 and QD.get(k) == round(float(_x.get(v, 0))) for k, v in
          (("Arenda", "arenda"), ("Elektr", "elektr"), ("Tushlik", "tushlik"), ("Soliqlar", "soliqlar")))
      and QD.get("Arenda") == 1_500_000, {k: QD.get(k) for k in ("Arenda", "Elektr", "Tushlik", "Soliqlar")})
check("A5 transport qatorlari: xarid (kirish) 900 va yuk (korxona hisobidan) 300 000 — hisobot bilan",
      QD.get("Transport — xomashyo xaridi (kirish)") == round(float(REP.get("transport_xarajat_kirish", -1)))
      and QD.get("Transport — yuk yetkazish (korxona hisobidan)") == round(float(REP.get("transport_xarajat_yetkazish", -1)))
      and QD.get("Transport — xomashyo xaridi (kirish)") == 900
      and QD.get("Transport — yuk yetkazish (korxona hisobidan)") == 300_000,
      [n for n in NOMLAR if "ransport" in n], )
check("A6 kirim hujjati xarajati NOMI bilan (\"Kirim hujjati — transport\" 700), xom kalit (\"transport_kirim\") yo'q",
      QD.get("Kirim hujjati — transport") == 700 == round(float(QX.get("transport_kirim", -1)))
      and not [n for n in NOMLAR if re.fullmatch(r"[a-z_]+_kirim|kirim_[a-z_]+", n)],
      [n for n in NOMLAR if "irim" in n])
check("A7 tannarxga qo'shilgan kirim xarajati (tushirish 200, yuklash 100, boshqa 50, transport 500) ro'yxatda YO'Q",
      not [n for n in NOMLAR if "tushirish" in n.lower() or "yuklash" in n.lower() or n == "Kirim hujjati — boshqa xarajat"]
      and QD.get("Kirim hujjati — transport") == 700, [n for n in NOMLAR if "irim" in n])
_boshqa = {n: v for n, v in QD.items() if n.startswith("Boshqa — ")}
check("A8 \"Boshqa\" izohlar bo'yicha: Tozalik 120 000, Texnik ko'rik 80 000, Izohsiz 30 000, Mayda 205 000 (205 ta — "
      "200 cheklovisiz); yig'indi = hisobot, qoldiq qatori yo'q",
      _boshqa.get("Boshqa — Tozalik") == 120_000 and _boshqa.get("Boshqa — Texnik ko'rik") == 80_000
      and _boshqa.get("Boshqa — Izohsiz") == 30_000 and _boshqa.get("Boshqa — Mayda") == 205_000
      and "Boshqa — boshqa yozuvlar" not in _boshqa and sum(_boshqa.values()) == round(float(QX.get("boshqa", -1))),
      [_boshqa, QX.get("boshqa")])
check("A9 boshqa turkumlar: Reklama 250 000, \"Kutilmagan xarajat — Zapchast\" 60 000, erkin \"internet\" 90 000, "
      "\"a<b>c\" 15 000 — matn AYNAN (belgilash sifatida o'qilmadi)",
      QD.get("Reklama") == 250_000 and QD.get("Kutilmagan xarajat — Zapchast") == 60_000 and QD.get("internet") == 90_000
      and {re.sub(r"\s+", "", n): v for n, v in QD.items()}.get("a<b>c") == 15_000,   # ReportLab "<" / ">" ni alohida bo'lak chizadi
      {k: QD.get(k) for k in ("Reklama", "Kutilmagan xarajat — Zapchast", "internet")} | {"a<b>c": [n for n in NOMLAR if "b" in n and "c" in n][:3]})
check("A10 usta KPI, hodim, Ehson, ishlab chiqarish qatorlari hisobot qiymatlari bilan",
      QD.get("Ehson (xayriya)") == round(float(REP.get("ehson_xarajat", -1)))
      and QD.get("Ishlab chiqarish xarajati (xomashyo tan narxi)") == round(float(REP.get("ishlab_chiqarish_xarajat", -1)))
      and any(n.startswith("Usta KPI — MT Usta") for n in NOMLAR) and any(n.startswith("MT Hodim") for n in NOMLAR),
      [n for n in NOMLAR if n.startswith(("Usta", "MT", "Ehson", "Ishlab"))])

# A11 — tranzaksiyalar to'liq berilmasa (masalan boshqa chaqiruvchi cheklab bersa): izohli qatorlar + QOLDIQ qatori, yig'indi = JAMI
try:
    import finance_pdf as _fpdf
    from models import ExpenseTransaction as _ET
    _s11 = SessionLocal()
    try:
        _bitta = _s11.query(_ET).filter(_ET.category == "boshqa", _ET.notes == "Tozalik").all()
        _pdf11 = _fpdf.generate_finance_report_pdf(REP, _bitta, [], YIL, OY, None, db=_s11, company_id=1)
    finally:
        _s11.close()
    _q11, _j11 = jadval(pdf_matn(_pdf11))
except Exception as e:                     # noqa: BLE001
    _q11, _j11 = [(f"{type(e).__name__}: {e}", 0)], None
_d11 = dict(_q11)
check("A11 tranzaksiyalar qisman berilsa: \"Boshqa — Tozalik\" 120 000 + \"Boshqa — boshqa yozuvlar\" (qoldiq), yig'indi = JAMI",
      _d11.get("Boshqa — Tozalik") == 120_000
      and _d11.get("Boshqa — boshqa yozuvlar") == round(float(QX.get("boshqa", 0))) - 120_000
      and _j11 is not None and abs(sum(v for _, v in _q11) - _j11) <= 1, [_q11, _j11])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Moliya sahifasi — buildExpDetail (node)")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════


def js_funksiya(src, nom_):
    i = src.find(f"\nfunction {nom_}(")
    if i < 0:
        return None
    j = src.find("\n}\n", i)
    return src[i + 1:j + 2] if j > 0 else None


_fin = open(os.path.join(ROOT, "templates", "finance.html"), encoding="utf-8").read()
_fn = js_funksiya(_fin, "buildExpDetail")
_JS = r"""
const elementlar = {};
const document = {getElementById: (id) => (elementlar[id] = elementlar[id] || {style: {}, textContent: '', innerHTML: ''})};
function fmtFull(n){return Number(Math.round(n||0)).toLocaleString('ru-RU');}
function fmt(n){return String(Math.round(n||0));}
function escapeHtml(s){return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function buildRevDonut(){}
__FN__
const d = JSON.parse(require('fs').readFileSync(0, 'utf8'));
buildExpDetail(d);
process.stdout.write(JSON.stringify(elementlar['expDetail'].innerHTML));
"""
_h = ""
if _fn:
    try:
        _p = subprocess.run(["node", "-e", _JS.replace("__FN__", _fn)], input=json.dumps(REP), capture_output=True, text=True,
                            timeout=60)
        _h = json.loads(_p.stdout) if _p.returncode == 0 else ""
        if not _h:
            print("   node:", _p.stderr[:400])
    except Exception as e:                 # noqa: BLE001
        print("   node ishlamadi:", e)


def _son(t):
    return int(re.sub(r"[^\d-]", "", t) or 0)


_guruh = [(_t, _son(_v)) for _t, _v in re.findall(r'fin-exp-group-title">([^<]*)</div>\s*<div class="fin-exp-group-total">([^<]*)<', _h)]
_dum = [(_t.strip(), _son(_v)) for _t, _v in re.findall(r'fin-exp-name"[^>]*>([^<]*)</span>\s*<span class="fin-exp-val"[^>]*>([^<]*)<', _h)]
_doimiy = [(_t, _son(_v)) for _t, _v in re.findall(r'fin-exp-group-row-name"[^>]*>([^<]*)</span><span class="fin-exp-group-row-val">([^<]*)<', _h)]
_jami_w = _son((re.search(r"Jami xarajat:</span><span[^>]*>([^<]*)<", _h) or [None, "0"])[1]) if _h else None
_yig_w = sum(v for t, v in _guruh if re.search(r"Doimiy|Usta yillik KPI|Hodimlar", t)) + sum(v for _, v in _dum)
check("B1 buildExpDetail node da ishladi", bool(_h), _fn is not None)
check("B2 ko'rsatilgan xarajatlar yig'indisi (guruhlar + ishlab chiqarish / Ehson / brak / transport) = \"Jami xarajat\"",
      _h and abs(_yig_w - _jami_w) <= 1 and abs(_jami_w - JAMI_HISOBOT) <= 1, [_yig_w, _jami_w, JAMI_HISOBOT, _guruh, _dum])
_dn = dict(_doimiy)
check("B3 HAMMA qo'shimcha turkum ro'yxatda: Reklama, Boshqa, Kutilmagan xarajat, internet, kirim transporti",
      _dn.get("Reklama") == 250_000 and _dn.get("Boshqa") == round(float(QX.get("boshqa", -1)))
      and _dn.get("Kutilmagan xarajat") == 60_000 and _dn.get("internet") == 90_000 and _dn.get("🚚 Transport (kirim)") == 700,
      _doimiy)
check("B4 erkin turkum nomi escapeHtml bilan (\"a&lt;b&gt;c\" — HTML sifatida o'qilmaydi)",
      "a&lt;b&gt;c" in _h and "a<b>c" not in _h, re.findall(r".{0,40}a.lt;b.{0,40}", _h)[:2])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("C. O'tgan oy — eski oylik shakl (MonthlyExpense), tranzaksiyasiz")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
_rep_o = js(req(C, "get", "/api/finance/report", params={"year": O_YIL, "month": O_OY})) or {}
_rp_o = req(C, "get", "/api/finance/report-pdf", params={"year": O_YIL, "month": O_OY})
try:
    _q_o, _j_o = jadval(pdf_matn(_rp_o.content)) if _rp_o.status_code == 200 else ([], None)
except Exception as e:                     # noqa: BLE001
    _q_o, _j_o = [(f"{type(e).__name__}: {e}", 0)], None
check("C1 o'tgan oy: Arenda 1 000 000, Elektr 150 000 (eski shakl); qatorlar yig'indisi = JAMI = hisobot",
      dict(_q_o).get("Arenda") == 1_000_000 and dict(_q_o).get("Elektr") == 150_000 and _j_o is not None
      and abs(sum(v for _, v in _q_o) - _j_o) <= 1
      and abs(_j_o - round(float(_rep_o.get("jami_xarajat", 0) or 0) + float(_rep_o.get("ishlab_chiqarish_xarajat", 0) or 0))) <= 1,
      [_q_o, _j_o, _rep_o.get("jami_xarajat")])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. Statik")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
_src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
_i = _src.find("def api_finance_report_pdf(")
_blok = _src[_i:_src.find("\ndef ", _i + 10)] if _i != -1 else ""
check("D1 PDF marshruti oyning HAMMA tranzaksiyasini beradi (`get_expense_transactions(..., limit=None, …)`)",
      re.search(r"get_expense_transactions\([^)]*limit=None", _blok), re.findall(r"get_expense_transactions\([^)]*\)", _blok))


def _nazorat_pdf():
    """Sun'iy PDF (Type1 shrift, ASCII85 + Flate kontent oqimi): ASCII85 matni tugatuvchi "~>" dan OLDIN ">" bilan tugaydi
    (">" — ASCII85 ning oddiy belgisi; `rstrip(b"~>")` uni ham o'chirib Flate ni buzardi — ~1-2 % oqim, vaqt sayohatida
    tasodifiy yiqilish, kech106); birinchi satr ichida "ET" / "BT" bor ("QISMAN YETKAZISH (BT) ET")."""
    for i in range(5000):
        kontent = ("BT /F1 12 Tf 72 700 Td (QISMAN YETKAZISH \\(BT\\) ET) Tj ET\n"
                   f"BT /F1 12 Tf 72 680 Td (nazorat {i}) Tj ET\n").encode("latin-1")
        kod = base64.a85encode(zlib.compress(kontent))
        if kod.endswith(b">"):
            break
    oqim = kod + b"~>"
    return (b"%PDF-1.4\n1 0 obj\n<< /BaseFont /Helvetica /Encoding /WinAnsiEncoding /Name /F1 /Subtype /Type1 /Type /Font >>\n"
            b"endobj\n2 0 obj\n<< /Filter [ /ASCII85Decode /FlateDecode ] /Length " + str(len(oqim)).encode() + b" >>\nstream\n"
            + oqim + b"\nendstream\nendobj\n%%EOF\n"), i


try:
    _npdf, _ni = _nazorat_pdf()
    _n = pdf_matn(_npdf)
except Exception as e:                     # noqa: BLE001
    _ni, _n = -1, [f"{type(e).__name__}: {e}"]
check("D2 nazorat: PDF o'quvchi — ASCII85 oqimi \">\" bilan tugasa ham o'qiladi (tugatuvchi \"~>\" faqat bir marta olinadi), satr ichidagi \"ET\" / \"BT\" (\"YETKAZISH\") BT … ET blokini uzmaydi",
      _n == ["QISMAN YETKAZISH (BT) ET", f"nazorat {_ni}"], [_ni, _n])

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
