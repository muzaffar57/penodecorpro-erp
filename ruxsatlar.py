"""ruxsatlar.py — ROLLAR VA RUXSATLAR (kech118, egasi QARORI 15:23: «Hodim rollarini admin o'zi boshqaradigan qilaylik»).

YAGONA MANBA: bo'limlar katalogi (har bo'lim — bandlar, har band — amallar: Ko'rish / Yaratish / Tahrirlash / O'chirish),
tayyor rollar (Admin, Menejer, Omborchi, Moliyachi) va ruxsatni tekshirish qoidasi. Hech qanday model / baza importi YO'Q
(models.py undan foydalanadi — aylanma import bo'lmasin).

QOIDALAR (egasi qarorlari, tugmali javoblar kech118 15:30):
* Ruxsat — har band uchun rasmdagidek 4 belgi (band o'ziga tegishli amallarnigina ko'rsatadi; masalan «Dashboard» — faqat
  Ko'rish). Bo'limni bir tugmada yoqish / o'chirish — sahifada.
* Pul sirlari — ALOHIDA ruxsat «Tannarx va foyda» (band `tannarx`, faqat Ko'rish).
* Tayyor rollar: Admin (doim, to'liq, o'zgarmaydi), Menejer, Omborchi, Moliyachi. «Usta» login roli — tayyor rollarda YO'Q
  (egasi qarori); eski «master» foydalanuvchisi bo'lsa — migratsiya uning AYNAN hozirgi huquqi bilan «Usta (eski)» rolini
  yaratadi (hech kim huquq yo'qotmaydi / ortiqcha olmaydi).
* Tayyor rollarning ruxsatlari — o'zgarishdan OLDINGI huquqlardan HISOBLANGAN (work/k119/tayinlash.py: har marshrut
  eski bog'lamasi → andoza); Menejer — AYNAN hozirgidek (egasi: «ruxsatlari hozirgidek»). Ataylab farqlar (hujjatlangan,
  tools/test_rollar.py da ro'yxat bilan tekshiriladi): Moliyachi — Dashboard va Qarzlar sahifalaridagi 6 ta so'rov
  (ilgari sahifasi ochilib, ma'lumoti 403 berardi) ochildi; Omborchi — sotuv cheki PDF (sotadi, lekin chekni ololmasdi);
  Menejer — hech qaysi sahifasi ishlatmaydigan 6 ta Dashboard / Qarzlar so'rovi yopildi (ko'rinadigan farq YO'Q).
* Admin (`users.role == ADMIN`) — hamma narsa; «Foydalanuvchilar va rollar» boshqaruvi — FAQAT Admin (topshirilmaydi:
  aks holda istalgan rol o'zini Admin qila olardi).
* Foydalanuvchining rolida band / amal yo'q — 403 («Sizning rolingizda … ruxsati yo'q»).
* (kech127, zip 150 — egasi QARORI 07.10 20:1x, tugmali: «Xomashyo narxlari va «Ombor qiymati» ham yashirilsin» — 2 hodim,
  «Menejer» roli) — ALOHIDA ruxsat «Xomashyo narxlari va ombor qiymati» (band `material_narx`, faqat Ko'rish): yo'q bo'lsa
  Omborxonadagi xarid narxi, kirim summasi, «Ombor qiymati», penoplast / loy ro'yxatidagi narx — «—» (`narx_tozala`).
  «Tannarx va foyda» bor rol narxni baribir ko'radi (tannarx shu narxlardan hisoblanadi — `narx_koradi`).
  Ta'minotchilar bo'limi (ta'minotchi qarzi va undan olingan xaridlar) — o'z ruxsati bilan, bu bandga kirmaydi."""
import json

AMALLAR = (("korish", "Ko'rish"), ("yaratish", "Yaratish"), ("tahrirlash", "Tahrirlash"), ("ochirish", "O'chirish"))
AMAL_NOMI = dict(AMALLAR)
_K, _Y, _T, _O = "korish", "yaratish", "tahrirlash", "ochirish"
_HAMMA = (_K, _Y, _T, _O)

