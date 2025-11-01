from datetime import datetime, timedelta
from collections import defaultdict
import pytz

import database as db
from app.utils.line_api import send_line_message
from .utils import get_week_dates_for_scheduler

def _do_send_reminders(app, appointments: list, reminder_type: str = 'daily') -> tuple[int, int]:
    sent_count = 0
    failed_count = 0
    if not appointments:
        return 0, 0

    user_appointments = defaultdict(list)
    for apt in appointments:
        if apt.get('user_id') and apt['user_id'].startswith('U'):
            user_appointments[apt['user_id']].append(apt)

    for user_id, apt_list in user_appointments.items():
        appointments_by_date = defaultdict(list)
        for apt in apt_list:
            appointments_by_date[apt['date']].append(apt)

        for date_str, daily_apt_list in appointments_by_date.items():
            daily_apt_list.sort(key=lambda x: x['time'])
            user_name = daily_apt_list[0]['user_name']
            TAIPEI_TZ = app.config['TAIPEI_TZ']
            apt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            today_in_taipei = datetime.now(TAIPEI_TZ).date()
            
            # 計算本週日的日期，用來判斷是否為「下週」
            this_sunday = today_in_taipei - timedelta(days=today_in_taipei.weekday()) + timedelta(days=6)
            
            weekday_names = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']
            weekday_name = weekday_names[apt_date.weekday()]

            if apt_date == today_in_taipei:
                date_keyword = "今天"
            elif apt_date == today_in_taipei + timedelta(days=1):
                date_keyword = "明天"
            elif apt_date > this_sunday:
                date_keyword = f"下{weekday_name}"
            else:
                date_keyword = weekday_name

            time_slots_str = ""
            for apt in daily_apt_list:
                time_obj = datetime.strptime(apt['time'], '%H:%M')
                time_str = time_obj.strftime('%p %I:%M').replace('AM', '上午').replace('PM', '下午')
                time_slots_str += f"• {time_str}\n"
                
            default_template = ("您好，提醒您{date_keyword} ({date}) 有預約以下時段：\n\n""{time_slots}\n\n""如果需要更改或取消，請與我們聯繫，謝謝。")
            template = db.get_config('message_template_reminder', default_template) or default_template

            message = template.format(user_name=user_name, date_keyword=date_keyword, date=apt_date.strftime('%m/%d'), weekday=weekday_name, time_slots=time_slots_str.strip())
            
            success = send_line_message(user_id=user_id, messages=[{"type": "text", "text": message}], message_type=f'reminder_{reminder_type}', target_name=user_name)
            if success:
                sent_count += 1
            else:
                failed_count += 1
            
    return sent_count, failed_count

def send_daily_reminders_job(app):
    """每日提醒的排程任務"""
    with app.app_context():
        if db.get_config('auto_reminder_daily_enabled', 'false') == 'true':
            app.logger.info("執行每日自動提醒...")
            TAIPEI_TZ = app.config['TAIPEI_TZ']
            today_str = datetime.now(TAIPEI_TZ).strftime('%Y-%m-%d')
            appointments = db.get_appointments_by_date_range(today_str, today_str)
            appointments = [apt for apt in appointments if apt['status'] == 'confirmed']
            if appointments:
                sent, failed = _do_send_reminders(app, appointments, 'daily')
                app.logger.info(f"每日提醒發送完成: {sent} 成功, {failed} 失敗。")
            else:
                app.logger.info("今日無預約，不執行提醒。")

def send_weekly_reminders_job(app):
    """每週提醒的排程任務"""
    with app.app_context():
        if db.get_config('auto_reminder_weekly_enabled', 'false') == 'true':
            app.logger.info("執行每週自動提醒...")
            week_dates = get_week_dates_for_scheduler(week_offset=1) # 預設為下週的預約
            start_date = week_dates[0]['date']
            end_date = week_dates[-1]['date']
            appointments = db.get_appointments_by_date_range(start_date, end_date)
            appointments = [apt for apt in appointments if apt['status'] == 'confirmed']
            if appointments:
                sent, failed = _do_send_reminders(app, appointments, 'weekly')
                app.logger.info(f"每週提醒發送完成: {sent} 成功, {failed} 失敗。")
            else:
                app.logger.info("下週無預約，不執行提醒。")

def send_custom_schedules_job(app):
    """處理自訂排程訊息的背景任務"""
    with app.app_context():
        # 獲取當前的 UTC 時間，並傳遞給資料庫查詢函式
        now_utc = datetime.now(pytz.utc)
        schedules_to_send = db.get_pending_schedules_to_send(now_utc)
        if not schedules_to_send:
            return

        app.logger.info(f"發現 {len(schedules_to_send)} 個待發送的排程...")
        for schedule in schedules_to_send:
            success = send_line_message(
                user_id=schedule['user_id'],
                messages=[{"type": "text", "text": schedule['message']}],
                message_type='custom_schedule',
                target_name=schedule['user_name']
            )
            
            new_status = 'sent' if success else 'failed'
            db.update_schedule_status(schedule['id'], new_status)
            app.logger.info(f"排程 {schedule['id']} 發送給 {schedule['user_name']}，狀態: {new_status}")