import sqlite3

conn = sqlite3.connect('appointments.db')
cursor = conn.cursor()

# 檢查表結構
cursor.execute('PRAGMA table_info(available_slots)')
columns = cursor.fetchall()
print('Columns:')
for col in columns:
    print(f'  {col}')

# 檢查表的 SQL 定義
cursor.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name="available_slots"')
table_sql = cursor.fetchone()
print('\nTable SQL:')
print(table_sql[0] if table_sql else 'Table not found')

# 檢查是否有 type 欄位
cursor.execute('SELECT name FROM pragma_table_info("available_slots") WHERE name="type"')
has_type = cursor.fetchone()
print(f'\nHas type column: {has_type is not None}')

# 嘗試查詢一些資料
cursor.execute('SELECT * FROM available_slots LIMIT 5')
rows = cursor.fetchall()
print(f'\nSample data ({len(rows)} rows):')
for row in rows:
    print(f'  {row}')

conn.close()
