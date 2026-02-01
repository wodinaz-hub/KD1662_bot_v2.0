import sqlite3
import logging
import pandas as pd
from contextlib import closing
from .base import get_connection

logger = logging.getLogger('db_manager.players')

def import_kingdom_players(file_path: str, kvk_name: str):
    """Imports the base list of kingdom players from Excel."""
    try:
        df = pd.read_excel(file_path)
        df.columns = [c.strip().lower() for c in df.columns]
        
        col_map = {
            'player_id': ['character id', 'governor id', 'id', 'player id', 'playerid', 'char id'],
            'player_name': ['username', 'governor name', 'name', 'player name', 'playername'],
            'power': ['current power', 'power', 'pwr']
        }
        
        found_cols = {}
        for target, variations in col_map.items():
            for var in variations:
                if var in df.columns:
                    found_cols[target] = var
                    break
        
        required = ['player_id', 'player_name', 'power']
        missing = [r for r in required if r not in found_cols]
        if missing:
            return False, f"Missing columns: {', '.join(missing)}"

        data_to_insert = []
        for _, row in df.iterrows():
            data_to_insert.append((
                int(row[found_cols['player_id']]),
                str(row[found_cols['player_name']]),
                int(row[found_cols['power']]),
                kvk_name
            ))

        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM kingdom_players WHERE kvk_name = ?", (kvk_name,))
            cursor.executemany('''
                INSERT INTO kingdom_players (player_id, player_name, power, kvk_name)
                VALUES (?, ?, ?, ?)
            ''', data_to_insert)
            conn.commit()
            
        return True, f"Imported {len(data_to_insert)} players."
    except Exception as e:
        logger.error(f"Error importing kingdom players: {e}")
        return False, str(e)

def get_kingdom_player(player_id: int, kvk_name: str):
    """Gets a player from the kingdom players list."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM kingdom_players WHERE player_id = ? AND kvk_name = ?", (player_id, kvk_name))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error getting kingdom player: {e}")
        return None

def get_all_kingdom_players(kvk_name: str):
    """Gets all players in the kingdom for this KvK."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM kingdom_players WHERE kvk_name = ?", (kvk_name,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting all kingdom players: {e}")
        return []

def delete_player(player_id: int):
    """Deletes all data associated with a player ID."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM kvk_stats WHERE player_id = ?", (player_id,))
            cursor.execute("DELETE FROM kvk_snapshots WHERE player_id = ?", (player_id,))
            cursor.execute("DELETE FROM linked_accounts WHERE player_id = ?", (player_id,))
            cursor.execute("DELETE FROM fort_stats WHERE player_id = ?", (player_id,))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error deleting player: {e}")
        return False

def link_account(discord_id: int, player_id: int, account_type: str = 'main'):
    """Links a game account to a Discord account."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO linked_accounts (discord_id, player_id, account_type)
                VALUES (?, ?, ?)
            ''', (discord_id, player_id, account_type))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error linking account: {e}")
        return False

def get_linked_accounts(discord_id: int):
    """Returns a list of all linked game accounts for a Discord ID with player names."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Try to join with kingdom_players or kvk_stats to get a name
            cursor.execute('''
                SELECT la.*, COALESCE(kp.player_name, ks.player_name, 'Unknown') as player_name
                FROM linked_accounts la
                LEFT JOIN kingdom_players kp ON la.player_id = kp.player_id
                LEFT JOIN (SELECT player_id, player_name FROM kvk_stats GROUP BY player_id) ks ON la.player_id = ks.player_id
                WHERE la.discord_id = ?
            ''', (discord_id,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting linked accounts: {e}")
        return []

def get_all_linked_accounts_full():
    """Returns a list of all linked accounts (Discord ID -> Player ID) with Player Name."""
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT la.*, COALESCE(kp.player_name, ks.player_name, 'Unknown') as player_name
                FROM linked_accounts la
                LEFT JOIN kingdom_players kp ON la.player_id = kp.player_id
                LEFT JOIN (SELECT player_id, player_name FROM kvk_stats GROUP BY player_id) ks ON la.player_id = ks.player_id
            ''')
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting all linked accounts: {e}")
        return []

def unlink_account(discord_id: int, player_id: int):
    """Unlinks a game account from a Discord account."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM linked_accounts WHERE discord_id = ? AND player_id = ?", (discord_id, player_id))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error unlinking account: {e}")
        return False

def add_new_player(player_id: int, name: str, power: int, kvk_name: str):
    """Adds or updates a player in the kingdom_players table."""
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO kingdom_players (player_id, player_name, power, kvk_name)
                VALUES (?, ?, ?, ?)
            ''', (player_id, name, power, kvk_name))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error adding new player: {e}")
        return False

def get_all_players_global():
    """
    Returns a list of ALL players found in the database (snapshots or kingdom roster).
    Returns the entry with the highest Kill Points (or Power if no KP) for each player ID.
    """
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # We want one row per player_id.
            # Strategy:
            # 1. Get latest snapshot for each player (Highest KP -> Highest Power)
            # 2. Get info from kingdom_players for anyone not in snapshots.
            
            cursor.execute('''
                WITH RankedSnaps AS (
                    SELECT 
                        player_id, player_name, power, kill_points, deaths,
                        ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY kill_points DESC, power DESC) as rn
                    FROM kvk_snapshots
                ),
                DistinctRoaster AS (
                    SELECT player_id, player_name, MAX(power) as power
                    FROM kingdom_players
                    GROUP BY player_id
                )
                
                SELECT 
                    COALESCE(rs.player_id, dr.player_id) as player_id,
                    COALESCE(rs.player_name, dr.player_name) as player_name,
                    COALESCE(rs.power, dr.power) as power,
                    COALESCE(rs.kill_points, 0) as kill_points,
                    COALESCE(rs.deaths, 0) as deaths
                FROM DistinctRoaster dr
                FULL OUTER JOIN RankedSnaps rs ON dr.player_id = rs.player_id AND rs.rn = 1
                WHERE rs.rn = 1 OR rs.player_id IS NULL
            ''')
            
            # Note: SQLite < 3.39 doesn't support FULL OUTER JOIN.
            # If that fails, we use UNION ALL strategy.
            # Most discord.py environments have recent sqlite, but let's be safe if it errors?
            # Actually, standard fallback is LEFT JOIN + UNION ALL (RIGHT JOIN equivalent or just getting the others).
            
            # Safer query for compatibility:
            # Get all form Snaps + all from Roaster not in Snaps.
            
            query_safe = '''
                SELECT 
                    player_id, player_name, power, kill_points, deaths, kvk_name
                FROM (
                    SELECT 
                        player_id, player_name, power, kill_points, deaths, kvk_name,
                        ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY kill_points DESC, power DESC) as rn
                    FROM kvk_snapshots
                ) WHERE rn = 1
                
                UNION ALL
                
                SELECT 
                    player_id, player_name, MAX(power) as power, 
                    0 as kill_points, 0 as deaths, 'Roster' as kvk_name
                FROM kingdom_players
                WHERE player_id NOT IN (SELECT DISTINCT player_id FROM kvk_snapshots)
                GROUP BY player_id
            '''
            
            cursor.execute(query_safe)
            return [dict(row) for row in cursor.fetchall()]
            
    except Exception as e:
        logger.error(f"Error getting global player list: {e}")
        return []
