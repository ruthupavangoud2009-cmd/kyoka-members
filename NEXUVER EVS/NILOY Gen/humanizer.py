import os
import sys
import time
import json
import uuid
import base64
import random
import hashlib
import asyncio
import threading
from io import BytesIO
from pathlib import Path
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, quote

import primp
from colorama import Fore, Style, init
from PIL import Image
import websockets
from python_socks.async_.asyncio import Proxy

init(autoreset=True)

ROOT_DIR = Path(__file__).parent.resolve()
MATERIAL_DIR = ROOT_DIR / "humanize material"
if not MATERIAL_DIR.exists() and (ROOT_DIR / "data").exists():
    MATERIAL_DIR = ROOT_DIR / "data"

INPUT_DIR = ROOT_DIR / "input"
OUTPUT_DIR = ROOT_DIR / "output"

_CLIENT_VER = "1.0.9171"
_ELECTRON_VER = "34.5.1"
_CHROME_VER = "132"
_BUILD_HINT = 519006
_API_BASE = "https://discord.com/api/v9"
_GW_URL = "wss://gateway.discord.gg/?v=9&encoding=json"
_HOUSES = {1: "Bravery", 2: "Brilliance", 3: "Balance"}

_UA = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) discord/{_CLIENT_VER} Chrome/{_CHROME_VER}.0.0.0 Electron/{_ELECTRON_VER} Safari/537.36"

_gw_loop = asyncio.new_event_loop()
_gw_thread = threading.Thread(target=_gw_loop.run_forever, daemon=True)
_gw_thread.start()

_BUILD_NUMBER: Optional[int] = None
_BUILD_LOCK = threading.Lock()


def get_discord_build() -> int:
    global _BUILD_NUMBER
    if _BUILD_NUMBER:
        return _BUILD_NUMBER
    with _BUILD_LOCK:
        if _BUILD_NUMBER:
            return _BUILD_NUMBER
        try:
            import re
            resp = primp.Client(verify=False).get("https://discord.com/login", timeout=6)
            if resp.status_code == 200:
                hashes = re.findall(r"/assets/([a-zA-Z0-9_-]+)\.js", resp.text)
                for h in reversed(hashes):
                    try:
                        js = primp.Client(verify=False).get(f"https://discord.com/assets/{h}.js", timeout=5)
                        if js.status_code == 200:
                            m = re.search(r'buildNumber["\s:,]+(\d{4,7})', js.text)
                            if m:
                                _BUILD_NUMBER = int(m.group(1))
                                return _BUILD_NUMBER
                    except Exception:
                        pass
        except Exception:
            pass
        _BUILD_NUMBER = _BUILD_HINT
        return _BUILD_NUMBER


def make_super_properties(launch_id: str, sig: str, hb_id: str, native_build: int) -> str:
    props = {
        "os": "Windows",
        "browser": "Discord Client",
        "release_channel": "stable",
        "client_version": _CLIENT_VER,
        "os_version": "10.0.26100",
        "os_arch": "x64",
        "app_arch": "x64",
        "system_locale": "en-US",
        "has_client_mods": False,
        "browser_user_agent": _UA,
        "browser_version": _ELECTRON_VER,
        "client_build_number": get_discord_build(),
        "native_build_number": native_build,
        "client_event_source": None,
        "client_launch_id": launch_id,
        "launch_signature": sig,
        "client_heartbeat_session_id": hb_id,
    }
    return base64.b64encode(json.dumps(props, separators=(",", ":")).encode()).decode()


_AVATAR_CACHE: Dict[Path, str] = {}
_AVATAR_CACHE_LOCK = threading.Lock()


