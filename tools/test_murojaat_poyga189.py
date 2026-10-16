#!/usr/bin/env python3
"""
test_murojaat_poyga189.py — kech147 (zip 189): murojaat yozishmasi (`templates/platforma.html` → `mpPastga`) — rasmlar yuklangach eng yangi
xabarga surish POYGASI. HAQIQIY Chromium (Playwright), HAQIQIY joylashuv; funksiya matni `platforma.html` dan AYNAN olinadi (sahifa
BAJARILMAYDI — aniq takrorlanadigan sahna, server kerak emas; rasm so'rovi sinov o'zi javob berguncha ushlab turiladi).

NIMA UCHUN KERAK (O'LCHANGAN — d193 va d197 etalonlarida `tools/test_murojaat_ui.py` B7b og'ir yukda yiqildi: scrollTop 44, oyna eng
pastda EMAS; `work/k189/probe/poyga.py` — aniq takrorlash: scrollTop 220 / 421):
  dastur pastga surgandan keyingi `scroll` hodisasi keyingi kadrda keladi; rasm o'lchami shu orada joylashsa (rasm `load` dan OLDIN)
  ishlovchi `pastda = false` hisoblardi (scrollHeight o'sgan, scrollTop eski) — rasm yuklanganda eng yangi xabarga surilmasdi.
  Endi dastur o'zi surgan joy eslab qolinadi — shu joydagi `scroll` hodisasi foydalanuvchi surishi emas.
Sahnalar: A — poyga (kontent `scroll` hodisasidan oldin o'sadi) → rasm `load` → eng PASTDA; B — foydalanuvchi yuqoriga surdi → rasm
`load` → o'sha joyda qoladi (eng yangi xabarga sakramaydi); C — oddiy holat (poygasiz) → eng PASTDA; S — statik.
Asl kodga (zip 188) qarshi QULAMAYDI — yiqiladi (A).
ISHLATISH: python3 tools/test_murojaat_poyga189.py
"""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:600]}")


def section(t):
    print(f"\n--- {t} ---")


S = open(os.path.join(ROOT, "templates/platforma.html"), encoding="utf-8").read()
i = S.find("function mpPastga(xs) {")
j = S.find("\n}\n", i) + 3 if i >= 0 else -1
FN = S[i:j] if i >= 0 and j > i else ""

section("S. Statik")
check("S1 `mpPastga` platforma.html da bor (funksiya matni olindi)", bool(FN) and FN.count("function mpPastga") == 1, len(FN))
check("S2 dastur o'zi surgan joy eslab qolinadi — shu joydagi `scroll` hodisasi `pastda` ni o'zgartirmaydi",
      "function pastgaSur() { xs.scrollTop = xs.scrollHeight; dastur = xs.scrollTop; }" in FN
      and "if (dastur !== null && Math.abs(xs.scrollTop - dastur) <= 1) return;" in FN
      and "im.addEventListener('load', function () { if (pastda) pastgaSur(); }, {once: true});" in FN)

HTML = ("<!doctype html><html><head><meta charset='utf-8'></head><body style='margin:0'>"
        "<div id='xs' style='height:300px;overflow:auto;border:1px solid #000'>"
        + "".join(f"<p style='height:40px;margin:0'>xabar {k}</p>" for k in range(12))
        + "<img id='im' src='/rasm.png' style='display:block;width:300px'><p id='oxir' style='height:40px;margin:0'>ENG YANGI XABAR</p></div>"
        "<script>" + FN + "</script></body></html>")
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360f8cf000000020001e221bc330000000049454e44ae426082")
HOLAT = ("() => { const xs = document.getElementById('xs'); return {sh: xs.scrollHeight, ch: xs.clientHeight, st: Math.round(xs.scrollTop),"
         " pastda: xs.scrollHeight - xs.clientHeight - xs.scrollTop < 24, rasm: document.getElementById('im').complete}; }")

try:
    from playwright.sync_api import sync_playwright
    PW = True
except Exception as _e:                    # noqa: BLE001
    PW = False
    _pwx = str(_e)

section("P. Chromium sahnalari")
check("P0 Playwright va funksiya matni", PW and bool(FN), _pwx if not PW else len(FN))
if PW and FN:
    with sync_playwright() as pw:
        _exe = sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*", "chrome-linux", "chrome")))
        br = pw.chromium.launch(executable_path=_exe[-1]) if _exe else pw.chromium.launch()

        def sahna(oldin_js, keyin_js):
            """sahifa ochiladi (rasm so'rovi ushlab turiladi) → `oldin_js` (mpPastga va boshqalar) → 300 ms (kadrlar, `scroll` hodisalari) →
            `keyin_js` → rasm javobi → 500 ms → holat"""
            pg = br.new_page(viewport={"width": 400, "height": 600})
            kut = {}
            pg.route("**/rasm.png", lambda route: kut.__setitem__("r", route))
            pg.route("**/sahifa", lambda r: r.fulfill(status=200, content_type="text/html", body=HTML))
            pg.goto("http://sinov189.local/sahifa", wait_until="domcontentloaded")
            pg.evaluate(oldin_js)
            pg.wait_for_timeout(300)
            if keyin_js:
                pg.evaluate(keyin_js)
                pg.wait_for_timeout(300)
            for _ in range(50):
                if "r" in kut:
                    break
                pg.wait_for_timeout(100)
            if "r" in kut:
                kut["r"].fulfill(status=200, content_type="image/png", body=PNG)
            pg.wait_for_timeout(500)
            v = pg.evaluate(HOLAT)
            pg.close()
            return v

        # A — poyga: dastur pastga suradi va SHU vazifada kontent o'sadi (rasm o'lchami joylashgandek) — `scroll` hodisasi keyin keladi
        a = sahna("() => { const xs = document.getElementById('xs'); mpPastga(xs); const d = document.createElement('div'); d.style.height = '200px';"
                  " xs.insertBefore(d, document.getElementById('oxir')); }", None)
        check("A1 poyga: kontent dastur surgandan keyingi `scroll` hodisasidan OLDIN o'sdi → rasm yuklangach oyna eng PASTDA (eng yangi xabar ko'rinadi)",
              a.get("rasm") and a.get("pastda") and a.get("sh", 0) > a.get("ch", 0) + 300, a)
        # B — foydalanuvchi yuqoriga surdi (o'qiyapti) → rasm yuklanganda o'sha joyda qoladi
        b = sahna("() => { mpPastga(document.getElementById('xs')); }", "() => { document.getElementById('xs').scrollTop = 0; }")
        check("B1 foydalanuvchi yuqoriga surgan → rasm yuklanganda o'sha joyda qoladi (eng yangi xabarga sakramaydi)",
              b.get("rasm") and b.get("st") == 0 and not b.get("pastda"), b)
        # C — oddiy holat: dastur suradi, kadrlar o'tadi, rasm yuklanadi
        c = sahna("() => { mpPastga(document.getElementById('xs')); }", None)
        check("C1 oddiy holat: rasm yuklangach oyna eng PASTDA", c.get("rasm") and c.get("pastda"), c)
        br.close()

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
