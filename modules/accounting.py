from datetime import datetime

class Accounting:
    """Double-entry accounting services for the POS."""
    def __init__(self, db): self.db=db; self.ensure_schema()
    def ensure_schema(self):
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY AUTOINCREMENT,code TEXT UNIQUE NOT NULL,name TEXT UNIQUE NOT NULL,account_type TEXT NOT NULL,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS journal_entries(id INTEGER PRIMARY KEY AUTOINCREMENT,entry_no TEXT UNIQUE NOT NULL,created_at TEXT NOT NULL,reference TEXT,description TEXT,business_day_id INTEGER,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS journal_lines(id INTEGER PRIMARY KEY AUTOINCREMENT,journal_id INTEGER NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,account_id INTEGER NOT NULL REFERENCES accounts(id),debit REAL DEFAULT 0,credit REAL DEFAULT 0);
        CREATE INDEX IF NOT EXISTS idx_journal_date ON journal_entries(created_at);
        CREATE INDEX IF NOT EXISTS idx_journal_account ON journal_lines(account_id);
        """)
        for row in [("1000","Cash","Asset"),("1010","Bank / Card","Asset"),("1100","Accounts Receivable","Asset"),("1200","Inventory","Asset"),("2000","Accounts Payable","Liability"),("3000","Owner Equity","Equity"),("4000","Sales Revenue","Revenue"),("4100","Discounts","Contra Revenue"),("5000","Cost of Goods Sold","Expense"),("6000","Operating Expenses","Expense"),("7000","Tax Payable","Liability")]: self.db.conn.execute("INSERT OR IGNORE INTO accounts(code,name,account_type) VALUES(?,?,?)",row)
        self.db.conn.commit()
    def account_id(self,name):
        r=self.db.conn.execute("SELECT id FROM accounts WHERE name=?",(name,)).fetchone()
        if not r: raise ValueError(f"Account not found: {name}")
        return r["id"]
    def post(self,reference,description,lines,business_day_id=None,user_id=None):
        debit=round(sum(float(x[1]) for x in lines),2);credit=round(sum(float(x[2]) for x in lines),2)
        if abs(debit-credit)>0.01:raise ValueError(f"Unbalanced journal entry: debit {debit} != credit {credit}")
        now=datetime.now().isoformat(timespec="seconds");entry_no="JE-"+datetime.now().strftime("%Y%m%d%H%M%S%f");cur=self.db.conn.cursor();cur.execute("INSERT INTO journal_entries(entry_no,created_at,reference,description,business_day_id,user_id) VALUES(?,?,?,?,?,?)",(entry_no,now,reference,description,business_day_id,user_id));jid=cur.lastrowid
        for account,d,c in lines:cur.execute("INSERT INTO journal_lines(journal_id,account_id,debit,credit) VALUES(?,?,?,?)",(jid,self.account_id(account),float(d),float(c)))
        return jid
    def sale(self,reference,total,cost,payment,customer_id=None,tax=0,discount=0,business_day_id=None,user_id=None):
        debit_account="Accounts Receivable" if payment=="Credit" else ("Cash" if payment=="Cash" else "Bank / Card")
        gross_revenue=max(0,float(total)+float(discount)-float(tax))
        lines=[(debit_account,float(total),0),("Sales Revenue",0,gross_revenue),("Tax Payable",0,max(0,float(tax)))]
        if discount:lines.append(("Discounts",float(discount),0))
        if cost:lines += [("Cost of Goods Sold",float(cost),0),("Inventory",0,float(cost))]
        self.post(reference,"POS sale",lines,business_day_id,user_id)
    def purchase(self,reference,total,paid,payment,business_day_id=None,user_id=None):
        lines=[("Inventory",total,0)]
        if paid:lines.append(("Cash" if payment=="Cash" else "Bank / Card",0,paid))
        if total-paid:lines.append(("Accounts Payable",0,total-paid))
        self.post(reference,"Purchase",lines,business_day_id,user_id)
    def expense(self,reference,amount,payment,business_day_id=None,user_id=None):self.post(reference,"Operating expense",[("Operating Expenses",amount,0),("Cash" if payment=="Cash" else "Bank / Card",0,amount)],business_day_id,user_id)
    def customer_payment(self,reference,amount,payment,business_day_id=None,user_id=None):self.post(reference,"Customer payment",[("Cash" if payment=="Cash" else "Bank / Card",amount,0),("Accounts Receivable",0,amount)],business_day_id,user_id)
    def supplier_payment(self,reference,amount,payment,business_day_id=None,user_id=None):self.post(reference,"Supplier payment",[("Accounts Payable",amount,0),("Cash" if payment=="Cash" else "Bank / Card",0,amount)],business_day_id,user_id)
    def cash_transfer(self,reference,amount,from_account="Cash",to_account="Bank / Card",business_day_id=None,user_id=None):self.post(reference,"Cash transfer",[(to_account,amount,0),(from_account,0,amount)],business_day_id,user_id)
    def trial_balance(self,date_from=None,date_to=None):
        where=[];args=[]
        if date_from:where.append("date(j.created_at)>=?");args.append(date_from)
        if date_to:where.append("date(j.created_at)<=?");args.append(date_to)
        w=" WHERE "+" AND ".join(where) if where else ""
        return self.db.conn.execute(f"SELECT a.code,a.name,a.account_type,COALESCE(SUM(l.debit),0) debit,COALESCE(SUM(l.credit),0) credit FROM accounts a LEFT JOIN journal_lines l ON l.account_id=a.id LEFT JOIN journal_entries j ON j.id=l.journal_id {w} GROUP BY a.id ORDER BY a.code",args).fetchall()
    def profit_loss(self,date_from,date_to):
        rows=self.trial_balance(date_from,date_to);revenue=sum(r["credit"]-r["debit"] for r in rows if r["account_type"]=="Revenue");contra=sum(r["debit"]-r["credit"] for r in rows if r["account_type"]=="Contra Revenue");expenses=sum(r["debit"]-r["credit"] for r in rows if r["account_type"]=="Expense");return {"revenue":revenue,"discounts":contra,"expenses":expenses,"net_profit":revenue-contra-expenses,"rows":rows}
