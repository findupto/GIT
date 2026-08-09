import csv
import tkinter as tk
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
        super().__init__(); self.db=Database(); self.title('MK Pizza & Ice Bar - Login'); self.geometry('430x310'); self.resizable(False,False)
        f=ttk.Frame(self,padding=28); f.pack(fill='both',expand=True)
        ttk.Label(f,text='MK Pizza & Ice Bar',font=('Arial',22,'bold')).pack(pady=8); ttk.Label(f,text='Advanced POS').pack(pady=(0,16))
        self.u=tk.StringVar(value='admin'); self.p=tk.StringVar(value='0099')
        for label,var,show in (('Username',self.u,''),('Password',self.p,'*')):
            ttk.Label(f,text=label).pack(anchor='w'); ttk.Entry(f,textvariable=var,show=show).pack(fill='x',pady=(2,8))
        ttk.Button(f,text='LOGIN',command=self.login).pack(fill='x',ipady=7); ttk.Label(f,text='Default: admin / 0099 | owner / 0099').pack(pady=12); self.protocol('WM_DELETE_WINDOW',self.close)
    def login(self):
        row=self.db.login(self.u.get().strip(),self.p.get())
        if not row: return messagebox.showerror('Login Failed','Invalid username or password.')
        self.withdraw(); POSApp(row,self.db).mainloop()
    def close(self): self.db.close(); self.destroy()


