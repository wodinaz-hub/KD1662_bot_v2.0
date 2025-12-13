import sqlite3
import os
import logging
import pandas as pd

# Logging configuration
logger = logging.getLogger('db_manager')

# Define database path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
DATABASE_PATH = os.path.join(DATA_DIR, 'kvk_data.db')


def create_tables():
    """
    Creates database tables if they do not exist.
    """
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Table for player statistics (Period results)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kvk_stats (
                player_id INTEGER,
                player_name TEXT NOT NULL,
                power INTEGER,
                kill_points INTEGER,
                deaths INTEGER,
                t1_kills INTEGER,
                t2_kills INTEGER,
                t3_kills INTEGER,
                t4_kills INTEGER,
                t5_kills INTEGER,
                kvk_name TEXT NOT NULL,
                period_key TEXT NOT NULL,
                PRIMARY KEY (player_id, kvk_name, period_key)
            )
        ''')

        # Table for raw snapshots (Start/End)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kvk_snapshots (
                player_id INTEGER,
                player_name TEXT NOT NULL,
                power INTEGER,
                kill_points INTEGER,
                deaths INTEGER,
                t1_kills INTEGER,
                t2_kills INTEGER,
                t3_kills INTEGER,
                t4_kills INTEGER,
                t5_kills INTEGER,
                kvk_name TEXT NOT NULL,
                period_key TEXT NOT NULL,
                snapshot_type TEXT NOT NULL, -- 'start' or 'end'
                PRIMARY KEY (player_id, kvk_name, period_key, snapshot_type)
            )
        ''')

        # Table for requirements
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kvk_requirements (
                kvk_name TEXT NOT NULL,
                min_power INTEGER,
                max_power INTEGER,
                required_kills INTEGER,
                required_deaths INTEGER,
                PRIMARY KEY (kvk_name, min_power)
            )
        ''')
        
        # Attempt migration: Rename column required_kill_points -> required_kills if exists
        try:
            # Check if column exists
            cursor.execute("PRAGMA table_info(kvk_requirements)")
            columns = [info[1] for info in cursor.fetchall()]
            if 'required_kill_points' in columns and 'required_kills' not in columns:
                # SQLite doesn't support simple RENAME COLUMN in older versions, but let's try
                # If fails, we might need to recreate. For now, let's just add the new one and copy if needed, 
                # or just drop the table since requirements are easily re-uploaded.
                # User guide says "Upload requirements". Dropping might be safer to ensure clean state.
                # But let's try to be nice.
                cursor.execute("ALTER TABLE kvk_requirements ADD COLUMN required_kills INTEGER DEFAULT 0")
                # We can't easily migrate data because KP != Kills. 
                # So we just leave it 0 and user has to re-upload.
        except Exception:
            pass

        # Table for linking Discord IDs to game IDs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS linked_accounts (
                discord_id INTEGER,
                player_id INTEGER,
                is_main_account INTEGER DEFAULT 0,
                account_type TEXT DEFAULT 'main',
                PRIMARY KEY (discord_id, player_id)
            )
        ''')
        
        # Attempt to migrate existing table if account_type is missing
        try:
            cursor.execute("ALTER TABLE linked_accounts ADD COLUMN account_type TEXT DEFAULT 'main'")
        except sqlite3.OperationalError:
            # Column likely already exists
            pass

        # Table for storing KvK settings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kvk_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL
            )
        ''')

        # Table for admin logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                admin_name TEXT,
                action TEXT,
                details TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Table for base kingdom player list (for account linking and initial power)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kingdom_players (
                player_id INTEGER PRIMARY KEY,
                player_name TEXT NOT NULL,
                power INTEGER,
                kvk_name TEXT NOT NULL
            )
        ''')

        # Create indexes for performance optimization
        logger.info("Creating database indexes...")
        
        # Index for kvk_stats queries by KvK and period
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_kvk_stats_kvk_period 
            ON kvk_stats(kvk_name, period_key)
        ''')
        
        # Index for kvk_stats queries by player
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_kvk_stats_player 
            ON kvk_stats(kvk_name, player_id)
        ''')
        
        # Index for snapshot lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_kvk_snapshots_lookup 
            ON kvk_snapshots(kvk_name, period_key, snapshot_type)
        ''')
        
        # Index for player snapshot lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_kvk_snapshots_player 
            ON kvk_snapshots(player_id, kvk_name)
        ''')
        
        # Index for linked accounts by Discord ID
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_linked_discord 
            ON linked_accounts(discord_id)
        ''')
        
        # Index for linked accounts by Player ID
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_linked_player 
            ON linked_accounts(player_id)
        ''')
        
        # Index for requirements by KvK
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_requirements_kvk 
            ON kvk_requirements(kvk_name)
        ''')
        
        conn.commit()
        logger.info("Database tables and indexes successfully created or verified.")
    except sqlite3.Error as e:
        logger.error(f"Error creating tables: {e}")
    finally:
        if conn:
            conn.close()


def import_kingdom_players(file_path: str, kvk_name: str):
    """
    Imports the base list of kingdom players from Excel.
    This is used for account linking and determining DKP requirements based on initial power.
    Expected columns: Governor ID, Governor Name, Power
    """
    conn = None
    try:
        df = pd.read_excel(file_path)
        # Normalize column names
        df.columns = [c.strip().lower() for c in df.columns]
        
        # Try to find required columns (flexible column names)
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
        
        if len(found_cols) < 3:
            missing = [k for k in col_map.keys() if k not in found_cols]
            logger.error(f"Kingdom players file missing columns: {missing}")
            logger.error(f"Found columns: {list(df.columns)}")
            return False, 0
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Clear old players for this KvK (replace with new list)
        cursor.execute("DELETE FROM kingdom_players WHERE kvk_name = ?", (kvk_name,))
        
        imported = 0
        for index, row in df.iterrows():
            try:
                player_id = int(row[found_cols['player_id']])
                player_name = str(row[found_cols['player_name']])
                power = int(row[found_cols['power']])
                
                cursor.execute('''
                    INSERT OR REPLACE INTO kingdom_players (player_id, player_name, power, kvk_name)
                    VALUES (?, ?, ?, ?)
                ''', (player_id, player_name, power, kvk_name))
                imported += 1
            except Exception as e:
                logger.error(f"Error in player row {index + 2}: {e}")
                continue
        
        conn.commit()
        logger.info(f"Imported {imported} kingdom players for '{kvk_name}'.")
        return True, imported
    except Exception as e:
        logger.error(f"Error importing kingdom players: {e}")
        return False, 0
    finally:
        if conn:
            conn.close()


def get_kingdom_player(player_id: int, kvk_name: str):
    """Gets a player from the kingdom players list."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM kingdom_players WHERE player_id = ? AND kvk_name = ?", (player_id, kvk_name))
        return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error getting kingdom player: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_all_kingdom_players(kvk_name: str):
    """Gets all players in the kingdom for this KvK."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM kingdom_players WHERE kvk_name = ? ORDER BY power DESC", (kvk_name,))
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting kingdom players: {e}")
        return []
    finally:
        if conn:
            conn.close()


def import_snapshot(file_path: str, kvk_name: str, period_key: str, snapshot_type: str):
    """
    Imports a snapshot (Start/End) from Excel into the kvk_snapshots table.
    Supports flexible column names.
    """
    conn = None
    try:
        df = pd.read_excel(file_path)
        # Normalize column names
        df.columns = [c.strip().lower() for c in df.columns]
        
        # Flexible column mapping
        col_map = {
            'player_id': ['character id', 'governor id', 'id', 'player id', 'playerid'],
            'player_name': ['username', 'governor name', 'name', 'player name'],
            'power': ['current power', 'power', 'pwr'],
            'kill_points': ['total kill points', 'kill points', 'killpoints', 'kp', 'kills'],
            'deaths': ['deaths', 'deads', 'dead'],
            't1_kills': ['t1', 'tier 1 kills', 'tier 1', 't1 kills'],
            't2_kills': ['t2', 'tier 2 kills', 'tier 2', 't2 kills'],
            't3_kills': ['t3', 'tier 3 kills', 'tier 3', 't3 kills'],
            't4_kills': ['t4', 'tier 4 kills', 'tier 4', 't4 kills'],
            't5_kills': ['t5', 'tier 5 kills', 'tier 5', 't5 kills']
        }
        
        found_cols = {}
        for target, variations in col_map.items():
            for var in variations:
                if var in df.columns:
                    found_cols[target] = var
                    break
        
        # Check for required columns (player_id, player_name, power, kill_points, deaths are required)
        required = ['player_id', 'player_name', 'power', 'kill_points', 'deaths']
        missing = [r for r in required if r not in found_cols]
        if missing:
            logger.error(f"Snapshot file missing required columns: {missing}")
            logger.error(f"Found columns: {list(df.columns)}")
            return False

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Check for existing data and warn about overwriting
        cursor.execute("SELECT COUNT(*) FROM kvk_snapshots WHERE kvk_name = ? AND period_key = ? AND snapshot_type = ?",
                       (kvk_name, period_key, snapshot_type))
        existing_count = cursor.fetchone()[0]
        if existing_count > 0:
            logger.warning(f"Overwriting {existing_count} existing snapshot records for {kvk_name}/{period_key}/{snapshot_type}")

        # Clear old snapshot of the same type for this period if overwriting is needed
        cursor.execute("DELETE FROM kvk_snapshots WHERE kvk_name = ? AND period_key = ? AND snapshot_type = ?",
                       (kvk_name, period_key, snapshot_type))

        imported = 0
        for index, row in df.iterrows():
            try:
                player_id = int(row[found_cols['player_id']])
                player_name = str(row[found_cols['player_name']])
                power = int(row[found_cols['power']])
                kill_points = int(row[found_cols['kill_points']])
                deaths = int(row[found_cols['deaths']])
                
                # Tier kills are optional (default to 0)
                t1 = int(row.get(found_cols.get('t1_kills', ''), 0) or 0)
                t2 = int(row.get(found_cols.get('t2_kills', ''), 0) or 0)
                t3 = int(row.get(found_cols.get('t3_kills', ''), 0) or 0)
                t4 = int(row.get(found_cols.get('t4_kills', ''), 0) or 0)
                t5 = int(row.get(found_cols.get('t5_kills', ''), 0) or 0)
                
                cursor.execute('''
                    INSERT INTO kvk_snapshots (
                        player_id, player_name, power, kill_points, deaths,
                        t1_kills, t2_kills, t3_kills, t4_kills, t5_kills,
                        kvk_name, period_key, snapshot_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    player_id, player_name, power, kill_points, deaths,
                    t1, t2, t3, t4, t5, kvk_name, period_key, snapshot_type
                ))
                imported += 1
            except Exception as e:
                logger.error(f"Error processing row {index + 2}: {e}")
                continue

        conn.commit()
        logger.info(f"Snapshot '{snapshot_type}' for '{kvk_name}' - '{period_key}': imported {imported} players.")
        return True
    except Exception as e:
        logger.error(f"Error importing snapshot: {e}")
        return False
    finally:
        if conn:
            conn.close()


