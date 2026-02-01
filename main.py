import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger('discord_bot')


class MyBot(commands.Bot):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(command_prefix="!", intents=intents)
        self.initial_extensions = ['modules.admin', 'modules.stats', 'modules.forts']  # List of modules to load
        
        # Initialize database tables on startup
        from database import database_manager as db_manager
        db_manager.create_tables()
        logger.info("Database tables initialized/verified.")

        # Initialize Notification Manager
        from core.notifications import NotificationManager
        self.notifications = NotificationManager(self)

    async def setup_hook(self):
        logger.info("Starting module loading...")
        for ext in self.initial_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"Module {ext} loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load module {ext}. Error: {e}")

        # Sync slash commands globally
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} slash commands globally.")
        except Exception as e:
            logger.error(f"Failed to sync slash commands. Error: {e}")

    @tasks.loop(hours=24) # Daily
    async def compliance_check(self):
        """Checks for players falling behind on requirements."""
        current_kvk = db_manager.get_current_kvk_name()
        if current_kvk:
            # If there is an active KvK, we don't send fort reminders (as per user request)
            return

        # If no active KvK, check forts for the most recent season
        fort_seasons = db_manager.get_fort_seasons()
        if not fort_seasons:
            return
        
        target_season = fort_seasons[0] # Most recent
        fort_leaderboard = db_manager.get_fort_leaderboard(target_season, "total")
        if fort_leaderboard:
            low_forts = [p for p in fort_leaderboard if p['total_forts'] < 35]
            if low_forts:
                # Group by count for cleaner message
                low_forts.sort(key=lambda x: x['total_forts'])
                reminder_text = "⚠️ **Fort Participation Reminder**\n"
                reminder_text += "The following players need to increase their activity (Goal: 35):\n"
                for p in low_forts[:10]: # Limit to 10 to avoid spam
                    reminder_text += f"• {p['player_name']}: **{p['total_forts']}/35**\n"
                
                if len(low_forts) > 10:
                    reminder_text += f"*...and {len(low_forts)-10} more players.*"

                if hasattr(self, 'notifications'):
                    await self.notifications.send_announcement(
                        "🏰 Fort Compliance Check",
                        reminder_text,
                        color=discord.Color.orange()
                    )

    @compliance_check.before_loop
    async def before_compliance_check(self):
        await self.wait_until_ready()

    async def on_ready(self):
        logger.info(f'Bot {self.user} successfully connected and ready to work!')
        logger.info(f'{self.user} has connected to Discord!')
        
        # Start background tasks if not already running
        if not self.weekly_report.is_running():
            self.weekly_report.start()
        if not self.compliance_check.is_running():
            self.compliance_check.start()

    @tasks.loop(hours=168) # Weekly
    async def weekly_report(self):
        """Sends a weekly summary of top performers."""
        current_kvk = db_manager.get_current_kvk_name()
        if not current_kvk:
            return

        # Get leaderboard for current KvK
        leaderboard = db_manager.get_leaderboard(current_kvk)
        if not leaderboard:
            return

        # Sort by KP and Deaths
        top_kp = sorted(leaderboard, key=lambda x: x['total_kill_points'], reverse=True)[:5]
        top_deaths = sorted(leaderboard, key=lambda x: x['total_deaths'], reverse=True)[:5]

        kp_text = "\n".join([f"• {p['player_name']}: **{p['total_kill_points']:,}**" for p in top_kp])
        deaths_text = "\n".join([f"• {p['player_name']}: **{p['total_deaths']:,}**" for p in top_deaths])

        fields = {
            "⚔️ Top KP": kp_text,
            "💀 Top Deaths": deaths_text
        }

        if hasattr(self, 'notifications'):
            await self.notifications.send_announcement(
                "📈 Weekly KvK Report",
                f"Activity summary for season **{current_kvk}** for the past week.",
                color=discord.Color.gold(),
                fields=fields
            )

    @weekly_report.before_loop
    async def before_weekly_report(self):
        await self.wait_until_ready()


intents = discord.Intents.default()
intents.message_content = True  # Enable message content intents
bot = MyBot(intents=intents)


# Global error handler for app commands
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    command_name = interaction.command.name if interaction.command else "Unknown Command"
    
    if isinstance(error, app_commands.CommandInvokeError):
        original = error.original
        if isinstance(original, discord.errors.NotFound):
            # Interaction expired - silently log, user already sees "interaction failed"
            logger.warning(f"Interaction expired for command '{command_name}' from {interaction.user}")
            return
    
    # Log other errors
    logger.error(f"Error in command '{command_name}': {error}")
    
    # Try to respond if possible
    try:
        if interaction.response.is_done():
            await interaction.followup.send(f"❌ An error occurred: {str(error)[:100]}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ An error occurred: {str(error)[:100]}", ephemeral=True)
    except:
        pass  # Can't respond, interaction is dead


@bot.command()
async def sync(ctx, spec: str = None):
    # Debug info
    exts = list(ctx.bot.extensions.keys())
    tree_cmds = len(ctx.bot.tree.get_commands())
    await ctx.send(f"Debug: Loaded extensions: {exts}")
    await ctx.send(f"Debug: Global commands in tree: {tree_cmds}")

    if spec == "guild":
        ctx.bot.tree.copy_global_to(guild=ctx.guild)
        synced = await ctx.bot.tree.sync(guild=ctx.guild)
        await ctx.send(f"Synced {len(synced)} commands to this guild (Instant).")
    else:
        synced = await ctx.bot.tree.sync()
        await ctx.send(f"Synced {len(synced)} commands globally. (May take up to 1 hour).")

@bot.command()
async def clearlocal(ctx):
    """Clears all commands from the current guild (Fixes duplicates)."""
    ctx.bot.tree.clear_commands(guild=ctx.guild)
    await ctx.bot.tree.sync(guild=ctx.guild)
    await ctx.send("✅ Cleared guild-specific commands. Duplicate menu items should disappear.")

# Run bot
if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        logger.error(
            "Bot token not found in environment variables. Ensure DISCORD_TOKEN is set in your .env file.")
    else:
        bot.run(TOKEN)

