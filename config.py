import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
GEN_DIR = BASE_DIR / "NEXUVER EVS" / "NILOY Gen"
UNLOCK_DIR = BASE_DIR / "UNLOCKER" / "Phone_Verifier"

# Discord Bot Settings
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
BOT_PREFIX = os.getenv("BOT_PREFIX", "!").strip()
ADMIN_IDS_RAW = os.getenv("ADMIN_USER_IDS", "")
ADMIN_USER_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()]

# Web Server & Keep-Alive Settings for Render
PORT = int(os.getenv("PORT", "8080"))
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").strip()
KEEP_ALIVE_INTERVAL = int(os.getenv("KEEP_ALIVE_INTERVAL", "300"))  # seconds

# Global Output Paths
GEN_OUTPUT_DIR = GEN_DIR / "output"
GEN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UNLOCK_OUTPUT_DIR = UNLOCK_DIR / "output"
UNLOCK_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VALID_TXT = GEN_OUTPUT_DIR / "valid.txt"
LOCKED_TXT = GEN_OUTPUT_DIR / "locked.txt"
UNVERIFIED_TXT = GEN_OUTPUT_DIR / "unverified.txt"
INVALID_TXT = GEN_OUTPUT_DIR / "invalid.txt"
UNLOCKED_TXT = UNLOCK_OUTPUT_DIR / "unlocked.txt"


def is_admin(user_id: int) -> bool:
    """Check if a Discord user is authorized. If no admin IDs are set, all users are allowed."""
    if not ADMIN_USER_IDS:
        return True
    return user_id in ADMIN_USER_IDS


def sync_env_to_configs():
    """Sync environment variables from Render into JSON config files if specified."""
    # Sync Gen config
    gen_cfg_path = GEN_DIR / "config.json"
    if gen_cfg_path.exists():
        try:
            with open(gen_cfg_path, "r", encoding="utf-8") as f:
                gen_cfg = json.load(f)

            updated = False
            # Email provider override
            if os.getenv("GEN_EMAIL_PROVIDER"):
                gen_cfg.setdefault("email_provider", {})["name"] = os.getenv("GEN_EMAIL_PROVIDER")
                updated = True
            if os.getenv("AFHAMXMAILZ_KEY"):
                gen_cfg.setdefault("email_provider", {}).setdefault("afhamxmailz", {})["api_key"] = os.getenv("AFHAMXMAILZ_KEY")
                updated = True
            if os.getenv("NINECAPTCHA_KEY"):
                gen_cfg.setdefault("ninecaptcha", {})["api_key"] = os.getenv("NINECAPTCHA_KEY")
                gen_cfg["ninecaptcha"]["enabled"] = True
                updated = True
            if os.getenv("NOPECHA_KEY"):
                nopecha_keys_file = GEN_DIR / "input" / "nopecha_keys.txt"
                nopecha_keys_file.parent.mkdir(parents=True, exist_ok=True)
                with open(nopecha_keys_file, "w", encoding="utf-8") as nf:
                    nf.write(os.getenv("NOPECHA_KEY") + "\n")
                gen_cfg.setdefault("nopecha", {})["enabled"] = True
                updated = True

            if updated:
                with open(gen_cfg_path, "w", encoding="utf-8") as f:
                    json.dump(gen_cfg, f, indent=4)
        except Exception as e:
            print(f"[Config] Error syncing Gen config: {e}")

    # Sync Unlock config
    unlock_cfg_path = UNLOCK_DIR / "config.json"
    if unlock_cfg_path.exists():
        try:
            with open(unlock_cfg_path, "r", encoding="utf-8") as f:
                u_cfg = json.load(f)

            updated = False
            if os.getenv("PHONE_SERVICE"):
                u_cfg["phone_service"] = os.getenv("PHONE_SERVICE")
                updated = True
            if os.getenv("FIVESIM_KEY"):
                u_cfg.setdefault("5sim", {})["api_key"] = os.getenv("FIVESIM_KEY")
                updated = True
            if os.getenv("SMSBOWER_KEY"):
                u_cfg.setdefault("smsbower", {})["api_key"] = os.getenv("SMSBOWER_KEY")
                updated = True
            if os.getenv("HEROSMS_KEY"):
                u_cfg.setdefault("herosms", {})["api_key"] = os.getenv("HEROSMS_KEY")
                updated = True
            if os.getenv("TIGERSMS_KEY"):
                u_cfg.setdefault("tigersms", {})["api_key"] = os.getenv("TIGERSMS_KEY")
                updated = True
            if os.getenv("CAPTCHA_SOLVER"):
                u_cfg.setdefault("captcha", {})["solver"] = os.getenv("CAPTCHA_SOLVER")
                updated = True
            if os.getenv("ONYX_KEY"):
                u_cfg.setdefault("captcha", {})["onyx_api_key"] = os.getenv("ONYX_KEY")
                updated = True
            if os.getenv("HCAPTCHASOLVER_KEY"):
                u_cfg.setdefault("captcha", {})["hcaptchasolver_api_key"] = os.getenv("HCAPTCHASOLVER_KEY")
                updated = True

            if updated:
                with open(unlock_cfg_path, "w", encoding="utf-8") as f:
                    json.dump(u_cfg, f, indent=2)
        except Exception as e:
            print(f"[Config] Error syncing Unlock config: {e}")

# Run sync once at startup
sync_env_to_configs()

