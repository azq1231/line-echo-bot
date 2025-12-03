import database as db
from app import create_app

app = create_app(start_scheduler=False)

with app.app_context():
    conn = db.get_db()
    cursor = conn.cursor()
    
    print("Checking for users with empty names...")
    cursor.execute("SELECT user_id, name, created_at FROM users WHERE name IS NULL OR name = ''")
    empty_users = cursor.fetchall()
    
    if empty_users:
        print(f"Found {len(empty_users)} users with empty names:")
        for u in empty_users:
            print(dict(u))
    else:
        print("No users with empty names found.")

    print("\nChecking for users with whitespace-only names...")
    cursor.execute("SELECT user_id, name FROM users")
    all_users = cursor.fetchall()
    whitespace_users = [dict(u) for u in all_users if not u['name'] or not u['name'].strip()]
    
    if whitespace_users:
        print(f"Found {len(whitespace_users)} users with whitespace-only names:")
        for u in whitespace_users:
            print(u)
    else:
        print("No users with whitespace-only names found.")
