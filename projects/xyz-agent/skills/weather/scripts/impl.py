#!/usr/bin/env python3
"""weather skill 的真实工具实现

SKILL.md 中的工具通过 `fn: "scripts/impl.py:函数名"` 引用本文件。
这样 skill 声明 + 真实实现 分离：声明在 SKILL.md，实现在 scripts/ 下。
（Hermes 风格：skill = 知识/编排 + 引用真实能力）
"""
import random
from datetime import datetime, timedelta


# 简化的城市天气数据（演示用，真实场景可对接天气 API）
_CITY_TEMP = {
    "北京": (18, 28),
    "上海": (20, 27),
    "广州": (24, 32),
    "深圳": (23, 30),
    "杭州": (19, 26),
}

_CONDITIONS = ["晴", "多云", "小雨", "阴", "雷阵雨"]


def get_current_weather(city: str, unit: str = "celsius") -> str:
    """查询指定城市的当前天气。

    参数:
      city: 城市名称
      unit: 温度单位 (celsius/fahrenheit)

    返回:
      该城市当前天气描述
    """
    city = city.strip()
    if city not in _CITY_TEMP:
        return f"抱歉，暂无 {city} 的天气数据。支持查询: {', '.join(_CITY_TEMP.keys())}"

    low, high = _CITY_TEMP[city]
    condition = random.choice(_CONDITIONS)
    temp = random.randint(low, high)

    if unit == "fahrenheit":
        temp = int(temp * 9 / 5 + 32)
        unit_label = "°F"
    else:
        unit_label = "°C"

    now = datetime.now().strftime("%H:%M")
    return f"{city} 当前 {condition}，{temp}{unit_label}（更新时间 {now}）"


def get_weather_forecast(city: str, days: int = 3) -> str:
    """查询指定城市未来几天的天气预报。

    参数:
      city: 城市名称
      days: 预报天数 (1-7)

    返回:
      未来几天天气简报
    """
    city = city.strip()
    if city not in _CITY_TEMP:
        return f"抱歉，暂无 {city} 的天气数据。支持查询: {', '.join(_CITY_TEMP.keys())}"

    days = max(1, min(int(days), 7))
    low, high = _CITY_TEMP[city]
    lines = [f"{city} 未来 {days} 天预报:"]
    today = datetime.now()
    for i in range(days):
        day = (today + timedelta(days=i + 1)).strftime("%m-%d")
        temp = random.randint(low, high)
        condition = random.choice(_CONDITIONS)
        lines.append(f"  {day}: {condition}，{temp}°C")
    return "\n".join(lines)


def get_air_quality(city: str) -> str:
    """查询指定城市的空气质量指数。

    参数:
      city: 城市名称

    返回:
      空气质量指数与等级描述
    """
    city = city.strip()
    if city not in _CITY_TEMP:
        return f"抱歉，暂无 {city} 的空气质量数据。"

    aqi = random.randint(20, 180)
    if aqi <= 50:
        level = "优"
    elif aqi <= 100:
        level = "良"
    elif aqi <= 150:
        level = "轻度污染"
    else:
        level = "中度污染"
    return f"{city} 空气质量 AQI {aqi}（{level}）"
