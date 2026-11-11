import sys
import os
import io
import asyncio
import time
import httpx
import discord
from discord import app_commands
from discord.ext import commands

from config import (
    DISCORD_BOT_TOKEN,
    BOT_PREFIX,
    ADMIN_USER_IDS,
    is_admin,
    update_service_key,
    GEN_DIR,
    PORT,
    VALID_TXT,
    LOCKED_TXT,
    UNVERIFIED_TXT,
    INVALID_TXT,
    UNLOCKED_TXT
)
from core.gen_runner import gen_runner
from core.unlock_runner import unlock_runner
from core.pipeline_runner import pipeline_runner
from web_server import start_web_server, set_bot_instance
from keep_alive import run_keep_alive_loop

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents, help_command=None)
set_bot_instance(bot)

START_TIME = time.time()


# ==================== UI HELPER VIEWS ====================
class StopButtonView(discord.ui.View):
    def __init__(self, task_type: str, author_id: int):
        super().__init__(timeout=3600)
        self.task_type = task_type
        self.author_id = author_id

    @discord.ui.button(label="Stop Task", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction.user.id) and interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ You are not authorized to stop this task.", ephemeral=True)

        if self.task_type == "gen":
            gen_runner.stop()
        elif self.task_type == "unlock":
            unlock_runner.stop()
        elif self.task_type == "pipeline":
            pipeline_runner.stop()
        else:
            gen_runner.stop()
            unlock_runner.stop()
            pipeline_runner.stop()

        button.disabled = True
        button.label = "Task Stopped"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"🛑 **{self.task_type.capitalize()} task has been stopped by {interaction.user.mention}.**")


# ==================== HELPER FUNCTIONS ====================
def get_file_line_count(p):
    if not p.exists():
        return 0
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


def format_uptime():
    elapsed = int(time.time() - START_TIME)
    days, rem = divmod(elapsed, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m {seconds}s"
    elif hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    return f"{minutes}m {seconds}s"


# ==================== BOT EVENTS ====================
@bot.event
async def on_ready():
    print("=" * 60)
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Connected to {len(bot.guilds)} guild(s)")
    print("=" * 60)

    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"[SlashCommands] Synced {len(synced)} command(s) globally.")
    except Exception as e:
        print(f"[SlashCommands] Sync error: {e}")

    # Set rich activity
    activity = discord.Activity(type=discord.ActivityType.watching, name="NEXUVER 24/7 Cloud | /help")
    await bot.change_presence(status=discord.Status.online, activity=activity)

    # Start background Web Server for Render Keep-Alive
    try:
        await start_web_server(PORT)
    except Exception as e:
        print(f"[WebServer] Failed to start on port {PORT}: {e}")

    # Start keep-alive self-ping loop
    asyncio.create_task(run_keep_alive_loop())


# ==================== SLASH & PREFIX COMMANDS ====================

# 1. HELP COMMAND
@bot.hybrid_command(name="help", description="Show all available bot commands and usage guide")
async def cmd_help(ctx: commands.Context):
    embed = discord.Embed(
        title="🌙 NEXUVER EVS & UNLOCKER — 24/7 Bot Suite",
        description="Full Discord control for Account Generation, Phone Verification, and Auto-Pipelines on Render Cloud.",
        color=0x7289DA
    )
    embed.add_field(
        name="⚡ Account Generator",
        value="`/gen <amount> [threads]` or `!gen <amount>`\nGenerates Discord accounts with email verification & captcha solving.",
        inline=False
    )
    embed.add_field(
        name="🔓 Phone Unlocker",
        value="`/unlock [threads]` or `!unlock [threads]` *(attach .txt file or paste)*\nVerifies phone numbers to unlock locked Discord accounts.",
        inline=False
    )
    embed.add_field(
        name="🔄 Auto Pipeline",
        value="`/pipeline <amount> [threads]` or `!pipeline <amount>`\nAuto-generates accounts and automatically unlocks any that get locked!",
        inline=False
    )
    embed.add_field(
        name="📊 Monitoring & Stats",
        value="`/status` — Check active jobs, bot uptime, and system info\n`/tokens` — View total saved tokens across all output files\n`/balance` — Check SMS service balances (5sim, SMSBower, etc.)",
        inline=False
    )
    embed.add_field(
        name="📥 File Retrieval & Formatting",
        value="`/download <category>` — Download raw token files\n`/export <format> <category>` — Export as `tokens_only` or `combos`",
        inline=False
    )
    embed.add_field(
        name="🛠️ Management & Utilities",
        value="`/setkey <service> <key>` — Update 5sim, onyx, afham, 9captcha keys dynamically\n`/check <category>` — Live Discord token validity checker\n`/proxies` & `/addproxy` — Check & upload proxy rotation list\n`/join <invite>` — Join a server using your generated accounts",
        inline=False
    )
    embed.add_field(
        name="🛑 Task Control",
        value="`/stop [type]` — Stop running `gen`, `unlock`, `pipeline`, or `all` tasks",
        inline=False
    )
    embed.set_footer(text=f"Prefix: {BOT_PREFIX} | Cloud Hosting: Render 24/7 | Nexuver Marketplace")
    await ctx.send(embed=embed)


