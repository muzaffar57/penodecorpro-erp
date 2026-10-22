#!/usr/bin/env python3
"""
test_platforma_korinish206.py — kech154 (zip 206 «Platforma — jadval»; EGASI so'rovi 22.10 11:40 «Platforma sahifasi juda katta ko'rinadi —
o'zgartirib ber», TANLOVI «2 · Jadval»): mijoz korxonalar ro'yxatida HAR korxona — bitta qator, ustunlar sarlavha bilan bir chiziqda;
tepadagi 7 ta raqam-karta o'rniga «Bugun: N kirish · N xato». FAQAT KO'RINISH.

NIMA UCHUN KERAK (O'LCHANGAN — `work/k206/ekran206.py`, zip 205 kodi, haqiqiy Chromium, 1920 px — egasining ekrani): har korxona kartochkasi
  219 px, bir qatorda 2 ta — 7 korxona ro'yxati 949 px; tepadagi 7 ta katta raqam-karta saralash tugmalaridagi sonlarni takrorlaydi.
  Mustaqil tekshiruv (kech154) O'LCHADI: qat'iy ustunlar 1094 px talab qiladi — chap menyu bilan 1101–1361 px ekranda ro'yxat torroq,
  `overflow:hidden` «Amallar» ustunini KESARDI (1280 px da «Parolni tiklash» bosib bo'lmasdi) — shu sabab ro'yxat kengligiga qarab
  (`@container plroyxat`): ≥ 1094 — bitta qator; 760–1093 — tugmalar qator ostida; < 760 — kartochka. Shu test oraliq kengliklarni ham o'lchaydi.
BO'LIMLAR:
  S — manba (`templates/platforma.html`): raqam-kartalar yo'q, `#plRaqamlar` — «Bugun: …» saralash yonida; ustun sarlavhalari faqat ro'yxat
      bo'sh bo'lmasa; sarlavha va qator — bir xil qat'iy ustunlar, ro'yxat konteyner, ikki `@container` bosqichi asosiy qoidalardan KEYIN;
      qatorda holat katagi, raqam nomlari «:» bilan (jadvalda ko'zdan yashirin, `display:none` emas), «Uzaytirish» (title — to'liq nomi),
      bloklanganda «Ochish» / «Uzaytirib ochish» / «Parolni tiklash», «jami»; foydalanuvchi matni `escapeHtml` bilan; pastki izoh.
  D — HAQIQIY Chromium + lokal server, korxonalar API orqali (2 tasi obuna 31.12.2027 gacha, muddatsiz, sinov davrida 3 ta (biri 63 belgili
      nom), muddati yaqin, imtiyozda («muddati o'tdi»), bloklangan — sabab va izoh bilan, nomida «<» «&»): 1920 / 1440 / 1366 px — bitta
      qator (≤ 64 px; uzun nom ≤ 3 satr, 1366 da imtiyozdagi ≤ 80), ustunlar sarlavha bilan bir chiziqda (±1 px); 1280 / 1101 px — tugmalar
      qator ostida; HAMMA kenglikda har tugma ro'yxat va oyna ichida, bosiladigan (`elementFromPoint`), ro'yxat ichida kesilish yo'q;
      «Bugun: N kirish · N xato» = `/api/platform/summary`, bitta `#plRaqamlar`, uslubi; saralash sonlari; «Uzaytirish» / «Bloklash»
      oynasi, Esc; saralash / qidiruv / bo'sh ro'yxat; bloklangan qator — qisqa izoh (to'liq — `title`), «jami»; kod `title`; raqam nomlari
      (ekran o'quvchisi uchun matn); rang (muddati yaqin — sariq, imtiyozda / bloklangan — qizg'ish, tungi rejimda ham) va kontrast;
      1000 va 390 px — ixcham kartochka, yon tomonga toshmaydi; JS xatosi yo'q.
REJIMLAR: SQLite (odatiy); `TENANT_FILTER=1`. Asl kodga (zip 205) qarshi QULAMAYDI — yiqiladi.
ISHLATISH: python3 tools/test_platforma_korinish206.py
"""
import os
import io
import re
import sys
import glob
import time
import socket
import tempfile
import datetime
import threading
import contextlib

ROOT = os.environ.get("REPO") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

TF = os.environ.get("TENANT_FILTER") == "1"
_T = tempfile.mkdtemp(prefix="k206_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'k206.db')}"
for _k in ("TELEGRAM_BOT_TOKEN", "BACKUP_TELEGRAM_CHAT_ID", "PG_URL"):
    os.environ.pop(_k, None)

YORLIQ = "[TF1] " if TF else ""
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond() if callable(cond) else cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e}"
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        if callable(detail):
            try:
                detail = detail()
            except Exception as e:         # noqa: BLE001
                detail = f"{type(e).__name__}: {e}"
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def xav(f, *a, standart=None, **k):
    try:
        return f(*a, **k)
    except Exception as e:                 # noqa: BLE001
        print(f"    (bajarilmadi: {getattr(f, '__name__', f)} — {type(e).__name__}: {str(e)[:200]})")
        return standart


