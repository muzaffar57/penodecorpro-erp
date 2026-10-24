#!/usr/bin/env python3
"""
test_maydon214.py — kech156 (zip 214 «1 m³ narxi kengroq» — egasi tanlovi 24.10: ««1 m³ narxi» kengroq (Tavsiya)»).

NIMA UCHUN KERAK
  Buyurtma oynasidagi detal maydonlari qat'iy ustunlarda edi — joy yetmasa 0 px gacha siqilardi. O'LCHANGAN (`work/k214/probe214.py`,
  zip 213 kodi, haqiqiy Chromium): «1 m³ narxi» yozish joyi 1440 px da 2 px, 1366 / 1280 / 1024 px da 0, 768 px da 45; Donali turida
  1440 px da Bo'yi, Qalinlik, «1 metrdan nechta», «1 dona narxi», Miqdor — 0 px, 1920 px da ham «1 dona narxi» sig'masdi; «1 dona /
  1 kg narxi» telefonda ham sig'masdi; Profil O'lchami 1280 px da 0; 901–1150 px da forma ustuni ~110–200 px (Nomi 0–86 px).
BO'LIMLAR
  S — manba: maydon qatorlari flex-wrap (son — 140 / 160 px, narx — 220 px, Qoplama — 150, Plotnost — 260), qutilar (≥ 901 px), 901–1150 px
      da o'ng panel formadan keyin, «Loy turi» butun qatorda, uchta klass.
  U — HAQIQIY Chromium, 10 ekran kengligi × 5 tur (Profil, Panel, Donali, Loy sotish, Blok): «1 m³ narxi» / «1 blok narxi» va hamma narx
      maydonlarida «1 250 000» sig'adi; har ko'rinadigan maydon yozish joyi ≥ 30 px; maydonlar detal ichida, sahifa yonga surilmaydi;
      keng ekranda (1920 / 1440) O'lcham va «Qoplama, plotnost, narx» avvalgidek bir qatorda; 901–1150 px — forma ochiq bo'lsa o'ng panel
      ostida (forma ≥ 380 px), yopilsa yana uch ustun; hisob ishlaydi (1 m³ narxi → Jami); JS xatosi yo'q.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`. Asl kodga (zip 213) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_maydon214.py
"""
import os
import io
import re
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

