from datetime import datetime

def create_sale(db,user_id,items,discount,tax_rate,payment,paid,order_type='Takeaway',customer_id=None):
    subtotal=sum(i['qty']*i['price'] for i in items); discount=max(0,min(float(discount),subtotal)); tax=(subtotal-discount)*float(tax_rate)/100; total=subtotal-discount+tax
    paid=total if payment!='Cash' and not paid else float(paid)
    if paid+1e-9<total: raise ValueError('Paid amount is less than total.')
    bid=db.current_business_day(); bid=bid['id'] if bid else db.open_business_day(0)
    now=datetime.now(); order_no='ORD-'+now.strftime('%Y%m%d%H%M%S%f')[:20]
    cur=db.conn.cursor(); cur.execute('INSERT INTO orders(order_no,created_at,user_id,customer_id,order_type,status,subtotal,discount,tax,total,payment_method,paid,change_amount,business_day_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(order_no,now.isoformat(timespec='seconds'),user_id,customer_id,order_type,'Completed',subtotal,discount,tax,total,payment,paid,max(0,paid-total),bid)); oid=cur.lastrowid
    for i in items:
        amount=i['qty']*i['price']; cur.execute('INSERT INTO order_items(order_id,product_id,item_name,qty,price,cost,amount) VALUES(?,?,?,?,?,?,?)',(oid,i['product_id'],i['name'],i['qty'],i['price'],i['cost'],amount)); cur.execute('UPDATE products SET stock=stock-? WHERE id=?',(i['qty'],i['product_id'])); cur.execute('INSERT INTO stock_movements(product_id,movement_type,qty,note,created_at,business_day_id) VALUES(?,?,?,?,?,?)',(i['product_id'],'SALE',-i['qty'],order_no,now.isoformat(timespec='seconds'),bid))
    if payment=='Cash': db.cash(total,'SALE','POS sale',user_id,order_no,bid)
    if customer_id:
        db.conn.execute('INSERT INTO customer_transactions(customer_id,created_at,type,reference,debit,credit,note,business_day_id) VALUES(?,?,?,?,?,?,?,?)',(customer_id,now.isoformat(timespec='seconds'),'SALE',order_no,total,paid,'POS sale',bid))
        db.conn.execute('UPDATE customers SET points=points+? WHERE id=?',(int(total//100),customer_id))
    db.conn.commit(); return oid,order_no,subtotal,discount,tax,total,max(0,paid-total)

def create_purchase(db,user_id,supplier_id,items,paid,payment):
    total=sum(i['qty']*i['cost'] for i in items); paid=float(paid); due=max(0,total-paid); bid=db.current_business_day(); bid=bid['id'] if bid else db.open_business_day(0); now=datetime.now(); no='PUR-'+now.strftime('%Y%m%d%H%M%S%f')[:20]
    cur=db.conn.cursor(); cur.execute('INSERT INTO purchases(purchase_no,created_at,supplier_id,total,paid,due,payment_method,business_day_id) VALUES(?,?,?,?,?,?,?,?)',(no,now.isoformat(timespec='seconds'),supplier_id,total,paid,due,payment,bid)); pid=cur.lastrowid
    for i in items:
        amt=i['qty']*i['cost']; cur.execute('INSERT INTO purchase_items(purchase_id,product_id,item_name,qty,cost,amount) VALUES(?,?,?,?,?,?)',(pid,i['product_id'],i['name'],i['qty'],i['cost'],amt)); cur.execute('UPDATE products SET stock=stock+?,cost=? WHERE id=?',(i['qty'],i['cost'],i['product_id'])); cur.execute('INSERT INTO stock_movements(product_id,movement_type,qty,note,created_at,business_day_id) VALUES(?,?,?,?,?,?)',(i['product_id'],'PURCHASE',i['qty'],no,now.isoformat(timespec='seconds'),bid))
    if payment=='Cash' and paid: db.cash(-paid,'PURCHASE','Supplier purchase',user_id,no,bid)
    if supplier_id: db.conn.execute('INSERT INTO supplier_transactions(supplier_id,created_at,type,reference,debit,credit,note,business_day_id) VALUES(?,?,?,?,?,?,?,?)',(supplier_id,now.isoformat(timespec='seconds'),'PURCHASE',no,total,paid,'Purchase invoice',bid))
    db.conn.commit(); return pid,no,total,due
