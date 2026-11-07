#!/usr/bin/env python3
"""
test_yaxlit_oqim269.py — kech204 (zip 269): narx yaxlitlash — BUTUN OQIMLAR haqiqiy brauzerda (egasi so'rovi 07.11 16:05: «tezkor buyurtma
yaratib yoki vaqtinchalik saqlash qilib qayta tahrirlab yoki jarayonda detalni + yoki − qilsam hech qanday xatolik bo'lmaydimi; block holatda
bitta sina; keyin bitta buyurtma ichida donalik, profil va panelda — qoplamali, qoplamasiz — chuqur tekshirib ber»).

NIMA TEKSHIRILADI (har qadamdan keyin SERVERDAGI narx Python da alohida hisoblangan kutilgan qiymat bilan solishtiriladi):
  BL — faqat BLOK yoqiq korxona («+500»): asosiy narxdan, o'z narxidan, qoplamali (koeffitsient 2) blok detallar;
       1) oddiy buyurtma → tahrirda miqdor + → miqdor − ; 2) «📝 Vaqtincha saqlash» (qoralama) → tahrir (miqdor +) → jarayonga olish;
       3) «⚡ Tez hisob» (taklif) → taklifni tahrirlash (miqdor −) → rasmiylashtirish (buyurtma).
  AR — Profil / Panel / Donalik, har biri qoplamasiz VA qoplamali — BITTA buyurtmada (6 detal, «+500»): o'sha uch oqim, har tahrirda
       miqdor + va −; narx (1 birlik) o'zgarmaydi, jami = yaxlit narx × yangi miqdor, buyurtma jami = detallar yig'indisi.
  QO — oqim davomida Sozlama «−1 000» ga o'zgarsa: saqlangan qoralama / taklif / buyurtma tahriri O'Z qoidasi bilan qoladi.
  Har oqimda: tasdiq / kamchilik oynasida xato yo'q, JS xatosi yo'q.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`. (PostgreSQL — brauzersiz qism `test_narx_yaxlit269.py` da.)
Asl kodga (77fbc14 — zip 268) qarshi YIQILADI, QULAMAYDI.
ISHLATISH: python3 tools/test_yaxlit_oqim269.py
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
TF = os.environ.get("TENANT_FILTER") == "1"
_T = tempfile.mkdtemp(prefix="k269o_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k269o.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "ADMIN_PASSWORD", "RESET_ADMIN_PASSWORD", "PG_URL"):
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


with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, Project, Order, Recipe   # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

PAROL = "Kuchli-Sinov-Parol-269o"
s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="Blok korxona 269"))
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "o269_a", PAROL, UserRole.ADMIN, "Aralash Admin", company_id=1)
    auth.create_user(s, "o269_b", PAROL, UserRole.ADMIN, "Blok Admin", company_id=2)
_ob = []
for _cid in (1, 2):
    _p = Inventory(company_id=_cid, item_name=f"Penoplast 15 ({_cid})", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                   volume_per_unit=2.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
    _pr = Project(company_id=_cid, client_name=f"Mijoz {_cid}", project_name=f"Loyiha {_cid}", client_phone=f"+99890111{_cid}269",
                  total_budget=0, total_paid=0)
    _rc = Recipe(company_id=_cid, name=f"Qoplama retsepti {_cid}")
    s.add_all([_p, _pr, _rc])
    s.flush()
    _ob.append((_pr.id, _rc.id))
s.commit()
ID = {"P1": _ob[0][0], "R1": _ob[0][1], "P2": _ob[1][0], "R2": _ob[1][1]}
s.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    return c


A, B = mijoz("o269_a"), mijoz("o269_b")
B.put("/api/settings/categories", data={"codes": "blok", "v": "2"})                  # B — faqat Blok
for _c in (A, B):
    _c.put("/api/settings/narx-yaxlit", data={"yonalish": "+", "qadam": "500"})


def js(r):
    try:
        return r.json()
    except Exception:                   # noqa: BLE001
        return {}


def yaxlit(n, qoida="+500"):
    """Brauzerdagi `narxYaxlit` ning Python nusxasi (kutilgan qiymat — mustaqil hisob)."""
    import math
    if not qoida or n <= 0:
        return n
    q = int(qoida[1:])
    t = round(n * 100) / 100
    b = math.ceil(t / q - 1e-9) if qoida[0] == "+" else math.floor(t / q + 1e-9)
    return b * q if b * q > 0 else n


def server(c, oid):
    d = js(c.get(f"/api/orders/{oid}"))
    return d, {i["name"]: (round(i["unit_price"], 2), round(i["total_price"], 2)) for i in (d.get("items") or [])}


def oxirgi_buyurtma(cid):
    _s = SessionLocal()
    try:
        o = _s.query(Order).execution_options(skip_tenant_filter=True).filter(Order.company_id == cid).order_by(Order.id.desc()).first()
        return o.id if o else None
    finally:
        _s.close()


# Kutilgan narxlar (formula — orders.html dagi bilan bir xil, mustaqil yozilgan)
KUB = 2_468_000           # 1 m³ asosiy narxi
BLOK = 123_400            # 1 blok asosiy narxi
AR_DETAL = {   # nom: (tur, maydonlar, qoplama, miqdor_maydoni, boshlang'ich miqdor, 1 birlik narxi (xom))
    "Profil oddiy": ("profil", {".i-h": "10", ".i-w": "10"}, False, ".i-l", 3, (0.10 * 0.10 * KUB) / 2),
    "Profil qoplamali": ("profil", {".i-h": "10", ".i-w": "10"}, True, ".i-l", 2, (0.10 * 0.10 * KUB) / 2 * 2),
    "Panel oddiy": ("panel", {".i-h": "5", ".i-t": "10"}, False, ".i-q", 2, 0.05 * 0.10 * KUB),
    "Panel qoplamali": ("panel", {".i-h": "4", ".i-t": "10"}, True, ".i-q", 3, 0.04 * 0.10 * KUB * 2),
    "Donalik oddiy": ("dona", {".i-h": "10", ".i-t": "10", ".i-donayield": "1"}, False, ".i-q", 4, (0.10 * 0.10 / 2 / 1) * KUB),
    "Donalik qoplamali": ("dona", {".i-h": "10", ".i-t": "10", ".i-donayield": "3"}, True, ".i-q", 5, (0.10 * 0.10 / 2 / 3) * KUB * 2),
}
BL_DETAL = {
    "Blok asosiy": ("blok", {".i-l": "10"}, False, ".i-q", 6, BLOK / 10),
    "Blok o'z narxi": ("blok", {".i-blokprice": "126 500", ".i-l": "10"}, False, ".i-q", 2, 126_500 / 10),
    "Blok qoplamali": ("blok", {".i-l": "20"}, True, ".i-q", 4, BLOK / 20 * 2),
}


def kutilgan(detallar, miqdor, qoida="+500"):
    """{nom: (serverdagi unit_price, total_price)}. Profil serverda «1 dona» = uzunlik × yaxlit 1 m narxi (soni — 1), jami ham shu;
    qolganlarida unit_price — yaxlit 1 birlik narxi, jami = narx × miqdor."""
    natija = {}
    for nom, v in detallar.items():
        y = yaxlit(v[5], qoida)
        jami = round(y * miqdor[nom], 2)
        natija[nom] = (jami, jami) if v[0] == "profil" else (y, jami)
    return natija


def solishtir(haqiqiy, kut):
    farq = {k: (haqiqiy.get(k), kut[k]) for k in kut if not haqiqiy.get(k) or abs(haqiqiy[k][0] - kut[k][0]) > 0.005
            or abs(haqiqiy[k][1] - kut[k][1]) > 0.005}
    ortiqcha = sorted(set(haqiqiy) - set(kut))
    return (not farq and not ortiqcha), {"farq": farq, "ortiqcha": ortiqcha}


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_sk = socket.socket()
_sk.bind(("127.0.0.1", 0))
PORT = _sk.getsockname()[1]
_sk.close()
import uvicorn                                    # noqa: E402
from playwright.sync_api import sync_playwright   # noqa: E402
_srv = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=PORT, log_level="error", lifespan="off"))
threading.Thread(target=_srv.run, daemon=True).start()
while not _srv.started:
    time.sleep(0.1)
BASE = f"http://127.0.0.1:{PORT}"
_exe = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
XATOLAR = []

TOLDIR_JS = """([nom, tur, maydon, qoplama, mqsel, miqdor]) => {
    addItem();
    const r = document.getElementById('item_' + itemCount);           // yangi qator ro'yxat boshiga qo'shiladi
    const b = r.querySelector('.type-opt[data-value="' + tur + '"]');
    if (!b) return 'tur yo`q: ' + tur;
    selectTypeOpt(b, tur);
    const set = (sel, v) => { const e = r.querySelector(sel); e.value = v; e.dispatchEvent(new Event('input', {bubbles: true})); };
    set('.i-name', nom);
    r.querySelector(qoplama ? '.coat-yes' : '.coat-no').click();
    for (const [k, v] of Object.entries(maydon)) set(k, v);
    set(mqsel, String(miqdor));
    calculateItem(r);
    return r.querySelector('.i-perm').value;
}"""

MIQDOR_JS = """([nom, mqsel, miqdor]) => {
    const r = [...document.querySelectorAll('#items .detal')].find(x => x.querySelector('.i-name').value === nom);
    if (!r) return 'detal yo`q: ' + nom;
    const e = r.querySelector(mqsel); e.value = String(miqdor); e.dispatchEvent(new Event('input', {bubbles: true}));
    calculateItem(r);
    return r.querySelector('.i-perm').value + ' / ' + r.querySelector('.i-price').value;
}"""


def tasdiqla(pg, marta=5):
    """Tasdiq oynalari («Saqlansinmi?», «Jarayonga olasizmi?») — bosiladi; kamchilik oynasi bo'lsa matni qaytadi."""
    for _ in range(marta):
        pg.wait_for_timeout(600)
        if not pg.evaluate("() => { const b = document.getElementById('genericConfirmOk'); if (b && b.offsetParent !== null) { b.click(); return true; }"
                           " const c = document.querySelector('.cc-ok, #customConfirmOk'); if (c && c.offsetParent !== null) { c.click(); return true; } return false; }"):
            break
    pg.wait_for_timeout(1500)
    return pg.evaluate("() => { const m = document.getElementById('validationModal'); return m && m.style.display === 'flex' ? m.textContent.trim().slice(0, 400) : ''; }")


