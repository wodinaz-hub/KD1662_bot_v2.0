import sqlite3
import logging
from contextlib import closing
from .base import get_connection

logger = logging.getLogger('db_manager.admin')

def log_admin_action(admin_id: int, admin_name: str, action: str, details: str):
    """Logs an admin action to the database."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO admin_logs (admin_id, admin_name, action, details)
                VALUES (?, ?, ?, ?)
            ''', (admin_id, admin_name, action, details))
            conn.commit()
    except Exception as e:
        logger.error(f"Error logging admin action: {e}")

def set_reward_role(role_id: int):
    """Sets the reward role ID in the database."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO kvk_settings (setting_key, setting_value) VALUES ('reward_role', ?)", (str(role_id),))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error setting reward role: {e}")
        return False

def get_reward_role():
    """Gets the reward role ID from the database."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT setting_value FROM kvk_settings WHERE setting_key = 'reward_role'")
            row = cursor.fetchone()
            return int(row[0]) if row else None
    except Exception as e:
        logger.error(f"Error getting reward role: {e}")
        return None

def get_global_requirements():
    """Returns the global requirements setting as a JSON string or None."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT setting_value FROM global_settings WHERE setting_key = 'requirements'")
            row = cursor.fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.error(f"Error getting global requirements: {e}")
        return None

def set_global_requirements(requirements_json: str):
    """Saves the global requirements setting."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO global_settings (setting_key, setting_value) VALUES ('requirements', ?)", (requirements_json,))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error setting global requirements: {e}")
        return False

def reset_all_data():
    """Completely clears the database (deletes all data from tables)."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            tables = [
                'kvk_stats', 'kvk_snapshots', 'kvk_requirements', 
                'linked_accounts', 'kvk_settings', 'admin_logs', 
                'kingdom_players', 'kvk_seasons', 'fort_stats', 
                'fort_periods', 'global_settings'
            ]
            for table in tables:
                cursor.execute(f"DELETE FROM {table}")
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error resetting all data: {e}")
        return False

def set_last_updated(kvk_name: str, period_key: str = "general"):
    """Sets the last updated timestamp for a KvK period."""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            key = f"last_updated_{kvk_name}_{period_key}"
            cursor.execute("INSERT OR REPLACE INTO kvk_settings (setting_key, setting_value) VALUES (?, ?)", (key, timestamp))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error setting last updated: {e}")
        return False

def get_last_updated(kvk_name: str, period_key: str = "general"):
    """Gets the last updated timestamp."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            key = f"last_updated_{kvk_name}_{period_key}"
            cursor.execute("SELECT setting_value FROM kvk_settings WHERE setting_key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else "Never"
    except Exception as e:
        logger.error(f"Error getting last updated: {e}")
        return "Error"
