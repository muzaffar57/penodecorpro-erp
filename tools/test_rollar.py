#!/usr/bin/env python3
"""
test_rollar.py — kech118 ROLLAR VA RUXSATLAR (egasi QARORI 2026-09-30 15:23: «Hodim rollarini admin o'zi boshqaradigan
qilaylik»; tugmali javoblar 15:30 — rasmdagidek 4 belgi (Ko'rish / Yaratish / Tahrirlash / O'chirish), pul sirlari alohida
ruxsat «Tannarx va foyda», tayyor rollar Admin / Menejer / Omborchi / Moliyachi; QAYTA SO'RALMAYDI).

NIMA UCHUN KERAK
  Ilgari huquq kodga qotirilgan edi: har marshrut `Depends(auth.admin_or_manager)` kabi rol-ro'yxatli qorovul bilan, menyu va
  tugmalar — `current_user.role.value == 'admin'` bilan. Endi: korxona rollari (`rollar` jadvali), har marshrut — rol RUXSATI
  (`auth.ruxsat(band, amal)`), menyu / tugmalar — `current_user.ruxsat(...)`. ENG MUHIM TALAB — o'zgarishdan keyin eski
  foydalanuvchilarning huquqi AYNAN qoladi (egasi: Menejer «ruxsatlari hozirgidek»).
TALAB (har biri o'lchanadi):
  S  katalog va tayyor rollar izchil; HAR marshrut quyidagi ESKI jadvalda (o'zgarishdan OLDINGI qorovul — rol harflari:
     A Admin, M Menejer, F Moliyachi, W Omborchi, U Usta); marshrut qorovuli + tayyor rol ruxsatlari → eski rollar uchun kirish
     ESKI jadval bilan AYNAN, farq — faqat FARQLAR ro'yxatidagi 14 ta ATAYLAB o'zgarish (sababi yonida); eski qorovul nomlari
     va shablonlarda rol turi shartlari qolmagan;
  H  HAQIQIY HTTP (har eski rol turidagi foydalanuvchi — migratsiya kabi tayyor roliga biriktirilgan): hamma marshrut ×
     5 rol — rad (401 / 403) ⇔ kutilgan; bosh sahifa yo'naltirishi; menyu havolalari (eski ro'yxat + Admin uchun «Rollar»);
  R  rollar API: yaratish / tahrirlash / tekshiruv (nom, katalog), Admin roli qulf, tayyor rol o'chirilmaydi, foydalanuvchili
     rol o'chirilmaydi, andozaga qaytarish, rol biriktirish (o'zini — yo'q, oxirgi Admin — yo'q, boshqa korxona — yo'q), jurnal
     yozuvi, o'zgarish DARHOL ta'sir qiladi (qayta kirishsiz); HAR (band, amal) juftligi uchun yakka ruxsatli rol — hamma
     marshrutda faqat shu juftni talab qiluvchilar ochiq; korxona chegarasi; birorta bo'limi yo'q rol — 403 sahifa;
  M  migratsiya: `rol_id` bo'sh foydalanuvchi — eski turining tayyor roliga (master — «Usta (eski)»), takroriy ishga
     tushishda o'zgarish yo'q; rol biriktirilmagan / boshqa korxona roli — eski turining andozasi (xavfsiz tomon).
REJIMLAR: SQLite (odatiy); `PG_URL` bilan HAQIQIY PostgreSQL 16.
ISHLATISH: python3 tools/test_rollar.py
"""
import os
import re
import sys
import json
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PG_URL = (os.environ.get("PG_URL") or "").rstrip("/")
PG_BAZA = "rollar_test"
_T = tempfile.mkdtemp(prefix="rollar_")
if PG_URL:
    from sqlalchemy import create_engine as _ce, text as _tx
    _adm = _ce(PG_URL.replace("postgresql://", "postgresql+pg8000://", 1) + "/postgres", isolation_level="AUTOCOMMIT")
    with _adm.connect() as _c:
        _c.execute(_tx(f"DROP DATABASE IF EXISTS {PG_BAZA} WITH (FORCE)"))
        _c.execute(_tx(f"CREATE DATABASE {PG_BAZA}"))
    _adm.dispose()
    os.environ["DATABASE_URL"] = f"{PG_URL}/{PG_BAZA}"
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_T, 'rollar_test.db')}"
os.environ.pop("TENANT_FILTER", None)

import io                                          # noqa: E402
import contextlib                                  # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    import main                                    # noqa: E402
    import auth                                    # noqa: E402
import ruxsatlar as RX                             # noqa: E402
from database import SessionLocal                  # noqa: E402
from models import UserRole, User, Rol, ActivityLog   # noqa: E402
from production_models import Company              # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402
from fastapi.routing import APIRoute               # noqa: E402
from starlette.requests import Request             # noqa: E402
from fastapi import HTTPException                  # noqa: E402

YORLIQ = "[PG] " if PG_URL else ""
OK = FAIL = 0
FAILED = []


def check(label, cond, detail=""):
    global OK, FAIL
    label = YORLIQ + label
    try:
        cond = bool(cond)
    except Exception as e:                 # noqa: BLE001
        cond = False
        detail = f"{type(e).__name__}: {e}"
    if cond:
        OK += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        FAILED.append(label)
        print(f"  ✗ {label}   {str(detail)[:900]}")


def section(t):
    print(f"\n--- {t} ---")


def js(r):
    try:
        return r.json()
    except Exception:                      # noqa: BLE001
        return {}


