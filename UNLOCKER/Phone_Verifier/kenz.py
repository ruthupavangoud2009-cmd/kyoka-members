"""
hCaptchaSolver API Integration Module
https://hcaptchasolver.com
Endpoints: /api/createTask, /api/getTaskResult, /api/reportTaskResult, /api/getBalance
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
    """Read hcaptchasolver_api_key from config.json at import time."""
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("captcha", {}).get("hcaptchasolver_api_key", "")
    except Exception:
        return ""

API_KEY = _load_api_key()


class Solver:
    """
    hCaptchaSolver client for hcaptchasolver.com.
    Supports: PopularCaptchaTaskProxyless, PopularCaptchaTask (with proxy).
    Optional fields: rqdata, pow_type, user_agent, is_invisible.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or API_KEY
        self.server_url = "https://hcaptchasolver.com"
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def _post(self, endpoint: str, payload: dict, token: str = ""):
        """Internal helper: POST to an endpoint, return parsed JSON or None."""
        url = f"{self.server_url}/api/{endpoint}"
        try:
            resp = requests.post(url, json=payload, headers=self.headers, timeout=30, verify=False)
        except requests.exceptions.SSLError:
            try:
                resp = requests.post(url, json=payload, headers=self.headers, timeout=30)
            except Exception as e:
                logger.error(token, f"[{endpoint}] Connection error (SSL retry)", str(e))
                return None
        except Exception as e:
            logger.error(token, f"[{endpoint}] Connection error", str(e))
            return None

        if resp.status_code != 200:
            logger.error(token, f"[{endpoint}] HTTP {resp.status_code}", resp.text[:500])
            return None

        if not resp.text or resp.text.strip() == "":
            logger.error(token, f"[{endpoint}] Empty response body", "")
            return None

        try:
            parsed = resp.json()
            # Always surface API-level errors with full detail
            if parsed.get("errorId", 0) != 0:
                err = parsed.get("errorDescription") or parsed.get("message") or "no description"
                logger.error(token, f"[{endpoint}] API error | errorId={parsed['errorId']} | {err}", "")
            return parsed
        except Exception as e:
            logger.error(token, f"[{endpoint}] JSON parse error", f"{e} | raw: {resp.text[:300]}")
            return None

    def get_balance(self):
        """
        Fetch account balance.
        POST /api/getBalance

        Returns:
            float: Current balance, or None if failed.
        """
        data = self._post("getBalance", {"clientKey": self.api_key}, token="getBalance")
        if data is None:
            return None
        if data.get("errorId", 0) != 0:
            return None
        balance = data.get("balance")
        logger.info("", f"Balance: ${balance}")
        return balance

    def report_task_result(self, task_id: str, correct: bool, token: str = ""):
        """
        Report whether a solved captcha was accepted or rejected.
        POST /api/reportTaskResult

        Args:
            task_id: The taskId from createTask.
            correct: True if the token worked, False if it was rejected.
            token:   Log label for this request (optional).

        Returns:
            bool: True if report was accepted, False otherwise.
        """
        payload = {
            "clientKey": self.api_key,
            "taskId": task_id,
            "result": "correct" if correct else "incorrect"
        }
        data = self._post("reportTaskResult", payload, token=token)
        if data is None:
            return False
        if data.get("errorId", 0) != 0:
            return False
        logger.info(token, f"Reported task {task_id} as {'correct' if correct else 'incorrect'}")
        return True

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
                       is_invisible: bool = False):
        """
        Solve an hCaptcha challenge.
        POST /api/createTask  ->  POST /api/getTaskResult (polled)

        Args:
            url:           Page URL where the hCaptcha is embedded.
            sitekey:       hCaptcha sitekey for that page.
            rqdata:        Enterprise rqdata from hCaptcha (optional).
            user_agent:    Custom UA for the solver worker (optional).
            proxy:         "http://user:pass@host:port" — omit for proxyless (optional).
            timeout:       Max seconds to wait for a solution (default 300).
            poll_interval: Seconds between polling attempts (default 3).
            pow_type:      Proof-of-work type: "hsw" or "hsl" (optional).
            token:         Log label for this request (optional).
            is_invisible:  True for invisible hCaptcha variant (optional).

        Returns:
            tuple: (captcha_token: str, cookies: dict) on success,
                   (None, None) on failure.
        """
        # Build task object
        task = {
            "type": "PopularCaptchaTask" if proxy else "PopularCaptchaTaskProxyless",
            "websiteURL": url,
            "websiteKey": sitekey,
        }

        # Append optional fields only when provided
        if proxy:
            task["proxy"] = proxy
        if rqdata:
            task["rqdata"] = rqdata
        if pow_type:
            task["pow_type"] = pow_type
        if user_agent:
            task["user_agent"] = user_agent
        if is_invisible:
            task["is_invisible"] = True

        payload = {
            "clientKey": self.api_key,
            "task": task
        }

        logger.captcha(token, "Solving captcha...")

        # Step 1: Create task
        data = self._post("createTask", payload, token=token)
        if data is None:
            return None, None

        error_id = data.get("errorId", 0)
        taskid = data.get("taskId")

        if error_id != 0 or not taskid:
            error_msg = data.get("errorDescription") or data.get("message") or "No taskId returned"
            logger.error(token, "createTask failed", f"{error_msg} | full: {data}")
            return None, None

        logger.info(token, f"Task created: {taskid}")

        # Step 2: Poll for result
        start_time = time.time()
        max_attempts = int(timeout / poll_interval)

        for _ in range(max_attempts):
            if time.time() - start_time >= timeout:
                break

            time.sleep(poll_interval + random.uniform(0, 0.5))

            poll_payload = {
                "clientKey": self.api_key,
                "taskId": taskid
            }
            data = self._post("getTaskResult", poll_payload, token=token)
            if data is None:
                continue

            status = (data.get("status") or "").lower()
            error_id = data.get("errorId", 0)

            if error_id != 0:
                return None, None

            if status == "ready":
                solution = data.get("solution", {})
                captcha_token = solution.get("gRecaptchaResponse") or solution.get("token")
                cookies = solution.get("cookies", {})

                if captcha_token:
                    logger.success(token, f"Captcha solved: {captcha_token[:20]}...")
                    return captcha_token, cookies
                else:
                    logger.error(token, "No token in solution", str(data))
                    return None, None

            # status == "processing" -> keep polling

        logger.error(token, "Solve failed", "Timeout")
        return None, None