import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from database import Database

class Login(tk.Tk):
    def __init__(self):
        super().__init__(); self.title('FastFood POS - Login'); self.geometry('420x300'); self.resizable(False,False); self.db=Database(); self.protocol('WM_DELETE_WINDOW',self.quit)
        box=ttk.Frame(self,padding=30); box.pack(fill='both',expand=True)
        ttk.Label(box,text='FASTFOOD POS',font=('Arial',24,'bold')).pack(pady=(10,4)); ttk.Label(box,text='Secure Point of Sale',font=('Arial',10)).pack(pady=(0,20))
        self.user=tk.StringVar(value='admin'); self.pwd=tk.StringVar(value='admin123')
        ttk.Label(box,text='Username').pack(anchor='w'); ttk.Entry(box,textvariable=self.user).pack(fill='x',pady=(2,10)); ttk.Label(box,text='Password').pack(anchor='w'); ttk.Entry(box,textvariable=self.pwd,show='*').pack(fill='x',pady=(2,15)); ttk.Button(box,text='LOGIN',command=self.login).pack(fill='x',ipady=7)
        ttk.Label(box,text='Default: admin / admin123',font=('Arial',8)).pack(pady=12)
    def login(self):
        u=self.db.login(self.user.get().strip(),self.pwd.get())
        if not u: messagebox.showerror('Login Failed','Invalid username or password.'); return
        self.destroy(); app=POSApp(u,self.db); app.mainloop()

