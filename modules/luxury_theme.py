"""Premium dark-gold Tkinter theme used by the POS UI."""
import tkinter as tk
from tkinter import ttk


def apply(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    bg = "#0b0d10"
    panel = "#14181d"
    card = "#1b2027"
    fg = "#f5f2e9"
    muted = "#a7adb7"
    accent = "#d7ad5b"
    accent2 = "#b88a35"
    root.configure(bg=bg)
    style.configure(".", background=panel, foreground=fg, font=("Segoe UI", 10))
    style.configure("TFrame", background=bg)
    style.configure("TLabelframe", background=panel, foreground=accent, borderwidth=1, relief="solid")
    style.configure("TLabelframe.Label", background=panel, foreground=accent, font=("Segoe UI Semibold", 10))
    style.configure("TLabel", background=bg, foreground=fg)
    style.configure("TNotebook", background=bg, borderwidth=0)
    style.configure("TNotebook.Tab", background=panel, foreground=muted, padding=(16, 9), font=("Segoe UI Semibold", 10))
    style.map("TNotebook.Tab", background=[("selected", card)], foreground=[("selected", accent)])
    style.configure("TButton", background=card, foreground=fg, padding=(12, 8), borderwidth=0, font=("Segoe UI Semibold", 9))
    style.map("TButton", background=[("active", accent2), ("pressed", accent)], foreground=[("active", "#ffffff")])
    style.configure("Accent.TButton", background=accent, foreground="#111111", padding=(14, 9), font=("Segoe UI Bold", 10))
    style.map("Accent.TButton", background=[("active", accent2)])
    style.configure("TEntry", fieldbackground="#0f1216", foreground=fg, insertcolor=fg, borderwidth=1, padding=7)
    style.configure("TCombobox", fieldbackground="#0f1216", foreground=fg, background=card, padding=6)
    style.configure("Treeview", background="#0f1216", fieldbackground="#0f1216", foreground=fg, rowheight=30, borderwidth=0)
    style.configure("Treeview.Heading", background=card, foreground=accent, font=("Segoe UI Semibold", 9), padding=8)
    style.map("Treeview", background=[("selected", "#4b3920")], foreground=[("selected", "#ffffff")])
    style.configure("Horizontal.TScrollbar", background=card, troughcolor=bg)
    style.configure("Vertical.TScrollbar", background=card, troughcolor=bg)
    root.option_add("*TearOff", False)
    return style


def install():
    """Patch Tk/Toplevel creation so the premium theme is applied automatically."""
    original_tk_init = tk.Tk.__init__
    original_top_init = tk.Toplevel.__init__
    def tk_init(self, *args, **kwargs):
        original_tk_init(self, *args, **kwargs)
        apply(self)
    def top_init(self, *args, **kwargs):
        original_top_init(self, *args, **kwargs)
        apply(self)
    if not getattr(tk.Tk, "_luxury_theme_installed", False):
        tk.Tk.__init__ = tk_init
        tk.Tk._luxury_theme_installed = True
        tk.Toplevel.__init__ = top_init

install()
