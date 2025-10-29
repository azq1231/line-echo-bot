from datetime import datetime, timedelta
from flask import current_app
from collections import defaultdict

import database as db
from app.utils.line_api import send_line_message
from app.utils.helpers import get_week_dates

def _do_send_reminders(appointments: list, reminder_type: str = 'daily') -> tuple[int, int]:
    sent_count = 0
    failed_count = 0
    TAIPEI_TZ = current_app.config['TAIPEI_TZ']

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
            apt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            today = datetime.now(TAIPEI_TZ).date()
            
            if apt_date == today:
                date_keyword = "今天"
            elif apt_date == today + timedelta(days=1):
                date_keyword = "明天"
            else:
                weekday_names = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']
                date_keyword = f" {weekday_names[apt_date.weekday()]}"

            time_slots_str = ""
            for apt in daily_apt_list:
                time_obj = datetime.strptime(apt['time'], '%H:%M')
                time_str = time_obj.strftime('%p %I:%M').replace('AM', '上午').replace('PM', '下午')
                time_slots_str += f"• {time_str}\n"
                
            default_template = (
                "您好，提醒您{date_keyword} ({date}) 有預約以下時段：\n\n"
                "{time_slots}\n\n"
                "如果需要更改或取消，請與我們聯繫，謝謝。")
            template = db.get_config('message_template_reminder', default_template) or default_template

            message = template.format(
                user_name=user_name,
                date_keyword=date_keyword,
                date=apt_date.strftime('%m/%d'),
                weekday=date_keyword.strip(),
                time_slots=time_slots_str.strip()
            )
            
            success = send_line_message(
                user_id=user_id,
                messages=[{"type": "text", "text": message}],
                message_type=f'reminder_{reminder_type}',
                target_name=user_name
            )
            if success:
                sent_count += 1
            else:
                failed_count += 1
            
    return sent_count, failed_count

def send_daily_reminders_job():
    with current_app.app_context():
        if db.get_config('auto_reminder_daily_enabled', 'false') == 'true':
            # ... implementation ...
            pass

def send_weekly_reminders_job():
    with current_app.app_context():
        if db.get_config('auto_reminder_weekly_enabled', 'false') == 'true':
            # ... implementation ...
            pass

def send_custom_schedules_job():
    with current_app.app_context():
        # ... implementation ...
        pass