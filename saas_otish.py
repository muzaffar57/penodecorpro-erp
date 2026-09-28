"""
saas_otish.py — `main` (eski, bitta korxonali) bazaga ko'p korxonali (SaaS) kod BIRINCHI marta tushganda —
ilova ishga tushishida, `init_database()` dan OLDIN, `saas_migration` to'lqinlarini AVTOMATIK bajaradi.

NIMA UCHUN KERAK (kech108, K108-1 — O'LCHANGAN, `main` zaxirasining lokal nusxasi, HAQIQIY PostgreSQL 16)
------------------------------------------------------------------------------------------------------
SaaS to'lqinlarisiz `main` bazasida `staging` kodi IMPORTDA yiqiladi (`auth.create_default_admin` —
`users.company_id` yo'q): Railway'da sayt ochilmasdi; undan OLDIN 5 ta startup migratsiyasi QISMAN bajarilib
ulgurardi (narx muzlatish 89 + 19, brak belgisi 123, FK / indekslar). To'lqinlar (W1–W6, W2B, W3B, M1KOD)
staging kodidan OLDIN bajarilsa — 0 xato, ikkinchi ishga tushish o'zgarishsiz (kech108 simulyatsiyasi).
Egasi dasturchi emas: ikki bosqichli (avval to'lqinlar sahifasi, keyin kod) yuklash o'rniga — BITTA yuklash.

QANDAY ISHLAYDI (texnik qaror — Claude, kech109)
-------------------------------------------------
  1. `otish_kerakmi(engine)` — faqat PostgreSQL; `users` jadvali BOR va to'lqin jadvallaridan birortasida
     `company_id` YO'Q bo'lsa — eski baza. Toza baza (hali jadval yo'q), `staging` va yangi o'rnatish — tegilmaydi.
  2. SINOV (butun zanjir BITTA tranzaksiyada, har qadam — savepoint): `companies` (id=1) + W1 … W6 + M1KOD
     HAQIQATDAN bajariladi, `verify_tables` tekshiriladi, keyin HAMMASI qaytarib olinadi. Biror qadam
     to'xtasa (NULL qoldi, yetim, takroriy qiymat, qulf) — HAQIQIY bosqich boshlanmaydi, baza O'ZGARMAYDI.
  3. HAQIQIY: xuddi shu tartib, har qadam O'Z tranzaksiyasida (`saas_migration.run_step` — sinalgan kod).
     Qadam xatosi — to'xtaydi; oldingi qadamlar saqlangan bo'lsa ham xavfsiz: har biri idempotent, eski kod
     ular bilan ishlaydi (vaqtinchalik DEFAULT 1), keyingi ishga tushish davom ettiradi.
  4. Xato bo'lsa — `RuntimeError` (ilova ishga tushmaydi, Railway loglarida aniq qadam va sabab): yarim
     sxemali ilova ishlab turgandan ko'ra to'xtagani xavfsiz.
`saas_migration.py` Python 3.12 sintaksisiga ega — faqat KERAK bo'lganda (eski baza) yuklanadi; bu modul 3.11
bilan ham ishlaydi (lokal testlar).
"""

from sqlalchemy import inspect as _sa_inspect, text

# `saas_migration.STEPS` dagi to'lqin tartibi (kech108 simulyatsiyasida sinalgan). TEKSHIRUV — `verify_tables`,
# M1KOD — `run_kod_migration` (alohida chaqiriladi). SINOV-TENANT — faqat staging, bu yerda YO'Q.
OTISH_TARTIBI = ("W1", "W2G1", "W2G2", "W2G3", "W2G4", "W2B", "W3", "W3B", "W4", "W5", "W6")

# To'lqinlar `company_id` qo'shadigan 25 jadval (`saas_migration.STEPS` "jadvallar") — aniqlash uchun
# (3.12 modulini yuklamasdan). `tools/test_saas_otish.py` ro'yxat STEPS bilan AYNAN ekanini tekshiradi.
TOLQIN_JADVALLARI = (
    "users",
    "inventory", "recipes", "suppliers", "projects",
    "masters", "master_gifts", "gift_periods", "employees",
    "cash_transactions", "recurring_obligations", "transport_expenses", "expense_transactions",
    "monthly_expenses", "company_settings", "activity_logs", "login_history",
    "orders", "order_items", "finished_products",
    "return_items", "inventory_movements", "inventory_receipts", "finished_product_sales",
    "finished_product_losses",
)

