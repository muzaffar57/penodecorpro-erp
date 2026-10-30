#!/usr/bin/env python3
"""
test_jurnal183.py — kech146 (zip 183): «TIZIM JURNALLARI» VA «SOZLAMALAR» — AUDIT 2-to'lqin (J1 … J14, N1, N2).

NIMA UCHUN KERAK (O'LCHANGAN — `work/k183_tayyorgarlik/agentlar/jurnal/HISOBOT.md`, SQLite = PG):
  J1  hodim paneli kirishi «Kirish tarixi» ga korxonani TELEFONDAN TAXMIN qilib yozardi: telefon «+998 90 …» ko'rinishida saqlangan
      bo'lsa — hech bir korxonaga (hodim kirishlari ko'rinmasdi), boshqa korxonada shu raqamli login / hodim bo'lsa — O'SHA korxonaga
      (begona hodimning telefoni va IP si); urinishlar cheklovi ham o'sha taxmin bilan (boshqa korxonadagi xatolar bu hodimni bloklardi).
  J2  «Tannarx va foyda» ruxsatisiz rol «Audit jurnali» da tannarxni ko'rardi (ishlab chiqarish yakuni, qo'lda ishlab chiqarish, brak
      bekori) va qidiruv orqali yashirin sonni topardi (egasi qarori kech118: ruxsat yo'q — HAMMA joyda «—»).
  J3  «Moliyaviy tekshiruv» — «Tekshirilgan sana:» bo'sh.          J8  korxona adminiga platforma himoya to'ri holati (`tenant_filter`).
  J4  «Xatoliklar»: sabab 200 belgidan keyin kesilgan, «bosib to'liq ko'ring» steksiz qatorda hech narsa ochmasdi.
  J5  o'zgarishsiz saqlash / ikki marta bosish — jurnalga soxta «tahrirlandi».
  J6  filtr sanasi 01.01.0001 / NUL belgisi — 500 (JSON).          J7  100 belgidan uzun login / telefon — PG da 500.
  J9  sozlamalar o'zgarishi (korxona ma'lumoti, mahsulot turlari, logotip, Telegram) jurnalda iz qoldirmasdi.
  J10 Telegram: «salom» token saqlanib «✓ O'z boti sozlangan» ko'rinardi; chat maydoni bo'shatilsa ID lar qaytib kelardi.
  J11 «O'chirish» ruxsatli, «Tahrirlash» siz rol — yo'nalishni o'chirish tugmasi yo'q edi; «Fayl tanlash» yuklash tugmasisiz.
  J12 `/sozlamalar` jurnal so'rovlarini yurgizib, yozuvlarni HTML ga qo'shardi; `/logs` sozlama yuklovchilarini chaqirardi.
  J13 «50 metr  tan narxi» (vergul yo'qolgan); «chap paneldа» (kirill «а»).
  J14 platforma «Tizim salomatligi» enum skani faqat platforma egasining O'Z korxonasini tekshirardi.
  N1  320 px: sozlama maydonlari kartadan chiqib kesilardi.           N2  uzun xato so'zi ro'yxatni yonga surardi.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16; `TENANT_FILTER=1`. U bo'limi — HAQIQIY Chromium, HAQIQIY lokal server.
Asl kodga (zip 182) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_jurnal183.py
"""
import os
import re
import io
import sys
import glob
import html
import json
import time
import socket
import tempfile
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "jurnal183_test"
_T = tempfile.mkdtemp(prefix="jr183_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'jr183.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from sqlalchemy import text                        # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, User, Rol, ActivityLog, LoginHistory, ErrorLog, Inventory)   # noqa: E402
from production_models import Company, ProductType   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"


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


def db_ishi(fn):
    s = SessionLocal()
    try:
        r = fn(s)
        s.commit()
        return r
    finally:
        s.close()


def mijoz(login=None):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    if login:
        assert c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False).status_code in (302, 303), login
    return c


def rol_qoy(login, ruxsat):
    def f(s):
        u = s.query(User).filter(User.username == login).first()
        r = Rol(company_id=u.company_id, nom="JR183 " + login, kod=None, ruxsatlar=json.dumps(ruxsat), tavsif="")
        s.add(r)
        s.flush()
        u.rol_id = r.id
        return r.id
    return db_ishi(f)


def kirishlar(username):
    """LoginHistory: [(company_id, success)] — id tartibida."""
    return db_ishi(lambda s: [(x.company_id, bool(x.success)) for x in
                              s.query(LoginHistory).filter(LoginHistory.username == username).order_by(LoginHistory.id).all()])


def soz_jurnali(cid):
    """«Sozlamalar — …» jurnal yozuvlari: [(entity_label, new_value)]."""
    return db_ishi(lambda s: [(x.entity_label or "", x.new_value or "") for x in
                              s.query(ActivityLog).filter(ActivityLog.entity_type == "company_settings", ActivityLog.company_id == cid)
                              .order_by(ActivityLog.id).all()])


def jurnal_soni(entity_type, entity_id):
    return db_ishi(lambda s: s.query(ActivityLog).filter(ActivityLog.entity_type == entity_type,
                                                         ActivityLog.entity_id == entity_id).count())


def sozlama(kalit, cid):
    return db_ishi(lambda s: (crud.get_setting(s, kalit, "", company_id=cid) or ""))


def audit_soni(html):
    m = re.search(r'id="auditSoni">\((\d[\d\s]*) ta', html or "")
    return int(re.sub(r"\s", "", m.group(1))) if m else None


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik: A (1, kod JR183A) — admin, faqat jurnal roli, o'chirish roli, hodim (telefon «+998 90 111 22 33»);
# B (2, kod JR183B) — admin LOGINI hodim telefonining raqamlari «998901112233» (J1: taxmin shu yerga olib borardi);
# 3 — platforma administratori; 7 — logotip sinovi (diskdagi fayl nomi boshqa sinovlar bilan to'qnashmasin)
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
TEL_KALIT = "998901112233"
s = SessionLocal()
_c1 = s.query(Company).filter(Company.id == 1).first()
if _c1 is None:
    s.add(Company(id=1, name="JR183 A korxona", code="JR183A"))
else:
    _c1.code = "JR183A"
