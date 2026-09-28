"""
obuna.py — PLATFORMA: korxona obunasi, bloklash, eslatmalar (kech111 — admin paneli KODI).

YAGONA MANBA. Korxonaning holati (faol / muddati yaqin / muddati o'tgan / bloklangan / muddatsiz), kirish rad
etiladimi, bloklash / ochish / uzaytirish, kunlik tekshiruv (eslatma va avtomatik bloklash), mijoz dasturidagi
ogohlantirish (banner) va platforma panelining ro'yxati — HAMMASI shu moduldan. Formula boshqa joyda qayta
yozilmaydi (loyiha saboqlari: "formula nusxalanmaydi — mavjud funksiya chaqiriladi").

EGASI QARORLARI (QAYTA SO'RALMAYDI):
  kech109 — bloklash / ochish, korxona faolligi, obuna muddati; korxona ma'lumotini platformadan tahrirlash — YO'Q.
  kech110 — ko'rinish "B — Kartochkalar"; eslatma "Sizga + mijozga" (egasiga Telegram, mijoz dasturida
            ogohlantirish); muddat o'tsa "3 kundan keyin avtomatik" bloklanadi; avtomatik bloklanganni muddatni
            uzaytirmasdan «Ochish» — "3 kunlik imtiyoz"; bloklangan sahifadagi telefon — "Sozlamada yozaman"
            (platforma panelidagi «Aloqa telefoni»); yangi korxona — 30 kunlik SINOV davri; foydalanuvchi limiti — yo'q.
  kech111 — uzaytirish "Aralash" (muddat hali tugamagan — eski sanadan davom etadi; tugagan — bugundan);
            ogohlantirishni kim ko'radi — "Admin, keyin hamma" (7 kun qolganda faqat korxona adminlari; muddat
            tugagach — 3 kunlik imtiyozda — barcha xodimlar, chunki kirish hammaga yopiladi).

MUDDAT QOIDASI (Toshkent kalendari — `database.tashkent_date()`; texnik — Claude):
  `obuna_tugash` (E) — obunaning OXIRGI to'langan kuni (shu kun ham ishlaydi); NULL — muddatsiz.
  E+1 … E+3 — imtiyoz (kirish OCHIQ, hamma xodimga qizil ogohlantirish); E+4 dan — avtomatik yopiladi.
  «Ochish» (muddat uzaytirilmasdan, imtiyozdan keyin) — `imtiyoz_gacha` = bugun + 3: yana 3 kun ochiq, so'ng yopiladi.
  Avtomatik yopilish HAR SO'ROVDA hisoblanadi (kunlik ish o'tkazib yuborilsa ham kirish yopiladi) — kunlik ish uni
  bazaga yozadi, sessiyalarni yopadi va egasiga xabar beradi.
  Bloklash ma'lumotni O'CHIRMAYDI; platforma egasining o'z korxonasi (platforma admini bor korxona) — muddatsiz,
  bloklanmaydi, ro'yxatda alohida.
"""
import calendar
from datetime import date, datetime, timedelta

SINOV_KUN = 30              # yangi korxona sinov davri (kech110 qarori)
IMTIYOZ_KUN = 3             # muddatdan keyingi / «Ochish» dan keyingi imtiyoz (kech110 qarori)
ESLATMA_KUN = 7             # shu kun qolganda — sariq ogohlantirish va egasiga xabar
BLOK_SABABLARI = ("To'lov qilinmagan", "Mijoz o'zi so'radi", "Boshqa")
AVTO_SABAB = "Obuna muddati o'tdi (avtomatik)"
AVTO_KIM = "Tizim (avtomatik)"
TELEFON_KALIT = "platforma_aloqa_telefoni"
BLOK_SARLAVHA = "X-Korxona-Bloklangan"      # 403 javobini sahifada /login ga yo'naltirish uchun belgi
IZOH_MAX = 500
UZAYTIRISH_OYLAR = (1, 3, 6, 12)
_BOSQICH_DARAJA = {"7": 1, "1": 2, "tugadi": 3, "bloklandi": 4}


def bugun():
    """Toshkent kalendar kuni (`date`). Testlar shu funksiyani almashtirib "bugun" ni belgilaydi."""
    from database import tashkent_date
    return tashkent_date()


