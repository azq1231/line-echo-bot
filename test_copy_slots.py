import database as db
import sqlite3

def test_copy():
    print("Testing copy_slots...")
    conn = db.get_db()
    cursor = conn.cursor()
    
    # 1. Setup: Clear slots and add some source slots
    cursor.execute("DELETE FROM available_slots")
    
    # Add source slots for Tuesday (weekday=1)
    cursor.execute("INSERT INTO available_slots (weekday, start_time, end_time, active, note, type) VALUES (1, '09:00', '10:00', 1, 'Test', 'consultation')")
    cursor.execute("INSERT INTO available_slots (weekday, start_time, end_time, active, note, type) VALUES (1, '10:00', '11:00', 1, 'Test', 'massage')")
    conn.commit()
    conn.close()
    
    # 2. Test Copy
    source_weekday = 1
    target_weekdays = ['1', '2'] # Include source weekday (1)
    types = ['consultation', 'massage']
    
    try:
        inserted, deleted = db.copy_slots(source_weekday, target_weekdays, types)
        print(f"Success: Inserted {inserted}, Deleted {deleted}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_copy()
