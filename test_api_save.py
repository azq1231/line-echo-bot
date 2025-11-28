
from app import create_app
import database as db
import json

def test_save_appointment_api():
    app = create_app(start_scheduler=False)
    client = app.test_client()

    # 1. Setup: Ensure a user exists
    user_id = "test_user_api"
    db.add_user(user_id, "Test API User")
    
    # 2. Login (Mock session)
    with client.session_transaction() as sess:
        sess['user'] = {'user_id': user_id, 'is_admin': True}
        # Ensure user is admin in DB
        db.update_user_admin_status(user_id, True)

    # 3. Test Save Appointment (Normal)
    data = {
        "date": "2025-12-02",
        "time": "10:00",
        "user_id": user_id,
        "user_name": "Test API User",
        "type": "massage"
    }
    print(f"Sending request: {data}")
    response = client.post('/api/admin/save_appointment', json=data)
    print(f"Response status: {response.status_code}")
    print(f"Response data: {response.get_json()}")
    
    if response.status_code != 200:
        print("FAILED: Normal save")
    else:
        print("SUCCESS: Normal save")

    # 4. Test Save Appointment (Same as above simulation - overwrite)
    # This simulates clicking "Same as above" on the NEXT slot
    data2 = {
        "date": "2025-12-02",
        "time": "10:30",
        "user_id": user_id,
        "user_name": "Test API User",
        "type": "massage",
        "waiting_list_item_id": None
    }
    print(f"Sending request 2: {data2}")
    response = client.post('/api/admin/save_appointment', json=data2)
    print(f"Response status: {response.status_code}")
    print(f"Response data: {response.get_json()}")

    if response.status_code != 200:
        print("FAILED: Overwrite save")
    else:
        print("SUCCESS: Overwrite save")

    # 5. Test with Manual User
    manual_id = "manual_api_test"
    db.add_manual_user(manual_id, "Manual API User")
    
    data3 = {
        "date": "2025-12-02",
        "time": "11:00",
        "user_id": manual_id,
        "user_name": "Manual API User",
        "type": "massage"
    }
    print(f"Sending request 3 (Manual): {data3}")
    response = client.post('/api/admin/save_appointment', json=data3)
    print(f"Response status: {response.status_code}")
    print(f"Response data: {response.get_json()}")

    if response.status_code != 200:
        print("FAILED: Manual user save")
    else:
        print("SUCCESS: Manual user save")

    # Clean up
    db.cancel_appointment("2025-12-02", "10:00", "massage")
    db.cancel_appointment("2025-12-02", "10:30", "massage")
    db.cancel_appointment("2025-12-02", "11:00", "massage")
    db.delete_user(user_id)
    db.delete_user(manual_id)

if __name__ == "__main__":
    test_save_appointment_api()
