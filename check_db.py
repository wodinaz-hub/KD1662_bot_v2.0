
import sqlite3
import os

DB_PATH = 'data/kvk_data.db'

def check_db():
    if not os.path.exists(DB_PATH):
        print("Database not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check fort_periods schema
        print("--- fort_periods columns ---")
        cursor.execute("PRAGMA table_info(fort_periods)")
        for col in cursor.fetchall():
            print(col)
            
        # Check kingdom_players count
        print("\n--- kingdom_players count ---")
        cursor.execute("SELECT count(*) FROM kingdom_players")
        print(cursor.fetchone()[0])
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_db()
