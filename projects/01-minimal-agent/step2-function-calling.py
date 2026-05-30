# step2-function-calling.py - 用 Function Calling 让 LLM 决定调用工具

from openai import OpenAI
import os
from dotenv import load_dotenv
import json

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

# ---------- 定义工具 ----------

# 1. 工具 Schema（告诉 LLM 有哪些工具可用）
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的当前天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，如 北京、上海",
                    }
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "获取指定城市的当前时间",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，如 北京、东京",
                    }
                },
                "required": ["city"],
            },
        },
    },
]

# 2. 工具的实际实现
def get_weather(city: str) -> str:
    """模拟查询天气（实际可接入 API）"""
    weather_data = {
        "北京": "晴，25°C，湿度 40%",
        "上海": "多云，28°C，湿度 65%",
        "深圳": "阵雨，30°C，湿度 80%",
        "杭州": "阴天，26°C，湿度 70%",
    }
    return weather_data.get(city, f"{city}：暂无天气数据")

def get_current_time(city: str) -> str:
    """模拟查询时间（实际可接入 API）"""
    time_data = {
        "北京": "2026-05-30 14:30:00 (CST)",
        "东京": "2026-05-30 15:30:00 (JST)",
        "伦敦": "2026-05-30 07:30:00 (BST)",
        "纽约": "2026-05-30 02:30:00 (EDT)",
    }
    return time_data.get(city, f"{city}：暂无时间数据")


# ---------- 调用 LLM ----------

def chat_with_tools(user_message: str):
    messages = [
        {"role": "system", "content": "你是一个有用的助手。根据用户的问题决定是否需要调用工具。"},
        {"role": "user", "content": user_message},
    ]

    print(f"\n👤 用户: {user_message}")
    print("-" * 50)

    # 第一次调用：LLM 决定是否调用工具
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
    )

    message = response.choices[0].message

    if not message.tool_calls:
        # LLM 认为不需要工具，直接回复
        print(f"🤖 助手: {message.content}")
        return

    # LLM 要求调用工具
    for tool_call in message.tool_calls:
        func_name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)

        print(f"🛠️  调用工具: {func_name}({args})")

        # 执行工具
        if func_name == "get_weather":
            result = get_weather(**args)
        elif func_name == "get_current_time":
            result = get_current_time(**args)
        else:
            result = f"未知工具: {func_name}"

        print(f"   → 结果: {result}")

        # 把工具调用和结果加入对话
        messages.append(message)  # assistant 的 tool_calls
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": result,
        })

    # 第二次调用：LLM 基于工具结果生成最终回复
    final_response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=TOOLS,
    )

    print(f"🤖 助手: {final_response.choices[0].message.content}")


# ---------- 测试 ----------

if __name__ == "__main__":
    chat_with_tools("北京现在的天气怎么样？")
    chat_with_tools("东京现在几点？")
    chat_with_tools("深圳天气和杭州天气都帮我查一下")
