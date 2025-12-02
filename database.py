import sqlite3
from typing import List, Dict, Optional
from pypinyin import pinyin, Style
from datetime import datetime
import pytz

DB_FILE = 'appointments.db'

def _name_to_zhuyin(name: str) -> str:
    """将中文姓名转换为注音首字母字符串，例如 '郭欽方' -> 'ㄍㄑㄈ'"""
    if not name:
        return ""
    try:
        # 使用 pypinyin 生成注音，Style.BOPOMOFO 返回注音列表
        zhuyin_list = pinyin(name, style=Style.BOPOMOFO)
        # 提取每个字的第一个注音符号并连接
        initials = "".join([item[0][0] for item in zhuyin_list if item and item[0]])
        return initials
    except Exception as e:
        print(f"注音转换失败 for name '{name}': {e}")
        return ""

def get_db():
    """获取数据库连接"""
    # 增加 timeout 到 30 秒，以減少 database is locked 錯誤
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """初始化数据库结构，并安全地添加新字段"""
    conn = get_db()
    # 啟用 WAL 模式以提高並發性能
    conn.execute('PRAGMA journal_mode=WAL')
    cursor = conn.cursor()
    
    # 用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT, -- 市話
            phone2 TEXT, -- 手機
            zhuyin TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 安全地為 users 表添加 picture_url 字段
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'picture_url' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN picture_url TEXT")
    # 安全地為 users 表添加 manual_update 字段，用於標記手動更新
    if 'manual_update' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN manual_update BOOLEAN DEFAULT FALSE")
    # 安全地為 users 表添加 address 字段
    if 'address' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN address TEXT")
    # 安全地為 users 表添加 is_admin 字段
    if 'is_admin' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE")
    # 安全地為 users 表添加 reminder_schedule 字段
    if 'reminder_schedule' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN reminder_schedule TEXT DEFAULT 'weekly'")


    # 预约表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            target_name TEXT NOT NULL,
            message_type TEXT NOT NULL,
            send_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL,
            error_message TEXT,
            message_excerpt TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # 预约表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            user_name TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            status TEXT DEFAULT 'confirmed',
            booking_group_id TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')

    # 安全地為 appointments 表添加新欄位，以支援回覆追蹤功能
    cursor.execute("PRAGMA table_info(appointments)")
    appointment_columns = [column[1] for column in cursor.fetchall()]
    if 'reply_status' not in appointment_columns:
        cursor.execute("ALTER TABLE appointments ADD COLUMN reply_status TEXT DEFAULT '未回覆'")
    if 'last_reply' not in appointment_columns:
        cursor.execute("ALTER TABLE appointments ADD COLUMN last_reply TEXT")
    if 'reply_time' not in appointment_columns:
        cursor.execute("ALTER TABLE appointments ADD COLUMN reply_time DATETIME")
    if 'confirm_time' not in appointment_columns:
        cursor.execute("ALTER TABLE appointments ADD COLUMN confirm_time DATETIME")
    if 'type' not in appointment_columns:
        cursor.execute("ALTER TABLE appointments ADD COLUMN type TEXT DEFAULT 'consultation'")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS closed_days (
            date TEXT PRIMARY KEY,
            reason TEXT
        )
    ''')

    # 可用時段表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS available_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weekday INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            active BOOLEAN DEFAULT TRUE,
            note TEXT,
            type TEXT DEFAULT 'consultation',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(weekday, start_time, type)
        )
    ''')
    
    # 安全地為 available_slots 表添加 type 字段
    cursor.execute("PRAGMA table_info(available_slots)")
    available_slots_columns = [column[1] for column in cursor.fetchall()]
    if 'type' not in available_slots_columns:
        cursor.execute("ALTER TABLE available_slots ADD COLUMN type TEXT DEFAULT 'consultation'")

    # 排程訊息表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            user_name TEXT NOT NULL,
            send_time TIMESTAMP NOT NULL,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'pending', -- pending, sent, failed
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    # 安全地為 schedules 表添加欄位，處理舊資料庫結構
    cursor.execute("PRAGMA table_info(schedules)")
    schedule_columns = [column[1] for column in cursor.fetchall()]
    if 'id' not in schedule_columns:
        # 這是個比較複雜的操作，因為舊的 PRIMARY KEY 可能不存在
        print("警告：偵測到舊的 'schedules' 表結構，正在嘗試升級。建議備份 appointments.db 檔案。")
        # 重新命名舊表
        cursor.execute("ALTER TABLE schedules RENAME TO schedules_old")
        # 建立新表
        cursor.execute('''
            CREATE TABLE schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                user_name TEXT NOT NULL,
                send_time TIMESTAMP NOT NULL,
                message TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        # 智慧地將舊資料複製到新表
        # 1. 獲取舊表的實際欄位
        cursor.execute("PRAGMA table_info(schedules_old)")
        old_columns = [column[1] for column in cursor.fetchall()]
        
        # 2. 建立要複製的欄位列表 (排除 id)
        columns_to_copy = [col for col in old_columns if col != 'id']
        columns_str = ", ".join(columns_to_copy)

        # 3. 執行複製操作，只選擇舊表中存在的欄位
        #    新表中多出來的欄位 (如 updated_at) 會自動使用預設值
        print(f"正在從舊表複製欄位: {columns_str}")
        cursor.execute('''
            INSERT INTO schedules ({columns_str})
            SELECT {columns_str} FROM schedules_old
        ''')
        # 刪除舊表
        cursor.execute("DROP TABLE schedules_old")
        print("已成功將 'schedules' 表升級到新結構。")

    # 系统配置表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS configs (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 備取名單表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS waiting_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            user_id TEXT NOT NULL,
            user_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # 新增紀錄發送訊息函數
def log_message_send(user_id: str, target_name: str, message_type: str, status: str, error_message: Optional[str] = None, message_excerpt: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO message_log 
        (user_id, target_name, message_type, status, error_message, message_excerpt)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, target_name, message_type, status, error_message, message_excerpt))
    
    conn.commit()
    conn.close()

def get_message_stats(month: Optional[str] = None, user_id: Optional[str] = None, message_type: Optional[str] = None):
    """獲取訊息統計資料
    
    Args:
        month: 統計月份，格式：YYYY-MM
        user_id: 特定使用者
        message_type: 訊息類型（單日/整週）
    
    Returns:
        Dict: 包含統計資料的字典
    """
    conn = get_db()
    cursor = conn.cursor()
    
    conditions = []
    params = []
    
    # 建立 SQL WHERE 條件
    if month:
        conditions.append("strftime('%Y-%m', send_time) = ?")
        params.append(month)
    if user_id:
        conditions.append("user_id = ?")
        params.append(user_id)
    if message_type:
        conditions.append("message_type = ?")
        params.append(message_type)
        
    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    
    # 獲取基本統計資料
    stats = {
        "total_messages": 0,
        "success_count": 0,
        "failed_count": 0,
        "success_rate": 0,
        "message_types": {},
        "daily_stats": [],
        "errors": []
    }
    
    # 統計總數和成功/失敗數
    cursor.execute(f'''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
        FROM message_log
        {where_clause}
    ''', params)
    row = cursor.fetchone()
    if row and row[0] > 0:
        stats["total_messages"] = row[0]
        stats["success_count"] = row[1]
        stats["failed_count"] = row[2]
        stats["success_rate"] = (row[1] / row[0] * 100)
    else:
        stats["success_rate"] = 'N/A'
    
    # 按訊息類型統計
    cursor.execute(f'''
        SELECT 
            message_type,
            COUNT(*) as count,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count
        FROM message_log
        {where_clause}
        GROUP BY message_type
    ''', params)
    for row in cursor.fetchall():
        stats["message_types"][row[0]] = {
            "total": row[1],
            "success": row[2],
            "success_rate": (row[2] / row[1] * 100) if row[1] > 0 else 'N/A'
        }
    
    # 按日期統計
    cursor.execute(f'''
        SELECT 
            date(send_time) as send_date,
            COUNT(*) as count,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count
        FROM message_log
        {where_clause}
        GROUP BY date(send_time)
        ORDER BY send_date
    ''', params)
    for row in cursor.fetchall():
        stats["daily_stats"].append({
            "date": row[0],
            "total": row[1],
            "success": row[2],
            "success_rate": (row[2] / row[1] * 100) if row[1] > 0 else 'N/A'
        })
    
    # 獲取最近的錯誤
    cursor.execute(f'''
        SELECT 
            send_time,
            target_name,
            message_type,
            error_message,
            message_excerpt
        FROM message_log
        {where_clause}
        AND status = 'failed'
        ORDER BY send_time DESC
        LIMIT 10
    ''', params)
    for row in cursor.fetchall():
        stats["errors"].append({
            "time": row[0],
            "target_name": row[1],
            "message_type": row[2],
            "error": row[3],
            "message": row[4]
        })
    
    conn.close()
    return stats

def get_recent_message_logs(limit: int = 20):
    """獲取最近的發送記錄"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            send_time,
            user_id,
            target_name,
            message_type,
            status,
            message_excerpt,
            error_message
        FROM message_log
        ORDER BY send_time DESC
        LIMIT ?
    """, (limit,))
    
    logs = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in logs]

# ==================== 用户管理 ====================

def get_all_users() -> List[Dict]:
    """获取所有用户"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users

# ... (rest of the file remains the same)

def get_user_by_id(user_id: str) -> Optional[Dict]:
    """通过 user_id 获取用户"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def add_user(user_id: str, name: str, picture_url: Optional[str] = None, phone: Optional[str] = None, phone2: Optional[str] = None, address: Optional[str] = None) -> None:
    """新增或更新用户，如果用户已存在，则更新姓名"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 检查用户是否存在
    cursor.execute('SELECT name, picture_url, manual_update FROM users WHERE user_id = ?', (user_id,))
    existing_user = cursor.fetchone()
    
    zhuyin = _name_to_zhuyin(name)

    if existing_user:
        # 關鍵商業邏輯：如果用戶名稱是手動更新過的 (manual_update=True)，
        # 則只更新頭像，不覆蓋手動設定的名稱，以保護管理員的修改。
        if existing_user['manual_update']:
            if existing_user['picture_url'] != picture_url:
                cursor.execute('''
                    UPDATE users SET picture_url = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?
                ''', (picture_url, user_id))
        # 否則，正常更新姓名和頭像
        elif existing_user['name'] != name or existing_user['picture_url'] != picture_url:
            cursor.execute('''
                UPDATE users 
                SET name = ?, zhuyin = ?, picture_url = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE user_id = ?
            ''', (name, zhuyin, picture_url, user_id))
            print(f"Updated user {user_id}'s info (name: {name}, picture_url: {picture_url})")

    else:
        # 新增用户
        cursor.execute('''
            INSERT INTO users (user_id, name, picture_url, phone, phone2, zhuyin, address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, name, picture_url, phone, phone2, zhuyin, address))
        print(f"Added new user: {name} ({user_id})")
        
    conn.commit()
    conn.close()