def import_requirements(file_path: str, kvk_name: str):
    """
    Imports KvK requirements from Excel.
    Supports multiple column name variations for flexibility.
    """
    conn = None
    try:
        df = pd.read_excel(file_path)
        # Normalize column names (remove spaces, lower case, remove underscores) for flexibility
        original_columns = list(df.columns)
        df.columns = [c.strip().lower().replace('_', ' ').replace('-', ' ') for c in df.columns]
        
        # Try to find matching columns with multiple possible names
        col_variations = {
            'min_power': ['min power', 'minpower', 'power min', 'min', 'from power', 'from'],
            'max_power': ['max power', 'maxpower', 'power max', 'max', 'to power', 'to'],
            'required_kills': ['required kills', 'kills', 'req kills', 'target kills', 'kill count'],
            'required_deaths': ['required deaths', 'required death', 'required deads', 'deaths', 'deads', 'dead', 'death']
        }
        
        # Find actual column names in dataset
        found_columns = {}
        missing_columns = []
        
        for target_col, variations in col_variations.items():
            found = False
            for variation in variations:
                if variation in df.columns:
                    found_columns[target_col] = variation
                    found = True
                    break
            if not found:
                missing_columns.append(target_col)
        
        if missing_columns:
            logger.error(f"Requirements file missing columns: {missing_columns}")
            logger.error(f"Found columns in file: {original_columns}")
            logger.error(f"Expected one of these for each: min_power ({col_variations['min_power']}), "
                        f"max_power ({col_variations['max_power']}), "
                        f"required_kills ({col_variations['required_kills']}), "
                        f"required_deaths ({col_variations['required_deaths']})")
            return False

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Clear old requirements for this KvK
        cursor.execute("DELETE FROM kvk_requirements WHERE kvk_name = ?", (kvk_name,))

        rows_imported = 0
        for index, row in df.iterrows():
            try:
                min_power = int(row[found_columns['min_power']])
                max_power = int(row[found_columns['max_power']])
                required_kills = int(row[found_columns['required_kills']])
                required_deaths = int(row[found_columns['required_deaths']])
                
                cursor.execute('''
                    INSERT INTO kvk_requirements (
                        kvk_name, min_power, max_power, required_kills, required_deaths
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (kvk_name, min_power, max_power, required_kills, required_deaths))
                rows_imported += 1
            except Exception as e:
                logger.error(f"Error in requirement row {index + 2}: {e}")
                continue

        conn.commit()
        logger.info(f"Requirements for '{kvk_name}' successfully imported. {rows_imported} rows.")
        return True
    except Exception as e:
        logger.error(f"Error importing requirements: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_snapshot_data(kvk_name: str, period_key: str, snapshot_type: str):
    """Retrieves snapshot data as a dictionary {player_id: row}."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM kvk_snapshots WHERE kvk_name = ? AND period_key = ? AND snapshot_type = ?",
                       (kvk_name, period_key, snapshot_type))
        rows = cursor.fetchall()
        return {row['player_id']: row for row in rows}
    except Exception as e:
        logger.error(f"Error retrieving snapshot: {e}")
        return {}
    finally:
        if conn: conn.close()


def save_period_results(results: list):
    """
    Saves calculated period results.
    Uses transaction to ensure atomic batch insert.
    """
    if not results:
        return True
        
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Begin explicit transaction
        cursor.execute("BEGIN IMMEDIATE TRANSACTION")
        
        for res in results:
            cursor.execute('''
                INSERT OR REPLACE INTO kvk_stats (
                    player_id, player_name, power, kill_points, deaths,
                    t1_kills, t2_kills, t3_kills, t4_kills, t5_kills,
                    kvk_name, period_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                res['player_id'], res['player_name'], res['power'],
                res['kill_points'], res['deaths'], res['t1_kills'],
                res['t2_kills'], res['t3_kills'], res['t4_kills'],
                res['t5_kills'], res['kvk_name'], res['period_key']
            ))
        
        # Commit transaction
        conn.commit()
        logger.info(f"Saved {len(results)} period results successfully.")
        return True
    except Exception as e:
        logger.error(f"Error saving results: {e}")
        if conn:
            conn.rollback()
            logger.info("Transaction rolled back due to error.")
        return False
    finally:
        if conn:
            conn.close()


