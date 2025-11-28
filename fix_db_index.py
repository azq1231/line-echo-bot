import sqlite3

conn = sqlite3.connect('appointments.db')
cursor = conn.cursor()

try:
    # 1. 刪除舊的索引
    print("正在刪除舊的索引 idx_confirmed_slot...")
    cursor.execute("DROP INDEX IF EXISTS idx_confirmed_slot")
    
    # 2. 建立新的索引，包含 type 欄位
    print("正在建立新的索引 idx_confirmed_slot (包含 type 欄位)...")
    cursor.execute("""
        CREATE UNIQUE INDEX idx_confirmed_slot
        ON appointments(date, time, type)
        WHERE status = 'confirmed'
    """)
    
    conn.commit()
    print("✅ 索引更新成功！")
    print("現在同一個時段可以同時有「看診」和「推拿」兩種預約了。")
    
except Exception as e:
    print(f"❌ 錯誤：{e}")
    conn.rollback()
finally:
    conn.close()
