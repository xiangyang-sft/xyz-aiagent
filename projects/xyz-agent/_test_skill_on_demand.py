#!/usr/bin/env python3
"""验证 skill 按需加载（skill_view/skill_list）机制（本地，不调用 LLM）。

验证点：
  1. 加载 >5 个 skill 时，主 system prompt 只含目录、不含完整详情
  2. skill_view 能加载指定 skill 的完整详情
  3. skill_list 能列出所有 skill 目录
  4. 完整 system prompt 中仍保留了 skill_view 的使用指引
  5. Agent 自动注册 skill_list / skill_view 工具
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from xyz_agent.agent import Agent, AgentConfig
from xyz_agent.skill_tools import skill_view, skill_list, set_active_skill_manager
from xyz_agent.skill import SkillManager

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

print("=" * 60)
print("准备: 加载 6 个 skill（>5 触发按需加载）")
print("=" * 60)
mgr = SkillManager()
loaded = mgr.load_directory(skill_dir)
names = sorted(s.name for s in mgr)
print(f"  加载 {loaded} 个: {names}")
check("  加载了至少 6 个 skill", len(mgr) >= 6)

print()
print("=" * 60)
print("验证 1: Agent 主 system prompt 只含目录、不含完整详情")
print("=" * 60)
config = AgentConfig(
    model="mock",
    skill_dirs=[skill_dir],
    enable_commands=False,
    enable_mcp=False,
)
agent = Agent(config=config)
agent.initialize()
sys_prompt = agent._build_system_prompt()

# 目录应包含所有 skill 名
for name in ["weather", "devops", "calculator", "translator", "git-helper", "notes"]:
    check(f"  目录包含 '{name}'", f"- {name}" in sys_prompt or name in sys_prompt)

# 说明不再注入完整详情：不应出现 skill 特有的详细内容关键词
too_big_markers = [
    "实时天气信息查询",      # weather 详情
    "引用内置 file/terminal 系统工具",  # devops 详情开头
    "安全地计算一个数学表达式",          # calculator 详情里的实现说明
]
for marker in too_big_markers:
    # 注意：有些 marker 也可能恰好出现在 description 里，这里挑选描述中不含、只在详情出现的词
    pass  # 详见下方针对性检查

# 针对性：完整详情（如 weather 的"使用场景"小节标题）不应出现
check(
    "  完整详情未注入 (无 '## 使用场景')",
    "## 使用场景" not in sys_prompt,
)
check(
    "  完整详情未注入 (无 '提供的工具')",
    "提供的工具" not in sys_prompt,
)

print()
print("=" * 60)
print("验证 2: system prompt 保留了 skill_view 使用指引")
print("=" * 60)
check(
    "  包含按需加载指引 (skill_view)",
    "skill_view" in sys_prompt and "按需加载" in sys_prompt,
)

print()
print("=" * 60)
print("验证 3: skill_view 加载指定 skill 详情")
print("=" * 60)
set_active_skill_manager(mgr)
weather_detail = skill_view("weather")
check("  skill_view('weather') 返回详情", "使用场景" in weather_detail or "天气" in weather_detail)
check("  详情含 skill 名标记", "weather skill" in weather_detail)
calc_detail = skill_view("calculator")
check("  skill_view('calculator') 返回详情含实现说明", "calc" in calc_detail)
missing = skill_view("nonexistent")
check("  skill_view('不存在') 返回错误提示", "未找到" in missing)

print()
print("=" * 60)
print("验证 4: skill_list 列出目录")
print("=" * 60)
lst = skill_list()
check("  skill_list 包含 weather", "weather" in lst)
check("  skill_list 包含 git-helper", "git-helper" in lst)
check("  skill_list 标注数量", "共 6 个" in lst or "共 7 个" in lst)

print()
print("=" * 60)
print("验证 5: Agent 自动注册 skill_list / skill_view 工具")
print("=" * 60)
tool_names = {t["name"] for t in agent.tool_registry.list_tools()}
check("  skill_list 已注册", "skill_list" in tool_names)
check("  skill_view 已注册", "skill_view" in tool_names)
print(f"  全部工具: {sorted(tool_names)}")

# 通过注册表真实执行 skill_view
if "skill_view" in tool_names:
    res = agent.tool_registry.execute("skill_view", {"name": "notes"})
    check("  通过 registry 执行 skill_view('notes') 成功", "notes skill" in res and "笔记" in res)

print()
print("=" * 60)
print(f"结果: {passed} 通过, {failed} 失败")
print("=" * 60)
sys.exit(1 if failed else 0)
