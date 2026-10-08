"""
PenoDecorPro ERP — SaaS ko'p-tenantlilik (multi-tenant) migratsiyasi
====================================================================
HOZIRGI VAZIFASI (kech129, zip 153): migratsiya DVIGATELI — `saas_otish.py` uni
FAQAT eski (SaaS dan oldingi, bitta korxonali) PostgreSQL baza aniqlanganda,
ilova ishga tushishida chaqiradi. `staging` (2026-09) va `main` (2026-10-07)
allaqachon o'tkazilgan — ularda bu modul YUKLANMAYDI ham. Kerak bo'ladigan
yagona holat: 07.10 dan oldingi Railway zaxirasi (20.09, 07.10 19:36) tiklansa,
ilova uni shu dvigatel bilan o'zi o'tkazadi (kech109 mexanizmi).

OLIB TASHLANDI (kech129, O'LCHANGAN sabab bilan): `/saas-migratsiya` sahifasi va
`/api/saas-migration/*` (8 marshrut), ularning HTML qismi va «Sinov tenanti»
vositasi. Qorovul `auth.admin_only` edi — ISTALGAN korxonaning admini kirardi:
boshqa korxonalar nomi va tasdiq so'zlarini ko'rardi, HAQIQIY qadamni bajara
olardi (`W1` — `users.company_id` ga `DEFAULT 1` ni qaytarardi). Endi
dvigatelni faqat ilovaning o'zi (`saas_otish`) yoki serverdagi terminal
(pastdagi buyruqlar, DATABASE_URL bilan) ishlatadi — HTTP orqali YO'Q.

Har bir qadam bir yoki bir nechta jadvalga `company_id` ustunini
qo'shadi. Jadval bo'yicha ketma-ketlik (kelishilgan, o'zgarmaydi):

  A1  ustun qo'shish (NULL bo'lishi mumkin holatda)
  A2  qatorlarni sanash
  A3  backfill (company_id = 1)
  A4  NULL = 0 ekanini tekshirish        <-- TO'XTATUVCHI
  A5  har bir qiymat companies'da bor    <-- TO'XTATUVCHI
  A6  indeks
  A7  tashqi kalit (FK)
  A8  DEFAULT 1  (o'tish davri — eski kod hali company_id yubormaydi)
  A9  NOT NULL

XAVFSIZLIK:
  * Butun qadam BITTA tranzaksiya ichida — bir jadvalda xato bo'lsa,
    QOLGANLARI HAM qaytariladi (Postgres'da DDL tranzaksiyaga bo'ysunadi).
  * dry_run=True: barcha amallar HAQIQATDAN bajariladi, oxirida ROLLBACK.
    Ya'ni bu taxmin emas — haqiqiy sinov, lekin bazada iz qolmaydi.
  * Idempotent: qayta ishga tushirilsa "ALLAQACHON BOR" deb o'tkazadi.
  * lock_timeout: jadval qulfini 4 soniyadan ortiq kutmaydi (quyida sabab).
  * Faqat PostgreSQL. Haqiqiy rejim uchun tasdiq so'zi shart.
"""

from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import text

# ============================================================
# Sozlamalar
# ============================================================

DEFAULT_COMPANY_ID = 1
REF_TABLE = "companies"

LOCK_TIMEOUT = "4s"        # jadval qulfini shuncha kutamiz, keyin toza xato
STATEMENT_TIMEOUT = "60s"  # bitta so'rov shundan uzoq cho'zilmasin


