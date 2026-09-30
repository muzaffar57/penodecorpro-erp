# PenoDecorPro ERP — LOYIHA PASPORTI

*Yozilgan: 2026-09-28 (kech104, 16-band; yangilangan — kech105: zip 99, zip 100; kech106: zip 101; kech107: zip 102; kech108: zip 103, `main` o'lchovlari; kech109: zip 104, `main` ko'chirish mexanizmi; kech110: zip 105 — tahrirda kelishilgan summa, MRP jurnali; kech111: zip 106 — platforma admin paneli: obuna, bloklash, eslatma, fayllar himoyasi; zip 107 — yuqori panel ochiluvchi panellari ekran ichida (K112-1), bloklashda ochiq sessiya sabab bilan yopiladi (K112-2); kech112: zip 108 — «Tayyor» da bo'sh loy = reja (K112-3), material nomi (K112-4), MRP qoplama belgisi (K112-5); ko'p korxonali yakuniy jonli sinov; kech115: zip 112 — butun dastur auditi A bosqichi (pul va ma'lumot xatolari) 1-qismi: kirim, qarzdorlar, «Tayyor», narxsiz buyurtma, o'chirilganlar jurnali, manfiy raqamlar, taqqoslash, korxona sog'ligi, ombor filtri; kech116: zip 113 — A bosqich 2-qismi: sog'liq sabablari (K115-2), «Bugungi xulosa» (K115-3), hujjatlardagi hisob qatorlari (G2-04), «Pul oqimi» — haqiqiy pul (G1-03), «Xarajat» — bitta ta'rif va «Tannarx» (G1-02), loyiha qiymati buyurtmalardan (G2-01), haqiqiy IP va kirish cheklovi (U-01), parol oynasi va kirishlarni yopish (G6-06); zip 114 — mijoz hujjatlarida kechirilgan qarz «Chegirma» ichida (egasi qarori); kech117: zip 115 — A2: yo'nalishlar bo'yicha moliya (G3-11, G6-09); zip 116 — jonli sinovdan keyin: «Belgilanmagan» manbalari, Moliya xarajatdan keyin yangilanadi; kech118: qolgan egasi qarorlari (6-bo'lim); zip 117 — B bosqichi 1-qism: dastur oynalari (xabar, kiritish, Esc / tashqariga bosish), o'zbekcha 404 / 403 sahifa, klaviatura fokusi; zip 118 — B bosqichi 2-qism: son / sana / birlik ko'rinishi, o'qiladigan rang, 12 px + yo'nalishlar bo'yicha moliyaviy natija (egasi qarori: taqsim yo'q, oyliklar alohida, davr, solishtirish); yangi qarorlar — rollar va ruxsatlar (6-bo'lim)). Egasi: Muzaffarbek (PenoDecorPro, Andijon — penoplast fasad bezaklari).*
*Bu faylni `main` ga ko'chirish bilan birga, keyin har katta o'zgarishda yangilab boring. 9-bo'lim AVTOMATIK
(`python3 tools/pasport_xarita.py --yoz`), qolgani qo'lda; `tools/test_pasport.py` ikkalasini ham tekshiradi.*

---

## 0. Bu fayl nima

Yangi chatda kichik tuzatish yoki o'zgartirish uchun **repo + muammo tavsifi yetarli** bo'lishi kerak — uzun
TOPSHIRIQ hujjati shart emas. Yangi chat shunday boshlaydi:

1. `git clone -b staging https://github.com/muzaffar57/penodecorpro-erp.git repo` va `git log --oneline -5`.
2. Shu faylni o'qing: avval 1-bo'lim (qoidalar) va 6-bo'lim (qabul qilingan qarorlar — QAYTA SO'RALMAYDI).
3. Muammoga tegishli joyni 9-bo'lim xaritasidan toping: sahifa → handler → shablon → API → `crud` / `services`
   funksiyalari. So'ng o'sha funksiyani o'qing.
4. Tuzatishdan OLDIN muammoni o'lchang (lokal SQLite + HAQIQIY PostgreSQL, kerak bo'lsa sinov saytida), keyin
   tuzating, test yozing, mutatsiya bilan tekshiring (5-bo'lim), zip bering (2-bo'lim, yuklash tartibi).

Egasining ish uslubi: dasturchi EMAS, o'zbek tilida yozadi, rus tilini o'qimaydi. Texnik savollar bermang —
texnik yechimni o'zingiz tanlab, sababini oddiy tilda tushuntiring. Faqat BIZNES qarorlari (pul, mijoz,
jarayon) uniki — ularni misol (haqiqiy raqamlar) va tavsiya bilan, tugmali savol qilib bering.

## 1. Ish qoidalari