class POSApp(tk.Tk):
    def __init__(self,user,db):
        super().__init__(); self.user=user; self.db=db; self.cfg=db.settings(); self.cart=[]; self.title(f"{self.cfg['store_name']} - {user['username']}"); self.geometry('1250x760'); self.minsize(1050,650); self.protocol('WM_DELETE_WINDOW',self.close)
        self.style=ttk.Style(self); self.style.configure('Title.TLabel',font=('Arial',20,'bold')); self.style.configure('Total.TLabel',font=('Arial',18,'bold')); self.build()
    def close(self): self.db.close(); self.destroy()
    def money(self,n): return f"{self.cfg.get('currency','Rs')} {float(n):,.2f}"
    def build(self):
        top=ttk.Frame(self,padding=10); top.pack(fill='x'); ttk.Label(top,text=self.cfg['store_name'],style='Title.TLabel').pack(side='left'); ttk.Label(top,text=f"  |  {self.user['username']} ({self.user['role']})").pack(side='left'); ttk.Button(top,text='Logout',command=self.close).pack(side='right')
        nb=ttk.Notebook(self); nb.pack(fill='both',expand=True,padx=10,pady=(0,10)); self.tabs={}
        for name,fn in [('Dashboard',self.dashboard_tab),('POS',self.pos_tab),('Products',self.products_tab),('Customers',self.customers_tab),('Sales',self.sales_tab),('Reports',self.reports_tab),('Settings',self.settings_tab)]:
            f=ttk.Frame(nb,padding=10); nb.add(f,text=name); self.tabs[name]=f; fn(f)
        if self.user['role']!='admin': nb.tab(self.tabs['Settings'],state='disabled')
        self.refresh_dashboard(); self.refresh_products(); self.refresh_customers(); self.refresh_sales()

    def dashboard_tab(self,f):
        self.dash_vars=[tk.StringVar(value='0') for _ in range(3)]
        cards=ttk.Frame(f); cards.pack(fill='x')
        for i,(title,var) in enumerate(zip(['Today Sales','Orders Today','Low Stock'],self.dash_vars)):
            c=ttk.LabelFrame(cards,text=title,padding=15); c.grid(row=0,column=i,sticky='nsew',padx=5); cards.columnconfigure(i,weight=1); ttk.Label(c,textvariable=var,font=('Arial',22,'bold')).pack()
        ttk.Label(f,text='Top Selling Items Today',font=('Arial',14,'bold')).pack(anchor='w',pady=(25,8)); self.top_tree=self.tree(f,['Item','Qty'])
    def refresh_dashboard(self):
        total,orders,low,items=self.db.dashboard(); self.dash_vars[0].set(self.money(total)); self.dash_vars[1].set(orders); self.dash_vars[2].set(low)
        for x in self.top_tree.get_children(): self.top_tree.delete(x)
        for r in items:self.top_tree.insert('','end',values=(r['item_name'],r['qty']))

    def pos_tab(self,f):
        left=ttk.Frame(f); left.pack(side='left',fill='both',expand=True,padx=(0,8)); right=ttk.LabelFrame(f,text='Current Order',padding=10); right.pack(side='right',fill='both',expand=True)
        tools=ttk.Frame(left); tools.pack(fill='x',pady=(0,8)); self.search=tk.StringVar(); ttk.Entry(tools,textvariable=self.search).pack(side='left',fill='x',expand=True); ttk.Button(tools,text='Search',command=self.refresh_products).pack(side='left',padx=5); self.cat=tk.StringVar(value='All'); self.catmap={'All':None};
        for c in self.db.categories(): self.catmap[c['name']]=c['id']
        self.catbox=ttk.Combobox(tools,textvariable=self.cat,values=list(self.catmap),state='readonly',width=16); self.catbox.pack(side='left'); self.catbox.bind('<<ComboboxSelected>>',lambda e:self.refresh_products())
        self.menu=self.tree(left,['SKU','Category','Product','Price','Stock']); self.menu.bind('<Double-1>',lambda e:self.add_product())
        ttk.Button(left,text='Add Selected Item',command=self.add_product).pack(fill='x',pady=8)
        self.cart_tree=self.tree(right,['Item','Qty','Price','Amount']); self.cart_tree.pack(fill='both',expand=True)
        a=ttk.Frame(right); a.pack(fill='x',pady=8)
        for txt,cmd in [('+ Qty',lambda:self.qty(1)),('- Qty',lambda:self.qty(-1)),('Remove',self.remove_cart),('Clear',self.clear_cart)]: ttk.Button(a,text=txt,command=cmd).pack(side='left',expand=True,fill='x',padx=2)
        form=ttk.Frame(right); form.pack(fill='x'); self.order_type=tk.StringVar(value='Takeaway'); self.payment=tk.StringVar(value='Cash'); self.discount=tk.StringVar(value='0'); self.paid=tk.StringVar(value='0'); self.customer=tk.StringVar(value='Walk-in Customer')
        for label,var,values in [('Order Type',self.order_type,['Dine-in','Takeaway','Delivery']),('Payment',self.payment,['Cash','Card','Mobile Wallet'])]:
            ttk.Label(form,text=label).pack(side='left'); ttk.Combobox(form,textvariable=var,values=values,state='readonly',width=13).pack(side='left',padx=(3,8))
        ttk.Label(form,text='Discount').pack(side='left'); ttk.Entry(form,textvariable=self.discount,width=8).pack(side='left',padx=3); ttk.Label(form,text='Paid').pack(side='left'); ttk.Entry(form,textvariable=self.paid,width=9).pack(side='left',padx=3)
        self.pos_total=tk.StringVar(value=self.money(0)); ttk.Label(right,textvariable=self.pos_total,style='Total.TLabel').pack(anchor='e',pady=8); ttk.Button(right,text='COMPLETE SALE & RECEIPT',command=self.complete_sale).pack(fill='x',ipady=8)
    def tree(self,parent,cols):
        t=ttk.Treeview(parent,columns=cols,show='headings',selectmode='browse');
        for c in cols:t.heading(c,text=c);t.column(c,width=110,anchor='center')
        t.pack(fill='both',expand=True); return t
    def refresh_products(self):
        if not hasattr(self,'menu'): return
        for x in self.menu.get_children():self.menu.delete(x)
        for p in self.db.products(self.search.get() if hasattr(self,'search') else '',self.catmap.get(self.cat.get()) if hasattr(self,'cat') else None): self.menu.insert('','end',values=(p['sku'],p['category'],p['name'],self.money(p['price']),p['stock']),iid=str(p['id']))
    def add_product(self):
        s=self.menu.selection()
        if not s:return
        p=self.db.conn.execute('SELECT * FROM products WHERE id=?',(s[0],)).fetchone()
        for i in self.cart:
            if i['product_id']==p['id']:i['qty']+=1;break
        else:self.cart.append({'product_id':p['id'],'name':p['name'],'price':p['price'],'cost':p['cost'],'qty':1})
        self.refresh_cart()
    def refresh_cart(self):
        for x in self.cart_tree.get_children():self.cart_tree.delete(x)
        sub=0
        for i in self.cart: amt=i['qty']*i['price'];sub+=amt;self.cart_tree.insert('','end',values=(i['name'],i['qty'],self.money(i['price']),self.money(amt)))
        try:d=max(0,min(float(self.discount.get() or 0),sub))
        except:d=0
        tax=(sub-d)*float(self.cfg['tax_rate'])/100; self.pos_total.set(f"Subtotal {self.money(sub)}  |  Discount {self.money(d)}  |  Tax {self.money(tax)}  |  TOTAL {self.money(sub-d+tax)}")
    def qty(self,n):
        s=self.cart_tree.selection()
        if not s:return
        i=self.cart_tree.index(s[0]); self.cart[i]['qty']+=n
        if self.cart[i]['qty']<=0:self.cart.pop(i)
        self.refresh_cart()
    def remove_cart(self):
        s=self.cart_tree.selection()
        if s:self.cart.pop(self.cart_tree.index(s[0]));self.refresh_cart()
    def clear_cart(self):self.cart=[];self.paid.set('0');self.discount.set('0');self.refresh_cart()
    def complete_sale(self):
        if not self.cart:return messagebox.showwarning('Empty Order','Add items first.')
        try:
            discount=float(self.discount.get() or 0); sub=sum(i['qty']*i['price'] for i in self.cart); total=sub-min(discount,sub)+(sub-min(discount,sub))*float(self.cfg['tax_rate'])/100
            paid=float(self.paid.get() or total) if self.payment.get()!='Cash' else float(self.paid.get() or 0)
            if self.payment.get()!='Cash':paid=total
            result=self.db.create_order(self.user['id'],None,self.order_type.get(),self.cart,discount,float(self.cfg['tax_rate']),self.payment.get(),paid)
            self.show_receipt(result[0]); self.clear_cart(); self.refresh_products(); self.refresh_dashboard(); self.refresh_sales()
        except Exception as e: messagebox.showerror('Sale Error',str(e))
    def show_receipt(self,oid):
        o=self.db.conn.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone(); items=self.db.order_items(oid); text=f"{self.cfg['store_name']}\n{self.cfg['store_address']}\n{self.cfg['store_phone']}\n{'='*38}\nOrder: {o['order_no']}\nDate: {o['created_at']}\nType: {o['order_type']}\n{'-'*38}\n"; text+=''.join(f"{i['item_name']} x{i['qty']}  {self.money(i['amount'])}\n" for i in items); text+=f"{'-'*38}\nSubtotal: {self.money(o['subtotal'])}\nDiscount: {self.money(o['discount'])}\nTax: {self.money(o['tax'])}\nTOTAL: {self.money(o['total'])}\nPaid: {self.money(o['paid'])}\nChange: {self.money(o['change_amount'])}\nPayment: {o['payment_method']}\n{'='*38}\n{self.cfg['receipt_footer']}\n"; messagebox.showinfo('Receipt',text)
        with open(f"receipt_{o['order_no']}.txt",'w',encoding='utf-8') as f:f.write(text)

    def products_tab(self,f):
        bar=ttk.Frame(f);bar.pack(fill='x'); ttk.Button(bar,text='Add Product',command=lambda:self.product_dialog()).pack(side='left'); self.prod_search=tk.StringVar(); ttk.Entry(bar,textvariable=self.prod_search).pack(side='right'); ttk.Button(bar,text='Search',command=self.refresh_product_admin).pack(side='right',padx=5); self.ptree=self.tree(f,['ID','SKU','Category','Product','Price','Cost','Stock','Reorder']); self.ptree.bind('<Double-1>',lambda e:self.edit_product())
    def refresh_product_admin(self):
        if not hasattr(self,'ptree'):return
        for x in self.ptree.get_children():self.ptree.delete(x)
        for p in self.db.products(self.prod_search.get()):self.ptree.insert('','end',values=(p['id'],p['sku'],p['category'],p['name'],self.money(p['price']),self.money(p['cost']),p['stock'],p['reorder_level']),iid=str(p['id']))
    def refresh_products(self):
        if hasattr(self,'menu'):
            for x in self.menu.get_children():self.menu.delete(x)
            for p in self.db.products(self.search.get(),self.catmap.get(self.cat.get())):self.menu.insert('','end',values=(p['sku'],p['category'],p['name'],self.money(p['price']),p['stock']),iid=str(p['id']))
        self.refresh_product_admin()
    def edit_product(self):
        s=self.ptree.selection()
        if s:self.product_dialog(int(s[0]))
    def product_dialog(self,pid=None):
        p=self.db.conn.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone() if pid else None; w=tk.Toplevel(self);w.title('Product');w.geometry('420x480');w.transient(self)
        vals={k:tk.StringVar(value=str(p[k]) if p else '') for k in ['name','sku','price','cost','stock','reorder_level']}; cats=self.db.categories(); cmap={c['name']:c['id'] for c in cats}; cv=tk.StringVar(value=(self.db.conn.execute('SELECT name FROM categories WHERE id=?',(p['category_id'],)).fetchone()['name'] if p else cats[0]['name']))
        for lab,key in [('Name','name'),('SKU','sku'),('Price','price'),('Cost','cost'),('Stock','stock'),('Reorder Level','reorder_level')]:ttk.Label(w,text=lab).pack(anchor='w',padx=20,pady=(10,2));ttk.Entry(w,textvariable=vals[key]).pack(fill='x',padx=20)
        ttk.Label(w,text='Category').pack(anchor='w',padx=20,pady=(10,2));ttk.Combobox(w,textvariable=cv,values=list(cmap),state='readonly').pack(fill='x',padx=20)
        def save():
            try:self.db.save_product(pid,cmap[cv.get()],vals['name'].get(),vals['sku'].get(),float(vals['price'].get()),float(vals['cost'].get()),float(vals['stock'].get()),float(vals['reorder_level'].get()));w.destroy();self.refresh_products()
            except Exception as e:messagebox.showerror('Product Error',str(e),parent=w)
        ttk.Button(w,text='SAVE',command=save).pack(fill='x',padx=20,pady=20)

    def customers_tab(self,f):
        bar=ttk.Frame(f);bar.pack(fill='x');ttk.Button(bar,text='Add Customer',command=self.customer_dialog).pack(side='left');self.csearch=tk.StringVar();ttk.Entry(bar,textvariable=self.csearch).pack(side='right');ttk.Button(bar,text='Search',command=self.refresh_customers).pack(side='right',padx=5);self.ctree=self.tree(f,['ID','Name','Phone','Email','Points','Created'])
    def refresh_customers(self):
        if not hasattr(self,'ctree'):return
        for x in self.ctree.get_children():self.ctree.delete(x)
        for c in self.db.customers(self.csearch.get() if hasattr(self,'csearch') else ''):self.ctree.insert('','end',values=(c['id'],c['name'],c['phone'] or '',c['email'] or '',c['points'],c['created_at']))
    def customer_dialog(self):
        w=tk.Toplevel(self);w.title('New Customer');w.geometry('380x300');vs=[tk.StringVar() for _ in range(3)]
        for lab,v in zip(['Name','Phone','Email'],vs):ttk.Label(w,text=lab).pack(anchor='w',padx=20,pady=(10,2));ttk.Entry(w,textvariable=v).pack(fill='x',padx=20)
        def save():
            try:self.db.save_customer(*[v.get().strip() for v in vs]);w.destroy();self.refresh_customers()
            except Exception as e:messagebox.showerror('Customer Error',str(e),parent=w)
        ttk.Button(w,text='SAVE',command=save).pack(fill='x',padx=20,pady=20)

    def sales_tab(self,f):
        bar=ttk.Frame(f);bar.pack(fill='x');self.sf=tk.StringVar(value=(datetime.now()-timedelta(days=30)).strftime('%Y-%m-%d'));self.st=tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'));ttk.Label(bar,text='From').pack(side='left');ttk.Entry(bar,textvariable=self.sf,width=12).pack(side='left',padx=4);ttk.Label(bar,text='To').pack(side='left');ttk.Entry(bar,textvariable=self.st,width=12).pack(side='left',padx=4);ttk.Button(bar,text='Refresh',command=self.refresh_sales).pack(side='left');self.str= self.tree(f,['ID','Order No','Date','Type','Customer','Payment','Total','User']);self.str.bind('<Double-1>',lambda e:self.sale_detail())
    def refresh_sales(self):
        if not hasattr(self,'str'):return
        for x in self.str.get_children():self.str.delete(x)
        for o in self.db.sales(self.sf.get(),self.st.get()):self.str.insert('','end',values=(o['id'],o['order_no'],o['created_at'],o['order_type'],o['customer'] or 'Walk-in',o['payment_method'],self.money(o['total']),o['username'] or ''))
    def sale_detail(self):
        s=self.str.selection()
        if not s:return
        oid=int(s[0]);items=self.db.order_items(oid);messagebox.showinfo('Sale Details','\n'.join(f"{i['item_name']} x{i['qty']} = {self.money(i['amount'])}" for i in items))

    def reports_tab(self,f):
        bar=ttk.Frame(f);bar.pack(fill='x');self.rf=tk.StringVar(value=datetime.now().strftime('%Y-%m-01'));self.rt=tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'));ttk.Entry(bar,textvariable=self.rf,width=12).pack(side='left');ttk.Entry(bar,textvariable=self.rt,width=12).pack(side='left',padx=5);ttk.Button(bar,text='Generate Report',command=self.report).pack(side='left');self.report_text=tk.Text(f,height=25);self.report_text.pack(fill='both',expand=True,pady=10)
    def report(self):
        row,profit,pays=self.db.report_summary(self.rf.get(),self.rt.get());t=f"SALES REPORT\n{self.rf.get()} to {self.rt.get()}\n{'='*45}\nOrders: {row['orders']}\nSubtotal: {self.money(row['subtotal'])}\nDiscounts: {self.money(row['discount'])}\nTax: {self.money(row['tax'])}\nRevenue: {self.money(row['total'])}\nEstimated Gross Profit: {self.money(profit)}\n\nPAYMENT BREAKDOWN\n";t+=''.join(f"{p['payment_method']}: {p['orders']} orders / {self.money(p['total'])}\n" for p in pays);self.report_text.delete('1.0','end');self.report_text.insert('1.0',t)

    def settings_tab(self,f):
        self.settings_vars={k:tk.StringVar(value=v) for k,v in self.cfg.items()};form=ttk.Frame(f);form.pack(fill='x',padx=80)
        for k in ['store_name','store_address','store_phone','tax_rate','currency','receipt_footer']:
            ttk.Label(form,text=k.replace('_',' ').title()).pack(anchor='w',pady=(10,2));ttk.Entry(form,textvariable=self.settings_vars[k]).pack(fill='x')
        def save():
            for k,v in self.settings_vars.items():self.db.conn.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',(k,v.get()))
            self.db.conn.commit();self.cfg=self.db.settings();messagebox.showinfo('Settings','Settings saved. Restart POS to apply all display changes.')
        ttk.Button(form,text='SAVE SETTINGS',command=save).pack(fill='x',pady=20)

if __name__=='__main__': Login().mainloop()
