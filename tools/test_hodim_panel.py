#!/usr/bin/env python3
"""
test_hodim_panel.py — kech133 (zip 158): hodim paneli (`/hodim`) — SERVER (`/api/hodim/oylik`: 12 oy, `?oy=YYYY-MM`) va SHABLON (statik).

NIMA UCHUN KERAK (egasi 09.10 12:00: hodimlar telefondan «avans yozadigan joyni topa olishmayapti, pastga surilmayapti»)
-------------------------------------------------------------------------------------------------------------------
  O'LCHANGAN (`work/k158/hodim_skrol.py`, haqiqiy Chromium, zip 157 kodi): `static/style.css` dagi asosiy ilova qoidasi
  `body{height:100vh;overflow:hidden}` 2026-09-30 dan (style.css ulangandan beri) mustaqil hodim panelida ham qo'llanardi — sahifa
  umuman SURILMASDI; «Oyligim» ro'yxati uzaygach (20 to'lov) «💰 Avans oldim deb yozish» formasi 915 px da, ekran 812 px — yetib
  bo'lmasdi. EGASI QARORLARI (09.10, tugmali + matn): avans formasi TEPADA; «Oyligim» — joriy oy ochiq, tugagan oylar yopiq
  («shtorka»), oxirgi 12 oy.

BO'LIMLAR
  A — `/api/hodim/oylik` (standart): joriy va o'tgan oy — eskisidek (raqamlar admin hisobotidan); `boshqa_oylar` — 3-…12-oylar faqat
      nomi bilan: ishga kirgan oy va keyingilari (`hire_date` — oylik hisobidagi qoida bilan bir xil) yoki to'lov bo'lgan oy; 12 oydan
      eskisi YO'Q; boshqa hodimning to'lovi ta'sir qilmaydi; standart so'rovda korxona oylik hisoboti FAQAT 2 marta (12 emas);
  B — `?oy=YYYY-MM`: o'sha oy (raqamlar admin hisoboti bilan AYNAN), joriy oy — «joriy»; ishga kirmagan va to'lovsiz oy — bo'sh ro'yxat;
      12 oydan eski, kelajak, 13-oy, 00-oy, noto'g'ri yozuv — 400; bo'sh `?oy=` — standart javob; hodimsiz — 401;
  C — hodim_panel.html (statik): sahifa suriladi (`height:auto;overflow:visible` style.css dan KEYIN), forma → Oyligim → So'rovlarim
      tartibi, yopiq oy (`<details>`), ochilganda bitta oy so'rovi.
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
Asl kodga (zip 157) qarshi YIQILADI (QULAMAYDI).
ISHLATISH: python3 tools/test_hodim_panel.py
"""
import os
import re
import sys
import tempfile

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "hodim_panel158_test"
_DB = os.path.join(tempfile.gettempdir(), "hodim_panel158_test.db")
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
from datetime import datetime                      # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import services                                # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal, tashkent_date   # noqa: E402
from models import UserRole, Employee, EmployeeAdvance  # noqa: E402
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


OY = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]
BUGUN = tashkent_date()


def oldin(n):
    """Bugungi (Toshkent) oydan n oy oldingi (yil, oy) — sinovning O'Z hisobi (servernikidan mustaqil)."""
    y, m = BUGUN.year, BUGUN.month
    for _ in range(n):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return y, m


def kalit(n):
    y, m = oldin(n)
    return f"{y:04d}-{m:02d}"


# ══════════════════════════════════════════════════════════════
# Fikstura: admin; U — 5 oy oldin ishga kirgan (to'lovlar: joriy 8, o'tgan 12, 3-oy 2, 7-oy — ISHGA KIRISHDAN OLDIN 1);
# Q — 20 oy oldin ishga kirgan (hamma 11 o'tgan oy); Y — shu oy ishga kirgan; boshqa hodim (X) — 9-oyda to'lov (U ga ta'sir qilmaydi)
# ══════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(s, "hp_admin", "Parol123!", UserRole.ADMIN, "HP admin", company_id=1)
s.commit()
s.close()
A = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
A.post("/login", data={"username": "hp_admin", "password": "Parol123!"}, follow_redirects=False)


