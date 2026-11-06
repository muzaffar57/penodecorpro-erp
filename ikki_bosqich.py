"""
ikki_bosqich.py — kech199 (zip 263, xavfsizlik REJA 2-band + 12-band): PLATFORMA EGASI kirishining ikkinchi bosqichi — Telegram kodi.

EGASI QARORI (06.11 17:33): «Ha qo'shilsin». Platforma egasi hisobi (`users.is_platform_admin`) — HAMMA korxonalar ustidan hokim:
paroli tushib qolsa (fishing, eslab qolingan brauzer, ko'zdan o'g'irlash) — butun platforma begona qo'lida. Endi to'g'ri paroldan keyin
sessiya YARATILMAYDI: 6 xonali kod egasining Telegram chatiga (`BACKUP_TELEGRAM_CHAT_ID` — kunlik zaxira boradigan chat, tizim boti
`TELEGRAM_BOT_TOKEN`) ketadi, kod `/login/kod` sahifasida kiritiladi.

QOIDALAR
  * Faqat platforma egasi; boshqa foydalanuvchilar — avvalgidek (parol).
  * Kod: `secrets` (kriptografik), 6 xona, 5 daqiqa, 5 urinish, BIR marta. Bazada kod emas — HMAC (kalit — brauzerdagi tasodifiy
    `kirish_kod` cookie si; bazada uning xeshi). Urinish va «ishlatildi» — ATOMAR (`UPDATE … WHERE urinish < 5`): parallel so'rovlar
    chegaradan oshirolmaydi, bitta kod ikki marta ishlamaydi.
  * Kod so'rash — bitta hisobga 15 daqiqada 5 tadan ko'p emas (paroli bilgan begona Telegramni to'ldirib tashlamasin).
  * Kod Telegramga ketmasa — KIRISH YO'Q (sessiya yaratilmaydi).
  * «Bu qurilmani eslab qolish» — 30 kun kod so'ralmaydi (`ishonchli_qurilma` cookie si, faqat /login yo'lida; bazada xeshi);
    parol almashtirilsa — o'z-o'zidan bekor (`parol_belgisi`).
  * Yoqilganlik: `PLATFORMA_2FA` = 0 / off / false / yoq — o'chiq (FAVQULODDA — Telegram ishlamay qolsa egasi Railway da o'zi qo'yadi).
    Tizim Telegrami (token + chat) umuman sozlanmagan bo'lsa — kod yuboradigan joy yo'q: 2FA ishlamaydi (yangi o'rnatish / sinov
    muhiti; o'zgaruvchilarni faqat Railway egasi o'zgartira oladi).
  * 12-band: login bo'yicha tarqoq blok (30 xato turli IP lardan — `crud.check_login_rate_limit` «login_jami») platforma egasini yangi
    qurilmadan kiritmay qo'yardi (DoS). Endi egasi to'g'ri parol + Telegram kodi bilan blokdan o'tadi (`main.login_submit`).
"""
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta

from sqlalchemy import update as _sa_update

KOD_DAQIQA = 5
KOD_URINISH = 5
KOD_SORASH_MAX = 5
KOD_SORASH_OYNA_DAQIQA = 15
QURILMA_KUN = 30
KOD_COOKIE = "kirish_kod"
QURILMA_COOKIE = "ishonchli_qurilma"
COOKIE_YOL = "/login"
_OCHIQ_QIYMATLAR = {"0", "off", "false", "no", "yoq", "yo'q"}


def yoqilganmi() -> bool:
    """`PLATFORMA_2FA` o'chirilmagan (standart — yoqiq)."""
    return (os.environ.get("PLATFORMA_2FA") or "").strip().lower() not in _OCHIQ_QIYMATLAR


def telegram_manzil():
    """(token, [chat, ...]) — tizim boti va egasining chat(lar)i (kunlik zaxira boradigan joy)."""
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chatlar = [c.strip() for c in (os.environ.get("BACKUP_TELEGRAM_CHAT_ID") or "").split(",") if c.strip()]
    return token, chatlar


