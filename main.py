import discord
from discord.ext import commands
import os
import logging
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger('discord_bot')


class MyBot(commands.Bot):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(command_prefix="!", intents=intents)
        self.initial_extensions = ['modules.admin']  # Список модулей для загрузки

    async def setup_hook(self):
        logger.info("Начинается загрузка модулей...")
        for ext in self.initial_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"Модуль {ext} успешно загружен.")
            except Exception as e:
                logger.error(f"Не удалось загрузить модуль {ext}. Ошибка: {e}")

        # Синхронизация слеш-команд
        try:
            synced = await self.tree.sync()
            logger.info(f"Синхронизировано {len(synced)} слеш-команд.")
        except Exception as e:
            logger.error(f"Не удалось синхронизировать слеш-команды. Ошибка: {e}")

    async def on_ready(self):
        logger.info(f'Бот {self.user} успешно подключен и готов к работе!')
        print(f'{self.user} has connected to Discord!')


intents = discord.Intents.default()
intents.message_content = True  # Включаем интенты для содержимого сообщений
bot = MyBot(intents=intents)

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

# Запуск бота
if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        logger.error(
            "Токен бота не найден в переменных окружения. Убедитесь, что DISCORD_TOKEN установлен в вашем .env файле.")
    else:
        bot.run(TOKEN)
