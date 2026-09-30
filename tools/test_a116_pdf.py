#!/usr/bin/env python3
"""
test_a116_pdf.py — kech116, A bosqich 2-qism, G2-04: buyurtma pul hisobi qatorlari — YAGONA qoida
(`crud.buyurtma_hisob_qatorlari`), uchala mijoz hujjati (yuk xati, hisob-kitob varaqasi, buyurtma nakladnoyi) va
buyurtma oynasi API si (`/api/orders/{id}` → `hisob`).

NIMA UCHUN KERAK (audit kech114 — O'LCHANGAN, asl kod = `staging` 44c40ee)
  «Yuk xati» va «Hisob-kitob varaqasi»: «Buyurtma jami 900 000 / To'langan 600 000 / QARZ QOLDI 264 000» — 36 000 so'mlik
  qaytarish hech qayerda yo'q (chegirma qatori faqat `discount_percent > 0` bo'lsa chiqardi); hisob-kitob varaqasida
  «Berilgan mahsulot 900 000» qatori summalar orasida turardi. Buyurtma PDF i shu qaytarishni «Chegirma: - 36,000» derdi
  (buyurtma oynasida u alohida «Qaytarish»); to'lovda kechirilgan qarz ham «Chegirma» ichida edi; qarz o'z formulasi
  bilan (`max(0, kelishilgan − to'langan)`). Mijoz raqamlarni qo'shib chiqolmasdi.
TALAB: hamma hujjatda bir xil qatorlar va ular qo'shiladi — jami − chegirma (yoki + ustama) − qaytarish − kechirilgan =
  kelishilgan; kelishilgan − to'langan = qarz (yoki ortiqcha to'langan); tiyinli summalarda ham (ko'rsatilgan butun
  so'mlarda) AYNAN.
BO'LIMLAR: A — audit holati (qaytarish, chegirmasiz); B — chegirma + kechirilgan qarz; C — ustama; D — ortiqcha to'langan;
  E — tiyinli summalar; X — xatolar. Har bo'limda: API `hisob`, yuk xati PDF, hisob-kitob varaqasi PDF, nakladnoy PDF
  (matn kutubxonasiz o'qiladi — `tools/test_pdf_matn.py` usuli).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga qarshi QULAMAYDI.
ISHLATISH: python3 tools/test_a116_pdf.py
"""
import os
import re
import sys
import zlib
import base64
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "a116_pdf_test"
_T = tempfile.mkdtemp(prefix="a116p_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'a116_pdf_test.db')}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, Project, Order, OrderItem, ReturnItem   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
HOLATLAR = []


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
        print(f"  ✗ {label}   {str(detail)[:700]}")


def section(t):
    print(f"\n--- {t} ---")


class _Xato:
    def __init__(self, e):
        self.status_code = 599
        self.text = f"{type(e).__name__}: {e}"
        self.content = b""
        self.headers = {}

    def json(self):
        return {}


def req(c, metod, url, **k):
    try:
        r = getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        r = _Xato(e)
    HOLATLAR.append((metod.upper() + " " + url.split("?")[0], r.status_code))
    return r


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


# ── PDF o'quvchi (kutubxonasiz; `tools/test_pdf_matn.py` / `tools/test_pdf_shrift.py` bilan bir xil usul) ─────────────
def _oqim(tana):
    lugat, _, qolgan = tana.partition(b"stream")
    data = qolgan[2:] if qolgan.startswith(b"\r\n") else qolgan[1:]
    m = re.search(rb"/Length\s+(\d+)(?!\s+\d+\s+R)", lugat)
    data = data[:int(m.group(1))] if m else data[:data.rfind(b"endstream")].rstrip(b"\r\n")
    if b"ASCII85Decode" in lugat:
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


_PDF_TOKEN = re.compile(rb"%[^\r\n]*|\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>|\[|\]|/[^\s/\[\]()<>{}%]*|[^\s/\[\]()<>{}%]+", re.S)


def _bt_bloklar(data):
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


def pdf_satrlar(bayt):
    """Har `BT … ET` bloki — bitta satr (sahifa oqimi tartibida)."""
    try:
        obyektlar = {int(n): tana for n, tana in re.findall(rb"(\d+) 0 obj\s*(.*?)\s*endobj", bayt, re.S)}
    except Exception:                      # noqa: BLE001
        return []
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
    for n in sorted(obyektlar):
        tana = obyektlar[n]
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
                satrlar.append("".join(qism).strip())
    return satrlar


def son(matn):
    """«− 36 000 so'm» / «- 36,000 so'm» / «+ 100 000 so'm» / «864 000 so'm» → ishorali butun son (None — son yo'q)."""
    t = (matn or "").replace("−", "-").replace("\xa0", " ")
    m = re.search(r"([-+])?\s*([\d][\d ,]*)", t)
    if not m:
        return None
    try:
        v = int(re.sub(r"[ ,]", "", m.group(2)))
    except ValueError:
        return None
    return -v if m.group(1) == "-" else v


def hisob_blok(satrlar, yorliqlar):
    """PDF satrlaridan hisob bloki: har yorliq (masalan «Buyurtma jami:») dan KEYINGI satr — qiymat. Yorliq bir necha marta
    bo'lsa — oxirgisi (hisob bloki hujjat oxirida). Natija: {yorliq: (matn, son)}; yo'q yorliq — natijada yo'q."""
    natija = {}
    for i, s in enumerate(satrlar):
        for y in yorliqlar:
            if s == y and i + 1 < len(satrlar):
                natija[y] = (satrlar[i + 1], son(satrlar[i + 1]))
    return natija


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "p116_admin", "Parol123!", UserRole.ADMIN, "P116 Admin", company_id=1)
PRJ = [Project(company_id=1, client_name=f"P116 Mijoz {i}", project_name=f"P116 loyiha {i}", total_budget=0, total_paid=0)
       for i in range(12)]