# ESKI qorovullar (o'zgarishdan OLDIN — staging 27be876 + zip 118; work/k119/rol_xarita.py bilan O'LCHANGAN): marshrut →
# kirish huquqi bor rollar (A Admin, M Menejer (manager), F Moliyachi (accountant), W Omborchi (warehouse), U Usta (master));
# «-» — qorovulsiz (ochiq yoki ichida tekshiriladi), LOGIN — har qanday kirgan, PLAT — platforma admini, EMP — hodim paneli.
# YANGI marshrut qo'shilsa — shu jadvalga (yoki YANGI_MARSHRUTLAR ga) qo'shilsin: jadvalsiz marshrut — test yiqiladi.
ESKI = {
    "GET /": "-",
    "POST /api/admin/advance-requests/{request_id}/confirm": "AF",
    "POST /api/admin/advance-requests/{request_id}/reject": "AF",
    "GET /api/admin/pending-advance-requests": "AF",
    "GET /api/cron/cleanup-sessions": "-",
    "GET /api/cron/find-chat-id": "-",
    "GET /api/cron/low-stock-check": "-",
    "GET /api/dashboard/charts": "AF",
    "GET /api/dashboard/debts": "AM",
    "GET /api/dashboard/deliveries": "AM",
    "GET /api/dashboard/production-periods": "AF",
    "GET /api/dashboard/stats": "AF",
    "GET /api/dashboard/today": "AF",
    "GET /api/dashboard/today-tasks": "LOGIN",
    "GET /api/dashboard/top-finished-products": "AF",
    "POST /api/deliveries": "AM",
    "DELETE /api/deliveries/{delivery_id}": "AM",
    "GET /api/deliveries/{delivery_id}/pdf": "AM",
    "GET /api/employees": "A",
    "POST /api/employees": "A",
    "DELETE /api/employees/advance/{advance_id}": "A",
    "POST /api/employees/backfill-compensation-history": "A",
    "DELETE /api/employees/{emp_id}": "A",
    "PUT /api/employees/{emp_id}": "A",
    "GET /api/employees/{emp_id}/compensation-history": "A",
    "DELETE /api/employees/{emp_id}/permanent": "A",
    "POST /api/employees/{emp_id}/restore": "A",
    "POST /api/employees/{emp_id}/set-login": "A",
    "POST /api/employees/{employee_id}/advance": "A",
    "GET /api/employees/{employee_id}/advances": "A",
    "GET /api/employees/{employee_id}/monthly-adjustment": "A",
    "POST /api/employees/{employee_id}/monthly-adjustment": "A",
    "GET /api/finance/cash-balance": "AF",
    "POST /api/finance/cash-transaction": "A",
    "GET /api/finance/cash-transactions": "AF",
    "DELETE /api/finance/cash-transactions/{tx_id}": "A",
    "GET /api/finance/daily": "AF",
    "GET /api/finance/debt-summary": "AF",
    "POST /api/finance/expense": "AF",
    "GET /api/finance/history": "AF",
    "GET /api/finance/pul-oqimi": "AF",
    "GET /api/finance/report": "AF",
    "GET /api/finance/report-pdf": "AF",
    "GET /api/finance/split-profit-pdf": "AF",
    "GET /api/finance/transactions": "AF",
    "POST /api/finance/transactions": "AMF",
    "DELETE /api/finance/transactions/{tx_id}": "AF",
    "PUT /api/finance/transactions/{tx_id}": "AMF",
    "GET /api/finance/yonalishlar": "AF",
    "GET /api/finished": "AWM",
    "POST /api/finished/loss": "AWM",
    "DELETE /api/finished/loss/{loss_id}": "A",
    "POST /api/finished/produce": "AWM",
    "POST /api/finished/production-brak": "AWM",
    "GET /api/finished/sales": "AWM",
    "GET /api/finished/sales/batch/{group_id}/pdf": "AM",
    "GET /api/finished/sales/{sale_id}/pdf": "AM",
    "GET /api/finished/search": "AWM",
    "POST /api/finished/sell": "AWM",
    "POST /api/finished/sell-batch": "AWM",
    "GET /api/finished/stats": "AWM",
    "DELETE /api/finished/{fp_id}": "AWM",
    "PUT /api/finished/{fp_id}": "AWM",
    "POST /api/finished/{fp_id}/add": "AWM",
    "POST /api/finished/{fp_id}/complete": "AWM",
    "POST /api/finished/{fp_id}/image": "AWM",
    "GET /api/finished/{fp_id}/profit": "AF",
    "POST /api/finished/{fp_id}/reduce": "AWM",
    "POST /api/finished/{fp_id}/release-reservation": "AWM",
    "GET /api/gift-period": "AF",
    "POST /api/gift-period/add-master": "AF",
    "POST /api/gift-period/close": "AF",
    "POST /api/gift-period/open": "AF",
    "POST /api/gift-period/redeem/{master_id}/{tier_id}": "AF",
    "PUT /api/gift-period/tier/{tier_id}": "AF",
    "GET /api/health": "-",
    "POST /api/hodim/advance-request": "EMP",
    "GET /api/hodim/my-requests": "EMP",
    "GET /api/inventory": "AWM",
    "POST /api/inventory": "AW",
    "POST /api/inventory/full-stock-report": "AW",
    "GET /api/inventory/kpi": "AWM",
    "POST /api/inventory/low-stock-alert": "AW",
    "GET /api/inventory/movements": "AWM",
    "GET /api/inventory/purchase-stats": "AWM",
    "GET /api/inventory/purchase-trend": "AWM",
    "GET /api/inventory/purchases": "AWM",
    "DELETE /api/inventory/purchases/{purchase_id}": "AW",
    "PUT /api/inventory/purchases/{purchase_id}": "AW",
    "POST /api/inventory/receipt": "AW",
    "POST /api/inventory/receipts/{receipt_id}/cancel": "AW",
    "GET /api/inventory/receipts/{receipt_id}/cancel-plan": "AW",
    "DELETE /api/inventory/{item_id}": "A",
    "PUT /api/inventory/{item_id}": "AW",
    "POST /api/inventory/{item_id}/image": "AW",
    "POST /api/inventory/{item_id}/min-stock": "AW",
    "POST /api/inventory/{item_id}/price": "AW",
    "POST /api/inventory/{item_id}/purchase": "AW",
    "POST /api/inventory/{item_id}/set-default-penoplast": "AW",
    "POST /api/inventory/{item_id}/stock": "A",
    "GET /api/loy-cost": "AM",
    "GET /api/loy-stock": "AM",
    "GET /api/masters": "AM",
    "POST /api/masters": "AM",
    "GET /api/masters/kpi-report": "AF",
    "DELETE /api/masters/{master_id}": "AM",
    "PUT /api/masters/{master_id}": "AM",
    "DELETE /api/masters/{master_id}/delete": "A",
    "PUT /api/masters/{master_id}/kpi": "AF",
    "GET /api/masters/{master_id}/kpi-detail": "AF",
    "GET /api/notifications": "LOGIN",
    "POST /api/obligations/employee/{employee_id}/close": "A",
    "GET /api/obligations/employee/{employee_id}/timeline": "AM",
    "GET /api/obligations/recurring": "AF",
    "POST /api/obligations/recurring": "A",
    "DELETE /api/obligations/recurring/{obligation_id}": "A",
    "GET /api/obligations/status": "AM",
    "GET /api/obligations/timeline": "AM",
    "DELETE /api/order-items/{item_id}": "AM",
    "PUT /api/order-items/{item_id}": "AM",
    "DELETE /api/order-items/{item_id}/image": "AMU",
    "POST /api/order-items/{item_id}/image": "AMU",
    "GET /api/orders": "AM",
    "POST /api/orders": "AM",
    "DELETE /api/orders/attachments/{attachment_id}": "AMU",
    "POST /api/orders/coating-notify-new": "AM",
    "POST /api/orders/mark-all-ready": "AM",
    "GET /api/orders/pinned": "AM",
    "DELETE /api/orders/{order_id}": "AM",
    "GET /api/orders/{order_id}": "AM",
    "PUT /api/orders/{order_id}": "AM",
    "POST /api/orders/{order_id}/activate": "AM",
    "PUT /api/orders/{order_id}/agreed-amount": "AM",
    "GET /api/orders/{order_id}/attachments": "AM",
    "POST /api/orders/{order_id}/attachments": "AMU",
    "POST /api/orders/{order_id}/coating-notify": "AM",
    "GET /api/orders/{order_id}/delivery-status": "AM",
    "PUT /api/orders/{order_id}/loy": "AM",
    "GET /api/orders/{order_id}/pdf": "AM",
    "DELETE /api/orders/{order_id}/permanent": "A",
    "POST /api/orders/{order_id}/pin": "AM",
    "GET /api/orders/{order_id}/planned-loy": "AM",
    "GET /api/orders/{order_id}/profit": "A",
    "POST /api/orders/{order_id}/ready": "AM",
    "POST /api/orders/{order_id}/refund-overpayment": "AMF",
    "POST /api/orders/{order_id}/restore": "A",
    "GET /api/orders/{order_id}/summary-pdf": "AM",
    "GET /api/ortiqcha-tolovlar": "AMF",
    "GET /api/payments": "AMF",
    "POST /api/payments": "AMF",
    "DELETE /api/payments/{payment_id}": "AMF",
    "GET /api/penoplasts": "AM",
    "GET /api/platform/companies": "PLAT",
    "POST /api/platform/companies": "PLAT",
    "POST /api/platform/companies/{company_id}/block": "PLAT",
    "POST /api/platform/companies/{company_id}/extend": "PLAT",
    "POST /api/platform/companies/{company_id}/reset-admin-password": "PLAT",
    "POST /api/platform/companies/{company_id}/unblock": "PLAT",
    "POST /api/platform/contact-phone": "PLAT",
    "GET /api/platform/errors": "PLAT",
    "GET /api/platform/summary": "PLAT",
    "POST /api/production/boms": "AW",
    "POST /api/production/boms/preview": "AW",
    "DELETE /api/production/boms/{bom_id}": "AW",
    "PUT /api/production/boms/{bom_id}": "AW",
    "GET /api/production/company-settings": "A",
    "PUT /api/production/company-settings": "A",
    "GET /api/production/mrp-order-items": "AWM",
    "GET /api/production/orders": "AWM",
    "POST /api/production/orders": "AWM",
    "GET /api/production/orders/preview": "AWM",
    "POST /api/production/orders/{po_id}/cancel": "AWM",
    "POST /api/production/orders/{po_id}/complete": "AWM",
    "GET /api/production/orders/{po_id}/preview": "AWM",
    "POST /api/production/orders/{po_id}/start": "AWM",
    "GET /api/production/product-types": "AW",
    "POST /api/production/product-types": "AW",
    "GET /api/production/product-types/xulosa": "AW",
    "DELETE /api/production/product-types/{pt_id}": "AW",
    "PATCH /api/production/product-types/{pt_id}": "AW",
    "GET /api/production/product-types/{pt_id}/boms": "AW",
    "GET /api/projects": "AM",
    "POST /api/projects": "AM",
    "GET /api/projects/dashboard-stats": "AMF",
    "GET /api/projects/progress-map": "AMF",
    "DELETE /api/projects/{project_id}": "AM",
    "PUT /api/projects/{project_id}": "AM",
    "GET /api/projects/{project_id}/detail-stats": "AMF",
    "POST /api/projects/{project_id}/image": "AMF",
    "GET /api/projects/{project_id}/items": "AM",
    "POST /api/projects/{project_id}/payment": "AMF",
    "DELETE /api/projects/{project_id}/permanent": "A",
    "POST /api/projects/{project_id}/restore": "A",
    "GET /api/recipes": "AW",
    "POST /api/recipes": "AW",
    "DELETE /api/recipes/{recipe_id}": "AW",
    "PUT /api/recipes/{recipe_id}": "AW",
    "POST /api/recipes/{recipe_id}/image": "AW",
    "GET /api/reports/alerts": "AF",
    "GET /api/reports/brak-materials": "AF",
    "GET /api/reports/brak-tahlil": "AF",
    "GET /api/reports/business-health": "AF",
    "GET /api/reports/comparison": "AF",
    "GET /api/reports/forecast": "AF",
    "GET /api/reports/top-customers": "AF",
    "GET /api/reports/top-materials": "AF",
    "GET /api/reports/top-products": "AF",
    "GET /api/reports/top-suppliers": "AF",
    "GET /api/returns": "AMW",
    "POST /api/returns": "AMW",
    "GET /api/returns/stats": "AMW",
    "DELETE /api/returns/{return_id}": "AMW",
    "POST /api/returns/{return_id}/image": "AMW",
    "POST /api/returns/{return_id}/refund": "AMW",
    "GET /api/settings/categories": "A",
    "PUT /api/settings/categories": "A",
    "GET /api/settings/company": "LOGIN",
    "PUT /api/settings/company": "A",
    "POST /api/settings/company/logo": "A",
    "GET /api/settings/ehson-percent": "AF",
    "PUT /api/settings/ehson-percent": "A",
    "GET /api/settings/telegram-bot": "A",
    "PUT /api/settings/telegram-bot": "A",
    "GET /api/suppliers": "AW",
    "POST /api/suppliers": "AW",
    "GET /api/suppliers/debt-total": "AW",
    "GET /api/suppliers/due-dates": "AW",
    "DELETE /api/suppliers/payments/{payment_id}": "AW",
    "DELETE /api/suppliers/{supplier_id}": "AW",
    "PUT /api/suppliers/{supplier_id}": "AW",
    "GET /api/suppliers/{supplier_id}/history": "AW",
    "POST /api/suppliers/{supplier_id}/payment": "AW",
    "GET /api/suppliers/{supplier_id}/purchased-items": "AW",
    "GET /api/system/backup": "PLAT",
    "POST /api/system/backup/send-now": "PLAT",
    "POST /api/system/factory-reset": "PLAT",
    "GET /api/system/health-check": "A",
    "POST /api/system/restore": "PLAT",
    "GET /api/system/telegram-debug": "PLAT",
    "POST /api/system/telegram-delete-webhook": "PLAT",
    "POST /api/system/telegram-setup-webhook-security": "PLAT",
    "GET /api/transport-expenses": "AM",
    "POST /api/transport-expenses": "AM",
    "DELETE /api/transport-expenses/{exp_id}": "AM",
    "GET /api/transport-stats": "AM",
    "POST /api/users": "A",
    "POST /api/users/{user_id}/password": "A",
    "POST /api/users/{user_id}/toggle": "A",
    "GET /api/warnings/low-stock": "LOGIN",
    "GET /api/yonalishlar": "AMFWU",
    "POST /api/yonalishlar": "A",
    "DELETE /api/yonalishlar/{yonalish_id}": "A",
    "PUT /api/yonalishlar/{yonalish_id}": "A",
    "GET /dashboard": "AF",
    "GET /debts": "AF",
    "GET /finance": "AF",
    "GET /finished": "AWM",
    "GET /hodim": "-",
    "GET /hodim/login": "-",
    "POST /hodim/login": "-",
    "GET /hodim/logout": "-",
    "GET /inventory": "AWM",
    "GET /kpi": "AF",
    "GET /kunlik-xarajat": "AMF",
    "GET /login": "-",
    "POST /login": "-",
    "GET /logout": "-",
    "GET /logs": "A",
    "GET /masters": "-",
    "GET /orders": "AMU",
    "GET /platforma": "-",
    "GET /production": "AW",
    "GET /projects": "AMF",
    "GET /recipes": "AW",
    "GET /reports": "AF",
    "GET /returns": "AMW",
    "GET /static/uploads/{papka}/{fayl}": "-",
    "GET /suppliers": "AW",
    "GET /suppliers/receive": "AW",
    "POST /telegram/webhook": "-",
    "GET /tiklash": "PLAT",
    "POST /tiklash": "PLAT",
    "GET /trash": "A",
    "GET /users": "A",
    "GET /ustalar": "AM",
}
# Rollar sahifasi va API (kech118) — FAQAT Admin (topshirilmaydi)
YANGI_MARSHRUTLAR = {
    "GET /rollar": "A", "GET /api/rollar": "A", "POST /api/rollar": "A", "PUT /api/rollar/{rol_id}": "A",
    "DELETE /api/rollar/{rol_id}": "A", "POST /api/rollar/{rol_id}/andoza": "A", "PUT /api/users/{user_id}/rol": "A",
    # kech118 (D-1, G5-11): TM «Kam» chegarasi — «Tayyor mahsulotlar: Tahrirlash» (PUT /api/finished/{fp_id} bilan bir xil)
    "PUT /api/finished/{fp_id}/kam-chegara": "AWM",
    # kech118 (D-1, G6-21): hodim panelidagi «Oyligim» — faqat hodim (PIN) sessiyasi
    "GET /api/hodim/oylik": "EMP",
    # kech120 (zip 129 — G4-14): ombor harakatlari «Tanlangan davr — jami» — «Ombor harakatlari» ro'yxati bilan bir xil ruxsat
    "GET /api/inventory/movements/jami": "AWM",
}
# ATAYLAB o'zgarishlar (rol, marshrut) → yangi holat (True — ochiq). Sababi: tayyor rollar sahifa bo'yicha izchil.
FARQLAR = {
    # Moliyachi — Dashboard va Qarzdorlar sahifalari ochilardi, lekin shu sahifalarning so'rovlari 403 berardi
    ("F", "GET /api/dashboard/debts"): True, ("F", "GET /api/dashboard/deliveries"): True,
    ("F", "GET /api/transport-stats"): True, ("F", "GET /api/obligations/status"): True,
    ("F", "GET /api/obligations/timeline"): True, ("F", "GET /api/obligations/employee/{employee_id}/timeline"): True,
    # Menejer — shu 6 so'rov faqat Dashboard / Qarzdorlar sahifasida ishlatiladi, u sahifalar Menejerga yopiq (ko'rinadigan farq yo'q)
    ("M", "GET /api/dashboard/debts"): False, ("M", "GET /api/dashboard/deliveries"): False,
    ("M", "GET /api/transport-stats"): False, ("M", "GET /api/obligations/status"): False,
    ("M", "GET /api/obligations/timeline"): False, ("M", "GET /api/obligations/employee/{employee_id}/timeline"): False,
    # Omborchi — tayyor mahsulot sotadi, lekin sotuv chekini (PDF) ololmasdi
    ("W", "GET /api/finished/sales/batch/{group_id}/pdf"): True, ("W", "GET /api/finished/sales/{sale_id}/pdf"): True,
}
ROL_TURI = {"A": UserRole.ADMIN, "M": UserRole.MANAGER, "F": UserRole.ACCOUNTANT, "W": UserRole.WAREHOUSE,
            "U": UserRole.MASTER}
