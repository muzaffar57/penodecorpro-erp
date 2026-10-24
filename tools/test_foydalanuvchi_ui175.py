#!/usr/bin/env python3
"""
test_foydalanuvchi_ui175.py — kech144 (zip 175, audit 2-to'lqin): «Foydalanuvchilar», «Rollar va ruxsatlar», «Sozlamalar»,
«O'chirilganlar» va umumiy tasdiqlash oynasi — HAQIQIY Chromium, HAQIQIY lokal server (uvicorn, test bazasi). Tarmoq xatolari Playwright
`route` bilan ataylab beriladi: so'rov serverda BAJARILADI, javob esa 502 bo'lib qaytadi (`route.fetch` + `fulfill`); tarmoq uzilishi
(`abort`); javob ushlab turiladi (kech javob, saqlash davomi).

NIMA UCHUN KERAK (asl kod = zip 174; audit `work/k173_tayyorgarlik/agentlar/foydalanuvchi/HISOBOT.md`):
  U1  Eski sahifadagi «O'chir» boshqa admin o'chirgan foydalanuvchini QAYTA YOQARDI. U2 / U3: rad — «Xato», internet uzilsa — hech narsa.
  U4  Yangi foydalanuvchi: 502 da JSON xatosi (xabar yo'q), qayta bosish — «Bu username band» (yaratilgan bo'lsa ham).
  U9  QR oynasi: korxona kodi yuklanmasa — kodsiz havola (hodim korxonani tanlay olmaydi). U12: «Hammasini o'chirish» 502 da inglizcha
      «Unexpected token» va «bog'lanib bo'lmadi» (bajarilgan bo'lishi mumkin). U13: yopilgan oynada parol qolardi. U14: rollar soni.
  R1  «Rollar»: birinchi yuklash xatosida ro'yxat va jadval abadiy «Yuklanmoqda…». R2: Admin nusxasi — bo'sh rol + tekshirilmagan PUT.
  R3  Yangi rol / nusxa saqlanmagan o'zgarishlarni JIM tashlardi. R4: rol o'zgartirish tarmoq xatosi ushlanmasdi. R5: ikkinchi DELETE.
  R6  Saqlash paytida belgilar ochiq — o'sha paytdagi belgi jim yo'qolardi. R7: eski javob yangisini bosardi.
  C1 / C2  «Sozlamalar»: ro'yxat / korxona ma'lumoti yuklanmasa ham «Saqlash» ishlardi (Loy sotish, Blok o'chardi; slogan, telefon,
      manzil tozalanardi). C3: 403 da yolg'on «Sozlanmagan». C4 / C5: rad etilsa ham maydon tozalanardi. C9 / C10: logotipdan keyin.
      C12: yo'nalishni o'chirish uchinchi tez bosishda ikkinchi DELETE.
  T5  «Butunlay o'chirish» ikki marta — ikki DELETE. X1: ikki tasdiqlash oynasi — birinchisi hech qachon tugamasdi.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16. Asl kodga (zip 174) qarshi QULAMAYDI — yiqiladi.
TALAB: Python `playwright` + Chromium.
ISHLATISH: python3 tools/test_foydalanuvchi_ui175.py
"""
import os
import re
import io
import sys
import glob
import json
import time
import base64
import socket
import tempfile
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "foydalanuvchi_ui175_test"
_T = tempfile.mkdtemp(prefix="fyui175_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'fyui175.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import ruxsatlar as RX                             # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, Rol, Project, Yonalish   # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []
PAROL = "Parol123!"


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
        print(f"  ✗ {label}   {str(detail)[:700]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


def db_ishi(fn):
    s = SessionLocal()
    try:
        r = fn(s)
        s.commit()
        return r
    finally:
        s.close()


def foydalanuvchi(login):
    """{id, rol_id, is_active} (sessiya yopilgach ham o'qiladi)."""
    from types import SimpleNamespace

    def f(s):
        u = s.query(User).filter(User.username == login).first()
        return SimpleNamespace(id=u.id, rol_id=u.rol_id, is_active=bool(u.is_active)) if u else None
    return db_ishi(f)


def faolmi(login):
    return db_ishi(lambda s: bool(s.query(User).filter(User.username == login).first().is_active))


def foyd_soni(login):
    return db_ishi(lambda s: s.query(User).filter(User.username == login).count())


def rol_soni(nom):
    return db_ishi(lambda s: s.query(Rol).filter(Rol.company_id == 1, Rol.nom == nom).count())


def rol_ruxsat(nom):
    def f(s):
        r = s.query(Rol).filter(Rol.company_id == 1, Rol.nom == nom).first()
        return RX.ruxsatlar_oqi(r.ruxsatlar) if r else None
    return db_ishi(f)


def rol_id(nom):
    return db_ishi(lambda s: (s.query(Rol).filter(Rol.company_id == 1, Rol.nom == nom).first() or Rol(id=None)).id)


def rol_qoy(login, ruxsat, nom):
    def f(s):
        u = s.query(User).filter(User.username == login).first()
        r = Rol(company_id=u.company_id, nom=nom, kod=None, ruxsatlar=json.dumps(ruxsat), tavsif="")
        s.add(r)
        s.flush()
        u.rol_id = r.id
        return r.id
    return db_ishi(f)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Tayyorgarlik
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "fu_admin", PAROL, UserRole.ADMIN, "FU Admin", company_id=1)
    for _u in ("fu_ishchi", "fu_ishchi2", "fu_soz", "fu_jur"):
        auth.create_user(s, _u, PAROL, UserRole.MANAGER, _u.upper(), company_id=1)
s.commit()
s.close()
rol_qoy("fu_soz", {"jurnal": ["korish"], "sozlama": ["tahrirlash"]}, "FU175 Sozlama muharriri")     # Ko'rishsiz (403 lar)
rol_qoy("fu_jur", {"jurnal": ["korish"]}, "FU175 Jurnal")

C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
assert C.post("/login", data={"username": "fu_admin", "password": PAROL}, follow_redirects=False).status_code in (302, 303)
_cats = ",".join(c["code"] for c in js(C.get("/api/settings/categories")).get("categories") or [])
C.put("/api/settings/categories", data={"codes": _cats})
_r = js(C.post("/api/rollar", json={"nom": "FU175 Ochiriladigan", "ruxsatlar": {"buyurtma": ["korish"]}}))
ID = {"ROL_OCH": _r.get("id")}
_r = js(C.post("/api/rollar", json={"nom": "FU175 Tahrir", "ruxsatlar": {"buyurtma": ["korish"]}}))
ID["ROL_T"] = _r.get("id")
ID["ISH"] = foydalanuvchi("fu_ishchi").id
ID["ISH2"] = foydalanuvchi("fu_ishchi2").id
ID["MEN"] = db_ishi(lambda s: s.query(User).filter(User.username == "fu_ishchi").first().rol_id)
ID["PRJ_DEL"] = db_ishi(lambda s: (lambda p: (s.add(p), s.flush(), p.id)[2])(
    Project(company_id=1, project_number="FU-DEL", project_name="FU savatdagi", client_name="Mijoz", is_deleted=True)))
ID["YON"] = db_ishi(lambda s: (lambda y: (s.add(y), s.flush(), y.id)[2])(Yonalish(company_id=1, nom="FU175 Yo'nalish")))


def kategoriyalar():
    return {c["code"]: c["enabled"] for c in (js(C.get("/api/settings/categories")).get("categories") or [])}


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# Server va brauzer
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_x = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_x = False, f"{type(_e).__name__}: {_e}"
import uvicorn                                     # noqa: E402


def _port():
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    p = so.getsockname()[1]
    so.close()
    return p


port = _port()
server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
threading.Thread(target=server.run, daemon=True).start()
for _ in range(150):
    if server.started:
        break
    time.sleep(0.1)
B = f"http://127.0.0.1:{port}"
pw_ctx = br = None
if PW_BOR and server.started:
    pw_ctx = sync_playwright().start()
    _exe = None
    for _yol in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                              "chrome-linux", "chrome"))):
        _exe = _yol
    try:
        br = pw_ctx.chromium.launch(executable_path=_exe) if _exe else pw_ctx.chromium.launch()
    except Exception as _e:                # noqa: BLE001
        br = None
        _pw_x = f"{type(_e).__name__}: {_e}"