def update_user_name(user_id: str, new_name: str) -> bool:
    """更新用戶名和注音，並同步更新所有相關的預約記錄。"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        # 開始交易
        conn.execute('BEGIN')

        # 1. 更新 users 表
        zhuyin = _name_to_zhuyin(new_name)
        cursor.execute('''
            UPDATE users 
            SET name = ?, zhuyin = ?, manual_update = TRUE, updated_at = CURRENT_TIMESTAMP 
            WHERE user_id = ?
        ''', (new_name, zhuyin, user_id))
        
        updated = cursor.rowcount > 0
        if not updated:
            raise Exception("User not found or name is the same.")

        # 2. 同步更新 appointments 表中的 user_name
        cursor.execute('''
            UPDATE appointments SET user_name = ? WHERE user_id = ?
        ''', (new_name, user_id))

        # 提交交易
        conn.commit()
        return True
    except Exception as e:
        conn.rollback() # 如果任何一步出錯，就回滾所有操作
        print(f"更新用戶姓名時發生錯誤: {e}")
        return False
    finally:
        conn.close()

def delete_user(user_id: str) -> bool:
    """删除用户"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def add_manual_user(user_id: str, name: str) -> Optional[Dict]:
    """專門用於新增手動建立的臨時用戶"""
    conn = get_db()
    cursor = conn.cursor()
    zhuyin = _name_to_zhuyin(name)
    try:
        cursor.execute("""
            INSERT INTO users (user_id, name, zhuyin, manual_update, is_admin)
            VALUES (?, ?, ?, TRUE, FALSE)
        """, (user_id, name, zhuyin))
        conn.commit()
        print(f"Added new manual user: {name} ({user_id})")
        # 查詢並返回剛剛新增的使用者
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        new_user = cursor.fetchone()
        return dict(new_user) if new_user else None
    except sqlite3.IntegrityError:
        print(f"Error: Manual user with ID {user_id} already exists.")
        return None
    finally:
        conn.close()

