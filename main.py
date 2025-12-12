import discord
from discord.ext import commands
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
        self.initial_extensions = ['modules.admin', 'modules.stats']  # List of modules to load

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

    async def on_ready(self):
        logger.info(f'Bot {self.user} successfully connected and ready to work!')
        logger.info(f'{self.user} has connected to Discord!')


intents = discord.Intents.default()
intents.message_content = True  # Enable message content intents
bot = MyBot(intents=intents)


# Global error handler for app commands
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandInvokeError):
        original = error.original
        if isinstance(original, discord.errors.NotFound):
            # Interaction expired - silently log, user already sees "interaction failed"
            logger.warning(f"Interaction expired for command '{interaction.command.name}' from {interaction.user}")
            return
    
    # Log other errors
    logger.error(f"Error in command '{interaction.command.name}': {error}")
    
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

# Run bot
if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        logger.error(
            "Bot token not found in environment variables. Ensure DISCORD_TOKEN is set in your .env file.")
    else:
        bot.run(TOKEN)

