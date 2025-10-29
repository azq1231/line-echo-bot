from flask import (
    request, jsonify, session
)
import uuid

import database as db

# Import from our new util modules
from app.utils.decorators import admin_required, api_error_handler
from . import api_admin_bp

@api_admin_bp.route("/update_user_name", methods=["POST"])
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

@api_admin_bp.route("/update_user_zhuyin", methods=["POST"])
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

@api_admin_bp.route("/update_user_phone", methods=["POST"])
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

@api_admin_bp.route("/update_user_address", methods=["POST"])
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

@api_admin_bp.route("/generate_zhuyin/<user_id>", methods=["POST"])
@admin_required
def generate_zhuyin_route(user_id):
    new_zhuyin = db.generate_and_save_zhuyin(user_id)
    if new_zhuyin is not None:
        return jsonify({"status": "success", "zhuyin": new_zhuyin})
    else:
        return jsonify({"status": "error", "message": "生成失败"}), 404

@api_admin_bp.route('/users', methods=['GET'])
@admin_required
@api_error_handler
def api_get_users():
    users = db.get_all_users()
    current_admin_id = session.get('user', {}).get('user_id')
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
    if user_id == session.get('user', {}).get('user_id'):
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