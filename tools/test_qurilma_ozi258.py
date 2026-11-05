#!/usr/bin/env python3
"""
test_qurilma_ozi258.py — kech191 (zip 258): hodim paneli — ruxsat berilgan («o'sha») telefon brauzeri saytni unutsa, qayta ruxsat
SO'RALMAYDI (egasi QARORI 05.11 «O'sha telefon — so'ramasin»).

NIMA UCHUN KERAK (egasi 05.11 12:09: «har 3–4 kunda palonchi hodim kirmoqchi, tasdiqlaysizmi? keladi — bitta ruxsatdan keyin qayta
so'ramasin»)
-------------------------------------------------------------------------------------------------------------------
  O'LCHANGAN — production zaxirasi 05.11 12:58 (`work/k258/prod_olchov258.py`; natija MAXFIY papkada): Ulug'bek — har kirish ODDIY
  Chrome («Android 10; K … Chrome/155», ilova ichidagi brauzer belgisi yo'q); 26.10 dan beri 5 so'rov: 3 tasida brauzer telefon kalitini
  (cookie) yo'qotgan — 05.11 11:59 da ruxsat berildi, 12:00 da yana yangi so'rov; 2 tasi — admin «Telefonni uzish» dan keyin (egasi:
  «kira olmayotgani uchun» bosgan — sababi PIN edi). Telefon nomi — modelli («Android · SM-A155F · Chrome»), har safar AYNAN bir xil.
  `work/k258/probe258.py` (zip 257 kodi, SQ = PG): cookie yo'qolsa — har kirishda so'rov + Telegram; nom tasdiqlangannikiga teng.
  EGASI QARORI (05.11, tugmali): ruxsat berilgan telefon MODELI (tizim · model · brauzer) bilan to'g'ri PIN — o'zi kiradi, adminga faqat
  «qayta kirdi» xabari; boshqa model — avvalgidek so'rov. Xavf egasiga aytilgan: PIN ni bilgan va AYNAN shu modeldagi telefoni bor odam.

BO'LIMLAR
  A — o'sha telefon (cookie siz, o'sha brauzer satri + model): panel darhol, so'rov / «yangi telefon» xabari YO'Q, «qayta kirdi» xabari,
      jurnal «qurilma_qayta», eski kalit sessiyasi yopiladi, nom / vaqt;
  B — so'raladiganlar: boshqa model, o'sha model boshqa brauzer, model noma'lum (yangi Chrome «K» + sahifa modeli yo'q), iPhone,
      telefon uzilgan, ruxsat hech qachon berilmagan, noto'g'ri PIN, model kichik-katta harf farqi;
  C — boshqa telefon so'rovi kutayotganda o'sha telefon qaytsa — so'rov saqlanadi; vaqtinchalik PIN — «pin» holati; boshqa korxona;
  D — telefon nomi: ilova ichidagi brauzer satri («Build/…; wv)») — model endi o'qiladi va brauzer «ilova ichida» / «Telegram ichida»
      (Chrome emas — review258 F3); eski nomlar o'zgarmagan;
  F — mustaqil tekshiruv (review258) himoyalari: F1 shu brauzer boshqa nom bilan kutayotgan bo'lsa — bog'lanmaydi (modelni taxmin
      qilish jim o'tmaydi); F6 rad etilgandan keyin — keyingi ruxsatgacha avtomatik yo'q; F5 poyga (eskirgan obyekt, ikki marta bosish);
      shu brauzerning o'sha nomli eski so'rovi tozalanadi; tizim (Windows) farqi; vaqt QAT'IY yangilanadi.
  E — statik: «Telefonni uzish» oynasida PIN eslatmasi, jurnal yorlig'i.
REJIMLAR: SQLite (odatiy); `PG_URL` — har ishga YANGI PostgreSQL bazasi; `TENANT_FILTER=1` bilan ham.
Asl kodga (zip 257) qarshi YIQILADI (QULAMAYDI).
ISHLATISH: python3 tools/test_qurilma_ozi258.py
"""
import os
import sys
import tempfile

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "qurilma_ozi258_test"
_DB = os.path.join(tempfile.gettempdir(), "qurilma_ozi258_test.db")
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

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

_quiet = io.StringIO()
with contextlib.redirect_stdout(_quiet):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import crud                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, Employee, EmployeeSession, ActivityLog   # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []


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


