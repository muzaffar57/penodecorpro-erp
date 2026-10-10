#!/usr/bin/env python3
"""
test_dash_yuklash_ui.py — kech137 (zip 163): Dashboard sahifasi har bir so'rov xatosida QOTMAYDI va yolg'on ko'rsatmaydi — HAQIQIY
brauzerda (Chromium, Playwright), HAQIQIY lokal server bilan (uvicorn, test bazasi) O'LCHANADI.

NIMA UCHUN KERAK (O'LCHANGAN — work/k163/olchov163.py, zip 162 kodi; egasi tanlovi 10.10 «Dashboard qotmasin»)
  * `loadAll` bitta `Promise.all` edi: stats / charts / today dan biri xato bersa (deploy paytidagi 502, internet uzilishi) BUTUN sahifa
    to'xtardi — pul kartalari «—», «Ishlab chiqarish» va 4 ro'yxat abadiy «Yuklanmoqda...», qolgan bloklar yuklanmasdi, sabab yo'q;
    Chart.js (CDN) yuklanmasa ham shunday;
  * `r.ok` tekshirilmasdi: xato JSON (500 / 401) — «0 so'm», «✓ Qarzdorlik yo'q», «Bu oy xomashyo xaridi bo'lmagan», «Brak 0 ta»,
    «undefined ta»;
  * ruxsatsiz rol (tayyor «Moliyachi»): server rad etardi (403), sahifa yolg'on son yozardi; majburiyatlar bloki (ijara, ish haqi)
    ta'minotchilar rad etilgani uchun BUTUNLAY yashirinardi;
  * «Yangilash»: qarzdorlik / majburiyatlar yuklanmasa ham «Yangilandi: …»; sessiya tugaganda «qayta urinib ko'ring»;
  * poyga: sekin birinchi javob «Yangilash» dan keyin kelsa yangi raqam ustiga eskisi yozilardi (2,2 mln → 1,1 mln).

BO'LIMLAR
  Y1 hammasi yuklandi (boy, nolsiz ma'lumot): har blok qiymati, sabab yozuvlari yashirin, holat yozuvi bo'sh, `/api/dashboard/stats`
     so'ralmaydi, «Jami majburiyat» to'g'ri;
  Y2 15 so'rov × 5 xato (502 HTML, 500 JSON, tarmoq, 401, 403): o'sha blok «—» va O'SHA blokda aniq sabab; QOLGAN hamma blok o'z
     qiymatida; «Yuklanmoqda...» / «undefined» / «NaN» ko'rinmaydi; holat yozuvi (401 — kirish havolasi); JS xatosi yo'q;
  Y3 Chart.js yuklanmadi — hamma ma'lumot ko'rinadi, grafik o'rnida yozuv;
  Y4 rollar (HAQIQIY server): Moliyachi, faqat Dashboard, Dashboard + Qarzlar, Dashboard + Tayyor, Dashboard + Kirim / Ta'minotchi /
     Qaytarish — ruxsatsiz blok yo'q va so'ralmaydi (403 yo'q), majburiyatlar bloki ko'rinadi; admin — hammasi (ijobiy nazorat);
  Y5 «Yangilash» xato bilan → sabab va «Ba'zi ma'lumotlar yangilanmadi»; tuzalgach → qiymat qaytadi, sabab yo'qoladi;
  Y6 avtomatik yangilash (soat 5 daqiqaga suriladi) — xato bo'lsa holat yozuvi aytadi, majburiyatlar ham yangilanadi;
  Y7 sessiya tugadi (HAQIQIY 401) — «Kirish muddati tugagan — qayta kiring» havolasi;
  Y8 poyga — eski javob kech kelsa tashlanadi (qarzdorlik va majburiyatlar);
  Y9 telefon 390 / 320 (kunduzgi / tungi): hamma blok xato — sahifa yon tomonga toshmaydi, sabab matni ekranda, kontrast ≥ 4.5;
  Y10 majburiyatlar: bo'sh va xatosiz — blok yashirin; bo'sh, lekin xato — sabab bilan ko'rinadi;
  Y11 statik: shablon tuzilishi.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan PostgreSQL. Asl kodga (zip 162) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_dash_yuklash_ui.py
"""
import os
import re
import io
import sys
import glob
import json
import time
import socket
import datetime
import tempfile
import threading
import contextlib
from urllib.parse import urlparse

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OK = FAIL = 0
FAILED = []
PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
YORLIQ = "[PG] " if PG_URL else ""


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
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
        print(f"  ✗ {label}   {str(detail)[:1500]}")


def section(t):
    print(f"\n--- {t} ---")


# Mutatsiya sinovlari uchun tanlov (odatiy — HAMMASI): DY_BOLIM=Y2,Y5 — faqat shu bo'limlar; DY_YOL=debts,suppliers — Y2 da faqat yo'lida
# shu bo'lak bor so'rovlar; DY_TUR=500_json,401_json — Y2 da faqat shu xatolar. Statik Y11 doim yuradi.
_BOLIM = {x for x in (os.environ.get("DY_BOLIM") or "").split(",") if x}
_YOL = [x for x in (os.environ.get("DY_YOL") or "").split(",") if x]
_TUR = {x for x in (os.environ.get("DY_TUR") or "").split(",") if x}


def bolim(nom):
    return not _BOLIM or nom in _BOLIM


try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_xato = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_xato = False, f"{type(_e).__name__}: {_e}"