def rgb(s):
    m = re.findall(r"[\d.]+", s or "")
    return tuple(float(x) for x in m[:3]) if len(m) >= 3 else None


def _lum(c):
    def k(v):
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * k(c[0]) + 0.7152 * k(c[1]) + 0.0722 * k(c[2])


def kontrast(a, b):
    if not a or not b:
        return 0
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S — manba")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
PH = open(os.path.join(ROOT, "templates", "platforma.html"), encoding="utf-8").read()
_uslub = PH[PH.find("{% block extra_css %}") if "{% block extra_css %}" in PH else 0:PH.find("{% block content %}")]
_kontent = PH[PH.find("{% block content %}"):PH.find("<script")]
_head = _kontent[_kontent.find('<div class="pl-head">'):_kontent.find('<div class="card" id="plYangi"')]
check("S1 tepadagi 7 ta raqam-karta YO'Q (`pl-stats` / `pl-stat`); `#plRaqamlar` — saralash tugmalari va qidiruv orasidagi `span.pl-bugun` "
      "(«Bugun: N kirish · N xato», yuklanmagan — «—»)",
      "pl-stats" not in PH and "pl-stat " not in PH and 'class="pl-stat"' not in PH
      and '<span class="pl-bugun" id="plRaqamlar" aria-live="polite">Bugun: <b>—</b> kirish · <b>—</b> xato</span>' in _head
      and _head.find('id="plChiplar"') < _head.find('id="plRaqamlar"') < _head.find('class="pl-tools"')
      and "document.getElementById('plRaqamlar').innerHTML = 'Bugun: <b>' + (bor ? plSon(r.bugun_kirish) : '—') + '</b> kirish · <b>' +" in PH
      and "(bor ? plSon(r.bugun_xato) : '—') + '</b> xato';" in PH, len(_head))
_cz = PH[PH.find("function plChizish()"):PH.find("function plRaqamlarChiz()")]
check("S2 ustun sarlavhalari (Korxona · Holat · Obuna · Foydal. · Buyurtma · Oxirgi kirish · Amallar) — faqat ro'yxat bo'sh bo'lmasa, "
      "`aria-hidden`",
      "el.innerHTML = ko.length ? '<div class=\"pl-jbosh\" aria-hidden=\"true\"><span>Korxona</span><span>Holat</span><span>Obuna</span>"
      "<span>Foydal.</span>' +" in _cz and "'<span>Buyurtma</span><span>Oxirgi kirish</span><span class=\"ong\">Amallar</span></div>' + "
      "ko.map(plKarta).join('')" in _cz, len(_cz))
_i_asos = _uslub.find(".pl-jbosh,.pl-card{display:grid;grid-template-columns:")
_i_c1 = _uslub.find("@container plroyxat (max-width:1093.98px){")
_i_c2 = _uslub.find("@container plroyxat (max-width:759.98px){")
_i_l = _uslub.find("  .pl-raqam .l{position:absolute;")
_i_btn = _uslub.find("  .pl-btns{display:flex;")
check("S3 sarlavha va qator — BIR xil qat'iy ustunlar (har qator alohida grid — `max-content` / `auto` bo'lsa ustunlar siljiydi; eng kam "
      "1094 px); ro'yxat — konteyner (`plroyxat`); < 1094 — tugmalar qator ostida, < 760 — kartochka; ikkala `@container` asosiy "
      "qoidalardan KEYIN (keyingisi bosmasin)",
      ".pl-jbosh,.pl-card{display:grid;grid-template-columns:minmax(170px,1fr) 120px minmax(170px,1fr) 52px 66px 104px 312px;column-gap:12px;"
      in _uslub and "container-type:inline-size;container-name:plroyxat}" in _uslub
      and ".pl-jbosh,.pl-card{grid-template-columns:minmax(140px,1fr) 120px minmax(150px,1fr) 48px 60px 96px}" in _uslub
      and ".pl-btns{grid-column:1 / -1;flex-wrap:wrap;justify-content:flex-start}" in _uslub and ".pl-jbosh .ong{display:none}" in _uslub
      and "    .pl-jbosh{display:none}" in _uslub and ".pl-blok-qosh{display:inline}" in _uslub and ".pl-blok-qosh{display:none}" in _uslub
      and 0 < _i_asos < _i_l < _i_btn < _i_c1 < _i_c2 and "@media (max-width:1100px)" not in _uslub,
      (_i_asos, _i_l, _i_btn, _i_c1, _i_c2))
