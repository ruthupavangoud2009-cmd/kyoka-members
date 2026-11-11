"""
VoidSolver API Integration Module
Uses the correct VoidSolver API endpoints: /createtask and /gettaskresult
"""

import requests
import time
import random
import logger

class VoidSolverBasic:
    """
    VoidSolver client using the correct API endpoints.
    POST /createtask and GET /gettaskresult
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize VoidSolver client.
        
        Args:
            api_key: Your VoidSolver API key (optional, has default)
        """
        self.api_key = api_key or "void_sk_itsr_mi56tqgm_v1svddzxl"
        self.server_url = "https://api.voidsolver.tech"
    
    def solve_hcaptcha(self, 
                       url: str, 
                       sitekey: str,
                       rqdata: str = "",
                       user_agent: str = "",
                       proxy: str = None,
                       timeout: int = 300,
                       poll_interval: int = 1,
                       pow_type: str = "",
                       token: str = ""):
        """
        Solve an hCaptcha challenge using VoidSolver API.
        
        Args:
            url: The URL where the captcha is located
            sitekey: The hCaptcha sitekey
            rqdata: Optional request data
            user_agent: User agent string to use
            proxy: Proxy in format "host:port" or "user:pass@host:port"
            timeout: Maximum time to wait for solution (seconds)
            poll_interval: Seconds between status checks
            token: Identifier for logging purposes
            
        Returns:
            tuple: (captcha_token, cookies) or (None, None) if failed
        """
        # Prepare request payload according to VoidSolver docs
        payload = {
            "site_key": sitekey,
            "site_url": url,
        }
        
        if pow_type:
            payload["pow_type"] = pow_type
        if rqdata:
            payload["rqdata"] = rqdata

        if proxy:
            payload["proxy"] = proxy        
        # Setup session
        sess = requests.Session()
        sess.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })
        
        if user_agent:
            sess.headers.update({"User-Agent": user_agent})
        
        # Create task
        create_endpoint = f"{self.server_url.rstrip('/')}/createtask"
        logger.captcha(token, "Solving captcha...")
        
        try:
            resp = sess.post(create_endpoint, json=payload, timeout=30)
        except Exception as e:
            logger.error(token, "Failed to create task", str(e))
            return None, None
        
        if resp.status_code != 200:
            logger.error(token, "Failed to create task", f"HTTP {resp.status_code}")
            try:
                error_data = resp.json()
                error_msg = error_data.get("error") or error_data.get("message") or resp.text[:200]
                logger.error(token, "API Error", error_msg)
            except:
                logger.error(token, "Response", resp.text[:200])
            return None, None
        
        # Check if response is empty
        if not resp.text or resp.text.strip() == "":
            logger.error(token, "Failed to parse response", "Empty response body")
            return None, None
        
        try:
            data = resp.json()
        except Exception as e:
            logger.error(token, "Failed to parse response", str(e))
            return None, None
        
        # Get task ID
        taskid = data.get("taskId") or data.get("taskid") or data.get("task_id")
        if not taskid:
            error_msg = data.get("error") or data.get("message") or "No task ID"
            logger.error(token, "Failed to create task", error_msg)
            return None, None
        
        # Poll for result
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                poll_endpoint = f"{self.server_url.rstrip('/')}/gettaskresult"
                poll_resp = sess.get(poll_endpoint, params={"taskid": taskid}, timeout=30)
            except Exception as e:
                time.sleep(poll_interval + random.uniform(0, 0.5))
                continue
            
            if poll_resp.status_code != 200:
                time.sleep(poll_interval + random.uniform(0, 0.5))
                continue
            
            # Check if response is empty
            if not poll_resp.text or poll_resp.text.strip() == "":
                time.sleep(poll_interval + random.uniform(0, 0.5))
                continue
            
            try:
                data = poll_resp.json()
            except Exception:
                time.sleep(poll_interval + random.uniform(0, 0.5))
                continue
            
            status = (data.get("status") or data.get("state") or "").lower()
            # VoidSolver returns "token" field according to docs
            captcha_token = (data.get("token") or data.get("solvedToken") or 
                           data.get("uuid") or data.get("value") or data.get("solution"))
            cookies = data.get("cookies", {}) or data.get("cookie", {})
            
            if status in ("solved", "success", "ready", "completed"):
                if captcha_token:
                    logger.success(token, f"Captcha solved: {captcha_token[:20]}...")
                    return captcha_token, cookies
                else:
                    logger.error(token, "No token in response", str(data))
                    return None, None
            
            if status in ("failed", "error"):
                error_msg = data.get("error") or data.get("message") or "Unknown error"
                logger.error(token, "Failed to solve", error_msg)
                return None, None
            
            # Still processing (status: "processing", "pending", etc.)
            time.sleep(poll_interval + random.uniform(0, 0.5))
        
        logger.error(token, "Failed to solve", "Timeout")
        return None, None


