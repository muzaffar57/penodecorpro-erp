#!/usr/bin/env python3
"""
test_qaytarish_korinish204.py — kech154 (zip 204 «Qaytarishlar ixcham»; EGASI SAVOLI 22.10 09:06 «nimaga Qaytarishlar bo'limidagi ayrimlari juda
katta», TANLOVI «1 · Hammasi yig'ma»): Qaytarishlar ro'yxatida HAR buyurtma — bitta yig'ma qator, tafsilot — ixcham. FAQAT KO'RINISH.

NIMA UCHUN KERAK (O'LCHANGAN — `work/k203/ekran204.py`, zip 203 kodi, haqiqiy Chromium, 1440 px): bitta qaytarishli buyurtma guruhlanmasdi —
  katta karta (70 px rasm joyi, brak bosqichi / sababi / javobgari holat ustunida 3–4 qatorda) — qator 62–103 px; 2+ qaytarishli buyurtma —
  ixcham qator (47 px); ro'yxat notekis, telefonda bitta yozuv 4–5 qavat.
BO'LIMLAR:
  S — manba (`templates/returns.html`): bitta yozuv ham yig'iladi; sarlavhada mahsulot nomi va «💰 Hisob-kitob kutilmoqda» (escape);
      brak tafsiloti nom ostida (`.ret-brak-satr`, o'sha klasslar), holat ustunida faqat belgi; qator ma'lumoti va amallar o'sha.
  D — HAQIQIY Chromium + lokal server, ma'lumot API orqali (brakli bitta qaytarishli buyurtma — bosqich / sabab / javobgar; hisob-kitobi
      kutilayotgan bitta butun qaytarishli buyurtma; 3 yozuvli buyurtma — 2 butun (biri hisob-kitob qilingan), 1 brak): har buyurtma —
      bitta yopiq qator (bir xil balandlik ≤ 64 px), sarlavhada mahsulot / «… va yana N ta», butun / brak soni, kutilayotgan hisob-kitob
      belgisi FAQAT o'sha buyurtmalarda; ochilganda tafsilot ixcham (≤ 72 px, brak satri BIR qatorda, rasm joyi 42 px), amallar o'sha;
      qidiruv va filtr guruhni o'zi ochadi, tozalansa yopadi; Enter bilan ochiladi; telefon (390 px) — yon tomonga toshmaydi, ro'yxat
      qisqa; tungi rejimda belgi kontrasti; JS xatosi yo'q.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`. Asl kodga (zip 203) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_qaytarish_korinish204.py
"""
import os
import io
import re
import sys
import glob
import time
import socket
import tempfile
import datetime
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
_T = tempfile.mkdtemp(prefix="k204_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k204.db')}"
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
        if callable(detail):
            try:
                detail = detail()
            except Exception as e:         # noqa: BLE001
                detail = f"{type(e).__name__}: {e}"
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def xav(f, *a, standart=None, **k):
    try:
        return f(*a, **k)
    except Exception as e:                 # noqa: BLE001
        print(f"    (bajarilmadi: {getattr(f, '__name__', f)} — {type(e).__name__}: {str(e)[:200]})")
        return standart


def rgb(s):
    m = re.findall(r"[\d.]+", s or "")
    return tuple(float(x) for x in m[:3]) if len(m) >= 3 else None


def _lum(c):
    def k(v):
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * k(c[0]) + 0.7152 * k(c[1]) + 0.0722 * k(c[2])


def kontrast(a, b):
    if not a or not b:
        return 0
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
RET = open(os.path.join(ROOT, "templates", "returns.html"), encoding="utf-8").read()
_gf = RET[RET.find("function groupReturnsByOrder(){"):]
_gf = _gf[:_gf.find("\ngroupReturnsByOrder();")]
check("S1 HAR buyurtma yig'ma qator: bitta yozuv ham yig'iladi (`groupRows.length < 2` qaytishi yo'q); sarlavhada mahsulot nomi va "
      "«💰 Hisob-kitob kutilmoqda» — `escapeHtml` bilan",
      _gf and "if (!rows.length) return;" in _gf and "groupRows.length < 2" not in _gf and "rows.length < 2" not in _gf
      and '<span class="g-nom">${escapeHtml(nom)}</span>' in _gf and '<span class="g-kutil">💰 Hisob-kitob kutilmoqda</span>' in _gf
      and "r.querySelector('.refund-btn, .refund-no')" in _gf and "${escapeHtml(orderKey)}" in _gf, len(_gf))
_nm = RET[RET.find('<div class="ret-name"'):RET.find('<div class="ret-qty"')]
_st = RET[RET.find('<div class="ret-status"'):RET.find('<div class="ret-dest"')]
check("S2 brak bosqichi / sababi / javobgari — nom ostidagi bitta satrda (`.ret-brak-satr`, o'sha klasslar); holat ustunida faqat belgi",
      '<div class="ret-brak-satr">' in _nm and '<div class="brak-bosqich">' in _nm and '<div class="brak-sabab">' in _nm
      and '<div class="brak-javobgar">' in _nm and "brak-bosqich" not in _st and "brak-sabab" not in _st and "brak-javobgar" not in _st
      and '<span class="badge badge-danger">🔴 Brak</span>' in _st, (len(_nm), len(_st)))
_qr = RET[RET.find('<div class="ret-row'):RET.find("{% endfor %}", RET.find('<div class="ret-row'))]
check("S3 qator ma'lumoti va amallari o'sha: `data-reason`, `data-refund`, `data-order`, `data-mijoz`, `data-sana`, `data-summa`, `data-search`; "
      "rasm, «Hisob-kitob qilish», brak taqdiri, o'chirish",
      all(a in _qr for a in ('data-reason="{{ r.reason.value }}"', "data-refund=", "data-order=", "data-mijoz=", "data-sana=", "data-summa=",
                             "data-search=", 'data-nom="{{ r.item_name }}"', 'onchange="uploadReturnImage({{ r.id }}, this)"',
                             'onclick="toggleRefund({{ r.id }}, false)"', 'onclick="taqdirOynaOch(this)"', 'onclick="deleteReturn({{ r.id }})"')),
      len(_qr))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# tayyorgarlik — ma'lumot API orqali
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_bosh = io.StringIO()
with contextlib.redirect_stdout(_bosh):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Inventory, Project, Master   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k204_a", PAROL, UserRole.ADMIN, "K204 Admin", company_id=1)
PENO = Inventory(company_id=1, item_name="K204 Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
P1 = Project(company_id=1, client_name="Sardor K204", project_name="Andijon K204", client_phone="+998977001122", total_budget=0, total_paid=0)
P2 = Project(company_id=1, client_name="Malika K204", project_name="Namangan K204", client_phone="+998994443322", total_budget=0, total_paid=0)
US = Master(company_id=1, name="K204 Usta", phone="+998900002040")
s.add_all([PENO, P1, P2, US])
s.commit()
ID = {"PENO": PENO.id, "P1": P1.id, "P2": P2.id, "US": US.id}
s.close()

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lg = C.post("/login", data={"username": "k204_a", "password": PAROL}, follow_redirects=False)
TK = (datetime.datetime.utcnow() + datetime.timedelta(hours=5)).date()
_hd = C.post("/api/employees", json={"name": "K204 Hodim", "position": "Kesuvchi", "pay_type": "fixed", "fixed_amount": 3000000,
                                     "production_type": "umumiy", "notes": ""})
HODIM = (_hd.json() or {}).get("id") if _hd.status_code == 200 else None


def buyurtma(pid, detallar):
    tana = {"project_id": pid, "order_type": "product", "recipe_id": None, "master_id": ID["US"], "deadline": (TK + datetime.timedelta(days=5)).isoformat(),
            "is_draft": False, "base_price": 600000, "loy_kg": None,
            "items": [{"name": n, "category": "panel", "width": 60, "thickness": 5, "length": 0, "quantity": q, "unit_price": p, "is_coated": False,
                       "penoplast_id": ID["PENO"], "price_per_m3": None, "finished_product_id": None} for n, q, p in detallar]}
    r = C.post("/api/orders", json=tana)
    if r.status_code == 409:
        r = C.post("/api/orders?confirm_shortage=true", json=tana)
    return (r.json() or {}).get("id") if r.status_code == 200 else None


def topshir(oid):
    h = ((C.get(f"/api/orders/{oid}/delivery-status").json() or {}).get("items")) or []
    r = C.post("/api/deliveries", json={"order_id": oid, "items": [{"order_item_id": x["id"], "quantity": x["remaining"]} for x in h if x["remaining"] > 0],
                                        "received_by": "Qabul K204", "notes": "", "transport_carrier": "", "transport_cost": 0, "transport_payer": "client"})
    return r.status_code, h


def qaytar(oid, d, miqdor, brak=False, pul=0, bosqich=None, sabab=None, jav=False):
    tana = {"order_id": oid, "order_item_id": d["id"], "item_name": d["name"], "quantity": miqdor, "unit": d["unit"],
            "reason": "Brak" if brak else "Ortiqcha", "refund_amount": 0 if brak else pul, "to_stock": not brak, "notes": "",
            "coating_applied": False}
    if brak:
        tana.update({"brak_bosqich": bosqich, "brak_sabab": sabab, **({"brak_javobgar_id": HODIM} if jav and HODIM else {})})
    r = C.post("/api/returns", json=tana)
    return (r.json() or {}).get("id") if r.status_code == 200 else None


O = {"brak": buyurtma(ID["P1"], [("Ustun bazasi", 8, 210000)]),
     "butun": buyurtma(ID["P2"], [("Devor paneli", 20, 22000)]),
     "kop": buyurtma(ID["P1"], [("Fasad karnizi", 30, 52000), ("Ustun kapiteli", 4, 380000)])}
D = {k: topshir(v)[1] if v else [] for k, v in O.items()}
Q = {}
if all(O.values()) and all(D.values()):
    Q["brak"] = qaytar(O["brak"], D["brak"][0], 1, brak=True, bosqich="saqlash_tashish", sabab="ishchi", jav=True)
    Q["butun"] = qaytar(O["butun"], D["butun"][0], 3, pul=66000)
    Q["kop1"] = qaytar(O["kop"], D["kop"][0], 2, pul=104000)
    Q["kop2"] = qaytar(O["kop"], D["kop"][0], 1, pul=52000)
    Q["kop3"] = qaytar(O["kop"], D["kop"][1], 1, brak=True, bosqich="kesish", sabab="uskuna")
    _rf = C.post(f"/api/returns/{Q['kop2']}/refund") if Q.get("kop2") else None
NUM = {k: (C.get(f"/api/orders/{v}").json() or {}).get("order_number") if v else None for k, v in O.items()}
check("T0 fikstura: kirish, hodim, 3 buyurtma topshirilgan, 5 qaytarish (2 brak, 3 butun — biri hisob-kitob qilingan)",
      _lg.status_code in (302, 303) and HODIM and all(O.values()) and len(Q) == 5 and all(Q.values())
      and _rf is not None and _rf.status_code == 200, (O, Q, getattr(_rf, "status_code", None)))

import uvicorn                                     # noqa: E402
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

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D — HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
PW_BOR = True
try:
    from playwright.sync_api import sync_playwright
except Exception:                          # noqa: BLE001
    PW_BOR = False
check("D0 Python `playwright` bor", PW_BOR)

ROYXAT = r"""() => {
  const l = document.getElementById('retList');
  const top = [...l.children].filter(e => e.offsetParent !== null);
  const h = [...l.querySelectorAll(':scope > .ret-group-header')].map(e => ({m: e.innerText.replace(/\s+/g, ' ').trim(), y: Math.round(e.getBoundingClientRect().height),
     ochiq: e.classList.contains('open'), nom: (e.querySelector('.g-nom') || {}).textContent || null, kutil: !!e.querySelector('.g-kutil')}));
  return {sarlavha: h, yakka: [...l.querySelectorAll(':scope > .ret-row')].filter(e => e.offsetParent !== null).length,
          korinadigan_qator: [...l.querySelectorAll('.ret-row')].filter(e => e.offsetParent !== null).length,
          balandlik: Math.round(l.getBoundingClientRect().height), kenglik: document.documentElement.scrollWidth - document.documentElement.clientWidth};
}"""
TAFSILOT = r"""(raqam) => {
  const h = [...document.querySelectorAll('#retList > .ret-group-header')].find(e => e.querySelector('.g-title').textContent === raqam);
  if (!h) return null;
  h.click();
  const b = document.getElementById(h.dataset.target);
  return [...b.querySelectorAll('.ret-row')].map(r => {
    const s = r.querySelector('.ret-brak-satr'), i = r.querySelector('.ret-icon');
    return {y: Math.round(r.getBoundingClientRect().height), ikon: i ? Math.round(i.getBoundingClientRect().width) : null,
            satr: s ? s.innerText.replace(/\s+/g, ' ').trim() : null, satr_y: s ? Math.round(s.getBoundingClientRect().height) : null,
            amal: [...r.querySelectorAll('button')].filter(x => x.offsetParent !== null).map(x => (x.getAttribute('onclick') || '').split('(')[0]),
            korinadi: r.offsetParent !== null};
  });
}"""
NAT = {}
XATO = []

if PW_BOR and len(Q) == 5:
    with sync_playwright() as pw:
        _exe = None
        for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                "chrome-linux", "chrome"))):
            _exe = _y
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()

        def sahifa(w, h, tel=False, tungi=False):
            ctx = br.new_context(viewport={"width": w, "height": h}, timezone_id="Asia/Tashkent", locale="uz-UZ", is_mobile=tel, has_touch=tel)
            ctx.set_default_timeout(20000)
            ctx.route(re.compile(r"^https://.*"), lambda r: r.fulfill(status=204, body=""))
            if tungi:
                ctx.add_init_script("try { localStorage.setItem('theme', 'dark'); } catch (e) {}")
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: XATO.append(str(e)[:300]))
            xav(pg.goto, BU + "/login")
            xav(pg.fill, "input[name=username]", "k204_a")
            xav(pg.fill, "input[name=password]", PAROL)
            xav(pg.press, "input[name=password]", "Enter")
            xav(pg.wait_for_load_state, "networkidle")
            xav(pg.goto, BU + "/returns")
            xav(pg.wait_for_load_state, "networkidle")
            xav(pg.wait_for_timeout, 600)
            return ctx, pg

        ctx, pg = sahifa(1440, 1000)
        NAT["royxat"] = xav(pg.evaluate, ROYXAT)
        NAT["kop"] = xav(pg.evaluate, TAFSILOT, NUM["kop"])
        NAT["brak"] = xav(pg.evaluate, TAFSILOT, NUM["brak"])
        xav(pg.evaluate, "() => document.querySelectorAll('#retList > .ret-group-header.open').forEach(h => h.click())")
        xav(pg.fill, "#ret-search", "Ustun bazasi")
        xav(pg.wait_for_timeout, 250)
        NAT["qidiruv"] = xav(pg.evaluate, r"""() => [...document.querySelectorAll('#retList > .ret-group-header')].filter(h => h.style.display !== 'none')
            .map(h => [h.querySelector('.g-title').textContent, h.classList.contains('open')])""")
        xav(pg.fill, "#ret-search", "")
        xav(pg.wait_for_timeout, 250)
        NAT["qidiruv_tozalandi"] = xav(pg.evaluate, "() => [...document.querySelectorAll('#retList > .ret-group-header')].map(h => h.classList.contains('open'))")
        xav(pg.select_option, "#filter-reason", "Brak")
        xav(pg.wait_for_timeout, 250)
        NAT["filtr"] = xav(pg.evaluate, r"""() => ({sarlavha: [...document.querySelectorAll('#retList > .ret-group-header')].filter(h => h.style.display !== 'none')
            .map(h => [h.querySelector('.g-title').textContent, h.classList.contains('open')]),
            qator: [...document.querySelectorAll('#retList .ret-row')].filter(r => r.offsetParent !== null).map(r => r.dataset.reason)})""")
        xav(pg.select_option, "#filter-reason", "")
        xav(pg.wait_for_timeout, 250)
        xav(pg.evaluate, f"() => {{ const h = [...document.querySelectorAll('#retList > .ret-group-header')].find(e => e.querySelector('.g-title').textContent === {NUM['butun']!r}); h.focus(); }}")
        xav(pg.keyboard.press, "Enter")
        NAT["enter"] = xav(pg.evaluate, f"() => [...document.querySelectorAll('#retList > .ret-group-header')].find(e => e.querySelector('.g-title').textContent === {NUM['butun']!r}).classList.contains('open')")
        NAT["yorug"] = xav(pg.evaluate, r"""() => { const k = document.querySelector('.g-kutil'), s = document.querySelector('.ret-brak-satr .brak-sabab');
            const kart = s ? getComputedStyle(s.closest('.ret-row')).backgroundColor : null;
            return {k_rang: k ? getComputedStyle(k).color : null, k_fon: k ? getComputedStyle(k).backgroundColor : null,
                    s_rang: s ? getComputedStyle(s).color : null, kart}; }""")
        ctx.close()

        ctx, pg = sahifa(1440, 1000, tungi=True)
        xav(pg.evaluate, TAFSILOT, NUM["brak"])
        NAT["tungi"] = xav(pg.evaluate, r"""() => { const k = document.querySelector('.g-kutil'), s = document.querySelector('.ret-brak-satr .brak-sabab');
            return {tema: document.documentElement.getAttribute('data-theme'), k_rang: k ? getComputedStyle(k).color : null,
                    k_fon: k ? getComputedStyle(k).backgroundColor : null, s_rang: s ? getComputedStyle(s).color : null,
                    kart: s ? getComputedStyle(s.closest('.ret-row')).backgroundColor : null}; }""")
        ctx.close()

        ctx, pg = sahifa(390, 844, tel=True)
        NAT["telefon"] = xav(pg.evaluate, ROYXAT)
        NAT["telefon_kop"] = xav(pg.evaluate, TAFSILOT, NUM["kop"])
        NAT["telefon_kenglik"] = xav(pg.evaluate, "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        ctx.close()
        br.close()

    _r = NAT.get("royxat") or {}
    _s = _r.get("sarlavha") or []
    _sar = {x["m"].split(" ")[0]: x for x in _s}
    check("D1 HAR buyurtma — bitta yopiq yig'ma qator (3 ta), ochiq turgan yakka qator yo'q; balandligi bir xil — 56…64 px (ilgari 62–103 px "
          "va 47 px aralash)",
          len(_s) == 3 and _r.get("yakka") == 0 and _r.get("korinadigan_qator") == 0 and not any(x["ochiq"] for x in _s)
          and 56 <= min(x["y"] for x in _s) and max(x["y"] for x in _s) <= 64 and max(x["y"] for x in _s) - min(x["y"] for x in _s) <= 2, _r)
    _b, _u, _k = _sar.get(NUM["brak"]) or {}, _sar.get(NUM["butun"]) or {}, _sar.get(NUM["kop"]) or {}
    check("D2 sarlavhada mahsulot nomi: bitta yozuvli — «Ustun bazasi» / «Devor paneli», 3 yozuvli — «… va yana 2 ta»; butun / brak soni; "
          "summa; sana; soni",
          _b.get("nom") == "Ustun bazasi" and "🔴 1 brak" in _b.get("m", "") and _b.get("m", "").endswith("1 ta")
          and _u.get("nom") == "Devor paneli" and "🟢 1 butun" in _u.get("m", "") and "66 000 so'm" in _u.get("m", "").replace(" ", " ")
          and (_k.get("nom") or "").endswith("va yana 2 ta") and "🟢 2 butun · 🔴 1 brak" in _k.get("m", "") and _k.get("m", "").endswith("3 ta")
          and all(re.search(r"\d\d\.\d\d\.\d{4}", x.get("m", "")) for x in (_b, _u, _k)), _s)
    check("D3 «💰 Hisob-kitob kutilmoqda» — faqat hisob-kitobi qilinmagan butun qaytarishli buyurtmalarda (yopiq qatorda ham ko'rinadi); "
          "brakli buyurtmada yo'q",
          _u.get("kutil") is True and _k.get("kutil") is True and _b.get("kutil") is False, _s)
    _kp, _bk = NAT.get("kop") or [], NAT.get("brak") or []
    check("D4 ochilganda tafsilot ixcham: har qator ≤ 72 px, rasm joyi 42 px, amallar (hisob-kitob, brak taqdiri, o'chirish) o'sha",
          len(_kp) == 3 and len(_bk) == 1 and all(x["korinadi"] and x["y"] <= 72 and x["ikon"] == 42 for x in _kp + _bk)
          and any("toggleRefund" in x["amal"] for x in _kp) and "taqdirOynaOch" in _bk[0]["amal"] and "deleteReturn" in _bk[0]["amal"], (_kp, _bk))
    check("D5 brak bosqichi · sababi · 👤 javobgar — nom ostida BIR satrda (≤ 20 px)",
          _bk and _bk[0]["satr"] and "Saqlash / tashish" in _bk[0]["satr"] and "Ishchi xatosi" in _bk[0]["satr"] and "👤 K204 Hodim" in _bk[0]["satr"]
          and (_bk[0]["satr_y"] or 99) <= 20, _bk)
    check("D6 qidiruv «Ustun bazasi» — faqat o'sha buyurtma qatori ko'rinadi va O'ZI ochiladi; tozalansa — hammasi yana yopiq",
          NAT.get("qidiruv") == [[NUM["brak"], True]] and NAT.get("qidiruv_tozalandi") == [False, False, False],
          (NAT.get("qidiruv"), NAT.get("qidiruv_tozalandi")))
    _f = NAT.get("filtr") or {}
    check("D7 filtr «Brak» — brakli 2 buyurtma qatori ochiladi, faqat brak yozuvlari ko'rinadi",
          sorted(x[0] for x in _f.get("sarlavha", [])) == sorted([NUM["brak"], NUM["kop"]]) and all(x[1] for x in _f.get("sarlavha", []))
          and _f.get("qator") == ["Brak", "Brak"], _f)
    check("D8 yig'ma qator klaviatura bilan ochiladi (Enter)", NAT.get("enter") is True, NAT.get("enter"))
    _t, _tk = NAT.get("telefon") or {}, NAT.get("telefon_kop") or []
    check("D9 telefon (390 px): 3 yig'ma qator, ro'yxat ≤ 420 px (ilgari bitta yozuv 4–5 qavat), yon tomonga toshmaydi; ochilganda tafsilot ko'rinadi",
          len(_t.get("sarlavha") or []) == 3 and (_t.get("balandlik") or 9999) <= 420 and NAT.get("telefon_kenglik", 9) <= 1
          and len(_tk) == 3 and all(x["korinadi"] for x in _tk), (_t, _tk, NAT.get("telefon_kenglik")))
    _y, _tg = NAT.get("yorug") or {}, NAT.get("tungi") or {}
    check("D10 kontrast ≥ 4,5:1 — «💰 Hisob-kitob kutilmoqda» va brak satri (yorug' va tungi rejim)",
          _tg.get("tema") == "dark" and kontrast(rgb(_y.get("k_rang")), rgb(_y.get("k_fon"))) >= 4.5
          and kontrast(rgb(_y.get("s_rang")), rgb(_y.get("kart"))) >= 4.5 and kontrast(rgb(_tg.get("k_rang")), rgb(_tg.get("k_fon"))) >= 4.5
          and kontrast(rgb(_tg.get("s_rang")), rgb(_tg.get("kart"))) >= 4.5,
          (_y, _tg, kontrast(rgb(_y.get("k_rang")), rgb(_y.get("k_fon"))), kontrast(rgb(_y.get("s_rang")), rgb(_y.get("kart"))),
           kontrast(rgb(_tg.get("k_rang")), rgb(_tg.get("k_fon"))), kontrast(rgb(_tg.get("s_rang")), rgb(_tg.get("kart")))))
    check("D11 sahifada JS xatosi yo'q (kompyuter, tungi, telefon)", not XATO, XATO)
server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
