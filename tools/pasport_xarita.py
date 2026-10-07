#!/usr/bin/env python3
"""pasport_xarita.py — `LOYIHA_PASPORTI.md` dagi AVTOMATIK bo'limlarni KODDAN yasaydi.

NIMA UCHUN KERAK
----------------
Pasport (16-band) yangi chatga "repo + muammo tavsifi yetarli" bo'lishi uchun
yozilgan. Qo'lda yozilgan xarita tez eskiradi: yangi endpoint, yangi migratsiya
yoki yangi test qo'shilsa, pasport jim turib yolg'on gapira boshlaydi. Shuning
uchun sahifa → marshrut → funksiya xaritasi, API ro'yxati, ishga tushish
(migratsiya) tartibi, jadvallar, muhit o'zgaruvchilari va testlar katalogi shu
skript bilan KODDAN olinadi va pasportdagi belgilangan bloklar ichiga yoziladi.
`tools/test_pasport.py` bloklar kod bilan AYNAN mosligini tekshiradi (darvoza).

ISHLATISH
---------
    python3 tools/pasport_xarita.py             # bloklarni ekranga chiqaradi
    python3 tools/pasport_xarita.py --yoz       # LOYIHA_PASPORTI.md dagi AVTO bloklarni yangilaydi
    python3 tools/pasport_xarita.py --tekshir   # farq bo'lsa ro'yxatini chiqarib, 1 bilan tugaydi

Blok belgilari (pasport ichida, qo'lda TAHRIRLANMAYDI):
    <!-- AVTO:NOM BOSHI -->
    ...
    <!-- AVTO:NOM OXIRI -->

QOIDALAR (natija Python 3.11 va 3.12 da AYNAN bir xil bo'lishi uchun)
---------------------------------------------------------------------
* `main.py`, `production_routes.py`, `models.py`, `production_models.py` va
  testlar `ast` bilan o'qiladi (ular 3.11 da ham import qilinadi).
* `saas_migration.py` faqat MATN (regex) bilan o'qiladi — unda 3.12 ga xos
  f-satr sintaksisi bor, 3.11 `ast` uni o'qiy olmaydi.
* Qator raqamlari YOZILMAYDI (har tahrirda o'zgaradi) — faqat nomlar.
* Hamma ro'yxat tartiblangan — natija deterministik.
"""
import ast
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASPORT = os.path.join(ROOT, "LOYIHA_PASPORTI.md")

HTTP_USULLAR = ("get", "post", "put", "delete", "patch")

# Handler tanasidagi to'g'ridan-to'g'ri chaqiruvlar shu modullarga tegishli bo'lsa yoziladi.
# production_routes.py da `import production_service as service` — `service.` ham shu.
CHAQIRUV_MODULLARI = {
    "crud": "crud",
    "services": "services",
    "production_service": "production_service",
    "service": "production_service",
    "auth": "auth",
    "company_brand": "company_brand",
    "delivery_pdf": "delivery_pdf",
    "finance_pdf": "finance_pdf",
    "pdf_service": "pdf_service",
    "tenant_context": "tenant_context",
}

ILOVA_FAYLLARI = (
    "auth.py", "company_brand.py", "crud.py", "database.py", "delivery_pdf.py",
    "erp_backup_tekshiruv.py", "finance_pdf.py", "main.py", "models.py", "pdf_service.py",
    "production_models.py", "production_routes.py", "production_schemas.py",
    "production_service.py", "saas_migration.py", "schemas.py", "services.py",
    "tenant_context.py",
)

BLOKLAR = ("MUHIT", "ISHGA_TUSHISH", "SAHIFALAR", "API", "MODELLAR", "TESTLAR")


# ---------------------------------------------------------------- yordamchilar

def _oqi(nisbiy):
    with open(os.path.join(ROOT, nisbiy), encoding="utf-8") as f:
        return f.read()


def _birinchi_qator(matn, chegara=200):
    """Docstring / izohning birinchi xatboshisi — bir qatorga yig'ilgan, qisqartirilgan."""
    if not matn:
        return ""
    xatboshi = []
    for q in matn.strip().splitlines():
        q = q.strip()
        if not q:
            break
        if set(q) <= set("=-"):
            break
        xatboshi.append(q)
    s = " ".join(xatboshi)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > chegara:
        s = s[: chegara - 1].rstrip() + "…"
    return s