ESKI_QOROVUL = {"admin_or_manager", "orders_page_access", "admin_manager_accountant", "admin_or_financier",
                "admin_or_warehouse", "admin_warehouse_or_manager", "inventory_view", "order_payments", "manager_or_warehouse"}


def marshrutlar(routes):
    for r in routes:
        if isinstance(r, APIRoute):
            yield r
        elif type(r).__name__ == "_IncludedRouter":
            yield from marshrutlar(r.original_router.routes)


def qorovullar(dep, acc):
    for d in dep.dependencies:
        if getattr(d.call, "__module__", "") == "auth":
            acc.append(d.call)
        qorovullar(d, acc)
    return acc


MARSHRUT = {}          # "USUL yo'l" → (route, [qorovul])
for _r in marshrutlar(main.app.routes):
    for _m in _r.methods:
        MARSHRUT[f"{_m} {_r.path}"] = (_r, [q for q in qorovullar(_r.dependant, [])
                                          if q.__name__ not in ("get_current_user", "get_current_company_id")])


def andoza_ruxsat(harf):
    """Eski rol turi → tayyor rol ruxsatlari (Admin — None: hammasi)."""
    if harf == "A":
        return None
    return RX.ruxsatlar_oqi(RX.TAYYOR_ROLLAR[RX.ENUM_ROL[ROL_TURI[harf].value]]["ruxsatlar"])


