#!/usr/bin/env python3
"""
Step 1 — ReAct 循环引擎演示

展示 xyz-agent 框架的核心引擎功能：
  1. 基础 ReAct 循环（思考→行动→观察→答案）
  2. 工具调用能力（模拟天气查询、计算器等）
  3. 单步执行模式
  4. 统计信息

运行:
  python step1-engine-demo.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from xyz_agent.engine import ReActEngine, ReActConfig
from xyz_agent.agent import Agent, AgentConfig


# ============================================================
# 步骤 1a: 引擎基础展示 — 无工具的问答
# ============================================================

def demo_basic_qa():
    """演示基础 ReAct 循环（无工具，直接问答）"""
    print("=" * 60)
    print("📌 步骤 1a：基础 ReAct 循环（直接问答）")
    print("=" * 60)

    # 模拟 LLM 调用（无工具时直接回答）
    def mock_llm(prompt, messages):
        return "最终答案: 北京今天的天气是晴天，温度25°C。", 150

    engine = ReActEngine(
        llm_call=mock_llm,
        config=ReActConfig(max_steps=3),
    )

    result = engine.run("北京的天气怎么样？")
    print(f"问题: 北京的天气怎么样？")
    print(f"答案: {result}")
    print(f"统计: {engine.get_stats()}")
    print()


# ============================================================
# 步骤 1b: 带工具的 ReAct 循环
# ============================================================

def demo_with_tools():
    """演示带工具调用的 ReAct 循环"""
    print("=" * 60)
    print("📌 步骤 1b：带工具的 ReAct 循环")
    print("=" * 60)

    # 模拟工具
    tools = {
        "get_weather": lambda city: f"{city}天气：晴，25°C，湿度45%",
        "calculator": lambda expr: str(eval(expr)),
        "get_time": lambda tz: "2026-06-16 20:30:00",
    }

    def mock_llm_with_tools(prompt, messages):
        """模拟 LLM，在合适的时候调用工具"""
        nonlocal tool_call_count
        tool_call_count += 1

        if tool_call_count == 1:
            return "思考: 用户想知道北京的天气，我需要调用天气工具。\n动作: get_weather\n参数: {\"city\": \"北京\"}", 200
        elif tool_call_count == 2:
            return "思考: 好的，北京天气是晴天25°C。还需要其他信息吗？\n最终答案: 北京今天天气晴朗，温度25°C，湿度45%，非常适合外出活动！", 180
        return "最终答案: 完成。", 100

    def tool_executor(name, args):
        fn = tools.get(name)
        if fn:
            result = fn(**args)
            print(f"  🔧 工具调用: {name}({args}) => {result}")
            return result
        return f"未知工具: {name}"

    tool_call_count = 0
    engine = ReActEngine(
        llm_call=mock_llm_with_tools,
        tool_executor=tool_executor,
        config=ReActConfig(max_steps=5, verbose=True),
        system_prompt="""你是一个天气助手。

可用工具:
- get_weather(city): 查询城市天气
- calculator(expr): 计算数学表达式

格式：
- 需要工具时输出「动作: 工具名\n参数: {...}」
- 有答案时输出「最终答案: <回答>」
""",
    )

    result = engine.run("北京的天气怎么样？")
    print(f"\n最终答案: {result}")
    print(f"统计: {engine.get_stats()}")
    print()


# ============================================================
# 步骤 1c: 单步执行模式
# ============================================================

def demo_step_by_step():
    """演示单步执行模式"""
    print("=" * 60)
    print("📌 步骤 1c：单步执行模式")
    print("=" * 60)

    step_count = 0

    def mock_llm_step(prompt, messages):
        nonlocal step_count
        step_count += 1

        if step_count == 1:
            return "思考: 用户想计算 3+5*2，我需要调用计算器。\n动作: calculator\n参数: {\"expr\": \"3+5*2\"}", 100
        elif step_count == 2:
            return "最终答案: 3+5*2 = 13。先算乘法5*2=10，再加3=13。", 120
        return "最终答案: 完成。", 50

    def tool_executor(name, args):
        print(f"  🔧 执行工具: {name}({args})")
        return str(eval(args["expr"]))

    step_count = 0
    engine = ReActEngine(
        llm_call=mock_llm_step,
        tool_executor=tool_executor,
        config=ReActConfig(max_steps=5),
    )

    engine.reset("3+5*2 等于多少？")

    while not engine.done:
        step = engine.step()
        print(f"  [{step.type.value}] {step.content[:80]}...")
        if step.tool_result:
            print(f"      结果: {step.tool_result}")
        print()

    print(f"最终答案: {engine.final_answer}")
    print(f"总步数: {len(engine.steps)}")
    print(f"总 Token: {engine.total_tokens}")
    print()


# ============================================================
# 步骤 1d: Agent 封装类使用
# ============================================================

def demo_agent_api():
    """演示高级 Agent 封装"""
    print("=" * 60)
    print("📌 步骤 1d：Agent 封装 API")
    print("=" * 60)

    # 定义一个真实的工具函数
    def greet(name: str, greeting: str = "你好") -> str:
        """向某人打招呼"""
        return f"{greeting}，{name}！欢迎使用 xyz-agent 框架 🎉"

    call_count = [0]

    def mock_llm_agent(prompt, messages):
        call_count[0] += 1
        if call_count[0] == 1:
            return ("思考: 用户想让我打招呼，我需要调用 greet 工具。\n"
                    "动作: greet\n参数: {\"name\": \"向阳\", \"greeting\": \"晚上好\"}", 100)
        return ("最终答案: 已经向向阳打了招呼：晚上好，向阳！欢迎使用 xyz-agent 框架 🎉", 80)

    def mock_tool(prompt, messages):
        return mock_llm_agent(prompt, messages)

    def tool_executor(name, args):
        if name == "greet":
            return greet(**args)
        return "未知工具"

    # 注册工具
    tools = [
        {
            "name": "greet",
            "description": "向某人打招呼",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "姓名"},
                    "greeting": {"type": "string", "description": "问候语"},
                },
                "required": ["name"],
            },
            "fn": greet,
        }
    ]

    agent = Agent(
        llm_provider=mock_llm_agent,
        tools=tools,
        config=AgentConfig(name="demo-agent", verbose=True),
    )

    result = agent.run("帮我打个招呼")
    print(f"问题: 帮我打个招呼")
    print(f"结果: {result}")
    print(f"统计: {agent.get_stats()}")
    print()


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║   xyz-agent 框架 — Step 1 引擎演示        ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print(f"框架版本: 0.1.0")
    print()

    demo_basic_qa()
    demo_with_tools()
    demo_step_by_step()
    demo_agent_api()

    print("=" * 60)
    print("✅ Step 1 全部演示完成！")
    print("=" * 60)
