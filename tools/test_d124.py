#!/usr/bin/env python3
"""
test_d124.py — kech118 D BOSQICHI 4-qism (zip 124): SAHIFALAR VAZIFASI (egasi QARORI kech118 11:40 «Vazifalar ajratilsin» — G1-09,
G2-17, G1-24; 01.10 «Tezkor kirish — 3–4 asosiy amal»; tugmali, QAYTA SO'RALMAYDI).

NIMA UCHUN KERAK (audit topilmalari)
  G1-09  Uch sahifada bir xil bloklar: «Buyurtmalar holati» doirasi Bosh sahifada ham, Dashboard da ham (yonida «Ishlab chiqarish
         holati» — xuddi shu sonlar); «Oylik daromad» = «Daromad»; «Eng faol ustalar» = «Usta reytingi»; kam material bir necha
         joyda; Hisobotlarda «Sotuv» ≈ «Moliya», «Mahsulotlar» ⊃ «Ishlab chiqarish», «Eng ko'p …» tablari = kartalar.
         QAROR: Bosh sahifa — BUGUNGI holat va ogohlantirishlar; Dashboard — ish jarayoni; Hisobotlar — oylik tahlil; takror —
         bittadan.
  G2-17  Loyihalar va Buyurtmalar bog'lanmagan: loyihadagi buyurtma qatori Buyurtmalar sahifasini HECH NARSA tanlanmagan holda
         ochardi, summa — jami (chegirmasiz), «+ Yangi buyurtma» faqat bo'sh loyihada, «Hujjatlarni ko'rish» hujjat emas.
         QAROR: Loyiha — mijoz kartasi (pul xulosasi, buyurtmalar), Buyurtmalar — ish joyi.
  G1-24  «Tezkor kirish» — chap menyuni takrorlovchi 9 karta (qat'iy «Kvars va marmar qoplama»). QAROR (01.10): 3–4 asosiy amal,
         har kimga faqat ruxsati borlari.
BO'LIMLAR: H (Bosh sahifa), D (Dashboard), R (Hisobotlar), P (Loyihalar), O (Buyurtmalar — «?order=ID», «?yangi=1»),
Q (Qaytarishlar «?brak=1»), T (sahifa skriptlari). JS xatti-harakati — tools/test_d124_ui.js.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16; `TENANT_FILTER=1` bilan ham.
ISHLATISH: python3 tools/test_d124.py
"""
import os
import re
import sys
import shutil
import tempfile
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "d124_test"
_T = tempfile.mkdtemp(prefix="d124_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'd124_test.db')}"

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

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
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t124_admin", "Parol123!", UserRole.ADMIN, "T124 Admin", company_id=1)
s.commit()
s.close()


def mijoz(u):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": u, "password": "Parol123!"}, follow_redirects=False)
    return c, r.status_code


CA, _sa = mijoz("t124_admin")
if _sa != 302:
    print("LOGIN BO'LMADI", _sa)
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)
H = {"Accept": "text/html"}


def sahifa(c, yol):
    r = c.get(yol, headers=H, follow_redirects=False)
    return r.status_code, r.text if r.status_code == 200 else ""


# maxsus rollar (ruxsatga qarab ko'rinish)
_rollar = {}
for _nom, _rx in (("Faqat buyurtma yozuvchi", {"dashboard": ["korish"], "buyurtma": ["korish", "yaratish"]}),
                  ("Faqat bosh sahifa", {"dashboard": ["korish"]}),
                  ("Loyiha ko'ruvchi", {"loyiha": ["korish"], "buyurtma": ["korish"]})):
    _rollar[_nom] = (js(CA.post("/api/rollar", json={"nom": _nom, "ruxsatlar": _rx})) or {}).get("id")
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    for _i, (_nom, _rid) in enumerate(_rollar.items()):
        if _rid:
            auth.create_user(s, f"t124_r{_i}", "Parol123!", UserRole.MANAGER, _nom, company_id=1, rol_id=_rid)
