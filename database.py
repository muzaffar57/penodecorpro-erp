import os
import datetime as _dt_modul     # kech106: tur tekshiruvi — HAQIQIY sinflar (testlar `database.datetime` ni almashtiradi)
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

# 2026-09-17 (audit topilmasi — jiddiy, keng tarqalgan xato tuzatildi):
# Bazadagi BARCHA datetime'lar (created_at, paid_at, completed_at va h.k.)
# doim datetime.utcnow() bilan, ya'ni UTC vaqtida saqlanadi — bu TO'G'RI va
# o'zgarishsiz qoladi. Lekin ko'plab hisobot/dashboard funksiyalarida
# "BUGUN"ning boshlanishini topish uchun to'g'ridan-to'g'ri
# `datetime.utcnow().replace(hour=0,...)` ishlatilgan edi — bu esa
# Toshkent (UTC+5) vaqti bilan ertalabki soat 00:00–04:59 oralig'idagi
# har qanday voqeani (to'lov, buyurtma yakunlanishi va h.k.) NOTO'G'RI
# ravishda "KECHAGI KUN"ga hisoblab qo'yardi — chunki o'sha payt UTC
# bo'yicha hali KECHAGI SANA edi. Quyidagi ikkita yordamchi funksiya —
# shu muammoning YAGONA, markazlashtirilgan yechimi: "bugun" TOSHKENT
# vaqti bo'yicha aniqlanadi, natija esa baza bilan solishtirish uchun
# UTC ko'rinishida qaytariladi.
TASHKENT_OFFSET = timedelta(hours=5)


def tashkent_today_start_utc() -> datetime:
    """Toshkent vaqti bo'yicha BUGUNNING boshlanishi (00:00), lekin UTC
    ko'rinishida qaytariladi — shuning uchun bazadagi datetime ustuni
    bilan TO'G'RIDAN-TO'G'RI solishtirish mumkin:
        Model.some_date >= tashkent_today_start_utc()
    "Hafta"/"oy" boshlanishini topish uchun ham shu qiymatdan
    boshlab hisoblash kerak (masalan `.replace(day=1)`), alohida
    UTC-asosli hisoblash EMAS."""
    tashkent_now = datetime.utcnow() + TASHKENT_OFFSET
    tashkent_midnight = tashkent_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return tashkent_midnight - TASHKENT_OFFSET


def tashkent_date(dt: datetime = None):
    """Berilgan (UTC, naive) datetime'ning Toshkent vaqti bo'yicha
    SANASINI (`date` obyekti) qaytaradi. `dt` berilmasa — hozirgi kun
    (Toshkent bo'yicha) qaytariladi. `.date() == today` ko'rinishidagi
    solishtirishlar uchun: `tashkent_date(p.paid_at) == tashkent_date()`."""
    if dt is None:
        dt = datetime.utcnow()
    return (dt + TASHKENT_OFFSET).date()


def tashkent_vaqt(dt: datetime = None) -> datetime:
    """kech106 (9 + 50-band B qismi; egasi qarori kech105 — "Toshkent vaqti bo'yicha"): KO'RINISH uchun Toshkent
    devor soati (naive datetime). `dt` — bazadagi UTC (naive) vaqt; berilmasa — HOZIR.

    PDF, Telegram xabari, sahifa (Jinja `|toshkent` filtri) va jurnal matnlaridagi sana-vaqt FAQAT shu orqali
    yoziladi. O'LCHANGAN (work/probe106.py, TZ=UTC — Railway kabi): ilgari `datetime.now()` (jarayon mintaqasi —
    Railway da UTC) va bazadagi UTC qiymatni to'g'ridan-to'g'ri `strftime` qilish Toshkent vaqtidan 5 soat orqada
    ko'rsatardi — Toshkent 01.10 01:30 dagi amal "30.09.2026 20:30" bo'lib chiqardi. Mintaqali (aware) qiymat avval
    UTC ga o'giriladi; faqat SANA (`date`) — kalendar kuni, siljitilmaydi. Natija bazaga YOZILMAYDI (saqlash — UTC)."""
    if dt is None:
        dt = datetime.utcnow()
    elif not isinstance(dt, _dt_modul.datetime):
        if isinstance(dt, _dt_modul.date):
            return datetime(dt.year, dt.month, dt.day)
        raise TypeError(f"tashkent_vaqt: datetime kerak, {type(dt).__name__} berildi")
    elif dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt + TASHKENT_OFFSET


# kech105 (9 + 50-band) — FOYDALANUVCHI QARORI (2026-09-28, "Toshkent vaqti bo'yicha"): hisobotlarning kun / oy /
# yil chegaralari TOSHKENT kalendari bo'yicha — kun 00:00 da almashadi (ilgari oylik / kunlik hisobot, KPI, xarajat
# ro'yxatlari UTC bo'yicha — Toshkent vaqti bilan 05:00 da almashardi: 1-oktyabr 01:30 dagi «Tayyor» sentyabrga
# tushardi, "Bugun" oynasi esa uni 1-oktyabr derdi). Bazadagi vaqtlar UTC (naive) — Toshkent davri [boshi, oxiri)
# UTC ko'rinishida olinadi. Faqat SANA kiritiladigan qiymatlar (xarajat / avans sanasi — yarim tun 00:00) o'z
# kunida qoladi: Toshkent D kuni = [D−1 19:00, D 19:00) UTC — D 00:00 shu oraliqda.
def tashkent_kun_oraligi(sana):
    """Toshkent kalendar kuni (`date`) → `(boshi, oxiri)` UTC (naive), oxiri KIRMAYDI."""
    boshi = datetime(sana.year, sana.month, sana.day) - TASHKENT_OFFSET
    return boshi, boshi + timedelta(days=1)


