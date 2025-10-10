"""
迁移脚本：将 JSON 数据迁移到 SQLite 数据库
"""
import json
import os
from database import init_database, add_user, add_appointment

def migrate_users():
    """迁移用户数据"""
    try:
        with open('users.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            users = data.get('allowed_users', [])
            
        for user in users:
            user_id = user.get('user_id')
            name = user.get('name', '未知')
            add_user(user_id, name)
            print(f"✅ 已迁移用户: {name} ({user_id})")
        
        print(f"✅ 用户迁移完成，共 {len(users)} 个用户")
    except FileNotFoundError:
        print("⚠️ users.json 不存在，跳过用户迁移")
    except Exception as e:
        print(f"❌ 用户迁移错误: {e}")

def migrate_appointments():
    """迁移预约数据"""
    try:
        with open('appointments.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            appointments = data.get('appointments', [])
            
        for apt in appointments:
            date = apt.get('date')
            time = apt.get('time')
            user_id = apt.get('user_id', '')
            user_name = apt.get('user_name', '未知')
            
            if user_id and user_name:
                add_appointment(user_id, user_name, date, time)
                print(f"✅ 已迁移预约: {date} {time} - {user_name}")
        
        print(f"✅ 预约迁移完成，共 {len(appointments)} 个预约")
    except FileNotFoundError:
        print("⚠️ appointments.json 不存在，跳过预约迁移")
    except Exception as e:
        print(f"❌ 预约迁移错误: {e}")

if __name__ == "__main__":
    print("开始数据迁移...")
    print("-" * 50)
    
    # 初始化数据库
    init_database()
    
    # 迁移数据
    migrate_users()
    print()
    migrate_appointments()
    
    print("-" * 50)
    print("✅ 数据迁移完成！")
