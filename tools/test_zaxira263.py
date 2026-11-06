#!/usr/bin/env python3
"""
test_zaxira263.py — kech199 (zip 263, xavfsizlik REJA 1-band — EGASI QARORI 06.11 17:33): kunlik zaxira — HAR KORXONA ALOHIDA,
SHIFRLANGAN (AES-256 zip, parol `ZAXIRA_PAROLI`), faqat egasiga; bot tokeni / webhook imzosi zaxiraga KIRMAYDI.

NIMA UCHUN KERAK
----------------
  O'LCHANGAN (Fable F1 `work/k263/fable/probes/backup_check.py`, Opus): `export_full_backup` har korxonaning `telegram_bot_token` va
  `telegram_webhook_secret` ini XOM chiqarardi; kunlik zaxira — BUTUN baza bitta SHIFRSIZ JSON bo'lib Telegram chatiga ketardi.

BO'LIMLAR
  A — eksport: sir sozlamalari yo'q (ikkala korxona), oddiy sozlamalar bor; /api/system/backup ham;
  B — tiklash: joriy sirlar SAQLANADI (fayl eski formatda bo'lsa ham joriy ustun), joriy yo'q bo'lsa — fayldagisi; oddiy sozlamalar
      fayldan;
  C — shifrlash yordamchilari: AES (WinZip AES, 256), parolsiz o'qilmaydi, to'g'ri parol — bayt-baayt bir xil, noto'g'ri parol,
      parol yo'q, ikki fayl, .json emas, zip-bomba (e'lon qilingan hajm), buzilgan zip, shifrsiz zip, parol qoidasi (12 belgi);
  D — kunlik zaxira (`run_daily_backup`): parol yo'q / qisqa — fayl YUBORILMAYDI, xabar + jurnal; korxona bo'yicha alohida fayl,
      nomi, turi, ochiladi, ichida faqat o'sha korxona, token yo'q, xom matn ko'rinmaydi; ikki chat; bitta korxona xatosi
      qolganini to'xtatmaydi; 49 MB; chat yo'q; kod tozalash;
  E — tiklash sahifalari: /tiklash .zip (forma paroli / server paroli / noto'g'ri parol), /api/system/restore .zip, eski .json;
      sahifada parol maydoni.
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
Asl kodga (zip 263 1-qism, 894aa9b) qarshi YIQILADI (QULAMAYDI).
ISHLATISH: python3 tools/test_zaxira263.py
"""
import os
import sys
import tempfile

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "zaxira263_test"
_DB = os.path.join(tempfile.gettempdir(), "zaxira263_test.db")
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
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "ZAXIRA_PAROLI"):
    os.environ.pop(_k, None)

import io                                          # noqa: E402
import json                                        # noqa: E402
import time                                        # noqa: E402
import zipfile                                     # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, CompanySetting, Master, ErrorLog   # noqa: E402
from production_models import Company             # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []
YANGI = hasattr(main, "zaxira_shifrla")


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


TOKEN_A = "123456789:AAZAXIRA263tokenSECRET_Axxxxxxxxxxx"
TOKEN_B = "223456789:AAZAXIRA263tokenSECRET_Bxxxxxxxxxxx"
SIR_A, SIR_B = "webhookSIR263A_qwertyuiop", "webhookSIR263B_asdfghjkl"
PAROL = "Zaxira-Paroli-263!"

s = SessionLocal()
c1 = s.query(Company).filter(Company.id == 1).first()
if c1 is None:
    s.add(Company(id=1, name="Bosh Korxona", code="BOSH-263"))
    s.commit()
    c1 = s.query(Company).filter(Company.id == 1).first()
if not s.query(Company).filter(Company.id == 2).first():
    s.add(Company(id=2, name="Ikkinchi «Korxona»", code="IKKI 263/Ж"))
s.commit()
KOD1 = s.query(Company).filter(Company.id == 1).first().code
with contextlib.redirect_stdout(_quiet):
    pa = auth.create_user(s, "z263_egasi", "Parol263!xyz", UserRole.ADMIN, "Platforma egasi", company_id=1)
