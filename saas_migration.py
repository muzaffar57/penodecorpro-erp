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
# Qulf (lock) diagnostikasi
# ============================================================

LOCK_TIMEOUT = "4s"        # jadval qulfini shuncha kutamiz, keyin toza xato
STATEMENT_TIMEOUT = "60s"  # bitta so'rov shundan uzoq cho'zilmasin


def _blocking_sessions(engine) -> list:
    """`users` jadvalini ushlab turgan boshqa ulanishlarni ko'rsatadi.

    ALIHIDA ulanishda ishlaydi — asosiy tranzaksiya xato bo'lgandan keyin
    ham ma'lumot olish uchun."""
    try:
        with engine.connect() as c:
            c.execute(text("SET statement_timeout = '5s'"))
            rows = c.execute(text("""
                SELECT a.pid,
                       a.state,
                       coalesce(a.application_name, '') AS ilova,
                       round(extract(epoch from (now() - a.state_change)))::int AS sekund,
                       left(coalesce(a.query, ''), 100) AS sorov
                FROM pg_locks l
                JOIN pg_stat_activity a ON a.pid = l.pid
                WHERE l.relation = 'users'::regclass
                  AND a.pid <> pg_backend_pid()
                ORDER BY sekund DESC NULLS LAST
                LIMIT 10
            """)).all()
        return [{"pid": r[0], "holat": r[1], "ilova": r[2],
                 "necha_sekund": r[3], "sorov": r[4]} for r in rows]
    except Exception as e:
        return [{"xato": f"aniqlab bo'lmadi: {e}"}]


def _is_lock_error(e: Exception) -> bool:
    m = str(e).lower()
    return ("lock timeout" in m or "55p03" in m or "lock_not_available" in m
            or "canceling statement due to lock" in m)


# ============================================================
# HOLAT — faqat o'qiydi, hech narsani o'zgartirmaydi
# ============================================================

