import os
import platform
import socket
import subprocess
import threading

class BluetoothPrinter:
    """Best-effort Bluetooth/ESC-POS helper.

    Discovery uses OS tools when available. RFCOMM printing is used on Linux/macOS
    when a Bluetooth MAC is supplied. Windows users can select the printer's
    Bluetooth-created COM port in the Settings module.
    """
    def __init__(self, mac='', name='', port='', channel=1):
        self.mac = mac.strip()
        self.name = name.strip()
        self.port = port.strip()
        self.channel = int(channel or 1)
        self.connected = False
        self.sock = None

    @staticmethod
    def discover():
        results = []
        system = platform.system().lower()
        try:
            if system == 'windows':
                ps = ("Get-PnpDevice -PresentOnly | Where-Object { $_.Class -match 'Bluetooth' } | "
                      "Select-Object FriendlyName,InstanceId | ConvertTo-Json -Compress")
                out = subprocess.check_output(['powershell','-NoProfile','-Command',ps], text=True, stderr=subprocess.DEVNULL, timeout=8)
                if out.strip():
                    import json
                    data=json.loads(out)
                    if isinstance(data,dict): data=[data]
                    for x in data: results.append({'name':x.get('FriendlyName','Bluetooth device'),'mac':x.get('InstanceId',''),'port':''})
            elif system == 'linux':
                out=subprocess.check_output(['bluetoothctl','devices'],text=True,stderr=subprocess.DEVNULL,timeout=8)
                for line in out.splitlines():
                    p=line.split(' ',2)
                    if len(p)>=3: results.append({'name':p[2],'mac':p[1],'port':''})
            elif system == 'darwin':
                # macOS does not expose a stable built-in CLI discovery API; keep configured devices.
                pass
        except Exception:
            pass
        return results

    def connect(self):
        if self.port and platform.system().lower() == 'windows':
            self.connected = os.path.exists(self.port.upper())
            return self.connected
        if not self.mac:
            return False
        try:
            self.sock=socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            self.sock.connect((self.mac,self.channel)); self.connected=True; return True
        except Exception:
            self.connected=False
            try:
                if self.sock: self.sock.close()
            except Exception: pass
            self.sock=None
            return False

    def disconnect(self):
        try:
            if self.sock: self.sock.close()
        finally:
            self.sock=None; self.connected=False

    def send(self, data):
        if not self.connected and not self.connect(): return False
        try:
            if self.sock: self.sock.sendall(data); return True
        except Exception:
            self.disconnect()
        return False

    def test_print(self, store_name='MK Pizza & Ice Bar'):
        payload=(b'\x1b@'+store_name.encode('utf-8','replace')+b'\n'
                 +b'Bluetooth 80mm Printer Test\n'
                 +b'--------------------------------\n\n\x1dV\x00')
        return self.send(payload)

    def auto_reconnect(self, callback, interval=5):
        def worker():
            while True:
                if not self.connected: self.connect()
                try: callback(self.connected)
                except Exception: pass
                threading.Event().wait(interval)
        threading.Thread(target=worker,daemon=True).start()
