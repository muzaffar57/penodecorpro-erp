#!/usr/bin/env python3
"""
tenant_lint.py — SaaS ko'p-tenantlilik uchun statik tekshiruvchi.

NIMA UCHUN KERAK
----------------
M4–M8 davomida BITTA xato sinfi besh marta takrorlandi: yangi (yoki eski)
kod `company_id` ni unutadi, natijada bir korxonaning ma'lumoti boshqasiga
tushadi yoki boshqasiga ko'rinadi. Har safar uni qo'lda, tasodifan topdik.

Bu skript o'sha qidiruvni avtomatlashtiradi. U ikki xil xatoni qidiradi:

  1) YOZISH — tenant "ildiz" modeli (`company_id` ustuni BOR, lekin
     `models._TENANT_RULES` da ota-zanjiri YO'Q) `company_id` siz
     yaratilyapti. Bunday yozuv bazada NOT NULL xatosi beradi yoki
     (agar default qaytarilsa) jimgina 1-korxonaga tushadi.

  2) O'QISH — tenant modeli bo'yicha `db.query(...)` korxona filtrisiz.
     Bularning ko'pi qonuniy (ota allaqachon tekshirilgan, ID bo'yicha
     qidiruv va h.k.), shuning uchun MAVJUD holat "baseline" fayliga
     yozib qo'yiladi va faqat YANGI paydo bo'lganlari xato deb belgilanadi.

ISHLATISH
---------
    python tools/tenant_lint.py              # tekshirish (CI uchun)
    python tools/tenant_lint.py --update     # baseline ni yangilash

Chiqish kodi: 0 — toza, 1 — yangi muammo topildi.
"""
import io
import json
import os
import re
import sys
import tokenize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tenant_lint_baseline.json")

SCAN_FILES = ["crud.py", "main.py", "services.py", "auth.py",
              "production_service.py", "production_routes.py"]

# Bu so'rovlarda korxona filtri ATAYLAB yo'q — sabab bilan.
ALLOW_FUNCTIONS = {
    "create_default_admin",          # bootstrap: baza bo'sh, birinchi admin
    "authenticate_user",             # login: hali sessiya yo'q, username global unique
    "_company_of_username",          # login: korxonani ANIQLAYDIGAN funksiyaning o'zi
    "resolve_company_by_code",       # login: korxona kodini qidiradi
    "check_login_rate_limit",        # IP bo'yicha global himoya — ataylab
    "cleanup_expired_sessions",      # tizim: muddati o'tgan sessiyalar
    "get_session_user",              # sessiya token bo'yicha
    "logout_user",
    "check_system_health",           # platforma diagnostikasi (xom SQL, alohida tekshirilgan)
    "export_full_backup",            # tenant filtri `_tenant_filter()` orqali
    "factory_reset_all_data",        # tenant filtri `_tenant_filter()` orqali
    "_tenant_filter",
}


def _load_models():
    """models.py va production_models.py dan model xaritasini tuzadi."""
    src = ""
    for f in ("models.py", "production_models.py"):
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            src += open(p, encoding="utf-8").read() + "\n"

    # _TENANT_RULES — ota-zanjiri bor modellar
    i = src.find("_TENANT_RULES = {")
    j = src.find("\n}", i)
    rules = set(re.findall(r'"(\w+)":', src[i:j])) if i >= 0 else set()

    has_cid, all_models = set(), set()
    for m in re.finditer(r"\nclass (\w+)\(Base\):(.*?)(?=\nclass |\Z)", src, re.S):
        name, body = m.group(1), m.group(2)
        all_models.add(name)
        if "company_id = Column" in body:
            has_cid.add(name)
    return all_models, has_cid, rules


def _enclosing_function(tree_lines, lineno):
    for i in range(lineno - 1, -1, -1):
        s = tree_lines[i]
        m = re.match(r"\s*(?:async\s+)?def\s+(\w+)", s)
        if m:
            return m.group(1)
    return "?"


def _kod_faqat(lines):
    """Izoh va ko'p qatorli satr (docstring) TANASINI bo'sh qatorga
    aylantirgan nusxa qaytaradi.

    `company_id` so'zi docstringda yoki izohda uchrasa, u KOD emas —
    so'rovni filtrlangan deb hisoblashga asos bo'la olmaydi. Bir qatorli
    satr literallari (masalan `"company_id"`) tegilmaydi, chunki ular
    haqiqiy kod qatorining ichida turadi.
    """
    chiqar = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO("\n".join(lines)).readline):
            if tok.type == tokenize.STRING and tok.end[0] > tok.start[0]:
                # ko'p qatorli satr — BIRINCHI qatoridan keyingi hammasi tana
                for ln in range(tok.start[0], tok.end[0] + 1):
                    chiqar.add(ln)
    except Exception:
        # sintaksis buzilgan bo'lsa — hech narsani o'chirmaymiz (xavfsiz tomon)
        return list(lines)
    natija = []
    for i, l in enumerate(lines):
        if (i + 1) in chiqar:
            natija.append("")
        else:
            natija.append(l.split("#")[0])
    return natija


