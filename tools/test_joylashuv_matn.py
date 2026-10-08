#!/usr/bin/env python3
"""
test_joylashuv_matn.py — kech132 (zip 156): foydalanuvchiga ko'rinadigan matnda JOYLASHUV so'zlari yo'q (kech127 / kech130 qoidasi).

NEGA: bir sahifa uch xil kenglikda ochiladi (kompyuter ~1440 px, ilova yon paneli ~760 px, telefon ~390 px). Kompyuterda yonma-yon
turgan bloklar telefonda ustma-ust tushadi, sahifa tugmalari yuqori panelda yoki «···» ichida bo'ladi — «pastdagi qizil tugma»,
«yuqoridagi filtr», «o'ngdagi ro'yxat» kabi matn bir kenglikda to'g'ri, boshqasida noto'g'ri. Shuning uchun TUGMA, MAYDON, FILTR,
BO'LIM, MENYU BANDI — faqat NOMI bilan ataladi («🔄 Botni asl holatiga qaytarish» tugmasi, «Partiya hajmi (kg)»).
RUXSAT: «Quyidagi …:» — SHU xabar / oyna / blok ichida darhol keladigan ro'yxat, qiymat yoki maydonlar uchun (ma'nosi «keyingi» —
o'qish tartibi har kenglikda bir xil). Bunday joylar `RUXSAT` ro'yxatida — fayl + aniq bo'lak + sabab; yangi joylashuv so'zi
qo'shilsa — sinov yiqiladi (nomi bilan yozing yoki, rostdan ham shu xabar ichidagi ketma-ketlik bo'lsa, ro'yxatga sababi bilan).

NIMA TEKSHIRILADI (statik — server / baza kerak emas):
  S — skaner o'zi (soxta kirishlarda): Jinja / HTML / CSS / JS izohlari va JS kodi (o'zgaruvchi nomi) o'tkaziladi; HTML matni va
      atributi, JS satrlari ('…', "…", `…` va uning ${…} ichidagi satrlar), Python satrlari (hujjat satri / docstring — EMAS) ushlanadi;
      katta-kichik harf va o' ning hamma yozilishi (o'  oʻ  o’  o`); ro'yxatda yo'q so'zlar («ustida», «pastga», «pastki») ushlanmaydi.
  J — butun daraxt: templates/*.html, static/**/*.js, ildizdagi *.py — joylashuv so'zi faqat RUXSAT dagi joylarda; RUXSAT dagi har
      yozuv HALI bor (eskirgani — yiqiladi); shablon / JS yozuvlari faqat «quyi…» (ketma-ketlik) bo'lishi mumkin.
  T — zip 156 tuzatishlari: yangi matnlar bor, eskilari yo'q; matndagi NOMLAR haqiqiy tugma / maydon / bo'lim / menyu nomi bilan AYNAN.
REJIM: faqat fayllar (SQLite / PG farqi yo'q). Asl kodga (zip 155) qarshi QULAMAYDI — J1 va T bo'limi yiqiladi.
ISHLATISH: python3 tools/test_joylashuv_matn.py
"""
import os
import re
import sys
import ast

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:4000]}")


def section(t):
    print(f"\n--- {t} ---")


# Joylashuv so'zlari: past / yuqori / quyi / tepa / chap / o'ng + da / dagi / dan (…lar, …cha ham), yon / ost + ida (…gi).
# «ustida» (ustida ishlash, ustiga yozish), «pastga» / «yuqoriga» (yaxlitlash yo'nalishi), «pastki» (CSS sinf nomi) — ATAYLAB yo'q.
JOY = re.compile(r"(?<![A-Za-z])((?:past|yuqori|quyi|tepa|chap|o[ʻ’‘'`]ng)(?:da|dagi|dan)[a-z]*|(?:yon|ost)ida[a-z]*)(?![A-Za-z])",
                 re.I)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
