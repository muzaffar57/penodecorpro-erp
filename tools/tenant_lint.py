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
    """Qatorni O'RAB turgan funksiya nomi.

    ⚠ 2026-09-21: ilgari eng yaqin `def` olinardi, OTSTUP hisobga
    olinmasdi. Natijada ichki (nested) yordamchi funksiyadan KEYINGI
    kod o'sha ichki funksiyaga tegishli deb belgilanardi — masalan
    `crud.py` dagi `_scoped(q)` dan keyingi hamma narsa.
    """
    qator = tree_lines[lineno - 1] if 0 < lineno <= len(tree_lines) else ""
    otstup = len(qator) - len(qator.lstrip()) if qator.strip() else 10**6
    for i in range(lineno - 1, -1, -1):
        s = tree_lines[i]
        m = re.match(r"(\s*)(?:async\s+)?def\s+(\w+)", s)
        if not m or len(m.group(1)) >= otstup:
            continue
        # Nomzod `def` HAQIQATAN o'rab turibdimi? Agar oralig'ida shu
        # `def` dan chuqur bo'lmagan qator bo'lsa — u tanasi tugagan,
        # demak bizning qator unga tegishli emas (ichki yordamchidan
        # KEYINGI kod holati).
        chek = len(m.group(1))
        oraliq_uzildi = False
        for j in range(i + 1, lineno - 1):
            q = tree_lines[j]
            if q.strip() and (len(q) - len(q.lstrip())) <= chek:
                oraliq_uzildi = True
                break
        if not oraliq_uzildi:
            return m.group(2)
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


def _oramchilar(lines):
    """Shu fayldagi "tenant o'ramchi" funksiyalari.

    Loyihada keng tarqalgan naqsh: `def _oc(q): return q.filter(
    Order.company_id == company_id) if company_id is not None else q`.
    Bunday yordamchiga berilgan so'rov CHEKLANGAN hisoblanadi. Nomlar
    qattiq kodga yozilmaydi — tanasida `company_id` bor va bitta
    argument qabul qiladigan har qanday funksiya shunday deb tanaladi.
    """
    natija = set()
    for i, l in enumerate(lines):
        m = re.match(r"(\s*)def\s+(\w+)\(\s*\w+\s*\)\s*:", l)
        if not m:
            continue
        chek = len(m.group(1))
        tana = []
        for j in range(i + 1, min(i + 8, len(lines))):
            if lines[j].strip() and (len(lines[j]) - len(lines[j].lstrip())) <= chek:
                break
            tana.append(lines[j])
        if "company_id" in "\n".join(tana):
            natija.add(m.group(2))
    return natija


def _funksiya_tanasi(lines, i):
    """`i` qatori tushgan funksiyaning (boshlanish, tugash) chegarasi."""
    bosh = 0
    chek = 0
    for j in range(i, -1, -1):
        m = re.match(r"(\s*)(?:async\s+)?def\s+\w+", lines[j])
        if m:
            bosh, chek = j, len(m.group(1))
            break
    oxir = len(lines)
    for j in range(bosh + 1, len(lines)):
        s = lines[j]
        if not s.strip():
            continue
        otstup = len(s) - len(s.lstrip())
        if otstup <= chek and re.match(r"\s*(?:async\s+)?def\s+\w+|\s*class\s+\w+", s):
            oxir = j
            break
    return bosh, oxir


