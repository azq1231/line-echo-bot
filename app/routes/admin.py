from flask import (
    Blueprint, request, jsonify, render_template, flash, redirect, url_for,
    Response, session, send_from_directory, current_app
)
from datetime import datetime
from collections import defaultdict
import json

import database as db

# Import from our new util modules
from app.utils.decorators import admin_required, api_error_handler
from app.utils.helpers import get_vue_assets, get_week_dates, generate_time_slots
from app.utils.line_api import user_avatar, refresh_user_profile
from app.scheduler.jobs import _do_send_reminders

# Blueprint for rendering admin HTML pages
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
# Blueprint for admin-related APIs, maintaining the original URL structure
api_admin_bp = Blueprint('api_admin', __name__, url_prefix='/api/admin')

# ============ WEB 路由 ============

@admin_bp.route("/")
@admin_required
def admin_home():
    return redirect(url_for('admin.users_vue_page'))

@admin_bp.route("/users_vue")
@admin_required
def users_vue_page():
    js_path, css_path = get_vue_assets('users.html')
    return render_template("admin_users_vue.html", js_path=js_path, css_path=css_path, user=session.get('user'))

@admin_bp.route("/schedule")
@admin_required
def schedule():
    user = session.get('user')
    if db.get_config('feature_schedule_enabled') == 'false':
        return "Feature disabled", 404
    return render_template("schedule.html", user=user)

@admin_bp.route("/appointments")
@admin_required
def appointments_page():
    js_path, css_path = get_vue_assets('index.html')
    return render_template("admin_appointments_vue.html", js_path=js_path, css_path=css_path, user=session.get('user'))

@admin_bp.route("/closed_days")
@admin_required
def closed_days_page():
    user = session.get('user')
    if db.get_config('feature_closed_days_enabled') == 'false':
        return "Feature disabled", 404
    return render_template("closed_days.html", user=user)

@admin_bp.route("/stats")
@admin_required
def stats_page():
    user = session.get('user')
    TAIPEI_TZ = current_app.config['TAIPEI_TZ']
    current_month = request.args.get('month', datetime.now(TAIPEI_TZ).strftime('%Y-%m'))
    message_type = request.args.get('type', '')
    user_id = request.args.get('user', '')
    all_users = db.get_all_users()
    stats_data = db.get_message_stats(
        month=current_month,
        message_type=message_type or None,
        user_id=user_id or None
    )
    return render_template('stats.html',
                         user=user,
                         stats=stats_data,
                         current_month=current_month,
                         all_users=all_users,
                         current_user_id=user_id,
                         current_type=message_type,
                         stats_data_json=json.dumps(stats_data))

@admin_bp.route("/configs")
@admin_required
def configs_page():
    TAIPEI_TZ = current_app.config['TAIPEI_TZ'] # Access TAIPEI_TZ from current_app.config
    all_configs_list = db.get_all_configs()
    configs_dict = {c['key']: c['value'] for c in all_configs_list}
    
    configs_dict.setdefault('booking_window_weeks', '2')
    configs_dict.setdefault('allow_user_deletion', 'false')
    configs_dict.setdefault('feature_schedule_enabled', 'true')
    configs_dict.setdefault('feature_closed_days_enabled', 'true')
    configs_dict.setdefault('feature_booking_enabled', 'true')
    configs_dict.setdefault('auto_reminder_daily_enabled', 'false')
    configs_dict.setdefault('auto_reminder_daily_time', '09:00')
    configs_dict.setdefault('auto_reminder_weekly_enabled', 'false')
    configs_dict.setdefault('auto_reminder_weekly_day', 'sun')
    configs_dict.setdefault('auto_reminder_weekly_time', '21:00')
    default_reminder_template = (
        "您好，提醒您{date_keyword} ({date}) 有預約以下時段：\n\n"
        "{time_slots}\n\n"
        "如果需要更改或取消，請與我們聯繫，謝謝。")
    user = session.get('user') # Get user after TAIPEI_TZ is defined
    configs_dict.setdefault('message_template_reminder', default_reminder_template)

    admins = [u for u in db.get_all_users() if u.get('is_admin')]
    return render_template("configs.html", user=user, configs=configs_dict, admins=admins)