# Bo'limlar katalogi — sahifadagi tartib. Har band: (kod, nom, izoh, amallar).
BOLIMLAR = (
    ("asosiy", "Bosh sahifa va Dashboard", "ti-chart-bar", (
        ("dashboard", "Bosh sahifa va Dashboard", "Bugungi holat, ko'rsatkichlar, grafiklar", (_K,)),
    )),
    ("buyurtmalar", "Buyurtmalar", "ti-receipt", (
        ("buyurtma", "Buyurtmalar", "Buyurtma yaratish, tahrirlash, tayyor deb belgilash, buyurtma hisobi PDF", _HAMMA),
        ("buyurtma_fayl", "Buyurtma rasmlari va fayllari", "Buyurtmaga rasm / fayl biriktirish", (_Y, _O)),
        ("tolov", "Mijoz to'lovlari", "To'lov qabul qilish, ortiqcha to'lovni qaytarish, loyihaga to'lov", (_K, _Y, _O)),
        ("yetkazish", "Yetkazib berish va transport", "Yuk xati, transport xarajatlari", (_K, _Y, _O)),
    )),
    ("loyihalar", "Loyihalar", "ti-clipboard-list", (
        ("loyiha", "Loyihalar", "Loyiha (mijoz) yaratish, tahrirlash, o'chirish", _HAMMA),
        ("loyiha_korsatkich", "Loyiha ko'rsatkichlari va rasmi", "Loyihalar sahifasidagi ko'rsatkichlar, loyiha rasmi",
         (_K, _T)),
    )),
    ("tayyor", "Tayyor mahsulotlar", "ti-building-factory-2", (
        ("tayyor", "Tayyor mahsulotlar", "Ishlab chiqarish, qo'shish / kamaytirish, tahrirlash", _HAMMA),
        ("sotuv", "Sotuv", "Tayyor mahsulot sotish, sotuv cheki", (_K, _Y)),
        ("brak", "Brak va hisobdan chiqarish", "Brak yozish, yo'qotishni hisobdan chiqarish", (_Y, _O)),
    )),
    ("ombor", "Omborxona", "ti-package", (
        ("material", "Materiallar", "Xomashyo ro'yxati, narx, minimal qoldiq, Telegramga qoldiq hisoboti", _HAMMA),
        ("qoldiq", "Qoldiqni qo'lda tuzatish", "Material qoldig'ini to'g'ridan-to'g'ri o'zgartirish", (_T,)),
        ("kirim", "Xomashyo kirimi (xaridlar)", "Kirim qilish, xaridni tahrirlash, kirimni bekor qilish", _HAMMA),
        # kech127 (zip 150): egasi QARORI 07.10 — xarid narxi va ombor qiymati alohida ruxsat (Menejerda yo'q)
        ("material_narx", "Xomashyo narxlari va ombor qiymati",
         "Xarid narxi, kirim summasi, «Ombor qiymati»; «Tannarx va foyda» bor rol ham ko'radi", (_K,)),
    )),
    ("taminot", "Ta'minotchilar", "ti-truck", (
        ("taminotchi", "Ta'minotchilar", "Ta'minotchi ro'yxati, tarixi, qarzi", _HAMMA),
        ("taminotchi_tolov", "Ta'minotchiga to'lov", "Ta'minotchiga to'lov yozish / o'chirish", (_Y, _O)),
    )),
    ("ishlab", "Retsept va ishlab chiqarish", "ti-flask", (
        ("retsept", "Loy retseptlari", "Retsept yaratish va tahrirlash", _HAMMA),
        ("mahsulot_turi", "Mahsulot turlari va tarkibi", "Ishlab chiqarish sahifasi: mahsulot turi, tarkibi (MRP)",
         _HAMMA),
        ("ishlab_buyurtma", "Ishlab chiqarish buyurtmalari", "MRP buyurtmasi: yaratish, boshlash, yakunlash, bekor qilish",
         _HAMMA),
    )),
    ("qaytarish", "Qaytarishlar", "ti-arrow-back-up", (
        ("qaytarish", "Qaytarishlar", "Mijozdan qaytgan mahsulot, pulni qaytarish", _HAMMA),
    )),
    ("moliya", "Moliya", "ti-trending-up", (
        ("moliya", "Moliyaviy hisobot", "Moliya sahifasi, yo'nalishlar natijasi, PDF, oylik xarajatlarni saqlash", (_K, _T)),
        ("kassa", "Kassa + bank", "Kassa + bank qoldig'i (naqd, karta, bank), pul oqimi, kassa yozuvlari", (_K, _Y, _O)),
        ("kunlik", "Kunlik xarajatlar", "Xarajat qo'shish, tahrirlash, o'chirish", _HAMMA),
        ("qarz", "Qarzlar va majburiyatlar", "Qarzdorlar sahifasi, doimiy majburiyatlar", _HAMMA),
        ("tannarx", "Tannarx va foyda", "Buyurtma va tayyor mahsulot foydasi (tannarx, foyda)", (_K,)),
    )),
    ("hisobotlar", "Hisobotlar", "ti-report", (
        ("hisobot", "Hisobotlar", "Oylik tahlil, eng ko'p sotilganlar, brak tahlili", (_K,)),
    )),
    ("hodimlar", "Ustalar va hodimlar", "ti-users", (
        ("usta", "Ustalar ro'yxati", "Usta qo'shish, tahrirlash, o'chirish", _HAMMA),
        ("kpi", "Ustalar KPI va sovg'alar", "KPI foizi, KPI hisoboti, sovg'a davri", (_K, _T)),
        ("hodim", "Hodimlar (oylik, avans)", "Hodim qo'shish, oylik, avans, hodim paneliga kirish", _HAMMA),
        ("avans_sorov", "Avans so'rovlari", "Hodim panelidan kelgan avans so'rovini tasdiqlash / rad etish", (_K, _T)),
    )),
    ("boshqaruv", "Boshqaruv", "ti-settings", (
        ("sozlama", "Korxona sozlamalari", "Korxona ma'lumoti, logotip, turkumlar, yo'nalishlar, Telegram bot, ehson foizi",
         _HAMMA),
        ("savat", "O'chirilganlar", "O'chirilganlarni tiklash va butunlay o'chirish", (_K, _T, _O)),
        ("jurnal", "Tizim jurnallari", "Amallar jurnali, tizim holati", (_K,)),
    )),
)