def hodim(nom, tel, pin, oy_oldin):
    r = A.post("/api/employees", json={"name": nom, "position": "Kesuvchi", "pay_type": "fixed", "fixed_amount": 11_000_000})
    eid = js(r).get("id")
    A.post(f"/api/employees/{eid}/set-login", data={"phone": tel, "pin": pin})
    y, m = oldin(oy_oldin)
    ss = SessionLocal()
    ss.query(Employee).filter(Employee.id == eid).update({"hire_date": datetime(y, m, 1, 5, 0)})   # Toshkent 1-kun 10:00
    ss.commit()
    ss.close()
    h = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    st = h.post("/hodim/login", data={"phone": tel, "pin": pin, "korxona": ""}, follow_redirects=False).status_code
    return eid, h, st


def avans(eid, n, kun, summa):
    y, m = oldin(n)
    ss = SessionLocal()
    ss.add(EmployeeAdvance(employee_id=eid, amount=summa, date=datetime(y, m, kun, 7, 0), notes="naqd", given_by="HP admin"))
    ss.commit()
    ss.close()


EU, HU, _s1 = hodim("Ulug'bek", "+998901110001", "4321", 5)
EQ, HQ, _s2 = hodim("Qadimiy", "+998901110002", "4322", 20)
EY, HY, _s3 = hodim("Yangi", "+998901110003", "4323", 0)
EX, HX, _s4 = hodim("Boshqa", "+998901110004", "4324", 1)
check("0 hodimlar paneliga kiradi (302)", (_s1, _s2, _s3, _s4) == (302, 302, 302, 302), (_s1, _s2, _s3, _s4))
for i in range(min(8, BUGUN.day)):
    avans(EU, 0, 1 + i % BUGUN.day, 50_000 + i * 1_000)
for i in range(12):
    avans(EU, 1, 1 + i * 2, 30_000 + i * 1_000)
avans(EU, 3, 10, 70_000)
avans(EU, 3, 20, 80_000)
avans(EU, 7, 15, 90_000)
avans(EX, 9, 12, 55_000)

# ══════════════════════════════════════════════════════════════
section("A. /api/hodim/oylik — joriy va o'tgan oy, qolgan oylar ro'yxati")
# ══════════════════════════════════════════════════════════════
_sanoq = {"n": 0}
_asl_rep = services.get_monthly_report


def _sanaydi(*a, **k):
    _sanoq["n"] += 1
    return _asl_rep(*a, **k)


services.get_monthly_report = _sanaydi
try:
    r = HU.get("/api/hodim/oylik")
finally:
    services.get_monthly_report = _asl_rep
d = js(r)
oylar = d.get("oylar") or []
boshqa = d.get("boshqa_oylar")
check("A1 200; «oylar» — joriy (BIRINCHI, «joriy») va o'tgan oy (to'liq raqamlar) — eskisidek",
      r.status_code == 200 and len(oylar) == 2 and oylar[0].get("joriy") is True and oylar[1].get("joriy") is False
      and (oylar[0].get("yil"), oylar[0].get("oy")) == oldin(0) and (oylar[1].get("yil"), oylar[1].get("oy")) == oldin(1)
      and len(oylar[1].get("tolovlar") or []) == 12, (r.status_code, [(o.get("oy"), o.get("joriy")) for o in oylar]))
_rep1 = services.get_monthly_report(SessionLocal(), *oldin(1), company_id=1)
_e1 = next((x for x in _rep1.get("hodimlar_moslashuvchan_breakdown", []) if x.get("employee_id") == EU), {})
check("A2 o'tgan oy raqamlari admin Hisobot / Moliya bilan AYNAN (hisoblangan 11 000 000, olingan = 12 to'lov, qolgan)",
      len(oylar) == 2 and oylar[1].get("hisoblangan") == round(_e1.get("amount", -1)) == 11_000_000
      and oylar[1].get("olingan") == round(_e1.get("avans", -1)) == sum(30_000 + i * 1_000 for i in range(12))
      and oylar[1].get("qolgan") == round(_e1.get("qolgan", -1)), (oylar[1:] and {k: oylar[1].get(k) for k in ("hisoblangan", "olingan", "qolgan")}, _e1))
_kut = [{"yil": oldin(n)[0], "oy": oldin(n)[1], "nomi": f"{OY[oldin(n)[1]]} {oldin(n)[0]}"} for n in (2, 3, 4, 5, 7)]
check("A3 «boshqa_oylar» — 3-…5-oy (ishga kirgan oy — 5-oy — ham) va 7-oy (ishga kirishdan OLDIN, lekin to'lov bor); 6-oy (ishga kirmagan, "
      "to'lovsiz) YO'Q; nomi «Oy Yil»; eng yangisi birinchi",
      boshqa == _kut, (boshqa, _kut))
