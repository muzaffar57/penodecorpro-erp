"""murojaat.py — kech127 (zip 151): mijoz korxonaning platforma egasiga MUROJAATI (yozishma).

EGASI QARORLARI (08.10 01:40, tugmali, QAYTA SO'RALMAYDI): (1) bo'lim HOZIR — birinchi mijozdan oldin; (2) murojaatni FAQAT
korxona admini yozadi; (3) javob — DASTUR ICHIDA (yozishma tarixi saqlanadi; telefon — qo'shimcha). O'LCHANGAN holat (08.10):
dasturda murojaat joyi yo'q edi — mijoz faqat aloqa telefonini (obuna ogohlantirishi / blok xabarida) ko'rardi.

Oqim: korxona admini «Yordam / Murojaat» sahifasida tur (Xato / Savol / Taklif / To'lov-obuna), matn va ixtiyoriy rasm bilan
murojaat ochadi → dastur o'zi kontekst qo'shadi (qaysi sahifadan, brauzer, ekran, korxonaning oxirgi 24 soatdagi texnik xatosi)
→ platforma egasiga Telegram (`main._send_telegram`) → egasi `/platforma` dagi «Murojaatlar» da yozishmani ochadi, javob yozadi
yoki yopadi → mijoz menyusida o'qilmagan javob soni. Holatlar — `models.Murojaat` izohida.

Korxona tomoni — har so'rov o'z korxonasi bilan (`company_id` sharti). Platforma tomoni — HAMMA korxonalar
(`tenant_context.system_context` ichida; obyektlar tashqariga chiqmaydi — lug'at qaytariladi). Bu modul `tools/tenant_lint.py`
tekshiradigan fayllardan tashqarida (obuna.py kabi) — korxona sharti har funksiyada qo'lda yozilgan va `tools/test_murojaat.py`
izolyatsiya bo'limida o'lchanadi."""
import json
import re
from datetime import datetime, timedelta

TURLAR = {"xato": "Xato", "savol": "Savol", "taklif": "Taklif", "tolov": "To'lov / obuna"}
HOLATLAR = {"yangi": "Yangi", "javob_berildi": "Javob berildi", "yopildi": "Yopildi"}
MATN_MAX = 4000                 # bitta xabar matni (belgi)
KUNLIK_CHEGARA = 20             # bir korxona 24 soatda ochadigan yangi murojaatlar
XABAR_CHEGARA = 200             # bitta yozishmadagi xabarlar
QISQA = 160                     # ro'yxatdagi birinchi xabar parchasi
_SAHIFA = re.compile(r"/[A-Za-z0-9_\-/]{0,190}")
_EKRAN = re.compile(r"\d{2,5}x\d{2,5}")


class MurojaatXato(ValueError):
    """Kiritilgan ma'lumot noto'g'ri yoki chegara oshdi — 400."""


class MurojaatYoq(LookupError):
    """Murojaat yo'q yoki boshqa korxonaniki — 404 (borligi oshkor qilinmaydi)."""


class MurojaatYopiq(Exception):
    """Yopilgan murojaatga yozib / qayta yopib bo'lmaydi — 409."""


# ══════════════════════════════════════════════════════════════
# YORDAMCHILAR
# ══════════════════════════════════════════════════════════════
def matn_tekshir(matn):
    """Bo'sh emas, ko'pi bilan `MATN_MAX` belgi; qaytaradigani — saqlanadigan matn.

    kech128 (zip 152 — O'LCHANDI haqiqiy Chromium da, `work/k152/crlf_olchov.py`): brauzer forma (FormData) yangi qatorni «\\r\\n»
    qilib yuboradi, `maxlength` esa uni 1 belgi sanaydi — 40 qatorli 4000 belgilik matn serverga 4040 bo'lib kelib «juda uzun» deb rad
    etilardi (hisoblagich «4000 / 4000» ko'rsatib turganda). Qator oxirlari tekshiruvdan OLDIN «\\n» ga keltiriladi (saqlanadigani ham)."""
    t = (matn or "") if isinstance(matn, str) else ""
    t = t.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not t:
        raise MurojaatXato("Murojaat matnini yozing")
    if len(t) > MATN_MAX:
        raise MurojaatXato(f"Matn juda uzun — ko'pi bilan {MATN_MAX} belgi")
    return t


