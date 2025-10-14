from flask import Flask, request, jsonify, render_template, flash, redirect, url_for
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

app = Flask(__name__)
app.secret_key = os.urandom(24) # for flash messages

LINE_CHANNEL_TOKEN = os.getenv("LINE_CHANNEL_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
TAIPEI_TZ = pytz.timezone('Asia/Taipei')

# 初始化数据库
db.init_database()

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
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            profile = response.json()
            display_name = profile.get('displayName', '未知')
            print(f"成功獲取用戶姓名：{display_name}")
            return display_name
        else:
            print(f"LINE Profile API 錯誤: {response.text}")
    except Exception as e:
        print(f"獲取用戶資料時發生錯誤: {e}")
    return '未知'

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
        response = requests.post(url, headers=headers, json=data)
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

# ============ WEB 路由 ============ 

@app.route("/")
def home():
    return render_template("admin.html")

@app.route("/schedule")
def schedule():
    return render_template("schedule.html")

@app.route("/appointments")
def appointments_page():
    return render_template("appointments.html")

@app.route("/closed_days")
def closed_days_page():
    return render_template("closed_days.html")

@app.route("/stats")
def stats_page():
    # 獲取月份參數，預設為當前月份
    current_month = request.args.get('month', datetime.now(TAIPEI_TZ).strftime('%Y-%m'))
    message_type = request.args.get('type')
    
    # 獲取統計數據
    stats_data = db.get_message_stats(
        month=current_month,
        message_type=message_type if message_type else None
    )
    
    return render_template('stats.html', 
                         stats=stats_data,
                         current_month=current_month)

@app.route("/api/message_stats")
def message_stats_api():
    month = request.args.get('month')
    message_type = request.args.get('type')
    user_id = request.args.get('user')
    
    stats_data = db.get_message_stats(month, user_id, message_type)
    
    return jsonify(stats_data)

# ============ Web Booking Site ============ 

@app.route("/booking/", methods=["GET", "POST"])
def booking_page():
    if request.method == "POST":
        phone = request.form.get('phone')
        date = request.form.get('date')
        time = request.form.get('time')

        if phone is None or date is None or time is None:
            flash("預約資料不完整，請重試。", "danger")
            return redirect(url_for('booking_page'))

        user = db.get_or_create_user_by_phone(phone)
        
        success = db.add_appointment(
            user_id=user['user_id'],
            user_name=user['name'],
            date=date,
            time=time
        )

        if success:
            flash(f"恭喜！您已成功預約 {date} {time} 的時段。", "success")
        else:
            flash(f"抱歉，{date} {time} 的時段已被預約，請選擇其他時段。", "danger")
        
        return redirect(url_for('booking_page', phone=phone))

    phone = request.args.get('phone', '')
    schedule_data = None

    if phone:
        week_dates = get_week_dates(week_offset=0)
        schedule_data = []
        for day in week_dates:
            available_slots = get_available_slots(day['date'], day['weekday'])
            all_slots = generate_time_slots(day['weekday'])
            day_schedule = {
                'date': day['date'],
                'display': day['display'],
                'day_name': day['day_name'],
                'slots': []
            }
            for slot in all_slots:
                day_schedule['slots'].append({
                    'time': slot,
                    'available': slot in available_slots
                })
            schedule_data.append(day_schedule)

    return render_template("booking.html", phone=phone, schedule=schedule_data)

# ============ 用户管理 API ============ 

@app.route("/list_users")
def list_users():
    users = db.get_all_users()
    return jsonify({"allowed_users": users, "count": len(users)})

@app.route("/add_user/<user_id>")
def add_user(user_id):
    db.add_user(user_id, "未知")
    return jsonify({"status": "success", "message": f"已新增使用者：{user_id}"})

@app.route("/delete_user/<user_id>")
def delete_user(user_id):
    if db.delete_user(user_id):
        return jsonify({"status": "success", "message": f"已刪除使用者：{user_id}"})
    else:
        return jsonify({"status": "error", "message": "使用者不存在"})

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
    
    sent_count = 0
    failed_count = 0
    
    for apt in appointments:
        if apt.get('user_id'):
            date_obj = datetime.strptime(apt['date'], '%Y-%m-%d')
            weekday_names = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
            weekday_name = weekday_names[date_obj.weekday()]
            
            message = f"您預約的時間是{date_obj.month}月{date_obj.day}日 {weekday_name} {apt['time']}，謝謝"
            
            success = reply_message(apt['user_id'], message)
            db.log_message(
                user_id=apt['user_id'], 
                msg_type='reminder', 
                content=message, 
                status='success' if success else 'failed'
            )
            if success:
                sent_count += 1
            else:
                failed_count += 1
    
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
            user_name = get_line_profile(user_id)
            db.add_user(user_id, user_name)
        
        elif event["type"] == "message" and event["message"]["type"] == "text":
            user_id = event["source"]["userId"]
            user_message = event["message"]["text"].strip()
            
            print(f"收到訊息 - 用戶ID: {user_id}, 訊息: {user_message}")
            
            # 每次收到訊息都嘗試更新用戶資料，db.add_user 會處理衝突
            user_name = get_line_profile(user_id)
            db.add_user(user_id, user_name)
            
            if user_message in ['預約', '预约', '訂位', '订位']:
                handle_booking_start(user_id)
            elif user_message in ['查詢', '查询', '我的預約', '我的预约']:
                handle_query_appointments(user_id)
            elif user_message in ['取消', '取消預約', '取消预约']:
                handle_cancel_booking(user_id)
        
        elif event["type"] == "postback":
            user_id = event["source"]["userId"]
            data = event["postback"]["data"]
            
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

# ============ 訊息統計 ============

@app.route('/stats')
def message_stats():
    """顯示訊息發送統計資料"""
    month = request.args.get('month')
    if not month:
        # 預設顯示當月
        month = datetime.now(TAIPEI_TZ).strftime('%Y-%m')
    
    user_id = request.args.get('user_id')
    message_type = request.args.get('type')
    
    stats = db.get_message_stats(month, user_id, message_type)
    
    return render_template(
        'stats.html',
        stats=stats,
        current_month=month
    )

@app.route('/api/message_stats')
def api_message_stats():
    """API端點，返回訊息統計資料"""
    month = request.args.get('month', datetime.now(TAIPEI_TZ).strftime('%Y-%m'))
    user_id = request.args.get('user_id')
    message_type = request.args.get('type')
    
    stats = db.get_message_stats(month, user_id, message_type)
    return jsonify(stats)

# ============ 排程系统（保留旧功能）============ 

def load_schedules():
    import json
    try:
        with open('schedules.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('schedules', [])
    except FileNotFoundError:
        return []

def save_schedules(schedules):
    import json
    with open('schedules.json', 'w', encoding='utf-8') as f:
        json.dump({'schedules': schedules}, f, ensure_ascii=False, indent=2)

def check_and_send_schedules():
    schedules = load_schedules()
    now = datetime.now(TAIPEI_TZ)
    updated = False
    
    for schedule in schedules:
        if schedule['status'] == 'pending':
            send_time_naive = datetime.strptime(schedule['send_time'], "%Y-%m-%d %H:%M")
            send_time = TAIPEI_TZ.localize(send_time_naive)
            if now >= send_time:
                success = reply_message(schedule['user_id'], schedule['message'])
                if success:
                    schedule['status'] = 'sent'
                    schedule['sent_at'] = now.strftime("%Y-%m-%d %H:%M:%S")
                    updated = True
                    print(f"✅ 已發送排程訊息給 {schedule['user_name']}: {schedule['message']}")
                else:
                    if 'retry_count' not in schedule:
                        schedule['retry_count'] = 0
                    schedule['retry_count'] += 1
                    updated = True
                    
                    if schedule['retry_count'] >= 3:
                        schedule['status'] = 'failed'
                        schedule['failed_at'] = now.strftime("%Y-%m-%d %H:%M:%S")
                        print(f"❌ 排程發送失敗（已重試3次）：{schedule['user_name']} - {schedule['message']}")
    
    if updated:
        save_schedules(schedules)

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
    
    schedules = load_schedules()
    schedule_id = str(uuid.uuid4())
    new_schedule = {
        "id": schedule_id,
        "user_id": user_id,
        "user_name": user_name,
        "send_time": send_time,
        "message": message,
        "status": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    schedules.append(new_schedule)
    save_schedules(schedules)
    return jsonify({"status": "success", "message": "排程已新增", "schedule_id": schedule_id})

@app.route("/list_schedules")
def list_schedules():
    schedules = load_schedules()
    return jsonify({"schedules": schedules, "count": len(schedules)})

@app.route("/delete_schedule/<schedule_id>")
def delete_schedule_route(schedule_id):
    schedules = load_schedules()
    schedules = [s for s in schedules if s['id'] != schedule_id]
    save_schedules(schedules)
    return jsonify({"status": "success", "message": "排程已刪除"})

# 初始化排程器
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_and_send_schedules, trigger="interval", seconds=30)
scheduler.start()
print("Scheduler started. Checking for messages to send every 30 seconds.")

if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=5000, debug=False)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()