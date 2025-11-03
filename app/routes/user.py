from flask import Blueprint, jsonify, current_app
from app.utils.decorators import admin_required
from app.utils.line_api import user_avatar, refresh_user_profile

user_bp = Blueprint('user', __name__, url_prefix='/users')

@user_bp.route("/user_avatar/<user_id>")
def user_avatar_route(user_id):
    """
    作為用戶頭像的代理，以實現瀏覽器快取。
    這是一個公開的路由，但可以考慮加上登入驗-證。
    """
    try:
        return user_avatar(user_id)
    except Exception as e:
        # 使用 logger.exception 來記錄完整的 traceback，方便偵錯
        current_app.logger.exception(f"獲取頭像失敗 for user_id {user_id}")
        return jsonify({"status": "error", "message": str(e)}), 500

@user_bp.route("/refresh_user_profile/<user_id>", methods=["POST"])
@admin_required # 只有管理員可以觸發更新
def refresh_user_profile_route(user_id):
    if refresh_user_profile(user_id):
        return jsonify({"status": "success", "message": "用戶資料已從 LINE 更新。"})
    else:
        return jsonify({"status": "error", "message": "從 LINE 獲取資料失敗。"}), 404