BANDLAR = {}          # kod → {"modul", "modul_nom", "nom", "izoh", "amallar"}
for _m, _mn, _ik, _bl in BOLIMLAR:
    for _b, _bn, _iz, _am in _bl:
        BANDLAR[_b] = {"modul": _m, "modul_nom": _mn, "nom": _bn, "izoh": _iz, "amallar": _am}


# Bandning amali qaysi SAHIFADA ishlatiladi — sahifasi o'zida bo'lmagan bandlar uchun (sahifada ogohlantirish: «bu bo'lim
# … sahifasida — … ham belgilang»). (kerak — birortasi yetadi, matn).
SAHIFA_KERAK = {
    "tolov": ((("buyurtma", _K), ("loyiha", _K), ("loyiha_korsatkich", _K), ("qarz", _K)),
              "Buyurtmalar, Loyihalar yoki Qarzdorlar sahifasida ishlaydi"),
    "yetkazish": ((("buyurtma", _K),), "Buyurtmalar sahifasida ishlaydi — «Buyurtmalar: Ko'rish» ham kerak"),
    "brak": ((("tayyor", _K), ("sotuv", _K)), "Tayyor mahsulotlar sahifasida ishlaydi"),
    "qoldiq": ((("material", _K),), "Omborxona sahifasida ishlaydi — «Materiallar: Ko'rish» ham kerak"),
    "kirim": ((("material", _K), ("kirim", _Y)), "Omborxona yoki Xomashyo ta'minoti sahifasida ishlaydi"),
    "material_narx": ((("material", _K), ("kirim", _K), ("kirim", _Y), ("buyurtma", _K), ("tayyor", _K)),
                      "Omborxona, Kirim, Buyurtmalar yoki Tayyor mahsulotlar sahifasida ishlaydi"),
    "taminotchi_tolov": ((("taminotchi", _K),), "Ta'minotchilar sahifasida ishlaydi — «Ta'minotchilar: Ko'rish» ham kerak"),
    "ishlab_buyurtma": ((("mahsulot_turi", _K), ("tayyor", _K)), "Ishlab chiqarish yoki Tayyor mahsulotlar sahifasida ishlaydi"),
    "kassa": ((("moliya", _K),), "Moliya sahifasida ishlaydi — «Moliyaviy hisobot: Ko'rish» ham kerak"),
    "hodim": ((("kpi", _K),), "«Ustalar KPI / Hodimlar» sahifasida ishlaydi — «Ustalar KPI: Ko'rish» ham kerak"),
    "avans_sorov": ((("dashboard", _K),), "Dashboard sahifasida ishlaydi — «Bosh sahifa va Dashboard: Ko'rish» ham kerak"),
    "sozlama": ((("jurnal", _K),), "«Tizim jurnallari» sahifasida ishlaydi — «Tizim jurnallari: Ko'rish» ham kerak"),
}


def _r(**kw):
    return {b: list(a) for b, a in kw.items()}