def _yol_norma(yol):
    """`/api/orders/{order_id}` → `/api/orders/{}` (taqqoslash uchun)."""
    return re.sub(r"\{[^}]*\}", "{}", yol)


# ---------------------------------------------------------------- marshrutlar

class Marshrut:
    __slots__ = ("usul", "yol", "handler", "fayl", "qorovul", "chaqiruvlar", "shablon")

    def __init__(self, usul, yol, handler, fayl, qorovul, chaqiruvlar, shablon):
        self.usul = usul
        self.yol = yol
        self.handler = handler
        self.fayl = fayl
        self.qorovul = qorovul
        self.chaqiruvlar = chaqiruvlar
        self.shablon = shablon


def _depends_nomlari(fn):
    """Funksiya argumentlaridagi `Depends(x)` — `get_db` dan tashqari."""
    natija = []
    standart = list(fn.args.defaults) + [d for d in fn.args.kw_defaults if d is not None]
    for d in standart:
        if isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "Depends" and d.args:
            nom = ast.unparse(d.args[0])
            if nom != "get_db":
                natija.append(nom)
    return natija


def _tana_chaqiruvlari(fn):
    topilgan = set()
    for tugun in ast.walk(fn):
        if isinstance(tugun, ast.Call) and isinstance(tugun.func, ast.Attribute):
            qiymat = tugun.func.value
            if isinstance(qiymat, ast.Name) and qiymat.id in CHAQIRUV_MODULLARI:
                topilgan.add(CHAQIRUV_MODULLARI[qiymat.id] + "." + tugun.func.attr)
    return topilgan


def _tana_shabloni(fn):
    shablonlar = set()
    for tugun in ast.walk(fn):
        if isinstance(tugun, ast.Call) and isinstance(tugun.func, ast.Attribute) \
                and tugun.func.attr == "TemplateResponse":
            for a in tugun.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value.endswith(".html"):
                    shablonlar.add(a.value)
    return sorted(shablonlar)


def _router_prefiksi(daraxt):
    for tugun in daraxt.body:
        if isinstance(tugun, ast.Assign) and isinstance(tugun.value, ast.Call) \
                and isinstance(tugun.value.func, ast.Name) and tugun.value.func.id == "APIRouter":
            for kw in tugun.value.keywords:
                if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                    return kw.value.value
    return ""


def _ast_marshrutlari(nisbiy, obyekt_nomi):
    daraxt = ast.parse(_oqi(nisbiy))
    prefiks = _router_prefiksi(daraxt) if obyekt_nomi == "router" else ""
    natija = []
    for fn in daraxt.body:
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dek in fn.decorator_list:
            if not (isinstance(dek, ast.Call) and isinstance(dek.func, ast.Attribute)):
                continue
            if not (isinstance(dek.func.value, ast.Name) and dek.func.value.id == obyekt_nomi):
                continue
            if dek.func.attr not in HTTP_USULLAR or not dek.args:
                continue
            birinchi = dek.args[0]
            if not (isinstance(birinchi, ast.Constant) and isinstance(birinchi.value, str)):
                continue
            qorovul = _depends_nomlari(fn)
            for kw in dek.keywords:
                if kw.arg == "dependencies" and isinstance(kw.value, (ast.List, ast.Tuple)):
                    for e in kw.value.elts:
                        if isinstance(e, ast.Call) and e.args:
                            qorovul.append(ast.unparse(e.args[0]))
            chaqiruvlar = _tana_chaqiruvlari(fn) - set(qorovul)
            natija.append(Marshrut(dek.func.attr.upper(), prefiks + birinchi.value, fn.name, nisbiy,
                                   sorted(set(qorovul)), sorted(chaqiruvlar), _tana_shabloni(fn)))
    return natija


_SAAS_DEK = re.compile(r'^\s*@router\.(get|post|put|delete|patch)\(\s*"([^"]+)"')
_SAAS_DEF = re.compile(r'^\s*(?:async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(')
_SAAS_DEP = re.compile(r'Depends\(\s*([A-Za-z_][A-Za-z0-9_.]*)\s*\)')


