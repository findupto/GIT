import platform, socket, subprocess, threading
try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial=None; list_ports=None

class BluetoothPrinter:
    """ESC/POS 80mm Bluetooth helper with OS discovery and reconnect."""
    def __init__(self,mac='',name='',port='',channel=1,baudrate=9600):
        self.mac=mac.strip(); self.name=name.strip(); self.port=port.strip(); self.channel=int(channel or 1); self.baudrate=int(baudrate or 9600)
        self.connected=False; self.sock=None; self.serial_conn=None; self._stop=False
    @staticmethod
    def discover():
        results=[]; system=platform.system().lower()
        try:
            if system=='windows':
                if list_ports:
                    for p in list_ports.comports():
                        text=' '.join(str(x or '') for x in (p.description,p.manufacturer,p.hwid)).lower()
                        if 'bluetooth' in text or 'standard serial over bluetooth' in text or 'printer' in text:
                            results.append({'name':p.description or p.device,'mac':'','port':p.device,'hwid':p.hwid or ''})
                ps="Get-PnpDevice -PresentOnly | Where-Object { $_.Class -match 'Bluetooth' } | Select-Object FriendlyName,InstanceId | ConvertTo-Json -Compress"
                import json
                out=subprocess.check_output(['powershell','-NoProfile','-Command',ps],text=True,stderr=subprocess.DEVNULL,timeout=8)
                if out.strip():
                    data=json.loads(out); data=[data] if isinstance(data,dict) else data
                    for x in data: results.append({'name':x.get('FriendlyName','Bluetooth device'),'mac':x.get('InstanceId',''),'port':'','hwid':''})
            elif system=='linux':
                out=subprocess.check_output(['bluetoothctl','devices'],text=True,stderr=subprocess.DEVNULL,timeout=8)
                for line in out.splitlines():
                    p=line.split(' ',2)
                    if len(p)>=3: results.append({'name':p[2],'mac':p[1],'port':'','hwid':''})
        except Exception: pass
        # de-duplicate while preserving the best port information
        unique={}
        for x in results: unique[(x.get('name',''),x.get('mac',''),x.get('port',''))]=x
        return list(unique.values())
    def connect(self):
        system=platform.system().lower()
        if self.port and system=='windows':
            if serial is None:return False
            try:
                self.serial_conn=serial.Serial(self.port,self.baudrate,timeout=2); self.connected=True; return True
            except Exception:
                self.connected=False; return False
        if not self.mac:return False
        try:
            self.sock=socket.socket(socket.AF_BLUETOOTH,socket.SOCK_STREAM,socket.BTPROTO_RFCOMM); self.sock.connect((self.mac,self.channel)); self.connected=True; return True
        except Exception:
            self.connected=False
            try:
                if self.sock:self.sock.close()
            except Exception:pass
            self.sock=None; return False
    def disconnect(self):
        try:
            if self.sock:self.sock.close()
            if self.serial_conn:self.serial_conn.close()
        finally:self.sock=None; self.serial_conn=None; self.connected=False
    def send(self,data):
        if not self.connected and not self.connect():return False
        try:
            if self.serial_conn:self.serial_conn.write(data); self.serial_conn.flush()
            elif self.sock:self.sock.sendall(data)
            else:return False
            return True
        except Exception:
            self.disconnect(); return False
    def test_print(self,store_name='MK Pizza & Ice Bar'):
        payload=b'\x1b@'+store_name.encode('utf-8','replace')+b'\n80mm Bluetooth Printer Test\n--------------------------------\n\n\x1dV\x00'
        return self.send(payload)
    def auto_reconnect(self,callback,interval=5):
        self._stop=False
        def worker():
            while not self._stop:
                if not self.connected:self.connect()
                try:callback(self.connected)
                except Exception:pass
                threading.Event().wait(interval)
        threading.Thread(target=worker,daemon=True,name='printer-reconnect',).start()
    def stop_reconnect(self): self._stop=True