# Skaner: har belgi uchun tur — 'C' izoh / ko'rinmaydi, 'H' HTML matn yoki atribut, 'S' JS satri, 'K' JS kodi, 'R' JS regex.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
def _js(s, start, end, m):
    i, prev = start, ""
    while i < end:
        c, c2 = s[i], s[i:i + 2]
        if c2 == "//":
            j = s.find("\n", i, end)
            j = end if j < 0 else j
            m[i:j] = "C" * (j - i)
            i = j
            continue
        if c2 == "/*":
            j = s.find("*/", i + 2, end)
            j = end if j < 0 else j + 2
            m[i:j] = "C" * (j - i)
            i = j
            continue
        if c in "\"'":
            j = i + 1
            while j < end and s[j] != c and s[j] != "\n":
                j += 2 if s[j] == "\\" else 1
            j = min(j + 1, end)
            m[i:j] = "S" * (j - i)
            i, prev = j, "x"
            continue
        if c == "`":
            m[i] = "S"
            j = i + 1
            while j < end and s[j] != "`":
                if s[j] == "\\":
                    m[j:min(j + 2, end)] = "S" * (min(j + 2, end) - j)
                    j += 2
                    continue
                if s[j:j + 2] == "${":
                    d, k, q = 1, j + 2, None
                    while k < end and d:
                        ch = s[k]
                        if q:
                            if ch == "\\":
                                k += 2
                                continue
                            if ch == q:
                                q = None
                        elif ch in "\"'`":
                            q = ch
                        elif ch == "{":
                            d += 1
                        elif ch == "}":
                            d -= 1
                        k += 1
                    m[j:j + 2] = "KK"
                    _js(s, j + 2, k - 1, m)
                    m[k - 1] = "K"
                    j = k
                    continue
                m[j] = "S"
                j += 1
            if j < end:
                m[j] = "S"
            i, prev = j + 1, "x"
            continue
        if c == "/" and prev in ("", "(", ",", "=", ":", "[", "!", "&", "|", "?", "{", "}", ";", "+", "-", "*", "%", "<", ">",
                                 "~", "^", "r"):
            j, sinf = i + 1, False
            while j < end and s[j] != "\n":
                if s[j] == "\\":
                    j += 2
                    continue
                if s[j] == "[":
                    sinf = True
                elif s[j] == "]":
                    sinf = False
                elif s[j] == "/" and not sinf:
                    break
                j += 1
            j = min(j + 1, end)
            m[i:j] = "R" * (j - i)
            i, prev = j, "x"
            continue
        m[i] = "K"
        if c.isalnum() or c in "_$":
            w = re.match(r"[\w$]+", s[i:end]).group(0)
            m[i:i + len(w)] = "K" * len(w)
            prev = "r" if w in ("return", "typeof", "case", "in", "of", "delete", "void", "throw", "new") else "x"
            i += len(w)
            continue
        if not c.isspace():
            prev = c if c in "(,=:[!&|?{};+-*%<>~^" else "x"
        i += 1


def shablon_turlari(s):
    """Jinja izohi render paytida BUTUNLAY yo'qoladi — avval bo'shliq bilan almashtiriladi (ichidagi «<script>» so'zi tuzilmani
    buzmasin); so'ng <style> / <script> bloklari, ular TASHQARISIDAGI HTML izohlari."""
    m = ["H"] * len(s)
    s2l = list(s)
    for x in re.finditer(r"\{#.*?#\}", s, re.S):
        s2l[x.start():x.end()] = " " * (x.end() - x.start())
        m[x.start():x.end()] = "C" * (x.end() - x.start())
    s2 = "".join(s2l)
    bloklar = []
    for x in re.finditer(r"<style\b[^>]*>(.*?)</style>", s2, re.S | re.I):
        m[x.start(1):x.end(1)] = "C" * (x.end(1) - x.start(1))
        bloklar.append((x.start(1), x.end(1)))
    for x in re.finditer(r"<script\b[^>]*>(.*?)</script>", s2, re.S | re.I):
        _js(s2, x.start(1), x.end(1), m)
        for k in range(x.start(1), x.end(1)):
            if s2[k] == " " and s[k] != " ":
                m[k] = "C"                 # skript ichidagi Jinja izohi
        bloklar.append((x.start(1), x.end(1)))
    for x in re.finditer(r"<!--.*?-->", s2, re.S):
        if not any(a <= x.start() < b for a, b in bloklar):
            m[x.start():x.end()] = "C" * (x.end() - x.start())
    return m


