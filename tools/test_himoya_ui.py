#!/usr/bin/env python3
"""
test_himoya_ui.py — kech143 (zip 171): HAQIQIY brauzer (Chromium) — himoya qatlami (A-X04, A-X06) va kech142 jonli sinovi
topilmalari N2, N3, guruh «Sotish» bekor qilinishi.

NIMA UCHUN KERAK (O'LCHANGAN — asl kod zip 170; yordamchi o'lchov `work/k171_tayyorgarlik/ui_agent/`, Chromium):
  N2  «Ta'minotchilar» → «Tarix» → «+ Xarid qo'shish»: forma oyna qutisidan (max-height 88vh, faqat tarix ro'yxati surilardi)
      tashqariga chiqib, «✓ Saqlash» ga HECH BIR kenglikda yetib bo'lmasdi (375×812: y≈1051; 756×921: y≈955; 1440×900: y≈922).
  N3  «Tayyor mahsulotlar» — guruh ichidagi partiya qatori 641–1279 px da: nom ustuni `.fp-main` 0–44 px, «🔒 Band» belgisi
      harflab tik (154 px), amallar qatordan chiqib `.fp-page` yon tomonga surilardi.
  G   Guruh «Sotish» oynasi sotmasdan yopilsa («Bekor qilish», ✕, Esc) — yopiq guruhdagi partiyalar belgili qolib,
      «3 ta tanlandi» paneli turardi.
  O   (N2 bilan bir xil nuqson, kech143 da topildi) Omborxona → «Xaridlar tarixi»: «material bo'yicha jami» qadalgan — bu oy 25
      materialdan xarid bo'lsa 691 px bo'lib, xaridlar ro'yxatiga 0 px qolardi (1440×900 da ham).
  A-X04 HAQIQIY brauzerda: o'z sahifasidagi amallar (kirish formasi, `fetch` POST, «Chiqish») ishlaydi (`Sec-Fetch-Site:
      same-origin`); BOSHQA saytdagi forma (localhost → 127.0.0.1) — 403; boshqa saytdagi `/logout` havolasi chiqarmaydi.
  A-X06 Hodim QR sahifasi: o'z manzili (port bilan) olinadi, begona manzil — yo'q.
BO'LIMLAR: N — N2; O — Omborxona «Xaridlar tarixi»; T — N3; G — guruh «Sotish»; M — manba (A-X04); Q — QR (A-X06); X — sahifa xatolari.
ISHLATISH: python3 tools/test_himoya_ui.py   (Chromium — PLAYWRIGHT_BROWSERS_PATH, odatda /opt/pw-browsers)
"""
import os
import re
import sys
import glob
import time
import socket
import tempfile
import threading
import http.server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
_T = tempfile.mkdtemp(prefix="himoya_ui_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'himoya_ui.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "RESET_ADMIN_PASSWORD"):
    os.environ.pop(_k, None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, FinishedProduct, Inventory   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        cond = bool(cond() if callable(cond) else cond)
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
    print(f"\n--- {t} ---", flush=True)


# ══════════════════════════════════════════════════════════════
# Tayyorgarlik — ma'lumot (API orqali, asl va yangi kodda bir xil)
# ══════════════════════════════════════════════════════════════
with TestClient(main.app, base_url="https://testserver") as _c0:
    _c0.get("/login")
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    _u = auth.create_user(s, "hu_admin", "Parol123!", UserRole.ADMIN, "HU Admin", company_id=1)
s.query(User).filter(User.id == _u.id).update({User.is_platform_admin: True})
s.commit()
s.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=True)
C.post("/login", data={"username": "hu_admin", "password": "Parol123!"}, follow_redirects=False)


def j(r):
    assert r.status_code == 200, (r.status_code, r.text[:300])
    return r.json()


PENO = j(C.post("/api/inventory", json={"item_name": "HU Penoplast 15", "unit": "blok", "stock_quantity": 500, "price_per_unit": 500000,
                                        "is_penoplast": True, "volume_per_unit": 1.0}))["id"]
KLEY = j(C.post("/api/inventory", json={"item_name": "HU Kley PVA", "unit": "kg", "stock_quantity": 100, "price_per_unit": 3000}))["id"]
QUM = j(C.post("/api/inventory", json={"item_name": "HU Qum", "unit": "kg", "stock_quantity": 5000, "price_per_unit": 820}))["id"]
SUP = j(C.post("/api/suppliers", json={"name": "HU Qurilish bozori, 12-do'kon (Andijon)", "phone": "+998901234567", "notes": None}))["id"]
for _k in range(6):
    j(C.post(f"/api/inventory/{KLEY}/purchase", json={"quantity": 10 + _k, "price_per_unit": 3000 + 100 * _k, "paid_now": 0,
                                                      "supplier_id": SUP, "transport_payer": "none", "transport_cost": 0}))
j(C.post(f"/api/inventory/{QUM}/purchase", json={"quantity": 1000, "price_per_unit": 800, "paid_now": 100000, "supplier_id": SUP,
                                                 "transport_payer": "none", "transport_cost": 0}))
j(C.post(f"/api/suppliers/{SUP}/payment", json={"supplier_id": SUP, "amount": 50000, "confirm_overpay": False}))


# Omborxona «Xaridlar tarixi» — bu oy 25 materialdan xarid (material bo'yicha jami bloki uzun bo'lsin)
for _i in range(25):
    _iid = j(C.post("/api/inventory", json={"item_name": f"HU Xarid material {_i:02d} uzunroq nom bilan", "unit": "kg",
                                            "stock_quantity": 0, "price_per_unit": 1000}))["id"]
    j(C.post(f"/api/inventory/{_iid}/purchase", json={"quantity": 5, "price_per_unit": 1000 + _i, "paid_now": 0,
                                                      "transport_payer": "none", "transport_cost": 0}))


def produce(name, qty=20, w=20, th=10, price=45000):
    r = j(C.post("/api/finished/produce", json={"name": name, "category": "profil", "is_coated": False, "penoplast_id": PENO,
                                                "price_per_m3": None, "unit_price": price, "recipe_id": None, "notes": None,
                                                "width": w, "thickness": th, "length": qty, "quantity": qty}))
    fid = r.get("id") or r.get("product_id") or (r.get("product") or {}).get("id")
    j(C.post(f"/api/finished/{fid}/complete"))
    return fid


GURUHLAR = [("Karniz 20 sm M-06 fasad uchun oq rangli qoplamali", 4), ("Pilyastra kapiteli bilan 30×12 klassik uslub", 3),
            ("Panel", 3), ("Deraza atrofi nalichnik 15 sm uzun nomli mahsulot nomi tekshiruv uchun", 4)]
FP = {}
for _gi, (_nom, _n) in enumerate(GURUHLAR):
    FP[_nom] = [produce(_nom, qty=10 + 3 * _b, w=20 + _gi) for _b in range(_n)]
s = SessionLocal()
for _nom, _lst in FP.items():
    if _nom == "Panel":
        continue
    for _k, _fid in enumerate(_lst):
        if _k in (0, 2):
            _o = s.get(FinishedProduct, _fid)
            _o.reserved_quantity = 5.0 if _k == 0 else float(_o.quantity)
s.commit()
s.close()

# ── ilova serveri (127.0.0.1) va «boshqa sayt» (localhost — brauzer uchun boshqa sayt) ──
import uvicorn                                     # noqa: E402


def _port():
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    p = so.getsockname()[1]
    so.close()
    return p


PORT = _port()
SERVER = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=PORT, log_level="critical", lifespan="off"))
threading.Thread(target=SERVER.run, daemon=True).start()
for _ in range(150):
    if SERVER.started:
        break
    time.sleep(0.1)
