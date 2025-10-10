from flask import Flask, request, jsonify, render_template
import os
import requests
import json
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import uuid
import pytz

app = Flask(__name__)

LINE_CHANNEL_TOKEN = os.getenv("LINE_CHANNEL_TOKEN")
TAIPEI_TZ = pytz.timezone('Asia/Taipei')

def load_users():
    try:
        with open('users.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            users_data = data.get('allowed_users', [])
            if users_data and isinstance(users_data[0], str):
                users_data = [{"user_id": uid, "name": "未知"} for uid in users_data]
            return users_data
    except FileNotFoundError:
        return []

def save_users(users):
    with open('users.json', 'w', encoding='utf-8') as f:
        json.dump({'allowed_users': users}, f, ensure_ascii=False, indent=2)

def save_user_with_name(user_id, name="未知"):
    users = load_users()
    user_ids = [u['user_id'] for u in users]
    if user_id not in user_ids:
        users.append({"user_id": user_id, "name": name})
        save_users(users)
        print(f"自動新增用戶：{name} ({user_id})")
    else:
        for user in users:
            if user['user_id'] == user_id and user['name'] == '未知' and name != '未知':
                user['name'] = name
                save_users(users)
                print(f"更新用戶姓名：{name} ({user_id})")
                break

def save_user(user_id):
    save_user_with_name(user_id)

def delete_user_from_list(user_id):
    users = load_users()
    users = [u for u in users if u['user_id'] != user_id]
    save_users(users)
    return True

def get_line_profile(user_id):
    url = f"https://api.line.me/v2/bot/profile/{user_id}"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}"
    }
    try:
        response = requests.get(url, headers=headers)
        print(f"LINE Profile API 回應: status={response.status_code}")
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

