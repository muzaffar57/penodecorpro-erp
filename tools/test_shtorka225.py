#!/usr/bin/env python3
"""
test_shtorka225.py — kech160 (zip 225 «Tizim jurnallari — Sozlamalardan, shtorkalar»; egasi 29.10 18:24, tanlovlar 18:2x, prototip «zo'r boshla»).

NIMA UCHUN KERAK
  Egasi: «Tizim jurnali» chap menyudan olinsin, faqat Sozlamalardan kirilsin; kirganda jurnal yorliqlari yo'qolmasin; bo'limlar shtorkali bo'lsin
  (kerakligini ochib-yopib). Tanlovlar: «Yorliqlar + qaytish», «Yorliq ichidagi bloklar», «Muammolisi ochiq», Sozlamalar bo'limlari ham — «Ha».
QOIDA: chap menyuda `/logs` yo'q, «Sozlamalar» `/sozlamalar` va `/logs` da belgili; Sozlamalar sarlavhasida «📋 Tizim jurnallari»; jurnalda
  «← Sozlamalar» + yorliqlar. Umumiy shtorka (base.html `shtorkaTayyor` / `shtorkaHolat` / `shtorkaHtml`): muammo / filtr qo'llangan — ochiq,
  aks holda brauzer xotirasidagi holat (birinchi marta — yopiq); foydalanuvchi ochgani / yopgani eslab qolinadi, dastur ochgani — yozilmaydi.
BO'LIMLAR
  S — manba (S5 / S6 — «Tizim jurnallari → Sozlamalar» yo'li matnlarda yo'q, O'chirilganlar havolasi ruxsat bilan). M — menyu va o'tish (haqiqiy Chromium, 1440 / 390 px). H — Sozlamalar holatlari (Telegram: 5 holat; yuklanmasa — qizil va ochiq;
  matn sifatida). X — xotira (ochish / yopish eslab qolinadi; muammo — baribir ochiq; dastur ochgani yozilmaydi). F — filtr shtorkasi
  (qo'llangan — ochiq). T — Salomatlik (javob ushlanadi: hammasi joyida — yopiq / yashil; qiymat / farq / kengaytirilmadi / moliya muammosi —
  ochiq / qizil; tekshirilmagan jadval / baza tekshiruvi xatosi — ochiq / qizil (T7 / T8); kengaytirilgan ustunlar — alohida, neytral; korxona admini — faqat «Moliyaviy izchillik»; sarlavha matni escape).
  R — korxona admini (platforma emas): menyu, tugma, «💰 Tekshiruv». K — ko'rinish: 1440 / 1151 / 901 / 390 / 320 px × Lotin / Kirill ×
  tungi rejim — sarlavha ≥ 44 px, toshish yo'q, sahifa gorizontal toshmaydi.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`. (Faqat sahifa o'zgargan — PG bo'limi yo'q.)
Asl kodga (zip 224) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_shtorka225.py
"""
import os
import io
import re
import sys
import json
import time
import socket
import tempfile
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
_T = tempfile.mkdtemp(prefix="k225_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k225.db')}"
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
from models import UserRole, User                  # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    with TestClient(main.app):
        pass
PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k225_pl", PAROL, UserRole.ADMIN, "K225 Platforma", company_id=1)
    auth.create_user(s, "k225_ad", PAROL, UserRole.ADMIN, "K225 Admin", company_id=1)
_u = s.query(User).filter(User.username == "k225_pl").first()
_u.is_platform_admin = True
s.commit()
s.close()

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_B = open(os.path.join(ROOT, "templates", "base.html"), encoding="utf-8").read()
_L = open(os.path.join(ROOT, "templates", "logs.html"), encoding="utf-8").read()
check("S1 base.html: chap menyuda `/logs` bandi yo'q; «Sozlamalar» — `active_page in ('sozlamalar', 'logs')`",
      'href="/logs" class="nav-item' not in _B and "active_page in ('sozlamalar', 'logs')" in _B)
check("S2 base.html: umumiy shtorka — `shtorkaTayyor`, `shtorkaHolat`, `shtorkaHtml`, `shtorkaOch` va `details.sht` uslubi",
      all(f"function {n}(" in _B for n in ("shtorkaTayyor", "shtorkaHolat", "shtorkaHtml", "shtorkaOch")) and "details.sht > summary{" in _B)
check("S3 logs.html: «📋 Tizim jurnallari» (`#soz-jurnal-btn`), «← Sozlamalar» (`.jr-orqaga`), eski «⚙️ Sozlamalar →» yorlig'i yo'q, 7 shtorka",
      'id="soz-jurnal-btn"' in _L and 'class="log-tab tab jr-orqaga" href="/sozlamalar"' in _L and "⚙️ Sozlamalar →" not in _L
      and _L.count('<details class="sht" data-sht="') == 7 and _L.count("</details>") == 7)
_MAIN = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
_PROD = open(os.path.join(ROOT, "templates", "production.html"), encoding="utf-8").read()
_TRASH = open(os.path.join(ROOT, "templates", "trash.html"), encoding="utf-8").read()
_tg_m = re.search(r'TELEGRAM_YUBORILMADI_XABARI = \((.*?)\)\n', _MAIN, re.S)
check("S5 «Tizim jurnallari → Sozlamalar» yo'li endi yo'q — Telegram xabari «Sozlamalar → 📱 Telegram bot», Ishlab chiqarish — «Sozlamalar → "
      "Yo'nalishlar» (review225 T2)",
      _tg_m is not None and "Tizim jurnallari" not in _tg_m.group(1) and "«Sozlamalar» → «📱 Telegram bot»" in _tg_m.group(1)
      and "Tizim jurnallari → Sozlamalar" not in _PROD and "Yangi yo'nalish — Sozlamalar → Yo'nalishlar" in _PROD,
      _tg_m.group(1)[-120:] if _tg_m else None)
check("S6 O'chirilganlar: «Tizim jurnallari →» havolasi `jurnal: Ko'rish` ruxsati bilan (review225 O1)",
      re.search(r"\{% if current_user\.ruxsat\('jurnal', 'korish'\) %\}<a href=\"/logs\"", _TRASH) is not None
      and _TRASH.count('href="/logs"') == 1)
_c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_c.post("/login", data={"username": "k225_pl", "password": PAROL}, follow_redirects=False)
_h_soz, _h_log = _c.get("/sozlamalar").text, _c.get("/logs").text
check("S4 server HTML: /sozlamalar va /logs — 200, menyuda `/logs` yo'q, ikkalasida «Sozlamalar» faol",
      'href="/logs" class="nav-item' not in _h_soz and 'href="/logs" class="nav-item' not in _h_log
      and re.search(r'href="/sozlamalar" class="nav-item\s+active', _h_soz) is not None
      and re.search(r'href="/sozlamalar" class="nav-item\s+active', _h_log) is not None, (_h_soz[:100], _h_log[:100]))

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
SHT = """() => Object.fromEntries([...document.querySelectorAll('details.sht')].filter(d => d.offsetParent !== null).map(d => [d.dataset.sht,
  {ochiq: d.open, holat: d.querySelector('.sht-holat').textContent.trim(), klass: d.querySelector('.sht-holat').className.replace('sht-holat', '').trim(),
   sarl: d.querySelector('.sht-sarl').textContent.trim()}]))"""
MENYU = """() => ({logs: !!document.querySelector('a.nav-item[href="/logs"]'), soz_aktiv: !!document.querySelector('a.nav-item.active[href="/sozlamalar"]'),
  jurnal_btn: (() => { const b = document.getElementById('soz-jurnal-btn'); return b && b.offsetParent !== null; })(),
  orqaga: (() => { const b = document.querySelector('.jr-orqaga'); return b && b.offsetParent !== null; })(),
  yorliqlar: [...document.querySelectorAll('.log-tablar .log-tab')].filter(b => b.offsetParent !== null).map(b => b.textContent.trim())})"""


def kontekst(br, w=1440, h=900, tel=False, yozuv="lotin", tungi=False):
    c = br.new_context(viewport={"width": w, "height": h}, timezone_id="Asia/Tashkent", locale="uz-UZ", is_mobile=tel, has_touch=tel)
    c.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda r: r.fulfill(status=204, body=""))
    _skr = f"localStorage.setItem('erp_script', '{yozuv}');" + ("localStorage.setItem('theme', 'dark');" if tungi else "")
    c.add_init_script(f"try {{ {_skr} }} catch (e) {{}}")
    return c


