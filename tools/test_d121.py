#!/usr/bin/env python3
"""
test_d121.py — kech118 D BOSQICHI 1-qism (zip 121): MAYDA QOIDALAR VA NOMLAR (egasi QARORLARI kech118 11:40, tugmali, QAYTA
SO'RALMAYDI).

NIMA UCHUN KERAK (audit topilmalari)
  G2-20  «Loyihani o'chirasizmi? Barcha buyurtmalar ham o'chadi!» — aslida faqat loyiha belgilanardi, buyurtmalar, qarz va
         to'lovlar ro'yxatlarda qolardi. QAROR «Taqiqlansin»: buyurtmasi bor loyiha o'chmaydi («Avval buyurtmalarni o'chiring»);
         loyihasi o'chirilgan buyurtma tiklansa — loyiha ham tiklanadi.
  G5-11  «Kam» belgisini dastur o'zi o'ylab topardi (qoldiqning 40 %, kamida 5 — qop, m², dona uchun bir xil). QAROR «Har
         mahsulotga o'zim yozaman», yozilmasa «Kam» yo'q; «Bugun ishlab chiqarilgan: 9 tur» — aslida partiya.
  G5-12  Guruh qatorida «Sotish» yo'q; savatchada «Kerakli miqdor» HAMMA qoldiq bilan to'lardi. QAROR «Qo'lda tanlash qolsin».
  G5-20  Brak sababi ixtiyoriy va ikki marta so'ralardi (yozma «Sabab» + ro'yxat). QAROR «Ha, majburiy» (bosqich / javobgar
         ixtiyoriy), yozma maydon — «Izoh».
  G6-21  Hodim o'z oyligini ko'rmasdi, rad etilgan avans sababsiz edi. QAROR «Oylik ko'rinsin + rad sababi» (majburiy).
  G3-14  «Kassa balansi — hozir qancha NAQD pul bor» — hisobga karta / bank ham kirardi, manfiy summa izohsiz. QAROR «Bitta:
         Kassa + bank», boshlang'ich balans kiritilmagan bo'lsa ogohlantirish va tugma.
  U-12 / G4-19 / G6-11  Nomlar: «Ta'minotchi» (yetkazib beruvchi / hamkor / yetkazuvchi o'rniga), Kirim formasida «Material»,
         hujjatlar «Buyurtma hisobi», «Yuk xati № …», «Sotuv cheki № …» (hammasi «NAKLADNOY» edi); menyuda «Kirim qilish» va
         «Ta'minotchilar».
BO'LIMLAR: L (loyiha), K («Kam» chegarasi), B (brak sababi), A (avans rad sababi), H (hodim oyligi), Q (kassa + bank),
N (nomlar, hujjatlar, menyu), T (shablonlar). JS xatti-harakati — tools/test_d121_ui.js.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16; `TENANT_FILTER=1` bilan ham.
ISHLATISH: python3 tools/test_d121.py
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
PG_BAZA = "d121_test"
_T = tempfile.mkdtemp(prefix="d121_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'd121_test.db')}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import crud                                        # noqa: E402
import services                                    # noqa: E402
import ruxsatlar as RX                             # noqa: E402
from database import SessionLocal, tashkent_date   # noqa: E402
from models import (UserRole, Order, OrderType, Project, FinishedProduct, StockSource, ProductionStatus,   # noqa: E402
                    AdvanceRequest, ActivityLog, ReturnItem, FinishedProductLoss, CashTransaction)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF] " if os.environ.get("TENANT_FILTER") else "")
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


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def xabar(r):
    d = js(r)
    if not isinstance(d, dict):
        return ""
    det = d.get("detail")
    if isinstance(det, dict):
        return str(det.get("message") or "")
    return str(det or "")


def xavfsiz(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:                 # noqa: BLE001
        return f"{type(e).__name__}: {e}"


def fayl(nom):
    try:
        with open(os.path.join(ROOT, nom), encoding="utf-8") as f:
            return f.read()
    except Exception:                      # noqa: BLE001
        return ""


# ── PDF matni (ReportLab: FlateDecode / ASCII85) — test_tannarx bilan bir usul ──
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


def pdf_matn(bayt):
    """PDF dagi hamma matn oqimlari (siqilgan bo'lsa ochib) — sarlavha qidirish uchun (Tj satrlari)."""
    try:
        obyektlar = re.findall(rb"(\d+) 0 obj\s*(.*?)\s*endobj", bayt, re.S)
    except Exception:                      # noqa: BLE001
        return ""
    qism = []
    for _, tana in obyektlar:
        if b"stream" not in tana:
            continue
        try:
            _, data = _oqim(tana)
        except Exception:                  # noqa: BLE001
            continue
        for m in re.finditer(rb"\((?:\\.|[^\\)])*\)\s*Tj", data):
            qism.append(m.group(0)[1:m.group(0).rfind(b")")].decode("latin-1", "replace"))
    return " ".join(qism)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Fikstura: korxona 1 (kod D1) va 2 (kod D2); foydalanuvchilar — Admin, Menejer, Omborchi, Moliyachi (1), Admin (2)
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="D121 B korxona"))
    s.commit()
s.get(Company, 1).code = "D1"
s.get(Company, 2).code = "D2"
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "d_admin", "Parol123!", UserRole.ADMIN, "D Admin", company_id=1)
    auth.create_user(s, "d_menejer", "Parol123!", UserRole.MANAGER, "D Menejer", company_id=1)
    auth.create_user(s, "d_omborchi", "Parol123!", UserRole.WAREHOUSE, "D Omborchi", company_id=1)
    auth.create_user(s, "d_moliyachi", "Parol123!", UserRole.ACCOUNTANT, "D Moliyachi", company_id=1)
    auth.create_user(s, "d_admin2", "Parol123!", UserRole.ADMIN, "D Admin B", company_id=2)
s.commit()
s.close()


def mijoz(u):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": u, "password": "Parol123!"}, follow_redirects=False)
    return c, r.status_code


CA, _sa = mijoz("d_admin")
CM, _sm = mijoz("d_menejer")
CW, _sw = mijoz("d_omborchi")
CF, _sf = mijoz("d_moliyachi")
CB, _sb = mijoz("d_admin2")
if {_sa, _sm, _sw, _sf, _sb} != {302}:
    print("LOGIN BO'LMADI", _sa, _sm, _sw, _sf, _sb)
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)

