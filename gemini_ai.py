import json
import os
from google import genai
from google.genai import types
from datetime import datetime, timedelta

# IMPORTANT: KEEP THIS COMMENT
# Using Gemini AI blueprint for Python integration
# Model: gemini-2.5-flash

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def analyze_appointment_slots(appointments_data, week_dates):
    """
    使用 Gemini AI 分析当前预约情况，提供空档建议
    
    Args:
        appointments_data: 当前预约数据列表
        week_dates: 本周可预约日期信息
    
    Returns:
        dict: 包含建议时段和分析摘要
    """
    try:
        # 构建分析提示
        prompt = f"""
你是一个诊所预约系统的智能助手。请分析以下预约数据，找出最佳的空档时段。

## 本周可预约时间规则：
- 星期二、四、六：14:00-18:00（每15分钟一个时段，共17个时段）
- 星期三、五：18:00-21:00（每15分钟一个时段，共13个时段）

## 本周日期：
{json.dumps(week_dates, ensure_ascii=False, indent=2)}

## 当前预约情况：
{json.dumps(appointments_data, ensure_ascii=False, indent=2)}

请分析以下内容：
1. 找出3-5个预约较少的时段作为推荐空档
2. 分析每天的预约分布情况
3. 给出整周预约的总体建议

请以JSON格式返回结果：
{{
  "recommended_slots": [
    {{"date": "2025-10-14", "time": "15:30", "day_name": "週二"}},
    ...
  ],
  "daily_summary": {{
    "2025-10-14": "預約情況：X/17 時段已預約",
    ...
  }},
  "overall_summary": "整體建議的文字描述"
}}
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        if response.text:
            result = json.loads(response.text)
            return result
        else:
            return {
                "recommended_slots": [],
                "daily_summary": {},
                "overall_summary": "AI 分析暂时不可用"
            }
    
    except Exception as e:
        print(f"Gemini AI 分析错误: {e}")
        return {
            "recommended_slots": [],
            "daily_summary": {},
            "overall_summary": f"AI 分析失败: {str(e)}"
        }

def suggest_best_slot_for_user(appointments_data, week_dates, user_preference=None):
    """
    为用户推荐最佳预约时段
    
    Args:
        appointments_data: 当前预约数据
        week_dates: 本周日期信息
        user_preference: 用户偏好（如时间段偏好）
    
    Returns:
        dict: 推荐的时段信息
    """
    try:
        preference_text = f"用户偏好：{user_preference}" if user_preference else "无特定偏好"
        
        prompt = f"""
基于以下信息，为用户推荐最合适的预约时段：

{preference_text}

## 当前预约情况：
{json.dumps(appointments_data, ensure_ascii=False, indent=2)}

## 本周可预约日期：
{json.dumps(week_dates, ensure_ascii=False, indent=2)}

请推荐3个最佳时段，考虑因素：
1. 避开过于拥挤的时段
2. 优先推荐下午时段（如果可能）
3. 分散在不同日期

返回JSON格式：
{{
  "top_recommendations": [
    {{"date": "2025-10-14", "time": "15:30", "reason": "推荐理由"}},
    ...
  ]
}}
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        if response.text:
            return json.loads(response.text)
        else:
            return {"top_recommendations": []}
    
    except Exception as e:
        print(f"Gemini 推荐错误: {e}")
        return {"top_recommendations": []}
