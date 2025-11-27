from datetime import datetime, timedelta
import pytz
from collections import defaultdict
from typing import List, Dict

import database as db
from app.utils.line_api import send_line_message

TAIPEI_TZ = pytz.timezone('Asia/Taipei')

def _do_send_reminders(app, appointments: list, reminder_type: str = 'daily', base_date=None) -> tuple[int, int]:
    sent_count = 0
    failed_count = 0
    
    # Group appointments by user_id
    user_appointments = defaultdict(list)
    for apt in appointments:
        user_appointments[apt['user_id']].append(apt)

    today = base_date if base_date else datetime.now(TAIPEI_TZ).date()

    for user_id, apts in user_appointments.items():
        # Sort appointments by time
        apts.sort(key=lambda x: x['time'])
        
        # Construct message
        user_name = apts[0]['user_name']
        msg = f"您好 {user_name}，提醒您：\n\n"
        
        for apt in apts:
            try:
                apt_date = datetime.strptime(apt['date'], '%Y-%m-%d').date()
            except ValueError:
                continue # Skip invalid dates

            date_keyword = ""
            if apt_date == today:
                date_keyword = "今天"
            elif apt_date == today + timedelta(days=1):
                date_keyword = "明天"
            else:
                weekday_names = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']
                date_keyword = f"下{weekday_names[apt_date.weekday()]}"

            msg += f"• {date_keyword} ({apt['date']}) {apt['time']} 有預約\n"
        
        msg += "\n請準時出席，謝謝！"

        # Send message
        try:
            success = send_line_message(
                user_id=user_id,
                messages=[{"type": "text", "text": msg}],
                message_type=f'{reminder_type}_reminder',
                target_name=user_name
            )
            if success:
                sent_count += 1
            else:
                failed_count += 1
        except Exception as e:
            app.logger.error(f"發送提醒失敗 user_id={user_id}: {e}")
            failed_count += 1
            
    return sent_count, failed_count

def send_daily_reminders_job(app, fake_today_str=None):
    with app.app_context():
        if fake_today_str:
            today = datetime.strptime(fake_today_str, '%Y-%m-%d').date()
        else:
            today = datetime.now(TAIPEI_TZ).date()
            
        target_date = today + timedelta(days=1) # Remind for tomorrow
        target_date_str = target_date.strftime('%Y-%m-%d')
        
        appointments = db.get_appointments_by_date_range(target_date_str, target_date_str)
        appointments_to_send = [apt for apt in appointments if apt['status'] == 'confirmed']
        
        if appointments_to_send:
            app.logger.info(f"開始發送每日提醒，目標日期: {target_date_str}, 數量: {len(appointments_to_send)}")
            _do_send_reminders(app, appointments_to_send, 'daily', base_date=today)
        else:
            app.logger.info(f"今日 ({today}) 無需發送明日 ({target_date_str}) 的提醒。")

def send_weekly_reminders_job(app, fake_today_str=None):
    with app.app_context():
        if fake_today_str:
            today = datetime.strptime(fake_today_str, '%Y-%m-%d').date()
        else:
            today = datetime.now(TAIPEI_TZ).date()
            
        # Logic: Send reminders for next week? Or just a summary?
        # Assuming it sends reminders for the upcoming week.
        start_date = today + timedelta(days=1)
        end_date = today + timedelta(days=7)
        
        appointments = db.get_appointments_by_date_range(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
        appointments_to_send = [apt for apt in appointments if apt['status'] == 'confirmed']
        
        if appointments_to_send:
             app.logger.info(f"開始發送每週提醒，範圍: {start_date} ~ {end_date}, 數量: {len(appointments_to_send)}")
             _do_send_reminders(app, appointments_to_send, 'week', base_date=today)

def send_custom_schedules_job(app):
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