PG_BAZA = "dash_yuklash_ui163_test"
_T = tempfile.mkdtemp(prefix="dy_ui_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'dy_ui_test.db')}"
os.environ.pop("TENANT_FILTER", None)
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("BACKUP_TELEGRAM_CHAT_ID", None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, Rol             # noqa: E402

# ══════════════════════════════════════════════════════════════
# Fikstura: admin, tayyor «Moliyachi» (rolsiz — `users.role` = accountant), maxsus rollar
# ══════════════════════════════════════════════════════════════
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "dy_a", "Parol123!", UserRole.ADMIN, "DY admin", company_id=1)
    auth.create_user(s, "dy_mol", "Parol123!", UserRole.ACCOUNTANT, "DY moliyachi", company_id=1)
    for _u in ("dy_d", "dy_dq", "dy_dt", "dy_dk"):
        auth.create_user(s, _u, "Parol123!", UserRole.MANAGER, _u.upper(), company_id=1)
ROLLAR = {"dy_d": {"dashboard": ["korish"]},
          "dy_dq": {"dashboard": ["korish"], "qarz": ["korish"]},
          "dy_dt": {"dashboard": ["korish"], "tayyor": ["korish"]},
          "dy_dk": {"dashboard": ["korish"], "kirim": ["korish"], "taminotchi": ["korish"], "qaytarish": ["korish"]}}
for _u, _rx in ROLLAR.items():
    _r = Rol(company_id=1, nom="DY163 " + _u, kod=None, ruxsatlar=json.dumps(_rx), tavsif="")
    s.add(_r)
    s.flush()
    s.query(User).filter(User.username == _u).first().rol_id = _r.id
s.commit()
s.close()

# «OK» javoblar — nolsiz, ajraladigan qiymatlar (xato «0 so'm» ni haqiqiy qiymatdan ajratish uchun)
BOY = {
    "/api/dashboard/charts": {"finance": {"total_paid": 12345678, "total_budget": 23456789},
                              "months": [{"label": "Sen", "orders": 4}, {"label": "Okt", "orders": 5}],
                              "statuses": {"new": 3, "in_progress": 2, "ready": 6},
                              "master_kpi": [{"name": "Usta Alisher", "orders": 4, "total": 3000000}]},
    "/api/dashboard/today": {"today_revenue": 1500000, "today_payments": 1000000, "today_sales": 500000, "active_orders": 7,
                             "in_production": 3, "due_today": 2, "active_masters": 4, "today_profit": 400000},
    "/api/finance/history": [{"daromad": 9876543}],
    "/api/dashboard/production-periods": {"today": 11, "week": 22, "month": 33},
    "/api/dashboard/debts": {"total_debt": 4500000, "debt_orders_count": 3, "overdue_count": 1,
                             "debt_orders": [{"order_number": "ORD-101", "payment_status": "partial", "agreed_amount": 1000000,
                                              "paid_amount": 400000, "debt_amount": 600000, "is_overdue": False, "days_passed": 3,
                                              "client_name": "Mijoz A", "project_name": "Loyiha A", "is_deleted": False}]},
    "/api/dashboard/deliveries": {"fully_delivered": 8, "partial_count": 1, "not_started": 2,
                                  "partial_orders": [{"order_number": "ORD-202", "items_pending": 2, "client_name": "Mijoz B",
                                                      "percent": 40, "debt_amount": 0}]},
    "/api/inventory/purchase-stats": {"total_amount": 7000000, "by_material": [
        {"name": "Penoplast 25", "category": "Penoplast", "total": 7000000, "quantity": 10, "unit": "m3", "avg_price": 700000}]},
    "/api/transport-stats": {"inbound_total": 300000, "outbound_company": 200000},
    "/api/suppliers/debt-total": {"total_debt": 500000, "supplier_count": 1},
    "/api/finished/stats": {"produced_value": 8000000, "in_progress_count": 6, "returned_value": 100000, "total_value": 8100000},
    "/api/returns/stats": {"brak_month_count": 4, "brak_month_value": 120000, "whole_month_count": 2, "brak_total_value": 900000},
    "/api/reports/brak-tahlil": {"meyor_foiz": 5, "brak_foizi": 2.5, "meyordan_oshdi": False, "ogohlantirish": None},
    "/api/obligations/status": {"recurring": [{"icon": "🏛️", "label": "Ijara", "due_day": 5, "status": "overdue", "debt": 1500000}],
                                "employees": [{"name": "Hodim Bekzod", "qolgan": 2000000, "status": "partial"}]},
    "/api/suppliers": [{"id": 1, "name": "Taminotchi A", "debt": 500000}],
    "/api/suppliers/due-dates": [{"supplier_id": 1, "due_date": "2026-10-01", "days_left": -9, "status": "overdue"}],
}
_OYLAR = ['', 'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun', 'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr']
_tk = datetime.datetime.utcnow() + datetime.timedelta(hours=5)
KUT = {   # id → kutilgan matn (aniq)
    "t-revenue": "1,5 mln so'm", "t-revenue-sub": "to'lovlar 1,0 mln · sotuv 500 ming", "t-active": "7 ta", "t-production": "3 ta",
    "t-due": "2 ta", "t-masters": "4 ta", "t-profit": "400 ming so'm", "prodPeriods": "11 Bugun 22 Hafta 33 Oy",
    "f-revenue": "9,9 mln so'm", "f-revenue-sub": f"{_OYLAR[_tk.month]} {_tk.year} · Hisobotlar bilan bir xil",
    "f-paid": "12,3 mln so'm", "f-budget": "23,5 mln so'm",
    "d-total": "4,5 mln so'm", "d-count": "3 ta", "d-overdue": "1 ta", "debt-count-label": "3 ta buyurtma",
    "purch-total": "7,0 mln so'm", "tr-inbound": "300 ming so'm", "tr-outbound": "200 ming so'm",
    "sup-debt-total": "500 ming so'm", "sup-debt-count": "1 ta ta'minotchiga qarzdormiz",
    "fp-produced-value": "8,0 mln so'm", "fp-progress-count": "6 ta", "fp-returned-value": "100 ming so'm", "fp-total-value": "8,1 mln so'm",
    "brk-month-count": "4 ta", "brk-month-value": "120 ming so'm", "brk-whole-count": "2 ta", "brk-meyor": "5 %", "brk-foiz": "2,5 %",
    "brk-total-value": "900 ming so'm", "dl-full": "8 ta", "dl-partial": "1 ta", "dl-none": "2 ta", "partial-label": "1 ta buyurtma",
}
KUT_ICHIDA = {   # id → matn ichida bo'lishi kerak
    "statusLegend": "Yangi 3 ta Jarayonda 2 ta Tayyor 6 ta", "purchList": "Penoplast 25", "partialList": "ORD-202", "debtList": "ORD-101",
    "masterList": "Usta Alisher", "obligList": "Taminotchi A — 01.10.2026 gacha",
}
XATO_IDLAR = ["xato-umumiy", "xato-bugun", "xato-moliya", "xato-qarzdorlik", "xato-yetkazish", "xato-transport", "xato-tayyor", "xato-brak",
              "xato-brak-ulush"]
# so'rov → blok: «—» bo'ladigan idlar, sabab yozuvi (id, nima), ro'yxat ichidagi sabab, kichik izoh, grafik, majburiyat qismi
BLOK = {
    "/api/dashboard/today": {"idlar": ["t-revenue", "t-active", "t-production", "t-due", "t-masters", "t-profit"],
                             "bosh": ["t-revenue-sub"], "sabab": ("xato-bugun", "Bugungi ko'rsatkichlar")},
    "/api/dashboard/charts": {"idlar": ["f-paid", "f-budget"], "sabab": ("xato-moliya", "«To'langan» va «Jami byudjet»"),
                              "royxat": [("statusLegend", "Buyurtmalar holati"), ("masterList", "Usta reytingi")],
                              "grafik": ("ordersCountChart", "Buyurtmalar soni")},
    "/api/finance/history": {"idlar": ["f-revenue"], "izoh": ("f-revenue-sub", "Shu oy daromadi")},
    "/api/dashboard/production-periods": {"royxat": [("prodPeriods", "Ishlab chiqarish")]},
    "/api/dashboard/debts": {"idlar": ["d-total", "d-count", "d-overdue", "debt-count-label"], "sabab": ("xato-qarzdorlik", "Qarzdorlik"),
                             "royxat": [("debtList", "Qarzdor buyurtmalar")]},
    "/api/dashboard/deliveries": {"idlar": ["dl-full", "dl-partial", "dl-none", "partial-label"],
                                  "sabab": ("xato-yetkazish", "Yetkazish ko'rsatkichlari"),
                                  "royxat": [("partialList", "Qisman topshirilgan buyurtmalar")]},
    "/api/inventory/purchase-stats": {"idlar": ["purch-total"], "royxat": [("purchList", "Xomashyo xaridlari")]},
    "/api/transport-stats": {"idlar": ["tr-inbound", "tr-outbound"], "sabab": ("xato-transport", "Transport xarajatlari")},
    "/api/suppliers/debt-total": {"idlar": ["sup-debt-total"], "izoh": ("sup-debt-count", "Ta'minotchilar qarzi")},
    "/api/finished/stats": {"idlar": ["fp-produced-value", "fp-progress-count", "fp-returned-value", "fp-total-value"],
                            "sabab": ("xato-tayyor", "Tayyor mahsulotlar")},
    "/api/returns/stats": {"idlar": ["brk-month-count", "brk-month-value", "brk-whole-count", "brk-total-value"],
                           "sabab": ("xato-brak", "Brak")},
    "/api/reports/brak-tahlil": {"idlar": ["brk-meyor", "brk-foiz"], "sabab": ("xato-brak-ulush", "Brak ulushi")},
    "/api/obligations/status": {"majburiyat": "Doimiy majburiyatlar va ish haqi"},
    "/api/suppliers": {"majburiyat": "Ta'minotchilar qarzi"},
    "/api/suppliers/due-dates": {"majburiyat": "Ta'minotchilarga to'lov muddatlari"},
}
SABAB = {"502_html": "server javob bermadi, «Yangilash» tugmasini bosing",
         "500_json": "server javob bermadi, «Yangilash» tugmasini bosing",
         "tarmoq": "internet aloqasi yo'q, «Yangilash» tugmasini bosing",
         "401_json": "kirish muddati tugagan, qayta kiring",
         "403_json": "ko'rish ruxsati yo'q"}
UMUMIY = "⚠️ Ba'zi ma'lumotlar yuklanmadi — sababi o'sha bo'limda yozilgan; «Yangilash» tugmasini bosing"
UMUMIY_SESSIYA = "⚠️ Kirish muddati tugagan — qayta kiring"
YANGILANMADI = "Yangilanmadi"
QIZIL = "rgb(185, 28, 28)"           # `--m-b91c1c` (kunduzgi) — sabab matni rangi


def matn(nima, tur):
    return f"⚠️ {nima} yuklanmadi — {SABAB[tur]}"


SNAP = r"""(xatoIdlar) => {
  const t = id => { const e = document.getElementById(id); return e ? (e.innerText || e.textContent || '').replace(/\s+/g, ' ').trim() : null; };
  const ko = e => !!e && !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden';
  const o = {qiymat: {}, xato: {}, grafik: {}};
  ['t-revenue','t-revenue-sub','t-active','t-production','t-due','t-masters','t-profit','statusLegend','prodPeriods','f-revenue',
   'f-revenue-sub','f-paid','f-budget','obligList','d-total','d-count','d-overdue','purch-total','tr-inbound','tr-outbound','purchList',
   'sup-debt-total','sup-debt-count','fp-produced-value','fp-progress-count','fp-returned-value','fp-total-value','brk-month-count',
   'brk-month-value','brk-whole-count','brk-meyor','brk-foiz','brk-total-value','dl-full','dl-partial','dl-none','partial-label',
   'partialList','debt-count-label','debtList','masterList'].forEach(i => o.qiymat[i] = t(i));
  xatoIdlar.forEach(i => { const e = document.getElementById(i);
    o.xato[i] = e ? {hidden: e.hidden, korinadi: ko(e), matn: (e.textContent || '').trim(), rang: getComputedStyle(e).color} : null; });
  ['ordersCountChart', 'statusChart'].forEach(i => { const c = document.getElementById(i);
    const y = c && c.parentElement ? c.parentElement.querySelector('.grafik-bosh') : null;
    o.grafik[i] = {kanvas: c ? getComputedStyle(c).display : null, yozuv: y && y.style.display !== 'none' ? y.textContent : null,
                   xato: !!(y && y.classList.contains('xato'))}; });
  const iz = id => { const e = document.getElementById(id); return e ? getComputedStyle(e).color : null; };
  o.izoh_rang = {'f-revenue-sub': iz('f-revenue-sub'), 'sup-debt-count': iz('sup-debt-count')};
  o.qator_rang = {};
  ['statusLegend', 'masterList', 'prodPeriods', 'debtList', 'partialList', 'purchList', 'obligList'].forEach(i => {
    const q = document.querySelector('#' + i + ' .dash-xato-qator, #' + i + ' .dash-xato'); o.qator_rang[i] = q ? getComputedStyle(q).color : null; });
  const yb = document.getElementById('dashYangilandi'); o.holat_rang = yb ? getComputedStyle(yb).color : null;
  const uh = document.querySelector('#xato-umumiy a'); o.umumiy_havola = uh ? uh.getAttribute('href') : null;
  const ob = document.getElementById('obligWidget');
  o.oblig = ob ? {display: getComputedStyle(ob).display, matn: t('obligList'), taminotchi: ob.dataset.taminotchi} : null;
  const pc = document.getElementById('partialCard');
  o.partialCard = pc ? getComputedStyle(pc).display : null;
  const yoz = document.getElementById('dashYangilandi');
  o.holat = yoz ? {matn: (yoz.textContent || '').trim(), xato: yoz.classList.contains('xato'),
                   havola: (yoz.querySelector('a') || {}).getAttribute ? yoz.querySelector('a').getAttribute('href') : null} : null;
  // ko'rinib turgan «Yuklanmoqda» / «undefined» / «NaN» (sahifa mazmuni)
  const kont = document.querySelector('.erp-content') || document.body;
  o.yuklanmoqda = [...kont.querySelectorAll('*')].filter(e => ko(e) && [...e.childNodes].some(n => n.nodeType === 3 && /Yuklanmoqda/.test(n.textContent)))
                    .map(e => e.id || e.parentElement.id || e.tagName);
  o.notogri = (kont.innerText.match(/[^\n]{0,30}(undefined|NaN)[^\n]{0,30}/g) || []).slice(0, 6);
  return o;
}"""

TEMA_KONTRAST = r"""(idlar) => {
  const rgba = c => { const m = (c.match(/[\d.]+/g) || []).map(Number); return [m[0] || 0, m[1] || 0, m[2] || 0, m.length > 3 ? m[3] : 1]; };
  const fonEl = e => { for (let p = e; p; p = p.parentElement) { const c = rgba(getComputedStyle(p).backgroundColor); if (c[3] > 0) return c; }
                       return rgba(getComputedStyle(document.documentElement).backgroundColor); };
  const lum = c => { const [r, g, b] = c.slice(0, 3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
                     return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const kon = (a, b) => { const x = lum(a), y = lum(b); return Math.round(100 * (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)) / 100; };
  const natija = {};
  idlar.forEach(sel => { const e = document.querySelector(sel); if (!e || !(e.offsetWidth || e.offsetHeight)) { natija[sel] = null; return; }
    const b = e.getBoundingClientRect();
    natija[sel] = {kontrast: kon(rgba(getComputedStyle(e).color), fonEl(e)), chap: Math.round(b.left), ong: Math.round(b.right)}; });
  natija.__vw = innerWidth; natija.__sw = document.documentElement.scrollWidth;
  const tb = document.querySelector('.erp-topbar'), tg = document.getElementById('dashYangilaBtn'), sr = document.querySelector('.page-title');
  natija.__topbar = {toshdi: !!tb && tb.scrollWidth > tb.clientWidth + 1, tugma_ong: tg ? Math.round(tg.getBoundingClientRect().right) : null,
                     sarlavha_eni: sr ? Math.round(sr.getBoundingClientRect().width) : null};
  return natija;
}"""

section("Y0. Tayyorgarlik")
check("Y0 Python `playwright` bor", PW_BOR, _pw_xato)

import uvicorn                                     # noqa: E402


def yol_mos(yol):
    return lambda url: urlparse(url).path == yol


def jv(r, holat, tana):
    r.fulfill(status=holat, body=json.dumps(tana), content_type="application/json")


XATOLAR = {
    "502_html": lambda r: r.fulfill(status=502, body="<html><body>Bad Gateway</body></html>", content_type="text/html"),
    "500_json": lambda r: jv(r, 500, {"detail": "Ichki xato"}),
    "tarmoq": lambda r: r.abort("failed"),
    "401_json": lambda r: jv(r, 401, {"detail": "Kirish talab qilinadi"}),
    "403_json": lambda r: jv(r, 403, {"detail": "Ruxsat yo'q"}),
}

if PW_BOR:
    so = socket.socket()
    so.bind(("127.0.0.1", 0))
    port = so.getsockname()[1]
    so.close()
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(150):
        if server.started:
            break
        time.sleep(0.1)
    check("Y0b lokal server ishga tushdi", server.started)
    BU = f"http://127.0.0.1:{port}"
    CHART_STUB = "window.Chart = function () { return {destroy() {}, update() {}}; };"

    JS_XATO = []

    with sync_playwright() as pw:
        _exe = None
        for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                "chrome-linux", "chrome"))):
            _exe = _y
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()

        def kontekst(user="dy_a", w=1440, h=900, chart=True, soat=False):
            tel = w < 700
            ctx = br.new_context(viewport={"width": w, "height": h}, is_mobile=tel, has_touch=tel, timezone_id="Asia/Tashkent",
                                 locale="uz-UZ")
            ctx.set_default_timeout(15000)
            if soat:
                xav(ctx.clock.install)
            ctx.route(re.compile(r"^https://.*"), lambda r: (r.fulfill(status=200, body=CHART_STUB, content_type="application/javascript")
                                                            if chart else r.abort("failed"))
                      if re.search(r"chart(\.umd)?(\.min)?\.js", r.request.url, re.I) else r.fulfill(status=204, body=""))
            pg = ctx.new_page()
            pg.__xato = []
            pg.__sorov = []
            pg.on("pageerror", lambda e: (JS_XATO.append(str(e)[:300]), pg.__xato.append(str(e)[:300])))
            pg.on("response", lambda r: pg.__sorov.append((urlparse(r.url).path, r.status)) if "/api/" in r.url else None)
            xav(pg.goto, BU + "/login")
            xav(pg.fill, "input[name=username]", user)
            xav(pg.fill, "input[name=password]", "Parol123!")
            xav(pg.press, "input[name=password]", "Enter")
            xav(pg.wait_for_load_state, "networkidle")
            return ctx, pg

        def ev(pg, kod, arg=None):
            try:
                return pg.evaluate(kod, arg) if arg is not None else pg.evaluate(kod)
            except Exception as ex:        # noqa: BLE001
                return {"js_xato": str(ex)[:300]}

        def xav(f, *a, **k):
            """Brauzer amali — element topilmasa (asl kodda / mutatsiyada) sinov QULAMAYDI, tekshiruv yiqiladi."""
            try:
                return f(*a, **k)
            except Exception as ex:        # noqa: BLE001
                print(f"    (amal bajarilmadi: {getattr(f, '__name__', f)} {a[:1]} — {type(ex).__name__})")
                return None

        def boy(pg, istisno=(), faqat=None):
            for yol, val in BOY.items():
                if yol in istisno or (faqat is not None and yol not in faqat):
                    continue
                pg.route(yol_mos(yol), (lambda v: lambda r: jv(r, 200, v))(val))

        def dash(pg, kut=600):
            del pg.__sorov[:]                      # kirishdan keyingi Bosh sahifa so'rovlari hisobga olinmaydi
            xav(pg.goto, BU + "/dashboard")
            xav(pg.wait_for_load_state, "networkidle")
            pg.wait_for_timeout(kut)

        def snap(pg):
            o = ev(pg, SNAP, XATO_IDLAR)
            return o if isinstance(o, dict) and "qiymat" in o else {"qiymat": {}, "xato": {}, "grafik": {}, "xom": o}

        def qiymatlar_ok(o, istisno=()):
            """istisnodan tashqari hamma blok — kutilgan (boy) qiymatda; farqlar ro'yxati"""
            farq = []
            q = o.get("qiymat", {})
            for k, v in KUT.items():
                if k not in istisno and q.get(k) != v:
                    farq.append((k, q.get(k), v))
            for k, v in KUT_ICHIDA.items():
                if k not in istisno and v not in (q.get(k) or ""):
                    farq.append((k, (q.get(k) or "")[:80], v))
            return farq

        def sabablar_yashirin(o, istisno=()):
            """ko'rinib turgan sabab yozuvlari (rolda chizilmagan yozuv — None — hisobga olinmaydi; admin uchun 8 tasi borligi — Y1b)"""
            return [i for i, v in (o.get("xato") or {}).items() if i not in istisno and v and (not v["hidden"] or v["korinadi"])]

        if bolim("Y1"):
            # ══════════════════════════════════════════════════════════════
            section("Y1. Hammasi yuklandi")
            # ══════════════════════════════════════════════════════════════
            ctx, pg = kontekst()
            boy(pg)
            dash(pg)
            o = snap(pg)
            check("Y1a har blok kutilgan qiymatda (pul kartalari, holat afsonasi, davrlar, qarzdorlik, yetkazish, xarid, transport, "
                  "ta'minotchi, tayyor, brak, usta reytingi)", not qiymatlar_ok(o), qiymatlar_ok(o))
            check("Y1b sabab yozuvlari (umumiy + 8 ta) yashirin, holat yozuvi bo'sh va qizil emas",
                  not sabablar_yashirin(o) and len(o["xato"]) == 9 and all(o["xato"].values())
                  and o.get("holat") == {"matn": "", "xato": False, "havola": None},
                  (sabablar_yashirin(o), o.get("holat"), o.get("xato")))
            check("Y1c «Yuklanmoqda...», «undefined», «NaN» ko'rinmaydi; JS xatosi yo'q",
                  not o.get("yuklanmoqda") and not o.get("notogri") and not pg.__xato, (o.get("yuklanmoqda"), o.get("notogri"), pg.__xato))
            _ol = (o.get("oblig") or {}).get("matn") or ""
            check("Y1d majburiyatlar: ijara, ish haqi, ta'minotchi (muddati bilan) va «Jami majburiyat 4 000 000 so'm»",
                  (o.get("oblig") or {}).get("display") == "block" and "Ijara (5-kunidan kechikdi!)" in _ol and "Hodim Bekzod ish haqi" in _ol
                  and "Taminotchi A — 01.10.2026 gacha (9 kun kechikdi!)" in _ol and "Jami majburiyat 4 000 000 so'm" in _ol, _ol[:300])
            _so = sorted({y for y, _ in pg.__sorov})
            check("Y1e `/api/dashboard/stats` so'ralmaydi (javobi ishlatilmasdi — ilgari uning xatosi butun sahifani to'xtatardi); qolgan "
                  "15 so'rov — bir martadan", "/api/dashboard/stats" not in _so and all(y in _so for y in BOY)
                  and all(sum(1 for y2, _ in pg.__sorov if y2 == y) == 1 for y in BOY), pg.__sorov)
            check("Y1f grafiklar kanvasda (yozuvsiz)", all(g.get("yozuv") is None and g.get("kanvas") != "none" for g in o["grafik"].values()),
                  o.get("grafik"))
            ctx.close()

        if bolim("Y2"):
            # ══════════════════════════════════════════════════════════════
            section("Y2. Har so'rov × har xato — faqat o'sha blok, aniq sabab bilan")
            # ══════════════════════════════════════════════════════════════
            ctx, pg = kontekst()
            for yol, b in BLOK.items():
                if _YOL and not any(x in yol for x in _YOL):
                    continue
                for tur, xf in XATOLAR.items():
                    if _TUR and tur not in _TUR:
                        continue
                    xav(pg.unroute_all, behavior="ignoreErrors")
                    boy(pg, istisno=(yol,))
                    pg.route(yol_mos(yol), xf)
                    del pg.__xato[:]
                    dash(pg, 500)
                    o = snap(pg)
                    q = o.get("qiymat", {})
                    xatolar = []
                    ist = set(b.get("idlar", [])) | set(b.get("bosh", []))
                    for i in b.get("idlar", []):
                        if q.get(i) != "—":
                            xatolar.append(("«—» emas", i, q.get(i)))
                    for i in b.get("bosh", []):
                        if q.get(i) != "":
                            xatolar.append(("bo'sh emas", i, q.get(i)))
                    if b.get("sabab"):
                        sid, nima = b["sabab"]
                        xv = (o.get("xato") or {}).get(sid) or {}
                        if not (xv.get("korinadi") and xv.get("matn") == matn(nima, tur) and xv.get("rang") == QIZIL):
                            xatolar.append(("sabab", sid, xv))
                    for rid, nima in b.get("royxat", []):
                        ist.add(rid)
                        if q.get(rid) != matn(nima, tur) or (o.get("qator_rang") or {}).get(rid) != QIZIL:
                            xatolar.append(("ro'yxat sababi", rid, q.get(rid), (o.get("qator_rang") or {}).get(rid)))
                    if b.get("izoh"):
                        iid, nima = b["izoh"]
                        ist.add(iid)
                        if q.get(iid) != matn(nima, tur) or (o.get("izoh_rang") or {}).get(iid) != QIZIL:
                            xatolar.append(("izoh", iid, q.get(iid), (o.get("izoh_rang") or {}).get(iid)))
                    if b.get("grafik"):
                        gid, nima = b["grafik"]
                        g = (o.get("grafik") or {}).get(gid) or {}
                        if not (g.get("yozuv") == matn(nima, tur) and g.get("xato") and g.get("kanvas") == "none"):
                            xatolar.append(("grafik", gid, g))
                    if yol == "/api/dashboard/deliveries" and o.get("partialCard") == "none":
                        xatolar.append(("qisman karta yashirin", o.get("partialCard")))
                    if b.get("majburiyat"):
                        ist.add("obligList")
                        ob = o.get("oblig") or {}
                        m = ob.get("matn") or ""
                        if (ob.get("display") != "block" or not m.startswith(matn(b["majburiyat"], tur))
                                or (o.get("qator_rang") or {}).get("obligList") != QIZIL):
                            xatolar.append(("majburiyat sababi", m[:160], (o.get("qator_rang") or {}).get("obligList")))
                        if yol == "/api/obligations/status" and ("Ijara" in m or "Hodim Bekzod" in m or "Taminotchi A — 01.10.2026" not in m
                                                                  or "Jami majburiyat" in m):
                            xatolar.append(("holatsiz: faqat ta'minotchi, jami yo'q", m[:200]))
                        if yol == "/api/suppliers" and ("Taminotchi A" in m or "Ijara (5-kunidan kechikdi!)" not in m
                                                        or "Hodim Bekzod ish haqi" not in m or "Jami majburiyat" in m):
                            xatolar.append(("ta'minotchisiz: ijara va ish haqi, jami yo'q", m[:200]))
                        if yol == "/api/suppliers/due-dates" and ("01.10.2026" in m or "Taminotchi A" not in m
                                                                  or "Jami majburiyat 4 000 000 so'm" not in m):
                            xatolar.append(("muddatsiz: ta'minotchi muddatsiz, jami bor", m[:200]))
                    farq = qiymatlar_ok(o, istisno=ist)
                    if farq:
                        xatolar.append(("boshqa bloklar o'zgardi", farq[:6]))
                    yash = sabablar_yashirin(o, istisno=["xato-umumiy"] + ([b["sabab"][0]] if b.get("sabab") else []))
                    if yash:
                        xatolar.append(("boshqa sabab ko'rindi", yash))
                    h = o.get("holat") or {}
                    u = (o.get("xato") or {}).get("xato-umumiy") or {}
                    kut_u = UMUMIY_SESSIYA if tur == "401_json" else UMUMIY
                    if not (u.get("korinadi") and u.get("matn") == kut_u and u.get("rang") == QIZIL
                            and (o.get("umumiy_havola") == "/login") == (tur == "401_json")):
                        xatolar.append(("umumiy xabar", u, o.get("umumiy_havola")))
                    if h != {"matn": "", "xato": False, "havola": None}:
                        xatolar.append(("holat yozuvi — birinchi yuklashda bo'sh qoladi", h))
                    if o.get("yuklanmoqda") or o.get("notogri") or pg.__xato:
                        xatolar.append(("Yuklanmoqda / undefined / JS", o.get("yuklanmoqda"), o.get("notogri"), pg.__xato[:2]))
                    check(f"Y2 {yol} {tur}: o'sha blok «—» va sabab bilan, qolgani o'z qiymatida", not xatolar, xatolar)
            ctx.close()

        if bolim("Y3"):
            # ══════════════════════════════════════════════════════════════
            section("Y3. Chart.js (internetdan) yuklanmadi")
            # ══════════════════════════════════════════════════════════════
            ctx, pg = kontekst(chart=False)
            boy(pg)
            dash(pg)
            o = snap(pg)
            check("Y3a hamma ma'lumot ko'rinadi (holat afsonasi, usta reytingi, qarzdorlik, … — ilgari grafik xatosi qolganini to'xtatardi)",
                  not qiymatlar_ok(o) and not o.get("yuklanmoqda"), (qiymatlar_ok(o), o.get("yuklanmoqda")))
            check("Y3b grafik o'rnida yozuv: «Buyurtmalar soni» — «Grafik chizilmadi — internet aloqasini tekshiring», doira — «Grafik chizilmadi»",
                  (o["grafik"].get("ordersCountChart") or {}).get("yozuv") == "Grafik chizilmadi — internet aloqasini tekshiring"
                  and (o["grafik"].get("statusChart") or {}).get("yozuv") == "Grafik chizilmadi", o.get("grafik"))
            check("Y3c JS xatosi yo'q; holat yozuvi bo'sh (ma'lumot xatosi emas)", not pg.__xato and (o.get("holat") or {}).get("matn") == "",
                  (pg.__xato, o.get("holat")))
            ctx.close()

        if bolim("Y4"):
            # ══════════════════════════════════════════════════════════════
            section("Y4. Rollar — HAQIQIY server (ruxsatsiz blok yo'q va so'ralmaydi)")
            # ══════════════════════════════════════════════════════════════
            TUZILISH = r"""() => { const b = id => !!document.getElementById(id);
              const g = document.querySelector('.dash-grid2');
              const xs = [...document.querySelectorAll('.card-head h3')].map(h => h.textContent.trim()).filter(x => /Xomashyo xaridlari|Transport xarajatlari/.test(x));
              return {finGrid: b('finGrid'), oblig: b('obligWidget'), xarid: b('purchList'), xarid_jami: b('purch-total'), transport: b('tr-inbound'),
                      taminotchi: b('sup-debt-total'), tayyor: b('fp-total-value'), brak: b('brk-month-count'), brak_ulush: b('brk-foiz'),
                      grid: g ? {yakka: g.classList.contains('yakka'), ustun: getComputedStyle(g).gridTemplateColumns.split(' ').filter(Boolean).length,
                                 kartalar: g.children.length} : null, xarid_sarlavha: xs}; }"""
            ROL_KUT = {
                "dy_a": {"finGrid": True, "oblig": True, "xarid": True, "xarid_jami": True, "transport": True, "taminotchi": True, "tayyor": True,
                         "brak": True, "brak_ulush": True, "grid": {"yakka": False, "ustun": 2, "kartalar": 2},
                         "xarid_sarlavha": ["Xomashyo xaridlari (bu oy)"]},
                "dy_mol": {"finGrid": True, "oblig": True, "xarid": False, "xarid_jami": False, "transport": True, "taminotchi": False,
                           "tayyor": False, "brak": False, "brak_ulush": True, "grid": {"yakka": True, "ustun": 1, "kartalar": 1},
                           "xarid_sarlavha": ["Transport xarajatlari (bu oy)"]},
                "dy_d": {"finGrid": False, "oblig": False, "xarid": False, "xarid_jami": False, "transport": True, "taminotchi": False,
                         "tayyor": False, "brak": False, "brak_ulush": False, "grid": None, "xarid_sarlavha": ["Transport xarajatlari (bu oy)"]},
                "dy_dq": {"finGrid": False, "oblig": True, "xarid": False, "xarid_jami": False, "transport": True, "taminotchi": False,
                          "tayyor": False, "brak": False, "brak_ulush": False, "grid": None, "xarid_sarlavha": ["Transport xarajatlari (bu oy)"]},
                "dy_dt": {"finGrid": False, "oblig": False, "xarid": False, "xarid_jami": False, "transport": True, "taminotchi": False,
                          "tayyor": True, "brak": False, "brak_ulush": False, "grid": {"yakka": True, "ustun": 1, "kartalar": 1},
                          "xarid_sarlavha": ["Transport xarajatlari (bu oy)"]},
                "dy_dk": {"finGrid": False, "oblig": False, "xarid": True, "xarid_jami": True, "transport": True, "taminotchi": True,
                          "tayyor": False, "brak": True, "brak_ulush": False, "grid": {"yakka": True, "ustun": 1, "kartalar": 1},
                          "xarid_sarlavha": ["Xomashyo xaridlari (bu oy)"]},
            }
            for u, kut in ROL_KUT.items():
                ctx, pg = kontekst(user=u)
                # majburiyatlar holati — boy (blok ko'rinadigan bo'lsin); qolgani HAQIQIY server
                boy(pg, faqat=("/api/obligations/status",))
                dash(pg)
                tz = ev(pg, TUZILISH)
                o = snap(pg)
                rad = sorted({(y, h) for y, h in pg.__sorov if h in (401, 403) and not y.startswith("/api/admin/")})
                check(f"Y4 {u}: bloklar ruxsatga mos (ruxsatsizi server chizishida yo'q)", tz == kut, (tz, kut))
                check(f"Y4 {u}: Dashboard so'rovlaridan birortasi rad etilmaydi (403 yo'q — ruxsatsiz blok so'ralmaydi)", not rad, rad)
                check(f"Y4 {u}: sabab yozuvi yo'q, «undefined» / «NaN» / «Yuklanmoqda...» ko'rinmaydi, holat yozuvi bo'sh, JS xatosi yo'q",
                      not sabablar_yashirin(o) and not o.get("notogri") and not o.get("yuklanmoqda") and (o.get("holat") or {}).get("matn") == ""
                      and not pg.__xato, (sabablar_yashirin(o), o.get("notogri"), o.get("yuklanmoqda"), o.get("holat"), pg.__xato))
                if kut["oblig"]:
                    _ob = o.get("oblig") or {}
                    _sup = [y for y, _ in pg.__sorov if y in ("/api/suppliers", "/api/suppliers/due-dates")]
                    _tm = u == "dy_a"
                    check(f"Y4 {u}: majburiyatlar bloki ko'rinadi — ijara va ish haqi (ilgari Moliyachida ta'minotchilar rad etilib BUTUN blok "
                          f"yashirinardi); ta'minotchilar ro'yxati faqat ruxsat bilan so'raladi ({'bor' if _tm else 'yo' + chr(39) + 'q'})",
                          _ob.get("display") == "block" and "Ijara (5-kunidan kechikdi!)" in (_ob.get("matn") or "")
                          and "Hodim Bekzod ish haqi" in (_ob.get("matn") or "") and "yuklanmadi" not in (_ob.get("matn") or "")
                          and _ob.get("taminotchi") == ("1" if _tm else "0") and (bool(_sup) == _tm), (_ob, _sup))
                ctx.close()

        if bolim("Y5"):
            # ══════════════════════════════════════════════════════════════
            section("Y5. «Yangilash» — xato bilan, so'ng tuzalgach")
            # ══════════════════════════════════════════════════════════════
            ctx, pg = kontekst()
            boy(pg)
            dash(pg)
            for yol, tekshir in (("/api/dashboard/debts", lambda o: o["qiymat"].get("debtList") == matn("Qarzdor buyurtmalar", "502_html")
                                                               and o["qiymat"].get("d-total") == "—"
                                                               and (o["xato"].get("xato-qarzdorlik") or {}).get("korinadi")),
                                 ("/api/obligations/status", lambda o: ((o.get("oblig") or {}).get("matn") or "").startswith(
                                     matn("Doimiy majburiyatlar va ish haqi", "502_html"))),
                                 ("/api/dashboard/charts", lambda o: o["qiymat"].get("statusLegend") == matn("Buyurtmalar holati", "502_html"))):
                mos = yol_mos(yol)                     # unroute — AYNAN shu predikat obyekti bilan
                pg.route(mos, XATOLAR["502_html"])
                xav(pg.click, "#dashYangilaBtn")
                pg.wait_for_timeout(1200)
                o = snap(pg)
                _u = (o.get("xato") or {}).get("xato-umumiy") or {}
                check(f"Y5a {yol} 502 da «Yangilash»: blokda sabab, sahifa boshida umumiy xabar, holat yozuvi — «{YANGILANMADI}» (qizil; "
                      f"ilgari qarzdorlik / majburiyatlarda «Yangilandi: …»), qolgan bloklar o'z qiymatida",
                      tekshir(o) and (o.get("holat") or {}).get("matn") == YANGILANMADI and (o.get("holat") or {}).get("xato")
                      and o.get("holat_rang") == QIZIL and _u.get("korinadi") and _u.get("matn") == UMUMIY
                      and not qiymatlar_ok(o, istisno=set(BLOK[yol].get("idlar", [])) | {r for r, _ in BLOK[yol].get("royxat", [])} | {"obligList"}),
                      (o.get("holat"), qiymatlar_ok(o, istisno=set(BLOK[yol].get("idlar", [])) | {"obligList"})))
                xav(pg.unroute, mos)                   # ostidagi boy javob qaytadi
                xav(pg.click, "#dashYangilaBtn")
                pg.wait_for_timeout(1200)
                o = snap(pg)
                h = o.get("holat") or {}
                check(f"Y5b {yol} tuzalgach «Yangilash»: hamma qiymat qaytdi, sabablar yashirin, grafiklar kanvasda, «Yangilandi: SS:DD» "
                      f"(qizil emas)",
                      not qiymatlar_ok(o) and not sabablar_yashirin(o) and re.fullmatch(r"Yangilandi: \d{2}:\d{2}", h.get("matn") or "")
                      and not h.get("xato") and "yuklanmadi" not in ((o.get("oblig") or {}).get("matn") or "")
                      and all(g.get("yozuv") is None and g.get("kanvas") != "none" and not g.get("xato") for g in o["grafik"].values()),
                      (qiymatlar_ok(o), sabablar_yashirin(o), h, o.get("grafik")))
            check("Y5c JS xatosi yo'q", not pg.__xato, pg.__xato)
            ctx.close()

        if bolim("Y6"):
            # ══════════════════════════════════════════════════════════════
            section("Y6. Avtomatik yangilash (har 5 daqiqa)")
            # ══════════════════════════════════════════════════════════════
            ctx, pg = kontekst(soat=True)
            boy(pg)
            dash(pg)
            _h0 = (snap(pg).get("holat") or {}).get("matn")
            xav(pg.click, "#dashYangilaBtn")                 # holat yozuvi to'ldiriladi («Yangilandi: SS:DD»)
            pg.wait_for_timeout(1200)
            _h1 = (snap(pg).get("holat") or {}).get("matn")
            _n0 = sum(1 for y, _ in pg.__sorov if y == "/api/obligations/status")
            _mos = yol_mos("/api/dashboard/debts")
            pg.route(_mos, XATOLAR["tarmoq"])
            xav(pg.clock.fast_forward, "05:01")
            pg.wait_for_timeout(1200)
            o = snap(pg)
            _n1 = sum(1 for y, _ in pg.__sorov if y == "/api/obligations/status")
            _u = (o.get("xato") or {}).get("xato-umumiy") or {}
            check("Y6a 5 daqiqadan keyin: qarzdorlik sababi «internet aloqasi yo'q», sahifa boshida umumiy xabar, holat yozuvi — «"
                  + YANGILANMADI + "» (qizil; birinchi yuklashda bo'sh edi, «Yangilash» dan keyin — vaqt); majburiyatlar ham qayta so'raldi "
                  "(ilgari avtomatik yangilashda yo'q edi)",
                  _h0 == "" and re.fullmatch(r"Yangilandi: \d{2}:\d{2}", _h1 or "")
                  and o["qiymat"].get("debtList") == matn("Qarzdor buyurtmalar", "tarmoq") and _u.get("korinadi") and _u.get("matn") == UMUMIY
                  and (o.get("holat") or {}).get("matn") == YANGILANMADI and (o.get("holat") or {}).get("xato") and _n1 == _n0 + 1,
                  (_h0, _h1, o["qiymat"].get("debtList"), _u, o.get("holat"), _n0, _n1))
            xav(pg.unroute, _mos)                      # ostidagi boy javob qaytadi
            xav(pg.clock.fast_forward, "05:01")
            pg.wait_for_timeout(1200)
            o = snap(pg)
            h = o.get("holat") or {}
            check("Y6b keyingi 5 daqiqada tuzaldi: qiymatlar qaytdi, umumiy xabar yashirin, holat «Yangilandi: SS:DD» (eski «Yangilanmadi» "
                  "qolib ketmaydi)",
                  not qiymatlar_ok(o) and not sabablar_yashirin(o) and re.fullmatch(r"Yangilandi: \d{2}:\d{2}", h.get("matn") or "")
                  and not h.get("xato"), (qiymatlar_ok(o), sabablar_yashirin(o), h))
            ctx.close()

        if bolim("Y7"):
            # ══════════════════════════════════════════════════════════════
            section("Y7. Sessiya tugadi — HAQIQIY server 401")
            # ══════════════════════════════════════════════════════════════
            ctx, pg = kontekst()
            dash(pg)
            xav(ctx.clear_cookies)
            xav(pg.click, "#dashYangilaBtn")
            pg.wait_for_timeout(1500)
            o = snap(pg)
            h = o.get("holat") or {}
            _r401 = sorted({y for y, k in pg.__sorov if k == 401})
            _u = (o.get("xato") or {}).get("xato-umumiy") or {}
            check("Y7a sahifa boshida: «Kirish muddati tugagan — qayta kiring» (havola — kirish sahifasi; ilgari «qayta urinib ko'ring»), "
                  "holat yozuvi — «Yangilanmadi»",
                  _u.get("korinadi") and _u.get("matn") == UMUMIY_SESSIYA and o.get("umumiy_havola") == "/login"
                  and h.get("matn") == YANGILANMADI and h.get("xato"), (_u, o.get("umumiy_havola"), h, _r401))
            check("Y7b bloklarda sabab «kirish muddati tugagan» (yolg'on «0 so'm» / «✓ Qarzdorlik yo'q» emas), «undefined» yo'q",
                  o["qiymat"].get("debtList") == matn("Qarzdor buyurtmalar", "401_json") and o["qiymat"].get("d-total") == "—"
                  and o["qiymat"].get("purchList") == matn("Xomashyo xaridlari", "401_json") and not o.get("notogri") and len(_r401) >= 10,
                  (o["qiymat"].get("debtList"), o["qiymat"].get("purchList"), o.get("notogri"), _r401))
            ctx.close()

        if bolim("Y8"):
            # ══════════════════════════════════════════════════════════════
            section("Y8. Poyga — eski javob kech kelsa tashlanadi")
            # ══════════════════════════════════════════════════════════════
            for yol, eski, yangi, ol in (
                    ("/api/dashboard/debts", dict(BOY["/api/dashboard/debts"], total_debt=1111111),
                     dict(BOY["/api/dashboard/debts"], total_debt=2222222), lambda o: o["qiymat"].get("d-total")),
                    ("/api/obligations/status",
                     {"recurring": [{"icon": "🏛️", "label": "Eski ijara", "due_day": 5, "status": "overdue", "debt": 100}], "employees": []},
                     {"recurring": [{"icon": "🏛️", "label": "Yangi ijara", "due_day": 5, "status": "overdue", "debt": 200}], "employees": []},
                     lambda o: (o.get("oblig") or {}).get("matn"))):
                ctx, pg = kontekst()
                boy(pg, istisno=(yol,))
                ushla = []

                def _ushlovchi(ushla, yangi):
                    # ishlovchi BITTA parametrli bo'lsin (Playwright parametrlar soniga qarab (route, request) ham uzatadi)
                    def _ush(r):
                        if not ushla:
                            ushla.append(r)
                        else:
                            jv(r, 200, yangi)
                    return _ush
                pg.route(yol_mos(yol), _ushlovchi(ushla, yangi))
                xav(pg.goto, BU + "/dashboard")
                pg.wait_for_timeout(900)
                xav(pg.click, "#dashYangilaBtn")
                pg.wait_for_timeout(1200)
                v1 = ol(snap(pg))
                if ushla:
                    xav(jv, ushla[0], 200, eski)
                pg.wait_for_timeout(900)
                v2 = ol(snap(pg))
                if yol == "/api/dashboard/debts":
                    ok = v1 == "2,2 mln so'm" and v2 == "2,2 mln so'm"
                else:
                    ok = "Yangi ijara" in (v1 or "") and "Yangi ijara" in (v2 or "") and "Eski ijara" not in (v2 or "")
                check(f"Y8 {yol}: birinchi javob ushlab turildi, «Yangilash» javobi chizildi; eski javob keyin kelib USTIGA YOZMAYDI "
                      f"(ilgari 2,2 mln → 1,1 mln)", ok and bool(ushla), (v1, v2, len(ushla)))
                ctx.close()

        if bolim("Y9"):
            # ══════════════════════════════════════════════════════════════
            section("Y9. Telefon — hamma blok xato bo'lsa ham sahifa toshmaydi, sabab o'qiladi")
            # ══════════════════════════════════════════════════════════════
            # 390 / 320 — telefon; 800 / 1024 — kompyuter ko'rinishi (yon menyu bilan; uzun holat yozuvi ilgari sarlavhani 0 px gacha
            # siqib, «Yangilash» tugmasini ekrandan chiqarardi — work/k163/holat_probe.py)
            for w, mavzular in ((390, ("light", "dark")), (320, ("light", "dark")), (800, ("light",)), (1024, ("light",))):
                for mavzu in mavzular:
                    ctx, pg = kontekst(w=w, h=844 if w < 700 else 900)
                    for yol in BOY:
                        pg.route(yol_mos(yol), XATOLAR["502_html"])
                    dash(pg)
                    xav(pg.click, "#dashYangilaBtn")      # holat yozuvi — «Yangilanmadi»
                    pg.wait_for_timeout(1200)
                    ev(pg, "(m) => document.documentElement.setAttribute('data-theme', m)", mavzu)
                    pg.wait_for_timeout(300)
                    k = ev(pg, TEMA_KONTRAST, ["#xato-umumiy", "#xato-bugun", "#xato-qarzdorlik", "#debtList .dash-xato-qator",
                                               "#dashYangilandi", "#obligList .dash-xato", "#f-revenue-sub", "#sup-debt-count", "#xato-tayyor"])
                    elar = {kk: v for kk, v in (k or {}).items() if not kk.startswith("__")} if isinstance(k, dict) else {}
                    tb = (k or {}).get("__topbar") or {} if isinstance(k, dict) else {}
                    check(f"Y9 {w}px {mavzu}: sahifa yon tomonga toshmaydi; sabab matnlari va «Yangilanmadi» ko'rinadi, ekran ichida, "
                          f"kontrast ≥ 4.5; yuqori panel toshmaydi, «Yangilash» tugmasi ekranda, sarlavha siqilmaydi (≥ 40 px — «Yangilandi: SS:DD» "
                          f"holatidagidek; ilgari xatoda 800 px da 0 px, tugma 878 px da — work/k163/holat_probe2.py)",
                          isinstance(k, dict) and k.get("__sw", 9999) <= w and len(elar) == 9 and all(
                              v and v["kontrast"] >= 4.5 and v["chap"] >= 0 and v["ong"] <= w for v in elar.values())
                          and not tb.get("toshdi") and (tb.get("tugma_ong") or 9999) <= w and (tb.get("sarlavha_eni") or 0) >= 40, k)
                    ctx.close()

        if bolim("Y10"):
            # ══════════════════════════════════════════════════════════════
            section("Y10. Majburiyatlar — bo'sh holatlar")
            # ══════════════════════════════════════════════════════════════
            BOSH = {"/api/obligations/status": {"recurring": [], "employees": []}, "/api/suppliers": [], "/api/suppliers/due-dates": []}
            for nom, xato_yol in (("bo'sh, xatosiz", None), ("bo'sh, ta'minotchilar 502", "/api/suppliers")):
                ctx, pg = kontekst()
                boy(pg, istisno=tuple(BOSH))
                for yol, v in BOSH.items():
                    if yol == xato_yol:
                        pg.route(yol_mos(yol), XATOLAR["502_html"])
                    else:
                        pg.route(yol_mos(yol), (lambda v: lambda r: jv(r, 200, v))(v))
                dash(pg)
                ob = snap(pg).get("oblig") or {}
                if xato_yol:
                    ok = ob.get("display") == "block" and ob.get("matn") == matn("Ta'minotchilar qarzi", "502_html")
                else:
                    ok = ob.get("display") == "none"
                check(f"Y10 {nom}: " + ("blok sabab bilan KO'RINADI (yashirilsa «majburiyat yo'q» deb o'qilardi), «Jami» yo'q" if xato_yol
                                        else "blok yashirin (avvalgidek)"), ok, ob)
                ctx.close()

        if bolim("Y13"):
            # ══════════════════════════════════════════════════════════════
            section("Y13. «Qisman topshirilgan buyurtmalar» — bo'sh (yashirin) kartada keyin xato")
            # ══════════════════════════════════════════════════════════════
            ctx, pg = kontekst()
            boy(pg, istisno=("/api/dashboard/deliveries",))
            _bosh_yet = dict(BOY["/api/dashboard/deliveries"], partial_count=0, partial_orders=[])
            pg.route(yol_mos("/api/dashboard/deliveries"), lambda r: jv(r, 200, _bosh_yet))
            dash(pg)
            _p0 = snap(pg).get("partialCard")
            pg.route(yol_mos("/api/dashboard/deliveries"), XATOLAR["502_html"])
            xav(pg.click, "#dashYangilaBtn")
            pg.wait_for_timeout(1200)
            o = snap(pg)
            check("Y13 qisman topshirilgan yo'q — karta yashirin; keyin yuklanmasa — karta sabab bilan KO'RINADI (yashirin qolsa «yo'q» deb "
                  "o'qilardi)", _p0 == "none" and o.get("partialCard") != "none"
                  and o["qiymat"].get("partialList") == matn("Qisman topshirilgan buyurtmalar", "502_html"),
                  (_p0, o.get("partialCard"), o["qiymat"].get("partialList")))
            ctx.close()

        check("Y12 JS sahifa xatosi (pageerror) yo'q — butun sinov davomida", not JS_XATO, JS_XATO[:5])
        br.close()
    server.should_exit = True

