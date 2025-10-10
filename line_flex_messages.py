"""
LINE Flex Message 模板
生成预约流程中的各种卡片
"""
from datetime import datetime, timedelta
from typing import List, Dict

def _build_navigation_buttons(current_week_offset: int, max_weeks: int) -> List[Dict]:
    """构建周次导航按钮"""
    buttons = []
    
    # 上一週按钮（只在不是第0週时显示）
    if current_week_offset > 0:
        buttons.append({
            "type": "button",
            "style": "link",
            "action": {
                "type": "postback",
                "label": "⬅️ 上一週",
                "data": f"action=change_week&offset={current_week_offset-1}"
            },
            "flex": 1
        })
    
    # 下一週按钮（根据最大周数限制）
    if current_week_offset < max_weeks - 1:
        buttons.append({
            "type": "button",
            "style": "link",
            "action": {
                "type": "postback",
                "label": "下一週 ➡️",
                "data": f"action=change_week&offset={current_week_offset+1}"
            },
            "flex": 1
        })
    
    # 如果没有按钮，添加一个占位
    if not buttons:
        buttons.append({
            "type": "text",
            "text": "僅可預約本週",
            "size": "sm",
            "color": "#999999",
            "align": "center"
        })
    
    return buttons

def generate_date_selection_card(week_dates: List[Dict], current_week_offset: int = 0, max_weeks: int = 2) -> Dict:
    """
    生成日期选择 Flex Message 卡片
    
    Args:
        week_dates: 本周日期列表 [{'date': '2025-10-07', 'day_name': '週二', 'weekday': 1}, ...]
        current_week_offset: 当前周偏移量（0=本周，1=下周，-1=上周）
    
    Returns:
        Flex Message 卡片的 dict
    """
    
    # 构建日期按钮
    date_buttons = []
    for date_info in week_dates:
        date_obj = datetime.strptime(date_info['date'], '%Y-%m-%d')
        month_day = f"{date_obj.month}/{date_obj.day}"
        
        date_buttons.append({
            "type": "button",
            "style": "primary",
            "color": "#667eea",
            "action": {
                "type": "postback",
                "label": f"{date_info['day_name']} {month_day}",
                "data": f"action=select_date&date={date_info['date']}&day_name={date_info['day_name']}"
            }
        })
    
    # 周次标题
    if current_week_offset == 0:
        week_title = "本週"
    elif current_week_offset == -1:
        week_title = "上週"
    elif current_week_offset == 1:
        week_title = "下週"
    elif current_week_offset > 1:
        week_title = f"第{current_week_offset}週"
    else:  # current_week_offset < -1
        week_title = f"前第{abs(current_week_offset)}週"
    
    flex_message = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "📅",
                            "size": "xl",
                            "weight": "bold",
                            "flex": 0
                        },
                        {
                            "type": "text",
                            "text": "請選擇預約日期",
                            "size": "xl",
                            "weight": "bold",
                            "margin": "md"
                        }
                    ]
                },
                {
                    "type": "text",
                    "text": week_title,
                    "size": "sm",
                    "color": "#999999",
                    "margin": "sm"
                }
            ],
            "backgroundColor": "#667eea",
            "paddingAll": "20px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": date_buttons,
            "spacing": "md",
            "paddingAll": "20px"
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "contents": _build_navigation_buttons(current_week_offset, max_weeks),
            "spacing": "sm"
        }
    }
    
    return {
        "type": "flex",
        "altText": "請選擇預約日期",
        "contents": flex_message
    }

