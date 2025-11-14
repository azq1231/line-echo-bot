from flask import jsonify, current_app, request
from app.utils.decorators import admin_required, api_error_handler
from app.scheduler.jobs import send_daily_reminders_job, send_weekly_reminders_job
from . import api_admin_bp

@api_admin_bp.route("/trigger_job/<job_id>", methods=["POST"])
@admin_required
@api_error_handler
def trigger_job(job_id):
    """
    臨時測試路由，用於手動觸發排程任務。
    可選參數 fake_date (YYYY-MM-DD) 用於模擬特定日期。
    """
    data = request.get_json() or {}
    fake_date = data.get('fake_date')

    if job_id == 'daily_reminder_job':
        send_daily_reminders_job(current_app, fake_today_str=fake_date)
        return jsonify({"status": "success", "message": f"每日提醒任務已觸發 (模擬日期: {fake_date or '無'})。"})
    elif job_id == 'weekly_reminder_job':
        send_weekly_reminders_job(current_app, fake_today_str=fake_date)
        return jsonify({"status": "success", "message": f"每週提醒任務已觸發 (模擬日期: {fake_date or '無'})。"})
    else:
        return jsonify({"status": "error", "message": "無效的任務 ID。"}), 404
