from datetime import datetime
from modules.accounting import Accounting


def _business_day(db):
    row = db.current_business_day()
    return row["id"] if row else db.open_business_day(0)


def create_sale(db, user_id, items, discount, tax_rate, payment, paid, order_type="Takeaway", customer_id=None):
    if not items:
        raise ValueError("Order is empty.")
    if payment == "Credit" and not customer_id:
        raise ValueError("A customer is required for credit sales.")
    for item in items:
        p = db.conn.execute("SELECT stock,cost,active FROM products WHERE id=?", (item["product_id"],)).fetchone()
        if not p or not p["active"]:
            raise ValueError(f"Product unavailable: {item['name']}")
        if float(item["qty"]) <= 0:
            raise ValueError("Quantity must be positive.")
        if float(p["stock"]) + 1e-9 < float(item["qty"]):
            raise ValueError(f"Insufficient stock: {item['name']}")

    subtotal = round(sum(float(i["qty"]) * float(i["price"]) for i in items), 2)
    discount = max(0, min(float(discount), subtotal))
    tax = round((subtotal - discount) * float(tax_rate) / 100, 2)
    total = round(subtotal - discount + tax, 2)
    paid = float(paid)
    if payment == "Credit":
        if paid < 0 or paid > total:
            raise ValueError("Invalid credit payment amount.")
    elif paid + 1e-9 < total:
        raise ValueError("Paid amount is less than total.")

    bid = _business_day(db)
    now = datetime.now()
    order_no = "ORD-" + now.strftime("%Y%m%d%H%M%S%f")[:20]
    try:
        cur = db.conn.cursor()
        cur.execute("BEGIN")
        cur.execute("""INSERT INTO orders(order_no,created_at,user_id,customer_id,order_type,status,subtotal,discount,tax,total,payment_method,paid,change_amount,business_day_id)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (order_no, now.isoformat(timespec="seconds"), user_id, customer_id, order_type, "Completed", subtotal, discount, tax, total, payment, paid, max(0, paid-total), bid))
        oid = cur.lastrowid
        cogs = 0
        for item in items:
            amount = round(float(item["qty"]) * float(item["price"]), 2)
            cost = float(item["cost"])
            cogs += float(item["qty"]) * cost
            cur.execute("INSERT INTO order_items(order_id,product_id,item_name,qty,price,cost,amount) VALUES(?,?,?,?,?,?,?)",
                        (oid, item["product_id"], item["name"], item["qty"], item["price"], cost, amount))
            cur.execute("UPDATE products SET stock=stock-? WHERE id=?", (item["qty"], item["product_id"]))
            cur.execute("INSERT INTO stock_movements(product_id,movement_type,qty,note,created_at,business_day_id) VALUES(?,?,?,?,?,?)",
                        (item["product_id"], "SALE", -item["qty"], order_no, now.isoformat(timespec="seconds"), bid))

        if payment == "Cash" and paid:
            cur.execute("INSERT INTO cash_transactions(created_at,type,amount,note,reference,user_id,business_day_id,payment_method) VALUES(?,?,?,?,?,?,?,?)",
                        (now.isoformat(timespec="seconds"), "SALE", total, "POS sale", order_no, user_id, bid, payment))
        if customer_id:
            cur.execute("INSERT INTO customer_transactions(customer_id,created_at,type,reference,debit,credit,note,business_day_id) VALUES(?,?,?,?,?,?,?,?)",
                        (customer_id, now.isoformat(timespec="seconds"), "SALE", order_no, total, paid, "POS sale", bid))
            cur.execute("UPDATE customers SET points=points+? WHERE id=?", (int(total // 100), customer_id))

        Accounting(db).sale(order_no, total, cogs, payment, customer_id, tax, discount, bid, user_id)
        db.audit(user_id, "CREATE", "sale", oid, order_no)
        db.conn.commit()
    except Exception:
        db.conn.rollback()
        raise
    return oid, order_no, subtotal, discount, tax, total, max(0, paid-total)


def create_purchase(db, user_id, supplier_id, items, paid, payment):
    if not items:
        raise ValueError("Purchase is empty.")
    if not supplier_id:
        raise ValueError("Supplier is required.")
    total = round(sum(float(i["qty"]) * float(i["cost"]) for i in items), 2)
    paid = float(paid)
    if paid < 0 or paid > total:
        raise ValueError("Invalid paid amount.")
    due = round(total-paid, 2)
    bid = _business_day(db)
    now = datetime.now()
    no = "PUR-" + now.strftime("%Y%m%d%H%M%S%f")[:20]
    try:
        cur = db.conn.cursor(); cur.execute("BEGIN")
        cur.execute("INSERT INTO purchases(purchase_no,created_at,supplier_id,total,paid,due,payment_method,business_day_id) VALUES(?,?,?,?,?,?,?,?)",
                    (no, now.isoformat(timespec="seconds"), supplier_id, total, paid, due, payment, bid))
        pid = cur.lastrowid
        for item in items:
            amount = float(item["qty"]) * float(item["cost"])
            cur.execute("INSERT INTO purchase_items(purchase_id,product_id,item_name,qty,cost,amount) VALUES(?,?,?,?,?,?)",
                        (pid, item["product_id"], item["name"], item["qty"], item["cost"], amount))
            cur.execute("UPDATE products SET stock=stock+?,cost=? WHERE id=?", (item["qty"], item["cost"], item["product_id"]))
            cur.execute("INSERT INTO stock_movements(product_id,movement_type,qty,note,created_at,business_day_id) VALUES(?,?,?,?,?,?)",
                        (item["product_id"], "PURCHASE", item["qty"], no, now.isoformat(timespec="seconds"), bid))
        if payment == "Cash" and paid:
            cur.execute("INSERT INTO cash_transactions(created_at,type,amount,note,reference,user_id,business_day_id,payment_method) VALUES(?,?,?,?,?,?,?,?)",
                        (now.isoformat(timespec="seconds"), "PURCHASE", -paid, "Supplier purchase", no, user_id, bid, payment))
        cur.execute("INSERT INTO supplier_transactions(supplier_id,created_at,type,reference,debit,credit,note,business_day_id) VALUES(?,?,?,?,?,?,?,?)",
                    (supplier_id, now.isoformat(timespec="seconds"), "PURCHASE", no, total, paid, "Purchase invoice", bid))
        Accounting(db).purchase(no, total, paid, payment, bid, user_id)
        db.audit(user_id, "CREATE", "purchase", pid, no)
        db.conn.commit()
    except Exception:
        db.conn.rollback(); raise
    return pid, no, total, due


def customer_payment(db, user_id, customer_id, amount, payment="Cash", note="Customer payment"):
    amount = float(amount)
    if amount <= 0: raise ValueError("Payment must be greater than zero.")
    bid = _business_day(db); now = datetime.now(); ref = "CP-" + now.strftime("%Y%m%d%H%M%S%f")
    cur = db.conn.cursor(); cur.execute("BEGIN")
    try:
        balance = db.conn.execute("SELECT opening_balance + COALESCE((SELECT SUM(debit-credit) FROM customer_transactions WHERE customer_id=c.id),0) balance FROM customers c WHERE c.id=?", (customer_id,)).fetchone()
        if not balance: raise ValueError("Customer not found.")
        if amount > float(balance["balance"]) + 0.01: raise ValueError("Payment exceeds customer due.")
        cur.execute("INSERT INTO customer_transactions(customer_id,created_at,type,reference,debit,credit,note,business_day_id) VALUES(?,?,?,?,?,?,?,?)", (customer_id, now.isoformat(timespec="seconds"), "PAYMENT", ref, 0, amount, note, bid))
        if payment == "Cash":
            cur.execute("INSERT INTO cash_transactions(created_at,type,amount,note,reference,user_id,business_day_id,payment_method) VALUES(?,?,?,?,?,?,?,?)", (now.isoformat(timespec="seconds"), "CUSTOMER_PAYMENT", amount, note, ref, user_id, bid, payment))
        Accounting(db).customer_payment(ref, amount, payment, bid, user_id)
        db.audit(user_id, "PAYMENT", "customer", customer_id, ref); db.conn.commit(); return ref
    except Exception:
        db.conn.rollback(); raise


def supplier_payment(db, user_id, supplier_id, amount, payment="Cash", note="Supplier payment"):
    amount = float(amount)
    if amount <= 0: raise ValueError("Payment must be greater than zero.")
    bid = _business_day(db); now = datetime.now(); ref = "SP-" + now.strftime("%Y%m%d%H%M%S%f")
    cur = db.conn.cursor(); cur.execute("BEGIN")
    try:
        balance = db.conn.execute("SELECT opening_balance + COALESCE((SELECT SUM(debit-credit) FROM supplier_transactions WHERE supplier_id=s.id),0) balance FROM suppliers s WHERE s.id=?", (supplier_id,)).fetchone()
        if not balance: raise ValueError("Supplier not found.")
        if amount > float(balance["balance"]) + 0.01: raise ValueError("Payment exceeds supplier due.")
        cur.execute("INSERT INTO supplier_transactions(supplier_id,created_at,type,reference,debit,credit,note,business_day_id) VALUES(?,?,?,?,?,?,?,?)", (supplier_id, now.isoformat(timespec="seconds"), "PAYMENT", ref, amount, 0, note, bid))
        if payment == "Cash":
            cur.execute("INSERT INTO cash_transactions(created_at,type,amount,note,reference,user_id,business_day_id,payment_method) VALUES(?,?,?,?,?,?,?,?)", (now.isoformat(timespec="seconds"), "SUPPLIER_PAYMENT", -amount, note, ref, user_id, bid, payment))
        Accounting(db).supplier_payment(ref, amount, payment, bid, user_id)
        db.audit(user_id, "PAYMENT", "supplier", supplier_id, ref); db.conn.commit(); return ref
    except Exception:
        db.conn.rollback(); raise
