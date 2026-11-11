import sys
import os
import io
import asyncio
import time
import httpx
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List, Dict, Any

from config import (
    DISCORD_BOT_TOKEN,
    BOT_PREFIX,
    ADMIN_USER_IDS,
    is_admin,
    update_service_key,
    update_phone_config,
    toggle_setting,
    get_full_config_summary,
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
from core.credits_manager import credits_manager
from core.stock_manager import stock_manager
from core.joiner import join_server_task, clean_invite_code
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


class DashboardPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Gen 1", style=discord.ButtonStyle.primary, emoji="⚡", row=0)
    async def btn_gen1(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction.user.id):
            return await interaction.response.send_message("❌ Unauthorized", ephemeral=True)
        if gen_runner.is_running:
            return await interaction.response.send_message("⚠️ Generator already active!", ephemeral=True)
        await interaction.response.send_message("⚡ Starting 1 account generation...", ephemeral=True)
        asyncio.create_task(gen_runner.start(target=1, threads=1))

    @discord.ui.button(label="Gen 5", style=discord.ButtonStyle.primary, emoji="🚀", row=0)
    async def btn_gen5(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction.user.id):
            return await interaction.response.send_message("❌ Unauthorized", ephemeral=True)
        if gen_runner.is_running:
            return await interaction.response.send_message("⚠️ Generator already active!", ephemeral=True)
        await interaction.response.send_message("🚀 Starting 5 accounts generation...", ephemeral=True)
        asyncio.create_task(gen_runner.start(target=5, threads=1))

    @discord.ui.button(label="Unlock Locked", style=discord.ButtonStyle.success, emoji="🔓", row=0)
    async def btn_unlock(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction.user.id):
            return await interaction.response.send_message("❌ Unauthorized", ephemeral=True)
        if unlock_runner.is_running:
            return await interaction.response.send_message("⚠️ Unlocker already active!", ephemeral=True)
        token_lines = []
        if LOCKED_TXT.exists():
            with open(LOCKED_TXT, "r", encoding="utf-8", errors="ignore") as f:
                token_lines = [l.strip() for l in f if l.strip()]
        if not token_lines:
            return await interaction.response.send_message("⚠️ No tokens in locked.txt to unlock.", ephemeral=True)
        await interaction.response.send_message(f"🔓 Verifying {len(token_lines)} locked accounts...", ephemeral=True)
        asyncio.create_task(unlock_runner.verify_tokens(token_lines, threads=5))

    @discord.ui.button(label="Pipeline 5", style=discord.ButtonStyle.success, emoji="🔄", row=0)
    async def btn_pipe(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction.user.id):
            return await interaction.response.send_message("❌ Unauthorized", ephemeral=True)
        if pipeline_runner.is_running or gen_runner.is_running or unlock_runner.is_running:
            return await interaction.response.send_message("⚠️ Another task is active!", ephemeral=True)
        await interaction.response.send_message("🔄 Starting Auto-Pipeline for 5 accounts...", ephemeral=True)
        asyncio.create_task(pipeline_runner.start(target=5, threads=1))

    @discord.ui.button(label="Stock", style=discord.ButtonStyle.secondary, emoji="📦", row=0)
    async def btn_stock(self, interaction: discord.Interaction, button: discord.ui.Button):
        st = stock_manager.get_stock_summary()
        emb = discord.Embed(
            title="📦 Live Server Stock (1 Account = 100 Servers)",
            description=(
                f"• **Ready Server Stock:** **{st['remaining_member_capacity']:,}** Server Joins\n"
                f"• **Unique Accounts:** `{st['total_accounts']:,}` *(1 account can join 100 servers)*\n"
                f"• **Exchange Rate:** 1 Credit = 1 Server Member"
            ),
            color=0x2ecc71
        )
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @discord.ui.button(label="Status", style=discord.ButtonStyle.secondary, emoji="📊", row=1)
    async def btn_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        emb = discord.Embed(title="🌐 Cloud System Status", color=0x2ecc71)
        emb.add_field(name="Uptime", value=format_uptime(), inline=True)
        emb.add_field(name="Ping", value=f"{round(bot.latency * 1000)}ms", inline=True)
        emb.add_field(name="Valid", value=str(get_file_line_count(VALID_TXT)), inline=True)
        emb.add_field(name="Unlocked", value=str(get_file_line_count(UNLOCKED_TXT)), inline=True)
        emb.add_field(name="Locked", value=str(get_file_line_count(LOCKED_TXT)), inline=True)
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @discord.ui.button(label="Balances", style=discord.ButtonStyle.secondary, emoji="💳", row=1)
    async def btn_bal(self, interaction: discord.Interaction, button: discord.ui.Button):
        bals = unlock_runner.get_balances()
        emb = discord.Embed(title="💳 Provider Balances", color=0xf1c40f)
        for k, v in bals.items():
            emb.add_field(name=k, value=f"`{v}`", inline=False)
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @discord.ui.button(label="Auto-Gen 24/7", style=discord.ButtonStyle.secondary, emoji="⚙️", row=1)
    async def btn_autogen(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction.user.id):
            return await interaction.response.send_message("❌ Unauthorized (Owner only)", ephemeral=True)
        if gen_runner.autogen_enabled:
            gen_runner.stop_autogen()
            await interaction.response.send_message("⏹️ **24/7 Auto-Generator Stopped.** Background restocker paused.", ephemeral=True)
        else:
            gen_runner.start_autogen(batch_size=1, cooldown_seconds=30)
            await interaction.response.send_message("🚀 **24/7 Auto-Generator Activated!** Restocking continuously in the background.", ephemeral=True)

    @discord.ui.button(label="Download", style=discord.ButtonStyle.secondary, emoji="📥", row=1)
    async def btn_dl(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction.user.id):
            return await interaction.response.send_message("❌ Unauthorized", ephemeral=True)
        if not VALID_TXT.exists() or VALID_TXT.stat().st_size == 0:
            return await interaction.response.send_message("⚠️ No valid tokens yet.", ephemeral=True)
        f = discord.File(str(VALID_TXT), filename="valid_tokens.txt")
        await interaction.response.send_message(file=f, ephemeral=True)

    @discord.ui.button(label="Stop All", style=discord.ButtonStyle.danger, emoji="⏹️", row=1)
    async def btn_stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction.user.id):
            return await interaction.response.send_message("❌ Unauthorized", ephemeral=True)
        gen_runner.stop()
        unlock_runner.stop()
        pipeline_runner.stop()
        await interaction.response.send_message("🛑 All tasks stopped.", ephemeral=True)