# production dagi Ulug'bek satri (05.11 zaxirasi) — yangi Chrome modelni yashiradi, model sahifa skriptidan keladi
CHROME = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Mobile Safari/537.36"
CHROME_YANGI = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Mobile Safari/537.36"
SAMSUNG = ("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/27.0 Chrome/125.0.0.0 "
           "Mobile Safari/537.36")
IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 "
          "Mobile/15E148 Safari/604.1")
WV = ("Mozilla/5.0 (Linux; Android 13; SM-A525F Build/TP1A.220624.014; wv) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Version/4.0 Chrome/130.0.6723.102 Mobile Safari/537.36")
WV_TG = WV + " Telegram-Android/11.4.2 (Samsung SM-A525F; Android 13; SDK 33; AVERAGE)"
MODEL = "SM-A155F"
_IP = {"n": 10}
TG = []
_asl_tg = main._send_telegram
main._send_telegram = lambda text, company_id=None: TG.append((text, company_id))


def mijoz(ua=CHROME):
    """TestClient — cookie siz (brauzer saytni «unutgan»), o'z ulanish manzili bilan."""
    _IP["n"] += 1
    try:
        c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False, client=(f"203.0.113.{_IP['n']}", 50000))
    except TypeError:
        c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    c.headers["user-agent"] = ua
    return c


s = SessionLocal()
if not s.query(Company).filter(Company.id == 2).first():
    s.add(Company(id=2, name="Ikkinchi Korxona", code="IKKINCHI-258"))
    s.commit()
with contextlib.redirect_stdout(_quiet):
    auth.create_user(s, "q_admin", "Parol123!", UserRole.ADMIN, "Q admin", company_id=1)
    auth.create_user(s, "q_b", "Parol123!", UserRole.ADMIN, "B admin", company_id=2)
s.commit()
KOD1 = s.query(Company).filter(Company.id == 1).first().code or ""
KOD2 = "IKKINCHI-258"
s.close()
A = mijoz()
B = mijoz()
_la = [A.post("/login", data={"username": "q_admin", "password": "Parol123!"}, follow_redirects=False).status_code,
       B.post("/login", data={"username": "q_b", "password": "Parol123!"}, follow_redirects=False).status_code]


def hodim(nom, tel, pin, klient=None, oz_pin=True):
    k = klient or A
    eid = js(k.post("/api/employees", json={"name": nom, "position": "Kesuvchi", "pay_type": "fixed",
                                            "fixed_amount": 5_000_000})).get("id")
    k.post(f"/api/employees/{eid}/set-login", data={"phone": tel, "pin": pin})
    if oz_pin:
        s = SessionLocal()
        s.query(Employee).filter(Employee.id == eid).update({"pin_vaqtinchalik": False}, synchronize_session=False)
        s.commit()
        s.close()
    return eid


def kir(c, tel, pin, model=MODEL, kod=None):
    d = {"phone": tel, "pin": pin, "korxona": KOD1 if kod is None else kod}
    if model is not None:
        d["qurilma_model"] = model
    return c.post("/hodim/login", data=d, follow_redirects=False)


def holat(c):
    r = c.get("/api/hodim/qurilma-holati")
    return js(r).get("holat") if r.status_code == 200 else r.status_code


def ruxsat(eid, klient=None):
    k = klient or A
    kal = next((x.get("kalit") for x in (js(k.get("/api/admin/qurilma-sorovlari")) or []) if x.get("employee_id") == eid), None)
    return k.post(f"/api/employees/{eid}/qurilma/ruxsat", json={"kalit": kal or ""}).status_code


def emp(eid):
    s = SessionLocal()
    try:
        e = s.query(Employee).filter(Employee.id == eid).first()
        return {k: getattr(e, k, None) for k in ("qurilma_hash", "qurilma_nomi", "qurilma_vaqti", "qurilma_sorov_hash",
                                                  "qurilma_sorov_nomi")}
    finally:
        s.close()


def jurnal(eid, amal):
    s = SessionLocal()
    try:
        return s.query(ActivityLog).filter(ActivityLog.entity_type == "employee", ActivityLog.entity_id == eid,
                                           ActivityLog.action == amal).count()
    finally:
        s.close()


def sessiyalar(eid):
    s = SessionLocal()
    try:
        return s.query(EmployeeSession).filter(EmployeeSession.employee_id == eid).count()
    finally:
        s.close()


