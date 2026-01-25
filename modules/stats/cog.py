"""
Stats Cog - Main logic for statistics commands.
Contains the Stats class with all slash commands and helper methods.
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
from database import database_manager as db_manager
from core import graphics
from .views import *
from .helpers import add_stats_fields, format_period_label

# Logging configuration
logger = logging.getLogger('stats_commands')


class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        db_manager.create_tables()

    @commands.command(name='stats')
    async def legacy_stats(self, ctx, player_id: str = None):
        """Legacy command to guide users to the new slash commands."""
        embed = discord.Embed(
            title="⚠️ Legacy Command Detected",
            description=(
                "We have moved to a new system! The `!stats` command is no longer supported.\n\n"
                "**How to use the new bot:**\n"
                "1. Type `/` to see available commands.\n"
                "2. Use `/start` to open the main dashboard.\n"
                "3. Use `/my_stats` to see your personal stats.\n"
                "4. Use `/link_account` to link your game account."
            ),
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

    @app_commands.command(name='start', description='Open the main menu dashboard.')
    async def start(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="👋 Welcome to KD1662 Stats Bot",
            description="Choose an option below to get started.",
            color=discord.Color.blue()
        )
        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)
        
        await interaction.response.send_message(embed=embed, view=StartView(self))
        await self.log_to_channel(interaction, "Command Used", "Command: /start")

    @app_commands.command(name='link_account', description='Link your game account to your Discord.')
    async def link_account(self, interaction: discord.Interaction):
        await interaction.response.send_message("Select account type to link:", view=LinkAccountView(self), ephemeral=True)
        await self.log_to_channel(interaction, "Command Used", "Command: /link_account")

    @app_commands.command(name='unlink_account', description='Unlink a game account.')
    async def unlink_account(self, interaction: discord.Interaction):
        accounts = db_manager.get_linked_accounts(interaction.user.id)
        if not accounts:
            await interaction.response.send_message("You have no linked accounts.", ephemeral=True)
            return

        await interaction.response.send_message("Select account to unlink:", view=UnlinkAccountView(accounts, self), ephemeral=True)
        await self.log_to_channel(interaction, "Command Used", "Command: /unlink_account")

    @app_commands.command(name='kingdom_stats', description='Show statistics for the whole kingdom.')
    @app_commands.describe(season="Optional: Select a specific season")
    async def kingdom_stats(self, interaction: discord.Interaction, season: str = None):
        await interaction.response.defer()
        await self.kingdom_stats_logic(interaction, kvk_name=season)

    @kingdom_stats.autocomplete('season')
    async def season_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        seasons = db_manager.get_all_seasons()
        choices = []
        for s in seasons:
            emoji = "📁" if s['is_archived'] else "⚔️"
            name = s['label']
            if s['is_archived'] and s['end_date']:
                name += f" (Ended: {s['end_date']})"
            
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=s['value']))
        return choices[:25]

    @app_commands.command(name='my_stats', description='Show statistics for your linked accounts.')
    async def my_stats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.my_stats_logic(interaction)

    async def my_stats_logic(self, interaction: discord.Interaction):
        accounts = db_manager.get_linked_accounts(interaction.user.id)
        if not accounts:
            msg = "Your Discord account is not linked to any game account. Use `/link_account` or the dashboard."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=False)
            else:
                await interaction.response.send_message(msg, ephemeral=False)
            await self.log_to_channel(interaction, "Command Failed", "Command: /my_stats\nReason: No accounts linked")
            return

        current_kvk_name = db_manager.get_current_kvk_name()
        if not current_kvk_name:
            msg = "No active KvK is currently set. Please ask an administrator to set it."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=False)
            else:
                await interaction.response.send_message(msg, ephemeral=False)
            await self.log_to_channel(interaction, "Command Failed", "Command: /my_stats\nReason: No active KvK")
            return

        if len(accounts) == 1:
            await self.show_player_stats(interaction, accounts[0]['player_id'], current_kvk_name)
        else:
            # Get periods to determine which view to use
            periods = db_manager.get_all_periods(current_kvk_name) or []
            unique_periods = list(set([p['period_key'] for p in periods])) if periods else []
            
            # Use PeriodSelectView if multiple periods exist, otherwise MyStatsView
            if len(unique_periods) > 1:
                view = PeriodSelectView(accounts, current_kvk_name, periods, self)
                message = "Select period and account to view stats:"
            else:
                view = MyStatsView(accounts, current_kvk_name, self)
                message = "Select an account to view stats, or view Total:"
            
            if interaction.response.is_done():
                await interaction.followup.send(message, view=view)
            else:
                await interaction.response.send_message(message, view=view)

    async def kingdom_stats_logic(self, interaction: discord.Interaction, period_key: str = "all", kvk_name: str = None):
        if not kvk_name:
            kvk_name = db_manager.get_current_kvk_name()
            
        if not kvk_name:
            msg = "No active KvK is currently set."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=False)
            else:
                await interaction.response.send_message(msg, ephemeral=False)
            return

        stats = db_manager.get_kingdom_stats_by_period(kvk_name, period_key)
        if not stats or not stats['player_count']:
            msg = f"No data found for KvK `{kvk_name}`."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=False)
            else:
                await interaction.response.send_message(msg, ephemeral=False)
            return

        # Get period info for display
        from .helpers import format_period_label
        periods = db_manager.get_all_periods(kvk_name) or []
        period_label = format_period_label(period_key, periods)
        
        # Calculate changes (power, KP, deaths) from start snapshot
        power_change = 0
        earned_kp = stats['kingdom_kill_points']
        earned_deaths = stats['kingdom_deaths']
        
        # Get start snapshot for comparison
        if period_key == "all":
            # For all periods, use KvK-wide start snapshot
            start_snapshot = db_manager.get_kingdom_start_snapshot(kvk_name)
        else:
            # For specific period, get start snapshot of that period
            start_data = db_manager.get_snapshot_data(kvk_name, period_key, 'start')
            if start_data:
                # Aggregate start snapshot
                start_power = sum(p['power'] for p in start_data.values())
                start_kp = sum(p['kill_points'] for p in start_data.values())
                start_deaths = sum(p['deaths'] for p in start_data.values())
                start_snapshot = {
                    'kingdom_power': start_power,
                    'kingdom_kill_points': start_kp,
                    'kingdom_deaths': start_deaths
                }
            else:
                start_snapshot = None
        
        if start_snapshot:
            power_change = stats['kingdom_power'] - (start_snapshot.get('kingdom_power') or 0)
            earned_kp = stats['kingdom_kill_points'] - (start_snapshot.get('kingdom_kill_points') or 0)
            earned_deaths = stats['kingdom_deaths'] - (start_snapshot.get('kingdom_deaths') or 0)
        
        embed = discord.Embed(
            title=f"🏰 Kingdom Stats: {kvk_name}",
            description=f"{period_label}",
            color=discord.Color.gold()
        )
        
        embed.add_field(name="Total Players", value=f"{stats['player_count']:,}", inline=False)
        
        # Power with change
        power_str = f"{stats['kingdom_power']:,}"
        if power_change != 0:
            power_str += f" ({power_change:+,})"
        embed.add_field(name="💪 Total Power", value=power_str, inline=False)
        
        # KP with earned KP
        kp_str = f"{stats['kingdom_kill_points']:,}"
        if start_snapshot:
            kp_str += f"\n📈 Earned: {earned_kp:,}"
        embed.add_field(name="⚔️ Total KP", value=kp_str, inline=True)
        
        # Deaths with earned deaths  
        deaths_str = f"{stats['kingdom_deaths']:,}"
        if start_snapshot:
            deaths_str += f"\n📈 Earned: {earned_deaths:,}"
        embed.add_field(name="💀 Total Deaths", value=deaths_str, inline=True)
        
        embed.add_field(name="🎖️ T4 Kills", value=f"{stats['kingdom_t4_kills']:,}", inline=True)
        embed.add_field(name="👑 T5 Kills", value=f"{stats['kingdom_t5_kills']:,}", inline=True)

        # --- History Comparison ---
        # Find previous KvK
        seasons = db_manager.get_all_seasons()
        prev_kvk = None
        for i, s in enumerate(seasons):
            if s['value'] == kvk_name and i > 0:
                prev_kvk = seasons[i-1]['value']
                break
        
        if prev_kvk:
            # Get stats from previous KvK (total period usually?)
            # Use "all" period for previous KvK
            prev_stats = db_manager.get_kingdom_stats_by_period(prev_kvk, "all")
            
            if prev_stats and prev_stats['player_count'] > 0:
                diff_power = stats['kingdom_power'] - prev_stats['kingdom_power']
                diff_kp = stats['kingdom_kill_points'] - prev_stats['kingdom_kill_points']
                diff_deaths = stats['kingdom_deaths'] - prev_stats['kingdom_deaths']
                
                embed.add_field(
                    name=f"🆚 vs {prev_kvk}",
                    value=f"Power: {diff_power:+,.0f}\nKP: {diff_kp:+,.0f}\nDeaths: {diff_deaths:+,.0f}",
                    inline=False
                )

        # Add Last Updated footer
        last_updated = db_manager.get_last_updated(kvk_name, period_key)
        footer_text = ""
        if last_updated:
            footer_text = f"🕒 Data updated: {last_updated}"
        
        if footer_text:
            embed.set_footer(text=footer_text)

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)
        await self.log_to_channel(interaction, "Command Used", "Command: /kingdom_stats")

    async def show_player_stats(self, interaction: discord.Interaction, player_id: int, kvk_name: str, period_key: str = "all"):
        stats_row = db_manager.get_player_stats_by_period(player_id, kvk_name, period_key)
        stats = dict(stats_row) if stats_row else None

        if not stats:
            if interaction.response.is_done():
                await interaction.followup.send(f"No data found for account ID `{player_id}` in KvK `{kvk_name}`.", ephemeral=False)
            else:
                await interaction.response.send_message(f"No data found for account ID `{player_id}` in KvK `{kvk_name}`.", ephemeral=False)
            return

        requirements = db_manager.get_requirements(kvk_name, stats['total_power'])
        
        # Get appropriate start snapshot based on period
        if period_key == "all":
            # For all periods, use KvK-wide start snapshot
            start_snapshot = db_manager.get_player_start_snapshot(player_id, kvk_name)
        else:
            # For specific period, get start snapshot of that period
            start_snapshot = db_manager.get_snapshot_player_data(kvk_name, period_key, 'start', player_id)
        
        earned_kp = stats['total_kill_points']
        power_change = 0
        
        if start_snapshot:
            earned_kp = stats['total_kill_points'] - (start_snapshot['kill_points'] or 0)
            power_change = stats['total_power'] - (start_snapshot['power'] or 0)
            
        rank = db_manager.get_player_rank(player_id, kvk_name)
        
        # Get period info for display
        periods = db_manager.get_all_periods(kvk_name) or []
        period_label = format_period_label(period_key, periods)
        
        embed = discord.Embed(
            title=f"📊 Player Statistics: {stats['player_name']} (ID: {player_id})",
            description=f"KvK: **{kvk_name}** | {period_label}",
            color=discord.Color.blue()
        )
        
        # Add Last Updated footer
        last_updated = db_manager.get_last_updated(kvk_name, period_key)
        footer_text = ""
        if last_updated:
            footer_text = f"🕒 Data updated: {last_updated}"
        
        embed.set_footer(text=footer_text)
        
        add_stats_fields(embed, stats, requirements, earned_kp, power_change, rank)
        
        # --- History Comparison ---
        # Find previous KvK
        seasons = db_manager.get_all_seasons()
        # Sort by value or something? Assuming they are ordered or we can find the one before current.
        # Simple logic: find current index, take index-1.
        prev_kvk = None
        for i, s in enumerate(seasons):
            if s['value'] == kvk_name and i > 0:
                prev_kvk = seasons[i-1]['value']
                break
        
        if prev_kvk:
            # Get stats from previous KvK (total period usually?)
            # We don't have a "total" period key guaranteed, but usually it's the last one or we sum up?
            # Or we look for a specific period?
            # Let's assume we want to compare with the FINAL stats of previous KvK.
            # If we don't know the period key, we might need a helper.
            # For now, let's try to find a period that looks like "total" or just take the latest one?
            # Or maybe we stored "total" as a period key?
            # Let's try to get stats for "all" or similar if we implemented that.
            # Actually, `get_player_stats_by_period` takes a period_key.
            # If we want "total" for previous KvK, we need to know what the key was.
            # Let's assume there is a period called "total" or we pick the last one.
            prev_periods = db_manager.get_all_periods(prev_kvk)
            if prev_periods:
                # Use the last period (assuming it's the final result)
                prev_period_key = prev_periods[-1]['period_key']
                prev_stats = db_manager.get_player_stats_by_period(player_id, prev_kvk, prev_period_key)
                
                if prev_stats:
                    # Calculate diffs
                    # Compare current TOTAL power/kp vs previous TOTAL power/kp?
                    # Or compare PERFORMANCE?
                    # User said: "видеть динамику изминеий в сравннении с текущим квк"
                    # Usually means: How much I improved since last KvK?
                    # Delta Power = Current Power - Prev Power
                    # Delta KP = Current KP - Prev KP
                    
                    diff_power = stats['total_power'] - prev_stats['total_power']
                    diff_kp = stats['total_kill_points'] - prev_stats['total_kill_points']
                    
                    embed.add_field(
                        name=f"🆚 vs {prev_kvk}",
                        value=f"Power: {diff_power:+,.0f}\nKP: {diff_kp:+,.0f}",
                        inline=False
                    )

        file = None
        if requirements:
            t4 = stats.get('total_t4_kills', 0) or 0
            t5 = stats.get('total_t5_kills', 0) or 0
            total_kills = t4 + t5
            
            img_buffer = graphics.create_player_stats_card(
                current_kills=total_kills,
                req_kills=requirements['required_kills'],
                current_deaths=stats['total_deaths'],
                req_deaths=requirements['required_deaths'],
                player_name=stats['player_name']
            )
            
            if img_buffer:
                file = discord.File(img_buffer, filename="stats_card.png")
                embed.set_image(url="attachment://stats_card.png")
        
        kwargs = {'embed': embed}
        if file:
            kwargs['file'] = file
            
        if interaction.response.is_done():
            await interaction.followup.send(**kwargs, ephemeral=False)
        else:
            await interaction.response.send_message(**kwargs, ephemeral=False)

    async def show_total_stats(self, interaction: discord.Interaction, accounts, kvk_name: str):
        # Get all player IDs for batch query
        player_ids = [acc['player_id'] for acc in accounts]
        
        # Batch query - get all stats in one SQL call instead of N calls
        all_stats = db_manager.get_total_stats_for_players(player_ids, kvk_name)
        
        if not all_stats:
             if interaction.response.is_done():
                await interaction.followup.send("No data found for any linked accounts.", ephemeral=False)
             else:
                await interaction.response.send_message("No data found for any linked accounts.", ephemeral=False)
             return
        
        # Aggregate stats from all accounts
        total_stats = {
            'total_power': 0, 'total_kill_points': 0, 'total_deaths': 0,
            'total_t1_kills': 0, 'total_t2_kills': 0, 'total_t3_kills': 0,
            'total_t4_kills': 0, 'total_t5_kills': 0,
            'player_name': "Aggregated Accounts"
        }
        
        earned_kp_total = 0
        power_change_total = 0
        
        for player_id, p_stats in all_stats.items():
            for key in total_stats:
                if key != 'player_name':
                    total_stats[key] += (p_stats.get(key, 0) or 0)
            
            # Calculate earned stats
            start_snapshot = db_manager.get_player_start_snapshot(player_id, kvk_name)
            if start_snapshot:
                earned_kp_total += (p_stats.get('total_kill_points', 0) - (start_snapshot['kill_points'] or 0))
                power_change_total += (p_stats.get('total_power', 0) - (start_snapshot['power'] or 0))
            else:
                earned_kp_total += p_stats.get('total_kill_points', 0)

        embed = discord.Embed(
            title=f"Total Statistics ({len(accounts)} accounts)",
            description=f"KvK: **{kvk_name}**",
            color=discord.Color.purple()
        )
        
        # Add Last Updated footer
        last_updated = db_manager.get_last_updated(kvk_name, "general")
        if last_updated:
            embed.set_footer(text=f"🕒 Data updated: {last_updated}")
        
        # Try to get global requirements first
        import json
        global_reqs_json = db_manager.get_global_requirements()
        requirements = None
        
        if global_reqs_json:
            try:
                global_reqs = json.loads(global_reqs_json)
                # Find matching bracket
                power = total_stats['total_power']
                for req in global_reqs:
                    if req['min_power'] <= power <= req['max_power']:
                        requirements = req
                        break
            except Exception as e:
                logger.error(f"Error parsing global requirements: {e}")
        
        # Fallback to KvK requirements if no global found (or maybe we shouldn't? User said "change requirements for this general statistics")
        # If global reqs are set, use them. If not, maybe use KvK reqs?
        if not requirements:
             requirements = db_manager.get_requirements(kvk_name, total_stats['total_power'])

        add_stats_fields(embed, total_stats, requirements, earned_kp_total, power_change_total, rank=None)

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)

    async def log_to_channel(self, interaction: discord.Interaction, action: str, details: str):
        log_channel_id = int(os.getenv('LOG_CHANNEL_ID', 0))
        if log_channel_id == 0:
            return
        channel = self.bot.get_channel(log_channel_id)
        
        if not channel:
            return

        embed = discord.Embed(title="👤 User Action Logged", color=discord.Color.green(), timestamp=interaction.created_at)
        embed.add_field(name="User", value=interaction.user.mention, inline=True)
        embed.add_field(name="Action", value=action, inline=True)
        embed.add_field(name="Details", value=details, inline=False)
        embed.set_footer(text=f"ID: {interaction.user.id}")
        
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send log message: {e}")
            
        db_manager.log_admin_action(interaction.user.id, interaction.user.name, action, details)