s.commit()
s.close()
KL = {_nom: mijoz(f"t124_r{_i}")[0] for _i, _nom in enumerate(_rollar)}

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H — Bosh sahifa: bugungi holat, ogohlantirishlar, tezkor amallar (G1-09, G1-24)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_kh, BOSH = sahifa(CA, "/")
_yoq = [x for x in ('id="statusChart"', 'id="revenueChart"', 'id="leaderboard"', "chart.umd.min.js", "Tezkor kirish",
                    "Kvars va marmar qoplama", "Eng faol ustalar", "Oylik daromad", "onmouseout=") if x in BOSH]
check("H1 Bosh sahifa: 200; takror bloklar YO'Q (doira, «Oylik daromad», «Eng faol ustalar», Chart.js, 9 kartali «Tezkor kirish», "
      "qat'iy «Kvars va marmar qoplama»)", _kh == 200 and not _yoq, (_kh, _yoq))
check("H2 qoladi / qo'shildi: KPI (k-orders, k-active, k-ready, k-masters, k-debt), «Bugungi vazifalar» (Dashboard dan), «So'nggi "
      "buyurtmalar», «Kam qolgan xomashyo»; izoh «Bugungi holat, ogohlantirishlar va tezkor amallar»",
      all(f'id="{x}"' in BOSH for x in ("k-orders", "k-active", "k-ready", "k-masters", "k-debt", "tasksCard", "tasksList",
                                        "recentOrders", "lowStock"))
      and "<h3>Bugungi vazifalar</h3>" in BOSH and "fetch('/api/dashboard/today-tasks')" in BOSH
      and "Bugungi holat, ogohlantirishlar va tezkor amallar" in BOSH)
_amallar = re.findall(r'<a class="tezkor-amal" href="([^"]+)">', BOSH)
check("H3 «Tezkor amallar» (Admin) — 4 ta: «Yangi buyurtma» (/orders?yangi=1), «To'lov qabul qilish» (/debts), «Kirim qilish» "
      "(/suppliers/receive), «Brak yozish» (/returns?brak=1)",
      _amallar == ["/orders?yangi=1", "/debts", "/suppliers/receive", "/returns?brak=1"] and "<h3>Tezkor amallar</h3>" in BOSH
      and all(x in BOSH for x in ("<b>Yangi buyurtma</b>", "<b>To'lov qabul qilish</b>", "<b>Kirim qilish</b>", "<b>Brak yozish</b>")),
      _amallar)
_k1, _h1 = sahifa(KL["Faqat buyurtma yozuvchi"], "/")
_k2, _h2 = sahifa(KL["Faqat bosh sahifa"], "/")
check("H4 ruxsatga qarab: faqat «Buyurtmalar: Yaratish» — bitta amal (Yangi buyurtma); hech qaysi amalga ruxsat yo'q — blok YO'Q",
      _k1 == 200 and re.findall(r'<a class="tezkor-amal" href="([^"]+)">', _h1) == ["/orders?yangi=1"]
      and _k2 == 200 and 'id="tezkorAmallar"' not in _h2 and "<h3>Tezkor amallar</h3>" not in _h2,
      (_k1, re.findall(r'<a class="tezkor-amal" href="([^"]+)">', _h1), _k2))
check("H5 «So'nggi buyurtmalar» qatori AYNAN shu buyurtmani ochadi (/orders?order=ID)",
      '<a class="list-row" href="/orders?order=${Number(o.id)}"' in BOSH)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D — Dashboard: ish jarayoni (G1-09)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_kd, DASH = sahifa(CA, "/dashboard")
_DASH_IZOHSIZ = re.sub(r"<!--.*?-->", "", DASH, flags=re.S)   # HTML izohidagi tarix matni hisobga olinmaydi
_dyoq = [x for x in ("tasksList", "stageList", "warnList", "revenueOnlyChart", "yonKarta", "pg-today-split", "prodTypeChart",
                     "mf-sof-foyda", "mf-expense-lines", "topProducts", "cashFlow", "bottomGrid")
         if f'id="{x}"' in DASH or f"getElementById('{x}')" in DASH]
_fyoq = [f for f in ("loadTasks", "loadTopProducts", "loadCashFlow", "buildStageList", "buildWarnList", "loadMonthlyFinance",
                     "buildRevenueOnlyChart", "buildProdTypeChart") if re.search(r"\b" + f + r"\s*\(", DASH)]
