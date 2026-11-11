import sys
import threading
import time
import random
import re
import json
import base64
import uuid
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from colorama import Fore, Style
from curl_cffi import requests as curl_requests
import httpx
from onyx import Solver as OnyxSolver
from kenz import Solver as KenzSolver
from logger import Console
from solver import VoidSolverBasic

console = Console()

from pathlib import Path

# ==================== CONFIG LOADING ====================
def load_config(path=None) -> dict:
    if path is None:
        default_p = Path(__file__).resolve().parent / "config.json"
        path = str(default_p) if default_p.exists() else "config.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        console.warning(f"config.json not found — using built-in defaults.")
        return {}
    except json.JSONDecodeError as e:
        console.failed(f"config.json parse error: {e}")
        sys.exit(1)

CFG = load_config()

# ==================== GLOBAL SETTINGS ====================
SINGLE_PROXY_PV    = CFG.get("proxy", "http://09a8e4291eb54283d891:592924c2676e6ae4@gw.dataimpulse.com:10000")
DISCORD_TIMEZONE   = CFG.get("discord_timezone", "Europe/London")

# Captcha
_CAP               = CFG.get("captcha", {})
CAPTCHA_SOLVER     = _CAP.get("solver", "onyx").lower()   # "onyx", "hcaptchasolver", or "voidsolver"
ONYX_API_KEY       = _CAP.get("onyx_api_key", "")
HCAPTCHASOLVER_KEY = _CAP.get("hcaptchasolver_api_key", "")
VOIDSOLVER_KEY     = _CAP.get("voidsolver_api_key", "")

# 5sim
_5SIM              = CFG.get("5sim", {})
FIVESIM_API_KEY    = _5SIM.get("api_key", "")
FIVESIM_API_URL    = _5SIM.get("api_url", "https://5sim.net/v1")
FIVESIM_COUNTRY    = _5SIM.get("country", "indonesia")
FIVESIM_OPERATOR   = _5SIM.get("operator", "virtual51")

# SMSBower
_BOWER             = CFG.get("smsbower", {})
SMSBOWER_API_KEY   = _BOWER.get("api_key", "")
SMSBOWER_API_URL   = _BOWER.get("api_url", "https://smsbower.page/stubs/handler_api.php")
SMSBOWER_COUNTRY   = _BOWER.get("country", "73")
SMSBOWER_SERVICE   = _BOWER.get("service", "ds")

# HeroSMS
_HERO              = CFG.get("herosms", {})
HEROSMS_API_KEY    = _HERO.get("api_key", "")
HEROSMS_API_URL    = _HERO.get("api_url", "https://hero.sms-activate.io/stubs/handler_api.php")
HEROSMS_COUNTRY    = _HERO.get("country", "0")
HEROSMS_SERVICE    = _HERO.get("service", "ds")

# TigerSMS
_TIGER             = CFG.get("tigersms", {})
TIGERSMS_API_KEY   = _TIGER.get("api_key", "")
TIGERSMS_API_URL   = _TIGER.get("api_url", "https://api.tiger-sms.com/stubs/handler_api.php")
TIGERSMS_COUNTRY   = _TIGER.get("country", "0")
TIGERSMS_SERVICE   = _TIGER.get("service", "ds")

# Active phone service — loaded from config.json ("5sim" | "smsbower" | "herosms" | "tigersms")
PHONE_SERVICE      = CFG.get("phone_service", "5sim").lower()

# Threads & token file — loaded from config.json
CFG_THREADS        = CFG.get("threads", 5)
CFG_TOKEN_FILE     = CFG.get("token_file", "locked.txt")

HCAPTCHA_SITE_KEY  = "a9b5fb07-92ff-493f-86fe-352a2803b3df"
HCAPTCHA_SITE_URL  = "https://discord.com"
IMPERSONATE        = "chrome136"
UA                 = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
SEC_CH_UA          = '"Not(A:Brand";v="8", "Chromium";v="136", "Google Chrome";v="136"'
BROWSER_VERSION    = "136.0.0.0"
FALLBACK_BUILD     = 503231


# ==================== LOGGING ====================
def log(message, status="info"):
    if status == "success":
        console.success(message)
    elif status == "failure":
        console.failed(message)
    elif status == "warning":
        console.warning(message)
    else:
        console.info(message)