def kalit_hash(c):
    k = next((ck.value for ck in c.cookies.jar if ck.name == "emp_qurilma"), None)
    return auth.qurilma_hash_ol(k) if k else None


def tayyor_hodim(nom, tel, ua=CHROME, model=MODEL, klient=None, kod=None):
    """Hodim + birinchi telefon (admin ruxsati bilan) — panel «tayyor». (eid, telefon klienti)"""
    eid = hodim(nom, tel, "4826", klient=klient)
    h = mijoz(ua)
    kir(h, tel, "4826", model=model, kod=kod)
    ruxsat(eid, klient=klient)
    return eid, h


E0 = hodim("Nol", "+998901580000", "4826")
check("0 adminlar kirdi (302 ×2), 1-korxona kodi bor; yangi funksiya bor (asl kodda yo'q — yiqiladi)",
      _la == [302, 302] and bool(KOD1) and callable(getattr(crud, "hodim_qurilma_ozi", None)), (_la, KOD1))

# ══════════════════════════════════════════════════════════════
section("A. O'sha telefon — brauzer saytni unutgan")
# ══════════════════════════════════════════════════════════════
E1, H1 = tayyor_hodim("Ulug'bek", "+998901580001")
_e0 = emp(E1)
check("A0 birinchi telefon — admin ruxsati bilan (so'rov 1, nom «Android · SM-A155F · Chrome»), panel «tayyor»",
      holat(H1) == "tayyor" and _e0["qurilma_nomi"] == "Android · SM-A155F · Chrome" and jurnal(E1, "qurilma_sorov") == 1
      and jurnal(E1, "qurilma_ruxsat") == 1, (holat(H1), _e0))
_s = SessionLocal()
_s.query(Employee).filter(Employee.id == E1).update({"qurilma_vaqti": _e0["qurilma_vaqti"].replace(year=2025)},
                                                     synchronize_session=False)
_s.commit()
_s.close()
_e0 = emp(E1)
TG.clear()
H1b = mijoz(CHROME)                       # o'sha telefon, o'sha brauzer — cookie lar yo'qolgan
_r = kir(H1b, "+998901580001", "4826")
_e1 = emp(E1)
check("A1 o'sha telefon (o'sha model va brauzer) cookie siz to'g'ri PIN bilan → /hodim, holat «tayyor» (ruxsat kutmaydi)",
      _r.status_code == 302 and _r.headers.get("location") == "/hodim" and holat(H1b) == "tayyor", (_r.status_code, holat(H1b)))
check("A2 so'rov YO'Q: kutayotgan so'rov bo'sh, jurnalda yangi «qurilma_sorov» yo'q, admin ro'yxatida yo'q",
      _e1["qurilma_sorov_hash"] is None and jurnal(E1, "qurilma_sorov") == 1
      and not any(x.get("employee_id") == E1 for x in js(A.get("/api/admin/qurilma-sorovlari")) or []), _e1)
check("A3 bazada telefon kaliti — YANGI brauzer kalitining xeshi; nom o'zgarmadi; vaqt yangilandi (2025 → bugun)",
      _e1["qurilma_hash"] == kalit_hash(H1b) and _e1["qurilma_hash"] != _e0["qurilma_hash"]
      and _e1["qurilma_nomi"] == _e0["qurilma_nomi"] and _e1["qurilma_vaqti"] is not None
      and _e0["qurilma_vaqti"].year == 2025 and _e1["qurilma_vaqti"].year >= 2026, (_e0, _e1))
check("A4 Telegram: BITTA xabar — «o'sha telefondan qayta kirdi», korxonaga, ism va telefon nomi, «Telefonni uzish» yo'li; "
      "«yangi telefondan kirmoqchi» YO'Q",
      len(TG) == 1 and TG[0][1] == 1 and "o'sha telefondan qayta kirdi" in TG[0][0] and "Ulug'bek" in TG[0][0]
      and "Android · SM-A155F · Chrome" in TG[0][0] and "Telefonni uzish" in TG[0][0] and "yangi PIN bering" in TG[0][0]
      and "yangi telefondan kirmoqchi" not in TG[0][0], TG)
check("A5 jurnalda «qurilma_qayta» (1 ta) — hodim nomidan, yozuv nomi «Ism: telefon»",
      jurnal(E1, "qurilma_qayta") == 1, jurnal(E1, "qurilma_qayta"))
