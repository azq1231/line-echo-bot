from flask import (
    request, jsonify, current_app
)
import json
from datetime import datetime

import database as db
from app.utils.decorators import admin_required, api_error_handler
from app.utils.helpers import get_week_dates, generate_time_slots
from app.scheduler.jobs import _do_send_reminders # 導入新的提醒函式
from . import api_admin_bp

def _truncate_name(name, limit=7):
    """如果名稱長度超過限制，則截斷。"""
    if name and len(name) > limit:
        return name[:limit]
    return name

@api_admin_bp.route("/get_week_appointments")
@api_error_handler
def get_week_appointments():
    week_offset = int(request.args.get('offset', 0))
    week_dates = get_week_dates(week_offset)
    
    # 取得所有用戶並預先截斷名稱
    all_users_raw = db.get_all_users()
    all_users = []
    for user in all_users_raw:
        processed_user = user.copy()
        # 在此處截斷用戶列表中的名稱
        if 'name' in processed_user and processed_user['name']:
            processed_user['name'] = _truncate_name(processed_user['name'])
        processed_user['user_id'] = str(user.get('user_id', '')) if user.get('user_id') is not None else ''
        processed_user['line_user_id'] = str(user.get('user_id', '')) if user.get('user_id') is not None else ''
        processed_user['id'] = processed_user['user_id']
        all_users.append(processed_user)

    week_schedule = {}
    waiting_lists = db.get_waiting_lists_by_date_range(week_dates[0]['date'], week_dates[-1]['date'])
    all_closed_days = {day['date'] for day in db.get_all_closed_days()}
    
    for date_info in week_dates:
        date_str = date_info['date']
        weekday = date_info['weekday']
        
        time_slots_consultation = generate_time_slots(weekday, 'consultation')
        time_slots_massage = generate_time_slots(weekday, 'massage')
        
        appointments = db.get_appointments_by_date_range(date_str, date_str)
        
        # 根據 type 區分預約
        appointments_map_consultation = {apt['time']: apt for apt in appointments if apt['status'] == 'confirmed' and apt.get('type', 'consultation') == 'consultation'}
        appointments_map_massage = {apt['time']: apt for apt in appointments if apt['status'] == 'confirmed' and apt.get('type') == 'massage'}
        
        def process_appointments(time_slots, appointments_map):
            day_appointments = {}
            for time_slot in time_slots:
                apt = appointments_map.get(time_slot)
                
                last_reply_obj = None
                if apt and apt.get('last_reply'):
                    try:
                        last_reply_obj = json.loads(apt['last_reply'])
                    except (json.JSONDecodeError, TypeError):
                        last_reply_obj = None

                day_appointments[time_slot] = {
                    'id': apt.get('id') if apt else None,
                    'reply_status': apt.get('reply_status', '未回覆') if apt else '未回覆',
                    'last_reply': last_reply_obj,
                    'user_name': _truncate_name(apt.get('user_name', '')) if apt else '',
                    'user_id': str(apt.get('user_id', '')) if apt and apt.get('user_id') is not None else ''
                }
            return day_appointments

        day_appointments_consultation = process_appointments(time_slots_consultation, appointments_map_consultation)
        day_appointments_massage = process_appointments(time_slots_massage, appointments_map_massage)
        
        # 取得並處理備取名單
        day_waiting_list = waiting_lists.get(date_str, [])
        for item in day_waiting_list:
            item['user_name'] = _truncate_name(item.get('user_name'))

        week_schedule[date_str] = {
            'date_info': date_info,
            'appointments': day_appointments_consultation, # 為了相容性，預設 appointments 欄位放看診
            'appointments_massage': day_appointments_massage, # 新增推拿欄位
            'is_closed': date_str in all_closed_days,
            'waiting_list': day_waiting_list
        }
        
    response_data = {
        'week_schedule': week_schedule,
        'users': all_users,
        'week_offset': week_offset
    }
    return jsonify(response_data)