def generate_time_selection_card(date: str, day_name: str, available_slots: List[str], is_closed: bool = False) -> Dict:
    """
    生成时段选择 Flex Message 卡片
    
    Args:
        date: 日期 '2025-10-07'
        day_name: 星期名称 '週二'
        available_slots: 可预约时段列表 ['14:00', '14:15', ...]
        is_closed: 是否休诊
    
    Returns:
        Flex Message 卡片
    """
    
    date_obj = datetime.strptime(date, '%Y-%m-%d')
    display_date = f"{date_obj.month}月{date_obj.day}日"
    
    if is_closed:
        # 休诊卡片
        flex_message = {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "😴 今日休診",
                        "size": "xl",
                        "weight": "bold",
                        "color": "#ffffff"
                    }
                ],
                "backgroundColor": "#ee5a6f",
                "paddingAll": "20px"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{display_date} ({day_name})",
                        "size": "lg",
                        "weight": "bold",
                        "align": "center"
                    },
                    {
                        "type": "text",
                        "text": "本日門診休息\n請選擇其他日期",
                        "size": "md",
                        "color": "#999999",
                        "align": "center",
                        "margin": "md",
                        "wrap": True
                    }
                ],
                "paddingAll": "20px"
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "action": {
                            "type": "postback",
                            "label": "返回選擇日期",
                            "data": "action=show_date_selection"
                        }
                    }
                ]
            }
        }
    else:
        # 正常时段选择卡片
        if not available_slots:
            body_contents = [
                {
                    "type": "text",
                    "text": f"{display_date} ({day_name})",
                    "size": "lg",
                    "weight": "bold",
                    "align": "center"
                },
                {
                    "type": "text",
                    "text": "本日時段已全部預約\n請選擇其他日期",
                    "size": "md",
                    "color": "#999999",
                    "align": "center",
                    "margin": "md",
                    "wrap": True
                }
            ]
        else:
            # 将时段按行分组（每行4个）
            slot_rows = []
            for i in range(0, len(available_slots), 4):
                row_slots = available_slots[i:i+4]
                row_buttons = []
                
                for slot in row_slots:
                    row_buttons.append({
                        "type": "button",
                        "style": "primary",
                        "color": "#48bb78",
                        "action": {
                            "type": "postback",
                            "label": slot,
                            "data": f"action=select_time&date={date}&day_name={day_name}&time={slot}"
                        },
                        "flex": 1,
                        "height": "sm"
                    })
                
                slot_rows.append({
                    "type": "box",
                    "layout": "horizontal",
                    "contents": row_buttons,
                    "spacing": "sm"
                })
            
            body_contents = [
                {
                    "type": "text",
                    "text": f"{display_date} ({day_name})",
                    "size": "lg",
                    "weight": "bold"
                },
                {
                    "type": "separator",
                    "margin": "md"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": slot_rows,
                    "spacing": "md",
                    "margin": "md"
                }
            ]
        
        flex_message = {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "⏰ 請選擇預約時間",
                        "size": "xl",
                        "weight": "bold",
                        "color": "#ffffff"
                    }
                ],
                "backgroundColor": "#667eea",
                "paddingAll": "20px"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": body_contents,
                "paddingAll": "20px"
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "link",
                        "action": {
                            "type": "postback",
                            "label": "← 返回選擇日期",
                            "data": "action=show_date_selection"
                        }
                    }
                ]
            }
        }
    
    return {
        "type": "flex",
        "altText": f"請選擇 {display_date} 的預約時間",
        "contents": flex_message
    }

def generate_confirmation_card(date: str, day_name: str, time: str, user_name: str) -> Dict:
    """
    生成预约确认 Flex Message 卡片
    
    Args:
        date: 日期
        day_name: 星期
        time: 时间
        user_name: 用户名
    
    Returns:
        Flex Message 确认卡片
    """
    
    date_obj = datetime.strptime(date, '%Y-%m-%d')
    display_date = f"{date_obj.month}月{date_obj.day}日"
    
    flex_message = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "✅ 確認預約",
                    "size": "xl",
                    "weight": "bold",
                    "color": "#ffffff"
                }
            ],
            "backgroundColor": "#48bb78",
            "paddingAll": "20px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "請確認您的預約資訊",
                    "size": "md",
                    "color": "#999999",
                    "margin": "md"
                },
                {
                    "type": "separator",
                    "margin": "lg"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "姓名",
                                    "size": "sm",
                                    "color": "#999999",
                                    "flex": 2
                                },
                                {
                                    "type": "text",
                                    "text": user_name,
                                    "size": "md",
                                    "weight": "bold",
                                    "flex": 5
                                }
                            ],
                            "spacing": "sm"
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "日期",
                                    "size": "sm",
                                    "color": "#999999",
                                    "flex": 2
                                },
                                {
                                    "type": "text",
                                    "text": f"{display_date} ({day_name})",
                                    "size": "md",
                                    "weight": "bold",
                                    "flex": 5
                                }
                            ],
                            "spacing": "sm",
                            "margin": "md"
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "時間",
                                    "size": "sm",
                                    "color": "#999999",
                                    "flex": 2
                                },
                                {
                                    "type": "text",
                                    "text": time,
                                    "size": "lg",
                                    "weight": "bold",
                                    "color": "#667eea",
                                    "flex": 5
                                }
                            ],
                            "spacing": "sm",
                            "margin": "md"
                        }
                    ],
                    "margin": "lg"
                }
            ],
            "paddingAll": "20px"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "action": {
                        "type": "postback",
                        "label": "✅ 確認預約",
                        "data": f"action=confirm_booking&date={date}&day_name={day_name}&time={time}"
                    },
                    "color": "#48bb78"
                },
                {
                    "type": "button",
                    "style": "link",
                    "action": {
                        "type": "postback",
                        "label": "← 重新選擇",
                        "data": "action=show_date_selection"
                    },
                    "margin": "sm"
                }
            ],
            "spacing": "sm"
        }
    }
    
    return {
        "type": "flex",
        "altText": f"確認預約：{display_date} {time}",
        "contents": flex_message
    }