def kerakmi(user) -> bool:
    """Shu foydalanuvchi kirishiga Telegram kodi kerakmi."""
    if user is None or not getattr(user, "is_platform_admin", False) or not yoqilganmi():
        return False
    token, chatlar = telegram_manzil()
    return bool(token and chatlar)


def _xesh(qiymat) -> str:
    return hashlib.sha256(str(qiymat or "").encode("utf-8")).hexdigest()


def _kod_xesh(token, kod) -> str:
    return hmac.new(str(token).encode("utf-8"), str(kod).encode("utf-8"), hashlib.sha256).hexdigest()


def parol_belgisi(user) -> str:
    return _xesh("parol-belgisi:" + str(getattr(user, "password_hash", "") or ""))


def kod_tozala(kod) -> str:
    """Foydalanuvchi yozgan kod — faqat raqamlar («123 456», «123-456» ham bo'ladi)."""
    return re.sub(r"\D", "", str(kod or ""))[:12]


# ── ishonchli qurilma ─────────────────────────────────────────────────────────────────────────────────────────────────
def qurilma_ishonchlimi(db, user, xom) -> bool:
    from models import IshonchliQurilma
    if not xom or len(str(xom)) > 200 or user is None:
        return False
    q = db.query(IshonchliQurilma).filter(IshonchliQurilma.token_xesh == _xesh(xom),
                                          IshonchliQurilma.user_id == user.id).first()
    if q is None:
        return False
    hozir = datetime.utcnow()
    if q.expires_at < hozir or not hmac.compare_digest(q.parol_belgisi, parol_belgisi(user)):
        db.delete(q)
        db.commit()
        return False
    q.oxirgi = hozir
    db.commit()
    return True


def qurilma_yarat(db, user, ip=None, qurilma=None) -> str:
    """Yangi ishonchli qurilma; qaytaradi — cookie uchun XOM token."""
    from models import IshonchliQurilma
    hozir = datetime.utcnow()
    db.query(IshonchliQurilma).filter(IshonchliQurilma.user_id == user.id,
                                      IshonchliQurilma.expires_at < hozir).delete(synchronize_session=False)
    xom = secrets.token_urlsafe(32)
    db.add(IshonchliQurilma(user_id=user.id, token_xesh=_xesh(xom), parol_belgisi=parol_belgisi(user),
                            qurilma=(qurilma or "")[:250] or None, ip=(ip or "")[:64] or None,
                            created_at=hozir, oxirgi=hozir, expires_at=hozir + timedelta(days=QURILMA_KUN)))
    db.commit()
    return xom


# ── kod ────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def sorovlar_soni(db, user_id) -> int:
    from models import IkkiBosqichKod
    chegara = datetime.utcnow() - timedelta(minutes=KOD_SORASH_OYNA_DAQIQA)
    return db.query(IkkiBosqichKod).filter(IkkiBosqichKod.user_id == user_id, IkkiBosqichKod.created_at >= chegara).count()


def kod_yarat(db, user, ip=None):
    """Yangi kod. Qaytaradi — (cookie uchun XOM token, 6 xonali kod). Shu foydalanuvchining eskirgan yozuvlari tozalanadi
    (so'rash oynasidagilar sanoq uchun qoladi)."""
    from models import IkkiBosqichKod
    hozir = datetime.utcnow()
    db.query(IkkiBosqichKod).filter(
        IkkiBosqichKod.user_id == user.id,
        IkkiBosqichKod.created_at < hozir - timedelta(minutes=max(KOD_SORASH_OYNA_DAQIQA, KOD_DAQIQA) + 1),
    ).delete(synchronize_session=False)
    xom = secrets.token_urlsafe(32)
    kod = f"{secrets.randbelow(10 ** 6):06d}"
    db.add(IkkiBosqichKod(user_id=user.id, token_xesh=_xesh(xom), kod_xesh=_kod_xesh(xom, kod), urinish=0,
                          ishlatilgan=False, ip=(ip or "")[:64] or None, created_at=hozir,
                          expires_at=hozir + timedelta(minutes=KOD_DAQIQA)))
    db.commit()
    return xom, kod