# kech119 (egasi QARORI 2026-10-01 «Shu kunlar bilan»): joriy (tugamagan) oy o'tgan oyning SHU KUNLARI bilan
# solishtiriladi — 1–N oktabr ↔ 1–N sentabr (ilgari 1 kunlik oktabr butun sentabr bilan: oy boshida doim «Daromad
# 100% kamaydi»). O'tgan oyning 1–N kunlik hisoboti — AYNAN oylik hisobot (`services.get_monthly_report`, uning
# hamma qismlari: buyurtmalar, sotuv, qaytarish, xarajat, transport, brak, KPI, hodim …) faqat davr oxiri N-kun
# oxirida: oylik hisobotning HAMMA oy chegaralari shu ikki yordamchidan (`tashkent_oy_oraligi` / `tashkent_oyida`)
# o'tadi, shuning uchun kesim bitta joyda. Oy darajasidagi yozuvlar (oylik shakl — arenda / elektr …, hodimning
# doimiy oyligi, oylik tuzatma) — butun oy uchun, ikkala oyda bir xil qoida.
# Kesim faqat `with tashkent_oy_kesimi(...)` bloki ichida va FAQAT o'sha yil / oy uchun (boshqa oylar — to'liq).
# `contextvars` — shu sinxron chaqiruv zanjiri ichida (o'rnatish va o'qish BITTA oqimda, blok tugashi bilan
# tiklanadi; `tenant_context.py` dagi muammo — qiymat so'rov qatlamlari ORASIDA o'tishi — bu yerda yo'q).
import contextlib as _contextlib_kesim
import contextvars as _contextvars_kesim

_OY_KESIMI = _contextvars_kesim.ContextVar("tashkent_oy_kesimi", default=None)


@_contextlib_kesim.contextmanager
def tashkent_oy_kesimi(yil, oy, kun):
    """Blok ichida Toshkent `yil` / `oy` oyi faqat 1..`kun` kunlari (davr oxiri — `kun`-kunning oxiri, Toshkent
    24:00). `kun` oy uzunligidan katta / teng — butun oy (kesim ta'sirsiz); `kun` < 1 — bo'sh davr."""
    _token = _OY_KESIMI.set((int(yil), int(oy), int(kun)))
    try:
        yield
    finally:
        _OY_KESIMI.reset(_token)


def tashkent_oy_oraligi(yil, oy):
    """Toshkent kalendar oyi → `(boshi, oxiri)` UTC (naive), oxiri KIRMAYDI. `tashkent_oy_kesimi` bloki ichida (shu oy
    uchun) oxiri — kesim kunining oxiri (oy oxiridan keyin emas)."""
    yil, oy = int(yil), int(oy)
    oxiri = datetime(yil + 1, 1, 1) if oy == 12 else datetime(yil, oy + 1, 1)
    boshi = datetime(yil, oy, 1) - TASHKENT_OFFSET
    oxiri = oxiri - TASHKENT_OFFSET
    _k = _OY_KESIMI.get()
    if _k is not None and _k[0] == yil and _k[1] == oy:
        oxiri = min(oxiri, boshi + timedelta(days=max(_k[2], 0)))
    return boshi, oxiri


def tashkent_yil_oraligi(yil):
    """Toshkent kalendar yili → `(boshi, oxiri)` UTC (naive), oxiri KIRMAYDI."""
    yil = int(yil)
    return datetime(yil, 1, 1) - TASHKENT_OFFSET, datetime(yil + 1, 1, 1) - TASHKENT_OFFSET


def tashkent_kunida(ustun, sana):
    """SQLAlchemy sharti: UTC ustun Toshkent `sana` kunida."""
    from sqlalchemy import and_
    boshi, oxiri = tashkent_kun_oraligi(sana)
    return and_(ustun >= boshi, ustun < oxiri)


def tashkent_oyida(ustun, yil, oy):
    """SQLAlchemy sharti: UTC ustun Toshkent `yil` / `oy` oyida (`extract('year') == … AND extract('month') == …`
    o'rniga — u UTC oyini olardi)."""
    from sqlalchemy import and_
    boshi, oxiri = tashkent_oy_oraligi(yil, oy)
    return and_(ustun >= boshi, ustun < oxiri)


def tashkent_yilida(ustun, yil):
    """SQLAlchemy sharti: UTC ustun Toshkent `yil` yilida."""
    from sqlalchemy import and_
    boshi, oxiri = tashkent_yil_oraligi(yil)
    return and_(ustun >= boshi, ustun < oxiri)

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./penodecor_erp.db")

# Railway postgres:// → postgresql+pg8000://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+pg8000://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+pg8000://", 1)