# ==================== TOKEN READING ====================
def parse_token_lines(lines: list) -> list:
    tokens = []
    for idx, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' in line:
            parts = line.split(':')
            if len(parts) >= 3:
                email    = parts[0].strip()
                password = parts[1].strip()
                token    = ':'.join(parts[2:]).strip()
                tokens.append({'email': email, 'token': token, 'password': password, 'line_num': idx})
            elif len(parts) == 2:
                tokens.append({'email': 'N/A', 'token': parts[0].strip(), 'password': parts[1].strip(), 'line_num': idx})
            else:
                log(f"Line {idx}: Invalid format - skipping", "warning")
        else:
            tokens.append({'email': 'N/A', 'token': line.strip(), 'password': None, 'line_num': idx})
    return tokens


def read_tokens_from_file(filename="locked.txt"):
    try:
        p = Path(filename)
        if not p.is_absolute() and not p.exists():
            parent_p = Path(__file__).resolve().parent / filename
            if parent_p.exists():
                p = parent_p
        with open(p, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        return parse_token_lines(lines)
    except FileNotFoundError:
        log(f"File '{filename}' not found!", "failure")
        return []
    except Exception as e:
        log(f"Error reading tokens: {e}", "failure")
        return []
    except Exception as e:
        log(f"Error reading tokens: {e}", "failure")
        return []


# ==================== SESSION CONTEXT ====================
def _new_session(proxy: str = None) -> curl_requests.Session:
    s = curl_requests.Session(impersonate=IMPERSONATE)
    if proxy:
        p = proxy if proxy.startswith("http") else f"http://{proxy}"
        s.proxies = {"http": p, "https": p}
    return s


def generate_client_launch_id():
    return str(uuid.uuid4())


def generate_launch_signature():
    return str(uuid.uuid4())


class SessionContext:
    def __init__(self, proxy=None):
        self.session      = _new_session(proxy)
        self.build_number = FALLBACK_BUILD
        self._proxy       = proxy
        self.fingerprint  = None
        self.super_properties = self._encode_super_props()

    def _nav_headers(self) -> dict:
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "max-age=0",
            "Sec-Ch-Ua": SEC_CH_UA,
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": UA,
        }

    def _encode_super_props(self) -> str:
        props = {
            "os": "Windows", "browser": "Chrome", "device": "",
            "system_locale": "en-US", "has_client_mods": False,
            "browser_user_agent": UA, "browser_version": BROWSER_VERSION,
            "os_version": "10", "referrer": "", "referring_domain": "",
            "referrer_current": "", "referring_domain_current": "",
            "release_channel": "stable",
            "client_build_number": self.build_number,
            "client_event_source": None,
            "client_launch_id": generate_client_launch_id(),
            "launch_signature": generate_launch_signature(),
            "client_heartbeat_session_id": str(uuid.uuid4()),
            "client_app_state": "focused"
        }
        return base64.b64encode(json.dumps(props, separators=(',', ':')).encode()).decode()

    def get_fingerprint(self):
        try:
            r = self.session.get(
                "https://discord.com/api/v9/experiments",
                headers=self.get_headers(endpoint_type="api", include_fingerprint=False),
                timeout=10
            )
            if r.status_code == 200:
                fp = r.json().get("fingerprint")
                if fp:
                    self.fingerprint = fp
                    return fp
        except Exception:
            pass
        return None

    def get_headers(self, endpoint_type="api", include_auth=None,
                    include_fingerprint=True, referer="https://discord.com/channels/@me") -> dict:
        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9",
            "Priority": "u=1, i",
            "User-Agent": UA,
            "Sec-Ch-Ua": SEC_CH_UA,
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
        if endpoint_type == "api":
            headers["Content-Type"] = "application/json"
            headers["Origin"] = "https://discord.com"
            headers["Referer"] = referer
            headers["X-Discord-Locale"] = "en-US"
            headers["X-Discord-Timezone"] = DISCORD_TIMEZONE
            headers["X-Debug-Options"] = "bugReporterEnabled"
            headers["X-Super-Properties"] = self.super_properties
        if include_auth:
            headers["Authorization"] = include_auth
        if include_fingerprint and self.fingerprint:
            headers["X-Fingerprint"] = self.fingerprint
        return headers


# ==================== UTILITY ====================
def _get_proxy():
    return SINGLE_PROXY_PV


# ==================== CAPTCHA SOLVING ====================
def _strip_proxy_scheme(proxy: str) -> str:
    """Both Onyx and hCaptchaSolver expect proxy WITHOUT the http:// scheme."""
    if proxy and proxy.startswith(("http://", "https://")):
        return proxy.split("://", 1)[1]
    return proxy