def kod_topish(db, xom):
    """Yaroqli (muddati o'tmagan, ishlatilmagan, urinishi qolgan) kod yozuvi yoki None."""
    from models import IkkiBosqichKod
    if not xom or len(str(xom)) > 200:
        return None
    q = db.query(IkkiBosqichKod).filter(IkkiBosqichKod.token_xesh == _xesh(xom)).first()
    if q is None or q.ishlatilgan or q.urinish >= KOD_URINISH or q.expires_at < datetime.utcnow():
        return None
    return q


def kod_bekor(db, xom):
    """Kod yozuvini o'chiradi (masalan Telegramga yuborilmadi)."""
    from models import IkkiBosqichKod
    if xom:
        db.query(IkkiBosqichKod).filter(IkkiBosqichKod.token_xesh == _xesh(xom)).delete(synchronize_session=False)
        db.commit()


def kod_tekshir(db, xom, kod) -> dict:
    """Kodni tekshiradi. Qaytaradi: {"ok": bool, "qolgan": int, "user_id": int | None, "yaroqsiz": bool}.
    `yaroqsiz` — yozuv yo'q / muddati o'tgan / ishlatilgan / urinish tugagan (qaytadan parol kerak)."""
    from models import IkkiBosqichKod
    q = kod_topish(db, xom)
    if q is None:
        return {"ok": False, "qolgan": 0, "user_id": None, "yaroqsiz": True}
    qid, uid, kx = q.id, q.user_id, q.kod_xesh
    t = IkkiBosqichKod.__table__
    # ATOMAR: urinish sanog'i chegaradan oshmaydi (parallel so'rovlar ham)
    r = db.execute(_sa_update(t).where(t.c.id == qid, t.c.urinish < KOD_URINISH, t.c.ishlatilgan == False)   # noqa: E712
                   .values(urinish=t.c.urinish + 1))
    if r.rowcount != 1:
        db.commit()
        return {"ok": False, "qolgan": 0, "user_id": uid, "yaroqsiz": True}
    db.commit()
    kod = kod_tozala(kod)
    togri = len(kod) == 6 and hmac.compare_digest(_kod_xesh(xom, kod), kx)
    if togri:
        r = db.execute(_sa_update(t).where(t.c.id == qid, t.c.ishlatilgan == False).values(ishlatilgan=True))   # noqa: E712
        db.commit()
        if r.rowcount != 1:
            return {"ok": False, "qolgan": 0, "user_id": uid, "yaroqsiz": True}      # parallel so'rov allaqachon ishlatdi
        return {"ok": True, "qolgan": 0, "user_id": uid, "yaroqsiz": False}
    db.expire_all()
    q2 = db.query(IkkiBosqichKod).filter(IkkiBosqichKod.id == qid).first()
    qolgan = max(0, KOD_URINISH - int(q2.urinish if q2 is not None else KOD_URINISH))
    return {"ok": False, "qolgan": qolgan, "user_id": uid, "yaroqsiz": qolgan == 0}


def foydalanuvchilar_yozuvlarini_ochir(db, user_ids):
    """Foydalanuvchi butunlay o'chirilganda (`crud.factory_reset_all_data(keep_only_user_id=…)`) — uning kod va qurilma yozuvlari
    (chet el kaliti `users.id`)."""
    from models import IkkiBosqichKod, IshonchliQurilma
    ids = [int(i) for i in (user_ids or [])]
    if not ids:
        return
    db.query(IkkiBosqichKod).filter(IkkiBosqichKod.user_id.in_(ids)).delete(synchronize_session=False)
    db.query(IshonchliQurilma).filter(IshonchliQurilma.user_id.in_(ids)).delete(synchronize_session=False)


NOMALUM = "noma'lum"


def kod_xabari(kod, username, ip, qurilma) -> str:
    """Telegram xabari (Markdown — kod ajralib turadi; qolgani — oddiy matn)."""
    return (f"🔐 *epserp — kirish kodi: {kod}*\n\n"
            f"Login: {str(username or '')[:60]}\n"
            f"IP: {str(ip or NOMALUM)[:64]}\n"
            f"Qurilma: {str(qurilma or NOMALUM)[:120]}\n\n"
            f"Kod {KOD_DAQIQA} daqiqa amal qiladi. Siz kirmayotgan bo'lsangiz — kodni hech kimga bermang va parolingizni almashtiring.")