# Tayyor rollar — tartib: sahifadagi ro'yxat. `yashirin` — tanlovda ko'rinmaydi (faqat eski foydalanuvchi uchun yaratiladi).
TAYYOR_ROLLAR = {
    "admin": {"nom": "Admin", "tavsif": "Hamma narsa — moliya, ombor, foydalanuvchilar, sozlamalar. O'zgartirilmaydi.",
              "ruxsatlar": {b: list(v["amallar"]) for b, v in BANDLAR.items()}},
    "menejer": {"nom": "Menejer", "tavsif": "Loyiha va buyurtmalar, to'lovlar, yetkazish, tayyor mahsulot, qaytarishlar, ustalar. "
                                            "Moliya, foyda, xomashyo narxlari, Ustalar KPI ko'rinmaydi.",
                "ruxsatlar": _r(buyurtma=_HAMMA, buyurtma_fayl=(_Y, _O), tolov=(_K, _Y, _O), yetkazish=(_K, _Y, _O),
                                loyiha=_HAMMA, loyiha_korsatkich=(_K, _T), tayyor=_HAMMA, sotuv=(_K, _Y), brak=(_Y,),
                                material=(_K,), kirim=(_K,), ishlab_buyurtma=_HAMMA, qaytarish=_HAMMA, kunlik=(_Y, _T),
                                usta=_HAMMA)},
    "omborchi": {"nom": "Omborchi", "tavsif": "Omborxona, xomashyo kirimi, ta'minotchilar, retseptlar, ishlab chiqarish, "
                                              "tayyor mahsulot, qaytarish va brak.",
                 "ruxsatlar": _r(tayyor=_HAMMA, sotuv=(_K, _Y), brak=(_Y,), material=(_K, _Y, _T), kirim=_HAMMA,
                                 material_narx=(_K,), taminotchi=_HAMMA, taminotchi_tolov=(_Y, _O), retsept=_HAMMA,
                                 mahsulot_turi=_HAMMA, ishlab_buyurtma=_HAMMA, qaytarish=_HAMMA)},
    "moliyachi": {"nom": "Moliyachi", "tavsif": "Moliya, kassa, kunlik xarajatlar, qarzlar, hisobotlar, Ustalar KPI, "
                                                "avans so'rovlari, mijoz to'lovlari.",
                  "ruxsatlar": _r(dashboard=(_K,), tolov=(_K, _Y, _O), loyiha_korsatkich=(_K, _T),
                                  material_narx=(_K,), moliya=(_K, _T), kassa=(_K,), kunlik=_HAMMA, qarz=(_K,),
                                  tannarx=(_K,), hisobot=(_K,), kpi=(_K, _T), avans_sorov=(_K, _T))},
    "usta": {"nom": "Usta (eski)", "tavsif": "Eski «Usta» login roli: faqat buyurtmaga rasm / fayl biriktirish.",
             "ruxsatlar": _r(buyurtma_fayl=(_Y, _O)), "yashirin": True},
}
TAYYOR_TARTIB = ("admin", "menejer", "omborchi", "moliyachi")

# Eski `users.role` qiymati → tayyor rol kodi (migratsiya va rol biriktirilmagan foydalanuvchi uchun zaxira qoida).
ENUM_ROL = {"admin": "admin", "manager": "menejer", "warehouse": "omborchi", "accountant": "moliyachi", "master": "usta"}
# Rol → `users.role` (eski ustun — faqat Admin belgisi uchun ahamiyatli; boshqalari ma'lumot uchun).
ROL_ENUM = {"admin": "admin", "menejer": "manager", "omborchi": "warehouse", "moliyachi": "accountant", "usta": "master"}


def ruxsatlar_oqi(matn) -> dict:
    """Bazadagi JSON matn → {band: set(amal)} (noma'lum band / amal tashlanadi; buzilgan matn — bo'sh)."""
    try:
        d = json.loads(matn) if isinstance(matn, str) else (matn or {})
    except (TypeError, ValueError):
        return {}
    if not isinstance(d, dict):
        return {}
    natija = {}
    for b, am in d.items():
        if b not in BANDLAR or not isinstance(am, (list, tuple)):
            continue
        s = {a for a in am if a in BANDLAR[b]["amallar"]}
        if s:
            natija[b] = s
    return natija


def ruxsatlar_tozala(kiritma) -> dict:
    """Admin yuborgan ruxsatlar ({band: [amal, ...]}) — tekshiriladi va tartiblanadi; noma'lum band / amal — ValueError."""
    if kiritma is None:
        return {}
    if not isinstance(kiritma, dict):
        raise ValueError("Ruxsatlar noto'g'ri yuborildi")
    natija = {}
    for b, am in kiritma.items():
        if b not in BANDLAR:
            raise ValueError(f"Noma'lum bo'lim: {b}")
        if not isinstance(am, (list, tuple)):
            raise ValueError(f"«{BANDLAR[b]['nom']}» amallari noto'g'ri")
        for a in am:
            if a not in BANDLAR[b]["amallar"]:
                raise ValueError(f"«{BANDLAR[b]['nom']}» bo'limida «{AMAL_NOMI.get(a, a)}» amali yo'q")
        tartibli = [a for a, _ in AMALLAR if a in am]
        if tartibli:
            natija[b] = tartibli
    return natija


def ruxsatlar_json(d: dict) -> str:
    """{band: set / list} → barqaror JSON matn (katalog tartibida)."""
    toza = {}
    for b in BANDLAR:
        if b in d and d[b]:
            toza[b] = [a for a, _ in AMALLAR if a in d[b]]
    return json.dumps(toza, ensure_ascii=False)