s.commit()
s.query(User).filter(User.id == pa.id).update({"is_platform_admin": True})
PA_ID = pa.id
for cid, tok, sir, belgi in ((1, TOKEN_A, SIR_A, "BELGI-A-263"), (2, TOKEN_B, SIR_B, "BELGI-B-263")):
    crud.set_setting(s, "telegram_bot_token", tok, company_id=cid)
    crud.set_setting(s, "telegram_webhook_secret", sir, company_id=cid)
    crud.set_setting(s, "z263_belgi", belgi, company_id=cid)
    crud.set_setting(s, "telegram_chat_id", f"-100{cid}263", company_id=cid)
    s.add(Master(company_id=cid, name=f"Usta {belgi}", phone=f"+99890263000{cid}"))
s.commit()
TOK_PA = auth.create_session(s, PA_ID)
s.close()


def sozlama(cid, k):
    db = SessionLocal()
    try:
        r = db.query(CompanySetting).filter(CompanySetting.company_id == cid, CompanySetting.key == k).first()
        return r.value if r else None
    finally:
        db.close()


# ═════════════════════════════════════════════════════════════════════════════════════════════════════════
section("A — eksport: sir sozlamalari yo'q")
s = SessionLocal()
ex1 = crud.export_full_backup(s, company_id=1)
ex2 = crud.export_full_backup(s, company_id=2)
exh = crud.export_full_backup(s)
s.close()
for nom, ex in (("1-korxona", ex1), ("2-korxona", ex2), ("butun baza", exh)):
    matn = json.dumps(ex, ensure_ascii=False)
    check(f"A1 {nom}: bot tokeni / webhook imzosi YO'Q",
          lambda m=matn: not any(x in m for x in (TOKEN_A, TOKEN_B, SIR_A, SIR_B)))
    kalitlar = {r["key"] for r in ex["tables"].get("company_settings", [])}
    check(f"A2 {nom}: sir kalitlari yo'q, oddiy sozlamalar (z263_belgi, telegram_chat_id) BOR",
          lambda k=kalitlar: "telegram_bot_token" not in k and "telegram_webhook_secret" not in k and "z263_belgi" in k
          and "telegram_chat_id" in k, kalitlar)
check("A3 1-korxona fayli — faqat o'z belgisi (B yo'q)",
      lambda: "BELGI-A-263" in json.dumps(ex1) and "BELGI-B-263" not in json.dumps(ex1))
check("A4 `_SECRET_SETTING_KEYS`", lambda: crud._SECRET_SETTING_KEYS == frozenset({"telegram_bot_token", "telegram_webhook_secret"}))
cp = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
cp.cookies.set("session_token", TOK_PA)
r = cp.get("/api/system/backup")
check("A5 /api/system/backup — 200, token / imzo yo'q, o'z belgisi bor",
      lambda: r.status_code == 200 and TOKEN_A not in r.text and SIR_A not in r.text and "BELGI-A-263" in r.text, r.status_code)
ESKI_JSON = json.loads(r.text) if r.status_code == 200 else None

# ═════════════════════════════════════════════════════════════════════════════════════════════════════════
section("B — tiklash: joriy sirlar saqlanadi")
s = SessionLocal()
nat = crud.import_full_backup(s, ex1, company_id=1, replace=True)
s.close()
check("B1 tiklash muvaffaqiyatli", lambda: nat.get("success"), nat)
check("B2 tiklashdan keyin bot tokeni / imzosi — JORIY qiymat (o'chmadi)",
      lambda: sozlama(1, "telegram_bot_token") == TOKEN_A and sozlama(1, "telegram_webhook_secret") == SIR_A)
check("B3 oddiy sozlama fayldan tiklandi", lambda: sozlama(1, "z263_belgi") == "BELGI-A-263")
check("B4 2-korxona sirlari tegilmadi", lambda: sozlama(2, "telegram_bot_token") == TOKEN_B and sozlama(2, "telegram_webhook_secret") == SIR_B)
eski = json.loads(json.dumps(ex1))
_namuna = dict(eski["tables"]["company_settings"][0])          # zip 263 dan oldingi zaxira qatori — hamma ustunlar bilan
eski["tables"]["company_settings"] = list(eski["tables"].get("company_settings", [])) + [
    dict(_namuna, id=990001, company_id=1, key="telegram_bot_token", value="ESKI-FAYL-TOKENI"),
    dict(_namuna, id=990002, company_id=1, key="telegram_webhook_secret", value="ESKI-FAYL-SIRI")]
