import sys
import os
import asyncio
import time
from pathlib import Path
from typing import Optional, Callable, Dict, Any

from config import GEN_DIR

# Add GEN_DIR to sys.path so its internal modules resolve properly
if str(GEN_DIR) not in sys.path:
    sys.path.insert(0, str(GEN_DIR))

try:
    import main as gen_module
except Exception as e:
    gen_module = None
    print(f"[GenRunner] Warning: Could not import gen main module: {e}")


class GeneratorRunner:
    def __init__(self):
        self.is_running = False
        self.target = 0
        self.created = 0
        self.valid = 0
        self.locked = 0
        self.invalid = 0
        self.unverified = 0
        self.start_time: Optional[float] = None
        self.current_task: Optional[asyncio.Task] = None
        self._callback: Optional[Callable] = None

    def get_stats(self) -> Dict[str, Any]:
        elapsed = time.time() - self.start_time if (self.is_running and self.start_time) else 0
        return {
            "is_running": self.is_running,
            "target": self.target,
            "created": self.created,
            "valid": self.valid,
            "locked": self.locked,
            "invalid": self.invalid,
            "unverified": self.unverified,
            "elapsed_seconds": int(elapsed)
        }

    def _event_handler(self, event_type: str, data: dict):
        if event_type == "account_saved":
            self.created = data.get("created", self.created + 1)
            self.valid = data.get("valid", self.valid)
            self.locked = data.get("locked", self.locked)
            self.invalid = data.get("invalid", self.invalid)
            self.unverified = data.get("unverified", self.unverified)

        if self._callback:
            try:
                # If callback is a coroutine or normal func
                res = self._callback(event_type, data)
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
            except Exception as e:
                print(f"[GenRunner] Callback error: {e}")

    async def start(self, target: int = 1, threads: int = 1, callback: Optional[Callable] = None) -> Dict[str, Any]:
        if self.is_running:
            raise RuntimeError("Generator is already running!")

        if gen_module is None:
            raise RuntimeError("Generator engine is not initialized.")

        self.is_running = True
        self.target = target
        self.created = 0
        self.valid = 0
        self.locked = 0
        self.invalid = 0
        self.unverified = 0
        self.start_time = time.time()
        self._callback = callback

        try:
            self.current_task = asyncio.current_task()
            results = await gen_module.run_generation_task(
                target=target,
                threads=threads,
                event_callback=self._event_handler
            )
            return results
        finally:
            self.is_running = False
            self.current_task = None

    def stop(self):
        if self.is_running and gen_module:
            gen_module.stop_generation()
            if self.current_task and not self.current_task.done():
                self.current_task.cancel()
            self.is_running = False


# Global singleton instance
gen_runner = GeneratorRunner()

