#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STATIK DARVOZA — shablonlardagi escape qoidalari (5.2d 4-band, kech33).

Nima uchun kerak (dinamik darvoza `tools/test_html_escape_dom.py` yetarli
emas):

  (d) Server GENERATORI qo'yadigan qiymat (buyurtma raqami, tokeni) —
      unda maxsus belgi hech qachon bo'lmaydi, shuning uchun dinamik test
      xavfli chaqiruv joyini ko'rsa ham YASHIL qoladi (kech33 da
      `/trash` buyurtma tugmasi shunday o'lchangan).
  (e) Chaqiruv joyi fiksturada umuman ishlamaydi (super-admin bo'limi,
      xato yo'llari, kamdan-kam ochiladigan oynalar).
  (f) 18 belgidan qisqa ustun (masalan `recurring_obligations.icon`
      String(10)) — belgi SIG'MAYDI, dinamik test uni HECH QACHON
      ko'rmaydi.

Shu sababli bu yerda KOD naqshi tekshiriladi, ma'lumot emas.

TEKSHIRILADIGAN QOIDALAR
────────────────────────
  Q1. HTML MATNI: `<script>` ichidagi template literal yoki satr
      birikmasi HTML chizsa, har `${...}` / `+ ifoda +` xavfsiz bo'lishi
      SHART: `escapeHtml(...)`, `jsAttrEscape(...)`,
      `encodeURIComponent(...)`, son formatlovchisi, son / id naqshi,
      satr literali yoki ruxsat ro'yxatida sababi bilan.
  Q2. onX ATRIBUTI (`onclick="..."` va h.k.) ichidagi interpolyatsiya:
      FAQAT `jsAttrEscape(...)` (yoki son / id / literal). `escapeHtml(`
      bu yerda YETARLI EMAS va ATAYLAB yiqiladi — brauzer atributni
      o'qiyotganda `&#39;` ni `'` ga qaytaradi va qiymat JS satridan
      chiqadi (kech30 da o'lchangan).
  Q3. H2 — SERVER shablonidagi (Jinja) onX atributi ichida `{{ ... }}`:
      FAQAT son / id / `'x' if ... else 'y'` naqshi ruxsat etiladi.
      `|replace("'", ...)` / `|replace('"', ...)` naqshi ATAYLAB
      yiqiladi — u himoya EMAS (`\\` bilan aylanib o'tiladi, `&` li
      matnni esa buzadi). Xavfsiz yechim — `data-x="{{ x }}"` +
      `onclick="f(this.dataset.x)"`.
  Q4. `reports.html` ustun funksiyalari `['Sarlavha', r => r.maydon]`:
      MATN maydoni `escapeHtml(...)` siz qaytarilsa yiqiladi.

LEKSER
──────
`${...}` ni oddiy regex bilan ajratib bo'lmaydi: shablon literali ichida
satr, satr ichida `${`, kod ichida REGEX LITERALI (`.replace(/"/g, ...)`)
uchraydi. kech31 da o'lchangan: regex literalidagi `"` ni satr boshi deb
o'qigan skript faylning qolganini KO'RMAY qolgan (kpi.html da ~130
o'rniga 16 ta joy chiqqan). Shuning uchun bu yerda to'liq leksik tahlil
bor va u 1-bo'limda O'Z-O'ZINI sinaydi — lekser ishlamasa darvoza jim
teshik bo'lib qoladi.
"""

import io
import os
import re
import sys

ROOT = os.environ.get("REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SHABLON_PAPKA = os.path.join(ROOT, "templates")

OK = 0
FAIL = 0


def check(label, cond, detail=""):
    global OK, FAIL
    if cond:
        OK += 1
        print(f"  ✅ {label}")
    else:
        FAIL += 1
        print(f"  ❌ {label}")
        if detail:
            print("       ↳ " + str(detail).replace("\n", "\n       ↳ ")[:4000])


def section(t):
    print("\n" + "─" * 66 + f"\n{t}\n" + "─" * 66)


def info(t):
    print(f"  ℹ️  {t}")


# ══════════════════════════════════════════════════════════════
# 1. JS LEKSERI
# ══════════════════════════════════════════════════════════════
# `/` belgisidan keyin REGEX boshlanadimi yoki BO'LISH amalimi — bu
# qaror oldingi muhim tokenga bog'liq. Ifoda tugagan bo'lsa (identifikator,
# son, `)`, `]`, `}`, satr, shablon) — bo'lish; aks holda regex.
# Kalit so'zdan keyin esa doim regex (`return /x/.test(s)`).
KALIT_SOZLAR = {
    "return", "typeof", "instanceof", "in", "of", "new", "delete", "void",
    "case", "do", "else", "yield", "await", "throw",
}
# Oldingi token "ifoda tugadi" degani — bundan keyin `/` BO'LISH.
TUGAGAN = {")", "]", "}", "'", "`", "w", "n"}


def _regex_oxiri(manba, i):
    """`i` dagi `/` dan boshlanadigan regex literalining oxirini qaytaradi
    (bayroqlari bilan). Regex emas bo'lsa — None."""
    j = i + 1
    sinf_ichida = False
    while j < len(manba):
        c = manba[j]
        if c == "\\":
            j += 2
            continue
        if c == "\n":
            return None
        if sinf_ichida:
            if c == "]":
                sinf_ichida = False
        elif c == "[":
            sinf_ichida = True
        elif c == "/":
            j += 1
            while j < len(manba) and (manba[j].isalpha()):
                j += 1
            return j
        j += 1
    return None


def js_tahlil(manba):
    """JS manbasini leksik tahlil qiladi.

    Qaytaradi (tokenlar, shablonlar):
      tokenlar   — (tur, bosh, oxir); tur: 'izoh' | 'satr' | 'regex'
      shablonlar — har template literal uchun lug'at:
                   {'bosh', 'oxir', 'matn': [(b, o), ...],
                    'ifodalar': [(b, o), ...], 'ota': ota_indeks | None}
    Shablon literalining `matn` va `ifodalar` bo'laklari NAVBATMA-NAVBAT
    keladi: matn[0], ifoda[0], matn[1], ifoda[1], ..., matn[k].
    """
    n = len(manba)
    i = 0
    tokenlar = []
    shablonlar = []
    stek = []
    oldingi = ""        # oxirgi muhim belgi turi
    oldingi_soz = ""

    while i < n:
        # ── shablon literali ichidagi MATN ─────────────────────────
        if stek and stek[-1]["tur"] == "shablon":
            c = manba[i]
            if c == "\\":
                i += 2
                continue
            if c == "`":
                ust = stek.pop()
                sh = shablonlar[ust["idx"]]
                sh["matn"].append((ust["matn_bosh"], i))
                sh["oxir"] = i + 1
                oldingi = "`"
                oldingi_soz = ""
                i += 1
                continue
            if manba.startswith("${", i):
                ust = stek[-1]
                sh = shablonlar[ust["idx"]]
                sh["matn"].append((ust["matn_bosh"], i))
                stek.append({"tur": "ifoda", "idx": ust["idx"],
                             "bosh": i + 2, "qavs": 0})
                oldingi = "{"
                oldingi_soz = ""
                i += 2
                continue
            i += 1
            continue

        # ── kod rejimi (asosiy oqim yoki `${...}` ichi) ────────────
        c = manba[i]
        if c in " \t\r\n":
            i += 1
            continue
        if manba.startswith("//", i):
            j = manba.find("\n", i)
            j = n if j < 0 else j
            tokenlar.append(("izoh", i, j))
            i = j
            continue
        if manba.startswith("/*", i):
            j = manba.find("*/", i + 2)
            j = n if j < 0 else j + 2
            tokenlar.append(("izoh", i, j))
            i = j
            continue
        if c in "'\"":
            j = i + 1
            while j < n:
                if manba[j] == "\\":
                    j += 2
                    continue
                if manba[j] == c or manba[j] == "\n":
                    break
                j += 1
            oxir = min(j + 1, n)
            tokenlar.append(("satr", i, oxir))
            i = oxir
            oldingi = "'"
            oldingi_soz = ""
            continue
        if c == "`":
            shablonlar.append({"bosh": i, "oxir": None, "matn": [],
                               "ifodalar": [],
                               "ota": stek[-1]["idx"] if stek else None})
            stek.append({"tur": "shablon", "idx": len(shablonlar) - 1,
                         "matn_bosh": i + 1})
            i += 1
            continue
        if c == "/":
            regexmi = (oldingi_soz in KALIT_SOZLAR) if oldingi == "w" \
                else (oldingi not in TUGAGAN)
            if regexmi:
                j = _regex_oxiri(manba, i)
                if j:
                    tokenlar.append(("regex", i, j))
                    i = j
                    oldingi = ")"
                    oldingi_soz = ""
                    continue
            i += 1
            oldingi = "/"
            oldingi_soz = ""
            continue
        if c == "{":
            if stek and stek[-1]["tur"] == "ifoda":
                stek[-1]["qavs"] += 1
            i += 1
            oldingi = "{"
            oldingi_soz = ""
            continue
        if c == "}":
            if stek and stek[-1]["tur"] == "ifoda":
                if stek[-1]["qavs"] == 0:
                    ust = stek.pop()
                    sh = shablonlar[ust["idx"]]
                    sh["ifodalar"].append((ust["bosh"], i))
                    stek[-1]["matn_bosh"] = i + 1
                    i += 1
                    oldingi = "}"
                    oldingi_soz = ""
                    continue
                stek[-1]["qavs"] -= 1
            i += 1
            oldingi = "}"
            oldingi_soz = ""
            continue
        m = re.match(r"[A-Za-z_$][\w$]*", manba[i:])
        if m:
            oldingi_soz = m.group(0)
            oldingi = "w"
            i += len(m.group(0))
            continue
        m = re.match(r"[0-9]+(\.[0-9]+)?", manba[i:])
        if m:
            oldingi = "n"
            oldingi_soz = ""
            i += len(m.group(0))
            continue
        oldingi = c
        oldingi_soz = ""
        i += 1

    # Yopilmagan shablon (manba bo'lagi kesilgan bo'lsa) — oxirini qo'yamiz
    while stek:
        ust = stek.pop()
        if ust["tur"] == "shablon":
            sh = shablonlar[ust["idx"]]
            sh["matn"].append((ust["matn_bosh"], n))
            if sh["oxir"] is None:
                sh["oxir"] = n
        else:
            sh = shablonlar[ust["idx"]]
            sh["ifodalar"].append((ust["bosh"], n))
    return tokenlar, shablonlar


# ══════════════════════════════════════════════════════════════
# 2. XAVFSIZLIK PREDIKATI
# ══════════════════════════════════════════════════════════════
XAVFSIZ_FN = (
    "escapeHtml(", "jsAttrEscape(", "encodeURIComponent(", "encodeURI(",
    "formatNum(", "fmt(", "fmtFull(", "fmtShort(", "fmtShortM(", "fmtN(",
    "fmtMoney(", "Number(", "parseInt(", "parseFloat(", "Math.",
    # `catBadge(cat)` — `reports.html:791` da O'QILDI: natija ichida
    # `escapeHtml(cat)` bor, qolgan qismi kod konstantalari.
    "catBadge(",
)
# onX atributida FAQAT shular xavfsiz (escapeHtml ATAYLAB yo'q).
XAVFSIZ_FN_ATRIBUT = (
    "jsAttrEscape(", "encodeURIComponent(", "encodeURI(",
    "Number(", "parseInt(", "parseFloat(", "Math.",
)
# Son / id / mantiqiy ko'rinishidagi nomlar — foydalanuvchi ERKIN MATNI emas.
# Qo'lda ro'yxat o'rniga NOM naqshi: `..._id` / `...Id`, `is_*` / `has_*`
# (mantiqiy) va son ma'nosini bildiruvchi o'zak. Shu tufayli yangi maydon
# qo'shilganda ro'yxatni yangilash SHART emas.
SON_OZAK = re.compile(
    r"(id|idx|index|no|num|count|len|length|size|qty|quantity|amount|price|"
    r"cost|total|sum|stock|percent|pct|level|page|width|height|thickness|"
    r"weight|kg|year|month|day|hour|minute|second|max|min|bonus|adjustment|"
    r"debt|paid|balance|remaining|delivered|ordered|reserved|shortage|tier|"
    r"step|rank|score|kpi|period|row|col|value|volume|factor|rate|days)",
    re.I)
MANTIQIY = re.compile(r"(is|has|can|should|allow|enable|show|hide)[_A-Z]", re.I)


def _nom_soni_mi(nom):
    """Nom son / id / mantiqiy qiymatni bildiradimi?

    MUHIM qalqon: nom MODELDAGI matn ustuni bo'lsa (`unit`, `order_number`,
    `label`), u HECH QACHON son deb hisoblanmaydi — aks holda darvoza
    o'sha ustunlarni ko'rmay qolardi."""
    if nom in MATN_MAYDON:
        return False
    if re.fullmatch(r"[ijkn]|idx|i\d+", nom):
        return True
    if re.search(r"(_id|Id|ID|_ids|Ids)$", nom):
        return True
    if MANTIQIY.match(nom):
        return True
    bolaklar = [b for b in re.split(r"[_]|(?<=[a-z0-9])(?=[A-Z])", nom) if b]
    return bool(bolaklar) and any(SON_OZAK.fullmatch(b) or b.isdigit()
                                 for b in bolaklar)


def son_yoki_id(ifoda):
    """`a.b.c` ko'rinishidagi ifodaning OXIRGI bo'lagi son / id / mantiqiy
    nom bo'lsa — foydalanuvchi matni emas."""
    ifoda = ifoda.strip()
    m = re.fullmatch(r"(?:[\w$]+\.)*([\w$]+)"
                     r"(?:\s*(?:\|\||\?\?)\s*(?:0|''|\"\"|null|false|true))?",
                     ifoda)
    if not m:
        return False
    return _nom_soni_mi(m.group(1))
SON_NAQSH = re.compile(r"-?\d+(\.\d+)?")
LITERAL_NAQSH = re.compile(r"'[^'\\]*'|\"[^\"\\]*\"")


def _tepa_bolish(ifoda, belgilar):
    """Ifodani FAQAT eng yuqori darajadagi `belgilar` bo'yicha bo'ladi
    (qavs, satr, shablon, regex ichidagilar hisobga olinmaydi)."""
    tokenlar, _ = js_tahlil(ifoda)
    yopiq = []
    for tur, b, o in tokenlar:
        yopiq.append((b, o))
    # shablon literallari ham yopiq hisoblanadi
    _, shablonlar = js_tahlil(ifoda)
    for sh in shablonlar:
        if sh["ota"] is None:
            yopiq.append((sh["bosh"], sh["oxir"]))

    def yopiqmi(p):
        return any(b <= p < o for b, o in yopiq)

    bolaklar = []
    daraja = 0
    oxirgi = 0
    i = 0
    while i < len(ifoda):
        if yopiqmi(i):
            i += 1
            continue
        c = ifoda[i]
        if c in "([{":
            daraja += 1
        elif c in ")]}":
            daraja -= 1
        elif daraja == 0:
            for bl in belgilar:
                if ifoda.startswith(bl, i) and not yopiqmi(i):
                    bolaklar.append(ifoda[oxirgi:i])
                    i += len(bl)
                    oxirgi = i
                    break
            else:
                i += 1
                continue
            continue
        i += 1
    bolaklar.append(ifoda[oxirgi:])
    return [b.strip() for b in bolaklar]


def _toliq_chaqiruvmi(ifoda, fn_royxat):
    """Ifoda BUTUNLIGICHA ro'yxatdagi funksiyaning chaqiruvimi?
    (`escapeHtml(x) + y` — EMAS; `escapeHtml(x || 'y')` — HA.)"""
    for fn in fn_royxat:
        if not ifoda.startswith(fn):
            continue
        if fn.endswith("."):          # `Math.` kabi
            return True
        daraja = 0
        tokenlar, shablonlar = js_tahlil(ifoda)
        yopiq = [(b, o) for _, b, o in tokenlar]
        for sh in shablonlar:
            if sh["ota"] is None:
                yopiq.append((sh["bosh"], sh["oxir"]))
        for p, c in enumerate(ifoda):
            if any(b <= p < o for b, o in yopiq):
                continue
            if c == "(":
                daraja += 1
            elif c == ")":
                daraja -= 1
                if daraja == 0:
                    return p == len(ifoda.rstrip()) - 1
    return False


def kod_xaritalari(kod):
    """Skript ichida OBYEKT LITERALI sifatida e'lon qilingan nomlar.

    `const STATUS_LABELS = {new: 'Yangi', ...}` — bunday xaritaga
    murojaat (`STATUS_LABELS[o.status]`) natijasi DOIM kod qiymati
    bo'ladi, kalit foydalanuvchi matni bo'lsa ham (topilmasa
    `undefined`). Bu — taxmin emas, e'lon KO'RINIB turadi."""
    nomlar = set()
    for m in re.finditer(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*[\{\[]", kod):
        nomlar.add(m.group(1))
    return nomlar


def mahalliy_qiymatlar(kod):
    """NOM → shu nomga BERILGAN barcha ifodalar.

    `const icon = ITEM_TYPE_ICON[...] || 'ti-box'` kabi mahalliy
    o'zgaruvchi keyin `${icon}` bo'lib chiziladi. Uning xavfsizligini
    BERILGAN qiymatdan bilish mumkin — bu taxmin emas, e'lon ko'rinib
    turadi. Nomga berilgan HAR qiymat tekshiriladi (qayta tayinlash ham),
    shuning uchun bitta xavfli tayinlash butun nomni xavfli qiladi."""
    tokenlar, shablonlar = js_tahlil(kod)
    yopiq = [(b, o) for _, b, o in tokenlar]
    for sh in shablonlar:
        if sh["oxir"] is not None:
            yopiq.append((sh["bosh"], sh["oxir"]))

    def yopiqmi(p):
        return any(b <= p < o for b, o in yopiq)

    qiymatlar = {}
    for m in re.finditer(r"(?<![.\w$])([A-Za-z_$][\w$]*)\s*=(?![=>])", kod):
        if yopiqmi(m.start()):
            continue
        nom = m.group(1)
        if nom in ("if", "for", "while", "return", "var", "let", "const"):
            continue
        i = m.end()
        daraja = 0
        j = i
        while j < len(kod):
            if yopiqmi(j):
                j += 1
                continue
            c = kod[j]
            if c in "([{":
                daraja += 1
            elif c in ")]}":
                if daraja == 0:
                    break
                daraja -= 1
            elif daraja == 0 and (c == ";" or c == "\n"):
                break
            j += 1
        ifoda = kod[i:j].strip()
        if ifoda:
            qiymatlar.setdefault(nom, []).append(ifoda)
    return qiymatlar


def _xarita_murojaatimi(ifoda, xaritalar):
    """`XARITA[...]` yoki `XARITA[...] || 'literal'` ko'rinishimi?"""
    m = re.match(r"([A-Za-z_$][\w$]*)\s*\[", ifoda)
    if not m or m.group(1) not in xaritalar:
        return False
    yopuvchi = None
    daraja = 0
    for p in range(m.end() - 1, len(ifoda)):
        if ifoda[p] == "[":
            daraja += 1
        elif ifoda[p] == "]":
            daraja -= 1
            if daraja == 0:
                yopuvchi = p
                break
    if yopuvchi is None:
        return False
    qoldiq = ifoda[yopuvchi + 1:].strip()
    if not qoldiq:
        return True
    return bool(re.fullmatch(r"(?:\|\||\?\?)\s*(?:'[^'\\]*'|\"[^\"\\]*\"|0|null|'')", qoldiq))


def _shartmi(ifoda):
    """Ifoda SOLISHTIRISH (uchlik shartning sharti) ko'rinishidami?
    Shart natijasi chizilmaydi — u interpolyatsiyaga tushmaydi."""
    for belgi in ("===", "!==", "==", "!=", ">=", "<=", ">", "<"):
        if len(_tepa_bolish(ifoda, [belgi])) > 1:
            return True
    return False


def _bitta_belgimi(ifoda):
    """Natija BITTA belgi bo'ladimi (`(x.name||'?')[0]`, `.charAt(0)`)?

    kech30 / kech31 da O'QILGAN va dinamik darvoza bilan O'LCHANGAN:
    bitta belgi HTML tegini yasay olmaydi (atribut ham, yopuvchi ham
    sig'maydi)."""
    return bool(re.search(r"(\[\s*0\s*\]|\.charAt\(\s*0\s*\))"
                          r"(\s*\.(toUpperCase|toLowerCase)\(\))?\s*$", ifoda))


def _maskala(ifoda):
    """Ifodadagi SATR va SHABLON literallarini o'rin egallovchi bilan
    almashtiradi.

    Nima uchun: `r.notes ? `<i>${escapeHtml(r.notes)}</i>` : ''` kabi
    ifodada ichki shablon literali ALOHIDA tekshiriladi (u ham
    `shablonlar` ro'yxatiga tushadi). Tashqi ifodani baholayotganda uni
    yopiq, xavfsiz bo'lak deb qarash kerak — aks holda har ichki escape
    qilingan shablon TASHQI ifodani ham yiqitardi."""
    tokenlar, shablonlar = js_tahlil(ifoda)
    oraliqlar = [(b, o) for tur, b, o in tokenlar if tur == "satr"]
    for sh in shablonlar:
        if sh["ota"] is None and sh["oxir"] is not None:
            oraliqlar.append((sh["bosh"], sh["oxir"]))
    if not oraliqlar:
        return ifoda
    oraliqlar.sort()
    natija = []
    oxirgi = 0
    for b, o in oraliqlar:
        if b < oxirgi:
            continue
        natija.append(ifoda[oxirgi:b])
        natija.append("'L'")
        oxirgi = o
    natija.append(ifoda[oxirgi:])
    return "".join(natija)


def _qavs_ichi(ifoda, bosh):
    """`bosh` dagi `(` ga mos yopuvchi qavs o'rnini qaytaradi."""
    daraja = 0
    tokenlar, shablonlar = js_tahlil(ifoda)
    yopiq = [(b, o) for _, b, o in tokenlar]
    for sh in shablonlar:
        if sh["ota"] is None and sh["oxir"] is not None:
            yopiq.append((sh["bosh"], sh["oxir"]))
    for p in range(bosh, len(ifoda)):
        if any(b <= p < o for b, o in yopiq):
            continue
        if ifoda[p] == "(":
            daraja += 1
        elif ifoda[p] == ")":
            daraja -= 1
            if daraja == 0:
                return p
    return -1


def _map_zanjiri_xavfsizmi(ifoda, atributda):
    """`X.map(CB)` / `X.map(CB).join(L)` — element darajasida escape.

    `CB` `escapeHtml` bo'lsa yoki `x => <xavfsiz ifoda>` bo'lsa, ro'yxat
    elementlari CHIZISH joyida escape qilinadi; shablon literali bo'lsa u
    alohida tekshiriladi. Shu sababli butun zanjir xavfsiz."""
    p = ifoda.find(".map(")
    if p < 0:
        return False
    yopuvchi = _qavs_ichi(ifoda, p + 4)
    if yopuvchi < 0:
        return False
    cb = ifoda[p + 5:yopuvchi].strip()
    qoldiq = ifoda[yopuvchi + 1:].strip()
    if qoldiq and not re.fullmatch(r"\.join\(\s*(?:'[^']*'|\"[^\"]*\")?\s*\)", qoldiq):
        return False
    if cb == "escapeHtml" or cb == "jsAttrEscape":
        return True
    m = re.match(r"(?:\(\s*[\w$,\s]*\)|[\w$]+)\s*=>\s*(.+)$", cb, re.S)
    if not m:
        return False
    tana = m.group(1).strip()
    return xavfsizmi(tana, atributda) or not matn_tegadimi(tana)


def xavfsizmi(ifoda, atributda=False):
    """Interpolyatsiya xavfsizmi? (chuqurlikka kirib tekshiradi)"""
    ifoda = " ".join(ifoda.split()).strip()
    if not ifoda:
        return True
    # Tashqi qavslarni olib tashlaymiz: `('#' + x.id)` → `'#' + x.id`
    while ifoda.startswith("(") and _qavs_ichi(ifoda, 0) == len(ifoda) - 1:
        ifoda = ifoda[1:-1].strip()
        if not ifoda:
            return True
    maskalangan = _maskala(ifoda)
    if maskalangan != ifoda:
        ifoda = maskalangan
    if _map_zanjiri_xavfsizmi(ifoda, atributda):
        return True
    if _xarita_murojaatimi(ifoda, XARITALAR):
        return True
    if _bitta_belgimi(ifoda):
        return True
    if re.fullmatch(r"[A-Za-z_$][\w$]*", ifoda) and ifoda in QIYMATLAR \
            and ifoda not in _KORILGAN_NOM:
        _KORILGAN_NOM.add(ifoda)
        try:
            return all(xavfsizmi(q, atributda) or not matn_tegadimi(q)
                       for q in QIYMATLAR[ifoda])
        finally:
            _KORILGAN_NOM.discard(ifoda)
    fn_royxat = XAVFSIZ_FN_ATRIBUT if atributda else XAVFSIZ_FN
    if LITERAL_NAQSH.fullmatch(ifoda):
        return True
    if SON_NAQSH.fullmatch(ifoda):
        return True
    if son_yoki_id(ifoda):
        return True
    if re.fullmatch(r"[\w$.]+\.toFixed\(\s*\d+\s*\)", ifoda):
        return True
    if re.fullmatch(r"[\w$.]+\s*(\+|-|\*|/)\s*[\w$.0-9]+", ifoda) and \
            all(son_yoki_id(x) or SON_NAQSH.fullmatch(x.strip())
                for x in re.split(r"[+\-*/]", ifoda) if x.strip()):
        return True
    if _toliq_chaqiruvmi(ifoda, fn_royxat):
        return True
    # Tarkibiy ifodada har operand: XAVFSIZ yoki foydalanuvchi MATNIGA
    # TEGMAYDIGAN (son, id, kod konstantasi) bo'lishi kifoya — bu butun
    # darvozaning asosiy qoidasi bilan bir xil.
    def operand_ok(x):
        # Solishtirish natijasi — `true` / `false`, chizilsa ham xavfsiz.
        return (_shartmi(x) or xavfsizmi(x, atributda)
                or not matn_tegadimi(x))

    # uchlik shart (ichma-ich ham): `a ? b : c` — SHART (a) chizilmaydi,
    # faqat tarmoqlar tekshiriladi. `a ? b : c ? d : e` da o'ng tarmoq
    # o'zi yana uchlik shart bo'ladi va REKURSIV tekshiriladi.
    bolaklar = _tepa_bolish(ifoda, ["?"])
    if len(bolaklar) > 1:
        tarmoqlar = _tepa_bolish("?".join(bolaklar[1:]), [":"])
        if len(tarmoqlar) > 1:
            chap = tarmoqlar[0]
            ong = ":".join(tarmoqlar[1:])
            return operand_ok(chap) and operand_ok(ong)
    # `a || b`, `a ?? b`, `a && b`
    for belgi in ("||", "??", "&&"):
        bolaklar = _tepa_bolish(ifoda, [belgi])
        if len(bolaklar) > 1:
            return all(operand_ok(b) for b in bolaklar)
    # `a + b + c` — har operand xavfsiz bo'lsa, birikma ham xavfsiz
    bolaklar = _tepa_bolish(ifoda, ["+"])
    if len(bolaklar) > 1:
        return all(operand_ok(b) for b in bolaklar)
    return False


# ══════════════════════════════════════════════════════════════
# 3. RUXSAT RO'YXATI (har biri SABAB bilan)
# ══════════════════════════════════════════════════════════════
# Kalit: (fayl, normallashtirilgan ifoda). Qiymat — SABAB (majburiy).
# Ruxsat FAQAT o'lchangan / o'qilgan holatlar uchun beriladi.
RUXSAT = {
    # ── Server GENERATORLARI (foydalanuvchi matni emas) ──────────
    ("dashboard.html", "o.order_number"): "server generatori (crud.create_order)",
    ("dashboard.html", "d.order_number"): "server generatori (crud.create_order)",
    ("orders.html", "o.order_number"): "server generatori (crud.create_order)",
    ("returns.html", "o.order_number"): "server generatori (crud.create_order)",
    ("returns.html", "it.order_number"): "server generatori (crud.create_order)",
    ("orders.html", "dl.delivery_number"): "server generatori (crud.create_delivery)",
    ("orders.html", "a.file_url"): "server generatori (`main._save_upload`) — TEXNIK ustun",
    # ── ENUM ustunlar (server nazoratida) ────────────────────────
    ("orders.html", "o.status"): "OrderStatus enum — erkin matn emas",
    ("production.html", "po.status"): "ProductionOrderStatus enum — erkin matn emas",
    ("inventory.html", "m.movement_type"): "InventoryMovement turi — enum",
    ("supplier_receive.html", "res.status"): "`fetch` javobining HTTP status RAQAMI",
    ("suppliers.html", "res.status"): "`fetch` javobining HTTP status RAQAMI",
    # ── KOD konstantalari (o'qib tasdiqlangan) ───────────────────
    ("dashboard.html", "it.label"):
        "kech30: qiymat CHIZISHDAN OLDIN escape qilinadi (buildX ichida escapeHtml)",
    ("finance.html", "title"):
        "`expGroup(icon, title, ...)` parametri — chaqiruvchilar (825/840/858/873) "
        "faqat literal beradi",
    ("finance.html", "name"):
        "donut afsonasi: `entries` massivi kod konstantalaridan destrukturizatsiya",
    ("finished.html", "unit"):
        "1595–1671: faqat 'metr' / 'dona' konstantalari (1222 dagi `unit` boshqa ko'lam)",
    ("inventory.html", "g.icon"):
        "801–821: faqat uch kod emojisi ('📋' / '🏭' / '📦')",
    ("kpi.html", "detail"):
        "795–802: kod konstantalari + escapeHtml(e.per_unit_type) "
        "(1706 dagi `detail` — boshqa ko'lam)",
    ("orders.html", "label"):
        "`STATUS_BADGE[order.status] || ['badge', order.status]` — kod xaritasi / enum",
    ("orders.html", "i.source_label"): "kech32: `crud` da qat'iy konstanta",
    ("orders.html", "fpUnitLabel(fp.unit)"):
        "kech32: faqat 'm' / 'm²' / 'ta' qaytaradi",
    ("projects.html", "e.icon"):
        "661–672: voqealar JS da tuziladi, `icon` — `ti-*` kod konstantasi",
    ("recipes.html", "st.icon"): "kech31: `recpCatStyle()` → `RECP_CAT_STYLE` qat'iy xaritasi",
    ("recipes.html", "st.label"): "kech31: `recpCatStyle()` → `RECP_CAT_STYLE` qat'iy xaritasi",
    # ── `initials()` — faqat bosh harflar, ≤ 2 belgi ─────────────
    # Dinamik darvoza `/kpi` va `/ustalar` da belgi bilan O'LCHADI: tugun 0.
    ("kpi.html", "initials(m.name)"): "≤2 bosh harf — teg yasay olmaydi (dinamik o'lchandi)",
    ("kpi.html", "initials(e.name)"): "≤2 bosh harf — teg yasay olmaydi (dinamik o'lchandi)",
    ("masters_manage.html", "initials(m.name)"):
        "≤2 bosh harf — teg yasay olmaydi (dinamik o'lchandi)",
}

# Joriy skript blokida e'lon qilingan kod xaritalari (`const X = {...}`).
# `fayl_skan` har blok oldidan to'ldiradi.
XARITALAR = set()
# Joriy blokdagi mahalliy o'zgaruvchilarga berilgan qiymatlar.
QIYMATLAR = {}
# Rekursiya qo'riqchisi (`a = b; b = a` kabi halqalar uchun).
_KORILGAN_NOM = set()

# Jinja (Q3) uchun alohida ruxsat: (fayl, ifoda) → sabab
RUXSAT_JINJA = {}


def _normal(s):
    return " ".join(s.split())


def maydonlar_ichida(ifoda):
    """Ifodada tilga olingan maydon / o'zgaruvchi nomlari."""
    nomlar = set(re.findall(r"\.([A-Za-z_]\w*)", ifoda))
    nomlar |= set(re.findall(r"\[\s*['\"](\w+)['\"]\s*\]", ifoda))
    nomlar |= set(re.findall(r"\b([A-Za-z_]\w*)\b", ifoda))
    return nomlar


def matn_tegadimi(ifoda):
    """Ifoda foydalanuvchi MATNIGA tegadimi? (MATN_MAYDON — modeldan)

    Nima uchun shunday: har `${...}` ni talab qilish 456 ta yolg'on
    bayroq berdi (son, rang, foiz, kod ikonkasi). Qoida MODELDAN olingan
    matn ustunlariga bog'landi — ro'yxat o'z-o'zidan yangilanadi, chunki
    yangi `String`/`Text` ustuni qo'shilishi bilan darvoza uni ko'radi."""
    return bool(maydonlar_ichida(_maskala(ifoda)) & MATN_MAYDON)


# ══════════════════════════════════════════════════════════════
# 4. HTML KONTEKSTI (matn / onX atributi)
# ══════════════════════════════════════════════════════════════
ON_ATRIBUT = re.compile(r"\bon[a-z]+\s*=\s*$", re.I)


def kontekstlar(tiklangan, joylar):
    """`tiklangan` — HTML bo'lagi, unda har interpolyatsiya o'rniga
    bitta \\x00 belgisi turadi. Qaytaradi: har \\x00 uchun kontekst —
    'matn' yoki 'on:<atribut>' yoki 'atr:<atribut>'."""
    natija = []
    i = 0
    teg_ichida = False
    atribut = None
    tirnoq = None
    joriy_nom = ""
    while i < len(tiklangan):
        c = tiklangan[i]
        if c == "\x00":
            if atribut is not None:
                natija.append(("on:" if atribut.lower().startswith("on") else "atr:") + atribut)
            else:
                natija.append("matn")
            i += 1
            continue
        if atribut is not None:
            if tirnoq and c == tirnoq:
                atribut = None
                tirnoq = None
            elif not tirnoq and c in " \t\n>":
                atribut = None
                if c == ">":
                    teg_ichida = False
            i += 1
            continue
        if not teg_ichida:
            if c == "<" and i + 1 < len(tiklangan) and \
                    (tiklangan[i + 1].isalpha() or tiklangan[i + 1] == "/"):
                teg_ichida = True
                joriy_nom = ""
            i += 1
            continue
        # teg ichida
        if c == ">":
            teg_ichida = False
            joriy_nom = ""
            i += 1
            continue
        m = re.match(r"([A-Za-z_:@-][\w:.-]*)\s*=\s*([\"']?)", tiklangan[i:])
        if m:
            joriy_nom = m.group(1)
            atribut = joriy_nom
            tirnoq = m.group(2) or None
            i += len(m.group(0))
            continue
        i += 1
    return natija


def shablon_tiklash(manba, sh):
    """Shablon literalini \\x00 o'rin egallovchilari bilan tiklaydi."""
    bolaklar = []
    matn = sh["matn"]
    ifodalar = sorted(sh["ifodalar"])
    for k, (b, o) in enumerate(matn):
        bolaklar.append(manba[b:o])
        if k < len(ifodalar):
            bolaklar.append("\x00")
    return "".join(bolaklar), [manba[b:o] for b, o in ifodalar]


# ══════════════════════════════════════════════════════════════
# 5. SATR BIRIKMASI (`'<td>' + x + '</td>'`) — logs.html naqshi
# ══════════════════════════════════════════════════════════════
def birikma_zanjiri(manba, tokenlar, satr_idx):
    """`satr_idx` dagi satr tokenidan boshlab `+` zanjirini ikki tomonga
    yig'adi. Qaytaradi: (bo'laklar, birinchi_token_indeksi) — bo'laklar
    ('satr', matn) yoki ('ifoda', matn) juftliklari."""
    satrlar = [(k, t) for k, t in enumerate(tokenlar) if t[0] == "satr"]
    del satrlar
    bolaklar = []
    # chapga
    chap = satr_idx
    while True:
        b = tokenlar[chap][1]
        oldingi_matn = manba[:b].rstrip()
        if not oldingi_matn.endswith("+"):
            break
        oldin = oldingi_matn[:-1].rstrip()
        # oldingi operand — satr tokeni bo'lsa zanjirni davom ettiramiz
        oldingi_token = None
        for k in range(chap - 1, -1, -1):
            if tokenlar[k][0] == "satr" and tokenlar[k][2] == len(oldin):
                oldingi_token = k
                break
            if tokenlar[k][2] <= len(oldin):
                break
        if oldingi_token is None:
            break
        chap = oldingi_token
    # o'ngga yurib yig'amiz
    i = tokenlar[chap][1]
    while i < len(manba):
        # joriy operand: satr tokenimi?
        token = next((t for t in tokenlar if t[0] == "satr" and t[1] == i), None)
        if token:
            bolaklar.append(("satr", manba[token[1]:token[2]]))
            i = token[2]
        else:
            # ifoda: keyingi eng yuqori darajadagi `+` gacha
            daraja = 0
            j = i
            while j < len(manba):
                if any(b <= j < o for _, b, o in tokenlar):
                    j += 1
                    continue
                c = manba[j]
                if c in "([{":
                    daraja += 1
                elif c in ")]}":
                    if daraja == 0:
                        break
                    daraja -= 1
                elif daraja == 0 and c in "+,;?:":
                    break
                j += 1
            bolaklar.append(("ifoda", manba[i:j]))
            i = j
        qoldiq = manba[i:]
        m = re.match(r"\s*\+\s*", qoldiq)
        if not m:
            break
        i += m.end()
    return bolaklar, chap


def birikma_tiklash(bolaklar):
    """Birikma bo'laklaridan HTML va ifodalar ro'yxatini tiklaydi."""
    html = []
    ifodalar = []
    for tur, matn in bolaklar:
        if tur == "satr":
            ichki = matn[1:-1]
            ichki = ichki.replace("\\'", "'").replace('\\"', '"').replace("\\n", "\n")
            html.append(ichki)
        else:
            html.append("\x00")
            ifodalar.append(matn.strip())
    return "".join(html), ifodalar


def html_korinadimi(s):
    """Matn HTML chizadimi? (`<teg` naqshi bor)"""
    return bool(re.search(r"<\s*/?[a-zA-Z][\w-]*", s))


# ══════════════════════════════════════════════════════════════
# 6. SHABLON FAYLINI SKANERLASH
# ══════════════════════════════════════════════════════════════
SKRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.S)


def qator(matn, siljish):
    return matn.count("\n", 0, siljish) + 1


def fayl_skan(yol):
    """Bitta shablon faylini skanerlaydi.
    Qaytaradi: (q1_topilgan, q2_topilgan, q3_topilgan) ro'yxatlari."""
    with io.open(yol, encoding="utf-8") as fh:
        html = fh.read()
    fn = os.path.basename(yol)
    q1 = []
    q2 = []

    skript_oraliq = []
    for m in SKRIPT.finditer(html):
        kod = m.group(1)
        siljish = m.start(1)
        skript_oraliq.append((m.start(), m.end()))
        global XARITALAR, QIYMATLAR
        XARITALAR = kod_xaritalari(kod)
        QIYMATLAR = mahalliy_qiymatlar(kod)
        tokenlar, shablonlar = js_tahlil(kod)

        # ── Q1 / Q2: template literallar ─────────────────────────
        for sh in shablonlar:
            tiklangan, ifodalar = shablon_tiklash(kod, sh)
            if not ifodalar:
                continue
            ktx = kontekstlar(tiklangan, None)
            html_mi = html_korinadimi(tiklangan)
            for k, ifoda in enumerate(ifodalar):
                kontekst = ktx[k] if k < len(ktx) else "matn"
                atributda = kontekst.startswith("on:")
                if not html_mi and not atributda:
                    continue
                if kontekst.startswith("atr:") and not html_mi:
                    continue
                kalit = (fn, _normal(ifoda))
                if kalit in RUXSAT:
                    continue
                joy = siljish + sorted(sh["ifodalar"])[k][0]
                if atributda:
                    if "escapeHtml(" in ifoda:
                        q2.append((qator(html, joy), _normal(ifoda), kontekst,
                                   "escapeHtml onX atributida YETARLI EMAS — jsAttrEscape"))
                    elif not xavfsizmi(ifoda, atributda=True) and matn_tegadimi(ifoda):
                        q2.append((qator(html, joy), _normal(ifoda), kontekst,
                                   "jsAttrEscape yo'q"))
                elif not xavfsizmi(ifoda, atributda=False) and matn_tegadimi(ifoda):
                    q1.append((qator(html, joy), _normal(ifoda), kontekst,
                               "escapeHtml yo'q"))

        # ── Q1 / Q2: satr birikmalari ────────────────────────────
        korilgan = set()
        for idx, (tur, b, o) in enumerate(tokenlar):
            if tur != "satr":
                continue
            if b in korilgan:
                continue
            if not html_korinadimi(kod[b:o]):
                continue
            bolaklar, chap = birikma_zanjiri(kod, tokenlar, idx)
            if len(bolaklar) < 2:
                continue
            for tur2, matn2 in bolaklar:
                if tur2 == "satr":
                    p = kod.find(matn2, tokenlar[chap][1])
                    if p >= 0:
                        korilgan.add(p)
            tiklangan, ifodalar = birikma_tiklash(bolaklar)
            if not ifodalar:
                continue
            ktx = kontekstlar(tiklangan, None)
            for k, ifoda in enumerate(ifodalar):
                kontekst = ktx[k] if k < len(ktx) else "matn"
                atributda = kontekst.startswith("on:")
                kalit = (fn, _normal(ifoda))
                if kalit in RUXSAT:
                    continue
                joy = siljish + tokenlar[chap][1]
                if atributda:
                    if "escapeHtml(" in ifoda:
                        q2.append((qator(html, joy), _normal(ifoda), kontekst,
                                   "escapeHtml onX atributida YETARLI EMAS — jsAttrEscape"))
                    elif not xavfsizmi(ifoda, atributda=True) and matn_tegadimi(ifoda):
                        q2.append((qator(html, joy), _normal(ifoda), kontekst,
                                   "jsAttrEscape yo'q (satr birikmasi)"))
                elif not xavfsizmi(ifoda, atributda=False) and matn_tegadimi(ifoda):
                    q1.append((qator(html, joy), _normal(ifoda), kontekst,
                               "escapeHtml yo'q (satr birikmasi)"))

    # ── Q3: Jinja onX atributlari (skript BLOKLARIDAN TASHQARIDA) ──
    maskalangan = list(html)
    for b, o in skript_oraliq:
        for p in range(b, o):
            maskalangan[p] = " "
    maskalangan = "".join(maskalangan)
    q3 = []
    for m in re.finditer(r"\bon[a-z]+\s*=\s*([\"'])(.*?)\1", maskalangan, re.S | re.I):
        tirnoq = m.group(1)
        qiymat = m.group(2)
        for j in re.finditer(r"\{\{(.*?)\}\}", qiymat, re.S):
            ifoda = _normal(j.group(1))
            kalit = (fn, ifoda)
            if kalit in RUXSAT_JINJA:
                continue
            joy = m.start(2) + j.start()
            if re.search(r"\|\s*replace\s*\(\s*(\"'\"|'\"'|'\\\\''|\"\\\\\"\")", ifoda):
                q3.append((qator(html, joy), ifoda,
                           "|replace(tirnoq) HIMOYA EMAS — data-* + dataset ishlating"))
                continue
            if "|replace(" in ifoda.replace(" ", ""):
                q3.append((qator(html, joy), ifoda,
                           "|replace(...) onX atributida ishonchsiz — data-* + dataset"))
                continue
            # `|tojson` — kech33 da O'LCHANGAN (jinja2, autoescape):
            #   YAKKA tirnoqli atribut: `'` → `\u0027`, qiymat JS satridan
            #     CHIQMAYDI va atributni sindirmaydi → XAVFSIZ.
            #   QO'SH tirnoqli atribut: `tojson` o'zi qo'yadigan `"` atributni
            #     DARHOL yopadi → IN'EKTSIYA. Shuning uchun tirnoq turi muhim.
            if re.search(r"\|\s*tojson\b", ifoda):
                if tirnoq == "'":
                    continue
                q3.append((qator(html, joy), ifoda,
                           "|tojson QO'SH tirnoqli atributda — o'zi qo'ygan \" "
                           "atributni yopadi (o'lchangan); yakka tirnoq ishlating"))
                continue
            if jinja_xavfsizmi(ifoda):
                continue
            q3.append((qator(html, joy), ifoda,
                       "onX atributida Jinja qiymati — data-* + dataset ishlating"))
    return q1, q2, q3


JINJA_ID = re.compile(
    r"(?:[\w]+\.)*(?:id|ids|index|index0|counter|counter0|year|month|day|"
    r"quantity|amount|price|total|count|percent|level|tier_id|employee_id|"
    r"master_id|order_id|project_id|item_id|supplier_id|inventory_id|"
    r"product_type_id|bom_id|recipe_id|min_stock|stock_quantity|qty|"
    r"length|width|thickness|no|num|period|page)"
    r"(?:\s*or\s*(?:0|'')\s*)?"
)


def jinja_xavfsizmi(ifoda):
    """Jinja ifodasi onX atributida xavfsizmi?
    Faqat: son, id ko'rinishidagi maydon, `'a' if ... else 'b'` naqshi,
    `loop.index`, `'...'` literali."""
    ifoda = ifoda.strip()
    if SON_NAQSH.fullmatch(ifoda):
        return True
    if re.fullmatch(r"'[^'\\]*'|\"[^\"\\]*\"", ifoda):
        return True
    if son_yoki_id(ifoda.replace(" or 0", "").replace(" or ''", "")):
        return True
    if JINJA_ID.fullmatch(ifoda):
        return True
    # `'true' if x else 'false'` — natija DOIM kod konstantasi
    m = re.fullmatch(r"('[^'\\]*'|\"[^\"\\]*\"|\d+)\s+if\s+.+?\s+else\s+"
                     r"('[^'\\]*'|\"[^\"\\]*\"|\d+)", ifoda, re.S)
    if m:
        return True
    if re.fullmatch(r"[\w.]+\s*\|\s*(int|float|round|length|abs)"
                    r"(\(\s*\d*\s*\))?", ifoda):
        return True
    return False


# ══════════════════════════════════════════════════════════════
# 7. Q4 — `reports.html` ustun funksiyalari
# ══════════════════════════════════════════════════════════════
def _model_matn_ustunlari():
    """MATN ustunlari ro'yxati MODELDAN o'qiladi — qo'lda yozilgan ro'yxat
    eskiradi va darvozada jim teshik qoldiradi. `models.py` va
    `production_models.py` dagi HAR `String`/`Text` ustuni olinadi."""
    nomlar = set()
    for fayl in ("models.py", "production_models.py"):
        yol = os.path.join(ROOT, fayl)
        if not os.path.exists(yol):
            continue
        with io.open(yol, encoding="utf-8") as fh:
            manba = fh.read()
        for m in re.finditer(r"^\s*(\w+)\s*=\s*Column\(\s*(?:String|Text)\b",
                             manba, re.M):
            nomlar.add(m.group(1))
    return nomlar


# Shablonlardagi MAHALLIY o'zgaruvchilar (ustun nomi emas, lekin qiymati —
# o'sha ustunlardan olingan foydalanuvchi matni). Bular kech28–kech32
# auditlarida O'QILGAN joylardan yig'ilgan.
MAHALLIY_MATN = set("""
message detail text title nomi nom dim qtyText mainName subDetail comment izoh
sabab employee_name master_name supplier_name material_name inventory_name
product_type_name type_name source_name order_name client customer_name
worker_name penoplast_name recipe_name source_label status_label month_label
detail_text shortages inventory_log inventory_changes xatolar warnings
""".split())

MATN_MAYDON = _model_matn_ustunlari() | MAHALLIY_MATN


def ustun_funksiyalari(yol):
    """`['Sarlavha', r => r.maydon]` naqshidagi ustunlar: MATN maydonini
    escape qilmasdan qaytaradiganlarini topadi."""
    with io.open(yol, encoding="utf-8") as fh:
        html = fh.read()
    topilgan = []
    for m in re.finditer(
            r"\[\s*(?:'[^']*'|\"[^\"]*\")\s*,\s*(\w+)\s*=>\s*(.+?)\s*\](?=\s*[,\]\)])",
            html, re.S):
        tana = _normal(m.group(2))
        # Tana SHABLON LITERALI bo'lsa — har `${...}` ni alohida tekshiramiz
        # (aks holda `${escapeHtml(i.unit)}` bor tana ham bayroqlanardi).
        _, shablonlar = js_tahlil(tana)
        ifodalar = []
        for sh in shablonlar:
            if sh["ota"] is not None:
                continue
            _, ifs = shablon_tiklash(tana, sh)
            ifodalar.extend(ifs)
        if not ifodalar:
            ifodalar = [tana]
        for ifoda in ifodalar:
            if xavfsizmi(ifoda):
                continue
            if not matn_tegadimi(ifoda):
                continue
            topilgan.append((qator(html, m.start()), _normal(ifoda)))
    return topilgan


# ══════════════════════════════════════════════════════════════
# 8. LEKSERNING O'Z-O'ZINI SINASHI
# ══════════════════════════════════════════════════════════════
def lekser_sinovi():
    section("1. Lekser o'z-o'zini sinaydi (darvoza jim teshik bo'lmasligi uchun)")

    # (a) regex literali satr boshi deb o'qilmasligi SHART
    kod = r"""const a = s.replace(/"/g, '&quot;'); const b = `<i>${x.name}</i>`;"""
    tokenlar, shablonlar = js_tahlil(kod)
    regexlar = [t for t in tokenlar if t[0] == "regex"]
    check("regex literali (/\"/g) tanildi", len(regexlar) == 1,
          str([kod[b:o] for _, b, o in tokenlar]))
    check("regexdan KEYINGI shablon literali topildi", len(shablonlar) == 1,
          str(len(shablonlar)))
    if shablonlar:
        _, ifodalar = shablon_tiklash(kod, shablonlar[0])
        check("regexdan keyingi ${x.name} ajratildi", ifodalar == ["x.name"],
              str(ifodalar))

    # (b) bo'lish amali regex deb o'qilmasligi SHART
    kod2 = "const c = a / b; const d = (x) / 2; const e = `<b>${y.nomi}</b>`;"
    tokenlar2, shablonlar2 = js_tahlil(kod2)
    check("bo'lish amali regex deb o'qilmadi",
          not [t for t in tokenlar2 if t[0] == "regex"],
          str([kod2[b:o] for tur, b, o in tokenlar2 if tur == "regex"]))
    check("bo'lishdan keyingi shablon topildi", len(shablonlar2) == 1)

    # (c) satr ichidagi `${` shablon deb o'qilmasligi SHART
    kod3 = "const t = '${yolgon}'; const u = `<i>${chin.name}</i>`;"
    _, shablonlar3 = js_tahlil(kod3)
    check("satr ichidagi ${...} shablon deb o'qilmadi", len(shablonlar3) == 1,
          str(len(shablonlar3)))
    if shablonlar3:
        _, ifodalar3 = shablon_tiklash(kod3, shablonlar3[0])
        check("faqat HAQIQIY shablon ifodasi ajratildi", ifodalar3 == ["chin.name"],
              str(ifodalar3))

    # (d) ichma-ich shablon va ${} ichidagi shablon
    kod4 = "const v = `<a>${x ? `<b>${y.name}</b>` : ''}</a>`;"
    _, shablonlar4 = js_tahlil(kod4)
    check("ichma-ich shablon literallari ajratildi", len(shablonlar4) == 2,
          str(len(shablonlar4)))

    # (e) izohlar
    kod5 = "// `<i>${a}</i>`\n/* `${b}` */\nconst w = `<i>${c.name}</i>`;"
    _, shablonlar5 = js_tahlil(kod5)
    check("izoh ichidagi shablon hisobga olinmadi", len(shablonlar5) == 1,
          str(len(shablonlar5)))

    # (f) satr ichidagi qochirilgan tirnoq
    kod6 = "const x = 'a\\'b'; const y = `<i>${z.name}</i>`;"
    _, shablonlar6 = js_tahlil(kod6)
    check("qochirilgan tirnoq satrni erta yopmadi", len(shablonlar6) == 1,
          str(len(shablonlar6)))

    # (g) kalit so'zdan keyingi regex
    kod7 = "function f(s) { return /a\\/b/.test(s); }"
    tokenlar7, _ = js_tahlil(kod7)
    check("return dan keyingi regex tanildi",
          len([t for t in tokenlar7 if t[0] == "regex"]) == 1,
          str([kod7[b:o] for tur, b, o in tokenlar7 if tur == "regex"]))

    # (h) regex ichidagi belgilar sinfi
    kod8 = r"const r = /[/'\"]+/g; const s = `<i>${a.name}</i>`;"
    _, shablonlar8 = js_tahlil(kod8)
    check("regex belgilar sinfi ichidagi / oxiri deb o'qilmadi",
          len(shablonlar8) == 1, str(len(shablonlar8)))

    # (i) HTML konteksti: matn va onX atributi
    kod9 = ("const h = `<div onclick=\"f('${a.name}')\" title=\"${b.name}\">"
            "${c.name}</div>`;")
    _, shablonlar9 = js_tahlil(kod9)
    check("kontekst sinovi uchun shablon topildi", len(shablonlar9) == 1)
    if shablonlar9:
        tiklangan, ifodalar9 = shablon_tiklash(kod9, shablonlar9[0])
        ktx = kontekstlar(tiklangan, None)
        check("onX atributi / oddiy atribut / matn konteksti ajratildi",
              ktx == ["on:onclick", "atr:title", "matn"], str(ktx))

    # (j) xavfsizlik predikati
    check("escapeHtml(x) — matnda xavfsiz", xavfsizmi("escapeHtml(x.name)"))
    check("x.name — matnda XAVFSIZ EMAS", not xavfsizmi("x.name"))
    check("escapeHtml(x) — onX atributida XAVFSIZ EMAS",
          not xavfsizmi("escapeHtml(x.name)", atributda=True))
    check("jsAttrEscape(x) — onX atributida xavfsiz",
          xavfsizmi("jsAttrEscape(x.name)", atributda=True))
    check("escapeHtml(a) + b — to'liq chaqiruv emas, XAVFSIZ EMAS",
          not xavfsizmi("escapeHtml(a) + b.name"))
    check("uchlik shart: ikkala tarmoq xavfsiz",
          xavfsizmi("x ? escapeHtml(a.name) : ''"))
    check("uchlik shart: bitta tarmoq xavfsiz emas",
          not xavfsizmi("x ? escapeHtml(a.name) : b.name"))
    check("son / id naqshi xavfsiz", xavfsizmi("item.id") and xavfsizmi("42"))
    check("`a || b` — ikkalasi ham tekshiriladi",
          not xavfsizmi("a.name || b.name") and xavfsizmi("escapeHtml(a.name) || ''"))

    # (k) Jinja predikati
    check("Jinja: {{ p.id }} xavfsiz", jinja_xavfsizmi("p.id"))
    check("Jinja: {{ e.name }} XAVFSIZ EMAS", not jinja_xavfsizmi("e.name"))
    check("Jinja: 'true' if x else 'false' xavfsiz",
          jinja_xavfsizmi("'true' if e.is_active else 'false'"))
    check("Jinja: {{ x|replace(...) }} XAVFSIZ EMAS",
          not jinja_xavfsizmi("e.name|replace('\"', '&quot;')"))


# ══════════════════════════════════════════════════════════════
# 9. ASOSIY
# ══════════════════════════════════════════════════════════════
def main():
    lekser_sinovi()

    fayllar = sorted(f for f in os.listdir(SHABLON_PAPKA) if f.endswith(".html"))
    section(f"2. Q1 — HTML matnida escapeHtml ({len(fayllar)} shablon)")
    jami_q1 = jami_q2 = jami_q3 = 0
    natijalar = {}
    for fn in fayllar:
        q1, q2, q3 = fayl_skan(os.path.join(SHABLON_PAPKA, fn))
        natijalar[fn] = (q1, q2, q3)
        jami_q1 += len(q1)
        jami_q2 += len(q2)
        jami_q3 += len(q3)
    for fn in fayllar:
        q1 = natijalar[fn][0]
        check(f"{fn}: HTML matnida escape qilinmagan interpolyatsiya yo'q ({len(q1)})",
              not q1,
              "\n".join(f"{fn}:{q}  [{k}]  {i}   ← {s}" for q, i, k, s in q1[:40]))

    section("3. Q2 — onX atributida jsAttrEscape (escapeHtml YETARLI EMAS)")
    for fn in fayllar:
        q2 = natijalar[fn][1]
        check(f"{fn}: onX atributida xavfsiz bo'lmagan interpolyatsiya yo'q ({len(q2)})",
              not q2,
              "\n".join(f"{fn}:{q}  [{k}]  {i}   ← {s}" for q, i, k, s in q2[:40]))

    section("4. Q3 — H2: server (Jinja) shablonidagi onX atributi")
    for fn in fayllar:
        q3 = natijalar[fn][2]
        check(f"{fn}: onX atributida xavfsiz bo'lmagan Jinja qiymati yo'q ({len(q3)})",
              not q3,
              "\n".join(f"{fn}:{q}  {{{{ {i} }}}}   ← {s}" for q, i, s in q3[:40]))

    section("5. Q4 — `reports.html` ustun funksiyalari")
    for fn in fayllar:
        yol = os.path.join(SHABLON_PAPKA, fn)
        topilgan = ustun_funksiyalari(yol)
        check(f"{fn}: ustun funksiyasi MATN maydonini escape siz qaytarmaydi ({len(topilgan)})",
              not topilgan,
              "\n".join(f"{fn}:{q}  {t}" for q, t in topilgan[:40]))

    info(f"jami topilgan: Q1={jami_q1} Q2={jami_q2} Q3={jami_q3}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        import traceback
        FAIL += 1
        print("  ❌ KUTILMAGAN ISTISNO:\n" + traceback.format_exc()[-2500:])
    print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
    sys.exit(0 if FAIL == 0 else 1)