PENO = Inventory(company_id=1, item_name="P116 Penoplast", unit="blok", stock_quantity=100000, price_per_unit=500000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
s.add_all(PRJ + [PENO])
s.commit()
PRJ_ID, PENO_ID = [p.id for p in PRJ], PENO.id
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "p116_admin", "password": "Parol123!"}, follow_redirects=False)
check("0 login", _lr.status_code in (200, 302, 303), _lr.status_code)

_n = [0]


def buyurtma(narx, dona, kelishilgan=None):
    """API orqali buyurtma (har biri o'z loyihasida). Jami = narx × dona (profil 100 sm)."""
    _n[0] += 1
    nom = f"P116_D{_n[0]}"
    r = req(C, "post", "/api/orders", json={
        "project_id": PRJ_ID[_n[0] % len(PRJ_ID)], "order_type": "product", "items": [
            {"name": nom, "category": "profil", "width": 20, "thickness": 10, "length": 100, "quantity": dona,
             "unit_price": narx, "is_coated": False, "penoplast_id": PENO_ID}]})
    d = SessionLocal()
    try:
        oi = d.query(OrderItem).filter(OrderItem.name == nom).order_by(OrderItem.id.desc()).first()
        oid, iid = (oi.order_id, oi.id) if oi is not None else (None, None)
    finally:
        d.close()
    if oid and kelishilgan is not None:
        req(C, "put", f"/api/orders/{oid}/agreed-amount", json={"agreed_amount": kelishilgan})
    return oid, iid, nom, r.status_code


def tolov(oid, summa, kechir=False, ortiqcha=False):
    t = {"order_id": oid, "amount": summa, "payment_method": "naqd"}
    if ortiqcha:
        t["confirm_overpay"] = True
    return req(C, "post", "/api/payments" + ("?write_off_remainder=true" if kechir else ""), json=t)


def yuk(oid, iid, miqdor):
    r = req(C, "post", "/api/deliveries", json={"order_id": oid, "items": [{"order_item_id": iid, "quantity": miqdor}],
                                                 "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd",
                                                 "payment_amount": 0})
    return (js(r) or {}).get("delivery_id") if isinstance(js(r), dict) else None


