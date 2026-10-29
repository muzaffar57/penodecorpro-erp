#!/usr/bin/env python3
"""
test_nom_tartib222.py — kech159 (zip 222 «Detal nomi — katta / kichik harf» — egasi 28.10: yuk xatida «PADAKOLNIK» → «Padakolnik»; tanlovi
«Saqlashda + yuk xatida (Tavsiya)»).

NIMA UCHUN KERAK (O'LCHANGAN — production 27.10 zaxirasi, `work/k222/nom_sinov222.py`)
  236 detal, 156 xil nom, 99 tasida butun katta harfli so'z («10 LI KARNIZ», «15 LI NALIChNIK», «NAKSh», «49  GA 3 LI USTUN» — ikki bo'shliq);
  `base.html` `capitalizeFirst` faqat birinchi harfni kattalashtiradi. Yuk xati / PDF / Telegram nomni JONLI `OrderItem.name` dan oladi.
QOIDA (`schemas.detal_nomi_tartib`)
  bo'shliqlar bittaga; butun katta harfli so'z (Ch / Sh / Yu / Ya / Yo / Ye digraflari hisobga, kamida 2 bosh harf) — kichik; birinchi harf — katta;
  oddiy / aralash so'z — o'zgarmaydi. Saqlashda (yaratish, tahrir, taklif, rasmiylashtirish, bitta detal tahriri) va ko'rsatishda (yuk xati
  — asosiy va «keyingi topshirish», umumiy hisobot, jamlanma, «BUYURTMA HISOBI», taklif PDF, Telegram yuk xabarlari). Tahrirda moslash kaliti
  bo'shliqlarni ham bittaga keltiradi — eski «49  GA 3 LI USTUN» o'sha detal (nomi tartiblangan shaklga yangilanadi). Bazadagi eski yozuv —
  tahrirlanmaguncha o'zgarmaydi.
BO'LIMLAR
  S — manba. N — qoida jadvali. A — server (saqlash: yaratish, 422, taklif va rasmiylashtirish, bitta detal tahriri; eski buyurtma tahriri — raqam
  bilan / raqamsiz, topshirilgani saqlanadi). P — PDF matni (yuk xati asosiy + keyingi topshirish, umumiy hisobot, jamlanma, «BUYURTMA HISOBI»,
  taklif). T — Telegram yuk xabari. (JS o'zgarmagan — brauzer bo'limi yo'q.)
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL (S + A).
Asl kodga (zip 221) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_nom_tartib222.py
"""
import os
import io
import sys
import json
import inspect
import datetime
import tempfile
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "nomtartib222_test"
_T = tempfile.mkdtemp(prefix="k222_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k222.db')}"
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
        print(f"  ✗ {label}   {str(detail)[:1200]}")


def section(t):
    print(f"\n--- {t} ---")


def xav(f, *a, standart=None, **k):
    try:
        return f(*a, **k)
    except Exception as e:                 # noqa: BLE001
        print(f"    (bajarilmadi: {getattr(f, '__name__', f)} — {type(e).__name__}: {str(e)[:200]})")
        return standart


with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import schemas                                 # noqa: E402
    import services                                # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, Project, Master, Order, Recipe, RecipeIngredient    # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    with TestClient(main.app):
        pass

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_dnt = getattr(schemas, "detal_nomi_tartib", None)
check("S1 `schemas.detal_nomi_tartib` bor; `OrderItemCreate.name` saqlashdan OLDIN tartiblanadi (validator, mode=before)",
      callable(_dnt) and "_nom_tartib222" in inspect.getsource(schemas.OrderItemCreate))
_uof = inspect.getsource(crud.update_order_full)
check("S2 tahrir moslash kaliti — `_nom_kalit222` (raqam bosqichi, «x» / 1 / 2 bosqichlari, `_tahrir_loy_oldindan`); moslangan detal nomi yangilanadi",
      "_nom_kalit222(_oi220.name) != _nom_kalit222(nd.name)" in _uof and "key = (_nom_kalit222(oi.name)" in _uof
      and "nkey = (_nom_kalit222(nd.name)" in _uof and "oi.name = nd.name" in _uof and "_nom_kalit222(" in inspect.getsource(crud._tahrir_loy_oldindan)
      and "detal_nomi_tartib" in inspect.getsource(crud._clean_order_item_update))
import delivery_pdf                                # noqa: E402
import pdf_service                                 # noqa: E402
check("S3 ko'rsatish: yuk xati (asosiy + keyingi topshirish), umumiy hisobot, jamlanma, «BUYURTMA HISOBI» / taklif, Telegram yuk xabarlari",
      inspect.getsource(delivery_pdf.generate_delivery_pdf).count("_detal_nomi_tartib(") >= 2
      and "_detal_nomi_tartib(" in inspect.getsource(delivery_pdf.generate_summary_pdf)
      and "_detal_nomi_tartib(" in inspect.getsource(delivery_pdf._jamlanma_nomi)
      and "_dnt222(item.name)" in inspect.getsource(pdf_service.generate_nakladnoy)
      and open(os.path.join(ROOT, "main.py"), encoding="utf-8").read().count("nm = schemas.detal_nomi_tartib(di.order_item.name)") == 2)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("N — qoida jadvali")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
JADVAL = [("PADAKOLNIK", "Padakolnik"), ("15 LI NALIChNIK", "15 li nalichnik"), ("50 LI YuMALOK USTUN", "50 li yumalok ustun"),
          ("NAKSh", "Naksh"), ("10 LI YaRIM YuMALOK", "10 li yarim yumalok"), ("ZINA UChUN KOLIB", "Zina uchun kolib"),
          ("49  GA 3 LI USTUN", "49 ga 3 li ustun"), ("  ROM   KARNIZ  ", "Rom karniz"), ("AYMAKS MODEL", "Aymaks model"),
          ("O'RTA CHEKA", "O'rta cheka"), ("G'ISHT", "G'isht"), ("40 GA 4LI", "40 ga 4li"),
          ("Karniz 15 sm", "Karniz 15 sm"), ("karniz 15 sm", "karniz 15 sm"), ("Arka  naksh", "Arka  naksh"), ("BN_D1", "BN_D1"),
          ("AAA_DUP6", "AAA_DUP6"), ("karniz  q8", "karniz  q8"), ("15 LI", "15 li"), ("10 GA 5 LI", "10 ga 5 li"), ("Tekkiz Ustun 50 sm", "Tekkiz Ustun 50 sm"),
          ("Belbog plyastr 30x4", "Belbog plyastr 30x4"), ("Penoplast 14P", "Penoplast 14P"), ("V shakl", "V shakl"), ("Ya", "Ya"),
          ("15 li shift karniz", "15 li shift karniz"), ("173,5 li", "173,5 li"), ("(QOPLAMALI) ROM", "(qoplamali) rom"), ("", ""),
          ("MDF panel", "MDF panel"), ("AO Q4 Karniz", "AO Q4 Karniz"), ("Panel LED 20", "Panel LED 20"), ("LED", "Led"),
          ("KO'K KARNIZ", "Ko'k karniz"), ("TO'G'RI USTUN", "To'g'ri ustun"), ("BURCHAK O'NG", "Burchak o'ng"), ("KO‘K PANEL", "Ko‘k panel"),
          ("Burchak o'ng", "Burchak o'ng")]
_yom = [(a, b, xav(_dnt, a) if callable(_dnt) else None) for a, b in JADVAL if not callable(_dnt) or _dnt(a) != b]
check(f"N1 qoida jadvali ({len(JADVAL)} holat): butun katta harfli nom — tartiblanadi (digraflar, apostrof, bo'shliq); oddiy / aralash («MDF panel») "
      "/ «_» li kod — AYNAN xodim yozgandek", not _yom, _yom)
check("N2 `None` va matn emas — o'zgarishsiz; takror qo'llash — o'sha natija (idempotent)",
      callable(_dnt) and _dnt(None) is None and _dnt(15) == 15 and all(_dnt(_dnt(a)) == _dnt(a) for a, _b in JADVAL))

# ── ma'lumot
PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k222_a", PAROL, UserRole.ADMIN, "K222 Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="K222 Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000, volume_per_unit=1.0,
                 is_penoplast=True, is_default_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="K222 Kley", unit="kg", stock_quantity=1_000_000, price_per_unit=2_000, category="Kimyo")
