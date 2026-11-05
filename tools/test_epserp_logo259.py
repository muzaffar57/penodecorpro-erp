#!/usr/bin/env python3
"""
test_epserp_logo259.py — kech191 (zip 259): o'z logotipi yo'q korxona menyusida — epserp logotipi; hujjatlarda — FAQAT o'z nomi.

NIMA UCHUN KERAK (egasi so'rovi 05.11 16:27: «demo bersak, demo olgan korxonada bizning epserp logolar turadigan qilishimiz kerak,
korxona keyin o'zinikiga almashtirib oladi»; QARORI tugmali savolga: «faqat dastur ichida — yuk xatlarida bizning nom va logo ketib
qolmasligi kerak»). O'LCHANGAN (asl kod — zip 258): logotipsiz korxona menyusida — doira ichida nomning birinchi harfi + nom + «ERP»
(epserp logotipi YO'Q); hujjatlarda — faqat nom (to'g'ri, saqlanishi SHART); Sozlamalarda logotip yo'qligi haqida hech narsa yozilmagan.
TALAB (har biri o'lchanadi):
  S  statik: base.html — logotipsiz tarmoqda oq taglikda `static/epserp_logo.svg` (`.s-logo-epserp`) + korxona nomi; eski «harf + nom +
     ERP» bloki yo'q; style.css qoidalari; Sozlamalarda izoh (`#co-logo-yoq`) va uni ko'rsatuvchi / yashiruvchi kod; hujjat kodi
     (company_brand, pdf_service, delivery_pdf, finance_pdf) epserp logotipiga HAVOLA QILMAYDI
  M  HTTP menyu (/orders): B (logotipsiz) — epserp logotipi + o'z nomi, boshqa rasm yo'q; A (logotip yuklagan) — o'z logotipi, epserp
     yo'q; 1 (platforma egasi) — `logo_menyu.webp`, epserp yo'q; C (logotip yo'li bor, fayli diskda yo'q) — epserp + nom (singan rasm
     emas); A logotipi fayli o'chsa — epserp; logotip SVG — 200, `image/svg+xml`; nomdagi HTML — matn bo'lib chiqadi
  B  `company_brand.get_brand`: B — logo bo'sh, nom — o'zi; hujjatlar (9 PDF): B — 200, rasm YO'Q, «epserp» / PenoDecorPro matni yo'q,
     o'z nomi bor
  Z  Sozlamalar API: B — `logo_korinish` bo'sh (izoh ko'rinadi), A — o'z logotipi
  J  HAQIQIY Chromium: kompyuter (1440) va telefon (390, menyu ochilgan) — epserp logotipi yuklandi (naturalWidth > 0), oq taglik ichida,
     taglik menyudan chiqmaydi, nom logotip tagida; tungi rejimda taglik oq; 40 belgili nom — qatorga bo'linadi, gorizontal surilish yo'q;
     Sozlamalar — B da izoh ko'rinadi, logotip yuklangach yashiriladi va menyuda o'z logotipi chiqadi
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`; `PG_URL` bilan HAQIQIY PostgreSQL 16 (J — faqat SQLite / TF1 da).
Asl kodga (zip 258) qarshi QULAMAYDI — yiqiladi. Test o'zi yozgan logotip fayllarini oxirida o'chiradi.
ISHLATISH: python3 tools/test_epserp_logo259.py
"""
import os
import io
import re
import sys
import html
import time
import socket
import tempfile
import threading
import contextlib
from datetime import datetime, timedelta, timezone

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = f"logo259_test_{os.getpid()}"
_DB = os.path.join(tempfile.mkdtemp(prefix="logo259_"), "logo259_test.db")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
    import company_brand                           # noqa: E402
from sqlalchemy import text                        # noqa: E402
from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import UserRole, User, Project, Inventory, FinishedProduct, StockSource, ProductionStatus  # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from PIL import Image                              # noqa: E402
import pdfplumber                                  # noqa: E402
from pypdf import PdfReader                        # noqa: E402

