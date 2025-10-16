from flask import Flask, request, jsonify, render_template, flash, redirect, url_for, Response, session
import os
import requests
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import uuid
import hmac
import hashlib
import base64

# 导入数据库和 Flex Message 模块
import database as db
import line_flex_messages as flex
import gemini_ai

# 載入 .env 檔案中的環境變數
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# 從環境變數讀取 SECRET_KEY，這對於生產環境至關重要
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    print("警告：未設定 FLASK_SECRET_KEY 環境變數，將使用隨機值。在生產環境中這會導致 session 問題。")
    app.secret_key = os.urandom(24)

LINE_CHANNEL_TOKEN = os.getenv("LINE_CHANNEL_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_LOGIN_CHANNEL_ID = os.getenv("LINE_LOGIN_CHANNEL_ID")
LINE_LOGIN_CHANNEL_SECRET = os.getenv("LINE_LOGIN_CHANNEL_SECRET")
TAIPEI_TZ = pytz.timezone('Asia/Taipei')

# 初始化数据库
db.init_database()

# ============ 全局上下文處理器 ============

@app.context_processor
def inject_feature_flags():
    """將功能開關的狀態注入到所有模板中，以便動態顯示/隱藏導覽列項目。"""
    return {
        'feature_schedule_enabled': db.get_config('feature_schedule_enabled', 'true') != 'false',
        'feature_closed_days_enabled': db.get_config('feature_closed_days_enabled', 'true') != 'false',
        'feature_booking_enabled': db.get_config('feature_booking_enabled', 'true') != 'false',
    }

# ============ LINE API 辅助函数 ============ 

def validate_signature(body, signature):
    """验证 LINE webhook 签名"""
    if not LINE_CHANNEL_SECRET:
        print("警告：未设置 LINE_CHANNEL_SECRET，跳过签名验证")
        return True
    
    hash_obj = hmac.new(
        LINE_CHANNEL_SECRET.encode('utf-8'),
        body.encode('utf-8'),
        hashlib.sha256
    )
    expected_signature = base64.b64encode(hash_obj.digest()).decode('utf-8')
    
    return hmac.compare_digest(signature, expected_signature)

def get_line_profile(user_id):
    """获取 LINE 用户资料"""
    url = f"https://api.line.me/v2/bot/profile/{user_id}"
    headers = {"Authorization": f"Bearer {LINE_CHANNEL_TOKEN}"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            profile = response.json()
            user_info = {
                'name': profile.get('displayName', '未知'),
                'picture_url': profile.get('pictureUrl')
            }
            print(f"成功獲取用戶資料：{user_info['name']}")
            return user_info
        else:
            print(f"LINE Profile API 錯誤: {response.text}")
    except Exception as e:
        print(f"獲取用戶資料時發生錯誤: {e}")
    return {'name': '未知', 'picture_url': None}

def send_line_message(user_id, messages, message_type="message", target_name=None):
    """发送 LINE 消息（支持文本和 Flex Message）"""
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}"
    }
    
    if not isinstance(messages, list):
        messages = [messages]
    
    data = {
        "to": user_id,
        "messages": messages
    }
    
    # 準備摘要
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
            # 記錄成功發送
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
            # 記錄失敗
            db.log_message_send(
                user_id=user_id,
                target_name=target_name or '未知',
                message_type=message_type,
                status='failed',
                error_message=error_msg,
                message_excerpt=message_excerpt
            )
            print(f"Error sending message: {error_msg}")
            return False
    except Exception as e:
        error_msg = str(e)
        # 記錄例外
        db.log_message_send(
            user_id=user_id,
            target_name=target_name or '未知',
            message_type=message_type,
            status='failed',
            error_message=error_msg,
            message_excerpt=message_excerpt
        )
        print(f"Exception sending message: {error_msg}")
        return False

def reply_message(user_id, text):
    """发送文本消息（兼容旧代码）"""
    return send_line_message(user_id, [{"type": "text", "text": text}], message_type="text")

# ============ 预约辅助函数 ============ 

def get_week_dates(week_offset=0):
    """
    获取指定周次的日期（週二到週六）
    week_offset: 0=本週, 1=下週, -1=上週
    """
    today = datetime.now(TAIPEI_TZ).date()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    
    week_dates = []
    for i in range(1, 6):  # 1=週二 到 5=週六
        date = monday + timedelta(days=i)
        day_names = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']
        week_dates.append({
            'date': date.strftime('%Y-%m-%d'),
            'day_name': day_names[i],
            'weekday': i,
            'display': date.strftime('%m/%d')
        })
    
    return week_dates