_s = SessionLocal()
_al = _s.query(ActivityLog).filter(ActivityLog.entity_id == E1, ActivityLog.action == "qurilma_qayta").first()
_s.close()
check("A5b jurnal yozuvi: performed_by — hodim, entity_label — «Ulug'bek: Android · SM-A155F · Chrome», korxona 1",
      _al is not None and _al.performed_by == "Ulug'bek" and _al.entity_label == "Ulug'bek: Android · SM-A155F · Chrome"
      and _al.company_id == 1, _al and (_al.performed_by, _al.entity_label, _al.company_id))
check("A6 eski kalitli brauzer sessiyasi yopildi (yagona telefon): eski brauzer holati — sessiya yo'q; bazada 1 sessiya",
      holat(H1) == 401 or holat(H1) in (None, "rad"), (holat(H1), sessiyalar(E1)))
check("A6b bazada faqat yangi kalit sessiyasi qoldi (eski kalit sessiyasi o'chirildi)", sessiyalar(E1) == 1, sessiyalar(E1))
_ro = H1b.get("/api/hodim/oylik")
check("A7 hodim API (oylik) — 200 (panel ishlaydi)", _ro.status_code == 200, (_ro.status_code, js(_ro)))
TG.clear()
_q = []
for i in range(4):                        # 3–4 kunda bir — bir necha marta takrorlansa ham so'rov yo'q
    h = mijoz(CHROME)
    kir(h, "+998901580001", "4826")
    _q.append(holat(h))
check("A8 4 marta ketma-ket (har biri cookie siz) — hammasi «tayyor», so'rov 1 (dastlabki) qoldi, Telegram faqat «qayta kirdi» ×4",
      _q == ["tayyor"] * 4 and jurnal(E1, "qurilma_sorov") == 1 and len(TG) == 4
      and all("qayta kirdi" in t for t, _ in TG), (_q, jurnal(E1, "qurilma_sorov"), [t[:40] for t, _ in TG]))
TG.clear()
H1c = mijoz(CHROME_YANGI)                 # Chrome yangilangan (satrda versiya boshqa) — nom bir xil
kir(H1c, "+998901580001", "4826")
check("A9 Chrome yangilangan (versiya boshqa, nom o'sha) — «tayyor», so'rov yo'q",
      holat(H1c) == "tayyor" and jurnal(E1, "qurilma_sorov") == 1 and len(TG) == 1, (holat(H1c), TG))
TG.clear()
_rr = kir(H1c, "+998901580001", "4826")
check("A10 o'sha brauzer (cookie bor) qayta kirsa — avvalgidek, xabar YO'Q, jurnal yozuvi qo'shilmaydi",
      _rr.status_code == 302 and holat(H1c) == "tayyor" and TG == [] and jurnal(E1, "qurilma_qayta") == 6,
      (_rr.status_code, TG, jurnal(E1, "qurilma_qayta")))

# ══════════════════════════════════════════════════════════════
section("B. Avvalgidek so'raladiganlar")
# ══════════════════════════════════════════════════════════════
E2, H2 = tayyor_hodim("Jurabek", "+998901580002")
_h_eski = emp(E2)["qurilma_hash"]
TG.clear()
H = mijoz(CHROME)
kir(H, "+998901580002", "4826", model="SM-A346E")
_e = emp(E2)
check("B1 BOSHQA model — so'rov («kutilmoqda»), «yangi telefondan kirmoqchi» xabari, bog'langan telefon o'zgarmadi",
      holat(H) == "kutilmoqda" and _e["qurilma_hash"] == _h_eski and _e["qurilma_sorov_nomi"] == "Android · SM-A346E · Chrome"
      and len(TG) == 1 and "yangi telefondan kirmoqchi" in TG[0][0] and holat(H2) == "tayyor", (holat(H), _e, TG))
E3, H3 = tayyor_hodim("Uch", "+998901580003")
TG.clear()
H = mijoz(SAMSUNG)
kir(H, "+998901580003", "4826")
check("B2 o'sha model, BOSHQA brauzer (Samsung Internet) — so'rov", holat(H) == "kutilmoqda" and len(TG) == 1
      and "kirmoqchi" in TG[0][0], (holat(H), TG))
E4, H4 = tayyor_hodim("To'rt", "+998901580004", model="")
TG.clear()
H = mijoz(CHROME)
kir(H, "+998901580004", "4826", model="")
_e = emp(E4)
check("B3 model NOMA'LUM (yangi Chrome «K», sahifa modeli yo'q) — nom «Android · Chrome» teng bo'lsa ham so'rov",
      _e["qurilma_nomi"] == "Android · Chrome" and holat(H) == "kutilmoqda" and len(TG) == 1, (_e, holat(H), TG))
