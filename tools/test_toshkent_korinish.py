#!/usr/bin/env python3
"""
test_toshkent_korinish.py — kech106, 9 + 50-band B qismi darvozasi (server KO'RINISHI). FOYDALANUVCHI QARORI (kech105,
2026-09-28): "Toshkent vaqti bo'yicha" — hisobot chegaralari (A qism, zip 100 — `tools/test_toshkent_vaqt.py`) bilan
birga ekran, hujjat va xabardagi sana-vaqt ham TOSHKENT devor soatida (UTC+5).

NIMA UCHUN (asl kod staging `e627685` da O'LCHANGAN — `work/probe106.py`; TZ=UTC — Railway kabi; SQLite = PG)
---------------------------------------------------------------------------------------------------------------
Baza vaqtni UTC da saqlaydi. Ko'rinishda esa: Telegram xabarlari (qoplama, yuk xati, «Tayyor», mijozga, ombor hisoboti)
`datetime.now()` bilan — Railway jarayoni UTC da, ya'ni "⏰ 30.09.2026 20:59" (Toshkent 01.10 01:59); nakladnoy PDF
"Sana" va "Chiqarilgan" — xuddi shunday, "Yaratilgan sana" — bazadagi UTC sanasi; hisob-kitob varaqasi PDF "Davr" va
yuk qatorlari — UTC sanasi (u yerdagi `tzinfo` tekshiruvi hech narsa qilmas edi); /users, /logs (kirishlar, faoliyat),
/orders, /projects, /recipes, /returns, /trash sahifalari, hodim to'lov tarixi, mahkamlangan buyurtmalar, to'lov
o'chirilgandagi jurnal matni, zaxira fayl nomi va kunlik zaxira sanasi — UTC. Toshkent 00:00–05:00 dagi amal "KECHA"
bo'lib ko'rinardi. (Yuk xati / TM sotuvi / moliya PDF — allaqachon Toshkentda, alohida `UZB_TZ` formulasi bilan edi.)

BO'LIMLAR ("hozir" — UTC 30.09.2026 20:59 = Toshkent 01.10.2026 01:59; yozuvlar — UTC 30.09 20:30 = Toshkent 01.10 01:30)
  A — Telegram: qoplama xabari, yuk xati (admin, mijoz / usta — PDF izohi va matnli zaxira), «Tayyor» (admin, mijoz),
      ombor hisoboti, kunlik zaxira (fayl nomi va sana)
  B — PDF: nakladnoy (Sana, Yaratilgan sana, Chiqarilgan), yuk xati, hisob-kitob varaqasi (Davr, yuk qatori, Sana),
      TM sotuvi (yakka / guruh), moliya hisoboti (Yaratildi)
  C — sahifalar (Jinja): /users, /logs (kirish, faoliyat; XATO JURNALI — allaqachon Toshkent, qayta siljimaydi), /orders,
      /projects, /recipes, /returns, /trash, /debts (muddat — kalendar kuni o'zgarmaydi)
  D — API matnlari: hodim to'lov tarixi, mahkamlangan buyurtmalar, to'lov audit matni, zaxira fayl nomi
  E — yordamchilar: `database.tashkent_vaqt` (naive / None / mintaqali / sana / xato tur), Jinja `|toshkent` filtri
  F — statik (AST): server kodida `datetime.now()` (mintaqasiz) va `date.today()` yo'q; bazadagi vaqt ustunini
      to'g'ridan-to'g'ri `.strftime(` qilish yo'q; shablonlarda ham (istisno — ErrorLog `e.created_at`)

"HOZIR": jarayon mintaqasi TZ=UTC (Railway kabi); modullardagi `datetime` sinfi `_Soat` bilan almashtiriladi.
PDF matni — kutubxonasiz (ASCII85 + Flate oqimlari, `( … ) Tj`; TTF shrift — ToUnicode xaritasi orqali, kech106 K106-1).

REJIMLAR: SQLite; `PG_URL` berilsa — har ishga YANGI PG bazasi.
    python3 tools/test_toshkent_korinish.py
    PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_toshkent_korinish.py
"""
import os
import re
import ast
import sys
import zlib
import time
import base64
import tempfile
from datetime import datetime, date, timezone, timedelta

os.environ["TZ"] = "UTC"
try:
    time.tzset()
except AttributeError:                     # Windows — tzset yo'q (test Linux da yuradi)
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "toshkent_korinish_test"
_DB = os.path.join(tempfile.gettempdir(), "toshkent_korinish_test.db")
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
os.environ.pop("TENANT_FILTER", None)
os.environ.pop("TELEGRAM_BOT_TOKEN", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth, services, crud, database          # noqa: E402
    import pdf_service, delivery_pdf, finance_pdf  # noqa: E402
from sqlalchemy import text                        # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Project, Inventory, Master, Recipe, ActivityLog, ErrorLog, FinishedProduct,  # noqa: E402
                    StockSource, ProductionStatus)
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
        print(f"  ✗ {label}   {str(detail)[:400]}")


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


def xavfsiz(fn, *a, **k):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return fn(*a, **k)
    except Exception as e:                 # noqa: BLE001
        return ("XATO", f"{type(e).__name__}: {str(e)[:200]}")


