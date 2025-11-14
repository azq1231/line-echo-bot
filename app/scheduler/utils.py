from datetime import datetime, timedelta
import pytz

def get_week_dates_for_scheduler(week_offset=0, base_date=None):
    """
    一个专为排程器使用的 get_week_dates 版本，不依赖 current_app。
    """
    TAIPEI_TZ = pytz.timezone('Asia/Taipei')
    if base_date:
        today = base_date
    else:
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