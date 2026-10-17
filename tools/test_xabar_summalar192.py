#!/usr/bin/env python3
"""
test_xabar_summalar192.py — kech151 (zip 192): server yozadigan MATNLARDAGI pul summalari BITTA son qoidasida.

NIMA UCHUN KERAK (egasi tanlovi 17.10 «Xabarlardagi summalar»; O'LCHANGAN — `work/k192/skan192.py` (AST: ildiz *.py dagi hamma `:,`
format, `"{:,}".format`, `format(x, ",")`, `.replace(",", " ")`) va `work/k192/skan192b.py` («so'm» yonidagi formatlagichsiz son), zip 191 kodi):
  V  ~30 xabarda VERGUL ming ajratgich — «Kiritilgan summa (5,000,000 so'm) qarzdan (3,703,701 so'm) 1,296,299 so'mga ko'p», qaytarish /
     ortiqcha to'lov xatolari, «Tayyor» yakuni, «juda past» narx, sovg'a bosqichi, yuk xati to'lovi, Telegram keshbek; jurnal: to'lov
     o'chirildi «3,553,701 so'm · …», ortiqcha to'lov qaytarildi «1,296,299.00 so'm», brak bekori «(450,000 so'm)».
  B  ajratgichsiz — «Qolgan 150000 so'm chegirmaga», «Buyurtma summasi 3703701 → 1234567», «0.01 so'm», «1234.5 so'm yo'nalishga
     bog'lanmadi», O'chirilganlar sahifasi «3703701 so'm».
  O  `.replace(",", " ")` — oddiy bo'shliq (xabarda qator oxirida bo'linadi), gapdagi vergul ham yo'qolardi («Jami: … so'm  1 ta
     detal», kirim bekori «… so'm  to'lov»); nuqtali kasr «12 500.5», «tannarx 1 234.56 so'm».
QOIDA: foydalanuvchi KO'RADIGAN xabar — `crud.xabar_son` / `services.son_korinish` (bo'linmas bo'shliq, kasr — vergul, ortiqcha nolsiz);
«Faoliyat jurnali» — `crud.audit_son` (o'sha qoida, ming ajratgich ODDIY bo'shliq: jurnal «Qidiruv» i va tannarx niqobi `[0-9 .,]`).
Yaxlitlash o'zgarmaydi (`:,.0f` → kasr 0). PDF va `erp_backup_tekshiruv.py` — ataylab tashqarida.
BO'LIMLAR: S — manba (AST); U — yordamchilar va istisno matnlari (yaxlitlash ekvivalentligi ham); D — ilovaning O'Z API si (to'lov,
yuk xati, kechirish, ortiqcha qaytarish, qaytarish, «Tayyor», ta'minotchi, tayyor mahsulot, savat, jurnal + qidiruv, O'chirilganlar),
Telegram matni (yuborish ushlanadi); T — tannarx niqobi yangi jurnal matnini ham yashiradi.
REJIM: SQLite (standart), `TENANT_FILTER=1` ham; `PG_URL=postgresql://postgres@127.0.0.1:5432` — PostgreSQL. Asl kodga (zip 191)
qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_xabar_summalar192.py
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
from datetime import datetime

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "xabar_summalar192_test"
_T = tempfile.mkdtemp(prefix="xabar192_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'xabar192.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import crud                                        # noqa: E402
import services                                    # noqa: E402
import production_service                          # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import (UserRole, Inventory, Project, Order, Payment, ActivityLog, FinishedProduct,   # noqa: E402
                    ProductionStatus)
from fastapi.testclient import TestClient          # noqa: E402

REJIM = ("[PG] " if PG_URL else "") + ("[TF1] " if os.environ.get("TENANT_FILTER") == "1" else "")
OK = FAIL = 0
FAILED = []
NB = " "


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
    """«1 500 000» (oddiy bo'shliq bilan yozilgan kutilgan qiymat) → bo'linmas bo'shliqli ko'rinish."""
    return re.sub(r"(?<=\d) (?=\d)", NB, s)


# ── S. Manba (AST) ────────────────────────────────────────────────────────────────────────────────────────────
section("S: server matnlari — vergulli / ajratgichsiz / nuqtali summa YO'Q (AST)")
TASHQARIDA = {"delivery_pdf.py", "finance_pdf.py", "pdf_service.py", "erp_backup_tekshiruv.py"}   # PDF (reportlab), konsol skripti
NAMUNA = {("services.py", "son_korinish"), ("main.py", "_son_filtri")}   # qoidaning o'zi (`son_korinish`, Jinja `|son`)


def _skan():
    vergul, somsiz = [], []
    for fn in sorted(os.listdir(ROOT)):
        if not fn.endswith(".py") or fn in TASHQARIDA:
            continue
        src = oqi(fn)
        tree = ast.parse(src)
        ota = {}
        for n in ast.walk(tree):
            for c in ast.iter_child_nodes(n):
                ota[c] = n

        def fn_nomi(n):
            while n in ota:
                n = ota[n]
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    return n.name
            return "<modul>"

        for n in ast.walk(tree):
            joy = None
            if isinstance(n, ast.FormattedValue) and isinstance(n.format_spec, ast.JoinedStr) and any(
                    isinstance(v, ast.Constant) and "," in str(v.value) for v in n.format_spec.values):
                joy = "f-string ':,'"
            elif isinstance(n, ast.Call):
                f = n.func
                if isinstance(f, ast.Attribute) and f.attr == "format" and isinstance(f.value, ast.Constant) \
                        and isinstance(f.value.value, str) and re.search(r"\{[^{}]*:[^{}]*,[^{}]*\}", f.value.value):
                    joy = "'{:,}'.format"
                elif isinstance(f, ast.Name) and f.id == "format" and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant) \
                        and "," in str(n.args[1].value):
                    joy = "format(x, ',')"
                elif isinstance(f, ast.Attribute) and f.attr == "replace" and len(n.args) == 2 and all(
                        isinstance(a, ast.Constant) for a in n.args) and n.args[0].value == ",":
                    joy = "replace(',')"
            if joy and (fn, fn_nomi(n)) not in NAMUNA:
                vergul.append(f"{fn}:{n.lineno} {fn_nomi(n)} {joy}")
            if isinstance(n, ast.JoinedStr):
                matn = "".join(v.value for v in n.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
                if "so'm" not in matn:
                    continue
                for v in n.values:
                    if not isinstance(v, ast.FormattedValue):
                        continue
                    # spec — format_spec ning O'Z matni (`get_source_segment` Python versiyasiga qarab «:g» yoki None beradi — mut192 M29)
                    spec = "".join(str(c.value) for c in (v.format_spec.values if isinstance(v.format_spec, ast.JoinedStr) else [])
                                   if isinstance(c, ast.Constant))
                    ifoda = ast.get_source_segment(src, v.value) or ""
                    if re.fullmatch(r"\.\d+f|g|d", spec) or re.match(r"\s*(round|int|float)\(", ifoda):
                        somsiz.append(f"{fn}:{v.lineno} {fn_nomi(v)} {{{ifoda}:{spec}}}")
    return vergul, somsiz


try:
    VERGUL, SOMSIZ = _skan()
except Exception as _e:                    # noqa: BLE001
    VERGUL, SOMSIZ = [f"skan xato: {_e}"], [f"skan xato: {_e}"]
check("S1 server kodida (PDF / konsol skriptidan tashqari) vergulli ming ajratgich YO'Q: `:,` format, `'{:,}'.format`, `format(x, ',')`, "
      "`.replace(',', …)` — faqat qoidaning o'zi (`services.son_korinish`, `main._son_filtri`)", not VERGUL, VERGUL)
check("S2 «so'm» yozilgan f-stringlarda formatlagichsiz son YO'Q (`:.0f`, `:.2f`, `:g`, xom `round(…)` / `int(…)`)", not SOMSIZ, SOMSIZ)
_tp = [f"{f}: {m}" for f in sorted(os.listdir(os.path.join(ROOT, "templates"))) if f.endswith(".html")
       for m in re.findall(r"\{\{[^{}]*\}\}\s*so'm", oqi(os.path.join("templates", f))) if "|son" not in m]
check("S3 shablonlarda «{{ … }} so'm» — hammasi `|son` bilan (O'chirilganlar sahifasidagi «|round|int» ham)", not _tp, _tp)
_m = oqi("main.py")
check("S4 ichki `[WRITEOFF:…]` belgisi O'ZGARMAGAN (izohdan `[\\d.]+` bilan o'qiladi — bo'shliq / vergul bo'lmasin)",
      'f" [WRITEOFF:{remaining:.0f}]"' in _m and r"\s*\[WRITEOFF:[\d.]+\]" in _m)
_AS, _XS = _src(getattr(crud, "audit_son", None)), _src(getattr(crud, "xabar_son", None))
check("S5 `crud.audit_son` — `son_korinish` + bo'linmas bo'shliq → ODDIY (jurnal qidiruvi); `crud.xabar_son` — `son_korinish`",
      "son_korinish(x, kasr)" in _AS and 'replace("\\u00a0", " ")' in _AS and "son_korinish(x, kasr)" in _XS, (_AS[:200], _XS[:200]))
_PS = oqi("production_service.py")
check("S6 ishlab chiqarish jurnali `_son110` — `crud.audit_son` (kasr vergul), xabardagi miqdor `_miqdor_matn` — `son_korinish`",
      "return crud.audit_son(x, 2)" in _src(production_service._son110)
      and "son_korinish(x, 4)" in _src(production_service._miqdor_matn), _src(production_service._son110)[-200:])
_KESH = _src(main._usta_boti_javobi) if hasattr(main, "_usta_boti_javobi") else _m
check("S7 Telegram usta keshbegi — `son_korinish` (ilgari `{int(…):,}` — «1,234,567 so'm»)",
      "Hisoblangan keshbek: {services.son_korinish(int(info['jami_bonus']), 0)} so'm" in _KESH)

# ── U. Yordamchilar, istisno matnlari, yaxlitlash ekvivalentligi ────────────────────────────────────────────────
section("U: yordamchilar va istisno matnlari")
_aud = getattr(crud, "audit_son", None)
_xab = getattr(crud, "xabar_son", None)


def _sinab(f, *a):
    try:
        return f(*a)
    except Exception as e:                 # noqa: BLE001
        return f"{type(e).__name__}"


check("U1 `audit_son` (jurnal): «1 200 000», «12,5», «1 234,568», kasr 0 — «1 234» / «2» (`:,.0f` kabi), «-1 234,5», None → «0», "
      "matn → o'zi, NaN / cheksiz → «—»; bo'linmas bo'shliq YO'Q",
      [_sinab(_aud, *a) for a in ((1200000,), (12.5,), (1234.5678,), (1234.5, 0), (2.5, 0), (-1234.5, 2), (None,), ("abc",),
                                  (float("nan"),), (float("inf"),))]
      == ["1 200 000", "12,5", "1 234,568", "1 234", "2", "-1 234,5", "0", "abc", "—", "—"],
      [_sinab(_aud, *a) for a in ((1200000,), (12.5,), (1234.5678,), (1234.5, 0), (2.5, 0), (-1234.5, 2), (None,), ("abc",),
                                  (float("nan"),), (float("inf"),))])
check("U2 `xabar_son` (xabar): «1 500 000» (bo'linmas), «0,01», «12 500,5», kasr 0 — «1 234», `services.son_korinish` bilan AYNAN",
      _xab is not None and [_xab(1500000), _xab(0.01, 2), _xab(12500.5, 2), _xab(1234.5)] == [
          nb("1 500 000"), "0,01", nb("12 500,5"), nb("1 234")]
      and all(_xab(v, k) == services.son_korinish(v, k) for v in (0, -5, 1e9, 123.456) for k in (0, 2, 4)))
random.seed(192)
_qiymat = [random.choice([random.uniform(-1e7, 1e7), round(random.uniform(0, 1e7)) + 0.5, round(random.uniform(0, 1e6), 2)])
           for _ in range(3000)] + [0.5, 1.5, 2.5, -2.5, 1234567.5, 461538.75, 999999.995]
_farq0 = [x for x in _qiymat if _xab and _xab(x, 0).replace(NB, "") != f"{x:,.0f}".replace(",", "")]
check("U3 yaxlitlash O'ZGARMAGAN: kasr 0 — `:,.0f` raqamlari bilan AYNAN (3007 qiymat, .5 holatlari ham)", _xab and not _farq0, _farq0[:5])
_farq2 = [x for x in _qiymat if _xab and _xab(x, 2) != f"{x:,.2f}".rstrip("0").rstrip(".").replace(",", NB).replace(".", ",")
          and not (_xab(x, 2) == "0" and f"{x:,.2f}".rstrip("0").rstrip(".") in ("-0", "0"))]
check("U4 kasr 2 — `:,.2f` raqamlari bilan AYNAN (ortiqcha nol olib tashlangan, kasr vergul)", _xab and not _farq2, _farq2[:5])


def _farq_aud():
    return [x for x in _qiymat if _aud(x, 0) != f"{x:,.0f}".replace(",", " ") and not (_aud(x, 0) == "0" and f"{x:,.0f}" == "-0")]


check("U5 jurnal kasr 0 — `:,.0f` + oddiy bo'shliq bilan AYNAN", lambda: _aud and not _farq_aud())
check("U6 ortiqcha to'lov istisnosi: «Ortiqcha to'lov: 1 296 299 so'm qarzdan ko'p»",
      lambda: str(crud.OverpaymentWarning(5_000_000, 3_703_701, 1_296_299)) == nb("Ortiqcha to'lov: 1 296 299 so'm qarzdan ko'p"))
_y1 = _sinab(lambda: str(crud.YukToloviBor("YX-001", [(1, 1_500_000.0)])))
_y2 = _sinab(lambda: str(crud.YukToloviBor("YX-001", [(1, 1_000_000.25), (2, 500_000.25)])))
check("U7 yuk xatiga bog'langan to'lov oynasi: «1 500 000 so'm to'lov», «qarz 1 500 000 so'mga ko'payadi»; ikki to'lov — «jami 1 500 000 so'm»",
      nb("1 500 000 so'm to'lov bog'langan") in _y1 and nb("(qarz 1 500 000 so'mga") in _y1
      and nb("2 ta to'lov (jami 1 500 000 so'm)") in _y2 and not re.search(r"\d,\d{3}", _y1 + _y2), (_y1[:300], _y2[:200]))
_av = _sinab(lambda: crud.AvansOylikdanOrtiq(1_000_000, 1_500_000.4, 500_000.4, 2026, 12).message)
check("U8 avans oylikdan ko'p: «qolgani 1 000 000 so'm, kiritilgan summa 1 500 000 so'm — 500 000 so'mga ko'p»",
      nb("qolgani 1 000 000 so'm, kiritilgan summa 1 500 000 so'm — 500 000 so'mga ko'p") in _av
      and "(Yanvar 2027)" in _av, _av)
check("U9 ta'minotchi xabarlari `crud._som`: «1 234 568» (0,5 — YUQORIGA), «0»",
      [crud._som(1234567.5), crud._som(0.5), crud._som(None)] == [nb("1 234 568"), "1", "0"],
      [crud._som(1234567.5), crud._som(0.5), crud._som(None)])
check("U10 `main.fmt_money` (Telegram, ortiqcha to'lov) va `main._somlar`: bo'linmas bo'shliq",
      [main.fmt_money(1234567.5), main.fmt_money("x"), main._somlar(150000), main._somlar(None)] == [
          nb("1 234 568"), "0", nb("150 000"), "0"], [main.fmt_money(1234567.5), main._somlar(150000)])
check("U11 jurnal: taklif jami — «Jami: 1 500 000 so'm, kelishilgan: 1 400 000 so'm» (ODDIY bo'shliq)",
      lambda: crud._taklif_jami_matni(1_500_000, 1_400_000.4) == "Jami: 1 500 000 so'm, kelishilgan: 1 400 000 so'm")
_pay = SimpleNamespace(amount=3_553_701.0, payment_type=None, payment_method=None, received_by="T192", paid_at=None, notes=None)
check("U12 jurnal: to'lov tafsiloti — «3 553 701 so'm · - · - · qabul qilgan: T192 · sana: -» (ODDIY bo'shliq)",
      lambda: crud._tolov_audit_matni(_pay) == "3 553 701 so'm · - · - · qabul qilgan: T192 · sana: -", _sinab(crud._tolov_audit_matni, _pay))
check("U13 jurnal: avans nomi — «Ali: 205 000 so'm (—)»",
      lambda: crud._avans_jurnal_nomi(SimpleNamespace(name="Ali"), SimpleNamespace(amount=205_000.4, date=None)) == "Ali: 205 000 so'm (—)")
_yop = _sinab(lambda: crud._yopish_natijasi(None, {"paid": 5_000_000, "new_agreed": 3_703_701, "debt": 0}, 4_938_268, False)["message"])
check("U14 «Tayyor» yakuni (topshirilgan qism): «buyurtma summasi 4 938 268 → 3 703 701 so'm», «Mijoz 1 296 299 so'm ORTIQCHA»",
      nb("buyurtma summasi 4 938 268 → 3 703 701 so'm") in _yop and nb("Mijoz 1 296 299 so'm ORTIQCHA") in _yop, _yop)
_yop2 = _sinab(lambda: crud._yopish_natijasi(None, {"paid": 1_000_000, "new_agreed": 3_703_701, "debt": 2_703_701}, 4_938_268, False)["message"])
check("U15 «Tayyor» yakuni — qarz: «Mijoz qarzi: 2 703 701 so'm.»", nb("Mijoz qarzi: 2 703 701 so'm.") in _yop2, _yop2)
_tx = _sinab(production_service._tannarx_sigimi_xatosi, 12_345_678_901_234.567, 1)
check("U16 ishlab chiqarish tannarxi sig'imdan katta: «(12 345 678 901 234,57 so'm)», sig'im «(… so'm)» — vergul / nuqta YO'Q",
      isinstance(_tx, str) and nb("(12 345 678 901 234,57 so'm)") in _tx and not re.search(r"\d[,.]\d{3}", _tx), _tx)
check("U17 xabardagi miqdor (`production_service._miqdor_matn`): «1 234,5» (bo'linmas), «0», «inf»",
      [production_service._miqdor_matn(1234.5), production_service._miqdor_matn(-0.00001), production_service._miqdor_matn(float("inf")),
       production_service._miqdor_matn(-1234.56789)] == [nb("1 234,5"), "0", "inf", nb("-1 234,5679")],
      [production_service._miqdor_matn(1234.5), production_service._miqdor_matn(-1234.56789)])
check("U18 ishlab chiqarish jurnali (`_son110`): «1 234,56», «1 200 000», «12,5» (ODDIY bo'shliq, kasr vergul)",
      [production_service._son110(1234.56), production_service._son110(1200000), production_service._son110(12.5)] == [
          "1 234,56", "1 200 000", "12,5"], [production_service._son110(1234.56)])

# ── D. Ilovaning o'z API si ─────────────────────────────────────────────────────────────────────────────────────
# mutatsiya yurishini qisqartirish (`work/k192/mut192.py`): T192_D=0 — D bo'limi YURMAYDI (S, U, T — doim)
D_YUR = os.environ.get("T192_D", "1") != "0"
if D_YUR:
    section("D: ilova — to'lov, yuk xati, kechirish, qaytarish, «Tayyor», ta'minotchi, sotuv, jurnal, O'chirilganlar, Telegram")
    TG = []
    _asl_tg = main._send_telegram
    main._send_telegram = lambda matn, company_id=None, *a, **k: TG.append(matn)
    _db = SessionLocal()
    with contextlib.redirect_stdout(io.StringIO()):
        auth.create_user(_db, "t192_a", "Parol123!", UserRole.ADMIN, "T192 A", company_id=1)
    _p = Inventory(company_id=1, item_name="T192 Penoplast", unit="blok", stock_quantity=100_000, price_per_unit=500_000,
                   volume_per_unit=1.0, is_penoplast=True, is_default_penoplast=True, category="Penoplast")
    _mat = Inventory(company_id=1, item_name="T192 Akril", unit="kg", stock_quantity=100, price_per_unit=25_000, category="Boshqa")
    _pr = Project(company_id=1, client_name="T192 Mijoz", project_name="T192 Loyiha", total_budget=0, total_paid=0)
    _fp = FinishedProduct(company_id=1, name="T192 Karniz", quantity=100, unit="metr", cost_price=200_000_000,   # jami (1 metr — 2 mln)
                          production_status=ProductionStatus.READY, unit_price=2_500_000)
    _db.add_all([_p, _mat, _pr, _fp])
    _db.commit()
    INV, MAT, PRJ, FP = _p.id, _mat.id, _pr.id, _fp.id
    _db.close()
    CL = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    CL.post("/login", data={"username": "t192_a", "password": "Parol123!"}, follow_redirects=False)


    def js(r):
        try:
            return r.json()
        except Exception:                      # noqa: BLE001
            return {}


    def det(r):
        d = js(r).get("detail")
        return d if isinstance(d, dict) else {"message": d}


    def buyurtma(nom, miqdor=3):
        t = {"project_id": PRJ, "order_type": "product", "loy_kg": 0, "items": [
            {"name": f"T192 panel {nom}", "category": "panel", "width": 30, "thickness": 5, "quantity": miqdor, "unit_price": 1_234_567,
             "is_coated": False, "penoplast_id": INV}]}
        r = CL.post("/api/orders", json=t, params={"confirm_shortage": "true"})
        assert r.status_code == 200, (r.status_code, r.text[:300])
        s = SessionLocal()
        try:
            o = s.get(Order, r.json()["id"])
            return o.id, o.order_number, o.items[0].id, t
        finally:
            s.close()


    def jurnal(**f):
        s = SessionLocal()
        try:
            q = s.query(ActivityLog).filter(ActivityLog.company_id == 1)
            for k, v in f.items():
                q = q.filter(getattr(ActivityLog, k) == v)
            return [(a.entity_label, a.old_value, a.new_value) for a in q.order_by(ActivityLog.id).all()]
        finally:
            s.close()


    O1, N1, I1, T1 = buyurtma("bir")
    check("D1 jurnal: buyurtma yaratildi — «Jami: 3 703 701 so'm, 1 ta detal» (ODDIY bo'shliq, gapdagi vergul joyida)",
          lambda: [x[2] for x in jurnal(action="created", entity_type="order", entity_id=O1)] == ["Jami: 3 703 701 so'm, 1 ta detal"],
          jurnal(action="created", entity_type="order", entity_id=O1))
    r = CL.post("/api/payments", json={"order_id": O1, "amount": 5_000_000})
    check("D2 to'lov qarzdan ko'p → 409: «Kiritilgan summa (5 000 000 so'm) qarzdan (3 703 701 so'm) 1 296 299 so'mga ko'p»",
          lambda: r.status_code == 409 and det(r)["message"] == nb("Kiritilgan summa (5 000 000 so'm) qarzdan (3 703 701 so'm) 1 296 299 ")
          + "so'mga ko'p. Shunday ham davom etasizmi?", (r.status_code, r.text[:300]))
    r = CL.post("/api/payments", json={"order_id": O1, "amount": 20_000_000})
    check("D3 to'lov buyurtmadan 3 baravar katta → 400: «Kiritilgan summa (20 000 000 so'm) buyurtma qiymatidan (3 703 701 so'm) juda katta»",
          lambda: r.status_code == 400 and nb("Kiritilgan summa (20 000 000 so'm) buyurtma qiymatidan (3 703 701 so'm) juda katta")
          in str(js(r).get("detail")), (r.status_code, r.text[:300]))
    r = CL.post("/api/payments", params={"write_off_remainder": "true", "kechirish": "100000"}, json={"order_id": O1, "amount": 3_553_701})
    check("D4 kechirish summasi o'zgargan → 409: «to'lovdan keyin 150 000 so'm qoladi, oynada esa 100 000 so'm»",
          lambda: r.status_code == 409 and nb("to'lovdan keyin 150 000 so'm qoladi, oynada esa 100 000 so'm") in det(r)["message"],
          (r.status_code, r.text[:300]))
    r = CL.post("/api/payments", params={"write_off_remainder": "true", "kechirish": "150000"}, json={"order_id": O1, "amount": 3_553_701})
    check("D5 qolgan qarz chegirmaga: «Qolgan 150 000 so'm chegirmaga qo'shildi»",
          lambda: r.status_code == 200 and (js(r).get("write_off") or {}).get("message", "").startswith(nb("Qolgan 150 000 so'm chegirmaga")),
          (r.status_code, r.text[:300]))
    _s = SessionLocal()
    _pid = (_s.query(Payment.id).filter(Payment.order_id == O1).order_by(Payment.id.desc()).first() or [None])[0]
    _s.close()
    r = CL.delete(f"/api/payments/{_pid}")
    _jp = [x[2] for x in jurnal(action="deleted", entity_type="payment", entity_id=_pid)]
    check("D6 jurnal: to'lov o'chirildi — «3 553 701 so'm · …» (ODDIY bo'shliq)",
          r.status_code == 200 and len(_jp) == 1 and _jp[0].startswith("3 553 701 so'm · "), (r.status_code, _jp))
    _s = SessionLocal()
    try:
        _q = crud.audit_jurnali_sahifasi(_s, 1, matn="3 553 701")
        _topildi = [a.entity_type for a in _q["yozuvlar"]]
    finally:
        _s.close()
    check("D7 «Faoliyat jurnali» qidiruvi oddiy bo'shliq bilan («3 553 701») — o'chirilgan to'lov yozuvini TOPADI", "payment" in _topildi, _topildi)
    O2, N2, I2, _ = buyurtma("ikki")
    r = CL.post("/api/payments", json={"order_id": O2, "amount": 5_000_000, "confirm_overpay": True})
    r = CL.post(f"/api/orders/{O2}/refund-overpayment", json={"amount": 2_000_000})
    check("D8 ortiqchadan ko'p qaytarish → 400: «Qaytariladigan summa (2 000 000 so'm) ortiqcha to'lovdan (1 296 299 so'm) ko'p»",
          lambda: r.status_code == 400 and js(r).get("detail") == nb("Qaytariladigan summa (2 000 000 so'm) ortiqcha to'lovdan (1 296 299 so'm) ko'p"),
          (r.status_code, r.text[:300]))
    r = CL.post(f"/api/orders/{O2}/refund-overpayment", json={"amount": 1_000_000.5})
    check("D9 jurnal: ortiqcha to'lov qaytarildi — «Ortiqcha to'lov mijozga qaytarildi: 1 000 000,5 so'm»",
          lambda: r.status_code == 200 and [x[2] for x in jurnal(action="refunded", entity_type="order", entity_id=O2)] == [
              "Ortiqcha to'lov mijozga qaytarildi: 1 000 000,5 so'm"], (r.status_code, jurnal(action="refunded", entity_type="order", entity_id=O2)))
    O3, N3, I3, _ = buyurtma("uch")
    r = CL.post("/api/deliveries", json={"order_id": O3, "items": [{"order_item_id": I3, "quantity": 1}], "payment_amount": 9_000_000,
                                         "payment_method": "naqd"})
    check("D10 yuk xati bilan to'lov qarzdan ko'p → 409: «Kiritilgan summa (9 000 000 so'm) qarzdan (3 703 701 so'm) 5 296 299 so'mga ko'p»",
          lambda: r.status_code == 409 and det(r)["message"].startswith(
              nb("Kiritilgan summa (9 000 000 so'm) qarzdan (3 703 701 so'm) 5 296 299 ") + "so'mga ko'p"), (r.status_code, r.text[:300]))
    O4, N4, I4, _ = buyurtma("tort")
    r = CL.post("/api/deliveries", json={"order_id": O4, "items": [{"order_item_id": I4, "quantity": 1}]})
    r2 = CL.post(f"/api/orders/{O4}/ready")
    _fin = (js(r2).get("finalized") or {}).get("message", "")
    check("D11 qisman «Tayyor»: «Buyurtma summasi 3 703 701 → 1 234 567 so'mga tushirildi», «Qarz qoldi: 1 234 567 so'm.»",
          r.status_code == 200 and r2.status_code == 200 and _fin.startswith(nb("Buyurtma summasi 3 703 701 → 1 234 567 so'mga tushirildi"))
          and _fin.endswith(nb("Qarz qoldi: 1 234 567 so'm.")), (r.status_code, r2.status_code, r2.text[:400]))
    O5, N5, I5, T5 = buyurtma("besh")
    r = CL.post("/api/returns", json={"order_id": O5, "order_item_id": I5, "item_name": "T192 panel besh", "quantity": 2, "unit": "metr",
                                      "reason": "Ortiqcha", "refund_amount": 9_000_000_000, "to_stock": True, "notes": None,
                                      "coating_applied": False})
    check("D12 qaytarish summasi katta → 400: «Qaytariladigan summa (9 000 000 000 so'm) … (2 469 134 so'm = 2 × 1 234 567 so'm)»",
          lambda: r.status_code == 400 and nb("Qaytariladigan summa (9 000 000 000 so'm) bu detal qismining kelishilgan qiymatidan "
                                              "(2 469 134 so'm = 2 × 1 234 567 so'm)") in str(js(r).get("detail")), (r.status_code, r.text[:300]))
    T5["items"][0]["quantity"] = 4
    r = CL.put(f"/api/orders/{O5}", json=T5, params={"confirm_shortage": "true"})
    _ju = jurnal(action="updated", entity_type="order", entity_id=O5)
    check("D13 jurnal: buyurtma tahrirlandi — eski «Jami: 3 703 701 so'm, 1 ta detal», yangi «Jami: 4 938 268 so'm, 1 ta detal…»",
          r.status_code == 200 and len(_ju) == 1 and _ju[0][1] == "Jami: 3 703 701 so'm, 1 ta detal"
          and (_ju[0][2] or "").startswith("Jami: 4 938 268 so'm, 1 ta detal"), (r.status_code, r.text[:200], _ju))
    O6, N6, I6, _ = buyurtma("olti")
    _s = SessionLocal()
    try:                                       # savatdagi buyurtma (topshirilmagan buyurtma DELETE da butunlay o'chadi — sahifa chizishi sinaladi)
        _o6 = _s.get(Order, O6)
        _o6.is_deleted = True
        _s.commit()
    finally:
        _s.close()
    _tr = CL.get("/trash")
    check("D14 O'chirilganlar sahifasi: buyurtma summasi «3 703 701 so'm» (bo'linmas bo'shliq; ilgari «3703701»)",
          _tr.status_code == 200 and N6 in _tr.text and nb("3 703 701 so'm") in _tr.text and "3703701 so'm" not in _tr.text,
          (_tr.status_code, N6 in _tr.text))
    r = CL.post("/api/suppliers", json={"name": "T192 Ta'minotchi", "phone": "+998901234567"})
    SUP = js(r).get("id") or (js(r).get("supplier") or {}).get("id")
    TG.clear()
    r = CL.post(f"/api/inventory/{MAT}/purchase", json={"quantity": 12.5, "price_per_unit": 120_000.5, "supplier_id": SUP, "paid_now": 0})
    _tg = "\n".join(TG)
    check("D15 Telegram «Nasiya xarid»: «12,5 kg × 120 000», «Jami summasi: 1 500 006 so'm», qarz — bo'linmas bo'shliq",
          r.status_code == 200 and nb("12,5 kg × 120 000") in _tg and nb("Jami summasi: 1 500 006 so'm") in _tg
          and nb("Shu ta'minotchiga qarz: 1 500 006 so'm") in _tg, (SUP, r.status_code, r.text[:200], _tg[:400]))
    r = CL.delete(f"/api/suppliers/{SUP}")
    check("D16 qarzi bor ta'minotchini o'chirish → 400: «Bu ta'minotchida 1 500 006 so'm qarz bor»",
          lambda: r.status_code == 400 and det(r)["message"] == nb("Bu ta'minotchida 1 500 006 so'm qarz bor"), (r.status_code, r.text[:300]))
    r = CL.post("/api/finished/sell", json={"finished_product_id": FP, "quantity": 1, "unit_price": 1_500_000, "payment_method": "naqd"})
    check("D17 tayyor mahsulot narxi juda past → 400: «Kiritilgan narx (1 metr uchun 1 500 000 so'm) juda past»",
          lambda: r.status_code == 400 and det(r).get("type") == "below_cost_warning"
          and det(r)["message"].startswith(nb("Kiritilgan narx (1 metr uchun 1 500 000 so'm) juda past")), (r.status_code, r.text[:300]))
    r = CL.post("/api/finished/sell-batch", json={"items": [{"finished_product_id": FP, "quantity": 1, "unit_price": 1_500_000}],
                                                   "payment_method": "naqd"})
    check("D18 savat: narx juda past → 400: «T192 Karniz: kiritilgan narx (1 metr uchun 1 500 000 so'm) juda past»",
          lambda: r.status_code == 400 and det(r)["message"].startswith(nb("T192 Karniz: kiritilgan narx (1 metr uchun 1 500 000 so'm) juda past")),
          (r.status_code, r.text[:300]))
    r = CL.post("/api/gift-period/open", json={"tiers": [{"gift_name": "T192 Sovg'a", "threshold_amount": 1_500_000}]})
    _s = SessionLocal()
    try:
        from models import GiftPeriodTier, Master
        _tier = _s.query(GiftPeriodTier).order_by(GiftPeriodTier.id.desc()).first()
        TIER = _tier.id if _tier else 0
        _u = Master(company_id=1, name="T192 Usta", phone="+998901112233")
        _s.add(_u)
        _s.commit()
        USTA = _u.id
    finally:
        _s.close()
    r = CL.put(f"/api/gift-period/tier/{TIER}", json={"gift_name": "T192 Sovg'a", "threshold_amount": 0.001})
    check("D20 sovg'a bosqichi — juda kichik summa → 400: «Summa kamida 0,01 so'm bo'lishi kerak» (ilgari «0.01»)",
          lambda: r.status_code == 400 and str(js(r).get("detail")).startswith("Summa kamida 0,01 so'm bo'lishi kerak"), (TIER, r.status_code, r.text[:200]))
    r = CL.post(f"/api/gift-period/redeem/{USTA}/{TIER}")
    check("D21 usta bosqichga yetmagan → 400: «(kerak: 1 500 000 so'm, mavjud: 0 so'm)» (ilgari «kerak: 1,500,000, mavjud: 0»)",
          lambda: r.status_code == 400 and str(js(r).get("detail")) == nb("Usta hali bu bosqichga yetmagan (kerak: 1 500 000 so'm, mavjud: 0 so'm)"),
          (r.status_code, r.text[:200]))
    r = CL.post("/api/inventory/receipt", json={
        "items": [{"inventory_id": MAT, "quantity": 10, "price_per_unit": 100_000}], "transport_cost": 1_234_567, "tushirish_cost": 0,
        "yuklash_cost": 0, "boshqa_cost": 0, "add_to_cost": False, "supplier_id": SUP, "document_number": "T192-K", "paid_now": 500_000,
        "notes": "T192"})
    _rid = js(r).get("receipt_id") or js(r).get("id")
    r2 = CL.post(f"/api/inventory/receipts/{_rid}/cancel", params={"tolov": "ochirish"})
    _jk = [x[2] for x in jurnal(action="deleted", entity_type="inventory_receipt", entity_id=_rid or -1)]
    check("D22 jurnal: kirim hujjati bekor — «1 ta material, qo'shimcha xarajat 1 234 567 so'm, to'lov 500 000 so'm — o'chirildi» (vergul joyida)",
          r.status_code == 200 and r2.status_code == 200 and _jk == ["1 ta material, qo'shimcha xarajat 1 234 567 so'm, to'lov 500 000 so'm — o'chirildi"],
          (r.status_code, r.text[:200], r2.status_code, r2.text[:200], _jk))
    r = CL.post("/api/inventory/receipt", json={
        "items": [{"inventory_id": MAT, "quantity": 1250, "price_per_unit": 100_000.5}] * 2, "transport_cost": 0, "tushirish_cost": 0,
        "yuklash_cost": 0, "boshqa_cost": 0, "add_to_cost": False, "supplier_id": SUP, "document_number": "T192-T", "paid_now": 0})
    check("D23 kirimda takror qator → 400: «(«T192 Akril», 1 250 × 100 000,5)» (ilgari «1250 × 100 000.5»)",
          lambda: r.status_code == 400 and nb("2-qator 1-qator bilan AYNAN bir xil («T192 Akril», 1 250 × 100 000,5)") in str(js(r).get("detail")),
          (r.status_code, r.text[:300]))
    TG.clear()
    main._avans_olmadim_telegram("Ali", 1_500_000.4, None, "T192 A", 1)
    check("D19 Telegram «Hodim avansni olmaganini aytdi»: «💰 1 500 000 so'm (—)»", nb("💰 1 500 000 so'm (—)") in "\n".join(TG), TG)
    main._send_telegram = _asl_tg

# ── T. Tannarx niqobi — yangi jurnal matnida ham ─────────────────────────────────────────────────────────────────
section("T: tannarx ruxsatisiz foydalanuvchi — yangi ko'rinishdagi jurnal yozuvida ham tannarx «—»")


def _niq(action, et, **v):
    a = SimpleNamespace(id=1, action=action, entity_type=et, entity_id=1, entity_label=v.get("label"), performed_by="T192",
                        old_value=None, new_value=v.get("new"), created_at=datetime(2026, 10, 17), company_id=1)
    return crud.jurnal_tannarx_yashir(a)


_s110 = production_service._son110
_ish = (f"{_s110(12.5)} m² — tannarx {_s110(1234567.5)} so'm (xomashyo {_s110(1000000)}, qo'shimcha {_s110(234567.5)})"
        f"; Boshlashdagi taxmin {_s110(1200000)} so'm, farq +{_s110(34567.5)} so'm")
_n1 = _niq("produced", "production_order", new=_ish)
check("T1 ishlab chiqarish yakuni («tannarx 1 234 567,5 so'm (xomashyo …)», «Boshlashdagi taxmin …») — tannarx va taxmin «—»",
      _n1.new_value == "12,5 m² — tannarx —; Boshlashdagi taxmin —", (_ish, _n1.new_value))
_qo = f"{crud.audit_son(12.5)} metr, tan narxi: {crud.audit_son(225000)} so'm"
_n2 = _niq("produced", "finished_product", new=_qo)
check("T2 qo'lda ishlab chiqarish («12,5 metr, tan narxi: 225 000 so'm») — «tan narxi: —»", _n2.new_value == "12,5 metr, tan narxi: —",
      (_qo, _n2.new_value))
try:
    _br = f"Brak bekor qilindi: T192 — {crud.audit_son(3.5)} dona ({crud.audit_son(450000.4, 0)} so'm) · ombor tiklandi"
except TypeError:                          # zip 191 kodi: `audit_son` da kasr parametri yo'q
    _br = ""
_n3 = _niq("delete", "finished_product_loss", label=_br)
check("T3 brak bekori («3,5 dona (450 000 so'm)») — «(—)»", _n3.entity_label == "Brak bekor qilindi: T192 — 3,5 dona (—) · ombor tiklandi",
      (_br, _n3.entity_label))

print(f"\n{REJIM}NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