HOZIR = datetime(2026, 9, 30, 20, 59)          # UTC → Toshkent 01.10.2026 01:59
LAHZA = datetime(2026, 9, 30, 20, 30)          # UTC → Toshkent 01.10.2026 01:30
T_HOZIR = "01.10.2026 01:59"
T_LAHZA = "01.10.2026 01:30"
T_SANA = "01.10.2026"
UTC_SANA = "30.09.2026"                        # asl (UTC) ko'rinish — BO'LMASLIGI kerak
# kech116: sahifa tekshiruvlari (C1 / C2 / C8) UTC sanasini butun sahifada emas, ANIQ asl ko'rinish namunalarida qidiradi —
# sahifada HAQIQIY joriy vaqt ham bor (sarlavha, «Joriy siz» — soat almashtirilmagan so'rovlar): haqiqiy Toshkent sanasi
# 30.09.2026 bo'lgan kuni (kech115 etaloni) butun sahifa qidiruvi asl kodda ham yiqilardi (bizning o'zgarish emas).
# Asl xato ko'rinishi — fikstura lahzalarining UTC matni va UTC sanali katak — shu namunalar bilan AYNAN ushlanadi.
UTC_NAMUNALAR = ("30.09.2026 20:30", "30.09.2026 20:59", ">30.09.2026</td>", ">30.09.2026<", "30.09.2026</span>")


def utc_korinishi_yoq(matn):
    return not any(x in (matn or "") for x in UTC_NAMUNALAR)


def fikstura_qatori(matn, login):
    """/users jadvalida FIKSTURA foydalanuvchisining qatori (`<tr id="urow-…">` … `</tr>`) — standart admin (haqiqiy
    joriy vaqtda yaratilgan) qatori tekshiruvga kirmaydi."""
    for m in re.finditer(r'<tr id="urow-\d+">(.*?)</tr>', matn or "", re.S):
        if f">{login}</span>" in m.group(1):
            return m.group(1)
    return ""
MODULLAR = (database, main, crud, services, pdf_service, delivery_pdf, finance_pdf)


class _Soat:
    """"Hozir" — `datetime.utcnow()` va `datetime.now()` (jarayon TZ=UTC; mintaqa berilsa — o'sha mintaqaga)
    `HOZIR` ni qaytaradi. `datetime` ni import qilgan HAR modulda almashtiriladi (asl kod — `datetime.now()`)."""

    def __init__(self, utc):
        self.utc = utc

    def __enter__(self):
        utc = self.utc

        class _D(datetime):
            @classmethod
            def utcnow(cls):
                return utc

            @classmethod
            def now(cls, tz=None):
                if tz is None:
                    return utc
                return utc.replace(tzinfo=timezone.utc).astimezone(tz)
        self._asl = {}
        for m in MODULLAR:
            if getattr(m, "datetime", None) is datetime:
                self._asl[m] = m.datetime
                m.datetime = _D
        return self

    def __exit__(self, *a):
        for m, v in self._asl.items():
            m.datetime = v


def _oqim_och(hdr, raw):
    """Oqim baytlari (`stream` qatoridan keyin): `/Length` bo'yicha kesiladi — Flate ikkilik ma'lumoti bo'shliq /
    qator belgisi bilan tugashi mumkin (`strip()` uni buzardi — TTF ToUnicode oqimi)."""
    m = re.search(rb"/Length\s+(\d+)(?!\s+\d+\s+R)", hdr)
    raw = raw[:int(m.group(1))] if m else raw.strip()
    if b"ASCII85Decode" in hdr:
        raw = re.sub(rb"\s", b"", raw)
        if raw.startswith(b"<~"):
            raw = raw[2:]
        if raw.endswith(b"~>"):
            raw = raw[:-2]
        raw = base64.a85decode(raw)
    if b"FlateDecode" in hdr:
        raw = zlib.decompress(raw)
    return raw


def _shrift_xaritalari(b):
    """PDF shrift nomi (`/F1`, TTF qism-to'plami `/F1+0`) → ToUnicode xaritasi (TTF) yoki None (Type1 — WinAnsi)."""
    obyektlar = {int(n): tana for n, tana in re.findall(rb"(\d+) 0 obj\s*(.*?)\s*endobj", b, re.S)}
    xarita = {}
    for tana in obyektlar.values():
        nom = re.search(rb"/Name\s*/([^\s/>\[]+)", tana)
        if b"/Type /Font" not in tana or not nom:
            continue
        cmap = None
        tu = re.search(rb"/ToUnicode\s+(\d+)\s+0\s+R", tana)
        if tu and int(tu.group(1)) in obyektlar:
            hdr, _, qolgan = obyektlar[int(tu.group(1))].partition(b"stream")
            qolgan = qolgan[2:] if qolgan.startswith(b"\r\n") else qolgan[1:]
            try:
                cm = _oqim_och(hdr, qolgan)
            except Exception:              # noqa: BLE001
                cm = b""
            cmap = {}
            for blok in re.findall(rb"beginbfchar(.*?)endbfchar", cm, re.S):
                for k, v in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blok):
                    cmap[int(k, 16)] = bytes.fromhex(v.decode()).decode("utf-16-be")
        xarita[nom.group(1)] = cmap
    return xarita


