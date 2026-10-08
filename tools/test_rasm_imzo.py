#!/usr/bin/env python3
"""
test_rasm_imzo.py — kech128 (zip 152): zip 151 ning staging JONLI sinovida (08.10) topilgan ikki kichik nuqson.

NIMA UCHUN KERAK (O'LCHANGAN):
  1. RASM EMAS FAYL. Ichida rasm bo'lmagan fayl (matn, 18 bayt) `soxta.png` nomi bilan murojaatga biriktirilganda QABUL qilinib
     saqlandi (staging, murojaat #1) — ko'rinishda «singan rasm». Kod tekshiruvi: bu dasturdagi HAMMA rasm yuklash joylarining umumiy
     yo'li (`main._save_upload` — faqat kengaytma tekshirilardi; `rasmni_kichraytir` o'qiy olmasa — ASLICHA saqlaydi) va logotip
     (`/api/settings/company/logo` — faqat brauzer aytgan tur). Endi fayl BOSHIDAGI imzo tekshiriladi: JPEG / PNG / WEBP bo'lmasa —
     400 «Bu fayl rasm emas — JPG, PNG yoki WEBP rasm tanlang», diskka ham, bazaga ham hech narsa yozilmaydi.
  2. 4000 BELGI VA YANGI QATORLAR. Murojaat matni maydoni (`maxlength="4000"`) yangi qatorni 1 belgi sanaydi, brauzer forma (FormData)
     esa uni «\\r\\n» qilib yuboradi — HAQIQIY Chromium da O'LCHANDI (`work/k152/crlf_olchov.py`): 40 qatorli 4000 belgilik matn serverga
     4040 bo'lib keldi va «Matn juda uzun» deb rad etildi (hisoblagich «4000 / 4000» ko'rsatib turganda). Endi `murojaat.matn_tekshir`
     qator oxirlarini tekshiruvdan OLDIN «\\n» ga keltiradi (saqlanadigani ham, Telegram matni ham).
  (Uchinchi topilma — platforma yozishma oynasi rasmlar keyin yuklanganda eng yangi xabarni yashirardi — HAQIQIY brauzerda,
  `tools/test_murojaat_ui.py` B7.)
BO'LIMLAR: S — statik; I — `rasm_imzosi` (imzolar); Y — rasm yuklash joylari (material, tayyor mahsulot, loyiha, retsept, qaytarish,
  detal, buyurtma ilovasi, logotip): rasm emas / bo'sh / GIF / WAVE — 400, diskda va bazada o'zgarish yo'q; haqiqiy JPEG / PNG / WEBP,
  PNG `.jpg` nomli, imzosi to'g'ri buzuq JPEG (avvalgidek ASLICHA — `test_e_rasm` Y5), PDF va chizma (.dwg) ilovalari — 200;
  M — murojaat (yaratish, mijoz xabari, platforma javobi) rasm emas fayl bilan — 400, murojaat / xabar / holat o'zgarmaydi;
  Q — qator oxirlari: «\\r\\n» bilan 4000 belgi — qabul, saqlangani «\\n», Telegram matnida «\\r» yo'q; 4001 — rad; yolg'iz «\\r» — «\\n».
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16; `TENANT_FILTER=1` bilan ham.
Asl kodga (zip 151) qarshi QULAMAYDI — yiqiladi (yangi nomlar `getattr`, HTTP istisno — 599).
Test o'zi yaratgan fayllarni (asl va kichik nusxa, logotip) oxirida o'chiradi / tiklaydi.
ISHLATISH: python3 tools/test_rasm_imzo.py
"""
import os
import io
import sys
import uuid
import tempfile
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "rasm_imzo_test"
_T = tempfile.mkdtemp(prefix="rasm_imzo_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'rasm_imzo_test.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

# test boshlanishidagi yuklangan fayllar (oxirida — faqat test yaratganlari o'chiriladi)
UPL = os.path.join(ROOT, "static", "uploads")


def hamma_fayllar():
    s = set()
    for d, _, fs in os.walk(UPL):
        for f in fs:
            s.add(os.path.join(d, f))
    return s


_BOSH = hamma_fayllar()
_LOGO_ZAXIRA = {}
for _kg in (".png", ".jpg", ".webp"):
    _y = os.path.join(UPL, "logos", f"company_1{_kg}")
    if os.path.isfile(_y):
        with open(_y, "rb") as _f:
            _LOGO_ZAXIRA[_y] = _f.read()

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import models                                  # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, User, Inventory, Project, Recipe, FinishedProduct, ReturnItem, ReturnReason,   # noqa: E402
                    Order, OrderItem, OrderType, OrderAttachment)
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from PIL import Image                              # noqa: E402

