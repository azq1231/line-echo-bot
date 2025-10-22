from flask import Flask, request, jsonify, render_template, flash, redirect, url_for, Response, session
import os
import requests
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import uuid
import hmac
import hashlib
from functools import wraps
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
    # 在生產環境中，FLASK_SECRET_KEY 必須被設定，否則會導致 session 失效
    raise ValueError("FLASK_SECRET_KEY 環境變數未設定。請在 .env 或環境中設定一個安全的隨機字串。")

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

# ============ 權限驗證裝飾器 ============

def admin_required(f):
    """
    一個裝飾器，用來驗證使用者是否為登入的管理員。
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. 檢查使用者是否登入
        if 'user' not in session or 'user_id' not in session['user']:
            flash('請先登入以存取此頁面。', 'warning')
            # 登入後將使用者導回原本想去的頁面
            return redirect(url_for('login', next=request.url))

        # 2. 檢查使用者是否具備管理員權限
        user_data = db.get_user_by_id(session['user']['user_id'])
        is_admin_in_db = user_data and user_data.get('is_admin')

        # 3. 如果資料庫中的權限與 session 不符，更新 session
        if 'is_admin' not in session['user'] or session['user']['is_admin'] != is_admin_in_db:
            session['user'] = db.get_user_by_id(session['user']['user_id']) # 直接用最新的資料庫物件覆蓋
            session.modified = True # 標記 session 已被修改

        # 4. 最終權限檢查
        if not is_admin_in_db:
            flash('您沒有權限存取此頁面。', 'danger')
            return redirect(url_for('booking_page')) # 導向首頁或沒有權限的頁面

        # 5. 如果驗證通過，執行原本的函式
        return f(*args, **kwargs)
    return decorated_function

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
    active_slots = db.get_active_slots_by_weekday(weekday)
    
    generated_slots = []
    for slot_setting in active_slots:
        start = datetime.strptime(slot_setting['start_time'], '%H:%M')
        end = datetime.strptime(slot_setting['end_time'], '%H:%M')
        
        current = start
        while current <= end:
            generated_slots.append(current.strftime('%H:%M'))
            current += timedelta(minutes=15)
            
    # 去重並排序
    slots = sorted(list(set(generated_slots)))
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
# 為了保護所有 /admin 路徑，建議將 admin_required 應用到所有相關路由

@app.route("/admin/") # 後台首頁
@admin_required
def admin_home():
    user = session.get('user')  # 從 session 中獲取已登入的使用者資訊
    # 從資料庫讀取設定，決定是否允許刪除用戶，預設為 'false'
    allow_deletion = db.get_config('allow_user_deletion', 'false') == 'true'
    return render_template("admin.html", user=user, allow_user_deletion=allow_deletion)

@app.route("/admin/schedule")
@admin_required
def schedule():
    user = session.get('user')
    if db.get_config('feature_schedule_enabled') == 'false':
        return "Feature disabled", 404
    return render_template("schedule.html", user=user)

@app.route("/admin/appointments")
@admin_required
def appointments_page():
    user = session.get('user')
    return render_template("appointments.html", user=user)

@app.route("/admin/closed_days")
@admin_required
def closed_days_page():
    user = session.get('user')
    if db.get_config('feature_closed_days_enabled') == 'false':
        return "Feature disabled", 404
    return render_template("closed_days.html", user=user)


@app.route("/admin/stats")
@admin_required
def stats_page():
    user = session.get('user')
    # 獲取月份參數，預設為當前月份
    current_month = request.args.get('month', datetime.now(TAIPEI_TZ).strftime('%Y-%m'))
    # 獲取其他篩選參數
    message_type = request.args.get('type', '')
    user_id = request.args.get('user', '')

    # 獲取所有用戶以供篩選
    all_users = db.get_all_users()
    
    # 獲取統計數據
    stats_data = db.get_message_stats(
        month=current_month,
        message_type=message_type or None, # 如果是空字串，傳遞 None 給資料庫查詢
        user_id=user_id or None
    )
    
    return render_template('stats.html', 
                         user=user,
                         stats=stats_data,
                         current_month=current_month,
                         all_users=all_users,
                         current_user=user_id,
                         current_type=message_type)

@app.route("/admin/configs")
@admin_required
def configs_page():
    user = session.get('user')
    """渲染系統設定頁面，並加入管理員列表"""
    all_configs_list = db.get_all_configs()
    # 將列表轉換為字典以便在模板中輕鬆訪問
    configs_dict = {c['key']: c['value'] for c in all_configs_list}
    
    # 為尚未設定的項目提供預設值
    configs_dict.setdefault('booking_window_weeks', '2')
    configs_dict.setdefault('allow_user_deletion', 'false')
    configs_dict.setdefault('feature_schedule_enabled', 'true')
    configs_dict.setdefault('feature_closed_days_enabled', 'true')
    configs_dict.setdefault('feature_booking_enabled', 'true')
    configs_dict.setdefault('auto_reminder_daily_enabled', 'false')
    configs_dict.setdefault('auto_reminder_daily_time', '09:00')
    configs_dict.setdefault('auto_reminder_weekly_enabled', 'false')
    configs_dict.setdefault('auto_reminder_weekly_day', 'sun')
    configs_dict.setdefault('auto_reminder_weekly_time', '21:00')
    configs_dict.setdefault('message_template_reminder', '提醒您，{user_name}，您的預約時間是 {date} {weekday} {time}，謝謝。')

    # 獲取所有管理員列表
    admins = [u for u in db.get_all_users() if u.get('is_admin')]

    return render_template("configs.html", user=user, configs=configs_dict, admins=admins)

@app.route('/admin/set_admin_status', methods=['POST'])
@admin_required
def set_admin_status():
    """手動新增或移除管理員"""
    user_id_to_change = request.form.get('user_id')
    action = request.form.get('action')

    if not user_id_to_change or not action:
        flash('缺少 User ID 或操作類型。', 'danger')
        return redirect(url_for('configs_page'))

    # 安全性檢查：不能修改自己的權限
    current_user_id = session.get('user', {}).get('user_id')
    if user_id_to_change == current_user_id:
        flash('無法修改自己的管理員權限。', 'warning')
        return redirect(url_for('configs_page'))

    # 檢查用戶是否存在
    user_to_modify = db.get_user_by_id(user_id_to_change)
    if not user_to_modify:
        flash(f'找不到 User ID 為 "{user_id_to_change}" 的使用者。請確認該使用者至少與機器人互動過一次。', 'danger')
        return redirect(url_for('configs_page'))

    is_admin = action == 'add'
    
    if db.update_user_admin_status(user_id_to_change, is_admin):
        action_text = "新增" if is_admin else "移除"
        flash(f'成功{action_text}使用者 {user_to_modify["name"]} 的管理員權限。', 'success')
    else:
        flash('更新權限時發生錯誤。', 'danger')

    return redirect(url_for('configs_page'))

@app.route("/admin/settings/slots")
@admin_required
def slots_settings_page():
    user = session.get('user')
    """渲染可預約時段設定頁面"""
    all_slots = db.get_all_available_slots()
    
    # 按星期分組
    slots_by_weekday = {i: [] for i in range(1, 6)} # 週二到週六
    for slot in all_slots:
        if slot['weekday'] in slots_by_weekday:
            slots_by_weekday[slot['weekday']].append(slot)
            
    return render_template("slots_settings.html", user=user, slots_by_weekday=slots_by_weekday)


# ============ 後台 API (需要 admin_required 保護) ============
@app.route("/api/admin/message_stats")
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

    # 如果有 'next' 參數，儲存到 session 中，以便 callback 處理
    next_param = request.args.get('next')
    if next_param:
        session['next_url'] = next_param
    
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

    # 將使用者資料存入資料庫 (db.add_user 會處理新增或更新)
    db.add_user(user_id, user_name, picture_url, address=None)

    # 從資料庫獲取完整的用戶資訊，包括 is_admin
    user_data_from_db = db.get_user_by_id(user_id)
    if not user_data_from_db:
        flash("登入失敗：無法獲取用戶資料。", "danger")
        return redirect(url_for('booking_page'))

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
        return redirect(next_url or url_for('admin_home'))
    # 否則，導向指定的公開頁面或預設的預約頁面
    return redirect(next_url or url_for('booking_page'))

@app.route('/logout')
def logout():
    """登出"""
    session.pop('user', None)
    flash("您已成功登出。", "info")
    return redirect(url_for('booking_page'))

@app.route("/", methods=["GET"])
def booking_page():
    if db.get_config('feature_booking_enabled') == 'false':
        return "Feature disabled", 404

    user_session = session.get('user') # 從 session 獲取用戶資訊
    schedule_data = None
    week_offset = 0 # 為 week_offset 提供預設值

    # 提前定義 max_weeks，避免未登入時出錯
    try:
        # 從資料庫獲取設定，如果不存在、為空或格式錯誤，則使用預設值 2
        max_weeks = int(db.get_config('booking_window_weeks', '2') or '2')
    except (ValueError, TypeError):
        max_weeks = 2  # 如果設定值無效（例如 'abc'），則使用預設值

    if user_session:
        # user_session 已經在 callback 或上次 booking_page 訪問時被完整填充，包含 is_admin
        user = user_session # 直接使用 session 中的完整 user 物件
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
    else:
        user = None # 確保未登入時 user 為 None

    return render_template("booking.html", user=user, schedule=schedule_data, week_offset=week_offset, max_weeks=max_weeks) # 這裡的 user 已經是完整的了

@app.route("/history", methods=["GET"])
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


# ============ 後台使用者管理 API (需要 admin_required 保護) ============ 

@app.route('/api/admin/users', methods=['GET']) # 新增：獲取所有使用者列表
@admin_required
def api_get_users():
    """
    提供所有使用者的列表 API。
    """
    users = db.get_all_users() # 假設 db.get_all_users() 返回一個字典列表
    
    # 取得當前登入的管理員 ID，避免在前端讓他自己移除自己的權限
    current_admin_id = session['user']['user_id'] if 'user' in session else None
    
    users_data = [
        {
            "id": user['user_id'], # 假設 'user_id' 是字典中的鍵
            "name": user['name'],
            "line_user_id": user['user_id'], # LINE user ID 在此作為主要 ID
            "is_admin": user.get('is_admin', False) # 預設為 False 如果未設定
        } for user in users
    ]
    return jsonify({
        "users": users_data,
        "current_admin_id": current_admin_id
    })

@app.route('/api/admin/users/<string:user_id>/toggle_admin', methods=['POST']) # 新增：切換管理員狀態
@admin_required
def api_toggle_admin(user_id):
    """
    切換指定使用者的管理員狀態。
    """
    # 安全性檢查：不能修改自己的權限
    if user_id == (session['user']['user_id'] if 'user' in session else None):
        return jsonify({"message": "無法修改自己的管理員權限。"}), 403

    user_to_modify = db.get_user_by_id(user_id)
    if not user_to_modify:
        return jsonify({"message": "找不到該使用者。"}), 404

    # 切換 is_admin 狀態
    new_admin_status = not user_to_modify.get('is_admin', False)
    
    # 假設 db.update_user_admin_status 存在於 database.py
    success = db.update_user_admin_status(user_id, new_admin_status)

    if success:
        action = "授予" if new_admin_status else "移除"
        return jsonify({
            "message": f"已成功為使用者 {user_to_modify['name']} {action}管理員權限。",
            "new_status": new_admin_status
        })
    else:
        return jsonify({"message": "更新管理員權限失敗。"}), 500

@app.route('/api/admin/users/add_manual', methods=['POST'])
@admin_required
def api_add_manual_user():
    """手動新增臨時用戶"""
    data = request.get_json()
    name = data.get('name')

    if not name or not name.strip():
        return jsonify({"status": "error", "message": "用戶名稱不能為空。"}), 400

    user_id = f"manual_{uuid.uuid4()}"
    new_user = db.add_manual_user(user_id, name.strip())

    if new_user:
        return jsonify({"status": "success", "message": "臨時用戶已成功新增。", "user": new_user})
    else:
        return jsonify({"status": "error", "message": "新增臨時用戶時發生錯誤。"}), 500

@app.route('/api/admin/users/merge', methods=['POST'])
@admin_required
def api_merge_users():
    """合併用戶"""
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


@app.route("/admin/refresh_user_profile/<user_id>", methods=["POST"])
def refresh_user_profile(user_id):
    """手動從 LINE 更新用戶的個人資料（特別是頭像）"""
    user_info = get_line_profile(user_id)
    if user_info and user_info['name'] != '未知':
        # add_user 包含智能更新邏輯：如果名稱被手動修改過，則只更新頭像
        db.add_user(user_id, user_info['name'], user_info['picture_url'], address=None)
        return jsonify({"status": "success", "message": "用戶資料已從 LINE 更新。"})
    else:
        return jsonify({"status": "error", "message": "從 LINE 獲取資料失敗。"}), 404

# 為了保持一致性，將這些 API 也加上 admin_required 裝飾器
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

@admin_required
@app.route("/admin/update_user_name", methods=["POST"])
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

@admin_required
@app.route("/admin/update_user_zhuyin", methods=["POST"])
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

@admin_required
@app.route("/admin/update_user_phone", methods=["POST"])
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

@admin_required
@app.route("/admin/update_user_address", methods=["POST"])
def update_user_address_route():
    """更新用戶地址"""
    data = request.get_json()
    user_id = data.get("user_id")
    address = data.get("address")

    if not user_id or address is None:
        return jsonify({"status": "error", "message": "缺少使用者 ID 或地址"}), 400

    if db.update_user_address(user_id, address):
        return jsonify({"status": "success", "message": "地址已更新"})
    else:
        return jsonify({"status": "error", "message": "更新失敗"}), 500

@admin_required
@app.route("/admin/generate_zhuyin/<user_id>", methods=["POST"])
def generate_zhuyin_route(user_id):
    new_zhuyin = db.generate_and_save_zhuyin(user_id)
    if new_zhuyin is not None:
        return jsonify({"status": "success", "zhuyin": new_zhuyin})
    else:
        return jsonify({"status": "error", "message": "生成失败"}), 404

# ============ 预约管理 API ============ 

@app.route("/api/admin/get_week_appointments")
def get_week_appointments():
    week_offset = int(request.args.get('offset', 0))
    print(f"get_week_appointments: offset={week_offset}")  # Add log

    week_dates = get_week_dates(week_offset)
    
    week_schedule = {}
    all_users = db.get_all_users()
    
    for date_info in week_dates:
        date_str = date_info['date']
        weekday = date_info['weekday']
        time_slots = generate_time_slots(weekday)
        
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
@app.route("/api/admin/save_appointment", methods=["POST"])
@admin_required
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

    # 從資料庫讀取訊息範本，若無則使用預設值
    default_template = '提醒您，{user_name}，您的預約時間是 {date} {weekday} {time}，謝謝。'
    template = db.get_config('message_template_reminder', default_template) or default_template
    
    for apt in appointments:
        user_id = apt.get('user_id')
        # 只對真實的 LINE 用戶 (ID 以 'U' 開頭) 發送提醒
        if user_id and user_id.startswith('U'):
            date_obj = datetime.strptime(apt['date'], '%Y-%m-%d')
            weekday_names = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
            weekday_name = weekday_names[date_obj.weekday()]
            
            # 準備用於範本的變數
            message = template.format(
                user_name=apt['user_name'],
                date=f"{date_obj.month}月{date_obj.day}日",
                weekday=weekday_name,
                time=apt['time']
            )
            
            success = send_line_message(
                user_id=user_id,
                messages=[{"type": "text", "text": message}],
                message_type='reminder',
                target_name=apt['user_name']
            )
            if success:
                sent_count += 1
            else:
                failed_count += 1
    return sent_count, failed_count

@app.route("/api/admin/send_appointment_reminders", methods=["POST"])
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
@admin_required

@app.route("/api/admin/closed_days")
def get_closed_days():
    closed_days = db.get_all_closed_days()
    return jsonify({"closed_days": closed_days})

@app.route("/api/admin/set_closed_day", methods=["POST"])
@admin_required
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

@app.route("/api/admin/remove_closed_day", methods=["POST"])
@admin_required
def remove_closed_day():
    data = request.get_json()
    date = data.get('date')
    
    if db.remove_closed_day(date):
        return jsonify({"status": "success", "message": "已移除休診設定"})
    else:
        return jsonify({"status": "error", "message": "未找到休診記錄"}), 404

# ============ 可用時段 API ============
@admin_required

@app.route("/api/admin/slots", methods=["POST"])
def api_add_slot():
    data = request.get_json()
    if db.add_available_slot(data['weekday'], data['start_time'], data['end_time'], data.get('note')):
        return jsonify({"status": "success", "message": "時段已新增"})
    else:
        return jsonify({"status": "error", "message": "新增失敗，該時段可能已存在"}), 409

@admin_required
@app.route("/api/admin/slots/<int:slot_id>", methods=["PUT"])
def api_update_slot(slot_id):
    data = request.get_json()
    if db.update_available_slot(
        slot_id,
        data['weekday'],
        data['start_time'],
        data['end_time'],
        data['active'],
        data.get('note')
    ):
        return jsonify({"status": "success", "message": "時段已更新"})
    else:
        return jsonify({"status": "error", "message": "更新失敗"}), 500

@admin_required
@app.route("/api/admin/slots/<int:slot_id>", methods=["DELETE"])
def api_delete_slot(slot_id):
    if db.delete_available_slot(slot_id):
        return jsonify({"status": "success", "message": "時段已刪除"})
    else:
        return jsonify({"status": "error", "message": "刪除失敗"}), 500

@admin_required
@app.route("/api/admin/slots/copy", methods=["POST"])
def api_copy_slots():
    data = request.get_json()
    source_weekday = data.get('source_weekday')
    target_weekdays = data.get('target_weekdays')

    if not source_weekday or not target_weekdays:
        return jsonify({"status": "error", "message": "來源或目標星期未選擇"}), 400

    inserted_count, _ = db.copy_slots(int(source_weekday), target_weekdays)
    if inserted_count > 0:
        return jsonify({"status": "success", "message": f"已成功複製設定，共新增 {inserted_count} 個時段。"})
    else:
        return jsonify({"status": "error", "message": "複製失敗，請確認來源星期有設定時段。"}), 400

# ============ 系统配置 API ============ 
@admin_required

@app.route("/api/admin/configs")
def get_config_api():
    configs = db.get_all_configs()
    return jsonify({"configs": configs})

@app.route("/api/admin/set_config", methods=["POST"])
@admin_required
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
            db.add_user(user_id, user_info['name'], user_info['picture_url'], address=None)
            
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
    if db.get_config('auto_reminder_daily_enabled', 'false') == 'true':
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
    if db.get_config('auto_reminder_weekly_enabled', 'false') == 'true':
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

def send_custom_schedules_job():
    """處理自訂排程訊息的背景任務"""
    with app.app_context():
        schedules_to_send = db.get_pending_schedules_to_send()
        if not schedules_to_send:
            return

        print(f"[{datetime.now(TAIPEI_TZ)}] 發現 {len(schedules_to_send)} 個待發送的排程...")
        for schedule in schedules_to_send:
            success = send_line_message(
                user_id=schedule['user_id'],
                messages=[{"type": "text", "text": schedule['message']}],
                message_type='custom_schedule',
                target_name=schedule['user_name']
            )
            
            new_status = 'sent' if success else 'failed'
            db.update_schedule_status(schedule['id'], new_status)
            print(f"  - 排程 {schedule['id']} 發送給 {schedule['user_name']}，狀態: {new_status}")

@app.route("/admin/add_schedule", methods=["POST"])
@admin_required
def add_schedule_route():
    import json
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

@app.route("/admin/list_schedules")
@admin_required
def list_schedules():
    schedules = db.get_all_schedules()
    return jsonify({"schedules": schedules, "count": len(schedules)})

@app.route("/admin/delete_schedule/<schedule_id>", methods=["DELETE"])
@admin_required
def delete_schedule_route(schedule_id):
    try:
        schedule_id = int(schedule_id)
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "無效的 ID 格式"}), 400
    if db.delete_schedule(schedule_id):
        return jsonify({"status": "success", "message": "排程已刪除"})
    else:
        return jsonify({"status": "error", "message": "刪除失敗，找不到該排程"}), 404

# ============ Flask CLI 指令 ============

@app.cli.command("set-admin")
def set_admin_command():
    """互動式設定管理員指令"""
    print("--- 設定管理員 ---")
    users = db.get_all_users()
    if not users:
        print("資料庫中沒有任何使用者。請先至少讓一位使用者登入系統。")
        return

    for i, user in enumerate(users):
        admin_tag = "[管理員]" if user.get('is_admin') else ""
        print(f"{i + 1}: {user['name']} ({user['user_id']}) {admin_tag}")
    
    try:
        choice = int(input("請輸入要設為管理員的使用者編號: ")) - 1
        if 0 <= choice < len(users):
            user_to_set = users[choice]
            db.update_user_admin_status(user_to_set['user_id'], True)
            print(f"✅ 已成功將 '{user_to_set['name']}' 設為管理員。")
        else:
            print("❌ 無效的選擇。")
    except ValueError:
        print("❌ 請輸入數字。")

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

# 每分鐘檢查一次自訂排程
scheduler.add_job(func=send_custom_schedules_job, trigger='interval', minutes=1, id='custom_schedule_job')

scheduler.start()
print("排程器已啟動。每日、每週及自訂排程任務已設定。")

if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=5000, debug=False)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()