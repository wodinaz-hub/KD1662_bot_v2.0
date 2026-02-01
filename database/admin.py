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

def get_all_admin_logs():
    """Retrieves all admin logs."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM admin_logs ORDER BY timestamp DESC")
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting admin logs: {e}")
        return []

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


def get_global_requirements_as_list():
    """
    Returns the global requirements as a list of dictionaries.
    This is used for auto-copying to new KvK seasons.
    
    Returns:
        [
            {'min_power': 40000000, 'max_power': 44999999, 'required_kills': 2500000, 'required_deaths': 200000},
            ...
        ]
    """
    try:
        import json
        reqs_json = get_global_requirements()
        if not reqs_json:
            return []
        
        # Parse JSON to list of dicts
        reqs_list = json.loads(reqs_json)
        return reqs_list if isinstance(reqs_list, list) else []
    except Exception as e:
        logger.error(f"Error parsing global requirements: {e}")
        return []


def set_global_requirements_from_file(file_path: str):
    """
    Loads global requirements from an Excel file and saves them.
    Format: min_power, max_power, required_kills, required_deaths
    
    Returns:
        (success: bool, message: str)
    """
    try:
        import pandas as pd
        import json
        
        df = pd.read_excel(file_path)
        df.columns = [c.strip().lower() for c in df.columns]
        
        # Map column names
        col_map = {
            'min_power': ['min power', 'min_power', 'power from'],
            'max_power': ['max power', 'max_power', 'power to'],
            'required_kills': ['required kills', 'kills', 'kill goal', 'required_kills', 'required_kill'],
            'required_deaths': ['required deaths', 'deaths', 'death goal', 'required_deaths', 'required_death']
        }
        
        found_cols = {}
        for target, variations in col_map.items():
            for var in variations:
                if var in df.columns:
                    found_cols[target] = var
                    break
        
        required = ['min_power', 'max_power', 'required_kills', 'required_deaths']
        missing = [r for r in required if r not in found_cols]
        if missing:
            return False, f"Missing columns: {', '.join(missing)}"
        
        # Build requirements list
        requirements_list = []
        for _, row in df.iterrows():
            requirements_list.append({
                'min_power': int(row[found_cols['min_power']]),
                'max_power': int(row[found_cols['max_power']]),
                'required_kills': int(row[found_cols['required_kills']]),
                'required_deaths': int(row[found_cols['required_deaths']])
            })
        
        # Save as JSON
        reqs_json = json.dumps(requirements_list)
        if set_global_requirements(reqs_json):
            return True, f"Global requirements updated! {len(requirements_list)} brackets loaded."
        else:
            return False, "Failed to save global requirements."
            
    except Exception as e:
        logger.error(f"Error loading global requirements from file: {e}")
        return False, str(e)


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

def get_dkp_formula():
    """Gets the DKP formula weights from the database."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT setting_value FROM kvk_settings WHERE setting_key = 'dkp_formula'")
            row = cursor.fetchone()
            if row:
                import json
                return json.loads(row[0])
            return {"t4": 4, "t5": 10, "deaths": 15} # Default
    except Exception as e:
        logger.error(f"Error getting DKP formula: {e}")
        return {"t4": 4, "t5": 10, "deaths": 15}

def set_dkp_formula(t4: int, t5: int, deaths: int):
    """Sets the DKP formula weights."""
    try:
        import json
        value = json.dumps({"t4": t4, "t5": t5, "deaths": deaths})
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO kvk_settings (setting_key, setting_value) VALUES ('dkp_formula', ?)", (value,))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error setting DKP formula: {e}")
        return False


