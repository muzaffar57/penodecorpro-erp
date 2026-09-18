"""
PenoDecorPro ERP — SaaS ko'p-tenantlilik (multi-tenant) migratsiyasi
====================================================================
VAQTINCHALIK MODUL. Migratsiya to'liq tugagach, bu fayl va uning
main.py'dagi include_router qatori olib tashlanadi.

1-QADAM (shu faylda): `users.company_id`
----------------------------------------
Nima uchun eng birinchi shu: hozir `User`da `company_id` yo'q, shuning
uchun so'rov kelganda "bu qaysi korxonaning foydalanuvchisi?" degan
savolga javob beradigan MANBA umuman mavjud emas. Qolgan 44 jadvalning
hammasi shu ustunga tayanadi — shuning uchun poydevor shu.

Ish tartibi (har bir jadval uchun kelishilgan ketma-ketlik):
  A1  ustun qo'shish (NULL bo'lishi mumkin holatda)
  A2  qatorlarni sanash
  A3  backfill (company_id = 1)
  A4  NULL = 0 ekanini tekshirish   <-- shart bajarilmasa TO'XTAYDI
  A5  har bir qiymat companies'da borligini tekshirish  <-- TO'XTATUVCHI
  A6  indeks
  A7  tashqi kalit (FK)
  A8  DEFAULT 1  (eski kod hali company_id yubormaydi — o'tish davri uchun)
  A9  NOT NULL

XAVFSIZLIK:
  * Hammasi BITTA tranzaksiya ichida. Bir joyda xato bo'lsa — hech narsa
    o'zgarmaydi (Postgres'da DDL ham tranzaksiyaga bo'ysunadi).
  * dry_run=True bo'lganda: barcha amallar HAQIQATDAN bajariladi, lekin
    oxirida ROLLBACK qilinadi. Ya'ni bu "taxmin" emas — haqiqiy sinov:
    agar xato bo'ladigan bo'lsa, u SINOVDA ko'rinadi, bazada esa hech
    qanday iz qolmaydi.
  * Idempotent: ikkinchi marta ishga tushirilsa, allaqachon bajarilgan
    amallarni "ALLAQACHON BOR" deb o'tkazib yuboradi.
  * Faqat PostgreSQL'da ishlaydi. Boshqa bazada darhol to'xtaydi.
  * Haqiqiy (dry_run=False) rejim uchun tasdiq so'zi shart.

MUHIM: bu modul faqat `users` jadvaliga tegadi. Boshqa hech qanday
jadval, ustun yoki ma'lumotga qo'l urmaydi.
"""

from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy import text

# ============================================================
# Sozlamalar
# ============================================================

# Haqiqiy (qaytarib bo'lmaydigan) migratsiya uchun majburiy tasdiq so'zi
CONFIRM_PHRASE = "PENODECORPRO-STEP1"

DEFAULT_COMPANY_ID = 1

TABLE = "users"
COLUMN = "company_id"
INDEX_NAME = "ix_users_company_id"        # models.py'dagi index=True bilan bir xil nom
FK_NAME = "users_company_id_fkey"          # Postgres'ning o'z standart nomlash uslubi
REF_TABLE = "companies"


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
    eng boshida shu ma'lumot chiqadi. Migratsiyani bosishdan OLDIN shuni
    o'qib chiqing."""
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
# HOLAT — faqat o'qiydi, hech narsani o'zgartirmaydi
# ============================================================

def status_report(engine) -> dict:
    """1-qadam hozir qaysi bosqichda ekanini ko'rsatadi. To'liq xavfsiz:
    bitta ham yozuv amali bajarilmaydi."""
    with engine.connect() as conn:
        if conn.dialect.name != "postgresql":
            return {
                "qadam": 1,
                "baza_turi": conn.dialect.name,
                "xato": "Bu migratsiya faqat PostgreSQL uchun.",
            }

        meta = _column_meta(conn, TABLE, COLUMN)
        fk = _fk_exists(conn, TABLE, COLUMN)

        total = null_cnt = yetim = None
        if meta:
            total = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar()
            null_cnt = conn.execute(
                text(f"SELECT COUNT(*) FROM {TABLE} WHERE {COLUMN} IS NULL")).scalar()
            if _table_exists(conn, REF_TABLE):
                yetim = conn.execute(text(f"""
                    SELECT COUNT(*) FROM {TABLE} u
                    LEFT JOIN {REF_TABLE} c ON c.id = u.{COLUMN}
                    WHERE u.{COLUMN} IS NOT NULL AND c.id IS NULL
                """)).scalar()

        tugallangan = bool(
            meta and not meta.get("null_bolishi_mumkin")
            and fk and _index_exists(conn, INDEX_NAME)
            and null_cnt == 0 and yetim == 0
        )

        return {
            "qadam": 1,
            "muhit": environment_info(conn),
            "ustun_bor": bool(meta),
            "ustun": meta or None,
            "indeks_bor": _index_exists(conn, INDEX_NAME),
            "tashqi_kalit": fk or None,
            "jami_foydalanuvchi": total,
            "company_id_bosh (NULL)": null_cnt,
            "yetim_company_id": yetim,
            "1_QADAM_TUGALLANGAN": tugallangan,
        }


