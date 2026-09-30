#!/usr/bin/env python3
"""
test_yonalish_natija.py — kech118 (egasi QARORI 2026-09-30 15:23, tugmali javoblar 15:30 — QAYTA SO'RALMAYDI):
YO'NALISHLAR BO'YICHA MOLIYAVIY NATIJA — umumiy xarajat TAQSIMLANMAYDI, oyliklar alohida, oxirida natija +/−, DAVR tanlash
(bir necha oy), oldingi davr bilan solishtirish, xarajatlar tarkibi. Server: `services.calculate_split_profit_report`
(`gacha_yil`, `gacha_oy`, `solishtirish`), `yonalish_davr_oylari`, `yonalish_oldingi_davr`, `yonalish_davr_nomi`,
`/api/finance/yonalishlar`, `/api/finance/split-profit-pdf`.

NIMA UCHUN KERAK
  Egasi: «Rasxodlarni alohida yozamiz, taqsimlamaymiz. Oyliklar alohida. Oxirida + va −.» Ilgari (kech114 qarori) umumiy
  xarajatlar yo'nalishlar DAROMAD ULUSHIGA bo'linardi — yo'nalish «sof foydasi» o'ziga tegishli bo'lmagan arenda / umumiy
  hodim bilan kamayardi. Endi: yo'nalish natijasi = daromad − tannarx − o'z oyliklari − o'z xarajatlari; umumiy (yo'nalishsiz)
  oylik va xarajatlar — faqat «Jami»; Jami natija = Moliya sof foydasi (AYNAN).
TALAB (har biri o'lchanadi, oylik hisobotdan mustaqil yig'ilgan qiymatlar bilan):
  P  davr — noto'g'ri davr 400 (o'zbekcha sabab), 36 oydan ortiq — 400; nomi («Iyul – Sentabr 2026», «Noyabr 2025 –
     Yanvar 2026»);
  B  bir oy: ustun D − T − O − X = N, oylik — yo'nalishli hodimning AYNAN oyligi, umumiy oylik — yo'nalishsiz hodimniki,
     umumiy xarajat — yo'nalishsiz xarajatlar, Jami natija = Moliya sof foydasi, taqsim yo'q (umumiy xarajat ustunlarga
     tushmaydi);
  K  bir necha oy: Jami = oylik hisobotlar YIG'INDISI (daromad, tannarx, natija), ustunlar = oylar ustunlari yig'indisi;
  S  oldingi davr: bir oy — o'tgan oy, chorak — o'tgan chorak, yanvardan — o'tgan yilning shu oylari; o'zgarish foizi;
  T  xarajatlar tarkibi — oylik + turlar, yig'indisi = Jami oylik + xarajat, foizlar ~100, kamayish tartibida;
  F  PDF — shu davr bilan (fayl nomi, sarlavha, oldingi davr qatori, NATIJA JAMI = hisobot);
  Z  korxona chegarasi (B korxona davr hisobotida A ning summalari yo'q), huquq (omborchi — 403).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga qarshi QULAMAYDI (yangi nomlar — xavfsiz olinadi).
ISHLATISH: python3 tools/test_yonalish_natija.py
"""
import os
import re
import sys
import zlib
import base64
import tempfile
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "yonalish_natija_test"
_T = tempfile.mkdtemp(prefix="yonnat_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'yonalish_natija_test.db')}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import services                                    # noqa: E402
from database import SessionLocal, tashkent_date, tashkent_oy_oraligi   # noqa: E402
from models import (UserRole, Project, ProjectStatus, Order, OrderItem, OrderType, OrderStatus,   # noqa: E402
                    ExpenseTransaction, TransportExpense)
from production_models import Company, ProductType   # noqa: E402
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
        print(f"  ✗ {label}   {str(detail)[:900]}")


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
        return getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        return _Xato(e)


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


def xavfsiz(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:                 # noqa: BLE001
        return {"XATO": f"{type(e).__name__}: {e}"}


def yaxlit(x, birlik=1):
    return int((Decimal(repr(float(x))) * birlik).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def oy_siljit(y, o, n):
    k = y * 12 + o - 1 + n
    return k // 12, k % 12 + 1


# ── PDF matni (kutubxonasiz; test_a116_pdf / test_a117_yonalish bilan bir usul) ─────────────────────────────────────────────────────
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
    t = (matn or "").replace("−", "-").replace("\xa0", " ")
    m = re.fullmatch(r"\s*([-+])?\s*(\d[\d ]*)(?:\s*so'm)?\s*", t)
    if not m:
        return None
    v = int(m.group(2).replace(" ", ""))
    return -v if m.group(1) == "-" else v


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — uch oy (M−2, M−1, M): buyurtmalar, xarajatlar, hodimlar
# ══════════════════════════════════════════════════════════════
BUGUN = tashkent_date()
YIL, OY = BUGUN.year, BUGUN.month
OYLAR3 = [oy_siljit(YIL, OY, -2), oy_siljit(YIL, OY, -1), (YIL, OY)]
_OYN = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]


def oy_sana(y, o, kun=3):
    boshi, _ox = tashkent_oy_oraligi(y, o)
    return boshi + timedelta(days=kun - 1, hours=4)


s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="YN B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "yn_admin", "Parol123!", UserRole.ADMIN, "YN Admin", company_id=1)
    auth.create_user(s, "yn_ombor", "Parol123!", UserRole.WAREHOUSE, "YN Omborchi", company_id=1)
    auth.create_user(s, "yn_b_admin", "Parol123!", UserRole.ADMIN, "YN B Admin", company_id=2)
PRJ = Project(company_id=1, project_number="PRJ-YN", client_name="YN mijoz", project_name="YN loyiha",
              status=ProjectStatus.DRAFT)
s.add(PRJ)
s.commit()
PRJ_ID = PRJ.id
s.close()

CA = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
CW = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
CB = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_la = req(CA, "post", "/login", data={"username": "yn_admin", "password": "Parol123!"}, follow_redirects=False)
_lw = req(CW, "post", "/login", data={"username": "yn_ombor", "password": "Parol123!"}, follow_redirects=False)
_lb = req(CB, "post", "/login", data={"username": "yn_b_admin", "password": "Parol123!"}, follow_redirects=False)
if _la.status_code != 302 or _lb.status_code != 302:
    print("LOGIN BO'LMADI", _la.status_code, _lb.status_code)
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_ra = js(req(CA, "get", "/api/yonalishlar")) or []
AID = next((y.get("id") for y in _ra if isinstance(y, dict) and y.get("asosiy")), None)
TID = (js(req(CA, "post", "/api/yonalishlar", json={"nom": "Travertin"})) or {}).get("id")
s = SessionLocal()
PT = ProductType(company_id=1, name="YN Travertin turi", unit="dona", input_template="quantity_only",
                 pricing_formula="unit_based", **({"yonalish_id": TID} if hasattr(ProductType, "yonalish_id") else {}))
# yo'nalishi BIRIKTIRILMAGAN tur — «Belgilanmagan» ustuni (foydada / zararda sonida hisoblanmaydi — mutatsiya Y19)
PT_B = ProductType(company_id=1, name="YN Belgisiz tur", unit="dona", input_template="quantity_only", pricing_formula="unit_based")
s.add_all([PT, PT_B])
s.commit()
PT_ID, PT_B_ID = PT.id, PT_B.id
# Buyurtmalar: har oyda loy sotish (asosiy — Penoplast) va MRP (Travertin)
DAROMAD_KUT = {}
for i, (y, o) in enumerate(OYLAR3):
    asosiy, trav = 100_000 * (i + 1), 150_000 * i
    DAROMAD_KUT[(y, o)] = (asosiy, trav)
    ordr = Order(company_id=1, order_number=f"YN-{y}{o:02d}", project_id=PRJ_ID, order_type=OrderType.PRODUCT,
                 total_amount=asosiy + trav, agreed_amount=asosiy + trav, status=OrderStatus.READY,
                 completed_at=oy_sana(y, o, 5))
    s.add(ordr)
    s.flush()
    s.add(OrderItem(company_id=1, order_id=ordr.id, name=f"YN loy {o}", category="loy_sotish", quantity=1,
                    unit_price=asosiy, total_price=asosiy))
    if trav:
        s.add(OrderItem(company_id=1, order_id=ordr.id, name=f"YN travertin {o}", category="mrp_product", quantity=1,
                        unit_price=trav, total_price=trav, product_type_id=PT_ID))
s.commit()
_ob = Order(company_id=1, order_number="YN-BELG", project_id=PRJ_ID, order_type=OrderType.PRODUCT, total_amount=80_000,
            agreed_amount=80_000, status=OrderStatus.READY, completed_at=oy_sana(YIL, OY, 6))
s.add(_ob)
s.flush()
s.add(OrderItem(company_id=1, order_id=_ob.id, name="YN belgisiz", category="mrp_product", quantity=1, unit_price=80_000,
                total_price=80_000, product_type_id=PT_B_ID))
# katta umumiy transport (900 000) — xarajatlar tarkibi tartibi «hodimlar, doimiy, qo'shimcha, transport…» dan farq qiladi
# (kamayish tartibi tekshiriladi — mutatsiya Y18)
s.add(TransportExpense(company_id=1, amount=900_000, expense_date=oy_sana(YIL, OY, 7)))
s.commit()
# Xarajatlar: joriy oy — umumiy arenda 500 000, Travertin «Boshqa» 120 000, Penoplast transport-yo'q «Boshqa» 33 333,33;
# o'tgan oy — umumiy reklama 70 000, Travertin «Boshqa» 45 000
_kw = {"yonalish_id": TID} if hasattr(ExpenseTransaction, "yonalish_id") else {}
_kwa = {"yonalish_id": AID} if hasattr(ExpenseTransaction, "yonalish_id") else {}
s.add_all([ExpenseTransaction(company_id=1, date=oy_sana(YIL, OY, 2), category="arenda", amount=500_000),
           ExpenseTransaction(company_id=1, date=oy_sana(YIL, OY, 2), category="boshqa", amount=120_000, **_kw),
           ExpenseTransaction(company_id=1, date=oy_sana(YIL, OY, 2), category="boshqa", amount=33_333.33, **_kwa),
           ExpenseTransaction(company_id=1, date=oy_sana(*OYLAR3[1], 4), category="reklama", amount=70_000),
           # o'tgan oyda ham yo'nalishli xarajat — davr yig'indisi har oyning ustunini QO'SHISHI tekshiriladi (mutatsiya Y8)
           ExpenseTransaction(company_id=1, date=oy_sana(*OYLAR3[1], 6), category="boshqa", amount=45_000, **_kw)])
s.commit()
s.close()
_e1 = req(CA, "post", "/api/employees", json={"name": "YN Travertin hodimi", "pay_type": "fixed", "fixed_amount": 1_000_000,
                                              "yonalish_id": TID})
_e2 = req(CA, "post", "/api/employees", json={"name": "YN Umumiy hodim", "pay_type": "fixed", "fixed_amount": 400_000,
                                              "yonalish_id": None})
E1, E2 = (js(_e1) or {}).get("id"), (js(_e2) or {}).get("id")


def rep(y, o, cid=1):
    d = SessionLocal()
    try:
        return xavfsiz(services.get_monthly_report, d, y, o, company_id=cid)
    finally:
        d.close()


def split(y, o, cid=1, **k):
    d = SessionLocal()
    try:
        return xavfsiz(services.calculate_split_profit_report, d, y, o, company_id=cid, **k)
    finally:
        d.close()


def hodim_oyligi(r, eid):
    return sum(float(b.get("amount") or 0) for b in (r.get("hodimlar_breakdown") or []) if b.get("employee_id") == eid)


def daromad_of(r):
    t = r.get("sof_foyda_tarkibi") or {}
    return float(t.get("daromad_buyurtmalar", 0)) + float(t.get("daromad_tm", 0))


# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. Davr — tekshiruv va nomi")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
_p = {
    "gacha_oldin": req(CA, "get", "/api/finance/yonalishlar", params={"year": YIL, "month": OY, "gacha_yil": YIL - 1,
                                                                      "gacha_oy": OY}),
    "37_oy": req(CA, "get", "/api/finance/yonalishlar", params={"year": YIL - 3, "month": OY, "gacha_yil": YIL,
                                                                "gacha_oy": OY}),
    "13_oy": req(CA, "get", "/api/finance/yonalishlar", params={"year": YIL, "month": 1, "gacha_yil": YIL, "gacha_oy": 13}),
    "yil_1999": req(CA, "get", "/api/finance/yonalishlar", params={"year": 1999, "month": 1}),
    "pdf_teskari": req(CA, "get", "/api/finance/split-profit-pdf", params={"year": YIL, "month": OY, "gacha_yil": YIL - 1,
                                                                          "gacha_oy": 1}),
}
check("P1 noto'g'ri davr — 400 va o'zbekcha sabab: oxiri boshidan oldin, 36 oydan ortiq, 13-oy, 1999-yil; PDF ham",
      [r.status_code for r in _p.values()] == [400] * 5
      and "oldin" in js(_p["gacha_oldin"]).get("detail", "") and "36" in js(_p["37_oy"]).get("detail", "")
      and "Oy 1–12" in js(_p["13_oy"]).get("detail", ""),
      {k: (r.status_code, r.text[:120]) for k, r in _p.items()})
_ok36 = req(CA, "get", "/api/finance/yonalishlar", params={"year": YIL - 3, "month": OY % 12 + 1 if OY < 12 else 1,
                                                          "gacha_yil": YIL if OY < 12 else YIL, "gacha_oy": OY})
_ok36_oy = (js(_ok36).get("davr") or {}).get("oylar")
check("P2 36 oylik davr — 200 (chegara), `davr.oylar` = 36", _ok36.status_code == 200 and _ok36_oy == 36,
      [_ok36.status_code, _ok36_oy, _ok36.text[:200]])
_nomlar = [services.yonalish_davr_nomi(services.yonalish_davr_oylari(*a)) for a in
           ((2026, 9, None, None), (2026, 7, 2026, 9), (2025, 11, 2026, 1))] \
    if hasattr(services, "yonalish_davr_nomi") else []
check("P3 davr nomi: «Sentabr 2026», «Iyul – Sentabr 2026», «Noyabr 2025 – Yanvar 2026»",
      _nomlar == ["Sentabr 2026", "Iyul – Sentabr 2026", "Noyabr 2025 – Yanvar 2026"], _nomlar)
_old = [services.yonalish_oldingi_davr(services.yonalish_davr_oylari(*a)) for a in
        ((2026, 9, None, None), (2026, 7, 2026, 9), (2026, 1, 2026, 9), (2026, 1, None, None), (2025, 11, 2026, 2))] \
    if hasattr(services, "yonalish_oldingi_davr") else []
check("P4 oldingi davr: oy → o'tgan oy; chorak → o'tgan chorak; yanvardan → o'tgan yilning shu oylari; yanvar bir oy → "
      "dekabr; Noyabr–Fevral → Iyul–Oktabr",
      _old == [[(2026, 8)], [(2026, 4), (2026, 5), (2026, 6)], [(2025, m) for m in range(1, 10)], [(2025, 12)],
               [(2025, 7), (2025, 8), (2025, 9), (2025, 10)]], _old)

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Bir oy — taqsim yo'q, oyliklar alohida, Jami = Moliya")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
R = rep(YIL, OY)
SP = split(YIL, OY, solishtirish=True)
_api = req(CA, "get", "/api/finance/yonalishlar", params={"year": YIL, "month": OY})
YL = {y.get("nom"): y for y in (SP.get("yonalishlar") or [])} if isinstance(SP, dict) else {}
J = SP.get("jami", {}) if isinstance(SP, dict) else {}
check("B0 API 200 = xizmat (solishtirish bilan); ustunlar Penoplast, Travertin; davr nomi — joriy oy",
      _api.status_code == 200 and js(_api).get("jami") == J and list(YL)[:2] == ["Penoplast", "Travertin"]
      and (SP.get("davr") or {}).get("nom") == f"{_OYN[OY - 1]} {YIL}" and (SP.get("davr") or {}).get("oylar") == 1,
      [_api.status_code, list(YL), SP.get("davr") if isinstance(SP, dict) else SP])
_som = [y["som"] for y in SP.get("yonalishlar", [])] if isinstance(SP, dict) else []
check("B1 har ustunda D − T − O − X = N; xarajat qismlari yig'indisi = X",
      _som and all(x["daromad"] - x["tannarx"] - x["oylik"] - x["xarajat"] == x["natija"]
                   and sum(x["xarajat_qismlari"].values()) == x["xarajat"] for x in _som), _som)
_e1o, _e2o = hodim_oyligi(R, E1), hodim_oyligi(R, E2)
check("B2 OYLIK alohida: Travertin ustunida — yo'nalishli hodimning AYNAN oyligi; Penoplast — 0; yo'nalishsiz hodim oyligi — "
      "faqat Jami (`umumiy_oylik`)",
      _e1o > 0 and _e2o > 0 and YL.get("Travertin", {}).get("som", {}).get("oylik") == yaxlit(_e1o)
      and YL.get("Penoplast", {}).get("som", {}).get("oylik") == 0 and J.get("umumiy_oylik") == yaxlit(_e2o)
      and J.get("oylik") == yaxlit(_e1o) + yaxlit(_e2o),
      [_e1o, _e2o, {k: v.get("som", {}).get("oylik") for k, v in YL.items()}, J.get("umumiy_oylik"), J.get("oylik")])
check("B3 XARAJAT taqsimlanmaydi: Travertin — faqat o'z «Boshqa» 120 000, Penoplast — o'z 33 333 (so'mda); umumiy arenda "
      "500 000 — faqat Jami (`umumiy_qismlari.doimiy`), ustunlarda yo'q",
      YL.get("Travertin", {}).get("som", {}).get("xarajat_qismlari", {}).get("qoshimcha") == 120_000
      and YL.get("Penoplast", {}).get("som", {}).get("xarajat_qismlari", {}).get("qoshimcha") == 33_333
      and all(y["som"]["xarajat_qismlari"].get("doimiy", 0) == 0 for y in SP.get("yonalishlar", []))
      and (J.get("umumiy_qismlari") or {}).get("doimiy") == 500_000,
      [{k: v.get("som", {}).get("xarajat_qismlari") for k, v in YL.items()}, J.get("umumiy_qismlari")])
_dk = DAROMAD_KUT[(YIL, OY)]
check("B4 daromad yo'nalishga aniq: Penoplast (loy sotish) 300 000, Travertin (MRP turi) 300 000",
      YL.get("Penoplast", {}).get("som", {}).get("daromad") == _dk[0]
      and YL.get("Travertin", {}).get("som", {}).get("daromad") == _dk[1], [_dk, {k: v.get("som", {}).get("daromad")
                                                                            for k, v in YL.items()}])
_sof = float(R.get("sof_foyda", 0)) if isinstance(R, dict) else 0.0
check("B5 Jami: ΣN − umumiy oylik − umumiy xarajat = natija = Moliya sof foydasi (so'm) = moliya_sof_foyda; tiyinda ham",
      isinstance(SP, dict) and sum(x["natija"] for x in _som) - J.get("umumiy_oylik", 0) - J.get("umumiy_xarajat", 0)
      == J.get("natija") == yaxlit(_sof) == SP.get("moliya_sof_foyda")
      and sum(yaxlit(y["aniq"]["natija"], 100) for y in SP["yonalishlar"])
      - yaxlit((SP.get("jami_aniq") or {}).get("umumiy_oylik", 0), 100)
      - yaxlit((SP.get("jami_aniq") or {}).get("umumiy_xarajat", 0), 100) == yaxlit(_sof, 100),
      [J, _sof])
check("B6 rentabellik = natija / daromad (1 xona); foydada / zararda soni ustunlar ishorasidan",
      all(y.get("rentabellik") == (round(y["som"]["natija"] / y["som"]["daromad"] * 100, 1) if y["som"]["daromad"] else None)
          for y in SP.get("yonalishlar", []))
      and SP.get("foydada_soni") == sum(1 for y in SP["yonalishlar"] if not y["belgilanmagan"] and y["som"]["natija"] > 0)
      and SP.get("zararda_soni") == sum(1 for y in SP["yonalishlar"] if not y["belgilanmagan"] and y["som"]["natija"] < 0)
      and SP.get("rentabellik") == (round(J["natija"] / J["daromad"] * 100, 1) if J.get("daromad") else None),
      [[(y["nom"], y.get("rentabellik")) for y in SP.get("yonalishlar", [])], SP.get("foydada_soni"), SP.get("zararda_soni")])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Bir necha oy — oylar yig'indisi")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
(_y0, _o0), (_y2, _o2) = OYLAR3[0], OYLAR3[-1]
SK = split(_y0, _o0, gacha_yil=_y2, gacha_oy=_o2, solishtirish=True)
RK = [rep(y, o) for y, o in OYLAR3]
SO = [split(y, o) for y, o in OYLAR3]
JK = SK.get("jami", {}) if isinstance(SK, dict) else {}
_sof3 = sum(float(r.get("sof_foyda", 0)) for r in RK)
check("K1 3 oy: `davr.oylar` 3, nomi; Jami natija = 3 oy sof foydasi yig'indisi (so'm va tiyin); daromad = yig'indi",
      isinstance(SK, dict) and (SK.get("davr") or {}).get("oylar") == 3
      and (SK.get("davr") or {}).get("nom") == services.yonalish_davr_nomi(OYLAR3)
      and JK.get("natija") == yaxlit(_sof3) == SK.get("moliya_sof_foyda")
      and yaxlit((SK.get("jami_aniq") or {}).get("natija", 0), 100) == yaxlit(_sof3, 100)
      and JK.get("daromad") == yaxlit(sum(daromad_of(r) for r in RK)),
      [SK.get("davr") if isinstance(SK, dict) else SK, JK, _sof3])
_yk = {y["nom"]: y["som"] for y in (SK.get("yonalishlar") or [])} if isinstance(SK, dict) else {}
_yo = [{y["nom"]: y["som"] for y in (s_.get("yonalishlar") or [])} for s_ in SO if isinstance(s_, dict)]
check("K2 ustunlar = oylar ustunlari yig'indisi (daromad, tannarx, oylik, xarajat — har biri ±1 so'm yaxlitlash)",
      len(_yo) == 3 and all(abs(_yk[n][k] - sum(m.get(n, {}).get(k, 0) for m in _yo)) <= 2 for n in _yk
                            for k in ("daromad", "tannarx", "oylik", "xarajat")),
      [_yk, _yo])
check("K3 3 oylik Jami: umumiy oylik va umumiy xarajat — oylar umumiy qismlari yig'indisi (±2 so'm); o'tgan oy reklamasi "
      "70 000 — Jami «Qo'shimcha» ichida, ustunlarda emas; Travertin «Boshqa» = 120 000 + 45 000 (ikki oy)",
      abs(JK.get("umumiy_oylik", 0) - sum((s_.get("jami") or {}).get("umumiy_oylik", 0) for s_ in SO)) <= 2
      and abs(JK.get("umumiy_xarajat", 0) - sum((s_.get("jami") or {}).get("umumiy_xarajat", 0) for s_ in SO)) <= 2
      and (JK.get("umumiy_qismlari") or {}).get("qoshimcha", 0) >= 70_000
      and _yk.get("Travertin", {}).get("xarajat_qismlari", {}).get("qoshimcha") == 165_000
      and _yk.get("Penoplast", {}).get("xarajat_qismlari", {}).get("qoshimcha") == 33_333,
      [JK.get("umumiy_oylik"), JK.get("umumiy_xarajat"), JK.get("umumiy_qismlari"), {k: v.get("xarajat_qismlari")
                                                                                        for k, v in _yk.items()}])
_ak = req(CA, "get", "/api/finance/yonalishlar", params={"year": _y0, "month": _o0, "gacha_yil": _y2, "gacha_oy": _o2})
check("K4 API davr bilan — xizmat natijasi bilan AYNAN (Jami va ustunlar)",
      _ak.status_code == 200 and js(_ak).get("jami") == JK and js(_ak).get("yonalishlar") == SK.get("yonalishlar"),
      [_ak.status_code, _ak.text[:300]])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Oldingi davr bilan solishtirish")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
_Rp = rep(*OYLAR3[1])
_old = SP.get("oldingi") or {} if isinstance(SP, dict) else {}
_oz = SP.get("ozgarish") or {} if isinstance(SP, dict) else {}
_dp, _dc = yaxlit(daromad_of(_Rp)), J.get("daromad", 0)
_xp = yaxlit(daromad_of(_Rp) - float(_Rp.get("sof_foyda", 0)))
_xc = J.get("tannarx", 0) + J.get("oylik", 0) + J.get("xarajat", 0)
check("S1 bir oy → o'tgan oy: davr nomi, daromad / xarajat (tannarx bilan) / natija — o'tgan oy hisobotidan",
      (_old.get("davr") or {}).get("nom") == f"{_OYN[OYLAR3[1][1] - 1]} {OYLAR3[1][0]}" and _old.get("daromad") == _dp
      and _old.get("natija") == yaxlit(float(_Rp.get("sof_foyda", 0))) and _old.get("xarajat") == _xp,
      [_old, _dp, _xp])
_of = getattr(services, "_ozgarish_foiz", None)
check("S2b o'zgarish foizi manfiy oldingida — |oldingi| ga bo'linadi: −100 → −50 = +50%, −100 → +100 = +200%, 100 → 50 = −50%, "
      "0 → 5 = None", _of and [_of(-50, -100), _of(100, -100), _of(50, 100), _of(5, 0)] == [50.0, 200.0, -50.0, None],
      [_of(-50, -100), _of(100, -100), _of(50, 100), _of(5, 0)] if _of else None)
check("S2 o'zgarish foizi: (joriy − oldingi) / |oldingi| × 100, 1 xona; oldingi 0 — None",
      _oz.get("daromad") == (round((_dc - _dp) / abs(_dp) * 100, 1) if _dp else None)
      and _oz.get("xarajat") == (round((_xc - _xp) / abs(_xp) * 100, 1) if _xp else None)
      and _oz.get("natija") == (round((J.get("natija", 0) - _old.get("natija", 0)) / abs(_old.get("natija", 0)) * 100, 1)
                                if _old.get("natija") else None),
      [_oz, _dc, _dp, _xc, _xp])
_oldk = SK.get("oldingi") or {} if isinstance(SK, dict) else {}
_k_old = services.yonalish_oldingi_davr(OYLAR3) if hasattr(services, "yonalish_oldingi_davr") else []
_sof_old = sum(float(rep(y, o).get("sof_foyda", 0)) for y, o in _k_old)
check("S3 3 oylik davr → oldingi 3 oy (yig'indi natija); yanvardan boshlanmagan",
      (_oldk.get("davr") or {}).get("dan") == f"{_k_old[0][0]}-{_k_old[0][1]:02d}" and _oldk.get("natija") == yaxlit(_sof_old),
      [_oldk, _k_old, _sof_old])
SY = split(YIL, 1, gacha_yil=YIL, gacha_oy=OY, solishtirish=True) if OY > 1 else {"oldingi": {"davr": {"dan": f"{YIL - 1}-12"}}}
check("S4 yanvardan (yil boshidan) → o'tgan yilning SHU oylari",
      ((SY.get("oldingi") or {}).get("davr") or {}).get("dan") == (f"{YIL - 1}-01" if OY > 1 else f"{YIL - 1}-12")
      and (((SY.get("oldingi") or {}).get("davr") or {}).get("gacha") == f"{YIL - 1}-{OY:02d}" if OY > 1 else True),
      SY.get("oldingi") if isinstance(SY, dict) else SY)

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Xarajatlar tarkibi (doira)")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
TR = SP.get("tarkib") or [] if isinstance(SP, dict) else []
check("T1 tarkib: oylik + har xarajat turi; yig'indi = Jami oylik + Jami xarajat; «Hodimlar oyligi» = Jami oylik; kamayish "
      "tartibida; foizlar yig'indisi ≈ 100",
      TR and sum(r["summa"] for r in TR) == J.get("oylik", 0) + J.get("xarajat", 0)
      and next((r["summa"] for r in TR if r["kalit"] == "hodimlar"), None) == J.get("oylik")
      and [r["summa"] for r in TR] == sorted((r["summa"] for r in TR), reverse=True)
      and abs(sum(r["foiz"] for r in TR if r["summa"] > 0) - 100) <= 0.6, TR)
check("T2 har xarajat turi = Jami `xarajat_qismlari` (ustunlar + umumiy)",
      all(r["summa"] == (J.get("xarajat_qismlari") or {}).get(r["kalit"]) for r in TR if r["kalit"] != "hodimlar"),
      [TR, J.get("xarajat_qismlari")])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("F. PDF — shu davr bilan")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
_rp = req(CA, "get", "/api/finance/split-profit-pdf", params={"year": _y0, "month": _o0, "gacha_yil": _y2, "gacha_oy": _o2})
SAT = pdf_satrlar(_rp.content) if _rp.status_code == 200 and (_rp.content or b"").startswith(b"%PDF") else []
_mat = "\n".join(SAT)
_nat = []
for i, q in enumerate(SAT):
    if q.startswith("NATIJA (+"):
        _nat = [son(x) for x in SAT[i + 1:i + 1 + len(SK.get("yonalishlar", [])) + 1]]
check("F1 PDF: 200, fayl nomi davr bilan, sarlavha, davr nomi, «Oldingi davr» qatori, «Moliya hisobotidagi sof foyda», "
      "NATIJA qatori = hisobot (ustunlar va JAMI), «■» yo'q",
      _rp.status_code == 200 and f"yonalishlar_hisobot_{_y0}_{_o0:02d}_{_y2}_{_o2:02d}" in (_rp.headers.get("content-disposition") or "")
      and "Yo'nalishlar bo'yicha moliyaviy natija" in _mat and services.yonalish_davr_nomi(OYLAR3) in _mat
      and "Oldingi davr" in _mat and "Moliya hisobotidagi sof foyda" in _mat and "■" not in _mat
      and _nat == [y["som"]["natija"] for y in SK.get("yonalishlar", [])] + [JK.get("natija")],
      [_rp.status_code, _rp.headers.get("content-disposition"), _nat, SAT[:40]])
check("F2 PDF: «OYLIKLAR», «XARAJATLAR», «yo'nalishsiz hodimlar (umumiy)», «Xarajatlar tarkibi» bor; «ulush» so'zi yo'q",
      all(x in _mat for x in ("3. OYLIKLAR", "4. XARAJATLAR", "yo'nalishsiz hodimlar (umumiy)", "Xarajatlar tarkibi"))
      and "ulush" not in _mat.lower(), SAT[:60])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Korxona chegarasi va huquq")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
_bk = req(CB, "get", "/api/finance/yonalishlar", params={"year": _y0, "month": _o0, "gacha_yil": _y2, "gacha_oy": _o2})
_bkj = js(_bk)
check("Z1 B korxona 3 oylik hisobotida A ning yo'nalishlari va summalari yo'q (faqat «Penoplast», daromad 0)",
      _bk.status_code == 200 and [y.get("nom") for y in (_bkj.get("yonalishlar") or [])] == ["Penoplast"]
      and (_bkj.get("jami") or {}).get("daromad") == 0 and (_bkj.get("jami") or {}).get("oylik") == 0,
      [_bk.status_code, _bk.text[:300]])
_w = req(CW, "get", "/api/finance/yonalishlar", params={"year": YIL, "month": OY})
_wp = req(CW, "get", "/api/finance/split-profit-pdf", params={"year": YIL, "month": OY})
check("Z2 omborchi (moliya huquqisiz) — 403 (JSON ham, PDF ham)", _w.status_code == 403 and _wp.status_code == 403,
      [_w.status_code, _wp.status_code])

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
