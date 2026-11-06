#!/usr/bin/env python3
"""
test_tana263.py — kech199 (zip 263, xavfsizlik REJA 10-band — Fable F2): so'rov TANASI hajmi chegarasi (`main._TanaChegarasi`).

NIMA UCHUN KERAK
----------------
  O'LCHANGAN (`work/k263/probe263_tana.py`, haqiqiy uvicorn, zip 263 1-qism kodi 894aa9b): FastAPI tanani kirish tekshiruvidan OLDIN
  o'qiydi — KIRISHSIZ 300 MB JSON → server xotirasi +1 144 MB (keyin 401); KIRISHSIZ 300 MB fayl /tiklash ga → 279 MB vaqtinchalik
  disk; kirgan foydalanuvchining 120 MB «rasmi» — `_save_upload` uni to'liq xotiraga o'qirdi (+121 MB). Bitta konteyner — hamma
  korxonalar. Tuzatilgan kodda: hammasi 413, xotira o'sishi 0.

BO'LIMLAR
  A — chegaralar va matnlar (`tana_chegarasi`, `tana_katta_xabari`), qatlam ENG TASHQI;
  B — haqiqiy ilova (TestClient): kirishsiz katta JSON — 413 (401 emas), chegaradan kichik — 401; kirgan admin 27 MB rasm — 413,
      murojaat YARATILMAYDI, fayl SAQLANMAYDI; 25,5 MB — ikkinchi qavat 400; /tiklash — korxona admini 30 MB → 413, platforma
      egasi 30 MB → 413 EMAS; logotip 2,5 MB → 400 «2 MB»;
  C — qatlamning o'zi (soxta ichki ilova, tana bo'laklab — xotirasiz): Content-Length katta — ichki ilova CHAQIRILMAYDI; chunked —
      chegarada to'xtaydi, ichki ilova javobi YUBORILMAYDI; qolgan tana o'qib tashlanadi (128 MB gacha), undan katta — `connection:
      close`; ilova xatoni ushlab 200 qaytarsa ham — 413; javob boshlangandan keyin oshsa — ulanish uziladi; yolg'on Content-Length;
      tana o'zgarmasdan o'tadi; uzilish; GET; websocket / lifespan; cookie turlari; tiklash yo'li — platforma egasi (faol / nofaol /
      muddati o'tgan sessiya / oddiy admin) chegarasi;
  D — ikkinchi qavat: `_save_upload`, `api_restore_backup`, `tiklash_bajarish` faylni chegara + 1 baytdan ko'p o'qimaydi.
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
Asl kodga (zip 263 1-qism, 894aa9b) qarshi YIQILADI (QULAMAYDI).
ISHLATISH: python3 tools/test_tana263.py
"""
import os
import sys
import tempfile

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "tana263_test"
_DB = os.path.join(tempfile.gettempdir(), "tana263_test.db")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    if os.path.exists(_DB):
        os.remove(_DB)
    os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("BACKUP_TELEGRAM_CHAT_ID", None)

import asyncio                                     # noqa: E402
import io                                          # noqa: E402
import contextlib                                  # noqa: E402
from datetime import datetime, timedelta           # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, UserSession     # noqa: E402
from production_models import Company             # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []
MB = 1024 * 1024


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {REJIM}{label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {REJIM}{label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


YANGI = hasattr(main, "_TanaChegarasi")
_IP = {"n": 10}


def mijoz():
    _IP["n"] += 1
    try:
        return TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False,
                          client=(f"198.51.100.{_IP['n']}", 50000))
    except TypeError:
        return TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)


s = SessionLocal()
if not s.query(Company).filter(Company.id == 2).first():
    s.add(Company(id=2, name="Ikkinchi Korxona", code="IKKINCHI-263"))
    s.commit()
with contextlib.redirect_stdout(_quiet):
    pa = auth.create_user(s, "t263_egasi", "Parol263!xyz", UserRole.ADMIN, "Platforma egasi", company_id=1)
    ka = auth.create_user(s, "t263_b", "Parol263!xyz", UserRole.ADMIN, "B admin", company_id=2)
    nf = auth.create_user(s, "t263_nofaol", "Parol263!xyz", UserRole.ADMIN, "Nofaol egasi", company_id=1)
s.commit()
for u, bayroq in ((pa, True), (ka, False), (nf, True)):
    s.query(User).filter(User.id == u.id).update({"is_platform_admin": bayroq})