def yangi_forma(pg, kub=None, blok=None):
    pg.goto(BASE + "/orders", wait_until="networkidle")
    pg.evaluate("() => { localStorage.clear(); showNewForm(); }")
    pg.wait_for_timeout(600)
    pg.evaluate("() => { document.getElementById('items').innerHTML = ''; }")
    if kub:
        pg.evaluate(f"() => {{ const e = document.getElementById('base_price'); e.value = '{kub}'; e.dispatchEvent(new Event('input', {{bubbles: true}})); }}")
    if blok:
        pg.evaluate(f"() => {{ const e = document.getElementById('blok_base_price'); e.value = '{blok}'; e.dispatchEvent(new Event('input', {{bubbles: true}})); }}")


def toldir(pg, detallar):
    return {nom: pg.evaluate(TOLDIR_JS, [nom, v[0], v[1], v[2], v[3], v[4]]) for nom, v in detallar.items()}


def rekvizit(pg, pid, rid):
    pg.evaluate(f"""() => {{ document.getElementById('project_id').value = '{pid}'; document.getElementById('deadline_input').value = '2026-12-20';
        const r = document.getElementById('recipe_id'); if (r) r.value = '{rid}';
        const l = document.getElementById('loy_kg'); if (l) {{ l.value = '10'; l.dispatchEvent(new Event('input', {{bubbles: true}})); }} }}""")


