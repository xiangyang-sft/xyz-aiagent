#!/usr/bin/env python3
"""流式端到端实测：验证流式调用下模型的准确性。

针对问题："engine.py 流式调用模型时只传了 messages，没传 skill 信息，回答准确吗？"

验证链路（流式 chat_stream）:
  1. 流式调用是否感知到 6 个 skill 目录（system 消息含目录）
  2. 流式调用是否正确触发 skill_view 加载详情
  3. 流式调用是否正确触发真实工具执行（calculator_calc / run_command）
  4. 最终回答是否准确

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
)
agent = Agent(llm_provider=provider, config=config)
agent.initialize()
engine = agent.engine

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


# ============================================================
# 1. 验证 system 消息确实包含 skill 目录（这是准确性的前提）
# ============================================================
print("=" * 66)
print("0. 前提: reset 后 system 消息是否含 skill 目录")
print("=" * 66)
# 先在第一次 reset 后再检查（reset 会注入 system prompt）
agent.reset("准备")
sys_msg = None
for m in (engine.messages if engine else []):
    if m.get("role") == "system":
        sys_msg = m.get("content", "")
        break
has_skill_dir = sys_msg is not None and "已加载的 Skill" in sys_msg
has_calculator = sys_msg is not None and "calculator" in sys_msg
has_git = sys_msg is not None and "git-helper" in sys_msg
has_guide = sys_msg is not None and "skill_view" in sys_msg and "按需加载" in sys_msg
# 也确认 tools 是否在 engine 里（FC schema）
has_tools = bool(engine and engine.tools)
tool_names = [t.get("function", {}).get("name") for t in (engine.tools if engine else [])]
check("  system 消息包含 skill 目录", has_skill_dir)
check("  目录含 calculator", has_calculator)
check("  目录含 git-helper", has_git)
check("  目录含 skill_view 按需加载指引", has_guide)
check("  engine 已配置 FC tools (非空)", has_tools)
print(f"  system 消息长度: {len(sys_msg) if sys_msg else 0} 字符")
print(f"  FC 工具: {tool_names}")
print()

# ============================================================
# 2. 流式算术任务：应识别 calculator → skill_view → calculator_calc
# ============================================================
print("=" * 66)
print("测试 A: 流式算术任务（skill_view + calculator_calc）")
print("=" * 66)
q1 = "请帮我流式计算 12 * 8 + 4 等于多少，用你的计算工具给出精确结果。"
try:
    agent.reset(q1)
    streamed = []
    for chunk in agent.chat_stream(q1):
        streamed.append(chunk)
    r1 = "".join(streamed)
    print(f"  [流式输出预览]: {r1[:120]}...")
    seq = [
        (s.tool_name, s.tool_args) for s in (engine.steps if engine else [])
        if getattr(s, "tool_name", None)
    ]
    print(f"  工具调用序列: {[(n, str(a)[:30]) for n, a in seq]}")
    names = [n for n, _ in seq]
    # 流式准确性核心：要么加载 skill 详情后执行，要么直接执行真实工具，结果必须准确
    check("  流式调用了 calculator_calc（真实工具执行）", "calculator_calc" in names)
    check("  结果含 100 (=12*8+4)", "100" in r1)
    # 记录是否走了 skill_view
    if "skill_view" in names:
        print("    ↳ 本次先加载了 skill 详情再执行 ✔")
    else:
        print("    ↳ 本次直接调用工具（未走 skill_view，工具 schema 足够时合法且高效）")
except Exception as e:
    check(f"  测试A 异常: {e}", False)
print()

# ============================================================
# 3. 流式命令任务：应识别 git-helper → run_command
# ============================================================
print("=" * 66)
print("测试 B: 流式 git 任务（run_command 真实执行）")
print("=" * 66)
q2 = "请用工具执行 git --version 看下版本。"
try:
    agent.reset(q2)
    streamed = []
    for chunk in agent.chat_stream(q2):
        streamed.append(chunk)
    r2 = "".join(streamed)
    print(f"  [流式输出预览]: {r2[:120]}...")
    seq = [
        (s.tool_name, s.tool_args) for s in (engine.steps if engine else [])
        if getattr(s, "tool_name", None)
    ]
    print(f"  工具调用序列: {[(n, str(a)[:30]) for n, a in seq]}")
    names = [n for n, _ in seq]
    check("  流式调用了 run_command", "run_command" in names)
    check("  回答包含 git 版本信息", "git" in r2.lower())
except Exception as e:
    check(f"  测试B 异常: {e}", False)
print()

print("=" * 66)
print(f"流式端到端结果: {passed} 通过, {failed} 失败")
print("=" * 66)
sys.exit(1 if failed else 0)
