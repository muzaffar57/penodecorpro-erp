#!/usr/bin/env python3
"""
test_taklif_ui.py — kech126 (zip 148) darvozasi: «⚡ TEZ HISOB / 📝 TAKLIFLAR» — HAQIQIY brauzerda (Chromium, Playwright) O'LCHANADI.

EGASI QARORLARI 07.10 (QAYTA SO'RALMAYDI): mijozga loyiha / buyurtma OCHMASDAN tez hisob — buyurtma formasining o'zi «taklif»
rejimida (loyiha o'rniga mijoz ismi / telefoni); saqlanadi («📝 Takliflar»), hujjat «TAKLIF (HISOB-KITOB)»; ombor tegilmaydi;
«olaman» desa — «✅ Rasmiylashtirish»: forma taklif bilan to'ladi, loyiha tanlanadi yoki shu mijoz uchun yangisi ochiladi.
BO'LIMLAR: S — statik (shablon: tugmalar, panel, natija oynasi, eski funksiyalarga ulanish `typeof` bilan — eski sinov qobiqlari
  qulamaydi); P — tayyorgarlik; B — brauzer 1440 px: B1 sahifa (JS xatosiz, tugmalar); B2 «⚡ Tez hisob» rejimi (loyiha yashirin,
  mijoz bloki, banner, sarlavha, muddat / loy ixtiyoriy, zaklat va «Vaqtincha saqlash» yo'q); B3 mijozsiz — kamchiliklar oynasi
  («Taklifni saqlashdan oldin»), so'rov YO'Q; B4 saqlash — `POST /api/takliflar` tanasi (loyihasiz, izoh), natija oynasi (PDF havolasi),
  buyurtma qoralamasi (localStorage) YOZILMAYDI; B5 ro'yxat (holat, summa, son); B6 «✏️ Tahrirlash» — HAMMA saqlangan maydon
  tiklanadi, `PUT`; B7 «✅ Rasmiylashtirish» — yangi loyiha varianti, nom, muddat majburiy, zaklat; saqlash — buyurtma va loyiha ochildi,
  buyurtma sahifasi; B8 «⛔ Bekor qilish» (tasdiq bilan); B9 qidiruv va filtr; B10 «+ Yangi buyurtma» — oddiy forma (taklif
  maydonlari tozalangan); B11 JS xatosi / «Server xatosi» yo'q; R — 756 px (ilova yon paneli) va 390 px (telefon): ro'yxat va forma
  sig'adi, gorizontal aylantirish yo'q; tungi rejim (`data-theme`).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 147) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_taklif_ui.py
"""
import os
import re
import io
import sys
import json
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
PG_BAZA = os.environ.get("TKU_PG_BAZA", "taklif_ui_test")
_T = tempfile.mkdtemp(prefix="taklif_ui_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'taklif_ui_test.db')}"
os.environ.pop("TENANT_FILTER", None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import models                                  # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Project, Inventory, Recipe, RecipeIngredient, Order, Master   # noqa: E402

Taklif = getattr(models, "Taklif", None)           # asl kodda yo'q — QULAMAYDI

YORLIQ = "[PG] " if PG_URL else ""
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


def oqi(yol):
    try:
        with open(os.path.join(ROOT, yol), encoding="utf-8") as f:
            return f.read()
    except Exception:                      # noqa: BLE001
        return ""


def funksiya(src, nom):
    m = re.search(r"(async\s+)?function\s+" + re.escape(nom) + r"\s*\(", src)
    if not m:
        return ""
    j = src.find("{", m.end())
    if j < 0:
        return ""
    d = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            d += 1
        elif src[k] == "}":
            d -= 1
            if d == 0:
                return src[m.start():k + 1]
    return ""


# ══════════════════════════════════════════════════════════════
section("S. Statik — templates/orders.html")
OH = oqi("templates/orders.html")
check("S1 chap panel: «⚡ Tez hisob» («Buyurtmalar: Yaratish» bilan) va «📝 Takliflar» (ko'rish ruxsati, son `#tkSoni`) tugmalari",
      re.search(r"current_user\.ruxsat\('buyurtma', 'yaratish'\) %\}<button type=\"button\" id=\"tezHisobBtn\"", OH) is not None
      and 'id="takliflarBtn"' in OH and 'id="tkSoni"' in OH and 'onclick="tezHisobOch()"' in OH, None)
check("S2 «📝 Takliflar» paneli (qidiruv, 5 filtr, ro'yxat, sahifalash), forma ichida banner, mijoz bloki, yangi loyiha nomi; "
      "natija oynasi yopish belgisi (`data-yopish`) bilan",
      'id="takliflarPanel"' in OH and 'id="tkQidiruv"' in OH and OH.count('class="chip tk-f') == 5 and 'id="tkRoyxat"' in OH
      and 'id="tkBanner"' in OH and 'id="tkMijozBlok"' in OH and 'id="tk_mijoz"' in OH and 'id="tk_telefon"' in OH
      and 'id="tk_izoh"' in OH and 'id="tkYangiLoyihaBlok"' in OH and 'id="tkNatijaOyna"' in OH
      and re.search(r'id="tkNatijaOyna"[\s\S]{0,1500}data-yopish', OH) is not None, None)
_eski = {nom: funksiya(OH, nom) for nom in ("showNewForm", "saveOrder", "submitOrderRequest", "buyurtmaUmumiyKamchiliklar",
                                            "saveDraftLS", "loyihaTanlovi", "showValidationModal", "editSelected", "hideNewForm")}
check("S3 eski funksiyalar yangi yordamchiga FAQAT `typeof` bilan murojaat qiladi (funksiyani kesib yurgizadigan eski sinov "
      "qobiqlari qulamaydi)",
      "typeof taklifRejiminiTozala === 'function'" in _eski["showNewForm"]
      and "typeof taklifRejim !== 'undefined'" in _eski["saveOrder"] and "typeof taklifniYubor === 'function'" in _eski["saveOrder"]
      and "typeof taklifRasmiySorovi === 'function'" in _eski["submitOrderRequest"]
      and "typeof taklifRejim !== 'undefined'" in _eski["buyurtmaUmumiyKamchiliklar"]
      and "typeof taklifRejim !== 'undefined' && taklifRejim) return;" in _eski["saveDraftLS"]
      and "typeof tkLoyihaTanlovi === 'function'" in _eski["loyihaTanlovi"]
      and "typeof taklifRejim !== 'undefined'" in _eski["showValidationModal"]
      and "typeof taklifRejiminiOrnat === 'function'" in _eski["editSelected"], {k: len(v) for k, v in _eski.items()})
_es = _eski["editSelected"]
check("S4 editSelected: 'taklif' / 'rasmiy' rejimi — topshirish holati o'qilmaydi, tayyor mahsulot chegarasi joriy qoldiq, saqlangan "
      "narx (nusxa qoidasi EMAS); eski qatorlar AYNAN",
      "const isTaklif = (mode === 'taklif' || mode === 'rasmiy') && !!preloadedOrder;" in _es
      and "if (!selectedOrderId && !isTaklif) return;" in _es and re.search(r"if \(!isDup\) \{\s*try \{\s*const dr0", _es)
      and "(isDup || isTaklif) ? fp.quantity : (fp.quantity + used)" in _es
      and "if (isDup || _tmSaqlangan === null) row.dataset.fpPrice = fp.unit_price;" in _es
      and "} else if (isTaklif) {" in _es, None)
_skr = "\n".join(m.group(1) for m in re.finditer(r"<script[^>]*>(.*?)</script>", OH, re.S))
_tk_kod = "\n".join(funksiya(OH, n) for n in ("taklifRejiminiTozala", "taklifRejiminiOrnat", "tkLoyihaTanlovi", "tezHisobOch",
                                               "taklifniYubor", "tkNatijaKorsat", "taklifRasmiySorovi", "takliflarOch",
                                               "takliflarChiz", "taklifTahrir", "taklifRasmiy", "taklifBekor", "takliflarYukla"))
check("S5 taklif funksiyalari (13 ta) bor; ularda Jinja ifodasi yo'q (`{{` — sinov qobig'i yiqiladi), foydalanuvchi matni `escapeHtml` bilan",
      len(_tk_kod) > 8000 and "{{" not in _tk_kod and "{%" not in _tk_kod and _tk_kod.count("escapeHtml(") >= 20 and _skr, len(_tk_kod))

# ══════════════════════════════════════════════════════════════
section("P. Tayyorgarlik")
ADMIN, PAROL = "tku_admin", "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, ADMIN, PAROL, UserRole.ADMIN, "Taklif Admin", company_id=1)
prj = Project(company_id=1, project_number="PRJ-001", client_name="Eski Mijoz", project_name="Eski loyiha", total_budget=0, total_paid=0)
peno = Inventory(company_id=1, item_name="UI Penoplast 14P", unit="blok", stock_quantity=100, price_per_unit=1_000_000,
                 volume_per_unit=1.0, is_penoplast=True, category="Penoplast")
akr = Inventory(company_id=1, item_name="UI Akril", unit="kg", stock_quantity=1000, price_per_unit=10_000, category="Kimyo")
usta = Master(company_id=1, name="UI Usta", phone="+998901234567")
s.add_all([prj, peno, akr, usta])
s.commit()
rc = Recipe(company_id=1, name="UI loy", batch_size_kg=100.0)
s.add(rc)
s.commit()
s.add(RecipeIngredient(recipe_id=rc.id, inventory_id=akr.id, quantity_kg=100.0))
s.commit()
P = dict(prj=prj.id, peno=peno.id, rc=rc.id, usta=usta.id)
s.close()
check("P1 tayyorgarlik — loyiha, penoplast, loy retsepti, usta", all(P.values()), P)

# ══════════════════════════════════════════════════════════════
section("B. Brauzer — 1440 px")
try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_xato = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_xato = False, f"{type(_e).__name__}: {_e}"
check("B0 Python `playwright` bor", PW_BOR, _pw_xato)

import uvicorn                                     # noqa: E402


def _port():
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    p = so.getsockname()[1]
    so.close()
    return p


CHART_ORINBOSAR = "window.Chart = function () { return {destroy() {}, update() {}}; };"
DB_TK = []


def tk_hammasi():
    if Taklif is None:
        return []
    s_ = SessionLocal()
    try:
        return [(t.id, t.raqam, t.holat, t.mijoz, float(t.jami), t.order_id) for t in s_.query(Taklif).order_by(Taklif.id).all()]
    finally:
        s_.close()


if PW_BOR:
    port = _port()
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(150):
        if server.started:
            break
        time.sleep(0.1)
    check("B0a lokal server ishga tushdi", server.started)
    BU = f"http://127.0.0.1:{port}"

    def yonalish(route):
        u = route.request.url
        if re.search(r"chart(\.umd)?(\.min)?\.js", u, re.I):
            return route.fulfill(status=200, content_type="application/javascript", body=CHART_ORINBOSAR)
        if u.startswith("https://fonts.googleapis.com/"):
            return route.fulfill(status=200, content_type="text/css", body="")
        return route.fulfill(status=204, body="")

    with sync_playwright() as pw:
        _exe = None
        for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                  "chrome-linux", "chrome"))):
            _exe = _yol
        try:
            br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()
        except Exception as _e:            # noqa: BLE001
            br = None
            check("B0b Chromium ishga tushdi", False, f"{type(_e).__name__}: {_e}")

        JS_XATOLAR = []
        SOROVLAR = []
        NULL_SOROV = []
        MSG_KUZAT = """() => { if (window.__msgOrnatildi) return; window.__msgOrnatildi = true; window.__msgs = [];
            const o = window.showMsg; window.showMsg = function (t, ty) { window.__msgs.push([String(t), ty]); return o(t, ty); }; }"""

        def kontekst(w, tema=None):
            tel = w < 700
            ctx = br.new_context(viewport={"width": w, "height": 900 if not tel else 844}, device_scale_factor=1, is_mobile=tel,
                                 has_touch=tel, timezone_id="Asia/Tashkent", locale="uz-UZ")
            ctx.set_default_timeout(15000)
            ctx.route(re.compile(r"^https://(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|api\.qrserver\.com|"
                                 r"cdn\.jsdelivr\.net|unpkg\.com)/.*"), yonalish)
            if tema:
                # sinov brauzerining O'Z localStorage i (egasining brauzeri emas) — test_u13 kabi
                ctx.add_init_script(f"try {{ localStorage.setItem('theme', '{tema}'); }} catch (e) {{}}")
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: JS_XATOLAR.append(str(e)[:300]))
            pg.on("request", lambda rq: SOROVLAR.append((rq.method, rq.url, rq.post_data)) if rq.method in ("POST", "PUT") else None)
            # bo'sh id li so'rov (`/api/orders/null/…`, `undefined`) — taklif rejimida buyurtma yo'q, bunday so'rov bo'lmasligi SHART
            pg.on("request", lambda rq: NULL_SOROV.append(rq.url) if re.search(r"/(null|undefined|NaN)(/|$|\?)", rq.url) else None)
            pg.goto(BU + "/login")
            pg.fill("input[name=username]", ADMIN)
            pg.fill("input[name=password]", PAROL)
            pg.press("input[name=password]", "Enter")
            pg.wait_for_load_state("networkidle")
            return ctx, pg

        def ev(pg, kod, arg=None):
            try:
                return pg.evaluate(kod, arg) if arg is not None else pg.evaluate(kod)
            except Exception as ex:        # noqa: BLE001
                return {"js_xato": str(ex)[:300]}

        def kut(pg, kod, ms=8000):
            # etalonda ikki to'liq to'plam parallel yuradi (sekin): har kutish — kamida 30 s (shart bajarilsa darrov qaytadi;
            # hamma kutishlar «bo'lishi kerak» sharti — salbiy kutish yo'q, vaqt faqat xatoda ketadi)
            try:
                pg.wait_for_function(kod, timeout=max(ms, 30000))
                return True
            except Exception:              # noqa: BLE001
                return False

        def tana(qism, metod=None):
            for m, u, d in reversed(SOROVLAR):
                if qism in u and (metod is None or m == metod):
                    try:
                        return json.loads(d or "null")
                    except Exception:      # noqa: BLE001
                        return {"xom": d}
            return None

        def koring(pg, sel):
            return ev(pg, "(s) => { const e = document.querySelector(s); if (!e) return null; const cs = getComputedStyle(e);"
                          " return cs.display !== 'none' && cs.visibility !== 'hidden' && e.offsetParent !== null; }", sel)

        def detal_toldir(pg, nom, boyi, qalin, uzun):
            try:
                pg.fill("#items .detal:last-child .i-name", nom, timeout=5000)
                pg.fill("#items .detal:last-child .i-h", str(boyi), timeout=5000)
                pg.fill("#items .detal:last-child .i-w", str(qalin), timeout=5000)
                pg.fill("#items .detal:last-child .i-l", str(uzun), timeout=5000)
            except Exception:              # noqa: BLE001 — asl kodda forma boshqa holatda bo'lishi mumkin: QULAMAYDI
                pass
            ev(pg, "() => { recalcAll(); if (typeof updateLiveStats === 'function') updateLiveStats(); }")

        def bos(pg, sel):
            """Bosish — element yo'q bo'lsa (asl kod) test QULAMAYDI, tekshiruvlar yiqiladi."""
            try:
                pg.click(sel, timeout=5000)
                return True
            except Exception:              # noqa: BLE001
                return False

        def yoz(pg, sel, qiymat):
            try:
                pg.fill(sel, qiymat, timeout=5000)
                return True
            except Exception:              # noqa: BLE001
                return False

        def tanla(pg, sel, qiymat):
            try:
                pg.select_option(sel, qiymat, timeout=5000)
                return True
            except Exception:              # noqa: BLE001
                return False

        if br is not None:
            ctx, pg = kontekst(1440)
            pg.goto(BU + "/orders")
            pg.wait_for_load_state("networkidle")
            ev(pg, MSG_KUZAT)
            check("B1 /orders: JS xatosi yo'q; «⚡ Tez hisob» va «📝 Takliflar» ko'rinadi, son yashirin (taklif yo'q)",
                  not JS_XATOLAR and koring(pg, "#tezHisobBtn") and koring(pg, "#takliflarBtn")
                  and ev(pg, "() => getComputedStyle(document.getElementById('tkSoni')).display") == "none", JS_XATOLAR)
            ev(pg, "() => { try { localStorage.removeItem(ORDER_DRAFT_LS_KEY); } catch (e) {} }")
            bos(pg, "#tezHisobBtn")
            kut(pg, "() => typeof taklifRejim !== 'undefined' && taklifRejim && taklifRejim.tur === 'yangi'")
            kut(pg, "() => (document.activeElement || {}).id === 'tk_mijoz'")
            q2 = ev(pg, """() => ({fokus: (document.activeElement || {}).id,
                rejim: taklifRejim && taklifRejim.tur, sarlavha: document.getElementById('formTitle').textContent,
                loyiha: getComputedStyle(document.getElementById('project_id').closest('.form-group')).display,
                mijoz: getComputedStyle(document.getElementById('tkMijozBlok')).display,
                banner: getComputedStyle(document.getElementById('tkBanner')).display,
                bannerMatn: document.getElementById('tkBanner').innerText,
                muddatYulduz: getComputedStyle(document.getElementById('deadline_input').closest('.form-group').querySelector('.majburiy')).display,
                zaklat: getComputedStyle(document.getElementById('zaklat-field-wrap')).display,
                qoralama: getComputedStyle(document.getElementById('draftSaveBtn')).display,
                tugma: document.querySelector('#newOrderForm .btn-dark').textContent, detallar: document.querySelectorAll('#items .detal').length})""")
            check("B2 «⚡ Tez hisob» — taklif rejimi: loyiha maydoni yashirin, mijoz bloki va banner ko'rinadi, sarlavha, muddat "
                  "majburiy emas, zaklat va «Vaqtincha saqlash» yo'q, tugma «💾 Taklifni saqlash va PDF», bitta bo'sh detal; kursor — mijoz ismida",
                  isinstance(q2, dict) and q2.get("rejim") == "yangi" and q2.get("fokus") == "tk_mijoz" and q2.get("sarlavha") == "⚡ Tez hisob (taklif)"
                  and q2.get("loyiha") == "none" and q2.get("mijoz") != "none" and q2.get("banner") == "block"
                  and "OCHILMAYDI" in (q2.get("bannerMatn") or "") and q2.get("muddatYulduz") == "none" and q2.get("zaklat") == "none"
                  and q2.get("qoralama") == "none" and q2.get("tugma") == "💾 Taklifni saqlash va PDF" and q2.get("detallar") == 1, q2)
            # B2b — «⚡ Tez hisob» bosilgach darrov detal maydoniga yozish boshlansa — kechiktirilgan fokus uni mijoz ismiga tortib olmaydi
            # (o'lchangan: etalonda ~6 dan 1 marta detal o'lchami «20» mijoz maydoniga tushardi)
            q2b = ev(pg, """() => new Promise(r => { tezHisobOch().then(() => {
                const n = document.querySelector('#items .detal .i-name'); if (!n) { r(null); return; }
                n.focus(); setTimeout(() => r({fokus: document.activeElement === n, mijoz: document.getElementById('tk_mijoz').value,
                    rejim: taklifRejim && taklifRejim.tur, detallar: document.querySelectorAll('#items .detal').length}), 250); }); })""")
            check("B2b «⚡ Tez hisob» dan keyin darrov detal maydoniga o'tilsa — kursor o'sha maydonda qoladi (mijoz ismiga tortilmaydi)",
                  isinstance(q2b, dict) and q2b.get("fokus") is True and q2b.get("mijoz") == "" and q2b.get("rejim") == "yangi"
                  and q2b.get("detallar") == 1, q2b)
            # B2c — kech126 (zip 149 — jonli sinov): taklifda to'lov yo'q — hisob panelida «Zaklat» / «Qolgan qarz» yashirin, sarlavha
            PANEL_JS = """() => { const q = id => { const v = document.getElementById(id); return v ? getComputedStyle(v.closest('.sum-item')).display : null; };
                return {s: (document.getElementById('lsSarlavha') || {}).textContent || null, z: q('ls-zaklat'), d: q('ls-debt'),
                        t: q('ls-total'), live: getComputedStyle(document.getElementById('liveStats')).display}; }"""
            q2c = ev(pg, PANEL_JS)
            check("B2c taklifda hisob paneli — sarlavha «Taklif hisob-kitobi», «Zaklat» va «Qolgan qarz» qatorlari yashirin, kelishilgan summa bor",
                  isinstance(q2c, dict) and q2c.get("s") == "Taklif hisob-kitobi" and q2c.get("z") == "none" and q2c.get("d") == "none"
                  and q2c.get("t") not in (None, "none"), q2c)
            _n_post0 = len([x for x in SOROVLAR if "/api/takliflar" in x[1]])
            detal_toldir(pg, "UI Karniz 20x10", 20, 10, 10)
            bos(pg, "#newOrderForm .btn-dark")
            kut(pg, "() => getComputedStyle(document.getElementById('validationModal')).display === 'flex'", 4000)
            q3 = ev(pg, "() => ({t: document.getElementById('validationTitle').textContent, l: document.getElementById('validationList').innerText})")
            check("B3 mijoz ismisiz saqlash — kamchiliklar oynasi «Taklifni saqlashdan oldin»: «Mijoz ismi kiritilmagan»; «Loyiha» / "
                  "«Topshirish sanasi» talab qilinmaydi; so'rov YUBORILMADI",
                  isinstance(q3, dict) and q3.get("t") == "Taklifni saqlashdan oldin" and "Mijoz ismi kiritilmagan" in q3.get("l", "")
                  and "Loyiha tanlanmagan" not in q3.get("l", "") and "Topshirish sanasi" not in q3.get("l", "")
                  and len([x for x in SOROVLAR if "/api/takliflar" in x[1]]) == _n_post0, q3)
            ev(pg, "() => closeValidationModal()")
            yoz(pg, "#tk_mijoz", "Ali Valiyev")
            yoz(pg, "#tk_telefon", "+998 90 111 22 33")
            yoz(pg, "#tk_izoh", "Yetkazib berish alohida")
            yoz(pg, "#base_price", "1 200 000")
            ev(pg, "() => { formatPriceInput(document.getElementById('base_price')); recalcAll(); }")
            tanla(pg, "#master_id", str(P["usta"]))
            yoz(pg, "#final_price", "110 000")
            ev(pg, "() => { formatPriceInput(document.getElementById('final_price')); calcDiscount(); }")
            bos(pg, "#newOrderForm .btn-dark")
            kut(pg, "() => getComputedStyle(document.getElementById('tkNatijaOyna')).display === 'flex'", 8000)
            tb = tana("/api/takliflar", "POST") or {}
            q4 = ev(pg, """() => ({sar: document.getElementById('tkNatijaSarlavha').textContent, mat: document.getElementById('tkNatijaMatn').innerText,
                pdf: document.getElementById('tkNatijaPdf').getAttribute('href'),
                ls: (function () { try { return localStorage.getItem(ORDER_DRAFT_LS_KEY); } catch (e) { return 'xato'; } })(),
                forma: getComputedStyle(document.getElementById('newOrderForm')).display, rejim: taklifRejim})""")
            _db = tk_hammasi()
            check("B4 saqlash — `POST /api/takliflar`: mijoz, telefon, buyurtma (loyihasiz, `is_draft` siz, izoh — `notes`, usta, "
                  "kelishilgan summa, detal); natija oynasi «Taklif T-0001 saqlandi», PDF havolasi; forma yopildi, rejim tozalandi",
                  tb.get("mijoz") == "Ali Valiyev" and tb.get("telefon") == "+998 90 111 22 33"
                  and "project_id" not in (tb.get("buyurtma") or {}) and "is_draft" not in (tb.get("buyurtma") or {})
                  and (tb.get("buyurtma") or {}).get("notes") == "Yetkazib berish alohida"
                  and (tb.get("buyurtma") or {}).get("master_id") == P["usta"] and (tb.get("buyurtma") or {}).get("agreed_amount") == 110000
                  and len((tb.get("buyurtma") or {}).get("items") or []) == 1
                  and isinstance(q4, dict) and q4.get("sar") == "Taklif T-0001 saqlandi" and "110 000" in q4.get("mat", "")
                  and q4.get("pdf") == f"/api/takliflar/{_db[0][0] if _db else 0}/pdf" and q4.get("forma") == "none"
                  and q4.get("rejim") is None and len(_db) == 1, (tb, q4, _db))
            check("B4b buyurtma qoralamasi (localStorage) — taklif rejimida YOZILMAYDI; sahifadan chiqishda ham (pagehide)",
                  isinstance(q4, dict) and q4.get("ls") is None
                  and ev(pg, "() => { tezHisobOch(); return new Promise(r => { const t0 = Date.now(); const qadam = () => {"
                             " const nm = document.querySelector('#newOrderForm .detal .i-name');"
                             " if (!(typeof taklifRejim !== 'undefined' && taklifRejim && nm)) {"
                             " if (Date.now() - t0 > 20000) { r('detal_yoq'); return; } setTimeout(qadam, 100); return; }"
                             " document.getElementById('tk_mijoz').value = 'X'; nm.value = 'Karniz B4b';"
                             " window.dispatchEvent(new Event('pagehide')); let v = null; try { v = localStorage.getItem(ORDER_DRAFT_LS_KEY); }"
                             " catch (e) { v = 'xato'; } r(v); }; qadam(); }); }") is None, q4)
            ev(pg, "() => { taklifRejiminiTozala(true); hideNewForm(); }")
            ev(pg, "() => { const o = document.getElementById('tkNatijaOyna'); if (o) o.style.display = 'none'; takliflarOch(); }")
            kut(pg, "() => document.querySelectorAll('#tkRoyxat .tk-qator').length === 1")
            q5 = ev(pg, """() => ({panel: getComputedStyle(document.getElementById('takliflarPanel')).display,
                qator: (document.querySelector('#tkRoyxat .tk-qator') || {}).innerText || '', son: document.getElementById('tkSoni').textContent,
                sonKor: getComputedStyle(document.getElementById('tkSoni')).display,
                tugmalar: Array.from(document.querySelectorAll('#tkRoyxat .tk-qator .tk-amallar .btn')).map(b => b.textContent.trim())})""")
            check("B5 «📝 Takliflar» ro'yxati: T-0001, «Amalda», mijoz, telefon, summa 110 000, izoh, muddat; tugmalar — PDF, "
                  "Rasmiylashtirish, Tahrirlash, Bekor qilish; chap tugmada son 1",
                  isinstance(q5, dict) and q5.get("panel") == "block" and "T-0001" in q5.get("qator", "") and "Amalda" in q5.get("qator", "")
                  and "Ali Valiyev" in q5.get("qator", "") and "110 000 so'm" in q5.get("qator", "")
                  and "Yetkazib berish alohida" in q5.get("qator", "") and "gacha amal qiladi" in q5.get("qator", "")
                  and q5.get("tugmalar") == ["📄 PDF", "✅ Rasmiylashtirish", "✏️ Tahrirlash", "⛔ Bekor qilish"]
                  and q5.get("son") == "1" and q5.get("sonKor") != "none", q5)
            pg.screenshot(path=os.path.join(_T, "royxat_1440.png"))
            # B6 — tahrir: hamma maydon tiklanadi
            ev(pg, f"() => taklifTahrir({_db[0][0] if _db else 0})")
            kut(pg, "() => typeof taklifRejim !== 'undefined' && taklifRejim && taklifRejim.tur === 'tahrir'")
            kut(pg, "() => { const n = document.querySelector('#items .detal .i-name'); return !!(n && n.value); }")
            pg.wait_for_timeout(300)
            q6 = ev(pg, """() => ({sar: document.getElementById('formTitle').textContent, m: document.getElementById('tk_mijoz').value,
                t: document.getElementById('tk_telefon').value, iz: document.getElementById('tk_izoh').value,
                bp: document.getElementById('base_price').value, fp: document.getElementById('final_price').value,
                us: document.getElementById('master_id').value, nom: (document.querySelector('#items .detal .i-name') || {}).value,
                tur: (document.querySelector('#items .detal .i-type') || {}).value, h: (document.querySelector('#items .detal .i-h') || {}).value,
                w: (document.querySelector('#items .detal .i-w') || {}).value, l: (document.querySelector('#items .detal .i-l') || {}).value,
                jami: document.getElementById('total_sum').textContent, loyiha: getComputedStyle(document.getElementById('project_id').closest('.form-group')).display,
                msgs: (window.__msgs || []).filter(x => /Server xatosi/.test(x[0]))})""")
            check("B6 «✏️ Tahrirlash» — HAMMA saqlangan maydon tiklandi: mijoz, telefon, izoh, asosiy narx, kelishilgan summa, usta, "
                  "detal (nomi, turi, o'lchamlari), jami; loyiha maydoni yashirin; «Server xatosi» yo'q",
                  isinstance(q6, dict) and q6.get("sar") == "Taklifni tahrirlash — T-0001" and q6.get("m") == "Ali Valiyev"
                  and q6.get("t") == "+998 90 111 22 33" and q6.get("iz") == "Yetkazib berish alohida" and q6.get("bp") == "1 200 000"
                  and q6.get("fp") == "110 000" and q6.get("us") == str(P["usta"]) and q6.get("nom") == "UI Karniz 20x10"
                  and q6.get("tur") == "profil" and q6.get("h") == "20" and q6.get("w") == "10" and q6.get("l") == "10"
                  and q6.get("jami") == "120 000 so'm" and q6.get("loyiha") == "none" and not q6.get("msgs") and not NULL_SOROV,
                  (q6, NULL_SOROV))
            yoz(pg, "#items .detal .i-l", "15")
            yoz(pg, "#final_price", "")
            ev(pg, "() => { recalcAll(); calcDiscount(); }")
            bos(pg, "#newOrderForm .btn-dark")
            kut(pg, "() => getComputedStyle(document.getElementById('tkNatijaOyna')).display === 'flex'", 8000)
            tp = tana("/api/takliflar/", "PUT") or {}
            _db2 = tk_hammasi()
            check("B6b saqlash — `PUT /api/takliflar/{id}` (yangi taklif EMAS): uzunlik 15, jami 180 000; natija «yangilandi»",
                  ((tp.get("buyurtma") or {}).get("items") or [{}])[0].get("length") == 15 and len(_db2) == 1 and _db2[0][4] == 180000
                  and "yangilandi" in str(ev(pg, "() => document.getElementById('tkNatijaSarlavha').textContent")), (tp, _db2))
            ev(pg, "() => { document.getElementById('tkNatijaOyna').style.display = 'none'; }")
            pg.screenshot(path=os.path.join(_T, "royxat2_1440.png"))
            # B7 — rasmiylashtirish
            ev(pg, f"() => taklifRasmiy({_db[0][0] if _db else 0})")
            kut(pg, "() => typeof taklifRejim !== 'undefined' && taklifRejim && taklifRejim.tur === 'rasmiy'")
            kut(pg, "() => { const n = document.querySelector('#items .detal .i-name'); return !!(n && n.value); }")
            pg.wait_for_timeout(300)
            q7 = ev(pg, """() => ({sar: document.getElementById('formTitle').textContent, sel: document.getElementById('project_id').value,
                opt: (document.querySelector('#project_id option[value="__taklif"]') || {}).textContent || '',
                yangi: getComputedStyle(document.getElementById('tkYangiLoyihaBlok')).display, nom: document.getElementById('tk_loyiha_nomi').value,
                loyiha: getComputedStyle(document.getElementById('project_id').closest('.form-group')).display,
                mijoz: getComputedStyle(document.getElementById('tkMijozBlok')).display,
                yulduz: getComputedStyle(document.getElementById('deadline_input').closest('.form-group').querySelector('.majburiy')).display,
                zaklat: getComputedStyle(document.getElementById('zaklat-field-wrap')).display,
                qoralama: getComputedStyle(document.getElementById('draftSaveBtn')).display,
                tugma: document.querySelector('#newOrderForm .btn-dark').textContent, jami: document.getElementById('total_sum').textContent,
                yangiYoq: (document.querySelector('#project_id option[value="__yangi"]') || {}).hidden})""")
            check("B7 «✅ Rasmiylashtirish» — loyiha maydoni: «➕ Yangi loyiha — Ali Valiyev (+998 …)» tanlangan, yangi loyiha nomi "
                  "(mijoz ismi), «+ Yangi loyiha yaratish…» yashirin; muddat majburiy, zaklat va «Vaqtincha saqlash» bor; tugma "
                  "«✅ Buyurtmani rasmiylashtirish»; jami taklifdagidek",
                  isinstance(q7, dict) and q7.get("sar") == "Taklifni rasmiylashtirish — T-0001" and q7.get("sel") == "__taklif"
                  and "Yangi loyiha — Ali Valiyev (+998 90 111 22 33)" in q7.get("opt", "") and q7.get("yangi") != "none"
                  and q7.get("nom") == "Ali Valiyev" and q7.get("loyiha") != "none" and q7.get("mijoz") == "none"
                  and q7.get("yulduz") != "none" and q7.get("zaklat") != "none" and q7.get("qoralama") != "none"
                  and q7.get("tugma") == "✅ Buyurtmani rasmiylashtirish" and q7.get("jami") == "180 000 so'm" and q7.get("yangiYoq") is True
                  and not NULL_SOROV, (q7, NULL_SOROV))
            q7d = ev(pg, PANEL_JS)
            check("B7d rasmiylashtirishda hisob paneli — oddiy buyurtmadagidek: «Buyurtma hisob-kitobi», «Zaklat» va «Qolgan qarz» ko'rinadi",
                  isinstance(q7d, dict) and q7d.get("s") == "Buyurtma hisob-kitobi" and q7d.get("z") not in (None, "none")
                  and q7d.get("d") not in (None, "none"), q7d)
            pg.screenshot(path=os.path.join(_T, "rasmiy_1440.png"))
            bos(pg, "#newOrderForm .btn-dark")
            kut(pg, "() => getComputedStyle(document.getElementById('validationModal')).display === 'flex'", 4000)
            q7b = ev(pg, "() => ({t: document.getElementById('validationTitle').textContent, l: document.getElementById('validationList').innerText})")
            check("B7b rasmiylashtirishda — buyurtma qoidalari: «Topshirish sanasi kiritilmagan» (sarlavha «Buyurtmani saqlashdan oldin»)",
                  isinstance(q7b, dict) and q7b.get("t") == "Buyurtmani saqlashdan oldin" and "Topshirish sanasi kiritilmagan" in q7b.get("l", "")
                  and "Mijoz ismi" not in q7b.get("l", ""), q7b)
            ev(pg, "() => closeValidationModal()")
            yoz(pg, "#tk_loyiha_nomi", "Ali Valiyev — uy fasadi")
            yoz(pg, "#deadline_input", "2026-12-20")
            yoz(pg, "#zaklat_amount", "50 000")
            ev(pg, "() => formatPriceInput(document.getElementById('zaklat_amount'))")
            try:
                with pg.expect_navigation(timeout=15000):
                    bos(pg, "#newOrderForm .btn-dark")
            except Exception:              # noqa: BLE001
                pass
            pg.wait_for_load_state("networkidle")
            tr = tana("/rasmiylashtir", "POST") or {}
            _db3 = tk_hammasi()
            s = SessionLocal()
            _ord = s.query(Order).filter(Order.id == (_db3[0][5] if _db3 else -1)).first()
            _ord_v = (float(_ord.total_amount), float(_ord.paid_amount), _ord.project.project_name, _ord.project.client_name,
                      _ord.project.client_phone, _ord.deadline.isoformat()[:10] if _ord.deadline else None) if _ord else None
            s.close()
            check("B7c saqlash — `POST /api/takliflar/{id}/rasmiylashtir` (yangi loyiha: nomi, ism / telefon taklifdan; buyurtma — "
                  "izoh bilan): buyurtma ochildi (180 000, zaklat 50 000 to'landi), yangi loyiha, taklif «rasmiylashtirildi»; "
                  "sahifa buyurtmaga o'tdi",
                  (tr.get("yangi_loyiha") or {}) == {"project_name": "Ali Valiyev — uy fasadi", "client_name": "Ali Valiyev",
                                                     "client_phone": "+998 90 111 22 33"}
                  and (tr.get("buyurtma") or {}).get("notes") == "Yetkazib berish alohida" and "loyiha_id" not in tr
                  and _db3 and _db3[0][2] == "rasmiylashtirildi" and _ord_v
                  and _ord_v[:5] == (180000.0, 50000.0, "Ali Valiyev — uy fasadi", "Ali Valiyev", "+998 90 111 22 33")
                  and _ord_v[5] == "2026-12-20" and "/orders" in pg.url, (tr, _db3, _ord_v, pg.url))
            # B8 — bekor qilish (tasdiq bilan); B9 — qidiruv va filtr
            for _i, _nom in enumerate(("Bekor Mijoz", "Qidiruv Mijoz")):
                ev(pg, f"""() => fetch('/api/takliflar', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{mijoz: '{_nom}', telefon: '+998 91 00{_i} 00 00', buyurtma: {{order_type: 'product',
                    items: [{{name: 'UI detal {_i}', category: 'profil', width: 20, thickness: 10, length: 1, quantity: 1, unit_price: 12000,
                    is_coated: false, penoplast_id: {P['peno']}}}]}}}})}}).then(r => r.status)""")
            pg.goto(BU + "/orders?takliflar=1")
            pg.wait_for_load_state("networkidle")
            ev(pg, MSG_KUZAT)
            kut(pg, "() => document.querySelectorAll('#tkRoyxat .tk-qator').length === 3")
            _bk = [t for t in tk_hammasi() if t[3] == "Bekor Mijoz"]
            ev(pg, f"() => {{ taklifBekor({_bk[0][0] if _bk else 0}); }}")
            kut(pg, "() => getComputedStyle(document.getElementById('ccModal')).display === 'flex'", 4000)
            _tasdiq = ev(pg, "() => document.getElementById('ccModalMessage').innerText")
            _tugmalar8 = ev(pg, "() => [document.getElementById('ccModalTitle').textContent, document.getElementById('ccModalOk').textContent.trim(),"
                                " document.getElementById('ccModalCancel').textContent.trim()]")
            bos(pg, "#ccModalOk")
            kut(pg, "() => /Bekor qilingan/.test(document.getElementById('tkRoyxat').innerText)", 6000)
            _bk2 = [t for t in tk_hammasi() if t[3] == "Bekor Mijoz"]
            check("B8 «⛔ Bekor qilish» — tasdiq oynasi (taklif o'chirilmasligi aytiladi), keyin holat «Bekor qilingan», amallar faqat PDF",
                  "o'chirilmaydi" in str(_tasdiq) and _bk2 and _bk2[0][2] == "bekor"
                  and ev(pg, f"() => Array.from(document.querySelectorAll('#tkRoyxat .tk-qator[data-id=\"{_bk2[0][0] if _bk2 else 0}\"] .tk-amallar .btn')).map(b => b.textContent.trim())")
                  == ["📄 PDF"], (_tasdiq, _bk2))
            # kech126 (zip 149 — zip 148 jonli sinovi): «yo'q» tugmasi ham «Bekor qilish» edi — amal nomi bilan bir xil, adashtirardi
            check("B8b bekor qilish oynasi tugmalari ikki ma'noli emas: «Ha, bekor qilish» / «Yo'q, qolsin», sarlavha «Taklifni bekor qilish»",
                  _tugmalar8 == ["Taklifni bekor qilish", "Ha, bekor qilish", "Yo'q, qolsin"], _tugmalar8)
            yoz(pg, "#tkQidiruv", "910010")
            kut(pg, "() => document.querySelectorAll('#tkRoyxat .tk-qator').length === 1", 5000)
            _q9 = ev(pg, "() => document.getElementById('tkRoyxat').innerText")
            yoz(pg, "#tkQidiruv", "")
            kut(pg, "() => document.querySelectorAll('#tkRoyxat .tk-qator').length === 3", 5000)
            ev(pg, "() => takliflarFiltr('rasmiylashtirildi')")
            kut(pg, "() => document.querySelectorAll('#tkRoyxat .tk-qator').length === 1", 5000)
            _q9b = ev(pg, """() => ({t: document.getElementById('tkRoyxat').innerText, a: document.querySelector('#takliflarPanel .tk-f.active').dataset.f,
                s: Array.from(document.querySelectorAll('#takliflarPanel .tk-f')).map(b => b.dataset.f + ':' + b.querySelector('.f-son').textContent)})""")
            check("B9 qidiruv (telefon raqamlari) — bitta taklif; filtr «Rasmiylashtirilgan» — T-0001 va buyurtma havolasi; tugmalardagi sonlar",
                  "Qidiruv Mijoz" in str(_q9) and "Bekor Mijoz" not in str(_q9) and isinstance(_q9b, dict) and "T-0001" in _q9b.get("t", "")
                  and "Rasmiylashtirildi:" in _q9b.get("t", "") and _q9b.get("a") == "rasmiylashtirildi"
                  and _q9b.get("s") == ["hammasi:3", "faol:1", "muddati_otgan:", "rasmiylashtirildi:1", "bekor:1"], (_q9, _q9b))
            # B12 — mijoz ismida HTML: ro'yxatda MATN bo'lib ko'rinadi (element yaratilmaydi)
            ev(pg, f"""() => fetch('/api/takliflar', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{mijoz: '<b>Qalin</b> & <img src=x onerror="window.__xss=1">', telefon: null, buyurtma: {{order_type: 'product',
                items: [{{name: '<i>Kursiv</i> detal', category: 'profil', width: 20, thickness: 10, length: 1, quantity: 1, unit_price: 12000,
                is_coated: false, penoplast_id: {P['peno']}}}]}}}})}}).then(r => r.status)""")
            ev(pg, "() => { takliflarFiltr('hammasi'); }")
            kut(pg, "() => /Qalin/.test(document.getElementById('tkRoyxat').innerText)", 5000)
            pg.wait_for_timeout(300)
            q12 = ev(pg, """() => { const q = Array.from(document.querySelectorAll('#tkRoyxat .tk-qator')).find(x => /Qalin/.test(x.innerText));
                return q ? {matn: q.querySelector('.tk-mijoz').textContent, b: q.querySelectorAll('.tk-mijoz b, img, .tk-meta i').length,
                            det: q.innerText.includes('<i>Kursiv</i> detal'), xss: window.__xss || 0} : null; }""")
            check("B12 mijoz ismi / detal nomidagi HTML — ro'yxatda oddiy MATN (element yaratilmaydi, skript ishlamaydi)",
                  isinstance(q12, dict) and q12.get("matn", "").startswith('<b>Qalin</b> & <img src=x') and q12.get("b") == 0
                  and q12.get("det") is True and q12.get("xss") == 0, q12)
            # B13 — ro'yxat ochiq turganda buyurtma tanlansa — ro'yxat yashiriladi, buyurtma ko'rinadi
            ev(pg, "() => { const e = document.querySelector('.ord-item'); if (e) e.click(); }")
            kut(pg, "() => getComputedStyle(document.getElementById('orderDetail')).display === 'block'")
            pg.wait_for_timeout(300)
            q13 = ev(pg, """() => ({p: getComputedStyle(document.getElementById('takliflarPanel')).display,
                d: getComputedStyle(document.getElementById('orderDetail')).display})""")
            check("B13 «📝 Takliflar» ochiq turganda buyurtma tanlansa — ro'yxat yashiriladi, buyurtma tafsiloti ko'rinadi",
                  isinstance(q13, dict) and q13.get("p") == "none" and q13.get("d") == "block", q13)
            # B10 — taklif rejimidan «+ Yangi buyurtma»
            ev(pg, "() => tezHisobOch()")
            kut(pg, "() => taklifRejim && taklifRejim.tur === 'yangi'")
            yoz(pg, "#tk_mijoz", "Tozalanadi")
            yoz(pg, "#items .detal .i-name", "Taklif detali")
            ev(pg, "() => showNewForm()")
            q10 = ev(pg, """() => ({rejim: taklifRejim, sar: document.getElementById('formTitle').textContent,
                loyiha: getComputedStyle(document.getElementById('project_id').closest('.form-group')).display,
                mijoz: getComputedStyle(document.getElementById('tkMijozBlok')).display, mv: document.getElementById('tk_mijoz').value,
                nomlar: Array.from(document.querySelectorAll('#items .detal .i-name')).map(i => i.value),
                tugma: document.querySelector('#newOrderForm .btn-dark').textContent,
                taklifOpt: !!document.querySelector('#project_id option[value="__taklif"]')})""")
            check("B10 taklif rejimidan «+ Yangi buyurtma» — oddiy forma: rejim yo'q, loyiha ko'rinadi, mijoz bloki yashirin va bo'sh, "
                  "taklif detali o'tib qolmadi, tugma «💾 Buyurtmani saqlash»",
                  isinstance(q10, dict) and q10.get("rejim") is None and q10.get("sar") == "Yangi buyurtma" and q10.get("loyiha") != "none"
                  and q10.get("mijoz") == "none" and q10.get("mv") == "" and "Taklif detali" not in (q10.get("nomlar") or [])
                  and q10.get("tugma") == "💾 Buyurtmani saqlash" and q10.get("taklifOpt") is False, q10)
            q10b = ev(pg, PANEL_JS)
            check("B10b oddiy buyurtma formasida hisob paneli asliga qaytdi: «Buyurtma hisob-kitobi», «Zaklat» va «Qolgan qarz» ko'rinadi",
                  isinstance(q10b, dict) and q10b.get("s") == "Buyurtma hisob-kitobi" and q10b.get("z") not in (None, "none")
                  and q10b.get("d") not in (None, "none") and q10b.get("live") != "none", q10b)
            _sx = ev(pg, "() => (window.__msgs || []).filter(x => /Server xatosi|Cannot|undefined/.test(x[0]))")
            check("B11 JS xatosi yo'q, «Server xatosi» xabari yo'q", not JS_XATOLAR and not _sx, (JS_XATOLAR, _sx))
            ctx.close()

            # ══════════════════════════════════════════════════════════════
            section("R. 756 px (ilova yon paneli) va 390 px (telefon); tungi rejim")
            for _w in (756, 390):
                for _tema in (None, "dark"):
                    ctx, pg = kontekst(_w, _tema)
                    pg.goto(BU + "/orders?takliflar=1")
                    pg.wait_for_load_state("networkidle")
                    kut(pg, "() => document.querySelectorAll('#tkRoyxat .tk-qator').length >= 4")
                    _r1 = ev(pg, """() => { const d = document.scrollingElement; const p = document.getElementById('takliflarPanel').getBoundingClientRect();
                        const tash = Array.from(document.querySelectorAll('#takliflarPanel .btn, #takliflarPanel .chip, #tkRoyxat .tk-summa, #tkRoyxat .tk-mijoz'))
                          .filter(e => { const r = e.getBoundingClientRect(); return r.width && (r.right > p.right + 1 || r.left < p.left - 1 || e.scrollWidth > e.clientWidth + 1); })
                          .map(e => e.textContent.trim().slice(0, 30));
                        const b = document.querySelector('#tkRoyxat .tk-belgi'); const bc = b ? getComputedStyle(b) : null;
                        return {sw: d.scrollWidth, cw: d.clientWidth, tash, tema: document.documentElement.getAttribute('data-theme'),
                                belgi: bc ? [bc.color, bc.backgroundColor] : null}; }""")
                    _nom = f"{_w} px{' tungi' if _tema else ''}"
                    check(f"R1 {_nom}: «📝 Takliflar» ro'yxati sig'adi — gorizontal aylantirish yo'q, tugma / summa panel chetidan chiqmaydi",
                          isinstance(_r1, dict) and _r1.get("sw", 9999) <= _r1.get("cw", 0) + 1 and not _r1.get("tash")
                          and (_tema is None or _r1.get("tema") == "dark") and _r1.get("belgi") and _r1["belgi"][0] != _r1["belgi"][1], _r1)
                    pg.screenshot(path=os.path.join(_T, f"royxat_{_w}{'_t' if _tema else ''}.png"), full_page=True)
                    ev(pg, "() => tezHisobOch()")
                    kut(pg, "() => taklifRejim && taklifRejim.tur === 'yangi'")
                    _r2 = ev(pg, """() => { const d = document.scrollingElement; const f = document.getElementById('newOrderForm').getBoundingClientRect();
                        const tash = Array.from(document.querySelectorAll('#tkMijozBlok input, #tkMijozBlok textarea, #tkBanner, #newOrderForm .btn-dark'))
                          .filter(e => { const r = e.getBoundingClientRect(); return r.width && (r.right > f.right + 1 || r.left < f.left - 1); })
                          .map(e => e.id || e.className);
                        return {sw: d.scrollWidth, cw: d.clientWidth, tash, mh: document.getElementById('tk_mijoz').getBoundingClientRect().height}; }""")
                    check(f"R2 {_nom}: «⚡ Tez hisob» formasi — mijoz maydonlari, banner, tugma sig'adi; gorizontal aylantirish yo'q",
                          isinstance(_r2, dict) and _r2.get("sw", 9999) <= _r2.get("cw", 0) + 1 and not _r2.get("tash")
                          and (_r2.get("mh") or 0) >= 36, _r2)
                    if _tema is None:
                        _r3 = ev(pg, """() => { const b = Array.from(document.querySelectorAll('.tk-tugmalar .btn'));
                            return b.map(e => { const r = e.getBoundingClientRect(); return {t: e.textContent.trim(), w: r.width, h: r.height, ichi: e.scrollWidth <= e.clientWidth + 1}; }); }""")
                        check(f"R3 {_nom}: chap paneldagi «⚡ Tez hisob» / «📝 Takliflar» — yozuv tugmaga sig'adi, balandlik ≥ 36 px",
                              isinstance(_r3, list) and len(_r3) == 2 and all(x["ichi"] and x["h"] >= 35.5 for x in _r3), _r3)
                    ctx.close()
            br.close()

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("Yiqilganlar:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
