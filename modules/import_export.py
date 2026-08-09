import csv
from pathlib import Path

FIELDS=['name','sku','category','price','cost','stock','reorder_level','active']

def export_products(db, path):
    rows=db.conn.execute('SELECT p.name,p.sku,c.name category,p.price,p.cost,p.stock,p.reorder_level,p.active FROM products p JOIN categories c ON c.id=p.category_id ORDER BY p.name').fetchall()
    with open(path,'w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader()
        for r in rows:w.writerow(dict(r))

def import_products(db, path, replace=False):
    with open(path,'r',newline='',encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
    required={'name','sku','category','price'}
    if rows and not required.issubset(rows[0].keys()): raise ValueError('CSV must contain: name, sku, category, price')
    if replace: db.conn.execute('UPDATE products SET active=0')
    count=0
    for r in rows:
        if not r.get('name') or not r.get('sku'): continue
        cat=r['category'].strip() or 'Uncategorized'
        db.conn.execute('INSERT OR IGNORE INTO categories(name) VALUES(?)',(cat,))
        cid=db.conn.execute('SELECT id FROM categories WHERE name=?',(cat,)).fetchone()['id']
        vals=(r['name'].strip(),r['sku'].strip(),cid,float(r.get('price') or 0),float(r.get('cost') or 0),float(r.get('stock') or 0),float(r.get('reorder_level') or 5),int(r.get('active') or 1))
        db.conn.execute('''INSERT INTO products(name,sku,category_id,price,cost,stock,reorder_level,active) VALUES(?,?,?,?,?,?,?,?)
                           ON CONFLICT(sku) DO UPDATE SET name=excluded.name,category_id=excluded.category_id,price=excluded.price,cost=excluded.cost,stock=excluded.stock,reorder_level=excluded.reorder_level,active=excluded.active''',vals)
        count+=1
    db.conn.commit(); return count
