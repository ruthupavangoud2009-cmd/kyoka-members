import json
import re
import threading
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from config import VALID_TXT, UNLOCKED_TXT, BASE_DIR

USAGE_FILE = BASE_DIR / "account_usage.json"
_LOCK = threading.Lock()
MAX_USES_PER_ACCOUNT = 100


class StockManager:
    def __init__(self, usage_file: Path = USAGE_FILE):
        self.usage_file = usage_file
        self._usage: Dict[str, Dict[str, Any]] = {}
        self._load_usage()

    def _load_usage(self):
        with _LOCK:
            if not self.usage_file.exists():
                self._usage = {}
                self._save_usage_unlocked()
            else:
                try:
                    with open(self.usage_file, "r", encoding="utf-8") as f:
                        self._usage = json.load(f)
                except Exception:
                    self._usage = {}

    def _save_usage_unlocked(self):
        try:
            with open(self.usage_file, "w", encoding="utf-8") as f:
                json.dump(self._usage, f, indent=2)
        except Exception as e:
            print(f"[StockManager] Error saving usage: {e}")

    def extract_token(self, line: str) -> Optional[str]:
        """Extract clean Discord token from a line (email:pass:token or raw token)."""
        line = line.strip()
        if not line:
            return None
        parts = line.split(":")
        candidate = parts[2] if len(parts) >= 3 else parts[0]
        candidate = candidate.strip().strip('"').strip("'")
        match = re.search(r"([a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{6,}\.[a-zA-Z0-9_-]{25,})", candidate)
        if match:
            return match.group(1)
        # Fallback for alternative or base64 token formats
        if len(candidate) >= 30 and " " not in candidate:
            return candidate
        return None

    def add_accounts(self, raw_text_or_lines: Any, target_file: Path = VALID_TXT) -> Tuple[int, int, int]:
        """
        Parse raw text or lines, deduplicate against target file, and append new accounts.
        Returns (added_count, duplicate_count, total_in_file).
        """
        if isinstance(raw_text_or_lines, str):
            lines = raw_text_or_lines.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        else:
            lines = list(raw_text_or_lines)

        target_file.parent.mkdir(parents=True, exist_ok=True)

        existing_tokens = set()
        existing_lines = []
        if target_file.exists():
            with open(target_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped:
                        existing_lines.append(stripped)
                        tok = self.extract_token(stripped)
                        if tok:
                            existing_tokens.add(tok)

        added = 0
        duplicates = 0
        new_lines_to_append = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            tok = self.extract_token(stripped)
            if not tok:
                continue
            if tok in existing_tokens:
                duplicates += 1
                continue

            existing_tokens.add(tok)
            new_lines_to_append.append(stripped)
            added += 1

        if new_lines_to_append:
            with open(target_file, "a", encoding="utf-8") as f:
                for nl in new_lines_to_append:
                    f.write(nl + "\n")

        total = len(existing_lines) + added
        return added, duplicates, total

    def get_all_raw_accounts(self) -> List[str]:
        """Get all raw account lines from VALID_TXT and UNLOCKED_TXT."""
        accounts = []
        seen = set()
        for fp in (UNLOCKED_TXT, VALID_TXT):
            if fp.exists():
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        stripped = line.strip()
                        tok = self.extract_token(stripped)
                        if tok and tok not in seen:
                            seen.add(tok)
                            accounts.append(stripped)
        return accounts

    def get_token_uses(self, token: str) -> int:
        return self._usage.get(token, {}).get("uses", 0)

    def has_token_joined_server(self, token: str, invite_or_guild: str) -> bool:
        clean = invite_or_guild.strip().lower()
        servers = self._usage.get(token, {}).get("servers", [])
        return clean in [s.lower() for s in servers]

    def record_join(self, token: str, invite_or_guild: str):
        """Record successful server join for a token."""
        clean = invite_or_guild.strip().lower()
        with _LOCK:
            if token not in self._usage:
                self._usage[token] = {"uses": 0, "servers": []}
            self._usage[token]["uses"] = self._usage[token].get("uses", 0) + 1
            servers = self._usage[token].setdefault("servers", [])
            if clean not in [s.lower() for s in servers]:
                servers.append(clean)
            self._save_usage_unlocked()

    def get_available_tokens_for_server(self, invite_code: str, amount: int) -> List[str]:
        """
        Get up to `amount` accounts. Each account can join up to 100 servers (MAX_USES_PER_ACCOUNT).
        Prioritizes accounts that haven't joined this server yet, but falls back to all active accounts with uses < 100.
        """
        clean_code = invite_code.strip().lower()
        eligible_fresh = []
        eligible_fallback = []
        raw_accounts = self.get_all_raw_accounts()

        for raw in raw_accounts:
            tok = self.extract_token(raw)
            if not tok:
                continue

            uses = self.get_token_uses(tok)
            if uses >= MAX_USES_PER_ACCOUNT:
                continue

            if not self.has_token_joined_server(tok, clean_code):
                eligible_fresh.append(tok)
            else:
                eligible_fallback.append(tok)

        eligible = (eligible_fresh + eligible_fallback)[:amount]
        return eligible

    def get_stock_summary(self) -> Dict[str, Any]:
        """Calculate comprehensive stock statistics."""
        raw_accounts = self.get_all_raw_accounts()
        total_accounts = len(raw_accounts)

        total_joins_used = 0
        fully_exhausted = 0
        active_accounts = 0

        for raw in raw_accounts:
            tok = self.extract_token(raw)
            if not tok:
                continue
            uses = self.get_token_uses(tok)
            total_joins_used += uses
            if uses >= MAX_USES_PER_ACCOUNT:
                fully_exhausted += 1
            else:
                active_accounts += 1

        total_capacity = total_accounts * MAX_USES_PER_ACCOUNT
        remaining_capacity = max(0, total_capacity - total_joins_used)

        valid_count = 0
        if VALID_TXT.exists():
            with open(VALID_TXT, "r", encoding="utf-8", errors="ignore") as f:
                valid_count = sum(1 for line in f if line.strip())

        unlocked_count = 0
        if UNLOCKED_TXT.exists():
            with open(UNLOCKED_TXT, "r", encoding="utf-8", errors="ignore") as f:
                unlocked_count = sum(1 for line in f if line.strip())

        return {
            "total_accounts": total_accounts,
            "active_accounts": active_accounts,
            "fully_exhausted": fully_exhausted,
            "max_uses_per_account": MAX_USES_PER_ACCOUNT,
            "remaining_member_capacity": remaining_capacity,
            "total_joins_performed": total_joins_used,
            "valid_stock": valid_count,
            "unlocked_stock": unlocked_count,
        }


# Global singleton instance
stock_manager = StockManager()

