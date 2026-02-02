import sqlite3
import logging
from contextlib import closing
from .base import get_connection

logger = logging.getLogger('db_manager.forts')

def import_fort_stats(stats_list: list, period_label: str = "Total"):
    """
    Imports fort statistics for a specific period.
    stats_list: list of dicts {player_id, player_name, forts_joined, forts_launched, total_forts, penalties, kvk_name}
    period_label: User-friendly name for the period (e.g., "Week 1")
    """
    if not stats_list: return False
    
    kvk_name = stats_list[0]['kvk_name']
    # Generate a period key from label (e.g., "Week 1" -> "week_1")
    period_key = period_label.lower().replace(" ", "_")
    
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            
            # 1. Register the period
            cursor.execute('''
                INSERT INTO fort_periods (kvk_name, period_key, period_label, created_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(kvk_name, period_key) DO UPDATE SET
                    created_at = CURRENT_TIMESTAMP
            ''', (kvk_name, period_key, period_label))
            
            # 2. Insert stats
            data = []
            for s in stats_list:
                data.append((
                    s['player_id'], s['player_name'], s['forts_joined'], 
                    s['forts_launched'], s['total_forts'], s['penalties'],
                    s['kvk_name'], period_key
                ))
            
            cursor.executemany('''
                INSERT OR REPLACE INTO fort_stats 
                (player_id, player_name, forts_joined, forts_launched, total_forts, penalties, kvk_name, period_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', data)
            
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error importing fort stats: {e}")
        return False

def get_fort_periods(kvk_name: str):
    """Returns all fort periods for a KvK."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM fort_periods WHERE kvk_name = ? ORDER BY created_at DESC", (kvk_name,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting fort periods: {e}")
        return []

def get_player_fort_stats_history(player_id: int, kvk_name: str):
    """Returns player's fort stats across all periods in a KvK."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT fs.*, fp.period_label 
                FROM fort_stats fs
                JOIN fort_periods fp ON fs.kvk_name = fp.kvk_name AND fs.period_key = fp.period_key
                WHERE fs.player_id = ? AND fs.kvk_name = ?
                ORDER BY fp.created_at ASC
            ''', (player_id, kvk_name))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting player fort history: {e}")
        return []

def get_fort_leaderboard(kvk_name: str, period_key: str = "total"):
    """
    Returns fort leaderboard. 
    Shows ALL players known in that KvK.
    If period_key is "total", sums up all periods.
    """
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if period_key == "total":
                cursor.execute('''
                    SELECT 
                        player_id, player_name,
                        SUM(forts_joined) as forts_joined,
                        SUM(forts_launched) as forts_launched,
                        SUM(total_forts) as total_forts,
                        SUM(penalties) as penalties
                    FROM fort_stats
                    WHERE kvk_name = ?
                    GROUP BY player_id
                    ORDER BY total_forts DESC
                ''', (kvk_name,))
            else:
                # Get all players known in this KvK, then join with specific period stats
                cursor.execute('''
                    SELECT 
                        p.player_id, 
                        p.player_name,
                        COALESCE(fs.forts_joined, 0) as forts_joined,
                        COALESCE(fs.forts_launched, 0) as forts_launched,
                        COALESCE(fs.total_forts, 0) as total_forts,
                        COALESCE(fs.penalties, 0) as penalties
                    FROM (
                        SELECT DISTINCT player_id, player_name 
                        FROM fort_stats 
                        WHERE kvk_name = ?
                    ) p
                    LEFT JOIN fort_stats fs 
                        ON p.player_id = fs.player_id 
                        AND fs.kvk_name = ? 
                        AND fs.period_key = ?
                    ORDER BY total_forts DESC
                ''', (kvk_name, kvk_name, period_key))
                
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting fort leaderboard: {e}")
        return []

def get_fort_last_updated(kvk_name: str, period_key: str = "total"):
    """Returns the ISO timestamp of the last update for this period (or newest if total)."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            if period_key == "total":
                cursor.execute("SELECT MAX(created_at) FROM fort_periods WHERE kvk_name = ?", (kvk_name,))
            else:
                cursor.execute("SELECT created_at FROM fort_periods WHERE kvk_name = ? AND period_key = ?", (kvk_name, period_key))
            
            row = cursor.fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.error(f"Error getting fort last updated: {e}")
        return None

def get_latest_fort_activity():
    """Returns the (kvk_name, period_key) of the most recently created fort period."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT kvk_name, period_key FROM fort_periods ORDER BY created_at DESC LIMIT 1")
            row = cursor.fetchone()
            return (row[0], row[1]) if row else (None, None)
    except Exception as e:
        logger.error(f"Error getting latest fort activity: {e}")
        return None, None

def get_fort_seasons():
    """Returns a list of all unique seasons (kvk_name) in fort_stats."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT kvk_name FROM fort_stats ORDER BY kvk_name")
            return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting fort seasons: {e}")
        return []

def get_fort_stats(player_id: int, kvk_name: str):
    """Gets fort stats for a player in a KvK."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    SUM(forts_joined) as forts_joined,
                    SUM(forts_launched) as forts_launched,
                    SUM(total_forts) as total_forts,
                    SUM(penalties) as penalties
                FROM fort_stats
                WHERE player_id = ? AND kvk_name = ?
            ''', (player_id, kvk_name))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error getting fort stats: {e}")
        return None

def clear_all_fort_data():
    """Deletes all records from fort_stats and fort_periods tables."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM fort_stats")
            cursor.execute("DELETE FROM fort_periods")
            conn.commit()
        logger.info("All fort data has been cleared from the database.")
        return True
    except sqlite3.Error as e:
        logger.error(f"Error clearing fort data: {e}")
        return False
        return False

def delete_fort_period(kvk_name: str, period_key: str):
    """Deletes all fort data for a specific period."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            # Delete stats
            cursor.execute('''
                DELETE FROM fort_stats 
                WHERE kvk_name = ? AND period_key = ?
            ''', (kvk_name, period_key))
            
            # Delete period definition
            cursor.execute('''
                DELETE FROM fort_periods 
                WHERE kvk_name = ? AND period_key = ?
            ''', (kvk_name, period_key))
            
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error deleting fort period: {e}")
        return False
