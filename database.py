import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
import os

DB_FILE = 'appointments.db'

def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # 使结果可以像字典一样访问
    return conn

def init_database():
    """初始化数据库结构"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 预约表（支持多时段预约）
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
    
    # 创建部分唯一索引：只对 confirmed 状态的预约强制唯一性
    cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_confirmed_slot 
        ON appointments(date, time) 
        WHERE status = 'confirmed'
    ''')
    
    # 休诊日期表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS closed_days (
            date TEXT PRIMARY KEY,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 排程消息表（保留原有功能）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedules (
            schedule_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            user_name TEXT,
            send_time TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sent_at TIMESTAMP,
            retry_count INTEGER DEFAULT 0
        )
    ''')
    
    # 通知模板表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notification_templates (
            template_id TEXT PRIMARY KEY,
            template_type TEXT NOT NULL,
            content TEXT NOT NULL,
            variables TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 插入默认通知模板
    default_templates = [
        ('appointment_confirmed', 'appointment', 
         '已為您預約 ${日期} ${時間}，若需取消請回覆「取消」。', 
         '["日期", "時間", "姓名"]'),
        ('appointment_multi', 'appointment', 
         '已為您預約 ${日期} ${時間列表}，共${人數}位。若需取消請回覆「取消」。', 
         '["日期", "時間列表", "人數"]'),
        ('clinic_closed', 'notification', 
         '原定 ${日期} 門診已休診，您的預約將自動取消，造成不便敬請見諒 🙏', 
         '["日期"]'),
    ]
    
    for template_id, template_type, content, variables in default_templates:
        cursor.execute('''
            INSERT OR IGNORE INTO notification_templates 
            (template_id, template_type, content, variables)
            VALUES (?, ?, ?, ?)
        ''', (template_id, template_type, content, variables))
    
    conn.commit()
    conn.close()
    print("✅ 数据库初始化完成")

# ==================== 用户管理 ====================

def get_all_users() -> List[Dict]:
    """获取所有用户"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users ORDER BY created_at DESC')
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users

def get_user_by_id(user_id: str) -> Optional[Dict]:
    """根据用户ID获取用户信息"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def add_user(user_id: str, name: str, phone: Optional[str] = None) -> bool:
    """添加或更新用户"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO users (user_id, name, phone)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                name = excluded.name,
                phone = excluded.phone,
                updated_at = CURRENT_TIMESTAMP
        ''', (user_id, name, phone))
        conn.commit()
        return True
    except Exception as e:
        print(f"添加用户错误: {e}")
        return False
    finally:
        conn.close()

def delete_user(user_id: str) -> bool:
    """删除用户"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"删除用户错误: {e}")
        return False
    finally:
        conn.close()

def update_user_name(user_id: str, new_name: str) -> bool:
    """更新用户姓名"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE users SET name = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE user_id = ?
        ''', (new_name, user_id))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"更新用户姓名错误: {e}")
        return False
    finally:
        conn.close()

# ==================== 预约管理 ====================

def get_appointments_by_date_range(start_date: str, end_date: str) -> List[Dict]:
    """获取日期范围内的所有预约"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM appointments 
        WHERE date >= ? AND date <= ? AND status = 'confirmed'
        ORDER BY date, time
    ''', (start_date, end_date))
    appointments = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return appointments

def get_appointments_by_user(user_id: str) -> List[Dict]:
    """获取用户的所有预约"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM appointments 
        WHERE user_id = ?
        ORDER BY date, time
    ''', (user_id,))
    appointments = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return appointments

def add_appointment(user_id: str, user_name: str, date: str, time: str, 
                   booking_group_id: Optional[str] = None, notes: Optional[str] = None) -> bool:
    """添加预约"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO appointments (user_id, user_name, date, time, booking_group_id, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, user_name, date, time, booking_group_id, notes))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        print(f"时段冲突: {date} {time} 已被预约")
        return False
    except Exception as e:
        print(f"添加预约错误: {e}")
        return False
    finally:
        conn.close()

def cancel_appointment(date: str, time: str) -> bool:
    """取消预约"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE appointments SET status = 'cancelled' 
            WHERE date = ? AND time = ?
        ''', (date, time))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"取消预约错误: {e}")
        return False
    finally:
        conn.close()

def get_user_appointments(user_id: str, status: str = 'confirmed') -> List[Dict]:
    """获取用户的所有预约"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM appointments 
        WHERE user_id = ? AND status = ?
        ORDER BY date, time
    ''', (user_id, status))
    appointments = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return appointments

# ==================== 休诊管理 ====================

def set_closed_day(date: str, reason: str = "休診") -> bool:
    """设置休诊日"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        # 添加休诊日
        cursor.execute('''
            INSERT OR REPLACE INTO closed_days (date, reason)
            VALUES (?, ?)
        ''', (date, reason))
        
        # 取消该日所有预约
        cursor.execute('''
            UPDATE appointments SET status = 'cancelled_by_clinic' 
            WHERE date = ? AND status = 'confirmed'
        ''', (date,))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"设置休诊错误: {e}")
        return False
    finally:
        conn.close()

def remove_closed_day(date: str) -> bool:
    """取消休诊"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM closed_days WHERE date = ?', (date,))
        conn.commit()
        return True
    except Exception as e:
        print(f"取消休诊错误: {e}")
        return False
    finally:
        conn.close()

def is_closed_day(date: str) -> bool:
    """检查是否为休诊日"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT date FROM closed_days WHERE date = ?', (date,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def get_closed_days() -> List[Dict]:
    """获取所有休诊日"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM closed_days ORDER BY date')
    closed_days = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return closed_days

def get_all_closed_days() -> List[Dict]:
    """获取所有休诊日（别名函数）"""
    return get_closed_days()

# ==================== 通知模板 ====================

def get_template(template_id: str) -> Optional[Dict]:
    """获取通知模板"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM notification_templates WHERE template_id = ?', (template_id,))
    template = cursor.fetchone()
    conn.close()
    return dict(template) if template else None

def render_template(template_id: str, variables: Dict) -> str:
    """渲染通知模板"""
    template = get_template(template_id)
    if not template:
        return ""
    
    content = template['content']
    for key, value in variables.items():
        content = content.replace(f"${{{key}}}", str(value))
    
    return content

# 初始化数据库
if __name__ == "__main__":
    init_database()
