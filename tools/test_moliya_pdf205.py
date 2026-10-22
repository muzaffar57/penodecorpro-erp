#!/usr/bin/env python3
"""
test_moliya_pdf205.py — kech154 (zip 205 «Oylik moliyaviy hisobot — tartibli PDF»; EGASI so'rovi 22.10 09:42 «oylik hisob PDF ni tartiblash
kerak … juda ko'p malumotlar», 09:5x «Ha, qo'shilsin» — oldingi oy bilan solishtirish; TANLOVI «B · Ixcham 2 sahifa»). RAQAMLAR VA FORMULALAR
O'ZGARMAYDI — faqat PDF ko'rinishi, qatorlarning guruhlanishi va nomlari.

NIMA UCHUN KERAK (O'LCHANGAN — `work/k205/namuna/yasash.py`: egasining Sentabr 2026 PDF idagi qatorlar va summalar bilan hisobot; zip 204
kodi egasining PDF ini AYNAN qaytardi):
  * doimiy majburiyat turkumi XOM KOD bilan chiqardi («bosh_offic_arenda_8477», «eski_shaxar_arenda_2165») — Moliya sahifasidagi «Doimiy va
    qo'shimcha xarajatlar» da ham;
  * «Hisob farqi (qatorlarda ko'rinmagan) −1 so'm» — brak xomashyo bo'yicha HAR BIRI alohida yaxlitlanib keladi
    (`crud.get_brak_material_summary`: `round(m["value"])`), 7 qatorning yaxlitlash qoldig'i 1 so'mdan oshardi;
  * rentabellik «-21.6%» (hujjatdagi boshqa sonlar «−» va vergul bilan); «Jilvir» va «JILVIR» — ikki qator;
  * 40+ qator bitta ro'yxatda, guruh / ulush / oldingi oy yo'q.
BO'LIMLAR:
  S — manba: `finance_pdf` guruhlari va yordamchilari, `/api/finance/report-pdf` oldingi oyni o'sha tozalash bilan beradi (yanvar — o'tgan
      yil dekabri), `/api/finance/report` — `qoshimcha_nomlari`, `crud.majburiyat_nomlari` korxona bilan, Moliya sahifasi nomni escape bilan.
  U — `finance_pdf` to'g'ridan-to'g'ri, egasining Sentabr raqamlari (Avgust — sinov uchun): guruh qatorlari = guruh, guruhlar = JAMI
      XARAJAT, «Hisob farqi» yo'q (brak xomashyolari alohida yaxlitlangan holda ham), majburiyat nomi, «−21,6%», bitta «Jilvir», 2 sahifa
      («1 / 2», «2 / 2»), faqat Liberation shrifti, oldingi oy kartalari / guruh o'zgarishi / qisqa xulosa raqamlari, `_moslash` chegaralari,
      `oldingi_oy_xulosasi`, «Tannarx va foyda» ruxsatisiz ko'rinish.
  D — marshrut (SQLite / PG; `TENANT_FILTER=1` ham): «Biz qarzdormiz» turkumi (nomida «<», «&»; 2-korxonada o'sha kod — boshqa nom), shu va
      o'tgan oy xarajatlari, «Tayyor» buyurtma: hisobot JSON i o'zgarmagan (+ `qoshimcha_nomlari`), PDF — nom AYNAN, xom kod yo'q, bitta
      «Jilvir», qatorlar yig'indisi = JAMI = hisobot, «Hisob farqi» yo'q, rentabellik «−N,N%», o'tgan oy kartalarda va guruhlar jadvalida
      (hisobot bilan), tannarxsiz foydalanuvchida o'tgan oy SOF FOYDA / JAMI XARAJAT ham «—», o'tgan oyi bo'sh oy — solishtirishsiz, yanvar
      — 200; Moliya sahifasi `buildExpDetail` (node) — nom escape bilan.
REJIMLAR: SQLite (odatiy); `PG_URL` — yangi PG bazasi; `TENANT_FILTER=1`. Asl kodga (zip 204) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_moliya_pdf205.py
"""
import os
import re
import io
import sys
import json
import zlib
import base64
import tempfile
import contextlib
import subprocess
from types import SimpleNamespace as NS

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "moliya_pdf205_test"
TF = os.environ.get("TENANT_FILTER") == "1"
_T = tempfile.mkdtemp(prefix="k205_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k205.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

YORLIQ = ("[PG] " if PG_URL else "") + ("[TF1] " if TF else "")
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {'' if callable(detail) else detail}"
    if not cond and callable(detail):
        try:
            detail = detail()
        except Exception as e:             # noqa: BLE001
            detail = f"{type(e).__name__}: {e}"
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:600]}")


def section(t):
    print(f"\n--- {t} ---")


def xav(f, *a, standart=None, **k):
    try:
        return f(*a, **k)
    except Exception as e:                 # noqa: BLE001
        print(f"   ({getattr(f, '__name__', f)}: {type(e).__name__}: {e})")
        return standart


def fayl(n):
    return open(os.path.join(ROOT, n), encoding="utf-8").read()


# ── PDF o'quvchi (kutubxonasiz; `tools/test_moliya_tafsilot.py` bilan bir xil usul) ──────────────────────────────────────────────────
def _oqim(tana):
    lugat, _, qolgan = tana.partition(b"stream")
    data = qolgan[2:] if qolgan.startswith(b"\r\n") else qolgan[1:]
    m = re.search(rb"/Length\s+(\d+)(?!\s+\d+\s+R)", lugat)
    data = data[:int(m.group(1))] if m else data[:data.rfind(b"endstream")].rstrip(b"\r\n")
    if b"ASCII85Decode" in lugat:
        data = re.sub(rb"\s", b"", data)
        if data.startswith(b"<~"):
            data = data[2:]
        if data.endswith(b"~>"):
            data = data[:-2]
        data = base64.a85decode(data)
    if b"FlateDecode" in lugat:
        data = zlib.decompress(data)
    return lugat, data


def _satr(b):
    chiq, i = bytearray(), 0
    while i < len(b):
        c = b[i]
        if c == 0x5C and i + 1 < len(b):
            n = b[i + 1]
            if 0x30 <= n <= 0x37:
                j = i + 1
                while j < len(b) and j < i + 4 and 0x30 <= b[j] <= 0x37:
                    j += 1
                chiq.append(int(b[i + 1:j], 8) & 0xFF)
                i = j
                continue
            chiq.append({ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12}.get(n, n))
            i += 2
            continue
        chiq.append(c)
        i += 1
    return bytes(chiq)


_PDF_TOKEN = re.compile(rb"%[^\r\n]*|\((?:\\.|[^\\)])*\)|<[0-9A-Fa-f\s]*>|\[|\]|/[^\s/\[\]()<>{}%]*|[^\s/\[\]()<>{}%]+", re.S)


def _bt_bloklar(data):
    blok = None
    for m in _PDF_TOKEN.finditer(data):
        tok = m.group(0)
        if tok.startswith(b"%"):
            continue
        if tok == b"BT":
            blok = []
        elif tok == b"ET":
            if blok is not None:
                yield blok
            blok = None
        elif blok is not None:
            blok.append(tok)


