#!/usr/bin/env python3
"""验证修复：CLI 直接 chat_stream（不预先 reset）时，首次对话会注入 system message。

复现 CLI 场景：
  - _get_agent() 调 initialize() 建好 engine（此时 messages 为空）
  - 用户输入第一句 → agent.chat_stream(msg)，不预先 reset
  - 修复前：走 add_user_message，messages 无 system → 模型看不到 skill 目录
  - 修复后：首次空 messages 时 reset，注入 system

验证（不调用真实 LLM，用 MockProvider）：
  1. 直接 chat_stream 首次调用后，messages 含 system + user
  2. system 内容含 skill 目录
  3. 第二次调用（正常连续对话）不会重复 reset
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from xyz_agent.agent import Agent, AgentConfig
from xyz_agent.providers import MockProvider

passed = 0
failed = 0


def check(label, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✅ {label}")
    else:
        failed += 1
        print(f"  ❌ {label}  {detail}")


skill_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")

# 完全模拟 CLI：initialize 后不 reset，直接 chat_stream
config = AgentConfig(
    name="cli-agent",
    model="mock",
    skill_dirs=[skill_dir],
    enable_commands=True,
    enable_mcp=False,
)
agent = Agent(llm_provider=MockProvider(), config=config)
agent.initialize()

print("=" * 60)
print("模拟 CLI 首次对话（initialize 后直接 chat_stream）")
print("=" * 60)

# 第一次调用：应触发 reset 注入 system
for _ in agent.chat_stream("你好，第一次对话"):  # 消费生成器
    pass

engine = agent.engine
roles = [m.get("role") for m in (engine.messages if engine else [])]
print(f"  首次对话后 roles: {roles}")
check("  messages 含 system", "system" in roles)
check("  messages 含 user", "user" in roles)
check("  system 在 user 之前", roles.index("system") < roles.index("user"))
sys_msg = next((m.get("content", "") for m in (engine.messages if engine else [])
                if m.get("role") == "system"), "")
check("  system 含 skill 目录", "已加载的 Skill" in sys_msg)
check("  system 含 calculator skill", "calculator" in sys_msg)
check("  system 含 skill_view 指引", "按需加载" in sys_msg and "skill_view" in sys_msg)

print()
print("=" * 60)
print("连续对话：第二次调用不应重复 reset（保留 system 只追加 user）")
print("=" * 60)
for _ in agent.chat_stream("再问一句"):  # 消费生成器
    pass
roles2 = [m.get("role") for m in (engine.messages if engine else [])]
# 连续对话追加 user（+ assistant 回复）；关键是 system 不重复
check("  第二次对话追加了 user", "user" in roles2 and roles2[-2] == "user")
check("  system 未重复注入 (仍 1 条)", roles2.count("system") == 1)
check("  system 仍在首位", roles2[0] == "system")
print(f"  第二次后 roles: {roles2}")

print()
print("=" * 60)
print(f"结果: {passed} 通过, {failed} 失败")
print("=" * 60)
sys.exit(1 if failed else 0)