def qaytar_puli_bilan(oid, iid, nom, summa):
    """Qaytarish (ortiqcha, omborga emas) — birlik narxi API dan, miqdor summa bo'yicha; so'ng «Pul qaytdi»."""
    it = next((x for x in ((js(req(C, "get", f"/api/orders/{oid}")) or {}).get("items") or []) if x.get("id") == iid), {})
    u = float(it.get("refund_price_per_unit") or 0)
    miqdor = round(summa / u, 4) if u else 0
    r = req(C, "post", "/api/returns", json={"order_id": oid, "order_item_id": iid, "item_name": nom, "quantity": miqdor,
                                             "unit": "metr", "reason": "Ortiqcha", "refund_amount": summa,
                                             "to_stock": False, "notes": None, "coating_applied": False})
    rid = (js(r) or {}).get("id") if isinstance(js(r), dict) else None
    rr = req(C, "post", f"/api/returns/{rid}/refund") if rid else None
    return r.status_code, (rr.status_code if rr is not None else None)


def order_api(oid):
    return js(req(C, "get", f"/api/orders/{oid}")) or {}


def db_order(oid):
    d = SessionLocal()
    try:
        o = d.get(Order, oid)
        qk = sum(float(x.refund_agreed_delta or 0) for x in d.query(ReturnItem).filter(
            ReturnItem.order_id == oid, ReturnItem.is_refunded.is_(True), ReturnItem.refunded_at.isnot(None)).all())
        return {"jami": float(o.total_amount or 0), "kelishilgan": o.kelishilgan_summa, "tolangan": float(o.paid_amount or 0),
                "qarz": float(o.debt_amount or 0), "ortiqcha": float(o.ortiqcha_tolov or 0), "kechirilgan": o.kechirilgan,
                "qaytarish": qk}
    finally:
        d.close()


def pdf(url):
    r = req(C, "get", url)
    ok = r.status_code == 200 and (getattr(r, "content", b"") or b"").startswith(b"%PDF")
    return ok, (pdf_satrlar(r.content) if ok else []), r.status_code


YX = ["Buyurtma jami:", "Chegirma:", "Ustama:", "Qaytarish (qaytgan mahsulot):", "Kechirilgan qarz:", "Kelishilgan summa:",
      "To'langan:", "QARZ QOLDI:", "ORTIQCHA TO'LANGAN:", "Berilgan mahsulot:"]
NK = ["Umumiy jami:", "Chegirma:", "Ustama:", "Qaytarish (qaytgan mahsulot):", "Kechirilgan qarz:", "TO'LOV SUMMASI:",
      "Kelishilgan summa:", "To'langan:", "QARZ QOLDI:", "ORTIQCHA TO'LANGAN:"]


def yx_bloki(satrlar):
    """Yuk xati / hisob-kitob varaqasi: chegirma yorlig'i foiz bilan bo'lishi mumkin («Chegirma (10%):») — normallashtiriladi."""
    norm = [re.sub(r"^Chegirma \([^)]*\):$", "Chegirma:", x) for x in satrlar]
    return hisob_blok(norm, YX), [x for x in satrlar if x.startswith("Chegirma")]


def nk_bloki(satrlar):
    norm = [re.sub(r"^Chegirma \([^)]*\):$", "Chegirma:", x) for x in satrlar]
    return hisob_blok(norm, NK)