def pdf_matn(bayt):
    """PDF matni: har `BT … ET` bloki alohida qator (jadval katagi — bitta qator), sahifalar tartibida."""
    obyektlar = {int(n): tana for n, tana in re.findall(rb"(\d+) 0 obj\s*(.*?)\s*endobj", bayt, re.S)}
    shriftlar = {}
    for tana in obyektlar.values():
        nom = re.search(rb"/Name\s*/([^\s/>\[]+)", tana)
        if b"/Type /Font" not in tana or not nom:
            continue
        cmap = None
        tu = re.search(rb"/ToUnicode\s+(\d+)\s+0\s+R", tana)
        if tu and int(tu.group(1)) in obyektlar:
            _, cm = _oqim(obyektlar[int(tu.group(1))])
            cmap = {}
            for blok in re.findall(rb"beginbfchar(.*?)endbfchar", cm, re.S):
                for k, v in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blok):
                    cmap[int(k, 16)] = bytes.fromhex(v.decode()).decode("utf-16-be")
        shriftlar[nom.group(1).decode()] = cmap
    # sahifalar tartibi: /Kids ro'yxati → har sahifaning /Contents
    tartib = []
    for tana in obyektlar.values():
        if re.search(rb"/Type\s*/Pages\b", tana):
            kids = re.search(rb"/Kids\s*\[([^\]]*)\]", tana)
            if kids:
                tartib = [int(x) for x in re.findall(rb"(\d+)\s+0\s+R", kids.group(1))]
    oqimlar = []
    for p in tartib:
        c = re.search(rb"/Contents\s+(\d+)\s+0\s+R", obyektlar.get(p, b""))
        if c:
            oqimlar.append(obyektlar.get(int(c.group(1)), b""))
    satrlar = []
    for tana in oqimlar:
        try:
            _, data = _oqim(tana)
        except Exception:                  # noqa: BLE001
            continue
        for blok in _bt_bloklar(data):
            cmap, qism = None, []
            for j, tok in enumerate(blok):
                if tok == b"Tf" and j >= 2 and blok[j - 2].startswith(b"/"):
                    cmap = shriftlar.get(blok[j - 2][1:].decode())
                elif tok == b"Tj" and j >= 1 and blok[j - 1].startswith(b"("):
                    kodlar = _satr(blok[j - 1][1:-1])
                    qism.append("".join(cmap.get(k, "■") for k in kodlar) if cmap is not None else kodlar.decode("cp1252", "replace"))
            if qism:
                satrlar.append(" ".join(qism).strip())
    return satrlar


def sahifalar_soni(bayt):
    return len(re.findall(rb"/Type\s*/Page(?![s\w])", bayt))


def shriftlar(bayt):
    return sorted({x.decode() for x in re.findall(rb"/BaseFont\s*/([^\s/>]+)", bayt)})


def ixcham(s):
    return re.sub(r"\s+", "", s or "")


def keyingi(satrlar, yorliq, n=1):
    """`yorliq` (birinchi uchrashi) dan keyingi n-qator."""
    try:
        i = satrlar.index(yorliq)
    except ValueError:
        return None
    return satrlar[i + n] if i + n < len(satrlar) else None


def tafsilot(satrlar):
    """«Xarajatlar tafsiloti»: ({guruh: (summa matni, [(nom, summa matni)])}, guruhlar tartibi, JAMI matni)."""
    import finance_pdf as _fp
    _gn = {g for _k, g in getattr(_fp, "XARAJAT_GURUHLARI", ())} | {getattr(_fp, "_FARQ_GURUHI", "Hisob farqi")}
    try:
        i = satrlar.index("Xarajatlar tafsiloti")
        j = next(k for k in range(i, len(satrlar)) if satrlar[k] == "JAMI XARAJAT")
    except (ValueError, StopIteration):
        return {}, [], None
    q = satrlar[i + 1:j]
    g, tartib, joriy, k = {}, [], None, 0
    while k + 1 < len(q):
        if q[k] in ("Xarajat nomi", "Summa"):
            k += 1
            continue
        nom = re.sub(r"\s+·\s+[−-]?[\d,]+%$", "", q[k])
        if nom in _gn:
            joriy = nom
            tartib.append(nom)
            g[nom] = (q[k + 1], [])
        elif joriy is not None:
            g[joriy][1].append((q[k], q[k + 1]))
        k += 2
    return g, tartib, (satrlar[j + 1] if j + 1 < len(satrlar) else None)


def son(matn):
    """«−36 000 so'm» / «+100 000» / «864 000 so'm» → ishorali butun son (None — son emas, masalan «—»)."""
    t = (matn or "").replace("−", "-").replace("\xa0", " ")
    m = re.fullmatch(r"\s*([-+])?\s*(\d[\d ]*)(?:\s*so'm)?\s*", t)
    if not m:
        return None
    v = int(m.group(2).replace(" ", ""))
    return -v if m.group(1) == "-" else v


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
FP = fayl("finance_pdf.py")
MN = fayl("main.py")
CR = fayl("crud.py")
FH = fayl("templates/finance.html")
_gen = FP[FP.find("def generate_finance_report_pdf("):]
check("S1 `finance_pdf`: 8 xarajat guruhi (tannarx, oylik, doimiy, brak, transport, boshqa, kutilmagan, ehson), guruh sarlavhasi nomi qator "
      "nomidan farqli («Ehson» / «Ehson (xayriya)», «Hisob farqi»), yordamchilar bor",
      all(f"def {n}(" in FP for n in ("xarajat_guruhlari_jami", "_moslash", "xarajat_tafsiloti", "oldingi_oy_xulosasi", "hisobot_raqamlari",
                                      "_xulosa_gaplari", "_raqamli_canvas", "_ulush_chizigi"))
      and '("ehson", "Ehson"),' in FP and '_FARQ_GURUHI = "Hisob farqi"' in FP and 'qosh("ehson", "Ehson (xayriya)", q["ehson"])' in FP,
      len(FP))
check("S2 ReportLab grafikasi (`Drawing`) YO'Q — u «Times-Roman» Type1 shriftini qo'shardi; sahifa raqami canvasda («N / jami»)",
      "Drawing(" not in FP and "reportlab.graphics" not in FP and 'f"{self._pageNumber} / {jami}"' in FP
      and "canvasmaker=_raqamli_canvas(pastki)" in _gen, "")
check("S3 brak xomashyo qatorlari AYNAN brak summasiga keltiriladi (`_moslash(... q[\"brak\"] ...)`); izoh kaliti — `casefold` (bir xil izoh "
      "har xil harf bilan — bitta qator)",
      'q["brak"], "Brak (yaroqsiz xomashyo)")' in FP and "kalit = (cat, izoh.casefold())" in FP, "")
_rp = MN[MN.find("def api_finance_report_pdf("):]
_rp = _rp[:_rp.find("\n@app.")]
check("S4 `/api/finance/report-pdf`: o'tgan oy — `get_monthly_report` (yanvar → o'tgan yil dekabri), tannarxsizda `tannarx_tozala`, "
      "`oldingi_oy_xulosasi` va majburiyat nomlari PDF ga",
      "_o_yil, _o_oy = (year - 1, 12) if month == 1 else (year, month - 1)" in _rp
      and "oldingi_report = services.get_monthly_report(db, _o_yil, _o_oy, company_id=auth.company_id_of(current_user))" in _rp
      and '_rx118.tannarx_tozala(oldingi_report, "/api/finance/report")' in _rp
      and "oldingi = finance_pdf.oldingi_oy_xulosasi(oldingi_report, majburiyat)" in _rp
      and "oldingi=oldingi, majburiyat_nomlari=majburiyat" in _rp
      and _rp.find("if tannarx_yoq:\n        _rx118.tannarx_tozala(oldingi_report") > _rp.find("tannarx_yoq = not current_user.ruxsat"), "")
_rr = MN[MN.find("def api_finance_report("):]
_rr = _rr[:_rr.find("\n@app.")]
check("S5 `/api/finance/report`: `qoshimcha_nomlari` — faqat shu oydagi qo'shimcha turkumlar, korxona nomlaridan; raqamlar o'sha",
      "_nomlar = crud.majburiyat_nomlari(db, auth.company_id_of(current_user))" in _rr
      and 'hisobot["qoshimcha_nomlari"] = {k: _nomlar.get(k) or crud.majburiyat_kodidan_nom(k) for k in (hisobot.get("qoshimcha_xarajatlar") or {})'
      in _rr, "")
_mj = CR[CR.find("def majburiyat_nomlari("):]
_mj = _mj[:_mj.find("\ndef ", 10)]
check("S6 `crud.majburiyat_nomlari` — korxona bilan cheklangan (`company_id`)",
      "_q = _q.filter(_RO205.company_id == company_id)" in _mj and "return {c: n for c, n in _q.all() if c and n}" in _mj, _mj[:200])
check("S8 `crud.majburiyat_kodidan_nom`: «Biz qarzdormiz» kodi (nom asosi + «_» + 4 raqam) → nom («bosh_offic_arenda_8477» → «Bosh offic "
      "arenda»); oddiy turkum («transport_kirim», «internet», «arenda») — None",
      lambda: ([__import__("crud").majburiyat_kodidan_nom(k) for k in ("bosh_offic_arenda_8477", "transport_kirim", "internet", "arenda",
                                                                     "арэнда_1234", "x_12345")]
               == ["Bosh offic arenda", None, None, None, "Арэнда", None]),
      lambda: ([getattr(__import__("crud"), "majburiyat_kodidan_nom", lambda k: "YO'Q")(k) for k in ("bosh_offic_arenda_8477", "internet")]))
