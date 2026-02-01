import sqlite3
import logging
import pandas as pd
from contextlib import closing
from .base import get_connection, logger as base_logger

logger = logging.getLogger('db_manager.kvk')

def import_snapshot(file_path: str, kvk_name: str, period_key: str, snapshot_type: str):
    """Imports a snapshot (Start/End) from Excel into the kvk_snapshots table."""
    try:
        df = pd.read_excel(file_path)
        df.columns = [c.strip().lower() for c in df.columns]
        
        col_map = {
            'player_id': ['character id', 'governor id', 'id', 'player id', 'playerid', 'char id'],
            'player_name': ['username', 'governor name', 'name', 'player name', 'playername'],
            'power': ['current power', 'power', 'pwr'],
            'kill_points': ['kill points', 'kp', 'killpoints', 'total kill points'],
            'deaths': ['dead', 'deaths', 'dead units'],
            't1_kills': ['t1 kills', 'tier 1 kills', 't1'],
            't2_kills': ['t2 kills', 'tier 2 kills', 't2'],
            't3_kills': ['t3 kills', 'tier 3 kills', 't3'],
            't4_kills': ['t4 kills', 'tier 4 kills', 't4'],
            't5_kills': ['t5 kills', 'tier 5 kills', 't5']
        }
        
        found_cols = {}
        for target, variations in col_map.items():
            for var in variations:
                if var in df.columns:
                    found_cols[target] = var
                    break
        
        required = ['player_id', 'player_name', 'power', 'kill_points', 'deaths']
        missing = [r for r in required if r not in found_cols]
        if missing:
            return False, f"Missing required columns: {', '.join(missing)}"

        data_to_insert = []
        for _, row in df.iterrows():
            data_to_insert.append((
                int(row[found_cols['player_id']]),
                str(row[found_cols['player_name']]),
                int(row[found_cols['power']]),
                int(row[found_cols['kill_points']]),
                int(row[found_cols['deaths']]),
                int(row.get(found_cols.get('t1_kills'), 0)),
                int(row.get(found_cols.get('t2_kills'), 0)),
                int(row.get(found_cols.get('t3_kills'), 0)),
                int(row.get(found_cols.get('t4_kills'), 0)),
                int(row.get(found_cols.get('t5_kills'), 0)),
                kvk_name,
                period_key,
                snapshot_type
            ))

        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT OR REPLACE INTO kvk_snapshots 
                (player_id, player_name, power, kill_points, deaths, t1_kills, t2_kills, t3_kills, t4_kills, t5_kills, kvk_name, period_key, snapshot_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', data_to_insert)
            conn.commit()
        
        return True, f"Successfully imported {len(data_to_insert)} records."
    except Exception as e:
        logger.error(f"Error importing snapshot: {e}")
        return False, str(e)

def import_requirements(file_path: str, kvk_name: str):
    """Imports KvK requirements from Excel."""
    try:
        df = pd.read_excel(file_path)
        df.columns = [c.strip().lower() for c in df.columns]
        
        col_map = {
            'min_power': ['min power', 'min_power', 'power from'],
            'max_power': ['max power', 'max_power', 'power to'],
            'required_kills': ['required kills', 'kills', 'kill goal', 'required_kills'],
            'required_deaths': ['required deaths', 'deaths', 'death goal', 'required_deaths']
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

        data_to_insert = []
        for _, row in df.iterrows():
            data_to_insert.append((
                kvk_name,
                int(row[found_cols['min_power']]),
                int(row[found_cols['max_power']]),
                int(row[found_cols['required_kills']]),
                int(row[found_cols['required_deaths']])
            ))

        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM kvk_requirements WHERE kvk_name = ?", (kvk_name,))
            cursor.executemany('''
                INSERT INTO kvk_requirements (kvk_name, min_power, max_power, required_kills, required_deaths)
                VALUES (?, ?, ?, ?, ?)
            ''', data_to_insert)
            conn.commit()
            
        return True, f"Imported {len(data_to_insert)} requirement brackets."
    except Exception as e:
        logger.error(f"Error importing requirements: {e}")
        return False, str(e)

def get_snapshot_data(kvk_name: str, period_key: str, snapshot_type: str):
    """Retrieves snapshot data as a dictionary {player_id: row}."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM kvk_snapshots 
                WHERE kvk_name = ? AND period_key = ? AND snapshot_type = ?
            ''', (kvk_name, period_key, snapshot_type))
            return {row['player_id']: dict(row) for row in cursor.fetchall()}
    except Exception as e:
        logger.error(f"Error getting snapshot data: {e}")
        return {}

def delete_snapshot(kvk_name: str, period_key: str, snapshot_type: str):
    """Deletes a specific snapshot batch."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM kvk_snapshots 
                WHERE kvk_name = ? AND period_key = ? AND snapshot_type = ?
            ''', (kvk_name, period_key, snapshot_type))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error deleting snapshot: {e}")
        return False

def save_period_results(results: list):
    """Saves calculated period results."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT OR REPLACE INTO kvk_stats 
                (player_id, player_name, power, kill_points, deaths, t1_kills, t2_kills, t3_kills, t4_kills, t5_kills, kvk_name, period_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', results)
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving period results: {e}")
        return False

def get_requirements(kvk_name: str, power: int):
    """Returns requirements for the given KvK and player power."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM kvk_requirements 
                WHERE kvk_name = ? AND ? BETWEEN min_power AND max_power
            ''', (kvk_name, power))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error getting requirements: {e}")
        return None

def get_all_requirements(kvk_name: str):
    """Returns all requirements for the given KvK, sorted by power descending."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM kvk_requirements 
                WHERE kvk_name = ? ORDER BY min_power DESC
            ''', (kvk_name,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting all requirements: {e}")
        return []

def save_requirements_batch(kvk_name: str, requirements: list):
    """Saves a list of requirements for KvK."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM kvk_requirements WHERE kvk_name = ?", (kvk_name,))
            data = [(kvk_name, r['min_power'], r['max_power'], r['required_kills'], r['required_deaths']) for r in requirements]
            cursor.executemany('''
                INSERT INTO kvk_requirements (kvk_name, min_power, max_power, required_kills, required_deaths)
                VALUES (?, ?, ?, ?, ?)
            ''', data)
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving requirements batch: {e}")
        return False

