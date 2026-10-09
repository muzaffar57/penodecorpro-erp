#!/usr/bin/env python3
"""
test_retsept_oyna.py — kech133 (zip 157): «Loy retseptlari» oynalari — SERVER (takror nom, o'chirilgan material) va SHABLON (statik).

NIMA UCHUN KERAK (egasi tanlovi 09.10 «Retsept oynasi izohi»; O'LCHANGAN — work/k157/olchov157.py, SQLite va PG, zip 156 kodi)
-------------------------------------------------------------------------------------------------------------------------------
  * Tahrir oynasida «Tarkibi» ostidagi izoh bo'sh (`&nbsp;`) edi — yangi retsept oynasida «Har biridan — «Partiya hajmi (kg)» uchun
    kerak miqdor (kg)» (egasi kuzatuvi, kech132).
  * Bir xil nomli retsept (yangi yoki tahrirda boshqa retseptning nomi) — 500 «Serverda kutilmagan xato yuz berdi» va xatolar jurnaliga
    yozuv (bazadagi `uq_recipes_company_name`). Endi 409 va sababi: ««…» nomli loy retsepti allaqachon bor — boshqa nom yozing …».
  * O'chirilgan (PG da yashirilgan, `is_deleted`) material retseptda qoladi va kartada ko'rinadi; tahrirda «?» bo'lib chiqar, saqlashda
    retseptdan JIMGINA o'chardi (UI — test_retsept_oyna_ui.py). Server uni PUT da QABUL QILADI (shu korxonaniki) — shu shart sinaladi.

BO'LIMLAR
  A — takror nom: POST / PUT → 409 (matn AYNAN), yozuv o'zgarmaydi, xatolar jurnaliga yozilmaydi; chetidagi bo'shliq bilan ham; o'z nomi
      bilan PUT — 200; boshqa korxona — o'sha nom bemalol; katta-kichik harf farqli nom — eskisidek (bazadagi qoida bilan bir xil);
      bir vaqtdagi so'rov (oldingi tekshiruv o'tib, bazaning o'zi rad etsa) — ham 409, tarkib o'chmaydi; nom bilan bog'liq bo'lmagan
      IntegrityError — 409 deb NIQOBLANMAYDI (500, jurnalga).
  B — o'chirilgan material: PUT tarkibida qoladi; /recipes sahifasi tahrir tugmasiga material nomi va birligini beradi.
  C — recipes.html (statik): tahrir oynasi izohi / sarlavhasi / tugmalari — yangi oynadagi bilan AYNAN; «Yopish» yorlig'i; nom
      maydonida `maxlength` = server chegarasi (100); `|| 100` (bo'sh hajm → 100) va `collectIngredients` (miqdorsiz qatorni tashlash) YO'Q;
      JS son chegarasi = `crud._UPD_SON_CHEGARA`; qator raqami tasodifiy emas.
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
Asl kodga (zip 156) qarshi YIQILADI (QULAMAYDI).
ISHLATISH: python3 tools/test_retsept_oyna.py
"""
import os
import re
import sys
import tempfile

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "retsept_oyna157_test"
_DB = os.path.join(tempfile.gettempdir(), "retsept_oyna157_test.db")
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
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("BACKUP_TELEGRAM_CHAT_ID", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import crud                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, Recipe, RecipeIngredient, ErrorLog  # noqa: E402
from production_models import Company              # noqa: E402
from sqlalchemy.exc import IntegrityError          # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

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
        print(f"  ✗ {REJIM}{label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


# ══════════════════════════════════════════════════════════════
# Fikstura: 1 — korxona A (admin), 2 — korxona B (admin)
# ══════════════════════════════════════════════════════════════
db = SessionLocal()
if not db.query(Company).filter(Company.id == 2).first():
    db.add(Company(id=2, name="BBB_RETSEPT_157"))
db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(db, "ro_a", "Parol123!", UserRole.ADMIN, "RO A admin", company_id=1)
    auth.create_user(db, "ro_b", "Parol123!", UserRole.ADMIN, "RO B admin", company_id=2)
MA = Inventory(company_id=1, item_name="RO157 Kley", unit="kg", stock_quantity=5, price_per_unit=1000, min_stock=0,
               category="Kimyoviy qo'shimchalar")
MB = Inventory(company_id=1, item_name="RO157 Qum", unit="kg", stock_quantity=5, price_per_unit=1000, min_stock=0,
               category="Qattiq qotishmalar")
MC = Inventory(company_id=1, item_name="RO157 Bo'yoq", unit="l", stock_quantity=5, price_per_unit=1000, min_stock=0,
               category="Boshqa")
MBK = Inventory(company_id=2, item_name="RO157 B Kley", unit="kg", stock_quantity=5, price_per_unit=1000, min_stock=0,
                category="Kimyoviy qo'shimchalar")
db.add_all([MA, MB, MC, MBK])
db.flush()
R1 = Recipe(company_id=1, name="RO157 Kvars", batch_size_kg=120, notes="birinchi")
R2 = Recipe(company_id=1, name="RO157 Marmar", batch_size_kg=150, notes="ikkinchi")
db.add_all([R1, R2])
db.flush()
db.add_all([RecipeIngredient(recipe_id=R1.id, inventory_id=MA.id, quantity_kg=2.5),
            RecipeIngredient(recipe_id=R1.id, inventory_id=MB.id, quantity_kg=60),
            RecipeIngredient(recipe_id=R2.id, inventory_id=MA.id, quantity_kg=3),
            RecipeIngredient(recipe_id=R2.id, inventory_id=MC.id, quantity_kg=1.2)])
db.commit()
A_ID, B_ID, C_ID, BK_ID, R1_ID, R2_ID = MA.id, MB.id, MC.id, MBK.id, R1.id, R2.id
db.close()


def kirgan(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": "Parol123!"}, follow_redirects=False)
    assert r.status_code == 302, f"{login} kirmadi: {r.status_code}"
    return c


CA, CBB = kirgan("ro_a"), kirgan("ro_b")


def retsept(rid):
    """Bazadagi holat: (nom, hajm, izoh, [(material, miqdor), …] — tartiblangan)."""
    s = SessionLocal()
    try:
        r = s.query(Recipe).filter(Recipe.id == rid).first()
        if r is None:
            return None
        ing = sorted((i.inventory_id, float(i.quantity_kg))
                     for i in s.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == rid).all())
        return (r.name, float(r.batch_size_kg), r.notes, ing)
    finally:
        s.close()


def retseptlar_soni(cid):
    s = SessionLocal()
    try:
        return s.query(Recipe).filter(Recipe.company_id == cid).count()
    finally:
        s.close()


def jurnal_soni():
    s = SessionLocal()
    try:
        return s.query(ErrorLog).count()
    finally:
        s.close()


def band_matn(nom):
    return f"«{nom}» nomli loy retsepti allaqachon bor — boshqa nom yozing (yoki o'sha retseptni tahrirlang)"


def tana(nom, hajm=100, izoh=None, tarkib=None):
    return {"name": nom, "batch_size_kg": hajm, "notes": izoh,
            "ingredients": tarkib if tarkib is not None else [{"inventory_id": A_ID, "quantity_kg": 1}]}


R1_ASL, R2_ASL = retsept(R1_ID), retsept(R2_ID)

# ══════════════════════════════════════════════════════════════
section("A. Takror nom — 409 (ilgari 500)")
# ══════════════════════════════════════════════════════════════
_j0, _n0 = jurnal_soni(), retseptlar_soni(1)
r = CA.post("/api/recipes", json=tana("RO157 Kvars"))
check("A1 yangi retsept boshqasining nomi bilan → 409, sababi AYNAN (««RO157 Kvars» nomli loy retsepti allaqachon bor — boshqa nom "
      "yozing (yoki o'sha retseptni tahrirlang)»); retsept qo'shilmadi; xatolar jurnaliga YOZILMADI",
      r.status_code == 409 and js(r).get("detail") == band_matn("RO157 Kvars") and retseptlar_soni(1) == _n0
      and jurnal_soni() == _j0, (r.status_code, r.text[:300], retseptlar_soni(1), _n0, jurnal_soni(), _j0))
r = CA.post("/api/recipes", json=tana("   RO157 Kvars  "))
check("A2 chetida bo'shliq bilan («   RO157 Kvars  ») — ham 409 (server nomni bo'shliqsiz yozadi), sababda nom bo'shliqsiz",
      r.status_code == 409 and js(r).get("detail") == band_matn("RO157 Kvars") and retseptlar_soni(1) == _n0,
      (r.status_code, r.text[:300]))
_j0 = jurnal_soni()
r = CA.put(f"/api/recipes/{R2_ID}", json=tana("RO157 Kvars", 150, "ikkinchi",
                                               [{"inventory_id": A_ID, "quantity_kg": 3}, {"inventory_id": C_ID, "quantity_kg": 1.2}]))
check("A3 tahrirda BOSHQA retseptning nomiga o'zgartirish → 409, sababi AYNAN; ikkinchi retsept (nomi, hajmi, izohi, TARKIBI) "
      "o'zgarmadi; jurnalga yozilmadi",
      r.status_code == 409 and js(r).get("detail") == band_matn("RO157 Kvars") and retsept(R2_ID) == R2_ASL and jurnal_soni() == _j0,
      (r.status_code, r.text[:300], retsept(R2_ID)))
r = CA.put(f"/api/recipes/{R1_ID}", json=tana("RO157 Kvars", 125, "birinchi",
                                               [{"inventory_id": A_ID, "quantity_kg": 2.5}, {"inventory_id": B_ID, "quantity_kg": 60}]))
check("A4 o'z nomi bilan tahrir (hajm 120 → 125) — 200, saqlandi (o'zini «band» demaydi)",
      r.status_code == 200 and retsept(R1_ID) == ("RO157 Kvars", 125.0, "birinchi", sorted([(A_ID, 2.5), (B_ID, 60.0)])),
      (r.status_code, r.text[:300], retsept(R1_ID)))
r = CBB.post("/api/recipes", json=tana("RO157 Kvars", tarkib=[{"inventory_id": BK_ID, "quantity_kg": 1}]))
check("A5 boshqa korxona (B) — o'sha nom bemalol (qoida korxona ichida) — 200",
      r.status_code == 200 and js(r).get("name") == "RO157 Kvars" and retseptlar_soni(2) == 1, (r.status_code, r.text[:300]))
r = CA.post("/api/recipes", json=tana("ro157 kvars"))
check("A6 katta-kichik harfi boshqa nom («ro157 kvars») — eskisidek 200 (bazadagi `uq_recipes_company_name` qoidasi bilan bir xil)",
      r.status_code == 200 and js(r).get("name") == "ro157 kvars", (r.status_code, r.text[:300]))
_YANGI_ID = js(r).get("id")

# A7–A8: oldingi tekshiruv o'tib ketgan holat (bir vaqtdagi ikki so'rov) — bazaning o'zi rad etadi
_asl_band = getattr(main, "_retsept_nomi_band", None)
_sanoq = {"n": 0}


def _birinchisi_yolgon(*a, **k):
    """Birinchi chaqiruv (oldingi tekshiruv) — «band emas» (bir vaqtdagi so'rov), keyingisi — haqiqiy javob."""
    _sanoq["n"] += 1
    return False if _sanoq["n"] == 1 else _asl_band(*a, **k)


_j0, _n0 = jurnal_soni(), retseptlar_soni(1)
if _asl_band is not None:
    main._retsept_nomi_band = _birinchisi_yolgon
try:
    r = CA.post("/api/recipes", json=tana("RO157 Marmar"))
    _st1, _d1 = r.status_code, js(r).get("detail")
    _sanoq["n"] = 0
    r = CA.put(f"/api/recipes/{R1_ID}", json=tana("RO157 Marmar", 125, "birinchi", [{"inventory_id": A_ID, "quantity_kg": 9}]))
    _st2, _d2 = r.status_code, js(r).get("detail")
finally:
    if _asl_band is not None:
        main._retsept_nomi_band = _asl_band
check("A7 bir vaqtdagi so'rov (oldingi tekshiruv o'tib, bazaning o'zi rad etsa): yangi — 409 sababi bilan, retsept qo'shilmadi; tahrir — "
      "409, birinchi retseptning nomi va TARKIBI o'zgarmadi (tarkib o'chib ketmadi); jurnalga yozilmadi",
      _asl_band is not None and _st1 == 409 and _d1 == band_matn("RO157 Marmar") and _st2 == 409 and _d2 == band_matn("RO157 Marmar")
      and retseptlar_soni(1) == _n0 and retsept(R1_ID) == ("RO157 Kvars", 125.0, "birinchi", sorted([(A_ID, 2.5), (B_ID, 60.0)]))
      and jurnal_soni() == _j0, (_st1, _d1, _st2, _d2, retseptlar_soni(1), _n0, retsept(R1_ID), jurnal_soni(), _j0))

_asl_create = crud.create_recipe


def _boshqa_integrity(*a, **k):
    raise IntegrityError("INSERT INTO boshqa", {}, Exception("boshqa cheklov (nom emas)"))


_j0 = jurnal_soni()
crud.create_recipe = _boshqa_integrity
try:
    r = CA.post("/api/recipes", json=tana("RO157 Yangi nom"))
finally:
    crud.create_recipe = _asl_create
check("A8 nom bilan bog'liq BO'LMAGAN IntegrityError — «nom band» deb NIQOBLANMAYDI: 500, xatolar jurnaliga yoziladi",
      r.status_code == 500 and "allaqachon bor" not in r.text and jurnal_soni() == _j0 + 1, (r.status_code, r.text[:300], jurnal_soni(), _j0))
r = CA.post("/api/recipes", json=tana("RO157 Yangi nom"))
check("A9 yangi (band bo'lmagan) nom — 200 (oddiy yo'l buzilmadi)", r.status_code == 200 and js(r).get("name") == "RO157 Yangi nom",
      (r.status_code, r.text[:300]))

# ══════════════════════════════════════════════════════════════
section("B. O'chirilgan (yashirilgan) material — tarkibda qoladi")
# ══════════════════════════════════════════════════════════════
s = SessionLocal()
s.query(Inventory).filter(Inventory.id == C_ID).update({"is_deleted": True})
s.commit()
s.close()
r = CA.get("/api/inventory")
_royxat = [x.get("id") for x in (js(r) if isinstance(js(r), list) else [])]
check("B1 yashirilgan material Omborxona ro'yxatida (`/api/inventory`) YO'Q — tahrir oynasi uni ro'yxatdan topa olmaydi (shuning uchun "
      "nomi retseptning o'zidan olinadi)", r.status_code == 200 and C_ID not in _royxat and A_ID in _royxat, (r.status_code, _royxat))
r = CA.put(f"/api/recipes/{R2_ID}", json=tana("RO157 Marmar", 150, "faqat izoh o'zgardi",
                                               [{"inventory_id": A_ID, "quantity_kg": 3}, {"inventory_id": C_ID, "quantity_kg": 1.2}]))
check("B2 tahrir tarkibida yashirilgan material (shu korxonaniki) — 200, retseptda QOLDI (miqdori bilan)",
      r.status_code == 200 and retsept(R2_ID) == ("RO157 Marmar", 150.0, "faqat izoh o'zgardi", sorted([(A_ID, 3.0), (C_ID, 1.2)])),
      (r.status_code, r.text[:300], retsept(R2_ID)))
r = CA.get("/recipes")
_m = re.search(r"openEditModal\(" + str(R2_ID) + r", (.*?)\)'", r.text)
check("B3 /recipes: «RO157 Marmar» tahrir tugmasi material NOMI va BIRLIGINI ham beradi («RO157 Bo'yoq», «l») — oyna uni «?» / «kg» "
      "emas, aslidek ko'rsatadi",
      r.status_code == 200 and _m is not None and "RO157 Bo\\u0027yoq" in _m.group(1) and '"l"' in _m.group(1),
      (r.status_code, _m.group(1)[:300] if _m else None))

# ══════════════════════════════════════════════════════════════
section("C. recipes.html (statik)")
# ══════════════════════════════════════════════════════════════
H = open(os.path.join(ROOT, "templates", "recipes.html"), encoding="utf-8").read()
_ki = H.find('<div id="addModal"')
_ti = H.find('<div id="editModal"')
QO, TA = (H[_ki:_ti], H[_ti:]) if 0 < _ki < _ti else ("", "")
IZOH = "Har biridan — «Partiya hajmi (kg)» uchun kerak miqdor (kg)"


def sub_matn(blok):
    return [re.sub(r"\s+", " ", x).strip() for x in re.findall(r'<div class="recp-section-sub">(.*?)</div>', blok, re.S)]


def sarlavha(blok):
    return [x.strip() for x in re.findall(r'<div class="recp-section-title">(.*?)</div>', blok, re.S)]


def tugmalar(blok):
    return [re.sub(r"\s+", " ", x).strip() for x in re.findall(r'<button[^>]*class="btn btn-(?:dark|outline) w-full"[^>]*>(.*?)</button>',
                                                                 blok, re.S)]


_TA_IZOHSIZ = re.sub(r"<!--.*?-->", "", re.sub(r"\{#.*?#\}", "", TA, flags=re.S), flags=re.S)   # eski matn izohda tilga olinadi
check("C1 tahrir oynasi «Tarkibi» izohi — yangi retsept oynasidagi bilan AYNAN («Har biridan — «Partiya hajmi (kg)» uchun kerak miqdor "
      "(kg)»); bo'sh `&nbsp;` YO'Q (izohsiz matnda)", sub_matn(QO) == [IZOH] and sub_matn(TA) == [IZOH] and "&nbsp;" not in _TA_IZOHSIZ,
      (sub_matn(QO), sub_matn(TA)))
check("C2 tahrir oynasi bo'lim sarlavhasi — yangi oynadagi bilan AYNAN («Tarkibi (Omborxonadagi materiallardan)»)",
      sarlavha(QO) == ["Tarkibi (Omborxonadagi materiallardan)"] and sarlavha(TA) == sarlavha(QO), (sarlavha(QO), sarlavha(TA)))
check("C3 tahrir oynasi «Saqlash» / «Bekor» tugmalari — yangi oynadagi bilan AYNAN (belgi bilan; «💾» emas)",
      tugmalar(QO) == ['<i class="ti ti-device-floppy"></i> Saqlash', '<i class="ti ti-x"></i> Bekor'] and tugmalar(TA) == tugmalar(QO),
      (tugmalar(QO), tugmalar(TA)))
_yop = re.findall(r'<button data-yopish type="button" class="recp-modal-close"([^>]*)>', H)
check("C4 ikkala oynaning «×» tugmasi — `title` va `aria-label` «Yopish» (ilgari yorliqsiz)",
      len(_yop) == 2 and all('title="Yopish"' in x and 'aria-label="Yopish"' in x for x in _yop), _yop)
_nom_chegara = (crud._val_rules().get("RecipeBody") or {}).get("name")
check("C5 «Retsept nomi» maydonlari (yangi va tahrir) — `maxlength` = server chegarasi (RecipeBody «name» — 100)",
      _nom_chegara == ("matn", True, 100) and re.search(r'<input type="text" id="f-name"[^>]*maxlength="100"', H) is not None
      and re.search(r'<input type="text" id="edit-name"[^>]*maxlength="100"', H) is not None, _nom_chegara)
_skript = H[H.find("{% block scripts %}"):H.find("</script>")]
_kod = "\n".join(x for x in _skript.splitlines() if not x.strip().startswith("//"))
check("C6 JS kodida (izohsiz) bo'sh hajmni jimgina 100 qiladigan `|| 100` YO'Q; miqdorsiz qatorni tashlab yuboradigan "
      "`collectIngredients` YO'Q; qator raqami tasodifiy (`Math.random`) EMAS",
      "|| 100" not in _kod and "collectIngredients" not in _kod and "Math.random" not in _kod and "recpQatorN" in _kod,
      [x for x in ("|| 100", "collectIngredients", "Math.random") if x in _kod])
_jsc = re.search(r"const RECP_SON_CHEGARA = (\d+);", _kod)
_rb = crud._val_rules().get("RecipeBody") or {}
_ri = crud._val_rules().get("RecipeIngredient") or {}
check("C7 JS son chegarasi `RECP_SON_CHEGARA` = `crud._UPD_SON_CHEGARA` va server «Partiya hajmi» / miqdor qoidasi SHU chegarada",
      _jsc is not None and float(_jsc.group(1)) == crud._UPD_SON_CHEGARA
      and _rb.get("batch_size_kg", (None,) * 4)[3] == crud._UPD_SON_CHEGARA
      and _ri.get("quantity_kg", (None,) * 4)[3] == crud._UPD_SON_CHEGARA,
      (_jsc.group(1) if _jsc else None, crud._UPD_SON_CHEGARA, _rb.get("batch_size_kg"), _ri.get("quantity_kg")))
check("C8 saqlash — yangi va tahrir BITTA yo'l (`retseptSaqlash`): server sababi `serverXatoSababi` bilan (JSON bo'lmasa ham), tarmoq "
      "uzilsa «Server bilan aloqa yo'q…», tugma `innerHTML` bilan tiklanadi",
      "async function saveRecipe() { return retseptSaqlash('f'); }" in _kod
      and "async function saveEditRecipe() { return retseptSaqlash('edit'); }" in _kod
      and "await serverXatoSababi(res, standart)" in _kod
      and "Server bilan aloqa yo'q. Internetni tekshirib, qayta urinib ko'ring." in _kod and "btn.innerHTML = aslHtml" in _kod)



def css_qoidalar(css):
    """(selektor, {xususiyat: (qiymat, !important)}, @media zanjiri) — <style> ichidagi qoidalar TARTIB bilan."""
    res = []

    def tahlil(matn, med):
        j = 0
        while j < len(matn):
            k = matn.find("{", j)
            if k < 0:
                break
            sel = re.sub(r"/\*.*?\*/", "", matn[j:k], flags=re.S).strip()
            d, e = 1, k + 1
            while e < len(matn) and d:
                d += {"{": 1, "}": -1}.get(matn[e], 0)
                e += 1
            ich = matn[k + 1:e - 1]
            if sel.startswith("@media"):
                tahlil(ich, med + [sel])
            elif sel and not sel.startswith("@"):
                dek = {}
                for qism in re.sub(r"/\*.*?\*/", "", ich, flags=re.S).split(";"):
                    if ":" in qism:
                        a, b = qism.split(":", 1)
                        dek[a.strip().lower()] = (b.strip(), "!important" in b)
                for s1 in sel.split(","):
                    res.append((re.sub(r"\s+", " ", s1.strip()), dek, tuple(med)))
            j = e
    tahlil(re.sub(r"/\*.*?\*/", "", css, flags=re.S), [])     # izohdagi qoida — hisobga olinmaydi
    return res


def css_ziddiyat(css):
    """@media ichidagi qoida KEYINGI media'siz qoida bilan bekor bo'ladimi: (selektor, media, xususiyat, media qiymati, keyingi qiymat)."""
    q = css_qoidalar(css)
    return [(sel, med[-1], x, v, dek2[x][0]) for i, (sel, dek, med) in enumerate(q) if med
            for sel2, dek2, med2 in q[i + 1:] if sel2 == sel and not med2
            for x, (v, imp) in dek.items() if x in dek2 and not imp and dek2[x][0] != v]


# skanerning o'zi — soxta kirishlar (bekor bo'ladigan / bo'lmaydigan / !important / boshqa xususiyat / izohdagi qoida)
_s1 = css_ziddiyat("@media (max-width:600px){ .a{position:static;color:red} }\n.a{position:absolute;color:red}")
_s2 = css_ziddiyat(".a{position:absolute}\n@media (max-width:600px){ .a{position:static} }")
_s3 = css_ziddiyat("@media (max-width:600px){ .a{position:static !important} }\n.a{position:absolute}")
_s4 = css_ziddiyat("@media (max-width:600px){ .a, .b{max-height:60vh} }\n/* eski: .a{max-height:1px} */\n.b{max-height:340px}")
check("C9s CSS tartib skanerining o'zi: media qoidasini keyingi asosiy qoida bekor qilsa — topadi (faqat farqli xususiyat); asosiy qoidadan "
      "KEYINGI media — ziddiyat emas; `!important` — emas; vergulli selektor; izohdagi qoida hisobga olinmaydi",
      _s1 == [(".a", "@media (max-width:600px)", "position", "static", "absolute")] and _s2 == [] and _s3 == []
      and _s4 == [(".b", "@media (max-width:600px)", "max-height", "60vh", "340px")], (_s1, _s2, _s3, _s4))
_css = "".join(re.findall(r"<style[^>]*>(.*?)</style>", re.sub(r"\{#.*?#\}", "", H, flags=re.S), re.S))
_q = css_qoidalar(_css)
_zid = css_ziddiyat(_css)
check("C9 recipes.html CSS: telefon (@media) qoidasini KEYINGI asosiy qoida bekor qilmaydi (ilgari `.recp-picker-panel` — `position: static` "
      "va `max-height: 60vh` telefonda ishlamasdi); telefon blokida tanlash paneli qoidasi bor",
      not _zid and any(sel == ".recp-picker-panel" and med and dek.get("position", ("",))[0] == "static" for sel, dek, med in _q), _zid)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAIL:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
