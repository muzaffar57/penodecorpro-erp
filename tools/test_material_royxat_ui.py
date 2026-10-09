#!/usr/bin/env python3
"""
test_material_royxat_ui.py — kech135 (zip 161): «Materiallar ro'yxati (retsept va tarkib uchun)» ruxsati — HAQIQIY brauzerda (Chromium,
Playwright), HAQIQIY lokal server bilan (uvicorn, test bazasi) O'LCHANADI.

NIMA UCHUN KERAK (O'LCHANGAN — work/k161/olchov161.py, zip 160 kodi, SQLite va PG)
  * faqat «Loy retseptlari» ruxsati bor rol — retsept oynasida material tanlab bo'lmaydi (sabab — «Omborxona → Materiallar» yo'q);
  * faqat «Mahsulot turlari va tarkibi» ruxsati bor rol — tarkib oynasida tanlov XABARSIZ bo'sh («— Material tanlang —» xolos),
    mavjud qatorlarda noto'g'ri «(yashirilgan)»;
  * «Ishlab chiqarish buyurtmalari» ruxsati yo'q rolga «Ishlab chiqarish» yorlig'i ko'rinadi, ro'yxat 403 bilan «Hali ishlab chiqarish
    yo'q» deb yozadi (har ochilishda 403 so'rov).
  EGASI QARORI (09.10 22:0x, tugmali): rollarda belgi — admin xohlasa ochadi, xohlasa yopadi; ro'yxatda — «Nomi va birligi».

BO'LIMLAR
  U1 retsept oynasi (retsept + belgi): tanlash paneli turkumlar bo'yicha, qoldiqsiz; material qo'shib saqlash;  U2 tahrir — qatorlar
  turkum belgisi bilan;  U3 belgisiz rol — sabab yangi ruxsat nomi bilan;  U4 tarkib oynasi (tarkib + belgi): «Nomi — birligi», qoldiq
  yo'q, tanlab saqlash;  U5 tahrir — tanlangan material;  U6 belgisiz rol — oynada sabab, «— Material tanlab bo'lmaydi —», tahrirda
  belgisiz nom, o'zgarishsiz saqlash;  U7 Admin — «— omborda …» avvalgidek, o'chirilgan material «(o'chirilgan)»;  U8 buyurtmalar
  ruxsatisiz — yorliq yo'q, so'rov yo'q, `?po=` — sabab;  U9 buyurtmalar ruxsati bilan — 500 / tarmoq uzilishida jadvalda sabab;
  U10 tarmoq uzilishi (retsept va tarkib) — sabab, qayta ochilganda ro'yxat keladi;  U11 Rollar sahifasi — yangi band (faqat
  Ko'rish), «retsept yoziladi, ro'yxat yo'q» ogohlantirishi, belgilab saqlash;  U12 telefon (390 px);  U13 JS sahifa xatosi yo'q.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan PostgreSQL. Asl kodga (zip 160) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_material_royxat_ui.py
"""
import os
import re
import io
import sys
import glob
import json
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

