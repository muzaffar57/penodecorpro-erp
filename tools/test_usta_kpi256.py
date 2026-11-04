#!/usr/bin/env python3
"""
test_usta_kpi256.py — kech189 (zip 256: Moliya «− Usta KPI to'landi» — ustaga bog'lanadi).

NIMA UCHUN KERAK
  O'LCHANGAN (`work/k256/probe256.py`, zip 255 kodi, SQ = PG): Moliyadagi «− Usta KPI to'landi» kassadan `usta_kpi` chiqimini ustaga
  BOG'LAMASDAN yozardi — «💸 Keshbek berildi» (naqd) bilan birga bosilsa kassadan 2 marta ayirilardi (−20 000), usta keshbek qoldig'i esa
  1 marta kamayardi; faqat Moliya tugmasi bosilsa — qoldiq umuman kamaymasdi (keshbekni yana berib yuborish mumkin edi).
  Egasi QARORI 05.11 (AskUserQuestion — QAYTA SO'RALMAYDI): «Ustaga bog'lash» — tugma qoladi, bosilganda usta tanlanadi va to'lov
  «Keshbek berildi» (usul «naqd») sifatida yoziladi.
BO'LIMLAR
  S — tayyorgarlik. R — ro'yxat `GET /api/finance/usta-keshbek` (qoldiq KPI sahifasi bilan AYNAN, qoldig'i 0 — yo'q, nofaol, tartib,
  maydonlar, ruxsat, ikkinchi korxona). K — kassa yo'li: `usta_kpi` — 400 (hech narsa yozilmaydi), «Ehson» / boshlang'ich — avvalgidek,
  eski bog'lanmagan yozuvlar ro'yxatda va o'chiriladi. T — to'lov (`POST /api/masters/{id}/keshbek`, naqd): kassadan BIR marta,
  qoldiq kamayadi, qoldiqdan ko'p — 409, ro'yxat yangilanadi. U — sahifa (Chromium): usta tanlovi, qoldiq, tekshiruvlar, saqlash,
  Ehson oynasida tanlov yo'q, bo'sh ro'yxat, ism — matn (XSS yo'q), JS xatosi yo'q.
REJIMLAR: SQLite; `TENANT_FILTER=1`; `PG_URL=postgresql://postgres@127.0.0.1:5432` (PG da U o'tkaziladi).
ISHLATISH: python3 tools/test_usta_kpi256.py
Asl kodga (zip 255) qarshi QULAMAYDI — yiqiladi (yo'l yo'q, `usta_kpi` 200).
"""
import os
import io
import sys
import time
import tempfile
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = f"ustakpi256_{os.getpid()}"
_T = tempfile.mkdtemp(prefix="t256_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 't256.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "DOKON_BOT_TOKEN", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_ENVIRONMENT"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import models                                  # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Master, Project, Inventory, Recipe, RecipeIngredient, CashTransaction)  # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"
UstaKeshbek = getattr(models, "UstaKeshbek", None)
YOL = "/api/finance/usta-keshbek"
KB = "/api/masters/{}/keshbek"


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if callable(detail):
        try:
            detail = detail()
        except Exception as e:             # noqa: BLE001
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


def js(r):
    try:
        x = r.json()
        return x if isinstance(x, (dict, list)) else {}
    except Exception:                      # noqa: BLE001
        return {}


def bazadan(fn):
    d = SessionLocal()
    try:
        return fn(d)
    except Exception:                      # noqa: BLE001
        d.rollback()
        return None
    finally:
        d.close()


main._send_telegram = lambda *a, **k: True
main._tg_post_message = lambda *a, **k: True
main._tg_javob = lambda *a, **k: True

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Tayyorgarlik")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
s.add(Company(id=2, name="T256 Begona"))
s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "t256_admin", PAROL, UserRole.ADMIN, "T256 Admin", company_id=1)
    auth.create_user(s, "t256_moliya", PAROL, UserRole.ACCOUNTANT, "T256 Moliyachi", company_id=1)
    auth.create_user(s, "t256_b", PAROL, UserRole.ADMIN, "T256 B", company_id=2)
PENO = Inventory(company_id=1, item_name="T256 Peno", unit="blok", stock_quantity=100000, price_per_unit=500000, volume_per_unit=1.0,
                 is_penoplast=True, category="Penoplast")