# ==================== MODULAR HELP SYSTEM ====================
def get_help_embed(category: str, user_id: int) -> discord.Embed:
    cat = category.lower().strip()
    bal = credits_manager.format_credits(user_id)
    is_adm = is_admin(user_id)

    if cat in ("home", "main"):
        embed = discord.Embed(
            title="🏠 KYOKA & NEXUVER — QUICK START",
            description="**Automated Discord Generator & Member Booster running 24/7 on Render.**\nSimple, clean, and modular.",
            color=0x5865F2
        )
        embed.add_field(
            name="💎 Your Status",
            value=(
                f"• **Balance:** `{bal}`\n"
                f"• **Exchange Rate:** `1 Credit = 1 Member Joined`\n"
                f"• **24/7 Restocker:** `{'🟢 Running (Auto-Restocking)' if gen_runner.autogen_enabled else '⚪ Standby'}`\n"
                f"• **Role:** `{'👑 Owner / Admin' if is_adm else '👤 Regular User'}`"
            ),
            inline=False
        )
        embed.add_field(
            name="⚡ Top 5 Commands (Simple & Fast)",
            value=(
                f"📦 `{BOT_PREFIX}stock` — View live accounts available to join\n"
                f"🎁 `{BOT_PREFIX}daily` — Claim free credit every 24 hours\n"
                f"👥 `{BOT_PREFIX}order <invite> <count>` — Add members to your server\n"
                f"⚡ `{BOT_PREFIX}gen <count>` — Generate new accounts\n"
                f"👤 `{BOT_PREFIX}profile` — View your credits & booster stats"
            ),
            inline=False
        )
        embed.add_field(
            name="📂 Detailed Categories",
            value="Select any category from the **dropdown menu below** to view all commands.",
            inline=False
        )
        embed.set_footer(text=f"Prefix: {BOT_PREFIX} • Slash / commands also supported")
        return embed

    elif "stock" in cat or "exchange" in cat:
        embed = discord.Embed(
            title="📦 Category: Stock & Member Exchange",
            description="Exchange credits directly for real Discord server members.",
            color=0x2ecc71
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}stock`",
            value=(
                "View real-time stock of phone-verified and email-verified accounts ready to join.\n"
                "• Shows readiness bar, phone verified count, and auto-restocker state."
            ),
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}order <invite> <amount>` *(or {BOT_PREFIX}boost / {BOT_PREFIX}join)*",
            value=(
                "Exchange credits for Discord server members.\n"
                "• **Rate:** `1 Credit = 1 Member Joined`\n"
                "• **Guarantee:** Only successful joins cost credits. Any failed joins are **instantly refunded**!\n"
                f"• *Example:* `{BOT_PREFIX}order discord.gg/mycode 10`"
            ),
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}autogen <on|off|status>`",
            value=(
                "Controls the 24/7 continuous account restocker on Render Cloud.\n"
                "• Continuously generates accounts in the background so stock never runs out.\n"
                f"• *Example:* `{BOT_PREFIX}autogen on` or `{BOT_PREFIX}autogen status`"
            ),
            inline=False
        )
        embed.set_footer(text=f"Prefix: {BOT_PREFIX} • 1 Credit = 1 Member")
        return embed

    elif "generator" in cat or "gen" in cat:
        embed = discord.Embed(
            title="⚡ Category: Account Generator",
            description="Create Discord accounts automatically with email verification & captcha solving.",
            color=0x9b59b6
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}gen <amount> [threads]`",
            value=(
                "Generate Discord accounts.\n"
                "• **Cost:** 1 credit per account *(Free for Owner)*\n"
                "• **Credentials:** Sent directly to your private DMs!\n"
                f"• *Example:* `{BOT_PREFIX}gen 5` or `/gen amount:5 threads:1`"
            ),
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}pipeline <amount> [threads]`",
            value=(
                "**Ultimate Auto-Pipeline**: Generates accounts, and if any account gets locked, it immediately unlocks it with phone verification!\n"
                f"• *Example:* `{BOT_PREFIX}pipeline 5` or `/pipeline amount:5`"
            ),
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}stop gen`",
            value="Safely stops the active generator task.",
            inline=False
        )
        embed.set_footer(text=f"Prefix: {BOT_PREFIX} | Nexuver Marketplace")
        return embed

    elif "unlock" in cat or "phone" in cat:
        embed = discord.Embed(
            title="🔓 Category: Phone Unlocker & Verifier",
            description="Unlock locked Discord accounts using real SMS numbers (5sim, SMSBower, HeroSMS).",
            color=0xf1c40f
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}unlock [threads]`",
            value=(
                "Starts phone verification on locked accounts.\n"
                "• **File:** Attach a `.txt` file with tokens, or it reads `output/locked.txt`.\n"
                f"• *Example:* `{BOT_PREFIX}unlock 5` or `/unlock threads:5`"
            ),
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}balance`",
            value="Check your live SMS balance across 5sim, SMSBower, HeroSMS, and TigerSMS.",
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}phone_config <service> <country> [operator]`",
            value=(
                "Change SMS country & operator on the fly.\n"
                f"• *Example:* `{BOT_PREFIX}phone_config 5sim indonesia virtual51`"
            ),
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}stop unlock`",
            value="Safely cancels any active phone unlocking task.",
            inline=False
        )
        return embed

    elif "join" in cat or "server" in cat:
        embed = discord.Embed(
            title="👥 Category: Server Joiner & Booster",
            description="Exchange credits to make real accounts join your Discord server! (1 Credit = 1 Member).",
            color=0x2ecc71
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}order <invite> <amount>` / `{BOT_PREFIX}join <invite> [amount]`",
            value=(
                "Make accounts join your target Discord server.\n"
                "• **Rate:** `1 Credit = 1 Member Joined`\n"
                "• **Guarantee:** Only successful joins cost credits. Failed joins are **automatically refunded**!\n"
                "• **Supports:** Full invite links (`discord.gg/code`) or raw codes (`code`).\n"
                f"• *Example:* `{BOT_PREFIX}order discord.gg/example 10`"
            ),
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}stock`",
            value="View live accounts ready in stock, lifetime joins, and 100x member boost capacity.",
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}restock [attach .txt file]` *(or {BOT_PREFIX}addstock)*",
            value="Upload accounts via `.txt` file attachment (`email:pass:token` or tokens) to add directly to stock.",
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}start`",
            value="Open the system start panel with interactive quick action buttons.",
            inline=False
        )
        return embed

    elif "credit" in cat:
        embed = discord.Embed(
            title="💰 Category: Credits System",
            description="Manage, claim, and transfer credits. 1 Credit = 1 Server Member.",
            color=0xe67e22
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}credits [@user]`",
            value="Check your own or another user's credit balance. *(Owner has ♾️ Infinite)*.",
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}daily`",
            value="Claim 1 free credit every 24 hours. (1 Credit = 1 Member!).",
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}profile [@user]`",
            value="View detailed booster stats and total server members joined.",
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}leaderboard` *(or {BOT_PREFIX}top)*",
            value="View the top credit holders and top server boosters.",
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}transfer <@user> <amount>`",
            value=f"Transfer credits from your balance to a friend.\n• *Example:* `{BOT_PREFIX}transfer @user 10`",
            inline=False
        )
        embed.add_field(
            name="👑 OWNER COMMANDS (Infinite Credit Generation)",
            value=(
                f"`{BOT_PREFIX}addcredits <@user> <amount>` — Add credits to a user\n"
                f"`{BOT_PREFIX}removecredits <@user> <amount>` — Remove credits from a user\n"
                f"`{BOT_PREFIX}setcredits <@user> <amount>` — Set user's exact balance\n"
                "*(Owners bypass all credit deductions completely)*"
            ),
            inline=False
        )
        return embed

    elif "human" in cat:
        embed = discord.Embed(
            title="🎭 Category: Profile Humanizer",
            description="Make accounts look 100% human with realistic profiles.",
            color=0xe91e63
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}humanize [category] [limit]`",
            value=(
                "Applies real avatars, bios, pronouns, and HypeSquad badges to saved accounts.\n"
                f"• *Example:* `{BOT_PREFIX}humanize valid 5`\n"
                "• *Example:* `/humanize category:unlocked limit:10`"
            ),
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}toggle humanizer on/off`",
            value="Toggle automatic humanization during account generation.",
            inline=False
        )
        return embed

    elif "tool" in cat or "config" in cat:
        embed = discord.Embed(
            title="🛠️ Category: Tools & Configuration",
            description="Settings, live health checks, and proxy management.",
            color=0x3498db
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}panel`",
            value="Opens the interactive 1-click button dashboard.",
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}status`",
            value="View bot ping, uptime, active workers, and token counts.",
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}config`",
            value="Displays all active settings and API keys.",
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}setkey <service> <key>`",
            value="Change API keys (`5sim`, `onyx`, `afham`, `9cap`) on the fly.",
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}check [category]`",
            value="Scan tokens to see if they are Alive, Phone-Locked, or Dead.",
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}proxies` / `{BOT_PREFIX}addproxy`",
            value="View proxy stats or add new proxies to the pool.",
            inline=False
        )
        return embed

    elif "download" in cat or "file" in cat or "export" in cat:
        embed = discord.Embed(
            title="📥 Category: Downloads & Exports",
            description="Download and format your generated accounts.",
            color=0x1abc9c
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}download <category>`",
            value=(
                "Download raw token files as `.txt` attachments.\n"
                "• Categories: `valid`, `unlocked`, `locked`, `unverified`\n"
                f"• *Example:* `{BOT_PREFIX}download valid`"
            ),
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}export <format> <category>`",
            value=(
                "Export tokens formatted as `tokens_only` or `combos`.\n"
                f"• *Example:* `{BOT_PREFIX}export tokens_only valid`"
            ),
            inline=False
        )
        embed.add_field(
            name=f"`{BOT_PREFIX}clear <category>`",
            value=f"Wipes clean any token file (e.g. `{BOT_PREFIX}clear invalid`).",
            inline=False
        )
        return embed

    return get_help_embed("home", user_id)


class HelpSelect(discord.ui.Select):
    def __init__(self, user_id: int, current_cat: str = "Home"):
        self.user_id = user_id
        options = [
            discord.SelectOption(label="Home", emoji="🏠", description="Overview, quick start & status", default=(current_cat == "Home")),
            discord.SelectOption(label="Stock & Exchange", emoji="📦", description="!stock, !order (1 Credit = 1 Member)", default=(current_cat == "Stock & Exchange")),
            discord.SelectOption(label="Account Generator", emoji="⚡", description="!gen, !pipeline, !autogen", default=(current_cat == "Account Generator")),
            discord.SelectOption(label="Phone Unlocker", emoji="🔓", description="!unlock, !balance, !phone_config", default=(current_cat == "Phone Unlocker")),
            discord.SelectOption(label="Server Joiner", emoji="👥", description="!order, !join, !start", default=(current_cat == "Server Joiner")),
            discord.SelectOption(label="Credits System", emoji="💰", description="!credits, !daily, !profile, !top", default=(current_cat == "Credits System")),
            discord.SelectOption(label="Profile Humanizer", emoji="🎭", description="!humanize avatars & bios", default=(current_cat == "Profile Humanizer")),
            discord.SelectOption(label="Tools & Config", emoji="🛠️", description="!panel, !config, !setkey, !check", default=(current_cat == "Tools & Config")),
            discord.SelectOption(label="Downloads & Files", emoji="📥", description="!download, !export, !clear", default=(current_cat == "Downloads & Files")),
        ]
        super().__init__(placeholder="📂 Select a category to view commands...", min_values=1, max_values=1, options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        embed = get_help_embed(selected, interaction.user.id)
        view = ModularHelpView(interaction.user.id, current_cat=selected)
        await interaction.response.edit_message(embed=embed, view=view)


class ModularHelpView(discord.ui.View):
    def __init__(self, user_id: int, current_cat: str = "Home"):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.add_item(HelpSelect(user_id, current_cat))

    @discord.ui.button(label="Home", style=discord.ButtonStyle.primary, emoji="🏠", row=1)
    async def btn_home(self, interaction: discord.Interaction, button: discord.ui.Button):
        emb = get_help_embed("Home", interaction.user.id)
        view = ModularHelpView(interaction.user.id, "Home")
        await interaction.response.edit_message(embed=emb, view=view)

    @discord.ui.button(label="Stock", style=discord.ButtonStyle.secondary, emoji="📦", row=1)
    async def btn_stock(self, interaction: discord.Interaction, button: discord.ui.Button):
        emb = get_help_embed("Stock & Exchange", interaction.user.id)
        view = ModularHelpView(interaction.user.id, "Stock & Exchange")
        await interaction.response.edit_message(embed=emb, view=view)

    @discord.ui.button(label="Gen", style=discord.ButtonStyle.secondary, emoji="⚡", row=1)
    async def btn_gen(self, interaction: discord.Interaction, button: discord.ui.Button):
        emb = get_help_embed("Account Generator", interaction.user.id)
        view = ModularHelpView(interaction.user.id, "Account Generator")
        await interaction.response.edit_message(embed=emb, view=view)

    @discord.ui.button(label="Join", style=discord.ButtonStyle.secondary, emoji="👥", row=1)
    async def btn_join(self, interaction: discord.Interaction, button: discord.ui.Button):
        emb = get_help_embed("Server Joiner", interaction.user.id)
        view = ModularHelpView(interaction.user.id, "Server Joiner")
        await interaction.response.edit_message(embed=emb, view=view)

    @discord.ui.button(label="Credits", style=discord.ButtonStyle.secondary, emoji="💰", row=1)
    async def btn_credits(self, interaction: discord.Interaction, button: discord.ui.Button):
        emb = get_help_embed("Credits System", interaction.user.id)
        view = ModularHelpView(interaction.user.id, "Credits System")
        await interaction.response.edit_message(embed=emb, view=view)


class StartPanelView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id

    @discord.ui.button(label="Gen 1", style=discord.ButtonStyle.primary, emoji="⚡", row=0)
    async def btn_gen(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not credits_manager.can_afford(interaction.user.id, 1):
            return await interaction.response.send_message("❌ Insufficient credits! Contact the owner to get credits.", ephemeral=True)
        if gen_runner.is_running:
            return await interaction.response.send_message("⚠️ Generator already active!", ephemeral=True)
        credits_manager.deduct_credits(interaction.user.id, 1)
        await interaction.response.send_message("⚡ Starting 1 account generation...", ephemeral=True)
        asyncio.create_task(gen_runner.start(target=1, threads=1))

    @discord.ui.button(label="Stock", style=discord.ButtonStyle.secondary, emoji="📦", row=0)
    async def btn_stock(self, interaction: discord.Interaction, button: discord.ui.Button):
        st = stock_manager.get_stock_summary()
        emb = discord.Embed(
            title="📦 Live Server Stock (1 Account = 100 Servers)",
            description=(
                f"• **Ready Server Stock:** **{st['remaining_member_capacity']:,}** Server Joins\n"
                f"• **Unique Accounts:** `{st['total_accounts']:,}` *(1 account can join 100 servers)*\n"
                f"• **Exchange Rate:** 1 Credit = 1 Server Member"
            ),
            color=0x2ecc71
        )
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @discord.ui.button(label="Order Members", style=discord.ButtonStyle.primary, emoji="👥", row=0)
    async def btn_join(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"💡 Type `{BOT_PREFIX}order <invite_code> <amount>` (e.g. `{BOT_PREFIX}order discord.gg/example 5`) to exchange credits for members!", ephemeral=True)

    @discord.ui.button(label="My Credits", style=discord.ButtonStyle.secondary, emoji="💰", row=0)
    async def btn_credits(self, interaction: discord.Interaction, button: discord.ui.Button):
        bal = credits_manager.format_credits(interaction.user.id)
        emb = discord.Embed(title="💰 Your Credit Balance", description=f"You currently have: **{bal}**\n*Exchange rate: 1 Credit = 1 Server Member*", color=0xf1c40f)
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @discord.ui.button(label="Daily", style=discord.ButtonStyle.success, emoji="🎁", row=1)
    async def btn_daily(self, interaction: discord.Interaction, button: discord.ui.Button):
        success, msg, new_bal = credits_manager.claim_daily(interaction.user.id, reward=1)
        emb = discord.Embed(
            title="🎁 Daily Credit Claim",
            description=msg,
            color=0x2ecc71 if success else 0xe74c3c
        )
        emb.set_footer(text=f"Total Balance: {credits_manager.format_credits(interaction.user.id)}")
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @discord.ui.button(label="Profile", style=discord.ButtonStyle.secondary, emoji="👤", row=1)
    async def btn_profile(self, interaction: discord.Interaction, button: discord.ui.Button):
        stats = credits_manager.get_user_stats(interaction.user.id)
        emb = discord.Embed(title=f"👤 User Profile — {interaction.user.name}", color=0x9b59b6)
        emb.add_field(name="Role", value=stats["role"], inline=True)
        emb.add_field(name="Balance", value=str(stats["credits"]), inline=True)
        emb.add_field(name="Members Boosted", value=f"{stats['orders']:,} members", inline=True)
        emb.set_footer(text="Exchange: 1 Credit = 1 Member")
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @discord.ui.button(label="Help", style=discord.ButtonStyle.secondary, emoji="📖", row=1)
    async def btn_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        emb = get_help_embed("Home", interaction.user.id)
        view = ModularHelpView(interaction.user.id, "Home")
        await interaction.response.send_message(embed=emb, view=view, ephemeral=True)

    @discord.ui.button(label="Panel", style=discord.ButtonStyle.success, emoji="🎮", row=1)
    async def btn_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        emb = discord.Embed(
            title="🎮 NEXUVER CLOUD DASHBOARD",
            description="Click buttons below for instant 1-click execution. Runs 24/7 on Render.",
            color=0x9b59b6
        )
        emb.add_field(name="⚡ Generator", value="Create accounts with auto-captcha & email verification", inline=True)
        emb.add_field(name="🔓 Unlocker", value="Phone verify locked accounts via SMS", inline=True)
        emb.add_field(name="🔄 Pipeline", value="Generate and automatically unlock locked accounts", inline=True)
        emb.set_footer(text="Nexuver 24/7 Cloud Suite | Interactive Controller")
        await interaction.response.send_message(embed=emb, view=DashboardPanelView(), ephemeral=True)


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

# 1. HELP COMMAND (MODULAR INTERACTIVE)
@bot.hybrid_command(name="help", description="Show the modular interactive help menu with categories")
async def cmd_help(ctx: commands.Context):
    embed = get_help_embed("home", ctx.author.id)
    view = ModularHelpView(ctx.author.id, "Home")
    await ctx.send(embed=embed, view=view)


# 1.1 START COMMAND (WELCOME & LAUNCH PANEL)
@bot.hybrid_command(name="start", description="System start: welcome panel, credit balance & quick buttons")
async def cmd_start(ctx: commands.Context):
    bal = credits_manager.format_credits(ctx.author.id)
    role_badge = "👑 Owner / Admin" if is_admin(ctx.author.id) else "👤 Member"
    embed = discord.Embed(
        title="🚀 NEXUVER 24/7 CLOUD SYSTEM — STARTED",
        description=(
            f"Hello {ctx.author.mention}! The system is active and running 24/7 on Render.\n\n"
            f"• **Your Role:** `{role_badge}`\n"
            f"• **Your Credits:** `{bal}`\n"
            f"• **Bot Prefix:** `{BOT_PREFIX}` *(Slash `/` also active)*\n\n"
            "Use the quick action buttons below or type `!help` for the modular guide."
        ),
        color=0x5865F2
    )
    embed.add_field(
        name="⚡ Quick Commands",
        value=(
            f"`{BOT_PREFIX}gen 5` — Generate 5 accounts\n"
            f"`{BOT_PREFIX}join <invite> 5` — Join accounts to server\n"
            f"`{BOT_PREFIX}credits` — View your credit balance\n"
            f"`{BOT_PREFIX}help` — Interactive modular help menu"
        ),
        inline=False
    )
    embed.set_footer(text="Nexuver 24/7 Cloud Suite • Fast & Reliable")
    await ctx.send(embed=embed, view=StartPanelView(ctx.author.id))


# 1.2 CREDITS BALANCE COMMAND
@bot.hybrid_command(name="credits", description="Check your or another user's credit balance")
@app_commands.describe(user="User to check (optional, defaults to yourself)")
async def cmd_credits(ctx: commands.Context, user: Optional[discord.User] = None):
    target = user or ctx.author
    bal = credits_manager.format_credits(target.id)
    role = "👑 Owner" if is_admin(target.id) else "👤 Member"
    embed = discord.Embed(title="💰 Credit Balance", color=0xf1c40f)
    embed.add_field(name="User", value=target.mention, inline=True)
    embed.add_field(name="Role", value=role, inline=True)
    embed.add_field(name="Balance", value=f"**{bal}**", inline=False)
    if is_admin(target.id):
        embed.set_footer(text="Owners have unlimited infinite credits to generate accounts & boost servers.")
    await ctx.send(embed=embed)


# 1.3 OWNER: ADD CREDITS COMMAND (INFINITE GENERATION)
@bot.hybrid_command(name="addcredits", description="Add credits to a user (Owner only)")
@app_commands.describe(user="User to give credits to", amount="Number of credits to add")
async def cmd_addcredits(ctx: commands.Context, user: discord.User, amount: int):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied**: Only the bot owner can generate credits.", ephemeral=True)
    if amount <= 0:
        return await ctx.send("❌ Amount must be greater than 0.", ephemeral=True)
    new_bal = credits_manager.add_credits(user.id, amount)
    embed = discord.Embed(title="💰 Credits Generated", color=0x2ecc71)
    embed.description = f"Added **{amount:,}** credits to {user.mention}!\nNew Balance: **{new_bal:,} credits**"
    await ctx.send(embed=embed)


# 1.4 OWNER: REMOVE CREDITS COMMAND
@bot.hybrid_command(name="removecredits", description="Remove credits from a user (Owner only)")
@app_commands.describe(user="User to remove credits from", amount="Number of credits to remove")
async def cmd_removecredits(ctx: commands.Context, user: discord.User, amount: int):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied**: Only the bot owner can remove credits.", ephemeral=True)
    new_bal = credits_manager.remove_credits(user.id, amount)
    embed = discord.Embed(title="💰 Credits Removed", color=0xe74c3c)
    embed.description = f"Removed **{amount:,}** credits from {user.mention}.\nNew Balance: **{new_bal:,} credits**"
    await ctx.send(embed=embed)


# 1.5 OWNER: SET CREDITS COMMAND
@bot.hybrid_command(name="setcredits", description="Set a user's exact credits balance (Owner only)")
@app_commands.describe(user="Target user", amount="Exact credits amount")
async def cmd_setcredits(ctx: commands.Context, user: discord.User, amount: int):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied**: Only the bot owner can set credits.", ephemeral=True)
    new_bal = credits_manager.set_credits(user.id, amount)
    embed = discord.Embed(title="💰 Credits Set", color=0x3498db)
    embed.description = f"Set {user.mention}'s balance to **{new_bal:,} credits**."
    await ctx.send(embed=embed)


# 1.6 USER: TRANSFER CREDITS COMMAND
@bot.hybrid_command(name="transfer", description="Transfer your credits to another user")
@app_commands.describe(user="Recipient user", amount="Number of credits to transfer")
async def cmd_transfer(ctx: commands.Context, user: discord.User, amount: int):
    success, msg = credits_manager.transfer(ctx.author.id, user.id, amount)
    if success:
        embed = discord.Embed(title="💸 Credits Transferred", description=f"Transferred **{amount:,}** credits to {user.mention}!", color=0x2ecc71)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ Transfer failed: {msg}", ephemeral=True)


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
    if amount < 1:
        return await ctx.send("❌ Amount must be at least 1.", ephemeral=True)

    # Credit affordability check
    if not credits_manager.can_afford(ctx.author.id, amount):
        cur_bal = credits_manager.format_credits(ctx.author.id)
        return await ctx.send(
            f"❌ **Insufficient Credits!** You need **{amount}** credits to generate {amount} accounts, but you only have **{cur_bal}**.\nContact the bot owner to get credits!",
            ephemeral=True
        )

    if gen_runner.is_running:
        return await ctx.send("⚠️ **Generator is already running!** Use `/stop gen` to cancel it first.", ephemeral=True)

    # Deduct credits (Owner/admins are untouched)
    credits_manager.deduct_credits(ctx.author.id, amount)

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
@app_commands.describe(
    invite="Server invite code or link (e.g. discord.gg/code)",
    amount="How many accounts to join (default 5)",
    delay="Seconds delay between joins (default 2.5)"
)
async def cmd_join(ctx: commands.Context, invite: str, amount: int = 5, delay: float = 2.5):
    amount = max(1, amount)
    delay = max(1.0, min(delay, 30.0))

    # Check credits
    if not credits_manager.can_afford(ctx.author.id, amount):
        cur_bal = credits_manager.format_credits(ctx.author.id)
        return await ctx.send(
            f"❌ **Insufficient Credits!** You need **{amount}** credits to join {amount} accounts, but you have **{cur_bal}**.\nContact the bot owner to get credits!",
            ephemeral=True
        )

    clean_code = clean_invite_code(invite)

    # Collect tokens that haven't joined this server yet and haven't hit 100 uses
    tokens_to_use = stock_manager.get_available_tokens_for_server(clean_code, amount)
    if not tokens_to_use:
        st = stock_manager.get_stock_summary()
        return await ctx.send(
            f"❌ **No Available Accounts for this Server!**\n"
            f"All **{st['total_accounts']}** accounts in stock have either already joined `{clean_code}` or have reached their 100-server limit.\n"
            f"Use `{BOT_PREFIX}restock` to add more accounts!",
            ephemeral=True
        )

    actual_count = len(tokens_to_use)
    if actual_count < amount:
        await ctx.send(
            f"ℹ️ **Note:** You requested **{amount}** members, but only **{actual_count}** accounts in stock have not joined `{clean_code}` yet. Proceeding with **{actual_count}** members.",
            ephemeral=True
        )

    # Deduct credits (Owners/admins are untouched)
    credits_manager.deduct_credits(ctx.author.id, actual_count)

    start_embed = discord.Embed(
        title="👥 Server Joiner Started",
        description=(
            f"Attempting to join **{actual_count}** account(s) into `{clean_code}` (pacing: ~{delay}s)...\n"
            "💎 **Guarantee:** `1 Credit = 1 Member Joined`. Any failed joins are automatically refunded!"
        ),
        color=0x3498db
    )
    start_embed.add_field(name="Target Server", value="Connecting...", inline=True)
    start_embed.add_field(name="Accounts Ordered", value=str(actual_count), inline=True)
    start_embed.add_field(name="Paced Delay", value=f"~{delay}s", inline=True)
    start_embed.set_footer(text=f"Credits Remaining: {credits_manager.format_credits(ctx.author.id)}")
    msg = await ctx.send(embed=start_embed)

    results = await join_server_task(invite_code=clean_code, tokens=tokens_to_use, delay=delay)

    joined_count = results.get("joined", 0)
    failed_count = actual_count - joined_count

    # Record usage for successful tokens (up to 100 uses per account)
    for tok in results.get("successful_tokens", []):
        stock_manager.record_join(tok, clean_code)

    # 1 Credit = 1 Member Rule: Refund failed joins & record successful ones
    if failed_count > 0:
        credits_manager.refund_credits(ctx.author.id, failed_count)
    if joined_count > 0:
        credits_manager.record_members_joined(ctx.author.id, joined_count)

    done_embed = discord.Embed(
        title="🏁 Server Join Complete!",
        description=f"Exchange Result: **{joined_count}** server member(s) joined successfully.",
        color=0x2ecc71 if joined_count > 0 else 0xe74c3c
    )
    done_embed.add_field(name="Server", value=f"`{results.get('server_name')}`", inline=True)
    done_embed.add_field(name="Invite Code", value=f"`{clean_code}`", inline=True)
    done_embed.add_field(name="✅ Joined", value=f"**{joined_count}** members", inline=True)
    done_embed.add_field(name="🔒 Captcha Gated", value=str(results.get("captcha", 0)), inline=True)
    done_embed.add_field(name="❌ Dead/Invalid", value=str(results.get("invalid", 0)), inline=True)
    done_embed.add_field(name="⚠️ Other Failed", value=str(results.get("failed", 0)), inline=True)
    done_embed.add_field(
        name="💰 Credits Summary",
        value=f"• Deducted: `{joined_count}`\n• Refunded: `{failed_count}`\n• Your Balance: `{credits_manager.format_credits(ctx.author.id)}`",
        inline=False
    )
    done_embed.set_footer(text="1 Credit = 1 Member Guarantee • Kyoka Cloud Suite")
    await msg.edit(embed=done_embed)


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


# 14. INTERACTIVE DASHBOARD PANEL
@bot.hybrid_command(name="panel", description="Display the interactive Cloud Control Dashboard Panel")
async def cmd_panel(ctx: commands.Context):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied**.", ephemeral=True)
    embed = discord.Embed(
        title="🎮 NEXUVER CLOUD DASHBOARD",
        description="Click buttons below for instant 1-click execution. Runs 24/7 on Render.",
        color=0x9b59b6
    )
    embed.add_field(name="⚡ Generator", value="Create accounts with auto-captcha & email verification", inline=True)
    embed.add_field(name="🔓 Unlocker", value="Phone verify locked accounts via SMS", inline=True)
    embed.add_field(name="🔄 Pipeline", value="Generate and automatically unlock locked accounts", inline=True)
    embed.set_footer(text="Nexuver 24/7 Cloud Suite | Interactive Controller")
    await ctx.send(embed=embed, view=DashboardPanelView())


# 15. CONFIG VIEWER
@bot.hybrid_command(name="config", description="View active configuration across Generator and Unlocker")
async def cmd_config(ctx: commands.Context):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied**.", ephemeral=True)
    cfg = get_full_config_summary()
    embed = discord.Embed(title="⚙️ Active System Configuration", color=0x3498db)
    embed.add_field(name="📧 Email Provider", value=f"`{cfg.get('email_provider')}`", inline=True)
    embed.add_field(name="🧩 9captcha", value=f"`{cfg.get('ninecaptcha')}`", inline=True)
    embed.add_field(name="🧩 NopeCHA", value=f"`{cfg.get('nopecha')}`", inline=True)
    embed.add_field(name="📱 Phone Service", value=f"`{cfg.get('phone_service')}`", inline=True)
    embed.add_field(name="🛡️ Captcha Solver", value=f"`{cfg.get('captcha_solver')}`", inline=True)
    embed.add_field(name="🌐 Proxies", value=f"`{'Enabled' if cfg.get('proxy_enabled') else 'Disabled'}`", inline=True)
    embed.add_field(name="👤 Humanizer", value=f"`{'Enabled' if cfg.get('humanizer_enabled') else 'Disabled'}`", inline=True)
    embed.add_field(name="🌍 5sim Country", value=f"`{cfg.get('fivesim_country')} ({cfg.get('fivesim_operator')})`", inline=True)
    embed.add_field(name="⏱️ Cooldown", value=f"`{cfg.get('cooldown')}s`", inline=True)
    await ctx.send(embed=embed, ephemeral=True)


# 16. TOGGLE FEATURES
@bot.hybrid_command(name="toggle", description="Toggle features on/off (humanizer, hypesquad, proxies, avatar)")
@app_commands.describe(feature="Feature to toggle", state="Enable or Disable")
@app_commands.choices(feature=[
    app_commands.Choice(name="Humanizer (Avatars, Bios, Names)", value="humanizer"),
    app_commands.Choice(name="HypeSquad Badge", value="hypesquad"),
    app_commands.Choice(name="Custom Avatars", value="avatar"),
    app_commands.Choice(name="Proxy Rotation", value="proxy"),
    app_commands.Choice(name="9captcha Solver", value="ninecaptcha"),
], state=[
    app_commands.Choice(name="Enable (ON)", value="on"),
    app_commands.Choice(name="Disable (OFF)", value="off"),
])
async def cmd_toggle(ctx: commands.Context, feature: str, state: str):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied**.", ephemeral=True)
    is_on = state.lower() == "on"
    ok = toggle_setting(feature, is_on)
    if ok:
        await ctx.send(f"✅ Successfully set **{feature}** to **{'ON' if is_on else 'OFF'}**.", ephemeral=True)
    else:
        await ctx.send(f"❌ Failed to toggle `{feature}`.", ephemeral=True)


# 17. PHONE CONFIGURATION
@bot.hybrid_command(name="phone_config", description="Configure SMS service country and operator")
@app_commands.describe(service="SMS service (5sim, smsbower, herosms, tigersms)", country="Country name or code", operator="Operator (optional, e.g. virtual51)")
async def cmd_phone_config(ctx: commands.Context, service: str, country: str, operator: str = ""):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied**.", ephemeral=True)
    ok = update_phone_config(service, country, operator)
    if ok:
        await ctx.send(f"✅ Updated **{service}** to country `{country}`" + (f" and operator `{operator}`." if operator else "."), ephemeral=True)
    else:
        await ctx.send(f"❌ Failed to update phone config.", ephemeral=True)


# 18. HUMANIZE TOKENS DIRECTLY
@bot.hybrid_command(name="humanize", description="Humanize accounts: add avatars, bios, pronouns, and HypeSquad")
@app_commands.describe(category="Which accounts to humanize", limit="How many accounts to humanize")
@app_commands.choices(category=[
    app_commands.Choice(name="Valid Accounts (valid.txt)", value="valid"),
    app_commands.Choice(name="Unlocked Accounts (unlocked.txt)", value="unlocked"),
])
async def cmd_humanize(ctx: commands.Context, category: str = "valid", limit: int = 5):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied**.", ephemeral=True)

    fp = VALID_TXT if category == "valid" else UNLOCKED_TXT
    if not fp.exists() or fp.stat().st_size == 0:
        return await ctx.send(f"⚠️ No tokens in `{category}.txt`.", ephemeral=True)

    await ctx.defer()
    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
        lines = [l.strip() for l in f if l.strip()]

    tokens = []
    for l in lines:
        parts = l.split(":")
        tokens.append(parts[2] if len(parts) >= 3 else parts[0])

    tokens = tokens[:max(1, limit)]
    await ctx.send(f"🎭 Humanizing **{len(tokens)}** account(s)...")

    if str(GEN_DIR) not in sys.path:
        sys.path.insert(0, str(GEN_DIR))
    try:
        import humanizer as hz
        import json
        gen_cfg_path = GEN_DIR / "config.json"
        with open(gen_cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        succ = 0
        fail = 0
        for idx, t in enumerate(tokens, 1):
            try:
                ok = await asyncio.to_thread(hz.humanize_token, token=t, proxy=None, config=cfg)
                if ok:
                    succ += 1
                else:
                    fail += 1
            except Exception:
                fail += 1
            await asyncio.sleep(1.0)

        embed = discord.Embed(title="🎭 Humanization Complete", color=0x2ecc71 if succ > 0 else 0xe74c3c)
        embed.add_field(name="✅ Successful", value=str(succ), inline=True)
        embed.add_field(name="❌ Warnings/Failed", value=str(fail), inline=True)
        embed.add_field(name="Features Applied", value="Avatars, Bios, Pronouns, HypeSquad", inline=False)
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Humanizer error: {e}")


# 19. CLEAR TOKENS FILE
@bot.hybrid_command(name="clear", description="Clear tokens from an output file")
@app_commands.describe(category="Which file to clear")
@app_commands.choices(category=[
    app_commands.Choice(name="Invalid Accounts (invalid.txt)", value="invalid"),
    app_commands.Choice(name="Locked Accounts (locked.txt)", value="locked"),
    app_commands.Choice(name="Unverified Accounts (unverified.txt)", value="unverified"),
    app_commands.Choice(name="Valid Accounts (valid.txt)", value="valid"),
    app_commands.Choice(name="Unlocked Accounts (unlocked.txt)", value="unlocked"),
])
async def cmd_clear(ctx: commands.Context, category: str):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied**.", ephemeral=True)
    mapping = {
        "valid": VALID_TXT,
        "unlocked": UNLOCKED_TXT,
        "locked": LOCKED_TXT,
        "unverified": UNVERIFIED_TXT,
        "invalid": INVALID_TXT
    }
    fp = mapping.get(category.lower())
    if fp and fp.exists():
        open(fp, "w").close()
        await ctx.send(f"🗑️ Cleared `{category}.txt` successfully.", ephemeral=True)
    else:
        await ctx.send("⚠️ File already empty.", ephemeral=True)


# 20. ORDER / BOOST / EXCHANGE (1 CREDIT = 1 MEMBER)
@bot.hybrid_command(name="order", aliases=["boost", "exchange"], description="Exchange credits for Discord server members (1 Credit = 1 Member)")
@app_commands.describe(
    invite="Discord server invite code or link (e.g. discord.gg/example or example)",
    amount="Number of server members to order",
    delay="Seconds delay between joins (default 2.5)"
)
async def cmd_order(ctx: commands.Context, invite: str, amount: int = 1, delay: float = 2.5):
    """Convenient alias for cmd_join with 1 credit = 1 member guarantee."""
    await cmd_join(ctx, invite=invite, amount=amount, delay=delay)


# 20. RESTOCK / IMPORT ACCOUNTS (TXT FILE OR TEXT)
@bot.hybrid_command(name="restock", aliases=["addstock", "importstock", "loadstock"], description="Add accounts to stock via .txt file attachment or text")
@app_commands.describe(file="Text file (.txt) with accounts (email:pass:token or token per line)", accounts="Or paste accounts directly")
async def cmd_restock(ctx: commands.Context, file: Optional[discord.Attachment] = None, accounts: Optional[str] = None):
    if not is_admin(ctx.author.id):
        return await ctx.send("❌ **Access Denied.** Only bot admins/owners can restock accounts.", ephemeral=True)

    raw_data = ""
    if file:
        try:
            content_bytes = await file.read()
            raw_data = content_bytes.decode("utf-8", errors="ignore")
        except Exception as e:
            return await ctx.send(f"❌ Failed to read attached file: {e}", ephemeral=True)
    elif accounts:
        raw_data = accounts
    elif ctx.message.attachments:
        try:
            content_bytes = await ctx.message.attachments[0].read()
            raw_data = content_bytes.decode("utf-8", errors="ignore")
        except Exception as e:
            return await ctx.send(f"❌ Failed to read attachment: {e}", ephemeral=True)
    else:
        return await ctx.send(
            "❌ **No accounts provided!**\n"
            "Please attach a `.txt` file containing accounts or paste them.\n"
            f"*Example:* `{BOT_PREFIX}restock` (with `.txt` file attached) or `{BOT_PREFIX}restock accounts:email:pass:token`",
            ephemeral=True
        )

    added, duplicates, total = stock_manager.add_accounts(raw_data, VALID_TXT)
    if added == 0 and duplicates == 0:
        return await ctx.send("❌ No valid tokens found in the provided input. Each line should contain `email:pass:token` or a Discord token.", ephemeral=True)

    st = stock_manager.get_stock_summary()
    embed = discord.Embed(
        title="📦 Accounts Restocked Successfully!",
        description="Your accounts have been added to the stock file and are ready to join servers immediately.",
        color=0x2ecc71
    )
    embed.add_field(name="✅ Accounts Added", value=f"`+{added:,}` accounts", inline=True)
    embed.add_field(name="🔁 Duplicates Skipped", value=f"`{duplicates:,}` accounts", inline=True)
    embed.add_field(name="📦 Total Accounts in Stock", value=f"**{total:,}** accounts", inline=True)
    embed.add_field(
        name="👥 Total Member Capacity (100x Multi-Use)",
        value=f"**{st['remaining_member_capacity']:,}** Server Member Joins\n*(Each account can be used up to 100 times across different servers!)*",
        inline=False
    )
    embed.add_field(
        name="🚀 Max Per Single Server",
        value=f"**{st['active_accounts']:,}** members",
        inline=True
    )
    embed.set_footer(text=f"Ready for {BOT_PREFIX}order and {BOT_PREFIX}join")
    await ctx.send(embed=embed)


# 21. STOCK SYSTEM (LIVE AVAILABLE ACCOUNTS)
@bot.hybrid_command(name="stock", description="Check live stock of accounts ready to join servers")
async def cmd_stock(ctx: commands.Context):
    st = stock_manager.get_stock_summary()
    total_accs = st["total_accounts"]
    rem_cap = st["remaining_member_capacity"]
    active_accs = st["active_accounts"]
    joins_done = st["total_joins_performed"]
    valid_c = st["valid_stock"]
    unlocked_c = st["unlocked_stock"]

    embed = discord.Embed(
        title="📦 KYOKA & NEXUVER — 100x MULTI-SERVER STOCK SYSTEM",
        description=(
            f"⚡ **1 Account Can Join 100 Servers!**\n"
            f"• **Ready Stock:** **{rem_cap:,}** Server Joins\n"
            f"• **Accounts in Stock:** `{total_accs:,}` accounts\n"
            "• **Exchange Rate:** `1 Credit = 1 Server Member`"
        ),
        color=0x2ecc71 if rem_cap > 0 else 0xe74c3c
    )
    embed.add_field(name="📦 Ready Server Joins", value=f"**{rem_cap:,}** members", inline=True)
    embed.add_field(name="👤 Unique Accounts", value=f"**{total_accs:,}** *(×100 servers)*", inline=True)
    embed.add_field(name="📊 Joins Performed", value=f"`{joins_done:,}` / `{total_accs * 100:,}`", inline=True)
    embed.add_field(name="✉️ Email-Verified", value=f"`{valid_c:,}` accounts", inline=True)
    embed.add_field(name="📱 Phone-Verified", value=f"`{unlocked_c:,}` accounts", inline=True)
    embed.add_field(name="💎 Multi-Use Guarantee", value="**1 Account = 100 Server Joins**", inline=True)
    embed.add_field(
        name="📥 Add More Stock (.txt)",
        value=f"Upload accounts anytime with `{BOT_PREFIX}restock` (attach `.txt` file)!",
        inline=False
    )
    embed.add_field(
        name="🚀 How to Order Members",
        value=f"Type `{BOT_PREFIX}order <invite> <amount>`\n*Example:* `{BOT_PREFIX}order discord.gg/example 10`",
        inline=False
    )
    embed.set_footer(text=f"Your Balance: {credits_manager.format_credits(ctx.author.id)} • Prefix: {BOT_PREFIX}")
    await ctx.send(embed=embed)


# 22. 24/7 CONTINUOUS GENERATOR (RENDER CLOUD)
@bot.hybrid_command(name="autogen", description="Toggle 24/7 continuous account restocker on Render Cloud")
@app_commands.describe(action="Turn on, off, or check status", cooldown="Seconds between generation batches (min 10)")
@app_commands.choices(action=[
    app_commands.Choice(name="Status (Check current 24/7 restocker state)", value="status"),
    app_commands.Choice(name="On (Start continuous 24/7 restocker)", value="on"),
    app_commands.Choice(name="Off (Stop continuous 24/7 restocker)", value="off"),
])
async def cmd_autogen(ctx: commands.Context, action: str = "status", cooldown: int = 30):
    act = action.lower().strip()
    if act in ("on", "start"):
        if not is_admin(ctx.author.id):
            return await ctx.send("❌ **Access Denied.** Only the bot owner can toggle the 24/7 restocker.", ephemeral=True)
        if gen_runner.autogen_enabled:
            return await ctx.send("⚠️ 24/7 Auto-Generator is already running!", ephemeral=True)
        cooldown = max(10, cooldown)
        started = gen_runner.start_autogen(batch_size=1, cooldown_seconds=cooldown)
        if started:
            embed = discord.Embed(
                title="🚀 24/7 Auto-Generator Activated!",
                description=(
                    "The bot is now continuously generating accounts in the background on Render Cloud.\n"
                    f"• **Batch:** 1 account per cycle\n"
                    f"• **Cooldown:** {cooldown}s between cycles\n"
                    f"• **Target:** `output/valid.txt`\n"
                    f"• **Stop Command:** `{BOT_PREFIX}autogen off`"
                ),
                color=0x2ecc71
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to start auto-generator.", ephemeral=True)

    elif act in ("off", "stop"):
        if not is_admin(ctx.author.id):
            return await ctx.send("❌ **Access Denied.** Only the bot owner can toggle the 24/7 restocker.", ephemeral=True)
        stopped = gen_runner.stop_autogen()
        if stopped:
            await ctx.send("⏹️ **24/7 Auto-Generator Stopped.** Background restocker paused.")
        else:
            await ctx.send("⚠️ Auto-Generator was not running.")

    else:
        # Status
        uptime_str = "Not running"
        if gen_runner.autogen_enabled and gen_runner.autogen_start_time:
            elapsed = int(time.time() - gen_runner.autogen_start_time)
            hours, rem = divmod(elapsed, 3600)
            mins, secs = divmod(rem, 60)
            uptime_str = f"{hours}h {mins}m {secs}s"

        embed = discord.Embed(
            title="⚙️ 24/7 Auto-Generator Status",
            color=0x2ecc71 if gen_runner.autogen_enabled else 0x95a5a6
        )
        embed.add_field(name="State", value="🟢 **RUNNING 24/7**" if gen_runner.autogen_enabled else "⚪ **PAUSED**", inline=True)
        embed.add_field(name="Uptime", value=uptime_str, inline=True)
        embed.add_field(name="Total Produced", value=f"`{gen_runner.autogen_total_produced:,}` accounts", inline=True)
        st = stock_manager.get_stock_summary()
        embed.add_field(name="Ready Stock", value=f"`{st['total_accounts']:,}` accounts ({st['remaining_member_capacity']:,} joins)", inline=True)
        embed.set_footer(text=f"Toggle with '{BOT_PREFIX}autogen on' or '{BOT_PREFIX}autogen off'")
        await ctx.send(embed=embed)


# 23. DAILY REWARDS
@bot.hybrid_command(name="daily", description="Claim free daily credits (1 Credit = 1 Member)")
async def cmd_daily(ctx: commands.Context):
    success, msg, new_bal = credits_manager.claim_daily(ctx.author.id, reward=1)
    embed = discord.Embed(
        title="🎁 Daily Credit Claim",
        description=msg,
        color=0x2ecc71 if success else 0xe74c3c
    )
    embed.add_field(name="💎 Your Balance", value=credits_manager.format_credits(ctx.author.id), inline=True)
    embed.add_field(name="🏷️ Exchange Rate", value="**1 Credit = 1 Server Member**", inline=True)
    embed.set_footer(text=f"Claim once every 24 hours! • Prefix: {BOT_PREFIX}")
    await ctx.send(embed=embed)


# 24. USER PROFILE CARD
@bot.hybrid_command(name="profile", description="View user profile, credit balance, and member boost stats")
@app_commands.describe(user="The user whose profile you want to check (defaults to yourself)")
async def cmd_profile(ctx: commands.Context, user: Optional[discord.User] = None):
    target = user or ctx.author
    stats = credits_manager.get_user_stats(target.id)
    embed = discord.Embed(
        title=f"👤 User Profile — {target.name}",
        color=0x9b59b6
    )
    if hasattr(target, "display_avatar") and target.display_avatar:
        embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="🆔 User ID", value=f"`{target.id}`", inline=True)
    embed.add_field(name="👑 Role", value=stats["role"], inline=True)
    embed.add_field(name="💰 Credit Balance", value=str(stats["credits"]), inline=True)
    embed.add_field(name="👥 Members Boosted", value=f"**{stats['orders']:,}** members joined servers", inline=False)
    embed.add_field(name="💎 Exchange Rate", value="**1 Credit = 1 Discord Server Member**", inline=False)
    embed.set_footer(text=f"Prefix: {BOT_PREFIX} | Kyoka Suite")
    await ctx.send(embed=embed)


# 25. LEADERBOARD
@bot.hybrid_command(name="leaderboard", aliases=["top"], description="View top credit holders and server boosters")
async def cmd_leaderboard(ctx: commands.Context):
    top_users = credits_manager.get_leaderboard(limit=10)
    embed = discord.Embed(
        title="🏆 KYOKA LEADERBOARD — TOP USERS",
        description="Top credit holders & server boosters:",
        color=0xf1c40f
    )
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    if not top_users:
        embed.description = "No registered users on the leaderboard yet. Be the first to claim daily credits with `!daily`!"
    else:
        lines = []
        for i, (uid, bal) in enumerate(top_users):
            medal = medals[i] if i < len(medals) else f"`#{i+1}`"
            mention = f"<@{uid}>"
            stats = credits_manager.get_user_stats(int(uid))
            orders = stats.get("orders", 0)
            lines.append(f"{medal} {mention} — **{bal:,} credits** *(Boosted {orders:,} members)*")
        embed.add_field(name="Top Ranks", value="\n".join(lines), inline=False)

    embed.set_footer(text=f"1 Credit = 1 Member • Claim yours with {BOT_PREFIX}daily")
    await ctx.send(embed=embed)


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

