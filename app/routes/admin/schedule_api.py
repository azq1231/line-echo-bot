from flask import (
    request, jsonify, current_app
)
from datetime import datetime
import pytz

import database as db
from app.utils.decorators import admin_required, api_error_handler
from . import api_admin_bp

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

    # --- 新增時區處理邏輯 ---
    TAIPEI_TZ = current_app.config['TAIPEI_TZ']
    try:
        # 將前端傳來的時間字串轉換為 naive datetime 物件
        naive_dt = datetime.fromisoformat(send_time)
        # 附加台北時區資訊，使其成為 aware datetime 物件，然後轉換為 UTC
        utc_dt = TAIPEI_TZ.localize(naive_dt).astimezone(pytz.utc)
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "無效的時間格式"}), 400

    if db.add_schedule(user_id, user_name, utc_dt, message):
        return jsonify({"status": "success", "message": "排程已新增"})
    else:
        return jsonify({"status": "error", "message": "新增排程失敗"}), 500

@api_admin_bp.route("/schedule/list")
@admin_required
@api_error_handler
def list_schedules():
    schedules = db.get_all_schedules()
    return jsonify({"schedules": schedules, "count": len(schedules)})

@api_admin_bp.route("/schedule/<int:schedule_id>", methods=["PUT"])
@admin_required
@api_error_handler
def update_schedule_route(schedule_id):
    """更新特定排程的資訊，目前僅支援更新發送時間"""
    data = request.get_json()
    new_send_time = data.get("send_time")

    if not new_send_time:
        return jsonify({"status": "error", "message": "缺少新的發送時間"}), 400

    # --- 時區處理 ---
    TAIPEI_TZ = current_app.config['TAIPEI_TZ']
    try:
        naive_dt = datetime.fromisoformat(new_send_time)
        # 附加台北時區資訊，使其成為 aware datetime 物件，然後轉換為 UTC
        utc_dt = TAIPEI_TZ.localize(naive_dt).astimezone(pytz.utc)
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "無效的時間格式"}), 400

    if db.update_schedule_send_time(schedule_id, utc_dt):
        return jsonify({"status": "success", "message": "排程時間已更新"})
    else:
        return jsonify({"status": "error", "message": "更新失敗，可能排程不存在、狀態不符或時間格式錯誤"}), 404

@api_admin_bp.route("/schedule/<int:schedule_id>", methods=["DELETE"])
@admin_required
@api_error_handler
def delete_schedule_route(schedule_id):
    if db.delete_schedule(schedule_id):
        return jsonify({"status": "success", "message": "排程已刪除"})
    else:
        return jsonify({"status": "error", "message": "刪除失敗，找不到該排程"}), 404