#!/usr/bin/env python3
"""端到端 LLM 实测：Agent 通过 Function Calling 真实调用内置 file/terminal 工具

验证链路：LLM 决策 → Function Calling → 工具真实执行 → 返回结果 → 形成最终回答。
使用 DeepSeek deepseek-v4-flash（从 ~/.hermes/.env 读取 key）。
"""
import os
import sys
import tempfile

# 读取 deepseek key（从 Hermes 环境文件）
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

# 临时工作目录，用于真实读写测试
WORKDIR = tempfile.mkdtemp(prefix="xyz_e2e_")
DEMO_FILE = os.path.join(WORKDIR, "note.txt")

provider = OpenAIProvider(api_key=API_KEY, model=MODEL, base_url=BASE_URL)
config = AgentConfig(
    model=MODEL,
    enable_skills=False,  # 本轮只测内置系统工具，不加载 skill
    enable_commands=False,
    enable_mcp=False,
    max_steps=12,
    verbose=False,
)
agent = Agent(llm_provider=provider, config=config)
agent.initialize()

print(f"模型: {MODEL}")
engine = agent.engine
if engine:
    print(f"engine 工具数: {len(engine.tools)}")
    print(f"可用的 Function Calling 工具: {[t['function']['name'] for t in engine.tools]}")
print(f"工作目录: {WORKDIR}")
print()

passed = 0
failed = 0


def check(label, cond, detail=""):
    global passed, failed
    mark = "✅" if cond else "❌"
    if cond:
        passed += 1
    else:
        failed += 1
    print(f"  {mark} {label}" + (f"  {detail}" if detail and not cond else ""))


# ============================================================
# 测试 1：写文件 + 读文件（LLM 决定调用 write_file / read_file）
# ============================================================
print("=" * 66)
print("测试 1: LLM 调用 write_file + read_file")
print("=" * 66)
q1 = (
    f"请帮我用内置工具完成一个文件操作任务："
    f"1) 用 write_file 写入文件路径 '{DEMO_FILE}'，内容为 'e2e-tool-test-你好-123'；"
    f"2) 用 read_file 读回该文件，确认内容一致。"
    f"请真实调用工具，并把工具返回的结果告诉我。"
)
try:
    r1 = agent.chat(q1)
    print(f"  Agent 回答: {r1[:400]}")
    # 验证工具是否真的执行了（文件应该真实存在且内容正确）
    file_exists = os.path.isfile(DEMO_FILE)
    content_ok = False
    if file_exists:
        content_ok = open(DEMO_FILE, encoding="utf-8").read().strip() == "e2e-tool-test-你好-123"
    check("  文件已被真实创建 (write_file 真实执行)", file_exists)
    check("  文件内容正确 (read_file 读回一致)", content_ok)
    # 查看引擎是否记录到工具调用
    tools_used = [
        s.tool_name for s in ((engine.steps if engine else None) or [])
        if getattr(s, "tool_name", None)
    ]
    print(f"  引擎记录的工具调用: {tools_used}")
    check("  引擎记录了 write_file 调用", "write_file" in tools_used)
    check("  引擎记录了 read_file 调用", "read_file" in tools_used)
except Exception as e:
    check(f"  测试1 异常: {e}", False)
print()

# ============================================================
# 测试 2：执行命令（LLM 决定调用 run_command）
# ============================================================
print("=" * 66)
print("测试 2: LLM 调用 run_command")
print("=" * 66)
q2 = "请用 run_command 内置工具执行命令 echo xyz-e2e-command-ok，然后把命令输出告诉我。"
try:
    agent.reset(q2)
    r2 = agent.chat(q2)
    print(f"  Agent 回答: {r2[:300]}")
    tools_used2 = [
        s.tool_name for s in ((engine.steps if engine else None) or [])
        if getattr(s, "tool_name", None)
    ]
    print(f"  引擎记录的工具调用: {tools_used2}")
    check("  引擎记录了 run_command 调用", "run_command" in tools_used2)
except Exception as e:
    check(f"  测试2 异常: {e}", False)
print()

print("=" * 66)
print(f"端到端结果: {passed} 通过, {failed} 失败")
print("=" * 66)
sys.exit(1 if failed else 0)