# PDF kontent tokenlari (kech106): satr `( … )` — BUTUN token, shuning uchun uning ichidagi "ET" / "BT" ("YETKAZISH",
# "(BT)") `BT … ET` blokini uzmaydi (ilgari `re.finditer(rb"BT(.*?)ET", …)` blokni satr ichida uzib, qatorni tashlardi).
_PDF_TOKEN = re.compile(rb"%[^\r\n]*|\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>|\[|\]|/[^\s/\[\]()<>{}%]*|[^\s/\[\]()<>{}%]+", re.S)


def _bt_bloklar(data):
    """Kontent oqimidagi `BT … ET` bloklari — har biri tokenlar ro'yxati (satr tokeni qavslari bilan: `(…)`)."""
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


def pdf_matn(b):
    """reportlab PDF matni: `( … ) Tj` satrlari (oqimlar ASCII85 / Flate). Type1 (Helvetica) — latin-1 / WinAnsi;
    TTF qism-to'plami (kech106 K106-1 — Liberation Sans, `pdf_shrift.py`) — shriftning ToUnicode xaritasi orqali."""
    parts = []
    if not isinstance(b, (bytes, bytearray)):
        return ""
    xarita = _shrift_xaritalari(b)
    for m in re.finditer(rb"stream\r?\n", b):
        bosh = b.rfind(b"<<", 0, m.start())
        hdr = b[bosh:m.start()] if bosh >= 0 else b""
        oxir = b.find(b"endstream", m.end())
        if oxir < 0:
            continue
        try:
            raw = _oqim_och(hdr, b[m.end():oxir])
        except Exception:                  # noqa: BLE001
            continue
        for blok in _bt_bloklar(raw):
            cmap = None
            for j, tok in enumerate(blok):
                if tok == b"Tf" and j >= 2 and blok[j - 2].startswith(b"/"):
                    cmap = xarita.get(blok[j - 2][1:])
                    continue
                if not tok.startswith(b"("):
                    continue
                t = tok[1:-1]
                t = re.sub(rb"\\([0-7]{1,3})", lambda x: bytes([int(x.group(1), 8) & 255]), t)
                t = re.sub(rb"\\(.)", lambda x: {b"n": b"\n", b"r": b"\r", b"t": b"\t"}.get(x.group(1), x.group(1)), t)
                parts.append("".join(cmap.get(k, "\ufffd") for k in t) if cmap is not None else t.decode("latin-1"))
    return " ".join(parts)


def sanalar(matn):
    return sorted(set(re.findall(r"\d{2}\.\d{2}\.\d{4}(?:\s+\d{2}:\d{2})?", matn or "")))


def fayl(nom):
    try:
        return open(os.path.join(ROOT, nom), encoding="utf-8").read()
    except Exception:                      # noqa: BLE001
        return ""


# ── Telegram — yuborilmaydi, matn yoziladi ──────────────────────────────────────────────────────────────────
TG = []


def _yoz(tur):
    def f(*a, **k):
        matnlar = [x for x in a if isinstance(x, str)]
        if isinstance(k.get("caption"), str):
            matnlar.append(k["caption"])
        TG.append({"tur": tur, "matn": " | ".join(matnlar)})
        return False                       # hujjat "yuborilmadi" — matnli zaxira yo'li ham sinaladi
    return f


for _n in ("_send_telegram", "_send_telegram_to", "_send_telegram_document", "_send_telegram_to_qoplamachi"):
    setattr(main, _n, _yoz(_n))

# ── fikstura ────────────────────────────────────────────────────────────────────────────────────────────────
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "tk_admin", "Parol123!", UserRole.ADMIN, "TK admin", company_id=1)
PRJ = Project(company_id=1, client_name="TK Mijoz", project_name="TK loyiha", total_budget=0, total_paid=0,
              notes="tg_id=5550001", deadline=datetime(2026, 10, 5))
PENO = Inventory(company_id=1, item_name="TK Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
USTA = Master(company_id=1, name="TK Usta", phone="+998900001071", kpi_percent=10, telegram_id="5550002")
TM = FinishedProduct(company_id=1, name="TK TM", quantity=50, unit="metr", source=StockSource.PRODUCED,
                     production_status=ProductionStatus.READY, unit_price=10_000, cost_price=5_000)
s.add_all([PRJ, PENO, USTA, TM])
s.commit()
PRJ_ID, PENO_ID, USTA_ID, TM_ID = PRJ.id, PENO.id, USTA.id, TM.id
s.execute(text("UPDATE users SET is_platform_admin = :t WHERE username = 'tk_admin'"), {"t": True})
s.commit()
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = req(C, "post", "/login", data={"username": "tk_admin", "password": "Parol123!"}, follow_redirects=False)
if _lr.status_code != 302:
    print("LOGIN BO'LMADI", _lr.status_code)
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)


def buyurtma(nom, narx=1_000_000):
    tana = {"project_id": PRJ_ID, "order_type": "product", "master_id": USTA_ID, "deadline": "2026-10-05",
            "items": [{"name": nom, "category": "profil", "width": 20, "thickness": 10, "length": 10,
                       "quantity": 1, "unit_price": narx, "is_coated": False, "penoplast_id": PENO_ID}]}
    r = req(C, "post", "/api/orders", json=tana, params={"confirm_shortage": "true"})
    return (js(r) or {}).get("id") if r.status_code == 200 else None


ID = {}
ID["O1"] = buyurtma("TK detal A")
ID["O2"] = buyurtma("TK detal B")
s = SessionLocal()
try:
    ID["IT1"] = s.execute(text("SELECT id FROM order_items WHERE order_id = :o"), {"o": ID["O1"]}).scalar()
