from flask import Flask, request, jsonify, render_template
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

def send_line_message(user_id, messages):
    """发送 LINE 消息（支持文本和 Flex Message）"""
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}"
    }
    
    # 确保 messages 是列表格式
    if not isinstance(messages, list):
        messages = [messages]
    
    data = {
        "to": user_id,
        "messages": messages
    }
    
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        print(f"Error sending message: {response.status_code}, {response.text}")
        return False
    return True

def reply_message(user_id, text):
    """发送文本消息（兼容旧代码）"""
    return send_line_message(user_id, [{"type": "text", "text": text}])

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
            'display': date.strftime('%m/%d')  # 添加格式化的日期显示
        })
    
    return week_dates

def generate_time_slots(weekday):
    """根据星期生成时间段"""
    slots = []
    if weekday in [1, 3]:  # 週二、週四：14:00-18:00（17个时段）
        for hour in range(14, 18):
            for minute in [0, 15, 30, 45]:
                slots.append(f"{hour:02d}:{minute:02d}")
        slots.append("18:00")  # 18:00 结束
    elif weekday == 5:  # 週六：10:00-18:00（33个时段）
        for hour in range(10, 18):
            for minute in [0, 15, 30, 45]:
                slots.append(f"{hour:02d}:{minute:02d}")
        slots.append("18:00")  # 18:00 结束
    elif weekday in [2, 4]:  # 週三、週五：18:00-21:00（13个时段）
        for hour in range(18, 21):
            for minute in [0, 15, 30, 45]:
                slots.append(f"{hour:02d}:{minute:02d}")
        slots.append("21:00")  # 21:00 结束
    return slots

def get_available_slots(date, weekday):
    """获取某日期的可用时段（过滤掉已过去的时间）"""
    all_slots = generate_time_slots(weekday)
    
    # 检查是否休诊
    if db.is_closed_day(date):
        return []
    
    # 获取已预约的时段
    appointments = db.get_appointments_by_date_range(date, date)
    booked_times = [apt['time'] for apt in appointments if apt['status'] == 'confirmed']
    
    # 过滤掉已过去的时段
    now = datetime.now(TAIPEI_TZ)
    date_obj = datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=TAIPEI_TZ)
    
    filtered_slots = []
    for slot in all_slots:
        if slot not in booked_times:
            # 如果是今天，检查时间是否已过
            if date == now.strftime('%Y-%m-%d'):
                slot_time = datetime.strptime(f"{date} {slot}", '%Y-%m-%d %H:%M').replace(tzinfo=TAIPEI_TZ)
                if slot_time > now:
                    filtered_slots.append(slot)
            else:
                # 未来的日期，保留所有未预约的时段
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

# ============ 预约管理 API ============

@app.route("/get_week_appointments")
def get_week_appointments():
    week_offset = int(request.args.get('offset', 0))
    week_dates = get_week_dates(week_offset)
    
    # 组织本周的预约数据
    week_schedule = {}
    all_users = db.get_all_users()
    
    for date_info in week_dates:
        date_str = date_info['date']
        weekday = date_info['weekday']
        time_slots = generate_time_slots(weekday)
        
        # 获取该日期的所有预约
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
    
    return jsonify({
        'week_schedule': week_schedule,
        'users': all_users,
        'week_offset': week_offset
    })

@app.route("/save_appointment", methods=["POST"])
def save_appointment():
    data = request.get_json()
    date = data.get('date')
    time = data.get('time')
    user_name = data.get('user_name')
    user_id = data.get('user_id', '')
    
    # 先取消该时段的旧预约
    db.cancel_appointment(date, time)
    
    # 如果有选择用户，则添加新预约
    if user_name and user_id:
        db.add_appointment(user_id, user_name, date, time)
    
    return jsonify({"status": "success"})

@app.route("/send_appointment_reminders", methods=["POST"])
def send_appointment_reminders():
    data = request.get_json()
    send_type = data.get('type', 'week')
    target_date = data.get('date', '')
    
    # 筛选要发送的预约
    if send_type == 'day' and target_date:
        appointments = db.get_appointments_by_date_range(target_date, target_date)
    else:  # week
        week_dates = get_week_dates()
        start_date = week_dates[0]['date']
        end_date = week_dates[-1]['date']
        appointments = db.get_appointments_by_date_range(start_date, end_date)
    
    # 只发送 confirmed 状态的预约
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
    
    # 设置休诊并自动取消该日预约
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
    
    # 验证 booking_window_weeks 只能是 2 或 4
    if key == 'booking_window_weeks' and value not in ['2', '4']:
        return jsonify({"status": "error", "message": "预约窗口只能设置为2周或4周"}), 400
    
    if db.set_config(key, value, description):
        return jsonify({"status": "success", "message": "配置已更新"})
    else:
        return jsonify({"status": "error", "message": "更新失败"}), 500

# ============ LINE Webhook ============

