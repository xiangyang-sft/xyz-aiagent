"""
ReAct 模式实现：推理 + 行动交替循环
Step 1 - 基础版 ReAct，带双工具（搜索 + 计算器）
"""

import json
import re
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── 工具定义 ──────────────────────────────────────────

def search_web(query):
    """模拟搜索工具"""
    results = {
        "Agent 设计模式有哪些": "常见的 Agent 设计模式包括：ReAct（推理+行动）、Plan-Execute（规划-执行）、Reflection（反思）、Multi-Agent（多智能体协作）",
        "ReAct": "ReAct 是 Google 2022 年提出的框架，将推理（Reasoning）和行动（Acting）结合，让 LLM 边思考边使用工具。论文：https://arxiv.org/abs/2210.03629",
        "Python 列表推导式": "列表推导式是 Python 中创建列表的简洁语法：[x**2 for x in range(10)]",
    }
    return results.get(query, f"关于「{query}」的搜索结果：暂无具体信息")

def calculator(expr):
    """计算器工具"""
    try:
        # 安全评估，只允许基本运算
        allowed = set("0123456789+-*/(). ")
        if not all(c in allowed for c in expr):
            return "计算错误：包含非法字符"
        return str(eval(expr))
    except Exception as e:
        return f"计算错误：{e}"

TOOLS = {
    "search_web": {
        "func": search_web,
        "description": "搜索网络获取信息",
        "params": {"query": "搜索关键词"}
    },
    "calculator": {
        "func": calculator,
        "description": "执行数学计算",
        "params": {"expr": "数学表达式，如 (2+3)*4"}
    }
}

TOOL_DESC = """你是一个智能助手，可以调用工具来回答问题。

可用工具：
{tools}

响应格式（二选一）：
1. 如果需要使用工具：
   Thought: 你的推理过程
   Action: 工具名称
   Action Input: {{"参数名": "参数值"}}

2. 如果已经获得足够信息：
   Thought: 最终推理
   Final Answer: 最终答案
"""

SYSTEM_PROMPT = """你是一个 ReAct 模式的 Agent。
遵循 Thought → Action → Observation → Thought... → Final Answer 的循环。
每一步都要思考当前状态，然后决定是继续还是给出最终答案。
不要杜撰信息，使用工具获取事实。"""

# ── 核心逻辑 ──────────────────────────────────────────

def build_tool_desc():
    lines = []
    for name, tool in TOOLS.items():
        params = ", ".join(f"{k}: {v}" for k, v in tool["params"].items())
        lines.append(f"- {name}: {tool['description']}，参数：{params}")
    return "\n".join(lines)

def extract_action(text):
    """从 LLM 输出中提取 Action 和 Action Input"""
    action_match = re.search(r"Action:\s*(\w+)", text)
    input_match = re.search(r"Action Input:\s*(\{.*?\})", text, re.DOTALL)
    if action_match and input_match:
        try:
            params = json.loads(input_match.group(1))
            return action_match.group(1), params
        except json.JSONDecodeError:
            return None, None
    return None, None


def react_loop(query, max_steps=10):
    """
    ReAct 主循环

    参数：
        query: 用户问题
        max_steps: 最大迭代步数（防止死循环）
    """
    print(f"\n{'='*60}")
    print(f"🤖 ReAct 循环开始")
    print(f"📝 用户问题: {query}")
    print(f"{'='*60}")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + TOOL_DESC.format(tools=build_tool_desc())},
        {"role": "user", "content": query}
    ]

    for step in range(max_steps):
        print(f"\n{'─'*40}")
        print(f"Step {step + 1}/{max_steps}")
        print(f"{'─'*40}")

        # 调用 LLM
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        print(f"💭 LLM:\n{content}\n")

        # 检查是否给出了最终答案
        if "Final Answer:" in content:
            final = content.split("Final Answer:")[-1].strip()
            print(f"{'='*60}")
            print(f"✅ 最终答案:\n{final}")
            return final

        # 提取工具调用
        action_name, params = extract_action(content)
        if action_name and params:
            tool = TOOLS.get(action_name)
            if tool:
                try:
                    result = tool["func"](**params)
                    print(f"🛠️  调用 {action_name}({params})")
                    print(f"📊 观察: {result}")

                    # 将 Thought+Action 和 Observation 加入对话历史
                    messages.append({"role": "assistant", "content": content})
                    messages.append({"role": "user", "content": f"Observation: {result}"})
                except Exception as e:
                    print(f"❌ 工具调用失败: {e}")
                    messages.append({"role": "assistant", "content": content})
                    messages.append({"role": "user", "content": f"Observation: 工具调用出错: {e}"})
            else:
                print(f"❌ 未知工具: {action_name}")
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": f"Observation: 工具「{action_name}」不存在，可用工具：{', '.join(TOOLS.keys())}"})
        else:
            print(f"❌ 无法解析工具调用，终止循环")
            break

    print(f"\n⚠️  达到最大步数 {max_steps}，未得到完整答案")
    return None


def interactive():
    """交互式 ReAct 演示"""
    print("=" * 60)
    print("ReAct 模式 — 交互式演示")
    print("输入 'exit' 退出")
    print("=" * 60)

    while True:
        query = input("\n🧑 你的问题: ").strip()
        if query.lower() in ("exit", "quit", "q"):
            print("再见！")
            break
        if not query:
            continue
        react_loop(query)


if __name__ == "__main__":
    # 演示模式：运行示例问题
    examples = [
        "什么是 ReAct 模式？",
        "请计算 (15 + 27) * 3 的值",
        "请搜索 Python 列表推导式的信息，并计算 2 的 10 次方，然后总结回答",
    ]

    for i, query in enumerate(examples, 1):
        print(f"\n\n{'#'*60}")
        print(f"# 示例 {i}")
        print(f"{'#'*60}")
        react_loop(query)

    # 非交互模式，不启动 interactive()
