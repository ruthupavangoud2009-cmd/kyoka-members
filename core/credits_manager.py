import json
import os
import time
import threading
from pathlib import Path
from typing import Dict, Any, Tuple, List

from config import BASE_DIR, is_admin

CREDITS_FILE = BASE_DIR / "credits.json"
_LOCK = threading.Lock()


class CreditsManager:
    def __init__(self, file_path: Path = CREDITS_FILE):
        self.file_path = file_path
        self._credits: Dict[str, int] = {}
        self._orders: Dict[str, int] = {}
        self._daily: Dict[str, float] = {}
        self._load()

    def _load(self):
        with _LOCK:
            if not self.file_path.exists():
                self._credits = {}
                self._orders = {}
                self._daily = {}
                self._save_unlocked()
            else:
                try:
                    with open(self.file_path, "r", encoding="utf-8") as f:
                        raw = json.load(f)
                    if isinstance(raw, dict):
                        if "credits" in raw:
                            self._credits = raw.get("credits", {})
                            self._orders = raw.get("orders", {})
                            self._daily = raw.get("daily", {})
                        else:
                            # Backwards-compatibility with flat dictionary
                            self._credits = {k: int(v) for k, v in raw.items() if str(v).isdigit()}
                            self._orders = {}
                            self._daily = {}
                except Exception:
                    self._credits = {}
                    self._orders = {}
                    self._daily = {}

    def _save_unlocked(self):
        try:
            data = {
                "credits": self._credits,
                "orders": self._orders,
                "daily": self._daily
            }
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[Credits] Failed to save credits: {e}")

    def is_infinite(self, user_id: int) -> bool:
        """Admins and Owners have infinite credits."""
        return is_admin(user_id)

    def get_credits(self, user_id: int) -> int:
        if self.is_infinite(user_id):
            return 999999999
        uid = str(user_id)
        with _LOCK:
            return self._credits.get(uid, 0)

    def format_credits(self, user_id: int) -> str:
        if self.is_infinite(user_id):
            return "♾️ Infinite (Owner)"
        return f"{self.get_credits(user_id):,} credits"

    def can_afford(self, user_id: int, cost: int) -> bool:
        if self.is_infinite(user_id):
            return True
        return self.get_credits(user_id) >= cost

    def deduct_credits(self, user_id: int, cost: int) -> bool:
        """Deduct credits if user can afford it. Owners are never deducted."""
        if self.is_infinite(user_id) or cost <= 0:
            return True

        uid = str(user_id)
        with _LOCK:
            cur = self._credits.get(uid, 0)
            if cur < cost:
                return False
            self._credits[uid] = cur - cost
            self._save_unlocked()
            return True

    def refund_credits(self, user_id: int, amount: int):
        """Refund credits for failed member joins."""
        if self.is_infinite(user_id) or amount <= 0:
            return
        uid = str(user_id)
        with _LOCK:
            cur = self._credits.get(uid, 0)
            self._credits[uid] = cur + amount
            self._save_unlocked()

    def record_members_joined(self, user_id: int, count: int):
        """Record total successful member orders for the user."""
        if count <= 0:
            return
        uid = str(user_id)
        with _LOCK:
            cur = self._orders.get(uid, 0)
            self._orders[uid] = cur + count
            self._save_unlocked()

    def add_credits(self, user_id: int, amount: int) -> int:
        if amount <= 0:
            return self.get_credits(user_id)
        uid = str(user_id)
        with _LOCK:
            cur = self._credits.get(uid, 0)
            new_bal = cur + amount
            self._credits[uid] = new_bal
            self._save_unlocked()
            return new_bal

    def remove_credits(self, user_id: int, amount: int) -> int:
        uid = str(user_id)
        with _LOCK:
            cur = self._credits.get(uid, 0)
            new_bal = max(0, cur - amount)
            self._credits[uid] = new_bal
            self._save_unlocked()
            return new_bal

    def set_credits(self, user_id: int, amount: int) -> int:
        uid = str(user_id)
        with _LOCK:
            new_bal = max(0, amount)
            self._credits[uid] = new_bal
            self._save_unlocked()
            return new_bal

    def claim_daily(self, user_id: int, reward: int = 1) -> Tuple[bool, str, int]:
        """Claim daily free credits (24-hour cooldown)."""
        uid = str(user_id)
        now = time.time()
        cooldown = 86400  # 24 hours

        with _LOCK:
            last_claim = self._daily.get(uid, 0)
            elapsed = now - last_claim
            if elapsed < cooldown:
                remaining = int(cooldown - elapsed)
                hours, rem = divmod(remaining, 3600)
                mins, secs = divmod(rem, 60)
                time_str = f"{hours}h {mins}m {secs}s"
                return False, f"You have already claimed your daily reward! Please wait **{time_str}**.", self._credits.get(uid, 0)

            self._daily[uid] = now
            cur = self._credits.get(uid, 0)
            new_bal = cur + reward
            self._credits[uid] = new_bal
            self._save_unlocked()
            return True, f"🎉 You claimed your daily reward of **{reward} credit**! (1 Credit = 1 Member)", new_bal

    def transfer(self, sender_id: int, receiver_id: int, amount: int) -> Tuple[bool, str]:
        if sender_id == receiver_id:
            return False, "You cannot transfer credits to yourself."
        if amount <= 0:
            return False, "Transfer amount must be greater than 0."

        if not self.is_infinite(sender_id):
            with _LOCK:
                sender_cur = self._credits.get(str(sender_id), 0)
                if sender_cur < amount:
                    return False, f"Insufficient balance. You have {sender_cur:,} credits."
                self._credits[str(sender_id)] = sender_cur - amount
                self._credits[str(receiver_id)] = self._credits.get(str(receiver_id), 0) + amount
                self._save_unlocked()
        else:
            with _LOCK:
                self._credits[str(receiver_id)] = self._credits.get(str(receiver_id), 0) + amount
                self._save_unlocked()

        return True, f"Successfully transferred {amount:,} credits."

    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        uid = str(user_id)
        with _LOCK:
            credits = "♾️ Infinite (Owner)" if self.is_infinite(user_id) else self._credits.get(uid, 0)
            orders = self._orders.get(uid, 0)
        return {
            "credits": credits,
            "orders": orders,
            "role": "👑 Owner" if self.is_infinite(user_id) else "👤 Member"
        }

    def get_leaderboard(self, limit: int = 10) -> List[Tuple[str, int]]:
        with _LOCK:
            # Sort by credits
            sorted_users = sorted(
                [(uid, bal) for uid, bal in self._credits.items() if bal > 0],
                key=lambda x: x[1],
                reverse=True
            )
            return sorted_users[:limit]


# Global singleton
credits_manager = CreditsManager()