- **`staging` da bemalol, `main` ga tegilmaydi.** Hamma o'zgarish avval `staging` da (sinov sayti). `main`
  (haqiqiy ma'lumot) faqat egasining ANIQ roziligi bilan, bir martalik, ehtiyotkor ko'chirish orqali.
- **Taxmin qilinmaydi — o'lchanadi.** Har da'vo (nuqson bor / yo'q, raqam, sabab) kod o'qish + ishga tushirish
  bilan isbotlanadi. Eng kichik nuqson ham muhim.
- **Pul / yaxlitlash / sig'im masalalari HAQIQIY PostgreSQL da o'lchanadi.** SQLite `Numeric(12,2)` ni
  yaxlitlamaydi, FK ni sukut bo'yicha tekshirmaydi, `ORDER BY` siz so'rov rowid tartibida keladi (PG da
  tartibsiz) — SQLite natijasi yolg'on xotirjamlik beradi. Har yangi test birinchi kundan IKKALA rejimda.
- **Darvoza (test) yozilsa — mutatsiya bilan sinaladi.** Eng kuchlisi: testni tuzatishdan OLDINGI asl kodga
  qarshi yurgizish — yiqilishi SHART, test QULAMASLIGI shart (yangi nomlarga `getattr`, HTTP xatosi → 599).
  Mutatsiya ushlanmasa — sababini tahlil qiling (ikkinchi to'siq bormi, test holati ko'rmaydimi, ekvivalentmi).
- **Kod hech qachon qisqartirilmaydi, qismlarga bo'linmaydi, TODO / joy-to'ldiruvchi qoldirilmaydi** — har
  fayl 100% to'liq va ishchi holatda beriladi.
- **Zip nomi:** `penodecorpro_NN_GITHUBGA.zip` — egasi GitHub'ga yuklaydi; `..._GITHUBGA_EMAS.zip` — faqat
  keyingi chatga biriktiriladi (ish skriptlari). Har safar qaysi biri ekanini ANIQ ayting. Ataylab yiqiladigan
  (tuzatishi hali yo'q) test GitHub'ga YUKLANMAYDI — `tools/hammasi.sh` etalonini buzadi.
- **Sinov saytida Claude o'zi ishlaydi** (tugma bosish, yozish, o'chirish — ruxsat so'ramaydi; sinov
  ma'lumoti buzilishi muammo emas). Parol / login kiritilmaydi — sessiya bo'lmasa egasidan kirishni so'rang.
  Claude Code avto-rejim klassifikatori jonli yozuvni rad etsa — aylanib o'tilmaydi, lokal PG isboti bilan
  almashtiriladi. Sinov saytida Telegram xabarlari O'CHIRILGAN.
- **Chat to'lib borayotganini Claude o'zi aytadi** va keyingi chat uchun hujjat yozadi.
- **Egasining vazifasi kelganda** (yuklash, zaxira, qaror) — oldindan aniq ogohlantiring va uni kuting.
- **`main` ga ko'chirish bosqichiga yetilganda** Claude alohida xabar bilan ogohlantiradi: "`main` ga
  ko'chirishga yetib keldik" — nima qilinishi, egasidan nima kerakligi (zaxira, yuklash, qarorlar) va uning
  roziligisiz `main` ga hech narsa tegmasligi.

## 2. Muhit: `staging` va `main`

- **Repo:** `muzaffar57/penodecorpro-erp` (ochiq). Shoxlar: `staging` (sinov) va `main` (haqiqiy).
- **Railway loyihasi `blissful-unity`**, ikki muhit BIR loyihada (bitta ochiluvchi ro'yxatdan almashadi —
  xavfli amaldan oldin qaysi muhit tanlanganini tekshiring):
  - `sinov` → shox `staging` → `https://web-sinov.up.railway.app`
  - `production` → shox `main` → `https://web-production-a064.up.railway.app`
- **Stek:** Python 3.12 (`runtime.txt`), FastAPI, SQLAlchemy 2.0, `pg8000`, Jinja2 shablonlar, ReportLab (PDF),
  APScheduler (kunlik zaxira 23:30 Toshkent vaqti bilan — `main.run_daily_backup`). `Procfile`:
  `uvicorn main:app`. Baza: Railway PostgreSQL; lokal testlar SQLite va PostgreSQL 16.
- **Diqqat — Python versiyasi:** `saas_migration.py` da 3.12 ga xos f-satr bor; 3.11 da u yuklanmaydi (`main.py`
  uni `try/except` bilan ulaydi), shuning uchun lokal 3.11 testlarida `/saas-migratsiya` marshrutlari yo'q.
- **Yuklash tartibi (egasi qiladi):** zipni ochadi, papka ICHIDAGI narsalarni GitHub saytida `staging` shoxida
  **Add file → Upload files** ga sudraydi. `templates/*.html` fayllari `templates/` papkasi ICHIGA tushishi SHART
  (ikki marta ildizga tushgan — sahifa eski qolgan; bir marta `templates/` dagi fayllar adashib o'chirilgan →
  500). Yuklangach Claude YANGI klon qiladi: `git diff --name-status <oldingi> HEAD` faqat kutilgan fayllar,
  MD5 + qator soni AYNAN; so'ng sinov saytida deploy isboti (faqat o'qish: hisobotlar SHA-256 si oldingi bilan,
  yangi kod belgilari, `/logs` da yangi xato yo'q). Railway `staging` ga push bo'lishi bilan o'zi deploy qiladi.
- **Tarmoq:** Claude konteyneri `railway.app` ga chiqolmaydi — jonli ish faqat brauzer orqali (Claude
  ilovasining ichki brauzeri). Konteyner (VM) javoblar orasida qayta yuklanishi mumkin: fayllar qoladi,
  jarayonlar (PostgreSQL, fon testlari) o'ladi — fon ishlarini `setsid nohup … &` bilan va qayta davom
  etadigan qilib yozing.
- **Muhit o'zgaruvchilari** — 9-bo'lim, MUHIT bloki. `TENANT_FILTER=1` — global korxona filtri (4-bo'lim).
- **Zaxira:** `sinov` da Railway volume backup va PITR yoqilgan (Pro reja). `production` uchun to'liq zaxira
  (Railway Backups tab yoki `pg_dump --format=custom`) — `main` ga har qanday ko'chirishdan OLDIN majburiy.
  `/api/system/backup` (JSON eksport) — PostgreSQL zaxirasi EMAS: foydalanuvchilar paroli olib tashlanadi va
  `POST /api/system/restore` faqat chaqiruvchi korxonasiga tiklaydi (`users` tiklanmaydi).
  Yuklangan fayllar (chizma, rasm, logotip) bazada EMAS — `static/uploads/` da; ular Railway Volume da (`/app/static/uploads`)
  turishi SHART, aks holda har deployda yo'qoladi (kech111); JSON zaxira va PITR ularni saqlamaydi.

## 3. Tuzilma

Ildizdagi Python fayllari (vazifasi; aniq marshrutlar va funksiyalar — 9-bo'lim):

- `main.py` — FastAPI ilovasi: HAMMA sahifa va API marshrutlari (production va saas_migration dan tashqari),
  ishga tushishdagi `_migrate_*` migratsiyalar (9-bo'lim ISHGA_TUSHISH), Telegram yuborish, kunlik zaxira.
- `crud.py` — bazaga yozish / o'qish: buyurtma, loyiha, to'lov, yetkazish (yuk xati), qaytarish, ombor, tayyor
  mahsulot, hodim, ta'minotchi, sozlamalar, zaxira / tiklash, jurnal.
- `services.py` — biznes mantiqi va hisob-kitob: buyurtma foydasi, «Tayyor» (yakunlash), oylik hisobot, usta KPI,
  dashboard, qarz xulosasi, ogohlantirishlar.
- `models.py` — SQLAlchemy modellari (45 jadval), korxona qoidalari `_TENANT_RULES` / `_TENANT_REFS`, pul
  yordamchilari (`pul_tiyin`, `QARZ_BARDOSH`). `production_models.py` — MRP jadvallari (`companies`,
  `product_types`, `boms`, `bom_items`, `production_orders`).
- `production_routes.py`, `production_service.py`, `production_schemas.py` — dinamik ishlab chiqarish (MRP):
  mahsulot turi, retsept (BOM), ishlab chiqarish buyurtmasi (qoralama → boshlash → yakunlash / bekor).
- `auth.py` — login (cookie sessiya, bcrypt), rollar va qorovullar (`admin_only`, `platform_admin_only`, …),
  korxona qorovullari (`order_of_company` va h.k.), hodim (PIN) paneli sessiyasi.
- `schemas.py` — Pydantic sxemalari (kirish tekshiruvi: manfiy / haddan katta qiymatlar 422).
- `database.py` — ulanish (`pool_pre_ping`, `pool_recycle=280`), `get_db`, Toshkent vaqti yordamchilari (hisobot davri —
  `tashkent_oyida` va h.k.; ko'rinish — `tashkent_vaqt`).
- `tenant_context.py` — `TENANT_FILTER=1` bo'lsa har so'rovga korxona filtri (sessiya obyektiga bog'langan).
- `company_brand.py` — hujjatlardagi korxona nomi / telefoni / logotipi (korxona bo'yicha).
- `pdf_service.py`, `delivery_pdf.py`, `finance_pdf.py` — nakladnoy, yuk xati, oylik moliya hisobotining PDF lari
  (foydalanuvchi matni — `_x(…)`, katta sarlavha — korxona nomi; kech106, K106-3 / K106-4).
- `pdf_shrift.py` + `fonts/` — PDF shrifti: Liberation Sans 2.1.5 (SIL OFL 1.1, `fonts/OFL.txt`) standart Helvetica nomlari
  bilan (kech106, K106-1); har PDF moduli boshida `shriftlarni_ulash()`.
- `saas_migration.py` — VAQTINCHALIK: ko'p korxonali (SaaS) migratsiya sahifasi `/saas-migratsiya`
  (bosqichlar W1–W6, dry-run; `sinov` da BAJARILGAN, `main` da hali bajarilmagan).
- `obuna.py` — (kech111) PLATFORMA: korxona obunasi, bloklash / ochish, uzaytirish, sinov davri, kunlik tekshiruv (eslatma,
  avtomatik bloklash), mijoz ogohlantirishi, platforma paneli ro'yxati / raqamlari / xatolari — YAGONA manba (4-bo'lim
  "Platforma — obuna va bloklash"). Platforma moduli: so'rovlari ataylab korxonalararo (`system_context`), `tools/tenant_lint.py`
  uni tekshirmaydi.
- `saas_otish.py` — (kech109, K108-1) `main` ga BIR MARTALIK o'tish: ilova ishga tushishida, `init_database()` dan OLDIN,
  eski (to'lqinlarsiz) bazani aniqlab `saas_migration` to'lqinlarini SINOV → HAQIQIY bajaradi (4-bo'lim "`main` ko'chirishi").
- `erp_backup_tekshiruv.py` — JSON zaxira faylini tekshiruvchi mustaqil skript (tiklamaydi).
- `templates/` — 25 ta Jinja2 sahifa (kech111: `platforma.html` — platforma paneli; `base.html` — umumiy qobiq, brauzer vaqti yordamchilari `tk*`, server rad sababi
  `xatoSababi` / `serverXatoSababi`; kech107 da hech bir handler ko'rsatmaydigan eski usta shabloni olib tashlandi); `static/` — CSS,
  logotiplar, `translit.js` (Kirill ↔ Lotin). Statik fayl o'zgarsa `main.py` dagi `static_version` ni oshiring (kesh).
- `tools/` — testlar (`test_*.py`, `test_*.js`), `tenant_lint.py` (+ `tenant_lint_baseline.json`),
  `narx_etalon_baza.py` / `narx_etalon_jonli.json` (narx etaloni), `pasport_xarita.py` (shu faylning xaritasi),
  `hammasi.sh` (barcha testlar), `vaqt_sayohati.sh` (+ `vaqt_sayohati/sitecustomize.py` — to'plam soat chegarasi paytlarida).

## 4. Asosiy qoidalar (kodda)

**Korxona (tenant) izolyatsiyasi.** (kech108, K107-2: login `User.username` BUTUN TIZIM bo'yicha yagona — bandlik tekshiruvi `auth._login_egasi` tizim so'rovi, `skip_tenant_filter`; TENANT_FILTER=1 da boshqa korxonadagi band login — 400.) Har korxona ma'lumoti `company_id` bilan. So'rovdagi korxona —
`auth.company_id_of(current_user)`; ID bo'yicha yozuv faqat korxona qorovuli bilan olinadi
(`auth.order_of_company`, `auth.project_of_company`, …). `models.py` dagi `_TENANT_RULES` (ota orqali korxona)
va `_TENANT_REFS` (begona korxona yozuviga havola → `TenantMismatchError`, 409) ORM darajasida ikkinchi to'siq.
`TENANT_FILTER=1` (Railway o'zgaruvchisi) — `tenant_context.py` har SELECT ga korxona shartini qo'shadi
(uchinchi to'siq). Yangi yozuv yaratilganda `company_id` ANIQ beriladi (bazada `DEFAULT` yo'q — unutilsa NOT NULL
xatosi). `tools/tenant_lint.py` yangi filtrsiz so'rovni ushlaydi (`--update` faqat qator raqamlari siljiganda).
Ikkinchi korxona bilan test (A va B tomondan) — izolyatsiya testlarining majburiy qismi.

**Pul.** Pul ustunlari `Numeric(12,2)` (tiyin aniqligi); yaxlitlash HALF_UP; yig'indi `Decimal` bilan.
Qarz / to'lov holati `models.pul_tiyin` bilan, 0.5 so'mdan kichik qoldiq — qarz emas (`models.QARZ_BARDOSH`).
Ekranda sonlar `toLocaleString('ru-RU')`; ko'rsatish uchun yaxlitlangan qiymat hisobga qaytib kirmasin.

**Atomiklik va poygalar.** Bir nechta jadvalga yozadigan amal `crud.bitta_tranzaksiya` ichida (nosozlikda hech
narsa saqlanmaydi). Pul amallari `crud._pul_qulfi` (PostgreSQL advisory lock) ostida, qulfdan keyin qayta o'qish;
takror yuborish himoyasi `crud.PUL_TAKROR_SONIYA` (8 s) — hodim panelidagi avans so'rovi ham (`crud.create_advance_request`,
qulf 107 — hodim bo'yicha; kech107, 10c). Buyurtma yaratish loyiha bo'yicha qulflanadi
(`crud.create_order`). Ombor qatori `with_for_update()` bilan — bunday modelga `lazy="joined"` qo'yilmaydi.

**Vaqt.** Baza vaqtni UTC da (naive) saqlaydi (`datetime.utcnow`). Hisobotlarning kun / oy / yil chegaralari —
TOSHKENT kalendari (UTC+5, kun 00:00 da almashadi; kech105 QARORI, 6-bo'lim): davr sharti `database.tashkent_kunida`,
`database.tashkent_oyida`, `database.tashkent_yilida` (UTC `[boshi, oxiri)` oralig'i — `extract('year' / 'month')`
ISHLATILMAYDI, u UTC oyini oladi); "bugun" / joriy oy / yil — `database.tashkent_date()`,
`database.tashkent_today_start_utc` (`datetime.utcnow().date()` / `.year` ham, jarayon mintaqasiga bog'liq
`date.today()` / `datetime.now()` ham EMAS). Faqat sana kiritiladigan qiymatlar (xarajat / avans sanasi — 00:00) o'z
kunida qoladi. Bosh sahifa grafigi (`services.get_chart_data`) — Toshkent kalendar oylari, daromadi «Tayyor» oyi
bo'yicha (oylik hisobot kabi; kech105, K105-4).
KO'RINISH ham Toshkent vaqtida (kech106): serverda sana-vaqt matni — `database.tashkent_vaqt(dt)` (berilmasa — hozir;
`datetime.now()` / `date.today()` ISHLATILMAYDI — Railway jarayoni UTC da), shablonda — Jinja `|toshkent` filtri
(`{{ o.created_at|toshkent('%d.%m.%Y') }}`; istisno — `ErrorLog.created_at`, u `models._uzb_now` bilan allaqachon
Toshkentda), PDF lar ham shu orqali. Brauzerda — `templates/base.html` dagi `tk*` yordamchilari (`templates/hodim_panel.html`
da AYNAN nusxa): `tkMs` zona belgisiz server vaqtini UTC deb o'qiydi (`new Date(s)` uni MAHALLIY deb o'qiydi — 5 soat
orqada), `tkSana` / `tkSanaVaqt` / `tkToliq` — ko'rsatish (til va format o'zgarmaydi), `tkISO()` — "bugun"
(`<input type="date">` standarti; `toISOString()` — UTC sanasi), `tkHozir()` — joriy oy / yil, `tkKunFarqi` — Toshkent
kalendar kunlari. Shablon JS da (`tk*` blokidan tashqarida) `new Date(server_vaqti)`, `toISOString()`, mahalliy
`getMonth()` / `toLocaleDateString` ishlatilmaydi.

**PDF shrifti (kech106, K106-1).** ReportLab standart Helvetica (Type1, WinAnsi) Kirill harflari, "№" va emoji ni QORA
KVADRAT (■) qilib chizadi — shuning uchun `pdf_shrift.shriftlarni_ulash()` Liberation Sans ni 'Helvetica', 'Helvetica-Bold',
'Helvetica-Oblique', 'Helvetica-BoldOblique' NOMLARI bilan ro'yxatga oladi (metrikasi Helvetica bilan bir xil — joylashuv
o'zgarmaydi; PDF kodidagi `fontName='Helvetica…'` va `<b>` / `<i>` o'zgarishsiz TTF ni oladi); shriftda yo'q belgi
(ma'lumotdagi emoji) chizilmaydi. PDF kodi matnlarida emoji / shriftda yo'q belgi ishlatilmaydi; `fonts/` deployga kiradi;
ReportLab `requirements.txt` da 4.2.x (yangilansa — `tools/test_pdf_shrift.py` qayta).

**PDF matni (kech106, K106-3 / K106-4).** ReportLab `Paragraph` matnni BELGILASH (markup) sifatida o'qiydi: foydalanuvchi
matnidagi "<" + harf ("Karniz <A>", izoh "<b>izoh") PDF ni 500 qilardi — shuning uchun `Paragraph` ga foydalanuvchi /
korxona matni (nom, telefon, manzil, izoh, tashuvchi, turkum) FAQAT `_x(…)` (xml escape; har PDF modulida) orqali; tizim
qiymatlari (raqam, holat yorlig'i, oy nomi, hujjat raqami) — `tools/test_pdf_matn.py` dagi ro'yxatda. Jadval katagidagi
oddiy satr (Paragraph emas) belgilash sifatida o'qilmaydi. Hujjatning katta sarlavhasi — korxona nomi
(`_brand["name"].upper()`); qattiq "PENODECORPRO" YO'Q (boshqa korxona hujjatida bizning nom chiqardi).

**Moliya xarajatlar ro'yxati (kech106, K106-2).** Oylik hisobot PDF idagi "Xarajatlar tafsiloti" va Moliya sahifasidagi
xarajatlar ro'yxati (`buildExpDetail`) — hisobot (`services.get_monthly_report`) qismlaridan, JAMI XARAJAT bilan BIR manba:
asosiy 4 turkum (`xarajatlar`), qo'shimcha turkumlar (`qoshimcha_xarajatlar` — tannarxga qo'shilgan kirim xarajatlari
kirmaydi), transport (xarid va yuk — korxona hisobidan), usta KPI, hodimlar, Ehson, brak, ishlab chiqarish; "Boshqa" /
"Kutilmagan" — izoh bo'yicha; omborda tayyor turgan mahsulot yo'qotishi — "Brak" dan ALOHIDA qator (`fp_loss_xarajat`,
kech107). Qatorlar yig'indisi = JAMI (tekshiruv shu xossa bilan).

**Brak summasi — BITTA raqam (kech107, 49-band qarori).** Brak qiymati — brak chiqim harakatlari, chiqim paytidagi
muzlatilgan narx bilan: `crud.get_brak_material_summary` (narx qoidasi — `crud._brak_harakat_narxi`, davr oxiri
KIRMAYDI). Karta va bosh sahifa (`crud.get_return_stats` — shu oy Toshkent oyi, jami — hamma vaqt), Moliya "Brak"
qatori (`services.get_monthly_report`) va brak tahlili (`services.get_brak_tahlil`) — shu BITTA funksiya. Tahlilda
yozuv qiymati — unga bog'langan harakatlar (`crud.brak_yozuv_qiymatlari`), ishlab chiqarish braki — `cost_amount`,
Moliyadan farq — `boglanmagan_qiymat`; omborda tayyor turgan yo'qotish brak EMAS (taqsimotga kirmaydi,
`tayyor_yoqotish_qiymati`). Yozuvdagi saqlangan summa (`refund_amount`) hisobot uchun ishlatilmaydi va tegilmaydi.

**Server rad sababi (UI, kech107, 10d).** Server 400 / 404 / 409 / 422 da sababni `detail` da beradi (matn, obyekt
`{message}` / `{error}`, pydantic ro'yxati). Sahifada rad javobi FAQAT `templates/base.html` dagi `xatoSababi(javob,
standart)` / `serverXatoSababi(res, standart)` bilan o'qiladi ("Xato yuz berdi", `r.detail?.message`, "[object
Object]" — YO'Q); forma maydonlari `Optional[str] = Form(None)` + o'z tekshiruvi (bo'sh maydon 422 ro'yxati emas, 400 matn).

**Kirim hujjatini bekor qilish (kech107, 10f).** `crud.kirim_hujjatini_bekor_qilish` — reja (`faqat_hisob=True`,
`GET /api/inventory/receipts/{id}/cancel-plan`) va amal (`POST …/cancel?tolov=ochirish|avans`, bitta tranzaksiya)
BITTA funksiya: har xarid qaytadi (qoldiq — arifmetik, o'rtacha narx — `crud._xarid_narxini_qaytar`: narx hali
`narx_keyin` ga teng bo'lsa `narx_oldin` ga; oxirgi qatordan boshlab), hujjatning Moliyadagi qo'shimcha xarajatlari
o'chadi, «hozir to'langan» to'lov — egasi tanlovi (tanlovsiz 409 `receipt_has_payment`, hech narsa o'zgarmaydi).
Yakka xaridni o'chirish ham narxni shu qoida bilan qaytaradi.

**Loyiha tahriri (kech107, 10a).** Tahrirda muddat o'zgaradi / olib tashlanadi; ixtiyoriy maydon `null` — tozalanadi
(`crud.LOYIHA_TOZALANADIGAN`: telefon, manzil, tavsif, izoh (Telegram ID), muddat), `total_budget: null` — 0.

**Kam qolgan xomashyo — YAGONA qoida (kech108, K108-2 — egasi qarori "Ha, ko'rinsin").** `crud.kam_qoldiq_sharti()` /
`crud.kam_qoldiqmi(item)`: yashirilmagan, "Tayyor loy (" bilan boshlanmaydigan, COALESCE(qoldiq, 0) ≤ COALESCE(min, 0) —
minimal qoldig'i belgilanmagan material TUGASA (qoldiq ≤ 0) ham "kam". Bosh sahifa / dashboard / buyurtmalar ogohlantirishi /
bugungi vazifalar / grafik (`services.check_low_stock`), hisobotlar (`get_business_alerts`), Telegram ogohlantirishlari
(`crud.get_low_stock_items`), «Ombor hisoboti», Omborxona KPI — hammasi shu qoida; matnda qoldiq ≤ 0 — "tugagan" / "tugadi".
Brauzer: bosh sahifa `kamQoldiqHtml` (min 0 — chiziq 0 %), Omborxona qatori (min 0, tugagan — 0 %), hisobotlar `stockDot`.

**Buyurtma tahriri (kech108).** Tahrir banneri (`#editBanner`) mazmuni hech qachon ustidan yozilmaydi: topshirish
ogohlantirishi — `#editBannerTopshirish` bolasida (`_tahrirBanneriTopshirish`), `showNewForm` tiklaydi (`_tahrirBanneriTikla`)
— K108-3. Saqlangan narxi > 0 detal saqlashda 0 ga tushsa — umumiy tasdiqdan OLDIN ogohlantirish («Bekor» — PUT yo'q;
`row.dataset.saqlanganNarx`, `collectItems` → sanalmaydigan `_qator`, `_narxiNolgaTushgan`) — 71-band.

**MRP bandi va ishlab chiqarish bog'lamlari — korxona chegarasi (kech109, 10b E-1).** Qo'riqchi (`models._TENANT_REFS`)
`FinishedProduct.reserved_for_order_item_id` va `ProductionOrder` manbalarini (buyurtma, detal, tayyor mahsulot, mahsulot turi,
retsept) ham tekshiradi — begona korxona yozuviga bog'lash rad (409). Eski ma'lumotda begona korxona mahsuloti detalga band bo'lsa:
`crud._auto_release_mrp_reservations` detal korxonasining O'Z mahsulotlarini ozod qiladi (+ jurnal), BEGONA mahsulotda faqat FK
bog'lamini uzadi (band miqdori va egasining jurnali o'zgarmaydi — egasi «Tayyor mahsulotlar» da o'zi ozod qiladi);
`production_service.mrp_detal_kerak` — band faqat detal korxonasidan; korxonani tozalash begona ishoralarni uzadi (FK).

**Buyurtma tahriri — ishlab chiqarishga bog'langan detal (kech109, K109-2).** Tahrirda detallar NOM + TUR bo'yicha moslanadi:
olib tashlangan yoki NOMI o'zgargan detal o'chiriladi. Unga FAOL ishlab chiqarish bog'lami bo'lsa (band tayyor mahsulot yoki
qoralama / jarayondagi ishlab chiqarish buyurtmasi) — 400, sabab ro'yxati (`crud._mrp_faol_boglamlar`: "«nom» — 3 m² tayyor
mahsulot band; ishlab chiqarish buyurtmasi #7 (qoralama)"), hech narsa o'zgarmaydi (ilgari PG da 500). Faol bo'lmagan (tarixiy)
bog'lam — `delete_order_item` naqshi bilan uziladi. Tahrirda «📝 Vaqtincha saqlash» tugmasi yashiriladi (`#draftSaveBtn`,
K109-1 — ilgari `.btn-outline` birinchisi «✕ Yopish» topilib, tugma ko'rinib qolardi; bosilsa haqiqiy saqlash bo'lardi).

**`main` ko'chirishi — bitta yuklash (kech109, K108-1).** `main.py` modul darajasida, `init_database()` dan OLDIN
`saas_otish.startup_otish(engine)`: PostgreSQL, `users` jadvali bor va to'lqin jadvallaridan birida `company_id` yo'q — eski
baza. Shunda: (1) SINOV — `companies` (id=1) + W1 … W6 (W2B, W3B ichida) + `verify_tables` + M1KOD BITTA tranzaksiyada (har
qadam savepoint), oxirida HAMMASI qaytariladi; biror qadam to'xtasa (NULL, yetim, takror, qulf) — baza O'ZGARMAYDI; (2) HAQIQIY —
xuddi shu, har qadam o'z tranzaksiyasida (`saas_migration.run_step`); (3) xato — `RuntimeError`, ilova ATAYLAB ishga
tushmaydi (Railway logida qadam va sabab); qayta ishga tushish davom ettiradi (qadamlar idempotent, eski kod qisman o'tgan
baza bilan ishlaydi — vaqtinchalik DEFAULT 1). Yangi / staging baza — hech narsa qilinmaydi. `saas_migration.py` (3.12
sintaksisi) faqat eski bazada yuklanadi. Korxonalar id ketma-ketligi har ishga tushishda MAX(id) ga tenglashtiriladi
(`_seed_default_company`, K109-3 — ilgari id=1 aniq yozilgani uchun platformadan BIRINCHI "korxona qo'shish" 400 berardi).

**Kelishilgan summa — jami o'zgarganda YAGONA qoida (kech110, K110-1; egasi QARORLARI — ustama "Foizi saqlansin",
kechirilgan qarz "Kechirilgan so'mda qolsin").** `crud.kelishilgan_qayta_hisob(eski jami, yangi jami, eski ASL, kechirilgan)` —
to'liq tahrir (`crud.update_order_full`, summa QO'LDA yozilmagan bo'lsa), detal tahriri / o'chirish (`crud._detal_ozgargach_buyurtma`),
qisman «Tayyor» / o'chirishda yakunlash (`crud.finalize_partial_order_quantities`); brauzerdagi AYNAN nusxasi — `orders.html`
`kelishilganQayta` (paritet testi). Narx kelishuvi P = ASL kelishilgan + kechirilgan qarz: jami o'zgarmasa — o'zgarmaydi;
chegirmasiz — yangi jamiga teng (tiyinigacha); chegirma / ustama — NISBAT saqlanadi (butun so'mga HALF_UP); to'lovda
kechirilgan qarz (`Order.kechirilgan_qarz`, `main._tolov_qoldigini_chegirmaga` qo'shib boradi) — SO'MDA ayiriladi. Hisob
butun tiyinlarda (Python int / brauzerda BigInt) — float `yangi × P / eski` .5 chegarasida 1 so'mga adashardi.
`discount_percent` — faqat NARX chegirmasi (`crud._narx_chegirma_foizi`; kechirilgan qarz kirmaydi). Tahrir formasi summani
FAQAT xodim uni qo'lda yozganda yuboradi (`editUserTouched`) — aks holda server qoidasi hal qiladi (ilgari eski summa har doim
ketib, "qo'lda kiritilgan" deb olinardi: chegirmasiz 400 000 → jami 300 000, kelishilgan 400 000). Eski buyurtmalarning
kechirilgan summasi izohdagi `[WRITEOFF:N]` belgisidan bir marta to'ldiriladi (`main._migrate_kechirilgan_qarz`).

**MRP amallari Faoliyat jurnalida (kech110, 5.2d 2c).** Mahsulot turi va retsept (yaratish / o'zgartirish — eski → yangi /
nofaol qilish), ishlab chiqarish buyurtmasi (yaratildi / jarayonga olindi / ishlab chiqarildi / bekor qilindi — `production_service._po_jurnal`)
va «manfiy qoldiq bilan ishlab chiqarish» sozlamasi `/logs` «Audit jurnali» ga yoziladi — `crud.log_activity(commit=False)`:
yozuv amal bilan BITTA tranzaksiyada (rad etilgan / yiqilgan amal — yozuv yo'q), korxona — amal korxonasi.

**Kirim hujjati — sana, to'lov muddati, takror qator (kech115, A bosqich G4-01 / G4-02 / G4-03).** `crud.kirim_sanalari` —
kirim sanasi Toshkent kalendari bo'yicha: bugun / bo'sh — hozirgi vaqt; o'tgan kun — o'sha kunning 00:00 i (hujjat, xaridlar
`purchased_at`, qo'shimcha xarajatlar, «hozir to'langan» to'lov shu kunga; ombor harakati jurnali — kiritilgan vaqtda qoladi);
kelajak va `KIRIM_SANA_ORQAGA_KUN` (366) dan eski — rad; to'lov muddati kirim sanasidan oldin — rad, faqat nasiya qatoriga
yoziladi (dashboard ogohlantirishi `get_supplier_payment_due_dates`). `crud.kirim_takror_qator` — AYNAN bir xil qator (material,
miqdor, tiyinga yaxlitlangan narx, hajm, boshlang'ich belgisi) — rad (bir materialni boshqa narx / miqdorda — ruxsat, ikki
partiya). Sahifa (`supplier_receive.html`): hamma tekshiruv (ta'minotchi, yo'nalish, sana) — yozib qo'yilgan qatorni savatga
qo'shishdan OLDIN; qator faqat `apQatorniSavatga` orqali (maydonlar tozalanadi, takror rad); chala qator — to'xtaydi; sana
bugun emas — tasdiq; saqlangach «boshlang'ich ombor» belgisi, hujjat raqami, sana tozalanadi, material ro'yxati qayta yuklanadi
(K115-1); belgi turganda xulosa: to'langan / qarz 0 + ogohlantirish.

**Mijoz to'lovi — tasdiq va kechirish (kech115, G3-01 / G3-02).** Qarzdorlar: summa o'zi yozilmaydi («Butun qarz» tugmasi);
HAR saqlashdan oldin tasdiq (mijoz · buyurtma: summa); «Qolgan qarzni chegirma qilib yopish» belgisida kechiriladigan summa
jonli ko'rinadi (`payKechiriladi` — butun tiyinlarda, 0.5 so'mdan kichigi qarz emas), tasdiqda alohida (danger), natija
xabarida serverning `write_off.amount`. Buyurtmalar to'lov oynasida ham belgi bilan qarz qolsa — kechiriladigan summa
tasdiqda. Server qoidasi o'zgarmagan (`main._tolov_qoldigini_chegirmaga` — chegarasiz; chegara kerak bo'lsa — egasi qarori).

**«Tayyor» oynasi va sahifa xabarlari (kech115, G2-03 / G2-07).** «Tayyor» oynasi faqat MUVAFFAQIYATDA yopiladi; rad — oynada
(`#readyModalXato`) va xabarda (`xatoSababi`), kutishda tugma o'chiq; to'lovni o'chirish rad etilsa — sabab. Yangi buyurtma
(va tahrirda YANGI qo'shilgan qator) narxsiz (0) bo'lsa — tasdiq (`_narxsizDetallar` / `_narxsizTasdiq`; server 0 narxni
qabul qiladi — tekin namuna mumkin).

**Ko'rinish qoidalari (kech115, G3-10 / G1-04 / G1-01 / G1-06 / G4-06 / G6-01).** Qisqa summa — `base.html` `qisqaSumma`
(chegara modul bo'yicha, ishora saqlanadi; Moliya va Dashboard `fmt`); Moliya «Pul oqimi» ishorasi bilan, manfiy rentabellik
qizil. Taqqoslash (`services.get_monthly_comparison`): o'tgan oy 0 — `change_pct: None`, `holat` («malumot_yoq» /
«ozgarmadi» / «oshdi» / «kamaydi»); sahifada BITTA ko'rinish qoidasi `ozgarishKorinishi` (xarajat o'sishi — qizil), zarar oyi —
«Bu oy zarar». Korxona sog'ligi (`services.get_business_health`): ombor — kam / tugagan soni (`kam_qoldiq_sharti`), ishlab
chiqarish — muddati o'tgan faol buyurtmalar (0 / 1–2 / 3+), ma'lumot yo'q — «gray», har baho `sabablar` bilan (kech116,
K115-2: rentabellik va qarz sababi holatga qarab — «yaxshi / o'rtacha / past (yuqori)» chegarasi bilan; baho ko'rsatilgan,
1 xonagacha yaxlitlangan foizdan). «Bugungi xulosa» — ogohlantirish bo'lmasa ham yig'iladi (K115-3). Omborxona
holat filtri — belgilar bilan bir xil (`data-holat`: yetarli / oz / kam / tugagan; «Kam qolganlar» = kam + tugagan = karta
soni, karta bosilsa filtrlanadi). O'chirilganlar jurnali — faqat `crud.CHIQINDI_JURNAL_AMALLARI` (o'chirildi / tiklandi /
butunlay o'chirildi), boshqa amallar — «Tizim jurnallari».

**Buyurtma pul hisobi qatorlari (kech116, G2-04).** `crud.buyurtma_hisob_qatorlari` — YAGONA qatorlar: Buyurtma jami −
Chegirma (narx kelishuvi; kelishilgan jamidan katta bo'lsa — «Ustama») − Qaytarish (pul qaytarish kamaytirishi,
`pul_qaytarish_kamaytirgan`) − Kechirilgan qarz (`Order.kechirilgan_qarz`) = Kelishilgan summa; Kelishilgan − To'langan (sof) =
QARZ QOLDI (yoki ORTIQCHA TO'LANGAN). `korinish` — butun so'mlar (HALF_UP; chegirma / qarz — AYIRMA), shuning uchun hujjatdagi
qatorlar tiyinli summalarda ham qo'shiladi. Uchala mijoz hujjati (yuk xati, hisob-kitob varaqasi — `delivery_pdf._hisob_qatorlari`;
buyurtma nakladnoyi — `pdf_service`) va buyurtma oynasi (`/api/orders/{id}` → `hisob`, `orders.html` `loadPayments`) shundan.
Hisob-kitob varaqasidagi «Berilgan mahsulot» pul hisobi orasidan olindi (jadvaldagi «JAMI BERILGAN MAHSULOT» qatori qoldi).
Kech40 dan oldingi (kamaytirishi yozilmagan) qaytarish ajratilmaydi — chegirmada qoladi. MIJOZ hujjatlarida
(`mijoz_hujjati=True` — uchala PDF; egasi QARORI kech116) kechirilgan qarz alohida qator emas: «Chegirma» qatoriga qo'shiladi
(narx chegirmasi + kechirilgan, FOIZSIZ; narx chegirmasi yo'q / ustama bo'lsa — kechirilgan summa o'zi «Chegirma»); kechirilgan
qarz yo'q bo'lsa — «Chegirma (x %)» avvalgidek. Buyurtma oynasi (`/api/orders/{id}` → `hisob`) — kechirilgan qarz alohida.

**Pul oqimi va kassa (kech116, G1-03 — egasi QARORI kech114 «Pul oqimi — haqiqiy pul»).** `services._kassa_qismlari` — kassa
harakati qismlari (YAGONA manba, davr bilan): mijoz to'lovlari `paid_at` (qaytarilgan pul — manfiy to'lov), tayyor mahsulot
sotuvi `sold_at`, naqd xarid `purchased_at` (nasiya va boshlang'ich ombor — YO'Q; nasiya to'lanishi — ta'minotchiga to'lov),
ta'minotchiga to'lov, xarajatlar, kirish transporti, yetkazishning korxona ulushi `delivered_at`, hodimga avans / oylik
(`EmployeeAdvance`), kassaga qo'lda yozuv (boshlang'ich balans — harakat EMAS). Eski oylik shakl — oyning 1-kuniga.
`get_cash_balance` — butun davr (natija o'zgarmadi); `get_pul_oqimi(year, month | sana)` / `_pul_oqimi_oraliq` — davr,
`/api/finance/pul-oqimi` (`sana=` — Toshkent kuni; parametrsiz — joriy oy; noto'g'ri — 400). Butun davr oqimi + boshlang'ich =
kassa; oy = kunlar yig'indisi. Hisobotlar (karta, blok), Moliya (bugungi karta), Dashboard («Pul oqimi (bu oy)») va «Korxona
sog'ligi» (yashil — kirim ≥ chiqim; sariq — chiqim ko'p, kassada pul bor; qizil — kassa ham manfiy; kulrang — harakat yo'q) shundan.

**Xarajat — bitta ta'rif (kech116, G1-02).** «Xarajat» = `jami_xarajat` (sof foydadan ayriladigan; tannarx ALOHIDA) hamma
sahifada. `get_monthly_report` → `xarajat_tarkibi` (8 guruh: doimiy, qo'shimcha, transport, brak, TM yo'qotishi, usta KPI,
ehson, hodimlar — yig'indisi = `jami_xarajat`), `tannarx_jami` (buyurtmalar + TM sotuvi tannarxi), `fp_sales_tannarx`:
daromad − tannarx_jami − jami_xarajat = sof foyda. Hisobotlar — 8 karta (Daromad, Tannarx, Xarajat, Sof foyda / Pul oqimi,
Kassa, Buyurtmalar, Rentabellik) va tenglama qatori, «Xarajat tarkibi» doirasi — to'liq tarkib; Dashboard «Bu oy moliyaviy
holat» — Tannarx qatori alohida, qatorlar = tarkib, «Jami xarajat» = `jami_xarajat`.

**Loyiha qiymati (kech116, G2-01 — egasi QARORI kech114 «Loyiha qiymati — buyurtmalardan»).** `crud.loyiha_pul_hisobi` —
qiymat = buyurtmalar kelishilgan summalari, to'langan = ularning to'lovlari, qarz = ularning `debt_amount` i (Qarzdorlar
sharti `qarz_hisobidagi_buyurtma_sharti`; qoralama va bekor qilingan — KIRMAYDI). `get_projects_with_stats` → `p.pul`;
Loyihalar sahifasi (karta foizi, «Loyiha qiymati / To'langan / Qolgan to'lov», holat paneli, «Moliya» yorlig'i) shundan.
«Byudjet» maydoni formalardan olindi (`total_budget` ustuni bazada qoladi, saqlash tanasida yuborilmaydi).

**Haqiqiy IP va kirish cheklovi (kech116, U-01).** `auth.mijoz_ip`: ulanish manzili ichki (xususiy / CGNAT 100.64/10 /
loopback / link-local — Railway proksisi) bo'lsa — `X-Forwarded-For` dagi ENG O'NG ochiq manzil (mijoz yozgan soxta
qiymatlar undan chapda qoladi), bo'lmasa `X-Real-IP`, aks holda ulanish manzili; ulanish ochiq bo'lsa — sarlavhalarga
ISHONILMAYDI. (`uvicorn --forwarded-allow-ips='*'` ISHLATILMAYDI — 0.30.6 da XFF ning eng CHAP manzilini oladi.) Admin va hodim
kirishi shundan. `crud.check_login_rate_limit`: 15 daqiqada foydalanuvchi nomi bo'yicha 5, IP bo'yicha 20 xato (bitta ofis
NAT i ortidagi xodimlar bir-birini bloklamasin).

**Parol va kirishlar (kech116, G6-06).** Parol — `users.html` dastur oynasi (`#parolModal`: yashirin maydonlar, ko'zcha, yangi
+ takror bitta oynada, o'z parolida joriy parol; server rad sababi oynada). `auth.change_password(…, saqlanadigan_token)` —
parol bilan BITTA tranzaksiyada shu foydalanuvchining HAMMA sessiyalari o'chiriladi, faqat o'z parolini almashtirganning
joriy sessiyasi qoladi. Hodim PIN i (`crud.set_employee_login`) — hodimning hamma panel sessiyalari o'chiriladi.

**Dasturning o'z oynalari va yopish (kech118, B bosqichi — audit U-07 / U-08).** Brauzerning xom oynalari ISHLATILMAYDI:
xabar — `base.html` `xabarOyna(matn, {sarlavha, tur, okText})` (Promise; navbat bilan; tur — matn boshidagi ❌ / ✅ / ⚠ dan),
brauzerning native `alert` i `_xoAlertniUlash(window)` bilan shu oynaga yo'naltiriladi (eski `alert(...)` chaqiriqlari o'zgarmagan;
test / boshqa kod oldindan o'rnatgan almashtirishga tegilmaydi — faqat `[native code]`); kiritish — `kiritishOyna(sarlavha, {izoh,
qiymat, tur, okText, inputmode, tekshir})` (Promise: matn / `null`); tasdiq — `customConfirm`. Xom `prompt()` / `confirm()` —
YO'Q (`tools/test_b118_oyna.py` S1). MUHIM: dastur oynasi sahifani to'xtatmaydi — xabardan KEYIN sahifa yangilanadigan /
boshqa joyga o'tiladigan joyda `await xabarOyna(...)`. Yopish: Esc — eng ustki ochiq oynaning `data-yopish` tugmasi (oyna =
belgining eng yaqin `position: fixed` ajdodi; eng ustkisi — z-index, teng bo'lsa hujjatda keyingisi); oynaning tashqarisiga
(qora fonga) bosish — xuddi shunday; oynaga ma'lumot yozilgan bo'lsa (input / change) ikkalasi ham avval so'raydi («Oynaga
yozilgan ma'lumot saqlanmaydi. Oyna yopilsinmi?» — «Yopish» / «Davom etish»). `data-yopish-ichki` — oyna ichidagi ochiluvchi
panel (Esc avval uni yopadi); `data-esc-ozi` — o'z Esc ishlovchisi bor, yopish belgisiz oyna (platforma) — «ochiq oynalar»da
qatnashadi: u ustida turganda global Esc ostidagi oynaga tegmaydi. Yopish tugmasi FAQAT belgi bilan topiladi (matn
bo'yicha taxmin YO'Q: «Bekor qilish» / «✕» ba'zi joyda AMAL — ishlab chiqarishni bekor qilish `doCancel`, TM o'chirish `delFp`).
YANGI oyna qo'shilsa — yopish tugmasiga `data-yopish` (S3 / S4 statik darvozasi har qoplamani tekshiradi).
**Yo'q va ruxsatsiz sahifa (kech118, U-11).** `main.custom_http_exception_handler`: 404 / 403 da, brauzer SAHIFA so'rasa (GET /
HEAD, `Accept` da text/html, yo'l `/api/` yoki `/static/` emas) — `templates/xato_sahifa.html` («Bunday sahifa yo'q» / «Bu
bo'limga ruxsatingiz yo'q», «Bosh sahifaga», hodim yo'lida — `/hodim`), holat kodi saqlanadi. API va boshqa mijozlar — JSON
AYNAN avvalgidek. Rol nomlari foydalanuvchiga o'zbekcha — `auth.ROL_NOMI` / `auth.rollar_matni` (rad sababi: «Bu bo'lim faqat
Admin va Hodim uchun ochiq»). Klaviatura fokusi — `static/style.css` `:focus-visible` (hamma bosiladigan / yoziladigan element,
inline `outline:none` ustidan); `style.css` havolalari `?v={{ static_version }}` bilan (kesh).
**Son, sana, birlik ko'rinishi va o'qiladigan yozuv (kech118, B bosqichi 2-qism — audit U-03 / U-04 / U-05 / U-06).** Ekranga
chiqadigan son — bitta qoida: ming ajratgich bo'sh joy (NBSP), kasr — VERGUL, ortiqcha nolsiz («354», «8,3», «1 234,5»), «-0» →
«0», qiymat yo'q — «—». Brauzerda `base.html` `sonKor(x, kasr = 2)`, foiz — `foizKor(x, kasr = 1)` («33,3%»); shablonda Jinja
`|son(k)` (`main._son_filtri`); server yozadigan matnda (ogohlantirish, sabab) — `services._son_uz` (`:g` + vergul, «5,01 %»).
`qisqaSumma` — «1,6 mln». Kiritish maydonining QIYMATI (`input.value`, `editMinStock` standarti) — nuqta, avvalgidek (`parseNum`
ikkalasini oladi). Sana / vaqt — tk yordamchilari standart ('uz' / til berilmagan) ko'rinishni QO'LDA yozadi, brauzer tiliga
bog'liq emas: «01.10.2026», «01:30», «01.10.2026 01:30», «01.10.2026, 01:30:00», oy nomi bilan «1-oktabr, 2026»; boshqa til
('ru-RU') — brauzerning o'zi. Grafik oy yorlig'i — `services._OY_QISQA` («Okt 2026»). Birlik — `birlikKor` (m2 → m², m3 → m³).
Yozuv rangi oq / och fonda ≥ 4.5:1: `--text2` #5B6170, `--text3` #696D78, `--gold-dark` #8F5B2A (oltin rangdagi YOZUV — `--gold-dark`,
`--gold` — fon / chiziq / qorong'i fondagi yozuv); OQ yozuvli oltin tugma / belgi foni — `--gold-btn` #9A6231 (`--gold` bilan 3.6:1
edi); sahifa to'plamlari (Moliya `--f-*`, Kirim `--r-*`, Hisobotlar `--b-*`, Qarzdorlar `--d-*`) `--*-primary` — #9A6231 (matn ham,
tugma foni ham). Holat ranglari (#22C55E, #16A34A, #F59E0B, #EF4444, #0EA5E9, #94A3B8 …) chiziq / nuqta / fon uchun qoladi, YOZUVGA —
`matnRangi(c)` to'q tusi (#15803D, #B45309, #DC2626, #0369A1, #696D78 …); yozuv och RANGLI fonda (#FEF2F2, #F0FDF4, `${rang}22` …) —
`matnRangi(c, 1)` (#166534, #B91C1C, #92400E, #075985 …). O'zgaruvchidan keladigan yozuv rangi (`color:${rang}`) — doim
`matnRangi(...)` orqali; qorong'i kartada (Moliya «Kassa balansi» — gradient) och yozuv. Eng kichik yozuv — 12 px (style.css va
shablonlar; `tools/test_b118_korinish.py` S statik darvozasi). Xom kalit ekranga chiqmaydi (moliya: `transport_kirim` →
«Transport (kirim)» va h.k. — `CAT_LABELS`). YANGI sahifa kodida: son — `sonKor` / `|son`, rangli yozuv — to'q tus. `style.css`
o'zgarsa — `main.py` `static_version` ham yangilanadi (aks holda brauzer eski uslubni keshdan oladi; kech118 — «20260930-2»).
**Yo'nalishlar bo'yicha moliya (kech117, A2 — egasi QARORLARI kech114 00:08; G3-11, G6-09).** Jadval `yonalishlar`
(`models.Yonalish`: `company_id`, `nom` ≤ 60, `kod` — asosiysida 'penoplast', `yashirin`, `tartib`; `uq_yonalishlar_company_kod`).
Har korxonada ASOSIY yo'nalish («Penoplast», `crud.standart_yonalish` — yo'q bo'lsa yaratadi; yangi korxonada — platformadan
yaratilganda): o'chirilmaydi, yashirilmaydi, nomi o'zgaradi. Sozlamalar (Tizim jurnallari → Sozlamalar): qo'shish, nomini
o'zgartirish (ko'rinadiganlar orasida takror nom — rad, harf katta / kichikligi farqsiz), yashirish / ko'rsatish, faqat
ISHLATILMAGANINI o'chirish (`crud.yonalish_ishlatilishi` — hodim, xarajat, transport, kirim, MRP turi; o'chirilganlari ham).
`yonalish_id` (NULL — «Umumiy») ustunlari: `employees`, `expense_transactions`, `transport_expenses`, `inventory_receipts`,
`product_types` (NULL — «Belgilanmagan»). Yozish — `crud.yonalish_tanlovi`: `yonalish_id` yuborilsa — o'z korxonasining
KO'RINADIGAN (yoki yozuvning joriy) yo'nalishi, aks holda 400 («topilmadi» / «yashirilgan — avval Sozlamalarda ko'rsating»);
eski mijoz `production_type='penoplast'` → asosiy yo'nalish. Kirim hujjati yo'nalishi — uning xarajat yozuvlariga ham.
MRP turi yo'nalishi UIda MAJBURIY (`PATCH /api/production/product-types/{id}` — biriktirish; o'tgan oylar ham yangi
yo'nalishda ko'rinadi, umumiy sof foyda o'zgarmaydi). Migratsiya `_migrate_yonalishlar` (IDEMPOTENT): har korxonaga asosiy,
eski 'penoplast' → asosiy, 'umumiy' / NULL / 'gips' → «Umumiy» (gips — `main` da 0 yozuv, O'LCHANGAN).
Hisob — `services.calculate_split_profit_report` (manba — `get_monthly_report` ning `sof_foyda_tarkibi`, ya'ni sof foydaning
AYNAN qismlari): daromad va tannarx — detal bo'yicha aniq (`services._YonXarita`: profil, karniz, panel, dona, blok, loy sotish
— asosiy; MRP — turining yo'nalishi; turi yo'q / eskirgan turkum (gips, termopanel) / mahsuloti o'chirilgan TM sotuvi —
«Belgilanmagan», avtomatik Penoplast EMAS); qaytarish — detalining yo'nalishiga; brak va TM yo'qotishi — detal / mahsulot
bo'yicha; yo'nalishi tanlangan hodim (hisobotdagi AYNAN summa) — OYLIK, xarajat (KIRIM_TANNARX_MANBA — tannarxda, qayta
emas), transport — 100% o'ziga. **kech118 (egasi QARORI 15:23 — kech114 «daromad ulushida» BEKOR):** qolgan hamma xarajat
(arenda, svet, soliq, tushlik, Ehson, usta KPI, transport, «Boshqa», yo'nalishsiz hodimlar) TAQSIMLANMAYDI — faqat «Jami»
ustunida (`umumiy_oylik`, `umumiy_xarajat`, `umumiy_qismlari`). Ustun: `daromad`, `tannarx`, `oylik`, `xarajat`
(`xarajat_qismlari`), `natija` = D − T − O − X; Jami: `oylik` / `xarajat` = ustunlar + umumiy, `natija` = Moliya sof foydasi
(`yonalishlar_natijasi` − umumiy). Moslik maydonlari: `bevosita` = O + X, `bevosita_qismlari`, `sof_foyda` = natija. Butun so'm
(`som`, `jami`) va tiyin (`aniq`, `jami_aniq`) — eng katta qoldiq usuli (`_yaxlit_taqsim`): ustun ichida D − T − O − X = N,
ΣN − umumiy = Moliya sof foydasi (AYNAN). Qoldiq (< 1 tiyin) — eng kattasiga; haqiqiy farq — «Belgilanmagan» ga izoh bilan.
Davr — OY bo'yicha (`services.yonalish_davr_oylari`: `year-month` … `gacha_yil-gacha_oy`, ko'pi bilan 36 oy; har oy — oylik
hisobotdan, yig'iladi); `solishtirish` — oldingi davr (`yonalish_oldingi_davr`: yanvardan boshlangan davr — o'tgan yilning
shu oylari, qolgani — oldingi teng davr) `oldingi` / `ozgarish` (foiz); `tarkib` — xarajatlar tarkibi (tannarxsiz, oylik +
har xarajat turi, foizi bilan); `rentabellik`, `foydada_soni` / `zararda_soni`, `davr.nom` («Iyul – Sentabr 2026»).
`GET /api/finance/yonalishlar?year&month[&gacha_yil&gacha_oy]` (noto'g'ri davr — 400 o'zbekcha), PDF
`/api/finance/split-profit-pdf` (shu davr; fayl `yonalishlar_hisobot_YYYY_MM[_YYYY_MM].pdf`). Sahifalar: Moliya — «Yo'nalishlar
bo'yicha moliyaviy natija» bo'limi (bitta yo'nalish bo'lsa yashirin): davr tanlovi (tanlangan oy / chorak boshidan / yil
boshidan / oraliq), 4 karta (daromad, xarajatlar tannarx bilan, natija + rentabellik, yo'nalishlar soni — foydada / zararda;
oldingi davr bilan o'zgarish), jadval (1 Daromad, 2 Tannarx, 3 Oyliklar + yo'nalishsiz, 4 Xarajatlar + turlari + umumiy,
Natija +/−, Rentabellik; birinchi ustun telefonda joyida), tekshiruv qatori, xarajatlar tarkibi doirasi, rentabellik
chiziqlari, izoh; daromad doirasi yo'nalishlar bo'yicha, «Tannarx» kartasi; Dashboard /
Hisobotlar grafiklari (`today_yonalishlar`, `months[].yonalishlar`, `yonalishlar_daromadi`) — bitta yo'nalishda yashirin;
yashirilgan yo'nalishli yozuvni tahrirlashda vaqtincha «(yashirin)» varianti (yo'nalish yo'qolmaydi). «Belgilanmagan»
ustuni sababi — `belgilanmagan_turlar` (yo'nalishi biriktirilmagan MRP turlari) va `belgilanmagan_manbalar` (qolgan manbalar
nomi va summasi: eski turkumli detal, turi tanlanmagan MRP detali, detalsiz buyurtma, turi / asosiy turkumi yo'q yoki
mahsuloti o'chirilgan TM sotuvi; ko'pi bilan 10 ta) — Moliya ogohlantirishida va PDF da (kech117, zip 115 jonli sinovi:
sinovda 140 000 so'm sababsiz edi). Moliyada xarajat qo'shilsa / tahrirlansa / o'chirilsa — hisobot, kartalar va
yo'nalishlar jadvali darhol yangilanadi (`loadReport({txSaqla: true})` — kunlik ro'yxat sanasi joyida). Oylik moliya PDF i
(G6-09): «Daromad tarkibi», «Tayyor mahsulot sotuvi tannarxi» qatori, qatorlar butun so'mda yig'indiga teng, ishora bitta
ko'rinishda («−N»). Eski «Gips vs Penoplast» (`turlar_boyicha`, `today_gips_revenue`, `gips_revenue`) — YO'Q.

**Platforma — obuna va bloklash (kech111; egasi QARORLARI kech109 / kech110 / kech111, 6-bo'lim).** Hisob — `obuna.py`
(YAGONA manba); `companies` ustunlari (hammasi NULL, `default=` siz): `bloklangan_at`, `blok_sabab`, `blok_izoh`, `bloklagan`,
`blok_avtomatik`, `obuna_boshi`, `obuna_tugash` (Date — OXIRGI to'langan kun; NULL — muddatsiz), `obuna_turi` ('sinov' / 'obuna'),
`imtiyoz_gacha`, `eslatma_holati`. "Bugun" — Toshkent kuni (`obuna.bugun()` — testlar almashtiradi). Muddat E: E−7 … E —
"yaqin" (sariq); E+1 … E+3 — imtiyoz ("otgan", kirish OCHIQ); E+4 dan — AVTOMATIK yopiq (`obuna.holat`). Bloklash
(`obuna.blokla`): kirish (`auth.get_current_user` — HAR so'rovda, `auth._korxona_bloklanganmi`; sahifa → `/login?b=1|2`, API → 403
sababi bilan, belgi `obuna.BLOK_SARLAVHA`, `main.custom_http_exception_handler`), login (to'g'ri parolda xabar, urinish
"noto'g'ri" deb yozilmaydi), hodim paneli (`auth.get_current_employee`, `hodim_login_submit`), usta boti
(`main._master_by_chat_id`), kunlik "kam qoldi" Telegram (`/api/cron/low-stock-check`) — yopiladi; ochiq sessiyalar
bloklash paytida O'CHIRILMAYDI (`obuna.ochiq_sessiyalar` — faqat soni): keyingi so'rovda tekshiruv sessiyani o'chiradi va SABABNI
ko'rsatadi (K112-2: oldin darhol o'chirilardi — ochiq oynadagi xodim sababsiz oddiy kirish sahifasiga tushardi); ma'lumot O'CHMAYDI. Platforma admini hech qachon bloklanmaydi; platforma egasi korxonasi (platforma admini bor
korxona) bloklanmaydi, muddati yo'q (API 400; kunlik ish o'tkazadi). «Ochish» (`obuna.och`) — muddat imtiyozdan ham o'tgan bo'lsa
`imtiyoz_gacha` = bugun + 3 (3 kunlik imtiyoz). Uzaytirish (`obuna.uzaytirish_sanasi` / `obuna.uzaytir`, +1 / 3 / 6 / 12 oy yoki
aniq sana) — «Aralash»: E ≥ bugun — E dan, aks holda bugundan; sinov tugaydi, imtiyoz / eslatma belgisi tozalanadi, AVTOMATIK
blok ochiladi (qo'lda blok — «Ochish» bilan). Yangi korxona — 30 kunlik sinov (`obuna.sinov_ber`, `api_platform_create_company`).
Kunlik ish (`main.obuna_kunlik_ish`, rejalashtiruvchi 09:05 Toshkent) — imtiyozdan o'tganni BAZADA bloklaydi va egasiga Telegram
(`_send_telegram`, korxonasiz — platforma chati): 7 kun / 1 kun qolganda, muddat tugaganda, avtomatik bloklanganda — har bosqich
shu muddat uchun BIR marta (`eslatma_holati` = "<E>:<bosqich>"). Mijoz ogohlantirishi (`obuna.banner`, Jinja `obuna_banneri`) —
YUQORI PANELDA (sahifa joyini egallamaydi): ≤ 7 kun — faqat korxona ADMINIGA sariq; imtiyozda — HAMMAGA qizil; bosilsa to'liq
matn va aloqa telefoni (tashqariga bosilsa yopiladi). Yuqori paneldagi ochiluvchi panellar (obuna, bildirishnomalar) ochilganda
`base.html` `panelniJoyla` bilan EKRAN ICHIGA joylanadi (K112-1: tor ekranda tugmalar qatori chapga o'tib, `right: 0` li 340 px
panel ekrandan chapga chiqib ketardi — 390 px da −232 px; bildirishnomalar paneli ham, telefonda hamma foydalanuvchida). Aloqa telefoni — platforma sozlamasi (`obuna.TELEFON_KALIT`, egasi korxonasining `company_settings`;
bo'sh — egasi korxonasining hujjat telefoni). Platforma paneli — `/platforma` (`templates/platforma.html`, "B — Kartochkalar"):
`GET /api/platform/companies` (holat + faollik), `/summary`, `POST …/{id}/block|unblock|extend` (`korish=1` — yangi sanani faqat
hisoblaydi; brauzerda formula yo'q), `/contact-phone`, `GET /api/platform/errors` (hamma korxonalar xatolari; faqat 500 lar
yoziladi — status filtri yo'q). Amallar mijozning audit jurnaliga yoziladi (`blocked` / `unblocked` / `extended`).
Mijoz zaxirasiga / tiklashga `companies` KIRMAYDI — muddatni zaxira fayli orqali o'zgartirib bo'lmaydi.

**Yuklangan fayllar himoyasi (kech111).** `static/uploads/<papka>/<fayl>` (buyurtma chizmasi, detal / material / retsept /
loyiha / qaytarish rasmi, kech111 dan logotip ham — `static/uploads/logos/`) FAQAT `main.yuklangan_fayl` orqali: kirgan
foydalanuvchi + fayl SHU korxonaning yozuviga bog'langan (`main.yuklama_korxonanikimi` — papka → jadval ustunlari, bir fayl bir
necha jadvalda bo'lishi mumkin); begona / yetim — 404. Marshrut umumiy `/static` mount dan OLDIN (`_yuklama_marshrutini_oldinga`),
mount esa (`ReliableStaticFiles.lookup_path`) uploads ichidagi HAQIQIY yo'lni (realpath) hech qachon bermaydi — `%2E`, `//`, `..`
bilan aylanib o'tish yopiq. URL shakli o'zgarmagan (eski havolalar egasi korxonada ochiladi). SAQLASH JOYI: konteyner diski
deployda yo'qoladi — Railway Volume `/app/static/uploads` ga ulangan (production `web-volume` — TASDIQLANGAN 2026-09-29,
~21.09 dan beri; sinov `web` da volume YO'Q — 7-bo'lim).

**Buyurtma hayoti.** Holatlar: `draft` (qoralama) → `new` / `in_progress` (jarayonda) → `delivered` (hammasi topshirilgan,
lekin «Tayyor» bosilmagan) → `ready` («Tayyor» — YAKUNIY, hisobotga kiradi); `cancelled`. Yuk xati (`crud.create_delivery`) —
qisman topshirish. «Tayyor» — `services.complete_order` (jarayondagi yoki topshirilgan buyurtmadan; bitta tranzaksiya;
loy / xomashyo qoldiqlari, qolgan qism uchun avto yuk xati). Hisobot va usta KPI FAQAT «Tayyor» (READY)
buyurtmani sanaydi (`services.get_monthly_report`, `services.calculate_monthly_master_kpi`). O'chirish:
`crud.ochirishda_yumshoqmi` (yuk / READY / DELIVERED / qaytarish yozuvi bo'lsa — yumshoq, «O'chirilganlar» da
tiklanadi), reja — `main._buyurtma_ochirish_rejasi`. Qarz hisobidagi buyurtmalar — yagona shart
`crud.qarz_hisobidagi_buyurtma_sharti`. Qoplamali buyurtmada retsept majburiy — `crud.qoplama_retsepti_tekshir`.
Buyurtma, yuk xati, loyiha raqami hech qachon qayta berilmaydi.

**Foyda va tannarx — yagona manbalar.** Buyurtma foydasi: `services.calculate_order_profit` (hisobot, KPI,
foyda oynasi — hammasi shu). Tannarx ishlatilgan / olingan paytdagi narxda muzlaydi (xomashyo harakati narxi,
tayyor mahsulot birligi — `crud._fp_stable_unit_cost`, detal `fp_unit_cost`). Qaytarish hodisalari (pul, ombor)
— `services._qaytarish_hodisalari` (hisobotda qaytarish bo'lgan oyda alohida qator). Detal tannarxi —
`services.get_order_item_unit_cost`. Qoplama retsepti — `services.resolve_recipe`.
Tayyor loy ZAXIRASIDAN olingan loy — olingan paytdagi retsept tannarxida (kech107, 36-band): `services.take_loy_from_stock`
harakatga shu narxni yozadi (`crud.log_movement(unit_cost=…)`), buyurtma qoplamasining zaxira qismi — o'sha narxda
(`services._buyurtma_zaxira_loyi`, hisob `services._buyurtma_sarf_hisobi`), qolgani — ingredientlar narxida; eski (narxi
0 / NULL) zaxira harakati — avvalgi qoida. Brak ham zaxira loyini shu narxda baholaydi.
Qoplama xarajati foydaga `orders.actual_loy_kg` (yoki izohdagi `loy_kg=`) bo'yicha kiradi (kech112, K112-3): «Tayyor» da
haqiqiy loy BO'SH qoldirilsa (API — `loy_kg` siz) `services.complete_order` rejani haqiqiy loy sifatida YOZADI —
kiritilgan reja bilan AYNAN natija (ilgari "reja bo'yicha hisoblandi" deyilib, loy yozilmasdi va 20 kg (~30 000 so'm)
qoplama foydadan tushib qolardi; `main` da bunday buyurtma yo'q — UI oynasi rejani oldindan to'ldiradi).

**Turkumlar.** Doimiy (kodda): `profil`, `panel`, `dona`. Ixtiyoriy: `loy_sotish`; eskirgan: `blok` (faqat
yoqilsa). `gips`, `termopanel` koddan olib tashlangan — kerak bo'lsa korxona MRP da o'z mahsulot turini
yaratadi (`mrp_product`). Korxona sozlamasi — `main.enabled_categories_of`.
Ombor (xomashyo) turkumlari: `Penoplast`, `Kimyoviy qo'shimchalar`, `Qattiq qotishmalar` (Minerallar), `Boshqa` —
Ta'minotchilar va Kirim sahifalarida bir xil ro'yxat; turkum berilmasa nomidan — `crud.guess_category`. Penoplast
(plotnost) — `is_penoplast` BELGISI, nom emas: ro'yxat `services.get_penoplast_list`, asosiy —
`services.get_default_penoplast` (nom bo'yicha faqat belgisi NULL eski qatorlar); turkum aniq "Penoplast", belgi
yuborilmagan bo'lsa — `crud.add_item` penoplast qiladi (kech105, K105-3).
Material nomi (kech112, K112-4): korxona ichida yagona (`uq_inventory_company_item_name` — yashirilgan material ham nomni
band qiladi), chetidagi bo'shliqlarsiz saqlanadi (`crud.add_item`, `crud.update_item`); boshqa material nomiga qayta
nomlash — 400 aniq sabab bilan (ilgari 500 va xato jurnali). Katta / kichik harf farqi — alohida nom (qoida o'zgarmagan).

**MRP.** Ishlab chiqarish buyurtmasi retsept suratini boshlashda oladi (`production_service.start_production_order`),
yakunlashda xomashyoni yechadi va yetmasa rad etadi (`production_service.complete_production_order`,
`allow_negative_stock` o'chiq). Buyurtma detaliga ishlab chiqarilganidan ko'p yuk xati yozilmaydi.
MRP tayyor mahsuloti «qoplamali» (`finished_products.is_coated`) — faqat shu ishlab chiqarish suratida qoplama qatori
HAQIQATAN kiritilgan bo'lsa (kech112, K112-5; brak sarfi `services._mrp_birlik_sarfi` bilan bir qoida). Ilgari model
standarti (True) qolardi: har MRP birligi (qoplamasiz travertin m², kafel kley kg ham) oylik hisobotdagi qoplamachi
bonusiga va donabay hodim haqiga 1 000 so'mdan qo'shilardi.
Ishlab chiqarish sahifasi (kech113, 6-bo'lim "A — Jadval + oynalar") hisobni OLDINDAN ko'rsatadi — AMAL bilan BITTA
funksiyalardan (`production_service` 5-bo'lim, hech narsa yozmaydi): retsept oynasi — `retsept_tannarxi`
(`POST /api/production/boms/preview`: `_compute_bom_line` + `_qoshimcha_xarajat`, tana — retsept yaratish kabi); yangi
ishlab chiqarish — `ishlab_chiqarish_rejasi` (`GET /api/production/orders/preview`: tana `_tana("ProductionOrder")`,
tekshiruvlar `_yaratish_tekshiruvi` — yaratish bilan bitta); boshlash / yakunlash oynasi — `mavjud_ishlab_chiqarish_rejasi`
(`GET /api/production/orders/{id}/preview`: qoralama — boshlash qoidasi, jarayondagi — qotgan surat bilan yakunlash
qoidasi); ro'yxat — `royxat_qoshimchalari` (mahsulot, birlik, buyurtma raqami, mijoz, taxminiy tannarx, qoralama
xomashyo holati; so'rovlar soni qatorga bog'liq emas; `?oy=YYYY-MM` — shu Toshkent oyida yakunlangan / bekor qilingan va
HAMMA ochiq ishlab chiqarishlar). Surat qatorlari — `_surat_qatorlari`; ombor solishtiruvi — `_yetmaydimi` (nisbiy 1e-9;
K113-1: 1 kg + 10 % × 3 m² = 3,3000000000000003, omborda aniq 3,3 kg bo'lsa boshlash ham, yakunlash ham rad etardi);
qoldiq — `_qoldiq_keyin` (yakunlashda aniq yetgan qoldiq — 0; K113-2: bir material retseptda bir necha qatorda bo'lsa,
boshlash ham yakunlash TARTIBIDA ketma-ket tekshiradi — ilgari boshlash har qatorni to'liq qoldiq bilan solishtirib o'tkazar,
yakunlash "bor: 1" deb rad etardi). Boshqa jarayondagi ishlab chiqarishlar kutayotgan xomashyo — faqat ogohlantirish
(`band_bilan_yetmaydi`); boshlash qoidasi o'zgarmagan (xomashyo «Yakunlash» da yechiladi, `Inventory` da "band" ustuni yo'q).
Buyurtma butunlay o'chirilsa ishlab chiqarish TARIXIY yozuv bo'lib qoladi — ikkala bog'lam uziladi (`crud.delete_order`,
`crud.permanent_delete_order`), detal o'chirilsa faqat detal bog'lami: ro'yxatda buyurtma raqami / mijoz buyurtmaning O'ZIDAN
(`source_order_id`), bog'lam yo'q — «Mijoz buyurtmasi — buyurtma o'chirilgan», savatdagi — raqami bilan «buyurtma o'chirilgan»
(`manba_ochirilgan`; K113-3 — jonli sinovda 13 dan 10 tasida «Buyurtma #?» edi). Miqdor ko'rinishi: 1 dan kichik — 3 ta ma'noli
raqamgacha (0,00625 m³, 0,125 m²; K113-4), qolgani — 2 xonagacha.
MRP tayyor mahsuloti (`finished_products.category = 'dynamic_bom'`, faqat `start_production_order` yaratadi) holati FAQAT
«Ishlab chiqarish» bo'limida o'zgaradi (kech114, K114-1): «Tayyor mahsulotlar»dagi «Sotuvga tayyor»
(`crud.complete_production`) va jarayondagisini o'chirish (`DELETE /api/finished/{id}` — marshrut + `crud.delete_finished_product`,
ikki to'siq) — 400 `crud._MRP_JARAYON_XABAR`; jarayonda sotish / kamaytirish xabari — `crud._jarayonda_xabari(fp)`. Ilgari
«Sotuvga tayyor» TM ni tannarx 0 va yechilmagan xomashyo bilan sotuvga chiqarardi, o'chirish esa ishlab chiqarishni
«jarayonda» qoldirib, keyingi «Yakunlash» xomashyoni izsiz yechardi. Tayyor mahsuloti yo'q (yoki boshqa korxonaniki)
jarayondagi ishlab chiqarish yakunlanmaydi — 409 `production_service.TM_YOQ_XABARI`, «Yakunlash» oynasi rejasi ham
(`_yakunlash_tm_xatosi` — bitta qoida). Sahifada jarayondagi MRP qatorida faqat «Ishlab chiqarishda ochish →»
(`/production?po=ID` — o'sha ishlab chiqarish oynasi); penoplast (eski yo'l) jarayondagisi — o'zgarmagan.
«Tayyor mahsulotlar» (kech114, egasi QARORI «7A»): bir xil mahsulot (manba, turkum, MRP turi, nom, birlik, qoplama, o'lcham —
`fpGuruhKaliti`) partiyalari bitta guruh qatorida (jami qoldiq, jarayondagi, band, 1 birlik tannarxi, narx, qiymat), bosilsa
partiyalari («Partiya №<ishlab chiqarish raqami>» + sana, o'z amallari bilan) ochiladi — ochiq guruhlar shu brauzerda
(`localStorage`) eslab qolinadi; bitta partiyali — oddiy qator (avvalgidek); tugagan partiya standartda yashirin
(«Tugaganlar ham»). Ombor qiymati (QAROR — MRP sotuv narxi «qo'lda»): narxi bor — qoldiq × narx, narxsiz — qoldiq tannarxi
(`crud._fp_ombor_qiymati`: `cost_price` qoldiq bilan birga kamayadi); `/api/finished/stats` — `total_value` (shu qoida),
`narxli_qiymat`, `narxsiz_tannarx_qiymati`, `narxsiz_soni` (faqat tayyor), `miqdorlar` / `jarayonda_miqdorlar` (birliklar
bo'yicha; ilgari «134 birlik» — qop + m + m² yig'indisi); `/api/finished` qatorida `ombor_qiymati`, `ishlab_chiqarish_id`
(`crud.fp_ishlab_chiqarish_raqamlari` — bitta so'rov).
Mahsulot turlari (kech114, QAROR «5B»): bitta jadval — `GET /api/production/product-types/xulosa`
(`production_service.turlar_xulosasi`: turning o'z maydonlari, omborda — tayyor + qaytgan qoldiq, band, jarayonda —
jarayondagi ishlab chiqarishlar, har FAOL retseptning 1 birlik taxminiy tannarxi «doim» / «qoplamali»; so'rovlar soni tur /
retsept soniga bog'liq emas). Tannarx — retsept oynasi bilan BITTA hisob: `_retsept_satri` + `_retsept_holatlari`
(`retsept_tannarxi` ham shular orqali). Sahifa ilgari har tur uchun alohida `/boms` so'rovi yuborardi.
Yuqori panel (kech114, QAROR «6A»): sahifa tugmalari `base.html` `.tb-amallar` ichida (`{% filter trim %}` — tugmasiz
sahifada bo'sh); telefonda (≤ 768 px) 1-qator — menyu, sarlavha, obuna belgisi, qo'ng'iroqcha, «···» (tungi rejim, Кирилл /
Lotin — `tbKopAlmashtir`), 2-qator — sahifa tugmalari yonma-yon, teng (uzun yorliq tugma ichida 2 qatorga o'tadi); 191 → 107 px
(tugmasiz sahifa — 58 px). CSS `base.html` ichida (`style.css` versiyasiz — brauzer keshlaydi). Yangi buyurtma oynasida
faqat «Shu buyurtma» paneli (`orders.html` `statPanellari` — umumiy «Statistika» yashirinadi); loy yorlig'i qisqa, izoh
maydon ostida. Namuna matnlarida haqiqiy odam / korxona nomi yo'q (kech114 — «Akmal aka», «Rustam aka», «Jo'rabek» olib
tashlandi), «Chapdan …» yo'q (telefonda chap tomon yo'q).

**Migratsiyalar.** Alembic YO'Q. `main.py` dagi `_migrate_*` funksiyalari server ishga tushganda (import paytida)
ketma-ket yuradi — 9-bo'lim ISHGA_TUSHISH. Har biri IDEMPOTENT, o'z `try/except` va `conn.rollback()` bilan
(bitta xato keyingilarini o'ldirmasin), `from sqlalchemy import text` funksiya ICHIDA (modul darajasida yo'q).
Xom SQL da enum qiymatlari NOMI bilan: `'READY'` (`'ready'` emas). Migratsiya muvaffaqiyati Railway deploy
logidan tekshiriladi. Sxemani tiklash — faqat zaxiradan. Ma'lumot to'ldiruvchi (UPDATE) migratsiya foydalanuvchi
qiymatini HAR ishga tushishda qayta yozmasin: bir martalik to'ldirish — faqat ustun SHU ishga tushishda yangi
qo'shilganda (kech105: `'Boshqa'` → `'Bazalt'` olib tashlandi; nomdan `is_penoplast` va asosiy plotnost — bir marta).

**Xavfsizlik.** Shablonlarda foydalanuvchi matni `escapeHtml` bilan; `onclick` ga qiymat `data-*` atribut orqali
(`|tojson` emas). `/api/` da 401 — JSON, sahifalarda — `/login` ga yo'naltirish. Platforma amallari
(Telegram bot, butun zaxira, korxona qo'shish) — `auth.platform_admin_only`. FastAPI API hujjatlari
(`/docs`, `/openapi.json`) o'chirilgan.

## 5. Testlar va darvozalar

**O'rnatish (bir marta):**

```bash
pip install -r requirements.txt pyflakes httpx       # konteynerda: --break-system-packages
npm install -g jsdom@24                              # JS testlari uchun (NODE_PATH=$(npm root -g))
# Lokal PostgreSQL 16 (pul / poyga testlari uchun):
apt-get install -y postgresql
su postgres -c "/usr/lib/postgresql/16/bin/initdb -D /home/claude/pgdata -A trust -E UTF8 --locale=C.UTF-8"
su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /home/claude/pgdata -l /home/claude/pgdata/server.log \
  -o '-p 5432 -k /var/run/postgresql -c listen_addresses=127.0.0.1 -c fsync=off' start"
```

**Yurgizish:**

```bash
bash tools/hammasi.sh                         # hamma test, SQLite, TENANT_FILTER o'chiq → /tmp/hammasi_tf0/_xulosa.txt
TF=1 bash tools/hammasi.sh                    # TENANT_FILTER=1 bilan
PG_URL=postgresql://postgres@127.0.0.1:5432 bash tools/hammasi.sh   # PG qo'llaydigan testlar HAQIQIY PG da
python3 tools/test_tm_tannarx.py              # bitta test (SQLite)
PG_URL=postgresql://postgres@127.0.0.1:5432 python3 tools/test_tm_tannarx.py
node tools/test_kichik103_ui.js               # bitta JS test (shablonning haqiqiy JavaScript'i, jsdom)
python3 tools/tenant_lint.py                  # korxona filtri lint — "TOZA" kutiladi
python3 tools/pasport_xarita.py --tekshir     # shu pasport xaritasi kod bilan mos
bash tools/vaqt_sayohati.sh                   # vaqt / sana mantig'iga tegilsa: to'plam 4 chegara paytida (pip install time-machine)
python3 -m pyflakes crud.py main.py schemas.py services.py
```

Har test oxirida `NATIJA: o'tdi = N yiqildi = M jami = K`; talab — `yiqildi = 0` va chiqish kodi 0. PG testlarini
parallel yurgizmang. Bitta test ≤ 900 s. Test yurib turganda u o'qiydigan fayllarni tahrirlamang.

**Kutilgan natija (kech110 o'lchovi, 2026-09-29, zip 105 fayllari bilan):** `bash tools/hammasi.sh` — 151 test fayli (Python 123, JS 28), jami **12 417** tekshiruv, `fail=0`, `yomon_rc=0`; `TF=1 bash tools/hammasi.sh` — **12 418** (farq: `test_idor.py` TENANT_FILTER rejimida qo'shimcha tekshiruv); `PG_URL` bilan alohida yurgizilgan 92 ta PG testi + `tools/test_pul_query.py` / `tools/test_qaytarish_query.py` — hammasi 0 yiqilish; `tools/tenant_lint.py` — TOZA (ma'lum holatlar 106); pyflakes — `crud.py` 62, `main.py` + `schemas.py` 14, `services.py` 11 ta ESKI ogohlantirish (yangisi qo'shilmasin), testlar 0. Test qo'shilsa sonlar o'zgaradi — talab o'zgarmaydi: `fail=0`, `yomon_rc=0`.

**Darvozalar (o'zgartirishdan keyin yiqilsa — sababini toping, testni "moslab" yashirmang):**

- Korxona izolyatsiyasi: `tools/test_tenant_isolation.py`, `tools/test_idor.py`, `tools/test_telegram_tenant.py`,
  `tools/test_peno_tenant.py`, `tools/test_loy_tenant.py`, `tools/test_material_korxona.py`,
  `tools/test_hisobot_korxona.py`, `tools/test_top_tm_korxona.py`; statik — `tools/tenant_lint.py`.
- Pul aniqligi va sig'imi (PG): `tools/test_pul_query.py`, `tools/test_qaytarish_query.py`, `tools/test_qarz_tiyin.py`,
  `tools/test_buyurtma_narx_jami.py`, `tools/test_tolov_query.py`, `tools/test_xarajat_query.py`.
- Narx formulalari etaloni: `tools/test_narx_etalon.py` (server), `tools/test_narx_frontend.js` (brauzer).
- Atomiklik va poygalar (PG): `tools/test_atomik_103.py`, `tools/test_atomik_tolov.py`, `tools/test_ochirish_atomik.py`,
  `tools/test_tayyor_atomik.py`, `tools/test_detal_poyga.py`, `tools/test_tm_qulf.py`.
- Buyurtma hayoti / «Tayyor» / o'chirish: `tools/test_buyurtma_oqimi.py`, `tools/test_tayyor_yuk.py`,
  `tools/test_hisobot_tayyor.py`, `tools/test_ochirish_yopish.py`, `tools/test_ochirish_loy.py`, `tools/test_buyurtma_raqam.py`,
  `tools/test_qarz_ochirilgan.py`, `tools/test_mijozga_qaytarish.py`.
- Qaytarish: `tools/test_qaytarish_moliya.py`, `tools/test_qaytarish_narx.py`, `tools/test_qaytarish_ochirish.py`,
  `tools/test_qaytarish_yigindi.py`, `tools/test_ortiqcha_qaytarish.py`, `tools/test_qaytgan_tannarx.py`.
- Brak: `tools/test_brak_bosqich.py`, `tools/test_brak_tahlil.py`, `tools/test_brak_narx.py`, `tools/test_brak_ochirish.py`,
  `tools/test_brak_belgisi.py`, `tools/test_brak_belgi_himoya.py`, `tools/test_brak_mrp_loy.py`, `tools/test_eski_brak_muzlash.py`.
- Tayyor mahsulot (TM): `tools/test_tm_tannarx.py`, `tools/test_tm_detal_tannarx.py`, `tools/test_tm_qoshish.py`,
  `tools/test_tm_sotuv_narx.py`, `tools/test_tayyor_qiymat.py`, `tools/test_tayyor_mahsulot.py`.
- Loy / qoplama retsepti: `tools/test_qoplama_retsept.py`, `tools/test_retsept_almashtirish.py`, `tools/test_loy_manba.py`,
  `tools/test_loy_manfiy.py`.
- MRP: `tools/test_mrp_tannarx.py`, `tools/test_mrp_kerak.py`, `tools/test_mrp_yuk_qaytish.py`, `tools/test_mrp_tayyorlik.py`,
  `tools/test_mrp_xarajat_surat.py`, `tools/test_mrp_bosh_tannarx.py`.
- Tezlik (so'rovlar soni, N+1): `tools/test_royxat_n1.py`, `tools/test_hisobot_n1.py`, `tools/test_qoldiq_n1.py`,
  `tools/test_hisobot_kesh.py`, `tools/test_kesh_oquvchi.py`.
- HTML in'ektsiya: `tools/test_html_escape.py` (statik), `tools/test_html_escape_dom.py` (dinamik).
- Shu pasport va shablon → marshrut havolalari: `tools/test_pasport.py`.
- Ombor turkumi va penoplast belgisi (qayta ishga tushishda o'zgarmasligi, yangi material): `tools/test_ombor_turkum.py`,
  `tools/test_ombor_turkum_ui.js`.
- Vaqt — Toshkent kalendari (kun / oy / yil chegaralari, "bugun", jarayon mintaqasiga bog'liq emaslik):
  `tools/test_toshkent_vaqt.py`, `tools/test_soat_utc.py`; butun to'plam chegara paytlarida — `tools/vaqt_sayohati.sh`.
  Ko'rinish (kech106): server — `tools/test_toshkent_korinish.py` (Telegram, PDF, sahifalar, API matnlari, AST statik);
  brauzer — `tools/test_toshkent_korinish_ui.js` (tk yordamchilari va sahifa funksiyalari UCH mintaqada: Asia/Tashkent,
  UTC, America/New_York — natija AYNAN; statik: shablon JS da `new Date(` faqat saralash taqqoslashida, `toISOString()` —
  faqat `tk*` blokida).
- PDF shrifti (7 PDF — Kirill ma'lumot, "№", qora kvadrat yo'q; metrika = Helvetica; ma'lumotdagi emoji; statik — kod
  matnlarida shriftda yo'q belgi yo'q): `tools/test_pdf_shrift.py`.
- PDF matni va sarlavhasi ("<" / "&" li foydalanuvchi matni — 7 PDF 200 va matn AYNAN; 2-korxona sarlavhasi; statik —
  `Paragraph` ga `_x`): `tools/test_pdf_matn.py`.
- Moliya xarajatlar ro'yxati = JAMI (PDF va sahifa; 205 ta tranzaksiya — cheklovsiz; eski oylik shakl): `tools/test_moliya_tafsilot.py`.
- Brak — bitta raqam (karta = Moliya = tahlil; tayyor turgan yo'qotish alohida; bog'lanmagan eski harakat; oy chegarasi;
  PDF qatori; B korxona): `tools/test_brak_bitta_raqam.py`, `tools/test_brak_bitta_raqam_ui.js`.
- Tayyor loy zaxirasi narxi (qoplama muzlaydi, brak zaxira loyini oladi, eski harakat — avvalgidek): `tools/test_zaxira_loy_narx.py`.
- Kirim hujjatini bekor qilish (reja = amal, o'rtacha narx, to'lov tanlovi, izolyatsiya, PG poyga): `tools/test_kirim_bekor.py`,
  `tools/test_kirim_bekor_ui.js`.
- Server rad sababi — kpi / inventory / finished ning 29 joyi (matn, obyekt, ro'yxat): `tools/test_xato_sababi_ui.js`.
- Loyiha tahriri (muddat, tozalash, izolyatsiya): `tools/test_loyiha_tahrir.py`, `tools/test_loyiha_tahrir_ui.js`;
  hodim avans so'rovi (tekshiruv, takror, PG poyga): `tools/test_hodim_avans.py`.
- (kech114) K114-1 (jarayondagi MRP TM — «Sotuvga tayyor» / o'chirish / sotish / kamaytirish rad, ikki to'siq; TM yo'q yoki
  begona — yakunlash 409 va reja), ombor qiymati (narxsiz — tannarx), miqdorlar birliklar bo'yicha, `/api/finished`
  maydonlari (bitta so'rov), turlar jadvali (preview bilan AYNAN tannarx, faqat faol, so'rovlar soni), korxona chegarasi
  (SQLite, PG, TF1): `tools/test_tayyor_guruh.py`; sahifalar (HAQIQIY server + jsdom — guruhlar, ochish / eslab qolish,
  tugagan partiya, statistika, MRP havolasi, turlar jadvali, `?po=`, «···» menyusi, «Shu buyurtma», namunalar, HTML
  in'ektsiya): `tools/test_dizayn114_ui.py`.
- (kech116) A bosqich 2-qism: hujjatlardagi hisob qatorlari (qaytarish, chegirma + kechirilgan, ustama, ustama + kechirilgan,
  ortiqcha to'langan, tiyinli summalar — API `hisob` (kechirilgan alohida), yuk xati, hisob-kitob varaqasi, nakladnoy
  (kechirilgan — chegirma ichida, foizsiz; «Kechirilgan qarz» so'zi yo'q); belgilar; SQLite, PG): `tools/test_a116_pdf.py`;
  pul oqimi (mustaqil hisob bilan AYNAN, Toshkent chegaralari, kunlar = oy, korxona, API, kassa bilan bir qoida, «Korxona
  sog'ligi»), xarajat tarkibi va tannarx: `tools/test_a116_pul.py`; haqiqiy IP (`auth.mijoz_ip` qoidasi, HAQIQIY HTTP —
  jurnalda IP), kirish cheklovi (nom 5 / IP 20), parol / PIN almashtirilganda sessiyalar: `tools/test_a116_kirish.py`; sahifalar
  (HAQIQIY server + jsdom — buyurtma «Hisob-kitob», Hisobotlar, Moliya, Dashboard, Loyihalar, parol oynasi, in'ektsiya):
  `tools/test_a116_ui.py`. `test_a115_korinish.py` ga K115-2 / K115-3 (H8–H10, R10–R12). Moslangan: `test_naqd_kassa.py`
  (bosh sahifa pul oqimi — haqiqiy pul), `test_loyiha_forma.js` (tanada `total_budget` yo'q), `test_tana_qatiy.py` (parol oynasi),
  `test_toshkent_korinish.py` (UTC sanasi — aniq namunalarda: haqiqiy sana 30.09 bo'lgan kuni ham to'g'ri),
  `test_transport_foyda.py` U3 (bosh sahifa «Chiqim» — yagona `/api/finance/pul-oqimi` manbasidan).
- (kech118) B bosqichi 1-qism — dastur oynalari: statik (xom prompt / confirm yo'q, har qoplama oyna belgili — shablon va JS,
  xavfli amal tugmasi belgisiz, xabardan keyin yangilanadigan joyda `await`), HTTP (404 / 403 sahifa — brauzer; JSON — API va
  boshqa mijozlar; o'zbekcha rol nomlari), HAQIQIY server + jsdom (xabar oynasi va navbat, Esc / tashqariga bosish, yozilgan
  ma'lumotda so'rash, tasdiq ustidagi Esc, ustma-ust oynalar, ichki panel, kiritish oynasi — qarz to'lovi, TM narxi, xarid
  tahriri, «HAMMASINI-OCHIR», Telegram bot; SQLite, PG): `tools/test_b118_oyna.py`. Moslangan (sahifa endi `kiritishOyna` /
  `xabarOyna` chaqiradi — soxta muhitga shu test soxtalariga ulangan): `test_narx_kiritish_ui.js`, `test_xarid_tahrir_ui.js`,
  `test_xato_sababi_ui.js`, `test_toshkent_korinish_ui.js`, `test_qaytarish_ochirish_ui.js`.
- (kech118) B bosqichi 2-qism — son / sana / birlik ko'rinishi, kontrast, mayda yozuv: statik (12 px dan kichik yozuv yo'q,
  xira yozuv rangi yo'q, `--text3` / `--gold-dark` o'lchami — kontrast hisobi, kirish sahifalari, yangi global nom yo'q),
  yordamchilar (`sonKor`, `foizKor`, `birlikKor`, `matnRangi`, tk sana — node da haqiqiy funksiya; `|son`, `_son_uz`), HAQIQIY
  server sahifalari (ombor «8,3 kg», retsept «33,3%», grafik oy yorliqlari, korxona sog'ligi sabablari, moliya kassa kartasi;
  SQLite, PG): `tools/test_b118_korinish.py`. Moslangan (vergul, to'q yashil #15803D, kontekstga `sonKor`…, aniq sana matni):
  `test_a115_korinish.py`, `test_brak_bitta_raqam_ui.js`, `test_brak_tahlil_ui.js`, `test_brak_tahlil.py` (D2 «5,01 %»),
  `test_narx_kiritish_ui.js`, `test_toshkent_korinish_ui.js` (+ `soz` bir necha qatorli obyektni oladi), `test_kichik103_ui.js`,
  `test_kam_qoldiq_ui.js` (kontekstga `sonKor` / `matnRangi`), `test_ombor_kpi_loy.py` («5 kg»), `test_html_escape.py`
  (`matnRangi(x)` — «shaffof»: xavfsizligi x niki).
- (kech118, zip 118) Yo'nalishlar bo'yicha moliyaviy natija (egasi QARORI 15:23 — taqsim yo'q): server — `test_a117_yonalish.py`
  D bo'limi MOSLANDI (ustun D − T − O − X = N; ΣN − umumiy oylik − umumiy xarajat = Jami natija = Moliya sof foydasi — so'm va
  tiyinda; «ulush» yo'q; daromadsiz oy — taqsimsiz; D19 — yo'nalish xarajatlaridagi kasr qoldiq bilan yaxlitlash; PDF «NATIJA
  (+ / −)» qatori); sahifa — `test_a117_ui.py` M1–M2d (natija qatori ishorasi bilan, oyliklar bloki, umumiy — faqat Jami,
  kartalar, doira, rentabellik, izoh) va M13–M15 (davr: chorak boshidan, yil boshidan + PDF shu davr, oraliq + noto'g'ri
  oraliqda so'rov yo'q). Davr / solishtirish / tarkib — `tools/test_yonalish_natija.py`.
- (kech117) A2 — yo'nalishlar bo'yicha moliya: API (ro'yxat, qo'shish, takror nom, nomini o'zgartirish, yashirish, asosiyni
  himoya, ishlatilganini o'chirish rad, begona korxona), yozish yo'llari (hodim, xarajat, transport, kirim, MRP turi — yashirin /
  begona / eski `production_type`), migratsiya (idempotent), hisob D0–D18 (detal bo'yicha daromad / tannarx, chegirma, qaytarish,
  brak, TM, bevosita va ulush, daromadsiz oy — teng, qoldiq, yig'indi = Moliya sof foydasi so'mda va tiyinda), bugun / grafik /
  PDF (matn va SOF FOYDA qatori = hisobot), zaxira nusxa → tiklash (SQLite, PG): `tools/test_a117_yonalish.py`; sahifalar (HAQIQIY
  server + jsdom — Sozlamalar, Ishlab chiqarish, Hodimlar, Moliya, Kirim, Dashboard, Hisobotlar, bitta yo'nalishli korxona,
  in'ektsiya): `tools/test_a117_ui.py`. Moslangan (qoida yangi qarorga): `test_narx_etalon.py` I bo'limi (yo'nalishlar),
  `test_qaytarish_moliya.py`, `test_transport_foyda.py` C5/C6/H4, `test_qoldiq_n1.py` D9, `test_toshkent_vaqt.py` E1,
  `test_pdf_matn.py`, `test_pdf_shrift.py` B7, `test_tana_qatiy.py`, `test_mrp_sahifa_ui.py`, `test_mrp_bosh_tannarx.py` S1,
  `test_pul_query.py` / `test_xarajat_query.py` (qoida kalitlari + `yonalish_id`), `test_brak_belgi_himoya.py`, `test_brak_narx.py`,
  `test_kirim_qiymat.py`, `test_idor.py`, `test_tahrir_tiyin_ui.js`, `test_toshkent_korinish_ui.js`.
- (kech115) A bosqich 1-qism: kirim (takror qator, sana / muddat chegaralari va pul yozuvlari sanasi, sahifa ssenariylari —
  yo'nalishsiz bosish, tarmoq uzilishi, takror / chala qator, boshlang'ich ombor, o'tgan sana, K115-1 — SQLite, PG):
  `tools/test_kirim_a115.py`; Qarzdorlar (bo'sh summa, «Butun qarz», kechiriladigan summa, tasdiq), «Tayyor» (rad, tarmoq,
  muvaffaqiyat), to'lovni o'chirish sababi, narxsiz buyurtma, O'chirilganlar jurnali (HAQIQIY server + jsdom):
  `tools/test_a115_ui.py`; taqqoslash, korxona sog'ligi, Hisobotlar / Omborxona / Moliya / Dashboard ko'rinishi:
  `tools/test_a115_korinish.py`; to'lov funksiyalari (tasdiq bilan moslangan): `tools/test_tolov_ui.js`. Eski harness
  testlari yangi yordamchilar bilan MOSLANDI (qoida o'sha): `test_standart_tiyin_ui.js` (R10 — boshqa qator, YANGI R11 — takror
  qator rad), `test_tahrir_tiyin_ui.js` (summa «Butun qarz» da), `test_narx_kiritish_ui.js` A6 (hajm — bitta joy),
  `test_kelishilgan_tahrir_ui.js`, `test_narx_nol_himoya_ui.js`, `test_kichik103_ui.js` (`_narxsizDetallar` / `_narxsizTasdiq`).
- (kech113) MRP sahifasi — reja = amal (retsept tannarxi = yakunlangandagi tannarx; reja «mumkin» ⇔ boshlash / yakunlash
  o'tadi; reja xatosi = yaratish / boshlash xabari AYNAN), K113-1, K113-2, jarayondagilar bilan raqobat, ro'yxat qo'shimchalari
  (o'chirilgan / savatdagi buyurtma, o'chirilgan detal — K113-3),
  davr (Toshkent oyi chegarasi), so'rovlar soni, o'zbekcha xabarlar, reja hech narsa yozmaydi, korxona chegarasi (SQLite, PG,
  TF1): `tools/test_mrp_reja.py`; sahifa (HAQIQIY server + jsdom — ro'yxat, chiplar, saralash, yangi ishlab chiqarish,
  boshlash / yakunlash / batafsil / bekor oynalari, retsept oynasi, mahsulot turi, o'chirilgan buyurtma va kichik miqdorlar
  ko'rinishi — K113-3 / K113-4, in'ektsiya): `tools/test_mrp_sahifa_ui.py`
  (+ HAQIQIY brauzer o'lchovi 360 / 390 / 768 / 1440 px — `work/k113/ekran113.py`).
- (kech111) Platforma admin paneli (holat chegaralari, uzaytirish «Aralash», ruxsat, sinov davri, qo'lda / avtomatik bloklash —
  login, API, sessiyalar, hodim paneli, bot, kam qoldi cron; ochish va imtiyoz, kunlik eslatmalar takrorsiz, mijoz ogohlantirishi,
  aloqa telefoni, raqamlar, xatolar, fayllar himoyasi va aylanib o'tish, logotip, migratsiya — SQLite, PG, TF1):
  `tools/test_platforma_obuna.py`; panel sahifasi (HAQIQIY markup va JS, jsdom — kartochkalar, saralash, oynalar, in'ektsiya):
  `tools/test_platforma_ui.js`; yuqori panel ochiluvchi panellari ekran ichida (tor / keng / o'lcham o'zgarishi, tashqi bosish):
  `tools/test_yuqori_panel_ui.js` (+ HAQIQIY brauzer o'lchovi — `work/k112/probe112panel.py`, 360–1400 px).
- (kech110) Tahrirda kelishilgan summa — yagona qoida, kechirilgan qarz, migratsiya, brauzer ↔ server paritet (SQLite, PG, TF1):
  `tools/test_kelishilgan_nisbat.py`; tahrir formasi (HAQIQIY `editSelected` qismi, `reapplyDiscount`, `updateOrder` tanasi):
  `tools/test_kelishilgan_tahrir_ui.js`; MRP amallari Faoliyat jurnalida (atomiklik, korxona, `/logs`): `tools/test_mrp_jurnal.py`.
- (kech109) MRP bandi korxona chegarasi va tahrirda ishlab chiqarishga bog'langan detal (E-1, K109-2 — SQLite, PG, TF1):
  `tools/test_mrp_band_korxona.py`; hodim to'lov tarixi korxona bo'yicha + o'lik funksiya (E-2 / E-3):
  `tools/test_hodim_tarix_korxona.py`; lint ko'r nuqtalari (func / case so'rovlari, `.filter(*ro'yxat)`, K107-3):
  `tools/test_lint_func_royxat.py`; `main` ko'chirish mexanizmi (SINOV → HAQIQIY, soxta `saas_migration` bilan) va korxona id
  ketma-ketligi (K108-1, K109-3): `tools/test_saas_otish.py`; tahrirda qoralama tugmasi (HAQIQIY forma markupi, K109-1):
  `tools/test_qoralama_tugma_ui.js`. Haqiqiy `main` ma'lumoti ustidagi o'tish (python3.12 — `saas_migration` sintaksisi;
  `python3.12 -m pip install -r requirements.txt httpx2`): ISH zipidagi `otish109.sh`.

**Yangi o'zgarish tartibi:** (1) asl kodda nuqsonni o'lchash (probe — SQLite va PG); (2) tuzatish; (3) yangi test
(asl kodga qarshi yiqiladi, QULAMAYDI); (4) mutatsiyalar; (5) `bash tools/hammasi.sh` (+ `TF=1`), PG testlari,
`tools/tenant_lint.py`, pyflakes, `tools/pasport_xarita.py --tekshir` (yangi marshrut / migratsiya / test bo'lsa
`--yoz`); (6) zip + yuklash ko'rsatmasi; (7) yuklangach klon + MD5 + jonli deploy isboti (faqat o'qish).

## 6. Qabul qilingan BIZNES qarorlari (QAYTA SO'RALMAYDI)

Egasining javoblari (sana, qisqa mazmun). Yangi savol faqat shu ro'yxatda YO'Q holat uchun.

**Umumiy / jarayon**
- (2026-09-20) `main` ga bosqichma-bosqich emas — hammasi `staging` da tugab, BIR marta ehtiyotkor ko'chirish;
  keyin sotuv. Istisno: `main` ga bugun zarar berayotgan narsa alohida kichik reliz bo'lishi mumkin.
- (kech91) "Hammasini staging da" — mayda UX, o'lik kod, tezlik kuzatuvlari ham `main` dan OLDIN.
- (kech107, 10g) "Boshqa bot" — ERP xabarlari (admin / mijoz / usta) katalog botidan EMAS, alohida botdan keladi:
  «Telegram xavfsizligini yoqish» katalog botiga tegmaydi.
- (kech105, K105-1) `main` shoxidagi 2026-09-24 xato yuklash oqibati (`main.py` 15-sentabr nusxasi: sovg'a davriga
  usta qo'shish «+ Qo'shish» va zaxiradan tiklash marshrutlari yo'q) — "Yo'q, katta ko'chirishda tuzalsin": hozir
  `main` ga tegilmaydi, bir martalik ko'chirishda tuzaladi.
- (2026-09-20) Rus tilida so'zlashuvchi mijozlarga ham sotiladi — interfeys tarjimasi (i18n) kerak; (kech104) u `main` ga
  ko'chirishdan KEYIN, rus tilidagi mijozga sotishdan OLDIN qilinadi.

**Turkumlar va MRP**
- `profil`, `panel`, `dona` — kodda doimiy qoladi (kundalik, pul uchun muhim). `gips`, `termopanel` — koddan
  BUTUNLAY olib tashlanadi (bajarilgan); G'isht ham (tizim tekshiruvida eski izoh belgisi qoldig'i bor).
  `blok`, `gips`, `bazalt` — har korxona MRP da o'zi yaratadi.
- Qoplama narxi koeffitsiyenti korxona bo'yicha MRP sozlamasi (kimdir ×2, kimdir ×2.5); detal qoplamali /
  qoplamasiz ekani saqlanadi. Hodimlarning gips to'lov birliklari kerak emas (`metr` / `dona` / `kg` yetarli).
- (kech113, "MRP asosiy: 1–4") Ishlab chiqarish sahifasi dizayni — variant "A — Jadval + oynalar" (avval "B" tanlangan,
  o'sha kuni A ga o'zgartirildi): ro'yxat — jadval (telefonda kartalar), holat chiplari, davr / mahsulot / qidiruv; yangi
  ishlab chiqarish, retsept, boshlash / yakunlash / batafsil — oynalarda; qoralama qatorida «xomashyo yetadi / yetmaydi»
  belgisi (C dan). «Tayyor — omborga kirim» tezkor tugmasi — "Kerak emas".
- (kech114, dizayn 5–10 — "hammasi") «Tayyor mahsulotlar» — "7A — Guruh, bosilsa ochiladi"; mahsulot turlari — "5B — Jadval";
  telefonda yuqori panel — "6A — Bir qator + tugmalar" (hamma sahifalarga); MRP tayyor mahsulotining sotuv narxi —
  "Hozirgidek qo'lda" (narx 0 qoladi, sotishda yoziladi; «Ombor qiymati» narxsiz partiyani TANNARX bo'yicha qo'shadi).

**Buyurtma**
- (kech85–86, "A") Buyurtma, yuk xati va loyiha raqami HECH QACHON qayta berilmaydi (faqat o'sadi, bo'shliq qoladi).
- (kech74, 91 "B") To'liq topshirilgan buyurtma hisobot va usta KPI ga FAQAT hodim «Tayyor» bosganda kiradi.
- (kech74, 92 "B") «Tayyor» buyurtmaning yuk xatini o'chirish TAQIQLANGAN; DELIVERED buyurtma yuki o'chirilsa —
  buyurtma jarayonga (`in_progress`) qaytadi.
- (kech38, 12-band) To'lov bog'langan yuk xati o'chirilganda HAR SAFAR so'raladi: to'lovni ham o'chirish yoki
  to'lovni saqlab qolish.
- (kech99, 93 "B") Qisman topshirilgan buyurtma o'chirilsa, topshirilgan qism daromadi, tannarxi va usta KPI
  hisobotda QOLADI ("qisman bo'lsa ham tovar berilgan").
- (kech100, 134 "A") O'chirilgan, lekin hisobotda qolgan (READY / DELIVERED) buyurtma qarzi Qarzdorlarda
  "o'chirilgan" belgisi bilan ko'rinadi.
- (kech99, 131 "B") Ortiqcha to'langan buyurtma uchun "Mijozga qaytarish kerak" belgisi va ro'yxati.
- (kech103, 59) "Tarix saqlansin" — qaytarish yozuvi (ortiqcha / brak) bor buyurtma o'chirilsa yumshoq
  o'chiriladi (qaytarish va to'lov yozuvlari saqlanadi, tiklash mumkin).
- (kech103, 54) "Majburiy tanlov" — qoplamali buyurtmada retsept tanlanmasa saqlanmaydi.
- (kech58) Retseptsiz ESKI buyurtmalar — qoplama xarajati foydaga qo'shilmaydi, eski foyda o'zgarmaydi
  ("faqat yangi buyurtmalar").
- (kech62) Jarayondagi buyurtmada retsept almashtirilsa — eski retsept loyi omborga QAYTADI, yangisidan YECHILADI.
- (kech81, 102 "A") O'chirilgan (tugallanmagan) buyurtmaning ishlatilmagan loyi OLINGAN joyiga qaytadi.
- (kech70, "Taqiqlansin") MRP detaliga ishlab chiqarilganidan ko'p yuk xati yozilmaydi.
- (kech60, "Ha") Kerak bo'lmay qolgan ortiqcha mahsulot (yetkazishdan oldin ham) tayyor mahsulot omboriga qo'yiladi.
- (kech47) Buyurtma tannarxi xomashyo ISHLATILGAN paytdagi narxda muzlaydi; (kech49, "A") eski buyurtmalar
  (narx yozilmagan) bugungi narxda bir marta muzlatilgan.

- (kech110, K110-1) Ustamali buyurtmada jami o'zgarsa — "Foizi saqlansin" (400 000 / 450 000 → 300 000 da 337 500);
  to'lovda kechirilgan qarz — "Kechirilgan so'mda qolsin" (1 000 000, 5 %, 2 000 kechirilgan → 1 200 000 da 1 138 000).

**Qaytarish va pul qaytarish**
- (kech41, 4-band) Chegirmali buyurtmada qaytarish summasi KELISHILGAN (chegirmali) narxdan: 1 000 000 lik
  buyurtma 900 000 ga kelishilgan bo'lsa — to'liq qaytarishda 900 000.
- (kech41, 24-band) To'lanmagan pulni qaytarib bo'lmaydi: qaytgan mahsulot qarzdan chegiriladi, naqd faqat
  ortiqcha to'langan qism uchun (faqat butun qaytarish).
- (kech40, 22 "B") Pul qaytarilgan qaytarish o'chirilsa — hammasi orqaga (kelishilgan summa tiklanadi, manfiy
  to'lov o'chadi, loyiha to'langan summasi qayta hisoblanadi, jurnalga yoziladi).
- (kech102, 144) "Qaytarish oyida" — o'tgan oylar o'zgarmaydi, qaytarish bo'lgan oyda alohida qator; usta KPI
  "yo'qotilgan foydaga" (qaytarilgan pul − omborga qaytgan tannarx).

**Brak**
- (2026-09-23) Brak faqat ishlab chiqarish ichida: mijoz brak olmaydi, buyurtma miqdori baribir to'liq
  tayyorlanadi; brak xomashyo yechish va zarar yozish uchun (mijozga pul qaytarish emas).
- (kech45) Brak bosqichlari: Kesish, Qoplash (loy tortish), Quritish, Saqlash / tashish. Brak mahsulotning
  keyingi taqdiri — keyin hal qilinadi (7-bo'lim).
- (kech56) Brak me'yori 5 %; sabab ro'yxati — Xomashyo sifati, Ishchi xatosi, Uskuna / stanok nosozligi,
  O'lcham / qolip xatosi, Boshqa; javobgar hodim — ixtiyoriy.
- (kech52, 38 "C") Omborxona qo'lda "Chiqim" izohi "Brak" bilan boshlansa — brak xarajati hisoblanadi.
- (kech51, 37 "A") Eski brak (narx yozilmagan) bugungi narxda bir marta muzlatilgan.
- (kech54, 41) MRP detali brakining qoplama loyi — qoplama narxi ulushiga qarab (qimmat detal ko'proq).
- (kech54, 42) Brak summasi qoidasi — eskisi o'zgarmaydi, faqat yangilari to'g'ri.
- (kech107, 49 "Bitta raqam") Karta, bosh sahifa, tahlil va Moliya «Brak» qatori — BITTA haqiqiy xomashyo narxi;
  omborda tayyor turgan mahsulot shikastlanishi — Moliyada ALOHIDA qator; jami xarajat o'zgarmaydi.
- (kech107, K107-4 "Shart emas") Yozuvga bog'lanmagan ESKI brak (bog'lam 2026-09-23 dan oldin; `main` da — ko'chirishgacha
  hammasi: 13 yozuv, 2026-09) tahlil taqsimotida 0 so'm, summa «bog'lanmagan» izohida; jami raqamlar to'g'ri; kod o'zgarmaydi.

**Platforma (SaaS) — admin paneli (kech110)**
- Ko'rinish — "B — Kartochkalar" (har korxona kartochka, obuna muddati chizig'i, saralash). Qo'shimchalar (kech109): bloklash /
  ochish, korxona faolligi, obuna muddati; korxona ma'lumotini platformadan tahrirlash — YO'Q.
- Obuna eslatmasi — "Sizga + mijozga": egasiga Telegram, mijozning o'z dasturida ogohlantirish. Muddat o'tsa — "3 kundan keyin
  avtomatik" bloklanadi (ochish — egasi); avtomatik bloklanganni muddatni uzaytirmasdan ochish — "3 kunlik imtiyoz" (uzaytirilmasa
  yana yopiladi). Bloklangan sahifadagi telefon — "Sozlamada yozaman" (platforma panelidagi «Aloqa telefoni»).
- (kech110 oxiri, egasining «Super Admin» promptidan) Qo'shimcha qamrov: yuklangan fayllar himoyasi + doimiy saqlash joyi,
  platforma raqamlari (korxonalar holati, bugungi kirishlar / xatolar) va hamma korxonalar xatolari bitta ro'yxatda, yangi
  korxona — **30 kunlik sinov davri** (tugagach — oddiy obuna kabi: eslatma → 3 kundan keyin avtomatik bloklash). Foydalanuvchi
  limiti — YO'Q. Tariflar, support tiketlari, versiya boshqaruvi, server resurslari, VIEW / EDIT ruxsatlari — hozir emas.
- (kech111) Uzaytirish — "Aralash": muddat hali tugamagan — eski sanadan davom etadi (15.10 → +1 oy → 15.11); tugagan — bugundan
  (20.09 tugagan, bugun 29.09 → 29.10); bloklangan kunlar uchun pul olinmaydi. Mijoz ogohlantirishi — "Admin, keyin hamma":
  7 kun qolganda faqat korxona adminlari, muddat tugagach (imtiyoz) — barcha xodimlar.

**Moliya va ombor**
- (kech114, audit — 144 topilma) Tuzatish tartibi: «A — pul va ma'lumot xatolari» BIRINCHI, keyin A2 (yo'nalishlar bo'yicha
  moliya), qolgan qarorlar, B–F, so'ng `main`.
- (kech114) «Sof foyda» — BITTA raqam: Moliyadagi sof foyda asosiy; bo'lingan hisobot (yo'nalishlar) aynan shuni bo'ladi
  (yig'indisi teng). BAJARILDI kech117 (so'mda va tiyinda teng).
- (kech114) «Pul oqimi» — HAQIQIY pul: kirim — shu oy mijozlardan olingan to'lovlar, chiqim — haqiqatda to'langan pul (xarid,
  oylik, xarajat). BAJARILDI kech116 (4-bo'lim «Pul oqimi va kassa»).
- (kech114) «Loyiha qiymati» — buyurtmalardan: qiymat = loyiha buyurtmalari yig'indisi, qarz = buyurtmalar qarzi (byudjet
  maydoni kerak emas). BAJARILDI kech116 (4-bo'lim «Loyiha qiymati»).
- (kech116, zip 113 jonli ko'rilgach — «Chegirmaga qo'shilsin») MIJOZGA beriladigan hujjatlarda (yuk xati, hisob-kitob
  varaqasi, buyurtma nakladnoyi) «Kechirilgan qarz» so'zi chiqmaydi: to'lovda kechirilgan summa «Chegirma» qatoriga
  qo'shiladi, foiz yozilmaydi (narx chegirmasi foizi bilan chalkashmasin); buyurtma oynasida (ichki) alohida qator qoladi.
  BAJARILDI kech116 (zip 114; 4-bo'lim «Buyurtma pul hisobi qatorlari»).
- (kech114, 00:08) Gips — moliyadan BUTUNLAY olib tashlanadi; har yo'nalishning o'z foyda hisobi — «Ha, alohida»; yo'nalishlarni
  egasi o'zi nomlaydi va guruhlaydi (har mahsulot turi bittasiga; penoplast detallari — «Penoplast»); umumiy xarajatlar (ijara,
  svet, soliq, umumiy hodimlar) — daromad ulushiga qarab [BEKOR — kech118 15:23 qarori, pastda]; kassa — BITTA.
  Tafsilotlari (kech114 00:08, QAYTA SO'RALMAYDI): yo'nalishlar ro'yxati korxonaniki («Penoplast» — standart; korxona qo'shadi,
  nomini o'zgartiradi; ishlatilgani faqat yashiriladi); MRP turi yo'nalishi — UIda majburiy, mavjud turlarni egasi biriktiradi,
  biriktirilmagani — «Belgilanmagan» ogohlantirishi (avtomatik Penoplast EMAS); hodim / xarajat / transport / kirim — yo'nalish
  yoki «Umumiy»; daromad yo'q oy — teng (izoh bilan); yig'indi Moliya sof foydasiga tiyingacha teng. BAJARILDI kech117
  (zip 115; 4-bo'lim «Yo'nalishlar bo'yicha moliya»; G3-11, G6-09 shu ichida).
- (kech114) MRP tayyor mahsuloti sotuv narxi — «Hozirgidek qo'lda» (narx 0 qoladi, sotishda yoziladi; «Ombor qiymati» narxsiz
  partiyani tannarx bo'yicha qo'shadi).
- (kech87, 104) Xomashyo xaridida korxona to'lagan transport — to'langan oyning xarajati; mijozga yetkazishda
  korxona to'lagan transport — to'langan oyda sof foydadan ayriladi.
- (kech105, 2026-09-28, 9 va 50) "Toshkent vaqti bo'yicha": hisobotlarning kun / oy / yil chegaralari — Toshkent
  kalendari (kun 00:00 da almashadi); hamma hisobot va "Bugun" bir xil; o'tgan oylarda tungi (00:00–05:00) yozuvlar
  to'g'ri kun / oyga ko'chadi.
- (kech36) Ortgan loy (Tayyor loy) uchun minimal chegara shart emas — "kam qoldi" ogohlantirishiga kirmaydi.
- (kech108, 19-band / K108-2 "Ha, ko'rinsin") Minimal qoldig'i belgilanmagan (0) material TUGASA — bosh sahifa «Kam qolgan
  xomashyo» blokida ham ko'rinadi (qo'ng'iroqcha «qolmadi» va Omborxona «Kam qolganlar» bilan bir xil).
- (kech107, 10f "Har safar so'rasin") Kirim hujjatini bekor qilishda «hozir to'langan» to'lov — har safar tanlov:
  to'lovni ham o'chirish yoki ta'minotchida avans qolsin; ombor, o'rtacha narx, qo'shimcha xarajatlar — avtomatik orqaga.
- (2026-09-16) Joriy sovg'a davri ataylab yangi ustalar uchun (eski ustalar qatnashmaydi).

**Qolgan egasi qarorlari (kech118, 2026-09-30 — audit «Sizning qaroringiz kerak»; QAYTA SO'RALMAYDI; D bosqichida kodlanadi,
bajarilganlari belgilanadi)**
- Tungi rejim — «To'liq tuzatilsin» (hamma sahifa ranglari umumiy ranglar ro'yxatiga; U-02).
- Kassa — «Bitta: Kassa + bank»: karta nomi to'g'rilanadi (mijozning plastik / o'tkazma to'lovlari ham kiradi), boshlang'ich
  balans kiritilmagan bo'lsa ogohlantirish (G3-14). Naqd va bank alohida EMAS.
- Hodim paneli — «Oylik ko'rinsin»: shu oy hisoblangan / olingan / qoladi; avans so'rovini rad etishda SABAB MAJBURIY va
  panelda ko'rinadi (G6-21).
- Sahifalar vazifasi — «Vazifalar ajratilsin»: Bosh sahifa — bugungi holat va ogohlantirishlar; Dashboard — ish jarayoni;
  Hisobotlar — oylik tahlil; Loyiha — mijoz kartasi (pul xulosasi, buyurtmalar), Buyurtmalar — ish joyi; takror bloklar
  bittadan (G1-09, G2-17, G1-24).
- Rollar: «Usta» LOGIN roli olib tashlanadi (Ustalar ro'yxati, KPI, bonus, sovg'alar QOLADI); «Moliyachi» (hisobchi) roli
  ham olib tashlanadi (kerak bo'lsa keyin qayta); Omborchi qaytarish va brak YOZA OLADI (G2-05, G1-05, G5-03). O'lchov:
  `main` zaxirasida (28.09) foydalanuvchilar — admin + 2 Hodim; usta / moliyachi / omborchi login yo'q.
- Ishlab chiqarish: ikkalasi qoladi, nomi ajratiladi — Tayyor mahsulotlardagi eski oyna «Penoplast detal», yonida «Retsept
  bo'yicha» havola (G5-01); «Loy retseptlari» (menyu) va «Mahsulot tarkibi» (Ishlab chiqarish ichida) (G4-22); brak — BITTA
  «Brak yozish» oynasi (avval «brak qayerda chiqdi»; «Yangi qaytarish» — faqat mijozdan qaytgan butun mahsulot) (G5-04);
  brak SABABI (ro'yxatdan) MAJBURIY, bosqich / javobgar ixtiyoriy (G5-20).
- Nomlar lug'ati — taklif qilingani: «Ta'minotchi» (yetkazib beruvchi / hamkor / yetkazuvchi o'rniga); login roli «Menejer»
  (hozir «Hodim»), oylik oladigan ishchi — «Hodim»; hujjatlar — «Buyurtma hisobi», «Yuk xati № …», «Sotuv cheki № …»
  («NAKLADNOY» o'rniga) (U-12, G4-19, G6-11).
- Buyurtmasi bor loyihani o'chirish — TAQIQLANADI («Avval buyurtmalarni o'chiring») (G2-20).
- Tayyor mahsulot «Kam» chegarasi — har mahsulotga egasi o'zi yozadi; yozilmasa «Kam» ko'rsatilmaydi (G5-11).
- Sotishda partiya — qo'lda tanlash QOLADI (guruh qatoriga «Sotish» — texnik) (G5-12).

**Yangi qarorlar (kech118, 2026-09-30 15:16–15:30 — egasi o'zi yozdi, rasmlar bilan; tugmali javoblar; QAYTA SO'RALMAYDI)**
- YO'NALISHLAR BO'YICHA NATIJA: umumiy xarajatlar TAQSIMLANMAYDI (kech114 «daromad ulushiga qarab» BEKOR) — faqat «Jami»
  ustunida; oyliklar ALOHIDA blok (yo'nalishi belgilangan hodim — o'z ustunida, yo'nalishsizlari — faqat Jami da); xarajatlar
  alohida blok (o'ziniki ustunda, umumiy — Jami da); oxirida NATIJA +/−. Misol (tasdiqlangan): Penoplast 30 000 000 −
  15 000 000 − 10 000 000 − 2 000 000 = +3 000 000; Travertin +6 000 000; Jami 50 000 000 − 24 000 000 − 17 000 000
  (yo'nalishsiz 3 000 000 bilan) − 8 000 000 (umumiy 5 000 000 bilan) = +1 000 000. Joyi — MOLIYA sahifasida; qo'shimchalar —
  o'tgan davr bilan solishtirish, xarajatlar tarkibi doirasi, rentabellik chiziqlari, davr tanlash (hammasi). BAJARILDI kech118
  (zip 118; 4-bo'lim «Yo'nalishlar bo'yicha moliya»).
- ROLLAR VA RUXSATLAR (keyingi ish, zip 119+): admin o'zi rol yaratadi va boshqaradi; ruxsat — har bo'lim / amalda 4 belgi
  (Ko'rish, Yaratish, Tahrirlash, O'chirish) + bo'limni bir tugmada yoqish; «Tannarx va foydani ko'rish» — ALOHIDA ruxsat (yo'q
  bo'lsa hamma joyda, PDF da ham «—»); tayyor rollar — Admin (doim, to'liq, o'zgarmaydi), Menejer (hozirgi 2 «Hodim»
  foydalanuvchi, ruxsatlari hozirgidek), Omborchi, Moliyachi («Ishlab chiqarish» andozasi kerak emas). «Usta» login roli yo'q.
- Ish tartibi: zip 118 (B-2 + yo'nalishlar) → rollar (zip 119).

## 7. Ochiq masalalar

- **`main` o'lchovlari — BAJARILDI (kech108, egasi bergan JSON zaxira 2026-09-28 15:03 UTC, 43 jadval, lokal PG):**
  30+ chekka holat tekshiruvi — deyarli hammasi 0 (topilganlari: PRJ-033 `total_paid` 0 ↔ to'lovlar 2 560 000 — migratsiya
  tenglashtiradi; Penoplast 10P −0.06 (K108-2); Kirill 1 loyiha; retseptsiz 2 READY; "Tayyor loy" turkumi "Bazalt" —
  production'da `Boshqa → Bazalt` UPDATE ISHLAGAN, `main.py` izohidagi "hech qachon" da'vosi noto'g'ri, ko'rinishga ta'siri yo'q).
  O'TISH SIMULYATSIYASI (lokal nusxa): `saas_migration` W1–W6 + W2B / W3B / M1KOD — ✅, keyin staging kodi — 0 SQL xato,
  2-ishga tushish ma'lumotni o'zgartirmaydi; 93 hisobot solishtirildi — sentabr ishlab chiqarish xarajati 24 284 338 →
  20 268 362 (o'lchamsiz «dona»: eski kod tannarx = sotuv narxi), jami xarajat +750 000 (korxona to'lagan yetkazish
  transporti), sof foyda −12 278 563 → −9 012 587, brak kartasi 1 379 476 → 1 030 301; TENANT_FILTER=1 — AYNAN.
  **K108-1 (O'LCHANGAN):** SaaS to'lqinlarisiz `main` bazasida staging `main.py` IMPORTDA YIQILADI (`auth.create_default_admin` —
  `users.company_id` yo'q), undan oldin 5 migratsiya qisman bajariladi — ko'chirishda W1–W6 staging kodidan OLDIN
  bajarilishi SHART (texnik tartib — `main` bosqichida, egasi `main` ga o'zi hech narsa yuklamaydi). JSON zaxira sxemani
  (enum turlari) bermaydi — haqiqiy ko'chirishdan oldin Railway to'liq zaxirasi.
- **`main` ko'chirish MEXANIZMI — TAYYOR (kech109, K108-1):** `saas_otish.py` (4-bo'lim). `main` zaxirasining lokal nusxasida
  (HAQIQIY PG 16, staging kodi python3.12): bitta ishga tushish — to'lqinlar + migratsiyalar, 0 SQL xato, `/login` 200; ikkinchi
  ishga tushish — ma'lumot va sxema AYNAN; natija kech108 dagi ikki bosqichli usul bilan AYNAN (sxema — `pg_dump` farqi bo'sh,
  ma'lumot — vaqt tamg'alaridan tashqari); 93 hisobot kech108 KEYIN bilan AYNAN (farq faqat K108-2 — kam qolgan 0 → 1, va vaqt
  tamg'alari); `orders` ni boshqa ulanish ushlab tursa — SINOV W3 da "qulf band" bilan to'xtaydi, baza O'ZGARMAYDI, qayta
  ishga tushganda yakunlanadi.
- **`main` ga ko'chirish (keyingi bosqich).** Avval `production` ning to'liq zaxirasi (+ PITR), so'ng `main`
  bazasida faqat o'qish o'lchovlari (eski ma'lumotdagi chekka holatlar — topilganlari egasiga BIZNES savoli),
  keyin kod (to'lqinlar — `saas_otish.py`, birinchi ishga tushishda avtomatik; hech kim ishlamayotgan paytda — eski ilova
  o'tish paytida bir necha soniya yozishda xato berishi mumkin: to'lqinlardan keyin DEFAULT 1 olib tashlanadi).
  Ko'chirishdan keyin egasi: «Aloqa telefoni» ni yozadi (platforma), o'z logotipini (yuklagan bo'lsa) BIR MARTA qayta
  yuklaydi (eski `static/logos/` volume da emas edi — kech111).
  Ko'chirishda: `TENANT_FILTER=1`, korxona nomi, `enabled_categories`, `projects.total_paid` sinxron
  migratsiyasi (farqli loyihalarni oldin ko'rsatish). To'liq ro'yxat — oxirgi TOPSHIRIQ hujjatining 6-bo'limi.
  (kech105, K105-1) `main` da hozir `main.py` ning 2026-09-15 nusxasi ishlaydi (24.09 da zip 51 ning `main.py` si
  adashib `main` ga yuklangan, 1,5 daqiqadan keyin eski nusxa bilan almashtirilgan): ko'chirishgacha KPI → Sovg'a
  davri → «+ Qo'shish» 404; ma'lumotga zarar YO'Q (lokal PG simulyatsiyasi — `pg_dump` oldin = keyin).
  (kech105, K105-2 / K105-3) `main` o'lchovlariga (zaxira JSON): `is_penoplast` = true, lekin turkumi `Penoplast`
  emas materiallar (eski kod nomdan majburan belgilagan — masalan "… penoplast kleyi"); `is_penoplast` NULL soni;
  `Boshqa` / `Bazalt` turkumli materiallar; `produced_quantity` NULL li READY tayyor mahsulotlar (staging kodi
  ko'chirishda ularni birinchi marta to'ldiradi — hodim haqiga ta'sir).
  (kech105, 9 + 50 / K105-4) `main` o'lchoviga: har oy bo'yicha Toshkent 1-kun 00:00–05:00 dagi «Tayyor» / to'lov / xarajat
  (ko'chirishdan keyin o'tgan oylar raqami shuncha o'zgaradi — egasiga misol bilan); READY, lekin `completed_at` NULL
  buyurtmalar — bosh sahifa grafigidan chiqadi (oylik hisobot ularni allaqachon sanamaydi).
- **`staging` da ✅ belgisiz qolgan eski bandlar (oxirgi TOPSHIRIQ, 5-bo'lim) — `main` dan OLDIN ko'rib chiqiladi:** 9 va 50 —
  YOPILDI (kech105 zip 100 — hisobot chegaralari; kech106 zip 101 — ko'rinish: PDF, Telegram, sahifalar, brauzer
  standart sanalari va joriy oy — 4-bo'lim "Vaqt"); 10 — kech23 qoldiqlari: YOPILDI kech107 (loyiha tahririda muddat,
  hodim paneli avansi, UI 400 sabablari, o'lik usta shabloni, "Kirim hujjatini bekor qilish", Telegram — qaror "Boshqa
  bot"); lint baseline (108) TOIFALANDI (kech107, kod o'qish — A 9, B 84, C 12, E 3; natija — oxirgi TOPSHIRIQ):
  E-1, E-2, E-3 — TUZATILDI kech109 (E toifasi 0; baseline 106 — №14 lint ko'r nuqtasi edi, K107-3 da lint kengaytirildi);
  TENANT_FILTER=1 da `auth.create_user` band login 500 va Telegram «Sovg'alar» boshqa korxona ustasiga "faol davr
  yo'q" — TUZATILDI kech108 (K107-2, K107-1); 36, 49 — YOPILDI kech107; 26 — hujjat (qaytarishda `to_stock: false`
  faqat API, UI yubormaydi); 71 — YOPILDI kech108 (`main` ning 32 buyurtmasida tahrir → narx o'zgarmadi; `base_price` siz buyurtmada 0 ga
  tushish — endi ogohlantirish, «Bekor» — hech narsa o'zgarmaydi).
- **`main` o'lchoviga (kech107) — O'LCHANDI kech108:** `base_price` NULL va `price_per_m3` NULL detalli buyurtma — 0; brak
  kartasi 1 379 476 → 1 030 301 (egasiga ko'rsatildi).
- **SaaS / Telegram (kech107, 10g):** korxona sozlamasidagi bot — xabar YUBORADI, lekin usta menyusi (`/telegram/webhook`)
  faqat muhit boti (`TELEGRAM_BOT_TOKEN`) uchun ishlaydi.
- **Ko'p korxonali YAKUNIY jonli sinov — BAJARILDI (kech112, `sinov`):** C korxonada (yangi mijoz, bo'sh) TO'LIQ ish zanjiri
  (sozlama → ombor, rasm → ta'minotchi, kirim → qoplama retsepti → usta, hodim → loyiha → MRP: tur, retsept, 3 ishlab
  chiqarish → 3 buyurtma: profil qoplamali + panel, donali + loy sotish + MRP, qoralama → jarayonga → zaklat, yuk xatlari,
  to'lov → «Tayyor» → qaytarish + «Pulni qaytarish» → brak → tayyor mahsulot: sotuv, yo'qotish, ishlab chiqarish braki →
  xarajat, transport, ta'minotchiga to'lov, avans, oylik tuzatma, usta KPI, majburiyat → 6 PDF → 20 sahifa): 100 qadam — 0
  xato; jonli raqamlar lokal PG dagi aynan shu zanjir bilan AYNAN. Izolyatsiya: D → C 202, C → D 134, A (platforma admini)
  → C, D 228, C → A 199 (faqat o'qish) tekshiruv — 0 sizish. Zanjir 3 kamchilik topdi (K112-3 / 4 / 5 — 4-bo'lim). Qolgani
  (`main` dan oldin): korxona qo'shish (egasi, `/platforma`), dizayn. Sinovdagi eski MRP tayyor mahsulotlari (K112-5 dan oldin
  yaratilgan) `is_coated` = True bo'lib qoldi — tuzatilmaydi (sinov ma'lumoti; `main` da MRP ma'lumoti yo'q).
- **Admin paneli — BAJARILDI (kech111, zip 106; 4-bo'lim "Platforma — obuna va bloklash"):** kartochkalar, bloklash / ochish,
  obuna + uzaytirish, 30 kunlik sinov, eslatma (egasiga Telegram, mijozga yuqori panelda), 3 kundan keyin avtomatik bloklash,
  3 kunlik imtiyoz, aloqa telefoni, platforma raqamlari, hamma korxonalar xatolari, yuklangan fayllar himoyasi. Qolgani:
  `main` da (ko'chirishdan keyin) egasi «Aloqa telefoni» ni yozadi; mavjud mijoz bo'lsa — muddatini qo'yadi (hozir hamma
  mavjud korxona muddatsiz).
- **Yuklangan fayllar saqlash joyi (kech111):** Railway Volume `/app/static/uploads` — production `web-volume` TASDIQLANDI
  (egasi skrinshoti 2026-09-29; ~21.09 dan beri — 12.09 chizmasi undan oldin yo'qolgan, qaytmaydi). Sinov muhitida `web`
  xizmatiga volume ULANMAGAN (egasi skrinshoti 2026-09-29: yagona volume — `postgres-volume`, `/var/lib/postgresql/data`) —
  sinovga yuklangan fayllar har deployda o'chadi; sinov uchun maqbul (qaror: qo'shilmaydi). Shu sababli sinovda "fayl deploydan
  keyin saqlandi" ni tekshirib bo'lmaydi — deploydan keyin eski rasm 404 bo'lishi XATO EMAS; himoya yangi yuklangan fayl bilan
  tekshiriladi. Eski kod logotipni volume dan TASHQARIGA (`static/logos/`) yozgan — production da har deployda o'chgan
  (`company_logo_of` fayl yo'q bo'lsa `None` qaytaradi — sahifa buzilmaydi); yangi kod `static/uploads/logos/` ga yozadi.
- **Egasi hal qiladi:** brak mahsulotning keyingi taqdiri (chiqindi / tuzatildi / qayta ishlatildi / 2-nav);
  SaaS uchun alohida brend nomi, narx tariflari, mijoz bilan shartnoma (ma'lumot egaligi).
- **Rus tili (i18n)** — `main` ko'chirishidan KEYIN (qaror kech104); kodda hali yo'q (faqat Kirill ↔ Lotin), 25 sahifaga tegadi.
- **Texnik qarz (ma'lum):** `orders.notes` ichidagi `[WRITEOFF:…]` (qarz kechirilgan) va `[OVERPAID:…]` belgilari
  (alohida ustun emas); tizim tekshiruvida eski `[GISHT:` izoh belgisini sanash qoldig'i; `saas_migration.py` —
  `main` migratsiyasidan keyin olib tashlanadi (Python 3.12 sintaksisi).

## 8. Texnik saboqlar (qayta qilmang)

- `with_for_update()` bilan qulflanadigan modelga `lazy="joined"` — PG da `FOR UPDATE cannot be applied to the
  nullable side of an outer join` (500).
- FastAPI sync bog'liqliklari threadpool'da — `contextvars` so'rov holatini yo'qotadi; holat sessiya obyektiga
  (`Session.info`) bog'lanadi.
- Veb so'rov ichidan `ALTER TABLE` o'z so'rovining ochiq tranzaksiyasi bilan tiqilib, butun saytni to'xtatgan —
  migratsiya oldidan sessiyani `rollback` / `close`, `lock_timeout`.
- Modelga `company_id` qo'shilsa SQLAlchemy INSERT da aniq NULL yuboradi — bazadagi `DEFAULT` ishlamaydi.
- `ORDER BY` siz "birinchi" yozuv PG da tartibsiz (SQLite da rowid) — K103-6.
- Ko'rsatish uchun yaxlitlangan qiymatni hisobga qaytarish — narx siljishi (Donalik "Kelishilgan summa").
- Formula nusxalanmaydi — mavjud funksiya chaqiriladi (foyda / hajm formulalarining ajralishi ko'p nuqson bergan).
- Migratsiya "bajarildi" deyishdan oldin deploy logini o'qing (`name 'text' is not defined` bir necha deploy jim
  yiqilgan).
- GitHub'ga yuklashda fayl ildizga tushishi yoki eski nusxa qayta yuklanishi mumkin — yuklangandan keyin DOIM
  klon + MD5.
- Shablondagi tugma o'chirilgan marshrutni chaqirib qolgan (K104-1, 404) — `tools/test_pasport.py` B bo'limi
  endi har `/api/` havolasini tekshiradi.
- `extract('month', ustun)` va `datetime(yil, oy, 1)` oralig'i UTC oyini oladi (Toshkent vaqti bilan 1-kun 00:00–05:00
  dagi amal oldingi oyga tushardi) — Toshkent oyi uchun `database.tashkent_oyida`. Testda ham "joriy yil / oy / kun"
  `datetime.utcnow()` dan EMAS, Toshkent devor soatidan (UTC + 5) — aks holda Toshkent 00:00–05:00 da SOXTA yiqilish
  (kech105 vaqt sayohati o'lchovi; endi `tools/vaqt_sayohati.sh` — TZ=UTC va TZ=Asia/Tashkent, 4 payt).
- «Bir martalik» deb yozilgan ishga tushish UPDATE si shartsiz bo'lsa — HAR deployda ishlaydi va foydalanuvchi
  tanlovini jimgina qayta yozadi (K105-2 `'Boshqa'` → `'Bazalt'`, K105-3 nomdan penoplast belgisi; K42-1
  `agreed_amount = 0` — xuddi shu sinf). Tekshiruv: material yaratib, serverni QAYTA ishga tushirib solishtirish.
- GitHub'da yuklashdan OLDIN shox (branch) nomini tekshiring: 2026-09-24 da zip 51 ning `main.py` si `main` ga
  tushgan, keyin `main` ga eski (15-sentabr) nusxa yuklangan (K105-1) — `main` tarixini ham `git log` bilan kuzating.
- Brauzerda `new Date("2026-09-30T20:30:00")` (zona belgisiz) — MAHALLIY vaqt (Toshkent kompyuterida 5 soat orqada),
  `new Date().toISOString().slice(0, 10)` — UTC sanasi (Toshkent 00:00–05:00 da KECHA), mahalliy oy boshi
  `new Date(y, m, 1).toISOString()` — UTC+ mintaqada OLDINGI kun (kech106: brak xulosasi "shu oy" oldingi oyning oxirgi
  kunidan boshlanardi).
  Ko'rinishni o'lchash — HAQIQIY brauzerda (Playwright: `timezone_id`, `page.clock.set_fixed_time`), kamida 3 mintaqada.
- Testda modul `datetime` sinfini almashtirish ("hozir" simulyatsiyasi) shu moduldagi `isinstance(x, datetime)` ni aldaydi —
  tur tekshiruvi HAQIQIY sinf bilan (`import datetime as _dt_modul`; kech106 `database.tashkent_vaqt`).
- Shablon funksiyasini vm / node da yurgizadigan eski testlar yangi umumiy yordamchi (`base.html`) chaqirilganda
  "is not defined" bilan yiqiladi — kontekstga o'sha yordamchilarni yuklang (kech106: 5 test moslandi).
- Testdagi muzlatish (masalan K81-1 — PDF "hozir") VAQT MANBAI bilan birga ko'chishi shart: kech106 da PDF modullari
  `datetime` o'rniga `database.tashkent_vaqt` ga o'tgach `tools/test_hisobot_korxona.py` muzlatishi jimgina ishlamay
  qoldi (daqiqa chegarasida S1 yiqilardi — vaqt sayohati bilan O'LCHANDI) — endi S6 deterministik tekshiradi.
- ReportLab standart shriftlari (Helvetica, Times, Courier — Type1, WinAnsi) Kirill / "№" / emoji ni ■ qiladi; PDF ni
  HAQIQIY chizib (`pdftoppm`) ko'ring. `registerFont` nom band bo'lsa TTF ni JIM o'tkazib yuboradi va har TTF uchun
  o'z "oilasi"ni yozib `<b>` / `<i>` ni buzadi (`pdf_shrift.py` ikkalasini tuzatadi). PDF oqimini o'qishda Flate ikkilik
  ma'lumotini `strip()` qilmang — `/Length` bo'yicha kesing (oqim bo'shliq baytida tugashi mumkin).
- "Jami" va uning "tafsiloti" ALOHIDA hisoblansa, albatta ajraladi (K106-2: PDF jadvali tranzaksiyalarni qayta sanab,
  asosiy turkumlarni ikki marta chiqardi, transportni tushirib qoldirdi — qatorlar 5 251 550, JAMI 3 151 600): ro'yxatni
  jami bilan BIR manbadan quring va "qatorlar yig'indisi = jami" xossasini boy fiksturada tekshiring.
- ReportLab `Paragraph` ga foydalanuvchi matnini xom bermang (`<` — belgilash, PDF 500); bir modulda tuzatilgan
  qattiq qiymat (2026-09-20 — "PenoDecorPro" brendi) boshqa modullarda QOLGAN bo'lishi mumkin — butun turni qidiring
  (K106-4: 6 sarlavha).
- PDF o'quvchi (testlarda, kutubxonasiz): ASCII85 tugatuvchisi `~>` ni FAQAT bir marta olib tashlang (`rstrip(b"~>")`
  ma'lumotning oxirgi ">" ini ham o'chiradi — ~1–2 % oqim; kontent vaqtga bog'liq bo'lgani uchun vaqt sayohatida
  TASODIFAN yiqildi); `BT … ET` bloklarini TOKENLAB ajrating (satr ichidagi "ET" — "YETKAZISH" — `BT(.*?)ET` ni
  uzadi, qator jim tashlanadi). Har PDF o'quvchili testda o'quvchining o'zi uchun sun'iy PDF nazorati bor.
- SQLite eng katta id li qator o'chirilsa, o'sha id ni QAYTA beradi (PG ketma-ketligi bermaydi): izohdagi "#N" bo'yicha
  bog'lash ishonchsiz (kech107: bekor qilingan kirimning avans to'lovi izohi "Kirim to'lovi — #N" bilan boshlanmaydi).
- FastAPI `Form(...)` bo'sh maydonni 422 (pydantic RO'YXATI) qiladi — sahifa "[object Object]" ko'rsatadi: matn maydoni
  `Optional[str] = Form(None)` + o'z tekshiruvi (400, tushunarli matn).
- Mutatsiya faqat STATIK tekshiruv bilan ushlansa — xulq tekshiruvini qo'shing (kech107: 8 ta UI joyi faqat statik ushlanardi;
  bitta holatning ikki yurgizishi soxta DOM elementlarini bo'lishsa — birinchi natija ustiga yozilardi).
- Bir raqamning uch ta'rifi (karta / Moliya / tahlil) — BITTA funksiyaga (49-band): ta'rif har joyda qayta yozilsa, ajraladi.
- `main` (production) zaxirasi — HAQIQIY foydalanish naqshlarini beradi: har buyurtmani haqiqiy brauzerda tahrir → saqlash
  (kech108 `work/probe108u71.py`) sintetik fiksturada ko'rinmagan K108-3 ni topdi (topshirila boshlagan buyurtma). O'tish
  simulyatsiyasi (lokal nusxa, SaaS to'lqinlari + yangi kod + hisobotlar oldin ↔ keyin) — egasiga raqamlar bilan tushuntirish uchun.
- Konteyner ichidagi `innerHTML = …` konteyner ichidagi `id` li bolani O'CHIRADI — keyingi `getElementById(...).textContent`
  TypeError (K108-3). Ogohlantirish — alohida bola elementga; o'rnatish — null-xavfsiz; forma qayta ochilganda tiklansin.
- TENANT_FILTER=1: butun tizim bo'yicha YAGONA ustun (login) bandligini tekshirish — tizim so'rovi (`skip_tenant_filter`),
  aks holda boshqa korxonadagi qiymat ko'rinmaydi va INSERT 500 beradi (K107-2).
- TENANT_FILTER=1 da FK bog'lamini uzish uchun ORM bilan YUKLAB o'zgartirish ishlamaydi — begona yozuv so'rovga ko'rinmaydi
  va bog'lam qoladi (PG FK — 500); FK uzish — bulk UPDATE (filtr faqat SELECT ga qo'yiladi) (E-1).
- Bog'liq migratsiya qadamlarining dry-run'i alohida-alohida o'tmaydi (W2B — "avval W2 ni bajaring"): butun zanjirni BITTA
  tranzaksiyada savepoint'lar bilan yurgizib, oxirida qaytaring (`saas_otish._SinovMotori`) — keyingi qadam oldingisini ko'radi.
- PostgreSQL da id ni ANIQ yozish (`Company(id=1, …)`) ketma-ketlikni surmaydi — keyingi avtomatik id takrorlanadi (K109-3);
  aniq id dan keyin `setval(pg_get_serial_sequence(…), MAX(id))`.
- Tahrir formasi "o'zgarmagan" qiymatni ham yuborsa, server uni "qo'lda kiritilgan" deb qabul qiladi va o'z qoidasini
  qo'llamaydi (K110-1): yuborishni foydalanuvchi haqiqatda yozganiga bog'lang, qolganini serverning yagona qoidasi hal qilsin.
- Nisbatni float bilan hisoblash (`yangi × P / eski`) .5 chegarasida 1 so'mga adashadi (736 334.90 / 368 167.45, 1 022 239 →
  511 119, aniq 511 120) — pul nisbatlari butun tiyinlarda (int / BigInt) (K110-1).
- (kech111) Aniq yo'lli himoyalangan marshrut (`/static/uploads/{papka}/{fayl}`) umumiy `StaticFiles` mount dan OLDIN tursa
  ham yetmaydi: marshrutga mos kelmagan yo'l (`%2E`, `//`, qo'shimcha bo'lak) mount ga tushadi va u faylni normallashtirib LOGINSIZ
  beradi — mount ning o'zida HAQIQIY yo'l (realpath) bo'yicha rad etish kerak.
- (kech111) Kontent oqimiga (`{% block content %}` ustiga) qo'shilgan qator ko'p sahifani buzadi: ular `height: calc(100vh - 58px)`
  bilan qurilgan va `.erp-main` `overflow: hidden` — pastki qismi ko'rinmay qoladi. Umumiy ogohlantirish — yuqori panelda.
- (kech111, K112-1) Ochiluvchi panelni tugmaning o'ng chetiga (`right: 0`) bog'lash tor ekranda panelni ekrandan chiqarib
  yuboradi (tugmalar qatori keyingi qatorga, chapga o'tadi) — keng ekrandagi skrinshot buni ko'rsatmaydi; ochilganda ekran
  ichiga joylang va HAQIQIY brauzerda bir necha kenglikda (360 / 390 / 600 / 756 / 1024 / 1400) panel to'rtburchagini o'lchang.
- (kech111, K112-2) "Darhol ta'sir" uchun sessiyani oldindan o'chirish foydalanuvchidan SABABNI yashiradi (keyingi so'rov oddiy
  "kiring" bo'lib qoladi). Har so'rovda tekshiruv bo'lsa — sessiyani o'sha yerda, sabab bilan yoping. Testda faqat "kirish
  yopildimi" emas, "foydalanuvchi NIMA ko'rdi" ni ham tekshiring (manzil `?b=1`, xabar, telefon).
- (kech111) Loginsiz jonli so'rovni `cache: 'no-store'` bilan yuboring — aks holda brauzer oldingi sessiyali (private) javobni
  keshdan beradi va himoya ishlamayotgandek ko'rinadi.
- (kech111) Testda sahifa matnini tekshirishda Jinja `'` ni `&#39;` qiladi (`to'xtatilgan`) — HTML dan oldin `html.unescape`.
  `<script>` ichiga JSON qo'yilsa `</script>` bo'lagi skriptni yopadi — `<` → `\u003c`.
- Tugmani CSS sinfining BIRINCHISI bilan topish (`querySelector('.btn-outline')`) — sahifaga boshqa shunday tugma qo'shilganda
  jimgina boshqasini topadi (K109-1, iyundan beri); tugmaga `id`.
- (kech112) Yangi (bo'sh) korxonada TO'LIQ ish zanjiri — eng samarali jonli sinov: bir JS skript (`work/k112z/zanjir_c.js`)
  avval lokal (Playwright + uvicorn, PG + TF1, platforma orqali yaratilgan korxona), so'ng jonli yuriladi va raqamlar
  solishtiriladi (AYNAN bo'lishi shart) — 3 ta yangi kamchilik shu yo'l bilan topildi. Profil yetkazish miqdori — METR
  (`/delivery-status` `remaining`), `quantity` emas: 1 yuborilsa «Tayyor» buyurtmani 1 m ga "yakunlaydi".
- (kech112) Sizish skriptini egasining O'Z korxonasi (A) ga qarshi yurgizganda — faqat o'qish (`faqat_oqish`); yozish
  urinishlari D ↔ C da (sinov korxonalari) tekshiriladi. Sizish skriptini hech qachon egasi korxonaning o'z sessiyasida
  o'z ID lari bilan yurgizmang (o'zgartirish urinishlari HAQIQATAN bajariladi).
- (kech112) Claude in Chrome `javascript_tool`: `(async () => …)()` natijasi `{}` qaytadi — yuqori darajadagi `await` yozing.
  Ichki brauzer `read_console_messages` navigatsiyada tozalanmaydi (oldingi fetch 404 lari ham ko'rinadi) — `pattern`
  ("Uncaught", "Error") bilan o'qing.
- (kech113) SQLite da vaqtni XOM SQL bilan yozish ORM saqlagan matn shaklidan farq qiladi (`'…19:00:00'` va
  `'…19:00:00.000000'` — matn solishtiruvida birinchisi kichik): vaqt chegarasi testida sanani ORM orqali yozing, aks holda
  aniq chegaradagi yozuv noto'g'ri oyga tushgandek ko'rinadi.
- (kech113) Oldindan ko'rsatiladigan hisob (reja, taxminiy tannarx) — alohida formula EMAS, amalning o'z funksiyalari
  (yordamchiga ajratib, ikkala joydan chaqiriladi); test — "reja = amal" (AYNAN xabar, AYNAN tannarx, «mumkin» ⇔ o'tadi).
- (kech114) Dizaynni o'lchashda HAQIQIY xato topildi (K114-1): sahifadagi tugma boshqa bo'limning amalini chetlab o'tardi.
  Yangi tugma / havola qo'shilganda — u qaysi server amalini chaqirishini va o'sha amal boshqa bo'limning qoidasini
  (xomashyo, tannarx) chetlab o'tmasligini tekshiring. Jadval / ro'yxat test ID lari bir-biriga TENG chiqmasin (masalan,
  ishlab chiqarish va TM raqamlari 1, 2, 3 — test ularni farqlay olmaydi; oldindan qoralama yaratib siljiting).
- (kech114) `obuna.kunlik_tekshiruv` eslatma bosqichlari — 7 kun / 1 kun / tugadi / bloklandi («3 kun» bosqichi YO'Q);
  sinovda Telegram o'chiq — eslatma kelmasligi kutilgan. `_send_telegram` token yo'q bo'lsa istisno bermaydi — natijada
  `yuborildi: true` (faqat jurnal ma'lumoti).

- (kech115) jsdom ssenariysida sahifaning FON so'rovlari (ta'minotchi tanlanganda material filtri ro'yxatni qayta chizadi)
  keyingi qadamdan KEYIN tugasa, tanlangan qiymat jimgina birinchi variantga qaytadi — tanlovni `amal` ichida qiling (tarmoq
  tinchishini kutadi), `natija` da emas. Chart.js (CDN) jsdom da yuklanmaydi va `base.html` o'rovchisi `window.Chart` ni
  ushlaydi — soxta konstruktorni `beforeParse` da emas, resurs yuklovchi orqali CDN manzili o'rnida bering.
- (kech115) Sahifadagi so'rov hisoblagichi URL prefiksi bilan (`/api/orders`) boshqa marshrutlarni ham sanaydi
  (`/api/orders/5/ready`) — aniq yo'l yoki `?` bilan solishtiring.
- (kech116) `uvicorn --proxy-headers --forwarded-allow-ips='*'` (0.30.6) `X-Forwarded-For` ning ENG CHAP (mijoz yozadigan)
  manzilini oladi — IP cheklovini soxta sarlavha bilan aylanib o'tish mumkin; haqiqiy IP — `auth.mijoz_ip` (O'LCHANGAN manba kodi).
  Testda IP bo'yicha cheklov hisoblari aralashmasin — `TestClient(..., client=(ip, port))` (har bo'lim o'z manzili).
- (kech116) Sahifa `toLocaleString('ru-RU')` bo'shlig'i — NBSP (U+00A0); jsdom `textContent` ni `\s+` bilan normallashtirsangiz,
  kutilgan satrni ham normallashtiring (aks holda «1 565 000» ≠ «1 565 000»).
- (kech116) Eski test ma'lum formulani matn sifatida tekshirsa (`test_naqd_kassa` H5 — bosh sahifa «Chiqim» formulasi) va egasi
  qarori formulani o'zgartirsa — test yangi qarorga MOSLANADI (izoh bilan), eski formulani saqlash uchun kod o'zgartirilmaydi.
- (kech116) Testdagi uvicorn (`uvicorn.Config` standarti — `proxy_headers=True`, 127.0.0.1 ga ishonadi) ulanish 127.0.0.1
  bo'lganda `X-Forwarded-For` ni O'ZI almashtiradi — `request.client.host` ga qaytgan kod ham testda «to'g'ri» IP ko'rsatadi
  (mutatsiya ushlanmadi). Jonlida (Railway, proksi 100.64.x — uvicorn ishonmaydi) almashtirish yo'q — testda
  `proxy_headers=False` (jonlidagi kabi).
- (kech116) Python `max(-0.0, 0.0)` → `-0.0` (teng qiymatlarda BIRINCHISI qaytadi) — JSON da «-0.0»; pul qiymatini ishora
  sharti bilan (`x if x > 0 else 0.0`) yoki `pul_tiyin` bilan chiqaring. Jinja `{{ float }}` — «220000.0», `Numeric` ustuni —
  «220000.00»: `data-*` atributlari `'%.2f'|format(...)` bilan (eski testlar va JS `parseFloat` uchun bir xil).
- (kech117) Umumiy summani ustunlarga bo'lib, har ustunni ALOHIDA yaxlitlash yig'indini 1–2 so'mga buzadi (va ustun ichida
  D − T − J ≠ S). To'g'risi: har qator (daromad, tannarx, bevosita, sof foyda) — eng katta qoldiq usulida jamiga teng
  (`services._yaxlit_taqsim`), ulush esa AYIRMA (D − T − B − S) — ustun identifikatori o'z-o'zidan saqlanadi.
- (kech117) Test `check(..., detail)` ning `detail` argumenti ham HAR DOIM hisoblanadi — asl kodda (yangi kalit yo'q)
  `SPB["yonalishlar"]` kabi to'g'ridan-to'g'ri kalit testni QULATADI (yiqilish o'rniga). `detail` da ham `.get()`.
- (kech117) UIda yangi MAJBURIY maydon (masalan MRP turi yo'nalishi) eski UI testlarida «saqlash» ni jim to'xtatadi (so'rov
  ketmaydi — test boshqa sabab bilan yiqiladi): ssenariyga tanlovni qo'shing (asl kodda maydon yo'q bo'lsa — o'tkazib yuboring).
  Sahifadan olib, alohida yuklanadigan funksiya (harness `olib(...)`) yangi yordamchini chaqirsa — ro'yxatga o'sha yordamchini ham.
- (kech117) Ichki brauzer paneli (Claude_Browser): sahifaga o'tgandan keyingi BIRINCHI sichqoncha bosishi ko'pincha
  yo'qoladi va skrinshot 1–2 soniya kechikadi — bosishdan keyin natijani DOM / tarmoq so'rovlari bilan tekshiring
  (`read_network_requests`), skrinshotga ishonmang; tugma ko'rinmasa (gorizontal aylantiriladigan jadval) — element `.click()`.
- (kech117) PDF `Paragraph` darvozasi (`test_pdf_matn` C2) f-satrdagi `_x(...)` chaqiruvini taniydi, `"..." + _x(...)`
  qo'shishni tanimaydi — foydalanuvchi matnini f-satr ichida `_x(...)` bilan bering; son ko'rinishlari — TIZIM ro'yxatiga.
- (kech118) jsdom tashqi uslub faylini (`<link>` — `style.css`) sahifaning `<style>` bloklaridan KEYIN kaskadga qo'shadi
  (brauzerda — hujjat tartibida): `style.css` dagi `.modal-overlay{display:flex}` sahifaning `display:none` i ustidan yozilib,
  YOPIQ oynalar jsdom da «ochiq» hisoblanadi. Oyna ko'rinishini jsdom da tekshiruvchi test `style.css` ni yuklamasin (inline /
  sahifa uslublari yetarli) yoki natijani HAQIQIY brauzerda o'lchang.
- (kech118) Har `input` / `change` hodisasida ishlaydigan global tinglovchida `getComputedStyle` (ajdodlar zanjiri) — jsdom da
  juda sekin (katta uslub fayli bilan har chaqiruv millisekundlar): eski test ssenariysi 5 s dan uzoq cho'zilib, test serverining
  keep-alive ulanishi yopilgan paytga to'g'ri kelgan POST «fetch failed / other side closed» bo'ldi (test_ochirilgan_tur B0a).
  Tez-tez hodisada — faqat arzon tekshiruv (inline uslub, klass, atribut); hisoblangan uslub — kam uchraydigan hodisada (Esc).
- (kech118) Xom `alert` sahifani to'xtatadi — undan KEYINGI `location.reload()` xabar yopilgach bajarilardi. Dastur oynasi
  to'xtatmaydi: shunday joyda `await xabarOyna(...)` (aks holda xabar ko'rinmay qoladi).
- (kech118) `toLocaleDateString('uz')` brauzerga bog'liq: node — «01/10/2026», Chromium (audit) — «2026-09-29» va oy nomi bilan
  «2026 M09 29». O'zbekcha ko'rinishni brauzer tiliga TOPSHIRMANG — qo'lda yozing (tk yordamchilari); testda kutilgan qiymat —
  aniq matn, `toLocale…('uz')` natijasi emas.
- (kech118) `toLocaleString('ru-RU')` ming ajratgichi — oddiy bo'sh joy EMAS, NBSP (U+00A0): matnni solishtiruvchi test
  kutilgan qiymatda ham NBSP yozsin yoki ikkalasini bir xil ko'rinishga keltirsin.
- (kech118) Testlar sahifa funksiyalarini NOMI bo'yicha kesib oladi (`olib(src, 'funksiya')`) — `base.html` ga yangi global
  `const` / yordamchi qo'shilsa, uni chaqiruvchi sahifa funksiyasi soxta muhitda «X is not defined» bilan yiqiladi (platforma,
  toshkent testlari). Yordamchini ichki (mahalliy) massiv bilan yozing; yangi global funksiya qo'shilsa — testlarning yordamchi
  ro'yxatiga (TK_FUNKS / TK_NOMLAR / tk) qo'shing.
- (kech118) Umumiy rang o'zgaruvchisini (`--text3`) och fon uchun to'qlashtirish QORONG'I kartadagi yozuvni o'qib bo'lmaydigan qildi
  (Moliya «Kassa balansi»: #696D78 gradient #111827 ustida — 2.8:1). Audit fon rangini ajdodlarning `background-color` idan olardi —
  gradient (`background-image`) ko'rinmasdi. Kontrast o'lchovi gradient to'xtashlarini ham olsin (eng yomoni bilan), rangni almashtirgach
  qorong'i joylarni alohida tekshiring.
- (kech118) HAQIQIY server + jsdom testlari (masalan `test_mrp_sahifa_ui`) bir vaqtda 2 yadroda etalon + audit + regress yurganda
  «fetch failed» bilan yiqilishi mumkin (keep-alive / vaqt); yolg'iz qayta yurgizilganda o'tdi. Yiqilishni «yuk» deb yozishdan oldin
  — yolg'iz qayta yurgizing.

## 9. Xarita (AVTOMATIK)

Quyidagi bloklar `python3 tools/pasport_xarita.py --yoz` bilan KODDAN yasaladi — qo'lda tahrirlamang.
`tools/test_pasport.py` ular kod bilan AYNAN ekanini tekshiradi.

### 9.1 Muhit o'zgaruvchilari

<!-- AVTO:MUHIT BOSHI — qo'lda tahrirlamang: python3 tools/pasport_xarita.py --yoz -->
Kod o'qiydigan muhit o'zgaruvchilari (Railway → Variables). Ro'yxat `os.getenv` / `os.environ` dan olingan.

- `ADMIN_PASSWORD` — `auth.py`
- `BACKUP_TELEGRAM_CHAT_ID` — `main.py`
- `CRON_SECRET` — `main.py`
- `DATABASE_URL` — `database.py`
- `QOPLAMACHI_TELEGRAM_CHAT_ID` — `main.py`
- `RAILWAY_ENVIRONMENT` — `saas_migration.py`
- `RAILWAY_ENVIRONMENT_NAME` — `saas_migration.py`
- `RAILWAY_PUBLIC_DOMAIN` — `saas_migration.py`
- `RAILWAY_SERVICE_NAME` — `saas_migration.py`
- `RESET_ADMIN_PASSWORD` — `auth.py`
- `TELEGRAM_BOT_TOKEN` — `main.py`
- `TELEGRAM_WEBHOOK_SECRET` — `main.py`
- `TENANT_FILTER` — `tenant_context.py`
<!-- AVTO:MUHIT OXIRI -->

### 9.2 Ishga tushish tartibi (migratsiyalar)

<!-- AVTO:ISHGA_TUSHISH BOSHI — qo'lda tahrirlamang: python3 tools/pasport_xarita.py --yoz -->
`main.py` import qilinganda (server ishga tushganda, `app = FastAPI(...)` dan OLDIN va keyin) modul darajasida
bajariladigan chaqiruvlar — AYNAN shu tartibda. `_migrate_*` — idempotent sxema / ma'lumot migratsiyalari
(Alembic YO'Q). Yangi migratsiya shu ro'yxat oxiriga qo'shiladi.

1. `_saas_otish.startup_otish`
2. `init_database`
3. `_seed_default_company` — 2026-09-16: yangi Production moduli uchun — SaaS'gacha ishlatiladigan YAGONA korxona yozuvini (id=1) bir marta yaratib qo'yadi. Xatoni boshqa init funksiyalari kabi yuti…
4. `_seed_tg_tagline` — 2026-09-21: ustaga salomdagi shior endi sozlama (`tg_welcome_tagline`).
5. `_migrate_recipe_name_column` — ESKI QOLDIQ TUZATISH: bazada "recipes.name" ustuni, hozir kodda umuman mavjud bo'lmagan "recipetype" maxsus (enum) turi sifatida qolib ketgan edi (eski, allaqachon o'zga…
6. `_migrate_payment_columns` — Mavjud bazaga to'lov ustunlarini qo'shadi (agar yo'q bo'lsa).
7. `_migrate_drop_company_id_defaults` — M8/F1 (2026-09-18) — VAQTINCHALIK `DEFAULT 1` ni olib tashlaydi.
8. `_migrate_faza3_columns` — Faza 3 (2026-09-19) — uchta yangi ustun. Xavfsiz va idempotent.
9. `_migrate_float_to_numeric` — Bosqich 1 (2026-09-20) — to'rtta pul maydoni `Float` dan `Numeric(12,2)` ga o'tkaziladi.
10. `_migrate_fp_product_type` — Bosqich 3, 10-band (2026-09-20) — `finished_products.product_type_id`.
11. `_migrate_return_order_item` — kech39 (5-bo'lim 3-band) — `return_items.order_item_id`.
12. `_migrate_qaytarish_orqaga` — kech40 (5-bo'lim 22-band + K40-1) — IDEMPOTENT, PostgreSQL va SQLite.
13. `_migrate_brak_harakat` — kech45 (13-band, 6-qadam) — IDEMPOTENT, PostgreSQL va SQLite.
14. `_migrate_harakat_narx` — kech46 (13-band, 2-qadam) — IDEMPOTENT, PostgreSQL va SQLite.
15. `_migrate_eski_buyurtma_narxi` — kech49 (5-bo'lim 33-band) — IDEMPOTENT, PostgreSQL va SQLite.
16. `_migrate_eski_brak_narxi` — kech51 (5-bo'lim 37-band) — IDEMPOTENT, PostgreSQL va SQLite.
17. `_migrate_brak_belgisi` — kech52 (13-band, 3-qadam) — IDEMPOTENT, PostgreSQL va SQLite.
18. `_migrate_brak_sabab_javobgar` — kech56 (13-band, 7-qadam) — IDEMPOTENT, PostgreSQL va SQLite.
19. `_migrate_qoplama_retsept` — kech58 (K58-1 / K58-2 / K58-3, 43-band) — IDEMPOTENT, PostgreSQL va SQLite.
20. `_migrate_tm_birlik_tannarx` — kech59 (47-band, K59-1 / K59-2 / K59-4) — IDEMPOTENT, PostgreSQL va SQLite.
21. `_migrate_tm_detal_tannarx` — kech103 (5-bo'lim 56-band) — IDEMPOTENT, PostgreSQL va SQLite.
22. `_migrate_ortiqcha_qaytarish` — kech60 (57-band, K59-3) — IDEMPOTENT, PostgreSQL va SQLite.
23. `_migrate_buyurtma_raqam_hisoblagich` — kech86 (100-band, QAROR "A" — buyurtma raqami hech qachon qayta berilmaydi) — IDEMPOTENT, PG va SQLite.
24. `_migrate_kirim_tannarx_manba` — kech87 (104-band) — IDEMPOTENT, PG va SQLite.
25. `_migrate_kechirilgan_qarz` — kech110 (K110-1, egasi QARORI "Kechirilgan so'mda qolsin") — IDEMPOTENT, PG va SQLite.
26. `_migrate_platforma_obuna` — kech111 (admin paneli — egasi QARORLARI kech109 / kech110 / kech111) — IDEMPOTENT, PG va SQLite.
27. `_migrate_yonalishlar` — kech117 (A2 — YO'NALISHLAR BO'YICHA MOLIYA; egasi QARORLARI kech114 00:08) — IDEMPOTENT, PG va SQLite.
28. `auth.create_default_admin`
29. `crud.backfill_employee_compensation_history`
30. `_migrate_loyiha_tolangan_sinxron` — 17c (2026-09-21): `projects.total_paid` ni HAQIQIY to'lovlar bilan bir marta tenglashtiradi.
31. `app.include_router(production_router)`
32. `app.include_router(saas_migration_router)`
33. `_yuklama_marshrutini_oldinga`
34. `_scheduler.add_job`
35. `_scheduler.add_job`
36. `_scheduler.start`
<!-- AVTO:ISHGA_TUSHISH OXIRI -->

### 9.3 Sahifalar: URL → handler → shablon → API

<!-- AVTO:SAHIFALAR BOSHI — qo'lda tahrirlamang: python3 tools/pasport_xarita.py --yoz -->
Har sahifa: URL → handler → shablon → qorovul (ruxsat), so'ng shablon JavaScript'i chaqiradigan API yo'llari
(matndan statik olingan; `{}` — o'zgaruvchan qism). ⚠ — hech bir marshrutga mos kelmagan yo'l (o'lik havola bo'lishi mumkin).
`base.html` (hamma sahifada): `/api/notifications`

### `GET /` → `main.py:home` → `templates/home.html`
- Qorovul: — (tanada tekshiriladi yoki ochiq)
- Server chaqiruvlari: auth.get_current_user
- `home.html` API: `/api/dashboard/charts`, `/api/dashboard/stats`, `/api/orders`

### `GET /dashboard` → `main.py:dashboard_page` → `templates/dashboard.html`
- Qorovul: auth.admin_or_financier
- Server chaqiruvlari: auth.company_id_of, services.get_dashboard_stats
- `dashboard.html` API: `/api/admin/advance-requests/{}/confirm`, `/api/admin/advance-requests/{}/reject`, `/api/admin/pending-advance-requests`, `/api/dashboard/charts`, `/api/dashboard/debts`, `/api/dashboard/deliveries`, `/api/dashboard/production-periods`, `/api/dashboard/stats`, `/api/dashboard/today`, `/api/dashboard/today-tasks`, `/api/dashboard/top-finished-products`, `/api/finance/pul-oqimi`, `/api/finance/report`, `/api/finished/stats`, `/api/inventory/purchase-stats`, `/api/obligations/status`, `/api/reports/brak-tahlil`, `/api/returns/stats`, `/api/suppliers`, `/api/suppliers/debt-total`, `/api/suppliers/due-dates`, `/api/transport-stats`

### `GET /debts` → `main.py:debts_page` → `templates/debts.html`
- Qorovul: auth.admin_or_financier
- Server chaqiruvlari: auth.company_id_of, crud.get_ortiqcha_tolovlar, crud.get_suppliers_with_debt, crud.qarz_hisobidagi_buyurtma_sharti, services.get_company_obligations_status, services.get_recurring_obligations
- `debts.html` API: `/api/finance/transactions`, `/api/obligations/employee/{}/close`, `/api/obligations/employee/{}/timeline`, `/api/obligations/recurring`, `/api/obligations/recurring/{}`, `/api/obligations/timeline`, `/api/orders/{}/refund-overpayment`, `/api/payments`

### `GET /finance` → `main.py:finance_page` → `templates/finance.html`
- Qorovul: auth.admin_or_financier
- `finance.html` API: `/api/finance/cash-balance`, `/api/finance/cash-transaction`, `/api/finance/cash-transactions`, `/api/finance/daily`, `/api/finance/debt-summary`, `/api/finance/pul-oqimi`, `/api/finance/report`, `/api/finance/report-pdf`, `/api/finance/split-profit-pdf`, `/api/finance/transactions`, `/api/finance/transactions/{}`, `/api/finance/yonalishlar`, `/api/inventory/kpi`

### `GET /finished` → `main.py:finished_page` → `templates/finished.html`
- Qorovul: auth.admin_warehouse_or_manager
- Server chaqiruvlari: auth.company_id_of, crud.get_employees, crud.get_finished_products, crud.get_finished_stats, crud.get_masters, crud.get_recipes, services.get_default_penoplast, services.get_penoplast_list
- `finished.html` API: `/api/finished`, `/api/finished/loss`, `/api/finished/produce`, `/api/finished/production-brak`, `/api/finished/sales/batch/{}/pdf`, `/api/finished/sales/{}/pdf`, `/api/finished/sell`, `/api/finished/sell-batch`, `/api/finished/stats`, `/api/finished/{}`, `/api/finished/{}/add`, `/api/finished/{}/complete`, `/api/finished/{}/image`, `/api/finished/{}/profit`, `/api/finished/{}/release-reservation`, `/api/loy-cost`

### `GET /hodim` → `main.py:hodim_panel` → `templates/hodim_panel.html`
- Qorovul: — (tanada tekshiriladi yoki ochiq)
- Server chaqiruvlari: auth.get_current_employee
- `hodim_panel.html` API: `/api/hodim/advance-request`, `/api/hodim/my-requests`

### `GET /hodim/login` → `main.py:hodim_login_page` → `templates/hodim_login.html`
- Qorovul: — (tanada tekshiriladi yoki ochiq)
- Server chaqiruvlari: auth.get_current_employee

### `POST /hodim/login` → `main.py:hodim_login_submit` → `templates/hodim_login.html`
- Qorovul: — (tanada tekshiriladi yoki ochiq)
- Server chaqiruvlari: auth.create_employee_session, auth.mijoz_ip, crud.authenticate_employee, crud.check_login_rate_limit, crud.log_login_attempt, crud.resolve_company_by_code

### `GET /inventory` → `main.py:inventory_page` → `templates/inventory.html`
- Qorovul: auth.inventory_view
- Server chaqiruvlari: auth.company_id_of, crud.get_inventory, crud.get_suppliers, services.get_inventory_kpi
- `inventory.html` API: `/api/inventory/full-stock-report`, `/api/inventory/low-stock-alert`, `/api/inventory/movements`, `/api/inventory/purchase-stats`, `/api/inventory/purchases`, `/api/inventory/purchases/{}`, `/api/inventory/receipts/{}/cancel`, `/api/inventory/receipts/{}/cancel-plan`, `/api/inventory/{}`, `/api/inventory/{}/image`, `/api/inventory/{}/min-stock`, `/api/inventory/{}/price`, `/api/inventory/{}/set-default-penoplast`, `/api/inventory/{}/stock`

### `GET /kpi` → `main.py:kpi_page` → `templates/kpi.html`
- Qorovul: auth.admin_or_financier
- `kpi.html` API: `/api/employees`, `/api/employees/advance/{}`, `/api/employees/{}`, `/api/employees/{}/advance`, `/api/employees/{}/advances`, `/api/employees/{}/compensation-history`, `/api/employees/{}/monthly-adjustment`, `/api/employees/{}/set-login`, `/api/finance/report`, `/api/gift-period`, `/api/gift-period/add-master`, `/api/gift-period/close`, `/api/gift-period/open`, `/api/gift-period/redeem/{}/{}`, `/api/gift-period/tier/{}`, `/api/masters`, `/api/masters/kpi-report`, `/api/masters/{}`, `/api/masters/{}/kpi`, `/api/masters/{}/kpi-detail`, `/api/settings/ehson-percent`

### `GET /kunlik-xarajat` → `main.py:kunlik_xarajat_page` → `templates/kunlik_xarajat.html`
- Qorovul: auth.admin_manager_accountant
- `kunlik_xarajat.html` API: `/api/finance/transactions`

### `GET /login` → `main.py:login_page` → `templates/login.html`
- Qorovul: — (tanada tekshiriladi yoki ochiq)
- Server chaqiruvlari: auth.get_current_user

### `POST /login` → `main.py:login_submit` → `templates/login.html`
- Qorovul: — (tanada tekshiriladi yoki ochiq)
- Server chaqiruvlari: auth.create_session, auth.mijoz_ip, auth.verify_and_upgrade_password, crud.check_login_rate_limit, crud.log_login_attempt

### `GET /logs` → `main.py:logs_page` → `templates/logs.html`
- Qorovul: auth.admin_only
- Server chaqiruvlari: auth.company_id_of, crud.get_activity_log, crud.get_error_logs, crud.get_login_history
- `logs.html` API: `/api/settings/categories`, `/api/settings/company`, `/api/settings/company/logo`, `/api/settings/telegram-bot`, `/api/system/backup`, `/api/system/health-check`, `/api/yonalishlar`, `/api/yonalishlar/{}`

### `GET /orders` → `main.py:orders_page` → `templates/orders.html`
- Qorovul: auth.orders_page_access
- Server chaqiruvlari: auth.company_id_of, crud.get_deadline_urgency, crud.get_masters, crud.get_orders_for_main_page, crud.get_projects, crud.get_recipes, services.get_default_penoplast, services.get_penoplast_list
- `orders.html` API: `/api/deliveries`, `/api/deliveries/{}`, `/api/deliveries/{}/pdf`, `/api/finished`, `/api/finished/search`, `/api/loy-stock`, `/api/order-items/{}/image`, `/api/orders`, `/api/orders/attachments/{}`, `/api/orders/pinned`, `/api/orders/{}`, `/api/orders/{}/activate`, `/api/orders/{}/agreed-amount`, `/api/orders/{}/attachments`, `/api/orders/{}/coating-notify`, `/api/orders/{}/delivery-status`, `/api/orders/{}/pdf`, `/api/orders/{}/pin`, `/api/orders/{}/planned-loy`, `/api/orders/{}/profit`, `/api/orders/{}/ready`, `/api/orders/{}/summary-pdf`, `/api/payments`, `/api/payments/{}`, `/api/production/product-types`, `/api/warnings/low-stock`

### `GET /platforma` → `main.py:platforma_page` → `templates/platforma.html`
- Qorovul: — (tanada tekshiriladi yoki ochiq)
- Server chaqiruvlari: auth.get_current_user
- `platforma.html` API: `/api/platform/companies`, `/api/platform/companies/{}/block`, `/api/platform/companies/{}/extend`, `/api/platform/companies/{}/reset-admin-password`, `/api/platform/companies/{}/unblock`, `/api/platform/contact-phone`, `/api/platform/errors`, `/api/platform/summary`

### `GET /production` → `main.py:production_page` → `templates/production.html`
- Qorovul: auth.admin_or_warehouse
- `production.html` API: `/api/inventory`, `/api/production/boms`, `/api/production/boms/preview`, `/api/production/boms/{}`, `/api/production/mrp-order-items`, `/api/production/orders`, `/api/production/orders/preview`, `/api/production/orders/{}/cancel`, `/api/production/orders/{}/complete`, `/api/production/orders/{}/preview`, `/api/production/orders/{}/start`, `/api/production/product-types`, `/api/production/product-types/xulosa`, `/api/production/product-types/{}`, `/api/production/product-types/{}/boms`

### `GET /projects` → `main.py:projects_page` → `templates/projects.html`
- Qorovul: auth.admin_manager_accountant
- Server chaqiruvlari: auth.company_id_of, crud.get_projects_dashboard_stats, crud.get_projects_with_stats
- `projects.html` API: `/api/inventory/movements`, `/api/orders`, `/api/payments`, `/api/projects`, `/api/projects/progress-map`, `/api/projects/{}`, `/api/projects/{}/detail-stats`, `/api/projects/{}/image`, `/api/projects/{}/items`

### `GET /recipes` → `main.py:recipes_page` → `templates/recipes.html`
- Qorovul: auth.admin_or_warehouse
- Server chaqiruvlari: auth.company_id_of, crud.get_recipe_insights, crud.get_recipes
- `recipes.html` API: `/api/inventory`, `/api/recipes`, `/api/recipes/{}`, `/api/recipes/{}/image`

### `GET /reports` → `main.py:reports_page` → `templates/reports.html`
- Qorovul: auth.admin_or_financier
- `reports.html` API: `/api/dashboard/top-finished-products`, `/api/finance/cash-balance`, `/api/finance/history`, `/api/finance/pul-oqimi`, `/api/finance/report`, `/api/finished`, `/api/inventory`, `/api/inventory/kpi`, `/api/masters/kpi-report`, `/api/reports/alerts`, `/api/reports/business-health`, `/api/reports/comparison`, `/api/reports/forecast`, `/api/reports/top-customers`, `/api/reports/top-materials`, `/api/reports/top-suppliers`

### `GET /returns` → `main.py:returns_page` → `templates/returns.html`
- Qorovul: auth.manager_or_warehouse
- Server chaqiruvlari: auth.company_id_of, crud.get_employees, crud.get_orders_for_main_page, crud.get_projects, crud.get_return_items_for_main_page, crud.hodim_nomlari
- `returns.html` API: `/api/orders/{}`, `/api/projects/{}/items`, `/api/reports/brak-materials`, `/api/reports/brak-tahlil`, `/api/returns`, `/api/returns/stats`, `/api/returns/{}`, `/api/returns/{}/image`, `/api/returns/{}/refund`

### `GET /suppliers` → `main.py:suppliers_page` → `templates/suppliers.html`
- Qorovul: auth.admin_or_warehouse
- `suppliers.html` API: `/api/inventory`, `/api/inventory/purchases/{}`, `/api/inventory/{}/purchase`, `/api/suppliers`, `/api/suppliers/payments/{}`, `/api/suppliers/{}`, `/api/suppliers/{}/history`, `/api/suppliers/{}/payment`

### `GET /suppliers/receive` → `main.py:supplier_receive_page` → `templates/supplier_receive.html`
- Qorovul: auth.admin_or_warehouse
- Server chaqiruvlari: auth.company_id_of, crud.get_suppliers
- `supplier_receive.html` API: `/api/inventory`, `/api/inventory/receipt`, `/api/suppliers`, `/api/suppliers/{}/history`, `/api/suppliers/{}/payment`, `/api/suppliers/{}/purchased-items`

### `GET /trash` → `main.py:trash_page` → `templates/trash.html`
- Qorovul: auth.admin_only
- Server chaqiruvlari: auth.company_id_of, crud.get_activity_log, crud.get_deleted_employees, crud.get_deleted_orders, crud.get_deleted_projects
- `trash.html` API: `/api/employees/{}/permanent`, `/api/employees/{}/restore`, `/api/orders/{}/permanent`, `/api/orders/{}/restore`, `/api/projects/{}/permanent`, `/api/projects/{}/restore`

### `GET /users` → `main.py:users_page` → `templates/users.html`
- Qorovul: auth.admin_only
- Server chaqiruvlari: auth.company_id_of, auth.get_all_users
- `users.html` API: `/api/system/factory-reset`, `/api/system/telegram-delete-webhook`, `/api/system/telegram-setup-webhook-security`, `/api/users`, `/api/users/{}/password`, `/api/users/{}/toggle`

### `GET /ustalar` → `main.py:masters_manage_page` → `templates/masters_manage.html`
- Qorovul: auth.admin_or_manager
- `masters_manage.html` API: `/api/masters`, `/api/masters/{}`

Hech bir handler to'g'ridan-to'g'ri ko'rsatmaydigan shablonlar: `xato_sahifa.html`
<!-- AVTO:SAHIFALAR OXIRI -->

### 9.4 API marshrutlari

<!-- AVTO:API BOSHI — qo'lda tahrirlamang: python3 tools/pasport_xarita.py --yoz -->
Har qator: `USUL yo'l` → `fayl:handler` · 🔒 qorovul (`Depends`) · handler tanasidagi to'g'ridan-to'g'ri
`crud.` / `services.` / `production_service.` / `auth.` … chaqiruvlari. 🔓 — `Depends` qorovuli yo'q (ochiq yoki
ruxsat tanada tekshiriladi — o'zgartirishdan OLDIN handler'ni o'qing).

#### `/` (1)
- `GET /` → `main.py:home` · 🔓 · auth.get_current_user

#### `/api/admin` (3)
- `POST /api/admin/advance-requests/{request_id}/confirm` → `main.py:api_confirm_advance_request` · 🔒 auth.admin_or_financier · auth.company_id_of, crud.confirm_advance_request
- `POST /api/admin/advance-requests/{request_id}/reject` → `main.py:api_reject_advance_request` · 🔒 auth.admin_or_financier · auth.company_id_of, crud.reject_advance_request
- `GET /api/admin/pending-advance-requests` → `main.py:api_pending_advance_requests` · 🔒 auth.admin_or_financier · auth.company_id_of, crud.get_pending_advance_requests

#### `/api/cron` (3)
- `GET /api/cron/cleanup-sessions` → `main.py:api_cron_cleanup_sessions` · 🔓 · auth.cleanup_expired_sessions
- `GET /api/cron/find-chat-id` → `main.py:api_find_chat_id` · 🔓
- `GET /api/cron/low-stock-check` → `main.py:api_cron_low_stock_check` · 🔓 · crud.get_low_stock_items

#### `/api/dashboard` (8)
- `GET /api/dashboard/charts` → `main.py:api_dashboard_charts` · 🔒 auth.admin_or_financier · auth.company_id_of, services.get_chart_data
- `GET /api/dashboard/debts` → `main.py:api_debt_stats` · 🔒 auth.admin_or_manager · auth.company_id_of, crud.get_debt_stats
- `GET /api/dashboard/deliveries` → `main.py:api_delivery_stats` · 🔒 auth.admin_or_manager · auth.company_id_of, crud.get_delivery_stats
- `GET /api/dashboard/production-periods` → `main.py:api_production_periods` · 🔒 auth.admin_or_financier · auth.company_id_of, services.get_production_period_stats
- `GET /api/dashboard/stats` → `main.py:api_dashboard_stats` · 🔒 auth.admin_or_financier · auth.company_id_of, services.get_dashboard_stats
- `GET /api/dashboard/today` → `main.py:api_dashboard_today` · 🔒 auth.admin_or_financier · auth.company_id_of, services.get_today_stats
- `GET /api/dashboard/today-tasks` → `main.py:api_today_tasks` · 🔒 auth.require_login · auth.company_id_of, services.get_today_tasks
- `GET /api/dashboard/top-finished-products` → `main.py:api_dashboard_top_finished_products` · 🔒 auth.admin_or_financier · auth.company_id_of, services.get_top_finished_products_sold

#### `/api/deliveries` (3)
- `POST /api/deliveries` → `main.py:api_create_delivery` · 🔒 auth.admin_or_manager · auth.company_id_of, crud._clean_val, crud.create_delivery, crud.get_delivery
- `DELETE /api/deliveries/{delivery_id}` → `main.py:api_delete_delivery` · 🔒 auth.admin_or_manager · auth.company_id_of, auth.delivery_of_company, crud.delete_delivery
- `GET /api/deliveries/{delivery_id}/pdf` → `main.py:api_delivery_pdf` · 🔒 auth.admin_or_manager · auth.company_id_of, crud.get_delivery, delivery_pdf.generate_delivery_pdf

#### `/api/employees` (14)
- `GET /api/employees` → `main.py:api_get_employees` · 🔒 auth.admin_only · auth.company_id_of, crud.get_employees, crud.yonalish_nomlari
- `POST /api/employees` → `main.py:api_create_employee` · 🔒 auth.admin_only · auth.company_id_of, crud._clean_create, crud.create_employee
- `DELETE /api/employees/advance/{advance_id}` → `main.py:api_delete_employee_advance` · 🔒 auth.admin_only · auth.company_id_of, auth.employee_of_company, crud.delete_employee_advance
- `POST /api/employees/backfill-compensation-history` → `main.py:api_backfill_compensation_history` · 🔒 auth.admin_only · auth.company_id_of, crud.backfill_employee_compensation_history
- `PUT /api/employees/{emp_id}` → `main.py:api_update_employee` · 🔒 auth.admin_only · auth.company_id_of, auth.employee_of_company, crud._clean_update, crud.update_employee
- `DELETE /api/employees/{emp_id}` → `main.py:api_delete_employee` · 🔒 auth.admin_only · auth.company_id_of, auth.employee_of_company, crud.delete_employee
- `GET /api/employees/{emp_id}/compensation-history` → `main.py:api_employee_compensation_history` · 🔒 auth.admin_only · auth.company_id_of, auth.employee_of_company
- `DELETE /api/employees/{emp_id}/permanent` → `main.py:api_permanent_delete_employee` · 🔒 auth.admin_only · auth.company_id_of, auth.employee_of_company, crud.permanent_delete_employee
- `POST /api/employees/{emp_id}/restore` → `main.py:api_restore_employee` · 🔒 auth.admin_only · auth.company_id_of, auth.employee_of_company, crud.restore_employee
- `POST /api/employees/{emp_id}/set-login` → `main.py:api_set_employee_login` · 🔒 auth.admin_only · auth.company_id_of, auth.employee_of_company, crud.set_employee_login
- `POST /api/employees/{employee_id}/advance` → `main.py:api_create_employee_advance` · 🔒 auth.admin_only · auth.company_id_of, auth.employee_of_company, crud._clean_avans, crud.create_employee_advance
- `GET /api/employees/{employee_id}/advances` → `main.py:api_get_employee_advances` · 🔒 auth.admin_only · auth.company_id_of, auth.employee_of_company, services.get_employee_advances_list, services.get_employee_advances_total
- `GET /api/employees/{employee_id}/monthly-adjustment` → `main.py:api_get_employee_adjustment` · 🔒 auth.admin_only · auth.company_id_of, auth.employee_of_company, crud.get_employee_monthly_adjustment
- `POST /api/employees/{employee_id}/monthly-adjustment` → `main.py:api_set_employee_adjustment` · 🔒 auth.admin_only · auth.company_id_of, auth.employee_of_company, crud._clean_oylik_tuzatish, crud.set_employee_monthly_adjustment

#### `/api/finance` (17)
- `GET /api/finance/cash-balance` → `main.py:api_get_cash_balance` · 🔒 auth.admin_or_financier · auth.company_id_of, services.get_cash_balance
- `POST /api/finance/cash-transaction` → `main.py:api_record_cash_transaction` · 🔒 auth.admin_only · auth.company_id_of, crud.record_cash_transaction, services.get_cash_balance
- `GET /api/finance/cash-transactions` → `main.py:api_get_cash_transactions` · 🔒 auth.admin_or_financier · auth.company_id_of, crud.get_cash_transactions
- `DELETE /api/finance/cash-transactions/{tx_id}` → `main.py:api_delete_cash_transaction` · 🔒 auth.admin_only · auth.cash_transaction_of_company, auth.company_id_of, crud.delete_cash_transaction
- `GET /api/finance/daily` → `main.py:api_finance_daily` · 🔒 auth.admin_or_financier · auth.company_id_of, services.get_daily_finance_summary
- `GET /api/finance/debt-summary` → `main.py:api_finance_debt_summary` · 🔒 auth.admin_or_financier · auth.company_id_of, services.get_full_debt_summary
- `POST /api/finance/expense` → `main.py:api_save_expense` · 🔒 auth.admin_or_financier
- `GET /api/finance/history` → `main.py:api_finance_history` · 🔒 auth.admin_or_financier · auth.company_id_of, services.get_finance_history
- `GET /api/finance/pul-oqimi` → `main.py:api_finance_pul_oqimi` · 🔒 auth.admin_or_financier · auth.company_id_of, crud._query_butun, services.get_pul_oqimi
- `GET /api/finance/report` → `main.py:api_finance_report` · 🔒 auth.admin_or_financier · auth.company_id_of, services.get_monthly_report
- `GET /api/finance/report-pdf` → `main.py:api_finance_report_pdf` · 🔒 auth.admin_or_financier · auth.company_id_of, crud.get_brak_material_summary, crud.get_expense_transactions, finance_pdf.generate_finance_report_pdf, services.get_full_debt_summary, services.get_monthly_report
- `GET /api/finance/split-profit-pdf` → `main.py:api_split_profit_pdf` · 🔒 auth.admin_or_financier · auth.company_id_of, finance_pdf.generate_split_profit_pdf, services.calculate_split_profit_report
- `GET /api/finance/transactions` → `main.py:api_list_expense_transactions` · 🔒 auth.admin_or_financier · auth.company_id_of, crud.get_expense_transactions
- `POST /api/finance/transactions` → `main.py:api_create_expense_transaction` · 🔒 auth.admin_manager_accountant · auth.company_id_of, crud._clean_val, crud.create_expense_transaction
- `PUT /api/finance/transactions/{tx_id}` → `main.py:api_update_expense_transaction` · 🔒 auth.admin_manager_accountant · auth.company_id_of, auth.expense_of_company, crud._clean_val, crud.update_expense_transaction
- `DELETE /api/finance/transactions/{tx_id}` → `main.py:api_delete_expense_transaction` · 🔒 auth.admin_or_financier · auth.company_id_of, crud.delete_expense_transaction
- `GET /api/finance/yonalishlar` → `main.py:api_finance_yonalishlar` · 🔒 auth.admin_or_financier · auth.company_id_of, services.calculate_split_profit_report

#### `/api/finished` (20)
- `GET /api/finished` → `main.py:api_get_finished` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, crud._fp_ombor_qiymati, crud.fp_ishlab_chiqarish_raqamlari, crud.get_finished_products, crud.get_finished_products_for_main_page
- `POST /api/finished/loss` → `main.py:api_record_finished_loss` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, crud.record_finished_product_loss
- `DELETE /api/finished/loss/{loss_id}` → `main.py:api_delete_finished_loss` · 🔒 auth.admin_only · auth.company_id_of, crud.delete_finished_product_loss
- `POST /api/finished/produce` → `main.py:api_produce` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, crud.bitta_tranzaksiya, crud.get_low_stock_items, crud.produce_finished_product
- `POST /api/finished/production-brak` → `main.py:api_finished_production_brak` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, crud.bitta_tranzaksiya, crud.record_finished_product_production_brak
- `GET /api/finished/sales` → `main.py:api_get_finished_sales` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of
- `GET /api/finished/sales/batch/{group_id}/pdf` → `main.py:api_finished_sale_batch_pdf` · 🔒 auth.admin_or_manager · auth.company_id_of, delivery_pdf.generate_finished_sale_batch_pdf
- `GET /api/finished/sales/{sale_id}/pdf` → `main.py:api_finished_sale_pdf` · 🔒 auth.admin_or_manager · auth.company_id_of, delivery_pdf.generate_finished_sale_pdf
- `GET /api/finished/search` → `main.py:api_search_finished` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, crud.search_finished_products
- `POST /api/finished/sell` → `main.py:api_sell_finished_product` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, crud.sell_finished_product
- `POST /api/finished/sell-batch` → `main.py:api_sell_finished_products_batch` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, crud.sell_finished_products_batch
- `GET /api/finished/stats` → `main.py:api_finished_stats` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, crud.get_finished_stats
- `PUT /api/finished/{fp_id}` → `main.py:api_update_finished` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, crud._clean_update, crud.get_finished_product, crud.update_finished_product
- `DELETE /api/finished/{fp_id}` → `main.py:api_delete_finished` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, auth.finished_product_of_company, crud._fp_tayyormi, crud._mrp_tm_mi, crud.bitta_tranzaksiya, crud.delete_finished_product
- `POST /api/finished/{fp_id}/add` → `main.py:api_add_production` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, crud.add_to_production, crud.bitta_tranzaksiya, crud.get_finished_product, crud.get_low_stock_items
- `POST /api/finished/{fp_id}/complete` → `main.py:api_complete_production` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, crud.complete_production
- `POST /api/finished/{fp_id}/image` → `main.py:api_upload_finished_image` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, auth.finished_product_of_company
- `GET /api/finished/{fp_id}/profit` → `main.py:api_finished_profit` · 🔒 auth.admin_or_financier · auth.company_id_of, crud.get_finished_profit
- `POST /api/finished/{fp_id}/reduce` → `main.py:api_reduce_production` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, crud.get_finished_product, crud.reduce_production
- `POST /api/finished/{fp_id}/release-reservation` → `main.py:api_release_finished_product_reservation` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, crud.release_finished_product_reservation

#### `/api/gift-period` (6)
- `GET /api/gift-period` → `main.py:api_get_gift_period` · 🔒 auth.admin_or_financier · auth.company_id_of, crud.get_gift_period_overview
- `POST /api/gift-period/add-master` → `main.py:api_add_master_to_gift_period` · 🔒 auth.admin_or_financier · auth.company_id_of, crud._clean_val, crud.add_master_to_active_gift_period
- `POST /api/gift-period/close` → `main.py:api_close_gift_period` · 🔒 auth.admin_or_financier · auth.company_id_of, crud._clean_val, crud.close_gift_period
- `POST /api/gift-period/open` → `main.py:api_open_gift_period` · 🔒 auth.admin_or_financier · auth.company_id_of, crud._faqat_kalitlar, crud.open_gift_period
- `POST /api/gift-period/redeem/{master_id}/{tier_id}` → `main.py:api_redeem_gift_period_tier` · 🔒 auth.admin_or_financier · auth.company_id_of, crud.redeem_gift_period_tier
- `PUT /api/gift-period/tier/{tier_id}` → `main.py:api_update_gift_period_tier` · 🔒 auth.admin_or_financier · auth.company_id_of, crud._faqat_kalitlar, crud.update_gift_period_tier

#### `/api/health` (1)
- `GET /api/health` → `main.py:health` · 🔓

#### `/api/hodim` (2)
- `POST /api/hodim/advance-request` → `main.py:api_hodim_advance_request` · 🔒 auth.require_employee_login · crud._clean_avans, crud.create_advance_request
- `GET /api/hodim/my-requests` → `main.py:api_hodim_my_requests` · 🔒 auth.require_employee_login · crud.get_employee_own_requests

#### `/api/inventory` (22)
- `GET /api/inventory` → `main.py:api_get_inventory` · 🔒 auth.inventory_view · auth.company_id_of, crud.get_inventory
- `POST /api/inventory` → `main.py:api_create_item` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud._clean_create, crud.add_item
- `POST /api/inventory/full-stock-report` → `main.py:api_full_stock_report` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud.kam_qoldiqmi
- `GET /api/inventory/kpi` → `main.py:api_inventory_kpi` · 🔒 auth.inventory_view · auth.company_id_of, services.get_inventory_kpi
- `POST /api/inventory/low-stock-alert` → `main.py:api_low_stock_alert` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud.get_low_stock_items
- `GET /api/inventory/movements` → `main.py:api_inventory_movements` · 🔒 auth.inventory_view · auth.company_id_of
- `GET /api/inventory/purchase-stats` → `main.py:api_purchase_stats` · 🔒 auth.inventory_view · auth.company_id_of, crud.get_purchase_stats
- `GET /api/inventory/purchase-trend` → `main.py:api_purchase_trend` · 🔒 auth.inventory_view · auth.company_id_of, crud.get_purchase_stats_range
- `GET /api/inventory/purchases` → `main.py:api_get_purchases` · 🔒 auth.inventory_view · auth.company_id_of, crud.get_purchases
- `PUT /api/inventory/purchases/{purchase_id}` → `main.py:api_update_purchase` · 🔒 auth.admin_or_warehouse · auth.company_id_of, auth.purchase_of_company, crud.update_purchase
- `DELETE /api/inventory/purchases/{purchase_id}` → `main.py:api_delete_purchase` · 🔒 auth.admin_or_warehouse · auth.company_id_of, auth.purchase_of_company, crud.delete_purchase
- `POST /api/inventory/receipt` → `main.py:api_create_inventory_receipt` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud._pul_yigindi, crud._require_inventory_of_company, crud._xarid_narx_jami, crud.bitta_tranzaksiya, crud.create_inventory_receipt, crud.get_supplier
- `POST /api/inventory/receipts/{receipt_id}/cancel` → `main.py:api_receipt_cancel` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud.bitta_tranzaksiya, crud.kirim_hujjatini_bekor_qilish
- `GET /api/inventory/receipts/{receipt_id}/cancel-plan` → `main.py:api_receipt_cancel_plan` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud.kirim_hujjatini_bekor_qilish
- `PUT /api/inventory/{item_id}` → `main.py:api_update_inventory_item` · 🔒 auth.admin_or_warehouse · auth.company_id_of, auth.inventory_of_company, crud._clean_update, crud.update_item
- `DELETE /api/inventory/{item_id}` → `main.py:api_delete_item` · 🔒 auth.admin_only · auth.company_id_of, auth.inventory_of_company, crud.delete_item
- `POST /api/inventory/{item_id}/image` → `main.py:api_upload_inventory_image` · 🔒 auth.admin_or_warehouse · auth.company_id_of, auth.inventory_of_company
- `POST /api/inventory/{item_id}/min-stock` → `main.py:api_update_min_stock` · 🔒 auth.admin_or_warehouse · auth.company_id_of, auth.inventory_of_company, crud._faqat_kalitlar, crud._json_son
- `POST /api/inventory/{item_id}/price` → `main.py:api_update_price` · 🔒 auth.admin_or_warehouse · auth.company_id_of, auth.inventory_of_company, crud._faqat_kalitlar, crud._json_son
- `POST /api/inventory/{item_id}/purchase` → `main.py:api_purchase_stock` · 🔒 auth.admin_or_warehouse · auth.company_id_of, auth.inventory_of_company, crud._xarid_narx_jami, crud.bitta_tranzaksiya, crud.create_supplier_payment, crud.create_transport_expense, crud.get_supplier, crud.get_supplier_debt, crud.get_suppliers_with_debt, crud.purchase_stock
- `POST /api/inventory/{item_id}/set-default-penoplast` → `main.py:api_set_default_penoplast` · 🔒 auth.admin_or_warehouse · auth.company_id_of, auth.inventory_of_company
- `POST /api/inventory/{item_id}/stock` → `main.py:api_update_stock` · 🔒 auth.admin_only · auth.company_id_of, auth.inventory_of_company, crud._clean_stock_change, crud.update_stock

#### `/api/loy-cost` (1)
- `GET /api/loy-cost` → `main.py:api_loy_cost` · 🔒 auth.admin_or_manager · auth.company_id_of, services.get_loy_cost_per_kg

#### `/api/loy-stock` (1)
- `GET /api/loy-stock` → `main.py:api_loy_stock` · 🔒 auth.admin_or_manager · auth.company_id_of, services.get_or_create_loy_stock

#### `/api/masters` (8)
- `GET /api/masters` → `main.py:api_get_masters` · 🔒 auth.admin_or_manager · auth.company_id_of, crud.get_masters
- `POST /api/masters` → `main.py:api_create_master` · 🔒 auth.admin_or_manager · auth.company_id_of, crud._clean_create, crud.create_master
- `GET /api/masters/kpi-report` → `main.py:api_masters_kpi_report` · 🔒 auth.admin_or_financier · auth.company_id_of, crud.get_masters_kpi_report
- `PUT /api/masters/{master_id}` → `main.py:api_update_master` · 🔒 auth.admin_or_manager · auth.company_id_of, crud._clean_update, crud.get_master, crud.update_master
- `DELETE /api/masters/{master_id}` → `main.py:api_delete_master` · 🔒 auth.admin_or_manager · auth.company_id_of, crud.delete_master
- `DELETE /api/masters/{master_id}/delete` → `main.py:api_delete_master_permanent` · 🔒 auth.admin_only · auth.company_id_of, auth.master_of_company
- `PUT /api/masters/{master_id}/kpi` → `main.py:api_update_master_kpi` · 🔒 auth.admin_or_financier · auth.company_id_of, crud.update_master_kpi
- `GET /api/masters/{master_id}/kpi-detail` → `main.py:api_master_kpi_detail` · 🔒 auth.admin_or_financier · auth.company_id_of, crud.get_master_kpi_detail

#### `/api/notifications` (1)
- `GET /api/notifications` → `main.py:api_notifications` · 🔒 auth.require_login · auth.company_id_of, services.get_notifications

#### `/api/obligations` (7)
- `POST /api/obligations/employee/{employee_id}/close` → `main.py:api_close_employee_debt` · 🔒 auth.admin_only · auth.company_id_of, auth.employee_of_company, crud._clean_oylik_yopish, services.close_employee_debt
- `GET /api/obligations/employee/{employee_id}/timeline` → `main.py:api_employee_obligation_timeline` · 🔒 auth.admin_or_manager · auth.company_id_of, auth.employee_of_company, services.get_employee_payment_timeline
- `GET /api/obligations/recurring` → `main.py:api_get_recurring_obligations` · 🔒 auth.admin_or_financier · auth.company_id_of, services.get_recurring_obligations
- `POST /api/obligations/recurring` → `main.py:api_set_recurring_obligation` · 🔒 auth.admin_only · auth.company_id_of, crud._clean_majburiyat, services.set_recurring_obligation
- `DELETE /api/obligations/recurring/{obligation_id}` → `main.py:api_delete_recurring_obligation` · 🔒 auth.admin_only · auth.company_id_of, services.delete_recurring_obligation
- `GET /api/obligations/status` → `main.py:api_obligations_status` · 🔒 auth.admin_or_manager · auth.company_id_of, services.get_company_obligations_status
- `GET /api/obligations/timeline` → `main.py:api_obligations_timeline` · 🔒 auth.admin_or_manager · auth.company_id_of, services.get_obligation_timeline

#### `/api/order-items` (4)
- `PUT /api/order-items/{item_id}` → `main.py:api_update_order_item` · 🔒 auth.admin_or_manager · auth.company_id_of, crud.update_order_item
- `DELETE /api/order-items/{item_id}` → `main.py:api_delete_order_item` · 🔒 auth.admin_or_manager · auth.company_id_of, crud.delete_order_item
- `POST /api/order-items/{item_id}/image` → `main.py:api_upload_order_item_image` · 🔒 auth.orders_page_access · auth.company_id_of
- `DELETE /api/order-items/{item_id}/image` → `main.py:api_delete_order_item_image` · 🔒 auth.orders_page_access · auth.company_id_of

#### `/api/orders` (25)
- `GET /api/orders` → `main.py:api_get_orders` · 🔒 auth.admin_or_manager · auth.company_id_of, crud.get_orders
- `POST /api/orders` → `main.py:api_create_order` · 🔒 auth.admin_or_manager · auth.company_id_of, auth.project_of_company, crud._buyurtma_sigim_tekshir, crud._detal_turi_tekshir, crud._json_loy, crud._query_loy, crud.bitta_tranzaksiya, crud.check_finished_for_order, crud.create_order, crud.get_low_stock_items, crud.qoplama_retsepti_tekshir, services.check_inventory_for_order, services.check_loy_ingredients_for_order, services.deduct_inventory_for_order
- `DELETE /api/orders/attachments/{attachment_id}` → `main.py:api_delete_order_attachment` · 🔒 auth.orders_page_access · auth.company_id_of, crud.log_error
- `POST /api/orders/coating-notify-new` → `main.py:api_coating_notify_with_loy` · 🔒 auth.admin_or_manager
- `POST /api/orders/mark-all-ready` → `main.py:api_mark_all_ready` · 🔒 auth.admin_or_manager
- `GET /api/orders/pinned` → `main.py:api_get_pinned_orders` · 🔒 auth.admin_or_manager · auth.company_id_of, crud.get_pinned_orders
- `GET /api/orders/{order_id}` → `main.py:api_get_order` · 🔒 auth.admin_or_manager · auth.company_id_of, crud.buyurtma_hisob_qatorlari, crud.get_order, crud.pul_qaytarish_kamaytirgan, crud.qaytarish_birlik_narxi, crud.qaytarish_narx_koeffitsienti, production_service.get_order_mrp_readiness, services.get_order_item_unit_cost
- `PUT /api/orders/{order_id}` → `main.py:api_update_order` · 🔒 auth.admin_or_manager · auth.company_id_of, auth.order_of_company, crud._query_loy, crud.get_low_stock_items, crud.get_order, crud.update_order_full, crud.update_order_loy
- `DELETE /api/orders/{order_id}` → `main.py:api_delete_order` · 🔒 auth.admin_or_manager · auth.company_id_of, crud._pul_qulfi, crud._query_loy, crud._return_finished_for_order, crud.bitta_tranzaksiya, crud.delete_order, crud.get_order, crud.ochirishda_topshirilganni_yopish, crud.ochirishda_yopiladimi, crud.ochirishda_yumshoqmi, services._get_planned_loy, services.buyurtmadan_qisman_chiqqan, services.deduct_loy_ingredients, services.loy_manba_ochirish_boshla, services.loy_manba_rejimi, services.loy_relevant_remaining_fraction, services.return_inventory_for_order, services.return_inventory_for_order_partial, services.return_loy_ingredients
- `POST /api/orders/{order_id}/activate` → `main.py:api_activate_draft` · 🔒 auth.admin_or_manager · auth.company_id_of, auth.order_of_company, crud.activate_draft_order
- `PUT /api/orders/{order_id}/agreed-amount` → `main.py:api_update_agreed_amount` · 🔒 auth.admin_or_manager · auth.company_id_of, auth.order_of_company, crud._clean_val, crud.update_order_agreed_amount
- `GET /api/orders/{order_id}/attachments` → `main.py:api_list_order_attachments` · 🔒 auth.admin_or_manager · auth.company_id_of, crud.get_order
- `POST /api/orders/{order_id}/attachments` → `main.py:api_upload_order_attachment` · 🔒 auth.orders_page_access · auth.company_id_of
- `POST /api/orders/{order_id}/coating-notify` → `main.py:api_coating_notify` · 🔒 auth.admin_or_manager · auth.company_id_of, crud._query_loy, crud.get_order, services._set_planned_loy
- `GET /api/orders/{order_id}/delivery-status` → `main.py:api_delivery_status` · 🔒 auth.admin_or_manager · auth.company_id_of, crud.get_delivery_status, crud.get_order
- `PUT /api/orders/{order_id}/loy` → `main.py:api_update_loy` · 🔒 auth.admin_or_manager · auth.company_id_of, auth.order_of_company, crud.bitta_tranzaksiya, crud.update_order_loy
- `GET /api/orders/{order_id}/pdf` → `main.py:api_order_pdf` · 🔒 auth.admin_or_manager · auth.company_id_of, crud.get_order, pdf_service.generate_nakladnoy
- `DELETE /api/orders/{order_id}/permanent` → `main.py:api_permanent_delete_order` · 🔒 auth.admin_only · auth.company_id_of, auth.order_of_company, crud.bitta_tranzaksiya, crud.permanent_delete_order
- `POST /api/orders/{order_id}/pin` → `main.py:api_toggle_order_pin` · 🔒 auth.admin_or_manager · auth.company_id_of, auth.order_of_company, crud.toggle_order_pin
- `GET /api/orders/{order_id}/planned-loy` → `main.py:api_planned_loy` · 🔒 auth.admin_or_manager · auth.company_id_of, crud.get_order, services._get_planned_loy
- `GET /api/orders/{order_id}/profit` → `main.py:api_order_profit` · 🔒 auth.admin_only · auth.company_id_of, crud.get_order, services.calculate_order_profit
- `POST /api/orders/{order_id}/ready` → `main.py:api_mark_order_ready` · 🔒 auth.admin_or_manager · auth.company_id_of, auth.order_of_company, crud._query_loy, crud.bitta_tranzaksiya, crud.get_order, crud.log_error, services.complete_order
- `POST /api/orders/{order_id}/refund-overpayment` → `main.py:api_refund_overpayment` · 🔒 auth.order_payments · auth.company_id_of, crud.bitta_tranzaksiya, crud.ortiqcha_tolovni_qaytar
- `POST /api/orders/{order_id}/restore` → `main.py:api_restore_order` · 🔒 auth.admin_only · auth.company_id_of, auth.order_of_company, crud.restore_order
- `GET /api/orders/{order_id}/summary-pdf` → `main.py:api_summary_pdf` · 🔒 auth.admin_or_manager · auth.company_id_of, auth.order_of_company

#### `/api/ortiqcha-tolovlar` (1)
- `GET /api/ortiqcha-tolovlar` → `main.py:api_ortiqcha_tolovlar` · 🔒 auth.order_payments · auth.company_id_of, crud.get_ortiqcha_tolovlar

#### `/api/payments` (3)
- `GET /api/payments` → `main.py:api_get_payments` · 🔒 auth.order_payments · auth.company_id_of, crud.get_payments
- `POST /api/payments` → `main.py:api_create_payment` · 🔒 auth.order_payments · auth.company_id_of, crud._clean_val, crud.bitta_tranzaksiya, crud.create_payment, crud.get_order
- `DELETE /api/payments/{payment_id}` → `main.py:api_delete_payment` · 🔒 auth.order_payments · auth.company_id_of, crud.bitta_tranzaksiya, crud.delete_payment

#### `/api/penoplasts` (1)
- `GET /api/penoplasts` → `main.py:api_get_penoplasts` · 🔒 auth.admin_or_manager · auth.company_id_of, services.get_default_penoplast, services.get_penoplast_list

#### `/api/platform` (9)
- `GET /api/platform/companies` → `main.py:api_platform_companies` · 🔒 auth.platform_admin_only
- `POST /api/platform/companies` → `main.py:api_platform_create_company` · 🔒 auth.platform_admin_only · auth.create_user, crud.set_setting, crud.standart_yonalish
- `POST /api/platform/companies/{company_id}/block` → `main.py:api_platform_block_company` · 🔒 auth.platform_admin_only
- `POST /api/platform/companies/{company_id}/extend` → `main.py:api_platform_extend_company` · 🔒 auth.platform_admin_only
- `POST /api/platform/companies/{company_id}/reset-admin-password` → `main.py:api_platform_reset_admin_password` · 🔒 auth.platform_admin_only · auth.hash_password, crud.log_activity
- `POST /api/platform/companies/{company_id}/unblock` → `main.py:api_platform_unblock_company` · 🔒 auth.platform_admin_only
- `POST /api/platform/contact-phone` → `main.py:api_platform_contact_phone` · 🔒 auth.platform_admin_only · auth.company_id_of
- `GET /api/platform/errors` → `main.py:api_platform_errors` · 🔒 auth.platform_admin_only
- `GET /api/platform/summary` → `main.py:api_platform_summary` · 🔒 auth.platform_admin_only

#### `/api/production` (20)
- `POST /api/production/boms` → `production_routes.py:create_bom` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud.log_activity
- `POST /api/production/boms/preview` → `production_routes.py:preview_bom` · 🔒 auth.admin_or_warehouse · auth.company_id_of, production_service.retsept_tannarxi
- `PUT /api/production/boms/{bom_id}` → `production_routes.py:update_bom` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud.log_activity
- `DELETE /api/production/boms/{bom_id}` → `production_routes.py:deactivate_bom` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud.log_activity
- `GET /api/production/company-settings` → `production_routes.py:get_company_settings` · 🔒 auth.admin_only · auth.company_id_of
- `PUT /api/production/company-settings` → `production_routes.py:update_company_settings` · 🔒 auth.admin_only · auth.company_id_of, crud.log_activity
- `GET /api/production/mrp-order-items` → `production_routes.py:list_mrp_order_items_pending` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, production_service.get_mrp_order_items_status
- `GET /api/production/orders` → `production_routes.py:list_production_orders` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, production_service.royxat_qoshimchalari
- `POST /api/production/orders` → `production_routes.py:create_order` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, production_service.create_production_order
- `GET /api/production/orders/preview` → `production_routes.py:preview_production_order` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, production_service.ishlab_chiqarish_rejasi
- `POST /api/production/orders/{po_id}/cancel` → `production_routes.py:cancel_order` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, production_service.cancel_production_order
- `POST /api/production/orders/{po_id}/complete` → `production_routes.py:complete_order` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, production_service.complete_production_order
- `GET /api/production/orders/{po_id}/preview` → `production_routes.py:preview_existing_production_order` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, production_service.mavjud_ishlab_chiqarish_rejasi
- `POST /api/production/orders/{po_id}/start` → `production_routes.py:start_order` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, production_service.start_production_order
- `GET /api/production/product-types` → `production_routes.py:list_product_types` · 🔒 auth.admin_or_warehouse · auth.company_id_of
- `POST /api/production/product-types` → `production_routes.py:create_product_type` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud.log_activity, crud.yonalish_tanlovi
- `GET /api/production/product-types/xulosa` → `production_routes.py:product_types_summary` · 🔒 auth.admin_or_warehouse · auth.company_id_of, production_service.turlar_xulosasi
- `DELETE /api/production/product-types/{pt_id}` → `production_routes.py:deactivate_product_type` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud.log_activity
- `PATCH /api/production/product-types/{pt_id}` → `production_routes.py:set_product_type_yonalish` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud.log_activity, crud.yonalish_nomlari, crud.yonalish_tanlovi
- `GET /api/production/product-types/{pt_id}/boms` → `production_routes.py:list_boms_for_product` · 🔒 auth.admin_or_warehouse · auth.company_id_of

#### `/api/projects` (12)
- `GET /api/projects` → `main.py:api_get_projects` · 🔒 auth.admin_or_manager · auth.company_id_of, crud.get_projects
- `POST /api/projects` → `main.py:api_create_project` · 🔒 auth.admin_or_manager · auth.company_id_of, crud._clean_create, crud.create_project
- `GET /api/projects/dashboard-stats` → `main.py:api_projects_dashboard_stats` · 🔒 auth.admin_manager_accountant · auth.company_id_of, crud.get_projects_dashboard_stats
- `GET /api/projects/progress-map` → `main.py:api_projects_progress_map` · 🔒 auth.admin_manager_accountant · auth.company_id_of
- `PUT /api/projects/{project_id}` → `main.py:api_update_project` · 🔒 auth.admin_or_manager · auth.company_id_of, auth.project_of_company, crud._clean_update, crud.update_project
- `DELETE /api/projects/{project_id}` → `main.py:api_delete_project` · 🔒 auth.admin_or_manager · auth.company_id_of, auth.project_of_company, crud.delete_project
- `GET /api/projects/{project_id}/detail-stats` → `main.py:api_project_detail_stats` · 🔒 auth.admin_manager_accountant · auth.company_id_of, auth.project_of_company, crud.log_error, crud.loyiha_bajarilish_foizi, services._hk_tayyorla, services.calculate_order_profit, services.hisobot_keshi
- `POST /api/projects/{project_id}/image` → `main.py:api_upload_project_image` · 🔒 auth.admin_manager_accountant · auth.company_id_of, auth.project_of_company
- `GET /api/projects/{project_id}/items` → `main.py:api_get_project_items` · 🔒 auth.admin_or_manager · auth.company_id_of, auth.project_of_company
- `POST /api/projects/{project_id}/payment` → `main.py:api_add_payment` · 🔒 auth.admin_manager_accountant · auth.company_id_of, auth.project_of_company
- `DELETE /api/projects/{project_id}/permanent` → `main.py:api_permanent_delete_project` · 🔒 auth.admin_only · auth.company_id_of, auth.project_of_company, crud.bitta_tranzaksiya, crud.permanent_delete_project
- `POST /api/projects/{project_id}/restore` → `main.py:api_restore_project` · 🔒 auth.admin_only · auth.company_id_of, auth.project_of_company, crud.restore_project

#### `/api/recipes` (5)
- `GET /api/recipes` → `main.py:api_get_recipes` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud.get_recipes
- `POST /api/recipes` → `main.py:api_create_recipe` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud.create_recipe
- `PUT /api/recipes/{recipe_id}` → `main.py:api_update_recipe` · 🔒 auth.admin_or_warehouse · auth.company_id_of, auth.recipe_of_company, crud.update_recipe
- `DELETE /api/recipes/{recipe_id}` → `main.py:api_delete_recipe` · 🔒 auth.admin_or_warehouse · auth.company_id_of
- `POST /api/recipes/{recipe_id}/image` → `main.py:api_upload_recipe_image` · 🔒 auth.admin_or_warehouse · auth.company_id_of, auth.recipe_of_company

#### `/api/reports` (10)
- `GET /api/reports/alerts` → `main.py:api_reports_alerts` · 🔒 auth.admin_or_financier · auth.company_id_of, services.get_business_alerts
- `GET /api/reports/brak-materials` → `main.py:api_reports_brak_materials` · 🔒 auth.admin_or_financier · auth.company_id_of, crud.get_brak_material_summary
- `GET /api/reports/brak-tahlil` → `main.py:api_brak_tahlil` · 🔒 auth.admin_or_financier · auth.company_id_of, services.get_brak_tahlil
- `GET /api/reports/business-health` → `main.py:api_reports_business_health` · 🔒 auth.admin_or_financier · auth.company_id_of, services.get_business_health
- `GET /api/reports/comparison` → `main.py:api_reports_comparison` · 🔒 auth.admin_or_financier · auth.company_id_of, services.get_monthly_comparison
- `GET /api/reports/forecast` → `main.py:api_reports_forecast` · 🔒 auth.admin_or_financier · auth.company_id_of, services.get_simple_forecast
- `GET /api/reports/top-customers` → `main.py:api_reports_top_customers` · 🔒 auth.admin_or_financier · auth.company_id_of, services.get_top_customers_report
- `GET /api/reports/top-materials` → `main.py:api_reports_top_materials` · 🔒 auth.admin_or_financier · auth.company_id_of, services.get_top_materials_report
- `GET /api/reports/top-products` → `main.py:api_reports_top_products` · 🔒 auth.admin_or_financier · auth.company_id_of, services.get_top_products_report
- `GET /api/reports/top-suppliers` → `main.py:api_reports_top_suppliers` · 🔒 auth.admin_or_financier · auth.company_id_of, services.get_top_suppliers_report

#### `/api/returns` (6)
- `GET /api/returns` → `main.py:api_get_returns` · 🔒 auth.manager_or_warehouse · auth.company_id_of, crud.get_return_items
- `POST /api/returns` → `main.py:api_create_return` · 🔒 auth.manager_or_warehouse · auth.company_id_of, auth.order_of_company, crud._clean_val, crud.bitta_tranzaksiya, crud.create_return_item
- `GET /api/returns/stats` → `main.py:api_return_stats` · 🔒 auth.manager_or_warehouse · auth.company_id_of, crud.get_return_stats
- `DELETE /api/returns/{return_id}` → `main.py:api_delete_return` · 🔒 auth.manager_or_warehouse · auth.company_id_of, auth.return_of_company, crud.delete_return_item
- `POST /api/returns/{return_id}/image` → `main.py:api_upload_return_image` · 🔒 auth.manager_or_warehouse · auth.company_id_of, auth.return_of_company
- `POST /api/returns/{return_id}/refund` → `main.py:api_mark_refunded` · 🔒 auth.manager_or_warehouse · auth.company_id_of, auth.return_of_company, crud.mark_refunded

#### `/api/saas-migration` (2)
- `GET /api/saas-migration/status` → `saas_migration.py:api_status` · 🔒 auth.admin_only
- `POST /api/saas-migration/step/{kalit}` → `saas_migration.py:api_step` · 🔒 auth.admin_only

#### `/api/settings` (9)
- `GET /api/settings/categories` → `main.py:api_get_categories` · 🔒 auth.admin_only · auth.company_id_of
- `PUT /api/settings/categories` → `main.py:api_set_categories` · 🔒 auth.admin_only · auth.company_id_of, crud.set_setting
- `GET /api/settings/company` → `main.py:api_get_company` · 🔒 auth.require_login · auth.company_id_of
- `PUT /api/settings/company` → `main.py:api_set_company` · 🔒 auth.admin_only · auth.company_id_of, crud.set_setting
- `POST /api/settings/company/logo` → `main.py:api_upload_company_logo` · 🔒 auth.admin_only · auth.company_id_of
- `GET /api/settings/ehson-percent` → `main.py:api_get_ehson_percent` · 🔒 auth.admin_or_financier · auth.company_id_of, crud.get_setting
- `PUT /api/settings/ehson-percent` → `main.py:api_set_ehson_percent` · 🔒 auth.admin_only · auth.company_id_of, crud.set_setting
- `GET /api/settings/telegram-bot` → `main.py:api_get_telegram_bot` · 🔒 auth.admin_only · auth.company_id_of, crud.get_setting
- `PUT /api/settings/telegram-bot` → `main.py:api_set_telegram_bot` · 🔒 auth.admin_only · auth.company_id_of, crud.set_setting

#### `/api/suppliers` (10)
- `GET /api/suppliers` → `main.py:api_get_suppliers` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud.get_suppliers_with_debt
- `POST /api/suppliers` → `main.py:api_create_supplier` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud._clean_create, crud.create_supplier
- `GET /api/suppliers/debt-total` → `main.py:api_suppliers_debt_total` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud.get_suppliers_with_debt
- `GET /api/suppliers/due-dates` → `main.py:api_suppliers_due_dates` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud.get_supplier_payment_due_dates
- `DELETE /api/suppliers/payments/{payment_id}` → `main.py:api_delete_supplier_payment` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud.delete_supplier_payment
- `PUT /api/suppliers/{supplier_id}` → `main.py:api_update_supplier` · 🔒 auth.admin_or_warehouse · auth.company_id_of, auth.supplier_of_company, crud._clean_update, crud.update_supplier
- `DELETE /api/suppliers/{supplier_id}` → `main.py:api_delete_supplier` · 🔒 auth.admin_or_warehouse · auth.company_id_of, auth.supplier_of_company, crud.delete_supplier
- `GET /api/suppliers/{supplier_id}/history` → `main.py:api_supplier_history` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud.get_supplier, crud.get_supplier_history
- `POST /api/suppliers/{supplier_id}/payment` → `main.py:api_supplier_payment` · 🔒 auth.admin_or_warehouse · auth.company_id_of, auth.supplier_of_company, crud._clean_val, crud.create_supplier_payment, crud.get_supplier_debt
- `GET /api/suppliers/{supplier_id}/purchased-items` → `main.py:api_supplier_purchased_items` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud.get_supplier_purchased_items

#### `/api/system` (8)
- `GET /api/system/backup` → `main.py:api_system_backup` · 🔒 auth.platform_admin_only · auth.company_id_of, crud.export_full_backup
- `POST /api/system/backup/send-now` → `main.py:api_backup_send_now` · 🔒 auth.platform_admin_only
- `POST /api/system/factory-reset` → `main.py:api_factory_reset` · 🔒 auth.platform_admin_only · auth.company_id_of, crud.factory_reset_all_data
- `GET /api/system/health-check` → `main.py:api_system_health_check` · 🔒 auth.admin_only · auth.company_id_of, crud.check_financial_consistency, crud.check_system_health
- `POST /api/system/restore` → `main.py:api_restore_backup` · 🔒 auth.platform_admin_only · auth.company_id_of, crud.import_full_backup
- `GET /api/system/telegram-debug` → `main.py:api_telegram_debug` · 🔒 auth.platform_admin_only
- `POST /api/system/telegram-delete-webhook` → `main.py:api_telegram_delete_webhook` · 🔒 auth.platform_admin_only
- `POST /api/system/telegram-setup-webhook-security` → `main.py:api_telegram_setup_webhook_security` · 🔒 auth.platform_admin_only

#### `/api/transport-expenses` (3)
- `GET /api/transport-expenses` → `main.py:api_get_transport` · 🔒 auth.admin_or_manager · auth.company_id_of, crud.get_transport_expenses
- `POST /api/transport-expenses` → `main.py:api_create_transport` · 🔒 auth.admin_or_manager · auth.company_id_of, crud._clean_val, crud.create_transport_expense
- `DELETE /api/transport-expenses/{exp_id}` → `main.py:api_delete_transport` · 🔒 auth.admin_or_manager · auth.company_id_of, crud.delete_transport_expense

#### `/api/transport-stats` (1)
- `GET /api/transport-stats` → `main.py:api_transport_stats` · 🔒 auth.admin_or_manager · auth.company_id_of, crud.get_transport_stats

#### `/api/users` (3)
- `POST /api/users` → `main.py:api_create_user` · 🔒 auth.admin_only · auth.company_id_of, auth.create_user, crud._clean_val
- `POST /api/users/{user_id}/password` → `main.py:api_change_password` · 🔒 auth.admin_only · auth.change_password, auth.company_id_of, auth.verify_and_upgrade_password, crud._clean_val
- `POST /api/users/{user_id}/toggle` → `main.py:api_toggle_user` · 🔒 auth.admin_only · auth.company_id_of, auth.toggle_user_active

#### `/api/warnings` (1)
- `GET /api/warnings/low-stock` → `main.py:api_low_stock` · 🔒 auth.require_login · auth.company_id_of, services.get_low_stock_warnings

#### `/api/yonalishlar` (4)
- `GET /api/yonalishlar` → `main.py:api_yonalishlar` · 🔒 auth.all_staff · auth.company_id_of, crud.yonalish_dict, crud.yonalish_ishlatilishi, crud.yonalishlar_royxati
- `POST /api/yonalishlar` → `main.py:api_yonalish_yarat` · 🔒 auth.admin_only · auth.company_id_of, crud.yonalish_dict, crud.yonalish_yarat
- `PUT /api/yonalishlar/{yonalish_id}` → `main.py:api_yonalish_yangila` · 🔒 auth.admin_only · auth.company_id_of, crud.yonalish_dict, crud.yonalish_yangila
- `DELETE /api/yonalishlar/{yonalish_id}` → `main.py:api_yonalish_ochir` · 🔒 auth.admin_only · auth.company_id_of, crud.yonalish_ochir

#### `/dashboard` (1)
- `GET /dashboard` → `main.py:dashboard_page` · 🔒 auth.admin_or_financier · auth.company_id_of, services.get_dashboard_stats

#### `/debts` (1)
- `GET /debts` → `main.py:debts_page` · 🔒 auth.admin_or_financier · auth.company_id_of, crud.get_ortiqcha_tolovlar, crud.get_suppliers_with_debt, crud.qarz_hisobidagi_buyurtma_sharti, services.get_company_obligations_status, services.get_recurring_obligations

#### `/finance` (1)
- `GET /finance` → `main.py:finance_page` · 🔒 auth.admin_or_financier

#### `/finished` (1)
- `GET /finished` → `main.py:finished_page` · 🔒 auth.admin_warehouse_or_manager · auth.company_id_of, crud.get_employees, crud.get_finished_products, crud.get_finished_stats, crud.get_masters, crud.get_recipes, services.get_default_penoplast, services.get_penoplast_list

#### `/hodim` (4)
- `GET /hodim` → `main.py:hodim_panel` · 🔓 · auth.get_current_employee
- `GET /hodim/login` → `main.py:hodim_login_page` · 🔓 · auth.get_current_employee
- `POST /hodim/login` → `main.py:hodim_login_submit` · 🔓 · auth.create_employee_session, auth.mijoz_ip, crud.authenticate_employee, crud.check_login_rate_limit, crud.log_login_attempt, crud.resolve_company_by_code
- `GET /hodim/logout` → `main.py:hodim_logout` · 🔓 · auth.delete_employee_session

#### `/inventory` (1)
- `GET /inventory` → `main.py:inventory_page` · 🔒 auth.inventory_view · auth.company_id_of, crud.get_inventory, crud.get_suppliers, services.get_inventory_kpi

#### `/kpi` (1)
- `GET /kpi` → `main.py:kpi_page` · 🔒 auth.admin_or_financier

#### `/kunlik-xarajat` (1)
- `GET /kunlik-xarajat` → `main.py:kunlik_xarajat_page` · 🔒 auth.admin_manager_accountant

#### `/login` (2)
- `GET /login` → `main.py:login_page` · 🔓 · auth.get_current_user
- `POST /login` → `main.py:login_submit` · 🔓 · auth.create_session, auth.mijoz_ip, auth.verify_and_upgrade_password, crud.check_login_rate_limit, crud.log_login_attempt

#### `/logout` (1)
- `GET /logout` → `main.py:logout` · 🔓 · auth.delete_session

#### `/logs` (1)
- `GET /logs` → `main.py:logs_page` · 🔒 auth.admin_only · auth.company_id_of, crud.get_activity_log, crud.get_error_logs, crud.get_login_history

#### `/masters` (1)
- `GET /masters` → `main.py:masters_page_redirect` · 🔓

#### `/orders` (1)
- `GET /orders` → `main.py:orders_page` · 🔒 auth.orders_page_access · auth.company_id_of, crud.get_deadline_urgency, crud.get_masters, crud.get_orders_for_main_page, crud.get_projects, crud.get_recipes, services.get_default_penoplast, services.get_penoplast_list

#### `/platforma` (1)
- `GET /platforma` → `main.py:platforma_page` · 🔓 · auth.get_current_user

#### `/production` (1)
- `GET /production` → `main.py:production_page` · 🔒 auth.admin_or_warehouse

#### `/projects` (1)
- `GET /projects` → `main.py:projects_page` · 🔒 auth.admin_manager_accountant · auth.company_id_of, crud.get_projects_dashboard_stats, crud.get_projects_with_stats

#### `/recipes` (1)
- `GET /recipes` → `main.py:recipes_page` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud.get_recipe_insights, crud.get_recipes

#### `/reports` (1)
- `GET /reports` → `main.py:reports_page` · 🔒 auth.admin_or_financier

#### `/returns` (1)
- `GET /returns` → `main.py:returns_page` · 🔒 auth.manager_or_warehouse · auth.company_id_of, crud.get_employees, crud.get_orders_for_main_page, crud.get_projects, crud.get_return_items_for_main_page, crud.hodim_nomlari

#### `/saas-migratsiya` (6)
- `GET /saas-migratsiya` → `saas_migration.py:panel_page` · 🔒 auth.admin_only
- `POST /saas-migratsiya/haqiqiy/{kalit}` → `saas_migration.py:panel_apply` · 🔒 auth.admin_only
- `POST /saas-migratsiya/kod/haqiqiy` → `saas_migration.py:panel_kod_haqiqiy` · 🔒 auth.admin_only
- `POST /saas-migratsiya/kod/sinov` → `saas_migration.py:panel_kod_sinov` · 🔒 auth.admin_only
- `POST /saas-migratsiya/sinov-tenant` → `saas_migration.py:panel_test_tenant` · 🔒 auth.admin_only
- `POST /saas-migratsiya/sinov/{kalit}` → `saas_migration.py:panel_dry_run` · 🔒 auth.admin_only

#### `/static` (1)
- `GET /static/uploads/{papka}/{fayl}` → `main.py:yuklangan_fayl` · 🔓 · auth.company_id_of, auth.get_current_user

#### `/suppliers` (2)
- `GET /suppliers` → `main.py:suppliers_page` · 🔒 auth.admin_or_warehouse
- `GET /suppliers/receive` → `main.py:supplier_receive_page` · 🔒 auth.admin_or_warehouse · auth.company_id_of, crud.get_suppliers

#### `/telegram` (1)
- `POST /telegram/webhook` → `main.py:telegram_webhook` · 🔓 · crud.get_master_gift_period_progress, crud.get_master_yearly_cashback

#### `/tiklash` (2)
- `GET /tiklash` → `main.py:tiklash_sahifa` · 🔒 auth.platform_admin_only · auth.company_id_of
- `POST /tiklash` → `main.py:tiklash_bajarish` · 🔒 auth.platform_admin_only · auth.company_id_of, crud.import_full_backup, crud.log_activity

#### `/trash` (1)
- `GET /trash` → `main.py:trash_page` · 🔒 auth.admin_only · auth.company_id_of, crud.get_activity_log, crud.get_deleted_employees, crud.get_deleted_orders, crud.get_deleted_projects

#### `/users` (1)
- `GET /users` → `main.py:users_page` · 🔒 auth.admin_only · auth.company_id_of, auth.get_all_users

#### `/ustalar` (1)
- `GET /ustalar` → `main.py:masters_manage_page` · 🔒 auth.admin_or_manager

Jami marshrutlar: 293 (main.py: 265, production_routes.py: 20, saas_migration.py: 8).
<!-- AVTO:API OXIRI -->

### 9.5 Jadvallar

<!-- AVTO:MODELLAR BOSHI — qo'lda tahrirlamang: python3 tools/pasport_xarita.py --yoz -->
Har jadval: `jadval` — `Klass` (`fayl`, ustunlar soni) — korxona (tenant) bog'lanishi. `_TENANT_RULES` (models.py) —
ORM qorovuli yangi / o'zgargan qatorda ota yozuv korxonasini tekshiradi.

- `activity_logs` — `ActivityLog` (`models.py`, 10) — o'z `company_id`
- `advance_requests` — `AdvanceRequest` (`models.py`, 9) — ota orqali (employee_id→Employee)
- `bom_items` — `BOMItem` (`production_models.py`, 12) — o'z `company_id`
- `boms` — `BOM` (`production_models.py`, 9) — o'z `company_id`
- `cash_transactions` — `CashTransaction` (`models.py`, 7) — o'z `company_id`
- `companies` — `Company` (`production_models.py`, 20) — korxonasiz
- `company_settings` — `CompanySetting` (`models.py`, 4) — o'z `company_id`
- `deliveries` — `Delivery` (`models.py`, 10) — ota orqali (order_id→Order)
- `delivery_items` — `DeliveryItem` (`models.py`, 6) — ota orqali (delivery_id→Delivery)
- `employee_advances` — `EmployeeAdvance` (`models.py`, 6) — ota orqali (employee_id→Employee)
- `employee_compensation_history` — `EmployeeCompensationHistory` (`models.py`, 13) — ota orqali (employee_id→Employee)
- `employee_monthly_adjustments` — `EmployeeMonthlyAdjustment` (`models.py`, 10) — ota orqali (employee_id→Employee)
- `employee_sessions` — `EmployeeSession` (`models.py`, 4) — ota orqali (employee_id→Employee)
- `employees` — `Employee` (`models.py`, 18) — o'z `company_id`
- `error_logs` — `ErrorLog` (`models.py`, 8) — o'z `company_id`
- `expense_transactions` — `ExpenseTransaction` (`models.py`, 11) — o'z `company_id`
- `finished_product_losses` — `FinishedProductLoss` (`models.py`, 14) — o'z `company_id` + ota tekshiruvi (finished_product_id→FinishedProduct)
- `finished_product_sales` — `FinishedProductSale` (`models.py`, 18) — o'z `company_id` + ota tekshiruvi (finished_product_id→FinishedProduct, master_id→Master)
- `finished_products` — `FinishedProduct` (`models.py`, 42) — o'z `company_id` + ota tekshiruvi (from_order_id→Order, recipe_id→Recipe, penoplast_id→Inventory)
- `gift_period_participants` — `GiftPeriodParticipant` (`models.py`, 3) — ota orqali (period_id→GiftPeriod)
- `gift_period_tiers` — `GiftPeriodTier` (`models.py`, 6) — o'z `company_id` + ota tekshiruvi (period_id→GiftPeriod)
- `gift_periods` — `GiftPeriod` (`models.py`, 6) — o'z `company_id`
- `inventory` — `Inventory` (`models.py`, 19) — o'z `company_id`
- `inventory_movements` — `InventoryMovement` (`models.py`, 16) — o'z `company_id` + ota tekshiruvi (inventory_id→Inventory, order_id→Order, supplier_id→Supplier)
- `inventory_purchases` — `InventoryPurchase` (`models.py`, 19) — ota orqali (inventory_id→Inventory, supplier_id→Supplier)
- `inventory_receipts` — `InventoryReceipt` (`models.py`, 15) — o'z `company_id` + ota tekshiruvi (supplier_id→Supplier)
- `login_history` — `LoginHistory` (`models.py`, 7) — o'z `company_id`
- `master_gift_period_redemptions` — `MasterGiftPeriodRedemption` (`models.py`, 10) — ota orqali (period_id→GiftPeriod)
- `master_gift_redemptions` — `MasterGiftRedemption` (`models.py`, 7) — ota orqali (master_id→Master)
- `master_gifts` — `MasterGift` (`models.py`, 7) — o'z `company_id`
- `masters` — `Master` (`models.py`, 11) — o'z `company_id`
- `monthly_expenses` — `MonthlyExpense` (`models.py`, 19) — o'z `company_id`
- `order_attachments` — `OrderAttachment` (`models.py`, 6) — ota orqali (order_id→Order)
- `order_gips_additives` — `OrderGipsAdditive` (`models.py`, 6) — ota orqali (order_id→Order)
- `order_item_sub_details` — `OrderItemSubDetail` (`models.py`, 12) — ota orqali (order_item_id→OrderItem)
- `order_items` — `OrderItem` (`models.py`, 22) — o'z `company_id` + ota tekshiruvi (order_id→Order)
- `orders` — `Order` (`models.py`, 32) — o'z `company_id` + ota tekshiruvi (project_id→Project)
- `payments` — `Payment` (`models.py`, 10) — ota orqali (order_id→Order)
- `product_types` — `ProductType` (`production_models.py`, 13) — o'z `company_id`
- `production_orders` — `ProductionOrder` (`production_models.py`, 21) — o'z `company_id`
- `projects` — `Project` (`models.py`, 18) — o'z `company_id`
- `recipe_ingredients` — `RecipeIngredient` (`models.py`, 4) — ota orqali (recipe_id→Recipe)
- `recipes` — `Recipe` (`models.py`, 8) — o'z `company_id`
- `recurring_obligations` — `RecurringObligation` (`models.py`, 9) — o'z `company_id`
- `return_items` — `ReturnItem` (`models.py`, 26) — o'z `company_id` + ota tekshiruvi (order_id→Order, finished_product_id→FinishedProduct)
- `supplier_payments` — `SupplierPayment` (`models.py`, 6) — ota orqali (supplier_id→Supplier)
- `suppliers` — `Supplier` (`models.py`, 7) — o'z `company_id`
- `transport_expenses` — `TransportExpense` (`models.py`, 9) — o'z `company_id`
- `user_sessions` — `UserSession` (`models.py`, 4) — korxonasiz
- `users` — `User` (`models.py`, 10) — o'z `company_id`
- `yonalishlar` — `Yonalish` (`models.py`, 8) — o'z `company_id`

Jami jadvallar: 51.
<!-- AVTO:MODELLAR OXIRI -->

### 9.6 Testlar katalogi

<!-- AVTO:TESTLAR BOSHI — qo'lda tahrirlamang: python3 tools/pasport_xarita.py --yoz -->
`tools/test_*.py` (SQLite; ko'plari `PG_URL` bilan PostgreSQL da ham) va `tools/test_*.js` (Node + jsdom — shablonning
HAQIQIY JavaScript'i). Har biri oxirida `NATIJA: o'tdi = N yiqildi = M jami = K` chiqaradi; `yiqildi = 0` va chiqish kodi 0 — talab.
Tavsif — faylning birinchi izoh xatboshisi.

- `test_a115_korinish.py` · PG — kech115, A bosqich, ko'rinish guruhi: G3-10 / G1-04 (manfiy raqamlar), G1-01 (o'tgan oy 0 — «100 % oshdi»), G1-06 («Korxona sog'ligi»), G4-06 («Kam» filtri). Server funksiyala…
- `test_a115_ui.py` · PG — kech115, A bosqich (pul va ma'lumot xatolari): «Qarzdorlar», «Buyurtmalar», «O'chirilganlar» sahifalari — HAQIQIY sahifalar (server bergan HTML, shablon + base.html skriptlari) jsdo…
- `test_a116_kirish.py` · PG — kech116, A bosqich 2-qism: U-01 (mijozning HAQIQIY IP manzili, kirish cheklovi) va G6-06 (parol / PIN almashtirilganda o'sha odamning boshqa kirishlari yopiladi). Server qismi;…
- `test_a116_pdf.py` · PG — kech116, A bosqich 2-qism, G2-04: buyurtma pul hisobi qatorlari — YAGONA qoida (`crud.buyurtma_hisob_qatorlari`), uchala mijoz hujjati (yuk xati, hisob-kitob varaqasi, buyurtma nak…
- `test_a116_pul.py` · PG — kech116, A bosqich 2-qism: G1-03 («Pul oqimi» — HAQIQIY pul, egasi QARORI kech114) va G1-02 («Xarajat» — BITTA ta'rif, «Tannarx» alohida). Server qismi: `services.get_pul_oqimi` /…
- `test_a116_ui.py` · PG — kech116, A bosqich 2-qism: sahifalar (HAQIQIY server — uvicorn, sahifalar — jsdom, sahifaning O'Z JavaScript'i). Server qoidalari — `tools/test_a116_pdf.py`, `tools/test_a116_pul.py…
- `test_a117_ui.py` · PG — kech117, A2: YO'NALISHLAR BO'YICHA MOLIYA — sahifalar (HAQIQIY server — uvicorn, sahifalar — jsdom, sahifaning O'Z JavaScript'i). Server qoidalari — `tools/test_a117_yonalish.py`.
- `test_a117_yonalish.py` · PG — kech117, A2: YO'NALISHLAR BO'YICHA MOLIYA (egasi QARORLARI kech114 00:08 — QAYTA SO'RALMAYDI; audit G3-11 / G6-09 shu ichida). Server qismi: `models.Yonalish`, `crud.yonalish_…
- `test_asosiy_penoplast.py` · PG — 18-band (K37-1) darvozasi (kech37, 2026-09-23).
- `test_atomik_103.py` · PG — kech84 darvozasi (2026-09-27, 103-band): YOZADIGAN endpointlar atomik — nosozlik bo'lsa baza O'ZGARMAYDI, qayta urinish ishni BIR marta bajaradi.
- `test_atomik_tolov.py` · PG — kech99 (2026-09-27), probe103 QOLDIG'I (G, H, I).
- `test_b118_korinish.py` · PG — kech118, B bosqichi 2-qism: YAGONA KO'RINISH — o'qiladigan rang va yozuv o'lchami, raqam / sana / birlik yozilishi, inglizcha va xom so'zlar.
- `test_b118_oyna.py` · PG — kech118, B bosqichi 1-qism: DASTURNING O'Z OYNALARI (xabar, kiritish, yopish) va o'zbekcha 404 / 403.
- `test_brak_bekor.py` — xato yozilgan brakni bekor qilish.
- `test_brak_belgi_himoya.py` · PG — K57-1 / 40-band darvozasi (kech57, 2026-09-24).
- `test_brak_belgisi.py` · PG — 13-band 3-qadam darvozasi (kech52, 2026-09-24).
- `test_brak_bitta_raqam.py` · PG — kech107, 49-band darvozasi: BRAK SUMMASI — "BITTA RAQAM" (egasi qarori, QAYTA SO'RALMAYDI).
- `test_brak_bosqich.py` · PG — 13-band 1-qadam darvozasi (kech53, 2026-09-24).
- `test_brak_mrp_loy.py` · PG — 13-band 5-qadam + 41-band + 42-band darvozasi (kech54, 2026-09-24).
- `test_brak_narx.py` · PG — 13-band (brak tizimi) 2-qadam darvozasi (kech46, 2026-09-24).
- `test_brak_ochirish.py` · PG — 13-band (brak tizimi) 6-qadam darvozasi (kech45, 2026-09-23).
- `test_brak_tahlil.py` · PG — 13-band 7-qadam darvozasi (kech56, 2026-09-24).
- `test_buyurtma_narx_jami.py` · PG — kech95 darvozasi (2026-09-27, 117-band + K95-1): buyurtma detali NARXI bazadagidek 2 xonaga (HALF_UP), JAMI shu narxdan; buyurtma jami — detallar jamisining o'nlik yig'in…
- `test_buyurtma_oqimi.py` — buyurtmaning to'liq hayot sikli va OMBOR.
- `test_buyurtma_raqam.py` · PG — kech86 darvozasi (100-band, FOYDALANUVCHI QARORI "A": buyurtma raqami HECH QACHON qayta berilmaydi — raqam faqat o'sadi, o'chirilgan buyurtma raqami bo'shliq bo'lib qoladi) +…
- `test_detal_poyga.py` · PG — 5-bo'lim 14-band darvozasi (kech41, 2026-09-23): detal tahriri / o'chirish / "Tayyor" va yetkazish orasidagi poygalar.
- `test_dizayn114_ui.py` · PG — kech114: dizayn 5–10 (egasi QARORLARI «7A — Guruh, bosilsa ochiladi», «5B — Jadval», «6A — Bir qator + tugmalar»; 9 / 10 — texnik) va K114-1 ning sahifadagi qismi — HAQIQIY sah…
- `test_donalik_hajm_snapshot.py` · PG — kech96 (2026-09-27), 126-band.
- `test_eski_brak_muzlash.py` · PG — 37-band darvozasi (kech51, 2026-09-24).
- `test_eski_narx_muzlash.py` · PG — 33-band darvozasi (kech49, 2026-09-24).
- `test_finished_tartib.py` · PG — 15-band darvozasi (kech35, 2026-09-23).
- `test_fp_product_type.py` — Bosqich 3, 10-band tekshiruvi.
- `test_hisobot_kesh.py` · PG — kech89 darvozasi (2026-09-26, 52-band: Moliya hisobotidagi N+1 so'rovlar).
- `test_hisobot_korxona.py` · PG — kech79 darvozasi (2026-09-25, 101-band): Hisobotlar "Oyma-oy solishtirish" (`/api/reports/comparison`, `services.get_monthly_comparison`) va "Bashorat" (`/api/reports/foreca…
- `test_hisobot_n1.py` · PG — kech97 (2026-09-27), 111-band (oylik hisobotda hodim / usta boshiga so'rovlar) + 116-band 2-qadam (majburiyatlar holati).
- `test_hisobot_tayyor.py` · PG — kech76 darvozasi (2026-09-25, 97-band): hisobotlar FAQAT "Tayyor" (READY) buyurtmani sanaydi — 91-band FOYDALANUVCHI QARORI "B" ("to'liq topshirilgan buyurtma hisobotga / ust…
- `test_hodim_avans.py` · PG — kech107 darvozasi (5-bo'lim 10-band, "hodim paneli"): hodim o'zi yozadigan "avans oldim" so'rovi (`POST /api/hodim/advance-request`, `/hodim` paneli — telefon + PIN) — QAT'IY te…
- `test_hodim_oyligi.py` — Moslashuvchan hodim oyligi hisobi.
- `test_hodim_tarix_korxona.py` · PG — kech109 darvozasi: 10b E-2 / E-3 — chaqirilmaydigan korxonasiz o'qish funksiyalari.
- `test_html_escape.py` — STATIK DARVOZA — shablonlardagi escape qoidalari (5.2d 4-band, kech33).
- `test_html_escape_dom.py` — DINAMIK innerHTML / HTML in'ektsiya darvozasi (5-bo'lim 2-band, kech29).
- `test_idor.py` — IDOR (Insecure Direct Object Reference) darvozasi.
- `test_kam_qoldiq_yagona.py` · PG — kech108, K108-2 (19-band) darvozasi.
- `test_kategoriyalar.py` — buyurtma oynasida qaysi turkum ko'rinadi.
- `test_kelishilgan_nisbat.py` · PG — kech110 darvozasi: K110-1. Buyurtma jami o'zgarganda KELISHILGAN summaning YAGONA qoidasi (`crud.kelishilgan_qayta_hisob`) — to'liq tahrir, detal tahriri / o'chirish, qis…
- `test_kelishilgan_tahrir.py` · PG — kech43 darvozasi: 28-band (K42-2). Kelishilgan summani QAYTA hisoblaydigan joylar pul qaytarish kamaytirishini (`refund_agreed_delta`) yo'qotmasin.
- `test_kesh_oquvchi.py` · PG — kech90 darvozasi (2026-09-26, 110-band: Moliyadan tashqaridagi N+1 o'quvchilar).
- `test_kichik103.py` · PG — kech103 kichik bandlari darvozasi (server tomoni + shablonlar): 45, 63, 83, 90, 69 (+ 11, 25, 55, 64 — statik). UI funksiyalari (58 / 63 / 83 / 90 / 62 / 66 / K103-3 / K103-4) — `…
- `test_kirim_a115.py` · PG — kech115, A bosqich (pul va ma'lumot xatolari), «Kirim qilish» guruhi: G4-01, G4-02, G4-03 va K115-1.
- `test_kirim_bekor.py` · PG — kech107 darvozasi (5-bo'lim 10-band, "Kirim hujjatini bekor qilish"): Ombor KIRIM HUJJATINI butunlay bekor qilish va xarid o'chirilganda O'RTACHA NARXning qaytishi. UI qismi — `…
- `test_kirim_qiymat.py` — 17b: ombor kirimi, kirim HUJJATI va retseptlar tanalarining QAT'IY tekshiruvi.
- `test_kirim_tolov_chegara.py` · PG — kech96 (2026-09-27), 125-band (server + brauzer↔server paritet qismi).
- `test_lint_func_royxat.py` · PG — kech109, K107-3: `tools/tenant_lint.py` ko'r nuqtalari.
- `test_lint_taxallus.py` · PG — kech99 (2026-09-27), 113-band.
- `test_loy_manba.py` · PG — kech82 darvozasi (2026-09-26, 102-band, FOYDALANUVCHI QARORI "A"): buyurtmaning ishlatilmagan LOYI OLINGAN joyiga qaytadi — tayyor loy zaxirasidan olingani zaxiraga, xom ingredien…
- `test_loy_manfiy.py` — 19-band: loy xomashyosi yetishmasa qoldiq MANFIYGA tushadi, kirimda qoplanadi; qo'lda chiqim manfiy qoldiqdagi qarzni o'chira olmaydi.
- `test_loy_query.py` — 17d-band: so'rov qatoridagi LOY miqdori, doimiy majburiyat va eskirgan marshrutlar.
- `test_loy_tenant.py` — loy (qoplama) retsepti bo'yicha korxonalararo darvoza.
- `test_loyiha_foiz.py` · PG — kech101 darvozasi (2026-09-27, 139-band + K101-5).
- `test_loyiha_izchillik.py` · PG — kech98 (2026-09-27), 130-band.
- `test_loyiha_tahrir.py` · PG — kech107 darvozasi (5-bo'lim 10-band, "1a loyiha tahririda muddat"): LOYIHA TAHRIRI — muddat (deadline) va ixtiyoriy maydonlarni tozalash. UI qismi — `tools/test_loyiha_tahrir_…
- `test_material_korxona.py` · PG — kech99 (2026-09-27), 112-band.
- `test_material_nom.py` · PG — kech112 darvozasi: K112-4 — materialni (ombor) boshqa material nomiga qayta nomlash 500 berardi.
- `test_mijozga_qaytarish.py` · PG — kech100 darvozasi (2026-09-27, 131-band, FOYDALANUVCHI QARORI "B" — "Kerak").
- `test_moliya_tafsilot.py` · PG — kech106, K106-2 darvozasi: oylik moliya hisobotining xarajatlar ro'yxati (PDF "Xarajatlar tafsiloti" jadvali va Moliya sahifasidagi ro'yxat) JAMI XARAJAT bilan BIR xil bo'ls…
- `test_mrp_band_korxona.py` · PG — kech109 darvozasi: MRP bandi va ishlab chiqarish bog'lamlari — korxona chegarasi (10b E-1) va buyurtma tahririda ishlab chiqarishga bog'langan detal (K109-2).
- `test_mrp_bosh_tannarx.py` · PG — kech101 darvozasi (2026-09-27, 138-band): MRP detali tannarxi — BO'SHAGAN dona ikki marta emas.
- `test_mrp_jurnal.py` · PG — kech110 darvozasi: 5.2d «Keyingi chat tartibi» 2 (c) — MRP amallari Faoliyat jurnalida.
- `test_mrp_kerak.py` · PG — kech72 darvozasi (2026-09-25, 85-band / K71-2): MRP detali uchun "hali ishlab chiqarish KERAK" miqdori — YAGONA qoida.
- `test_mrp_loy_ulush.py` · PG — 5-bo'lim 44-band + K62-1 darvozasi (kech62, 2026-09-24): MRP detali buyurtma LOYINI sarflamaydi — YAGONA qoida.
- `test_mrp_ortiqcha.py` · PG — kech73 darvozasi (2026-09-25, 86-band / K72-1): MRP detalidan ORTIQCHA qaytarish.
- `test_mrp_qoplama_belgi.py` · PG — kech112 darvozasi: K112-5 — MRP ishlab chiqargan tayyor mahsulot DOIM «qoplamali» bo'lardi.
- `test_mrp_reja.py` · PG — kech113 darvozasi: Ishlab chiqarish (MRP) sahifasi dizayni — egasi qarori "MRP asosiy: 1–4", variant "A — Jadval + oynalar" (server qismi) va K113-1 / K113-2.
- `test_mrp_sahifa_ui.py` · PG — kech113: Ishlab chiqarish (MRP) sahifasi, variant "A — Jadval + oynalar" — HAQIQIY sahifa (server bergan HTML, `templates/production.html` + `base.html` skriptlari) jsdom da,…
- `test_mrp_tannarx.py` — MRP xarajati buyurtma foydasiga yetib boradimi.
- `test_mrp_tayyorlik.py` · PG — kech80 darvozasi (2026-09-26, 88-band): buyurtmadagi «MRP: tayyor» belgisi va «Tayyor» tugmasi / yuk xati — BIR XIL shart.
- `test_mrp_xarajat_surat.py` · PG — kech94 darvozasi (2026-09-27, 122-band): ishlab chiqarish buyurtmasini yakunlashdagi QO'SHIMCHA xarajat (`fixed_cost_per_unit` — 1 birlikka qat'iy summa, `percentage_cost`…
- `test_mrp_yuk_qaytish.py` · PG — kech70 / kech71 darvozasi (2026-09-25): MRP detali yuk xati — olish, qaytarish va "ishlab chiqarilganidan ko'p berib bo'lmaydi".
- `test_naqd_kassa.py` · PG — kech88 darvozasi (2026-09-26, 105 / 107 / 108-band).
- `test_narx_etalon.py` — NARX HISOB-KITOBLARI ETALONI (Bosqich 3, 9-band).
- `test_nom_noyobligi.py` — mahsulot turi va retsept varianti nomlari.
- `test_ochirilgan_tur.py` — 77-band (kech68): korxonada O'CHIRILGAN detal turi (eskirgan `blok`, ixtiyoriy `loy_sotish`) bilan saqlangan MAVJUD detal buyurtma formasida jimgina '' turga aylanmasligi va…
- `test_ochirish_atomik.py` · PG — kech81 darvozasi (2026-09-26, 99-band): buyurtmani O'CHIRISH va TIKLASH atomik — yo hammasi saqlanadi, yo hech biri (nosozlik in'ektsiyasi bilan).
- `test_ochirish_loy.py` · PG — kech77 darvozasi (2026-09-25, 95-band + K77-1): qisman chiqqan buyurtmani o'chirishda "Haqiqatda qancha loy ISHLATILGAN edi?" so'rovi va o'chirish <-> tiklash LOY simmetriyasi.
- `test_ochirish_yopish.py` · PG — kech100 darvozasi (2026-09-27, 93-band, FOYDALANUVCHI QARORI "B").
- `test_ombor_kpi_loy.py` · PG — K35-1 darvozasi (kech36, 2026-09-23).
- `test_ombor_turkum.py` · PG — kech105 darvozasi: K105-2 (ombor turkumi "Boshqa" har deployda "Bazalt" ga aylanardi) va K105-3 (penoplast belgisi material NOMIDAN har deployda qo'yilardi; Ta'minotchilar sahi…
- `test_ortiqcha_qaytarish.py` · PG — 5-bo'lim 57-band darvozasi (kech60, 2026-09-24): ORTIQCHA mahsulot omborga.
- `test_pasport.py` · PG — `LOYIHA_PASPORTI.md` (16-band) izchilligi va shablon → marshrut havolalari darvozasi (kech104, 2026-09-28).
- `test_pdf_matn.py` · PG — kech106, K106-3 va K106-4 darvozasi: PDF hujjatlardagi foydalanuvchi matni va korxona nomi.
- `test_pdf_shrift.py` · PG — kech106, K106-1 darvozasi: PDF hujjatlarda shriftda YO'Q belgi (QORA KVADRAT ■) chiqmasin.
- `test_peno_tenant.py` — "asosiy penoplast" bo'yicha korxonalararo darvoza va `models._tenant_guard` ning filtr ostida ishlashi.
- `test_platforma_obuna.py` · PG — kech111 darvozasi: PLATFORMA ADMIN PANELI (egasi QARORLARI kech109 / kech110 / kech111).
- `test_pul_query.py` · PG — 17f-band: pul maydonlarining ANIQLIGI (1 tiyindan kichik musbat summa) va SIG'IMI (Numeric(12,2)), kirish transporti, mijoz to'lovi, sovg'a davri, xarid tahriri va xarid / kirim h…
- `test_qarz_ochirilgan.py` · PG — kech100 darvozasi (2026-09-27, 134-band, FOYDALANUVCHI QARORI "A"; K100-4).
- `test_qarz_tiyin.py` · PG — kech92 darvozasi (2026-09-26, 119-band / K91-1): mijoz buyurtmasining qarzi va to'lov holati tiyin aniqligida, 0.5 so'mdan oshmaydigan qoldiq — qarz YO'Q (`models.QARZ_BARDOSH`).
- `test_qaytarish_moliya.py` · PG — kech102 darvozasi (2026-09-27, 144-band + K102-1).
- `test_qaytarish_narx.py` · PG — kech42 darvozasi: 4-band, 24-band, brak pul qaytarish va K42-1.
- `test_qaytarish_ochirish.py` · PG — 5-bo'lim 22-band (K39-1) va K40-1 darvozasi (kech40, 2026-09-23).
- `test_qaytarish_query.py` · PG — 17g-band: qaytarish (`POST /api/returns`), yetkazish (`POST /api/deliveries`), xarid narxi va jamisining yaxlitlanishi (3 xonali narx), ta'minotchi to'lovining xarid bilan b…
- `test_qaytarish_yigindi.py` · PG — 5-bo'lim 3-band darvozasi (kech39, 2026-09-23).
- `test_qaytgan_tannarx.py` · PG — 5-bo'lim 34-band darvozasi (kech55, 2026-09-24).
- `test_qoldiq_n1.py` · PG — kech98 (2026-09-27), 129-band (116-band QOLDIG'I: qator boshiga so'rov qolgan 5 joy) + ta'minotchi qarzi yig'indisi va yaxlitlash qoidasi.
- `test_qoplama.py` — Bosqich 3, 11.0-band: MRP mahsulotida QOPLAMA.
- `test_qoplama_retsept.py` · PG — K58-1 / K58-2 / K58-3 (5-bo'lim 43-band) darvozasi (kech58, 2026-09-24).
- `test_qoplama_vaqti.py` — 22-band: qoplamachi bonusi (va ishlab chiqarish miqdoriga bog'liq hodim to'lovi) FAQAT mahsulot "Sotuvga tayyor" (READY) bo'lganda, va u TAYYOR BO'LGAN oyda hisoblanadi.
- `test_retsept_almashtirish.py` · PG — 5-bo'lim 53-band (+ 67-band) darvozasi (kech63, 2026-09-24): jarayondagi buyurtmada QOPLAMA RETSEPTI o'zgartirilsa eski retsept loyi omborga QAYTADI, yangisidan YECHILA…
- `test_royxat_n1.py` · PG — kech97 (2026-09-27), 116-band 1-qadam (buyurtma / loyiha N+1) + 114-band (ro'yxat tartibi).
- `test_saas_otish.py` · PG — kech109 darvozasi: `main` ko'chirishi (K108-1) — `saas_otish.py` va korxona id ketma-ketligi (K109-3).
- `test_soat_utc.py` — kech96 (2026-09-27), 123-band.
- `test_sovga_davr_tenant.py` · PG — kech108, K107-1 darvozasi: Telegram usta boti «🎁 Sovg'alar» ikki korxonada.
- `test_taminotchisiz_xarid.py` · PG — kech100 darvozasi (2026-09-27, 109-band).
- `test_tan_narx_muzlash.py` · PG — K47-1 (5-bo'lim 32-band) darvozasi (kech48, 2026-09-24).
- `test_tana_qatiy.py` · PG — kech93 darvozasi (2026-09-27, 8-band + K93-1 + K93-2): tanasi ilgari QAT'IY tekshirilmagan marshrutlar — foydalanuvchi, parol, usta KPI, sovg'a davri, material narxi / min qoldig…
- `test_tayyor_atomik.py` · PG — kech101 darvozasi (2026-09-27, 142-band + K101-1 … K101-4).
- `test_tayyor_guruh.py` · PG — kech114 darvozasi (2026-09-29): «Tayyor mahsulotlar» guruhlash (egasi QARORI «7A»), ombor qiymati (QAROR — MRP sotuv narxi «Hozirgidek qo'lda»: narxsiz partiya TANNARX bo'yicha…
- `test_tayyor_mahsulot.py` — Tayyor mahsulotning UCHTA ombor funksiyasi.
- `test_tayyor_qiymat.py` — 17-band (17a) darvozasi: TAYYOR MAHSULOT qiymat yo'llari.
- `test_tayyor_reja_loy.py` · PG — kech112 darvozasi: K112-3 — «Tayyor» da haqiqiy loy kiritilmasa, qoplama xarajati foydadan tushib qolardi.
- `test_tayyor_yuk.py` · PG — kech75 darvozasi (2026-09-25, 91 / 92 / 93 / 94-band): "Tayyor" (READY) va yuk xati.
- `test_telegram_tenant.py` — Telegram xabarnomalari va dashboard o'qishlari bo'yicha korxonalararo darvoza (9-sizish).
- `test_tenant_isolation.py` — ikki korxonali avtomatik izolyatsiya testi.
- `test_tf1_login_band.py` · PG — kech108, K107-2 darvozasi: TENANT_FILTER=1 da boshqa korxonada BAND login.
- `test_tm_detal_tannarx.py` · PG — 5-bo'lim 56-band + K103-1 darvozasi (kech103, 2026-09-28): "Tayyor mahsulotdan" olingan detal tannarxi OLINGAN paytda muzlaydi.
- `test_tm_dona_narx.py` — 78-band + K69-1 (kech69): "Tayyor mahsulotdan" (TM) olingan DONALIK detal narxi.
- `test_tm_qoshish.py` · PG — kech61 darvozasi (2026-09-24): tayyor mahsulotga "+" va foyda oynasi.
- `test_tm_qulf.py` · PG — 5-bo'lim 68-band + K64-1 + K65-1 darvozasi (kech65, 2026-09-25): tayyor mahsulot (TM) qatorini o'zgartiradigan amallar orasidagi poygalar.
- `test_tm_sotuv_narx.py` · PG — kech91 darvozasi (2026-09-26, 7-band): tayyor mahsulot sotuvida (bitta — `POST /api/finished/sell`, savatcha — `POST /api/finished/sell-batch`) bazaga yoziladigan narx va jami…
- `test_tm_tahrir_narx.py` — 75-band (kech67): "Tayyor mahsulotdan" (TM) olingan detal narxi buyurtmani TAHRIRLAB saqlaganda o'zgarmasligi.
- `test_tm_tannarx.py` · PG — 5-bo'lim 47-band darvozasi (kech59, 2026-09-24): TAYYOR MAHSULOT 1 birlik tannarxi.
- `test_tolov_query.py` — 17c-band: so'rov qatoridagi pul marshrutlari va loyiha "To'langan" summasi.
- `test_top_tm_korxona.py` · PG — kech78 darvozasi (2026-09-25, 98-band): Dashboard "Tayyor mahsulotdan eng ko'p sotilganlar" (`/api/dashboard/top-finished-products`, `services.get_top_finished_products_sold`…
- `test_toshkent_korinish.py` · PG — kech106, 9 + 50-band B qismi darvozasi (server KO'RINISHI). FOYDALANUVCHI QARORI (kech105, 2026-09-28): "Toshkent vaqti bo'yicha" — hisobot chegaralari (A qism, zip 100 —…
- `test_toshkent_vaqt.py` · PG — kech105, 9 + 50-band darvozasi. FOYDALANUVCHI QARORI (2026-09-28): "Toshkent vaqti bo'yicha (Tavsiya)" — hisobotlarning kun / oy / yil chegaralari TOSHKENT kalendari bo'yicha,…
- `test_transport_foyda.py` · PG — kech87 darvozasi (2026-09-26, 104-band).
- `test_usta_oxirgi_sana.py` · PG — kech91 darvozasi (2026-09-26, 115-band): Usta KPI hisobotidagi "Oxirgi buyurtma" sanasi (`crud.get_masters_kpi_report` → `last_order_date`, `/api/masters/kpi-report`, `/mas…
- `test_xarajat_query.py` — 17e-band: kunlik xarajat tranzaksiyasi va buyurtmaning kelishilgan summasi.
- `test_xarid_manfiy.py` — 20-band: xarid o'chirilganda qoldiq ARIFMETIK kamayadi (manfiyga tushishi mumkin), penoplast qirqishlari olib tashlandi, ombor jurnali to'liq, bildirishnomalarda o'chirilgan ma…
- `test_xarid_tahrir.py` — 21-band: xarid TAHRIRI ombor bilan mos, va ta'minotchini o'chirish FK cheklovida yiqilmaydi.
- `test_yashirin_material.py` · PG — K34-1 darvozasi (kech34, 2026-09-22).
- `test_yetkazish_detal_tolov.py` · PG — 5-bo'lim 6-band va 13-band darvozasi (kech38, 2026-09-23).
- `test_yonalish_natija.py` · PG — kech118 (egasi QARORI 2026-09-30 15:23, tugmali javoblar 15:30 — QAYTA SO'RALMAYDI): YO'NALISHLAR BO'YICHA MOLIYAVIY NATIJA — umumiy xarajat TAQSIMLANMAYDI, oyliklar alohida…
- `test_zaxira_loy_narx.py` · PG — kech107, 36-band darvozasi: TAYYOR LOY ZAXIRASIDAN olingan qoplama narxi.
- `test_brak_bitta_raqam_ui.js` · JS — kech107, 49-band ("Bitta raqam", egasi qarori) UI darvozasi.
- `test_brak_bosqich_ui.js` · JS — 13-band 1-qadam (kech53, 2026-09-24): brak BOSQICHI tanlovi UI si.
- `test_brak_mrp_ui.js` · JS — 13-band 5-qadam (kech54, 2026-09-24): "Ishlab chiqarishda chiqdi" MRP tayyor mahsuloti (`category = 'dynamic_bom'`) uchun ham ochiladi.
- `test_brak_tahlil_ui.js` · JS — 13-band 7-qadam (kech56, 2026-09-24): brak SABABI, JAVOBGAR hodim va BRAK TAHLILI UI si.
- `test_kam_qoldiq_ui.js` · JS — kech108, K108-2 (19-band, EGASI QARORI "Ha, ko'rinsin"): «kam qolgan xomashyo» brauzer qismi.
- `test_kelishilgan_tahrir_ui.js` · JS — kech110, K110-1: buyurtma TAHRIRIDA kelishilgan summa (templates/orders.html).
- `test_kichik103_ui.js` · JS — kech103 kichik bandlari (UI) darvozasi.
- `test_kirim_bekor_ui.js` · JS — kech107 darvozasi (10-band "Kirim hujjatini bekor qilish"): UI oqimi.
- `test_loyiha_forma.js` · JS — Loyiha formalaridagi "Mijoz Telegram ID" va izoh.
- `test_loyiha_tahrir_ui.js` · JS — kech107 darvozasi (10-band "1a"): LOYIHA TAHRIR OYNASI (`templates/projects.html`) — "Muddati" maydoni (`e-deadline`) va tozalangan maydonlar. Server qismi — `tools/test_lo…
- `test_narx_frontend.js` · JS — BRAUZERDAGI narx formulalarining etaloni.
- `test_narx_kiritish_ui.js` · JS — 118-band (kech94): pul / son kiritishning YAGONA qoidasi 9 sahifada (debts, finance, finished, hodim_panel, inventory, kpi, orders, supplier_receive, suppliers).
- `test_narx_nol_himoya_ui.js` · JS — kech108, 71-band qoldig'i: buyurtma tahririda detal narxi JIM 0 ga tushmasin (templates/orders.html — `editSelected` / `collectItems` / `_narxiNolgaTushgan` / `updateOrde…
- `test_ombor_chiqim.js` · JS — Ombor sahifasidagi "Chiqim" oynasi (`saveChiqim`).
- `test_ombor_turkum_ui.js` · JS — kech105 (K105-2 / K105-3) UI darvozasi.
- `test_platforma_ui.js` · JS — kech111: PLATFORMA PANELI sahifasi (templates/platforma.html) — HAQIQIY markup va HAQIQIY sahifa JavaScript'i jsdom da, `fetch` soxta (server javoblari fiksturadan).
- `test_qaytarish_ochirish_ui.js` · JS — kech40 (2026-09-23), 5-bo'lim 22-band + K40-1: qaytarishni o'chirish va qaytgan tayyor mahsulotni o'chirish UI si.
- `test_qoralama_tugma_ui.js` · JS — kech109, K109-1: buyurtma TAHRIRIDA «📝 Vaqtincha saqlash» tugmasi yashirilishi (templates/orders.html).
- `test_standart_tiyin_ui.js` · JS — kech96 (2026-09-27), 125-band + K96-1 (brauzer qismi).
- `test_tahrir_banner_ui.js` · JS — kech108, K108-3: topshirila boshlagan buyurtmani tahrirlash oynasi (templates/orders.html).
- `test_tahrir_tiyin_ui.js` · JS — kech95 (2026-09-27), 124-band + 117-band (brauzer qismi).
- `test_tolov_panel_ui.js` · JS — tools/test_tolov_panel_ui.js — kech44, 30-band.
- `test_tolov_ui.js` · JS — mijoz to'lovini saqlash (`savePayment`) ikki sahifada: templates/orders.html (to'lov oynasi) va templates/debts.html (qarzni yopish).
- `test_toshkent_korinish_ui.js` · JS — kech106, 9 + 50-band C qismi darvozasi (BRAUZER ko'rinishi). FOYDALANUVCHI QARORI (kech105, 2026-09-28): "Toshkent vaqti bo'yicha" — ekrandagi sana-vaqt, "bugun" standa…
- `test_xarid_ochirish.js` · JS — Ta'minotchilar sahifasidagi xaridni o'chirish (`deletePurchase`, templates/suppliers.html).
- `test_xarid_tahrir_ui.js` · JS — Ta'minotchilar sahifasidagi xaridni TAHRIRLASH (`editPurchase`) va server sababini ko'rsatish (`serverSababi`), templates/suppliers.html.
- `test_xato_sababi_ui.js` · JS — kech107 darvozasi (5-bo'lim 10-band, "UI 400 sabablari kpi / inventory / finished").
- `test_yetkazish_ui.js` · JS — 17g (2026-09-22): yetkazish va brak yozish UI si.
- `test_yuk_ochirish_ui.js` · JS — kech38 (2026-09-23), 5-bo'lim 12-band: to'lov bog'langan yuk xatini o'chirish UI si.
- `test_yuqori_panel_ui.js` · JS — kech111 (K112-1): yuqori paneldagi ochiluvchi panellar — obuna ogohlantirishi (`#obunaPanel`) va bildirishnomalar (`#notifPanel`) — ochilganda EKRAN ICHIDA joylanadi (templa…

Jami test fayllari: 173 (Python 143, JS 30).
<!-- AVTO:TESTLAR OXIRI -->