def qoshiladimi(b, jami_y, kel_y):
    """Blok qatorlari qo'shiladimi: jami − chegirma + ustama − qaytarish − kechirilgan = kelishilgan;
    kelishilgan − to'langan = qarz − ortiqcha. `kel_y` — kelishilgan yorlig'i (yo'q bo'lsa jami olinadi)."""
    def v(y):
        return (b.get(y) or (None, 0))[1] or 0
    jami = v(jami_y)
    kel = v(kel_y) if kel_y in b else jami
    ch, us, qy, ke = abs(v("Chegirma:")), abs(v("Ustama:")), abs(v("Qaytarish (qaytgan mahsulot):")), abs(v("Kechirilgan qarz:"))
    tol, qarz, ort = v("To'langan:"), v("QARZ QOLDI:"), v("ORTIQCHA TO'LANGAN:")
    return (jami - ch + us - qy - ke == kel) and (kel - tol == qarz - ort), {
        "jami": jami, "chegirma": ch, "ustama": us, "qaytarish": qy, "kechirilgan": ke, "kelishilgan": kel,
        "tolangan": tol, "qarz": qarz, "ortiqcha": ort}


def tekshir_hammasi(bol, oid, did, kutil):
    """Bitta buyurtma: API `hisob`, yuk xati, hisob-kitob varaqasi, nakladnoy — kutilgan butun so'mlar (`kutil`)."""
    o = order_api(oid)
    h = o.get("hisob") or {}
    k = h.get("korinish") or {}
    kalitlar = [q.get("kalit") for q in (h.get("qatorlar") or [])]
    check(f"{bol}1 API `hisob.korinish` — kutilgan qatorlar ({kutil})",
          all(k.get(x) == kutil.get(x, 0) for x in ("jami", "chegirma", "ustama", "qaytarish", "kechirilgan", "kelishilgan",
                                                     "tolangan", "qarz", "ortiqcha")), (k, kalitlar))
    check(f"{bol}2 API qatorlar qo'shiladi (jami − chegirma + ustama − qaytarish − kechirilgan = kelishilgan; "
          f"kelishilgan − to'langan = qarz − ortiqcha) va qarz = `debt_amount` qoidasi",
          k and k.get("jami", 0) - k.get("chegirma", 0) + k.get("ustama", 0) - k.get("qaytarish", 0) - k.get("kechirilgan", 0)
          == k.get("kelishilgan") and k.get("kelishilgan", 0) - k.get("tolangan", 0) == k.get("qarz", 0) - k.get("ortiqcha", 0)
          and abs(float(h.get("qarz", -1)) - float(o.get("debt_amount", -2))) < 0.005, (k, o.get("debt_amount")))
    for nom, url in (("yuk xati", f"/api/deliveries/{did}/pdf"), ("hisob-kitob varaqasi", f"/api/orders/{oid}/summary-pdf")):
        ok, st, kod = pdf(url)
        b, cheg = yx_bloki(st)
        q, qiy = qoshiladimi(b, "Buyurtma jami:", "Kelishilgan summa:")
        check(f"{bol}3 {nom}: PDF 200, qatorlar qo'shiladi ({qiy})", ok and b and q, (kod, b))
        check(f"{bol}4 {nom}: qiymatlar = kutilgan (qaytarish {kutil.get('qaytarish', 0)}, kechirilgan "
              f"{kutil.get('kechirilgan', 0)}, chegirma {kutil.get('chegirma', 0)}, ustama {kutil.get('ustama', 0)}, "
              f"qarz {kutil.get('qarz', 0)}, ortiqcha {kutil.get('ortiqcha', 0)})",
              ok and all(qiy.get(x) == kutil.get(x, 0) for x in ("jami", "chegirma", "ustama", "qaytarish", "kechirilgan",
                                                                  "kelishilgan", "tolangan", "qarz", "ortiqcha")), (qiy, b))
        _bel = [(y, (b.get(y) or ("", None))[1]) for y in ("Chegirma:", "Qaytarish (qaytgan mahsulot):", "Kechirilgan qarz:",
                                                           "Ustama:") if y in b]
        check(f"{bol}8 {nom}: ayiriladigan qatorlar MINUS bilan, ustama PLYUS bilan (belgi yo'qolmagan)",
              ok and all((v or 0) < 0 for y, v in _bel if y != "Ustama:")
              and all((v or 0) > 0 and b["Ustama:"][0].lstrip().startswith("+") for y, v in _bel if y == "Ustama:"),
              _bel)
        if nom == "hisob-kitob varaqasi":
            check(f"{bol}5 hisob-kitob varaqasi: «Berilgan mahsulot:» pul hisobi orasida YO'Q (jadvaldagi «JAMI BERILGAN "
                  f"MAHSULOT:» — bor)", ok and "Berilgan mahsulot:" not in b and "JAMI BERILGAN MAHSULOT:" in st, st[-25:])
    ok, st, kod = pdf(f"/api/orders/{oid}/pdf")
    b = nk_bloki(st)
    q, qiy = qoshiladimi(b, "Umumiy jami:", "TO'LOV SUMMASI:")
    check(f"{bol}6 nakladnoy: PDF 200, qatorlar qo'shiladi, «TO'LOV SUMMASI» = kelishilgan ({qiy})",
          ok and b and q and qiy.get("kelishilgan") == kutil.get("kelishilgan"), (kod, b))
    check(f"{bol}7 nakladnoy: qaytarish va kechirilgan qarz «Chegirma» EMAS (chegirma = faqat narx chegirmasi "
          f"{kutil.get('chegirma', 0)})",
          ok and qiy.get("chegirma") == kutil.get("chegirma", 0) and qiy.get("qaytarish") == kutil.get("qaytarish", 0)
          and qiy.get("kechirilgan") == kutil.get("kechirilgan", 0) and qiy.get("ustama") == kutil.get("ustama", 0), (qiy, b))
    return h


