import sys
import warnings
warnings.filterwarnings('ignore')

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import asyncio
import math
import subprocess
from datetime import datetime, timezone
import hashlib
import os
import shutil
from pathlib import Path
import platform
import re
import threading
import time
import json
import random
import string
import signal
import socket
import tempfile
import zipfile
import io
from typing import Optional, Dict, Tuple
import requests
import httpx
import tls_client
from colorama import Fore, Style, init
from pystyle import Center
from rich.console import Console
import warnings
try:
    import nodriver as uc
    from nodriver import cdp
    import nodriver.cdp.input_ as cdp_input
except ImportError:
    import truedriver as uc
    from truedriver import cdp
    import truedriver.cdp.input_ as cdp_input
import urllib3
import base64
import imaplib
import email as email_lib
from curl_cffi import requests as cffi_requests


def safe_clean_cache():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    folders_to_delete = [".browser_cache", "__pycache__"]
    for folder_name in folders_to_delete:
        folder_path = os.path.join(base_dir, folder_name)
        if os.path.exists(folder_path):
            try:
                shutil.rmtree(folder_path)
                print(f"[Clean] Successfully removed: {folder_name}")
            except Exception:
                pass


_SCREEN_W, _SCREEN_H = 1920, 1080
try:
    _res = subprocess.check_output(
        ['powershell', '-NoProfile', '-NonInteractive', '-Command',
         'Add-Type -AssemblyName System.Windows.Forms; '
         '[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width.ToString()'
         ' + "x" + '
         '[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height.ToString()'],
        text=True, timeout=4
    ).strip()
    _w, _h = map(int, _res.split('x'))
    if _w > 800 and _h > 600:
        _SCREEN_W, _SCREEN_H = _w, _h
except Exception:
    pass


def get_window_rect(slot: int, total: int):
    TASKBAR = 50
    cols  = min(max(total, 1), 4)
    rows  = math.ceil(max(total, 1) / cols)
    win_w = _SCREEN_W // cols
    win_h = (_SCREEN_H - TASKBAR) // rows
    col   = (slot - 1) % cols
    row   = (slot - 1) // cols
    return col * win_w, row * win_h, win_w, win_h


async def _cdp_key(tab, key: str, code: str, keycode: int):
    try:
        await tab.send(
            cdp.input_.dispatch_key_event(
                type_="keyDown", key=key, code=code,
                windows_virtual_key_code=keycode,
                native_virtual_key_code=keycode,
            )
        )
        await asyncio.sleep(0.05)
        await tab.send(
            cdp.input_.dispatch_key_event(
                type_="keyUp", key=key, code=code,
                windows_virtual_key_code=keycode,
                native_virtual_key_code=keycode,
            )
        )
    except Exception:
        pass


BROWSER_CONFIG = {
    "brave": {
        "name": "Brave",
        "paths": [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\BraveSoftware\Brave-Browser\Application\brave.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\BraveSoftware\Brave-Browser\Application\brave.exe"),
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/usr/bin/brave-browser",
            "/usr/bin/brave",
            "/snap/bin/brave",
        ],
    },
    "edge": {
        "name": "Microsoft Edge",
        "paths": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe"),
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/usr/bin/microsoft-edge",
            "/usr/bin/microsoft-edge-stable",
            "/usr/bin/edge",
        ],
    },
    "chrome": {
        "name": "Google Chrome",
        "paths": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ],
    },
    "playwright": {
        "name": "Chrome Playwright",
        "paths": [],
    },
}


NOPECHA_EXT_ID  = "dknlfmjaanfblgfdfebhijalfmhmjjjo"
NOPECHA_EXT_DIR = (Path(__file__).parent / "nopecha_ext").resolve()
NOPECHA_KEYS_FILE = (Path(__file__).parent / "input" / "nopecha_keys.txt").resolve()


# ═══════════════════════════════════════════════════════════════
# 9CAPTCHA EXTENSION  (NEW)
# ═══════════════════════════════════════════════════════════════
NINECAPTCHA_EXT_DIR    = (Path(__file__).parent / "ninecaptcha_ext").resolve()
NINECAPTCHA_SETUP_BASE = "https://9captcha-api.pridesmp.fun/setup"
NINECAPTCHA_API_BASE   = "https://9captcha-api.pridesmp.fun/api/ext"


def get_brave_path() -> Optional[str]:
    for p in BROWSER_CONFIG["brave"]["paths"]:
        if os.path.exists(p):
            return p
    return None


def get_edge_path() -> Optional[str]:
    for p in BROWSER_CONFIG["edge"]["paths"]:
        if os.path.exists(p):
            return p
    return None