check("S7 Moliya sahifasi «Doimiy va qo'shimcha xarajatlar»: majburiyat nomi `escapeHtml` bilan (`d.qoshimcha_nomlari`)",
      "escapeHtml((d.qoshimcha_nomlari || {})[k] || QX_NOMI[k] || k)" in FH and "escapeHtml(QX_NOMI[k] || k)" not in FH, "")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# U — finance_pdf to'g'ridan-to'g'ri: egasining Sentabr 2026 raqamlari (PDF idan; Avgust — SINOV uchun)
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_bosh = io.StringIO()
with contextlib.redirect_stdout(_bosh):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
    import services                                # noqa: E402
import finance_pdf as FPM                          # noqa: E402


def fp(nom):
    """`finance_pdf` dagi yangi (zip 205) funksiya — asl kodda yo'q bo'lsa None (`xav` yiqitadi, test qulamaydi)."""
    return getattr(FPM, nom, None)
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, Rol, Project, Inventory, Master, RecurringObligation   # noqa: E402
from production_models import Company              # noqa: E402
import ruxsatlar as RX                             # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from fastapi.encoders import jsonable_encoder      # noqa: E402

for _n in ("_send_telegram", "_send_telegram_to", "_send_telegram_document", "_send_telegram_to_qoplamachi"):
    if hasattr(main, _n):
        setattr(main, _n, lambda *a, **k: False)


def oy_hisoboti(year, month, daromad, ishlab, tushlik, kpi, hodimlar, brak_aniq, yetkazish, qoshimcha, izohlar):
    """`services.get_monthly_report` shaklidagi hisobot (egasining PDF idagi qatorlar); brak — xomashyo bo'yicha AYNAN (kasr) qiymat,
    `crud.get_brak_material_summary` kabi har biri ALOHIDA `round()`."""
    brak_jami = sum(v for _n, v in brak_aniq)
    hod_jami = sum(a for _n, _p, _d, a in hodimlar)
    kpi_jami = sum(round(p * pr / 100) for _n, p, pr in kpi)
    jami = ishlab + tushlik + kpi_jami + hod_jami + brak_jami + yetkazish + sum(qoshimcha.values())
    sof = daromad - jami
    rep = {
        "year": year, "month": month, "daromad": round(daromad), "daromad_buyurtmalardan": round(daromad),
        "ishlab_chiqarish_xarajat": ishlab, "fp_sales_tannarx": 0.0, "fp_loss_xarajat": 0, "brak_xarajat": round(brak_jami),
        "xarajatlar": {"arenda": 0.0, "elektr": 0.0, "tushlik": float(tushlik), "soliqlar": 0.0},
        "qoshimcha_xarajatlar": dict(qoshimcha), "usta_kpi_xarajat": kpi_jami,
        "usta_kpi_breakdown": [{"master_name": n, "kpi_percent": p, "monthly_profit": pr, "kpi_amount": round(p * pr / 100)}
                               for n, p, pr in kpi],
        "hodimlar_moslashuvchan_xarajat": hod_jami,
        "hodimlar_moslashuvchan_breakdown": [{"name": n, "position": p, "detail": dt, "amount": a} for n, p, dt, a in hodimlar],
        "ehson_xarajat": 0.0, "transport_xarajat_kirish": 0.0, "transport_xarajat_yetkazish": float(yetkazish),
        "sof_foyda": sof, "foyda_foiz": round(sof / daromad * 100, 1),
        "sof_foyda_tarkibi": {"daromad_buyurtmalar": daromad, "daromad_tm": 0.0, "tannarx_buyurtmalar": ishlab, "tannarx_tm": 0.0,
                              "doimiy": float(tushlik), "qoshimcha": float(sum(qoshimcha.values())), "transport": float(yetkazish),
                              "brak": brak_jami, "tm_yoqotish": 0.0, "usta_kpi": kpi_jami, "ehson": 0.0, "hodimlar": hod_jami},
    }
    brak = [{"item_name": n, "value": round(v)} for n, v in sorted(brak_aniq, key=lambda z: -z[1])]
    tx = [NS(category=c, amount=a, notes=nt, source=None) for c, nt, a in izohlar]
    return rep, tx, brak


SEN_REP, SEN_TX, SEN_BRAK = oy_hisoboti(
    2026, 9, 47460980.0, 21960463.0, 2551000, [("Axroraka", 3.0, 3146149)],
    [("Ulug'bek", "Kesuvchi", "Doimiy oylik", 11000000), ("Mirjalol", "Kesuvchi", "Doimiy oylik", 5000000),
     ("Jurabek", "Qoplamachi", "Oylik 1 500 000 + (773 metr/dona × 1 000 = 773 000)", 2273000)],
    [("Penoplast 14P", 983270.7), ("Akril Toshkent", 24737.8), ("Kroshka extra", 5131.9), ("Zagustitel", 1923.9),
     ("Kroshka mel", 1634.9), ("Penogasitel", 1048.9), ("Oddiy mel", 377.9)],
    750000, {"bosh_offic_arenda_8477": 2000000.0, "eski_shaxar_arenda_2165": 700000.0, "boshqa": 9667500.0, "kutilmagan": 704000.0},
    [("boshqa", "Jurabekni avgust oyidan qolgan to'lovimiz", 5950000), ("boshqa", "Kleydan karzimiz boridi berdik", 977500),
     ("boshqa", "BARNOGA ARENDA", 700000), ("boshqa", "FARUGA UYMAGA", 600000), ("boshqa", "MUXAMMADRASUL OLDI", 550000),
     ("boshqa", "LABO YOLKIRA", 200000), ("boshqa", "AXLATGA", 200000), ("boshqa", "MUXAMMADRASUL YOLKIRA XISOBIDAN OLDI", 160000),
     ("boshqa", "MUXAMMADRASUL SORADI", 160000), ("boshqa", "JORAGA UJNGA", 50000), ("boshqa", "Xolaga", 50000),
     ("boshqa", "LABO XIZMATI", 40000), ("boshqa", "KOK ChOYGA", 30000),
     ("kutilmagan", "Titan kley", 260000), ("kutilmagan", "ShABLONGA LIST", 240000), ("kutilmagan", "Zagustitl", 114000),
     ("kutilmagan", "Loyga salafan", 60000), ("kutilmagan", "Jilvir", 20000), ("kutilmagan", "JILVIR", 10000)])
AVG_REP, _avg_tx, _avg_brak = oy_hisoboti(
    2026, 8, 53200000.0, 24100000.0, 2400000, [("Axroraka", 3.0, 2500000)],
    [("Ulug'bek", "Kesuvchi", "Doimiy oylik", 11000000), ("Mirjalol", "Kesuvchi", "Doimiy oylik", 5000000),
     ("Jurabek", "Qoplamachi", "Oylik 1 500 000 + (650 metr/dona × 1 000 = 650 000)", 2150000)],
    [("Penoplast 14P", 612400.4), ("Akril Toshkent", 27599.6)],
    900000, {"bosh_offic_arenda_8477": 2000000.0, "eski_shaxar_arenda_2165": 700000.0, "boshqa": 1300000.0, "kutilmagan": 435000.0}, [])
MAJ = {"bosh_offic_arenda_8477": "Bosh ofis arendasi", "eski_shaxar_arenda_2165": "Eski shahar arendasi"}
DEBT = {"customer_debt": 57641292, "customer_debt_count": 10, "supplier_debt": 0, "supplier_debt_count": 0, "employee_debt": 0,
        "recurring_debt": 0, "recurring_debt_count": 0, "net_position": 57641292}