def foydalanuvchi_ruxsatlari(user):
    """Foydalanuvchining ruxsatlari: {band: set(amal)}; Admin — None (hammasi). So'rov davomida user obyektida eslab
    qolinadi. Rol biriktirilmagan (yoki boshqa korxonaning roli — xavfsiz tomon) — eski `role` qiymatining tayyor andozasi."""
    kesh = user.__dict__.get("_ruxsat_kesh", False)
    if kesh is not False:
        return kesh
    rv = getattr(getattr(user, "role", None), "value", None)
    if rv == "admin":
        natija = None
    else:
        rol = getattr(user, "rol", None) if getattr(user, "rol_id", None) else None
        if rol is not None and rol.company_id == user.company_id:
            natija = ruxsatlar_oqi(rol.ruxsatlar)
        else:
            natija = ruxsatlar_oqi(TAYYOR_ROLLAR.get(ENUM_ROL.get(rv, ""), {}).get("ruxsatlar", {}))
    user.__dict__["_ruxsat_kesh"] = natija
    return natija


def bormi(user, band: str, amal: str = None) -> bool:
    """Foydalanuvchida band (amal berilmasa — bandning ISTALGAN amali) ruxsati bormi. Admin — doim ha."""
    if user is None:
        return False
    r = foydalanuvchi_ruxsatlari(user)
    if r is None:
        return True
    s = r.get(band) or set()
    return bool(s) if amal is None else amal in s


def rad_matni(band: str, amal: str) -> str:
    b = BANDLAR.get(band, {})
    return (f"Sizning rolingizda «{b.get('modul_nom', band)} → {b.get('nom', band)}» bo'limida "
            f"«{AMAL_NOMI.get(amal, amal)}» ruxsati yo'q. Admin bilan bog'laning.")


def katalog() -> list:
    """Sahifa uchun katalog: [{kod, nom, ikon, bandlar: [{kod, nom, izoh, amallar}]}]."""
    return [{"kod": m, "nom": mn, "ikon": ik,
             "bandlar": [{"kod": b, "nom": bn, "izoh": iz, "amallar": list(am),
                          "kerak": [{"band": kb, "amal": ka} for kb, ka in SAHIFA_KERAK.get(b, ((), ""))[0]],
                          "kerak_matn": SAHIFA_KERAK.get(b, ((), ""))[1]} for b, bn, iz, am in bl]}
            for m, mn, ik, bl in BOLIMLAR]


# Bosh sahifa (`/`) — Dashboard ruxsati bo'lmasa, birinchi ochiq sahifaga yo'naltiriladi (menyu tartibida). Eski qoida
# bilan AYNAN: Menejer va eski Usta — /orders, Omborchi — /inventory; Admin va Moliyachi — bosh sahifa.
YONALTIRISH = (
    ("/orders", (("buyurtma", "korish"), ("buyurtma_fayl", "yaratish"))),
    ("/inventory", (("material", "korish"),)),
    ("/finished", (("tayyor", "korish"), ("sotuv", "korish"))),
    ("/projects", (("loyiha", "korish"), ("loyiha_korsatkich", "korish"))),
    ("/returns", (("qaytarish", "korish"),)),
    ("/suppliers/receive", (("kirim", "yaratish"),)),
    ("/recipes", (("retsept", "korish"),)),
    ("/production", (("mahsulot_turi", "korish"),)),
    ("/kunlik-xarajat", (("kunlik", "korish"), ("kunlik", "yaratish"))),
    ("/ustalar", (("usta", "korish"),)),
    ("/finance", (("moliya", "korish"),)),
    ("/debts", (("qarz", "korish"),)),
    ("/kpi", (("kpi", "korish"),)),
    ("/reports", (("hisobot", "korish"),)),
    ("/trash", (("savat", "korish"),)),
    ("/logs", (("jurnal", "korish"),)),
)


def birinchi_sahifa(user):
    """Dashboard ruxsati bo'lmagan foydalanuvchi uchun birinchi ochiq sahifa (yo'q — None)."""
    for url, talab in YONALTIRISH:
        if any(bormi(user, b, a) for b, a in talab):
            return url
    return None


# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
# «TANNARX VA FOYDA» — ruxsati YO'Q foydalanuvchiga pul sirlari «—» (egasi QARORI kech118 18:4x, tugmali; QAYTA SO'RALMAYDI):
# «ruxsat yo'q — tannarx HAMMA joyda «—»» (Menejer / Omborchi hozir ko'radigan «tan: …», tayyor mahsulot «Ombor qiymati»,
# MRP «Taxminiy tannarx» ham); XARID narxi (material narxi, kirim summasi, ta'minotchi qarzi) — tannarxga KIRMAYDI.
# Server `/api/` JSON javobini foydalanuvchiga yuborishdan OLDIN tozalaydi (`main._TannarxHimoyasi`): qiymat `null` bo'ladi,
# sahifa uni «—» ko'rsatadi. O'LCHANGAN kalitlar (work/k119/tannarx_skan3.py / 4.py — boy baza, har GET API).
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════

