#!/usr/bin/env python3
"""
test_d123.py — kech118 D BOSQICHI 3-qism (zip 123): BRAK — BITTA OYNA, «PENOPLAST DETAL» / «RETSEPT BO'YICHA», «LOY RETSEPTLARI» /
«MAHSULOT TARKIBI» (egasi QARORLARI kech118 11:40 — G5-04, G5-01, G4-22; tugmali, QAYTA SO'RALMAYDI).

NIMA UCHUN KERAK (audit topilmalari)
  G5-04  Brak uch xil oynada yozilardi: Qaytarishlar «Brak yozish» (loyiha bo'yicha), «Yangi qaytarish» → «Brak» (buyurtma bo'yicha,
         boshqa oyna) va Tayyor mahsulotlar «−» (ikki rejim, yana boshqa oyna). QAROR: BITTA «Brak yozish» oynasi — avval «brak
         qayerda chiqdi» (buyurtma detalida / omborda turgan tayyor mahsulotda / ishlab chiqarishda); «Yangi qaytarish» — faqat
         mijozdan qaytgan BUTUN mahsulot. Oyna — templates/_brak_oyna.html (Qaytarishlar va Tayyor mahsulotlar ulaydi).
  G5-01  Tayyor mahsulotlardagi «+ Ishlab chiqarish» eski penoplast oynasini ochardi, retsept bo'yicha ishlab chiqarish — boshqa
         sahifada. QAROR: ikkalasi qoladi, nomi ajratiladi — «Penoplast detal» va yonida «Retsept bo'yicha» havola.
  G4-22  Menyudagi «Retseptlar» (loy aralashmasi) va Ishlab chiqarishdagi «Retsept» (mahsulot tarkibi) bir xil nomlanardi. QAROR:
         «Loy retseptlari» (menyu, sahifa) va «Mahsulot tarkibi» (Ishlab chiqarish ichida).
BO'LIMLAR: B (bitta brak oynasi — sahifalarda, ruxsatga qarab), Q («Yangi qaytarish» — faqat butun), N (nomlar), T (sahifa
skriptlari: sintaksis, bir sahifada takror e'lon yo'q). JS xatti-harakati — tools/test_d123_ui.js.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16; `TENANT_FILTER=1` bilan ham.
ISHLATISH: python3 tools/test_d123.py
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
PG_BAZA = "d123_test"
_T = tempfile.mkdtemp(prefix="d123_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'd123_test.db')}"

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


def fayl(nom):
    try:
        with open(os.path.join(ROOT, nom), encoding="utf-8") as f:
            return f.read()
    except Exception:                      # noqa: BLE001
        return ""


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return None


s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t123_admin", "Parol123!", UserRole.ADMIN, "T123 Admin", company_id=1)
s.commit()
s.close()


def mijoz(u):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": u, "password": "Parol123!"}, follow_redirects=False)
    return c, r.status_code


CA, _sa = mijoz("t123_admin")
if _sa != 302:
    print("LOGIN BO'LMADI", _sa)
    print("\nNATIJA:  o'tdi = 0   yiqildi = 1   jami = 1")
    sys.exit(1)
H = {"Accept": "text/html"}


def sahifa(c, yol):
    r = c.get(yol, headers=H, follow_redirects=False)
    return r.status_code, r.text if r.status_code == 200 else ""


def manbalar(html):
    return sorted(re.findall(r'name="brak-manba" value="(\w+)"', html))


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B — bitta «Brak yozish» oynasi (G5-04)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_kr, RET = sahifa(CA, "/returns")
_kf, FIN = sahifa(CA, "/finished")
check("B1 Qaytarishlar (Admin): 200, oyna BITTA (`id=\"brakModal\"` 1 marta), «Brak qayerda chiqdi?» — uch yo'l (buyurtma, ombor, "
      "ishlab), eski Tayyor mahsulotlar oynasi (`lossModal`) YO'Q, «Brak yozish» tugmasi bor",
      _kr == 200 and RET.count('id="brakModal"') == 1 and manbalar(RET) == ["buyurtma", "ishlab", "ombor"]
      and "lossModal" not in RET and "Brak qayerda chiqdi?" in RET and 'onclick="showBrakModal()"' in RET,
      (_kr, RET.count('id="brakModal"'), manbalar(RET), "lossModal" in RET))
check("B2 Tayyor mahsulotlar (Admin): 200, AYNAN SHU oyna (1 marta) — «−» dan ochiladi; yo'llar: ombor, ishlab (buyurtma detali — "
      "Qaytarishlarda; bu sahifada loyiha ro'yxati yo'q); eski `lossModal` YO'Q",
      _kf == 200 and FIN.count('id="brakModal"') == 1 and manbalar(FIN) == ["ishlab", "ombor"] and "lossModal" not in FIN
      and "Brak qayerda chiqdi?" in FIN and "function openLossModal(" in FIN,
      (_kf, FIN.count('id="brakModal"'), manbalar(FIN)))
_oyna = fayl("templates/_brak_oyna.html")
_maydon = ["brak-cause", "brak-stage", "brak-worker", "brak-notes"]
check("B3 oynada umumiy maydonlar (hamma yo'lda bir xil): sabab (majburiy «*», ro'yxatdan), bosqich, javobgar, izoh — tartib "
      "shunday; sabab va bosqich ro'yxatlari serverdagi ro'yxatlar bilan AYNAN",
      all(f'id="{k}"' in RET for k in _maydon)
      and [RET.find(f'id="{k}"') for k in _maydon] == sorted(RET.find(f'id="{k}"') for k in _maydon)
      and "Nima sababdan brak bo'ldi? <span" in RET
      and all(f'<option value="{k}">' in RET for k in __import__("crud").BRAK_SABABLARI)
      and all(f'<option value="{k}">' in RET for k in __import__("crud").BRAK_BOSQICHLARI),
      [RET.find(f'id="{k}"') for k in _maydon])
_eski = [x for x in ("id=\"lossModal\"", "loss-cause", "loss-stage", "loss-worker", "loss-reason", "loss-submit-btn")
         if x in fayl("templates/finished.html") + fayl("templates/returns.html") + _oyna]
check("B4 eski ikkinchi oyna va uning maydonlari (loss-cause / loss-stage / loss-worker / loss-reason) — hech qayerda YO'Q; "
      "returns.html va finished.html oynani ulaydi (`{% include \"_brak_oyna.html\" %}`)",
      not _eski and fayl("templates/returns.html").count('{% include "_brak_oyna.html" %}') == 1
      and fayl("templates/finished.html").count('{% include "_brak_oyna.html" %}') == 1, _eski)

# ruxsatga qarab: maxsus rollar
_rollar = {}
for _nom, _rx in (("Faqat qaytarish yozuvchi", {"qaytarish": ["korish", "yaratish"], "loyiha": ["korish"]}),
                  ("Faqat brak yozuvchi", {"qaytarish": ["korish"], "brak": ["yaratish"], "tayyor": ["korish"], "sotuv": ["korish"]}),
                  ("Faqat ko'ruvchi", {"qaytarish": ["korish"]})):
    _r = CA.post("/api/rollar", json={"nom": _nom, "ruxsatlar": _rx})
    _rollar[_nom] = (js(_r) or {}).get("id")
check("B5 sinov rollari yaratildi (3 ta)", all(_rollar.values()), _rollar)
_kl = {}
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    for _i, (_nom, _rid) in enumerate(_rollar.items()):
        if _rid:
            auth.create_user(s, f"t123_r{_i}", "Parol123!", UserRole.MANAGER, _nom, company_id=1, rol_id=_rid)
s.commit()
s.close()
for _i, _nom in enumerate(_rollar):
    _kl[_nom] = mijoz(f"t123_r{_i}")[0]
_k1, _h1 = sahifa(_kl["Faqat qaytarish yozuvchi"], "/returns")
_k2, _h2 = sahifa(_kl["Faqat brak yozuvchi"], "/returns")
_k3, _h3 = sahifa(_kl["Faqat ko'ruvchi"], "/returns")
check("B6 «Qaytarishlar: Yaratish» (brak ruxsatisiz) — faqat «Buyurtma detalida» yo'li",
      _k1 == 200 and manbalar(_h1) == ["buyurtma"] and 'onclick="showBrakModal()"' in _h1, (_k1, manbalar(_h1)))
check("B7 «Brak: Yaratish» (qaytarish yaratmaydi) — faqat «Omborda turgan» va «Ishlab chiqarishda»; loyiha paneli YO'Q",
      _k2 == 200 and manbalar(_h2) == ["ishlab", "ombor"] and 'id="brak-panel-project"' not in _h2, (_k2, manbalar(_h2)))
check("B8 ikkalasi ham yo'q — «Brak yozish» tugmasi YO'Q, oynada «Brak yozishga ruxsatingiz yo'q»",
      _k3 == 200 and 'onclick="showBrakModal()"' not in _h3 and manbalar(_h3) == [] and "Brak yozishga ruxsatingiz yo'q" in _h3,
      (_k3, manbalar(_h3)))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("Q — «Yangi qaytarish» — faqat mijozdan qaytgan BUTUN mahsulot")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_add = RET[RET.find('id="addModal"'):RET.find('id="brakModal"')]
check("Q1 «Yangi qaytarish» oynasida «Brak» varianti va brak maydonlari (f-brak-*, qoplama savoli) YO'Q; yashirin «Ortiqcha»; "
      "maslahat: brak — «Brak yozish»",
      _add and 'value="Brak"' not in _add and "f-brak-" not in _add and "coating-applied-wrap" not in _add
      and 'name="f-reason" value="Ortiqcha" checked hidden' in _add and "Brak bo'lsa — «Brak yozish» tugmasi" in _add,
      [x for x in ('value="Brak"', "f-brak-", "coating-applied-wrap") if x in _add])
_sr = re.search(r"async function saveReturn\(\)\{[\s\S]*?\n\}", RET)
check("Q2 saveReturn: brak tanasi YO'Q, qoplama — false", _sr and "brakTana" not in _sr.group(0)
      and "brak_sabab" not in _sr.group(0) and "coating_applied: false" in _sr.group(0), _sr.group(0)[:300] if _sr else None)
check("Q3 sahifa izohi: «Mijozdan qaytgan butun mahsulot va brak (yo'qotish hisobi)»",
      "Mijozdan qaytgan butun mahsulot va brak (yo'qotish hisobi)" in RET)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("N — nomlar: «Penoplast detal» / «Retsept bo'yicha» (G5-01), «Loy retseptlari» / «Mahsulot tarkibi» (G4-22)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
check("N1 Tayyor mahsulotlar: «+ Penoplast detal» (eski oyna — openProduceModal), yonida «Retsept bo'yicha →» (/production); "
      "oyna sarlavhasi «Penoplast detal ishlab chiqarish»; eski «+ Ishlab chiqarish» tugmasi YO'Q",
      'onclick="openProduceModal()"' in FIN and "> Penoplast detal</button>" in FIN
      and re.search(r'<a class="btn btn-outline" id="retseptBoyichaHavola" href="/production"[^>]*>.*Retsept bo\'yicha →</a>', FIN)
      and "🏭 Penoplast detal ishlab chiqarish" in FIN and "> Ishlab chiqarish</button>" not in FIN
      and "Tayyor mahsulot ishlab chiqarish</div>" not in FIN)
check("N2 bo'sh ombor maslahati: «+ Penoplast detal» va «Retsept bo'yicha» (eski «+ Ishlab chiqarish tugmasini bosing» YO'Q)",
      "Penoplast detal — yuqoridagi <b>+ Penoplast detal</b> tugmasi" in FIN and "Ishlab chiqarish</b> tugmasini bosing" not in FIN)
_k4, _h4 = sahifa(_kl["Faqat brak yozuvchi"], "/finished")
check("N3 «Mahsulot turlari: Ko'rish» ruxsati yo'q — «Retsept bo'yicha» havolasi YO'Q (sahifa ochilmasdi)",
      _k4 == 200 and "retseptBoyichaHavola" not in _h4 and "> Penoplast detal</button>" in _h4, _k4)
_kb, BOSH = sahifa(CA, "/")
check("N4 menyu: «Loy retseptlari» (eski «Retseptlar» YO'Q)",
      _kb == 200 and '<span class="n-txt">Loy retseptlari</span>' in BOSH and '<span class="n-txt">Retseptlar</span>' not in BOSH)
_krc, REC = sahifa(CA, "/recipes")
check("N5 Loy retseptlari sahifasi: sarlavha, «Yangi loy retsepti», oyna «+ Yangi loy retsepti» / «Loy retseptini tahrirlash»; "
      "mahsulot tarkibi — «Ishlab chiqarish» bo'limida (izoh)",
      _krc == 200 and "<title>Loy retseptlari — PenoDecorPro ERP</title>" in REC and "> Yangi loy retsepti</button>" in REC
      and '<div class="page-title">Loy retseptlari</div>' in REC
      and "+ Yangi loy retsepti</div>" in REC and "Loy retseptini tahrirlash</div>" in REC
      and "tarkibi — «Ishlab chiqarish» bo'limida" in REC, _krc)
_kp, PRD = sahifa(CA, "/production")
_eski_p = [x for x in ("+ Retsept</button>", ">Yangi retsept</div>", ">Retsept nomi</label>", '<label for="po-f-bom">Retsept</label>',
                       "<th>Retseptlar va 1 birlik", "Hali retsept yo", "Retsept bo'yicha</th>") if x in PRD]
check("N6 Ishlab chiqarish: «Mahsulot tarkibi» — jadval sarlavhasi, «+ Tarkib», «Yangi mahsulot tarkibi», «Tarkib nomi», ishlab "
      "chiqarish formasida «Mahsulot tarkibi»; eski «Retsept» yozuvlari YO'Q",
      _kp == 200 and "<th>Mahsulot tarkibi va 1 birlik taxminiy tannarxi</th>" in PRD and ">+ Tarkib</button>" in PRD
      and ">Yangi mahsulot tarkibi</div>" in PRD and ">Tarkib nomi</label>" in PRD
      and '<label for="po-f-bom">Mahsulot tarkibi</label>' in PRD and not _eski_p, (_kp, _eski_p))
_rd = CA.delete("/api/production/boms/987654")
check("N7 server: yo'q tarkib — 404 «Mahsulot tarkibi topilmadi»",
      _rd.status_code == 404 and (js(_rd) or {}).get("detail") == "Mahsulot tarkibi topilmadi", (_rd.status_code, _rd.text[:200]))
_pr = fayl("production_routes.py") + fayl("production_service.py")
check("N8 server xabarlari: «nomli tarkib allaqachon bor», «Mahsulot tarkibi surati topilmadi» (eski «Retsept topilmadi» — ishlab "
      "chiqarishda YO'Q)",
      "nomli tarkib allaqachon bor" in _pr and "Mahsulot tarkibi surati topilmadi" in _pr and '"Retsept topilmadi"' not in _pr)

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


for _yol, _html in (("/returns", RET), ("/finished", FIN), ("/production", PRD), ("/recipes", REC)):
    if not _NODE or not _html:
        check(f"T1 {_yol} — sahifa skriptlari", False, "node yo'q" if not _NODE else "sahifa yo'q")
        continue
    _sk = skriptlar(_html)
    _xato = [x for x in (node_check(k, f"t{i}.js") for i, k in enumerate(_sk)) if x]
    # bir sahifadagi skriptlar BITTA global muhitda: yuqori darajadagi `let` / `const` takror e'loni — ikkinchi skript BUTUNLAY
    # ishlamaydi (SyntaxError: oyna ulanganda sahifaning eski e'lonlari qolib ketsa)
    _el = {}
    for _k in _sk:
        for _m in re.finditer(r"^(?:let|const)\s+([A-Za-z_$][\w$]*)\s*=", _k, re.M):
            _el[_m.group(1)] = _el.get(_m.group(1), 0) + 1
    _takror = [n for n, c in _el.items() if c > 1]
    check(f"T1 {_yol} — har ichki skript sintaksisi toza (node --check), yuqori darajadagi let / const takror e'lon qilinmagan",
          not _xato and not _takror, (_xato, _takror))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  - " + f)
sys.exit(1 if FAIL else 0)