for _n in ("_send_telegram", "_send_telegram_to", "_send_telegram_document", "_send_telegram_to_qoplamachi"):
    if hasattr(main, _n):
        setattr(main, _n, lambda *a, **k: False)
crud.PUL_TAKROR_SONIYA = 0

OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        good = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        good = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if good:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        try:
            d = detail() if callable(detail) else detail
        except Exception as e:             # noqa: BLE001
            d = f"{type(e).__name__}: {e}"
        print(f"  ✗ {label}   {str(d)[:700]}")


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


def fayl(nom):
    try:
        with open(os.path.join(ROOT, nom), encoding="utf-8") as f:
            return f.read()
    except Exception:                      # noqa: BLE001
        return ""


def pdf_rasmlari(b):
    try:
        return [im.image.size for p in PdfReader(io.BytesIO(b)).pages for im in p.images]
    except Exception:                      # noqa: BLE001
        return None


def pdf_matni(b):
    try:
        with pdfplumber.open(io.BytesIO(b)) as p:
            return "\n".join((pg.extract_text() or "") for pg in p.pages)
    except Exception:                      # noqa: BLE001
        return ""


def rasm_bayt(w, h, rang=(20, 120, 90)):
    im = Image.new("RGB", (w, h), rang)
    for x in range(0, w, 5):
        im.putpixel((x, (x * 7) % h), (250, 250, 20))
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


UPL = os.path.join(ROOT, "static", "uploads", "logos")
EPSERP = "/static/epserp_logo.svg"

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Statik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
BASE = fayl("templates/base.html")
ST = fayl("static/style.css")
LOGS = fayl("templates/logs.html")
_blok = BASE[BASE.find('<div class="s-logo">'):BASE.find('<div class="s-user">')]
check("S1 base.html: logotipsiz tarmoq — oq taglikda epserp logotipi (`.s-logo-epserp`, `/static/epserp_logo.svg?v=`), tagida korxona nomi",
      '<div class="s-logo-epserp-blok">' in _blok
      and '<img class="s-logo-epserp" src="/static/epserp_logo.svg?v={{ static_version }}" alt="epserp" width="150" height="38">' in _blok
      and '{% if _kn %}<div class="logo-name">{{ _kn }}</div>{% endif %}' in _blok, _blok[-900:])
check("S2 base.html: eski «harf + nom + ERP» bloki (42 px doira, `logo-ver`) — YO'Q; o'z logotipi tarmog'i o'zgarmagan",
      "border-radius:50%" not in _blok and 'class="logo-ver"' not in _blok and "[0]|upper" not in _blok
      and '<img class="s-logo-oddiy" src="{{ _lm.src }}"' in _blok and 'class="s-logo-kesim"' in _blok, _blok[:400])
check("S3 style.css: `.s-logo-epserp` (150 px, nisbati saqlanadi), nom — markazda, uzun nom qatorga bo'linadi",
      ".s-logo-epserp {\n  display: block;\n  width: 150px;\n  max-width: 100%;\n  height: auto;\n}" in ST
      and ".s-logo-epserp-blok .logo-name {" in ST and "overflow-wrap: anywhere;" in ST.split(".s-logo-epserp-blok .logo-name {")[-1][:200])
check("S4 Sozlamalar: izoh `#co-logo-yoq` (yashirin, «epserp logotipi turibdi», «hujjatlarda … faqat korxona nomingiz»); `loadCompany` — "
      "o'z logotipi bo'lsa yashiradi, yo'q bo'lsa ko'rsatadi",
      'id="co-logo-yoq" style="display:none;' in LOGS and "dastur menyusida hozir epserp logotipi turibdi" in LOGS
      and "faqat korxona nomingiz" in LOGS and "if (_yoq259) _yoq259.style.display = 'none';" in LOGS
      and "if (_yoq259) _yoq259.style.display = 'block';" in LOGS)
