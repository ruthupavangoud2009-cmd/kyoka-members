import asyncio
import re
import base64
import json
import uuid
import httpx
from typing import List, Dict, Any, Optional, Callable

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"

def clean_invite_code(raw_invite: str) -> str:
    """Extract the clean invite code from full URLs or raw codes."""
    raw = raw_invite.strip()
    # Match discord.gg/CODE or discord.com/invite/CODE
    m = re.search(r"(?:discord\.gg/|discord\.com/invite/|discordapp\.com/invite/)?([a-zA-Z0-9-]+)", raw)
    if m:
        return m.group(1)
    return raw


def make_sprops():
    props = {
        "os": "Windows",
        "browser": "Chrome",
        "device": "",
        "system_locale": "en-US",
        "browser_user_agent": UA,
        "browser_version": "132.0.0.0",
        "os_version": "10",
        "referrer": "",
        "referring_domain": "",
        "referrer_current": "",
        "referring_domain_current": "",
        "release_channel": "stable",
        "client_build_number": 519006,
        "client_event_source": None
    }
    return base64.b64encode(json.dumps(props).encode()).decode()


async def join_server_task(
    invite_code: str,
    tokens: List[str],
    delay: float = 1.2,
    callback: Optional[Callable] = None
) -> Dict[str, Any]:
    code = clean_invite_code(invite_code)
    sprops = make_sprops()

    results = {
        "invite": code,
        "server_name": "Unknown",
        "total": len(tokens),
        "joined": 0,
        "already_in": 0,
        "captcha": 0,
        "invalid": 0,
        "failed": 0,
        "successful_tokens": [],
    }

    async with httpx.AsyncClient(timeout=12) as client:
        # 1. Fetch server info from invite
        try:
            inv_res = await client.get(f"https://discord.com/api/v9/invites/{code}?with_counts=true")
            if inv_res.status_code == 200:
                inv_data = inv_res.json()
                guild = inv_data.get("guild", {})
                results["server_name"] = guild.get("name", "Unknown Server")
            else:
                results["server_name"] = f"Invalid/Expired ({inv_res.status_code})"
                return results
        except Exception as e:
            results["server_name"] = f"Lookup Error: {e}"
            return results

        # 2. Iterate through tokens
        for idx, token in enumerate(tokens, 1):
            t_clean = token.strip()
            if ":" in t_clean:
                parts = t_clean.split(":")
                t_clean = parts[2] if len(parts) >= 3 else parts[0]

            headers = {
                "Authorization": t_clean,
                "Content-Type": "application/json",
                "User-Agent": UA,
                "X-Super-Properties": sprops,
            }

            status = "failed"
            try:
                r = await client.post(
                    f"https://discord.com/api/v9/invites/{code}",
                    headers=headers,
                    json={},
                )

                if r.status_code in (200, 204):
                    results["joined"] += 1
                    results["successful_tokens"].append(t_clean)
                    status = "joined"
                elif r.status_code == 400:
                    d = r.json() or {}
                    if "captcha_sitekey" in d:
                        results["captcha"] += 1
                        status = "captcha"
                    else:
                        results["failed"] += 1
                        status = "failed"
                elif r.status_code == 401:
                    results["invalid"] += 1
                    status = "invalid"
                elif r.status_code == 403:
                    d = r.json() or {}
                    if d.get("code") == 40007:  # Banned
                        results["failed"] += 1
                        status = "banned"
                    else:
                        results["failed"] += 1
                        status = "locked"
                elif r.status_code == 429:
                    results["failed"] += 1
                    status = "rate_limit"
                else:
                    results["failed"] += 1
                    status = f"http_{r.status_code}"

            except Exception as ex:
                results["failed"] += 1
                status = f"error_{ex}"

            if callback:
                try:
                    callback(idx, len(tokens), status, results)
                except Exception:
                    pass

            if idx < len(tokens):
                await asyncio.sleep(delay)

    return results