# Har qanday chuqurlikda: shu nomli kalitning qiymati (son / matn; lug'at bo'lsa — ichidagi hamma qiymat) null bo'ladi.
TANNARX_KALITLAR = frozenset({
    # tannarx
    "tannarx", "taxminiy_tannarx", "tan_narxi", "cost_price", "cost_amount", "cost_per_unit", "cost_per_kg", "total_cost",
    "total_material_cost", "total_extra_cost", "line_cost", "loy_cost", "loy_cost_per_kg", "peno_cost", "penoplast_cost",
    "xomashyo_cost", "unit_cost", "stock_cost", "cost_price_per_unit", "cost_price_per_unit_no_coating",
    "narxsiz_tannarx_qiymati", "tannarx_jami", "tannarx_buyurtmalar", "tannarx_tm", "qaytarish_tannarx", "fp_sales_tannarx",
    "ishlab_chiqarish_xarajat", "brak_xarajat", "fp_loss_xarajat", "brak_total_value", "brak_month_value",
    # kech121 (zip 138 — G5-23): brak ulushi asosining tarkibi
    "buyurtmalar_tannarxi", "omborga_ishlab_tannarxi",
    # foyda
    "profit", "profit_per_unit", "margin", "today_profit", "total_profit", "yearly_profit", "monthly_profit", "foyda",
    "sof_foyda", "sof_daromad", "foyda_foiz", "buyurtmalar_foydasi", "fp_sales_foyda", "forecast_foyda", "current_foyda",
    "natija", "yonalishlar_natijasi", "moliya_sof_foyda", "moliya_sof_foyda_aniq", "rentabellik", "foydada_soni",
    "zararda_soni",
})

# Brak (xomashyo) va tayyor mahsulot yo'qotishi QIYMATI — tannarx bo'yicha baholanadi (ilgari ham «Brak qiymati» kartasi
# faqat tannarxni ko'radiganlarga edi): xarajat tarkibi qatorlarida ham «—».
_BRAK_QISMLAR = ("brak", "tm_yoqotish")


def _qism_yollari(*asoslar):
    return tuple(f"{a}.{q}" for a in asoslar for q in _BRAK_QISMLAR)


# Nomi umumiy (boshqa joyda tannarx EMAS) kalitlar — faqat shu marshrutda. Yo'l: "a.b", "[].x", "a[].b"; "a[k=v1|v2].x" —
# ro'yxatning faqat `k` maydoni v1 yoki v2 bo'lgan elementlari; "*~regex" — shu darajadagi (ichma-ich ham) regexga mos hamma
# kalit.
TANNARX_YOLLAR = {
    "/api/finance/daily": ("sales.cost",),
    "/api/finished/stats": ("produced_value", "returned_value", "total_value"),
    "/api/reports/brak-materials": ("by_material[].value", "by_order[].items[].value", "by_order[].total_value",
                                    "total_value"),
    "/api/reports/brak-tahlil": ("*~qiymat",),
    # ishlab chiqarish rejasi: xomashyo summasi, qo'shimcha xarajat, 1 birlik tannarxi — tannarx qismlari
    "/api/production/orders/preview": ("qatorlar[].summa", "xomashyo", "qoshimcha", "bir_birlik"),
    "/api/production/orders/{po_id}/preview": ("qatorlar[].summa", "xomashyo", "qoshimcha", "bir_birlik"),
    # retsept oynasi: 1 birlik taxminiy tannarxi (oddiy / qoplamali / hammasi bilan)
    "/api/production/boms/preview": ("qatorlar[].summa", "doim", "qoplamali", "hammasi"),
    # buyurtma «Tayyor»: usta KPI summasi — shu buyurtma FOYDASI × foiz (foydani ochib beradi)
    "/api/orders/{order_id}/ready": ("master_kpi.total_kpi",),
    "/api/finance/report": _qism_yollari("sof_foyda_tarkibi") + (f"xarajat_tarkibi[kalit={'|'.join(_BRAK_QISMLAR)}].summa",),
    "/api/finance/history": _qism_yollari("[].sof_foyda_tarkibi") + (
        f"[].xarajat_tarkibi[kalit={'|'.join(_BRAK_QISMLAR)}].summa",),
    # «jami xarajat (tannarx bilan)» va oldingi davr «xarajat» — tannarx ichida (ayirib topiladi)
    "/api/finance/yonalishlar": ("yonalishlar[].som.jami_xarajat", "yonalishlar[].aniq.jami_xarajat", "jami.jami_xarajat",
                                 "jami_aniq.jami_xarajat", "oldingi.xarajat", "ozgarish.xarajat",
                                 "yonalishlar[].som.bevosita", "yonalishlar[].aniq.bevosita") + _qism_yollari(
        "yonalishlar[].som.xarajat_qismlari", "yonalishlar[].aniq.xarajat_qismlari",
        "yonalishlar[].som.bevosita_qismlari", "yonalishlar[].aniq.bevosita_qismlari",
        "jami.xarajat_qismlari", "jami_aniq.xarajat_qismlari", "jami.bevosita_qismlari", "jami_aniq.bevosita_qismlari",
        "jami.umumiy_qismlari", "jami_aniq.umumiy_qismlari", "umumiy_xarajatlar") + (
        f"tarkib[kalit={'|'.join(_BRAK_QISMLAR)}].summa", f"tarkib[kalit={'|'.join(_BRAK_QISMLAR)}].foiz"),
}


