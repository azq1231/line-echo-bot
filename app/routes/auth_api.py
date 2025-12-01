from flask import Blueprint, request, jsonify, session, current_app
import requests
import database as db

auth_api_bp = Blueprint('auth_api', __name__)

@auth_api_bp.route('/liff_login', methods=['POST'])
def liff_login():
    """
    處理來自前端 LIFF 的登入請求
    接收 idToken，驗證後建立 Session
    """
    data = request.get_json()
    id_token = data.get('idToken')

    if not id_token:
        return jsonify({'status': 'error', 'message': 'Missing idToken'}), 400

    # 1. 驗證 ID Token
    # https://developers.line.biz/en/reference/line-login/#verify-id-token
    channel_id = current_app.config.get('LINE_LOGIN_CHANNEL_ID')
    if not channel_id:
        return jsonify({'status': 'error', 'message': 'Server configuration error: LINE_LOGIN_CHANNEL_ID not set'}), 500

    verify_url = 'https://api.line.me/oauth2/v2.1/verify'
    payload = {
        'id_token': id_token,
        'client_id': channel_id
    }

    try:
        response = requests.post(verify_url, data=payload)
        
        if response.status_code != 200:
            current_app.logger.error(f"LIFF ID Token verification failed: {response.text}")
            return jsonify({'status': 'error', 'message': 'Invalid ID Token'}), 401
            
        user_info = response.json()
        
        # 驗證成功，取得用戶資訊
        user_id = user_info.get('sub')
        name = user_info.get('name')
        picture_url = user_info.get('picture')
        
        if not user_id:
             return jsonify({'status': 'error', 'message': 'Invalid user info from LINE'}), 401

        # 2. 更新或建立用戶資料
        # 注意：這裡假設 db.add_user 會處理更新邏輯
        db.add_user(user_id, name, picture_url)
        
        # 3. 建立 Flask Session
        # 為了保持一致性，我們從資料庫重新讀取完整的用戶資料（包含 is_admin 等欄位）
        user_data_from_db = db.get_user_by_id(user_id)
        
        if not user_data_from_db:
             # Fallback if DB read fails immediately after write (unlikely but safe)
             user_data_from_db = {
                 'user_id': user_id,
                 'name': name,
                 'picture_url': picture_url,
                 'is_admin': False
             }

        session['user'] = {
            'user_id': user_data_from_db['user_id'],
            'name': user_data_from_db['name'],
            'picture_url': user_data_from_db.get('picture_url'),
            'is_admin': user_data_from_db.get('is_admin', False)
        }
        
        # 設置 session 為永久 (根據 app config 設定，通常是 30 天)
        session.permanent = True
        
        current_app.logger.info(f"LIFF login success for user: {name} ({user_id})")
        
        return jsonify({
            'status': 'success', 
            'user': session['user']
        })

    except Exception as e:
        current_app.logger.error(f"LIFF login error: {e}")
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500