@admin_bp.route('/set_admin_status', methods=['POST'])
@admin_required
def set_admin_status():
    user_id_to_change = request.form.get('user_id')
    action = request.form.get('action')

    if not user_id_to_change or not action:
        flash('缺少 User ID 或操作類型。', 'danger')
        return redirect(url_for('admin.configs_page'))

    current_user_id = session.get('user', {}).get('user_id')
    if user_id_to_change == current_user_id:
        flash('無法修改自己的管理員權限。', 'warning')
        return redirect(url_for('admin.configs_page'))

    user_to_modify = db.get_user_by_id(user_id_to_change)
    if not user_to_modify:
        flash(f'找不到 User ID 為 "{user_id_to_change}" 的使用者。請確認該使用者至少與機器人互動過一次。', 'danger')
        return redirect(url_for('admin.configs_page'))

    is_admin = action == 'add'
    
    if db.update_user_admin_status(user_id_to_change, is_admin):
        action_text = "新增" if is_admin else "移除"
        flash(f'成功{action_text}使用者 {user_to_modify["name"]} 的管理員權限。', 'success')
    else:
        flash('更新權限時發生錯誤。', 'danger')

    return redirect(url_for('admin.configs_page'))

@admin_bp.route("/settings/slots")
@admin_required
def slots_settings_page():
    user = session.get('user')
    all_slots = db.get_all_available_slots()
    
    slots_by_weekday = {i: [] for i in range(1, 6)}
    for slot in all_slots:
        if slot['weekday'] in slots_by_weekday:
            slots_by_weekday[slot['weekday']].append(slot)
            
    return render_template("slots_settings.html", user=user, slots_by_weekday=slots_by_weekday)

@admin_bp.route("/update_user_name", methods=["POST"])
@admin_required
def update_user_name():
    data = request.get_json()
    user_id = data.get("user_id")
    new_name = data.get("name")
    
    if not user_id or not new_name:
        return jsonify({"status": "error", "message": "缺少必要欄位"}), 400
    
    if db.update_user_name(user_id, new_name):
        return jsonify({"status": "success", "message": f"已更新姓名為：{new_name}"})
    else:
        return jsonify({"status": "error", "message": "找不到用戶"}), 404

@admin_bp.route("/update_user_zhuyin", methods=["POST"])
@admin_required
def update_user_zhuyin_route():
    data = request.get_json()
    user_id = data.get("user_id")
    zhuyin = data.get("zhuyin")
    
    if not user_id or zhuyin is None:
        return jsonify({"status": "error", "message": "缺少必要参数"}), 400

    if db.update_user_zhuyin(user_id, zhuyin):
        return jsonify({"status": "success", "message": "注音已更新"})
    else:
        return jsonify({"status": "error", "message": "更新失败"}), 500

@admin_bp.route("/update_user_phone", methods=["POST"])
@admin_required
def update_user_phone_route():
    data = request.get_json()
    user_id = data.get("user_id")
    phone = data.get("phone")
    field = data.get("field", 'phone')

    if not user_id or phone is None:
        return jsonify({"status": "error", "message": "缺少使用者 ID 或電話號碼"}), 400

    if db.update_user_phone_field(user_id, field, phone):
        return jsonify({"status": "success", "message": "電話號碼已更新"})
    else:
        return jsonify({"status": "error", "message": "更新失敗"}), 500

@admin_bp.route("/update_user_address", methods=["POST"])
@admin_required
def update_user_address_route():
    data = request.get_json()
    user_id = data.get("user_id")
    address = data.get("address")

    if not user_id or address is None:
        return jsonify({"status": "error", "message": "缺少使用者 ID 或地址"}), 400

    if db.update_user_address(user_id, address):
        return jsonify({"status": "success", "message": "地址已更新"})
    else:
        return jsonify({"status": "error", "message": "更新失敗"}), 500