check("A4 standart so'rovda korxona oylik hisoboti FAQAT 2 marta (joriy va o'tgan oy) — qolgan oylar ochilganda (12 ta birdan emas)",
      _sanoq["n"] == 2, _sanoq["n"])
dq = js(HQ.get("/api/hodim/oylik"))
_kq = [f"{oldin(n)[0]}-{oldin(n)[1]}" for n in range(2, 12)]
check("A5 20 oy oldin ishga kirgan hodim — «boshqa_oylar» 10 ta (3-…12-oy, jami 12 oy), 13-oy va eskisi YO'Q",
      [f"{b.get('yil')}-{b.get('oy')}" for b in (dq.get("boshqa_oylar") or [])] == _kq and len(dq.get("oylar") or []) == 2,
      (dq.get("boshqa_oylar"), _kq))
dy = js(HY.get("/api/hodim/oylik"))
check("A6 shu oy ishga kirgan, to'lovsiz hodim — faqat joriy oy; o'tgan oy va «boshqa_oylar» bo'sh",
      len(dy.get("oylar") or []) == 1 and (dy.get("oylar") or [{}])[0].get("joriy") is True and dy.get("boshqa_oylar") == [], dy)
dx = js(HX.get("/api/hodim/oylik"))
check("A7 boshqa hodim (X): o'z 9-oy to'lovi ko'rinadi; U ning to'lovlari X ga, X niki U ga ta'sir qilmaydi (U da 9-oy yo'q)",
      [(b.get("yil"), b.get("oy")) for b in (dx.get("boshqa_oylar") or [])] == [oldin(9)]
      and oldin(9) not in [(b.get("yil"), b.get("oy")) for b in (boshqa or [])], (dx, boshqa))

# ══════════════════════════════════════════════════════════════
section("B. /api/hodim/oylik?oy=YYYY-MM — bitta oy")
# ══════════════════════════════════════════════════════════════
r3 = HU.get("/api/hodim/oylik", params={"oy": kalit(3)})
o3 = (js(r3).get("oylar") or [{}])[0]
_rep3 = services.get_monthly_report(SessionLocal(), *oldin(3), company_id=1)
_e3 = next((x for x in _rep3.get("hodimlar_moslashuvchan_breakdown", []) if x.get("employee_id") == EU), {})
check("B1 3-oy: 200, bitta oy — hisoblangan / olingan / qolgan admin hisoboti bilan AYNAN, 2 to'lov (80 000, 70 000), «joriy» emas",
      r3.status_code == 200 and len(js(r3).get("oylar") or []) == 1 and (o3.get("yil"), o3.get("oy")) == oldin(3)
      and o3.get("joriy") is False and o3.get("hisoblangan") == round(_e3.get("amount", -1)) == 11_000_000
      and o3.get("olingan") == round(_e3.get("avans", -1)) == 150_000 and o3.get("qolgan") == round(_e3.get("qolgan", -1))
      and [t.get("summa") for t in o3.get("tolovlar") or []] == [80_000, 70_000] and "boshqa_oylar" not in js(r3), (r3.status_code, o3, _e3))
r0 = HU.get("/api/hodim/oylik", params={"oy": kalit(0)})
check("B2 joriy oy so'ralsa — «joriy», to'lovlar 8 ta (standart javobdagi joriy oy bilan AYNAN)",
      r0.status_code == 200 and (js(r0).get("oylar") or [{}])[0] == oylar[0], (r0.status_code, js(r0)))
r6 = HU.get("/api/hodim/oylik", params={"oy": kalit(6)})
r7 = HU.get("/api/hodim/oylik", params={"oy": kalit(7)})
o7 = (js(r7).get("oylar") or [{}])[0]
check("B3 6-oy (ishga kirmagan, to'lovsiz) — 200, bo'sh ro'yxat; 7-oy (ishga kirishdan oldin to'lov) — hisoblangan 0, olingan 90 000, "
      "qolgan −90 000",
      r6.status_code == 200 and js(r6).get("oylar") == [] and r7.status_code == 200
      and (o7.get("hisoblangan"), o7.get("olingan"), o7.get("qolgan")) == (0, 90_000, -90_000), (js(r6), o7))
