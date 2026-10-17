#!/usr/bin/env python3
"""
test_xabar_miqdorlar193.py — kech152 (zip 193): server yozadigan MATNLARDAGI miqdorlar (kg, blok, metr, dona, MB, kasrli foiz) BITTA son
qoidasida.

NIMA UCHUN KERAK (egasi tanlovi 17.10 «Xabarlardagi miqdorlar»; O'LCHANGAN — `work/k193/skan193.py` (AST: `{x:g}`, `{x:.Nf}`,
`_miqdor_matn(...)` — 218 joy / 179 qator, manzili bilan) va `work/k193/skan193b.py` (formatlagichsiz son birlik yonida), zip 192 kodi):
  G  `{x:g}` — nuqtali kasr, ajratgichsiz, katta sonda eksponent: «T193 Akril: omborda 1234.5 kg bor — 2000 kg chiqim qilib bo'lmaydi»,
     «Omborda faqat 1234.5 metr bor, 2000 sota olmaysiz», tayyor mahsulot band / minus xabarlari, «📦 Ombor to'g'rilandi» ro'yxati.
  F  `{x:.Nf}` — ortiqcha nol va nuqta: «Penoplast yetishmayapti! Kerak: 12.50 blok», kam qoldiq Telegram «1234.5 kg qoldi (min: 2000,
     yetishmaydi: 766.0)» (0,5 kg minimum — «min: 0»), «Rejadan 2.5 kg ko'p ketdi», zaxira «49.3 MB».
  M  `crud._miqdor_matn` — «1234.5», «3.333» (qaytarish / MRP / brak taqdiri xabarlari).
  K  `.1f` yetishmovchilik xabari «T193 Penoplast: kerak 0.4 blok, qoldi 0.4 blok» — kerakli 0,42 qoldiq 0,4 bilan BIR XIL ko'rinardi.
  R  formatlagichsiz: qaytarish puli to'lov izohi «(3.0 dona)», Telegram «Loy tayyorlang: *12 kg*» (12,94 kg — `int()` KESARDI).
QOIDA: foydalanuvchi KO'RADIGAN matn — `crud.xabar_son` / `services.son_korinish` / `crud._miqdor_matn` (bo'linmas bo'shliq, kasr — vergul,
ortiqcha nolsiz, eksponentsiz); «Faoliyat jurnali» — `crud.audit_son` / `crud._miqdor_jurnal` (ming ajratgich ODDIY bo'shliq — jurnal
«Qidiruv» i). Kasr — miqdorda BITTA: 3 xona (sahifadagi `sonKor(x, 3)`; `:g`, `.1f`, `.2f` ham), MRP moduli — 4, MB — 1. Ichki belgilar (`[WRITEOFF:…]`, `loy_kg=…`, «Kam» kaliti),
konsol (`print`), PDF, butun foiz `{pct:.0f}%` — ataylab tegilmagan.
BO'LIMLAR: S — manba (AST); U — yordamchilar va xabar matnlari (yaxlitlash ekvivalentligi ham); D — ilovaning O'Z API si (qo'lda chiqim,
material o'chirish, sotuv, savat, brak, qo'shish / kamaytirish, «Kam» chegarasi jurnali, mahsulot o'chirish, kam qoldiq va ombor hisoboti
Telegrami, Bosh sahifa ogohlantirishlari, buyurtma penoplast yetishmasligi, yuk xati / qaytarish xatolari, qaytarish puli izohi, yuk xati
va loy Telegrami, brak taqdiri jurnali va xatosi).
REJIM: SQLite (standart), `TENANT_FILTER=1` ham; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL. Asl kodga (zip 192)
qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_xabar_miqdorlar193.py
"""
import os
import re
import io
import ast
import sys
import random
import inspect
import tempfile
import contextlib
from types import SimpleNamespace

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "xabar_miqdorlar193_test"
_T = tempfile.mkdtemp(prefix="xabar193_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'xabar193.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "QOPLAMACHI_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import crud                                        # noqa: E402
import services                                    # noqa: E402
import production_service                          # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Inventory, InventoryMovement, Project, Order, Payment, ActivityLog, FinishedProduct,   # noqa: E402
                    ProductionStatus, StockSource)
from fastapi.testclient import TestClient          # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []
NB = "\u00a0"