def merge_users(source_user_id: str, target_user_id: str) -> bool:
    """將 source_user 的資料合併到 target_user，然後刪除 source_user"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        # 0. 安全性檢查
        source_user = get_user_by_id(source_user_id)
        target_user = get_user_by_id(target_user_id)
        if not source_user or not target_user:
            print("Error: Source or target user not found.")
            return False
        if not source_user_id.startswith('manual_'):
            print("Error: Source user is not a manual user.")
            return False
        if not target_user_id.startswith('U'):
            print("Error: Target user is not a real LINE user.")
            return False

        target_user_name = target_user['name']

        # 1. (新增) 合併用戶欄位資料
        # 如果 target_user 的欄位是空的，而 source_user 有資料，就複製過去
        fields_to_merge = ['phone', 'phone2', 'address']
        updates = {}
        for field in fields_to_merge:
            if not target_user.get(field) and source_user.get(field):
                updates[field] = source_user[field]
        
        if updates:
            set_clause = ", ".join([f"{field} = ?" for field in updates.keys()])
            params = list(updates.values())
            params.append(target_user_id)
            cursor.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", tuple(params))
            print(f"Merged user fields {list(updates.keys())} from {source_user_id} to {target_user_id}")


        # 1. 更新 appointments 表
        cursor.execute("""
            UPDATE appointments SET user_id = ?, user_name = ? WHERE user_id = ?
        """, (target_user_id, target_user_name, source_user_id))
        print(f"Updated {cursor.rowcount} appointments from {source_user_id} to {target_user_id}")

        # 2. 更新 message_log 表
        cursor.execute("""
            UPDATE message_log SET user_id = ?, target_name = ? WHERE user_id = ?
        """, (target_user_id, target_user_name, source_user_id))
        print(f"Updated {cursor.rowcount} message logs from {source_user_id} to {target_user_id}")

        # 3. 更新 schedules 表
        cursor.execute("""
            UPDATE schedules SET user_id = ?, user_name = ? WHERE user_id = ?
        """, (target_user_id, target_user_name, source_user_id))
        print(f"Updated {cursor.rowcount} schedules from {source_user_id} to {target_user_id}")

        # 4. 刪除 source_user
        cursor.execute("DELETE FROM users WHERE user_id = ?", (source_user_id,))
        print(f"Deleted source user {source_user_id}")

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"An error occurred during user merge: {e}")
        return False
    finally:
        conn.close()

def update_user_admin_status(user_id: str, is_admin: bool) -> bool:
    """更新指定用戶的管理員狀態"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET is_admin = ? WHERE user_id = ?', (is_admin, user_id))
        updated = cursor.rowcount > 0
        conn.commit()
        return updated
    except Exception as e:
        print(f"更新管理員狀態時發生錯誤: {e}")
        return False
    finally:
        conn.close()

