# MK Pizza & Ice Bar — Advanced POS

Advanced desktop Point of Sale and small-business management system for **MK Pizza & Ice Bar**, built with Python, Tkinter and SQLite.

## Business defaults

- Business: **MK Pizza & Ice Bar**
- Address: **Collage Road Abbas Chowk, Bhakkar, Pakistan**
- Phone: **0316 9700025**
- Currency: **Rs.**
- Tax: **0%**
- Business day: **06:00 → 05:59** by default; configurable in Settings
- Printer: Bluetooth/ESC-POS 80mm configuration in Settings

## Default users

| Username | Role | Password |
|---|---|---|
| admin | Admin | `0099` |
| owner | Owner | `0099` |

## Modules

- Dashboard
- POS / orders
- Products and categories
- Bulk menu CSV import/export
- Inventory and stock movements
- Customers and customer ledgers
- Suppliers and supplier ledgers
- Purchases and supplier dues
- Expenses
- Cash in / cash out
- Opening and closing cash reconciliation
- Configurable business day
- Sales history and filtering
- Product/customer/supplier transaction history
- Profit/Loss and COGS reporting
- Cash-flow records
- Double-entry journal / trial balance foundation
- Audit log
- Database backup/restore utilities
- Bluetooth thermal printer discovery/reconnect helpers

## Financial model

Sales, purchases and expenses are designed to update inventory, cash/receivables/payables and accounting journals together. Core sales and purchasing operations use database transactions so stock and financial records do not partially update after an error.

## Run

Python 3.10+ with Tkinter is recommended.

```bash
pip install -r requirements.txt
python app.py
```

The local `fastfood_pos.db` file is created automatically.

## Project structure

- `app.py` — desktop POS UI
- `database.py` — database schema, defaults, ledgers, business-day and audit operations
- `modules/services.py` — transactional sales/purchase services
- `modules/accounting.py` — double-entry journal and financial reporting foundation
- `modules/import_export.py` — bulk product CSV import/export
- `modules/printer.py` — Bluetooth/ESC-POS printer helper
- `modules/backup.py` — consistent SQLite backup/restore utility
- `tests/test_core.py` — regression tests
- `.github/workflows/python-check.yml` — compile and automated test workflow

## 80mm printer

Pair the Bluetooth printer with the operating system first where required, then configure its MAC/name/COM port/channel in Settings. The printer helper supports discovery where the OS exposes it, ESC/POS test printing and background reconnect attempts.

## Important deployment note

This is an advanced single-location desktop POS foundation. For a true multi-branch enterprise deployment, the next architectural step is a server/API backend, PostgreSQL or equivalent production database, encrypted credentials, centralized authentication, synchronized branches and remote backup/monitoring.