# Qadamlar. Har birining O'Z tasdiq so'zi bor — bir qadamni bosaman deb
# boshqasini bosib yubormaslik uchun.
STEPS = [
    {
        "kalit": "W1",
        "nomi": "1-qadam — users (poydevor)",
        "izoh": "Butun tizimning tenant manbai.",
        "jadvallar": ["users"],
        "tasdiq": "PENODECORPRO-STEP1",
    },
    {
        "kalit": "W2G1",
        "nomi": "2-to'lqin, G1 — ombor o'zagi",
        "izoh": "Inventory, Recipe, Supplier, Project — bir-biriga bog'liq "
                "emas, hammasiga company_id=1 qo'yiladi.",
        "jadvallar": ["inventory", "recipes", "suppliers", "projects"],
        "tasdiq": "PENODECORPRO-W2G1",
    },
    {
        "kalit": "W2G2",
        "nomi": "2-to'lqin, G2 — ustalar va hodimlar",
        "izoh": "Master, MasterGift, GiftPeriod, Employee. Telefon/telegram_id "
                "unique cheklovlariga BU QADAMDA TEGILMAYDI — ular W2b da "
                "korxonaga bog'lanadi.",
        "jadvallar": ["masters", "master_gifts", "gift_periods", "employees"],
        "tasdiq": "PENODECORPRO-W2G2",
    },
    {
        "kalit": "W2G3",
        "nomi": "2-to'lqin, G3 — moliya",
        "izoh": "CashTransaction, RecurringObligation, TransportExpense, "
                "ExpenseTransaction. recurring_obligations.category unique "
                "cheklovi W2b da korxonaga bog'lanadi.",
        "jadvallar": ["cash_transactions", "recurring_obligations",
                      "transport_expenses", "expense_transactions"],
        "tasdiq": "PENODECORPRO-W2G3",
    },
    {
        "kalit": "W2G4",
        "nomi": "2-to'lqin, G4 — qolgan jadvallar",
        "izoh": "MonthlyExpense, CompanySetting, ActivityLog, LoginHistory. "
                "Shu qadam bilan 2-to'lqinning 16 jadvali tugaydi.",
        "jadvallar": ["monthly_expenses", "company_settings",
                      "activity_logs", "login_history"],
        "tasdiq": "PENODECORPRO-W2G4",
    },
    {
        "kalit": "W2B",
        "tur": "unique",
        "nomi": "2-to'lqin B — unique cheklovlarni korxonaga bog'lash",
        "izoh": "Hozir usta telefoni, retsept nomi va h.k. BUTUN TIZIM bo'yicha "
                "yagona. Ikkinchi korxona bir xil telefonli ustani qo'sha "
                "olmaydi. Shu cheklovlar (company_id + ustun) juftligiga "
                "o'tkaziladi. users.username, users.telegram_id va "
                "masters.telegram_id ATAYLAB global qoladi — login va "
                "Telegram bot ular bo'yicha odamni topadi.",
        "maqsadlar": [
            {"jadval": "inventory", "ustun": "item_name"},
            {"jadval": "projects", "ustun": "project_number"},
            {"jadval": "recipes", "ustun": "name"},
            {"jadval": "masters", "ustun": "phone"},
            {"jadval": "employees", "ustun": "phone"},
            {"jadval": "recurring_obligations", "ustun": "category"},
            # Bu BIRLAMCHI KALIT (unique emas) — shuning uchun alohida yo'l bilan
            {"jadval": "company_settings", "ustun": "key", "pk": True},
        ],
        "tasdiq": "PENODECORPRO-W2B",
    },
    {
        "kalit": "W3",
        "nomi": "3-to'lqin — buyurtmalar (orders)",
        "izoh": "company_id ODDIY 1 QILIB EMAS, har bir buyurtmaning O'Z "
                "loyihasidan olinadi (orders.project_id -> projects.company_id). "
                "Shunday qilib bog'liqlik boshidanoq to'g'ri quriladi.",
        "jadvallar": ["orders"],
        "ota": {"orders": {"jadval": "projects", "fk": "project_id"}},
        "tasdiq": "PENODECORPRO-W3",
    },
    {
        "kalit": "W3B",
        "tur": "unique",
        "nomi": "3-to'lqin B — buyurtma raqami cheklovi",
        "izoh": "orders.order_number hozir butun tizim bo'yicha yagona. "
                "(company_id, order_number) juftligiga o'tkaziladi.",
        "maqsadlar": [
            {"jadval": "orders", "ustun": "order_number"},
        ],
        "tasdiq": "PENODECORPRO-W3B",
    },
    {
        "kalit": "W4",
        "nomi": "4-to'lqin — buyurtma detallari (order_items)",
        "izoh": "company_id har bir detalning O'Z buyurtmasidan olinadi "
                "(order_items.order_id -> orders.company_id). order_id NOT NULL, "
                "shuning uchun zaxira qiymat kerak emas.",
        "jadvallar": ["order_items"],
        "ota": {"order_items": {"jadval": "orders", "fk": "order_id"}},
        "tasdiq": "PENODECORPRO-W4",
    },
    {
        "kalit": "W5",
        "nomi": "5-to'lqin — tayyor mahsulotlar (finished_products)",
        "izoh": "company_id buyurtmadan olinadi (from_order_id -> orders). "
                "LEKIN from_order_id BO'SH bo'lishi mumkin — omborga to'g'ridan-"
                "to'g'ri ishlab chiqarilgan mahsulotlarda buyurtma yo'q. "
                "Shunday qatorlarga zaxira qiymat (company_id=1) qo'yiladi.",
        "jadvallar": ["finished_products"],
        "ota": {"finished_products": {"jadval": "orders", "fk": "from_order_id"}},
        "zaxira": True,
        "tasdiq": "PENODECORPRO-W5",
    },
    {
        "kalit": "W6",
        "nomi": "6-to'lqin — qolgan 5 jadval (yakuniy)",
        "izoh": "ReturnItem, InventoryMovement, InventoryReceipt, "
                "FinishedProductSale, FinishedProductLoss. Hammasining ota-FK'si "
                "BO'SH bo'lishi mumkin, shuning uchun otasi topilmaganlarga "
                "zaxira qiymat qo'yiladi. Shu qadam bilan migratsiya tugaydi.",
        "jadvallar": ["return_items", "inventory_movements", "inventory_receipts",
                      "finished_product_sales", "finished_product_losses"],
        "ota": {
            "return_items": {"jadval": "orders", "fk": "order_id"},
            "inventory_movements": {"jadval": "inventory", "fk": "inventory_id"},
            "inventory_receipts": {"jadval": "suppliers", "fk": "supplier_id"},
            "finished_product_sales": {"jadval": "finished_products",
                                       "fk": "finished_product_id"},
            "finished_product_losses": {"jadval": "finished_products",
                                        "fk": "finished_product_id"},
        },
        "zaxira": True,
        "tasdiq": "PENODECORPRO-W6",
    },
    {
        "kalit": "TEKSHIRUV",
        "tur": "verify",
        "nomi": "Yakuniy tekshiruv — 7 jadval (faqat o'qiydi)",
        "izoh": "OrderItem, FinishedProduct, ReturnItem, InventoryMovement, "
                "InventoryReceipt, FinishedProductSale, FinishedProductLoss. "
                "Hech narsa o'zgartirmaydi: qatorlar, NULL, yetim, taqsimot, "
                "FK/indeks/NOT NULL va ota bilan MOS KELMAGAN qatorlar.",
        "maqsadlar": [],
        "tasdiq": "",
    },
    {
        "kalit": "M1KOD",
        "tur": "kod",
        "nomi": "M1 — korxona kodi (companies.code)",
        "izoh": "Xodim paneliga kirishda korxona kontekstini aniqlash uchun. "
                "W2b dan keyin ikki korxonada bir xil telefonli xodim bo'lishi "
                "mumkin, shuning uchun faqat telefon yetarli emas. Kod nomdan "
                "avtomatik hosil qilinadi, mavjud ma'lumotga tegilmaydi.",
        "maqsadlar": [],
        "tasdiq": "PENODECORPRO-M1KOD",
    },
]

# Tekshiruv uchun ota zanjirlari — models.py'dagi _TENANT_RULES bilan
# BIR XIL bo'lishi shart. Bu yerda SQL ko'rinishida yozilgan.
VERIFY_TABLES = [
    ("order_items", [("order_id", "orders")]),
    ("finished_products", [("from_order_id", "orders"),
                           ("recipe_id", "recipes"),
                           ("penoplast_id", "inventory")]),
    ("return_items", [("order_id", "orders"),
                      ("finished_product_id", "finished_products")]),
    ("inventory_movements", [("inventory_id", "inventory"),
                             ("order_id", "orders"),
                             ("supplier_id", "suppliers")]),
    ("inventory_receipts", [("supplier_id", "suppliers")]),
    ("finished_product_sales", [("finished_product_id", "finished_products"),
                                ("master_id", "masters")]),
    ("finished_product_losses", [("finished_product_id", "finished_products")]),
]


