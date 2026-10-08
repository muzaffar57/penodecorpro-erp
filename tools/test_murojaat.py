#!/usr/bin/env python3
"""
test_murojaat.py — kech127 (zip 151): «MUROJAAT» bo'limi — mijoz korxona admini → platforma egasi (EGASI QARORLARI 08.10 01:40,
tugmali, QAYTA SO'RALMAYDI: (1) hozir, birinchi mijozdan oldin; (2) murojaatni FAQAT korxona admini yozadi; (3) javob — DASTUR
ICHIDA). Shu zipdagi ikki kichik tuzatish ham: jurnalda `loy_tuzatish` amali o'zbekcha nom bilan; «Ombor harakatlari → jami»
penoplastni («dona» kirim + «blok» chiqim) BITTA qatorda ko'rsatadi.

NIMA UCHUN KERAK
  O'LCHANGAN (08.10): dasturda mijoz korxona platforma egasiga yozadigan joy yo'q edi — faqat aloqa telefoni (obuna ogohlantirishi /
  blok xabarida). Endi: «Yordam / Murojaat» (korxona admini) → Telegram egasiga → «Platforma» → «Murojaatlar» da javob / yopish →
  mijoz menyusida o'qilmagan javob soni. Yozishma korxona zaxirasiga kirmaydi va korxona tozalashi uni o'chirmaydi (xat kabi).
TALAB (har biri o'lchanadi):
  S  statik: jadvallar, `_TENANT_RULES`, zaxiradan tashqari (`_NON_TENANT_TABLES`), tozalash tartibida yo'q, rasm papkasi himoyada,
     marshrutlar va qorovullar, menyu bandi, `AUDIT_AMALLARI["loy_tuzatish"]`;
  Y  yaratish: korxona admini — murojaat + birinchi xabar, sahifa, muallif; Telegram egasiga (`company_id=None`) — raqam, korxona,
     tur, sahifa, matn; kontekst (brauzer, ekran, korxonaning OXIRGI 24 SOATDAGI texnik xatosi — boshqa korxonaniki / eskisi emas);
     tekshiruvlar (bo'sh / uzun matn, noto'g'ri tur — 400, hech narsa yozilmaydi; begona sahifa / ekran — yozilmaydi); rasm (PNG —
     saqlanadi; ruxsatsiz tur — 400, murojaat ham, fayl ham yo'q); sutkalik chegara (rasmli rad — fayl ham, kichik nusxasi ham
     o'chadi); faqat admin (menejer — 403), platforma egasi — 403 / sahifa → /platforma;
  L  mijoz: ro'yxat — faqat o'z korxonasi; yozishma — begona / yo'q — 404; qo'shimcha xabar — «Yangi», Telegram; begonasiga — 404;
  P  platforma: hamma korxonalar, korxona nomi, sanoq, holat / korxona filtri; oddiy admin — 403; yozishma — kontekst bilan (mijozga
     kontekst berilmaydi); javob — «Javob berildi», mijozda «yangi javob» va menyu soni, o'qilgach — 0; mijoz yana yozsa — «Yangi»;
     yopish — mijoz ham, platforma ham yozolmaydi (409), qayta yopish — 409;
  R  rasm himoyasi: o'z korxonasi — 200; begona korxona — 404; platforma egasi — 200 (faqat murojaat papkasi — boshqa korxonaning
     ombor rasmi — 404); kirmagan — 401;
  M  menyu: korxona admini — «Yordam / Murojaat» (o'qilmagan javob soni bilan), menejer — yo'q, platforma egasi — yo'q, «Platforma»
     yonida javob kutayotganlar soni;
  Z  zaxira / tozalash: korxona zaxirasida murojaat jadvallari YO'Q; korxonani tozalash va zaxiradan tiklash yozishmani o'zgartirmaydi;
  T  ORM qo'riqchisi: xabar korxonasi murojaatnikidan farq qilsa — rad;
  J  jurnal: `loy_tuzatish` — «loy rejasi xatosi tuzatildi» («amal: loy_tuzatish» emas);
  H  «Ombor harakatlari → jami»: penoplast («dona» kirim, «blok» chiqim) — bitta qator, materialning birligi bilan.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16; `TENANT_FILTER=1` bilan ham.
Asl kodga (zip 150) qarshi QULAMAYDI — yiqiladi (yangi nomlar `getattr`, HTTP istisno — 599).
ISHLATISH: python3 tools/test_murojaat.py
"""
import os
import re
import sys
import io
import json
import glob
import tempfile
import contextlib
from datetime import datetime, timedelta

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "murojaat_test"
_DB = os.path.join(tempfile.gettempdir(), "murojaat_test.db")
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
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import crud, auth, models                      # noqa: E402

from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import UserRole, User, ErrorLog, Inventory, InventoryMovement, _uzb_now   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

Murojaat = getattr(models, "Murojaat", None)        # asl kodda yo'q — test QULAMAYDI, tekshiruvlar yiqiladi
MurojaatXabari = getattr(models, "MurojaatXabari", None)
try:
    import murojaat as MJ                          # noqa: E402
except Exception:                                  # noqa: BLE001
    MJ = None

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
        return getattr(c, metod)(url, **k)
    except Exception as e:                 # noqa: BLE001
        return _Xato(e)


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


def xavfsiz(fn, standart=None):
    try:
        return fn()
    except Exception:                      # noqa: BLE001
        return standart


def fayl(nom):
    try:
        return open(os.path.join(ROOT, nom), encoding="utf-8").read()
    except Exception:                      # noqa: BLE001
        return ""