def _saas_marshrutlari():
    """saas_migration.py — faqat matn bilan (3.12 sintaksisi, 3.11 ast o'qimaydi)."""
    qatorlar = _oqi("saas_migration.py").splitlines()
    natija = []
    i = 0
    while i < len(qatorlar):
        m = _SAAS_DEK.match(qatorlar[i])
        if not m:
            i += 1
            continue
        usul, yol = m.group(1).upper(), m.group(2)
        j = i + 1
        while j < len(qatorlar) and not _SAAS_DEF.match(qatorlar[j]):
            j += 1
        if j >= len(qatorlar):
            break
        nom = _SAAS_DEF.match(qatorlar[j]).group(1)
        # imzo — `):` gacha
        imzo = []
        k = j
        while k < len(qatorlar):
            imzo.append(qatorlar[k])
            if qatorlar[k].rstrip().endswith(":"):
                break
            k += 1
        qorovul = sorted(set(d for d in _SAAS_DEP.findall(" ".join(imzo)) if d != "get_db"))
        natija.append(Marshrut(usul, yol, nom, "saas_migration.py", qorovul, [], []))
        i = k + 1
    return natija


def hamma_marshrutlar():
    m = _ast_marshrutlari("main.py", "app")
    m += _ast_marshrutlari("production_routes.py", "router")
    m += _saas_marshrutlari()
    m.sort(key=lambda r: (r.yol, HTTP_USULLAR.index(r.usul.lower()), r.handler))
    return m


# ---------------------------------------------------------------- shablonlardagi API havolalari

_JINJA = re.compile(r"\{\{.*?\}\}")
_API_LITERAL = re.compile(r"""(['"`])(/api/[^'"`\s?#]*)""")
# `'/api/x/' + id + '/y'` — o'zgaruvchidan keyingi davomi (qo'shtirnoq ichida `/` bilan boshlanadi)
_DAVOMI = re.compile(r"""\s*\+\s*[A-Za-z_$][A-Za-z0-9_$.\[\]()'"]*?\s*\+\s*(['"`])(/[^'"`\s?#]*)""")


def shablon_api_yollari(nisbiy):
    matn = _JINJA.sub("{J}", _oqi(nisbiy))
    topilgan = set()
    for m in _API_LITERAL.finditer(matn):
        yol = m.group(2)
        yopuvchi = matn.find(m.group(1), m.end())
        if yol.endswith("/") and yopuvchi != -1:
            joy = yopuvchi + 1
            keyin = matn[joy: joy + 3]
            if keyin.strip().startswith("+"):
                yol += "{}"
                # davomi: + '/pdf' yoki + id + '/restore' …
                while True:
                    d = _DAVOMI.match(matn, joy)
                    if not d:
                        break
                    yol += d.group(2)
                    yopuvchi2 = matn.find(d.group(1), d.end())
                    if yopuvchi2 == -1 or not d.group(2).endswith("/"):
                        break
                    joy = yopuvchi2 + 1
                    if not matn[joy: joy + 3].strip().startswith("+"):
                        break
                    yol += "{}"
        yol = re.sub(r"\$\{[^}]*\}", "{}", yol).replace("{J}", "{}")
        while "{}{}" in yol:
            yol = yol.replace("{}{}", "{}")
        yol = yol.rstrip("/") or yol
        topilgan.add(yol)
    return sorted(topilgan)


# ---------------------------------------------------------------- bloklar

def blok_muhit():
    naqsh = re.compile(r"""os\.(?:getenv|environ\.get)\(\s*['"]([A-Z][A-Z0-9_]*)['"]|os\.environ\[\s*['"]([A-Z][A-Z0-9_]*)['"]\s*\]""")
    joylar = {}
    for f in ILOVA_FAYLLARI:
        for m in naqsh.finditer(_oqi(f)):
            nom = m.group(1) or m.group(2)
            joylar.setdefault(nom, set()).add(f)
    q = ["Kod o'qiydigan muhit o'zgaruvchilari (Railway → Variables). Ro'yxat `os.getenv` / `os.environ` dan olingan.", ""]
    for nom in sorted(joylar):
        q.append(f"- `{nom}` — {', '.join('`' + f + '`' for f in sorted(joylar[nom]))}")
    return "\n".join(q)


def _chaqiruv_royxati(bayonot):
    """Modul darajasidagi bayonotdan (Expr / Try / If ichida) chaqiruvlar."""
    natija = []
    if isinstance(bayonot, ast.Expr) and isinstance(bayonot.value, ast.Call):
        natija.append(bayonot.value)
    elif isinstance(bayonot, (ast.Try, ast.If)):
        for b in bayonot.body:
            natija.extend(_chaqiruv_royxati(b))
    return natija