def status_report(engine) -> dict:
    """1-qadam hozir qaysi bosqichda ekanini ko'rsatadi. To'liq xavfsiz:
    bitta ham yozuv amali bajarilmaydi."""
    with engine.connect() as conn:
        try:
            conn.execute(text(f"SET statement_timeout = '{STATEMENT_TIMEOUT}'"))
        except Exception:
            pass
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
        # MUHIM (2026-09-18, real hodisadan keyin qo'shildi): ALTER TABLE
        # jadvalga TO'LIQ EKSKLYUZIV qulf so'raydi. Agar boshqa ulanish o'sha
        # jadvalni ushlab tursa, bizning so'rovimiz navbatga turadi — va
        # navbatdagi eksklyuziv so'rov UNDAN KEYINGI barcha oddiy so'rovlarni
        # ham to'sib qo'yadi, natijada BUTUN SAYT javob bermay qoladi.
        # lock_timeout shuni oldini oladi: 4 soniyada qulf bo'shamasa, toza
        # xato bilan chiqamiz va hech kimni to'smaymiz.
        conn.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))
        conn.execute(text(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'"))

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
        if _is_lock_error(e):
            hisobot["natija"] = (
                "⏳ QULF BAND — 'users' jadvalini boshqa ulanish ushlab turibdi, "
                "shuning uchun to'xtatildi. Bazada hech narsa o'zgarmadi. "
                "ERP'ning ortiqcha tablarini yoping va qaytadan urinib ko'ring; "
                "yordam bermasa Railway'da 'web' xizmatini Restart qiling."
            )
            hisobot["qulf_tutib_turganlar"] = _blocking_sessions(engine)
        else:
            hisobot["natija"] = "❌ XATO — hech narsa o'zgarmadi (rollback)."
        hisobot["xato"] = f"{type(e).__name__}: {e}"
    finally:
        conn.close()

    return hisobot


# ============================================================
# Boshqaruv sahifasi — JAVASCRIPTSIZ (oddiy HTML forma)
# ============================================================
# Nima uchun JS yo'q: brauzerda (kengaytma yoki sayt sozlamasi tufayli)
# JavaScript bloklanib qolishi mumkin — shunda tugmalar jim turadi va
# sabab ko'rinmaydi. Oddiy forma esa har qanday brauzerda, hatto JS
# butunlay o'chirilgan bo'lsa ham ishlaydi. Natijani ham SERVER tayyorlab
# beradi.

_CSS = """
  :root { --bg:#f6f7f9; --card:#fff; --line:#e4e7ec; --text:#101828;
          --muted:#667085; --blue:#2563eb; --red:#b42318; --green:#027a48; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--text);
         font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; }
  .wrap { max-width:960px; margin:0 auto; padding:28px 20px 60px; }
  h1 { font-size:20px; margin:0 0 4px; }
  .sub { color:var(--muted); font-size:13px; margin-bottom:22px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px;
          padding:18px 20px; margin-bottom:16px; }
  .card h2 { font-size:13px; margin:0 0 12px; letter-spacing:.04em; color:var(--muted); }
  .banner { border-radius:10px; padding:12px 14px; font-size:13px; margin-bottom:16px;
            border:1px solid; line-height:1.55; }
  .ok   { background:#ecfdf3; border-color:#abefc6; color:var(--green); }
  .warn { background:#fffaeb; border-color:#fedf89; color:#b54708; }
  .err  { background:#fef3f2; border-color:#fecdca; color:var(--red); }
  table { border-collapse:collapse; width:100%; font-size:13px; }
  td, th { padding:7px 10px; border-bottom:1px solid var(--line); text-align:left;
           vertical-align:top; }
  th { color:var(--muted); font-weight:500; width:210px; }
  tr:last-child td, tr:last-child th { border-bottom:none; }
  .pill { display:inline-block; padding:2px 9px; border-radius:20px; font-size:12px; }
  .p-ok { background:#ecfdf3; color:var(--green); }
  .p-no { background:#f2f4f7; color:var(--muted); }
  .p-er { background:#fef3f2; color:var(--red); }
  button { font:inherit; border-radius:8px; padding:10px 18px; cursor:pointer;
           border:1px solid var(--line); background:#fff; color:var(--text); }
  button:hover { background:#f9fafb; }
  .primary { background:var(--blue); border-color:var(--blue); color:#fff; }
  .primary:hover { background:#1d4ed8; }
  .danger { background:var(--red); border-color:var(--red); color:#fff; }
  .danger:hover { background:#912018; }
  form { display:inline; }
  .row { display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
  input[type=text] { font:inherit; padding:10px 12px; border:1px solid var(--line);
                     border-radius:8px; min-width:300px; }
  pre { background:#0c111d; color:#d1d5db; padding:16px; border-radius:10px;
        overflow:auto; max-height:540px; font-size:12px; line-height:1.55;
        white-space:pre-wrap; word-break:break-word; margin:0; user-select:all; }
  .hint { color:var(--muted); font-size:12px; margin-top:10px; line-height:1.55; }
"""


def _esc(v) -> str:
    import html as _html
    return _html.escape("" if v is None else str(v))


def _env_block(muhit: dict) -> str:
    """Muhit jadvali + yashil/qizil ogohlantirish chizig'i."""
    if not muhit:
        return '<div class="banner warn">Muhit aniqlanmadi.</div>'
    env = str(muhit.get("railway_muhit", "")).lower()
    dom = str(muhit.get("domen", "")).lower()
    if "sinov" in env or "sinov" in dom:
        banner = ('<div class="banner ok">SINOV (staging) muhiti — ishlash xavfsiz.</div>')
    else:
        banner = ('<div class="banner err">DIQQAT: bu SINOV muhiti EMAS. '
                  'Haqiqiy migratsiyani bajarmang — avval qaysi muhitda '
                  'ekaningizni tekshiring.</div>')
    qatorlar = "".join(
        f"<tr><th>{_esc(k)}</th><td><b>{_esc(v)}</b></td></tr>"
        for k, v in [
            ("Railway muhiti", muhit.get("railway_muhit")),
            ("Xizmat", muhit.get("railway_xizmat")),
            ("Domen", muhit.get("domen")),
            ("Baza nomi", muhit.get("baza_nomi")),
            ("PostgreSQL", muhit.get("postgres_versiya")),
        ])
    return banner + f'<div class="card"><h2>MUHIT</h2><table>{qatorlar}</table></div>'


def _pill(val, ok_text="BOR", no_text="YO'Q") -> str:
    if val:
        return f'<span class="pill p-ok">{ok_text}</span>'
    return f'<span class="pill p-no">{no_text}</span>'


def _status_block(st: dict) -> str:
    qatorlar = [
        ("users.company_id ustuni", _pill(st.get("ustun_bor"))),
        ("Indeks", _pill(st.get("indeks_bor"))),
        ("Tashqi kalit (FK)", _pill(bool(st.get("tashqi_kalit")))),
        ("Jami foydalanuvchi", _esc(st.get("jami_foydalanuvchi"))),
        ("company_id bo'sh (NULL)", _esc(st.get("company_id_bosh (NULL)"))),
        ("Yetim company_id", _esc(st.get("yetim_company_id"))),
        ("1-QADAM TUGALLANGANMI",
         _pill(st.get("1_QADAM_TUGALLANGAN"), "HA", "HALI YO'Q")),
    ]
    body = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in qatorlar)
    return f'<div class="card"><h2>HOZIRGI HOLAT</h2><table>{body}</table></div>'


def _report_block(rep: dict) -> str:
    """Migratsiya hisobotini o'qiladigan ko'rinishda chiqaradi."""
    import json as _json
    if not rep:
        return ""
    natija = rep.get("natija", "")
    klass = "ok" if natija.startswith("✅") else ("err" if natija else "warn")
    qismlar = [f'<div class="banner {klass}">{_esc(natija)}</div>']
    if rep.get("xato"):
        qismlar.append(f'<div class="banner err">Sabab: {_esc(rep["xato"])}</div>')

    t = "".join(
        f'<tr><th>{_esc(x.get("kod"))}</th><td>{_esc(x.get("tavsif"))}</td>'
        f'<td><b>{_esc(x.get("holat"))}</b></td><td>{_esc(x.get("izoh"))}</td></tr>'
        for x in rep.get("tekshiruvlar", []))
    a = "".join(
        f'<tr><th>{_esc(x.get("kod"))}</th><td>{_esc(x.get("tavsif"))}</td>'
        f'<td><b>{_esc(x.get("holat"))}</b></td><td>{_esc(x.get("izoh"))}</td></tr>'
        for x in rep.get("amallar", []))
    if t:
        qismlar.append(f'<div class="card"><h2>TEKSHIRUVLAR</h2><table>{t}</table></div>')
    if a:
        qismlar.append(f'<div class="card"><h2>AMALLAR ({_esc(rep.get("rejim"))})</h2>'
                       f'<table>{a}</table></div>')

    blk = rep.get("qulf_tutib_turganlar")
    if blk:
        rows = "".join(
            "<tr><th>{}</th><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                _esc(x.get("pid")), _esc(x.get("holat")),
                _esc(str(x.get("necha_sekund")) + " sek" if x.get("necha_sekund") is not None else ""),
                _esc(x.get("sorov") or x.get("xato")))
            for x in blk)
        qismlar.append('<div class="card"><h2>JADVALNI USHLAB TURGAN ULANISHLAR</h2>'
                       '<table><tr><th>PID</th><td><b>holat</b></td><td><b>qancha vaqt</b></td>'
                       f'<td><b>so\'rov</b></td></tr>{rows}</table></div>')

    xom = _json.dumps(rep, indent=2, ensure_ascii=False)
    qismlar.append('<div class="card"><h2>TO\'LIQ HISOBOT (nusxalash uchun)</h2>'
                   f'<pre>{_esc(xom)}</pre>'
                   '<div class="hint">Matn ustiga bosib, Ctrl+A / Ctrl+C bilan '
                   'nusxalashingiz mumkin.</div></div>')
    return "".join(qismlar)