def js_turlari(s):
    m = ["K"] * len(s)
    _js(s, 0, len(s), m)
    return m


def _qator(s, pos):
    a = s.rfind("\n", 0, pos) + 1
    b = s.find("\n", pos)
    return s.count("\n", 0, pos) + 1, s[a:len(s) if b < 0 else b]


def matn_topilmalari(s, turlar):
    """Ko'rinadigan matndagi (HTML / JS satri) joylashuv so'zlari: [(qator, so'z, qator matni, so'zning qatordagi o'rni)]."""
    nat = []
    for x in JOY.finditer(s):
        if turlar[x.start()] in ("H", "S"):
            ln, q = _qator(s, x.start())
            nat.append((ln, x.group(1), q, x.start() - (s.rfind("\n", 0, x.start()) + 1)))
    return nat


def python_topilmalari(src):
    """Python satrlari (hujjat satri va yolg'iz satr-izohlar — `Expr` — EMAS): [(qator, so'z, satr qiymati)]."""
    t = ast.parse(src)
    expr = set()
    for n in ast.walk(t):
        if isinstance(n, ast.Expr) and isinstance(n.value, (ast.Constant, ast.JoinedStr)):
            expr.add(id(n.value))
            if isinstance(n.value, ast.JoinedStr):
                expr.update(id(v) for v in n.value.values)
    nat = []
    for n in ast.walk(t):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in expr:
            for x in JOY.finditer(n.value):
                nat.append((n.lineno, x.group(1), n.value, x.start()))
    return nat


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
# RUXSAT: (fayl, aniq bo'lak, tur, sabab). Tur: «ketma-ket» — SHU xabar / oyna / blok ichida darhol keladigan narsa
# («Quyidagi …:»); «ui-emas» — foydalanuvchi sahifasida ko'rinmaydigan satr (server jurnali, API JSON matni).
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
RUXSAT = [
    ("templates/kpi.html", "`Quyidagi ustalar sovg'aga yetgan, lekin hali", "ketma-ket",
     "tasdiq oynasi: ustalar ro'yxati SHU matn ichida (\\n\\n${namesStr})"),
    ("templates/orders.html", ">Quyidagi ma'lumotlarni tekshiring</div>", "ketma-ket",
     "«Tayyor» oynasi sarlavhasi ostidagi izoh — tekshiriladigan maydonlar SHU oyna ichida"),
    ("templates/orders.html", ">Quyidagi maydonlarni to'ldiring:</div>", "ketma-ket",
     "oyna ichidagi izoh — maydonlar SHU oynada darhol keladi"),
    ("templates/orders.html", "`Quyidagi detal(lar) narxi KIRITILMAGAN (0 so'm):", "ketma-ket",
     "tasdiq oynasi: detallar ro'yxati SHU matn ichida (${qatorlar})"),
    ("templates/orders.html", "`Quyidagi detal(lar) narxi 0 ga tushadi:", "ketma-ket",
     "tasdiq oynasi: detallar ro'yxati SHU matn ichida (${qatorlar108})"),
    ("templates/production.html", "Bekor qilingan — xomashyo ombordan yechilmagan. Quyida — boshlangandagi reja.", "ketma-ket",
     "ishlab chiqarish oynasi: izoh qatori va undan keyingi jadval — BITTA blok"),
    ("templates/returns.html", ">Quyidagi taqsimot — shu oyning brak yozuvlari bo'yicha", "ketma-ket",
     "«Brak tahlili» kartasi: izoh va taqsimot qatorlari — BITTA blok"),
    ("templates/supplier_receive.html", "👤 Quyidagi ma'lumotlar — faqat <b>tanlangan ta'minotchi</b>ga tegishli:", "ketma-ket",
     "ta'minotchi kartasi: izoh va raqamlar katakchalari — BITTA blok"),
    ("templates/users.html", "Endi quyidagi qiymatni nusxalab, <b>Railway → Variables</b>", "ketma-ket",
     "natija bloki: nusxalanadigan qiymat SHU blokda darhol keladi"),
    ("templates/users.html", "\"Tasdiqlash uchun quyidagi so'zni AYNAN shunday yozing:\"", "ketma-ket",
     "kiritish oynasi: so'z (izoh: HAMMASINI-OCHIR) SHU oyna ichida"),
    ("main.py", "Quyidagi tugmalardan foydalaning:", "ketma-ket",
     "Telegram /start: klaviatura SHU xabarga biriktirilgan (reply_markup)"),
    ("main.py", "avval quyidagilar tuzatilsin:", "ui-emas",
     "server jurnali (print) — ro'yxat keyingi qatorlarda"),
    ("main.py", "MUHIM: yuqoridagi 'new_secret' qiymatini nusxalab", "ui-emas",
     "API JSON `message` — sahifa uni ko'rsatmaydi (users.html o'z matnini quradi); «yuqoridagi» — JSON dagi `new_secret` kaliti"),
]