def set_kvk_dates(kvk_name: str, start_date: str, end_date: str):
    """Sets the start and end dates for a KvK season."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE kvk_seasons 
                SET start_date = ?, end_date = ? 
                WHERE value = ?
            ''', (start_date, end_date, kvk_name))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error setting KvK dates: {e}")
        return False

def archive_kvk_data(current_name: str, archive_name: str):
    """Archives KvK data by renaming it in the stats and snapshots tables."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            
            # First, get the original label to preserve it
            cursor.execute("SELECT label, start_date, end_date FROM kvk_seasons WHERE value = ?", (current_name,))
            row = cursor.fetchone()
            original_label = row[0] if row else current_name
            start_date = row[1] if row else None
            end_date = row[2] if row else None
            
            # Create a display label with dates if available
            if start_date and end_date:
                display_label = f"{original_label} ({start_date} - {end_date})"
            else:
                display_label = original_label
            
            # Update stats
            cursor.execute("UPDATE kvk_stats SET kvk_name = ? WHERE kvk_name = ?", (archive_name, current_name))
            # Update snapshots
            cursor.execute("UPDATE kvk_snapshots SET kvk_name = ? WHERE kvk_name = ?", (archive_name, current_name))
            # Update requirements
            cursor.execute("UPDATE kvk_requirements SET kvk_name = ? WHERE kvk_name = ?", (archive_name, current_name))
            # Update fort stats
            cursor.execute("UPDATE fort_stats SET kvk_name = ? WHERE kvk_name = ?", (archive_name, current_name))
            cursor.execute("UPDATE fort_periods SET kvk_name = ? WHERE kvk_name = ?", (archive_name, current_name))
            
            # Update season definition - preserve the label, only update value (key)
            cursor.execute("""
                UPDATE kvk_seasons 
                SET value = ?, label = ?, is_active = 0, is_archived = 1 
                WHERE value = ?
            """, (archive_name, display_label, current_name))
            
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error archiving KvK data: {e}")
        return False

