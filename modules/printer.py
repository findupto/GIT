"""Robust 80mm ESC/POS printer discovery, diagnostics and reconnect support.

Important: on Windows, a paired Bluetooth printer normally exposes an outgoing
RFCOMM service as a COM port. The RFCOMM channel is owned by Windows and must
not be guessed or changed arbitrarily. This module therefore discovers COM
ports first, tests them at common printer baud rates, and only uses a direct
RFCOMM socket on platforms that expose Bluetooth sockets.
"""
import json
import platform
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
        self.mac = (mac or "").strip().upper()
        self.name = (name or "").strip()
        self.port = (port or "").strip().upper()
        self.channel = int(channel or 0)
        self.baudrate = int(baudrate or 9600)
        self.connected = False
        self.sock = None
        self.serial_conn = None
        self._stop = False
        self.last_error = ""
        self.last_port = ""
        self.last_baudrate = 0

    @staticmethod
    def discover():
        """Return Bluetooth devices and usable serial ports exposed by the OS."""
        results = []
        system = platform.system().lower()
        if list_ports:
            try:
                for p in list_ports.comports():
                    text = " ".join(str(x or "") for x in (p.device, p.description, p.manufacturer, p.hwid)).lower()
                    if any(k in text for k in ("bluetooth", "rfcomm", "standard serial over bluetooth", "printer")):
                        results.append({"name": p.description or p.device, "mac": "", "port": p.device, "hwid": p.hwid or "", "type": "COM"})
            except Exception:
                pass
        try:
            if system == "windows":
                ps = "Get-PnpDevice -PresentOnly | Where-Object { $_.FriendlyName -match 'Bluetooth|RFCOMM|Printer' } | Select-Object FriendlyName,InstanceId,Status | ConvertTo-Json -Compress"
                out = subprocess.check_output(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], text=True, stderr=subprocess.DEVNULL, timeout=10)
                if out.strip():
                    data = json.loads(out)
                    data = [data] if isinstance(data, dict) else data
                    for x in data:
                        results.append({"name": x.get("FriendlyName", "Bluetooth device"), "mac": x.get("InstanceId", ""), "port": "", "hwid": x.get("InstanceId", ""), "type": "Bluetooth"})
            elif system == "linux":
                out = subprocess.check_output(["bluetoothctl", "devices"], text=True, stderr=subprocess.DEVNULL, timeout=10)
                for line in out.splitlines():
                    p = line.split(" ", 2)
                    if len(p) >= 3:
                        results.append({"name": p[2], "mac": p[1].upper(), "port": "", "hwid": "", "type": "Bluetooth"})
        except Exception:
            pass
        unique = {}
        for x in results:
            key = (x.get("name", ""), x.get("mac", ""), x.get("port", ""))
            unique[key] = x
        return list(unique.values())

    @staticmethod
    def serial_ports():
        if not list_ports:
            return []
        try:
            return [{"port": p.device, "description": p.description, "manufacturer": p.manufacturer or "", "hwid": p.hwid or ""} for p in list_ports.comports()]
        except Exception:
            return []

    @staticmethod
    def _looks_like_printer(data):
        if not data:
            return False
        blob = bytes(data)
        # ESC/POS status/query responses are short; many receipt printers also
        # return an ASCII identity/status string. Any readable response is a
        # useful diagnostic signal, but absence of a response does not prove
        # the printer is unusable because most cheap printers are write-only.
        return any(32 <= b < 127 for b in blob) or len(blob) <= 64

    def _connect_serial(self, port, baudrate):
        if serial is None:
            raise RuntimeError("pyserial is not installed.")
        self.serial_conn = serial.Serial(port=port, baudrate=baudrate, bytesize=8, parity=serial.PARITY_NONE, stopbits=1, timeout=1, write_timeout=2)
        self.port, self.baudrate = port.upper(), baudrate
        self.last_port, self.last_baudrate = self.port, baudrate
        self.serial_conn.write(b"\x1b@\n")
        self.serial_conn.flush()
        self.connected = True

    def connect(self, probe=True):
        self.disconnect()
        self.last_error = ""
        system = platform.system().lower()
        # Windows: COM is the correct transport once Bluetooth pairing created
        # an outgoing RFCOMM COM port. The channel is not used for COM ports.
        if system == "windows" and self.port:
            try:
                self._connect_serial(self.port, self.baudrate)
                return True
            except Exception as e:
                self.last_error = f"{self.port} @ {self.baudrate}: {e}"
                return False
        if system == "windows" and not self.port:
            ports = self.serial_ports()
            candidates = [p["port"] for p in ports]
            for port in candidates:
                for baud in (self.baudrate,) + tuple(x for x in COMMON_BAUDRATES if x != self.baudrate):
                    try:
                        self._connect_serial(port, baud)
                        return True
                    except Exception as e:
                        self.last_error = f"{port} @ {baud}: {e}"
                        self.disconnect()
        # Linux/macOS where Python exposes RFCOMM sockets.
        if self.mac and hasattr(socket, "AF_BLUETOOTH") and hasattr(socket, "BTPROTO_RFCOMM"):
            if self.channel <= 0:
                self.last_error = "RFCOMM channel is not configured. Discover the printer service channel first."
                return False
            try:
                self.sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
                self.sock.settimeout(4)
                self.sock.connect((self.mac, self.channel))
                self.connected = True
                return True
            except Exception as e:
                self.last_error = f"RFCOMM {self.mac}:{self.channel}: {e}"
                self.disconnect()
        if not self.last_error:
            self.last_error = "No supported printer transport was found."
        return False

    def disconnect(self):
        try:
            if self.sock:
                self.sock.close()
            if self.serial_conn:
                self.serial_conn.close()
        finally:
            self.sock = None
            self.serial_conn = None
            self.connected = False

    def send(self, data):
        if not self.connected and not self.connect():
            return False
        try:
            if self.serial_conn:
                self.serial_conn.write(data)
                self.serial_conn.flush()
            elif self.sock:
                self.sock.sendall(data)
            else:
                return False
            return True
        except Exception as e:
            self.last_error = str(e)
            self.disconnect()
            return False

    def test_print(self, store_name="MK Pizza & Ice Bar"):
        payload = b"\x1b@" + store_name.encode("utf-8", "replace") + b"\n80mm ESC/POS TEST\nTransport: " + (self.port or "RFCOMM") .encode("ascii", "replace") + b"\nBaud: " + str(self.baudrate).encode() + b"\n--------------------------------\n\n\x1dV\x00"
        return self.send(payload)

    def diagnostics(self):
        return {"connected": self.connected, "port": self.port, "mac": self.mac, "channel": self.channel, "baudrate": self.baudrate, "last_error": self.last_error, "serial_available": serial is not None, "os": platform.system()}

    def auto_reconnect(self, callback, interval=5):
        self._stop = False
        def worker():
            while not self._stop:
                if not self.connected:
                    self.connect()
                try:
                    callback(self.connected, self.last_error)
                except TypeError:
                    try:
                        callback(self.connected)
                    except Exception:
                        pass
                except Exception:
                    pass
                time.sleep(interval)
        threading.Thread(target=worker, daemon=True, name="printer-reconnect").start()

    def stop_reconnect(self):
        self._stop = True
        self.disconnect()
