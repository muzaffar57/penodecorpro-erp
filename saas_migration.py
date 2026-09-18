"""
PenoDecorPro ERP — SaaS ko'p-tenantlilik (multi-tenant) migratsiyasi
====================================================================
VAQTINCHALIK MODUL. Migratsiya to'liq tugagach, bu fayl va uning
main.py'dagi include_router qatori olib tashlanadi.

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
]


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
            jadvallar = [_table_status(conn, t) for t in s["jadvallar"]]
            qadamlar.append({
                "kalit": s["kalit"], "nomi": s["nomi"], "izoh": s["izoh"],
                "tasdiq": s["tasdiq"], "jadvallar": jadvallar,
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
            if bosh:
                r = conn.execute(text(
                    f"UPDATE {t} SET company_id = :cid WHERE company_id IS NULL"),
                    {"cid": DEFAULT_COMPANY_ID})
                amal(t, "A3", f"Bo'sh qatorlarni to'ldirish (company_id={DEFAULT_COMPANY_ID})",
                     "BAJARILDI", f"{r.rowcount} qator yangilandi")
            else:
                amal(t, "A3", "Bo'sh qatorlarni to'ldirish", "KERAK EMAS",
                     "bo'sh qator yo'q")

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


def run_step1(engine, dry_run: bool = True) -> dict:
    """Orqaga moslik uchun (eski nom)."""
    return run_step(engine, "W1", dry_run=dry_run)


# ============================================================
# Boshqaruv sahifasi — JAVASCRIPTSIZ (oddiy HTML forma)
# ============================================================
# Nima uchun JS yo'q: brauzerda (kengaytma yoki sayt sozlamasi tufayli)
# JavaScript bloklanib qolishi mumkin — shunda tugmalar jim turadi va
# sabab ko'rinmaydi. Oddiy forma har qanday brauzerda ishlaydi.

_CSS = """
  :root { --bg:#f6f7f9; --card:#fff; --line:#e4e7ec; --text:#101828;
          --muted:#667085; --blue:#2563eb; --red:#b42318; --green:#027a48; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--text);
         font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; }
  .wrap { max-width:1000px; margin:0 auto; padding:28px 20px 60px; }
  h1 { font-size:20px; margin:0 0 4px; }
  .sub { color:var(--muted); font-size:13px; margin-bottom:22px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px;
          padding:18px 20px; margin-bottom:16px; }
  .card h2 { font-size:12px; margin:0 0 4px; letter-spacing:.06em; color:var(--muted); }
  .card h3 { font-size:15px; margin:0 0 6px; }
  .banner { border-radius:10px; padding:12px 14px; font-size:13px; margin-bottom:16px;
            border:1px solid; line-height:1.55; }
  .ok   { background:#ecfdf3; border-color:#abefc6; color:var(--green); }
  .warn { background:#fffaeb; border-color:#fedf89; color:#b54708; }
  .err  { background:#fef3f2; border-color:#fecdca; color:var(--red); }
  table { border-collapse:collapse; width:100%; font-size:13px; margin-top:10px; }
  td, th { padding:7px 10px; border-bottom:1px solid var(--line); text-align:left;
           vertical-align:top; }
  th { color:var(--muted); font-weight:500; }
  tr:last-child td, tr:last-child th { border-bottom:none; }
  .pill { display:inline-block; padding:2px 9px; border-radius:20px; font-size:12px; }
  .p-ok { background:#ecfdf3; color:var(--green); }
  .p-no { background:#f2f4f7; color:var(--muted); }
  button { font:inherit; border-radius:8px; padding:10px 18px; cursor:pointer;
           border:1px solid var(--line); background:#fff; color:var(--text); }
  button:hover { background:#f9fafb; }
  .primary { background:var(--blue); border-color:var(--blue); color:#fff; }
  .primary:hover { background:#1d4ed8; }
  .danger { background:var(--red); border-color:var(--red); color:#fff; }
  .danger:hover { background:#912018; }
  form { display:inline; }
  .row { display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-top:12px; }
  input[type=text] { font:inherit; padding:10px 12px; border:1px solid var(--line);
                     border-radius:8px; min-width:280px; }
  pre { background:#0c111d; color:#d1d5db; padding:16px; border-radius:10px;
        overflow:auto; max-height:520px; font-size:12px; line-height:1.55;
        white-space:pre-wrap; word-break:break-word; margin:0; user-select:all; }
  .hint { color:var(--muted); font-size:12px; margin-top:10px; line-height:1.55; }
  .done { opacity:.72; }
"""


def _esc(v) -> str:
    import html as _html
    return _html.escape("" if v is None else str(v))


def _pill(val, ok_text="BOR", no_text="YO'Q") -> str:
    k = "p-ok" if val else "p-no"
    return f'<span class="pill {k}">{ok_text if val else no_text}</span>'


def _env_block(muhit: dict) -> str:
    if not muhit:
        return '<div class="banner warn">Muhit aniqlanmadi.</div>'
    env = str(muhit.get("railway_muhit", "")).lower()
    dom = str(muhit.get("domen", "")).lower()
    if "sinov" in env or "sinov" in dom:
        banner = '<div class="banner ok">SINOV (staging) muhiti — ishlash xavfsiz.</div>'
    else:
        banner = ('<div class="banner err">DIQQAT: bu SINOV muhiti EMAS. '
                  'Haqiqiy migratsiyani bajarmang — avval qaysi muhitda '
                  'ekaningizni tekshiring.</div>')
    rows = "".join(f"<tr><th>{_esc(k)}</th><td><b>{_esc(v)}</b></td></tr>" for k, v in [
        ("Railway muhiti", muhit.get("railway_muhit")),
        ("Xizmat", muhit.get("railway_xizmat")),
        ("Domen", muhit.get("domen")),
        ("Baza nomi", muhit.get("baza_nomi")),
        ("PostgreSQL", muhit.get("postgres_versiya"))])
    return banner + f'<div class="card"><h2>MUHIT</h2><table>{rows}</table></div>'


def _step_card(q: dict) -> str:
    """Bitta qadam: holat jadvali + tugmalar."""
    rows = ""
    for j in q["jadvallar"]:
        if not j.get("mavjud"):
            rows += (f'<tr><th>{_esc(j["jadval"])}</th><td colspan="6">'
                     f'<span class="pill p-no">JADVAL YO\'Q</span></td></tr>')
            continue
        rows += (f'<tr><th>{_esc(j["jadval"])}</th>'
                 f'<td>{_pill(j["ustun_bor"])}</td>'
                 f'<td>{_pill(j["indeks_bor"])}</td>'
                 f'<td>{_pill(bool(j["tashqi_kalit"]))}</td>'
                 f'<td>{_esc(j["qatorlar"])}</td>'
                 f'<td>{_esc(j["bosh_NULL"])}</td>'
                 f'<td>{_pill(j["tugallangan"], "HA", "YO\'Q")}</td></tr>')

    bosh = ('<tr><th>jadval</th><th>ustun</th><th>indeks</th><th>FK</th>'
            '<th>qatorlar</th><th>bo\'sh</th><th>tugallangan</th></tr>')

    if q["tugallangan"]:
        tugma = ('<div class="row"><span class="pill p-ok">BU QADAM TUGALLANGAN</span>'
                 f'<form method="post" action="/saas-migratsiya/sinov/{_esc(q["kalit"])}">'
                 '<button type="submit">Qayta tekshirish (sinov)</button></form></div>')
    else:
        tugma = (
            f'<div class="row">'
            f'<form method="post" action="/saas-migratsiya/sinov/{_esc(q["kalit"])}">'
            f'<button type="submit" class="primary">SINOV (dry-run)</button></form>'
            f'</div>'
            f'<form method="post" action="/saas-migratsiya/haqiqiy/{_esc(q["kalit"])}">'
            f'<div class="row"><input type="text" name="confirm" autocomplete="off" '
            f'placeholder="Tasdiq so\'zi"> '
            f'<button type="submit" class="danger">Haqiqiy migratsiya</button></div></form>'
            f'<div class="hint">Tasdiq so\'zi: <b>{_esc(q["tasdiq"])}</b> — '
            f'har bir qadamning o\'z so\'zi bor, adashib bosilmasin uchun.</div>')

    klass = "card done" if q["tugallangan"] else "card"
    return (f'<div class="{klass}"><h2>{_esc(q["kalit"])}</h2>'
            f'<h3>{_esc(q["nomi"])}</h3>'
            f'<div class="hint" style="margin-top:0">{_esc(q["izoh"])}</div>'
            f'<table>{bosh}{rows}</table>{tugma}</div>')


def _report_block(rep: dict) -> str:
    import json as _json
    if not rep:
        return ""
    natija = rep.get("natija", "")
    klass = "ok" if natija.startswith("✅") else ("err" if natija else "warn")
    out = [f'<div class="banner {klass}">{_esc(natija)}</div>']
    if rep.get("xato"):
        out.append(f'<div class="banner err">Sabab: {_esc(rep["xato"])}</div>')

    t = "".join(f'<tr><th>{_esc(x.get("kod"))}</th><td>{_esc(x.get("tavsif"))}</td>'
                f'<td><b>{_esc(x.get("holat"))}</b></td><td>{_esc(x.get("izoh"))}</td></tr>'
                for x in rep.get("tekshiruvlar", []))
    if t:
        out.append(f'<div class="card"><h2>TEKSHIRUVLAR</h2><table>{t}</table></div>')

    a = "".join(f'<tr><th>{_esc(x.get("jadval"))}</th><td>{_esc(x.get("kod"))}</td>'
                f'<td>{_esc(x.get("tavsif"))}</td><td><b>{_esc(x.get("holat"))}</b></td>'
                f'<td>{_esc(x.get("izoh"))}</td></tr>'
                for x in rep.get("amallar", []))
    if a:
        out.append(f'<div class="card"><h2>AMALLAR ({_esc(rep.get("rejim"))})</h2>'
                   f'<table>{a}</table></div>')

    blk = rep.get("qulf_tutib_turganlar")
    if blk:
        r = "".join("<tr><th>{}</th><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            _esc(x.get("pid")), _esc(x.get("holat")), _esc(x.get("jadval")),
            _esc(f'{x.get("necha_sekund")} sek' if x.get("necha_sekund") is not None else ""),
            _esc(x.get("sorov") or x.get("xato"))) for x in blk)
        out.append('<div class="card"><h2>JADVALNI USHLAB TURGAN ULANISHLAR</h2>'
                   f'<table>{r}</table></div>')

    xom = _json.dumps(rep, indent=2, ensure_ascii=False)
    out.append('<div class="card"><h2>TO\'LIQ HISOBOT (nusxalash uchun)</h2>'
               f'<pre>{_esc(xom)}</pre>'
               '<div class="hint">Matn ustiga bosib, Ctrl+A / Ctrl+C bilan '
               'nusxalashingiz mumkin.</div></div>')
    return "".join(out)


def _render_page(status: dict, report: dict = None, xabar: str = "") -> str:
    muhit = (report or {}).get("muhit") or (status or {}).get("muhit")
    ogoh = f'<div class="banner err">{_esc(xabar)}</div>' if xabar else ""
    qadamlar = "".join(_step_card(q) for q in (status or {}).get("qadamlar", []))
    return f"""<!DOCTYPE html>
<html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SaaS migratsiya</title><style>{_CSS}</style></head><body>
<div class="wrap">
  <h1>SaaS ko'p-tenantlilik migratsiyasi</h1>
  <div class="sub">vaqtinchalik sahifa &middot; migratsiya tugagach olib tashlanadi</div>
  {ogoh}
  {_env_block(muhit)}
  <form method="get" action="/saas-migratsiya">
    <button type="submit">Holatni yangilash</button></form>
  {qadamlar}
  {_report_block(report)}
</div></body></html>"""


# ============================================================
# HTTP yo'llari — faqat ADMIN
# ============================================================

try:
    from fastapi import APIRouter, Depends, HTTPException, Query, Form
    from fastapi.responses import HTMLResponse
    from sqlalchemy.orm import Session

    from database import get_db
    import auth

    # prefix ATAYLAB yo'q — sahifa /api/ dan tashqarida bo'lishi kerak
    # (main.py'dagi 401 -> /login yo'naltirishi shunda ishlaydi).
    router = APIRouter(tags=["saas-migration"])

    def _release(db):
        """Migratsiyadan OLDIN, shu so'rovning o'z sessiyasini yopadi.

        2026-09-18, real hodisadan keyin qo'shildi. FastAPI har bir so'rovda
        `get_db` orqali sessiya ochadi, `auth.admin_only` esa shu sessiya
        bilan `users` dan o'qiydi. SQLAlchemy bu tranzaksiyani so'rov
        TUGAGUNCHA ochiq ushlaydi ("idle in transaction") va ACCESS SHARE
        qulfini tutadi. ALTER TABLE esa ACCESS EXCLUSIVE so'raydi —
        natijada migratsiya O'ZINING so'rovi tufayli qulfni hech qachon
        ololmasdi, va navbatdagi eksklyuziv so'rov butun saytni to'sib
        qo'yardi. Yechim: auth tugagach tranzaksiyani darhol yopamiz."""
        engine = db.get_bind()
        try:
            db.rollback()
            db.close()
        except Exception:
            pass
        return engine

    # ---------- JSON API ----------

    @router.get("/api/saas-migration/status")
    def api_status(db: Session = Depends(get_db),
                   current_user=Depends(auth.admin_only)):
        return status_report(_release(db))

    @router.post("/api/saas-migration/step/{kalit}")
    def api_step(kalit: str, dry_run: bool = Query(True),
                 confirm: str = Query(""),
                 db: Session = Depends(get_db),
                 current_user=Depends(auth.admin_only)):
        s = _step(kalit)
        if not s:
            raise HTTPException(status_code=404, detail=f"Noma'lum qadam: {kalit}")
        if not dry_run and confirm != s["tasdiq"]:
            raise HTTPException(
                status_code=400,
                detail=f"Haqiqiy migratsiya uchun confirm={s['tasdiq']} shart. "
                       f"Hech narsa bajarilmadi.")
        return run_step(_release(db), kalit, dry_run=dry_run)

    # ---------- HTML sahifa (JavaScriptsiz) ----------

    @router.get("/saas-migratsiya", response_class=HTMLResponse)
    def panel_page(db: Session = Depends(get_db),
                   current_user=Depends(auth.admin_only)):
        return HTMLResponse(_render_page(status_report(_release(db))))

    @router.post("/saas-migratsiya/sinov/{kalit}", response_class=HTMLResponse)
    def panel_dry_run(kalit: str, db: Session = Depends(get_db),
                      current_user=Depends(auth.admin_only)):
        engine = _release(db)
        if not _step(kalit):
            return HTMLResponse(_render_page(status_report(engine), None,
                                             f"Noma'lum qadam: {kalit}"))
        rep = run_step(engine, kalit, dry_run=True)
        return HTMLResponse(_render_page(status_report(engine), rep))

    @router.post("/saas-migratsiya/haqiqiy/{kalit}", response_class=HTMLResponse)
    def panel_apply(kalit: str, confirm: str = Form(""),
                    db: Session = Depends(get_db),
                    current_user=Depends(auth.admin_only)):
        engine = _release(db)
        s = _step(kalit)
        if not s:
            return HTMLResponse(_render_page(status_report(engine), None,
                                             f"Noma'lum qadam: {kalit}"))
        if confirm.strip() != s["tasdiq"]:
            return HTMLResponse(_render_page(
                status_report(engine), None,
                f"Tasdiq so'zi noto'g'ri ({s['kalit']}) — hech narsa bajarilmadi."))
        rep = run_step(engine, kalit, dry_run=False)
        return HTMLResponse(_render_page(status_report(engine), rep))

except ImportError:  # pragma: no cover
    router = None


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