section("U — egasining Sentabr 2026 hisoboti (finance_pdf to'g'ridan-to'g'ri)")
OLD = xav(fp("oldingi_oy_xulosasi"), AVG_REP, MAJ)
D = xav(fp("hisobot_raqamlari"), SEN_REP, SEN_TX, SEN_BRAK, MAJ) or {"guruhlar": []}
GR = {g["kalit"]: g for g in D["guruhlar"]}
check("U1 JAMI XARAJAT 57 718 473 = daromad − sof foyda (butun so'mda), SOF FOYDA −10 257 493, DAROMAD 47 460 980 (egasining PDF i bilan AYNAN)",
      lambda: (D.get("jami") == 57718473 and D.get("sof") == -10257493 and D.get("daromad") == 47460980), lambda: ({k: D.get(k) for k in ("jami", "sof", "daromad")}))
check("U2 har guruh qatorlari yig'indisi = guruh summasi; guruhlar yig'indisi = JAMI XARAJAT; «Hisob farqi» guruhi YO'Q",
      lambda: (D["guruhlar"] and all(sum(v for _n, v in g["qatorlar"]) == g["summa"] for g in D["guruhlar"])
      and sum(g["summa"] for g in D["guruhlar"]) == D.get("jami") and "farq" not in GR),
      lambda: ([(g["kalit"], g["summa"], sum(v for _n, v in g["qatorlar"])) for g in D["guruhlar"]]))
check("U3 brak: xomashyo qatorlari alohida yaxlitlangan (yig'indisi 1 018 127 — eski «Hisob farqi −1» sababi), guruh — brakning AYNAN summasi "
      "1 018 126; eng katta qator (Penoplast 14P) 983 270",
      lambda: (sum(m["value"] for m in SEN_BRAK) == 1018127 and GR.get("brak", {}).get("summa") == 1018126
      and dict(GR.get("brak", {}).get("qatorlar", [])).get("Brak — Penoplast 14P") == 983270), lambda: (GR.get("brak")))
check("U4 guruhlar (egasining qatorlari bo'yicha): tannarx 21 960 463, oyliklar 18 367 384, doimiy 5 251 000 (tushlik + 2 arenda), transport "
      "750 000, boshqa 9 667 500, kutilmagan 704 000; ulush (%) jami xarajatdan",
      lambda: ([(k, GR.get(k, {}).get("summa")) for k in ("tannarx", "oylik", "doimiy", "transport", "boshqa", "kutilmagan")]
      == [("tannarx", 21960463), ("oylik", 18367384), ("doimiy", 5251000), ("transport", 750000), ("boshqa", 9667500),
          ("kutilmagan", 704000)] and abs(GR["tannarx"]["ulush"] - 21960463 / 57718473 * 100) < 1e-9), lambda: ({k: g.get("summa") for k, g in GR.items()}))
check("U5 doimiy majburiyat — «Biz qarzdormiz» dagi NOMI bilan (xom kod emas); «Boshqa» izohlari o'z nomi bilan; «Jilvir» + «JILVIR» — bitta "
      "qator «Jilvir» 30 000",
      lambda: (dict(GR["doimiy"]["qatorlar"]) == {"Tushlik": 2551000, "Bosh ofis arendasi": 2000000, "Eski shahar arendasi": 700000}
      and dict(GR["kutilmagan"]["qatorlar"]).get("Jilvir") == 30000 and "JILVIR" not in dict(GR["kutilmagan"]["qatorlar"])
      and dict(GR["boshqa"]["qatorlar"]).get("Jurabekni avgust oyidan qolgan to'lovimiz") == 5950000),
      lambda: ([GR["doimiy"]["qatorlar"], GR["kutilmagan"]["qatorlar"]]))
PDF_U = xav(FPM.generate_finance_report_pdf, SEN_REP, SEN_TX, SEN_BRAK, 2026, 9, DEBT, oldingi=OLD, majburiyat_nomlari=MAJ, standart=b"")
SU = xav(pdf_matn, PDF_U, standart=[]) or []
GU, TU, JU = tafsilot(SU)
_kod_bor = [q for q in SU if "bosh_offic" in q or "eski_shaxar" in q or re.search(r"[a-z]+_[a-z]+_\d{3,}", q)]
check("U6 PDF: 2 sahifa, faqat Liberation shrifti (Type1 / Times-Roman yo'q), har sahifada «N / 2»",
      lambda: (sahifalar_soni(PDF_U) == 2 and shriftlar(PDF_U) and all("LiberationSans" in f for f in shriftlar(PDF_U))
      and "1 / 2" in SU and "2 / 2" in SU), lambda: ([sahifalar_soni(PDF_U), shriftlar(PDF_U), [q for q in SU if "/" in q][:4]]))
check("U7 PDF matni: xom kod yo'q, «Bosh ofis arendasi» bor; «Hisob farqi» yo'q; rentabellik «−21,6%» («-21.6%» yo'q)",
      lambda: (not _kod_bor and "Bosh ofis arendasi" in SU and not [q for q in SU if "Hisob farqi" in q]
      and keyingi(SU, "RENTABELLIK") == "−21,6%" and not [q for q in SU if "21.6" in q]), lambda: ([_kod_bor, keyingi(SU, "RENTABELLIK")]))
check("U8 tafsilot: 7 guruh tartibda, har guruh summasi = qatorlari yig'indisi, guruhlar yig'indisi = JAMI XARAJAT 57 718 473 so'm",
      lambda: (TU == ["Sotilgan mahsulot tannarxi", "Oyliklar va usta bonusi", "Doimiy xarajatlar", "Brak va yo'qotishlar", "Transport va yuk ishlari",
             "Boshqa xarajatlar", "Kutilmagan xarajatlar"]
      and all(son(s) == sum(son(v) for _n, v in q) for s, q in GU.values())
      and sum(son(s) for s, _q in GU.values()) == son(JU) == 57718473), lambda: ([TU, JU, {g: (s, len(q)) for g, (s, q) in GU.items()}]))
check("U9 kartalar oldingi oy bilan: «Avgust 2026: 53 200 000» «▼ 10,8%», «Avgust 2026: 50 700 000» «▲ 13,8%», «Avgust 2026: +2 500 000» "
      "«▼ 12 757 493», «Avgust 2026: 4,7%» «▼ 26,3 punkt»",
      lambda: ([keyingi(SU, "JAMI DAROMAD", 2), keyingi(SU, "JAMI DAROMAD", 3)] == ["Avgust 2026: 53 200 000", "▼ 10,8%"]
      and [keyingi(SU, "JAMI XARAJAT", 2), keyingi(SU, "JAMI XARAJAT", 3)] == ["Avgust 2026: 50 700 000", "▲ 13,8%"]
      and [keyingi(SU, "SOF FOYDA", 2), keyingi(SU, "SOF FOYDA", 3)] == ["Avgust 2026: +2 500 000", "▼ 12 757 493"]
      and [keyingi(SU, "RENTABELLIK", 2), keyingi(SU, "RENTABELLIK", 3)] == ["Avgust 2026: 4,7%", "▼ 26,3 punkt"]),
      lambda: ([[keyingi(SU, y, n) for n in (1, 2, 3)] for y in ("JAMI DAROMAD", "JAMI XARAJAT", "SOF FOYDA", "RENTABELLIK")]))
_tk = SU.index("Xarajatlar tarkibi") if "Xarajatlar tarkibi" in SU else -1
_tq = SU[_tk:SU.index("Xarajatlar tafsiloti")] if _tk >= 0 and "Xarajatlar tafsiloti" in SU else []
check("U10 «Xarajatlar tarkibi»: ustunlar Guruh / Sentabr / Ulush / Avgust / O'zgarish; «Boshqa xarajatlar» 9 667 500 · 16,7% · 1 300 000 · "
      "+8 367 500; JAMI 57 718 473 · 50 700 000 · +7 018 473",
      lambda: (_tq[1:6] == ["Guruh", "Sentabr", "Ulush", "Avgust", "O'zgarish"]
      and ixcham(" ".join(_tq)).count(ixcham("Boshqa xarajatlar 9 667 500 so'm 16,7% 1 300 000 +8 367 500")) == 1
      and ixcham(" ".join(_tq)).count(ixcham("JAMI XARAJAT 57 718 473 so'm 100% 50 700 000 +7 018 473")) == 1), lambda: (_tq[:12]))