@admin_bp.route("/generate_zhuyin/<user_id>", methods=["POST"])
@admin_required
def generate_zhuyin_route(user_id):
    new_zhuyin = db.generate_and_save_zhuyin(user_id)
    if new_zhuyin is not None:
        return jsonify({"status": "success", "zhuyin": new_zhuyin})
    else:
        return jsonify({"status": "error", "message": "生成失败"}), 404

# ============ 後台 API (JSON) ============

@api_admin_bp.route("/message_stats")
@admin_required
def message_stats_api():
    month = request.args.get('month')
    message_type = request.args.get('type')
    user_id = request.args.get('user')
    stats_data = db.get_message_stats(month, user_id, message_type)
    return jsonify(stats_data)

@api_admin_bp.route('/users', methods=['GET'])
@admin_required
@api_error_handler
def api_get_users():
    users = db.get_all_users()
    current_admin_id = session['user']['user_id'] if 'user' in session else None
    users_data = [
        {
            "id": str(user.get('user_id', '')) if user.get('user_id') is not None else '',
            "name": user.get('name', ''),
            "line_user_id": str(user.get('user_id', '')) if user.get('user_id') is not None else '',
            "is_admin": user.get('is_admin', False),
            "zhuyin": user.get('zhuyin', ''),
            "phone": user.get('phone', ''),
            "phone2": user.get('phone2', '')
        } 
        for user in users
    ]
    allow_deletion = db.get_config('allow_user_deletion', 'false') == 'true'
    return jsonify({"status": "success", "users": users_data, "current_admin_id": current_admin_id, "allow_user_deletion": allow_deletion})

@api_admin_bp.route('/users/<string:user_id>/toggle_admin', methods=['POST'])
@admin_required
@api_error_handler
def api_toggle_admin(user_id):
    if user_id == (session['user']['user_id'] if 'user' in session else None):
        return jsonify({"status": "error", "message": "無法修改自己的管理員權限。"}), 403
    user_to_modify = db.get_user_by_id(user_id)
    if not user_to_modify:
        return jsonify({"status": "error", "message": "找不到該使用者。"}), 404
    new_admin_status = not user_to_modify.get('is_admin', False)
    success = db.update_user_admin_status(user_id, new_admin_status)
    if success:
        action = "授予" if new_admin_status else "移除"
        return jsonify({"status": "success", "message": f"已成功為使用者 {user_to_modify['name']} {action}管理員權限。", "new_status": new_admin_status})
    else:
        return jsonify({"status": "error", "message": "更新管理員權限失敗。"}), 500

@api_admin_bp.route('/users/add_manual', methods=['POST'])
@admin_required
@api_error_handler
def api_add_manual_user():
    data = request.get_json()
    name = data.get('name')
    if not name or not name.strip():
        return jsonify({"status": "error", "message": "用戶名稱不能為空。"}), 400
    import uuid
    user_id = f"manual_{uuid.uuid4()}"
    new_user = db.add_manual_user(user_id, name.strip())
    if new_user:
        formatted_user = {
            "id": str(new_user.get('user_id', '')) if new_user.get('user_id') is not None else '',
            "name": new_user.get('name', ''),
            "line_user_id": str(new_user.get('user_id', '')) if new_user.get('user_id') is not None else '',
            "is_admin": new_user.get('is_admin', False),
            "zhuyin": new_user.get('zhuyin', ''),
            "phone": new_user.get('phone', ''),
            "phone2": new_user.get('phone2', '')
        }
        return jsonify({"status": "success", "message": "臨時用戶已成功新增。", "user": formatted_user})
    else:
        return jsonify({"status": "error", "message": "新增臨時用戶時發生錯誤。"}), 500