# ============================================================
# 1-QADAM — asosiy migratsiya
# ============================================================

class _MigrationStop(Exception):
    """To'xtatuvchi shart bajarildi — hammasi bekor qilinadi."""


def run_step1(engine, dry_run: bool = True) -> dict:
    """1-qadamni bajaradi.

    dry_run=True  -> hamma narsa haqiqatdan bajariladi, oxirida ROLLBACK.
    dry_run=False -> COMMIT (qaytarib bo'lmaydi, faqat backupdan tiklash).
    """
    hisobot = {
        "qadam": 1,
        "nomi": "users.company_id + poydevor",
        "rejim": "DRY-RUN (sinov, o'zgarish saqlanmaydi)" if dry_run else "HAQIQIY (COMMIT)",
        "vaqt_utc": datetime.utcnow().isoformat(timespec="seconds"),
        "muhit": {},
        "tekshiruvlar": [],
        "amallar": [],
        "oxirgi_holat": {},
        "natija": "",
        "xato": None,
    }

    def tekshir(kod, tavsif, ok, izoh=""):
        hisobot["tekshiruvlar"].append({
            "kod": kod, "tavsif": tavsif,
            "holat": "OK" if ok else "TO'XTASH", "izoh": izoh,
        })
        if not ok:
            raise _MigrationStop(f"{kod}: {tavsif} — {izoh}")

    def amal(kod, tavsif, holat, izoh=""):
        hisobot["amallar"].append({
            "kod": kod, "tavsif": tavsif, "holat": holat, "izoh": izoh,
        })

    conn = engine.connect()
    trans = conn.begin()
    try:
        # ---------- MUHIT ----------
        hisobot["muhit"] = environment_info(conn)

        # ---------- OLDINDAN TEKSHIRUVLAR ----------
        tekshir("P1", "Baza PostgreSQL bo'lishi shart",
                conn.dialect.name == "postgresql",
                f"topildi: {conn.dialect.name}")

        tekshir("P2", f"'{TABLE}' jadvali mavjud", _table_exists(conn, TABLE))

        tekshir("P3", f"'{REF_TABLE}' jadvali mavjud", _table_exists(conn, REF_TABLE),
                "Production/MRP moduli yaratadi — server bir marta ishga tushgan bo'lishi kerak")

        comp_exists = conn.execute(
            text(f"SELECT 1 FROM {REF_TABLE} WHERE id = :i"),
            {"i": DEFAULT_COMPANY_ID}).scalar()
        tekshir("P4", f"Asosiy korxona (companies.id={DEFAULT_COMPANY_ID}) mavjud",
                bool(comp_exists))

        comp_count = conn.execute(text(f"SELECT COUNT(*) FROM {REF_TABLE}")).scalar()
        hisobot["tekshiruvlar"].append({
            "kod": "P5", "tavsif": "companies jadvalidagi korxonalar soni",
            "holat": "MA'LUMOT", "izoh": str(comp_count),
        })

        # ---------- A1: ustun qo'shish (NULL ruxsat) ----------
        if _column_exists(conn, TABLE, COLUMN):
            amal("A1", f"{TABLE}.{COLUMN} ustunini qo'shish", "ALLAQACHON BOR",
                 str(_column_meta(conn, TABLE, COLUMN)))
        else:
            conn.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} INTEGER"))
            amal("A1", f"{TABLE}.{COLUMN} ustunini qo'shish (NULL ruxsat)", "BAJARILDI")

        # ---------- A2: qatorlarni sanash ----------
        jami = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar()
        bosh = conn.execute(
            text(f"SELECT COUNT(*) FROM {TABLE} WHERE {COLUMN} IS NULL")).scalar()
        amal("A2", "Qatorlarni sanash", "MA'LUMOT",
             f"jami={jami}, company_id bo'sh={bosh}")

        # ---------- A3: backfill ----------
        if bosh:
            r = conn.execute(text(
                f"UPDATE {TABLE} SET {COLUMN} = :cid WHERE {COLUMN} IS NULL"),
                {"cid": DEFAULT_COMPANY_ID})
            amal("A3", f"Bo'sh qatorlarni to'ldirish (company_id={DEFAULT_COMPANY_ID})",
                 "BAJARILDI", f"{r.rowcount} qator yangilandi")
        else:
            amal("A3", "Bo'sh qatorlarni to'ldirish", "KERAK EMAS",
                 "bo'sh qator yo'q")

        # ---------- A4: NULL = 0 (TO'XTATUVCHI) ----------
        qolgan = conn.execute(
            text(f"SELECT COUNT(*) FROM {TABLE} WHERE {COLUMN} IS NULL")).scalar()
        tekshir("A4", "Backfilldan keyin bo'sh (NULL) qator qolmasligi shart",
                qolgan == 0, f"qolgan={qolgan}")

        # ---------- A5: yetim qiymat yo'q (TO'XTATUVCHI) ----------
        yetim = conn.execute(text(f"""
            SELECT COUNT(*) FROM {TABLE} u
            LEFT JOIN {REF_TABLE} c ON c.id = u.{COLUMN}
            WHERE c.id IS NULL
        """)).scalar()
        tekshir("A5", "Har bir company_id companies jadvalida mavjud bo'lishi shart",
                yetim == 0, f"yetim={yetim}")

        # ---------- A6: indeks ----------
        if _index_exists(conn, INDEX_NAME):
            amal("A6", f"Indeks {INDEX_NAME}", "ALLAQACHON BOR")
        else:
            conn.execute(text(
                f"CREATE INDEX {INDEX_NAME} ON {TABLE} ({COLUMN})"))
            amal("A6", f"Indeks {INDEX_NAME} yaratish", "BAJARILDI")

        # ---------- A7: tashqi kalit ----------
        mavjud_fk = _fk_exists(conn, TABLE, COLUMN)
        if mavjud_fk:
            amal("A7", "Tashqi kalit (FK)", "ALLAQACHON BOR",
                 f"{mavjud_fk['nom']} -> {mavjud_fk['bogliq_jadval']}")
        else:
            conn.execute(text(
                f"ALTER TABLE {TABLE} ADD CONSTRAINT {FK_NAME} "
                f"FOREIGN KEY ({COLUMN}) REFERENCES {REF_TABLE} (id)"))
            amal("A7", f"Tashqi kalit {FK_NAME} qo'shish", "BAJARILDI",
                 f"{TABLE}.{COLUMN} -> {REF_TABLE}.id")

        # ---------- A8: DEFAULT (o'tish davri uchun) ----------
        # Nima uchun: baza ustunni NOT NULL qilgandan keyin, lekin kod hali
        # yangilanmagan oraliqda, ESKI kod (auth.create_user) company_id
        # yubormaydi -> INSERT yiqilardi. DEFAULT shu oraliqni yopadi.
        # Haqiqiy ko'p-tenantlilikda bu DEFAULT keyingi bosqichda OLIB
        # TASHLANADI (aks holda unutilgan company_id jimgina 1-korxonaga
        # tushib qoladi — bu ma'lumot sizib chiqishiga olib keladi).
        meta = _column_meta(conn, TABLE, COLUMN)
        if meta.get("default"):
            amal("A8", "Vaqtinchalik DEFAULT", "ALLAQACHON BOR", str(meta["default"]))
        else:
            conn.execute(text(
                f"ALTER TABLE {TABLE} ALTER COLUMN {COLUMN} SET DEFAULT {DEFAULT_COMPANY_ID}"))
            amal("A8", f"Vaqtinchalik DEFAULT {DEFAULT_COMPANY_ID} qo'yish", "BAJARILDI",
                 "o'tish davri uchun; keyingi bosqichda olib tashlanadi")

        # ---------- A9: NOT NULL ----------
        if meta and not meta.get("null_bolishi_mumkin"):
            amal("A9", "NOT NULL", "ALLAQACHON BOR")
        else:
            conn.execute(text(
                f"ALTER TABLE {TABLE} ALTER COLUMN {COLUMN} SET NOT NULL"))
            amal("A9", "Ustunni NOT NULL qilish", "BAJARILDI")

        # ---------- OXIRGI HOLAT ----------
        oxirgi_meta = _column_meta(conn, TABLE, COLUMN)
        oxirgi_fk = _fk_exists(conn, TABLE, COLUMN)
        namuna = [
            {"id": r[0], "username": r[1], "company_id": r[2]}
            for r in conn.execute(text(
                f"SELECT id, username, {COLUMN} FROM {TABLE} ORDER BY id LIMIT 20")).all()
        ]
        hisobot["oxirgi_holat"] = {
            "ustun": oxirgi_meta,
            "indeks": INDEX_NAME if _index_exists(conn, INDEX_NAME) else None,
            "tashqi_kalit": oxirgi_fk or None,
            "jami_foydalanuvchi": jami,
            "foydalanuvchilar (max 20)": namuna,
        }

        if dry_run:
            trans.rollback()
            hisobot["natija"] = (
                "✅ SINOV MUVAFFAQIYATLI — barcha amallar haqiqatdan bajarildi va "
                "keyin TO'LIQ QAYTARIB OLINDI (rollback). Bazada hech qanday "
                "o'zgarish qolmadi. Haqiqiy migratsiyani boshlash mumkin."
            )
        else:
            trans.commit()
            hisobot["natija"] = (
                "✅ HAQIQIY MIGRATSIYA BAJARILDI VA SAQLANDI (commit). "
                "Endi kod fayllarini (models.py, auth.py) yuklash mumkin."
            )

    except _MigrationStop as e:
        trans.rollback()
        hisobot["natija"] = "⛔ TO'XTATILDI — hech narsa o'zgarmadi (rollback)."
        hisobot["xato"] = str(e)
    except Exception as e:
        trans.rollback()
        hisobot["natija"] = "❌ XATO — hech narsa o'zgarmadi (rollback)."
        hisobot["xato"] = f"{type(e).__name__}: {e}"
    finally:
        conn.close()

    return hisobot


