from flask import Blueprint, request, session, render_template, jsonify
from datetime import datetime
import pytz

import database as db
from app.utils.helpers import get_week_dates, generate_time_slots, api_response

booking_bp = Blueprint('booking', __name__)

@booking_bp.route("/", methods=["GET"])
def booking_page():
    if db.get_config('feature_booking_enabled') == 'false':
        return "Feature disabled", 404

    user_session = session.get('user')
    schedule_data = None
    week_offset = 0

    try:
        max_weeks = int(db.get_config('booking_window_weeks', '2') or '2')
    except (ValueError, TypeError):
        max_weeks = 2

    if user_session:
        user = user_session
        week_offset_str = request.args.get('week_offset', '0')
        try:
            week_offset = int(week_offset_str)
        except ValueError:
            week_offset = 0

        week_dates = get_week_dates(week_offset=week_offset)
        start_date = week_dates[0]['date']
        end_date = week_dates[-1]['date']
        
        appointments_this_week = db.get_appointments_by_date_range(start_date, end_date)
        booked_slots = {(apt['date'], apt['time']): apt['user_name'] for apt in appointments_this_week if apt['status'] == 'confirmed'}
        closed_days = {day['date'] for day in db.get_all_closed_days()}

        schedule_data = []
        TAIPEI_TZ = pytz.timezone('Asia/Taipei')
        now = datetime.now(TAIPEI_TZ)

        for day in week_dates:
             day['is_closed'] = day['date'] in closed_days
             all_slots = generate_time_slots(day['weekday'])
             day['slots'] = []
             for slot in all_slots:                 
                 is_available = (day['date'], slot) not in booked_slots and not day['is_closed']
                 
                 if is_available:
                     try:
                         slot_datetime = datetime.strptime(f"{day['date']} {slot}", '%Y-%m-%d %H:%M').replace(tzinfo=TAIPEI_TZ)
                         if slot_datetime <= now:
                             is_available = False
                     except ValueError:
                         pass
                 day['slots'].append({'time': slot, 'available': is_available, 'user_name': booked_slots.get((day['date'], slot))})
             schedule_data.append(day)
    else:
        user = None

    return render_template("booking.html", user=user, schedule=schedule_data, week_offset=week_offset, max_weeks=max_weeks)

@booking_bp.route("/history", methods=["GET"])
def booking_history_page():
    user = session.get('user')
    if not user:
        return render_template("booking_history.html", user=None)

    user_id = user['user_id']
    all_appointments = db.get_appointments_by_user(user_id)

    TAIPEI_TZ = pytz.timezone('Asia/Taipei')
    now = datetime.now(TAIPEI_TZ)
    weekday_names = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']

    future_appointments = []
    past_appointments = []

    for apt in all_appointments:
        try:
            apt_datetime = datetime.strptime(f"{apt['date']} {apt['time']}", '%Y-%m-%d %H:%M').replace(tzinfo=TAIPEI_TZ)
            apt['created_at'] = datetime.strptime(apt['created_at'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.utc).astimezone(TAIPEI_TZ)
            apt['formatted_date'] = apt_datetime.strftime('%Y/%m/%d')
            apt['weekday'] = weekday_names[apt_datetime.weekday()]

            if apt_datetime > now and apt['status'] == 'confirmed':
                future_appointments.append(apt)
            else:
                past_appointments.append(apt)
        except (ValueError, TypeError):
            continue
    
    future_appointments.sort(key=lambda x: (x['date'], x['time']))
    past_appointments.sort(key=lambda x: (x['date'], x['time']), reverse=True)

    return render_template(
        "booking_history.html",
        user=user,
        future_appointments=future_appointments,
        past_appointments=past_appointments
    )

@booking_bp.route("/api/book_appointment", methods=["POST"])
def api_book_appointment():
    if 'user' not in session:
        return jsonify({"status": "error", "message": "使用者未登入"}), 401

    data = request.get_json()
    date = data.get('date')
    time = data.get('time')

    if not date or not time:
        return api_response(error="預約資料不完整", status_code=400)

    user = session['user']
    success = db.add_appointment(
        user_id=user['user_id'],
        user_name=user['name'],
        date=date,
        time=time
    )

    if success:
        return api_response(data={"message": f"恭喜！您已成功預約 {date} {time} 的時段。"})
    else:
        return api_response(error=f"抱歉，{date} {time} 的時段已被預約，請選擇其他時段。", status_code=409)

@booking_bp.route("/api/cancel_my_appointment", methods=["POST"])
def api_cancel_my_appointment():
    if 'user' not in session:
        return api_response(error="使用者未登入", status_code=401)

    data = request.get_json()
    appointment_id = data.get('appointment_id')
    if not appointment_id:
        return api_response(error="缺少預約 ID", status_code=400)

    user = session['user']
    user_id = user['user_id']

    apt_to_cancel = db.get_appointment_by_id(appointment_id)
    if not apt_to_cancel or apt_to_cancel['user_id'] != user_id:
        return api_response(error="找不到此預約或權限不足", status_code=404)

    success = db.cancel_user_appointment(appointment_id, user_id)

    if success:
        return api_response(data={"message": "預約已成功取消。"})
    else:
        return api_response(error="取消失敗，請稍後再試。", status_code=500)