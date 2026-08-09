import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime

DB = "pos.db"

MENU = [
    ("Burgers", "Classic Burger", 350),
    ("Burgers", "Chicken Burger", 450),
    ("Pizza", "Chicken Pizza", 900),
    ("Pizza", "Cheese Pizza", 800),
    ("Sides", "French Fries", 250),
    ("Sides", "Chicken Nuggets", 400),
    ("Drinks", "Soft Drink", 120),
    ("Drinks", "Mineral Water", 80),
]


class POSApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FastFood POS")
        self.geometry("1000x650")
        self.minsize(900, 600)
        self.cart = []
        self.conn = sqlite3.connect(DB)
        self.setup_db()
        self.build_ui()

    def setup_db(self):
        self.conn.execute("""CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            subtotal REAL NOT NULL,
            discount REAL NOT NULL,
            tax REAL NOT NULL,
            total REAL NOT NULL,
            payment_method TEXT NOT NULL
        )""")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            qty INTEGER NOT NULL,
            price REAL NOT NULL
        )""")
        self.conn.commit()

    def build_ui(self):
        header = ttk.Frame(self, padding=12)
        header.pack(fill="x")
        ttk.Label(header, text="FASTFOOD POS", font=("Arial", 22, "bold")).pack(side="left")
        ttk.Label(header, text="Point of Sale System", font=("Arial", 11)).pack(side="left", padx=15)

        main = ttk.PanedWindow(self, orient="horizontal")
        main.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        menu_frame = ttk.LabelFrame(main, text="Menu", padding=10)
        cart_frame = ttk.LabelFrame(main, text="Current Order", padding=10)
        main.add(menu_frame, weight=3)
        main.add(cart_frame, weight=2)

        columns = ("category", "item", "price")
        self.menu_tree = ttk.Treeview(menu_frame, columns=columns, show="headings", height=20)
        for col, title, width in [("category", "Category", 100), ("item", "Item", 220), ("price", "Price (Rs)", 100)]:
            self.menu_tree.heading(col, text=title)
            self.menu_tree.column(col, width=width, anchor="center" if col != "item" else "w")
        for category, item, price in MENU:
            self.menu_tree.insert("", "end", values=(category, item, price))
        self.menu_tree.pack(fill="both", expand=True)
        self.menu_tree.bind("<Double-1>", lambda e: self.add_selected())
        ttk.Button(menu_frame, text="Add Selected Item", command=self.add_selected).pack(fill="x", pady=(8, 0))

        cart_cols = ("item", "qty", "price", "amount")
        self.cart_tree = ttk.Treeview(cart_frame, columns=cart_cols, show="headings", height=14)
        for col, title, width in [("item", "Item", 150), ("qty", "Qty", 50), ("price", "Price", 70), ("amount", "Amount", 80)]:
            self.cart_tree.heading(col, text=title)
            self.cart_tree.column(col, width=width, anchor="center" if col != "item" else "w")
        self.cart_tree.pack(fill="both", expand=True)

        actions = ttk.Frame(cart_frame)
        actions.pack(fill="x", pady=8)
        ttk.Button(actions, text="+ Qty", command=lambda: self.change_qty(1)).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(actions, text="- Qty", command=lambda: self.change_qty(-1)).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(actions, text="Remove", command=self.remove_selected).pack(side="left", expand=True, fill="x", padx=2)

        totals = ttk.Frame(cart_frame)
        totals.pack(fill="x", pady=5)
        self.subtotal_var = tk.StringVar(value="Rs 0.00")
        self.tax_var = tk.StringVar(value="Rs 0.00")
        self.total_var = tk.StringVar(value="Rs 0.00")
        for label, var in [("Subtotal", self.subtotal_var), ("Tax (5%)", self.tax_var), ("TOTAL", self.total_var)]:
            row = ttk.Frame(totals)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=label, font=("Arial", 11, "bold") if label == "TOTAL" else ("Arial", 10)).pack(side="left")
            ttk.Label(row, textvariable=var, font=("Arial", 14, "bold") if label == "TOTAL" else ("Arial", 10)).pack(side="right")

        ttk.Label(cart_frame, text="Payment Method").pack(anchor="w", pady=(8, 2))
        self.payment_var = tk.StringVar(value="Cash")
        ttk.Combobox(cart_frame, textvariable=self.payment_var, values=["Cash", "Card", "Mobile Wallet"], state="readonly").pack(fill="x")
        ttk.Button(cart_frame, text="COMPLETE SALE", command=self.complete_sale).pack(fill="x", pady=10, ipady=8)
        ttk.Button(cart_frame, text="Clear Order", command=self.clear_cart).pack(fill="x")

    def add_selected(self):
        selected = self.menu_tree.selection()
        if not selected:
            messagebox.showwarning("Select Item", "Please select a menu item first.")
            return
        category, item, price = self.menu_tree.item(selected[0], "values")
        price = float(price)
        for entry in self.cart:
            if entry["item"] == item:
                entry["qty"] += 1
                break
        else:
            self.cart.append({"item": item, "price": price, "qty": 1})
        self.refresh_cart()

    def selected_cart_index(self):
        selected = self.cart_tree.selection()
        if not selected:
            return None
        return self.cart_tree.index(selected[0])

    def change_qty(self, delta):
        index = self.selected_cart_index()
        if index is None:
            return
        self.cart[index]["qty"] += delta
        if self.cart[index]["qty"] <= 0:
            self.cart.pop(index)
        self.refresh_cart()

    def remove_selected(self):
        index = self.selected_cart_index()
        if index is not None:
            self.cart.pop(index)
            self.refresh_cart()

    def clear_cart(self):
        self.cart.clear()
        self.refresh_cart()

    def refresh_cart(self):
        for row in self.cart_tree.get_children():
            self.cart_tree.delete(row)
        subtotal = 0
        for entry in self.cart:
            amount = entry["qty"] * entry["price"]
            subtotal += amount
            self.cart_tree.insert("", "end", values=(entry["item"], entry["qty"], f"{entry['price']:.2f}", f"{amount:.2f}"))
        tax = subtotal * 0.05
        total = subtotal + tax
        self.subtotal_var.set(f"Rs {subtotal:.2f}")
        self.tax_var.set(f"Rs {tax:.2f}")
        self.total_var.set(f"Rs {total:.2f}")

    def complete_sale(self):
        if not self.cart:
            messagebox.showwarning("Empty Order", "Add at least one item before completing the sale.")
            return
        subtotal = sum(x["qty"] * x["price"] for x in self.cart)
        tax = subtotal * 0.05
        total = subtotal + tax
        payment = self.payment_var.get()
        cur = self.conn.cursor()
        cur.execute("INSERT INTO sales(created_at, subtotal, discount, tax, total, payment_method) VALUES (?, ?, ?, ?, ?, ?)",
                    (datetime.now().isoformat(timespec="seconds"), subtotal, 0, tax, total, payment))
        sale_id = cur.lastrowid
        for x in self.cart:
            cur.execute("INSERT INTO sale_items(sale_id, item_name, qty, price) VALUES (?, ?, ?, ?)",
                        (sale_id, x["item"], x["qty"], x["price"]))
        self.conn.commit()
        messagebox.showinfo("Sale Complete", f"Sale #{sale_id}\nTotal: Rs {total:.2f}\nPayment: {payment}")
        self.clear_cart()

    def destroy(self):
        self.conn.close()
        super().destroy()


if __name__ == "__main__":
    POSApp().mainloop()
