# 🚀 Complete Deployment Guide: 24/7 Render Cloud & Discord Bot Suite

This guide walks you through deploying your **Discord Account Generator & Phone Unlocker** to **Render.com** to run **24/7 continuously** and control everything via **Discord**.

---

## 📋 Table of Contents
1. [Discord Bot Creation & Token](#1-discord-bot-creation--token)
2. [Deploying on Render (Step-by-Step)](#2-deploying-on-render-step-by-step)
3. [Making it Run 24/7 Without Sleeping (UptimeRobot)](#3-making-it-run-247-without-sleeping-uptimerobot)
4. [Discord Bot Commands Reference](#4-discord-bot-commands-reference)
5. [Local Testing (Optional)](#5-local-testing-optional)

---

## 1. Discord Bot Creation & Token

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application** (give it a name like `Nexuver Cloud Bot`).
3. Click on the **Bot** tab on the left menu:
   - Click **Reset Token** and copy your **Bot Token** (keep this safe!).
   - Scroll down to **Privileged Gateway Intents**:
     - ✅ **PRESENCE INTENT** -> ON
     - ✅ **SERVER MEMBERS INTENT** -> ON
     - ✅ **MESSAGE CONTENT INTENT** -> ON
   - Click **Save Changes**.
4. Invite the Bot to your Discord server:
   - Go to **OAuth2** -> **URL Generator**.
   - Under **Scopes**, select: `bot` and `applications.commands`.
   - Under **Bot Permissions**, select: `Administrator` (or *Send Messages*, *Embed Links*, *Attach Files*, *Read Message History*).
   - Copy the generated URL at the bottom, paste it into your browser, and authorize it to your Discord server.

---

## 2. Deploying on Render (Step-by-Step)

Render is a cloud hosting platform that can run your Docker container 24/7.

### Step 2.1: Push to GitHub
1. Create a **Private Repository** on [GitHub](https://github.com/new) (e.g. `nexuver-suite`).
2. Push this folder to your repository:
   ```bash
   git init
   git add .
   git commit -m "Initial 24/7 Discord bot suite"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/nexuver-suite.git
   git push -u origin main
   ```

### Step 2.2: Create Web Service on Render
1. Go to [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** -> **Web Service**.
3. Select **Build and deploy from a Git repository** and connect your GitHub repository.
4. Set the configuration:
   - **Name**: `nexuver-24-7-bot` (or any name you choose)
   - **Region**: Oregon (or closest to you)
   - **Branch**: `main`
   - **Runtime**: **Docker** *(Render detects the included Dockerfile automatically!)*
   - **Instance Type**: **Free**
5. Scroll down to **Environment Variables** and add the following:

| Key | Value | Description |
| :--- | :--- | :--- |
| `DISCORD_BOT_TOKEN` | `YOUR_DISCORD_BOT_TOKEN` | **Required**: Token from Discord Developer Portal |
| `ADMIN_USER_IDS` | `YOUR_DISCORD_USER_ID` | **Recommended**: Only you can run commands (Right click your name in Discord -> Copy User ID) |
| `BOT_PREFIX` | `!` | Command prefix |
| `PORT` | `8080` | Render HTTP port |
| `RENDER_EXTERNAL_URL` | `https://your-service-name.onrender.com` | Your Render public service URL |

*(Optional overrides for keys if you prefer setting them in Render instead of config.json)*:
- `AFHAMXMAILZ_KEY`: Your email API key
- `NINECAPTCHA_KEY`: Your 9captcha key
- `FIVESIM_KEY`: Your 5sim API key
- `ONYX_KEY`: Your Onyx API key
- `PHONE_SERVICE`: `5sim` / `smsbower` / `herosms` / `tigersms`

6. Click **Deploy Web Service**!
   Render will build the Docker container (with Chromium and Xvfb virtual display) and start your bot!

---

## 3. Making it Run 24/7 Without Sleeping (UptimeRobot)

Render's free tier spins down web services after 15 minutes of HTTP inactivity. Because we built an integrated **HTTP Health Server** directly inside `bot.py`, you can keep it awake 24/7 forever for free using UptimeRobot:

1. Sign up for free at [UptimeRobot.com](https://uptimerobot.com).
2. Click **Add New Monitor**:
   - **Monitor Type**: `HTTP(s)`
   - **Friendly Name**: `Nexuver Bot 24/7`
   - **URL (or IP)**: `https://your-service-name.onrender.com/healthz`
   - **Monitoring Interval**: Every `5 minutes`
3. Click **Create Monitor**.

🎉 **Done!** UptimeRobot will ping your bot every 5 minutes, preventing Render from ever sleeping.

---

## 4. Discord Bot Commands Reference

You can use both **Slash Commands** (`/`) and **Prefix Commands** (`!`):

### ⚡ Generation Commands
- `/gen amount:5 threads:1` or `!gen 5`
  Starts generating Discord accounts. Updates the Discord embed with live progress and sends credentials directly to your DMs!
- `/stop gen` or `!stop gen`
  Stops the account generator safely.

### 🔓 Phone Unlocker Commands
- `/unlock threads:5` or `!unlock`
  Verifies phone numbers for accounts that need phone verification.
  - You can **upload a `.txt` file** with tokens in your message!
  - If no file is attached, it automatically reads previously locked tokens from `output/locked.txt`.
- `/stop unlock` or `!stop unlock`
  Stops ongoing phone verification.

### 🔄 Auto Pipeline (Gen + Auto-Unlock)
- `/pipeline amount:5` or `!pipeline 5`
  **The ultimate hands-off command:**
  1. Generates accounts.
  2. Any account that gets locked is immediately sent to the phone verifier.
  3. Produces fully unlocked, phone-verified and email-verified Discord accounts!

### 📥 Token Download & Monitoring
- `/download category:valid` — Download valid email-verified tokens file.
- `/download category:unlocked` — Download phone-unlocked tokens file.
- `/download category:locked` — Download locked tokens file.
- `/status` — View bot uptime, ping, active tasks, and total saved tokens.
- `/balance` — Check remaining balance across 5sim, SMSBower, HeroSMS, TigerSMS.
- `/stop all` — Cancels all running tasks immediately.

---

## 5. Local Testing (Optional)

To test locally on your computer before deploying:

1. Create a `.env` file from `.env.example`:
   ```bash
   cp .env.example .env
   ```
2. Put your `DISCORD_BOT_TOKEN` in `.env`.
3. Run the bot:
   ```bash
   python bot.py
   ```
4. Check your Discord server and try `/help` or `!status`!

