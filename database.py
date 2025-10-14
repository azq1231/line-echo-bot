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
    if row:
        stats["total_messages"] = row[0]
        stats["success_count"] = row[1]
        stats["failed_count"] = row[2]
        stats["success_rate"] = (row[1] / row[0] * 100) if row[0] > 0 else 0
    
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
            "success_rate": (row[2] / row[1] * 100) if row[1] > 0 else 0
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
            "success_rate": (row[2] / row[1] * 100) if row[1] > 0 else 0
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