def rename_kvk_season(old_name: str, new_name: str):
    """Renames a KvK season across all tables."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            # Check if new name exists
            cursor.execute("SELECT 1 FROM kvk_seasons WHERE value = ?", (new_name,))
            if cursor.fetchone():
                return False, f"Season '{new_name}' already exists."

            # Update all tables
            cursor.execute("UPDATE kvk_stats SET kvk_name = ? WHERE kvk_name = ?", (new_name, old_name))
            cursor.execute("UPDATE kvk_snapshots SET kvk_name = ? WHERE kvk_name = ?", (new_name, old_name))
            cursor.execute("UPDATE kvk_requirements SET kvk_name = ? WHERE kvk_name = ?", (new_name, old_name))
            cursor.execute("UPDATE fort_stats SET kvk_name = ? WHERE kvk_name = ?", (new_name, old_name))
            cursor.execute("UPDATE fort_periods SET kvk_name = ? WHERE kvk_name = ?", (new_name, old_name))
            cursor.execute("UPDATE kingdom_players SET kvk_name = ? WHERE kvk_name = ?", (new_name, old_name))
            
            # Update season definition
            cursor.execute("UPDATE kvk_seasons SET value = ?, label = ? WHERE value = ?", (new_name, new_name, old_name))
            
            # Update current settings if applicable
            cursor.execute("UPDATE kvk_settings SET setting_value = ? WHERE setting_key = 'current_kvk' AND setting_value = ?", (new_name, old_name))
            
            conn.commit()
        return True, f"Successfully renamed '{old_name}' to '{new_name}'."
    except Exception as e:
        logger.error(f"Error renaming KvK season: {e}")
        return False, str(e)

def get_all_seasons():
    """Returns all available KvK seasons (active, available, and archived)."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM kvk_seasons ORDER BY is_active DESC, value DESC")
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting all seasons: {e}")
        return []

# Cache for frequently called functions
_cache = {}
_cache_timestamps = {}
CACHE_TTL = 60  # seconds

def _get_cached(key, fetch_func, ttl=CACHE_TTL):
    """Helper to get cached value or fetch fresh."""
    import time
    current_time = time.time()
    
    if key in _cache:
        if current_time - _cache_timestamps.get(key, 0) < ttl:
            return _cache[key]
    
    result = fetch_func()
    _cache[key] = result
    _cache_timestamps[key] = current_time
    return result

def clear_season_cache():
    """Clears the season cache. Call after modifying seasons."""
    _cache.pop('played_seasons', None)
    _cache.pop('current_kvk', None)

def get_played_seasons():
    """Returns only active or archived KvK seasons (excluding templates). Cached."""
    def fetch():
        try:
            with closing(get_connection()) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM kvk_seasons WHERE is_active = 1 OR is_archived = 1 ORDER BY is_active DESC, value DESC")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting played seasons: {e}")
            return []
    
    return _get_cached('played_seasons', fetch)


def delete_kvk_season(kvk_name: str):
    """Permanently deletes a KvK season and all associated data."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM kvk_stats WHERE kvk_name = ?", (kvk_name,))
            cursor.execute("DELETE FROM kvk_snapshots WHERE kvk_name = ?", (kvk_name,))
            cursor.execute("DELETE FROM kvk_requirements WHERE kvk_name = ?", (kvk_name,))
            cursor.execute("DELETE FROM kvk_seasons WHERE value = ?", (kvk_name,))
            cursor.execute("DELETE FROM fort_stats WHERE kvk_name = ?", (kvk_name,))
            cursor.execute("DELETE FROM fort_periods WHERE kvk_name = ?", (kvk_name,))
            conn.commit()
        return True, f"Season {kvk_name} and all associated data deleted."
    except Exception as e:
        logger.error(f"Error deleting KvK season: {e}")
        return False, str(e)

def seed_seasons(default_options: list):
    """Populates the kvk_seasons table with defaults if empty."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM kvk_seasons")
            if cursor.fetchone()[0] == 0:
                data = [(opt['value'], opt['label'], opt.get('description', '')) for opt in default_options]
                cursor.executemany("INSERT INTO kvk_seasons (value, label, description) VALUES (?, ?, ?)", data)
                conn.commit()
                logger.info("Seeded default KvK seasons.")
    except Exception as e:
        logger.error(f"Error seeding seasons: {e}")

