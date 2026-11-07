#!/usr/bin/env python3
"""
test_oracle265.py — kech202 (zip 265): xavfsizlik REJA 14-band (Fable F6) — «mavjudlik oracle'i» yopiladi.

NIMA UCHUN KERAK (zip 264 gacha — O'LCHANDI shu testning A / B bandlarida, asl kodda yiqiladi):
  B korxonasi buyurtmasiga A korxonasining usta / retsept id si yozilsa — 409 «Boshqa korxonaning ma'lumoti bilan bog'lab bo'lmaydi»;
  umuman YO'Q id (99999 …) yozilsa — SQLite da 200 (osilgan havola bazaga yozilardi), PostgreSQL da FK xatosi → 500 (+ xatolar jurnali).
  Id lar butun platforma bo'yicha umumiy, shuning uchun javob farqidan «shu id li usta / retsept boshqa korxonada BOR» degan xulosa
  chiqardi. Endi: `models._tenant_guard` YANGI qo'yilayotgan havola (yangi yozuvda — har havola, o'zgartirilgan yozuvda — faqat o'zgargan
  ustun) topilmasa ham `TenantMismatchError` beradi, `main.tenant_mismatch_handler` ikkalasiga bir xil 404 + bir xil matn qaytaradi.
  O'zgarmagan eski (osilgan) havolali yozuvni boshqa maydoni bo'yicha tahrirlash — avvalgidek ishlaydi (C bo'limi).
BO'LIMLAR: A — HTTP: yangi buyurtma (usta, retsept) — begona ↔ yo'q id javobi AYNAN bir xil, 404, ichki sabab ko'rinmaydi, bazaga hech narsa
           yozilmaydi; B — HTTP: buyurtmani tahrirlash (o'zgargan usta); C — ORM: yangi / o'zgargan / o'zgarmagan havola, o'z korxonasi;
           D — xatolar jurnali (ErrorLog) to'lmaydi, oddiy (o'z) bog'lanish 200.
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
Asl kodga (26fc68d — zip 264) qarshi YIQILADI, QULAMAYDI.
ISHLATISH: python3 tools/test_oracle265.py
"""
import os
import sys
import tempfile

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "oracle265_test"
_T = tempfile.mkdtemp(prefix="oracle265_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'oracle265_test.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "ADMIN_PASSWORD", "RESET_ADMIN_PASSWORD"):
    os.environ.pop(_k, None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import schemas                                 # noqa: E402
import models                                      # noqa: E402
import tenant_context                              # noqa: E402
from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import UserRole, Order, Master, Recipe, ErrorLog, TenantMismatchError   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from sqlalchemy import text as _sql                # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {REJIM}{label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {REJIM}{label}   {str(detail)[:700]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


PAROL = "Kuchli-Sinov-Parol-265"
YOQ_ID = 987654                            # hech qaysi korxonada yo'q id

with TestClient(main.app, base_url="https://testserver") as _c0:
    _c0.get("/login")

s = SessionLocal()
with tenant_context.system_context(s):
    if not s.query(Company).filter(Company.id == 2).first():
        s.add(Company(id=2, name="Oracle B korxona", code="ORACLE-B265"))
        s.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(s, "or_a_admin", PAROL, UserRole.ADMIN, "A Admin", company_id=1)
    auth.create_user(s, "or_b_admin", PAROL, UserRole.ADMIN, "B Admin", company_id=2)
    MA = crud.create_master(s, schemas.MasterCreate(name="OR265_A_Usta", phone="+998901000265"), company_id=1).id
    MB = crud.create_master(s, schemas.MasterCreate(name="OR265_B_Usta", phone="+998902000265"), company_id=2).id
    IA = crud.add_item(s, schemas.InventoryCreate(item_name="OR265_A_Mat", unit="kg", stock_quantity=100, price_per_unit=1000),
                       company_id=1).id
    IB = crud.add_item(s, schemas.InventoryCreate(item_name="OR265_B_Mat", unit="kg", stock_quantity=100, price_per_unit=1000),
                       company_id=2).id
    RA = crud.create_recipe(s, schemas.RecipeCreate(name="OR265_A_Ret", batch_size_kg=10,
                            ingredients=[schemas.RecipeIngredientCreate(inventory_id=IA, quantity_kg=1)]), company_id=1).id
    RB = crud.create_recipe(s, schemas.RecipeCreate(name="OR265_B_Ret", batch_size_kg=10,
                            ingredients=[schemas.RecipeIngredientCreate(inventory_id=IB, quantity_kg=1)]), company_id=2).id
    PB = crud.create_project(s, schemas.ProjectCreate(project_name="OR265_B_Loyiha", client_name="OR265 B Mijoz",
                                                      client_phone="+998902111265"), company_id=2).id
s.close()


def kirgan(login, ip):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False, client=(ip, 50000))
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), f"{login} kirmadi: {r.status_code} {r.text[-200:]}"
    return c