def get_playwright_path() -> Optional[str]:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            exec_path = p.chromium.executable_path
            if exec_path and os.path.exists(exec_path):
                return exec_path
    except Exception:
        pass
    pw_dir = Path(os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright"))
    if pw_dir.exists():
        for p in pw_dir.rglob("chrome.exe"):
            if p.exists():
                return str(p)
        for p in pw_dir.rglob("headless_shell.exe"):
            if p.exists():
                return str(p)
    return None


def get_chrome_path() -> Optional[str]:
    for p in BROWSER_CONFIG.get("chrome", {}).get("paths", []):
        if os.path.exists(p):
            return p
    return get_playwright_path()


def get_browser_executable(browser_choice: str = None) -> Tuple[Optional[str], str]:
    choice = (browser_choice or config.get("browser", "brave") or "brave").strip().lower()
    if choice in ["brave"]:
        p = get_brave_path()
        if p:
            return p, "Brave"
    elif choice in ["edge", "msedge"]:
        p = get_edge_path()
        if p:
            return p, "Microsoft Edge"
    elif choice in ["chrome", "google-chrome", "googlechrome", "playwright", "chromium"]:
        p = get_chrome_path()
        if p:
            return p, "Google Chrome"
    for name, getter in [
        ("Brave", get_brave_path),
        ("Google Chrome", get_chrome_path),
        ("Microsoft Edge", get_edge_path),
    ]:
        p = getter()
        if p:
            return p, name
    return None, "System Default Browser"


async def launch_browser(
    proxy_config=None,
    slot: int = 1,
    total: int = 1,
    temp_profile: str = None,
    worker_cache_dir=None,
):
    browser_type = config.get("browser", "brave")
    executable_path, browser_name = get_browser_executable(browser_type)

    args = [
        "--lang=en-US",
        "--disable-infobars",
        "--disable-search-engine-choice-screen",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
    ]

    # If running on Linux without an X11 display, fallback to headless=new
    if sys.platform != 'win32' and not os.environ.get("DISPLAY"):
        args.append("--headless=new")

    # ── NopeCHA extension ──
    nopecha_cfg = config.get("nopecha", {}) or {}
    nopecha_enabled = nopecha_cfg.get("enabled", False) if isinstance(nopecha_cfg, dict) else bool(nopecha_cfg)
    if nopecha_enabled and NOPECHA_EXT_DIR.exists():
        ext_path = str(NOPECHA_EXT_DIR.resolve())
        args.append(f"--load-extension={ext_path}")
        args.append(f"--disable-extensions-except={ext_path}")
        args.append("--enable-extensions")

    # ── 9captcha extension ──
    ninecaptcha_cfg = config.get("ninecaptcha", {}) or {}
    ninecaptcha_enabled = ninecaptcha_cfg.get("enabled", False) if isinstance(ninecaptcha_cfg, dict) else bool(ninecaptcha_cfg)
    if (ninecaptcha_enabled
            and NINECAPTCHA_EXT_DIR.exists()
            and (NINECAPTCHA_EXT_DIR / "manifest.json").exists()):
        ext_path = str(NINECAPTCHA_EXT_DIR.resolve())
        args.append(f"--load-extension={ext_path}")
        args.append(f"--disable-extensions-except={ext_path}")
        args.append("--enable-extensions")

    proxy_str = None
    if proxy_config:
        proxy_str = proxy_config.get('full_url') or proxy_config.get('url')

    browser = await uc.start(
        browser_executable_path=executable_path if executable_path else None,
        browser_args=args,
        proxy=proxy_str,
        user_data_dir=temp_profile if temp_profile else None,
        sandbox=True
    )
    return browser


NOPECHA_KEY_INDEX = 0
NOPECHA_KEY_LOCK = threading.Lock()


def clear_nopecha_ext():
    if not NOPECHA_EXT_DIR.exists():
        return
    try:
        settings_path = NOPECHA_EXT_DIR / "settings.json"
        if settings_path.exists():
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump({"key": "", "keys": [], "enabled": False}, f, indent=2)
    except Exception as e:
        log.debug(f"NopeCHA settings.json clear error: {e}")
    try:
        manifest_path = NOPECHA_EXT_DIR / "manifest.json"
        if manifest_path.exists():
            manifest = json.load(open(manifest_path, 'r', encoding='utf-8'))
            if 'nopecha' in manifest:
                manifest.pop('nopecha', None)
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    json.dump(manifest, f, indent=2)
    except Exception as e:
        log.debug(f"NopeCHA manifest.json clear error: {e}")

    CLEAN_PATTERNS = [
        (re.compile(r'key:me\(ge\(\),\"[^\"]*\"\)', re.IGNORECASE), 'key:me(ge(),"")'),
        (re.compile(r'keys:me\(he\(ge\(\)\),\[[^\]]*\]\)', re.IGNORECASE), 'keys:me(he(ge()),[])'),
        (re.compile(r'key:\"[^\"]*\",keys:\[[^\]]*\]', re.IGNORECASE), 'key:"",keys:[]'),
        (re.compile(r'key:\"sub_[^\"]*\"', re.IGNORECASE), 'key:""'),
        (re.compile(r'keys:\[\"sub_[^\"]*\"\]', re.IGNORECASE), 'keys:[]'),
    ]
    for js_dir in [NOPECHA_EXT_DIR, NOPECHA_EXT_DIR / "assets"]:
        if not js_dir.exists():
            continue
        for js_file in js_dir.glob("*.js"):
            try:
                original = js_file.read_text(encoding="utf-8", errors="ignore")
                patched = original
                for pattern, replacement in CLEAN_PATTERNS:
                    patched = pattern.sub(replacement, patched)
                if patched != original:
                    js_file.write_text(patched, encoding="utf-8")
            except Exception as e:
                log.debug(f"NopeCHA clean error {js_file.name}: {e}")


def load_nopecha_keys() -> list:
    if not NOPECHA_KEYS_FILE.exists():
        NOPECHA_KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
        NOPECHA_KEYS_FILE.write_text("")
        clear_nopecha_ext()
        return []
    keys = []
    seen = set()
    for line in NOPECHA_KEYS_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line and not line.startswith('#') and line not in seen:
            seen.add(line)
            keys.append(line)
    if not keys:
        clear_nopecha_ext()
    return keys


def get_current_nopecha_key() -> Optional[str]:
    keys = load_nopecha_keys()
    if not keys:
        return None
    global NOPECHA_KEY_INDEX
    return keys[NOPECHA_KEY_INDEX % len(keys)]


def rotate_nopecha_key():
    global NOPECHA_KEY_INDEX
    keys = load_nopecha_keys()
    if keys and len(keys) > 1:
        with NOPECHA_KEY_LOCK:
            NOPECHA_KEY_INDEX = (NOPECHA_KEY_INDEX + 1) % len(keys)
            next_key = keys[NOPECHA_KEY_INDEX]
        log.info(f"Rotated to NopeCHA key #{NOPECHA_KEY_INDEX + 1}/{len(keys)} ({next_key[:10]}...)")
        inject_nopecha_key(next_key, all_keys=keys, log_output=False)


def inject_nopecha_key(api_key: Optional[str] = None, all_keys: Optional[list] = None, log_output: bool = True) -> bool:
    keys_list = all_keys if all_keys is not None else load_nopecha_keys()
    if not keys_list and api_key:
        keys_list = [api_key]
    primary_key = api_key or (keys_list[0] if keys_list else "")
    if not primary_key or not keys_list:
        clear_nopecha_ext()
        return False
    if not NOPECHA_EXT_DIR.exists():
        return False
    ok = False
    try:
        settings_path = NOPECHA_EXT_DIR / "settings.json"
        settings = {}
        if settings_path.exists():
            try:
                settings = json.load(open(settings_path, 'r', encoding='utf-8'))
            except Exception:
                settings = {}
        settings['key']     = primary_key
        settings['keys']    = keys_list
        settings['enabled'] = True
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
        ok = True
    except Exception as e:
        log.debug(f"NopeCHA settings.json write error: {e}")

    key_json = json.dumps(primary_key)
    keys_json = json.dumps(keys_list)
    KEY_PATTERNS = [
        (re.compile(r'key:me\(ge\(\),\"[^\"]*\"\)', re.IGNORECASE), lambda m: f'key:me(ge(),{key_json})'),
        (re.compile(r'keys:me\(he\(ge\(\)\),\[[^\]]*\]\)', re.IGNORECASE), lambda m: f'keys:me(he(ge()),{keys_json})'),
        (re.compile(r'key:\"[^\"]*\",keys:\[[^\]]*\]', re.IGNORECASE), lambda m: f'key:{key_json},keys:{keys_json}'),
    ]
    for js_dir in [NOPECHA_EXT_DIR, NOPECHA_EXT_DIR / "assets"]:
        if not js_dir.exists():
            continue
        for js_file in js_dir.glob("*.js"):
            try:
                original = js_file.read_text(encoding="utf-8", errors="ignore")
                patched = original
                for pattern, replacement in KEY_PATTERNS:
                    patched = pattern.sub(replacement, patched)
                if patched != original:
                    js_file.write_text(patched, encoding="utf-8")
                    ok = True
            except Exception as e:
                log.debug(f"NopeCHA patch error {js_file.name}: {e}")
    if ok and log_output:
        if len(keys_list) > 1:
            log.info(f"NopeCHA: {len(keys_list)} keys loaded, active key #{NOPECHA_KEY_INDEX + 1} ({primary_key[:10]}...)")
        else:
            log.info(f"NopeCHA: key injected ({primary_key[:10]}...)")
    return ok


def download_nopecha_ext() -> Optional[Path]:
    if NOPECHA_EXT_DIR.exists() and (NOPECHA_EXT_DIR / "manifest.json").exists():
        return NOPECHA_EXT_DIR
    crx_url = (
        f"https://clients2.google.com/service/update2/crx"
        f"?response=redirect&prodversion=120.0.0.0&acceptformat=crx2,crx3"
        f"&x=id%3D{NOPECHA_EXT_ID}%26uc"
    )
    try:
        with httpx.Client(follow_redirects=True) as client:
            r = client.get(crx_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
            if r.status_code != 200:
                return None
            data = r.content
        if data[:4] == b"Cr24":
            version = int.from_bytes(data[4:8], "little")
            if version == 3:
                zip_start = 12 + int.from_bytes(data[8:12], "little")
            else:
                zip_start = 16 + int.from_bytes(data[8:12], "little") + int.from_bytes(data[12:16], "little")
        else:
            zip_start = 0
        NOPECHA_EXT_DIR.mkdir(exist_ok=True, parents=True)
        with zipfile.ZipFile(io.BytesIO(data[zip_start:])) as z:
            z.extractall(NOPECHA_EXT_DIR)
        if (NOPECHA_EXT_DIR / "manifest.json").exists():
            return NOPECHA_EXT_DIR
        return None
    except Exception:
        return None


async def setup_nopecha():
    nopecha_cfg = config.get("nopecha", {}) or {}
    enabled = nopecha_cfg.get("enabled", False) if isinstance(nopecha_cfg, dict) else bool(nopecha_cfg)
    if not enabled:
        log.info("NopeCHA disabled - manual captcha solving mode")
        return None
    ext_path = download_nopecha_ext()
    if not ext_path:
        return None
    keys = load_nopecha_keys()
    if keys:
        current_key = get_current_nopecha_key()
        inject_nopecha_key(current_key, all_keys=keys, log_output=True)
    else:
        clear_nopecha_ext()
    return ext_path


# ═══════════════════════════════════════════════════════════════
# 9CAPTCHA HELPERS  (NEW)
# ═══════════════════════════════════════════════════════════════
def build_ninecaptcha_setup_url(api_key: str) -> str:
    """
    Extension reads #key=...|base_api=... from the URL fragment and self-configures.
    """
    return f"{NINECAPTCHA_SETUP_BASE}#key={api_key}|base_api={NINECAPTCHA_API_BASE}"


def _download_crx_to(url: str, dest_dir: Path) -> Optional[Path]:
    """Generic CRX/zip downloader + extractor."""
    try:
        with httpx.Client(follow_redirects=True) as client:
            r = client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
            if r.status_code != 200:
                return None
            data = r.content
        if data[:4] == b"Cr24":
            version = int.from_bytes(data[4:8], "little")
            if version == 3:
                zip_start = 12 + int.from_bytes(data[8:12], "little")
            else:
                zip_start = 16 + int.from_bytes(data[8:12], "little") + int.from_bytes(data[12:16], "little")
        else:
            zip_start = 0
        dest_dir.mkdir(exist_ok=True, parents=True)
        with zipfile.ZipFile(io.BytesIO(data[zip_start:])) as z:
            z.extractall(dest_dir)
        if (dest_dir / "manifest.json").exists():
            return dest_dir
        return None
    except Exception as e:
        log.debug(f"CRX download error ({url}): {e}")
        return None


def ensure_ninecaptcha_ext(cfg: dict) -> Optional[Path]:
    """
    Resolve 9captcha extension dir:
      1. local ninecaptcha_ext/ with manifest.json
      2. download from cfg["extension_url"] (direct CRX/zip)
      3. download from Chrome Web Store via cfg["extension_id"]
      4. give up
    """
    if NINECAPTCHA_EXT_DIR.exists() and (NINECAPTCHA_EXT_DIR / "manifest.json").exists():
        return NINECAPTCHA_EXT_DIR

    url = (cfg.get("extension_url") or "").strip()
    if url:
        return _download_crx_to(url, NINECAPTCHA_EXT_DIR)

    ext_id = (cfg.get("extension_id") or "").strip()
    if ext_id:
        crx_url = (
            f"https://clients2.google.com/service/update2/crx"
            f"?response=redirect&prodversion=120.0.0.0&acceptformat=crx2,crx3"
            f"&x=id%3D{ext_id}%26uc"
        )
        return _download_crx_to(crx_url, NINECAPTCHA_EXT_DIR)

    return None


async def setup_ninecaptcha():
    cfg = config.get("ninecaptcha", {}) or {}
    enabled = cfg.get("enabled", False) if isinstance(cfg, dict) else bool(cfg)
    if not enabled:
        log.info("9captcha disabled")
        return None
    api_key = (cfg.get("api_key") or "").strip()
    if not api_key:
        log.warning("9captcha enabled but no api_key set in config.json")
        return None
    ext_path = await asyncio.to_thread(ensure_ninecaptcha_ext, cfg)
    if not ext_path:
        log.warning("9captcha extension unavailable — setup URL visit will be a no-op")
        return None
    log.success(f"9captcha extension ready: {ext_path.name}")
    return ext_path


async def visit_ninecaptcha_setup(page) -> bool:
    """
    MANDATORY — must run before discord.com/register.
    The extension reads `#key=...|base_api=...` from the hash and self-configures.
    """
    cfg = config.get("ninecaptcha", {}) or {}
    enabled = cfg.get("enabled", False) if isinstance(cfg, dict) else bool(cfg)
    if not enabled:
        return False
    api_key = (cfg.get("api_key") or "").strip()
    if not api_key:
        return False
    setup_url = build_ninecaptcha_setup_url(api_key)
    try:
        log.info("Visiting 9captcha setup URL...")
        await page.get(setup_url)
        await asyncio.sleep(3.0)   # give the content script time to read the hash
        log.success("9captcha extension configured")
        return True
    except Exception as e:
        log.warning(f"9captcha setup visit failed: {e}")
        return False


from proxy_handler import (
    parse_proxy,
    get_browser_proxy_args,
    get_session_proxy,
    get_random_proxy,
    load_proxies,
    test_proxy,
)

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

init(autoreset=True)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore', category=ResourceWarning)
warnings.filterwarnings('ignore', message='.*connection.*refused.*')
warnings.filterwarnings('ignore', message='.*Task exception was never retrieved.*')

import logging
logging.getLogger('asyncio').setLevel(logging.CRITICAL)
logging.getLogger('websockets').setLevel(logging.CRITICAL)
logging.getLogger('nodriver').setLevel(logging.CRITICAL)


async def fetch_discord_token(email: str, password: str, proxy_config: Dict = None) -> str:
    url = "https://discord.com/api/v9/auth/login"
    _super_props = base64.b64encode(json.dumps({
        "os": "Windows", "browser": "Chrome", "device": "",
        "system_locale": "en-US",
        "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "browser_version": "131.0.0.0", "os_version": "10",
        "referrer": "", "referring_domain": "",
        "referrer_current": "", "referring_domain_current": "",
        "release_channel": "stable", "client_build_number": 346580,
        "client_event_source": None,
    }, separators=(',', ':')).encode()).decode()
    headers = {
        "accept": "*/*", "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json", "origin": "https://discord.com",
        "referer": "https://discord.com/login",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0", "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty", "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "x-discord-locale": "en-US",
        "x-discord-timezone": "America/New_York",
        "x-super-properties": _super_props,
    }
    payload = {"login": email, "password": password, "undelete": False, "gift_code_sku_id": None}
    session = tls_client.Session(client_identifier="chrome_131", random_tls_extension_order=True)
    if proxy_config:
        proxy_dict = get_session_proxy(proxy_config)
        if proxy_dict:
            session.proxies = proxy_dict
    try:
        response = session.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            token = data.get("token", "")
            if token:
                return token
            if data.get("mfa"):
                log.debug("API login: MFA required")
            elif data.get("captcha_key"):
                sitekey = data.get("captcha_sitekey", "")
                log.warning(f"Discord login HTTP 200 — captcha required (sitekey={sitekey})")
            return ""
        elif response.status_code == 400:
            body = response.json()
            captcha_key = body.get("captcha_key")
            if captcha_key:
                sitekey = body.get("captcha_sitekey", "")
                log.warning(f"Discord login HTTP 400 — captcha required (sitekey={sitekey})")
            else:
                log.debug(f"API login 400: {body}")
            return ""
        else:
            log.debug(f"API login HTTP {response.status_code}")
            return ""
    except Exception as e:
        log.debug(f"API login exception: {e}")
        return ""


JS_UTILS = '''
(() => {
    if (window.utils) return;
    function setInput(selector, value) {
        const el = document.querySelector(selector);
        if (el) {
            el.value = value;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }
    function clickAllCheckboxes() {
        const checkboxes = document.querySelectorAll('input[type="checkbox"]');
        let clicked = 0;
        checkboxes.forEach(cb => {
            if (!cb.checked) {
                cb.click(); cb.checked = true;
                cb.dispatchEvent(new Event('change', { bubbles: true }));
                clicked++;
            }
        });
        return { clicked: clicked, total: checkboxes.length };
    }
    function clickElement(selector) {
        const el = document.querySelector(selector);
        if (el) el.click();
    }
    function setDropdown(label, value) {
        const dropdown = document.querySelector(`div[role="button"][aria-label="${label}"]`);
        if (!dropdown) return;
        dropdown.click();
        setTimeout(() => {
            const options = document.querySelectorAll('div[role="option"]');
            const match = Array.from(options).find(opt => opt.textContent.trim() === value);
            if (match) match.click();
        }, 100);
    }
    function waitForDiscordToken(timeout = 5000) {
        return new Promise((resolve) => {
            const start = Date.now();
            const check = () => {
                const token = localStorage.getItem('token');
                if (token) resolve(token.replace(/^"|"$/g, ''));
                else if (Date.now() - start < timeout) setTimeout(check, 200);
                else resolve(null);
            };
            check();
        });
    }
    function findCaptchaFrame() {
        const iframes = document.querySelectorAll('iframe');
        for (let iframe of iframes) {
            const src = iframe.src || '';
            if (src.includes('captcha') || src.includes('hcaptcha') || src.includes('recaptcha'))
                return iframe;
        }
        return null;
    }
    window.utils = { setInput, clickAllCheckboxes, clickElement, setDropdown, waitForDiscordToken, findCaptchaFrame };
})();
'''


console = Console()
LOCK = threading.Lock()
SCRIPT_DIR = Path(__file__).parent
MS_CLIENT_ID = "d8fbe69d-15be-43fa-b204-5c5bc5a73ad7"

BROWSER_CACHE_DIR = Path(__file__).parent / ".browser_cache"
BROWSER_CACHE_DIR.mkdir(parents=True, exist_ok=True)

SESSION_TARGET = 0
SESSION_CREATED = 0
SESSION_STOP = False
ACTIVE_WORKERS = 0
WORKER_LOCK = threading.Lock()
COOLDOWN_SECONDS = 90

PROXY_LIST: list = []

SESSION_VALID      = 0
SESSION_LOCKED     = 0
SESSION_INVALID    = 0
SESSION_UNVERIFIED = 0

CONFIG_PATH = Path(__file__).resolve().parent / 'config.json'
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def load_or_create_config():
    if not CONFIG_PATH.exists():
        config_text = r'''{
    "email_provider": {
        "name": "mailcow",
        "cowmail": {
            "api_base": "https://mail.yashlegit.shop",
            "api_key": "42712D-D02B3D-143F53-6B9524-B66D29",
            "domain": "mail.yashlegit.shop",
            "imap_host": "mail.yashlegit.shop",
            "imap_port": 993
        },
        "duckmail": {
            "api_base": "https://api.duckmail.sbs",
            "api_key": "",
            "password": "NILOY693741@",
            "domain": ""
        },
        "afhamxmailz": {
            "api_base": "https://api.afhamxmailz.com",
            "api_key": "",
            "type": "discord"
        }
    },
    "use_wasted_mails": false,
    "browser": "brave",
    "nopecha": {
        "enabled": false
    },
    "ninecaptcha": {
        "enabled": false,
        "api_key": "",
        "extension_id": "",
        "extension_url": ""
    },
    "proxy": {
        "enabled": false,
        "file": "input/proxies.txt"
    },
    "adb": {
        "enabled": false,
        "device_id": "",
        "settle_seconds": 6,
        "verify_ip": true,
        "max_wait": 45
    },
    "threads": 1,
    "cooldown": 90,
    "humanizer": {
        "enabled": true,
        "name": true,
        "bio": true,
        "pronouns": true,
        "avatar": true,
        "hypesquad": true
    }
}
'''
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            f.write(config_text)
        print(f"\n\033[93m[CONFIG]\033[0m Config created: {CONFIG_PATH}")
        print(f"\033[93m[CONFIG]\033[0m Edit it with your settings then run again.\n")
        sys.exit(0)
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    provider = config.get("email_provider", {}).get("name", "")
    if provider not in ("mailcow", "cowmail", "duckmail", "afhamxmailz"):
        print(f"\033[91m[ERROR]\033[0m Supported providers: mailcow, cowmail, duckmail, afhamxmailz.")
        sys.exit(1)
    return config


config = load_or_create_config()
THREAD_COUNT = config.get("threads", 1)
COOLDOWN_SECONDS = config.get("cooldown", 90)

ADB_CONFIG = config.get("adb", {})
ADB_ENABLED = ADB_CONFIG.get("enabled", False)


if sys.platform == 'win32':
    import ctypes
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

GRAY    = '\033[38;5;250m'
GREEN   = '\033[38;5;151m'
CYAN    = '\033[38;5;159m'
RED     = '\033[38;5;215m'
YELLOW  = '\033[38;5;229m'
WHITE   = '\033[38;5;255m'
RESET   = '\033[0m'
BLUE    = '\033[38;5;153m'
PURPLE  = '\033[38;5;153m'
PINK    = '\033[38;5;24m'
DIM     = '\033[38;5;238m'
BOLD    = '\033[1m'


class Logger:
    def __init__(self):
        self._lock = threading.Lock()

    @staticmethod
    def _print(tag: str, tag_color: str, message: str):
        ts = datetime.now().strftime('%H:%M:%S')
        bar   = f"{DIM}|{RESET}"
        time_part = f"{DIM}{ts}{RESET}"
        clear_prefix = "\r" + " " * 80 + "\r"
        line = f"{clear_prefix} {bar} {time_part} {bar} {tag_color}{BOLD}{tag}{RESET} {WHITE}{message}{RESET}\n"
        try:
            sys.stdout.write(line)
            sys.stdout.flush()
        except UnicodeEncodeError:
            safe = line.encode('ascii', 'replace').decode('ascii')
            sys.stdout.write(safe)
            sys.stdout.flush()

    def mask_token(self, token: str) -> str:
        return token[:20] + '...' if len(token) > 20 else token

    def info(self, message: str):
        self._print('INFO', CYAN, message)

    def success(self, message: str):
        self._print('OK', GREEN, message)

    def warning(self, message: str):
        self._print('WARN', YELLOW, message)

    def error(self, message: str):
        self._print('ERR', RED, message)

    def debug(self, message: str):
        self._print('DBG', DIM, message)

    def adb(self, message: str):
        self._print('ADB', CYAN, message)


log = Logger()


from adb_handler import ADBRotator
_adb_device_id = ADB_CONFIG.get("device_id", "").strip() or None
try:
    adb_rotator = ADBRotator(logger=log, device_id=_adb_device_id)
except TypeError:
    adb_rotator = ADBRotator(logger=log)


USA_FIRST_NAMES = [
    'Aether', 'James', 'John', 'Robert', 'Michael', 'William', 'David', 'Richard',
    'Joseph', 'Thomas', 'Charles', 'Christopher', 'Daniel', 'Matthew', 'Anthony',
    'Mark', 'Donald', 'Steven', 'Andrew', 'Joshua', 'Kevin', 'Brian', 'George',
    'Edward', 'Ronald', 'Timothy', 'Jason', 'Jeffrey', 'Ryan', 'Jacob', 'Gary',
    'Nicholas', 'Eric', 'Jonathan', 'Stephen', 'Larry', 'Justin', 'Scott', 'Brandon',
    'Benjamin', 'Samuel', 'Gregory', 'Alexander', 'Patrick', 'Frank', 'Raymond',
    'Jack', 'Dennis', 'Jerry', 'Tyler', 'Aaron', 'Jose', 'Henry', 'Adam', 'Nathan',
    'Mary', 'Patricia', 'Jennifer', 'Linda', 'Elizabeth', 'Barbara', 'Susan',
    'Jessica', 'Sarah', 'Karen', 'Nancy', 'Lisa', 'Emily', 'Ashley', 'Amanda',
    'Olivia', 'Emma', 'Madison', 'Abigail', 'Sophia', 'Grace', 'Ethan', 'Logan',
    'Betty', 'Margaret', 'Sandra', 'Donna', 'Carol', 'Ruth', 'Sharon', 'Michelle',
    'Laura', 'Kimberly', 'Deborah', 'Amy', 'Angela', 'Brenda', 'Rebecca', 'Anna',
    'Chloe', 'Mia', 'Ella', 'Avery', 'Scarlett', 'Lily', 'Hannah', 'Zoe', 'Natalie',
    'Mason', 'Noah', 'Liam', 'Lucas', 'Oliver', 'Elijah', 'Aiden', 'Carter', 'Owen',
]

USA_LAST_NAMES = [
    'Aether', 'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller',
    'Davis', 'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez', 'Wilson',
    'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Perez',
    'Thompson', 'White', 'Harris', 'Clark', 'Lewis', 'Walker', 'Hall', 'Allen',
    'Young', 'King', 'Wright', 'Scott', 'Green', 'Baker', 'Adams', 'Nelson',
    'Hill', 'Ramirez', 'Campbell', 'Mitchell', 'Roberts', 'Carter', 'Phillips',
    'Evans', 'Turner', 'Torres', 'Parker', 'Collins', 'Edwards', 'Stewart', 'Flores',
    'Morris', 'Nguyen', 'Murphy', 'Rivera', 'Cook', 'Rogers', 'Morgan', 'Peterson',
    'Cooper', 'Reed', 'Bailey', 'Bell', 'Gomez', 'Kelly', 'Howard', 'Ward', 'Cox',
    'Diaz', 'Richardson', 'Wood', 'Watson', 'Brooks', 'Bennett', 'Gray', 'James',
    'Reyes', 'Cruz', 'Hughes', 'Price', 'Myers', 'Long', 'Foster', 'Sanders', 'Ross',
    'Powell', 'Sullivan', 'Russell', 'Ortiz', 'Jenkins', 'Gutierrez', 'Perry', 'Butler',
    'Barnes', 'Fisher', 'Henderson', 'Coleman', 'Simmons', 'Patterson', 'Jordan',
]


def generate_usa_name() -> tuple:
    first = random.choice(USA_FIRST_NAMES)
    last  = random.choice(USA_LAST_NAMES)
    return first, last


def generate_display_name() -> str:
    first, last = generate_usa_name()
    if 'Aether' not in (first, last) and random.random() < 0.3:
        if random.random() < 0.5:
            first = 'Aether'
        else:
            last = 'Aether'
    return f"{first} {last}"


def generate_username() -> str:
    first, last = generate_usa_name()
    if 'Aether' not in (first, last) and random.random() < 0.3:
        last = 'Aether'
    sep = random.choice(['', '', '_', '.'])
    base = f"{first}{sep}{last}"
    return f"{base}{random.randint(100000, 99999999)}".lower()


def _random_local_part() -> str:
    first, last = generate_usa_name()
    if 'Aether' not in (first, last) and random.random() < 0.15:
        if random.random() < 0.5:
            first = 'Aether'
        else:
            last = 'Aether'
    first = first.lower()
    last = last.lower()
    style = random.choices(
        ['first.last', 'firstlast', 'first_last', 'first.l', 'flast', 'first'],
        weights=[30, 30, 10, 10, 10, 10], k=1
    )[0]
    if style == 'first.last':
        local = f"{first}.{last}"
    elif style == 'firstlast':
        local = f"{first}{last}"
    elif style == 'first_last':
        local = f"{first}_{last}"
    elif style == 'first.l':
        local = f"{first}.{last[0]}"
    elif style == 'flast':
        local = f"{first[0]}{last}"
    else:
        local = first
    if random.random() < 0.70:
        digits = random.randint(1, 9999)
        local += str(digits) if random.random() < 0.5 else str(digits).zfill(4)
    return re.sub(r'[^a-z0-9._]', '', local)


# ═══════════════════════════════════════════════════════════════
# DUCKMAIL PROVIDER
# ═══════════════════════════════════════════════════════════════

_duckmail_domains_cache: list = []
_duckmail_domains_lock = threading.Lock()
DUCKMAIL_BLACKLIST = {"duckmail.sbs"}


def duckmail_get_domains(api_base: str, api_key: str = "") -> list:
    global _duckmail_domains_cache
    with _duckmail_domains_lock:
        if _duckmail_domains_cache:
            return _duckmail_domains_cache
    try:
        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        r = requests.get(f"{api_base.rstrip('/')}/domains", headers=headers, timeout=20, verify=False)
        if r.status_code == 200:
            data = r.json()
            members = data.get("hydra:member") or data.get("member") or []
            domains = [m.get("domain") for m in members if m.get("domain") and m.get("isVerified")]

            before = len(domains)
            domains = [d for d in domains if d.lower() not in DUCKMAIL_BLACKLIST]
            removed = before - len(domains)

            if domains:
                with _duckmail_domains_lock:
                    _duckmail_domains_cache = domains
                msg = f"DuckMail: {len(domains)} verified domains loaded"
                if removed:
                    msg += f" (excluded {removed} blacklisted)"
                log.info(msg)
                return domains
    except Exception as e:
        log.debug(f"DuckMail domains fetch error: {e}")
    return []


def duckmail_create_account(api_base: str, api_key: str = "",
                            username: str = "", password: str = "",
                            custom_domain: str = "") -> Optional[tuple]:
    if custom_domain:
        domain = custom_domain.strip()
        log.info(f"DuckMail: using custom domain '{domain}'")
    else:
        domains = duckmail_get_domains(api_base, api_key)
        if not domains:
            log.error("DuckMail: no verified domains available")
            return None
        domain = random.choice(domains)

    if not username:
        username = _random_local_part()
    else:
        username = re.sub(r'[^a-z0-9._]', '', username.lower())
        if len(username) < 3:
            username = _random_local_part()

    if not password:
        password = "NILOY693741@"

    address = f"{username}@{domain}"
    payload = {"address": address, "password": password, "expiresIn": 0}
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        r = requests.post(f"{api_base.rstrip('/')}/accounts", json=payload,
                          headers=headers, timeout=25, verify=False)
        if r.status_code in (200, 201):
            data = r.json()
            addr = data.get("address") or address
            token = data.get("token") or ""
            if not token:
                try:
                    tr = requests.post(f"{api_base.rstrip('/')}/token",
                                       json={"address": addr, "password": password},
                                       headers={"Content-Type": "application/json"},
                                       timeout=15, verify=False)
                    if tr.status_code == 200:
                        token = tr.json().get("token") or ""
                except Exception:
                    pass
            log.success(f"DuckMail account created: {addr}")
            return addr, password, token
        else:
            log.warning(f"DuckMail HTTP {r.status_code}: {r.text[:120]}")
    except Exception as e:
        log.warning(f"DuckMail create error: {e}")
    return None


def get_duckmail_email(config: dict) -> tuple:
    dm_cfg = config.get("email_provider", {}).get("duckmail", {})
    api_base = dm_cfg.get("api_base", "https://api.duckmail.sbs")
    api_key  = dm_cfg.get("api_key", "")
    password = dm_cfg.get("password") or "NILOY693741@"
    custom_domain = dm_cfg.get("domain", "").strip()
    result = duckmail_create_account(api_base, api_key, password=password,
                                     custom_domain=custom_domain)
    if result:
        addr, pw, token = result
        return addr, pw, token, None
    return None, None, None, None


def duckmail_get_messages(api_base: str, bearer: str, page: int = 1) -> list:
    try:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {bearer}"}
        r = requests.get(f"{api_base.rstrip('/')}/messages", headers=headers,
                         params={"page": page}, timeout=15, verify=False)
        if r.status_code == 200:
            data = r.json()
            return data.get("hydra:member") or data.get("member") or []
    except Exception as e:
        log.debug(f"DuckMail messages fetch error: {e}")
    return []


def duckmail_get_message_detail(api_base: str, bearer: str, msg_id: str) -> dict:
    try:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {bearer}"}
        r = requests.get(f"{api_base.rstrip('/')}/messages/{msg_id}", headers=headers,
                         timeout=15, verify=False)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        log.debug(f"DuckMail message detail error: {e}")
    return {}


def duckmail_get_verify_url(api_base: str, bearer: str, email: str,
                            password: str, timeout: int = 180) -> Optional[str]:
    if not bearer:
        try:
            r = requests.post(f"{api_base.rstrip('/')}/token",
                              json={"address": email, "password": password},
                              headers={"Content-Type": "application/json"},
                              timeout=15, verify=False)
            if r.status_code == 200:
                bearer = r.json().get("token") or ""
        except Exception:
            pass

    if not bearer:
        log.warning("DuckMail: no bearer token — cannot poll inbox")
        return None

    start_time = time.time()
    seen_ids = set()
    last_count = -1

    while time.time() - start_time < timeout:
        messages = duckmail_get_messages(api_base, bearer)

        if len(messages) != last_count:
            last_count = len(messages)
            log.info(f"DuckMail inbox: {len(messages)} message(s)")

        for msg in messages:
            msg_id = msg.get("id")
            if not msg_id or msg_id in seen_ids:
                continue

            subject = (msg.get("subject") or "").lower()
            sender_obj = msg.get("from") or {}
            if isinstance(sender_obj, dict):
                sender = (sender_obj.get("address") or sender_obj.get("name") or "").lower()
            else:
                sender = str(sender_obj).lower()

            is_verify = (
                "discord" in sender
                or "discord" in subject
                or "verify" in subject
                or "confirm" in subject
            )
            if not is_verify:
                seen_ids.add(msg_id)
                continue

            seen_ids.add(msg_id)

            detail = duckmail_get_message_detail(api_base, bearer, msg_id)
            if not detail:
                continue

            html_body = ""
            if isinstance(detail.get("html"), list) and detail["html"]:
                html_body = detail["html"][0] or ""
            elif isinstance(detail.get("html"), str):
                html_body = detail["html"]
            text_body = detail.get("text", "") or ""
            combined = html_body + "\n" + text_body

            m = re.search(r'https://discord\.com/verify\?token=[^"\'\>\s<]+', combined)
            if m:
                log.success("DuckMail: verify link found")
                return m.group(0).replace("&amp;", "&")

            for cm in re.finditer(r'https://click\.discord\.com/ls/click\?[^"\'\>\s<]+', combined):
                url = cm.group(0)
                try:
                    resp = requests.get(url, allow_redirects=True, timeout=15, verify=False)
                    if "discord.com/verify" in resp.url:
                        log.success("DuckMail: verify link found via click redirect")
                        return resp.url
                    m2 = re.search(r'https://discord\.com/verify\?token=[^"\'\>\s<]+', resp.text)
                    if m2:
                        log.success("DuckMail: verify link found in redirect body")
                        return m2.group(0).replace("&amp;", "&")
                except Exception:
                    pass

        time.sleep(2.0)

    log.warning("DuckMail: no verification mail after timeout")
    return None


async def verify_email_duckmail(email: str, password: str, bearer: str, browser,
                                token: str, api_base: str = "https://api.duckmail.sbs",
                                timeout: int = 180) -> bool:
    log.info("Waiting for DuckMail verification email...")
    verify_url = await asyncio.get_event_loop().run_in_executor(
        None, lambda: duckmail_get_verify_url(api_base, bearer, email, password, timeout))
    if verify_url:
        return await verify_email_with_url(browser, verify_url, token)
    log.warning("DuckMail: verification email not found after timeout")
    return False


# ═══════════════════════════════════════════════════════════════
# AFHAMXMAILZ PROVIDER
# ═══════════════════════════════════════════════════════════════

_afhamxmailz_domains_cache: list = []
_afhamxmailz_domains_lock = threading.Lock()


def afhamxmailz_get_domains(api_base: str, api_key: str = "", domain_type: str = "discord") -> list:
    global _afhamxmailz_domains_cache
    if _afhamxmailz_domains_cache:
        return _afhamxmailz_domains_cache
    with _afhamxmailz_domains_lock:
        if _afhamxmailz_domains_cache:
            return _afhamxmailz_domains_cache
    try:
        headers = {"Accept": "application/json"}
        if api_key:
            headers["X-API-KEY"] = api_key
        params = {"type": domain_type} if domain_type else None
        r = requests.get(f"{api_base.rstrip('/')}/domains", headers=headers,
                         params=params, timeout=20, verify=False)
        if r.status_code == 200:
            data = r.json()
            domains = []
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("domain"):
                        domains.append(item)
            if domains:
                with _afhamxmailz_domains_lock:
                    _afhamxmailz_domains_cache = domains
                log.info(f"AfhamXMailz: {len(domains)} domain(s) loaded (type={domain_type})")
                return domains
            log.warning(f"AfhamXMailz: /domains returned no usable entries")
        else:
            log.debug(f"AfhamXMailz /domains HTTP {r.status_code}: {r.text[:160]}")
    except Exception as e:
        log.debug(f"AfhamXMailz domains fetch error: {e}")
    return []


def afhamxmailz_create_account(api_base: str, api_key: str = "",
                               domain_type: str = "discord",
                               username: str = "") -> Optional[tuple]:
    if not username:
        username = _random_local_part()

    url = f"{api_base.rstrip('/')}/inbox/generate"
    params = {"type": domain_type} if domain_type else None
    payload = {"username": username}

    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if api_key:
        headers["X-API-KEY"] = api_key

    try:
        r = requests.post(url, headers=headers, json=payload, params=params,
                          timeout=25, verify=False)
        if r.status_code in (200, 201):
            data = r.json() or {}
            addr = data.get("address")
            inbox_id = data.get("id")
            if addr:
                log.success(f"AfhamXMailz inbox created: {addr}")
                return addr, "NILOY693741@", inbox_id
            log.warning(f"AfhamXMailz: unexpected create response: {str(data)[:160]}")
        else:
            log.warning(f"AfhamXMailz HTTP {r.status_code}: {r.text[:160]}")
    except Exception as e:
        log.warning(f"AfhamXMailz create error: {e}")
    return None


def get_afhamxmailz_email(config: dict) -> tuple:
    am_cfg = config.get("email_provider", {}).get("afhamxmailz", {})
    api_base = am_cfg.get("api_base", "https://api.afhamxmailz.com")
    api_key  = am_cfg.get("api_key", "") or am_cfg.get("apiKey", "")
    dtype    = am_cfg.get("type", "discord") or "discord"

    result = afhamxmailz_create_account(api_base, api_key, domain_type=dtype)
    if result:
        addr, pw, inbox_id = result
        return addr, pw, inbox_id, None
    return None, None, None, None


def afhamxmailz_list_emails(api_base: str, api_key: str, address: str) -> list:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["X-API-KEY"] = api_key
    try:
        r = requests.get(f"{api_base.rstrip('/')}/emails/{address}",
                         headers=headers, timeout=20, verify=False)
        if r.status_code == 200:
            data = r.json() or {}
            emails = data.get("emails") or []
            return emails if isinstance(emails, list) else []
        if r.status_code != 404:
            log.debug(f"AfhamXMailz /emails HTTP {r.status_code}: {r.text[:120]}")
    except Exception as e:
        log.debug(f"AfhamXMailz list emails error: {e}")
    return []


def afhamxmailz_wait_emails(api_base: str, api_key: str, address: str, timeout: int = 30) -> list:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["X-API-KEY"] = api_key
    try:
        r = requests.get(f"{api_base.rstrip('/')}/emails/{address}/wait",
                         headers=headers, params={"timeout": min(max(timeout, 1), 60)},
                         timeout=timeout + 10, verify=False)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("emails") or []
    except Exception as e:
        log.debug(f"AfhamXMailz wait error: {e}")
    return []


def afhamxmailz_get_message(api_base: str, api_key: str, msg_id: str) -> dict:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["X-API-KEY"] = api_key
    try:
        r = requests.get(f"{api_base.rstrip('/')}/emails/message/{msg_id}",
                         headers=headers, timeout=20, verify=False)
        if r.status_code == 200:
            return r.json() or {}
    except Exception as e:
        log.debug(f"AfhamXMailz message fetch error: {e}")
    return {}


def _afhamxmailz_extract_verify_url(combined: str) -> Optional[str]:
    if not combined:
        return None

    m = re.search(r'https://discord\.com/verify\?token=[^"\'\>\s<]+', combined)
    if m:
        return m.group(0).replace("&amp;", "&")

    m = re.search(r'https://discord\.com/verify(?:-email)?[^"\'\>\s<]+', combined)
    if m:
        return m.group(0).replace("&amp;", "&")

    for cm in re.finditer(r'https://click\.discord\.com/ls/click\?[^"\'\>\s<]+', combined):
        url = cm.group(0).replace("&amp;", "&")
        try:
            resp = requests.get(url, allow_redirects=True, timeout=15, verify=False)
            if "discord.com/verify" in resp.url:
                return resp.url
            m2 = re.search(r'https://discord\.com/verify\?token=[^"\'\>\s<]+', resp.text)
            if m2:
                return m2.group(0).replace("&amp;", "&")
        except Exception:
            pass

    return None


def afhamxmailz_get_verify_url(api_base: str, api_key: str, address: str,
                               timeout: int = 180) -> Optional[str]:
    start_time = time.time()
    seen_ids = set()

    while time.time() - start_time < timeout:
        remaining = int(timeout - (time.time() - start_time))
        if remaining <= 0:
            break

        emails = []
        if remaining >= 5:
            emails = afhamxmailz_wait_emails(
                api_base, api_key, address, timeout=min(30, remaining)
            )
        if not emails:
            emails = afhamxmailz_list_emails(api_base, api_key, address)

        for em in emails:
            msg_id = em.get("id")
            if not msg_id or msg_id in seen_ids:
                continue
            seen_ids.add(msg_id)

            sender = (em.get("from_address") or em.get("from_name") or "").lower()
            subject = (em.get("subject") or "").lower()

            is_verify = (
                "discord" in sender
                or "discord" in subject
                or "verify" in subject
                or "confirm" in subject
                or "activate" in subject
            )
            if not is_verify:
                continue

            detail = afhamxmailz_get_message(api_base, api_key, msg_id)
            if not detail:
                continue

            combined = "\n".join([
                str(detail.get("body_html") or ""),
                str(detail.get("body_text") or ""),
                str(detail.get("subject") or ""),
            ])
            url = _afhamxmailz_extract_verify_url(combined)
            if url:
                log.success("AfhamXMailz: verify link found")
                return url

        time.sleep(1.0)

    log.warning("AfhamXMailz: no verification mail after timeout")
    return None


async def verify_email_afhamxmailz(email: str, password: str, inbox_id: str, browser,
                                   token: str, api_base: str = "https://api.afhamxmailz.com",
                                   api_key: str = "", timeout: int = 180) -> bool:
    log.info("Waiting for AfhamXMailz verification email...")
    verify_url = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: afhamxmailz_get_verify_url(api_base, api_key, email, timeout),
    )
    if verify_url:
        return await verify_email_with_url(browser, verify_url, token)
    log.warning("AfhamXMailz: verification email not found after timeout")
    return False


# ═══════════════════════════════════════════════════════════════
# MAILCOW PROVIDER
# ═══════════════════════════════════════════════════════════════

class MailcowProvider:
    def __init__(self, mc_config: dict):
        self.config = mc_config
        api_base = mc_config.get("api_base", "").rstrip("/")
        host     = mc_config.get("host", "").rstrip("/")
        if api_base:
            self.base_url = api_base
        elif host:
            self.base_url = host if host.startswith("http") else f"https://{host}"
        else:
            self.base_url = ""
        self.api_key   = mc_config.get("api_key", "")
        self.imap_host = mc_config.get(
            "imap_host",
            host.replace("https://", "").replace("http://", "") if host else ""
        )
        self.imap_port       = int(mc_config.get("imap_port", 993))
        self.domain          = mc_config.get("domain", "")
        self.headers         = {"X-API-Key": self.api_key, "Content-Type": "application/json"}
        self._created_email  = None
        self._created_password = None

    def create_account(self) -> Optional[str]:
        if not self.base_url or not self.api_key or not self.domain:
            log.error("CowMail: api_base / api_key / domain missing in config")
            return None
        for attempt in range(3):
            try:
                local = _random_local_part()
                addr  = f"{local}@{self.domain}"
                pw    = "NILOY693741@"
                data  = {
                    "active":     "1",
                    "domain":     self.domain,
                    "local_part": local,
                    "name":       local,
                    "password":   pw,
                    "password2":  pw,
                    "quota":      "10",
                }
                api_url = self.base_url.rstrip("/")
                if not api_url.endswith("/api/v1"):
                    api_url += "/api/v1"
                r = requests.post(f"{api_url}/add/mailbox", json=data,
                                  headers=self.headers, timeout=25, verify=False)
                if r.status_code in (200, 201):
                    body = r.text.strip()
                    ok = False
                    if not body:
                        ok = True
                    else:
                        try:
                            resp_json = r.json()
                            if isinstance(resp_json, list):
                                ok = any(item.get("type") == "success" for item in resp_json)
                            else:
                                ok = True
                        except Exception:
                            ok = True
                    if ok:
                        self._created_email    = addr
                        self._created_password = pw
                        log.success(f"CowMail mailbox created: {addr}")
                        return addr
                    log.warning(f"CowMail attempt {attempt+1}/3 failed: {r.text[:80]}")
                else:
                    log.warning(f"CowMail HTTP {r.status_code} on attempt {attempt+1}/3")
            except Exception as exc:
                log.warning(f"CowMail exception attempt {attempt+1}/3: {exc}")
            if attempt < 2:
                time.sleep(2)
        return None

    def get_verify_url(self, timeout: int = 120) -> Optional[str]:
        em = self._created_email
        pw = self._created_password
        if not em or not pw or not self.imap_host:
            log.error("CowMail: cannot poll IMAP — missing credentials")
            return None
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
                mail.login(em, pw)
                for folder in ["INBOX", "Junk", "Spam"]:
                    try:
                        status, _ = mail.select(folder)
                        if status != "OK":
                            continue
                        status, messages = mail.search(None, "ALL")
                        if status != "OK" or not messages[0]:
                            continue
                        for num in reversed(messages[0].split()):
                            res, msg_data = mail.fetch(num, "(RFC822)")
                            if res != "OK":
                                continue
                            msg = email_lib.message_from_bytes(msg_data[0][1])
                            subject  = str(msg.get("Subject", "")).lower()
                            from_hdr = str(msg.get("From", "")).lower()
                            if not ("discord" in subject or "verify" in subject or "discord" in from_hdr):
                                continue
                            body = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if part.get_content_type() in ("text/plain", "text/html"):
                                        try:
                                            body += part.get_payload(decode=True).decode(errors="ignore")
                                        except Exception:
                                            pass
                            else:
                                try:
                                    body = msg.get_payload(decode=True).decode(errors="ignore")
                                except Exception:
                                    pass
                            if not body:
                                continue
                            for pat in [
                                r'https://click\.discord\.com/ls/click\?[^"\s<>]+',
                                r'https://discord\.com/verify(?:-email)?[^"\s<>]+',
                                r'https://discord\.com/verify\?token=[^"\s<>]+',
                            ]:
                                m = re.search(pat, body, re.IGNORECASE)
                                if m:
                                    url = m.group(0).replace("&amp;", "&")
                                    mail.logout()
                                    log.success("CowMail: found verify link")
                                    return url
                    except Exception:
                        pass
                mail.logout()
            except Exception as exc:
                log.debug(f"CowMail IMAP error: {exc}")
            time.sleep(5)
        return None


_cowmail_providers: dict = {}


def get_cowmail_email(config: dict) -> tuple:
    cm_cfg = config.get("email_provider", {}).get("cowmail", {})
    if not cm_cfg:
        log.error("CowMail: no 'cowmail' block in email_provider config")
        return None, None, None, None
    provider = MailcowProvider(cm_cfg)
    email = provider.create_account()
    if email:
        _cowmail_providers[threading.current_thread().ident] = provider
        return email, provider._created_password, None, None
    return None, None, None, None


# ═══════════════════════════════════════════════════════════════
# PROVIDER DISPATCH
# ═══════════════════════════════════════════════════════════════

def get_email_from_provider(config: dict) -> tuple:
    provider_name = config.get("email_provider", {}).get("name", "")

    if provider_name in ("mailcow", "cowmail"):
        email, password, token, uuid = get_cowmail_email(config)
        if email:
            return email, password, None, None, "mailcow"
        log.error("Mailcow failed to create an email address")
        return None, None, None, None, None

    if provider_name == "duckmail":
        email, password, token, uuid = get_duckmail_email(config)
        if email:
            return email, password, token, None, "duckmail"
        log.error("DuckMail failed to create an email address")
        return None, None, None, None, None

    if provider_name == "afhamxmailz":
        email, password, token, uuid = get_afhamxmailz_email(config)
        if email:
            return email, password, token, None, "afhamxmailz"
        log.error("AfhamXMailz failed to create an email address")
        return None, None, None, None, None

    log.error(f"Unknown email provider: {provider_name}")
    return None, None, None, None, None


# ═══════════════════════════════════════════════════════════════
# ACCOUNT CLASSIFICATION  (NEW RULES)
#   VALID      — email verified + no phone gate
#   LOCKED     — email verified + phone required
#   UNVERIFIED — token works, email not verified yet
#   INVALID    — wrong / rejected token
#   ERROR      — network / rate-limit
# ═══════════════════════════════════════════════════════════════
def check_token(token: str, proxy_config: Dict = None) -> str:
    try:
        session = tls_client.Session(client_identifier="chrome_138", random_tls_extension_order=True)
        if proxy_config:
            proxy_dict = get_session_proxy(proxy_config)
            if proxy_dict:
                session.proxies = proxy_dict
        headers = {
            'Authorization': token,
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
        }
        response = session.get('https://discord.com/api/v9/users/@me', headers=headers)

        if response.status_code == 200:
            try:
                data = response.json() or {}
            except Exception:
                data = {}

            verified        = bool(data.get('verified', False))
            required_action = str(data.get('required_action') or '').upper()

            # Discord signals phone-gating via required_action
            if required_action:
                if 'PHONE' in required_action:
                    return 'LOCKED'
                if 'EMAIL' in required_action:
                    return 'UNVERIFIED'

            if not verified:
                return 'UNVERIFIED'
            return 'VALID'

        if response.status_code == 401:
            return 'INVALID'

        if response.status_code == 403:
            body_lower = ''
            try:
                body_lower = json.dumps(response.json() or {}).lower()
            except Exception:
                body_lower = (response.text or '').lower()
            if 'phone' in body_lower:
                return 'LOCKED'
            return 'INVALID'

        if response.status_code == 429:
            return 'ERROR'

        return 'INVALID'
    except Exception as e:
        log.debug(f"Token check error: {e}")
        return 'ERROR'


def check_email_verified_api(token: str, proxy_config: Dict = None):
    """Legacy helper — returns (verified_bool_or_None, email_or_None)."""
    try:
        session = tls_client.Session(client_identifier="chrome_138", random_tls_extension_order=True)
        if proxy_config:
            proxy_dict = get_session_proxy(proxy_config)
            if proxy_dict:
                session.proxies = proxy_dict
        headers = {
            'Authorization': token,
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = session.get('https://discord.com/api/v9/users/@me', headers=headers)
        if response.status_code == 200:
            data = response.json()
            verified = data.get('verified', False)
            email = data.get('email', 'N/A')
            return verified, email
        return None, None
    except:
        return None, None


EVENT_CALLBACK = None

def set_event_callback(cb):
    global EVENT_CALLBACK
    EVENT_CALLBACK = cb

def save_account_to_file(email: str, password: str, token: str, status: str):
    global SESSION_VALID, SESSION_LOCKED, SESSION_INVALID, SESSION_UNVERIFIED, EVENT_CALLBACK
    try:
        if status == 'VALID':
            output_file = OUTPUT_DIR / "valid.txt"
            with LOCK:
                SESSION_VALID += 1
        elif status == 'LOCKED':
            output_file = OUTPUT_DIR / "locked.txt"
            with LOCK:
                SESSION_LOCKED += 1
        elif status == 'UNVERIFIED':
            output_file = OUTPUT_DIR / "unverified.txt"
            with LOCK:
                SESSION_UNVERIFIED += 1
        else:  # INVALID / ERROR
            output_file = OUTPUT_DIR / "invalid.txt"
            with LOCK:
                SESSION_INVALID += 1

        with LOCK:
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(f"{email}:{password}:{token}\n")
        log.success(f"Saved [{status}] → {output_file.name}")

        if EVENT_CALLBACK:
            try:
                EVENT_CALLBACK("account_saved", {
                    "email": email,
                    "password": password,
                    "token": token,
                    "status": status,
                    "valid": SESSION_VALID,
                    "locked": SESSION_LOCKED,
                    "invalid": SESSION_INVALID,
                    "unverified": SESSION_UNVERIFIED,
                    "created": SESSION_CREATED
                })
            except Exception:
                pass
        return True
    except Exception as e:
        log.error(f"Failed to save account: {e}")
        return False


WASTED_MAILS_FILE = Path("wasted_mails.txt")
WASTED_LOCK = threading.Lock()
WASTED_PROVIDERS = ()


def save_wasted_mail(email: str, password: str, token: str, uuid: str, provider: str):
    if provider not in WASTED_PROVIDERS or not email:
        return
    line = f"{email}:{password or ''}:{token or ''}:{uuid or ''}"
    try:
        with WASTED_LOCK:
            with open(WASTED_MAILS_FILE, 'a', encoding='utf-8') as f:
                f.write(line + "\n")
        log.warning(f"Wasted mail saved → {WASTED_MAILS_FILE.name}")
    except Exception as e:
        log.error(f"Failed to save wasted mail: {e}")


def pop_wasted_mail() -> Optional[tuple]:
    try:
        with WASTED_LOCK:
            if not WASTED_MAILS_FILE.exists():
                return None
            lines = [l for l in WASTED_MAILS_FILE.read_text(encoding='utf-8').splitlines() if l.strip()]
            if not lines:
                return None
            first = lines.pop(0)
            WASTED_MAILS_FILE.write_text(
                ("\n".join(lines) + "\n") if lines else "",
                encoding='utf-8',
            )
    except Exception as e:
        log.error(f"Failed to read wasted mail: {e}")
        return None
    parts = first.split(":")
    email    = parts[0] if len(parts) > 0 else ""
    password = parts[1] if len(parts) > 1 else ""
    token    = parts[2] if len(parts) > 2 else ""
    uuid     = parts[3] if len(parts) > 3 else ""
    return email, password, token, uuid


async def human_type(element, text: str):
    for char in text:
        await element.send_keys(char)
        await asyncio.sleep(random.uniform(0.005, 0.02))


async def clear_and_type(page, selector: str, value: str, timeout: int = 45):
    try:
        element = None
        for _ in range(5):
            try:
                element = await page.select(selector, timeout=timeout//5)
                if element:
                    break
            except Exception:
                await asyncio.sleep(2)
        if not element:
            raise Exception(f"Element not found: {selector}")
        selector_js = json.dumps(selector)
        await page.evaluate(
            f'''() => {{
                const el = document.querySelector({selector_js});
                if (!el) return;
                el.focus();
                el.value = "";
                el.dispatchEvent(new Event("input", {{ bubbles: true }}));
                el.dispatchEvent(new Event("change", {{ bubbles: true }}));
            }}'''
        )
        await asyncio.sleep(random.uniform(0.01, 0.04))
        await human_type(element, value)
    except Exception as e:
        raise e


async def fill_registration_form(page, email: str, display_name: str, username: str, password: str, config: dict = None) -> bool:
    try:
        log.info("Filling form...")
        try:
            await clear_and_type(page, 'input[name="email"]', email, timeout=45)
            await asyncio.sleep(random.uniform(0.05, 0.15))
        except Exception:
            return False
        try:
            await clear_and_type(page, 'input[name="global_name"]', display_name, timeout=20)
            await asyncio.sleep(random.uniform(0.05, 0.15))
        except Exception:
            return False
        try:
            await clear_and_type(page, 'input[name="username"]', username, timeout=20)
            await asyncio.sleep(random.uniform(0.05, 0.15))
        except Exception:
            return False
        try:
            await clear_and_type(page, 'input[name="password"]', password, timeout=20)
            await asyncio.sleep(random.uniform(0.05, 0.15))
        except Exception:
            return False
        await asyncio.sleep(0.1)
        await fill_date_of_birth(page)
        await asyncio.sleep(0.05)
        try:
            await page.evaluate(JS_UTILS)
            await asyncio.sleep(0.05)
            await page.evaluate('window.utils.clickAllCheckboxes()')
            await asyncio.sleep(0.05)
        except Exception:
            pass
        clicked = False
        await asyncio.sleep(0.1)
        try:
            buttons = await page.select_all('button')
            for button in buttons:
                try:
                    text = await button.get('textContent') or getattr(button, 'text', '') or ""
                    text = str(text).strip()
                    if text and any(keyword in text for keyword in ['Continue', 'Create', 'Submit', 'Register']):
                        await button.click()
                        clicked = True
                        break
                except Exception:
                    continue
        except Exception:
            pass
        if not clicked:
            try:
                submit = await page.select('[type="submit"]', timeout=0)
                if submit:
                    await submit.click()
                    clicked = True
            except Exception:
                pass
        if not clicked:
            try:
                clicked_eval = await page.evaluate('''() => {
                    const buttons = document.querySelectorAll('button');
                    for (const btn of buttons) {
                        const text = btn.textContent || '';
                        if (text.includes('Continue') || text.includes('Create') || text.includes('Submit')) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                }''')
                if clicked_eval:
                    clicked = True
            except Exception:
                pass
        if not clicked:
            log.error("Could not find submit button")
            return False
        log.success("Form submitted!")
        return True
    except Exception as e:
        log.error(f"Form fill error: {e}")
        return False


async def fill_date_of_birth(page):
    try:
        import nodriver.cdp.input_ as cdp_input
    except ImportError:
        import truedriver.cdp.input_ as cdp_input
    try:
        month_el = await page.select('[aria-label*="Month"], [aria-label*="Mês"]', timeout=5)
        if month_el:
            await month_el.click()
            await asyncio.sleep(0.05)
            month_scrolls = random.randint(1, 11)
            for _ in range(month_scrolls):
                await page.send(cdp_input.dispatch_key_event(type_="keyDown", key="ArrowDown", windows_virtual_key_code=40, native_virtual_key_code=40))
                await page.send(cdp_input.dispatch_key_event(type_="keyUp", key="ArrowDown", windows_virtual_key_code=40, native_virtual_key_code=40))
                await asyncio.sleep(0.005)
            await asyncio.sleep(0.05)
            await page.send(cdp_input.dispatch_key_event(type_="keyDown", key="Enter", windows_virtual_key_code=13, native_virtual_key_code=13))
            await page.send(cdp_input.dispatch_key_event(type_="keyUp", key="Enter", windows_virtual_key_code=13, native_virtual_key_code=13))
            await asyncio.sleep(0.05)
        day_el = await page.select('[aria-label*="Day"], [aria-label*="Dia"]', timeout=5)
        if day_el:
            await day_el.click()
            await asyncio.sleep(0.05)
            day_scrolls = random.randint(1, 28)
            for _ in range(day_scrolls):
                await page.send(cdp_input.dispatch_key_event(type_="keyDown", key="ArrowDown", windows_virtual_key_code=40, native_virtual_key_code=40))
                await page.send(cdp_input.dispatch_key_event(type_="keyUp", key="ArrowDown", windows_virtual_key_code=40, native_virtual_key_code=40))
                await asyncio.sleep(0.005)
            await asyncio.sleep(0.05)
            await page.send(cdp_input.dispatch_key_event(type_="keyDown", key="Enter", windows_virtual_key_code=13, native_virtual_key_code=13))
            await page.send(cdp_input.dispatch_key_event(type_="keyUp", key="Enter", windows_virtual_key_code=13, native_virtual_key_code=13))
            await asyncio.sleep(0.05)
        year_el = await page.select('[aria-label*="Year"], [aria-label*="Ano"]', timeout=5)
        if year_el:
            await year_el.click()
            await asyncio.sleep(0.05)
            year_scrolls = random.randint(25, 35)
            for _ in range(year_scrolls):
                await page.send(cdp_input.dispatch_key_event(type_="keyDown", key="ArrowDown", windows_virtual_key_code=40, native_virtual_key_code=40))
                await page.send(cdp_input.dispatch_key_event(type_="keyUp", key="ArrowDown", windows_virtual_key_code=40, native_virtual_key_code=40))
                await asyncio.sleep(0.005)
            await asyncio.sleep(0.05)
            await page.send(cdp_input.dispatch_key_event(type_="keyDown", key="Enter", windows_virtual_key_code=13, native_virtual_key_code=13))
            await page.send(cdp_input.dispatch_key_event(type_="keyUp", key="Enter", windows_virtual_key_code=13, native_virtual_key_code=13))
            await asyncio.sleep(0.05)
    except Exception as e:
        log.debug(f"DOB error: {e}")


async def wait_for_account_creation(page, timeout: int = 900) -> bool:
    deadline = time.time() + timeout
    last_url = ""
    captcha_logged = False
    log.info("Waiting for you to solve the captcha manually in the browser window...")
    log.info(f"(timeout: {timeout}s)")
    while time.time() < deadline:
        await asyncio.sleep(1.0)
        try:
            try:
                current_url = await page.evaluate('window.location.href')
                if hasattr(current_url, 'value'):
                    current_url = current_url.value or ""
                elif isinstance(current_url, tuple):
                    current_url = str(current_url[0]) if current_url[0] else ""
                else:
                    current_url = str(current_url) if current_url else ""
            except Exception:
                current_url = ""
            if current_url and current_url != last_url:
                last_url = current_url
            if current_url:
                skip = ['discord.com/register', 'discord.com/login', 'about:blank', 'chrome://']
                if 'discord.com' in current_url and not any(s in current_url for s in skip):
                    log.success(f"Account created! Redirected to: {current_url}")
                    return True
            try:
                has_captcha = await page.evaluate('''() => {
                    const frames = document.querySelectorAll('iframe');
                    for (const f of frames) {
                        const src = f.src || '';
                        if (src.includes('hcaptcha') || src.includes('captcha') || src.includes('recaptcha'))
                            return true;
                    }
                    return false;
                }''')
                if has_captcha and not captcha_logged:
                    log.info("Captcha detected — solve it manually in the browser window")
                    captcha_logged = True
                elif not has_captcha and captcha_logged:
                    log.success("Captcha cleared — waiting for redirect...")
                    captcha_logged = False
            except Exception:
                pass
        except Exception as e:
            log.debug(f"URL check error: {e}")
    log.error("Timeout waiting for account creation")
    return False


async def wait_for_discord_token(page, timeout: int = 30, email: str = None, password: str = None, proxy_config: Dict = None):
    if not email or not password:
        log.error("Email and password required for API token fetch")
        return None
    await asyncio.sleep(3)
    log.info("Fetching token via API login...")
    for attempt in range(5):
        try:
            token = await fetch_discord_token(email, password, proxy_config)
            if token:
                log.success(f"Token via API login (attempt {attempt + 1})")
                return token
            log.warning(f"API returned empty token (attempt {attempt + 1}/5)")
        except Exception as e:
            log.debug(f"API login error: {e}")
        await asyncio.sleep(3)
    log.error("Could not obtain token via API")
    return None


async def verify_email_with_url(browser, verify_url: str, token: str, timeout: int = 60) -> bool:
    if not verify_url:
        return False
    log.info("Opening verification link...")
    try:
        from urllib.parse import urlparse, parse_qs
        parsed  = urlparse(verify_url)
        params  = parse_qs(parsed.query)
        email_verify_token = params.get('token', [None])[0]
        if email_verify_token:
            session = tls_client.Session(client_identifier='chrome_131', random_tls_extension_order=True)
            headers = {
                'Authorization': token, 'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Origin': 'https://discord.com', 'Referer': 'https://discord.com/',
            }
            resp = session.post('https://discord.com/api/v9/auth/verify',
                                headers=headers, json={'token': email_verify_token})
            if resp.status_code == 200:
                log.success("Email verified successfully!")
                return True
            log.debug(f"API verify returned {resp.status_code} — falling back to browser")
    except Exception as e:
        log.debug(f"API verify error: {e} — falling back to browser")
    try:
        tab = await browser.get(verify_url, new_tab=True)
        await asyncio.sleep(5)
        for _ in range(timeout // 5):
            await asyncio.sleep(5)
            verified, _ = check_email_verified_api(token)
            if verified:
                log.success("Email verified successfully!")
                return True
        return True
    except Exception as e:
        log.warning(f"Error opening verification URL: {e}")
        return False


async def verify_email_cowmail(email: str, password: str, browser, token: str, timeout: int = 120) -> bool:
    log.info("Waiting for CowMail verification email...")
    provider = _cowmail_providers.get(threading.current_thread().ident)
    if not provider:
        cm_cfg = config.get("email_provider", {}).get("cowmail", {})
        provider = MailcowProvider(cm_cfg)
        provider._created_email = email
        provider._created_password = password
    verify_url = await asyncio.get_event_loop().run_in_executor(
        None, lambda: provider.get_verify_url(timeout)
    )
    if verify_url:
        return await verify_email_with_url(browser, verify_url, token)
    log.warning("CowMail: verification email not found after timeout")
    return False


async def worker(worker_id: int, proxy_config: Dict = None, slot: int = 1, total: int = 1):
    global SESSION_CREATED, SESSION_STOP, ACTIVE_WORKERS
    if SESSION_STOP:
        return
    with WORKER_LOCK:
        ACTIVE_WORKERS += 1

    browser = None
    temp_profile = None
    account_created = False
    wasted_info = None

    try:
        log.info(f"Starting account creation...")
        if proxy_config:
            masked_proxy = proxy_config.get('masked_url', proxy_config.get('full_url', 'Unknown'))
            log.info(f"Using proxy (browser only): {masked_proxy}")

        username = generate_username()
        display_name = generate_display_name()

        email_from_api, email_password, email_token, email_uuid, email_provider = get_email_from_provider(config)

        if email_from_api:
            email = email_from_api
            password = email_password
            wasted_info = (email, email_password, email_token, email_uuid, email_provider)
            log.success(f"Fetched: {email}")
        else:
            log.error(f"Failed to get email")
            return

        temp_profile = tempfile.mkdtemp(prefix="yogi_brave_")
        worker_cache_dir = BROWSER_CACHE_DIR / Path(temp_profile).name
        worker_cache_dir.mkdir(parents=True, exist_ok=True)

        browser = await launch_browser(
            proxy_config=proxy_config,
            slot=slot,
            total=total,
            temp_profile=temp_profile,
            worker_cache_dir=str(worker_cache_dir),
        )

        # ── MANDATORY: visit 9captcha setup URL BEFORE register ──
        try:
            boot_page = await browser.get("about:blank")
            if boot_page is not None:
                await visit_ninecaptcha_setup(boot_page)
        except Exception as e:
            log.warning(f"9captcha boot step failed: {e}")

        page = await browser.get("https://discord.com/register")
        if page is None:
            log.error(f"Could not get browser page")
            return

        try:
            await page.wait_for_ready_state('complete', timeout=30000)
        except Exception:
            pass

        try:
            await page.evaluate(JS_UTILS)
        except Exception:
            pass

        log.info(f"Register page loaded")
        await asyncio.sleep(0.5)

        success = await fill_registration_form(page, email, display_name, username, password, config=config)
        if not success:
            log.error(f"Form fill failed")
            return

        log.info(f"Form filled")
        log.info(f"Waiting for captcha solve...")
        created = await wait_for_account_creation(page)

        if not created:
            log.error(f"Account creation failed - no redirect detected")
            return

        log.info(f"Extracting token...")
        token = await wait_for_discord_token(page, email=email, password=password, proxy_config=proxy_config)

        if token:
            if token.startswith('"') and token.endswith('"'):
                token = token[1:-1]
            token_match = re.search(r'([a-zA-Z0-9_-]{20,})\.([a-zA-Z0-9_-]{6})\.([a-zA-Z0-9_-]{27,})', token)
            if token_match:
                token = f"{token_match.group(1)}.{token_match.group(2)}.{token_match.group(3)}"
            log.info(f"Token: {log.mask_token(token)}")

            # Optional: still trigger email verification flow if not yet verified
            try:
                verified, _ = check_email_verified_api(token, None)
                if verified is False:
                    if email_provider == "mailcow":
                        ok = await verify_email_cowmail(email, email_password, browser, token)
                        if ok:
                            log.success("Email verified!")
                    elif email_provider == "duckmail":
                        dm_cfg = config.get("email_provider", {}).get("duckmail", {})
                        dm_base = dm_cfg.get("api_base", "https://api.duckmail.sbs")
                        ok = await verify_email_duckmail(
                            email=email, password=email_password,
                            bearer=email_token or "", browser=browser,
                            token=token, api_base=dm_base, timeout=180,
                        )
                        if ok:
                            log.success("Email verified!")
                    elif email_provider == "afhamxmailz":
                        am_cfg = config.get("email_provider", {}).get("afhamxmailz", {})
                        am_base = am_cfg.get("api_base", "https://api.afhamxmailz.com")
                        am_key  = am_cfg.get("api_key", "") or am_cfg.get("apiKey", "")
                        ok = await verify_email_afhamxmailz(
                            email=email, password=email_password,
                            inbox_id=email_token or "", browser=browser,
                            token=token, api_base=am_base, api_key=am_key,
                            timeout=180,
                        )
                        if ok:
                            log.success("Email verified!")
            except Exception as e:
                log.warning(f"Email verification step error (continuing): {e}")

            # Classify using new rules
            try:
                result = check_token(token, None)
                log.info(f"Token Status: {result}")
            except Exception as e:
                log.warning(f"Token check failed: {e}")
                result = 'ERROR'

            try:
                save_account_to_file(email, password, token, result)
            except Exception as e:
                log.error(f"Failed to save account: {e}")

            account_created = True
            with LOCK:
                SESSION_CREATED += 1
                created_now = SESSION_CREATED

            if sys.platform == 'win32':
                try:
                    import ctypes
                    t = f"/{SESSION_TARGET}" if SESSION_TARGET else "/∞"
                    ctypes.windll.kernel32.SetConsoleTitleW(
                        f"NILOY EVS GEN  |  {created_now}{t}  ✓{SESSION_VALID}  ⚠{SESSION_LOCKED}  ✗{SESSION_INVALID}"
                    )
                except:
                    pass

            log.success(f"Account #{created_now} created")

            try:
                proxy_str = (proxy_config.get('full_url') or proxy_config.get('url')) if proxy_config else None
                log.info(f"Humanizing account #{created_now}...")
                await asyncio.to_thread(_humanize_account, token, created_now, proxy_str)
            except Exception as e:
                log.error(f"Humanizer error: {e}")

            if SESSION_TARGET > 0 and created_now >= SESSION_TARGET:
                with LOCK:
                    SESSION_STOP = True
                log.success(f"Target reached! {created_now}/{SESSION_TARGET} accounts. Stopping...")
                return
        else:
            log.warning(f"Could not extract token")

    except Exception as e:
        log.error(f"Worker error: {e}")

    finally:
        if not account_created and wasted_info:
            save_wasted_mail(*wasted_info)

        if browser:
            try:
                await browser.stop()
            except Exception:
                pass
            await asyncio.sleep(0.2)

        _profile_to_delete = temp_profile
        _cache_to_delete = (
            BROWSER_CACHE_DIR / Path(temp_profile).name if temp_profile else None
        )

        def _background_cleanup():
            if _profile_to_delete and os.path.exists(_profile_to_delete):
                if PSUTIL_AVAILABLE:
                    try:
                        norm_profile = os.path.normpath(_profile_to_delete).lower()
                        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                            try:
                                cmdline = proc.info.get('cmdline') or []
                                cmd_str = ' '.join(cmdline).lower()
                                if norm_profile in cmd_str:
                                    proc.kill()
                                    proc.wait(timeout=3)
                            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                                pass
                    except Exception:
                        pass
                    time.sleep(0.5)

                def _on_exc(func, fpath, exc):
                    try:
                        os.chmod(fpath, 0o777)
                        func(fpath)
                    except Exception:
                        pass

                def _force_rmtree(path):
                    shutil.rmtree(path, onexc=_on_exc)

                for _attempt in range(15):
                    try:
                        _force_rmtree(_profile_to_delete)
                        break
                    except Exception:
                        time.sleep(2)
                else:
                    shutil.rmtree(_profile_to_delete, ignore_errors=True)

            if _cache_to_delete and _cache_to_delete.exists():
                try:
                    shutil.rmtree(_cache_to_delete, ignore_errors=True)
                except Exception:
                    pass

        threading.Thread(target=_background_cleanup, daemon=True).start()

        with WORKER_LOCK:
            ACTIVE_WORKERS -= 1


def _humanize_account(token: str, account_num: int = 1, proxy: Optional[str] = None) -> bool:
    _hmz_cfg = config.get('humanizer', {})
    if isinstance(_hmz_cfg, bool):
        if not _hmz_cfg:
            log.debug('Humanizer disabled in config')
            return False
        _hmz_cfg = {}
    elif not _hmz_cfg.get('enabled', True):
        log.debug('Humanizer disabled in config')
        return False
    try:
        import humanizer as _hz
        ok = _hz.humanize_token(token=token, proxy=proxy, config=config)
        if ok:
            log.success(f"Token #{account_num} humanized successfully")
        else:
            log.warning(f"Token #{account_num} humanization completed with warnings")
        return ok
    except ImportError as e:
        log.warning(f"Humanizer import failed: {e}")
        return False
    except Exception as e:
        log.warning(f"Humanizer error #{account_num}: {e}")
        return False


async def batch_cooldown(batch_size: int, accounts_created_in_batch: int):
    if accounts_created_in_batch == 0:
        return
    log.info(f"Batch of {batch_size} workers completed. Cooldown for {COOLDOWN_SECONDS}s...")
    for remaining in range(COOLDOWN_SECONDS, 0, -1):
        mins, secs = divmod(remaining, 60)
        print(f"\r{BLUE}[COOLDOWN]{RESET} Next Account Gen in: {CYAN}{mins:02d}:{secs:02d}{RESET} ", end='', flush=True)
        await asyncio.sleep(1)
    print()


async def rotate_adb_ip():
    try:
        await asyncio.to_thread(adb_rotator.auto_switch_ip)
    except Exception as e:
        log.warning(f"ADB rotation error: {e} — continuing")


async def run_workers():
    global SESSION_TARGET, SESSION_CREATED, SESSION_STOP, ACTIVE_WORKERS
    accounts_before_batch = 0
    _proxy_index = 0

    while not SESSION_STOP:
        with LOCK:
            if SESSION_TARGET > 0 and SESSION_CREATED >= SESSION_TARGET:
                SESSION_STOP = True
                break
        with LOCK:
            accounts_before_batch = SESSION_CREATED

        remaining = SESSION_TARGET - SESSION_CREATED if SESSION_TARGET > 0 else THREAD_COUNT
        batch_size = min(THREAD_COUNT, remaining) if SESSION_TARGET > 0 else THREAD_COUNT
        if batch_size <= 0 and SESSION_TARGET > 0:
            break

        if ADB_ENABLED:
            await rotate_adb_ip()

        tasks = []
        for i in range(batch_size):
            worker_id = random.randint(10000, 99999)
            if PROXY_LIST:
                current_proxy = PROXY_LIST[(_proxy_index + i) % len(PROXY_LIST)]
            else:
                current_proxy = None
            task = asyncio.create_task(worker(worker_id, current_proxy, i + 1, batch_size))
            tasks.append(task)

        if PROXY_LIST:
            _proxy_index = (_proxy_index + batch_size) % len(PROXY_LIST)

        log.info(f"Batch {batch_size} starting  {DIM}[{SESSION_CREATED}/{SESSION_TARGET if SESSION_TARGET else '∞'}]{RESET}")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        with LOCK:
            accounts_created_in_batch = SESSION_CREATED - accounts_before_batch

        if SESSION_TARGET > 0:
            if SESSION_CREATED < SESSION_TARGET:
                await batch_cooldown(batch_size, accounts_created_in_batch)
        else:
            await batch_cooldown(batch_size, accounts_created_in_batch)

        await asyncio.sleep(0.1)

    total = SESSION_VALID + SESSION_LOCKED + SESSION_INVALID + SESSION_UNVERIFIED
    sep = f"{DIM}  {'─'*52}{RESET}"
    print()
    print(sep)
    print(f"  {DIM}│{RESET}  {GRAY}{'Results':^50}{RESET}  {DIM}│{RESET}")
    print(sep)
    print(f"  {DIM}│{RESET}  {GRAY}{'Total Created':<24}{RESET} {WHITE}{total}{RESET}")
    print(f"  {DIM}│{RESET}  {GREEN}{'Valid':<24}{RESET} {GREEN}{SESSION_VALID}{RESET}")
    print(f"  {DIM}│{RESET}  {YELLOW}{'Locked':<24}{RESET} {YELLOW}{SESSION_LOCKED}{RESET}")
    print(f"  {DIM}│{RESET}  {RED}{'Invalid':<24}{RESET} {RED}{SESSION_INVALID}{RESET}")
    print(f"  {DIM}│{RESET}  {CYAN}{'Unverified':<24}{RESET} {CYAN}{SESSION_UNVERIFIED}{RESET}")
    print(sep)
    print()


async def main():
    global SESSION_TARGET, SESSION_CREATED, SESSION_STOP, ADB_ENABLED

    if sys.platform == 'win32':
        import ctypes
        try:
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 7
            )
        except Exception:
            pass

    W = WHITE; P = PURPLE; K = PINK; G = GRAY; R = RESET; D = DIM
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW("NILOY EVS GEN  |  Manual Cap")

    import shutil
    term_width = shutil.get_terminal_size((80, 24)).columns
    print()

    C = [
        '\033[38;2;174;220;255m',
        '\033[38;2;190;230;255m',
        '\033[38;2;210;240;255m',
        '\033[38;2;230;245;255m',
        '\033[38;2;245;250;255m',
        '\033[38;2;255;255;255m',
    ]

    rows = [
    "███╗   ██╗███████╗██╗  ██╗ ██████╗ ██████╗  █████╗     ███████╗██╗   ██╗███████╗",
    "████╗  ██║██╔════╝╚██╗██╔╝██╔═══██╗██╔══██╗██╔══██╗    ██╔════╝██║   ██║██╔════╝",
    "██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║██████╔╝███████║    █████╗  ██║   ██║███████╗",
    "██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║██╔══██╗██╔══██║    ██╔══╝  ╚██╗ ██╔╝╚════██║",
    "██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝██║  ██║██║  ██║    ███████╗ ╚████╔╝ ███████║",
    "╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝    ╚══════╝  ╚═══╝  ╚══════╝"
]
    for i, art in enumerate(rows):
        pad = max(0, (term_width - len(art)) // 2)
        print(f"{' ' * pad}{C[i]}{BOLD}{art}{RESET}")

    subtitle_plain = "EVS GEN  ·  AUTO CAP  ·  V3"
    pad = max(0, (term_width - len(subtitle_plain)) // 2)
    _c1 = '\033[38;2;174;220;255m'
    _c2 = '\033[38;2;255;255;255m'
    print(
        f"{' ' * pad}"
        f"{_c1}{BOLD}MADE BY NEXUVER .gg/nexoramarketplace{RESET}"
        f"{DIM}  ·  {RESET}"
        f"{_c1}{BOLD}AUTO CAPTCHA SOLVE{RESET}"
        f"{DIM}  ·  {RESET}"
        f"{_c2}{BOLD}V2{RESET}"
    )
    print()

    provider = config.get("email_provider", {}).get("name", "")
    sep = f"{DIM}  {'─'*62}{RESET}"
    print(sep)

    def row(label, value, vcolor=WHITE):
        print(f"  {DIM}│{RESET}  {GRAY}{label:<18}{RESET} {vcolor}{value}{RESET}")

    if provider == "duckmail":
        dm_cfg = config.get("email_provider", {}).get("duckmail", {})
        dm_base = dm_cfg.get("api_base", "https://api.duckmail.sbs")
        custom = dm_cfg.get("domain", "").strip()
        label = f"DuckMail  [{dm_base}]"
        if custom:
            label += f"  custom:{custom}"
        row("Provider", label, GREEN)
    elif provider == "afhamxmailz":
        am_cfg = config.get("email_provider", {}).get("afhamxmailz", {})
        am_base = am_cfg.get("api_base", "https://api.afhamxmailz.com")
        am_type = am_cfg.get("type", "discord")
        row("Provider", f"AfhamXMailz  [{am_base}]  type={am_type}", GREEN)
    else:
        mc_domain = config.get("email_provider", {}).get("cowmail", {}).get("domain", "")
        row("Provider", f"CowMail (Mailcow)  [{mc_domain}]", GREEN)
    _, b_name = get_browser_executable()
    row("Browser",   b_name, CYAN)
    row("Threads",   str(THREAD_COUNT), YELLOW)
    row("Cooldown",  f"{COOLDOWN_SECONDS}s", YELLOW)
    if ADB_ENABLED:
        row("ADB IP Switch", "On  [auto]", GREEN)
    else:
        row("ADB IP Switch", "Off", GRAY)
    nopecha_cfg = config.get("nopecha", {}) or {}
    nopecha_on = nopecha_cfg.get("enabled", False) if isinstance(nopecha_cfg, dict) else bool(nopecha_cfg)
    row("Captcha Solver", "NopeCHA (auto)" if nopecha_on else "Autocap (bot solve it)", CYAN)
    ninecaptcha_cfg = config.get("ninecaptcha", {}) or {}
    ninecaptcha_on = ninecaptcha_cfg.get("enabled", False) if isinstance(ninecaptcha_cfg, dict) else bool(ninecaptcha_cfg)
    row("9captcha", "On (extension)" if ninecaptcha_on else "Off", GREEN if ninecaptcha_on else GRAY)
    print(sep)
    print()

    SESSION_TARGET = 0
    while True:
        try:
            count = input(f"\n  {PURPLE}┌─{RESET} {WHITE}How many accounts?  {DIM}(0 = infinite){RESET}\n  {PURPLE}└─▶ {PINK}{BOLD}").strip()
            print(RESET, end="")
            if count.isdigit():
                SESSION_TARGET = int(count)
                break
        except:
            pass

    await setup_nopecha()
    await setup_ninecaptcha()

    global PROXY_LIST
    proxy_cfg = config.get("proxy", {})
    PROXY_LIST = load_proxies(
        proxy_cfg.get("file", "input/proxies.txt"),
        proxy_cfg.get("enabled", False),
    )
    if PROXY_LIST:
        log.info(f"Loaded {len(PROXY_LIST)} proxies for rotation")
    elif not ADB_ENABLED:
        log.info("No proxies — using system IP")

    if ADB_ENABLED:
        if not adb_rotator.initialize():
            ADB_ENABLED = False

    try:
        await run_workers()
    except asyncio.CancelledError:
        log.info("Stopping workers...")
        with LOCK:
            SESSION_STOP = True
    except KeyboardInterrupt:
        log.info("Interrupted by user...")
        with LOCK:
            SESSION_STOP = True
        await asyncio.sleep(2)


def stop_generation():
    global SESSION_STOP
    with LOCK:
        SESSION_STOP = True
    log.info("Generation stop requested.")

async def run_generation_task(target: int = 1, threads: Optional[int] = None, event_callback = None):
    global SESSION_TARGET, SESSION_CREATED, SESSION_STOP, THREAD_COUNT
    global SESSION_VALID, SESSION_LOCKED, SESSION_INVALID, SESSION_UNVERIFIED
    global PROXY_LIST, EVENT_CALLBACK

    EVENT_CALLBACK = event_callback
    with LOCK:
        SESSION_TARGET = target
        SESSION_CREATED = 0
        SESSION_STOP = False
        SESSION_VALID = 0
        SESSION_LOCKED = 0
        SESSION_INVALID = 0
        SESSION_UNVERIFIED = 0
        if threads:
            THREAD_COUNT = max(1, threads)

    await setup_nopecha()
    await setup_ninecaptcha()

    proxy_cfg = config.get("proxy", {})
    PROXY_LIST = load_proxies(
        proxy_cfg.get("file", str(Path(__file__).resolve().parent / "input" / "proxies.txt")),
        proxy_cfg.get("enabled", False),
    )

    try:
        await run_workers()
    except asyncio.CancelledError:
        stop_generation()

    return {
        "valid": SESSION_VALID,
        "locked": SESSION_LOCKED,
        "invalid": SESSION_INVALID,
        "unverified": SESSION_UNVERIFIED,
        "total": SESSION_CREATED
    }


if __name__ == "__main__":
    warnings.filterwarnings('ignore', category=ResourceWarning)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}[WARNING]{RESET} Stopped by user")
    except Exception as e:
        print(f"\n{RED}[ERROR]{RESET} {e}")