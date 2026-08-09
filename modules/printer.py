import platform,socket,subprocess,threading
try:
    import serial
except ImportError:
    serial=None

class BluetoothPrinter:
    def __init__(self,mac='',name='',port='',channel=1):
        self.mac=mac.strip();self.name=name.strip();self.port=port.strip();self.channel=int(channel or 1);self.connected=False;self.sock=None;self.serial_conn=None
    @staticmethod
    def discover():
        results=[];system=platform.system().lower()
        try:
            if system=='windows':
                ps="Get-PnpDevice -PresentOnly | Where-Object { $_.Class -match 'Bluetooth' } | Select-Object FriendlyName,InstanceId | ConvertTo-Json -Compress"
                import json
                out=subprocess.check_output(['powershell','-NoProfile','-Command',ps],text=True,stderr=subprocess.DEVNULL,timeout=8)
                if out.strip():
                    data=json.loads(out);data=[data] if isinstance(data,dict) else data
                    for x in data:results.append({'name':x.get('FriendlyName','Bluetooth device'),'mac':x.get('InstanceId',''),'port':''})
            elif system=='linux':
                out=subprocess.check_output(['bluetoothctl','devices'],text=True,stderr=subprocess.DEVNULL,timeout=8)
                for line in out.splitlines():
                    p=line.split(' ',2)
                    if len(p)>=3:results.append({'name':p[2],'mac':p[1],'port':''})
        except Exception:pass
        return results
    def connect(self):
        system=platform.system().lower()
        if self.port and system=='windows':
            if serial is None:return False
            try:self.serial_conn=serial.Serial(self.port,9600,timeout=2);self.connected=True;return True
            except Exception:self.connected=False;return False
        if not self.mac:return False
        try:
            self.sock=socket.socket(socket.AF_BLUETOOTH,socket.SOCK_STREAM,socket.BTPROTO_RFCOMM);self.sock.connect((self.mac,self.channel));self.connected=True;return True
        except Exception:
            self.connected=False
            try:
                if self.sock:self.sock.close()
            except Exception:pass
            self.sock=None;return False
    def disconnect(self):
        try:
            if self.sock:self.sock.close()
            if self.serial_conn:self.serial_conn.close()
        finally:self.sock=None;self.serial_conn=None;self.connected=False
    def send(self,data):
        if not self.connected and not self.connect():return False
        try:
            if self.serial_conn:self.serial_conn.write(data)
            elif self.sock:self.sock.sendall(data)
            else:return False
            return True
        except Exception:self.disconnect();return False
    def test_print(self,store_name='MK Pizza & Ice Bar'):
        return self.send(b'\x1b@'+store_name.encode('utf-8','replace')+b'\n80mm Bluetooth Printer Test\n--------------------------------\n\n\x1dV\x00')
    def auto_reconnect(self,callback,interval=5):
        def worker():
            while True:
                if not self.connected:self.connect()
                try:callback(self.connected)
                except Exception:pass
                threading.Event().wait(interval)
        threading.Thread(target=worker,daemon=True).start()
