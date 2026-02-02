import discord
import os
import logging

logger = logging.getLogger('discord_bot.notifications')

class NotificationManager:
    def __init__(self, bot):
        self.bot = bot
        self.channel_id = int(os.getenv('NOTIFICATIONS_CHANNEL_ID', 0))

    async def send_announcement(self, title, description, color=discord.Color.blue(), fields=None, tag_role=True):
        """Sends a formatted announcement to the notifications channel."""
        if not self.channel_id:
            logger.warning("NOTIFICATIONS_CHANNEL_ID not set. Skipping announcement.")
            return

        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(self.channel_id)
            except Exception as e:
                logger.error(f"Could not find notification channel {self.channel_id}: {e}")
                return

        content = None # Role ping removed by user request
        embed = discord.Embed(title=title, description=description, color=color)
        if fields:
            for name, value in fields.items():
                embed.add_field(name=name, value=value, inline=False)
        
        try:
            await channel.send(content=content, embed=embed)
            logger.info(f"Announcement sent: {title}")
        except Exception as e:
            logger.error(f"Failed to send announcement: {e}")

    async def notify_new_fort_data(self, season, period_name):
        """Specific notification for new fort data upload."""
        fields = {
            "Season": season,
            "Period": period_name,
            "Action": "Use `/my_forts` to check your stats."
        }
        await self.send_announcement(
            "🏰 New Fort Data!",
            "The administrator has uploaded fresh fort statistics.",
            color=discord.Color.orange(),
            fields=fields
        )

    async def notify_new_stats_data(self, season, period_name, snapshot_type):
        """Specific notification for new KvK stats upload."""
        fields = {
            "Season": season,
            "Period": period_name,
            "Type": snapshot_type.capitalize(),
            "Action": "Use `/my_stats` to check your progress."
        }
        await self.send_announcement(
            "📊 KvK Stats Updated!",
            "New kill and death data has been uploaded.",
            color=discord.Color.green(),
            fields=fields
        )