def ruxsatmi(fayl, soz, matn, ishlatilgan, orin):
    """`orin` — so'zning `matn` dagi o'rni: so'z AYNAN shu faylning RUXSAT bo'lagi ICHIDA bo'lsagina ruxsat (qatorda bo'lak bor, lekin
    so'z undan tashqarida — ruxsat EMAS)."""
    for i, (f, bolak, _tur, _s) in enumerate(RUXSAT):
        if f != fayl:
            continue
        k = matn.find(bolak)
        while k >= 0:
            if k <= orin < k + len(bolak) and matn[orin:orin + len(soz)] == soz:
                ishlatilgan.add(i)
                return True
            k = matn.find(bolak, k + 1)
    return False


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Skaner o'zi — soxta kirishlar")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
def sh(s):
    return [t[1] for t in matn_topilmalari(s, shablon_turlari(s))]


check("S1 Jinja izohi {# … #} — o'tkaziladi", sh("<div>{# pastdagi tugma #}Nom</div>") == [], sh("<div>{# pastdagi tugma #}Nom</div>"))
check("S2 HTML izohi <!-- … --> — o'tkaziladi", sh("<!-- yuqoridagi filtr -->\n<p>Matn</p>") == [])
check("S3 <style> ichi (CSS izohi bilan) — o'tkaziladi", sh("<style>/* o'ngdagi ustun */ .chapda{x:1}</style>") == [])
check("S4 HTML matni — ushlanadi", sh("<div>Pastdagi tugmani bosing</div>") == ["Pastdagi"], sh("<div>Pastdagi tugmani bosing</div>"))
check("S5 HTML atributi (title / placeholder) — ushlanadi", sh('<input title="yuqoridagi maydon" placeholder="chapdan">') ==
      ["yuqoridagi", "chapdan"], sh('<input title="yuqoridagi maydon" placeholder="chapdan">'))
# izohdagi qo'shtirnoq: `//` izoh deb olinmasa — «'pastdagi …'» satr bo'lib ushlanadi (mutatsiya M22 da birinchi variant buni ko'rmagan)
_s6 = "<script>// pastdagi\n/* quyidagi\n tugma */ var pastda = 1; if (pastda) f(); // eski matn: 'pastdagi tugma'\n</script>"
check("S6 JS izohlari (// va /* */) va kod (o'zgaruvchi `pastda`) — o'tkaziladi", sh(_s6) == [], sh(_s6))
_s7 = "<script>alert('pastdagi'); x = \"chapda\"; y = `o'ngda ${a ? 'yonidagi' : b} tepada`;</script>"
check("S7 JS satrlari: '…', \"…\", `…` va ${…} ichidagi satr — hammasi ushlanadi", sh(_s7) == ["pastdagi", "chapda", "o'ngda",
                                                                                              "yonidagi", "tepada"], sh(_s7))