check("U11 qisqa xulosa — faqat raqamlar: zarar 10 257 493, qoplash 82,2%, eng katta xarajat — tannarx (38%), Avgust bilan: daromad −10,8%, "
      "xarajat +13,8%, eng ko'p o'sgan — Boshqa xarajatlar (+8 367 500)",
      lambda: (keyingi(SU, "Natija") == "Sentabr 2026: 10 257 493 so'm zarar (rentabellik −21,6%)."
      and keyingi(SU, "Qoplash") == "Daromad xarajatlarning 82,2% ini qopladi."
      and keyingi(SU, "Eng katta xarajat") == "Sotilgan mahsulot tannarxi — 21 960 463 so'm (38%)."
      and keyingi(SU, "Avgust 2026 bilan") == ("daromad −10,8%, xarajat +13,8%. Eng ko'p o'sgan: Boshqa xarajatlar (+8 367 500 so'm).")),
      lambda: ([keyingi(SU, y) for y in ("Natija", "Qoplash", "Eng katta xarajat", "Avgust 2026 bilan")]))
check("U12 yakun: «47 460 980 so'm − 57 718 473 so'm = −10 257 493 so'm · −21,6%»; qarzlar va daromad bloklari bor",
      lambda: (SU[len(SU) - 1 - SU[::-1].index("RENTABELLIK") + 1:][:6] == ["47 460 980 so'm", "−", "57 718 473 so'm", "=", "−10 257 493 so'm",
                                                                    "−21,6%"]
      and "Qarzlar va majburiyatlar" in SU and keyingi(SU, "BIZGA QARZDORLAR") == "57 641 292 so'm" and "Daromad tarkibi" in SU),
      lambda: (SU[-12:]))

_m = fp("_moslash")
_r1 = xav(_m, [("a", 10.0), ("b", 3.0)], 12.6, "U", standart=[])
_r2 = xav(_m, [("a", 10.0), ("b", 3.0)], 20.0, "U", standart=[])
_r3 = xav(_m, [], 5.0, "U", standart=[])
_r4 = xav(_m, [("a", None)], None, "U", standart=[])
check("U13 `_moslash`: yaxlitlash qoldig'i (≤ 0,5 so'm × qator) — eng katta qatorga; kattaroq farq — «… — boshqa yozuvlar»; qator yo'q — bitta "
      "umumiy qator; jami yashirin — «—» (None)",
      lambda: (len(_r1) == 2 and _r1[0][0] == "a" and abs(_r1[0][1] - 9.6) < 1e-9 and _r1[1] == ("b", 3.0)
      and len(_r2) == 3 and _r2[:2] == [("a", 10.0), ("b", 3.0)] and _r2[2][0] == "U — boshqa yozuvlar" and abs(_r2[2][1] - 7.0) < 1e-9
      and _r3 == [("U", 5.0)] and _r4 == [("a", None)]), lambda: ([_r1, _r2, _r3, _r4]))
check("U14 `oldingi_oy_xulosasi`: guruhlar yig'indisi = jami xarajat (butun so'mda); bo'sh oy (daromad va xarajat yo'q) va None — None",
      lambda: (OLD and sum(OLD["guruhlar"].values()) == OLD["jami_xarajat"] == 50700000 and OLD["sof_foyda"] == 2500000
      and FPM.oldingi_oy_xulosasi(None) is None
      and FPM.oldingi_oy_xulosasi({"year": 2026, "month": 7, "daromad": 0, "sof_foyda": 0.0, "foyda_foiz": 0, "xarajatlar": {},
                                   "qoshimcha_xarajatlar": {}}) is None), lambda: (OLD))
# «Tannarx va foyda» ruxsatisiz ko'rinish (hisobotlar o'sha tozalash bilan)
_rt = json.loads(json.dumps(SEN_REP))
RX.tannarx_tozala(_rt, "/api/finance/report")
_ot = json.loads(json.dumps(AVG_REP))
RX.tannarx_tozala(_ot, "/api/finance/report")
_brt = [{"item_name": m["item_name"], "value": None} for m in SEN_BRAK]
DT = xav(fp("hisobot_raqamlari"), _rt, SEN_TX, _brt, MAJ, True) or {"guruhlar": []}
OT = xav(fp("oldingi_oy_xulosasi"), _ot, MAJ)
PDF_T = xav(FPM.generate_finance_report_pdf, _rt, SEN_TX, _brt, 2026, 9, DEBT, tannarx_yoq=True, oldingi=OT, majburiyat_nomlari=MAJ,
            standart=b"")
ST = xav(pdf_matn, PDF_T, standart=[]) or []
GT = {g["kalit"]: g for g in DT["guruhlar"]}
check("U15 tannarxsiz: JAMI / SOF FOYDA / rentabellik — None, tannarx va brak guruhi — None, qolgan guruhlar o'z summasi bilan; o'tgan oy "
      "jami / sof — None",
      lambda: (DT.get("jami") is None and DT.get("sof") is None and GT.get("tannarx", {}).get("summa", 0) is None
      and GT.get("brak", {}).get("summa", 0) is None and GT.get("doimiy", {}).get("summa") == 5251000
      and OT and OT["jami_xarajat"] is None and OT["sof_foyda"] is None and OT["daromad"] == 53200000),
      lambda: ([DT.get("jami"), {k: g["summa"] for k, g in GT.items()}, OT]))
_raqamlar_t = " ".join(ST)
check("U16 tannarxsiz PDF: kartalar JAMI XARAJAT / SOF FOYDA / RENTABELLIK «—», o'tgan oy jami / sof «Avgust 2026: —»; sir raqamlar (sof "
      "foyda, tannarx, brak, o'tgan oy jami / sof) matnda YO'Q",
      lambda: ([keyingi(ST, y) for y in ("JAMI XARAJAT", "SOF FOYDA", "RENTABELLIK")] == ["—"] * 3
      and keyingi(ST, "JAMI XARAJAT", 2) == "Avgust 2026: —" and keyingi(ST, "SOF FOYDA", 2) == "Avgust 2026: —"
      and not any(x in _raqamlar_t for x in ("10 257 493", "21 960 463", "983 27", "1 018 12", "50 700 000", "2 500 000", "57 718 473"))),
      lambda: ([[keyingi(ST, y, n) for n in (1, 2)] for y in ("JAMI XARAJAT", "SOF FOYDA", "RENTABELLIK")]))

# ── mustaqil tekshiruv topganlari (kech154): o'tgan oyda bor, shu oyda yo'q guruh; 0 ga yaxlitlangan brak bo'lagi; tannarxsiz xulosa;
#    o'tgan oy ustuni = o'sha oy PDF i; guruh sarlavhasi sahifa oxirida; uzun korxona nomi
_A2, _tx2, _b2 = oy_hisoboti(2026, 8, 12000000.0, 8000000.0, 1000000, [], [], [], 700000, {}, [])
_A2["ehson_xarajat"] = 500000.0
_A2["sof_foyda_tarkibi"]["ehson"] = 500000.0
_A2["sof_foyda"] -= 500000.0
_S2, _tx2s, _b2s = oy_hisoboti(2026, 9, 12000000.0, 8000000.0, 1000000, [], [], [], 0, {}, [])
_O2 = xav(fp("oldingi_oy_xulosasi"), _A2, {})
_P2 = xav(FPM.generate_finance_report_pdf, _S2, [], [], 2026, 9, None, oldingi=_O2, standart=b"")
_S2t = xav(pdf_matn, _P2, standart=[]) or []
_t2 = _S2t[_S2t.index("Xarajatlar tarkibi"):_S2t.index("Xarajatlar tafsiloti")] if "Xarajatlar tarkibi" in _S2t and "Xarajatlar tafsiloti" in _S2t else []
check("U17 o'tgan oyda bo'lib shu oyda YO'Q guruh (Ehson, Transport) ham jadvalda: shu oy «0 so'm», o'tgan oy summasi, o'zgarish «−…»; o'tgan oy "
      "ustuni yig'indisi = o'sha oy JAMI (10 200 000)",
      lambda: (ixcham(" ".join(_t2)).count(ixcham("Transport va yuk ishlari 0 so'm 0% 700 000 \u2212700 000")) == 1
               and ixcham(" ".join(_t2)).count(ixcham("Ehson 0 so'm 0% 500 000 \u2212500 000")) == 1
               and ixcham(" ".join(_t2)).count(ixcham("JAMI XARAJAT 9 000 000 so'm 100% 10 200 000 \u22121 200 000")) == 1
               and sum(v for v in _O2["guruhlar"].values()) == _O2["jami_xarajat"] == 10200000),
      lambda: (_t2, _O2))