KLEY = Inventory(company_id=1, item_name="T256 Kley", unit="kg", stock_quantity=100000, price_per_unit=2000, category="Kimyo")
s.add_all([PENO, KLEY])
s.flush()
REC = Recipe(company_id=1, name="T256 retsept", batch_size_kg=100.0)
s.add(REC)
s.flush()
s.add(RecipeIngredient(recipe_id=REC.id, inventory_id=KLEY.id, quantity_kg=100.0))
U1 = Master(company_id=1, name="Bobur usta", phone="+998931120001", kpi_percent=10.0, is_active=True)
U2 = Master(company_id=1, name="Anvar usta", phone="+998931120002", kpi_percent=10.0, is_active=True)
U3 = Master(company_id=1, name="Zafar usta", phone="+998931120003", kpi_percent=10.0, is_active=True)     # nofaol bo'ladi
U4 = Master(company_id=1, name="Keshbeksiz usta", phone="+998931120004", kpi_percent=10.0, is_active=True)
UX = Master(company_id=1, name='<img src=x onerror="window.__xss=1">', phone="+998931120005", kpi_percent=10.0, is_active=True)
UB = Master(company_id=2, name="Begona usta", phone="+998931120006", kpi_percent=10.0, is_active=True)
s.add_all([U1, U2, U3, U4, UX, UB])
s.commit()
ID = {"peno": PENO.id, "rec": REC.id, "u1": U1.id, "u2": U2.id, "u3": U3.id, "u4": U4.id, "ux": UX.id, "ub": UB.id}
s.close()


def mijoz(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    assert r.status_code in (302, 303), (login, r.status_code)
    return c


CA = mijoz("t256_admin")
CM = mijoz("t256_moliya")
CB = mijoz("t256_b")
NC = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)


def buyurtma(mid):
    d = SessionLocal()
    try:
        p = Project(company_id=1, client_name="T256 mijoz", project_name=f"T256 {mid}", total_budget=0, total_paid=0)
        d.add(p)
        d.commit()
        pid = p.id
    finally:
        d.close()
    t = {"project_id": pid, "order_type": "product", "loy_kg": 10, "recipe_id": ID["rec"], "master_id": mid,
         "items": [{"name": "D256", "category": "profil", "width": 20, "thickness": 10, "length": 10, "quantity": 1,
                    "unit_price": 500000, "is_coated": True, "penoplast_id": ID["peno"], "recipe_id": ID["rec"]}]}
    with contextlib.redirect_stdout(io.StringIO()):
        oid = js(CA.post("/api/orders", json=t, params={"confirm_shortage": "true"})).get("id")
        rr = CA.post(f"/api/orders/{oid}/ready", params={"loy_kg": "10"})
    return oid, rr.status_code


_st = [buyurtma(ID[k])[1] for k in ("u1", "u2", "u3", "ux")]
d0 = SessionLocal()
d0.get(Master, ID["u3"]).is_active = False
d0.commit()
d0.close()
H0 = {h["turi"]: h for h in (js(CA.get("/api/finance/hisoblar")).get("hisoblar") or [])}
_rq = CA.post("/api/finance/hisoblar/qoldiq", json={"qoldiqlar": [{"hisob_id": H0[t]["id"], "summa": 1_000_000} for t in ("naqd", "bank", "karta")]})


def bal():
    return {h["turi"]: h.get("balans") for h in (js(CA.get("/api/finance/hisoblar")).get("hisoblar") or [])}


def holat(mid):
    return js(CA.get(KB.format(mid)))


def kpi_qoldiq():
    return {int(k): v for k, v in (js(CA.get("/api/masters/kpi-keshbek")).get("qoldiqlar") or {}).items()}


def royxat(c=None):
    return js((c or CA).get(YOL))


def kassa_soni():
    return bazadan(lambda d: d.query(CashTransaction).filter(CashTransaction.company_id == 1).count())


Y = holat(ID["u1"]).get("yozilgan")
check("S1 tayyorgarlik: 4 buyurtma «Tayyor» (200), qoldiq kiritildi (200), usta 10 % — keshbek yozildi (> 0)",
      _st == [200, 200, 200, 200] and _rq.status_code == 200 and (Y or 0) > 0, (_st, _rq.status_code, _rq.text[:200], Y))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. Ro'yxat — keshbek qoldig'i bor ustalar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