def update_user_reminder_schedule(user_id: str, schedule_type: str) -> bool:
    """更新指定用戶的提醒排程"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE users SET reminder_schedule = ? WHERE user_id = ?', (schedule_type, user_id))
        updated = cursor.rowcount > 0
        conn.commit()
        return updated
    except Exception as e:
        print(f"更新用戶提醒排程時發生錯誤: {e}")
        return False
    finally:
        conn.close()

def add_schedule(user_id: str, user_name: str, send_time: datetime, message: str) -> bool:
    """新增一個排程訊息"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        # 明確將 datetime 物件轉為 ISO 格式字串再儲存，確保時區資訊被保留
        # 修正：直接傳遞 UTC datetime 物件，讓 DB-API 自動處理轉換
        cursor.execute('''
            INSERT INTO schedules (user_id, user_name, send_time, message)
            VALUES (?, ?, ?, ?)
        ''', (user_id, user_name, send_time, message))
        conn.commit()
        return True
    except Exception as e:
        print(f"新增排程失敗: {e}")
        return False
    finally:
        conn.close()

def get_all_schedules() -> List[Dict]:
    """獲取所有排程訊息"""
    conn = get_db()
    cursor = conn.cursor()
    # 明確指定所有欄位，並使用 'AS' 確保主鍵永遠被命名為 'id'
    # 這可以避免任何潛在的欄位名稱衝突或不明確性
    cursor.execute('''
        SELECT id, user_id, user_name, send_time, message, status, created_at, updated_at 
        FROM schedules 
        ORDER BY send_time DESC
    ''')
    schedules = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return schedules

def delete_schedule(schedule_id: int) -> bool:
    """刪除一個排程訊息"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM schedules WHERE id = ?', [schedule_id])
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_pending_schedules_to_send(now_utc: datetime) -> List[Dict]:
    """獲取所有待發送且時間已到的排程"""
    conn = get_db()
    cursor = conn.cursor()
    # 使用由應用程式傳入的 UTC 時間進行比較，以確保時區一致性
    cursor.execute("SELECT * FROM schedules WHERE status = 'pending' AND send_time <= ?", (now_utc,))
    schedules = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return schedules

def update_schedule_send_time(schedule_id: int, new_send_time: datetime) -> bool:
    """更新指定排程的發送時間，僅限於 'pending' 狀態的排程"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        # 修正：直接傳遞 UTC datetime 物件
        cursor.execute(
            'UPDATE schedules SET send_time = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = ?',
            (new_send_time, schedule_id, 'pending')
        )
        updated = cursor.rowcount > 0
        conn.commit()
        return updated
    except Exception as e:
        print(f"更新排程時間失敗: {e}")
        return False
    finally:
        conn.close()

# ==================== 预约管理 ====================

