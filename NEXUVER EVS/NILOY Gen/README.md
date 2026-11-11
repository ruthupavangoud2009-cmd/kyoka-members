# MoonGen V3

> EVS Gen · Auto Cap · made by \*\*Moon\*\* 🌙

An automated Discord account generator with email-verification (EVS) support, automatic captcha solving via the NopeCHA browser extension, proxy rotation, humanizer profile customizer, and optional ADB-based mobile IP switching.

> ⚠️ \*\*Do not sell without permission.\*\* Use responsibly and only where you are authorized to.

\---

## Requirements

* **Python 3.11+** (3.11 or 3.12 recommended)
* **Windows 11 / Windows 10** (screen-sizing and ADB helpers are tuned for Windows; other platforms partially supported)
* **Brave Browser** installed (default automation browser), Chrome Playwright (`playwright install chromium`), or Edge
* An email provider account/API key (`cowmail`/`mailcow`, `draxono`, `hotmail007`, `duckmail`, `crowmail`)
* *(Optional)* [NopeCHA](https://nopecha.com) key(s) in `input/nopecha\_keys.txt` for automatic captcha solving
* *(Optional)* An Android device + ADB for mobile IP rotation

\---

## Setup

### 1\. Install Python dependencies

```powershell
pip install -r requirements.txt
```

If you want to use **Chrome Playwright** (`"browser": "chrome"` or `"browser": "playwright"` in config):

```powershell
playwright install chromium
```

### 2\. Install Brave

Download Brave from [brave.com](https://brave.com). MoonGen auto-detects it at the standard install locations — no extra config needed.

### 3\. Generate the config file

On first run, MoonGen creates a `config.json` template and exits:

```powershell
python moongen.py
```

Edit `config.json` (see [Configuration](#configuration) below), then run again.

### 4\. Prepare input files

These live in the `input/` folder (created automatically):

|File|Purpose|
|-|-|
|`input/proxies.txt`|One proxy per line. Format: `host:port`, `host:port:user:pass`, or `user:pass@host:port`. Only used if `proxy.enabled` is `true`.|
|`input/nopecha\_keys.txt`|One or multiple NopeCHA API keys (one per line). Auto-rotates across keys per account/worker. If empty, all keys are automatically purged from extension files.|

### 5\. Run

```powershell
python moongen.py
```

You'll be prompted for how many accounts to create (`0` = run until stopped). Results are written to the `output/` folder:

|File|Contents|
|-|-|
|`output/valid.txt`|Verified, working accounts/tokens (`email:password:token`)|
|`output/locked.txt`|Accounts that got locked|
|`output/unverified.txt`|Accounts created but not email-verified|

\---

## Configuration

`config.json` controls everything. Example:

```json
{
    "email\_provider": {
        "name": "cowmail",
        "client\_key": "",
        "cowmail": {
            "api\_base": "https://mail.example.com/api/v1",
            "api\_key": "YOUR\_MAILCOW\_API\_KEY",
            "domain": "example.com",
            "imap\_host": "mail.example.com",
            "imap\_port": 993
        },
        "crowmail": {
            "api\_key": ""
        }
    },
    "use\_wasted\_mails": false,
    "browser": "brave",
    "proxy": {
        "enabled": false,
        "file": "input/proxies.txt"
    },
    "adb": {
        "enabled": false,
        "device\_id": "",
        "settle\_seconds": 6,
        "verify\_ip": true,
        "max\_wait": 45
    },
    "threads": 1,
    "cooldown": 90,
    "humanizer": {
        "enabled": true,
        "name": true,
        "bio": true,
        "pronouns": true,
        "avatar": true,
        "hypesquad": true
    }
}
```

### Key fields

|Field|Description|
|-|-|
|`email\_provider.name`|`cowmail` (or `mailcow`), `draxono`, `hotmail007`, `duckmail`, or `crowmail`|
|`use\_wasted\_mails`|Reuse previously-wasted paid mails before buying new ones (see [Wasted mail reuse](#wasted-mail-reuse))|
|`browser`|`brave` (default), `chrome`, `edge`, or `playwright`|
|`proxy.enabled`|Enable proxy rotation from `proxy.file`|
|`adb.enabled`|Enable ADB mobile-IP switching between accounts|
|`threads`|Number of concurrent browser workers|
|`cooldown`|Seconds to wait between cycles per worker|
|`humanizer.enabled`|Automatically configure display name, avatar, bio, pronouns, and HypeSquad badge|

### Email providers

Set `email\_provider.name` and provide the matching credentials:

* **`cowmail`** (or **`mailcow`**) — self-hosted Mailcow. Provide an `email\_provider.cowmail` block:

```json
"email\_provider": {
    "name": "cowmail",
    "cowmail": {
        "api\_base": "https://mail.example.com/api/v1",
        "api\_key": "YOUR\_MAILCOW\_API\_KEY",
        "domain": "example.com",
        "imap\_host": "mail.example.com",
        "imap\_port": 993
    }
}
```

> \*\*Mailcow Configuration Note\*\*:
> In Mailcow Admin UI (\*\*System\*\* \&rarr; \*\*Configuration\*\* \&rarr; \*\*Access\*\* \&rarr; \*\*API\*\*):
> 1. Ensure \*\*API status\*\* is active.
> 2. Ensure your API Key has \*\*Read-Write Access\*\* (needed to create mailboxes).
> 3. In \*\*Allow API access from these IPs\*\*, add `0.0.0.0/0, ::/0` (or your client IP) to prevent HTTP 403 Forbidden.

* **`draxono`** — set `email\_provider.client\_key` (DraxonMails API key).
* **`hotmail007`** — set `email\_provider.hotmail007.client\_key` (or top-level `client\_key`).
* **`duckmail`** / **`crowmail`** — free temporary email providers (no API key required).
* **`zeus`** — set `zues\_key` and `mail\_type` (`trusted` ≈ $0.01, `cheap` ≈ $0.002).

\---

## Wasted mail reuse

Paid mail providers (**Zeus-X** and **Hotmail007**) charge you per email. If MoonGen buys a mail but the account fails to be created — form fill error, captcha failure, no token extracted, or any crash — that mail would normally be lost. Instead, MoonGen automatically saves it to `wasted\_mails.txt` in the exact format so it can be reused later:

```
email:password:refresh\_token:client\_id
```

To **reuse** these saved mails, set:

```json
"use\_wasted\_mails": true
```

When enabled, workers pop from `wasted\_mails.txt` before buying a fresh email. Free providers (`draxono`, `cowmail`, `duckmail`, `crowmail`) are never written here.

\---

## Captcha solving (NopeCHA)

MoonGen auto-downloads the NopeCHA extension into `nopecha\_ext/` on first run.

* **Multi-Key Support**: Add one or more keys to `input/nopecha\_keys.txt` (one per line). MoonGen automatically rotates through keys across generation cycles and workers.
* **Auto-Purge**: If all keys are removed from `input/nopecha\_keys.txt` (file is empty), MoonGen automatically wipes and purges all key data from extension files (`settings.json`, `assets/bklhy9.js`, etc.) on disk.

\---

## ADB mobile IP rotation (optional)

For fresh IPs between accounts using an Android phone:

1. Enable **USB debugging** on the device and connect it via USB.
2. Place the `platform-tools` folder inside the MoonGen directory (next to `moongen.py`).
3. Set `adb.enabled` to `true`. Leave `device\_id` empty to auto-pick the connected device, or set it to a specific serial.

\---

## Project layout

```
moongen.py              # main entry point
humanizer.py            # Discord account humanizer module
proxy\_handler.py        # proxy parsing / rotation
adb\_handler.py          # ADB mobile IP switching
config.json             # your settings (auto-generated)
requirements.txt        # Python dependencies
humanize material/      # names.txt, bio.txt, pronoun.txt, avatars/
input/                  # proxies.txt, nopecha\_keys.txt
output/                 # valid.txt, locked.txt, unverified.txt
wasted\_mails.txt        # auto-saved paid mails that failed (reusable)
nopecha\_ext/            # auto-downloaded captcha-solver extension
```

\---

<p align="center">Made 🌙 by <b>Moon</b> · MoonGen V3</p>

