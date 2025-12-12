"""
Stats Module - Player and Kingdom Statistics

This module provides commands for viewing player and kingdom statistics.
Refactored into separate components for better maintainability.
"""
from .cog import Stats
import logging

logger = logging.getLogger('stats_commands')

async def setup(bot):
    """Setup function for loading the Stats cog."""
    await bot.add_cog(Stats(bot))
    logger.info("Module 'stats' loaded successfully.")

__all__ = ['Stats', 'setup']
