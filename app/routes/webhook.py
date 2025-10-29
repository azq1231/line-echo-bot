from flask import Blueprint, request, jsonify, current_app
from datetime import datetime

import database as db
import line_flex_messages as flex
from app.utils.line_api import validate_signature, get_line_profile, send_line_message
from app.utils.helpers import get_week_dates, get_available_slots

webhook_bp = Blueprint('webhook', __name__)

@webhook_bp.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get('X-Line-Signature', '')
    body_text = request.get_data(as_text=True)
    
    if not validate_signature(body_text, signature):
        current_app.logger.error("❌ LINE Webhook 签名验证失败")
        return jsonify({"status": "error", "message": "Invalid signature"}), 403
    
    body = request.get_json()
    events = body.get("events", [])

    for event in events:
        if event["type"] == "follow":
            user_id = event["source"]["userId"]
            current_app.logger.info(f"用戶加入好友 - 用戶ID: {user_id}")
            user_info = get_line_profile(user_id)
            db.add_user(user_id, user_info['name'], user_info['picture_url'])
        
        elif event["type"] == "message":
            user_id = event["source"]["userId"]
            message_type = event["message"]["type"]
            current_app.logger.info(f"收到訊息 - 用戶ID: {user_id}, 類型: {message_type}")
            
            user_info = get_line_profile(user_id)
            db.add_user(user_id, user_info['name'], user_info['picture_url'], address=None)
            
            if message_type == "text":
                user_message = event["message"]["text"].strip()

                upcoming_appointment = db.get_closest_future_appointment(user_id)
                if upcoming_appointment:
                    db.update_appointment_reply_status(
                        appointment_id=upcoming_appointment['id'],
                        status='已回覆',
                        last_reply=user_message
                    )

                if user_message in ['預約', '预约', '訂位', '订位']:
                    handle_booking_start(user_id)
                elif user_message in ['查詢', '查询', '我的預約', '我的预约']:
                    handle_query_appointments(user_id)
                elif user_message in ['取消', '取消預約', '取消预约']:
                    handle_cancel_booking(user_id)
        
        elif event["type"] == "postback":
            user_id = event["source"]["userId"]
            data = event["postback"]["data"]
            
            user_info = get_line_profile(user_id)
            if user_info:
                db.add_user(user_id, user_info['name'], user_info['picture_url'])

            current_app.logger.info(f"收到 Postback - 用戶ID: {user_id}, Data: {data}")
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
        
        if not date or not day_name: return
        
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
        
        if not date or not day_name or not time: return
        
        user = db.get_user_by_id(user_id)
        user_name = user['name'] if user else '未知'
        
        confirm_card = flex.generate_confirmation_card(date, day_name, time, user_name)
        send_line_message(user_id, [confirm_card], message_type="booking_confirmation", target_name=user_name)
    
    elif action == 'confirm_booking':
        date = params.get('date')
        time = params.get('time')
        
        if not date or not time: return
        
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
    # This function needs TAIPEI_TZ, which should be accessed via current_app
    TAIPEI_TZ = current_app.config['TAIPEI_TZ']
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
    TAIPEI_TZ = current_app.config['TAIPEI_TZ']
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