CB = kirgan("or_b_admin", "203.0.113.65")


def sanoq(model, **filtr):
    d = SessionLocal()
    try:
        with tenant_context.system_context(d):
            q = d.query(model)
            for k, v in filtr.items():
                q = q.filter(getattr(model, k) == v)
            return q.count()
    finally:
        d.close()


def xato_soni():
    return sanoq(ErrorLog)


def buyurtma_tanasi(**qosh):
    t = {"project_id": PB, "order_type": "product",
         "items": [{"name": "OR265 detal", "category": "panel", "quantity": 1, "unit_price": 1000}]}
    t.update(qosh)
    return t


def javob(r):
    return (r.status_code, js(r))


# ═══════════════════════════════════════════════════════════════════════════════════════════════
section("A — yangi buyurtma: begona id ↔ yo'q id — bir xil javob")
for maydon, begona, oziniki in (("master_id", MA, MB), ("recipe_id", RA, RB)):
    _b0, _x0 = sanoq(Order, project_id=PB), xato_soni()
    r_beg = CB.post("/api/orders", json=buyurtma_tanasi(**{maydon: begona}))
    r_yoq = CB.post("/api/orders", json=buyurtma_tanasi(**{maydon: YOQ_ID}))
    _b1, _x1 = sanoq(Order, project_id=PB), xato_soni()
    check(f"A1 {maydon}: begona (A) id va YO'Q id — status va tana AYNAN bir xil",
          javob(r_beg) == javob(r_yoq), (javob(r_beg), javob(r_yoq)))
    check(f"A2 {maydon}: ikkalasi ham 404", r_beg.status_code == 404 and r_yoq.status_code == 404,
          (r_beg.status_code, r_yoq.status_code))
    _d = str(js(r_beg).get("detail", ""))
    check(f"A3 {maydon}: matn — «topilmadi», ichki sabab (id, korxona raqami, model nomi) ko'rinmaydi",
          "topilmadi" in _d and str(begona) not in _d and str(YOQ_ID) not in _d and "Master" not in _d
          and "Recipe" not in _d and "company" not in _d.lower(), _d)
    check(f"A4 {maydon}: bazaga buyurtma yozilmadi (ikkala urinishda)", _b1 == _b0, (_b0, _b1))
    check(f"A5 {maydon}: xatolar jurnaliga yozuv tushmadi (500 emas)", _x1 == _x0, (_x0, _x1))
    r_oz = CB.post("/api/orders", json=buyurtma_tanasi(**{maydon: oziniki}))
    check(f"A6 {maydon}: o'z korxonasining id si — 200 (oddiy ish buzilmagan)", r_oz.status_code == 200,
          (r_oz.status_code, r_oz.text[:300]))

# ═══════════════════════════════════════════════════════════════════════════════════════════════
section("B — buyurtmani tahrirlash: o'zgargan usta")
r0 = CB.post("/api/orders", json=buyurtma_tanasi(master_id=MB))
OID = js(r0).get("id") or js(r0).get("order_id") or (js(r0).get("order") or {}).get("id")
check("B0 tahrir uchun B buyurtmasi yaratildi", r0.status_code == 200 and OID, (r0.status_code, r0.text[:300]))
if OID:
    r_beg = CB.put(f"/api/orders/{OID}", json=buyurtma_tanasi(master_id=MA))
    r_yoq = CB.put(f"/api/orders/{OID}", json=buyurtma_tanasi(master_id=YOQ_ID))
    check("B1 tahrirda begona usta ↔ yo'q usta — status va tana AYNAN bir xil", javob(r_beg) == javob(r_yoq),
          (javob(r_beg), javob(r_yoq)))
    check("B2 ikkalasi ham 404", r_beg.status_code == 404 and r_yoq.status_code == 404, (r_beg.status_code, r_yoq.status_code))

    def _usta():
        d = SessionLocal()
        try:
            with tenant_context.system_context(d):
                return d.query(Order.master_id).filter(Order.id == OID).scalar()
        finally:
            d.close()
    check("B3 buyurtmaning ustasi o'zgarmadi (o'z ustasi qoldi)", _usta() == MB, _usta())
    r_oz = CB.put(f"/api/orders/{OID}", json=buyurtma_tanasi(master_id=None, notes="OR265 tahrir"))
    check("B4 ustani olib tashlab tahrirlash — 200", r_oz.status_code == 200, (r_oz.status_code, r_oz.text[:300]))