def _tm_ombor_qiymati(data):
    """Tayyor mahsulot ro'yxati: `ombor_qiymati` — narxi bor partiyada qoldiq × SOTUV narxi (sir emas), narxsizda (MRP) —
    TANNARX: faqat narxsizlarda null."""
    for i in data if isinstance(data, list) else []:
        if isinstance(i, dict) and not (i.get("unit_price") or 0) and "ombor_qiymati" in i:
            i["ombor_qiymati"] = None


# Shartli qoida (maydon qiymati yozuvning boshqa maydoniga bog'liq) — marshrut → funksiya(data).
TANNARX_SHARTLI = {
    "/api/finished": _tm_ombor_qiymati,
}


# Hodim oyligi izohi (`services` — «Foydadan foiz» turi): «Foyda 673 774 × 5%» — MATN ichida foyda summasi. Umumiy `detail`
# kalitidagi shu naqsh — «Foyda — × 5%» (boshqa izohlar, xato matni — tegilmaydi).
_FOYDA_MATNI = __import__("re").compile(r"(Foyda )[-−]?\d[\d \u00a0\u202f.,]*( ×)")
MATN_KALITLAR = frozenset({"detail"})


def foyda_matni_yashir(s):
    """«Foyda 673 774 × 5%» → «Foyda — × 5%» (Jinja filtri `foyda_yashir` ham shu); matn bo'lmasa — o'zi."""
    return _FOYDA_MATNI.sub("\\1—\\2", s) if isinstance(s, str) else s