def add_appointment(user_id: str, date: str, time: str, notes: Optional[str] = None, user_name: Optional[str] = None, type: str = 'consultation') -> Optional[int]:
    """新增預約。
    
    為了確保資料一致性，此函數會優先從 users 表中查詢最新的 user_name。
    前端傳遞的 user_name 僅作為備用，以相容舊的呼叫方式。
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        # 1. 查詢最新的用戶姓名，確保資料正確性
        # 1. 查詢最新的用戶姓名，確保資料正確性
        cursor.execute('SELECT name FROM users WHERE user_id = ?', (user_id,))
        user_row = cursor.fetchone()
        
        final_user_name = user_name

        # 如果找不到用戶
        if not user_row:
            if user_id.startswith('manual_') and user_name:
                # 自動修復：如果手動用戶不存在但有提供名稱，則重新建立
                print(f"[APPOINTMENT INFO] 自動建立缺失的手動用戶: {user_name} ({user_id})")
                zhuyin = _name_to_zhuyin(user_name)
                try:
                    cursor.execute("""
                        INSERT INTO users (user_id, name, zhuyin, manual_update, is_admin)
                        VALUES (?, ?, ?, TRUE, FALSE)
                    """, (user_id, user_name, zhuyin))
                except sqlite3.IntegrityError:
                    pass # 應該不會發生，因為剛查過不存在
                final_user_name = user_name
            elif not user_name:
                print(f"[APPOINTMENT ERROR] 新增預約失敗：找不到用戶 user_id={user_id}，備用名稱={user_name}")
                return None
        else:
            final_user_name = user_row['name']

        print(f"[APPOINTMENT DEBUG] 嘗試新增預約：user_id={user_id}, user_name={final_user_name}, date={date}, time={time}")
        cursor.execute('''
            INSERT INTO appointments (user_id, user_name, date, time, notes, type)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, final_user_name, date, time, notes, type))
        new_id = cursor.lastrowid
        conn.commit()
        print(f"[APPOINTMENT SUCCESS] 預約成功建立：appointment_id={new_id}, {date} {time}")
        return new_id
    except sqlite3.IntegrityError as e:
        # 唯一性约束失败 - 通常表示此 (user_id, date, time) 的時段已被預約
        print(f"[APPOINTMENT CONFLICT] 唯一性約束失敗（該時段可能已被預約）：user_id={user_id}, date={date}, time={time}, type={type}, detail={str(e)}")
        return None
    except Exception as e:
        # 其他異常
        print(f"[APPOINTMENT ERROR] 新增預約時發生異常：{type(e).__name__}: {str(e)}")
        return None
    finally:
        conn.close()

def get_appointments_by_date_range(start_date: str, end_date: str) -> List[Dict]:
    """获取指定日期范围内的预约，并包含用户的提醒设置"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            a.*, 
            u.reminder_schedule,
            u.is_admin
        FROM appointments a
        LEFT JOIN users u ON a.user_id = u.user_id
        WHERE a.date BETWEEN ? AND ?
        ORDER BY a.date, a.time
    ''', (start_date, end_date))
    appointments = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return appointments

def get_appointment_by_id(appointment_id: int) -> Optional[Dict]:
    """透過 ID 獲取單筆預約"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM appointments WHERE id = ?', (appointment_id,))
    appointment = cursor.fetchone()
    conn.close()
    return dict(appointment) if appointment else None

def get_appointment_by_date_and_time(date: str, time: str) -> Optional[Dict]:
    """透過日期與時間檢查是否存在預約（用於防止衝突）"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM appointments WHERE date = ? AND time = ? AND status = ?',
        (date, time, 'confirmed')
    )
    appointment = cursor.fetchone()
    conn.close()
    return dict(appointment) if appointment else None

def get_closest_future_appointment(user_id: str) -> Optional[Dict]:
    """
    獲取指定用戶最近的一個未來預約。
    """
    conn = get_db()
    cursor = conn.cursor()
    # 修正：直接使用 pytz 獲取時區，避免循環匯入 app
    now_in_taipei = datetime.now(pytz.timezone('Asia/Taipei'))
    current_date = now_in_taipei.strftime('%Y-%m-%d')
    current_time = now_in_taipei.strftime('%H:%M')

    cursor.execute('''
        SELECT * FROM appointments 
        WHERE user_id = ? 
        AND status = 'confirmed'
        AND (date > ? OR (date = ? AND time >= ?))
        ORDER BY date ASC, time ASC
        LIMIT 1
    ''', (user_id, current_date, current_date, current_time))
    
    appointment = cursor.fetchone()
    conn.close()
    return dict(appointment) if appointment else None

def update_appointment_reply_status(appointment_id: int, status: str, last_reply: Optional[str] = None, confirm_time: Optional[datetime] = None) -> bool:
    """
    更新預約的回覆狀態。
    """
    conn = get_db()
    cursor = conn.cursor()
    
    # 根據狀態決定要更新哪些欄位
    if status == '已回覆':
        cursor.execute('''
UPDATE appointments
SET reply_status = ?, last_reply = ?, reply_time = ?
WHERE id = ?
''', (status, last_reply, datetime.now(pytz.timezone('Asia/Taipei')), appointment_id))
    elif status == '已確認':
        # 修正：當確認時，同時更新 reply_status, last_reply 和 confirm_time
        # 如果 last_reply 是 None，則不更新該欄位
        if last_reply:
            cursor.execute('UPDATE appointments SET reply_status = ?, last_reply = ?, confirm_time = ? WHERE id = ?', 
                           (status, last_reply, confirm_time, appointment_id))
        else:
            cursor.execute('UPDATE appointments SET reply_status = ?, confirm_time = ? WHERE id = ?', 
                           (status, confirm_time, appointment_id))
    elif status == '未回覆':
        # 修正：新增處理「未回覆」狀態的邏輯，將相關欄位重設為 NULL
        cursor.execute('''
            UPDATE appointments SET reply_status = ?, last_reply = NULL, reply_time = NULL, confirm_time = NULL WHERE id = ?
        ''', (status, appointment_id))
    else:
        # 其他狀態
        cursor.execute('UPDATE appointments SET reply_status = ? WHERE id = ?', (status, appointment_id))

    updated = cursor.rowcount > 0
    conn.commit()
    return updated

def get_active_slots_by_weekday(weekday: int, type: Optional[str] = None) -> List[Dict]:
    """獲取指定星期和類型的可用時段"""
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM available_slots WHERE weekday = ? AND active = TRUE"
    params = [weekday]
    
    if type:
        query += " AND type = ?"
        params.append(type)
        
    query += " ORDER BY start_time"
    
    cursor.execute(query, tuple(params))
    slots = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return slots

def get_all_available_slots() -> List[Dict]:
    """獲取所有設定的可用時段"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM available_slots ORDER BY weekday, start_time')
    slots = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return slots

def add_available_slot(weekday: int, start_time: str, end_time: str, note: Optional[str] = None, type: str = 'consultation') -> bool:
    """新增可用時段"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO available_slots (weekday, start_time, end_time, note, type)
            VALUES (?, ?, ?, ?, ?)
        ''', (weekday, start_time, end_time, note, type))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_available_slot(slot_id: int, weekday: int, start_time: str, end_time: str, note: Optional[str] = None, active: bool = True, type: str = 'consultation') -> bool:
    """更新可用時段"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE available_slots 
            SET weekday = ?, start_time = ?, end_time = ?, note = ?, active = ?, type = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (weekday, start_time, end_time, note, active, type, slot_id))
        updated = cursor.rowcount > 0
        conn.commit()
        return updated
    except Exception as e:
        print(f"Update slot error: {e}")
        return False
    finally:
        conn.close()

def delete_available_slot(slot_id: int) -> bool:
    """刪除可用時段"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM available_slots WHERE id = ?', (slot_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def is_closed_day(date_str: str) -> bool:
    """檢查指定日期是否為休診日"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM closed_days WHERE date = ?', (date_str,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def get_all_closed_days() -> List[Dict]:
    """獲取所有休診日"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM closed_days ORDER BY date')
    days = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return days