PRJ = Project(company_id=1, client_name="K222 mijoz", project_name="K222 loyiha", client_phone="+998901112222", total_budget=0, total_paid=0)
US = Master(company_id=1, name="K222 Usta", phone="+998900002222", kpi_percent=10)
s.add_all([PENO, KLEY, PRJ, US])
s.flush()
REC = Recipe(company_id=1, name="K222 Oq marmar", batch_size_kg=100.0)
s.add(REC)
s.flush()
s.add(RecipeIngredient(recipe_id=REC.id, inventory_id=KLEY.id, quantity_kg=100.0))
s.commit()
ID = {"PENO": PENO.id, "PRJ": PRJ.id, "US": US.id, "REC": REC.id}
s.close()
A = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
A.post("/login", data={"username": "k222_a", "password": PAROL}, follow_redirects=False)
BUGUN = datetime.date.today()
_SANOQ = [0]


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {"_matn": r.text[:300]}


def detal(nom, L=10, coated=False):
    return {"name": nom, "category": "profil", "width": 20, "thickness": 10, "length": L, "quantity": 1, "unit_price": 50_000 * L,
            "is_coated": coated, "penoplast_id": ID["PENO"], "price_per_m3": None, "finished_product_id": None}


def tana(items):
    _SANOQ[0] += 1
    return {"project_id": ID["PRJ"], "order_type": "product", "recipe_id": ID["REC"], "master_id": ID["US"],
            "deadline": (BUGUN + datetime.timedelta(days=5)).isoformat(), "is_draft": False, "base_price": 0, "loy_kg": None,
            "notes": f"K222 {_SANOQ[0]}", "items": items}


