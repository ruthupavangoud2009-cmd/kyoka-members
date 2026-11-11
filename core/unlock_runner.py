import sys
import os
import asyncio
import threading
import time
import httpx
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List

from config import UNLOCK_DIR

if str(UNLOCK_DIR) not in sys.path:
    sys.path.insert(0, str(UNLOCK_DIR))

try:
    import pv as unlock_module
except Exception as e:
    unlock_module = None
    print(f"[UnlockRunner] Warning: Could not import unlock module: {e}")


class UnlockRunner:
    def __init__(self):
        self.is_running = False
        self.total = 0
        self.successful = 0
        self.failed = 0
        self.start_time: Optional[float] = None
        self._cancel_flag = threading.Event()
        self._callback: Optional[Callable] = None

    def get_stats(self) -> Dict[str, Any]:
        elapsed = time.time() - self.start_time if (self.is_running and self.start_time) else 0
        return {
            "is_running": self.is_running,
            "total": self.total,
            "successful": self.successful,
            "failed": self.failed,
            "elapsed_seconds": int(elapsed)
        }

    def _event_handler(self, event_type: str, data: dict):
        if event_type == "token_finished":
            self.successful = data.get("successful", self.successful)
            self.failed = data.get("failed", self.failed)

        if self._callback:
            try:
                res = self._callback(event_type, data)
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
            except Exception as e:
                print(f"[UnlockRunner] Callback error: {e}")

    async def verify_tokens(
        self,
        token_lines: List[str],
        threads: int = 5,
        callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        if self.is_running:
            raise RuntimeError("Unlocker is already running!")

        if unlock_module is None:
            raise RuntimeError("Unlocker engine is not loaded.")

        parsed_tokens = unlock_module.parse_token_lines(token_lines)
        if not parsed_tokens:
            raise ValueError("No valid tokens found in the input list.")

        self.is_running = True
        self.total = len(parsed_tokens)
        self.successful = 0
        self.failed = 0
        self.start_time = time.time()
        self._cancel_flag.clear()
        self._callback = callback

        try:
            # Run in thread pool executor since pv.py uses blocking network requests
            results = await asyncio.to_thread(
                unlock_module.run_phone_verifier_task,
                tokens_list=parsed_tokens,
                threads=threads,
                event_callback=self._event_handler,
                cancel_flag=self._cancel_flag
            )
            return results
        finally:
            self.is_running = False

    def stop(self):
        if self.is_running:
            self._cancel_flag.set()
            self.is_running = False

    @staticmethod
    def get_balances() -> Dict[str, str]:
        """Check balances across configured SMS and Captcha providers."""
        balances = {}
        if unlock_module is None:
            return {"error": "Unlock module not loaded"}

        cfg = unlock_module.CFG
        # 5sim
        fivesim_key = cfg.get("5sim", {}).get("api_key", unlock_module.FIVESIM_API_KEY)
        if fivesim_key:
            try:
                r = httpx.get("https://5sim.net/v1/user/profile",
                              headers={"Authorization": f"Bearer {fivesim_key}", "Accept": "application/json"},
                              timeout=7)
                if r.status_code == 200:
                    data = r.json()
                    balances["5sim"] = f"{data.get('balance', 'N/A')} RUB (Rating: {data.get('rating', 'N/A')})"
                else:
                    balances["5sim"] = f"HTTP {r.status_code}"
            except Exception as e:
                balances["5sim"] = f"Error: {e}"

        # SMSBower
        bower_key = cfg.get("smsbower", {}).get("api_key", unlock_module.SMSBOWER_API_KEY)
        if bower_key:
            try:
                url = cfg.get("smsbower", {}).get("api_url", "https://smsbower.page/stubs/handler_api.php")
                r = httpx.get(url, params={"api_key": bower_key, "action": "getBalance"}, timeout=7)
                balances["SMSBower"] = r.text.strip()
            except Exception as e:
                balances["SMSBower"] = f"Error: {e}"

        # HeroSMS
        hero_key = cfg.get("herosms", {}).get("api_key", unlock_module.HEROSMS_API_KEY)
        if hero_key:
            try:
                url = cfg.get("herosms", {}).get("api_url", "https://hero.sms-activate.io/stubs/handler_api.php")
                r = httpx.get(url, params={"api_key": hero_key, "action": "getBalance"}, timeout=7)
                balances["HeroSMS"] = r.text.strip()
            except Exception as e:
                balances["HeroSMS"] = f"Error: {e}"

        # TigerSMS
        tiger_key = cfg.get("tigersms", {}).get("api_key", unlock_module.TIGERSMS_API_KEY)
        if tiger_key:
            try:
                url = cfg.get("tigersms", {}).get("api_url", "https://api.tiger-sms.com/stubs/handler_api.php")
                r = httpx.get(url, params={"api_key": tiger_key, "action": "getBalance"}, timeout=7)
                balances["TigerSMS"] = r.text.strip()
            except Exception as e:
                balances["TigerSMS"] = f"Error: {e}"

        return balances


# Global singleton instance
unlock_runner = UnlockRunner()