ASOSIY_KORXONA_ID = 1
ASOSIY_KORXONA_NOMI = "PenodecorPro"


def otish_kerakmi(engine) -> bool:
    """Eski (to'lqinlarsiz) PostgreSQL bazasimi. SQLite / toza baza / to'lqinlar bajarilgan baza — False."""
    if getattr(engine.dialect, "name", "") != "postgresql":
        return False
    with engine.connect() as c:
        ins = _sa_inspect(c)
        jadvallar = set(ins.get_table_names())
        if "users" not in jadvallar:
            return False
        for t in TOLQIN_JADVALLARI:
            if t not in jadvallar:
                continue
            if "company_id" not in {x["name"] for x in ins.get_columns(t)}:
                return True
    return False


class _SavepointUlanish:
    """Bitta haqiqiy ulanishning proksisi: `begin()` — savepoint, `close()` — hech narsa (tashqi tranzaksiya
    ochiq qoladi). `saas_migration` funksiyalari `engine.connect()` / `conn.begin()` / `commit` / `rollback`
    naqshini o'zgarishsiz ishlatadi."""

    def __init__(self, conn):
        self._c = conn

    def begin(self):
        return self._c.begin_nested()

    def close(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __getattr__(self, nom):
        return getattr(self._c, nom)


class _SinovMotori:
    """`engine` o'rniga — hamma `connect()` BITTA ulanishga (tashqi tranzaksiya ichida) qaytadi."""

    def __init__(self, conn):
        self._c = conn
        self.dialect = conn.dialect
        self.url = getattr(conn.engine, "url", None)

    def connect(self):
        return _SavepointUlanish(self._c)

    def begin(self):
        return self._c.begin_nested()


def _korxona_tayyorla(conn, chiqar) -> list:
    """`companies` jadvali (staging DDL) va asosiy korxona (id=1); id ketma-ketligi id=1 dan keyinga suriladi
    (aks holda platformadan birinchi "korxona qo'shish" — takroriy kalit)."""
    from production_models import Company
    amallar = []
    ins = _sa_inspect(conn)
    if "companies" not in set(ins.get_table_names()):
        Company.__table__.create(bind=conn, checkfirst=True)
        amallar.append("companies jadvali yaratildi")
    if not conn.execute(text("SELECT 1 FROM companies WHERE id = :i"), {"i": ASOSIY_KORXONA_ID}).scalar():
        conn.execute(Company.__table__.insert().values(id=ASOSIY_KORXONA_ID, name=ASOSIY_KORXONA_NOMI,
                                                       allow_negative_stock=False))
        amallar.append(f"companies id={ASOSIY_KORXONA_ID} ({ASOSIY_KORXONA_NOMI}) yaratildi")
    conn.execute(text("SELECT setval(pg_get_serial_sequence('companies', 'id'), "
                      "(SELECT MAX(id) FROM companies), true)"))
    for a in amallar:
        chiqar(f"   · {a}")
    return amallar


def _tekshiruv_xatolari(verify) -> list:
    """`saas_migration.verify_tables` natijasidagi to'xtatuvchi holatlar (NULL, yetim, ota bilan mos kelmaslik)."""
    xato = []
    for j in verify or []:
        if not j.get("mavjud", True):
            continue
        nom = j.get("jadval")
        if j.get("NULL_company_id"):
            xato.append(f"{nom}: company_id bo'sh {j.get('NULL_company_id')}")
        if j.get("yetim_company_id"):
            xato.append(f"{nom}: yetim company_id {j.get('yetim_company_id')}")
        for n in j.get("nomuvofiq") or []:
            xato.append(f"{nom}: ota bilan mos emas {n}")
    return xato


def _zanjir(motor, sm, chiqar, bosqich) -> dict:
    """W1 … W6 + TEKSHIRUV + M1KOD. Qaytaradi: {ok, qadam, xato, hisobotlar}."""
    hisobotlar = []

    def _natija(r):
        # SINOVDA qadamning "commit" i — savepoint (tashqi tranzaksiya oxirida hammasi qaytariladi)
        if bosqich == "SINOV" and not r.get("xato"):
            return "✅ o'tdi (savepoint — oxirida qaytariladi)"
        return r.get("natija")

    for k in OTISH_TARTIBI:
        r = sm.run_step(motor, k, dry_run=False)
        hisobotlar.append(r)
        chiqar(f"   {bosqich} {k}: {_natija(r)}")
        if r.get("xato"):
            return {"ok": False, "qadam": k, "xato": r.get("xato"), "hisobotlar": hisobotlar}
    v = sm.verify_tables(motor)
    vx = _tekshiruv_xatolari(v)
    chiqar(f"   {bosqich} TEKSHIRUV: {'OK' if not vx else '; '.join(vx)}")
    if vx:
        return {"ok": False, "qadam": "TEKSHIRUV", "xato": "; ".join(vx), "hisobotlar": hisobotlar}
    r = sm.run_kod_migration(motor, dry_run=False)
    hisobotlar.append(r)
    chiqar(f"   {bosqich} M1KOD: {_natija(r)}")
    if r.get("xato"):
        return {"ok": False, "qadam": "M1KOD", "xato": r.get("xato"), "hisobotlar": hisobotlar}
    return {"ok": True, "qadam": None, "xato": None, "hisobotlar": hisobotlar}


def otish(engine, sm=None, chiqar=print) -> dict:
    """Eski bazani to'lqinlardan o'tkazadi: SINOV (hammasi qaytariladi) → HAQIQIY. `sm` — `saas_migration`
    moduli (testda almashtiriladi). Qaytaradi: {ok, bosqich, qadam, xato}."""
    if sm is None:
        import saas_migration as sm  # noqa: F811 — 3.12 sintaksisi, faqat eski bazada yuklanadi
    chiqar("🔄 SaaS o'tishi: eski (bitta korxonali) baza aniqlandi — to'lqinlar staging kodidan OLDIN bajariladi")

    # 1) SINOV — bitta tranzaksiya, oxirida ROLLBACK
    conn = engine.connect()
    tashqi = conn.begin()
    try:
        _korxona_tayyorla(conn, chiqar)
        sinov = _zanjir(_SinovMotori(conn), sm, chiqar, "SINOV")
    except Exception as e:  # noqa: BLE001
        sinov = {"ok": False, "qadam": "SINOV", "xato": f"{type(e).__name__}: {e}"}
    finally:
        try:
            tashqi.rollback()
        finally:
            conn.close()
    if not sinov["ok"]:
        chiqar(f"⛔ SaaS o'tishi SINOVDA to'xtadi ({sinov['qadam']}): {sinov['xato']} — baza O'ZGARMADI")
        return {"ok": False, "bosqich": "sinov", "qadam": sinov["qadam"], "xato": sinov["xato"]}
    chiqar("✅ SaaS o'tishi SINOVI muvaffaqiyatli (hammasi qaytarib olindi) — HAQIQIY bosqich")

    # 2) HAQIQIY — har qadam o'z tranzaksiyasida
    with engine.begin() as c:
        _korxona_tayyorla(c, chiqar)
    haqiqiy = _zanjir(engine, sm, chiqar, "HAQIQIY")
    if not haqiqiy["ok"]:
        chiqar(f"⛔ SaaS o'tishi HAQIQIY bosqichda to'xtadi ({haqiqiy['qadam']}): {haqiqiy['xato']}")
        return {"ok": False, "bosqich": "haqiqiy", "qadam": haqiqiy["qadam"], "xato": haqiqiy["xato"]}
    chiqar("✅ SaaS o'tishi BAJARILDI: W1–W6, W2B, W3B, M1KOD — keyingi ishga tushishlarda tegilmaydi")
    return {"ok": True, "bosqich": "haqiqiy", "qadam": None, "xato": None}


def startup_otish(engine, chiqar=print) -> bool:
    """`main.py` — `init_database()` dan OLDIN. Kerak bo'lmasa — False (hech narsa qilinmaydi). Kerak bo'lsa va
    muvaffaqiyatsiz — RuntimeError (ilova ishga tushmaydi)."""
    if not otish_kerakmi(engine):
        return False
    natija = otish(engine, chiqar=chiqar)
    if not natija["ok"]:
        raise RuntimeError(
            f"SaaS o'tishi to'xtadi ({natija['bosqich']}, {natija['qadam']}): {natija['xato']}. "
            f"Ilova ATAYLAB ishga tushirilmadi — yarim sxemada ishlamasin.")
    return True
