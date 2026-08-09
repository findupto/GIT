# MK Pizza & Ice Bar POS

Professional desktop Point of Sale system for **MK Pizza & Ice Bar**, built with Python, Tkinter and SQLite.

## Business Defaults

- **Business:** MK Pizza & Ice Bar
- **Address:** Collage Road Abbas Chowk, Bhakkar, Pakistan
- **Phone:** 0316 9700025
- **Currency:** Rs.
- **Tax:** 0%
- **Printer:** Configure the Bluetooth MAC address in Settings

## Features

- Admin and Owner login
- Dashboard with today's sales, order count, low-stock count and top sellers
- POS order screen with product search and category filtering
- Dine-in, Takeaway and Delivery order types
- Cash, Card and Mobile Wallet payments
- Discounts with 0% tax by default
- Automatic stock deduction on completed sales
- Stock adjustment and reorder levels
- Product/SKU/category/price/cost management
- Customer records and loyalty points
- Sales history with date filtering
- Sale detail lookup
- Sales, tax, discount and estimated gross-profit reports
- Payment-method breakdown
- Receipt generation and receipt text-file output
- Store information and configurable Bluetooth printer MAC setting
- SQLite database with relational order, product, customer and inventory records

## Default Users

| Username | Role | Password |
|---|---|---|
| admin | Admin | `0099` |
| owner | Owner | `0099` |

The old `cashier` account is disabled by the database migration.

## Run

Requires Python 3.10+ with Tkinter available.

```bash
python app.py
```

The database `fastfood_pos.db` is created automatically.

## Project Structure

- `app.py` - POS desktop application and UI
- `database.py` - SQLite schema, business defaults, seed data and business operations
- `requirements.txt` - dependency note
- `fastfood_pos.db` - created locally at runtime; do not commit it

## Printer

Set the receipt printer's Bluetooth MAC address in the application's Settings screen. The value is stored as `printer_bluetooth_mac` for hardware-specific Bluetooth printing integration.