# ══════════════════════════════════════════════════════════════
section("A. Audit holati — chegirmasiz, 36 000 qaytarish, 600 000 to'langan")
# ══════════════════════════════════════════════════════════════
oA, iA, nA, stA = buyurtma(50000, 18)
dA = yuk(oA, iA, 10) if oA else None
_tA = tolov(oA, 600000) if oA else None
_qA = qaytar_puli_bilan(oA, iA, nA, 36000) if oA else (None, None)
_bA = db_order(oA) if oA else {}
check("A0 fikstura: jami 900 000, qaytarish 36 000 (qarzdan), kelishilgan 864 000, to'langan 600 000, qarz 264 000",
      stA == 200 and dA and _tA is not None and _tA.status_code == 200 and _qA == (200, 200)
      and abs(_bA.get("jami", 0) - 900000) < 0.01 and abs(_bA.get("qaytarish", 0) - 36000) < 0.01
      and abs(_bA.get("kelishilgan", 0) - 864000) < 0.01 and abs(_bA.get("qarz", 0) - 264000) < 0.01, (stA, dA, _qA, _bA))
tekshir_hammasi("A", oA, dA, {"jami": 900000, "qaytarish": 36000, "kelishilgan": 864000, "tolangan": 600000, "qarz": 264000})

# ══════════════════════════════════════════════════════════════
section("B. Chegirma 10 % + to'lovda kechirilgan qarz 5 000")
# ══════════════════════════════════════════════════════════════
oB, iB, nB, stB = buyurtma(50000, 20, kelishilgan=900000)
dB = yuk(oB, iB, 5) if oB else None
_tB = tolov(oB, 895000, kechir=True) if oB else None
_bB = db_order(oB) if oB else {}
check("B0 fikstura: jami 1 000 000, kelishilgan 895 000 (chegirma 100 000 + kechirilgan 5 000), to'langan 895 000",
      stB == 200 and dB and _tB is not None and _tB.status_code == 200 and abs(_bB.get("kechirilgan", 0) - 5000) < 0.01
      and abs(_bB.get("kelishilgan", 0) - 895000) < 0.01 and _bB.get("qarz") == 0, (_bB, getattr(_tB, "text", "")[:200]))
_hB = tekshir_hammasi("B", oB, dB, {"jami": 1000000, "chegirma": 100000, "kechirilgan": 5000, "kelishilgan": 895000,
                                    "tolangan": 895000, "qarz": 0})
