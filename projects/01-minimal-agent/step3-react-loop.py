# step3-react-loop.py - 完整的 ReAct 循环（多轮推理 + 工具调用）

from openai import OpenAI
import os
from dotenv import load_dotenv
import json

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

# ---------- 工具定义 ----------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "执行数学计算",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 '2 + 3 * 4'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_database",
            "description": "查询数据库中的信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "查询关键词",
                    }
                },
                "required": ["query"],
            },
        },
    },
]


def calculate(expression: str) -> str:
    """执行数学计算"""
    try:
        # 使用 Python 的 eval 做简单计算（仅供演示，生产环境要安全处理）
        result = eval(expression, {"__builtins__": {}}, {})
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误: {e}"


def search_database(query: str) -> str:
    """模拟数据库查询"""
    db = {
        "销售额": "2026年4月总销售额：¥12,800,000，同比增长15%",
        "用户数": "2026年4月活跃用户：85,000人，环比增长8%",
        "库存": "当前总库存：45,000件，周转率3.2",
        "客户满意度": "2026年4月 NPS 评分：72分，目标：75分",
    }
    for key, value in db.items():
        if key in query:
            return value
    return f"未找到关于 '{query}' 的数据"


def execute_tool(func_name: str, args: dict) -> str:
    """执行工具调用"""
    if func_name == "calculate":
        return calculate(**args)
    elif func_name == "search_database":
        return search_database(**args)
    else:
        return f"未知工具: {func_name}"


# ---------- ReAct 循环 ----------

MAX_ITERATIONS = 5  # 防止死循环


def react_agent(user_message: str):
    """完整的 ReAct 循环实现"""
    messages = [
        {
            "role": "system",
            "content": (
                "你是一个数据分析助手。你遵循 ReAct 模式：\n"
                "1. 分析用户的问题（Reasoning）\n"
                "2. 决定是否需要调用工具（Action）\n"
                "3. 执行工具获取信息（Observation）\n"
                "4. 综合所有信息回答用户\n"
                "如果已经得到足够信息，直接回答用户，不要再调工具。"
            ),
        },
        {"role": "user", "content": user_message},
    ]

    print(f"\n{'='*60}")
    print(f"👤 用户: {user_message}")
    print(f"{'='*60}")

    step = 0

    while step < MAX_ITERATIONS:
        step += 1
        print(f"\n--- 第 {step} 轮推理 ---")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        message = response.choices[0].message

        # 打印 LLM 的推理（如果有 reasoning 内容）
        if message.content:
            print(f"🤖 思考: {message.content}")

        # 如果没有工具调用，说明 LLM 已经准备好回答
        if not message.tool_calls:
            print(f"\n✅ 最终回答: {message.content}")
            return

        # 执行所有工具调用
        messages.append(message)  # 保存 assistant 消息（含 tool_calls）

        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            print(f"🔧 行动: {func_name}({json.dumps(args, ensure_ascii=False)})")

            result = execute_tool(func_name, args)

            print(f"📊 观察: {result}")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    print(f"\n⚠️  达到最大迭代次数 ({MAX_ITERATIONS})，停止循环。")
    # 最后一次尝试给出回答
    final_response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
    )
    print(f"🤖 最终回答: {final_response.choices[0].message.content}")


# ---------- 测试 ----------

if __name__ == "__main__":
    # 测试1：单步工具
    react_agent("上个月的销售额是多少？和去年比怎么样？")

    print("\n" + "=" * 60)
    print("第二个测试：多步推理")
    print("=" * 60)

    # 测试2：需要多步推理（先查销售额，再查用户数，再计算人均）
    react_agent("帮我算一下4月份人均销售额（销售额÷用户数）")
