#!/usr/bin/env python3
"""
test_karusel_nuqta_ui.py — kech136 (zip 162): Dashboard yuqori kartalar karuseli («Buyurtmalar holati» / «Ishlab chiqarish») va
uning nuqtalari — HAQIQIY brauzerda (Chromium, Playwright), HAQIQIY lokal server bilan (uvicorn, test bazasi) O'LCHANADI.

NIMA UCHUN KERAK (O'LCHANGAN — work/k162/olchov162.py, zip 161 kodi)
  * nuqtalar hech qachon ko'rinmasdi (320 … 768 px da `display: none` — asosiy qoida telefon blokidan KEYIN);
  * ikkinchi kartada turganda o'lcham o'zgarsa (telefonda manzil satri yashirinishi, burilish — `resize`) faol nuqta birinchiga
    qaytardi; har `resize` da yangi `scroll` tinglovchisi qo'shilardi (4 o'zgarishda 6 ta);
  * nuqta bosilmasdi — 760 px da (ilova yon paneli) sichqoncha g'ildiragi bilan ikkinchi kartaga o'tib bo'lmasdi;
  * faol bo'lmagan nuqta fonga nisbatan 1.39 (kunduzgi) / 1.54 (tungi) — ko'rinmasdi (me'yor ≥ 3:1).

BO'LIMLAR
  U1 kengliklar (1440 … 320): ≥ 769 px — panjara, ikki ustun, nuqtalar yashirin; ≤ 768 px — karusel, nuqtalar KO'RINADI (tugmalar,
     kartalar soniga teng, birinchisi faol), sahifa yon tomonga toshmaydi;
  U2 telefon (390) — haqiqiy barmoq surishi (CDP touch): ikkinchi karta → ikkinchi nuqta faol (aria-current), qaytib — birinchi;
  U3 qisman surish — snap dan keyin faol nuqta ko'rinib turgan karta bilan bir xil;
  U4 o'lcham o'zgarishi (balandlik 3 marta, burilish 844 va qaytish) — faol nuqta HOZIRGI surilishdan, `scroll` tinglovchisi BITTA;
  U5 nuqtani barmoq bilan bosish (markazidan va 8px tepadan) — o'sha karta; reduced-motion — darhol;
  U6 760 px sichqoncha: nuqta bosilsa ikkinchi karta; Tab bilan nuqtaga kelib Enter — birinchi karta;
  U7 tugma: type=button, nomi — karta sarlavhasi, faqat bittasida aria-current;
  U8 kontrast (kunduzgi / tungi — faqat `data-theme`): faol va faol bo'lmagan nuqta fonga nisbatan ≥ 3:1 (shaffoflik hisobga olinadi);
  U9 Buyurtmalar: `.right-panel` ustun, `.ord-list` balandligi — 900 px dan katta va kichik kenglikda (olib tashlangan eskirgan
     qoidalar ta'sir qilmasdi — ko'rinish o'zgarmagan);
  U10 JS sahifa xatosi (pageerror) yo'q.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan PostgreSQL. Asl kodga (zip 161) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_karusel_nuqta_ui.py
"""
import os
import re
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

OK = FAIL = 0
FAILED = []
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
YORLIQ = "[PG] " if PG_URL else ""


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
        print(f"  ✗ {label}   {str(detail)[:1500]}")


def section(t):
    print(f"\n--- {t} ---")


try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_xato = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_xato = False, f"{type(_e).__name__}: {_e}"

