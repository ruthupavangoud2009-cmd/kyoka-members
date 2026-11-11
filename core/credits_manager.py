import json
import os
import threading
from pathlib import Path
from typing import Dict, Any, Tuple

from config import BASE_DIR, is_admin

CREDITS_FILE = BASE_DIR / "credits.json"
_LOCK = threading.Lock()


class CreditsManager:
    def __init__(self, file_path: Path = CREDITS_FILE):
        self.file_path = file_path
        self._credits: Dict[str, int] = {}
        self._load()

    def _load(self):
        with _LOCK:
            if not self.file_path.exists():
                self._credits = {}
                self._save_unlocked()
            else:
                try:
                    with open(self.file_path, "r", encoding="utf-8") as f:
                        self._credits = json.load(f)
                except Exception:
                    self._credits = {}

    def _save_unlocked(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self._credits, f, indent=2)
        except Exception as e:
            print(f"[Credits] Failed to save credits: {e}")

    def is_infinite(self, user_id: int) -> bool:
        """Admins and Owners have infinite credits."""
        return is_admin(user_id)

    def get_credits(self, user_id: int) -> int:
        """Return credits. If owner, returns 999999999 for numeric math."""
        if self.is_infinite(user_id):
            return 999999999
        uid = str(user_id)
        with _LOCK:
            return self._credits.get(uid, 0)

    def format_credits(self, user_id: int) -> str:
        """Return formatted string: ♾️ Infinite for owner, or exact number."""
        if self.is_infinite(user_id):
            return "♾️ Infinite (Owner)"
        return f"{self.get_credits(user_id):,} credits"

    def can_afford(self, user_id: int, cost: int) -> bool:
        if self.is_infinite(user_id):
            return True
        return self.get_credits(user_id) >= cost

    def deduct_credits(self, user_id: int, cost: int) -> bool:
        """Deduct credits if user can afford it. Owners are never deducted."""
        if self.is_infinite(user_id):
            return True
        if cost <= 0:
            return True

        uid = str(user_id)
        with _LOCK:
            cur = self._credits.get(uid, 0)
            if cur < cost:
                return False
            self._credits[uid] = cur - cost
            self._save_unlocked()
            return True

    def add_credits(self, user_id: int, amount: int) -> int:
        """Add credits to a user."""
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
        """Remove credits from a user (cannot go below 0)."""
        uid = str(user_id)
        with _LOCK:
            cur = self._credits.get(uid, 0)
            new_bal = max(0, cur - amount)
            self._credits[uid] = new_bal
            self._save_unlocked()
            return new_bal

    def set_credits(self, user_id: int, amount: int) -> int:
        """Set exact credit balance for a user."""
        uid = str(user_id)
        with _LOCK:
            new_bal = max(0, amount)
            self._credits[uid] = new_bal
            self._save_unlocked()
            return new_bal

    def transfer(self, sender_id: int, receiver_id: int, amount: int) -> Tuple[bool, str]:
        """Transfer credits between users."""
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
            # Owner has infinite credits, so receiver simply receives the amount
            with _LOCK:
                self._credits[str(receiver_id)] = self._credits.get(str(receiver_id), 0) + amount
                self._save_unlocked()

        return True, f"Successfully transferred {amount:,} credits."


# Global singleton
credits_manager = CreditsManager()