def talab_bajariladi(q, ruxsat, turi_harf):
    """Qorovul `q` rol ruxsatlari bilan o'tadimi (Admin — ruxsat None)."""
    t = getattr(q, "ruxsat_talabi", None)
    if t is not None:
        if ruxsat is None:
            return True
        bor = [a in (ruxsat.get(b) or set()) for b, a in t[1]]
        return any(bor) if t[0] == "biri" else all(bor)
    n = q.__name__
    if n == "admin_only":
        return turi_harf == "A"
    if n in ("all_staff", "require_login"):
        return True
    if n in ("platform_admin_only", "require_employee_login"):
        return False
    raise AssertionError(f"noma'lum qorovul: {n}")


def kutilgan(kalit, harf):
    """ESKI jadval + ataylab farqlar → shu rol kirishi kerakmi (None — tekshirilmaydi)."""
    if (harf, kalit) in FARQLAR:
        return FARQLAR[(harf, kalit)]
    e = ESKI.get(kalit, YANGI_MARSHRUTLAR.get(kalit))
    if e is None or e in ("-", "EMP", "PLAT"):
        return False if e in ("EMP", "PLAT") else None
    if e == "LOGIN":
        return True
    return harf in e


# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("S. Katalog, tayyor rollar, marshrut qorovullari (statik)")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
_amal = {a for a, _ in RX.AMALLAR}
check("S1 katalog: har band kodi yagona, har bandda 1–4 amal (faqat Ko'rish / Yaratish / Tahrirlash / O'chirish)",
      len(RX.BANDLAR) == sum(len(m[3]) for m in RX.BOLIMLAR)
      and all(v["amallar"] and set(v["amallar"]) <= _amal for v in RX.BANDLAR.values()), len(RX.BANDLAR))
_yomon = [(k, b, a) for k, v in RX.TAYYOR_ROLLAR.items() for b, am in v["ruxsatlar"].items() for a in am
          if b not in RX.BANDLAR or a not in RX.BANDLAR[b]["amallar"]]
check("S2 tayyor rollar faqat katalogdagi band / amal; Admin andozasi — HAMMA ruxsat; tartib Admin, Menejer, Omborchi, Moliyachi",
      not _yomon and RX.ruxsatlar_oqi(RX.TAYYOR_ROLLAR["admin"]["ruxsatlar"]) == {b: set(v["amallar"]) for b, v in RX.BANDLAR.items()}
      and RX.TAYYOR_TARTIB == ("admin", "menejer", "omborchi", "moliyachi")
      and [RX.TAYYOR_ROLLAR[k]["nom"] for k in RX.TAYYOR_TARTIB] == ["Admin", "Menejer", "Omborchi", "Moliyachi"], _yomon)
check("S3 «Tannarx va foyda» — alohida band (faqat Ko'rish); Menejer / Omborchi da YO'Q, Moliyachi da BOR (eskisidek)",
      RX.BANDLAR["tannarx"]["amallar"] == ("korish",) and "tannarx" not in RX.TAYYOR_ROLLAR["menejer"]["ruxsatlar"]
      and "tannarx" not in RX.TAYYOR_ROLLAR["omborchi"]["ruxsatlar"] and "tannarx" in RX.TAYYOR_ROLLAR["moliyachi"]["ruxsatlar"])
_jadvalsiz = sorted(k for k in MARSHRUT if k not in ESKI and k not in YANGI_MARSHRUTLAR)
_yoq = sorted(k for k in list(ESKI) + list(YANGI_MARSHRUTLAR) if k not in MARSHRUT)
check("S4 HAR marshrut jadvalda (yangi marshrut ruxsati belgilanmay qolmagan), jadvaldagi hamma marshrut ilovada bor",
      not _jadvalsiz and not _yoq, (_jadvalsiz, _yoq))
_qsiz = sorted(k for k, (_, q) in MARSHRUT.items() if ESKI.get(k, YANGI_MARSHRUTLAR.get(k)) not in ("-", None) and len(q) != 1)
_ortiq = sorted(k for k, (_, q) in MARSHRUT.items() if ESKI.get(k) == "-" and q)
check("S5 qorovulli marshrutda AYNAN bitta qorovul, qorovulsiz («-») marshrutlarda qorovul yo'q",
      not _qsiz and not _ortiq, (_qsiz[:10], _ortiq[:10]))
_eski_q = sorted({q.__name__ for _, qs in MARSHRUT.values() for q in qs} & ESKI_QOROVUL)
check("S6 eski rol-ro'yxatli qorovullar ishlatilmaydi (auth da ham yo'q)",
      not _eski_q and not any(hasattr(auth, n) for n in ESKI_QOROVUL), _eski_q)
_farq, _ortiqcha_farq = [], []
for k, (_, qs) in sorted(MARSHRUT.items()):
    for h in "AMFWU":
        kut = kutilgan(k, h)
        if kut is None or not qs:
            continue
        haq = all(talab_bajariladi(q, andoza_ruxsat(h), h) for q in qs)
        if haq != kut:
            _farq.append((h, k, haq, kut))
for (h, k), v in FARQLAR.items():
    if h in ESKI.get(k, "") and v or (h not in ESKI.get(k, "") and not v):
        _ortiqcha_farq.append((h, k))
check("S7 ESKI rollar × HAMMA marshrut: qorovul + tayyor rol ruxsatlari = ESKI huquq (farq — faqat 14 ta ATAYLAB)",
      not _farq and not _ortiqcha_farq and len(FARQLAR) == 14, (_farq[:12], _ortiqcha_farq))
_menejer_ozg = sorted(k for (h, k) in FARQLAR if h == "M")
check("S8 Menejer — ataylab farqlari faqat YOPILGAN va hech bir Menejer sahifasi ishlatmaydigan so'rovlar (dashboard.html / debts.html)",
      all(not FARQLAR[("M", k)] for k in _menejer_ozg) and len(_menejer_ozg) == 6, _menejer_ozg)
_shablon = []
for _f in sorted(os.listdir(os.path.join(ROOT, "templates"))):
    if not _f.endswith(".html"):
        continue
    for _i, _q in enumerate(open(os.path.join(ROOT, "templates", _f), encoding="utf-8").read().splitlines(), 1):
        if re.search(r"role\.value\s*(==|!=|in)|\{%\s*set\s+role\s*=", _q) and not (_f == "base.html" and "m_admin" in _q) \
                and not (_f == "users.html" and "u.role.value == 'admin'" in _q):
            _shablon.append(f"{_f}:{_i}")
check("S9 shablonlarda rol TURI sharti qolmagan (faqat Admin belgisi — menyu «Boshqaruv», Foydalanuvchilar ro'yxati)",
      not _shablon, _shablon)
_kerak_yomon = [b for b, (k, _) in RX.SAHIFA_KERAK.items() if b not in RX.BANDLAR
                or any(kb not in RX.BANDLAR or ka not in RX.BANDLAR[kb]["amallar"] for kb, ka in k)]
