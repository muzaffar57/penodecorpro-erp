#!/usr/bin/env python3
"""
test_retsept_oyna_ui.py — kech133 (zip 157): «Loy retseptlari» oynalari (yangi / tahrir) — HAQIQIY brauzerda (Chromium, Playwright),
HAQIQIY lokal server bilan (uvicorn, test bazasi) O'LCHANADI.

NIMA UCHUN KERAK (O'LCHANGAN — work/k157/olchov157.py, zip 156 kodi, SQLite va PG)
  * tahrir oynasida «Tarkibi» izohi bo'sh (`&nbsp;`), sarlavha / tugmalar yangi oynadan boshqacha;
  * o'chirilgan (PG da yashirilgan) material tahrirda «?» / «kg» bo'lib chiqar, faqat izoh o'zgartirilib saqlansa ham retseptdan JIMGINA
    o'chardi; rolda «Omborxona → Materiallar: Ko'rish» bo'lmasa — HAMMA qator «?», tanlash paneli «Material topilmadi», saqlab bo'lmasdi;
  * bo'sh «Partiya hajmi (kg)» jimgina 100 bo'lib saqlanardi (120 → 100); miqdorsiz material jimgina tashlanardi («✓ Retsept yangilandi!»);
  * takror nom — «Xato: Serverda kutilmagan xato yuz berdi»; 502 / tarmoq uzilishi — HECH QANDAY xabar (sahifa xatosi); xatodan keyin
    «Saqlash» belgisi yo'qolardi; tahrir tugmasi tez ikki marta bosilsa qatorlar ikki baravar (2 → 4).

BO'LIMLAR
  U1 oynalar ko'rinishi (izoh, sarlavha, tugmalar, «Yopish»);  U2 nom bo'sh;  U3 «Partiya hajmi (kg)» bo'sh / 0 / manfiy / juda katta;
  U4 miqdorsiz material, so'ng to'g'ri saqlash (tugma qayta yuklanguncha o'chiq);  U5 o'chirilgan material — nomi, belgisi, birligi,
  saqlashda QOLADI;  U5b (faqat SQLite — PG da tashqi kalit bunga yo'l qo'ymaydi) bazada yo'q material — «Noma'lum material (ID …)», server
  rad etadi, olib tashlab saqlanadi;  U6 takror nom (yangi va tahrir);  U7 502 va tarmoq uzilishi;  U8 tahrir tugmasi ikki marta;
  U9 «Materiallar: Ko'rish» siz rol;  U10 qatorni olib tashlash (bo'sh holat, tanlash paneli);  U11 ko'p tarkibli retsept — qator `id`
  lari takrorlanmaydi;  U13 telefon (390 px);  U14 «O'chirilgan material» belgisi o'qiladi (yorug' va tungi rejim ≥ 4.5:1);
  U15 materialsiz korxona — tanlash paneli nima qilishni aytadi;  U16 sahifa xatosi (JS) yo'q.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan PostgreSQL. Asl kodga (zip 156) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_retsept_oyna_ui.py
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

PG_BAZA = "retsept_oyna_ui157_test"
_T = tempfile.mkdtemp(prefix="retsept_ui_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'retsept_ui_test.db')}"
os.environ.pop("TENANT_FILTER", None)
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("BACKUP_TELEGRAM_CHAT_ID", None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from production_models import Company              # noqa: E402
from models import UserRole, User, Rol, Inventory, Recipe, RecipeIngredient  # noqa: E402
from sqlalchemy import text as _sql                # noqa: E402

# ══════════════════════════════════════════════════════════════
# Fikstura
# ══════════════════════════════════════════════════════════════
s = SessionLocal()
if not s.query(Company).filter(Company.id == 2).first():
    s.add(Company(id=2, name="RU157 B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "rou_a", "Parol123!", UserRole.ADMIN, "RU A admin", company_id=1)
    auth.create_user(s, "rou_tex", "Parol123!", UserRole.MANAGER, "RU Texnolog", company_id=1)
    auth.create_user(s, "rou_b", "Parol123!", UserRole.ADMIN, "RU B admin", company_id=2)
_rol = Rol(company_id=1, nom="RU157 Texnolog", kod=None,
           ruxsatlar=json.dumps({"retsept": ["korish", "yaratish", "tahrirlash", "ochirish"]}), tavsif="")
s.add(_rol)
s.flush()
s.query(User).filter(User.username == "rou_tex").first().rol_id = _rol.id


def mat(nom, birlik, kat, cid=1):
    m = Inventory(company_id=cid, item_name=nom, unit=birlik, stock_quantity=10, price_per_unit=1000, min_stock=0, category=kat)
    s.add(m)
    s.flush()
    return m.id


A = mat("RU157 Kley", "kg", "Kimyoviy qo'shimchalar")
B = mat("RU157 Qum", "kg", "Qattiq qotishmalar")
C = mat("RU157 Bo'yoq", "l", "Boshqa")
D = mat("RU157 Gips", "kg", "Gips")
E = [mat(f"RU157 Qo'shimcha {i}", "kg", "Bazalt") for i in range(1, 4)]
Z = mat("RU157 Yetim", "kg", "Boshqa") if not PG_URL else None


def ret(nom, hajm, izoh, tarkib):
    r = Recipe(company_id=1, name=nom, batch_size_kg=hajm, notes=izoh)
    s.add(r)
    s.flush()
    for mid, q in tarkib:
        s.add(RecipeIngredient(recipe_id=r.id, inventory_id=mid, quantity_kg=q))
    s.flush()
    return r.id


R1 = ret("RU157 Kvars", 120, "birinchi", [(A, 2.5), (B, 60)])
R2 = ret("RU157 Marmar", 150, None, [(A, 3), (C, 1.2)])
R3 = ret("RU157 Kop tarkib", 100, None, [(A, 1), (B, 2), (D, 3), (E[0], 4), (E[1], 5), (E[2], 6)])
R4 = ret("RU157 Yetim retsept", 100, None, [(A, 1), (Z, 2)]) if Z else None
s.query(Inventory).filter(Inventory.id == C).update({"is_deleted": True})      # production (PG) dagi «yashirildi» holati
s.commit()
if Z:
    s.execute(_sql("DELETE FROM inventory WHERE id = :i"), {"i": Z})          # SQLite: tashqi kalit yo'q — yetim tarkib qatori
    s.commit()
s.close()


def baza(rid):
    s2 = SessionLocal()
    try:
        r = s2.query(Recipe).filter(Recipe.id == rid).first()
        if r is None:
            return None
        ing = sorted((i.inventory_id, float(i.quantity_kg))
                     for i in s2.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == rid).all())
        return (r.name, float(r.batch_size_kg), r.notes, ing)
    finally:
        s2.close()


R1_ASL, R2_ASL = baza(R1), baza(R2)
IZOH = "Har biridan — «Partiya hajmi (kg)» uchun kerak miqdor (kg)"
SARLAVHA = "Tarkibi (Omborxonadagi materiallardan)"
SAQLASH_HTML = '<i class="ti ti-device-floppy"></i> Saqlash'
BEKOR_HTML = '<i class="ti ti-x"></i> Bekor'
HAJM_XATO = "«Partiya hajmi (kg)» — 0 dan katta son kiriting"
ROL_SABAB = "Material tanlab bo'lmaydi: Sizning rolingizda «Omborxona → Materiallar» bo'limida «Ko'rish» ruxsati yo'q. Admin bilan bog'laning."


def band_matn(nom):
    return f"Xato: «{nom}» nomli loy retsepti allaqachon bor — boshqa nom yozing (yoki o'sha retseptni tahrirlang)"


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
    YUBORILGAN = []          # (login, metod, url) — /api/recipes ga yozish so'rovlari

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
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: JS_XATO.append((login, str(e)[:300])))
            pg.on("request", lambda r: YUBORILGAN.append((login, r.method, r.url))
                  if re.search(r"/api/recipes(/\d+)?$", r.url) and r.method in ("POST", "PUT") else None)
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

        def ochish(pg, yol="/recipes"):
            xav(pg.goto, BU + yol)
            xav(pg.wait_for_load_state, "networkidle")

        def oyna(pg, mid):
            return ev(pg, """(id) => { const m = document.getElementById(id); if (!m) return null;
                const q = (s) => m.querySelector(s); const sub = q('.recp-section-sub'); const yop = q('.recp-modal-close');
                return {ochiq: getComputedStyle(m).display === 'flex', title: (q('.recp-section-title') || {}).textContent,
                  sub: sub ? sub.textContent : null, sub_h: sub ? sub.offsetHeight : 0,
                  save: (q('.btn-dark') || {}).innerHTML, bekor: (q('.btn-outline') || {}).innerHTML,
                  yop: yop ? [yop.getAttribute('aria-label'), yop.getAttribute('title')] : null,
                  qatorlar: Array.from(m.querySelectorAll('.recp-ing-row')).map(r => ({rid: r.id, id: r.dataset.inventoryId,
                    nom: (r.querySelector('.recp-ing-name') || {}).textContent, pill: (r.querySelector('.recp-cat-pill') || {}).textContent,
                    birlik: (r.querySelector('.recp-ing-qty span') || {}).textContent, miq: (r.querySelector('input') || {}).value,
                    qid: (r.querySelector('input') || {}).id})),
                  bosh: !!q('.recp-ing-empty')}; }""", mid)

        def toast_tozala(pg):
            ev(pg, "() => { const t = document.getElementById('recpToastText'); if (t) t.textContent = ''; "
                   "const o = document.getElementById('recpToastOverlay'); if (o) o.style.display = 'none'; }")

        def toast(pg, ms=6000):
            kut(pg, "(() => { const t = document.getElementById('recpToastText'); const o = document.getElementById('recpToastOverlay'); "
                    "return t && o && o.style.display === 'flex' && t.textContent.trim().length > 0; })()", ms)
            return ev(pg, "() => { const o = document.getElementById('recpToastOverlay'); const t = document.getElementById('recpToastText'); "
                          "return (o && t && o.style.display === 'flex') ? t.textContent : null; }")

        def tahrir_och(pg, nom):
            toast_tozala(pg)
            xav(pg.click, f".rec-card:has-text('{nom} retsepti') button[aria-label='Tahrirlash']")
            kut(pg, "getComputedStyle(document.getElementById('editModal')).display === 'flex'")
            pg.wait_for_timeout(200)

        def yangi_och(pg):
            toast_tozala(pg)
            xav(pg.click, "button:has-text('Yangi loy retsepti')")
            kut(pg, "getComputedStyle(document.getElementById('addModal')).display === 'flex'")

        def yopish(pg):
            ev(pg, "() => { try { closeEditModal(); } catch (e) {} try { closeAddModal(); } catch (e) {} }")

        def yozuvlar(login):
            return [x for x in YUBORILGAN if x[0] == login]

        def saqla(pg, prefix):
            toast_tozala(pg)
            xav(pg.click, "#recipe-edit-save-btn" if prefix == "edit" else "#recipe-save-btn")
            return toast(pg)

        def tanlash(pg, prefix, nom):
            xav(pg.click, f"#{'editModal' if prefix == 'edit' else 'addModal'} .recp-add-btn")
            kut(pg, f"!!document.querySelector('#{prefix}-picker-list .recp-picker-item, #{prefix}-picker-list .recp-picker-empty')")
            xav(pg.click, f"#{prefix}-picker-list .recp-picker-item:has-text(\"{nom}\")")
            pg.wait_for_timeout(250)

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U1. Oynalar ko'rinishi")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        ca, pa = kontekst("rou_a")
        ochish(pa)
        yangi_och(pa)
        _q = oyna(pa, "addModal")
        yopish(pa)
        tahrir_och(pa, "RU157 Kvars")
        _t = oyna(pa, "editModal")
        check("U1a yangi retsept oynasi: «Tarkibi» sarlavhasi va izohi, «Saqlash» / «Bekor» (belgi bilan), «×» — «Yopish» yorlig'i",
              isinstance(_q, dict) and _q.get("title") == SARLAVHA and _q.get("sub") == IZOH and _q.get("save", "").strip() == SAQLASH_HTML
              and _q.get("bekor", "").strip() == BEKOR_HTML and _q.get("yop") == ["Yopish", "Yopish"], _q)
        tanlash(pa, "edit", "RU157 Gips")
        xav(pa.click, "#editModal .recp-add-btn")
        kut(pa, "!!document.querySelector('#edit-picker-list .recp-picker-item')")
        _kpos = ev(pa, "() => { const p = document.querySelector('#editModal .recp-picker-panel'); return p ? getComputedStyle(p).position : null; }")
        ev(pa, "() => { try { closeIngredientPicker('edit'); } catch (e) {} }")
        yopish(pa)
        tahrir_och(pa, "RU157 Kvars")
        check("U1c kompyuterda (1440 px) tanlash paneli — eskisidek ustma-ust (`position: absolute`)", _kpos == "absolute", _kpos)
        check("U1b tahrir oynasi — izoh KO'RINADI va yangi oynadagi bilan AYNAN («Har biridan — «Partiya hajmi (kg)» uchun kerak miqdor (kg)»), "
              "sarlavha, «Saqlash» / «Bekor», «Yopish» — ham AYNAN",
              isinstance(_t, dict) and _t.get("ochiq") and _t.get("sub") == IZOH and _t.get("sub_h", 0) > 0
              and _t.get("title") == SARLAVHA and _t.get("save", "").strip() == SAQLASH_HTML
              and _t.get("bekor", "").strip() == BEKOR_HTML and _t.get("yop") == ["Yopish", "Yopish"], _t)

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U2–U4. Saqlashdan oldingi tekshiruv")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        _n0 = len(yozuvlar("rou_a"))
        xav(pa.fill, "#edit-name", "")
        _x = saqla(pa, "edit")
        check("U2 tahrirda nom bo'sh → ««Retsept nomi» kiritilishi shart» (inglizcha «'name' …» emas); so'rov YUBORILMADI; retsept o'zgarmadi",
              _x == "«Retsept nomi» kiritilishi shart" and len(yozuvlar("rou_a")) == _n0 and baza(R1) == R1_ASL, (_x, baza(R1)))
        _natija = []
        for _qiymat in ("", "0", "-5"):
            yopish(pa)
            tahrir_och(pa, "RU157 Kvars")
            xav(pa.fill, "#edit-batch", _qiymat)
            _natija.append((_qiymat, saqla(pa, "edit")))
        check("U3a «Partiya hajmi (kg)» bo'sh / 0 / −5 → ««Partiya hajmi (kg)» — 0 dan katta son kiriting»; so'rov YUBORILMADI; hajm 120 "
              "qoldi (ilgari bo'sh → jimgina 100)",
              all(x[1] == HAJM_XATO for x in _natija) and len(yozuvlar("rou_a")) == _n0 and baza(R1) == R1_ASL, (_natija, baza(R1)))
        yopish(pa)
        tahrir_och(pa, "RU157 Kvars")
        xav(pa.fill, "#edit-batch", "1e13")
        _x = saqla(pa, "edit")
        check("U3b «Partiya hajmi (kg)» server chegarasidan katta (1e13) → ««Partiya hajmi (kg)» juda katta» (server xabari «'batch_size_kg' …» "
              "emas); so'rov yo'q", _x == "«Partiya hajmi (kg)» juda katta" and len(yozuvlar("rou_a")) == _n0, _x)
        yopish(pa)
        tahrir_och(pa, "RU157 Kvars")
        tanlash(pa, "edit", "RU157 Gips")
        _o = oyna(pa, "editModal")
        _x = saqla(pa, "edit")
        check("U4a miqdori yozilmagan material («RU157 Gips») → ««RU157 Gips» uchun miqdor kiriting (0 dan katta)»; so'rov YUBORILMADI; "
              "retsept o'zgarmadi (ilgari material jimgina tashlanib, «✓ Retsept yangilandi!»)",
              isinstance(_o, dict) and [r.get("nom") for r in _o.get("qatorlar", [])] == ["RU157 Kley", "RU157 Qum", "RU157 Gips"]
              and _x == "«RU157 Gips» uchun miqdor kiriting (0 dan katta)" and len(yozuvlar("rou_a")) == _n0 and baza(R1) == R1_ASL,
              (_o, _x, baza(R1)))
        xav(pa.fill, f"#{(_o or {}).get('qatorlar', [{}] * 3)[-1].get('qid', 'yoq')}" if isinstance(_o, dict) and len(_o.get("qatorlar", [])) == 3
            else "#yoq-qator", "5")
        _x = saqla(pa, "edit")
        _tg = ev(pa, "() => { const b = document.getElementById('recipe-edit-save-btn'); return b ? [b.disabled, b.textContent.trim()] : null; }")
        check("U4b miqdor yozilgach — «✓ Retsept yangilandi!», hajm 120 (o'zgarmadi), Gips 5 kg qo'shildi; qayta yuklanguncha «Saqlash» O'CHIQ "
              "(«Saqlanmoqda...» — ikkinchi bosish yo'q)",
              _x == "✓ Retsept yangilandi!" and baza(R1) == ("RU157 Kvars", 120.0, "birinchi", sorted([(A, 2.5), (B, 60.0), (D, 5.0)]))
              and _tg == [True, "Saqlanmoqda..."], (_x, baza(R1), _tg))
        xav(pa.wait_for_timeout, 1700)
        xav(pa.wait_for_load_state, "networkidle")

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U5. O'chirilgan material")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        ochish(pa)
        tahrir_och(pa, "RU157 Marmar")
        _o = oyna(pa, "editModal")
        _qr = (_o or {}).get("qatorlar", []) if isinstance(_o, dict) else []
        check("U5a o'chirilgan (yashirilgan) material — retseptdagi NOMI («RU157 Bo'yoq»), BIRLIGI («l»), belgisi «O'chirilgan material», "
              "material raqami saqlangan (ilgari «?», «kg», raqamsiz); boshqa qator — oddiy",
              len(_qr) == 2 and _qr[0].get("nom") == "RU157 Kley" and _qr[0].get("pill") == "Kimyoviy qo'shimcha"
              and _qr[1].get("nom") == "RU157 Bo'yoq" and _qr[1].get("pill") == "O'chirilgan material" and _qr[1].get("birlik") == "l"
              and _qr[1].get("id") == str(C) and _qr[1].get("miq") == "1.2", _qr)
        _pt = ev(pa, "() => { const p = document.querySelector('#editModal .recp-pill-ochirilgan'); return p ? p.title : null; }")
        check("U5b belgi izohi (`title`) — nima bo'lishini aytadi (retseptda qoladi, «Olib tashlash» tugmasi bilan olib tashlanadi)",
              isinstance(_pt, str) and "Retseptda o'zgarishsiz qoladi" in _pt and "«Olib tashlash» tugmasi" in _pt, _pt)
        xav(pa.fill, "#edit-notes", "faqat izoh o'zgardi")
        _x = saqla(pa, "edit")
        # izoh maydoni birinchi harfni o'zi katta qiladi (umumiy qoida — base.html) — «Faqat …»
        check("U5c faqat izoh o'zgartirilib saqlansa — «✓ Retsept yangilandi!», o'chirilgan material retseptda QOLDI (ilgari jimgina o'chardi)",
              _x == "✓ Retsept yangilandi!" and baza(R2) == ("RU157 Marmar", 150.0, "Faqat izoh o'zgardi", sorted([(A, 3.0), (C, 1.2)])),
              (_x, baza(R2)))
        xav(pa.wait_for_timeout, 1700)
        xav(pa.wait_for_load_state, "networkidle")
        if Z:
            ochish(pa)
            tahrir_och(pa, "RU157 Yetim retsept")
            _o = oyna(pa, "editModal")
            _qr = (_o or {}).get("qatorlar", []) if isinstance(_o, dict) else []
            _x = saqla(pa, "edit")
            _yetim_asl = baza(R4)
            check("U5d (SQLite) bazada umuman yo'q material — «Noma'lum material (ID …)», «O'chirilgan material»; saqlashda server rad etadi "
                  "(«Xato: Material topilmadi (ID …)» — o'sha ID), retsept o'zgarmadi",
                  len(_qr) == 2 and _qr[1].get("nom") == f"Noma'lum material (ID {Z})" and _qr[1].get("pill") == "O'chirilgan material"
                  and _x == f"Xato: Material topilmadi (ID {Z})" and _yetim_asl == ("RU157 Yetim retsept", 100.0, None, sorted([(A, 1.0), (Z, 2.0)])),
                  (_qr, _x, _yetim_asl))
            toast_tozala(pa)
            xav(pa.click, "#editModal .recp-ing-row:nth-child(2) .recp-ing-del")
            _x = saqla(pa, "edit")
            check("U5e o'sha qator «Olib tashlash» bilan olib tashlangach — saqlandi, retseptda faqat «RU157 Kley»",
                  _x == "✓ Retsept yangilandi!" and baza(R4) == ("RU157 Yetim retsept", 100.0, None, [(A, 1.0)]), (_x, baza(R4)))
            xav(pa.wait_for_timeout, 1700)
            xav(pa.wait_for_load_state, "networkidle")

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U6–U7. Server rad etsa / javob bermasa")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        ochish(pa)
        yangi_och(pa)
        xav(pa.fill, "#f-name", "RU157 Kvars")
        tanlash(pa, "f", "RU157 Kley")
        xav(pa.fill, "#addModal .recp-ing-qty input", "1")
        _x = saqla(pa, "f")
        _tg = ev(pa, "() => { const b = document.getElementById('recipe-save-btn'); return [b.disabled, b.innerHTML.trim()]; }")
        check("U6a yangi retsept boshqasining nomi bilan → «Xato: «RU157 Kvars» nomli loy retsepti allaqachon bor — …» (ilgari «Serverda "
              "kutilmagan xato»); «Saqlash» qayta yoqiq va BELGISI joyida",
              _x == band_matn("RU157 Kvars") and _tg == [False, SAQLASH_HTML], (_x, _tg))
        yopish(pa)
        tahrir_och(pa, "RU157 Marmar")
        _r2 = baza(R2)
        xav(pa.fill, "#edit-name", "RU157 Kvars")
        _x = saqla(pa, "edit")
        check("U6b tahrirda boshqa retseptning nomi → o'sha sabab; retsept o'zgarmadi",
              _x == band_matn("RU157 Kvars") and baza(R2) == _r2, (_x, baza(R2)))
        xav(pa.fill, "#edit-name", "RU157 Marmar")

        def _r502(route):
            if route.request.method == "PUT":
                return route.fulfill(status=502, content_type="text/html", body="<html><body>Bad Gateway</body></html>")
            return route.continue_()

        def _uzil(route):
            if route.request.method == "PUT":
                return route.abort()
            return route.continue_()

        _xato0 = len(JS_XATO)
        _yol = re.compile(r".*/api/recipes/\d+$")
        xav(pa.route, _yol, _r502)
        _x1 = saqla(pa, "edit")
        _tg1 = ev(pa, "() => { const b = document.getElementById('recipe-edit-save-btn'); return [b.disabled, b.innerHTML.trim()]; }")
        xav(pa.unroute, _yol)
        xav(pa.route, _yol, _uzil)
        _x2 = saqla(pa, "edit")
        _tg2 = ev(pa, "() => { const b = document.getElementById('recipe-edit-save-btn'); return [b.disabled, b.innerHTML.trim()]; }")
        xav(pa.unroute, _yol)
        check("U7 server JSON bo'lmagan javob (502) → «Xato: Saqlanmadi (server javobi: 502)»; tarmoq uzilsa → «Server bilan aloqa yo'q. "
              "Internetni tekshirib, qayta urinib ko'ring.» (ilgari HECH QANDAY xabar yo'q); tugma tiklanadi; sahifa xatosi yo'q",
              _x1 == "Xato: Saqlanmadi (server javobi: 502)" and _x2 == "Server bilan aloqa yo'q. Internetni tekshirib, qayta urinib ko'ring."
              and _tg1 == [False, SAQLASH_HTML] and _tg2 == [False, SAQLASH_HTML] and len(JS_XATO) == _xato0,
              (_x1, _x2, _tg1, _tg2, JS_XATO[_xato0:]))
        yopish(pa)

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U8. Tahrir tugmasi tez ikki marta (materiallar ro'yxati sekin)")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        ochish(pa)
        USHLANGAN = []
        _iy = re.compile(r".*/api/inventory$")
        xav(pa.route, _iy, lambda route: USHLANGAN.append(route))
        ev(pa, """() => { const k = Array.from(document.querySelectorAll('.rec-card')).find(c => c.textContent.includes('RU157 Kvars retsepti'));
            const b = k && k.querySelector("button[aria-label='Tahrirlash']"); if (b) { b.click(); setTimeout(() => b.click(), 120); } }""")
        xav(pa.wait_for_timeout, 700)
        _ush = len(USHLANGAN)
        for _r in USHLANGAN:
            xav(_r.continue_)
        kut(pa, "getComputedStyle(document.getElementById('editModal')).display === 'flex'")
        xav(pa.wait_for_timeout, 800)
        xav(pa.unroute, _iy)
        _o = oyna(pa, "editModal")
        _qr = (_o or {}).get("qatorlar", []) if isinstance(_o, dict) else []
        check("U8 ikki bosish (ikkala so'rov ushlab turilgan) — qatorlar BIR marta: 3 ta (Kley, Qum, Gips), takror yo'q (ilgari 2 baravar)",
              _ush >= 1 and [r.get("nom") for r in _qr] == ["RU157 Kley", "RU157 Qum", "RU157 Gips"], (_ush, _qr))
        yopish(pa)
        # U8b: BIRINCHI retseptning tahriri, darhol IKKINCHISINIKI; javoblar TESKARI tartibda (ikkinchisi oldin) — kech qolgan birinchi
        # javob ikkinchi retsept oynasiga BIRINCHI retsept tarkibini yozmasin (saqlansa ikkinchi retseptga begona tarkib yozilardi)
        ochish(pa)
        USHLANGAN = []
        xav(pa.route, _iy, lambda route: USHLANGAN.append(route))
        ev(pa, """() => { const t = (nom) => { const k = Array.from(document.querySelectorAll('.rec-card')).find(c => c.textContent.includes(nom + ' retsepti'));
            return k && k.querySelector("button[aria-label='Tahrirlash']"); };
            const a = t('RU157 Kvars'), b = t('RU157 Marmar'); if (a && b) { a.click(); setTimeout(() => b.click(), 120); } }""")
        xav(pa.wait_for_timeout, 700)
        _ush = len(USHLANGAN)
        if _ush >= 2:
            xav(USHLANGAN[1].continue_)
            xav(pa.wait_for_timeout, 600)
            xav(USHLANGAN[0].continue_)
        else:
            for _r in USHLANGAN:
                xav(_r.continue_)
        kut(pa, "getComputedStyle(document.getElementById('editModal')).display === 'flex'")
        xav(pa.wait_for_timeout, 800)
        xav(pa.unroute, _iy)
        _o = oyna(pa, "editModal")
        _qr = (_o or {}).get("qatorlar", []) if isinstance(_o, dict) else []
        _nm = ev(pa, "() => document.getElementById('edit-name').value")
        check("U8b «RU157 Kvars» tahriri, darhol «RU157 Marmar» niki, javoblar teskari tartibda — oynada FAQAT «RU157 Marmar» (nomi va tarkibi: "
              "Kley, Bo'yoq); kech qolgan birinchi javob begona tarkib yozmadi",
              _ush == 2 and _nm == "RU157 Marmar" and [r.get("nom") for r in _qr] == ["RU157 Kley", "RU157 Bo'yoq"], (_ush, _nm, _qr))
        yopish(pa)

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U10–U11. Qatorni olib tashlash; qator raqamlari")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        ochish(pa)
        yangi_och(pa)
        tanlash(pa, "f", "RU157 Kley")
        _o1 = oyna(pa, "addModal")
        xav(pa.click, "#addModal .recp-ing-row .recp-ing-del")
        xav(pa.wait_for_timeout, 300)
        _o = oyna(pa, "addModal")
        check("U10a oxirgi qator «Olib tashlash» bilan olib tashlangach — «Hali material qo'shilmagan» QAYTADI (ilgari jadval bo'sh qolardi)",
              isinstance(_o1, dict) and [r.get("nom") for r in _o1.get("qatorlar", [])] == ["RU157 Kley"]
              and isinstance(_o, dict) and _o.get("bosh") is True and not _o.get("qatorlar"), (_o1, _o))
        yopish(pa)
        tahrir_och(pa, "RU157 Kop tarkib")
        _o = oyna(pa, "editModal")
        _qr = (_o or {}).get("qatorlar", []) if isinstance(_o, dict) else []
        check("U11 6 tarkibli retsept: qator va miqdor maydoni `id` lari TAKRORLANMAYDI (ilgari vaqt + tasodifiy son — bir xil chiqishi mumkin edi)",
              len(_qr) == 6 and len({r.get("rid") for r in _qr}) == 6 and len({r.get("qid") for r in _qr}) == 6, _qr)
        yopish(pa)

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U14. «O'chirilgan material» belgisi o'qiladi (yorug' / tungi)")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        _KONTRAST = """() => { const p = document.querySelector('#editModal .recp-pill-ochirilgan'); if (!p) return null;
            const rgb = (s) => (s.match(/[\\d.]+/g) || []).slice(0, 3).map(Number);
            const L = (c) => { const [r, g, b] = c.map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
              return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
            const cs = getComputedStyle(p); const a = L(rgb(cs.color)), b = L(rgb(cs.backgroundColor));
            return {k: (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05), c: cs.color, f: cs.backgroundColor}; }"""
        _kt = []
        for _rej in ("light", "dark"):
            ev(pa, "(r) => document.documentElement.setAttribute('data-theme', r)", _rej)
            tahrir_och(pa, "RU157 Marmar")
            _kt.append((_rej, ev(pa, _KONTRAST)))
            yopish(pa)
        ev(pa, "() => document.documentElement.removeAttribute('data-theme')")
        check("U14 belgi yozuvi o'z fonida ≥ 4.5:1 — yorug' va tungi rejimda (`data-theme`; egasining sozlamasi o'zgartirilmaydi)",
              all(isinstance(x[1], dict) and x[1].get("k", 0) >= 4.5 for x in _kt), _kt)
        ca.close()

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U9. «Omborxona → Materiallar: Ko'rish» siz rol (faqat «Loy retseptlari»)")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        cx, px = kontekst("rou_tex")
        ochish(px)
        tahrir_och(px, "RU157 Kvars")
        _o = oyna(px, "editModal")
        _qr = (_o or {}).get("qatorlar", []) if isinstance(_o, dict) else []
        check("U9a tahrir: qatorlar retseptdagi NOMLAR bilan («RU157 Kley», «RU157 Qum», «RU157 Gips»), belgisi «Material» (o'chirilgan emas), "
              "material raqamlari saqlangan (ilgari hammasi «?» va raqamsiz)",
              [r.get("nom") for r in _qr] == ["RU157 Kley", "RU157 Qum", "RU157 Gips"] and all(r.get("pill") == "Material" for r in _qr)
              and [r.get("id") for r in _qr] == [str(A), str(B), str(D)], _qr)
        xav(px.click, "#editModal .recp-add-btn")
        kut(px, "!!document.querySelector('#edit-picker-list .recp-picker-empty')")
        _pn = ev(px, "() => (document.querySelector('#edit-picker-list .recp-picker-empty') || {}).textContent")
        check("U9b tanlash paneli — SABABI: «Material tanlab bo'lmaydi: Sizning rolingizda «Omborxona → Materiallar» bo'limida «Ko'rish» "
              "ruxsati yo'q. Admin bilan bog'laning.» (ilgari «Material topilmadi»)", _pn == ROL_SABAB, _pn)
        ev(px, "() => { try { closeIngredientPicker('edit'); } catch (e) {} }")
        if len(_qr) == 3:
            xav(px.fill, f"#{_qr[0].get('qid')}", "2.75")
        _x = saqla(px, "edit")
        check("U9c miqdor o'zgartirib saqlansa — «✓ Retsept yangilandi!», HAMMA material qoldi (Kley 2.75, Qum 60, Gips 5)",
              _x == "✓ Retsept yangilandi!" and baza(R1) == ("RU157 Kvars", 120.0, "birinchi", sorted([(A, 2.75), (B, 60.0), (D, 5.0)])),
              (_x, baza(R1)))
        xav(px.wait_for_timeout, 1700)
        xav(px.wait_for_load_state, "networkidle")
        ochish(px)
        yangi_och(px)
        xav(px.click, "#addModal .recp-add-btn")
        kut(px, "!!document.querySelector('#f-picker-list .recp-picker-empty')")
        _pn = ev(px, "() => (document.querySelector('#f-picker-list .recp-picker-empty') || {}).textContent")
        check("U9d yangi retsept oynasida ham — o'sha sabab", _pn == ROL_SABAB, _pn)
        cx.close()

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U15. Materialsiz korxona")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        cb, pb = kontekst("rou_b")
        ochish(pb)
        yangi_och(pb)
        xav(pb.click, "#addModal .recp-add-btn")
        kut(pb, "!!document.querySelector('#f-picker-list .recp-picker-empty')")
        _pn = ev(pb, "() => (document.querySelector('#f-picker-list .recp-picker-empty') || {}).textContent")
        check("U15 omborxonada material yo'q — «Omborxonada hali material yo'q — avval «Omborxona» bo'limida material qo'shing» "
              "(ilgari «Material topilmadi»)", _pn == "Omborxonada hali material yo'q — avval «Omborxona» bo'limida material qo'shing", _pn)
        cb.close()

        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        section("U13. Telefon (390 px)")
        # ══════════════════════════════════════════════════════════════════════════════════════════════════════
        ct, pt = kontekst("rou_a", 390, 844)
        ochish(pt)
        _OLCHOV = """(id) => { const m = document.querySelector('#' + id + ' .recp-modal'); const sub = document.querySelector('#' + id + ' .recp-section-sub');
            if (!m || !sub) return null; const r = sub.getBoundingClientRect();
            return {msw: m.scrollWidth, mcw: m.clientWidth, dsw: document.documentElement.scrollWidth, vw: innerWidth,
                    sub: [Math.round(r.left), Math.round(r.right), Math.round(r.height)], matn: sub.textContent}; }"""
        tahrir_och(pt, "RU157 Marmar")
        _tt = ev(pt, _OLCHOV, "editModal")
        yopish(pt)
        yangi_och(pt)
        _tq = ev(pt, _OLCHOV, "addModal")
        check("U13 390 px: ikkala oyna — gorizontal aylantirish yo'q; «Tarkibi» izohi ekranga sig'adi va ko'rinadi",
              all(isinstance(x, dict) and x["msw"] <= x["mcw"] and x["dsw"] <= x["vw"] and x["sub"][0] >= 0 and x["sub"][1] <= x["vw"]
                  and x["sub"][2] > 0 and x["matn"] == IZOH for x in (_tt, _tq)), (_tt, _tq))
        # telefonda tanlash paneli oqim ichida (kech119) — panel ochiq turib qatorni olib tashlash mumkin
        tanlash(pt, "f", "RU157 Kley")
        xav(pt.click, "#addModal .recp-add-btn")
        kut(pt, "!!document.querySelector('#f-picker-list .recp-picker-item')")
        _oldin = ev(pt, "() => Array.from(document.querySelectorAll('#f-picker-list .recp-picker-item')).map(e => e.textContent.trim())")
        _joy = ev(pt, """() => { const p = document.querySelector('#addModal .recp-picker-panel'); const d = document.querySelector('#addModal .recp-ing-del');
            if (!p || !d) return null; d.scrollIntoView({block: 'center'}); const r = d.getBoundingClientRect();
            const e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
            return {pos: getComputedStyle(p).position, ustida: !!(e && e.closest('.recp-ing-del'))}; }""")
        check("U13b (390 px) tanlash paneli OQIM ichida (`position: static` — kech119 niyati; ilgari keyingi asosiy qoida uni `absolute` qilib, "
              "panel tarkib qatorlarini yopardi): ochiq panel turganda «Olib tashlash» tugmasi ustida boshqa element yo'q",
              isinstance(_joy, dict) and _joy.get("pos") == "static" and _joy.get("ustida") is True, _joy)
        xav(pt.click, "#addModal .recp-ing-row .recp-ing-del")
        xav(pt.wait_for_timeout, 400)
        _keyin = ev(pt, "() => Array.from(document.querySelectorAll('#f-picker-list .recp-picker-item')).map(e => e.textContent.trim())")
        check("U10b (390 px) tanlash paneli ochiq turib qator olib tashlansa — material panelda YANA ko'rinadi (ilgari sahifa qayta ochilguncha "
              "yo'q edi)", isinstance(_oldin, list) and "RU157 Kley" not in _oldin and isinstance(_keyin, list) and "RU157 Kley" in _keyin,
              (_oldin, _keyin))
        ct.close()
        br.close()

    section("U16. Sahifa xatosi")
    check("U16 JS sahifa xatosi (pageerror) yo'q", not JS_XATO, JS_XATO[:5])
    server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAIL:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
