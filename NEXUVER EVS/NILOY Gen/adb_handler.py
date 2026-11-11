import subprocess as _sp
import time
import requests
import shutil
from pathlib import Path
from typing import Optional


def _resolve_adb() -> str:
    """Return the path to adb — local platform-tools first, then system PATH."""
    
    local = Path(__file__).parent / "platform-tools" / "adb.exe"
    if local.exists():
        return str(local)
    
    found = shutil.which("adb")
    if found:
        return found
    
    return "adb"


_ADB_EXE = _resolve_adb()


class _NullLogger:
    def info(self, msg):    print(f"[INFO] {msg}")
    def success(self, msg): print(f"[OK]   {msg}")
    def warning(self, msg): print(f"[WARN] {msg}")
    def error(self, msg):   print(f"[ERR]  {msg}")
    def adb(self, msg):     print(f"[ADB]  {msg}")
    def debug(self, msg):   pass


class ADBRotator:

    def __init__(self, logger=None, device_id: str = None):
        self.enabled = False
        self._fail_count = 0
        self._MAX_FAILS  = 5
        self._serial     = device_id.strip() if device_id and device_id.strip() else None
        self._airplane_fallback = False
        self.log = logger or _NullLogger()

    def _adb(self, *args, timeout: int = 10):
        cmd = [_ADB_EXE]
        if self._serial:
            cmd.extend(['-s', self._serial])
        cmd.extend(args)
        try:
            r = _sp.run(cmd, capture_output=True, text=True, timeout=timeout)
            return r.returncode == 0, r.stdout.strip()
        except Exception:
            return False, ''

    def is_device_connected(self) -> bool:
        try:
            r = _sp.run([_ADB_EXE, 'devices'], capture_output=True, text=True, timeout=5)
            for line in r.stdout.strip().splitlines()[1:]:
                if 'device' in line and 'offline' not in line:
                    if not self._serial:
                        self._serial = line.split()[0]
                    return True
        except Exception:
            pass
        return False

    def _get_external_ip(self) -> Optional[str]:
        for url in ('https://api.ipify.org', 'https://ifconfig.me/ip'):
            try:
                r = requests.get(url, timeout=6)
                if r.status_code == 200 and r.text.strip():
                    return r.text.strip()
            except Exception:
                continue
        return None

    def _wait_for_interface(self, timeout: int = 15) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            ok, out = self._adb('shell', 'ip', 'route', 'get', '8.8.8.8')
            if ok and 'src' in out:
                return True
            time.sleep(1)
        return False

    def _data_off(self) -> bool:
        if self._airplane_fallback:
            ok, _ = self._adb('shell', 'cmd', 'connectivity', 'airplane-mode', 'enable')
            return ok
        ok, _ = self._adb('shell', 'svc', 'data', 'disable')
        if not ok:
            self._airplane_fallback = True
            return self._data_off()
        return ok

    def _data_on(self) -> bool:
        if self._airplane_fallback:
            ok, _ = self._adb('shell', 'cmd', 'connectivity', 'airplane-mode', 'disable')
            return ok
        ok, _ = self._adb('shell', 'svc', 'data', 'enable')
        if not ok:
            self._airplane_fallback = True
            return self._data_on()
        return ok

    def initialize(self) -> bool:
        try:
            result = _sp.run([_ADB_EXE, 'devices'], capture_output=True, text=True, timeout=5)
            lines = result.stdout.strip().splitlines()
            devs = [
                line for line in lines[1:]
                if line.strip() and 'offline' not in line and 'unauthorized' not in line
                and ('device' in line or 'transport' in line)
            ]
            if devs:
                detected = devs[0].split()[0]
                # Prefer config device_id if it matches, else use detected
                if self._serial and any(self._serial in line for line in devs):
                    self.log.adb(f'Using config device_id: {self._serial}')
                else:
                    self._serial = detected
                self.enabled = True
                self.log.adb(f'ADB rotation ENABLED — device: {self._serial}')
                return True
            elif self._serial:
                # Try the config device_id directly even if not in list
                ok, out = self._adb('shell', 'echo', 'ping')
                if ok and 'ping' in out:
                    self.enabled = True
                    self.log.adb(f'ADB rotation ENABLED (config serial) — device: {self._serial}')
                    return True
        except Exception as e:
            self.log.warning(f'ADB init error: {e}')

        self.enabled = False
        self.log.warning('ADB: no device detected — check USB cable, enable USB debugging, and run: adb devices')
        return False

    def rotate(self) -> bool:
        if not self.enabled:
            return False
        if not self.is_device_connected():
            self.log.warning('[ADB] Device not connected — cannot rotate')
            return False
        old_ip = self._get_external_ip() or 'unknown'
        self.log.adb(f'Rotating IP (current: {old_ip})')
        self._data_off()
        time.sleep(4)
        self._data_on()
        time.sleep(2)
        self._wait_for_interface(timeout=20)
        for _ in range(20):
            time.sleep(2)
            new_ip = self._get_external_ip()
            if new_ip and new_ip != old_ip:
                self.log.adb(f'New IP: {new_ip}')
                self._fail_count = 0
                return True
        self._fail_count += 1
        self.log.warning(f'[ADB] IP unchanged (attempt {self._fail_count}/{self._MAX_FAILS})')
        if self._fail_count >= self._MAX_FAILS:
            self.enabled = False
            self.log.error('[ADB] Sticky IP — ADB rotation DISABLED')
        return False

    def auto_switch_ip(self) -> bool:
        if not self.enabled:
            return True
        self.log.adb('Triggering ADB IP rotation...')
        return self.rotate()


if __name__ == "__main__":
    rotator = ADBRotator()
    if rotator.initialize():
        ip = rotator._get_external_ip()
        print(f"Current IP: {ip}")
        print("Rotating...")
        ok = rotator.rotate()
        print(f"Rotation {'succeeded' if ok else 'failed'}")
        new_ip = rotator._get_external_ip()
        print(f"New IP: {new_ip}")
    else:
        print("No ADB device found.")
