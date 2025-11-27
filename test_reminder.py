import sys
from app import create_app
from app.scheduler.jobs import send_daily_reminders_job, send_weekly_reminders_job

def test_daily_reminder(fake_date):
    app = create_app(start_scheduler=False)
    with app.app_context():
        print(f"正在模擬 {fake_date} 的每日提醒...")
        # 注意：每日提醒會發送「明天」的預約
        send_daily_reminders_job(app, fake_today_str=fake_date)
        print("測試完成。")

def test_weekly_reminder(fake_date):
    app = create_app(start_scheduler=False)
    with app.app_context():
        print(f"正在模擬 {fake_date} 的每週提醒...")
        # 注意：每週提醒會發送「下週」的預約
        send_weekly_reminders_job(app, fake_today_str=fake_date)
        print("測試完成。")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python test_reminder.py [daily|weekly] [YYYY-MM-DD]")
        print("範例: python test_reminder.py daily 2025-11-27")
    else:
        mode = sys.argv[1]
        date = sys.argv[2]
        if mode == 'daily':
            test_daily_reminder(date)
        elif mode == 'weekly':
            test_weekly_reminder(date)
        else:
            print("未知的模式，請使用 daily 或 weekly")
