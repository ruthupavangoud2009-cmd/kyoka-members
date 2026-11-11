# 🌙 NEXUVER 24/7 Cloud Suite — Generator & Unlocker Discord Bot

All-in-one Discord bot controller for running **MoonGen / EVS Discord Account Generator** and **Phone Verifier / Unlocker** 24/7 on **Render Cloud**.

---

## ✨ Features

- **🎮 Full Discord Control**: Run everything through slash commands (`/gen`, `/unlock`, `/pipeline`, `/status`, `/download`, `/balance`, `/stop`).
- **☁️ Render 24/7 Hosting Ready**: Pre-configured `Dockerfile` with virtual display (`Xvfb`), Chromium, and built-in HTTP server to keep the service running 24/7 on Render for free.
- **🔄 Auto Pipeline**: Links Generator and Unlocker together. Automatically sends locked accounts to the phone verifier for automated unlocking.
- **📥 Direct File Downloads**: Download `valid.txt`, `unlocked.txt`, `locked.txt` directly through Discord attachments.
- **🔒 Admin Protection**: Restrict commands to designated Discord User IDs (`ADMIN_USER_IDS`).
- **💳 Balance Checker**: Query remaining SMS balances (5sim, SMSBower, HeroSMS, TigerSMS) in Discord with `/balance`.

---

## 🚀 Quick Setup

See **[DEPLOY_GUIDE.md](DEPLOY_GUIDE.md)** for full step-by-step instructions.

1. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and set your `DISCORD_BOT_TOKEN`.
2. **Deploy to Render**:
   - Push repository to GitHub.
   - Create a Web Service on Render selecting **Docker** runtime.
   - Add environment variables (`DISCORD_BOT_TOKEN`, `ADMIN_USER_IDS`).
3. **Keep Alive 24/7**:
   - Set up a free monitor at [UptimeRobot](https://uptimerobot.com) pointing to `https://your-app.onrender.com/healthz`.

---

## 📜 Bot Commands

| Command | Description |
| :--- | :--- |
| `/gen <amount> [threads]` | Start generating Discord accounts with email & captcha verification |
| `/unlock [threads]` | Phone verify & unlock accounts (upload a `.txt` file or use `output/locked.txt`) |
| `/pipeline <amount>` | Fully automated pipeline: Gen -> Auto-Unlock |
| `/status` | View uptime, active tasks, latency, and saved token counts |
| `/download <category>` | Download token files directly as Discord attachments |
| `/balance` | Check balances across SMS and Captcha providers |
| `/stop [target]` | Cancel active tasks (`gen`, `unlock`, `pipeline`, or `all`) |
| `/help` | Detailed command list and help |

