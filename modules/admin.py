import discord
from discord.ext import commands
from discord import app_commands
import os
import logging
import re
import asyncio
import io
from database import database_manager as db_manager

# Logging configuration
logger = logging.getLogger('discord_bot.admin')

# List of available KvK seasons
KVK_OPTIONS = [
    {"label": "KvK 1", "value": "kvk1", "description": "KvK Season 1"},
    {"label": "KvK 2", "value": "kvk2", "description": "KvK Season 2"},
    {"label": "KvK 3", "value": "kvk3", "description": "KvK Season 3"},
    {"label": "Alliance Invictus", "value": "alliance_invictus", "description": "Alliance Invictus KvK"},
    {"label": "Heroic Anthem", "value": "heroic_anthem", "description": "Heroic Anthem KvK"},
    {"label": "Keener Blades", "value": "keener_blades", "description": "Keener Blades KvK"},
    {"label": "King of all Britain", "value": "king_of_all_britain", "description": "King of all Britain KvK"},
    {"label": "King of the Nile", "value": "king_of_the_nile", "description": "King of the Nile KvK"},
    {"label": "Shifting Gears", "value": "shifting_gears", "description": "Shifting Gears KvK"},
    {"label": "Siege of Orleans", "value": "siege_of_orleans", "description": "Siege of Orleans KvK"},
    {"label": "Storm of Stratagems", "value": "storm_of_stratagems", "description": "Storm of Stratagems KvK"},
    {"label": "Strife of the Eight", "value": "strife_of_the_eight", "description": "Strife of the Eight KvK"},
    {"label": "Tides of War", "value": "tides_of_war", "description": "Tides of War KvK"},
    {"label": "Warriors Unbound", "value": "warriors_unbound", "description": "Warriors Unbound KvK"},
    {"label": "Song of Troy", "value": "song_of_troy", "description": "Song of Troy KvK"}
]