# regex ichidagi qo'shtirnoq satr boshi deb olinsa — keyingi satr KOD bo'lib qoladi (mutatsiya M24 da birinchi variant buni ko'rmagan)
_s8 = "<script>var r = /'/g; var u = 'quyidagi'; var t = s.replace(/[\"']/g, ''); var w = \"pastda\";</script>"
check("S8 JS regex ichidagi qo'shtirnoq satrni buzmaydi (regexdan keyingi satrlar ushlanadi)", sh(_s8) == ["quyidagi", "pastda"], sh(_s8))
_s9 = "<script>\n{# pastdagi 'a #}\nvar a = 'Matn';</script>"
check("S9 <script> ichidagi Jinja izohi (ichida qo'shtirnoq bilan) — o'tkaziladi, keyingi satr buzilmaydi", sh(_s9) == [], sh(_s9))
_s9b = "{# eslatma: <script> va <!-- shu yerda #}<div>Pastdagi tugma</div><script>var t = 'yuqorida';</script>"
check("S9b Jinja izohi ichidagi «<script>» / «<!--» so'zi tuzilmani buzmaydi — keyingi HTML matni va JS satri ushlanadi",
      sh(_s9b) == ["Pastdagi", "yuqorida"], sh(_s9b))
_s10 = "<div>buyurtma ustida ish, pastga aylantiring, yuqoriga yaxlitlab</div><div class=\"rl-pastki\"></div>"
check("S10 ro'yxatda yo'q so'zlar («ustida», «pastga», «yuqoriga», «pastki») — ushlanmaydi", sh(_s10) == [], sh(_s10))
_s11 = "<p>PASTDAGI</p><p>oʻngdagi</p><p>o’ngda</p><p>o`ngdan</p><p>Yuqoridagilar</p><p>quyidagicha</p><p>ostidagi</p>"
check("S11 katta harf, o' ning hamma yozilishi, qo'shimchalar (…lar, …cha) — ushlanadi",
      sh(_s11) == ["PASTDAGI", "oʻngdagi", "o’ngda", "o`ngdan", "Yuqoridagilar", "quyidagicha", "ostidagi"], sh(_s11))
_s12 = "<p>Kampastdagi</p><p>yuqoridagixyz</p>"
check("S12 so'z boshqa so'z ichida emas (oldida harf) — ushlanmaydi; oxirida harf — so'z davomi (ushlanadi)",
      sh(_s12) == ["yuqoridagixyz"], sh(_s12))
_p = ('"""Modul — pastdagi funksiyalar."""\n'
      'def f():\n    """yuqoridagi kabi."""\n    "chapdagi izoh-satr"\n'
      '    x = "o\'ngdagi tugma"\n    y = f"tepadagi {x}"\n    raise ValueError(detail="Quyidagilar:\\nA")\n')
_pt = [t[1] for t in python_topilmalari(_p)]
check("S13 Python: docstring va yolg'iz satr-izoh — o'tkaziladi; oddiy satr, f-satr, \\n dan keyingi so'z — ushlanadi",
      _pt == ["o'ngdagi", "tepadagi", "Quyidagilar"], _pt)
check("S14 JS fayl (static) — izoh o'tkaziladi, satr ushlanadi",
      [t[1] for t in matn_topilmalari("// pastda\nvar a = 'yuqorida';", js_turlari("// pastda\nvar a = 'yuqorida';"))] ==
      ["yuqorida"])
_q = "<div style=\"font-size:13px;color:var(--m-6b7280)\">Quyidagi maydonlarni to'ldiring:</div>"
_qo = _q.find("Quyidagi")
check("S15 RUXSAT fayliga bog'liq: o'sha bo'lak O'Z faylida ruxsat, boshqa faylda — YO'Q",
      ruxsatmi("templates/orders.html", "Quyidagi", _q, set(), _qo) is True
      and ruxsatmi("templates/finance.html", "Quyidagi", _q, set(), _qo) is False)
check("S16 RUXSAT so'zga bog'liq: bo'lak bor qatorda boshqa joylashuv so'zi (bo'lakdan TASHQARIDA) — ruxsat EMAS",
      ruxsatmi("templates/orders.html", "pastdagi", _q + " pastdagi tugma", set(), len(_q) + 1) is False)
check("S17 RUXSAT o'ringa bog'liq: bo'lakdagi so'z bilan BIR XIL so'z, lekin bo'lakdan tashqarida («… Quyidagi tugma») — ruxsat EMAS",
      ruxsatmi("templates/orders.html", "Quyidagi", _q + " Quyidagi tugma", set(), len(_q) + 1) is False)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