for _cid, _nom, _kod in ((2, "JR183 B korxona", "JR183B"), (3, "JR183 Platforma", "JR183P"), (7, "JR183 Logo", "JR183L")):
    if not s.query(Company).filter(Company.id == _cid).first():
        s.add(Company(id=_cid, name=_nom, code=_kod))
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "jr_admin", PAROL, UserRole.ADMIN, "JR183 Admin", company_id=1)
    for _u in ("jr_jur", "jr_och"):
        auth.create_user(s, _u, PAROL, UserRole.MANAGER, _u.upper(), company_id=1)
    auth.create_user(s, TEL_KALIT, PAROL, UserRole.ADMIN, "B korxona admini", company_id=2)
    auth.create_user(s, "jr_plat", PAROL, UserRole.ADMIN, "Platforma Egasi", company_id=3)
    auth.create_user(s, "jr_logo", PAROL, UserRole.ADMIN, "Logo Admin", company_id=7)
s.commit()
_pu = s.query(User).filter(User.username == "jr_plat").first()
_pu.is_platform_admin = True
PENO = Inventory(company_id=1, item_name="JR183 PENO", unit="blok", stock_quantity=1000, min_stock=0, is_penoplast=True,
                 volume_per_unit=1, price_per_unit=500000, category="Penoplast")
s.add(PENO)
s.commit()
PENO_ID = PENO.id
s.close()
rol_qoy("jr_jur", {"jurnal": ["korish"]})
rol_qoy("jr_och", {"jurnal": ["korish"], "sozlama": ["korish", "ochirish"]})

A = mijoz("jr_admin")
B = mijoz(TEL_KALIT)
JUR = mijoz("jr_jur")
PL = mijoz("jr_plat")
check("T0 admin / B admin / jurnal roli / platforma kirdi", A.get("/logs").status_code == 200 and B.get("/logs").status_code == 200
      and JUR.get("/logs").status_code == 200 and PL.get("/logs").status_code == 200)

# hodim (A korxona): telefon admin oynasidagidek bo'sh joyli — `telefon_kaliti` bilan «998901112233»
_r = A.post("/api/employees", json={"name": "JR183 Hodim", "position": "Kesuvchi", "pay_type": "fixed", "fixed_amount": 5_000_000})
EID = js(_r).get("id")
_r2 = A.post(f"/api/employees/{EID}/set-login", data={"phone": "+998 90 111 22 33", "pin": "4321"})
check("T1 hodim yaratildi, telefon + PIN berildi", bool(EID) and _r2.status_code == 200, (_r.status_code, _r.text[:200], _r2.text[:200]))


def hodim_kir(kod, tel, pin, c=None):
    c = c or mijoz()
    r = c.post("/hodim/login", data={"phone": tel, "pin": pin, "korxona": kod}, follow_redirects=False)
    return c, r


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J1. Hodim kirishi — o'z korxonasi bilan (taxmin yo'q), urinishlar cheklovi shu korxona bo'yicha")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
def _b_soni():
    return db_ishi(lambda s: s.query(LoginHistory).filter(LoginHistory.username == TEL_KALIT, LoginHistory.company_id == 2).count())


_B0 = _b_soni()                            # B adminining O'Z kirishi (login = shu raqamlar) — hodim yozuvlari bunga qo'shilmasin
_n0 = len(kirishlar(TEL_KALIT))
_c, _r = hodim_kir("JR183A", "+998901112233", "9999")
_k = kirishlar(TEL_KALIT)[_n0:]
check("J1a noto'g'ri PIN (A korxona kodi) — «Kirish tarixi» yozuvi A korxonaga (asl: B — o'sha raqamli login korxonasiga)",
      _r.status_code == 200 and _k == [(1, False)], (_r.status_code, _k))
_n0 = len(kirishlar(TEL_KALIT))
HC, _r = hodim_kir("JR183A", "+998901112233", "4321")
_k = kirishlar(TEL_KALIT)[_n0:]
check("J1b to'g'ri PIN — kirdi (302), muvaffaqiyatli yozuv A korxonada", _r.status_code in (302, 303) and _k == [(1, True)],
      (_r.status_code, _k))
_a_html = A.get("/logs").text
check("J1c A admini «Kirish tarixi» da hodim kirishini ko'radi; B korxonada bu yozuvlar YO'Q (asl: B ga tushardi)",
      TEL_KALIT in _a_html and _b_soni() == _B0, (TEL_KALIT in _a_html, _b_soni(), _B0))
_n0 = len(kirishlar(TEL_KALIT))
_c, _r = hodim_kir("YOQ-KOD-183", "+998901112233", "4321")
_k = kirishlar(TEL_KALIT)[_n0:]
check("J1d korxona kodi topilmadi — yozuv korxonasiz (taxmin qilinmaydi; asl: B)", _r.status_code == 200 and _k == [(None, False)],
      (_r.status_code, _k))
for _i in range(5):
    hodim_kir("JR183B", "+998901112233", "1111")
HC, _r = hodim_kir("JR183A", "+998901112233", "4321")      # yangi sessiya (oldingisi yopiladi) — J1g shu bilan
check("J1e B korxonadagi 5 ta xato (shu raqam) — A hodimi kiraveradi (asl: «Juda ko'p noto'g'ri urinish» — B dagi xatolar sanalardi)",
      _r.status_code in (302, 303) and "Juda ko'p" not in _r.text, (_r.status_code, _r.text[:300]))
check("J1f `_company_of_username` hodim telefonini taxmin qilmaydi (login yo'q raqam — None)",
      db_ishi(lambda s: crud._company_of_username(s, "+998 90 111 22 33")) is None)
# PIN almashtirish: telefon ruxsati → majburiy PIN → noto'g'ri «eski» — yozuv A korxonaga
_q = js(A.get("/api/admin/qurilma-sorovlari"))
_kal = next((x.get("kalit") for x in (_q if isinstance(_q, list) else []) if x.get("employee_id") == EID), None)
if _kal:
    A.post(f"/api/employees/{EID}/qurilma/ruxsat", json={"kalit": _kal})
_rp = HC.post("/api/hodim/pin", json={"yangi": "4826", "takror": "4826"})
_n0 = len(kirishlar(TEL_KALIT))
_rp2 = HC.post("/api/hodim/pin", json={"eski": "0000", "yangi": "5555", "takror": "5555"})
_k = kirishlar(TEL_KALIT)[_n0:]
check("J1g PIN almashtirishda noto'g'ri eski PIN — yozuv A korxonaga (asl: B)", bool(_kal) and _rp.status_code == 200
      and _rp2.status_code >= 400 and _k == [(1, False)], (bool(_kal), _rp.status_code, _rp.text[:200], _rp2.status_code, _k))