def _solve_captcha(ctx: SessionContext, sitekey, rqdata="", rqtoken="", session_id=""):
    proxy     = _get_proxy()
    cap_proxy = _strip_proxy_scheme(proxy)   # scheme-less for solver APIs
    cap       = None

    if CAPTCHA_SOLVER == "hcaptchasolver":
        solver = KenzSolver(api_key=HCAPTCHASOLVER_KEY)
    elif CAPTCHA_SOLVER == "voidsolver":
        solver = VoidSolverBasic(api_key=VOIDSOLVER_KEY)
    else:
        solver = OnyxSolver(api_key=ONYX_API_KEY)

    for attempt in range(1, 4):
        try:
            cap, cookies = solver.solve_hcaptcha(
                url=HCAPTCHA_SITE_URL,
                sitekey=sitekey,
                rqdata=rqdata,
                user_agent=UA,
                proxy=cap_proxy,
                timeout=120,
                poll_interval=1,
                pow_type="hsw",
                token="discord_pv"
            )
            if cap:
                break
        except Exception as e:
            if "Rate limited by hCaptcha" in str(e):
                time.sleep(2)
                continue
            log(f"Captcha solver error: {e}", "failure")
            break
    return cap


# ==================== 5SIM ====================
def _fivesim_headers() -> dict:
    return {
        "Authorization": f"Bearer {FIVESIM_API_KEY}",
        "Accept":        "application/json",
    }


def _purchase_phone_5sim(attempt=1, max_attempts=9):
    proxy = _get_proxy()
    try:
        url = f"{FIVESIM_API_URL}/user/buy/activation/{FIVESIM_COUNTRY}/{FIVESIM_OPERATOR}/discord"
        r = httpx.get(url, headers=_fivesim_headers(), proxy=proxy, timeout=15, follow_redirects=True)
        if r.status_code == 200:
            data     = r.json()
            order_id = str(data["id"])
            phone    = str(data["phone"])
            return order_id, phone, None
        else:
            if attempt < max_attempts:
                return _purchase_phone_5sim(attempt + 1, max_attempts)
            log("[5sim] Failed to purchase number", "failure")
            return None, None, None
    except Exception as e:
        log(f"[5sim] Purchase error: {e}", "failure")
        if attempt < max_attempts:
            return _purchase_phone_5sim(attempt + 1, max_attempts)
        return None, None, None


def _manage_order_5sim(order_id, action="finish"):
    try:
        proxy    = _get_proxy()
        endpoint = {"finish": "finish", "cancel": "cancel", "ban": "ban"}.get(action, "cancel")
        url      = f"{FIVESIM_API_URL}/user/cancel/{order_id}" if endpoint == "cancel" \
                   else f"{FIVESIM_API_URL}/user/{endpoint}/{order_id}"
        httpx.get(url, headers=_fivesim_headers(), proxy=proxy, timeout=10, follow_redirects=True)
    except Exception as e:
        log(f"[5sim] Manage order error: {e}", "warning")


def _fetch_otp_5sim(order_id, timeout=180):
    proxy     = _get_proxy()
    url       = f"{FIVESIM_API_URL}/user/check/{order_id}"
    start     = time.time()
    check_cnt = 0

    while time.time() - start < timeout:
        try:
            r = httpx.get(url, headers=_fivesim_headers(), proxy=proxy, timeout=10, follow_redirects=True)
            if r.status_code == 200:
                data   = r.json()
                status = data.get("status", "")
                if status == "RECEIVED":
                    sms_list = data.get("sms", [])
                    if sms_list:
                        raw_text = sms_list[-1].get("text", "") or sms_list[-1].get("code", "")
                        m = re.search(r'\b\d{4,8}\b', raw_text)
                        if m:
                            log(f"OTP received: {m.group(0)}", "success")
                            return m.group(0)
                elif status in ("CANCELED", "TIMEOUT", "BANNED"):
                    return None
        except Exception as e:
            log(f"[5sim] OTP poll error: {e}", "warning")

        check_cnt += 1
        time.sleep(2)

    log("[5sim] OTP timeout", "failure")
    return None


# ==================== SMSBOWER ====================
def _purchase_phone_smsbower(attempt=1, max_attempts=9):
    proxy = _get_proxy()
    try:
        params = {
            "api_key":  SMSBOWER_API_KEY,
            "action":   "getNumber",
            "service":  SMSBOWER_SERVICE,
            "country":  SMSBOWER_COUNTRY,
            "maxPrice": "0.01",
        }
        r = httpx.get(SMSBOWER_API_URL, params=params, timeout=15)
        text = r.text.strip()
        if text.startswith("ACCESS_NUMBER"):
            parts    = text.split(":")
            order_id = parts[1]
            phone    = parts[2]
            if not phone.startswith("+"):
                phone = f"+{phone}"
            return order_id, phone, None
        else:
            if attempt < max_attempts:
                return _purchase_phone_smsbower(attempt + 1, max_attempts)
            log("[SMSBower] Failed to purchase number", "failure")
            return None, None, None
    except Exception as e:
        log(f"[SMSBower] Purchase error: {e}", "failure")
        if attempt < max_attempts:
            return _purchase_phone_smsbower(attempt + 1, max_attempts)
        return None, None, None