def png_bayt(rang=(200, 30, 30), olcham=(64, 48)):
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", olcham, rang).save(b, "PNG")
    return b.getvalue()


UPL = os.path.join(ROOT, "static", "uploads")
MJ_PAPKA = os.path.join(UPL, "murojaat")
KICHIK_PAPKA = os.path.join(UPL, "_kichik", "murojaat")


def papka_fayllari(p):
    return set(os.listdir(p)) if os.path.isdir(p) else set()


_BOSH_FAYLLAR = papka_fayllari(MJ_PAPKA)
_BOSH_KICHIK = papka_fayllari(KICHIK_PAPKA)

# Telegram — ushlab olinadi (tarmoqqa chiqmaydi)
TG = []
main._send_telegram = lambda matn, company_id=None: TG.append((matn, company_id)) or True

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik: korxona 1 — platforma egasi; 2 — «MJ Alfa» (mijoz A); 3 — «MJ Beta» (mijoz B)
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_db = SessionLocal()
for _cid, _nom in ((2, "MJ Alfa Dekor"), (3, "MJ Beta Fasad"), (4, "MJ Gamma (faqat eski xato)")):
    if not _db.query(Company).filter(Company.id == _cid).first():
        _db.add(Company(id=_cid, name=_nom))
_db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "mj_ega", "Parol123!", UserRole.ADMIN, "Platforma Egasi", company_id=1)
    auth.create_user(_db, "mj_a_admin", "Parol123!", UserRole.ADMIN, "Alisher Admin", company_id=2)
    auth.create_user(_db, "mj_a_menejer", "Parol123!", UserRole.MANAGER, "Anvar Menejer", company_id=2)
    auth.create_user(_db, "mj_b_admin", "Parol123!", UserRole.ADMIN, "Botir Admin", company_id=3)
_db.query(User).filter(User.username == "mj_ega").update({"is_platform_admin": True})
_db.query(User).filter(User.username.in_(["mj_a_admin", "mj_a_menejer", "mj_b_admin"])).update(
    {"is_platform_admin": False}, synchronize_session=False)
# texnik xatolar: A — 1 soat oldin (kutilgan), A — 2 kun oldin (eski), B — 10 daqiqa oldin (begona)
_hozir_tk = _uzb_now()
_db.add_all([
    ErrorLog(company_id=2, error_message="A eski xato", endpoint="/api/eski", method="GET", created_at=_hozir_tk - timedelta(days=2)),
    ErrorLog(company_id=2, error_message="KeyError: 'narx' — A yangi xato", endpoint="/api/orders", method="POST",
             created_at=_hozir_tk - timedelta(hours=1)),
    ErrorLog(company_id=3, error_message="B xatosi", endpoint="/api/b", method="GET", created_at=_hozir_tk - timedelta(minutes=10)),
    ErrorLog(company_id=4, error_message="G eski xato", endpoint="/api/g", method="GET", created_at=_hozir_tk - timedelta(hours=25)),
])
_db.commit()
_db.close()


def mijoz(u):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(c, "post", "/login", data={"username": u, "password": "Parol123!"}, follow_redirects=False)
    return c, getattr(r, "status_code", 599)


CE, _s1 = mijoz("mj_ega")
CA, _s2 = mijoz("mj_a_admin")
CM, _s3 = mijoz("mj_a_menejer")
CB, _s4 = mijoz("mj_b_admin")
if {_s1, _s2, _s3, _s4} != {302}:
    print("LOGIN BO'LMADI", _s1, _s2, _s3, _s4)
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)


def bazadan(fn):
    s = SessionLocal()
    try:
        return fn(s)
    except Exception as e:                 # noqa: BLE001
        return f"XATO: {type(e).__name__}: {e}"
    finally:
        s.close()


def murojaatlar_soni():
    if Murojaat is None:
        return -1
    return bazadan(lambda s: (s.query(Murojaat).count(), s.query(MurojaatXabari).count()))


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_tab = models.Base.metadata.tables
check("S1 jadvallar `murojaatlar`, `murojaat_xabarlari` (company_id NOT NULL; xabar → murojaat, ON DELETE CASCADE)",
      "murojaatlar" in _tab and "murojaat_xabarlari" in _tab and not _tab["murojaatlar"].c.company_id.nullable
      and not _tab["murojaat_xabarlari"].c.company_id.nullable
      and any(fk.column.table.name == "murojaatlar" and fk.ondelete == "CASCADE" for fk in _tab["murojaat_xabarlari"].c.murojaat_id.foreign_keys),
      sorted(t for t in _tab if "murojaat" in t))
check("S2 `_TENANT_RULES[\"MurojaatXabari\"]` — o'z murojaatidan; foydalanuvchiga FK yo'q (tiklashda `users` tiklanmaydi)",
      xavfsiz(lambda: models._TENANT_RULES["MurojaatXabari"]) == [("murojaat_id", "Murojaat")]
      and not [fk for t in ("murojaatlar", "murojaat_xabarlari") if t in _tab for c in _tab[t].c for fk in c.foreign_keys
               if fk.column.table.name == "users"])
check("S3 korxona zaxirasidan tashqari (`crud._NON_TENANT_TABLES`), tozalash tartibida YO'Q (`_reset_table_order`)",
      {"murojaatlar", "murojaat_xabarlari"} <= set(getattr(crud, "_NON_TENANT_TABLES", set()))
      and not [m for m in xavfsiz(crud._reset_table_order, []) if m.__name__ in ("Murojaat", "MurojaatXabari")])
