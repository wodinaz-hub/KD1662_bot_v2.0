import sqlite3
import os
import logging
from contextlib import closing

# Logging configuration
logger = logging.getLogger('db_manager.base')

# Define database path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# Allow overriding data directory via environment variable (useful for Railway Volumes)
DATA_DIR = os.getenv('DATA_PATH', os.path.join(PROJECT_ROOT, 'data'))
DATABASE_PATH = os.path.join(DATA_DIR, 'kvk_data.db')

def get_connection():
    """Returns a new sqlite3 connection."""
    return sqlite3.connect(DATABASE_PATH)

def backup_database():
    """
    Creates a backup of the database file.
    Returns the path to the backup file or None if failed.
    """
    import shutil
    from datetime import datetime
    
    try:
        if not os.path.exists(DATABASE_PATH):
            logger.error("Database file not found for backup.")
            return None
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"kvk_data_backup_{timestamp}.db"
        backup_path = os.path.join(DATA_DIR, backup_filename)
        
        # Create a copy
        shutil.copy2(DATABASE_PATH, backup_path)
        logger.info(f"Database backup created at {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Error creating database backup: {e}")
        return None

def restore_database(uploaded_path: str):
    """
    Restores the database from an uploaded backup file.
    1. Creates a safety backup of the current DB
    2. Replaces the active DB with the uploaded file
    
    Returns:
        (success: bool, message: str, safety_backup_path: str or None)
    """
    import shutil
    
    try:
        # Validate that uploaded file is a valid SQLite database
        try:
            test_conn = sqlite3.connect(uploaded_path)
            test_conn.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
            test_conn.close()
        except sqlite3.DatabaseError:
            return False, "The uploaded file is not a valid SQLite database.", None
        
        # Create a safety backup before replacing
        safety_backup_path = backup_database()
        if not safety_backup_path:
            return False, "Failed to create safety backup before restore. Aborting.", None
        
        # Replace the database file
        shutil.copy2(uploaded_path, DATABASE_PATH)
        
        logger.info(f"Database restored from {uploaded_path}. Safety backup at {safety_backup_path}")
        return True, "Database restored successfully!", safety_backup_path
        
    except Exception as e:
        logger.error(f"Error restoring database: {e}")
        return False, f"Error during restore: {e}", None

def create_tables():
    """
    Creates database tables if they do not exist.
    """
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    try:
        with closing(get_connection()) as conn:
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
            
            # Migration: Rename column required_kill_points -> required_kills if exists
            try:
                cursor.execute("PRAGMA table_info(kvk_requirements)")
                columns = [info[1] for info in cursor.fetchall()]
                if 'required_kill_points' in columns and 'required_kills' not in columns:
                    cursor.execute("ALTER TABLE kvk_requirements ADD COLUMN required_kills INTEGER DEFAULT 0")
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
            
            # Migration: Add account_type if missing
            try:
                cursor.execute("ALTER TABLE linked_accounts ADD COLUMN account_type TEXT DEFAULT 'main'")
            except sqlite3.OperationalError:
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

            # Table for base kingdom player list
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS kingdom_players (
                    player_id INTEGER PRIMARY KEY,
                    player_name TEXT NOT NULL,
                    power INTEGER,
                    kvk_name TEXT NOT NULL
                )
            ''')

            # Table for KvK Seasons
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS kvk_seasons (
                    value TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    description TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    is_active INTEGER DEFAULT 0,
                    is_archived INTEGER DEFAULT 0
                )
            ''')

            # Table for fort statistics
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fort_stats (
                    player_id INTEGER,
                    player_name TEXT NOT NULL,
                    forts_joined INTEGER DEFAULT 0,
                    forts_launched INTEGER DEFAULT 0,
                    total_forts INTEGER DEFAULT 0,
                    penalties INTEGER DEFAULT 0,
                    kvk_name TEXT NOT NULL,
                    period_key TEXT NOT NULL,
                    PRIMARY KEY (player_id, kvk_name, period_key)
                )
            ''')

            # Table for fort periods
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fort_periods (
                    kvk_name TEXT NOT NULL,
                    period_key TEXT NOT NULL,
                    period_label TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (kvk_name, period_key)
                )
            ''')

            # Table for player types (for unlinked accounts or manual overrides)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS player_types (
                    player_id INTEGER PRIMARY KEY,
                    account_type TEXT NOT NULL DEFAULT 'main'
                )
            ''')

            # Table for global settings
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS global_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT NOT NULL
                )
            ''')

            # Create indexes
            logger.info("Creating database indexes...")
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_kvk_stats_kvk_period ON kvk_stats(kvk_name, period_key)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_kvk_stats_player ON kvk_stats(kvk_name, player_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_kvk_snapshots_lookup ON kvk_snapshots(kvk_name, period_key, snapshot_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_kvk_snapshots_player ON kvk_snapshots(player_id, kvk_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_linked_discord ON linked_accounts(discord_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_linked_player ON linked_accounts(player_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_requirements_kvk ON kvk_requirements(kvk_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_fort_stats_kvk ON fort_stats(kvk_name, period_key)')
            
            conn.commit()
            logger.info("Database tables and indexes verified.")
    except sqlite3.Error as e:
        logger.error(f"Error creating tables: {e}")