# ═══════════════════════════════════════════════════════════════════════════════════════════════
section("C — ORM qo'riqchisi")


def orm(fn):
    d = SessionLocal()
    try:
        with tenant_context.system_context(d):
            fn(d)
            d.commit()
        return "OK"
    except TenantMismatchError as e:
        d.rollback()
        return "RAD:" + str(e)
    except Exception as e:                 # noqa: BLE001
        d.rollback()
        return f"BOSHQA:{type(e).__name__}"
    finally:
        d.close()


def _yangi(master_id):
    def f(d):
        d.add(Order(project_id=PB, company_id=2, master_id=master_id, order_type=models.OrderType.PRODUCT))
    return f


_rb = orm(_yangi(MA))
_ry = orm(_yangi(YOQ_ID))
check("C1 yangi yozuv, begona havola — rad (TenantMismatchError, eski xulq)", _rb.startswith("RAD:"), _rb)
check("C2 yangi yozuv, YO'Q havola — xuddi shu sinf bilan rad (ilgari SQLite da yozilardi, PG da FK xatosi)",
      _ry.startswith("RAD:") and "topilmadi" in _ry, _ry)
check("C3 yangi yozuv, o'z havolasi — yoziladi", orm(_yangi(MB)) == "OK")
check("C3b yangi yozuv, havolasiz — yoziladi", orm(_yangi(None)) == "OK")

