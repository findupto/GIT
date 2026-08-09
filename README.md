# MK Pizza & Ice Bar — Advanced FastFood POS

Advanced single-location desktop POS and business-management system for **MK Pizza & Ice Bar**, built with Python, Tkinter and SQLite.

## Business defaults

- Business: **MK Pizza & Ice Bar**
- Address: **Collage Road Abbas Chowk, Bhakkar, Pakistan**
- Phone: **0316 9700025**
- Currency: **Rs.**
- Tax: **0%**
- Business day: **06:00 → 05:59** by default; configurable in Settings
- Thermal printer: **80mm ESC/POS Bluetooth/COM**, configured in Settings

## Default users

| Username | Role | Password |
|---|---|---|
| admin | Admin | `0099` |
| owner | Owner | `0099` |

## Functional modules

- Dashboard with sales, orders, gross/net profit, expenses, customer dues and supplier dues
- POS with search, categories, stock validation, dine-in/takeaway/delivery and receipt printing
- Cash, Card, Mobile Wallet and Credit sales
- Customer selection and customer credit ledger
- Product/menu CRUD, deactivate-all, stock adjustments and history
- CSV bulk menu import/export
- Customer CRUD, dues, payments, exports and transaction history
- Supplier CRUD, dues, payments, exports and transaction history
- Purchases with stock receiving, supplier payable and partial payment
- Expenses with cash/bank posting
- Business-day opening, configurable day boundary, cash in/out and end-of-day reconciliation
- Sales history with date/payment/search filters and sale detail
- Product, customer and supplier drill-down history
- Double-entry accounting, trial balance and P&L
- COGS and inventory movement accounting
- Cash-flow records and reconciliation
- Audit log foundation
- SQLite WAL mode and indexed transaction/history queries
- Consistent SQLite backup/restore
- Bluetooth printer discovery, saved configuration and automatic reconnect attempts
- Automated regression tests for sales, discounts, credit, purchases and party payments

## Bulk menu

CSV import/export is supported for SKU, product name, category, price, cost, stock and reorder level.

## 80mm printer

Pair the Bluetooth printer with the operating system when required. In **Settings**, scan/select the printer or enter its MAC address. On Windows, a paired printer exposed through a COM port can be configured directly. The POS saves the configuration and starts background reconnect attempts after launch/disconnect.

Automatic Bluetooth pairing cannot be guaranteed by a desktop Python application because pairing and permissions are controlled by the operating system and printer hardware.

## Run

Python 3.10+ with Tkinter is recommended:

```bash
pip install -r requirements.txt
python app.py
```

The local `fastfood_pos.db` database is created automatically.

## Project structure

- `app.py` — POS desktop UI and operational modules
- `database.py` — SQLite schema, settings, inventory, ledgers, cash and business-day operations
- `modules/services.py` — transactional sales, purchases and customer/supplier payments
- `modules/accounting.py` — double-entry journal, trial balance and P&L
- `modules/import_export.py` — bulk product CSV import/export
- `modules/printer.py` — Bluetooth/ESC-POS printer discovery and reconnect helper
- `modules/backup.py` — SQLite backup/restore
- `tests/test_core.py` — regression tests
- `.github/workflows/python-check.yml` — compile and automated test workflow

## Deployment scope

This release is a **fully operational advanced single-location desktop POS foundation**. It is not a multi-branch cloud ERP. Enterprise multi-branch deployment would additionally require a server/API backend, PostgreSQL-class production database, centralized authentication, encrypted secrets, branch synchronization, remote backup and monitoring.