check("S10 sahifa bog'liqligi (ogohlantirish) — faqat katalogdagi band / amal", not _kerak_yomon, _kerak_yomon)

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("H. HAQIQIY HTTP — eski rol turlari (migratsiya kabi tayyor rolga biriktirilgan)")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
db = SessionLocal()
with contextlib.redirect_stdout(io.StringIO()):
    if not db.query(Company).filter(Company.id == 2).first():
        db.add(Company(id=2, name="Rollar B korxona"))
        db.commit()
    for h, t in ROL_TURI.items():
        auth.create_user(db, f"rt_{h}", "Parol123!", t, f"Rol test {h}", company_id=1)
    auth.create_user(db, "rt_B_admin", "Parol123!", UserRole.ADMIN, "B admin", company_id=2)
    auth.create_user(db, "rt_B_men", "Parol123!", UserRole.MANAGER, "B menejer", company_id=2)
_u = {u.username: u for u in db.query(User).all()}
_kod = {h: (_u[f"rt_{h}"].rol.kod if _u[f"rt_{h}"].rol else None) for h in ROL_TURI}
check("H1 har yangi foydalanuvchi o'z korxonasining tayyor roliga biriktirilgan (admin / menejer / moliyachi / omborchi / usta)",
      _kod == {"A": "admin", "M": "menejer", "F": "moliyachi", "W": "omborchi", "U": "usta"}
      and all(_u[f"rt_{h}"].rol.company_id == 1 for h in ROL_TURI) and _u["rt_B_men"].rol.company_id == 2, _kod)
_rollar_A = sorted(r.kod or "" for r in db.query(Rol).filter(Rol.company_id == 1).all())
check("H2 1-korxona rollari: Admin, Menejer, Omborchi, Moliyachi + «Usta (eski)» (faqat usta foydalanuvchisi bor bo'lgani uchun)",
      _rollar_A == sorted(["admin", "menejer", "omborchi", "moliyachi", "usta"]), _rollar_A)
db.close()


def kirish(login, parol="Parol123!"):
    c = TestClient(main.app, base_url="https://testserver", raise_server_exceptions=False)
    c.post("/login", data={"username": login, "password": parol}, follow_redirects=False)
    return c


KL = {h: kirish(f"rt_{h}") for h in ROL_TURI}
XAVFLI = {"/logout", "/hodim/logout", "/login", "/hodim/login", "/telegram/webhook", "/tiklash"}
_hfarq = []
_soni = 0
for k, (r, qs) in sorted(MARSHRUT.items()):
    usul, yol = k.split(" ", 1)
    if yol in XAVFLI or yol.startswith("/api/cron") or yol.startswith("/static") or not qs:
        continue
    y = re.sub(r"\{[^}]+\}", "999999", yol)
    for h in "AMFWU":
        kut = kutilgan(k, h)
        if kut is None:
            continue
        x = KL[h].get(y, follow_redirects=False) if usul == "GET" else \
            KL[h].request(usul, y, json={"__rollar_test__": 1}, follow_redirects=False)
        _soni += 1
        if (x.status_code not in (401, 403)) != kut:
            _hfarq.append((h, k, x.status_code, kut))
check(f"H3 HTTP: hamma qorovulli marshrut × 5 eski rol ({_soni} so'rov) — rad (401 / 403) ⇔ kutilgan (ESKI ± ATAYLAB)",
      not _hfarq and _soni > 1300, _hfarq[:12])
_bosh = {h: (lambda x: (x.status_code, x.headers.get("location")))(KL[h].get("/", follow_redirects=False)) for h in "AMFWU"}
check("H4 bosh sahifa: Admin, Moliyachi — 200; Menejer, Usta → /orders; Omborchi → /inventory (eskisidek)",
      _bosh == {"A": (200, None), "F": (200, None), "M": (302, "/orders"), "U": (302, "/orders"), "W": (302, "/inventory")}, _bosh)
# kech118 (D-1, G4-19 — egasi QARORI «Taklif qilingan lug'at»): «Kirim qilish» (/suppliers/receive) yonida «Ta'minotchilar»
# (/suppliers, «Ta'minotchilar: Ko'rish» ruxsati bilan) — ATAYLAB yangi band (ro'yxat sahifasi ilgari faqat Kirim sahifasidagi
# kichik tugmadan ochilardi; ruxsat o'zgarmagan)
MENYU_KUT = {
    "A": ["/", "/dashboard", "/projects", "/orders", "/inventory", "/suppliers/receive", "/suppliers", "/recipes", "/production",
          "/finished", "/returns", "/debts", "/finance", "/kpi", "/reports", "/users", "/rollar", "/trash", "/logs"],
    "M": ["/projects", "/orders", "/inventory", "/finished", "/kunlik-xarajat", "/returns", "/ustalar"],
    "F": ["/", "/dashboard", "/projects", "/debts", "/finance", "/kpi", "/reports"],
    "W": ["/inventory", "/suppliers/receive", "/suppliers", "/recipes", "/production", "/finished", "/returns"],
    "U": ["/orders"],
}
_sah = {"A": "/finance", "M": "/orders", "F": "/finance", "W": "/inventory", "U": "/orders"}
_menyu = {}
for h in "AMFWU":
    _t = KL[h].get(_sah[h]).text
    _nav = _t[_t.find('<nav class="s-nav">'):_t.find("</nav>", _t.find('<nav class="s-nav">'))]
    _menyu[h] = re.findall(r'<a href="([^"]+)" class="nav-item', _nav)
check("H5 menyu havolalari — eski ro'yxat bilan AYNAN (Admin — yangi «Rollar va ruxsatlar»; D-1 — «Ta'minotchilar»)", _menyu == MENYU_KUT,
      {h: (sorted(set(_menyu[h]) ^ set(MENYU_KUT[h]))) for h in "AMFWU"})
_rolnom = {h: re.search(r'<div class="u-role">([^<]*)</div>', KL[h].get(_sah[h]).text) for h in "AMFWU"}
_rolnom = {h: (m.group(1).strip() if m else None) for h, m in _rolnom.items()}
check("H6 menyudagi rol nomi — o'zbekcha rol nomi (ilgari inglizcha «Manager» / «Accountant»)",
      _rolnom == {"A": "Admin", "M": "Menejer", "F": "Moliyachi", "W": "Omborchi", "U": "Usta (eski)"}, _rolnom)
_x = KL["M"].get("/api/employees")
check("H7 rad sababi — qaysi bo'lim / amal (o'zbekcha)",
      _x.status_code == 403 and js(_x).get("detail") == RX.rad_matni("hodim", "korish")
      and "Hodimlar (oylik, avans)" in js(_x).get("detail", "") and "«Ko'rish»" in js(_x).get("detail", ""), js(_x))
_x = KL["M"].get("/finance", headers={"accept": "text/html"})
check("H8 ruxsatsiz SAHIFA (brauzer) — 403 sahifa, sababi bilan (qaysi bo'lim), «Bosh sahifaga»",
      _x.status_code == 403 and "ruxsatingiz yo" in _x.text and "Moliyaviy hisobot" in _x.text and "Bosh sahifaga" in _x.text,
      (_x.status_code, _x.text[:300]))
# Sahifadagi tugmalar (eski shartlar bilan AYNAN): Omborxona — narx / «Ombor qiymati» (Admin, Omborchi), chiqim / o'chirish (Admin)
with contextlib.redirect_stdout(io.StringIO()):
    _s = SessionLocal()
    from models import Inventory as _Inv
    _s.add(_Inv(company_id=1, item_name="Rollar material", unit="kg", stock_quantity=5, price_per_unit=1000, min_stock=1))
    _s.commit()
    _s.close()
_inv = {h: KL[h].get("/inventory").text for h in "AMW"}
check("H9 Omborxona: narx tahriri va «Ombor qiymati» — Admin, Omborchi; chiqim (qoldiq tuzatish) va o'chirish — faqat Admin",
      all(('onclick="editPrice(' in _inv[h]) == (h in "AW") and ("Ombor qiymati" in _inv[h]) == (h in "AW")
          and ('onclick="openChiqimModal(' in _inv[h]) == (h == "A")
          and ('onclick="deleteItem(' in _inv[h]) == (h == "A") for h in "AMW"),
      {h: ('onclick="editPrice(' in _inv[h], "Ombor qiymati" in _inv[h], 'onclick="openChiqimModal(' in _inv[h],
           'onclick="deleteItem(' in _inv[h]) for h in "AMW"})