_N = [0]


def buyurtma(pid, cid=1):
    """Loyihaga buyurtma (ORM — faqat bog'lanish kerak)."""
    _N[0] += 1
    d = SessionLocal()
    try:
        o = Order(company_id=cid, project_id=pid, order_number=f"D121-{_N[0]}", order_type=OrderType.PRODUCT)
        d.add(o)
        d.commit()
        return o.id
    finally:
        d.close()


def loyiha(c, nom):
    r = c.post("/api/projects", json={"project_name": nom, "client_name": "D mijoz"})
    return (js(r) or {}).get("id") if r.status_code in (200, 201) else None


def loyiha_holati(pid):
    d = SessionLocal()
    try:
        p = d.get(Project, pid)
        return None if p is None else bool(p.is_deleted)
    finally:
        d.close()


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("L. G2-20 — buyurtmasi bor loyihani o'chirib bo'lmaydi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
P1 = loyiha(CA, "D121 Loyiha buyurtmali")
O1, O2 = buyurtma(P1), buyurtma(P1)
_r = CA.delete(f"/api/projects/{P1}")
check("L1 2 ta buyurtmali loyiha → 400, sabab «Loyihada 2 ta buyurtma bor — avval buyurtmalarni o'chiring», loyiha O'CHMADI",
      _r.status_code == 400 and xabar(_r) == "Loyihada 2 ta buyurtma bor — avval buyurtmalarni o'chiring"
      and loyiha_holati(P1) is False, (_r.status_code, _r.text[:200], loyiha_holati(P1)))
_d = SessionLocal()
try:
    _d.get(Order, O1).is_deleted = True
    _d.commit()
finally:
    _d.close()
_r = CA.delete(f"/api/projects/{P1}")
check("L2 bittasi o'chirilgach — «1 ta buyurtma bor», loyiha joyida",
      _r.status_code == 400 and "1 ta buyurtma" in xabar(_r) and loyiha_holati(P1) is False, (_r.status_code, _r.text[:200]))
_d = SessionLocal()
try:
    _d.get(Order, O2).is_deleted = True
    _d.commit()
finally:
    _d.close()
_r = CA.delete(f"/api/projects/{P1}")
check("L3 hamma buyurtma o'chirilgach (savatda) — loyiha o'chadi (200, yumshoq)",
      _r.status_code == 200 and loyiha_holati(P1) is True, (_r.status_code, _r.text[:200]))
P0 = loyiha(CA, "D121 Bo'sh loyiha")
_r = CA.delete(f"/api/projects/{P0}")
check("L4 buyurtmasiz loyiha — o'chadi (200)", _r.status_code == 200 and loyiha_holati(P0) is True, _r.status_code)
_r = CA.post(f"/api/orders/{O2}/restore")
_d = SessionLocal()
try:
    _o2 = _d.get(Order, O2)
    _o2_del = bool(_o2.is_deleted)
    _jurnal = [(a.action, a.entity_type, a.entity_id) for a in _d.query(ActivityLog).filter(
        ActivityLog.action == "restored").all()]
finally:
    _d.close()
check("L5 loyihasi o'chirilgan buyurtma tiklansa — loyiha ham tiklanadi (faol buyurtmali o'chirilgan loyiha qolmaydi), "
      "ikkalasi jurnalda",
      _r.status_code == 200 and _o2_del is False and loyiha_holati(P1) is False
      and ("restored", "order", O2) in _jurnal and ("restored", "project", P1) in _jurnal,
      (_r.status_code, _r.text[:200], _o2_del, loyiha_holati(P1), _jurnal))
P2 = loyiha(CB, "D121 B loyiha")
OB = buyurtma(P2, cid=2)
_d = SessionLocal()
try:
    _tos = getattr(crud, "loyiha_ochirish_tosigi", None)
    _dp = xavfsiz(_tos, _d, P2, company_id=1) if _tos else "YO'Q"
    _dp2 = xavfsiz(_tos, _d, P2, company_id=2) if _tos else "YO'Q"
finally:
    _d.close()
check("L6 to'siq korxona ichida sanaladi (boshqa korxona buyurtmasi — hisobda emas); o'z korxonasida — «1 ta»",
      _dp is None and _dp2 == "Loyihada 1 ta buyurtma bor — avval buyurtmalarni o'chiring", (_dp, _dp2))
_r = CA.delete(f"/api/projects/{P2}")
check("L7 begona korxona loyihasi — 404 (o'chmaydi)", _r.status_code == 404 and loyiha_holati(P2) is False, _r.status_code)
_pj = fayl("templates/projects.html")
_pjf = _pj[_pj.find("async function deleteProj"):]
_pjf = re.sub(r"(?m)^\s*//.*$", "", _pjf[:_pjf.find("\n}\n")]).replace("\\'", "'")
check("L8 tasdiq matni haqiqatga mos: «O'chirilganlar» + tiklash mumkin + buyurtmasi borini o'chirib bo'lmaydi; eski yolg'on "
      "«Barcha buyurtmalar ham o'chadi» YO'Q; xato sababi serverdan",
      "«O'chirilganlar»" in _pjf and "tiklash mumkin" in _pjf and "avval buyurtmalarni o'chiring" in _pjf
      and "Barcha buyurtmalar ham o'chadi" not in _pj.replace("«Barcha buyurtmalar ham o'chadi!» derdi", "")
      and "serverXatoSababi(res" in _pjf, _pjf[:400])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. G5-11 — «Kam» chegarasi: egasi yozadi, yozilmasa «Kam» yo'q")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_d = SessionLocal()
try:
    def _fp(nom, cid=1, qalin=5.0, manba=StockSource.PRODUCED, miqdor=8.0, holat=ProductionStatus.READY):
        f = FinishedProduct(company_id=cid, name=nom, category="profil", quantity=miqdor, produced_quantity=miqdor,
                            unit="metr", unit_price=10_000, cost_price=miqdor * 4000, width=12.0, thickness=qalin,
                            is_coated=True, source=manba, production_status=holat)
        _d.add(f)
        _d.flush()
        return f.id
    KA1 = _fp("D Karniz  Oq")
    KA2 = _fp("d karniz oq", miqdor=3.0)              # xuddi shu mahsulot (katta-kichik harf, bo'shliq) — 2-partiya
    KB = _fp("D Karniz Oq", qalin=7.0)                  # boshqa o'lcham — boshqa mahsulot
    KR = _fp("D Qaytgan", manba=StockSource.RETURNED)
    KX = _fp("D Karniz Oq", cid=2)                      # B korxona
    _d.commit()
finally:
    _d.close()


def tm_royxat(c=CA):
    return {x["id"]: x for x in (js(c.get("/api/finished")) or []) if isinstance(x, dict)}


def kc(l, i):
    """Qatordagi `kam_chegara` (kalit / qator yo'q — «YO'Q»: asl kodda test qulamaydi)."""
    return (l.get(i) or {}).get("kam_chegara", "YO'Q")


_l = tm_royxat()
check("K1 /api/finished — har qatorda `kam_chegara`, standart null (yozilmagan — «Kam» yo'q)",
      all("kam_chegara" in _l.get(i, {}) and kc(_l, i) is None for i in (KA1, KA2, KB, KR)),
      {i: _l.get(i, {}).get("kam_chegara", "YO'Q") for i in (KA1, KA2, KB, KR)})
_r = CA.put(f"/api/finished/{KA1}/kam-chegara", json={"chegara": 20})
_l = tm_royxat()
check("K2 chegara 20 yozildi — shu mahsulotning HAMMA partiyalari (nom katta-kichik harf / bo'shliq farqi bilan) oladi, "
      "boshqa o'lcham — yo'q",
      _r.status_code == 200 and (js(_r) or {}).get("kam_chegara") == 20
      and kc(_l, KA1) == 20 and kc(_l, KA2) == 20 and kc(_l, KB) is None,
      (_r.status_code, _r.text[:200], {i: kc(_l, i) for i in (KA1, KA2, KB)}))
_r = CA.put(f"/api/finished/{KA2}/kam-chegara", json={"chegara": 12.5})
_l = tm_royxat()
check("K3 boshqa partiyadan o'zgartirish — bitta yozuv yangilanadi (12.5), ikkalasida bir xil",
      _r.status_code == 200 and kc(_l, KA1) == 12.5 and kc(_l, KA2) == 12.5,
      {i: kc(_l, i) for i in (KA1, KA2)})
_d = SessionLocal()
try:
    import models as _models
    _TKC = getattr(_models, "TmKamChegara", None)
    _yoz = [(y.company_id, y.chegara, y.updated_by) for y in _d.query(_TKC).all()] if _TKC is not None else "YO'Q"
    _log = [(a.entity_id, a.old_value, a.new_value, a.performed_by) for a in _d.query(ActivityLog).filter(
        ActivityLog.entity_type == "finished_product", ActivityLog.action == "updated").all()]
finally:
    _d.close()
check("K4 bazada BITTA yozuv (korxona 1, 12.5, kim yozgani); jurnalda ikkala o'zgarish (— → 20 metr, 20 metr → 12.5 metr)",
      _yoz == [(1, 12.5, "D Admin")] and (KA1, "—", "20 metr", "D Admin") in _log and (KA2, "20 metr", "12.5 metr", "D Admin") in _log,
      (_yoz, _log))
for _nomi, _tana in (("matn", {"chegara": "5"}), ("manfiy", {"chegara": -1}), ("bool", {"chegara": True}),
                     ("juda katta", {"chegara": 1e12}), ("ortiqcha kalit", {"chegara": 5, "x": 1}), ("bo'sh tana", {}),
                     ("ro'yxat", {"chegara": [5]})):
    _r = CA.put(f"/api/finished/{KA1}/kam-chegara", json=_tana)
    check(f"K5 noto'g'ri tana ({_nomi}) → 400, chegara o'zgarmadi",
          _r.status_code == 400 and kc(tm_royxat(), KA1) == 12.5, (_r.status_code, _r.text[:150]))
_r = CA.put(f"/api/finished/{KA1}/kam-chegara", content=b'{"chegara": Infinity}', headers={"content-type": "application/json"})
check("K5b Infinity → 400 / 422 (cheksiz son saqlanmaydi)", _r.status_code in (400, 422) and kc(tm_royxat(), KA1) == 12.5,
      _r.status_code)
_r = CA.put(f"/api/finished/{KR}/kam-chegara", json={"chegara": 5})
check("K6 qaytgan (ishlab chiqarilmagan) mahsulot → 400", _r.status_code == 400 and "ishlab chiqarilgan" in xabar(_r), _r.text[:200])
_r = CA.put(f"/api/finished/{KX}/kam-chegara", json={"chegara": 5})
check("K7 begona korxona mahsuloti → 404; B korxonasida chegara yozilmadi",
      _r.status_code == 404 and kc(tm_royxat(CB), KX) is None, (_r.status_code, _r.text[:150]))
_r = CB.put(f"/api/finished/{KX}/kam-chegara", json={"chegara": 3})
check("K8 korxonalar ajratilgan: B da xuddi shu nomli mahsulot uchun o'z chegarasi (3), A niki 12.5 bo'lib qoladi",
      _r.status_code == 200 and kc(tm_royxat(CB), KX) == 3 and kc(tm_royxat(), KA1) == 12.5,
      (_r.status_code, _r.text[:150]))
_huquq = [(n, c.put(f"/api/finished/{KB}/kam-chegara", json={"chegara": 4}).status_code)
          for n, c in (("menejer", CM), ("omborchi", CW), ("moliyachi", CF))]
check("K9 huquq: «Tayyor mahsulotlar: Tahrirlash» — Menejer / Omborchi 200, Moliyachi 403",
      _huquq == [("menejer", 200), ("omborchi", 200), ("moliyachi", 403)], _huquq)
_r = CA.put(f"/api/finished/{KA1}/kam-chegara", json={"chegara": None})
_l = tm_royxat()
_r0 = CA.put(f"/api/finished/{KB}/kam-chegara", json={"chegara": 0})
check("K10 null — olib tashlandi (ikkala partiyada null); 0 ham — olib tashlash",
      _r.status_code == 200 and kc(_l, KA1) is None and kc(_l, KA2) is None
      and _r0.status_code == 200 and kc(tm_royxat(), KB) is None, (_r.text[:150], _r0.text[:150]))
_fin = fayl("templates/finished.html")
check("K11 sahifa: dastur o'ylab topgan chegara (`suggestedReserve`, 40 %, kamida 5) YO'Q; «Kam» — `fpKamChegara` (server "
      "`kam_chegara`), yozish tugmasi «Tahrirlash» ruxsati bilan; «Bugun ishlab chiqarilgan» — partiya",
      # kech120 (zip 133 — MOSLANDI): «Math.max(5000, …)» — xabar ko'rinish vaqti (G5-13), chegara emas; eski qoida — «Math.max(5, …)»
      "suggestedReserve" not in _fin and "Math.max(5," not in _fin and "Math.max(5 ," not in _fin and "function fpKamChegara(i)" in _fin
      and "i.kam_chegara" in _fin and "const TM_TAHRIR = {{ 'true' if current_user.ruxsat('tayyor', 'tahrirlash')" in _fin
      and "todayProduced + ' partiya'" in _fin and "todayProduced + ' tur'" not in _fin)
_st_w = CW.get("/finished")
_st_f = CA.get("/finished")
check("K12 /finished — Omborchida `TM_TAHRIR = true`; sahifa 200",
      _st_w.status_code == 200 and "const TM_TAHRIR = true;" in _st_w.text and "const TM_TAHRIR = true;" in _st_f.text,
      _st_w.status_code)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. G5-20 — brak sababi majburiy (hamma yo'lda)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def holat():
    d = SessionLocal()
    try:
        return (d.query(ReturnItem).count(), d.query(FinishedProductLoss).count(),
                round(float(d.get(FinishedProduct, KA1).quantity or 0), 6))
    finally:
        d.close()


h0 = holat()
_r = CA.post("/api/finished/loss", json={"finished_product_id": KA1, "quantity": 1, "reason": "sindi"})
check("B1 «Kamaytirish» sababsiz → 400 «Brak sababini tanlang (ro'yxatdan)», qoldiq va yozuvlar o'zgarmadi",
      _r.status_code == 400 and xabar(_r) == "Brak sababini tanlang (ro'yxatdan)" and holat() == h0, (_r.status_code, _r.text[:200]))
_r = CA.post("/api/finished/loss", json={"finished_product_id": KA1, "quantity": 1, "reason": "sindi", "brak_sabab": None})
check("B1b sabab null → 400 (o'zgarmadi)", _r.status_code == 400 and holat() == h0, _r.status_code)
_r = CA.post("/api/finished/loss", json={"finished_product_id": KA1, "quantity": 1, "reason": "sindi", "brak_sabab": "xomashyo"})
check("B2 sabab bilan → 200, yozuvda sabab 'xomashyo', qoldiq −1",
      _r.status_code == 200 and holat()[2] == h0[2] - 1, (_r.status_code, _r.text[:200]))
KP = None
_d = SessionLocal()
try:
    _f = FinishedProduct(company_id=1, name="D jarayon", category="profil", quantity=5, produced_quantity=5, unit="metr",
                         unit_price=0, cost_price=0, width=10.0, thickness=5.0, source=StockSource.PRODUCED,
                         production_status=ProductionStatus.IN_PROGRESS, unit_volume_m3=0.001)
    _d.add(_f)
    _d.commit()
    KP = _f.id
finally:
    _d.close()
h1 = holat()
_r = CA.post("/api/finished/production-brak", json={"finished_product_id": KP, "brak_qty": 1})
check("B3 ishlab chiqarish braki sababsiz → 400 (xomashyo YECHILMADI, yozuv yo'q)",
      _r.status_code == 400 and xabar(_r) == "Brak sababini tanlang (ro'yxatdan)" and holat() == h1, (_r.status_code, _r.text[:200]))
P3 = loyiha(CA, "D121 Brak loyiha")
O3 = buyurtma(P3)
_d = SessionLocal()
try:
    from models import OrderItem as _OI
    _oi = _OI(company_id=1, order_id=O3, name="D detal", category="profil", width=10.0, thickness=5.0, length=10.0,
              quantity=10.0,
              is_coated=False, unit_price=1000)
    _d.add(_oi)
    _d.commit()
    OI3 = _oi.id
finally:
    _d.close()
h2 = holat()
_r = CA.post("/api/returns", json={"order_id": O3, "order_item_id": OI3, "item_name": "D detal", "quantity": 1, "reason": "Brak", "to_stock": False})
check("B4 buyurtma braki («Brak yozish» / «Yangi qaytarish» → Brak) sababsiz → 400, qaytarish yozuvi yo'q",
      _r.status_code == 400 and xabar(_r) == "Brak sababini tanlang (ro'yxatdan)" and holat() == h2, (_r.status_code, _r.text[:200]))
_r = CA.post("/api/returns", json={"order_id": O3, "order_item_id": OI3, "item_name": "D detal", "quantity": 1, "reason": "Brak", "to_stock": False,
                                   "brak_sabab": "ishchi"})
check("B5 sabab bilan → 200 (brak_sabab 'ishchi')", _r.status_code == 200 and (js(_r) or {}).get("brak_sabab") == "ishchi",
      (_r.status_code, _r.text[:200]))
_r = CA.post("/api/returns", json={"order_id": O3, "order_item_id": OI3, "item_name": "D detal", "quantity": 1, "reason": "Ortiqcha", "to_stock": False})
check("B6 brak EMAS qaytarish («Ortiqcha») — sababsiz ham 200 (qoida faqat brak uchun)", _r.status_code == 200, _r.text[:200])
# kech118 (zip 123 — egasi QARORI G5-04, MOSLANDI): brak — BITTA «Brak yozish» oynasi (templates/_brak_oyna.html; Qaytarishlar va
# Tayyor mahsulotlar ulaydi). Ilgari B7 «Kamaytirish» oynasini (loss-*), B8 «Yangi qaytarish» → «Brak» maydonlarini tekshirardi.
_ret = fayl("templates/returns.html")
_oy = fayl("templates/_brak_oyna.html")
check("B7 «Brak yozish» oynasi (bitta, hamma yo'l uchun): sabab ro'yxati BIRINCHI (majburiy «*», «— Tanlang —»), keyin bosqich, "
      "javobgar, oxirida «Izoh (ixtiyoriy)»; eski «Sabab (ixtiyoriy)» / «Nima sababdan? (ixtiyoriy)» YO'Q",
      -1 < _oy.find('id="brakModal"') < _oy.find('id="brak-cause"') < _oy.find('id="brak-stage"') < _oy.find('id="brak-worker"')
      < _oy.find('id="brak-notes"') and "Sabab (ixtiyoriy)" not in _oy + _fin and "Nima sababdan? (ixtiyoriy)" not in _oy + _fin
      and "Izoh <span" in _oy and re.search(r'<select id="brak-cause"[^>]*>\s*<option value="">— Tanlang —</option>', _oy)
      and '{% include "_brak_oyna.html" %}' in _fin)
check("B8 Qaytarishlar: oyna ulangan; «Yangi qaytarish» da «Brak» varianti va f-brak-* maydonlari YO'Q (faqat butun); eski "
      "«⚠️ (Kamaytirish)» / «Sabab / izoh» yo'q",
      '{% include "_brak_oyna.html" %}' in _ret and 'id="f-brak-cause"' not in _ret and 'value="Brak" onchange' not in _ret
      and "⚠️ (Kamaytirish)" not in _ret + _oy and "Sabab / izoh" not in _ret + _oy)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. G6-21 — avans so'rovini rad etish: sabab majburiy, hodim ko'radi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def hodim(nom, tel, pin, **qosh):
    t = {"name": nom, "pay_type": "fixed", "fixed_amount": 3_000_000}
    t.update(qosh)
    r = CA.post("/api/employees", json=t)
    eid = (js(r) or {}).get("id") if r.status_code == 200 else None
    CA.post(f"/api/employees/{eid}/set-login", data={"phone": tel, "pin": pin})
    h = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = h.post("/hodim/login", data={"phone": tel, "pin": pin, "korxona": "D1"}, follow_redirects=False)
    return eid, h, r.status_code


E1, H1, _he = hodim("D Hodim 1", "+998907771101", "5511")
E2, H2, _he2 = hodim("D Hodim 2", "+998907771102", "5522", fixed_amount=2_000_000)
check("A0 hodimlar paneliga kirdi (302)", E1 and E2 and _he == 302 and _he2 == 302, (E1, E2, _he, _he2))
BUGUN = tashkent_date()
SANA = BUGUN.strftime("%Y-%m-%d")
for _i in range(3):
    H1.post("/api/hodim/advance-request", data={"amount": str(100_000 + _i), "requested_date": SANA, "notes": f"D{_i}"})
_d = SessionLocal()
try:
    RQ = [r.id for r in _d.query(AdvanceRequest).filter(AdvanceRequest.employee_id == E1).order_by(AdvanceRequest.id).all()]
finally:
    _d.close()


def sorov(i):
    d = SessionLocal()
    try:
        r = d.get(AdvanceRequest, i)
        return (r.status.value, getattr(r, "rad_sababi", "USTUN YO'Q"), r.confirmed_by)
    finally:
        d.close()


for _nomi, _kw in (("tanasiz", {}), ("bo'sh sabab", {"json": {"sabab": "   "}}), ("sabab son", {"json": {"sabab": 5}}),
                   ("ortiqcha kalit", {"json": {"sabab": "x", "y": 1}}), ("301 belgi", {"json": {"sabab": "x" * 301}}),
                   ("null", {"json": {"sabab": None}})):
    _r = CA.post(f"/api/admin/advance-requests/{RQ[0]}/reject", **_kw)
    check(f"A1 rad etish {_nomi} → 400 (sabab majburiy), so'rov KUTILMOQDA",
          _r.status_code == 400 and sorov(RQ[0])[0] == "pending", (_r.status_code, _r.text[:150], sorov(RQ[0])))
_r = CA.post(f"/api/admin/advance-requests/{RQ[0]}/reject", json={"sabab": "  Bu kuni avans berilmagan  "})
check("A2 sabab bilan → 200; holat «rejected», sabab (bo'shliqsiz) va kim — saqlandi",
      _r.status_code == 200 and sorov(RQ[0]) == ("rejected", "Bu kuni avans berilmagan", "D Admin"), (_r.text[:150], sorov(RQ[0])))
_r = CA.post(f"/api/admin/advance-requests/{RQ[0]}/reject", json={"sabab": "yana"})
check("A3 qayta rad etish → 404, sabab o'zgarmadi", _r.status_code == 404 and sorov(RQ[0])[1] == "Bu kuni avans berilmagan",
      _r.status_code)
_r = CA.post(f"/api/admin/advance-requests/{RQ[1]}/reject", json={"sabab": "x" * 300})
check("A4 300 belgi — chegarada qabul qilinadi", _r.status_code == 200 and sorov(RQ[1])[1] == "x" * 300, _r.status_code)
_r = CB.post(f"/api/admin/advance-requests/{RQ[2]}/reject", json={"sabab": "begona"})
check("A5 begona korxona admini → 404, so'rov kutilmoqda", _r.status_code == 404 and sorov(RQ[2])[0] == "pending", _r.status_code)
_r = CA.post(f"/api/admin/advance-requests/{RQ[2]}/confirm")
_my = js(H1.get("/api/hodim/my-requests")) or []
_myd = {x.get("id"): x for x in _my if isinstance(x, dict)}
check("A6 hodimning «Mening so'rovlarim»: rad etilganda — sababi, tasdiqlanganda — null",
      _myd.get(RQ[0], {}).get("rad_sababi") == "Bu kuni avans berilmagan" and _myd.get(RQ[0], {}).get("status") == "rejected"
      and _myd.get(RQ[2], {}).get("rad_sababi") is None and _myd.get(RQ[2], {}).get("status") == "confirmed", _my)
check("A7 boshqa hodim birinchisining so'rovlarini ko'rmaydi", (js(H2.get("/api/hodim/my-requests")) or []) == [],
      js(H2.get("/api/hodim/my-requests")))
_dash = fayl("templates/dashboard.html")
_hp = fayl("templates/hodim_panel.html")
check("A8 Dashboard: «❌ Yo'q» — sabab so'raladi (kiritishOyna, bo'sh bo'lsa qayta), tana {sabab}; hodim panelida «Sabab: …»",
      "kiritishOyna(\"Nega rad etasiz?\"" in _dash and "JSON.stringify({sabab})" in _dash and "r.rad_sababi" in _hp
      and 'class="req-sabab">Sabab: ${escapeHtml(r.rad_sababi)}' in _hp)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H. G6-21 — hodim o'z oyligini ko'radi (joriy va o'tgan oy)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
CA.post(f"/api/employees/{E1}/advance", params={"amount": "250000", "notes": "D avans", "adv_date": SANA})
CA.post(f"/api/employees/{E1}/monthly-adjustment", params={"year": str(BUGUN.year), "month": str(BUGUN.month),
                                                           "reduction_amount": "40000", "reason": "2 kun kelmadi",
                                                           "bonus_amount": "150000", "bonus_reason": "Yaxshi ish"})
_ok = H1.get("/api/hodim/oylik")
_o = (js(_ok) or {}).get("oylar") or []
_rep = services.get_monthly_report(SessionLocal(), BUGUN.year, BUGUN.month, company_id=1)
_e = next((x for x in _rep.get("hodimlar_moslashuvchan_breakdown", []) if x.get("employee_id") == E1), {})
_j = _o[0] if _o else {}
check("H1 /api/hodim/oylik — 200; joriy oy BIRINCHI, «joriy»; o'tgan oy (ishga kirmagan, to'lovsiz) KO'RSATILMAYDI",
      _ok.status_code == 200 and len(_o) == 1 and _j.get("joriy") is True and (_j.get("yil"), _j.get("oy")) == (BUGUN.year, BUGUN.month),
      (_ok.status_code, _o))
check("H2 raqamlar admin Hisobot / Moliya bilan AYNAN (bir manba): hisoblangan 3 110 000 (3 000 000 + 150 000 − 40 000), "
      "olingan 350 000 (tasdiqlangan so'rov 100 002 + admin avansi 250 000 = 350 002 → yaxlit), qolgan",
      _j.get("hisoblangan") == _e.get("amount") == 3_110_000 and _j.get("olingan") == _e.get("avans") == 350_002
      and _j.get("qolgan") == _e.get("qolgan") == 3_110_000 - 350_002, (_j, _e))
check("H3 bonus va kamaytirish — summa va sababi", (_j.get("bonus"), _j.get("bonus_sababi"), _j.get("kamaytirish"),
                                                    _j.get("kamaytirish_sababi")) == (150_000, "Yaxshi ish", 40_000, "2 kun kelmadi"), _j)
check("H4 to'lovlar ro'yxati (sana, summa) — ikkala avans; hisob tafsiloti (korxona sotuvi / foydasi) BERILMAYDI",
      sorted(t.get("summa") for t in _j.get("tolovlar") or []) == [100_002, 250_000]
      and not ({"detail", "pay_type", "position"} & set(_j)) and "detail" not in _ok.text, _j)
_o2 = (js(H2.get("/api/hodim/oylik")) or {}).get("oylar") or []
check("H5 boshqa hodim — faqat o'z raqamlari (2 000 000, olingan 0)",
      len(_o2) == 1 and (_o2[0].get("hisoblangan"), _o2[0].get("olingan"), _o2[0].get("qolgan")) == (2_000_000, 0, 2_000_000), _o2)
_eski = BUGUN.replace(day=1)
_oy_o, _yil_o = (_eski.month - 1, _eski.year) if _eski.month > 1 else (12, _eski.year - 1)
_d = SessionLocal()
try:
    from models import EmployeeAdvance as _EA
    from datetime import datetime as _dt
    _d.add(_EA(employee_id=E2, amount=70_000, date=_dt(_yil_o, _oy_o, 10, 7, 0), notes="o'tgan oy", given_by="D Admin"))
    _d.commit()
finally:
    _d.close()
_o2 = (js(H2.get("/api/hodim/oylik")) or {}).get("oylar") or []
check("H6 o'tgan oyda to'lov bo'lsa — o'tgan oy ham (ikkinchi, «joriy» emas): ishga kirmagan — hisoblangan 0, olingan 70 000, "
      "qolgan −70 000 (ortiqcha olingan)",
      len(_o2) == 2 and _o2[1].get("joriy") is False and (_o2[1].get("yil"), _o2[1].get("oy")) == (_yil_o, _oy_o)
      and (_o2[1].get("hisoblangan"), _o2[1].get("olingan"), _o2[1].get("qolgan")) == (0, 70_000, -70_000), _o2)
_bosh = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
check("H7 kirmagan (hodim sessiyasisiz) → 401; oddiy foydalanuvchi (admin) sessiyasi bilan ham — 401",
      _bosh.get("/api/hodim/oylik").status_code == 401 and CA.get("/api/hodim/oylik").status_code == 401,
      (_bosh.get("/api/hodim/oylik").status_code, CA.get("/api/hodim/oylik").status_code))
_pn = H1.get("/hodim")
check("H8 hodim paneli: «💵 Oyligim» kartasi (joriy / o'tgan oy), «Ortiqcha olingan», to'lovlar ro'yxati",
      _pn.status_code == 200 and "💵 Oyligim" in _pn.text and "fetch('/api/hodim/oylik')" in _pn.text
      and "Ortiqcha olingan" in _pn.text and "(joriy oy — hozirgacha)" in _pn.text, _pn.status_code)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Q. G3-14 — «Kassa + bank», boshlang'ich balans ogohlantirishi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_k0 = js(CA.get("/api/finance/cash-balance")) or {}
check("Q1 boshlang'ich balans kiritilmagan — `boshlangich_kiritilgan: false`", _k0.get("boshlangich_kiritilgan") is False, _k0)
_kb = js(CB.get("/api/finance/cash-balance")) or {}
_r = CA.post("/api/finance/cash-transaction", data={"category": "boshlangich", "amount": "5000000", "notes": "D kassa"})
_k1 = js(CA.get("/api/finance/cash-balance")) or {}
_kb1 = js(CB.get("/api/finance/cash-balance")) or {}
check("Q2 kiritilgach — true, balans +5 000 000; B korxonada — hali false (korxona ichida)",
      _r.status_code == 200 and _k1.get("boshlangich_kiritilgan") is True and _k1.get("balance") == _k0.get("balance") + 5_000_000
      and _kb.get("boshlangich_kiritilgan") is False and _kb1.get("boshlangich_kiritilgan") is False, (_r.text[:150], _k1, _kb1))
_d = SessionLocal()
try:
    _d.add(CashTransaction(company_id=2, category="usta_kpi", amount=-1000, notes="D B", performed_by="x"))
    _d.commit()
finally:
    _d.close()
check("Q3 boshqa turdagi qo'lda yozuv (Usta KPI) — boshlang'ich hisoblanmaydi",
      (js(CB.get("/api/finance/cash-balance")) or {}).get("boshlangich_kiritilgan") is False)
_fh = CA.get("/finance")
check("Q4 Moliya kartasi: «Kassa + bank — hozir qancha pul bor», «naqd, karta va bank»; ogohlantirish bloki va «Boshlang'ich "
      "balansni kiritish» tugmasi; eski «hozir qancha naqd pul bor» YO'Q",
      _fh.status_code == 200 and "Kassa + bank — hozir qancha pul bor" in _fh.text and "naqd, karta va bank" in _fh.text
      and 'id="cash-boshlangich-yoq"' in _fh.text and "Boshlang'ich balansni kiritish</button>" in _fh.text
      and "hozir qancha naqd pul bor" not in _fh.text and "d.boshlangich_kiritilgan !== false" in _fh.text, _fh.status_code)
_fm = CF.get("/finance")
check("Q5 Moliyachi (kassa yaratish yo'q?) — sahifa 200; tugma ruxsatga bog'liq",
      _fm.status_code == 200 and (("Boshlang'ich balansni kiritish</button>" in _fm.text)
                                  == bool(RX.TAYYOR_ROLLAR["moliyachi"]["ruxsatlar"].get("kassa") and "yaratish" in
                                          RX.TAYYOR_ROLLAR["moliyachi"]["ruxsatlar"]["kassa"])), _fm.status_code)
check("Q6 nom hamma joyda: Hisobotlar KPI «Kassa + bank», Rollar katalogi «Kassa + bank»",
      '<div class="bi-kpi-label">Kassa + bank</div>' in fayl("templates/reports.html")
      and RX.BANDLAR.get("kassa", {}).get("nom") == "Kassa + bank", RX.BANDLAR.get("kassa"))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("N. U-12 / G4-19 / G6-11 — nomlar lug'ati, hujjatlar, menyu")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_SHABLON = ("dashboard", "debts", "finance", "reports", "supplier_receive", "suppliers", "users")


def korinadigan(matn):
    """Izohlarsiz (HTML <!-- -->, Jinja {# #}, JS // qator izohi) — foydalanuvchi ko'radigan matn."""
    m = re.sub(r"<!--.*?-->", "", matn, flags=re.S)
    m = re.sub(r"\{#.*?#\}", "", m, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", m)


_topildi = {n: re.findall(r"(?i)yetkazib beruvchi\w*|yetkazuvchi\w*|hamkorlarga|bu hamkorga|shu hamkorga",
                          korinadigan(fayl(f"templates/{n}.html"))) for n in _SHABLON}
check("N1 sahifalarda «yetkazib beruvchi» / «yetkazuvchi» / «hamkor»(ta'minotchi ma'nosida) — YO'Q («Hamkor ustalar» — usta, "
      "tegilmaydi)", not any(_topildi.values()), {k: v for k, v in _topildi.items() if v})
_sr = fayl("templates/supplier_receive.html")
check("N2 Kirim formasi: «Ta'minotchidan kirim qilish», «Material qo'shish», «Material *», «Materiallar ro'yxati», «Material "
      "nomi», «Materiallar summasi»; «Mahsulot qo'shish» / «Mahsulot *» YO'Q",
      all(x in _sr for x in ("Ta'minotchidan kirim qilish", "Material qo'shish", "<label>Material *</label>", "Materiallar ro'yxati",
                             "<th>Material nomi</th>", "Materiallar summasi", "Hali material qo'shilmagan"))
      and "Mahsulot qo'shish" not in korinadigan(_sr) and "<label>Mahsulot *</label>" not in _sr
      and "Mahsulotlar summasi" not in _sr)
_base = fayl("templates/base.html")
check("N3 menyu: «Kirim qilish» (/suppliers/receive, «Xomashyo kirimi» ruxsati) va «Ta'minotchilar» (/suppliers, «Ta'minotchilar: "
      "Ko'rish»); eski bitta «Xomashyo ta'minoti» YO'Q",
      '<span class="n-txt">Kirim qilish</span>' in _base and '<span class="n-txt">Ta\'minotchilar</span>' in _base
      and "{% set m_taminotchi = u.ruxsat('taminotchi', 'korish') %}" in _base
      and '<span class="n-txt">Xomashyo ta\'minoti</span>' not in _base)
_mw = CW.get("/inventory")
_mf = CF.get("/finance")
check("N4 menyu ruxsatga qarab: Omborchida ikkala band, Moliyachida (kirim / ta'minotchi ruxsatiga qarab)",
      _mw.status_code == 200 and 'href="/suppliers/receive"' in _mw.text and 'href="/suppliers" ' in _mw.text,
      _mw.status_code)
_crud_src = fayl("crud.py")
_main_src = fayl("main.py")
_main_kod = re.sub(r"#.*", "", _main_src)
check("N5 server matnlari: ombor harakati «Ta'minotchi: …», «Bu ta'minotchida … qarz bor», «Ta'minotchi topilmadi», Telegram "
      "«🏪 Ta'minotchi», «Shu ta'minotchiga qarz»; moliya PDF «TA'MINOTCHIGA QARZ»",
      'reason=f"Ta\'minotchi: {supplier_name}"' in _crud_src and "Bu ta'minotchida {debt_info" in _crud_src
      and 'detail="Ta\'minotchi topilmadi"' in _crud_src and "🏪 Ta'minotchi: *{supplier.name}*" in _main_src
      and "Shu ta'minotchiga qarz" in _main_src and "TA'MINOTCHIGA QARZ" in fayl("finance_pdf.py")
      and "YETKAZUVCHIGA" not in fayl("finance_pdf.py"))
_ps, _dp = (re.sub(r"#.*", "", fayl("pdf_service.py")), re.sub(r"#.*", "", fayl("delivery_pdf.py")))
check("N6 hujjat nomlari: buyurtma — «BUYURTMA HISOBI», yuk xati — «YUK XATI № …», sotuv — «SOTUV CHEKI № S-…»; «NAKLADNOY» "
      "hech bir sarlavhada YO'Q",
      'Paragraph("BUYURTMA HISOBI", st["doc_title"])' in _ps and "NAKLADNOY" not in _ps.replace("Nakladnoy", "")
      and "(NAKLADNOY)" not in _dp and _dp.count("<b>SOTUV CHEKI</b>") == 2 and _dp.count("<b>YUK XATI</b>") == 1)
check("N7 yuklab olish fayl nomlari: buyurtma_hisobi_…, yuk_xati_…, sotuv_cheki_… (nakladnoy_ / yuk_xati_sotuv_ YO'Q)",
      'f"buyurtma_hisobi_{order.order_number}.pdf"' in _main_kod and _main_kod.count('f"yuk_xati_{d.delivery_number') == 2
      and 'f"sotuv_cheki_{group_id}.pdf"' in _main_kod and 'f"sotuv_cheki_{sale.id}.pdf"' in _main_kod
      and "nakladnoy_" not in _main_kod and "yuk_xati_sotuv_" not in _main_kod)
_sell = CA.post("/api/finished/sell", json={"finished_product_id": KA1, "quantity": 1, "unit_price": 10_000})
_sid = (js(_sell) or {}).get("sale_id")
_pdf = CA.get(f"/api/finished/sales/{_sid}/pdf") if _sid else None
_pm = pdf_matn(_pdf.content) if _pdf is not None and _pdf.status_code == 200 else ""
check("N8 HAQIQIY sotuv PDF: sarlavhada «SOTUV CHEKI», «NAKLADNOY» yo'q; fayl nomi sotuv_cheki_<id>.pdf",
      _pdf is not None and _pdf.status_code == 200 and "SOTUV CHEKI" in _pm and "NAKLADNOY" not in _pm
      and f"sotuv_cheki_{_sid}.pdf" in _pdf.headers.get("content-disposition", ""),
      (_sell.status_code, _sell.text[:150], None if _pdf is None else _pdf.status_code, _pm[:200]))
_opdf = CA.get(f"/api/orders/{O3}/pdf")
_om = pdf_matn(_opdf.content) if _opdf.status_code == 200 else ""
check("N9 HAQIQIY buyurtma PDF: «BUYURTMA HISOBI», fayl nomi buyurtma_hisobi_…",
      _opdf.status_code == 200 and "BUYURTMA HISOBI" in _om and "NAKLADNOY" not in _om
      and "buyurtma_hisobi_" in _opdf.headers.get("content-disposition", ""), (_opdf.status_code, _om[:200]))
_ord = fayl("templates/orders.html")
check("N10 Buyurtmalar sahifasi: «Saqlash va yuk xatini olish», «Yuk xati tayyor», «Buyurtma hisobi (PDF)»; «nakladnoy» so'zi "
      "ko'rinadigan matnda YO'Q",
      "💾 Saqlash va yuk xatini olish" in _ord and "Yuk xati tayyor." in _ord and "📄 Buyurtma hisobi (PDF)" in _ord
      and not re.search(r"(?i)nakladnoy", korinadigan(_ord)), re.findall(r"(?i).{30}nakladnoy.{20}", korinadigan(_ord))[:3])
check("N11 Ta'minotchilar sahifasi sarlavhasi «Ta'minotchilar», tugma «+ Ta'minotchi»; Kirim yo'lakchasi «Ta'minotchilar»",
      "{% block page_title %}Ta'minotchilar{% endblock %}" in fayl("templates/suppliers.html")
      and "+ Ta'minotchi</button>" in fayl("templates/suppliers.html") and "Bosh sahifa · Ta'minotchilar · Kirim" in _sr)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. G5-12 — guruh qatorida «Sotish», savatcha bo'sh boshlanadi (shablon)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("T1 guruh qatorida «Sotish» (fpGuruhSotish), savatchada miqdor BO'SH (value=\"\"), «Qoladi» (eski «Mavjud miqdor» YO'Q), "
      "tugma «✓ Sotish» («Hammasini sotish» YO'Q)",
      'onclick="fpGuruhSotish(this)"' in _fin and 'class="batch-qty" value=""' in _fin and ">Qoladi</div>" in _fin
      and "Mavjud miqdor" not in _fin and "✓ Hammasini sotish" not in _fin and ">✓ Sotish</button>" in _fin)
import subprocess                                  # noqa: E402
import shutil                                      # noqa: E402
_NODE = shutil.which("node")


def js_sintaksis(html):
    """Sahifadagi har ichki <script> (src siz, JS turi) — `node --check` (sintaksis xatosi → matni)."""
    xatolar = []
    for i, m in enumerate(re.finditer(r"<script(?P<a>[^>]*)>(?P<k>.*?)</script>", html, re.S)):
        if "src=" in m.group("a") or re.search(r'type="(?!text/javascript|module)', m.group("a")):
            continue
        f = os.path.join(_T, f"s{i}.js")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(m.group("k"))
        k = subprocess.run([_NODE, "--check", f], capture_output=True, text=True)
        if k.returncode != 0:
            xatolar.append((k.stderr or "")[:300])
    return xatolar


for _sah, _kl in (("/finished", CA), ("/returns", CA), ("/finance", CA), ("/suppliers", CA), ("/suppliers/receive", CA),
                  ("/dashboard", CA), ("/projects", CA), ("/reports", CA), ("/orders", CA), ("/debts", CA), ("/users", CA),
                  ("/finished", CW), ("/finance", CF), ("/hodim", H1)):
    _x = _kl.get(_sah)
    _xs = js_sintaksis(_x.text) if (_NODE and _x.status_code == 200) else ["node yo'q" if not _NODE else "sahifa yo'q"]
    check(f"T2 {_sah} ({'hodim' if _kl is H1 else 'foydalanuvchi'}) — 200, ichki JS sintaksisi toza (node --check)",
          _x.status_code == 200 and not _xs, (_x.status_code, _xs))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  - " + f)
sys.exit(1 if FAIL else 0)
