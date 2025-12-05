import discord
import os
from dotenv import load_dotenv

load_dotenv()

class DebugBot(discord.Client):
    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')
        print(f'Connected to {len(self.guilds)} guilds:')
        for guild in self.guilds:
            print(f' - {guild.name} (ID: {guild.id})')
        print('------')
        await self.close()

intents = discord.Intents.default()
client = DebugBot(intents=intents)

TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    print("Error: DISCORD_TOKEN not found in .env")
else:
    try:
        client.run(TOKEN)
    except Exception as e:
        print(f"Error running bot: {e}")