s.commit()
PA_ID, KA_ID, NF_ID = pa.id, ka.id, nf.id
TOK_PA = auth.create_session(s, PA_ID)
TOK_KA = auth.create_session(s, KA_ID)
TOK_NF = auth.create_session(s, NF_ID)
TOK_ESKI = auth.create_session(s, PA_ID)
s.query(User).filter(User.id == NF_ID).update({"is_active": False})
s.query(UserSession).filter(UserSession.token == auth.token_xesh(TOK_ESKI)).update(
    {"expires_at": datetime.utcnow() - timedelta(hours=1)})
s.commit()
s.close()


def kirgan(token):
    c = mijoz()
    c.cookies.set("session_token", token)
    return c


def multipart(n_bayt, maydonlar=None, nom="r.jpg", tur="image/jpeg", bayt=b"a"):
    chegara = "----t263chegara"
    bosh = b""
    for k, v in (maydonlar or {}).items():
        bosh += (f"--{chegara}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
    bosh += (f"--{chegara}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{nom}\"\r\n"
             f"Content-Type: {tur}\r\n\r\n").encode()
    oxir = f"\r\n--{chegara}--\r\n".encode()
    return bosh + bayt * n_bayt + oxir, {"content-type": f"multipart/form-data; boundary={chegara}"}


# ═════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A — chegaralar, matnlar, qatlam o'rni")
check("A1 tana_chegarasi: JSON — 8 MB", lambda: main.tana_chegarasi("/api/x", "application/json") == 8 * MB)
check("A2 tana_chegarasi: forma (urlencoded) — 8 MB",
      lambda: main.tana_chegarasi("/login", "application/x-www-form-urlencoded") == 8 * MB)
check("A3 tana_chegarasi: multipart — MAX_UPLOAD_SIZE + 1 MB (26 MB)",
      lambda: main.tana_chegarasi("/api/orders/1/attachments", "multipart/form-data; boundary=x") == main.MAX_UPLOAD_SIZE + MB == 26 * MB)
check("A4 tana_chegarasi: tiklash, platforma egasi EMAS — fayl chegarasi",
      lambda: main.tana_chegarasi("/tiklash", "multipart/form-data; boundary=x") == 26 * MB)
check("A5 tana_chegarasi: tiklash, platforma egasi — 200 + 1 MB (ikkala yo'l)",
      lambda: all(main.tana_chegarasi(y, "multipart/form-data; b=x", platforma_egasi=True) == main.TIKLASH_MAX_BAYT + MB == 201 * MB
                  for y in ("/tiklash", "/api/system/restore")))
check("A6 tana_chegarasi: platforma egasi — boshqa yo'lda katta chegara YO'Q",
      lambda: main.tana_chegarasi("/api/murojaatlar", "multipart/form-data", platforma_egasi=True) == 26 * MB)
check("A7 tana_chegarasi: tiklash yo'liga JSON — 8 MB (platforma egasi ham)",
      lambda: main.tana_chegarasi("/api/system/restore", "application/json", platforma_egasi=True) == 8 * MB)
check("A8 tana_chegarasi: Content-Type yo'q / katta harf",
      lambda: main.tana_chegarasi("/x", "") == 8 * MB and main.tana_chegarasi("/x", "MULTIPART/FORM-DATA; b=1") == 26 * MB)
check("A9 xabar matnlari (8 / 25 / 200 MB)",
      lambda: "8 MB" in main.tana_katta_xabari(8 * MB) and "25 MB" in main.tana_katta_xabari(26 * MB)
      and "200 MB" in main.tana_katta_xabari(201 * MB) and "juda katta" in main.tana_katta_xabari(8 * MB))
check("A10 qatlam — ENG TASHQI (birinchi o'rinda)",
      lambda: main.app.user_middleware[0].cls is main._TanaChegarasi, [m.cls for m in main.app.user_middleware])
check("A11 TANA_TOKISH_MAX = 128 MB", lambda: main.TANA_TOKISH_MAX == 128 * MB)

# ═════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B — haqiqiy ilova")
c = mijoz()
tana = b'{"ozgarishlar":[],"x":"' + b"a" * (8 * MB) + b'"}'
r = c.post("/api/sayt-katalogi/excel/saqla", content=tana, headers={"content-type": "application/json"})
check("B1 kirishsiz JSON 8 MB+ → 413 (401 emas), JSON sabab «8 MB»",
      lambda: r.status_code == 413 and "8 MB" in js(r).get("detail", ""), (r.status_code, r.text[:200]))
check("B1b 413 javob sarlavhalari (nosniff, DENY, no-store)",
      lambda: r.headers.get("x-content-type-options") == "nosniff" and r.headers.get("x-frame-options") == "DENY"
      and r.headers.get("cache-control") == "no-store")
tana = b'{"ozgarishlar":[],"x":"' + b"a" * (8 * MB - 100) + b'"}'
r = c.post("/api/sayt-katalogi/excel/saqla", content=tana, headers={"content-type": "application/json"})
check("B2 kirishsiz JSON chegaradan kichik → 401 (oddiy yo'l)", lambda: r.status_code == 401, (r.status_code, r.text[:200]))
r = c.post("/login", content=b"username=x&password=" + b"a" * (9 * MB),
           headers={"content-type": "application/x-www-form-urlencoded"})
check("B3 kirishsiz /login 9 MB forma → 413 (HTML)", lambda: r.status_code == 413 and "juda katta" in r.text
      and r.headers.get("content-type", "").startswith("text/html"), (r.status_code, r.text[:200]))
r = mijoz().post("/login", data={"username": "t263_egasi", "password": "noto'g'ri"})
check("B4 oddiy /login (kichik) — 413 EMAS", lambda: r.status_code == 200 and "Login yoki parol" in r.text, r.status_code)

s = SessionLocal()
from models import Murojaat as _Mj               # noqa: E402
mj_oldin = s.query(_Mj).count()
s.close()
papka = os.path.join(main.static_dir, "uploads", "murojaat")
fayllar_oldin = set(os.listdir(papka)) if os.path.isdir(papka) else set()
cb = kirgan(TOK_KA)
tana, h = multipart(27 * MB, {"turi": "savol", "matn": "t263 katta rasm"})
r = cb.post("/api/murojaatlar", content=tana, headers=h)
check("B5 kirgan admin 27 MB rasm → 413 «25 MB»", lambda: r.status_code == 413 and "25 MB" in js(r).get("detail", ""),
      (r.status_code, r.text[:200]))
s = SessionLocal()
check("B6 murojaat YARATILMADI", lambda: s.query(_Mj).count() == mj_oldin)
s.close()
check("B7 fayl SAQLANMADI (uploads/murojaat)",
      lambda: (set(os.listdir(papka)) if os.path.isdir(papka) else set()) == fayllar_oldin)
tana, h = multipart(int(25.5 * MB), {"turi": "savol", "matn": "t263 25,5"})
r = cb.post("/api/murojaatlar", content=tana, headers=h)
check("B8 25,5 MB (qatlamdan o'tadi) → ikkinchi qavat 400 «25 MB dan katta»",
      lambda: r.status_code == 400 and "25 MB" in js(r).get("detail", ""), (r.status_code, r.text[:200]))
s = SessionLocal()
check("B8b murojaat YARATILMADI", lambda: s.query(_Mj).count() == mj_oldin)
s.close()
tana, h = multipart(30 * MB, {"confirm": ""}, "z.json", "application/json")
r = cb.post("/tiklash", content=tana, headers=h)
check("B9 /tiklash korxona admini 30 MB → 413 (tana o'qilmaydi)", lambda: r.status_code == 413, (r.status_code, r.text[:200]))
r = mijoz().post("/tiklash", content=tana, headers=h)
check("B10 /tiklash kirishsiz 30 MB → 413", lambda: r.status_code == 413, (r.status_code, r.text[:200]))
cp = kirgan(TOK_PA)
r = cp.post("/tiklash", content=tana, headers=h)
check("B11 /tiklash platforma egasi 30 MB → 413 EMAS (JSON o'qilmadi — 400 sahifa)",
      lambda: r.status_code == 400 and "JSON" in r.text, (r.status_code, r.text[:300]))
r = cp.post("/api/system/restore", content=tana, headers=h)
check("B12 /api/system/restore platforma egasi 30 MB → 413 EMAS (400 «o'qib bo'lmadi»)",
      lambda: r.status_code == 400 and "o'qib bo'lmadi" in js(r).get("detail", ""), (r.status_code, r.text[:300]))
r = kirgan(TOK_NF).post("/api/system/restore", content=tana, headers=h)
check("B13 /api/system/restore NOFAOL platforma egasi sessiyasi 30 MB → 413", lambda: r.status_code == 413, r.status_code)
r = kirgan(TOK_ESKI).post("/api/system/restore", content=tana, headers=h)
check("B14 /api/system/restore muddati o'tgan sessiya 30 MB → 413", lambda: r.status_code == 413, r.status_code)
tana, h = multipart(int(2.5 * MB), {}, "logo.png", "image/png")
r = cp.post("/api/settings/company/logo", content=tana, headers=h)
check("B15 logotip 2,5 MB → 400 «2 MB» (qatlamdan o'tadi, ikkinchi qavat)",
      lambda: r.status_code == 400 and "2 MB" in js(r).get("detail", ""), (r.status_code, r.text[:200]))
r = cp.get("/api/health")
check("B16 GET — o'zgarmagan", lambda: r.status_code == 200, r.status_code)


# ═════════════════════════════════════════════════════════════════════════════════════════════════════════
section("C — qatlamning o'zi (soxta ichki ilova, bo'laklab)")


class Soxta:
    """Ichki ilova: tanani to'liq o'qiydi (yoki `rejim` bo'yicha), 200 + o'qilgan bayt soni qaytaradi."""

    def __init__(self, rejim="oqi"):
        self.rejim = rejim
        self.chaqirildi = 0
        self.oqildi = 0
        self.xesh = None

    async def __call__(self, scope, receive, send):
        import hashlib
        self.chaqirildi += 1
        if scope["type"] == "lifespan":
            await send({"type": "lifespan.startup.complete"})
            return
        if self.rejim == "javob_avval":
            await send({"type": "http.response.start", "status": 200, "headers": []})
        h = hashlib.sha256()
        try:
            while True:
                x = await receive()
                if x["type"] != "http.request":
                    break
                b = x.get("body") or b""
                self.oqildi += len(b)
                h.update(b)
                if not x.get("more_body"):
                    break
        except Exception:                  # noqa: BLE001
            if self.rejim == "ushla":
                await send({"type": "http.response.start", "status": 200, "headers": []})
                await send({"type": "http.response.body", "body": b"ushlandi"})
                return
            raise
        self.xesh = h.hexdigest()
        if self.rejim != "javob_avval":
            await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": str(self.oqildi).encode()})


def asgi(ilova_rejim, yol, n_bayt, tur="application/json", cl=None, bolak=MB, cookie=None, usul="POST", uzilish_keyin=None,
         turi="http", tana_bayt=b"x"):
    ichki = Soxta(ilova_rejim)
    qatlam = main._TanaChegarasi(ichki)
    sarlavha = [(b"content-type", tur.encode())] if tur else []
    if cl is not None:
        sarlavha.append((b"content-length", str(cl).encode()))
    if cookie:
        for q in (cookie if isinstance(cookie, list) else [cookie]):
            sarlavha.append((b"cookie", q.encode()))
    scope = {"type": turi, "method": usul, "path": yol, "headers": sarlavha, "query_string": b""}
    holat = {"berildi": 0, "chaqiruv": 0}
    blok = tana_bayt * bolak if len(tana_bayt) == 1 else tana_bayt

    async def receive():
        holat["chaqiruv"] += 1
        if turi == "lifespan":
            return {"type": "lifespan.startup"}
        if uzilish_keyin is not None and holat["berildi"] >= uzilish_keyin:
            return {"type": "http.disconnect"}
        qoldi = n_bayt - holat["berildi"]
        k = min(len(blok), qoldi)
        holat["berildi"] += k
        return {"type": "http.request", "body": blok[:k], "more_body": holat["berildi"] < n_bayt}

    yuborildi = []

    async def send(x):
        yuborildi.append(x)

    xato = None
    try:
        asyncio.run(qatlam(scope, receive, send))
    except Exception as e:                 # noqa: BLE001
        xato = e
    bosh = next((x for x in yuborildi if x["type"] == "http.response.start"), None)
    sar = dict((k.lower(), v) for k, v in (bosh or {}).get("headers", [])) if bosh else {}
    tana = b"".join(x.get("body", b"") for x in yuborildi if x["type"] == "http.response.body")
    return {"ichki": ichki, "holat": holat, "status": bosh and bosh["status"], "sar": sar, "tana": tana, "xato": xato,
            "yuborildi": yuborildi}


if not YANGI:
    check("C0 `_TanaChegarasi` qatlami bor", False, "asl kod — qatlam yo'q")
else:
    n = asgi("oqi", "/api/x", 9 * MB, cl=9 * MB)
    check("C1 CL 9 MB (8 MB dan katta) — ichki ilova CHAQIRILMADI, 413", lambda: n["ichki"].chaqirildi == 0 and n["status"] == 413,
          (n["ichki"].chaqirildi, n["status"]))
    check("C1b tana oxirigacha o'qib tashlandi, `connection: close` YO'Q",
          lambda: n["holat"]["berildi"] == 9 * MB and b"connection" not in n["sar"], (n["holat"], n["sar"]))
    n = asgi("oqi", "/api/x", 300 * MB, cl=300 * MB)
    check("C2 CL 300 MB (8 + 128 dan katta) — darhol 413, tana O'QILMADI, `connection: close`",
          lambda: n["status"] == 413 and n["holat"]["chaqiruv"] == 0 and n["sar"].get(b"connection") == b"close"
          and n["ichki"].chaqirildi == 0, (n["status"], n["holat"], n["sar"]))
    n = asgi("oqi", "/api/x", 9 * MB)
    check("C3 chunked 9 MB — ichki ilova chegarada to'xtadi (≤ 8 MB o'qidi), 413, uning 200 javobi YUBORILMADI",
          lambda: n["status"] == 413 and n["ichki"].oqildi <= 8 * MB and b"8 MB" in n["tana"]
          and sum(1 for x in n["yuborildi"] if x["type"] == "http.response.start") == 1, (n["status"], n["ichki"].oqildi))
    check("C3b qolgan tana o'qib tashlandi (connection: close yo'q)",
          lambda: n["holat"]["berildi"] == 9 * MB and b"connection" not in n["sar"], n["holat"])
    n = asgi("oqi", "/api/x", 1024 * MB)
    check("C4 chunked 1 GB — 8 + 128 MB dan keyin o'qish TO'XTADI, `connection: close`",
          lambda: n["status"] == 413 and n["holat"]["berildi"] <= (8 + 128 + 2) * MB and n["sar"].get(b"connection") == b"close",
          (n["holat"], n["sar"]))
    n = asgi("ushla", "/api/x", 9 * MB)
    check("C5 ichki ilova xatoni ushlab 200 qaytarsa ham — 413 (ilova javobi yuborilmaydi)",
          lambda: n["status"] == 413 and b"ushlandi" not in n["tana"], (n["status"], n["tana"][:80]))
    n = asgi("javob_avval", "/api/x", 9 * MB)
    check("C6 javob boshlangandan keyin oshsa — xato (ulanish uziladi), 413 YO'Q",
          lambda: n["xato"] is not None and n["status"] == 200 and not any(
              x.get("status") == 413 for x in n["yuborildi"]), (n["xato"], n["status"]))
    n = asgi("oqi", "/api/x", 9 * MB, cl="abc")
    check("C7 yolg'on Content-Length («abc») — oqim sanog'i bilan 413", lambda: n["status"] == 413, n["status"])
    n = asgi("oqi", "/api/x", 5 * MB, cl=1)
    check("C7b kichik Content-Length (1), haqiqiy 5 MB — o'tadi (chegara ichida)", lambda: n["status"] == 200, n["status"])
    import hashlib as _hl
    blok = bytes(range(256)) * 4096
    n = asgi("oqi", "/api/x", 7 * MB, tana_bayt=blok, bolak=1)
    kut = _hl.sha256()
    q = 7 * MB
    while q > 0:
        k = min(len(blok), q)
        kut.update(blok[:k])
        q -= k
    check("C8 chegara ichidagi tana — o'zgarmasdan o'tadi (sha256 bir xil), 200",
          lambda: n["status"] == 200 and n["ichki"].xesh == kut.hexdigest() and n["ichki"].oqildi == 7 * MB)
    n = asgi("oqi", "/api/x", 8 * MB)
    check("C9 aynan 8 MB — o'tadi (chegara ham ruxsat)", lambda: n["status"] == 200 and n["ichki"].oqildi == 8 * MB, n["status"])
    n = asgi("oqi", "/api/x", 8 * MB + 1, bolak=MB)
    check("C9b 8 MB + 1 bayt — 413", lambda: n["status"] == 413, n["status"])
    n = asgi("oqi", "/api/x", 50 * MB, uzilish_keyin=3 * MB)
    check("C10 mijoz uzildi (3 MB da) — 413 yo'q, ilova o'zi tugatadi", lambda: n["status"] == 200 and n["xato"] is None,
          (n["status"], n["xato"]))
    n = asgi("oqi", "/api/x", 0, usul="GET", tur="")
    check("C11 GET (tanasiz) — o'tadi", lambda: n["status"] == 200 and n["ichki"].chaqirildi == 1, n["status"])
    n = asgi("oqi", "/x", 0, turi="lifespan", tur="")
    check("C12 lifespan — o'zgarmasdan o'tadi", lambda: n["ichki"].chaqirildi == 1 and n["xato"] is None, n["xato"])
    MP = "multipart/form-data; boundary=x"
    n = asgi("oqi", "/api/murojaatlar", 25 * MB, tur=MP)
    check("C13 multipart 25 MB (chunked) — o'tadi", lambda: n["status"] == 200, n["status"])
    n = asgi("oqi", "/api/murojaatlar", 27 * MB, tur=MP)
    check("C14 multipart 27 MB (chunked) — 413 «25 MB»", lambda: n["status"] == 413 and b"25 MB" in n["tana"], n["status"])
    n = asgi("oqi", "/tiklash", 150 * MB, tur=MP, cl=150 * MB, cookie=f"session_token={TOK_PA}")
    check("C15 /tiklash platforma egasi CL 150 MB — o'tadi (200)", lambda: n["status"] == 200 and n["ichki"].oqildi == 150 * MB,
          n["status"])
    n = asgi("oqi", "/tiklash", 202 * MB, tur=MP, cookie=f"session_token={TOK_PA}")
    check("C16 /tiklash platforma egasi chunked 202 MB — 413 «200 MB»", lambda: n["status"] == 413 and b"200 MB" in n["tana"],
          n["status"])
    n = asgi("oqi", "/api/system/restore", 150 * MB, tur=MP, cookie=["a=1", f"b=2; session_token={TOK_PA}"])
    check("C17 bir nechta cookie sarlavhasi — platforma egasi topildi (150 MB o'tadi)", lambda: n["status"] == 200, n["status"])
    n = asgi("oqi", "/tiklash", 150 * MB, tur=MP, cl=150 * MB, cookie=f"session_token={TOK_KA}")
    check("C18 /tiklash korxona admini CL 150 MB — 413 (ichki ilova chaqirilmadi)",
          lambda: n["status"] == 413 and n["ichki"].chaqirildi == 0 and b"25 MB" in n["tana"], n["status"])
    n = asgi("oqi", "/tiklash", 150 * MB, tur=MP, cl=150 * MB, cookie=f"session_token={TOK_NF}")
    check("C19 nofaol platforma egasi — 413", lambda: n["status"] == 413, n["status"])
    n = asgi("oqi", "/tiklash", 150 * MB, tur=MP, cl=150 * MB, cookie=f"session_token={TOK_ESKI}")
    check("C20 muddati o'tgan sessiya — 413", lambda: n["status"] == 413, n["status"])
    n = asgi("oqi", "/tiklash", 150 * MB, tur=MP, cl=150 * MB, cookie='session_token="; =;;"bad')
    check("C21 buzuq cookie — xatosiz, 413", lambda: n["status"] == 413 and n["xato"] is None, (n["status"], n["xato"]))
    n = asgi("oqi", "/tiklash", 150 * MB, tur=MP, cl=150 * MB, cookie="session_token=yoq-token")
    check("C22 bazada yo'q token — 413", lambda: n["status"] == 413, n["status"])
    n = asgi("oqi", "/api/murojaatlar", 150 * MB, tur=MP, cl=150 * MB, cookie=f"session_token={TOK_PA}")
    check("C23 platforma egasi — boshqa yo'lda 150 MB — 413 (katta chegara faqat tiklashda)",
          lambda: n["status"] == 413, n["status"])
    n = asgi("oqi", "/tiklash", 20 * MB, tur=MP, cl=20 * MB)
    check("C24 /tiklash 20 MB (fayl chegarasi ichida) — bazaga qaramasdan o'tadi", lambda: n["status"] == 200, n["status"])
    n = asgi("oqi", "/api/x", 9 * MB, tur="application/json")
    check("C25 /api/ — JSON javob", lambda: n["sar"].get(b"content-type") == b"application/json", n["sar"])
    n = asgi("oqi", "/hodim/login", 9 * MB, tur="application/x-www-form-urlencoded")
    check("C26 sahifa yo'li — HTML javob, «Orqaga» havolasi",
          lambda: n["sar"].get(b"content-type", b"").startswith(b"text/html") and "Orqaga" in n["tana"].decode()
          and int(n["sar"].get(b"content-length")) == len(n["tana"]), n["sar"])

# ═════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D — ikkinchi qavat: fayl chegara + 1 baytdan ko'p o'qilmaydi")


class SoxtaFayl:
    """`UploadFile` o'rnida: o'qish so'ralgan hajmni yozib boradi; 40 MB «fayl»."""

    def __init__(self, nom="r.jpg", hajm=40 * MB):
        self.filename = nom
        self.content_type = "image/jpeg"
        self.hajm = hajm
        self.sorovlar = []
        self.file = self

    def read(self, n=-1):
        self.sorovlar.append(n)
        k = self.hajm if (n is None or n < 0) else min(n, self.hajm)
        return b"a" * k


f = SoxtaFayl()
try:
    main._save_upload(f, "t263", main.ALLOWED_IMAGE_EXT)
    natija = "o'tdi"
except Exception as e:                     # noqa: BLE001
    natija = getattr(e, "status_code", type(e).__name__)
check("D1 `_save_upload` 40 MB — 400, o'qish ≤ MAX_UPLOAD_SIZE + 1",
      lambda: natija == 400 and f.sorovlar and all(0 <= x <= main.MAX_UPLOAD_SIZE + 1 for x in f.sorovlar), (natija, f.sorovlar))


class SoxtaAsync(SoxtaFayl):
    async def read(self, n=-1):            # noqa: D401 — UploadFile.read kabi async
        return SoxtaFayl.read(self, n)


f2 = SoxtaAsync("z.json", 210 * MB)
s = SessionLocal()
pa_u = s.query(User).filter(User.id == PA_ID).first()
try:
    asyncio.run(main.api_restore_backup(file=f2, replace=False, db=s, current_user=pa_u))
    natija = "o'tdi"
except Exception as e:                     # noqa: BLE001
    natija = (getattr(e, "status_code", type(e).__name__), str(getattr(e, "detail", e))[:120])
s.close()
check("D2 /api/system/restore 210 MB — 400 «200 MB», o'qish ≤ TIKLASH_MAX_BAYT + 1",
      lambda: natija[0] == 400 and "200 MB" in natija[1] and f2.sorovlar
      and all(0 <= x <= getattr(main, "TIKLASH_MAX_BAYT", 0) + 1 for x in f2.sorovlar), (natija, f2.sorovlar))
f3 = SoxtaAsync("z.json", 210 * MB)
s = SessionLocal()
pa_u = s.query(User).filter(User.id == PA_ID).first()


try:
    r3 = asyncio.run(main.tiklash_bajarish(file=f3, replace="", confirm="", db=s, current_user=pa_u))
    natija = (r3.status_code, r3.body.decode("utf-8", "replace"))
except Exception as e:                     # noqa: BLE001
    natija = (type(e).__name__, str(e)[:200])
s.close()
check("D3 /tiklash 210 MB — 400 «200 MB», o'qish ≤ TIKLASH_MAX_BAYT + 1",
      lambda: natija[0] == 400 and "200 MB" in natija[1] and f3.sorovlar
      and all(0 <= x <= getattr(main, "TIKLASH_MAX_BAYT", 0) + 1 for x in f3.sorovlar), (natija[0], f3.sorovlar))
f4 = SoxtaAsync("logo.png", 30 * MB)
f4.content_type = "image/png"
s = SessionLocal()
try:
    asyncio.run(main.api_upload_company_logo(file=f4, db=s, current_user=pa_u))
    natija = "o'tdi"
except Exception as e:                     # noqa: BLE001
    natija = getattr(e, "status_code", type(e).__name__)
s.close()
check("D4 logotip 30 MB — 400, o'qish ≤ 2 MB + 1", lambda: natija == 400 and f4.sorovlar
      and all(0 <= x <= 2 * MB + 1 for x in f4.sorovlar), (natija, f4.sorovlar))

print("\n" + "=" * 70)
print(f"{REJIM}NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
