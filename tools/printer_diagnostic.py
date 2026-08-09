"""Standalone 80mm Bluetooth/RFCOMM printer diagnostic.
Run: python tools/printer_diagnostic.py
"""
import tkinter as tk
from tkinter import ttk, messagebox
from modules.printer import BluetoothPrinter

root=tk.Tk();root.title("MK POS • Thermal Printer Diagnostics");root.geometry("980x620")
status=tk.StringVar(value="Ready")
t=ttk.Treeview(root,columns=("name","mac","port","type","hwid"),show="headings")
for c,w in (("name",240),("mac",220),("port",90),("type",100),("hwid",280)):
    t.heading(c,text=c.title());t.column(c,width=w)
t.pack(fill="both",expand=True,padx=12,pady=12)


def scan():
    for x in t.get_children():t.delete(x)
    rows=BluetoothPrinter.discover()
    for x in rows:t.insert("","end",values=(x.get("name",""),x.get("mac",""),x.get("port",""),x.get("type",""),x.get("hwid","")))
    status.set(f"Found {len(rows)} Bluetooth/COM entries. On Windows select the OUTGOING COM port created for the printer.")


def test():
    s=t.selection()
    if not s:return messagebox.showwarning("Select","Select a printer/COM port first.")
    v=t.item(s[0],"values");p=BluetoothPrinter(mac=v[1],name=v[0],port=v[2],channel=0)
    ok=p.test_print("MK Pizza & Ice Bar")
    status.set(("SUCCESS — test receipt sent." if ok else "FAILED — "+p.last_error)+" Diagnostics: "+str(p.diagnostics()))
    p.disconnect()


def auto():
    p=BluetoothPrinter();status.set("Trying every exposed COM port and common baud rates...");root.update_idletasks()
    ok=p.auto_detect(send_test=True)
    status.set(("AUTO-DETECT SUCCESS: "+p.port+" @ "+str(p.baudrate) if ok else "AUTO-DETECT FAILED: "+p.last_error))
    if ok:messagebox.showinfo("Printer detected",f"Printer transport opened: {p.port} @ {p.baudrate}. Save this COM port in POS Settings.")
    p.disconnect()

b=ttk.Frame(root);b.pack(fill="x",padx=12,pady=(0,12))
ttk.Button(b,text="SCAN BLUETOOTH / COM",command=scan).pack(side="left",padx=4)
ttk.Button(b,text="TEST SELECTED",command=test).pack(side="left",padx=4)
ttk.Button(b,text="AUTO-DETECT + TEST",command=auto).pack(side="left",padx=4)
tk.Label(root,textvariable=status,anchor="w").pack(fill="x",padx=12,pady=(0,12))
scan();root.mainloop()
