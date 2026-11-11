import time
import os
from aiohttp import web
from config import (
    PORT,
    VALID_TXT,
    LOCKED_TXT,
    UNVERIFIED_TXT,
    INVALID_TXT,
    UNLOCKED_TXT
)
from core.gen_runner import gen_runner
from core.unlock_runner import unlock_runner
from core.pipeline_runner import pipeline_runner

START_TIME = time.time()
BOT_INSTANCE = None


def set_bot_instance(bot):
    global BOT_INSTANCE
    BOT_INSTANCE = bot


def count_lines(filepath):
    if not filepath.exists():
        return 0
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


async def handle_root(request):
    uptime = int(time.time() - START_TIME)
    bot_name = str(BOT_INSTANCE.user) if (BOT_INSTANCE and BOT_INSTANCE.user) else "Starting..."
    bot_id = str(BOT_INSTANCE.user.id) if (BOT_INSTANCE and BOT_INSTANCE.user) else "N/A"

    data = {
        "status": "online",
        "service": "NEXUVER 24/7 Cloud Suite",
        "uptime_seconds": uptime,
        "bot_tag": bot_name,
        "bot_id": bot_id,
        "active_jobs": {
            "generator": gen_runner.is_running,
            "unlocker": unlock_runner.is_running,
            "pipeline": pipeline_runner.is_running
        },
        "token_counts": {
            "valid": count_lines(VALID_TXT),
            "locked": count_lines(LOCKED_TXT),
            "unlocked": count_lines(UNLOCKED_TXT),
            "unverified": count_lines(UNVERIFIED_TXT),
            "invalid": count_lines(INVALID_TXT)
        }
    }
    return web.json_response(data)


async def handle_health(request):
    return web.Response(text="OK", status=200)


async def handle_stats(request):
    stats = {
        "uptime_seconds": int(time.time() - START_TIME),
        "generator_stats": gen_runner.get_stats(),
        "unlocker_stats": unlock_runner.get_stats(),
        "pipeline_stats": pipeline_runner.get_stats(),
        "tokens": {
            "valid": count_lines(VALID_TXT),
            "locked": count_lines(LOCKED_TXT),
            "unlocked": count_lines(UNLOCKED_TXT),
            "unverified": count_lines(UNVERIFIED_TXT),
            "invalid": count_lines(INVALID_TXT)
        }
    }
    return web.json_response(stats)


def make_app():
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/healthz", handle_health)
    app.router.add_get("/stats", handle_stats)
    return app


async def start_web_server(port: int = PORT):
    app = make_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"[WebServer] HTTP keep-alive server listening on 0.0.0.0:{port}")
    return runner