_r5 = xav(fp("_moslash"), [("a", 100.0), ("b", 0.0)], 101.0, "U", standart=[])
_rb = xav(fp("hisobot_raqamlari"), {**SEN_REP, "sof_foyda_tarkibi": {**SEN_REP["sof_foyda_tarkibi"], "brak": 101.0},
                                    "sof_foyda": SEN_REP["sof_foyda"] + SEN_REP["sof_foyda_tarkibi"]["brak"] - 101.0},
          SEN_TX, [{"item_name": "Penoplast", "value": 100}, {"item_name": "Mel", "value": 0}], MAJ, standart={"guruhlar": []})
check("U18 0 ga yaxlitlangan brak bo'lagi (100,5 → 100 va 0,5 → 0, brak 101): qoldiq eng katta qatorga — «… boshqa yozuvlar 1 so'm» qatori YO'Q",
      lambda: (_r5 == [("a", 101.0)]
               and dict(next(g for g in _rb["guruhlar"] if g["kalit"] == "brak")["qatorlar"]) == {"Brak — Penoplast": 101}),
      lambda: (_r5, [g for g in _rb["guruhlar"] if g["kalit"] == "brak"]))
check("U19 tannarxsiz PDF: «Eng katta xarajat» va «Eng ko'p o'sgan» yo'q (yashirin guruhsiz xulosa noto'g'ri bo'lardi); admin PDF ida — bor",
      lambda: ("Eng katta xarajat" not in ST and not [q for q in ST if "Eng ko'p o'sgan" in q]
               and "Eng katta xarajat" in SU and [q for q in SU if "Eng ko'p o'sgan" in q]),
      lambda: ([q for q in ST if "Eng" in q], [q for q in SU if "Eng" in q]))
_A3, _tx3, _b3 = oy_hisoboti(2026, 8, 1000000.5, 0.0, 1500000, [], [], [], 700000, {}, [])
_O3 = xav(fp("oldingi_oy_xulosasi"), _A3, {})
_D3 = xav(fp("hisobot_raqamlari"), _A3, [], [], {}, standart={"guruhlar": []})
check("U20 o'tgan oy guruhlari — o'sha oyning O'Z PDF idagi bilan AYNAN (yaxlitlash qoldig'i bo'sh guruhga tushmaydi: «tannarx 1» yo'q)",
      lambda: ({k: v for k, v in _O3["guruhlar"].items() if v} == {g["kalit"]: g["summa"] for g in _D3["guruhlar"]}
               and not _O3["guruhlar"]["tannarx"] and _O3["jami_xarajat"] == _D3["jami"]),
      lambda: (_O3, [(g["kalit"], g["summa"]) for g in _D3["guruhlar"]]))



# 43 hodim — NOSPLIT siz «Doimiy xarajatlar» sarlavhasi 2-sahifa oxirida yolg'iz qolardi (O'LCHANGAN: 4, 35, 37, 40, 43, 53, 84, 86 da)
_hod = [(f"Hodim {i:02d}", "Kesuvchi", "Doimiy oylik", 1_000_000 + i) for i in range(1, 44)]
_S4, _tx4, _b4 = oy_hisoboti(2026, 9, 90000000.0, 21960463.0, 2551000, [("Axroraka", 3.0, 3146149)], _hod,
                             [("Penoplast 14P", 983270.7), ("Akril Toshkent", 24737.8)], 750000,
                             {"bosh_offic_arenda_8477": 2000000.0, "boshqa": 9667500.0, "kutilmagan": 704000.0},
                             [(c, n, a) for c, n, a in [("boshqa", f"Izoh {i}", 100000 + i) for i in range(1, 30)]]
                             + [("boshqa", "Qoldiq", 9667500 - sum(100000 + i for i in range(1, 30))), ("kutilmagan", "Titan kley", 704000)])
_P4 = xav(FPM.generate_finance_report_pdf, _S4, _tx4, _b4, 2026, 9, None, oldingi=OLD, majburiyat_nomlari=MAJ, standart=b"")
_gn4 = {g for _k, g in getattr(FPM, "XARAJAT_GURUHLARI", ())}


def _sahifa_oxirlari(bayt):
    """Har sahifaning pastki qatordan oldingi OXIRGI ikki mazmun qatori (jadval qatori — nom va summa)."""
    obyektlar = {int(n): tana for n, tana in re.findall(rb"(\d+) 0 obj\s*(.*?)\s*endobj", bayt, re.S)}
    kids = []
    for tana in obyektlar.values():
        if re.search(rb"/Type\s*/Pages\b", tana):
            k = re.search(rb"/Kids\s*\[([^\]]*)\]", tana)
            kids = [int(x) for x in re.findall(rb"(\d+)\s+0\s+R", k.group(1))] if k else []
    oxirlar = []
    for p in kids:
        c = re.search(rb"/Contents\s+(\d+)\s+0\s+R", obyektlar.get(p, b""))
        if not c:
            continue
        bitta = re.sub(rb"/Kids\s*\[[^\]]*\]", b"/Kids [" + str(p).encode() + b" 0 R]", bayt, count=1)
        q = [x for x in pdf_matn(bitta) if not re.fullmatch(r"\d+ / \d+", x) and "Yaratildi:" not in x]
        oxirlar.append(q[-2:] if len(q) >= 2 else None)
    return oxirlar


_ox4 = xav(_sahifa_oxirlari, _P4, standart=[]) or []
check("U21 ko'p qatorli tafsilot (43 hodim): 3+ sahifa, hech bir sahifa guruh sarlavhasi bilan TUGAMAYDI (sarlavha birinchi qatori bilan)",
      lambda: (sahifalar_soni(_P4) >= 3 and len(_ox4) == sahifalar_soni(_P4)
               and not [x for x in _ox4[:-1] if x is None or re.sub(r"\s+·\s+[−-]?[\d,]+%$", "", x[0]) in _gn4]),
      lambda: (sahifalar_soni(_P4), _ox4))
_uzun = "Juda Uzun Korxona Nomi " * 8
FPM.get_brand, _asl_brand = (lambda db=None, company_id=None: {"name": _uzun.strip(), "subtitle": "Sinov"}), FPM.get_brand
try:
    _P5 = xav(FPM.generate_finance_report_pdf, SEN_REP, SEN_TX, SEN_BRAK, 2026, 9, None, oldingi=OLD, majburiyat_nomlari=MAJ, standart=b"")
finally:
    FPM.get_brand = _asl_brand
_pq5 = [q for q in (xav(pdf_matn, _P5, standart=[]) or []) if "Yaratildi:" in q]
from reportlab.pdfbase.pdfmetrics import stringWidth as _sw   # noqa: E402
check("U22 uzun korxona nomi (180 belgi): pastki qator qisqartirilgan («…»), «Yaratildi: …» saqlangan, eni sahifa raqamigacha sig'adi",
      lambda: (len(_pq5) == 2 and all("…" in q and re.search(r"Yaratildi: \d\d\.\d\d\.\d{4} \d\d:\d\d$", q) for q in _pq5)
               and all(_sw(q, "Helvetica", 7.5) <= FPM.A4[0] - 2.6 * FPM.cm - 2 * FPM.cm + 0.5 for q in _pq5)),
      lambda: ([(q, round(_sw(q, "Helvetica", 7.5))) for q in _pq5]))

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# D — marshrut: fikstura API orqali
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
import datetime as _dt                             # noqa: E402
_tk = _dt.datetime.utcnow() + _dt.timedelta(hours=5)
YIL, OY = _tk.year, _tk.month
O_YIL, O_OY = (YIL, OY - 1) if OY > 1 else (YIL - 1, 12)
KOD = "ofis_arenda_7731"
NOM = "Ofis <arenda> & svet"
KOD2 = "eski_ombor_ijara_4321"          # «Biz qarzdormiz» dan O'CHIRILADIGAN majburiyat (xarajat tarixi qoladi)
PAROL = "Parol123!"

