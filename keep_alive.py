import asyncio
import httpx
import os
from config import RENDER_EXTERNAL_URL, PORT, KEEP_ALIVE_INTERVAL

async def run_keep_alive_loop():
    """Background task to self-ping and keep the Render web service awake 24/7."""
    # Determine URL to ping
    target_url = RENDER_EXTERNAL_URL
    if not target_url:
        target_url = f"http://127.0.0.1:{PORT}/healthz"

    print(f"[KeepAlive] Keep-alive worker started. Target: {target_url} (Every {KEEP_ALIVE_INTERVAL}s)")

    await asyncio.sleep(15)  # Wait for web server and bot to initialize

    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            try:
                r = await client.get(target_url)
                if r.status_code == 200:
                    # Successfully pinged
                    pass
                else:
                    print(f"[KeepAlive] Ping warning: status {r.status_code}")
            except Exception as e:
                # Log non-fatal error
                pass
            await asyncio.sleep(KEEP_ALIVE_INTERVAL)