def scan():
    all_models, has_cid, rules = _load_models()
    tenant_roots = has_cid - rules          # company_id SHART, ota yo'q
    tenant_any = has_cid | rules            # umuman tenantga tegishli

    write_issues, read_issues = [], []

    for fname in SCAN_FILES:
        path = os.path.join(ROOT, fname)
        if not os.path.exists(path):
            continue
        lines = open(path, encoding="utf-8").read().split("\n")

        # ⚠ 2026-09-21: `company_id` ni IZOH va DOCSTRING dan hisobga
        # olmaslik uchun "faqat kod" nusxasi tayyorlanadi.
        # Sabab (mutatsiya bilan isbotlangan): `calculate_order_profit`
        # docstringida "M6 — TENANT: company_id berilsa..." deb yozilgan.
        # Shu matn tufayli funksiya boshiga qo'yilgan HAQIQIY filtrsiz
        # `db.query(Inventory)` darvozaga UMUMAN ko'rinmasdi — u na xato
        # deb belgilanardi, na baselinega tushardi.
        kod_lines = _kod_faqat(lines)

        # --- 1) YOZISH: tenant ildiz modeli konstruktorlari ---
        # MUHIM: konstruktor BIR qatorda ham, bir NECHA qatorda ham
        # yozilishi mumkin — ikkalasi ham tekshiriladi. (Birinchi
        # versiyada faqat ko'p qatorli shakl qamralgan edi va o'z
        # sinovimizda bir qatorli regressiya e'tibordan chetda qolgan.)
        for i, line in enumerate(lines):
            for model in tenant_roots:
                if not re.search(rf"(?<![\w.]){model}\s*\(", line):
                    continue
                if "db.query" in line or "isinstance(" in line or "import" in line:
                    continue
                # qavslar shu qatorda yopilsa — bitta qator, aks holda blok
                depth, end = 0, i
                for j in range(i, min(i + 40, len(lines))):
                    depth += lines[j].count("(") - lines[j].count(")")
                    end = j
                    if depth <= 0:
                        break
                block = "\n".join(kod_lines[i:end + 1])
                if "company_id" not in block:
                    fn = _enclosing_function(lines, i + 1)
                    if fn in ALLOW_FUNCTIONS:
                        continue
                    write_issues.append(f"{fname}:{i+1} {model}() — company_id berilmagan (funksiya: {fn})")

        # --- 2) O'QISH: tenant modeli bo'yicha filtrsiz so'rov ---
        for i, line in enumerate(lines):
            for m in re.finditer(r"db\.query\(\s*([A-Za-z_]\w*)", line):
                model = m.group(1)
                if model not in tenant_any:
                    continue
                stmt = "\n".join(kod_lines[max(0, i - 3):i + 9])
                if "company_id" in stmt:
                    continue
                fn = _enclosing_function(lines, i + 1)
                if fn in ALLOW_FUNCTIONS:
                    continue
                # ⚠ 2026-09-21: xabarga SO'ROV MATNINING o'zi ham qo'shiladi.
                # Ilgari kalit faqat (fayl, model, funksiya) edi va qator
                # raqami tashlab yuborilardi — natijada BITTA funksiyadagi
                # bir modelning HAMMA filtrsiz so'rovi bitta kalitga
                # yig'ilardi. Shu sababli baselinega tushgan funksiyaga
                # qo'shilgan YANGI filtrsiz so'rov darvozadan jimgina
                # o'tib ketardi (mutatsiya bilan isbotlangan).
                kod = re.sub(r"\s+", " ", line.strip())[:100]
                read_issues.append(
                    f"{fname}:{i+1} db.query({model}) — korxona filtri yo'q "
                    f"(funksiya: {fn}) │ {kod}")

    return write_issues, read_issues


def main():
    update = "--update" in sys.argv
    write_issues, read_issues = scan()

    base = {"read": []}
    if os.path.exists(BASELINE):
        base = json.load(open(BASELINE, encoding="utf-8"))

    # o'qish muammolarini joy (fayl:qator) emas, MAZMUNI bo'yicha
    # solishtiramiz — qator raqami o'zgarishi soxta ogohlantirish bermasin.
    # ⚠ Lekin SONI ham hisobga olinadi: agar aynan bir xil so'rov bitta
    # funksiyada 2 marta paydo bo'lsa, baselineda 1 ta bo'lsa — bu YANGI
    # muammo. Ilgari faqat "kalit bormi" deb qaralardi va ortiqchasi
    # jimgina o'tib ketardi.
    def key(s):
        return re.sub(r":\d+", ":", s)

    from collections import Counter
    known = Counter(key(x) for x in base.get("read", []))
    korilgan = Counter()
    new_read = []
    for x in read_issues:
        k = key(x)
        korilgan[k] += 1
        if korilgan[k] > known.get(k, 0):
            new_read.append(x)

    if update:
        json.dump({"read": sorted(read_issues)}, open(BASELINE, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"✓ Baseline yangilandi: {len(read_issues)} ta ma'lum o'qish holati")
        return 0

    print("=" * 66)
    print("TENANT LINT — ko'p-tenantlilik statik tekshiruvi")
    print("=" * 66)

    ok = True
    if write_issues:
        ok = False
        print(f"\n⛔ YOZISH — company_id berilmagan ({len(write_issues)} ta):")
        for x in write_issues:
            print("   " + x)
    else:
        print("\n✓ YOZISH: barcha tenant-ildiz konstruktorlari company_id beradi")

    if new_read:
        ok = False
        print(f"\n⛔ O'QISH — YANGI filtrsiz so'rov ({len(new_read)} ta):")
        for x in new_read:
            print("   " + x)
        print("\n   Agar bular ataylab shunday bo'lsa: python tools/tenant_lint.py --update")
    else:
        print(f"✓ O'QISH: yangi filtrsiz so'rov yo'q (ma'lum holatlar: {len(known)})")

    print("\n" + ("✅ TOZA" if ok else "❌ MUAMMO TOPILDI"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