r = CA.get(YOL)
R = js(r)
_u = R.get("ustalar") if isinstance(R, dict) else None
check("R1 200; javob — faqat {\"ustalar\": [...]}; har qator maydonlari AYNAN id / nom / qoldiq / faol (foiz, foyda, telefon YO'Q)",
      r.status_code == 200 and isinstance(R, dict) and set(R) == {"ustalar"} and isinstance(_u, list) and _u
      and all(set(x) == {"id", "nom", "qoldiq", "faol"} for x in _u), (r.status_code, r.text[:400]))
_ids = [x.get("id") for x in (_u or [])]
check("R2 qoldig'i bor 4 usta (nofaol ham), keshbeksiz usta va boshqa korxona ustasi YO'Q",
      sorted(_ids) == sorted([ID["u1"], ID["u2"], ID["u3"], ID["ux"]]), _ids)
_kq = kpi_qoldiq()
check("R3 har usta qoldig'i = KPI sahifasi «Qoldiq» ustuni = usta keshbek holati (AYNAN)",
      _u and all(x["qoldiq"] == _kq.get(x["id"]) == holat(x["id"]).get("qoldiq") for x in _u),
      [(x.get("id"), x.get("qoldiq"), _kq.get(x.get("id")), holat(x.get("id")).get("qoldiq")) for x in (_u or [])])
check("R4 tartib: faollar oldin (ism bo'yicha), nofaol oxirida — faol belgisi bilan",
      lambda: [x["nom"] for x in _u] == ['<img src=x onerror="window.__xss=1">', "Anvar usta", "Bobur usta", "Zafar usta"]
      and [x["faol"] for x in _u] == [True, True, True, False], lambda: [(x.get("nom"), x.get("faol")) for x in (_u or [])])
_rm, _rn = CM.get(YOL), NC.get(YOL, follow_redirects=False)
check("R5 ruxsat: «Kassa: Yaratish» yo'q (Moliyachi — faqat ko'rish) — 403; kirilmagan — 401",
      _rm.status_code == 403 and _rn.status_code == 401, (_rm.status_code, _rn.status_code))
_rb = royxat(CB)
check("R6 ikkinchi korxona: o'z ustasi keshbeksiz — ro'yxat bo'sh (1-korxona ustalari ko'rinmaydi)",
      _rb == {"ustalar": []}, _rb)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("K. Kassa yo'li — bog'lanmagan «Usta KPI to'landi» endi yozilmaydi")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
b0, n0 = bal(), kassa_soni()
r = CA.post("/api/finance/cash-transaction", data={"category": "usta_kpi", "amount": -10000, "notes": "Bobur usta", "hisob": "naqd"})
check("K1 `usta_kpi` — 400 (sabab: ustaga bog'lab yoziladi), kassa yozuvi yo'q, hisoblar o'zgarmadi (asl: 200, Naqd −10 000)",
      r.status_code == 400 and "ustaga bog'lab" in r.text and kassa_soni() == n0 and bal() == b0, (r.status_code, r.text[:200], bal(), b0))
