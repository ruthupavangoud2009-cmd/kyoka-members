"""
OnyxSolver API Integration Module
Uses the correct OnyxSolver API endpoints: /createtask and /gettaskresult
"""

import json
import requests
import time
import random
import logger
import warnings
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings when verify=False is used
warnings.filterwarnings('ignore', category=InsecureRequestWarning)


def _load_api_key() -> str:
    """Read onyx_api_key from config.json at import time."""
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("captcha", {}).get("onyx_api_key", "")
    except Exception:
        return ""

API_KEY = _load_api_key()


class Solver:
    """
    OnyxSolver client using the correct API endpoints.
    POST /createtask and GET /gettaskresult
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize OnyxSolver client.
        
        Args:
            api_key: Your OnyxSolver API key (loaded from config.json by default)
        """
        self.api_key = api_key or API_KEY
        self.server_url = "https://onyxsolver.io"
    
    def solve_hcaptcha(self, 
                       url: str, 
                       sitekey: str,
                       rqdata: str = "",
                       user_agent: str = "",
                       proxy: str = None,
                       timeout: int = 300,
                       poll_interval: int = 3,
                       pow_type: str = "",
                       token: str = "",
                       devid: str = None):
        """
        Solve an hCaptcha challenge using OnyxSolver API.
        
        Args:
            url:           The URL where the captcha is located.
            sitekey:       The hCaptcha sitekey.
            rqdata:        Optional request data.
            user_agent:    User agent string to use.
            proxy:         Proxy in format "user:pass@host:port".
            timeout:       Maximum time to wait for solution (seconds).
            poll_interval: Seconds between status checks.
            token:         Identifier for logging purposes.
            devid:         Referral code for attribution.
            
        Returns:
            tuple: (captcha_token, cookies) or (None, None) if failed.
        """
        # Prepare request payload
        task = {
            "type": "PopularCaptchaTask" if proxy else "PopularCaptchaTaskProxyless",
            "websiteURL": url,
            "websiteKey": sitekey
        }
        
        if rqdata:
            task["rqdata"] = rqdata
        if proxy:
            task["proxy"] = proxy
        if devid:
            task["devid"] = devid

        payload = {
            "clientKey": self.api_key,
            "task": task
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        # ── Step 1: Create task ──────────────────────────────────────────────
        create_endpoint = f"{self.server_url.rstrip('/')}/api/createTask"
        logger.captcha(token, "Solving captcha...")
        
        try:
            resp = requests.post(create_endpoint, json=payload, headers=headers, timeout=30, verify=False)
        except requests.exceptions.SSLError:
            try:
                resp = requests.post(create_endpoint, json=payload, headers=headers, timeout=30)
            except Exception as e:
                logger.error(token, "Failed to create task", str(e))
                return None, None
        except Exception as e:
            logger.error(token, "Failed to create task", str(e))
            return None, None
        
        if resp.status_code != 200:
            logger.error(token, "Failed to create task", f"HTTP {resp.status_code}")
            try:
                error_data = resp.json()
                error_msg = error_data.get("errorDescription") or error_data.get("message") or resp.text[:200]
                logger.error(token, "API Error", error_msg)
            except Exception:
                logger.error(token, "Response", resp.text[:200])
            return None, None
        
        if not resp.text or resp.text.strip() == "":
            logger.error(token, "Failed to parse response", "Empty response body")
            return None, None
        
        try:
            data = resp.json()
        except Exception as e:
            logger.error(token, "Failed to parse response", str(e))
            return None, None
        
        taskid  = data.get("taskId")
        error_id = data.get("errorId", 0)
        
        if error_id != 0 or not taskid:
            error_msg = data.get("errorDescription") or data.get("message") or "No task ID"
            logger.error(token, "Failed to create task", error_msg)
            return None, None
        
        # ── Step 2: Poll for result ──────────────────────────────────────────
        start_time   = time.time()
        max_attempts = int(timeout / poll_interval)
        poll_endpoint = f"{self.server_url.rstrip('/')}/api/getTaskResult"
        
        for _ in range(max_attempts):
            if time.time() - start_time >= timeout:
                break
                
            time.sleep(poll_interval + random.uniform(0, 0.5))
            
            try:
                poll_payload = {
                    "clientKey": self.api_key,
                    "taskId": taskid
                }
                poll_resp = requests.post(poll_endpoint, json=poll_payload, headers=headers, timeout=30, verify=False)
            except Exception:
                continue
            
            if poll_resp.status_code != 200:
                continue
            
            if not poll_resp.text or poll_resp.text.strip() == "":
                continue
            
            try:
                data = poll_resp.json()
            except Exception:
                continue
            
            status   = (data.get("status") or "").lower()
            error_id = data.get("errorId", 0)
            
            if status == "ready":
                solution      = data.get("solution", {})
                captcha_token = solution.get("gRecaptchaResponse") or solution.get("token")
                cookies       = solution.get("cookies", {})
                
                if captcha_token:
                    logger.success(token, f"Captcha solved: {captcha_token[:20]}...")
                    return captcha_token, cookies
                else:
                    logger.error(token, "No token in response", str(data))
                    return None, None
            
            if error_id != 0:
                error_msg = data.get("errorDescription") or "Unknown error"
                logger.error(token, "Failed to solve", error_msg)
                return None, None
            
            # status == "processing" — keep polling

        logger.error(token, "Failed to solve", "Timeout")
        return None, None