def get_requirements(kvk_name: str, power: int):
    """Returns requirements for the given KvK and player power."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Find the range that power falls into
        cursor.execute('''
            SELECT * FROM kvk_requirements 
            WHERE kvk_name = ? AND ? >= min_power AND ? <= max_power
        ''', (kvk_name, power, power))
        
        return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error retrieving requirements: {e}")
        return None
    finally:
        if conn: conn.close()


def get_all_requirements(kvk_name: str):
    """Returns all requirements for the given KvK, sorted by power descending."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM kvk_requirements 
            WHERE kvk_name = ?
            ORDER BY min_power DESC
        ''', (kvk_name,))
        
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error retrieving requirements list: {e}")
        return []
    finally:
        if conn: conn.close()


def save_requirements_batch(kvk_name: str, requirements: list):
    """
    Saves a list of requirements for KvK.
    requirements: list of dicts {'min_power', 'max_power', 'required_kill_points', 'required_deaths'}
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Clear old requirements
        cursor.execute("DELETE FROM kvk_requirements WHERE kvk_name = ?", (kvk_name,))

        for req in requirements:
            cursor.execute('''
                INSERT INTO kvk_requirements (
                    kvk_name, min_power, max_power, required_kills, required_deaths
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                kvk_name, req['min_power'], req['max_power'],
                req['required_kills'], req['required_deaths']
            ))

        conn.commit()
        logger.info(f"Saved {len(requirements)} requirements for '{kvk_name}'.")
        return True
    except Exception as e:
        logger.error(f"Error saving requirements: {e}")
        return False
    finally:
        if conn: conn.close()