def tahrir_och(pg, oid):
    pg.goto(f"{BASE}/orders?order={oid}", wait_until="networkidle")
    pg.wait_for_timeout(700)
    pg.evaluate("() => { editSelected(); }")
    pg.wait_for_timeout(1500)


def miqdorlar(pg, detallar, miqdor):
    return {nom: pg.evaluate(MIQDOR_JS, [nom, detallar[nom][3], miqdor[nom]]) for nom in detallar}


def oqim_buyurtma(pg, c, cid, nom, detallar, kub, blok, pid, rid):
    """1) oddiy buyurtma → tahrir miqdor + → tahrir miqdor −"""
    yangi_forma(pg, kub, blok)
    toldir(pg, detallar)
    rekvizit(pg, pid, rid)
    oldin = oxirgi_buyurtma(cid)
    pg.evaluate("() => { saveOrder(); }")
    vm = tasdiqla(pg)
    oid = oxirgi_buyurtma(cid)
    miq = {k: v[4] for k, v in detallar.items()}
    d, h = server(c, oid) if oid != oldin else ({}, {})
    ok, f = solishtir(h, kutilgan(detallar, miq))
    check(f"{nom}1 buyurtma saqlandi: qoida «+500», har detal 1 birlik narxi yaxlit, jami = narx × miqdor, buyurtma jami = yig'indi",
          oid != oldin and not vm and d.get("narx_yaxlit") == "+500" and ok
          and abs(float(d.get("total_amount") or 0) - sum(x[1] for x in h.values())) < 0.01, (vm, d.get("narx_yaxlit"), f))
    for qadam, (belgi, o_zgar) in enumerate((("+", lambda m: m + 2), ("−", lambda m: max(1, m - 1))), start=2):
        miq = {k: o_zgar(m) for k, m in miq.items()}
        tahrir_och(pg, oid)
        q = pg.evaluate("() => NARX_YAXLIT")
        miqdorlar(pg, detallar, miq)
        pg.evaluate(f"() => {{ updateOrder({oid}); }}")
        vm = tasdiqla(pg)
        d, h = server(c, oid)
        ok, f = solishtir(h, kutilgan(detallar, miq))
        check(f"{nom}{qadam} tahrir — miqdor {belgi} ({', '.join(f'{k} {v}' for k, v in miq.items())}): narx o'zgarmadi, jami qayta hisoblandi, "
              "qoida «+500» qoldi", q == "+500" and not vm and d.get("narx_yaxlit") == "+500" and ok
              and abs(float(d.get("total_amount") or 0) - sum(x[1] for x in h.values())) < 0.01, (q, vm, f))
    return oid