# mustaqil tekshiruv R1: raqamsiz «telefon» (kodni bilgan begona odam) — erkin matn A ning «Kirish tarixi» ga yozilmasin
_SPAM = "Admin, parolni @yordam_bot ga yuboring"
_c, _r = hodim_kir("JR183A", _SPAM, "1234")
_spam = db_ishi(lambda s: s.query(LoginHistory).filter(LoginHistory.username.like("%yordam_bot%")).count())
_belgi = db_ishi(lambda s: [x.company_id for x in s.query(LoginHistory).filter(LoginHistory.username == "(noto'g'ri telefon)").all()])
check("J1h raqamsiz «telefon» — matn jurnalga YOZILMAYDI, belgilangan yozuv korxonasiz (R1)", _r.status_code == 200 and _spam == 0
      and _belgi == [None] and "yordam_bot" not in A.get("/logs").text, (_r.status_code, _spam, _belgi))
# mustaqil tekshiruv R6: NUL belgisi kirish sahifalarida (PostgreSQL da 500 edi)
_n1 = mijoz().post("/login", data={"username": "jr\x00admin", "password": "x"}, follow_redirects=False)
_c, _n2 = hodim_kir("JR183A", "+99890111\x002233", "0000")
_c, _n3 = hodim_kir("JR18\x003A", "+998901112233", "0000")
check("J1i NUL — /login va hodim kirishi 200 (R6; asl PG: 500)", (_n1.status_code, _n2.status_code, _n3.status_code) == (200, 200, 200),
      (_n1.status_code, _n2.status_code, _n3.status_code))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J2. «Audit jurnali» — «Tannarx va foyda» ruxsatisiz: tannarx «—», qidiruv yashirin sonni topmaydi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_pr = A.post("/api/finished/produce", json={"name": "JR183 Karniz", "category": "profil", "is_coated": False, "penoplast_id": PENO_ID,
                                            "price_per_m3": None, "unit_price": 100000, "recipe_id": None, "notes": None,
                                            "width": 10, "thickness": 10, "length": 10, "quantity": 1, "loy_kg": 0})
_fp_id = js(_pr).get("product_id") or js(_pr).get("id")
_qolda = db_ishi(lambda s: [x.new_value or "" for x in s.query(ActivityLog).filter(
    ActivityLog.action == "produced", ActivityLog.entity_type == "finished_product", ActivityLog.entity_id == _fp_id).all()])
_m = re.search(r"tan narxi: ([0-9][0-9 ]*) so'm", _qolda[0] if _qolda else "")
QOLDA_SON = _m.group(1) if _m else "§yoq§"
check("J2 (tayyorgarlik) qo'lda ishlab chiqarish — jurnalda tannarx bor", _pr.status_code == 200 and _m and QOLDA_SON not in ("0",),
      (_pr.status_code, _pr.text[:200], _qolda))
check("J13a qo'lda ishlab chiqarish yozuvi: «10 metr, tan narxi: …» (asl: «10 metr  tan narxi» — vergul yo'qolgan)",
      bool(_qolda) and "metr, tan narxi:" in _qolda[0] and "  tan narxi" not in _qolda[0], _qolda)


def _yoz(**k):
    def f(s):
        a = ActivityLog(company_id=1, performed_by="JR183 Admin", **k)
        s.add(a)
        s.flush()
        return a.id
    return db_ishi(f)


ID_PO = _yoz(action="produced", entity_type="production_order", entity_id=91830, entity_label="Ishlab chiqarish #91830 — JR183 Karniz",
             new_value="12 dona — tannarx 1 234 567 so'm (xomashyo 1 000 000, qo'shimcha 234 567); Boshlashdagi taxmin 1 200 000 so'm, "
                       "farq +34 567 so'm")
ID_ESKI = _yoz(action="produced", entity_type="finished_product", entity_id=91831, entity_label="JR183 Eski karniz",
               new_value="50 metr  tan narxi: 225 000 so'm")
ID_BRAK = _yoz(action="delete", entity_type="finished_product_loss", entity_id=91832,
               entity_label="Brak bekor qilindi: JR183 Karniz — 3 dona (450,000 so'm) · ombor tiklandi")
ID_ODDIY = _yoz(action="updated", entity_type="order", entity_id=91833, entity_label="JR183-BUYURTMA",
                old_value="Jami: 7 000 000 so'm", new_value="Jami: 7 777 777 so'm")
ID_MINUS = _yoz(action="produced", entity_type="production_order", entity_id=91834, entity_label="Ishlab chiqarish #91834 — JR183 Minus",
                new_value="2 dona — tannarx −98 765 so'm (xomashyo 0, qo'shimcha −98 765)")
_hj = JUR.get("/logs?tab=activity").text
_ha = A.get("/logs?tab=activity").text
_yashirin = ("1 234 567", "1 200 000", "34 567", "225 000", "450,000", QOLDA_SON, "98 765")
check("J2a ruxsatsiz rol — tannarx sonlari sahifada YO'Q (asl: hammasi ko'rinardi)", all(x not in _hj for x in _yashirin),
      [x for x in _yashirin if x in _hj])
check("J2b ruxsatsiz rol — o'rnida «—» (tannarx —, tan narxi: —, (—)); oddiy yozuv summasi ko'rinadi",
      "tannarx —" in _hj and "tan narxi: —" in _hj and "(—)" in _hj and "Boshlashdagi taxmin —" in _hj and "7 777 777" in _hj)
check("J2c admin — hamma son ko'rinadi", all(x in _ha for x in _yashirin), [x for x in _yashirin if x not in _ha])
_sj = {q: audit_soni(JUR.get("/logs", params={"tab": "activity", "a_q": q}).text) for q in ("1 234 567", "225 000", "450,000", QOLDA_SON)}
_sa = {q: audit_soni(A.get("/logs", params={"tab": "activity", "a_q": q}).text) for q in ("1 234 567", "225 000", "450,000", QOLDA_SON)}
check("J2d qidiruv: ruxsatsiz rolga yashirin son bo'yicha 0 ta (asl: topardi — yashirin sonni bilish yo'li)",
      all(v == 0 for v in _sj.values()), _sj)