check("D1 Dashboard: 200; olib tashlangan (takror): «Bugungi vazifalar», «Ishlab chiqarish holati», «Ombor ogohlantirishlari», "
      "«Tezkor amallar», «💰 Daromad», yo'nalishlar, «Bu oy moliyaviy holat», «Eng ko'p sotilgan», «Pul oqimi» — elementi ham, "
      "funksiyasi ham YO'Q", _kd == 200 and not _dyoq and not _fyoq and "Ombor ogohlantirishlari" not in _DASH_IZOHSIZ
      and "Bu oy moliyaviy holat" not in _DASH_IZOHSIZ and "Bugungi vazifalar" not in _DASH_IZOHSIZ
      and "Tezkor amallar" not in _DASH_IZOHSIZ, (_kd, _dyoq, _fyoq))
check("D2 qoladi: bugungi KPI (t-*), «Buyurtmalar holati» doirasi AFSONA bilan (statusLegend), «Ishlab chiqarish» davrlari, "
      "«Buyurtmalar soni», pul qatori, qarz, yetkazish, usta reytingi",
      all(f'id="{x}"' in DASH for x in ("t-revenue", "t-active", "statusChart", "statusLegend", "prodPeriods", "ordersCountChart",
                                        "finGrid", "d-total", "dl-full", "masterList"))
      and "const leg=document.getElementById('statusLegend');" in DASH and "buildStatusChart(c.statuses)" in DASH)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R — Hisobotlar: oylik tahlil, takror jadvallar yo'q (G1-09)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_kr, REP = sahifa(CA, "/reports")
_tablar = re.findall(r'<button class="bi-tab[^"]*" data-r="([\w-]+)"', REP)
check("R1 jadval tablari: Ombor, Mahsulotlar, Ustalar / KPI, Moliya (Sotuv, Ishlab chiqarish, Eng ko'p sotilgan / xomashyo — "
      "YO'Q, ularning yuklovchilari ham)",
      _kr == 200 and _tablar == ["inventory", "products", "masters", "finance"]
      and not any(re.search(r"\b" + f + r"\s*\(", REP) for f in ("loadSalesReport", "loadProductionReport", "loadTopProducts",
                                                                 "loadTopMaterials")), (_kr, _tablar))