check("T0 lokal server va Chromium", bool(server.started and br), _pw_x)
JS_XATO, SOROV, JAVOB = [], [], []


def _tana(q):
    """So'rov tanasi matn sifatida (rasm kabi ikkilik tana — `latin-1` bilan, yiqilmasin)."""
    try:
        return q.post_data
    except Exception:                      # noqa: BLE001
        try:
            b = q.post_data_buffer
            return b.decode("latin-1") if b else None
        except Exception:                  # noqa: BLE001
            return None


def kontekst(user="fu_admin"):
    ctx = br.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Tashkent", locale="uz-UZ")
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1).*"), lambda route: route.fulfill(status=204, body=""))
    pg = ctx.new_page()
    pg.set_default_timeout(15000)
    pg.on("pageerror", lambda e: JS_XATO.append(str(e)[:200]))
    pg.on("request", lambda q: SOROV.append((q.method, q.url.replace(B, ""), _tana(q), q.headers.get("x-amal-kaliti")))
          if "/api/" in q.url and q.method in ("POST", "PUT", "DELETE") else None)
    pg.on("response", lambda r: JAVOB.append((r.request.method, r.url.replace(B, ""), r.status, r.headers.get("x-takror")))
          if "/api/" in r.url and r.request.method in ("POST", "PUT", "DELETE") else None)
    pg.goto(B + "/login")
    pg.fill("input[name=username]", user)
    pg.fill("input[name=password]", PAROL)
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    return ctx, pg


# Xabarlar, tasdiq va kiritish oynalari: `window.__msg`; tasdiq javobi — `window.__ha` (standart: true); `window.__tasdiq` — savollar
ILGAK = """() => { window.__msg = []; window.__ha = true; window.__kirit = null; window.__tasdiq = [];
  window.showMsg = (t, ty) => { window.__msg.push([String(t), ty || '']); };
  window.alert = (t) => { window.__msg.push([String(t), 'alert']); };
  window.xabarOyna = async (t) => { window.__msg.push([String(t), 'oyna']); };
  window.customConfirm = async (a, b) => { window.__tasdiq.push(String(a) + ' | ' + String(typeof b === 'string' ? b : '')); return window.__ha; };
  window.kiritishOyna = async () => window.__kirit;
  window.open = () => null; }"""
SAHIFA_502 = {"status": 502, "content_type": "text/html", "body": "<html><body><h1>502 Bad Gateway</h1></body></html>"}


def ochiq(pg, yol, ilgak=True):
    pg.goto(B + yol, wait_until="networkidle")
    pg.wait_for_timeout(400)
    if ilgak:
        pg.evaluate(ILGAK)


def msg(pg):
    try:
        return pg.evaluate("() => window.__msg || []")
    except Exception:                      # noqa: BLE001
        return []


def msg_matn(pg):
    return " || ".join(m[0] for m in msg(pg))


def sorovlar(nima, usul="POST"):
    return [x for x in SOROV if nima in x[1] and x[0] == usul]