_kt = PH[PH.find("function plKarta(r)"):PH.find("var PL_CHIP_NOMI")]
check("S4 qator: holat katagi (`pl-holat`), raqam nomlari «Foydalanuvchi:» / «Buyurtma (shu oy):» / «Oxirgi kirish:» (jadvalda ko'zdan "
      "yashirin — ekran o'quvchisi uchun bor, `display:none` EMAS), «Uzaytirish» (title «Muddatni uzaytirish»); bloklanganda «Ochish» / "
      "«Uzaytirib ochish» / «Parolni tiklash», sonning yonida «jami»; `data-amal` / `data-id` / `data-korxona` o'sha",
      '<div class="pl-holat">\' + plBadge(h) + \'</div></div>\'' in _kt and "Foydalanuvchi:" in _kt and "'Buyurtma (shu oy):'" in _kt
      and "Oxirgi kirish:" in _kt and 'data-amal="uzaytir" data-id="\' + id + \'" title="Muddatni uzaytirish">Uzaytirish</button>' in _kt
      and '>Ochish</button>' in _kt and '>Uzaytirib ochish</button>' in _kt and '>Parolni tiklash</button>' in _kt
      and 'data-amal="blokla"' in _kt and 'data-korxona="\' + id + \'"' in _kt and "Muddatni uzaytirish</button>" not in _kt
      and "(h.bloklangan ? ' <span class=\"pl-jami\" aria-hidden=\"true\">jami</span>' : '')" in _kt
      and ".pl-raqam .l{display:none}" not in _uslub
      and ".pl-raqam .l{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0 0 0 0);" in _uslub, len(_kt))
check("S5 foydalanuvchi matni — `escapeHtml` bilan: nom, kod (va uning `title`), sabab, izoh, bloklangan qatorning to'liq izohi (`title`)",
      "escapeHtml(r.name || '')" in _kt and "'<div class=\"pl-kod\" title=\"' + escapeHtml(r.code || '—') + dan + '\">' + escapeHtml(r.code || '—') "
      "+ dan + '</div></div>'" in _kt and "escapeHtml(h.sabab || '—')" in _kt
      and "escapeHtml(r.blok_izoh)" in _kt and "'<div class=\"pl-blok\" title=\"' + escapeHtml(_toliq) + '\">'" in _kt, "")
check("S6 pastki izoh: «Muddatga 7 kun qolganda qator sariq bo'ladi» (endi kartochka emas — qator)",
      "Muddatga 7 kun qolganda qator sariq bo'ladi" in PH and "kartochka sariq" not in PH, "")

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
# tayyorgarlik — platforma admini, korxonalar API orqali
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
_bosh = io.StringIO()
with contextlib.redirect_stdout(_bosh):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User                  # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

PAROL = "Parol123!"
s = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    auth.create_user(s, "k206_plat", PAROL, UserRole.ADMIN, "K206 Platforma", company_id=1)
s.query(User).filter(User.username == "k206_plat").first().is_platform_admin = True
s.commit()
s.close()
C = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
_lg = C.post("/login", data={"username": "k206_plat", "password": PAROL}, follow_redirects=False)
TK = (datetime.datetime.utcnow() + datetime.timedelta(hours=5)).date()
UZUN = "Andijon Fasad Dekor Qurilish Materiallari Ishlab Chiqarish MChJ"
KORX = [("ZZZ_SINOV_KORXONA_B", "k206_b"), ("Sinov Korxona C", "k206_c"), ("Sinov Korxona D", "k206_d"), ("Sinov Korxona E", "k206_e"),
        ("Alfa Dekor MChJ", "k206_alfa"), ("Bekobod Fasad", "k206_bek"), ("Chust <Dekor> & Co", "k206_chust"),
        ("Otgan Imtiyozda", "k206_otgan"), (UZUN, "k206_uzun")]
ID = {}
for _n, _l in KORX:
    _r = C.post("/api/platform/companies", data={"name": _n, "admin_username": _l})
    ID[_n] = ((_r.json() or {}).get("company") or {}).get("id") if _r.status_code == 200 else None
_st = []
for _n in ("ZZZ_SINOV_KORXONA_B", "Sinov Korxona C"):
    _st.append(C.post(f"/api/platform/companies/{ID[_n]}/extend", data={"sana": "2027-12-31"}).status_code)
_st.append(C.post(f"/api/platform/companies/{ID['Alfa Dekor MChJ']}/extend", data={"sana": (TK + datetime.timedelta(days=5)).isoformat()}).status_code)
_st.append(C.post(f"/api/platform/companies/{ID['Bekobod Fasad']}/block",
                  data={"sabab": "To'lov qilinmagan", "izoh": "Iyun to'lovi kelmadi"}).status_code)
s = SessionLocal()
try:
    s.get(Company, ID["Sinov Korxona D"]).obuna_tugash = None
    s.get(Company, ID["Otgan Imtiyozda"]).obuna_tugash = TK - datetime.timedelta(days=1)     # imtiyozda (3 kun) — «Muddati o'tdi»
    s.commit()
finally:
    s.close()