def turi_tekshir(turi):
    t = (turi or "").strip() if isinstance(turi, str) else ""
    if t not in TURLAR:
        raise MurojaatXato("Murojaat turini tanlang: Xato, Savol, Taklif yoki To'lov / obuna")
    return t


def sahifa_toza(sahifa):
    """Mijoz qaysi sahifadan kelgan — faqat ichki yo'l («/orders»); boshqa narsa — yozilmaydi."""
    s = (sahifa or "").strip() if isinstance(sahifa, str) else ""
    return s if _SAHIFA.fullmatch(s) else None


def muallif_nomi(user):
    return ((getattr(user, "full_name", None) or "").strip() or getattr(user, "username", None) or "—")[:100]


def _iso(v):
    return v.isoformat() if v else None


def oxirgi_xato(db, company_id):
    """Korxonaning oxirgi 24 soatdagi texnik xatosi (`error_logs` — Toshkent devor vaqti) yoki None."""
    from models import ErrorLog, _uzb_now
    e = (db.query(ErrorLog).filter(ErrorLog.company_id == company_id, ErrorLog.created_at >= _uzb_now() - timedelta(hours=24))
         .order_by(ErrorLog.created_at.desc(), ErrorLog.id.desc()).first())
    if e is None:
        return None
    return {"vaqt": e.created_at.strftime("%d.%m.%Y %H:%M") if e.created_at else "", "endpoint": (e.endpoint or "")[:200],
            "usul": (e.method or "")[:10], "xabar": (e.error_message or "")[:300]}


def kontekst_yasa(db, company_id, brauzer=None, ekran=None):
    """Dastur o'zi qo'shadigan ma'lumot (JSON matn)."""
    k = {"brauzer": (brauzer or "")[:300] or None,
         "ekran": ekran if isinstance(ekran, str) and _EKRAN.fullmatch(ekran.strip()) else None,
         "oxirgi_xato": oxirgi_xato(db, company_id)}
    return json.dumps(k, ensure_ascii=False)


def _kontekst_oqi(m):
    try:
        k = json.loads(m.kontekst or "{}")
        return k if isinstance(k, dict) else {}
    except (ValueError, TypeError):
        return {}


def _xabarlar(db, m):
    from models import MurojaatXabari as _X
    return (db.query(_X).filter(_X.murojaat_id == m.id, _X.company_id == m.company_id)
            .order_by(_X.yaratilgan, _X.id).all())


def _xabar_korinish(x):
    return {"id": x.id, "kimdan": x.kimdan, "muallif": x.muallif, "matn": x.matni, "rasm": x.rasm,
            "yaratilgan": _iso(x.yaratilgan)}


def _yangi_javob(m):
    """Mijoz hali o'qimagan platforma javobi bormi."""
    return m.holat == "javob_berildi" and (m.mijoz_korgan is None or m.mijoz_korgan < m.yangilangan)


def _qator(m, birinchi, soni, korxona=None):
    d = {"id": m.id, "turi": m.turi, "turi_nomi": TURLAR.get(m.turi, m.turi), "holat": m.holat,
         "holat_nomi": HOLATLAR.get(m.holat, m.holat), "parcha": (birinchi or "")[:QISQA], "xabarlar_soni": soni,
         "yaratilgan": _iso(m.yaratilgan), "yangilangan": _iso(m.yangilangan), "yaratgan": m.yaratgan,
         "yangi_javob": _yangi_javob(m), "sahifa": m.kelgan_sahifa}
    if korxona is not None:
        d["korxona_id"] = m.company_id
        d["korxona"] = korxona
        d["oqilmagan"] = m.holat == "yangi" and (m.platforma_korgan is None or m.platforma_korgan < m.yangilangan)
    return d