def _manage_order_smsbower(order_id, action="finish"):
    status_map = {"finish": "6", "cancel": "8", "ban": "8"}
    try:
        params = {
            "api_key": SMSBOWER_API_KEY,
            "action":  "setStatus",
            "id":      order_id,
            "status":  status_map.get(action, "8"),
        }
        httpx.get(SMSBOWER_API_URL, params=params, timeout=10)
    except Exception as e:
        log(f"[SMSBower] Manage order error: {e}", "warning")


def _fetch_otp_smsbower(order_id, timeout=180):
    start     = time.time()
    check_cnt = 0

    while time.time() - start < timeout:
        try:
            params = {
                "api_key": SMSBOWER_API_KEY,
                "action":  "getStatus",
                "id":      order_id,
            }
            r    = httpx.get(SMSBOWER_API_URL, params=params, timeout=10)
            text = r.text.strip()
            if text.startswith("STATUS_OK"):
                code = text.split(":")[1]
                m    = re.search(r'\b\d{4,8}\b', code)
                if m:
                    log(f"OTP received: {m.group(0)}", "success")
                    return m.group(0)
            elif text == "STATUS_CANCEL":
                return None
        except Exception as e:
            log(f"[SMSBower] OTP poll error: {e}", "warning")

        check_cnt += 1
        time.sleep(2)

    log("[SMSBower] OTP timeout", "failure")
    return None


# ==================== HEROSMS ====================
def _purchase_phone_herosms(attempt=1, max_attempts=9):
    try:
        params = {
            "api_key": HEROSMS_API_KEY,
            "action":  "getNumber",
            "service": HEROSMS_SERVICE,
            "country": HEROSMS_COUNTRY,
        }
        r    = httpx.get(HEROSMS_API_URL, params=params, timeout=15)
        text = r.text.strip()
        if text.startswith("ACCESS_NUMBER"):
            parts    = text.split(":")
            order_id = parts[1]
            phone    = parts[2]
            if not phone.startswith("+"):
                phone = f"+{phone}"
            return order_id, phone, None
        else:
            log(f"[HeroSMS] Response: {text}", "warning")
            if attempt < max_attempts:
                time.sleep(2)
                return _purchase_phone_herosms(attempt + 1, max_attempts)
            log("[HeroSMS] Failed to purchase number", "failure")
            return None, None, None
    except Exception as e:
        log(f"[HeroSMS] Purchase error: {e}", "failure")
        if attempt < max_attempts:
            return _purchase_phone_herosms(attempt + 1, max_attempts)
        return None, None, None


def _manage_order_herosms(order_id, action="finish"):
    # HeroSMS uses the sms-activate-compatible API
    # 1 = received sms (finish), 6 = confirm (finish), 8 = cancel
    status_map = {"finish": "6", "cancel": "8", "ban": "8"}
    try:
        params = {
            "api_key": HEROSMS_API_KEY,
            "action":  "setStatus",
            "id":      order_id,
            "status":  status_map.get(action, "8"),
        }
        httpx.get(HEROSMS_API_URL, params=params, timeout=10)
    except Exception as e:
        log(f"[HeroSMS] Manage order error: {e}", "warning")


def _fetch_otp_herosms(order_id, timeout=180):
    start     = time.time()
    check_cnt = 0

    while time.time() - start < timeout:
        try:
            params = {
                "api_key": HEROSMS_API_KEY,
                "action":  "getStatus",
                "id":      order_id,
            }
            r    = httpx.get(HEROSMS_API_URL, params=params, timeout=10)
            text = r.text.strip()
            if text.startswith("STATUS_OK"):
                code = text.split(":")[1]
                m    = re.search(r'\b\d{4,8}\b', code)
                if m:
                    log(f"OTP received: {m.group(0)}", "success")
                    return m.group(0)
            elif text in ("STATUS_CANCEL", "STATUS_TIMEOUT"):
                log(f"[HeroSMS] Order cancelled/timed out", "failure")
                return None
            # STATUS_WAIT_CODE means still waiting — keep polling
        except Exception as e:
            log(f"[HeroSMS] OTP poll error: {e}", "warning")

        check_cnt += 1
        time.sleep(2)

    log("[HeroSMS] OTP timeout", "failure")
    return None