BASE = f"http://127.0.0.1:{PORT}"
PORT2 = _port()
BEGONA_HTML = {
    "/forma.html": (f'<!doctype html><meta charset="utf-8"><form id="f" method="post" action="{BASE}/api/inventory/{KLEY}/stock">'
                    f'<input name="quantity_change" value="5"></form><script>document.getElementById("f").submit()</script>'),
    "/havola.html": f'<!doctype html><meta charset="utf-8"><a id="h" href="{BASE}/logout">Chiqish</a>',
}


class _Begona(http.server.BaseHTTPRequestHandler):
    def do_GET(self):                      # noqa: N802
        t = BEGONA_HTML.get(self.path.split("?")[0])
        self.send_response(200 if t else 404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write((t or "yo'q").encode("utf-8"))

    def log_message(self, *a):
        pass


BEGONA = http.server.ThreadingHTTPServer(("127.0.0.1", PORT2), _Begona)
threading.Thread(target=BEGONA.serve_forever, daemon=True).start()
BEGONA_URL = f"http://localhost:{PORT2}"

from playwright.sync_api import sync_playwright    # noqa: E402

_exe = None
for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                        "chrome-linux", "chrome"))):
    _exe = _y
XATOLAR = []


def sahifa(br, w, h, mobil=False, kirish=True):
    ctx = br.new_context(viewport={"width": w, "height": h}, is_mobile=mobil, has_touch=mobil, timezone_id="Asia/Tashkent",
                         locale="uz-UZ", device_scale_factor=1)
    ctx.set_default_timeout(20000)

    def tashqi(route):
        if re.search(r"chart(\.umd)?(\.min)?\.js", route.request.url, re.I):
            return route.fulfill(status=200, content_type="application/javascript",
                                 body="window.Chart = function () { return {destroy() {}, update() {}}; };")
        return route.fulfill(status=204, body="")
    ctx.route(re.compile(r"^https://(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|api\.qrserver\.com|"
                         r"cdn\.jsdelivr\.net|unpkg\.com)/.*"), tashqi)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: XATOLAR.append(f"{w}x{h}: {str(e)[:200]}"))
    if kirish:
        pg.goto(BASE + "/login")
        pg.fill("input[name=username]", "hu_admin")
        pg.fill("input[name=password]", "Parol123!")
        pg.press("input[name=password]", "Enter")
        pg.wait_for_load_state("networkidle")
    return ctx, pg