def _birinchi_va_soni(db, ids, company_id=None):
    """{murojaat_id: (birinchi xabar matni, xabarlar soni)}."""
    from models import MurojaatXabari as _X
    if not ids:
        return {}
    q = db.query(_X.murojaat_id, _X.matni, _X.id).filter(_X.murojaat_id.in_(ids))
    if company_id is not None:
        q = q.filter(_X.company_id == company_id)
    nat = {}
    for mid, matn, xid in q.order_by(_X.murojaat_id, _X.yaratilgan, _X.id).all():
        if mid not in nat:
            nat[mid] = [matn, 0]
        nat[mid][1] += 1
    return {k: (v[0], v[1]) for k, v in nat.items()}


# ══════════════════════════════════════════════════════════════
# KORXONA (mijoz) TOMONI — har funksiya o'z korxonasi bilan
# ══════════════════════════════════════════════════════════════
def mijoz_ol(db, murojaat_id, company_id, lock=False):
    from models import Murojaat as _M
    q = db.query(_M).filter(_M.id == murojaat_id, _M.company_id == company_id)
    if lock:
        q = q.with_for_update().populate_existing()
    m = q.first()
    if m is None:
        raise MurojaatYoq("Murojaat topilmadi")
    return m


def yarat(db, user, company_id, turi, matn, sahifa=None, brauzer=None, ekran=None, rasm=None):
    """Yangi murojaat (birinchi xabari bilan). Qaytaradi: (Murojaat, birinchi xabar matni). Commit qiladi."""
    from models import Murojaat as _M, MurojaatXabari as _X
    turi = turi_tekshir(turi)
    matn = matn_tekshir(matn)
    hozir = datetime.utcnow()
    soni = db.query(_M.id).filter(_M.company_id == company_id, _M.yaratilgan >= hozir - timedelta(hours=24)).count()
    if soni >= KUNLIK_CHEGARA:
        raise MurojaatXato(f"Bir sutkada {KUNLIK_CHEGARA} tadan ortiq murojaat ochib bo'lmaydi — mavjud murojaatga yozing")
    nom = muallif_nomi(user)
    m = _M(company_id=company_id, turi=turi, holat="yangi", kelgan_sahifa=sahifa_toza(sahifa),
           kontekst=kontekst_yasa(db, company_id, brauzer, ekran), yaratilgan=hozir, yaratgan=nom,
           yaratgan_login=(getattr(user, "username", None) or "")[:50] or None, yangilangan=hozir, mijoz_korgan=hozir)
    db.add(m)
    db.flush()
    db.add(_X(company_id=company_id, murojaat_id=m.id, kimdan="mijoz", muallif=nom, matni=matn, rasm=rasm, yaratilgan=hozir))
    db.commit()
    return m, matn


def mijoz_royxati(db, company_id):
    from models import Murojaat as _M
    ms = (db.query(_M).filter(_M.company_id == company_id)
          .order_by(_M.yangilangan.desc(), _M.id.desc()).limit(500).all())
    bs = _birinchi_va_soni(db, [m.id for m in ms], company_id)
    return {"murojaatlar": [_qator(m, *bs.get(m.id, ("", 0))) for m in ms],
            "turlar": TURLAR, "holatlar": HOLATLAR, "matn_max": MATN_MAX}


def mijoz_yozishmasi(db, murojaat_id, company_id, korildi=True):
    """Yozishma (mijoz ko'rinishi — kontekst ko'rsatilmaydi). Ochilganda — «ko'rildi» belgisi (o'qilmagan javob soni kamayadi)."""
    m = mijoz_ol(db, murojaat_id, company_id)
    xs = _xabarlar(db, m)
    d = _qator(m, xs[0].matni if xs else "", len(xs))
    d["xabarlar"] = [_xabar_korinish(x) for x in xs]
    d["yopilgan"] = _iso(m.yopilgan)
    if korildi:
        m.mijoz_korgan = datetime.utcnow()
        db.commit()
    return d