SUMMARY = ((C.get("/api/platform/summary").json() or {}).get("raqamlar") or {}) if _lg.status_code in (302, 303) else {}
_holat = {r.get("name"): (r.get("holat") or {}).get("bosqich") for r in (C.get("/api/platform/companies").json() or [])}
check("T0 fikstura: platforma admini, 9 mijoz korxona (2 — obuna 31.12.2027 gacha, muddatsiz, muddati yaqin, imtiyozda («otgan»), "
      "bloklangan, 3 — sinov davrida, biri nomida «<», «&», biri 63 belgili), umumiy raqamlar olindi",
      _lg.status_code in (302, 303) and all(ID.values()) and _st == [200] * 4 and "bugun_kirish" in SUMMARY
      and _holat.get("Otgan Imtiyozda") == "otgan" and _holat.get("Bekobod Fasad") == "bloklangan" and _holat.get("Alfa Dekor MChJ") == "yaqin",
      (_lg.status_code, ID, _st, SUMMARY, _holat))

import uvicorn                                     # noqa: E402
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
BU = f"http://127.0.0.1:{port}"

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("D — HAQIQIY brauzer")
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════════
PW_BOR = True
try:
    from playwright.sync_api import sync_playwright
except Exception:                          # noqa: BLE001
    PW_BOR = False
check("D0 Python `playwright` bor", PW_BOR)

ROYXAT = r"""() => {
  const el = document.getElementById('plKartalar'), gr = el.getBoundingClientRect();
  const bosh = el.querySelector('.pl-jbosh');
  const bx = bosh ? [...bosh.children].map(c => Math.round(c.getBoundingClientRect().left)) : [];
  const q = [...el.querySelectorAll('.pl-card')].map(r => {
    const kat = [...r.querySelector('.pl-top').children, ...[...r.children].slice(1, 2), ...r.querySelector('.pl-raqam').children,
                 r.querySelector('.pl-btns')];
    const tug = [...r.querySelectorAll('.pl-btns button')];
    r.scrollIntoView({block: 'center'});                  // pastdagi qatorlar ham — `elementFromPoint` faqat oyna ichida
    const tb = tug.map(b => { const x = b.getBoundingClientRect(); const h = document.elementFromPoint(x.left + x.width / 2, x.top + x.height / 2);
      return {o: x.right, c: x.left, top: x.top, ust: x.bottom, bos: !!h && (h === b || b.contains(h))}; });
    const nr = r.querySelector('.pl-nom').getBoundingClientRect();
    const lb = [...r.querySelectorAll('.pl-raqam .l')];
    const bq = r.querySelector('.pl-raqam').children[1];
    const jm = r.querySelector('.pl-jami');
    return {id: r.dataset.korxona, nom: r.querySelector('.pl-nom').textContent, html: r.querySelector('.pl-nom').innerHTML,
            y: Math.round(r.getBoundingClientRect().height), x: kat.map(c => Math.round(c.getBoundingClientRect().left)),
            tugma: tug.map(b => b.textContent.trim()), tugma_ichida: tb.every(t => t.o <= Math.min(gr.right, innerWidth) + 0.5 && t.c >= gr.left - 0.5),
            tugma_bosiladi: tb.every(t => t.bos), tugma_ostida: tb.length ? tb.every(t => t.top >= nr.bottom - 0.5) : null,
            tugma_yonida: tb.length ? tb.every(t => t.top < nr.bottom && t.ust > nr.top) : null,
            fon: getComputedStyle(r).backgroundColor, nom_rang: getComputedStyle(r.querySelector('.pl-nom')).color,
            klass: r.className, l_matn: lb.map(x => x.textContent), l_kenglik: lb.map(x => Math.round(x.getBoundingClientRect().width)),
            l_display: lb.map(x => getComputedStyle(x).display),
            buyurtma_matn: bq ? bq.querySelector('.n').innerText.replace(/\s+/g, ' ').trim() : null,
            jami_korinadi: jm ? jm.getBoundingClientRect().width > 1 && getComputedStyle(jm).display !== 'none' : null,
            kod: {matn: r.querySelector('.pl-kod').textContent, title: r.querySelector('.pl-kod').title},
            blok: r.querySelector('.pl-blok') ? {matn: r.querySelector('.pl-blok').innerText.replace(/\s+/g, ' ').trim(),
                                                 title: r.querySelector('.pl-blok').title} : null,
            tugma_title: (r.querySelector('[data-amal="uzaytir"]') || {}).title || null};
  });
  const bg = document.querySelectorAll('#plRaqamlar');
  const bh = document.querySelector('.pl-head .pl-bugun');
  return {bosh: bosh ? {korinadi: getComputedStyle(bosh).display !== 'none', x: bx, matn: [...bosh.children].map(c => c.textContent),
                        amallar: getComputedStyle(bosh.lastElementChild).display !== 'none'} : null,
          qator: q, balandlik: Math.round(gr.height), kesilgan: el.scrollWidth - el.clientWidth,
          bugun: bh ? bh.textContent : null, bugun_soni: bg.length, bugun_bir: bg.length === 1 && bg[0] === bh,
          bugun_uslub: bh ? getComputedStyle(bh).fontSize + ' ' + getComputedStyle(bh).whiteSpace : null,
          stat: document.querySelectorAll('.pl-stat, .pl-stats').length,
          chip: [...document.querySelectorAll('#plChiplar .pl-chip')].map(c => c.textContent),
          toshma: document.documentElement.scrollWidth - document.documentElement.clientWidth};
}"""
NAT = {}
XATO = []