check("J2e qidiruv: admin — topadi", all((v or 0) >= 1 for v in _sa.values()), _sa)
_sn = audit_soni(JUR.get("/logs", params={"tab": "activity", "a_q": "Ishlab chiqarish #91830"}).text)
_so = audit_soni(JUR.get("/logs", params={"tab": "activity", "a_q": "7 777 777"}).text)
check("J2f ruxsatsiz rol: ishlab chiqarish NOMI bo'yicha va oddiy yozuv summasi bo'yicha qidiruv ishlaydi", _sn == 1 and _so == 1, (_sn, _so))
check("J2g bazadagi yozuv o'zgarmagan (yashirish faqat sahifada)", db_ishi(lambda s: "1 234 567" in (s.get(ActivityLog, ID_PO).new_value or "")
                                                                             and "450,000" in (s.get(ActivityLog, ID_BRAK).entity_label or "")))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J3 / J8. «Tekshiruv» — sana bor; platforma himoya to'ri holati faqat platforma administratoriga")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_hk = A.get("/api/system/health-check")
_hp = PL.get("/api/system/health-check")
check("J3 korxona admini: `checked_at` bor (asl: yo'q — «Tekshirilgan sana:» bo'sh)", _hk.status_code == 200 and bool(js(_hk).get("checked_at")),
      (_hk.status_code, list(js(_hk).keys())))
check("J8 korxona admini javobida `tenant_filter` YO'Q (asl: bor); platformada bor",
      "tenant_filter" not in js(_hk) and "tenant_filter" in js(_hp), (list(js(_hk).keys()), list(js(_hp).keys())))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J4. «Xatoliklar» — uzun xabar to'liq ochiladi; steksiz qisqa xabarda «bosib ko'ring» yo'q")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
UZUN_XATO = ("Faoliyat jurnaliga yozilmadi (updated · order #5 · " + "J" * 190 + ") — amalning o'zi saqlandi: SABAB183 value too long")
UZUN_SOZ = "get_projects_dashboard_stats:calculate_order_profit_" + "x" * 160


def _xato(m, iz=None):
    def f(s):
        e = ErrorLog(company_id=None, error_message=m, stack_trace=iz, endpoint="/api/jr183", method="GET")
        s.add(e)
        s.flush()
        return e.id
    return db_ishi(f)


_xato(UZUN_XATO)
_xato("QISQA183 xato")
_xato("STEKLI183 xato", "Traceback (most recent call last):\n  File ...\nValueError: STEK183")
_xato(UZUN_SOZ)
_hx = PL.get("/logs?tab=errors").text
_qatorlar = {m: blk for blk in _hx.split('class="err-row"')[1:] for m in ("SABAB183", "QISQA183", "STEKLI183") if m in blk}
check("J4a uzun xabar — to'liq matn sahifada (bosilganda ochiladi; asl: 200 belgida kesilgan, sabab yo'q)",
      "SABAB183" in _hx and "SABAB183" in _qatorlar.get("SABAB183", "") and 'class="err-detail"' in _qatorlar.get("SABAB183", ""))
check("J4b steksiz qisqa xabar — «bosib to'liq ko'ring» va bosish yo'q (asl: bor, hech narsa ochmasdi)",
      "bosib to'liq ko'ring" not in _qatorlar.get("QISQA183", "x bosib to'liq ko'ring") and "toggleErrDetail" not in _qatorlar.get("QISQA183", "toggleErrDetail"))
check("J4c stekli xabar — avvalgidek ochiladi", "STEK183" in _qatorlar.get("STEKLI183", "") and "bosib to'liq ko'ring" in _qatorlar.get("STEKLI183", ""))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J5. O'zgarishsiz saqlash — jurnalga yozilmaydi (yo'nalish, mahsulot turi yo'nalishi)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_ry = A.post("/api/yonalishlar", json={"nom": "JR183 Yo'nalish"})
YID = js(_ry).get("id")
_ry2 = A.post("/api/yonalishlar", json={"nom": "JR183 Bo'sh yo'nalish"})
YID_BOSH = js(_ry2).get("id")
_n0 = jurnal_soni("yonalish", YID)
_p1 = A.put(f"/api/yonalishlar/{YID}", json={"nom": "JR183 Yo'nalish"})
_p2 = A.put(f"/api/yonalishlar/{YID}", json={"nom": "  JR183   Yo'nalish "})
_p3 = A.put(f"/api/yonalishlar/{YID}", json={"yashirin": False})
_n1 = jurnal_soni("yonalish", YID)
check("J5a nom / holat o'zgarmagan 3 ta saqlash — 200, jurnalga 0 ta yozuv (asl: 3 ta «tahrirlandi»)",
      bool(YID) and all(r.status_code == 200 for r in (_p1, _p2, _p3)) and _n1 == _n0,
      (YID, _p1.status_code, _p2.status_code, _p3.status_code, _n0, _n1))
_p4 = A.put(f"/api/yonalishlar/{YID}", json={"nom": "JR183 Yo'nalish 2"})
check("J5b nom o'zgardi — BITTA yozuv", _p4.status_code == 200 and jurnal_soni("yonalish", YID) == _n0 + 1)


def _tur(s):
    pt = ProductType(company_id=1, name="JR183 Tur", unit="dona", input_template="quantity_only", pricing_formula="unit_based",
                     yonalish_id=YID)
    s.add(pt)
    s.flush()
    return pt.id


PT_ID = db_ishi(_tur)
_n0 = jurnal_soni("product_type", PT_ID)
_t1 = A.patch(f"/api/production/product-types/{PT_ID}", json={"yonalish_id": YID})
check("J5c mahsulot turiga o'sha yo'nalish qayta tanlandi — 200, jurnalga yozilmadi (asl: «tahrirlandi»)",
      _t1.status_code == 200 and jurnal_soni("product_type", PT_ID) == _n0, (_t1.status_code, _t1.text[:200]))
# zip 183 gacha yozilgan (yoki tafsilotsiz) «tahrirlandi» yozuvi — qisqa tavsif o'zgarmagan, «O'zgardi» qatori yo'q
_yoz(action="updated", entity_type="yonalish", entity_id=91835, entity_label="Yo'nalish «JR183 Eski izoh»",
     old_value="JR183 Eski izoh", new_value="JR183 Eski izoh")