s = SessionLocal()
nat = crud.import_full_backup(s, eski, company_id=1, replace=True)
s.close()
check("B5 eski formatdagi fayl (sirlar bilan) — JORIY qiymat ustun",
      lambda: nat.get("success") and sozlama(1, "telegram_bot_token") == TOKEN_A and sozlama(1, "telegram_webhook_secret") == SIR_A,
      (nat, sozlama(1, "telegram_bot_token")))
s = SessionLocal()
s.query(CompanySetting).filter(CompanySetting.company_id == 1,
                               CompanySetting.key.in_(["telegram_bot_token", "telegram_webhook_secret"])).delete(synchronize_session=False)
s.commit()
nat = crud.import_full_backup(s, eski, company_id=1, replace=True)
s.close()
check("B6 joriy sir yo'q (yangi baza) — eski fayldagi qiymat tiklanadi",
      lambda: nat.get("success") and sozlama(1, "telegram_bot_token") == "ESKI-FAYL-TOKENI", (nat, sozlama(1, "telegram_bot_token")))
s = SessionLocal()
crud.set_setting(s, "telegram_bot_token", TOKEN_A, company_id=1)
crud.set_setting(s, "telegram_webhook_secret", SIR_A, company_id=1)
s.commit()
n_sozlama = s.query(CompanySetting).filter(CompanySetting.company_id == 1, CompanySetting.key == "telegram_bot_token").count()
s.close()
check("B7 sir kaliti bitta qator (takror yo'q)", lambda: n_sozlama == 1, n_sozlama)

# ═════════════════════════════════════════════════════════════════════════════════════════════════════════
section("C — shifrlash yordamchilari")
if not YANGI:
    check("C0 `zaxira_shifrla` / `zaxira_ochish` bor", False, "asl kod")