# O'zgarmagan ESKI osilgan havola: bazaga to'g'ridan-to'g'ri (SQL) yozilgan buyurtma — boshqa maydoni tahrirlanadi
_osilgan_id = None
if not PG_URL:
    d = SessionLocal()
    try:
        with tenant_context.system_context(d):
            _o = Order(project_id=PB, company_id=2, master_id=MB, order_type=models.OrderType.PRODUCT, notes="OR265 osilgan")
            d.add(_o)
            d.commit()
            _osilgan_id = _o.id
            d.execute(_sql("UPDATE orders SET master_id = :m WHERE id = :i"), {"m": YOQ_ID, "i": _osilgan_id})
            d.commit()
    finally:
        d.close()

    def _boshqa_maydon(d):
        o = d.query(Order).filter(Order.id == _osilgan_id).first()
        o.notes = "OR265 osilgan — tahrirlandi"
    _r = orm(_boshqa_maydon)
    check("C4 osilgan (o'zgarmagan) havolali eski yozuvning BOSHQA maydonini tahrirlash — yoziladi (eski ish buzilmaydi)",
          _r == "OK", _r)

    def _kuzatilgan_boshqa(d):
        o = d.query(Order).filter(Order.id == _osilgan_id).first()
        o.qoplama_retsept_id = RB          # qo'riqchi kuzatadigan havola (_TENANT_REFS), LEKIN osilgan master_id emas
    _r = orm(_kuzatilgan_boshqa)
    check("C5 osilgan master_id li yozuvda BOSHQA kuzatiladigan havola (qoplama_retsept_id) o'zgarsa — yoziladi (faqat o'zgargan ustun)",
          _r == "OK", _r)

    # Osilgan OTA-yozuv (project_id) — o'zgarmagan; boshqa kuzatiladigan havola (master_id) o'zgaradi
    d = SessionLocal()
    try:
        with tenant_context.system_context(d):
            _o2 = Order(project_id=PB, company_id=2, master_id=None, order_type=models.OrderType.PRODUCT, notes="OR265 osilgan ota")
            d.add(_o2)
            d.commit()
            _osilgan_ota = _o2.id
            d.execute(_sql("UPDATE orders SET project_id = :p WHERE id = :i"), {"p": YOQ_ID, "i": _osilgan_ota})
            d.commit()
    finally:
        d.close()

    def _ota_osilgan_usta_qoy(d):
        o = d.query(Order).filter(Order.id == _osilgan_ota).first()
        o.master_id = MB
    _r = orm(_ota_osilgan_usta_qoy)
    check("C5b osilgan (o'zgarmagan) ota-yozuvli (project_id) yozuvda boshqa havola o'zgarsa — yoziladi (ota faqat o'zgarsa tekshiriladi)",
          _r == "OK", _r)
    def _expired_qayta(d):
        o = d.query(Order).filter(Order.id == _osilgan_id).first()
        d.expire(o)                         # atribut eski qiymati noma'lum («o'zgargan» ko'rinadi)
        o.master_id = YOQ_ID                # bazadagi AYNAN o'sha osilgan qiymat qayta yoziladi
        o.notes = "OR265 expired qayta"
    _r = orm(_expired_qayta)
    check("C4c expired atributga bazadagi o'sha osilgan qiymat qayta yozilsa — o'zgarmagan hisoblanadi, yoziladi (review265 PAST-3)",
          _r == "OK", _r)

    # review265 PAST-2: qaytgan detal omborga — detaldagi penoplast bazadan butunlay o'chgan (osilgan id) bo'lsa ham qaytarish to'xtamaydi
    d = SessionLocal()
    try:
        with tenant_context.system_context(d):
            _pen = crud.add_item(d, schemas.InventoryCreate(item_name="OR265 o'chadigan penoplast", unit="m3", stock_quantity=1,
                                                            price_per_unit=1000), company_id=2)
            _pen_id = _pen.id
            _ord_q = Order(project_id=PB, company_id=2, order_type=models.OrderType.PRODUCT, notes="OR265 qaytarish")
            d.add(_ord_q)
            d.flush()
            _it_q = models.OrderItem(order_id=_ord_q.id, company_id=2, name="OR265 qaytgan detal", category="panel", quantity=2,
                                     width=10, thickness=10, length=1, penoplast_id=_pen_id)
            d.add(_it_q)
            d.commit()
            _it_q_id, _ord_q_id = _it_q.id, _ord_q.id
            d.execute(_sql("DELETE FROM inventory_movements WHERE inventory_id = :i"), {"i": _pen_id})
            d.execute(_sql("DELETE FROM inventory WHERE id = :i"), {"i": _pen_id})
            d.commit()
    finally:
        d.close()
    d = SessionLocal()
    try:
        with tenant_context.system_context(d):
            _it_q = d.query(models.OrderItem).filter(models.OrderItem.id == _it_q_id).first()
            try:
                with contextlib.redirect_stdout(_quiet):
                    _fp_q = crud.add_returned_to_stock(d, _it_q, 1, "OR265 qaytarish", order_id=_ord_q_id)
                _natija_q = ("OK", getattr(_fp_q, "penoplast_id", "yo'q"), getattr(_fp_q, "id", None))
            except TenantMismatchError as e:
                d.rollback()
                _natija_q = ("RAD", str(e), None)
    finally:
        d.close()
    check("C4d qaytgan detal omborga: detaldagi penoplast bazadan o'chgan — qaytarish yoziladi, partiyada penoplast bo'sh",
          _natija_q[0] == "OK" and _natija_q[1] is None and _natija_q[2], _natija_q)
else:
    print("  · [PG] C4 / C5 / C5b — PostgreSQL FK osilgan havolani yozdirmaydi (holat faqat FK siz eski ustunlarda bo'ladi) — SQLite da sinaladi")


def _ozgart(master_id):
    def f(d):
        o = d.query(Order).filter(Order.project_id == PB, Order.master_id == MB).order_by(Order.id).first()
        o.master_id = master_id
    return f


_rb = orm(_ozgart(MA))
_ry = orm(_ozgart(YOQ_ID))
check("C6 o'zgartirilgan yozuv: begona havola — rad", _rb.startswith("RAD:"), _rb)
check("C7 o'zgartirilgan yozuv: YO'Q havolaga o'zgartirish — rad (topilmadi)", _ry.startswith("RAD:") and "topilmadi" in _ry, _ry)

# Ota-yozuv qoidasi o'zgartirilgan yozuvda: buyurtma detalini (OrderItem — order_id faqat _TENANT_RULES da, _TENANT_REFS da emas)
# umuman yo'q buyurtmaga ko'chirish
d = SessionLocal()
try:
    with tenant_context.system_context(d):
        _ord_det = d.query(Order.id).filter(Order.project_id == PB).order_by(Order.id).first()[0]
        _it = models.OrderItem(order_id=_ord_det, company_id=2, name="OR265 detal ORM", category="panel", quantity=1)
        d.add(_it)
        d.commit()
        _DET_ID = _it.id
finally:
    d.close()


def _detal_kochir(order_id):
    def f(d):
        it = d.query(models.OrderItem).filter(models.OrderItem.id == _DET_ID).first()
        it.order_id = order_id
    return f


