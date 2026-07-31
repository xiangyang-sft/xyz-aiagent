#!/usr/bin/env python3
"""验证重构后的系统工具集与 Skill 引用机制（本地，不调用 LLM）。

验证点：
  1. 内置 file/terminal 工具已注册到默认 registry（真实能力，非占位）
  2. 写入/读取文件真实可用
  3. 执行命令真实可用
  4. devops skill 声明的工具引用了全局真实工具（非 lambda 占位）
  5. Agent 初始化后内置工具自动可见
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from xyz_agent.tool import _default_registry
from xyz_agent.system_tools import list_toolsets
from xyz_agent.skill import SkillManager
from xyz_agent.agent import Agent, AgentConfig

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


def is_real_system_tool(tool):
    """判断工具是否绑定到内置真实函数（来自 system_tools 模块）"""
    return tool is not None and getattr(tool.fn, "__module__", "") == "xyz_agent.system_tools"


print("=" * 60)
print("验证 1: 内置系统工具已注册且为真实能力")
print("=" * 60)
print(f"  toolsets: {list_toolsets()}")
for name in ["read_file", "write_file", "list_dir", "run_command"]:
    tool = _default_registry.get_tool(name)
    check(f"  '{name}' 已注册且为内置真实能力", is_real_system_tool(tool))

print()
print("=" * 60)
print("验证 2: 文件写入/读取真实可用")
print("=" * 60)
with tempfile.TemporaryDirectory() as td:
    demo_file = os.path.join(td, "demo.txt")
    # 直接调用注册表 execute，模拟 LLM 发起工具调用
    result = _default_registry.execute("write_file", {"path": demo_file, "content": "hello xyz"})
    check(f"  write_file 返回: {result.strip()[:60]}", "已写入" in result)
    content = _default_registry.execute("read_file", {"path": demo_file})
    check(f"  read_file 读回: {content.strip()}", content.strip() == "hello xyz")
    ls = _default_registry.execute("list_dir", {"path": td})
    check(f"  list_dir 能看到 demo.txt: {ls.strip()}", "demo.txt" in ls)

print()
print("=" * 60)
print("验证 3: 命令执行真实可用")
print("=" * 60)
out = _default_registry.execute("run_command", {"command": "echo xyz-system-tools"})
check(f"  run_command echo: {out.strip()}", "xyz-system-tools" in out)

print()
print("=" * 60)
print("验证 4: devops skill 声明工具引用全局真实工具（非占位）")
print("=" * 60)
skill_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")
mgr = SkillManager()  # 内部使用独立 registry
loaded = mgr.load_directory(skill_dir)
check(f"  加载 {loaded} 个 skill", loaded >= 1)
devops = mgr.get("devops")
check("  devops skill 存在", devops is not None)
if devops:
    declared = [t.get("name") for t in devops.tools]
    print(f"  devops 声明工具: {declared}")
    # 验证引用：SkillManager 的 registry 应与默认 registry 共享（Agent 场景）
    # 此处直接读取默认 registry 中的同名工具，确认是真实函数而非占位
    for name in declared:
        tool = _default_registry.get_tool(str(name))
        check(f"    '{name}' 是内置真实能力", is_real_system_tool(tool))

print()
print("=" * 60)
print("验证 5: Agent 初始化后内置工具自动可见")
print("=" * 60)
config = AgentConfig(
    model="mock",
    skill_dirs=[skill_dir],
    enable_commands=False,
    enable_mcp=False,
)
agent = Agent(config=config)
agent.initialize()
tool_names = {t["name"] for t in agent.tool_registry.list_tools()}
print(f"  Agent 工具: {sorted(tool_names)}")
check("  read_file 可见", "read_file" in tool_names)
check("  run_command 可见", "run_command" in tool_names)
print(f"  engine.tools 数量: {len(agent.engine.tools) if agent.engine else 0}")

print()
print("=" * 60)
print("验证 6: weather skill 自带真实实现（文件 fn 动态加载）")
print("=" * 60)
# 通过 Agent 的 skill_manager 检查 weather 工具是否注册为真实函数
wmgr = agent.skill_manager
weather = wmgr.get("weather") if wmgr else None
check("  weather skill 存在", weather is not None)
if weather:
    print(f"  weather 声明工具: {[t.get('name') for t in weather.tools]}")
# weather 工具注册名为 skill 前缀 + 工具名
for name in ["weather_get_current_weather", "weather_get_weather_forecast", "weather_get_air_quality"]:
    tool = agent.tool_registry.get_tool(name)
    # 真实实现来自 scripts/impl.py，模块名形如 _skill_mod_impl.py_*
    mod = getattr(tool.fn, "__module__", "") if tool else ""
    is_real = tool is not None and mod.startswith("_skill_mod_")
    check(f"  '{name}' 已实现且可执行 (mod={mod})", is_real)
# 真实执行一次（走 Agent 的 tool_registry）
try:
    wr = agent.tool_registry.execute("weather_get_current_weather", {"city": "北京"})
    check(f"  执行 get_current_weather('北京'): {wr[:40]}", "北京" in wr)
except Exception as e:
    check(f"  执行 get_current_weather 失败: {e}", False)
try:
    waq = agent.tool_registry.execute("weather_get_air_quality", {"city": "广州"})
    check(f"  执行 get_air_quality('广州'): {waq[:40]}", "广州" in waq)
except Exception as e:
    check(f"  执行 get_air_quality 失败: {e}", False)

print()
print("=" * 60)
print(f"结果: {passed} 通过, {failed} 失败")
print("=" * 60)
sys.exit(1 if failed else 0)