PG_BAZA = "karusel_nuqta_ui162_test"
_T = tempfile.mkdtemp(prefix="kn_ui_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'kn_ui_test.db')}"
os.environ.pop("TENANT_FILTER", None)
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("BACKUP_TELEGRAM_CHAT_ID", None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole                        # noqa: E402

s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "kn_a", "Parol123!", UserRole.ADMIN, "KN admin", company_id=1)
s.commit()
s.close()

KARTA_NOMLARI = ["Buyurtmalar holati", "Ishlab chiqarish"]
# afsona to'la bo'lsin (7 holat) va davrlar katta son — karta balandligi haqiqiy ishdagidek
TOLA_STATUS = {"draft": 3, "new": 12, "in_progress": 27, "coating": 5, "ready": 140, "delivered": 88, "cancelled": 2}
TOLA_DAVR = {"today": 12, "week": 345, "month": 1280}

# `#topGrid` ga ulangan `scroll` tinglovchilari soni (ilgari har `resize` da qo'shilib borardi)
SANOQ = r"""(() => {
  const asl = EventTarget.prototype.addEventListener;
  window.__grid_scroll = 0;
  EventTarget.prototype.addEventListener = function (t, f, o) {
    try { if (this && this.id === 'topGrid' && t === 'scroll') window.__grid_scroll++; } catch (e) {}
    return asl.call(this, t, f, o);
  };
})();"""

HOLAT = r"""() => {
  const g = document.getElementById('topGrid'), d = document.getElementById('topGridDots');
  if (!g) return {xato: 'topGrid yoq'};
  const cs = getComputedStyle(g);
  const kartalar = [...g.children].filter(c => c.classList.contains('card'));
  const gr = g.getBoundingClientRect();
  const korinish = kartalar.map(c => { const b = c.getBoundingClientRect(); const ich = Math.max(0, Math.min(b.right, gr.right) - Math.max(b.left, gr.left));
                                        return Math.round(100 * ich / Math.max(1, b.width)); });
  const kids = d ? [...d.children] : [];
  const dis = d ? getComputedStyle(d).display : null;
  return {vw: innerWidth, display: cs.display, ustunlar: cs.gridTemplateColumns.split(' ').filter(Boolean).length, overflowX: cs.overflowX,
          sl: Math.round(g.scrollLeft), chekka: g.scrollWidth - g.clientWidth, kartalar: kartalar.length,
          karta_top: kartalar.map(c => Math.round(c.getBoundingClientRect().top)), korinish,
          nuqta_display: dis, nuqtalar: kids.length,
          nuqta_korinadi: kids.map(k => { const b = k.getBoundingClientRect(); return dis !== 'none' && b.width > 0 && b.height > 0 && b.left >= 0 && b.right <= innerWidth; }),
          faol: kids.map((k, i) => k.classList.contains('active') ? i : -1).filter(i => i >= 0),
          joriy: kids.map((k, i) => k.getAttribute('aria-current') === 'true' ? i : -1).filter(i => i >= 0),
          teg: kids.map(k => k.tagName.toLowerCase() + ':' + (k.getAttribute('type') || '')),
          nom: kids.map(k => k.getAttribute('aria-label') || ''),
          olcham: kids.map(k => { const b = k.getBoundingClientRect(); return [Math.round(b.width), Math.round(b.height)]; }),
          hujjat_sw: document.documentElement.scrollWidth, tinglovchi: window.__grid_scroll};
}"""

KONTRAST = r"""() => {
  const d = document.getElementById('topGridDots'); if (!d || !d.children.length) return null;
  const rgba = c => { const m = (c.match(/[\d.]+/g) || []).map(Number); return [m[0] || 0, m[1] || 0, m[2] || 0, m.length > 3 ? m[3] : 1]; };
  const fonEl = e => { for (let p = e; p; p = p.parentElement) { const c = rgba(getComputedStyle(p).backgroundColor); if (c[3] > 0) return c; }
                       return rgba(getComputedStyle(document.documentElement).backgroundColor); };
  const lum = c => { const [r, g, b] = c.slice(0, 3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
                     return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const kon = (a, b) => { const x = lum(a), y = lum(b); return Math.round(100 * (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)) / 100; };
  const fon = fonEl(d.parentElement);
  return [...d.children].map(k => {
    // ko'rinadigan nuqta — tugmaning `::before` i (bo'lsa), aks holda tugmaning o'z foni; shaffoflik — o'zi va ota-onalari
    const s = getComputedStyle(k), ps = getComputedStyle(k, '::before');
    let c = rgba(ps.backgroundColor), a = c[3] * Number(ps.opacity), qayer = '::before';
    if (ps.content === 'none' || c[3] === 0) { c = rgba(s.backgroundColor); a = c[3]; qayer = 'tugma'; }
    for (let p = k; p && p !== document.documentElement; p = p.parentElement) a *= Number(getComputedStyle(p).opacity);
    const aralash = [0, 1, 2].map(i => a * c[i] + (1 - a) * fon[i]);
    return {faol: k.classList.contains('active'), kontrast: kon(aralash, fon), rang: 'rgb(' + c.slice(0, 3).join(', ') + ')', qayer,
            shaffoflik: Math.round(a * 100) / 100};
  });
}"""

ORD = r"""() => { const rp = document.querySelector('.right-panel'), ol = document.querySelector('.ord-list');
  return {yon: rp ? getComputedStyle(rp).flexDirection : null, bal: ol ? getComputedStyle(ol).maxHeight : null}; }"""

section("U0. Tayyorgarlik")
check("U0 Python `playwright` bor", PW_BOR, _pw_xato)

import uvicorn                                     # noqa: E402

if PW_BOR:
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
    check("U0b lokal server ishga tushdi", server.started)
    BU = f"http://127.0.0.1:{port}"

    def yonalish(route):
        u = route.request.url
        if re.search(r"chart(\.umd)?(\.min)?\.js", u, re.I):
            return route.fulfill(status=200, content_type="application/javascript",
                                 body="window.Chart = function () { return {destroy() {}, update() {}}; };")
        return route.fulfill(status=204, body="")

    JS_XATO = []

    with sync_playwright() as pw:
        _exe = None
        for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                "chrome-linux", "chrome"))):
            _exe = _y
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()

        def kontekst(w, h=844, tel=None, harakat=None):
            tel = (w < 700) if tel is None else tel
            k = dict(viewport={"width": w, "height": h}, is_mobile=tel, has_touch=tel, timezone_id="Asia/Tashkent", locale="uz-UZ")
            if harakat:
                k["reduced_motion"] = harakat
            ctx = br.new_context(**k)
            ctx.set_default_timeout(15000)
            ctx.route(re.compile(r"^https://(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|api\.qrserver\.com|"
                                 r"cdn\.jsdelivr\.net|unpkg\.com)/.*"), yonalish)
            ctx.add_init_script(SANOQ)
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: JS_XATO.append((w, str(e)[:300])))

            def charts(route):
                try:
                    r = route.fetch()
                    j = r.json()
                    j["statuses"] = dict(TOLA_STATUS)
                    route.fulfill(response=r, json=j)
                except Exception:          # noqa: BLE001
                    route.continue_()
            pg.route("**/api/dashboard/charts", charts)
            pg.route("**/api/dashboard/production-periods", lambda r: r.fulfill(status=200, json=dict(TOLA_DAVR)))
            pg.goto(BU + "/login")
            pg.fill("input[name=username]", "kn_a")
            pg.fill("input[name=password]", "Parol123!")
            pg.press("input[name=password]", "Enter")
            pg.wait_for_load_state("networkidle")
            return ctx, pg

        def ev(pg, kod, arg=None):
            try:
                return pg.evaluate(kod, arg) if arg is not None else pg.evaluate(kod)
            except Exception as ex:        # noqa: BLE001
                return {"js_xato": str(ex)[:300]}

        def xav(f, *a, **k):
            """Brauzer amali — element topilmasa (asl kodda / mutatsiyada) sinov QULAMAYDI, tekshiruv yiqiladi."""
            try:
                return f(*a, **k)
            except Exception as ex:        # noqa: BLE001
                print(f"    (amal bajarilmadi: {getattr(f, '__name__', f)} {a[:1]} — {type(ex).__name__})")
                return None

        def dash(pg):
            xav(pg.goto, BU + "/dashboard")
            xav(pg.wait_for_load_state, "networkidle")
            pg.wait_for_timeout(500)

        def sur(pg, x):
            ev(pg, "(x) => { const g = document.getElementById('topGrid'); g && g.scrollTo({left: x, behavior: 'instant'}); }", x)
            pg.wait_for_timeout(700)

        def oxiri(pg):
            ev(pg, "() => { const g = document.getElementById('topGrid'); g && g.scrollTo({left: g.scrollWidth, behavior: 'instant'}); }")
            pg.wait_for_timeout(700)

        def barmoq(pg, ctx, dx):
            """Haqiqiy barmoq surishi (CDP touchStart → 10 × touchMove → touchEnd); dx < 0 — chapga (keyingi karta)."""
            try:
                cdp = ctx.new_cdp_session(pg)
                b = pg.evaluate("() => { const r = document.getElementById('topGrid').getBoundingClientRect(); "
                                "return {l: r.left, w: r.width, y: r.top + 90}; }")
                x0, y0 = b["l"] + b["w"] * (0.8 if dx < 0 else 0.2), b["y"]
                cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x0, "y": y0}]})
                for i in range(1, 11):
                    cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x0 + dx * i / 10, "y": y0}]})
                    pg.wait_for_timeout(16)
                cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
                cdp.detach()
            except Exception as ex:        # noqa: BLE001
                print(f"    (barmoq surishi bajarilmadi — {type(ex).__name__}: {str(ex)[:120]})")
            pg.wait_for_timeout(1200)

        def nuqta_markazi(pg, i, dy=0):
            return ev(pg, """([i, dy]) => { const d = document.getElementById('topGridDots'); const n = d && d.children[i];
                if (!n) return null; n.scrollIntoView({block: 'center', inline: 'nearest'}); const b = n.getBoundingClientRect();
                const x = b.left + b.width / 2, y = b.top + b.height / 2 + dy; const e = document.elementFromPoint(x, y);
                return {x, y, ustida: !!(e && (e === n || n.contains(e)))}; }""", [i, dy])

        # ══════════════════════════════════════════════════════════════
        section("U1. Kengliklar — panjara (≥ 769) va karusel (≤ 768)")
        # ══════════════════════════════════════════════════════════════
        for w in (1440, 1024, 900, 800, 769):
            ctx, pg = kontekst(w, 900, tel=False)
            dash(pg)
            h = ev(pg, HOLAT)
            check(f"U1 {w}px: panjara, ikki ustun, kartalar yonma-yon; nuqtalar YASHIRIN; sahifa yon tomonga toshmaydi",
                  isinstance(h, dict) and h.get("display") == "grid" and h.get("ustunlar") == 2 and h.get("kartalar") == 2
                  and len(set(h.get("karta_top", [1, 2]))) == 1 and h.get("nuqta_display") == "none" and h.get("hujjat_sw", 9e9) <= w, h)
            ctx.close()
        for w in (768, 760, 600, 414, 390, 375, 360, 320):
            ctx, pg = kontekst(w, 844, tel=(w < 700))
            dash(pg)
            h = ev(pg, HOLAT)
            check(f"U1 {w}px: karusel (flex, yon tomonga suriladi), nuqtalar KO'RINADI — tugmalar, soni kartalar soniga teng (2), ekran "
                  f"ichida, birinchisi faol; sahifa yon tomonga toshmaydi",
                  isinstance(h, dict) and h.get("display") == "flex" and h.get("overflowX") == "auto" and h.get("chekka", 0) > 0
                  and h.get("nuqta_display") == "flex" and h.get("nuqtalar") == 2 == h.get("kartalar")
                  and h.get("nuqta_korinadi") == [True, True] and h.get("teg") == ["button:button"] * 2
                  and h.get("faol") == [0] and h.get("hujjat_sw", 9e9) <= w, h)
            ctx.close()

        # ══════════════════════════════════════════════════════════════
        section("U2–U5. Telefon (390 px)")
        # ══════════════════════════════════════════════════════════════
        ctx, pg = kontekst(390, 844)
        dash(pg)
        h0 = ev(pg, HOLAT)
        check("U7 nuqtalar — `type=button` tugmalar, nomi (aria-label) — karta sarlavhasi, faqat birinchisida aria-current; tugma "
              "(bosish maydoni) kamida 24 × 36 px (umumiy tugma qoidasi — telefonda 36 px)",
              isinstance(h0, dict) and h0.get("teg") == ["button:button"] * 2 and h0.get("nom") == KARTA_NOMLARI and h0.get("joriy") == [0]
              and all(w >= 24 and h >= 35.5 for w, h in h0.get("olcham") or [[0, 0]]), h0)
        jy = ev(pg, """() => { const g = document.getElementById('topGrid'), d = document.getElementById('topGridDots');
            const k = [...g.children].filter(c => c.classList.contains('card')); if (!k.length || !d || !d.children.length) return null;
            const kr = k[0].getBoundingClientRect(), gr = g.getBoundingClientRect();
            const e = document.elementFromPoint(kr.left + 20, kr.bottom - 3);
            const e2 = document.elementFromPoint(kr.left + 20, Math.min(kr.bottom + 2, gr.bottom - 1));   // tasma ostki chekkasi (qator shu ustida)
            const n = d.children[0], ps = getComputedStyle(n, '::before'), nb = n.getBoundingClientRect();
            const markaz = nb.top + nb.height / 2;
            let keyingi = d.nextElementSibling; while (keyingi && keyingi.getBoundingClientRect().height === 0) keyingi = keyingi.nextElementSibling;
            return {karta_ostida: !!(e && e.closest('#topGrid')), ustidagi: e ? (e.id || e.tagName) : null,
                    tasma_ostida: !!(e2 && e2.closest('#topGrid')), ustidagi2: e2 ? (e2.id || e2.tagName) : null,
                    markaz_karta_ostidan: Math.round(markaz - kr.bottom), nuqta_bal: parseFloat(ps.height) || nb.height,
                    keyingi_blok: keyingi ? Math.round(keyingi.getBoundingClientRect().top - (markaz + 3)) : null}; }""")
        check("U7b nuqtalar qatori karta va tasma ostini yopmaydi (karta pastki chetidan 3px yuqori va 2px past nuqta — tasmaniki: surish shu "
              "yerdan ham boshlanadi), nuqta markazi karta ostidan "
              "10–18 px pastda, keyingi blok nuqtadan kamida 10 px pastda",
              isinstance(jy, dict) and jy.get("karta_ostida") and jy.get("tasma_ostida") and 10 <= (jy.get("markaz_karta_ostidan") or 0) <= 18
              and (jy.get("keyingi_blok") is None or jy.get("keyingi_blok") >= 10), jy)
        barmoq(pg, ctx, -250)
        h = ev(pg, HOLAT)
        check("U2a barmoq bilan chapga surildi → ikkinchi karta to'liq ko'rinadi, IKKINCHI nuqta faol (aria-current ham)",
              isinstance(h, dict) and h.get("sl", 0) > 0 and h.get("korinish", [0, 0])[1] >= 95 and h.get("faol") == [1]
              and h.get("joriy") == [1], h)
        oxiri(pg)                          # holat — U2a ga tayanmaydi: ikkinchi kartadan
        h2 = ev(pg, HOLAT)
        barmoq(pg, ctx, 250)
        h = ev(pg, HOLAT)
        check("U2b ikkinchi kartadan barmoq bilan qaytdi → birinchi karta, BIRINCHI nuqta faol",
              isinstance(h2, dict) and h2.get("sl", 0) > 0 and isinstance(h, dict) and h.get("sl") == 0
              and h.get("korinish", [0, 0])[0] >= 95 and h.get("faol") == [0] and h.get("joriy") == [0], [h2, h])
        for x in (60, 140, 200):
            sur(pg, x)
            h = ev(pg, HOLAT)
            kor = h.get("korinish", [0, 0]) if isinstance(h, dict) else [0, 0]
            check(f"U3 qisman surish ({x}px) → snap dan keyin faol nuqta — ko'proq ko'rinayotgan karta",
                  isinstance(h, dict) and h.get("faol") == [0 if kor[0] >= kor[1] else 1] and max(kor) >= 95, h)
        sur(pg, 0)
        oxiri(pg)
        h1 = ev(pg, HOLAT)
        natija = []
        for bal in (760, 844, 700):
            pg.set_viewport_size({"width": 390, "height": bal})
            pg.wait_for_timeout(600)
            natija.append(ev(pg, HOLAT))
        check("U4a ikkinchi kartada turganda balandlik 3 marta o'zgardi (manzil satri) — surilish o'zgarmadi, faol nuqta IKKINCHI qoldi "
              "(ilgari birinchiga qaytardi)",
              isinstance(h1, dict) and h1.get("faol") == [1]
              and all(isinstance(x, dict) and x.get("sl") == h1.get("sl") and x.get("faol") == [1] and x.get("joriy") == [1] for x in natija),
              [h1] + natija)
        pg.set_viewport_size({"width": 844, "height": 390})
        pg.wait_for_timeout(600)
        hb = ev(pg, HOLAT)
        pg.set_viewport_size({"width": 390, "height": 844})
        pg.wait_for_timeout(700)
        hq = ev(pg, HOLAT)
        check("U4b burilish (844 px — panjara, nuqtalar yashirin) va qaytish (390) — faol nuqta ko'rinib turgan karta bilan bir xil",
              isinstance(hb, dict) and hb.get("display") == "grid" and hb.get("nuqta_display") == "none"
              and isinstance(hq, dict) and hq.get("display") == "flex"
              and hq.get("faol") == [0 if hq.get("korinish", [0, 0])[0] >= hq.get("korinish", [0, 0])[1] else 1], [hb, hq])
        check("U4c `#topGrid` ga `scroll` tinglovchisi BITTA (5 o'lcham o'zgarishidan keyin ham; ilgari har `resize` da qo'shilardi)",
              isinstance(hq, dict) and hq.get("tinglovchi") == 1, hq)
        # U5 — nuqtani barmoq bilan bosish
        oxiri(pg)
        m = nuqta_markazi(pg, 0)
        if m:
            xav(pg.touchscreen.tap, m["x"], m["y"])
        pg.wait_for_timeout(1000)
        h = ev(pg, HOLAT)
        check("U5a ikkinchi kartada turib BIRINCHI nuqta barmoq bilan bosildi → birinchi karta, birinchi nuqta faol",
              bool(m) and m.get("ustida") and isinstance(h, dict) and h.get("sl") == 0 and h.get("faol") == [0], [m, h])
        sur(pg, 0)                         # holat — oldingi tekshiruvga tayanmaydi (kech128): birinchi kartadan
        m = nuqta_markazi(pg, 1, -8)
        if m:
            xav(pg.touchscreen.tap, m["x"], m["y"])
        pg.wait_for_timeout(1000)
        h = ev(pg, HOLAT)
        check("U5b birinchi kartada turib IKKINCHI nuqtaning 8px tepasidan bosildi (bosish maydoni nuqtadan katta) → ikkinchi karta, "
              "ikkinchi nuqta faol",
              bool(m) and m.get("ustida") and isinstance(h, dict) and h.get("sl", 0) > 0 and h.get("korinish", [0, 0])[1] >= 95
              and h.get("faol") == [1], [m, h])
        ctx.close()

        ctx, pg = kontekst(390, 844, harakat="reduce")
        dash(pg)
        r = ev(pg, """() => { const g = document.getElementById('topGrid'); const n = document.querySelector('#topGridDots .carousel-dot:nth-child(2)');
            if (!g || !n) return null; g.scrollTo({left: 0, behavior: 'instant'}); n.click();
            return {sl: Math.round(g.scrollLeft), chekka: g.scrollWidth - g.clientWidth}; }""")
        check("U5c «harakatni kamaytirish» sozlamasida nuqta bosilsa karta DARHOL almashadi (silliq aylantirishsiz)",
              isinstance(r, dict) and r.get("chekka", 0) > 0 and abs(r.get("sl", -99) - r.get("chekka", 0)) <= 1, r)
        ctx.close()

        # ══════════════════════════════════════════════════════════════
        section("U6. 760 px — ilova yon paneli, sichqoncha va klaviatura")
        # ══════════════════════════════════════════════════════════════
        ctx, pg = kontekst(760, 900, tel=False)
        dash(pg)
        xav(pg.click, "#topGridDots .carousel-dot:nth-child(2)", timeout=4000)
        pg.wait_for_timeout(1000)
        h = ev(pg, HOLAT)
        check("U6a sichqoncha bilan IKKINCHI nuqta bosildi → «Ishlab chiqarish» kartasi to'liq ko'rinadi, ikkinchi nuqta faol",
              isinstance(h, dict) and h.get("korinish", [0, 0])[1] >= 95 and h.get("faol") == [1], h)
        oxiri(pg)                          # holat — oldingi tekshiruvga tayanmaydi (kech128): ikkinchi kartadan
        f = ev(pg, "() => { const n = document.querySelector('#topGridDots .carousel-dot'); if (!n) return null; n.focus(); "
                   "return document.activeElement === n; }")
        xav(pg.keyboard.press, "Enter")
        pg.wait_for_timeout(1000)
        h = ev(pg, HOLAT)
        check("U6b ikkinchi kartada turib birinchi nuqta klaviatura fokusida (Tab bilan yetiladi) — Enter → birinchi karta, birinchi "
              "nuqta faol",
              f is True and isinstance(h, dict) and h.get("sl") == 0 and h.get("faol") == [0], [f, h])
        tab = []
        dash(pg)                           # fokus boshlanish nuqtasi — sahifa boshi (blur oldingi fokus joyini eslab qoladi)
        for _ in range(80):
            xav(pg.keyboard.press, "Tab")
            t = ev(pg, "() => { const a = document.activeElement; return a && a.classList && a.classList.contains('carousel-dot') ? "
                       "(a.getAttribute('aria-label') || '') : null; }")
            if t:
                tab.append(t)
            if len(tab) >= 2:
                break
        check("U6c Tab bilan ikkala nuqtaga ham yetib boriladi (tartib — kartalar tartibi)", tab == KARTA_NOMLARI, tab)
        ctx.close()

        # ══════════════════════════════════════════════════════════════
        section("U8. Kontrast — kunduzgi va tungi rejim")
        # ══════════════════════════════════════════════════════════════
        for mavzu in ("light", "dark"):
            ctx, pg = kontekst(390, 844)
            dash(pg)
            ev(pg, "(m) => document.documentElement.setAttribute('data-theme', m)", mavzu)
            pg.wait_for_timeout(500)
            k = ev(pg, KONTRAST)
            check(f"U8 {mavzu}: faol va faol bo'lmagan nuqta fonga nisbatan ≥ 3:1 (shaffoflik hisobga olingan; ilgari faol bo'lmagan "
                  f"1.39 / 1.54)", isinstance(k, list) and len(k) == 2 and all(x.get("kontrast", 0) >= 3.0 for x in k), k)
            ctx.close()

        # ══════════════════════════════════════════════════════════════
        section("U9. Buyurtmalar — ko'rinish o'zgarmagan")
        # ══════════════════════════════════════════════════════════════
        for w, kut in ((1440, False), (1000, False), (900, True), (760, True), (390, True)):
            ctx, pg = kontekst(w, 900, tel=(w < 700))
            xav(pg.goto, BU + "/orders")
            xav(pg.wait_for_load_state, "networkidle")
            o = ev(pg, ORD)
            _bal = "280px" if kut else "ekran bo'yicha"
            check(f"U9 {w}px: o'ng panel — ustun (teskari emas), ro'yxat balandligi {_bal}",
                  isinstance(o, dict) and o.get("yon") == "column" and ((o.get("bal") == "280px") if kut else (o.get("bal") not in (None, "280px", "none"))), o)
            ctx.close()

        check("U10 JS sahifa xatosi (pageerror) yo'q", not JS_XATO, JS_XATO[:5])
        br.close()
    server.should_exit = True

print("\n" + "=" * 70)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
