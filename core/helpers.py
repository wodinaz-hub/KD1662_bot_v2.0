"""
Core helpers module - common utility functions used across the bot.
"""
import re
from datetime import datetime
from functools import lru_cache
from typing import Optional, Tuple, List
from discord import app_commands


def validate_date(date_str: str) -> Tuple[bool, Optional[str]]:
    """
    Validates a date string in YYYY-MM-DD format.
    Returns (is_valid, error_message).
    """
    if not date_str:
        return True, None  # Empty is valid (optional)
    
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True, None
    except ValueError:
        return False, f"Invalid date format: '{date_str}'. Use YYYY-MM-DD."


def format_number(n: int) -> str:
    """Formats a number with comma separators."""
    if n is None:
        return "0"
    return f"{n:,}"


def generate_unique_key(name: str, existing_keys: List[str] = None) -> str:
    """
    Generates a unique key from a name.
    Removes special characters, replaces spaces with underscores.
    If key exists, appends a number suffix.
    """
    # Basic sanitization
    key = name.lower()
    key = re.sub(r'[^\w\s-]', '', key)  # Remove special chars except - and _
    key = re.sub(r'[-\s]+', '_', key)   # Replace spaces and dashes with underscores
    key = re.sub(r'_+', '_', key)        # Collapse multiple underscores
    key = key.strip('_')
    
    if not existing_keys:
        return key
    
    # Check for collisions and add suffix if needed
    base_key = key
    counter = 1
    while key in existing_keys:
        key = f"{base_key}_{counter}"
        counter += 1
    
    return key


def truncate_string(s: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncates a string to max_length, adding suffix if truncated."""
    if not s or len(s) <= max_length:
        return s or ""
    return s[:max_length - len(suffix)] + suffix


# Caching decorators for common database queries
def cached_ttl(seconds: int = 60):
    """
    Decorator that caches function results for a specified time.
    Uses a simple time-based invalidation.
    """
    def decorator(func):
        cache = {}
        
        def wrapper(*args, **kwargs):
            import time
            key = (args, tuple(sorted(kwargs.items())))
            current_time = time.time()
            
            if key in cache:
                result, timestamp = cache[key]
                if current_time - timestamp < seconds:
                    return result
            
            result = func(*args, **kwargs)
            cache[key] = (result, current_time)
            return result
        
        wrapper.cache_clear = lambda: cache.clear()
        return wrapper
    
    return decorator


# Season autocomplete helper
def get_season_autocomplete_choices(seasons: list, current: str, include_archived: bool = True) -> List[app_commands.Choice[str]]:
    """
    Creates autocomplete choices for season selection.
    Filters and formats seasons consistently.
    """
    choices = []
    for s in seasons:
        # Skip archived if not wanted
        if not include_archived and s.get('is_archived') and not s.get('is_active'):
            continue
        
        label = s.get('label', s.get('value', ''))
        value = s.get('value', '')
        
        # Filter by current input
        if current.lower() not in label.lower():
            continue
        
        # Add emoji prefix
        if s.get('is_active'):
            display = f"⚔️ {label}"
        elif s.get('is_archived'):
            display = f"📁 {label}"
        else:
            display = label
        
        # Truncate display if too long (Discord limit is 100)
        display = truncate_string(display, 100)
        
        choices.append(app_commands.Choice(name=display, value=value))
    
    return choices[:25]  # Discord limit