def _filtrlanganmi(kod, i, zanjir, var, bosh, oxir, oramchilar=()):
    """So'rov korxona bo'yicha cheklanganmi?

    ⚠ 2026-09-21 — bu tekshiruv QAYTA YOZILDI. Eski versiya so'rov
    atrofidagi 12 qatorda `company_id` so'zini qidirardi va u so'z QAYSI
    so'rovga tegishli ekanini ajratmasdi. Mutatsiya bilan isbotlangan:
    `calculate_order_profit` ichiga qo'yilgan haqiqiy filtrsiz
    `db.query(Inventory)` darvozaga UMUMAN ko'rinmasdi, chunki yonida
    BOSHQA so'rovning (`_oq`) qonuniy `company_id` filtri turardi.

    Endi filtr SHU so'rovning o'z zanjirida yoki SHU o'zgaruvchiga
    bog'langan keyingi amalda bo'lishi shart — buning evaziga qidiruv
    oynasi 12 qatordan BUTUN FUNKSIYA TANASIGA kengaytirildi, shunda
    qonuniy "ikki bosqichli" naqsh soxta ogohlantirish bermaydi.
    """
    # 1) so'rovning o'z zanjirida
    if "company_id" in zanjir:
        return True
    # 2) loyihadagi tayyor tenant o'ramchilari
    if re.search(r"_scope\(|_scoped\(|_tenant_filter\(", zanjir):
        return True
    for _o in oramchilar:
        if re.search(rf"\b{re.escape(_o)}\(", zanjir):
            return True
    if not var:
        return False
    tana = "\n".join(kod[bosh:oxir])
    # 3) shu o'zgaruvchiga bog'langan keyingi cheklov
    for naqsh in (
        rf"\b{re.escape(var)}\s*=\s*[^\n]*\b{re.escape(var)}\b[^\n]*company_id",
        rf"\b{re.escape(var)}\s*=\s*(?:_scope|_scoped|_tenant_filter)\(\s*{re.escape(var)}\b",
        rf"\b{re.escape(var)}\s*=\s*{re.escape(var)}\.join\([^\n]*\n?[^\n]*company_id",
        rf"\b{re.escape(var)}\.filter\([^)]*company_id",
    ):
        if re.search(naqsh, tana):
            return True
    # 4) ko'p qatorli zanjir: `var = var.join(...)` dan keyingi qatorda filtr
    for m in re.finditer(rf"\b{re.escape(var)}\s*=\s*{re.escape(var)}\b", tana):
        parcha = tana[m.start():m.start() + 400]
        if "company_id" in parcha.split("\n\n")[0]:
            return True
    return False


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
        # ⚠ kod_lines ustida yuriladi: docstringdagi MISOL kod
        # (masalan `auth.py` dagi ishlatilish namunasi) so'rov emas.
        oramchilar = _oramchilar(kod_lines)
        for i, line in enumerate(kod_lines):
            for m in re.finditer(r"db\.query\(\s*([A-Za-z_]\w*)", line):
                model = m.group(1)
                if model not in tenant_any:
                    continue
                fn = _enclosing_function(lines, i + 1)
                if fn in ALLOW_FUNCTIONS:
                    continue
                # so'rovning O'Z zanjiri (qavslar yopilib, nuqta davom etmaguncha)
                zanjir, depth = "", 0
                for j in range(i, min(i + 20, len(kod_lines))):
                    zanjir += kod_lines[j] + "\n"
                    depth += kod_lines[j].count("(") - kod_lines[j].count(")")
                    keyingi = kod_lines[j + 1].strip() if j + 1 < len(kod_lines) else ""
                    if depth <= 0 and not keyingi.startswith("."):
                        break
                # so'rov qaysi o'zgaruvchiga berilyapti
                var = None
                mv = re.match(r"\s*([A-Za-z_]\w*)\s*=\s*$", line[:m.start()])
                if mv:
                    var = mv.group(1)
                bosh, oxir = _funksiya_tanasi(kod_lines, i)
                if _filtrlanganmi(kod_lines, i, zanjir, var, bosh, oxir, oramchilar):
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

    # ⚠ 2026-09-21 — XRAPOVIK. Ilgari baselineda bor, lekin koddan
    # YO'QOLGAN yozuvlar jimgina qolib ketardi. O'lchandi: tuzatilgan
    # so'rovlar tufayli 16 ta shunday yozuv to'plangan edi (ekranda
    # "156" turardi, kodda haqiqatda 140 ta). Eskirgan yozuv — "bo'sh
    # o'rin": o'sha funksiyaga AYNAN shu filtrsiz so'rov qayta yozilsa,
    # lint uni "ma'lum holat" deb o'tkazib yuborardi. Endi eskirgan
    # yozuv ham darvozani yiqitadi — baseline faqat QISQARA oladi.
    stale = known - Counter(key(x) for x in read_issues)

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
        # ⚠ 2026-09-21: ilgari bu yerda len(known) — ya'ni NOYOB kalitlar
        # soni chiqarardi. Aynan bir xil so'rov bitta funksiyada 2 marta
        # uchrasa, bitta kalitga tushadi va son kamayib ko'rinardi
        # (baseline 156 yozuv → ekranda 153). Darvozaning o'zi to'g'ri
        # ishlardi (Counter sonni ham tutadi), faqat hisobot yolg'on
        # gapirardi. Endi YOZUVLAR soni chiqadi — baseline fayli bilan teng.
        print(f"✓ O'QISH: yangi filtrsiz so'rov yo'q "
              f"(ma'lum holatlar: {sum(known.values())})")

    if stale:
        ok = False
        print(f"\n⛔ BASELINE ESKIRGAN — kodda endi YO'Q ({sum(stale.values())} ta):")
        for k, v in sorted(stale.items()):
            print(f"   {v}x {k[:150]}")
        print("\n   Bu yaxshi xabar (so'rov tuzatilgan), lekin o'rni yopilishi")
        print("   kerak: python tools/tenant_lint.py --update")

    print("\n" + ("✅ TOZA" if ok else "❌ MUAMMO TOPILDI"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