section("J. Butun daraxt — joylashuv so'zi faqat RUXSAT dagi joylarda")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
ISHL = set()
KUTILMAGAN = {"shablon": [], "js": [], "python": []}
FAYLLAR = {}
_td = os.path.join(ROOT, "templates")
for fn in sorted(os.listdir(_td)):
    if fn.endswith(".html"):
        rel = "templates/" + fn
        s = open(os.path.join(_td, fn), encoding="utf-8").read()
        _tur = shablon_turlari(s)
        FAYLLAR[rel] = "".join(ch for ch, t in zip(s, _tur) if t != "C")      # izohlarsiz (izohda eski matn qolishi mumkin)
        for ln, soz, q, o in matn_topilmalari(s, _tur):
            if not ruxsatmi(rel, soz, q, ISHL, o):
                KUTILMAGAN["shablon"].append(f"{rel}:{ln} «{soz}» | {q.strip()[:160]}")
for kat, _dirs, fs in os.walk(os.path.join(ROOT, "static")):
    for fn in sorted(fs):
        if fn.endswith(".js"):
            p = os.path.join(kat, fn)
            rel = os.path.relpath(p, ROOT)
            s = open(p, encoding="utf-8").read()
            for ln, soz, q, o in matn_topilmalari(s, js_turlari(s)):
                if not ruxsatmi(rel, soz, q, ISHL, o):
                    KUTILMAGAN["js"].append(f"{rel}:{ln} «{soz}» | {q.strip()[:160]}")
_py_soni = 0
for fn in sorted(os.listdir(ROOT)):
    if fn.endswith(".py"):
        _py_soni += 1
        s = open(os.path.join(ROOT, fn), encoding="utf-8").read()
        FAYLLAR[fn] = s
        for ln, soz, q, o in python_topilmalari(s):
            if not ruxsatmi(fn, soz, q, ISHL, o):
                KUTILMAGAN["python"].append(f"{fn}:{ln} «{soz}» | {q.strip()[:160]!r}")
check(f"J0 skanerlandi: shablonlar {sum(1 for k in FAYLLAR if k.startswith('templates/'))}, ildiz .py {_py_soni}",
      sum(1 for k in FAYLLAR if k.startswith("templates/")) >= 25 and _py_soni >= 20)
check("J1 shablonlar (HTML matni, atributlar, JS satrlari) — RUXSAT dan tashqari joylashuv so'zi YO'Q",
      not KUTILMAGAN["shablon"], "\n".join(KUTILMAGAN["shablon"]))
check("J2 static/*.js satrlari — joylashuv so'zi YO'Q", not KUTILMAGAN["js"], "\n".join(KUTILMAGAN["js"]))
check("J3 ildizdagi .py satrlari (docstring emas) — RUXSAT dan tashqari joylashuv so'zi YO'Q",
      not KUTILMAGAN["python"], "\n".join(KUTILMAGAN["python"]))
_eski = [f"{RUXSAT[i][0]}: {RUXSAT[i][1]}" for i in range(len(RUXSAT)) if i not in ISHL]
check("J4 RUXSAT dagi har yozuv HALI kodda bor (eskirgan yozuv yo'q — matn o'zgarsa ro'yxat ham yangilanadi)", not _eski, _eski)
_yomon_tur = [r[:2] for r in RUXSAT if (r[0].startswith("templates/") or r[0].startswith("static/"))
              and not (r[2] == "ketma-ket" and all(x.group(1).lower().startswith("quyi") for x in JOY.finditer(r[1]))
                       and JOY.search(r[1]))]
check("J5 sahifa (shablon / static) RUXSAT yozuvlari — faqat «quyi…» ketma-ketlik (tugma / maydon joylashuvi bilan ATALMAYDI)",
      not _yomon_tur, _yomon_tur)

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
section("T. Zip 156 tuzatishlari — nomlar haqiqiy elementlar bilan AYNAN")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
F = FAYLLAR          # shablonlar — IZOHLARSIZ (Jinja / HTML / JS izohlari olib tashlangan): eski matn izohda tilga olinsa ham «yo'q»