def yarat(items):
    r = A.post("/api/orders?confirm_shortage=true", json=tana(items))
    return js(r).get("id") if r.status_code == 200 else None


def nomlar(oid):
    s2 = SessionLocal()
    try:
        return [(i.id, i.name) for i in sorted(s2.get(Order, oid).items, key=lambda x: x.id)]
    finally:
        s2.close()


def xom_nom(oid, juftlar):
    """bazaga to'g'ridan-to'g'ri eski (tartiblanmagan) nom — zip 222 dan oldingi yozuv"""
    s2 = SessionLocal()
    try:
        for it in sorted(s2.get(Order, oid).items, key=lambda x: x.id):
            if it.id in juftlar:
                it.name = juftlar[it.id]
        s2.commit()
    finally:
        s2.close()


def topshir(oid, faqat=None):
    h = js(A.get(f"/api/orders/{oid}/delivery-status")).get("items") or []
    items = [{"order_item_id": x["id"], "quantity": x["remaining"]} for x in h
             if (x.get("remaining") or 0) > 1e-6 and (faqat is None or x["id"] in faqat)]
    _SANOQ[0] += 1
    r = A.post("/api/deliveries", json={"order_id": oid, "items": items, "received_by": "K222", "notes": f"K222 yuk {_SANOQ[0]}",
                                        "transport_carrier": "", "transport_cost": 0, "transport_payer": "client"})
    return r.status_code, js(r)


def pdf_matn(url):
    r = A.get(url)
    if r.status_code != 200 or not r.content.startswith(b"%PDF"):
        return f"XATO {r.status_code} {r.text[:200]}"
    import pypdf
    return " ".join(" ".join((p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(r.content)).pages).split())


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A — server (saqlash)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
O1 = yarat([detal("PADAKOLNIK"), detal("15 LI NALIChNIK", 12), detal("Karniz 15 sm", 14), detal("49  GA 3 LI USTUN", 16)])
check("A1 yangi buyurtma: «PADAKOLNIK» → «Padakolnik», «15 LI NALIChNIK» → «15 li nalichnik», «49  GA 3 LI USTUN» → «49 ga 3 li ustun», «Karniz 15 sm» "
      "— o'zgarmaydi", O1 and sorted(n for _i, n in nomlar(O1)) == sorted(["Padakolnik", "15 li nalichnik", "Karniz 15 sm", "49 ga 3 li ustun"]),
      O1 and nomlar(O1))
O2 = yarat([detal("karniz  q8"), detal("BN_D1", 12)])
check("A2 oddiy yozilgan («karniz  q8») va «_» li kod («BN_D1») nom — AYNAN xodim yozgandek saqlanadi (avvalgidek)",
      O2 and sorted(n for _i, n in nomlar(O2)) == sorted(["karniz  q8", "BN_D1"]), O2 and nomlar(O2))