E5, H5 = tayyor_hodim("Besh", "+998901580005", ua=IPHONE, model="")
TG.clear()
H = mijoz(IPHONE)
kir(H, "+998901580005", "4826", model="")
check("B4 iPhone (model yo'q) — so'rov", emp(E5)["qurilma_nomi"] == "iPhone · Safari" and holat(H) == "kutilmoqda" and len(TG) == 1,
      (emp(E5), holat(H)))
E6, H6 = tayyor_hodim("Olti", "+998901580006")
_ru = A.post(f"/api/employees/{E6}/qurilma/uzish")
TG.clear()
H = mijoz(CHROME)
kir(H, "+998901580006", "4826")
check("B5 admin «Telefonni uzish» dan keyin o'sha telefon — so'rov (uzish o'z kuchida)",
      _ru.status_code == 200 and emp(E6)["qurilma_hash"] is None and holat(H) == "kutilmoqda" and len(TG) == 1
      and "kirmoqchi" in TG[0][0], (_ru.status_code, emp(E6), holat(H)))
E7 = hodim("Yetti", "+998901580007", "4826")
TG.clear()
H = mijoz(CHROME)
kir(H, "+998901580007", "4826")
H = mijoz(CHROME)
kir(H, "+998901580007", "4826")
check("B6 hech qachon ruxsat berilmagan hodim — har yangi brauzer so'rov (o'z-o'zini tasdiqlamaydi), bog'langan telefon yo'q",
      holat(H) == "kutilmoqda" and emp(E7)["qurilma_hash"] is None and len(TG) == 2, (holat(H), emp(E7), len(TG)))
E8, H8 = tayyor_hodim("Sakkiz", "+998901580008")
_h8 = emp(E8)["qurilma_hash"]
TG.clear()
H = mijoz(CHROME)
_rx = kir(H, "+998901580008", "0000")
check("B7 noto'g'ri PIN (o'sha model) — kirilmaydi (200 xato sahifa), kalit / jurnal / xabar o'zgarmadi",
      _rx.status_code == 200 and "noto'g'ri" in _rx.text.replace("&#39;", "'") and emp(E8)["qurilma_hash"] == _h8
      and jurnal(E8, "qurilma_qayta") == 0 and TG == [], (_rx.status_code, TG))
TG.clear()
H = mijoz(CHROME)
kir(H, "+998901580008", "4826", model="sm-a155f")
check("B8 model harfi boshqa («sm-a155f») — nom AYNAN emas → so'rov", holat(H) == "kutilmoqda" and len(TG) == 1, (holat(H), TG))
E9, H9 = tayyor_hodim("To'qqiz", "+998901580009")
TG.clear()
H = mijoz(CHROME)
kir(H, "+998901580001", "4826")           # Ulug'bek raqami — boshqa hodim telefoni bilan emas; E9 ga ta'sir yo'q
check("B9 boshqa hodimning qayta kirishi E9 ga tegmaydi (E9 kaliti o'zgarmadi)", emp(E9)["qurilma_hash"] == kalit_hash(H9),
      emp(E9))

# ══════════════════════════════════════════════════════════════
section("C. Kutayotgan boshqa so'rov, vaqtinchalik PIN, boshqa korxona")
# ══════════════════════════════════════════════════════════════
E10, H10 = tayyor_hodim("O'n", "+998901580010")
X = mijoz(CHROME)
kir(X, "+998901580010", "4826", model="Redmi Note 12")    # boshqa telefon so'rovi kutmoqda
_es = emp(E10)
TG.clear()
H = mijoz(CHROME)
kir(H, "+998901580010", "4826")                          # o'sha (bog'langan) telefon qaytdi
_e = emp(E10)
check("C1 boshqa telefon so'rovi kutayotganda o'sha telefon cookie siz qaytsa — «tayyor»; kutayotgan so'rov SAQLANDI (o'sha nom, "
      "o'sha belgi); boshqa telefon hali «kutilmoqda»",
      holat(H) == "tayyor" and _e["qurilma_sorov_hash"] == _es["qurilma_sorov_hash"] and _e["qurilma_sorov_nomi"] ==
      "Android · Redmi Note 12 · Chrome" and holat(X) == "kutilmoqda" and len(TG) == 1 and "qayta kirdi" in TG[0][0], (_e, holat(X)))