def bor(fayl, *bolaklar):
    return all(b in F.get(fayl, "") for b in bolaklar)


def yoq(fayl, *bolaklar):
    return fayl in F and not any(b in F[fayl] for b in bolaklar)


_fin = F.get("templates/finance.html", "")
check("T1 Moliya: «Oy va yilni tanlang yoki «Ko'rish» tugmasini bosing» (eski «Yuqoridagi filtrdan …» YO'Q); «Ko'rish» tugmasi oy / yil "
      "bilan BIR filtr qatorida",
      bor("templates/finance.html", "<div style=\"font-size:13px\">Oy va yilni tanlang yoki «Ko'rish» tugmasini bosing</div>")
      and yoq("templates/finance.html", "Yuqoridagi filtrdan")
      and re.search(r'<select id="sel-month"[\s\S]{0,900}<input type="number" id="sel-year"[^>]*>\s*'
                    r'<button class="btn btn-gold" onclick="loadReport\(\)">Ko\'rish</button>', _fin) is not None)
_fh = F.get("templates/finished.html", "")
check("T2 Tayyor mahsulotlar (bo'sh ombor): «Penoplast detal — <b>+ Penoplast detal</b> tugmasi» («yuqoridagi» YO'Q); shu nomli tugma bor "
      "(ti-plus + «Penoplast detal»)",
      "'Ombor bo\\'sh<br><br><span style=\"font-size:12px\">Penoplast detal — <b>+ Penoplast detal</b> tugmasi; boshqa mahsulot — " in _fh
      and "yuqoridagi <b>+ Penoplast detal</b>" not in _fh
      and re.search(r'<button class="btn btn-dark" onclick="openProduceModal\(\)"[^>]*><i class="ti ti-plus"></i> Penoplast detal</button>',
                    _fh) is not None)
_rc = F.get("templates/recipes.html", "")
_rk = _rc.find("Har biridan — «Partiya hajmi (kg)» uchun kerak miqdor (kg)")
check("T3 Loy retseptlari (yangi retsept oynasi): «Har biridan — «Partiya hajmi (kg)» uchun kerak miqdor (kg)»; o'sha oynada aynan "
      "«Partiya hajmi (kg)» yorlig'i (f-batch) bor; «yuqoridagi partiya hajmi» YO'Q",
      _rk > 0 and "yuqoridagi partiya hajmi" not in _rc
      and re.search(r"<label>Partiya hajmi \(kg\)</label>\s*<div class=\"recp-field-input\">\s*<i class=\"ti ti-scale\"></i>\s*"
                    r"<input type=\"number\" id=\"f-batch\"", _rc[:_rk]) is not None)
_sr = F.get("templates/supplier_receive.html", "")
check("T4 Kirim: «Qo'shimcha xarajatlarni tannarxga qo'shish — yoqilsa, bu xarajatlar …» («yuqoridagi xarajatlar» YO'Q); «Qo'shimcha "
      "xarajatlar» bo'limi (Transport, Tushirish, Yuklash, Boshqa) shu belgidan OLDIN",
      "<b>Qo'shimcha xarajatlarni tannarxga qo'shish</b> — yoqilsa, bu xarajatlar materiallar qiymatiga proporsional taqsimlanib" in _sr
      and "yuqoridagi xarajatlar" not in _sr
      and 0 < _sr.find('<div class="rcv-card-title" style="margin-top:16px">Qo\'shimcha xarajatlar') < _sr.find('id="ap-cost-boshqa"')
      < _sr.find("<b>Qo'shimcha xarajatlarni tannarxga qo'shish</b>"))
_us = F.get("templates/users.html", "")


def tugma_matni(html, tid):
    x = re.search(r'<button[^>]*id="' + tid + r'"[^>]*>\s*(.*?)\s*</button>', html, re.S)
    return x.group(1).strip() if x else None


