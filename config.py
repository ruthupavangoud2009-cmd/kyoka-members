import os
import json
import base64
import hashlib
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

# Persistent Storage across Cloud Reboots / Redeployments
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATA_STOCK_VAULT = DATA_DIR / "stock.vault"
DATA_STOCK_TXT = DATA_DIR / "stock.txt"
DATA_PROXIES_TXT = DATA_DIR / "proxies.txt"
DATA_CREDITS_JSON = DATA_DIR / "credits.json"
DATA_USAGE_JSON = DATA_DIR / "account_usage.json"
VAULT_KEY = "kyoka_vault_salt_2026"


def _vault_encrypt(text: str) -> str:
    kb = hashlib.sha256(VAULT_KEY.encode()).digest()
    db = text.encode("utf-8")
    enc = bytes(b ^ kb[i % len(kb)] for i, b in enumerate(db))
    return base64.b64encode(enc).decode("ascii")


def _vault_decrypt(enc_str: str) -> str:
    kb = hashlib.sha256(VAULT_KEY.encode()).digest()
    enc = base64.b64decode(enc_str.strip().encode("ascii"))
    dec = bytes(b ^ kb[i % len(kb)] for i, b in enumerate(enc))
    return dec.decode("utf-8", errors="ignore")


def save_stock_to_vault():
    """Read VALID_TXT and encrypt into data/stock.vault for Git-safe persistence."""
    try:
        if VALID_TXT.exists() and VALID_TXT.stat().st_size > 0:
            with open(VALID_TXT, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if content.strip():
                enc = _vault_encrypt(content)
                with open(DATA_STOCK_VAULT, "w", encoding="ascii") as f:
                    f.write(enc)
    except Exception as e:
        print(f"[Persistence] Failed to save vault: {e}")


def sync_persistent_data():
    """
    Ensure files persist across Render restarts/re-deploys.
    Syncs committed data/ files into runtime paths and vice-versa.
    """
    try:
        # 1. Accounts: If VALID_TXT is empty/missing, restore from encrypted DATA_STOCK_VAULT
        if DATA_STOCK_VAULT.exists() and (not VALID_TXT.exists() or VALID_TXT.stat().st_size == 0):
            try:
                with open(DATA_STOCK_VAULT, "r", encoding="ascii") as f:
                    raw_enc = f.read()
                if raw_enc.strip():
                    decrypted = _vault_decrypt(raw_enc)
                    with open(VALID_TXT, "w", encoding="utf-8") as f:
                        f.write(decrypted)
            except Exception as e:
                print(f"[Persistence] Error restoring stock vault: {e}")

        # If VALID_TXT has accounts, update the vault
        save_stock_to_vault()

        # 2. Proxies: Sync data/proxies.txt <-> GEN_DIR/input/proxies.txt
        gen_proxy_file = GEN_DIR / "input" / "proxies.txt"
        gen_proxy_file.parent.mkdir(parents=True, exist_ok=True)
        seen_proxies = set()
        all_proxies = []

        for p_file in (DATA_PROXIES_TXT, gen_proxy_file):
            if p_file.exists():
                with open(p_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        p = line.strip()
                        if p and not p.startswith("#") and p not in seen_proxies:
                            seen_proxies.add(p)
                            all_proxies.append(p)

        if all_proxies:
            with open(gen_proxy_file, "w", encoding="utf-8") as f:
                for p in all_proxies:
                    f.write(p + "\n")
            with open(DATA_PROXIES_TXT, "w", encoding="utf-8") as f:
                for p in all_proxies:
                    f.write(p + "\n")

        # 3. Credits & Usage sync
        root_credits = BASE_DIR / "credits.json"
        if DATA_CREDITS_JSON.exists() and (not root_credits.exists() or root_credits.stat().st_size <= 2):
            if DATA_CREDITS_JSON.stat().st_size > 2:
                with open(DATA_CREDITS_JSON, "r", encoding="utf-8") as f:
                    content = f.read()
                with open(root_credits, "w", encoding="utf-8") as f:
                    f.write(content)
        elif root_credits.exists() and root_credits.stat().st_size > 2:
            with open(root_credits, "r", encoding="utf-8") as f:
                content = f.read()
            with open(DATA_CREDITS_JSON, "w", encoding="utf-8") as f:
                f.write(content)

        root_usage = BASE_DIR / "account_usage.json"
        if DATA_USAGE_JSON.exists() and (not root_usage.exists() or root_usage.stat().st_size <= 2):
            if DATA_USAGE_JSON.stat().st_size > 2:
                with open(DATA_USAGE_JSON, "r", encoding="utf-8") as f:
                    content = f.read()
                with open(root_usage, "w", encoding="utf-8") as f:
                    f.write(content)
        elif root_usage.exists() and root_usage.stat().st_size > 2:
            with open(root_usage, "r", encoding="utf-8") as f:
                content = f.read()
            with open(DATA_USAGE_JSON, "w", encoding="utf-8") as f:
                f.write(content)
    except Exception as e:
        print(f"[Persistence] Error syncing persistent data: {e}")


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
            env_9cap = (os.getenv("NINECAPTCHA_KEY") or "").strip()
            if env_9cap and env_9cap != "9cap-8a70873a-b3e7-45b6-bbcb-5c8f63782e49":
                gen_cfg.setdefault("ninecaptcha", {})["api_key"] = env_9cap
                gen_cfg["ninecaptcha"]["enabled"] = True
                updated = True
            elif not gen_cfg.get("ninecaptcha", {}).get("api_key") or gen_cfg.get("ninecaptcha", {}).get("api_key") == "9cap-8a70873a-b3e7-45b6-bbcb-5c8f63782e49":
                gen_cfg.setdefault("ninecaptcha", {})["api_key"] = "9cap-49ee15da-a2d9-4cef-8cce-a224eeda172b"
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


def update_service_key(service: str, key: str) -> bool:
    """Dynamically set an API key or config from Discord commands."""
    service = service.lower().strip()
    key = key.strip()

    gen_cfg_path = GEN_DIR / "config.json"
    unlock_cfg_path = UNLOCK_DIR / "config.json"

    if service in ("5sim", "fivesim"):
        os.environ["FIVESIM_KEY"] = key
        if unlock_cfg_path.exists():
            with open(unlock_cfg_path, "r", encoding="utf-8") as f:
                c = json.load(f)
            c.setdefault("5sim", {})["api_key"] = key
            with open(unlock_cfg_path, "w", encoding="utf-8") as f:
                json.dump(c, f, indent=2)
        return True

    elif service in ("onyx", "onyx_key"):
        os.environ["ONYX_KEY"] = key
        if unlock_cfg_path.exists():
            with open(unlock_cfg_path, "r", encoding="utf-8") as f:
                c = json.load(f)
            c.setdefault("captcha", {})["onyx_api_key"] = key
            with open(unlock_cfg_path, "w", encoding="utf-8") as f:
                json.dump(c, f, indent=2)
        return True

    elif service in ("smsbower", "bower"):
        os.environ["SMSBOWER_KEY"] = key
        if unlock_cfg_path.exists():
            with open(unlock_cfg_path, "r", encoding="utf-8") as f:
                c = json.load(f)
            c.setdefault("smsbower", {})["api_key"] = key
            with open(unlock_cfg_path, "w", encoding="utf-8") as f:
                json.dump(c, f, indent=2)
        return True

    elif service in ("herosms", "hero"):
        os.environ["HEROSMS_KEY"] = key
        if unlock_cfg_path.exists():
            with open(unlock_cfg_path, "r", encoding="utf-8") as f:
                c = json.load(f)
            c.setdefault("herosms", {})["api_key"] = key
            with open(unlock_cfg_path, "w", encoding="utf-8") as f:
                json.dump(c, f, indent=2)
        return True

    elif service in ("ninecaptcha", "9cap"):
        os.environ["NINECAPTCHA_KEY"] = key
        if gen_cfg_path.exists():
            with open(gen_cfg_path, "r", encoding="utf-8") as f:
                c = json.load(f)
            c.setdefault("ninecaptcha", {})["api_key"] = key
            c["ninecaptcha"]["enabled"] = True
            with open(gen_cfg_path, "w", encoding="utf-8") as f:
                json.dump(c, f, indent=4)
        return True

    elif service in ("afhamxmailz", "afham", "mail"):
        os.environ["AFHAMXMAILZ_KEY"] = key
        if gen_cfg_path.exists():
            with open(gen_cfg_path, "r", encoding="utf-8") as f:
                c = json.load(f)
            c.setdefault("email_provider", {}).setdefault("afhamxmailz", {})["api_key"] = key
            with open(gen_cfg_path, "w", encoding="utf-8") as f:
                json.dump(c, f, indent=4)
        return True

    elif service in ("phone_service", "service"):
        os.environ["PHONE_SERVICE"] = key
        if unlock_cfg_path.exists():
            with open(unlock_cfg_path, "r", encoding="utf-8") as f:
                c = json.load(f)
            c["phone_service"] = key
            with open(unlock_cfg_path, "w", encoding="utf-8") as f:
                json.dump(c, f, indent=2)
        return True

    return False


def update_phone_config(service: str, country: str, operator: str = "") -> bool:
    """Update country and operator for SMS service."""
    service = service.lower().strip()
    unlock_cfg_path = UNLOCK_DIR / "config.json"
    if not unlock_cfg_path.exists():
        return False
    try:
        with open(unlock_cfg_path, "r", encoding="utf-8") as f:
            c = json.load(f)
        if service in c:
            if country:
                c[service]["country"] = country
            if operator and "operator" in c[service]:
                c[service]["operator"] = operator
        with open(unlock_cfg_path, "w", encoding="utf-8") as f:
            json.dump(c, f, indent=2)
        return True
    except Exception:
        return False


def toggle_setting(feature: str, enabled: bool) -> bool:
    """Toggle boolean settings like humanizer, proxy, hypesquad."""
    feature = feature.lower().strip()
    gen_cfg_path = GEN_DIR / "config.json"
    if not gen_cfg_path.exists():
        return False
    try:
        with open(gen_cfg_path, "r", encoding="utf-8") as f:
            c = json.load(f)
        if feature in ("humanizer", "humanize"):
            c.setdefault("humanizer", {})["enabled"] = enabled
        elif feature in ("hypesquad", "hype"):
            c.setdefault("humanizer", {})["hypesquad"] = enabled
        elif feature in ("avatar", "avatars"):
            c.setdefault("humanizer", {})["avatar"] = enabled
        elif feature in ("bio", "bios"):
            c.setdefault("humanizer", {})["bio"] = enabled
        elif feature in ("proxy", "proxies"):
            c.setdefault("proxy", {})["enabled"] = enabled
        elif feature in ("nopecha",):
            c.setdefault("nopecha", {})["enabled"] = enabled
        elif feature in ("ninecaptcha", "9cap"):
            c.setdefault("ninecaptcha", {})["enabled"] = enabled
        else:
            return False
        with open(gen_cfg_path, "w", encoding="utf-8") as f:
            json.dump(c, f, indent=4)
        return True
    except Exception:
        return False


def get_full_config_summary() -> dict:
    """Read both configs and return a clean dictionary for Discord embed."""
    summary = {}
    gen_cfg_path = GEN_DIR / "config.json"
    unlock_cfg_path = UNLOCK_DIR / "config.json"

    if gen_cfg_path.exists():
        try:
            with open(gen_cfg_path, "r", encoding="utf-8") as f:
                gc = json.load(f)
            summary["email_provider"] = gc.get("email_provider", {}).get("name", "N/A")
            summary["ninecaptcha"] = "Enabled" if gc.get("ninecaptcha", {}).get("enabled") else "Disabled"
            summary["nopecha"] = "Enabled" if gc.get("nopecha", {}).get("enabled") else "Disabled"
            summary["proxy_enabled"] = bool(gc.get("proxy", {}).get("enabled", False))
            summary["humanizer_enabled"] = bool(gc.get("humanizer", {}).get("enabled", False))
            summary["cooldown"] = gc.get("cooldown", 90)
            summary["threads"] = gc.get("threads", 1)
        except Exception:
            pass

    if unlock_cfg_path.exists():
        try:
            with open(unlock_cfg_path, "r", encoding="utf-8") as f:
                uc = json.load(f)
            summary["phone_service"] = uc.get("phone_service", "5sim")
            summary["captcha_solver"] = uc.get("captcha", {}).get("solver", "onyx")
            summary["fivesim_country"] = uc.get("5sim", {}).get("country", "indonesia")
            summary["fivesim_operator"] = uc.get("5sim", {}).get("operator", "virtual51")
        except Exception:
            pass

    return summary

# Run sync once at startup
sync_env_to_configs()

