import csv, tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from database import Database
from modules.services import create_sale, create_purchase, customer_payment, supplier_payment
from modules.import_export import export_products, import_products
from modules.accounting import Accounting
from modules.backup import backup_database, restore_database
from modules.printer import BluetoothPrinter

class Login(tk.Tk):
    def __init__(self):
        super().__init__(); self.db=Database(); self.title("MK Pizza & Ice Bar"); self.geometry("430x310")
        f=ttk.Frame(self,padding=28); f.pack(fill="both",expand=True); ttk.Label(f,text="MK Pizza & Ice Bar",font=("Arial",22,"bold")).pack(pady=8); ttk.Label(f,text="Advanced POS").pack(pady=(0,15))
        self.u=tk.StringVar(value="admin"); self.p=tk.StringVar(value="0099")
        for label,var,show in (("Username",self.u,""),("Password",self.p,"*")): ttk.Label(f,text=label).pack(anchor="w"); ttk.Entry(f,textvariable=var,show=show).pack(fill="x",pady=4)
        ttk.Button(f,text="LOGIN",command=self.login).pack(fill="x",ipady=7); ttk.Label(f,text="admin / 0099    owner / 0099").pack(pady=10); self.protocol("WM_DELETE_WINDOW",self.close)
    def login(self):
        r=self.db.login(self.u.get().strip(),self.p.get())
        if not r:return messagebox.showerror("Login Failed","Invalid username or password.")
        self.withdraw(); POS(self.db,r).mainloop()
    def close(self): self.db.close(); self.destroy()