def encode_avatar(img_path: Path, dim: int = 256) -> Optional[str]:
    with _AVATAR_CACHE_LOCK:
        if img_path in _AVATAR_CACHE:
            return _AVATAR_CACHE[img_path]

    try:
        with Image.open(img_path) as img:
            is_png = img_path.suffix.lower() == ".png"
            if is_png and img.mode == "P":
                img = img.convert("RGBA")
            elif not is_png and img.mode in ["RGBA", "P"]:
                img = img.convert("RGB")
            img = img.resize((dim, dim), Image.Resampling.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="PNG" if is_png else "JPEG", optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode()
            mime = "image/png" if is_png else "image/jpeg"
            uri = f"data:{mime};base64,{b64}"
            with _AVATAR_CACHE_LOCK:
                _AVATAR_CACHE[img_path] = uri
            return uri
    except Exception:
        return None


def load_materials(data_dir: Optional[Path] = None) -> Dict[str, List[Any]]:
    target = data_dir or MATERIAL_DIR
    target.mkdir(parents=True, exist_ok=True)

    def _lines(fname: str) -> List[str]:
        fp = target / fname
        if not fp.exists():
            return []
        try:
            return [l.strip() for l in fp.read_text(encoding="utf-8").splitlines() if l.strip() and not l.strip().startswith("#")]
        except Exception:
            return []

    avatars_dir = target / "avatars"
    avatars_dir.mkdir(parents=True, exist_ok=True)
    valid_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    avatar_files = [f for f in avatars_dir.iterdir() if f.suffix.lower() in valid_exts] if avatars_dir.exists() else []

    return {
        "names": _lines("names.txt"),
        "bios": _lines("bio.txt"),
        "pronouns": _lines("pronoun.txt"),
        "avatars": avatar_files,
    }


def parse_proxy(raw: str) -> Optional[str]:
    p = raw.strip()
    if not p or p.startswith("#"):
        return None
    if "://" in p:
        parsed = urlparse(p)
        return p if (parsed.hostname and parsed.port) else None
    if "@" in p:
        at = p.rfind("@")
        auth, hp = p[:at], p[at + 1:]
        ci = auth.find(":")
        if ci == -1:
            return None
        return f"http://{quote(auth[:ci], safe='')}:{quote(auth[ci + 1:], safe='')}@{hp}"
    parts = p.split(":")
    if len(parts) == 4:
        return f"http://{quote(parts[2], safe='')}:{quote(parts[3], safe='')}@{parts[0]}:{parts[1]}"
    if len(parts) == 2:
        return f"http://{parts[0]}:{parts[1]}"
    return None


class Humanizer:
    def __init__(self, token: str, proxy: Optional[str] = None):
        self.token = token.strip().replace('"', "")
        self.proxy = proxy
        self.locked = False
        self._sess_id: Optional[str] = None
        self._client = primp.Client(verify=False, proxy=proxy or None)
        self._install_id = f"{random.randint(10**18, 10**19 - 1)}." + "".join(random.choices("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_", k=22))
        self._native = random.randint(65600, 65800)
        self._sprops = make_super_properties(str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4()), self._native)

    def get_headers(self) -> Dict[str, str]:
        hdrs = {
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en-US",
            "authorization": self.token,
            "content-type": "application/json",
            "user-agent": _UA,
            "x-debug-options": "bugReporterEnabled",
            "x-discord-locale": "en-US",
            "x-discord-timezone": "America/New_York",
            "x-installation-id": self._install_id,
            "x-super-properties": self._sprops,
        }
        fp = self._get_fingerprint()
        if fp:
            hdrs["x-fingerprint"] = fp
        return hdrs

    def _get_fingerprint(self) -> Optional[str]:
        try:
            r = self._client.get(f"{_API_BASE}/experiments", timeout=4)
            if r.status_code == 200:
                return r.json().get("fingerprint")
        except Exception:
            pass
        return None

    def _call(self, method: str, url: str, data: Dict, hdrs: Dict) -> Dict[str, Any]:
        if self.locked:
            return {"success": False, "error": "Token locked"}
        for _ in range(3):
            try:
                fn = self._client.post if method.upper() == "POST" else self._client.patch
                resp = fn(url, headers=hdrs, json=data, timeout=30)
                if resp.status_code in (200, 204):
                    try:
                        return {"success": True, "data": resp.json() if resp.text else {}}
                    except Exception:
                        return {"success": True, "data": {}}
                try:
                    ed = resp.json() if resp.text else {}
                except Exception:
                    ed = {}
                if resp.status_code == 400 and isinstance(ed, dict) and ed.get("code") == 10020:
                    return {"success": False, "unknown_session": True, "error": "Unknown Session"}
                if resp.status_code == 429:
                    time.sleep(float(resp.headers.get("retry-after") or 1.5))
                    continue
                if resp.status_code in (401, 403):
                    self.locked = True
                    return {"success": False, "error": f"Locked ({resp.status_code})"}
                return {"success": False, "error": ed or f"HTTP {resp.status_code}"}
            except Exception as ex:
                time.sleep(1.0)
        return {"success": False, "error": "Request failed"}

    def update_user_profile(self, payload: Dict, hdrs: Dict) -> Dict[str, Any]:
        return self._call("patch", f"{_API_BASE}/users/@me", payload, hdrs)

    def update_profile_fields(self, payload: Dict, hdrs: Dict) -> Dict[str, Any]:
        return self._call("patch", f"{_API_BASE}/users/@me/profile", payload, hdrs)

    async def _gw_identify(self, ws) -> bool:
        try:
            hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if hello.get("op") != 10:
                return False
            payload = {
                "op": 2,
                "d": {
                    "token": self.token,
                    "capabilities": 16381,
                    "properties": {
                        "os": "Windows",
                        "browser": "Discord Client",
                        "release_channel": "stable",
                        "client_version": _CLIENT_VER,
                        "os_version": "10.0.26100",
                        "os_arch": "x64",
                        "app_arch": "x64",
                        "system_locale": "en-US",
                        "browser_user_agent": _UA,
                        "browser_version": _ELECTRON_VER,
                        "os_sdk_version": "26100",
                        "client_build_number": get_discord_build(),
                        "native_build_number": self._native,
                        "client_event_source": None,
                        "design_id": 0,
                    },
                    "presence": {"status": "online", "since": 0, "activities": [], "afk": False},
                    "compress": False,
                    "client_state": {"guild_versions": {}, "highest_last_message_id": "0", "read_state_version": 0, "user_guild_settings_version": -1, "user_settings_version": -1, "private_channels_version": "0", "api_code_version": 0},
                },
            }
            await ws.send(json.dumps(payload))
            return True
        except Exception:
            return False

    async def _gw_ready(self, ws) -> bool:
        try:
            for _ in range(10):
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
                if msg.get("t") == "READY":
                    self._sess_id = msg["d"].get("session_id")
                    return True
                if msg.get("op") == 9:
                    return False
        except Exception:
            pass
        return False

    async def _apply_with_session(self, payload: Dict) -> Dict[str, Any]:
        if self.locked:
            return {"success": False, "error": "Token locked"}
        hdrs = self.get_headers()
        loop = asyncio.get_event_loop()

        if "avatar" not in payload:
            direct = await loop.run_in_executor(None, lambda: self.update_user_profile(payload, hdrs))
            if direct.get("success") or not direct.get("unknown_session"):
                return direct

        async def _ws_flow(ws):
            if not await self._gw_identify(ws) or not await self._gw_ready(ws):
                return {"success": False, "error": "Gateway handshake failed"}
            return await loop.run_in_executor(None, lambda: self.update_user_profile(payload, hdrs))

        extras = {"User-Agent": _UA}
        try:
            if self.proxy:
                sock = await Proxy.from_url(self.proxy).connect(dest_host="gateway.discord.gg", dest_port=443)
                async with websockets.connect(_GW_URL, additional_headers=extras, sock=sock, server_hostname="gateway.discord.gg", open_timeout=25, close_timeout=5) as ws:
                    return await _ws_flow(ws)
            else:
                async with websockets.connect(_GW_URL, additional_headers=extras, open_timeout=25, close_timeout=5) as ws:
                    return await _ws_flow(ws)
        except Exception as ex:
            return {"success": False, "error": f"Gateway error: {ex}"}

    def update_account_sync(self, payload: Dict) -> Dict[str, Any]:
        try:
            return asyncio.run_coroutine_threadsafe(self._apply_with_session(payload), _gw_loop).result(timeout=40)
        except Exception as ex:
            return {"success": False, "error": str(ex)}

    def set_hypesquad(self, house_id: int, hdrs: Dict) -> Dict[str, Any]:
        hname = _HOUSES.get(house_id, "Unknown")
        try:
            chk = self._client.get(f"{_API_BASE}/users/@me", headers=hdrs, timeout=12)
            if chk.status_code == 200 and (chk.json().get("flags", 0) & 14):
                return {"success": True, "house": hname, "already_set": True}
        except Exception:
            pass
        res = self._call("post", f"{_API_BASE}/hypesquad/online", {"house_id": house_id}, hdrs)
        return {"success": True, "house": hname} if res.get("success") else {"success": False, "error": f"HypeSquad failed", "house": hname}

    def process(
        self,
        names: Optional[List[str]] = None,
        bios: Optional[List[str]] = None,
        pronouns: Optional[List[str]] = None,
        avatars: Optional[List[Path]] = None,
        cfg: Optional[Dict[str, bool]] = None,
    ) -> Dict[str, Any]:
        cfg = cfg or {}
        hdrs = self.get_headers()
        results: Dict[str, Any] = {"success": True, "details": {}}

        acct_payload = {}
        if cfg.get("name", True) and names:
            name_val = random.choice(names)
            acct_payload["global_name"] = name_val
            results["details"]["name"] = name_val

        if cfg.get("avatar", True) and avatars:
            av_file = random.choice(avatars)
            av_b64 = encode_avatar(av_file)
            if av_b64:
                acct_payload["avatar"] = av_b64
                acct_payload["avatar_description"] = f"{hashlib.md5(av_b64[:100].encode()).hexdigest()}, set {time.strftime('%B %d, %Y')}"
                results["details"]["avatar"] = av_file.name

        if acct_payload:
            res = self.update_account_sync(acct_payload) if "avatar" in acct_payload else self.update_user_profile(acct_payload, hdrs)
            if not res.get("success"):
                results["success"] = False
                results["details"]["account_error"] = res.get("error")

        prof_payload = {}
        if cfg.get("bio", True) and bios:
            bio_val = random.choice(bios)
            prof_payload["bio"] = bio_val
            results["details"]["bio"] = bio_val

        if cfg.get("pronouns", True) and pronouns:
            prn_val = random.choice(pronouns)
            prof_payload["pronouns"] = prn_val
            results["details"]["pronouns"] = prn_val

        if prof_payload:
            res = self.update_profile_fields(prof_payload, hdrs)
            if not res.get("success"):
                results["success"] = False
                results["details"]["profile_error"] = res.get("error")

        if cfg.get("hypesquad", True):
            hid = random.choice([1, 2, 3])
            res = self.set_hypesquad(hid, hdrs)
            if res.get("success"):
                results["details"]["hypesquad"] = res.get("house")
            else:
                results["success"] = False
                results["details"]["hypesquad_error"] = res.get("error")

        return results


def humanize_token(token: str, proxy: Optional[str] = None, config: Optional[Dict] = None) -> bool:
    cfg = config or {}
    hmz_cfg = cfg.get("humanizer", {})
    if isinstance(hmz_cfg, bool):
        if not hmz_cfg:
            return False
        hmz_cfg = {}
    elif not hmz_cfg.get("enabled", True):
        return False

    materials = load_materials()
    h = Humanizer(token=token, proxy=proxy)
    res = h.process(
        names=materials.get("names"),
        bios=materials.get("bios"),
        pronouns=materials.get("pronouns"),
        avatars=materials.get("avatars"),
        cfg=hmz_cfg,
    )
    return res.get("success", False)