finally:
    s.close()

section("0. Tayyorgarlik")
check("0.1 buyurtmalar yaratildi", ID["O1"] and ID["O2"] and ID["IT1"], ID)

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A. Telegram xabarlari — Toshkent vaqti")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
SOAT = _Soat(HOZIR)
SOAT.__enter__()


def tg_vaqtlar(xabarlar):
    """Har xabardagi "⏰ …" va boshqa sana-vaqtlar."""
    return [sanalar(x["matn"]) for x in xabarlar]


TG.clear()
_r = req(C, "post", f"/api/orders/{ID['O1']}/coating-notify", params={"loy_kg": "10"})
_x = [x for x in TG if "Loy tayyorlang" in x["matn"]]
check("A1 qoplama xabari (admin va qoplamachi): ⏰ 01.10.2026 01:59 (asl: 30.09.2026 20:59 — UTC)",
      _r.status_code == 200 and len(_x) >= 2 and all(v == [T_HOZIR] for v in tg_vaqtlar(_x)),
      [_r.status_code, tg_vaqtlar(_x)])

TG.clear()
_r = req(C, "post", "/api/deliveries", json={"order_id": ID["O1"], "items": [{"order_item_id": ID["IT1"], "quantity": 4}],
                                             "notes": "tk yuk", "transport_cost": 0, "transport_payer": "none",
                                             "payment_method": "naqd", "payment_amount": 100_000})
ID["D1"] = (js(_r) or {}).get("delivery_id") if isinstance(js(_r), dict) else None
_adm = [x for x in TG if x["tur"] == "_send_telegram" and "Mahsulot topshirildi" in x["matn"]]
_hujjat = [x for x in TG if x["tur"] == "_send_telegram_document"]
_matnli = [x for x in TG if x["tur"] == "_send_telegram_to" and "Yuk xati" in x["matn"]]
check("A2 yuk xati — admin xabari: ⏰ 01.10.2026 01:59", _r.status_code == 200 and len(_adm) == 1
      and tg_vaqtlar(_adm) == [[T_HOZIR]], [_r.status_code, tg_vaqtlar(_adm)])
check("A3 yuk xati — mijoz va usta: PDF izohi (2 ta) va matnli zaxira (2 ta) — ⏰ 01.10.2026 01:59",
      len(_hujjat) == 2 and len(_matnli) == 2 and all(v == [T_HOZIR] for v in tg_vaqtlar(_hujjat + _matnli)),
      [len(_hujjat), len(_matnli), tg_vaqtlar(_hujjat + _matnli)])

TG.clear()
_r = req(C, "post", f"/api/orders/{ID['O2']}/ready", params={"loy_kg": "5"})
_adm = [x for x in TG if x["tur"] == "_send_telegram" and "Buyurtma tayyor" in x["matn"]]
_mij = [x for x in TG if x["tur"] == "_send_telegram_to" and "Buyurtmangiz" in x["matn"]]
check("A4 «Tayyor» — admin va mijoz xabarlari: ⏰ 01.10.2026 01:59", _r.status_code == 200 and len(_adm) == 1
      and len(_mij) == 1 and tg_vaqtlar(_adm + _mij) == [[T_HOZIR], [T_HOZIR]], [_r.status_code, tg_vaqtlar(_adm + _mij)])

TG.clear()
_r = req(C, "post", "/api/inventory/full-stock-report")
_x = [x for x in TG if "Ombor hisoboti" in x["matn"]]
check("A5 ombor hisoboti: 01.10.2026 01:59", _r.status_code == 200 and tg_vaqtlar(_x) == [[T_HOZIR]],
      [_r.status_code, tg_vaqtlar(_x)])

TG.clear()
os.environ["BACKUP_TELEGRAM_CHAT_ID"] = "5550003"
xavfsiz(main.run_daily_backup)
os.environ.pop("BACKUP_TELEGRAM_CHAT_ID", None)
_x = [x for x in TG if x["tur"] == "_send_telegram_document"]
check("A6 kunlik zaxira: fayl nomi …2026-10-01.json va xabarda 📅 01.10.2026 (asl: 2026-09-30 / 30.09.2026)",
      len(_x) == 1 and "penodecorpro-backup-2026-10-01.json" in _x[0]["matn"] and "📅 01.10.2026" in _x[0]["matn"]
      and UTC_SANA not in _x[0]["matn"], [x["matn"][:160] for x in _x])

# ── yozuv vaqtlari — LAHZA (Toshkent 01.10 01:30) ──────────────────────────────────────────────────────────
_r1 = req(C, "post", "/api/finished/sell", json={"finished_product_id": TM_ID, "quantity": 1, "unit_price": 10_000,
                                                 "buyer_name": "TK xaridor"})
_r2 = req(C, "post", "/api/finished/sell-batch", json={"items": [{"finished_product_id": TM_ID, "quantity": 1,
                                                                   "unit_price": 10_000}], "buyer_name": "TK savat"})
ID["SALE"] = (js(_r1) or {}).get("sale_id") if isinstance(js(_r1), dict) else None
ID["GROUP"] = (js(_r2) or {}).get("sale_group_id") if isinstance(js(_r2), dict) else None
_rr = req(C, "post", "/api/returns", json={"order_id": ID["O1"], "order_item_id": ID["IT1"], "item_name": "TK detal A",
                                           "quantity": 1, "unit": "metr", "reason": "Brak", "to_stock": False})
