#!/usr/bin/env python3
"""test_soat_utc.py — kech96 (2026-09-27), 123-band.

NIMA UCHUN KERAK
----------------
Server hamma yozuvni UTC da saqlaydi (`default=datetime.utcnow`) va hisobot / "bugun" oynalarini shu bilan oladi.
Jonli sayt jarayoni UTC da ishlaydi (kech96 o'lchovi: `/users` sahifasidagi server `datetime.now()` 00:29 =
brauzer 00:29Z) — shuning uchun jonli xulq izchil. Lekin:
  • testlar yil / oy / kunni lokal `datetime.now()` dan olardi (konteyner +05): butun `hammasi` to'plami soat
    siljitilib O'LCHANDI (kech96 `run/h96tz.sh`, `run/h96vaqt.sh`, asl = zip 89) — lokal sana ≠ UTC sana:
    `test_transport_foyda` 2 (K92-1); oy chegarasi (Toshkent 1-sana 02:00): `test_naqd_kassa` 15,
    `test_transport_foyda` 17, `test_brak_bekor` 1 — SOXTA yiqilishlar;
  • serverda 3 ta standart jarayon mintaqasiga bog'liq edi: `/api/finance/daily` (sana berilmasa
    `date.today()`), usta KPI hisoboti / tafsiloti (yil berilmasa `datetime.now().year`), Telegram keshbek yili —
    TZ o'rnatilgan muhitda UTC yozuvlar bilan aralashardi (19:00–24:00 UTC oralig'ida "bugun" boshqa kun).

kech105 (9 + 50-band, FOYDALANUVCHI QARORI 2026-09-28 "Toshkent vaqti bo'yicha"): hisobotlarning kun / oy / yili
endi TOSHKENT kalendari — server standartlari (`/api/finance/daily` sanasiz, usta KPI yili, Telegram keshbek yili)
`database.tashkent_date()` dan (UTC + 5 — jarayon mintaqasiga bog'liq EMAS); 3 test ham hisobot davrini Toshkent
devor soatidan (UTC + 5) oladi. Test nomi (`soat_utc`) tarixiy: talab — lokal mintaqaga bog'liq bo'lmaslik.

BO'LIMLAR
---------
  A — dinamik: jarayon mintaqasi ataylab lokal sana ≠ TOSHKENT sana bo'ladigan qilib qo'yiladi (Toshkent soatiga
      qarab Etc/GMT+12 yoki Etc/GMT-12); `/api/finance/daily` SANASIZ — hozir yozilgan xarajat Toshkent "bugun" ida
      bo'lishi shart;
  S — statik: server standartlari Toshkent kalendari (`tashkent_date`); soatga bog'liq bo'lgan 3 test hisobot
      davrini Toshkent devor soatidan oladi (lokal soat ham, UTC sana ham EMAS).

ISHLATISH
---------
    python3 tools/test_soat_utc.py

Chiqish kodi: 0 — hammasi o'tdi, 1 — kamida bittasi yiqildi.
"""
import os
import re
import sys
import time
import inspect
import tempfile
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

# Jarayon mintaqasi — lokal sana TOSHKENT sanasidan FARQ qiladigan qilib (ilova import qilinishidan OLDIN).
# kech105: Toshkent = UTC + 5. Etc/GMT+12 (UTC − 12 = Toshkent − 17 soat) — Toshkent soati 17:00 gacha lokal sana
# boshqa; Etc/GMT-14 (UTC + 14 = Toshkent + 9 soat) — Toshkent 15:00 dan keyin boshqa. Chegara 16 — ikkala tomonga
# 1 soat zaxira (Etc/GMT-12 = UTC + 12 bo'lardi: Toshkent 17:00 gacha lokal sana BIR XIL — yaramaydi).
_t_soat = (datetime.utcnow().hour + 5) % 24
os.environ["TZ"] = "Etc/GMT+12" if _t_soat < 16 else "Etc/GMT-14"
time.tzset()

_T = tempfile.mkdtemp(prefix="soat_")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_T, "soat_utc_test.db")
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
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


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