def oqim_qoralama(pg, c, cid, nom, detallar, kub, blok, pid, rid):
    """2) qoralama → (sozlama «−1000» ga o'zgaradi) → tahrir miqdor + → jarayonga olish"""
    yangi_forma(pg, kub, blok)
    toldir(pg, detallar)
    rekvizit(pg, pid, rid)
    oldin = oxirgi_buyurtma(cid)
    pg.evaluate("() => { saveOrder(true); }")
    vm = tasdiqla(pg)
    oid = oxirgi_buyurtma(cid)
    miq = {k: v[4] for k, v in detallar.items()}
    d, h = server(c, oid) if oid != oldin else ({}, {})
    ok, f = solishtir(h, kutilgan(detallar, miq))
    check(f"{nom}1 «📝 Vaqtincha saqlash» — qoralama: qoida «+500», narxlar yaxlit", oid != oldin and not vm and d.get("is_draft") is True
          and d.get("narx_yaxlit") == "+500" and ok, (vm, d.get("is_draft"), d.get("narx_yaxlit"), f))
    c.put("/api/settings/narx-yaxlit", data={"yonalish": "-", "qadam": "1000"})
    miq = {k: m + 1 for k, m in miq.items()}
    tahrir_och(pg, oid)
    q = pg.evaluate("() => NARX_YAXLIT")
    miqdorlar(pg, detallar, miq)
    pg.evaluate(f"() => {{ updateOrder({oid}); }}")
    vm = tasdiqla(pg)
    d, h = server(c, oid)
    ok, f = solishtir(h, kutilgan(detallar, miq))
    check(f"{nom}2 Sozlama «−1 000» ga o'zgardi → qoralamani tahrirlash (miqdor +): qoralama O'Z qoidasi («+500») bilan, narx o'zgarmadi",
          q == "+500" and not vm and d.get("is_draft") is True and d.get("narx_yaxlit") == "+500" and ok, (q, vm, f))
    pg.goto(f"{BASE}/orders?order={oid}", wait_until="networkidle")
    pg.wait_for_timeout(700)
    pg.evaluate("() => { activateDraft(); }")
    vm = tasdiqla(pg)
    pg.wait_for_timeout(800)
    d, h = server(c, oid)
    ok, f = solishtir(h, kutilgan(detallar, miq))
    check(f"{nom}3 qoralama jarayonga olindi — narxlar, jami va qoida o'zgarmadi", d.get("is_draft") is False and d.get("narx_yaxlit") == "+500"
          and ok, (vm, d.get("is_draft"), d.get("status"), f))
    c.put("/api/settings/narx-yaxlit", data={"yonalish": "+", "qadam": "500"})
    return oid