_rd = orm(_detal_kochir(YOQ_ID))
check("C7b o'zgartirilgan yozuv: ota-yozuvni (OrderItem.order_id) YO'Q buyurtmaga o'zgartirish — rad (topilmadi)",
      _rd.startswith("RAD:") and "topilmadi" in _rd, _rd)
check("C7c detal o'z buyurtmasida qoldi", sanoq(models.OrderItem, id=_DET_ID, order_id=_ord_det) == 1)

# Ota-yozuv qoidasi (_TENANT_RULES): yangi buyurtma umuman yo'q loyihaga
_rp = orm(lambda d: d.add(Order(project_id=YOQ_ID, order_type=models.OrderType.PRODUCT)))
check("C8 yangi yozuv, YO'Q ota-yozuv (project_id) — rad (topilmadi)", _rp.startswith("RAD:") and "topilmadi" in _rp, _rp)
check("C9 qo'riqchi funksiyalarida yangi parametr bor (manba)",
      "yoqni_tekshir" in open(os.path.join(ROOT, "models.py"), encoding="utf-8").read())
_QOLDA_ID = 876543


def _bir_flushda(d):
    # ota-yozuv (usta) id si qo'lda berilgan va hali bazada YO'Q — bola (buyurtma) bilan BIR flush da yoziladi
    d.add(Master(id=_QOLDA_ID, name="OR265 bir flush usta", phone="+998903000265", company_id=2))
    d.add(Order(project_id=PB, company_id=2, master_id=_QOLDA_ID, order_type=models.OrderType.PRODUCT, notes="OR265 bir flush"))


_r = orm(_bir_flushda)
check("C10 havola qilingan yozuv SHU flush da yangi (id qo'lda) — topilmadi deb rad etilmaydi, ikkalasi yoziladi",
      _r == "OK" and sanoq(Master, id=_QOLDA_ID) == 1 and sanoq(Order, master_id=_QOLDA_ID) == 1, _r)


def _bir_flushda_boshqa_id(d):
    # shu flush da BOSHQA id li yangi usta bor, buyurtma esa umuman yo'q ustaga ishora qiladi
    d.add(Master(id=_QOLDA_ID + 1, name="OR265 bir flush usta 2", phone="+998903000266", company_id=2))
    d.add(Order(project_id=PB, company_id=2, master_id=YOQ_ID, order_type=models.OrderType.PRODUCT, notes="OR265 bir flush 2"))


_r = orm(_bir_flushda_boshqa_id)
check("C10b shu flush dagi yangi yozuv BOSHQA id li bo'lsa — yo'q havola baribir rad, hech biri yozilmaydi",
      _r.startswith("RAD:") and "topilmadi" in _r and sanoq(Master, id=_QOLDA_ID + 1) == 0, _r)

# ═══════════════════════════════════════════════════════════════════════════════════════════════
section("D — javob ishlovchisi")
check("D1 umumiy matn modulda (`main.TENANT_BOG_XATO_MATNI`) va 404", lambda: "topilmadi" in main.TENANT_BOG_XATO_MATNI)
_s0 = sanoq(Master)
r = CB.post("/api/orders", json=buyurtma_tanasi(master_id=MA, recipe_id=YOQ_ID))
check("D2 bir so'rovda begona usta + yo'q retsept — 404, bitta umumiy matn", r.status_code == 404
      and js(r).get("detail") == main.TENANT_BOG_XATO_MATNI, (r.status_code, r.text[:300]))
check("D3 ustalar soni o'zgarmadi", sanoq(Master) == _s0)
_jurnal = io.StringIO()
with contextlib.redirect_stdout(_jurnal):
    r = CB.post("/api/orders", json=buyurtma_tanasi(master_id=YOQ_ID))
_j = _jurnal.getvalue()
check("D5 ichki sabab SERVER jurnaliga yoziladi (yo'l + model + ustun), javobda emas (review265 O'RTA-1)",
      r.status_code == 404 and "/api/orders" in _j and "master_id" in _j and str(YOQ_ID) in _j
      and str(YOQ_ID) not in r.text, (r.status_code, _j[-300:]))
check("D4 retseptlar o'z joyida (A retsepti A da)", sanoq(Recipe, id=RA, company_id=1) == 1)
_ = models  # modul import qilingan (qo'riqchi ro'yxatga olingan)

print(f"\nNATIJA: {OK} / {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for x in FAILED:
        print("  -", x)
sys.exit(1 if FAIL else 0)
