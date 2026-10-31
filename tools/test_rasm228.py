#!/usr/bin/env python3
"""
test_rasm228.py — kech163 (zip 228 «rasm yo'qolmasin»; review224 PAST «Rasm yuklash — qayd»).

NIMA UCHUN KERAK
  (1) Taklif saqlanganda formada tanlangan detal rasmi hech qayerga yuborilmasdi va xodimga hech narsa aytilmasdi (taklif rasm saqlamaydi).
  (2) Yangi buyurtma javobi yo'qolib «💾 Buyurtmani saqlash» qayta bosilsa (`X-Takror`) rasmlar yuklanmasdi — jimgina yo'qolardi.
QOIDA: taklif natija oynasida «📷 N ta rasm taklifga saqlanmaydi — …»; `X-Takror` javobida rasm hali rasmi yo'q detalga yuklanadi.
BO'LIMLAR: S — manba. T — taklif (haqiqiy Chromium, haqiqiy server): rasm bilan — eslatma, rasm so'rovi yo'q, taklif saqlandi; rasmsiz —
  eslatma yo'q. Q — javob yo'qolgan yangi buyurtma: qayta bosish → o'sha buyurtma, rasm detalga yuklandi (fayl o'sha), takror yo'q.
  Q3 — ikki bosish orasida forma o'zgardi: nomi mos — o'z detaliga, mos emas — xabar (boshqa detalga tushmaydi). F — `uploadPendingItemImages(..., faqatRasmsiz)`: rasmi bor detalga so'rov yo'q, rasmsizga — bor.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`. (Faqat sahifa o'zgargan — PG bo'limi yo'q.)
Asl kodga (zip 227) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_rasm228.py
"""
import os
import io
import re
import sys
import time
import socket
import hashlib
import tempfile
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
_T = tempfile.mkdtemp(prefix="k228_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k228.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "PG_URL"):
    os.environ.pop(_k, None)

YORLIQ = "[TF1] " if TF else ""
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


@contextlib.contextmanager
def bolim(nom):
    """Bo'lim xatosi (asl kodda yo'q element) — sinov qulamasin: bo'lim «yiqildi» deb yoziladi, keyingisi davom etadi."""
    try:
        yield
    except Exception as e:                 # noqa: BLE001
        check(f"{nom} — bo'lim oxirigacha bajarildi", False, f"{type(e).__name__}: {e}")


with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Project, Order, Taklif   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    with TestClient(main.app):
        pass
PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k228", PAROL, UserRole.ADMIN, "K228", company_id=1)
PRJ = Project(company_id=1, client_name="K228 mijoz", project_name="K228 loyiha", client_phone="+998901110228", total_budget=0, total_paid=0)
s.add(PRJ)
s.commit()
ID = {"PRJ": PRJ.id}
s.close()

from PIL import Image                               # noqa: E402
RASM = os.path.join(_T, "r228.png")
Image.new("RGB", (40, 30), (12, 140, 200)).save(RASM)
RASM_MD5 = hashlib.md5(open(RASM, "rb").read()).hexdigest()
YUKLANGAN = []


def soni(model):
    d = SessionLocal()
    try:
        return d.query(model).filter(model.company_id == 1).count()
    finally:
        d.close()


def detal_rasmlari(oid):
    d = SessionLocal()
    try:
        out = []
        for it in sorted(d.get(Order, oid).items, key=lambda x: x.id):
            m = None
            if it.image_url:
                yol = os.path.join(ROOT, it.image_url.lstrip("/"))
                YUKLANGAN.append(yol)
                try:
                    m = hashlib.md5(open(yol, "rb").read()).hexdigest()
                except OSError:
                    m = "fayl yo'q"
            out.append((it.name, m))
        return out
    finally:
        d.close()


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_O = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
check("S1 orders.html: taklif natijasida rasm eslatmasi (`.tk-rasm228`); `uploadPendingItemImages` 4-parametri `faqatRasmsiz`; `X-Takror` da "
      "rasm yuklash o'tkazib yuborilmaydi",
      "tk-rasm228" in _O and "async function uploadPendingItemImages(savedItems, yuborilgan, idlar, faqatRasmsiz)" in _O
      and "if (saved.items && saved.items.length && !takror)" not in _O
      and "uploadPendingItemImages(saved.items, undefined, undefined, takror)" in _O)

import uvicorn                                      # noqa: E402
from playwright.sync_api import sync_playwright     # noqa: E402
so = socket.socket()
so.bind(("127.0.0.1", 0))
port = so.getsockname()[1]
so.close()
server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
threading.Thread(target=server.run, daemon=True).start()
for _ in range(150):
    if server.started:
        break
    time.sleep(0.1)
BU = f"http://127.0.0.1:{port}"
XATO = []
ILGAK = """() => { window.__msg = []; window.showMsg = (t, ty) => { window.__msg.push([String(t), ty]);
    try { const a = JSON.parse(sessionStorage.getItem('k228m') || '[]'); a.push([String(t), ty]); sessionStorage.setItem('k228m', JSON.stringify(a)); } catch (e) {} };
  window.showConfirmModal = async () => true; window.customConfirm = async () => true; window.confirm = () => true;
  try { localStorage.removeItem('penodecor_new_order_draft_v1'); } catch (e) {} }"""
TOLDIR = """([nomlar, loyiha]) => {
  if (!Array.isArray(nomlar)) nomlar = [nomlar];
  if (loyiha) { const p = document.getElementById('project_id'); if (p) { p.value = String(loyiha); p.dispatchEvent(new Event('change')); } }
  const d = document.getElementById('deadline_input'); if (d) d.value = '2026-12-01';
  while (document.querySelectorAll('#items .detal').length < nomlar.length) addItem();
  const rows = [...document.querySelectorAll('#items .detal')];
  nomlar.forEach((nom, i) => { const r = rows[i]; const t = r.querySelector('.type-opt[data-value="dona"]'); if (t) t.click();
    r.querySelector('.i-name').value = nom; r.querySelector('.i-name').dispatchEvent(new Event('input', {bubbles: true}));
    const q = r.querySelector('.i-q'); q.value = '2'; q.dispatchEvent(new Event('input', {bubbles: true}));
    const up = r.querySelector('.i-unitprice'); if (up) { up.value = '15 000'; up.dispatchEvent(new Event('input', {bubbles: true})); } });
  return rows.length; }"""


def kontekst(br):
    c = br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
    c.set_default_timeout(20000)
    c.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda r: r.fulfill(status=204, body=""))
    pg = c.new_page()
    pg.on("pageerror", lambda e: XATO.append(str(e)[:300]))
    pg._sorov = []
    pg.on("request", lambda q: pg._sorov.append((q.method, q.url.replace(BU, ""))))
    pg.goto(BU + "/login")
    pg.fill("input[name=username]", "k228")
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    pg.goto(BU + "/orders")
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(400)
    pg.evaluate(ILGAK)
    return c, pg