# 2. STATUS COMMAND
@bot.hybrid_command(name="status", description="Check current bot status, active tasks, and saved tokens")
async def cmd_status(ctx: commands.Context):
    embed = discord.Embed(
        title="🌐 System Status & Active Tasks",
        color=0x2ecc71 if not (gen_runner.is_running or unlock_runner.is_running) else 0xf39c12
    )
    embed.add_field(name="⏱️ Uptime", value=format_uptime(), inline=True)
    embed.add_field(name="📶 Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="☁️ Hosting", value="Render Cloud (24/7 Active)", inline=True)

    # Active states
    gen_state = "🟢 Running" if gen_runner.is_running else "⚪ Idle"
    unlock_state = "🟢 Running" if unlock_runner.is_running else "⚪ Idle"
    pipe_state = "🟢 Running" if pipeline_runner.is_running else "⚪ Idle"

    embed.add_field(
        name="⚙️ Tasks",
        value=f"**Generator:** {gen_state}\n**Unlocker:** {unlock_state}\n**Pipeline:** {pipe_state}",
        inline=False
    )

    # Tokens count
    embed.add_field(
        name="📁 Saved Token Counts",
        value=(
            f"✅ **Valid:** {get_file_line_count(VALID_TXT)}\n"
            f"🔓 **Unlocked:** {get_file_line_count(UNLOCKED_TXT)}\n"
            f"🔒 **Locked:** {get_file_line_count(LOCKED_TXT)}\n"
            f"⚠️ **Unverified:** {get_file_line_count(UNVERIFIED_TXT)}\n"
            f"❌ **Invalid:** {get_file_line_count(INVALID_TXT)}"
        ),
        inline=False
    )
    await ctx.send(embed=embed)


# 3. GENERATOR COMMAND
@bot.hybrid_command(name="gen", description="Start generating Discord accounts")
@app_commands.describe(amount="Number of accounts to generate (e.g. 5)", threads="Worker threads (default 1)")
async def cmd_gen(ctx: commands.Context, amount: int = 1, threads: int = 1):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied**: You are not authorized to run this command.", ephemeral=True)

    if gen_runner.is_running:
        return await ctx.send("⚠️ **Generator is already running!** Use `/stop gen` to cancel it first.", ephemeral=True)

    if amount < 1:
        return await ctx.send("❌ Amount must be at least 1.", ephemeral=True)

    embed = discord.Embed(
        title="🚀 Generator Started",
        description=f"Starting generation of **{amount}** account(s) with **{threads}** thread(s)...",
        color=0x9b59b6
    )
    embed.add_field(name="Progress", value=f"0 / {amount}", inline=True)
    embed.add_field(name="Valid", value="0", inline=True)
    embed.add_field(name="Locked", value="0", inline=True)
    embed.set_footer(text="Running on Render 24/7 | Updates live")

    view = StopButtonView(task_type="gen", author_id=ctx.author.id)
    msg = await ctx.send(embed=embed, view=view)

    # Callback when an account is created
    def on_event(event_type, data):
        if event_type == "account_saved":
            # Send private DM to user with token if valid/locked
            token_str = data.get("token", "")
            email_str = data.get("email", "")
            pwd_str = data.get("password", "")
            status_str = data.get("status", "")

            # Non-blocking DM notification
            async def send_dm():
                try:
                    dm_embed = discord.Embed(
                        title=f"🎉 Account Created [{status_str}]",
                        color=0x2ecc71 if status_str == "VALID" else 0xe67e22
                    )
                    dm_embed.add_field(name="Email", value=f"`{email_str}`", inline=False)
                    dm_embed.add_field(name="Password", value=f"`{pwd_str}`", inline=False)
                    dm_embed.add_field(name="Token", value=f"||{token_str}||", inline=False)
                    dm_embed.add_field(name="Combo", value=f"```{email_str}:{pwd_str}:{token_str}```", inline=False)
                    await ctx.author.send(embed=dm_embed)
                except Exception:
                    pass
            asyncio.create_task(send_dm())

    # Live update loop for the Discord embed
    async def update_embed_loop():
        while gen_runner.is_running:
            await asyncio.sleep(4)
            st = gen_runner.get_stats()
            up_embed = discord.Embed(
                title="⚡ Account Generator In Progress",
                description=f"Target: **{st['target']}** accounts | Elapsed: **{st['elapsed_seconds']}s**",
                color=0x3498db
            )
            up_embed.add_field(name="Progress", value=f"{st['created']} / {st['target']}", inline=True)
            up_embed.add_field(name="✅ Valid", value=str(st['valid']), inline=True)
            up_embed.add_field(name="🔒 Locked", value=str(st['locked']), inline=True)
            up_embed.add_field(name="⚠️ Unverified", value=str(st['unverified']), inline=True)
            up_embed.add_field(name="❌ Invalid", value=str(st['invalid']), inline=True)
            try:
                await msg.edit(embed=up_embed, view=view)
            except Exception:
                pass

    update_task = asyncio.create_task(update_embed_loop())

    try:
        results = await gen_runner.start(target=amount, threads=threads, callback=on_event)
        done_embed = discord.Embed(
            title="🏁 Generator Finished!",
            color=0x2ecc71
        )
        done_embed.add_field(name="Total Created", value=str(results.get("total", 0)), inline=True)
        done_embed.add_field(name="✅ Valid", value=str(results.get("valid", 0)), inline=True)
        done_embed.add_field(name="🔒 Locked", value=str(results.get("locked", 0)), inline=True)
        done_embed.add_field(name="⚠️ Unverified", value=str(results.get("unverified", 0)), inline=True)
        done_embed.add_field(name="❌ Invalid", value=str(results.get("invalid", 0)), inline=True)
        done_embed.set_footer(text="Use /download valid to download tokens file.")
        await msg.edit(embed=done_embed, view=None)
    except Exception as e:
        err_embed = discord.Embed(
            title="❌ Generator Stopped / Error",
            description=f"Details: `{e}`",
            color=0xe74c3c
        )
        await msg.edit(embed=err_embed, view=None)
    finally:
        update_task.cancel()


# 4. UNLOCKER COMMAND
@bot.hybrid_command(name="unlock", description="Unlock locked Discord accounts using Phone Verification")
@app_commands.describe(threads="Concurrent verification threads (default 5)")
async def cmd_unlock(ctx: commands.Context, threads: int = 5):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied**: You are not authorized to run this command.", ephemeral=True)

    if unlock_runner.is_running:
        return await ctx.send("⚠️ **Unlocker is already running!** Use `/stop unlock` first.", ephemeral=True)

    # Check if a file was uploaded with the command message
    token_lines = []
    if ctx.message.attachments:
        attachment = ctx.message.attachments[0]
        if attachment.filename.endswith(".txt"):
            content = await attachment.read()
            token_lines = content.decode("utf-8", errors="ignore").splitlines()

    # If no file attached, fall back to output/locked.txt
    if not token_lines:
        if LOCKED_TXT.exists():
            with open(LOCKED_TXT, "r", encoding="utf-8", errors="ignore") as f:
                token_lines = [l.strip() for l in f if l.strip()]

    if not token_lines:
        return await ctx.send(
            "❌ **No tokens to verify!**\nPlease attach a `.txt` file containing tokens (`email:pass:token` or `token`), or generate accounts first to populate `output/locked.txt`."
        )

    embed = discord.Embed(
        title="🔓 Phone Verifier Started",
        description=f"Loaded **{len(token_lines)}** tokens to verify with **{threads}** thread(s)...",
        color=0xf1c40f
    )
    embed.add_field(name="Total", value=str(len(token_lines)), inline=True)
    embed.add_field(name="Successful", value="0", inline=True)
    embed.add_field(name="Failed", value="0", inline=True)

    view = StopButtonView(task_type="unlock", author_id=ctx.author.id)
    msg = await ctx.send(embed=embed, view=view)

    # Live update loop
    async def update_embed_loop():
        while unlock_runner.is_running:
            await asyncio.sleep(4)
            st = unlock_runner.get_stats()
            up_embed = discord.Embed(
                title="🔓 Phone Verifying In Progress",
                description=f"Total: **{st['total']}** | Elapsed: **{st['elapsed_seconds']}s**",
                color=0xf39c12
            )
            up_embed.add_field(name="✅ Successful", value=str(st['successful']), inline=True)
            up_embed.add_field(name="❌ Failed", value=str(st['failed']), inline=True)
            up_embed.add_field(name="Progress", value=f"{st['successful'] + st['failed']} / {st['total']}", inline=True)
            try:
                await msg.edit(embed=up_embed, view=view)
            except Exception:
                pass

    update_task = asyncio.create_task(update_embed_loop())

    try:
        results = await unlock_runner.verify_tokens(token_lines=token_lines, threads=threads)
        done_embed = discord.Embed(
            title="🏁 Phone Verification Complete!",
            color=0x2ecc71
        )
        done_embed.add_field(name="Total", value=str(results.get("total", 0)), inline=True)
        done_embed.add_field(name="✅ Successfully Unlocked", value=str(results.get("successful", 0)), inline=True)
        done_embed.add_field(name="❌ Failed", value=str(results.get("failed", 0)), inline=True)
        done_embed.set_footer(text="Use /download unlocked to get your unlocked tokens file.")
        await msg.edit(embed=done_embed, view=None)
    except Exception as e:
        err_embed = discord.Embed(
            title="❌ Unlocker Error",
            description=f"Details: `{e}`",
            color=0xe74c3c
        )
        await msg.edit(embed=err_embed, view=None)
    finally:
        update_task.cancel()


# 5. PIPELINE COMMAND (GEN + AUTO-UNLOCK)
@bot.hybrid_command(name="pipeline", description="Auto Pipeline: Generate accounts and automatically unlock locked ones")
@app_commands.describe(amount="Number of accounts to generate", threads="Generation threads (default 1)")
async def cmd_pipeline(ctx: commands.Context, amount: int = 1, threads: int = 1):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied**: You are not authorized to run this command.", ephemeral=True)

    if pipeline_runner.is_running or gen_runner.is_running or unlock_runner.is_running:
        return await ctx.send("⚠️ Another generation or unlock task is already active. Please stop it first.", ephemeral=True)

    embed = discord.Embed(
        title="🔄 Auto Pipeline Started",
        description=f"Target: **{amount}** accounts.\nAny account requiring phone verification will be unlocked automatically via SMS!",
        color=0x34495e
    )
    view = StopButtonView(task_type="pipeline", author_id=ctx.author.id)
    msg = await ctx.send(embed=embed, view=view)

    async def update_pipeline_loop():
        while pipeline_runner.is_running:
            await asyncio.sleep(4)
            st = pipeline_runner.get_stats()
            up_embed = discord.Embed(
                title="🔄 Auto Pipeline Active",
                description=f"Target: **{st['target']}** | Elapsed: **{st['elapsed_seconds']}s**",
                color=0x1abc9c
            )
            up_embed.add_field(name="Generated", value=f"{st['generated']} / {st['target']}", inline=True)
            up_embed.add_field(name="✅ Valid Directly", value=str(st['valid']), inline=True)
            up_embed.add_field(name="🔓 Auto-Unlocked", value=str(st['unlocked_success']), inline=True)
            up_embed.add_field(name="❌ Unlock Failed", value=str(st['unlocked_failed']), inline=True)
            try:
                await msg.edit(embed=up_embed, view=view)
            except Exception:
                pass

    update_task = asyncio.create_task(update_pipeline_loop())

    try:
        await pipeline_runner.start(target=amount, threads=threads)
        st = pipeline_runner.get_stats()
        fin_embed = discord.Embed(
            title="🎉 Pipeline Completed Successfully!",
            color=0x2ecc71
        )
        fin_embed.add_field(name="Total Generated", value=str(st['generated']), inline=True)
        fin_embed.add_field(name="Directly Valid", value=str(st['valid']), inline=True)
        fin_embed.add_field(name="Unlocked with Phone", value=str(st['unlocked_success']), inline=True)
        fin_embed.add_field(name="Net Working Accounts", value=str(st['valid'] + st['unlocked_success']), inline=False)
        await msg.edit(embed=fin_embed, view=None)
    except Exception as e:
        err_embed = discord.Embed(title="❌ Pipeline Stopped", description=f"`{e}`", color=0xe74c3c)
        await msg.edit(embed=err_embed, view=None)
    finally:
        update_task.cancel()


# 6. DOWNLOAD COMMAND
@bot.hybrid_command(name="download", description="Download generated or unlocked token files directly")
@app_commands.describe(category="Which token file to download: valid, unlocked, locked, unverified, or invalid")
@app_commands.choices(category=[
    app_commands.Choice(name="Valid Accounts (Email Verified)", value="valid"),
    app_commands.Choice(name="Unlocked Accounts (Phone Verified)", value="unlocked"),
    app_commands.Choice(name="Locked Accounts", value="locked"),
    app_commands.Choice(name="Unverified Accounts", value="unverified"),
    app_commands.Choice(name="Invalid Accounts", value="invalid"),
])
async def cmd_download(ctx: commands.Context, category: str = "valid"):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied**.", ephemeral=True)

    mapping = {
        "valid": VALID_TXT,
        "unlocked": UNLOCKED_TXT,
        "locked": LOCKED_TXT,
        "unverified": UNVERIFIED_TXT,
        "invalid": INVALID_TXT
    }
    file_path = mapping.get(category.lower())
    if not file_path or not file_path.exists() or file_path.stat().st_size == 0:
        return await ctx.send(f"⚠️ No tokens found in `{category}.txt` yet.", ephemeral=True)

    try:
        discord_file = discord.File(str(file_path), filename=f"{category}_tokens.txt")
        count = get_file_line_count(file_path)
        await ctx.send(
            content=f"📥 **Here is your `{category}.txt` file** ({count} tokens):",
            file=discord_file,
            ephemeral=True
        )
    except Exception as e:
        await ctx.send(f"❌ Error uploading file: {e}", ephemeral=True)


# 7. BALANCE COMMAND
@bot.hybrid_command(name="balance", description="Check balances of configured SMS and Captcha providers")
async def cmd_balance(ctx: commands.Context):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied**.", ephemeral=True)

    await ctx.defer(ephemeral=True)
    balances = unlock_runner.get_balances()

    embed = discord.Embed(title="💳 Provider Balances", color=0x2ecc71)
    if not balances:
        embed.description = "No active SMS or Captcha balances found or keys not configured."
    else:
        for provider, bal in balances.items():
            embed.add_field(name=provider, value=f"`{bal}`", inline=False)
    await ctx.send(embed=embed, ephemeral=True)


# 8. STOP COMMAND
@bot.hybrid_command(name="stop", description="Stop any active generator, unlocker, or pipeline task")
@app_commands.describe(target="Task to stop: all, gen, unlock, or pipeline")
@app_commands.choices(target=[
    app_commands.Choice(name="All Running Tasks", value="all"),
    app_commands.Choice(name="Generator Task", value="gen"),
    app_commands.Choice(name="Unlocker Task", value="unlock"),
    app_commands.Choice(name="Pipeline Task", value="pipeline"),
])
async def cmd_stop(ctx: commands.Context, target: str = "all"):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied**.", ephemeral=True)

    stopped = []
    if target in ("all", "gen") and gen_runner.is_running:
        gen_runner.stop()
        stopped.append("Generator")
    if target in ("all", "unlock") and unlock_runner.is_running:
        unlock_runner.stop()
        stopped.append("Unlocker")
    if target in ("all", "pipeline") and pipeline_runner.is_running:
        pipeline_runner.stop()
        stopped.append("Pipeline")

    if stopped:
        await ctx.send(f"🛑 **Stopped task(s):** {', '.join(stopped)}.")
    else:
        await ctx.send("ℹ️ No active tasks were running.", ephemeral=True)


# 9. SETKEY COMMAND (DYNAMIC CONFIG)
@bot.hybrid_command(name="setkey", description="Set or update an API key dynamically (5sim, onyx, afham, 9captcha)")
@app_commands.describe(service="Service to configure", key="API key or value")
@app_commands.choices(service=[
    app_commands.Choice(name="5sim SMS Key", value="5sim"),
    app_commands.Choice(name="Onyx Captcha Key", value="onyx"),
    app_commands.Choice(name="9captcha Key", value="ninecaptcha"),
    app_commands.Choice(name="AfhamXMailz Key", value="afhamxmailz"),
    app_commands.Choice(name="SMSBower Key", value="smsbower"),
    app_commands.Choice(name="HeroSMS Key", value="herosms"),
    app_commands.Choice(name="Active Phone Service", value="phone_service"),
])
async def cmd_setkey(ctx: commands.Context, service: str, key: str):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied**.", ephemeral=True)
    ok = update_service_key(service, key)
    if ok:
        await ctx.send(f"✅ Successfully updated **{service}** key! It is now active.", ephemeral=True)
    else:
        await ctx.send(f"❌ Failed to update key for `{service}`.", ephemeral=True)


# 10. TOKEN HEALTH CHECKER
@bot.hybrid_command(name="check", description="Check live Discord token validity for saved accounts")
@app_commands.describe(category="Which token list to check: valid, locked, or unlocked")
@app_commands.choices(category=[
    app_commands.Choice(name="Valid Accounts (valid.txt)", value="valid"),
    app_commands.Choice(name="Unlocked Accounts (unlocked.txt)", value="unlocked"),
    app_commands.Choice(name="Locked Accounts (locked.txt)", value="locked"),
])
async def cmd_check(ctx: commands.Context, category: str = "valid"):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied**.", ephemeral=True)

    mapping = {
        "valid": VALID_TXT,
        "unlocked": UNLOCKED_TXT,
        "locked": LOCKED_TXT
    }
    file_p = mapping.get(category.lower())
    if not file_p or not file_p.exists() or file_p.stat().st_size == 0:
        return await ctx.send(f"⚠️ No tokens in `{category}.txt` to check.", ephemeral=True)

    await ctx.defer()
    with open(file_p, "r", encoding="utf-8", errors="ignore") as f:
        lines = [l.strip() for l in f if l.strip()]

    tokens = []
    for l in lines:
        parts = l.split(":")
        tokens.append(parts[2] if len(parts) >= 3 else parts[0])

    alive = 0
    phone_locked = 0
    dead = 0

    async with httpx.AsyncClient(timeout=8) as client:
        for t in tokens[:100]:
            try:
                r = await client.get("https://discord.com/api/v9/users/@me", headers={"Authorization": t})
                if r.status_code == 200:
                    d = r.json() or {}
                    req_act = str(d.get("required_action") or "").upper()
                    if "PHONE" in req_act:
                        phone_locked += 1
                    else:
                        alive += 1
                elif r.status_code == 403:
                    phone_locked += 1
                else:
                    dead += 1
            except Exception:
                dead += 1

    embed = discord.Embed(title=f"🔎 Token Health Check: `{category}.txt`", color=0x3498db)
    embed.add_field(name="Total Checked", value=str(min(len(tokens), 100)), inline=True)
    embed.add_field(name="🟢 Alive / Working", value=str(alive), inline=True)
    embed.add_field(name="🔒 Phone-Locked", value=str(phone_locked), inline=True)
    embed.add_field(name="❌ Dead / Invalid", value=str(dead), inline=True)
    await ctx.send(embed=embed)


# 11. PROXIES STATUS & ADD
@bot.hybrid_command(name="proxies", description="View loaded proxy statistics")
async def cmd_proxies(ctx: commands.Context):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied**.", ephemeral=True)

    proxy_file = GEN_DIR / "input" / "proxies.txt"
    count = get_file_line_count(proxy_file)
    embed = discord.Embed(title="🌐 Proxies Status", color=0x9b59b6)
    embed.add_field(name="Loaded Proxies", value=str(count), inline=True)
    embed.add_field(name="File", value="`input/proxies.txt`", inline=True)
    embed.set_footer(text="Use /addproxy or upload a proxies.txt to add more.")
    await ctx.send(embed=embed)


@bot.hybrid_command(name="addproxy", description="Add proxies directly to the proxy rotation list")
@app_commands.describe(proxy="Single proxy string (e.g. user:pass@host:port or host:port)")
async def cmd_addproxy(ctx: commands.Context, proxy: str = None):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied**.", ephemeral=True)

    proxy_file = GEN_DIR / "input" / "proxies.txt"
    proxy_file.parent.mkdir(parents=True, exist_ok=True)

    added = 0
    if ctx.message.attachments:
        att = ctx.message.attachments[0]
        content = await att.read()
        lines = content.decode("utf-8", errors="ignore").splitlines()
        with open(proxy_file, "a", encoding="utf-8") as f:
            for l in lines:
                if l.strip():
                    f.write(l.strip() + "\n")
                    added += 1
    elif proxy:
        with open(proxy_file, "a", encoding="utf-8") as f:
            f.write(proxy.strip() + "\n")
            added = 1

    total = get_file_line_count(proxy_file)
    await ctx.send(f"✅ Added **{added}** proxy(ies). Total active proxies: **{total}**.", ephemeral=True)


# 12. SERVER JOINER
@bot.hybrid_command(name="join", description="Join a Discord server with your valid/unlocked accounts")
@app_commands.describe(invite="Server invite code or link (e.g. abcdef or discord.gg/abcdef)", limit="Maximum tokens to join")
async def cmd_join(ctx: commands.Context, invite: str, limit: int = 5):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied**.", ephemeral=True)

    code = invite.strip().split("/")[-1]
    tokens = []
    for fp in (UNLOCKED_TXT, VALID_TXT):
        if fp.exists():
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.strip().split(":")
                    if len(parts) >= 3:
                        tokens.append(parts[2])
                    elif parts:
                        tokens.append(parts[0])

    if not tokens:
        return await ctx.send("❌ No valid or unlocked tokens found to join with.", ephemeral=True)

    tokens = tokens[:max(1, limit)]
    await ctx.send(f"🚀 Attempting to join `{code}` with **{len(tokens)}** account(s)...")

    joined = 0
    failed = 0
    async with httpx.AsyncClient(timeout=10) as client:
        for t in tokens:
            try:
                r = await client.post(
                    f"https://discord.com/api/v9/invites/{code}",
                    headers={"Authorization": t, "Content-Type": "application/json"},
                    json={}
                )
                if r.status_code in (200, 204):
                    joined += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
            await asyncio.sleep(1.5)

    embed = discord.Embed(title="🏁 Server Join Results", color=0x2ecc71 if joined > 0 else 0xe74c3c)
    embed.add_field(name="Invite", value=f"`{code}`", inline=True)
    embed.add_field(name="✅ Joined", value=str(joined), inline=True)
    embed.add_field(name="❌ Failed/Captcha", value=str(failed), inline=True)
    await ctx.send(embed=embed)


# 13. EXPORT TOKENS
@bot.hybrid_command(name="export", description="Export tokens formatted as raw tokens or full credentials")
@app_commands.describe(category="Token category", format="Export format")
@app_commands.choices(category=[
    app_commands.Choice(name="Valid Accounts", value="valid"),
    app_commands.Choice(name="Unlocked Accounts", value="unlocked"),
    app_commands.Choice(name="Locked Accounts", value="locked"),
], format=[
    app_commands.Choice(name="Tokens Only (token per line)", value="tokens_only"),
    app_commands.Choice(name="Full Combos (email:pass:token)", value="combos"),
])
async def cmd_export(ctx: commands.Context, category: str = "valid", format: str = "tokens_only"):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied**.", ephemeral=True)

    mapping = {"valid": VALID_TXT, "unlocked": UNLOCKED_TXT, "locked": LOCKED_TXT}
    fp = mapping.get(category.lower())
    if not fp or not fp.exists() or fp.stat().st_size == 0:
        return await ctx.send(f"⚠️ No tokens in `{category}.txt` to export.", ephemeral=True)

    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
        lines = [l.strip() for l in f if l.strip()]

    output_lines = []
    if format == "tokens_only":
        for l in lines:
            parts = l.split(":")
            output_lines.append(parts[2] if len(parts) >= 3 else parts[0])
    else:
        output_lines = lines

    data_bytes = "\n".join(output_lines).encode("utf-8")
    discord_file = discord.File(io.BytesIO(data_bytes), filename=f"{category}_{format}.txt")
    await ctx.send(
        content=f"📤 **Exported {len(output_lines)} tokens** ({format}):",
        file=discord_file,
        ephemeral=True
    )


# ==================== MAIN LAUNCHER ====================
def main():
    if not DISCORD_BOT_TOKEN:
        print("\n" + "=" * 65)
        print(" [ERROR] DISCORD_BOT_TOKEN is not set!")
        print(" Please provide your bot token via environment variable or in .env:")
        print(" DISCORD_BOT_TOKEN=your_token_here")
        print("=" * 65 + "\n")
        sys.exit(1)

    print("[Launcher] Starting NEXUVER Discord Bot Suite...")
    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()

