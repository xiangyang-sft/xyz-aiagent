---
name: weather
description: "天气查询 Skill — 提供实时天气信息查询、天气预报、空气质量等功能。加载本 skill 后 Agent 能查询任意城市的天气。"
version: 1.0.0
author: xyz-agent
license: MIT
metadata:
  hermes:
    tags: [weather, tool, information]
    related_skills: []
---

# Weather Skill

提供丰富的天气查询能力。

## 使用场景
- 查询当前城市的实时天气
- 获取未来几天的天气预报
- 查询空气质量指数
- 天气预警信息

## 提供的工具

```json
[
  {
    "name": "get_current_weather",
    "description": "查询指定城市的当前天气",
    "fn": "scripts/impl.py:get_current_weather",
    "parameters": {
      "type": "object",
      "properties": {
        "city": {
          "type": "string",
          "description": "城市名称"
        },
        "unit": {
          "type": "string",
          "description": "温度单位 (celsius/fahrenheit)",
          "enum": ["celsius", "fahrenheit"],
          "default": "celsius"
        }
      },
      "required": ["city"]
    }
  },
  {
    "name": "get_weather_forecast",
    "description": "查询指定城市未来几天的天气预报",
    "fn": "scripts/impl.py:get_weather_forecast",
    "parameters": {
      "type": "object",
      "properties": {
        "city": {
          "type": "string",
          "description": "城市名称"
        },
        "days": {
          "type": "integer",
          "description": "预报天数 (1-7)",
          "default": 3
        }
      },
      "required": ["city"]
    }
  },
  {
    "name": "get_air_quality",
    "description": "查询指定城市的空气质量指数",
    "fn": "scripts/impl.py:get_air_quality",
    "parameters": {
      "type": "object",
      "properties": {
        "city": {
          "type": "string",
          "description": "城市名称"
        }
      },
      "required": ["city"]
    }
  }
]
```

## 使用示例

当用户询问天气时，使用 get_current_weather 查询当前天气。
如果需要预报，使用 get_weather_forecast 获取未来天气。
如果用户提到空气质量，使用 get_air_quality。