def oqim_taklif(pg, c, cid, nom, detallar, kub, blok, pid, rid):
    """3) «⚡ Tez hisob» (taklif) → taklifni tahrirlash (miqdor −) → rasmiylashtirish"""
    pg.goto(BASE + "/orders", wait_until="networkidle")
    pg.evaluate("() => { localStorage.clear(); tezHisobOch(); }")
    pg.wait_for_timeout(700)
    pg.evaluate("() => { document.getElementById('items').innerHTML = ''; }")
    if kub:
        pg.evaluate(f"() => {{ const e = document.getElementById('base_price'); e.value = '{kub}'; e.dispatchEvent(new Event('input', {{bubbles: true}})); }}")
    if blok:
        pg.evaluate(f"() => {{ const e = document.getElementById('blok_base_price'); e.value = '{blok}'; e.dispatchEvent(new Event('input', {{bubbles: true}})); }}")
    toldir(pg, detallar)
    pg.evaluate(f"""() => {{ document.getElementById('tk_mijoz').value = 'Tez mijoz {cid}'; document.getElementById('tk_telefon').value = '+998901234{cid}69';
        const r = document.getElementById('recipe_id'); if (r) r.value = '{rid}';
        const l = document.getElementById('loy_kg'); if (l) {{ l.value = '10'; l.dispatchEvent(new Event('input', {{bubbles: true}})); }} }}""")
    tk0 = {t["id"] for t in (js(c.get("/api/takliflar")).get("takliflar") or js(c.get("/api/takliflar")).get("items") or [])}
    pg.evaluate("() => { saveOrder(); }")
    vm = tasdiqla(pg)
    _ro = js(c.get("/api/takliflar"))
    _tk = [t for t in (_ro.get("takliflar") or _ro.get("items") or []) if t["id"] not in tk0]
    tid = _tk[0]["id"] if _tk else None
    tk = js(c.get(f"/api/takliflar/{tid}")) if tid else {}
    miq = {k: v[4] for k, v in detallar.items()}
    h = {i["name"]: (round(i["unit_price"], 2), round(i["total_price"], 2)) for i in (tk.get("items") or [])}
    ok, f = solishtir(h, kutilgan(detallar, miq))
    check(f"{nom}1 «⚡ Tez hisob» — taklif saqlandi: qoida «+500», narxlar yaxlit", bool(tid) and not vm and tk.get("narx_yaxlit") == "+500" and ok,
          (vm, tid, tk.get("narx_yaxlit"), f, list(_ro)[:4]))
    if not tid:
        return None
    miq = {k: max(1, m - 1) for k, m in miq.items()}
    pg.goto(BASE + "/orders", wait_until="networkidle")
    pg.evaluate(f"() => taklifTahrir({tid})")
    pg.wait_for_timeout(1500)
    q = pg.evaluate("() => NARX_YAXLIT")
    miqdorlar(pg, detallar, miq)
    pg.evaluate("() => { saveOrder(); }")
    vm = tasdiqla(pg)
    tk = js(c.get(f"/api/takliflar/{tid}"))
    h = {i["name"]: (round(i["unit_price"], 2), round(i["total_price"], 2)) for i in (tk.get("items") or [])}
    ok, f = solishtir(h, kutilgan(detallar, miq))
    check(f"{nom}2 taklif tahrirlandi (miqdor −): o'z qoidasi, narx o'zgarmadi, jami qayta hisoblandi", q == "+500" and not vm
          and tk.get("narx_yaxlit") == "+500" and ok, (q, vm, f))
    oldin = oxirgi_buyurtma(cid)
    pg.goto(BASE + "/orders", wait_until="networkidle")
    pg.evaluate(f"() => taklifRasmiy({tid})")
    pg.wait_for_timeout(1500)
    q = pg.evaluate("() => NARX_YAXLIT")
    perm = pg.evaluate("() => [...document.querySelectorAll('#items .detal')].map(r => r.querySelector('.i-name').value + '=' + r.querySelector('.i-perm').value)")
    rekvizit(pg, pid, rid)
    pg.evaluate("() => { saveOrder(); }")
    vm = tasdiqla(pg)
    oid = oxirgi_buyurtma(cid)
    d, h = server(c, oid) if oid != oldin else ({}, {})
    ok, f = solishtir(h, kutilgan(detallar, miq))
    check(f"{nom}3 taklif rasmiylashtirildi → buyurtma: qoida «+500» (taklifniki), narx va jami taklifdagidek", q == "+500" and oid != oldin
          and not vm and d.get("narx_yaxlit") == "+500" and ok, (q, vm, perm, f))
    return oid


