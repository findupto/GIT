import tempfile
from pathlib import Path

from database import Database
from modules.services import create_sale, create_purchase
from modules.accounting import Accounting


def test_sale_purchase_and_ledgers():
    with tempfile.TemporaryDirectory() as td:
        db=Database(Path(td)/'test.db')
        user=db.login('admin','0099')
        db.open_business_day(1000)
        p=db.products()[0]
        sale=create_sale(db,user['id'],[{'product_id':p['id'],'name':p['name'],'price':p['price'],'cost':p['cost'],'qty':1}],0,0,'Cash',p['price'])
        assert sale[5] == p['price']
        assert db.products(p['name'])[0]['stock'] == p['stock']-1
        supplier=db.conn.execute("INSERT INTO suppliers(name,created_at) VALUES('Test Supplier',datetime('now'))").lastrowid
        db.conn.commit()
        create_purchase(db,user['id'],supplier,[{'product_id':p['id'],'name':p['name'],'cost':p['cost'],'qty':2}],0,'Cash')
        rows=Accounting(db).trial_balance()
        assert round(sum(r['debit'] for r in rows),2)==round(sum(r['credit'] for r in rows),2)
        db.close()
