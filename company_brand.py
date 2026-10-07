"""
company_brand.py — hujjatlarda ishlatiladigan korxona brendi.

NIMA UCHUN KERAK
----------------
Yuk xati, nakladnoy va moliya hisobotlarida korxona nomi, shiori, manzili
va TELEFON RAQAMI qattiq yozilgan edi — 7 ta joyda:
    "PenoDecorPro" · "Fasad bezaklari  ·  Andijon  ·  +998 97 999 57 57"
SaaS uchun bu to'g'ri emas: ikkinchi mijozning yuk xatida boshqa
korxonaning nomi va telefoni chiqardi, mijozi qo'ng'iroq qilsa — boshqa
odamga tushardi.

Endi bu ma'lumot `companies` jadvalidan olinadi. Maydon bo'sh bo'lsa —
ESKI qiymat ishlatiladi, ya'ni mavjud korxonada hech narsa o'zgarmaydi.
"""
import os

# Zaxira qiymatlar — birinchi korxonaning hozirgi ma'lumoti.
# Shu sababli bu o'zgarish mavjud hujjatlarni o'zgartirmaydi.
DEFAULT_NAME = "PenoDecorPro"
DEFAULT_SLOGAN = "Fasad bezaklari"
DEFAULT_ADDRESS = "Andijon"
DEFAULT_PHONE = "+998 97 999 57 57"
DEFAULT_LOGO = "static/logo_transparent.png"


def get_brand(db, company_id=None) -> dict:
    """Korxonaning hujjat brendini qaytaradi.

    Har doim to'liq lug'at qaytaradi — chaqiruvchi None tekshirishi
    shart emas. Baza o'qilmasa ham zaxira qiymatlar bilan ishlaydi.
    """
    nom = slogan = manzil = telefon = logo = None
    if db is not None and company_id is not None:
        try:
            from production_models import Company
            c = db.query(Company).filter(Company.id == company_id).first()
            if c is not None:
                nom = (c.name or "").strip() or None
                slogan = (getattr(c, "slogan", None) or "").strip() or None
                manzil = (getattr(c, "address", None) or "").strip() or None
                telefon = (getattr(c, "phone", None) or "").strip() or None
                logo = (getattr(c, "logo_path", None) or "").strip() or None
        except Exception:
            pass

    # 2026-09-20 — MUHIM: zaxira qiymatlar FAQAT korxona ma'lum
    # bo'lmaganda ishlatiladi (tizim hujjatlari). Korxona ma'lum bo'lsa-yu
    # maydoni bo'sh bo'lsa — u BO'SH qoladi.
    # Sabab: aks holda telefonini kiritmagan mijozning yuk xatida
    # PLATFORMA EGASINING raqami chiqardi va uning mijozi boshqa odamga
    # qo'ng'iroq qilardi. Logotipdagi bilan bir xil xato sinfi.
    if company_id is None:
        nom = nom or DEFAULT_NAME
        slogan = slogan or DEFAULT_SLOGAN
        manzil = manzil or DEFAULT_ADDRESS
        telefon = telefon or DEFAULT_PHONE
    else:
        nom = nom or DEFAULT_NAME   # nom har doim bor (companies.name majburiy)

    # 2026-09-20 — MUHIM: bu funksiya HECH QACHON None qaytarmaydi.
    # Sabab: PDF kutubxonasi `Paragraph(None)` ni qabul qilmaydi va
    # "'NoneType' object has no attribute 'split'" xatosi bilan yiqiladi —
    # jonli sinovda yuk xati aynan shu sababdan chiqmay qoldi.
    # Bo'sh maydon endi bo'sh MATN bo'ladi, chaqiruvchi esa bo'sh
    # qatorlarni o'zi tashlab ketadi.
    slogan = slogan or ""
    manzil = manzil or ""
    telefon = telefon or ""

    # LOGOTIP — 2026-09-20 dagi muhim tuzatish.
    # Ilgari korxonada logotip bo'lmasa UMUMIY logotipga (platforma
    # egasining logotipi) qaytilardi. Natijada yangi mijozning yuk xatida
    # BOSHQA korxonaning logotipi chiqardi — jonli sinovda aynan shu
    # aniqlandi. Endi: korxonaning O'Z logotipi bo'lmasa — logotip
    # UMUMAN ishlatilmaydi va hujjatda uning o'rniga korxona NOMI
    # yoziladi. Umumiy logotip faqat korxona ma'lum bo'lmaganda
    # (tizim hujjatlari) ishlatiladi.
    logo_abs = None
    kandidatlar = [logo] if company_id is not None else [DEFAULT_LOGO]
    for kandidat in kandidatlar:
        if not kandidat:
            continue
        yol = kandidat if os.path.isabs(kandidat) else os.path.join(
            os.path.dirname(os.path.abspath(__file__)), kandidat)
        if os.path.exists(yol):
            logo_abs = yol
            break

    # Sarlavha ostidagi bitta qator: "Fasad bezaklari · Andijon · +998 ..."
    qismlar = [x for x in (slogan, manzil, telefon) if x]
    return {"name": nom, "slogan": slogan, "address": manzil,
            "phone": telefon, "logo": logo_abs,
            "subtitle": "  ·  ".join(qismlar)}


def company_id_of(obj, db=None):
    """Obyektdan (yetkazish, sotuv, buyurtma) korxonani aniqlaydi."""
    if obj is None:
        return None
    cid = getattr(obj, "company_id", None)
    if cid:
        return cid
    for ota in ("order", "finished_product", "delivery"):
        o = getattr(obj, ota, None)
        if o is not None:
            cid = getattr(o, "company_id", None)
            if cid:
                return cid
    return None