# ============================================================
# HTTP yo'llari — brauzerdan ishga tushirish uchun (faqat ADMIN)
# ============================================================

try:
    from fastapi import APIRouter, Depends, HTTPException, Query
    from sqlalchemy.orm import Session

    from database import get_db
    import auth

    router = APIRouter(prefix="/api/saas-migration", tags=["saas-migration"])

    @router.get("/status")
    def api_status(db: Session = Depends(get_db),
                   current_user=Depends(auth.admin_only)):
        """Faqat o'qiydi — 1-qadam qaysi bosqichda ekanini ko'rsatadi."""
        return status_report(db.get_bind())

    @router.post("/step1")
    def api_step1(dry_run: bool = Query(True, description="True = sinov (rollback)"),
                  confirm: str = Query("", description=f"Haqiqiy rejim uchun: {CONFIRM_PHRASE}"),
                  db: Session = Depends(get_db),
                  current_user=Depends(auth.admin_only)):
        """1-qadam. Standart holatda SINOV (dry-run) rejimida ishlaydi.

        Haqiqiy migratsiya uchun IKKALASI ham kerak:
            ?dry_run=false&confirm=PENODECORPRO-STEP1
        """
        if not dry_run and confirm != CONFIRM_PHRASE:
            raise HTTPException(
                status_code=400,
                detail=(f"Haqiqiy migratsiya uchun confirm={CONFIRM_PHRASE} "
                        f"parametri shart. Hech narsa bajarilmadi."),
            )
        return run_step1(db.get_bind(), dry_run=dry_run)

