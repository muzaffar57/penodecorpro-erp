"""
PenoDecorPro ERP — Production/MRP uchun API yo'llari
=======================================================
Mavjud main.py juda katta (4000+ qator) bo'lgani uchun, yangi
endpointlar ATAYLAB alohida APIRouter sifatida yozildi — main.py'ga
faqat 2 qator qo'shish kifoya (pastda, "main.py'GA QO'SHISH KERAK
BO'LGAN QATORLAR" bo'limiga qarang).

Hozircha company_id har doim 1 (bitta korxona) — to'liq SaaS
migratsiyasi boshlanganda, bu joyga "joriy foydalanuvchining
korxonasi" degan haqiqiy mantiq keladi.
"""

from typing import List, Optional

import re as _re181

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

import auth
import crud
from models import Inventory
from database import get_db, tashkent_oyida
import production_schemas as schemas
import production_service as service
from production_models import ProductType, BOM, BOMItem, ProductionOrder, Company

# 2026-09-18 — M3: bu modulda tenant endi QATTIQ YOZILGAN qiymatdan emas,
# TIZIMGA KIRGAN foydalanuvchining korxonasidan olinadi
# (auth.company_id_of(current_user)). Ilgari hamma joyda DEFAULT_COMPANY_ID
# (=1) turardi — bitta korxonada to'g'ri ishlardi, ikkinchisi qo'shilganda
# esa MRP butunlay 1-korxonaning ma'lumoti bilan ishlab qolardi.

router = APIRouter(prefix="/api/production", tags=["production"])

# 2026-09-16: to'liq SaaS migratsiyasigacha — YAGONA korxona.
DEFAULT_COMPANY_ID = 1


# kech144 (zip 181, audit D3): server xabaridagi maydon nomi — sahifadagi yorliq bilan (ilgari «'quantity' juda katta», «'items' 2-qator»
# — inglizcha kalit; «Miqdor» maydoniga 99 999 999 999 yozilsa shunday chiqardi)
MAYDON_NOMI = {
    "name": "Nomi", "unit": "O'lchov birligi", "input_template": "Kiritish shakli", "pricing_formula": "Narx usuli",
    "fixed_unit_price": "Qat'iy narx", "supports_coating": "Qoplama", "coating_price_multiplier": "Qoplama koeffitsiyenti",
    "notes": "Izoh", "yonalish_id": "Yo'nalish", "inventory_id": "Material", "component_type": "Tarkib turi", "quantity": "Miqdor",
    "scrap_factor_percent": "Isrof", "is_optional": "Ixtiyoriy", "is_coating": "Qoplama qatori",
    "fixed_cost_per_unit": "Qo'shimcha xarajat", "percentage_cost": "Ustama foizi", "product_type_id": "Mahsulot turi",
    "variant_name": "Tarkib nomi", "batch_quantity": "Tarkib necha birlik uchun", "items": "Tarkib", "bom_id": "Tarkib (retsept)",
    "source_type": "Kim uchun", "source_order_id": "Buyurtma", "source_order_item_id": "Buyurtma detali",
    "selected_optional_bom_item_ids": "Ixtiyoriy tarkiblar",
}


def _maydon_nomlari(matn) -> str:
    """«'quantity' juda katta» → «Miqdor juda katta» (faqat MAYDON_NOMI dagi kalitlar; boshqasi o'zgarmaydi)."""
    return _re181.sub(r"'(\w+)'", lambda m: MAYDON_NOMI.get(m.group(1), m.group(0)), str(matn))


def _tana(model: str, data, sxema):
    """kech93 (8-band): xom JSON QAT'IY tekshiriladi (`crud._clean_val`), keyin
    sxemaga o'giriladi (sxema ham strict — ikkinchi to'siq). Qoida buzilsa 400 va
    `detail` — MATN: `production.html` `'Xato: ' + e.detail` ni ko'rsatadi
    (sxemaning 422 ro'yxati "Xato: [object Object]" bo'lib chiqardi).
    kech144 (zip 181, D3): maydon nomlari — o'zbekcha (`_maydon_nomlari`)."""
    try:
        toza = crud._clean_val(model, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=_maydon_nomlari(e))
    return sxema(**toza)


def _retsept_materiallari(db: Session, items, company_id: int) -> None:
    """kech93 (8-band, HAQIQIY PostgreSQL da O'LCHANGAN `work/probe8b.py` M7 / M8):
    yo'q material id si (va 2**31) — PostgreSQL 500 (FK / integer), SQLite esa
    JIM bog'lamsiz retsept qatori saqlardi; begona korxona materiali — 409 (ORM
    qo'riqchisi). Endi har qator materiali SHU korxonada bo'lishi shart → 400
    (qaysi qator ekani bilan; begona — "topilmadi", oracle yo'q)."""
    ids = {it.inventory_id for it in items}
    bor = set()
    if ids:
        bor = {r[0] for r in db.query(Inventory.id).filter(
            Inventory.id.in_(ids), Inventory.company_id == company_id).all()}
    for i, it in enumerate(items):
        if it.inventory_id not in bor:
            raise HTTPException(status_code=400,
                                detail=f"Tarkib {i + 1}-qator: material topilmadi")     # kech144 (zip 181, D3): ilgari «'items'»


# ============================================================
# MAHSULOT TURLARI (ProductType)
# ============================================================

# kech144 (zip 181, audit A1 / A2): AMAL KALITI (`X-Amal-Kaliti`, zip 174 — `crud.amal_kaliti_bilan`; main.py dagi `_amal_kaliti` /
# `_amal_bajar` ning shu moduldagi nusxasi — main.py ni import qilib bo'lmaydi). Takrorda birinchi javob (`takror: true`, `X-Takror: 1`).
# Nom tekshiruvi qulfi (`crud._pul_qulfi`, PostgreSQL) — fazolar: mahsulot turi nomi (korxona), tarkib nomi (mahsulot turi).
TUR_NOMI_QULF_NS = 181
TARKIB_NOMI_QULF_NS = 182


