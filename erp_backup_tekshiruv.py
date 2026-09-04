#!/usr/bin/env python3
"""
PenoDecorPro ERP — Backup faylini tekshiruvchi skript
========================================================
Ishlatish:
    python3 erp_backup_tekshiruv.py backup.json

Bu skript ERP'dan olingan JSON backup faylini o'qib, quyidagilarni
avtomatik tekshiradi va topilgan muammolarni ro'yxat qilib chiqaradi:

  1. Buyurtma tarkibi (order_items) yig'indisi total_amount'ga mosligi
  2. Chegirma foizi (discount_percent) hisob-kitobga mosligi
  3. To'lovlar (payments) buyurtma summasidan oshib ketmasligi va
     payment_status maydoni haqiqiy holatga mosligi
  4. Loyihadagi total_paid maydoni shu loyihaga tegishli buyurtmalar
     bo'yicha to'lovlar yig'indisiga mosligi
  5. Loyiha raqamlash naqshi (PRJ-<id>) ketma-ketligi
  6. Ombordagi stock_quantity qiymati kirim/chiqim harakatlari
     (inventory_movements) bilan hisoblab chiqilgan qoldiqqa mosligi
  7. Retseptlar (recipes) — ingredientlar yig'indisi batch_size_kg'ga
     yaqinligi
  8. Yetkazib berish (delivery) sanasi buyurtma yaratilgan/yakunlangan
     sanadan oldin bo'lib qolmaganligi, va to'lovsiz yetkazib
     berilgan buyurtmalar
  9. Bog'lanish (Foreign key) xatoliklari — masalan order_items'da
     mavjud bo'lmagan order_id'ga ishora qilish
  10. Login tarixida bitta foydalanuvchi/telefon uchun ketma-ket
      ko'p muvaffaqiyatsiz kirish urinishlari

Natijada har bir toifadagi topilgan muammolar ro'yxati va oxirida
umumiy statistika chiqariladi. Muammo topilmasa "muammo yo'q" deb
yoziladi.
"""

import json
import sys
from collections import defaultdict
from datetime import datetime

TOLERANCE = 1.0  # so'mda ruxsat etilgan yumaloqlash farqi
PCT_TOLERANCE = 0.05  # foizda ruxsat etilgan farq
QTY_TOLERANCE = 0.01  # ombor miqdorlarida ruxsat etilgan farq