def get_current_kvk_name():
    """Returns the current KvK name from the database. Cached."""
    def fetch():
        try:
            with closing(get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT setting_value FROM kvk_settings WHERE setting_key = 'current_kvk'")
                row = cursor.fetchone()
                return row[0] if row else "Not set"
        except Exception as e:
            logger.error(f"Error getting current KvK name: {e}")
            return "Not set"
    
    return _get_cached('current_kvk', fetch)

def create_kvk_season(name: str, start_date: str = None, end_date: str = None, make_active: bool = True):
    """Creates a new KvK season with optional dates and sets it as active."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            
            # Get existing keys to ensure uniqueness
            cursor.execute("SELECT value FROM kvk_seasons")
            existing_keys = [row[0] for row in cursor.fetchall()]
            
            # Generate a unique value (key) from the name using helper
            from core.helpers import generate_unique_key
            value = generate_unique_key(name, existing_keys)
            
            # Reset all active flags if making this one active
            if make_active:
                cursor.execute("UPDATE kvk_seasons SET is_active = 0")
            
            # Insert new season
            cursor.execute('''
                INSERT INTO kvk_seasons (value, label, start_date, end_date, is_active, is_archived)
                VALUES (?, ?, ?, ?, ?, 0)
            ''', (value, name, start_date, end_date, 1 if make_active else 0))
            
            # Also update kvk_settings if making active
            if make_active:
                cursor.execute("INSERT OR REPLACE INTO kvk_settings (setting_key, setting_value) VALUES ('current_kvk', ?)", (value,))
            
            conn.commit()
        clear_season_cache()  # Clear cache after creating
        return True, f"Season **{name}** created successfully! (Key: `{value}`)"
    except Exception as e:
        logger.error(f"Error creating KvK season: {e}")
        return False, str(e)

def set_current_kvk_name(kvk_name: str):
    """Sets the current KvK name in the database."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO kvk_settings (setting_key, setting_value) VALUES ('current_kvk', ?)", (kvk_name,))
            # Also update kvk_seasons to mark it as active
            cursor.execute("UPDATE kvk_seasons SET is_active = 0") # Reset all
            cursor.execute("UPDATE kvk_seasons SET is_active = 1 WHERE value = ?", (kvk_name,))
            conn.commit()
        clear_season_cache()  # Clear cache after changing active season
        return True
    except Exception as e:
        logger.error(f"Error setting current KvK name: {e}")
        return False

def get_player_stats_by_period(player_id: int, kvk_name: str, period_key: str = "all"):
    """Retrieves player statistics for a specific period or all periods."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if period_key == "all":
                cursor.execute('''
                    SELECT 
                        player_name,
                        MAX(power) as total_power,
                        SUM(kill_points) as total_kill_points,
                        SUM(deaths) as total_deaths,
                        SUM(t1_kills) as total_t1_kills,
                        SUM(t2_kills) as total_t2_kills,
                        SUM(t3_kills) as total_t3_kills,
                        SUM(t4_kills) as total_t4_kills,
                        SUM(t5_kills) as total_t5_kills
                    FROM kvk_stats
                    WHERE player_id = ? AND kvk_name = ?
                    GROUP BY player_id
                ''', (player_id, kvk_name))
            else:
                cursor.execute('''
                    SELECT 
                        player_name,
                        power as total_power,
                        kill_points as total_kill_points,
                        deaths as total_deaths,
                        t1_kills as total_t1_kills,
                        t2_kills as total_t2_kills,
                        t3_kills as total_t3_kills,
                        t4_kills as total_t4_kills,
                        t5_kills as total_t5_kills
                    FROM kvk_stats
                    WHERE player_id = ? AND kvk_name = ? AND period_key = ?
                ''', (player_id, kvk_name, period_key))
            
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error getting player stats by period: {e}")
        return None

def get_kingdom_stats_by_period(kvk_name: str, period_key: str = "all"):
    """Retrieves kingdom statistics for a specific period or all periods."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if period_key == "all":
                cursor.execute('''
                    SELECT 
                        COUNT(DISTINCT player_id) as player_count,
                        SUM(power) as kingdom_power,
                        SUM(kill_points) as kingdom_kill_points,
                        SUM(deaths) as kingdom_deaths,
                        SUM(t4_kills) as kingdom_t4_kills,
                        SUM(t5_kills) as kingdom_t5_kills
                    FROM (
                        SELECT player_id, MAX(power) as power, SUM(kill_points) as kill_points, 
                               SUM(deaths) as deaths, SUM(t4_kills) as t4_kills, SUM(t5_kills) as t5_kills
                        FROM kvk_stats WHERE kvk_name = ?
                        GROUP BY player_id
                    )
                ''', (kvk_name,))
            else:
                cursor.execute('''
                    SELECT 
                        COUNT(player_id) as player_count,
                        SUM(power) as kingdom_power,
                        SUM(kill_points) as kingdom_kill_points,
                        SUM(deaths) as kingdom_deaths,
                        SUM(t4_kills) as kingdom_t4_kills,
                        SUM(t5_kills) as kingdom_t5_kills
                    FROM kvk_stats
                    WHERE kvk_name = ? AND period_key = ?
                ''', (kvk_name, period_key))
            
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error getting kingdom stats by period: {e}")
        return None