def oy_qosh(sana, oylar):
    """Sanaga kalendar oylar qo'shadi; oy oxiri siqiladi (31.01 + 1 oy → 28/29.02)."""
    oy0 = sana.month - 1 + int(oylar)
    yil = sana.year + oy0 // 12
    oy = oy0 % 12 + 1
    kun = min(sana.day, calendar.monthrange(yil, oy)[1])
    return date(yil, oy, kun)


def sana_matn(s):
    return s.strftime("%d.%m.%Y") if s else ""


def _sana(v):
    """`date` / `datetime` / ISO matn → `date` (bazadan kelgan qiymat har xil bo'lishi mumkin)."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


# ══════════════════════════════════════════════════════════════
# HOLAT — yagona hisob
# ══════════════════════════════════════════════════════════════
def holat(c, kun=None):
    """Korxonaning obuna / blok holati (`Company` qatori bo'yicha, bazaga YOZMAYDI).

    Qaytaradi: bosqich ('faol' | 'yaqin' | 'otgan' | 'bloklangan' | 'muddatsiz'), bloklangan (bool),
    avtomatik (bloklangan bo'lsa — muddat sababli), qolgan_kun (E − bugun; muddatsiz — None), yopilish_kuni
    (kirish yopiladigan birinchi kun; bloklangan / muddatsiz — None), yopilishga (shu kungacha kun),
    sinov (sinov davri), obuna_boshi, obuna_tugash, davr_kun, imtiyoz_gacha, sabab, bloklangan_at, bloklagan."""
    kun = kun or bugun()
    e = _sana(getattr(c, "obuna_tugash", None))
    imt = _sana(getattr(c, "imtiyoz_gacha", None))
    boshi = _sana(getattr(c, "obuna_boshi", None))
    qolda = getattr(c, "bloklangan_at", None) is not None
    oxirgi = None                        # kirish OCHIQ bo'lgan oxirgi kun
    if e is not None:
        oxirgi = e + timedelta(days=IMTIYOZ_KUN)
        if imt is not None and imt > oxirgi:
            oxirgi = imt
    hisob_avto = e is not None and kun > oxirgi
    bloklangan = qolda or hisob_avto
    if qolda:
        avtomatik = bool(getattr(c, "blok_avtomatik", False))
        sabab = getattr(c, "blok_sabab", None) or ("" if not avtomatik else AVTO_SABAB)
    elif hisob_avto:
        avtomatik, sabab = True, AVTO_SABAB
    else:
        avtomatik, sabab = False, None
    qolgan = (e - kun).days if e is not None else None
    if bloklangan:
        bosqich = "bloklangan"
    elif e is None:
        bosqich = "muddatsiz"
    elif kun > e:
        bosqich = "otgan"
    elif qolgan <= ESLATMA_KUN:
        bosqich = "yaqin"
    else:
        bosqich = "faol"
    yopilish_kuni = (oxirgi + timedelta(days=1)) if (e is not None and not bloklangan) else None
    return {
        "bosqich": bosqich,
        "bloklangan": bloklangan,
        "avtomatik": avtomatik,
        "sabab": sabab,
        "qolgan_kun": qolgan,
        "yopilish_kuni": yopilish_kuni,
        "yopilishga": (yopilish_kuni - kun).days if yopilish_kuni else None,
        "sinov": (getattr(c, "obuna_turi", None) == "sinov") and e is not None,
        "obuna_boshi": boshi,
        "obuna_tugash": e,
        # kartochkadagi chiziq: qolgan_kun / davr_kun (joriy davr uzunligi, kunlarda); boshi noma'lum — None
        "davr_kun": (e - boshi).days if (e is not None and boshi is not None and e > boshi) else None,
        "imtiyoz_gacha": imt,
        "bloklangan_at": getattr(c, "bloklangan_at", None),
        "bloklagan": getattr(c, "bloklagan", None) if qolda else (AVTO_KIM if hisob_avto else None),
    }


def holat_json(h):
    """`holat()` natijasi — API uchun (sanalar ISO matn)."""
    out = {}
    for k, v in h.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, date):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


# ══════════════════════════════════════════════════════════════
# PLATFORMA EGASI va ALOQA TELEFONI
# ══════════════════════════════════════════════════════════════
def platforma_korxonalari(db):
    """Platforma egasining korxona(lar)i — platforma admini (`users.is_platform_admin`) bor korxonalar.
    Ular muddatsiz, bloklanmaydi, uzaytirilmaydi. Tizim so'rovi (TENANT_FILTER=1 da ham hamma korxona)."""
    import tenant_context as _tc
    from models import User
    with _tc.system_context(db):
        rows = (db.query(User.company_id)
                .filter(User.is_platform_admin == True)            # noqa: E712
                .distinct().all())
    return {r[0] for r in rows if r[0] is not None}


def aloqa_telefoni(db):
    """Bloklangan korxonaga ko'rsatiladigan platforma aloqa telefoni (egasi panelda yozadi).
    Yozilmagan bo'lsa — platforma egasi korxonasining hujjatlardagi telefoni; u ham bo'lmasa — bo'sh."""
    import tenant_context as _tc
    from models import CompanySetting
    from production_models import Company
    egalar = sorted(platforma_korxonalari(db))
    if not egalar:
        return ""
    with _tc.system_context(db):
        row = (db.query(CompanySetting)
               .filter(CompanySetting.company_id.in_(egalar), CompanySetting.key == TELEFON_KALIT)
               .order_by(CompanySetting.company_id).first())
        if row is not None and (row.value or "").strip():
            return row.value.strip()
        eg = db.query(Company).filter(Company.id == egalar[0]).first()
    return ((getattr(eg, "phone", None) or "").strip()) if eg is not None else ""


def aloqa_telefoni_saqla(db, company_id, telefon):
    """Platforma aloqa telefonini platforma egasi korxonasining sozlamasiga yozadi (bo'sh — tozalaydi)."""
    import crud
    t = (telefon or "").strip()
    if len(t) > 60:
        raise ValueError("Telefon juda uzun (60 belgidan ko'p)")
    crud.set_setting(db, TELEFON_KALIT, t, company_id=company_id)
    return t


# ══════════════════════════════════════════════════════════════
# KIRISH — auth, login, hodim paneli, Telegram bot shu yerdan so'raydi
# ══════════════════════════════════════════════════════════════
def korxona_holati(db, company_id, kun=None):
    """(Company, holat) — korxona topilmasa (None, None)."""
    from production_models import Company
    if company_id is None:
        return None, None
    c = db.query(Company).filter(Company.id == company_id).first()
    if c is None:
        return None, None
    return c, holat(c, kun)


def blok_xabari(db, h=None):
    """Bloklangan korxona foydalanuvchisiga ko'rsatiladigan xabar (login, hodim paneli, bot, API 403)."""
    tel = aloqa_telefoni(db)
    m = "Korxonangiz hisobi vaqtincha to'xtatilgan."
    if h and h.get("avtomatik"):
        m += " Obuna muddati tugagan."
    m += " Ma'lumotlaringiz saqlangan. Qayta ochish uchun xizmat ko'rsatuvchi bilan bog'laning"
    m += (": " + tel) if tel else "."
    return m


def kirish_rad_sababi(db, company_id, kun=None):
    """Korxona bloklangan bo'lsa — (xabar, belgi '1' qo'lda / '2' avtomatik); aks holda None.
    Platforma admini uchun chaqirilmaydi (chaqiruvchi tekshiradi)."""
    c, h = korxona_holati(db, company_id, kun)
    if h is None or not h["bloklangan"]:
        return None
    return blok_xabari(db, h), ("2" if h["avtomatik"] else "1")


# ══════════════════════════════════════════════════════════════
# AMALLAR — bloklash / ochish / uzaytirish / sinov davri
# ══════════════════════════════════════════════════════════════
class ObunaXato(ValueError):
    """Platforma amali rad etildi (400 — sababi matnda)."""


def _jurnal(db, c, action, matn, kim, eski=None):
    import crud
    crud.log_activity(db, action, "company", c.id, f"Korxona «{c.name}»",
                      performed_by=kim, old_value=eski, new_value=matn, company_id=c.id, commit=False)


def sessiyalarni_yop(db, company_id):
    """Korxonaning BARCHA ochiq sessiyalari (foydalanuvchi va hodim paneli) o'chiriladi — bloklash darhol ta'sir qiladi."""
    import tenant_context as _tc
    from models import User, UserSession, Employee, EmployeeSession
    with _tc.system_context(db):
        uids = [r[0] for r in db.query(User.id).filter(User.company_id == company_id).all()]
        eids = [r[0] for r in db.query(Employee.id).filter(Employee.company_id == company_id).all()]
        n_u = n_e = 0
        if uids:
            n_u = (db.query(UserSession).filter(UserSession.user_id.in_(uids))
                   .delete(synchronize_session=False))
        if eids:
            n_e = (db.query(EmployeeSession).filter(EmployeeSession.employee_id.in_(eids))
                   .delete(synchronize_session=False))
    return n_u, n_e


def _egasi_emas(db, c):
    if c.id in platforma_korxonalari(db):
        raise ObunaXato("Platforma egasining o'z korxonasi bloklanmaydi va muddati yo'q")


def blokla(db, c, sabab, izoh, kim, avtomatik=False):
    """Korxonani bloklaydi: kirish, API, hodim paneli, Telegram bot yopiladi; ma'lumot O'CHMAYDI.
    Commit — chaqiruvchida (bitta tranzaksiya)."""
    _egasi_emas(db, c)
    if getattr(c, "bloklangan_at", None) is not None:
        raise ObunaXato("Korxona allaqachon bloklangan")
    sabab = (sabab or "").strip()
    if not avtomatik and sabab not in BLOK_SABABLARI:
        raise ObunaXato("Sababni ro'yxatdan tanlang: " + ", ".join(BLOK_SABABLARI))
    izoh = (izoh or "").strip()
    if len(izoh) > IZOH_MAX:
        raise ObunaXato(f"Izoh juda uzun ({IZOH_MAX} belgidan ko'p)")
    c.bloklangan_at = datetime.utcnow()
    c.blok_sabab = AVTO_SABAB if avtomatik else sabab
    c.blok_izoh = izoh or None
    c.bloklagan = AVTO_KIM if avtomatik else (kim or "")[:100]
    c.blok_avtomatik = bool(avtomatik)
    n_u, n_e = sessiyalarni_yop(db, c.id)
    matn = f"Bloklandi — sabab: {c.blok_sabab}"
    if c.obuna_tugash:
        matn += f"; obuna {sana_matn(_sana(c.obuna_tugash))} gacha edi"
    _jurnal(db, c, "blocked", matn, c.bloklagan)
    return {"sessiyalar": n_u, "hodim_sessiyalari": n_e}


def och(db, c, kim, kun=None):
    """Blokni ochadi. Obuna muddati imtiyozdan ham o'tgan bo'lsa — 3 kunlik imtiyoz beriladi (kech110 qarori),
    shu kunlarda uzaytirilmasa — yana avtomatik yopiladi."""
    kun = kun or bugun()
    _egasi_emas(db, c)
    h = holat(c, kun)
    if not h["bloklangan"]:
        raise ObunaXato("Korxona bloklanmagan")
    eski = f"Bloklangan — {h['sabab'] or ''}".strip(" —")
    c.bloklangan_at = None
    c.blok_sabab = None
    c.blok_izoh = None
    c.bloklagan = None
    c.blok_avtomatik = None
    c.eslatma_holati = None
    matn = "Ochildi"
    e = _sana(c.obuna_tugash)
    if e is not None and kun > e + timedelta(days=IMTIYOZ_KUN):
        c.imtiyoz_gacha = kun + timedelta(days=IMTIYOZ_KUN)
        matn += (f" — {IMTIYOZ_KUN} kunlik imtiyoz: {sana_matn(c.imtiyoz_gacha)} gacha"
                 f" (muddat uzaytirilmasa — yana avtomatik yopiladi)")
    _jurnal(db, c, "unblocked", matn, kim, eski=eski)
    return {"imtiyoz_gacha": _sana(c.imtiyoz_gacha).isoformat() if c.imtiyoz_gacha else None}


def uzaytirish_sanasi(c, oylar=None, sana=None, kun=None):
    """Yangi obuna tugash sanasi (BAZAGA YOZMAYDI) — «Aralash» qoida (kech111 qarori): muddat hali tugamagan
    (E ≥ bugun) — E dan davom etadi; tugagan yoki muddatsiz — bugundan. Aniq sana — o'sha kun (bugundan oldin — rad)."""
    kun = kun or bugun()
    if sana is not None:
        s = _sana(sana)
        if s is None:
            raise ObunaXato("Sana noto'g'ri (YYYY-MM-DD)")
        if s < kun:
            raise ObunaXato("Sana bugundan oldin bo'lmasin")
        return s
    try:
        n = int(oylar)
    except (TypeError, ValueError):
        raise ObunaXato("Muddatni tanlang: " + " / ".join(f"+{x} oy" for x in UZAYTIRISH_OYLAR))
    if n not in UZAYTIRISH_OYLAR:
        raise ObunaXato("Muddatni tanlang: " + " / ".join(f"+{x} oy" for x in UZAYTIRISH_OYLAR))
    e = _sana(getattr(c, "obuna_tugash", None))
    asos = e if (e is not None and e >= kun) else kun
    return oy_qosh(asos, n)


def uzaytir(db, c, kim, oylar=None, sana=None, kun=None):
    """Obunani uzaytiradi (to'lov olindi): sinov davri tugaydi, imtiyoz va eslatma belgisi tozalanadi,
    AVTOMATIK blok ochiladi (qo'lda bloklangan korxona — «Ochish» bilan alohida)."""
    kun = kun or bugun()
    _egasi_emas(db, c)
    yangi = uzaytirish_sanasi(c, oylar=oylar, sana=sana, kun=kun)
    eski_e = _sana(c.obuna_tugash)
    eski = (f"{'Sinov davri' if c.obuna_turi == 'sinov' else 'Obuna'} {sana_matn(eski_e)} gacha"
            if eski_e else "Muddatsiz")
    h = holat(c, kun)
    c.obuna_boshi = kun
    c.obuna_tugash = yangi
    c.obuna_turi = "obuna"
    c.imtiyoz_gacha = None
    c.eslatma_holati = None
    ochildi = False
    if h["bloklangan"] and h["avtomatik"]:
        c.bloklangan_at = None
        c.blok_sabab = None
        c.blok_izoh = None
        c.bloklagan = None
        c.blok_avtomatik = None
        ochildi = True
    matn = f"Obuna {sana_matn(yangi)} gacha" + (" (avtomatik blok ochildi)" if ochildi else "")
    _jurnal(db, c, "extended", matn, kim, eski=eski)
    return {"obuna_tugash": yangi.isoformat(), "ochildi": ochildi}


def sinov_ber(c, kun=None):
    """Yangi korxona — 30 kunlik sinov davri (kech110 qarori)."""
    kun = kun or bugun()
    c.obuna_boshi = kun
    c.obuna_tugash = kun + timedelta(days=SINOV_KUN)
    c.obuna_turi = "sinov"
    return c.obuna_tugash


# ══════════════════════════════════════════════════════════════
# KUNLIK TEKSHIRUV — avtomatik bloklash va egasiga eslatma (takrorsiz)
# ══════════════════════════════════════════════════════════════
def _bosqich_kaliti(h):
    """Egasiga xabar bosqichi: '7' (≤ 7 kun), '1' (≤ 1 kun), 'tugadi' (imtiyoz), 'bloklandi' (avtomatik); aks holda None."""
    if h["bloklangan"]:
        return "bloklandi" if h["avtomatik"] else None
    if h["bosqich"] == "otgan":
        return "tugadi"
    if h["bosqich"] == "yaqin":
        return "1" if h["qolgan_kun"] <= 1 else "7"
    return None


def _yuborilganmi(c, e, bosqich):
    """`eslatma_holati` = "<E ISO>:<bosqich>" — shu muddat uchun shu yoki kuchliroq bosqich yuborilganmi."""
    s = (getattr(c, "eslatma_holati", None) or "").strip()
    if ":" not in s:
        return False
    se, sb = s.rsplit(":", 1)
    return se == e.isoformat() and _BOSQICH_DARAJA.get(sb, 0) >= _BOSQICH_DARAJA[bosqich]


def _egasi_xabari(c, h, bosqich):
    turi = "Sinov davri" if h["sinov"] else "Obuna"
    e = sana_matn(h["obuna_tugash"])
    if bosqich == "7":
        return (f"⏳ *{c.name}* — {turi.lower()} {h['qolgan_kun']} kundan keyin tugaydi ({e}).\n"
                f"To'lovni eslating; uzaytirish — Platforma paneli.")
    if bosqich == "1":
        qachon = "BUGUN" if h["qolgan_kun"] == 0 else "ERTAGA"
        return f"⚠️ *{c.name}* — {turi.lower()} {qachon} tugaydi ({e})."
    if bosqich == "tugadi":
        return (f"⛔ *{c.name}* — {turi.lower()} {e} da tugadi. Kirish {sana_matn(h['yopilish_kuni'])} dan "
                f"avtomatik yopiladi ({h['yopilishga']} kundan keyin), agar uzaytirilmasa.")
    return (f"🔒 *{c.name}* — {turi.lower()} muddati o'tgani uchun kirish AVTOMATIK yopildi.\n"
            f"Ma'lumotlar saqlangan. Ochish yoki uzaytirish — Platforma paneli.")


def kunlik_tekshiruv(db, kun=None, yubor=None):
    """Har kuni (Toshkent 09:05): imtiyozdan o'tgan korxonalarni BAZADA bloklaydi (sessiyalar yopiladi, jurnal) va
    egasiga eslatma yuboradi — 7 kun / 1 kun qolganda, muddat tugaganda, avtomatik bloklanganda; har bosqich shu
    muddat uchun BIR MARTA (`eslatma_holati`). Kun o'tkazib yuborilsa — keyingi ishda joriy bosqich yuboriladi.
    `yubor(matn)` — egasiga Telegram (berilmasa — faqat bazaga yoziladi). Qaytaradi: amallar ro'yxati."""
    from production_models import Company
    kun = kun or bugun()
    egalar = platforma_korxonalari(db)
    natija = []
    for c in db.query(Company).order_by(Company.id).all():
        if c.id in egalar:
            continue
        try:
            natija.extend(_korxona_kunlik(db, c, kun, yubor))
        except Exception as ex:                        # noqa: BLE001 — bitta korxona nosozligi qolganlarini to'xtatmasin
            db.rollback()
            print(f"⚠ Obuna tekshiruvi ({getattr(c, 'name', c.id)}): {ex}")
            natija.append({"korxona": c.id, "amal": "xato", "xato": str(ex)[:200]})
    return natija


def _korxona_kunlik(db, c, kun, yubor):
    """Bitta korxonaning kunlik tekshiruvi (`kunlik_tekshiruv` ichida, o'z commit lari bilan)."""
    out = []
    h = holat(c, kun)
    e = h["obuna_tugash"]
    if e is None:
        return out
    if h["bloklangan"] and h["avtomatik"] and c.bloklangan_at is None:
        blokla(db, c, AVTO_SABAB, None, AVTO_KIM, avtomatik=True)
        db.commit()
        out.append({"korxona": c.id, "amal": "bloklandi"})
        h = holat(c, kun)
    bosqich = _bosqich_kaliti(h)
    if bosqich is None or _yuborilganmi(c, e, bosqich):
        return out
    matn = _egasi_xabari(c, h, bosqich)
    yuborildi = False
    if yubor is not None:
        try:
            yubor(matn)
            yuborildi = True
        except Exception as ex:                        # noqa: BLE001
            print(f"⚠ Obuna eslatmasi yuborilmadi ({c.name}): {ex}")
    c.eslatma_holati = f"{e.isoformat()}:{bosqich}"
    db.commit()
    out.append({"korxona": c.id, "amal": "eslatma", "bosqich": bosqich, "yuborildi": yuborildi, "matn": matn})
    return out


# ══════════════════════════════════════════════════════════════
# MIJOZ DASTURIDAGI OGOHLANTIRISH (base.html)
# ══════════════════════════════════════════════════════════════
def banner(db, user, kun=None):
    """Korxona foydalanuvchisiga ogohlantirish (kech111 qarori "Admin, keyin hamma"):
    muddatga ≤ 7 kun — faqat korxona ADMINLARIGA sariq; muddat tugagan (imtiyoz) — HAMMAGA qizil.
    Qaytaradi {"daraja": "sariq"|"qizil", "matn": to'liq matn, "qisqa": yuqori paneldagi qisqa yozuv} yoki None."""
    if user is None or getattr(user, "is_platform_admin", False):
        return None
    c, h = korxona_holati(db, getattr(user, "company_id", None), kun)
    if h is None or h["obuna_tugash"] is None or h["bloklangan"]:
        return None
    tel = aloqa_telefoni(db)
    aloqa = (" Bog'lanish: " + tel) if tel else ""
    turi = "Sinov davri" if h["sinov"] else "Obunangiz"
    if h["bosqich"] == "otgan":
        n = h["yopilishga"]
        qachon = "ertaga" if n == 1 else f"{n} kundan keyin"
        return {"daraja": "qizil",
                "matn": (f"{turi} muddati {sana_matn(h['obuna_tugash'])} da tugadi — kirish {qachon} "
                         f"({sana_matn(h['yopilish_kuni'])}) yopiladi. Ma'lumotlar saqlanadi.{aloqa}"),
                "qisqa": f"Obuna tugadi — kirish {qachon} yopiladi"}
    if h["bosqich"] == "yaqin":
        rol = getattr(getattr(user, "role", None), "value", getattr(user, "role", None))
        if rol != "admin":
            return None
        q = h["qolgan_kun"]
        qachon = "bugun" if q == 0 else ("ertaga" if q == 1 else f"{q} kundan keyin")
        return {"daraja": "sariq",
                "matn": f"{turi} {qachon} tugaydi ({sana_matn(h['obuna_tugash'])}).{aloqa}",
                "qisqa": f"{'Sinov davri' if h['sinov'] else 'Obuna'} {qachon} tugaydi"}
    return None


# ══════════════════════════════════════════════════════════════
# PLATFORMA PANELI — ro'yxat, raqamlar, xatolar
# ══════════════════════════════════════════════════════════════
def korxonalar_royxati(db, kun=None):
    """Hamma korxonalar: holat + faollik (foydalanuvchilar, shu oy / jami buyurtmalar, oxirgi kirish).
    Tizim so'rovlari (TENANT_FILTER=1 da ham hamma korxona), guruhlangan — korxona soniga qarab so'rovlar ko'paymaydi."""
    import tenant_context as _tc
    from sqlalchemy import func
    from database import tashkent_oyida
    from models import User, Order, OrderStatus, LoginHistory, Employee, EmployeeSession
    from production_models import Company
    kun = kun or bugun()
    egalar = platforma_korxonalari(db)
    with _tc.system_context(db):
        foyd = dict(db.query(User.company_id, func.count(User.id))
                    .filter(User.is_active == True).group_by(User.company_id).all())   # noqa: E712
        _faol_buyurtma = (Order.is_deleted.isnot(True), Order.status != OrderStatus.DRAFT)
        jami = dict(db.query(Order.company_id, func.count(Order.id))
                    .filter(*_faol_buyurtma).group_by(Order.company_id).all())
        shu_oy = dict(db.query(Order.company_id, func.count(Order.id))
                      .filter(*_faol_buyurtma, tashkent_oyida(Order.created_at, kun.year, kun.month))
                      .group_by(Order.company_id).all())
        kirish = dict(db.query(LoginHistory.company_id, func.max(LoginHistory.created_at))
                      .filter(LoginHistory.success == True)                             # noqa: E712
                      .group_by(LoginHistory.company_id).all())
        hodim = dict(db.query(Employee.company_id, func.max(EmployeeSession.created_at))
                     .join(EmployeeSession, EmployeeSession.employee_id == Employee.id)
                     .group_by(Employee.company_id).all())
        rows = db.query(Company).order_by(Company.id).all()
    out = []
    for c in rows:
        h = holat(c, kun)
        k1, k2 = kirish.get(c.id), hodim.get(c.id)
        oxirgi = max([x for x in (k1, k2) if x is not None], default=None)
        out.append({
            "id": c.id, "name": c.name, "code": c.code,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "users": int(foyd.get(c.id, 0) or 0),
            "buyurtma_shu_oy": int(shu_oy.get(c.id, 0) or 0),
            "buyurtma_jami": int(jami.get(c.id, 0) or 0),
            "oxirgi_kirish": oxirgi.isoformat() if oxirgi else None,
            "platforma_egasi": c.id in egalar,
            "blok_izoh": getattr(c, "blok_izoh", None),
            "holat": holat_json(h),
        })
    return out


def platforma_raqamlari(db, royxat=None, kun=None):
    """Kartochkalar tepasidagi raqamlar: mijoz korxonalar (platforma egasisiz) holati, bugungi kirishlar va xatolar."""
    import tenant_context as _tc
    from database import tashkent_kunida
    from models import LoginHistory, ErrorLog
    kun = kun or bugun()
    royxat = royxat if royxat is not None else korxonalar_royxati(db, kun)
    mijoz = [r for r in royxat if not r["platforma_egasi"]]
    bosq = [r["holat"]["bosqich"] for r in mijoz]
    kun_boshi = datetime(kun.year, kun.month, kun.day)
    with _tc.system_context(db):
        kirish = (db.query(LoginHistory).filter(LoginHistory.success == True,               # noqa: E712
                                                tashkent_kunida(LoginHistory.created_at, kun)).count())
        # ErrorLog.created_at — ALLAQACHON Toshkent vaqti (models._uzb_now), shuning uchun kun oralig'i to'g'ridan-to'g'ri.
        xato = (db.query(ErrorLog).filter(ErrorLog.created_at >= kun_boshi,
                                          ErrorLog.created_at < kun_boshi + timedelta(days=1)).count())
    return {
        "jami": len(mijoz),
        "faol": sum(1 for b in bosq if b in ("faol", "muddatsiz")),
        "muddati_yaqin": sum(1 for b in bosq if b in ("yaqin", "otgan")),
        "bloklangan": sum(1 for b in bosq if b == "bloklangan"),
        "sinov": sum(1 for r in mijoz if r["holat"]["sinov"] and not r["holat"]["bloklangan"]),
        "bugun_kirish": kirish,
        "bugun_xato": xato,
        "bugun": kun.isoformat(),
    }


def xatolar(db, korxona=None, qidiruv=None, limit=200):
    """Hamma korxonalarning texnik xatolari BITTA ro'yxatda (faqat platforma admini). `korxona`: id,
    'platforma' (korxonaga bog'lanmagan) yoki None (hammasi); `qidiruv` — xabar / manzil / kim ichida.
    Xabarlar `crud.log_error` da allaqachon tozalangan (SQL parametrlari yashirilgan)."""
    import tenant_context as _tc
    from sqlalchemy import or_
    from models import ErrorLog
    from production_models import Company
    with _tc.system_context(db):
        q = db.query(ErrorLog)
        if korxona == "platforma":
            q = q.filter(ErrorLog.company_id.is_(None))
        elif korxona not in (None, "", "hammasi"):
            try:
                q = q.filter(ErrorLog.company_id == int(korxona))
            except (TypeError, ValueError):
                raise ObunaXato("Korxona noto'g'ri")
        s = (qidiruv or "").strip()
        if s:
            naqsh = f"%{s[:100]}%"
            q = q.filter(or_(ErrorLog.error_message.ilike(naqsh), ErrorLog.endpoint.ilike(naqsh),
                             ErrorLog.performed_by.ilike(naqsh)))
        rows = q.order_by(ErrorLog.created_at.desc(), ErrorLog.id.desc()).limit(max(1, min(int(limit), 500))).all()
        nomlar = dict(db.query(Company.id, Company.name).all())
    return [{
        "id": r.id, "company_id": r.company_id,
        "korxona": nomlar.get(r.company_id) if r.company_id is not None else None,
        "vaqt": r.created_at.strftime("%d.%m.%Y %H:%M") if r.created_at else "",
        "method": r.method or "", "endpoint": r.endpoint or "", "kim": r.performed_by or "",
        "xabar": (r.error_message or "")[:400], "trace": r.stack_trace or "",
    } for r in rows]
