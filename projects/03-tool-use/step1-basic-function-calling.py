"""
基础 Function Calling 实现
展示 OpenAI 原生 tools API 的基本用法
"""

import json
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── 工具定义 ──────────────────────────────────────────

def get_weather(city: str, unit: str = "celsius") -> dict:
    """获取天气信息（模拟）"""
    weather_data = {
        "北京": {"temp": 22, "humidity": 45, "condition": "晴"},
        "上海": {"temp": 25, "humidity": 70, "condition": "多云"},
        "深圳": {"temp": 30, "humidity": 80, "condition": "阵雨"},
        "杭州": {"temp": 24, "humidity": 65, "condition": "阴"},
    }
    data = weather_data.get(city, {"temp": 20, "humidity": 55, "condition": "未知"})
    if unit == "fahrenheit":
        data["temp"] = data["temp"] * 9 / 5 + 32
    return data


def calculator(expr: str) -> str:
    """执行数学计算"""
    try:
        allowed = set("0123456789+-*/().% ")
        if not all(c in allowed for c in expr):
            return "错误：表达式包含非法字符"
        return str(eval(expr))
    except Exception as e:
        return f"错误：{e}"


# ── OpenAI Tool Schema ────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的当前天气信息，包括温度、湿度、天气状况",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，支持中文城市名，如北京、上海"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "温度单位，celsius（摄氏度）或 fahrenheit（华氏度）"
                    }
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "执行数学计算，支持加(+)减(-)乘(*)除(/)和括号",
            "parameters": {
                "type": "object",
                "properties": {
                    "expr": {
                        "type": "string",
                        "description": "数学表达式，如 (15+27)*3"
                    }
                },
                "required": ["expr"]
            }
        }
    }
]

# ── 工具分发器 ──────────────────────────────────────────

TOOL_FUNCTIONS = {
    "get_weather": get_weather,
    "calculator": calculator,
}

def execute_tool_call(tool_call):
    """执行单个工具调用"""
    func_name = tool_call.function.name
    arguments = json.loads(tool_call.function.arguments) if isinstance(tool_call.function.arguments, str) else tool_call.function.arguments

    func = TOOL_FUNCTIONS.get(func_name)
    if not func:
        return f"未知工具: {func_name}"

    print(f"  🛠️  调用 {func_name}({json.dumps(arguments, ensure_ascii=False)})")
    result = func(**arguments)
    print(f"     结果: {result}")
    return result


def function_calling_demo(query):
    """完整的 Function Calling 流程演示"""
    print(f"\n{'='*60}")
    print(f"📝 用户问题: {query}")
    print(f"{'='*60}")

    messages = [{"role": "user", "content": query}]

    # 第 1 轮：LLM 决定是否调用工具
    print(f"\n{'─'*40}")
    print(f"第 1 步：LLM 分析请求")
    print(f"{'─'*40}")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto"
    )

    msg = response.choices[0].message

    if msg.tool_calls:
        # LLM 决定调用工具
        print(f"✅ LLM 决定调用 {len(msg.tool_calls)} 个工具:")
        messages.append(msg)

        for tc in msg.tool_calls:
            print(f"\n  Tool Call ID: {tc.id}")
            print(f"  函数: {tc.function.name}")
            print(f"  参数: {tc.function.arguments}")

        # 执行工具调用
        print(f"\n{'─'*40}")
        print(f"第 2 步：执行工具")
        print(f"{'─'*40}")

        for tc in msg.tool_calls:
            try:
                result = execute_tool_call(tc)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False)
                })
            except Exception as e:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": f"执行错误: {e}"
                })

        # 将工具结果送回 LLM
        print(f"\n{'─'*40}")
        print(f"第 3 步：LLM 综合回答")
        print(f"{'─'*40}")

        final_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto"
        )
        final_answer = final_response.choices[0].message.content
        print(f"\n💬 {final_answer}")
        return final_answer
    else:
        # LLM 直接回答
        print(f"💬 {msg.content}")
        return msg.content


def interactive():
    """交互式演示"""
    print("=" * 60)
    print("Function Calling 交互演示")
    print("支持：天气查询、数学计算")
    print("输入 'exit' 退出")
    print("=" * 60)

    while True:
        query = input("\n🧑 你的问题: ").strip()
        if query.lower() in ("exit", "quit", "q"):
            break
        if not query:
            continue
        function_calling_demo(query)


if __name__ == "__main__":
    # 演示
    examples = [
        "北京天气怎么样？",
        "计算 (235 + 89) * 12 的值",
        "上海天气如何？顺便帮我算一下 2 的 10 次方",
    ]
    for q in examples:
        function_calling_demo(q)