_ord = {h: KL[h].get("/orders").text for h in "AMU"}
check("H10 Buyurtmalar: «Moliya» (tannarx / foyda) bloki va «Foyda hisoblash» — faqat «Tannarx va foyda» ruxsatida (Admin)",
      all(('id="btn-profit"' in _ord[h]) == (h == "A") and ('id="s-cost"' in _ord[h]) == (h == "A") for h in "AMU"),
      {h: 'id="btn-profit"' in _ord[h] for h in "AMU"})

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("R. Rollar API va ruxsat qo'llanishi")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
A = KL["A"]


def rol_id(cid, kod):
    """Tayyor rol id si — bazadan (API ga bog'liq emas: mutatsiyada Admin huquqi yo'qolsa ham test oxirigacha yuradi)."""
    _ss = SessionLocal()
    try:
        _x = _ss.query(Rol).filter(Rol.company_id == cid, Rol.kod == kod).first()
        return _x.id if _x else None
    finally:
        _ss.close()


def user_id(login):
    _ss = SessionLocal()
    try:
        _x = _ss.query(User).filter(User.username == login).first()
        return _x.id if _x else None
    finally:
        _ss.close()


_r = A.get("/api/rollar")
_d = js(_r)
check("R1 GET /api/rollar (Admin): katalog (hamma bo'lim), 4 amal, rollar — tayyorlari birinchi, foydalanuvchilar",
      _r.status_code == 200 and [m["kod"] for m in _d.get("katalog", [])] == [m[0] for m in RX.BOLIMLAR]
      and [a["kod"] for a in _d.get("amallar", [])] == ["korish", "yaratish", "tahrirlash", "ochirish"]
      and [r["kod"] for r in _d.get("rollar", [])][:4] == ["admin", "menejer", "omborchi", "moliyachi"]
      and any(u["username"] == "rt_M" for u in _d.get("foydalanuvchilar", []))
      and not any(u["username"].startswith("rt_B") for u in _d.get("foydalanuvchilar", [])), (_r.status_code, str(_d)[:300]))
check("R2 rollar sahifasi / API — faqat Admin (Menejer, Moliyachi, Omborchi — 403)",
      all(KL[h].get("/api/rollar").status_code == 403 and KL[h].get("/rollar").status_code == 403 for h in "MFW")
      and A.get("/rollar").status_code == 200, [KL[h].get("/api/rollar").status_code for h in "MFW"])
_adm = next((r for r in _d.get("rollar", []) if r.get("kod") == "admin"), {"id": rol_id(1, "admin")})
_men = next((r for r in _d.get("rollar", []) if r.get("kod") == "menejer"), {"id": rol_id(1, "menejer")})
check("R3 Admin roli: hamma ruxsat, o'zgartirib / o'chirib bo'lmaydi (sahifa belgisi va server)",
      _adm.get("ruxsatlar") == {b: list(v["amallar"]) for b, v in RX.BANDLAR.items()} and _adm.get("ozgartirish_mumkin") is False
      and _adm.get("ochirish_mumkin") is False and A.put(f"/api/rollar/{_adm['id']}", json={"nom": "Boshliq"}).status_code == 400
      and A.delete(f"/api/rollar/{_adm['id']}").status_code == 400, _adm)
_bad = [
    A.post("/api/rollar", json={"nom": "  "}).status_code,
    A.post("/api/rollar", json={"nom": "x" * 61}).status_code,
    A.post("/api/rollar", json={"nom": "Yangi", "ruxsatlar": {"yoq_band": ["korish"]}}).status_code,
    A.post("/api/rollar", json={"nom": "Yangi", "ruxsatlar": {"dashboard": ["ochirish"]}}).status_code,
    A.post("/api/rollar", json={"nom": "Yangi", "boshqa": 1}).status_code,
    A.post("/api/rollar", json={"nom": "menejer"}).status_code,
    A.post("/api/rollar", json={"nom": "Yangi", "ruxsatlar": {"kassa": "korish"}}).status_code,
    A.post("/api/rollar", json=[1]).status_code,
]
check("R4 yangi rol tekshiruvi: bo'sh nom, 61 belgi, noma'lum band / amal / maydon, band nom (katta-kichik harf farqsiz) — 400",
      all(c in (400, 422) for c in _bad), _bad)
_r = A.post("/api/rollar", json={"nom": "  Sotuvchi   yordamchi ", "tavsif": "Faqat moliya ko'radi",
                                 "ruxsatlar": {"moliya": ["korish"], "kassa": ["korish", "ochirish", "korish"]}})
_sot = js(_r)
check("R5 rol yaratildi: nom tozalangan, ruxsatlar katalog tartibida (takror yo'q), jurnalga yozildi",
      _r.status_code == 200 and _sot.get("nom") == "Sotuvchi yordamchi" and _sot.get("tayyor") is False
      and _sot.get("ruxsatlar") == {"moliya": ["korish"], "kassa": ["korish", "ochirish"]}, (_r.status_code, _sot))
_s = SessionLocal()
_log = _s.query(ActivityLog).filter(ActivityLog.entity_type == "rol", ActivityLog.company_id == 1).order_by(ActivityLog.id.desc()).first()
_s.close()
check("R6 jurnal: «Rol «Sotuvchi yordamchi»» yaratildi, kim, qaysi ruxsatlar",
      _log is not None and _log.action == "created" and "Sotuvchi yordamchi" in (_log.entity_label or "")
      and _log.performed_by == "rt_A" and "Moliyaviy hisobot: Ko'rish" in (_log.new_value or ""), _log and _log.new_value)
# Menejerni shu rolga o'tkazish — DARHOL (qayta kirishsiz) ta'sir qiladi
_m_id = user_id("rt_M")
_old = (KL["M"].get("/api/finance/report").status_code, KL["M"].get("/api/orders").status_code)
_r = A.put(f"/api/users/{_m_id}/rol", json={"rol_id": _sot.get("id")})
_new = (KL["M"].get("/api/finance/report").status_code, KL["M"].get("/api/orders").status_code)
_menyu_m = re.findall(r'<a href="([^"]+)" class="nav-item', KL["M"].get("/finance").text)
check("R7 foydalanuvchi rolini almashtirish — DARHOL ta'sir (qayta kirishsiz): Moliya ochildi, Buyurtmalar yopildi, menyu yangilandi",
      _r.status_code == 200 and js(_r).get("rol_nomi") == "Sotuvchi yordamchi" and js(_r).get("role") == "manager"
      and _old[0] == 403 and _old[1] == 200 and _new[0] not in (401, 403) and _new[1] == 403 and _menyu_m == ["/finance"],
      (_r.status_code, _old, _new, _menyu_m))
check("R8 bosh sahifa — birinchi ochiq sahifaga (Moliya)", KL["M"].get("/", follow_redirects=False).headers.get("location") == "/finance",
      KL["M"].get("/", follow_redirects=False).headers)
_r = A.put(f"/api/rollar/{_sot.get('id')}", json={"ruxsatlar": {"moliya": ["korish"], "hisobot": ["korish"]}, "nom": "Sotuvchi"})
check("R9 rol tahriri: nom va ruxsatlar — darhol (Hisobotlar ochildi, Kassa yopildi); jurnalda farq (+ / −)",
      _r.status_code == 200 and KL["M"].get("/api/reports/alerts").status_code != 403
      and KL["M"].get("/api/finance/cash-balance").status_code == 403, (_r.status_code, js(_r)))
_s = SessionLocal()
_log = _s.query(ActivityLog).filter(ActivityLog.entity_type == "rol", ActivityLog.action == "updated").order_by(ActivityLog.id.desc()).first()
_s.close()
check("R10 jurnal: «+ Hisobotlar: Ko'rish», «− Kassa + bank: Ko'rish» (kech118 G3-14 nomi), nomi o'zgargani",
      _log is not None and "+ Hisobotlar: Ko'rish" in _log.new_value and "− Kassa + bank: Ko'rish" in _log.new_value
      and "«Sotuvchi yordamchi» → «Sotuvchi»" in _log.new_value, _log and _log.new_value)
check("R11 foydalanuvchisi bor rol o'chirilmaydi (400, sababi bilan); tayyor rol o'chirilmaydi",
      A.delete(f"/api/rollar/{_sot.get('id')}").status_code == 400 and A.delete(f"/api/rollar/{_men['id']}").status_code == 400
      and "foydalanuvchi bor" in js(A.delete(f"/api/rollar/{_sot.get('id')}")).get("detail", ""))
