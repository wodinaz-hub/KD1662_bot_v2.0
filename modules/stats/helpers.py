"""
Helper functions for stats module.
Contains utility functions for formatting and calculations.
"""
import discord


def add_stats_fields(embed, stats, requirements, earned_kp=None, power_change=None, rank=None):
    """
    Add statistics fields to Discord embed with 3-column layout.
    
    Args:
        embed: Discord.Embed object to add fields to
        stats: Dict with player statistics
        requirements: Dict with KvK requirements or None
        earned_kp: Earned kill points (optional)
        power_change: Power change from start (optional)
        rank: Player's DKP rank (optional)
    """
    # Row 1: Power, Kills (T4+T5), Deaths
    power_val = f"{stats['total_power']:,}"
    if power_change is not None:
        sign = "+" if power_change >= 0 else ""
        power_val += f"\n({sign}{power_change:,})"
    embed.add_field(name="💪 Power", value=power_val, inline=True)

    t4 = stats.get('total_t4_kills', 0) or 0
    t5 = stats.get('total_t5_kills', 0) or 0
    total_kills = t4 + t5
    
    kills_val = f"{total_kills:,}"
    if requirements:
        req_kills = requirements['required_kills']
        status = "✅" if total_kills >= req_kills else "❌"
        pct = 0
        if req_kills > 0:
            pct = min(100, (total_kills / req_kills) * 100)
        kills_val += f" / {req_kills:,}\n{status} ({int(pct)}%)"
    embed.add_field(name="⚔️ Kills (T4+T5)", value=kills_val, inline=True)

    deaths_val = f"{stats['total_deaths']:,}"
    if requirements:
        req_deaths = requirements['required_deaths']
        status = "✅" if stats['total_deaths'] >= req_deaths else "❌"
        pct = 0
        if req_deaths > 0:
            pct = min(100, (stats['total_deaths'] / req_deaths) * 100)
        deaths_val += f" / {req_deaths:,}\n{status} ({int(pct)}%)"
    embed.add_field(name="💀 Deaths", value=deaths_val, inline=True)

    # Row 2: T4 Kills, T5 Kills, Empty
    embed.add_field(name="🎯 T4 Kills", value=f"{t4:,}", inline=True)
    embed.add_field(name="⭐ T5 Kills", value=f"{t5:,}", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    # Row 3: DKP Score, DKP Rank, Empty
    deaths = stats.get('total_deaths', 0) or 0
    dkp = calculate_dkp(t4, t5, deaths)
    embed.add_field(name="🏆 DKP Score", value=f"**{dkp:,}**\n`T4×4 + T5×10 + Deaths×15`", inline=True)
    
    if rank:
        embed.add_field(name="📊 DKP Rank", value=f"**#{rank}**", inline=True)
    else:
        embed.add_field(name="📊 DKP Rank", value="N/A", inline=True)
    
    embed.add_field(name="\u200b", value="\u200b", inline=True)


def calculate_dkp(t4_kills, t5_kills, deaths):
    """
    Calculate DKP (Dragon Kill Points) based on kills and deaths.
    
    Formula: T4×4 + T5×10 + Deaths×15
    
    Args:
        t4_kills: Number of T4 kills
        t5_kills: Number of T5 kills
        deaths: Number of deaths
        
    Returns:
        int: Calculated DKP score
    """
    return (t4_kills * 4) + (t5_kills * 10) + (deaths * 15)


def format_period_label(period_key, periods):
    """
    Format period display label for embed description.
    
    Args:
        period_key: Period key string or "all"
        periods: List of period dicts from database
        
    Returns:
        str: Formatted label like "All Periods (3)" or "Period: Period_1"
    """
    if period_key == "all":
        unique_periods = list(set([p['period_key'] for p in periods])) if periods else []
        return f"All Periods ({len(unique_periods)})" if len(unique_periods) > 1 else "All Data"
    return f"Period: {period_key}"