def archive_kvk_data(current_name: str, archive_name: str):
    """
    Archives KvK data by renaming it in the stats and snapshots tables.
    Uses transaction to ensure atomic operation.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Begin explicit transaction
        cursor.execute("BEGIN IMMEDIATE TRANSACTION")

        # Update kvk_stats
        cursor.execute("UPDATE kvk_stats SET kvk_name = ? WHERE kvk_name = ?", (archive_name, current_name))
        
        # Update kvk_snapshots
        cursor.execute("UPDATE kvk_snapshots SET kvk_name = ? WHERE kvk_name = ?", (archive_name, current_name))

        # Requirements are left as a template (not renamed) so they can be used again.
        # Or should we copy them for the archive?
        # User asked for "data archive". Requirements are settings.
        # Let's copy requirements to the archive name to know what they were THEN.
        
        # 1. Get current requirements
        cursor.execute("SELECT * FROM kvk_requirements WHERE kvk_name = ?", (current_name,))
        reqs = cursor.fetchall()
        
        # 2. Insert them under the new name
        for req in reqs:
            cursor.execute('''
                INSERT INTO kvk_requirements (kvk_name, min_power, max_power, required_kills, required_deaths)
                VALUES (?, ?, ?, ?, ?)
            ''', (archive_name, req[1], req[2], req[3], req[4])) # Indices depend on column order in SELECT *

        # Commit transaction
        conn.commit()
        logger.info(f"KvK data '{current_name}' successfully archived to '{archive_name}'.")
        return True
    except Exception as e:
        logger.error(f"Error archiving data: {e}")
        if conn:
            conn.rollback()
            logger.info("Transaction rolled back due to error.")
        return False
    finally:
        if conn: conn.close()


def link_account(discord_id: int, player_id: int, account_type: str = 'main'):
    """
    Links a game account to a Discord account.
    account_type: 'main', 'alt', 'farm'
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Legacy support: is_main_account column
        is_main_int = 1 if account_type == 'main' else 0

        if is_main_int:
             cursor.execute("UPDATE linked_accounts SET is_main_account = 0, account_type = 'alt' WHERE discord_id = ? AND account_type = 'main'", (discord_id,))

        cursor.execute('''
            INSERT OR REPLACE INTO linked_accounts (discord_id, player_id, is_main_account, account_type)
            VALUES (?, ?, ?, ?)
        ''', (discord_id, player_id, is_main_int, account_type))

        conn.commit()
        logger.info(f"Account {player_id} successfully linked to Discord ID {discord_id}.")
        return True
    except sqlite3.Error as e:
        logger.error(f"Error linking account: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_linked_accounts(discord_id: int):
    """
    Returns a list of all linked game accounts for a Discord ID.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT player_id, is_main_account, account_type FROM linked_accounts WHERE discord_id = ?", (discord_id,))
        rows = cursor.fetchall()

        # Handle legacy rows where account_type might be NULL if migration failed (unlikely with DEFAULT)
        # or if we just want to be safe.
        accounts = []
        for row in rows:
            acc_type = row[2]
            if not acc_type:
                acc_type = 'main' if row[1] else 'alt'
            
            accounts.append({
                'player_id': row[0],
                'is_main': bool(row[1]),
                'account_type': acc_type
            })
        return accounts
    except sqlite3.Error as e:
        logger.error(f"Error retrieving linked accounts: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_current_kvk_name():
    """
    Returns the current KvK name from the database.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT setting_value FROM kvk_settings WHERE setting_key = 'current_kvk_name'")
        result = cursor.fetchone()

        return result[0] if result else None
    except sqlite3.Error as e:
        logger.error(f"Error retrieving current KvK: {e}")
        return None
    finally:
        if conn:
            conn.close()


def set_current_kvk_name(kvk_name: str):
    """
    Sets the current KvK name in the database.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO kvk_settings (setting_key, setting_value)
            VALUES ('current_kvk_name', ?)
        ''', (kvk_name,))

        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error setting current KvK: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_player_stats(player_id: int, kvk_name: str, period_key: str):
    """
    Retrieves player statistics by ID for a specific KvK and period.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM kvk_stats
            WHERE player_id = ? AND kvk_name = ? AND period_key = ?
        ''', (player_id, kvk_name, period_key))

        return cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"Error retrieving player statistics: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_total_player_stats(player_id: int, kvk_name: str):
    """
    Retrieves total player statistics for all periods within a KvK.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
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

        return cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"Error retrieving total player statistics: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_player_stats_by_period(player_id: int, kvk_name: str, period_key: str = "all"):
    """
    Retrieves player statistics for a specific period or all periods.
    Returns data with 'total_' prefix for consistency.
    
    Args:
        player_id: Player ID
        kvk_name: KvK season name
        period_key: Period key or "all" for total stats across all periods
    
    Returns:
        Row object with stats (with total_ prefix) or None
    """
    if period_key == "all":
        return get_total_player_stats(player_id, kvk_name)
    else:
        # Get single period stats
        conn = None
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

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

            return cursor.fetchone()
        except sqlite3.Error as e:
            logger.error(f"Error retrieving player statistics: {e}")
            return None
        finally:
            if conn:
                conn.close()


def get_kingdom_stats_by_period(kvk_name: str, period_key: str = "all"):
    """
    Retrieves kingdom statistics for a specific period or all periods.
    
    Args:
        kvk_name: KvK season name
        period_key: Period key or "all" for total stats across all periods
    
    Returns:
        Dictionary with aggregated kingdom stats
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if period_key == "all":
            # Sum across all periods, but MAX power per player (power doesn't accumulate)
            # Subquery gets max power per player, then sum across all players
            cursor.execute('''
                SELECT COUNT(DISTINCT player_id) as player_count,
                       (SELECT SUM(max_power) FROM (
                           SELECT player_id, MAX(power) as max_power
                           FROM kvk_stats
                           WHERE kvk_name = ?
                           GROUP BY player_id
                       )) as kingdom_power,
                       SUM(kill_points) as kingdom_kill_points,
                       SUM(deaths) as kingdom_deaths,
                       SUM(t1_kills) as kingdom_t1_kills,
                       SUM(t2_kills) as kingdom_t2_kills,
                       SUM(t3_kills) as kingdom_t3_kills,
                       SUM(t4_kills) as kingdom_t4_kills,
                       SUM(t5_kills) as kingdom_t5_kills
                FROM kvk_stats
                WHERE kvk_name = ?
            ''', (kvk_name, kvk_name))
        else:
            # Stats for specific period
            cursor.execute('''
                SELECT COUNT(player_id) as player_count,
                       SUM(power) as kingdom_power,
                       SUM(kill_points) as kingdom_kill_points,
                       SUM(deaths) as kingdom_deaths,
                       SUM(t1_kills) as kingdom_t1_kills,
                       SUM(t2_kills) as kingdom_t2_kills,
                       SUM(t3_kills) as kingdom_t3_kills,
                       SUM(t4_kills) as kingdom_t4_kills,
                       SUM(t5_kills) as kingdom_t5_kills
                FROM kvk_stats
                WHERE kvk_name = ? AND period_key = ?
            ''', (kvk_name, period_key))
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    except sqlite3.Error as e:
        logger.error(f"Error retrieving kingdom statistics by period: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_all_linked_accounts_full():
    """
    Returns a list of all linked accounts (Discord ID -> Player ID) with Player Name.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT la.*, kp.player_name 
            FROM linked_accounts la
            LEFT JOIN kingdom_players kp ON la.player_id = kp.player_id
        ''')
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        logger.error(f"Error retrieving all linked accounts: {e}")
        return []
    finally:
        if conn:
            conn.close()