def verify_tables(engine) -> list:
    """7 jadval uchun to'liq tekshiruv. FAQAT O'QIYDI."""
    natija = []
    with engine.connect() as conn:
        try:
            conn.execute(text(f"SET statement_timeout = '{STATEMENT_TIMEOUT}'"))
        except Exception:
            pass
        for t, otalar in VERIFY_TABLES:
            if not _table_exists(conn, t):
                natija.append({"jadval": t, "mavjud": False})
                continue
            meta = _column_meta(conn, t, "company_id")
            fk = _fk_exists(conn, t, "company_id")
            jami = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            bosh = conn.execute(text(
                f"SELECT COUNT(*) FROM {t} WHERE company_id IS NULL")).scalar() if meta else None
            yetim = conn.execute(text(f"""
                SELECT COUNT(*) FROM {t} x LEFT JOIN {REF_TABLE} c ON c.id = x.company_id
                WHERE x.company_id IS NOT NULL AND c.id IS NULL""")).scalar() if meta else None
            taqsimot = [{"company_id": r[0], "qatorlar": r[1]} for r in conn.execute(text(
                f"SELECT company_id, COUNT(*) FROM {t} GROUP BY company_id "
                f"ORDER BY company_id")).all()] if meta else []

            # Ota bilan MOS KELMAGAN qatorlar + otasi umuman aniqlanmaganlar
            nomuvofiq, otasiz = [], None
            if meta and otalar:
                shartlar = []
                for fk_col, p_tbl in otalar:
                    if not _column_exists(conn, t, fk_col):
                        continue
                    n = conn.execute(text(f"""
                        SELECT COUNT(*) FROM {t} x
                        JOIN {p_tbl} p ON p.id = x.{fk_col}
                        WHERE x.company_id <> p.company_id""")).scalar()
                    if n:
                        nomuvofiq.append({"ota": f"{fk_col} -> {p_tbl}", "qatorlar": n})
                    shartlar.append(f"x.{fk_col} IS NOT NULL")
                if shartlar:
                    otasiz = conn.execute(text(
                        f"SELECT COUNT(*) FROM {t} x WHERE NOT ({' OR '.join(shartlar)})"
                    )).scalar()

            natija.append({
                "jadval": t, "mavjud": True,
                "qatorlar": jami,
                "company_id_bor": bool(meta),
                "NULL_company_id": bosh,
                "yetim_company_id": yetim,
                "taqsimot": taqsimot,
                "FK": fk.get("nom") if fk else None,
                "indeks": _index_name(t) if _index_exists(conn, _index_name(t)) else None,
                "NOT_NULL": (not meta.get("null_bolishi_mumkin")) if meta else None,
                "ota_bilan_nomuvofiq": nomuvofiq,
                "otasi_aniqlanmagan": otasiz,
                "tugallangan": bool(meta and not meta.get("null_bolishi_mumkin") and fk
                                    and _index_exists(conn, _index_name(t))
                                    and bosh == 0 and yetim == 0 and not nomuvofiq),
            })
    return natija


def _step(kalit: str):
    for s in STEPS:
        if s["kalit"] == kalit:
            return s
    return None


def _index_name(table: str) -> str:
    # models.py'dagi index=True bilan bir xil nom (SQLAlchemy standarti)
    return f"ix_{table}_company_id"


def _fk_name(table: str) -> str:
    # Postgres'ning o'z standart nomlash uslubi
    return f"{table}_company_id_fkey"


# ============================================================
# Kichik yordamchilar (hammasi FAQAT o'qiydi)
# ============================================================

def _table_exists(conn, table: str) -> bool:
    return bool(conn.execute(text("""
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = current_schema() AND table_name = :t
    """), {"t": table}).scalar())