if "sqlite" in DATABASE_URL:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # 2026-09-20 — ULANISH HOVUZI SOZLAMASI (jonli xatolikdan keyin qo'shildi).
    #
    # MUAMMO: Railway'dagi PostgreSQL bir muddat ishlatilmagan ulanishlarni
    # o'zi yopadi. SQLAlchemy esa ulanishlarni hovuzda saqlaydi va keyingi
    # so'rovda ALLAQACHON O'LIK ulanishni uzatardi. Natijada so'rov
    # "pg8000.exceptions.InterfaceError: network error" bilan yiqilardi —
    # foydalanuvchi uchun bu tasodifiy 500 xatosi bo'lib ko'rinardi
    # (ko'pincha uzoq tanaffusdan keyingi BIRINCHI so'rovda, masalan
    # ertalabki loginda; sahifani yangilasa ishlab ketardi).
    #
    # YECHIM:
    #   pool_pre_ping — har ulanishdan OLDIN "tirikmisan?" deb tekshiradi;
    #                   o'lik bo'lsa jimgina yangisini oladi.
    #   pool_recycle  — 280 soniyadan eski ulanish majburan yangilanadi
    #                   (Railway va oldidagi proksilar odatda ~5 daqiqada uzadi).
    #   pool_size / max_overflow — bir vaqtda ochiladigan ulanishlar chegarasi.
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=280,
        pool_size=5,
        max_overflow=10,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ============================================================
# kech120 (E bosqichi, U-09) — YOZUV VERSIYASI: shu jarayondagi HAR QANDAY bazaga yozish hisoblagichi
# ============================================================
# O'LCHANGAN (`work/k127/tez.py`, 300 buyurtma, HAQIQIY PG 16): «Hisobotlar» sahifasi bir ochilishda oylik hisobotni
# 12 marta (bir xil oylar uchun) qayta hisoblaydi — serverda ~8 s; «Dashboard» — 4 marta, ~5,7 s. Sinov saytida (kam
# ma'lumot) har hisobot so'rovi 0,5–1,2 s. `services` dagi HISOBOT XOTIRASI natijani so'rovlar ORASIDA eslab qoladi va
# shu versiya o'zgarishi bilan (istalgan jadvalga istalgan yozuv) darhol eskiradi.
#
# Qoida (texnik — Claude): `SELECT` bilan boshlanmaydigan har bayonot (INSERT / UPDATE / DELETE / DDL …, CTE ham) — YOZUV
# deb olinadi (shubhada — yozuv: xotira faqat kamroq ishlaydi, hech qachon eski natija bermaydi). Yozuv bajarilganda
# versiya oshadi va ulanishga «shu tranzaksiyada yozdi» belgisi qo'yiladi; tranzaksiya yakunlanganda (commit YOKI
# rollback) — versiya YANA oshadi. Ikkinchi oshish poyga uchun: boshqa ulanish tranzaksiya OCHIQ paytida (yozuv hali
# ko'rinmas) hisoblagan natija commit dan keyin versiyasi eskirgan bo'lib qoladi. Hodisalar `Engine` SINFIGA ulanadi —
# jarayondagi HAMMA dvigatellar (asosiy, test, migratsiya) hisobga olinadi.
import threading as _threading_yv
from sqlalchemy import event as _event_yv
from sqlalchemy.engine import Engine as _Engine_yv

_YV_QULF = _threading_yv.Lock()
_YV = {"v": 0}
_YV_BELGI = "_kech120_yozdi"
_YV_OQISH = ("SELECT", "PRAGMA", "SHOW", "EXPLAIN")


def yozuv_versiyasi():
    """Shu jarayondagi yozuvlar hisoblagichi (har yozuv va har yozuvli tranzaksiya yakunida oshadi)."""
    return _YV["v"]


def _yv_osh():
    with _YV_QULF:
        _YV["v"] += 1


def yozuv_bayonotimi(statement):
    """Bayonot yozuvmi: `SELECT` / `PRAGMA` / `SHOW` / `EXPLAIN` (izoh va bo'shliqdan keyin) bilan boshlanmasa — HA."""
    s = (statement or "").lstrip()
    while s.startswith("--") or s.startswith("/*"):
        if s.startswith("--"):
            _n = s.find("\n")
            s = "" if _n < 0 else s[_n + 1:].lstrip()
        else:
            _n = s.find("*/")
            s = "" if _n < 0 else s[_n + 2:].lstrip()
    _b = s[:8].upper()
    return not any(_b.startswith(k) for k in _YV_OQISH)


def ulanish_yozganmi(conn):
    """Ulanish joriy tranzaksiyada yozganmi (`Connection.info` belgisi)."""
    try:
        return bool(conn.info.get(_YV_BELGI))
    except Exception:
        return True


@_event_yv.listens_for(_Engine_yv, "before_cursor_execute")
def _yv_bayonot(conn, cursor, statement, parameters, context, executemany):
    if yozuv_bayonotimi(statement):
        try:
            conn.info[_YV_BELGI] = True
        except Exception:
            pass
        _yv_osh()


def _yv_yakun(conn):
    try:
        _yozdi = conn.info.pop(_YV_BELGI, None)
    except Exception:
        _yozdi = True
    if _yozdi:
        _yv_osh()


_event_yv.listen(_Engine_yv, "commit", _yv_yakun)
_event_yv.listen(_Engine_yv, "rollback", _yv_yakun)


def _yv_qaytdi(dbapi_connection, connection_record):
    """Ulanish hovuzga qaytdi — belgi tozalanadi (yozuvli, lekin yakunlanmagan tranzaksiya hovuzda rollback qilinadi:
    ma'lumot o'zgarmagan; versiya baribir oshiriladi — ehtiyot)."""
    try:
        if connection_record.info.pop(_YV_BELGI, None):
            _yv_osh()
    except Exception:
        pass


try:
    from sqlalchemy.pool import Pool as _Pool_yv
    _event_yv.listen(_Pool_yv, "checkin", _yv_qaytdi)
except Exception:
    pass


