#!/usr/bin/env python3
"""
Step 1: 极简 Agent — 80 行实现 ReAct 循环

核心功能：
- ReAct 循环（思考→行动→观察→回答）
- 3 个内置工具（计算器、时间查询、知识搜索）
- 无记忆，无持久化

学习目标：
- 理解 ReAct 循环的最简实现
- 掌握工具注册和调用的本质
- 建立 Agent 应用的"最小可工作"概念
"""

import json
import os
import math
import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "your-api-key"),
)


# ═══════════════════════════════════════════════════════════════
# 1. 工具定义
# ═══════════════════════════════════════════════════════════════

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "执行数学计算，支持 + - * / ** sqrt sin cos",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 '2 + 3 * 4' 或 'sqrt(16)'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "获取当前日期和时间",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "搜索内置知识库中的信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                    }
                },
                "required": ["query"],
            },
        },
    },
]

# 内置知识库
KNOWLEDGE_BASE = {
    "python": "Python 是一种解释型、高级、通用编程语言，由 Guido van Rossum 于 1991 年创建。",
    "agent": "AI Agent 是能感知环境、自主推理并执行行动的智能体程序。核心组件：LLM + 工具 + 记忆。",
    "react": "ReAct (Reasoning + Acting) 是一种 Agent 设计模式，让 LLM 交替进行推理和行动，通过观察工具返回结果来指导下一步行动。",
    "function calling": "Function Calling 是 LLM API 的一种能力，让模型能够识别何时需要调用外部工具，并输出结构化的调用参数。",
}


def execute_tool(name: str, args: dict) -> str:
    """执行工具并返回结果"""
    try:
        if name == "calculate":
            expr = args["expression"]
            # 安全计算：只允许数学表达式
            allowed_names = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
                           "pi": math.pi, "e": math.e, "abs": abs, "round": round}
            result = eval(expr, {"__builtins__": {}}, allowed_names)
            return json.dumps({"result": result}, ensure_ascii=False)

        elif name == "get_time":
            now = datetime.datetime.now()
            return json.dumps({
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "weekday": now.strftime("%A"),
            }, ensure_ascii=False)

        elif name == "search_knowledge":
            query = args["query"].lower()
            results = {k: v for k, v in KNOWLEDGE_BASE.items() if query in k or query in v.lower()}
            if results:
                return json.dumps({"results": results}, ensure_ascii=False)
            return json.dumps({"results": {}, "message": f"未找到 '{query}' 的相关信息"}, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# 2. Agent 主循环（ReAct）
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """你是一个智能 AI 助手，可以执行计算、查询时间和搜索知识。

工作流程：
1. 理解用户需求
2. 如果需要工具，调用合适的工具
3. 观察工具返回结果
4. 给出最终回答

注意：
- 如果需要计算，使用 calculate 工具
- 如果问时间或日期，使用 get_time 工具
- 如果问知识或概念，使用 search_knowledge 工具
- 如果不需要工具，直接回答"""


def run_agent(user_input: str, max_steps: int = 10) -> str:
    """运行 Agent ReAct 循环"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]

    for step in range(max_steps):
        print(f"\n  [Step {step + 1}] LLM 推理中...")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.3,
        )

        msg = response.choices[0].message
        messages.append(msg)

        # 检查是否有工具调用
        if msg.tool_calls:
            for tc in msg.tool_calls:
                func_name = tc.function.name
                func_args = json.loads(tc.function.arguments)
                print(f"  → 调用工具: {func_name}({func_args})")

                result = execute_tool(func_name, func_args)
                print(f"  ← 结果: {result[:100]}...")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
        else:
            # 没有工具调用，说明 LLM 给出了最终回答
            print(f"  ✓ 完成")
            return msg.content

    return "⚠️ 已达到最大步骤限制，请简化你的问题。"


# ═══════════════════════════════════════════════════════════════
# 3. 主程序
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 55)
    print("  🤖 极简 Agent（80 行 ReAct 循环）")
    print("=" * 55)

    # 示例对话
    test_questions = [
        "现在几点了？",
        "3.14 * 5^2 等于多少？",
        "什么是 AI Agent？",
        "帮我算一下 sin(30) 的值",
    ]

    for q in test_questions:
        print(f"\n{'─' * 55}")
        print(f"🧑 用户: {q}")
        answer = run_agent(q)
        print(f"\n🤖 Agent: {answer}")

    print(f"\n{'=' * 55}")
    print("  ✅ 极简 Agent 演示完成")
    print("=" * 55)
