#!/usr/bin/env python3
"""
交互式 xyz-agent 演示 — 真实运行体验
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from xyz_agent import Agent, AgentConfig, ToolRegistry, tool, load_skills, list_skills

# 1. 注册一些真实工具
@tool
def get_weather(city: str) -> str:
    """查询指定城市当前天气"""
    data = {
        "北京": "晴，25°C，湿度45%，北风3级",
        "上海": "多云，28°C，湿度60%，东南风2级",
        "深圳": "雷阵雨，30°C，湿度80%，南风4级",
        "成都": "阴，22°C，湿度70%，微风",
    }
    return data.get(city, f"暂无{city}的天气数据")

@tool
def calculator(expr: str) -> str:
    """计算数学表达式"""
    allowed = set("0123456789+-*/(). ")
    if not all(c in allowed for c in expr):
        return "表达式包含非法字符"
    try:
        return f"{expr} = {eval(expr)}"
    except Exception as e:
        return f"计算错误: {e}"

@tool
def get_time(city: str = "北京") -> str:
    """查询指定城市的当前时间"""
    import datetime
    now = datetime.datetime.now()
    timezones = {"北京": 8, "东京": 9, "纽约": -5, "伦敦": 0, "巴黎": 1}
    offset = timezones.get(city, 8)
    utc = datetime.datetime.utcnow()
    local = utc + datetime.timedelta(hours=offset)
    return f"{city}当前时间: {local.strftime('%Y-%m-%d %H:%M:%S')}"

# 2. 加载 Hermes Agent 已有的 Skills（如果在的话）
count = load_skills()
if count > 0:
    print(f"📦 自动加载了 {count} 个 Skill")
    for s in list_skills():
        print(f"   · {s['name']}: {s['description'][:50]}")

# 3. 创建 Agent（集成所有子系统）
print("\n" + "=" * 50)
print("🤖 xyz-agent 交互模式")
print("=" * 50)

agent = Agent.from_openai(
    api_key=os.environ.get("OPENAI_API_KEY", ""),
    model="gpt-4o",
    name="demo",
)

if not os.environ.get("OPENAI_API_KEY"):
    print("⚠️  未检测到 OPENAI_API_KEY")
    print("   使用 Mock 模式演示工具系统\n")

    from xyz_agent import MockProvider
    agent = Agent(
        llm_provider=MockProvider(
            custom_responses={
                "天气": "思考: 用户想知道天气，我来调用 get_weather 工具。\n动作: get_weather\n参数: {\"city\": \"北京\"}\n---\n观察: 北京晴，25°C\n最终答案: 北京今天天气晴朗，温度25°C，适合外出活动！",
                "计算": "最终答案: 我可以帮你计算！请告诉我表达式。",
            },
        ),
        config=AgentConfig(name="mock-demo"),
    )
    agent.initialize()

    result = agent.run("北京的天气怎么样？")
    print(f"🧑 问：北京的天气怎么样？")
    print(f"🤖 答：{result}")
    print()

    result = agent.run("帮我算一下 (15+3)*2 等于多少？")
    print(f"🧑 问：帮我算一下 (15+3)*2 等于多少？")
    print(f"🤖 答：{result}")
    print()

    # 测试命令系统
    print("--- 命令系统测试 ---")
    print(agent.chat("/help"))
    print()
    print(agent.chat("/version"))
else:
    agent.initialize()
    print("\n✅ 已配置 OpenAI API，可以真实对话了！")
    print("输入 'exit' 退出\n")

    while True:
        try:
            q = input("🧑 > ").strip()
            if q.lower() in ("exit", "quit", "/exit"):
                break
            if not q:
                continue
            result = agent.chat(q)
            print(f"🤖 > {result}\n")
        except (KeyboardInterrupt, EOFError):
            break

print("\n✅ 演示完成！🎉")