@api_admin_bp.route("/save_appointment", methods=["POST"])
@admin_required
@api_error_handler
def save_appointment():
    data = request.get_json()
    print(f"[DEBUG] save_appointment data: {data}")
    date = data.get('date')
    time = data.get('time')
    user_name = data.get('user_name')
    user_id = data.get('user_id', '')
    waiting_list_item_id = data.get('waiting_list_item_id')
    type = data.get('type', 'consultation') # 預設為看診

    # 1. 先刪除該時段的現有預約，為新增或清空做準備
    # 使用 type 參數確保只刪除正確類型的預約
    db.cancel_appointment(date, time, type) 

    # 2. 如果提供了 user_id，代表是「新增」或「更新」操作
    if user_id:
        new_appointment_id = db.add_appointment(
            user_id=user_id, 
            date=date, 
            time=time, 
            user_name=user_name, # 將 user_name 作為備用名稱傳遞
            type=type
        )
        print(f"[DEBUG] new_appointment_id: {new_appointment_id}")
        if new_appointment_id:
            # 如果是從備取名單拖曳過來的，則從備取名單中移除
            if waiting_list_item_id is not None:
                try:
                    db.remove_from_waiting_list(int(waiting_list_item_id))
                except (ValueError, TypeError):
                    current_app.logger.warning(f"警告：無法將 waiting_list_item_id '{waiting_list_item_id}' 轉換為整數。")
            new_appointment = db.get_appointment_by_id(new_appointment_id)
            return jsonify({"status": "success", "message": "預約已儲存", "appointment": new_appointment})
        else:
            print("[DEBUG] add_appointment returned None")
            return jsonify({"status": "error", "message": "預約儲存失敗，該時段可能已被佔用或資料庫錯誤。"}), 500

    # 3. 如果沒有提供 user_id，代表是「取消」操作，前面已經刪除完畢，直接回傳成功即可
    return jsonify({"status": "success", "message": "預約已清空"})

@api_admin_bp.route("/send_appointment_reminders", methods=["POST"])
@admin_required
@api_error_handler
def send_appointment_reminders():
    data = request.get_json()
    send_type = data.get('type', 'week')
    target_date = data.get('date', '')
    offset = data.get('offset', 0)
    if send_type == 'day' and target_date:
        appointments = db.get_appointments_by_date_range(target_date, target_date)
        reminder_type = 'day'
    else:
        week_dates = get_week_dates(week_offset=offset)
        start_date = week_dates[0]['date']
        end_date = week_dates[-1]['date']
        appointments = db.get_appointments_by_date_range(start_date, end_date)
        reminder_type = 'week'
    appointments = [apt for apt in appointments if apt['status'] == 'confirmed']
    # 直接使用 _do_send_reminders，並傳入當前的 app 物件
    sent_count, failed_count = _do_send_reminders(current_app, appointments, reminder_type)
    return jsonify({"status": "success", "sent_count": sent_count, "failed_count": failed_count})

@api_admin_bp.route("/appointments/<int:appointment_id>/confirm_reply", methods=["POST"])
@admin_required
@api_error_handler
def confirm_appointment_reply_api(appointment_id):
    TAIPEI_TZ = current_app.config['TAIPEI_TZ']
    
    # 獲取當前的預約資料
    appointment = db.get_appointment_by_id(appointment_id)
    if not appointment:
        return jsonify({"status": "error", "message": "找不到該預約。"}), 404

    new_last_reply_str = appointment.get('last_reply')
    # 檢查 last_reply 是否為有效的 JSON 字串
    if new_last_reply_str:
        try:
            last_reply_obj = json.loads(new_last_reply_str)
            if isinstance(last_reply_obj, dict):
                last_reply_obj['confirmed'] = True
                new_last_reply_str = json.dumps(last_reply_obj, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            # 如果解析失敗，保持原樣，只更新狀態
            pass

    success = db.update_appointment_reply_status(appointment_id, '已確認', last_reply=new_last_reply_str, confirm_time=datetime.now(TAIPEI_TZ))
    if success:
        return jsonify({"status": "success", "message": "已成功確認回覆。"})
    else:
        return jsonify({"status": "error", "message": "找不到該預約或更新失敗。"}), 404

@api_admin_bp.route("/appointments/<int:appointment_id>/reply_status", methods=["PUT"])
@admin_required
@api_error_handler
def update_appointment_reply_status_manual_api(appointment_id):
    data = request.get_json()
    new_status = data.get('status')
    if not new_status or new_status not in ['未回覆', '已回覆', '已確認']:
        return jsonify({"status": "error", "message": "無效的狀態值。"}), 400
    TAIPEI_TZ = current_app.config['TAIPEI_TZ']
    success = db.update_appointment_reply_status(appointment_id, new_status, confirm_time=datetime.now(TAIPEI_TZ) if new_status == '已確認' else None)
    if success:
        return jsonify({"status": "success", "message": "回覆狀態已更新。"})
    else:
        return jsonify({"status": "error", "message": "找不到該預約或更新失敗。"}), 404

@api_admin_bp.route("/confirm_user_day_replies", methods=["POST"])
@admin_required
@api_error_handler
def confirm_user_day_replies_api():
    data = request.get_json()
    user_id = data.get('user_id')
    date = data.get('date')
    if not user_id or not date:
        return jsonify({"status": "error", "message": "缺少 user_id 或 date。"}), 400
    db.update_user_day_reply_status(user_id, date, '已確認')
    return jsonify({"status": "success", "message": "已成功確認該用戶當日所有預約。"})