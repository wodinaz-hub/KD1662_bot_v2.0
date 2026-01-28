import discord
import logging
from database import database_manager as db_manager

logger = logging.getLogger('discord_bot.admin.views')

# List of available KvK seasons (moved from admin.py)
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
        
        db_options = db_manager.get_all_seasons()
        options = []
        for opt in db_options:
            emoji = "📁" if opt['is_archived'] else "⚔️"
            label = f"{emoji} {opt['label']}"
            if opt['is_archived'] and opt['end_date']:
                label += f" (Ended: {opt['end_date']})"
                
            options.append(discord.SelectOption(
                label=label, 
                value=opt["value"], 
                description=opt.get("description")
            ))
            
        if not options:
            options = [
                discord.SelectOption(label=opt["label"], value=opt["value"], description=opt.get("description"))
                for opt in KVK_OPTIONS
            ]
        
        select = discord.ui.Select(placeholder="Choose a KvK Season...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        select = self.children[0]
        selected_kvk = select.values[0]
        
        if db_manager.set_current_kvk_name(selected_kvk):
            reqs = db_manager.get_all_requirements(selected_kvk)
            snapshots = db_manager.get_all_periods(selected_kvk)
            
            embed = discord.Embed(
                title=f"✅ KvK Season Set: {selected_kvk}",
                description="Season successfully activated! Here's what you need to do next:",
                color=discord.Color.green()
            )
            
            if reqs:
                embed.add_field(name="📋 Requirements", value=f"✅ Already set ({len(reqs)} brackets)", inline=False)
            else:
                embed.add_field(name="📋 Requirements", value="⚠️ **Not set** - Use `/set_requirements` (file) or `/set_requirements_text` (paste text)", inline=False)
            
            if snapshots:
                embed.add_field(name="📊 Player Data", value=f"✅ {len(snapshots)} period(s) uploaded", inline=False)
            else:
                embed.add_field(name="📊 Player Data", value="⚠️ **Not uploaded** - Use `/upload_snapshot` to upload Start/End snapshots", inline=False)
            
            next_steps = []
            if not reqs: next_steps.append("1️⃣ Set requirements for power brackets")
            if not snapshots: next_steps.append("2️⃣ Upload player snapshot (Start)")
            
            if next_steps:
                embed.add_field(name="📌 Next Steps", value="\n".join(next_steps), inline=False)
            else:
                embed.add_field(name="📌 Status", value="✅ All data is ready! You can use `/check_compliance` to check player stats.", inline=False)
            
            embed.set_footer(text="💡 Tip: Use /kvk_setup for a guided wizard to set everything up step-by-step")
            
            await interaction.response.edit_message(content=None, embed=embed, view=None)
            await self.admin_cog.log_to_channel(interaction, "Set KvK", f"New Season: {selected_kvk}")
        else:
            await interaction.response.edit_message(content="❌ Failed to set KvK season. Check logs.", view=None)
            await self.admin_cog.log_to_channel(interaction, "Set KvK Failed", f"Attempted: {selected_kvk}")
        self.stop()

class FinishKvKConfirmView(discord.ui.View):
    def __init__(self, original_interaction, kvk_name, admin_cog):
        super().__init__(timeout=60)
        self.original_interaction = original_interaction
        self.kvk_name = kvk_name
        self.admin_cog = admin_cog

    @discord.ui.button(label="Yes, Finish & Archive", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        from datetime import datetime
        start_date = "Unknown" 
        end_date = datetime.now().strftime("%Y-%m-%d")
        archive_name = f"{self.kvk_name} ({start_date} - {end_date})"
        
        if db_manager.archive_kvk_data(self.kvk_name, archive_name):
            db_manager.set_current_kvk_name("Not set")
            await interaction.response.edit_message(
                content=f"✅ Season **{self.kvk_name}** finished.\n📂 Data archived as: **{archive_name}**.\nBot is now ready for a new season.",
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
            await interaction.response.edit_message(content="✅ **ALL DATA HAS BEEN WIPED.** The bot is now ready for a fresh start.", view=None)
            await self.admin_cog.log_to_channel(interaction, "RESET BOT", "All data wiped.")

class ClearFortsConfirmView(discord.ui.View):
    def __init__(self, admin_cog):
        super().__init__(timeout=60)
        self.admin_cog = admin_cog

    @discord.ui.button(label="YES, CLEAR ALL FORT DATA", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if db_manager.clear_all_fort_data():
            await interaction.response.edit_message(content="✅ **ALL FORT DATA HAS BEEN CLEARED.**", view=None)
            await self.admin_cog.log_to_channel(interaction, "CLEAR FORT DATA", "All fort stats and periods cleared.")
        else:
            await interaction.response.edit_message(content="❌ Failed to clear fort data.", view=None)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Action cancelled.", view=None)
        self.stop()

class WizardConfirmationView(discord.ui.View):
    def __init__(self, kvk_name, reqs_count, admin_cog):
        super().__init__(timeout=120)
        self.kvk_name = kvk_name
        self.reqs_count = reqs_count
        self.admin_cog = admin_cog

    @discord.ui.button(label="Activate Season", style=discord.ButtonStyle.green)
    async def activate(self, interaction: discord.Interaction, button: discord.ui.Button):
        if db_manager.set_current_kvk_name(self.kvk_name):
            embed = discord.Embed(title="🎉 KvK Season Activated!", color=discord.Color.green())
            embed.add_field(name="Season", value=self.kvk_name, inline=False)
            embed.add_field(name="Requirements", value=f"{self.reqs_count} brackets set" if self.reqs_count > 0 else "Not set (or set later)", inline=False)
            embed.set_footer(text="You can now start uploading snapshots.")
            await interaction.response.edit_message(embed=embed, view=None)
            await self.admin_cog.log_to_channel(interaction, "KvK Setup Complete", f"Season: {self.kvk_name}\nReqs: {self.reqs_count}")
        else:
            await interaction.response.edit_message(content="❌ Failed to activate season. Database error.", view=None)

class WizardRequirementsView(discord.ui.View):
    def __init__(self, kvk_name, admin_cog):
        super().__init__(timeout=120)
        self.kvk_name = kvk_name
        self.admin_cog = admin_cog

    @discord.ui.button(label="Paste Text", style=discord.ButtonStyle.primary)
    async def paste_text(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .modals import WizardRequirementsModal
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

class DeletePlayerConfirmView(discord.ui.View):
    def __init__(self, player_id, admin_cog):
        super().__init__(timeout=60)
        self.player_id = player_id
        self.admin_cog = admin_cog

    @discord.ui.button(label="Yes, Delete Player", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if db_manager.delete_player(self.player_id):
            await interaction.response.edit_message(content=f"✅ Player `{self.player_id}` has been deleted from the database.", view=None)
            await self.admin_cog.log_to_channel(interaction, "Delete Player", f"Deleted ID: {self.player_id}")
        else:
            await interaction.response.send_message("❌ Failed to delete player. Check logs.", view=None)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Deletion cancelled.", view=None)
        self.stop()

class DeleteKvKConfirmView(discord.ui.View):
    def __init__(self, original_interaction, season_name, admin_cog):
        super().__init__(timeout=60)
        self.original_interaction = original_interaction
        self.season_name = season_name
        self.admin_cog = admin_cog

    @discord.ui.button(label="YES, DELETE PERMANENTLY", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        # 1. Create a final backup before deletion
        backup_path = db_manager.backup_database()
        if backup_path:
            try:
                file = discord.File(backup_path, filename=f"pre_delete_{self.season_name}.db")
                await self.admin_cog.log_to_channel(interaction, "Pre-Deletion Backup", f"Season: {self.season_name}")
                # We can't easily send the file to the log channel here without more logic, 
                # but we can try to send it to the same channel where the command was used.
                await interaction.followup.send("📦 **Pre-deletion backup created.**", file=file)
            except Exception as e:
                logger.error(f"Failed to send pre-deletion backup: {e}")

        # 2. Delete the season
        success, message = db_manager.delete_kvk_season(self.season_name)
        if success:
            await interaction.followup.send(f"✅ **{self.season_name}** has been permanently deleted.")
            await self.admin_cog.log_to_channel(interaction, "Delete KvK Season", f"Season: {self.season_name}")
        else:
            await interaction.followup.send(f"❌ Failed to delete season: {message}")
        
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Deletion cancelled.", view=None)
        self.stop()

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
        embed = discord.Embed(title=f"{self.title} - {self.kvk_name}", description="**Formula:** T4×4 + T5×10 + Deaths×15", color=discord.Color.gold())
        leaderboard_text = ""
        for i, player in enumerate(page_data, start + 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**{i}.**"
            def fmt(n): return f"{n:,}"
            def fmt_short(n):
                if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
                if n >= 1_000: return f"{n/1_000:.1f}K"
                return str(n)
            player_name = player['player_name']
            if len(player_name) > 20: player_name = player_name[:17] + "..."
            leaderboard_text += f"{medal} **{player_name}**\n   🏆 **{fmt(player['dkp'])} DKP** | ⚡ {fmt_short(player.get('power', 0))}\n   ⚔️ T4: {fmt_short(player['t4'])} | T5: {fmt_short(player['t5'])} | 💀 {fmt_short(player['deaths'])}\n"
            if i < start + len(page_data): leaderboard_text += "\n"
        if not leaderboard_text: leaderboard_text = "No data available"
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
        embed = discord.Embed(title="🔗 Linked Accounts", color=discord.Color.blue())
        text = ""
        for acc in page_data:
            player_name = acc.get('player_name') or "Unknown Name"
            player_id = acc['player_id']
            discord_id = acc['discord_id']
            acc_type = acc.get('account_type') or ('main' if acc.get('is_main_account') else 'alt')
            type_emoji = "🏠" if acc_type == 'main' else "👤" if acc_type == 'alt' else "🚜"
            type_str = acc_type.capitalize()
            text += f"**{player_name}** (`{player_id}`)\nLinked to: <@{discord_id}>\n{type_emoji} **{type_str}**\n" + "─" * 20 + "\n"
        if not text: text = "No accounts found."
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

class CompliancePaginationView(discord.ui.View):
    def __init__(self, data, title, kvk_name):
        super().__init__(timeout=180)
        self.data = data
        self.title = title
        self.kvk_name = kvk_name
        self.per_page = 8
        self.current_page = 0
        self.total_pages = (len(data) - 1) // self.per_page + 1

    def create_embed(self):
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_data = self.data[start:end]
        embed = discord.Embed(title=f"{self.title} - {self.kvk_name}", description="✅ = Met | ❌ = Failed\nFormat: Current / Required", color=discord.Color.blue())
        for player in page_data:
            status_icon = "✅" if player['compliant'] else "❌"
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

class AdminPanelView(discord.ui.View):
    def __init__(self, admin_cog):
        super().__init__(timeout=300)
        self.admin_cog = admin_cog

    @discord.ui.button(label="⚙️ Set KvK", style=discord.ButtonStyle.primary, row=0)
    async def set_kvk(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.admin_cog.set_kvk_command.callback(self.admin_cog, interaction)

    @discord.ui.button(label="📋 Requirements", style=discord.ButtonStyle.primary, row=0)
    async def set_reqs(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.admin_cog.set_requirements_text.callback(self.admin_cog, interaction)

    @discord.ui.button(label="📥 Upload Snapshot", style=discord.ButtonStyle.success, row=1)
    async def upload_snapshot(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("To upload a snapshot, use the command: `/upload_snapshot`", ephemeral=True)

    @discord.ui.button(label="🏰 Fort Upload", style=discord.ButtonStyle.success, row=1)
    async def fort_upload(self, interaction: discord.Interaction, button: discord.ui.Button):
        forts_cog = interaction.client.get_cog("Forts")
        if forts_cog: await forts_cog.fort_wait.callback(forts_cog, interaction)
        else: await interaction.response.send_message("❌ Forts module not found.", ephemeral=True)

    @discord.ui.button(label="📁 Archive KvK", style=discord.ButtonStyle.secondary, row=2)
    async def archive_kvk(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.admin_cog.finish_kvk.callback(self.admin_cog, interaction)

    @discord.ui.button(label="🗑️ Delete Season", style=discord.ButtonStyle.danger, row=2)
    async def delete_season(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("To delete a season, use: `/delete_kvk_season season:NAME`", ephemeral=True)

    @discord.ui.button(label="📦 Backup DB", style=discord.ButtonStyle.secondary, row=3)
    async def backup_db(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.admin_cog.admin_backup.callback(self.admin_cog, interaction)