check("B8 chegirma foizi — faqat narx chegirmasidan (10 %), kechirilgan qarz kirmaydi",
      abs(float(_hB.get("chegirma_foiz", 0)) - 10.0) < 0.001, _hB.get("chegirma_foiz"))
ok, st, _ = pdf(f"/api/deliveries/{dB}/pdf")
check("B9 yuk xatida chegirma yorlig'i foiz bilan: «Chegirma (10%):»", ok and "Chegirma (10%):" in st, [x for x in st if "hegirma" in x])

# ══════════════════════════════════════════════════════════════
section("C. Ustama — kelishilgan jamidan katta")
# ══════════════════════════════════════════════════════════════
oC, iC, nC, stC = buyurtma(50000, 20, kelishilgan=1100000)
dC = yuk(oC, iC, 3) if oC else None
_bC = db_order(oC) if oC else {}
check("C0 fikstura: jami 1 000 000, kelishilgan 1 100 000, to'lov yo'q", stC == 200 and dC
      and abs(_bC.get("kelishilgan", 0) - 1100000) < 0.01, _bC)
tekshir_hammasi("C", oC, dC, {"jami": 1000000, "ustama": 100000, "kelishilgan": 1100000, "tolangan": 0, "qarz": 1100000})

# ══════════════════════════════════════════════════════════════
section("D. Ortiqcha to'langan — qarz o'rniga «ORTIQCHA TO'LANGAN»")
# ══════════════════════════════════════════════════════════════
oD, iD, nD, stD = buyurtma(50000, 10)
dD = yuk(oD, iD, 10) if oD else None
_tD = tolov(oD, 520000, ortiqcha=True) if oD else None
_bD = db_order(oD) if oD else {}
check("D0 fikstura: jami 500 000, to'langan 520 000 (tasdiqlangan ortiqcha)", stD == 200 and dD and _tD is not None
      and _tD.status_code == 200 and abs(_bD.get("ortiqcha", 0) - 20000) < 0.01, (_bD, getattr(_tD, "text", "")[:200]))
tekshir_hammasi("D", oD, dD, {"jami": 500000, "kelishilgan": 500000, "tolangan": 520000, "ortiqcha": 20000})
ok, st, _ = pdf(f"/api/orders/{oD}/summary-pdf")
b, _c = yx_bloki(st)
check("D8 ortiqcha to'langanda «QARZ QOLDI» qatori yo'q (ilgari «0» — 500 000 − 520 000 ≠ 0)",
      ok and "QARZ QOLDI:" not in b and "ORTIQCHA TO'LANGAN:" in b, b)

# ══════════════════════════════════════════════════════════════
section("E. Tiyinli summalar — ko'rsatilgan butun so'mlar ham qo'shiladi")
# ══════════════════════════════════════════════════════════════
oE, iE, nE, stE = buyurtma(33333.33, 3, kelishilgan=89999.7)
dE = yuk(oE, iE, 1) if oE else None
_tE = tolov(oE, 40000.5) if oE else None
_bE = db_order(oE) if oE else {}
check("E0 fikstura: jami 99 999.99, kelishilgan 89 999.70, to'langan 40 000.50", stE == 200 and dE
      and abs(_bE.get("jami", 0) - 99999.99) < 0.001 and abs(_bE.get("kelishilgan", 0) - 89999.7) < 0.001
      and abs(_bE.get("tolangan", 0) - 40000.5) < 0.001, (_bE, getattr(_tE, "text", "")[:200]))
# kutilgan ko'rinish (HALF_UP): jami 100 000, to'langan 40 001, kelishilgan 90 000, qarz 49 999, chegirma 10 000
tekshir_hammasi("E", oE, dE, {"jami": 100000, "chegirma": 10000, "kelishilgan": 90000, "tolangan": 40001, "qarz": 49999})

# ══════════════════════════════════════════════════════════════
section("X. Xatolar")
# ══════════════════════════════════════════════════════════════
_5xx = [x for x in HOLATLAR if x[1] >= 500]
check("X1 API / PDF 5xx yo'q", not _5xx, _5xx[:5])

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