def generate_time_slots(weekday):
    """根据星期生成时间段"""
    slots = []
    if weekday in [1, 3]:
        for hour in range(14, 18):
            for minute in [0, 15, 30, 45]:
                slots.append(f"{hour:02d}:{minute:02d}")
        slots.append("18:00")
    elif weekday == 5:
        for hour in range(10, 18):
            for minute in [0, 15, 30, 45]:
                slots.append(f"{hour:02d}:{minute:02d}")
        slots.append("18:00")
    elif weekday in [2, 4]:
        for hour in range(18, 21):
            for minute in [0, 15, 30, 45]:
                slots.append(f"{hour:02d}:{minute:02d}")
        slots.append("21:00")
    return slots

def get_available_slots(date, weekday):
    """获取某日期的可用时段（过滤掉已过去的时间）"""
    all_slots = generate_time_slots(weekday)
    
    if db.is_closed_day(date):
        return []
    
    appointments = db.get_appointments_by_date_range(date, date)
    booked_times = [apt['time'] for apt in appointments if apt['status'] == 'confirmed']
    
    now = datetime.now(TAIPEI_TZ)
    
    filtered_slots = []
    for slot in all_slots:
        if slot not in booked_times:
            if date == now.strftime('%Y-%m-%d'):
                slot_time = datetime.strptime(f"{date} {slot}", '%Y-%m-%d %H:%M').replace(tzinfo=TAIPEI_TZ)
                if slot_time > now:
                    filtered_slots.append(slot)
            else:
                filtered_slots.append(slot)
    
    return filtered_slots

def get_week_schedule_for_booking(week_offset=0):
    """一次性获取整周的预约时段，用于线上预约页面"""
    week_dates = get_week_dates(week_offset)
    start_date = week_dates[0]['date']
    end_date = week_dates[-1]['date']

    # 一次性获取整周的预约和休诊日
    all_appointments = db.get_appointments_by_date_range(start_date, end_date)
    all_closed_days = {day['date'] for day in db.get_all_closed_days()}
    
    # 将预约按日期分组
    appointments_by_date = {}
    for apt in all_appointments:
        if apt['status'] == 'confirmed':
            appointments_by_date.setdefault(apt['date'], set()).add(apt['time'])

    schedule_data = []
    for day in week_dates:
        day['is_closed'] = day['date'] in all_closed_days
        day['available_slots'] = get_available_slots(day['date'], day['weekday'])
        schedule_data.append(day)
    return schedule_data

# ============ WEB 路由 ============ 

@app.route("/")
def home():
    # 從資料庫讀取刪除功能的開關狀態，預設為關閉 (False)
    allow_deletion = db.get_config('allow_user_deletion') == 'true'
    return render_template("admin.html", allow_user_deletion=allow_deletion)

@app.route("/schedule")
def schedule():
    if db.get_config('feature_schedule_enabled') == 'false':
        return "Feature disabled", 404
    return render_template("schedule.html")

@app.route("/appointments")
def appointments_page():
    return render_template("appointments.html")

@app.route("/closed_days")
def closed_days_page():
    if db.get_config('feature_closed_days_enabled') == 'false':
        return "Feature disabled", 404
    return render_template("closed_days.html")

@app.route("/stats")
def stats_page():
    # 獲取月份參數，預設為當前月份
    current_month = request.args.get('month', datetime.now(TAIPEI_TZ).strftime('%Y-%m'))
    # 獲取其他篩選參數
    message_type = request.args.get('type')
    user_id = request.args.get('user')

    # 獲取所有用戶以供篩選
    all_users = db.get_all_users()
    
    # 獲取統計數據
    stats_data = db.get_message_stats(
        month=current_month,
        message_type=message_type if message_type else None,
        user_id=user_id if user_id else None
    )
    
    return render_template('stats.html', 
                         stats=stats_data,
                         current_month=current_month,
                         all_users=all_users,
                         current_user=user_id,
                         current_type=message_type)

@app.route("/configs")
def configs_page():
    """渲染系統設定頁面"""
    all_configs_list = db.get_all_configs()
    # 將列表轉換為字典以便在模板中輕鬆訪問
    configs_dict = {c['key']: c['value'] for c in all_configs_list}
    
    # 為尚未設定的項目提供預設值
    configs_dict.setdefault('booking_window_weeks', '2')
    configs_dict.setdefault('allow_user_deletion', 'false')
    configs_dict.setdefault('feature_schedule_enabled', 'true')
    configs_dict.setdefault('feature_closed_days_enabled', 'true')
    configs_dict.setdefault('feature_booking_enabled', 'true')
    configs_dict.setdefault('auto_reminder_enabled', 'false')
    configs_dict.setdefault('auto_reminder_daily_time', '09:00')
    configs_dict.setdefault('auto_reminder_weekly_day', 'sun')
    configs_dict.setdefault('auto_reminder_weekly_time', '21:00')

    return render_template("configs.html", configs=configs_dict)


