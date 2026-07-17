import sqlite3
import argparse
import datetime
import os

# Resolve DB_PATH relative to this script's directory to ensure it always finds the root sessions.db
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "sessions.db"))

def list_sessions():
    if not os.path.exists(DB_PATH):
        print(f"Database file '{DB_PATH}' not found yet. Play a game first to generate it.")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, input_mode, start_time, completed, final_score FROM sessions ORDER BY id DESC")
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        print("Sessions table does not exist yet. Play a game first.")
        conn.close()
        return
    conn.close()
    
    if not rows:
        print("No sessions logged in database.")
        return
        
    print(f"{'ID':<6} | {'Mode':<10} | {'Start Time':<20} | {'Completed':<10} | {'Score':<8}")
    print("-" * 65)
    for r in rows:
        dt = datetime.datetime.fromtimestamp(r[2]).strftime('%Y-%m-%d %H:%M:%S') if r[2] else 'N/A'
        print(f"{r[0]:<6} | {r[1]:<10} | {dt:<20} | {str(bool(r[3])):<10} | {r[4]:<8}")

def delete_session(session_id):
    if not os.path.exists(DB_PATH):
        print(f"Database file '{DB_PATH}' not found.")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM events WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        deleted = cursor.rowcount
    except sqlite3.OperationalError as e:
        print(f"Database error: {e}")
        conn.close()
        return
    conn.close()
    
    if deleted == 0:
        print(f"Error: Session #{session_id} not found in database.")
    else:
        print(f"Success: Session #{session_id} and associated event logs deleted successfully.")

def clear_all():
    if not os.path.exists(DB_PATH):
        print(f"Database file '{DB_PATH}' not found.")
        return
        
    confirm = input("Are you sure you want to delete ALL sessions and event logs from SQLite? (y/N): ")
    if confirm.lower() != 'y':
        print("Aborted.")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM events")
        cursor.execute("DELETE FROM sessions")
        conn.commit()
        print("Success: SQLite database cleared successfully.")
    except sqlite3.OperationalError as e:
        print(f"Database error: {e}")
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AirDash SQLite Database Administrator")
    parser.add_argument("--list", action="store_true", help="List all sessions in SQLite")
    parser.add_argument("--delete", type=int, metavar="ID", help="Delete a specific session by ID")
    parser.add_argument("--clear", action="store_true", help="Clear all session history records")
    
    args = parser.parse_args()
    
    if args.list:
        list_sessions()
    elif args.delete is not None:
        delete_session(args.delete)
    elif args.clear:
        clear_all()
    else:
        parser.print_help()
