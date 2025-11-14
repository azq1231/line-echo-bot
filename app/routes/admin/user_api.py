from flask import (
    request, jsonify, session
)
import re
import uuid

import database as db

# Import from our new util modules
from app.utils.decorators import admin_required, api_error_handler
from . import api_admin_bp

@api_admin_bp.route("/update_user_field", methods=["POST"])
@admin_required
@api_error_handler
def update_user_field():
    """通用API，用於更新用戶的單一欄位（如 name, zhuyin, phone, phone2, address）。"""
    data = request.get_json()
    user_id = data.get("user_id")
    field = data.get("field")
    value = data.get("value")
    
    if not all([user_id, field, value is not None]):
        return jsonify({"status": "error", "message": "缺少 user_id, field 或 value"}), 400
    
    # 將欄位名稱映射到對應的資料庫更新函式
    update_functions = {
        'name': db.update_user_name,
        'zhuyin': db.update_user_zhuyin,
        'phone': lambda uid, val: db.update_user_phone_field(uid, 'phone', val),
        'phone2': lambda uid, val: db.update_user_phone_field(uid, 'phone2', val),
        'address': db.update_user_address
    }

    if field in update_functions:
        if update_functions[field](user_id, value):
            return jsonify({"status": "success", "message": f"用戶 {field} 已更新"})
    
    return jsonify({"status": "error", "message": "更新失敗或欄位不支援"}), 404

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
            "phone2": user.get('phone2', ''),
            "reminder_schedule": user.get('reminder_schedule', 'weekly')
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

@api_admin_bp.route('/users/<string:user_id>/update_reminder_schedule', methods=['POST'])
@admin_required
@api_error_handler
def api_update_reminder_schedule(user_id):
    data = request.get_json()
    schedule_type = data.get('schedule_type')

    if schedule_type not in ['daily', 'weekly']:
        return jsonify({"status": "error", "message": "無效的排程類型"}), 400

    success = db.update_user_reminder_schedule(user_id, schedule_type)
    if success:
        return jsonify({"status": "success", "message": "提醒排程已更新"})
    else:
        return jsonify({"status": "error", "message": "更新提醒排程失敗"}), 500

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

@api_admin_bp.route('/users/merge_suggestions', methods=['GET'])
@admin_required
@api_error_handler
def api_get_merge_suggestions():
    """
    分析用戶數據，提供臨時用戶與真實 LINE 用戶的合併建議。
    """
    all_users = db.get_all_users()
    manual_users = [u for u in all_users if u['user_id'].startswith('manual_')]
    line_users = [u for u in all_users if u['user_id'].startswith('U')]

    suggestions = []
    processed_line_users = set()
    processed_manual_users = set()

    def normalize_name(name):
        """移除常見的手動標記、所有空格和數字，以提取核心姓名。"""
        return re.sub(r'[\s()（）手動\d]', '', name) if name else ''

    line_users_by_phone = {}
    for u in line_users:
        if u.get('phone'): line_users_by_phone[u['phone']] = u
        if u.get('phone2'): line_users_by_phone[u['phone2']] = u

    for manual_user in manual_users:
        if manual_user['user_id'] in processed_manual_users:
            continue

        # 將可能包含多個姓名的 manual_user.name 拆分成多個 token 進行比對
        name_tokens = [t for t in re.split(r'[,\n/;，；\s]+', manual_user.get('name') or '') if t]
        if not name_tokens:
            continue

        # 規則 1：基於電話號碼匹配 (優先)
        if manual_user.get('phone') and manual_user['phone'] in line_users_by_phone:
            line_user = line_users_by_phone[manual_user['phone']]
            if line_user['user_id'] not in processed_line_users:
                suggestions.append({'source': dict(manual_user), 'target': dict(line_user), 'reason': '電話號碼相同'})
                processed_line_users.add(line_user['user_id'])
                processed_manual_users.add(manual_user['user_id'])
                continue # 找到就往下一個 manual_user 繼續

        # 規則 2：基於標準化後的姓名包含關係進行匹配
        for token in name_tokens:
            normalized_manual_name = normalize_name(token)
            if not normalized_manual_name:
                continue

            for line_user in line_users:
                if line_user['user_id'] in processed_line_users:
                    continue
                normalized_line_name = normalize_name(line_user['name'])
                if not normalized_line_name:
                    continue

                # 檢查名稱是否相互包含
                if normalized_manual_name in normalized_line_name or normalized_line_name in normalized_manual_name:
                    suggestions.append({'source': dict(manual_user), 'target': dict(line_user), 'reason': '姓名相似'})
                    processed_line_users.add(line_user['user_id'])
                    processed_manual_users.add(manual_user['user_id'])
                    break # 找到配對，處理下一個 manual_user
            if manual_user['user_id'] in processed_manual_users:
                break

    return jsonify({"status": "success", "suggestions": suggestions})

@api_admin_bp.route('/users/<string:user_id>', methods=['DELETE'])
@admin_required
@api_error_handler
def api_delete_user(user_id):
    if db.delete_user(user_id):
        return jsonify({"status": "success", "message": "用戶已成功刪除。"})
    else:
        return jsonify({"status": "error", "message": "刪除用戶失敗，找不到該用戶或有關聯資料。"}), 500