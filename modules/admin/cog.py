import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import logging
import io
import csv
from database import database_manager as db_manager
from .views import (
    AdminPanelView, KvKSelectView, FinishKvKConfirmView, 
    ResetBotConfirmView, ClearFortsConfirmView, WizardKvKSelectView,
    DeletePlayerConfirmView, DeleteKvKConfirmView, LeaderboardPaginationView,
    LinkedAccountsPaginationView, CompliancePaginationView
)
from .modals import RequirementsModal, GlobalRequirementsModal

logger = logging.getLogger('discord_bot.admin')

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.admin_role_ids = []
        
        # Load multiple admin role IDs from environment variables
        role_ids_str = os.getenv('ADMIN_ROLE_IDS', '')
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
        
        # Start background tasks
        self.backup_loop.start()

    def cog_unload(self):
        self.backup_loop.cancel()

    @tasks.loop(hours=24)
    async def backup_loop(self):
        """Background task to backup database every 24 hours."""
        log_channel_id = int(os.getenv('LOG_CHANNEL_ID', 0))
        if log_channel_id == 0:
            return

        channel = self.bot.get_channel(log_channel_id)
        if not channel:
            return

        backup_path = db_manager.backup_database()
        if backup_path:
            try:
                file = discord.File(backup_path)
                await channel.send(f"📦 **Daily Database Backup**", file=file)
                try:
                    os.remove(backup_path)
                except:
                    pass
            except Exception as e:
                logger.error(f"Failed to send auto-backup: {e}")
    
    @backup_loop.before_loop
    async def before_backup_loop(self):
        await self.bot.wait_until_ready()

    def is_admin(self, interaction: discord.Interaction):
        if not self.admin_role_ids:
            return False
        for role_id in self.admin_role_ids:
            admin_role = discord.utils.get(interaction.guild.roles, id=role_id)
            if admin_role and admin_role in interaction.user.roles:
                return True
        return False

    def is_admin_ctx(self, ctx: commands.Context) -> bool:
        """Check if user has admin role (for message commands)."""
        if not ctx.guild:
            return False
        for role_id in self.admin_role_ids:
            admin_role = discord.utils.get(ctx.guild.roles, id=role_id)
            if admin_role and admin_role in ctx.author.roles:
                return True
        return False

    async def log_to_channel(self, interaction: discord.Interaction, action: str, details: str):
        """Logs an admin action to the specified Discord channel and database."""
        log_channel_id = int(os.getenv('LOG_CHANNEL_ID', 0))
        if log_channel_id != 0:
            channel = self.bot.get_channel(log_channel_id)
            if channel:
                embed = discord.Embed(title="🛡️ Admin Action Logged", color=discord.Color.blue(), timestamp=interaction.created_at)
                embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
                embed.add_field(name="Action", value=action, inline=True)
                embed.add_field(name="Details", value=details, inline=False)
                embed.set_footer(text=f"ID: {interaction.user.id}")
                try:
                    await channel.send(embed=embed)
                except Exception as e:
                    logger.error(f"Failed to send log message: {e}")
        
        db_manager.log_admin_action(interaction.user.id, interaction.user.name, action, details)

    @app_commands.command(name='admin_panel', description='Open the central administrative dashboard.')
    @app_commands.default_permissions(administrator=True)
    async def admin_panel(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ You do not have permissions.", ephemeral=False)
            return

        embed = discord.Embed(
            title="👑 Admin Control Panel",
            description="Welcome to the central management hub. Use the buttons below to manage KvK seasons, player stats, and fort participation.",
            color=discord.Color.dark_red()
        )
        embed.add_field(name="Current Season", value=f"**{db_manager.get_current_kvk_name() or 'Not set'}**", inline=True)
        await interaction.response.send_message(embed=embed, view=AdminPanelView(self))

    @app_commands.command(name="admin_backup", description="Create and download a database backup.")
    @app_commands.default_permissions(administrator=True)
    async def admin_backup(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return

        await interaction.response.defer(ephemeral=False)
        backup_path = db_manager.backup_database()
        if backup_path:
            try:
                file = discord.File(backup_path)
                await interaction.followup.send("📦 **Database Backup Created**", file=file)
                await self.log_to_channel(interaction, "Backup Created", "Manual backup via /admin_backup")
                try:
                    os.remove(backup_path)
                except:
                    pass
            except Exception as e:
                await interaction.followup.send(f"❌ Failed to upload backup: {e}")
        else:
            await interaction.followup.send("❌ Failed to create backup file.")

    @app_commands.command(name="export_logs", description="Export all admin logs as a CSV file.")
    @app_commands.default_permissions(administrator=True)
    async def export_logs(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return
            
        logs = db_manager.get_all_admin_logs()
        if not logs:
            await interaction.response.send_message("No logs found.", ephemeral=False)
            return
            
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Admin ID', 'Admin Name', 'Action', 'Details', 'Timestamp'])
        for log in logs:
            writer.writerow([log['id'], log['admin_id'], log['admin_name'], log['action'], log['details'], log['timestamp']])
            
        output.seek(0)
        file = discord.File(io.BytesIO(output.getvalue().encode()), filename="admin_logs.csv")
        await interaction.response.send_message(f"Found {len(logs)} logs.", file=file, ephemeral=False)

    @app_commands.command(name="set_kvk", description="Sets the current KvK season (admin only).")
    @app_commands.default_permissions(administrator=True)
    async def set_kvk_command(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return
        await interaction.response.send_message("Select the active KvK season:", view=KvKSelectView(interaction, self), ephemeral=False)

    @app_commands.command(name="set_kvk_dates", description="Set start and end dates for a KvK season.")
    @app_commands.describe(kvk_name="Select the KvK season", start_date="YYYY-MM-DD", end_date="YYYY-MM-DD")
    @app_commands.default_permissions(administrator=True)
    async def set_kvk_dates(self, interaction: discord.Interaction, kvk_name: str, start_date: str, end_date: str):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return

        try:
            from datetime import datetime
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            await interaction.response.send_message("❌ Invalid date format. Use YYYY-MM-DD.", ephemeral=False)
            return

        if db_manager.set_kvk_dates(kvk_name, start_date, end_date):
            await interaction.response.send_message(f"✅ Dates for **{kvk_name}** updated: {start_date} to {end_date}.", ephemeral=False)
            await self.log_to_channel(interaction, "Set KvK Dates", f"KvK: {kvk_name}\nStart: {start_date}\nEnd: {end_date}")
        else:
            await interaction.response.send_message(f"❌ Failed to set dates. Season `{kvk_name}` not found.", ephemeral=False)

    @set_kvk_dates.autocomplete('kvk_name')
    async def set_kvk_dates_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        seasons = db_manager.get_played_seasons()
        return [app_commands.Choice(name=s['label'], value=s['value']) for s in seasons if current.lower() in s['label'].lower()][:25]

    @app_commands.command(name="admin_cleanup_players", description="View and delete player data.")
    @app_commands.describe(player_id="The player ID to delete")
    @app_commands.default_permissions(administrator=True)
    async def admin_cleanup_players(self, interaction: discord.Interaction, player_id: str = None):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return

        if not player_id:
            await interaction.response.send_message("Use `/admin_cleanup_players player_id:12345` to delete a player.", ephemeral=False)
            return

        try: pid = int(player_id)
        except ValueError:
            await interaction.response.send_message("❌ Invalid Player ID.", ephemeral=False)
            return

        await interaction.response.send_message(f"⚠️ Are you sure you want to delete ALL data for player ID `{pid}`?", view=DeletePlayerConfirmView(pid, self), ephemeral=False)

    @app_commands.command(name="set_global_requirements", description="Set global requirements for 'Total Stats' view.")
    @app_commands.default_permissions(administrator=True)
    async def set_global_requirements(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return
        await interaction.response.send_modal(GlobalRequirementsModal(self))

    @app_commands.command(name="status", description="Check the current status of the bot.")
    @app_commands.default_permissions(administrator=True)
    async def status(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return

        kvk_name = db_manager.get_current_kvk_name()
        embed = discord.Embed(title="Bot Status", color=discord.Color.gold())
        if kvk_name and kvk_name != "Not set":
            embed.add_field(name="Current KvK Season", value=f"**{kvk_name}**", inline=False)
            reqs = db_manager.get_all_requirements(kvk_name)
            embed.add_field(name="Requirements", value=f"✅ Set ({len(reqs)} brackets)" if reqs else "⚠️ Not set", inline=False)
        else:
            embed.add_field(name="Current KvK Season", value="❌ Not selected", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="set_requirements_text", description="Enter KvK requirements via text paste.")
    @app_commands.default_permissions(administrator=True)
    async def set_requirements_text(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return
        current_kvk = db_manager.get_current_kvk_name()
        if not current_kvk or current_kvk == "Not set":
            await interaction.response.send_message("Please set the current KvK season first.", ephemeral=False)
            return
        await interaction.response.send_modal(RequirementsModal(self))

    @app_commands.command(name="finish_kvk", description="Finish the current KvK season and archive data.")
    @app_commands.default_permissions(administrator=True)
    async def finish_kvk(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return
        current_kvk_name = db_manager.get_current_kvk_name()
        if not current_kvk_name or current_kvk_name == "Not set":
            await interaction.response.send_message("No KvK season is currently active.", ephemeral=False)
            return
        await interaction.response.send_message(f"Are you sure you want to finish **{current_kvk_name}**?", view=FinishKvKConfirmView(interaction, current_kvk_name, self), ephemeral=False)

    @app_commands.command(name="list_kvk_seasons", description="Show all KvK seasons.")
    @app_commands.default_permissions(administrator=True)
    async def list_kvk_seasons(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return
        seasons = db_manager.get_played_seasons()
        if not seasons:
            await interaction.response.send_message("No played/archived seasons found.", ephemeral=False)
            return
        embed = discord.Embed(title="📅 Played KvK Seasons", color=discord.Color.blue())
        for s in seasons:
            status = "ACTIVE" if s.get('is_active') else "Archived" if s.get('is_archived') else "Inactive"
            embed.add_field(name=f"{s['label']} (`{s['value']}`)", value=f"Status: {status}", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="delete_kvk_season", description="⚠️ Permanently delete an archived KvK season.")
    @app_commands.describe(season="Select archived season to delete")
    @app_commands.default_permissions(administrator=True)
    async def delete_kvk_season(self, interaction: discord.Interaction, season: str):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return
        seasons = db_manager.get_all_seasons()
        target = next((s for s in seasons if s['value'] == season), None)
        if not target or not target.get('is_archived'):
            await interaction.response.send_message("❌ Season not found or not archived.", ephemeral=False)
            return
        await interaction.response.send_message(f"⚠️ **DANGER: PERMANENT DELETION** ⚠️\nDelete **{target['label']}**?", view=DeleteKvKConfirmView(interaction, season, self), ephemeral=False)

    @delete_kvk_season.autocomplete('season')
    async def delete_kvk_season_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        seasons = db_manager.get_all_seasons()
        return [app_commands.Choice(name=s['label'], value=s['value']) for s in seasons if s.get('is_archived') and current.lower() in s['label'].lower()][:25]

    @app_commands.command(name="rename_kvk_season", description="✏️ Rename an archived KvK season.")
    @app_commands.describe(old_name="Select the season to rename", new_name="The new name (e.g. 'KvK 1 (Win)')")
    @app_commands.default_permissions(administrator=True)
    async def rename_kvk_season(self, interaction: discord.Interaction, old_name: str, new_name: str):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return
            
        await interaction.response.defer(ephemeral=False)
        
        success, msg = db_manager.rename_kvk_season(old_name, new_name)
        if success:
            await interaction.followup.send(f"✅ {msg}")
            await self.log_to_channel(interaction, "Rename KvK Season", f"Old: {old_name}\nNew: {new_name}")
        else:
            await interaction.followup.send(f"❌ Failed: {msg}")

    @rename_kvk_season.autocomplete('old_name')
    async def rename_kvk_season_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        seasons = db_manager.get_played_seasons()
        return [app_commands.Choice(name=s['label'], value=s['value']) for s in seasons if current.lower() in s['label'].lower()][:25]

    @app_commands.command(name="calculate_period", description="Calculate results for a period.")
    @app_commands.describe(period_name="Name of the period")
    @app_commands.default_permissions(administrator=True)
    async def calculate_period(self, interaction: discord.Interaction, period_name: str):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return
        current_kvk = db_manager.get_current_kvk_name()
        if not current_kvk or current_kvk == "Not set":
            await interaction.response.send_message("No active KvK.", ephemeral=False)
            return
        await interaction.response.defer()
        from core import calculation
        success, message = calculation.calculate_period_results(current_kvk, period_name)
        await interaction.followup.send(f"{'✅' if success else '❌'} {message}")

    @app_commands.command(name="view_requirements", description="View current KvK requirements.")
    @app_commands.default_permissions(administrator=True)
    async def view_requirements(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return
        current_kvk = db_manager.get_current_kvk_name()
        reqs = db_manager.get_all_requirements(current_kvk)
        if not reqs:
            await interaction.response.send_message("No requirements set.", ephemeral=False)
            return
        embed = discord.Embed(title=f"Requirements for {current_kvk}", color=discord.Color.blue())
        desc = ""
        for req in reqs:
            desc += f"**{req['min_power']/1e6:.0f}M+**: Kills: {req['required_kills']/1e6:.1f}M | Deads: {req['required_deaths']/1e6:.1f}M\n"
        embed.description = desc
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="list_linked_accounts", description="List all linked Discord accounts.")
    @app_commands.default_permissions(administrator=True)
    async def list_linked_accounts(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return
        accounts = db_manager.get_all_linked_accounts_full()
        if not accounts:
            await interaction.response.send_message("No accounts linked.", ephemeral=False)
            return
        view = LinkedAccountsPaginationView(accounts)
        view.update_buttons()
        await interaction.response.send_message(embed=view.create_embed(), view=view)

    @app_commands.command(name="admin_link_account", description="Link a player ID to a Discord user.")
    @app_commands.describe(user="The Discord user", player_id="The game ID")
    @app_commands.default_permissions(administrator=True)
    async def admin_link_account(self, interaction: discord.Interaction, user: discord.User, player_id: int):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return
        existing = db_manager.get_linked_accounts(user.id)
        if db_manager.link_account(user.id, player_id, 'main' if not existing else 'alt'):
            await interaction.response.send_message(f"✅ Linked `{player_id}` to {user.mention}.")
        else:
            await interaction.response.send_message("❌ Failed to link.")

    @app_commands.command(name="admin_unlink_account", description="Unlink a game account.")
    @app_commands.describe(player_id="The game ID")
    @app_commands.default_permissions(administrator=True)
    async def admin_unlink_account(self, interaction: discord.Interaction, player_id: int):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return
        all_links = db_manager.get_all_linked_accounts_full()
        target = next((acc for acc in all_links if acc['player_id'] == player_id), None)
        if target and db_manager.unlink_account(target['discord_id'], player_id):
            await interaction.response.send_message(f"✅ Unlinked `{player_id}`.")
        else:
            await interaction.response.send_message("❌ Not found or failed.")

    @app_commands.command(name="export_leaderboard", description="Export DKP leaderboard as CSV.")
    @app_commands.default_permissions(administrator=True)
    async def export_leaderboard(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return
        current_kvk = db_manager.get_current_kvk_name()
        await interaction.response.defer()
        all_stats = db_manager.get_all_kvk_stats(current_kvk)
        if not all_stats:
            await interaction.followup.send("No stats.")
            return
            
        formula = db_manager.get_dkp_formula()
        t4_w, t5_w, death_w = formula.get('t4', 4), formula.get('t5', 10), formula.get('deaths', 15)
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Name', 'Power', 'KP', 'Deaths', 'T4', 'T5', f'DKP (T4x{t4_w} T5x{t5_w} Dx{death_w})'])
        for s in all_stats:
            dkp = (s.get('total_t4_kills',0)*t4_w) + (s.get('total_t5_kills',0)*t5_w) + (s.get('total_deaths',0)*death_w)
            writer.writerow([s['player_id'], s['player_name'], s['total_power'], s['total_kill_points'], s['total_deaths'], s['total_t4_kills'], s['total_t5_kills'], dkp])
        output.seek(0)
        file = discord.File(io.BytesIO(output.getvalue().encode()), filename=f"leaderboard_{current_kvk}.csv")
        await interaction.followup.send(file=file)

    @app_commands.command(name="set_reward_role", description="Set reward role.")
    @app_commands.describe(role="The role")
    @app_commands.default_permissions(administrator=True)
    async def set_reward_role(self, interaction: discord.Interaction, role: discord.Role):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return
        if db_manager.set_reward_role(role.id):
            await interaction.response.send_message(f"✅ Role set to {role.mention}")
        else:
            await interaction.response.send_message("❌ Failed.")

    @app_commands.command(name="reset_bot", description="⚠️ WIPE ALL DATA.")
    @app_commands.default_permissions(administrator=True)
    async def reset_bot(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return
        await interaction.response.defer()
        await interaction.followup.send("⚠️ **DANGER ZONE** ⚠️ Wipe all data?", view=ResetBotConfirmView(self))

    @app_commands.command(name="admin_clear_forts", description="⚠️ Clear all fort data.")
    @app_commands.default_permissions(administrator=True)
    async def admin_clear_forts(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return
        await interaction.response.send_message("⚠️ Clear all fort data?", view=ClearFortsConfirmView(self), ephemeral=False)

    @app_commands.command(name="kvk_setup", description="🧙‍♂️ Guided wizard.")
    @app_commands.default_permissions(administrator=True)
    async def kvk_setup(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return
        await interaction.response.defer()
        await interaction.followup.send("🧙‍♂️ KvK Setup Wizard", view=WizardKvKSelectView(self))

    @app_commands.command(name="check_compliance", description="Check player compliance.")
    @app_commands.default_permissions(administrator=True)
    async def check_compliance(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=False)
            return
        current_kvk = db_manager.get_current_kvk_name()
        await interaction.response.defer()
        all_stats = db_manager.get_all_kvk_stats(current_kvk)
        if not all_stats:
            await interaction.followup.send("No stats.")
            return
        data = []
        for p in all_stats:
            reqs = db_manager.get_requirements(current_kvk, p['total_power'])
            rk = reqs['required_kills'] if reqs else 0
            rd = reqs['required_deaths'] if reqs else 0
            tk = (p.get('total_t4_kills',0) or 0) + (p.get('total_t5_kills',0) or 0)
            td = p.get('total_deaths',0) or 0
            compliant = tk >= rk and td >= rd and reqs is not None
            data.append({'name': p['player_name'], 'power': p['total_power'], 'kills': tk, 'deaths': td, 'req_kills': rk, 'req_deaths': rd, 'compliant': compliant})
        data.sort(key=lambda x: (x['compliant'], -x['power']))
        view = CompliancePaginationView(data, "📋 Compliance Report", current_kvk)
        view.update_buttons()
        await interaction.followup.send(embed=view.create_embed(), view=view)

    @app_commands.command(name="help", description="📖 Show all commands.")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(title="📖 KD Bot - Command Guide", color=discord.Color.blue())
        embed.description = "Use `/admin_panel` for all administrative tasks."
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="dkp_leaderboard", description="🏆 Show DKP leaderboard.")
    @app_commands.describe(season="Optional: Select a specific season")
    async def dkp_leaderboard(self, interaction: discord.Interaction, season: str = None):
        await interaction.response.defer()
        target = season or db_manager.get_current_kvk_name()
        all_stats = db_manager.get_all_kvk_stats(target)
        if not all_stats:
            await interaction.followup.send("No stats.")
            return
        player_dkp = []
        formula = db_manager.get_dkp_formula()
        t4_w, t5_w, death_w = formula.get('t4', 4), formula.get('t5', 10), formula.get('deaths', 15)
        
        for s in all_stats:
            t4, t5, d = s.get('total_t4_kills',0) or 0, s.get('total_t5_kills',0) or 0, s.get('total_deaths',0) or 0
            dkp = (t4 * t4_w) + (t5 * t5_w) + (d * death_w)
            player_dkp.append({'player_id': s['player_id'], 'player_name': s['player_name'], 'power': s.get('total_power',0), 't4': t4, 't5': t5, 'deaths': d, 'dkp': dkp})
        player_dkp.sort(key=lambda x: x['dkp'], reverse=True)
        view = LeaderboardPaginationView(player_dkp, f"🏆 DKP Leaderboard (T4x{t4_w} T5x{t5_w} Dx{death_w})", target)
        view.update_buttons()
        await interaction.followup.send(embed=view.create_embed(), view=view)

    @dkp_leaderboard.autocomplete('season')
    async def season_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        # Use get_played_seasons to exclude templates
        from database import database_manager as db_manager # Ensure import
        # Note: database_manager proxy needs to expose get_played_seasons. 
        # Since database_manager imports * from .kvk, it should work if __all__ or wildcards are correct.
        # Assuming db_manager has it now.
        
        # We need to fetch via db_manager which proxies to kvk.py
        seasons = db_manager.get_played_seasons()
        
        # Also include 'Current' if there is one active? 
        # The list already has active and archived.
        
        return [app_commands.Choice(name=s['label'], value=s['value']) for s in seasons if current.lower() in s['label'].lower()][:25]

    @commands.command(name="upload_requirements")
    async def msg_upload_requirements(self, ctx: commands.Context):
        if not self.is_admin_ctx(ctx):
            await ctx.send("❌ You do not have permissions to use this command.")
            return
        if not ctx.message.attachments: return
        attachment = ctx.message.attachments[0]
        current_kvk = db_manager.get_current_kvk_name()
        file_path = f"temp_uploads/{attachment.filename}"
        if not os.path.exists("temp_uploads"): os.makedirs("temp_uploads")
        await attachment.save(file_path)
        success = db_manager.import_requirements(file_path, current_kvk)
        os.remove(file_path)
        await ctx.send(f"{'✅' if success else '❌'} Requirements upload {'successful' if success else 'failed'}.")

    @commands.command(name="upload_players")
    async def msg_upload_players(self, ctx: commands.Context):
        if not self.is_admin_ctx(ctx):
            await ctx.send("❌ You do not have permissions to use this command.")
            return
        if not ctx.message.attachments: return
        attachment = ctx.message.attachments[0]
        current_kvk = db_manager.get_current_kvk_name()
        file_path = f"temp_uploads/{attachment.filename}"
        if not os.path.exists("temp_uploads"): os.makedirs("temp_uploads")
        await attachment.save(file_path)
        success, count = db_manager.import_kingdom_players(file_path, current_kvk)
        os.remove(file_path)
        await ctx.send(f"{'✅' if success else '❌'} Imported {count} players.")

    @commands.command(name="upload_snapshot")
    async def msg_upload_snapshot(self, ctx: commands.Context, period_name: str, snapshot_type: str):
        if not self.is_admin_ctx(ctx):
            await ctx.send("❌ You do not have permissions to use this command.")
            return
        if not ctx.message.attachments: return
        attachment = ctx.message.attachments[0]
        current_kvk = db_manager.get_current_kvk_name()
        file_path = f"temp_uploads/{attachment.filename}"
        if not os.path.exists("temp_uploads"): os.makedirs("temp_uploads")
        await attachment.save(file_path)
        success, msg = db_manager.import_snapshot(file_path, current_kvk, period_name, snapshot_type.lower())
        os.remove(file_path)
        await ctx.send(f"{'✅' if success else '❌'} {msg}")

    @commands.command(name="export_db")
    async def msg_export_db(self, ctx: commands.Context):
        if not self.is_admin_ctx(ctx):
            await ctx.send("❌ You do not have permissions to use this command.")
            return
        await ctx.send(file=discord.File(db_manager.DATABASE_PATH, filename="kvk_data_backup.db"))

    @app_commands.command(name="set_dkp_formula", description="Configure DKP formula weights.")
    @app_commands.describe(t4="Points per T4 kill", t5="Points per T5 kill", deaths="Points per death")
    @app_commands.default_permissions(administrator=True)
    async def set_dkp_formula(self, interaction: discord.Interaction, t4: int, t5: int, deaths: int):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ You do not have permissions.", ephemeral=False)
            return
        
        if db_manager.set_dkp_formula(t4, t5, deaths):
            await interaction.response.send_message(f"✅ DKP Formula Updated:\n**T4:** {t4}\n**T5:** {t5}\n**Deaths:** {deaths}", ephemeral=False)
            await self.log_to_channel(interaction, "Set DKP Formula", f"T4: {t4}, T5: {t5}, Deaths: {deaths}")
        else:
            await interaction.response.send_message("❌ Failed to update DKP formula.", ephemeral=False)

    @app_commands.command(name="add_player", description="Manually add or update a player.")
    @app_commands.describe(player_id="Game ID", name="Governor Name", power="Current Power")
    @app_commands.default_permissions(administrator=True)
    async def add_player(self, interaction: discord.Interaction, player_id: str, name: str, power: str):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ You do not have permissions.", ephemeral=False)
            return
        
        try:
            pid = int(player_id)
            pwr = int(power)
            
            # Helper to determine current KvK
            kvk = db_manager.get_current_kvk_name() or "General"
            
            if db_manager.add_new_player(pid, name, pwr, kvk):
                await interaction.response.send_message(f"✅ Player **{name}** ({pid}) added/updated with {pwr} power in **{kvk}**.", ephemeral=False)
                await self.log_to_channel(interaction, "Add Player", f"ID: {pid}, Name: {name}, Power: {pwr}")
            else:
                await interaction.response.send_message("❌ Failed to add player.", ephemeral=False)
        except ValueError:
            await interaction.response.send_message("❌ ID and Power must be numbers.", ephemeral=False)

    @app_commands.command(name="list_players", description="List top players by power.")
    @app_commands.describe(limit="Number of players to show (default 20)")
    async def list_players(self, interaction: discord.Interaction, limit: int = 20):
        await interaction.response.defer()
        kvk = db_manager.get_current_kvk_name()
        players = db_manager.get_all_kingdom_players(kvk) if kvk else []
        
        if not players:
            await interaction.followup.send("No players found for current season.")
            return

        # Sort by power descending
        players.sort(key=lambda x: x.get('power', 0), reverse=True)
        top = players[:limit]
        
        text = f"**Top {len(top)} Players (Power)**\n"
        for i, p in enumerate(top, 1):
             text += f"{i}. **{p['player_name']}** ({p['player_id']}) - ⚡ {p['power']:,}\n"
             
        # Split if too long
        if len(text) > 2000:
            text = text[:1900] + "\n...(truncated)"
            
        await interaction.followup.send(text)

    @app_commands.command(name="delete_snapshot", description="⚠️ Delete a specific snapshot batch.")
    @app_commands.describe(period="Period key (e.g. week_1)", type="start or end", kvk="Optional KvK name")
    @app_commands.default_permissions(administrator=True)
    async def delete_snapshot(self, interaction: discord.Interaction, period: str, type: str, kvk: str = None):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permissions denied.", ephemeral=False)
            return
        
        target_kvk = kvk or db_manager.get_current_kvk_name()
        type = type.lower()
        if type not in ['start', 'end']:
            await interaction.response.send_message("❌ Type must be 'start' or 'end'.", ephemeral=False)
            return

        from db_manager import kvk as kvk_db # Direct import since it's added recently? or via database_manager
        # database_manager is a proxy, need to ensure it exposes delete_snapshot.
        # Actually database_manager.py imports * from .kvk, so it should be there.
        
        if db_manager.delete_snapshot(target_kvk, period, type):
            await interaction.response.send_message(f"✅ Deleted **{type}** snapshot for **{period}** in **{target_kvk}**.", ephemeral=False)
            await self.log_to_channel(interaction, "Delete Snapshot", f"KvK: {target_kvk}, Period: {period}, Type: {type}")
        else:
            await interaction.response.send_message("❌ Failed to delete snapshot (or none found).", ephemeral=False)

    @app_commands.command(name="delete_fort_period", description="⚠️ Delete fort stats for a specific period.")
    @app_commands.describe(period="Period key (e.g. week_1)", kvk="Optional KvK name")
    @app_commands.default_permissions(administrator=True)
    async def delete_fort_period(self, interaction: discord.Interaction, period: str, kvk: str = None):
        if not self.is_admin(interaction):
            await interaction.response.send_message("❌ Permissions denied.", ephemeral=False)
            return
        
        target_kvk = kvk or db_manager.get_current_kvk_name()
        
        if db_manager.delete_fort_period(target_kvk, period):
             await interaction.response.send_message(f"✅ Deleted fort data for **{period}** in **{target_kvk}**.", ephemeral=False)
             await self.log_to_channel(interaction, "Delete Fort Period", f"KvK: {target_kvk}, Period: {period}")
        else:
             await interaction.response.send_message("❌ Failed to delete fort period (or none found).", ephemeral=False)