class Bajar502:
    """So'rov serverga YETADI va bajariladi (`route.fetch`), lekin brauzerga 502 HTML qaytadi (deploy almashinuvi)."""

    def __init__(self):
        self.holat = []

    def __call__(self, route):
        try:
            j = route.fetch()
            self.holat.append(j.status)
        except Exception as e:             # noqa: BLE001
            self.holat.append(f"{type(e).__name__}")
        route.fulfill(**SAHIFA_502)


def baj(pg, ifoda, kutish=600):
    x = None
    try:
        pg.evaluate(ifoda)
    except Exception as e:                 # noqa: BLE001 — sahifa qayta yuklangan
        x = str(e)[:120]
    pg.wait_for_timeout(kutish)
    try:
        pg.wait_for_load_state("networkidle")
    except Exception:                      # noqa: BLE001
        pass
    return x


def matn(pg, sel):
    try:
        return pg.evaluate(f"() => {{ const e = document.querySelector({json.dumps(sel)}); return e ? e.textContent : null; }}")
    except Exception:                      # noqa: BLE001
        return None


def soni_matn(pg, rid):
    """«Rollar va huquqlar» kartasidagi «N ta foydalanuvchi» (asl kodda belgi yo'q — None)."""
    try:
        return pg.evaluate(f"() => {{ const e = document.querySelector('[data-rol-soni=\"{rid}\"]'); return e ? e.textContent : null; }}")
    except Exception:                      # noqa: BLE001
        return None


def son(t):
    try:
        return int(str(t).split()[0])
    except Exception:                      # noqa: BLE001
        return None


NOMALUM = "natijasi noma'lum"
TAKROR = "ikkinchi marta yozilmadi"

