from functools import wraps
from flask import request, session, redirect, url_for, flash, current_app
import traceback

import database as db
from .helpers import api_response # We will move api_response later

def admin_required(f):
    """
    一個裝飾器，用來驗證使用者是否為登入的管理員。
    現在也支援透過 X-Admin-Token 進行 API 驗證。
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        is_api_request = request.path.startswith('/api/')

        # --- API Token 驗證 (優先於 Session 驗證) ---
        if is_api_request:
            admin_token = request.headers.get("X-Admin-Token")
            if admin_token:
                if admin_token == current_app.config.get("ADMIN_API_TOKEN"):
                    # Token 有效，直接授權
                    return f(*args, **kwargs)
                else:
                    # Token 無效
                    return api_response(error="API Token 無效。", status_code=401)
            # 如果沒有提供 API Token，則繼續執行 Session 驗證

        # --- Session 驗證 (針對網頁請求或未提供 API Token 的 API 請求) ---
        if 'user' not in session or 'user_id' not in session['user']:
            if is_api_request:
                return api_response(error="未授權或登入逾時，請重新整理頁面並登入。", status_code=401)
            else:
                flash('請先登入以存取此頁面。', 'warning')
                return redirect(url_for('auth.login', next=request.url))

        user_data = db.get_user_by_id(session['user']['user_id'])
        is_admin_in_db = user_data and user_data.get('is_admin')

        if 'is_admin' not in session['user'] or session['user']['is_admin'] != is_admin_in_db:
            session['user'] = db.get_user_by_id(session['user']['user_id'])
            session.modified = True

        if not is_admin_in_db:
            if is_api_request:
                return api_response(error="權限不足。", status_code=403)
            else:
                flash('您沒有權限存取此頁面。', 'danger')
                return redirect(url_for('booking.booking_page'))

        return f(*args, **kwargs)
    return decorated_function

def api_error_handler(f):
    """
    一個通用的 API 錯誤處理裝飾器。
    它會自動捕捉路由函式中的所有例外，記錄詳細的 traceback，
    並確保總是回傳一個格式正確的 JSON 錯誤訊息。
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            print(f"--- Unhandled Exception in API endpoint: {request.path} ---")
            traceback.print_exc()
            print("-----------------------------------------------------------")
            return api_response(error=f"伺服器內部發生未預期錯誤: {e}", status_code=500)
    return decorated_function