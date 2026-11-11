import asyncio
import time
from typing import Optional, Callable, Dict, Any, List

from core.gen_runner import gen_runner
from core.unlock_runner import unlock_runner

class PipelineRunner:
    def __init__(self):
        self.is_running = False
        self.target = 0
        self.generated = 0
        self.valid = 0
        self.locked_to_unlock = 0
        self.unlocked_success = 0
        self.unlocked_failed = 0
        self.start_time: Optional[float] = None
        self._callback: Optional[Callable] = None
        self._locked_queue: asyncio.Queue = asyncio.Queue()
        self._consumer_task: Optional[asyncio.Task] = None

    def get_stats(self) -> Dict[str, Any]:
        elapsed = time.time() - self.start_time if (self.is_running and self.start_time) else 0
        return {
            "is_running": self.is_running,
            "target": self.target,
            "generated": self.generated,
            "valid": self.valid,
            "locked_queued": self.locked_to_unlock,
            "unlocked_success": self.unlocked_success,
            "unlocked_failed": self.unlocked_failed,
            "elapsed_seconds": int(elapsed)
        }

    async def _unlock_consumer(self):
        """Asynchronous worker that consumes locked tokens and passes them to Phone Verifier."""
        while self.is_running or not self._locked_queue.empty():
            try:
                token_item = await asyncio.wait_for(self._locked_queue.get(), timeout=1.5)
            except asyncio.TimeoutError:
                continue

            # Process single token unlock
            line = f"{token_item['email']}:{token_item['password']}:{token_item['token']}"
            try:
                res = await unlock_runner.verify_tokens([line], threads=1)
                if res.get("successful", 0) > 0:
                    self.unlocked_success += 1
                    status = "success"
                else:
                    self.unlocked_failed += 1
                    status = "failed"

                if self._callback:
                    try:
                        self._callback("pipeline_unlock_result", {
                            "email": token_item["email"],
                            "token": token_item["token"],
                            "status": status,
                            "unlocked_success": self.unlocked_success,
                            "unlocked_failed": self.unlocked_failed
                        })
                    except Exception:
                        pass
            except Exception as e:
                print(f"[Pipeline] Unlock error for {token_item.get('email')}: {e}")
                self.unlocked_failed += 1
            finally:
                self._locked_queue.task_done()

    def _gen_event_handler(self, event_type: str, data: dict):
        if event_type == "account_saved":
            self.generated = data.get("created", self.generated + 1)
            status = data.get("status", "")
            if status == "VALID":
                self.valid += 1
            elif status == "LOCKED":
                self.locked_to_unlock += 1
                self._locked_queue.put_nowait({
                    "email": data.get("email"),
                    "password": data.get("password"),
                    "token": data.get("token")
                })

        if self._callback:
            try:
                self._callback(event_type, data)
            except Exception:
                pass

    async def start(self, target: int = 1, threads: int = 1, callback: Optional[Callable] = None):
        if self.is_running:
            raise RuntimeError("Pipeline is already running!")

        self.is_running = True
        self.target = target
        self.generated = 0
        self.valid = 0
        self.locked_to_unlock = 0
        self.unlocked_success = 0
        self.unlocked_failed = 0
        self.start_time = time.time()
        self._callback = callback
        self._locked_queue = asyncio.Queue()

        self._consumer_task = asyncio.create_task(self._unlock_consumer())

        try:
            # Run generator
            await gen_runner.start(target=target, threads=threads, callback=self._gen_event_handler)
            # Wait for any remaining locked items in queue to finish processing
            if not self._locked_queue.empty():
                await self._locked_queue.join()
        finally:
            self.is_running = False
            if self._consumer_task and not self._consumer_task.done():
                self._consumer_task.cancel()

    def stop(self):
        if self.is_running:
            self.is_running = False
            gen_runner.stop()
            unlock_runner.stop()
            if self._consumer_task and not self._consumer_task.done():
                self._consumer_task.cancel()


# Global singleton instance
pipeline_runner = PipelineRunner()