except ImportError:  # pragma: no cover
    # FastAPI yo'q (masalan, faylni to'g'ridan-to'g'ri terminalda ishlatish)
    router = None


# ============================================================
# Terminaldan ishlatish (DATABASE_URL bo'lgan kompyuterda)
#   python saas_migration.py --dry-run
#   python saas_migration.py --apply --confirm PENODECORPRO-STEP1
# ============================================================

if __name__ == "__main__":
    import argparse
    import json

    p = argparse.ArgumentParser(description="SaaS migratsiya — 1-qadam")
    p.add_argument("--dry-run", action="store_true", default=True,
                   help="Sinov rejimi (standart)")
    p.add_argument("--apply", action="store_true",
                   help="HAQIQIY migratsiya (commit)")
    p.add_argument("--status", action="store_true",
                   help="Faqat holatni ko'rsatish")
    p.add_argument("--confirm", default="",
                   help=f"--apply bilan birga: {CONFIRM_PHRASE}")
    args = p.parse_args()

    from database import engine

    if args.status:
        print(json.dumps(status_report(engine), indent=2, ensure_ascii=False))
    elif args.apply:
        if args.confirm != CONFIRM_PHRASE:
            raise SystemExit(f"⛔ --apply uchun --confirm {CONFIRM_PHRASE} shart.")
        print(json.dumps(run_step1(engine, dry_run=False), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(run_step1(engine, dry_run=True), indent=2, ensure_ascii=False))