class KvKSelectView(discord.ui.View):
    def __init__(self, original_interaction, admin_cog):
        super().__init__(timeout=60)
        self.original_interaction = original_interaction
        self.admin_cog = admin_cog
        
        # Create the select menu
        options = [
            discord.SelectOption(label=opt["label"], value=opt["value"], description=opt.get("description"))
            for opt in KVK_OPTIONS
        ]
        
        # Split options if > 25 (Discord limit), but here we have < 25
        select = discord.ui.Select(placeholder="Choose a KvK Season...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        select = self.children[0]
        selected_kvk = select.values[0]
        
        # Save to DB
        if db_manager.set_current_kvk_name(selected_kvk):
            # Check what data is missing and build helpful guidance
            reqs = db_manager.get_all_requirements(selected_kvk)
            snapshots = db_manager.get_all_periods(selected_kvk)
            
            # Build the embed with next steps
            embed = discord.Embed(
                title=f"✅ KvK Season Set: {selected_kvk}",
                description="Season successfully activated! Here's what you need to do next:",
                color=discord.Color.green()
            )
            
            # Requirements status
            if reqs:
                embed.add_field(
                    name="📋 Requirements",
                    value=f"✅ Already set ({len(reqs)} brackets)",
                    inline=False
                )
            else:
                embed.add_field(
                    name="📋 Requirements",
                    value="⚠️ **Not set** - Use `/set_requirements` (file) or `/set_requirements_text` (paste text)",
                    inline=False
                )
            
            # Snapshots status
            if snapshots:
                embed.add_field(
                    name="📊 Player Data",
                    value=f"✅ {len(snapshots)} period(s) uploaded",
                    inline=False
                )
            else:
                embed.add_field(
                    name="📊 Player Data",
                    value="⚠️ **Not uploaded** - Use `/upload_snapshot` to upload Start/End snapshots",
                    inline=False
                )
            
            # Next steps summary
            next_steps = []
            if not reqs:
                next_steps.append("1️⃣ Set requirements for power brackets")
            if not snapshots:
                next_steps.append("2️⃣ Upload player snapshot (Start)")
            
            if next_steps:
                embed.add_field(
                    name="📌 Next Steps",
                    value="\n".join(next_steps),
                    inline=False
                )
            else:
                embed.add_field(
                    name="📌 Status",
                    value="✅ All data is ready! You can use `/check_compliance` to check player stats.",
                    inline=False
                )
            
            embed.set_footer(text="💡 Tip: Use /kvk_setup for a guided wizard to set everything up step-by-step")
            
            await interaction.response.edit_message(content=None, embed=embed, view=None)
            await self.admin_cog.log_to_channel(interaction, "Set KvK", f"New Season: {selected_kvk}")
        else:
            await interaction.response.edit_message(content="❌ Failed to set KvK season. Check logs.", view=None)
            await self.admin_cog.log_to_channel(interaction, "Set KvK Failed", f"Attempted: {selected_kvk}")
            
        self.stop()

class RequirementsModal(discord.ui.Modal, title="Set KvK Requirements"):
    requirements_text = discord.ui.TextInput(
        label="Paste Requirements Text",
        style=discord.TextStyle.paragraph,
        placeholder="100M - 150M Power\n100M Kills / 1M deads\n...",
        required=True,
        max_length=2000
    )

    def __init__(self, admin_cog):
        super().__init__()
        self.admin_cog = admin_cog

    async def on_submit(self, interaction: discord.Interaction):
        text = self.requirements_text.value
        parsed_reqs = self.parse_requirements(text)
        
        if not parsed_reqs:
            await interaction.response.send_message("❌ Could not parse any requirements from the text.", ephemeral=True)
            await self.admin_cog.log_to_channel(interaction, "Set Requirements Failed", "Reason: Parsing error")
            return
            
        current_kvk = db_manager.get_current_kvk_name()
        if db_manager.save_requirements_batch(current_kvk, parsed_reqs):
            await interaction.response.send_message(f"✅ Successfully saved {len(parsed_reqs)} requirement brackets for **{current_kvk}**.", ephemeral=True)
            await self.admin_cog.log_to_channel(interaction, "Set Requirements (Text)", f"KvK: {current_kvk}\nBrackets: {len(parsed_reqs)}")
        else:
            await interaction.response.send_message("❌ Database error while saving requirements.", ephemeral=True)

    def parse_requirements(self, text):
        requirements = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            try:
                # Extract Power Range
                min_power = 0
                max_power = 0
                
                # Check for "X - Y Power"
                range_match = re.search(r'(\d+)[Mm]?\s*-\s*(\d+)[Mm]?\s*Power', line, re.IGNORECASE)
                if range_match:
                    val1 = int(range_match.group(1)) * 1_000_000
                    val2 = int(range_match.group(2)) * 1_000_000
                    min_power = min(val1, val2)
                    max_power = max(val1, val2)
                else:
                    # Check for "X+ Power"
                    plus_match = re.search(r'(\d+)[Mm]?\+\s*Power', line, re.IGNORECASE)
                    if plus_match:
                        min_power = int(plus_match.group(1)) * 1_000_000
                        max_power = 2_000_000_000 # Arbitrary high cap
                
                if min_power == 0 and max_power == 0:
                    continue

                # Extract Goals
                # Updated regex to capture suffixes
                kills_match = re.search(r'([\d\.,]+[kKmMbB]?)\s*Kills', line, re.IGNORECASE)
                deads_match = re.search(r'([\d\.,]+[kKmMbB]?)\s*deads', line, re.IGNORECASE)
                
                req_kp = 0
                req_deads = 0
                
                if kills_match:
                    val_str = kills_match.group(1).replace(',', '.')
                    multiplier = 1
                    if 'k' in val_str.lower():
                        multiplier = 1_000
                        val_str = re.sub(r'[kK]', '', val_str)
                    elif 'm' in val_str.lower():
                        multiplier = 1_000_000
                        val_str = re.sub(r'[mM]', '', val_str)
                    elif 'b' in val_str.lower():
                        multiplier = 1_000_000_000
                        val_str = re.sub(r'[bB]', '', val_str)
                    
                    try:
                        req_kp = int(float(val_str) * multiplier)
                    except ValueError:
                        req_kp = 0
                    
                if deads_match:
                    val_str = deads_match.group(1).replace(',', '.')
                    multiplier = 1
                    if 'k' in val_str.lower():
                        multiplier = 1_000
                        val_str = re.sub(r'[kK]', '', val_str)
                    elif 'm' in val_str.lower():
                        multiplier = 1_000_000
                        val_str = re.sub(r'[mM]', '', val_str)
                    elif 'b' in val_str.lower():
                        multiplier = 1_000_000_000
                        val_str = re.sub(r'[bB]', '', val_str)

                    try:
                        req_deads = int(float(val_str) * multiplier)
                    except ValueError:
                        req_deads = 0
                    
                if req_kp == 0 and req_deads == 0:
                    continue
                    
                requirements.append({
                    'min_power': min_power,
                    'max_power': max_power,
                    'required_kills': req_kp, # Reusing variable name from regex but storing as required_kills
                    'required_deaths': req_deads
                })
                
            except Exception as e:
                logger.error(f"Error parsing line '{line}': {e}")
                continue
                
        return requirements

class FinishKvKConfirmView(discord.ui.View):
    def __init__(self, original_interaction, kvk_name, admin_cog):
        super().__init__(timeout=60)
        self.original_interaction = original_interaction
        self.kvk_name = kvk_name
        self.admin_cog = admin_cog

    @discord.ui.button(label="Yes, Finish & Archive", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        from datetime import datetime
        
        # Get start date (mock implementation if not stored)
        # Ideally we should store start date in kvk_settings too
        start_date = "Unknown" 
        end_date = datetime.now().strftime("%Y-%m-%d")
        
        archive_name = f"{self.kvk_name} ({start_date} - {end_date})"
        
        # Archive data
        if db_manager.archive_kvk_data(self.kvk_name, archive_name):
            # Reset current KvK
            db_manager.set_current_kvk_name("Not set")
            
            await interaction.response.edit_message(
                content=f"✅ Season **{self.kvk_name}** finished.\n"
                        f"📂 Data archived as: **{archive_name}**.\n"
                        f"Bot is now ready for a new season.",
                view=None
            )
            await self.admin_cog.log_to_channel(interaction, "Finish KvK", f"KvK: {self.kvk_name}\nArchived as: {archive_name}")
        else:
            await interaction.response.edit_message(content="❌ Error archiving data. Check logs.", view=None)
            await self.admin_cog.log_to_channel(interaction, "Finish KvK Failed", f"KvK: {self.kvk_name}\nError: Archiving failed.")
        
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Action cancelled.", view=None)
        await self.admin_cog.log_to_channel(interaction, "Finish KvK Cancelled", "User cancelled the action.")
        self.stop()


class ResetBotConfirmView(discord.ui.View):
    def __init__(self, admin_cog):
        super().__init__(timeout=60)
        self.admin_cog = admin_cog

    @discord.ui.button(label="YES, WIPE ALL DATA", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if db_manager.reset_all_data():
            await interaction.response.edit_message(
                content="✅ **ALL DATA HAS BEEN WIPED.** The bot is now ready for a fresh start.",
                view=None
            )
            await self.admin_cog.log_to_channel(interaction, "RESET BOT", "All data wiped.")
        else:
            await interaction.response.edit_message(content="❌ Error wiping data. Check logs.", view=None)
            await self.admin_cog.log_to_channel(interaction, "Reset Bot Failed", "Error wiping data.")
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Reset cancelled.", view=None)
        await self.admin_cog.log_to_channel(interaction, "Reset Bot Cancelled", "User cancelled the action.")
        self.stop()


# --- Wizard Classes ---

class WizardConfirmationView(discord.ui.View):
    def __init__(self, kvk_name, reqs_count, admin_cog):
        super().__init__(timeout=120)
        self.kvk_name = kvk_name
        self.reqs_count = reqs_count
        self.admin_cog = admin_cog

    @discord.ui.button(label="Activate Season", style=discord.ButtonStyle.green)
    async def activate(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Finalize setup
        if db_manager.set_current_kvk_name(self.kvk_name):
            embed = discord.Embed(title="🎉 KvK Season Activated!", color=discord.Color.green())
            embed.add_field(name="Season", value=self.kvk_name, inline=False)
            embed.add_field(name="Requirements", value=f"{self.reqs_count} brackets set" if self.reqs_count > 0 else "Not set (or set later)", inline=False)
            embed.set_footer(text="You can now start uploading snapshots.")
            
            await interaction.response.edit_message(embed=embed, view=None)
            await self.admin_cog.log_to_channel(interaction, "KvK Setup Complete", f"Season: {self.kvk_name}\nReqs: {self.reqs_count}")
        else:
            await interaction.response.edit_message(content="❌ Failed to activate season. Database error.", view=None)

class WizardRequirementsModal(discord.ui.Modal, title="Wizard: Set Requirements"):
    requirements_text = discord.ui.TextInput(
        label="Paste Requirements Text",
        style=discord.TextStyle.paragraph,
        placeholder="100M - 150M Power\n100M Kills / 1M deads\n...",
        required=True,
        max_length=2000
    )

    def __init__(self, kvk_name, admin_cog):
        super().__init__()
        self.kvk_name = kvk_name
        self.admin_cog = admin_cog

    async def on_submit(self, interaction: discord.Interaction):
        text = self.requirements_text.value
        # Quick hack to reuse the parser from the other class instance
        dummy_modal = RequirementsModal(self.admin_cog)
        parsed_reqs = dummy_modal.parse_requirements(text)
        
        if not parsed_reqs:
            await interaction.response.send_message("❌ Could not parse requirements. Please try again.", ephemeral=True)
            return

        if db_manager.save_requirements_batch(self.kvk_name, parsed_reqs):
            # Proceed to confirmation
            embed = discord.Embed(title="Step 3: Confirmation", description="Review your settings.", color=discord.Color.blue())
            embed.add_field(name="Selected Season", value=self.kvk_name, inline=False)
            embed.add_field(name="Requirements", value=f"✅ {len(parsed_reqs)} brackets parsed", inline=False)
            
            await interaction.response.edit_message(embed=embed, view=WizardConfirmationView(self.kvk_name, len(parsed_reqs), self.admin_cog))
        else:
            await interaction.response.send_message("❌ Database error.", ephemeral=True)

class WizardRequirementsView(discord.ui.View):
    def __init__(self, kvk_name, admin_cog):
        super().__init__(timeout=120)
        self.kvk_name = kvk_name
        self.admin_cog = admin_cog

    @discord.ui.button(label="Paste Text", style=discord.ButtonStyle.primary)
    async def paste_text(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(WizardRequirementsModal(self.kvk_name, self.admin_cog))

    @discord.ui.button(label="Upload File Later", style=discord.ButtonStyle.secondary)
    async def upload_later(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="Step 3: Confirmation", description="Review your settings.", color=discord.Color.blue())
        embed.add_field(name="Selected Season", value=self.kvk_name, inline=False)
        embed.add_field(name="Requirements", value="⚠️ To be set later (use `/set_requirements`)", inline=False)
        
        await interaction.response.edit_message(embed=embed, view=WizardConfirmationView(self.kvk_name, 0, self.admin_cog))

    @discord.ui.button(label="Skip Requirements", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="Step 3: Confirmation", description="Review your settings.", color=discord.Color.blue())
        embed.add_field(name="Selected Season", value=self.kvk_name, inline=False)
        embed.add_field(name="Requirements", value="❌ None", inline=False)
        
        await interaction.response.edit_message(embed=embed, view=WizardConfirmationView(self.kvk_name, 0, self.admin_cog))

class WizardKvKSelectView(discord.ui.View):
    def __init__(self, admin_cog):
        super().__init__(timeout=120)
        self.admin_cog = admin_cog
        
        options = [
            discord.SelectOption(label=opt["label"], value=opt["value"], description=opt.get("description"))
            for opt in KVK_OPTIONS
        ]
        select = discord.ui.Select(placeholder="Select Season...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        selected_kvk = self.children[0].values[0]
        
        # Move to Step 2
        embed = discord.Embed(title="Step 2: Requirements", description=f"Selected: **{selected_kvk}**.\nHow do you want to set requirements?", color=discord.Color.blue())
        await interaction.response.edit_message(embed=embed, view=WizardRequirementsView(selected_kvk, self.admin_cog))


class LeaderboardPaginationView(discord.ui.View):
    def __init__(self, data, title, kvk_name):
        super().__init__(timeout=180)
        self.data = data
        self.title = title
        self.kvk_name = kvk_name
        self.per_page = 10
        self.current_page = 0
        self.total_pages = (len(data) - 1) // self.per_page + 1

    def create_embed(self):
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_data = self.data[start:end]

        embed = discord.Embed(
            title=f"{self.title} - {self.kvk_name}",
            description="**Formula:** T4×4 + T5×10 + Deaths×15\n✅ = Met Requirements | ❌ = Failed",
            color=discord.Color.gold()
        )

        leaderboard_text = ""
        for i, player in enumerate(page_data, start + 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            # Status icon
            status_icon = "✅" if player.get('compliant', False) else "❌"
            
            leaderboard_text += f"{medal} **{player['player_name']}** {status_icon} — {player['dkp']:,} DKP\n"
            leaderboard_text += f"   T4: {player['t4']:,} | T5: {player['t5']:,} | Deaths: {player['deaths']:,}\n"

        if not leaderboard_text:
            leaderboard_text = "No data available"

        embed.add_field(name=f"Leaderboard (Page {self.current_page + 1}/{self.total_pages})", value=leaderboard_text, inline=False)
        embed.set_footer(text=f"Total players: {len(self.data)}")
        return embed

    def update_buttons(self):
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page == self.total_pages - 1

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, disabled=True)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)


class LinkedAccountsPaginationView(discord.ui.View):
    def __init__(self, data):
        super().__init__(timeout=180)
        self.data = data
        self.per_page = 10
        self.current_page = 0
        self.total_pages = (len(data) - 1) // self.per_page + 1

    def create_embed(self):
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_data = self.data[start:end]

        embed = discord.Embed(
            title="🔗 Linked Accounts",
            color=discord.Color.blue()
        )

        text = ""
        for acc in page_data:
            player_name = acc.get('player_name') or "Unknown Name"
            player_id = acc['player_id']
            discord_id = acc['discord_id']
            # account_type might be None if old data, handle gracefully
            acc_type = acc.get('account_type') or ('main' if acc.get('is_main_account') else 'alt')
            
            type_emoji = "🏠" if acc_type == 'main' else "👤" if acc_type == 'alt' else "🚜"
            type_str = acc_type.capitalize()
            
            text += f"**{player_name}** (`{player_id}`)\n"
            text += f"Linked to: <@{discord_id}>\n"
            text += f"{type_emoji} **{type_str}**\n"
            text += "─" * 20 + "\n"

        if not text:
            text = "No accounts found."

        embed.description = text
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages} | Total: {len(self.data)}")
        return embed

    def update_buttons(self):
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page == self.total_pages - 1

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, disabled=True)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)


# Cog for administrator commands
class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.admin_role_ids = []
        
        # Load multiple admin role IDs from environment variables (comma-separated)
        role_ids_str = os.getenv('ADMIN_ROLE_IDS', '')
        
        # Fallback to old single ADMIN_ROLE_ID for backwards compatibility
        if not role_ids_str:
            role_ids_str = os.getenv('ADMIN_ROLE_ID', '')
        
        if role_ids_str:
            for rid in role_ids_str.split(','):
                rid = rid.strip()
                if rid:
                    try:
                        self.admin_role_ids.append(int(rid))
                    except ValueError:
                        logger.warning(f"Invalid role ID in ADMIN_ROLE_IDS: {rid}")
            
            if self.admin_role_ids:
                logger.info(f"Admin role IDs successfully loaded: {self.admin_role_ids}")
            else:
                logger.error("No valid admin role IDs found. Check ADMIN_ROLE_IDS in .env file.")
        else:
            logger.error("ADMIN_ROLE_IDS not set in .env file.")

    # Admin role check function
    def is_admin(self, interaction: discord.Interaction):
        if not self.admin_role_ids:
            logger.warning("Admin role check failed because no role IDs were loaded.")
            return False

        # Check if user has any of the admin roles
        for role_id in self.admin_role_ids:
            admin_role = discord.utils.get(interaction.guild.roles, id=role_id)
            if admin_role and admin_role in interaction.user.roles:
                return True
        return False

    async def log_to_channel(self, interaction: discord.Interaction, action: str, details: str):
        """Logs an admin action to the specified Discord channel."""
        await self._do_log_to_channel(interaction, action, details)
    
    async def _do_log_to_channel(self, interaction: discord.Interaction, action: str, details: str):
        """Internal method that actually performs the logging."""
        log_channel_id = int(os.getenv('LOG_CHANNEL_ID', 0))
        if log_channel_id == 0:
            return
        channel = self.bot.get_channel(log_channel_id)
        
        if not channel:
            logger.warning(f"Log channel {log_channel_id} not found.")
            return

        embed = discord.Embed(title="🛡️ Admin Action Logged", color=discord.Color.blue(), timestamp=interaction.created_at)
        embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
        embed.add_field(name="Action", value=action, inline=True)
        embed.add_field(name="Details", value=details, inline=False)
        embed.set_footer(text=f"ID: {interaction.user.id}")
        
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send log message: {e}")
            
        # Also log to database
        db_manager.log_admin_action(interaction.user.id, interaction.user.name, action, details)

    @app_commands.command(name="export_logs", description="Export all admin logs as a CSV file.")
    @app_commands.default_permissions(administrator=True)
    async def export_logs(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return
            
        # Check if command is used in the logging channel
        log_channel_id = int(os.getenv('LOG_CHANNEL_ID', 0))
        if log_channel_id != 0 and interaction.channel_id != log_channel_id:
            await interaction.response.send_message(f"This command can only be used in the logging channel <#{log_channel_id}>.", ephemeral=True)
            await self.log_to_channel(interaction, "Command Failed", f"Command: /export_logs\nReason: Wrong channel (Attempted in {interaction.channel.name})")
            return
            
        logs = db_manager.get_all_admin_logs()
        if not logs:
            await interaction.response.send_message("No logs found in the database.", ephemeral=True)
            await self.log_to_channel(interaction, "Command Failed", "Command: /export_logs\nReason: Database empty")
            return
            
        # Create CSV content
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Admin ID', 'Admin Name', 'Action', 'Details', 'Timestamp'])
        
        for log in logs:
            writer.writerow([
                log['id'],
                log['admin_id'],
                log['admin_name'],
                log['action'],
                log['details'],
                log['timestamp']
            ])
            
        output.seek(0)
        file = discord.File(io.BytesIO(output.getvalue().encode()), filename="admin_logs.csv")
        
        await interaction.response.send_message(f"Found {len(logs)} logs.", file=file, ephemeral=True)
        await self.log_to_channel(interaction, "Command Used", "Command: /export_logs")

    @app_commands.command(name="set_kvk", description="Sets the current KvK season (admin only).")
    @app_commands.default_permissions(administrator=True)
    async def set_kvk_command(self, interaction: discord.Interaction):
        # Role permission check
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return

        # Check the list of options before creating the View
        if not KVK_OPTIONS:
            logger.error("KVK_OPTIONS list is empty. Cannot create a select menu.")
            await interaction.response.send_message(
                "Sorry, the list of available KvK is empty. Please contact the developer.",
                ephemeral=True
            )
            await self.log_to_channel(interaction, "Command Failed", "Command: /set_kvk\nReason: KVK_OPTIONS empty")
            return

        # Respond to the interaction by sending the View (dropdown menu)
        await interaction.response.send_message("Select the current KvK:", view=KvKSelectView(interaction, self))
        await self.log_to_channel(interaction, "Command Used", "Command: /set_kvk")

    @app_commands.command(name="status", description="Check the current status of the bot (Active KvK, Requirements).")
    @app_commands.default_permissions(administrator=True)
    async def status(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return

        # Get current KvK
        kvk_name = db_manager.get_current_kvk_name()
        
        embed = discord.Embed(title="Bot Status", color=discord.Color.gold())
        
        if kvk_name and kvk_name != "Not set":
            embed.add_field(name="Current KvK Season", value=f"**{kvk_name}**", inline=False)
            
            # Check requirements
            reqs = db_manager.get_all_requirements(kvk_name)
            if reqs:
                embed.add_field(name="Requirements", value=f"✅ Set ({len(reqs)} brackets)", inline=False)
            else:
                embed.add_field(name="Requirements", value="⚠️ Not set", inline=False)
        else:
            embed.add_field(name="Current KvK Season", value="❌ Not selected", inline=False)
            embed.description = "Use `/set_kvk` to select a season."

        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.log_to_channel(interaction, "Command Used", "Command: /status")

    @app_commands.command(name="set_requirements_text", description="Enter KvK requirements via text paste.")
    @app_commands.default_permissions(administrator=True)
    async def set_requirements_text(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return

        current_kvk = db_manager.get_current_kvk_name()
        if not current_kvk or current_kvk == "Not set":
            await interaction.response.send_message("Please set the current KvK season first using /set_kvk.", ephemeral=True)
            await self.log_to_channel(interaction, "Command Failed", f"Command: /{interaction.command.name}\nReason: No active KvK")
            return

        await interaction.response.send_modal(RequirementsModal(self))
        await self.log_to_channel(interaction, "Command Used", "Command: /set_requirements_text")

    @app_commands.command(name="finish_kvk", description="Finish the current KvK season and archive data.")
    @app_commands.default_permissions(administrator=True)
    async def finish_kvk(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return

        current_kvk_name = db_manager.get_current_kvk_name()
        
        if not current_kvk_name or current_kvk_name == "Not set":
            await interaction.response.send_message("No KvK season is currently active.", ephemeral=True)
            await self.log_to_channel(interaction, "Command Failed", f"Command: /{interaction.command.name}\nReason: No active KvK")
            return

        # Confirm action
        await interaction.response.send_message(
            f"Are you sure you want to finish **{current_kvk_name}**?\n"
            "This will archive all stats and snapshots with today's date and reset the active season.",
            view=FinishKvKConfirmView(interaction, current_kvk_name, self),
            ephemeral=True
        )
        await self.log_to_channel(interaction, "Command Used", "Command: /finish_kvk")

    # NOTE: Slash commands for file uploads (/upload_snapshot, /set_requirements) removed
    # due to Discord's 3-second interaction timeout issues with file attachments.
    # Use message commands instead: !upload_snapshot, !upload_requirements, !upload_players


    @app_commands.command(name="calculate_period", description="Calculate results for a period.")
    @app_commands.describe(period_name="Name of the period to calculate")
    @app_commands.default_permissions(administrator=True)
    async def calculate_period(self, interaction: discord.Interaction, period_name: str):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return

        current_kvk = db_manager.get_current_kvk_name()
        if not current_kvk or current_kvk == "Not set":
            await interaction.response.send_message("Please set the current KvK season first using /set_kvk.", ephemeral=True)
            await self.log_to_channel(interaction, "Command Failed", f"Command: /{interaction.command.name}\nReason: No active KvK")
            return

        await interaction.response.defer(ephemeral=True)

        from core import calculation
        success, message = calculation.calculate_period_results(current_kvk, period_name)

        if success:
            await interaction.followup.send(f"Calculation successful: {message}")
            await self.log_to_channel(interaction, "Calculate Period", f"KvK: {current_kvk}\nPeriod: {period_name}\nResult: {message}")
        else:
            await interaction.followup.send(f"Calculation failed: {message}")
            await self.log_to_channel(interaction, "Calculate Period Failed", f"KvK: {current_kvk}\nPeriod: {period_name}\nError: {message}")

    @app_commands.command(name="view_requirements", description="View current KvK requirements.")
    @app_commands.default_permissions(administrator=True)
    async def view_requirements(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return

        current_kvk = db_manager.get_current_kvk_name()
        if not current_kvk or current_kvk == "Not set":
            await interaction.response.send_message("No KvK season is currently active.", ephemeral=True)
            return

        reqs = db_manager.get_all_requirements(current_kvk)
        if not reqs:
            await interaction.response.send_message(f"No requirements set for **{current_kvk}**.", ephemeral=True)
            await self.log_to_channel(interaction, "Command Failed", f"Command: /view_requirements\nReason: No requirements set for {current_kvk}")
            return

        embed = discord.Embed(title=f"Requirements for {current_kvk}", color=discord.Color.blue())
        desc = ""
        for req in reqs:
            # req is a Row object, access by index or key if row_factory is set
            # In db_manager.get_all_requirements, row_factory is set to sqlite3.Row
            min_p = req['min_power']
            max_p = req['max_power']
            kp = req['required_kills']
            deads = req['required_deaths']
            
            range_str = f"{min_p/1_000_000:.0f}M - {max_p/1_000_000:.0f}M" if max_p < 2_000_000_000 else f"{min_p/1_000_000:.0f}M+"
            desc += f"**{range_str}**: Kills: {kp/1_000_000:.1f}M | Deads: {deads/1_000_000:.1f}M\n"
        
        embed.description = desc
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.log_to_channel(interaction, "Command Used", "Command: /view_requirements")

    @app_commands.command(name="list_linked_accounts", description="List all linked Discord accounts.")
    @app_commands.default_permissions(administrator=True)
    async def list_linked_accounts(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return
            
        accounts = db_manager.get_all_linked_accounts_full()
        if not accounts:
            await interaction.response.send_message("No accounts linked yet.", ephemeral=True)
            return
            
        view = LinkedAccountsPaginationView(accounts)
        view.update_buttons()
        await interaction.response.send_message(embed=view.create_embed(), view=view, ephemeral=True)
        await self.log_to_channel(interaction, "Command Used", "Command: /list_linked_accounts")

    @app_commands.command(name="admin_link_account", description="Link a player ID to a specific Discord user.")
    @app_commands.describe(user="The Discord user", player_id="The game ID")
    @app_commands.default_permissions(administrator=True)
    async def admin_link_account(self, interaction: discord.Interaction, user: discord.User, player_id: int):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return
            
        # Check if user already has a main account? The logic in db_manager.link_account handles is_main logic if we pass it.
        # Let's assume admin links are main by default if it's the first one, or we can just call the same logic.
        
        # We need to know if this user has other accounts to set is_main correctly if we want to mimic the user command.
        # db_manager.link_account logic:
        # accounts = db_manager.get_linked_accounts(discord_id)
        # is_main = len(accounts) == 0
        
        discord_id = user.id
        existing = db_manager.get_linked_accounts(discord_id)
        is_main = len(existing) == 0 if existing else True
        
        if db_manager.link_account(discord_id, player_id, 'main' if is_main else 'alt'):
            await interaction.response.send_message(f"✅ Successfully linked ID `{player_id}` to {user.mention}.", ephemeral=True)
            await self.log_to_channel(interaction, "Admin Link Account", f"User: {user.mention} ({user.id})\nPlayer ID: {player_id}")
        else:
            await interaction.response.send_message("❌ Failed to link account.", ephemeral=True)
            await self.log_to_channel(interaction, "Admin Link Account Failed", f"User: {user.mention}\nPlayer ID: {player_id}")

    @app_commands.command(name="admin_unlink_account", description="Unlink a game account from a Discord user.")
    @app_commands.describe(player_id="The game ID to unlink")
    @app_commands.default_permissions(administrator=True)
    async def admin_unlink_account(self, interaction: discord.Interaction, player_id: int):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return

        # We don't need discord_id to unlink by player_id if we assume player_id is unique globally or we just unlink it from whoever has it.
        # But db_manager.unlink_account requires discord_id.
        # Let's find who owns it first.
        # Actually, db_manager.unlink_account takes (discord_id, player_id).
        # We might want a function to unlink by player_id regardless of owner, or we need to find the owner.
        # Let's assume we want to unlink it from ANYONE.
        
        # We need a new DB function or we iterate.
        # Let's check linked_accounts table.
        # For now, let's implement a "Force Unlink" that removes it from linked_accounts table by player_id.
        # We need to add this to db_manager or use raw SQL here (bad practice).
        # Let's just ask the user for the Discord User too? No, usually you just want to unlink a bad ID.
        
        # Let's add force_unlink to db_manager?
        # Or just use the existing one if we know the user.
        # Let's assume the admin knows the ID.
        
        # Quick hack: Get all linked accounts, find the one with this player_id.
        all_links = db_manager.get_all_linked_accounts_full()
        target_link = next((acc for acc in all_links if acc['player_id'] == player_id), None)
        
        if not target_link:
            await interaction.response.send_message(f"❌ Player ID `{player_id}` is not linked to anyone.", ephemeral=True)
            return
            
        if db_manager.unlink_account(target_link['discord_id'], player_id):
             await interaction.response.send_message(f"✅ Successfully unlinked ID `{player_id}` from <@{target_link['discord_id']}>.", ephemeral=True)
             await self.log_to_channel(interaction, "Admin Force Unlink", f"Player ID: {player_id}\nOwner: {target_link['discord_id']}")
        else:
             await interaction.response.send_message("❌ Failed to unlink account.", ephemeral=True)

    @app_commands.command(name="export_leaderboard", description="Export the DKP leaderboard as a CSV file.")
    @app_commands.default_permissions(administrator=True)
    async def export_leaderboard(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return
            
        current_kvk = db_manager.get_current_kvk_name()
        if not current_kvk or current_kvk == "Not set":
            await interaction.response.send_message("No KvK season is currently active.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        
        all_stats = db_manager.get_all_kvk_stats(current_kvk)
        if not all_stats:
            await interaction.followup.send("No stats available.")
            return
            
        # Calculate DKP
        data = []
        for stat in all_stats:
            t4 = stat.get('total_t4_kills', 0) or 0
            t5 = stat.get('total_t5_kills', 0) or 0
            deaths = stat.get('total_deaths', 0) or 0
            dkp = (t4 * 4) + (t5 * 10) + (deaths * 15)
            total_kills = t4 + t5
            
            data.append([
                stat['player_id'],
                stat['player_name'],
                stat['total_power'],
                stat['total_kill_points'],
                deaths,
                t4,
                t5,
                total_kills,
                dkp
            ])
            
        # Sort by DKP
        data.sort(key=lambda x: x[8], reverse=True)
        
        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Player ID', 'Name', 'Power', 'Kill Points', 'Deaths', 'T4 Kills', 'T5 Kills', 'Total Kills (T4+T5)', 'DKP'])
        writer.writerows(data)
        
        output.seek(0)
        file = discord.File(io.BytesIO(output.getvalue().encode()), filename=f"leaderboard_{current_kvk}.csv")
        
        await interaction.followup.send(f"Leaderboard for **{current_kvk}** ({len(data)} players)", file=file)
        await self.log_to_channel(interaction, "Command Used", "Command: /export_leaderboard")

    @app_commands.command(name="set_reward_role", description="Set the Discord role to be given to compliant players.")
    @app_commands.describe(role="The role to assign")
    @app_commands.default_permissions(administrator=True)
    async def set_reward_role(self, interaction: discord.Interaction, role: discord.Role):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return
            
        if db_manager.set_reward_role(role.id):
            await interaction.response.send_message(f"✅ Reward role set to: {role.mention}", ephemeral=True)
            await self.log_to_channel(interaction, "Set Reward Role", f"Role: {role.name} ({role.id})")
        else:
            await interaction.response.send_message("❌ Failed to set reward role.", ephemeral=True)

    @app_commands.command(name="reset_bot", description="⚠️ WIPE ALL DATA and reset bot to factory settings.")
    @app_commands.default_permissions(administrator=True)
    async def reset_bot(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return
        
        # Defer immediately to prevent interaction timeout
        await interaction.response.defer(ephemeral=True)
        
        await interaction.followup.send(
            "⚠️ **DANGER ZONE** ⚠️\n"
            "Are you sure you want to **DELETE ALL DATA** (Stats, Snapshots, Requirements, Linked Accounts)?\n"
            "This action cannot be undone.",
            view=ResetBotConfirmView(self),
            ephemeral=True
        )
        await self.log_to_channel(interaction, "Command Used", "Command: /reset_bot")


    @app_commands.command(name="kvk_setup", description="🧙‍♂️ Guided wizard to set up a new KvK season.")
    @app_commands.default_permissions(administrator=True)
    async def kvk_setup(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return

        # Defer immediately to prevent interaction timeout
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(title="🧙‍♂️ KvK Setup Wizard", description="Welcome! Let's set up your new KvK season step-by-step.", color=discord.Color.blue())
        embed.add_field(name="Step 1", value="Select the KvK Season", inline=False)
        
        await interaction.followup.send(embed=embed, view=WizardKvKSelectView(self), ephemeral=True)
        await self.log_to_channel(interaction, "Command Used", "Command: /kvk_setup")


class CompliancePaginationView(discord.ui.View):
    def __init__(self, data, title, kvk_name):
        super().__init__(timeout=180)
        self.data = data
        self.title = title
        self.kvk_name = kvk_name
        self.per_page = 8  # Fewer items per page due to more text
        self.current_page = 0
        self.total_pages = (len(data) - 1) // self.per_page + 1

    def create_embed(self):
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_data = self.data[start:end]

        embed = discord.Embed(
            title=f"{self.title} - {self.kvk_name}",
            description="✅ = Met | ❌ = Failed\nFormat: Current / Required",
            color=discord.Color.blue()
        )

        for player in page_data:
            status_icon = "✅" if player['compliant'] else "❌"
            
            # Format numbers (e.g. 1.5M)
            def fmt(num):
                if num >= 1_000_000_000: return f"{num/1_000_000_000:.1f}B"
                if num >= 1_000_000: return f"{num/1_000_000:.1f}M"
                if num >= 1_000: return f"{num/1_000:.1f}K"
                return str(num)

            kills_str = f"{fmt(player['kills'])} / {fmt(player['req_kills'])}"
            deaths_str = f"{fmt(player['deaths'])} / {fmt(player['req_deaths'])}"
            
            field_name = f"{status_icon} {player['name']} ({fmt(player['power'])})"
            field_value = f"⚔️ Kills: **{kills_str}**\n💀 Deaths: **{deaths_str}**"
            
            if not player['compliant']:
                missing = []
                if player['kills'] < player['req_kills']: missing.append("Kills")
                if player['deaths'] < player['req_deaths']: missing.append("Deaths")
                field_value += f"\n⚠️ Failed: {', '.join(missing)}"

            embed.add_field(name=field_name, value=field_value, inline=False)

        embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages} | Total: {len(self.data)}")
        return embed

    def update_buttons(self):
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page == self.total_pages - 1

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, disabled=True)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)


    @app_commands.command(name="check_compliance", description="Check which players met the requirements.")
    @app_commands.default_permissions(administrator=True)
    async def check_compliance(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return

        current_kvk = db_manager.get_current_kvk_name()
        if not current_kvk or current_kvk == "Not set":
            await interaction.response.send_message("No KvK season is currently active.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # Get all players stats for this KvK
        all_stats = db_manager.get_all_kvk_stats(current_kvk)
        
        if not all_stats:
            await interaction.followup.send("No stats found for this KvK season.")
            return

        compliance_data = []

        for player in all_stats:
            reqs = db_manager.get_requirements(current_kvk, player['total_power'])
            
            # Default values if no reqs found (treat as 0 reqs or handle as error)
            req_kills = reqs['required_kills'] if reqs else 0
            req_deaths = reqs['required_deaths'] if reqs else 0
            
            t4 = player.get('total_t4_kills', 0) or 0
            t5 = player.get('total_t5_kills', 0) or 0
            total_kills = t4 + t5
            total_deaths = player.get('total_deaths', 0) or 0
            
            kills_met = total_kills >= req_kills
            deaths_met = total_deaths >= req_deaths
            compliant = kills_met and deaths_met and (reqs is not None)

            compliance_data.append({
                'name': player['player_name'],
                'power': player['total_power'],
                'kills': total_kills,
                'deaths': total_deaths,
                'req_kills': req_kills,
                'req_deaths': req_deaths,
                'compliant': compliant,
                'has_reqs': reqs is not None
            })

        # Sort: Non-compliant first, then by power descending
        compliance_data.sort(key=lambda x: (x['compliant'], -x['power']))
        
        view = CompliancePaginationView(compliance_data, "📋 Compliance Report", current_kvk)
        view.update_buttons()
        await interaction.followup.send(embed=view.create_embed(), view=view)
        
        await self.log_to_channel(interaction, "Check Compliance", f"KvK: {current_kvk}\nChecked {len(compliance_data)} players")

    @app_commands.command(name="help", description="📖 Show all available commands.")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(title="📖 KD Bot - Command Guide", color=discord.Color.blue())
        
        # Admin commands
        admin_cmds = (
            "🔧 **Admin Slash Commands:**\n"
            "`/set_kvk` - Select KvK season\n"
            "`/kvk_setup` - Interactive setup wizard\n"
            "`/status` - View current KvK status\n"
            "`/view_requirements` - Show requirements table\n"
            "`/set_requirements_text` - Enter requirements via text\n"
            "`/calculate_period <name>` - Calculate period results\n"
            "`/check_compliance` - Export compliance report\n"
            "`/dkp_leaderboard` - Show DKP rankings\n"
            "`/finish_kvk` - Archive current KvK\n"
            "`/list_linked_accounts` - View all linked accounts\n"
            "`/admin_unlink_account` - Unlink game account\n"
            "`/export_logs` - Export admin logs\n"
            "`/export_leaderboard` - Export DKP leaderboard\n"
            "`/set_reward_role` - Set role for compliant players\n"
            "`/reset_bot` - ⚠️ Delete ALL data"
        )
        
        # Admin message commands
        msg_cmds = (
            "\n📤 **Admin Upload Commands (Message with file):**\n"
            "`!upload_players` - Upload kingdom player list\n"
            "`!upload_requirements` - Upload requirements from Excel\n"
            "`!upload_snapshot \"Period\" start/end` - Upload period data"
        )
        
        # Player commands
        player_cmds = (
            "\n👤 **Player Commands:**\n"
            "`/start` - Open main dashboard\n"
            "`/link` - Link your game account\n"
            "`/unlink` - Unlink game account\n"
            "`/my_stats` - View your statistics\n"
            "`/kingdom_stats` - View kingdom statistics\n"
            "`/dkp_leaderboard` - View DKP rankings"
        )
        
        embed.description = admin_cmds + msg_cmds + player_cmds
        embed.set_footer(text="DKP Formula: T4×4 + T5×10 + Deaths×15")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="dkp_leaderboard", description="🏆 Show DKP leaderboard (T4×4 + T5×10 + Deaths×15).")
    async def dkp_leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        current_kvk = db_manager.get_current_kvk_name()
        if not current_kvk or current_kvk == "Not set":
            await interaction.followup.send("❌ No active KvK season set.", ephemeral=True)
            return
        
        # Get all calculated stats
        all_stats = db_manager.get_all_kvk_stats(current_kvk)
        if not all_stats:
            await interaction.followup.send("❌ No player statistics available. Calculate periods first.", ephemeral=True)
            return
        
        # Calculate DKP for each player and sort
        # DKP = T4*4 + T5*10 + Deaths*15
        player_dkp = []
        for stat in all_stats:
            t4 = stat.get('total_t4_kills', 0) or 0
            t5 = stat.get('total_t5_kills', 0) or 0
            deaths = stat.get('total_deaths', 0) or 0
            dkp = (t4 * 4) + (t5 * 10) + (deaths * 15)
            
            # Check compliance
            reqs = db_manager.get_requirements(current_kvk, stat['total_power'])
            compliant = False
            if reqs:
                total_kills = t4 + t5
                kills_met = total_kills >= reqs['required_kills']
                deaths_met = deaths >= reqs['required_deaths']
                compliant = kills_met and deaths_met
            
            player_dkp.append({
                'player_id': stat['player_id'],
                'player_name': stat['player_name'],
                't4': t4,
                't5': t5,
                'deaths': deaths,
                'dkp': dkp,
                'compliant': compliant
            })
        
        # Sort by DKP descending
        player_dkp.sort(key=lambda x: x['dkp'], reverse=True)
        
        view = LeaderboardPaginationView(player_dkp, "🏆 DKP Leaderboard", current_kvk)
        view.update_buttons()
        await interaction.followup.send(embed=view.create_embed(), view=view)

    # ===== MESSAGE-BASED COMMANDS FOR FILE UPLOADS =====
    # These are more reliable than slash commands for file uploads
    
    def is_admin_ctx(self, ctx: commands.Context) -> bool:
        """Check if user has admin role (for message commands)."""
        if not ctx.guild:
            return False
        for role_id in self.admin_role_ids:
            admin_role = discord.utils.get(ctx.guild.roles, id=role_id)
            if admin_role and admin_role in ctx.author.roles:
                return True
        return False
    
    @commands.command(name="upload_requirements")
    async def msg_upload_requirements(self, ctx: commands.Context):
        """Upload requirements from an Excel file. Attach the file to your message with this command."""
        if not self.is_admin_ctx(ctx):
            await ctx.send("❌ You do not have permissions to use this command.")
            return
            
        if not ctx.message.attachments:
            await ctx.send("❌ Please attach an Excel file (.xlsx) to your message.\n**Usage:** `!upload_requirements` with an attached Excel file")
            return
        
        attachment = ctx.message.attachments[0]
        if not attachment.filename.endswith('.xlsx'):
            await ctx.send("❌ Please upload a valid Excel file (.xlsx).")
            return
        
        current_kvk = db_manager.get_current_kvk_name()
        if not current_kvk or current_kvk == "Not set":
            await ctx.send("❌ Please set the current KvK season first using `/set_kvk`.")
            return
        
        # Show processing message
        msg = await ctx.send("⏳ Processing file...")
        
        # Save file temporarily
        file_path = f"temp_uploads/{attachment.filename}"
        if not os.path.exists("temp_uploads"):
            os.makedirs("temp_uploads")
        
        await attachment.save(file_path)
        
        success = db_manager.import_requirements(file_path, current_kvk)
        os.remove(file_path)
        
        if success:
            await msg.edit(content=f"✅ Requirements for '{current_kvk}' uploaded successfully!")
        else:
            await msg.edit(content="❌ Failed to import requirements.\n\n**Expected columns:**\n• `min power`\n• `max power`\n• `required kills` (T4+T5)\n• `required death` or `required deaths`")

    @commands.command(name="upload_players")
    async def msg_upload_players(self, ctx: commands.Context):
        """Upload the base list of kingdom players.
        
        This is the initial list of players participating in KvK.
        Their power from this list will be used to determine DKP requirements.
        Usage: !upload_players with an attached Excel file.
        """
        if not self.is_admin_ctx(ctx):
            await ctx.send("❌ You do not have permissions to use this command.")
            return
            
        if not ctx.message.attachments:
            await ctx.send("❌ Please attach an Excel file (.xlsx) to your message.\n**Usage:** `!upload_players` with an attached Excel file\n\n**Expected columns:** `Governor ID`, `Governor Name`, `Power`")
            return
        
        attachment = ctx.message.attachments[0]
        if not attachment.filename.endswith('.xlsx'):
            await ctx.send("❌ Please upload a valid Excel file (.xlsx).")
            return
        
        current_kvk = db_manager.get_current_kvk_name()
        if not current_kvk or current_kvk == "Not set":
            await ctx.send("❌ Please set the current KvK season first using `/set_kvk`.")
            return
        
        # Show processing message
        msg = await ctx.send("⏳ Processing file...")
        
        # Save file temporarily
        file_path = f"temp_uploads/{attachment.filename}"
        if not os.path.exists("temp_uploads"):
            os.makedirs("temp_uploads")
        
        await attachment.save(file_path)
        
        success, count = db_manager.import_kingdom_players(file_path, current_kvk)
        os.remove(file_path)
        
        if success:
            await msg.edit(content=f"✅ Successfully imported **{count}** kingdom players for '{current_kvk}'!\n\nPlayers can now use `/link <Governor ID>` to link their accounts.")
        else:
            await msg.edit(content="❌ Failed to import players.\n\n**Expected columns:**\n• `Governor ID` or `ID`\n• `Governor Name` or `Name`\n• `Power`")


    @commands.command(name="upload_snapshot")
    async def msg_upload_snapshot(self, ctx: commands.Context, period_name: str, snapshot_type: str):
        """Upload a snapshot from an Excel file.
        
        Usage: !upload_snapshot "Period Name" start/end
        Attach the Excel file to your message.
        """
        if not self.is_admin_ctx(ctx):
            await ctx.send("❌ You do not have permissions to use this command.")
            return
            
        if not ctx.message.attachments:
            await ctx.send("❌ Please attach an Excel file (.xlsx) to your message.\n**Usage:** `!upload_snapshot \"Period Name\" start` with an attached Excel file")
            return
        
        attachment = ctx.message.attachments[0]
        if not attachment.filename.endswith('.xlsx'):
            await ctx.send("❌ Please upload a valid Excel file (.xlsx).")
            return
        
        if snapshot_type.lower() not in ['start', 'end']:
            await ctx.send("❌ Snapshot type must be 'start' or 'end'.")
            return
        
        current_kvk = db_manager.get_current_kvk_name()
        if not current_kvk or current_kvk == "Not set":
            await ctx.send("❌ Please set the current KvK season first using `/set_kvk`.")
            return
        
        # Show processing message
        msg = await ctx.send("⏳ Processing file...")
        
        # Save file temporarily
        file_path = f"temp_uploads/{attachment.filename}"
        if not os.path.exists("temp_uploads"):
            os.makedirs("temp_uploads")
        
        await attachment.save(file_path)
        
        success = db_manager.import_snapshot(file_path, current_kvk, period_name, snapshot_type.lower())
        os.remove(file_path)
        
        if success:
            await msg.edit(content=f"✅ Snapshot '{snapshot_type}' for period '{period_name}' uploaded successfully!")
        else:
            await msg.edit(content="❌ Failed to import snapshot. Check that your Excel file has the correct columns.")

    @commands.command(name="export_db")
    async def msg_export_db(self, ctx: commands.Context):
        """Export the entire database file (Backup)."""
        if not self.is_admin_ctx(ctx):
            await ctx.send("❌ You do not have permissions to use this command.")
            return
            
        db_path = db_manager.DATABASE_PATH
        if not os.path.exists(db_path):
            await ctx.send("❌ Database file not found.")
            return
            
        await ctx.send("📦 Exporting database...", file=discord.File(db_path, filename="kvk_data_backup.db"))


async def setup(bot: commands.Bot):
    # Add the cog to the bot
    await bot.add_cog(Admin(bot))