class POS(tk.Toplevel):
    def __init__(self,db,user):
        super().__init__(); self.db=db; self.user=user; self.cfg=db.settings(); self.cart=[]; self.purchase_items=[]; self.printer=None
        self.title(self.cfg["store_name"]); self.geometry("1500x900"); self.protocol("WM_DELETE_WINDOW",self.close); self.make_ui(); self.refresh_all(); self.start_printer()
    def money(self,x): return f"{self.cfg.get('currency','Rs.')} {float(x):,.2f}"
    def tree(self,p,cols):
        t=ttk.Treeview(p,columns=cols,show="headings")
        for c in cols:t.heading(c,text=c);t.column(c,width=120,anchor="center")
        t.pack(fill="both",expand=True);return t
    def make_ui(self):
        h=ttk.Frame(self,padding=8);h.pack(fill="x");ttk.Label(h,text=self.cfg["store_name"],font=("Arial",20,"bold")).pack(side="left");ttk.Label(h,text=f" | {self.user['username']} ({self.user['role']})").pack(side="left");ttk.Button(h,text="Refresh",command=self.refresh_all).pack(side="right");ttk.Button(h,text="Logout",command=self.close).pack(side="right",padx=4)
        self.nb=ttk.Notebook(self);self.nb.pack(fill="both",expand=True,padx=8,pady=8)
        for name,fn in [("Dashboard",self.dashboard),("POS",self.pos),("Products",self.products),("Customers",self.customers),("Suppliers",self.suppliers),("Purchases",self.purchases),("Expenses",self.expenses),("Cash & Day",self.cashday),("Sales",self.sales),("Accounting",self.accounting),("Reports",self.reports),("Settings",self.settings)]:
            f=ttk.Frame(self.nb,padding=8);self.nb.add(f,text=name);fn(f)
    def refresh_all(self):
        for n in ("dash","prod","sale","cash","exp","acct"):
            f=getattr(self,"refresh_"+n,None)
            if f:
                try:f()
                except Exception:pass
        try:self.refresh_party("customer",self.custtfilter.get())
        except Exception:pass
        try:self.refresh_party("supplier",self.supptfilter.get())
        except Exception:pass
    def dashboard(self,f):
        self.cards=[tk.StringVar(value="0") for _ in range(7)];labels=["Sales","Orders","Gross Profit","Expenses","Net Profit","Customer Due","Supplier Due"];row=ttk.Frame(f);row.pack(fill="x")
        for i,l in enumerate(labels):
            x=ttk.LabelFrame(row,text=l,padding=10);x.grid(row=0,column=i,sticky="nsew",padx=2);row.columnconfigure(i,weight=1);ttk.Label(x,textvariable=self.cards[i],font=("Arial",13,"bold")).pack()
        self.day=tk.StringVar();ttk.Label(f,textvariable=self.day,font=("Arial",12,"bold")).pack(anchor="w",pady=10);self.top=self.tree(f,["Product","Qty","Revenue"])
    def refresh_dash(self):
        d=self.db.business_date();r,c,e,g,n=self.db.report(d,d);cu=sum(max(0,float(x["balance"])) for x in self.db.customers());su=sum(max(0,float(x["balance"])) for x in self.db.suppliers());vals=[r["sales"],r["orders"],g,e,n,cu,su]
        for i,x in enumerate(vals):self.cards[i].set(str(x) if i==1 else self.money(x))
        b=self.db.current_business_day();self.day.set(f"Business day {d} | "+("OPEN" if b else "NOT OPEN"))
        for x in self.top.get_children():self.top.delete(x)
        for q in self.db.conn.execute("SELECT item_name,SUM(qty) qty,SUM(amount) revenue FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE date(o.created_at)=? GROUP BY item_name ORDER BY qty DESC LIMIT 15",(d,)):self.top.insert("","end",values=(q["item_name"],q["qty"],self.money(q["revenue"])))
    def pos(self,f):
        l=ttk.Frame(f);l.pack(side="left",fill="both",expand=True);r=ttk.LabelFrame(f,text="Order",padding=8);r.pack(side="right",fill="both",expand=True,padx=(8,0));bar=ttk.Frame(l);bar.pack(fill="x");self.q=tk.StringVar();ttk.Entry(bar,textvariable=self.q).pack(side="left",fill="x",expand=True);ttk.Button(bar,text="Search",command=self.refresh_pos).pack(side="left")
        self.cm={"All":None};[self.cm.update({c["name"]:c["id"]}) for c in self.db.categories()];self.cat=tk.StringVar(value="All");ttk.Combobox(bar,textvariable=self.cat,values=list(self.cm),state="readonly",width=15).pack(side="left",padx=4);self.pt=self.tree(l,["SKU","Category","Product","Price","Stock"]);self.pt.bind("<Double-1>",lambda e:self.add());ttk.Button(l,text="ADD",command=self.add).pack(fill="x",pady=4)
        self.ct=self.tree(r,["Item","Qty","Price","Amount"]);a=ttk.Frame(r);a.pack(fill="x")
        for t,c in (("+",lambda:self.qty(1)),("-",lambda:self.qty(-1)),("Remove",self.remove),("Clear",self.clear)):ttk.Button(a,text=t,command=c).pack(side="left",fill="x",expand=True,padx=2)
        self.typ=tk.StringVar(value="Takeaway");self.pay=tk.StringVar(value="Cash");self.customer=tk.StringVar(value="Walk-in");self.discount=tk.StringVar(value="0");self.paid=tk.StringVar(value="0")
        for label,var,vals in (("Type",self.typ,["Dine-in","Takeaway","Delivery"]),("Payment",self.pay,["Cash","Card","Mobile Wallet","Credit"])):ttk.Label(r,text=label).pack(anchor="w");ttk.Combobox(r,textvariable=var,values=vals,state="readonly").pack(fill="x")
        ttk.Label(r,text="Customer").pack(anchor="w");self.cc=ttk.Combobox(r,textvariable=self.customer,state="readonly");self.cc.pack(fill="x");self.load_customers()
        for label,var in (("Discount",self.discount),("Paid",self.paid)):ttk.Label(r,text=label).pack(anchor="w");ttk.Entry(r,textvariable=var).pack(fill="x")
        self.total=ttk.Label(r,font=("Arial",14,"bold"));self.total.pack(anchor="e",pady=8);ttk.Button(r,text="COMPLETE SALE + RECEIPT",command=self.finish_sale).pack(fill="x",ipady=8)
    def load_customers(self):
        if hasattr(self,"cc"):self.custmap={"Walk-in":None};[self.custmap.update({f"{c['name']} ({c['phone'] or ''})":c["id"]}) for c in self.db.customers()];self.cc["values"]=list(self.custmap)
    def refresh_pos(self):
        for x in self.pt.get_children():self.pt.delete(x)
        for p in self.db.products(self.q.get(),self.cm.get(self.cat.get())):self.pt.insert("","end",iid=str(p["id"]),values=(p["sku"],p["category"],p["name"],self.money(p["price"]),p["stock"]))
    def add(self):
        s=self.pt.selection()
        if not s:return
        p=self.db.conn.execute("SELECT * FROM products WHERE id=?",(s[0],)).fetchone();i=next((x for x in self.cart if x["product_id"]==p["id"]),None)
        if p["stock"]<=0:return messagebox.showwarning("Stock","Out of stock.")
        if i:
            if i["qty"]>=p["stock"]:return messagebox.showwarning("Stock","Insufficient stock.")
            i["qty"]+=1
        else:self.cart.append({"product_id":p["id"],"name":p["name"],"price":p["price"],"cost":p["cost"],"qty":1})
        self.refresh_cart()
    def refresh_cart(self):
        for x in self.ct.get_children():self.ct.delete(x)
        sub=sum(i["qty"]*i["price"] for i in self.cart)
        for i in self.cart:self.ct.insert("","end",values=(i["name"],i["qty"],self.money(i["price"]),self.money(i["qty"]*i["price"])))
        try:d=max(0,min(float(self.discount.get() or 0),sub))
        except:d=0
        tax=(sub-d)*float(self.cfg.get("tax_rate",0))/100;self.total.config(text=f"Subtotal {self.money(sub)} | Discount {self.money(d)} | Tax {self.money(tax)} | TOTAL {self.money(sub-d+tax)}")
    def qty(self,n):
        s=self.ct.selection()
        if not s:return
        i=self.cart[self.ct.index(s[0])];i["qty"]+=n
        if i["qty"]<=0:self.cart.remove(i)
        self.refresh_cart()
    def remove(self):
        s=self.ct.selection()
        if s:self.cart.pop(self.ct.index(s[0]));self.refresh_cart()
    def clear(self):self.cart=[];self.discount.set("0");self.paid.set("0");self.refresh_cart()
    def finish_sale(self):
        if not self.cart:return messagebox.showwarning("Order","Add products first.")
        try:
            if not self.db.current_business_day():self.db.open_business_day(0)
            cid=self.custmap.get(self.customer.get());r=create_sale(self.db,self.user["id"],self.cart,float(self.discount.get() or 0),float(self.cfg.get("tax_rate",0)),self.pay.get(),float(self.paid.get() or 0),self.typ.get(),cid);self.receipt(r[0]);self.clear();self.refresh_all()
        except Exception as e:messagebox.showerror("Sale",str(e))
    def receipt(self,oid):
        o=self.db.conn.execute("SELECT * FROM orders WHERE id=?",(oid,)).fetchone();lines=[self.cfg["store_name"],self.cfg["store_address"],self.cfg["store_phone"],"="*42,f"Order {o['order_no']} {o['created_at']}","-"*42]
        lines += [f"{i['item_name']} x{i['qty']} {self.money(i['amount'])}" for i in self.db.order_items(oid)];lines += ["-"*42,f"Subtotal: {self.money(o['subtotal'])}",f"Discount: {self.money(o['discount'])}",f"Tax: {self.money(o['tax'])}",f"TOTAL: {self.money(o['total'])}",f"Paid: {self.money(o['paid'])}",f"Change: {self.money(o['change_amount'])}",f"Payment: {o['payment_method']}",self.cfg["receipt_footer"]];text="\n".join(lines);open(f"receipt_{o['order_no']}.txt","w",encoding="utf-8").write(text)
        if self.printer:self.printer.send(("\x1b@"+text+"\n\x1dV\x00").encode("utf-8","replace"))
        messagebox.showinfo("Receipt",text)
    def products(self,f):
        b=ttk.Frame(f);b.pack(fill="x")
        for t,c in (("Add",self.product_dialog),("Edit",self.edit_product),("Delete",self.delete_product),("Delete ALL",self.delete_all),("Import CSV",self.import_menu),("Export CSV",self.export_menu),("Stock",self.stock_adjust)):ttk.Button(b,text=t,command=c).pack(side="left",padx=2)
        self.pfilter=tk.StringVar();ttk.Entry(b,textvariable=self.pfilter).pack(side="right");ttk.Button(b,text="Filter",command=self.refresh_prod).pack(side="right");self.prodt=self.tree(f,["ID","SKU","Category","Product","Price","Cost","Stock","Reorder"]);self.prodt.bind("<Double-1>",lambda e:self.product_history())
    def refresh_prod(self):
        for x in self.prodt.get_children():self.prodt.delete(x)
        for p in self.db.products(self.pfilter.get()):self.prodt.insert("","end",iid=str(p["id"]),values=(p["id"],p["sku"],p["category"],p["name"],self.money(p["price"]),self.money(p["cost"]),p["stock"],p["reorder_level"]))
        self.refresh_pos()
    def product_dialog(self,pid=None):
        old=self.db.conn.execute("SELECT * FROM products WHERE id=?",(pid,)).fetchone() if pid else None;w=tk.Toplevel(self);w.title("Product");w.geometry("430x460");vs={k:tk.StringVar(value=str(old[k]) if old else "") for k in ("name","sku","price","cost","stock","reorder_level")};cats=self.db.categories();mp={c["name"]:c["id"] for c in cats};cv=tk.StringVar(value=(self.db.conn.execute("SELECT name FROM categories WHERE id=?",(old["category_id"],)).fetchone()["name"] if old else cats[0]["name"]))
        for lab,k in (("Name","name"),("SKU","sku"),("Price","price"),("Cost","cost"),("Stock","stock"),("Reorder","reorder_level")):ttk.Label(w,text=lab).pack(anchor="w",padx=20,pady=(6,1));ttk.Entry(w,textvariable=vs[k]).pack(fill="x",padx=20)
        ttk.Label(w,text="Category").pack(anchor="w",padx=20,pady=(6,1));ttk.Combobox(w,textvariable=cv,values=list(mp),state="readonly").pack(fill="x",padx=20)
        def save():
            try:self.db.save_product(pid,mp[cv.get()],vs["name"].get().strip(),vs["sku"].get().strip(),float(vs["price"].get()),float(vs["cost"].get()),float(vs["stock"].get()),float(vs["reorder_level"].get()),self.user["id"]);w.destroy();self.refresh_prod()
            except Exception as e:messagebox.showerror("Product",str(e),parent=w)
        ttk.Button(w,text="SAVE",command=save).pack(fill="x",padx=20,pady=18)
    def edit_product(self):
        s=self.prodt.selection()
        if s:self.product_dialog(int(s[0]))
    def delete_product(self):
        s=self.prodt.selection()
        if s and messagebox.askyesno("Delete","Deactivate selected product?"):self.db.delete_product(int(s[0]),False,self.user["id"]);self.refresh_prod()
    def delete_all(self):
        if messagebox.askyesno("Delete ALL","Deactivate every product?"):self.db.delete_all_products(self.user["id"]);self.refresh_prod()
    def stock_adjust(self):
        s=self.prodt.selection()
        if s:
            try:self.db.adjust_stock(int(s[0]),float(self.ask("Stock adjustment","0")),self.ask("Reason","Manual adjustment"),self.db.current_business_day()["id"] if self.db.current_business_day() else None,self.user["id"]);self.refresh_prod()
            except Exception as e:messagebox.showerror("Stock",str(e))
    def product_history(self):
        s=self.prodt.selection()
        if s:self.history("Product History",self.db.product_history(int(s[0])),["created_at","movement_type","qty","note"])
    def import_menu(self):
        p=filedialog.askopenfilename(filetypes=[("CSV","*.csv")])
        if p:
            try:n=import_products(self.db,p,False);messagebox.showinfo("Import",f"{n} products imported/updated.");self.refresh_prod()
            except Exception as e:messagebox.showerror("Import",str(e))
    def export_menu(self):
        p=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if p:
            try:export_products(self.db,p);messagebox.showinfo("Export","Menu exported.")
            except Exception as e:messagebox.showerror("Export",str(e))
    def customers(self,f):self.party_tab(f,"customer")
    def suppliers(self,f):self.party_tab(f,"supplier")
    def party_tab(self,f,kind):
        top=ttk.Frame(f);top.pack(fill="x");attr="custt" if kind=="customer" else "suppt";tree=self.tree(f,["ID","Name","Phone","Email","Opening","Due"]);setattr(self,attr,tree)
        for t,c in (("Add",lambda:self.party_dialog(kind)),("Edit",lambda:self.party_dialog(kind,self.selected(tree))), ("Payment",lambda:self.party_payment(kind)),("Export",lambda:self.export_party(kind))):ttk.Button(top,text=t,command=c).pack(side="left",padx=2)
        search=tk.StringVar();ttk.Entry(top,textvariable=search).pack(side="right");ttk.Button(top,text="Filter",command=lambda:self.refresh_party(kind,search.get())).pack(side="right");setattr(self,attr+"filter",search);tree.bind("<Double-1>",lambda e:self.party_history(kind,tree))
    def refresh_party(self,kind,search=""):
        tree=self.custt if kind=="customer" else self.suppt
        for x in tree.get_children():tree.delete(x)
        rows=self.db.customers(search) if kind=="customer" else self.db.suppliers(search)
        for r in rows:tree.insert("","end",iid=str(r["id"]),values=(r["id"],r["name"],r["phone"] or "",r["email"] or "",self.money(r["opening_balance"]),self.money(max(0,float(r["balance"])))) )
        if kind=="customer":self.load_customers()
    def party_history(self,kind,tree):
        s=self.selected(tree)
        if s:self.history(kind.title()+" History",self.db.customer_history(s) if kind=="customer" else self.db.supplier_history(s),["created_at","type","reference","debit","credit","note"])
    def party_dialog(self,kind,pid=None):
        table="customers" if kind=="customer" else "suppliers";old=self.db.conn.execute(f"SELECT * FROM {table} WHERE id=?",(pid,)).fetchone() if pid else None;w=tk.Toplevel(self);w.title("Party");w.geometry("400x330");vs=[tk.StringVar(value=str(old[k]) if old else "") for k in ("name","phone","email","opening_balance")]
        for lab,v in zip(("Name","Phone","Email","Opening Balance"),vs):ttk.Label(w,text=lab).pack(anchor="w",padx=20,pady=(7,1));ttk.Entry(w,textvariable=v).pack(fill="x",padx=20)
        def save():
            try:
                if pid:self.db.conn.execute(f"UPDATE {table} SET name=?,phone=?,email=? WHERE id=?",(vs[0].get(),vs[1].get() or None,vs[2].get() or None,pid))
                else:self.db.conn.execute(f"INSERT INTO {table}(name,phone,email,opening_balance,created_at) VALUES(?,?,?,?,?)",(vs[0].get(),vs[1].get() or None,vs[2].get() or None,float(vs[3].get() or 0),datetime.now().isoformat(timespec="seconds")))
                self.db.conn.commit();w.destroy();self.refresh_party(kind,getattr(self,kind[:4]+"tfilter").get())
            except Exception as e:messagebox.showerror("Party",str(e),parent=w)
        ttk.Button(w,text="SAVE",command=save).pack(fill="x",padx=20,pady=18)
    def party_payment(self,kind):
        tree=self.custt if kind=="customer" else self.suppt;s=self.selected(tree)
        if not s:return
        rows=self.db.customers() if kind=="customer" else self.db.suppliers();due=next(float(r["balance"]) for r in rows if r["id"]==s);amount=float(self.ask("Payment",str(max(0,due))));method=self.ask_choice("Method",["Cash","Card","Mobile Wallet"],"Cash");note=self.ask("Note",kind.title()+" payment")
        try:ref=customer_payment(self.db,self.user["id"],s,amount,method,note) if kind=="customer" else supplier_payment(self.db,self.user["id"],s,amount,method,note);messagebox.showinfo("Payment",ref);self.refresh_all()
        except Exception as e:messagebox.showerror("Payment",str(e))
    def export_party(self,kind):
        p=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if not p:return
        rows=self.db.customers() if kind=="customer" else self.db.suppliers()
        with open(p,"w",newline="",encoding="utf-8") as f:
            w=csv.writer(f);w.writerow(["ID","Name","Phone","Email","Opening","Balance"])
            for r in rows:w.writerow([r["id"],r["name"],r["phone"],r["email"],r["opening_balance"],r["balance"]])
    def selected(self,t):s=t.selection();return int(s[0]) if s else None
    def history(self,title,rows,keys):
        w=tk.Toplevel(self);w.title(title);w.geometry("950x500");t=self.tree(w,keys)
        for r in rows:t.insert("","end",values=tuple(r[k] if k in r.keys() else "" for k in keys))
    def purchases(self,f):
        top=ttk.Frame(f);top.pack(fill="x");self.smap={f"{s['name']} ({s['phone'] or ''})":s["id"] for s in self.db.suppliers()};self.pmap={f"{p['name']} ({p['sku']})":p["id"] for p in self.db.products()};self.psup=tk.StringVar();self.pprod=tk.StringVar();self.pqty=tk.StringVar(value="1");self.pcost=tk.StringVar(value="0");self.ppaid=tk.StringVar(value="0");self.ppay=tk.StringVar(value="Cash")
        for label,var,vals in (("Supplier",self.psup,list(self.smap)),("Product",self.pprod,list(self.pmap))):ttk.Label(top,text=label).pack(side="left");ttk.Combobox(top,textvariable=var,values=vals,state="readonly",width=25).pack(side="left",padx=4)
        ttk.Label(top,text="Qty").pack(side="left");ttk.Entry(top,textvariable=self.pqty,width=7).pack(side="left");ttk.Label(top,text="Cost").pack(side="left");ttk.Entry(top,textvariable=self.pcost,width=9).pack(side="left");ttk.Button(top,text="Add",command=self.add_purchase).pack(side="left",padx=4);self.purt=self.tree(f,["Product","Qty","Cost","Amount"]);self.purtotal=tk.StringVar();ttk.Label(f,textvariable=self.purtotal,font=("Arial",14,"bold")).pack(anchor="e")
        bot=ttk.Frame(f);bot.pack(fill="x");ttk.Label(bot,text="Paid").pack(side="left");ttk.Entry(bot,textvariable=self.ppaid,width=12).pack(side="left");ttk.Combobox(bot,textvariable=self.ppay,values=["Cash","Card","Mobile Wallet"],state="readonly").pack(side="left");ttk.Button(bot,text="SAVE PURCHASE",command=self.save_purchase).pack(side="right")
    def add_purchase(self):
        pid=self.pmap.get(self.pprod.get())
        if not pid:return
        p=self.db.conn.execute("SELECT * FROM products WHERE id=?",(pid,)).fetchone();self.purchase_items.append({"product_id":pid,"name":p["name"],"qty":float(self.pqty.get()),"cost":float(self.pcost.get() or p["cost"])});self.refresh_purchase()
    def refresh_purchase(self):
        for x in self.purt.get_children():self.purt.delete(x)
        total=0
        for i in self.purchase_items:a=i["qty"]*i["cost"];total+=a;self.purt.insert("","end",values=(i["name"],i["qty"],self.money(i["cost"]),self.money(a)))
        self.purtotal.set("Total: "+self.money(total))
    def save_purchase(self):
        try:r=create_purchase(self.db,self.user["id"],self.smap[self.psup.get()],self.purchase_items,float(self.ppaid.get() or 0),self.ppay.get());messagebox.showinfo("Purchase",f"{r[1]} | Due {self.money(r[3])}");self.purchase_items=[];self.refresh_purchase();self.refresh_all()
        except Exception as e:messagebox.showerror("Purchase",str(e))
    def expenses(self,f):
        b=ttk.Frame(f);b.pack(fill="x");self.ev=[tk.StringVar() for _ in range(4)]
        for lab,v,vals in (("Category",self.ev[0],["Rent","Utilities","Salary","Supplies","Delivery","Repairs","Other"]),("Description",self.ev[1],None),("Amount",self.ev[2],None),("Payment",self.ev[3],["Cash","Card","Mobile Wallet"])):ttk.Label(b,text=lab).pack(side="left");(ttk.Combobox(b,textvariable=v,values=vals,state="readonly",width=14) if vals else ttk.Entry(b,textvariable=v,width=16)).pack(side="left",padx=3)
        self.ev[3].set("Cash");ttk.Button(b,text="ADD",command=self.add_expense).pack(side="left");self.expt=self.tree(f,["Date","Category","Description","Amount","Payment"])
    def add_expense(self):
        try:self.db.add_expense(self.ev[0].get(),self.ev[1].get(),float(self.ev[2].get()),self.ev[3].get(),self.user["id"]);self.refresh_exp();self.refresh_acct()
        except Exception as e:messagebox.showerror("Expense",str(e))
    def refresh_exp(self):
        for x in self.expt.get_children():self.expt.delete(x)
        for r in self.db.conn.execute("SELECT * FROM expenses ORDER BY id DESC LIMIT 500"):self.expt.insert("","end",values=(r["created_at"],r["category"],r["description"],self.money(r["amount"]),r["payment_method"]))
    def cashday(self,f):
        self.cashinfo=tk.StringVar();ttk.Label(f,textvariable=self.cashinfo,font=("Arial",13,"bold")).pack(anchor="w");b=ttk.Frame(f);b.pack(fill="x",pady=8)
        for t,c in (("Open Day",self.open_day),("Cash In",lambda:self.cash_move(1)),("Cash Out",lambda:self.cash_move(-1)),("Close/Reconcile",self.close_day)):ttk.Button(b,text=t,command=c).pack(side="left",padx=3)
        self.casht=self.tree(f,["Date","Type","Amount","Note","Reference","Payment"])
    def refresh_cash(self):
        b=self.db.current_business_day();self.cashinfo.set("No business day open." if not b else f"{b['business_date']} | Opening {self.money(b['opening_cash'])} | {b['status']} | Variance {self.money(b['variance'] or 0)}")
        for x in self.casht.get_children():self.casht.delete(x)
        if b:
            for r in self.db.cash_flow(b["id"]):self.casht.insert("","end",values=(r["created_at"],r["type"],self.money(r["amount"]),r["note"],r["reference"],r["payment_method"]))
    def open_day(self):
        try:self.db.open_business_day(float(self.ask("Opening cash","0")));self.refresh_all()
        except Exception as e:messagebox.showerror("Day",str(e))
    def cash_move(self,s):
        try:self.db.cash(s*float(self.ask("Amount","0")),"CASH_IN" if s>0 else "CASH_OUT",self.ask("Note",""),self.user["id"]);self.refresh_cash()
        except Exception as e:messagebox.showerror("Cash",str(e))
    def close_day(self):
        try:e,v=self.db.close_business_day(float(self.ask("Actual cash","0")),self.ask("Note",""));messagebox.showinfo("Reconciliation",f"Expected {self.money(e)}\nVariance {self.money(v)}");self.refresh_all()
        except Exception as e:messagebox.showerror("Day",str(e))
    def sales(self,f):
        b=ttk.Frame(f);b.pack(fill="x");self.sf=tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"));self.st=tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"));self.spp=tk.StringVar(value="All");self.sx=tk.StringVar()
        for lab,v in (("From",self.sf),("To",self.st),("Search",self.sx)):ttk.Label(b,text=lab).pack(side="left");ttk.Entry(b,textvariable=v,width=13).pack(side="left",padx=3)
        ttk.Combobox(b,textvariable=self.spp,values=["All","Cash","Card","Mobile Wallet","Credit"],state="readonly",width=14).pack(side="left");ttk.Button(b,text="FILTER",command=self.refresh_sale).pack(side="left");self.salest=self.tree(f,["Order","Date","Customer","Type","Payment","Subtotal","Discount","Tax","Total"]);self.salest.bind("<Double-1>",lambda e:self.sale_detail())
    def refresh_sale(self):
        for x in self.salest.get_children():self.salest.delete(x)
        pay=None if self.spp.get()=="All" else self.spp.get()
        for r in self.db.sales(self.sf.get(),self.st.get(),payment=pay):
            if self.sx.get().lower() not in (r["order_no"]+" "+(r["customer"] or "")).lower():continue
            self.salest.insert("","end",iid=str(r["id"]),values=(r["order_no"],r["created_at"],r["customer"] or "Walk-in",r["order_type"],r["payment_method"],self.money(r["subtotal"]),self.money(r["discount"]),self.money(r["tax"]),self.money(r["total"])))
    def sale_detail(self):
        s=self.salest.selection()
        if s:
            w=tk.Toplevel(self);w.title("Sale Detail");w.geometry("800x450");t=self.tree(w,["Item","Qty","Price","Cost","Amount"])
            for i in self.db.order_items(int(s[0])):t.insert("","end",values=(i["item_name"],i["qty"],self.money(i["price"]),self.money(i["cost"]),self.money(i["amount"])))
    def accounting(self,f):
        b=ttk.Frame(f);b.pack(fill="x");self.af=tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"));self.at=tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"));ttk.Entry(b,textvariable=self.af,width=13).pack(side="left");ttk.Entry(b,textvariable=self.at,width=13).pack(side="left");ttk.Button(b,text="RUN",command=self.refresh_acct).pack(side="left",padx=4);ttk.Button(b,text="BACKUP",command=self.backup).pack(side="left");ttk.Button(b,text="RESTORE",command=self.restore).pack(side="left",padx=3);self.acctinfo=tk.StringVar();ttk.Label(f,textvariable=self.acctinfo,font=("Arial",13,"bold"),justify="left").pack(anchor="w",pady=8);self.acctt=self.tree(f,["Code","Account","Type","Debit","Credit","Balance"])
    def refresh_acct(self):
        for x in self.acctt.get_children():self.acctt.delete(x)
        a=Accounting(self.db);tb=a.trial_balance(self.af.get(),self.at.get());pl=a.profit_loss(self.af.get(),self.at.get());self.acctinfo.set(f"Debit {self.money(sum(x['debit'] for x in tb))} | Credit {self.money(sum(x['credit'] for x in tb))}\nRevenue {self.money(pl['revenue'])} | Discounts {self.money(pl['discounts'])} | Expenses {self.money(pl['expenses'])} | NET {self.money(pl['net_profit'])}")
        for x in tb:self.acctt.insert("","end",values=(x["code"],x["name"],x["account_type"],self.money(x["debit"]),self.money(x["credit"]),self.money(x["debit"]-x["credit"])))
    def backup(self):
        try:messagebox.showinfo("Backup",f"Created: {backup_database(self.db)}")
        except Exception as e:messagebox.showerror("Backup",str(e))
    def restore(self):
        p=filedialog.askopenfilename(filetypes=[("SQLite","*.db")])
        if p and messagebox.askyesno("Restore","Restore and restart POS?"):
            try:target=self.db.path;self.db.close();restore_database(p,target);messagebox.showinfo("Restore","Restored. Restart the application.")
            except Exception as e:messagebox.showerror("Restore",str(e))
    def reports(self,f):
        b=ttk.Frame(f);b.pack(fill="x");self.rf=tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"));self.rt=tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"));ttk.Entry(b,textvariable=self.rf,width=13).pack(side="left");ttk.Entry(b,textvariable=self.rt,width=13).pack(side="left");ttk.Button(b,text="RUN",command=self.run_report).pack(side="left");self.rep=tk.StringVar();ttk.Label(f,textvariable=self.rep,font=("Arial",13,"bold"),justify="left").pack(anchor="w",pady=10);self.flow=self.tree(f,["Date","Type","Amount","Note","Reference","Payment"])
    def run_report(self):
        r,c,e,g,n=self.db.report(self.rf.get(),self.rt.get());self.rep.set(f"Orders {r['orders']} | Sales {self.money(r['sales'])}\nCOGS {self.money(c)} | Gross Profit {self.money(g)} | Expenses {self.money(e)} | NET {self.money(n)}\nTax {self.money(r['tax'])} | Discounts {self.money(r['discounts'])}")
        for x in self.flow.get_children():self.flow.delete(x)
        for q in self.db.conn.execute("SELECT * FROM cash_transactions WHERE date(created_at) BETWEEN ? AND ? ORDER BY id",(self.rf.get(),self.rt.get())):self.flow.insert("","end",values=(q["created_at"],q["type"],self.money(q["amount"]),q["note"],q["reference"],q["payment_method"]))
    def settings(self,f):
        keys=["store_name","store_address","store_phone","currency","tax_rate","business_day_start","business_day_end","printer_bluetooth_mac","printer_name","printer_port","printer_channel","receipt_footer"];self.sv={k:tk.StringVar(value=self.cfg.get(k,"")) for k in keys};grid=ttk.Frame(f);grid.pack(fill="x");labels=[("Business","store_name"),("Address","store_address"),("Phone","store_phone"),("Currency","currency"),("Tax %","tax_rate"),("Day Start","business_day_start"),("Day End","business_day_end"),("Printer MAC","printer_bluetooth_mac"),("Printer Name","printer_name"),("COM Port","printer_port"),("RFCOMM Channel","printer_channel"),("Receipt Footer","receipt_footer")]
        for i,(lab,k) in enumerate(labels):ttk.Label(grid,text=lab).grid(row=i,column=0,sticky="w",pady=3);ttk.Entry(grid,textvariable=self.sv[k],width=65).grid(row=i,column=1,sticky="ew",pady=3)
        b=ttk.Frame(f);b.pack(fill="x",pady=10)
        for t,c in (("SAVE",self.save_settings),("SCAN BLUETOOTH",self.scan),("CONNECT",self.connect_printer),("TEST PRINT",self.test_print)):ttk.Button(b,text=t,command=c).pack(side="left",padx=3)
        self.pstatus=tk.StringVar(value="Printer not connected");ttk.Label(f,textvariable=self.pstatus).pack(anchor="w")
    def save_settings(self):
        try:
            if float(self.sv["tax_rate"].get())<0:raise ValueError("Tax cannot be negative.")
            self.db.save_settings({k:v.get() for k,v in self.sv.items()},self.user["id"]);self.cfg=self.db.settings();self.start_printer();messagebox.showinfo("Settings","Saved.")
        except Exception as e:messagebox.showerror("Settings",str(e))
    def scan(self):
        w=tk.Toplevel(self);w.title("Bluetooth Devices");w.geometry("700x380");t=self.tree(w,["Name","MAC","Port"])
        for x in BluetoothPrinter.discover():t.insert("","end",values=(x.get("name",""),x.get("mac",""),x.get("port","")))
        def use():
            s=t.selection()
            if s:
                v=t.item(s[0],"values");self.sv["printer_name"].set(v[0]);self.sv["printer_bluetooth_mac"].set(v[1]);self.save_settings();w.destroy()
        ttk.Button(w,text="USE SELECTED",command=use).pack(fill="x",padx=10,pady=8)
    def start_printer(self):
        try:
            if self.printer:self.printer.disconnect()
            self.printer=BluetoothPrinter(self.cfg.get("printer_bluetooth_mac",""),self.cfg.get("printer_name",""),self.cfg.get("printer_port",""),self.cfg.get("printer_channel","1"));self.printer.auto_reconnect(lambda ok:self.after(0,lambda:self.pstatus.set("Printer connected" if ok else "Printer disconnected")))
        except Exception:pass
    def connect_printer(self):self.pstatus.set("Printer connected" if self.printer and self.printer.connect() else "Printer connection failed")
    def test_print(self):
        if not self.printer or not self.printer.test_print(self.cfg["store_name"]):messagebox.showerror("Printer","Pair printer with the OS first and configure MAC/COM.")
        else:self.pstatus.set("Test print sent")
    def ask(self,title,default=""):
        w=tk.Toplevel(self);w.title(title);v=tk.StringVar(value=default);ttk.Label(w,text=title).pack(padx=20,pady=10);ttk.Entry(w,textvariable=v).pack(padx=20);out=[];ttk.Button(w,text="OK",command=lambda:(out.append(v.get()),w.destroy())).pack(pady=10);w.grab_set();self.wait_window(w);return out[0] if out else default
    def ask_choice(self,title,values,default):
        w=tk.Toplevel(self);w.title(title);v=tk.StringVar(value=default);ttk.Label(w,text=title).pack(padx=20,pady=10);ttk.Combobox(w,textvariable=v,values=values,state="readonly").pack(padx=20);out=[];ttk.Button(w,text="OK",command=lambda:(out.append(v.get()),w.destroy())).pack(pady=10);w.grab_set();self.wait_window(w);return out[0] if out else default
    def close(self):
        try:self.printer.disconnect()
        except Exception:pass
        self.db.close();self.destroy()

if __name__=="__main__":Login().mainloop()
