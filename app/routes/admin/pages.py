from flask import (
    request, render_template, flash, redirect, url_for,
    session, current_app
)
from datetime import datetime
import json

import database as db
from app.utils.decorators import admin_required
from app.utils.helpers import get_vue_assets
from . import admin_bp

@admin_bp.route("/")
@admin_required
def admin_home():
    return redirect(url_for('admin.users_vue_page'))

@admin_bp.route("/users_vue")
@admin_required
def users_vue_page():
    js_path, css_path = get_vue_assets('users.html')
    return render_template("admin_users_vue.html", js_path=js_path, css_path=css_path, user=session.get('user'))

@admin_bp.route("/schedule")
@admin_required
def schedule():
    user = session.get('user')
    if db.get_config('feature_schedule_enabled') == 'false':
        return "Feature disabled", 404
    return render_template("schedule.html", user=user)

@admin_bp.route("/appointments")
@admin_required
def appointments_page():
    js_path, css_path = get_vue_assets('index.html')
    return render_template("admin_appointments_vue.html", js_path=js_path, css_path=css_path, user=session.get('user'))

@admin_bp.route("/closed_days")
@admin_required
def closed_days_page():
    user = session.get('user')
    if db.get_config('feature_closed_days_enabled') == 'false':
        return "Feature disabled", 404
    return render_template("closed_days.html", user=user)

@admin_bp.route("/stats")
@admin_required
def stats_page():
    user = session.get('user')
    TAIPEI_TZ = current_app.config['TAIPEI_TZ']
    current_month = request.args.get('month', datetime.now(TAIPEI_TZ).strftime('%Y-%m'))
    message_type = request.args.get('type', '')
    user_id = request.args.get('user', '')
    all_users = db.get_all_users()
    stats_data = db.get_message_stats(
        month=current_month,
        message_type=message_type or None,
        user_id=user_id or None
    )
    return render_template('stats.html',
                         user=user,
                         stats=stats_data,
                         current_month=current_month,
                         all_users=all_users,
                         current_user_id=user_id,
                         current_type=message_type,
                         stats_data_json=json.dumps(stats_data))

@admin_bp.route("/configs")
@admin_required
def configs_page():
    user = session.get('user')
    all_configs_list = db.get_all_configs()
    configs_dict = {c['key']: c['value'] for c in all_configs_list}
    
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
    default_reminder_template = (
        "您好，提醒您{date_keyword} ({date}) 有預約以下時段：\n\n"
        "{time_slots}\n\n"
        "如果需要更改或取消，請與我們聯繫，謝謝。")
    configs_dict.setdefault('message_template_reminder', default_reminder_template)

    admins = [u for u in db.get_all_users() if u.get('is_admin')]
    return render_template("configs.html", user=user, configs=configs_dict, admins=admins)

@admin_bp.route('/set_admin_status', methods=['POST'])
@admin_required
def set_admin_status():
    user_id_to_change = request.form.get('user_id')
    action = request.form.get('action')

    if not user_id_to_change or not action:
        flash('缺少 User ID 或操作類型。', 'danger')
        return redirect(url_for('admin.configs_page'))

    current_user_id = session.get('user', {}).get('user_id')
    if user_id_to_change == current_user_id:
        flash('無法修改自己的管理員權限。', 'warning')
        return redirect(url_for('admin.configs_page'))

    user_to_modify = db.get_user_by_id(user_id_to_change)
    if not user_to_modify:
        flash(f'找不到 User ID 為 "{user_id_to_change}" 的使用者。請確認該使用者至少與機器人互動過一次。', 'danger')
        return redirect(url_for('admin.configs_page'))

    is_admin = action == 'add'
    
    if db.update_user_admin_status(user_id_to_change, is_admin):
        action_text = "新增" if is_admin else "移除"
        flash(f'成功{action_text}使用者 {user_to_modify["name"]} 的管理員權限。', 'success')
    else:
        flash('更新權限時發生錯誤。', 'danger')

    return redirect(url_for('admin.configs_page'))

@admin_bp.route("/settings/slots")
@admin_required
def slots_settings_page():
    user = session.get('user')
    all_slots = db.get_all_available_slots()
    
    slots_by_weekday = {i: [] for i in range(1, 6)}
    for slot in all_slots:
        if slot['weekday'] in slots_by_weekday:
            slots_by_weekday[slot['weekday']].append(slot)
            
    return render_template("slots_settings.html", user=user, slots_by_weekday=slots_by_weekday)

@admin_bp.route('/users/merge/')
@admin_required
def merge_users_page():
    # 修正：傳入 Vite 設定檔中的入口點名稱 'merge_users.html'
    js_path, css_path = get_vue_assets('merge_users.html')
    # 修正：渲染新的空殼模板
    return render_template('admin_merge_users_vue.html', js_path=js_path, css_path=css_path, user=session.get('user'))