def add_closed_day(date: str, reason: Optional[str] = None) -> bool:
    """新增休診日"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO closed_days (date, reason) VALUES (?, ?)', (date, reason))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def delete_closed_day(date: str) -> bool:
    """刪除休診日"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM closed_days WHERE date = ?', (date,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_waiting_lists_by_date_range(start_date: str, end_date: str) -> Dict[str, List[Dict]]:
    """獲取指定日期範圍內的備取名單，回傳以日期為 key 的字典"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM waiting_list 
        WHERE date BETWEEN ? AND ?
        ORDER BY date, created_at
    ''', (start_date, end_date))
    
    result = {}
    for row in cursor.fetchall():
        item = dict(row)
        date = item['date']
        if date not in result:
            result[date] = []
        result[date].append(item)
        
    conn.close()
    return result

def add_to_waiting_list(date: str, user_id: str, user_name: str) -> Optional[int]:
    """新增至備取名單"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO waiting_list (date, user_id, user_name)
            VALUES (?, ?, ?)
        ''', (date, user_id, user_name))
        new_id = cursor.lastrowid
        conn.commit()
        return new_id
    except Exception as e:
        print(f"Add to waiting list error: {e}")
        return None
    finally:
        conn.close()

def remove_from_waiting_list(item_id: int) -> bool:
    """從備取名單移除"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM waiting_list WHERE id = ?', (item_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_waiting_list_item(item_id: int) -> Optional[Dict]:
    """獲取單個備取項目"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM waiting_list WHERE id = ?', (item_id,))
    item = cursor.fetchone()
    conn.close()
    return dict(item) if item else None



def update_user_day_reply_status(user_id: str, date: str, status: str) -> bool:
    """更新用戶在特定日期的所有預約回覆狀態"""
    conn = get_db()
    cursor = conn.cursor()
    TAIPEI_TZ = pytz.timezone('Asia/Taipei')
    now = datetime.now(TAIPEI_TZ)
    
    try:
        if status == '已確認':
            cursor.execute('''
                UPDATE appointments 
                SET reply_status = ?, confirm_time = ?
                WHERE user_id = ? AND date = ?
            ''', (status, now, user_id, date))
        else:
            cursor.execute('''
                UPDATE appointments 
                SET reply_status = ?
                WHERE user_id = ? AND date = ?
            ''', (status, user_id, date))
            
        updated = cursor.rowcount > 0
        conn.commit()
        return updated
    except Exception as e:
        print(f"Update user day reply status error: {e}")
        return False
    finally:
        conn.close()

def get_all_configs() -> List[Dict]:
    """獲取所有系統配置"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM configs')
    configs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return configs

def get_config(key: str, default: str = None) -> str:
    """獲取單個配置值"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM configs WHERE key = ?', (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else default

def set_config(key: str, value: str, description: Optional[str] = None) -> bool:
    """設定配置值"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        if description:
            cursor.execute('''
                INSERT INTO configs (key, value, description, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                description = excluded.description,
                updated_at = CURRENT_TIMESTAMP
            ''', (key, value, description))
        else:
            cursor.execute('''
                INSERT INTO configs (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            ''', (key, value))
        conn.commit()
        return True
    except Exception as e:
        print(f"Set config error: {e}")
        return False
    finally:
        conn.close()
    
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def update_user_day_reply_status(user_id: str, date: str, status: str) -> bool:
    """
    更新指定用戶在某一天的所有預約的回覆狀態。
    """
    conn = get_db()
    cursor = conn.cursor()
    
    now_str = datetime.now(pytz.timezone('Asia/Taipei')).strftime('%Y-%m-%d %H:%M:%S')

    if status == '已確認':
        cursor.execute('''
            UPDATE appointments SET reply_status = ?, confirm_time = ? 
            WHERE user_id = ? AND date = ?
        ''', (status, now_str, user_id, date))
    elif status == '未回覆':
        cursor.execute('''
            UPDATE appointments SET reply_status = ?, last_reply = NULL, reply_time = NULL, confirm_time = NULL 
            WHERE user_id = ? AND date = ?
        ''', (status, user_id, date))
    
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def get_appointments_by_user(user_id: str) -> List[Dict]:
    """获取指定用户的所有预约"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM appointments WHERE user_id = ? ORDER BY date, time
    ''', (user_id,))
    appointments = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return appointments

def cancel_appointment(date: str, time: str, type: str = 'consultation') -> bool:
    """取消指定日期和類型的預約"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM appointments WHERE date = ? AND time = ? AND type = ?", (date, time, type))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def cancel_user_appointment(appointment_id: int, user_id: str) -> bool:
    """安全地取消指定用戶的預約（透過 ID）"""
    conn = get_db()
    cursor = conn.cursor()
    # 確保只有本人可以刪除自己的預約
    cursor.execute("DELETE FROM appointments WHERE id = ? AND user_id = ?", (appointment_id, user_id))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted
# ... (rest of the file remains the same)

# ==================== 休診日管理 ====================

def get_all_closed_days() -> List[Dict]:
    """獲取所有休診日"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM closed_days ORDER BY date DESC')
    days = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return days

def is_closed_day(date: str) -> bool:
    """檢查某天是否為休診日"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM closed_days WHERE date = ?', (date,))
    is_closed = cursor.fetchone() is not None
    conn.close()
    return is_closed

def set_closed_day(date: str, reason: str) -> int:
    """設定休診日並取消當天所有預約"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO closed_days (date, reason) VALUES (?, ?)', (date, reason))
    cursor.execute("DELETE FROM appointments WHERE date = ?", (date,))
    cancelled_count = cursor.rowcount
    conn.commit()
    conn.close()
    return cancelled_count

def remove_closed_day(date: str) -> bool:
    """移除休診日設定"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM closed_days WHERE date = ?', (date,))
    removed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return removed

# ==================== 可用時段管理 ====================

def get_all_available_slots() -> List[Dict]:
    """獲取所有可預約時段設定"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM available_slots ORDER BY weekday, start_time')
    slots = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return slots

def get_active_slots_by_weekday(weekday: int, type: str = 'consultation') -> List[Dict]:
    """根據星期獲取所有啟用的時段"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM available_slots 
        WHERE weekday = ? AND active = TRUE AND type = ?
        ORDER BY start_time
    ''', (weekday, type))
    slots = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return slots

def add_available_slot(weekday: int, start_time: str, end_time: str, note: Optional[str] = None, type: str = 'consultation') -> bool:
    """新增一個可預約時段"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO available_slots (weekday, start_time, end_time, note, type)
            VALUES (?, ?, ?, ?, ?)
        ''', (weekday, start_time, end_time, note, type))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False # 時段已存在
    finally:
        conn.close()

def update_available_slot(slot_id: int, weekday: int, start_time: str, end_time: str, active: bool, note: Optional[str], type: str = 'consultation') -> bool:
    """更新一個可預約時段"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE available_slots SET weekday=?, start_time=?, end_time=?, active=?, note=?, type=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    ''', (weekday, start_time, end_time, active, note, type, slot_id))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def delete_available_slot(slot_id: int) -> bool:
    """刪除一個可預約時段"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM available_slots WHERE id=?', (slot_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def copy_slots(source_weekday: int, target_weekdays: List[int], types: List[str] = None) -> tuple[int, int]:
    """將指定來源星期的時段設定複製到多個目標星期
    
    Args:
        source_weekday: 來源星期 (1-5)
        target_weekdays: 目標星期列表
        types: 要複製的類型列表，例如 ['consultation', 'massage']。如果為 None，則複製所有類型
    """
    if types is None:
        types = ['consultation', 'massage']  # 預設複製所有類型
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        # 1. 獲取來源星期的指定類型時段，並立即轉換為普通的 tuple 列表
        # 這樣即使之後刪除了來源資料，這些資料也不會受影響
        placeholders = ','.join('?' for _ in types)
        query = f'SELECT start_time, end_time, active, note, type FROM available_slots WHERE weekday = ? AND type IN ({placeholders})'
        cursor.execute(query, (source_weekday, *types))
        source_slots_raw = cursor.fetchall()
        
        if not source_slots_raw:
            return 0, 0 # 沒有可複製的時段
        
        # 將 Row 物件轉換為普通的 tuple，避免在刪除操作後資料失效
        source_slots = [(row['start_time'], row['end_time'], row['active'], row['note'], row['type']) 
                        for row in source_slots_raw]

        # 2. 刪除目標星期的指定類型時段
        weekday_placeholders = ','.join('?' for _ in target_weekdays)
        type_placeholders = ','.join('?' for _ in types)
        delete_query = f'DELETE FROM available_slots WHERE weekday IN ({weekday_placeholders}) AND type IN ({type_placeholders})'
        cursor.execute(delete_query, (*target_weekdays, *types))
        deleted_count = cursor.rowcount

        # 3. 準備要插入的新時段
        slots_to_insert = []
        for slot in source_slots:
            start_time, end_time, active, note, slot_type = slot
            for weekday in target_weekdays:
                slots_to_insert.append((weekday, start_time, end_time, active, note, slot_type))
        
        cursor.executemany('INSERT INTO available_slots (weekday, start_time, end_time, active, note, type) VALUES (?, ?, ?, ?, ?, ?)', slots_to_insert)
        inserted_count = cursor.rowcount
        conn.commit()
        return inserted_count, deleted_count # 回傳新增數量和刪除數量
    except Exception as e:
        conn.rollback()
        print(f"複製時段時發生錯誤: {e}")
        raise e
    finally:
        conn.close()

# ==================== 杂项功能 ====================

def update_user_zhuyin(user_id: str, zhuyin: str) -> bool:
    """更新用户注音"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET zhuyin = ? WHERE user_id = ?', (zhuyin, user_id))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def update_user_phone_field(user_id: str, field: str, phone: str) -> bool:
    """更新用户的电话字段（phone 或 phone2）"""
    if field not in ['phone', 'phone2']:
        return False
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(f'UPDATE users SET {field} = ? WHERE user_id = ?', (phone, user_id))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def update_user_address(user_id: str, address: str) -> bool:
    """更新用戶地址"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET address = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?', (address, user_id))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def get_pending_schedules_to_send(current_time: datetime) -> List[Dict]:
    """獲取待發送的排程"""
    conn = get_db()
    cursor = conn.cursor()
    # 假設 schedules 表有 scheduled_time 欄位
    cursor.execute('''
        SELECT * FROM schedules 
        WHERE status = 'pending' AND send_time <= ?
    ''', (current_time,))
    schedules = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return schedules

def update_schedule_status(schedule_id: int, status: str) -> bool:
    """更新排程的狀態"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE schedules SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (status, schedule_id))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def generate_and_save_zhuyin(user_id: str) -> Optional[str]:
    """为用户生成并保存注音"""
    user = get_user_by_id(user_id)
    if not user:
        return None
    new_zhuyin = _name_to_zhuyin(user['name'])
    if update_user_zhuyin(user_id, new_zhuyin):
        return new_zhuyin
    return None