_tk = {"mijoz": "K222 taklif mijozi", "telefon": "+998901112223", "buyurtma": dict(tana([detal("ROM KARNIZ"), detal("USTUNGA KOPITEL", 8)]))}
_tk["buyurtma"].pop("project_id", None)
_rt = A.post("/api/takliflar", json=_tk)
TK = (js(_rt).get("taklif") or {}).get("id")
s3 = SessionLocal()
_tana = None
if TK:
    from models import Taklif                      # noqa: E402
    _tana = json.loads(s3.get(Taklif, TK).tana or "{}")
s3.close()
check("A3 taklif tanasida nomlar tartiblangan («Rom karniz», «Ustunga kopitel»)",
      _rt.status_code == 200 and _tana and sorted(i.get("name") for i in _tana.get("items") or []) == ["Rom karniz", "Ustunga kopitel"],
      (_rt.status_code, str(js(_rt))[:200], _tana and [i.get("name") for i in _tana.get("items") or []]))
_rr = A.post(f"/api/takliflar/{TK}/rasmiylashtir?confirm_shortage=true",
             json={"loyiha_id": ID["PRJ"], "buyurtma": dict(_tk["buyurtma"], items=[detal("ROM KARNIZ"), detal("USTUNGA KOPITEL", 8)])})
OR3 = js(_rr).get("id") or js(_rr).get("order_id")
check("A3b taklifni rasmiylashtirish (forma xom nom yuborsa ham) — buyurtma nomlari tartiblangan",
      _rr.status_code == 200 and OR3 and sorted(n for _i, n in nomlar(OR3)) == ["Rom karniz", "Ustunga kopitel"], (_rr.status_code, str(js(_rr))[:300]))

_i4 = nomlar(O1)[0][0]
_r4 = A.put(f"/api/order-items/{_i4}", json={"name": "ROM  KARNIZ BAZA"})
check("A4 bitta detal tahriri (`PUT /api/order-items/{id}`): «ROM  KARNIZ BAZA» → «Rom karniz baza»",
      _r4.status_code == 200 and dict(nomlar(O1)).get(_i4) == "Rom karniz baza", (_r4.status_code, _r4.text[:200], nomlar(O1)))

# eski buyurtma (zip 222 dan oldingi — bazada xom nom, bittasi topshirilgan): forma saqlangan (xom) nomni yuboradi
O5 = yarat([detal("Eski 1", 20, True), detal("Eski 2", 10)])
_n5 = nomlar(O5)
xom_nom(O5, {_n5[0][0]: "49  GA 3 LI USTUN", _n5[1][0]: "PADAKOLNIK"})
_t5 = topshir(O5, faqat={_n5[0][0]})


def _tahrir(oid, raqam, uzun2=None):
    s2 = SessionLocal()
    try:
        its = sorted(s2.get(Order, oid).items, key=lambda x: x.id)
        tt = tana([dict(detal(it.name, float(it.length), bool(it.is_coated)), **({"id": it.id} if raqam else {})) for it in its])
    finally:
        s2.close()
    tt["items"].reverse()                          # forma tartibi — saqlanganga teskari (zip 220)
    if uzun2 is not None:
        tt["items"][0]["length"] = uzun2
        tt["items"][0]["unit_price"] = 50_000 * uzun2
    return A.put(f"/api/orders/{oid}?confirm_shortage=true", json=tt)


def _topshirilgan(oid):
    return {x["id"]: round(float(x.get("delivered") or 0), 4) for x in (js(A.get(f"/api/orders/{oid}/delivery-status")).get("items") or [])}


_d5 = _topshirilgan(O5)
_r5 = _tahrir(O5, True, uzun2=14)
check("A5 eski buyurtma tahriri (raqam bilan, ikki bo'shliqli topshirilgan «49  GA 3 LI USTUN»): 200, o'sha detallar (raqamlar), nomlar tartiblangan, "
      "topshirilgani o'zgarmadi",
      _t5[0] == 200 and _r5.status_code == 200 and [i for i, _n in nomlar(O5)] == [i for i, _n in _n5]
      and dict(nomlar(O5)) == {_n5[0][0]: "49 ga 3 li ustun", _n5[1][0]: "Padakolnik"} and _topshirilgan(O5) == _d5 and _d5.get(_n5[0][0], 0) > 0,
      (_t5[0], _r5.status_code, _r5.text[:300], nomlar(O5), _d5, _topshirilgan(O5)))
