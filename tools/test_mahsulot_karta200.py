#!/usr/bin/env python3
"""
test_mahsulot_karta200.py — kech154 (zip 200 «Mayda qoldiqlar — Mahsulotlar kartochkasi»; egasi TANLOVI 22.10 00:3x): «Tayyor mahsulotlar»
sahifasidagi «Mahsulotlar» kartochkasi QAYTGAN mahsulotlarni ham sanaydi. HAQIQIY Chromium, HAQIQIY lokal server (uvicorn, test bazasi).

NIMA UCHUN KERAK (O'LCHANGAN — egasining asosiy sayt skrinshoti 22.10 00:18): omborda 2 ta qaytgan mahsulot (14 m va 4 m), ro'yxatda
«QAYTGAN MAHSULOTLAR (2)», «Omborda 18 m» — lekin «Mahsulotlar: 0 ta, 0 partiya»: karta faqat ishlab chiqarilgan partiyalarni sanardi.
TEKSHIRUVLAR:
  M1  ishlab chiqarilgan 2 mahsulot (biri 2 partiyali) + 2 qaytgan: «4 ta», izoh «3 partiya · 2 qaytgan» (asl kodda «2 ta», «3 partiya»).
  M2  karta = ro'yxat: ishlab chiqarilgan guruhlar soni + «Qaytgan mahsulotlar» bo'limidagi qatorlar soni.
  M3  faqat qaytganlar (asosiy saytdagi holat): «2 ta», «0 partiya · 2 qaytgan» (asl kodda «0 ta», «0 partiya»).
  M4  faqat ishlab chiqarilganlar: «2 ta», «3 partiya» — qaytgan bo'lmasa ko'rinish AVVALGIDEK (izohda « · 0 qaytgan» yo'q).
  M5  «Kam qolganlar», «Omborda» o'zgarmagan; sahifada JS xatosi yo'q.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 199) qarshi QULAMAYDI — M1 va M3 yiqiladi.
TALAB: Python `playwright` + Chromium.
ISHLATISH: python3 tools/test_mahsulot_karta200.py
"""
import os
import io
import sys
import glob
import time
import socket
import tempfile
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = os.environ.get("K200_PG_BAZA") or "mahsulot_karta200_test"
_T = tempfile.mkdtemp(prefix="k200_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k200.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, FinishedProduct, StockSource, ProductionStatus   # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"


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
        print(f"  ✗ {label}   {str(detail)[:700]}")


def section(t):
    print(f"\n--- {t} ---")


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik: ishlab chiqarilgan «K200 Karniz» (2 partiya) va «K200 Profil» (1 partiya), qaytgan «K200 Qaytgan A» / «B»
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k200_admin", PAROL, UserRole.ADMIN, "K200 Admin", company_id=1)


def tm(nom, miqdor, manba=StockSource.PRODUCED, kenglik=20, qalinlik=10, narx=30000):
    fp = FinishedProduct(company_id=1, name=nom, category="profil", width=kenglik, thickness=qalinlik, quantity=miqdor,
                         produced_quantity=miqdor if manba == StockSource.PRODUCED else 0, unit="metr", unit_price=narx,
                         cost_price=miqdor * 10000, source=manba, reserved_quantity=0, production_status=ProductionStatus.READY,
                         is_coated=False)
    s.add(fp)
    s.flush()
    return fp.id


tm("K200 Karniz", 5)
tm("K200 Karniz", 6)
tm("K200 Profil", 3, kenglik=15, qalinlik=5)
tm("K200 Qaytgan A", 4, manba=StockSource.RETURNED, kenglik=15, qalinlik=3)
tm("K200 Qaytgan B", 2, manba=StockSource.RETURNED, kenglik=17, qalinlik=15)
s.commit()
s.close()

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Server va brauzer
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
B = f"http://127.0.0.1:{port}"
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
check("T0 lokal server va Chromium", bool(server.started and br), _pw_x)
JS_XATO = []


def sahifa():
    import re
    ctx = br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
    pg = ctx.new_page()
    pg.set_default_timeout(15000)
    pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
    pg.goto(B + "/login")
    pg.fill("input[name=username]", "k200_admin")
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    pg.goto(B + "/finished", wait_until="networkidle")
    pg.wait_for_timeout(500)
    return ctx, pg


def karta(pg):
    return pg.evaluate("""() => ({
      tur: (document.getElementById('k-types') || {}).textContent || null,
      partiya: (document.getElementById('k-partiya') || {}).textContent || null,
      kam: (document.getElementById('k-low') || {}).textContent || null,
      omborda: (document.getElementById('k-total-qty') || {}).textContent || null })""")


def qayta_hisobla(pg, filtr_js):
    """`fpItems` ni (sahifaning o'z ro'yxati) filtrlab, kartalarni sahifaning O'Z funksiyasi bilan qayta hisoblaydi."""
    pg.evaluate(f"async () => {{ fpItems = fpItems.filter({filtr_js}); await loadStats(); }}")
    pg.wait_for_timeout(300)
    return karta(pg)


section("M — «Mahsulotlar» kartochkasi qaytgan mahsulotlarni ham sanaydi")
if br:
    ctx, pg = sahifa()
    k1 = karta(pg)
    check("M1 ishlab chiqarilgan 2 mahsulot (biri 2 partiyali) + 2 qaytgan: «4 ta», izoh «3 partiya · 2 qaytgan»",
          k1.get("tur") == "4 ta" and k1.get("partiya") == "3 partiya · 2 qaytgan", k1)
    rl = pg.evaluate("""() => {
      const guruhlar = fpGuruhla(fpItems.filter(i => i.source === 'produced')).length;
      const qaytgan = fpItems.filter(i => i.source === 'returned').length;
      const sahifada = Array.from(document.querySelectorAll('#fpList *')).filter(e => e.children.length === 0
        && /K200 Qaytgan/.test(e.textContent || '')).length;
      return {guruhlar, qaytgan, sahifada, matn: (document.getElementById('fpList') || {}).textContent || ''};
    }""")
    check("M2 karta = ro'yxat: ishlab chiqarilgan guruhlar (2) + ro'yxatdagi qaytgan qatorlar (2) = 4; qaytganlar ro'yxatda ko'rinadi",
          rl.get("guruhlar") == 2 and rl.get("qaytgan") == 2 and "K200 Qaytgan A" in rl.get("matn", "")
          and "K200 Qaytgan B" in rl.get("matn", "") and k1.get("tur") == f"{rl.get('guruhlar', 0) + rl.get('qaytgan', 0)} ta",
          {k: v for k, v in rl.items() if k != "matn"})
    check("M5 «Kam qolganlar» o'zgarmagan («0 ta» — qaytganlarga «kam» chegarasi yo'q), «Omborda» — serverdan (20 m)",
          k1.get("kam") == "0 ta" and "20 m" in str(k1.get("omborda")), k1)
    ctx.close()
    ctx, pg = sahifa()
    k3 = qayta_hisobla(pg, "i => i.source === 'returned'")
    check("M3 faqat qaytgan mahsulotlar (asosiy saytdagi holat): «2 ta», izoh «0 partiya · 2 qaytgan» (ilgari «0 ta», «0 partiya»)",
          k3.get("tur") == "2 ta" and k3.get("partiya") == "0 partiya · 2 qaytgan", k3)
    ctx.close()
    ctx, pg = sahifa()
    k4 = qayta_hisobla(pg, "i => i.source === 'produced'")
    check("M4 faqat ishlab chiqarilganlar: «2 ta», izoh «3 partiya» — qaytgan bo'lmasa ko'rinish AVVALGIDEK",
          k4.get("tur") == "2 ta" and k4.get("partiya") == "3 partiya", k4)
    ctx.close()
check("M6 sahifada JS xatosi yo'q", not JS_XATO, JS_XATO[:3])

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