# ==================== TIGERSMS ====================
# Uses the sms-activate compatible API: api.tiger-sms.com/stubs/handler_api.php
# Same query-string protocol as SMSBower / HeroSMS

def _purchase_phone_tigersms(attempt=1, max_attempts=9):
    try:
        params = {
            "api_key":  TIGERSMS_API_KEY,
            "action":   "getNumber",
            "service":  TIGERSMS_SERVICE,
            "country":  TIGERSMS_COUNTRY,
            "maxprice": "1"
            
        }
        r    = httpx.get(TIGERSMS_API_URL, params=params, timeout=15)
        text = r.text.strip()
        if text.startswith("ACCESS_NUMBER"):
            parts    = text.split(":")
            order_id = parts[1]
            phone    = parts[2]
            if not phone.startswith("+"):
                phone = f"+{phone}"
            return order_id, phone, None
        else:
            log(f"[TigerSMS] Purchase failed: {text[:100]}", "warning")
            if attempt < max_attempts:
                time.sleep(2)
                return _purchase_phone_tigersms(attempt + 1, max_attempts)
            log("[TigerSMS] Failed to purchase number", "failure")
            return None, None, None
    except Exception as e:
        log(f"[TigerSMS] Purchase error: {e}", "failure")
        if attempt < max_attempts:
            return _purchase_phone_tigersms(attempt + 1, max_attempts)
        return None, None, None


def _manage_order_tigersms(order_id, action="finish"):
    # 6=finish, 8=cancel/ban (sms-activate protocol)
    status_map = {"finish": "6", "cancel": "8", "ban": "8"}
    try:
        params = {
            "api_key": TIGERSMS_API_KEY,
            "action":  "setStatus",
            "id":      order_id,
            "status":  status_map.get(action, "8"),
        }
        httpx.get(TIGERSMS_API_URL, params=params, timeout=10)
    except Exception as e:
        log(f"[TigerSMS] Manage order error: {e}", "warning")


def _fetch_otp_tigersms(order_id, timeout=180):
    start     = time.time()
    check_cnt = 0

    while time.time() - start < timeout:
        try:
            params = {
                "api_key": TIGERSMS_API_KEY,
                "action":  "getStatus",
                "id":      order_id,
            }
            r    = httpx.get(TIGERSMS_API_URL, params=params, timeout=10)
            text = r.text.strip()
            if text.startswith("STATUS_OK"):
                code = text.split(":")[1]
                m    = re.search(r"\d{4,8}", code)
                if m:
                    log(f"OTP received: {m.group(0)}", "success")
                    return m.group(0)
            elif text in ("STATUS_CANCEL", "STATUS_TIMEOUT"):
                log("[TigerSMS] Order cancelled/timed out", "failure")
                return None
            # STATUS_WAIT_CODE — keep polling
        except Exception as e:
            log(f"[TigerSMS] OTP poll error: {e}", "warning")

        check_cnt += 1
        time.sleep(2)

    log("[TigerSMS] OTP timeout", "failure")
    return None


# ==================== UNIFIED PHONE SERVICE ====================
def _purchase_phone(attempt=1, max_attempts=9):
    if PHONE_SERVICE == "smsbower":
        return _purchase_phone_smsbower(attempt, max_attempts)
    elif PHONE_SERVICE == "herosms":
        return _purchase_phone_herosms(attempt, max_attempts)
    elif PHONE_SERVICE == "tigersms":
        return _purchase_phone_tigersms(attempt, max_attempts)
    return _purchase_phone_5sim(attempt, max_attempts)


def _manage_order(order_id, _unused_session, action="finish"):
    if PHONE_SERVICE == "smsbower":
        _manage_order_smsbower(order_id, action)
    elif PHONE_SERVICE == "herosms":
        _manage_order_herosms(order_id, action)
    elif PHONE_SERVICE == "tigersms":
        _manage_order_tigersms(order_id, action)
    else:
        _manage_order_5sim(order_id, action)


def _fetch_otp(order_id, _unused_session, timeout=180):
    if PHONE_SERVICE == "smsbower":
        return _fetch_otp_smsbower(order_id, timeout)
    elif PHONE_SERVICE == "herosms":
        return _fetch_otp_herosms(order_id, timeout)
    elif PHONE_SERVICE == "tigersms":
        return _fetch_otp_tigersms(order_id, timeout)
    return _fetch_otp_5sim(order_id, timeout)


