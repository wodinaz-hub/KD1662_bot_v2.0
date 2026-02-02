
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
        # Check kvk_stats count
        print("\n--- kvk_stats count ---")
        cursor.execute("SELECT count(DISTINCT player_id) FROM kvk_stats")
        print(cursor.fetchone()[0])
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_db()