else:
    tana = json.dumps(ex1, ensure_ascii=False, indent=2).encode("utf-8")
    z = main.zaxira_shifrla(tana, "BOSH-2026-11-06.json", PAROL)
    check("C1 zip imzosi, ichida bitta fayl", lambda: z[:4] == b"PK\x03\x04" and len(zipfile.ZipFile(io.BytesIO(z)).infolist()) == 1)
    inf = zipfile.ZipFile(io.BytesIO(z)).infolist()[0]
    check("C2 shifrlangan (bayroq) va WinZip AES (usul 99), AES-256 (kuch 3)",
          lambda: inf.flag_bits & 1 and inf.compress_type == 99 and inf.extra.find(b"\x01\x99") >= 0
          and inf.extra[inf.extra.find(b"\x01\x99") + 8] == 3, (inf.flag_bits, inf.compress_type, inf.extra))
    check("C3 xom matn ko'rinmaydi (belgi, korxona nomi)", lambda: b"BELGI-A-263" not in z and b"z263_belgi" not in z)

    def stdlib_oqiydimi():
        try:
            zipfile.ZipFile(io.BytesIO(z)).read(inf.filename)
            return True
        except Exception:                  # noqa: BLE001
            return False
    check("C4 parolsiz (oddiy zipfile) o'qilmaydi", lambda: not stdlib_oqiydimi())
    check("C5 to'g'ri parol — bayt-baayt bir xil", lambda: main.zaxira_ochish(z, PAROL, 10 * 1024 * 1024) == tana)

    def xato(fn):
        try:
            fn()
            return None
        except main.ZaxiraOchishXato as e:
            return str(e)
        except Exception as e:             # noqa: BLE001
            return f"BOSHQA {type(e).__name__}: {e}"
    x = xato(lambda: main.zaxira_ochish(z, "notogri-parol-1234", 10 * 1024 * 1024))
    check("C6 noto'g'ri parol — «parol noto'g'ri»", lambda: x and "noto'g'ri" in x and "BOSHQA" not in x, x)
    x = xato(lambda: main.zaxira_ochish(z, "", 10 * 1024 * 1024))
    check("C7 parol yo'q — «parolni kiriting»", lambda: x and "parol" in x.lower() and "BOSHQA" not in x, x)
    import pyzipper
    b2 = io.BytesIO()
    with pyzipper.AESZipFile(b2, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zz:
        zz.setpassword(PAROL.encode())
        zz.writestr("a.json", b"{}")
        zz.writestr("b.json", b"{}")
    x = xato(lambda: main.zaxira_ochish(b2.getvalue(), PAROL, 10 * 1024 * 1024))
    check("C8 zip ichida ikki fayl — rad", lambda: x and "bitta .json" in x, x)
    b3 = io.BytesIO()
    with zipfile.ZipFile(b3, "w") as zz:
        zz.writestr("a.txt", b"{}")
    x = xato(lambda: main.zaxira_ochish(b3.getvalue(), PAROL, 10 * 1024 * 1024))
    check("C9 .json emas — rad", lambda: x and "bitta .json" in x, x)
    b4 = io.BytesIO()
    with zipfile.ZipFile(b4, "w", compression=zipfile.ZIP_DEFLATED) as zz:
        zz.writestr("bomba.json", b"0" * (30 * 1024 * 1024))
    x = xato(lambda: main.zaxira_ochish(b4.getvalue(), "", 20 * 1024 * 1024))
    check("C10 zip-bomba (ochilgan 30 MB > chegara 20 MB) — rad, xotiraga ochilmaydi",
          lambda: x and "juda katta" in x and len(b4.getvalue()) < 1024 * 1024, (x, len(b4.getvalue())))
    # e'lon qilingan hajm yolg'on (kichik) — baribir chegara + 1 baytdan ko'p o'qilmaydi
    soxta = bytearray(b4.getvalue())
    import struct
    i_cd = soxta.rfind(b"PK\x01\x02")
    struct.pack_into("<I", soxta, i_cd + 24, 100)          # markaziy katalogdagi ochilgan hajm — 100 bayt
    i_lh = soxta.find(b"PK\x03\x04")
    struct.pack_into("<I", soxta, i_lh + 22, 100)
    x = xato(lambda: main.zaxira_ochish(bytes(soxta), "", 20 * 1024 * 1024))
    check("C11 e'lon qilingan hajm yolg'on — baribir rad (o'qish chegarada to'xtaydi)", lambda: x and "BOSHQA" not in x, x)
    x = xato(lambda: main.zaxira_ochish(b"PK\x03\x04buzilgan" + b"\x00" * 50, PAROL, 1024))
    check("C12 buzilgan zip — «buzilgan»", lambda: x and "buzilgan" in x, x)
    b5 = io.BytesIO()
    with zipfile.ZipFile(b5, "w", compression=zipfile.ZIP_DEFLATED) as zz:
        zz.writestr("eski.json", b'{"tables":{}}')
    check("C13 shifrsiz zip (.json) — parolsiz ochiladi", lambda: main.zaxira_ochish(b5.getvalue(), "", 1024) == b'{"tables":{}}')
    check("C14 parol qoidasi: bo'sh / 11 belgi — xato, 12 — yaroqli",
          lambda: main.zaxira_paroli_xatosi("") and main.zaxira_paroli_xatosi("a" * 11) and main.zaxira_paroli_xatosi("a" * 12) is None)
    x = xato(lambda: main.zaxira_shifrla(b"{}", "a.json", "qisqa"))
    check("C15 qisqa parol bilan shifrlash — rad (shifrsiz fayl chiqmaydi)", lambda: x and "qisqa" in x, x)
    check("C16 kod tozalash: bo'shliq / kirill / «/» — «-»; bo'sh — k<id>",
          lambda: main.zaxira_kodi("IKKI 263/Ж", 2) == "IKKI-263" and main.zaxira_kodi("", 7) == "k7"
          and main.zaxira_kodi("../../x", 3) == "x" and main.zaxira_kodi("ABC_1-2", 1) == "ABC_1-2")
    check("C17 json fayl — o'zgarmasdan (zip emas)", lambda: main.zaxira_json_ol(b'{"a":1}', "") == b'{"a":1}')

# ═════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D — kunlik zaxira (run_daily_backup)")
HUJJAT, XABAR = [], []
_asl_doc, _asl_msg, _asl_sleep = main._send_telegram_document, main._send_telegram, time.sleep
HUJJAT_OK = {"v": True}


def _doc(chat_id, file_bytes, filename, caption="", content_type="application/json", company_id=None):
    HUJJAT.append({"chat": chat_id, "bayt": file_bytes, "nom": filename, "izoh": caption, "tur": content_type})
    return HUJJAT_OK["v"] if not callable(HUJJAT_OK["v"]) else HUJJAT_OK["v"](chat_id, filename)


main._send_telegram_document = _doc
main._send_telegram = lambda text, company_id=None: XABAR.append(text)
time.sleep = lambda *_a, **_k: None


def ishlat(env):
    HUJJAT.clear()
    XABAR.clear()
    for k in ("BACKUP_TELEGRAM_CHAT_ID", "ZAXIRA_PAROLI"):
        os.environ.pop(k, None)
    os.environ.update(env)
    with contextlib.redirect_stdout(_quiet):
        main.run_daily_backup()


def xato_soni(qism):
    db = SessionLocal()
    try:
        return db.query(ErrorLog).filter(ErrorLog.error_message.like(f"%{qism}%")).count()
    finally:
        db.close()


ishlat({"BACKUP_TELEGRAM_CHAT_ID": "777"})
check("D1 ZAXIRA_PAROLI yo'q — HECH QANDAY fayl yuborilmadi", lambda: HUJJAT == [], [h["nom"] for h in HUJJAT])
check("D2 … egasiga xabar «o'rnatilmagan» + Railway yo'riqnomasi",
      lambda: XABAR and "YUBORILMADI" in XABAR[0] and "ZAXIRA_PAROLI o'rnatilmagan" in XABAR[0] and "Railway" in XABAR[0], XABAR)
check("D3 … «Xatoliklar» jurnaliga yozildi", lambda: xato_soni("ZAXIRA_PAROLI o'rnatilmagan") >= 1)
ishlat({"BACKUP_TELEGRAM_CHAT_ID": "777", "ZAXIRA_PAROLI": "qisqa-11-be"})
check("D4 parol 11 belgi — fayl yuborilmadi, xabar «juda qisqa»",
      lambda: HUJJAT == [] and XABAR and "juda qisqa" in XABAR[0], (len(HUJJAT), XABAR))
ishlat({"BACKUP_TELEGRAM_CHAT_ID": "777", "ZAXIRA_PAROLI": PAROL})
s = SessionLocal()
korx = {c.id: c for c in s.query(Company).all()}
kodlar = {cid: main.zaxira_kodi(c.code, cid) for cid, c in korx.items()} if YANGI else {}
s.close()
check("D5 har korxonaga BITTA fayl (2 korxona — 2 fayl), xato xabari yo'q",
      lambda: len(HUJJAT) == len(korx) == 2 and XABAR == [], ([h["nom"] for h in HUJJAT], XABAR))
sana = main._t_vaqt().strftime("%Y-%m-%d")
check("D6 fayl nomlari epserp-<kod>-<sana>.zip, turi application/zip",
      lambda: sorted(h["nom"] for h in HUJJAT) == sorted(f"epserp-{k}-{sana}.zip" for k in kodlar.values())
      and all(h["tur"] == "application/zip" for h in HUJJAT), [(h["nom"], h["tur"]) for h in HUJJAT])
ochilgan = {}
for h in HUJJAT:
    try:
        ochilgan[h["nom"]] = json.loads(main.zaxira_ochish(h["bayt"], PAROL, 50 * 1024 * 1024))
    except Exception as e:                 # noqa: BLE001
        ochilgan[h["nom"]] = repr(e)
check("D7 har fayl parol bilan ochiladi, ichida o'sha korxona (company_id)",
      lambda: all(isinstance(ochilgan.get(f"epserp-{kodlar[c]}-{sana}.zip"), dict)
                  and ochilgan[f"epserp-{kodlar[c]}-{sana}.zip"]["company_id"] == c for c in korx), list(ochilgan))
check("D8 1-korxona faylida faqat 1-korxona (B belgisi / ustasi yo'q), 2-da — faqat 2",
      lambda: "BELGI-A-263" in json.dumps(ochilgan[f"epserp-{kodlar[1]}-{sana}.zip"])
      and "BELGI-B-263" not in json.dumps(ochilgan[f"epserp-{kodlar[1]}-{sana}.zip"])
      and "BELGI-B-263" in json.dumps(ochilgan[f"epserp-{kodlar[2]}-{sana}.zip"])
      and "BELGI-A-263" not in json.dumps(ochilgan[f"epserp-{kodlar[2]}-{sana}.zip"]))
check("D9 ochilgan fayllarda token / imzo YO'Q",
      lambda: not any(t in json.dumps(v) for v in ochilgan.values() for t in (TOKEN_A, TOKEN_B, SIR_A, SIR_B)))
check("D10 shifrlangan baytlarda xom matn yo'q (belgi, «Usta»)",
      lambda: all(b"BELGI" not in h["bayt"] and b"Usta" not in h["bayt"] for h in HUJJAT))
check("D11 ichki fayl nomi <kod>-<sana>.json",
      lambda: all(zipfile.ZipFile(io.BytesIO(h["bayt"])).infolist()[0].filename == h["nom"][len("epserp-"):-4] + ".json"
                  for h in HUJJAT))
check("D12 izohda korxona nomi, sana, «Shifrlangan»",
      lambda: all("Kunlik zaxira" in h["izoh"] and "Shifrlangan" in h["izoh"] for h in HUJJAT)
      and any("Ikkinchi «Korxona»" in h["izoh"] for h in HUJJAT))
ishlat({"BACKUP_TELEGRAM_CHAT_ID": "777, 888", "ZAXIRA_PAROLI": PAROL})
check("D13 ikki chat — har korxona har chatga (4 fayl)",
      lambda: len(HUJJAT) == 4 and sorted({h["chat"] for h in HUJJAT}) == ["777", "888"], [(h["chat"], h["nom"]) for h in HUJJAT])
HUJJAT_OK["v"] = lambda chat, nom: not nom.startswith(f"epserp-{kodlar.get(1)}-")
ishlat({"BACKUP_TELEGRAM_CHAT_ID": "777", "ZAXIRA_PAROLI": PAROL})
HUJJAT_OK["v"] = True
check("D14 1-korxona fayli yuborilmadi — 2-korxona baribir yuborildi, xato xabari (1 ta)",
      lambda: len(HUJJAT) == 2 and XABAR and "1 ta xato" in XABAR[-1] and "Telegramga yuborilmadi" in XABAR[-1], XABAR)
check("D15 … xato jurnalda", lambda: xato_soni("Telegramga yuborilmadi") >= 1)
_asl_ex = crud.export_full_backup


def _ex_buz(db, company_id=None):
    if company_id == 2:
        raise RuntimeError("sinov: eksport buzildi")
    return _asl_ex(db, company_id=company_id)


crud.export_full_backup = _ex_buz
ishlat({"BACKUP_TELEGRAM_CHAT_ID": "777", "ZAXIRA_PAROLI": PAROL})
crud.export_full_backup = _asl_ex
check("D16 2-korxona eksporti xato — 1-korxona yuborildi, xabarda sabab",
      lambda: [h["nom"] for h in HUJJAT] == [f"epserp-{kodlar[1]}-{sana}.zip"] and XABAR and "sinov: eksport buzildi" in XABAR[-1],
      ([h["nom"] for h in HUJJAT], XABAR))
if YANGI:
    _asl_sh = main.zaxira_shifrla
    main.zaxira_shifrla = lambda tana, nom, parol: b"PK\x03\x04" + b"0" * (49 * 1024 * 1024)
    ishlat({"BACKUP_TELEGRAM_CHAT_ID": "777", "ZAXIRA_PAROLI": PAROL})
    main.zaxira_shifrla = _asl_sh
    check("D17 fayl ≥ 49 MB — yuborilmadi, xabar «50 MB»", lambda: HUJJAT == [] and XABAR and "50 MB" in XABAR[-1], XABAR)
ishlat({"ZAXIRA_PAROLI": PAROL})
check("D18 BACKUP_TELEGRAM_CHAT_ID yo'q — hech narsa", lambda: HUJJAT == [] and XABAR == [])
SAQLANGAN = None
ishlat({"BACKUP_TELEGRAM_CHAT_ID": "777", "ZAXIRA_PAROLI": PAROL})
for h in HUJJAT:
    if h["nom"].startswith(f"epserp-{kodlar.get(1)}-"):
        SAQLANGAN = h["bayt"]
main._send_telegram_document, main._send_telegram, time.sleep = _asl_doc, _asl_msg, _asl_sleep
for k in ("BACKUP_TELEGRAM_CHAT_ID", "ZAXIRA_PAROLI"):
    os.environ.pop(k, None)

# ═════════════════════════════════════════════════════════════════════════════════════════════════════════
section("E — tiklash sahifalari (.zip)")
r = cp.get("/tiklash")
check("E1 /tiklash sahifasi — parol maydoni, .zip qabul qilinadi",
      lambda: r.status_code == 200 and 'name="zaxira_paroli"' in r.text and 'type="password"' in r.text and ".zip" in r.text,
      r.status_code)
s = SessionLocal()
s.query(Master).filter(Master.company_id == 1).delete(synchronize_session=False)
s.add(Master(company_id=1, name="Tiklashdan oldin qo'shilgan usta", phone="+998902630099"))
s.commit()
s.close()


def ustalar1():
    db = SessionLocal()
    try:
        return sorted(m.name for m in db.query(Master).filter(Master.company_id == 1).all())
    finally:
        db.close()


FORMA = {"replace": "true", "confirm": "TIKLASHNI-TASDIQLAYMAN"}
if SAQLANGAN:
    r = cp.post("/tiklash", data=dict(FORMA, zaxira_paroli="notogri-parol-12345"),
                files={"file": ("epserp.zip", SAQLANGAN, "application/zip")})
    check("E2 /tiklash noto'g'ri parol — 400, «noto'g'ri», ma'lumot O'ZGARMADI",
          lambda: r.status_code == 400 and "noto" in r.text and ustalar1() == ["Tiklashdan oldin qo'shilgan usta"], (r.status_code, r.text[-400:]))
    r = cp.post("/tiklash", data=dict(FORMA, zaxira_paroli=PAROL), files={"file": ("epserp.zip", SAQLANGAN, "application/zip")})
    check("E3 /tiklash .zip + forma paroli — tiklandi (zaxiradagi usta qaytdi)",
          lambda: r.status_code == 200 and ustalar1() == ["Usta BELGI-A-263"], (r.status_code, r.text[-400:], ustalar1()))
    check("E4 … bot tokeni / imzosi joriy qiymatda", lambda: sozlama(1, "telegram_bot_token") == TOKEN_A
          and sozlama(1, "telegram_webhook_secret") == SIR_A)
    r = cp.post("/tiklash", data=FORMA, files={"file": ("epserp.zip", SAQLANGAN, "application/zip")})
    check("E5 /tiklash parolsiz, serverda ZAXIRA_PAROLI yo'q — 400 «parolni kiriting»",
          lambda: r.status_code == 400 and "parol" in r.text, (r.status_code, r.text[-300:]))
    os.environ["ZAXIRA_PAROLI"] = PAROL
    r = cp.post("/tiklash", data=FORMA, files={"file": ("epserp.zip", SAQLANGAN, "application/zip")})
    check("E6 /tiklash parolsiz, serverda ZAXIRA_PAROLI bor — tiklandi", lambda: r.status_code == 200, (r.status_code, r.text[-300:]))
    os.environ.pop("ZAXIRA_PAROLI", None)
    r = cp.post("/api/system/restore?replace=true", data={"zaxira_paroli": PAROL},
                files={"file": ("epserp.zip", SAQLANGAN, "application/zip")})
    check("E7 /api/system/restore .zip + parol — 200 success", lambda: r.status_code == 200 and js(r).get("success"),
          (r.status_code, r.text[:300]))
    r = cp.post("/api/system/restore?replace=true", data={"zaxira_paroli": "notogri-parol-12345"},
                files={"file": ("epserp.zip", SAQLANGAN, "application/zip")})
    check("E8 /api/system/restore noto'g'ri parol — 400 «noto'g'ri»",
          lambda: r.status_code == 400 and "noto'g'ri" in js(r).get("detail", ""), (r.status_code, r.text[:300]))
else:
    check("E2 kunlik zaxira fayli olindi", False, "SAQLANGAN yo'q")
if ESKI_JSON is not None:
    r = cp.post("/tiklash", data=FORMA, files={"file": ("eski.json", json.dumps(ESKI_JSON).encode(), "application/json")})
    check("E9 eski .json — avvalgidek tiklanadi", lambda: r.status_code == 200, (r.status_code, r.text[-300:]))
    r = cp.post("/api/system/restore?replace=true", files={"file": ("eski.json", json.dumps(ESKI_JSON).encode(), "application/json")})
    check("E10 /api/system/restore eski .json — 200", lambda: r.status_code == 200 and js(r).get("success"), (r.status_code, r.text[:200]))
check("E11 requirements.txt — pyzipper va pycryptodomex (aniq versiya)",
      lambda: "pyzipper==0.3.6" in open("requirements.txt").read() and "pycryptodomex==3.20.0" in open("requirements.txt").read())

print("\n" + "=" * 70)
print(f"{REJIM}NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
