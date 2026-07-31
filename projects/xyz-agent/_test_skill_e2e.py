#!/usr/bin/env python3
"""端到端实测：skill 按需加载（>5 个 skill，LLM 通过 skill_view 加载并执行）

验证链路：
  主 prompt 只含 6 个 skill 的目录 → LLM 判断任务命中 calculator →
  调用 skill_view("calculator") 加载详情 → 按详情调用 calculator_calc 执行计算 → 返回结果。
使用 DeepSeek deepseek-v4-flash。
"""
import os
import sys

_env_path = os.path.expanduser("~/.hermes/.env")
API_KEY = ""
if os.path.isfile(_env_path):
    with open(_env_path, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line.startswith("DEEPSEEK_API_KEY="):
                API_KEY = _line.split("=", 1)[1].strip().strip('"').strip("'")
                break

if not API_KEY:
    print("错误：未在 ~/.hermes/.env 找到 DEEPSEEK_API_KEY")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from xyz_agent.agent import Agent, AgentConfig
from xyz_agent.providers import OpenAIProvider

MODEL = "deepseek-v4-flash"
BASE_URL = "https://api.deepseek.com/v1"
skill_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")

provider = OpenAIProvider(api_key=API_KEY, model=MODEL, base_url=BASE_URL)
config = AgentConfig(
    model=MODEL,
    skill_dirs=[skill_dir],
    enable_commands=False,
    enable_mcp=False,
    max_steps=15,
    verbose=False,
)
agent = Agent(llm_provider=provider, config=config)
agent.initialize()
engine = agent.engine

print(f"模型: {MODEL}")
sm = agent.skill_manager
print(f"已加载 skill 数: {len(sm) if sm else 0}")
tool_names = [t["name"] for t in agent.tool_registry.list_tools()]
print(f"可用工具: {tool_names}")
print("主 system prompt 是否含 calculator 详情: " + ("是" if engine and "提供的工具" in engine.system_prompt else "否(仅目录)"))
print()

passed = 0
failed = 0


def check(label, cond):
    global passed, failed
    mark = "✅" if cond else "❌"
    if cond:
        passed += 1
    else:
        failed += 1
    print(f"  {mark} {label}")


def tool_call_sequence():
    """提取引擎记录的工具调用序列"""
    steps = engine.steps if engine else []
    return [
        (s.tool_name, s.tool_args) for s in steps
        if getattr(s, "tool_name", None)
    ]

# ============================================================
# 测试 1：算数 —— 应走 calculator skill
# ============================================================
print("=" * 66)
print("测试 1: 算术任务 → skill_view + calculator_calc")
print("=" * 66)
q1 = "请帮我计算 23 * 45 + 67 等于多少，并用你自己的计算工具给出精确结果。"
try:
    agent.reset(q1)
    r1 = agent.chat(q1)
    print(f"  Agent 回答: {r1[:300]}")
    seq = tool_call_sequence()
    print(f"  工具调用序列: {[(n, str(a)[:40]) for n, a in seq]}")
    names = [n for n, _ in seq]
    check("  调用了 skill_view", "skill_view" in names)
    check("  调用了 calculator_calc", "calculator_calc" in names)
    check("  结果含 1102 (=23*45+67)", "1102" in r1)
except Exception as e:
    check(f"  测试1 异常: {e}", False)
print()

# ============================================================
# 测试 2：git 任务 —— 应走 git-helper skill
# ============================================================
print("=" * 66)
print("测试 2: git 任务 → skill_view + run_command")
print("=" * 66)
q2 = "请用 git 工具查看当前仓库的最近 3 条提交记录（git log）。"
try:
    agent.reset(q2)
    r2 = agent.chat(q2)
    print(f"  Agent 回答: {r2[:300]}")
    seq = tool_call_sequence()
    print(f"  工具调用序列: {[(n, str(a)[:40]) for n, a in seq]}")
    names = [n for n, _ in seq]
    # git-helper 引用内置 run_command；LLM 可能直接调用 run_command 而不必先 skill_view
    check("  调用了 run_command", "run_command" in names)
except Exception as e:
    check(f"  测试2 异常: {e}", False)
print()

print("=" * 66)
print(f"端到端结果: {passed} 通过, {failed} 失败")
print("=" * 66)
sys.exit(1 if failed else 0)
