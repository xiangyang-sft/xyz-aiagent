"""
工具设计最佳实践
涵盖：tool_choice 四种模式、错误处理、工具路由
"""

import json
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── 工具定义 ──────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_database",
            "description": "从数据库中查询用户信息。当用户询问用户数据、订单、账户信息时使用",
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "enum": ["users", "orders", "products"],
                        "description": "要查询的表名"
                    },
                    "query": {
                        "type": "string",
                        "description": "查询条件，如 'id=123' 或 'name=张三'"
                    }
                },
                "required": ["table", "query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "classify_intent",
            "description": "对用户输入进行分类，判断意图类别。仅用于路由分流",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "用户输入文本"
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的天气信息",
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
    }
]


# ── 工具函数实现 ──────────────────────────────────────────

def search_database(table: str, query: str) -> dict:
    """模拟数据库查询"""
    fake_db = {
        "users": {
            "id=123": {"name": "张三", "email": "zhangsan@example.com", "level": "VIP"},
            "name=张三": {"name": "张三", "email": "zhangsan@example.com", "level": "VIP"},
        },
        "orders": {
            "id=456": {"order_id": 456, "user": "张三", "amount": 299, "status": "已发货"},
            "user_id=123": [
                {"order_id": 456, "amount": 299, "status": "已发货"},
                {"order_id": 789, "amount": 599, "status": "已签收"},
            ],
        },
        "products": {
            "category=电子产品": [
                {"name": "手机", "price": 4999, "stock": 100},
                {"name": "平板", "price": 3999, "stock": 50},
            ],
        },
    }
    result = fake_db.get(table, {}).get(query, "未找到数据")
    return {"table": table, "query": query, "result": result}


def classify_intent(text: str) -> dict:
    """模拟意图分类"""
    if "天气" in text or "温度" in text or "下雨" in text:
        return {"intent": "weather", "confidence": 0.95}
    elif "用户" in text or "账户" in text or "订单" in text:
        return {"intent": "database_query", "confidence": 0.88}
    elif "计算" in text or "等于" in text or "+" in text:
        return {"intent": "calculation", "confidence": 0.92}
    else:
        return {"intent": "general_chat", "confidence": 0.60}


def get_weather(city: str) -> dict:
    """模拟天气查询"""
    weather_data = {
        "北京": "22°C, 晴",
        "上海": "25°C, 多云",
        "深圳": "30°C, 阵雨",
    }
    return {"city": city, "weather": weather_data.get(city, "未知")}


TOOL_FUNCTIONS = {
    "search_database": search_database,
    "classify_intent": classify_intent,
    "get_weather": get_weather,
}


def execute_tool_call(tc):
    """执行工具调用并返回结果"""
    func_name = tc.function.name
    arguments = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments

    func = TOOL_FUNCTIONS.get(func_name)
    if not func:
        return {"status": "error", "error": f"未知工具: {func_name}"}

    try:
        result = func(**arguments)
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ── 演示函数 ──────────────────────────────────────────

def demo_tool_choice_modes():
    """演示 tool_choice 四种模式的区别"""
    print("=" * 60)
    print("1. tool_choice='auto' — 让 LLM 自行决定")
    print("=" * 60)

    query = "今天天气怎么样？"

    messages = [{"role": "user", "content": query}]

    # auto 模式
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto"
    )
    msg = response.choices[0].message
    if msg.tool_calls:
        print(f"  ✅ LLM 决定调用工具: {msg.tool_calls[0].function.name}")
    else:
        print(f"  ❌ LLM 决定不调用工具，直接回答")
        print(f"  回答: {msg.content[:100]}...")

    # required 模式
    print(f"\n{'='*60}")
    print("2. tool_choice='required' — 强制调用工具")
    print("=" * 60)

    response2 = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=TOOLS,
        tool_choice="required"
    )
    msg2 = response2.choices[0].message
    print(f"  ✅ 强制调用工具: {msg2.tool_calls[0].function.name}")

    # none 模式
    print(f"\n{'='*60}")
    print("3. tool_choice='none' — 禁止调用工具")
    print("=" * 60)

    response3 = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=TOOLS,
        tool_choice="none"
    )
    msg3 = response3.choices[0].message
    print(f"  ✅ 禁止调用工具，直接回答: {msg3.content[:100]}...")

    # 强制指定工具
    print(f"\n{'='*60}")
    print("4. 强制指定工具 — tool_choice={type:function, function:{name:xxx}}")
    print("=" * 60)

    response4 = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=TOOLS,
        tool_choice={"type": "function", "function": {"name": "classify_intent"}}
    )
    msg4 = response4.choices[0].message
    print(f"  ✅ 强制调用 classify_intent: {msg4.tool_calls[0].function.arguments}")