SAQLASH = r"""(sel) => { const b = document.querySelector(sel); if (!b) return {yoq: true};
  const r = b.getBoundingClientRect(); const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  const hit = (cy >= 0 && cy < innerHeight) ? document.elementFromPoint(cx, cy) : null;
  return {top: Math.round(r.top), bottom: Math.round(r.bottom), ih: innerHeight,
          korinadi: r.top >= 0 && r.bottom <= innerHeight && !!hit && (hit === b || b.contains(hit))}; }"""

with sync_playwright() as pw:
    br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()

    # ══════════════════════════════════════════════════════════════
    section("N. «Ta'minotchilar» → «Tarix» → «+ Xarid qo'shish» — «✓ Saqlash» ga yetib boriladi (N2)")
    # ══════════════════════════════════════════════════════════════
    for w, h, mob in ((375, 812, True), (756, 921, False), (1440, 900, False), (812, 375, True)):
        ctx, pg = sahifa(br, w, h, mob)
        try:
            pg.goto(BASE + "/suppliers", wait_until="networkidle")
            pg.locator(".sup-row", has_text="HU Qurilish bozori").locator(".sup-tarix").click()
            pg.wait_for_function("document.querySelectorAll('#hist-purchases .mini-btn').length > 0")
            pg.get_by_role("button", name="+ Xarid qo'shish").click()
            pg.wait_for_function("document.querySelectorAll('#ap-item option').length > 0")
            pg.wait_for_timeout(250)
            _p = pg.evaluate("() => { const r = document.getElementById('historyModal').firstElementChild.getBoundingClientRect();"
                             " return [r.left + r.width / 2, Math.min(innerHeight - 5, Math.max(5, r.top + r.height * 0.6))]; }")
            pg.mouse.move(_p[0], _p[1])
            _m, _q = pg.evaluate(SAQLASH, "#ap-save-btn"), 0
            while not _m.get("korinadi") and _q < 40:
                pg.mouse.wheel(0, 120)
                pg.wait_for_timeout(60)
                _q += 1
                _m = pg.evaluate(SAQLASH, "#ap-save-btn")
            check(f"N1 {w}×{h}: «✓ Saqlash» g'ildirak bilan ekranga chiqadi va bosiladi (asl: oynadan tashqarida, yetib bo'lmasdi)",
                  _m.get("korinadi"), (_m, _q))
            _x = pg.evaluate("() => { const b = document.querySelector('#historyModal [data-yopish]').getBoundingClientRect();"
                             " const h = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);"
                             " return !!h && !!h.closest('[data-yopish]'); }")
            check(f"N2 {w}×{h}: surilgandan keyin ham «✕» (yopish) joyida va bosiladi", _x)
        except Exception as e:             # noqa: BLE001
            check(f"N1 {w}×{h}: o'lchov", False, f"{type(e).__name__}: {e}")
        ctx.close()

    # ══════════════════════════════════════════════════════════════
    section("O. Omborxona → «Xaridlar tarixi» — ko'p material bilan ro'yxat ko'rinadi (N2 bilan bir xil nuqson)")
    # ══════════════════════════════════════════════════════════════
    OXIRGI = r"""() => { const rows = [...document.querySelectorAll('#hist-list button')]; const last = rows[rows.length - 1];
      if (!last) return {n: 0};
      last.scrollIntoView({block: 'nearest'});
      const r = last.getBoundingClientRect(); const h = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      const x = document.querySelector('#historyModal [data-yopish]').getBoundingClientRect();
      const hx = document.elementFromPoint(x.left + x.width / 2, x.top + x.height / 2);
      return {n: rows.length, korinadi: r.top >= 0 && r.bottom <= innerHeight && !!h && (h === last || last.contains(h)),
              yopish: !!hx && !!hx.closest('[data-yopish]')}; }"""
    for w, h, mob in ((375, 812, True), (812, 375, True), (1440, 900, False)):
        ctx, pg = sahifa(br, w, h, mob)
        try:
            pg.goto(BASE + "/inventory", wait_until="networkidle")
            pg.evaluate("openPurchaseHistory()")
            pg.wait_for_function("document.querySelectorAll('#hist-list button').length >= 25")
            pg.wait_for_timeout(300)
            _m = pg.evaluate(OXIRGI)
            check(f"O1 {w}×{h}: 25 material — xaridlar ro'yxatining oxirgi qatori ekranga chiqadi va bosiladi, «✕» joyida "
                  f"(asl: material bo'yicha jami 691 px, ro'yxatga 0 px — ko'rinmasdi)", _m.get("korinadi") and _m.get("yopish"), _m)
        except Exception as e:             # noqa: BLE001
            check(f"O1 {w}×{h}: o'lchov", False, f"{type(e).__name__}: {e}")
        ctx.close()

    # ══════════════════════════════════════════════════════════════
    section("T. «Tayyor mahsulotlar» guruh partiyalari — planshet / kichik noutbuk kengligi (N3)")
    # ══════════════════════════════════════════════════════════════
    OLCH = r"""() => { const R = e => e.getBoundingClientRect();
      const rows = [...document.querySelectorAll('#fpList .fp-guruh-ichi .fp-row')].filter(r => r.offsetParent !== null);
      const mainW = rows.map(r => Math.round(R(r.querySelector(':scope > .fp-main')).width));
      const band = [...document.querySelectorAll('#fpList .fp-guruh-ichi .fp-badge')].filter(b => b.textContent.includes('Band')
                    && b.offsetParent !== null).map(b => Math.round(R(b).height));
      const pgEl = document.querySelector('.fp-page'), de = document.documentElement;
      return {n: rows.length, mainMin: Math.min(...mainW), bandMax: band.length ? Math.max(...band) : 0, bandN: band.length,
              sahifaSurilish: pgEl.scrollWidth - pgEl.clientWidth, docSurilish: de.scrollWidth - de.clientWidth}; }"""
    for w, h, mob in ((375, 812, True), (700, 1024, True), (768, 1024, True), (800, 1024, False), (1024, 768, False),
                      (1200, 900, False), (1440, 900, False)):
        ctx, pg = sahifa(br, w, h, mob)
        try:
            pg.goto(BASE + "/finished", wait_until="networkidle")
            pg.wait_for_function("document.querySelectorAll('#fpList .fp-guruh').length >= 4")
            pg.evaluate("() => document.querySelectorAll('#fpList .fp-guruh').forEach(g => { if (!g.classList.contains('ochiq'))"
                        " g.querySelector('.fp-guruh-tugma').click(); })")
            pg.wait_for_timeout(500)
            _m = pg.evaluate(OLCH)
            check(f"T1 {w}px: partiya qatorlarida nom ustuni ≥ 120 px, «🔒 Band» belgisi tik emas (≤ 30 px), yon surilish yo'q "
                  f"(asl 641–1279 px: nom 0–44 px, belgi 154 px)",
                  _m["n"] >= 10 and _m["mainMin"] >= 120 and _m["bandN"] >= 3 and _m["bandMax"] <= 30
                  and _m["sahifaSurilish"] <= 1 and _m["docSurilish"] <= 1, _m)
        except Exception as e:             # noqa: BLE001
            check(f"T1 {w}px: o'lchov", False, f"{type(e).__name__}: {e}")
        ctx.close()

    # ══════════════════════════════════════════════════════════════
    section("G. Guruh «Sotish» oynasi sotmasdan yopilsa — belgilar qaytadi")
    # ══════════════════════════════════════════════════════════════
    HOLAT = r"""() => ({modal: getComputedStyle(document.getElementById('batchSellModal')).display,
      bar: getComputedStyle(document.getElementById('batchSellBar')).display,
      belgili: document.querySelectorAll('.fp-batch-check:checked').length,
      belgi_qoldi: document.querySelectorAll('.fp-batch-check[data-guruh-avto]').length})"""
    GSOT = r"""(nom) => { const g = [...document.querySelectorAll('#fpList .fp-guruh')].find(x =>
      x.querySelector('.fp-guruh-bosh .fp-name').textContent.trim() === nom);
      g.querySelector('.fp-guruh-bosh button[aria-label="Sotish"]').click(); }"""
    ctx, pg = sahifa(br, 1440, 900)

    def yangi():
        pg.goto(BASE + "/finished", wait_until="networkidle")
        pg.wait_for_function("document.querySelectorAll('#fpList .fp-guruh').length >= 4")
        pg.wait_for_timeout(300)

    try:
        for nom, yop in (("«Bekor qilish»", lambda: pg.locator("#batchSellModal button", has_text="Bekor qilish").click()),
                         ("«✕»", lambda: pg.locator("#batchSellModal button[aria-label=Yopish]").click()),
                         ("Esc", lambda: pg.keyboard.press("Escape"))):
            yangi()
            pg.evaluate(GSOT, "Panel")
            pg.wait_for_timeout(200)
            _o = pg.evaluate(HOLAT)
            yop()
            pg.wait_for_timeout(200)
            _k = pg.evaluate(HOLAT)
            check(f"G1 guruh «Sotish» → {nom}: belgilar olib tashlandi, panel yopildi (asl: 3 ta belgili qolardi)",
                  _o["belgili"] == 3 and _k["modal"] == "none" and _k["belgili"] == 0 and _k["bar"] == "none", (_o, _k))
        yangi()
        pg.evaluate("() => { const g = [...document.querySelectorAll('#fpList .fp-guruh')].find(x => x.querySelector("
                    "'.fp-guruh-bosh .fp-name').textContent.startsWith('Pilyastra')); if (!g.classList.contains('ochiq'))"
                    " g.querySelector('.fp-guruh-tugma').click(); }")
        pg.wait_for_timeout(300)
        _cb = pg.locator(".fp-guruh.ochiq .fp-guruh-ichi .fp-batch-check:not([disabled])")
        _cb.nth(0).check()
        pg.wait_for_timeout(100)
        pg.evaluate(GSOT, "Panel")
        pg.wait_for_timeout(200)
        _o = pg.evaluate(HOLAT)
        pg.locator("#batchSellModal button", has_text="Bekor qilish").click()
        pg.wait_for_timeout(200)
        _k = pg.evaluate(HOLAT)
        check("G2 qo'lda belgilangan 1 + guruh «Sotish» 3 → «Bekor qilish»: qo'lda belgilangani qoladi (1), panel ko'rinadi",
              _o["belgili"] == 4 and _k["belgili"] == 1 and _k["bar"] != "none" and _k["belgi_qoldi"] == 0, (_o, _k))
        yangi()
        pg.evaluate("() => { const g = [...document.querySelectorAll('#fpList .fp-guruh')].find(x => x.querySelector("
                    "'.fp-guruh-bosh .fp-name').textContent.trim() === 'Panel'); if (!g.classList.contains('ochiq'))"
                    " g.querySelector('.fp-guruh-tugma').click(); }")
        pg.wait_for_timeout(300)
        PANEL = r"""() => [...document.querySelectorAll('#fpList .fp-guruh')].find(x =>
          x.querySelector('.fp-guruh-bosh .fp-name').textContent.trim() === 'Panel')"""
        pg.evaluate("(f) => { const g = eval(f)(); const c = g.querySelectorAll('.fp-guruh-ichi .fp-batch-check:not([disabled])');"
                    " c[1].click(); }", PANEL)
        pg.wait_for_timeout(100)
        pg.evaluate(GSOT, "Panel")
        pg.wait_for_timeout(200)
        _o = pg.evaluate(HOLAT)
        pg.locator("#batchSellModal button", has_text="Bekor qilish").click()
        pg.wait_for_timeout(200)
        _k = pg.evaluate(HOLAT)
        _qoldi = pg.evaluate("(f) => [...eval(f)().querySelectorAll('.fp-guruh-ichi .fp-batch-check:not([disabled])')]"
                             ".map(x => x.checked)", PANEL)
        check("G3 o'sha guruhda qo'lda belgilangan 1 + guruh «Sotish» → «Bekor qilish»: AYNAN o'sha 1 ta belgili qoladi",
              _o["belgili"] == 3 and _k["belgili"] == 1 and _qoldi == [False, True, False] and _k["belgi_qoldi"] == 0,
              (_o, _k, _qoldi))
    except Exception as e:                 # noqa: BLE001
        check("G o'lchov", False, f"{type(e).__name__}: {e}")
    ctx.close()

    # ══════════════════════════════════════════════════════════════
    section("M. Boshqa saytdan so'rov — haqiqiy brauzerda (A-X04)")
    # ══════════════════════════════════════════════════════════════
    ctx, pg = sahifa(br, 1280, 900)
    try:
        check("M1 kirish formasi (o'z sayti) — kirdi", "/login" not in pg.url, pg.url)
        _r = pg.evaluate("""async (id) => { const r = await fetch('/api/inventory/' + id + '/stock', {method: 'POST',
            headers: {'Content-Type': 'application/json'}, body: JSON.stringify({quantity_change: 1, reason: 'UI sinov'})});
            return r.status; }""", KLEY)
        check("M2 sahifadagi fetch POST (Sec-Fetch-Site: same-origin) — 200", _r == 200, _r)
        _hol = []
        pg.on("response", lambda r: _hol.append((r.url, r.status)) if "/api/inventory/" in r.url else None)
        _s0 = float(SessionLocal().get(Inventory, KLEY).stock_quantity)
        pg.goto(BEGONA_URL + "/forma.html")
        pg.wait_for_timeout(1500)
        _s1 = float(SessionLocal().get(Inventory, KLEY).stock_quantity)
        _st = [x[1] for x in _hol if "/stock" in x[0]]
        check("M3 BOSHQA saytdagi forma (localhost → 127.0.0.1) avtomatik POST — 403, qoldiq o'zgarmadi (asl: 401/422 — "
              "manba tekshirilmasdi)", _st and _st[-1] == 403 and _s1 == _s0, (_st, _s0, _s1))
        pg.goto(BEGONA_URL + "/havola.html")
        pg.click("#h")
        pg.wait_for_load_state("networkidle")
        _ish = pg.evaluate("async () => (await fetch('/api/inventory')).status")
        check("M4 BOSHQA saytdagi «/logout» havolasi bosildi — tizimdan CHIQMADI (asl: chiqarardi)", _ish == 200, (_ish, pg.url))
        pg.goto(BASE + "/")
        pg.wait_for_load_state("networkidle")
        pg.locator("a.s-logout").first.click()
        pg.wait_for_load_state("networkidle")
        _ish2 = pg.evaluate("async () => (await fetch('/api/inventory')).status")
        check("M5 o'z sahifasidagi «Chiqish» — chiqardi (401)", _ish2 == 401 and "/login" in pg.url, (_ish2, pg.url))
    except Exception as e:                 # noqa: BLE001
        check("M o'lchov", False, f"{type(e).__name__}: {e}")
    ctx.close()

    # ══════════════════════════════════════════════════════════════
    section("Q. Hodim QR — o'z manzili (port bilan), begona manzil yo'q (A-X06)")
    # ══════════════════════════════════════════════════════════════
    ctx, pg = sahifa(br, 1280, 900)
    try:
        pg.goto(BASE + "/users/hodim-qr?manzil=" + BASE)
        _t = pg.inner_text("body")
        check("Q1 manzil = o'z sayti (127.0.0.1:port) — QR manzili shu", f"{BASE}/hodim?k=" in _t, _t[:300])
        pg.goto(BASE + "/users/hodim-qr?manzil=https://evil.example")
        _t = pg.inner_text("body")
        check("Q2 begona manzil — sahifada yo'q, o'z manzili bor (asl: https://evil.example/hodim?k=…)",
              "evil.example" not in _t and f"{BASE}/hodim?k=" in _t, _t[:300])
    except Exception as e:                 # noqa: BLE001
        check("Q o'lchov", False, f"{type(e).__name__}: {e}")
    ctx.close()
    br.close()

# ══════════════════════════════════════════════════════════════
section("X. Sahifa xatolari")
# ══════════════════════════════════════════════════════════════
check("X1 sahifalarda JS xatosi yo'q", not XATOLAR, XATOLAR[:5])
SERVER.should_exit = True
BEGONA.shutdown()

print(f"\nNATIJA: o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
