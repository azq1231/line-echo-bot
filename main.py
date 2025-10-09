from flask import Flask, request, jsonify
import os
import requests

app = Flask(__name__)

LINE_CHANNEL_TOKEN = os.getenv("LINE_CHANNEL_TOKEN")  # 在 Replit 設定環境變數


@app.route("/")
def home():
    return "LINE Bot is running!"


@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_json()
    events = body.get("events", [])

    for event in events:
        if event["type"] == "message" and event["message"]["type"] == "text":
            user_id = event["source"]["userId"]
            user_message = event["message"]["text"]

            reply_message(user_id, f"你說了：{user_message}")

    return jsonify({"status": "ok"})


def reply_message(user_id, text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}"
    }
    data = {"to": user_id, "messages": [{"type": "text", "text": text}]}
    requests.post(url, headers=headers, json=data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