E11 = hodim("O'n bir", "+998901580011", "4826", oz_pin=False)    # PIN — admin bergan (vaqtinchalik)
H = mijoz(CHROME)
kir(H, "+998901580011", "4826")
ruxsat(E11)
H = mijoz(CHROME)
kir(H, "+998901580011", "4826")
check("C2 PIN hali vaqtinchalik — o'sha telefon qaytsa holat «pin» (avval o'z PIN i; ruxsat so'ralmaydi)",
      holat(H) == "pin" and jurnal(E11, "qurilma_sorov") == 1 and jurnal(E11, "qurilma_qayta") == 1, (holat(H),))
E12, H12 = tayyor_hodim("Ikkinchi korxona", "+998901580012", klient=B, kod=KOD2)
TG.clear()
H = mijoz(CHROME)
kir(H, "+998901580012", "4826", kod=KOD2)
check("C3 2-korxona hodimi — o'sha telefon qayta kirdi, xabar O'Z korxonasiga (2)",
      holat(H) == "tayyor" and len(TG) == 1 and TG[0][1] == 2, (holat(H), TG))
_f = getattr(crud, "hodim_qurilma_ozi", None)
_s = SessionLocal()
_ee = _s.query(Employee).filter(Employee.id == E1).first()
_r1 = _f(_s, _ee, _ee.qurilma_hash, CHROME, MODEL) if _f else None
_r2 = _f(_s, _ee, "", CHROME, MODEL) if _f else None
_s.close()
check("C4 funksiya chegaralari: o'sha kalit (allaqachon bog'langan) — False; bo'sh kalit — False", (_r1, _r2) == (False, False),
      (_r1, _r2))

# ══════════════════════════════════════════════════════════════
section("D. Telefon nomi")
# ══════════════════════════════════════════════════════════════
_nom = crud.qurilma_nomi_yasash
check("D1 ilova ichidagi brauzer satri («SM-A525F Build/…; wv)») — model o'qiladi (ilgari «Android · Chrome»), brauzer — «ilova "
      "ichida» (Chrome EMAS); Telegram belgili satr — «Telegram ichida»",
      _nom(WV, "") == "Android · SM-A525F · ilova ichida" and _nom(WV_TG, "") == "Android · SM-A525F · Telegram ichida",
      (_nom(WV, ""), _nom(WV_TG, "")))
check("D2 eski nomlar o'zgarmagan: «Android 10; K» — model yo'q; sahifa modeli ustun; Samsung Internet; iPhone; «Build/» siz satr",
      _nom(CHROME, "") == "Android · Chrome" and _nom(CHROME, "Redmi Note 12") == "Android · Redmi Note 12 · Chrome"
      and _nom(IPHONE, "") == "iPhone · Safari"
      and _nom("Mozilla/5.0 (Linux; Android 13; SM-A525F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
               "") == "Android · SM-A525F · Chrome"
      and _nom("Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/25.0 "
               "Chrome/121.0.0.0 Mobile Safari/537.36", "") == "Android · SM-S918B · Samsung Internet",
      [_nom(CHROME, ""), _nom(IPHONE, "")])
check("D3 «wv» o'zi model emas («Android 10; wv)» — model yo'q, brauzer «ilova ichida»)",
      _nom("Mozilla/5.0 (Linux; Android 10; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/130.0 Mobile Safari/537.36",
           "") == "Android · ilova ichida", None)

# ══════════════════════════════════════════════════════════════
section("F. Mustaqil tekshiruv (review258) himoyalari")
# ══════════════════════════════════════════════════════════════
E20, H20 = tayyor_hodim("Yigirma", "+998901580020")
TG.clear()
G = mijoz(CHROME)
kir(G, "+998901580020", "4826", model="SM-A346E")          # birinchi taxmin — so'rov + xabar
_g = [holat(G)]
for _m in ("SM-A156B", MODEL):                             # keyingi taxminlar (o'sha brauzer) — to'g'ri modelda ham bog'lanmaydi
    kir(G, "+998901580020", "4826", model=_m)
    _g.append(holat(G))