Murojaat = getattr(models, "Murojaat", None)
MurojaatXabari = getattr(models, "MurojaatXabari", None)
try:
    import murojaat as MJ                          # noqa: E402
except Exception:                                  # noqa: BLE001
    MJ = None

IMZO = getattr(main, "rasm_imzosi", None)          # asl kodda yo'q — test QULAMAYDI, tekshiruvlar yiqiladi
XABAR = getattr(main, "RASM_EMAS_XABARI", "Bu fayl rasm emas — JPG, PNG yoki WEBP rasm tanlang")

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF] " if os.environ.get("TENANT_FILTER") else "")
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


def oqi(yol):
    try:
        with open(os.path.join(ROOT, yol), encoding="utf-8") as f:
            return f.read()
    except Exception:                      # noqa: BLE001
        return ""


def rasm(w, h, fmt="JPEG", rang=(180, 120, 60), **k):
    b = io.BytesIO()
    Image.new("RGB", (w, h), rang).save(b, fmt, **k)
    return b.getvalue()


def bazadan(fn):
    s = SessionLocal()
    try:
        return fn(s)
    except Exception as e:                 # noqa: BLE001
        return f"XATO: {type(e).__name__}: {e}"
    finally:
        s.close()


def detail(r):
    return (js(r) or {}).get("detail") if isinstance(js(r), dict) else None


JPEG = rasm(200, 150, "JPEG", quality=90)
PNG = rasm(200, 150, "PNG")
WEBP = rasm(200, 150, "WEBP", quality=90)
MATN = b"bu matn, rasm emas"                         # staging dagi `soxta.png` (18 bayt) bilan bir xil
GIF = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
WAVE = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 24
HTML = b"<html><script>alert(1)</script></html>"
BUZUQ_JPEG = b"\xff\xd8\xff\xe0" + os.urandom(2000)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
MAIN = oqi("main.py")
MJPY = oqi("murojaat.py")
PL = oqi("templates/platforma.html")
check("S1 `main.rasm_imzosi` va `RASM_EMAS_XABARI` bor", callable(IMZO) and getattr(main, "RASM_EMAS_XABARI", None) == XABAR
      and XABAR == "Bu fayl rasm emas — JPG, PNG yoki WEBP rasm tanlang", (IMZO, XABAR))
check("S2 `_save_upload`: kengaytmasi rasm bo'lsa — imzo tekshiruvi (kichraytirishdan va diskka yozishdan OLDIN)",
      "if ext in ALLOWED_IMAGE_EXT and rasm_imzosi(contents) is None:" in MAIN
      and 0 < MAIN.find("if ext in ALLOWED_IMAGE_EXT and rasm_imzosi(contents) is None:") < MAIN.find("contents = rasmni_kichraytir(contents, ext)")
      < MAIN.find('with open(os.path.join(folder, fname), "wb") as f:'))
_lg = MAIN[MAIN.find("async def api_upload_company_logo"):]
check("S3 logotip: imzo tekshiruvi diskka yozishdan OLDIN", "if rasm_imzosi(data) is None:" in _lg
      and 0 < _lg.find("if rasm_imzosi(data) is None:") < _lg.find('with open(_os.path.join(papka, nom), "wb") as f:'))
check("S4 `murojaat.matn_tekshir` — qator oxirlari «\\n» ga (uzunlik tekshiruvidan OLDIN)",
      't = t.replace("\\r\\n", "\\n").replace("\\r", "\\n").strip()' in MJPY
      and MJPY.find('t = t.replace("\\r\\n", "\\n")') < MJPY.find("if len(t) > MATN_MAX:"))