ID["RET"] = (js(_rr) or {}).get("id") if isinstance(js(_rr), dict) else None
_re = req(C, "post", "/api/employees", json={"name": "TK Hodim", "pay_type": "fixed", "fixed_amount": 3_000_000})
ID["EMP"] = (js(_re) or {}).get("id") if isinstance(js(_re), dict) else None
req(C, "post", f"/api/orders/{ID['O1']}/pin")
s = SessionLocal()
try:
    s.add(Recipe(company_id=1, name="TK retsept", batch_size_kg=150, created_at=LAHZA))
    s.add(Recipe(company_id=1, name="TK retsept 2", batch_size_kg=150, created_at=datetime(2026, 9, 1, 8, 0),
                 updated_at=LAHZA))
    s.add(ActivityLog(company_id=1, action="deleted", entity_type="order", entity_id=ID["O2"] or 0,
                      entity_label="TK ochirildi", performed_by="TK", created_at=LAHZA))
    # xato jurnali — `models._uzb_now` bilan ALLAQACHON Toshkent vaqtida yoziladi (01.10 01:30 Toshkent)
    s.add(ErrorLog(company_id=1, error_message="TK xato jurnali", endpoint="/tk", created_at=datetime(2026, 10, 1, 1, 30)))
    for sql in ("UPDATE orders SET created_at = :d WHERE id IN (:a, :b)",
                "UPDATE deliveries SET delivered_at = :d WHERE order_id = :a",
                "UPDATE payments SET paid_at = :d WHERE order_id = :a",
                "UPDATE projects SET start_date = :d WHERE id = :p",
                "UPDATE users SET created_at = :d WHERE username = 'tk_admin'",
                "UPDATE login_history SET created_at = :d",
                "UPDATE return_items SET returned_at = :d",
                "UPDATE finished_product_sales SET sold_at = :d",
                "UPDATE employee_compensation_history SET created_at = :d"):
        s.execute(text(sql), {"d": LAHZA, "a": ID["O1"], "b": ID["O2"], "p": PRJ_ID})
    s.commit()
    _fiks = "ok"
except Exception as e:                     # noqa: BLE001
    s.rollback()
    _fiks = f"{type(e).__name__}: {e}"
finally:
    s.close()
check("0.2 yozuvlar (TM sotuvi yakka / guruh, qaytarish, hodim, retseptlar, jurnallar) — Toshkent 01.10 01:30 ga",
      _fiks == "ok" and all(ID.get(k) for k in ("D1", "SALE", "GROUP", "RET", "EMP")),
      [_fiks, {k: ID.get(k) for k in ("D1", "SALE", "GROUP", "RET", "EMP")}])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B. PDF hujjatlar — Toshkent vaqti")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════


def pdf(url, **k):
    r = req(C, "get", url, **k)
    return r.status_code, (pdf_matn(r.content) if r.status_code == 200 else "")


_st, _m = pdf(f"/api/orders/{ID['O1']}/pdf")
check("B1 nakladnoy: \"Sana: 01.10.2026\" (asl: 30.09.2026 — `datetime.now()`)", _st == 200 and f"Sana: {T_SANA}" in _m,
      [_st, re.findall(r"Sana:\s*[\d.]+", _m)])
check("B2 nakladnoy: \"Chiqarilgan: 01.10.2026 01:59\"", f"Chiqarilgan: {T_HOZIR}" in _m,
      re.findall(r"Chiqarilgan:\s*[\d. :]+", _m))
check("B3 nakladnoy: \"Yaratilgan sana\" — 01.10.2026 (buyurtma Toshkent 01:30 da); UTC sanasi YO'Q",
      "YARATILGAN SANA" in _m and sanalar(_m) == [T_SANA, T_HOZIR], sanalar(_m))
_st, _m = pdf(f"/api/deliveries/{ID['D1']}/pdf")
check("B4 yuk xati PDF: sana 01.10.2026 01:30, pastki qator 01.10.2026 01:59 (asl ham to'g'ri — yagona manbaga o'tdi)",
      _st == 200 and "01.10.2026  01:30" in _m and T_HOZIR in _m and UTC_SANA not in _m, [_st, sanalar(_m)])
_st, _m = pdf(f"/api/orders/{ID['O1']}/summary-pdf")
check("B5 hisob-kitob varaqasi: Davr va yuk qatori 01.10.2026, Sana 01.10.2026 01:59; UTC sanasi YO'Q (asl: 30.09.2026)",
      _st == 200 and "Davr:" in _m and sanalar(_m) == [T_SANA, T_HOZIR] and f"· {T_SANA} · Yuk xati" in _m,
      [_st, sanalar(_m), re.findall(r"· [\d.]+ · Yuk xati", _m)])
_st, _m = pdf(f"/api/finished/sales/{ID['SALE']}/pdf")
check("B6 TM sotuvi (yakka) PDF: 01.10.2026  01:30", _st == 200 and "01.10.2026  01:30" in _m and UTC_SANA not in _m,
      [_st, sanalar(_m)])
_st, _m = pdf(f"/api/finished/sales/batch/{ID['GROUP']}/pdf")
check("B7 TM sotuvi (guruh) PDF: 01.10.2026  01:30", _st == 200 and "01.10.2026  01:30" in _m and UTC_SANA not in _m,
      [_st, sanalar(_m)])