_mb = xavfsiz(main._yuklama_manbalari, {})
check("S4 rasm papkasi `murojaat` fayl himoyasida (o'z korxonasi) va platforma admini sharti `yuklangan_fayl` da",
      "murojaat" in _mb and 'papka == "murojaat" and getattr(user, "is_platform_admin", False)' in fayl("main.py")
      and "_mj.rasm_bormi(db" in fayl("main.py"))
_yol = {(sorted(getattr(r, "methods", None) or [""])[0], getattr(r, "path", "")) for r in main.app.routes}
_kut_yol = {("GET", "/murojaat"), ("GET", "/api/murojaatlar"), ("POST", "/api/murojaatlar"), ("GET", "/api/murojaatlar/{murojaat_id}"),
            ("POST", "/api/murojaatlar/{murojaat_id}/xabar"), ("GET", "/api/platform/murojaatlar"),
            ("GET", "/api/platform/murojaatlar/{murojaat_id}"), ("POST", "/api/platform/murojaatlar/{murojaat_id}/javob"),
            ("POST", "/api/platform/murojaatlar/{murojaat_id}/yopish")}
check("S5 marshrutlar (9 ta) bor", _kut_yol <= _yol, sorted(_kut_yol - _yol))
_base = fayl("templates/base.html")
check("S6 menyu: «Yordam / Murojaat» — Admin blokida, platforma egasida emas; «Platforma» yonida son",
      'href="/murojaat"' in _base and "{% if not current_user.is_platform_admin %}" in _base
      and _base.find('href="/murojaat"') > _base.find('href="/rollar"') and "murojaat_soni(current_user)" in _base)
check("S7 jurnal: `AUDIT_AMALLARI[\"loy_tuzatish\"]` (zip 150 dagi bir martalik tuzatish o'zbekcha nom bilan)",
      isinstance(getattr(crud, "AUDIT_AMALLARI", {}).get("loy_tuzatish"), tuple))
check("S8 Telegram — `_send_telegram(…, company_id=None)` (platforma egasining muhit boti)",
      "_send_telegram(matn, company_id=None)" in fayl("main.py"))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Y. Yaratish (korxona admini)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
TG.clear()
_matn1 = "Buyurtmani saqlaganda xato chiqyapti.\nIkkinchi qator <b>qalin</b> & «qo'shtirnoq»"
r = req(CA, "post", "/api/murojaatlar", data={"turi": "xato", "matn": "  " + _matn1 + "  ", "sahifa": "/orders",
                                               "ekran": "1280x800"})
M1 = (js(r) or {}).get("id")
check("Y1 korxona admini — 200, murojaat raqami", r.status_code == 200 and isinstance(M1, int), (r.status_code, r.text[:200]))


def _m(mid):
    return bazadan(lambda s: s.query(Murojaat).filter(Murojaat.id == mid).first()) if Murojaat is not None else None


def _xlar(mid):
    if MurojaatXabari is None:
        return []
    return bazadan(lambda s: [(x.kimdan, x.muallif, x.matni, x.rasm, x.company_id)
                              for x in s.query(MurojaatXabari).filter(MurojaatXabari.murojaat_id == mid).order_by(MurojaatXabari.id).all()])


_m1 = _m(M1)
check("Y2 bazada: korxona 2, «Xato», «yangi», sahifa /orders, muallif (ism + login); birinchi xabar — mijozdan, matn bo'shliqsiz",
      _m1 is not None and not isinstance(_m1, str) and _m1.company_id == 2 and _m1.turi == "xato" and _m1.holat == "yangi"
      and _m1.kelgan_sahifa == "/orders" and _m1.yaratgan == "Alisher Admin" and _m1.yaratgan_login == "mj_a_admin"
      and _xlar(M1) == [("mijoz", "Alisher Admin", _matn1, None, 2)], (_m1, _xlar(M1)))
_tg1 = [t for t in TG if t[0].startswith("🆘")]
check("Y3 Telegram egasiga BITTA xabar (`company_id=None`): raqam, korxona, kim, tur, sahifa, matn",
      len(TG) == 1 and len(_tg1) == 1 and _tg1[0][1] is None and f"#{M1}" in _tg1[0][0] and "MJ Alfa Dekor" in _tg1[0][0]
      and "Alisher Admin (mj_a_admin)" in _tg1[0][0] and "Turi: Xato" in _tg1[0][0] and "Sahifa: /orders" in _tg1[0][0]
      and "Ikkinchi qator <b>qalin</b>" in _tg1[0][0], TG)
_k1 = xavfsiz(lambda: json.loads(_m1.kontekst), {})
check("Y4 kontekst: brauzer, ekran 1280x800, oxirgi xato — A ning 1 soat oldingisi (2 kunlik eski va B niki — EMAS)",
      isinstance(_k1, dict) and _k1.get("ekran") == "1280x800" and (_k1.get("brauzer") or "") != ""
      and (_k1.get("oxirgi_xato") or {}).get("xabar", "").startswith("KeyError: 'narx'")
      and (_k1.get("oxirgi_xato") or {}).get("endpoint") == "/api/orders" and (_k1.get("oxirgi_xato") or {}).get("usul") == "POST", _k1)
_g = xavfsiz(lambda: bazadan(lambda s: MJ.oxirgi_xato(s, 4)), "yiqildi")
_b3 = xavfsiz(lambda: bazadan(lambda s: MJ.oxirgi_xato(s, 3)), None)
check("Y4b oxirgi xato — faqat 24 soat ichidagisi (25 soat oldingi — yo'q), o'z korxonasiniki (B — o'zining 10 daqiqalik xatosi)",
      _g is None and isinstance(_b3, dict) and _b3.get("xabar") == "B xatosi", (_g, _b3))