def reset_all_data():
    """
    Completely clears the database (deletes all data from tables).
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # List of tables to clear
        tables = ['kvk_stats', 'kvk_snapshots', 'kvk_requirements', 'linked_accounts', 'kvk_settings', 'admin_logs']
        
        for table in tables:
            cursor.execute(f"DELETE FROM {table}")
            
        conn.commit()
        logger.info("All data successfully deleted from the database.")
        return True
    except sqlite3.Error as e:
        logger.error(f"Error resetting data: {e}")
        return False
    finally:
        if conn:
            conn.close()

def log_admin_action(admin_id: int, admin_name: str, action: str, details: str):
    """
    Logs an admin action to the database.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO admin_logs (admin_id, admin_name, action, details)
            VALUES (?, ?, ?, ?)
        ''', (admin_id, admin_name, action, details))

        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error logging admin action: {e}")
        return False
    finally:
        if conn:
            conn.close()


def set_reward_role(role_id: int):
    """
    Sets the reward role ID in the database.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO kvk_settings (setting_key, setting_value)
            VALUES ('reward_role_id', ?)
        ''', (str(role_id),))

        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error setting reward role: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_reward_role():
    """
    Gets the reward role ID from the database.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT setting_value FROM kvk_settings WHERE setting_key = 'reward_role_id'")
        result = cursor.fetchone()

        return int(result[0]) if result else None
    except Exception as e:
        logger.error(f"Error getting reward role: {e}")
        return None
    finally:
        if conn:
            conn.close()


def unlink_account(discord_id: int, player_id: int):
    """
    Unlinks a game account from a Discord account.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM linked_accounts WHERE discord_id = ? AND player_id = ?", (discord_id, player_id))
        
        if cursor.rowcount > 0:
            conn.commit()
            logger.info(f"Account {player_id} unlinked from Discord ID {discord_id}.")
            return True
        return False
    except sqlite3.Error as e:
        logger.error(f"Error unlinking account: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_kingdom_stats(kvk_name: str):
    """
    Retrieves aggregated statistics for the entire kingdom for a specific KvK.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # We need to sum up the MAX power (latest) for each player? 
        # Or sum up the stats from kvk_stats table?
        # kvk_stats has one row per player per period.
        # But get_total_player_stats aggregates by taking MAX power and SUM kills.
        # So we should do the same here: first aggregate per player, then sum up.
        
        # Subquery to get total stats per player
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

        return cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"Error retrieving kingdom stats: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_all_periods(kvk_name: str):
    """
    Returns all unique periods (snapshots) for a specific KvK.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DISTINCT period_key, snapshot_type FROM kvk_snapshots 
            WHERE kvk_name = ?
            ORDER BY period_key
        ''', (kvk_name,))
        
        rows = cursor.fetchall()
        return [{'period_key': row[0], 'snapshot_type': row[1]} for row in rows]
    except sqlite3.Error as e:
        logger.error(f"Error retrieving periods: {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_all_kvk_stats(kvk_name: str):
    """
    Retrieves stats for all players in a specific KvK.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Aggregate stats per player
        cursor.execute('''
            SELECT 
                player_id,
                MAX(player_name) as player_name,
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
        ''', (kvk_name,))
        
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logger.error(f"Error retrieving all kvk stats: {e}")
        return []
    finally:
        if conn:
            conn.close()



def get_player_start_snapshot(player_id: int, kvk_name: str):
    """
    Retrieves the 'start' snapshot for a player in a specific KvK.
    Used to calculate earned stats (Current - Start).
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get the first (earliest) period's start snapshot
        cursor.execute('''
            SELECT * FROM kvk_snapshots
            WHERE player_id = ? AND kvk_name = ? AND snapshot_type = 'start'
            ORDER BY period_key ASC
            LIMIT 1
        ''', (player_id, kvk_name))
        
        return cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"Error retrieving player start snapshot: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_total_stats_for_players(player_ids: list, kvk_name: str):
    """
    Retrieves total player statistics for multiple players in a single query.
    Optimized batch version of get_total_player_stats.
    
    Args:
        player_ids: List of player IDs
        kvk_name: KvK season name
    
    Returns:
        Dictionary mapping player_id to stats row
    """
    if not player_ids:
        return {}
    
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Create placeholders for IN clause
        placeholders = ','.join('?' * len(player_ids))
        
        cursor.execute(f'''
            SELECT player_id,
                   MAX(power) as total_power,
                   SUM(kill_points) as total_kill_points,
                   SUM(deaths) as total_deaths,
                   SUM(t1_kills) as total_t1_kills,
                   SUM(t2_kills) as total_t2_kills,
                   SUM(t3_kills) as total_t3_kills,
                   SUM(t4_kills) as total_t4_kills,
                   SUM(t5_kills) as total_t5_kills,
                   MAX(player_name) as player_name
            FROM kvk_stats
            WHERE player_id IN ({placeholders}) AND kvk_name = ?
            GROUP BY player_id
        ''', (*player_ids, kvk_name))
        
        results = cursor.fetchall()
        return {row['player_id']: dict(row) for row in results}
    except sqlite3.Error as e:
        logger.error(f"Error retrieving batch player statistics: {e}")
        return {}
    finally:
        if conn:
            conn.close()


def get_kingdom_start_snapshot(kvk_name: str):
    """
    Gets aggregated kingdom-wide start snapshot (first period's start).
    
    Args:
        kvk_name: KvK season name
    
    Returns:
        Dictionary with aggregated start snapshot data
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Find the earliest period
        cursor.execute('''
            SELECT period_key FROM kvk_snapshots
            WHERE kvk_name = ? AND snapshot_type = 'start'
            ORDER BY period_key ASC
            LIMIT 1
        ''', (kvk_name,))
        
        first_period = cursor.fetchone()
        if not first_period:
            return None
        
        # Get aggregated start snapshot for that period
        cursor.execute('''
            SELECT SUM(power) as kingdom_power,
                   SUM(kill_points) as kingdom_kill_points,
                   SUM(deaths) as kingdom_deaths
            FROM kvk_snapshots
            WHERE kvk_name = ? AND period_key = ? AND snapshot_type = 'start'
        ''', (kvk_name, first_period['period_key']))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    except sqlite3.Error as e:
        logger.error(f"Error retrieving kingdom start snapshot: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_snapshot_player_data(kvk_name: str, period_key: str, snapshot_type: str, player_id: int):
    """
    Retrieves snapshot data for a specific player.
    
    Args:
        kvk_name: KvK season name
        period_key: Period key
        snapshot_type: 'start' or 'end'
        player_id: Player ID
    
    Returns:
        Row object with snapshot data or None
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM kvk_snapshots
            WHERE kvk_name = ? AND period_key = ? AND snapshot_type = ? AND player_id = ?
        ''', (kvk_name, period_key, snapshot_type, player_id))
        
        return cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"Error retrieving player snapshot: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_player_rank(player_id: int, kvk_name: str):
    """
    Gets player's DKP rank within the kingdom.
    
    Args:
        player_id: Player ID
        kvk_name: KvK season name
    
    Returns:
        Rank number (1-based) or None
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Calculate DKP for all players and rank them
        cursor.execute('''
            SELECT player_id,
                   (SUM(t4_kills) * 4 + SUM(t5_kills) * 10 + SUM(deaths) * 15) as dkp
            FROM kvk_stats
            WHERE kvk_name = ?
            GROUP BY player_id
            ORDER BY dkp DESC
        ''', (kvk_name,))
        
        rows = cursor.fetchall()
        for rank, row in enumerate(rows, 1):
            if row[0] == player_id:
                return rank
        return None
    except sqlite3.Error as e:
        logger.error(f"Error retrieving player rank: {e}")
        return None
    finally:
        if conn:
            conn.close()