_st, _m = pdf("/api/finance/report-pdf", params={"year": 2026, "month": 10})
check("B8 oylik moliya PDF: \"Yaratildi: 01.10.2026 01:59\"", _st == 200 and f"Yaratildi: {T_HOZIR}" in _m,
      [_st, re.findall(r"Yaratildi:\s*[\d. :]+", _m)])


def _nazorat_pdf():
    """Sun'iy PDF (Type1 shrift, ASCII85 + Flate kontent oqimi): ASCII85 matni tugatuvchi "~>" dan OLDIN ">" bilan tugaydi
    (">" — ASCII85 ning oddiy belgisi; `rstrip(b"~>")` uni ham o'chirib Flate ni buzardi — ~1-2 % oqim, vaqt sayohatida
    tasodifiy yiqilish, kech106); birinchi satr ichida "ET" / "BT" bor ("QISMAN YETKAZISH (BT) ET")."""
    for i in range(5000):
        kontent = ("BT /F1 12 Tf 72 700 Td (QISMAN YETKAZISH \\(BT\\) ET) Tj ET\n"
                   f"BT /F1 12 Tf 72 680 Td (nazorat {i}) Tj ET\n").encode("latin-1")
        kod = base64.a85encode(zlib.compress(kontent))
        if kod.endswith(b">"):
            break
    oqim = kod + b"~>"
    return (b"%PDF-1.4\n1 0 obj\n<< /BaseFont /Helvetica /Encoding /WinAnsiEncoding /Name /F1 /Subtype /Type1 /Type /Font >>\n"
            b"endobj\n2 0 obj\n<< /Filter [ /ASCII85Decode /FlateDecode ] /Length " + str(len(oqim)).encode() + b" >>\nstream\n"
            + oqim + b"\nendstream\nendobj\n%%EOF\n"), i


try:
    _npdf, _ni = _nazorat_pdf()
    _n = pdf_matn(_npdf)
except Exception as e:                     # noqa: BLE001
    _ni, _n = -1, f"{type(e).__name__}: {e}"
check("B9 nazorat: PDF o'quvchi — ASCII85 oqimi \">\" bilan tugasa ham o'qiladi (tugatuvchi \"~>\" faqat bir marta olinadi), satr ichidagi \"ET\" / \"BT\" (\"YETKAZISH\") BT … ET blokini uzmaydi",
      _n == f"QISMAN YETKAZISH (BT) ET nazorat {_ni}", [_ni, _n[:80]])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("C. Sahifalar (Jinja) — Toshkent vaqti")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════


def sahifa(url):
    r = req(C, "get", url)
    return r.status_code, (r.text if r.status_code == 200 else "")


_st, _h = sahifa("/users")
check("C1 /users: foydalanuvchi yaratilgan 01.10.2026, \"Joriy siz\" vaqti 01.10.2026 01:59 (asl: 30.09)",
      _st == 200 and f">{T_SANA}</td>" in fikstura_qatori(_h, "tk_admin") and T_HOZIR in _h
      and utc_korinishi_yoq(fikstura_qatori(_h, "tk_admin")) and "30.09.2026 20:59" not in _h, [_st, sanalar(_h)])
_st, _h = sahifa("/logs")
check("C2 /logs: kirish va faoliyat 01.10.2026 01:30 (asl: 30.09.2026 20:30); UTC sanasi YO'Q",
      _st == 200 and _h.count(T_LAHZA) >= 3 and utc_korinishi_yoq(_h), [_st, sanalar(_h)])
check("C3 /logs: xato jurnali (allaqachon Toshkentda yozilgan) — 01.10.2026 01:30, IKKINCHI marta siljimagan (06:30 YO'Q)",
      "TK xato jurnali" in _h and "01.10.2026 06:30" not in _h, sanalar(_h))
_st, _h = sahifa("/orders")
check("C4 /orders: buyurtma sanasi 01.10.2026 (data-date va ro'yxat)", _st == 200
      and f'data-date="{T_SANA}"' in _h and f'<div class="ord-date">{T_SANA}' in _h
      and f'data-date="{UTC_SANA}"' not in _h, [_st, re.findall(r'data-date="[^"]*"', _h)[:4]])
_st, _h = sahifa("/projects")
check("C5 /projects: boshlanish 01.10.2026 / 2026-10-01 (filtr), muddat 05.10.2026 (kalendar kuni o'zgarmaydi)",
      _st == 200 and f'data-start="{T_SANA}"' in _h and 'data-start-raw="2026-10-01"' in _h
      and 'data-deadline="05.10.2026"' in _h, [_st, re.findall(r'data-(?:start|start-raw|deadline)="[^"]*"', _h)[:6]])
_st, _h = sahifa("/recipes")
check("C6 /recipes: \"Yaratilgan: 01.10.2026\" va \"Yangilangan: 01.10.2026\"", _st == 200
      and f"Yaratilgan: {T_SANA}" in _h and f"Yangilangan: {T_SANA}" in _h,
      [_st, re.findall(r"(?:Yaratilgan|Yangilangan): [\d.]+", _h)])
_st, _h = sahifa("/returns")
check("C7 /returns: qaytarish sanasi 01.10.2026", _st == 200 and re.search(r'class="ret-date"[^>]*>' + re.escape(T_SANA), _h),
      [_st, re.findall(r'class="ret-date"[^>]*>[\d.]+', _h)])