_ha = A.get("/logs?tab=activity").text
check("J5d «tavsif o'zgarmagan» izohi — «bu yozuvda tafsilot saqlanmagan» («eski yozuv» deyilmaydi)",
      "bu eski yozuvda" not in _ha and "qisqa tavsif o'zgarmagan (bu yozuvda tafsilot saqlanmagan)" in html.unescape(_ha))
_yq = js(A.post("/api/yonalishlar", json={"nom": "JR183 Q (yashirin)"})).get("id")
_pq = A.put(f"/api/yonalishlar/{_yq}", json={"nom": "JR183 Q", "yashirin": True})
check("J5e «Q (yashirin)» nomli ko'rinadigan yo'nalish → nom «Q» + yashirin: o'zgarish SAQLANDI (R2 — matn bir xil chiqsa ham)",
      _pq.status_code == 200 and js(_pq).get("nom") == "JR183 Q" and js(_pq).get("yashirin") is True, (_pq.status_code, _pq.text[:200]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J6. Filtr: 01.01.0001 va NUL — sahifa ochiladi (500 emas)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_holat = {}
for _nom, _par in (("a_dan", {"a_dan": "0001-01-01", "tab": "activity"}), ("k_gacha", {"k_gacha": "0001-01-01"}),
                   ("a_q NUL", {"a_q": "ab\x00c", "tab": "activity"}), ("a_kim NUL", {"a_kim": "\x00"}), ("k_kim NUL", {"k_kim": "x\x00"}),
                   ("a_gacha 9999", {"a_gacha": "9999-12-31", "tab": "activity"})):
    _rr = A.get("/logs", params=_par)
    _holat[_nom] = (_rr.status_code, "text/html" in _rr.headers.get("content-type", ""))
_rs = A.get("/sozlamalar", params={"a_dan": "0001-01-01", "k_dan": "0001-01-01"})
_holat["/sozlamalar"] = (_rs.status_code, "text/html" in _rs.headers.get("content-type", ""))
check("J6a hamma noto'g'ri qiymat — 200 HTML (asl: 0001 — 500 JSON; PG da NUL — 500)", all(v == (200, True) for v in _holat.values()), _holat)
check("J6b sana maydonlarida min / max (01.01.0001 terib bo'lmaydi)", _ha.count('min="2020-01-01" max="2100-12-31"') == 4)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J7. 100 belgidan uzun login / telefon — oddiy xato, yozuv ≤ 100")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_uz = "u" * 150
_rl = mijoz().post("/login", data={"username": _uz, "password": "x"}, follow_redirects=False)
_c, _rh = hodim_kir("JR183A", "9" * 150, "1234")
_uzunlar = db_ishi(lambda s: [len(x.username or "") for x in s.query(LoginHistory).filter(
    (LoginHistory.username.like("uuuuuuuuuu%")) | (LoginHistory.username.like("9999999999%"))).all()])
check("J7a login 150 belgi — 200, «noto'g'ri» xabari (asl PG: 500)", _rl.status_code == 200 and "noto'g'ri" in html.unescape(_rl.text),
      _rl.status_code)
check("J7b hodim telefoni 150 raqam — 200 (asl PG: 500)", _rh.status_code == 200, _rh.status_code)
check("J7c «Kirish tarixi» yozuvlari ≤ 100 belgi (asl SQLite: 150)", _uzunlar and max(_uzunlar) <= 100, _uzunlar)
check("J7d kirish sahifalarida maxlength", 'name="username" maxlength="100"' in mijoz().get("/login").text
      and 'maxlength="30"' in mijoz().get("/hodim/login").text)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J9 / J10. Sozlamalar o'zgarishi — «Audit jurnali» ga; Telegram token / chat tekshiruvi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_n0 = len(soz_jurnali(1))
_co = {"name": "JR183 A korxona", "slogan": "", "phone": "+998 71 000 00 01", "address": "Toshkent", "tg_tagline": ""}
_s1 = A.put("/api/settings/company", data=_co)
_s2 = A.put("/api/settings/company", data=_co)
_j = soz_jurnali(1)[_n0:]
check("J9a korxona ma'lumoti o'zgardi — BITTA yozuv (telefon / manzil eski → yangi), takror saqlash — yozuv yo'q (asl: 0 ta)",
      _s1.status_code == 200 and _s2.status_code == 200 and len(_j) == 1 and "Korxona ma'lumotlari" in _j[0][0]
      and "Telefon:" in _j[0][1] and "+998 71 000 00 01" in _j[0][1] and "Manzil:" in _j[0][1], _j)
check("J9f sozlama yozuvi sahifada «O'zgardi: …» qatori bilan (boshqa tahrir yozuvlaridek; R8)",
      re.search(r"<b>O'zgardi:</b> [^<]*Telefon: «", A.get("/logs?tab=activity").text) is not None)
_cats = js(A.get("/api/settings/categories")).get("categories") or []
_yoq = [c for c in _cats if c.get("enabled")]
_n0 = len(soz_jurnali(1))
if _yoq:
    _qol = [c["code"] for c in _yoq[1:]]
    _k1 = A.put("/api/settings/categories", data={"codes": ",".join(_qol), "bosh": "" if _qol else "1"})
    _k2 = A.put("/api/settings/categories", data={"codes": ",".join(_qol), "bosh": "" if _qol else "1"})
    _j = soz_jurnali(1)[_n0:]
    check("J9b mahsulot turi o'chirildi — BITTA yozuv «o'chirildi: <nomi>» (birinchi saqlash ham — hammasi yoqiq hisoblanadi)",
          _k1.status_code == 200 and _k2.status_code == 200 and len(_j) == 1 and f"o'chirildi: {_yoq[0]['label']}" in _j[0][1]
          and "yoqildi" not in _j[0][1], (_j, _yoq[0]))
    A.put("/api/settings/categories", data={"codes": ",".join(c["code"] for c in _yoq), "bosh": ""})
else:
    check("J9b mahsulot turlari ro'yxati bor", False, _cats)
try:
    from PIL import Image as _Im
    _b = io.BytesIO()
    _Im.new("RGB", (40, 20), (200, 120, 60)).save(_b, "PNG")
    _png = _b.getvalue()
except Exception:                          # noqa: BLE001
    _png = b""
LG = mijoz("jr_logo")
_n0 = len(soz_jurnali(7))
_rlg = LG.post("/api/settings/company/logo", files={"file": ("logo.png", _png, "image/png")})
_j = soz_jurnali(7)[_n0:]
check("J9c logotip yuklandi — yozuv «Korxona logotipi»", _rlg.status_code == 200 and len(_j) == 1 and "logotip" in _j[0][0].lower(),
      (_rlg.status_code, _rlg.text[:200], _j))
# mustaqil tekshiruv R3: salom shiori hech qachon yozilmagan korxona — sahifa ko'rsatgan qiymatlar o'zgartirmay saqlansa yozuv YO'Q
# korxona shiori bor, salom shiori sozlamasi hech qachon yozilmagan — sahifa shiorni ko'rsatadi (`_tg_tagline`)
db_ishi(lambda s: setattr(s.query(Company).filter(Company.id == 7).first(), "slogan", "JR183 Logo shiori"))
_k7 = js(LG.get("/api/settings/company"))
_n7 = len(soz_jurnali(7))
_s7 = LG.put("/api/settings/company", data={"name": _k7.get("name") or "JR183 Logo", "slogan": _k7.get("slogan") or "",
                                            "phone": _k7.get("phone") or "", "address": _k7.get("address") or "",
                                            "tg_tagline": _k7.get("tg_tagline") or ""})
check("J9e o'zgarishsiz saqlash (shior — sahifadagi qiymat) — jurnal yozuvi yo'q (R3)", _s7.status_code == 200
      and _k7.get("tg_tagline") == "JR183 Logo shiori"
      and len(soz_jurnali(7)) == _n7, (_s7.status_code, soz_jurnali(7)[_n7:]))
for _p in glob.glob(os.path.join(ROOT, "static", "uploads", "logos", "company_7.*")):
    try:
        os.remove(_p)
    except OSError:
        pass
for _d in (os.path.join(ROOT, "static", "uploads", "logos"), os.path.join(ROOT, "static", "uploads")):
    try:
        os.rmdir(_d)                       # faqat bo'sh bo'lsa (boshqa sinov fayli bo'lsa — tegilmaydi)
    except OSError:
        pass

TOKEN = "123456789:" + "B" * 33 + "Q7"
_n0 = len(soz_jurnali(1))
_t1 = A.put("/api/settings/telegram-bot", data={"token": "salom", "chat_id": ""})
_g1 = js(A.get("/api/settings/telegram-bot"))
check("J10a «salom» token — 400, saqlanmadi, «sozlangan» emas (asl: 200, «✓ O'z boti sozlangan»)",
      _t1.status_code == 400 and sozlama("telegram_bot_token", 1) == "" and not _g1.get("configured"), (_t1.status_code, _g1))
_t2 = A.put("/api/settings/telegram-bot", data={"token": "", "chat_id": "mening guruhim"})
_t3 = A.put("/api/settings/telegram-bot", data={"token": "", "chat_id": ",".join(["1"] * 21)})
check("J10b chat ID matn / 21 ta — 400, saqlanmadi", _t2.status_code == 400 and _t3.status_code == 400
      and sozlama("telegram_chat_id", 1) == "", (_t2.status_code, _t3.status_code))
_t4 = A.put("/api/settings/telegram-bot", data={"token": TOKEN, "chat_id": " -100183 , 456 "})
check("J10c to'g'ri token va chat — 200, chat toza ko'rinishda «-100183,456»", _t4.status_code == 200
      and sozlama("telegram_bot_token", 1) == TOKEN and sozlama("telegram_chat_id", 1) == "-100183,456", (_t4.status_code, _t4.text[:200]))
_j = soz_jurnali(1)[_n0:]
_hamma = db_ishi(lambda s: [((x.entity_label or "") + (x.old_value or "") + (x.new_value or "")) for x in s.query(ActivityLog).all()])
check("J9d Telegram — BITTA yozuv: «bot tokeni almashtirildi (…BBQ7)», chat eski → yangi; token jurnalda YO'Q",
      len(_j) == 1 and "bot tokeni almashtirildi (…" + TOKEN[-4:] + ")" in _j[0][1] and "-100183,456" in _j[0][1]
      and not any(TOKEN in x or TOKEN[:20] in x for x in _hamma), _j)
_t5 = A.put("/api/settings/telegram-bot", data={"token": "", "chat_id": ""})
check("J10d bo'sh maydonlar — o'zgarmaydi (ilgarigidek), jurnal yozuvi yo'q", _t5.status_code == 200
      and sozlama("telegram_chat_id", 1) == "-100183,456" and len(soz_jurnali(1)) == _n0 + 1)
_t6 = A.put("/api/settings/telegram-bot", data={"token": "", "chat_id": " @jr183_kanal , -100183,, "})
_c6 = sozlama("telegram_chat_id", 1)
_t7 = A.put("/api/settings/telegram-bot", data={"token": "", "chat_id": "\u0661\u0662\u0663\u0664\u0665\u0666"})
check("J10e ochiq kanal (@kanal) va ortiqcha vergullar qabul qilinadi; boshqa yozuvdagi raqamlar — 400 (R4)",
      _t6.status_code == 200 and _c6 == "@jr183_kanal,-100183" and _t7.status_code == 400, (_t6.status_code, _t6.text[:200], _c6, _t7.status_code))
A.put("/api/settings/telegram-bot", data={"token": "", "chat_id": "-100183,456"})

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J11 / J12 / J13. «Sozlamalar» sahifasi — ruxsatlar, jurnal so'rovlari yo'q, matnlar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
db_ishi(lambda s: s.add(LoginHistory(company_id=1, username="jr183_belgi_kirish", success=True, ip_address="10.1.8.3")))
_sz = A.get("/sozlamalar").text
_lg = A.get("/logs").text
check("J12a /sozlamalar — kirish / audit yozuvlari HTML da YO'Q (asl: bor), /logs da bor",
      "jr183_belgi_kirish" not in _sz and "JR183-BUYURTMA" not in _sz and "jr183_belgi_kirish" in _lg)
check("J12b /sozlamalar — «Kirish urinishlari» kartasi boshidanoq yashirin",
      '<div id="tab-login" class="card" style="display:none">' in _sz and '<div id="tab-login" class="card">' in _lg)
_yuk = "document.addEventListener('DOMContentLoaded', () => { loadTgBot(); loadCompany(); loadCategories(); yonYukla(); });"
check("J12c sozlama yuklovchilari — faqat /sozlamalar da (asl: /logs da ham)", _yuk in _sz and _yuk not in _lg)
_so = mijoz("jr_och").get("/sozlamalar").text
check("J11a «Tahrirlash» siz rol — «Fayl tanlash» yo'q (asl: bor, yuklash tugmasisiz)", "Fayl tanlash" not in _so and "Fayl tanlash" in _sz)
check("J11b o'chirish ruxsati — sahifaga uzatiladi (YON_OCHIR = true, YON_TAHRIR = false)",
      "const YON_TAHRIR = false;" in _so and "const YON_OCHIR = true;" in _so)
check("J11c «Bo'shatib saqlansa …» izohi — faqat saqlay oladigan rolga (R9)", "Bo'shatib saqlansa" not in _so and "Bo'shatib saqlansa" in _sz)
check("J13b «Bu nom menyuda va hujjatlarda ko'rinadi.» (kirill «а» va «chap panel» yo'q)",
      "Bu nom menyuda va hujjatlarda ko'rinadi." in _sz and "paneldа" not in _sz)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J14. Platforma salomatligi — HAMMA korxonalar, korxona nomi bilan")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_eb = js(B.post("/api/employees", json={"name": "JR183 B hodim", "position": "Kesuvchi", "pay_type": "fixed", "fixed_amount": 1_000_000}))
EID_B = _eb.get("id")
_asl_tur = db_ishi(lambda s: s.execute(text("SELECT pay_type FROM employees WHERE id = :i"), {"i": EID_B}).scalar()) if EID_B else None
if not PG_URL and EID_B:
    db_ishi(lambda s: s.execute(text("UPDATE employees SET pay_type = 'XATO183' WHERE id = :i"), {"i": EID_B}))
_hp = js(PL.get("/api/system/health-check"))
if not PG_URL:
    _top = [i for i in (_hp.get("issues") or []) if i.get("table") == "employees" and i.get("id") == EID_B]
    check("J14a B korxonadagi noto'g'ri qiymat platforma skanida topildi, korxona nomi bilan (asl: faqat platforma korxonasi)",
          len(_top) == 1 and _top[0].get("company") == "JR183 B korxona" and _top[0].get("bad_value") == "XATO183", _hp.get("issues"))
    db_ishi(lambda s: s.execute(text("UPDATE employees SET pay_type = :t WHERE id = :i"), {"i": EID_B, "t": _asl_tur}))
check("J14b platforma skani — hech bir jadval xatosiz (ota jadval orqali korxona — payments / advance_requests)",
      not _hp.get("check_errors") and _hp.get("total_checks", 0) >= 12, _hp.get("check_errors"))
_hk = js(A.get("/api/system/health-check"))
check("J14c korxona admini — texnik skan yashirin (o'zgarmagan)", _hk.get("technical_hidden") is True and not _hk.get("issues"))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# U. HAQIQIY Chromium — lokal server
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_x = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_x = False, f"{type(_e).__name__}: {_e}"
import uvicorn                                     # noqa: E402


def _port():
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    p = so.getsockname()[1]
    so.close()
    return p


port = _port()
server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
threading.Thread(target=server.run, daemon=True).start()
for _ in range(150):
    if server.started:
        break
    time.sleep(0.1)
BU = f"http://127.0.0.1:{port}"
pw_ctx = br = None
if PW_BOR and server.started:
    pw_ctx = sync_playwright().start()
    _exe = None
    for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                              "chrome-linux", "chrome"))):
        _exe = _yol
    try:
        br = pw_ctx.chromium.launch(executable_path=_exe) if _exe else pw_ctx.chromium.launch()
    except Exception as _e:                # noqa: BLE001
        br = None
        _pw_x = f"{type(_e).__name__}: {_e}"
