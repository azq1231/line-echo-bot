from apscheduler.schedulers.background import BackgroundScheduler
import pytz

from .jobs import (
    send_daily_reminders_job,
    send_weekly_reminders_job,
    send_custom_schedules_job
)
import database as db

scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Taipei'))

def init_scheduler(app):
    """初始化並啟動排程器"""
    with app.app_context():
        # 讀取資料庫中的設定
        daily_time_str = db.get_config('auto_reminder_daily_time', '09:00') or '09:00'
        daily_hour, daily_minute = map(int, daily_time_str.split(':'))

        weekly_day = db.get_config('auto_reminder_weekly_day', 'sun') or 'sun'        
        weekly_time_str = db.get_config('auto_reminder_weekly_time', '21:00') or '21:00'
        weekly_hour, weekly_minute = map(int, weekly_time_str.split(':'))

        # ✅ 使用 lambda 將 app 實例傳入 job，而不是讓 job 自己去 import
        scheduler.add_job(
            func=lambda: send_daily_reminders_job(app),
            trigger="cron", id='daily_reminder_job',
            hour=daily_hour, minute=daily_minute,
            replace_existing=True
        )
        scheduler.add_job(
            func=lambda: send_weekly_reminders_job(app),
            trigger="cron", id='weekly_reminder_job',
            day_of_week=weekly_day, hour=weekly_hour, minute=weekly_minute,
            replace_existing=True
        )
        scheduler.add_job(
            func=lambda: send_custom_schedules_job(app),
            trigger="interval", id='custom_schedules_job',
            minutes=1, replace_existing=True
        )

        if not scheduler.running:
            scheduler.start()
            app.logger.info("排程器已啟動。")