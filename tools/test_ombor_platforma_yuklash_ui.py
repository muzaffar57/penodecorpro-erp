#!/usr/bin/env python3
"""
test_ombor_platforma_yuklash_ui.py — kech139 (zip 166): «Omborxona» va «Platforma» sahifalari bitta so'rov xatosida QOTMAYDI, yolg'on
qiymat («Yangi · 0», oldingi ochilishning «21 400 000 so'm» jami, abadiy «Yuklanmoqda…») ko'rsatmaydi, «Aloqa telefoni» yuklanmasa
«Saqlash» serverdagi telefonni O'CHIRMAYDI, tez almashtirilgan tanlovning kech kelgan javobi yangisining ustiga yozilmaydi, amal (saqlash,
bloklash, uzaytirish, o'chirish …) xatosida — internet uzilsa ham — sabab ko'rinadi, «Uzaytirish» ikki marta bosilsa muddat ikki marta
uzaymaydi, xaridni bekor qilish tugmalari faqat ruxsat bilan — HAQIQIY brauzerda (Chromium, Playwright), HAQIQIY lokal server bilan
(uvicorn, test bazasi) O'LCHANADI. Ma'lumot — `tools/test_c_telefon.py` ZANJIR_JS (dasturning o'z API si orqali to'liq ish zanjiri) +
ikkinchi penoplast + platforma aloqa telefoni + mijoz korxonalar B (2 murojaat bilan) va C (bloklangan).

NIMA UCHUN KERAK (O'LCHANGAN — work/k166/olchov166.py, zip 165 kodi; egasi tanlovi 10.10 «Sahifalar qotmasin»; reja — zip 164 Moliya +
Hisobotlar, zip 165 KPI + Loyihalar, zip 166 Omborxona + Platforma)
  * Platforma: korxonalar / raqamlar so'rovi yiqilsa «Aloqa telefoni» BO'SH qolardi va «Saqlash» («✓ Saqlandi») serverdagi telefonni
    O'CHIRARDI; raqamlar abadiy «Yuklanmoqda… —»; murojaatlar yuklanmasa «Yangi · 0»; xatolar ro'yxati tarmoqda abadiy «Yuklanmoqda…»;
    3 poyga (murojaat holati, xatolar korxona tanlovi, «Muddatni uzaytirish» oldindan ko'rishi — «+12 oy» tanlangan, «+1 oy» sanasi);
    internet uzilsa bloklash / uzaytirish / ochish / parol / yangi korxona / telefon — jim;
  * Omborxona: «Xaridlar tarixi» — ikki so'rovdan biri yiqilsa ikkalasi sababsiz «Yuklashda xato», qayta ochilganda OLDINGI jami
    qolardi; «Ombor harakatlari» — «Tanlangan davr — jami» jimgina yo'qolardi (tarmoqda ro'yxat ham), «Yana yuklash» xatosida tugma
    «Yuklanmoqda…» da qotardi; internet uzilsa narx, chegara, o'chirish, Telegram hisobotlari — jim (502 da hisobotlar ham), rasm —
    inglizcha «Failed to fetch»; xaridni bekor qilish tugmalari «O'chirish» ruxsatisiz rolga ham chizilardi (bosilsa 403).
BO'LIMLAR
  I1 «Xaridlar tarixi» — hammasi yuklandi;  I2 — 2 so'rov × 5 xato (502 HTML, 500 JSON, tarmoq, 401, 403): o'sha blokda sabab, qolgani
  o'z qiymatida;  I3 — OK ochilgandan keyin xato bilan qayta ochish: eski raqam qolmaydi;  I4 — «Yana yuklash» xatosi;
  I5 «Ombor harakatlari» — ro'yxat × 5, davr jami × 5, «Yana yuklash» xatosi;  I6 — 12 amal × 4 xato (tarmoq, 502, 401, 403);
  I7 — rollar (HAQIQIY server): xaridni bekor qilish tugmalari faqat «Xomashyo kirimi: O'chirish» bilan;
  P1 Platforma — hammasi yuklandi;  P2 — 4 so'rov × 5 xato;  P3 — «Aloqa telefoni»: yuklanmasa «Saqlash» yopiq va serverdagi telefon
  O'ZGARMAYDI (HAQIQIY server), saqlash xatosi — sabab;  P4 — 3 poyga;  P5 — oldindan ko'rish × 5 xato + server rad sababi;
  P6 — 8 amal × 4 xato;  P7 — «Uzaytirish» va «Yaratish» ikki marta bosilsa — bitta so'rov (HAQIQIY server: muddat bir marta uzayadi);
  P8 — sabablar ro'yxati yuklanmasa «Bloklash» oynasida tugma yopiq;
  T  telefon 390 / 320 px (kunduzgi / tungi): hamma so'rov xato — sahifa toshmaydi, sabab ekranda va o'qiladi (kontrast ≥ 4.5);
  S  statik.
REJIMLAR: SQLite (odatiy); `PG_URL` bilan PostgreSQL. Asl kodga (zip 165) qarshi QULAMAYDI — yiqiladi.
TANLOV (mutatsiya sinovlari uchun; odatiy — HAMMASI): OP_BOLIM=I2,P2; OP_YOL=purchase-stats,summary; OP_TUR=500_json; OP_AMAL=narx,blokla.
ISHLATISH: python3 tools/test_ombor_platforma_yuklash_ui.py
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


_BOLIM = {x for x in (os.environ.get("OP_BOLIM") or "").split(",") if x}
_YOL = [x for x in (os.environ.get("OP_YOL") or "").split(",") if x]
_TUR = {x for x in (os.environ.get("OP_TUR") or "").split(",") if x}
_AMAL = {x for x in (os.environ.get("OP_AMAL") or "").split(",") if x}


def bolim(nom):
    return not _BOLIM or nom in _BOLIM


def tanlangan(yol, tur):
    return (not _YOL or any(x in yol for x in _YOL)) and (not _TUR or tur in _TUR)


def amal_tanlangan(nom, tur):
    return (not _AMAL or nom in _AMAL) and (not _TUR or tur in _TUR)


def oqi(nom):
    try:
        with open(os.path.join(ROOT, "templates", nom), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def funksiya(src, nom):
    m = re.search(r"(async\s+)?function\s+" + nom + r"\s*\(", src)
    if not m:
        return ""
    j = src.find("{", m.end())
    d = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            d += 1
        elif src[k] == "}":
            d -= 1
            if d == 0:
                return src[m.start():k + 1]
    return ""


# ══════════════════════════════════════════════════════════════
section("S. Statik — inventory.html, platforma.html, base.html")
# ══════════════════════════════════════════════════════════════
INV, PLT, BASE = oqi("inventory.html"), oqi("platforma.html"), oqi("base.html")
_xom = r"fetch\([^;]*?\)\s*\.then\(\s*r\s*=>\s*r\.(json|ok)"
check("S1 Omborxona va Platforma: xom `fetch(…).then(r => r.json())` (xato JSON chizilardi / jimgina tashlanardi) yo'q",
      not re.search(_xom, INV) and not re.search(_xom, PLT), (re.findall(r"[^\n]{0,60}" + _xom, INV)[:3], re.findall(r"[^\n]{0,60}" + _xom, PLT)[:3]))
check("S2 Platforma «Aloqa telefoni»: maydon va «Saqlash» boshida YOPIQ (`disabled`), saqlash — faqat yuklangan telefon bilan "
      "(`PL.telefonYuklandi`)",
      re.search(r'id="plTelefon"[^>]*disabled', PLT) is not None and re.search(r'id="plTelefonSaqla"[^>]*disabled', PLT) is not None
      and "PL.telefonYuklandi" in funksiya(PLT, "plTelefonSaqla"), "")
check("S3 Omborxona «Xaridlar tarixi»: ikki blok alohida (`Promise.allSettled`); xaridni / kirimni bekor qilish tugmalari — ruxsat bilan "
      "(`data-ochirish`, «Kirim hujjatini bekor qilish» — `kirim: ochirish`)",
      "Promise.allSettled([phJamiYukla(raqam), phRoyxatYukla(raqam)])" in funksiya(INV, "openPurchaseHistory")
      and "{% if current_user.ruxsat('kirim', 'ochirish') %} data-ochirish=\"1\"{% endif %}" in INV
      and re.search(r"\{% if current_user\.ruxsat\('kirim', 'ochirish'\) %\}\s*<div[^>]*>\s*<button id=\"phDrawerBekor\"", INV) is not None, "")
check("S4 base.html: `amalSababi` (amal xatosi sababi) bor; `yukOl` ikkinchi argumentga javobni beradi (sarlavhalar — `X-Jami`)",
      bool(funksiya(BASE, "amalSababi")) and "javob.r = r" in funksiya(BASE, "yukOl"), "")
_js_izoh = [m for m in re.findall(r"<script>([\s\S]*?)</script>", INV + PLT + BASE) if re.search(r"//[^\n]*\{%", m)]
check("S5 `<script>` ichidagi JS izohida Jinja tegi (`{% … %}`) yo'q (kech137: sahifa 500)", not _js_izoh, len(_js_izoh))

try:
    from playwright.sync_api import sync_playwright
    PW_BOR, _pw_xato = True, ""
except Exception as _e:                    # noqa: BLE001
    PW_BOR, _pw_xato = False, f"{type(_e).__name__}: {_e}"

PG_BAZA = "ombor_platforma_yuklash_ui166_test"
_T = tempfile.mkdtemp(prefix="op_ui_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'op_ui_test.db')}"
for _k in ("TENANT_FILTER", "TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID"):
    os.environ.pop(_k, None)

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, Rol             # noqa: E402

PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "op_a", PAROL, UserRole.ADMIN, "Namuna Dekor", company_id=1)
    _pa = auth.create_user(s, "op_pa", PAROL, UserRole.ADMIN, "Platforma Admin", company_id=1)
    _pa.is_platform_admin = True
    auth.create_user(s, "op_men", PAROL, UserRole.MANAGER, "OP menejer", company_id=1)
    auth.create_user(s, "op_omb", PAROL, UserRole.WAREHOUSE, "OP omborchi", company_id=1)
    auth.create_user(s, "op_kirim", PAROL, UserRole.MANAGER, "OP kirimchi", company_id=1)
_r = Rol(company_id=1, nom="OP166 kirimchi", kod=None, tavsif="",
         ruxsatlar=json.dumps({"material": ["korish"], "kirim": ["korish", "yaratish"]}))
s.add(_r)
s.flush()
s.query(User).filter(User.username == "op_kirim").first().rol_id = _r.id
s.commit()
s.close()

_src_tel = ""
try:
    with open(os.path.join(ROOT, "tools", "test_c_telefon.py"), encoding="utf-8") as _f:
        _src_tel = _f.read()
except OSError:
    pass


def _js_ol(nom):
    i = _src_tel.find(nom + ' = r"""')
    if i < 0:
        return ""
    i += len(nom + ' = r"""')
    return _src_tel[i:_src_tel.find('"""', i)]