_st, _h = sahifa("/trash")
check("C8 /trash: o'chirish vaqti 01.10.2026 01:30", _st == 200 and T_LAHZA in _h and utc_korinishi_yoq(_h),
      [_st, sanalar(_h)])
_st, _h = sahifa("/debts")
check("C9 /debts: buyurtma muddati 05.10.2026 (kalendar kuni — siljimaydi)", _st == 200
      and 'data-deadline="05.10.2026"' in _h, [_st, re.findall(r'data-deadline="[^"]*"', _h)[:3]])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D. API matnlari — Toshkent vaqti")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
_r = req(C, "get", f"/api/employees/{ID['EMP']}/compensation-history")
_j = js(_r) if isinstance(js(_r), list) else []
check("D1 hodim to'lov tarixi: \"01.10.2026 01:30\" (asl: 30.09.2026 20:30)", _r.status_code == 200 and _j
      and all(x.get("created_at") == T_LAHZA for x in _j), [_r.status_code, [x.get("created_at") for x in _j]])
_r = req(C, "get", "/api/orders/pinned")
_j = [x for x in (js(_r) if isinstance(js(_r), list) else []) if x.get("id") == ID["O1"]]
check("D2 mahkamlangan buyurtma: yaratilgan 01.10.2026, muddat 05.10.2026", _r.status_code == 200 and len(_j) == 1
      and _j[0].get("created_at") == T_SANA and _j[0].get("deadline") == "05.10.2026",
      [_r.status_code, [(x.get("created_at"), x.get("deadline")) for x in _j]])
s = SessionLocal()
try:
    _pid = s.execute(text("SELECT id FROM payments WHERE order_id = :o ORDER BY id"), {"o": ID["O1"]}).scalar()
finally:
    s.close()
_r = req(C, "delete", f"/api/payments/{_pid}")
s = SessionLocal()
try:
    _au = " ".join(str(v or "") for row in s.execute(text(
        "SELECT old_value, new_value FROM activity_logs WHERE entity_type = 'payment'")).fetchall() for v in row)
finally:
    s.close()
check("D3 to'lov o'chirilgandagi jurnal matni: \"sana: 2026-10-01 01:30\" (asl: 2026-09-30 20:30)",
      _r.status_code == 200 and "sana: 2026-10-01 01:30" in _au and "2026-09-30" not in _au,
      [_r.status_code, re.findall(r"sana: [\d\- :]+", _au)])
_r = req(C, "get", "/api/system/backup")
_disp = (getattr(_r, "headers", {}) or {}).get("content-disposition", "")
check("D4 zaxira fayli nomi: penodecorpro-backup-2026-10-01_01-59.json (asl: …2026-09-30_20-59)",
      _r.status_code == 200 and "penodecorpro-backup-2026-10-01_01-59.json" in _disp, [_r.status_code, _disp])

SOAT.__exit__()

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E. Yordamchilar — database.tashkent_vaqt, Jinja |toshkent")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
_tv = getattr(database, "tashkent_vaqt", None)
check("E1 database.tashkent_vaqt bor", callable(_tv))
check("E2 naive UTC 30.09 20:30 → 2026-10-01 01:30 (Toshkent)", callable(_tv)
      and xavfsiz(_tv, LAHZA) == datetime(2026, 10, 1, 1, 30), xavfsiz(_tv, LAHZA) if callable(_tv) else None)
with _Soat(HOZIR):
    _hz = xavfsiz(_tv) if callable(_tv) else None
check("E3 argumentsiz — HOZIR (UTC 20:59) + 5 soat = 2026-10-01 01:59", _hz == datetime(2026, 10, 1, 1, 59), _hz)
_aw = datetime(2026, 10, 1, 1, 0, tzinfo=timezone(timedelta(hours=3)))       # = UTC 30.09 22:00
check("E4 mintaqali qiymat (UTC+3 01.10 01:00 = UTC 30.09 22:00) → naive 2026-10-01 03:00",
      callable(_tv) and xavfsiz(_tv, _aw) == datetime(2026, 10, 1, 3, 0), xavfsiz(_tv, _aw) if callable(_tv) else None)
check("E5 faqat sana (date 2026-10-01) — kalendar kuni, siljimaydi → 2026-10-01 00:00",
      callable(_tv) and xavfsiz(_tv, date(2026, 10, 1)) == datetime(2026, 10, 1, 0, 0),
      xavfsiz(_tv, date(2026, 10, 1)) if callable(_tv) else None)
_xt = xavfsiz(_tv, "2026-10-01") if callable(_tv) else None
check("E6 noto'g'ri tur (satr) — TypeError (jim noto'g'ri natija EMAS)", isinstance(_xt, tuple) and "TypeError" in _xt[1], _xt)
_f = main.templates.env.filters.get("toshkent")
check("E7 Jinja filtri `toshkent` ro'yxatda", callable(_f))
check("E8 filtr: standart format \"01.10.2026 01:30\", '%d.%m.%Y' — \"01.10.2026\", '%Y-%m-%d' — \"2026-10-01\"",
      callable(_f) and xavfsiz(_f, LAHZA) == T_LAHZA and xavfsiz(_f, LAHZA, "%d.%m.%Y") == T_SANA
      and xavfsiz(_f, LAHZA, "%Y-%m-%d") == "2026-10-01",
      [xavfsiz(_f, LAHZA), xavfsiz(_f, LAHZA, "%d.%m.%Y")] if callable(_f) else None)
