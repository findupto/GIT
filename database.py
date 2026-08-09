import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).with_name('fastfood_pos.db')

class Database:
    def __init__(self, path=DB_PATH):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.setup()

    def setup(self):
        self.conn.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'cashier',active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,category_id INTEGER NOT NULL REFERENCES categories(id),name TEXT NOT NULL,sku TEXT UNIQUE NOT NULL,price REAL NOT NULL DEFAULT 0,cost REAL NOT NULL DEFAULT 0,stock REAL NOT NULL DEFAULT 0,reorder_level REAL NOT NULL DEFAULT 5,active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,phone TEXT UNIQUE,email TEXT,points INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,order_no TEXT UNIQUE NOT NULL,created_at TEXT NOT NULL,user_id INTEGER REFERENCES users(id),customer_id INTEGER REFERENCES customers(id),order_type TEXT NOT NULL DEFAULT 'Takeaway',status TEXT NOT NULL DEFAULT 'Completed',subtotal REAL NOT NULL,discount REAL NOT NULL DEFAULT 0,tax REAL NOT NULL DEFAULT 0,total REAL NOT NULL,payment_method TEXT NOT NULL,paid REAL NOT NULL DEFAULT 0,change_amount REAL NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS order_items(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,product_id INTEGER REFERENCES products(id),item_name TEXT NOT NULL,qty REAL NOT NULL,price REAL NOT NULL,cost REAL NOT NULL DEFAULT 0,amount REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS stock_movements(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER NOT NULL REFERENCES products(id),movement_type TEXT NOT NULL,qty REAL NOT NULL,note TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        ''')
        self.conn.execute("INSERT OR IGNORE INTO users(username,password,role) VALUES('admin','admin123','admin')")
        self.conn.execute("INSERT OR IGNORE INTO users(username,password,role) VALUES('cashier','cashier123','cashier')")
        for name in ('Burgers','Pizza','Sides','Drinks','Desserts'):
            self.conn.execute('INSERT OR IGNORE INTO categories(name) VALUES(?)',(name,))
        defaults={'store_name':'FASTFOOD POS','store_address':'Main Street, Pakistan','store_phone':'0300-0000000','tax_rate':'5','currency':'Rs','receipt_footer':'Thank you for your visit!'}
        for k,v in defaults.items(): self.conn.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(k,v))
        if self.conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]==0:
            seeds=[('Burgers','Classic Burger','BUR-001',350,180,50),('Burgers','Chicken Burger','BUR-002',450,240,50),('Pizza','Chicken Pizza','PIZ-001',900,500,30),('Pizza','Cheese Pizza','PIZ-002',800,420,30),('Sides','French Fries','SID-001',250,100,80),('Sides','Chicken Nuggets','SID-002',400,220,60),('Drinks','Soft Drink','DRK-001',120,60,100),('Drinks','Mineral Water','DRK-002',80,30,100),('Desserts','Ice Cream','DES-001',200,80,40)]
            for cat,name,sku,price,cost,stock in seeds:
                cid=self.conn.execute('SELECT id FROM categories WHERE name=?',(cat,)).fetchone()['id']
                self.conn.execute('INSERT INTO products(category_id,name,sku,price,cost,stock) VALUES(?,?,?,?,?,?)',(cid,name,sku,price,cost,stock))
        self.conn.commit()

    def close(self): self.conn.close()
    def settings(self): return {r['key']:r['value'] for r in self.conn.execute('SELECT key,value FROM settings')}
    def categories(self): return self.conn.execute('SELECT * FROM categories WHERE active=1 ORDER BY name').fetchall()
    def products(self,search='',category_id=None):
        sql='SELECT p.*,c.name category FROM products p JOIN categories c ON c.id=p.category_id WHERE p.active=1'; args=[]
        if search: sql+=' AND (p.name LIKE ? OR p.sku LIKE ?)'; args += [f'%{search}%',f'%{search}%']
        if category_id: sql+=' AND p.category_id=?'; args.append(category_id)
        return self.conn.execute(sql+' ORDER BY c.name,p.name',args).fetchall()
    def save_product(self,pid,category_id,name,sku,price,cost,stock,reorder):
        if pid: self.conn.execute('UPDATE products SET category_id=?,name=?,sku=?,price=?,cost=?,stock=?,reorder_level=? WHERE id=?',(category_id,name,sku,price,cost,stock,reorder,pid))
        else: self.conn.execute('INSERT INTO products(category_id,name,sku,price,cost,stock,reorder_level) VALUES(?,?,?,?,?,?,?)',(category_id,name,sku,price,cost,stock,reorder))
        self.conn.commit()
    def adjust_stock(self,pid,qty,note='Stock adjustment'):
        self.conn.execute('UPDATE products SET stock=stock+? WHERE id=?',(qty,pid)); self.conn.execute('INSERT INTO stock_movements(product_id,movement_type,qty,note,created_at) VALUES(?,?,?,?,?)',(pid,'ADJUSTMENT',qty,note,datetime.now().isoformat(timespec='seconds'))); self.conn.commit()
    def customers(self,search=''):
        if search: return self.conn.execute('SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? ORDER BY name',(f'%{search}%',f'%{search}%')).fetchall()
        return self.conn.execute('SELECT * FROM customers ORDER BY name').fetchall()
    def save_customer(self,name,phone,email):
        self.conn.execute('INSERT INTO customers(name,phone,email,created_at) VALUES(?,?,?,?)',(name,phone or None,email,datetime.now().isoformat(timespec='seconds'))); self.conn.commit()
    def login(self,username,password): return self.conn.execute('SELECT * FROM users WHERE username=? AND password=? AND active=1',(username,password)).fetchone()
    def create_order(self,user_id,customer_id,order_type,items,discount,tax_rate,payment,paid):
        subtotal=sum(i['qty']*i['price'] for i in items); discount=max(0,min(float(discount),subtotal)); tax=(subtotal-discount)*tax_rate/100; total=subtotal-discount+tax; paid=float(paid); change=max(0,paid-total)
        if paid+1e-9<total: raise ValueError('Paid amount is less than the order total.')
        for i in items:
            p=self.conn.execute('SELECT stock FROM products WHERE id=? AND active=1',(i['product_id'],)).fetchone()
            if not p or p['stock']<i['qty']: raise ValueError(f"Insufficient stock for {i['name']}.")
        now=datetime.now(); order_no='ORD-'+now.strftime('%Y%m%d%H%M%S')+'-'+str(now.microsecond//1000).zfill(3); cur=self.conn.cursor()
        cur.execute('INSERT INTO orders(order_no,created_at,user_id,customer_id,order_type,subtotal,discount,tax,total,payment_method,paid,change_amount) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(order_no,now.isoformat(timespec='seconds'),user_id,customer_id,order_type,subtotal,discount,tax,total,payment,paid,change)); oid=cur.lastrowid
        for i in items:
            amount=i['qty']*i['price']; cur.execute('INSERT INTO order_items(order_id,product_id,item_name,qty,price,cost,amount) VALUES(?,?,?,?,?,?,?)',(oid,i['product_id'],i['name'],i['qty'],i['price'],i['cost'],amount)); cur.execute('UPDATE products SET stock=stock-? WHERE id=?',(i['qty'],i['product_id'])); cur.execute('INSERT INTO stock_movements(product_id,movement_type,qty,note,created_at) VALUES(?,?,?,?,?)',(i['product_id'],'SALE',-i['qty'],order_no,now.isoformat(timespec='seconds')))
        if customer_id: cur.execute('UPDATE customers SET points=points+? WHERE id=?',(int(total//100),customer_id))
        self.conn.commit(); return oid,order_no,subtotal,discount,tax,total,change
    def dashboard(self):
        today=datetime.now().strftime('%Y-%m-%d'); s=self.conn.execute("SELECT COALESCE(SUM(total),0) total,COUNT(*) orders FROM orders WHERE date(created_at)=? AND status='Completed'",(today,)).fetchone(); low=self.conn.execute('SELECT COUNT(*) n FROM products WHERE active=1 AND stock<=reorder_level').fetchone()['n']; items=self.conn.execute("SELECT item_name,SUM(qty) qty FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE date(o.created_at)=? GROUP BY product_id ORDER BY qty DESC LIMIT 5",(today,)).fetchall(); return s['total'],s['orders'],low,items
    def sales(self,df='',dt=''):
        sql='SELECT o.*,u.username,c.name customer FROM orders o LEFT JOIN users u ON u.id=o.user_id LEFT JOIN customers c ON c.id=o.customer_id WHERE 1=1'; args=[]
        if df: sql+=' AND date(o.created_at)>=?'; args.append(df)
        if dt: sql+=' AND date(o.created_at)<=?'; args.append(dt)
        return self.conn.execute(sql+' ORDER BY o.id DESC LIMIT 500',args).fetchall()
    def order_items(self,oid): return self.conn.execute('SELECT * FROM order_items WHERE order_id=?',(oid,)).fetchall()
    def report_summary(self,df,dt):
        row=self.conn.execute('SELECT COUNT(*) orders,COALESCE(SUM(subtotal),0) subtotal,COALESCE(SUM(discount),0) discount,COALESCE(SUM(tax),0) tax,COALESCE(SUM(total),0) total FROM orders WHERE date(created_at) BETWEEN ? AND ?',(df,dt)).fetchone(); profit=self.conn.execute('SELECT COALESCE(SUM(oi.amount-oi.qty*oi.cost),0) profit FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE date(o.created_at) BETWEEN ? AND ?',(df,dt)).fetchone()['profit']; payments=self.conn.execute('SELECT payment_method,COUNT(*) orders,COALESCE(SUM(total),0) total FROM orders WHERE date(created_at) BETWEEN ? AND ? GROUP BY payment_method',(df,dt)).fetchall(); return row,profit,payments
