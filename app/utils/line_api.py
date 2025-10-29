import hmac
import hashlib
import base64
import requests
from flask import current_app, Response, send_from_directory

import database as db

def validate_signature(body, signature):
    """验证 LINE webhook 签名"""
    channel_secret = current_app.config.get('LINE_CHANNEL_SECRET')
    if not channel_secret:
        current_app.logger.warning("未设置 LINE_CHANNEL_SECRET，跳过签名验证")
        return True
    
    hash_obj = hmac.new(
        channel_secret.encode('utf-8'),
        body.encode('utf-8'),
        hashlib.sha256
    )
    expected_signature = base64.b64encode(hash_obj.digest()).decode('utf-8')
    
    return hmac.compare_digest(signature, expected_signature)

def get_line_profile(user_id):
    """获取 LINE 用户资料"""
    channel_token = current_app.config.get('LINE_CHANNEL_TOKEN')
    url = f"https://api.line.me/v2/bot/profile/{user_id}"
    headers = {"Authorization": f"Bearer {channel_token}"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            profile = response.json()
            user_info = {
                'name': profile.get('displayName', '未知'),
                'picture_url': profile.get('pictureUrl')
            }
            current_app.logger.info(f"成功獲取用戶資料：{user_info['name']}")
            return user_info
        else:
            current_app.logger.error(f"LINE Profile API 錯誤: {response.text}")
    except Exception as e:
        current_app.logger.error(f"獲取用戶資料時發生錯誤: {e}")
    return {'name': '未知', 'picture_url': None}

def send_line_message(user_id, messages, message_type="message", target_name=None):
    """发送 LINE 消息（支持文本和 Flex Message）"""
    channel_token = current_app.config.get('LINE_CHANNEL_TOKEN')
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {channel_token}"
    }
    
    if not isinstance(messages, list):
        messages = [messages]
    
    data = {
        "to": user_id,
        "messages": messages
    }
    
    message_excerpt = None
    if len(messages) > 0:
        first_message = messages[0]
        if isinstance(first_message, dict) and first_message.get("type") == "text":
            message_excerpt = first_message["text"][:100] + "..." if len(first_message["text"]) > 100 else first_message["text"]
        elif isinstance(first_message, str):
            message_excerpt = first_message[:100] + "..." if len(first_message) > 100 else first_message
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            db.log_message_send(
                user_id=user_id,
                target_name=target_name or '未知',
                message_type=message_type,
                status='success',
                message_excerpt=message_excerpt
            )
            return True
        else:
            error_msg = f"Error {response.status_code}: {response.text}"
            db.log_message_send(
                user_id=user_id,
                target_name=target_name or '未知',
                message_type=message_type,
                status='failed',
                error_message=error_msg,
                message_excerpt=message_excerpt
            )
            current_app.logger.error(f"Error sending message: {error_msg}")
            return False
    except Exception as e:
        error_msg = str(e)
        db.log_message_send(
            user_id=user_id,
            target_name=target_name or '未知',
            message_type=message_type,
            status='failed',
            error_message=error_msg,
            message_excerpt=message_excerpt
        )
        current_app.logger.error(f"Exception sending message: {error_msg}")
        return False

def user_avatar(user_id):
    user = db.get_user_by_id(user_id)
    if not user or not user.get('picture_url') or user_id.startswith('manual_'):
        return send_from_directory('static', 'nohead.png')
    try:
        picture_response = requests.get(user['picture_url'], timeout=5)
        picture_response.raise_for_status()
        response = Response(picture_response.content, mimetype=picture_response.headers['Content-Type'])
        response.headers['Cache-Control'] = 'public, max-age=3600'
        return response
    except requests.RequestException as e:
        current_app.logger.error(f"下載頭像失敗 for user {user_id}: {e}")
        return send_from_directory('static', 'nohead.png')

def refresh_user_profile(user_id):
    user_info = get_line_profile(user_id)
    if user_info and user_info['name'] != '未知':
        db.add_user(user_id, user_info['name'], user_info['picture_url'], address=None)
        return True
    return False