_old = murojaatlar_soni()
_rad = []
for _d, _nom in (({"turi": "xato", "matn": "   "}, "bo'sh matn"), ({"turi": "boshqa", "matn": "salom"}, "noto'g'ri tur"),
                 ({"turi": "savol", "matn": "x" * 4001}, "4001 belgi")):
    rr = req(CA, "post", "/api/murojaatlar", data=_d)
    if rr.status_code != 400:
        _rad.append((_nom, rr.status_code))
check("Y5 bo'sh / 4001 belgili matn, noto'g'ri tur — 400, hech narsa yozilmaydi, Telegram yo'q",
      not _rad and murojaatlar_soni() == _old and len(TG) == 1, (_rad, murojaatlar_soni(), _old))
r = req(CA, "post", "/api/murojaatlar", data={"turi": "savol", "matn": "x" * 4000, "sahifa": "javascript:alert(1)",
                                               "ekran": "<script>"})
_m4 = _m((js(r) or {}).get("id"))
_k4 = xavfsiz(lambda: json.loads(_m4.kontekst), {})
check("Y6 4000 belgi — qabul; begona sahifa («javascript:…») va ekran — YOZILMAYDI",
      r.status_code == 200 and _m4 is not None and not isinstance(_m4, str) and _m4.kelgan_sahifa is None and _k4.get("ekran") is None,
      (r.status_code, getattr(_m4, "kelgan_sahifa", None), _k4))
r = req(CA, "post", "/api/murojaatlar", data={"turi": "taklif", "matn": "Rasm bilan taklif"},
        files={"file": ("ekran.png", png_bayt(), "image/png")})
M2 = (js(r) or {}).get("id")
_x2 = _xlar(M2)
RASM_A = _x2[0][3] if _x2 else None
check("Y7 PNG rasm bilan — saqlandi (`/static/uploads/murojaat/<nom>.png`), fayl diskda, Telegramda «rasm biriktirilgan»",
      r.status_code == 200 and RASM_A and re.fullmatch(r"/static/uploads/murojaat/[0-9a-f]{32}\.png", RASM_A)
      and os.path.isfile(os.path.join(ROOT, RASM_A.lstrip("/"))) and "📎 rasm biriktirilgan" in (TG[-1][0] if TG else ""), (r.status_code, _x2))
_old = murojaatlar_soni()
_fb = papka_fayllari(MJ_PAPKA)
r = req(CA, "post", "/api/murojaatlar", data={"turi": "xato", "matn": "gif"}, files={"file": ("a.gif", b"GIF89a....", "image/gif")})
check("Y8 ruxsatsiz rasm turi (.gif) — 400; murojaat ham, fayl ham yo'q", r.status_code == 400 and murojaatlar_soni() == _old
      and papka_fayllari(MJ_PAPKA) == _fb, (r.status_code, r.text[:150]))
r = req(CM, "post", "/api/murojaatlar", data={"turi": "xato", "matn": "menejerdan"})
_r2 = req(CM, "get", "/api/murojaatlar")
_r3 = req(CM, "get", f"/api/murojaatlar/{M1}")
check("Y9 menejer (admin emas) — 403 (yozish, ro'yxat, yozishma)", r.status_code == 403 and _r2.status_code == 403
      and _r3.status_code == 403, (r.status_code, _r2.status_code, _r3.status_code))
r = req(CE, "post", "/api/murojaatlar", data={"turi": "xato", "matn": "egadan"})
_r2 = req(CE, "get", "/murojaat", follow_redirects=False)
check("Y10 platforma egasi — murojaat yozmaydi (403), sahifa → /platforma", r.status_code == 403 and _r2.status_code == 303
      and _r2.headers.get("location") == "/platforma", (r.status_code, _r2.status_code, _r2.headers.get("location")))
_r = req(CA, "get", "/murojaat")
check("Y11 sahifa (korxona admini) — 200: sarlavha, 4 tur, forma, ro'yxat", _r.status_code == 200 and "Yordam / Murojaat" in _r.text
      and all(t in _r.text for t in ("Xato", "Savol", "Taklif", "To&#39;lov / obuna")) and 'id="mjMatn"' in _r.text
      and 'id="mjRoyxat"' in _r.text, _r.status_code)
# sutkalik chegara: hozirgacha A — 3 ta; yana 17 ta → 20; 21-chisi (rasm bilan) — 400, rasm va kichik nusxasi o'chadi
_kchk = getattr(MJ, "KUNLIK_CHEGARA", 20)
_bor = xavfsiz(lambda: bazadan(lambda s: s.query(Murojaat).filter(Murojaat.company_id == 2).count()), 0)
_bor = _bor if isinstance(_bor, int) else _kchk          # asl kodda (jadval yo'q) — to'ldirish so'rovlari yuborilmaydi
_ok = 0
for i in range(max(0, _kchk - _bor)):
    if req(CA, "post", "/api/murojaatlar", data={"turi": "savol", "matn": f"to'ldirish {i}"}).status_code == 200:
        _ok += 1
