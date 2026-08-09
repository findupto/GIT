# FastFood POS

Professional desktop Point of Sale system for a fast-food store, built with **Python, Tkinter and SQLite**.

## Features

- Secure login with Admin and Cashier roles
- Dashboard with today's sales, order count, low-stock count and top sellers
- POS order screen with product search and category filtering
- Dine-in, Takeaway and Delivery order types
- Cash, Card and Mobile Wallet payments
- Discounts and configurable tax
- Automatic stock deduction on completed sales
- Stock adjustment and reorder levels
- Product/SKU/category/price/cost management
- Customer records and loyalty points
- Sales history with date filtering
- Sale detail lookup
- Sales, tax, discount and estimated gross-profit reports
- Payment-method breakdown
- Receipt generation and receipt text-file output
- Store information, currency and tax settings
- SQLite database with relational order, product, customer and inventory records

## Run

Requires Python 3.10+ with Tkinter available.

```bash
python app.py
```

The database `fastfood_pos.db` is created automatically.

### Default accounts

| Username | Password | Role |
|---|---|---|
| admin | admin123 | Admin |
| cashier | cashier123 | Cashier |

Change default credentials before deploying to a real store.

## Project Structure

- `app.py` - POS desktop application and UI
- `database.py` - SQLite schema, seed data and business operations
- `requirements.txt` - dependency note
- `fastfood_pos.db` - created locally at runtime; do not commit it

## Notes

This is a complete local desktop POS foundation. Hardware-specific receipt printers, barcode scanners, cloud synchronization and online payment gateways require store-specific integration.