O6 = yarat([detal("Eski 3", 20, True), detal("Eski 4", 10)])
_n6 = nomlar(O6)
xom_nom(O6, {_n6[0][0]: "49  GA 3 LI USTUN", _n6[1][0]: "15  LI  NALIChNIK"})
_t6 = topshir(O6, faqat={_n6[0][0]})
_d6 = _topshirilgan(O6)
_r6 = _tahrir(O6, False)
check("A5b eski ochiq sahifa (raqamsiz) — ham 200, o'sha detallar, nomlar tartiblangan, topshirilgani o'zgarmadi (asl: tartiblangan nom «nomi o'zgargan "
      "topshirilgan detal» bo'lardi)",
      _t6[0] == 200 and _r6.status_code == 200 and [i for i, _n in nomlar(O6)] == [i for i, _n in _n6]
      and dict(nomlar(O6)) == {_n6[0][0]: "49 ga 3 li ustun", _n6[1][0]: "15 li nalichnik"} and _topshirilgan(O6) == _d6,
      (_t6[0], _r6.status_code, _r6.text[:300], nomlar(O6)))
_nk = getattr(crud, "_nom_kalit222", None)
check("A6 moslash kaliti (`_nom_kalit222`, `_tahrir_loy_oldindan` ham shu): «49  GA 3 LI USTUN» = «49 ga 3 li ustun», boshqa nom — boshqa kalit",
      callable(_nk) and _nk("49  GA 3 LI USTUN") == _nk("49 ga 3 li ustun") == _nk(" 49 ga 3 LI  ustun ") and _nk("49 ga 3 li ustun") != _nk("49 ga 4 li ustun")
      and _nk(None) == "")

# eski buyurtmani o'zgarishsiz saqlash — jurnal: faqat «nomi: A → B» (review222 №2: ilgari «− PADAKOLNIK; + Padakolnik»)
O7 = yarat([detal("Eski 7", 20), detal("Eski 8", 10)])
_n7 = nomlar(O7)
xom_nom(O7, {_n7[0][0]: "PADAKOLNIK", _n7[1][0]: "ROM  KARNIZ"})
_t7 = topshir(O7)
_r7 = _tahrir(O7, True)
from models import ActivityLog                     # noqa: E402
_s7 = SessionLocal()
_j7 = _s7.query(ActivityLog).filter(ActivityLog.entity_type == "order", ActivityLog.entity_id == O7, ActivityLog.action == "updated") \
    .order_by(ActivityLog.id.desc()).first()
_j7 = (_j7.new_value or "") if _j7 else ""
_s7.close()
check("A7 eski buyurtmani o'zgarishsiz saqlash — jurnalda «nomi: PADAKOLNIK → Padakolnik», «nomi: ROM  KARNIZ → Rom karniz»; «−» / «+» (detal "
      "o'chirildi / qo'shildi) YO'Q",
      _t7[0] == 200 and _r7.status_code == 200 and "nomi: PADAKOLNIK → Padakolnik" in _j7 and "nomi: ROM  KARNIZ → Rom karniz" in _j7
      and "− PADAKOLNIK" not in _j7 and "+ Padakolnik" not in _j7, (_t7[0], _r7.status_code, _j7[:500]))
_r8 = A.post("/api/returns", json={"order_id": O7, "item_name": "PADAKOLNIK", "quantity": 1.0, "unit": "metr", "reason": "Mijoz iltimosi",
                                   "refund_amount": 0, "to_stock": False})
check("A8 detal raqamisiz (nom bo'yicha) qaytarish — tahrirdan keyin eski xom nom «PADAKOLNIK» bilan ham topiladi (review222 №6)",
      _r8.status_code == 200, (_r8.status_code, _r8.text[:300]))

