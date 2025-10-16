import sqlite3
from typing import List, Dict, Optional
from pypinyin import pinyin, Style

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
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """初始化数据库结构，并安全地添加新字段"""
    conn = get_db()
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

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS closed_days (
            date TEXT PRIMARY KEY,
            reason TEXT
        )
    ''')

    # 系统配置表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS configs (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    conn.commit()
    conn.close()
    print("Database initialized.")

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

def add_user(user_id: str, name: str, picture_url: Optional[str] = None, phone: Optional[str] = None, phone2: Optional[str] = None) -> None:
    """新增或更新用户，如果用户已存在，则更新姓名"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 检查用户是否存在
    cursor.execute('SELECT name, picture_url, manual_update FROM users WHERE user_id = ?', (user_id,))
    existing_user = cursor.fetchone()
    
    zhuyin = _name_to_zhuyin(name)

    if existing_user:
        # 如果用戶名稱是手動更新的，則只更新頭像，不覆蓋名稱
        if existing_user['manual_update']:
            if existing_user['picture_url'] != picture_url:
                cursor.execute('''
                    UPDATE users SET picture_url = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?
                ''', (picture_url, user_id))
                print(f"Updated user {user_id}'s picture_url (name is manually set)")
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
            INSERT INTO users (user_id, name, picture_url, phone, phone2, zhuyin)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, name, picture_url, phone, phone2, zhuyin))
        print(f"Added new user: {name} ({user_id})")
        
    conn.commit()
    conn.close()

def update_user_name(user_id: str, new_name: str) -> bool:
    """更新用户名和注音"""
    conn = get_db()
    cursor = conn.cursor()
    zhuyin = _name_to_zhuyin(new_name)
    cursor.execute('''
        UPDATE users 
        SET name = ?, zhuyin = ?, manual_update = TRUE, updated_at = CURRENT_TIMESTAMP 
        WHERE user_id = ?
    ''', (new_name, zhuyin, user_id))
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def delete_user(user_id: str) -> bool:
    """删除用户"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

# ==================== 预约管理 ====================

def add_appointment(user_id: str, user_name: str, date: str, time: str, notes: Optional[str] = None) -> bool:
    """新增预约"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO appointments (user_id, user_name, date, time, notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, user_name, date, time, notes))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # 唯一性约束失败
        return False
    finally:
        conn.close()

def get_appointments_by_date_range(start_date: str, end_date: str) -> List[Dict]:
    """获取指定日期范围内的预约"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM appointments 
        WHERE date BETWEEN ? AND ?
        ORDER BY date, time
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

def cancel_appointment(date: str, time: str) -> bool:
    """取消指定日期的预约"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM appointments WHERE date = ? AND time = ?", (date, time))
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
# ... (rest of the file remains the same)