check("E9 filtr: qiymat yo'q (None / '') — bo'sh satr (asl shablon `None.strftime` — 500)",
      callable(_f) and xavfsiz(_f, None) == "" and xavfsiz(_f, "") == "",
      [xavfsiz(_f, None), xavfsiz(_f, "")] if callable(_f) else None)
_mt = [getattr(main, "_t_vaqt", None), getattr(crud, "_tashkent_vaqt", None), getattr(pdf_service, "_tashkent_vaqt", None),
       getattr(delivery_pdf, "_tashkent_vaqt", None), getattr(finance_pdf, "_tashkent_vaqt", None)]
check("E10 main / crud / pdf_service / delivery_pdf / finance_pdf — AYNAN `database.tashkent_vaqt` (yagona manba)",
      callable(_tv) and all(x is _tv for x in _mt), [x is _tv for x in _mt])

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("F. Statik — server kodi va shablonlar")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
SERVER = ["main.py", "crud.py", "services.py", "database.py", "pdf_service.py", "delivery_pdf.py", "finance_pdf.py",
          "auth.py", "company_brand.py", "production_routes.py", "production_service.py", "tenant_context.py"]
VAQT_USTUN = re.compile(r"(_at|^date$|^deadline$|_date$)")


def ast_topilmalar(matn):
    """(1) `datetime.now()` mintaqasiz, (2) `date.today()`, (3) `X.<vaqt ustuni>.strftime(...)` — izoh / hujjat
    satrlari hisobga olinmaydi (AST), f-satr ichidagi ifodalar esa hisobga olinadi."""
    try:
        tree = ast.parse(matn)
    except SyntaxError as e:
        return [("SINTAKSIS", str(e))]
    out = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call) or not isinstance(n.func, ast.Attribute):
            continue
        f = n.func
        if f.attr == "now" and isinstance(f.value, ast.Name) and f.value.id == "datetime" and not n.args and not n.keywords:
            out.append(("datetime.now()", n.lineno))
        if f.attr == "today" and isinstance(f.value, ast.Name) and f.value.id == "date":
            out.append(("date.today()", n.lineno))
        if f.attr == "strftime" and isinstance(f.value, ast.Attribute) and VAQT_USTUN.search(f.value.attr):
            out.append((f"{f.value.attr}.strftime", n.lineno))
    return out


_top = {nom: ast_topilmalar(fayl(nom)) for nom in SERVER}
check("F1 server kodida `datetime.now()` (mintaqasiz — Railway da UTC) yo'q",
      not any(x[0] == "datetime.now()" for v in _top.values() for x in v),
      {k: [x for x in v if x[0] == "datetime.now()"] for k, v in _top.items() if any(x[0] == "datetime.now()" for x in v)})
check("F2 server kodida `date.today()` yo'q", not any(x[0] == "date.today()" for v in _top.values() for x in v),
      {k: v for k, v in _top.items() if any(x[0] == "date.today()" for x in v)})
check("F3 server kodida bazadagi vaqt ustuni to'g'ridan-to'g'ri `.strftime(` qilinmaydi (`tashkent_vaqt(...)` orqali)",
      not any(x[0].endswith(".strftime") for v in _top.values() for x in v),
      {k: [x for x in v if x[0].endswith(".strftime")] for k, v in _top.items() if any(x[0].endswith(".strftime") for x in v)})
_naz = ast_topilmalar('"""datetime.now() — hujjat satri"""\n# datetime.now() — izoh\nx = f"⏰ {datetime.now().strftime(\'%H\')}"\n'
                      'y = o.created_at.strftime("%d")\nz = date.today()\nw = datetime.now(UZB)\n')
check("F4 nazorat: AST tahlili f-satr ichidagi `datetime.now()`, `o.created_at.strftime`, `date.today()` ni TOPADI, "
      "izoh / hujjat satri va `datetime.now(mintaqa)` ni topmaydi",
      sorted(x[0] for x in _naz) == ["created_at.strftime", "date.today()", "datetime.now()"], _naz)
_jinja_hato = []
for _nom in sorted(os.listdir(os.path.join(ROOT, "templates"))):
    if not _nom.endswith(".html"):
        continue
    for _i, _q in enumerate(fayl(os.path.join("templates", _nom)).split("\n"), 1):
        for _m in re.finditer(r"\{\{[^}]*?\b(\w+)\.(\w+)\.strftime\(", _q):
            if VAQT_USTUN.search(_m.group(2)) and not (_nom == "logs.html" and _m.group(1) == "e" and _m.group(2) == "created_at"):
                _jinja_hato.append(f"{_nom}:{_i} {_m.group(1)}.{_m.group(2)}")
check("F5 shablonlarda bazadagi vaqt `|toshkent` filtri bilan (to'g'ridan-to'g'ri `.strftime(` — faqat ErrorLog `e.created_at`)",
      not _jinja_hato, _jinja_hato)
check("F6 logs.html: xato jurnali (ErrorLog) filtrsiz — ikki marta siljimasin (izohi bilan)",
      "e.created_at.strftime('%d.%m.%Y %H:%M')" in fayl("templates/logs.html") and "models._uzb_now" in fayl("templates/logs.html"))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
