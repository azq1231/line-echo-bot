from flask import (
    request, jsonify
)

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