#!/usr/bin/env python3
"""真实 CLI 场景回归：initialize 后不预先 reset，直接 chat_stream 第一次对话。
验证修复后 system message 注入，且真实 LLM 能正确使用工具。
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
skill_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")

provider = OpenAIProvider(api_key=API_KEY, model=MODEL, base_url="https://api.deepseek.com/v1")
config = AgentConfig(
    name="cli-agent",
    model=MODEL,
    skill_dirs=[skill_dir],
    enable_commands=True,
    enable_mcp=False,
    max_steps=12,
)
agent = Agent(llm_provider=provider, config=config)
agent.initialize()

passed = 0
failed = 0


def check(label, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✅ {label}")
    else:
        failed += 1
        print(f"  ❌ {label}")


# 关键修复验证：initialize 后不 reset，直接 chat_stream（CLI 真实流程）
print("=" * 60)
print("模拟 CLI: 首次对话(不预先 reset) → system 注入 + 工具调用")
print("=" * 60)
q = "帮我算一下 7 * 6 + 9，用工具给出精确结果。"
try:
    streamed = []
    for chunk in agent.chat_stream(q):  # 第一句，不 reset
        streamed.append(chunk)
    r = "".join(streamed)
    print(f"  [回复预览]: {r[:150]}...")
    engine = agent.engine
    roles = [m.get("role") for m in (engine.messages if engine else [])]
    print(f"  messages roles: {roles}")
    check("  system message 已注入 (修复生效)", roles[:1] == ["system"])
    names = [
        s.tool_name for s in (engine.steps if engine else [])
        if getattr(s, "tool_name", None)
    ]
    print(f"  工具调用: {names}")
    check("  调用了工具", bool(names))
    check("  结果含 51 (=7*6+9)", "51" in r)
except Exception as e:
    check(f"  CLI 模拟异常: {e}", False)
print()

print("=" * 60)
print(f"结果: {passed} 通过, {failed} 失败")
print("=" * 60)
sys.exit(1 if failed else 0)