with sync_playwright() as pw:
    br = pw.chromium.launch()
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("T — taklif: tanlangan rasm")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    with bolim("T"):
        for rasmli in (True, False, 2):
            c, pg = kontekst(br)
            n0 = soni(Taklif)
            pg.evaluate("async () => { await tezHisobOch(); }")
            pg.wait_for_timeout(500)
            pg.fill("#tk_mijoz", "K228 Mijoz " + ("rasmli" if rasmli else "rasmsiz"))
            pg.evaluate(TOLDIR, [["K228 taklif detal", "K228 taklif ikkinchi"] if rasmli == 2 else ["K228 taklif detal"], None])
            if rasmli:
                for _q in pg.query_selector_all("#items .detal .i-pending-image")[:(2 if rasmli == 2 else 1)]:
                    _q.set_input_files(RASM)
            pg._sorov.clear()
            pg.evaluate("() => { saveOrder(false); }")
            for _ in range(30):
                pg.wait_for_timeout(300)
                if soni(Taklif) > n0:
                    break
            pg.wait_for_timeout(1200)
            _t = pg.evaluate("""() => { const o = document.getElementById('tkNatijaOyna'); const e = document.querySelector('#tkNatijaOgoh .tk-rasm228');
              return {oyna: !!o && getComputedStyle(o).display !== 'none', eslatma: e ? e.textContent.trim() : null,
                      korinadi: !!e && e.getClientRects().length > 0, msg: window.__msg || []}; }""")
            _img = [x for x in pg._sorov if x[0] == "POST" and "/image" in x[1]]
            if rasmli == 2:
                check("T3 taklif (2 detalda rasm) — «📷 2 ta rasm taklifga saqlanmaydi — …»",
                      soni(Taklif) == n0 + 1 and _t["korinadi"] and (_t["eslatma"] or "").startswith("📷 2 ta rasm taklifga saqlanmaydi")
                      and not _img, (soni(Taklif), n0, _t, _img))
            elif rasmli:
                check("T1 taklif (rasm tanlangan) — taklif SAQLANDI, natija oynasida «📷 1 ta rasm taklifga saqlanmaydi — taklifni buyurtmaga "
                      "rasmiylashtirishda rasmni tanlang.» ko'rinadi; rasm so'rovi yo'q (asl: eslatma yo'q — rasm jimgina yo'qolardi)",
                      soni(Taklif) == n0 + 1 and _t["oyna"] and _t["korinadi"]
                      and _t["eslatma"] == "📷 1 ta rasm taklifga saqlanmaydi — taklifni buyurtmaga rasmiylashtirishda rasmni tanlang."
                      and not _img, (soni(Taklif), n0, _t, _img))
            else:
                check("T2 taklif (rasmsiz) — saqlandi, rasm eslatmasi YO'Q (avvalgidek)",
                      soni(Taklif) == n0 + 1 and _t["oyna"] and _t["eslatma"] is None, (soni(Taklif), n0, _t))
            c.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("Q — javobi yo'qolgan yangi buyurtma: qayta bosishda rasm yuklanadi")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    with bolim("Q"):
        c, pg = kontekst(br)
        pg.evaluate("() => showNewForm()")
        pg.wait_for_timeout(400)
        pg.evaluate(TOLDIR, [["K228 Q detal"], ID["PRJ"]])
        pg.query_selector("#items .detal .i-pending-image").set_input_files(RASM)
        n0 = soni(Order)
        BIRINCHI = [0]

        def _ushla(b):
            def _h(r):                      # kech138b: BITTA parametr
                if r.request.method != "POST" or b[0]:
                    return r.continue_()
                b[0] = 1
                r.fetch()                   # server SAQLAYDI, javob yo'qoladi
                r.fulfill(status=502, content_type="text/html", body="<html><body>502 Bad Gateway</body></html>")
            return _h
        _hq = _ushla(BIRINCHI)
        pg.route(re.compile(r".*/api/orders(\?.*)?$"), _hq)
        pg.evaluate("() => { window.__msg = []; saveOrder(false); }")
        for _ in range(30):
            pg.wait_for_timeout(300)
            if pg.evaluate("() => (window.__msg || []).length"):
                break
        _m1 = pg.evaluate("() => window.__msg")
        n1 = soni(Order)
        d = SessionLocal()
        _oid = d.query(Order.id).filter(Order.company_id == 1).order_by(Order.id.desc()).limit(1).scalar()
        d.close()
        _r1 = detal_rasmlari(_oid) if _oid else None
        check("Q1 birinchi bosish: server saqladi, javob yo'qoldi — «❌ Natija noma'lum», rasm hali yuklanmagan",
              n1 == n0 + 1 and any(m[0].startswith("❌ Natija noma'lum") for m in _m1) and _r1 == [("K228 Q detal", None)], (n0, n1, _m1, _r1))
        pg._sorov.clear()
        pg.evaluate("() => { window.__msg = []; sessionStorage.removeItem('k228m'); saveOrder(false); }")
        pg.wait_for_timeout(6000)              # muvaffaqiyatdan keyin sahifa buyurtmaga o'tadi (1 / 4 s)
        pg.wait_for_load_state("networkidle")
        _m2 = pg.evaluate("() => JSON.parse(sessionStorage.getItem('k228m') || '[]')")
        n2 = soni(Order)
        _r2 = detal_rasmlari(_oid)
        _img = [x for x in pg._sorov if x[0] == "POST" and "/image" in x[1]]
        check("Q2 qayta bosish: YANGI buyurtma yo'q, «avval saqlangan ekan», tanlangan rasm O'SHA detalga yuklandi (fayl aynan) — 1 ta rasm "
              "so'rovi (asl: rasm yuklanmasdi)",
              n2 == n1 and any("avval saqlangan ekan" in m[0] for m in _m2) and _r2 == [("K228 Q detal", RASM_MD5)] and len(_img) == 1,
              (n1, n2, _m2, _r2, _img))
        pg.unroute(re.compile(r".*/api/orders(\?.*)?$"), _hq)
        c.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("Q3 — ikki bosish orasida forma o'zgardi (review228 M1)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    with bolim("Q3"):
        c, pg = kontekst(br)
        pg.evaluate("() => showNewForm()")
        pg.wait_for_timeout(400)
        pg.evaluate(TOLDIR, [["K228 Pa", "K228 Pb"], ID["PRJ"]])
        n0 = soni(Order)
        B3 = [0]
        _hq3 = _ushla(B3)
        pg.route(re.compile(r".*/api/orders(\?.*)?$"), _hq3)
        pg.evaluate("() => { window.__msg = []; saveOrder(false); }")
        for _ in range(30):
            pg.wait_for_timeout(300)
            if pg.evaluate("() => (window.__msg || []).length"):
                break
        d = SessionLocal()
        _oid3 = d.query(Order.id).filter(Order.company_id == 1).order_by(Order.id.desc()).limit(1).scalar()
        d.close()
        # xodim «Natija noma'lum» dan keyin: «K228 Pb» ni «K228 Pd» ga o'zgartirdi, ikkala qatorga rasm tanladi
        pg.evaluate("""() => { const r = [...document.querySelectorAll('#items .detal')][1]; r.querySelector('.i-name').value = 'K228 Pd';
                               r.querySelector('.i-name').dispatchEvent(new Event('input', {bubbles: true})); }""")
        for _q in pg.query_selector_all("#items .detal .i-pending-image")[:2]:
            _q.set_input_files(RASM)
        pg._sorov.clear()
        pg.evaluate("() => { window.__msg = []; sessionStorage.removeItem('k228m'); saveOrder(false); }")
        pg.wait_for_timeout(7000)
        pg.wait_for_load_state("networkidle")
        _m3 = pg.evaluate("() => JSON.parse(sessionStorage.getItem('k228m') || '[]')")
        _r3 = detal_rasmlari(_oid3)
        _img3 = [x for x in pg._sorov if x[0] == "POST" and "/image" in x[1]]
        check("Q3 takrorda nomi mos qator («K228 Pa») — rasm o'z detaliga; o'zgartirilgan qator («K228 Pd») — rasm BOSHQA detalga («K228 Pb») "
              "TUSHMAYDI, xabar: «avval saqlangan ekan … detal topilmadi»; yangi buyurtma yo'q",
              soni(Order) == n0 + 1 and _r3 == [("K228 Pa", RASM_MD5), ("K228 Pb", None)] and len(_img3) == 1
              and any(m[0].startswith("ℹ️ Bu buyurtma avval saqlangan ekan") and "detal topilmadi" in m[0] for m in _m3),
              (soni(Order), n0, _r3, _img3, _m3))
        pg.unroute(re.compile(r".*/api/orders(\?.*)?$"), _hq3)
        c.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("F — faqat rasmi yo'q detalga")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    with bolim("F"):
        c, pg = kontekst(br)
        _f = pg.evaluate("""async () => {
          showNewForm(); const items = document.getElementById('items'); items.querySelectorAll('.detal').forEach(r => r.remove());
          addItem(); addItem(); const rows = [...items.querySelectorAll('.detal')];
          rows[0].querySelector('.i-name').value = 'F rasmli'; rows[1].querySelector('.i-name').value = 'F rasmsiz';
          const dt = () => { const d = new DataTransfer(); d.items.add(new File(['x'], 'x.png', {type: 'image/png'})); return d.files; };
          rows.forEach(r => { r.querySelector('.i-pending-image').files = dt(); });
          const saved = [{id: 901, name: 'F rasmli', image_url: '/static/uploads/bor.png'}, {id: 902, name: 'F rasmsiz', image_url: null}];
          const yuborildi = []; const asl = window.fetch;
          window.fetch = async (u, o) => { yuborildi.push(String(u)); return new Response('{}', {status: 200}); };
          let x1, x2, y1, y2;
          try { x1 = await uploadPendingItemImages(saved, undefined, undefined, true); y1 = yuborildi.splice(0);
                x2 = await uploadPendingItemImages(saved); y2 = yuborildi.splice(0); } finally { window.fetch = asl; }
          return {y1, y2, x1, x2}; }""")
        check("F1 `faqatRasmsiz` — rasmi bor detalga so'rov YO'Q, rasmsizga — bor; parametrsiz — ikkalasiga (avvalgidek)",
              _f["y1"] == ["/api/order-items/902/image"] and sorted(_f["y2"]) == ["/api/order-items/901/image", "/api/order-items/902/image"]
              and _f["x1"] == [] and _f["x2"] == [], _f)
        c.close()
    check("J sahifa JS xatosi yo'q", not XATO, XATO[:3])
    br.close()
server.should_exit = True

import glob                                       # noqa: E402
for _y2 in set(YUKLANGAN):      # sinov rasmlari va ularning kichik nusxalari — repo `static/uploads` da qolmasin (faqat SHU sinovniki)
    _stem = os.path.splitext(os.path.basename(_y2))[0]
    for _f2 in [_y2] + glob.glob(os.path.join(ROOT, "static", "uploads", "_kichik", "*", _stem + "_*")):
        try:
            os.remove(_f2)
        except OSError:
            pass

print(f"\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