_HUJ = {f: fayl(f) for f in ("company_brand.py", "pdf_service.py", "delivery_pdf.py", "finance_pdf.py")}
check("S5 hujjat kodi (company_brand, pdf_service, delivery_pdf, finance_pdf) epserp logotipiga havola qilmaydi",
      all(_HUJ.values()) and not any(re.search(r"epserp_logo|epserp_belgi", s) for s in _HUJ.values()),
      {k: bool(v) for k, v in _HUJ.items()})
_svg = fayl("static/epserp_logo.svg")
check("S6 epserp_logo.svg — 475 × 120 (nisbat ≈ 3,96 — menyuda 150 × 38)", _svg.startswith("<svg") and 'viewBox="0 0 475.3 120"' in _svg)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik: korxona 1 (platforma egasi — platforma logotipi), platforma admini; A (logotip yuklaydi), B (logotipsiz),
# C (logo_path bor — fayli yo'q), U (40 belgili nom, HTML belgilari bilan) — platforma paneli API si bilan
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
PLAT_LOGO = getattr(main, "PLATFORMA_LOGOTIPI", "static/logo_transparent.png")
s = SessionLocal()
c1 = s.query(Company).filter(Company.id == 1).first()
if c1 is None:
    c1 = Company(id=1, name="PenodecorPro")
    s.add(c1)
    s.flush()
c1.logo_path = PLAT_LOGO
c1.slogan, c1.address, c1.phone = "Fasad bezaklari", "Andijon", "+998 97 999 57 57"
s.commit()
_X = 200_000 + os.getpid() * 5            # logotip fayli `company_<id>` — parallel yurishlar bir-birinikini almashtirmasin
s.add(Company(id=_X, name=f"L259 bo'sh {_X}"))
s.commit()
if PG_URL:
    s.execute(text("SELECT setval(pg_get_serial_sequence('companies', 'id'), :x)"), {"x": _X})
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "l259_plat", "Parol123!", UserRole.ADMIN, "Platforma", company_id=1)
_u = s.query(User).filter(User.username == "l259_plat").first()
_u.is_platform_admin = True
s.commit()
s.close()


def kirish(login, parol):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = req(c, "post", "/login", data={"username": login, "password": parol}, follow_redirects=False)
    return c if getattr(r, "status_code", 599) == 302 else None


UZUN = "Andijon <b>Fasad</b> Penoplast Dekor Zavodi"          # 40+ belgi, HTML — matn bo'lib chiqishi kerak
PL = kirish("l259_plat", "Parol123!")
KX = {"1": {"nom": "PenodecorPro", "id": 1, "C": PL}}
for _k, _nom, _login in (("A", "Namuna Penoplast", "l259_namuna"), ("B", "Sinov Dekor", "l259_sinov"),
                         ("C", "Yo'qolgan Logo", "l259_yoq"), ("U", UZUN, "l259_uzun")):
    _r = req(PL, "post", "/api/platform/companies", data={"name": _nom, "admin_username": _login, "admin_full_name": _nom[:20] + " admin"}) \
        if PL else _Xato(Exception("platforma admini kirmadi"))
    _j = js(_r) or {}
    KX[_k] = {"nom": _nom, "id": (_j.get("company") or {}).get("id"), "login": _login, "parol": (_j.get("admin") or {}).get("password") or "",
              "C": kirish(_login, (_j.get("admin") or {}).get("password") or "")}
check("0.1 fikstura: platforma admini; A, B, C, U korxonalari platforma paneli API si bilan yaratildi, adminlari kirdi",
      PL is not None and all(KX[k]["id"] and KX[k]["C"] is not None for k in ("A", "B", "C", "U")),
      {k: (v["id"], v["C"] is not None) for k, v in KX.items()})
if not all(KX[k]["C"] is not None for k in ("1", "A", "B", "C", "U")):
    print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL + 1}   jami = {OK + FAIL + 1}")
    sys.exit(1)