check("S5 platforma yozishma oynasi: `mpPastga` — rasm `load` da (foydalanuvchi tepaga aylantirmagan bo'lsa) eng pastga",
      "function mpPastga(xs)" in PL and "mpPastga(document.getElementById('mpXabarlar'));" in PL
      and "im.addEventListener('load', function () { if (pastda) xs.scrollTop = xs.scrollHeight; }, {once: true});" in PL
      and "xs.addEventListener('scroll'," in PL)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("I. rasm_imzosi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_im = (lambda b: xavfsiz(lambda: IMZO(b), "yiqildi")) if IMZO else (lambda b: "yo'q")
check("I1 haqiqiy JPEG / PNG / WEBP — turi", (_im(JPEG), _im(PNG), _im(WEBP)) == ("JPEG", "PNG", "WEBP"), (_im(JPEG), _im(PNG), _im(WEBP)))
check("I2 imzosi to'g'ri, ichi buzilgan JPEG — «JPEG» (buzuq rasm avvalgidek ASLICHA saqlanadi)", _im(BUZUQ_JPEG) == "JPEG", _im(BUZUQ_JPEG))
_yoq = {"matn": _im(MATN), "bo'sh": _im(b""), "None": _im(None), "GIF": _im(GIF), "WAVE (RIFF)": _im(WAVE), "HTML": _im(HTML),
        "PDF": _im(b"%PDF-1.4\n"), "qisqa JPEG boshi": _im(b"\xff\xd8"), "qisqa RIFF": _im(b"RIFF\x00\x00\x00\x00WEB"),
        "PNG boshi buzuq": _im(b"\x89PNG" + b"x" * 20)}
check("I3 rasm emas — None (matn, bo'sh, GIF, WAVE, HTML, PDF, qisqa bo'laklar, boshi buzuq PNG)", all(v is None for v in _yoq.values()), _yoq)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Y. Rasm yuklash joylari")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
PAROL = "Parol123!"
_db = SessionLocal()
if not _db.query(Company).filter(Company.id == 2).first():
    _db.add(Company(id=2, name="RI Beta Fasad", code="RI-BETA"))
    _db.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(_db, "ri_admin", PAROL, UserRole.ADMIN, "RI Admin", company_id=1)
    auth.create_user(_db, "ri_ega", PAROL, UserRole.ADMIN, "Platforma Egasi", company_id=1)
    auth.create_user(_db, "ri_b_admin", PAROL, UserRole.ADMIN, "Botir Admin", company_id=2)
_db.query(User).filter(User.username == "ri_ega").update({"is_platform_admin": True})
_db.query(User).filter(User.username.in_(["ri_admin", "ri_b_admin"])).update({"is_platform_admin": False}, synchronize_session=False)
_n = uuid.uuid4().hex[:6]
_inv = Inventory(company_id=1, item_name=f"RI material {_n}", unit="kg")
_prj = Project(company_id=1, project_number=f"RI-{_n}", project_name=f"RI loyiha {_n}", client_name="RI Mijoz")
_rec = Recipe(company_id=1, name=f"RI retsept {_n}")
_fp = FinishedProduct(company_id=1, name=f"RI mahsulot {_n}", quantity=5, unit="dona", category="dona")
_db.add_all([_inv, _prj, _rec, _fp])
_db.commit()
_ord = Order(company_id=1, project_id=_prj.id, order_number=f"RI-{_n}-1", order_type=OrderType.PRODUCT)
_db.add(_ord)
_db.commit()
_oi = OrderItem(company_id=1, order_id=_ord.id, name="RI detal")
_ret = ReturnItem(company_id=1, finished_product_id=_fp.id, item_name="RI qaytarish", quantity=1, reason=ReturnReason.DEFECT)
_db.add_all([_oi, _ret])
_db.commit()
ID = {"inv": _inv.id, "prj": _prj.id, "rec": _rec.id, "fp": _fp.id, "ord": _ord.id, "oi": _oi.id, "ret": _ret.id}
_db.close()


def mijoz(u):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(c, "post", "/login", data={"username": u, "password": PAROL}, follow_redirects=False)
    return c, getattr(r, "status_code", 599)


C, _l1 = mijoz("ri_admin")
CE, _l2 = mijoz("ri_ega")
CB, _l3 = mijoz("ri_b_admin")
check("Y0 uchala foydalanuvchi kirdi (korxona admini, platforma egasi, mijoz korxona admini)", (_l1, _l2, _l3) == (302, 302, 302),
      (_l1, _l2, _l3))

JOYLAR = {"material": f"/api/inventory/{ID['inv']}/image", "tayyor mahsulot": f"/api/finished/{ID['fp']}/image",
          "loyiha": f"/api/projects/{ID['prj']}/image", "retsept": f"/api/recipes/{ID['rec']}/image",
          "qaytarish": f"/api/returns/{ID['ret']}/image", "detal": f"/api/order-items/{ID['oi']}/image",
          "buyurtma ilovasi": f"/api/orders/{ID['ord']}/attachments"}


def rasmlar_bazada():
    def _f(s):
        return (s.query(Inventory.image_url).filter(Inventory.id == ID["inv"]).scalar(),
                s.query(FinishedProduct.image_url).filter(FinishedProduct.id == ID["fp"]).scalar(),
                s.query(Project.image_url).filter(Project.id == ID["prj"]).scalar(),
                s.query(Recipe.image_url).filter(Recipe.id == ID["rec"]).scalar(),
                s.query(ReturnItem.image_url).filter(ReturnItem.id == ID["ret"]).scalar(),
                s.query(OrderItem.image_url).filter(OrderItem.id == ID["oi"]).scalar(),
                s.query(OrderAttachment).filter(OrderAttachment.order_id == ID["ord"]).count(),
                s.query(Company.logo_path).filter(Company.id == 1).scalar())
    return bazadan(_f)


_rad = {}
_oldin_disk, _oldin_baza = hamma_fayllar(), rasmlar_bazada()
for _nom, _yol in JOYLAR.items():
    for _fnom, _bayt, _tur in (("soxta.png", MATN, "image/png"), ("bosh.jpg", b"", "image/jpeg"), ("animatsiya.png", GIF, "image/png"),
                               ("ovoz.webp", WAVE, "image/webp"), ("sahifa.jpg", HTML, "image/jpeg")):
        r = req(C, "post", _yol, files={"file": (_fnom, _bayt, _tur)})
        if not (r.status_code == 400 and detail(r) == XABAR):
            _rad[f"{_nom} / {_fnom}"] = (r.status_code, r.text[:120])
check("Y1 7 ta joy (material, tayyor mahsulot, loyiha, retsept, qaytarish, detal, buyurtma ilovasi): rasm emas (matn, bo'sh, GIF, "
      "WAVE, HTML) — 400 «Bu fayl rasm emas …»", not _rad, _rad)
check("Y2 … diskka HECH NARSA yozilmadi (asl ham, kichik nusxa ham), bazada rasm / ilova o'zgarmadi",
      hamma_fayllar() == _oldin_disk and rasmlar_bazada() == _oldin_baza, (sorted(hamma_fayllar() - _oldin_disk)[:6], rasmlar_bazada()))
_o3 = (hamma_fayllar(), rasmlar_bazada())          # Y1 / Y2 natijasiga tayanmaydi
_lr = req(C, "post", "/api/settings/company/logo", files={"file": ("logo.png", MATN, "image/png")})
_lr2 = req(C, "post", "/api/settings/company/logo", files={"file": ("logo.jpg", HTML, "image/jpeg")})
check("Y3 logotip: rasm emas (turi «image/png» deb aytilgan) — 400, fayl yozilmadi, korxona logotipi o'zgarmadi",
      _lr.status_code == 400 and detail(_lr) == XABAR and _lr2.status_code == 400 and detail(_lr2) == XABAR
      and hamma_fayllar() == _o3[0] and rasmlar_bazada() == _o3[1], (_lr.status_code, _lr.text[:120], _lr2.status_code))
_o4 = rasmlar_bazada()
_ok = {}
for (_nom, _yol), (_fnom, _bayt, _tur) in zip(JOYLAR.items(), (("a.jpg", JPEG, "image/jpeg"), ("b.png", PNG, "image/png"),
                                                                 ("c.webp", WEBP, "image/webp"), ("d.jpeg", JPEG, "image/jpeg"),
                                                                 ("e.jpg", PNG, "image/jpeg"), ("f.jpg", BUZUQ_JPEG, "image/jpeg"),
                                                                 ("g.png", PNG, "image/png"))):
    r = req(C, "post", _yol, files={"file": (_fnom, _bayt, _tur)})
    _ok[f"{_nom} / {_fnom}"] = r.status_code
check("Y4 haqiqiy rasmlar — 200 (JPEG, PNG, WEBP, .jpeg; PNG `.jpg` nomli; imzosi to'g'ri buzuq JPEG — avvalgidek ASLICHA)",
      all(v == 200 for v in _ok.values()), _ok)
_b = rasmlar_bazada()
check("Y5 … bazada 6 ta rasm manzili (yangi) va 1 ta ilova yozildi", isinstance(_b, tuple) and isinstance(_o4, tuple) and all(_b[:6])
      and all(_b[i] != _o4[i] for i in range(6)) and _b[6] == _o4[6] + 1, (_b, _o4))
_pdf = req(C, "post", JOYLAR["buyurtma ilovasi"], files={"file": ("hujjat.pdf", b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n",
                                                                     "application/pdf")})
_dwg = req(C, "post", JOYLAR["buyurtma ilovasi"], files={"file": ("chizma.dwg", b"AC1032" + os.urandom(500), "application/octet-stream")})
check("Y6 rasm bo'lmagan ilovalar (PDF, chizma .dwg) — imzo tekshirilmaydi, 200 (avvalgidek)", _pdf.status_code == 200
      and _dwg.status_code == 200, (_pdf.status_code, _dwg.status_code))
_lg = req(C, "post", "/api/settings/company/logo", files={"file": ("logo.png", PNG, "image/png")})
check("Y7 logotip — haqiqiy PNG: 200", _lg.status_code == 200, (_lg.status_code, _lg.text[:120]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("M. Murojaat — rasm emas fayl")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
TG = []
main._send_telegram = lambda matn, company_id=None: TG.append((matn, company_id)) or True


def mj_soni():
    if Murojaat is None:
        return "yo'q"
    return bazadan(lambda s: (s.query(Murojaat).count(), s.query(MurojaatXabari).count()))


_o = (mj_soni(), hamma_fayllar())
r = req(CB, "post", "/api/murojaatlar", data={"turi": "xato", "matn": "soxta rasm bilan"}, files={"file": ("soxta.png", MATN, "image/png")})
check("M1 yangi murojaat + rasm emas fayl — 400 «Bu fayl rasm emas …», murojaat ham, fayl ham YO'Q, Telegram yo'q",
      r.status_code == 400 and detail(r) == XABAR and mj_soni() == _o[0] and hamma_fayllar() == _o[1] and not TG,
      (r.status_code, r.text[:150], mj_soni(), _o[0], len(TG)))
r = req(CB, "post", "/api/murojaatlar", data={"turi": "savol", "matn": "haqiqiy rasm bilan"}, files={"file": ("ekran.png", PNG, "image/png")})
M1 = (js(r) or {}).get("id")
check("M2 haqiqiy PNG bilan — 200", r.status_code == 200 and isinstance(M1, int), (r.status_code, r.text[:150]))
_o = (mj_soni(), hamma_fayllar(), len(TG))
r = req(CB, "post", f"/api/murojaatlar/{M1}/xabar", data={"matn": "qo'shimcha"}, files={"file": ("soxta.webp", MATN, "image/webp")})
check("M3 mijozning qo'shimcha xabari + rasm emas — 400, xabar yozilmadi, fayl yo'q, Telegram yo'q",
      r.status_code == 400 and detail(r) == XABAR and mj_soni() == _o[0] and hamma_fayllar() == _o[1] and len(TG) == _o[2],
      (r.status_code, r.text[:150]))
_h = bazadan(lambda s: s.query(Murojaat.holat).filter(Murojaat.id == M1).scalar()) if Murojaat is not None else None
r = req(CE, "post", f"/api/platform/murojaatlar/{M1}/javob", data={"matn": "javob"}, files={"file": ("soxta.jpg", HTML, "image/jpeg")})
check("M4 platforma javobi + rasm emas — 400, javob yozilmadi, holat o'zgarmadi («yangi»), fayl yo'q",
      r.status_code == 400 and detail(r) == XABAR and mj_soni() == _o[0] and hamma_fayllar() == _o[1] and _h == "yangi"
      and bazadan(lambda s: s.query(Murojaat.holat).filter(Murojaat.id == M1).scalar()) == "yangi", (r.status_code, r.text[:150], _h))
r = req(CE, "post", f"/api/platform/murojaatlar/{M1}/javob", data={"matn": "javob rasm bilan"}, files={"file": ("j.webp", WEBP, "image/webp")})
check("M5 platforma javobi + haqiqiy WEBP — 200, «Javob berildi»", r.status_code == 200
      and bazadan(lambda s: s.query(Murojaat.holat).filter(Murojaat.id == M1).scalar()) == "javob_berildi", (r.status_code, r.text[:150]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Q. Qator oxirlari va 4000 belgi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
MAX = getattr(MJ, "MATN_MAX", 4000) if MJ else 4000
_qatorlar = ["a" * 99] * 40                          # 40 qator: 40 × 99 + 39 ta yangi qator = 3999 (+1 = 4000)
_lf = "\n".join(_qatorlar) + "b"                      # maydon sanagani (har yangi qator — 1 belgi)
_crlf = _lf.replace("\n", "\r\n")                     # brauzer yuborgani (FormData)
check("Q0 sinov matni: maydon hisobi 4000 belgi, yuborilgani 4039 (39 ta «\\r\\n»)", len(_lf) == MAX == 4000 and len(_crlf) == 4039,
      (len(_lf), len(_crlf)))


def oxirgi_xabar(mid):
    if MurojaatXabari is None:
        return None
    return bazadan(lambda s: s.query(MurojaatXabari.matni).filter(MurojaatXabari.murojaat_id == mid)
                   .order_by(MurojaatXabari.id.desc()).first()[0])


TG.clear()
r = req(CB, "post", "/api/murojaatlar", data={"turi": "taklif", "matn": _crlf})
M2 = (js(r) or {}).get("id")
_s = oxirgi_xabar(M2) if M2 else None
check("Q1 yangi murojaat: «\\r\\n» bilan 4000 belgilik matn — 200 (avval «juda uzun» — 400 edi)", r.status_code == 200 and isinstance(M2, int),
      (r.status_code, r.text[:150]))
check("Q2 … saqlangani — «\\n» bilan, AYNAN maydondagi matn (4000 belgi, «\\r» yo'q)", _s == _lf, (len(_s or ""), (_s or "")[:30]))
check("Q3 … Telegram matnida «\\r» yo'q", len(TG) == 1 and "\r" not in TG[0][0] and "a" * 99 + "\n" + "a" * 99 in TG[0][0],
      [t[0][:80] for t in TG])
# keyingi tekshiruvlar Q1 natijasiga tayanmaydi: Q1 yiqilsa (asl kod) — M2 bo'limidagi murojaatga yoziladi
MQ = M2 if isinstance(M2, int) else M1
_o = mj_soni()
r = req(CB, "post", "/api/murojaatlar", data={"turi": "taklif", "matn": _crlf + "c"})
check("Q4 4001 belgi (qatorlar «\\n» sanalganda) — 400 «Matn juda uzun», hech narsa yozilmadi", r.status_code == 400
      and "juda uzun" in (detail(r) or "") and mj_soni() == _o, (r.status_code, r.text[:150]))
r = req(CB, "post", f"/api/murojaatlar/{MQ}/xabar", data={"matn": _crlf})
check("Q5 mijozning qo'shimcha xabari — «\\r\\n» bilan 4000 belgi: 200, saqlangani «\\n» bilan", r.status_code == 200 and oxirgi_xabar(MQ) == _lf,
      (r.status_code, r.text[:150]))
r = req(CE, "post", f"/api/platform/murojaatlar/{MQ}/javob", data={"matn": _crlf})
check("Q6 platforma javobi — «\\r\\n» bilan 4000 belgi: 200, saqlangani «\\n» bilan", r.status_code == 200 and oxirgi_xabar(MQ) == _lf,
      (r.status_code, r.text[:150]))
r = req(CB, "post", f"/api/murojaatlar/{MQ}/xabar", data={"matn": "  birinchi\rikkinchi\r\nuchinchi\n  "})
check("Q7 yolg'iz «\\r» ham «\\n» ga; chetdagi bo'shliqlar olib tashlanadi", r.status_code == 200
      and oxirgi_xabar(MQ) == "birinchi\nikkinchi\nuchinchi", (r.status_code, oxirgi_xabar(MQ)))
_bosh = req(CB, "post", f"/api/murojaatlar/{MQ}/xabar", data={"matn": "\r\n\r\n \r "})
check("Q8 faqat qator oxirlari / bo'shliqdan iborat matn — 400 «Murojaat matnini yozing»", _bosh.status_code == 400
      and detail(_bosh) == "Murojaat matnini yozing", (_bosh.status_code, _bosh.text[:150]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# test yaratgan fayllar — o'chiriladi; logotip — tiklanadi
for _y in hamma_fayllar() - _BOSH:
    try:
        os.remove(_y)
    except OSError:
        pass
for _y, _b in _LOGO_ZAXIRA.items():
    with open(_y, "wb") as _f:
        _f.write(_b)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
os._exit(0 if not FAIL else 1)