def kirish(pg, u="k225_pl"):
    pg.goto(BU + "/login")
    pg.fill("input[name=username]", u)
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")


def bos(pg, sel):
    """Element bo'lsa bosadi (asl kodda yo'q tugma — sinov qulamasin, keyingi tekshiruv yiqilsin)."""
    try:
        if pg.locator(sel).count() == 0:
            return False
        pg.click(sel, timeout=5000)
        return True
    except Exception:                      # noqa: BLE001
        return False


def och(pg, yol, kut=700):
    pg.goto(BU + yol)
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(kut)


def tg_javob(pg, javob, status=200):
    def _h(r):
        r.fulfill(status=status, content_type="application/json", body=json.dumps(javob))
    pg.route("**/api/settings/telegram-bot", _h)
    return _h


def salomatlik(pg, javob):
    def _h(r):
        r.fulfill(status=200, content_type="application/json", body=json.dumps(javob))
    pg.route("**/api/system/health-check", _h)
    pg.evaluate("() => { runHealthCheck(); }")
    pg.wait_for_timeout(800)
    pg.unroute("**/api/system/health-check", _h)
    return pg.evaluate(SHT)


with sync_playwright() as pw:
    br = pw.chromium.launch()
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("M — menyu va o'tish")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    with bolim("M"):
        for w, h, tel in ((1440, 900, False), (390, 844, True)):
            ctx = kontekst(br, w, h, tel)
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: XATO.append(str(e)[:300]))
            kirish(pg)
            och(pg, "/sozlamalar")
            _m1 = pg.evaluate(MENYU)
            check(f"M1 {w} px Sozlamalar: menyuda «Tizim jurnallari» yo'q, «Sozlamalar» faol, «📋 Tizim jurnallari» ko'rinadi, jurnal yorliqlari yo'q",
                  _m1["logs"] is False and _m1["soz_aktiv"] and _m1["jurnal_btn"] and not _m1["yorliqlar"], _m1)
            bos(pg, "#soz-jurnal-btn")
            pg.wait_for_load_state("networkidle")
            pg.wait_for_timeout(400)
            _m2 = pg.evaluate(MENYU)
            check(f"M2 {w} px «📋 Tizim jurnallari» → /logs: «← Sozlamalar» + yorliqlar (Kirish tarixi, Xatoliklar, Audit, Salomatlik, Korxonalar), "
                  "menyuda «Sozlamalar» faol",
                  pg.url.split(":%d" % port)[1].startswith("/logs") and _m2["orqaga"] and _m2["soz_aktiv"] and _m2["logs"] is False
                  and _m2["yorliqlar"][:1] == ["← Sozlamalar"] and len(_m2["yorliqlar"]) == 6 and "⚙️ Sozlamalar →" not in _m2["yorliqlar"], (pg.url, _m2))
            bos(pg, ".log-tab[data-tab='health']")
            pg.wait_for_timeout(200)
            _m3 = pg.evaluate(MENYU)
            bos(pg, ".jr-orqaga")
            pg.wait_for_load_state("networkidle")
            _m3_url = pg.url.split(":%d" % port)[1]
            check(f"M3 {w} px boshqa yorliqqa o'tilganda ham «← Sozlamalar» va yorliqlar joyida; «← Sozlamalar» → /sozlamalar",
                  _m3["orqaga"] and len(_m3["yorliqlar"]) == 6 and _m3_url.startswith("/sozlamalar"), (_m3, _m3_url))
            ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("H — Sozlamalar holatlari va X — xotira")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    with bolim("H"):
        ctx = kontekst(br)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: XATO.append(str(e)[:300]))
        kirish(pg)
        och(pg, "/sozlamalar")
        _s0 = pg.evaluate(SHT)
        check("H1 5 shtorka, hammasi yopiq (birinchi marta); holat: nom, «N ta yoqiq», «N ta», Telegram «umumiy bot», Zaxira «butun korxona — 1 fayl» — "
              "hammasi NEYTRAL (yashil ham, qizil ham emas — oddiy ma'lumot; review225 T4 / T5)",
              list(_s0) == ["soz-nom", "soz-tur", "soz-yon", "soz-tg", "soz-zaxira"] and not any(v["ochiq"] for v in _s0.values())
              and _s0["soz-nom"]["holat"] and re.fullmatch(r"\d+ ta yoqiq", _s0["soz-tur"]["holat"]) and re.fullmatch(r"\d+ ta", _s0["soz-yon"]["holat"])
              and _s0["soz-tg"]["holat"] == "umumiy bot" and _s0["soz-zaxira"]["holat"] == "butun korxona — 1 fayl"
              and all(v["klass"] == "" for v in _s0.values()), _s0)
        _hol = {}
        for nom, javob, status, kut_holat, kut_yomon, kut_klass in (
                ("ulangan", {"configured": True, "ulangan": True, "asosiy_muhit": True, "token_hint": "…ab", "bot_username": "k225bot", "chat_id": ""}, 200, "✅ ulangan", False, "yaxshi"),
                ("ulanmagan", {"configured": True, "ulangan": False, "asosiy_muhit": True, "token_hint": "…ab", "chat_id": ""}, 200, "ulanmagan", True, "yomon"),
                ("umumiy", {"configured": False, "uses_system_bot": True, "chat_id": ""}, 200, "umumiy bot", False, ""),
                ("sozlanmagan", {"configured": False, "uses_system_bot": False, "chat_id": ""}, 200, "sozlanmagan", True, "yomon"),
                ("xato", {"detail": "x"}, 500, "yuklanmadi", True, "yomon")):
            _hh = tg_javob(pg, javob, status)
            och(pg, "/sozlamalar")
            pg.unroute("**/api/settings/telegram-bot", _hh)
            _t = pg.evaluate(SHT)["soz-tg"]
            _hol[nom] = _t
            check(f"H2 Telegram «{nom}»: sarlavhada «{kut_holat}», {'qizil va OCHIQ' if kut_yomon else 'yopiq'}, rang «{kut_klass or 'neytral'}»",
                  _t["holat"] == kut_holat and _t["ochiq"] is kut_yomon and _t["klass"] == kut_klass, _t)
        check("X1 dastur ochgan Telegram shtorkasi (muammo) xotiraga YOZILMAGAN (`sht:soz-tg` yo'q)",
              lambda: pg.evaluate("() => localStorage.getItem('sht:soz-tg')") is None, pg.evaluate("() => localStorage.getItem('sht:soz-tg')"))
        bos(pg, 'details.sht[data-sht="soz-tur"] > summary')
        pg.wait_for_timeout(200)
        och(pg, "/sozlamalar")
        _x2 = pg.evaluate(SHT)["soz-tur"]["ochiq"]
        bos(pg, 'details.sht[data-sht="soz-tur"] > summary')
        pg.wait_for_timeout(200)
        och(pg, "/sozlamalar")
        _x3 = pg.evaluate(SHT)["soz-tur"]["ochiq"]
        check("X2 «Mahsulot turlari» ochildi → qayta yuklash — ochiq; yopildi → qayta yuklash — yopiq (brauzer xotirasi)", _x2 is True and _x3 is False, (_x2, _x3))
        _hh = tg_javob(pg, {"configured": False, "uses_system_bot": False, "chat_id": ""})
        och(pg, "/sozlamalar")
        bos(pg, 'details.sht[data-sht="soz-tg"] > summary')
        pg.wait_for_timeout(200)
        _x4a = pg.evaluate("() => [document.querySelector('details.sht[data-sht=\"soz-tg\"]').open, localStorage.getItem('sht:soz-tg')]")
        och(pg, "/sozlamalar")
        _x4b = pg.evaluate(SHT)["soz-tg"]["ochiq"]
        pg.unroute("**/api/settings/telegram-bot", _hh)
        check("X3 muammoli shtorkani foydalanuvchi yopdi (xotirada «0») — keyingi ochilishda muammo bor bo'lsa baribir OCHIQ",
              _x4a == [False, "0"] and _x4b is True, (_x4a, _x4b))
        pg.evaluate("""() => { const d = document.querySelector('details.sht[data-sht="soz-nom"]'); d.removeAttribute('data-majburiy');
            shtorkaHolat('soz-nom', '<img src=x onerror="window.__x225=1">'); }""")
        check("H3 holat matn sifatida (HTML emas): `<img …>` — matn, element yaratilmaydi",
              lambda: pg.evaluate("""() => { const h = document.querySelector('details.sht[data-sht="soz-nom"] .sht-holat');
                return h.textContent.startsWith('<img') && !h.querySelector('img') && !window.__x225; }"""))
        _lk = pg.evaluate("() => { try { localStorage.setItem = () => { throw new Error('yopiq'); }; localStorage.getItem = () => { throw new Error('yopiq'); }; return 1; } catch (e) { return 0; } }")
        check("X4 brauzer xotirasi ishlamasa (yashirin oyna) — shtorka baribir ochiladi / yopiladi, sahifa xatosi yo'q",
              lambda: pg.evaluate("""() => { const d = document.createElement('details'); d.className = 'sht'; d.dataset.sht = 'k225-sinov';
                d.innerHTML = '<summary><span class="sht-str">▶</span><span class="sht-sarl">S</span><span class="sht-holat"></span></summary><div class="sht-ich">i</div>';
                document.body.appendChild(d); shtorkaTayyor(document.body); const a = d.open; d.open = true; return a === false && d.open === true; }""")
              and _lk == 1)

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("F — filtr shtorkasi")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    with bolim("F"):
        och(pg, "/logs?tab=login", 300)
        _f1 = pg.evaluate(SHT)
        och(pg, "/logs?tab=login&k_natija=xato", 300)
        _f2 = pg.evaluate(SHT)
        och(pg, "/logs?tab=activity&a_q=k225", 300)
        _f3 = pg.evaluate(SHT)
        check("F1 Kirish tarixi: filtrsiz — «🔍 Filtr» yopiq; filtr qo'llangan — OCHIQ, «qo'llangan»; Audit jurnali — xuddi shunday",
              _f1.get("jr-kirish-filtr", {}).get("ochiq") is False and _f2["jr-kirish-filtr"]["ochiq"] is True
              and _f2["jr-kirish-filtr"]["holat"] == "qo'llangan" and _f3["jr-audit-filtr"]["ochiq"] is True, (_f1, _f2, _f3))
        check("F2 filtr shtorka ichida — «Ko'rsatish» ishlaydi (forma o'sha, `tab` saqlanadi)",
              lambda: (pg.goto(BU + "/logs?tab=login") or True) and (bos(pg, 'details.sht[data-sht="jr-kirish-filtr"] > summary') or True)
              and (pg.select_option("select[name=k_natija]", "ok", timeout=5000) or True) and (bos(pg, "#kirishFiltr button[type=submit]") or True)
              and (pg.wait_for_load_state("networkidle") or True) and "k_natija=ok" in pg.url and "tab=login" in pg.url, pg.url)

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("T — Salomatlik")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    with bolim("T"):
        och(pg, "/logs?tab=health", 300)
        _yaxshi = {"checked_at": "2026-10-29T13:00:00", "total_checks": 12, "issues_found": 0, "issues": [], "technical_hidden": False,
                   "sxema": {"tekshirildi": True, "jadvallar": 63, "ustunlar": 786, "farqlar": [], "kengaytirilgan": [], "ishga_tushish": {"xatolar": []}},
                   "financial": {"issues_found": 0, "issues": []}}
        _t1 = salomatlik(pg, _yaxshi)
        check("T1 hammasi joyida — 3 shtorka (Qiymatlar, Baza tuzilishi, Moliyaviy izchillik), hammasi YOPIQ, holat yashil",
              list(_t1) == ["jr-qiymat", "jr-sxema", "jr-moliya"] and not any(v["ochiq"] for v in _t1.values())
              and all(v["klass"] == "yaxshi" for v in _t1.values()) and _t1["jr-sxema"]["holat"] == "✅ kod bilan mos", _t1)
        _yomon = json.loads(json.dumps(_yaxshi))
        _yomon["issues_found"] = 2
        _yomon["issues"] = [{"id": 1, "label": "<b>X</b>", "table": "orders", "column": "status", "bad_value": "q", "valid_names": ["a"]},
                            {"id": 2, "label": "Y", "table": "orders", "column": "status", "bad_value": "w", "valid_names": ["a"]}]
        _yomon["sxema"]["farqlar"] = [{"jadval": "orders", "ustun": "payment_status", "kodda": "ENUM", "bazada": "VARCHAR(20)", "tur": "boshqa", "izoh": "x"},
                                      {"jadval": "finished_products", "ustun": "production_status", "kodda": "ENUM", "bazada": "VARCHAR(20)", "tur": "boshqa", "izoh": "y"}]
        _yomon["sxema"]["kengaytirilgan"] = [{"jadval": "activity_logs", "ustun": "new_value", "oldin": "VARCHAR(255)", "keyin": "TEXT"}] * 10
        _yomon["financial"] = {"issues_found": 1, "issues": [{"label": "ORD-1", "type": "debt_mismatch", "detail": "z"}]}
        _t2 = salomatlik(pg, _yomon)
        check("T2 muammolar — Qiymatlar «⚠️ 2 ta noto'g'ri qiymat», Baza «⚠️ 2 ta farq», Moliya «⚠️ 1 ta nomuvofiqlik» — OCHIQ va qizil; "
              "«🔧 Kengaytirilgan ustunlar» (10 ta) — alohida, YOPIQ, neytral",
              _t2["jr-qiymat"] == {"ochiq": True, "holat": "⚠️ 2 ta noto'g'ri qiymat", "klass": "yomon", "sarl": "🔎 Qiymatlar tekshiruvi"}
              and _t2["jr-sxema"]["ochiq"] and _t2["jr-sxema"]["holat"] == "⚠️ 2 ta farq" and _t2["jr-moliya"]["ochiq"]
              and _t2["jr-moliya"]["holat"] == "⚠️ 1 ta nomuvofiqlik" and _t2["jr-keng"]["ochiq"] is False and _t2["jr-keng"]["klass"] == ""
              and _t2["jr-keng"]["holat"].startswith("10 ta"), _t2)
        _x3b = json.loads(json.dumps(_yaxshi))
        _x3b["sxema"]["ishga_tushish"] = {"xatolar": [{"jadval": "orders", "ustun": "x", "xato": "e"}]}
        _t3 = salomatlik(pg, _x3b)
        check("T3 faqat «kengaytirib bo'lmadi» — Baza tuzilishi «⚠️ 1 ta kengaytirilmadi», OCHIQ", _t3["jr-sxema"]["ochiq"]
              and _t3["jr-sxema"]["holat"] == "⚠️ 1 ta kengaytirilmadi", _t3)
        _t4 = salomatlik(pg, {"checked_at": "2026-10-29T13:00:00", "technical_hidden": True, "financial": {"issues_found": 0, "issues": []}})
        check("T4 texnik qism yashirin (korxona admini javobi) — faqat «💰 Moliyaviy izchillik», yopiq", list(_t4) == ["jr-moliya"]
              and _t4["jr-moliya"]["ochiq"] is False, _t4)
        check("T5 sahifadagi xato matni (`<b>X</b>` belgisi) — matn, qalin element yaratilmaydi; ochilgan qiymat bloki ichida",
              lambda: (salomatlik(pg, _yomon) and True) and pg.evaluate("""() => { const d = document.querySelector('details.sht[data-sht="jr-qiymat"]');
                return d.open && d.querySelector('.sht-ich').textContent.includes('<b>X</b>') && !d.querySelector('.sht-ich b'); }"""))
        bos(pg, 'details.sht[data-sht="jr-keng"] > summary')
        pg.wait_for_timeout(200)
        _t6 = salomatlik(pg, _yomon)
        check("T6 «Kengaytirilgan ustunlar» ochildi — qayta «Tekshirish» dan keyin ham ochiq (xotira)", _t6["jr-keng"]["ochiq"] is True, _t6)
        _KOR = """(k) => { const d = document.querySelector('details.sht[data-sht="' + k + '"]'); const i = d && d.querySelector('.sht-ich');
          return i ? {ochiq: d.open, ichi: i.textContent.replace(/\\s+/g, ' ').trim(), korinadi: i.getClientRects().length > 0} : null; }"""
        _x7 = json.loads(json.dumps(_yaxshi))
        _x7["check_errors"] = [{"table": "a", "error": "x"}, {"table": "b", "error": "y"}]
        _t7 = salomatlik(pg, _x7)
        _t7k = pg.evaluate(_KOR, "jr-qiymat")
        check("T7 qiymatlar muammosiz, lekin 2 jadval TEKSHIRILMADI — «🔎 Qiymatlar tekshiruvi» «⚠️ 2 ta jadval tekshirilmadi», qizil, OCHIQ, "
              "ogohlantirish ko'rinadi (review225 T1 — asl kodda doim ko'rinardi)",
              _t7["jr-qiymat"]["holat"] == "⚠️ 2 ta jadval tekshirilmadi" and _t7["jr-qiymat"]["klass"] == "yomon" and _t7["jr-qiymat"]["ochiq"]
              and _t7k and _t7k["korinadi"] and "2 ta jadval tekshirilmadi" in _t7k["ichi"], (_t7, _t7k))
        _x8 = json.loads(json.dumps(_yaxshi))
        _x8["sxema"] = {"tekshirildi": False, "xato": "permission denied for table k225"}
        _t8 = salomatlik(pg, _x8)
        _t8k = pg.evaluate(_KOR, "jr-sxema")
        _x9 = json.loads(json.dumps(_yaxshi))
        _x9["sxema"] = {"tekshirildi": False, "izoh": "SQLite ustun uzunligi va turini tekshirmaydi — sxema tekshiruvi faqat PostgreSQL da"}
        _t9 = salomatlik(pg, _x9)
        check("T8 Baza tuzilishi tekshiruvi XATO bilan — «⚠️ tekshirib bo'lmadi», qizil, OCHIQ, sababi ko'rinadi; SQLite (tekshirilmaydi) — "
              "«tekshirilmadi», neytral, yopiq (review225 T3)",
              _t8["jr-sxema"]["holat"] == "⚠️ tekshirib bo'lmadi" and _t8["jr-sxema"]["klass"] == "yomon" and _t8["jr-sxema"]["ochiq"]
              and _t8k and _t8k["korinadi"] and "permission denied for table k225" in _t8k["ichi"]
              and _t9["jr-sxema"]["holat"] == "tekshirilmadi" and _t9["jr-sxema"]["klass"] == "" and _t9["jr-sxema"]["ochiq"] is False,
              (_t8, _t8k, _t9))
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("R — korxona admini (platforma emas)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    with bolim("R"):
        ctx = kontekst(br)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: XATO.append(str(e)[:300]))
        kirish(pg, "k225_ad")
        och(pg, "/sozlamalar")
        _r1 = pg.evaluate(MENYU)
        _r1s = pg.evaluate(SHT)
        och(pg, "/logs")
        _r2 = pg.evaluate(MENYU)
        check("R1 korxona admini: menyuda «Tizim jurnallari» yo'q, tugma bor; Zaxira bo'limi yo'q (4 shtorka); jurnal — «← Sozlamalar», Kirish, "
              "Audit, «💰 Tekshiruv» (Xatoliklar / Korxonalar yo'q)",
              not _r1["logs"] and _r1["jurnal_btn"] and list(_r1s) == ["soz-nom", "soz-tur", "soz-yon", "soz-tg"]
              and _r2["yorliqlar"] == ["← Sozlamalar", "🔑 Kirish tarixi", "🕓 Audit jurnali", "💰 Tekshiruv"], (_r1, _r1s, _r2))
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("K — ko'rinish")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    with bolim("K"):
        _yomonlar = {}
        OLCH = """() => { const out = [];
          document.querySelectorAll('details.sht').forEach(d => { if (d.offsetParent === null) return; const s = d.querySelector('summary');
            const b = s.getBoundingClientRect(); if (b.height < 43.5) out.push(d.dataset.sht + ' balandlik ' + b.height);
            [...s.children].forEach(c => { if (c.scrollWidth > c.clientWidth + 1) out.push(d.dataset.sht + ' toshdi ' + c.className); });
            if (d.getBoundingClientRect().right > document.documentElement.clientWidth + 0.5) out.push(d.dataset.sht + ' ekrandan chiqdi'); });
          const sah = document.documentElement.scrollWidth - document.documentElement.clientWidth; if (sah > 0) out.push('sahifa toshdi ' + sah);
          return {out: out, n: [...document.querySelectorAll('details.sht')].filter(d => d.offsetParent !== null).length}; }"""
        _olchandi = 0      # review225 T6: asl kodda shtorka yo'q — «toshish yo'q» bo'sh o'lchovdan o'tmasin
        for w, h, tel in ((1440, 900, False), (1151, 900, False), (901, 900, False), (390, 844, True), (320, 640, True)):
            for yozuv, tungi in (("lotin", False), ("kirill", False), ("lotin", True)):
                ctx = kontekst(br, w, h, tel, yozuv, tungi)
                pg = ctx.new_page()
                pg.on("pageerror", lambda e: XATO.append(str(e)[:300]))
                kirish(pg)
                for yol in ("/sozlamalar", "/logs?tab=login"):
                    och(pg, yol, 500)
                    for holat in ("yopiq", "ochiq"):      # odatiy (yopiq) ko'rinish ham, eng uzun (ochiq) ham
                        if holat == "ochiq":
                            pg.evaluate("() => document.querySelectorAll('details.sht').forEach(d => { d.open = true; })")
                            pg.wait_for_timeout(150)
                        _o = pg.evaluate(OLCH)
                        _olchandi += _o["n"]
                        if _o["out"]:
                            _yomonlar[f"{w}_{yozuv}{'_tungi' if tungi else ''}{yol}_{holat}"] = _o["out"]
                ctx.close()
        check("K1 1440 / 1151 / 901 / 390 / 320 px × Lotin / Kirill / tungi: sarlavha ≥ 44 px, matn toshmaydi, shtorka ekrandan chiqmaydi, sahifa "
              "gorizontal toshmaydi (Sozlamalar va Kirish tarixi, shtorkalar yopiq va ochiq; o'lchangan shtorka bor)",
              not _yomonlar and _olchandi >= 15 * 6, (_olchandi, _yomonlar))
        check("K2 sahifa JS xatosi yo'q (hamma bo'limlar)", not XATO, XATO[:3])
    br.close()
server.should_exit = True

print(f"\nNATIJA: {OK} o'tdi, {FAIL} yiqildi")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