if PW_BOR and all(ID.values()):
    with sync_playwright() as pw:
        _exe = None
        for _y in sorted(glob.glob(os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers", "chromium-*",
                                                "chrome-linux", "chrome"))):
            _exe = _y
        br = pw.chromium.launch(executable_path=_exe) if _exe else pw.chromium.launch()

        def sahifa(w, h, tel=False, tungi=False):
            ctx = br.new_context(viewport={"width": w, "height": h}, timezone_id="Asia/Tashkent", locale="uz-UZ", is_mobile=tel, has_touch=tel)
            ctx.set_default_timeout(20000)
            ctx.route(re.compile(r"^https://.*"), lambda r: r.fulfill(status=204, body=""))
            if tungi:
                ctx.add_init_script("try { localStorage.setItem('theme', 'dark'); } catch (e) {}")
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: XATO.append(str(e)[:300]))
            xav(pg.goto, BU + "/login")
            xav(pg.fill, "input[name=username]", "k206_plat")
            xav(pg.fill, "input[name=password]", PAROL)
            xav(pg.press, "input[name=password]", "Enter")
            xav(pg.wait_for_load_state, "networkidle")
            xav(pg.goto, BU + "/platforma")
            xav(pg.wait_for_load_state, "networkidle")
            xav(pg.wait_for_timeout, 500)
            return ctx, pg

        for _w in (1920, 1440, 1366, 1280, 1101):
            ctx, pg = sahifa(_w, 1300)
            NAT[f"k{_w}"] = xav(pg.evaluate, ROYXAT)
            if _w == 1440:
                NAT["summary"] = xav(pg.evaluate, "async () => ((await (await fetch('/api/platform/summary')).json()) || {}).raqamlar || {}")
                _bid = str(ID["Alfa Dekor MChJ"])
                xav(pg.click, f'#plKartalar [data-korxona="{_bid}"] button[data-amal="uzaytir"]')
                xav(pg.wait_for_timeout, 300)
                NAT["uz_oyna"] = xav(pg.evaluate, """() => { const m = document.getElementById('plModal');
                    return {ochiq: m.classList.contains('ochiq'), matn: m.innerText.replace(/\\s+/g, ' ').slice(0, 300)}; }""")
                xav(pg.keyboard.press, "Escape")
                xav(pg.wait_for_timeout, 200)
                NAT["uz_yopildi"] = xav(pg.evaluate, "() => document.getElementById('plModal').classList.contains('ochiq')")
                xav(pg.click, f'#plKartalar [data-korxona="{ID["Sinov Korxona C"]}"] button[data-amal="blokla"]')
                xav(pg.wait_for_timeout, 300)
                NAT["bl_oyna"] = xav(pg.evaluate, """() => { const m = document.getElementById('plModal');
                    return {ochiq: m.classList.contains('ochiq'), matn: m.innerText.replace(/\\s+/g, ' ').slice(0, 300)}; }""")
                xav(pg.keyboard.press, "Escape")
                xav(pg.click, '[data-filtr="bloklangan"]')
                xav(pg.wait_for_timeout, 200)
                NAT["filtr"] = xav(pg.evaluate, """() => ({qator: [...document.querySelectorAll('#plKartalar .pl-card')].map(r => r.dataset.korxona),
                    bosh: !!document.querySelector('#plKartalar .pl-jbosh')})""")
                xav(pg.click, '[data-filtr="hammasi"]')
                xav(pg.fill, "#plQidiruv", "alfa")
                xav(pg.wait_for_timeout, 250)
                NAT["qidiruv"] = xav(pg.evaluate, "() => [...document.querySelectorAll('#plKartalar .pl-card')].map(r => r.dataset.korxona)")
                xav(pg.fill, "#plQidiruv", "yoq_bunday_korxona")
                xav(pg.wait_for_timeout, 250)
                NAT["bosh_royxat"] = xav(pg.evaluate, """() => { const e = document.querySelector('#plKartalar > .pl-izoh');
                    return {jbosh: !!document.querySelector('#plKartalar .pl-jbosh'), matn: document.getElementById('plKartalar').innerText.trim(),
                            chekka: e ? getComputedStyle(e).paddingLeft : null}; }""")
            ctx.close()

        for _w in (1440, 1280):
            ctx, pg = sahifa(_w, 1300, tungi=True)
            NAT[f"tungi{_w}"] = xav(pg.evaluate, ROYXAT)
            if _w == 1440:
                NAT["tema"] = xav(pg.evaluate, "() => document.documentElement.getAttribute('data-theme')")
                NAT["tungi_bosh"] = xav(pg.evaluate, """() => { const b = document.querySelector('#plKartalar .pl-jbosh span');
                    return b ? {rang: getComputedStyle(b).color, fon: getComputedStyle(b.parentElement).backgroundColor} : null; }""")
            ctx.close()
        ctx, pg = sahifa(1000, 900)
        NAT["k1000"] = xav(pg.evaluate, ROYXAT)
        ctx.close()
        ctx, pg = sahifa(390, 844, tel=True)
        NAT["t390"] = xav(pg.evaluate, ROYXAT)
        ctx.close()
        br.close()

    _BLOK = str(ID["Bekobod Fasad"])
    _YAQIN = str(ID["Alfa Dekor MChJ"])
    _OTGAN = str(ID["Otgan Imtiyozda"])
    _UZUN = str(ID[UZUN])
    _ODDIY = str(ID["Sinov Korxona C"])
    for _w in (1920, 1440, 1366):
        _r = NAT.get(f"k{_w}") or {}
        _q = _r.get("qator") or []
        _chek = lambda x: 92 if x["id"] == _UZUN else (64 if _w >= 1440 else 80)   # noqa: E731
        check(f"D1 {_w} px: har korxona — BITTA qator (9 ta; tugmalar nom bilan bir satrda), ≤ 64 px (bloklangan, imtiyozda ham; 63 belgili "
              f"nom ≤ 3 satr; 1366 da — eng tor bitta qator — ≤ 80); ro'yxat ≤ 9 × 64 + 60 (1366 da 9 × 80) (ilgari 7 korxona — 949 px)",
              len(_q) == 9 and all(x["y"] <= _chek(x) and x["tugma_yonida"] is True for x in _q)
              and (_r.get("balandlik") or 9999) <= (9 * 64 + 60 if _w >= 1440 else 9 * 80) and _r.get("toshma", 9) <= 1,
              lambda: ([(x["id"], x["y"], x["tugma_yonida"]) for x in _q], _r.get("balandlik"), _r.get("toshma")))
        _b = _r.get("bosh") or {}
        check(f"D2 {_w} px: ustunlar sarlavha bilan bir chiziqda (±1 px, 7 ustun, «Amallar» ham); har tugma ro'yxat va oyna ICHIDA, bosiladigan "
              f"(`elementFromPoint`), ro'yxat ichida kesilish yo'q",
              _b.get("korinadi") and _b.get("amallar") and len(_b.get("x") or []) == 7 and _q
              and all(len(x["x"]) == 7 and all(abs(a - b) <= 1 for a, b in zip(x["x"][:6], _b["x"][:6])) for x in _q)
              and all(x["tugma_ichida"] and x["tugma_bosiladi"] for x in _q) and _r.get("kesilgan", 9) <= 1,
              lambda: (_b, [(x["id"], x["x"], x["tugma_ichida"], x["tugma_bosiladi"]) for x in _q], _r.get("kesilgan")))
    for _w in (1280, 1101):
        _r = NAT.get(f"k{_w}") or {}
        _q = _r.get("qator") or []
        _b = _r.get("bosh") or {}
        check(f"D12 {_w} px (chap menyu bilan ro'yxat < 1094 px): ustunlar sarlavha bilan bir chiziqda (6 ustun, «Amallar» sarlavhasi yo'q), "
              f"tugmalar qator OSTIDA — KESILMAYDI: har tugma ro'yxat va oyna ichida, bosiladigan; qator ≤ 130 px; toshish yo'q",
              len(_q) == 9 and _b.get("korinadi") and _b.get("amallar") is False
              and all(len(x["x"]) == 7 and all(abs(a - b) <= 1 for a, b in zip(x["x"][:6], _b["x"][:6])) for x in _q)
              and all(x["tugma_ostida"] is True and x["tugma_ichida"] and x["tugma_bosiladi"] and x["y"] <= 130 for x in _q)
              and _r.get("kesilgan", 9) <= 1 and _r.get("toshma", 9) <= 1,
              lambda: (_b, [(x["id"], x["y"], x["tugma_ostida"], x["tugma_ichida"], x["tugma_bosiladi"]) for x in _q], _r.get("kesilgan"),
                       _r.get("toshma")))
    _r = NAT.get("k1440") or {}
    _q = {x["id"]: x for x in (_r.get("qator") or [])}
    _sm = NAT.get("summary") or {}
    check("D3 tepada raqam-kartalar YO'Q; bitta `#plRaqamlar` — saralash yonidagi «Bugun: N kirish · N xato» (13 px, bir satr) = "
          "`/api/platform/summary` (har kirish sanaladi — N ≥ 2); saralash tugmalarida sonlar (Hammasi · 9, Faol · 6, Muddati yaqin · 2, "
          "Bloklangan · 1, Sinov davri · 4)",
          _r.get("stat") == 0 and _r.get("bugun_bir") is True and _r.get("bugun_uslub") == "13px nowrap" and (_sm.get("bugun_kirish") or 0) >= 2
          and _r.get("bugun") == f"Bugun: {_sm.get('bugun_kirish')} kirish · {_sm.get('bugun_xato')} xato"
          and _r.get("chip") == ["Hammasi · 9", "Faol · 6", "Muddati yaqin · 2", "Bloklangan · 1", "Sinov davri · 4"],
          lambda: (_r.get("stat"), _r.get("bugun_soni"), _r.get("bugun_bir"), _r.get("bugun_uslub"), _r.get("bugun"), _sm, _r.get("chip")))
    check("D4 tugmalar: oddiy qatorda «Uzaytirish» (title «Muddatni uzaytirish») / «Bloklash» / «Parolni tiklash»; bloklanganda «Ochish» / "
          "«Uzaytirib ochish» / «Parolni tiklash»",
          _q and all(x["tugma"] == ["Uzaytirish", "Bloklash", "Parolni tiklash"] and x["tugma_title"] == "Muddatni uzaytirish"
                     for k, x in _q.items() if k != _BLOK)
          and (_q.get(_BLOK) or {}).get("tugma") == ["Ochish", "Uzaytirib ochish", "Parolni tiklash"],
          lambda: {k: (x["tugma"], x["tugma_title"]) for k, x in _q.items()})
    _uz, _bl = NAT.get("uz_oyna") or {}, NAT.get("bl_oyna") or {}
    check("D5 «Uzaytirish» — o'sha korxona oynasi ochiladi, Esc yopadi; «Bloklash» — o'sha korxona bloklash oynasi",
          _uz.get("ochiq") is True and "Alfa Dekor MChJ" in (_uz.get("matn") or "") and NAT.get("uz_yopildi") is False
          and _bl.get("ochiq") is True and "Sinov Korxona C" in (_bl.get("matn") or ""), lambda: (_uz, NAT.get("uz_yopildi"), _bl))
    check("D6 saralash «Bloklangan» — faqat bloklangan qator (sarlavha bilan); qidiruv «alfa» — Alfa; mos korxona yo'q — izoh (ro'yxat "
          "chegarasidan ichkarida), sarlavha satri yo'q",
          (NAT.get("filtr") or {}).get("qator") == [_BLOK] and (NAT.get("filtr") or {}).get("bosh") is True
          and NAT.get("qidiruv") == [_YAQIN] and (NAT.get("bosh_royxat") or {}).get("jbosh") is False
          and "Tanlovga mos korxona yo'q" in (NAT.get("bosh_royxat") or {}).get("matn", "")
          and (NAT.get("bosh_royxat") or {}).get("chekka") == "14px",
          lambda: (NAT.get("filtr"), NAT.get("qidiruv"), NAT.get("bosh_royxat")))
    _bq = _q.get(_BLOK) or {}
    _bk = _bq.get("blok") or {}
    check("D7 bloklangan qator: qisqa izoh (sana · sabab) ko'rinadi, «obuna … tugagan», izoh va «Ma'lumoti saqlangan» — faqat `title` da; "
          "«Buyurtma» — jami, sonning yonida «jami» ko'rinadi (ustun sarlavhasi — shu oy); oddiy qatorda «jami» yo'q",
          re.fullmatch(r"\d\d\.\d\d\.\d{4} dan bloklangan · sabab: To'lov qilinmagan", _bk.get("matn") or "")
          and "Iyun to'lovi kelmadi" in (_bk.get("title") or "") and "Ma'lumoti saqlangan" in (_bk.get("title") or "")
          and _bq.get("buyurtma_matn") == "0 jami" and _bq.get("jami_korinadi") is True
          and all(x["jami_korinadi"] is None and "jami" not in (x["buyurtma_matn"] or "") for k, x in _q.items() if k != _BLOK),
          lambda: (_bk, _bq.get("buyurtma_matn"), _bq.get("jami_korinadi"), [(k, x["buyurtma_matn"]) for k, x in _q.items()]))
    _ch = (_q.get(str(ID["Chust <Dekor> & Co"])) or {})
    check("D8 nomda «<», «&» — matn sifatida (element yaratilmaydi); kod qatori «…» bilan kesilsa ham to'liq matni `title` da (HAMMA qatorda)",
          _ch.get("nom") == "Chust <Dekor> & Co" and _ch.get("html") == "Chust &lt;Dekor&gt; &amp; Co"
          and _q and all(x["kod"]["title"] == x["kod"]["matn"] and x["kod"]["matn"].endswith(" dan") for x in _q.values()),
          lambda: (_ch.get("nom"), _ch.get("html"), [x["kod"] for x in _q.values()]))
    _tq = {x["id"]: x for x in ((NAT.get("tungi1440") or {}).get("qator") or [])}
    _tb = NAT.get("tungi_bosh") or {}
    _kk = [kontrast(rgb((d.get(k) or {}).get("nom_rang")), rgb((d.get(k) or {}).get("fon"))) for d in (_q, _tq) for k in (_YAQIN, _BLOK, _OTGAN)]
    _t_bosh = kontrast(rgb(_tb.get("rang")), rgb(_tb.get("fon")))
    _farq = kontrast(rgb((_tq.get(_OTGAN) or {}).get("fon")), rgb((_tq.get(_ODDIY) or {}).get("fon")))
    check("D9 rang: muddati yaqin qator — sariq (#FFFBEB), imtiyozda va bloklangan — qizg'ish (#FBF5F5), oddiy — oq; tungi rejimda imtiyozda / "
          "bloklangan — #2A1E22 (oddiy qatordan farqli); kontrast ≥ 4,5:1 (yorug' va tungi, sarlavha satri ham)",
          rgb((_q.get(_YAQIN) or {}).get("fon")) == (255.0, 251.0, 235.0) and rgb((_q.get(_BLOK) or {}).get("fon")) == (251.0, 245.0, 245.0)
          and rgb((_q.get(_OTGAN) or {}).get("fon")) == (251.0, 245.0, 245.0)
          and rgb((_q.get(_ODDIY) or {}).get("fon")) == (255.0, 255.0, 255.0) and NAT.get("tema") == "dark"
          and rgb((_tq.get(_OTGAN) or {}).get("fon")) == (42.0, 30.0, 34.0) and rgb((_tq.get(_BLOK) or {}).get("fon")) == (42.0, 30.0, 34.0)
          and rgb((_tq.get(_ODDIY) or {}).get("fon")) != (42.0, 30.0, 34.0) and min(_kk + [_t_bosh]) >= 4.5,
          lambda: ([(k, (_q.get(k) or {}).get("fon"), (_tq.get(k) or {}).get("fon")) for k in (_YAQIN, _BLOK, _OTGAN, _ODDIY)], _kk, _t_bosh, _farq))
    _L = ["Foydalanuvchi:", "Buyurtma (shu oy):", "Oxirgi kirish:"]
    _LB = ["Foydalanuvchi:", "Buyurtma (jami):", "Oxirgi kirish:"]
    check("D13 jadvalda (1440 px) raqam nomlari ko'zdan yashirin (1 px), lekin ekran o'quvchisi uchun BOR (`display:none` emas, matni "
          "«Foydalanuvchi:» / «Buyurtma (shu oy):» — bloklanganda «Buyurtma (jami):» / «Oxirgi kirish:»)",
          _q and all(x["l_matn"] == (_LB if k == _BLOK else _L) and all(w <= 1 for w in x["l_kenglik"])
                     and all(d != "none" for d in x["l_display"]) for k, x in _q.items()),
          lambda: [(k, x["l_matn"], x["l_kenglik"], x["l_display"]) for k, x in _q.items()])
    for _nom, _w in (("k1000", 1000), ("t390", 390)):
        _r = NAT.get(_nom) or {}
        _qq = {x["id"]: x for x in (_r.get("qator") or [])}
        check(f"D10 {_w} px: ixcham kartochka — sarlavha satri yo'q, raqam nomlari ko'rinadi («Foydalanuvchi:» …), «jami» yo'q (nomida bor), "
              f"bloklanganda to'liq izoh; tugmalar bosiladi; yon tomonga toshmaydi",
              len(_qq) == 9 and (_r.get("bosh") or {}).get("korinadi") is False
              and all(x["l_matn"] == (_LB if k == _BLOK else _L) and all(w > 20 for w in x["l_kenglik"]) for k, x in _qq.items())
              and (_qq.get(_BLOK) or {}).get("jami_korinadi") is False
              and "Ma'lumoti saqlangan" in ((_qq.get(_BLOK) or {}).get("blok") or {}).get("matn", "")
              and all(x["tugma_ichida"] and x["tugma_bosiladi"] for x in _qq.values()) and _r.get("toshma", 9) <= 1 and _r.get("kesilgan", 9) <= 1,
              lambda: ((_r.get("bosh") or {}).get("korinadi"), [(k, x["l_matn"], x["l_kenglik"], x["y"], x["tugma_ichida"], x["tugma_bosiladi"])
                                                                for k, x in _qq.items()],
                       (_qq.get(_BLOK) or {}).get("blok"), (_qq.get(_BLOK) or {}).get("jami_korinadi"), _r.get("toshma"), _r.get("kesilgan")))
    _t2 = NAT.get("tungi1280") or {}
    check("D14 tungi rejim, 1280 px: tugmalar kesilmaydi va bosiladi, imtiyozdagi qator qizg'ish",
          len(_t2.get("qator") or []) == 9 and all(x["tugma_ichida"] and x["tugma_bosiladi"] for x in _t2["qator"]) and _t2.get("kesilgan", 9) <= 1
          and any(x["id"] == _OTGAN and rgb(x["fon"]) == (42.0, 30.0, 34.0) for x in _t2["qator"]),
          lambda: ([(x["id"], x["tugma_ichida"], x["tugma_bosiladi"], x["fon"]) for x in (_t2.get("qator") or [])], _t2.get("kesilgan")))
    check("D11 sahifada JS xatosi yo'q (kompyuter, oraliq kengliklar, tungi, planshet, telefon)", not XATO, XATO)
server.should_exit = True

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
for _f in FAILED:
    print("  ✗", _f)
sys.exit(1 if FAIL else 0)