s = SessionLocal()
if not s.get(Company, 2):
    s.add(Company(id=2, name="K205 B korxona"))
    s.commit()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k205_admin", PAROL, UserRole.ADMIN, "K205 Admin", company_id=1)
    auth.create_user(s, "k205_tannarxsiz", PAROL, UserRole.MANAGER, "K205 Tannarxsiz", company_id=1)
_hammasi = {b: list(v["amallar"]) for b, v in RX.BANDLAR.items()}
_rol_t = Rol(company_id=1, nom="K205 Tannarxsiz", kod=None, ruxsatlar=json.dumps({b: v for b, v in _hammasi.items() if b != "tannarx"}),
             tavsif="")
s.add(_rol_t)
s.commit()
s.query(User).filter(User.username == "k205_tannarxsiz").first().rol_id = _rol_t.id
PRJ = Project(company_id=1, client_name="K205 Mijoz", project_name="K205 loyiha", total_budget=0, total_paid=0)
PENO = Inventory(company_id=1, item_name="K205 Penoplast", unit="blok", stock_quantity=10_000, price_per_unit=500_000,
                 volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
USTA = Master(company_id=1, name="K205 Usta", phone="+998900002050", kpi_percent=10)
s.add_all([PRJ, PENO, USTA,
           RecurringObligation(company_id=2, category=KOD, label="BEGONA korxona nomi", monthly_target=1000, due_day=5, is_active=True)])
s.commit()
ID = {"PRJ": PRJ.id, "PENO": PENO.id, "USTA": USTA.id}
s.close()


def kirish(login):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    r = c.post("/login", data={"username": login, "password": PAROL}, follow_redirects=False)
    return c, r.status_code


CA, _la = kirish("k205_admin")
CT, _lt = kirish("k205_tannarxsiz")
_ob = CA.post("/api/obligations/recurring", params={"category": KOD, "label": NOM, "monthly_target": "2000000", "icon": "📦", "due_day": "5"})
_ob2 = CA.post("/api/obligations/recurring", params={"category": KOD2, "label": "Eski ombor ijarasi", "monthly_target": "400000", "icon": "📦",
                                                     "due_day": "5"})
_oy_ichida = f"{YIL}-{OY:02d}-{min(_tk.day, 28):02d}T{_tk.hour:02d}:00:00"
_otgan = f"{O_YIL}-{O_OY:02d}-15T12:00:00"
XAR = [(KOD, 2_000_000, "oktabr arendasi", None), ("tushlik", 300_000, None, None), ("boshqa", 1_500_000, "Tozalik", None),
       ("boshqa", 20_000, "Jilvir", None), ("boshqa", 10_000, "  JILVIR ", None), ("kutilmagan", 60_000, "Zapchast", None),
       (KOD, 2_000_000, "o'tgan oy arendasi", _otgan), ("tushlik", 250_000, None, _otgan), ("boshqa", 100_000, "Mayda", _otgan),
       (KOD2, 400_000, "ombor ijarasi", None)]
_st = []
for _c, _v, _iz, _sana in XAR:
    _j = {"category": _c, "amount": float(_v), "notes": _iz}
    if _sana:
        _j["date"] = _sana
    _st.append(CA.post("/api/finance/transactions", json=_j).status_code)
_del2 = CA.delete(f"/api/obligations/recurring/{(_ob2.json() or {}).get('id') if _ob2.status_code == 200 else 0}")
_ro = CA.post("/api/orders", params={"confirm_shortage": "true"}, json={
    "project_id": ID["PRJ"], "order_type": "product", "master_id": ID["USTA"],
    "items": [{"name": "K205 detal", "category": "profil", "width": 20, "thickness": 10, "length": 10, "quantity": 1,
               "unit_price": 1_000_000, "is_coated": False, "penoplast_id": ID["PENO"]}]})
ID["O1"] = (_ro.json() or {}).get("id") if _ro.status_code == 200 else None
s = SessionLocal()
try:
    from sqlalchemy import text as _text
    ID["IT1"] = s.execute(_text("SELECT id FROM order_items WHERE order_id = :o"), {"o": ID["O1"] or 0}).scalar()
finally:
    s.close()
_rd = CA.post("/api/deliveries", json={"order_id": ID["O1"], "items": [{"order_item_id": ID["IT1"], "quantity": 10}],
                                       "transport_cost": 0, "transport_payer": "none", "payment_method": "naqd", "payment_amount": 1_000_000})
_rt_ = CA.post(f"/api/orders/{ID['O1']}/ready", params={"loy_kg": "0"})

section("D — marshrut (fikstura API orqali)")
check("D0 fikstura: kirish (admin, tannarxsiz), majburiyat turkumi (nomida «<», «&»), ikkinchi majburiyat (to'lovdan keyin O'CHIRILDI), 10 xarajat "
      "(3 tasi o'tgan oyda), buyurtma → yuk → «Tayyor»",
      lambda: (_la in (302, 303) and _lt in (302, 303) and _ob.status_code == 200 and _ob2.status_code == 200 and _del2.status_code == 200
      and _st == [200] * 10 and _rd.status_code == 200
      and _rt_.status_code == 200), lambda: ([_la, _lt, _ob.status_code, _ob.text[:120], _st, _rd.status_code, _rt_.status_code, _rt_.text[:160]]))

REP = xav(lambda: CA.get("/api/finance/report", params={"year": YIL, "month": OY}).json(), standart={}) or {}
REP_O = xav(lambda: CA.get("/api/finance/report", params={"year": O_YIL, "month": O_OY}).json(), standart={}) or {}
s = SessionLocal()
try:
    _xizmat = jsonable_encoder(services.get_monthly_report(s, YIL, OY, company_id=1))
finally:
    s.close()
check("D1 `/api/finance/report`: `qoshimcha_nomlari` = {kod: shu korxona nomi} (2-korxonaning o'sha kodli nomi EMAS); qolgan javob "
      "`services.get_monthly_report` bilan AYNAN (raqamlar o'zgarmagan)",
      lambda: (REP.get("qoshimcha_nomlari") == {KOD: NOM, KOD2: "Eski ombor ijara"} and {k: v for k, v in REP.items() if k != "qoshimcha_nomlari"} == _xizmat
      and REP.get("qoshimcha_xarajatlar", {}).get(KOD) == 2_000_000),
      lambda: ([REP.get("qoshimcha_nomlari"), sorted(set(REP) ^ set(_xizmat)), REP.get("qoshimcha_xarajatlar")]))

_pa = CA.get("/api/finance/report-pdf", params={"year": YIL, "month": OY})
PA = _pa.content if _pa.status_code == 200 else b""
SA = xav(pdf_matn, PA, standart=[]) or []
GA, TA, JA = tafsilot(SA)
_jami_kut = int(REP.get("daromad", 0)) - FPM._yaxlit_butun(REP.get("sof_foyda", 0))
check("D2 PDF 200, 2 sahifa, faqat Liberation shrifti, «1 / 2» va «2 / 2»",
      lambda: (_pa.status_code == 200 and sahifalar_soni(PA) == 2 and shriftlar(PA) and all("LiberationSans" in f for f in shriftlar(PA))
      and "1 / 2" in SA and "2 / 2" in SA), lambda: ([_pa.status_code, sahifalar_soni(PA), shriftlar(PA)]))
_doimiy = dict((ixcham(n), son(v)) for n, v in GA.get("Doimiy xarajatlar", ("", []))[1])
check("D3 «Doimiy xarajatlar» da majburiyat NOMI AYNAN («Ofis <arenda> & svet», belgilash sifatida o'qilmagan) 2 000 000 va Tushlik 300 000; "
      "xom kod va 2-korxona nomi PDF da YO'Q",
      lambda: (_doimiy.get(ixcham(NOM)) == 2_000_000 and _doimiy.get("Tushlik") == 300_000
      and not [q for q in SA if KOD in q or "BEGONA" in q]), lambda: ([GA.get("Doimiy xarajatlar"), [q for q in SA if "ofis" in q.lower()][:4]]))
_bq = dict(GA.get("Boshqa xarajatlar", ("", []))[1])
check("D4 «Boshqa xarajatlar»: «Tozalik» 1 500 000; «Jilvir» + «  JILVIR » — bitta «Jilvir» 30 000; «Kutilmagan xarajatlar»: «Zapchast» 60 000",
      lambda: (son(_bq.get("Tozalik")) == 1_500_000 and son(_bq.get("Jilvir")) == 30_000 and not [n for n in _bq if n.upper() == "JILVIR" and n != "Jilvir"]
      and son(dict(GA.get("Kutilmagan xarajatlar", ("", []))[1]).get("Zapchast")) == 60_000), lambda: ([_bq, GA.get("Kutilmagan xarajatlar")]))
check("D5 tafsilot: har guruh summasi = qatorlari yig'indisi; guruhlar yig'indisi = JAMI XARAJAT = hisobot (daromad − sof foyda, butun "
      "so'mda); «Hisob farqi» yo'q",
      lambda: (GA and all(son(sm) == sum(son(v) for _n, v in q) for sm, q in GA.values()) and sum(son(sm) for sm, _q in GA.values()) == son(JA) == _jami_kut
      and not [q for q in SA if "Hisob farqi" in q]), lambda: ([JA, _jami_kut, {g: (sm, [son(v) for _n, v in q]) for g, (sm, q) in GA.items()}]))
_ren = keyingi(SA, "RENTABELLIK")
check("D6 rentabellik karta — hisobot `foyda_foiz` i «−N,N%» ko'rinishida (U+2212, vergul); zararli oy",
      lambda: (REP.get("foyda_foiz", 0) < 0 and _ren == FPM._foiz_uz(REP.get("foyda_foiz"), True) and _ren.startswith("−") and "." not in _ren),
      lambda: ([_ren, REP.get("foyda_foiz")]))
_on = f"{FPM.MONTH_NAMES[O_OY]} {O_YIL}"
_o_jami = int(REP_O.get("daromad", 0)) - FPM._yaxlit_butun(REP_O.get("sof_foyda", 0))
check("D7 o'tgan oy kartalarda (hisobot bilan): «<oy> <yil>: <daromad>», «… : <jami xarajat>», «… : <sof foyda ±>»; guruhlar jadvalida o'tgan "
      "oy ustuni va «O'zgarish»; qisqa xulosada «… bilan»",
      lambda: (keyingi(SA, "JAMI DAROMAD", 2) == f"{_on}: {FPM._fmt_ishora(REP_O.get('daromad', 0))}"
      and keyingi(SA, "JAMI XARAJAT", 2) == f"{_on}: {FPM._fmt_ishora(_o_jami)}"
      and keyingi(SA, "SOF FOYDA", 2) == f"{_on}: {FPM._fmt_natija(FPM._yaxlit_butun(REP_O.get('sof_foyda', 0)))}"
      and FPM.MONTH_NAMES[O_OY] in SA and "O'zgarish" in SA and f"{_on} bilan" in SA and _o_jami == 2_350_000),
      lambda: ([[keyingi(SA, y, 2) for y in ("JAMI DAROMAD", "JAMI XARAJAT", "SOF FOYDA")], _o_jami]))
_pt = CT.get("/api/finance/report-pdf", params={"year": YIL, "month": OY})
STT = xav(pdf_matn, _pt.content, standart=[]) if _pt.status_code == 200 else []
check("D8 tannarxsiz foydalanuvchi: kartalar JAMI XARAJAT / SOF FOYDA / RENTABELLIK «—»; o'tgan oy jami xarajat va sof foyda ham «—» (o'sha "
      "tozalash — marshrut o'tgan oy hisobotini tozalaydi); o'tgan oy jami (2 350 000) matnda YO'Q",
      lambda: (_pt.status_code == 200 and [keyingi(STT, y) for y in ("JAMI XARAJAT", "SOF FOYDA", "RENTABELLIK")] == ["—"] * 3
      and keyingi(STT, "JAMI XARAJAT", 2) == f"{_on}: —" and keyingi(STT, "SOF FOYDA", 2) == f"{_on}: —"
      and not any("2 350 000" in q for q in STT)),
      lambda: ([_pt.status_code, [[keyingi(STT, y, n) for n in (1, 2)] for y in ("JAMI XARAJAT", "SOF FOYDA", "RENTABELLIK")]]))
_po = CA.get("/api/finance/report-pdf", params={"year": O_YIL, "month": O_OY})
SPO = xav(pdf_matn, _po.content, standart=[]) if _po.status_code == 200 else []
_pj = CA.get("/api/finance/report-pdf", params={"year": YIL, "month": 1})
check("D9 o'tgan oyi bo'sh oy (fiksturaning o'tgan oyi) — solishtirishsiz (O'zgarish ustuni, karta qatori yo'q), o'z majburiyat nomi bilan; "
      "yanvar (o'tgan yil dekabri bilan) — 200",
      lambda: (_po.status_code == 200 and "O'zgarish" not in SPO and not [q for q in SPO if q.endswith(" bilan")]
      and ixcham(NOM) in [ixcham(q) for q in SPO] and _pj.status_code == 200 and _pj.content.startswith(b"%PDF")),
      lambda: ([_po.status_code, _pj.status_code, [q for q in SPO if "bilan" in q or "O'zgarish" in q][:3]]))


def js_funksiya(src, nom_):
    i = src.find(f"\nfunction {nom_}(")
    if i < 0:
        return None
    j = src.find("\n}\n", i)
    return src[i + 1:j + 2] if j > 0 else None


_fn = js_funksiya(FH, "buildExpDetail")
_base = fayl("templates/base.html")
_yordam = "\n".join(filter(None, (js_funksiya(_base, _n) for _n in ("sonKor", "foizKor", "birlikKor", "matnRangi"))))
_JS = r"""
const elementlar = {};
const document = {getElementById: (id) => (elementlar[id] = elementlar[id] || {style: {}, textContent: '', innerHTML: ''})};
function fmtFull(n){return Number(Math.round(n||0)).toLocaleString('ru-RU');}
function fmt(n){return String(Math.round(n||0));}
function escapeHtml(s){return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function buildRevDonut(){}
__FN__
const d = JSON.parse(require('fs').readFileSync(0, 'utf8'));
buildExpDetail(d);
process.stdout.write(JSON.stringify(elementlar['expDetail'].innerHTML));
"""
_h = ""
if _fn and REP:
    _p = xav(subprocess.run, ["node", "-e", _JS.replace("__FN__", _yordam + "\n" + _fn)], input=json.dumps(REP), capture_output=True,
             text=True, timeout=60)
    _h = (json.loads(_p.stdout) if _p is not None and _p.returncode == 0 and _p.stdout else "")
    if _p is not None and not _h:
        print("   node:", (_p.stderr or "")[:300])
_dq = re.findall(r'fin-exp-group-row-name"[^>]*>([^<]*)</span><span class="fin-exp-group-row-val">([^<]*)<', _h)
check("D10 Moliya sahifasi «Doimiy va qo'shimcha xarajatlar» (`buildExpDetail`, node): majburiyat NOMI escape bilan («Ofis &lt;arenda&gt; &amp; "
      "svet») 2 000 000; xom kod va 2-korxona nomi yo'q",
      lambda: (bool(_h) and any(n == "Ofis &lt;arenda&gt; &amp; svet" and re.sub(r"\D", "", v) == "2000000" for n, v in _dq)
      and KOD not in _h and "BEGONA" not in _h and "Ofis <arenda>" not in _h), lambda: (_dq))

check("D11 «Biz qarzdormiz» dan O'CHIRILGAN majburiyat: xarajati «Doimiy xarajatlar» da koddan nom bilan («Eski ombor ijara» 400 000), xom kod "
      "PDF da va Moliya sahifasida YO'Q",
      lambda: (_doimiy.get(ixcham("Eski ombor ijara")) == 400_000 and not [q for q in SA if KOD2 in q]
               and any(n == "Eski ombor ijara" and re.sub(r"\D", "", v) == "400000" for n, v in _dq) and KOD2 not in _h),
      lambda: (GA.get("Doimiy xarajatlar"), [q for q in SA if "ombor" in q.lower()], _dq))

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f_ in FAILED:
        print("  -", f_)
sys.exit(1 if FAIL else 0)