def mijoz_xabari(db, user, murojaat_id, company_id, matn, rasm=None):
    """Mijozning qo'shimcha xabari — murojaat yana «Yangi» (platforma javobini kutadi). Commit qiladi. Qaytaradi: (Murojaat, matn)."""
    from models import MurojaatXabari as _X
    matn = matn_tekshir(matn)
    m = mijoz_ol(db, murojaat_id, company_id, lock=True)
    if m.holat == "yopildi":
        db.rollback()
        raise MurojaatYopiq("Murojaat yopilgan — yangi murojaat oching")
    if db.query(_X.id).filter(_X.murojaat_id == m.id, _X.company_id == company_id).count() >= XABAR_CHEGARA:
        db.rollback()
        raise MurojaatXato(f"Bitta murojaatda {XABAR_CHEGARA} tadan ortiq xabar bo'lmaydi — yangi murojaat oching")
    hozir = datetime.utcnow()
    db.add(_X(company_id=company_id, murojaat_id=m.id, kimdan="mijoz", muallif=muallif_nomi(user), matni=matn, rasm=rasm,
              yaratilgan=hozir))
    m.holat = "yangi"
    m.yangilangan = hozir
    m.mijoz_korgan = hozir
    db.commit()
    return m, matn


def mijoz_soni(db, user):
    """Korxona admini menyusidagi son — o'qilmagan platforma javoblari."""
    from models import Murojaat as _M
    cid = getattr(user, "company_id", None)
    if cid is None:
        return 0
    ms = db.query(_M).filter(_M.company_id == cid, _M.holat == "javob_berildi").all()
    return sum(1 for m in ms if _yangi_javob(m))


# ══════════════════════════════════════════════════════════════
# PLATFORMA TOMONI — hamma korxonalar (system_context)
# ══════════════════════════════════════════════════════════════
def _korxona_nomlari(db, ids):
    from production_models import Company
    if not ids:
        return {}
    return dict(db.query(Company.id, Company.name).filter(Company.id.in_(list(ids))).all())


def _platforma_ol(db, murojaat_id, lock=False):
    from models import Murojaat as _M
    q = db.query(_M).filter(_M.id == murojaat_id)
    if lock:
        q = q.with_for_update().populate_existing()
    m = q.first()
    if m is None:
        raise MurojaatYoq("Murojaat topilmadi")
    return m


def platforma_royxati(db, holat=None, korxona=None, limit=200):
    """Hamma korxonalar murojaatlari (yangilari — tepada). `holat` — 'yangi' / 'javob_berildi' / 'yopildi' / None (hammasi)."""
    import tenant_context as _tc
    from models import Murojaat as _M
    from sqlalchemy import func as _f
    limit = max(1, min(int(limit or 200), 500))
    with _tc.system_context(db):
        q = db.query(_M)
        if holat in HOLATLAR:
            q = q.filter(_M.holat == holat)
        if korxona is not None:
            q = q.filter(_M.company_id == korxona)
        ms = q.order_by(_M.yangilangan.desc(), _M.id.desc()).limit(limit).all()
        bs = _birinchi_va_soni(db, [m.id for m in ms])
        nomlar = _korxona_nomlari(db, {m.company_id for m in ms})
        sanoq = dict(db.query(_M.holat, _f.count(_M.id)).group_by(_M.holat).all())
        return {"murojaatlar": [_qator(m, *bs.get(m.id, ("", 0)), korxona=nomlar.get(m.company_id, f"#{m.company_id}"))
                                for m in ms],
                "sanoq": {h: int(sanoq.get(h, 0)) for h in HOLATLAR}, "turlar": TURLAR, "holatlar": HOLATLAR,
                "matn_max": MATN_MAX}


def platforma_yozishmasi(db, murojaat_id, korildi=True):
    """Yozishma (platforma ko'rinishi — kontekst va korxona bilan). Ochilganda — «ko'rildi» belgisi."""
    import tenant_context as _tc
    with _tc.system_context(db):
        m = _platforma_ol(db, murojaat_id)
        xs = _xabarlar(db, m)
        d = _qator(m, xs[0].matni if xs else "", len(xs), korxona=_korxona_nomlari(db, {m.company_id}).get(m.company_id, ""))
        d["xabarlar"] = [_xabar_korinish(x) for x in xs]
        d["kontekst"] = _kontekst_oqi(m)
        d["yaratgan_login"] = m.yaratgan_login
        d["yopilgan"] = _iso(m.yopilgan)
        d["yopgan"] = m.yopgan
        if korildi:
            m.platforma_korgan = datetime.utcnow()
            db.commit()
        return d