def _ui():
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path=_exe[-1] if _exe else None)
        for login, c, cid, kub, blok, detallar, pid, rid, bosh in (
                ("o269_b", B, 2, None, "123 400", BL_DETAL, ID["P2"], ID["R2"], "BL"),
                ("o269_a", A, 1, "2 468 000", None, AR_DETAL, ID["P1"], ID["R1"], "AR")):
            ctx = br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent")
            ctx.route("**/*", lambda r: r.fulfill(status=204, body="") if not r.request.url.startswith(BASE) else r.continue_())
            pg = ctx.new_page()
            pg.set_default_timeout(15000)
            pg.on("pageerror", lambda e: XATOLAR.append(str(e)[:200]))
            pg.on("dialog", lambda d: d.accept())
            pg.goto(BASE + "/login")
            pg.fill("input[name=username]", login)
            pg.fill("input[name=password]", PAROL)
            pg.press("input[name=password]", "Enter")
            pg.wait_for_load_state("networkidle")
            section(f"{bosh} — {'faqat Blok korxona' if bosh == 'BL' else 'Profil / Panel / Donalik, qoplamali va qoplamasiz — bitta buyurtmada'}")
            # kutilgan qiymatlar odamga ko'rinadigan shaklda (hisobot uchun)
            print("    kutilgan 1 birlik narxi:", {k: f"{v[5]:,.2f} → {yaxlit(v[5]):,}".replace(",", " ") for k, v in detallar.items()})
            yangi_forma(pg, kub, blok)
            p = toldir(pg, detallar)
            check(f"{bosh}0 formada 1 birlik narxi — yaxlit (kutilgan bilan)", all(p[k].replace(" ", " ").replace(" ", " ")
                  == f"{yaxlit(v[5]):,}".replace(",", " ") for k, v in detallar.items()), p)
            oqim_buyurtma(pg, c, cid, f"{bosh}-B", detallar, kub, blok, pid, rid)
            oqim_qoralama(pg, c, cid, f"{bosh}-Q", detallar, kub, blok, pid, rid)
            oqim_taklif(pg, c, cid, f"{bosh}-T", detallar, kub, blok, pid, rid)
            ctx.close()
        br.close()


try:
    _ui()
    check("U0 brauzer bo'limi oxirigacha yurdi", True)
except Exception as e:                 # noqa: BLE001 — asl kodda test QULAMAYDI, yiqiladi
    check("U0 brauzer bo'limi oxirigacha yurdi", False, f"{type(e).__name__}: {str(e)[:600]}")
check("U9 sahifalarda JS xatosi yo'q", not XATOLAR, XATOLAR[:5])
_srv.should_exit = True

print(f"\nNATIJA: o'tdi = {OK}, yiqildi = {FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(0 if FAIL == 0 else 1)