TF = os.environ.get("TENANT_FILTER") == "1"
_T = tempfile.mkdtemp(prefix="k214_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k214.db')}"
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
        print(f"  ✗ {label}   {str(detail)[:1200]}")


def section(t):
    print(f"\n--- {t} ---")


def xav(f, *a, standart=None, **k):
    try:
        return f(*a, **k)
    except Exception as e:                 # noqa: BLE001
        print(f"    (bajarilmadi: {getattr(f, '__name__', f)} — {type(e).__name__}: {str(e)[:200]})")
        return standart


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
ORD = open(os.path.join(ROOT, "templates", "orders.html"), encoding="utf-8").read()
check("S1 maydon qatorlari (O'lcham, Miqdor va narx, Qoplama-plotnost-narx) — flex-wrap; son — 140 / 160 px, narx — 220 px, Qoplama — 150, "
      "Plotnost — 260; natija kartalari — 200 px",
      ".i-dims-box > .dgrp-row, .i-qty-box > .dgrp-row, .dgrp-row.yb-qoplama-qator{display:flex;flex-wrap:wrap;align-items:flex-end}" in ORD
      and ".i-dims-box > .dgrp-row > .dif{flex:1 1 140px;min-width:0}" in ORD and ".i-qty-box > .dgrp-row > .dif{flex:1 1 160px;min-width:0}" in ORD
      and ".i-qty-box > .dgrp-row > .i-unitprice-wrap, .yb-qoplama-qator > .i-m3price-wrap, .yb-qoplama-qator > .i-blokprice-wrap"
          "{flex:1 1 220px;min-width:0}" in ORD
      and ".yb-qoplama-qator > .i-coat-wrap{flex:1 1 150px;min-width:0}" in ORD and ".yb-qoplama-qator > .i-peno-wrap{flex:2 1 260px;min-width:0}" in ORD
      and ".detal-result .result-card{flex:1 1 200px}" in ORD)
check("S2 ≥ 901 px: O'lcham / Miqdor qutilari tor ustunda ustma-ust; 901–1150 px: yangi buyurtma ochiq — o'ng panel formadan keyin; "
      "«Loy turi» butun qatorda; Qoplama / Plotnost / 1 m³ narxi — klasslar",
      "@media (min-width:901px){\n  /* «O'lcham» va «Miqdor va narx» qutilari" in ORD
      and ".dgrp-flex-row > .i-dims-box{flex:2 1 260px !important;min-width:0}" in ORD and ".dgrp-flex-row > .i-qty-box{flex:3 1 320px !important;min-width:0}" in ORD
      and "@media (min-width:901px) and (max-width:1150px){" in ORD and ".ord-layout.yangi-forma{grid-template-columns:260px minmax(0,1fr)}" in ORD
      and "@media (min-width:1151px) and (max-width:1365px){" in ORD and ".ord-layout.yangi-forma{grid-template-columns:260px minmax(0,1fr) 240px}" in ORD
      and ".ord-layout.yangi-forma > .right-panel{grid-column:2}" in ORD and ".detal-grid > .i-loysale-recipe-wrap{grid-column:1/-1}" in ORD
      and '<div class="dif i-coat-wrap"><label>Qoplama</label>' in ORD and '<div class="dif i-peno-wrap"><label>Plotnost</label>' in ORD
      and '<div class="dif i-m3price-wrap"><label>1 m³ narxi</label>' in ORD)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# tayyorgarlik
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, Project   # noqa: E402

PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k214_a", PAROL, UserRole.ADMIN, "K214 Admin", company_id=1)
s.add_all([Inventory(company_id=1, item_name="Penoplast 25", unit="blok", stock_quantity=1000, price_per_unit=500_000, volume_per_unit=1.0,
                     is_penoplast=True, is_default_penoplast=True, category="Penoplast"),
           Inventory(company_id=1, item_name="Penoplast 35", unit="blok", stock_quantity=1000, price_per_unit=700_000,
                     volume_per_unit=1.0, is_penoplast=True, category="Penoplast"),
           Project(company_id=1, client_name="K214 mijoz", project_name="K214 loyiha", client_phone="+998901112214", total_budget=0,
                   total_paid=0)])
s.commit()
crud.set_setting(s, "mahsulot_turlari", "profil,panel,dona,blok,loy_sotish,mrp_product", company_id=1)
crud.set_setting(s, "enabled_categories", "blok,loy_sotish", company_id=1)
s.commit()
s.close()

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U — HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
PW_BOR = True
try:
    from playwright.sync_api import sync_playwright
except Exception:                          # noqa: BLE001
    PW_BOR = False
check("U0 Python `playwright` bor", PW_BOR)

OLCH = r"""(tur) => {
  const r = document.querySelector('#items .detal');
  const t = r.querySelector(`.type-opt[data-value="${tur}"]`); if (!t) return {yoq: true};
  t.click();
  const dr = r.getBoundingClientRect();
  const maydon = [...r.querySelectorAll('input, select')].filter(e => e.offsetParent !== null && e.type !== 'hidden' && e.type !== 'file'
      && !e.closest('.subdetail-list') && !e.classList.contains('i-name')).map(e => {
    const d = e.closest('.dif, .result-card') || e.parentElement; const lab = ((d && d.querySelector('label')) || {}).textContent || e.className;
    const cs = getComputedStyle(e); const b = e.getBoundingClientRect();
    let sig = null, yozuv = null;
    if (e.tagName === 'INPUT' && e.type === 'text') { const eski = e.value; e.value = '1 250 000'; sig = e.scrollWidth <= e.clientWidth + 1; e.value = eski; }
    if (e.tagName === 'SELECT' && e.selectedIndex >= 0) {
      const c = (window.__k214c = window.__k214c || document.createElement('canvas')).getContext('2d');
      c.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
      const m = c.measureText(e.options[e.selectedIndex].text).width;
      yozuv = m <= e.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) - 16;
    }
    return {lab: lab.trim().slice(0, 30), sinf: e.className, ichki: Math.round(e.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)),
            sig, yozuv, ichida: b.left >= dr.left - 1 && b.right <= dr.right + 1, y: Math.round(b.top)}; });
  const q = r.querySelector('.yb-qoplama-qator');
  const qy = [...q.children].filter(e => e.offsetParent !== null).map(e => Math.round(e.getBoundingClientRect().top));
  const dy = [...r.querySelectorAll('.i-dims-box > .dgrp-row > .dif')].filter(e => e.offsetParent !== null).map(e => Math.round(e.getBoundingClientRect().top));
  return {maydon, qoplama_y: qy, olcham_y: dy, tosh: document.documentElement.scrollWidth - document.documentElement.clientWidth};
}"""
USTUN = r"""() => { const m = document.querySelector('.ord-layout > .mid-panel').getBoundingClientRect();
  const o = document.querySelector('.ord-layout > .right-panel').getBoundingClientRect();
  const f = document.getElementById('newOrderForm').getBoundingClientRect();
  return {mid_x: Math.round(m.left), mid_w: Math.round(m.width), ong_x: Math.round(o.left), ong_y: Math.round(o.top), forma_past: Math.round(f.bottom),
          forma_ochiq: getComputedStyle(document.getElementById('newOrderForm')).display !== 'none',
          ustunlar: getComputedStyle(document.querySelector('.ord-layout')).gridTemplateColumns.split(' ').length}; }"""
KENGLIK = ((1920, 1080, False), (1440, 900, False), (1366, 768, False), (1280, 800, False), (1200, 800, False), (1151, 800, False),
           (1024, 768, False), (901, 900, False),
           (900, 900, False), (768, 1024, True), (390, 844, True), (360, 740, True))
TURLAR = ("profil", "panel", "dona", "loy_sotish", "blok")
NARX = ("1 m³ narxi", "1 blok narxi", "narxi", "Jami")
NAT = {}
USTUNLAR = {}
XATO = []
HISOB = {}

if PW_BOR:
    import uvicorn                                 # noqa: E402
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
    with sync_playwright() as pw:
        _exe = None
        for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                "chrome-linux", "chrome"))):
            _exe = _y
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()
        for w, h, tel in KENGLIK:
            ctx = br.new_context(viewport={"width": w, "height": h}, timezone_id="Asia/Tashkent", locale="uz-UZ", is_mobile=tel, has_touch=tel)
            ctx.set_default_timeout(20000)
            ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda r: r.fulfill(status=204, body=""))
            ctx.add_init_script("try { localStorage.removeItem('penodecor_new_order_draft_v1'); } catch (e) {}")
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: XATO.append(str(e)[:300]))
            try:
                xav(pg.goto, BU + "/login")
                xav(pg.fill, "input[name=username]", "k214_a")
                xav(pg.fill, "input[name=password]", PAROL)
                xav(pg.press, "input[name=password]", "Enter")
                xav(pg.wait_for_load_state, "networkidle")
                xav(pg.goto, BU + "/orders")
                xav(pg.wait_for_load_state, "networkidle")
                xav(pg.evaluate, "() => showNewForm()")
                xav(pg.wait_for_timeout, 300)
                USTUNLAR[w] = {"ochiq": xav(pg.evaluate, USTUN, standart={})}
                for tur in TURLAR:
                    NAT[(w, tur)] = xav(pg.evaluate, OLCH, tur, standart={}) or {}
                if w == 1440:
                    xav(pg.evaluate, """() => { const r = document.querySelector('#items .detal');
                        r.querySelector('.type-opt[data-value="profil"]').click();
                        const v = (c, x) => { const e = r.querySelector(c); e.value = x; e.dispatchEvent(new Event('input')); };
                        v('.i-h', '20'); v('.i-w', '10'); v('.i-l', '5'); v('.i-m3price', '1 250 000'); }""")
                    xav(pg.wait_for_timeout, 300)
                    HISOB["jami"] = xav(pg.evaluate, "() => document.querySelector('#items .detal .i-price').value", standart="")
                xav(pg.evaluate, "() => hideNewForm()")
                xav(pg.wait_for_timeout, 200)
                USTUNLAR[w]["yopiq"] = xav(pg.evaluate, USTUN, standart={})
            finally:
                ctx.close()
        br.close()

    def maydonlar(pred):
        out = []
        for (w, tur), v in NAT.items():
            for m in (v or {}).get("maydon", []):
                if pred(m):
                    out.append((w, tur, m["lab"], m["ichki"], m["sig"]))
        return out
    _jami_tur = all(NAT.get((w, t), {}).get("maydon") for w, _, _ in KENGLIK for t in TURLAR)
    check("U1 o'lchov to'liq: 10 kenglik × 5 tur (Blok va Loy sotish ham yoqiq)", _jami_tur,
          [(k, bool(v.get("maydon")), v.get("yoq")) for k, v in NAT.items() if not v.get("maydon")])
    _m3 = maydonlar(lambda m: m["lab"] in ("1 m³ narxi", "1 blok narxi"))
    check("U2 «1 m³ narxi» / «1 blok narxi» — HAMMA kenglikda «1 250 000» sig'adi, yozish joyi ≥ 100 px (asl: 1440 px — 2, 1366 / 1280 / "
          "1024 px — 0, 768 px — 45)",
          len(_m3) >= len(KENGLIK) * 4 and all(x[4] and x[3] >= 100 for x in _m3), [x for x in _m3 if not (x[4] and x[3] >= 100)][:12])
    _nx = maydonlar(lambda m: m["sig"] is not None and any(k in m["lab"] for k in NARX))
    check("U3 hamma narx maydonlari («1 dona / 1 kg / 1 m narxi», «1 metr narxi», «Jami») — «1 250 000» sig'adi (asl: Donali 1440 px da 0, "
          "1920 px da ham sig'masdi; telefonda «1 dona narxi» — 56 px)",
          _nx and all(x[4] for x in _nx), [x for x in _nx if not x[4]][:12])
    _tor = maydonlar(lambda m: m["ichki"] < 40)
    check("U4 har ko'rinadigan maydon yozish joyi ≥ 40 px — hamma kenglik va tur (asl: ko'pi 0 px)", not _tor, _tor[:15])
    _tash = maydonlar(lambda m: not m["ichida"])
    _surildi = [(k, v.get("tosh")) for k, v in NAT.items() if (v or {}).get("tosh", 0) > 0]
    check("U5 maydonlar detal ichida, sahifa yon tomonga surilmaydi", not _tash and not _surildi, (_tash[:10], _surildi[:10]))
    _keng = {w: (NAT.get((w, "profil"), {}).get("olcham_y"), NAT.get((w, "profil"), {}).get("qoplama_y")) for w in (1920, 1440)}
    check("U6 keng ekranda avvalgidek: 1920 / 1440 px — O'lcham (Bo'yi, Qalinligi, Uzunlik) bir qatorda; 1920 px — Qoplama, Plotnost, "
          "1 m³ narxi bir qatorda",
          all(v[0] and len(v[0]) == 3 and len(set(v[0])) == 1 for v in _keng.values()) and _keng[1920][1] and len(set(_keng[1920][1])) == 1,
          _keng)
    _u = {w: USTUNLAR.get(w, {}) for w in (1024, 901, 1151, 1280, 1366)}
    check("U7 901–1150 px: yangi buyurtma ochiq — o'ng panel forma OSTIDA, forma ustuni ≥ 330 px (asl: 93–216 px); 1151–1365 px — 3 ustun, "
          "forma ≥ 360 px (asl: 283 px 1151 da); yopilganda — avvalgi uch ustun (forma ustuni o'sha); 1366 px — o'zgarmagan",
          all(v.get("ochiq", {}).get("ustunlar") == 2 and v["ochiq"].get("mid_w", 0) >= 330 and v["ochiq"].get("ong_y", 0) >= v["ochiq"].get("forma_past", 9e9) - 1
              and v.get("yopiq", {}).get("ustunlar") == 3 for w, v in _u.items() if w in (1024, 901))
          and all(_u[w].get("ochiq", {}).get("ustunlar") == 3 and _u[w]["ochiq"].get("mid_w", 0) >= 360
                  and _u[w].get("yopiq", {}).get("mid_w", 0) < _u[w]["ochiq"].get("mid_w", 0) for w in (1151, 1280))
          and _u[1366].get("ochiq", {}).get("mid_w") == _u[1366].get("yopiq", {}).get("mid_w"), _u)
    check("U8 hisob o'zgarmagan: Profil 20 × 10 sm, 5 m, 1 m³ narxi «1 250 000» → Jami 62 500 (asl kod bilan AYNAN)",
          HISOB.get("jami") == "62\u00a0500", HISOB)
    _sel = []
    for (w, tur), v in NAT.items():
        for m in (v or {}).get("maydon", []):
            if m["lab"].startswith("Plotnost") and w != 360 and m["ichki"] < 150:   # 360 px — butun qatorda (asl ham 190 px)
                _sel.append((w, tur, m["lab"], m["ichki"]))
            elif not m["lab"].startswith("Plotnost") and m.get("yozuv") is False:
                _sel.append((w, tur, m["lab"], m["ichki"]))
    check("U10 tanlov maydonlari: Plotnost yozish joyi ≥ 150 px (360 px dan boshqa; asl: 1280 / 1024 px da 1), «Loy turi» tanlangan yozuvi "
          "to'liq (asl: 1280 px da 40 px) — hamma kenglik va tur", not _sel, _sel[:12])
    check("U9 JS xatosi yo'q", not XATO, XATO[:5])

print(f"\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