def _column_exists(conn, table: str, column: str) -> bool:
    return bool(conn.execute(text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = :t AND column_name = :c
    """), {"t": table, "c": column}).scalar())


def _column_meta(conn, table: str, column: str) -> dict:
    row = conn.execute(text("""
        SELECT data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = :t AND column_name = :c
    """), {"t": table, "c": column}).first()
    if not row:
        return {}
    return {"tur": row[0], "null_bolishi_mumkin": row[1] == "YES", "default": row[2]}


def _index_exists(conn, name: str) -> bool:
    return bool(conn.execute(text("""
        SELECT 1 FROM pg_indexes
        WHERE schemaname = current_schema() AND indexname = :n
    """), {"n": name}).scalar())


def _fk_exists(conn, table: str, column: str) -> dict:
    """Shu ustunda TASHQI KALIT bormi — nomidan qat'i nazar (baza qo'lda
    o'zgartirilgan bo'lsa, nom boshqacha bo'lishi mumkin)."""
    row = conn.execute(text("""
        SELECT tc.constraint_name, ccu.table_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name
         AND tc.table_schema = ccu.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = current_schema()
          AND tc.table_name = :t
          AND kcu.column_name = :c
    """), {"t": table, "c": column}).first()
    if not row:
        return {}
    return {"nom": row[0], "bogliq_jadval": row[1]}


def environment_info(conn) -> dict:
    """Qaysi MUHITDA turganimizni ko'rsatadi.

    MUHIM: `production` va `sinov` — bitta Railway loyihasining ikki
    muhiti. Xato muhitda ishlab yubormaslik uchun, har bir hisobotning
    eng boshida shu ma'lumot chiqadi."""
    try:
        db_name = conn.execute(text("SELECT current_database()")).scalar()
    except Exception:
        db_name = "?"
    try:
        version = conn.execute(text("SHOW server_version")).scalar()
    except Exception:
        version = "?"
    return {
        "railway_muhit": os.environ.get("RAILWAY_ENVIRONMENT_NAME")
                          or os.environ.get("RAILWAY_ENVIRONMENT") or "(nomalum)",
        "railway_xizmat": os.environ.get("RAILWAY_SERVICE_NAME") or "(nomalum)",
        "domen": os.environ.get("RAILWAY_PUBLIC_DOMAIN") or "(nomalum)",
        "baza_nomi": db_name,
        "postgres_versiya": version,
    }


# ============================================================
# Qulf (lock) diagnostikasi
# ============================================================

def _blocking_sessions(engine, tables) -> list:
    """Berilgan jadvallarni ushlab turgan boshqa ulanishlarni ko'rsatadi.
    ALOHIDA ulanishda ishlaydi — asosiy tranzaksiya xato bo'lgandan keyin
    ham ma'lumot olish uchun."""
    try:
        with engine.connect() as c:
            c.execute(text("SET statement_timeout = '5s'"))
            rows = c.execute(text("""
                SELECT a.pid, a.state, coalesce(a.application_name,'') AS ilova,
                       round(extract(epoch from (now() - a.state_change)))::int AS sekund,
                       l.relation::regclass::text AS jadval,
                       left(coalesce(a.query,''), 100) AS sorov
                FROM pg_locks l
                JOIN pg_stat_activity a ON a.pid = l.pid
                WHERE l.relation::regclass::text = ANY(:t)
                  AND a.pid <> pg_backend_pid()
                ORDER BY sekund DESC NULLS LAST
                LIMIT 10
            """), {"t": list(tables)}).all()
        return [{"pid": r[0], "holat": r[1], "ilova": r[2], "necha_sekund": r[3],
                 "jadval": r[4], "sorov": r[5]} for r in rows]
    except Exception as e:
        return [{"xato": f"aniqlab bo'lmadi: {e}"}]


def _is_lock_error(e: Exception) -> bool:
    m = str(e).lower()
    return ("lock timeout" in m or "55p03" in m or "lock_not_available" in m
            or "canceling statement due to lock" in m)



# ============================================================
# Unique / birlamchi kalit yordamchilari (W2B uchun)
# ============================================================
# MUHIM: cheklov nomlari QATTIQ YOZILMAYDI. Postgres ularni o'zi nomlaydi,
# va baza qo'lda o'zgartirilgan bo'lsa nom boshqacha bo'lishi mumkin —
# shuning uchun har safar bazadan topiladi.

_YAGONA_SQL = """
SELECT c.conname, CASE c.contype WHEN 'p' THEN 'PRIMARY KEY' ELSE 'CONSTRAINT' END
FROM pg_constraint c
JOIN pg_class t ON t.oid = c.conrelid
JOIN pg_namespace n ON n.oid = t.relnamespace AND n.nspname = current_schema()
JOIN pg_attribute a ON a.attrelid = t.oid AND a.attname = :col
WHERE t.relname = :tbl AND c.contype IN ('u','p')
  AND c.conkey = ARRAY[a.attnum]::smallint[]
UNION ALL
SELECT i.relname, 'INDEX'
FROM pg_index x
JOIN pg_class t ON t.oid = x.indrelid
JOIN pg_namespace n ON n.oid = t.relnamespace AND n.nspname = current_schema()
JOIN pg_class i ON i.oid = x.indexrelid
JOIN pg_attribute a ON a.attrelid = t.oid AND a.attname = :col
WHERE t.relname = :tbl AND x.indisunique AND x.indnatts = 1
  AND x.indkey[0] = a.attnum
  AND NOT EXISTS (SELECT 1 FROM pg_constraint c2 WHERE c2.conindid = x.indexrelid)
"""


def _single_col_uniques(conn, table: str, column: str) -> list:
    """Shu USTUNNING O'ZIGA (bitta ustunga) qo'yilgan unique/PK obyektlar."""
    return [{"nom": r[0], "tur": r[1]}
            for r in conn.execute(text(_YAGONA_SQL), {"tbl": table, "col": column}).all()]


def _pk_columns(conn, table: str) -> list:
    return [r[0] for r in conn.execute(text("""
        SELECT a.attname
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace AND n.nspname = current_schema()
        JOIN unnest(c.conkey) WITH ORDINALITY k(attnum, ord) ON true
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum
        WHERE t.relname = :t AND c.contype = 'p'
        ORDER BY k.ord
    """), {"t": table}).all()]


def _uq_name(table: str, column: str) -> str:
    return f"uq_{table}_company_{column}"


def _duplicates(conn, table: str, column: str) -> int:
    """(company_id, ustun) juftligi bo'yicha takrorlanish soni.
    NULL qiymatlar hisobga olinmaydi — Postgres ularni bir-biriga teng
    deb hisoblamaydi, shuning uchun ular to'qnashmaydi."""
    return conn.execute(text(f"""
        SELECT COUNT(*) FROM (
            SELECT company_id, {column}
            FROM {table}
            WHERE {column} IS NOT NULL
            GROUP BY company_id, {column}
            HAVING COUNT(*) > 1
        ) d
    """)).scalar()


def _unique_target_status(conn, maqsad: dict) -> dict:
    t, col = maqsad["jadval"], maqsad["ustun"]
    if not _table_exists(conn, t) or not _column_exists(conn, t, "company_id"):
        return {"jadval": t, "ustun": col, "tayyor_emas": True, "tugallangan": False}
    eski = _single_col_uniques(conn, t, col)
    if maqsad.get("pk"):
        pk = _pk_columns(conn, t)
        yangi_bor = pk == ["company_id", col] or set(pk) == {"company_id", col}
        yangi_nom = "PRIMARY KEY (company_id, %s)" % col
    else:
        yangi_bor = _index_exists(conn, _uq_name(t, col))
        yangi_nom = _uq_name(t, col)
    return {
        "jadval": t, "ustun": col, "pk": bool(maqsad.get("pk")),
        "yangi": yangi_nom, "yangi_bor": yangi_bor,
        "eski_yagona": eski,
        "dublikat": _duplicates(conn, t, col),
        "tugallangan": bool(yangi_bor and not eski),
    }

# ============================================================
# HOLAT — faqat o'qiydi
# ============================================================

def _table_status(conn, table: str) -> dict:
    if not _table_exists(conn, table):
        return {"jadval": table, "mavjud": False}
    meta = _column_meta(conn, table, "company_id")
    fk = _fk_exists(conn, table, "company_id")
    jami = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
    bosh = yetim = None
    if meta:
        bosh = conn.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE company_id IS NULL")).scalar()
        yetim = conn.execute(text(f"""
            SELECT COUNT(*) FROM {table} x
            LEFT JOIN {REF_TABLE} c ON c.id = x.company_id
            WHERE x.company_id IS NOT NULL AND c.id IS NULL
        """)).scalar()
    tugallangan = bool(meta and not meta.get("null_bolishi_mumkin")
                       and fk and _index_exists(conn, _index_name(table))
                       and bosh == 0 and yetim == 0)
    return {
        "jadval": table, "mavjud": True,
        "ustun_bor": bool(meta), "ustun": meta or None,
        "indeks_bor": _index_exists(conn, _index_name(table)),
        "tashqi_kalit": fk or None,
        "qatorlar": jami, "bosh_NULL": bosh, "yetim": yetim,
        "tugallangan": tugallangan,
    }


def status_report(engine) -> dict:
    """Barcha qadamlarning holati. To'liq xavfsiz: bitta ham yozuv yo'q."""
    with engine.connect() as conn:
        try:
            conn.execute(text(f"SET statement_timeout = '{STATEMENT_TIMEOUT}'"))
        except Exception:
            pass
        if conn.dialect.name != "postgresql":
            return {"baza_turi": conn.dialect.name,
                    "xato": "Bu migratsiya faqat PostgreSQL uchun."}

        qadamlar = []
        for s in STEPS:
            if s.get("tur") == "kod":
                k = kod_status(engine)
                qadamlar.append({
                    "kalit": s["kalit"], "nomi": s["nomi"], "izoh": s["izoh"],
                    "tasdiq": s["tasdiq"], "tur": "kod", "kod": k,
                    "tugallangan": bool(k.get("tugallangan")),
                })
                continue
            if s.get("tur") == "verify":
                j = verify_tables(engine)
                qadamlar.append({
                    "kalit": s["kalit"], "nomi": s["nomi"], "izoh": s["izoh"],
                    "tasdiq": s["tasdiq"], "tur": "verify", "tekshiruv": j,
                    "tugallangan": all(x.get("tugallangan") for x in j),
                })
                continue
            if s.get("tur") == "unique":
                maqsadlar = [_unique_target_status(conn, m) for m in s["maqsadlar"]]
                qadamlar.append({
                    "kalit": s["kalit"], "nomi": s["nomi"], "izoh": s["izoh"],
                    "tasdiq": s["tasdiq"], "tur": "unique", "maqsadlar": maqsadlar,
                    "tugallangan": all(m.get("tugallangan") for m in maqsadlar),
                })
                continue
            jadvallar = [_table_status(conn, t) for t in s["jadvallar"]]
            qadamlar.append({
                "kalit": s["kalit"], "nomi": s["nomi"], "izoh": s["izoh"],
                "tasdiq": s["tasdiq"], "tur": "column", "jadvallar": jadvallar,
                "tugallangan": all(j.get("tugallangan") for j in jadvallar),
            })
        return {"muhit": environment_info(conn), "qadamlar": qadamlar}


# ============================================================
# MIGRATSIYA
# ============================================================

class _MigrationStop(Exception):
    """To'xtatuvchi shart bajarildi — hammasi bekor qilinadi."""


def run_step(engine, kalit: str, dry_run: bool = True) -> dict:
    """Bitta qadamni (bir yoki bir nechta jadval) bajaradi.

    dry_run=True  -> hamma narsa haqiqatdan bajariladi, oxirida ROLLBACK.
    dry_run=False -> COMMIT (qaytarib bo'lmaydi, faqat backupdan tiklash).
    """
    s = _step(kalit)
    if not s:
        return {"natija": f"❌ Noma'lum qadam: {kalit}", "xato": "kalit topilmadi"}

    if s.get("tur") == "unique":
        return _run_unique_step(engine, s, dry_run)

    hisobot = {
        "qadam": s["kalit"],
        "nomi": s["nomi"],
        "jadvallar": list(s["jadvallar"]),
        "rejim": "DRY-RUN (sinov, o'zgarish saqlanmaydi)" if dry_run else "HAQIQIY (COMMIT)",
        "vaqt_utc": datetime.utcnow().isoformat(timespec="seconds"),
        "muhit": {}, "tekshiruvlar": [], "amallar": [],
        "oxirgi_holat": [], "natija": "", "xato": None,
    }

    def tekshir(kod, tavsif, ok, izoh=""):
        hisobot["tekshiruvlar"].append({
            "kod": kod, "tavsif": tavsif,
            "holat": "OK" if ok else "TO'XTASH", "izoh": izoh})
        if not ok:
            raise _MigrationStop(f"{kod}: {tavsif} — {izoh}")

    def amal(jadval, kod, tavsif, holat, izoh=""):
        hisobot["amallar"].append({
            "jadval": jadval, "kod": kod, "tavsif": tavsif,
            "holat": holat, "izoh": izoh})

    conn = engine.connect()
    trans = conn.begin()
    try:
        # MUHIM (2026-09-18, real hodisadan keyin qo'shildi): ALTER TABLE
        # jadvalga TO'LIQ EKSKLYUZIV qulf so'raydi. Agar boshqa ulanish o'sha
        # jadvalni ushlab tursa, bizning so'rovimiz navbatga turadi — va
        # navbatdagi eksklyuziv so'rov UNDAN KEYINGI barcha oddiy so'rovlarni
        # ham to'sib qo'yadi, natijada BUTUN SAYT javob bermay qoladi.
        conn.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))
        conn.execute(text(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'"))

        hisobot["muhit"] = environment_info(conn)

        # ---------- UMUMIY TEKSHIRUVLAR ----------
        tekshir("P1", "Baza PostgreSQL bo'lishi shart",
                conn.dialect.name == "postgresql", f"topildi: {conn.dialect.name}")
        tekshir("P2", f"'{REF_TABLE}' jadvali mavjud", _table_exists(conn, REF_TABLE),
                "Production/MRP moduli yaratadi")
        tekshir("P3", f"Asosiy korxona (companies.id={DEFAULT_COMPANY_ID}) mavjud",
                bool(conn.execute(text(f"SELECT 1 FROM {REF_TABLE} WHERE id = :i"),
                                  {"i": DEFAULT_COMPANY_ID}).scalar()))
        for t in s["jadvallar"]:
            tekshir(f"P4:{t}", f"'{t}' jadvali mavjud", _table_exists(conn, t))

        # ---------- HAR BIR JADVAL ----------
        for t in s["jadvallar"]:
            idx, fkn = _index_name(t), _fk_name(t)

            # A1 — ustun
            if _column_exists(conn, t, "company_id"):
                amal(t, "A1", "company_id ustunini qo'shish", "ALLAQACHON BOR")
            else:
                conn.execute(text(f"ALTER TABLE {t} ADD COLUMN company_id INTEGER"))
                amal(t, "A1", "company_id ustunini qo'shish (NULL ruxsat)", "BAJARILDI")

            # A2 — sanash
            jami = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            bosh = conn.execute(
                text(f"SELECT COUNT(*) FROM {t} WHERE company_id IS NULL")).scalar()
            amal(t, "A2", "Qatorlarni sanash", "MA'LUMOT",
                 f"jami={jami}, company_id bo'sh={bosh}")

            # A3 — backfill
            # Ikki xil usul bor:
            #  * ODDIY: company_id = 1 (mustaqil, ota-jadvali yo'q jadvallar)
            #  * OTA-JADVALDAN: masalan orders.company_id ni o'z loyihasidan
            #    olish. Bu to'g'riroq — ko'p korxonali holatda har bir qator
            #    HAQIQIY egasini oladi, hammasi 1-korxonaga tushib qolmaydi.
            ota = (s.get("ota") or {}).get(t)
            if not bosh:
                amal(t, "A3", "Bo'sh qatorlarni to'ldirish", "KERAK EMAS",
                     "bo'sh qator yo'q")
            elif ota:
                r = conn.execute(text(f"""
                    UPDATE {t} AS x
                    SET company_id = p.company_id
                    FROM {ota['jadval']} AS p
                    WHERE p.id = x.{ota['fk']} AND x.company_id IS NULL
                """))
                amal(t, "A3", f"Ota-jadvaldan to'ldirish "
                              f"({t}.{ota['fk']} -> {ota['jadval']}.company_id)",
                     "BAJARILDI", f"{r.rowcount} qator yangilandi")
                # Ota-jadvali topilmagan (yetim yoki bo'sh FK) qatorlar qolsa
                qoldi = conn.execute(text(
                    f"SELECT COUNT(*) FROM {t} WHERE company_id IS NULL")).scalar()
                if qoldi and s.get("zaxira"):
                    r2 = conn.execute(text(
                        f"UPDATE {t} SET company_id = :cid WHERE company_id IS NULL"),
                        {"cid": DEFAULT_COMPANY_ID})
                    amal(t, "A3b", f"Otasi topilmaganlar uchun zaxira "
                                   f"(company_id={DEFAULT_COMPANY_ID})",
                         "BAJARILDI", f"{r2.rowcount} qator")
                elif qoldi:
                    amal(t, "A3b", "Otasi topilmagan qatorlar", "DIQQAT",
                         f"{qoldi} qator — A4 buni to'xtatadi")
            else:
                r = conn.execute(text(
                    f"UPDATE {t} SET company_id = :cid WHERE company_id IS NULL"),
                    {"cid": DEFAULT_COMPANY_ID})
                amal(t, "A3", f"Bo'sh qatorlarni to'ldirish (company_id={DEFAULT_COMPANY_ID})",
                     "BAJARILDI", f"{r.rowcount} qator yangilandi")

            # A4 — NULL = 0 (TO'XTATUVCHI)
            qolgan = conn.execute(
                text(f"SELECT COUNT(*) FROM {t} WHERE company_id IS NULL")).scalar()
            tekshir(f"A4:{t}", f"'{t}': backfilldan keyin bo'sh qator qolmasligi shart",
                    qolgan == 0, f"qolgan={qolgan}")

            # A5 — yetim yo'q (TO'XTATUVCHI)
            yetim = conn.execute(text(f"""
                SELECT COUNT(*) FROM {t} x
                LEFT JOIN {REF_TABLE} c ON c.id = x.company_id
                WHERE c.id IS NULL
            """)).scalar()
            tekshir(f"A5:{t}", f"'{t}': har bir company_id companies'da bo'lishi shart",
                    yetim == 0, f"yetim={yetim}")

            # A6 — indeks
            if _index_exists(conn, idx):
                amal(t, "A6", f"Indeks {idx}", "ALLAQACHON BOR")
            else:
                conn.execute(text(f"CREATE INDEX {idx} ON {t} (company_id)"))
                amal(t, "A6", f"Indeks {idx} yaratish", "BAJARILDI")

            # A7 — tashqi kalit
            mavjud_fk = _fk_exists(conn, t, "company_id")
            if mavjud_fk:
                amal(t, "A7", "Tashqi kalit (FK)", "ALLAQACHON BOR",
                     f"{mavjud_fk['nom']} -> {mavjud_fk['bogliq_jadval']}")
            else:
                conn.execute(text(
                    f"ALTER TABLE {t} ADD CONSTRAINT {fkn} "
                    f"FOREIGN KEY (company_id) REFERENCES {REF_TABLE} (id)"))
                amal(t, "A7", f"Tashqi kalit {fkn} qo'shish", "BAJARILDI",
                     f"{t}.company_id -> {REF_TABLE}.id")

            # A8 — vaqtinchalik DEFAULT
            # Baza NOT NULL bo'lgandan keyin, lekin kod hali yangilanmagan
            # oraliqda ESKI kod company_id yubormaydi -> INSERT yiqilardi.
            # DEFAULT shu oraliqni yopadi. Keyinroq OLIB TASHLANADI: aks holda
            # unutilgan company_id jimgina 1-korxonaga tushib qoladi.
            meta = _column_meta(conn, t, "company_id")
            if meta.get("default"):
                amal(t, "A8", "Vaqtinchalik DEFAULT", "ALLAQACHON BOR", str(meta["default"]))
            else:
                conn.execute(text(
                    f"ALTER TABLE {t} ALTER COLUMN company_id SET DEFAULT {DEFAULT_COMPANY_ID}"))
                amal(t, "A8", f"Vaqtinchalik DEFAULT {DEFAULT_COMPANY_ID}", "BAJARILDI",
                     "o'tish davri uchun; keyinroq olib tashlanadi")

            # A9 — NOT NULL
            if meta and not meta.get("null_bolishi_mumkin"):
                amal(t, "A9", "NOT NULL", "ALLAQACHON BOR")
            else:
                conn.execute(text(
                    f"ALTER TABLE {t} ALTER COLUMN company_id SET NOT NULL"))
                amal(t, "A9", "Ustunni NOT NULL qilish", "BAJARILDI")

        # ---------- OXIRGI HOLAT ----------
        hisobot["oxirgi_holat"] = [_table_status(conn, t) for t in s["jadvallar"]]

        if dry_run:
            trans.rollback()
            hisobot["natija"] = (
                "✅ SINOV MUVAFFAQIYATLI — barcha amallar haqiqatdan bajarildi va "
                "keyin TO'LIQ QAYTARIB OLINDI (rollback). Bazada hech qanday "
                "o'zgarish qolmadi. Haqiqiy migratsiyani boshlash mumkin.")
        else:
            trans.commit()
            hisobot["natija"] = "✅ HAQIQIY MIGRATSIYA BAJARILDI VA SAQLANDI (commit)."

    except _MigrationStop as e:
        trans.rollback()
        hisobot["natija"] = "⛔ TO'XTATILDI — hech narsa o'zgarmadi (rollback)."
        hisobot["xato"] = str(e)
    except Exception as e:
        trans.rollback()
        if _is_lock_error(e):
            hisobot["natija"] = (
                "⏳ QULF BAND — jadvalni boshqa ulanish ushlab turibdi, shuning "
                "uchun to'xtatildi. Bazada hech narsa o'zgarmadi. ERP'ning "
                "ortiqcha tablarini yoping va qaytadan urinib ko'ring; yordam "
                "bermasa Railway'da 'web' xizmatini Restart qiling.")
            hisobot["qulf_tutib_turganlar"] = _blocking_sessions(engine, s["jadvallar"])
        else:
            hisobot["natija"] = "❌ XATO — hech narsa o'zgarmadi (rollback)."
        hisobot["xato"] = f"{type(e).__name__}: {e}"
    finally:
        conn.close()

    return hisobot



def _run_unique_step(engine, s: dict, dry_run: bool) -> dict:
    """Unique / birlamchi kalit cheklovlarini (company_id + ustun) juftligiga
    o'tkazadi.

    Tartib — YANGISI AVVAL, ESKISI KEYIN: avval yangi kompozit cheklov
    yaratiladi, tekshiriladi, keyingina eskisi olib tashlanadi. Shunda
    oraliqda jadval bir lahza ham himoyasiz qolmaydi.

    BIRLAMChI KALIT (company_settings) — istisno: bitta jadvalda ikkita
    PRIMARY KEY bo'lolmaydi, shuning uchun u yerda eskisi avval olib
    tashlanadi va darhol yangisi qo'yiladi. Ikkalasi ham BITTA
    tranzaksiya ichida bo'lgani uchun, xato bo'lsa hammasi qaytariladi.
    """
    hisobot = {
        "qadam": s["kalit"], "nomi": s["nomi"],
        "rejim": "DRY-RUN (sinov, o'zgarish saqlanmaydi)" if dry_run else "HAQIQIY (COMMIT)",
        "vaqt_utc": datetime.utcnow().isoformat(timespec="seconds"),
        "muhit": {}, "tekshiruvlar": [], "amallar": [],
        "oxirgi_holat": [], "natija": "", "xato": None,
    }

    def tekshir(kod, tavsif, ok, izoh=""):
        hisobot["tekshiruvlar"].append({
            "kod": kod, "tavsif": tavsif,
            "holat": "OK" if ok else "TO'XTASH", "izoh": izoh})
        if not ok:
            raise _MigrationStop(f"{kod}: {tavsif} — {izoh}")

    def amal(jadval, kod, tavsif, holat, izoh=""):
        hisobot["amallar"].append({
            "jadval": jadval, "kod": kod, "tavsif": tavsif,
            "holat": holat, "izoh": izoh})

    jadvallar = [m["jadval"] for m in s["maqsadlar"]]
    conn = engine.connect()
    trans = conn.begin()
    try:
        conn.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))
        conn.execute(text(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'"))
        hisobot["muhit"] = environment_info(conn)

        tekshir("P1", "Baza PostgreSQL bo'lishi shart",
                conn.dialect.name == "postgresql", f"topildi: {conn.dialect.name}")

        # Oldindan: har bir jadvalda company_id bo'lishi SHART
        for m in s["maqsadlar"]:
            t = m["jadval"]
            tekshir(f"P2:{t}", f"'{t}' jadvalida company_id bo'lishi shart",
                    _table_exists(conn, t) and _column_exists(conn, t, "company_id"),
                    "avval 2-to'lqin qadamlarini bajaring")

        # Oldindan: TAKRORLANISH bo'lmasligi shart (eng muhim to'xtatuvchi)
        for m in s["maqsadlar"]:
            t, col = m["jadval"], m["ustun"]
            d = _duplicates(conn, t, col)
            tekshir(f"B1:{t}.{col}",
                    f"'{t}.{col}': (company_id, {col}) juftligi takrorlanmasligi shart",
                    d == 0, f"takrorlangan={d}")

        # Har bir maqsad
        for m in s["maqsadlar"]:
            t, col = m["jadval"], m["ustun"]
            eski = _single_col_uniques(conn, t, col)

            if m.get("pk"):
                pk = _pk_columns(conn, t)
                if set(pk) == {"company_id", col}:
                    amal(t, "B3", f"Birlamchi kalit (company_id, {col})", "ALLAQACHON BOR")
                else:
                    eski_pk = [e for e in eski if e["tur"] == "PRIMARY KEY"]
                    for e in eski_pk:
                        conn.execute(text(f'ALTER TABLE {t} DROP CONSTRAINT "{e["nom"]}"'))
                        amal(t, "B4", f"Eski birlamchi kalitni olib tashlash", "BAJARILDI", e["nom"])
                    conn.execute(text(
                        f"ALTER TABLE {t} ADD PRIMARY KEY (company_id, {col})"))
                    amal(t, "B3", f"Yangi birlamchi kalit (company_id, {col})", "BAJARILDI")
                continue

            # 1) YANGISI
            uq = _uq_name(t, col)
            if _index_exists(conn, uq):
                amal(t, "B3", f"Kompozit unique {uq}", "ALLAQACHON BOR")
            else:
                conn.execute(text(
                    f"CREATE UNIQUE INDEX {uq} ON {t} (company_id, {col})"))
                amal(t, "B3", f"Kompozit unique {uq} yaratish", "BAJARILDI",
                     f"(company_id, {col})")

            # 2) tekshiruv — yangisi haqiqatan paydo bo'ldimi
            tekshir(f"B4:{t}.{col}", f"'{uq}' yaratilgan bo'lishi shart",
                    _index_exists(conn, uq))

            # 3) ESKISI
            if not eski:
                amal(t, "B5", f"Eski yagona-ustun unique ({col})", "YO'Q EDI")
            for e in eski:
                if e["tur"] == "INDEX":
                    conn.execute(text(f'DROP INDEX "{e["nom"]}"'))
                else:
                    conn.execute(text(f'ALTER TABLE {t} DROP CONSTRAINT "{e["nom"]}"'))
                amal(t, "B5", f"Eski {e['tur']} ni olib tashlash", "BAJARILDI", e["nom"])

        # Yakuniy tekshiruv
        for m in s["maqsadlar"]:
            st = _unique_target_status(conn, m)
            tekshir(f"B6:{st['jadval']}.{st['ustun']}",
                    f"'{st['jadval']}.{st['ustun']}': yangisi bor, eskisi yo'q",
                    st["tugallangan"],
                    f"yangi_bor={st['yangi_bor']}, eski={[e['nom'] for e in st['eski_yagona']]}")

        hisobot["oxirgi_holat"] = [_unique_target_status(conn, m) for m in s["maqsadlar"]]

        if dry_run:
            trans.rollback()
            hisobot["natija"] = (
                "✅ SINOV MUVAFFAQIYATLI — barcha cheklovlar haqiqatdan "
                "o'zgartirildi va keyin TO'LIQ QAYTARIB OLINDI (rollback). "
                "Bazada hech qanday o'zgarish qolmadi.")
        else:
            trans.commit()
            hisobot["natija"] = "✅ HAQIQIY MIGRATSIYA BAJARILDI VA SAQLANDI (commit)."

    except _MigrationStop as e:
        trans.rollback()
        hisobot["natija"] = "⛔ TO'XTATILDI — hech narsa o'zgarmadi (rollback)."
        hisobot["xato"] = str(e)
    except Exception as e:
        trans.rollback()
        if _is_lock_error(e):
            hisobot["natija"] = (
                "⏳ QULF BAND — jadvalni boshqa ulanish ushlab turibdi. Bazada "
                "hech narsa o'zgarmadi. Ortiqcha tablarni yoping va qaytadan "
                "urinib ko'ring.")
            hisobot["qulf_tutib_turganlar"] = _blocking_sessions(engine, jadvallar)
        else:
            hisobot["natija"] = "❌ XATO — hech narsa o'zgarmadi (rollback)."
        hisobot["xato"] = f"{type(e).__name__}: {e}"
    finally:
        conn.close()

    return hisobot


# ============================================================
# M1 — korxona kodi (companies.code)
# ============================================================

def _kod_yasa(nom: str) -> str:
    """Korxona nomidan qisqa, terish oson kod hosil qiladi."""
    import re as _re
    almashuv = {"'": "", "'": "", "‘": "", "’": ""}
    for a, b in almashuv.items():
        nom = nom.replace(a, b)
    kod = _re.sub(r"[^A-Za-z0-9]+", "-", nom).strip("-").upper()
    return (kod or "KORXONA")[:30]


def kod_status(engine) -> dict:
    """companies.code holati. Faqat o'qiydi."""
    with engine.connect() as conn:
        if not _column_exists(conn, REF_TABLE, "code"):
            jami = conn.execute(text(f"SELECT COUNT(*) FROM {REF_TABLE}")).scalar()
            return {"ustun_bor": False, "korxonalar": jami, "tugallangan": False}
        rows = conn.execute(text(
            f"SELECT id, name, code FROM {REF_TABLE} ORDER BY id")).all()
        bosh = sum(1 for r in rows if not r[2])
        return {
            "ustun_bor": True,
            "indeks_bor": _index_exists(conn, "ix_companies_code"),
            "korxonalar": [{"id": r[0], "name": r[1], "code": r[2]} for r in rows],
            "kodsiz": bosh,
            "tugallangan": bosh == 0 and _index_exists(conn, "ix_companies_code"),
        }


def run_kod_migration(engine, dry_run: bool = True) -> dict:
    """companies.code ustunini qo'shadi va nomlardan kod hosil qiladi.

    Xuddi boshqa qadamlar kabi: bitta tranzaksiya, dry-run rollback qiladi,
    idempotent. MAVJUD MA'LUMOTGA TEGMAYDI — faqat yangi ustun to'ldiriladi.
    """
    hisobot = {"qadam": "M1KOD", "nomi": "Korxona kodi",
               "rejim": "DRY-RUN (sinov, o'zgarish saqlanmaydi)" if dry_run else "HAQIQIY (COMMIT)",
               "vaqt_utc": datetime.utcnow().isoformat(timespec="seconds"),
               "muhit": {}, "amallar": [], "natija": "", "xato": None}

    def amal(kod, tavsif, holat, izoh=""):
        hisobot["amallar"].append({"kod": kod, "tavsif": tavsif,
                                   "holat": holat, "izoh": izoh})

    conn = engine.connect()
    trans = conn.begin()
    try:
        conn.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))
        conn.execute(text(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'"))
        hisobot["muhit"] = environment_info(conn)

        # K1 — ustun
        if _column_exists(conn, REF_TABLE, "code"):
            amal("K1", "companies.code ustuni", "ALLAQACHON BOR")
        else:
            conn.execute(text(f"ALTER TABLE {REF_TABLE} ADD COLUMN code VARCHAR(30)"))
            amal("K1", "companies.code ustunini qo'shish", "BAJARILDI")

        # K2 — kod hosil qilish (faqat bo'sh bo'lganlarga)
        rows = conn.execute(text(
            f"SELECT id, name, code FROM {REF_TABLE} ORDER BY id")).all()
        band = {r[2] for r in rows if r[2]}
        yangilandi = 0
        for r in rows:
            if r[2]:
                continue
            asos = _kod_yasa(r[1] or f"KORXONA-{r[0]}")
            kod, n = asos, 1
            while kod in band:
                n += 1
                kod = f"{asos[:26]}-{n}"
            band.add(kod)
            conn.execute(text(f"UPDATE {REF_TABLE} SET code = :k WHERE id = :i"),
                         {"k": kod, "i": r[0]})
            amal("K2", f"Korxona #{r[0]} ({r[1]})", "KOD BERILDI", kod)
            yangilandi += 1
        if not yangilandi:
            amal("K2", "Kod hosil qilish", "KERAK EMAS", "hammasida kod bor")

        # K3 — bo'sh qolmasligi (TO'XTATUVCHI)
        bosh = conn.execute(text(
            f"SELECT COUNT(*) FROM {REF_TABLE} WHERE code IS NULL OR code = ''")).scalar()
        if bosh:
            raise _MigrationStop(f"K3: {bosh} ta korxona kodsiz qoldi")
        amal("K3", "Kodsiz korxona qolmasligi shart", "OK", "kodsiz=0")

        # K4 — unique indeks
        if _index_exists(conn, "ix_companies_code"):
            amal("K4", "Indeks ix_companies_code", "ALLAQACHON BOR")
        else:
            conn.execute(text(
                f"CREATE UNIQUE INDEX ix_companies_code ON {REF_TABLE} (code)"))
            amal("K4", "Unique indeks ix_companies_code", "BAJARILDI")

        hisobot["oxirgi_holat"] = [
            {"id": r[0], "name": r[1], "code": r[2]}
            for r in conn.execute(text(
                f"SELECT id, name, code FROM {REF_TABLE} ORDER BY id")).all()]

        if dry_run:
            trans.rollback()
            hisobot["natija"] = ("✅ SINOV MUVAFFAQIYATLI — hammasi bajarildi va "
                                 "keyin qaytarib olindi (rollback).")
        else:
            trans.commit()
            hisobot["natija"] = "✅ HAQIQIY MIGRATSIYA BAJARILDI VA SAQLANDI (commit)."
    except _MigrationStop as e:
        trans.rollback()
        hisobot["natija"] = "⛔ TO'XTATILDI — hech narsa o'zgarmadi."
        hisobot["xato"] = str(e)
    except Exception as e:
        trans.rollback()
        if _is_lock_error(e):
            hisobot["natija"] = "⏳ QULF BAND — hech narsa o'zgarmadi."
            hisobot["qulf_tutib_turganlar"] = _blocking_sessions(engine, [REF_TABLE])
        else:
            hisobot["natija"] = "❌ XATO — hech narsa o'zgarmadi (rollback)."
        hisobot["xato"] = f"{type(e).__name__}: {e}"
    finally:
        conn.close()
    return hisobot


# ============================================================
# Terminaldan ishlatish (DATABASE_URL bo'lgan kompyuterda)
#   python saas_migration.py --status
#   python saas_migration.py W2G1 --dry-run
#   python saas_migration.py W2G1 --apply --confirm PENODECORPRO-W2G1
# ============================================================

if __name__ == "__main__":
    import argparse
    import json

    p = argparse.ArgumentParser(description="SaaS migratsiya")
    p.add_argument("kalit", nargs="?", default="W1", help="qadam kaliti (W1, W2G1...)")
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--apply", action="store_true", help="HAQIQIY migratsiya (commit)")
    p.add_argument("--status", action="store_true", help="Faqat holat")
    p.add_argument("--confirm", default="")
    args = p.parse_args()

    from database import engine

    if args.status:
        print(json.dumps(status_report(engine), indent=2, ensure_ascii=False))
    elif args.apply:
        s = _step(args.kalit)
        if not s:
            raise SystemExit(f"⛔ Noma'lum qadam: {args.kalit}")
        if args.confirm != s["tasdiq"]:
            raise SystemExit(f"⛔ --apply uchun --confirm {s['tasdiq']} shart.")
        print(json.dumps(run_step(engine, args.kalit, dry_run=False),
                         indent=2, ensure_ascii=False))
    else:
        print(json.dumps(run_step(engine, args.kalit, dry_run=True),
                         indent=2, ensure_ascii=False))