# Menejerni qaytarish
A.put(f"/api/users/{_m_id}/rol", json={"rol_id": _men["id"]})
check("R12 bo'sh o'zi yaratgan rol o'chiriladi (jurnal), keyin 404",
      A.delete(f"/api/rollar/{_sot.get('id')}").status_code == 200 and A.delete(f"/api/rollar/{_sot.get('id')}").status_code == 404)
# Tayyor rolni o'zgartirish va andozaga qaytarish
_r1 = A.put(f"/api/rollar/{_men['id']}", json={"ruxsatlar": {"buyurtma": ["korish"]}})
_ol = KL["M"].get("/api/projects").status_code
_r2 = A.post(f"/api/rollar/{_men['id']}/andoza")
check("R13 tayyor rol (Menejer) o'zgartiriladi (Loyihalar yopildi) va «Boshlang'ich holat» — andoza AYNAN tiklanadi",
      _r1.status_code == 200 and _ol == 403 and _r2.status_code == 200
      and {b: set(a) for b, a in js(_r2).get("ruxsatlar", {}).items()} == RX.ruxsatlar_oqi(RX.TAYYOR_ROLLAR["menejer"]["ruxsatlar"])
      and KL["M"].get("/api/projects").status_code == 200, (_r1.status_code, _ol, _r2.status_code))
check("R14 andozaga qaytarish — faqat tayyor rol (Admin roli / o'zi yaratgan — 400)",
      A.post(f"/api/rollar/{_adm['id']}/andoza").status_code == 400)
# Biriktirish qoidalari
_a_id = user_id("rt_A")
_r = A.put(f"/api/users/{_a_id}/rol", json={"rol_id": _men["id"]})
check("R15 o'z rolini o'zgartirib bo'lmaydi (400)", _r.status_code == 400 and "O'z rolingizni" in js(_r).get("detail", ""), js(_r))
_s = SessionLocal()
_b_rol = _s.query(Rol).filter(Rol.company_id == 2, Rol.kod == "admin").first()   # B da doim bor (admin yaratilganda)
_b_men = _s.query(User).filter(User.username == "rt_B_men").first()
_s.close()
check("R16 boshqa korxonaning roli — 400; boshqa korxonaning foydalanuvchisi — 404",
      A.put(f"/api/users/{_m_id}/rol", json={"rol_id": _b_rol.id}).status_code == 400
      and A.put(f"/api/users/{_b_men.id}/rol", json={"rol_id": _men["id"]}).status_code == 404
      and A.put(f"/api/rollar/{_b_rol.id}", json={"nom": "X"}).status_code == 404)
check("R17 tana QAT'IY: rol_id yo'q / matn / true — 400",
      all(A.put(f"/api/users/{_m_id}/rol", json=b).status_code == 400 for b in ({}, {"rol_id": "2"}, {"rol_id": True},
                                                                               {"rol_id": 2, "x": 1})))
# oxirgi faol Admin: B korxonada yagona admin (rt_B_admin) — B korxonaning ikkinchi adminini yaratib, birinchisini tushirish
KB = kirish("rt_B_admin")
_bd = js(KB.get("/api/rollar"))
_b_admin_rol = {"id": rol_id(2, "admin")}
_b_men_rol = {"id": rol_id(2, "menejer")}
_r = KB.post("/api/users", json={"username": "rt_B_admin2", "password": "Parol123!", "rol_id": _b_admin_rol["id"]})
_b2 = js(_r).get("id")
check("R18 yangi foydalanuvchi Admin roli bilan — `role` = admin (Admin belgisi roldan)",
      _r.status_code == 200 and js(_r).get("role") == "admin" and js(_r).get("rol_nomi") == "Admin", js(_r))
KB2 = kirish("rt_B_admin2")
_r1 = KB2.put(f"/api/users/{user_id('rt_B_admin')}/rol", json={"rol_id": _b_men_rol["id"]})
_r2 = kirish("rt_B_admin").get("/api/rollar").status_code
check("R19 ikkinchi Admin bor — birinchi Admin Menejer qilinadi (endi rollar sahifasi 403)", _r1.status_code == 200 and _r2 == 403,
      (_r1.status_code, js(_r1), _r2))
_s = SessionLocal()
_b_adm1 = _s.query(User).filter(User.username == "rt_B_admin").first()
_s.close()
_r1 = KB2.put(f"/api/users/{_b_adm1.id}/rol", json={"rol_id": _b_admin_rol["id"]})
KB1 = kirish("rt_B_admin")
_r3 = KB1.put(f"/api/users/{_b2}/rol", json={"rol_id": _b_men_rol["id"]})
_r4 = KB2.get("/api/rollar").status_code
# endi rt_B_admin — yagona Admin; o'zini tushira olmaydi (o'z roli), boshqa hech kim Admin emas
_r5 = KB1.put(f"/api/users/{_b_adm1.id}/rol", json={"rol_id": _b_men_rol["id"]})
check("R20 Admin qaytarildi; ikkinchi Admin tushirildi (403); yagona Admin — o'zini tushira olmaydi",
      _r1.status_code == 200 and _r3.status_code == 200 and _r4 == 403 and _r5.status_code == 400, (_r1.status_code, _r3.status_code, _r4, _r5.status_code))
# oxirgi faol admin qoidasi (to'g'ridan-to'g'ri): B da yagona faol Admin — boshqa Admin uni tushira olmaydi (boshqa Admin yo'q)
_s = SessionLocal()
try:
    auth.rol_biriktir(_s, _b_adm1.id, _b_men_rol["id"], 2, None)
    _xato = None
except HTTPException as e:
    _xato = e.detail
_s.rollback()
_s.close()
check("R21 korxonada kamida bitta FAOL Admin qoladi (oxirgi Admin tushirilmaydi)",
      _xato == "Korxonada kamida bitta faol Admin qolishi kerak", _xato)
check("R22 B korxona admini faqat o'z rollarini ko'radi (A ning o'zi yaratgan rollari yo'q), A rolini tahrirlay olmaydi (404)",
      bool(_bd.get("rollar")) and all(r.get("id") != _men["id"] for r in _bd.get("rollar", [])) and KB1.put(f"/api/rollar/{_men['id']}", json={"nom": "X"}).status_code == 404)
_r = A.post("/api/users", json={"username": "rt_yangi", "password": "Parol123!", "rol_id": _b_rol.id})
_r2 = A.post("/api/users", json={"username": "rt_yangi", "password": "Parol123!", "rol_id": _men["id"], "full_name": "Yangi"})
check("R23 foydalanuvchi yaratish: boshqa korxona roli — 400; o'z roli — 200 (role = manager, rol — Menejer)",
      _r.status_code == 400 and _r2.status_code == 200 and js(_r2).get("rol_nomi") == "Menejer" and js(_r2).get("role") == "manager",
      (_r.status_code, js(_r2)))
# Birorta bo'limi yo'q rol
_bo = js(A.post("/api/rollar", json={"nom": "Bo'sh rol"}))
_y_id = js(_r2).get("id")
A.put(f"/api/users/{_y_id}/rol", json={"rol_id": _bo.get("id")})
KY = kirish("rt_yangi")
_x = KY.get("/", headers={"accept": "text/html"}, follow_redirects=False)
check("R24 birorta bo'limi yo'q rol — bosh sahifa 403 (sababi: «hali birorta bo'lim berilmagan»), menyu bo'sh",
      _x.status_code == 403 and "birorta bo" in _x.text and not re.findall(r'class="nav-item', _x.text), (_x.status_code, _x.text[:200]))

# Har (band, amal) juftligi — yakka ruxsatli rol: qorovullar faqat shu juftni talab qiluvchi marshrutlarni o'tkazadi
_yakka_farq = []
_s = SessionLocal()
_yu = _s.query(User).filter(User.username == "rt_yangi").first()
_tok = auth.create_session(_s, _yu.id) if _yu is not None else "yoq"
_s.close()
_sorov = Request({"type": "http", "method": "GET", "path": "/", "headers": [(b"cookie", f"session_token={_tok}".encode())],
                  "query_string": b""})
_juftlar = [(b, a) for b, v in RX.BANDLAR.items() for a in v["amallar"]]
if _yu is None or not _bo.get("id"):
    _yakka_farq.append(("sozlanmadi", _yu is None, _bo))
    _juftlar_yur = []