def load_schedules():
    try:
        with open('schedules.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('schedules', [])
    except FileNotFoundError:
        return []

def save_schedules(schedules):
    with open('schedules.json', 'w', encoding='utf-8') as f:
        json.dump({'schedules': schedules}, f, ensure_ascii=False, indent=2)

def add_schedule(user_id, user_name, send_time, message):
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
    return schedule_id

def delete_schedule(schedule_id):
    schedules = load_schedules()
    schedules = [s for s in schedules if s['id'] != schedule_id]
    save_schedules(schedules)
    return True

def check_and_send_schedules():
    schedules = load_schedules()
    # 使用台北時區（UTC+8）
    taipei_tz = pytz.timezone('Asia/Taipei')
    now = datetime.now(taipei_tz)
    updated = False
    
    for schedule in schedules:
        if schedule['status'] == 'pending':
            # 將排程時間解析為台北時區的時間
            send_time_naive = datetime.strptime(schedule['send_time'], "%Y-%m-%d %H:%M")
            send_time = taipei_tz.localize(send_time_naive)
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
                    else:
                        print(f"⚠️ 排程發送失敗（將重試 {schedule['retry_count']}/3）：{schedule['user_name']} - {schedule['message']}")
    
    if updated:
        save_schedules(schedules)

@app.route("/")
def home():
    return render_template("admin.html")

@app.route("/schedule")
def schedule():
    return render_template("schedule.html")

@app.route("/add_user/<user_id>")
def add_user(user_id):
    save_user(user_id)
    return jsonify({"status": "success", "message": f"已新增使用者：{user_id}"})

@app.route("/delete_user/<user_id>")
def delete_user(user_id):
    if delete_user_from_list(user_id):
        return jsonify({"status": "success", "message": f"已刪除使用者：{user_id}"})
    else:
        return jsonify({"status": "error", "message": "使用者不存在"})

@app.route("/list_users")
def list_users():
    users = load_users()
    return jsonify({"allowed_users": users, "count": len(users)})

@app.route("/update_user_name", methods=["POST"])
def update_user_name():
    data = request.get_json()
    user_id = data.get("user_id")
    new_name = data.get("name")
    
    if not user_id or not new_name:
        return jsonify({"status": "error", "message": "缺少必要欄位"}), 400
    
    users = load_users()
    user_found = False
    
    for user in users:
        if user['user_id'] == user_id:
            user['name'] = new_name
            user_found = True
            break
    
    if user_found:
        save_users(users)
        return jsonify({"status": "success", "message": f"已更新姓名為：{new_name}"})
    else:
        return jsonify({"status": "error", "message": "找不到用戶"}), 404

@app.route("/add_schedule", methods=["POST"])
def add_schedule_route():
    data = request.get_json()
    user_id = data.get("user_id")
    user_name = data.get("user_name")
    send_time = data.get("send_time")
    message = data.get("message")
    
    if not all([user_id, send_time, message]):
        return jsonify({"status": "error", "message": "缺少必要欄位"}), 400
    
    schedule_id = add_schedule(user_id, user_name, send_time, message)
    return jsonify({"status": "success", "message": "排程已新增", "schedule_id": schedule_id})

@app.route("/list_schedules")
def list_schedules():
    schedules = load_schedules()
    return jsonify({"schedules": schedules, "count": len(schedules)})

@app.route("/delete_schedule/<schedule_id>")
def delete_schedule_route(schedule_id):
    delete_schedule(schedule_id)
    return jsonify({"status": "success", "message": "排程已刪除"})

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_json()
    events = body.get("events", [])

    for event in events:
        # 處理用戶加好友事件
        if event["type"] == "follow":
            user_id = event["source"]["userId"]
            print(f"用戶加入好友 - 用戶ID: {user_id}")
            user_name = get_line_profile(user_id)
            save_user_with_name(user_id, user_name)
        
        # 處理訊息事件
        elif event["type"] == "message" and event["message"]["type"] == "text":
            user_id = event["source"]["userId"]
            user_message = event["message"]["text"]
            
            print(f"收到訊息 - 用戶ID: {user_id}, 訊息: {user_message}")

            allowed_users = load_users()
            user_ids = [u['user_id'] for u in allowed_users]
            
            if user_id in user_ids:
                # 檢查用戶姓名是否為"未知"，如果是則嘗試更新
                current_user = next((u for u in allowed_users if u['user_id'] == user_id), None)
                if current_user and current_user.get('name') == '未知':
                    user_name = get_line_profile(user_id)
                    save_user_with_name(user_id, user_name)
                # 不發送任何回應
            else:
                user_name = get_line_profile(user_id)
                save_user_with_name(user_id, user_name)

    return jsonify({"status": "ok"})

def reply_message(user_id, text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}"
    }
    data = {
        "to": user_id,
        "messages": [{"type": "text", "text": text}]
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        print(f"Error sending message: {response.status_code}, {response.text}")
        return False
    return True

# ============ 預約管理功能 ============

def load_appointments():
    try:
        with open('appointments.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"appointments": []}

def save_appointments(appointments_data):
    with open('appointments.json', 'w', encoding='utf-8') as f:
        json.dump(appointments_data, f, ensure_ascii=False, indent=2)

def get_week_dates(start_date=None):
    """獲取本週的日期（週一到週日）"""
    if start_date is None:
        start_date = datetime.now(TAIPEI_TZ).date()
    
    # 找到本週的週一
    weekday = start_date.weekday()
    monday = start_date - timedelta(days=weekday)
    
    # 生成週二到週六的日期
    week_dates = {}
    for i in range(1, 6):  # 1=週二, 2=週三, ..., 5=週六
        date = monday + timedelta(days=i)
        day_name = ['週一', '週二', '週三', '週四', '週五', '週六', '週日'][i]
        week_dates[i] = {
            'date': date.strftime('%Y-%m-%d'),
            'display': f"{date.month}/{date.day}",
            'day_name': day_name,
            'weekday': i
        }
    
    return week_dates

def generate_time_slots(weekday):
    """根據星期生成時間段"""
    slots = []
    if weekday in [1, 3, 5]:  # 週二、週四、週六：14:00-18:00
        start_hour = 14
        end_hour = 18
        # 二四六要包含 18:00
        for hour in range(start_hour, end_hour):
            for minute in [0, 15, 30, 45]:
                time_str = f"{hour:02d}:{minute:02d}"
                slots.append(time_str)
        slots.append("18:00")  # 加入最後的 18:00
    elif weekday in [2, 4]:  # 週三、週五：18:00-21:00
        start_hour = 18
        end_hour = 21
        for hour in range(start_hour, end_hour):
            for minute in [0, 15, 30, 45]:
                time_str = f"{hour:02d}:{minute:02d}"
                slots.append(time_str)
    else:
        return []
    
    return slots

@app.route("/appointments")
def appointments_page():
    return render_template("appointments.html")

@app.route("/get_week_appointments")
def get_week_appointments():
    week_dates = get_week_dates()
    appointments_data = load_appointments()
    
    # 組織本週的預約數據
    week_schedule = {}
    for weekday, date_info in week_dates.items():
        date_str = date_info['date']
        time_slots = generate_time_slots(weekday)
        
        day_appointments = {}
        for time_slot in time_slots:
            # 查找該日期時段的預約
            appointment = next(
                (apt for apt in appointments_data.get('appointments', [])
                 if apt['date'] == date_str and apt['time'] == time_slot),
                None
            )
            day_appointments[time_slot] = {
                'user_name': appointment['user_name'] if appointment else '',
                'user_id': appointment['user_id'] if appointment else ''
            }
        
        week_schedule[weekday] = {
            'date_info': date_info,
            'appointments': day_appointments
        }
    
    return jsonify(week_schedule)

@app.route("/save_appointment", methods=["POST"])
def save_appointment():
    data = request.get_json()
    date = data.get('date')
    time = data.get('time')
    user_name = data.get('user_name')
    user_id = data.get('user_id', '')
    
    appointments_data = load_appointments()
    appointments = appointments_data.get('appointments', [])
    
    # 移除該時段的舊預約
    appointments = [apt for apt in appointments 
                   if not (apt['date'] == date and apt['time'] == time)]
    
    # 如果有選擇用戶，則添加新預約
    if user_name:
        appointments.append({
            'date': date,
            'time': time,
            'user_name': user_name,
            'user_id': user_id
        })
    
    appointments_data['appointments'] = appointments
    save_appointments(appointments_data)
    
    return jsonify({"status": "success"})

@app.route("/send_appointment_reminders", methods=["POST"])
def send_appointment_reminders():
    data = request.get_json()
    send_type = data.get('type', 'week')  # 'week' or 'day'
    target_date = data.get('date', '')  # 如果是 'day'，需要指定日期
    
    appointments_data = load_appointments()
    appointments = appointments_data.get('appointments', [])
    
    # 篩選要發送的預約
    if send_type == 'day' and target_date:
        target_appointments = [apt for apt in appointments if apt['date'] == target_date]
    else:  # week
        week_dates = get_week_dates()
        week_date_strs = [info['date'] for info in week_dates.values()]
        target_appointments = [apt for apt in appointments if apt['date'] in week_date_strs]
    
    sent_count = 0
    failed_count = 0
    
    for apt in target_appointments:
        if apt.get('user_id'):
            # 格式化日期和時間
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

# 初始化排程器（在模組層級啟動，確保無論如何啟動都會執行）
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_and_send_schedules, trigger="interval", seconds=30)
scheduler.start()
print("🚀 排程檢查器已啟動，每30秒檢查一次待發送訊息")

if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=5000)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