section("A. Dinamik: jarayon mintaqasi ≠ Toshkent — \"bugun\" Toshkent kalendarida")
_lokal, _tosh = datetime.now().date(), (datetime.utcnow() + timedelta(hours=5)).date()
check(f"A0 sinov sharti: lokal sana ({_lokal}) ≠ Toshkent sana ({_tosh}), TZ={os.environ['TZ']}", _lokal != _tosh)
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "soat_admin", "Parol123!", UserRole.ADMIN, "Soat Admin", company_id=1)
s.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lr = C.post("/login", data={"username": "soat_admin", "password": "Parol123!"}, follow_redirects=False)
check("A1 login", _lr.status_code in (200, 302, 303), _lr.status_code)
r = C.post("/api/transport-expenses", json={"amount": 4321, "materials_note": "SOAT123", "notes": "SOAT123"})
check("A2 transport xarajati yozildi (vaqt — server standarti, utcnow)", r.status_code == 200, (r.status_code, r.text[:200]))
d = js(C.get("/api/finance/daily"))
try:
    _tr = float(d["expenses"]["transport"]["total"])
except Exception:                          # noqa: BLE001
    _tr = None
check("A3 `/api/finance/daily` SANASIZ: hozirgi transport xarajati \"bugun\" da (4 321) — standart Toshkent kuni",
      _tr == 4321.0 and d.get("date") == _tosh.isoformat(), (d.get("date"), _tr))
d2 = js(C.get("/api/finance/daily", params={"target_date": _tosh.isoformat()}))
check("A4 aniq Toshkent sana bilan ham AYNAN (nazorat)", d2.get("date") == _tosh.isoformat()
      and float(((d2.get("expenses") or {}).get("transport") or {}).get("total") or 0) == 4321.0, d2.get("date"))

section("S. Statik")
_src = inspect.getsource(main.api_finance_daily)
check("S1 `/api/finance/daily` standarti — Toshkent sanasi `database.tashkent_date()` (lokal `date.today()` ham, "
      "UTC `utcnow().date()` ham EMAS)",
      "tashkent_date as _t_sana" in _src and "d = _t_sana()" in _src and "date_cls.today()" not in _src
      and "utcnow().date()" not in _src)
_k1 = inspect.getsource(main.api_masters_kpi_report)
_k2 = inspect.getsource(main.api_master_kpi_detail)
check("S2 usta KPI hisoboti / tafsiloti — joriy yil Toshkent (`_t_sana().year`)", "_t_sana().year" in _k1
      and "_t_sana().year" in _k2 and "datetime.now().year" not in _k1 + _k2 and "utcnow().year" not in _k1 + _k2)
with open(os.path.join(ROOT, "main.py"), encoding="utf-8") as f:
    _main = f.read()
check("S3 main.py da `datetime.now().year` ham, `utcnow().year` ham qolmadi (Telegram keshbek yili ham Toshkent)",
      "datetime.now().year" not in _main and "utcnow().year" not in _main)


def kod_qatorlari(yol):
    with open(os.path.join(ROOT, yol), encoding="utf-8") as f:
        return [q.split("#", 1)[0] for q in f.read().splitlines()]


for _t in ("tools/test_transport_foyda.py", "tools/test_naqd_kassa.py", "tools/test_brak_bekor.py"):
    _q = kod_qatorlari(_t)
    _lokal_q = [q.strip() for q in _q if re.search(r"\b(datetime|_dt|dt)\.now\(\)|date\.today\(\)", q)]
    check(f"S4 {_t}: lokal soat (`now()` / `date.today()`) ishlatilmaydi", not _lokal_q, _lokal_q[:3])
    # kech105: hisobot davri (yil / oy / kun) UTC sanadan ham olinmaydi — Toshkent devor soati (UTC + 5)
    _utc_q = [q.strip() for q in _q if re.search(r"utcnow\(\)\.(year|month|day|date\(\))|\bNOW\.(year|month|day|date\(\)"
                                                 r"|replace\()|=\s*_dt\.utcnow\(\)\s*$", q)]
    check(f"S5 {_t}: hisobot davri UTC sanadan olinmaydi (Toshkent devor soati — UTC + 5)",
          not _utc_q and any("hours=5" in q for q in _q), _utc_q[:3])

print()
print("=" * 60)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
print("=" * 60)
sys.exit(0 if FAIL == 0 else 1)