def _hammasini_null(v):
    if isinstance(v, dict):
        return {k: _hammasini_null(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_hammasini_null(x) for x in v]
    return None


def _kalit_tozala(x):
    if isinstance(x, dict):
        for k in list(x):
            v = x[k]
            if k in TANNARX_KALITLAR and not isinstance(v, bool):
                x[k] = _hammasini_null(v) if isinstance(v, (dict, list)) else None
            elif k in MATN_KALITLAR and isinstance(v, str):
                x[k] = foyda_matni_yashir(v)
            else:
                _kalit_tozala(v)
    elif isinstance(x, list):
        for v in x:
            _kalit_tozala(v)


def _yol_tozala(x, qismlar):
    import re as _re
    if x is None or not qismlar:
        return
    q = qismlar[0]
    if q.startswith("*~"):
        rx = _re.compile(q[2:])

        def _ichki(y):
            if isinstance(y, dict):
                for k in list(y):
                    if rx.search(str(k)) and not isinstance(y[k], (dict, list, bool)):
                        y[k] = None
                    else:
                        _ichki(y[k])
            elif isinstance(y, list):
                for v in y:
                    _ichki(v)
        _ichki(x)
        return
    _f = _re.fullmatch(r"(\w*)\[(\w+)=([\w|]+)\]", q)
    if _f:
        k, fk, fq = _f.group(1), _f.group(2), set(_f.group(3).split("|"))
        royxat_ = x if k == "" else (x.get(k) if isinstance(x, dict) else None)
        if isinstance(royxat_, list):
            for v in royxat_:
                if isinstance(v, dict) and str(v.get(fk)) in fq:
                    _yol_tozala(v, qismlar[1:])
        return
    royxat = q.endswith("[]")
    k = q[:-2] if royxat else q
    if k == "":
        if isinstance(x, list):
            for v in x:
                _yol_tozala(v, qismlar[1:])
        return
    if not isinstance(x, dict) or k not in x:
        return
    if royxat:
        if isinstance(x[k], list):
            for v in x[k]:
                _yol_tozala(v, qismlar[1:])
        return
    if len(qismlar) == 1:
        if not isinstance(x[k], bool):
            x[k] = _hammasini_null(x[k]) if isinstance(x[k], (dict, list)) else None
        return
    _yol_tozala(x[k], qismlar[1:])


def _yol_qismlari(yol):
    """"yonalishlar[].som.x" → ["yonalishlar[]", "som", "x"]; "[].x" → ["[]", "x"]; "*~regex" — bitta qism."""
    if yol.startswith("*~"):
        return [yol]
    return [p for p in yol.split(".") if p != ""]


def tannarx_tozala(data, marshrut: str = None):
    """«Tannarx va foyda» ruxsati yo'q foydalanuvchi uchun javobni JOYIDA tozalaydi va qaytaradi: TANNARX_KALITLAR (har qanday
    chuqurlikda), shu marshrutning TANNARX_YOLLAR va TANNARX_SHARTLI — null."""
    _kalit_tozala(data)
    for yol in TANNARX_YOLLAR.get(marshrut or "", ()):
        _yol_tozala(data, _yol_qismlari(yol))
    if marshrut in TANNARX_SHARTLI:
        TANNARX_SHARTLI[marshrut](data)
    return data


# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
# «XOMASHYO NARXLARI VA OMBOR QIYMATI» (kech127, zip 150 — egasi QARORI 07.10 20:1x, tugmali; QAYTA SO'RALMAYDI:
# «Ulugbek va Mirjalol (Menejer) xomashyo xarid narxlari va «Ombor qiymati» ni ham ko'rmasin»). O'LCHANGAN (`work/narx127.py`,
# `main` ning ko'chirilgan nusxasi, Menejer nomidan HAMMA GET marshrut, QIYMAT bo'yicha qidiruv — material narxi, xarid summasi,
# ombor qiymati): sir faqat quyidagi marshrutlarda edi; sahifalarda — Omborxona «Ombor qiymati» / narx ustuni (ilgari
# «Materiallar: Tahrirlash» sharti), Buyurtmalar va Tayyor mahsulotlar sahifasiga yozilgan penoplast narxi (`PENOPLASTS`,
# `PENOS`). Ta'minotchilar bo'limi (`taminotchi`) — o'z ruxsati (ta'minotchi qarzi, undan olingan xaridlar) — bu yerga kirmaydi.
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════

NARX_YOLLAR = {
    "/api/inventory": ("[].price_per_unit",),
    "/api/inventory/kpi": ("total_value",),
    "/api/inventory/purchases": ("[].price_per_unit", "[].total_amount"),
    "/api/inventory/purchase-stats": ("total_amount", "by_material[].total", "by_material[].avg_price"),
    "/api/inventory/purchase-trend": ("months[].total",),
    "/api/penoplasts": ("items[].price_per_unit",),
    "/api/loy-cost": ("breakdown[].price",),
}

# Migratsiya belgisi (korxona sozlamasi): shu korxona rollari yangi band bilan bir marta ko'rib chiqilgan — admin keyin
# o'chirgan ruxsat qayta qo'shilmaydi; rollari HOZIRGI andozadan yaratilgan korxona (`auth.tayyor_rollar`) — darhol belgilanadi.
NARX_MIGRATSIYA_KALITI = "rx_material_narx"


def narx_koradi(user) -> bool:
    """Xomashyo narxi va ombor qiymatini ko'radimi: «Xomashyo narxlari va ombor qiymati» YOKI «Tannarx va foyda» ruxsati
    (tannarx shu narxlardan hisoblanadi — tannarxni ko'rgan narxni ham bilib oladi; sahifa kalkulyatorlari narxsiz noto'g'ri
    tannarx chiqarardi). Admin — doim."""
    return bormi(user, "material_narx", "korish") or bormi(user, "tannarx", "korish")


def material_narx_kerakmi(kod, ruxsat: dict) -> bool:
    """Migratsiya qoidasi (yangi band qo'shilganda MAVJUD rol uchun bir marta): narx bilan ishlaydigan rol — avvalgidek ko'radi.
    Tayyor Omborchi / Moliyachi (andozada bor); o'zi yaratilgan rol — material / kirim YARATISH, TAHRIRLASH yoki O'CHIRISH
    (narx kiritadi / tuzatadi), ta'minotchi yoki Moliya KO'RISH. Faqat ko'radigan rol (Menejer: «Materiallar: Ko'rish»,
    «Xomashyo kirimi: Ko'rish») — yo'q (egasi qarori)."""
    if kod in ("omborchi", "moliyachi"):
        return True
    if kod in ("admin", "menejer", "usta"):
        return False
    yt = {"yaratish", "tahrirlash", "ochirish"}
    return bool((set(ruxsat.get("material") or ()) & yt) or (set(ruxsat.get("kirim") or ()) & yt)
                or "korish" in set(ruxsat.get("taminotchi") or ()) or "korish" in set(ruxsat.get("moliya") or ()))


def narx_tozala(data, marshrut: str = None):
    """«Xomashyo narxlari va ombor qiymati» ko'rmaydigan foydalanuvchi uchun javobni JOYIDA tozalaydi (shu marshrutning
    NARX_YOLLAR — null) va qaytaradi."""
    for yol in NARX_YOLLAR.get(marshrut or "", ()):
        _yol_tozala(data, _yol_qismlari(yol))
    return data