if br:
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("U. «Foydalanuvchilar» (U1–U4, U9, U12–U14)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, "/users")
        # U1: boshqa admin fu_ishchi ni o'chirdi; bu sahifa hali «O'chir» ko'rsatadi
        db_ishi(lambda s: setattr(s.query(User).filter(User.username == "fu_ishchi").first(), "is_active", False))
        n0 = len(sorovlar("/toggle"))
        baj(pg, f"() => toggleUser({ID['ISH']}, true, null)", 900)
        _s = sorovlar("/toggle")[n0:]
        check("U1a eski sahifa «O'chir»: so'rov maqsad holat bilan (`faol=false`)", len(_s) == 1 and "faol=false" in _s[0][1], _s)
        check("U1b foydalanuvchi QAYTA YOQILMADI (asl kod yoqardi)", not faolmi("fu_ishchi"))
        db_ishi(lambda s: setattr(s.query(User).filter(User.username == "fu_ishchi").first(), "is_active", True))
        ochiq(pg, "/users")
        pg.evaluate("() => { window.__yuklandi = false; }")
        baj(pg, f"() => toggleUser({ID['ISH']}, false, null)", 900)   # sahifa «Faollashtir» ko'rsatadi, foydalanuvchi esa faol
        check("U1c 409: sahifa yangilandi (sabab ko'rsatilgach), holat o'zgarmadi",
              faolmi("fu_ishchi") and pg.evaluate("() => window.__yuklandi === undefined"))
        # U3: internet uzildi
        ochiq(pg, "/users")
        pg.route("**/api/users/*/toggle*", lambda r: r.abort())
        baj(pg, f"() => toggleUser({ID['ISH']}, true, null)", 700)
        pg.unroute("**/api/users/*/toggle*")
        check("U3 internet uzilsa — xabar «Holat o'zgartirilmadi: internet aloqasi yo'q» (asl: hech narsa)",
              "Holat o'zgartirilmadi" in msg_matn(pg) and "internet aloqasi yo'q" in msg_matn(pg) and faolmi("fu_ishchi"), msg(pg))
        # U2: server rad etdi (403 — masalan to'xtatilgan korxona) — sabab
        pg.route("**/api/users/*/toggle*", lambda r: r.fulfill(status=403, content_type="application/json",
                                                                 body=json.dumps({"detail": "FU175 rad sababi"})))
        baj(pg, f"() => toggleUser({ID['ISH']}, true, null)", 700)
        pg.unroute("**/api/users/*/toggle*")
        check("U2 rad — server sababi (asl: «Xato»)", "FU175 rad sababi" in msg_matn(pg), msg(pg))

        # U4: yangi foydalanuvchi — 502 (server yaratdi), qayta bosish — takror, bitta foydalanuvchi
        ochiq(pg, "/users")
        pg.evaluate(f"""() => {{ showAddModal(); document.getElementById('f-username').value = 'fu_yangi';
            document.getElementById('f-password').value = '{PAROL}'; document.getElementById('f-fullname').value = 'FU Yangi';
            const s = document.getElementById('f-role'); s.value = s.options[s.options.length - 1].value; }}""")
        h = Bajar502()
        pg.route("**/api/users", h)
        n0 = len(sorovlar("/api/users"))
        baj(pg, "() => saveUser()", 900)
        pg.unroute("**/api/users", h)
        _x = matn(pg, "#user-error") or ""
        check("U4a 502 (server yaratdi) — «natijasi noma'lum … ikki marta yozilmaydi» (asl: JSON xatosi, xabar yo'q)",
              h.holat == [200] and NOMALUM in _x and "ikki marta yozilmaydi" in _x, (h.holat, _x))
        baj(pg, "() => saveUser()", 1200)
        _s = [x for x in SOROV if x[0] == "POST" and x[1] == "/api/users"][-2:]
        _j = [x for x in JAVOB if x[0] == "POST" and x[1] == "/api/users"][-1:]
        check("U4b qayta bosish — o'sha kalit bilan, server birinchi javobni qaytardi (`X-Takror: 1`), «username band» EMAS",
              len(_s) == 2 and _s[0][3] and _s[0][3] == _s[1][3] and _j and _j[0][2] == 200 and _j[0][3] == "1", (_s, _j))
        check("U4c bazada BITTA fu_yangi", foyd_soni("fu_yangi") == 1, foyd_soni("fu_yangi"))

        # U13: yopilgan oynada parol qolmaydi
        ochiq(pg, "/users")
        pg.evaluate("() => { showAddModal(); document.getElementById('f-password').value = 'Maxfiy123'; closeModal(); }")
        check("U13 oyna yopilganda parol maydoni tozalandi", pg.evaluate("() => document.getElementById('f-password').value") == "")

        # U9: QR — korxona kodi yuklanmasa kodsiz havola ko'rsatilmaydi
        pg.route("**/api/settings/company", lambda r: r.fulfill(**SAHIFA_502))
        baj(pg, "() => showHodimQR()", 700)
        pg.unroute("**/api/settings/company")
        _u = matn(pg, "#hodimQrUrl") or ""
        check("U9 kod yuklanmadi — havola YO'Q, sabab va «nusxalamang» (asl: «/hodim» kodsiz havola)",
              "/hodim" not in _u and "yuklanmadi" in _u and "nusxalamang" in _u and (matn(pg, "#hodimQrKod") or "") == "—", _u)
        baj(pg, "() => showHodimQR()", 700)
        _u = matn(pg, "#hodimQrUrl") or ""
        check("U9b kod yuklandi — havola `?k=` bilan", "/hodim?k=" in _u, _u)

        # U14: rol soni (rol o'zgargach)
        ochiq(pg, "/users")
        _old, _new = soni_matn(pg, ID["MEN"]), soni_matn(pg, ID["ROL_T"])
        baj(pg, f"""() => {{ const sel = [...document.querySelectorAll('select.u-rol-tanlov')].find(x => x.getAttribute('onchange').includes('({ID['ISH2']},'));
            sel.value = '{ID['ROL_T']}'; return userRoli({ID['ISH2']}, sel); }}""", 900)
        _old2, _new2 = soni_matn(pg, ID["MEN"]), soni_matn(pg, ID["ROL_T"])
        check("U14 rol o'zgardi — «Rollar va huquqlar» soni darhol: eskisi −1, yangisi +1 (asl: o'zgarmasdi)",
              son(_old) is not None and son(_old) - 1 == son(_old2) and son(_new) + 1 == son(_new2)
              and foydalanuvchi("fu_ishchi2").rol_id == ID["ROL_T"], (_old, _old2, _new, _new2))
        # U6 / U7: tarmoq uzilsa — natija noma'lum, tanlov eski qiymatga
        pg.route("**/api/users/*/rol", lambda r: r.abort())
        baj(pg, f"""() => {{ const sel = [...document.querySelectorAll('select.u-rol-tanlov')].find(x => x.getAttribute('onchange').includes('({ID['ISH2']},'));
            sel.value = '{ID['MEN']}'; return userRoli({ID['ISH2']}, sel); }}""", 800)
        pg.unroute("**/api/users/*/rol")
        _v = pg.evaluate(f"""() => {{ const sel = [...document.querySelectorAll('select.u-rol-tanlov')].find(x => x.getAttribute('onchange').includes('({ID['ISH2']},'));
            return [sel.value, sel.disabled]; }}""")
        check("U7 rolni o'zgartirishda internet uzildi — «natijasi noma'lum», tanlov eski rolga qaytdi va ochiq",
              NOMALUM in msg_matn(pg) and _v == [str(ID["ROL_T"]), False], (msg(pg), _v))

        # U12: «Hammasini o'chirish» — 502 (so'rov serverga YUBORILMAYDI — faqat brauzer javobi)
        ochiq(pg, "/users")
        pg.evaluate("() => { window.__kirit = 'HAMMASINI-OCHIR'; }")
        pg.route("**/api/system/factory-reset*", lambda r: r.fulfill(**SAHIFA_502))
        baj(pg, "() => startFactoryReset()", 800)
        pg.unroute("**/api/system/factory-reset*")
        _m = msg_matn(pg)
        check("U12 502 — «Natija noma'lum … o'chgan bo'lishi mumkin», inglizcha «Unexpected token» yo'q (asl: «bog'lanib bo'lmadi: Unexpected…»)",
              "Natija noma'lum" in _m and "Unexpected" not in _m and "bog'lanib bo'lmadi" not in _m, _m)
    except Exception as _x:               # noqa: BLE001 — asl kodda yo'q funksiya / belgi: bo'lim yiqiladi, sinov QULAMAYDI
        check("Foydalanuvchilar bo'limi oxirigacha bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("R. «Rollar va ruxsatlar» (R1–R7)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        # R1: birinchi yuklash 502
        pg.route("**/api/rollar", lambda r: r.fulfill(**SAHIFA_502) if r.request.method == "GET" else r.continue_())
        ochiq(pg, "/rollar", ilgak=False)
        pg.unroute("**/api/rollar")
        _r, _j = matn(pg, "#rlRoyxat") or "", matn(pg, "#rlJadval") or ""
        check("R1 birinchi yuklash 502 — ro'yxat va jadvalda «Rollar yuklanmadi — …» (asl: abadiy «Yuklanmoqda…»)",
              "Rollar yuklanmadi" in _r and "Rollar yuklanmadi" in _j and "Yuklanmoqda" not in _r + _j, (_r, _j))

        ochiq(pg, "/rollar")
        pg.wait_for_function("() => typeof RL !== 'undefined' && RL && RL.rollar && RL.rollar.length > 0")
        _adm = pg.evaluate("() => RL.rollar.find(r => r.admin).id")
        # R2: Admin nusxasi — bitta POST, ruxsatlar shu POST da
        pg.evaluate(f"() => {{ window.__kirit = 'FU175 Admin nusxa'; return rolniTanla({_adm}, true); }}")
        nP, nU = len(sorovlar("/api/rollar", "POST")), len(sorovlar("/api/rollar/", "PUT"))
        baj(pg, "() => rolNusxa()", 1200)
        _p = sorovlar("/api/rollar", "POST")[nP:]
        _u = sorovlar("/api/rollar/", "PUT")[nU:]
        _rx = rol_ruxsat("FU175 Admin nusxa") or {}
        _hamma = {b: set(v["amallar"]) for b, v in RX.BANDLAR.items()}
        check("R2a Admin nusxasi: BITTA POST (ruxsatlar shu tanada), alohida PUT yo'q",
              len(_p) == 1 and len(_u) == 0 and '"ruxsatlar"' in (_p[0][2] or "") and '"dashboard"' in (_p[0][2] or ""), (_p, _u))
        check("R2b yangi rolda HAMMA ruxsatlar (Admin kabi), rol bitta",
              {b: set(a) for b, a in _rx.items()} == _hamma and rol_soni("FU175 Admin nusxa") == 1, _rx)
        # R2c: nusxa POST 502 (server yaratdi) — ro'yxatdan tekshirib «yaratilgan ekan»
        h = Bajar502()
        pg.route("**/api/rollar", lambda r: h(r) if r.request.method == "POST" else r.continue_())
        pg.evaluate(f"() => {{ window.__msg = []; window.__kirit = 'FU175 Nusxa 502'; return rolniTanla({ID['ROL_T']}, true); }}")
        baj(pg, "() => rolNusxa()", 1500)
        pg.unroute("**/api/rollar")
        _sel = pg.evaluate("() => (rlRol(rlTanlangan) || {}).nom")
        check("R2c nusxa 502 (server yaratdi) — ro'yxatdan topildi: «✓ Nusxa yaratildi» + «ikkinchi marta yozilmadi», yangi rol tanlandi",
              h.holat == [200] and "Nusxa yaratildi" in msg_matn(pg) and TAKROR in msg_matn(pg) and _sel == "FU175 Nusxa 502"
              and rol_soni("FU175 Nusxa 502") == 1, (h.holat, msg(pg), _sel))
        # R2d: POST 502 va server YARATMAGAN (so'rov yetib bormadi) — «qayta bosing»
        pg.route("**/api/rollar", lambda r: r.fulfill(**SAHIFA_502) if r.request.method == "POST" else r.continue_())
        pg.evaluate(f"() => {{ window.__msg = []; window.__kirit = 'FU175 Yetmagan'; return rolniTanla({ID['ROL_T']}, true); }}")
        baj(pg, "() => rolNusxa()", 1500)
        pg.unroute("**/api/rollar")
        check("R2d 502 va rol yaratilmagan — «natijasi noma'lum … bu nomli rol yo'q — qayta bosing»",
              NOMALUM in msg_matn(pg) and "qayta bosing" in msg_matn(pg) and rol_soni("FU175 Yetmagan") == 0, msg(pg))

        # R3: saqlanmagan o'zgarish + «Yangi rol» / «Nusxa» — avval so'raladi
        pg.evaluate(f"() => rolniTanla({ID['ROL_T']}, true)")
        pg.click('.rl-cb[data-band="buyurtma"][data-amal="yaratish"]')
        pg.wait_for_timeout(200)
        pg.evaluate("() => { window.__tasdiq = []; window.__ha = false; }")
        baj(pg, "() => yangiRol()", 400)
        _t = pg.evaluate("() => window.__tasdiq")
        _ochiq = pg.evaluate("() => document.getElementById('rlYangiModal').style.display")
        check("R3a saqlanmagan o'zgarish bor — «Yangi rol» avval so'radi; «Qolish» — oyna ochilmadi, o'zgarish turibdi (asl: so'ramasdi)",
              any("Saqlanmagan o'zgarish" in x for x in _t) and _ochiq != "flex" and pg.evaluate("() => rlIflos") is True, (_t, _ochiq))
        nP = len(sorovlar("/api/rollar", "POST"))
        pg.evaluate("() => { window.__tasdiq = []; window.__ha = false; window.__kirit = 'FU175 R3'; }")
        baj(pg, "() => rolNusxa()", 600)
        check("R3b «Nusxa» ham so'radi; «Qolish» — POST yo'q, o'zgarish turibdi",
              any("Saqlanmagan o'zgarish" in x for x in pg.evaluate("() => window.__tasdiq"))
              and len(sorovlar("/api/rollar", "POST")) == nP and pg.evaluate("() => rlIflos") is True)
        pg.evaluate("() => { window.__ha = true; }")

        # R6: saqlash davomida belgilar qulf
        ushla = []
        pg.route(f"**/api/rollar/{ID['ROL_T']}", lambda r: ushla.append(r) if r.request.method == "PUT" else r.continue_())
        pg.evaluate("() => { window.__saqla = rolniSaqla(); }")
        pg.wait_for_timeout(500)
        _band = pg.evaluate("() => [document.querySelector('.rl-cb').disabled, document.getElementById('rlNom').disabled, (typeof rlAmalda === 'undefined' ? null : rlAmalda)]")
        pg.evaluate("() => rolniTanla(RL.rollar[0].id)")      # amal paytida boshqa rolga o'tish e'tiborsiz
        _tan = pg.evaluate("() => rlTanlangan")
        for r in ushla:
            r.continue_()
        pg.wait_for_timeout(1200)
        pg.unroute(f"**/api/rollar/{ID['ROL_T']}")
        _keyin = pg.evaluate("() => [document.querySelector('.rl-cb').disabled, rlAmalda, rlIflos]")
        check("R6a saqlash davomida belgilar va nom qulf (asl: ochiq — o'sha paytdagi belgi jim yo'qolardi)", _band == [True, True, True], _band)
        check("R6b saqlash davomida boshqa rolga o'tib bo'lmadi", _tan == ID["ROL_T"], _tan)
        check("R6c saqlandi — belgilar yana ochiq, o'zgarish yo'q; bazada «Buyurtmalar: Yaratish»",
              _keyin == [False, False, False] and "yaratish" in (rol_ruxsat("FU175 Tahrir") or {}).get("buyurtma", []), (_keyin, rol_ruxsat("FU175 Tahrir")))
        # R6d: saqlash 502 — natija noma'lum
        pg.click('.rl-cb[data-band="buyurtma"][data-amal="tahrirlash"]')
        pg.route(f"**/api/rollar/{ID['ROL_T']}", lambda r: r.fulfill(**SAHIFA_502) if r.request.method == "PUT" else r.continue_())
        pg.evaluate("() => { window.__msg = []; }")
        baj(pg, "() => rolniSaqla()", 700)
        pg.unroute(f"**/api/rollar/{ID['ROL_T']}")
        check("R6d saqlash 502 — «Rolni saqlash natijasi noma'lum» (asl: «Saqlanmadi»), o'zgarish turibdi",
              NOMALUM in msg_matn(pg) and pg.evaluate("() => rlIflos") is True, msg(pg))
        pg.evaluate("() => ozgarishniBekor()")

        # R4: foydalanuvchi rolini o'zgartirish — internet uzildi
        pg.evaluate(f"() => rolniTanla({ID['MEN']}, true)")
        pg.wait_for_timeout(300)
        pg.route("**/api/users/*/rol", lambda r: r.abort())
        pg.evaluate("() => { window.__msg = []; }")
        baj(pg, f"""() => {{ const sel = document.querySelector('#rlUserlar select[aria-label="fu_ishchi roli"]');
            sel.value = '{ID['ROL_T']}'; return userRoliniOzgartir({ID['ISH']}, sel); }}""", 1200)
        pg.unroute("**/api/users/*/rol")
        _v = pg.evaluate("() => { const s = document.querySelector('#rlUserlar select[aria-label=\"fu_ishchi roli\"]'); return s ? [s.value, s.disabled] : null; }")
        check("R4 internet uzildi — «natijasi noma'lum», tanlov haqiqiy (eski) rolni ko'rsatadi va ochiq (asl: ushlanmagan xato, yangi rol ko'rinib qolardi)",
              NOMALUM in msg_matn(pg) and _v == [str(ID["MEN"]), False] and foydalanuvchi("fu_ishchi").rol_id == ID["MEN"], (msg(pg), _v))

        # R5: o'chirish ikki marta — bitta DELETE; 404 — «allaqachon o'chirilgan»
        pg.evaluate(f"() => rolniTanla({ID['ROL_OCH']}, true)")
        nD = len(sorovlar(f"/api/rollar/{ID['ROL_OCH']}", "DELETE"))
        pg.evaluate("() => { window.__msg = []; rolOchir(); rolOchir(); }")
        pg.wait_for_timeout(1500)
        _d = sorovlar(f"/api/rollar/{ID['ROL_OCH']}", "DELETE")[nD:]
        check("R5a ikki marta bosish — BITTA DELETE, «✓ Rol o'chirildi», «Rol topilmadi» yo'q",
              len(_d) == 1 and "Rol o'chirildi" in msg_matn(pg) and "topilmadi" not in msg_matn(pg) and rol_soni("FU175 Ochiriladigan") == 0,
              (_d, msg(pg)))
        _r404 = js(C.post("/api/rollar", json={"nom": "FU175 Boshqa admin", "ruxsatlar": {}})).get("id")
        baj(pg, "() => rollarniYukla()", 500)
        pg.evaluate(f"() => rolniTanla({_r404}, true)")
        C.delete(f"/api/rollar/{_r404}")                       # boshqa admin o'chirdi
        pg.evaluate("() => { window.__msg = []; }")
        baj(pg, "() => rolOchir()", 1000)
        check("R5b rol allaqachon o'chirilgan (404) — «allaqachon o'chirilgan ekan — ro'yxat yangilandi», ro'yxatda yo'q",
              "allaqachon o'chirilgan" in msg_matn(pg) and pg.evaluate(f"() => !rlRol({_r404})"), msg(pg))

        # R7: eski javob yangisini bosmaydi
        ushla = []

        def _r7(r):
            if r.request.method == "GET" and not ushla:
                ushla.append(r)
            else:
                r.continue_()
        pg.route("**/api/rollar", _r7)
        pg.evaluate("() => { window.__y1 = rollarniYukla(); }")
        pg.wait_for_timeout(300)
        pg.evaluate("() => { window.__y2 = rollarniYukla(); }")
        pg.wait_for_timeout(800)
        if ushla:
            _javob = ushla[0].fetch()
            _d = _javob.json()
            for _x in _d.get("rollar", []):
                _x["nom"] = "ESKI JAVOB " + _x["nom"]
            ushla[0].fulfill(response=_javob, body=json.dumps(_d))
        pg.wait_for_timeout(800)
        pg.unroute("**/api/rollar", _r7)
        check("R7 birinchi (eski) javob kech keldi — ro'yxat yangi javobniki (asl: eski javob ustiga yozardi)",
              bool(ushla) and pg.evaluate("() => !RL.rollar.some(r => r.nom.startsWith('ESKI JAVOB'))")
              and "ESKI JAVOB" not in (matn(pg, "#rlRoyxat") or ""), matn(pg, "#rlRoyxat"))

        # X1: ikki tasdiqlash oynasi (asl dasturning oynasi — ilgaksiz)
        ochiq(pg, "/rollar", ilgak=False)
        pg.evaluate("() => { window.__p1 = customConfirm('Birinchi'); window.__p2 = customConfirm('Ikkinchi'); }")
        pg.wait_for_timeout(200)
        _p1 = pg.evaluate("() => Promise.race([window.__p1, new Promise(ok => setTimeout(() => ok('kutmoqda'), 400))])")
        pg.click("#ccModalOk")
        _p2 = pg.evaluate("() => window.__p2")
        check("X1 ikkinchi oyna ochilganda birinchisi «Bekor» (false) bilan tugadi, ikkinchisi «Tasdiqlash» — true (asl: birinchisi abadiy kutardi)",
              _p1 is False and _p2 is True, (_p1, _p2))
    except Exception as _x:               # noqa: BLE001 — asl kodda yo'q funksiya / belgi: bo'lim yiqiladi, sinov QULAMAYDI
        check("Rollar bo'limi oxirigacha bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("S. «Sozlamalar» (C1–C5, C9, C10, C12)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        # C1: mahsulot turlari yuklanmadi — Saqlash yopiq, so'rov ketmaydi, hech narsa o'chmaydi
        _oldin = kategoriyalar()
        pg.route("**/api/settings/categories", lambda r: r.fulfill(**SAHIFA_502) if r.request.method == "GET" else r.continue_())
        ochiq(pg, "/sozlamalar")
        nC = len(sorovlar("/api/settings/categories", "PUT"))
        baj(pg, "() => saveCategories()", 500)
        pg.unroute("**/api/settings/categories")
        check("C1a ro'yxat yuklanmadi — sabab ko'rinadi, «Saqlash» yopiq",
              "Mahsulot turlari yuklanmadi" in (matn(pg, "#cat-list") or "") and pg.evaluate("() => document.getElementById('cat-save-btn').disabled"),
              matn(pg, "#cat-list"))
        check("C1b saveCategories() — so'rov KETMADI, turlar o'zgarmadi (asl: `codes=''` — Loy sotish va Blok O'CHARDI)",
              len(sorovlar("/api/settings/categories", "PUT")) == nC and kategoriyalar() == _oldin, (kategoriyalar(), _oldin))
        ochiq(pg, "/sozlamalar")
        pg.evaluate("() => document.querySelectorAll('.cat-cb').forEach(c => { c.checked = false; })")
        baj(pg, "() => saveCategories()", 600)
        _put = sorovlar("/api/settings/categories", "PUT")[-1:]
        # kech155 (zip 211 — egasi QARORI «kamida bittasi yoqiq»): hammasi olib tashlansa — so'rov KETMAYDI, «Kamida bitta …», o'zgarmadi
        check("C1c yuklangan ro'yxatda hammasi olib tashlansa — saqlanmaydi (kamida bitta tur yoqiq, zip 211), turlar o'zgarmadi",
              len(sorovlar("/api/settings/categories", "PUT")) == nC and "Kamida bitta" in (matn(pg, "#cat-status") or "")
              and kategoriyalar() == _oldin, (_put, matn(pg, "#cat-status"), kategoriyalar()))
        C.put("/api/settings/categories", data={"codes": _cats})

        # C2: korxona ma'lumoti yuklanmadi — Saqlash yopiq
        C.put("/api/settings/company", data={"name": "FU Korxona", "slogan": "FU shior", "phone": "+998901112233", "address": "Andijon",
                                             "tg_tagline": "FU tg"})
        pg.route("**/api/settings/company", lambda r: r.fulfill(**SAHIFA_502) if r.request.method == "GET" else r.continue_())
        ochiq(pg, "/sozlamalar")
        pg.unroute("**/api/settings/company")
        nK = len(sorovlar("/api/settings/company", "PUT"))
        pg.evaluate("() => { document.getElementById('co-name').value = 'Yangi nom'; }")
        baj(pg, "() => saveCompany()", 500)
        _co = js(C.get("/api/settings/company"))
        check("C2 korxona ma'lumoti yuklanmadi — sabab, «Saqlash» yopiq, so'rov ketmadi: slogan / telefon / manzil SAQLANIB qoldi",
              "Korxona ma'lumoti yuklanmadi" in (matn(pg, "#co-status") or "") and len(sorovlar("/api/settings/company", "PUT")) == nK
              and _co.get("slogan") == "FU shior" and _co.get("phone") == "+998901112233", (matn(pg, "#co-status"), _co))

        # C9 / C10: logotip yuklangach yozilgan (saqlanmagan) nom qoladi, fayl nomi yozuvi tozalanadi (sinov fayli oxirida o'chiriladi)
        _logo_oldin = set(glob.glob(os.path.join(ROOT, "static", "uploads", "logos", "company_1.*")))
        ochiq(pg, "/sozlamalar")
        pg.evaluate("() => { document.getElementById('co-name').value = 'Saqlanmagan nom'; }")
        _png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
        pg.set_input_files("#co-logo-file", files=[{"name": "logo.png", "mimeType": "image/png", "buffer": _png}])
        baj(pg, "() => uploadLogo()", 1200)
        check("C9 / C10 logotip yuklandi — yozilgan nom QOLDI (asl: qayta yuklanib yo'qolardi), fayl nomi «Fayl tanlanmagan»",
              "Yuklandi" in (matn(pg, "#co-logo-status") or "") and pg.evaluate("() => document.getElementById('co-name').value") == "Saqlanmagan nom"
              and (matn(pg, "#co-logo-nomi") or "") == "Fayl tanlanmagan", (matn(pg, "#co-logo-status"), matn(pg, "#co-logo-nomi")))
        for _f in set(glob.glob(os.path.join(ROOT, "static", "uploads", "logos", "company_1.*"))) - _logo_oldin:
            try:
                os.remove(_f)
            except OSError:
                pass

        # C5: bot tokeni saqlanmadi — token maydoni tozalanmaydi, sabab
        ochiq(pg, "/sozlamalar")
        pg.route("**/api/settings/telegram-bot", lambda r: r.fulfill(status=400, content_type="application/json",
                                                                     body=json.dumps({"detail": "FU175 token noto'g'ri"}))
                 if r.request.method == "PUT" else r.continue_())
        pg.evaluate("() => { document.getElementById('tg-token').value = '123:ABC'; }")
        baj(pg, "() => saveTgBot()", 600)
        check("C5 rad — sabab ko'rinadi, kiritilgan token O'CHMADI (asl: «Saqlashda xato» va token tozalanardi)",
              "FU175 token noto'g'ri" in (matn(pg, "#tg-status") or "") and pg.evaluate("() => document.getElementById('tg-token').value") == "123:ABC",
              matn(pg, "#tg-status"))
        # C4: tozalash rad etildi — chat maydoni qoladi
        pg.route("**/api/settings/telegram-bot", lambda r: r.fulfill(status=403, content_type="application/json",
                                                                     body=json.dumps({"detail": "FU175 ruxsat yo'q"}))
                 if r.request.method == "PUT" else r.continue_())
        pg.evaluate("() => { document.getElementById('tg-chat').value = '555'; }")
        baj(pg, "() => clearTgBot()", 600)
        pg.unroute("**/api/settings/telegram-bot")
        check("C4 tozalash rad etildi — «Tozalanmadi: …», chat maydoni QOLDI (asl: jim tozalab «Sozlanmagan»)",
              "Tozalanmadi" in (matn(pg, "#tg-status") or "") and pg.evaluate("() => document.getElementById('tg-chat').value") == "555",
              matn(pg, "#tg-status"))

        # C12: yo'nalishni o'chirish — tez to'rt bosish (uchinchisi qo'riqchisiz «Yana bosing» ga qaytarar, to'rtinchisi ikkinchi
        # DELETE yuborardi), bitta DELETE
        ochiq(pg, "/sozlamalar")
        pg.wait_for_function(f"() => !!document.querySelector('.yon-ochir[data-id=\"{ID['YON']}\"]')")
        nD = len(sorovlar(f"/api/yonalishlar/{ID['YON']}", "DELETE"))
        _yt = pg.evaluate(f"""() => {{ const b = document.querySelector('.yon-ochir[data-id="{ID['YON']}"]');
            yonOchir(b); yonOchir(b); yonOchir(b); yonOchir(b); return b.textContent; }}""")
        pg.wait_for_timeout(1200)
        _d = sorovlar(f"/api/yonalishlar/{ID['YON']}", "DELETE")[nD:]
        check("C12 tez to'rt bosish — BITTA DELETE (to'rtinchisi ikkinchisini yubormadi), «✓ O'chirildi» («topilmadi» yo'q)",
              len(_d) == 1 and "topilmadi" not in (matn(pg, "#yon-status") or ""), (_d, _yt, matn(pg, "#yon-status")))
    except Exception as _x:               # noqa: BLE001 — asl kodda yo'q funksiya / belgi: bo'lim yiqiladi, sinov QULAMAYDI
        check("Sozlamalar bo'limi oxirigacha bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    ctx, pg = kontekst("fu_soz")
    try:
        ochiq(pg, "/sozlamalar")
        _t = matn(pg, "#tg-status") or ""
        check("C3 «Ko'rish» siz rol: bot holati 403 — «Bot holati yuklanmadi — ko'rish ruxsati yo'q», yolg'on «Sozlanmagan» YO'Q",
              "Bot holati yuklanmadi" in _t and "Sozlanmagan" not in _t, _t)
        check("C3b … «Mahsulot turlari» ham sabab bilan, «Saqlash» yopiq",
              "Mahsulot turlari yuklanmadi" in (matn(pg, "#cat-list") or "") and pg.evaluate("() => document.getElementById('cat-save-btn').disabled"))
    except Exception as _x:               # noqa: BLE001 — asl kodda yo'q funksiya / belgi: bo'lim yiqiladi, sinov QULAMAYDI
        check("Sozlamalar (Ko'rishsiz rol) bo'limi oxirigacha bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    section("T. «O'chirilganlar» (T5)")
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════
    ctx, pg = kontekst()
    try:
        ochiq(pg, "/trash")
        nD = len(sorovlar(f"/api/projects/{ID['PRJ_DEL']}/permanent", "DELETE"))
        pg.evaluate(f"""() => {{ const b = [...document.querySelectorAll('button')].find(x => (x.getAttribute('onclick') || '').includes("permanentDelete('project', {ID['PRJ_DEL']},"));
            permanentDelete('project', {ID['PRJ_DEL']}, b.dataset.label, b); permanentDelete('project', {ID['PRJ_DEL']}, b.dataset.label, b); }}""")
        pg.wait_for_timeout(1500)
        _d = sorovlar(f"/api/projects/{ID['PRJ_DEL']}/permanent", "DELETE")[nD:]
        check("T5 «Butunlay o'chirish» ikki marta — BITTA DELETE, «topilmadi» xabari yo'q",
              len(_d) == 1 and "topilmadi" not in msg_matn(pg) and db_ishi(lambda s: s.get(Project, ID["PRJ_DEL"])) is None, (_d, msg(pg)))
    except Exception as _x:               # noqa: BLE001 — asl kodda yo'q funksiya / belgi: bo'lim yiqiladi, sinov QULAMAYDI
        check("O'chirilganlar bo'limi oxirigacha bajarildi", False, f"{type(_x).__name__}: {str(_x)[:300]}")
    finally:
        ctx.close()

    section("Z. Sahifa xatolari")
    check("Z1 sahifalarda ushlanmagan JS xatosi yo'q", not JS_XATO, JS_XATO[:5])

try:
    if br:
        br.close()
    if pw_ctx:
        pw_ctx.stop()
except Exception:                          # noqa: BLE001
    pass
server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
