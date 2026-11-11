# 🌙 NEXUVER 24/7 Cloud Suite — Generator, Unlocker & Joiner Discord Bot

All-in-one Discord bot controller for running **MoonGen / EVS Discord Account Generator**, **Phone Verifier / Unlocker**, and **Server Joiner / Member Booster** 24/7 on **Render Cloud**.

---

## ✨ Features

- **📖 Super Simple Modular Help**: Interactive dropdown menu (`!help` / `/help`) categorized by topic (Home, Generator, Unlocker, Joiner, Credits, Humanizer, Tools, Downloads).
- **👥 Server Joiner & Booster**: Prefix command `!join <invite> [amount]` and slash `/join` to join target Discord servers with your accounts.
- **💰 Credits Economy System**: Users need credits to generate accounts and join servers; **Bot Owner has infinite credits** and can generate unlimited credits (`!addcredits`, `!removecredits`, `!setcredits`).
- **🚀 System Start Panel**: Quick launch dashboard (`!start`) with interactive buttons.
- **🎮 Full Discord Control**: Works with both prefix (`!`) and slash commands (`/`).
- **☁️ Render 24/7 Hosting Ready**: Pre-configured `Dockerfile` with virtual display (`Xvfb`), Chromium, and built-in HTTP server to keep the service running 24/7 on Render for free.
- **🔄 Auto Pipeline**: Links Generator and Unlocker together. Automatically sends locked accounts to the phone verifier for automated unlocking.
- **📥 Direct File Downloads**: Download `valid.txt`, `unlocked.txt`, `locked.txt` directly through Discord attachments.
- **💳 Balance Checker**: Query remaining SMS balances (5sim, SMSBower, HeroSMS, TigerSMS) in Discord with `/balance` or `!balance`.

---

## 📜 Bot Commands (Prefix `!` or Slash `/`)

| Command | Usage | Description |
| :--- | :--- | :--- |
| **`!help`** | `!help` | Modular categorized help menu with interactive dropdown & buttons |
| **`!start`** | `!start` | System launch panel with credit balance & quick action buttons |
| **`!join`** | `!join <invite> [amount]` | Join accounts to target server (`!join discord.gg/code 5`) |
| **`!gen`** | `!gen <amount> [threads]` | Generate Discord accounts with email & captcha solving |
| **`!pipeline`** | `!pipeline <amount>` | Fully automated pipeline: Gen -> Auto-Unlock |
| **`!unlock`** | `!unlock [threads]` | Phone verify & unlock accounts *(upload a `.txt` file or use `output/locked.txt`)* |
| **`!credits`** | `!credits [@user]` | Check credit balance *(Owner has ♾️ Infinite)* |
| **`!addcredits`** | `!addcredits <@user> <amount>` | **Owner Only**: Generate & give credits to any user |
| **`!removecredits`** | `!removecredits <@user> <amount>` | **Owner Only**: Remove credits from a user |
| **`!setcredits`** | `!setcredits <@user> <amount>` | **Owner Only**: Set user's exact balance |
| **`!transfer`** | `!transfer <@user> <amount>` | Transfer your credits to a friend |
| **`!humanize`** | `!humanize [category] [limit]` | Apply real avatars, bios, pronouns, and HypeSquad badges |
| **`!panel`** | `!panel` | Interactive 1-click button dashboard |
| **`!status`** | `!status` | View uptime, active tasks, latency, and saved token counts |
| **`!check`** | `!check [category]` | Live token health check (Valid / Locked / Dead) |
| **`!download`** | `!download <category>` | Download token files directly as Discord attachments |
| **`!export`** | `!export <format> <category>`| Export formatted as `tokens_only` or `combos` |
| **`!balance`** | `!balance` | Check balances across SMS and Captcha providers |
| **`!stop`** | `!stop [target]` | Cancel active tasks (`gen`, `unlock`, `pipeline`, or `all`) |
| **`!clear`** | `!clear <category>` | Wipes clean any output token file |