_fr = re.search(r"async function loadFinanceReport\(\) \{[\s\S]*?\n\}", REP)
check("R2 «Moliya» jadvalida «Buyurtmalar soni» ustuni (ilgari alohida «Sotuv» jadvalida); «Bugungi xulosa» → «Oy xulosasi»",
      _fr and '["Buyurtmalar soni", h => h.buyurtmalar_soni + \' ta\']' in _fr.group(0)
      and '<div class="bi-summary-title">Oy xulosasi</div>' in REP and "Bugungi xulosa</div>" not in REP)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("P — Loyihalar: mijoz kartasi (G2-17)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_kp, PRJ = sahifa(CA, "/projects")
check("P1 sarlavha izohi «Mijoz va loyiha kartasi — pul xulosasi va buyurtmalari …»; tugmalar «Buyurtmalari», «Mahsulotlar "
      "ro'yxati» (eski «Buyurtmaga o'tish» / «Hujjatlarni ko'rish» YO'Q)",
      _kp == 200 and "Mijoz va loyiha kartasi — pul xulosasi va buyurtmalari" in PRJ
      and "Korxonaning barcha buyurtmalarini boshqaruvchi markaziy modul" not in PRJ
      and "</i> Buyurtmalari</button>" in PRJ and "</i> Mahsulotlar ro'yxati</button>" in PRJ
      and "Buyurtmaga o'tish" not in PRJ and "Hujjatlarni ko'rish" not in PRJ, _kp)
_ro = re.search(r"async function renderOrders\(d\) \{[\s\S]*?\n\}", PRJ)
_ro = _ro.group(0) if _ro else ""
check("P2 buyurtma qatori → /orders?order=ID (aynan shu buyurtma), summa — KELISHILGAN (loyihaBuyurtmaSummasi), «+ Yangi buyurtma» "
      "buyurtmasi bor loyihada ham (ruxsatga qarab)",
      "onclick=\"window.location.href='/orders?order=${Number(o.id)}'\"" in _ro and "fmt(loyihaBuyurtmaSummasi(o))" in _ro
      and "fmt(o.total_amount)" not in _ro and "(yangiTugma ? `<div style=\"display:flex;justify-content:flex-end" in _ro
      and "const BUYURTMA_YARATADI = true;" in PRJ, _ro[:300])
_k3, _h3 = sahifa(KL["Loyiha ko'ruvchi"], "/projects")
check("P3 «Buyurtmalar: Yaratish» ruxsati yo'q — «+ Yangi buyurtma» chizilmaydi (BUYURTMA_YARATADI = false)",
      _k3 == 200 and "const BUYURTMA_YARATADI = false;" in _h3, _k3)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("O / Q — Buyurtmalar «?order=ID» / «?yangi=1», Qaytarishlar «?brak=1»")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_ko, ORD = sahifa(CA, "/orders?order=1")
_ko2, _ = sahifa(CA, "/orders?show_all=true&order=99999")
check("O1 /orders?order=ID va ?show_all=true&order=ID — 200 (parametr sahifada o'qiladi)", _ko == 200 and _ko2 == 200, (_ko, _ko2))
check("O2 orders.html: buyurtmaniParamdanOch (guruhni ochadi, tanlaydi; ro'yxatda yo'q — «Barchasi» bilan qayta; topilmasa — "
      "xabar), «?yangi=1» — yangi buyurtma formasi; qoralama tiklashdan OLDIN",
      "function buyurtmaniParamdanOch(params)" in ORD and "if (buyurtmaniParamdanOch(params)) return;" in ORD
      and "window.location.replace('/orders?show_all=true&order=' + id)" in ORD and "params.get('yangi') === '1'" in ORD
      and ORD.find("if (buyurtmaniParamdanOch(params)) return;") < ORD.find("localStorage.getItem(ORDER_DRAFT_LS_KEY)"))
_kq, RET = sahifa(CA, "/returns?brak=1")
check("Q1 /returns?brak=1 — 200, sahifa bitta brak oynasini ochadi (p.get('brak') === '1' → showBrakModal())",
      _kq == 200 and "if (p.get('brak') !== '1') return;" in RET and "showBrakModal()" in RET, _kq)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T — sahifa skriptlari")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_NODE = shutil.which("node")


def skriptlar(html):
    return [m.group("k") for m in re.finditer(r"<script(?P<a>[^>]*)>(?P<k>.*?)</script>", html, re.S)
            if "src=" not in m.group("a") and not re.search(r'type="(?!text/javascript|module)', m.group("a"))]


def node_check(kod, nom):
    f = os.path.join(_T, nom)
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(kod)
    k = subprocess.run([_NODE, "--check", f], capture_output=True, text=True)
    return (k.stderr or "")[:400] if k.returncode else ""


for _yol, _html in (("/", BOSH), ("/dashboard", DASH), ("/reports", REP), ("/projects", PRJ), ("/orders", ORD), ("/returns", RET)):
    if not _NODE or not _html:
        check(f"T1 {_yol} — sahifa skriptlari", False, "node yo'q" if not _NODE else "sahifa yo'q")
        continue
    _sk = skriptlar(_html)
    _xato = [x for x in (node_check(k, f"t{i}.js") for i, k in enumerate(_sk)) if x]
    _el = {}
    for _k in _sk:
        for _m in re.finditer(r"^(?:let|const)\s+([A-Za-z_$][\w$]*)\s*=", _k, re.M):
            _el[_m.group(1)] = _el.get(_m.group(1), 0) + 1
    _takror = [n for n, c in _el.items() if c > 1]
    check(f"T1 {_yol} — ichki skriptlar sintaksisi toza (node --check), yuqori darajadagi let / const takrorlanmagan",
          not _xato and not _takror, (_xato, _takror))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  - " + f)
sys.exit(1 if FAIL else 0)
