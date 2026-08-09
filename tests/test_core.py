import tempfile
from pathlib import Path

from database import Database
from modules.services import create_sale, create_purchase, customer_payment, supplier_payment
from modules.accounting import Accounting


def test_sale_purchase_discount_and_ledgers():
    with tempfile.TemporaryDirectory() as td:
        db=Database(Path(td)/"test.db")
        user=db.login("admin","0099"); db.open_business_day(1000); p=db.products()[0]
        sale=create_sale(db,user["id"],[{"product_id":p["id"],"name":p["name"],"price":p["price"],"cost":p["cost"],"qty":1}],50,0,"Cash",p["price"]-50)
        assert sale[5] == p["price"]-50
        rows=Accounting(db).trial_balance(); assert round(sum(r["debit"] for r in rows),2)==round(sum(r["credit"] for r in rows),2)
        supplier=db.conn.execute("INSERT INTO suppliers(name,created_at) VALUES('Test Supplier',datetime('now'))").lastrowid; db.conn.commit()
        create_purchase(db,user["id"],supplier,[{"product_id":p["id"],"name":p["name"],"cost":p["cost"],"qty":2}],0,"Cash")
        rows=Accounting(db).trial_balance(); assert round(sum(r["debit"] for r in rows),2)==round(sum(r["credit"] for r in rows),2)
        db.close()


def test_credit_sale_and_party_payments():
    with tempfile.TemporaryDirectory() as td:
        db=Database(Path(td)/"test.db"); user=db.login("admin","0099"); db.open_business_day(500)
        db.conn.execute("INSERT INTO customers(name,created_at) VALUES('Customer',datetime('now'))"); cid=db.conn.execute("SELECT id FROM customers WHERE name='Customer'").fetchone()["id"]
        db.conn.execute("INSERT INTO suppliers(name,created_at) VALUES('Supplier',datetime('now'))"); sid=db.conn.execute("SELECT id FROM suppliers WHERE name='Supplier'").fetchone()["id"]; db.conn.commit(); p=db.products()[0]
        create_sale(db,user["id"],[{"product_id":p["id"],"name":p["name"],"price":p["price"],"cost":p["cost"],"qty":1}],0,0,"Credit",0,"Takeaway",cid)
        assert round(db.customers()[0]["balance"],2)==round(p["price"],2)
        customer_payment(db,user["id"],cid,p["price"],"Cash")
        assert round(db.customers()[0]["balance"],2)==0
        db.conn.execute("INSERT INTO supplier_transactions(supplier_id,created_at,type,reference,debit,credit,note) VALUES(?,?,?,?,?,?,?)",(sid,"2026-01-01","OPENING","OPEN",100,0,"opening")); db.conn.commit()
        supplier_payment(db,user["id"],sid,50,"Cash")
        assert round(db.suppliers()[0]["balance"],2)==50
        rows=Accounting(db).trial_balance(); assert round(sum(r["debit"] for r in rows),2)==round(sum(r["credit"] for r in rows),2)
        db.close()