# ==================== DISCORD PHONE FLOW ====================
def _check_status(ctx: SessionContext, token: str) -> str:
    try:
        headers = ctx.get_headers(endpoint_type="api", include_auth=token,
                                  include_fingerprint=True,
                                  referer="https://discord.com/channels/@me")
        r = ctx.session.get("https://discord.com/api/v9/users/@me", headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("phone"):
                return "has_phone"
            if not data.get("verified"):
                return "unverified"
            return "phone_pending"
        if r.status_code == 401:
            return "invalid"
        return "unknown"
    except Exception as e:
        log(f"Status check error: {e}", "failure")
        return "error"


def _add_phone(ctx: SessionContext, token: str, phone: str, order_id: str = None, attempt: int = 1, max_attempts: int = 3) -> bool:
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    url     = "https://discord.com/api/v9/users/@me/phone"
    payload = {"phone": f"+{clean_phone}", "change_phone_reason": "user_action_required"}
    headers = ctx.get_headers(endpoint_type="api", include_auth=token,
                              include_fingerprint=True,
                              referer="https://discord.com/channels/@me")
    r = ctx.session.post(url, json=payload, headers=headers, timeout=15)

    if r.status_code in (200, 204):
        return True, phone, order_id

    if r.status_code in (400, 403):
        try:
            err = r.json()
        except Exception as e:
            log(f"Add phone response parse error: {e} — raw: {r.text[:200]}", "failure")
            return False, phone, order_id

        if err.get("code") == 50022:
            if order_id:
                _manage_order(order_id, None, "cancel")
            if attempt < max_attempts:
                new_order_id, new_phone, _ = _purchase_phone()
                if not new_order_id:
                    return False, phone, order_id
                return _add_phone(ctx, token, new_phone, new_order_id, attempt + 1, max_attempts)
            log("Invalid phone — max retries reached", "failure")
            return False, phone, order_id

        if "captcha_sitekey" in err:
            sitekey    = err.get("captcha_sitekey", HCAPTCHA_SITE_KEY)
            rqdata     = err.get("captcha_rqdata", "")
            rqtoken    = err.get("captcha_rqtoken", "")
            session_id = err.get("captcha_session_id", "")

            cap = _solve_captcha(ctx, sitekey, rqdata, rqtoken, session_id)
            if not cap:
                log("Captcha solve failed", "failure")
                return False, phone, order_id

            hdrs = ctx.get_headers(endpoint_type="api", include_auth=token,
                                   include_fingerprint=True,
                                   referer="https://discord.com/channels/@me")
            hdrs["X-Captcha-Key"] = cap
            if rqtoken:
                hdrs["X-Captcha-Rqtoken"]    = rqtoken
            if session_id:
                hdrs["X-Captcha-Session-Id"] = session_id

            r2 = ctx.session.post(url, json=payload, headers=hdrs, timeout=15)
            if r2.status_code in (200, 204):
                return True, phone, order_id

            if r2.status_code == 400:
                try:
                    e2 = r2.json()
                    if e2.get("code") == 50022:
                        if order_id:
                            _manage_order(order_id, None, "cancel")
                        if attempt < max_attempts:
                            new_order_id, new_phone, _ = _purchase_phone()
                            if not new_order_id:
                                return False, phone, order_id
                            return _add_phone(ctx, token, new_phone, new_order_id, attempt + 1, max_attempts)
                        log("Invalid phone — max retries reached", "failure")
                        return False, phone, order_id
                    if "captcha_sitekey" in e2:
                        sitekey2    = e2.get("captcha_sitekey", HCAPTCHA_SITE_KEY)
                        rqdata2     = e2.get("captcha_rqdata", "")
                        rqtoken2    = e2.get("captcha_rqtoken", "")
                        session_id2 = e2.get("captcha_session_id", "")
                        cap2 = _solve_captcha(ctx, sitekey2, rqdata2, rqtoken2, session_id2)
                        if not cap2:
                            log("Second captcha solve failed", "failure")
                            return False, phone, order_id
                        hdrs2 = ctx.get_headers(endpoint_type="api", include_auth=token,
                                                include_fingerprint=True,
                                                referer="https://discord.com/channels/@me")
                        hdrs2["X-Captcha-Key"] = cap2
                        if rqtoken2:
                            hdrs2["X-Captcha-Rqtoken"]    = rqtoken2
                        if session_id2:
                            hdrs2["X-Captcha-Session-Id"] = session_id2
                        r3 = ctx.session.post(url, json=payload, headers=hdrs2, timeout=15)
                        if r3.status_code in (200, 204):
                            return True, phone, order_id
                        log(f"Add phone failed after second captcha [{r3.status_code}] — {r3.text[:200]}", "failure")
                        return False, phone, order_id
                except Exception as e:
                    log(f"Add phone response parse error: {e}", "failure")

            log(f"Add phone failed after captcha [{r2.status_code}] — {r2.text[:200]}", "failure")
            return False, phone, order_id

        log(f"Add phone failed [{r.status_code}] — {err}", "failure")
        return False, phone, order_id

    log(f"Add phone failed [{r.status_code}]", "failure")
    return False, phone, order_id


def _verify_otp(ctx: SessionContext, token: str, phone: str, otp: str):
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    url     = "https://discord.com/api/v9/phone-verifications/verify"
    payload = {"code": otp, "phone": f"+{clean_phone}"}
    headers = ctx.get_headers(endpoint_type="api", include_auth=token,
                              include_fingerprint=True,
                              referer="https://discord.com/channels/@me")
    r = ctx.session.post(url, json=payload, headers=headers, timeout=15)
    if r.status_code == 200:
        return r.json().get("token")
    log(f"OTP verify failed [{r.status_code}]", "failure")
    return None


def _finalize(ctx: SessionContext, token: str, password: str, phone_token: str) -> bool:
    url     = "https://discord.com/api/v9/users/@me/phone"
    payload = {
        "phone_token":         phone_token,
        "password":            password,
        "change_phone_reason": "user_action_required"
    }
    headers = ctx.get_headers(endpoint_type="api", include_auth=token,
                              include_fingerprint=True,
                              referer="https://discord.com/channels/@me")
    r = ctx.session.post(url, json=payload, headers=headers, timeout=15)
    if r.status_code not in (200, 204):
        log(f"Finalize failed: HTTP {r.status_code}", "failure")
    return r.status_code in (200, 204)


# ==================== VERIFICATION PROCESS ====================
def verify_single_account(token_data, timezone):
    token    = token_data['token']
    password = token_data.get('password')
    email    = token_data.get('email', 'N/A')
    line_num = token_data.get('line_num', '?')

    if not password:
        if sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
            password = input(f"Enter password for {email}: ").strip()
        if not password:
            log("Password required for finalization", "failure")
            return False

    proxy = _get_proxy()
    ctx   = SessionContext(proxy=proxy)

    ctx.get_fingerprint()

    status = _check_status(ctx, token)
    if status in ("invalid", "error"):
        log(f"[{email}] Invalid token", "failure")
        return False
    if status == "has_phone":
        log(f"[{email}] Already verified — skipping", "success")
        return True

    order_id = None
    try:
        order_id, phone, _ = _purchase_phone()
        if not order_id:
            log(f"[{email}] Failed to purchase phone number", "failure")
            return False

        log(f"Email [{email}] | Phone [{phone}]", "info")

        success, phone, order_id = _add_phone(ctx, token, phone, order_id)
        if not success:
            if order_id:
                _manage_order(order_id, None, "cancel")
            log(f"[{email}] Failed to add phone to Discord", "failure")
            return False

        otp = _fetch_otp(order_id, None)
        if not otp:
            _manage_order(order_id, None, "ban")
            log(f"[{email}] OTP timeout", "failure")
            return False

        phone_token = _verify_otp(ctx, token, phone, otp)
        if not phone_token:
            _manage_order(order_id, None, "cancel")
            log(f"[{email}] OTP verification failed", "failure")
            return False

        if _finalize(ctx, token, password, phone_token):
            _manage_order(order_id, None, "finish")
            log(f"✅ SUCCESS! Email [{email}] | Phone [{phone}]", "success")
            try:
                out_dir = Path(__file__).resolve().parent / "output"
                out_dir.mkdir(exist_ok=True)
                with open(out_dir / "unlocked.txt", "a", encoding="utf-8") as uf:
                    uf.write(f"{email}:{password}:{token}:{phone}\n")
            except Exception:
                pass
            return True
        else:
            _manage_order(order_id, None, "cancel")
            log(f"[{email}] Finalization failed", "failure")
            return False

    except KeyboardInterrupt:
        if order_id:
            _manage_order(order_id, None, "cancel")
        return False
    except Exception as e:
        log(f"[{email}] Error: {e}", "failure")
        if order_id:
            _manage_order(order_id, None, "cancel")
        return False


def run_phone_verifier_task(tokens_list: list, threads: int = 5, event_callback = None, cancel_flag = None):
    successful = 0
    failed = 0
    total = len(tokens_list)
    lock = threading.Lock()

    def _worker(token_data):
        nonlocal successful, failed
        if cancel_flag and cancel_flag.is_set():
            return False
        email = token_data.get('email', 'N/A')
        token = token_data.get('token', '')
        if event_callback:
            try:
                event_callback("verifying_start", {
                    "email": email,
                    "token": token,
                    "completed": successful + failed,
                    "total": total
                })
            except Exception:
                pass

        result = verify_single_account(token_data, DISCORD_TIMEZONE)
        with lock:
            if result:
                successful += 1
            else:
                failed += 1
            cur_succ = successful
            cur_fail = failed

        if event_callback:
            try:
                event_callback("token_finished", {
                    "email": email,
                    "token": token,
                    "success": result,
                    "successful": cur_succ,
                    "failed": cur_fail,
                    "total": total
                })
            except Exception:
                pass
        return result

    thread_count = max(1, min(threads, total)) if total > 0 else 1
    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        futures = {executor.submit(_worker, td): td for td in tokens_list}
        for future in as_completed(futures):
            if cancel_flag and cancel_flag.is_set():
                break
            try:
                future.result()
            except Exception as e:
                td = futures[future]
                log(f"[{td.get('email', 'N/A')}] Thread error: {e}", "failure")
                with lock:
                    failed += 1

    return {
        "successful": successful,
        "failed": failed,
        "total": total
    }


# ==================== MAIN ====================
def main():
    print("Discord Phone Verification — Batch Processing")

    # ── Everything is driven by config.json ─────────────────────────────────
    global PHONE_SERVICE, DISCORD_TIMEZONE

    # Validate the service from config
    valid_services = ("5sim", "smsbower", "herosms", "tigersms")
    if PHONE_SERVICE not in valid_services:
        log(f"Invalid phone_service '{PHONE_SERVICE}' in config.json — must be one of {valid_services}", "failure")
        sys.exit(1)

    valid_solvers = ("onyx", "hcaptchasolver", "voidsolver")
    if CAPTCHA_SOLVER not in valid_solvers:
        log(f"Invalid captcha solver '{CAPTCHA_SOLVER}' in config.json — must be one of {valid_solvers}", "failure")
        sys.exit(1)

    # Print active config summary
    print("\n┌──────────────────────────────────────────┐")
    print(  "│           Config loded NEXORA            │")
    print(  "│              OWN NEXUVER                  │")
    print(  "├──────────────────────────────────────────┤")
    print(f"│  Phone Service : {PHONE_SERVICE:<24}│")
    print(f"│  Captcha Solver: {CAPTCHA_SOLVER:<24}│")
    print(f"│  Timezone      : {DISCORD_TIMEZONE:<24}│")
    print(f"│  Token File    : {CFG_TOKEN_FILE:<24}│")
    print(  "└──────────────────────────────────────────┘")

    # ── Load tokens from config-specified file ───────────────────────────────
    tokens_list = read_tokens_from_file(CFG_TOKEN_FILE)
    if not tokens_list:
        log(f"No tokens found in {CFG_TOKEN_FILE}", "failure")
        return
    log(f"Loaded {len(tokens_list)} token(s) from {CFG_TOKEN_FILE}", "success")

    # ── Only ask for thread count ────────────────────────────────────────────
    default_threads = min(CFG_THREADS, len(tokens_list))
    thread_count_input = input(f"\nEnter number of threads [default: {default_threads}, max: {len(tokens_list)}]: ").strip()
    try:
        thread_count = int(thread_count_input)
        if thread_count < 1:
            thread_count = 1
        if thread_count > len(tokens_list):
            thread_count = len(tokens_list)
    except ValueError:
        thread_count = default_threads

    log(f"Starting {len(tokens_list)} account(s) | {thread_count} thread(s) | service: {PHONE_SERVICE}", "info")

    successful = 0
    failed     = 0
    lock       = threading.Lock()

    def _worker(token_data):
        result = verify_single_account(token_data, DISCORD_TIMEZONE)
        with lock:
            nonlocal successful, failed
            if result:
                successful += 1
            else:
                failed += 1
        return result

    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        futures = {executor.submit(_worker, td): td for td in tokens_list}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                td = futures[future]
                log(f"[{td.get('email', 'N/A')}] Thread error: {e}", "failure")
                with lock:
                    failed += 1

    console.success(f"Successful: {successful}")
    console.failed(f"Failed: {failed}")
    console.info(f"Total: {len(tokens_list)}")


if __name__ == "__main__":
    main()