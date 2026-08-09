from datetime import datetime
from modules.accounting import Accounting


def _accounts(db):
    return Accounting(db)


def create_sale(db,user_id,items,discount,tax_rate,payment,paid,order_type='Takeaway',customer_id=None):
    if not items: raise ValueError('Order is empty.')
    for i in items:
        p=db.conn.execute('SELECT stock,cost,active FROM products WHERE id=?',(i['product_id'],)).fetchone()
        if not p or not p['active']: raise ValueError(f"Product unavailable: {i['name']}")
        if float(i['qty']) <= 0: raise ValueError('Quantity must be positive.')
        if float(p['stock']) + 1e-9 < float(i['qty']): raise ValueError(f"Insufficient stock: {i['name']}")
    subtotal=sum(float(i['qty'])*float(i['price']) for i in items); discount=max(0,min(float(discount),subtotal)); tax=(subtotal-discount)*float(tax_rate)/100; total=subtotal-discount+tax
    paid=total if payment!='Cash' and not paid else float(paid)
    if paid+1e-9<total: raise ValueError('Paid amount is less than total.')
    bid=db.current_business_day(); bid=bid['id'] if bid else db.open_business_day(0); now=datetime.now(); order_no='ORD-'+now.strftime('%Y%m%d%H%M%S%f')[:20]
    try:
        cur=db.conn.cursor(); cur.execute('BEGIN')
        cur.execute('INSERT INTO orders(order_no,created_at,user_id,customer_id,order_type,status,subtotal,discount,tax,total,payment_method,paid,change_amount,business_day_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(order_no,now.isoformat(timespec='seconds'),user_id,customer_id,order_type,'Completed',subtotal,discount,tax,total,payment,paid,max(0,paid-total),bid)); oid=cur.lastrowid
        cogs=0
        for i in items:
            amount=float(i['qty'])*float(i['price']); cost=float(i['cost']); cogs += float(i['qty'])*cost
            cur.execute('INSERT INTO order_items(order_id,product_id,item_name,qty,price,cost,amount) VALUES(?,?,?,?,?,?,?)',(oid,i['product_id'],i['name'],i['qty'],i['price'],cost,amount)); cur.execute('UPDATE products SET stock=stock-? WHERE id=?',(i['qty'],i['product_id'])); cur.execute('INSERT INTO stock_movements(product_id,movement_type,qty,note,created_at,business_day_id) VALUES(?,?,?,?,?,?)',(i['product_id'],'SALE',-i['qty'],order_no,now.isoformat(timespec='seconds'),bid))
        if payment=='Cash': cur.execute('INSERT INTO cash_transactions(created_at,type,amount,note,reference,user_id,business_day_id,payment_method) VALUES(?,?,?,?,?,?,?,?)',(now.isoformat(timespec='seconds'),'SALE',total,'POS sale',order_no,user_id,bid,payment))
        if customer_id:
            cur.execute('INSERT INTO customer_transactions(customer_id,created_at,type,reference,debit,credit,note,business_day_id) VALUES(?,?,?,?,?,?,?,?)',(customer_id,now.isoformat(timespec='seconds'),'SALE',order_no,total,paid,'POS sale',bid)); cur.execute('UPDATE customers SET points=points+? WHERE id=?',(int(total//100),customer_id))
        _accounts(db).sale(order_no,total,cogs,payment,customer_id,tax,discount,bid,user_id)
        db.audit(user_id,'CREATE','sale',oid,order_no); db.conn.commit()
    except Exception:
        db.conn.rollback(); raise
    return oid,order_no,subtotal,discount,tax,total,max(0,paid-total)


def create_purchase(db,user_id,supplier_id,items,paid,payment):
    if not items: raise ValueError('Purchase is empty.')
    total=sum(float(i['qty'])*float(i['cost']) for i in items); paid=float(paid)
    if paid < 0 or paid > total: raise ValueError('Invalid paid amount.')
    due=max(0,total-paid); bid=db.current_business_day(); bid=bid['id'] if bid else db.open_business_day(0); now=datetime.now(); no='PUR-'+now.strftime('%Y%m%d%H%M%S%f')[:20]
    try:
        cur=db.conn.cursor(); cur.execute('BEGIN'); cur.execute('INSERT INTO purchases(purchase_no,created_at,supplier_id,total,paid,due,payment_method,business_day_id) VALUES(?,?,?,?,?,?,?,?)',(no,now.isoformat(timespec='seconds'),supplier_id,total,paid,due,payment,bid)); pid=cur.lastrowid
        for i in items:
            amt=float(i['qty'])*float(i['cost']); cur.execute('INSERT INTO purchase_items(purchase_id,product_id,item_name,qty,cost,amount) VALUES(?,?,?,?,?,?)',(pid,i['product_id'],i['name'],i['qty'],i['cost'],amt)); cur.execute('UPDATE products SET stock=stock+?,cost=? WHERE id=?',(i['qty'],i['cost'],i['product_id'])); cur.execute('INSERT INTO stock_movements(product_id,movement_type,qty,note,created_at,business_day_id) VALUES(?,?,?,?,?,?)',(i['product_id'],'PURCHASE',i['qty'],no,now.isoformat(timespec='seconds'),bid))
        if payment=='Cash' and paid: cur.execute('INSERT INTO cash_transactions(created_at,type,amount,note,reference,user_id,business_day_id,payment_method) VALUES(?,?,?,?,?,?,?,?)',(now.isoformat(timespec='seconds'),'PURCHASE',-paid,'Supplier purchase',no,user_id,bid,payment))
        if supplier_id: cur.execute('INSERT INTO supplier_transactions(supplier_id,created_at,type,reference,debit,credit,note,business_day_id) VALUES(?,?,?,?,?,?,?,?)',(supplier_id,now.isoformat(timespec='seconds'),'PURCHASE',no,total,paid,'Purchase invoice',bid))
        _accounts(db).purchase(no,total,paid,payment,bid,user_id); db.audit(user_id,'CREATE','purchase',pid,no); db.conn.commit()
    except Exception:
        db.conn.rollback(); raise
    return pid,no,total,due
