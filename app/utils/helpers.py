import os
import json
from datetime import datetime, timedelta
from flask import url_for, current_app, jsonify

import database as db

def api_response(data=None, error=None, status_code=200):
    """通用的 API 回應包裝器"""
    if error:
        return jsonify({"status": "error", "message": error}), status_code
    return jsonify({"status": "success", **(data or {})}), status_code

def get_vue_assets(entry_point: str):
    """
    從 manifest.json 讀取 Vite 打包後的 JS 和 CSS 資源路徑。
    """
    static_folder = current_app.static_folder
    if not static_folder:
        current_app.logger.error("Flask static_folder is not configured. Cannot find manifest.json.")
        return None, None

    try:
        manifest_path = os.path.join(static_folder, ".vite", "manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        
        entry = manifest.get(entry_point, {}) 
        js_file = entry.get('file')
        css_files = entry.get('css', [])

        js_path = url_for('static', filename=js_file) if js_file else None
        css_path = url_for('static', filename=css_files[0]) if css_files else None
        return js_path, css_path
    except (FileNotFoundError, json.JSONDecodeError) as e:
        current_app.logger.warning(f"⚠️ 無法載入或解析 manifest.json: {e}. 請確認已在 frontend 目錄執行 'npm run build'")
        return None, None

def get_week_dates(week_offset=0):
    """
    获取指定周次的日期（週二到週六）
    """
    TAIPEI_TZ = current_app.config['TAIPEI_TZ']
    today = datetime.now(TAIPEI_TZ).date()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    
    week_dates = []
    for i in range(1, 6):
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
            
    slots = sorted(list(set(generated_slots)))
    return slots

def get_available_slots(date, weekday):
    """获取某日期的可用时段（过滤掉已过去的时间）"""
    all_slots = generate_time_slots(weekday)
    
    if db.is_closed_day(date):
        return []
    
    appointments = db.get_appointments_by_date_range(date, date)
    booked_times = [apt['time'] for apt in appointments if apt['status'] == 'confirmed']
    
    TAIPEI_TZ = current_app.config['TAIPEI_TZ']
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