check("F1 shu brauzer BOSHQA nom bilan ruxsat kutayotgan bo'lsa — to'g'ri modelni yuborsa ham bog'lanmaydi («kutilmoqda»); bog'langan "
      "telefon o'zgarmadi; xabar 1 (birinchi so'rov)",
      _g == ["kutilmoqda"] * 3 and emp(E20)["qurilma_hash"] == kalit_hash(H20) and jurnal(E20, "qurilma_qayta") == 0
      and len(TG) == 1 and "kirmoqchi" in TG[0][0], (_g, len(TG)))
E21, H21 = tayyor_hodim("Yigirma bir", "+998901580021")
G = mijoz(CHROME)
kir(G, "+998901580021", "4826", model="")                  # model kelmagan so'rov — admin RAD etadi
_kal = next((x.get("kalit") for x in js(A.get("/api/admin/qurilma-sorovlari")) if x.get("employee_id") == E21), "")
_rr = A.post(f"/api/employees/{E21}/qurilma/rad", json={"kalit": _kal})
TG.clear()
kir(G, "+998901580021", "4826")                            # o'sha (rad etilgan) brauzer endi modelni yuboradi
H = mijoz(CHROME)
kir(H, "+998901580021", "4826")                            # yana bir cookie siz brauzer, o'sha model
check("F6 admin rad etgandan keyin — o'sha model bilan ham avtomatik bog'lanmaydi (so'rov), keyingi admin ruxsatigacha",
      _rr.status_code == 200 and holat(G) in ("kutilmoqda", "rad") and holat(H) == "kutilmoqda" and jurnal(E21, "qurilma_qayta") == 0
      and emp(E21)["qurilma_hash"] == kalit_hash(H21), (_rr.status_code, holat(G), holat(H), jurnal(E21, "qurilma_qayta")))
ruxsat(E21)
H = mijoz(CHROME)
kir(H, "+998901580021", "4826")
check("F6b admin yana ruxsat bergach — keyingi «unutish» yana avtomatik («tayyor», qurilma_qayta 1)",
      holat(H) == "tayyor" and jurnal(E21, "qurilma_qayta") == 1, (holat(H), jurnal(E21, "qurilma_qayta")))
E22, H22 = tayyor_hodim("Yigirma ikki", "+998901580022")
_kalit = auth.yangi_qurilma_kaliti()
_s = SessionLocal()
_ee = _s.query(Employee).filter(Employee.id == E22).first()
_ee.qurilma_sorov_hash, _ee.qurilma_sorov_nomi = auth.qurilma_hash_ol(_kalit), _ee.qurilma_nomi   # yangilanishdan oldingi so'rov
_s.commit()
_s.close()
G = mijoz(CHROME)
G.cookies.set("emp_qurilma", _kalit, domain=next((ck.domain for ck in A.cookies.jar), "testserver.local"), path="/")
TG.clear()
kir(G, "+998901580022", "4826")
_e = emp(E22)
check("F7 shu brauzerning O'SHA nomli eski so'rovi (yangilanishdan oldin qolgan) — bog'lanadi va so'rov tozalanadi (admin ro'yxatida yo'q)",
      holat(G) == "tayyor" and _e["qurilma_hash"] == auth.qurilma_hash_ol(_kalit) and _e["qurilma_sorov_hash"] is None
      and _e["qurilma_sorov_nomi"] is None and not any(x.get("employee_id") == E22 for x in js(A.get("/api/admin/qurilma-sorovlari")))
      and len(TG) == 1 and "qayta kirdi" in TG[0][0], (holat(G), _e, TG))
E23, H23 = tayyor_hodim("Yigirma uch", "+998901580023")
_f = getattr(crud, "hodim_qurilma_ozi", None) or (lambda *a, **k: None)      # asl kodda yo'q — yiqiladi, qulamaydi
_s1, _s2 = SessionLocal(), SessionLocal()
_e1o = _s1.query(Employee).filter(Employee.id == E23).first()
_e2o = _s2.query(Employee).filter(Employee.id == E23).first()
_ = (_e1o.qurilma_nomi, _e2o.qurilma_nomi)
_hn = auth.qurilma_hash_ol(auth.yangi_qurilma_kaliti())
_t1 = _f(_s1, _e1o, _hn, CHROME, MODEL)
_t2 = _f(_s2, _e2o, _hn, CHROME, MODEL)                    # ikki marta bosish: ikkinchisi eskirgan obyekt bilan
_h2 = _e2o.qurilma_hash
_s1.close()
_s2.close()
check("F5 ikki marta bosish: birinchisi True, ikkinchisi (eskirgan obyekt) False va obyekt yangi kalitni ko'radi (kirish yo'li so'rov "
      "yaratmaydi); jurnalda «qurilma_qayta» 1",
      (_t1, _t2) == (True, False) and _h2 == _hn and jurnal(E23, "qurilma_qayta") == 1, (_t1, _t2, _h2 == _hn))
