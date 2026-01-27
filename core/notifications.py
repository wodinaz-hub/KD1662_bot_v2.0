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

        content = "<@&1239286227317030912>" if tag_role else None
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
            "Сезон / Season": season,
            "Период / Period": period_name,
            "Действие / Action": "Используйте `/my_forts` для проверки своей статистики."
        }
        await self.send_announcement(
            "🏰 Новые данные по фортам! / New Fort Data!",
            "Администратор загрузил свежую статистику по фортам.",
            color=discord.Color.orange(),
            fields=fields
        )

    async def notify_new_stats_data(self, season, period_name, snapshot_type):
        """Specific notification for new KvK stats upload."""
        fields = {
            "Сезон / Season": season,
            "Период / Period": period_name,
            "Тип / Type": snapshot_type.capitalize(),
            "Действие / Action": "Используйте `/my_stats` для проверки своего прогресса."
        }
        await self.send_announcement(
            "📊 Обновление статистики КвК! / KvK Stats Updated!",
            "Загружены новые данные по убийствам и смертям.",
            color=discord.Color.green(),
            fields=fields
        )
