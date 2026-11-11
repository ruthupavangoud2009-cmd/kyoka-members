# 🌙 KYOKA & NEXUVER 24/7 Cloud Suite — Generator, Unlocker & Member Booster

All-in-one Discord bot controller for running **Discord Account Generator**, **SMS Phone Verifier / Unlocker**, and **Server Joiner / Member Booster** 24/7 on **Render Cloud**.

---

## ✨ Features & Systems

- **📦 Live Stock System (`!stock`)**: Displays real-time stock of phone-verified (SMS verified) and email-verified accounts ready to boost servers, with a visual readiness progress bar.
- **💎 1 Credit = 1 Member Exchange (`!order <invite> <amount>`)**:
  - Exchange credits directly for real Discord server members!
  - **Zero-Loss Guarantee:** Only accounts that actually join your server consume credits. If an account fails to join or gets captcha-gated, your credit is **automatically refunded**!
- **⚡ 24/7 Continuous Restocker (`!autogen on/off/status`)**: Runs in the background on Render Cloud to continuously produce accounts so stock never runs dry.
- **🎁 Daily Free Rewards (`!daily`)**: Every user can claim free credits once every 24 hours.
- **👤 Profile Cards (`!profile`)**: Clean profile card showcasing user rank, credit balance, and total members boosted into servers.
- **🏆 Booster Leaderboard (`!leaderboard` / `!top`)**: Live ranking of top credit holders and server boosters with medals.
- **📖 Super Simple Modular Help (`!help`)**: Interactive dropdown menu with dead-simple Home category and modular sub-categories.
- **🚀 System Start Panel (`!start`)**: Quick launch welcome dashboard with 1-click interactive buttons.
- **👑 Owner Infinite Credits (`!addcredits`, `!removecredits`, `!setcredits`)**: The bot owner has unlimited infinite credits (`♾️`) and can generate credits for any user.
- **🔄 Auto Pipeline (`!pipeline`)**: Links Generator and Unlocker together: automatically sends locked accounts to the phone verifier for automated unlocking.
- **🎭 Profile Humanizer (`!humanize`)**: Applies realistic avatars, bios, pronouns, and HypeSquad badges to accounts.
- **☁️ Render 24/7 Hosting Ready**: Pre-configured `Dockerfile` with virtual display (`Xvfb`), Chromium, and built-in HTTP server to keep the service running 24/7 on Render.

---

## 📜 Bot Commands (Prefix `!` or Slash `/`)

| Command | Usage | Description |
| :--- | :--- | :--- |
| **`!stock`** | `!stock` | Live stock of phone-verified & email-verified accounts ready to boost |
| **`!order`** | `!order <invite> <amount>` | Exchange credits for server members (**1 Credit = 1 Member**, failed joins refunded!) *(aliases: `!boost`, `!exchange`)* |
| **`!autogen`** | `!autogen <on\|off\|status>` | 24/7 background continuous restocker on Render Cloud |
| **`!daily`** | `!daily` | Claim 1 free daily credit every 24 hours |
| **`!profile`** | `!profile [@user]` | View user profile card, credit balance & members boosted |
| **`!leaderboard`** | `!leaderboard` | View top credit holders & server boosters *(alias: `!top`)* |
| **`!help`** | `!help` | Modular categorized help menu with interactive dropdown & buttons |
| **`!start`** | `!start` | System launch panel with credit balance & quick action buttons |
| **`!join`** | `!join <invite> [amount]` | Make accounts join your target server |
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

---

## ☁️ How to Run 24/7 on Render

1. Go to [Render Dashboard](https://dashboard.render.com/) and click **New +** -> **Web Service**.
2. Connect your GitHub repository: `https://github.com/ruthupavangoud2009-cmd/kyoka-members.git`.
3. Choose **Docker** as the Runtime environment.
4. Set Environment Variables in Render:
   - `DISCORD_BOT_TOKEN`: Your Discord bot token
   - `ADMIN_USER_IDS`: Your Discord User ID (gives you infinite credits & owner access)
   - `BOT_PREFIX`: `!`
   - `PORT`: `8080`
   - `RENDER_EXTERNAL_URL`: `https://your-service-name.onrender.com` (for self-pinger keep-alive)
   - `AFHAMXMAILZ_KEY`: Your email API key
   - `NINECAPTCHA_KEY`: Your 9captcha solver key
   - `ONYX_KEY`: Your onyx captcha key
   - `PHONE_SERVICE`: `5sim`
   - `FIVESIM_KEY`: Your 5sim API key
5. Click **Deploy Web Service**! Render will build the Docker container with virtual display and start the bot 24/7.