def get_all_periods(kvk_name: str):
    """Returns all unique periods (snapshots) for a specific KvK."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT period_key FROM kvk_snapshots WHERE kvk_name = ? ORDER BY period_key", (kvk_name,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting all periods: {e}")
        return []

def get_all_kvk_stats(kvk_name: str):
    """Retrieves stats for all players in a specific KvK."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    player_id, player_name,
                    MAX(power) as total_power,
                    SUM(kill_points) as total_kill_points,
                    SUM(deaths) as total_deaths,
                    SUM(t4_kills) as total_t4_kills,
                    SUM(t5_kills) as total_t5_kills
                FROM kvk_stats
                WHERE kvk_name = ?
                GROUP BY player_id
                ORDER BY total_kill_points DESC
            ''', (kvk_name,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting all KvK stats: {e}")
        return []

def get_player_start_snapshot(player_id: int, kvk_name: str):
    """Retrieves the 'start' snapshot for a player in a specific KvK."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Find the very first snapshot for this player in this KvK
            cursor.execute('''
                SELECT * FROM kvk_snapshots 
                WHERE player_id = ? AND kvk_name = ? AND snapshot_type = 'start'
                ORDER BY period_key ASC LIMIT 1
            ''', (player_id, kvk_name))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error getting player start snapshot: {e}")
        return None

def get_total_stats_for_players(player_ids: list, kvk_name: str):
    """Retrieves total player statistics for multiple players in a single query."""
    if not player_ids: return {}
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            placeholders = ','.join(['?'] * len(player_ids))
            cursor.execute(f'''
                SELECT 
                    player_id, player_name,
                    MAX(power) as total_power,
                    SUM(kill_points) as total_kill_points,
                    SUM(deaths) as total_deaths,
                    SUM(t1_kills) as total_t1_kills,
                    SUM(t2_kills) as total_t2_kills,
                    SUM(t3_kills) as total_t3_kills,
                    SUM(t4_kills) as total_t4_kills,
                    SUM(t5_kills) as total_t5_kills
                FROM kvk_stats
                WHERE player_id IN ({placeholders}) AND kvk_name = ?
                GROUP BY player_id
            ''', (*player_ids, kvk_name))
            return {row['player_id']: dict(row) for row in cursor.fetchall()}
    except Exception as e:
        logger.error(f"Error getting total stats for players: {e}")
        return {}

def get_kingdom_start_snapshot(kvk_name: str):
    """Gets aggregated kingdom-wide start snapshot (first period's start)."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Find the first period key
            cursor.execute("SELECT MIN(period_key) FROM kvk_snapshots WHERE kvk_name = ?", (kvk_name,))
            first_period = cursor.fetchone()[0]
            if not first_period: return None
            
            cursor.execute('''
                SELECT 
                    SUM(power) as kingdom_power,
                    SUM(kill_points) as kingdom_kill_points,
                    SUM(deaths) as kingdom_deaths
                FROM kvk_snapshots 
                WHERE kvk_name = ? AND period_key = ? AND snapshot_type = 'start'
            ''', (kvk_name, first_period))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error getting kingdom start snapshot: {e}")
        return None

def get_snapshot_player_data(kvk_name: str, period_key: str, snapshot_type: str, player_id: int):
    """Retrieves snapshot data for a specific player."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM kvk_snapshots 
                WHERE kvk_name = ? AND period_key = ? AND snapshot_type = ? AND player_id = ?
            ''', (kvk_name, period_key, snapshot_type, player_id))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error getting snapshot player data: {e}")
        return None

