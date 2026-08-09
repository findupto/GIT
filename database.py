import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH=Path(__file__).with_name('fastfood_pos.db')

class Database:
    def __init__(self,path=DB_PATH):
        self.conn=sqlite3.connect(path); self.conn.row_factory=sqlite3.Row; self.conn.execute('PRAGMA foreign_keys=ON'); self.setup()
    def setup(self):
        self.conn.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE,password TEXT NOT NULL,role TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,category_id INTEGER REFERENCES categories(id),name TEXT NOT NULL,sku TEXT UNIQUE NOT NULL,price REAL DEFAULT 0,cost REAL DEFAULT 0,stock REAL DEFAULT 0,reorder_level REAL DEFAULT 5,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,phone TEXT UNIQUE,email TEXT,points INTEGER DEFAULT 0,opening_balance REAL DEFAULT 0,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS suppliers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,phone TEXT UNIQUE,email TEXT,opening_balance REAL DEFAULT 0,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,order_no TEXT UNIQUE,created_at TEXT,user_id INTEGER,customer_id INTEGER,order_type TEXT,status TEXT DEFAULT 'Completed',subtotal REAL,discount REAL,tax REAL,total REAL,payment_method TEXT,paid REAL,change_amount REAL,business_day_id INTEGER);
        CREATE TABLE IF NOT EXISTS order_items(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,product_id INTEGER,item_name TEXT,qty REAL,price REAL,cost REAL,amount REAL);
        CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY AUTOINCREMENT,purchase_no TEXT UNIQUE,created_at TEXT,supplier_id INTEGER,total REAL,paid REAL,due REAL,payment_method TEXT,business_day_id INTEGER,status TEXT DEFAULT 'Completed');
        CREATE TABLE IF NOT EXISTS purchase_items(id INTEGER PRIMARY KEY AUTOINCREMENT,purchase_id INTEGER REFERENCES purchases(id) ON DELETE CASCADE,product_id INTEGER,item_name TEXT,qty REAL,cost REAL,amount REAL);
        CREATE TABLE IF NOT EXISTS customer_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,customer_id INTEGER,created_at TEXT,type TEXT,reference TEXT,debit REAL DEFAULT 0,credit REAL DEFAULT 0,note TEXT,business_day_id INTEGER);
        CREATE TABLE IF NOT EXISTS supplier_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,supplier_id INTEGER,created_at TEXT,type TEXT,reference TEXT,debit REAL DEFAULT 0,credit REAL DEFAULT 0,note TEXT,business_day_id INTEGER);
        CREATE TABLE IF NOT EXISTS cash_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT,type TEXT,amount REAL,note TEXT,reference TEXT,user_id INTEGER,business_day_id INTEGER,payment_method TEXT DEFAULT 'Cash');
        CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT,category TEXT,description TEXT,amount REAL,payment_method TEXT,business_day_id INTEGER,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS stock_movements(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,movement_type TEXT,qty REAL,note TEXT,created_at TEXT,business_day_id INTEGER);
        CREATE TABLE IF NOT EXISTS price_history(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,old_price REAL,new_price REAL,changed_at TEXT,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS business_days(id INTEGER PRIMARY KEY AUTOINCREMENT,business_date TEXT UNIQUE,opened_at TEXT,closed_at TEXT,opening_cash REAL DEFAULT 0,closing_cash REAL,expected_cash REAL,variance REAL,status TEXT DEFAULT 'Open',note TEXT);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit_logs(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT,user_id INTEGER,action TEXT,entity TEXT,entity_id INTEGER,details TEXT);
        ''')
        self.conn.execute("INSERT OR IGNORE INTO users(username,password,role) VALUES('admin','0099','Admin')")
        self.conn.execute("INSERT OR IGNORE INTO users(username,password,role) VALUES('owner','0099','Owner')")
        self.conn.execute("UPDATE users SET password='0099',role='Admin',active=1 WHERE username='admin'")
        self.conn.execute("UPDATE users SET password='0099',role='Owner',active=1 WHERE username='owner'")
        for n in ('Burgers','Pizza','Sides','Drinks','Desserts'): self.conn.execute('INSERT OR IGNORE INTO categories(name) VALUES(?)',(n,))
        defaults={'store_name':'MK Pizza & Ice Bar','store_address':'Collage Road Abbas Chowk, Bhakkar, Pakistan','store_phone':'0316 9700025','tax_rate':'0','currency':'Rs.','printer_bluetooth_mac':'','printer_name':'','printer_port':'','printer_channel':'1','business_day_start':'06:00','business_day_end':'05:59','receipt_footer':'Thank you for visiting MK Pizza & Ice Bar!'}
        for k,v in defaults.items(): self.conn.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(k,v))
        if self.conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]==0:
            for cat,name,sku,price,cost,stock in [('Burgers','Classic Burger','BUR-001',350,180,50),('Burgers','Chicken Burger','BUR-002',450,240,50),('Pizza','Chicken Pizza','PIZ-001',900,500,30),('Pizza','Cheese Pizza','PIZ-002',800,420,30),('Sides','French Fries','SID-001',250,100,80),('Sides','Chicken Nuggets','SID-002',400,220,60),('Drinks','Soft Drink','DRK-001',120,60,100),('Drinks','Mineral Water','DRK-002',80,30,100),('Desserts','Ice Cream','DES-001',200,80,40)]:
                cid=self.conn.execute('SELECT id FROM categories WHERE name=?',(cat,)).fetchone()['id']; self.conn.execute('INSERT INTO products(category_id,name,sku,price,cost,stock) VALUES(?,?,?,?,?,?)',(cid,name,sku,price,cost,stock))
        self.conn.commit()
    def close(self): self.conn.close()
    def settings(self): return {r['key']:r['value'] for r in self.conn.execute('SELECT key,value FROM settings')}
    def save_settings(self,values):
        for k,v in values.items(): self.conn.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,str(v)))
        self.conn.commit()
    def login(self,u,p): return self.conn.execute('SELECT * FROM users WHERE username=? AND password=? AND active=1',(u,p)).fetchone()
    def categories(self): return self.conn.execute('SELECT * FROM categories WHERE active=1 ORDER BY name').fetchall()
    def products(self,search='',category_id=None):
        sql='SELECT p.*,c.name category FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.active=1'; a=[]
        if search: sql+=' AND (p.name LIKE ? OR p.sku LIKE ?)'; a += [f'%{search}%',f'%{search}%']
        if category_id: sql+=' AND p.category_id=?'; a.append(category_id)
        return self.conn.execute(sql+' ORDER BY c.name,p.name',a).fetchall()
    def save_product(self,pid,category_id,name,sku,price,cost,stock,reorder,user_id=None):
        old=self.conn.execute('SELECT price FROM products WHERE id=?',(pid,)).fetchone() if pid else None
        if pid:self.conn.execute('UPDATE products SET category_id=?,name=?,sku=?,price=?,cost=?,stock=?,reorder_level=?,active=1 WHERE id=?',(category_id,name,sku,price,cost,stock,reorder,pid))
        else:self.conn.execute('INSERT INTO products(category_id,name,sku,price,cost,stock,reorder_level) VALUES(?,?,?,?,?,?,?)',(category_id,name,sku,price,cost,stock,reorder)); pid=self.conn.execute('SELECT id FROM products WHERE sku=?',(sku,)).fetchone()['id']
        if old and float(old['price'])!=float(price): self.conn.execute('INSERT INTO price_history(product_id,old_price,new_price,changed_at,user_id) VALUES(?,?,?,?,?)',(pid,old['price'],price,datetime.now().isoformat(timespec='seconds'),user_id))
        self.conn.commit()
    def delete_product(self,pid,hard=False):
        if hard:self.conn.execute('DELETE FROM products WHERE id=?',(pid,))
        else:self.conn.execute('UPDATE products SET active=0 WHERE id=?',(pid,))
        self.conn.commit()
    def delete_all_products(self): self.conn.execute('UPDATE products SET active=0'); self.conn.commit()
    def adjust_stock(self,pid,qty,note='Adjustment',business_day_id=None):
        self.conn.execute('UPDATE products SET stock=stock+? WHERE id=?',(qty,pid)); self.conn.execute('INSERT INTO stock_movements(product_id,movement_type,qty,note,created_at,business_day_id) VALUES(?,?,?,?,?,?)',(pid,'ADJUSTMENT',qty,note,datetime.now().isoformat(timespec='seconds'),business_day_id)); self.conn.commit()
    def customers(self,search=''): return self.conn.execute('SELECT * FROM customers WHERE name LIKE ? OR COALESCE(phone,\'\') LIKE ? ORDER BY name',(f'%{search}%',f'%{search}%')).fetchall()
    def save_customer(self,name,phone,email,opening=0):
        self.conn.execute('INSERT INTO customers(name,phone,email,opening_balance,created_at) VALUES(?,?,?,?,?)',(name,phone or None,email,opening,datetime.now().isoformat(timespec='seconds'))); self.conn.commit()
    def suppliers(self,search=''): return self.conn.execute('SELECT * FROM suppliers WHERE name LIKE ? OR COALESCE(phone,\'\') LIKE ? ORDER BY name',(f'%{search}%',f'%{search}%')).fetchall()
    def save_supplier(self,name,phone,email,opening=0): self.conn.execute('INSERT INTO suppliers(name,phone,email,opening_balance,created_at) VALUES(?,?,?,?,?)',(name,phone or None,email,opening,datetime.now().isoformat(timespec='seconds'))); self.conn.commit()
    def open_business_day(self,opening_cash):
        d=self.business_date(); row=self.conn.execute('SELECT * FROM business_days WHERE business_date=?',(d,)).fetchone()
        if row and row['status']=='Open': return row['id']
        if row and row['status']=='Closed': raise ValueError('Business day already closed.')
        cur=self.conn.execute('INSERT INTO business_days(business_date,opened_at,opening_cash,status) VALUES(?,?,?,\'Open\')',(d,datetime.now().isoformat(timespec='seconds'),float(opening_cash))); self.conn.commit(); return cur.lastrowid
    def business_date(self,now=None):
        now=now or datetime.now(); start=self.settings().get('business_day_start','06:00'); h,m=map(int,start.split(':')); boundary=now.replace(hour=h,minute=m,second=0,microsecond=0); return (now-timedelta(days=1)).strftime('%Y-%m-%d') if now<boundary else now.strftime('%Y-%m-%d')
    def current_business_day(self): return self.conn.execute('SELECT * FROM business_days WHERE business_date=?',(self.business_date(),)).fetchone()
    def cash(self,amount,typ,note='',user_id=None,ref='',business_day_id=None): self.conn.execute('INSERT INTO cash_transactions(created_at,type,amount,note,reference,user_id,business_day_id) VALUES(?,?,?,?,?,?,?)',(datetime.now().isoformat(timespec='seconds'),typ,float(amount),note,ref,user_id,business_day_id or (self.current_business_day()['id'] if self.current_business_day() else None))); self.conn.commit()
    def close_business_day(self,actual_cash,note=''):
        b=self.current_business_day()
        if not b: raise ValueError('Open a business day first.')
        expected=b['opening_cash']+self.conn.execute("SELECT COALESCE(SUM(amount),0) x FROM cash_transactions WHERE business_day_id=?",(b['id'],)).fetchone()['x']
        variance=float(actual_cash)-expected; self.conn.execute("UPDATE business_days SET closed_at=?,closing_cash=?,expected_cash=?,variance=?,status='Closed',note=? WHERE id=?",(datetime.now().isoformat(timespec='seconds'),actual_cash,expected,variance,note,b['id'])); self.conn.commit(); return expected,variance
    def cash_flow(self,bid=None): return self.conn.execute('SELECT * FROM cash_transactions WHERE business_day_id=? ORDER BY id',(bid or (self.current_business_day()['id'] if self.current_business_day() else -1),)).fetchall()
    def add_expense(self,category,description,amount,payment,user_id=None,bid=None): self.conn.execute('INSERT INTO expenses(created_at,category,description,amount,payment_method,business_day_id,user_id) VALUES(?,?,?,?,?,?,?)',(datetime.now().isoformat(timespec='seconds'),category,description,float(amount),payment,bid or (self.current_business_day()['id'] if self.current_business_day() else None),user_id)); self.conn.commit();
    def product_history(self,pid): return self.conn.execute('SELECT created_at,movement_type,qty,note FROM stock_movements WHERE product_id=? ORDER BY id DESC',(pid,)).fetchall()
    def customer_history(self,cid): return self.conn.execute('SELECT * FROM customer_transactions WHERE customer_id=? ORDER BY id DESC',(cid,)).fetchall()
    def supplier_history(self,sid): return self.conn.execute('SELECT * FROM supplier_transactions WHERE supplier_id=? ORDER BY id DESC',(sid,)).fetchall()
    def sales(self,df='',dt='',user_id=None,payment=None,customer_id=None):
        sql='SELECT o.*,u.username,cu.name customer FROM orders o LEFT JOIN users u ON u.id=o.user_id LEFT JOIN customers cu ON cu.id=o.customer_id WHERE 1=1'; a=[]
        if df:sql+=' AND date(o.created_at)>=?';a.append(df)
        if dt:sql+=' AND date(o.created_at)<=?';a.append(dt)
        if user_id:sql+=' AND o.user_id=?';a.append(user_id)
        if payment:sql+=' AND o.payment_method=?';a.append(payment)
        if customer_id:sql+=' AND o.customer_id=?';a.append(customer_id)
        return self.conn.execute(sql+' ORDER BY o.id DESC LIMIT 1000',a).fetchall()
    def order_items(self,oid): return self.conn.execute('SELECT * FROM order_items WHERE order_id=?',(oid,)).fetchall()
    def report(self,df,dt):
        s=self.conn.execute('SELECT COUNT(*) orders,COALESCE(SUM(total),0) sales,COALESCE(SUM(discount),0) discounts,COALESCE(SUM(tax),0) tax FROM orders WHERE date(created_at) BETWEEN ? AND ?',(df,dt)).fetchone()
        c=self.conn.execute('SELECT COALESCE(SUM(qty*cost),0) cost FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE date(o.created_at) BETWEEN ? AND ?',(df,dt)).fetchone()['cost']
        e=self.conn.execute('SELECT COALESCE(SUM(amount),0) expenses FROM expenses WHERE date(created_at) BETWEEN ? AND ?',(df,dt)).fetchone()['expenses']; gross=s['sales']-c; net=gross-e; return s,c,e,gross,net
