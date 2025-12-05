import discord
from discord.ext import commands
from discord import app_commands
import logging
from database import database_manager as db_manager

# Настройка логирования
logger = logging.getLogger('stats_commands')


class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Создаём таблицы базы данных при инициализации
        db_manager.create_tables()

    @app_commands.command(name='link_account', description='Привязать игровой аккаунт к вашему Discord.')
    @app_commands.describe(player_id="Ваш игровой ID, состоящий только из цифр.")
    async def link_account(self, interaction: discord.Interaction, player_id: int):
        """
        Привязывает игровой аккаунт к аккаунту Discord.
        """
        discord_id = interaction.user.id
        accounts = db_manager.get_linked_accounts(discord_id)
        is_main = len(accounts) == 0

        success = db_manager.link_account(discord_id, player_id, is_main)

        if success:
            await interaction.response.send_message(
                f"Игровой ID `{player_id}` успешно привязан к вашему аккаунту Discord.")
            logger.info(f"Аккаунт {player_id} привязан к Discord ID {discord_id}.")
        else:
            await interaction.response.send_message(
                "Произошла ошибка при привязке аккаунта. Пожалуйста, попробуйте еще раз.")

    @app_commands.command(name='my_stats', description='Показать статистику вашего основного аккаунта за текущий KVK.')
    async def my_stats(self, interaction: discord.Interaction):
        """
        Показывает суммарную статистику основного привязанного аккаунта.
        """
        await interaction.response.defer()  # Отправляем отложенный ответ, чтобы избежать ошибки таймаута

        discord_id = interaction.user.id
        accounts = db_manager.get_linked_accounts(discord_id)

        if not accounts:
            await interaction.followup.send(
                "Ваш аккаунт Discord не привязан к игровому аккаунту. Используйте `/link_account <ваш_игровой_ID>`.")
            return

        main_account = next((acc for acc in accounts if acc['is_main']), None)
        if not main_account:
            main_account = accounts[0]  # Если нет основного, берём первый

        player_id = main_account['player_id']
        current_kvk_name = db_manager.get_current_kvk_name()
import discord
from discord.ext import commands
from discord import app_commands
import logging
from database import database_manager as db_manager

# Настройка логирования
logger = logging.getLogger('stats_commands')


class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Создаём таблицы базы данных при инициализации
        db_manager.create_tables()

    @app_commands.command(name='link_account', description='Привязать игровой аккаунт к вашему Discord.')
    @app_commands.describe(player_id="Ваш игровой ID, состоящий только из цифр.")
    async def link_account(self, interaction: discord.Interaction, player_id: int):
        """
        Привязывает игровой аккаунт к аккаунту Discord.
        """
        discord_id = interaction.user.id
        accounts = db_manager.get_linked_accounts(discord_id)
        is_main = len(accounts) == 0

        success = db_manager.link_account(discord_id, player_id, is_main)

        if success:
            await interaction.response.send_message(
                f"Игровой ID `{player_id}` успешно привязан к вашему аккаунту Discord.")
            logger.info(f"Аккаунт {player_id} привязан к Discord ID {discord_id}.")
        else:
            await interaction.response.send_message(
                "Произошла ошибка при привязке аккаунта. Пожалуйста, попробуйте еще раз.")

    @app_commands.command(name='my_stats', description='Показать статистику вашего основного аккаунта за текущий KVK.')
    async def my_stats(self, interaction: discord.Interaction):
        """
        Показывает суммарную статистику основного привязанного аккаунта.
        """
        await interaction.response.defer()  # Отправляем отложенный ответ, чтобы избежать ошибки таймаута

        discord_id = interaction.user.id
        accounts = db_manager.get_linked_accounts(discord_id)

        if not accounts:
            await interaction.followup.send(
                "Ваш аккаунт Discord не привязан к игровому аккаунту. Используйте `/link_account <ваш_игровой_ID>`.")
            return

        main_account = next((acc for acc in accounts if acc['is_main']), None)
        if not main_account:
            main_account = accounts[0]  # Если нет основного, берём первый

        player_id = main_account['player_id']
        current_kvk_name = db_manager.get_current_kvk_name()

        if not current_kvk_name:
            await interaction.followup.send(
                "В данный момент не установлен активный KVK. Пожалуйста, попросите администратора установить его.")
            return

        stats = db_manager.get_total_player_stats(player_id, current_kvk_name)

        if not stats:
            await interaction.followup.send(
                f"Данные для аккаунта с ID `{player_id}` в KVK `{current_kvk_name}` не найдены.")
            return

        # Получаем требования
        requirements = db_manager.get_requirements(current_kvk_name, stats['total_power'])
        
        embed = discord.Embed(
            title=f"Статистика: {stats['player_name']} (ID: {player_id})",
            description=f"KVK: **{current_kvk_name}**",
            color=discord.Color.blue()
        )
        
        # Power
        embed.add_field(name="Мощь", value=f"{stats['total_power']:,}", inline=False)

        # Kill Points
        kp_val = f"{stats['total_kill_points']:,}"
        if requirements:
            req_kp = requirements['required_kill_points']
            status = "✅" if stats['total_kill_points'] >= req_kp else "❌"
            kp_val += f" / {req_kp:,} {status}"
        embed.add_field(name="Очки Убийств (KP)", value=kp_val, inline=True)

        # Deaths
        deaths_val = f"{stats['total_deaths']:,}"
        if requirements:
            req_deaths = requirements['required_deaths']
            status = "✅" if stats['total_deaths'] >= req_deaths else "❌"
            deaths_val += f" / {req_deaths:,} {status}"
        embed.add_field(name="Смерти (Deads)", value=deaths_val, inline=True)

        # Kills breakdown
        embed.add_field(name="T1", value=f"{stats['total_t1_kills']:,}", inline=True)
        embed.add_field(name="T2", value=f"{stats['total_t2_kills']:,}", inline=True)
        embed.add_field(name="T3", value=f"{stats['total_t3_kills']:,}", inline=True)
        embed.add_field(name="T4", value=f"{stats['total_t4_kills']:,}", inline=True)
        embed.add_field(name="T5", value=f"{stats['total_t5_kills']:,}", inline=True)

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Stats(bot))
    logger.info("Модуль 'stats' успешно загружен.")