def _render_page(status: dict, report: dict = None, xabar: str = "") -> str:
    muhit = (report or {}).get("muhit") or (status or {}).get("muhit")
    ogoh = f'<div class="banner err">{_esc(xabar)}</div>' if xabar else ""
    return f"""<!DOCTYPE html>
<html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SaaS migratsiya — 1-qadam</title><style>{_CSS}</style></head><body>
<div class="wrap">
  <h1>SaaS ko'p-tenantlilik migratsiyasi — 1-qadam</h1>
  <div class="sub">users.company_id + poydevor &middot; vaqtinchalik sahifa,
    migratsiya tugagach olib tashlanadi</div>
  {ogoh}
  {_env_block(muhit)}
  {_status_block(status or {})}

  <div class="card">
    <h2>AMALLAR</h2>
    <div class="row">
      <form method="get" action="/saas-migratsiya">
        <button type="submit">Holatni yangilash</button>
      </form>
      <form method="post" action="/saas-migratsiya/sinov">
        <button type="submit" class="primary">SINOV (dry-run)</button>
      </form>
    </div>
    <div class="hint">SINOV barcha amallarni haqiqatdan bajaradi, so'ng to'liq
      qaytarib oladi (rollback). Bazada hech qanday o'zgarish qolmaydi.</div>
  </div>

  <div class="card">
    <h2>HAQIQIY MIGRATSIYA</h2>
    <form method="post" action="/saas-migratsiya/haqiqiy">
      <div class="row">
        <input type="text" name="confirm" placeholder="Tasdiq so'zini kiriting"
               autocomplete="off">
        <button type="submit" class="danger">Haqiqiy migratsiyani bajarish</button>
      </div>
    </form>
    <div class="hint">Tasdiq so'zi noto'g'ri bo'lsa, server hech narsa
      bajarmaydi. Bu amal qaytarib bo'lmaydi — orqaga qaytish faqat
      backupdan tiklash orqali.</div>
  </div>

  {_report_block(report)}
</div></body></html>"""


