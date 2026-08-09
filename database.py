import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).with_name("fastfood_pos.db")

class Database:
    def __init__(self, path=DB_PATH):
        self.path=Path(path)
        self.conn=sqlite3.connect(self.path)
        self.conn.row_factory=sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.setup()
    def setup(self):
        self.conn.executescript("""
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
        CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY AUTOINCREMENT,code TEXT UNIQUE NOT NULL,name TEXT UNIQUE NOT NULL,account_type TEXT NOT NULL,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS journal_entries(id INTEGER PRIMARY KEY AUTOINCREMENT,entry_no TEXT UNIQUE NOT NULL,created_at TEXT NOT NULL,reference TEXT,description TEXT,business_day_id INTEGER,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS journal_lines(id INTEGER PRIMARY KEY AUTOINCREMENT,journal_id INTEGER NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,account_id INTEGER NOT NULL REFERENCES accounts(id),debit REAL DEFAULT 0,credit REAL DEFAULT 0);
        CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
        CREATE INDEX IF NOT EXISTS idx_stock_product ON stock_movements(product_id,created_at);
        CREATE INDEX IF NOT EXISTS idx_customer_tx ON customer_transactions(customer_id,created_at);
        CREATE INDEX IF NOT EXISTS idx_supplier_tx ON supplier_transactions(supplier_id,created_at);
        CREATE INDEX IF NOT EXISTS idx_cash_day ON cash_transactions(business_day_id,created_at);
        CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);
        CREATE INDEX IF NOT EXISTS idx_order_customer ON orders(customer_id,created_at);
        """)
        for u,role in (("admin","Admin"),("owner","Owner")):
            self.conn.execute("INSERT OR IGNORE INTO users(username,password,role) VALUES(?,?,?)",(u,"0099",role))
            self.conn.execute("UPDATE users SET password='0099',role=?,active=1 WHERE username=?",(role,u))
        for n in ("Burgers","Pizza","Sides","Drinks","Desserts"): self.conn.execute("INSERT OR IGNORE INTO categories(name) VALUES(?)",(n,))
        defaults={"store_name":"MK Pizza & Ice Bar","store_address":"Collage Road Abbas Chowk, Bhakkar, Pakistan","store_phone":"0316 9700025","tax_rate":"0","currency":"Rs.","printer_bluetooth_mac":"","printer_name":"","printer_port":"","printer_channel":"1","business_day_start":"06:00","business_day_end":"05:59","receipt_footer":"Thank you for visiting MK Pizza & Ice Bar!"}
        for k,v in defaults.items(): self.conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",(k,v))
        for row in (("1000","Cash","Asset"),("1010","Bank / Card","Asset"),("1100","Accounts Receivable","Asset"),("1200","Inventory","Asset"),("2000","Accounts Payable","Liability"),("3000","Owner Equity","Equity"),("4000","Sales Revenue","Revenue"),("4100","Discounts","Contra Revenue"),("5000","Cost of Goods Sold","Expense"),("6000","Operating Expenses","Expense"),("7000","Tax Payable","Liability")):
            self.conn.execute("INSERT OR IGNORE INTO accounts(code,name,account_type) VALUES(?,?,?)",row)
        if self.conn.execute("SELECT COUNT(*) n FROM products").fetchone()["n"]==0:
            for cat,name,sku,price,cost,stock in (("Burgers","Classic Burger","BUR-001",350,180,50),("Burgers","Chicken Burger","BUR-002",450,240,50),("Pizza","Chicken Pizza","PIZ-001",900,500,30),("Pizza","Cheese Pizza","PIZ-002",800,420,30),("Sides","French Fries","SID-001",250,100,80),("Sides","Chicken Nuggets","SID-002",400,220,60),("Drinks","Soft Drink","DRK-001",120,60,100),("Drinks","Mineral Water","DRK-002",80,30,100),("Desserts","Ice Cream","DES-001",200,80,40)):
                cid=self.conn.execute("SELECT id FROM categories WHERE name=?",(cat,)).fetchone()["id"];self.conn.execute("INSERT INTO products(category_id,name,sku,price,cost,stock) VALUES(?,?,?,?,?,?)",(cid,name,sku,price,cost,stock))
        self.conn.commit()
    def close(self): self.conn.close()
    def settings(self): return {r["key"]:r["value"] for r in self.conn.execute("SELECT key,value FROM settings")}
    def save_settings(self,values,user_id=None):
        for k,v in values.items(): self.conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,str(v)))
        self.audit(user_id,"UPDATE","settings",None,"Settings updated");self.conn.commit()
    def login(self,u,p): return self.conn.execute("SELECT * FROM users WHERE username=? AND password=? AND active=1",(u,p)).fetchone()
    def audit(self,user_id,action,entity,entity_id=None,details=""): self.conn.execute("INSERT INTO audit_logs(created_at,user_id,action,entity,entity_id,details) VALUES(?,?,?,?,?,?)",(datetime.now().isoformat(timespec="seconds"),user_id,action,entity,entity_id,details))
    def categories(self): return self.conn.execute("SELECT * FROM categories WHERE active=1 ORDER BY name").fetchall()
    def products(self,search="",category_id=None,include_inactive=False):
        sql="SELECT p.*,c.name category FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE 1=1";a=[]
        if not include_inactive:sql+=" AND p.active=1"
        if search:sql+=" AND (p.name LIKE ? OR p.sku LIKE ?)";a += [f"%{search}%",f"%{search}%"]
        if category_id:sql+=" AND p.category_id=?";a.append(category_id)
        return self.conn.execute(sql+" ORDER BY c.name,p.name",a).fetchall()
    def save_product(self,pid,category_id,name,sku,price,cost,stock,reorder,user_id=None):
        if not name or not sku:raise ValueError("Product name and SKU are required.")
        old=self.conn.execute("SELECT price FROM products WHERE id=?",(pid,)).fetchone() if pid else None
        if pid:self.conn.execute("UPDATE products SET category_id=?,name=?,sku=?,price=?,cost=?,stock=?,reorder_level=?,active=1 WHERE id=?",(category_id,name,sku,price,cost,stock,reorder,pid))
        else:self.conn.execute("INSERT INTO products(category_id,name,sku,price,cost,stock,reorder_level) VALUES(?,?,?,?,?,?,?)",(category_id,name,sku,price,cost,stock,reorder));pid=self.conn.execute("SELECT id FROM products WHERE sku=?",(sku,)).fetchone()["id"]
        if old and float(old["price"])!=float(price):self.conn.execute("INSERT INTO price_history(product_id,old_price,new_price,changed_at,user_id) VALUES(?,?,?,?,?)",(pid,old["price"],price,datetime.now().isoformat(timespec="seconds"),user_id))
        self.audit(user_id,"SAVE","product",pid,name);self.conn.commit();return pid
    def delete_product(self,pid,hard=False,user_id=None):
        if hard:self.conn.execute("DELETE FROM products WHERE id=?",(pid,))
        else:self.conn.execute("UPDATE products SET active=0 WHERE id=?",(pid,))
        self.audit(user_id,"DELETE","product",pid,"Hard delete" if hard else "Deactivated");self.conn.commit()
    def delete_all_products(self,user_id=None):self.conn.execute("UPDATE products SET active=0");self.audit(user_id,"DELETE_ALL","product",None,"All products deactivated");self.conn.commit()
    def adjust_stock(self,pid,qty,note="Adjustment",business_day_id=None,user_id=None):
        self.conn.execute("UPDATE products SET stock=stock+? WHERE id=?",(qty,pid));self.conn.execute("INSERT INTO stock_movements(product_id,movement_type,qty,note,created_at,business_day_id) VALUES(?,?,?,?,?,?)",(pid,"ADJUSTMENT",qty,note,datetime.now().isoformat(timespec="seconds"),business_day_id));self.audit(user_id,"ADJUST","stock",pid,note);self.conn.commit()
    def customers(self,search=""):
        return self.conn.execute("SELECT c.*,COALESCE((SELECT SUM(debit-credit) FROM customer_transactions WHERE customer_id=c.id),0)+c.opening_balance balance FROM customers c WHERE c.name LIKE ? OR COALESCE(c.phone,'') LIKE ? ORDER BY c.name",(f"%{search}%",f"%{search}%")).fetchall()
    def suppliers(self,search=""):
        return self.conn.execute("SELECT s.*,COALESCE((SELECT SUM(debit-credit) FROM supplier_transactions WHERE supplier_id=s.id),0)+s.opening_balance balance FROM suppliers s WHERE s.name LIKE ? OR COALESCE(s.phone,'') LIKE ? ORDER BY s.name",(f"%{search}%",f"%{search}%")).fetchall()
    def save_customer(self,name,phone,email,opening=0): self.conn.execute("INSERT INTO customers(name,phone,email,opening_balance,created_at) VALUES(?,?,?,?,?)",(name,phone or None,email or None,float(opening),datetime.now().isoformat(timespec="seconds")));self.conn.commit()
    def save_supplier(self,name,phone,email,opening=0): self.conn.execute("INSERT INTO suppliers(name,phone,email,opening_balance,created_at) VALUES(?,?,?,?,?)",(name,phone or None,email or None,float(opening),datetime.now().isoformat(timespec="seconds")));self.conn.commit()
    def customer_history(self,cid):return self.conn.execute("SELECT * FROM customer_transactions WHERE customer_id=? ORDER BY id DESC",(cid,)).fetchall()
    def supplier_history(self,sid):return self.conn.execute("SELECT * FROM supplier_transactions WHERE supplier_id=? ORDER BY id DESC",(sid,)).fetchall()
    def product_history(self,pid):return self.conn.execute("SELECT created_at,movement_type,qty,note FROM stock_movements WHERE product_id=? ORDER BY id DESC",(pid,)).fetchall()
    def business_date(self,now=None):
        now=now or datetime.now();start=self.settings().get("business_day_start","06:00");h,m=map(int,start.split(":"));boundary=now.replace(hour=h,minute=m,second=0,microsecond=0);return (now-timedelta(days=1)).strftime("%Y-%m-%d") if now<boundary else now.strftime("%Y-%m-%d")
    def current_business_day(self):return self.conn.execute("SELECT * FROM business_days WHERE business_date=?",(self.business_date(),)).fetchone()
    def open_business_day(self,opening_cash):
        d=self.business_date();row=self.conn.execute("SELECT * FROM business_days WHERE business_date=?",(d,)).fetchone()
        if row and row["status"]=="Open":return row["id"]
        if row and row["status"]=="Closed":raise ValueError("Business day already closed.")
        cur=self.conn.execute("INSERT INTO business_days(business_date,opened_at,opening_cash,status) VALUES(?,?,?,'Open')",(d,datetime.now().isoformat(timespec="seconds"),float(opening_cash)));self.conn.commit();return cur.lastrowid
    def cash(self,amount,typ,note="",user_id=None,ref="",business_day_id=None):
        bid=business_day_id or (self.current_business_day()["id"] if self.current_business_day() else None);self.conn.execute("INSERT INTO cash_transactions(created_at,type,amount,note,reference,user_id,business_day_id) VALUES(?,?,?,?,?,?,?)",(datetime.now().isoformat(timespec="seconds"),typ,float(amount),note,ref,user_id,bid));self.conn.commit()
    def close_business_day(self,actual_cash,note=""):
        b=self.current_business_day()
        if not b:raise ValueError("Open a business day first.")
        expected=float(b["opening_cash"])+float(self.conn.execute("SELECT COALESCE(SUM(amount),0) x FROM cash_transactions WHERE business_day_id=?",(b["id"],)).fetchone()["x"]);variance=float(actual_cash)-expected
        self.conn.execute("UPDATE business_days SET closed_at=?,closing_cash=?,expected_cash=?,variance=?,status='Closed',note=? WHERE id=?",(datetime.now().isoformat(timespec="seconds"),actual_cash,expected,variance,note,b["id"]));self.audit(None,"CLOSE","business_day",b["id"],f"Expected {expected}; actual {actual_cash}; variance {variance}");self.conn.commit();return expected,variance
    def cash_flow(self,bid=None):return self.conn.execute("SELECT * FROM cash_transactions WHERE business_day_id=? ORDER BY id",(bid or (self.current_business_day()["id"] if self.current_business_day() else -1),)).fetchall()
    def add_expense(self,category,description,amount,payment,user_id=None,bid=None):
        bid=bid or (self.current_business_day()["id"] if self.current_business_day() else None);now=datetime.now();ref="EXP-"+now.strftime("%Y%m%d%H%M%S%f");amount=float(amount)
        if amount<=0:raise ValueError("Expense amount must be greater than zero.")
        try:
            self.conn.execute("BEGIN");self.conn.execute("INSERT INTO expenses(created_at,category,description,amount,payment_method,business_day_id,user_id) VALUES(?,?,?,?,?,?,?)",(now.isoformat(timespec="seconds"),category,description,amount,payment,bid,user_id))
            if payment=="Cash":self.conn.execute("INSERT INTO cash_transactions(created_at,type,amount,note,reference,user_id,business_day_id,payment_method) VALUES(?,?,?,?,?,?,?,?)",(now.isoformat(timespec="seconds"),"EXPENSE",-amount,description,ref,user_id,bid,payment))
            from modules.accounting import Accounting
            Accounting(self).expense(ref,amount,payment,bid,user_id)
            self.audit(user_id,"CREATE","expense",None,description);self.conn.commit()
        except Exception:self.conn.rollback();raise
    def sales(self,df="",dt="",user_id=None,payment=None,customer_id=None):
        sql="SELECT o.*,u.username,cu.name customer FROM orders o LEFT JOIN users u ON u.id=o.user_id LEFT JOIN customers cu ON cu.id=o.customer_id WHERE 1=1";a=[]
        if df:sql+=" AND date(o.created_at)>=?";a.append(df)
        if dt:sql+=" AND date(o.created_at)<=?";a.append(dt)
        if user_id:sql+=" AND o.user_id=?";a.append(user_id)
        if payment:sql+=" AND o.payment_method=?";a.append(payment)
        if customer_id:sql+=" AND o.customer_id=?";a.append(customer_id)
        return self.conn.execute(sql+" ORDER BY o.id DESC LIMIT 2000",a).fetchall()
    def order_items(self,oid):return self.conn.execute("SELECT * FROM order_items WHERE order_id=?",(oid,)).fetchall()
    def report(self,df,dt):
        s=self.conn.execute("SELECT COUNT(*) orders,COALESCE(SUM(total),0) sales,COALESCE(SUM(discount),0) discounts,COALESCE(SUM(tax),0) tax FROM orders WHERE date(created_at) BETWEEN ? AND ?",(df,dt)).fetchone();c=self.conn.execute("SELECT COALESCE(SUM(qty*cost),0) cost FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE date(o.created_at) BETWEEN ? AND ?",(df,dt)).fetchone()["cost"];e=self.conn.execute("SELECT COALESCE(SUM(amount),0) expenses FROM expenses WHERE date(created_at) BETWEEN ? AND ?",(df,dt)).fetchone()["expenses"];gross=s["sales"]-c;return s,c,e,gross,gross-e
    def audit_logs(self,limit=500):return self.conn.execute("SELECT a.*,u.username FROM audit_logs a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT ?",(limit,)).fetchall()