section("U. Brauzer (Chromium)")
check("U0 lokal server va Chromium", bool(server.started and br), _pw_x)
JS_XATO, SOROV = [], []


def kontekst(user, en=1440, boy=900):
    ctx = br.new_context(viewport={"width": en, "height": boy}, timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.add_init_script("try { window.addEventListener('load', () => document.querySelectorAll('details.sht').forEach(d => { d.open = true; })); } catch (e) {}")      # kech160 (zip 225): Sozlamalar bo'limlari shtorkada — ochiq
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
    pg = ctx.new_page()
    pg.set_default_timeout(15000)
    pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
    pg.on("request", lambda q: SOROV.append((q.method, q.url.replace(BU, ""))) if "/api/" in q.url else None)
    pg.goto(BU + "/login")
    pg.fill("input[name=username]", user)
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    return ctx, pg


def ochiq(pg, yol):
    pg.goto(BU + yol, wait_until="networkidle")
    pg.wait_for_timeout(500)


if br:
    # U1 — J10: chat maydoni bo'shatilib saqlansa — o'chiriladi
    ctx, pg = kontekst("jr_admin")
    try:
        ochiq(pg, "/sozlamalar")
        pg.wait_for_function("() => document.getElementById('tg-chat').value === '-100183,456'", timeout=8000)
        pg.fill("#tg-chat", "")
        pg.click("#tg-save-btn")
        pg.wait_for_timeout(1800)
        check("U1 chat ID maydoni bo'shatilib «Saqlash» — chat ID lar o'chdi (asl: «✓ Saqlandi», ID lar qoldi)",
              sozlama("telegram_chat_id", 1) == "" and sozlama("telegram_bot_token", 1) == TOKEN,
              (sozlama("telegram_chat_id", 1), pg.inner_text("#tg-status")))
        # U5 — J5: «Nomini saqlash» ikki marta — BITTA PUT
        pg.wait_for_selector(f".yon-qator[data-id='{YID}'] .yon-nom")
        pg.fill(f".yon-qator[data-id='{YID}'] .yon-nom", "JR183 Yo'nalish 3")
        _n0 = len([x for x in SOROV if x == ("PUT", f"/api/yonalishlar/{YID}")])
        _j0 = jurnal_soni("yonalish", YID)
        pg.evaluate(f"""() => {{ const b = document.querySelector(".yon-qator[data-id='{YID}'] button[onclick^='yonNomSaqla']");
                               yonNomSaqla(b); yonNomSaqla(b); }}""")
        pg.wait_for_timeout(1800)
        _n1 = len([x for x in SOROV if x == ("PUT", f"/api/yonalishlar/{YID}")])
        check("U5 «Nomini saqlash» ikki marta — BITTA so'rov, BITTA jurnal yozuvi (asl: 2 so'rov)",
              _n1 - _n0 == 1 and jurnal_soni("yonalish", YID) == _j0 + 1, (_n1 - _n0, jurnal_soni("yonalish", YID) - _j0))
        # U8 — mustaqil tekshiruv R5: bot sozlanmagan (token yo'q), chat ID saqlangan — maydonda ko'rinadi, bo'shatib saqlansa o'chadi
        A.put("/api/settings/telegram-bot", data={"token": "-", "chat_id": "-100555"})
        ochiq(pg, "/sozlamalar")
        pg.wait_for_timeout(600)
        _v8 = pg.input_value("#tg-chat")
        pg.fill("#tg-chat", "")
        pg.click("#tg-save-btn")
        pg.wait_for_timeout(1800)
        check("U8 token yo'q — saqlangan chat ID maydonda ko'rinadi va bo'shatib saqlansa o'chadi (R5; asl: yashirin qolardi)",
              _v8 == "-100555" and sozlama("telegram_chat_id", 1) == "", (_v8, sozlama("telegram_chat_id", 1)))
    except Exception as _x:               # noqa: BLE001
        check("U1 / U5 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    # U2 — N1: 320 px — sozlama maydonlari kartadan chiqmaydi
    ctx, pg = kontekst("jr_admin", 320, 700)
    try:
        ochiq(pg, "/sozlamalar")
        _olc = pg.evaluate("""() => ['co-name','co-slogan','co-tg-tagline','co-phone','co-address','yon-yangi','tg-token','tg-chat'].map(id => {
            const el = document.getElementById(id); if (!el) return [id, null];
            const r = el.getBoundingClientRect(), k = el.closest('.card').getBoundingClientRect();
            return [id, Math.round(r.left), Math.round(r.right), Math.round(k.left), Math.round(k.right), Math.round(r.width)]; })""")
        _yomon = [x for x in _olc if x[1] is None or x[2] > x[4] + 0.5 or x[1] < x[3] - 0.5 or x[5] < 120]
        check("U2 320 px: 8 ta maydon karta ichida, kengligi ≥ 120 px (asl: 280 px li maydonlar ~26 px kesilardi)", not _yomon, _olc)
        _yq = pg.evaluate("""() => [...document.querySelectorAll('.yon-qator .yon-nom')].map(el => {
            const r = el.getBoundingClientRect(), k = el.closest('.card').getBoundingClientRect(); return r.right <= k.right + 0.5; })""")
        check("U2b 320 px: yo'nalish nomi maydonlari karta ichida", _yq and all(_yq), _yq)
    except Exception as _x:               # noqa: BLE001
        check("U2 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    # U3 — J12: /logs — sozlama so'rovlari yo'q
    ctx, pg = kontekst("jr_admin")
    try:
        _n0 = len(SOROV)
        ochiq(pg, "/logs")
        _s = [x for x in SOROV[_n0:] if x[1].startswith("/api/settings/") or x[1].startswith("/api/yonalishlar")]
        check("U3 /logs ochilganda sozlama / yo'nalish so'rovlari YO'Q (asl: 4 ta)", not _s, _s)
        _n0 = len(SOROV)
        ochiq(pg, "/sozlamalar")
        _s = [x for x in SOROV[_n0:] if x[1].startswith("/api/settings/") or x[1].startswith("/api/yonalishlar")]
        check("U3b /sozlamalar — yuklovchilar ishlaydi (4 ta so'rov), «Kirish urinishlari» ko'rinmaydi",
              len(_s) >= 4 and not pg.is_visible("#tab-login") and pg.is_visible("#tab-settings"), (_s, pg.is_visible("#tab-login")))
    except Exception as _x:               # noqa: BLE001
        check("U3 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    # U4 — J11: o'chirish ruxsatli, tahrirlashsiz rol
    ctx, pg = kontekst("jr_och")
    try:
        ochiq(pg, "/sozlamalar")
        pg.wait_for_selector(f".yon-qator[data-id='{YID_BOSH}']")
        _b = pg.locator(f".yon-qator[data-id='{YID_BOSH}'] button.yon-ochir")
        _bor = _b.count() == 1
        check("U4 «Tahrirlash» siz, «O'chirish» li rol — ishlatilmagan yo'nalishda «O'chirish» tugmasi (asl: yo'q)",
              _bor and pg.locator(f".yon-qator[data-id='{YID_BOSH}'] .yon-nom").count() == 0, _b.count())
        if _bor:
            _b.click()
            pg.wait_for_timeout(200)
            _b.click()
            pg.wait_for_timeout(1500)
            check("U4b ikki bosqichli o'chirish — yo'nalish o'chdi (server ruxsat beradi)",
                  js(A.get("/api/yonalishlar?hammasi=true")) and all(y.get("id") != YID_BOSH for y in js(A.get("/api/yonalishlar?hammasi=true"))))
    except Exception as _x:               # noqa: BLE001
        check("U4 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    # U6 / U7 — J4 / N2: platforma «Xatoliklar»
    ctx, pg = kontekst("jr_plat", 320, 700)
    try:
        ochiq(pg, "/logs?tab=errors")
        _qator = pg.locator(".err-row", has_text="SABAB183")
        _qator.first.click()
        pg.wait_for_timeout(300)
        _pre = _qator.first.locator(".err-detail")
        check("U6 uzun xabar bosildi — to'liq matn (SABAB183) ko'rindi (asl: hech narsa ochilmasdi)",
              _pre.count() == 1 and _pre.is_visible() and "SABAB183" in _pre.inner_text())
        _sk = pg.evaluate("""() => { const q = document.querySelector('#tab-errors .err-row').parentElement;
                                     return [q.scrollWidth, q.clientWidth]; }""")
        check("U7 320 px: uzun so'zli xato ro'yxatni yonga surmaydi (N2)", _sk[0] <= _sk[1] + 1, _sk)
    except Exception as _x:               # noqa: BLE001
        check("U6 / U7 bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    section("Z. Sahifa xatolari")
    check("Z1 sahifalarda ushlanmagan JS xatosi yo'q", not JS_XATO, JS_XATO[:5])

try:
    if br:
        br.close()
    if pw_ctx:
        pw_ctx.stop()
except Exception:                          # noqa: BLE001
    pass
server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