_fb, _kb = papka_fayllari(MJ_PAPKA), papka_fayllari(KICHIK_PAPKA)
_old = murojaatlar_soni()
r = req(CA, "post", "/api/murojaatlar", data={"turi": "xato", "matn": "21-chi"}, files={"file": ("b.png", png_bayt((0, 90, 0)), "image/png")})
check(f"Y12 sutkalik chegara ({_kchk}) — keyingisi 400 («Bir sutkada …»); yuklangan rasm VA kichik nusxasi o'chirildi (yetim fayl yo'q)",
      _ok == _kchk - _bor and r.status_code == 400 and "Bir sutkada" in r.text and murojaatlar_soni() == _old
      and papka_fayllari(MJ_PAPKA) == _fb and papka_fayllari(KICHIK_PAPKA) == _kb,
      (_ok, r.status_code, r.text[:120], papka_fayllari(MJ_PAPKA) - _fb, papka_fayllari(KICHIK_PAPKA) - _kb))
r = req(CB, "post", "/api/murojaatlar", data={"turi": "tolov", "matn": "Obunani uzaytirmoqchimiz", "sahifa": "/"})
MB = (js(r) or {}).get("id")
check("Y13 boshqa korxona (B) — o'z chegarasi alohida (A chegarasi unga ta'sir qilmaydi)", r.status_code == 200 and isinstance(MB, int),
      (r.status_code, r.text[:150]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("L. Mijoz: ro'yxat, yozishma, qo'shimcha xabar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_la = js(req(CA, "get", "/api/murojaatlar")) or {}
_lb = js(req(CB, "get", "/api/murojaatlar")) or {}
_ida = {q.get("id") for q in _la.get("murojaatlar", [])}
_idb = {q.get("id") for q in _lb.get("murojaatlar", [])}
check("L1 ro'yxat — faqat o'z korxonasi (A — 20 ta, B — 1 ta; kesishma yo'q); tur / holat nomlari, parcha (160 belgigacha)",
      M1 in _ida and MB in _idb and not (_ida & _idb) and len(_ida) == _kchk and len(_idb) == 1
      and all(len(q.get("parcha") or "") <= 160 for q in _la.get("murojaatlar", []))
      and any(q.get("turi_nomi") == "Xato" and q.get("holat_nomi") == "Yangi" for q in _la.get("murojaatlar", [])),
      (len(_ida), len(_idb)))
_y = js(req(CA, "get", f"/api/murojaatlar/{M1}")) or {}
check("L2 yozishma — xabarlar (matn aslicha), kontekst MIJOZGA berilmaydi", [x.get("matn") for x in _y.get("xabarlar", [])] == [_matn1]
      and "kontekst" not in _y and _y.get("holat") == "yangi", _y)
_n = [req(CB, "get", f"/api/murojaatlar/{M1}").status_code, req(CA, "get", f"/api/murojaatlar/{MB}").status_code,
      req(CA, "get", "/api/murojaatlar/999999").status_code]
check("L3 begona korxona murojaati va yo'q raqam — 404", _n == [404, 404, 404], _n)
TG.clear()
_old = _xlar(MB)
_n = req(CA, "post", f"/api/murojaatlar/{MB}/xabar", data={"matn": "begonaga"}).status_code
check("L4 begona murojaatga xabar — 404, hech narsa yozilmaydi, Telegram yo'q", _n == 404 and _xlar(MB) == _old and not TG, _n)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P. Platforma: ro'yxat, yozishma, javob, yopish")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_p = js(req(CE, "get", "/api/platform/murojaatlar?holat=")) or {}
_pq = {q.get("id"): q for q in _p.get("murojaatlar", [])}
check("P1 platforma — HAMMA korxonalar (A va B), korxona nomi, sanoq («Yangi» = 21)",
      M1 in _pq and MB in _pq and _pq[M1].get("korxona") == "MJ Alfa Dekor" and _pq[MB].get("korxona") == "MJ Beta Fasad"
      and (_p.get("sanoq") or {}).get("yangi") == _kchk + 1 and _pq[M1].get("oqilmagan") is True, (_p.get("sanoq"), len(_pq)))
_pf = js(req(CE, "get", "/api/platform/murojaatlar?korxona=3")) or {}
check("P2 korxona filtri — faqat B", [q.get("id") for q in _pf.get("murojaatlar", [])] == [MB], _pf.get("murojaatlar"))
_n = [req(CA, "get", "/api/platform/murojaatlar").status_code, req(CB, "get", f"/api/platform/murojaatlar/{M1}").status_code,
      req(CA, "post", f"/api/platform/murojaatlar/{M1}/javob", data={"matn": "o'zim"}).status_code,
      req(CA, "post", f"/api/platform/murojaatlar/{M1}/yopish").status_code]
check("P3 oddiy korxona admini — platforma marshrutlari 403", _n == [403, 403, 403, 403], _n)
_py = js(req(CE, "get", f"/api/platform/murojaatlar/{M1}")) or {}
check("P4 platforma yozishmasi — kontekst (ekran, oxirgi xato), korxona, login; ochilgach «o'qilmagan» emas",
      (_py.get("kontekst") or {}).get("ekran") == "1280x800" and _py.get("korxona") == "MJ Alfa Dekor"
      and _py.get("yaratgan_login") == "mj_a_admin" and _py.get("sahifa") == "/orders"
      and {q.get("id"): q for q in (js(req(CE, "get", "/api/platform/murojaatlar")) or {}).get("murojaatlar", [])}.get(M1, {}).get("oqilmagan") is False,
      _py)
TG.clear()
r = req(CE, "post", f"/api/platform/murojaatlar/{M1}/javob", data={"matn": "Rahmat, tuzatdik. Sahifani yangilang."},
        files={"file": ("javob.png", png_bayt((10, 10, 200)), "image/png")})
_xj = _xlar(M1)
RASM_P = _xj[-1][3] if _xj else None
check("P5 javob — 200; xabar platformadan (muallif — egasi, rasm bilan, korxona — A); holat «javob_berildi»; Telegram YO'Q (o'zi yozdi)",
      r.status_code == 200 and len(_xj) == 2 and _xj[-1][0] == "platforma" and _xj[-1][1] == "Platforma Egasi" and RASM_P
      and _xj[-1][4] == 2 and getattr(_m(M1), "holat", None) == "javob_berildi" and not TG, (r.status_code, _xj))
_la = js(req(CA, "get", "/api/murojaatlar")) or {}
_q1 = {q.get("id"): q for q in _la.get("murojaatlar", [])}.get(M1, {})
_soni = xavfsiz(lambda: bazadan(lambda s: MJ.mijoz_soni(s, s.query(User).filter(User.username == "mj_a_admin").first())), -1)
check("P6 mijozda — «yangi javob» belgisi, menyu soni 1; ro'yxatda holat «Javob berildi»",
      _q1.get("yangi_javob") is True and _q1.get("holat_nomi") == "Javob berildi" and _soni == 1, (_q1, _soni))
_y = js(req(CA, "get", f"/api/murojaatlar/{M1}")) or {}
_q1 = {q.get("id"): q for q in (js(req(CA, "get", "/api/murojaatlar")) or {}).get("murojaatlar", [])}.get(M1, {})
_soni = xavfsiz(lambda: bazadan(lambda s: MJ.mijoz_soni(s, s.query(User).filter(User.username == "mj_a_admin").first())), -1)
check("P7 mijoz yozishmani ochdi — javob ko'rinadi, «yangi javob» va menyu soni 0",
      [x.get("kimdan") for x in _y.get("xabarlar", [])] == ["mijoz", "platforma"] and _q1.get("yangi_javob") is False and _soni == 0,
      (_q1, _soni))
TG.clear()
r = req(CA, "post", f"/api/murojaatlar/{M1}/xabar", data={"matn": "Yana bir savol"})
_soni_pl = xavfsiz(lambda: bazadan(lambda s: MJ.platforma_soni(s)), -1)
check("P8 mijoz yana yozdi — holat «yangi», Telegram «mijozdan yangi xabar», platforma soni = javob kutayotganlar",
      r.status_code == 200 and getattr(_m(M1), "holat", None) == "yangi" and len(TG) == 1 and TG[0][0].startswith(f"💬 Murojaat #{M1}")
      and TG[0][1] is None and _soni_pl == _kchk + 1, (r.status_code, TG, _soni_pl))
r = req(CE, "post", f"/api/platform/murojaatlar/{M1}/yopish")
_old = _xlar(M1)
_n = [req(CA, "post", f"/api/murojaatlar/{M1}/xabar", data={"matn": "yopilgandan keyin"}).status_code,
      req(CE, "post", f"/api/platform/murojaatlar/{M1}/javob", data={"matn": "yopilgandan keyin"}).status_code,
      req(CE, "post", f"/api/platform/murojaatlar/{M1}/yopish").status_code]
_m1 = _m(M1)
check("P9 yopish — «yopildi» (kim, qachon); keyin mijoz ham, platforma ham yozolmaydi (409), qayta yopish — 409; xabar qo'shilmadi",
      r.status_code == 200 and getattr(_m1, "holat", None) == "yopildi" and getattr(_m1, "yopgan", None) == "Platforma Egasi"
      and getattr(_m1, "yopilgan", None) is not None and _n == [409, 409, 409] and _xlar(M1) == _old, (r.status_code, _n))
_n = [req(CE, "get", "/api/platform/murojaatlar/999999").status_code,
      req(CE, "post", "/api/platform/murojaatlar/999999/javob", data={"matn": "x"}).status_code,
      req(CE, "post", "/api/platform/murojaatlar/999999/yopish").status_code]
check("P10 yo'q raqam — 404 (platforma)", _n == [404, 404, 404], _n)
_r = req(CE, "post", f"/api/platform/murojaatlar/{MB}/javob", data={"matn": "   "})
check("P11 bo'sh javob — 400, hech narsa yozilmaydi", _r.status_code == 400 and len(_xlar(MB)) == 1, (_r.status_code, _xlar(MB)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. Rasm himoyasi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_n = {k: req(c, "get", RASM_A or "/static/uploads/murojaat/yoq.png").status_code for k, c in
      (("A", CA), ("A_menejer", CM), ("B", CB), ("ega", CE))}
check("R1 mijoz rasmi: o'z korxonasi — 200 (admin ham, menejer ham), begona korxona — 404, platforma egasi — 200",
      _n == {"A": 200, "A_menejer": 200, "B": 404, "ega": 200}, _n)
_n = {k: req(c, "get", (RASM_P or "/x") + "?o=k").status_code for k, c in (("A", CA), ("B", CB), ("ega", CE))}
check("R2 platforma javobidagi rasm (kichik nusxa ham): A — 200, B — 404, egasi — 200", _n == {"A": 200, "B": 404, "ega": 200}, _n)
# boshqa papka: korxona A ning ombor rasmi — platforma egasiga 404 (alohida shart faqat murojaat papkasi uchun)
_inv_url = None
_s = SessionLocal()
try:
    os.makedirs(os.path.join(UPL, "inventory"), exist_ok=True)
    import uuid as _uuid
    _inv_nom = _uuid.uuid4().hex + ".png"
    with open(os.path.join(UPL, "inventory", _inv_nom), "wb") as _f:
        _f.write(png_bayt())
    _inv_url = f"/static/uploads/inventory/{_inv_nom}"
    _s.add(Inventory(company_id=2, item_name="MJ rasmli material", unit="kg", stock_quantity=0, min_stock=0, image_url=_inv_url,
                     category="Kimyoviy qo'shimchalar"))
    _s.commit()
finally:
    _s.close()
_n = {k: req(c, "get", _inv_url).status_code for k, c in (("A", CA), ("ega", CE))}
check("R3 platforma egasining alohida sharti FAQAT murojaat papkasi — A ning ombor rasmi egasiga 404, A ga 200",
      _n == {"A": 200, "ega": 404}, _n)
# yetim fayl (murojaat papkasida, lekin hech bir xabarga bog'lanmagan) — platforma egasiga ham 404
os.makedirs(MJ_PAPKA, exist_ok=True)
_yetim = "f" * 32 + ".png"
with open(os.path.join(MJ_PAPKA, _yetim), "wb") as _f:
    _f.write(png_bayt())
_n = {k: req(c, "get", "/static/uploads/murojaat/" + _yetim).status_code for k, c in (("A", CA), ("ega", CE))}
check("R5 murojaat papkasidagi yetim fayl (yozuvga bog'lanmagan) — platforma egasiga ham, korxonaga ham 404",
      _n == {"A": 404, "ega": 404}, _n)
_c0 = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_r = req(_c0, "get", RASM_A or "/x", follow_redirects=False)
check("R4 kirmagan foydalanuvchi — rasm berilmaydi (401 / kirish sahifasiga)", _r.status_code in (401, 302, 303, 307), _r.status_code)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("M. Menyu")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def nav(c, url="/projects"):
    t = req(c, "get", url).text or ""
    i = t.find('<nav class="s-nav">')
    return t[i:t.find("</nav>", i)] if i >= 0 else ""


# A ga yangi javob (B ga ham — sanoq korxonaga bog'liqmi)
_mid = next(iter(sorted(q for q in _ida if q != M1)), 999999)
req(CE, "post", f"/api/platform/murojaatlar/{_mid}/javob", data={"matn": "javob 2"})
req(CE, "post", f"/api/platform/murojaatlar/{MB}/javob", data={"matn": "B ga javob"})
_na, _nm, _ne = nav(CA), nav(CM), nav(CE, "/")
_badge = re.search(r'href="/murojaat"[^>]*>[\s\S]*?</a>', _na)
check("M1 korxona admini menyusida «Yordam / Murojaat», o'qilmagan javob soni 1 (B niki sanalmaydi)",
      _badge is not None and "Yordam / Murojaat" in _badge.group(0) and re.search(r'<span class="n-badge"[^>]*>1</span>', _badge.group(0)),
      _badge.group(0) if _badge else _na[-600:])
check("M2 menejer va platforma egasi menyusida «Yordam / Murojaat» YO'Q", 'href="/murojaat"' not in _nm and 'href="/murojaat"' not in _ne
      and _nm != "" and _ne != "")
_pl = re.search(r'href="/platforma"[^>]*>[\s\S]*?</a>', _ne)
# kutilgan son — bazadan MUSTAQIL (javob kutayotgan = holati «yangi», hamma korxonalar)
_kut = bazadan(lambda s: s.query(Murojaat).filter(Murojaat.holat == "yangi").count()) if Murojaat is not None else -1
check(f"M3 platforma egasi menyusida «Platforma» yonida javob kutayotganlar soni ({_kut})",
      _pl is not None and isinstance(_kut, int) and _kut > 0 and f'<span class="n-badge" title="Javob kutayotgan murojaatlar">{_kut}</span>' in _pl.group(0),
      (_pl.group(0) if _pl else None, _kut))
req(CA, "get", f"/api/murojaatlar/{_mid}")
_badge = re.search(r'href="/murojaat"[^>]*>[\s\S]*?</a>', nav(CA))
check("M4 o'qilgach — son yo'qoladi", _badge is not None and "n-badge" not in _badge.group(0), _badge.group(0) if _badge else None)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Zaxira va tozalash — yozishma korxona ma'lumotiga kirmaydi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_s = SessionLocal()
try:
    with contextlib.redirect_stdout(_quiet):
        _zax = crud.export_full_backup(_s, company_id=2)
    _jad = set((_zax.get("tables") or _zax.get("data") or {}).keys()) if isinstance(_zax, dict) else set()
    _matn_z = json.dumps(_zax, ensure_ascii=False, default=str)
finally:
    _s.close()
check("Z1 korxona zaxirasida `murojaatlar` / `murojaat_xabarlari` YO'Q (zaxirada boshqa jadvallar bor)",
      bool(_jad) and "murojaatlar" not in _jad and "murojaat_xabarlari" not in _jad and _matn1 not in _matn_z, sorted(_jad)[:8])
_old = bazadan(lambda s: (s.query(Murojaat).filter(Murojaat.company_id == 2).count(),
                          s.query(MurojaatXabari).filter(MurojaatXabari.company_id == 2).count())) if Murojaat is not None else None
_s = SessionLocal()
try:
    with contextlib.redirect_stdout(_quiet):
        _imp = crud.import_full_backup(_s, _zax, company_id=2, replace=True)
finally:
    _s.close()
_yangi = bazadan(lambda s: (s.query(Murojaat).filter(Murojaat.company_id == 2).count(),
                            s.query(MurojaatXabari).filter(MurojaatXabari.company_id == 2).count())) if Murojaat is not None else None
check("Z2 zaxiradan tiklash (almashtirish) — yozishma O'ZGARMADI", isinstance(_imp, dict) and _imp.get("success") is not False
      and _old == _yangi and _old and _old[0] == _kchk, (_old, _yangi, str(_imp)[:200]))
_s = SessionLocal()
try:
    with contextlib.redirect_stdout(_quiet):
        crud.factory_reset_all_data(_s, company_id=2)
finally:
    _s.close()
_yangi = bazadan(lambda s: (s.query(Murojaat).filter(Murojaat.company_id == 2).count(),
                            s.query(MurojaatXabari).filter(MurojaatXabari.company_id == 2).count())) if Murojaat is not None else None
_b = bazadan(lambda s: s.query(Murojaat).filter(Murojaat.company_id == 3).count()) if Murojaat is not None else None
check("Z3 korxonani tozalash — yozishma O'CHMAYDI (A ham, B ham)", _old == _yangi and _b == 1, (_old, _yangi, _b))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. ORM qo'riqchisi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_s = SessionLocal()
_rad = None
try:
    _s.add(MurojaatXabari(company_id=3, murojaat_id=M1, kimdan="mijoz", muallif="x", matni="begona korxona"))
    _s.flush()
    _rad = False
except Exception as e:                     # noqa: BLE001
    _rad = type(e).__name__
finally:
    _s.rollback()
    _s.close()
check("T1 xabar korxonasi (3) murojaatnikidan (2) farq qiladi — ORM rad etadi (`TenantMismatchError`)",
      _rad == "TenantMismatchError", _rad)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J. Jurnal — `loy_tuzatish`")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_s = SessionLocal()
try:
    with contextlib.redirect_stdout(_quiet):
        crud.log_activity(_s, "loy_tuzatish", "order", 1, entity_label="ORD-MJ-1", performed_by="Tizim (tuzatish)",
                          old_value="Loy rejasi 500 000 kg", new_value="Loy rejasi 500 kg (xato tuzatildi)", company_id=3)
finally:
    _s.close()
_t = req(CB, "get", "/logs").text or ""
check("J1 «Tizim jurnallari»: «ORD-MJ-1 — loy rejasi xatosi tuzatildi» («amal: loy_tuzatish» emas)",
      "loy rejasi xatosi tuzatildi" in _t and "amal: loy_tuzatish" not in _t and "ORD-MJ-1" in _t,
      re.findall(r".{0,80}ORD-MJ-1.{0,80}", _t)[:2])

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H. «Ombor harakatlari → jami» — penoplast bitta qatorda")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_s = SessionLocal()
try:
    _p = Inventory(company_id=3, item_name="MJ Penoplast 14P", unit="dona", stock_quantity=7, min_stock=0, category="Penoplast",
                   is_penoplast=True)
    _k = Inventory(company_id=3, item_name="MJ Kley", unit="kg", stock_quantity=5, min_stock=0, category="Kimyoviy qo'shimchalar")
    _s.add_all([_p, _k])
    _s.flush()
    _t0 = datetime(2026, 10, 3, 6, 0, 0)
    for _inv, _tur, _q, _u in ((_p, "in", 10.0, "dona"), (_p, "out", 2.0, "blok"), (_p, "out", 1.0, "blok"), (_k, "in", 5.0, "kg")):
        _s.add(InventoryMovement(company_id=3, inventory_id=_inv.id, item_name=_inv.item_name, movement_type=_tur, quantity=_q,
                                 unit=_u, reason="sinov", created_at=_t0))
    _s.commit()
    PID = _p.id
finally:
    _s.close()
_j = js(req(CB, "get", "/api/inventory/movements/jami?date_from=2026-10-01&date_to=2026-10-05")) or {}
_pq = [m for m in _j.get("materiallar", []) if m.get("name") == "MJ Penoplast 14P"]
check("H1 penoplast — BITTA qator, birligi «dona» (materialniki): kirim 10, chiqim 3, 3 ta harakat; kley — o'zi",
      _pq == [{"name": "MJ Penoplast 14P", "unit": "dona", "in": 10.0, "out": 3.0, "soni": 3}]
      and {"name": "MJ Kley", "unit": "kg", "in": 5.0, "out": 0.0, "soni": 1} in _j.get("materiallar", []) and _j.get("jami") == 4,
      _j)
_j2 = js(req(CB, "get", f"/api/inventory/movements/jami?item_id={PID}&date_from=2026-10-01&date_to=2026-10-05")) or {}
check("H2 material filtri bilan ham — bitta qator", [m.get("unit") for m in _j2.get("materiallar", [])] == ["dona"], _j2)

# ── tozalash: test yaratgan fayllar (repo papkasida qolmasin)
for _p_, _bosh in ((MJ_PAPKA, _BOSH_FAYLLAR), (KICHIK_PAPKA, _BOSH_KICHIK)):
    for _f in papka_fayllari(_p_) - _bosh:
        xavfsiz(lambda: os.remove(os.path.join(_p_, _f)))
if _inv_url:
    xavfsiz(lambda: os.remove(os.path.join(UPL, "inventory", os.path.basename(_inv_url))))
    for _y in glob.glob(os.path.join(UPL, "_kichik", "inventory", os.path.splitext(os.path.basename(_inv_url))[0] + "_*")):
        xavfsiz(lambda: os.remove(_y))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if not FAIL else 1)