def blok_ishga_tushish():
    daraxt = ast.parse(_oqi("main.py"))
    funksiyalar = {n.name: n for n in daraxt.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    q = ["`main.py` import qilinganda (server ishga tushganda, `app = FastAPI(...)` dan OLDIN va keyin) modul darajasida",
         "bajariladigan chaqiruvlar — AYNAN shu tartibda. `_migrate_*` — idempotent sxema / ma'lumot migratsiyalari",
         "(Alembic YO'Q). Yangi migratsiya shu ro'yxat oxiriga qo'shiladi.", ""]
    n = 0
    for bayonot in daraxt.body:
        for c in _chaqiruv_royxati(bayonot):
            nom = ast.unparse(c.func)
            if nom.startswith(("print", "os.", "mimetypes.", "app.mount", "uvicorn.")):
                continue
            n += 1
            tavsif = ""
            if nom in funksiyalar:
                tavsif = _birinchi_qator(ast.get_docstring(funksiyalar[nom]) or "", 170)
            elif nom == "app.include_router" and c.args:
                nom = f"app.include_router({ast.unparse(c.args[0])})"
            q.append(f"{n}. `{nom}`" + (f" — {tavsif}" if tavsif else ""))
    return "\n".join(q)


def blok_sahifalar(marshrutlar):
    naqshlar = {}
    for r in marshrutlar:
        naqshlar.setdefault(_yol_norma(r.yol), []).append(r)
    q = ["Har sahifa: URL → handler → shablon → qorovul (ruxsat), so'ng shablon JavaScript'i chaqiradigan API yo'llari",
         "(matndan statik olingan; `{}` — o'zgaruvchan qism). ⚠ — hech bir marshrutga mos kelmagan yo'l (o'lik havola bo'lishi mumkin).",
         "`base.html` (hamma sahifada): " + ", ".join(f"`{y}`" for y in shablon_api_yollari("templates/base.html")), ""]
    sahifalar = [r for r in marshrutlar if r.shablon]
    for r in sahifalar:
        qorovul = ", ".join(r.qorovul) if r.qorovul else "— (tanada tekshiriladi yoki ochiq)"
        q.append(f"### `{r.usul} {r.yol}` → `{r.fayl}:{r.handler}` → {', '.join('`templates/' + s + '`' for s in r.shablon)}")
        q.append(f"- Qorovul: {qorovul}")
        if r.chaqiruvlar:
            q.append(f"- Server chaqiruvlari: {', '.join(r.chaqiruvlar)}")
        for s in r.shablon:
            if s == "base.html":
                continue
            yollar = shablon_api_yollari("templates/" + s)
            if yollar:
                belgili = [(f"`{y}`" if _yol_norma(y) in naqshlar else f"⚠`{y}`") for y in yollar]
                q.append(f"- `{s}` API: " + ", ".join(belgili))
        q.append("")
    shablonsiz = sorted(set(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "templates", "*.html")))
                        - set(s for r in sahifalar for s in r.shablon) - {"base.html"})
    q.append("Hech bir handler to'g'ridan-to'g'ri ko'rsatmaydigan shablonlar: "
             + (", ".join(f"`{s}`" for s in shablonsiz) if shablonsiz else "yo'q"))
    return "\n".join(q).rstrip()


def _guruh(yol):
    qismlar = [p for p in yol.split("/") if p]
    if not qismlar:
        return "/"
    if qismlar[0] == "api" and len(qismlar) > 1:
        return "/api/" + qismlar[1]
    return "/" + qismlar[0]


def blok_api(marshrutlar):
    q = ["Har qator: `USUL yo'l` → `fayl:handler` · 🔒 qorovul (`Depends`) · handler tanasidagi to'g'ridan-to'g'ri",
         "`crud.` / `services.` / `production_service.` / `auth.` … chaqiruvlari. 🔓 — `Depends` qorovuli yo'q (ochiq yoki",
         "ruxsat tanada tekshiriladi — o'zgartirishdan OLDIN handler'ni o'qing).", ""]
    guruhlar = {}
    for r in marshrutlar:
        guruhlar.setdefault(_guruh(r.yol), []).append(r)
    jami = 0
    for g in sorted(guruhlar):
        q.append(f"#### `{g}` ({len(guruhlar[g])})")
        for r in guruhlar[g]:
            jami += 1
            qorovul = ("🔒 " + ", ".join(r.qorovul)) if r.qorovul else "🔓"
            chaq = (" · " + ", ".join(r.chaqiruvlar)) if r.chaqiruvlar else ""
            q.append(f"- `{r.usul} {r.yol}` → `{r.fayl}:{r.handler}` · {qorovul}{chaq}")
        q.append("")
    q.append(f"Jami marshrutlar: {jami} (main.py: {sum(1 for r in marshrutlar if r.fayl == 'main.py')}, "
             f"production_routes.py: {sum(1 for r in marshrutlar if r.fayl == 'production_routes.py')}, "
             f"saas_migration.py: {sum(1 for r in marshrutlar if r.fayl == 'saas_migration.py')}).")
    return "\n".join(q)