r = CA.post("/api/finance/cash-transaction", data={"category": "usta_kpi", "amount": 5000})
check("K2 musbat / hisobsiz `usta_kpi` ham — 400, hech narsa yozilmadi", r.status_code == 400 and kassa_soni() == n0, (r.status_code, r.text[:200]))
r = CA.post("/api/finance/cash-transaction", data={"category": "ehson", "amount": -3000, "hisob": "bank"})
check("K3 «Ehson to'landi» — avvalgidek 200, Bank −3 000", r.status_code == 200 and bal()["bank"] == b0["bank"] - 3000, (r.status_code, bal()))
r = CA.post("/api/finance/cash-transaction", data={"category": "nimadir", "amount": -1})
check("K4 noma'lum kategoriya — 400 (avvalgidek)", r.status_code == 400, r.status_code)
# eski (zip 256 dan oldingi) bog'lanmagan yozuv — ro'yxatda, o'chiriladi
d0 = SessionLocal()
_eski = CashTransaction(company_id=1, category="usta_kpi", amount=-7000, notes="Eski KPI sovg'asi", performed_by="x")
d0.add(_eski)
d0.commit()
EID = _eski.id
d0.close()
_ct = js(CA.get("/api/finance/cash-transactions"))
_rd = CA.delete(f"/api/finance/cash-transactions/{EID}")
check("K5 eski bog'lanmagan «Usta KPI to'landi» — tarixda ko'rinadi va o'chiriladi (200)",
      any(x.get("id") == EID and x.get("category") == "usta_kpi" for x in (_ct if isinstance(_ct, list) else []))
      and _rd.status_code == 200 and bazadan(lambda d: d.get(CashTransaction, EID)) is None, (_rd.status_code, _rd.text[:200]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. To'lov — ustaga bog'lanadi (oyna `POST /api/masters/{id}/keshbek` usul «naqd»)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
b0, q0 = bal(), holat(ID["u1"]).get("qoldiq")
r = CA.post(KB.format(ID["u1"]), json={"summa": 10000, "usul": "naqd", "hisob": "karta", "izoh": "yillik KPI sovg'asi"})
b1, q1 = bal(), holat(ID["u1"]).get("qoldiq")
_x = [x for x in (royxat().get("ustalar") or []) if x.get("id") == ID["u1"]]
_tx = bazadan(lambda d: [(float(t.amount), t.category, t.notes) for t in d.query(CashTransaction).filter(
    CashTransaction.company_id == 1, CashTransaction.category == "usta_kpi").all()]) or []
check("T1 10 000 Karta dan — 200; Karta −10 000 (BIR marta), usta qoldig'i −10 000; ro'yxatda yangi qoldiq; kassa yozuvi «Keshbek — usta …»",
      r.status_code == 200 and b1["karta"] == b0["karta"] - 10000 and b1["naqd"] == b0["naqd"] and b1["bank"] == b0["bank"]
      and q1 == q0 - 10000 and _x and _x[0]["qoldiq"] == q1
      and _tx == [(-10000.0, "usta_kpi", "Keshbek — usta Bobur usta (yillik KPI sovg'asi)")], (r.status_code, r.text[:200], b0, b1, q0, q1, _x, _tx))
r = CA.post(KB.format(ID["u2"]), json={"summa": holat(ID["u2"]).get("qoldiq") + 1, "usul": "naqd", "hisob": "naqd"})
check("T2 qoldiqdan ko'p — 409, kassa o'zgarmadi", r.status_code == 409 and bal() == b1, (r.status_code, r.text[:200]))
_q2 = holat(ID["u2"]).get("qoldiq")
r = CA.post(KB.format(ID["u2"]), json={"summa": _q2, "usul": "naqd", "hisob": "naqd"})
_ids2 = [x.get("id") for x in (royxat().get("ustalar") or [])]
check("T3 qoldiq to'liq berildi — usta ro'yxatdan chiqdi (qoldiq 0)", r.status_code == 200 and ID["u2"] not in _ids2 and ID["u1"] in _ids2,
      (r.status_code, _ids2))
r = CA.post(KB.format(ID["ub"]), json={"summa": 1, "usul": "naqd"})
check("T4 boshqa korxona ustasiga — 404", r.status_code == 404, r.status_code)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("U. Sahifa — Moliya «− Usta KPI to'landi» oynasi (Chromium)")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
if PG_URL:
    print("  (PG rejimida UI bo'limi o'tkazib yuboriladi — SQLite / TF1 da)")
else:
    import glob
    import socket
    import threading
    import uvicorn
    from playwright.sync_api import sync_playwright
    _sk = socket.socket()
    _sk.bind(("127.0.0.1", 0))
    PORT = _sk.getsockname()[1]
    _sk.close()
    _srv = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=PORT, log_level="error", lifespan="off"))
    threading.Thread(target=_srv.run, daemon=True).start()
    while not _srv.started:
        time.sleep(0.1)
    BASE = f"http://127.0.0.1:{PORT}"
    _exe = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
    XATOLAR = []
    SOROVLAR = []

    def _ui():
        with sync_playwright() as pw:
            br = pw.chromium.launch(executable_path=_exe[-1] if _exe else None)
            ctx = br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent")
            ctx.route("**/*", lambda r: r.fulfill(status=204, body="") if not r.request.url.startswith(BASE) else r.continue_())
            pg = ctx.new_page()
            pg.set_default_timeout(10000)
            pg.on("pageerror", lambda e: XATOLAR.append(str(e)[:200]))
            pg.on("dialog", lambda d: (XATOLAR.append("dialog: " + d.message[:100]), d.accept()))
            pg.on("request", lambda q: SOROVLAR.append((q.method, q.url.replace(BASE, ""))) if q.method == "POST" else None)
            pg.goto(BASE + "/login")
            pg.fill("input[name=username]", "t256_admin")
            pg.fill("input[name=password]", PAROL)
            pg.press("input[name=password]", "Enter")
            pg.wait_for_load_state("networkidle")

            def tasdiq():
                pg.wait_for_timeout(250)
                return pg.evaluate("""() => { const b = [...document.querySelectorAll('button')].filter(x => x.offsetParent !== null &&
                    /^(Ha, |Ha$|OK$|Tasdiqlash$)/.test(x.textContent.trim())); if (b.length) { b[b.length - 1].click(); return true; } return false; }""")

            def oyna():
                return pg.evaluate("""() => ({joy: getComputedStyle(document.getElementById('cashtx-usta-joy')).display,
                    opt: [...document.querySelectorAll('#cashtx-usta option')].map(o => [o.value, o.textContent.replace(/[\\s\\u00a0\\u202f]+/g, ' ').trim()]),
                    dis: document.getElementById('cashtx-usta').disabled,
                    izoh: document.getElementById('cashtx-usta-izoh').textContent.replace(/[\\s\\u00a0\\u202f]+/g, ' ').trim(),
                    xato: document.getElementById('cashtx-error').style.display === 'none' ? '' : document.getElementById('cashtx-error').textContent,
                    max: document.getElementById('cashtx-notes').getAttribute('maxlength'),
                    hint: document.getElementById('cashTxHint').textContent, img: document.querySelectorAll('#cashTxModal img').length,
                    xss: window.__xss || 0, ochiq: document.getElementById('cashTxModal').style.display})""")

            pg.goto(BASE + "/finance", wait_until="networkidle")
            pg.wait_for_timeout(500)
            pg.click("text=− Usta KPI to'landi")
            pg.wait_for_timeout(700)
            o1 = oyna()
            _q1 = holat(ID["u1"]).get("qoldiq")
            check("U1 oyna: «Qaysi ustaga?» tanlovi ko'rinadi — «— ustani tanlang —», faollar (ism, qoldiq), nofaol «(nofaol)»; qoldig'i 0 usta "
                  "(Anvar) YO'Q; izoh maydoni ≤ 200; yo'riqnomada «Keshbek berildi» bilan bir xil ekani",
                  o1["joy"] == "block" and not o1["dis"] and o1["opt"][0] == ["", "— ustani tanlang —"]
                  and [x[0] for x in o1["opt"][1:]] == [str(ID["ux"]), str(ID["u1"]), str(ID["u3"])]
                  and o1["opt"][2][1].startswith("Bobur usta — qoldiq ") and o1["opt"][2][1].endswith(" so'm")
                  and o1["opt"][3][1].endswith("(nofaol)") and o1["max"] == "200" and "Keshbek berildi" in o1["hint"],
                  o1)
            check("U2 usta ismi — MATN (HTML ishlamaydi): <img> yo'q, onerror bajarilmadi",
                  o1["img"] == 0 and o1["xss"] == 0 and o1["opt"][1][1].startswith('<img src=x onerror="window.__xss=1"> — qoldiq'), o1)
            n_post = len(SOROVLAR)
            pg.fill("#cashtx-amount", "5 000")
            pg.click("#cashTxModal >> text=Saqlash")
            pg.wait_for_timeout(300)
            o2 = oyna()
            check("U3 usta tanlanmasa — «Ustani tanlang», so'rov YUBORILMADI", o2["xato"] == "Ustani tanlang" and len(SOROVLAR) == n_post,
                  (o2["xato"], SOROVLAR[n_post:]))
            pg.select_option("#cashtx-usta", str(ID["u1"]))
            pg.wait_for_timeout(150)
            o3 = oyna()
            pg.fill("#cashtx-amount", str(int(_q1) + 1))
            pg.click("#cashTxModal >> text=Saqlash")
            pg.wait_for_timeout(300)
            o4 = oyna()
            check("U4 tanlanganda — «Keshbek qoldig'i: … so'm»; qoldiqdan ko'p — «Qoldiqdan ko'p — …», so'rov YUBORILMADI",
                  o3["izoh"].startswith("Keshbek qoldig'i:") and o4["xato"].startswith("Qoldiqdan ko'p — Bobur usta") and len(SOROVLAR) == n_post,
                  (o3["izoh"], o4["xato"], SOROVLAR[n_post:]))
            b_ui0 = bal()
            pg.fill("#cashtx-amount", "12 345")
            pg.fill("#cashtx-notes", "UI sovg'a")
            pg.click("#cashtx-hisob button[data-turi='bank']")
            pg.click("#cashTxModal >> text=Saqlash")
            pg.wait_for_timeout(300)
            _savol = pg.evaluate("() => [...document.querySelectorAll('div,p')].filter(x => x.offsetParent !== null && "
                                 "/Kassadan −/.test(x.textContent) && x.children.length === 0).map(x => x.textContent).slice(-1)[0] || ''")
            tasdiq()
            pg.wait_for_timeout(1200)
            o5 = oyna()
            b_ui1 = bal()
            _yoz = bazadan(lambda d: [(float(k.summa), k.usul, k.izoh) for k in d.query(UstaKeshbek).filter(
                UstaKeshbek.master_id == ID["u1"]).order_by(UstaKeshbek.id).all()]) or []
            check("U5 saqlash: tasdiq savolida usta va hisob («Kassadan −12 345 so'm … Bobur usta · Bank», qoldiq → …); so'rov — "
                  "`POST /api/masters/{id}/keshbek` (kassa yo'li EMAS); Bank −12 345 (bir marta); keshbek yozuvi «naqd», izoh bilan; oyna yopildi",
                  "−12" in _savol and "Bobur usta" in _savol and "Bank" in _savol
                  and SOROVLAR[n_post:] == [("POST", f"/api/masters/{ID['u1']}/keshbek")]
                  and b_ui1["bank"] == b_ui0["bank"] - 12345 and b_ui1["naqd"] == b_ui0["naqd"] and b_ui1["karta"] == b_ui0["karta"]
                  and _yoz[-1] == (12345.0, "naqd", "UI sovg'a") and o5["ochiq"] == "none",
                  (_savol, SOROVLAR[n_post:], b_ui0, b_ui1, _yoz[-1:], o5["ochiq"]))
            pg.click("text=− Ehson to'landi")
            pg.wait_for_timeout(400)
            o6 = oyna()
            pg.evaluate("() => { document.getElementById('cashTxModal').style.display = 'none'; }")
            check("U6 «Ehson to'landi» oynasida usta tanlovi YO'Q, izoh chegarasi olib tashlandi", o6["joy"] == "none" and o6["max"] is None, o6)
            # hamma qoldiq berilgan holat (boshqa korxona — keshbeksiz)
            p2 = ctx.browser.new_context(viewport={"width": 375, "height": 700}).new_page()
            p2.on("pageerror", lambda e: XATOLAR.append(str(e)[:200]))
            p2.goto(BASE + "/login")
            p2.fill("input[name=username]", "t256_b")
            p2.fill("input[name=password]", PAROL)
            p2.press("input[name=password]", "Enter")
            p2.wait_for_load_state("networkidle")
            p2.goto(BASE + "/finance", wait_until="networkidle")
            p2.wait_for_timeout(400)
            p2.click("text=− Usta KPI to'landi")
            p2.wait_for_timeout(700)
            o7 = p2.evaluate("""() => ({opt: [...document.querySelectorAll('#cashtx-usta option')].map(o => o.textContent),
                dis: document.getElementById('cashtx-usta').disabled, izoh: document.getElementById('cashtx-usta-izoh').textContent,
                surish: document.documentElement.scrollWidth - document.documentElement.clientWidth})""")
            check("U7 keshbek qoldig'i bor usta yo'q — «Keshbek qoldig'i bor usta yo'q», tanlov yopiq, izohda sabab; 375 px — gorizontal surilmaydi",
                  o7["opt"] == ["Keshbek qoldig'i bor usta yo'q"] and o7["dis"] and "qoldiq 0" in o7["izoh"] and o7["surish"] <= 0, o7)
            br.close()
    try:
        _ui()
    except Exception as _e:                 # noqa: BLE001
        check("U0 brauzer bo'limi xatosiz yakunlandi", False, f"{type(_e).__name__}: {str(_e)[:300]}")
    check("U8 sahifa JS xatosi / brauzer dialog oynasi yo'q", not XATOLAR, XATOLAR[:5])
    _srv.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
