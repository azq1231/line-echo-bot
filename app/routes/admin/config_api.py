from flask import (
    request, jsonify, current_app
)

import database as db
from app.utils.decorators import admin_required, api_error_handler
from . import api_admin_bp

@api_admin_bp.route("/message_stats")
@admin_required
def message_stats_api():
    month = request.args.get('month')
    message_type = request.args.get('type')
    user_id = request.args.get('user')
    stats_data = db.get_message_stats(month, user_id, message_type)
    return jsonify(stats_data)

@api_admin_bp.route("/closed_days")
@admin_required
@api_error_handler
def get_closed_days_api():
    closed_days = db.get_all_closed_days()
    return jsonify({"status": "success", "closed_days": closed_days})

@api_admin_bp.route("/set_closed_day", methods=["POST"])
@admin_required
@api_error_handler
def set_closed_day_api():
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
def add_to_waiting_list_api():
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
def remove_from_waiting_list_api(item_id):
    if db.remove_from_waiting_list(item_id):
        return jsonify({"status": "success", "message": "已從備取名單移除"})
    else:
        return jsonify({"status": "error", "message": "移除失敗，找不到該項目"}), 404

@api_admin_bp.route("/remove_closed_day", methods=["POST"])
@admin_required
@api_error_handler
def remove_closed_day_api():
    data = request.get_json()
    date = data.get('date')
    if db.remove_closed_day(date):
        return jsonify({"status": "success", "message": "已移除休診設定"})
    else:
        return jsonify({"status": "error", "message": "未找到休診記錄"}), 404

@api_admin_bp.route("/slots", methods=["POST"])
@admin_required
@api_error_handler
def api_add_slot_api():
    data = request.get_json()
    # 修正：將 type 作為位置參數傳遞
    slot_type = data.get('type', 'consultation')
    if db.add_available_slot(data['weekday'], data['start_time'], data['end_time'], data.get('note'), slot_type):
        return jsonify({"status": "success", "message": "時段已新增"})
    else:
        return jsonify({"status": "error", "message": "新增失敗，該時段可能已存在"}), 409

@api_admin_bp.route("/slots/<int:slot_id>", methods=["PUT"])
@admin_required
@api_error_handler
def api_update_slot(slot_id):
    data = request.get_json()
    # 修正：將 type 作為位置參數傳遞
    slot_type = data.get('type', 'consultation')
    if db.update_available_slot(slot_id, data['weekday'], data['start_time'], data['end_time'], data['active'], data.get('note'), slot_type):
        return jsonify({"status": "success", "message": "時段已更新"})
    else:
        return jsonify({"status": "error", "message": "更新失敗"}), 500

@api_admin_bp.route("/slots/<int:slot_id>", methods=["DELETE"])
@admin_required
@api_error_handler
def api_delete_slot_api(slot_id):
    if db.delete_available_slot(slot_id):
        return jsonify({"status": "success", "message": "時段已刪除"})
    else:
        return jsonify({"status": "error", "message": "刪除失敗"}), 500

@api_admin_bp.route("/slots/copy", methods=["POST"])
@admin_required
@api_error_handler
def api_copy_slots_api():
    data = request.get_json()
    source_weekday = data.get('source_weekday')
    target_weekdays = data.get('target_weekdays')
    types = data.get('types')  # 獲取類型參數
    
    if not source_weekday or not target_weekdays:
        return jsonify({"status": "error", "message": "來源或目標星期未選擇"}), 400
        
    inserted_count, _ = db.copy_slots(int(source_weekday), target_weekdays, types)
    if inserted_count > 0:
        return jsonify({"status": "success", "message": f"已成功複製設定，共新增 {inserted_count} 個時段。"})
    else:
        return jsonify({"status": "error", "message": "複製失敗，請確認來源星期有設定時段。"}), 400

@api_admin_bp.route("/configs")
@admin_required
@api_error_handler
def get_config_api_admin():
    configs = db.get_all_configs()
    return jsonify({"status": "success", "configs": configs})

@api_admin_bp.route("/set_config", methods=["POST"])
@admin_required
@api_error_handler
def set_config_api_admin():
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