def _tenant_qoidalari():
    daraxt = ast.parse(_oqi("models.py"))
    for tugun in daraxt.body:
        if isinstance(tugun, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "_TENANT_RULES" for t in tugun.targets):
            try:
                return ast.literal_eval(tugun.value)
            except ValueError:
                return {}
    return {}


def blok_modellar():
    qoidalar = _tenant_qoidalari()
    qatorlar = []
    for fayl in ("models.py", "production_models.py"):
        daraxt = ast.parse(_oqi(fayl))
        for kl in daraxt.body:
            if not isinstance(kl, ast.ClassDef):
                continue
            jadval = None
            ustunlar = []
            for b in kl.body:
                if isinstance(b, ast.Assign):
                    for t in b.targets:
                        if isinstance(t, ast.Name) and t.id == "__tablename__" and isinstance(b.value, ast.Constant):
                            jadval = b.value.value
                        elif isinstance(t, ast.Name) and isinstance(b.value, ast.Call) \
                                and ast.unparse(b.value.func) in ("Column", "sa.Column"):
                            ustunlar.append(t.id)
            if not jadval:
                continue
            if "company_id" in ustunlar:
                tenant = "o'z `company_id`"
                if kl.name in qoidalar:
                    tenant += " + ota tekshiruvi (" + ", ".join(f"{u}→{m}" for u, m in qoidalar[kl.name]) + ")"
            elif kl.name in qoidalar:
                tenant = "ota orqali (" + ", ".join(f"{u}→{m}" for u, m in qoidalar[kl.name]) + ")"
            else:
                tenant = "korxonasiz"
            qatorlar.append((jadval, kl.name, fayl, len(ustunlar), tenant))
    qatorlar.sort()
    q = ["Har jadval: `jadval` — `Klass` (`fayl`, ustunlar soni) — korxona (tenant) bog'lanishi. `_TENANT_RULES` (models.py) —",
         "ORM qorovuli yangi / o'zgargan qatorda ota yozuv korxonasini tekshiradi.", ""]
    for jadval, klass, fayl, n, tenant in qatorlar:
        q.append(f"- `{jadval}` — `{klass}` (`{fayl}`, {n}) — {tenant}")
    q.append("")
    q.append(f"Jami jadvallar: {len(qatorlar)}.")
    return "\n".join(q)


def _js_izoh(matn):
    m = re.search(r"/\*\*?(.*?)\*/", matn, re.S)
    if not m:
        return ""
    qatorlar = [re.sub(r"^\s*\*\s?", "", q) for q in m.group(1).splitlines()]
    return "\n".join(qatorlar)


def blok_testlar():
    q = ["`tools/test_*.py` (SQLite; ko'plari `PG_URL` bilan PostgreSQL da ham) va `tools/test_*.js` (Node + jsdom — shablonning",
         "HAQIQIY JavaScript'i). Har biri oxirida `NATIJA: o'tdi = N yiqildi = M jami = K` chiqaradi; `yiqildi = 0` va chiqish kodi 0 — talab.",
         "Tavsif — faylning birinchi izoh xatboshisi.", ""]
    for f in sorted(glob.glob(os.path.join(ROOT, "tools", "test_*.py"))):
        nom = os.path.basename(f)
        with open(f, encoding="utf-8") as fh:
            matn = fh.read()
        try:
            doc = ast.get_docstring(ast.parse(matn)) or ""
        except SyntaxError:
            doc = ""
        tavsif = _birinchi_qator(doc)
        tavsif = re.sub(r"^" + re.escape(nom) + r"\s*[—-]\s*", "", tavsif)
        pg = " · PG" if "PG_URL" in matn else ""
        q.append(f"- `{nom}`{pg} — {tavsif}")
    for f in sorted(glob.glob(os.path.join(ROOT, "tools", "test_*.js"))):
        nom = os.path.basename(f)
        with open(f, encoding="utf-8") as fh:
            matn = fh.read()
        tavsif = _birinchi_qator(_js_izoh(matn))
        tavsif = re.sub(r"^" + re.escape(nom) + r"\s*[—-]\s*", "", tavsif)
        q.append(f"- `{nom}` · JS — {tavsif}")
    py = len(glob.glob(os.path.join(ROOT, "tools", "test_*.py")))
    js = len(glob.glob(os.path.join(ROOT, "tools", "test_*.js")))
    q.append("")
    q.append(f"Jami test fayllari: {py + js} (Python {py}, JS {js}).")
    return "\n".join(q)