# «Eng ko'p sotilgan tayyor mahsulotlar»: qaytarish eski xom nomda, detal — tartiblangan (review222 №3)
from models import FinishedProduct, ReturnItem, ReturnReason, OrderStatus      # noqa: E402
O9 = yarat([detal("Rom karniz", 10)])
s9 = SessionLocal()
_fp9 = FinishedProduct(company_id=1, name="ROM KARNIZ")
s9.add(_fp9)
s9.flush()
_o9 = s9.get(Order, O9)
_o9.items[0].finished_product_id = _fp9.id
_o9.status = OrderStatus.READY
_o9.completed_at = datetime.datetime.utcnow()
s9.add(ReturnItem(company_id=1, order_id=O9, item_name="ROM KARNIZ", quantity=0.5, unit="metr", reason=ReturnReason.CUSTOMER_REQUEST))
s9.commit()
with contextlib.redirect_stdout(io.StringIO()):
    _top9 = [x for x in services.get_top_finished_products_sold(s9, days=30, limit=50, company_id=1) if x.get("name") == "Rom karniz"]
s9.close()
check("A9 «Eng ko'p sotilgan tayyor mahsulotlar»: qaytarish (eski «ROM KARNIZ») tartiblangan «Rom karniz» detalidan ayiriladi (1 − 0,5 = 0,5)",
      len(_top9) == 1 and abs(float(_top9[0]["quantity"]) - 0.5) < 1e-9, _top9)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P — PDF matni (bazada eski xom nom)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
O8 = yarat([detal("Eski 5", 20, True), detal("Eski 6", 10)])
_n8 = nomlar(O8)
xom_nom(O8, {_n8[0][0]: "50 LI YuMALOK USTUN", _n8[1][0]: "ZINA UChUN KOLIB"})
TG = []
_asl_tg = main._send_telegram
main._send_telegram = lambda text, company_id=None, **k: TG.append(str(text))
try:
    _t8 = topshir(O8, faqat={_n8[0][0]})
finally:
    main._send_telegram = _asl_tg
DID = (_t8[1] or {}).get("delivery_id") or (_t8[1] or {}).get("id")
_p_yuk = pdf_matn(f"/api/deliveries/{DID}/pdf")
check("P1 yuk xati: asosiy jadvalda «50 li yumalok ustun (qoplamali)», «keyingi topshirish»da «Zina uchun kolib»; xom katta harfli nom YO'Q",
      _t8[0] == 200 and "50 li yumalok ustun (qoplamali)" in _p_yuk and "Zina uchun kolib" in _p_yuk
      and "YuMALOK" not in _p_yuk and "UChUN" not in _p_yuk, (_t8[0], _p_yuk[:600]))
_p_sum = pdf_matn(f"/api/orders/{O8}/summary-pdf")
check("P2 umumiy hisobot PDF — «50 li yumalok ustun», xom nom yo'q", "50 li yumalok ustun" in _p_sum and "YuMALOK" not in _p_sum, _p_sum[:500])
_p_jam = pdf_matn(f"/api/projects/{ID['PRJ']}/yuk-xatlari/jamlama-pdf")
check("P3 yuk xatlari jamlanmasi PDF — «50 li yumalok ustun», xom nom yo'q", "50 li yumalok ustun" in _p_jam and "YuMALOK" not in _p_jam, _p_jam[:500])
_p_nak = pdf_matn(f"/api/orders/{O8}/pdf")
check("P4 «BUYURTMA HISOBI» PDF — «50 li yumalok ustun (qoplamali)», «Zina uchun kolib», xom nom yo'q",
      "50 li yumalok ustun (qoplamali)" in _p_nak and "Zina uchun kolib" in _p_nak and "YuMALOK" not in _p_nak and "UChUN" not in _p_nak,
      _p_nak[:600])
s9 = SessionLocal()
if TK:
    _tq = s9.get(Taklif, TK)
    _tb = json.loads(_tq.tana)
    for _it in _tb.get("items") or []:
        _it["name"] = "ROM KARNIZ" if _it["name"] == "Rom karniz" else "USTUNGA KOPITEL"
    _tq.tana = json.dumps(_tb, ensure_ascii=False)
    s9.commit()
s9.close()
_p_tk = pdf_matn(f"/api/takliflar/{TK}/pdf")
check("P5 taklif PDF (tanada eski xom nom) — «Rom karniz», «Ustunga kopitel»", "Rom karniz" in _p_tk and "Ustunga kopitel" in _p_tk
      and "ROM KARNIZ" not in _p_tk, _p_tk[:500])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T — Telegram")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("T1 yuk xabarida «• 50 li yumalok ustun: …», xom nom yo'q", any("• 50 li yumalok ustun:" in t for t in TG) and not any("YuMALOK" in t for t in TG),
      TG[:3])

print(f"\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
