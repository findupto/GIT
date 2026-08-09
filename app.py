import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from database import Database
from modules.services import create_sale, create_purchase
from modules.import_export import export_products, import_products
from modules.printer import BluetoothPrinter

class Login(tk.Tk):
    def __init__(self):
        super().__init__(); self.db=Database(); self.title('MK Pizza & Ice Bar - Login'); self.geometry('420x300'); self.resizable(False,False)
        f=ttk.Frame(self,padding=30); f.pack(fill='both',expand=True)
        ttk.Label(f,text='MK Pizza & Ice Bar',font=('Arial',22,'bold')).pack(pady=10); ttk.Label(f,text='Professional POS').pack(pady=(0,18))
        self.u=tk.StringVar(value='admin'); self.p=tk.StringVar(value='0099')
        for t,v,show in [('Username',self.u,''),('Password',self.p,'*')]: ttk.Label(f,text=t).pack(anchor='w'); ttk.Entry(f,textvariable=v,show=show).pack(fill='x',pady=(2,10))
        ttk.Button(f,text='LOGIN',command=self.login).pack(fill='x',ipady=7); ttk.Label(f,text='Default: admin / 0099 | owner / 0099').pack(pady=12); self.protocol('WM_DELETE_WINDOW',self.close)
    def login(self):
        row=self.db.login(self.u.get().strip(),self.p.get())
        if not row:return messagebox.showerror('Login Failed','Invalid username or password.')
        self.withdraw(); POSApp(row,self.db).mainloop()
    def close(self): self.db.close(); self.destroy()