def load_backup(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("tables", data)


def parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def fmt(n):
    try:
        return f"{n:,.2f}".replace(",", " ")
    except (TypeError, ValueError):
        return str(n)


class Report:
    def __init__(self):
        self.sections = {}

    def add(self, section, message):
        self.sections.setdefault(section, []).append(message)

    def total_issues(self):
        return sum(len(v) for v in self.sections.values())

    def print_all(self):
        titles = {
            "order_totals": "1) Buyurtma summalari (order_items vs total_amount)",
            "discounts": "2) Chegirma foizi (discount_percent)",
            "payments": "3) To'lovlar va payment_status",
            "project_paid": "4) Loyiha total_paid maydoni",
            "project_numbering": "5) Loyiha raqamlash naqshi (PRJ-<id>)",
            "inventory_balance": "6) Ombor qoldig'i (stock_quantity)",
            "recipes": "7) Retsept ingredientlari yig'indisi",
            "delivery_timing": "8) Yetkazib berish sanasi va to'lov holati",
            "fk_errors": "9) Bog'lanish (foreign key) xatoliklari",
            "login_attempts": "10) Login urinishlari",
        }
        print("=" * 60)
        print("PENODECORPRO ERP — BACKUP TEKSHIRUV HISOBOTI")
        print("=" * 60)
        for key, title in titles.items():
            print(f"\n{title}")
            print("-" * len(title))
            msgs = self.sections.get(key, [])
            if not msgs:
                print("  ✅ Muammo topilmadi")
            else:
                for m in msgs:
                    print(f"  ⚠️  {m}")
        print("\n" + "=" * 60)
        total = self.total_issues()
        if total == 0:
            print("NATIJA: Jiddiy xatolik topilmadi. ✅")
        else:
            print(f"NATIJA: Jami {total} ta e'tibor talab qiladigan nuqta topildi.")
        print("=" * 60)


def check_order_totals(tables, rep):
    order_items = tables.get("order_items", [])
    by_order = defaultdict(float)
    for oi in order_items:
        by_order[oi["order_id"]] += oi.get("total_price") or 0.0

    for o in tables.get("orders", []):
        oid = o["id"]
        items_sum = by_order.get(oid, 0.0)
        total = o.get("total_amount") or 0.0
        if abs(items_sum - total) > TOLERANCE:
            rep.add(
                "order_totals",
                f"{o.get('order_number', oid)}: order_items yig'indisi "
                f"{fmt(items_sum)} so'm, lekin total_amount={fmt(total)} so'm "
                f"(farq {fmt(items_sum - total)})",
            )


def check_discounts(tables, rep):
    for o in tables.get("orders", []):
        total = o.get("total_amount") or 0.0
        agreed = o.get("agreed_amount")
        stored_pct = o.get("discount_percent")
        if not total or agreed is None or stored_pct is None:
            continue
        implied_pct = (total - agreed) / total * 100
        if abs(implied_pct - stored_pct) > PCT_TOLERANCE:
            rep.add(
                "discounts",
                f"{o.get('order_number', o['id'])}: saqlangan discount_percent="
                f"{stored_pct}%, lekin total/agreed summalardan hisoblansa "
                f"{implied_pct:.2f}% chiqadi",
            )
        if agreed > total + TOLERANCE:
            rep.add(
                "discounts",
                f"{o.get('order_number', o['id'])}: agreed_amount ({fmt(agreed)}) "
                f"total_amount'dan ({fmt(total)}) katta — chegirma manfiy",
            )


def check_payments(tables, rep):
    orders = {o["id"]: o for o in tables.get("orders", [])}
    paid_by_order = defaultdict(float)
    for p in tables.get("payments", []):
        paid_by_order[p["order_id"]] += p.get("amount") or 0.0

    for oid, o in orders.items():
        agreed = o.get("agreed_amount") or 0.0
        paid = paid_by_order.get(oid, 0.0)
        status = o.get("payment_status")
        order_no = o.get("order_number", oid)

        if paid > agreed + TOLERANCE:
            rep.add(
                "payments",
                f"{order_no}: to'langan summa ({fmt(paid)}) kelishilgan "
                f"summadan ({fmt(agreed)}) ko'p",
            )

        if status == "unpaid" and paid > TOLERANCE:
            rep.add(
                "payments",
                f"{order_no}: payment_status='unpaid', lekin {fmt(paid)} so'm "
                f"to'lov qayd etilgan",
            )
        elif status == "paid" and abs(paid - agreed) > TOLERANCE:
            rep.add(
                "payments",
                f"{order_no}: payment_status='paid', lekin to'langan "
                f"({fmt(paid)}) kelishilgan summaga ({fmt(agreed)}) teng emas",
            )
        elif status == "partial" and (paid <= TOLERANCE or paid >= agreed - TOLERANCE):
            rep.add(
                "payments",
                f"{order_no}: payment_status='partial', lekin to'langan summa "
                f"({fmt(paid)}) 0 yoki to'liq summaga ({fmt(agreed)}) teng",
            )


def check_project_paid(tables, rep):
    orders = tables.get("orders", [])
    payments = tables.get("payments", [])
    order_to_project = {o["id"]: o.get("project_id") for o in orders}

    paid_by_project = defaultdict(float)
    for p in payments:
        proj_id = order_to_project.get(p["order_id"])
        if proj_id is not None:
            paid_by_project[proj_id] += p.get("amount") or 0.0

    for proj in tables.get("projects", []):
        pid = proj["id"]
        recorded = proj.get("total_paid") or 0.0
        computed = paid_by_project.get(pid, 0.0)
        if abs(recorded - computed) > TOLERANCE:
            rep.add(
                "project_paid",
                f"{proj.get('project_number', pid)} ({proj.get('client_name')}): "
                f"total_paid={fmt(recorded)}, lekin buyurtmalar bo'yicha "
                f"to'lovlar yig'indisi {fmt(computed)}",
            )


def check_project_numbering(tables, rep):
    for proj in tables.get("projects", []):
        pid = proj["id"]
        expected = f"PRJ-{pid:03d}"
        actual = proj.get("project_number")
        if actual != expected:
            rep.add(
                "project_numbering",
                f"id={pid} ({proj.get('client_name')}): project_number="
                f"'{actual}', kutilgan naqsh bo'yicha '{expected}' bo'lishi kerak edi",
            )


def check_inventory_balance(tables, rep):
    movements = tables.get("inventory_movements", [])
    by_item = defaultdict(float)
    for m in movements:
        qty = m.get("quantity") or 0.0
        if m.get("movement_type") == "in":
            by_item[m["inventory_id"]] += qty
        elif m.get("movement_type") == "out":
            by_item[m["inventory_id"]] -= qty
        else:
            rep.add(
                "inventory_balance",
                f"inventory_id={m['inventory_id']}: noma'lum movement_type="
                f"'{m.get('movement_type')}' (id={m.get('id')})",
            )

    inv_by_id = {i["id"]: i for i in tables.get("inventory", [])}
    for inv_id, computed in by_item.items():
        inv = inv_by_id.get(inv_id)
        if inv is None:
            rep.add(
                "fk_errors",
                f"inventory_movements mavjud bo'lmagan inventory_id={inv_id}'ga ishora qiladi",
            )
            continue
        actual = inv.get("stock_quantity") or 0.0
        # Harakatlar odatda "opening stock"ni ham "in" sifatida o'z ichiga oladi,
        # shuning uchun computed == actual bo'lishi kutiladi.
        if abs(computed - actual) > QTY_TOLERANCE:
            rep.add(
                "inventory_balance",
                f"{inv.get('item_name')} (id={inv_id}): harakatlardan hisoblangan "
                f"qoldiq {computed:.3f} {inv.get('unit')}, lekin stock_quantity="
                f"{actual:.3f} {inv.get('unit')} (farq {computed - actual:.3f})",
            )


def check_recipes(tables, rep):
    ingredients_by_recipe = defaultdict(float)
    for ri in tables.get("recipe_ingredients", []):
        ingredients_by_recipe[ri["recipe_id"]] += ri.get("quantity_kg") or 0.0

    for r in tables.get("recipes", []):
        rid = r["id"]
        batch = r.get("batch_size_kg") or 0.0
        ing_sum = ingredients_by_recipe.get(rid, 0.0)
        if batch and abs(ing_sum - batch) / batch > 0.02:  # 2% dan katta farq
            rep.add(
                "recipes",
                f"Retsept '{r.get('name')}' (id={rid}): ingredientlar yig'indisi "
                f"{ing_sum:.3f} kg, batch_size_kg={batch:.3f} kg "
                f"(farq {ing_sum - batch:.3f} kg, {abs(ing_sum - batch) / batch * 100:.1f}%)",
            )


def check_delivery_timing(tables, rep):
    orders = {o["id"]: o for o in tables.get("orders", [])}
    paid_by_order = defaultdict(float)
    for p in tables.get("payments", []):
        paid_by_order[p["order_id"]] += p.get("amount") or 0.0

    for d in tables.get("deliveries", []):
        o = orders.get(d.get("order_id"))
        if o is None:
            rep.add(
                "fk_errors",
                f"deliveries id={d['id']}: mavjud bo'lmagan order_id={d.get('order_id')}",
            )
            continue
        order_no = o.get("order_number", o["id"])
        delivered_at = parse_dt(d.get("delivered_at"))
        completed_at = parse_dt(o.get("completed_at"))
        created_at = parse_dt(o.get("created_at"))

        if delivered_at and completed_at and delivered_at < completed_at:
            rep.add(
                "delivery_timing",
                f"{order_no}: yetkazib berilgan sana ({delivered_at}) buyurtma "
                f"yakunlangan sanadan ({completed_at}) OLDIN — ketma-ketlik shubhali",
            )
        if delivered_at and created_at:
            gap = (delivered_at - created_at).total_seconds()
            if 0 <= gap < 300:
                rep.add(
                    "delivery_timing",
                    f"{order_no}: buyurtma yaratilgandan atigi {gap:.0f} soniya "
                    f"o'tib yetkazib berilgan — tayyorlanish vaqti tekshirilsin",
                )

        paid = paid_by_order.get(o["id"], 0.0)
        if paid <= TOLERANCE:
            rep.add(
                "delivery_timing",
                f"{order_no}: mahsulot yetkazib berilgan, lekin hech qanday "
                f"to'lov qayd etilmagan (paid={fmt(paid)})",
            )


def check_fk_integrity(tables, rep):
    order_ids = {o["id"] for o in tables.get("orders", [])}
    project_ids = {p["id"] for p in tables.get("projects", [])}
    order_item_ids = {oi["id"] for oi in tables.get("order_items", [])}
    inventory_ids = {i["id"] for i in tables.get("inventory", [])}
    recipe_ids = {r["id"] for r in tables.get("recipes", [])}

    for o in tables.get("orders", []):
        if o.get("project_id") is not None and o["project_id"] not in project_ids:
            rep.add(
                "fk_errors",
                f"{o.get('order_number', o['id'])}: mavjud bo'lmagan "
                f"project_id={o['project_id']}'ga ishora qiladi",
            )

    for oi in tables.get("order_items", []):
        if oi.get("order_id") not in order_ids:
            rep.add(
                "fk_errors",
                f"order_items id={oi['id']}: mavjud bo'lmagan "
                f"order_id={oi.get('order_id')}'ga ishora qiladi",
            )
        pid = oi.get("penoplast_id")
        if pid is not None and pid not in inventory_ids:
            rep.add(
                "fk_errors",
                f"order_items id={oi['id']}: mavjud bo'lmagan "
                f"penoplast_id={pid}'ga ishora qiladi",
            )
        rid = oi.get("recipe_id")
        if rid is not None and rid not in recipe_ids:
            rep.add(
                "fk_errors",
                f"order_items id={oi['id']}: mavjud bo'lmagan "
                f"recipe_id={rid}'ga ishora qiladi",
            )

    for di in tables.get("delivery_items", []):
        if di.get("order_item_id") not in order_item_ids:
            rep.add(
                "fk_errors",
                f"delivery_items id={di['id']}: mavjud bo'lmagan "
                f"order_item_id={di.get('order_item_id')}'ga ishora qiladi",
            )

    for p in tables.get("payments", []):
        if p.get("order_id") not in order_ids:
            rep.add(
                "fk_errors",
                f"payments id={p['id']}: mavjud bo'lmagan "
                f"order_id={p.get('order_id')}'ga ishora qiladi",
            )

    for ri in tables.get("recipe_ingredients", []):
        if ri.get("inventory_id") not in inventory_ids:
            rep.add(
                "fk_errors",
                f"recipe_ingredients id={ri['id']}: mavjud bo'lmagan "
                f"inventory_id={ri.get('inventory_id')}'ga ishora qiladi",
            )


def check_login_attempts(tables, rep):
    history = tables.get("login_history", [])
    # created_at bo'yicha tartiblash
    history_sorted = sorted(history, key=lambda r: r.get("created_at") or "")
    streak_user = None
    streak_count = 0
    for r in history_sorted:
        user = (r.get("username") or "").strip()
        success = r.get("success")
        if success is False:
            if user == streak_user:
                streak_count += 1
            else:
                streak_user = user
                streak_count = 1
            if streak_count == 3:
                rep.add(
                    "login_attempts",
                    f"'{user}' uchun ketma-ket kamida 3 ta muvaffaqiyatsiz "
                    f"kirish urinishi qayd etilgan",
                )
        else:
            streak_user = None
            streak_count = 0

    # Bo'sh joy/formatlash muammosi bo'lishi mumkin bo'lgan username'lar
    seen_trimmed = defaultdict(set)
    for r in history:
        raw = r.get("username") or ""
        seen_trimmed[raw.strip()].add(raw)
    for trimmed, variants in seen_trimmed.items():
        if len(variants) > 1:
            rep.add(
                "login_attempts",
                f"'{trimmed}' username bir nechta xil yozilishda uchramoqda: "
                f"{sorted(variants)} — forma bo'sh joyni tozalamasligi mumkin",
            )


def main():
    if len(sys.argv) < 2:
        print("Ishlatish: python3 erp_backup_tekshiruv.py <backup.json>")
        sys.exit(1)

    path = sys.argv[1]
    tables = load_backup(path)
    rep = Report()

    check_order_totals(tables, rep)
    check_discounts(tables, rep)
    check_payments(tables, rep)
    check_project_paid(tables, rep)
    check_project_numbering(tables, rep)
    check_inventory_balance(tables, rep)
    check_recipes(tables, rep)
    check_delivery_timing(tables, rep)
    check_fk_integrity(tables, rep)
    check_login_attempts(tables, rep)

    rep.print_all()
    sys.exit(1 if rep.total_issues() > 0 else 0)


if __name__ == "__main__":
    main()