CA, CB = KX["A"]["C"], KX["B"]["C"]
_rl = req(CA, "post", "/api/settings/company/logo", files={"file": ("namuna.png", rasm_bayt(600, 300), "image/png")})
LOGO_A_YOL = os.path.join(ROOT, (js(_rl) or {}).get("logo_path") or "x")
check("0.2 A korxonasi logotipi yuklandi", _rl.status_code == 200 and os.path.exists(LOGO_A_YOL), (_rl.status_code, _rl.text[:200]))
s = SessionLocal()
s.query(Company).filter(Company.id == KX["C"]["id"]).update({"logo_path": f"static/uploads/logos/company_{KX['C']['id']}_yoq.png"},
                                                             synchronize_session=False)
s.commit()
s.close()

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("M. Menyu (HTTP)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════


def menyu(c, url="/orders"):
    h = getattr(req(c, "get", url), "text", "")
    b = h[h.find('<div class="s-logo">'):h.find('<div class="s-user">')] if '<div class="s-logo">' in h else ""
    return {"epserp": re.findall(r'class="s-logo-epserp" src="([^"]+)"', b),
            "oz": re.findall(r'class="s-logo-(?:rasm|oddiy)" src="([^"]+)"', b),
            "nom": (re.search(r'<div class="logo-name">(.*?)</div>', b, re.S) or [None, None])[1],
            "plita": b.count('class="s-logo-plita"'), "img": len(re.findall(r"<img\b", b)), "blok": b}


_mb, _ma, _m1, _mc, _mu = menyu(CB), menyu(CA), menyu(PL), menyu(KX["C"]["C"]), menyu(KX["U"]["C"])
check("M1 B (logotipsiz): oq taglikda epserp logotipi (`/static/epserp_logo.svg?v=…`), tagida o'z nomi «Sinov Dekor»; boshqa rasm yo'q",
      len(_mb["epserp"]) == 1 and _mb["epserp"][0].startswith(EPSERP + "?v=") and _mb["oz"] == [] and _mb["img"] == 1 and _mb["plita"] == 1
      and _mb["nom"] == "Sinov Dekor", {k: v for k, v in _mb.items() if k != "blok"})
check("M2 A (logotip yuklagan): o'z logotipi (`company_<A>`), epserp logotipi yo'q, nom matni yo'q",
      _ma["oz"] and all(f"company_{KX['A']['id']}." in x for x in _ma["oz"]) and _ma["epserp"] == [] and _ma["nom"] is None,
      {k: v for k, v in _ma.items() if k != "blok"})
check("M3 korxona 1 (platforma egasi): `logo_menyu.webp`, epserp logotipi yo'q",
      _m1["oz"] == ["/static/logo_menyu.webp"] and _m1["epserp"] == [], {k: v for k, v in _m1.items() if k != "blok"})
check("M4 C (logotip yo'li bor — fayli diskda yo'q): epserp logotipi + o'z nomi (singan rasm emas)",
      len(_mc["epserp"]) == 1 and _mc["oz"] == [] and html.unescape(_mc["nom"] or "") == "Yo'qolgan Logo",
      {k: v for k, v in _mc.items() if k != "blok"})
check("M5 U (nomida HTML belgilari): nom MATN bo'lib chiqadi (`&lt;b&gt;`), menyuda `<b>` tegi yo'q; epserp logotipi bor",
      len(_mu["epserp"]) == 1 and _mu["nom"] == "Andijon &lt;b&gt;Fasad&lt;/b&gt; Penoplast Dekor Zavodi" and "<b>" not in _mu["blok"],
      {k: v for k, v in _mu.items() if k != "blok"})
_svgr = req(CB, "get", EPSERP)
check("M6 epserp logotipi fayli — 200, `image/svg+xml`", _svgr.status_code == 200
      and (_svgr.headers.get("content-type") or "").startswith("image/svg+xml") and _svgr.content.startswith(b"<svg"),
      (_svgr.status_code, _svgr.headers.get("content-type")))
_sah = {u: menyu(CB, u) for u in ("/", "/finance", "/sozlamalar", "/kpi")}
check("M7 B ning boshqa sahifalarida ham (bosh, moliya, sozlamalar, KPI) — epserp logotipi + nom",
      all(len(v["epserp"]) == 1 and v["nom"] == "Sinov Dekor" for v in _sah.values()),
      {u: (v["epserp"], v["nom"]) for u, v in _sah.items()})

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. Hujjatlar (9 PDF) — B da epserp YO'Q")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
_gb = company_brand.get_brand(s, KX["B"]["id"])
s.close()
check("B1 `get_brand` (B): logotip bo'sh, nom — «Sinov Dekor» (epserp / platforma logotipi BERILMAYDI)",
      not _gb.get("logo") and _gb.get("name") == "Sinov Dekor", _gb)

s = SessionLocal()
for _k in ("B",):
    _cid = KX[_k]["id"]
    _p = Project(company_id=_cid, client_name=f"{_k} mijoz", client_phone="+998 91 000 00 00", project_name=f"{_k} loyiha",
                 total_budget=0, total_paid=0)
    _pe = Inventory(company_id=_cid, item_name=f"{_k} Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                    volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
    _tm = FinishedProduct(company_id=_cid, name=f"{_k} TM", quantity=50, unit="metr", source=StockSource.PRODUCED,
                          production_status=ProductionStatus.READY, unit_price=10_000, cost_price=5_000)
    s.add_all([_p, _pe, _tm])
    s.commit()
    KX[_k].update({"PRJ": _p.id, "PENO": _pe.id, "TM": _tm.id})
s.close()
_tk = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=5)


def hujjatlar(k):
    """Korxona k da: buyurtma, yuk xati, TM sotuvi (yakka / savat), xarajat, taklif — 9 hujjat manzili."""
    d = KX[k]
    c = d["C"]
    tana = {"project_id": d["PRJ"], "order_type": "product",
            "items": [{"name": f"{k} karniz", "category": "profil", "width": 20, "thickness": 10, "length": 10, "quantity": 1,
                       "unit_price": 1_000_000, "is_coated": False, "penoplast_id": d["PENO"]}]}
    oid = (js(req(c, "post", "/api/orders", params={"confirm_shortage": "true"}, json=tana)) or {}).get("id")
    s_ = SessionLocal()
    try:
        its = [x[0] for x in s_.execute(text("SELECT id FROM order_items WHERE order_id = :o ORDER BY id"), {"o": oid or 0}).fetchall()]
    finally:
        s_.close()
    it = its[0] if its else None
    did = (js(req(c, "post", "/api/deliveries", json={"order_id": oid, "items": [{"order_item_id": it, "quantity": 4}],
                                                      "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd",
                                                      "payment_amount": 0})) or {}).get("delivery_id")
    sid = (js(req(c, "post", "/api/finished/sell", json={"finished_product_id": d["TM"], "quantity": 1, "unit_price": 10_000,
                                                         "buyer_name": "X"})) or {}).get("sale_id")
    gid = (js(req(c, "post", "/api/finished/sell-batch", json={"items": [{"finished_product_id": d["TM"], "quantity": 1,
                                                                          "unit_price": 10_000}], "buyer_name": "Y"})) or {}).get("sale_group_id")
    req(c, "post", "/api/finance/transactions", json={"category": "boshqa", "amount": 5_000.0, "notes": "x"})
    tid = ((js(req(c, "post", "/api/takliflar", json={"mijoz": "T mijoz", "telefon": "+998 90 111 22 33",
                                                      "buyurtma": {"order_type": "product", "items": tana["items"][:1]}})) or {})
           .get("taklif") or {}).get("id")
    d["URL"] = {"buyurtma_hisobi": (f"/api/orders/{oid}/pdf", {}),
                "taklif": (f"/api/takliflar/{tid}/pdf", {}),
                "yuk_xati": (f"/api/deliveries/{did}/pdf", {}),
                "hisob_kitob": (f"/api/orders/{oid}/summary-pdf", {}),
                "sotuv_cheki": (f"/api/finished/sales/{sid}/pdf", {}),
                "sotuv_savat": (f"/api/finished/sales/batch/{gid}/pdf", {}),
                "yuk_jamlanma": (f"/api/projects/{d['PRJ']}/yuk-xatlari/jamlama-pdf", {}),
                "moliya_oylik": ("/api/finance/report-pdf", {"year": _tk.year, "month": _tk.month}),
                "foyda_ulushi": ("/api/finance/split-profit-pdf", {"year": _tk.year, "month": _tk.month})}
    return all((oid, it, did, sid, gid, tid))


_hb = hujjatlar("B")
check("B2 fikstura: B korxonasida buyurtma, yuk xati, sotuvlar, xarajat, taklif yaratildi", _hb, KX["B"].get("URL"))
_P = {}
for _n, (_url, _par) in (KX["B"].get("URL") or {}).items():
    _r = req(CB, "get", _url, params=_par)
    _P[_n] = _r.content if _r.status_code == 200 and _r.content[:4] == b"%PDF" else None
check("B3 B: 9 hujjat — 200 (PDF)", len(_P) == 9 and all(_P.values()), {n: b is not None for n, b in _P.items()})
_hbx = {n: (pdf_rasmlari(b), pdf_matni(b)) for n, b in _P.items() if b}
check("B4 B: 9 hujjatda rasm YO'Q (epserp ham, platforma logotipi ham), «epserp» / «PenoDecor» matni yo'q, o'z nomi «Sinov Dekor» bor",
      len(_hbx) == 9 and all(r == [] and not re.search(r"epserp|penodecor", m, re.I) and "SINOV DEKOR" in m.upper()
                             for r, m in _hbx.values()),
      {n: (r, bool(re.search(r"epserp|penodecor", m, re.I)), "SINOV DEKOR" in m.upper()) for n, (r, m) in _hbx.items()})

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Z. Sozlamalar API")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_zb, _za = js(req(CB, "get", "/api/settings/company")) or {}, js(req(CA, "get", "/api/settings/company")) or {}
_hz = getattr(req(CB, "get", "/sozlamalar"), "text", "")
check("Z1 B: `logo_korinish` bo'sh (Sozlamalarda izoh ko'rinadi); A: o'z logotipi; /sozlamalar sahifasida izoh bloki bor",
      "logo_korinish" in _zb and not _zb.get("logo_korinish") and f"company_{KX['A']['id']}." in (_za.get("logo_korinish") or "")
      and 'id="co-logo-yoq"' in _hz, (_zb.get("logo_korinish"), _za.get("logo_korinish")))
try:
    os.remove(LOGO_A_YOL)
except OSError:
    pass
_ma2 = menyu(CA)
check("Z2 A logotipi fayli diskdan o'chsa — menyuda epserp logotipi + o'z nomi (singan rasm emas)",
      len(_ma2["epserp"]) == 1 and _ma2["oz"] == [] and _ma2["nom"] == "Namuna Penoplast", {k: v for k, v in _ma2.items() if k != "blok"})

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J. HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    print("  (J — PG da o'tkaziladi)")
else:
    import uvicorn
    from playwright.sync_api import sync_playwright
    _s = socket.socket()
    _s.bind(("127.0.0.1", 0))
    PORT = _s.getsockname()[1]
    _s.close()
    _srv = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=PORT, log_level="error"))
    threading.Thread(target=_srv.run, daemon=True).start()
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", PORT), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    BASEURL = f"http://127.0.0.1:{PORT}"
    LOGO_JS = """() => { const b = document.querySelector('.s-logo'); const p = b ? b.querySelector('.s-logo-plita') : null;
        const i = b ? b.querySelector('img.s-logo-epserp') : null; const n = b ? b.querySelector('.logo-name') : null;
        const sb = document.querySelector('.sidebar'); const r = e => e ? e.getBoundingClientRect() : null;
        const ri = r(i), rp = r(p), rn = r(n), rs = r(sb);
        return {bor: !!i, nw: i ? i.naturalWidth : 0, iw: ri ? ri.width : 0, ih: ri ? ri.height : 0,
                ichida: !!(ri && rp && ri.left >= rp.left - 0.5 && ri.right <= rp.right + 0.5 && ri.top >= rp.top - 0.5 && ri.bottom <= rp.bottom + 0.5),
                plita_menyuda: !!(rp && rs && rp.left >= rs.left - 0.5 && rp.right <= rs.right + 0.5),
                nom: n ? n.textContent.trim() : null, nom_tagida: !!(rn && rp && rn.top >= rp.bottom - 0.5),
                nom_ichida: !!(rn && rs && rn.left >= rs.left - 0.5 && rn.right <= rs.right + 0.5), nom_qator: rn ? Math.round(rn.height) : 0,
                fon: p ? getComputedStyle(p).backgroundColor : null,
                surilish: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1}; }"""
    J = {}
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch()

            def kontekst(login, parol, w, h):
                ctx = br.new_context(viewport={"width": w, "height": h})
                pg = ctx.new_page()
                pg.goto(BASEURL + "/login", wait_until="networkidle")
                pg.fill("input[name=username]", login)
                pg.fill("input[name=password]", parol)
                pg.click("button[type=submit]")
                pg.wait_for_load_state("networkidle")
                return ctx, pg

            for _k, _w, _h in (("B", 390, 844), ("U", 1440, 900), ("U", 390, 844), ("B", 1440, 900)):   # B 1440 — oxirida (logotip yuklaydi)
                ctx, pg = kontekst(KX[_k]["login"], KX[_k]["parol"], _w, _h)
                pg.goto(BASEURL + "/orders", wait_until="networkidle")
                if _w < 800:
                    pg.click(".mobile-menu-btn")                                   # telefonda menyu — «☰» tugmasi
                    pg.wait_for_function("() => document.querySelector('.sidebar').classList.contains('sidebar-open')", timeout=5000)
                    pg.wait_for_timeout(500)
                J[(_k, _w)] = pg.evaluate(LOGO_JS)
                if os.environ.get("L259_RASM"):                                  # ixtiyoriy: ko'z bilan tekshirish uchun rasm
                    pg.screenshot(path=os.path.join(os.environ["L259_RASM"], f"menyu_{_k}_{_w}.png"))
                if (_k, _w) == ("B", 1440):
                    pg.evaluate("() => document.documentElement.setAttribute('data-theme', 'dark')")
                    J["qorongi"] = pg.evaluate(LOGO_JS)
                    if os.environ.get("L259_RASM"):
                        pg.screenshot(path=os.path.join(os.environ["L259_RASM"], "menyu_B_qorongi.png"))
                    pg.evaluate("() => document.documentElement.setAttribute('data-theme', 'light')")
                    pg.goto(BASEURL + "/sozlamalar", wait_until="networkidle")
                    pg.evaluate("() => { const d = document.querySelector('details[data-sht=\"soz-nom\"]'); if (d) d.open = true; }")
                    pg.wait_for_function("() => document.getElementById('co-name') && document.getElementById('co-name').value !== ''",
                                         timeout=15000)
                    if os.environ.get("L259_RASM"):
                        pg.locator('details[data-sht="soz-nom"]').screenshot(path=os.path.join(os.environ["L259_RASM"], "sozlama_B.png"))
                    J["izoh_oldin"] = pg.evaluate("() => { const e = document.getElementById('co-logo-yoq'); "
                                                  "return e ? {k: getComputedStyle(e).display, t: e.textContent.trim()} : null; }")
                    pg.set_input_files("#co-logo-file", files=[{"name": "logo.png", "mimeType": "image/png", "buffer": rasm_bayt(400, 200)}])
                    pg.click("#co-logo-btn")
                    pg.wait_for_function("() => (document.getElementById('co-logo-status').textContent || '').includes('Yuklandi')", timeout=15000)
                    pg.wait_for_function("() => getComputedStyle(document.getElementById('co-logo-preview')).display !== 'none'", timeout=15000)
                    J["izoh_keyin"] = pg.evaluate("() => getComputedStyle(document.getElementById('co-logo-yoq')).display")
                    pg.goto(BASEURL + "/orders", wait_until="networkidle")
                    J["yuklangach"] = pg.evaluate("() => { const b = document.querySelector('.s-logo'); return {"
                                                  "epserp: b.querySelectorAll('img.s-logo-epserp').length, "
                                                  "oz: Array.from(b.querySelectorAll('img.s-logo-rasm, img.s-logo-oddiy')).map(i => i.getAttribute('src')), "
                                                  "nw: Array.from(b.querySelectorAll('img')).map(i => i.naturalWidth)}; }")
                ctx.close()
            br.close()
    except Exception as e:                 # noqa: BLE001
        J["xato"] = f"{type(e).__name__}: {e}"

    def _yaxshi(v, uzun=False):
        return (v and v["bor"] and v["nw"] > 0 and 140 <= v["iw"] <= 151 and 35 <= v["ih"] <= 39.5 and v["ichida"] and v["plita_menyuda"]
                and v["nom_tagida"] and v["nom_ichida"] and not v["surilish"] and (v["nom_qator"] >= 30 if uzun else True))

    check("J1 kompyuter (1440): epserp logotipi yuklandi, ~150 × 38, oq taglik ichida, taglik menyuda; nom — logotip tagida, menyudan "
          "chiqmaydi; oq taglik (rgb 255)", _yaxshi(J.get(("B", 1440))) and J[("B", 1440)]["nom"] == "Sinov Dekor"
          and J[("B", 1440)]["fon"] == "rgb(255, 255, 255)", (J.get("xato"), J.get(("B", 1440))))
    check("J2 telefon (390, menyu ochilgan): xuddi shunday, sahifa gorizontal surilmaydi", _yaxshi(J.get(("B", 390))), J.get(("B", 390)))
    check("J3 tungi rejim: taglik OQ qoladi (epserp yozuvi to'q — ko'rinadi)", J.get("qorongi") and J["qorongi"]["fon"] == "rgb(255, 255, 255)"
          and J["qorongi"]["bor"], J.get("qorongi"))
    check("J4 uzun nom (40+ belgi, HTML belgilari): kompyuter va telefonda — qatorga bo'linadi (≥ 2 qator), menyudan chiqmaydi, matn bo'lib "
          "chiqadi", _yaxshi(J.get(("U", 1440)), True) and _yaxshi(J.get(("U", 390)), True)
          and J[("U", 1440)]["nom"] == "Andijon <b>Fasad</b> Penoplast Dekor Zavodi", (J.get(("U", 1440)), J.get(("U", 390))))
    check("J5 Sozlamalar (B): izoh KO'RINADI («epserp logotipi turibdi»); logotip yuklangach — yashiriladi; menyuda endi o'z logotipi "
          "(yuklandi), epserp yo'q",
          J.get("izoh_oldin") and J["izoh_oldin"]["k"] == "block" and "epserp logotipi turibdi" in J["izoh_oldin"]["t"]
          and J.get("izoh_keyin") == "none" and J.get("yuklangach") and J["yuklangach"]["epserp"] == 0
          and len(J["yuklangach"]["oz"]) == 1 and f"company_{KX['B']['id']}." in J["yuklangach"]["oz"][0]
          and all(x > 0 for x in J["yuklangach"]["nw"]), (J.get("izoh_oldin"), J.get("izoh_keyin"), J.get("yuklangach")))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tozalash: test yozgan logotip fayllari
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if os.path.isdir(UPL):
    for _f in os.listdir(UPL):
        if any(_f.startswith(f"company_{KX[k]['id']}.") or _f.startswith(f"company_{KX[k]['id']}_") for k in ("A", "B", "C", "U")):
            try:
                os.remove(os.path.join(UPL, _f))
            except OSError:
                pass
if PG_URL:
    try:
        from database import engine as _eng
        _eng.dispose()
        _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
        with _adm.connect() as _c:
            _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _adm.dispose()
    except Exception:                      # noqa: BLE001
        pass

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for _f in FAILED:
        print("  " + _f)
sys.exit(1 if FAIL else 0)