@app.route("/webhook", methods=["POST"])
def webhook():
    # 获取签名
    signature = request.headers.get('X-Line-Signature', '')
    
    # 获取原始请求体
    body_text = request.get_data(as_text=True)
    
    # 验证签名
    if not validate_signature(body_text, signature):
        print("❌ LINE Webhook 签名验证失败")
        return jsonify({"status": "error", "message": "Invalid signature"}), 403
    
    body = request.get_json()
    events = body.get("events", [])

    for event in events:
        # 处理用户加好友事件
        if event["type"] == "follow":
            user_id = event["source"]["userId"]
            print(f"用戶加入好友 - 用戶ID: {user_id}")
            user_name = get_line_profile(user_id)
            db.add_user(user_id, user_name)
        
        # 处理文本消息
        elif event["type"] == "message" and event["message"]["type"] == "text":
            user_id = event["source"]["userId"]
            user_message = event["message"]["text"].strip()
            
            print(f"收到訊息 - 用戶ID: {user_id}, 訊息: {user_message}")
            
            # 自动注册用户
            users = db.get_all_users()
            user_ids = [u['user_id'] for u in users]
            
            if user_id not in user_ids:
                user_name = get_line_profile(user_id)
                db.add_user(user_id, user_name)
            
            # 处理预约命令
            if user_message in ['預約', '预约', '訂位', '订位']:
                handle_booking_start(user_id)
            elif user_message in ['查詢', '查询', '我的預約', '我的预约']:
                handle_query_appointments(user_id)
            elif user_message in ['取消', '取消預約', '取消预约']:
                handle_cancel_booking(user_id)
        
        # 处理 postback 事件（按钮点击）
        elif event["type"] == "postback":
            user_id = event["source"]["userId"]
            data = event["postback"]["data"]
            
            print(f"收到 Postback - 用戶ID: {user_id}, Data: {data}")
            handle_postback(user_id, data)

    return jsonify({"status": "ok"})

# ============ LINE 预约流程处理 ============

def handle_booking_start(user_id, week_offset=0):
    """开始预约流程：显示日期选择"""
    # 获取配置的最大预约周数
    max_weeks = int(db.get_config('booking_window_weeks') or '2')
    
    # 限制 week_offset 在有效范围内
    week_offset = max(0, min(week_offset, max_weeks - 1))
    
    week_dates = get_week_dates(week_offset)
    date_card = flex.generate_date_selection_card(week_dates, week_offset, max_weeks)
    send_line_message(user_id, [date_card])

def handle_postback(user_id, data):
    """处理 postback 事件"""
    # 解析 postback 数据
    params = {}
    for param in data.split('&'):
        if '=' in param:
            key, value = param.split('=', 1)
            params[key] = value
    
    action = params.get('action')
    
    if action == 'change_week':
        # 切换周次
        offset = int(params.get('offset', 0))
        handle_booking_start(user_id, offset)
    
    elif action == 'show_date_selection':
        # 返回日期选择
        handle_booking_start(user_id, 0)
    
    elif action == 'select_date':
        # 选择日期后，显示时段选择
        date = params.get('date')
        day_name = params.get('day_name')
        
        if not date or not day_name:
            return
        
        # 获取星期数
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        weekday = date_obj.weekday()
        
        # 检查是否休诊
        is_closed = db.is_closed_day(date)
        
        # 获取可用时段
        available_slots = get_available_slots(date, weekday)
        
        # 生成时段选择卡片
        time_card = flex.generate_time_selection_card(date, day_name, available_slots, is_closed)
        send_line_message(user_id, [time_card])
    
    elif action == 'select_time':
        # 选择时段后，显示确认卡片
        date = params.get('date')
        day_name = params.get('day_name')
        time = params.get('time')
        
        if not date or not day_name or not time:
            return
        
        # 获取用户姓名
        user = db.get_user_by_id(user_id)
        user_name = user['name'] if user else '未知'
        
        # 生成确认卡片
        confirm_card = flex.generate_confirmation_card(date, day_name, time, user_name)
        send_line_message(user_id, [confirm_card])
    
    elif action == 'confirm_booking':
        # 确认预约
        date = params.get('date')
        time = params.get('time')
        
        if not date or not time:
            return
        
        # 获取用户信息
        user = db.get_user_by_id(user_id)
        user_name = user['name'] if user else '未知'
        
        # 添加预约
        success = db.add_appointment(user_id, user_name, date, time)
        
        if success:
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            weekday_names = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
            weekday_name = weekday_names[date_obj.weekday()]
            
            success_msg = f"✅ 預約成功！\n\n日期：{date_obj.month}月{date_obj.day}日 ({weekday_name})\n時間：{time}\n姓名：{user_name}\n\n我們會在預約前提醒您，謝謝！"
            send_line_message(user_id, [{"type": "text", "text": success_msg}])
        else:
            error_msg = "❌ 預約失敗，該時段可能已被預約。請重新選擇。"
            send_line_message(user_id, [{"type": "text", "text": error_msg}])

def handle_query_appointments(user_id):
    """查询用户的预约"""
    # 获取用户的所有预约（未来7天）
    today = datetime.now(TAIPEI_TZ).date()
    end_date = today + timedelta(days=7)
    
    appointments = db.get_appointments_by_user(user_id)
    # 只显示未来的预约
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
    
    send_line_message(user_id, [{"type": "text", "text": msg}])

def handle_cancel_booking(user_id):
    """处理取消预约"""
    # 获取用户的预约
    today = datetime.now(TAIPEI_TZ).date()
    appointments = db.get_appointments_by_user(user_id)
    future_apts = [apt for apt in appointments 
                   if datetime.strptime(apt['date'], '%Y-%m-%d').date() >= today
                   and apt['status'] == 'confirmed']
    
    if not future_apts:
        msg = "您目前沒有可取消的預約。"
        send_line_message(user_id, [{"type": "text", "text": msg}])
    else:
        # 取消最近的一个预约
        apt = sorted(future_apts, key=lambda x: (x['date'], x['time']))[0]
        db.cancel_appointment(apt['date'], apt['time'])
        
        date_obj = datetime.strptime(apt['date'], '%Y-%m-%d')
        weekday_names = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
        weekday_name = weekday_names[date_obj.weekday()]
        
        msg = f"✅ 已取消預約\n\n日期：{date_obj.month}月{date_obj.day}日 ({weekday_name})\n時間：{apt['time']}"
        send_line_message(user_id, [{"type": "text", "text": msg}])

# ============ 排程系统（保留旧功能）============

# 这部分暂时保留 JSON 方式，后续可迁移到数据库
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
        app.run(host="0.0.0.0", port=5000)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