def hamma_bloklar():
    marshrutlar = hamma_marshrutlar()
    return {
        "MUHIT": blok_muhit(),
        "ISHGA_TUSHISH": blok_ishga_tushish(),
        "SAHIFALAR": blok_sahifalar(marshrutlar),
        "API": blok_api(marshrutlar),
        "MODELLAR": blok_modellar(),
        "TESTLAR": blok_testlar(),
    }


# ---------------------------------------------------------------- pasport fayli bilan ishlash

def _belgilar(nom):
    return (f"<!-- AVTO:{nom} BOSHI — qo'lda tahrirlamang: python3 tools/pasport_xarita.py --yoz -->",
            f"<!-- AVTO:{nom} OXIRI -->")


def pasportdagi_bloklar(matn):
    """{nom: ichidagi matn} — belgilar orasidagi (bosh / oxirgi bo'sh qatorlarsiz)."""
    natija = {}
    for nom in BLOKLAR:
        bosh, oxir = _belgilar(nom)
        i = matn.find(bosh)
        j = matn.find(oxir)
        if i == -1 or j == -1 or j < i:
            continue
        natija[nom] = matn[i + len(bosh): j].strip("\n")
    return natija


def pasportni_yangila(matn, bloklar):
    for nom in BLOKLAR:
        bosh, oxir = _belgilar(nom)
        i = matn.find(bosh)
        j = matn.find(oxir)
        if i == -1 or j == -1 or j < i:
            raise SystemExit(f"LOYIHA_PASPORTI.md da {nom} bloki belgilari topilmadi: {bosh!r} … {oxir!r}")
        matn = matn[: i + len(bosh)] + "\n" + bloklar[nom] + "\n" + matn[j:]
    return matn


def farqlar(matn, bloklar):
    bor = pasportdagi_bloklar(matn)
    natija = []
    for nom in BLOKLAR:
        if nom not in bor:
            natija.append((nom, "blok belgilari yo'q"))
        elif bor[nom] != bloklar[nom]:
            eski = bor[nom].splitlines()
            yangi = bloklar[nom].splitlines()
            birinchi = next((k for k in range(max(len(eski), len(yangi)))
                             if (eski[k] if k < len(eski) else None) != (yangi[k] if k < len(yangi) else None)), 0)
            e = eski[birinchi] if birinchi < len(eski) else "(yo'q)"
            y = yangi[birinchi] if birinchi < len(yangi) else "(yo'q)"
            natija.append((nom, f"{birinchi + 1}-qatorda farq:\n      pasportda: {e[:200]}\n      kodda:     {y[:200]}"))
    return natija


def main(argv):
    bloklar = hamma_bloklar()
    if "--yoz" in argv:
        with open(PASPORT, encoding="utf-8") as f:
            matn = f.read()
        yangi = pasportni_yangila(matn, bloklar)
        with open(PASPORT, "w", encoding="utf-8") as f:
            f.write(yangi)
        print("LOYIHA_PASPORTI.md yangilandi (" + ", ".join(BLOKLAR) + ").")
        return 0
    if "--tekshir" in argv:
        with open(PASPORT, encoding="utf-8") as f:
            matn = f.read()
        f_ = farqlar(matn, bloklar)
        if not f_:
            print("PASPORT AVTO bloklari kod bilan AYNAN.")
            return 0
        for nom, izoh in f_:
            print(f"FARQ [{nom}]: {izoh}")
        print("Tuzatish: python3 tools/pasport_xarita.py --yoz  (so'ng qo'lda yozilgan bo'limlarni ham ko'rib chiqing)")
        return 1
    for nom in BLOKLAR:
        print(f"===== {nom}")
        print(bloklar[nom])
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