ZANJIR_JS = _js_ol("ZANJIR_JS")
CHART_ORINBOSAR = _js_ol("CHART_ORINBOSAR") or "window.Chart = function () { return {destroy() {}, update() {}}; };"

SABAB = {"502_html": "server javob bermadi, sahifani yangilang",
         "500_json": "server javob bermadi, sahifani yangilang",
         "tarmoq": "internet aloqasi yo'q, sahifani yangilang",
         "401_json": "kirish muddati tugagan, qayta kiring",
         "403_json": "ko'rish ruxsati yo'q"}
AMAL = {"502_html": "server javob bermadi — sahifani yangilab tekshiring",
        "500_json": "server javob bermadi — sahifani yangilab tekshiring",
        "tarmoq": "internet aloqasi yo'q — sahifani yangilab tekshiring",
        "401_json": "kirish muddati tugagan, qayta kiring",
        "403_json": "Ruxsat yo'q"}
SESSIYA = "⚠️ Kirish muddati tugagan — qayta kiring"
QIZIL = "rgb(185, 28, 28)"
TEL = "+998 90 111 22 33"
TEL_QOSHIMCHA = " («Saqlash» yopiq — joriy telefon ko'rinmaguncha o'zgartirilmaydi)"
AMAL_TURLAR = ("tarmoq", "502_html", "401_json", "403_json")


def matn(nima, tur):
    return f"⚠️ {nima} yuklanmadi — {SABAB[tur]}"


def bs(x):
    return re.sub(r"\s+", "", x or "")


INV_SNAP = r"""() => {
  const ko = e => !!e && !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length) && !e.hidden && getComputedStyle(e).visibility !== 'hidden';
  const t = id => { const e = document.getElementById(id); return e ? {v: ko(e), t: (e.innerText || e.textContent || '').replace(/\s+/g, ' ').trim(), c: getComputedStyle(e).color} : null; };
  const q = document.querySelector('#hist-list .yuk-xato-qator'), mq = document.querySelector('#mv-list .yuk-xato-qator');
  const ov = document.getElementById('invToastOverlay');
  const yb = document.querySelector('#mvYana button'), pb = document.querySelector('#phYana button');
  return {tot: t('hist-total'), mat: t('hist-by-material'), xs: t('xato-hist-stat'), list: t('hist-list'),
          list_rang: q ? getComputedStyle(q).color : null, trash: document.querySelectorAll('#hist-list button[onclick^="deletePurchase"]').length,
          mv: t('mv-list'), mv_rang: mq ? getComputedStyle(mq).color : null, mvj: t('mvDavrJamiXato'), mvj_bor: !!document.getElementById('mvDavrJami'),
          mv_yana: yb ? [yb.disabled, yb.innerText.trim()] : null, ph_yana: pb ? [pb.disabled, pb.innerText.trim()] : null,
          toast: (ov && ov.style.display !== 'none') ? (document.getElementById('invToastText').innerText || '').replace(/\s+/g, ' ').trim() : '',
          tk: t('tk-xato'), sess: t('yukSessiya')};
}"""

PL_SNAP = r"""() => {
  const ko = e => !!e && !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length) && !e.hidden && getComputedStyle(e).visibility !== 'hidden';
  const t = id => { const e = document.getElementById(id); return e ? {v: ko(e), t: (e.innerText || e.textContent || '').replace(/\s+/g, ' ').trim(), c: getComputedStyle(e).color} : null; };
  const tel = document.getElementById('plTelefon'), tb = document.getElementById('plTelefonSaqla');
  const rang = id => { const q = document.querySelector('#' + id + ' .yuk-xato-qator'); return q ? getComputedStyle(q).color : null; };
  const m = (document.querySelector('.erp-main') || document.body).innerText || '';
  return {raq: t('plRaqamlar'), xraq: t('xato-pl-raqam'), kart: t('plKartalar'), kart_rang: rang('plKartalar'),
          chip: [...document.querySelectorAll('#plChiplar .pl-chip')].map(b => b.innerText.trim()),
          tel: tel ? {qiymat: tel.value, yopiq: tel.disabled, tugma_yopiq: tb.disabled} : null, xtel: t('xato-pl-telefon'),
          mp: t('mpRoyxat'), mp_rang: rang('mpRoyxat'), mpson: [...document.querySelectorAll('#mpChiplar [data-son]')].map(s => s.textContent.trim()),
          xt: t('xtRoyxat'), xt_rang: rang('xtRoyxat'), sess: t('yukSessiya'), tel_natija: t('plTelefonNatija'),
          yuklanmoqda: (m.match(/Yuklanmoqda/g) || []).length};
}"""

KONTRAST = r"""() => {
  const rgba = c => { const m = (c.match(/[\d.]+/g) || []).map(Number); return [m[0] || 0, m[1] || 0, m[2] || 0, m.length > 3 ? m[3] : 1]; };
  const fonEl = e => { for (let p = e; p; p = p.parentElement) { const st = getComputedStyle(p);
                         const c = rgba(st.backgroundColor); if (c[3] > 0) return c; }
                       return rgba(getComputedStyle(document.documentElement).backgroundColor); };
  const lum = c => { const [r, g, b] = c.slice(0, 3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
                     return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const kon = (a, b) => { const x = lum(a), y = lum(b); return Math.round(100 * (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)) / 100; };
  const natija = [];
  document.querySelectorAll('.yuk-xato, .yuk-xato-qator').forEach(e => {
    if (!(e.offsetWidth || e.offsetHeight) || e.hidden) return;
    const r = e.getBoundingClientRect();
    natija.push({id: e.id || (e.parentElement && e.parentElement.id) || e.className, kontrast: kon(rgba(getComputedStyle(e).color), fonEl(e)),
                 chap: Math.round(r.left), ong: Math.round(r.right), toshgan: e.scrollWidth > e.clientWidth + 1});
  });
  return {el: natija, vw: innerWidth, sw: document.documentElement.scrollWidth};
}"""

MSG_USHLA = r"""() => { if (window.__msgUshla) return; window.__msgUshla = true; window.__msg = [];
  const o = window.showMsg; window.showMsg = function (t, ty) { window.__msg.push([String(t), ty]); }; }"""

section("0. Tayyorgarlik")
check("0a Python `playwright` bor va ish zanjiri (`tools/test_c_telefon.py` ZANJIR_JS) topildi", PW_BOR and len(ZANJIR_JS) > 1000, _pw_xato)

import uvicorn                                     # noqa: E402


def yol_mos(yol):
    if yol.startswith("/api/"):
        return lambda url: urlparse(url).path == yol
    return lambda url: urlparse(url).path.endswith(yol)


def jv(r, holat, tana, sarlavha=None):
    r.fulfill(status=holat, body=json.dumps(tana), content_type="application/json", headers=sarlavha or {})


XATOLAR = {
    "502_html": lambda r: r.fulfill(status=502, body="<html><body>Bad Gateway</body></html>", content_type="text/html"),
    "500_json": lambda r: jv(r, 500, {"detail": "Ichki xato"}),
    "tarmoq": lambda r: r.abort("failed"),
    "401_json": lambda r: jv(r, 401, {"detail": "Iltimos, tizimga kiring"}),
    "403_json": lambda r: jv(r, 403, {"detail": "Ruxsat yo'q"}),
}

