from flask import Flask, request, jsonify, render_template
import os
import requests
import json

app = Flask(__name__)

LINE_CHANNEL_TOKEN = os.getenv("LINE_CHANNEL_TOKEN")

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

@app.route("/")
def home():
    return render_template("admin.html")

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

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_json()
    events = body.get("events", [])

    for event in events:
        if event["type"] == "message" and event["message"]["type"] == "text":
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
                
                reply_message(user_id, f"你說了：{user_message}")
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
