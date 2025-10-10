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
            return data.get('allowed_users', [])
    except FileNotFoundError:
        return []

def save_users(users):
    with open('users.json', 'w', encoding='utf-8') as f:
        json.dump({'allowed_users': users}, f, ensure_ascii=False, indent=2)

def save_user(user_id):
    users = load_users()
    if user_id not in users:
        users.append(user_id)
        save_users(users)

def delete_user_from_list(user_id):
    users = load_users()
    if user_id in users:
        users.remove(user_id)
        save_users(users)
        return True
    return False

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

            allowed_users = load_users()
            if user_id in allowed_users:
                reply_message(user_id, f"你說了：{user_message}")

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
