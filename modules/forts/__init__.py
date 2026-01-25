from .cog import Forts

async def setup(bot):
    await bot.add_cog(Forts(bot))
