import sqlite3

conn = sqlite3.connect('appointments.db')
cursor = conn.cursor()

print("開始修正資料庫 schema...")

# 1. 檢查 available_slots 表是否有 type 欄位
cursor.execute("PRAGMA table_info(available_slots)")
columns = [col[1] for col in cursor.fetchall()]
has_type_column = 'type' in columns

print(f"available_slots 表{'已有' if has_type_column else '沒有'} type 欄位")

# 2. 建立新的表格（包含正確的 UNIQUE 約束）
cursor.execute('''
    CREATE TABLE IF NOT EXISTS available_slots_new (
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

# 3. 複製舊資料到新表格
if has_type_column:
    # 如果已有 type 欄位，直接複製
    cursor.execute('''
        INSERT INTO available_slots_new (id, weekday, start_time, end_time, active, note, type, created_at, updated_at)
        SELECT id, weekday, start_time, end_time, active, note, type, created_at, updated_at
        FROM available_slots
    ''')
else:
    # 如果沒有 type 欄位，設定預設值為 'consultation'
    cursor.execute('''
        INSERT INTO available_slots_new (id, weekday, start_time, end_time, active, note, type, created_at, updated_at)
        SELECT id, weekday, start_time, end_time, active, note, 'consultation', created_at, updated_at
        FROM available_slots
    ''')

# 4. 刪除舊表格
cursor.execute('DROP TABLE available_slots')

# 5. 重新命名新表格
cursor.execute('ALTER TABLE available_slots_new RENAME TO available_slots')

print("\n處理 appointments 表...")

# 6. 檢查 appointments 表是否有 type 欄位
cursor.execute("PRAGMA table_info(appointments)")
columns = [col[1] for col in cursor.fetchall()]
has_type_in_appointments = 'type' in columns

print(f"appointments 表{'已有' if has_type_in_appointments else '沒有'} type 欄位")

# 7. 如果 appointments 表沒有 type 欄位，加入它
if not has_type_in_appointments:
    cursor.execute("ALTER TABLE appointments ADD COLUMN type TEXT DEFAULT 'consultation'")
    print("已在 appointments 表中加入 type 欄位")

conn.commit()

# 驗證結果
print("\n=== 驗證結果 ===")
cursor.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name="available_slots"')
table_sql = cursor.fetchone()
print('\navailable_slots 表結構:')
print(table_sql[0])

cursor.execute('SELECT COUNT(*) FROM available_slots')
count = cursor.fetchone()[0]
print(f'\navailable_slots 資料筆數: {count}')

cursor.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name="appointments"')
table_sql = cursor.fetchone()
print('\nappointments 表結構:')
print(table_sql[0])

cursor.execute('SELECT COUNT(*) FROM appointments')
count = cursor.fetchone()[0]
print(f'\nappointments 資料筆數: {count}')

conn.close()
print('\n✅ 資料庫 schema 修正完成！')