else:
    _juftlar_yur = _juftlar
for jb, ja in _juftlar_yur:
    _s = SessionLocal()
    _s.query(Rol).filter(Rol.id == _bo.get("id")).update({"ruxsatlar": json.dumps({jb: [ja]})})
    _s.commit()
    _s.close()
    for k, (r, qs) in MARSHRUT.items():
        for q in qs:
            _s = SessionLocal()
            try:
                q(_sorov, _s)
                haq = True
            except HTTPException:
                haq = False
            finally:
                _s.close()
            kut = talab_bajariladi(q, {jb: {ja}}, "M")
            if haq != kut:
                _yakka_farq.append((jb, ja, k, haq, kut))
check(f"R25 HAR juft ({len(_juftlar)} ta) uchun yakka ruxsatli rol × hamma marshrut qorovuli — faqat shu juftni talab qiluvchilar ochiq",
      not _yakka_farq and len(_juftlar) == sum(len(v["amallar"]) for v in RX.BANDLAR.values()), _yakka_farq[:10])
_s = SessionLocal()
_s.query(Rol).filter(Rol.id == _bo.get("id")).update({"ruxsatlar": json.dumps({"tannarx": ["korish"]})})
_s.commit()
_s.close()
_t1 = KY.get("/api/orders/999999/profit").status_code
_s = SessionLocal()
_s.query(Rol).filter(Rol.id == _bo.get("id")).update({"ruxsatlar": json.dumps({"tannarx": ["korish"], "buyurtma": ["korish"]})})
_s.commit()
_s.close()
_t2 = KY.get("/api/orders/999999/profit").status_code
check("R26 buyurtma foydasi — «Tannarx va foyda» VA «Buyurtmalar: Ko'rish» ikkalasi kerak (bittasi — 403)",
      _t1 == 403 and _t2 == 404, (_t1, _t2))
_t = KY.get("/orders").text
check("R27 tannarx + buyurtma ko'rish: Buyurtmalar sahifasida «Moliya» bloki va «Foyda hisoblash» ko'rinadi",
      'id="btn-profit"' in _t and 'id="s-cost"' in _t)
_up = A.get("/users").text
check("R28 Foydalanuvchilar sahifasi: rol tanlovi — korxona rollari (o'zidan boshqasiga), «Rollar va huquqlar» — «Sozlash →»",
      'class="u-rol-tanlov"' in _up and "Sotuvchi" not in _up and "Bo&#39;sh rol" in _up and 'href="/rollar"' in _up
      and "rt_B" not in _up, re.findall(r'<select class="u-rol-tanlov".{0,200}', _up)[:1])

_s = SessionLocal()
_adm_rol = _s.query(Rol).filter(Rol.company_id == 1, Rol.kod == "admin").first()
_adm_eski = _adm_rol.ruxsatlar
_adm_rol.ruxsatlar = "{}"
_s.commit()
_s.close()
_a_kirish = (A.get("/api/finance/cash-balance").status_code, A.get("/api/employees").status_code,
             A.get("/finance").status_code)
_s = SessionLocal()
_s.query(Rol).filter(Rol.company_id == 1, Rol.kod == "admin").update({"ruxsatlar": _adm_eski})
_s.commit()
_s.close()
check("R29 Admin — ruxsati tekshirilmaydi: Admin roli yozuvi bazada bo'sh bo'lsa ham hamma bo'lim ochiq (katalogga yangi band "
      "qo'shilsa ham Admin to'liq qoladi)", _a_kirish == (200, 200, 200), _a_kirish)

# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
section("M. Migratsiya va zaxira qoida")
# ════════════════════════════════════════════════════════════════════════════════════════════════════════════
with contextlib.redirect_stdout(io.StringIO()):
    _s = SessionLocal()
    for n, t in (("rt_mig_w", UserRole.WAREHOUSE), ("rt_mig_f", UserRole.ACCOUNTANT), ("rt_mig_u", UserRole.MASTER)):
        auth.create_user(_s, n, "Parol123!", t, n, company_id=2)
    _s.query(User).filter(User.username.in_(["rt_mig_w", "rt_mig_f", "rt_mig_u", "rt_B_men"])).update({"rol_id": None},
                                                                                                      synchronize_session=False)
    _s.query(Rol).filter(Rol.company_id == 2, Rol.kod.in_(["usta", "omborchi"])).delete(synchronize_session=False)
    _s.commit()
    _s.close()
_s = SessionLocal()
_fu = _s.query(User).filter(User.username == "rt_mig_f").first()
_zaxira = (RX.bormi(_fu, "moliya", "korish"), RX.bormi(_fu, "buyurtma", "korish"))
_s.close()
check("M1 rol biriktirilmagan foydalanuvchi — eski turining tayyor andozasi (Moliyachi: Moliya bor, Buyurtmalar yo'q)",
      _zaxira == (True, False), _zaxira)
_ol = kirish("rt_mig_w").get("/api/suppliers").status_code
_s = SessionLocal()
_biriktirilgan = {u.username: u.rol_id for u in _s.query(User).filter(User.rol_id.isnot(None)).all()}
_s.close()
with contextlib.redirect_stdout(io.StringIO()):
    main._migrate_rollar()
_s = SessionLocal()
_keyin = {u.username: u.rol_id for u in _s.query(User).filter(User.username.in_(list(_biriktirilgan))).all()}
_s.close()
check("M6 migratsiya roli BOR foydalanuvchiga tegmaydi (admin bergan rol — masalan «Bo'sh rol» — saqlanadi)",
      _keyin == _biriktirilgan and _biriktirilgan.get("rt_yangi") == _bo.get("id"),
      {k: (v, _keyin.get(k)) for k, v in _biriktirilgan.items() if _keyin.get(k) != v})
_s = SessionLocal()
_mig = {u.username: (u.rol.kod if u.rol else None, u.rol.company_id if u.rol else None)
        for u in _s.query(User).filter(User.username.in_(["rt_mig_w", "rt_mig_f", "rt_mig_u", "rt_B_men"])).all()}
_rs = sorted(r.kod or "" for r in _s.query(Rol).filter(Rol.company_id == 2).all())
_soni1 = (_s.query(Rol).count(), [u.rol_id for u in _s.query(User).order_by(User.id).all()])
_s.close()
check("M2 migratsiya: rol_id bo'shlar — o'z korxonasining tayyor roliga (omborchi qayta yaratildi; master — «Usta (eski)»)",
      _mig == {"rt_mig_w": ("omborchi", 2), "rt_mig_f": ("moliyachi", 2), "rt_mig_u": ("usta", 2), "rt_B_men": ("menejer", 2)}
      and "usta" in _rs and "omborchi" in _rs, (_mig, _rs))
check("M3 migratsiyadan oldin ham, keyin ham Omborchi Ta'minotchilar ro'yxatiga kiradi (huquq yo'qolmaydi)",
      _ol == 200 and kirish("rt_mig_w").get("/api/suppliers").status_code == 200, _ol)
with contextlib.redirect_stdout(io.StringIO()):
    main._migrate_rollar()
_s = SessionLocal()
_soni2 = (_s.query(Rol).count(), [u.rol_id for u in _s.query(User).order_by(User.id).all()])
# boshqa korxonaning roli — zaxira qoida (o'sha rol ruxsati EMAS)
_w = _s.query(User).filter(User.username == "rt_mig_w").first()
_a_rol = _s.query(Rol).filter(Rol.company_id == 1, Rol.kod == "moliyachi").first()
_w.rol_id = _a_rol.id
_s.commit()
_s.close()
check("M4 migratsiya takror ishga tushsa — hech narsa o'zgarmaydi (idempotent)", _soni1 == _soni2, (_soni1[0], _soni2[0]))
_kw = kirish("rt_mig_w")
check("M5 boshqa korxonaning roliga ishora — o'sha rol ruxsati QO'LLANMAYDI (eski tur andozasi: Omborchi)",
      _kw.get("/api/finance/report").status_code == 403 and _kw.get("/api/suppliers").status_code == 200)

print(f"\nNATIJA:  o'tdi = {OK}   yiqildi = {FAIL}   jami = {OK + FAIL}")
if FAILED:
    print("YIQILGANLAR:")
    for f in FAILED:
        print("  -", f)
sys.exit(1 if FAIL else 0)