_t_sec, _t_del = tugma_matni(_us, "tg-security-btn"), tugma_matni(_us, "tg-delete-webhook-btn")
check("T5a Foydalanuvchilar → Telegram xavfsizligi: tugmalar matni — «🔐 Telegram xavfsizligini yoqish», «🔄 Botni asl holatiga qaytarish»",
      _t_sec == "🔐 Telegram xavfsizligini yoqish" and _t_del == "🔄 Botni asl holatiga qaytarish", (_t_sec, _t_del))
check("T5b «Diqqat» ogohlantirishi: ««🔐 Telegram xavfsizligini yoqish» tugmasini bosish …», «… «🔄 Botni asl holatiga qaytarish» tugmasi "
      "orqali darhol tuzatib …» (eski «bu tugmani bosish», «pastdagi qizil tugma» YO'Q)",
      f"BOSHQA, alohida serverda ishlasa — «{_t_sec}» tugmasini bosish o'sha botni vaqtincha" in _us
      and f"Agar shunday bo'lsa — «{_t_del}» tugmasi orqali darhol tuzatib olishingiz mumkin." in _us
      and "pastdagi qizil tugma" not in _us and "— bu tugmani bosish" not in _us)
check("T5c qizil ogohlantirish: «Agar «🔐 Telegram xavfsizligini yoqish» tugmasini bosgandan keyin … — «🔄 Botni asl holatiga qaytarish» "
      "tugmasi orqali qaytaring:» (eski «shu tugmani», «quyidagi tugma orqali» YO'Q)",
      f"⚠️ Agar «{_t_sec}» tugmasini bosgandan keyin botingiz (boshqa, alohida serverdagi) ishlamay qolgan bo'lsa — «{_t_del}» "
      "tugmasi orqali qaytaring:" in _us and "Agar shu tugmani bosgandan" not in _us and "quyidagi tugma orqali" not in _us)
_tg_fn = re.search(r"\['tg-security-btn', 'tg-delete-webhook-btn'\]\.forEach\(function \(id\) \{(.*?)\n  \}\);", _us, re.S)
check("T5d asosiy saytda tugmaning ASL `title` i tiklanadi (birinchi chaqiruvda `data-asl-title` ga saqlanadi; '' yozilmaydi)",
      _tg_fn is not None and "b.setAttribute('data-asl-title', b.getAttribute('title') || '')" in _tg_fn.group(1)
      and "if (!b.hasAttribute('data-asl-title'))" in _tg_fn.group(1)
      and "b.title = d.asosiy_muhit ? b.getAttribute('data-asl-title') : 'Faqat asosiy saytda';" in _tg_fn.group(1)
      and "b.title = d.asosiy_muhit ? '' :" not in _us, _tg_fn.group(1) if _tg_fn else None)
_mj, _bs = F.get("templates/murojaat.html", ""), F.get("templates/base.html", "")
check("T6 Murojaat: «menyudagi «Yordam / Murojaat» bandida son paydo bo'ladi» («yonida» YO'Q); menyu bandida aynan «Yordam / Murojaat» va "
      "son (n-badge) — BIR bandda",
      "Javob shu sahifada chiqadi — menyudagi «Yordam / Murojaat» bandida son paydo bo'ladi." in _mj
      and "«Yordam / Murojaat» yonida" not in _mj
      and re.search(r'<span class="n-txt">Yordam / Murojaat</span>\{% if _mj_soni %\}<span class="n-badge"', _bs) is not None)
_lg, _mn = F.get("templates/logs.html", ""), F.get("main.py", "")
check("T7 Sozlamalar → Telegram shiori: «Yangi usta qo'shilganda bot salom xabarining oxirida chiqadi: «🏗 Korxona nomi — shior»» («nom "
      "yonida» YO'Q); xabar shakli `main._tg_signature` bilan AYNAN («🏗 *Nom* — Shior»)",
      "Yangi usta qo'shilganda bot salom xabarining oxirida chiqadi: «🏗 Korxona nomi — shior»</div>" in _lg
      and "nom yonida chiqadi" not in _lg
      and 'qatorlar.append(f"🏗 *{nom}*" + (f" — {shior}" if shior else ""))' in _mn)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAIL:
    print("Yiqilganlar:\n  - " + "\n  - ".join(FAILED))
sys.exit(1 if FAIL else 0)