def javob(db, admin, murojaat_id, matn, rasm=None):
    """Platforma javobi — murojaat «Javob berildi». Commit qiladi. Qaytaradi: korxona_id."""
    import tenant_context as _tc
    from models import MurojaatXabari as _X
    matn = matn_tekshir(matn)
    with _tc.system_context(db):
        m = _platforma_ol(db, murojaat_id, lock=True)
        if m.holat == "yopildi":
            db.rollback()
            raise MurojaatYopiq("Murojaat yopilgan — unga yozib bo'lmaydi")
        if db.query(_X.id).filter(_X.murojaat_id == m.id, _X.company_id == m.company_id).count() >= XABAR_CHEGARA:
            db.rollback()
            raise MurojaatXato(f"Bitta murojaatda {XABAR_CHEGARA} tadan ortiq xabar bo'lmaydi")
        hozir = datetime.utcnow()
        cid = m.company_id
        db.add(_X(company_id=cid, murojaat_id=m.id, kimdan="platforma", muallif=muallif_nomi(admin), matni=matn, rasm=rasm,
                  yaratilgan=hozir))
        m.holat = "javob_berildi"
        m.yangilangan = hozir
        m.platforma_korgan = hozir
        db.commit()
        return cid


def yopish(db, admin, murojaat_id):
    """Platforma yozishmani yopadi (mijoz endi unga yozolmaydi — yangi murojaat ochadi). Commit qiladi."""
    import tenant_context as _tc
    with _tc.system_context(db):
        m = _platforma_ol(db, murojaat_id, lock=True)
        if m.holat == "yopildi":
            db.rollback()
            raise MurojaatYopiq("Murojaat allaqachon yopilgan")
        hozir = datetime.utcnow()
        m.holat = "yopildi"
        m.yopilgan = hozir
        m.yopgan = muallif_nomi(admin)
        m.platforma_korgan = hozir
        db.commit()
        return m.company_id


def platforma_soni(db):
    """Platforma menyusidagi son — javob kutayotgan («Yangi») murojaatlar."""
    import tenant_context as _tc
    from models import Murojaat as _M
    with _tc.system_context(db):
        return db.query(_M.id).filter(_M.holat == "yangi").count()


def rasm_bormi(db, url):
    """Rasm biror murojaat xabariga bog'langanmi (platforma admini uchun fayl himoyasi — hamma korxonalar)."""
    import tenant_context as _tc
    from models import MurojaatXabari as _X
    with _tc.system_context(db):
        return db.query(_X.id).filter(_X.rasm == url).first() is not None


def korxona_nomi(db, company_id):
    import tenant_context as _tc
    with _tc.system_context(db):
        return _korxona_nomlari(db, {company_id}).get(company_id, f"#{company_id}")


# ══════════════════════════════════════════════════════════════
# TELEGRAM MATNLARI (platforma egasiga)
# ══════════════════════════════════════════════════════════════
def telegram_yangi(m_id, turi, korxona, muallif, login, sahifa, matn, rasm_bor=False):
    s = [f"🆘 Yangi murojaat #{m_id}", f"Korxona: {korxona}", f"Kim: {muallif}" + (f" ({login})" if login else ""),
         f"Turi: {TURLAR.get(turi, turi)}"]
    if sahifa:
        s.append(f"Sahifa: {sahifa}")
    s.append("")
    s.append(matn if len(matn) <= 700 else matn[:700] + "…")
    if rasm_bor:
        s.append("📎 rasm biriktirilgan")
    s.append("")
    s.append("Javob berish: Platforma → Murojaatlar")
    return "\n".join(s)


def telegram_qoshimcha(m_id, korxona, muallif, matn, rasm_bor=False):
    s = [f"💬 Murojaat #{m_id} — mijozdan yangi xabar", f"Korxona: {korxona}", f"Kim: {muallif}", "",
         matn if len(matn) <= 700 else matn[:700] + "…"]
    if rasm_bor:
        s.append("📎 rasm biriktirilgan")
    return "\n".join(s)