PG_BAZA = "material_royxat_ui161_test"
_T = tempfile.mkdtemp(prefix="mr_ui_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'mr_ui_test.db')}"
os.environ.pop("TENANT_FILTER", None)
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("BACKUP_TELEGRAM_CHAT_ID", None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, Rol, Inventory, Recipe, RecipeIngredient, Yonalish   # noqa: E402
from production_models import ProductType, BOM, BOMItem   # noqa: E402

HAMMA = ["korish", "yaratish", "tahrirlash", "ochirish"]
BAND = "material_royxat"
BAND_NOMI = "Materiallar ro'yxati (retsept va tarkib uchun)"
RAD = (f"Sizning rolingizda «Retsept va ishlab chiqarish → {BAND_NOMI}» bo'limida «Ko'rish» ruxsati yo'q. "
       "Admin bilan bog'laning.")
AK_RETSEPT = f"Retseptga yangi material qo'shish uchun «{BAND_NOMI}» ham kerak"

# ══════════════════════════════════════════════════════════════
# Fikstura
# ══════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "mru_a", "Parol123!", UserRole.ADMIN, "MRU admin", company_id=1)
    for _u in ("mru_rb", "mru_r", "mru_mb", "mru_m", "mru_mpo"):
        auth.create_user(s, _u, "Parol123!", UserRole.MANAGER, _u.upper(), company_id=1)
ROLLAR = {"mru_rb": {"retsept": HAMMA, BAND: ["korish"]}, "mru_r": {"retsept": HAMMA},
          "mru_mb": {"mahsulot_turi": HAMMA, BAND: ["korish"]}, "mru_m": {"mahsulot_turi": HAMMA},
          "mru_mpo": {"mahsulot_turi": HAMMA, BAND: ["korish"], "ishlab_buyurtma": ["korish"]}}
ROL_ID = {}
for _u, _rx in ROLLAR.items():
    _r = Rol(company_id=1, nom="MRU161 " + _u, kod=None, ruxsatlar=json.dumps(_rx), tavsif="")
    s.add(_r)
    s.flush()
    ROL_ID[_u] = _r.id
    s.query(User).filter(User.username == _u).first().rol_id = _r.id
_rk = Rol(company_id=1, nom="MRU161 Ko'ruvchi", kod=None, ruxsatlar=json.dumps({"retsept": ["korish"]}), tavsif="")
s.add(_rk)
s.flush()
ROL_ID["korish"] = _rk.id
_rbe = Rol(company_id=1, nom="MRU161 Faqat belgi", kod=None, ruxsatlar=json.dumps({BAND: ["korish"]}), tavsif="")
s.add(_rbe)
s.flush()
ROL_ID["belgi"] = _rbe.id


def mat(nom, birlik, kat, stock, narx, base=None, ochir=False):
    m = Inventory(company_id=1, item_name=nom, unit=birlik, base_unit=base, conversion_factor=50 if base else None,
                  stock_quantity=stock, price_per_unit=narx, min_stock=0, category=kat, is_deleted=ochir)
    s.add(m)
    s.flush()
    return m.id


A = mat("MRU Kley", "kg", "Kimyoviy qo'shimchalar", 12.37, 7319)
B = mat("MRU Qum", "qop", "Qattiq qotishmalar", 41.73, 25017, base="kg")
C = mat("MRU Bo'yoq", "l", None, 9.61, 41023)
D = mat("MRU Eski", "kg", "Gips", 5, 100, ochir=True)
R1 = Recipe(company_id=1, name="MRU Kvars", batch_size_kg=120, notes="birinchi")
s.add(R1)
s.flush()
s.add_all([RecipeIngredient(recipe_id=R1.id, inventory_id=A, quantity_kg=2.5),
           RecipeIngredient(recipe_id=R1.id, inventory_id=B, quantity_kg=60)])
_yo = s.query(Yonalish).filter(Yonalish.company_id == 1).first()
PT = ProductType(company_id=1, name="MRU Kafel kley", unit="qop", input_template="quantity_only", pricing_formula="unit_based",
                 yonalish_id=_yo.id if _yo else None)
s.add(PT)
s.flush()
BM = BOM(company_id=1, product_type_id=PT.id, variant_name="Standart", batch_quantity=1)
s.add(BM)
s.flush()
s.add(BOMItem(company_id=1, bom_id=BM.id, inventory_id=A, quantity=0.5, scrap_factor_percent=0))
BMD = BOM(company_id=1, product_type_id=PT.id, variant_name="Eski", batch_quantity=1)
s.add(BMD)
s.flush()
s.add(BOMItem(company_id=1, bom_id=BMD.id, inventory_id=D, quantity=1, scrap_factor_percent=0))
s.commit()
R1_ID, PT_ID, BOM_ID, BOMD_ID = R1.id, PT.id, BM.id, BMD.id
s.close()


def baza_retsept(nom):
    s2 = SessionLocal()
    try:
        r = s2.query(Recipe).filter(Recipe.name == nom).first()
        if r is None:
            return None
        return sorted((i.inventory_id, float(i.quantity_kg))
                      for i in s2.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == r.id).all())
    finally:
        s2.close()


def baza_tarkiblar():
    s2 = SessionLocal()
    try:
        return {b.variant_name: sorted((i.inventory_id, float(i.quantity)) for i in s2.query(BOMItem).filter(BOMItem.bom_id == b.id).all())
                for b in s2.query(BOM).filter(BOM.product_type_id == PT_ID).all()}
    finally:
        s2.close()


def rol_json(rid):
    s2 = SessionLocal()
    try:
        r = s2.query(Rol).filter(Rol.id == rid).first()
        return json.loads(r.ruxsatlar or "{}") if r else None
    finally:
        s2.close()


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
    SOROVLAR = []            # (login, metod, yo'l, holat) — /api/ javoblari
    XABAR_KUZAT = """
    (() => {
      window.__xabarlar = [];
      const kuzat = () => {
        new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(n => {
          if (n.nodeType === 1 && n.style && n.style.position === 'fixed' && String(n.style.zIndex) === '3000')
            window.__xabarlar.push(n.textContent);
        }))).observe(document.body, {childList: true});
      };
      if (document.body) kuzat(); else document.addEventListener('DOMContentLoaded', kuzat);
    })();
    """

    with sync_playwright() as pw:
        _exe = None
        for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                "chrome-linux", "chrome"))):
            _exe = _y
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()

        def kontekst(login, w=1440, h=900):
            tel = w < 700
            ctx = br.new_context(viewport={"width": w, "height": h}, is_mobile=tel, has_touch=tel, timezone_id="Asia/Tashkent",
                                 locale="uz-UZ", screen={"width": w, "height": h})
            ctx.set_default_timeout(15000)
            ctx.route(re.compile(r"^https://(fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|api\.qrserver\.com|"
                                 r"cdn\.jsdelivr\.net|unpkg\.com)/.*"), yonalish)
            ctx.add_init_script(XABAR_KUZAT)
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: JS_XATO.append((login, w, str(e)[:300])))
            pg.on("response", lambda r: SOROVLAR.append((login, r.request.method, r.url.replace(BU, ""), r.status))
                  if "/api/" in r.url else None)
            pg.goto(BU + "/login")
            pg.fill("input[name=username]", login)
            pg.fill("input[name=password]", "Parol123!")
            pg.press("input[name=password]", "Enter")
            pg.wait_for_load_state("networkidle")
            return ctx, pg

        def ev(pg, kod, arg=None):
            try:
                return pg.evaluate(kod, arg) if arg is not None else pg.evaluate(kod)
            except Exception as ex:        # noqa: BLE001
                return {"js_xato": str(ex)[:300]}

        def kut(pg, kod, ms=8000):
            try:
                pg.wait_for_function(kod, timeout=ms)
                return True
            except Exception:              # noqa: BLE001
                return False

        def xav(f, *a, **k):
            """Brauzer amali — element topilmasa (asl kodda / mutatsiyada) sinov QULAMAYDI, tekshiruv yiqiladi."""
            try:
                return f(*a, **k)
            except Exception as ex:        # noqa: BLE001
                print(f"    (amal bajarilmadi: {getattr(f, '__name__', f)} {a[:1]} — {type(ex).__name__})")
                return None

        def ochish(pg, yol):
            xav(pg.goto, BU + yol)
            xav(pg.wait_for_load_state, "networkidle")

        def sorovlar(login, naqsh, n0=0):
            return [x for x in SOROVLAR[n0:] if x[0] == login and re.search(naqsh, x[2])]

        # ── retsept oynasi yordamchilari
        def r_yangi(pg):
            ev(pg, "() => { try { openAddModal(); } catch (e) {} }")
            kut(pg, "getComputedStyle(document.getElementById('addModal')).display === 'flex'")

        def r_tahrir(pg, nom):
            xav(pg.click, f".rec-card:has-text('{nom} retsepti') button[aria-label='Tahrirlash']")
            kut(pg, "getComputedStyle(document.getElementById('editModal')).display === 'flex'")
            pg.wait_for_timeout(300)

        def r_panel(pg, prefix):
            xav(pg.click, f"#{'editModal' if prefix == 'edit' else 'addModal'} .recp-add-btn")
            kut(pg, f"!!document.querySelector('#{prefix}-picker-list .recp-picker-item, #{prefix}-picker-list .recp-picker-empty')")
            return ev(pg, f"""() => {{ const l = document.getElementById('{prefix}-picker-list'); if (!l) return null;
                return {{elem: Array.from(l.querySelectorAll('.recp-picker-item')).map(e => e.textContent.trim()),
                        guruh: Array.from(l.querySelectorAll('.recp-picker-cat')).map(e => e.textContent.trim()),
                        bosh: (l.querySelector('.recp-picker-empty') || {{}}).textContent || null, matn: l.innerText}}; }}""")

        def r_qatorlar(pg, mid):
            return ev(pg, f"""() => Array.from(document.querySelectorAll('#{mid} .recp-ing-row')).map(r => ({{id: r.dataset.inventoryId,
                nom: (r.querySelector('.recp-ing-name') || {{}}).textContent, pill: (r.querySelector('.recp-cat-pill') || {{}}).textContent,
                birlik: (r.querySelector('.recp-ing-qty span') || {{}}).textContent, qid: (r.querySelector('input') || {{}}).id}}))""")

        def r_toast(pg, ms=6000):
            kut(pg, "(() => { const t = document.getElementById('recpToastText'); const o = document.getElementById('recpToastOverlay'); "
                    "return t && o && o.style.display === 'flex' && t.textContent.trim().length > 0; })()", ms)
            return ev(pg, "() => { const o = document.getElementById('recpToastOverlay'); const t = document.getElementById('recpToastText'); "
                          "return (o && t && o.style.display === 'flex') ? t.textContent : null; }")

        # ── tarkib oynasi yordamchilari
        def t_och(pg, bom_id=None):
            ev(pg, f"async () => {{ try {{ await openBomModal({PT_ID}{', ' + str(bom_id) if bom_id else ''}); }} catch (e) {{}} }}")
            kut(pg, "document.querySelectorAll('#bom-items-wrap .bi-inventory').length > 0 && "
                    "Array.from(document.querySelectorAll('#bom-items-wrap .bi-inventory')).every(s => s.options.length > 0)")
            pg.wait_for_timeout(300)

        def t_holat(pg):
            return ev(pg, """() => ({
                qatorlar: Array.from(document.querySelectorAll('#bom-items-wrap .bomitem-row')).map(r => {
                  const s = r.querySelector('.bi-inventory');
                  return {tanlangan: s.value, matn: (s.selectedOptions[0] || {}).textContent,
                          variantlar: Array.from(s.options).map(o => o.textContent), birlik: r.querySelector('.bi-birlik').textContent}; }),
                xato: (() => { const e = document.getElementById('bom-material-xato');
                  return e ? {matn: e.textContent, korinadi: !e.hidden && getComputedStyle(e).display !== 'none'} : null; })(),
                ochiq: document.getElementById('bom-modal').classList.contains('open')})""")

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U1–U3. «Loy retseptlari» oynasi")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        crb, prb = kontekst("mru_rb")
        ochish(prb, "/recipes")
        r_yangi(prb)
        _p = r_panel(prb, "f") or {}
        check("U1a retsept + belgi: tanlash paneli — 3 material (o'chirilgani yo'q), turkumlar bo'yicha guruhlangan, qoldiq / narx yo'q",
              isinstance(_p, dict) and sorted(_p.get("elem") or []) == ["MRU Bo'yoq", "MRU Kley", "MRU Qum"]
              and set(_p.get("guruh") or []) == {"KIMYOVIY QO'SHIMCHALAR", "MINERAL QO'SHIMCHALAR", "BOSHQA MATERIALLAR"}
              and not re.search(r"omborda|12[.,]37|7 ?319", _p.get("matn") or ""), _p)
        xav(prb.click, "#f-picker-list .recp-picker-item:has-text(\"MRU Kley\")")
        prb.wait_for_timeout(300)
        _q = r_qatorlar(prb, "addModal")
        check("U1b tanlangan material qatori — nomi, turkum belgisi «Kimyoviy qo'shimcha», birligi «kg»",
              isinstance(_q, list) and len(_q) == 1 and _q[0].get("nom") == "MRU Kley" and _q[0].get("pill") == "Kimyoviy qo'shimcha"
              and (_q[0].get("birlik") or "").strip() == "kg" and _q[0].get("id") == str(A), _q)
        xav(prb.fill, "#f-name", "MRU Yangi retsept")
        if isinstance(_q, list) and _q:
            xav(prb.fill, f"#{_q[0].get('qid')}", "3.5")
        xav(prb.click, "#recipe-save-btn")
        _t = r_toast(prb)
        check("U1c saqlash — «✓ Retsept qo'shildi!», bazada AYNAN shu material (Kley 3,5)",
              _t == "✓ Retsept qo'shildi!" and baza_retsept("MRU Yangi retsept") == [(A, 3.5)], (_t, baza_retsept("MRU Yangi retsept")))
        prb.wait_for_timeout(1700)
        ochish(prb, "/recipes")
        r_tahrir(prb, "MRU Kvars")
        _q = r_qatorlar(prb, "editModal")
        check("U2a tahrir: qatorlar turkum belgisi bilan (ilgari ro'yxatsiz rolda «Material»), birliklar «kg» / «qop»",
              isinstance(_q, list) and [(x.get("nom"), x.get("pill"), (x.get("birlik") or "").strip()) for x in _q]
              == [("MRU Kley", "Kimyoviy qo'shimcha", "kg"), ("MRU Qum", "Mineral qo'shimcha", "qop")], _q)
        _p = r_panel(prb, "edit") or {}
        check("U2b tahrir tanlash paneli — faqat qo'shilmagan material (Bo'yoq)", (_p.get("elem") or []) == ["MRU Bo'yoq"], _p)
        crb.close()

        cr, pr = kontekst("mru_r")
        ochish(pr, "/recipes")
        r_yangi(pr)
        _p = r_panel(pr, "f") or {}
        check("U3 belgisiz (faqat retsept) rol — tanlash panelida sabab yangi ruxsat NOMI bilan",
              _p.get("bosh") == "Material tanlab bo'lmaydi: " + RAD and not _p.get("elem"), _p)
        cr.close()

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U4–U7. «Mahsulot tarkibi» oynasi")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        cmb, pmb = kontekst("mru_mb")
        ochish(pmb, "/production")
        t_och(pmb)
        _h = t_holat(pmb) or {}
        _v = ((_h.get("qatorlar") or [{}])[0] or {}).get("variantlar") if isinstance(_h, dict) else None
        check("U4a tarkib + belgi: yangi tarkib tanlovi — «— Material tanlang —», «Nomi — birligi» (qoldiq yo'q; Qum — tarkib birligi kg)",
              _v == ["— Material tanlang —", "MRU Bo'yoq — l", "MRU Kley — kg", "MRU Qum — kg"], _h)
        check("U4b sabab oynasi ko'rinmaydi (ro'yxat bor)", isinstance(_h.get("xato"), dict) and not _h["xato"].get("korinadi"), _h.get("xato"))
        xav(pmb.select_option, "#bom-items-wrap .bomitem-row .bi-inventory", str(B))
        xav(pmb.fill, "#bom-items-wrap .bomitem-row .bi-quantity", "20")
        xav(pmb.fill, "#bom-f-variant", "MRU Yozgi")
        _n0 = len(SOROVLAR)
        ev(pmb, "async () => { try { await saveBom(); } catch (e) {} }")
        pmb.wait_for_timeout(800)
        check("U4c tanlab saqlash — POST 200, bazada «MRU Yozgi»: Qum 20, oyna yopildi",
              [x[3] for x in sorovlar("mru_mb", r"^/api/production/boms$", _n0) if x[1] == "POST"] == [200]
              and baza_tarkiblar().get("MRU Yozgi") == [(B, 20.0)] and not (t_holat(pmb) or {}).get("ochiq"),
              (sorovlar("mru_mb", r"boms", _n0), baza_tarkiblar()))
        t_och(pmb, BOM_ID)
        _h = t_holat(pmb) or {}
        _q0 = ((_h.get("qatorlar") or [{}])[0] or {}) if isinstance(_h, dict) else {}
        check("U5 tahrir: mavjud material tanlangan — «MRU Kley — kg» (belgisiz), birlik «kg»",
              _q0.get("tanlangan") == str(A) and _q0.get("matn") == "MRU Kley — kg" and _q0.get("birlik") == "kg", _h)
        ev(pmb, "() => closeModal('bom-modal')")
        cmb.close()

        cm, pm = kontekst("mru_m")
        ochish(pm, "/production")
        t_och(pm)
        _h = t_holat(pm) or {}
        check("U6a belgisiz (faqat tarkib) rol: oynada sabab — «Material tanlab bo'lmaydi: …» (ilgari XABARSIZ bo'sh tanlov)",
              isinstance(_h.get("xato"), dict) and _h["xato"].get("korinadi") and _h["xato"].get("matn") == "Material tanlab bo'lmaydi: " + RAD,
              _h.get("xato"))
        check("U6b yangi qator tanlovi — «— Material tanlab bo'lmaydi —» (bitta variant)",
              [q.get("variantlar") for q in (_h.get("qatorlar") or [])] == [["— Material tanlab bo'lmaydi —"]], _h.get("qatorlar"))
        ev(pm, "() => closeModal('bom-modal')")
        t_och(pm, BOM_ID)
        _h = t_holat(pm) or {}
        _q0 = ((_h.get("qatorlar") or [{}])[0] or {}) if isinstance(_h, dict) else {}
        check("U6c tahrir: mavjud material — faqat nomi «MRU Kley» (ilgari «(yashirilgan)»), sabab ko'rinadi",
              _q0.get("tanlangan") == str(A) and _q0.get("matn") == "MRU Kley" and (_h.get("xato") or {}).get("korinadi"), _h)
        _asl = baza_tarkiblar().get("Standart")
        _n0 = len(SOROVLAR)
        ev(pm, "async () => { try { await saveBom(); } catch (e) {} }")
        pm.wait_for_timeout(800)
        check("U6d o'zgarishsiz saqlash — PUT 200, tarkib o'zgarmadi (Kley 0,5)",
              [x[3] for x in sorovlar("mru_m", r"^/api/production/boms/\d+$", _n0) if x[1] == "PUT"] == [200]
              and baza_tarkiblar().get("Standart") == _asl == [(A, 0.5)], (sorovlar("mru_m", r"boms", _n0), baza_tarkiblar()))

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U8. «Ishlab chiqarish buyurtmalari» ruxsatisiz — yorliq va so'rov yo'q")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        _n0 = len(SOROVLAR)
        ochish(pm, "/production")
        pm.wait_for_timeout(500)
        _y = ev(pm, "() => Array.from(document.querySelectorAll('.prod-tab')).map(t => t.dataset.tab)")
        check("U8a faqat «Mahsulot turlari» yorlig'i (ilgari «Ishlab chiqarish» ham — 403 bilan «Hali ishlab chiqarish yo'q»)",
              _y == ["types"], _y)
        check("U8b sahifa ochilganda `/api/production/orders` so'ralmaydi (ilgari har ochilishda 403)",
              not sorovlar("mru_m", r"^/api/production/orders", _n0), sorovlar("mru_m", r"^/api/production/orders", _n0))
        ev(pm, "async () => { try { await switchProdTab('orders'); } catch (e) {} }")
        pm.wait_for_timeout(400)
        _a = ev(pm, "() => (document.querySelector('.prod-panel.active') || {}).id")
        check("U8c `switchProdTab('orders')` — «Mahsulot turlari» qoladi, so'rov yo'q",
              _a == "panel-types" and not sorovlar("mru_m", r"^/api/production/orders", _n0), _a)
        ochish(pm, "/production?po=5")
        pm.wait_for_timeout(600)
        # xabar sahifa skripti ishlaganda (DOMContentLoaded dan OLDIN) chiqadi — kuzatuvchi ulanmagan bo'lishi mumkin: hozir ekrandagi
        # xabar (4 s turadi) ham o'qiladi
        _x = ev(pm, "() => window.__xabarlar.concat(Array.from(document.body.children).filter(e => e.style && "
                    "e.style.position === 'fixed' && String(e.style.zIndex) === '3000').map(e => e.textContent))")
        check("U8d `?po=5` (Tayyor mahsulotlardan havola) — sabab xabari, so'rov yo'q",
              isinstance(_x, list) and any("«Ishlab chiqarish buyurtmalari»" in m and "ruxsati yo'q" in m for m in _x)
              and not sorovlar("mru_m", r"^/api/production/orders", _n0), _x)
        cm.close()

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U9. Buyurtmalar ruxsati bilan — xato sababi jadvalda")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        cpo, ppo = kontekst("mru_mpo")
        ochish(ppo, "/production")
        _y = ev(ppo, "() => Array.from(document.querySelectorAll('.prod-tab')).map(t => t.dataset.tab)")
        check("U9a ruxsat bor — ikkala yorliq", _y == ["types", "orders"], _y)
        _poy = re.compile(r".*/api/production/orders\?oy=.*")
        xav(ppo.route, _poy, lambda route: route.fulfill(status=500, content_type="application/json",
                                                        body=json.dumps({"detail": "MRU sinov xatosi"})))
        ev(ppo, "async () => { try { await switchProdTab('orders'); } catch (e) {} }")
        kut(ppo, "((document.getElementById('po-list') || {}).textContent || '').includes('MRU sinov xatosi')", 5000)
        _m = ev(ppo, "() => (document.getElementById('po-list') || {}).textContent")
        check("U9b server xatosi (500) — jadvalda SABABI (ilgari «Hali ishlab chiqarish yo'q»)",
              isinstance(_m, str) and "MRU sinov xatosi" in _m and "Hali ishlab chiqarish yo'q" not in _m, _m)
        xav(ppo.unroute, _poy)
        xav(ppo.route, _poy, lambda route: route.abort())
        ev(ppo, "async () => { try { await loadProductionOrders(); } catch (e) {} }")
        kut(ppo, "((document.getElementById('po-list') || {}).textContent || '').includes('aloqa')", 5000)
        _m = ev(ppo, "() => (document.getElementById('po-list') || {}).textContent")
        check("U9c tarmoq uzilishi — «Server bilan aloqa yo'q — ishlab chiqarishlar ro'yxati yuklanmadi»",
              isinstance(_m, str) and "Server bilan aloqa yo'q — ishlab chiqarishlar ro'yxati yuklanmadi" in _m, _m)
        xav(ppo.unroute, _poy)
        ev(ppo, "async () => { try { await loadProductionOrders(); } catch (e) {} }")
        kut(ppo, "((document.getElementById('po-list') || {}).textContent || '').includes('Hali ishlab')", 5000)
        _m = ev(ppo, "() => (document.getElementById('po-list') || {}).textContent")
        check("U9d qayta yuklanganda (javob bor, ro'yxat bo'sh) — «Hali ishlab chiqarish yo'q», sabab qolmaydi",
              isinstance(_m, str) and "Hali ishlab chiqarish yo'q" in _m and "aloqa" not in _m, _m)
        cpo.close()

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U7. Admin — avvalgidek, o'chirilgan material")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        ca, pa = kontekst("mru_a")
        ochish(pa, "/production")
        t_och(pa)
        _h = t_holat(pa) or {}
        _v = ((_h.get("qatorlar") or [{}])[0] or {}).get("variantlar") if isinstance(_h, dict) else None
        check("U7a Admin: tanlov «— omborda …» (ombor birligi) — avvalgidek",
              _v == ["— Material tanlang —", "MRU Bo'yoq — omborda 9,61 l", "MRU Kley — omborda 12,37 kg", "MRU Qum — omborda 41,73 qop"],
              _v)
        ev(pa, "() => closeModal('bom-modal')")
        t_och(pa, BOMD_ID)
        _h = t_holat(pa) or {}
        _q0 = ((_h.get("qatorlar") or [{}])[0] or {}) if isinstance(_h, dict) else {}
        check("U7b Omborxonadan o'chirilgan material — «MRU Eski (o'chirilgan)» (ilgari «(yashirilgan)»), sabab oynasi yo'q",
              _q0.get("tanlangan") == str(D) and _q0.get("matn") == "MRU Eski (o'chirilgan)"
              and not (_h.get("xato") or {"korinadi": True}).get("korinadi"), _h)
        ev(pa, "() => closeModal('bom-modal')")

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U10. Tarmoq uzilishi — sabab, qayta ochilganda ro'yxat")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        _mr = re.compile(r".*/api/material-royxati$")
        crb, prb = kontekst("mru_rb")
        xav(prb.route, _mr, lambda route: route.abort())
        ochish(prb, "/recipes")
        r_yangi(prb)
        _p = r_panel(prb, "f") or {}
        check("U10a retsept: tarmoq uzilishi — «Material tanlab bo'lmaydi: Server bilan aloqa yo'q — materiallar ro'yxati yuklanmadi»",
              _p.get("bosh") == "Material tanlab bo'lmaydi: Server bilan aloqa yo'q — materiallar ro'yxati yuklanmadi", _p)
        xav(prb.unroute, _mr)
        ev(prb, "() => { try { closeIngredientPicker('f'); } catch (e) {} }")
        _p = r_panel(prb, "f") or {}
        check("U10b panel qayta ochilganda ro'yxat qayta so'raladi — 3 material", len(_p.get("elem") or []) == 3, _p)
        crb.close()
        cmb, pmb = kontekst("mru_mb")
        xav(pmb.route, _mr, lambda route: route.abort())
        ochish(pmb, "/production")
        t_och(pmb)
        _h = t_holat(pmb) or {}
        check("U10c tarkib: tarmoq uzilishi — oynada sabab «… Server bilan aloqa yo'q — materiallar ro'yxati yuklanmadi»",
              (_h.get("xato") or {}).get("korinadi")
              and (_h.get("xato") or {}).get("matn") == "Material tanlab bo'lmaydi: Server bilan aloqa yo'q — materiallar ro'yxati yuklanmadi",
              _h.get("xato"))
        ev(pmb, "() => closeModal('bom-modal')")
        xav(pmb.unroute, _mr)
        t_och(pmb)
        _h = t_holat(pmb) or {}
        check("U10d oyna qayta ochilganda — ro'yxat keldi (4 variant), sabab yashirindi",
              len(((_h.get("qatorlar") or [{}])[0] or {}).get("variantlar") or []) == 4 and not (_h.get("xato") or {}).get("korinadi"), _h)
        ev(pmb, "() => closeModal('bom-modal')")
        cmb.close()

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U11. «Rollar» sahifasi")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        def rol_qatori(pg, band):
            return ev(pg, f"""() => {{ const cb = document.querySelector('.rl-cb[data-band="{band}"]');
                const tr = cb ? cb.closest('tr') : null; if (!tr) return null;
                return {{nom: (tr.querySelector('.rl-band-nom') || {{}}).textContent, izoh: (tr.querySelector('.rl-band-izoh') || {{}}).textContent,
                  ogoh: Array.from(tr.querySelectorAll('.rl-band-ogoh')).map(e => e.textContent.trim()),
                  belgilar: Array.from(tr.querySelectorAll('td')).slice(1).map(td => td.querySelector('.rl-cb') ? td.querySelector('.rl-cb').dataset.amal
                                                                                    : td.textContent.trim())}}; }}""")

        def rol_tanla(pg, rid):
            ev(pg, f"async () => {{ try {{ await rolniTanla({rid}, true); }} catch (e) {{}} }}")
            pg.wait_for_timeout(300)

        ochish(pa, "/rollar")
        kut(pa, "!!document.querySelector('.rl-cb')")
        rol_tanla(pa, ROL_ID["mru_r"])
        _b = rol_qatori(pa, BAND)
        check("U11a yangi band qatori — nomi, izohi, faqat «Ko'rish» katagi (qolgani «—»)",
              isinstance(_b, dict) and _b.get("nom") == BAND_NOMI and "nomi va birligi" in (_b.get("izoh") or "")
              and _b.get("belgilar") == ["korish", "—", "—", "—"], _b)
        _rq = rol_qatori(pa, "retsept")
        check("U11b retsept yozadigan, ro'yxatsiz rol — «Loy retseptlari» qatorida sariq ogohlantirish",
              isinstance(_rq, dict) and AK_RETSEPT in (_rq.get("ogoh") or []), _rq)
        xav(pa.click, f'.rl-cb[data-band="{BAND}"][data-amal="korish"]')
        pa.wait_for_timeout(200)
        _rq = rol_qatori(pa, "retsept")
        check("U11c belgi qo'yilgach — ogohlantirish yo'qoldi", isinstance(_rq, dict) and AK_RETSEPT not in (_rq.get("ogoh") or []), _rq)
        ev(pa, "async () => { try { await rolniSaqla(); } catch (e) {} }")
        pa.wait_for_timeout(800)
        check("U11d «Saqlash» — bazada rolda `material_royxat: [korish]`", (rol_json(ROL_ID["mru_r"]) or {}).get(BAND) == ["korish"],
              rol_json(ROL_ID["mru_r"]))
        rol_tanla(pa, ROL_ID["korish"])
        _rq = rol_qatori(pa, "retsept")
        check("U11e faqat ko'radigan retsept roli — ogohlantirish yo'q", isinstance(_rq, dict) and not (_rq.get("ogoh") or []), _rq)
        rol_tanla(pa, ROL_ID["mru_m"])
        _mq = rol_qatori(pa, "mahsulot_turi")
        check("U11f tarkib yozadigan, ro'yxatsiz rol — «Mahsulot turlari va tarkibi» qatorida ogohlantirish",
              isinstance(_mq, dict) and f"Tarkibga yangi material qo'shish uchun «{BAND_NOMI}» ham kerak" in (_mq.get("ogoh") or []), _mq)
        xav(pa.click, '.rl-cb[data-band="material"][data-amal="korish"]')
        pa.wait_for_timeout(200)
        _mq = rol_qatori(pa, "mahsulot_turi")
        check("U11g «Omborxona → Materiallar: Ko'rish» belgilansa ham — ogohlantirish yo'qoladi", isinstance(_mq, dict)
              and not [o for o in (_mq.get("ogoh") or []) if "Tarkibga" in o], _mq)
        ev(pa, "() => { try { ozgarishniBekor(); } catch (e) {} }")
        rol_tanla(pa, ROL_ID["belgi"])
        _bq = rol_qatori(pa, BAND)
        check("U11h belgi yolg'iz (sahifasiz) — band qatorida «Loy retseptlari yoki Ishlab chiqarish sahifasida ishlaydi …» ogohlantirishi",
              isinstance(_bq, dict) and any(o.startswith("Loy retseptlari yoki Ishlab chiqarish sahifasida ishlaydi") for o in (_bq.get("ogoh") or [])),
              _bq)
        ca.close()

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U12. Telefon (390 px)")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        db_rol = SessionLocal()
        db_rol.query(Rol).filter(Rol.id == ROL_ID["mru_r"]).update({"ruxsatlar": json.dumps({"retsept": HAMMA})})
        db_rol.commit()
        db_rol.close()
        cmt, pmt = kontekst("mru_m", 390, 844)
        ochish(pmt, "/production")
        t_och(pmt)
        _o = ev(pmt, """() => { const e = document.getElementById('bom-material-xato'); const r = e.getBoundingClientRect();
            const box = document.querySelector('#bom-modal .modal-box').getBoundingClientRect();
            return {chap: r.left, ong: r.right, eni: innerWidth, box_ong: box.right, korinadi: !e.hidden && r.height > 0,
                    sahifa: document.documentElement.scrollWidth}; }""")
        check("U12a tarkib oynasidagi sabab — telefonda oyna ichida, gorizontal surilish yo'q",
              isinstance(_o, dict) and _o.get("korinadi") and _o.get("chap", -1) >= 0 and _o.get("ong", 999) <= _o.get("box_ong", 0) + 0.5
              and _o.get("sahifa", 999) <= _o.get("eni", 0), _o)
        cmt.close()
        cat, pat = kontekst("mru_a", 390, 844)
        ochish(pat, "/rollar")
        kut(pat, "!!document.querySelector('.rl-cb')")
        rol_tanla(pat, ROL_ID["mru_r"])
        _o = ev(pat, """() => { const o = Array.from(document.querySelectorAll('.rl-amal-ogoh'))[0]; if (!o) return null;
            const r = o.getBoundingClientRect(); const td = o.closest('td').getBoundingClientRect();
            return {matn: o.textContent.trim(), chap: r.left, ong: r.right, td_ong: td.right + 0.5, sahifa: document.documentElement.scrollWidth,
                    eni: innerWidth}; }""")
        check("U12b Rollar ogohlantirishi — telefonda katak ichida, sahifa gorizontal surilmaydi",
              isinstance(_o, dict) and _o.get("matn") == AK_RETSEPT and _o.get("ong", 999) <= _o.get("td_ong", 0)
              and _o.get("sahifa", 999) <= _o.get("eni", 0), _o)
        cat.close()

        check("U13 JS sahifa xatosi (pageerror) yo'q", not JS_XATO, JS_XATO[:5])
        br.close()
    server.should_exit = True

print("\n" + "=" * 70)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