if PW_BOR and ZANJIR_JS:
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
    check("0b lokal server ishga tushdi", server.started)
    BU = f"http://127.0.0.1:{port}"

    with sync_playwright() as pw:
        _exe = None
        for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                "chrome-linux", "chrome"))):
            _exe = _y
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()

        def xav(f, *a, **k):
            """Brauzer amali — element topilmasa (asl kodda / mutatsiyada) sinov QULAMAYDI, tekshiruv yiqiladi."""
            try:
                return f(*a, **k)
            except Exception as ex:        # noqa: BLE001
                print(f"    (amal bajarilmadi: {getattr(f, '__name__', f)} {a[:1]} — {type(ex).__name__})")
                return None

        def kontekst(user="op_a", w=1440, h=900, parol=PAROL):
            tel = w < 700
            ctx = br.new_context(viewport={"width": w, "height": h}, is_mobile=tel, has_touch=tel, timezone_id="Asia/Tashkent",
                                 locale="uz-UZ")
            ctx.set_default_timeout(20000)

            def tashqi(r):
                u = r.request.url
                if re.search(r"chart(\.umd)?(\.min)?\.js", u, re.I):
                    return r.fulfill(status=200, content_type="application/javascript", body=CHART_ORINBOSAR)
                if u.startswith("https://fonts.googleapis.com/"):
                    return r.fulfill(status=200, content_type="text/css", body="")
                return r.fulfill(status=204, body="")
            ctx.route(re.compile(r"^https://.*"), tashqi)
            pg = ctx.new_page()
            xav(pg.goto, BU + "/login")
            xav(pg.fill, "input[name=username]", user)
            xav(pg.fill, "input[name=password]", parol)
            xav(pg.press, "input[name=password]", "Enter")
            xav(pg.wait_for_load_state, "networkidle")
            pg.close()
            return ctx

        def tana(r):
            """So'rov tanasi matni (rasm — ikkilik: `post_data` UnicodeDecodeError beradi — bo'sh)."""
            try:
                return r.post_data or ""
            except Exception:              # noqa: BLE001
                return ""

        def sahifa(ctx):
            pg = ctx.new_page()
            pg.__xato = []
            pg.__sorov = []
            pg.on("pageerror", lambda e: pg.__xato.append(str(e)[:300]))
            pg.on("request", lambda r: pg.__sorov.append((r.method, r.url.replace(BU, ""), tana(r))) if "/api/" in r.url else None)
            return pg

        def och(pg, url, kut=1300):
            xav(pg.goto, BU + url, wait_until="networkidle")
            pg.wait_for_timeout(kut)

        def ev(pg, kod, arg=None):
            try:
                return pg.evaluate(kod, arg) if arg is not None else pg.evaluate(kod)
            except Exception as ex:        # noqa: BLE001
                return {"js_xato": str(ex)[:300]}

        def tt(o, k):
            e = (o or {}).get(k) if isinstance(o, dict) else None
            return e["t"] if isinstance(e, dict) else None

        def vv(o, k):
            e = (o or {}).get(k) if isinstance(o, dict) else None
            return bool(isinstance(e, dict) and e["v"])

        def sessiya_ok(o, tur):
            ss = (o or {}).get("sess") or {}
            return (ss.get("v") and ss.get("t") == SESSIYA) if tur == "401_json" else not ss.get("v")

        CTX = {u: kontekst(u) for u in ("op_a", "op_pa", "op_men", "op_omb", "op_kirim")}
        _tk = datetime.datetime.utcnow() + datetime.timedelta(hours=5)
        K = {"m": "Namuna", "sana": _tk.strftime("%Y-%m-%d"), "yil": _tk.year, "oy": _tk.month,
             "muddat": (_tk + datetime.timedelta(days=9)).strftime("%Y-%m-%d")}
        pg = sahifa(CTX["op_a"])
        och(pg, "/", 300)
        try:
            Z = pg.evaluate(ZANJIR_JS, K)
        except Exception as _e:            # noqa: BLE001
            Z = {"yiqilgan": [["istisno", 0, str(_e)[:300]]], "L": []}
        P25 = ev(pg, """async () => { const r = await fetch('/api/inventory', {method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({item_name: 'Namuna Penoplast 25', category: 'Penoplast', unit: 'blok', stock_quantity: 0, min_stock: 0,
                                  is_penoplast: true, is_default_penoplast: false, volume_per_unit: 1.0})}); return r.status; }""")
        pg.close()
        # Platforma: aloqa telefoni, mijoz korxona B (2 murojaat) va C (bloklangan)
        pg = sahifa(CTX["op_pa"])
        och(pg, "/", 300)
        PQ = ev(pg, """async (tel) => {
            const fd = new FormData(); fd.append('telefon', tel);
            const t = await fetch('/api/platform/contact-phone', {method: 'POST', body: fd});
            const yarat = async (nom, login) => { const f = new FormData(); f.append('name', nom); f.append('admin_username', login);
                const r = await fetch('/api/platform/companies', {method: 'POST', body: f}); return [r.status, await r.json()]; };
            const b = await yarat('Mijoz Korxona B', 'op_mijoz_b'), c = await yarat('Mijoz Korxona C', 'op_mijoz_c');
            const fb = new FormData(); fb.append('sabab', "To'lov qilinmagan");
            const bl = await fetch('/api/platform/companies/' + c[1].company.id + '/block', {method: 'POST', body: fb});
            return {tel: t.status, b: b[0], b_id: b[1].company.id, b_parol: b[1].admin.password, c: c[0], c_id: c[1].company.id, blok: bl.status}; }""", TEL)
        pg.close()
        MJ = None
        if isinstance(PQ, dict) and PQ.get("b_parol"):
            ctxb = kontekst("op_mijoz_b", parol=PQ["b_parol"])
            pg = sahifa(ctxb)
            och(pg, "/", 300)
            MJ = ev(pg, """async () => { const r = []; for (const [t, m] of [['savol', 'OP166 savol: ombor qoldigi'], ['xato', 'OP166 xato: hisobot']]) {
                const fd = new FormData(); fd.append('turi', t); fd.append('matn', m); fd.append('sahifa', '/inventory');
                const x = await fetch('/api/murojaatlar', {method: 'POST', body: fd}); r.push(x.status); } return r; }""")
            pg.close()
            ctxb.close()
        check("0c ish zanjiri: hamma qadam 2xx; ikkinchi penoplast; platforma telefoni, mijoz korxona B (2 murojaat), C (bloklangan)",
              not Z.get("yiqilgan") and len(Z.get("L") or []) >= 50 and P25 == 200 and isinstance(PQ, dict)
              and (PQ.get("tel"), PQ.get("b"), PQ.get("c"), PQ.get("blok")) == (200, 200, 200, 200) and MJ == [200, 200],
              [Z.get("yiqilgan"), len(Z.get("L") or []), P25, PQ, MJ])
        B_ID = (PQ or {}).get("b_id") if isinstance(PQ, dict) else None
        C_ID = (PQ or {}).get("c_id") if isinstance(PQ, dict) else None

        def ushla_yasa(ushla, shart):
            """Birinchi mos so'rovni USHLAB turadi (poyga sinovi), qolganlari o'tadi. Ishlovchi — BITTA parametrli (kech138b)."""
            def _tut(r):
                if shart(r.request.url) and not ushla:
                    ushla.append(r)
                else:
                    r.continue_()
            return _tut

        def ochiq_inv(user="op_a"):
            pg_ = sahifa(CTX[user])
            och(pg_, "/inventory", 900)
            return pg_

        # ══════════════════════════════════════════════════════════════
        # OMBORXONA
        # ══════════════════════════════════════════════════════════════
        I_ASL = {}
        IDS = {}
        if any(bolim(b) for b in ("I1", "I2", "I3", "I4", "I6", "I7")):
            section("I1. Omborxona — «Xaridlar tarixi» hammasi yuklandi")
            pg = ochiq_inv()
            IDS = ev(pg, """() => { const r = [...document.querySelectorAll('.mat-row')];
                const id = el => { const m = (el.querySelector('[id^="price-"]') || {}).id || ''; return Number(m.split('-')[1]) || null; };
                const d = document.querySelector('button[onclick^="setDefaultPenoplast"]');
                return {mat: id(r[1] || r[0]), def: d ? Number(d.getAttribute('onclick').match(/\\d+/)[0]) : null}; }""") or {}
            ev(pg, "() => { openPurchaseHistory(); }")
            pg.wait_for_timeout(1300)
            I_ASL = ev(pg, INV_SNAP) or {}
            PH = ev(pg, "() => ({p: (phAllPurchases.find(p => !p.receipt_id) || {}).id, r: (phAllPurchases.find(p => p.receipt_id) || {}).receipt_id})") or {}
            IDS.update(PH if isinstance(PH, dict) else {})
            check("I1a jami «21 400 000 so'm», material bo'yicha ro'yxat, xaridlar ro'yxati va «Ko'rsatilgan: N / N»; sabab yozuvi yashirin; "
                  "admin — bekor qilish tugmalari bor",
                  bs(tt(I_ASL, "tot")) == bs("21 400 000 so'm") and "Sement M400" in (tt(I_ASL, "mat") or "")
                  and "Ko'rsatilgan:" in (tt(I_ASL, "list") or "") and "Sement M400" in (tt(I_ASL, "list") or "")
                  and not vv(I_ASL, "xs") and I_ASL.get("trash", 0) >= 3 and not pg.__xato,
                  (tt(I_ASL, "tot"), (tt(I_ASL, "mat") or "")[:80], (tt(I_ASL, "list") or "")[:80], I_ASL.get("xs"), I_ASL.get("trash"), pg.__xato))
            check("I1b sinov ma'lumoti: oddiy material, ikkinchi penoplast («Asosiy qilish»), yakka xarid va kirim hujjati topildi",
                  all(IDS.get(k) for k in ("mat", "def", "p", "r")), IDS)
            pg.close()

        if bolim("I2"):
            section("I2. «Xaridlar tarixi» — har so'rov × 5 xato: o'sha blokda sabab, qolgani o'z qiymatida")
            for yol, nima in (("/api/inventory/purchase-stats", "Bu oy jami xarid"), ("/api/inventory/purchases", "Xaridlar ro'yxati")):
                for tur, xf in XATOLAR.items():
                    if not tanlangan(yol, tur):
                        continue
                    pg = ochiq_inv()
                    pg.route(yol_mos(yol), xf)
                    ev(pg, "() => { openPurchaseHistory(); }")
                    pg.wait_for_timeout(1300)
                    o = ev(pg, INV_SNAP) or {}
                    x = []
                    if yol.endswith("purchase-stats"):
                        if tt(o, "tot") != "—" or tt(o, "mat") != "":
                            x.append(("jami «—», materiallar bo'sh", tt(o, "tot"), tt(o, "mat")))
                        if not (vv(o, "xs") and tt(o, "xs") == matn(nima, tur) and (o.get("xs") or {}).get("c") == QIZIL):
                            x.append(("jami sababi", o.get("xs")))
                        if bs(tt(o, "list")) != bs(tt(I_ASL, "list")) or o.get("trash") != I_ASL.get("trash"):
                            x.append(("ro'yxat o'z qiymatida", (tt(o, "list") or "")[:80]))
                    else:
                        if not (tt(o, "list") == matn(nima, tur) and o.get("list_rang") == QIZIL):
                            x.append(("ro'yxat sababi", tt(o, "list"), o.get("list_rang")))
                        if bs(tt(o, "tot")) != bs(tt(I_ASL, "tot")) or bs(tt(o, "mat")) != bs(tt(I_ASL, "mat")) or vv(o, "xs"):
                            x.append(("jami o'z qiymatida", tt(o, "tot"), o.get("xs")))
                    if not sessiya_ok(o, tur):
                        x.append(("sessiya xabari", o.get("sess")))
                    if pg.__xato:
                        x.append(("JS xatosi", pg.__xato[:2]))
                    check(f"I2 {yol} {tur}: «{nima}» — sabab, qolgani o'z qiymatida", not x, x)
                    pg.close()

        if bolim("I3"):
            section("I3. «Xaridlar tarixi» — OK ochilgandan keyin xato bilan qayta ochish: eski raqam qolmaydi")
            for yol in ("/api/inventory/purchase-stats", "/api/inventory/purchases"):
                for tur in ("502_html", "tarmoq"):
                    if not tanlangan(yol, tur):
                        continue
                    pg = ochiq_inv()
                    ev(pg, "() => { openPurchaseHistory(); }")
                    pg.wait_for_timeout(1200)
                    b1 = ev(pg, INV_SNAP) or {}
                    ev(pg, "() => { closePurchaseHistory(); }")
                    pg.route(yol_mos(yol), XATOLAR[tur])
                    ev(pg, "() => { openPurchaseHistory(); }")
                    pg.wait_for_timeout(1200)
                    o = ev(pg, INV_SNAP) or {}
                    if yol.endswith("purchase-stats"):
                        ok_ = (bs(tt(b1, "tot")) == bs("21 400 000 so'm") and tt(o, "tot") == "—" and tt(o, "mat") == ""
                               and tt(o, "xs") == matn("Bu oy jami xarid", tur))
                    else:
                        ok_ = (tt(o, "list") == matn("Xaridlar ro'yxati", tur) and bs(tt(o, "tot")) == bs(tt(b1, "tot")) and o.get("trash") == 0)
                    check(f"I3 {yol} {tur}: qayta ochilganda oldingi ochilish raqami / ro'yxati qolmaydi, sabab ko'rinadi", ok_,
                          (tt(b1, "tot"), tt(o, "tot"), (tt(o, "mat") or "")[:60], tt(o, "xs"), (tt(o, "list") or "")[:80]))
                    pg.close()

        if bolim("I3") and not _TUR and not _YOL:
            ushla = []
            pg = ochiq_inv()
            pg.route(yol_mos("/api/inventory/purchases"), ushla_yasa(ushla, lambda u: True))
            ev(pg, "() => { openPurchaseHistory(); }")
            pg.wait_for_timeout(500)
            ev(pg, "() => { closePurchaseHistory(); openPurchaseHistory(); }")
            pg.wait_for_timeout(1100)
            for r in ushla:
                xav(jv, r, 200, [{"id": 99999, "inventory_id": 1, "item_name": "ESKI XARID", "quantity": 1, "unit": "kg", "price_per_unit": 1,
                                  "total_amount": 1, "purchased_at": "2026-01-01T10:00:00", "purchased_by": "op", "notes": None,
                                  "receipt_id": None}], {"X-Jami": "1", "X-Keyingi": "1"})
            pg.wait_for_timeout(800)
            o = ev(pg, INV_SNAP) or {}
            check("I3c poyga: birinchi ochilishning ro'yxat javobi ushlandi → oyna yopilib qayta ochildi → eski javob keyin keldi: ro'yxat yangisi",
                  len(ushla) == 1 and "ESKI XARID" not in (tt(o, "list") or "") and bs(tt(o, "list")) == bs(tt(I_ASL, "list")),
                  (len(ushla), (tt(o, "list") or "")[:100]))
            pg.close()

        def soxta_xaridlar(n, bosh):
            return [{"id": 90000 + bosh + i, "inventory_id": 1, "item_name": f"Soxta xarid {bosh + i}", "quantity": 1, "unit": "kg",
                     "price_per_unit": 1000, "total_amount": 1000, "purchased_at": "2026-10-01T10:00:00", "purchased_by": "op",
                     "notes": None, "receipt_id": None} for i in range(n)]

        def soxta_harakatlar(n, bosh):
            return [{"id": 90000 + bosh + i, "inventory_id": 1, "item_name": f"Soxta material {bosh + i}", "movement_type": "out",
                     "quantity": 1, "unit": "kg", "reason": f"Soxta sabab {bosh + i}", "order_id": None,
                     "performed_by": "op", "created_at": f"2026-10-01T10:{(bosh + i) % 60:02d}:00"} for i in range(n)]

        def yana_yasa(soxta, tur):
            def _h(r):
                if "offset=0" in r.request.url:
                    return jv(r, 200, soxta(100, 0), {"X-Jami": "150", "X-Keyingi": "100"})
                return XATOLAR[tur](r)
            return _h

        if bolim("I4"):
            section("I4. «Xaridlar tarixi» — «Yana yuklash» xatosi: sabab, tugma qaytadi")
            for tur in ("502_html", "tarmoq", "403_json"):
                if not tanlangan("/api/inventory/purchases", tur):
                    continue
                pg = ochiq_inv()
                pg.route(yol_mos("/api/inventory/purchases"), yana_yasa(soxta_xaridlar, tur))
                ev(pg, "() => { openPurchaseHistory(); }")
                pg.wait_for_timeout(1000)
                b1 = ev(pg, INV_SNAP) or {}
                xav(pg.click, "#phYana button")
                pg.wait_for_timeout(1000)
                o = ev(pg, INV_SNAP) or {}
                check(f"I4 {tur}: «Yana yuklash» xatosi — xabarda sabab, tugma yana bosiladi, yuklangan 100 ta qoladi",
                      b1.get("ph_yana") == [False, "Yana 50 ta yuklash"] and o.get("toast") == matn("Keyingi xaridlar", tur)
                      and o.get("ph_yana") == [False, "Yana yuklash"] and "100 / 150" in (tt(o, "list") or "") and not pg.__xato,
                      (b1.get("ph_yana"), o.get("toast"), o.get("ph_yana"), (tt(o, "list") or "")[-60:], pg.__xato[:1]))
                pg.close()

        if bolim("I5"):
            section("I5. «Ombor harakatlari» — ro'yxat, davr jami, «Yana yuklash»")
            pg = ochiq_inv()
            ev(pg, "() => { openMovements(); }")
            pg.wait_for_timeout(1000)
            M_ASL = ev(pg, INV_SNAP) or {}
            ev(pg, "s => { document.getElementById('mv-date-from').value = s; loadMovements(''); }", K["sana"])
            pg.wait_for_timeout(1000)
            M_SANA = ev(pg, INV_SNAP) or {}
            pg.close()
            check("I5a OK: ro'yxat («Ko'rsatilgan: N / N ta harakat»), sana bilan — «Tanlangan davr — jami» bloki",
                  "ta harakat" in (tt(M_ASL, "mv") or "") and not M_ASL.get("mvj_bor") and M_SANA.get("mvj_bor")
                  and "TANLANGAN DAVR" in (tt(M_SANA, "mv") or "").upper(), ((tt(M_ASL, "mv") or "")[-60:], M_SANA.get("mvj_bor")))
            for tur, xf in XATOLAR.items():
                if tanlangan("/api/inventory/movements", tur):
                    pg = ochiq_inv()
                    pg.route(yol_mos("/api/inventory/movements"), xf)
                    ev(pg, "() => { openMovements(); }")
                    pg.wait_for_timeout(1000)
                    o = ev(pg, INV_SNAP) or {}
                    check(f"I5b /api/inventory/movements {tur}: ro'yxat o'rnida sabab",
                          tt(o, "mv") == matn("Ombor harakatlari", tur) and o.get("mv_rang") == QIZIL and sessiya_ok(o, tur) and not pg.__xato,
                          (tt(o, "mv"), o.get("mv_rang"), o.get("sess"), pg.__xato[:1]))
                    pg.close()
                if tanlangan("/api/inventory/movements/jami", tur):
                    pg = ochiq_inv()
                    pg.route(yol_mos("/api/inventory/movements/jami"), xf)
                    ev(pg, "s => { document.getElementById('mv-date-from').value = s; openMovements(); }", K["sana"])
                    pg.wait_for_timeout(1000)
                    o = ev(pg, INV_SNAP) or {}
                    check(f"I5c /api/inventory/movements/jami {tur}: davr jami o'rnida sabab, ro'yxat baribir chiziladi",
                          vv(o, "mvj") and tt(o, "mvj") == matn("Tanlangan davr jami", tur) and (o.get("mvj") or {}).get("c") == QIZIL
                          and not o.get("mvj_bor") and "ta harakat" in (tt(o, "mv") or "") and sessiya_ok(o, tur) and not pg.__xato,
                          (o.get("mvj"), o.get("mvj_bor"), (tt(o, "mv") or "")[:160], pg.__xato[:1]))
                    pg.close()
            for tur in ("502_html", "tarmoq"):
                if not tanlangan("/api/inventory/movements", tur):
                    continue
                pg = ochiq_inv()
                pg.route(yol_mos("/api/inventory/movements"), yana_yasa(soxta_harakatlar, tur))
                ev(pg, "() => { openMovements(); }")
                pg.wait_for_timeout(1000)
                b1 = ev(pg, INV_SNAP) or {}
                xav(pg.click, "#mvYana button")
                pg.wait_for_timeout(1000)
                o = ev(pg, INV_SNAP) or {}
                check(f"I5d «Yana yuklash» {tur}: xabarda sabab, tugma qotmaydi (yana bosiladi), yuklangan 100 ta qoladi",
                      b1.get("mv_yana") == [False, "Yana 50 ta yuklash"] and o.get("toast") == matn("Keyingi harakatlar", tur)
                      and o.get("mv_yana") == [False, "Yana 50 ta yuklash"] and "100 / 150" in (tt(o, "mv") or "") and not pg.__xato,
                      (b1.get("mv_yana"), o.get("toast"), o.get("mv_yana"), (tt(o, "mv") or "")[-50:], pg.__xato[:1]))
                pg.close()

        if bolim("I6"):
            section("I6. Omborxona amallari × (tarmoq, 502 HTML, 401, 403): xabarda sabab (jim emas, inglizcha emas)")
            M, P, R, D = IDS.get("mat"), IDS.get("p"), IDS.get("r"), IDS.get("def")
            PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                                "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")

            def prompt(pg, qiymat):
                pg.wait_for_timeout(150)
                xav(pg.fill, "#cp-input", qiymat)
                ev(pg, "() => _cpConfirm()")

            def tasdiq(pg):
                pg.wait_for_timeout(200)
                xav(pg.click, "#ccModalOk", timeout=2000)

            AMALLAR = [
                ("narx", f"/api/inventory/{M}/price", "❌ Narx saqlanmadi: ", lambda pg: (ev(pg, "i => { editPrice(i, 1000); }", M), prompt(pg, "1234"))),
                ("chegara", f"/api/inventory/{M}/min-stock", "❌ Chegara saqlanmadi: ", lambda pg: (ev(pg, "i => { editMinStock(i, 0, 'kg'); }", M), prompt(pg, "5"))),
                ("toifa", f"/api/inventory/{M}", "❌ Kategoriya saqlanmadi: ",
                 lambda pg: (ev(pg, "i => { editCategory(document.querySelector('.cat-badge[data-id=\"' + i + '\"]')); }", M), prompt(pg, "Boshqa"))),
                ("chiqim", f"/api/inventory/{M}/stock", "❌ Chiqim qilinmadi: ",
                 lambda pg: ev(pg, "i => { openChiqimModal(i, 'X', 'kg', 100); document.getElementById('chiqim-qty').value = '1'; saveChiqim(); }", M)),
                ("tuz_kirim", f"/api/inventory/{M}/stock", "❌ Qo'shilmadi: ",
                 lambda pg: ev(pg, "i => { openTuzKirimModal(i, 'X', 'kg', 100); document.getElementById('tk-qty').value = '1'; "
                                   "document.getElementById('tk-notes').value = 'op166'; saveTuzKirim(); }", M)),
                ("ochirish", f"/api/inventory/{M}", "❌ «X» o'chirilmadi: ", lambda pg: (ev(pg, "i => { deleteItem(i, {name: 'X', qty: 0, unit: 'kg'}); }", M), tasdiq(pg))),
                ("rasm", f"/api/inventory/{M}/image", "❌ Rasm yuklanmadi. Sabab: ",
                 lambda pg: xav(pg.set_input_files, f".mat-row:has(#price-{M}) input[type=file]", files=[{"name": "a.png", "mimeType": "image/png", "buffer": PNG}])),
                ("hisobot_tg", "/api/inventory/full-stock-report", "❌ Ombor hisoboti yuborilmadi: ", lambda pg: ev(pg, "() => { sendFullStockReport(); }")),
                ("kam_tg", "/api/inventory/low-stock-alert", "❌ Kam qoldiqlar xabari yuborilmadi: ", lambda pg: ev(pg, "() => { sendLowStockAlert(); }")),
                ("asosiy", f"/api/inventory/{D}/set-default-penoplast", "❌ Asosiy qilinmadi: ", lambda pg: (ev(pg, "i => { setDefaultPenoplast(i); }", D), tasdiq(pg))),
                ("xarid_ochir", f"/api/inventory/purchases/{P}", "❌ Xarid bekor qilinmadi: ",
                 lambda pg: (ev(pg, "() => { openPurchaseHistory(); }"), pg.wait_for_timeout(900), ev(pg, "i => { deletePurchase(i, 'X', 1); }", P), tasdiq(pg))),
                ("kirim_reja", f"/api/inventory/receipts/{R}/cancel-plan", "❌ Bekor qilish rejasi olinmadi: ",
                 lambda pg: ev(pg, "i => { kirimHujjatiniBekorQil(String(i)); }", R)),
                ("kirim_bekor", f"/api/inventory/receipts/{R}/cancel", "❌ Kirim bekor qilinmadi: ",
                 lambda pg: (ev(pg, "i => { kirimHujjatiniBekorQil(String(i)); }", R), pg.wait_for_timeout(700), tasdiq(pg))),
            ]
            TOZALA = """() => { try { invToastHide(); closeChiqimModal(); closeTuzKirimModal(); closePurchaseHistory(); closePhDrawer(); } catch (e) {}
                document.getElementById('ccModal').style.display = 'none'; document.getElementById('cpModal').style.display = 'none';
                const s = document.getElementById('yukSessiya'); if (s) s.hidden = true; isSavingChiqim = false; isSavingTk = false; }"""
            for nom, yol, old, qil in AMALLAR:
                if not any(amal_tanlangan(nom, t_) for t_ in AMAL_TURLAR):
                    continue
                pg = ochiq_inv()
                for tur in AMAL_TURLAR:
                    if not amal_tanlangan(nom, tur):
                        continue
                    P_ = yol_mos(yol)
                    pg.route(P_, XATOLAR[tur])
                    del pg.__xato[:]
                    qil(pg)
                    pg.wait_for_timeout(900)
                    o = ev(pg, INV_SNAP) or {}
                    xabar = (tt(o, "tk") or "") if nom == "tuz_kirim" else (o.get("toast") or "")
                    kut = old + AMAL[tur]
                    tugma = ev(pg, "() => { const b = document.getElementById('chiqim-save-btn'); return b ? [b.disabled, b.innerText.trim()] : null; }")
                    check(f"I6 {nom} {tur}: «{kut}»", bs(xabar) == bs(kut) and sessiya_ok(o, tur) and not pg.__xato
                          and (nom != "chiqim" or tugma == [False, "Chiqim qilish"]),
                          (xabar, o.get("sess"), pg.__xato[:1], tugma))
                    pg.unroute(P_)
                    ev(pg, TOZALA)
                pg.close()

        if bolim("I7"):
            section("I7. Omborxona — rollar (HAQIQIY server): xaridni / kirimni bekor qilish tugmalari faqat «O'chirish» ruxsati bilan")
            for user, kut_tugma, kut_trash in (("op_kirim", True, False), ("op_omb", True, True), ("op_a", True, True), ("op_men", False, False)):
                pg = ochiq_inv(user)
                tugma = ev(pg, "() => !!document.querySelector('button[onclick=\"openPurchaseHistory()\"]')")
                o, bekor = {}, None
                if tugma:
                    ev(pg, "() => { openPurchaseHistory(); }")
                    pg.wait_for_timeout(1200)
                    o = ev(pg, INV_SNAP) or {}
                    ev(pg, "i => { openPhDrawer(String(i)); }", IDS.get("r"))
                    pg.wait_for_timeout(300)
                    bekor = ev(pg, """() => ({bekor: !!document.getElementById('phDrawerBekor'),
                        trash: document.querySelectorAll('#phDrawerBody button[onclick^="deletePurchase"]').length,
                        qator: document.querySelectorAll('#phDrawerBody .mv-row').length})""")
                ok_ = (tugma == kut_tugma and not pg.__xato and
                       (not kut_tugma or ("Ko'rsatilgan:" in (tt(o, "list") or "") and ((o.get("trash", 0) > 0) == kut_trash)
                                          and isinstance(bekor, dict) and bekor.get("qator", 0) > 0 and bekor.get("bekor") == kut_trash
                                          and (bekor.get("trash", 0) > 0) == kut_trash)))
                check(f"I7 {user}: «Xaridlar tarixi» tugmasi {'bor' if kut_tugma else 'yo`q'}, bekor qilish tugmalari "
                      f"{'bor' if kut_trash else 'YO`Q'}", ok_, (tugma, o.get("trash"), bekor, (tt(o, "list") or "")[:60], pg.__xato[:1]))
                pg.close()

        # ══════════════════════════════════════════════════════════════
        # PLATFORMA
        # ══════════════════════════════════════════════════════════════
        def ochiq_pl(marshrut=None, kut=1100):
            pg_ = sahifa(CTX["op_pa"])
            if marshrut:
                pg_.route(*marshrut)
            och(pg_, "/platforma", kut)
            ev(pg_, MSG_USHLA)
            return pg_

        P_ASL = {}
        if any(bolim(b) for b in ("P1", "P2", "P3")):
            section("P1. Platforma — hammasi yuklandi")
            pg = ochiq_pl()
            P_ASL = ev(pg, PL_SNAP) or {}
            # kech154 (zip 206 «Platforma — jadval»): tepadagi 7 ta raqam-karta o'rniga — «Bugun: N kirish · N xato»; korxona sanoqlari —
            # saralash tugmalarida (2 mijoz korxona, 1 bloklangan)
            check("P1a raqamlar («Bugun: N kirish · N xato»), kartochkalar (B, C), saralash sanoqlari (2 mijoz korxona, 1 bloklangan), "
                  "murojaatlar (2 yangi), xatolar; telefon maydoni to'ldirilgan va ochiq; sabab yozuvlari yashirin; «Yuklanmoqda» yo'q",
                  re.fullmatch(r"Bugun: \d+ kirish · \d+ xato", tt(P_ASL, "raq") or "") and "Bloklangan · 1" in P_ASL.get("chip", [])
                  and "Mijoz Korxona B" in (tt(P_ASL, "kart") or "") and "Mijoz Korxona C" in (tt(P_ASL, "kart") or "")
                  and P_ASL.get("chip", [""])[0] == "Hammasi · 2" and P_ASL.get("mpson") == ["2", "0", "0"]
                  and "OP166" in (tt(P_ASL, "mp") or "") and tt(P_ASL, "xt")
                  and P_ASL.get("tel") == {"qiymat": TEL, "yopiq": False, "tugma_yopiq": False}
                  and not vv(P_ASL, "xraq") and not vv(P_ASL, "xtel") and not P_ASL.get("yuklanmoqda") and not pg.__xato,
                  (tt(P_ASL, "raq"), (tt(P_ASL, "kart") or "")[:80], P_ASL.get("chip"), P_ASL.get("mpson"), P_ASL.get("tel"),
                   P_ASL.get("yuklanmoqda"), pg.__xato[:1]))
            pg.close()

        RAQ_BOSH = "Bugun: — kirish · — xato"      # kech154 (zip 206): yuklanmagan — «—» (yolg'on «0» emas)
        if bolim("P2"):
            section("P2. Platforma — 4 so'rov × 5 xato: o'sha blokda sabab, qolgani o'z qiymatida")
            for yol in ("/api/platform/companies", "/api/platform/summary", "/api/platform/errors", "/api/platform/murojaatlar"):
                for tur, xf in XATOLAR.items():
                    if not tanlangan(yol, tur):
                        continue
                    pg = ochiq_pl((yol_mos(yol), xf))
                    o = ev(pg, PL_SNAP) or {}
                    x = []
                    teng = lambda k: bs(tt(o, k)) == bs(tt(P_ASL, k))   # noqa: E731
                    if yol.endswith("companies"):
                        if not (tt(o, "kart") == matn("Mijoz korxonalar", tur) and o.get("kart_rang") == QIZIL):
                            x.append(("kartochkalar sababi", tt(o, "kart"), o.get("kart_rang")))
                        if o.get("chip") != ["Hammasi · —", "Faol · —", "Muddati yaqin · —", "Bloklangan · —", "Sinov davri · —"]:
                            x.append(("saralash sanoqlari «—»", o.get("chip")))
                        if not teng("raq") or o.get("tel") != P_ASL.get("tel") or not teng("mp") or not teng("xt"):
                            x.append(("qolgani o'z qiymatida", tt(o, "raq"), o.get("tel")))
                    elif yol.endswith("summary"):
                        if bs(tt(o, "raq")) != bs(RAQ_BOSH) or not (vv(o, "xraq") and tt(o, "xraq") == matn("Platforma raqamlari", tur)
                                                                 and (o.get("xraq") or {}).get("c") == QIZIL):
                            x.append(("raqamlar «—» va sabab", tt(o, "raq"), o.get("xraq")))
                        if o.get("tel") != {"qiymat": "", "yopiq": True, "tugma_yopiq": True} or \
                                tt(o, "xtel") != matn("Aloqa telefoni", tur) + TEL_QOSHIMCHA or not vv(o, "xtel"):
                            x.append(("telefon yopiq va sabab", o.get("tel"), o.get("xtel")))
                        if not teng("kart") or o.get("chip") != P_ASL.get("chip") or not teng("mp") or not teng("xt"):
                            x.append(("qolgani o'z qiymatida", (tt(o, "kart") or "")[:60], o.get("chip")))
                    elif yol.endswith("errors"):
                        if not (tt(o, "xt") == matn("Xatolar ro'yxati", tur) and o.get("xt_rang") == QIZIL):
                            x.append(("xatolar sababi", tt(o, "xt"), o.get("xt_rang")))
                        if not teng("kart") or not teng("raq") or o.get("tel") != P_ASL.get("tel") or not teng("mp"):
                            x.append(("qolgani o'z qiymatida", (tt(o, "kart") or "")[:60]))
                    else:
                        if not (tt(o, "mp") == matn("Murojaatlar", tur) and o.get("mp_rang") == QIZIL and o.get("mpson") == ["—", "—", "—"]):
                            x.append(("murojaatlar sababi, sanoqlar «—»", tt(o, "mp"), o.get("mpson")))
                        if not teng("kart") or not teng("raq") or o.get("tel") != P_ASL.get("tel") or not teng("xt"):
                            x.append(("qolgani o'z qiymatida", (tt(o, "kart") or "")[:60]))
                    if o.get("yuklanmoqda"):
                        x.append(("«Yuklanmoqda» qoldi", o.get("yuklanmoqda")))
                    if not sessiya_ok(o, tur):
                        x.append(("sessiya xabari", o.get("sess")))
                    if pg.__xato:
                        x.append(("JS xatosi", pg.__xato[:2]))
                    check(f"P2 {yol} {tur}: sabab o'sha blokda, qolgani o'z qiymatida", not x, x)
                    pg.close()

        def server_tel():
            pg_ = sahifa(CTX["op_pa"])
            och(pg_, "/", 200)
            r_ = ev(pg_, "async () => (await (await fetch('/api/platform/summary')).json()).aloqa_telefoni")
            pg_.close()
            return r_

        if bolim("P3"):
            section("P3. «Aloqa telefoni» — yuklanmasa «Saqlash» telefonni O'CHIRMAYDI (HAQIQIY server); saqlash xatosi — sabab")
            for yol, tur in (("/api/platform/summary", "502_html"), ("/api/platform/summary", "tarmoq"), ("/api/platform/summary", "401_json"),
                             ("/api/platform/companies", "502_html")):
                if not tanlangan(yol, tur):
                    continue
                pg = ochiq_pl((yol_mos(yol), XATOLAR[tur]))
                o = ev(pg, PL_SNAP) or {}
                xav(pg.click, "#plTelefonSaqla", force=True, timeout=2000)
                pg.wait_for_timeout(700)
                post = [x for x in pg.__sorov if x[0] == "POST" and "contact-phone" in x[1]]
                pg.close()
                st = server_tel()
                if st != TEL:
                    pg = sahifa(CTX["op_pa"])
                    och(pg, "/", 200)
                    ev(pg, "async (t) => { const fd = new FormData(); fd.append('telefon', t); await fetch('/api/platform/contact-phone', {method: 'POST', body: fd}); }", TEL)
                    pg.close()
                if yol.endswith("summary"):
                    check(f"P3a {yol} {tur}: maydon bo'sh va YOPIQ, «Saqlash» bosilsa so'rov ketmaydi, serverda telefon o'zgarmadi",
                          o.get("tel") == {"qiymat": "", "yopiq": True, "tugma_yopiq": True} and not post and st == TEL,
                          (o.get("tel"), len(post), st))
                else:
                    check(f"P3b {yol} {tur}: telefon (raqamlar so'rovidan) yuklangan — maydon ochiq, «Saqlash» o'sha telefonni yozadi, server o'zgarmadi",
                          o.get("tel") == {"qiymat": TEL, "yopiq": False, "tugma_yopiq": False} and len(post) == 1 and st == TEL,
                          (o.get("tel"), len(post), st))
            pg = ochiq_pl()
            for tur in AMAL_TURLAR:
                if not tanlangan("/api/platform/contact-phone", tur):
                    continue
                P_ = yol_mos("/api/platform/contact-phone")
                pg.route(P_, XATOLAR[tur])
                xav(pg.click, "#plTelefonSaqla")
                pg.wait_for_timeout(700)
                o = ev(pg, PL_SNAP) or {}
                check(f"P3c saqlash {tur}: «Saqlanmadi: {AMAL[tur]}» (qizil)",
                      tt(o, "tel_natija") == "Saqlanmadi: " + AMAL[tur] and (o.get("tel_natija") or {}).get("c") == QIZIL
                      and sessiya_ok(o, tur) and not pg.__xato, (o.get("tel_natija"), o.get("sess"), pg.__xato[:1]))
                pg.unroute(P_)
                ev(pg, "() => { document.getElementById('yukSessiya').hidden = true; }")
            if not _TUR:
                xav(pg.fill, "#plTelefon", "+998 90 111 22 34")
                xav(pg.click, "#plTelefonSaqla")
                pg.wait_for_timeout(700)
                o = ev(pg, PL_SNAP) or {}
                st = server_tel()
                check("P3d xatodan keyin OK saqlash: «✓ Saqlandi» (kulrang), serverda yangi telefon",
                      tt(o, "tel_natija") == "✓ Saqlandi" and (o.get("tel_natija") or {}).get("c") != QIZIL and st == "+998 90 111 22 34",
                      (o.get("tel_natija"), st))
                xav(pg.fill, "#plTelefon", TEL)
                xav(pg.click, "#plTelefonSaqla")
                pg.wait_for_timeout(600)
            pg.close()

        if bolim("P4"):
            section("P4. Platforma — poyga: kech kelgan ESKI javob yangisining ustiga yozilmaydi")
            ushla = []
            pg = ochiq_pl((yol_mos("/api/platform/murojaatlar"), ushla_yasa(ushla, lambda u: "holat=yangi" in u)), kut=600)
            xav(pg.click, "#mpChiplar [data-holat='']")
            pg.wait_for_timeout(900)
            for r in ushla:
                xav(r.fulfill, status=200, content_type="application/json",
                    body=json.dumps({"murojaatlar": [], "sanoq": {"yangi": 7, "javob_berildi": 0, "yopildi": 0}}))
            pg.wait_for_timeout(900)
            o = ev(pg, PL_SNAP) or {}
            aktiv = ev(pg, "() => document.querySelector('#mpChiplar .aktiv').innerText")
            check("P4a murojaat holati: «Yangi» javobi ushlandi → «Hammasi» → eski javob keldi: ro'yxat «Hammasi» niki (2 murojaat), sanoq 2",
                  len(ushla) == 1 and "Hammasi" in str(aktiv) and (tt(o, "mp") or "").count("OP166") == 2 and o.get("mpson", [""])[0] == "2",
                  (len(ushla), aktiv, (tt(o, "mp") or "")[:100], o.get("mpson")))
            pg.close()
            ushla = []
            pg = ochiq_pl((yol_mos("/api/platform/errors"), ushla_yasa(ushla, lambda u: "korxona=" not in u)), kut=600)
            xav(pg.select_option, "#xtKorxona", "platforma")
            pg.wait_for_timeout(900)
            for r in ushla:
                xav(r.fulfill, status=200, content_type="application/json", body=json.dumps(
                    [{"xabar": "ESKI_JAVOB xato", "vaqt": "01.01 10:00", "korxona": "Mijoz Korxona B", "method": "GET", "endpoint": "/x", "kim": "", "trace": ""}]))
            pg.wait_for_timeout(900)
            o = ev(pg, PL_SNAP) or {}
            check("P4b xatolar: «Hammasi» javobi ushlandi → «Platforma (korxonasiz)» → eski javob keldi: ro'yxat tanlanganniki",
                  len(ushla) == 1 and "ESKI_JAVOB" not in (tt(o, "xt") or "") and tt(o, "xt"), (len(ushla), tt(o, "xt")))
            pg.close()
            ushla, sanoq = [], []

            def _uz_yasa(ushla, sanoq):
                def _tut(r):
                    sanoq.append(1)
                    if len(sanoq) == 1:
                        ushla.append(r)
                    else:
                        r.continue_()
                return _tut
            pg = ochiq_pl(kut=600)
            pg.route(lambda u: u.endswith(f"/companies/{B_ID}/extend"), _uz_yasa(ushla, sanoq))
            xav(pg.click, f"[data-amal='uzaytir'][data-id='{B_ID}']")
            pg.wait_for_timeout(500)
            xav(pg.click, "input[name=uzOy][value='12']")
            pg.wait_for_timeout(900)
            oldin = ev(pg, "() => document.getElementById('uzKorish').innerText")
            for r in ushla:
                xav(r.fulfill, status=200, content_type="application/json", body=json.dumps({"status": "korish", "obuna_tugash": "2030-01-01"}))
            pg.wait_for_timeout(900)
            keyin = ev(pg, "() => document.getElementById('uzKorish').innerText")
            check("P4c «Muddatni uzaytirish»: «+1 oy» ko'rishi ushlandi → «+12 oy» → eski javob keldi: «+12 oy» sanasi qoladi",
                  len(ushla) == 1 and str(oldin).startswith("Yangi muddat:") and keyin == oldin and "2030" not in str(keyin),
                  (len(ushla), oldin, keyin))
            pg.close()
            ushla = []
            pg = ochiq_pl(kut=600)
            xav(pg.click, "#mpChiplar [data-holat='']")
            pg.wait_for_timeout(700)
            pg.route(lambda u: urlparse(u).path == "/api/platform/murojaatlar/1", ushla_yasa(ushla, lambda u: True))
            xav(pg.click, "#mpRoyxat [data-mp-id='1']")
            pg.wait_for_timeout(300)
            xav(pg.click, "#mpRoyxat [data-mp-id='2']")
            pg.wait_for_timeout(900)
            for r in ushla:
                xav(jv, r, 200, {"id": 1, "turi": "savol", "turi_nomi": "Savol", "holat": "yangi", "holat_nomi": "Yangi", "korxona": "ESKI_YOZISHMA",
                                 "yaratgan": "x", "yaratilgan": "2026-01-01T10:00:00", "xabarlar": [], "kontekst": {}})
            pg.wait_for_timeout(800)
            yoz = ev(pg, "() => document.getElementById('mpYozishma').innerText")
            check("P4d murojaat yozishmasi: #1 javobi ushlandi → #2 ochildi → #1 javobi keyin keldi: #2 yozishmasi qoladi",
                  len(ushla) == 1 and "Murojaat #2" in str(yoz) and "ESKI_YOZISHMA" not in str(yoz), (len(ushla), str(yoz)[:120]))
            pg.close()

        if bolim("P5"):
            section("P5. «Muddatni uzaytirish» oldindan ko'rish × xato: sabab (abadiy «Hisoblanmoqda…» emas)")
            pg = ochiq_pl(kut=600)
            for tur, xf in XATOLAR.items():
                if not tanlangan("/extend", tur):
                    continue
                P_ = (lambda b: (lambda u: u.endswith(f"/companies/{b}/extend")))(B_ID)
                pg.route(P_, xf)
                del pg.__xato[:]
                xav(pg.click, f"[data-amal='uzaytir'][data-id='{B_ID}']")
                pg.wait_for_timeout(900)
                k = ev(pg, "() => document.getElementById('uzKorish').innerText")
                s_ = ev(pg, PL_SNAP) or {}
                check(f"P5 oldindan ko'rish {tur}: «{AMAL[tur]}»", k == AMAL[tur] and sessiya_ok(s_, tur) and not pg.__xato, (k, pg.__xato[:1]))
                pg.unroute(P_)
                ev(pg, "() => { plModalYop(); document.getElementById('yukSessiya').hidden = true; }")
            if not _TUR:
                xav(pg.click, f"[data-amal='uzaytir'][data-id='{B_ID}']")
                pg.wait_for_timeout(600)
                xav(pg.click, "input[name=uzOy][value='sana']")
                pg.wait_for_timeout(200)
                ev(pg, "() => { const i = document.getElementById('uzSana'); i.value = '2020-01-01'; i.dispatchEvent(new Event('change', {bubbles: true})); }")
                pg.wait_for_timeout(900)
                k = ev(pg, "() => document.getElementById('uzKorish').innerText")
                srv = ev(pg, """async (b) => { const fd = new FormData(); fd.append('sana', '2020-01-01'); fd.append('korish', '1');
                    const r = await fetch('/api/platform/companies/' + b + '/extend', {method: 'POST', body: fd}); return [r.status, (await r.json()).detail]; }""", B_ID)
                check("P5b server rad etsa (o'tgan sana) — serverning o'z sababi", isinstance(srv, list) and srv[0] == 400 and k == srv[1], (k, srv))
            pg.close()

        if bolim("P6"):
            section("P6. Platforma amallari × (tarmoq, 502 HTML, 401, 403): sabab (internet uzilsa ham — jim emas)")

            def pl_tasdiq(pg):
                pg.wait_for_timeout(200)
                xav(pg.click, "#ccModalOk", timeout=2000)

            def mp_och(pg):
                xav(pg.click, "#mpChiplar [data-holat='']")
                pg.wait_for_timeout(700)
                xav(pg.click, "#mpRoyxat [data-mp-id='2']")

            def oxiri(o):
                return lambda u: u.endswith(o)

            def uz_tut(xf):
                def _t(r):
                    if 'name="korish"' in tana(r.request):
                        return r.continue_()
                    return xf(r)
                return _t

            AMALLAR = [
                ("blokla", oxiri(f"/companies/{B_ID}/block"), None, lambda pg: (xav(pg.click, f"[data-amal='blokla'][data-id='{B_ID}']"), pg.wait_for_timeout(250),
                                                                               xav(pg.click, "button[data-modal='blokla']")),
                 lambda pg: ev(pg, "() => document.getElementById('blXato').innerText"), ""),
                ("uzaytir", oxiri(f"/companies/{B_ID}/extend"), uz_tut, lambda pg: (xav(pg.click, f"[data-amal='uzaytir'][data-id='{B_ID}']"), pg.wait_for_timeout(700),
                                                                                    xav(pg.click, "button[data-modal='uzaytir']")),
                 lambda pg: ev(pg, "() => document.getElementById('uzXato').innerText"), ""),
                ("och", oxiri(f"/companies/{C_ID}/unblock"), None, lambda pg: (xav(pg.click, f"[data-amal='och'][data-id='{C_ID}']"), pl_tasdiq(pg)),
                 lambda pg: (ev(pg, "() => (window.__msg.slice(-1)[0] || [''])[0]")), "Ochilmadi: "),
                ("parol", oxiri(f"/companies/{B_ID}/reset-admin-password"), None, lambda pg: (xav(pg.click, f"[data-amal='parol'][data-id='{B_ID}']"), pl_tasdiq(pg)),
                 lambda pg: ev(pg, "() => (window.__msg.slice(-1)[0] || [''])[0]"), "Parol tiklanmadi: "),
                ("yarat", lambda u: urlparse(u).path == "/api/platform/companies", None,
                 lambda pg: (ev(pg, "() => { document.getElementById('plYangi').style.display = ''; }"), xav(pg.fill, "#ncNom", "OP Korxona X"),
                             xav(pg.fill, "#ncLogin", "op_x_admin"), xav(pg.click, "#ncYarat")),
                 lambda pg: ev(pg, "() => (window.__msg.slice(-1)[0] || [''])[0]"), "Korxona yaratilmadi: "),
                ("mp_javob", oxiri("/murojaatlar/2/javob"), None, lambda pg: (xav(pg.fill, "#mpMatn", "op166 javob"), xav(pg.click, "#mpYozishma button[data-mp='javob']")),
                 lambda pg: ev(pg, "() => (window.__msg.slice(-1)[0] || [''])[0]"), "Javob yuborilmadi: "),
                ("mp_yop", oxiri("/murojaatlar/2/yopish"), None, lambda pg: (xav(pg.click, "#mpYozishma button[data-mp='yop']"), pl_tasdiq(pg)),
                 lambda pg: ev(pg, "() => (window.__msg.slice(-1)[0] || [''])[0]"), "Murojaat yopilmadi: "),
            ]
            for nom, shart, ishlov, qil, oqi_, old in AMALLAR:
                if not any(amal_tanlangan(nom, t_) for t_ in AMAL_TURLAR):
                    continue
                pg = ochiq_pl(kut=700)
                if nom.startswith("mp_"):
                    mp_och(pg)
                    pg.wait_for_timeout(700)
                for tur in AMAL_TURLAR:
                    if not amal_tanlangan(nom, tur):
                        continue
                    h = ishlov(XATOLAR[tur]) if ishlov else XATOLAR[tur]
                    pg.route(shart, h)
                    del pg.__xato[:]
                    qil(pg)
                    pg.wait_for_timeout(900)
                    m_ = oqi_(pg)
                    s_ = ev(pg, PL_SNAP) or {}
                    check(f"P6 {nom} {tur}: «{old}{AMAL[tur]}»", m_ == old + AMAL[tur] and sessiya_ok(s_, tur) and not pg.__xato,
                          (m_, s_.get("sess"), pg.__xato[:1]))
                    pg.unroute(shart)
                    ev(pg, "() => { plModalYop(); document.getElementById('yukSessiya').hidden = true; window.__msg = []; }")
                pg.close()
            # murojaatni ochish (GET) × xato
            if any(amal_tanlangan("mp_och", t_) for t_ in AMAL_TURLAR + ("500_json",)):
                pg = ochiq_pl(kut=700)
                xav(pg.click, "#mpChiplar [data-holat='']")
                pg.wait_for_timeout(700)
                for tur, xf in XATOLAR.items():
                    if not amal_tanlangan("mp_och", tur):
                        continue
                    P_ = (lambda u: urlparse(u).path == "/api/platform/murojaatlar/2")
                    pg.route(P_, xf)
                    del pg.__xato[:]
                    xav(pg.click, "#mpRoyxat [data-mp-id='2']")
                    pg.wait_for_timeout(800)
                    m_ = ev(pg, "() => (window.__msg.slice(-1)[0] || [''])[0]")
                    s_ = ev(pg, PL_SNAP) or {}
                    check(f"P6 mp_och {tur}: «{matn('Murojaat #2', tur)}»", m_ == matn("Murojaat #2", tur) and sessiya_ok(s_, tur) and not pg.__xato,
                          (m_, pg.__xato[:1]))
                    pg.unroute(P_)
                    ev(pg, "() => { document.getElementById('yukSessiya').hidden = true; window.__msg = []; }")
                pg.close()

        if bolim("P8"):
            section("P8. Sabablar ro'yxati yuklanmasa — «Bloklash» oynasida tugma yopiq, sabab")
            pg = ochiq_pl((yol_mos("/api/platform/summary"), XATOLAR["502_html"]), kut=700)
            xav(pg.click, f"[data-amal='blokla'][data-id='{B_ID}']")
            pg.wait_for_timeout(300)
            o = ev(pg, """() => { const b = document.querySelector('#plOyna button[data-modal="blokla"]');
                return {xato: (document.getElementById('blXato') || {}).innerText, yopiq: b ? b.disabled : null}; }""")
            check("P8 «⚠️ Bloklash sabablari yuklanmadi — sahifani yangilang», «Bloklash» yopiq",
                  isinstance(o, dict) and o.get("xato") == "⚠️ Bloklash sabablari yuklanmadi — sahifani yangilang" and o.get("yopiq") is True, o)
            pg.close()

        if bolim("P7"):
            section("P7. Ikki marta bosish — bitta so'rov (HAQIQIY server: muddat BIR marta uzayadi)")
            pg = ochiq_pl(kut=700)
            xav(pg.click, f"[data-amal='uzaytir'][data-id='{B_ID}']")
            pg.wait_for_timeout(900)
            korish = ev(pg, "() => document.getElementById('uzKorish').innerText")
            del pg.__sorov[:]
            ev(pg, "() => { const b = document.querySelector('button[data-modal=\"uzaytir\"]'); b.click(); b.click(); }")
            pg.wait_for_timeout(1500)
            post = [x for x in pg.__sorov if x[0] == "POST" and x[1].endswith("/extend") and 'name="korish"' not in x[2]]
            srv = ev(pg, """async (b) => { const r = await (await fetch('/api/platform/companies')).json(); const k = r.find(x => x.id === b);
                return k && k.holat ? k.holat.obuna_tugash : null; }""", B_ID)
            kut_sana = str(korish).replace("Yangi muddat: ", "").replace(" gacha", "")
            srv_sana = (srv[8:10] + "." + srv[5:7] + "." + srv[0:4]) if isinstance(srv, str) and len(srv) >= 10 else srv
            check("P7a «Uzaytirish» ikki marta bosildi: BITTA so'rov, serverda muddat oldindan ko'rsatilgan sanaga (bir marta) uzaydi",
                  len(post) == 1 and srv_sana == kut_sana, (len(post), korish, srv))
            pg.close()
            pg = ochiq_pl(kut=700)
            ev(pg, "() => { document.getElementById('plYangi').style.display = ''; }")
            xav(pg.fill, "#ncNom", "OP Korxona D")
            xav(pg.fill, "#ncLogin", "op_d_admin")
            del pg.__sorov[:]
            ev(pg, "() => { const b = document.getElementById('ncYarat'); b.click(); b.click(); }")
            pg.wait_for_timeout(1500)
            post = [x for x in pg.__sorov if x[0] == "POST" and urlparse(x[1]).path == "/api/platform/companies"]
            nat = ev(pg, "() => document.getElementById('plNatija').innerText")
            check("P7b «Yaratish» ikki marta bosildi: BITTA so'rov, korxona yaratildi (parol bir marta ko'rsatildi)",
                  len(post) == 1 and "OP Korxona D" in str(nat), (len(post), str(nat)[:80]))
            pg.close()

        if bolim("T"):
            section("T. Telefon 390 / 320 px (kunduzgi / tungi): hamma so'rov xato — sahifa toshmaydi, sabab ekranda va o'qiladi")
            for w, tema in ((390, "light"), (320, "light"), (390, "dark")):
                for user, url, eng_kam in (("op_a", "/inventory", 2), ("op_pa", "/platforma", 5)):
                    ctx = kontekst(user, w=w, h=844)
                    pg = sahifa(ctx)
                    if tema == "dark":
                        pg.add_init_script("try { localStorage.setItem('theme', 'dark'); } catch (e) {}")
                    pg.route(lambda u: urlparse(u).path.startswith("/api/") and urlparse(u).path != "/api/notifications", XATOLAR["500_json"])
                    och(pg, url, 1200)
                    if url == "/inventory":
                        ev(pg, "() => { openPurchaseHistory(); }")
                        pg.wait_for_timeout(900)
                    if tema == "dark":
                        ev(pg, "() => document.documentElement.setAttribute('data-theme', 'dark')")
                        pg.wait_for_timeout(200)
                    r = ev(pg, KONTRAST)
                    els = ((r or {}).get("el") or []) if isinstance(r, dict) else []
                    yomon = [e for e in els if e["kontrast"] < 4.5 or e["ong"] > r["vw"] + 1 or e["chap"] < -1 or e["toshgan"]]
                    check(f"T {url} {w} px {tema}: sahifa toshmaydi (eni {w}), sabablar ekranda, qutisidan chiqmaydi, kontrast ≥ 4.5, kamida {eng_kam} ta",
                          isinstance(r, dict) and r.get("sw", 9999) <= w + 1 and len(els) >= eng_kam and not yomon and not pg.__xato,
                          (r.get("sw") if isinstance(r, dict) else r, len(els), yomon[:4], pg.__xato[:1]))
                    pg.close()
                    ctx.close()

        for c in CTX.values():
            c.close()
        br.close()
    server.should_exit = True

print("\n" + "=" * 70)
print(f"NATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("   -", f)
sys.exit(1 if FAIL else 0)