@api_admin_bp.route('/users/merge', methods=['POST'])
@admin_required
@api_error_handler
def api_merge_users():
    data = request.get_json()
    source_user_id = data.get('source_user_id')
    target_user_id = data.get('target_user_id')
    if not source_user_id or not target_user_id:
        return jsonify({"status": "error", "message": "缺少來源或目標用戶 ID。"}), 400
    if source_user_id == target_user_id:
        return jsonify({"status": "error", "message": "來源和目標用戶不能相同。"}), 400
    success = db.merge_users(source_user_id, target_user_id)
    if success:
        return jsonify({"status": "success", "message": "用戶資料已成功合併。"})
    else:
        return jsonify({"status": "error", "message": "合併用戶時發生錯誤，請檢查後台日誌。"}), 500

@api_admin_bp.route('/users/<string:user_id>', methods=['DELETE'])
@admin_required
@api_error_handler
def api_delete_user(user_id):
    if db.delete_user(user_id):
        return jsonify({"status": "success", "message": "用戶已成功刪除。"})
    else:
        return jsonify({"status": "error", "message": "刪除用戶失敗，找不到該用戶或有關聯資料。"}), 500

@api_admin_bp.route("/get_week_appointments")
@api_error_handler
def get_week_appointments():
    week_offset = int(request.args.get('offset', 0))
    week_dates = get_week_dates(week_offset)
    start_date = week_dates[0]['date']
    end_date = week_dates[-1]['date']
    all_users_raw = db.get_all_users()
    all_users = []
    for user in all_users_raw:
        processed_user = user.copy()
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
        time_slots = generate_time_slots(weekday)
        appointments = db.get_appointments_by_date_range(date_str, date_str)
        appointments_map = {apt['time']: apt for apt in appointments if apt['status'] == 'confirmed'}
        day_appointments = {}
        for time_slot in time_slots:
            apt = appointments_map.get(time_slot)
            day_appointments[time_slot] = {
                'id': apt.get('id') if apt else None,
                'reply_status': apt.get('reply_status', '未回覆') if apt else '未回覆',
                'last_reply': apt.get('last_reply', '') if apt else '',
                'user_name': apt.get('user_name', '') if apt else '',
                'user_id': str(apt.get('user_id', '')) if apt and apt.get('user_id') is not None else ''
            }
        week_schedule[date_str] = {
            'date_info': date_info,
            'appointments': day_appointments,
            'is_closed': date_str in all_closed_days,
            'waiting_list': waiting_lists.get(date_str, [])
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
    date = data.get('date')
    time = data.get('time')
    user_name = data.get('user_name')
    user_id = data.get('user_id', '')
    waiting_list_item_id = data.get('waiting_list_item_id')
    db.cancel_appointment(date, time)
    if user_name and user_id:
        new_appointment_id = db.add_appointment(user_id, user_name, date, time)
        if new_appointment_id:
            new_appointment = db.get_appointment_by_id(new_appointment_id)
            return jsonify({"status": "success", "message": "預約已儲存", "appointment": new_appointment})
    if waiting_list_item_id is not None:
        try:
            db.remove_from_waiting_list(int(waiting_list_item_id))
        except ValueError:
            current_app.logger.warning(f"警告：無法將 waiting_list_item_id '{waiting_list_item_id}' 轉換為整數。")
    return jsonify({"status": "success", "message": "預約已更新"})

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
    sent_count, failed_count = _do_send_reminders(appointments, reminder_type)
    return jsonify({"status": "success", "sent_count": sent_count, "failed_count": failed_count})

@api_admin_bp.route("/appointments/<int:appointment_id>/confirm_reply", methods=["POST"])
@admin_required
@api_error_handler
def confirm_appointment_reply_api(appointment_id): # Renamed to avoid conflict with main's confirm_appointment_reply
    TAIPEI_TZ = current_app.config['TAIPEI_TZ']
    success = db.update_appointment_reply_status(appointment_id, '已確認', confirm_time=datetime.now(TAIPEI_TZ))
    if success:
        return jsonify({"status": "success", "message": "已成功確認回覆。"})
    else:
        return jsonify({"status": "error", "message": "找不到該預約或更新失敗。"}), 404

@api_admin_bp.route("/appointments/<int:appointment_id>/reply_status", methods=["PUT"])
@admin_required
@api_error_handler
def update_appointment_reply_status_manual_api(appointment_id): # Renamed to avoid conflict with main's update_appointment_reply_status_manual
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
def confirm_user_day_replies_api(): # Renamed to avoid conflict with main's confirm_user_day_replies
    data = request.get_json()
    user_id = data.get('user_id')
    date = data.get('date')
    if not user_id or not date:
        return jsonify({"status": "error", "message": "缺少 user_id 或 date。"}), 400
    db.update_user_day_reply_status(user_id, date, '已確認')
    return jsonify({"status": "success", "message": "已成功確認該用戶當日所有預約。"})

@api_admin_bp.route("/closed_days")
@admin_required
@api_error_handler
def get_closed_days_api(): # Renamed to avoid conflict with main's get_closed_days
    closed_days = db.get_all_closed_days()
    return jsonify({"status": "success", "closed_days": closed_days})

@api_admin_bp.route("/set_closed_day", methods=["POST"])
@admin_required
@api_error_handler
def set_closed_day_api(): # Renamed to avoid conflict with main's set_closed_day
    data = request.get_json()
    date = data.get('date')
    reason = data.get('reason', '休診')
    if not date:
        return jsonify({"status": "error", "message": "缺少日期"}), 400
    cancelled_count = db.set_closed_day(date, reason)
    return jsonify({"status": "success", "message": f"已設定休診，取消了 {cancelled_count} 個預約"})

@api_admin_bp.route("/waiting_list", methods=["POST"])
@admin_required
@api_error_handler
def add_to_waiting_list_api(): # Renamed to avoid conflict with main's add_to_waiting_list
    data = request.get_json()
    date = data.get('date')
    user_id = data.get('user_id')
    user_name = data.get('user_name')
    if not all([date, user_id, user_name]):
        return jsonify({"status": "error", "message": "缺少必要參數"}), 400
    new_item = db.add_to_waiting_list(date, user_id, user_name)
    if new_item:
        return jsonify({"status": "success", "message": "已新增至備取名單", "item": new_item})
    else:
        return jsonify({"status": "error", "message": "新增備取失敗"}), 500

@api_admin_bp.route("/waiting_list/<int:item_id>", methods=["DELETE"])
@admin_required
@api_error_handler
def remove_from_waiting_list_api(item_id): # Renamed to avoid conflict with main's remove_from_waiting_list
    if db.remove_from_waiting_list(item_id):
        return jsonify({"status": "success", "message": "已從備取名單移除"})
    else:
        return jsonify({"status": "error", "message": "移除失敗，找不到該項目"}), 404

@api_admin_bp.route("/remove_closed_day", methods=["POST"])
@admin_required
@api_error_handler
def remove_closed_day_api(): # Renamed to avoid conflict with main's remove_closed_day
    data = request.get_json()
    date = data.get('date')
    if db.remove_closed_day(date):
        return jsonify({"status": "success", "message": "已移除休診設定"})
    else:
        return jsonify({"status": "error", "message": "未找到休診記錄"}), 404

@api_admin_bp.route("/slots", methods=["POST"])
@admin_required
@api_error_handler
def api_add_slot_api(): # Renamed to avoid conflict with main's api_add_slot
    data = request.get_json()
    if db.add_available_slot(data['weekday'], data['start_time'], data['end_time'], data.get('note')):
        return jsonify({"status": "success", "message": "時段已新增"})
    else:
        return jsonify({"status": "error", "message": "新增失敗，該時段可能已存在"}), 409

@api_admin_bp.route("/slots/<int:slot_id>", methods=["PUT"])
@admin_required
@api_error_handler
def api_update_slot(slot_id):
    data = request.get_json()
    if db.update_available_slot(slot_id, data['weekday'], data['start_time'], data['end_time'], data['active'], data.get('note')):
        return jsonify({"status": "success", "message": "時段已更新"})
    else:
        return jsonify({"status": "error", "message": "更新失敗"}), 500

@api_admin_bp.route("/slots/<int:slot_id>", methods=["DELETE"])
@admin_required
@api_error_handler
def api_delete_slot_api(slot_id): # Renamed to avoid conflict with main's api_delete_slot
    if db.delete_available_slot(slot_id):
        return jsonify({"status": "success", "message": "時段已刪除"})
    else:
        return jsonify({"status": "error", "message": "刪除失敗"}), 500

@api_admin_bp.route("/slots/copy", methods=["POST"])
@admin_required
@api_error_handler
def api_copy_slots_api(): # Renamed to avoid conflict with main's api_copy_slots
    data = request.get_json()
    source_weekday = data.get('source_weekday')
    target_weekdays = data.get('target_weekdays')
    if not source_weekday or not target_weekdays:
        return jsonify({"status": "error", "message": "來源或目標星期未選擇"}), 400
    inserted_count, _ = db.copy_slots(int(source_weekday), target_weekdays)
    if inserted_count > 0:
        return jsonify({"status": "success", "message": f"已成功複製設定，共新增 {inserted_count} 個時段。"})
    else:
        return jsonify({"status": "error", "message": "複製失敗，請確認來源星期有設定時段。"}), 400

@api_admin_bp.route("/configs")
@admin_required
@api_error_handler
def get_config_api_admin(): # Renamed to avoid conflict with main's get_config_api
    configs = db.get_all_configs()
    return jsonify({"status": "success", "configs": configs})

@api_admin_bp.route("/set_config", methods=["POST"])
@admin_required
@api_error_handler
def set_config_api_admin(): # Renamed to avoid conflict with main's set_config_api
    data = request.get_json()
    key = data.get('key')
    value = data.get('value')
    description = data.get('description', '')
    if not key or value is None:
        return jsonify({"status": "error", "message": "缺少必要参数"}), 400
    if key == 'booking_window_weeks' and str(value) not in ['2', '4']:
        return jsonify({"status": "error", "message": "预约窗口只能设置为2周或4周"}), 400
    updated = db.set_config(key, str(value), description)
    if updated:
        return jsonify({"status": "success", "message": "配置已更新"})
    else:
        return jsonify({"status": "error", "message": "更新失败"}), 500

# ============ 排程管理 API ============

@api_admin_bp.route("/schedule", methods=["POST"])
@admin_required
@api_error_handler
def add_schedule_route():
    data = request.get_json()
    user_id = data.get("user_id")
    user_name = data.get("user_name")
    send_time = data.get("send_time")
    message = data.get("message")
    
    if not all([user_id, send_time, message]):
        return jsonify({"status": "error", "message": "缺少必要欄位"}), 400
    
    if db.add_schedule(user_id, user_name, send_time, message):
        return jsonify({"status": "success", "message": "排程已新增"})
    else:
        return jsonify({"status": "error", "message": "新增排程失敗"}), 500

@api_admin_bp.route("/schedule/list")
@admin_required
@api_error_handler
def list_schedules():
    schedules = db.get_all_schedules()
    return jsonify({"schedules": schedules, "count": len(schedules)})

@api_admin_bp.route("/schedule/<int:schedule_id>", methods=["DELETE"])
@admin_required
@api_error_handler
def delete_schedule_route(schedule_id):
    if db.delete_schedule(schedule_id):
        return jsonify({"status": "success", "message": "排程已刪除"})
    else:
        return jsonify({"status": "error", "message": "刪除失敗，找不到該排程"}), 404