# ============================================================
# HTTP yo'llari — brauzerdan ishga tushirish uchun (faqat ADMIN)
# ============================================================

try:
    from fastapi import APIRouter, Depends, HTTPException, Query, Form
    from fastapi.responses import HTMLResponse
    from sqlalchemy.orm import Session

    from database import get_db
    import auth

    # DIQQAT: prefix ATAYLAB yo'q — boshqaruv SAHIFASI /api/ dan tashqarida
    # bo'lishi kerak (main.py'dagi 401 -> /login yo'naltirishi faqat /api/
    # BO'LMAGAN yo'llarda ishlaydi; shunda sessiya tugasa foydalanuvchi xom
    # JSON emas, login sahifasini ko'radi).
    router = APIRouter(tags=["saas-migration"])

    # ---------- MUHIM: so'rovning O'Z tranzaksiyasini yopish ----------

    def _release(db) -> object:
        """Migratsiyadan OLDIN, shu so'rovning o'z sessiyasini yopadi.

        2026-09-18, real hodisadan keyin qo'shildi. Muammo: FastAPI har bir
        so'rovda `get_db` orqali sessiya ochadi, `auth.admin_only` esa shu
        sessiya bilan `users` jadvalidan foydalanuvchini o'qiydi. SQLAlchemy
        bu tranzaksiyani so'rov TUGAGUNCHA ochiq ushlab turadi ("idle in
        transaction") — va u `users` ustida ACCESS SHARE qulfini tutadi.

        `ALTER TABLE users` esa ACCESS EXCLUSIVE qulf so'raydi. Natijada
        migratsiya O'ZINING so'rovi tufayli qulfni HECH QACHON ololmasdi —
        o'z-o'zini bloklash. Undan ham yomoni: navbatda turgan eksklyuziv
        so'rov undan keyingi barcha oddiy so'rovlarni ham to'sib qo'yardi,
        ya'ni butun sayt javob bermay qolardi.

        Yechim: auth tekshiruvi tugagach, tranzaksiyani darhol yopamiz.
        Hech narsa yo'qolmaydi — u faqat O'QIGAN edi."""
        engine = db.get_bind()
        try:
            db.rollback()   # ochiq tranzaksiyani yopadi -> qulf bo'shaydi
            db.close()      # ulanishni hovuzga qaytaradi
        except Exception:
            pass
        return engine

    # ---------- JSON API (dastur/skript uchun) ----------

    @router.get("/api/saas-migration/status")
    def api_status(db: Session = Depends(get_db),
                   current_user=Depends(auth.admin_only)):
        """Faqat o'qiydi — 1-qadam qaysi bosqichda ekanini ko'rsatadi."""
        return status_report(db.get_bind())

    @router.post("/api/saas-migration/step1")
    def api_step1(dry_run: bool = Query(True, description="True = sinov (rollback)"),
                  confirm: str = Query("", description=f"Haqiqiy rejim uchun: {CONFIRM_PHRASE}"),
                  db: Session = Depends(get_db),
                  current_user=Depends(auth.admin_only)):
        """Haqiqiy migratsiya uchun: ?dry_run=false&confirm=<tasdiq so'zi>"""
        if not dry_run and confirm != CONFIRM_PHRASE:
            raise HTTPException(
                status_code=400,
                detail=(f"Haqiqiy migratsiya uchun confirm={CONFIRM_PHRASE} "
                        f"parametri shart. Hech narsa bajarilmadi."),
            )
        return run_step1(_release(db), dry_run=dry_run)

    # ---------- HTML sahifa (JavaScriptsiz) ----------

    @router.get("/saas-migratsiya", response_class=HTMLResponse)
    def panel_page(db: Session = Depends(get_db),
                   current_user=Depends(auth.admin_only)):
        return HTMLResponse(_render_page(status_report(_release(db))))

    @router.post("/saas-migratsiya/sinov", response_class=HTMLResponse)
    def panel_dry_run(db: Session = Depends(get_db),
                      current_user=Depends(auth.admin_only)):
        engine = _release(db)
        rep = run_step1(engine, dry_run=True)
        return HTMLResponse(_render_page(status_report(engine), rep))

    @router.post("/saas-migratsiya/haqiqiy", response_class=HTMLResponse)
    def panel_apply(confirm: str = Form(""),
                    db: Session = Depends(get_db),
                    current_user=Depends(auth.admin_only)):
        engine = _release(db)
        if confirm.strip() != CONFIRM_PHRASE:
            return HTMLResponse(_render_page(
                status_report(engine), None,
                "Tasdiq so'zi noto'g'ri — hech narsa bajarilmadi."))
        rep = run_step1(engine, dry_run=False)
        return HTMLResponse(_render_page(status_report(engine), rep))

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
