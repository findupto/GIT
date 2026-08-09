"""Robust 80mm ESC/POS printer discovery, diagnostics and reconnect support.

Windows note: when a Bluetooth printer is paired, Windows owns the RFCOMM
service/channel and normally exposes it as an outgoing COM port. Therefore a
random RFCOMM channel cannot be used to connect through a Windows COM port.
This module discovers COM/RFCOMM mappings and supports direct RFCOMM where the
operating system exposes Bluetooth sockets.
"""
import json
import platform
import re
import socket
import subprocess
import threading
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None

COMMON_BAUDRATES = (9600, 19200, 38400, 57600, 115200)


class BluetoothPrinter:
    def __init__(self, mac="", name="", port="", channel=0, baudrate=9600):
        self.mac=(mac or "").strip().upper(); self.name=(name or "").strip(); self.port=(port or "").strip().upper()
        self.channel=int(channel or 0); self.baudrate=int(baudrate or 9600); self.connected=False
        self.sock=None; self.serial_conn=None; self._stop=False; self.last_error=""; self.last_port=""; self.last_baudrate=0

    @staticmethod
    def serial_ports():
        if not list_ports:return []
        try:return [{"port":p.device,"description":p.description or "","manufacturer":p.manufacturer or "","hwid":p.hwid or ""} for p in list_ports.comports()]
        except Exception:return []

    @staticmethod
    def _windows_registry_ports():
        """Find COM port assignments under Windows Bluetooth/RFCOMM devices."""
        if platform.system().lower()!="windows":return []
        try:
            import winreg
            root=winreg.ConnectRegistry(None,winreg.HKEY_LOCAL_MACHINE)
            base=r"SYSTEM\\CurrentControlSet\\Enum\\BTHENUM"
            out=[]
            def walk(key,path=""):
                try:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        name=winreg.EnumKey(key,i)
                        sub=winreg.OpenKey(key,name); full=path+"\\"+name
                        try:
                            for j in range(winreg.QueryInfoKey(sub)[1]):
                                vn, val, _=winreg.EnumValue(sub,j)
                                if vn.lower()=="portname" and re.match(r"^COM\\d+$",str(val),re.I):out.append((str(val).upper(),full))
                        except OSError:pass
                        walk(sub,full);winreg.CloseKey(sub)
                except OSError:pass
            k=winreg.OpenKey(root,base);walk(k,base);winreg.CloseKey(k);root.Close()
            return [{"port":p,"description":"Bluetooth RFCOMM","manufacturer":"","hwid":h} for p,h in out]
        except Exception:return []

    @staticmethod
    def discover():
        results=[]; system=platform.system().lower()
        for p in BluetoothPrinter.serial_ports():
            text=" ".join(str(p.get(k,"") or "") for k in ("port","description","manufacturer","hwid")).lower()
            if any(k in text for k in ("bluetooth","rfcomm","standard serial over bluetooth","printer")):
                results.append({"name":p["description"] or p["port"],"mac":"","port":p["port"],"hwid":p["hwid"],"type":"COM"})
        for p in BluetoothPrinter._windows_registry_ports():
            results.append({"name":p["description"],"mac":"","port":p["port"],"hwid":p["hwid"],"type":"COM"})
        try:
            if system=="windows":
                ps="Get-PnpDevice -PresentOnly | Where-Object { $_.FriendlyName -match 'Bluetooth|RFCOMM|Printer' } | Select-Object FriendlyName,InstanceId,Status | ConvertTo-Json -Compress"
                out=subprocess.check_output(["powershell","-NoProfile","-ExecutionPolicy","Bypass","-Command",ps],text=True,stderr=subprocess.DEVNULL,timeout=10)
                if out.strip():
                    data=json.loads(out);data=[data] if isinstance(data,dict) else data
                    for x in data:results.append({"name":x.get("FriendlyName","Bluetooth device"),"mac":x.get("InstanceId",""),"port":"","hwid":x.get("InstanceId",""),"type":"Bluetooth"})
            elif system=="linux":
                out=subprocess.check_output(["bluetoothctl","devices"],text=True,stderr=subprocess.DEVNULL,timeout=10)
                for line in out.splitlines():
                    p=line.split(" ",2)
                    if len(p)>=3:results.append({"name":p[2],"mac":p[1].upper(),"port":"","hwid":"","type":"Bluetooth"})
        except Exception:pass
        unique={}
        for x in results:unique[(x.get("name",""),x.get("mac",""),x.get("port",""))]=x
        return list(unique.values())

    @staticmethod
    def discover_rfcomm_channels(mac):
        """Discover RFCOMM service channels on Linux when sdptool is available."""
        mac=(mac or "").strip(); found=[]
        if not mac:return found
        try:
            out=subprocess.check_output(["sdptool","browse",mac],text=True,stderr=subprocess.DEVNULL,timeout=15)
            current=""
            for line in out.splitlines():
                if "Service Name:" in line:current=line.split(":",1)[1].strip()
                m=re.search(r"Channel:\s*(\d+)",line)
                if m:found.append({"channel":int(m.group(1)),"service":current})
        except Exception:pass
        return found

    def _connect_serial(self,port,baudrate):
        if serial is None:raise RuntimeError("pyserial is not installed.")
        self.serial_conn=serial.Serial(port=port,baudrate=baudrate,bytesize=8,parity=serial.PARITY_NONE,stopbits=1,timeout=1,write_timeout=2)
        self.port=port.upper();self.baudrate=baudrate;self.last_port=self.port;self.last_baudrate=baudrate
        self.serial_conn.write(b"\x1b@");self.serial_conn.flush();self.connected=True

    def connect(self):
        self.disconnect();self.last_error="";system=platform.system().lower()
        if system=="windows":
            if not self.port:
                self.last_error="Select the Windows Bluetooth OUTGOING COM port first. RFCOMM channel is managed by Windows."
                return False
            for baud in (self.baudrate,)+tuple(x for x in COMMON_BAUDRATES if x!=self.baudrate):
                try:self._connect_serial(self.port,baud);return True
                except Exception as e:self.last_error=f"{self.port} @ {baud}: {e}"
            return False
        if self.mac and hasattr(socket,"AF_BLUETOOTH") and hasattr(socket,"BTPROTO_RFCOMM"):
            if self.channel<=0:self.last_error="No RFCOMM channel. Use service discovery instead of guessing.";return False
            try:
                self.sock=socket.socket(socket.AF_BLUETOOTH,socket.SOCK_STREAM,socket.BTPROTO_RFCOMM);self.sock.settimeout(4);self.sock.connect((self.mac,self.channel));self.connected=True;return True
            except Exception as e:self.last_error=f"RFCOMM {self.mac}:{self.channel}: {e}";self.disconnect()
        if not self.last_error:self.last_error="No supported printer transport was found."
        return False

    def auto_detect(self,send_test=False,store_name="MK Pizza & Ice Bar"):
        """Try every OS-exposed COM port and common printer baud rates.
        This is deliberately opt-in because a successful COM open alone cannot
        prove that a cheap write-only printer is attached to that port.
        """
        candidates=[]
        seen=set()
        for p in self.serial_ports()+self._windows_registry_ports():
            if p["port"] not in seen:seen.add(p["port"]);candidates.append(p["port"])
        for port in candidates:
            for baud in COMMON_BAUDRATES:
                try:
                    self._connect_serial(port,baud)
                    if send_test:self.test_print(store_name)
                    return True
                except Exception as e:self.last_error=f"{port} @ {baud}: {e}";self.disconnect()
        self.last_error="No COM port/baud combination could be opened. Pair the printer in Windows Bluetooth settings and select its OUTGOING COM port."
        return False

    def disconnect(self):
        try:
            if self.sock:self.sock.close()
            if self.serial_conn:self.serial_conn.close()
        finally:self.sock=None;self.serial_conn=None;self.connected=False

    def send(self,data):
        if not self.connected and not self.connect():return False
        try:
            if self.serial_conn:self.serial_conn.write(data);self.serial_conn.flush()
            elif self.sock:self.sock.sendall(data)
            else:return False
            return True
        except Exception as e:self.last_error=str(e);self.disconnect();return False

    def test_print(self,store_name="MK Pizza & Ice Bar"):
        transport=(self.port or "RFCOMM").encode("ascii","replace")
        payload=b"\x1b@"+store_name.encode("utf-8","replace")+b"\n80mm ESC/POS TEST\nTransport: "+transport+b"\nBaud: "+str(self.baudrate).encode()+b"\n--------------------------------\n\n\x1dV\x00"
        return self.send(payload)

    def diagnostics(self):
        return {"connected":self.connected,"port":self.port,"mac":self.mac,"channel":self.channel,"baudrate":self.baudrate,"last_error":self.last_error,"serial_available":serial is not None,"os":platform.system()}

    def auto_reconnect(self,callback,interval=5):
        self._stop=False
        def worker():
            while not self._stop:
                if not self.connected:self.connect()
                try:callback(self.connected,self.last_error)
                except TypeError:
                    try:callback(self.connected)
                    except Exception:pass
                except Exception:pass
                time.sleep(interval)
        threading.Thread(target=worker,daemon=True,name="printer-reconnect").start()

    def stop_reconnect(self):self._stop=True;self.disconnect()
