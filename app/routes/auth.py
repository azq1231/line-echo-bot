import os
import uuid
import requests
from flask import Blueprint, request, session, redirect, url_for, flash, current_app

import database as db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login')
def login():
    """重定向到 LINE 登入頁面"""
    line_login_channel_id = current_app.config.get('LINE_LOGIN_CHANNEL_ID')
    if not line_login_channel_id:
        flash("系統未設定 LINE Login Channel，無法登入。", "danger")
        return redirect(url_for('booking.booking_page'))

    state = str(uuid.uuid4())
    session['oauth_state'] = state
    redirect_uri = url_for('auth.callback', _external=True)

    # 如果有 'next' 參數，儲存到 session 中，以便 callback 處理
    next_param = request.args.get('next')
    if next_param:
        session['next_url'] = next_param
    
    auth_url = (
        f"https://access.line.me/oauth2/v2.1/authorize?response_type=code"
        f"&client_id={line_login_channel_id}"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
        f"&scope=profile%20openid"
    )
    return redirect(auth_url)

@auth_bp.route('/callback')
def callback():
    """處理 LINE 登入後的回呼"""
    code = request.args.get('code')
    state = request.args.get('state')

    if not state or state != session.get('oauth_state'):
        flash("登入驗證失敗，請重試。", "danger")
        return redirect(url_for('booking_page')) # 之後會改成 booking_bp.booking_page

    # 換取 Access Token
    token_url = "https://api.line.me/oauth2/v2.1/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": url_for('auth.callback', _external=True),
        "client_id": current_app.config.get('LINE_LOGIN_CHANNEL_ID'),
        "client_secret": current_app.config.get('LINE_LOGIN_CHANNEL_SECRET'),
    }
    response = requests.post(token_url, headers=headers, data=data)
    if response.status_code != 200:
        flash("無法從 LINE 獲取 Token，請稍後再試。", "danger")
        return redirect(url_for('booking.booking_page'))

    # 獲取使用者資料
    profile_url = "https://api.line.me/v2/profile"
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    profile_response = requests.get(profile_url, headers=headers)
    if profile_response.status_code != 200:
        flash("無法獲取 LINE 使用者資料。", "danger")
        return redirect(url_for('booking.booking_page'))

    profile = profile_response.json()
    user_id = profile['userId']
    user_name = profile['displayName']
    picture_url = profile.get('pictureUrl')

    # 將使用者資料存入資料庫 (db.add_user 會處理新增或更新)
    db.add_user(user_id, user_name, picture_url, address=None)

    # 從資料庫獲取完整的用戶資訊，包括 is_admin
    user_data_from_db = db.get_user_by_id(user_id)
    if not user_data_from_db:
        flash("登入失敗：無法獲取用戶資料。", "danger")
        return redirect(url_for('booking.booking_page'))

    # 將完整的用戶資訊存入 session
    session['user'] = {
        'user_id': user_data_from_db['user_id'],
        'name': user_data_from_db['name'],
        'picture_url': user_data_from_db.get('picture_url'),
        'is_admin': user_data_from_db.get('is_admin', False) # 確保有 is_admin 屬性
    }
    
    flash("登入成功！", "success")

    # 處理登入後的重定向
    next_url = session.pop('next_url', None)
    # 如果使用者是管理員，優先導向後台首頁或指定的後台頁面
    if session.get('user', {}).get('is_admin'):
        return redirect(next_url or url_for('admin.admin_home'))
    # 否則，導向指定的公開頁面或預設的預約頁面
    return redirect(next_url or url_for('booking.booking_page'))

@auth_bp.route('/logout')
def logout():
    """登出"""
    session.pop('user', None)
    flash("您已成功登出。", "info")
    return redirect(url_for('booking.booking_page'))
