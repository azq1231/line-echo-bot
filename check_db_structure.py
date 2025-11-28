import sqlite3

conn = sqlite3.connect('appointments.db')
cursor = conn.cursor()

# 檢查 appointments 表的結構
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='appointments'")
result = cursor.fetchone()
if result:
    print("=== appointments 表結構 ===")
    print(result[0])
    print()

# 檢查是否有索引
cursor.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='appointments'")
indexes = cursor.fetchall()
if indexes:
    print("=== appointments 表的索引 ===")
    for idx in indexes:
        if idx[0]:  # 有些索引可能是 None (自動建立的)
            print(idx[0])
    print()

conn.close()
print("檢查完成")