@app.route("/api/message_stats")
def message_stats_api():
    month = request.args.get('month')
    message_type = request.args.get('type')
    user_id = request.args.get('user')
    
    stats_data = db.get_message_stats(month, user_id, message_type)
    
    return jsonify(stats_data)

# ============ LINE Login & Web Booking Site ============

@app.route('/login')
def login():
    """重定向到 LINE 登入頁面"""
    if not all([LINE_LOGIN_CHANNEL_ID, LINE_LOGIN_CHANNEL_SECRET]):
        flash("系統未設定 LINE Login Channel，無法登入。", "danger")
        return redirect(url_for('booking_page'))

    state = str(uuid.uuid4())
    session['oauth_state'] = state
    redirect_uri = url_for('callback', _external=True)
    
    auth_url = (
        f"https://access.line.me/oauth2/v2.1/authorize?response_type=code"
        f"&client_id={LINE_LOGIN_CHANNEL_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
        f"&scope=profile%20openid"
    )
    return redirect(auth_url)

@app.route('/callback')
def callback():
    """處理 LINE 登入後的回呼"""
    code = request.args.get('code')
    state = request.args.get('state')

    if not state or state != session.get('oauth_state'):
        flash("登入驗證失敗，請重試。", "danger")
        return redirect(url_for('booking_page'))

    # 換取 Access Token
    token_url = "https://api.line.me/oauth2/v2.1/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": url_for('callback', _external=True),
        "client_id": LINE_LOGIN_CHANNEL_ID,
        "client_secret": LINE_LOGIN_CHANNEL_SECRET,
    }
    response = requests.post(token_url, headers=headers, data=data)
    if response.status_code != 200:
        flash("無法從 LINE 獲取 Token，請稍後再試。", "danger")
        return redirect(url_for('booking_page'))

    # 獲取使用者資料
    profile_url = "https://api.line.me/v2/profile"
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    profile_response = requests.get(profile_url, headers=headers)
    if profile_response.status_code != 200:
        flash("無法獲取 LINE 使用者資料。", "danger")
        return redirect(url_for('booking_page'))

    profile = profile_response.json()
    user_id = profile['userId']
    user_name = profile['displayName']
    picture_url = profile.get('pictureUrl')

    # 將使用者資料存入資料庫和 session
    db.add_user(user_id, user_name, picture_url)
    session['user'] = {
        'user_id': user_id,
        'name': user_name,
        'picture_url': picture_url
    }
    
    flash("登入成功！", "success")
    return redirect(url_for('booking_page'))

@app.route('/logout')
def logout():
    """登出"""
    session.pop('user', None)
    flash("您已成功登出。", "info")
    return redirect(url_for('booking_page'))

@app.route("/booking/", methods=["GET"])
def booking_page():
    if db.get_config('feature_booking_enabled') == 'false':
        return "Feature disabled", 404

    user = session.get('user')
    schedule_data = None
    week_offset = 0 # 為 week_offset 提供預設值

    if user:
        week_offset_str = request.args.get('week_offset', '0')
        try:
            week_offset = int(week_offset_str)
        except ValueError:
            week_offset = 0

        week_dates = get_week_dates(week_offset=week_offset)
        start_date = week_dates[0]['date']
        end_date = week_dates[-1]['date']
        
        appointments_this_week = db.get_appointments_by_date_range(start_date, end_date)
        booked_slots = {(apt['date'], apt['time']): apt['user_name'] for apt in appointments_this_week if apt['status'] == 'confirmed'}
        closed_days = {day['date'] for day in db.get_all_closed_days()}

        schedule_data = []
        now = datetime.now(TAIPEI_TZ)

        for day in week_dates:
             day['is_closed'] = day['date'] in closed_days
             all_slots = generate_time_slots(day['weekday'])
             day['slots'] = []
             for slot in all_slots:
                 is_available = (day['date'], slot) not in booked_slots.keys() and not day['is_closed']
                 
                 # 統一檢查時段是否已過去
                 if is_available:
                     try:
                         slot_datetime = datetime.strptime(f"{day['date']} {slot}", '%Y-%m-%d %H:%M').replace(tzinfo=TAIPEI_TZ)
                         if slot_datetime <= now:
                             is_available = False
                     except ValueError:
                         pass # 忽略解析錯誤
                 day['slots'].append({'time': slot, 'available': is_available, 'user_name': booked_slots.get((day['date'], slot))})
             schedule_data.append(day)

    return render_template("booking.html", user=user, schedule=schedule_data, week_offset=week_offset, max_weeks=int(db.get_config('booking_window_weeks') or '2'))