def _amal_kaliti(request) -> Optional[str]:
    if request is None:
        return None
    try:
        return crud.amal_kaliti_toza(request.headers.get("X-Amal-Kaliti"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _amal_bajar(db: Session, current_user, response, amal: str, kalit, bajar):
    javob, takror = crud.amal_kaliti_bilan(db, auth.company_id_of(current_user), amal, kalit, bajar, kim=_kim(current_user))
    if takror:
        if response is not None:
            response.headers["X-Takror"] = "1"
        if isinstance(javob, dict):
            javob = {**javob, "takror": True}
    return javob, takror


def _kim(current_user) -> str:
    return current_user.full_name or current_user.username


def _retsept_xulosa(bom, unit: str) -> str:
    """Retsept qisqa tavsifi jurnal uchun (kech110, 2c): nom, partiya, materiallar soni."""
    _n = len(list(bom.items or []))
    return (f"«{bom.variant_name}»: partiya {service._son110(bom.batch_quantity)} {unit or ''}, "
            f"{_n} ta material").replace(" ,", ",")


def _retsept_holati(bom) -> dict:
    """kech120 (zip 129 — G6-23): retseptning jurnal uchun holati (oddiy qiymatlar — o'zgarishdan OLDIN olinadi):
    nom, partiya, izoh va materiallar (material + turi bo'yicha: miqdor, chiqindi %, ixtiyoriy / qoplama, narx
    sozlamalari, izoh)."""
    _m = {}
    for _i in list(bom.items or []):
        _k = (_i.inventory_id, _i.component_type or "")
        _d = _m.setdefault(_k, {"miqdor": 0.0, "boshqa": []})
        _d["miqdor"] += float(_i.quantity or 0)
        _d["boshqa"].append((float(_i.scrap_factor_percent or 0), bool(_i.is_optional), bool(_i.is_coating),
                             _i.fixed_cost_per_unit, _i.percentage_cost, (_i.notes or "").strip()))
    return {"nom": bom.variant_name or "", "partiya": float(bom.batch_quantity or 0),
            "izoh": (bom.notes or "").strip(), "materiallar": _m}


def _retsept_farqi(db: Session, company_id: int, eski: dict, yangi: dict, unit: str) -> list:
    """kech120 (zip 129 — G6-23): ikki `_retsept_holati` orasidagi o'zgarishlar. O'LCHANGAN (audit kech114): ilgari
    yozuvda faqat «partiya 1 m², 4 ta material → partiya 1 m², 4 ta material» — material miqdori o'zgargani
    ko'rinmasdi."""
    _ids = {k[0] for k in list(eski["materiallar"]) + list(yangi["materiallar"])}
    _inv = {r.id: r for r in db.query(Inventory).filter(Inventory.id.in_(_ids), Inventory.company_id == company_id).all()} \
        if _ids else {}

    def _nom(k):
        _r = _inv.get(k[0])
        _s = _r.item_name if _r else f"material #{k[0]}"
        return _s + (" (qadoq)" if k[1] == "packaging" else "")

    def _bir(k):
        _r = _inv.get(k[0])
        return (" " + _r.unit) if _r and _r.unit else ""

    _f = []
    if eski["nom"] != yangi["nom"]:
        _f.append(f"nomi: «{eski['nom']}» → «{yangi['nom']}»")
    if abs(eski["partiya"] - yangi["partiya"]) > 1e-9:
        _f.append(f"partiya: {crud.audit_son(eski['partiya'])} → {crud.audit_son(yangi['partiya'])} {unit or ''}".rstrip())
    if eski["izoh"] != yangi["izoh"]:
        _f.append("izoh o'zgardi")
    _e, _y = eski["materiallar"], yangi["materiallar"]
    for _k in _e:
        if _k not in _y:
            _f.append(f"− {_nom(_k)}")
    for _k in _y:
        if _k not in _e:
            _f.append(f"+ {_nom(_k)} {crud.audit_son(_y[_k]['miqdor'])}{_bir(_k)}")
            continue
        if abs(_e[_k]["miqdor"] - _y[_k]["miqdor"]) > 1e-9:
            _f.append(f"{_nom(_k)}: {crud.audit_son(_e[_k]['miqdor'])} → {crud.audit_son(_y[_k]['miqdor'])}{_bir(_k)}")
        if _e[_k]["boshqa"] != _y[_k]["boshqa"]:
            _a, _b = _e[_k]["boshqa"], _y[_k]["boshqa"]
            if len(_a) == len(_b) == 1 and _a[0][0] != _b[0][0] and _a[0][1:] == _b[0][1:]:
                _f.append(f"{_nom(_k)}: chiqindi {crud.audit_son(_a[0][0])} → {crud.audit_son(_b[0][0])} %")
            elif len(_a) == len(_b) == 1 and _a[0][1] != _b[0][1] and _a[0][2:] == _b[0][2:] and _a[0][0] == _b[0][0]:
                _f.append(f"{_nom(_k)}: {'ixtiyoriy' if _a[0][1] else 'majburiy'} → {'ixtiyoriy' if _b[0][1] else 'majburiy'}")
            else:
                _f.append(f"{_nom(_k)}: sozlamasi o'zgardi (chiqindi / ixtiyoriy / qoplama / narx / izoh)")
    return _f


@router.get("/product-types", response_model=list[schemas.ProductTypeRead])
def list_product_types(db: Session = Depends(get_db), current_user=Depends(auth.ruxsat_biri(
        ("mahsulot_turi", "korish"), ("buyurtma", "yaratish"), ("buyurtma", "tahrirlash")))):
    """kech144 (zip 173, audit P1-3 — O'LCHANGAN): faol mahsulot turlari (nomi, birligi, kiritish shakli, SOTUV narxi qoidasi).
    Buyurtma yaratish / tahrirlash ruxsati ham yetadi — «MRP mahsuloti» detalini tanlash va tahrirda tiklash shu ro'yxatdan
    (ilgari faqat «Mahsulot turlari: ko'rish»: tayyor «Menejer» rolida 403 → ro'yxat bo'sh, MRP buyurtmasini tahrirlash saqlashda
    detal turini, qoplamasini va o'lchamlarini o'chirardi). Tannarx / ombor (`/product-types/xulosa`) — avvalgidek."""
    return db.query(ProductType).filter(
        ProductType.company_id == auth.company_id_of(current_user), ProductType.is_active == True
    ).order_by(ProductType.name).all()


@router.get("/product-types/xulosa")
def product_types_summary(db: Session = Depends(get_db), current_user=Depends(auth.ruxsat("mahsulot_turi", "korish"))):
    """kech114 (egasi QARORI «5B — Jadval»): mahsulot turlari jadvali — har tur: omborda / band / jarayonda va
    retseptlarining 1 birlik taxminiy tannarxi (`service.turlar_xulosasi`; faqat o'qiydi). Huquq — turlar ro'yxati
    bilan bir xil."""
    return service.turlar_xulosasi(db, auth.company_id_of(current_user))


@router.post("/product-types", response_model=schemas.ProductTypeRead)
def create_product_type(data: dict = Body(...), db: Session = Depends(get_db), current_user=Depends(auth.ruxsat("mahsulot_turi", "yaratish")),
                        request: Request = None, response: Response = None):
    # kech93 (8-band): tana QAT'IY (`_tana`), sabab — `crud._val_rules()["ProductType"]` izohida.
    data = _tana("ProductType", data, schemas.ProductTypeCreate)
    _cid = auth.company_id_of(current_user)
    # kech144 (zip 181, audit A1): `X-Amal-Kaliti` — ikki marta bosish / qayta yuborish ikkinchi tur yaratmaydi; nom tekshiruvi — korxona
    # qulfi ostida (parallel ikki bir xil nom — ikkinchisi «allaqachon bor»)
    kalit = _amal_kaliti(request)

    def _bajar():
        crud._pul_qulfi(db, TUR_NOMI_QULF_NS, _cid)
        # QO'SHILDI 2026-09-20 — nom TAKRORLANMASIN.
        # Ilgari hech qanday shart yo'q edi: bitta korxona aynan bir xil
        # nomli ikkita tur yaratishi mumkin edi va ishlab chiqarish
        # oynasidagi ro'yxatda ular bir xil ko'rinardi — operator qaysi
        # biri qaysiligini ajrata olmasdi.
        # Faqat FAOL turlar tekshiriladi: nofaol qilingan (o'chirilgan)
        # turning nomini qayta ishlatish mumkin bo'lib qolsin.
        _nom = (data.name or "").strip()
        _bor = db.query(ProductType).filter(
            ProductType.company_id == _cid,
            ProductType.is_active == True,
            func.lower(func.trim(ProductType.name)) == _nom.lower(),
        ).first()
        if _bor:
            raise HTTPException(
                status_code=400,
                detail=f"'{_nom}' nomli mahsulot turi allaqachon bor. Boshqa nom tanlang.")
        _payload = data.model_dump()
        _payload["name"] = _nom
        # kech117 (A2): yo'nalish FAQAT shu korxonaniki va ko'rinadigan (begona / yo'q — "topilmadi", oracle yo'q)
        if _payload.get("yonalish_id") is not None:
            try:
                _payload["yonalish_id"], _ = crud.yonalish_tanlovi(db, _cid, _payload["yonalish_id"])
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
        pt = ProductType(company_id=_cid, **_payload)
        db.add(pt)
        db.flush()
        # kech110 (2c): Faoliyat jurnali — amal bilan BITTA tranzaksiyada
        crud.log_activity(db, "created", "product_type", pt.id, f"Mahsulot turi «{pt.name}»", _kim(current_user),
                          new_value=f"birlik: {pt.unit}", company_id=_cid, commit=False)
        db.commit()
        db.refresh(pt)
        return schemas.ProductTypeRead.model_validate(pt).model_dump(mode="json")
    javob, _ = _amal_bajar(db, current_user, response, "mahsulot_turi", kalit, _bajar)
    return javob


@router.patch("/product-types/{pt_id}", response_model=schemas.ProductTypeRead)
def set_product_type_yonalish(pt_id: int, data: dict = Body(...), db: Session = Depends(get_db),
                              current_user=Depends(auth.ruxsat("mahsulot_turi", "tahrirlash"))):
    """kech117 (A2 — egasi QARORI «mavjud turlar — egasi biriktiradi»): turga yo'nalish biriktirish / almashtirish.
    Faqat `yonalish_id` (shu korxonaning ko'rinadigan yo'nalishi). Turning boshqa maydonlari (birlik, narx usuli)
    ATAYLAB o'zgartirilmaydi — eski buyurtma / ishlab chiqarish tarixi shularga tayanadi. Yo'nalish almashsa, o'tgan
    oylar hisoboti ham yangi yo'nalish bo'yicha bo'linadi (tur — yagona manba; sof foyda jami o'zgarmaydi)."""
    _cid = auth.company_id_of(current_user)
    pt = db.query(ProductType).filter(ProductType.id == pt_id, ProductType.company_id == _cid).first()
    if not pt:
        raise HTTPException(status_code=404, detail="Mahsulot turi topilmadi")
    try:
        toza = schemas.ProductTypeYonalish(**data) if isinstance(data, dict) else None
    except Exception:
        toza = None
    if toza is None:
        raise HTTPException(status_code=400, detail="Faqat 'yonalish_id' (butun son) yuboriladi")
    try:
        _yid, _ = crud.yonalish_tanlovi(db, _cid, toza.yonalish_id, joriy_id=pt.yonalish_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _nomlar = crud.yonalish_nomlari(db, _cid)
    _eski = _nomlar.get(pt.yonalish_id, "Belgilanmagan") if pt.yonalish_id else "Belgilanmagan"
    if _yid == pt.yonalish_id:
        # kech146 (zip 183, audit J5): o'sha yo'nalish qayta tanlandi — jurnalga soxta «tahrirlandi» yozilmaydi
        return pt
    pt.yonalish_id = _yid
    crud.log_activity(db, "updated", "product_type", pt.id, f"Mahsulot turi «{pt.name}»", _kim(current_user),
                      old_value=f"yo'nalish: {_eski}", new_value=f"yo'nalish: {_nomlar.get(_yid, '')}",
                      company_id=_cid, commit=False)
    db.commit()
    db.refresh(pt)
    return pt


# kech120 (zip 133 — F bosqichi 3-qism, audit G5-06): turni TAHRIRLASH. Ilgari saqlangach nomi, birligi, kiritish shakli, narx usulini
# o'zgartiradigan yo'l yo'q edi — xato yozilgan birlik yoki takror tur abadiy qolardi. Qoida: nom (takrorsiz), narx usuli, qat'iy narx,
# qoplama, izoh, yo'nalish — har doim; BIRLIK va KIRITISH SHAKLI — faqat tur hali hech qayerda ishlatilmagan bo'lsa (retsept partiyasi,
# buyurtma miqdori, ishlab chiqarish va tayyor mahsulot shu birlikda; `service.tur_ishlatilishi`) — aks holda 409 sababi bilan.
# Ko'rinishi bir xil birlik («m2» → «m²», «ta» → «dona» — `services.birlik_korinish`) — ishlatilgan turda ham ruxsat.
_TUR_KIRITISH133 = {"quantity_only": "faqat miqdor", "dimensional_3d": "o'lcham 3D", "area_2d": "maydon",
                    "weight_volume": "og'irlik / hajm", "flexible_unit": "moslashuvchan"}


@router.put("/product-types/{pt_id}", response_model=schemas.ProductTypeRead)
def update_product_type(pt_id: int, data: dict = Body(...), db: Session = Depends(get_db),
                        current_user=Depends(auth.ruxsat("mahsulot_turi", "tahrirlash"))):
    import services as _sv133
    data = _tana("ProductType", data, schemas.ProductTypeCreate)
    _cid = auth.company_id_of(current_user)
    pt = db.query(ProductType).filter(ProductType.id == pt_id, ProductType.company_id == _cid,
                                      ProductType.is_active == True).first()  # noqa: E712
    if not pt:
        raise HTTPException(status_code=404, detail="Mahsulot turi topilmadi")
    # kech146 (zip 181, review181 F4 — ESKI, O'LCHANGAN HAQIQIY PG 16): nom tekshiruvi — yaratishdagi korxona qulfi ostida (ilgari faqat
    # yaratishda edi: nomini «RV X» ga o'zgartirish ∥ «RV X» yaratish — ikkita faol «RV X»)
    crud._pul_qulfi(db, TUR_NOMI_QULF_NS, _cid)
    _nom = (data.name or "").strip()
    _unit = (data.unit or "").strip()
    _bor = db.query(ProductType.id).filter(
        ProductType.company_id == _cid, ProductType.is_active == True, ProductType.id != pt.id,  # noqa: E712
        func.lower(func.trim(ProductType.name)) == _nom.lower()).first()
    if _bor:
        raise HTTPException(status_code=400, detail=f"'{_nom}' nomli mahsulot turi allaqachon bor. Boshqa nom tanlang.")
    _birlik_ozgardi = _sv133.birlik_korinish(_unit) != _sv133.birlik_korinish(pt.unit)
    _shakl_ozgardi = data.input_template != pt.input_template
    if _birlik_ozgardi or _shakl_ozgardi:
        _ish = service.tur_ishlatilishi(db, _cid, [pt.id]).get(pt.id) or {}
        _matn = service.tur_ishlatilishi_matni(_ish)
        if _matn:
            _nima = " va ".join([x for x in ("o'lchov birligi" if _birlik_ozgardi else "",
                                              "kiritish shakli" if _shakl_ozgardi else "") if x])
            raise HTTPException(status_code=409, detail={
                "type": "product_type_used",
                "message": (f"«{pt.name}» ishlatilgan ({_matn}) — {_nima} o'zgartirilmaydi: eski retsept, buyurtma va ishlab "
                            "chiqarish tarixi shu birlikda. Nom, narx, qoplama va izohni o'zgartirish mumkin; boshqa birlik "
                            "kerak bo'lsa — yangi mahsulot turi qo'shing.")})
    _yid = pt.yonalish_id
    if data.yonalish_id is not None:
        try:
            _yid, _ = crud.yonalish_tanlovi(db, _cid, data.yonalish_id, joriy_id=pt.yonalish_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    _eski = {"nomi": pt.name, "birlik": pt.unit, "kiritish": _TUR_KIRITISH133.get(pt.input_template, pt.input_template),
             "narx usuli": pt.pricing_formula,
             "qat'iy narx": crud.audit_son(pt.fixed_unit_price) if pt.fixed_unit_price is not None else "—",
             "qoplama": ("×" + crud.audit_son(pt.coating_price_multiplier)) if pt.supports_coating else "yo'q",
             "izoh": (pt.notes or "").strip(), "yo'nalish": pt.yonalish_id}
    pt.name = _nom
    pt.unit = _unit
    pt.input_template = data.input_template
    pt.pricing_formula = data.pricing_formula
    pt.fixed_unit_price = data.fixed_unit_price
    pt.supports_coating = bool(data.supports_coating)
    pt.coating_price_multiplier = data.coating_price_multiplier
    pt.notes = data.notes
    pt.yonalish_id = _yid
    _yangi = {"nomi": pt.name, "birlik": pt.unit, "kiritish": _TUR_KIRITISH133.get(pt.input_template, pt.input_template),
              "narx usuli": pt.pricing_formula,
              "qat'iy narx": crud.audit_son(pt.fixed_unit_price) if pt.fixed_unit_price is not None else "—",
              "qoplama": ("×" + crud.audit_son(pt.coating_price_multiplier)) if pt.supports_coating else "yo'q",
              "izoh": (pt.notes or "").strip(), "yo'nalish": pt.yonalish_id}
    _farq = [k for k in _eski if _eski[k] != _yangi[k]]
    if _farq:
        _ynom = crud.yonalish_nomlari(db, _cid)

        def _q(d, k):
            v = d[k]
            if k == "yo'nalish":
                return _ynom.get(v, "Belgilanmagan") if v else "Belgilanmagan"
            if k == "izoh":
                return "bor" if v else "yo'q"
            return str(v)
        crud.log_activity(db, "updated", "product_type", pt.id, f"Mahsulot turi «{pt.name}»", _kim(current_user),
                          old_value="; ".join(f"{k}: {_q(_eski, k)}" for k in _farq),
                          new_value="; ".join(f"{k}: {_q(_yangi, k)}" for k in _farq), company_id=_cid, commit=False)
    db.commit()
    db.refresh(pt)
    return pt


@router.delete("/product-types/{pt_id}")
def deactivate_product_type(pt_id: int, db: Session = Depends(get_db), current_user=Depends(auth.ruxsat("mahsulot_turi", "ochirish"))):
    """O'chirilmaydi (eski BOM/ProductionOrder tarixi buzilmasligi
    uchun) — faqat 'nofaol' qilib belgilanadi, xuddi mavjud
    Inventory.is_deleted naqshiga o'xshab.
    kech120 (zip 133 — G5-06): qoralama / jarayondagi ishlab chiqarishi bor tur nofaol qilinmaydi (409 — avval yakunlang yoki bekor
    qiling); sahifada endi «O'chirish» tugmasi bor (ilgari faqat API)."""
    pt = db.query(ProductType).filter(ProductType.id == pt_id, ProductType.company_id == auth.company_id_of(current_user)).first()
    if not pt:
        raise HTTPException(status_code=404, detail="Mahsulot turi topilmadi")
    _ochiq133 = (service.tur_ishlatilishi(db, pt.company_id, [pt.id]).get(pt.id) or {}).get("ochiq_ishlab", 0)
    if _ochiq133:
        raise HTTPException(status_code=409, detail={
            "type": "product_type_in_production",
            "message": (f"«{pt.name}»: {_ochiq133} ta ishlab chiqarish hali ochiq (qoralama yoki jarayonda) — avval ularni "
                        "yakunlang yoki bekor qiling, so'ng turni o'chiring.")})
    pt.is_active = False
    crud.log_activity(db, "deleted", "product_type", pt.id, f"Mahsulot turi «{pt.name}»", _kim(current_user),
                      new_value="nofaol qilindi (eski retsept va ishlab chiqarish tarixi saqlanadi)",
                      company_id=pt.company_id, commit=False)   # kech110 (2c)
    db.commit()
    return {"status": "ok"}


# ============================================================
# RETSEPTLAR (BOM)
# ============================================================

@router.get("/product-types/{pt_id}/boms", response_model=list[schemas.BOMRead])
def list_boms_for_product(pt_id: int, db: Session = Depends(get_db), current_user=Depends(auth.ruxsat("mahsulot_turi", "korish"))):
    return db.query(BOM).filter(
        BOM.product_type_id == pt_id, BOM.company_id == auth.company_id_of(current_user), BOM.is_active == True
    ).all()


@router.post("/boms", response_model=schemas.BOMRead)
def create_bom(data: dict = Body(...), db: Session = Depends(get_db), current_user=Depends(auth.ruxsat("mahsulot_turi", "yaratish")),
               request: Request = None, response: Response = None):
    # kech93 (8-band): tana QAT'IY (`_tana`), materiallar — shu korxonadan.
    data = _tana("BOM", data, schemas.BOMCreate)
    pt = db.query(ProductType).filter(ProductType.id == data.product_type_id, ProductType.company_id == auth.company_id_of(current_user)).first()
    if not pt:
        raise HTTPException(status_code=404, detail="Mahsulot turi topilmadi")
    _retsept_materiallari(db, data.items, auth.company_id_of(current_user))
    # kech144 (zip 181, audit A1): `X-Amal-Kaliti` — ikki marta bosish ikkinchi tarkib yaratmaydi; nom tekshiruvi — mahsulot turi qulfi ostida
    kalit = _amal_kaliti(request)

    def _bajar():
        crud._pul_qulfi(db, TARKIB_NOMI_QULF_NS, pt.id)
        # QO'SHILDI 2026-09-20 — variant nomi ham TAKRORLANMASIN (yuqoridagi
        # bilan bir xil sabab: ro'yxatda ikkita "Standart" ajralmaydi).
        # kech93: faqat bo'shliqli nom ham "Standart" (ilgari '' saqlanardi).
        _vnom = (data.variant_name or "").strip() or "Standart"
        _bor = db.query(BOM).filter(
            BOM.product_type_id == pt.id,
            BOM.company_id == auth.company_id_of(current_user),
            BOM.is_active == True,
            func.lower(func.trim(BOM.variant_name)) == _vnom.lower(),
        ).first()
        if _bor:
            raise HTTPException(
                status_code=400,
                detail=f"Bu mahsulotda '{_vnom}' nomli tarkib allaqachon bor. Boshqa nom tanlang.")
        bom = BOM(
            company_id=auth.company_id_of(current_user),
            product_type_id=pt.id,
            variant_name=_vnom,
            batch_quantity=data.batch_quantity,
            notes=data.notes,
        )
        db.add(bom)
        db.flush()
        for item_data in data.items:
            # Qoida #6 (Multi-tenancy): BOMItem endi to'g'ridan-to'g'ri
            # company_id'ga ega — ota-BOM orqali bilvosita emas.
            db.add(BOMItem(bom_id=bom.id, company_id=auth.company_id_of(current_user), **item_data.model_dump()))
        db.flush()
        db.refresh(bom)
        # kech110 (2c): Faoliyat jurnali — amal bilan BITTA tranzaksiyada
        crud.log_activity(db, "created", "bom", bom.id, f"Retsept «{bom.variant_name}» — {pt.name}", _kim(current_user),
                          new_value=_retsept_xulosa(bom, pt.unit), company_id=bom.company_id, commit=False)
        db.commit()
        db.refresh(bom)
        return schemas.BOMRead.model_validate(bom).model_dump(mode="json")
    javob, _ = _amal_bajar(db, current_user, response, "tarkib", kalit, _bajar)
    return javob


@router.post("/boms/preview")
def preview_bom(data: dict = Body(...), db: Session = Depends(get_db), current_user=Depends(auth.ruxsat("mahsulot_turi", "korish"))):
    """kech113 (dizayn 2-band — retsept oynasi): SAQLANMAGAN retseptning taxminiy tannarxi (1 birlik uchun: oddiy,
    qoplamali, hamma ixtiyoriy bilan) va har qator narxi — ishlab chiqarish suratidagi AYNAN hisob
    (`production_service.retsept_tannarxi`). Tana — retsept yaratish bilan bir xil (qat'iy tekshiruv, materiallar —
    shu korxonadan); hech narsa yozilmaydi."""
    data = _tana("BOM", data, schemas.BOMCreate)
    _cid = auth.company_id_of(current_user)
    pt = db.query(ProductType).filter(ProductType.id == data.product_type_id, ProductType.company_id == _cid).first()
    if not pt:
        raise HTTPException(status_code=404, detail="Mahsulot turi topilmadi")
    _retsept_materiallari(db, data.items, _cid)
    return service.retsept_tannarxi(db, _cid, pt, data)


@router.put("/boms/{bom_id}", response_model=schemas.BOMRead)
def update_bom(bom_id: int, data: dict = Body(...), db: Session = Depends(get_db), current_user=Depends(auth.ruxsat("mahsulot_turi", "tahrirlash"))):
    """MUHIM: bu FAQAT hali IN_PROGRESS/COMPLETED bo'lmagan kelajakdagi
    ishlab chiqarishlarga ta'sir qiladi — chunki boshlangan buyurtmalar
    o'zining recipe_snapshot_json'idan foydalanadi, JORIY BOM'ni emas."""
    # kech93 (8-band): tana QAT'IY (`_tana`), materiallar — shu korxonadan.
    data = _tana("BOM", data, schemas.BOMCreate)
    # kech146 (zip 181, review181 F4 — ESKI, O'LCHANGAN HAQIQIY PG 16): tarkib nomi tekshiruvi — yaratishdagi mahsulot turi qulfi
    # ostida (ilgari faqat yaratishda: «Boshqa» → «Standart» ∥ «Standart» yaratish — ikkita faol «Standart»). Tartib — yaratish bilan
    # bir: AVVAL nom qulfi, keyin tarkib qatori (mahsulot turi tahrirda o'zgarmaydi — qulfsiz o'qiladi)
    _pt146 = db.query(BOM.product_type_id).filter(BOM.id == bom_id, BOM.company_id == auth.company_id_of(current_user)).first()
    if _pt146 is not None and _pt146[0] is not None:
        crud._pul_qulfi(db, TARKIB_NOMI_QULF_NS, _pt146[0])
    # kech142 (zip 170, A-O02): retsept qatori QULFLANADI va qayta o'qiladi — ikki parallel saqlash navbat bilan
    # (ikkinchisi birinchisining qatorlarini ko'radi; ilgari PG da qatorlar IKKI baravar bo'lib qolishi mumkin edi).
    bom = db.query(BOM).filter(BOM.id == bom_id, BOM.company_id == auth.company_id_of(current_user)
                               ).populate_existing().with_for_update().first()
    if not bom:
        raise HTTPException(status_code=404, detail="Mahsulot tarkibi topilmadi")
    _retsept_materiallari(db, data.items, auth.company_id_of(current_user))
    _vnom = (data.variant_name or "").strip() or "Standart"
    _bor = db.query(BOM).filter(
        BOM.product_type_id == bom.product_type_id,
        BOM.company_id == auth.company_id_of(current_user),
        BOM.is_active == True,
        BOM.id != bom.id,
        func.lower(func.trim(BOM.variant_name)) == _vnom.lower(),
    ).first()
    if _bor:
        raise HTTPException(
            status_code=400,
            detail=f"Bu mahsulotda '{_vnom}' nomli boshqa tarkib bor. Boshqa nom tanlang.")
    _pt110 = db.query(ProductType).filter(ProductType.id == bom.product_type_id,
                                          ProductType.company_id == bom.company_id).first()
    _unit110 = _pt110.unit if _pt110 else ""
    _eski110 = _retsept_xulosa(bom, _unit110)      # kech110 (2c): o'zgarishdan OLDINGI holat
    _holat120 = _retsept_holati(bom)               # kech120 (zip 129 — G6-23): nima o'zgarganini yozish uchun
    bom.variant_name = _vnom
    bom.batch_quantity = data.batch_quantity
    bom.notes = data.notes
    # kech142 (zip 170, A-O02 — O'LCHANGAN HAQIQIY PG `work/audit/tasdiq/ombor/p_o02.py`): qatorlar JOYIDA yangilanadi
    # (mos qator id si saqlanadi — `service.retsept_qatorlarini_yangila`). Ilgari hammasi o'chirilib qayta yaratilardi —
    # qoralama ishlab chiqarishning qoplama tanlovi eski id larda qolib, o'zgarishsiz saqlash ham qoplamani tushirardi.
    service.retsept_qatorlarini_yangila(db, bom, data.items, auth.company_id_of(current_user))
    db.expire(bom, ["items"])
    # kech110 (2c): Faoliyat jurnali — eski → yangi (amal bilan BITTA tranzaksiyada)
    try:        # farq matnidagi kutilmagan xato retseptni saqlashga xalaqit bermasin — yozuv qisqa tavsif bilan qoladi
        _farq120 = crud.audit_farq_matni(_retsept_farqi(db, bom.company_id, _holat120, _retsept_holati(bom), _unit110))
    except Exception:
        _farq120 = ""
    crud.log_activity(db, "updated", "bom", bom.id,
                      f"Retsept «{bom.variant_name}» — {_pt110.name if _pt110 else 'mahsulot'}", _kim(current_user),
                      old_value=_eski110, new_value=_retsept_xulosa(bom, _unit110) + _farq120,
                      company_id=bom.company_id, commit=False)
    db.commit()
    db.refresh(bom)
    return bom


@router.delete("/boms/{bom_id}")
def deactivate_bom(bom_id: int, db: Session = Depends(get_db), current_user=Depends(auth.ruxsat("mahsulot_turi", "ochirish"))):
    """2026-09-16: ProductType.is_active bilan bir xil naqsh — BOM
    o'chirilmaydi (eski ProductionOrder'lar o'zining recipe_snapshot_json
    surati bilan ishlaydi, JORIY BOM'ga bog'liq emas, shuning uchun
    o'chirish ularga zarar keltirmaydi), faqat yangi buyurtmalar uchun
    tanlov ro'yxatidan yashiriladi."""
    bom = db.query(BOM).filter(BOM.id == bom_id, BOM.company_id == auth.company_id_of(current_user)).first()
    if not bom:
        raise HTTPException(status_code=404, detail="Mahsulot tarkibi topilmadi")
    bom.is_active = False
    _pt110 = db.query(ProductType).filter(ProductType.id == bom.product_type_id,
                                          ProductType.company_id == bom.company_id).first()
    crud.log_activity(db, "deleted", "bom", bom.id,
                      f"Retsept «{bom.variant_name}» — {_pt110.name if _pt110 else 'mahsulot'}", _kim(current_user),
                      new_value="nofaol qilindi (boshlangan ishlab chiqarishlar o'z suratidan foydalanadi)",
                      company_id=bom.company_id, commit=False)   # kech110 (2c)
    db.commit()
    return {"status": "ok"}


# ============================================================
# ISHLAB CHIQARISH BUYURTMALARI (ProductionOrder)
# ============================================================

def _oy_qiymati(oy: str):
    """`oy` — "YYYY-MM" (Toshkent kalendar oyi) → (yil, oy). Noto'g'ri qiymat — 400 (matn bilan)."""
    try:
        yil_s, oy_s = str(oy).strip().split("-")
        yil, oyn = int(yil_s), int(oy_s)
        if len(yil_s) != 4 or not (2000 <= yil <= 2100) or not (1 <= oyn <= 12):
            raise ValueError
        return yil, oyn
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Davr «YYYY-MM» shaklida bo'lishi kerak (masalan 2026-09)")


@router.get("/orders", response_model=list[schemas.ProductionOrderListItem])
def list_production_orders(status: str = None, oy: str = None, db: Session = Depends(get_db),
                           current_user=Depends(auth.ruxsat("ishlab_buyurtma", "korish"))):
    """kech113 (dizayn 4-band): `oy` = "YYYY-MM" — shu Toshkent oyida YAKUNLANGAN / BEKOR QILINGANLAR va HAMMA hali
    ochiq (qoralama, jarayondagi) ishlab chiqarishlar (ochiq ish oy o'tsa ham ro'yxatdan tushib qolmasin);
    `oy` yo'q yoki "hammasi" — hammasi (avvalgidek). Har qatorga ko'rsatish uchun qo'shimcha maydonlar —
    `production_service.royxat_qoshimchalari` (so'rovlar soni qator soniga bog'liq emas)."""
    _cid = auth.company_id_of(current_user)
    q = db.query(ProductionOrder).filter(ProductionOrder.company_id == _cid)
    if status:
        q = q.filter(ProductionOrder.status == status)
    if oy and str(oy).strip().lower() != "hammasi":
        yil, oyn = _oy_qiymati(oy)
        q = q.filter(or_(
            ProductionOrder.status.in_([service.ProductionOrderStatus.DRAFT.value,
                                        service.ProductionOrderStatus.IN_PROGRESS.value]),
            and_(ProductionOrder.status == service.ProductionOrderStatus.COMPLETED.value,
                 tashkent_oyida(ProductionOrder.completed_at, yil, oyn)),
            and_(ProductionOrder.status == service.ProductionOrderStatus.CANCELLED.value,
                 tashkent_oyida(ProductionOrder.cancelled_at, yil, oyn)),
        ))
    rows = q.order_by(ProductionOrder.created_at.desc(), ProductionOrder.id.desc()).all()
    qoshimcha = service.royxat_qoshimchalari(db, _cid, rows)
    natija = []
    for r in rows:
        d = _serialize_po(r)
        d.update(qoshimcha.get(r.id, {}))
        natija.append(d)
    return natija


@router.get("/orders/preview")
def preview_production_order(product_type_id: int = Query(...), bom_id: int = Query(...), quantity: float = Query(...),
                             source_type: str = Query("warehouse_stock"),
                             source_order_item_id: Optional[int] = Query(None),
                             selected_optional_bom_item_ids: List[int] = Query(default=[]),
                             db: Session = Depends(get_db), current_user=Depends(auth.ruxsat("ishlab_buyurtma", "korish"))):
    """kech113 (dizayn 3-band — «Yangi ishlab chiqarish» oynasi): yaratish + boshlash natijasi OLDINDAN — xomashyo
    yetadimi, qanchasi yetmaydi, eng ko'pi qancha chiqadi, taxminiy tannarx. Hech narsa yozilmaydi; tekshiruvlar
    yaratish / boshlash bilan AYNAN (`production_service.ishlab_chiqarish_rejasi`). Qiymatlar YARATISH tanasi
    kabi tekshiriladi (`_tana("ProductionOrder", …)` — chegaralar, manba turi, id lar): yaratish rad etadigan
    qiymatga reja «mumkin» demasin."""
    _xom = {"product_type_id": product_type_id, "bom_id": bom_id, "quantity": quantity, "source_type": source_type,
            "selected_optional_bom_item_ids": list(selected_optional_bom_item_ids or [])}
    if source_order_item_id is not None:
        _xom["source_order_item_id"] = source_order_item_id
    data = _tana("ProductionOrder", _xom, schemas.ProductionOrderCreate)
    natija = service.ishlab_chiqarish_rejasi(db, auth.company_id_of(current_user), data)
    if not natija.get("success"):
        raise HTTPException(status_code=400, detail=natija.get("message") or "Reja hisoblanmadi")
    return natija


@router.get("/orders/{po_id}/preview")
def preview_existing_production_order(po_id: int, db: Session = Depends(get_db),
                                      current_user=Depends(auth.ruxsat("ishlab_buyurtma", "korish"))):
    """kech113 («Boshlash» / «Yakunlash» oynasi): qoralama — joriy retsept bilan boshlash rejasi, jarayondagi — qotgan
    surat bilan yakunlash rejasi (`production_service.mavjud_ishlab_chiqarish_rejasi`). Hech narsa yozilmaydi."""
    natija = service.mavjud_ishlab_chiqarish_rejasi(db, po_id, auth.company_id_of(current_user))
    if not natija.get("success"):
        raise HTTPException(status_code=natija.get("kod") or 409, detail=natija.get("message") or "Reja hisoblanmadi")
    return natija


@router.get("/mrp-order-items")
def list_mrp_order_items_pending(product_type_id: int = None, db: Session = Depends(get_db), current_user=Depends(auth.ruxsat("ishlab_buyurtma", "korish"))):
    """2026-09-17: "Mijoz buyurtmasi asosida" ishlab chiqarish uchun —
    hali to'liq ta'minlanmagan (remaining_quantity > 0) buyurtma-
    detallari ro'yxati, ixtiyoriy ravishda bitta mahsulot turi bo'yicha
    filtrlangan."""
    return service.get_mrp_order_items_status(db, auth.company_id_of(current_user), product_type_id)


@router.post("/orders")
def create_order(data: dict = Body(...), db: Session = Depends(get_db), current_user=Depends(auth.ruxsat("ishlab_buyurtma", "yaratish")),
                 request: Request = None, response: Response = None):
    # kech93 (8-band): tana QAT'IY (`_tana`); manba bog'lanishlari — servisda (K93-1).
    data = _tana("ProductionOrder", data, schemas.ProductionOrderCreate)
    # kech144 (zip 181, audit A2): `X-Amal-Kaliti` — 502 / javob yo'qolgandan keyin qayta bosish IKKINCHI ishlab chiqarish yaratmaydi
    kalit = _amal_kaliti(request)

    def _bajar():
        result = service.create_production_order(db, auth.company_id_of(current_user), data, created_by=current_user.full_name or current_user.username)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return {"success": True, "production_order": _serialize_po(result["production_order"])}
    javob, _ = _amal_bajar(db, current_user, response, "ishlab_yaratish", kalit, _bajar)
    return javob


@router.post("/orders/{po_id}/start")
def start_order(po_id: int, db: Session = Depends(get_db), current_user=Depends(auth.ruxsat("ishlab_buyurtma", "tahrirlash")),
                request: Request = None, response: Response = None):
    # ESLATMA (qoida #4): "Guardrails" talabida qattiq bloklashda HTTP 400
    # so'ralgan edi; bu yerda ATAYLAB 409 (Conflict) qoldirildi — chunki bu
    # "so'rov noto'g'ri tuzilgan" (400 ning ma'nosi) emas, balki "so'rov
    # to'g'ri, lekin joriy holat/ombor bilan ziddiyatda" degani (masalan
    # noto'g'ri holatdagi buyurtmani boshlash — shu yerning o'zida ham 409
    # qaytaradi). Ikkalasi BIR XIL endpoint ichida bo'lgani uchun, ikkitasi
    # ham 409 bo'lishi frontend uchun izchil. Agar 400'ni qat'iy xohlasangiz
    # — shu qatordagi status_code'ni almashtirish yetarli.
    # kech144 (zip 181, audit A2): `X-Amal-Kaliti` — javobi yo'qolgan «Boshlash» ni qayta bosish birinchi javobni oladi (ilgari 409
    # «allaqachon boshlangan» — boshlangan-u, ekranda xato)
    kalit = _amal_kaliti(request)

    def _bajar():
        result = service.start_production_order(db, po_id, auth.company_id_of(current_user), performed_by=current_user.full_name or current_user.username)
        if not result["success"]:
            raise HTTPException(status_code=409, detail={"message": result["message"], "stock_issues": result.get("stock_issues", [])})
        return {
            "success": True,
            "production_order": _serialize_po(result["production_order"]),
            "stock_warnings": result.get("stock_warnings", []),
        }
    javob, _ = _amal_bajar(db, current_user, response, "ishlab_boshlash", kalit, _bajar)
    return javob


@router.post("/orders/{po_id}/complete")
def complete_order(po_id: int, db: Session = Depends(get_db), current_user=Depends(auth.ruxsat("ishlab_buyurtma", "tahrirlash")),
                   request: Request = None, response: Response = None):
    kalit = _amal_kaliti(request)      # kech144 (zip 181, audit A2)

    def _bajar():
        result = service.complete_production_order(db, po_id, auth.company_id_of(current_user), performed_by=current_user.full_name or current_user.username)
        if not result["success"]:
            raise HTTPException(status_code=409, detail=result["message"])
        return {"success": True, "production_order": _serialize_po(result["production_order"])}
    javob, _ = _amal_bajar(db, current_user, response, "ishlab_yakunlash", kalit, _bajar)
    return javob


@router.post("/orders/{po_id}/cancel")
def cancel_order(po_id: int, db: Session = Depends(get_db), current_user=Depends(auth.ruxsat("ishlab_buyurtma", "ochirish")),
                 request: Request = None, response: Response = None):
    kalit = _amal_kaliti(request)      # kech144 (zip 181, audit A2)

    def _bajar():
        result = service.cancel_production_order(db, po_id, auth.company_id_of(current_user), performed_by=current_user.full_name or current_user.username)
        if not result["success"]:
            raise HTTPException(status_code=409, detail=result["message"])
        return {"success": True, "production_order": _serialize_po(result["production_order"])}
    javob, _ = _amal_bajar(db, current_user, response, "ishlab_bekor", kalit, _bajar)
    return javob


# ============================================================
# KORXONA SOZLAMALARI (allow_negative_stock)
# ============================================================

@router.get("/company-settings")
def get_company_settings(db: Session = Depends(get_db), current_user=Depends(auth.ruxsat("sozlama", "korish"))):
    c = db.query(Company).filter(Company.id == auth.company_id_of(current_user)).first()
    if not c:
        raise HTTPException(status_code=404, detail="Korxona topilmadi (init_production_module ishga tushirilmagan bo'lishi mumkin)")
    return {"allow_negative_stock": c.allow_negative_stock}


@router.put("/company-settings")
def update_company_settings(allow_negative_stock: bool, db: Session = Depends(get_db), current_user=Depends(auth.ruxsat("sozlama", "tahrirlash"))):
    c = db.query(Company).filter(Company.id == auth.company_id_of(current_user)).first()
    if not c:
        raise HTTPException(status_code=404, detail="Korxona topilmadi")
    _eski110 = bool(c.allow_negative_stock)
    c.allow_negative_stock = allow_negative_stock
    if _eski110 != bool(allow_negative_stock):
        # kech110 (2c): xavfli sozlama — omborda yetmasa ham ishlab chiqarishga ruxsat
        crud.log_activity(db, "updated", "company_settings", c.id, "Manfiy qoldiq bilan ishlab chiqarishga ruxsat",
                          _kim(current_user), old_value=("ha" if _eski110 else "yo'q"),
                          new_value=("ha" if allow_negative_stock else "yo'q"), company_id=c.id, commit=False)
    db.commit()
    return {"status": "ok"}


# ============================================================
# Yordamchi — JSON snapshot'ni sxemaga mos parse qilib beradi
# ============================================================

def _serialize_po(po: ProductionOrder) -> dict:
    import json
    data = schemas.ProductionOrderRead.model_validate(po).model_dump()
    data["recipe_snapshot"] = json.loads(po.recipe_snapshot_json) if po.recipe_snapshot_json else []
    return data