_y11, _m11 = oldin(11)
_y12, _m12 = oldin(12)
_kel_y, _kel_m = (BUGUN.year + (1 if BUGUN.month == 12 else 0), 1 if BUGUN.month == 12 else BUGUN.month + 1)
_rad = {q: HU.get("/api/hodim/oylik", params={"oy": q}) for q in
        (f"{_y12:04d}-{_m12:02d}", f"{_kel_y:04d}-{_kel_m:02d}", f"{BUGUN.year:04d}-13", f"{BUGUN.year:04d}-00", "abc", "2026-1", "2026-10-01")}
r11 = HU.get("/api/hodim/oylik", params={"oy": f"{_y11:04d}-{_m11:02d}"})
# sabab — FAQAT o'zbekcha ikki matndan biri (kech133 mutatsiya M13: oy raqami tekshiruvi olib tashlansa «2026-00» ham 400 berardi,
# lekin `datetime` ning inglizcha «month must be in 1..12» matni bilan — tekshiruv shuni ushlaydi)
_SABAB = {"Oy noto'g'ri (YYYY-MM)", "Oy noto'g'ri — faqat oxirgi 12 oy ko'rsatiladi"}
check("B4 12-oy (oxirgi 12 oy ichida) — 200; 13-oy (eski), kelajak oy, 13 / 00 oy, noto'g'ri yozuv — 400, sababi o'zbekcha (500 emas)",
      r11.status_code == 200 and all(x.status_code == 400 and js(x).get("detail") in _SABAB for x in _rad.values()),
      (r11.status_code, {q: (x.status_code, js(x).get("detail")) for q, x in _rad.items()}))
rb = HU.get("/api/hodim/oylik", params={"oy": ""})
check("B5 bo'sh `?oy=` — standart javob (joriy, o'tgan, «boshqa_oylar»)", rb.status_code == 200 and js(rb) == d, (rb.status_code, js(rb)))
_bosh = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
check("B6 hodim sessiyasisiz — 401; admin sessiyasi bilan — 401 (`?oy=` bilan ham)",
      _bosh.get("/api/hodim/oylik", params={"oy": kalit(3)}).status_code == 401
      and A.get("/api/hodim/oylik", params={"oy": kalit(3)}).status_code == 401)

# ══════════════════════════════════════════════════════════════
section("C. hodim_panel.html (statik)")
# ══════════════════════════════════════════════════════════════
H = open(os.path.join(ROOT, "templates", "hodim_panel.html"), encoding="utf-8").read()
_hz = re.sub(r"<!--.*?-->", "", re.sub(r"\{#.*?#\}", "", H, flags=re.S), flags=re.S)
_st = H.find('href="/static/style.css')
_bm = re.search(r"\n\s*body\{([^}]*)\}", _hz)
check("C1 sahifa suriladi: `body` qoidasi style.css ulangandan KEYIN va `height:auto` + `overflow:visible` (style.css dagi asosiy ilova "
      "`body{height:100vh;overflow:hidden}` bekor)",
      _st > 0 and _bm is not None and _hz.find(_bm.group(0)) > _hz.find('href="/static/style.css')
      and "height:auto" in _bm.group(1) and "overflow:visible" in _bm.group(1), _bm.group(0) if _bm else None)
_i_forma = _hz.find('<div class="h-card-title">💰 Avans oldim deb yozish</div>')
_i_oylik = _hz.find('<div class="h-card-title">💵 Oyligim</div>')
_i_sorov = _hz.find('<div class="h-card-title">📋 Mening so\'rovlarim</div>')
check("C2 tartib (egasi qarori): «💰 Avans oldim deb yozish» → «💵 Oyligim» → «📋 Mening so'rovlarim»",
      0 < _i_forma < _i_oylik < _i_sorov, (_i_forma, _i_oylik, _i_sorov))
check("C3 tugagan oy — yopiq `<details class=\"oy-yopiq\">` (sarlavhada qolgan summa); qolgan oylar ochilganda bitta oy so'raladi "
      "(`?oy=`), standart so'rov o'zgarmagan",
      '<details class="oy-yopiq"' in H and "ontoggle=\"if (this.open) oyniYukla(this)\"" in H
      and "fetch('/api/hodim/oylik?oy=' + encodeURIComponent(dt.dataset.oy))" in H and "fetch('/api/hodim/oylik')" in H
      and "o.joriy ? oylikHtml(o) : oyYopiqHtml(o)" in H)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAIL:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