def demo_parallel_calls():
    """演示并行调用多个工具"""
    print(f"\n{'='*60}")
    print("5. 并行工具调用（Parallel Tool Call）")
    print("=" * 60)

    query = "帮我查一下北京天气，再查用户 ID 为 123 的信息"

    messages = [{"role": "user", "content": query}]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto"
    )

    msg = response.choices[0].message
    print(f"\n  LLM 同时返回 {len(msg.tool_calls)} 个工具调用:")
    for tc in msg.tool_calls:
        print(f"    [{tc.id}] {tc.function.name}({tc.function.arguments})")

    # 执行所有工具
    messages.append(msg)
    for tc in msg.tool_calls:
        result = execute_tool_call(tc)
        print(f"    结果: {json.dumps(result, ensure_ascii=False)}")
        messages.append({
            "role": "tool",
            "tool_call_id": tc.id,
            "content": json.dumps(result, ensure_ascii=False)
        })

    # 综合回答
    final = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=TOOLS
    )
    print(f"\n  💬 综合回答: {final.choices[0].message.content}")


def demo_error_handling():
    """演示工具调用的错误处理"""
    print(f"\n{'='*60}")
    print("6. 工具错误处理演示")
    print("=" * 60)

    # 模拟一个会出错的工具
    tools_with_error = TOOLS + [
        {
            "type": "function",
            "function": {
                "name": "divide_numbers",
                "description": "两个数字相除",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number"},
                        "b": {"type": "number"}
                    },
                    "required": ["a", "b"]
                }
            }
        }
    ]

    TOOL_FUNCTIONS["divide_numbers"] = lambda a, b: a / b  # 可能除零错误

    query = "计算 10 除以 0"

    messages = [{"role": "user", "content": query}]
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=tools_with_error,
        tool_choice="auto"
    )

    msg = response.choices[0].message
    if msg.tool_calls:
        messages.append(msg)
        for tc in msg.tool_calls:
            result = execute_tool_call(tc)
            print(f"  工具返回: {json.dumps(result, ensure_ascii=False)}")
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False)
            })

        final = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools_with_error
        )
        print(f"\n  💬 LLM 处理错误后回答: {final.choices[0].message.content}")


def demo_routing():
    """演示用工具做路由分流"""
    print(f"\n{'='*60}")
    print("7. 工具路由分流 — 用 classify_intent 做入口")
    print("=" * 60)

    queries = [
        "今天上海天气怎么样？",
        "帮我查一下用户张三的订单",
        "随便聊聊天吧",
    ]

    for query in queries:
        print(f"\n  📝 输入: {query}")

        messages = [{"role": "user", "content": query}]
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=[TOOLS[1]],  # 只给 classify_intent 一个工具
            tool_choice={"type": "function", "function": {"name": "classify_intent"}}
        )

        msg = response.choices[0].message
        result = execute_tool_call(msg.tool_calls[0])
        print(f"  🔀 路由结果: {result['data']}")


if __name__ == "__main__":
    demo_tool_choice_modes()
    demo_parallel_calls()
    demo_error_handling()
    demo_routing()