class POSApp(tk.Toplevel):
    def __init__(self,user,db):
        super().__init__(); self.user=user; self.db=db; self.cfg=db.settings(); self.cart=[]; self.title(self.cfg['store_name']); self.geometry('1400x820'); self.minsize(1150,700); self.printer=None; self.protocol('WM_DELETE_WINDOW',self.close); self.build(); self.refresh_all(); self.start_printer()
    def money(self,x): return f"{self.cfg.get('currency','Rs.')} {float(x):,.2f}"
    def tree(self,p,cols):
        t=ttk.Treeview(p,columns=cols,show='headings')
        for c in cols:t.heading(c,text=c);t.column(c,width=120,anchor='center')
        t.pack(fill='both',expand=True); return t
    def build(self):
        top=ttk.Frame(self,padding=8);top.pack(fill='x');ttk.Label(top,text=self.cfg['store_name'],font=('Arial',20,'bold')).pack(side='left');ttk.Label(top,text=f" | {self.user['username']} ({self.user['role']})").pack(side='left');ttk.Button(top,text='Refresh',command=self.refresh_all).pack(side='right');ttk.Button(top,text='Logout',command=self.close).pack(side='right',padx=5)
        self.nb=ttk.Notebook(self);self.nb.pack(fill='both',expand=True,padx=8,pady=(0,8));self.frames={}
        for name,fn in [('Dashboard',self.dashboard_tab),('POS',self.pos_tab),('Products',self.products_tab),('Customers',self.customers_tab),('Suppliers',self.suppliers_tab),('Purchases',self.purchases_tab),('Expenses',self.expenses_tab),('Cash & Day',self.cash_tab),('Sales',self.sales_tab),('Reports',self.reports_tab),('Settings',self.settings_tab)]:
            f=ttk.Frame(self.nb,padding=8);self.nb.add(f,text=name);self.frames[name]=f;fn(f)
        if self.user['role'].lower() not in ('admin','owner'):self.nb.tab(self.frames['Settings'],state='disabled')
    def refresh_all(self):
        for fn in ('refresh_dashboard','refresh_products','refresh_customers','refresh_suppliers','refresh_sales','refresh_cash','refresh_expenses'):
            if hasattr(self,fn):
                try:getattr(self,fn)()
                except Exception:pass
    def dashboard_tab(self,f):
        self.dv=[tk.StringVar(value='0') for _ in range(5)];cards=ttk.Frame(f);cards.pack(fill='x')
        for i,t in enumerate(['Sales Today','Orders','Gross Profit','Expenses','Low Stock']):
            c=ttk.LabelFrame(cards,text=t,padding=15);c.grid(row=0,column=i,sticky='nsew',padx=4);cards.columnconfigure(i,weight=1);ttk.Label(c,textvariable=self.dv[i],font=('Arial',17,'bold')).pack()
        ttk.Label(f,text='Business Day',font=('Arial',13,'bold')).pack(anchor='w',pady=(18,5));self.day_info=tk.StringVar();ttk.Label(f,textvariable=self.day_info).pack(anchor='w');self.top=self.tree(f,['Product','Qty','Revenue'])
    def refresh_dashboard(self):
        if not hasattr(self,'dv'):return
        d=self.db.business_date();r=self.db.report(d,d);s=r[0];self.dv[0].set(self.money(s['sales']));self.dv[1].set(s['orders']);self.dv[2].set(self.money(r[3]));self.dv[3].set(self.money(r[2]));low=self.db.conn.execute('SELECT COUNT(*) n FROM products WHERE active=1 AND stock<=reorder_level').fetchone()['n'];self.dv[4].set(low);b=self.db.current_business_day();self.day_info.set(f"{d} | "+(f"OPEN • Opening cash {self.money(b['opening_cash'])}" if b else 'NOT OPEN'))
        for x in self.top.get_children():self.top.delete(x)
        for q in self.db.conn.execute("SELECT item_name,SUM(qty) qty,SUM(amount) revenue FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE date(o.created_at)=? GROUP BY item_name ORDER BY qty DESC LIMIT 10",(d,)).fetchall():self.top.insert('','end',values=(q['item_name'],q['qty'],self.money(q['revenue'])))
    def pos_tab(self,f):
        left=ttk.Frame(f);left.pack(side='left',fill='both',expand=True,padx=(0,8));right=ttk.LabelFrame(f,text='Current Order',padding=8);right.pack(side='right',fill='both',expand=True)
        bar=ttk.Frame(left);bar.pack(fill='x');self.ps=tk.StringVar();ttk.Entry(bar,textvariable=self.ps).pack(side='left',fill='x',expand=True);ttk.Button(bar,text='Search',command=self.refresh_pos).pack(side='left',padx=4);self.pc=tk.StringVar(value='All');self.pmap={'All':None};[self.pmap.update({c['name']:c['id']}) for c in self.db.categories()];self.pcb=ttk.Combobox(bar,textvariable=self.pc,values=list(self.pmap),state='readonly',width=18);self.pcb.pack(side='left');self.pcb.bind('<<ComboboxSelected>>',lambda e:self.refresh_pos());self.pt=self.tree(left,['SKU','Category','Product','Price','Stock']);self.pt.bind('<Double-1>',lambda e:self.add_pos());ttk.Button(left,text='ADD SELECTED',command=self.add_pos).pack(fill='x',pady=5)
        self.ct=self.tree(right,['Item','Qty','Price','Amount']);a=ttk.Frame(right);a.pack(fill='x',pady=5)
        for txt,cmd in [('+ Qty',lambda:self.change_qty(1)),('- Qty',lambda:self.change_qty(-1)),('Remove',self.remove_pos),('Clear',self.clear_cart)]:ttk.Button(a,text=txt,command=cmd).pack(side='left',fill='x',expand=True,padx=2)
        self.ot=tk.StringVar(value='Takeaway');self.pm=tk.StringVar(value='Cash');self.dis=tk.StringVar(value='0');self.paid=tk.StringVar(value='0');self.cust=tk.StringVar(value='Walk-in');form=ttk.Frame(right);form.pack(fill='x',pady=5)
        for label,var,vals in [('Type',self.ot,['Dine-in','Takeaway','Delivery']),('Payment',self.pm,['Cash','Card','Mobile Wallet'])]:ttk.Label(form,text=label).pack(side='left');ttk.Combobox(form,textvariable=var,values=vals,state='readonly',width=13).pack(side='left',padx=4)
        ttk.Label(form,text='Customer').pack(side='left');self.cb=ttk.Combobox(form,textvariable=self.cust,state='readonly',width=18);self.cb.pack(side='left',padx=4);self.load_customer_choices();ttk.Label(form,text='Discount').pack(side='left');ttk.Entry(form,textvariable=self.dis,width=8).pack(side='left',padx=3);ttk.Label(form,text='Paid').pack(side='left');ttk.Entry(form,textvariable=self.paid,width=9).pack(side='left',padx=3)
        self.total=ttk.Label(right,text='',font=('Arial',16,'bold'));self.total.pack(anchor='e',pady=8);ttk.Button(right,text='COMPLETE SALE + RECEIPT',command=self.complete_sale).pack(fill='x',ipady=8)
    def load_customer_choices(self):
        if hasattr(self,'cb'):self.custmap={'Walk-in':None};[self.custmap.update({f"{c['name']} ({c['phone'] or ''})":c['id']}) for c in self.db.customers()];self.cb['values']=list(self.custmap)
    def refresh_pos(self):
        for x in self.pt.get_children():self.pt.delete(x)
        for p in self.db.products(self.ps.get(),self.pmap.get(self.pc.get())):self.pt.insert('','end',iid=str(p['id']),values=(p['sku'],p['category'],p['name'],self.money(p['price']),p['stock']))
    def add_pos(self):
        s=self.pt.selection();
        if not s:return
        p=self.db.conn.execute('SELECT * FROM products WHERE id=?',(s[0],)).fetchone()
        if p['stock']<=0:return messagebox.showwarning('Stock','Product is out of stock.')
        for i in self.cart:
            if i['product_id']==p['id']:i['qty']+=1;break
        else:self.cart.append({'product_id':p['id'],'name':p['name'],'price':p['price'],'cost':p['cost'],'qty':1})
        self.refresh_cart()
    def refresh_cart(self):
        for x in self.ct.get_children():self.ct.delete(x)
        sub=sum(i['qty']*i['price'] for i in self.cart)
        for i in self.cart:self.ct.insert('','end',values=(i['name'],i['qty'],self.money(i['price']),self.money(i['qty']*i['price'])))
        try:d=max(0,min(float(self.dis.get() or 0),sub))
        except:d=0
        tax=(sub-d)*float(self.cfg['tax_rate'])/100;self.total.config(text=f"Subtotal {self.money(sub)} | Discount {self.money(d)} | Tax {self.money(tax)} | TOTAL {self.money(sub-d+tax)}")
    def change_qty(self,n):
        s=self.ct.selection();
        if not s:return
        i=self.cart[self.ct.index(s[0])];i['qty']+=n
        if i['qty']<=0:self.cart.remove(i)
        self.refresh_cart()
    def remove_pos(self):
        s=self.ct.selection();
        if s:self.cart.pop(self.ct.index(s[0]));self.refresh_cart()
    def clear_cart(self):self.cart=[];self.paid.set('0');self.dis.set('0');self.refresh_cart()
    def complete_sale(self):
        if not self.cart:return messagebox.showwarning('Order','Add products first.')
        try:
            if not self.db.current_business_day():self.db.open_business_day(0)
            cid=self.custmap.get(self.cust.get());r=create_sale(self.db,self.user['id'],self.cart,float(self.dis.get() or 0),float(self.cfg['tax_rate']),self.pm.get(),float(self.paid.get() or 0),self.ot.get(),cid);self.receipt(r[0]);self.clear_cart();self.refresh_all()
        except Exception as e:messagebox.showerror('Sale Error',str(e))
    def receipt(self,oid):
        o=self.db.conn.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone();items=self.db.order_items(oid);lines=[self.cfg['store_name'],self.cfg['store_address'],self.cfg['store_phone'],'='*42,f"Order {o['order_no']}  {o['created_at']}",'-'*42]+[f"{i['item_name']} x{i['qty']}  {self.money(i['amount'])}" for i in items]+['-'*42,f"Subtotal: {self.money(o['subtotal'])}",f"Discount: {self.money(o['discount'])}",f"Tax: {self.money(o['tax'])}",f"TOTAL: {self.money(o['total'])}",f"Paid: {self.money(o['paid'])}",f"Change: {self.money(o['change_amount'])}",f"Payment: {o['payment_method']}",'='*42,self.cfg['receipt_footer']];text='\n'.join(lines);open(f"receipt_{o['order_no']}.txt",'w',encoding='utf-8').write(text);messagebox.showinfo('Receipt',text)
        if self.printer and self.printer.connected:self.printer.send(('\x1b@'+text+'\n\x1dV\x00').encode('utf-8','replace'))
    def products_tab(self,f):
        b=ttk.Frame(f);b.pack(fill='x');ttk.Button(b,text='Add',command=self.product_dialog).pack(side='left');ttk.Button(b,text='Edit',command=self.edit_product).pack(side='left',padx=3);ttk.Button(b,text='Delete',command=self.delete_product).pack(side='left');ttk.Button(b,text='Delete ALL',command=self.delete_all).pack(side='left',padx=3);ttk.Button(b,text='Import CSV',command=self.import_menu).pack(side='left');ttk.Button(b,text='Export CSV',command=self.export_menu).pack(side='left',padx=3);self.psearch=tk.StringVar();ttk.Entry(b,textvariable=self.psearch).pack(side='right');ttk.Button(b,text='Filter',command=self.refresh_products).pack(side='right',padx=3);self.padmin=self.tree(f,['ID','SKU','Category','Product','Price','Cost','Stock','Reorder']);self.padmin.bind('<Double-1>',lambda e:self.product_history())
    def refresh_products(self):
        if not hasattr(self,'padmin'):return
        for x in self.padmin.get_children():self.padmin.delete(x)
        for p in self.db.products(self.psearch.get()):self.padmin.insert('','end',iid=str(p['id']),values=(p['id'],p['sku'],p['category'],p['name'],self.money(p['price']),self.money(p['cost']),p['stock'],p['reorder_level']))
        if hasattr(self,'pt'):self.refresh_pos()
    def product_dialog(self,pid=None):
        p=self.db.conn.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone() if pid else None;w=tk.Toplevel(self);w.title('Product');w.geometry('430x470');vs={k:tk.StringVar(value=str(p[k]) if p else '') for k in ['name','sku','price','cost','stock','reorder_level']};cats=self.db.categories();cm={c['name']:c['id'] for c in cats};cv=tk.StringVar(value=(self.db.conn.execute('SELECT name FROM categories WHERE id=?',(p['category_id'],)).fetchone()['name'] if p else cats[0]['name']))
        for lab,key in [('Name','name'),('SKU','sku'),('Price','price'),('Cost','cost'),('Stock','stock'),('Reorder','reorder_level')]:ttk.Label(w,text=lab).pack(anchor='w',padx=20,pady=(8,1));ttk.Entry(w,textvariable=vs[key]).pack(fill='x',padx=20)
        ttk.Label(w,text='Category').pack(anchor='w',padx=20,pady=(8,1));ttk.Combobox(w,textvariable=cv,values=list(cm),state='readonly').pack(fill='x',padx=20)
        def save():
            try:self.db.save_product(pid,cm[cv.get()],vs['name'].get(),vs['sku'].get(),float(vs['price'].get()),float(vs['cost'].get()),float(vs['stock'].get()),float(vs['reorder_level'].get()),self.user['id']);w.destroy();self.refresh_products()
            except Exception as e:messagebox.showerror('Product',str(e),parent=w)
        ttk.Button(w,text='SAVE',command=save).pack(fill='x',padx=20,pady=20)
    def edit_product(self):
        s=self.padmin.selection();
        if s:self.product_dialog(int(s[0]))
    def delete_product(self):
        s=self.padmin.selection();
        if s and messagebox.askyesno('Delete','Deactivate selected product?'):self.db.delete_product(int(s[0]));self.refresh_products()
    def delete_all(self):
        if messagebox.askyesno('Delete ALL','Deactivate every product?'):self.db.delete_all_products();self.refresh_products()
    def product_history(self):
        s=self.padmin.selection();
        if not s:return
        w=tk.Toplevel(self);w.title('Product History');w.geometry('700x450');t=self.tree(w,['Date','Type','Qty','Note']);[t.insert('','end',values=(r['created_at'],r['movement_type'],r['qty'],r['note'])) for r in self.db.product_history(int(s[0]))]
    def import_menu(self):
        p=filedialog.askopenfilename(filetypes=[('CSV','*.csv')]);
        if not p:return
        try:n=import_products(self.db,p,False);messagebox.showinfo('Import',f'{n} products imported/updated.');self.refresh_products()
        except Exception as e:messagebox.showerror('Import',str(e))
    def export_menu(self):
        p=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')]);
        if p:
            try:export_products(self.db,p);messagebox.showinfo('Export','Menu exported successfully.')
            except Exception as e:messagebox.showerror('Export',str(e))
    def customers_tab(self,f):
        b=ttk.Frame(f);b.pack(fill='x');ttk.Button(b,text='Add Customer',command=lambda:self.party_dialog('customer')).pack(side='left');self.cs=tk.StringVar();ttk.Entry(b,textvariable=self.cs).pack(side='right');ttk.Button(b,text='Filter',command=self.refresh_customers).pack(side='right',padx=3);self.ctree=self.tree(f,['ID','Name','Phone','Email','Points','Opening']);self.ctree.bind('<Double-1>',lambda e:self.customer_history())
    def refresh_customers(self):
        if not hasattr(self,'ctree'):return
        for x in self.ctree.get_children():self.ctree.delete(x)
        for c in self.db.customers(self.cs.get() if hasattr(self,'cs') else ''):self.ctree.insert('','end',iid=str(c['id']),values=(c['id'],c['name'],c['phone'] or '',c['email'] or '',c['points'],self.money(c['opening_balance'])))
        if hasattr(self,'cb'):self.load_customer_choices()
    def customer_history(self):self.history_window('Customer',self.ctree,self.db.customer_history,['Date','Type','Reference','Debit','Credit','Note'])
    def suppliers_tab(self,f):
        b=ttk.Frame(f);b.pack(fill='x');ttk.Button(b,text='Add Supplier',command=lambda:self.party_dialog('supplier')).pack(side='left');self.ss=tk.StringVar();ttk.Entry(b,textvariable=self.ss).pack(side='right');ttk.Button(b,text='Filter',command=self.refresh_suppliers).pack(side='right',padx=3);self.stree=self.tree(f,['ID','Name','Phone','Email','Opening']);self.stree.bind('<Double-1>',lambda e:self.supplier_history())
    def refresh_suppliers(self):
        if not hasattr(self,'stree'):return
        for x in self.stree.get_children():self.stree.delete(x)
        for s in self.db.suppliers(self.ss.get() if hasattr(self,'ss') else ''):self.stree.insert('','end',iid=str(s['id']),values=(s['id'],s['name'],s['phone'] or '',s['email'] or '',self.money(s['opening_balance'])))
    def supplier_history(self):self.history_window('Supplier',self.stree,self.db.supplier_history,['Date','Type','Reference','Debit','Credit','Note'])
    def history_window(self,title,tree,fn,cols):
        s=tree.selection();
        if not s:return
        w=tk.Toplevel(self);w.title(title+' History');w.geometry('850x450');t=self.tree(w,cols)
        for r in fn(int(s[0])):t.insert('','end',values=tuple(r[k.lower().replace(' ','_')] if k.lower().replace(' ','_') in r.keys() else '' for k in cols))
    def party_dialog(self,kind):
        w=tk.Toplevel(self);w.title('New '+kind.title());w.geometry('400x330');vs=[tk.StringVar() for _ in range(4)]
        for lab,v in zip(['Name','Phone','Email','Opening Balance'],vs):ttk.Label(w,text=lab).pack(anchor='w',padx=20,pady=(8,1));ttk.Entry(w,textvariable=v).pack(fill='x',padx=20)
        def save():
            try:
                if kind=='customer':self.db.save_customer(vs[0].get(),vs[1].get(),vs[2].get(),float(vs[3].get() or 0));self.refresh_customers()
                else:self.db.save_supplier(vs[0].get(),vs[1].get(),vs[2].get(),float(vs[3].get() or 0));self.refresh_suppliers()
                w.destroy()
            except Exception as e:messagebox.showerror(kind.title(),str(e),parent=w)
        ttk.Button(w,text='SAVE',command=save).pack(fill='x',padx=20,pady=20)
    def purchases_tab(self,f):
        ttk.Label(f,text='Purchase entry').pack(anchor='w');self.purchase_supplier=tk.StringVar();self.purchase_product=tk.StringVar();self.purchase_qty=tk.StringVar(value='1');self.purchase_cost=tk.StringVar(value='0');self.purchase_paid=tk.StringVar(value='0');self.purchase_payment=tk.StringVar(value='Cash');self.purchase_items=[];form=ttk.Frame(f);form.pack(fill='x',pady=8);self.smap={f"{s['name']} ({s['phone'] or ''})":s['id'] for s in self.db.suppliers()};ttk.Label(form,text='Supplier').pack(side='left');ttk.Combobox(form,textvariable=self.purchase_supplier,values=list(self.smap),state='readonly',width=25).pack(side='left',padx=4);self.ppmap={f"{p['name']} ({p['sku']})":p['id'] for p in self.db.products()};ttk.Label(form,text='Product').pack(side='left');ttk.Combobox(form,textvariable=self.purchase_product,values=list(self.ppmap),state='readonly',width=25).pack(side='left',padx=4);ttk.Label(form,text='Qty').pack(side='left');ttk.Entry(form,textvariable=self.purchase_qty,width=7).pack(side='left');ttk.Label(form,text='Cost').pack(side='left');ttk.Entry(form,textvariable=self.purchase_cost,width=9).pack(side='left');ttk.Button(form,text='Add',command=self.add_purchase_item).pack(side='left',padx=5);self.purtree=self.tree(f,['Product','Qty','Cost','Amount']);self.pur_total=tk.StringVar(value='0');ttk.Label(f,textvariable=self.pur_total,font=('Arial',14,'bold')).pack(anchor='e');ttk.Button(f,text='SAVE PURCHASE',command=self.save_purchase).pack(fill='x',pady=8)
    def add_purchase_item(self):
        pid=self.ppmap.get(self.purchase_product.get());
        if not pid:return
        p=self.db.conn.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone();self.purchase_items.append({'product_id':pid,'name':p['name'],'qty':float(self.purchase_qty.get()),'cost':float(self.purchase_cost.get() or p['cost'])});self.refresh_purchase()
    def refresh_purchase(self):
        for x in self.purtree.get_children():self.purtree.delete(x)
        total=0
        for i in self.purchase_items:amt=i['qty']*i['cost'];total+=amt;self.purtree.insert('','end',values=(i['name'],i['qty'],self.money(i['cost']),self.money(amt)))
        self.pur_total.set('Total: '+self.money(total))
    def save_purchase(self):
        try:
            r=create_purchase(self.db,self.user['id'],self.smap[self.purchase_supplier.get()],self.purchase_items,float(self.purchase_paid.get() or 0),self.purchase_payment.get());messagebox.showinfo('Purchase',f'{r[1]} saved. Due: {self.money(r[3])}');self.purchase_items=[];self.refresh_purchase();self.refresh_all()
        except Exception as e:messagebox.showerror('Purchase',str(e))
    def expenses_tab(self,f):
        vs=[tk.StringVar() for _ in range(4)];opts=[['Rent','Utilities','Salary','Supplies','Other'],None,None,['Cash','Card','Mobile Wallet']]
        for lab,v,o in zip(['Category','Description','Amount','Payment'],vs,opts):ttk.Label(f,text=lab).pack(anchor='w');(ttk.Combobox(f,textvariable=v,values=o,state='readonly') if o else ttk.Entry(f,textvariable=v)).pack(fill='x',pady=(1,8))
        vs[3].set('Cash');ttk.Button(f,text='ADD EXPENSE',command=lambda:self.add_exp(vs)).pack(fill='x');self.expt=self.tree(f,['Date','Category','Description','Amount','Payment'])
    def add_exp(self,vs):
        try:self.db.add_expense(vs[0].get(),vs[1].get(),float(vs[2].get()),vs[3].get(),self.user['id']);self.refresh_expenses()
        except Exception as e:messagebox.showerror('Expense',str(e))
    def refresh_expenses(self):
        if not hasattr(self,'expt'):return
        for x in self.expt.get_children():self.expt.delete(x)
        for r in self.db.conn.execute('SELECT * FROM expenses ORDER BY id DESC LIMIT 300'):self.expt.insert('','end',values=(r['created_at'],r['category'],r['description'],self.money(r['amount']),r['payment_method']))
    def cash_tab(self,f):
        self.cash_info=tk.StringVar();ttk.Label(f,textvariable=self.cash_info,font=('Arial',14,'bold')).pack(anchor='w');b=ttk.Frame(f);b.pack(fill='x',pady=10);ttk.Button(b,text='Open Business Day',command=self.open_day).pack(side='left');ttk.Button(b,text='Cash In',command=lambda:self.cash_dialog(1)).pack(side='left',padx=5);ttk.Button(b,text='Cash Out',command=lambda:self.cash_dialog(-1)).pack(side='left');ttk.Button(b,text='Close Day / Reconcile',command=self.close_day).pack(side='left',padx=5);self.casht=self.tree(f,['Date','Type','Amount','Note','Reference','Payment'])
    def refresh_cash(self):
        if not hasattr(self,'casht'):return
        b=self.db.current_business_day();self.cash_info.set('No business day open.' if not b else f"Business day {b['business_date']} | Opening {self.money(b['opening_cash'])} | Status {b['status']} | Variance {self.money(b['variance'] or 0)}");[self.casht.delete(x) for x in self.casht.get_children()]
        if b:
            for r in self.db.cash_flow(b['id']):self.casht.insert('','end',values=(r['created_at'],r['type'],self.money(r['amount']),r['note'],r['reference'],r['payment_method']))
    def open_day(self):
        try:self.db.open_business_day(float(self.ask('Opening cash','0')));self.refresh_all()
        except Exception as e:messagebox.showerror('Business Day',str(e))
    def cash_dialog(self,sign):
        try:self.db.cash(sign*float(self.ask('Cash amount','0')),'CASH_IN' if sign>0 else 'CASH_OUT',self.ask('Note',''),self.user['id']);self.refresh_cash()
        except Exception as e:messagebox.showerror('Cash',str(e))
    def close_day(self):
        try:expected,var=self.db.close_business_day(float(self.ask('Actual cash counted','0')),self.ask('Closing note',''));messagebox.showinfo('Reconciliation',f'Expected: {self.money(expected)}\nVariance: {self.money(var)}');self.refresh_all()
        except Exception as e:messagebox.showerror('Close Day',str(e))
    def ask(self,title,default=''):
        w=tk.Toplevel(self);w.title(title);v=tk.StringVar(value=default);ttk.Label(w,text=title).pack(padx=20,pady=10);ttk.Entry(w,textvariable=v).pack(padx=20);out=[];ttk.Button(w,text='OK',command=lambda:(out.append(v.get()),w.destroy())).pack(pady=10);w.grab_set();self.wait_window(w);return out[0] if out else default
    def sales_tab(self,f):
        b=ttk.Frame(f);b.pack(fill='x');self.sfrom=tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'));self.sto=tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'));ttk.Label(b,text='From').pack(side='left');ttk.Entry(b,textvariable=self.sfrom,width=12).pack(side='left');ttk.Label(b,text='To').pack(side='left');ttk.Entry(b,textvariable=self.sto,width=12).pack(side='left');self.spay=tk.StringVar(value='All');ttk.Combobox(b,textvariable=self.spay,values=['All','Cash','Card','Mobile Wallet'],state='readonly',width=15).pack(side='left',padx=5);ttk.Button(b,text='FILTER',command=self.refresh_sales).pack(side='left');self.salest=self.tree(f,['Order','Date','Customer','Type','Payment','Subtotal','Discount','Tax','Total']);self.salest.bind('<Double-1>',lambda e:self.sale_detail())
    def refresh_sales(self):
        if not hasattr(self,'salest'):return
        for x in self.salest.get_children():self.salest.delete(x)
        pay=None if self.spay.get()=='All' else self.spay.get()
        for r in self.db.sales(self.sfrom.get(),self.sto.get(),payment=pay):self.salest.insert('','end',iid=str(r['id']),values=(r['order_no'],r['created_at'],r['customer'] or 'Walk-in',r['order_type'],r['payment_method'],self.money(r['subtotal']),self.money(r['discount']),self.money(r['tax']),self.money(r['total'])))
    def sale_detail(self):
        s=self.salest.selection();
        if not s:return
        w=tk.Toplevel(self);w.title('Sale Detail');w.geometry('700x450');t=self.tree(w,['Item','Qty','Price','Amount']);[t.insert('','end',values=(i['item_name'],i['qty'],self.money(i['price']),self.money(i['amount']))) for i in self.db.order_items(int(s[0]))]
    def reports_tab(self,f):
        b=ttk.Frame(f);b.pack(fill='x');self.rf=tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'));self.rt=tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'));ttk.Entry(b,textvariable=self.rf,width=12).pack(side='left');ttk.Entry(b,textvariable=self.rt,width=12).pack(side='left',padx=4);ttk.Button(b,text='RUN REPORT',command=self.run_report).pack(side='left');self.report_text=tk.StringVar();ttk.Label(f,textvariable=self.report_text,font=('Arial',14,'bold'),justify='left').pack(anchor='w',pady=15);self.flow=self.tree(f,['Date','Type','Amount','Note','Reference','Payment'])
    def run_report(self):
        r,c,e,g,n=self.db.report(self.rf.get(),self.rt.get());self.report_text.set(f"Orders: {r['orders']}\nSales: {self.money(r['sales'])}\nCOGS: {self.money(c)}\nGross Profit: {self.money(g)}\nExpenses: {self.money(e)}\nNET PROFIT / LOSS: {self.money(n)}\nTax: {self.money(r['tax'])} | Discounts: {self.money(r['discounts'])}");[self.flow.delete(x) for x in self.flow.get_children()]
        for q in self.db.conn.execute('SELECT * FROM cash_transactions WHERE date(created_at) BETWEEN ? AND ? ORDER BY id',(self.rf.get(),self.rt.get())):self.flow.insert('','end',values=(q['created_at'],q['type'],self.money(q['amount']),q['note'],q['reference'],q['payment_method']))
    def settings_tab(self,f):
        keys=['store_name','store_address','store_phone','currency','tax_rate','business_day_start','business_day_end','printer_bluetooth_mac','printer_name','printer_port','printer_channel','receipt_footer'];self.setvars={k:tk.StringVar(value=self.cfg.get(k,'')) for k in keys};grid=ttk.Frame(f);grid.pack(fill='x')
        labels=[('Business','store_name'),('Address','store_address'),('Phone','store_phone'),('Currency','currency'),('Tax %','tax_rate'),('Business Day Start','business_day_start'),('Business Day End','business_day_end'),('Printer MAC','printer_bluetooth_mac'),('Printer Name','printer_name'),('Windows COM Port','printer_port'),('RFCOMM Channel','printer_channel'),('Receipt Footer','receipt_footer')]
        for i,(lab,k) in enumerate(labels):ttk.Label(grid,text=lab).grid(row=i,column=0,sticky='w',pady=3);ttk.Entry(grid,textvariable=self.setvars[k],width=65).grid(row=i,column=1,sticky='ew',pady=3)
        grid.columnconfigure(1,weight=1);b=ttk.Frame(f);b.pack(fill='x',pady=10);ttk.Button(b,text='SAVE SETTINGS',command=self.save_settings).pack(side='left');ttk.Button(b,text='SCAN BLUETOOTH',command=self.scan_printers).pack(side='left',padx=5);ttk.Button(b,text='CONNECT',command=self.connect_printer).pack(side='left');ttk.Button(b,text='TEST PRINT',command=self.test_print).pack(side='left',padx=5);self.printer_status=tk.StringVar(value='Printer not connected');ttk.Label(f,textvariable=self.printer_status).pack(anchor='w')
    def save_settings(self):
        try:self.db.save_settings({k:v.get() for k,v in self.setvars.items()});self.cfg=self.db.settings();self.title(self.cfg['store_name']);messagebox.showinfo('Settings','Settings saved.');self.start_printer()
        except Exception as e:messagebox.showerror('Settings',str(e))
    def scan_printers(self):
        rows=BluetoothPrinter.discover();w=tk.Toplevel(self);w.title('Bluetooth Printers');w.geometry('650x350');t=self.tree(w,['Name','MAC','Port']);
        for r in rows:t.insert('','end',values=(r['name'],r['mac'],r['port']))
        def choose():
            s=t.selection();
            if s:v=t.item(s[0],'values');self.setvars['printer_name'].set(v[0]);self.setvars['printer_bluetooth_mac'].set(v[1]);self.save_settings();w.destroy()
        ttk.Button(w,text='USE SELECTED',command=choose).pack(fill='x',padx=10,pady=8)
    def start_printer(self):
        try:
            if self.printer:self.printer.disconnect()
            self.printer=BluetoothPrinter(self.cfg.get('printer_bluetooth_mac',''),self.cfg.get('printer_name',''),self.cfg.get('printer_port',''),self.cfg.get('printer_channel','1'));self.printer.auto_reconnect(lambda ok:self.after(0,lambda:self.printer_status.set('Printer connected' if ok else 'Printer disconnected')))
        except Exception:pass
    def connect_printer(self):
        if self.printer and self.printer.connect():self.printer_status.set('Printer connected')
        else:self.printer_status.set('Printer connection failed')
    def test_print(self):
        if self.printer and self.printer.test_print(self.cfg['store_name']):self.printer_status.set('Test print sent')
        else:messagebox.showerror('Printer','Could not connect. Pair the printer first and set its MAC or Windows COM port.')
    def close(self):
        try:self.printer.disconnect()
        except Exception:pass
        self.db.close();self.destroy()

if __name__=='__main__':Login().mainloop()