@app.route("/booking/history", methods=["GET"])
def booking_history_page():
    """使用者預約歷史頁面"""
    user = session.get('user')
    if not user:
        # 如果未登入，可以選擇渲染一個提示登入的頁面或重定向
        return render_template("booking_history.html", user=None)

    user_id = user['user_id']
    all_appointments = db.get_appointments_by_user(user_id)

    now = datetime.now(TAIPEI_TZ)
    weekday_names = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']

    future_appointments = []
    past_appointments = []

    for apt in all_appointments:
        try:
            # 將資料庫中的字串時間轉換為有時區的 datetime 物件
            apt_datetime = datetime.strptime(f"{apt['date']} {apt['time']}", '%Y-%m-%d %H:%M').replace(tzinfo=TAIPEI_TZ)
            apt['created_at'] = datetime.strptime(apt['created_at'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.utc).astimezone(TAIPEI_TZ)
            apt['formatted_date'] = apt_datetime.strftime('%Y/%m/%d')
            apt['weekday'] = weekday_names[apt_datetime.weekday()]

            if apt_datetime > now and apt['status'] == 'confirmed':
                future_appointments.append(apt)
            else:
                past_appointments.append(apt)
        except (ValueError, TypeError):
            # 忽略格式錯誤的舊資料
            continue
    
    # 排序，讓最近的在最前面
    future_appointments.sort(key=lambda x: (x['date'], x['time']))
    past_appointments.sort(key=lambda x: (x['date'], x['time']), reverse=True)

    return render_template(
        "booking_history.html",
        user=user,
        future_appointments=future_appointments,
        past_appointments=past_appointments
    )


# ============ 用户管理 API ============ 

@app.route("/list_users")
def list_users():
    users = db.get_all_users()
    return jsonify({"allowed_users": users, "count": len(users)})

@app.route("/add_user/<user_id>")
def add_user(user_id):
    # 從 LINE 獲取用戶資料
    user_info = get_line_profile(user_id)
    # 將完整資料存入資料庫
    db.add_user(user_id, user_info['name'], user_info['picture_url']) 
    db.update_user_name(user_id, user_info['name']) # 標記為手動（或至少是管理員介入）
    
    return jsonify({"status": "success", "message": f"已新增使用者：{user_id}"})

@app.route("/delete_user/<user_id>")
def delete_user(user_id):
    if db.delete_user(user_id):
        return jsonify({"status": "success", "message": f"已刪除使用者：{user_id}"})
    else:
        return jsonify({"status": "error", "message": "使用者不存在"})

@app.route("/refresh_user_profile/<user_id>", methods=["POST"])
def refresh_user_profile(user_id):
    """手動從 LINE 更新用戶的個人資料（特別是頭像）"""
    user_info = get_line_profile(user_id)
    if user_info and user_info['name'] != '未知':
        # add_user 包含智能更新邏輯：如果名稱被手動修改過，則只更新頭像
        db.add_user(user_id, user_info['name'], user_info['picture_url'])
        return jsonify({"status": "success", "message": "用戶資料已從 LINE 更新。"})
    else:
        return jsonify({"status": "error", "message": "從 LINE 獲取資料失敗。"}), 404

@app.route('/user_avatar/<user_id>')
def user_avatar(user_id):
    """作為用戶頭像的代理，以實現瀏覽器快取"""
    user = db.get_user_by_id(user_id)
    
    # 如果找不到用戶或用戶沒有頭像URL，重定向到一個預設圖片
    if not user or not user.get('picture_url'):
        return redirect('https://via.placeholder.com/40')

    try:
        # 從 LINE 的伺服器下載圖片
        picture_response = requests.get(user['picture_url'], timeout=5)
        picture_response.raise_for_status() # 如果請求失敗則拋出異常

        # 建立一個 Flask Response 物件，並設定快取時間為 1 小時
        response = Response(picture_response.content, mimetype=picture_response.headers['Content-Type'])
        response.headers['Cache-Control'] = 'public, max-age=3600'
        return response
    except requests.RequestException as e:
        print(f"下載頭像失敗 for user {user_id}: {e}")
        return redirect('https://via.placeholder.com/40')

@app.route("/update_user_name", methods=["POST"])
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

@app.route("/update_user_zhuyin", methods=["POST"])
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

@app.route("/update_user_phone", methods=["POST"])
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

@app.route("/generate_zhuyin/<user_id>", methods=["POST"])
def generate_zhuyin_route(user_id):
    new_zhuyin = db.generate_and_save_zhuyin(user_id)
    if new_zhuyin is not None:
        return jsonify({"status": "success", "zhuyin": new_zhuyin})
    else:
        return jsonify({"status": "error", "message": "生成失败"}), 404

# ============ 预约管理 API ============ 

@app.route("/get_week_appointments")
def get_week_appointments():
    week_offset = int(request.args.get('offset', 0))
    print(f"get_week_appointments: offset={week_offset}")  # Add log

    week_dates = get_week_dates(week_offset)
    
    week_schedule = {}
    all_users = db.get_all_users()
    
    for date_info in week_dates:
        date_str = date_info['date']
        weekday = date_info['weekday']
        time_slots = generate_time_slots(weekday)  # Corrected variable name
        
        appointments = db.get_appointments_by_date_range(date_str, date_str)
        appointments_map = {apt['time']: apt for apt in appointments if apt['status'] == 'confirmed'}
        
        day_appointments = {}
        for time_slot in time_slots:
            apt = appointments_map.get(time_slot)
            day_appointments[time_slot] = {
                'user_name': apt['user_name'] if apt else '',
                'user_id': apt['user_id'] if apt else ''
            }
        
        week_schedule[date_str] = {
            'date_info': date_info,
            'appointments': day_appointments
        }
    
    response_data = {
        'week_schedule': week_schedule,
        'users': all_users,
        'week_offset': week_offset
    }
    
    print(f"get_week_appointments: response={response_data}")  # Add log
    return jsonify(response_data)
@app.route("/save_appointment", methods=["POST"])
def save_appointment():
    data = request.get_json()
    date = data.get('date')
    time = data.get('time')
    user_name = data.get('user_name')
    user_id = data.get('user_id', '')
    
    db.cancel_appointment(date, time)
    
    if user_name and user_id:
        db.add_appointment(user_id, user_name, date, time)
    
    return jsonify({"status": "success"})

@app.route("/api/book_appointment", methods=["POST"])
def api_book_appointment():
    """API for booking from the web interface"""
    if 'user' not in session:
        return jsonify({"status": "error", "message": "使用者未登入"}), 401

    data = request.get_json()
    date = data.get('date')
    time = data.get('time')

    if not date or not time:
        return jsonify({"status": "error", "message": "預約資料不完整"}), 400

    user = session['user']
    success = db.add_appointment(
        user_id=user['user_id'],
        user_name=user['name'],
        date=date,
        time=time
    )

    if success:
        return jsonify({"status": "success", "message": f"恭喜！您已成功預約 {date} {time} 的時段。"})
    else:
        return jsonify({"status": "error", "message": f"抱歉，{date} {time} 的時段已被預約，請選擇其他時段。"}), 409

@app.route("/api/cancel_my_appointment", methods=["POST"])
def api_cancel_my_appointment():
    """API for user to cancel their own appointment from the web."""
    if 'user' not in session:
        return jsonify({"status": "error", "message": "使用者未登入"}), 401

    data = request.get_json()
    appointment_id = data.get('appointment_id')
    if not appointment_id:
        return jsonify({"status": "error", "message": "缺少預約 ID"}), 400

    user = session['user']
    user_id = user['user_id']

    # 在取消前先獲取預約資訊，以便發送通知
    apt_to_cancel = db.get_appointment_by_id(appointment_id)
    if not apt_to_cancel or apt_to_cancel['user_id'] != user_id:
        return jsonify({"status": "error", "message": "找不到此預約或權限不足"}), 404

    success = db.cancel_user_appointment(appointment_id, user_id)

    if success:
        # 已移除 LINE 取消成功通知
        # send_line_message(...)
        return jsonify({"status": "success", "message": "預約已成功取消。"})
    else:
        return jsonify({"status": "error", "message": "取消失敗，請稍後再試。"}), 500

def _do_send_reminders(appointments: list) -> tuple[int, int]:
    """發送提醒的核心邏輯"""
    sent_count = 0
    failed_count = 0
    
    for apt in appointments:
        if apt.get('user_id'):
            date_obj = datetime.strptime(apt['date'], '%Y-%m-%d')
            weekday_names = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
            weekday_name = weekday_names[date_obj.weekday()]
            
            message = f"提醒您，您的預約時間是 {date_obj.month}月{date_obj.day}日 {weekday_name} {apt['time']}，謝謝。"
            
            success = send_line_message(
                user_id=apt['user_id'],
                messages=[{"type": "text", "text": message}],
                message_type='reminder',
                target_name=apt['user_name']
            )
            if success:
                sent_count += 1
            else:
                failed_count += 1
    return sent_count, failed_count

@app.route("/send_appointment_reminders", methods=["POST"])
def send_appointment_reminders():
    data = request.get_json()
    send_type = data.get('type', 'week')
    target_date = data.get('date', '')
    
    if send_type == 'day' and target_date:
        appointments = db.get_appointments_by_date_range(target_date, target_date)
    else:
        week_dates = get_week_dates()
        start_date = week_dates[0]['date']
        end_date = week_dates[-1]['date']
        appointments = db.get_appointments_by_date_range(start_date, end_date)
    
    appointments = [apt for apt in appointments if apt['status'] == 'confirmed']
    
    sent_count, failed_count = _do_send_reminders(appointments)
    
    return jsonify({
        "status": "success",
        "sent_count": sent_count,
        "failed_count": failed_count
    })

# ============ 休诊管理 API ============ 

@app.route("/get_closed_days")
def get_closed_days():
    closed_days = db.get_all_closed_days()
    return jsonify({"closed_days": closed_days})

@app.route("/set_closed_day", methods=["POST"])
def set_closed_day():
    data = request.get_json()
    date = data.get('date')
    reason = data.get('reason', '休診')
    
    if not date:
        return jsonify({"status": "error", "message": "缺少日期"}), 400
    
    cancelled_count = db.set_closed_day(date, reason)
    
    return jsonify({
        "status": "success",
        "message": f"已設定休診，取消了 {cancelled_count} 個預約"
    })

@app.route("/remove_closed_day", methods=["POST"])
def remove_closed_day():
    data = request.get_json()
    date = data.get('date')
    
    if db.remove_closed_day(date):
        return jsonify({"status": "success", "message": "已移除休診設定"})
    else:
        return jsonify({"status": "error", "message": "未找到休診記錄"}), 404

# ============ 系统配置 API ============ 

@app.route("/get_config")
def get_config_api():
    configs = db.get_all_configs()
    return jsonify({"configs": configs})

@app.route("/set_config", methods=["POST"])
def set_config_api():
    data = request.get_json()
    key = data.get('key')
    value = data.get('value')
    description = data.get('description', '')
    
    if not key or not value:
        return jsonify({"status": "error", "message": "缺少必要参数"}), 400
    
    if key == 'booking_window_weeks' and value not in ['2', '4']:
        return jsonify({"status": "error", "message": "预约窗口只能设置为2周或4周"}), 400
    
    if db.set_config(key, value, description):
        # 如果更新的是排程時間，動態更新排程器
        if key.startswith('auto_reminder_'):
            try:
                # 移除現有排程
                scheduler.remove_job('daily_reminder_job')
                scheduler.remove_job('weekly_reminder_job')
                
                # 重新讀取所有相關設定並新增排程
                daily_time_str = db.get_config('auto_reminder_daily_time', '09:00') or '09:00'
                daily_time = daily_time_str.split(':')
                scheduler.add_job(func=send_daily_reminders_job, trigger="cron", id='daily_reminder_job', hour=int(daily_time[0]), minute=int(daily_time[1]), timezone=TAIPEI_TZ, replace_existing=True)

                weekly_day = db.get_config('auto_reminder_weekly_day', 'sun') or 'sun'
                weekly_time_str = db.get_config('auto_reminder_weekly_time', '21:00') or '21:00'
                weekly_time = weekly_time_str.split(':')
                scheduler.add_job(func=send_weekly_reminders_job, trigger="cron", id='weekly_reminder_job', day_of_week=weekly_day, hour=int(weekly_time[0]), minute=int(weekly_time[1]), timezone=TAIPEI_TZ, replace_existing=True)
                
                print("排程器任務已動態更新。")
            except Exception as e:
                print(f"動態更新排程器失敗: {e}")

        return jsonify({"status": "success", "message": "配置已更新"})
    else:
        return jsonify({"status": "error", "message": "更新失败"}), 500

# ============ LINE Webhook ============ 

@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get('X-Line-Signature', '')
    body_text = request.get_data(as_text=True)
    
    if not validate_signature(body_text, signature):
        print("❌ LINE Webhook 签名验证失败")
        return jsonify({"status": "error", "message": "Invalid signature"}), 403
    
    body = request.get_json()
    events = body.get("events", [])

    for event in events:
        if event["type"] == "follow":
            user_id = event["source"]["userId"]
            print(f"用戶加入好友 - 用戶ID: {user_id}")
            user_info = get_line_profile(user_id)
            db.add_user(user_id, user_info['name'], user_info['picture_url'])
        
        elif event["type"] == "message":
            user_id = event["source"]["userId"]
            message_type = event["message"]["type"]
            print(f"收到訊息 - 用戶ID: {user_id}, 類型: {message_type}")
            
            # 每次收到訊息都嘗試更新用戶資料，db.add_user 會處理衝突
            user_info = get_line_profile(user_id)
            db.add_user(user_id, user_info['name'], user_info['picture_url'])
            
            # 如果是文字訊息，才進一步處理內容
            if message_type == "text":
                user_message = event["message"]["text"].strip()
                if user_message in ['預約', '预约', '訂位', '订位']:
                    handle_booking_start(user_id)
                elif user_message in ['查詢', '查询', '我的預約', '我的预约']:
                    handle_query_appointments(user_id)
                elif user_message in ['取消', '取消預約', '取消预约']:
                    handle_cancel_booking(user_id)
        
        elif event["type"] == "postback":
            user_id = event["source"]["userId"]
            data = event["postback"]["data"]
            
            # 確保用戶存在於資料庫中
            user_info = get_line_profile(user_id)
            if user_info:
                db.add_user(user_id, user_info['name'], user_info['picture_url'])

            print(f"收到 Postback - 用戶ID: {user_id}, Data: {data}")
            handle_postback(user_id, data)

    return jsonify({"status": "ok"})

# ============ LINE 预约流程处理 ============ 

def handle_booking_start(user_id, week_offset=0):
    """开始预约流程：显示日期选择"""
    max_weeks = int(db.get_config('booking_window_weeks') or '2')
    week_offset = max(0, min(week_offset, max_weeks - 1))
    
    week_dates = get_week_dates(week_offset)
    date_card = flex.generate_date_selection_card(week_dates, week_offset, max_weeks)
    send_line_message(user_id, [date_card], message_type="date_selection")

def handle_postback(user_id, data):
    """处理 postback 事件"""
    params = {}
    for param in data.split('&'):
        if '=' in param:
            key, value = param.split('=', 1)
            params[key] = value
    
    action = params.get('action')
    
    if action == 'change_week':
        offset = int(params.get('offset', 0))
        handle_booking_start(user_id, offset)
    
    elif action == 'show_date_selection':
        handle_booking_start(user_id, 0)
    
    elif action == 'select_date':
        date = params.get('date')
        day_name = params.get('day_name')
        
        if not date or not day_name:
            return
        
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        weekday = date_obj.weekday()
        
        is_closed = db.is_closed_day(date)
        available_slots = get_available_slots(date, weekday)
        
        time_card = flex.generate_time_selection_card(date, day_name, available_slots, is_closed)
        send_line_message(user_id, [time_card], message_type="time_selection")
    
    elif action == 'select_time':
        date = params.get('date')
        day_name = params.get('day_name')
        time = params.get('time')
        
        if not date or not day_name or not time:
            return
        
        user = db.get_user_by_id(user_id)
        user_name = user['name'] if user else '未知'
        
        confirm_card = flex.generate_confirmation_card(date, day_name, time, user_name)
        send_line_message(user_id, [confirm_card], message_type="booking_confirmation", target_name=user_name)
    
    elif action == 'confirm_booking':
        date = params.get('date')
        time = params.get('time')
        
        if not date or not time:
            return
        
        user = db.get_user_by_id(user_id)
        user_name = user['name'] if user else '未知'
        
        success = db.add_appointment(user_id, user_name, date, time)
        
        if success:
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            weekday_names = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
            weekday_name = weekday_names[date_obj.weekday()]
            
            success_msg = f"✅ 預約成功！\n\n日期：{date_obj.month}月{date_obj.day}日 ({weekday_name})\n時間：{time}\n姓名：{user_name}\n\n我們會在預約前提醒您，謝謝！"
            send_line_message(user_id, [{"type": "text", "text": success_msg}], message_type="booking_success", target_name=user_name)
        else:
            error_msg = "❌ 預約失敗，該時段可能已被預約。請重新選擇。"
            send_line_message(user_id, [{"type": "text", "text": error_msg}], message_type="booking_error", target_name=user_name)

def handle_query_appointments(user_id):
    """查询用户的预约"""
    today = datetime.now(TAIPEI_TZ).date()
    
    appointments = db.get_appointments_by_user(user_id)
    future_apts = [apt for apt in appointments 
                   if datetime.strptime(apt['date'], '%Y-%m-%d').date() >= today
                   and apt['status'] == 'confirmed']
    
    if not future_apts:
        msg = "您目前沒有預約記錄。\n\n如需預約，請輸入「預約」。"
    else:
        msg = "📅 您的預約記錄：\n\n"
        for apt in sorted(future_apts, key=lambda x: (x['date'], x['time'])):
            date_obj = datetime.strptime(apt['date'], '%Y-%m-%d')
            weekday_names = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
            weekday_name = weekday_names[date_obj.weekday()]
            msg += f"• {date_obj.month}月{date_obj.day}日 ({weekday_name}) {apt['time']}\n"
        msg += "\n如需取消預約，請輸入「取消」。"
    
    send_line_message(user_id, [{"type": "text", "text": msg}], message_type="appointment_list")

def handle_cancel_booking(user_id):
    """处理取消预约"""
    today = datetime.now(TAIPEI_TZ).date()
    appointments = db.get_appointments_by_user(user_id)
    future_apts = [apt for apt in appointments 
                   if datetime.strptime(apt['date'], '%Y-%m-%d').date() >= today
                   and apt['status'] == 'confirmed']
    
    if not future_apts:
        msg = "您目前沒有可取消的預約。"
        send_line_message(user_id, [{"type": "text", "text": msg}], message_type="cancel_booking_error")
    else:
        apt = sorted(future_apts, key=lambda x: (x['date'], x['time']))[0]
        db.cancel_appointment(apt['date'], apt['time'])
        
        date_obj = datetime.strptime(apt['date'], '%Y-%m-%d')
        weekday_names = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
        weekday_name = weekday_names[date_obj.weekday()]
        
        msg = f"✅ 已取消預約\n\n日期：{date_obj.month}月{date_obj.day}日 ({weekday_name})\n時間：{apt['time']}"
        send_line_message(user_id, [{"type": "text", "text": msg}], message_type="cancel_booking_success")

def send_daily_reminders_job():
    """每日提醒的排程任務"""
    if db.get_config('auto_reminder_enabled', 'false') == 'true':
        print(f"[{datetime.now(TAIPEI_TZ)}] 執行每日自動提醒...")
        today_str = datetime.now(TAIPEI_TZ).strftime('%Y-%m-%d')
        appointments = db.get_appointments_by_date_range(today_str, today_str)
        appointments = [apt for apt in appointments if apt['status'] == 'confirmed']
        if appointments:
            sent, failed = _do_send_reminders(appointments)
            print(f"每日提醒發送完成: {sent} 成功, {failed} 失敗。")
        else:
            print("今日無預約，不執行提醒。")

def send_weekly_reminders_job():
    """每週提醒的排程任務"""
    if db.get_config('auto_reminder_enabled', 'false') == 'true':
        print(f"[{datetime.now(TAIPEI_TZ)}] 執行每週自動提醒...")
        # 預設為下週的預約
        week_dates = get_week_dates(week_offset=1)
        start_date = week_dates[0]['date']
        end_date = week_dates[-1]['date']
        appointments = db.get_appointments_by_date_range(start_date, end_date)
        appointments = [apt for apt in appointments if apt['status'] == 'confirmed']
        if appointments:
            sent, failed = _do_send_reminders(appointments)
            print(f"每週提醒發送完成: {sent} 成功, {failed} 失敗。")
        else:
            print("下週無預約，不執行提醒。")

@app.route("/add_schedule", methods=["POST"])
def add_schedule_route():
    import json
    data = request.get_json()
    user_id = data.get("user_id")
    user_name = data.get("user_name")
    send_time = data.get("send_time")
    message = data.get("message")
    
    if not all([user_id, send_time, message]):
        return jsonify({"status": "error", "message": "缺少必要欄位"}), 400
    
    # 這裡應改為寫入資料庫的邏輯
    return jsonify({"status": "error", "message": "此功能尚未與資料庫整合"}), 501

@app.route("/list_schedules")
def list_schedules():
    return jsonify({"schedules": [], "count": 0})

@app.route("/delete_schedule/<schedule_id>")
def delete_schedule_route(schedule_id):
    return jsonify({"status": "error", "message": "此功能尚未與資料庫整合"}), 501

# 初始化排程器
scheduler = BackgroundScheduler()
# 每日提醒，從設定檔讀取時間
daily_time_str = db.get_config('auto_reminder_daily_time', '09:00') or '09:00'
daily_time = daily_time_str.split(':')
scheduler.add_job(func=send_daily_reminders_job, trigger="cron", id='daily_reminder_job', hour=int(daily_time[0]), minute=int(daily_time[1]), timezone=TAIPEI_TZ)

# 每週提醒，從設定檔讀取星期與時間
weekly_day = db.get_config('auto_reminder_weekly_day', 'sun') or 'sun'
weekly_time_str = db.get_config('auto_reminder_weekly_time', '21:00') or '21:00'
weekly_time = weekly_time_str.split(':')
scheduler.add_job(func=send_weekly_reminders_job, trigger="cron", id='weekly_reminder_job', day_of_week=weekly_day, hour=int(weekly_time[0]), minute=int(weekly_time[1]), timezone=TAIPEI_TZ)

scheduler.start()
print("排程器已啟動。每日與每週提醒任務已設定。")

if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=5000, debug=False)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()