def get_player_rank(player_id: int, kvk_name: str):
    """Gets player's DKP rank within the kingdom."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            # Rank by total kill points across all periods in this KvK
            cursor.execute('''
                SELECT rank FROM (
                    SELECT player_id, RANK() OVER (ORDER BY SUM(kill_points) DESC) as rank
                    FROM kvk_stats WHERE kvk_name = ?
                    GROUP BY player_id
                ) WHERE player_id = ?
            ''', (kvk_name, player_id))
            row = cursor.fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.error(f"Error getting player rank: {e}")
        return None

def get_player_stats_history(player_id: int, kvk_name: str):
    """Returns player stats history across all periods."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT period_key, kill_points, deaths, power
                FROM kvk_stats
                WHERE player_id = ? AND kvk_name = ?
                ORDER BY period_key ASC
            ''', (player_id, kvk_name))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting player stats history: {e}")
        return []

def get_player_stats(player_id: int, kvk_name: str, period_key: str):
    """Retrieves player statistics by ID for a specific KvK and period."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM kvk_stats
                WHERE player_id = ? AND kvk_name = ? AND period_key = ?
            ''', (player_id, kvk_name, period_key))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error retrieving player statistics: {e}")
        return None

def get_total_player_stats(player_id: int, kvk_name: str):
    """Retrieves total player statistics for all periods within a KvK."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT MAX(power) as total_power,
                       SUM(kill_points) as total_kill_points,
                       SUM(deaths) as total_deaths,
                       SUM(t1_kills) as total_t1_kills,
                       SUM(t2_kills) as total_t2_kills,
                       SUM(t3_kills) as total_t3_kills,
                       SUM(t4_kills) as total_t4_kills,
                       SUM(t5_kills) as total_t5_kills,
                       player_name
                FROM kvk_stats
                WHERE player_id = ? AND kvk_name = ?
                GROUP BY player_id
            ''', (player_id, kvk_name))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error retrieving total player statistics: {e}")
        return None

def get_kingdom_stats(kvk_name: str):
    """Retrieves aggregated statistics for the entire kingdom for a specific KvK."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    SUM(total_power) as kingdom_power,
                    SUM(total_kill_points) as kingdom_kill_points,
                    SUM(total_deaths) as kingdom_deaths,
                    SUM(total_t1_kills) as kingdom_t1_kills,
                    SUM(total_t2_kills) as kingdom_t2_kills,
                    SUM(total_t3_kills) as kingdom_t3_kills,
                    SUM(total_t4_kills) as kingdom_t4_kills,
                    SUM(total_t5_kills) as kingdom_t5_kills,
                    COUNT(*) as player_count
                FROM (
                    SELECT 
                        MAX(power) as total_power,
                        SUM(kill_points) as total_kill_points,
                        SUM(deaths) as total_deaths,
                        SUM(t1_kills) as total_t1_kills,
                        SUM(t2_kills) as total_t2_kills,
                        SUM(t3_kills) as total_t3_kills,
                        SUM(t4_kills) as total_t4_kills,
                        SUM(t5_kills) as total_t5_kills
                    FROM kvk_stats
                    WHERE kvk_name = ?
                    GROUP BY player_id
                )
            ''', (kvk_name,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error retrieving kingdom stats: {e}")
        return None
def get_player_cross_kvk_stats(player_id: int, kvk_names: list) -> list:
    """
    Batch retrieves player stats across multiple KvK seasons in a single query.
    Returns list of dicts with season label and aggregated stats.
    
    This is more efficient than calling get_player_stats_by_period() in a loop.
    """
    if not kvk_names:
        return []
    
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Build IN clause placeholders
            placeholders = ','.join('?' * len(kvk_names))
            
            query = f'''
                SELECT 
                    kvk_name,
                    player_name,
                    MAX(power) as total_power,
                    SUM(kill_points) as total_kill_points,
                    SUM(deaths) as total_deaths,
                    SUM(t4_kills) as total_t4_kills,
                    SUM(t5_kills) as total_t5_kills
                FROM kvk_stats
                WHERE player_id = ? AND kvk_name IN ({placeholders})
                GROUP BY kvk_name
                ORDER BY kvk_name
            '''
            
            cursor.execute(query, [player_id] + kvk_names)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting cross-KvK stats: {e}")
        return []
