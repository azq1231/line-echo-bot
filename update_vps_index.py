#!/usr/bin/env python3
"""
VPS 資料庫索引更新腳本
用於修復預約簿「同上」功能的索引問題
"""
import sqlite3
import sys

def update_index(db_path='appointments.db'):
    """更新資料庫索引，將 type 欄位加入唯一約束"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("=" * 50)
        print("開始更新資料庫索引...")
        print("=" * 50)
        
        # 1. 檢查舊索引是否存在
        cursor.execute("""
            SELECT sql FROM sqlite_master 
            WHERE type='index' AND name='idx_confirmed_slot'
        """)
        old_index = cursor.fetchone()
        
        if old_index:
            print(f"\n舊索引：\n{old_index[0]}\n")
        else:
            print("\n未找到舊索引\n")
        
        # 2. 刪除舊索引
        print("正在刪除舊索引...")
        cursor.execute("DROP INDEX IF EXISTS idx_confirmed_slot")
        print("✅ 舊索引已刪除")
        
        # 3. 建立新索引
        print("\n正在建立新索引（包含 type 欄位）...")
        cursor.execute("""
            CREATE UNIQUE INDEX idx_confirmed_slot
            ON appointments(date, time, type)
            WHERE status = 'confirmed'
        """)
        print("✅ 新索引已建立")
        
        # 4. 驗證新索引
        cursor.execute("""
            SELECT sql FROM sqlite_master 
            WHERE type='index' AND name='idx_confirmed_slot'
        """)
        new_index = cursor.fetchone()
        
        if new_index:
            print(f"\n新索引：\n{new_index[0]}\n")
        
        conn.commit()
        
        print("=" * 50)
        print("✅ 索引更新成功！")
        print("=" * 50)
        print("\n修復說明：")
        print("- 同一時段現在可以同時有「看診」和「推拿」預約")
        print("- 「同上」功能不會再因為重複時段而失敗")
        print("- 仍然保持唯一性：同一時段、同一類型只能有一筆預約")
        print()
        
        return True
        
    except Exception as e:
        print(f"\n❌ 錯誤：{e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    # 可以從命令列參數指定資料庫路徑
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'appointments.db'
    
    print(f"資料庫路徑：{db_path}\n")
    
    success = update_index(db_path)
    sys.exit(0 if success else 1)
