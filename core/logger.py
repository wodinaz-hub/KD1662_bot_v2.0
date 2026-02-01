import discord
import logging
import os
from datetime import datetime

logger = logging.getLogger('discord_bot.core.logger')

class BotLogger:
    def __init__(self, bot):
        self.bot = bot
        self.log_channel_id = int(os.getenv('LOG_CHANNEL_ID', 0))
        if self.log_channel_id == 0:
            logger.warning("LOG_CHANNEL_ID not set in environment variables. Channel logging disabled.")

    async def _send_log_embed(self, embed):
        """Internal helper to send log embed to channel."""
        if self.log_channel_id == 0:
            return

        channel = self.bot.get_channel(self.log_channel_id)
        if not channel:
            # Try fetching if not in cache (rare case for ready bot)
            try:
                channel = await self.bot.fetch_channel(self.log_channel_id)
            except Exception as e:
                logger.error(f"Could not fetch log channel {self.log_channel_id}: {e}")
                return

        if channel:
            try:
                await channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Failed to send log to channel: {e}")

    async def log_command(self, interaction: discord.Interaction, command_name: str):
        """Logs a standard user command execution."""
        embed = discord.Embed(
            title="👤 Command Used", 
            color=discord.Color.blue(), 
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=f"{interaction.user.name} ({interaction.user.id})", icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Command", value=f"/{command_name}", inline=True)
        embed.add_field(name="Channel", value=f"{interaction.channel.mention if interaction.channel else 'DM'}", inline=True)
        
        # Add guild info if available
        if interaction.guild:
            embed.set_footer(text=f"Guild: {interaction.guild.name} ({interaction.guild.id})")
            
        await self._send_log_embed(embed)

    async def log_admin_action(self, interaction: discord.Interaction, action: str, details: str):
        """Logs an administrative action (also logs to DB via separate call usually)."""
        embed = discord.Embed(
            title="🛡️ Admin Action", 
            color=discord.Color.gold(), 
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=f"{interaction.user.name} ({interaction.user.id})", icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Action", value=action, inline=False)
        embed.add_field(name="Details", value=details, inline=False)
        
        await self._send_log_embed(embed)

    async def log_error(self, interaction: discord.Interaction, error: Exception, command_name: str = "Unknown"):
        """Logs an error occurring during command execution."""
        embed = discord.Embed(
            title="❌ Command Error", 
            color=discord.Color.red(), 
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=f"{interaction.user.name} ({interaction.user.id})", icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Command", value=f"/{command_name}", inline=True)
        embed.add_field(name="Error", value=f"```{str(error)[:1000]}```", inline=False)
        
        await self._send_log_embed(embed)

    async def log_custom(self, title: str, description: str, color: discord.Color = discord.Color.light_gray(), user: discord.User = None):
        """Logs a custom message."""
        embed = discord.Embed(
            title=title, 
            description=description, 
            color=color, 
            timestamp=discord.utils.utcnow()
        )
        if user:
            embed.set_author(name=f"{user.name} ({user.id})", icon_url=user.display_avatar.url)
            
        await self._send_log_embed(embed)