# ══════════════════════════════════════════════════════════════
section("Y11. Statik — shablon tuzilishi")
# ══════════════════════════════════════════════════════════════
DASH = open(os.path.join(ROOT, "templates", "dashboard.html"), encoding="utf-8").read()
_la = re.search(r"async function loadAll\([^)]*\)\{[\s\S]*?\n\}", DASH)
_la = _la.group(0) if _la else ""
check("Y11a `loadAll` — bitta `Promise.all` emas (`allSettled`), `/api/dashboard/stats` so'rovi yo'q, majburiyatlar ham ichida",
      "Promise.allSettled" in _la and "Promise.all(" not in _la and "fetch('/api/dashboard/stats')" not in DASH
      and "loadObligationsWidget()" in _la,
      _la[:400])
check("Y11b sabab yozuvlari (umumiy + 8) shablonda `hidden` bilan", all(re.search(r'<p class="dash-xato[^"]*" id="' + i + r'"[^>]*\bhidden></p>', DASH)
                                                              for i in XATO_IDLAR), [i for i in XATO_IDLAR if f'id="{i}"' not in DASH])
check("Y11c ruxsat shartlari: xarid (kirim), ta'minotchi, tayyor, qaytarish, hisobot; majburiyatlarda `data-taminotchi`",
      all(x in DASH for x in ("current_user.ruxsat('kirim', 'korish')", "{% if current_user.ruxsat('taminotchi', 'korish') %}",
                              "current_user.ruxsat('tayyor', 'korish')", "current_user.ruxsat('qaytarish', 'korish')",
                              "current_user.ruxsat('hisobot', 'korish')", "data-taminotchi=")))
check("Y11d avtomatik yangilash — `loadAll` (har 5 daqiqa)", "setInterval(loadAll,5*60*1000);" in DASH)

print("\n" + "=" * 70)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