class POSApp(tk.Toplevel):
    def __init__(self,user,db):
        super().__init__(); self.user=user; self.db=db; self.cfg=db.settings(); self.cart=[]; self.purchase_items=[]; self.printer=None
        self.title(self.cfg['store_name']); self.geometry('1500x900'); self.minsize(1200,720); self.protocol('WM_DELETE_WINDOW',self.close)
        self.build(); self.refresh_all(); self.start_printer()
    def money(self,x): return f"{self.cfg.get('currency','Rs.')} {float(x):,.2f}"
    def tree(self,parent,cols):
        t=ttk.Treeview(parent,columns=cols,show='headings')
        for c in cols: t.heading(c,text=c); t.column(c,width=max(90,min(180,900//max(1,len(cols)))),anchor='center')
        t.pack(fill='both',expand=True); return t
    def build(self):
        top=ttk.Frame(self,padding=8); top.pack(fill='x'); ttk.Label(top,text=self.cfg['store_name'],font=('Arial',20,'bold')).pack(side='left'); ttk.Label(top,text=f"  |  {self.user['username']} ({self.user['role']})").pack(side='left'); ttk.Button(top,text='Refresh',command=self.refresh_all).pack(side='right'); ttk.Button(top,text='Logout',command=self.close).pack(side='right',padx=5)
        self.nb=ttk.Notebook(self); self.nb.pack(fill='both',expand=True,padx=8,pady=(0,8)); self.frames={}
        tabs=[('Dashboard',self.dashboard_tab),('POS',self.pos_tab),('Products',self.products_tab),('Customers',self.customers_tab),('Suppliers',self.suppliers_tab),('Purchases',self.purchases_tab),('Expenses',self.expenses_tab),('Cash & Day',self.cash_tab),('Sales',self.sales_tab),('Accounting',self.accounting_tab),('Reports',self.reports_tab),('Settings',self.settings_tab)]
        for name,fn in tabs:
            f=ttk.Frame(self.nb,padding=8); self.nb.add(f,text=name); self.frames[name]=f; fn(f)
        if self.user['role'].lower() not in ('admin','owner'): self.nb.tab(self.frames['Settings'],state='disabled')
    def refresh_all(self):
        for n in ('dashboard','products','customers','suppliers','sales','cash','expenses','accounting'):
            fn=getattr(self,f'refresh_{n}',None)
            if fn:
                try: fn()
                except Exception: pass

    def dashboard_tab(self,f):
        self.dv=[tk.StringVar(value='0') for _ in range(7)]; cards=ttk.Frame(f); cards.pack(fill='x'); labels=['Sales','Orders','Gross Profit','Expenses','Net Profit','Customer Due','Supplier Due']
        for i,l in enumerate(labels):
            c=ttk.LabelFrame(cards,text=l,padding=12); c.grid(row=0,column=i,sticky='nsew',padx=3); cards.columnconfigure(i,weight=1); ttk.Label(c,textvariable=self.dv[i],font=('Arial',14,'bold')).pack()
        self.day_info=tk.StringVar(); ttk.Label(f,textvariable=self.day_info,font=('Arial',12,'bold')).pack(anchor='w',pady=12); self.top=self.tree(f,['Product','Qty','Revenue'])
    def refresh_dashboard(self):
        if not hasattr(self,'dv'): return
        d=self.db.business_date(); r,c,e,g,n=self.db.report(d,d); s=r
        cust=float(self.db.conn.execute('SELECT COALESCE(SUM(opening_balance),0)+COALESCE((SELECT SUM(debit-credit) FROM customer_transactions),0) x FROM customers').fetchone()['x'])
        supp=float(self.db.conn.execute('SELECT COALESCE(SUM(opening_balance),0)+COALESCE((SELECT SUM(debit-credit) FROM supplier_transactions),0) x FROM suppliers').fetchone()['x'])
        vals=[s['sales'],s['orders'],g,e,n,max(0,cust),max(0,supp)]
        for i,(v,x) in enumerate(zip(self.dv,vals)): v.set(str(x) if i==1 else self.money(x))
        b=self.db.current_business_day(); self.day_info.set(f"Business day: {d} | "+(f"OPEN | Opening cash {self.money(b['opening_cash'])}" if b else 'NOT OPEN'))
        for x in self.top.get_children(): self.top.delete(x)
        for q in self.db.conn.execute('SELECT item_name,SUM(qty) qty,SUM(amount) revenue FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE date(o.created_at)=? GROUP BY item_name ORDER BY qty DESC LIMIT 15',(d,)): self.top.insert('','end',values=(q['item_name'],q['qty'],self.money(q['revenue'])))

    def pos_tab(self,f):
        left=ttk.Frame(f); left.pack(side='left',fill='both',expand=True,padx=(0,8)); right=ttk.LabelFrame(f,text='Current Order',padding=8); right.pack(side='right',fill='both',expand=True)
        bar=ttk.Frame(left); bar.pack(fill='x'); self.ps=tk.StringVar(); ttk.Entry(bar,textvariable=self.ps).pack(side='left',fill='x',expand=True); ttk.Button(bar,text='Search',command=self.refresh_pos).pack(side='left',padx=4)
        self.pc=tk.StringVar(value='All'); self.pmap={'All':None}; [self.pmap.update({c['name']:c['id']}) for c in self.db.categories()]; cb=ttk.Combobox(bar,textvariable=self.pc,values=list(self.pmap),state='readonly',width=18); cb.pack(side='left'); cb.bind('<<ComboboxSelected>>',lambda e:self.refresh_pos())
        self.pt=self.tree(left,['SKU','Category','Product','Price','Stock']); self.pt.bind('<Double-1>',lambda e:self.add_pos()); ttk.Button(left,text='ADD SELECTED',command=self.add_pos).pack(fill='x',pady=5)
        self.ct=self.tree(right,['Item','Qty','Price','Amount']); a=ttk.Frame(right); a.pack(fill='x',pady=5)
        for txt,cmd in [('+ Qty',lambda:self.change_qty(1)),('- Qty',lambda:self.change_qty(-1)),('Remove',self.remove_pos),('Clear',self.clear_cart)]: ttk.Button(a,text=txt,command=cmd).pack(side='left',fill='x',expand=True,padx=2)
        self.ot=tk.StringVar(value='Takeaway'); self.pm=tk.StringVar(value='Cash'); self.dis=tk.StringVar(value='0'); self.paid=tk.StringVar(value='0'); self.cust=tk.StringVar(value='Walk-in'); form=ttk.Frame(right); form.pack(fill='x',pady=5)
        for label,var,vals in [('Type',self.ot,['Dine-in','Takeaway','Delivery']),('Payment',self.pm,['Cash','Card','Mobile Wallet','Credit'])]: ttk.Label(form,text=label).pack(side='left'); ttk.Combobox(form,textvariable=var,values=vals,state='readonly',width=13).pack(side='left',padx=4)
        ttk.Label(form,text='Customer').pack(side='left'); self.cb=ttk.Combobox(form,textvariable=self.cust,state='readonly',width=18); self.cb.pack(side='left',padx=4); self.load_customer_choices(); ttk.Label(form,text='Discount').pack(side='left'); ttk.Entry(form,textvariable=self.dis,width=8).pack(side='left',padx=3); ttk.Label(form,text='Paid').pack(side='left'); ttk.Entry(form,textvariable=self.paid,width=9).pack(side='left',padx=3)
        self.total=ttk.Label(right,text='',font=('Arial',16,'bold')); self.total.pack(anchor='e',pady=8); ttk.Button(right,text='COMPLETE SALE + RECEIPT',command=self.complete_sale).pack(fill='x',ipady=8)
    def load_customer_choices(self):
        if hasattr(self,'cb'):
            self.custmap={'Walk-in':None}; [self.custmap.update({f"{c['name']} ({c['phone'] or ''})":c['id']}) for c in self.db.customers()]; self.cb['values']=list(self.custmap)
    def refresh_pos(self):
        for x in self.pt.get_children(): self.pt.delete(x)
        for p in self.db.products(self.ps.get(),self.pmap.get(self.pc.get())): self.pt.insert('','end',iid=str(p['id']),values=(p['sku'],p['category'],p['name'],self.money(p['price']),p['stock']))
    def add_pos(self):
        s=self.pt.selection()
        if not s:return
        p=self.db.conn.execute('SELECT * FROM products WHERE id=?',(s[0],)).fetchone(); current=next((x for x in self.cart if x['product_id']==p['id']),None)
        if not current and p['stock']<=0:return messagebox.showwarning('Stock','Product is out of stock.')
        if current and current['qty']>=p['stock']:return messagebox.showwarning('Stock','No more stock available.')
        if current: current['qty']+=1
        else:self.cart.append({'product_id':p['id'],'name':p['name'],'price':p['price'],'cost':p['cost'],'qty':1})
        self.refresh_cart()
    def refresh_cart(self):
        for x in self.ct.get_children(): self.ct.delete(x)
        sub=sum(i['qty']*i['price'] for i in self.cart)
        for i in self.cart:self.ct.insert('','end',values=(i['name'],i['qty'],self.money(i['price']),self.money(i['qty']*i['price'])))
        try:d=max(0,min(float(self.dis.get() or 0),sub))
        except:d=0
        tax=(sub-d)*float(self.cfg.get('tax_rate',0))/100; self.total.config(text=f"Subtotal {self.money(sub)} | Discount {self.money(d)} | Tax {self.money(tax)} | TOTAL {self.money(sub-d+tax)}")
    def change_qty(self,n):
        s=self.ct.selection()
        if not s:return
        i=self.cart[self.ct.index(s[0])]; i['qty']+=n
        if i['qty']<=0:self.cart.remove(i)
        self.refresh_cart()
    def remove_pos(self):
        s=self.ct.selection()
        if s:self.cart.pop(self.ct.index(s[0])); self.refresh_cart()
    def clear_cart(self): self.cart=[]; self.paid.set('0'); self.dis.set('0'); self.refresh_cart()
    def complete_sale(self):
        if not self.cart:return messagebox.showwarning('Order','Add products first.')
        try:
            if not self.db.current_business_day(): self.db.open_business_day(0)
            cid=self.custmap.get(self.cust.get()); r=create_sale(self.db,self.user['id'],self.cart,float(self.dis.get() or 0),float(self.cfg.get('tax_rate',0)),self.pm.get(),float(self.paid.get() or 0),self.ot.get(),cid); self.receipt(r[0]); self.clear_cart(); self.refresh_all()
        except Exception as e: messagebox.showerror('Sale Error',str(e))
    def receipt(self,oid):
        o=self.db.conn.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone(); items=self.db.order_items(oid); lines=[self.cfg['store_name'],self.cfg['store_address'],self.cfg['store_phone'],'='*42,f"Order {o['order_no']}  {o['created_at']}",'-'*42]
        lines += [f"{i['item_name']} x{i['qty']}  {self.money(i['amount'])}" for i in items]; lines += ['-'*42,f"Subtotal: {self.money(o['subtotal'])}",f"Discount: {self.money(o['discount'])}",f"Tax: {self.money(o['tax'])}",f"TOTAL: {self.money(o['total'])}",f"Paid: {self.money(o['paid'])}",f"Change: {self.money(o['change_amount'])}",f"Payment: {o['payment_method']}",'='*42,self.cfg['receipt_footer']]; text='\n'.join(lines); open(f"receipt_{o['order_no']}.txt",'w',encoding='utf-8').write(text)
        if self.printer:self.printer.send(('\x1b@'+text+'\n\x1dV\x00').encode('utf-8','replace'))
        messagebox.showinfo('Receipt',text)

    def products_tab(self,f):
        b=ttk.Frame(f); b.pack(fill='x');
        for txt,cmd in [('Add',self.product_dialog),('Edit',self.edit_product),('Delete',self.delete_product),('Delete ALL',self.delete_all),('Import CSV',self.import_menu),('Export CSV',self.export_menu),('Adjust Stock',self.adjust_stock)]: ttk.Button(b,text=txt,command=cmd).pack(side='left',padx=2)
        self.psearch=tk.StringVar(); ttk.Entry(b,textvariable=self.psearch).pack(side='right'); ttk.Button(b,text='Filter',command=self.refresh_products).pack(side='right',padx=3); self.padmin=self.tree(f,['ID','SKU','Category','Product','Price','Cost','Stock','Reorder']); self.padmin.bind('<Double-1>',lambda e:self.product_history())
    def refresh_products(self):
        if not hasattr(self,'padmin'):return
        for x in self.padmin.get_children():self.padmin.delete(x)
        for p in self.db.products(self.psearch.get()):self.padmin.insert('','end',iid=str(p['id']),values=(p['id'],p['sku'],p['category'],p['name'],self.money(p['price']),self.money(p['cost']),p['stock'],p['reorder_level']))
        if hasattr(self,'pt'):self.refresh_pos()
    def product_dialog(self,pid=None):
        p=self.db.conn.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone() if pid else None; w=tk.Toplevel(self); w.title('Product'); w.geometry('440x470'); vars={k:tk.StringVar(value=str(p[k]) if p else '') for k in ['name','sku','price','cost','stock','reorder_level']}; cats=self.db.categories(); cm={c['name']:c['id'] for c in cats}; cv=tk.StringVar(value=(self.db.conn.execute('SELECT name FROM categories WHERE id=?',(p['category_id'],)).fetchone()['name'] if p else cats[0]['name']))
        for lab,key in [('Name','name'),('SKU','sku'),('Price','price'),('Cost','cost'),('Stock','stock'),('Reorder','reorder_level')]: ttk.Label(w,text=lab).pack(anchor='w',padx=20,pady=(7,1)); ttk.Entry(w,textvariable=vars[key]).pack(fill='x',padx=20)
        ttk.Label(w,text='Category').pack(anchor='w',padx=20,pady=(7,1)); ttk.Combobox(w,textvariable=cv,values=list(cm),state='readonly').pack(fill='x',padx=20)
        def save():
            try:self.db.save_product(pid,cm[cv.get()],vars['name'].get().strip(),vars['sku'].get().strip(),float(vars['price'].get()),float(vars['cost'].get()),float(vars['stock'].get()),float(vars['reorder_level'].get()),self.user['id']);w.destroy();self.refresh_products()
            except Exception as e:messagebox.showerror('Product',str(e),parent=w)
        ttk.Button(w,text='SAVE',command=save).pack(fill='x',padx=20,pady=18)
    def edit_product(self):
        s=self.padmin.selection()
        if s:self.product_dialog(int(s[0]))
    def delete_product(self):
        s=self.padmin.selection()
        if s and messagebox.askyesno('Delete','Deactivate selected product?'):self.db.delete_product(int(s[0]),False,self.user['id']);self.refresh_products()
    def delete_all(self):
        if messagebox.askyesno('Delete ALL','Deactivate every product?'):self.db.delete_all_products(self.user['id']);self.refresh_products()
    def adjust_stock(self):
        s=self.padmin.selection()
        if not s:return
        try:self.db.adjust_stock(int(s[0]),float(self.ask('Stock adjustment','0')),self.ask('Reason','Manual adjustment'),self.db.current_business_day()['id'] if self.db.current_business_day() else None,self.user['id']);self.refresh_products()
        except Exception as e:messagebox.showerror('Stock',str(e))
    def product_history(self):
        s=self.padmin.selection()
        if s:self.history('Product History',self.db.product_history(int(s[0])),['created_at','movement_type','qty','note'])
    def import_menu(self):
        p=filedialog.askopenfilename(filetypes=[('CSV','*.csv')])
        if p:
            try:n=import_products(self.db,p,False);messagebox.showinfo('Import',f'{n} products imported/updated.');self.refresh_products()
            except Exception as e:messagebox.showerror('Import',str(e))
    def export_menu(self):
        p=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')])
        if p:
            try:export_products(self.db,p);messagebox.showinfo('Export','Menu exported successfully.')
            except Exception as e:messagebox.showerror('Export',str(e))

    def customers_tab(self,f):
        b=ttk.Frame(f);b.pack(fill='x')
        for txt,cmd in [('Add',lambda:self.party_dialog('customer')),('Edit',lambda:self.party_dialog('customer',self.selected_id(self.ctree))),('Payment',lambda:self.party_payment('customer')),('Export',lambda:self.export_party('customer'))]:ttk.Button(b,text=txt,command=cmd).pack(side='left',padx=2)
        self.cs=tk.StringVar();ttk.Entry(b,textvariable=self.cs).pack(side='right');ttk.Button(b,text='Filter',command=self.refresh_customers).pack(side='right',padx=3);self.ctree=self.tree(f,['ID','Name','Phone','Email','Points','Opening','Due']);self.ctree.bind('<Double-1>',lambda e:self.customer_history())
    def refresh_customers(self):
        if not hasattr(self,'ctree'):return
        for x in self.ctree.get_children():self.ctree.delete(x)
        for c in self.db.customers(self.cs.get()):self.ctree.insert('','end',iid=str(c['id']),values=(c['id'],c['name'],c['phone'] or '',c['email'] or '',c['points'],self.money(c['opening_balance']),self.money(max(0,float(c['balance'])))))
        if hasattr(self,'cb'):self.load_customer_choices()
    def customer_history(self):
        s=self.ctree.selection()
        if s:self.history('Customer History',self.db.customer_history(int(s[0])),['created_at','type','reference','debit','credit','note'])
    def suppliers_tab(self,f):
        b=ttk.Frame(f);b.pack(fill='x')
        for txt,cmd in [('Add',lambda:self.party_dialog('supplier')),('Edit',lambda:self.party_dialog('supplier',self.selected_id(self.stree))),('Payment',lambda:self.party_payment('supplier')),('Export',lambda:self.export_party('supplier'))]:ttk.Button(b,text=txt,command=cmd).pack(side='left',padx=2)
        self.ss=tk.StringVar();ttk.Entry(b,textvariable=self.ss).pack(side='right');ttk.Button(b,text='Filter',command=self.refresh_suppliers).pack(side='right',padx=3);self.stree=self.tree(f,['ID','Name','Phone','Email','Opening','Due']);self.stree.bind('<Double-1>',lambda e:self.supplier_history())
    def refresh_suppliers(self):
        if not hasattr(self,'stree'):return
        for x in self.stree.get_children():self.stree.delete(x)
        for s in self.db.suppliers(self.ss.get()):self.stree.insert('','end',iid=str(s['id']),values=(s['id'],s['name'],s['phone'] or '',s['email'] or '',self.money(s['opening_balance']),self.money(max(0,float(s['balance'])))))
    def supplier_history(self):
        s=self.stree.selection()
        if s:self.history('Supplier History',self.db.supplier_history(int(s[0])),['created_at','type','reference','debit','credit','note'])
    def selected_id(self,tree):
        s=tree.selection();return int(s[0]) if s else None
    def party_dialog(self,kind,pid=None):
        table='customers' if kind=='customer' else 'suppliers'; row=self.db.conn.execute(f'SELECT * FROM {table} WHERE id=?',(pid,)).fetchone() if pid else None; w=tk.Toplevel(self);w.title(('Edit ' if pid else 'New ')+kind.title());w.geometry('420x340');vs=[tk.StringVar(value=str(row[k]) if row and row[k] is not None else '') for k in ('name','phone','email','opening_balance')]
        for lab,v in zip(['Name','Phone','Email','Opening Balance'],vs):ttk.Label(w,text=lab).pack(anchor='w',padx=20,pady=(8,1));ttk.Entry(w,textvariable=v).pack(fill='x',padx=20)
        def save():
            try:
                if not vs[0].get().strip():raise ValueError('Name is required.')
                if pid:self.db.conn.execute(f'UPDATE {table} SET name=?,phone=?,email=? WHERE id=?',(vs[0].get().strip(),vs[1].get().strip() or None,vs[2].get().strip() or None,pid))
                else:self.db.conn.execute(f'INSERT INTO {table}(name,phone,email,opening_balance,created_at) VALUES(?,?,?,?,?)',(vs[0].get().strip(),vs[1].get().strip() or None,vs[2].get().strip() or None,float(vs[3].get() or 0),datetime.now().isoformat(timespec='seconds')))
                self.db.conn.commit();w.destroy();self.refresh_customers() if kind=='customer' else self.refresh_suppliers()
            except Exception as e:messagebox.showerror(kind.title(),str(e),parent=w)
        ttk.Button(w,text='SAVE',command=save).pack(fill='x',padx=20,pady=18)
    def party_payment(self,kind):
        tree=self.ctree if kind=='customer' else self.stree;pid=self.selected_id(tree)
        if not pid:return
        rows=self.db.customers() if kind=='customer' else self.db.suppliers(); balance=next((float(x['balance']) for x in rows if x['id']==pid),0); amount=self.ask('Payment amount',str(max(0,balance)));method=self.ask_choice('Payment Method',['Cash','Card','Mobile Wallet'],'Cash');note=self.ask('Note',kind.title()+' payment')
        try:
            ref=customer_payment(self.db,self.user['id'],pid,float(amount),method,note) if kind=='customer' else supplier_payment(self.db,self.user['id'],pid,float(amount),method,note);messagebox.showinfo('Payment',f'Saved: {ref}');self.refresh_all()
        except Exception as e:messagebox.showerror('Payment',str(e))
    def export_party(self,kind):
        p=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')]);
        if not p:return
        rows=self.db.customers() if kind=='customer' else self.db.suppliers()
        with open(p,'w',newline='',encoding='utf-8') as f:
            w=csv.writer(f);w.writerow(['ID','Name','Phone','Email','Opening Balance','Balance'])
            for r in rows:w.writerow([r['id'],r['name'],r['phone'],r['email'],r['opening_balance'],r['balance']])
        messagebox.showinfo('Export','Export completed.')
    def history(self,title,rows,keys):
        w=tk.Toplevel(self);w.title(title);w.geometry('950x500');t=self.tree(w,keys)
        for r in rows:t.insert('','end',values=tuple(r[k] if k in r.keys() else '' for k in keys))

    def purchases_tab(self,f):
        form=ttk.Frame(f);form.pack(fill='x');self.smap={f"{s['name']} ({s['phone'] or ''})":s['id'] for s in self.db.suppliers()};self.ppmap={f"{p['name']} ({p['sku']})":p['id'] for p in self.db.products()};self.purchase_supplier=tk.StringVar();self.purchase_product=tk.StringVar();self.purchase_qty=tk.StringVar(value='1');self.purchase_cost=tk.StringVar(value='0');self.purchase_paid=tk.StringVar(value='0');self.purchase_payment=tk.StringVar(value='Cash')
        for lab,var,vals in [('Supplier',self.purchase_supplier,list(self.smap)),('Product',self.purchase_product,list(self.ppmap)]:
            ttk.Label(form,text=lab).pack(side='left');ttk.Combobox(form,textvariable=var,values=vals,state='readonly',width=25).pack(side='left',padx=4)
        ttk.Label(form,text='Qty').pack(side='left');ttk.Entry(form,textvariable=self.purchase_qty,width=7).pack(side='left');ttk.Label(form,text='Cost').pack(side='left');ttk.Entry(form,textvariable=self.purchase_cost,width=9).pack(side='left');ttk.Button(form,text='Add Item',command=self.add_purchase_item).pack(side='left',padx=5);self.purtree=self.tree(f,['Product','Qty','Cost','Amount']);self.pur_total=tk.StringVar(value='Total: 0');ttk.Label(f,textvariable=self.pur_total,font=('Arial',14,'bold')).pack(anchor='e');pay=ttk.Frame(f);pay.pack(fill='x');ttk.Label(pay,text='Paid').pack(side='left');ttk.Entry(pay,textvariable=self.purchase_paid,width=12).pack(side='left');ttk.Label(pay,text='Method').pack(side='left');ttk.Combobox(pay,textvariable=self.purchase_payment,values=['Cash','Card','Mobile Wallet'],state='readonly',width=16).pack(side='left');ttk.Button(pay,text='SAVE PURCHASE',command=self.save_purchase).pack(side='right')
    def add_purchase_item(self):
        pid=self.ppmap.get(self.purchase_product.get())
        if not pid:return
        p=self.db.conn.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone();qty=float(self.purchase_qty.get());cost=float(self.purchase_cost.get() or p['cost'])
        if qty<=0 or cost<0:raise ValueError('Invalid quantity/cost.')
        self.purchase_items.append({'product_id':pid,'name':p['name'],'qty':qty,'cost':cost});self.refresh_purchase()
    def refresh_purchase(self):
        for x in self.purtree.get_children():self.purtree.delete(x)
        total=0
        for i in self.purchase_items:amt=i['qty']*i['cost'];total+=amt;self.purtree.insert('','end',values=(i['name'],i['qty'],self.money(i['cost']),self.money(amt)))
        self.pur_total.set('Total: '+self.money(total))
    def save_purchase(self):
        try:r=create_purchase(self.db,self.user['id'],self.smap[self.purchase_supplier.get()],self.purchase_items,float(self.purchase_paid.get() or 0),self.purchase_payment.get());messagebox.showinfo('Purchase',f'{r[1]} saved. Due: {self.money(r[3])}');self.purchase_items=[];self.refresh_purchase();self.refresh_all()
        except Exception as e:messagebox.showerror('Purchase',str(e))

    def expenses_tab(self,f):
        form=ttk.Frame(f);form.pack(fill='x');self.ev=[tk.StringVar() for _ in range(4)]
        for lab,v,vals in [('Category',self.ev[0],['Rent','Utilities','Salary','Supplies','Delivery','Repairs','Other']),('Description',self.ev[1],None),('Amount',self.ev[2],None),('Payment',self.ev[3],['Cash','Card','Mobile Wallet'])]:
            ttk.Label(form,text=lab).pack(side='left');(ttk.Combobox(form,textvariable=v,values=vals,state='readonly',width=15) if vals else ttk.Entry(form,textvariable=v,width=18)).pack(side='left',padx=3)
        self.ev[3].set('Cash');ttk.Button(form,text='ADD EXPENSE',command=self.add_exp).pack(side='left',padx=5);self.expt=self.tree(f,['Date','Category','Description','Amount','Payment'])
    def add_exp(self):
        try:self.db.add_expense(self.ev[0].get(),self.ev[1].get(),float(self.ev[2].get()),self.ev[3].get(),self.user['id']);self.refresh_expenses();self.refresh_accounting()
        except Exception as e:messagebox.showerror('Expense',str(e))
    def refresh_expenses(self):
        if not hasattr(self,'expt'):return
        for x in self.expt.get_children():self.expt.delete(x)
        for r in self.db.conn.execute('SELECT * FROM expenses ORDER BY id DESC LIMIT 500'):self.expt.insert('','end',values=(r['created_at'],r['category'],r['description'],self.money(r['amount']),r['payment_method']))

    def cash_tab(self,f):
        self.cash_info=tk.StringVar();ttk.Label(f,textvariable=self.cash_info,font=('Arial',13,'bold')).pack(anchor='w');b=ttk.Frame(f);b.pack(fill='x',pady=8)
        for txt,cmd in [('Open Business Day',self.open_day),('Cash In',lambda:self.cash_dialog(1)),('Cash Out',lambda:self.cash_dialog(-1)),('Close/Reconcile',self.close_day)]:ttk.Button(b,text=txt,command=cmd).pack(side='left',padx=3)
        self.casht=self.tree(f,['Date','Type','Amount','Note','Reference','Payment'])
    def refresh_cash(self):
        if not hasattr(self,'casht'):return
        b=self.db.current_business_day();self.cash_info.set('No business day open.' if not b else f"Business day {b['business_date']} | Opening {self.money(b['opening_cash'])} | Status {b['status']} | Variance {self.money(b['variance'] or 0)}")
        for x in self.casht.get_children():self.casht.delete(x)
        if b:
            for r in self.db.cash_flow(b['id']):self.casht.insert('','end',values=(r['created_at'],r['type'],self.money(r['amount']),r['note'],r['reference'],r['payment_method']))
    def open_day(self):
        try:self.db.open_business_day(float(self.ask('Opening cash','0')));self.refresh_all()
        except Exception as e:messagebox.showerror('Business Day',str(e))
    def cash_dialog(self,sign):
        try:self.db.cash(sign*float(self.ask('Cash amount','0')),'CASH_IN' if sign>0 else 'CASH_OUT',self.ask('Note',''),self.user['id']);self.refresh_cash()
        except Exception as e:messagebox.showerror('Cash',str(e))
    def close_day(self):
        try:expected,var=self.db.close_business_day(float(self.ask('Actual cash counted','0')),self.ask('Closing note',''));messagebox.showinfo('Reconciliation',f'Expected: {self.money(expected)}\nActual variance: {self.money(var)}');self.refresh_all()
        except Exception as e:messagebox.showerror('Close Day',str(e))

    def sales_tab(self,f):
        b=ttk.Frame(f);b.pack(fill='x');self.sfrom=tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'));self.sto=tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'));self.spay=tk.StringVar(value='All');self.ssearch=tk.StringVar()
        for lab,v in [('From',self.sfrom),('To',self.sto),('Search',self.ssearch)]:ttk.Label(b,text=lab).pack(side='left');ttk.Entry(b,textvariable=v,width=13).pack(side='left',padx=3)
        ttk.Combobox(b,textvariable=self.spay,values=['All','Cash','Card','Mobile Wallet','Credit'],state='readonly',width=14).pack(side='left');ttk.Button(b,text='FILTER',command=self.refresh_sales).pack(side='left',padx=4);self.salest=self.tree(f,['Order','Date','Customer','Type','Payment','Subtotal','Discount','Tax','Total']);self.salest.bind('<Double-1>',lambda e:self.sale_detail())
    def refresh_sales(self):
        if not hasattr(self,'salest'):return
        for x in self.salest.get_children():self.salest.delete(x)
        pay=None if self.spay.get()=='All' else self.spay.get()
        for r in self.db.sales(self.sfrom.get(),self.sto.get(),payment=pay):
            if self.ssearch.get().strip() and self.ssearch.get().lower() not in (r['order_no']+' '+(r['customer'] or '')).lower():continue
            self.salest.insert('','end',iid=str(r['id']),values=(r['order_no'],r['created_at'],r['customer'] or 'Walk-in',r['order_type'],r['payment_method'],self.money(r['subtotal']),self.money(r['discount']),self.money(r['tax']),self.money(r['total'])))
    def sale_detail(self):
        s=self.salest.selection()
        if not s:return
        oid=int(s[0]);w=tk.Toplevel(self);w.title('Sale Detail / Audit');w.geometry('850x520');t=self.tree(w,['Item','Qty','Price','Cost','Amount'])
        for i in self.db.order_items(oid):t.insert('','end',values=(i['item_name'],i['qty'],self.money(i['price']),self.money(i['cost']),self.money(i['amount'])))
        ttk.Button(w,text='Reprint Receipt',command=lambda:self.receipt(oid)).pack(fill='x',padx=10,pady=8)

    def accounting_tab(self,f):
        b=ttk.Frame(f);b.pack(fill='x');self.af=tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'));self.at=tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'));ttk.Entry(b,textvariable=self.af,width=13).pack(side='left');ttk.Entry(b,textvariable=self.at,width=13).pack(side='left',padx=4);ttk.Button(b,text='Refresh',command=self.refresh_accounting).pack(side='left');ttk.Button(b,text='Backup Database',command=self.backup).pack(side='left',padx=8);ttk.Button(b,text='Restore Backup',command=self.restore).pack(side='left')
        self.account_text=tk.StringVar();ttk.Label(f,textvariable=self.account_text,font=('Arial',13,'bold'),justify='left').pack(anchor='w',pady=10);self.atree=self.tree(f,['Code','Account','Type','Debit','Credit','Balance'])
    def refresh_accounting(self):
        if not hasattr(self,'atree'):return
        for x in self.atree.get_children():self.atree.delete(x)
        ac=Accounting(self.db);tb=ac.trial_balance(self.af.get(),self.at.get());debit=sum(r['debit'] for r in tb);credit=sum(r['credit'] for r in tb);pl=ac.profit_loss(self.af.get(),self.at.get());self.account_text.set(f"Trial Balance: Debit {self.money(debit)} | Credit {self.money(credit)}\nRevenue {self.money(pl['revenue'])} | Discounts {self.money(pl['discounts'])} | Expenses {self.money(pl['expenses'])} | NET PROFIT/LOSS {self.money(pl['net_profit'])}")
        for r in tb:self.atree.insert('','end',values=(r['code'],r['name'],r['account_type'],self.money(r['debit']),self.money(r['credit']),self.money(r['debit']-r['credit'])))
    def backup(self):
        try:p=backup_database(self.db);messagebox.showinfo('Backup',f'Backup created:\n{p}')
        except Exception as e:messagebox.showerror('Backup',str(e))
    def restore(self):
        p=filedialog.askopenfilename(filetypes=[('SQLite Database','*.db')])
        if not p:return
        if not messagebox.askyesno('Restore','Restore this database and restart the POS?'):return
        try:current=self.db.path;self.db.close();restore_database(p,current);messagebox.showinfo('Restore','Database restored. Restart the POS application.')
        except Exception as e:messagebox.showerror('Restore',str(e))

    def reports_tab(self,f):
        b=ttk.Frame(f);b.pack(fill='x');self.rf=tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'));self.rt=tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'));ttk.Label(b,text='From').pack(side='left');ttk.Entry(b,textvariable=self.rf,width=13).pack(side='left');ttk.Label(b,text='To').pack(side='left');ttk.Entry(b,textvariable=self.rt,width=13).pack(side='left');ttk.Button(b,text='RUN',command=self.run_report).pack(side='left',padx=5);self.report_text=tk.StringVar();ttk.Label(f,textvariable=self.report_text,font=('Arial',13,'bold'),justify='left').pack(anchor='w',pady=10);self.flow=self.tree(f,['Date','Type','Amount','Note','Reference','Payment'])
    def run_report(self):
        r,c,e,g,n=self.db.report(self.rf.get(),self.rt.get());self.report_text.set(f"Orders: {r['orders']}\nSales: {self.money(r['sales'])}\nCOGS: {self.money(c)}\nGross Profit: {self.money(g)}\nExpenses: {self.money(e)}\nNET PROFIT/LOSS: {self.money(n)}\nTax: {self.money(r['tax'])} | Discounts: {self.money(r['discounts'])}")
        for x in self.flow.get_children():self.flow.delete(x)
        for q in self.db.conn.execute('SELECT * FROM cash_transactions WHERE date(created_at) BETWEEN ? AND ? ORDER BY id',(self.rf.get(),self.rt.get())):self.flow.insert('','end',values=(q['created_at'],q['type'],self.money(q['amount']),q['note'],q['reference'],q['payment_method']))

    def settings_tab(self,f):
        keys=['store_name','store_address','store_phone','currency','tax_rate','business_day_start','business_day_end','printer_bluetooth_mac','printer_name','printer_port','printer_channel','receipt_footer'];self.setvars={k:tk.StringVar(value=self.cfg.get(k,'')) for k in keys};grid=ttk.Frame(f);grid.pack(fill='x');labels=[('Business','store_name'),('Address','store_address'),('Phone','store_phone'),('Currency','currency'),('Tax %','tax_rate'),('Business Day Start','business_day_start'),('Business Day End','business_day_end'),('Printer MAC','printer_bluetooth_mac'),('Printer Name','printer_name'),('Windows COM Port','printer_port'),('RFCOMM Channel','printer_channel'),('Receipt Footer','receipt_footer')]
        for i,(lab,k) in enumerate(labels):ttk.Label(grid,text=lab).grid(row=i,column=0,sticky='w',pady=3);ttk.Entry(grid,textvariable=self.setvars[k],width=65).grid(row=i,column=1,sticky='ew',pady=3)
        grid.columnconfigure(1,weight=1);b=ttk.Frame(f);b.pack(fill='x',pady=10)
        for txt,cmd in [('SAVE SETTINGS',self.save_settings),('SCAN BLUETOOTH',self.scan_printers),('CONNECT',self.connect_printer),('TEST PRINT',self.test_print)]:ttk.Button(b,text=txt,command=cmd).pack(side='left',padx=3)
        self.printer_status=tk.StringVar(value='Printer not connected');ttk.Label(f,textvariable=self.printer_status).pack(anchor='w')
    def save_settings(self):
        try:
            tax=float(self.setvars['tax_rate'].get());
            if tax<0:raise ValueError('Tax cannot be negative.')
            self.db.save_settings({k:v.get() for k,v in self.setvars.items()},self.user['id']);self.cfg=self.db.settings();self.title(self.cfg['store_name']);self.start_printer();messagebox.showinfo('Settings','Settings saved and applied.')
        except Exception as e:messagebox.showerror('Settings',str(e))
    def scan_printers(self):
        rows=BluetoothPrinter.discover();w=tk.Toplevel(self);w.title('Bluetooth Devices / Printers');w.geometry('750x400');t=self.tree(w,['Name','MAC','Port'])
        for r in rows:t.insert('','end',values=(r.get('name',''),r.get('mac',''),r.get('port','')))
        def choose():
            s=t.selection()
            if s:
                v=t.item(s[0],'values');self.setvars['printer_name'].set(v[0]);self.setvars['printer_bluetooth_mac'].set(v[1]);self.save_settings();w.destroy()
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
        else:messagebox.showerror('Printer','Pair the printer with the operating system first, then configure MAC or COM port.')
    def ask(self,title,default=''):
        w=tk.Toplevel(self);w.title(title);v=tk.StringVar(value=default);ttk.Label(w,text=title).pack(padx=20,pady=10);ttk.Entry(w,textvariable=v).pack(padx=20);out=[];ttk.Button(w,text='OK',command=lambda:(out.append(v.get()),w.destroy())).pack(pady=10);w.grab_set();self.wait_window(w);return out[0] if out else default
    def ask_choice(self,title,values,default):
        w=tk.Toplevel(self);w.title(title);v=tk.StringVar(value=default);ttk.Label(w,text=title).pack(padx=20,pady=10);ttk.Combobox(w,textvariable=v,values=values,state='readonly').pack(padx=20);out=[];ttk.Button(w,text='OK',command=lambda:(out.append(v.get()),w.destroy())).pack(pady=10);w.grab_set();self.wait_window(w);return out[0] if out else default
    def close(self):
        try:self.printer.disconnect()
        except Exception:pass
        self.db.close();self.destroy()


if __name__=='__main__':Login().mainloop()