# kech166 (zip 231c — sinov saytida JONLI tasdiqlandi 31.10, review231 №6; ESKI — `/api/rollar` da ham): so'rov tanasidagi juft
# bo'lmagan surrogat («\ud800») pg8000 da UTF-8 ga o'girilmaydi — xato bayonot YUBORILAYOTGAN paytda chiqadi, ulanish protokoli
# yarim holatda qoladi va hovuzga qaytgan ulanishda KEYINGI so'rovlar (boshqa foydalanuvchi / korxonaniki ham) 500 berardi
# (O'LCHANGAN `work/k231c/probe231c.py`, asl: [500, 500, 500, 200 …]). Yechim: bayonot paytidagi `UnicodeError` — ulanish
# «uzilgan» deb belgilanadi, SQLAlchemy uni hovuzdan chiqarib tashlaydi (keyingi so'rov yangi ulanish oladi).
def _unicode_ulanish_xatosi(ctx):
    try:
        if isinstance(ctx.original_exception, UnicodeError):
            ctx.is_disconnect = True
    except Exception:
        pass


_event_yv.listen(_Engine_yv, "handle_error", _unicode_ulanish_xatosi)

# 2026-09-19 — Faza 1: avtomatik tenant filtri (TENANT_FILTER=1 bo'lsa).
# Modul o'zi standart holatda O'CHIQ — yoqilmaguncha hech narsa o'zgarmaydi.
try:
    import tenant_context as _tc
    _tc.install(SessionLocal)