def check(label, cond, detail=""):
    global OK, FAIL
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e} | {detail}"
    if cond:
        OK += 1
        print(f"  ✓ {REJIM}{label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {REJIM}{label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def oqi(yol):
    return open(os.path.join(ROOT, yol), encoding="utf-8").read()


def _src(f):
    try:
        return inspect.getsource(f)
    except Exception:                      # noqa: BLE001
        return ""


def nb(s):
    """«1 500 000» (oddiy bo'shliq bilan yozilgan kutilgan qiymat) → bo'linmas bo'shliqli ko'rinish (faqat raqamlar orasida)."""
    return re.sub(r"(?<=\d) (?=\d)", NB, s)


def _sinab(f, *a):
    try:
        return f(*a)
    except Exception as e:                 # noqa: BLE001
        return f"{type(e).__name__}"


# ── S. Manba (AST) ────────────────────────────────────────────────────────────────────────────────────────────
section("S: server matnlari — `:g` / `.Nf` miqdor, formatlagichsiz miqdor, jurnalda bo'linmas bo'shliq YO'Q (AST)")
TASHQARIDA = {"delivery_pdf.py", "finance_pdf.py", "pdf_service.py", "erp_backup_tekshiruv.py"}   # PDF (reportlab), konsol skripti
# ICHKI (ko'rinish emas — izohdan regex bilan o'qiladigan belgi / bazadagi kalit): fayl, funksiya, spec
ICHKI = {("main.py", "_tolov_qoldigini_chegirmaga", ".0f"),       # `[WRITEOFF:…]`
         ("services.py", "complete_order", ".4f"),               # `loy_kg=…`
         ("models.py", "_s", "g")}                               # «Kam» chegarasi kaliti (`tm_kam_kaliti._s`)
JURNAL_CHAQIRUV = {"log_activity", "ActivityLog", "_AL", "_po_jurnal"}
FORMATLAGICH = {"son_korinish", "_son110", "xabar_son", "audit_son", "_miqdor_matn", "_miqdor_jurnal", "_som", "fmt_money", "_son_uz",
                "_son"}
XABAR_FN = {"_miqdor_matn", "xabar_son", "son_korinish"}


def _spec(fv):
    """kech151 saboq'i: spec — format_spec ning Constant qiymatlaridan (`get_source_segment` 3.13 da «:g» yoki None beradi)."""
    if not isinstance(fv.format_spec, ast.JoinedStr):
        return ""
    return "".join(str(c.value) for c in fv.format_spec.values if isinstance(c, ast.Constant))


def _nom(c):
    f = c.func
    return f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")


def _skan():
    miqdor, xom, jurnal_nb, jurnal_ro = [], [], [], []
    for fn in sorted(os.listdir(ROOT)):
        if not fn.endswith(".py") or fn in TASHQARIDA:
            continue
        src = oqi(fn)
        tree = ast.parse(src)
        ota = {}
        for n in ast.walk(tree):
            for c in ast.iter_child_nodes(n):
                ota[c] = n

        def zanjir(n):
            while n in ota:
                n = ota[n]
                yield n

        def fn_nomi(n):
            for p in zanjir(n):
                if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    return p.name
            return "<modul>"

        def printdami(n):
            return any(isinstance(p, ast.Call) and _nom(p) == "print" for p in zanjir(n))

        for n in ast.walk(tree):
            if isinstance(n, ast.JoinedStr):
                v = n.values
                for i, x in enumerate(v):
                    if not isinstance(x, ast.FormattedValue):
                        continue
                    sp = _spec(x)
                    keyin = v[i + 1] if i + 1 < len(v) else None
                    if re.fullmatch(r"\.\d+f|g|\.\d+g", sp):
                        if printdami(x) or (fn, fn_nomi(x), sp) in ICHKI:
                            continue
                        if sp == ".0f" and isinstance(keyin, ast.Constant) and str(keyin.value).startswith("%"):
                            continue          # butun foiz «40%»
                        miqdor.append(f"{fn}:{x.lineno} {fn_nomi(x)} {{:{sp}}}")
                    elif sp == "" and x.conversion == -1 and not printdami(x):
                        ifoda = ast.get_source_segment(src, x.value) or ""
                        if not re.search(r"quantity|qty\b|stock|loy_kg|miqdor\b|_mb\b", ifoda) or re.search(r"len\(|_id\b|\.id\b", ifoda):
                            continue
                        if isinstance(x.value, ast.Call) and _nom(x.value) in FORMATLAGICH:
                            continue          # allaqachon son qoidasida
                        birlik = (isinstance(keyin, ast.Constant) and re.match(r" ?(kg|blok|dona|metr|m²|m³|m|ta|birlik|litr|MB)\b",
                                                                                 str(keyin.value)))
                        birlik = birlik or (isinstance(keyin, ast.Constant) and keyin.value == " " and i + 2 < len(v)
                                            and isinstance(v[i + 2], ast.FormattedValue)
                                            and re.search(r"unit|birlik", ast.get_source_segment(src, v[i + 2].value) or ""))
                        if birlik and fn != "models.py":
                            xom.append(f"{fn}:{x.lineno} {fn_nomi(x)} {{{ifoda[:50]}}}")
            if isinstance(n, ast.Call) and _nom(n) in JURNAL_CHAQIRUV:
                for d in ast.walk(n):
                    if isinstance(d, ast.Call) and _nom(d) in XABAR_FN:
                        jurnal_nb.append(f"{fn}:{d.lineno} {fn_nomi(d)} {_nom(d)}")
            # jurnal ro'yxatlari / o'zgaruvchilari (brak taqdiri `jurnal`, qaytarish o'chirilgani `_qator` / `_xom`) va `_taqdir_teskari`
            hedef = None
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "append" \
                    and isinstance(n.func.value, ast.Name) and n.func.value.id in ("jurnal", "_xom"):
                hedef = n
            elif isinstance(n, (ast.Assign, ast.AugAssign)):
                t = n.targets[0] if isinstance(n, ast.Assign) else n.target
                if isinstance(t, ast.Name) and t.id == "_qator" and fn == "crud.py":
                    hedef = n
            elif isinstance(n, ast.Return) and fn == "crud.py" and fn_nomi(n) == "_taqdir_teskari":
                hedef = n
            if hedef is not None and fn == "crud.py":
                for d in ast.walk(hedef):
                    if isinstance(d, ast.Call) and _nom(d) in XABAR_FN:
                        jurnal_ro.append(f"{fn}:{d.lineno} {fn_nomi(d)} {_nom(d)}")
    return miqdor, xom, jurnal_nb, jurnal_ro


_MQ, _XOM, _JNB, _JRO = _skan()
check("S1 xabar / jurnal f-stringlarida `{x:g}` / `{x:.Nf}` miqdor YO'Q (ichki belgi, konsol, butun foiz — tashqarida)", not _MQ, _MQ[:12])
check("S2 formatlagichsiz miqdor birlik yonida YO'Q (to'lov izohi «(3.0 dona)», Telegram «*{int(loy_kg)} kg*»)", not _XOM, _XOM[:8])
check("S3 «Faoliyat jurnali» chaqiruvida bo'linmas bo'shliqli yordamchi (`_miqdor_matn`, `xabar_son`, `son_korinish`) YO'Q", not _JNB, _JNB[:8])
check("S4 brak taqdiri jurnali / qaytarish o'chirilgani `_qator` / `_taqdir_teskari` — `_miqdor_jurnal` (bo'linmas yordamchi YO'Q)",
      not _JRO, _JRO[:10])
_tq = _src(getattr(crud, "_taqdir_qolla", None))
check("S5 loy tuzatishi: `services.deduct_loy_ingredients` XABAR ro'yxati jurnalga bo'linmas bo'shliqsiz qo'shiladi",
      re.search(r"join\(_log\)\}\)\"\.replace\(\"\\u00a0\", \" \"\)", _tq) is not None, re.findall(r".*join\(_log\).*", _tq))
check("S6 ichki belgilar O'ZGARMAGAN: `[WRITEOFF:{remaining:.0f}]`, `loy_kg={actual_loy:.4f}`, «Kam» kaliti `f\"{float(v):g}\"`",
      'f" [WRITEOFF:{remaining:.0f}]"' in oqi("main.py") and 'f", loy_kg={actual_loy:.4f}"' in oqi("services.py")
      and 'return f"{float(v):g}"' in oqi("models.py"))

# ── U. Yordamchilar va xabar matnlari ───────────────────────────────────────────────────────────────────────────
section("U: `_miqdor_matn` / `_miqdor_jurnal` / `_son_uz`, xabar matnlari, yaxlitlash ekvivalentligi")
_mm, _mj = crud._miqdor_matn, getattr(crud, "_miqdor_jurnal", None)
check("U1 `crud._miqdor_matn` (xabar): «1 234,5» (bo'linmas), «3,333», «6», «0», «1 000 000» (eksponentsiz), «-1 234,568», None → «—»",
      [_sinab(_mm, x) for x in (1234.5, 3.33333, 6.0, -0.0001, 1e6, -1234.5678, None)]
      == [nb("1 234,5"), "3,333", "6", "0", nb("1 000 000"), nb("-1 234,568"), "—"],
      [_sinab(_mm, x) for x in (1234.5, 3.33333, 6.0, -0.0001, 1e6, -1234.5678, None)])
check("U2 `crud._miqdor_jurnal` (jurnal): «1 234,5», «1 000 000», «2,25» — ODDIY bo'shliq, bo'linmas YO'Q",
      _mj is not None and [_mj(1234.5), _mj(1e6), _mj(2.25)] == ["1 234,5", "1 000 000", "2,25"],
      _mj and [_mj(1234.5), _mj(1e6), _mj(2.25)])
random.seed(193)
_qiymat = [random.choice([random.uniform(-1e6, 1e6), round(random.uniform(0, 1e4), 3) + 0.0005, round(random.uniform(0, 1e3), 2),
                          random.uniform(0, 1)]) for _ in range(3000)] + [0.0005, 1.0005, 2.5, -2.5, 1234567.5, 999999.9995]


def _eski(x, k):
    s = f"{x:.{k}f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def _yangi_norm(s):
    return s.replace(NB, "").replace(" ", "").replace(",", ".")


_f3 = [x for x in _qiymat if _yangi_norm(_mm(x)) != _eski(x, 3)]
check("U3 yaxlitlash O'ZGARMAGAN: `_miqdor_matn` raqamlari eski `:.3f` bilan AYNAN (3006 qiymat, .0005 holatlari ham)", not _f3, _f3[:5])
_fk = [x for x in _qiymat[:1500] if not (crud.xabar_son(x, 3) == services.son_korinish(x, 3) == _mm(x)
                                         and _sinab(_mj, x) == _mm(x).replace(NB, " "))]
check("U4 BITTA miqdor qoidasi: `crud.xabar_son(x, 3)` (main) = `services.son_korinish(x, 3)` = `_miqdor_matn`; `_miqdor_jurnal` — o'sha, "
      "faqat oddiy bo'shliq (1500 qiymat)", not _fk, _fk[:5])
check("U5 `services._son_uz` (foiz matni): «-156,4», «12», «0,35», «5,01», «1 234,5», «1 000 000» (ilgari «1234,5», «1e+06»)",
      [services._son_uz(x) for x in (-156.4, 12.0, 0.35, 5.01, 1234.5, 1e6)]
      == ["-156,4", "12", "0,35", "5,01", nb("1 234,5"), nb("1 000 000")], [services._son_uz(x) for x in (-156.4, 12.0, 0.35, 5.01, 1234.5, 1e6)])
_m1 = crud.material_qoldiq_xabari(SimpleNamespace(stock_quantity=1234.5678, item_name="T193 Akril", unit="kg"))
_m2 = crud.material_qoldiq_xabari(SimpleNamespace(stock_quantity=-12.5, item_name="T193 Akril", unit="kg"))
check("U6 material o'chirish rad xabari: «omborda hali 1 234,568 kg bor», «qoldig'i manfiy (-12,5 kg)» (sahifadagi `sonKor(q, 3)` kabi)",
      _m1.startswith(nb("«T193 Akril» omborda hali 1 234,568 kg bor — ")) and _m2.startswith("«T193 Akril» qoldig'i manfiy (-12,5 kg) — "),
      (_m1, _m2))


def _fp(**k):
    d = dict(name="T193 Karniz", unit="metr", quantity=0.0, reserved_quantity=0.0, production_status=ProductionStatus.READY,
             source=StockSource.PRODUCED)
    d.update(k)
    return SimpleNamespace(**d)


_x7 = _sinab(crud._tm_minus_rad_xabari, _fp(quantity=-1234.5), "sotib")
check("U7 minusdagi mahsulot: «qoldiq minusda (-1 234,5 metr — 1 234,5 metr buyurtmalarga qarz, hali ishlab chiqarilmagan) — sotib bo'lmaydi.»",
      str(_x7).startswith(nb("T193 Karniz: qoldiq minusda (-1 234,5 metr — 1 234,5 metr buyurtmalarga qarz, hali ishlab chiqarilmagan) — "
                             "sotib bo'lmaydi. ")), _x7)
_x8 = _sinab(crud._tm_ushlangan_xabari, _fp(), 1500.25, 200.0, 2000.0)
check("U8 guruh qarzi ushlanadi: «(200 metr buyurtmaga qarz) … sotsa bo'ladi faqat 1 300,25 metr, 2 000 sota olmaysiz»",
      _x8 == nb("T193 Karniz: shu mahsulotning boshqa partiyasi minusda (200 metr buyurtmaga qarz) — bo'sh qoldiq avval qarzni yopadi: "
                "sotsa bo'ladi faqat 1 300,25 metr, 2 000 sota olmaysiz"), _x8)
_x9 = _sinab(crud._fp_band_xabari, _fp(quantity=1500.0, reserved_quantity=1000.5), 1200.0)
check("U9 band sababli sotuv rad: «omborda 1 500 metr, shundan 1 000,5 metr buyurtmaga band — sotsa bo'ladi faqat 499,5 metr, 1 200 …»",
      _x9 == nb("T193 Karniz: omborda 1 500 metr, shundan 1 000,5 metr buyurtmaga band — sotsa bo'ladi faqat 499,5 metr, 1 200 sota "
                "olmaysiz. Band mahsulotni sotish uchun avval «Bandni bekor qilish»"), _x9)
_x10 = _sinab(crud._tm_kerak_tekshir, _fp(quantity=1500.0, reserved_quantity=1000.5), 2000.0)
check("U10 buyurtmaga band mahsulot (rad): «omborda 1 500 metr, shundan 1 000,5 metr … bo'sh 499,5 metr, kerak 2 000 metr.»",
      isinstance(_x10, tuple) and _x10[1] is None and _x10[0] == nb(
          "🏭 T193 Karniz: omborda 1 500 metr, shundan 1 000,5 metr boshqa buyurtmaga band — bo'sh 499,5 metr, kerak 2 000 metr. Band "
          "mahsulotga tegib bo'lmaydi: yetmaganini ishlab chiqaring yoki band buyurtmada «Bandni bekor qilish»"), _x10)
_x11 = _sinab(crud._tm_kerak_tekshir, _fp(quantity=1500.0), 2000.0, 100.25)
check("U11 kam (tasdiq bilan): «omborda 1 500 metr, kerak 2 000 metr (… yana 100,25 metr olinadi — yetmagani 399,75 metr)»",
      isinstance(_x11, tuple) and _x11[0] is None and _x11[1] == nb(
          "🏭 T193 Karniz: omborda 1 500 metr, kerak 2 000 metr (shu mahsulotning boshqa partiyalaridan yana 100,25 metr olinadi — "
          "yetmagani 399,75 metr)"), _x11)
_x12 = _sinab(production_service._mrp_kerak_izoh, {"band": 1234.5, "topshirilgan": 2.25, "ombordan": True})
check("U12 MRP rad izohi: «allaqachon 1 234,5 band qilingan, 2,25 topshirilgan, …» (modul qoidasi — 4 xona)",
      _x12 == nb("allaqachon 1 234,5 band qilingan, 2,25 topshirilgan, detal buyurtma yaratilganda ombordagi tayyor mahsulotdan olingan"),
      _x12)

# ── D. Ilovaning o'z API si ─────────────────────────────────────────────────────────────────────────────────────
# mutatsiya yurishini qisqartirish (`work/k193/mut193.py`): T193_D=0 — D bo'limi YURMAYDI (S, U — doim)
D_YUR = os.environ.get("T193_D", "1") != "0"
if D_YUR:
    section("D: ilova — chiqim, material, sotuv, brak, qo'shish, «Kam», Telegram, Bosh sahifa, buyurtma, yuk xati, qaytarish, brak taqdiri")
    TG = []
    _asl_tg, _asl_qp = main._send_telegram, main._send_telegram_to_qoplamachi
    main._send_telegram = lambda matn, company_id=None, *a, **k: TG.append(matn)
    main._send_telegram_to_qoplamachi = lambda matn, company_id=None, *a, **k: None
    _db = SessionLocal()
    with contextlib.redirect_stdout(io.StringIO()):
        auth.create_user(_db, "t193_a", "Parol123!", UserRole.ADMIN, "T193 A", company_id=1)
    _p = Inventory(company_id=1, item_name="T193 Penoplast", unit="blok", stock_quantity=0.5, price_per_unit=500_000,
                   volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
    _mat = Inventory(company_id=1, item_name="T193 Akril", unit="kg", stock_quantity=1234.5, min_stock=2000.25, price_per_unit=25_000,
                     category="Boshqa")
    _mat2 = Inventory(company_id=1, item_name="T193 Gips", unit="kg", stock_quantity=1500.5, min_stock=0, price_per_unit=1_000,
                      category="Boshqa")
    _pr = Project(company_id=1, client_name="T193 Mijoz", project_name="T193 Loyiha", total_budget=0, total_paid=0)
    _fp1 = FinishedProduct(company_id=1, name="T193 Karniz", quantity=1234.5, unit="metr", cost_price=1_234_500,
                           production_status=ProductionStatus.READY, unit_price=50_000, unit_volume_m3=0.0001, unit_loy_kg=0)
    _fp2 = FinishedProduct(company_id=1, name="T193 Panel", quantity=3000, unit="metr", cost_price=3_000_000,
                           production_status=ProductionStatus.READY, unit_price=50_000)
    _fp3 = FinishedProduct(company_id=1, name="T193 Ustun", quantity=1234.5, unit="metr", cost_price=1_234_500,
                           production_status=ProductionStatus.READY, unit_price=50_000)
    _db.add_all([_p, _mat, _mat2, _pr, _fp1, _fp2, _fp3])
    _db.commit()
    INV, MAT, MAT2, PRJ, FP1, FP2, FP3 = _p.id, _mat.id, _mat2.id, _pr.id, _fp1.id, _fp2.id, _fp3.id
    _fp1.penoplast_id = INV                      # «Yana ishlab chiqarish» penoplastni shu materialdan yechadi
    _db.commit()
    _db.close()
    CL = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    CL.post("/login", data={"username": "t193_a", "password": "Parol123!"}, follow_redirects=False)

    def js(r):
        try:
            return r.json()
        except Exception:                      # noqa: BLE001
            return {}

    def det(r):
        d = js(r).get("detail")
        return d if isinstance(d, dict) else {"message": d}

    def jurnal(**f):
        s = SessionLocal()
        try:
            q = s.query(ActivityLog).filter(ActivityLog.company_id == 1)
            for k, v in f.items():
                q = q.filter(getattr(ActivityLog, k) == v)
            return [(a.entity_label, a.old_value, a.new_value) for a in q.order_by(ActivityLog.id).all()]
        finally:
            s.close()

    r = CL.post(f"/api/inventory/{MAT}/stock", json={"quantity_change": -2000, "reason": "T193 sinov"})
    check("D1 qo'lda chiqim qoldiqdan ko'p → 400: «T193 Akril: omborda 1 234,5 kg bor — 2 000 kg chiqim qilib bo'lmaydi»",
          lambda: r.status_code == 400 and js(r).get("detail") == nb("T193 Akril: omborda 1 234,5 kg bor — 2 000 kg chiqim qilib bo'lmaydi"),
          (r.status_code, r.text[:300]))
    r = CL.delete(f"/api/inventory/{MAT}")
    check("D2 qoldig'i bor materialni o'chirish → 409: ««T193 Akril» omborda hali 1 234,5 kg bor — …»",
          lambda: r.status_code == 409 and str(js(r).get("detail")).startswith(nb("«T193 Akril» omborda hali 1 234,5 kg bor — ")),
          (r.status_code, r.text[:300]))
    r = CL.post("/api/finished/sell", json={"finished_product_id": FP1, "quantity": 2000, "unit_price": 5_000_000, "payment_method": "naqd"})
    check("D3 sotuv qoldiqdan ko'p → 400: «Omborda faqat 1 234,5 metr bor, 2 000 sota olmaysiz»",
          lambda: r.status_code == 400 and det(r)["message"] == nb("Omborda faqat 1 234,5 metr bor, 2 000 sota olmaysiz"),
          (r.status_code, r.text[:300]))
    r = CL.post("/api/finished/sell-batch", json={"items": [{"finished_product_id": FP1, "quantity": 2000, "unit_price": 5_000_000}],
                                                   "payment_method": "naqd"})
    check("D4 savat qoldiqdan ko'p → 400: «T193 Karniz: sotish mumkin faqat 1 234,5 metr bor, 2 000 sota olmaysiz»",
          lambda: r.status_code == 400 and det(r)["message"] == nb("T193 Karniz: sotish mumkin faqat 1 234,5 metr bor, 2 000 sota olmaysiz"),
          (r.status_code, r.text[:300]))
    r = CL.post("/api/finished/loss", json={"finished_product_id": FP1, "quantity": 2000, "brak_sabab": "boshqa"})
    check("D5 brak qoldiqdan ko'p → 400: «Omborda faqat 1 234,5 metr bor, 2 000 kamaytira olmaysiz»",
          lambda: r.status_code == 400 and det(r)["message"] == nb("Omborda faqat 1 234,5 metr bor, 2 000 kamaytira olmaysiz"),
          (r.status_code, r.text[:300]))
    r = CL.post(f"/api/finished/{FP1}/add", json={"quantity": 1000.25})
    _jq = [x[2] for x in jurnal(action="produced", entity_type="finished_product", entity_id=FP1)]
    check("D6 «Yana ishlab chiqarish»: javob «+1 000,25 metr qo'shildi» (bo'linmas); jurnal «+1 000,25 metr qo'shildi, jami: 2 234,75 metr» "
          "(ODDIY bo'shliq)",
          lambda: r.status_code == 200 and js(r).get("message") == nb("+1 000,25 metr qo'shildi")
          and _jq == ["+1 000,25 metr qo'shildi, jami: 2 234,75 metr"], (r.status_code, r.text[:300], _jq))
    _s = SessionLocal()
    try:
        _q = crud.audit_jurnali_sahifasi(_s, 1, matn="2 234,75")
        _topildi = [a.entity_id for a in _q["yozuvlar"]]
    finally:
        _s.close()
    _s = SessionLocal()
    try:
        _hs = [h.reason or "" for h in _s.query(InventoryMovement).filter(InventoryMovement.inventory_id == INV).all()]
    finally:
        _s.close()
    check("D6b ombor harakati sababi (sahifada ko'rinadi — xabar qoidasi): «Ishlab chiqarish (+1 000,25): T193 Karniz» (ilgari «+1000.25»); "
          "javobdagi ro'yxat «T193 Penoplast: -0,1 blok» (ilgari «-0.10 blok»)",
          nb("Ishlab chiqarish (+1 000,25): T193 Karniz") in _hs and "T193 Penoplast: -0,1 blok" in (js(r).get("inventory_log") or []),
          (_hs, js(r).get("inventory_log")))
    check("D7 «Faoliyat jurnali» qidiruvi oddiy bo'shliq bilan («2 234,75») — ishlab chiqarish yozuvini TOPADI", FP1 in _topildi, _topildi)
    r = CL.post(f"/api/finished/{FP1}/reduce", json={"quantity": 0.25, "brak_sabab": "boshqa"})
    check("D8 kamaytirish (brak, API): «-0,25 metr chiqarildi (brak)»",
          lambda: r.status_code == 200 and js(r).get("message") == "-0,25 metr chiqarildi (brak)", (r.status_code, r.text[:300]))
    r1 = CL.put(f"/api/finished/{FP3}/kam-chegara", json={"chegara": 1500.5})
    r2 = CL.put(f"/api/finished/{FP3}/kam-chegara", json={"chegara": 2000})
    _jk = [(x[1], x[2]) for x in jurnal(action="updated", entity_type="finished_product", entity_id=FP3)]
    check("D9 «Kam» chegarasi jurnali: «—» → «1 500,5 metr» → «2 000 metr» (ODDIY bo'shliq; ilgari «1500.5 metr»)",
          r1.status_code == 200 and r2.status_code == 200 and _jk == [("—", "1 500,5 metr"), ("1 500,5 metr", "2 000 metr")],
          (r1.status_code, r1.text[:200], _jk))
    r = CL.delete(f"/api/finished/{FP3}")
    check("D10 qoldig'i bor tayyor mahsulotni o'chirish → 400: «Bu mahsulotda hali 1 234,5 metr qoldiq bor — …»",
          lambda: r.status_code == 400 and str(js(r).get("detail")).startswith(nb("Bu mahsulotda hali 1 234,5 metr qoldiq bor — ")),
          (r.status_code, r.text[:300]))
    TG.clear()
    r = CL.post("/api/inventory/low-stock-alert")
    _tg = "\n".join(TG)
    check("D11 kam qoldiq Telegrami: «T193 Akril: 1 234,5 kg qoldi (min: 2 000,25, yetishmaydi: 765,75)» (ilgari «1234.5 … min: 2000 … 765.8»)",
          r.status_code == 200 and nb("T193 Akril: 1 234,5 kg qoldi (min: 2 000,25, yetishmaydi: 765,75)") in _tg,
          (r.status_code, r.text[:200], _tg[:500]))
    TG.clear()
    r = CL.post("/api/inventory/full-stock-report")
    _tg = "\n".join(TG)
    check("D12 ombor hisoboti Telegrami: «T193 Akril: 1 234,5 kg», «T193 Gips: 1 500,5 kg»",
          r.status_code == 200 and nb("T193 Akril: 1 234,5 kg") in _tg and nb("T193 Gips: 1 500,5 kg") in _tg
          and not [q for q in _tg.split("\n") if "T193" in q and re.search(r"\d\.\d", q)],
          (r.status_code, _tg[:600]))
    _s = SessionLocal()
    try:
        _ogoh = [a.get("text", "") for a in services.get_business_alerts(_s, 1)]
        _vaz = [t.get("text", "") for t in services.get_today_tasks(_s, 1)]
    finally:
        _s.close()
    check("D13 Bosh sahifa ogohlantirishi: «Omborda T193 Akril kamaymoqda (1 234,5 kg qoldi)»",
          nb("Omborda T193 Akril kamaymoqda (1 234,5 kg qoldi)") in _ogoh, _ogoh)
    check("D14 «Bugungi vazifalar»: «T193 Akril kam qolgan (1 234,5 kg)»", nb("T193 Akril kam qolgan (1 234,5 kg)") in _vaz, _vaz)

    def buyurtma(nom, miqdor=3, tasdiq=True):
        t = {"project_id": PRJ, "order_type": "product", "loy_kg": 0, "items": [
            {"name": f"T193 panel {nom}", "category": "panel", "width": 30, "thickness": 5, "quantity": miqdor, "unit_price": 1_234_567,
             "is_coated": False, "penoplast_id": INV}]}
        r = CL.post("/api/orders", json=t, params={"confirm_shortage": "true"} if tasdiq else None)
        if not tasdiq:
            return r
        assert r.status_code == 200, (r.status_code, r.text[:300])
        s = SessionLocal()
        try:
            o = s.get(Order, r.json()["id"])
            return o.id, o.order_number, o.items[0].id, o.items[0].delivery_unit, t
        finally:
            s.close()

    r = buyurtma("yetishmaydi", miqdor=400, tasdiq=False)
    _yt = [x for x in (det(r).get("shortages") or []) if "T193 Penoplast" in str(x)]
    check("D15 buyurtma — penoplast yetishmaydi (409): «T193 Penoplast: kerak 6 blok, qoldi 0,4 blok» (0,399975 — 3 xona; nuqta YO'Q)",
          r.status_code == 409 and _yt == ["T193 Penoplast: kerak 6 blok, qoldi 0,4 blok"], (r.status_code, r.text[:400]))
    r = buyurtma("kam farq", miqdor=28, tasdiq=False)
    _yt = [x for x in (det(r).get("shortages") or []) if "T193 Penoplast" in str(x)]
    check("D15b kerak qoldiqdan ozgina ko'p: «kerak 0,42 blok, qoldi 0,4 blok» (ilgari `.1f` — «kerak 0.4 blok, qoldi 0.4 blok», bir xil)",
          r.status_code == 409 and _yt == ["T193 Penoplast: kerak 0,42 blok, qoldi 0,4 blok"], (r.status_code, r.text[:400]))
    O1, N1, I1, B1, T1 = buyurtma("bir")
    r = CL.post("/api/deliveries", json={"order_id": O1, "items": [{"order_item_id": I1, "quantity": 4.5}]})
    check("D16 yuk xati qolgandan ko'p → rad: «T193 panel bir: 4,5 … berilmoqchi, lekin qoldi 3 …»",
          lambda: r.status_code in (400, 409) and f"T193 panel bir: 4,5 {B1} berilmoqchi, lekin qoldi 3 {B1}" in str(js(r)),
          (r.status_code, r.text[:300]))
    TG.clear()
    r = CL.post("/api/deliveries", json={"order_id": O1, "items": [{"order_item_id": I1, "quantity": 1.5}]})
    _tg = "\n".join(TG)
    check("D17 yuk xati Telegrami: «• T193 panel bir: 1,5 …» (ilgari «1.5»)",
          r.status_code == 200 and f"• T193 panel bir: 1,5 {B1}" in _tg, (r.status_code, r.text[:200], _tg[:400]))
    r = CL.post("/api/returns", json={"order_id": O1, "order_item_id": I1, "item_name": "T193 panel bir", "quantity": 4.5, "unit": B1,
                                      "reason": "Ortiqcha", "refund_amount": 0, "to_stock": True, "notes": None, "coating_applied": False})
    check("D18 qaytarish buyurtmadagidan ko'p → 400: «Buyurtmada 3 … bor, 4,5 qaytarib bo'lmaydi»",
          lambda: r.status_code == 400 and f"Buyurtmada 3 {B1} bor, 4,5 qaytarib bo'lmaydi" in str(js(r).get("detail")),
          (r.status_code, r.text[:300]))
    O2, N2, I2, B2, T2 = buyurtma("ikki")
    r0 = CL.post("/api/payments", json={"order_id": O2, "amount": 3_703_701})
    r = CL.post("/api/returns", json={"order_id": O2, "order_item_id": I2, "item_name": "T193 panel ikki", "quantity": 2.5, "unit": B2,
                                      "reason": "Ortiqcha", "refund_amount": 1_000, "to_stock": False, "notes": None, "coating_applied": False})
    _rid = js(r).get("id")
    r = CL.post(f"/api/returns/{_rid}/refund")
    _s = SessionLocal()
    try:
        _iz = [p.notes or "" for p in _s.query(Payment).filter(Payment.order_id == O2, Payment.amount < 0).all()]
    finally:
        _s.close()
    check("D19 qaytarish puli to'lov izohi: «Qaytarilgan mahsulot uchun pul qaytarildi: T193 panel ikki (2,5 …)» (ilgari «(2.5 …)»)",
          r0.status_code == 200 and r.status_code == 200 and any(f"pul qaytarildi: T193 panel ikki (2,5 {B2})" in z for z in _iz),
          (r0.status_code, r.status_code, r.text[:300], _iz))
    TG.clear()
    r = CL.post(f"/api/orders/{O2}/coating-notify", params={"loy_kg": "12.94"})
    _tg = "\n".join(TG)
    check("D20 qoplamachi Telegrami: «🧱 Loy tayyorlang: *12,94 kg*» (ilgari `int()` — «*12 kg*»)",
          r.status_code == 200 and "🧱 Loy tayyorlang: *12,94 kg*" in _tg, (r.status_code, r.text[:200], _tg[:400]))
    r = CL.post("/api/finished/loss", json={"finished_product_id": FP2, "quantity": 1234.5, "brak_sabab": "boshqa",
                                            "taqdir": {"taqdir": "ikkinchi_nav", "narx": 12_345.5}})
    _jt = [x[2] or "" for x in jurnal(action="brak_taqdir")]
    check("D21 brak taqdiri jurnali: «2-nav: … +1 234,5 metr (narx 12 345,5)» (ODDIY bo'shliq; ilgari «+1234.5 metr (narx 12345.5)»)",
          r.status_code == 200 and any("+1 234,5 metr (narx 12 345,5)" in x for x in _jt) and not any(NB in x for x in _jt),
          (r.status_code, r.text[:300], _jt))
    r = CL.post("/api/finished/loss", json={"finished_product_id": FP2, "quantity": 1, "brak_sabab": "boshqa",
                                            "taqdir": {"taqdir": "tuzatildi", "materiallar": [{"inventory_id": MAT2, "miqdor": 5000}]}})
    check("D22 brak tuzatish xomashyosi yetmaydi → 400: «T193 Gips yetishmayapti! Kerak: 5 000 kg, omborda: 1 500,5 kg» (bo'linmas)",
          lambda: r.status_code == 400 and nb("T193 Gips yetishmayapti! Kerak: 5 000 kg, omborda: 1 500,5 kg") in str(det(r)["message"]),
          (r.status_code, r.text[:300]))
    r = CL.post("/api/finished/loss", json={"finished_product_id": FP2, "quantity": 1, "brak_sabab": "boshqa",
                                            "taqdir": {"taqdir": "tuzatildi", "materiallar": [{"inventory_id": MAT2, "miqdor": 1000.25}]}})
    _jt = [x[2] or "" for x in jurnal(action="brak_taqdir")]
    check("D23 brak tuzatish jurnali: «tuzatish: T193 Gips −1 000,25 kg» (ODDIY bo'shliq)",
          r.status_code == 200 and any("tuzatish: T193 Gips −1 000,25 kg" in x for x in _jt), (r.status_code, r.text[:300], _jt))
    main._send_telegram, main._send_telegram_to_qoplamachi = _asl_tg, _asl_qp

print(f"\n{REJIM}NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