def get_or_create_user_by_phone(phone: str) -> Optional[Dict]:
    """通过电话号码获取或创建用户"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE phone = ? OR phone2 = ?', (phone, phone))
    user = cursor.fetchone()
    if user:
        conn.close()
        return dict(user)
    else:
        # 如果用户不存在，创建一个新用户
        user_id = f"phone_user_{phone}"
        name = f"用戶_{phone[-4:]}"
        add_user(user_id, name, phone=phone, picture_url=None)
        return get_user_by_id(user_id)

# ==================== 系统配置 ====================

def get_all_configs() -> List[Dict]:
    """获取所有系统配置"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM configs ORDER BY key')
    configs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return configs

def get_config(key: str, default: Optional[str] = None) -> Optional[str]:
    """获取单个系统配置值"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM configs WHERE key = ?', (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else default

def set_config(key: str, value: str, description: Optional[str] = None) -> bool:
    """设置或更新系统配置"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO configs (key, value, description, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
        value = excluded.value,
        description = COALESCE(excluded.description, description),
        updated_at = CURRENT_TIMESTAMP
    ''', (key, value, description))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated
# ==================== 備取名單管理 ====================

def get_waiting_lists_by_date_range(start_date: str, end_date: str) -> Dict[str, List[Dict]]:
    """获取指定日期范围内的备取名单，并按日期分组"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM waiting_list 
        WHERE date BETWEEN ? AND ?
        ORDER BY date, created_at
    ''', (start_date, end_date))
    
    waiting_lists = {}
    for row in cursor.fetchall():
        row_dict = dict(row)
        date_str = row_dict['date']
        if date_str not in waiting_lists:
            waiting_lists[date_str] = []
        waiting_lists[date_str].append(row_dict)
        
    conn.close()
    return waiting_lists

def add_to_waiting_list(date: str, user_id: str, user_name: str) -> Optional[Dict]:
    """新增到备取名单"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO waiting_list (date, user_id, user_name)
            VALUES (?, ?, ?)
        ''', (date, user_id, user_name))
        item_id = cursor.lastrowid
        conn.commit()
        # 返回新增的項目
        return {"id": item_id, "date": date, "user_id": user_id, "user_name": user_name}
    except Exception as e:
        print(f"新增備取失敗: {e}")
        return None
    finally:
        conn.close()

def remove_from_waiting_list(item_id: int) -> bool:
    """从备取名单中移除"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM waiting_list WHERE id = ?', (item_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted
# ... (rest of the file remains the same)