except Exception as _e:   # modul yo'q bo'lsa ilova avvalgidek ishlayveradi
    print(f"⚠ tenant_context o'rnatilmadi: {_e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def _sql_type_for_column(col, dialect=None):
    """SQLAlchemy ustun turini shu baza (Postgres / SQLite) uchun SQL turiga aylantiradi — AYNAN `create_all` yozadigan tur.

    kech144 (zip 172, N4 — O'LCHANGAN): ilgari bu yerda qo'lda jadval bor edi va birinchi bo'lib `isinstance(t, String)`
    tekshirilardi. SQLAlchemy da `Text` (va `Enum`, `UnicodeText`) — `String` ning BOLASI, shuning uchun HAR `Text` ustun
    `VARCHAR(255)` bo'lib qo'shilardi (`elif isinstance(t, Text)` ga hech qachon yetmasdi). Natija: production bazasida
    keyinroq qo'shilgan matn ustunlari (birinchisi `activity_logs.old_value` / `new_value`, 22.07) 255 belgi bilan
    cheklangan — 12.10 11:47 buyurtma tahririda «value too long for type character varying(255)» → 500, retsept tahriri
    saqlanmaydi, yuk xati bor buyurtmani o'chirish («yopish» nusxasi) yiqiladi. Yangi bazada esa (`create_all`) shu ustunlar
    TEXT — sinovlar va zaxira nusxalari xatoni hech qachon ko'rsatmagan. Shuningdek `Numeric` (o'lchamsiz) → NUMERIC(12,2),
    `Numeric(p, 0)` → NUMERIC(p,2), `BigInteger` → INTEGER bo'lardi.
    Endi tur DIALEKT kompilyatoridan olinadi — keyin qo'shilgan ustun yangi bazadagi bilan bir xil. Eski bazadagi farqlar —
    `sxema_kengaytir()` (ishga tushishda) va `sxema_farqlari()` («Tizim salomatligi»)."""
    try:
        return col.type.compile(dialect=dialect or engine.dialect)
    except Exception:            # noqa: BLE001 — kompilyator bilmagan tur: xavfsiz variant (avvalgidek)
        return "TEXT"


def sync_missing_columns():
    """Kod (models.py) bilan haqiqiy baza jadvallarini solishtiradi.

    Agar modelda bor, lekin bazada yo'q ustun topilsa — uni AVTOMATIK qo'shadi
    (faqat ADD COLUMN, hech qachon o'chirish yoki o'zgartirish qilmaydi).

    Xavfsizlik: faqat NULL bo'lishi mumkin bo'lgan (nullable) ustunlarni qo'shadi,
    chunki mavjud jadvalga NOT NULL ustun standart qiymatsiz qo'shib bo'lmaydi.
    Har bir ustun alohida try/except bilan o'ralgan — bittasi xato bersa ham,
    server ishga tushishda to'xtab qolmaydi.
    """
    from sqlalchemy import inspect, text
    from enum import Enum as _PyEnum144

    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
    except Exception as e:
        print(f"⚠️ Ustunlarni tekshirishda xato (o'tkazib yuborildi): {e}")
        return

    added = []
    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue  # Yangi jadval — create_all() allaqachon to'liq yaratgan
        try:
            existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
        except Exception as e:
            print(f"⚠️ '{table_name}' jadvalini tekshirishda xato: {e}")
            continue

        for col in table.columns:
            if col.name in existing_cols:
                continue
            if not col.nullable and col.default is None and col.server_default is None:
                # NOT NULL va standart qiymatsiz ustunni xavfsiz qo'sha olmaymiz — o'tkazib yuboramiz
                print(f"⚠️ '{table_name}.{col.name}' qo'lda qo'shilishi kerak (NOT NULL, standart qiymatsiz)")
                continue
            try:
                sql_type = _sql_type_for_column(col)
                default_clause = ""
                # MUHIM: standart qiymatni ham SQL darajasida yozamiz — aks holda
                # ESKI qatorlar bu ustunda NULL bo'lib qoladi (Python darajasidagi
                # "default=" faqat YANGI qatorlarga ta'sir qiladi, eskilarga emas).
                if col.default is not None and getattr(col.default, "is_scalar", False):
                    val = col.default.arg
                    if isinstance(val, bool):
                        default_clause = f" DEFAULT {'TRUE' if val else 'FALSE'}"
                    elif isinstance(val, (int, float)):
                        default_clause = f" DEFAULT {val}"
                    elif isinstance(val, _PyEnum144) and hasattr(col.type, "_db_value_for_elem"):
                        # kech144 (zip 172): Enum standarti — bazada saqlanadigan qiymat (a'zo NOMI, `create_all` dagi kabi);
                        # ilgari Python enum `str` emas edi — standartsiz qo'shilib, eski qatorlar NULL qolardi
                        escaped = str(col.type._db_value_for_elem(val)).replace("'", "''")
                        default_clause = f" DEFAULT '{escaped}'"
                    elif isinstance(val, str):
                        escaped = val.replace("'", "''")
                        default_clause = f" DEFAULT '{escaped}'"
                with engine.connect() as conn:
                    # kech144 (zip 172): PG dagi ENUM turi (`create_all` uni jadval bilan yaratadi) — yangi ustun uchun
                    # tur bazada bo'lmasa avval yaratiladi (aks holda ADD COLUMN «type does not exist» bilan yiqilardi).
                    if engine.dialect.name == "postgresql" and hasattr(col.type, "create") \
                            and getattr(col.type, "native_enum", False):
                        col.type.create(bind=conn, checkfirst=True)
                    conn.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {col.name} {sql_type}{default_clause}'))
                    conn.commit()
                added.append(f"{table_name}.{col.name}")
            except Exception as e:
                print(f"⚠️ '{table_name}.{col.name}' ustunini qo'shishda xato: {e}")

    if added:
        print(f"✅ Avtomatik qo'shilgan ustunlar: {', '.join(added)}")
    else:
        print("✅ Barcha ustunlar bazada mavjud — qo'shish shart emas")


# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# kech144 (zip 172, N4 — O'LCHANGAN) — BAZA TUZILISHI (SXEMA) ↔ KOD.
# `create_all` mavjud jadvalni, `sync_missing_columns` mavjud ustunni HECH QACHON o'zgartirmaydi. Shuning uchun uzoq
# yashagan bazada (production — iyundan beri) ustun turi kod bilan farq qilishi mumkin: eski `_sql_type_for_column`
# xatosi (Text → VARCHAR(255)), keyin kodda kengaytirilgan uzunlik, qo'lda qo'shilgan ustun. Sinovlar va zaxira nusxalari
# sxemani KODDAN yaratadi — farqni hech qachon ko'rmaydi (12.10 11:47 production xatosi shu bilan yashiringan edi).
#   `sxema_farqlari(conn)` — har model ustuni ↔ `information_schema.columns` (faqat o'qish; PostgreSQL).
#   `sxema_kengaytir()`    — ishga tushishda: faqat KENGAYTIRISH (VARCHAR(n) → TEXT / VARCHAR(m > n), NUMERIC aniqligi,
#                            SMALLINT → INTEGER → BIGINT, REAL → DOUBLE PRECISION) — mavjud qiymat O'ZGARMAYDI, har ustun
#                            alohida tranzaksiyada, `lock_timeout` bilan; ustunga izoh (COMMENT) yoziladi — qayta ishga
#                            tushishdan keyin ham «Tizim salomatligi» da ko'rinadi. Boshqa farqlar (tur almashishi, NOT NULL,
#                            yo'q ustun) — FAQAT xabar («qo'lda»): ular ma'lumotni o'zgartirishi mumkin.
# SQLite ustun uzunligini / turini tekshirmaydi va ALTER COLUMN ni bilmaydi — u yerda tekshiruv o'tkazilmaydi.
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
SXEMA_IZOH_BELGI = "sxema_kengaytirildi"
SXEMA_ISHGA_TUSHISH = {"vaqt": None, "kengaytirildi": [], "xatolar": [], "qolda": 0}


def _sxema_kutilgan(col, dialekt_nomi="postgresql"):
    """Model ustuni → solishtirish shakli ({"tur": …, "uzunlik" / "aniqlik" / "kasr" / "nom"}); bilinmagan tur — None.
    Tartib MUHIM: `Enum` / `Text` — `String` ning bolalari, `Float` — `Numeric` ning, `BigInteger` / `SmallInteger` —
    `Integer` ning (N4 xatosining o'zi shu edi)."""
    from sqlalchemy import (String, Text, Integer, BigInteger, SmallInteger, Boolean, Float, Numeric, DateTime, Date,
                            Enum)
    t = col.type
    if isinstance(t, Enum):
        if getattr(t, "native_enum", True) and dialekt_nomi == "postgresql":
            return {"tur": "enum", "nom": t.name}
        return {"tur": "varchar", "uzunlik": t.length}
    if isinstance(t, Text):
        return {"tur": "text"}
    if isinstance(t, String):
        return {"tur": "varchar", "uzunlik": t.length}
    if isinstance(t, Boolean):
        return {"tur": "boolean"}
    if isinstance(t, BigInteger):
        return {"tur": "bigint"}
    if isinstance(t, SmallInteger):
        return {"tur": "smallint"}
    if isinstance(t, Integer):
        return {"tur": "integer"}
    if isinstance(t, Float):
        return {"tur": "float"}
    if isinstance(t, Numeric):
        if t.precision is None:
            return {"tur": "numeric", "aniqlik": None, "kasr": None}
        return {"tur": "numeric", "aniqlik": t.precision, "kasr": t.scale if t.scale is not None else 0}
    if isinstance(t, DateTime):
        return {"tur": "timestamptz" if getattr(t, "timezone", False) else "timestamp"}
    if isinstance(t, Date):
        return {"tur": "date"}
    return None


def _sxema_bazada(r) -> dict:
    """`information_schema.columns` qatori → solishtirish shakli."""
    dt = r["data_type"]
    if dt == "text":
        return {"tur": "text"}
    if dt == "character varying":
        return {"tur": "varchar", "uzunlik": r["character_maximum_length"]}
    if dt in ("integer", "bigint", "smallint", "boolean", "date", "real"):
        return {"tur": dt}
    if dt == "double precision":
        return {"tur": "float"}
    if dt == "numeric":
        return {"tur": "numeric", "aniqlik": r["numeric_precision"],
                "kasr": r["numeric_scale"] if r["numeric_precision"] is not None else None}
    if dt == "timestamp without time zone":
        return {"tur": "timestamp"}
    if dt == "timestamp with time zone":
        return {"tur": "timestamptz"}
    if dt == "USER-DEFINED":
        return {"tur": "enum", "nom": r["udt_name"]}
    return {"tur": dt}


def _sxema_matn(k) -> str:
    """Solishtirish shakli → odam o'qiydigan SQL turi."""
    if not k:
        return "—"
    t = k["tur"]
    if t == "varchar":
        return f"VARCHAR({k['uzunlik']})" if k.get("uzunlik") else "VARCHAR"
    if t == "numeric":
        return "NUMERIC" if k.get("aniqlik") is None else f"NUMERIC({k['aniqlik']},{k.get('kasr') or 0})"
    if t == "enum":
        return f"ENUM {k.get('nom')}"
    if t == "float":
        return "DOUBLE PRECISION"
    if t == "timestamptz":
        return "TIMESTAMP WITH TIME ZONE"
    if t == "yoq":
        return "yo'q"
    return str(t).upper()


_SXEMA_BUTUN = {"smallint": 1, "integer": 2, "bigint": 3}


def _sxema_solishtir(kut: dict, baz: dict):
    """→ None (mos — baza kod yozadigan HAR qiymatni sig'diradi) | ("kengaytirish", SQL turi) | ("qolda", izoh)."""
    kt, bt = kut["tur"], baz["tur"]
    qolda = ("qolda", "tur boshqa — avtomatik o'zgartirilmaydi (qiymatlar o'zgarishi mumkin)")
    if kt == "text":
        if bt == "text":
            return None
        return ("kengaytirish", "TEXT") if bt == "varchar" else qolda
    if kt == "varchar":
        if bt == "text":
            return None
        if bt != "varchar":
            return qolda
        ku, bu = kut.get("uzunlik"), baz.get("uzunlik")
        if bu is None or (ku is not None and bu >= ku):
            return None
        return ("kengaytirish", "VARCHAR" if ku is None else f"VARCHAR({ku})")
    if kt == "numeric":
        if bt != "numeric":
            return qolda
        kp, ks, bp, bs = kut.get("aniqlik"), kut.get("kasr"), baz.get("aniqlik"), baz.get("kasr")
        if bp is None:
            return None
        if kp is None:
            return ("kengaytirish", "NUMERIC")
        ks, bs = ks or 0, bs or 0
        if bs >= ks and (bp - bs) >= (kp - ks):
            return None
        butun, kasr = max(kp - ks, bp - bs), max(ks, bs)
        return ("kengaytirish", f"NUMERIC({butun + kasr},{kasr})")
    if kt in _SXEMA_BUTUN:
        if bt not in _SXEMA_BUTUN:
            return qolda
        return None if _SXEMA_BUTUN[bt] >= _SXEMA_BUTUN[kt] else ("kengaytirish", kt.upper())
    if kt == "float":
        if bt == "float":
            return None
        return ("kengaytirish", "DOUBLE PRECISION") if bt == "real" else qolda
    if kt == "enum":
        return None if (bt == "enum" and baz.get("nom") == kut.get("nom")) else qolda
    return None if kt == bt else qolda


def sxema_farqlari(conn=None) -> dict:
    """Har model ustunini bazadagi haqiqiy ustun bilan solishtiradi (FAQAT o'qish). PostgreSQL da:
    {"dialect", "tekshirildi": True, "jadvallar", "ustunlar", "farqlar": [{jadval, ustun, kodda, bazada, tur:
    "kengaytirish"|"qolda", sql, izoh}], "kengaytirilgan": [{jadval, ustun, izoh}] — ustun izohidan (`sxema_kengaytir`
    qachon nimani kengaytirgani)}. SQLite — {"tekshirildi": False, "izoh": …}."""
    from sqlalchemy import text
    dialekt = engine.dialect.name
    if dialekt != "postgresql":
        return {"dialect": dialekt, "tekshirildi": False,
                "izoh": "SQLite ustun uzunligi va turini tekshirmaydi — sxema tekshiruvi faqat PostgreSQL da"}
    egasi = conn is None
    if egasi:
        conn = engine.connect()
    try:
        qatorlar = conn.execute(text(
            "SELECT table_name, column_name, data_type, character_maximum_length, numeric_precision, numeric_scale, "
            "udt_name, is_nullable, column_default FROM information_schema.columns WHERE table_schema = current_schema()"
        )).mappings().all()
        izohlar = conn.execute(text(
            "SELECT c.relname AS jadval, a.attname AS ustun, d.description AS izoh FROM pg_catalog.pg_description d "
            "JOIN pg_catalog.pg_class c ON c.oid = d.objoid JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
            "JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid AND a.attnum = d.objsubid "
            "WHERE n.nspname = current_schema() AND d.objsubid > 0 AND d.description LIKE :b ORDER BY 1, 2"
        ), {"b": SXEMA_IZOH_BELGI + "%"}).mappings().all()
    finally:
        if egasi:
            conn.close()
    bazada = {}
    for r in qatorlar:
        bazada.setdefault(r["table_name"], {})[r["column_name"]] = r
    farqlar, jadvallar, ustunlar = [], 0, 0
    for jadval_nomi, jadval in sorted(Base.metadata.tables.items()):
        bj = bazada.get(jadval_nomi)
        if bj is None:
            continue                       # jadval yo'q — `create_all` yaratadi (bu yerga yetmaydi)
        jadvallar += 1
        for col in jadval.columns:
            kut = _sxema_kutilgan(col, dialekt)
            if kut is None:
                continue
            ustunlar += 1
            r = bj.get(col.name)
            if r is None:
                farqlar.append({"jadval": jadval_nomi, "ustun": col.name, "kodda": _sxema_matn(kut), "bazada": "yo'q",
                                "tur": "qolda", "sql": None, "izoh": "ustun bazada yo'q (avtomatik qo'shilmagan)"})
                continue
            baz = _sxema_bazada(r)
            natija = _sxema_solishtir(kut, baz)
            if natija is not None:
                farqlar.append({"jadval": jadval_nomi, "ustun": col.name, "kodda": _sxema_matn(kut),
                                "bazada": _sxema_matn(baz), "tur": natija[0],
                                "sql": natija[1] if natija[0] == "kengaytirish" else None,
                                "izoh": "kengaytiriladi (qiymatlar o'zgarmaydi)" if natija[0] == "kengaytirish"
                                else natija[1]})
            if col.nullable and not col.primary_key and r["is_nullable"] == "NO":
                farqlar.append({"jadval": jadval_nomi, "ustun": col.name, "kodda": "NULL bo'lishi mumkin",
                                "bazada": "NOT NULL", "tur": "qolda", "sql": None,
                                "izoh": "bazada majburiy — kod bo'sh qiymat yozsa saqlanmaydi"})
        modeldagi = {c.name for c in jadval.columns}
        for ustun, r in sorted(bj.items()):
            if ustun not in modeldagi and r["is_nullable"] == "NO" and r["column_default"] is None:
                farqlar.append({"jadval": jadval_nomi, "ustun": ustun, "kodda": "yo'q", "bazada": "NOT NULL",
                                "tur": "qolda", "sql": None,
                                "izoh": "kodda yo'q, bazada majburiy va standart qiymatsiz — yangi qator saqlanmaydi"})
    import re as _re144
    kengaytirilgan = []
    for x in izohlar:
        m = _re144.match(r"^" + SXEMA_IZOH_BELGI + r" (\S+): (.+?) -> (.+)$", x["izoh"] or "")
        kengaytirilgan.append({"jadval": x["jadval"], "ustun": x["ustun"], "vaqt": m.group(1) if m else None,
                               "oldin": m.group(2) if m else None, "keyin": m.group(3) if m else None,
                               "izoh": x["izoh"]})
    return {"dialect": dialekt, "tekshirildi": True, "jadvallar": jadvallar, "ustunlar": ustunlar, "farqlar": farqlar,
            "kengaytirilgan": kengaytirilgan}


def sxema_kengaytir() -> dict:
    """Ishga tushishda (`init_database`): `sxema_farqlari` dagi «kengaytirish» farqlarini tuzatadi. IDEMPOTENT — ikkinchi
    ishga tushishda farq yo'q, hech narsa qilinmaydi. Har ustun — alohida tranzaksiya (ALTER + COMMENT birga), xato bo'lsa
    o'sha ustun o'zgarmaydi (keyingi ishga tushishda qayta), ilova ishlayveradi. Natija — `SXEMA_ISHGA_TUSHISH`."""
    from sqlalchemy import text
    vaqt = _dt_modul.datetime.now(_dt_modul.timezone.utc).replace(microsecond=0).isoformat()
    natija = {"vaqt": vaqt, "kengaytirildi": [], "xatolar": [], "qolda": 0}
    if engine.dialect.name != "postgresql":
        SXEMA_ISHGA_TUSHISH.update(natija)
        return natija
    try:
        f = sxema_farqlari()
    except Exception as e:                 # noqa: BLE001 — tekshiruv xatosi ilovani to'xtatmaydi
        natija["xatolar"].append({"jadval": None, "ustun": None, "xato": str(e)[:300]})
        print(f"⚠️ Baza tuzilishi tekshirilmadi: {e}")
        SXEMA_ISHGA_TUSHISH.update(natija)
        return natija
    for x in f["farqlar"]:
        if x["tur"] != "kengaytirish":
            natija["qolda"] += 1
            continue
        jadval, ustun = x["jadval"], x["ustun"]
        izoh = f"{SXEMA_IZOH_BELGI} {vaqt}: {x['bazada']} -> {x['kodda']}".replace("'", "''")
        try:
            with engine.begin() as conn:
                conn.execute(text("SET LOCAL lock_timeout = '5s'"))
                conn.execute(text(f'ALTER TABLE "{jadval}" ALTER COLUMN "{ustun}" TYPE {x["sql"]}'))
                conn.execute(text(f"COMMENT ON COLUMN \"{jadval}\".\"{ustun}\" IS '{izoh}'"))
            natija["kengaytirildi"].append({"jadval": jadval, "ustun": ustun, "oldin": x["bazada"], "keyin": x["kodda"]})
            print(f"✓ Baza tuzilishi kengaytirildi: {jadval}.{ustun} {x['bazada']} → {x['kodda']}")
        except Exception as e:             # noqa: BLE001
            natija["xatolar"].append({"jadval": jadval, "ustun": ustun, "xato": str(e)[:300]})
            print(f"⚠️ {jadval}.{ustun} kengaytirilmadi ({x['bazada']} → {x['kodda']}): {e}")
    if natija["qolda"]:
        print(f"⚠️ Baza tuzilishida {natija['qolda']} ta farq qo'lda ko'rilishi kerak — «Tizim salomatligi»")
    SXEMA_ISHGA_TUSHISH.update(natija)
    return natija


def fix_recipe_name_column():
    """MAXSUS, BIR MARTALIK tuzatish: 'recipes.name' ustuni ilgari qattiq
    ENUM (faqat 'Kvars'/'Oq Marmar') edi, keyin kod darajasida erkin
    matn (String)ga o'zgartirilgan edi — lekin sync_missing_columns()
    hech qachon MAVJUD ustun turini o'zgartirmaydi (faqat yangi ustun
    qo'shadi), shuning uchun bazada bu ustun ESKI, cheklangan turida
    qolib ketgan bo'lishi mumkin edi. Bu funksiya buni xavfsiz, mavjud
    ma'lumotni SAQLAB QOLGAN holda VARCHAR ga o'tkazadi."""
    from sqlalchemy import inspect, text

    try:
        inspector = inspect(engine)
        if "recipes" not in inspector.get_table_names():
            return
        cols = {c["name"]: c for c in inspector.get_columns("recipes")}
        if "name" not in cols:
            return
        col_type = str(cols["name"]["type"]).upper()
        # Agar allaqachon VARCHAR/TEXT bo'lsa — hech narsa qilish shart emas
        if "VARCHAR" in col_type or "CHAR" in col_type or "TEXT" in col_type:
            return
        # ENUM (yoki shunga o'xshash cheklangan) tur — VARCHAR ga o'tkazamiz,
        # "USING name::text" orqali MAVJUD qiymatlar to'liq saqlanadi
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE recipes ALTER COLUMN name TYPE VARCHAR(100) USING name::text"))
            conn.commit()
        print("✅ 'recipes.name' ustuni VARCHAR turiga xavfsiz o'tkazildi (mavjud ma'lumot saqlanib qoldi)")
    except Exception as e:
        print(f"⚠️ 'recipes.name' ustunini tekshirishda xato (o'tkazib yuborildi): {e}")


def add_missing_indexes():
    """MAXSUS, BIR MARTALIK tuzatish: modelga index=True qo'shilgan
    ustunlar uchun, MAVJUD (ilgari yaratilgan) jadvallarda ham indeks
    yaratadi. sync_missing_columns() faqat YANGI USTUN qo'shadi, indeks
    yaratmaydi — shuning uchun bu alohida, xavfsiz qadam kerak.

    "CREATE INDEX IF NOT EXISTS" — Postgres'da xavfsiz, bir necha marta
    ishga tushirilsa ham xato bermaydi, jadvalni bloklamaydi."""
    from sqlalchemy import text

    indexes = [
        ("recipe_ingredients", "recipe_id"), ("recipe_ingredients", "inventory_id"),
        ("orders", "project_id"), ("orders", "master_id"),
        ("order_items", "order_id"), ("order_items", "recipe_id"),
        ("order_items", "penoplast_id"), ("order_items", "finished_product_id"),
        ("return_items", "order_id"),
        ("inventory_movements", "inventory_id"), ("inventory_movements", "order_id"),
        ("inventory_movements", "supplier_id"),
        ("inventory_purchases", "inventory_id"), ("inventory_purchases", "supplier_id"),
        ("advance_requests", "employee_id"), ("employee_advances", "employee_id"),
        ("supplier_payments", "supplier_id"),
        ("finished_products", "from_order_id"), ("finished_products", "penoplast_id"),
        ("finished_products", "recipe_id"),
        ("deliveries", "order_id"),
        ("delivery_items", "delivery_id"), ("delivery_items", "order_item_id"),
        ("payments", "order_id"), ("payments", "delivery_id"),
        ("order_attachments", "order_id"),
        ("orders", "yaratish_kaliti"),          # kech144 (zip 173): takror yaratishdan himoya kaliti
    ]

    from sqlalchemy import inspect
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    created = 0

    for table, col in indexes:
        if table not in existing_tables:
            continue
        idx_name = f"ix_{table}_{col}"
        try:
            with engine.connect() as conn:
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({col})"))
                conn.commit()
            created += 1
        except Exception as e:
            print(f"⚠️ Indeks yaratishda xato ({table}.{col}, o'tkazib yuborildi): {e}")

    if created:
        print(f"✅ {created} ta indeks tekshirildi/yaratildi (tezlik uchun)")


def init_database():
    Base.metadata.create_all(bind=engine)
    print("✅ Baza va jadvallar yaratildi!")
    sync_missing_columns()
    fix_recipe_name_column()
    # kech144 (zip 172, N4): mavjud ustunlar kod bilan solishtiriladi — faqat KENGAYTIRISH avtomatik (VARCHAR(255) → TEXT …)
    sxema_kengaytir()
    add_missing_indexes()

if __name__ == "__main__":
    init_database()