_s1, _s2 = SessionLocal(), SessionLocal()
_e1o = _s1.query(Employee).filter(Employee.id == E23).first()
_ = _e1o.qurilma_nomi
_e2o = _s2.query(Employee).filter(Employee.id == E23).first()
_e2o.qurilma_hash, _e2o.qurilma_nomi = "b" * 64, "Android · SM-S918B · Chrome"   # shu orada admin boshqa telefonga ruxsat berdi
_s2.commit()
_t3 = _f(_s1, _e1o, auth.qurilma_hash_ol(auth.yangi_qurilma_kaliti()), CHROME, MODEL)
_s1.close()
_s2.close()
_e = emp(E23)
check("F5b admin ruxsati bilan poyga (eskirgan obyekt) — False; bazada admin bergan telefon (kalit va nom) o'zgarmadi",
      _t3 is False and _e["qurilma_hash"] == "b" * 64 and _e["qurilma_nomi"] == "Android · SM-S918B · Chrome", (_t3, _e))
E24, H24 = tayyor_hodim("Yigirma to'rt", "+998901580024")
TG.clear()
H = mijoz("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36")
kir(H, "+998901580024", "4826")                            # kompyuter, o'sha model yozilgan
check("F8 tizim boshqa (Windows, o'sha model va brauzer) — so'rov", holat(H) == "kutilmoqda" and len(TG) == 1, (holat(H), TG))
WV1, HW = tayyor_hodim("Yigirma besh", "+998901580025", ua=WV, model="")
TG.clear()
H = mijoz(CHROME)
kir(H, "+998901580025", "4826", model="SM-A525F")          # o'sha telefon, lekin Chrome (ilova ichidagi brauzer bog'langan)
check("F3 ilova ichidagi brauzer bog'langan, o'sha telefonning Chrome'i — so'rov (bir-birini jim uzmaydi)",
      emp(WV1)["qurilma_nomi"] == "Android · SM-A525F · ilova ichida" and holat(H) == "kutilmoqda" and holat(HW) == "tayyor",
      (emp(WV1), holat(H), holat(HW)))

# ══════════════════════════════════════════════════════════════
section("E. Statik")
# ══════════════════════════════════════════════════════════════
_kpi = open(os.path.join(ROOT, "templates", "kpi.html"), encoding="utf-8").read()
check("E1 «Telefonni uzish» oynasi: uzish qachon kerakligi va «kira olmasa — yangi PIN bering (telefon bog'liq qoladi)» eslatmasi",
      "Uzish — faqat telefon yo'qolgan, almashgan yoki begona odam kirgan bo'lsa" in _kpi
      and "uzmang, shu oynada yangi PIN bering (telefon bog'liq qoladi)" in _kpi, None)
_yor = getattr(crud, "_AMAL_YORLIQ", None) or getattr(crud, "AMAL_YORLIQLARI", None)
_crud_matn = open(os.path.join(ROOT, "crud.py"), encoding="utf-8").read()
check("E2 jurnal yorlig'i «qurilma_qayta» — «o'sha telefondan qayta kirdi (ruxsat so'ralmadi)»",
      "\"qurilma_qayta\": (\"📱\", \"— o'sha telefondan qayta kirdi (ruxsat so'ralmadi)\", \"Hodim telefoni\")" in _crud_matn, None)
_main_matn = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
_i = _main_matn.find("def hodim_login_submit")
_blok = _main_matn[_i:_main_matn.find("\ndef ", _i + 10)]
check("E3 kirish yo'lida tartib: avval `hodim_qurilma_ozi`, aks holda `hodim_qurilma_sorovi` (bitta tarmoq)",
      _blok.find("crud.hodim_qurilma_ozi(") > 0 and _blok.find("crud.hodim_qurilma_ozi(") < _blok.find("crud.hodim_qurilma_sorovi(")
      and _blok.count("crud.hodim_qurilma_sorovi(") == 1, None)
main._send_telegram = _asl_tg

print("\n" + "=" * 70)
print(f"{REJIM}NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
