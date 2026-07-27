#!/usr/bin/env python3
"""
📦 xyz-agent v1.0 — 全功能架构演示

展示 xyz-agent 框架的所有核心能力：
  1. Skill 系统 — 从目录加载 SKILL.md
  2. 命令系统 — /help, /tools, /skills 等
  3. 工具注册 — @tool 装饰器 + 手动注册 + MCP 格式
  4. 引擎升级 — Function Calling + 传统 ReAct 双模式
  5. 扩展加载器 — 从配置文件自动发现扩展
  6. 混合模式 — 所有系统协同工作

运行:
  cd projects/xyz-agent
  pip install pyyaml
  python step4-production-demo.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import json

from xyz_agent import (
    Agent, AgentConfig,
    ToolRegistry, tool,
    SkillManager,
    CommandSystem,
    ExtensionLoader,
    load_skills, list_skills,
    execute_command, is_command,
    get_default_command_system,
)


def section(title: str):
    """打印分区标题"""
    print()
    print("=" * 70)
    print(f"  📌 {title}")
    print("=" * 70)
    print()


# ============================================================
# 演示 1: Skill 系统
# ============================================================

def demo_skill_system():
    section("1️⃣ Skill 系统 — 从目录加载 SKILL.md")

    # 创建 Skill 管理器
    skill_mgr = SkillManager()

    # 加载示例 Skill 目录
    skill_dir = os.path.join(os.path.dirname(__file__), "skills")
    if os.path.isdir(skill_dir):
        count = skill_mgr.load_directory(skill_dir)
        print(f"  从 {skill_dir} 加载了 {count} 个 Skill")
    else:
        print(f"  ⚠️ Skill 目录不存在: {skill_dir}")

    # 也可以从字符串加载一个 Skill
    skill_mgr.load_skill("demo-skill", """---
name: demo-skill
description: 演示 Skill
---

这是一个演示 Skill 的 system prompt 内容。
Agent 会自动融合到系统提示词中。
""")

    print(f"\n  总共加载了 {len(skill_mgr)} 个 Skill:")
    for s in skill_mgr:
        print(f"    📦 {s.name} v{s.version}")
        print(f"      描述: {s.description[:60]}...")
        if s.tools:
            print(f"      工具: {len(s.tools)} 个")
            for t in s.tools:
                print(f"        🔧 {t.get('name')}: {t.get('description', '')[:50]}")
        print()

    # 获取 system prompt
    prompts = skill_mgr.get_system_prompts()
    print(f"\n  Skill 贡献的 system prompt 片段: {len(prompts)} 段")

    # 关联的工具注册表
    registry = skill_mgr.get_tool_registry()
    print(f"  工具注册表: {len(registry)} 个工具")

    return skill_mgr


# ============================================================
# 演示 2: 命令系统
# ============================================================

def demo_command_system():
    section("2️⃣ 命令系统 — 内建命令 + 外部命令")

    cmd = CommandSystem()

    # 测试内建命令
    print("  内建命令测试:")
    print(f"    /help      => {cmd.execute('/help')[:80]}...")
    print(f"    /version   => {cmd.execute('/version')}")
    print(f"    /tools     => {cmd.execute('/tools')}")
    print()

    # 注册自定义命令
    @cmd.register("hello", "打个招呼", usage="/hello [名字]")
    def hello_handler(args: str, ctx: dict) -> str:
        return f"你好，{args or '世界'}！欢迎使用 xyz-agent 🎉"

    @cmd.register("echo", "回显消息", usage="/echo <消息>")
    def echo_handler(args: str, ctx: dict) -> str:
        return f"📢 {args}"

    print("  自定义命令测试:")
    print(f"    /hello 向阳 => {cmd.execute('/hello 向阳')}")
    print(f"    /echo 测试消息 => {cmd.execute('/echo 测试消息')}")

    # 检查命令
    print(f"\n  命令检测:")
    print(f"    '/help' 是命令吗? {cmd.is_command('/help')}")
    print(f"    '你好' 是命令吗? {cmd.is_command('你好')}")

    return cmd


# ============================================================
# 演示 3: 扩展加载器
# ============================================================

def demo_extension_loader():
    section("3️⃣ 扩展加载器 — 自动发现外部扩展")

    loader = ExtensionLoader()

    # 生成示例配置
    from xyz_agent.loader import generate_sample_config
    config_path = "/tmp/xyz-extensions-demo.yaml"
    if not os.path.exists(config_path):
        generate_sample_config(config_path)
        print(f"  已生成示例扩展配置: {config_path}")

    # 加载配置
    count = loader.load_config(config_path)
    print(f"  从配置文件发现了 {count} 个扩展:")
    print(f"    Skills: {len(loader.skills)}")
    print(f"    MCP Servers: {len(loader.mcp)}")
    print(f"    Commands: {len(loader.commands)}")
    print(f"    Plugins: {len(loader.plugins)}")

    # 扫描本地目录
    local_dir = os.path.join(os.path.dirname(__file__), "extensions")
    os.makedirs(local_dir, exist_ok=True)
    count = loader.load_directory(local_dir)
    print(f"  本地目录额外扫描: {count} 个扩展")

    return loader


# ============================================================
# 演示 4: Agent 集成 — 所有系统协同工作
# ============================================================

def demo_agent_integration():
    section("4️⃣ Agent 集成 — 所有系统协同")

    # 注册一些测试工具
    @tool
    def greet(name: str, greeting: str = "你好") -> str:
        """向某人打招呼"""
        return f"{greeting}，{name}！"

    @tool
    def calculator(expr: str) -> str:
        """计算数学表达式（安全）"""
        allowed = set("0123456789+-*/(). ")
        if not all(c in allowed for c in expr):
            return "错误：表达式包含非法字符"
        try:
            return f"{expr} = {eval(expr)}"
        except Exception as e:
            return f"计算错误: {e}"

    # 创建 Agent（使用 Mock Provider — 无 API key 也能跑）
    agent = Agent(
        config=AgentConfig(
            name="demo-agent",
            model="mock",
            auto_load_skills=False,
            auto_load_extensions=False,
        ),
    )

    # 手动初始化
    agent.initialize()

    # 查看 Agent 信息
    info = agent.get_info()
    print(f"  Agent 名称: {info['name']}")
    print(f"  版本: {info['version']}")
    print(f"  初始化: {'✅' if info['initialized'] else '❌'}")
    print(f"  工具数: {info['tools']}")

    print(f"\n  注册的工具:")
    for t in agent.list_tools():
        print(f"    🔧 {t['name']}: {t['description'][:50]}")

    print(f"\n  命令系统:")
    if agent.command_system:
        print(f"    /help  => {agent.command_system.execute('/help')[:60]}...")

    return agent


# ============================================================
# 演示 5: Skill + MCP + Commands + Tools 混合演示
# ============================================================

def demo_full_integration():
    section("5️⃣ 完整集成 — 生产级 Agent 启动流程")

    config = AgentConfig(
        name="production-agent",
        enable_skills=True,
        enable_commands=True,
        enable_mcp=False,  # MCP 需要 Node.js，禁用但代码就绪
        auto_load_skills=False,
        auto_load_extensions=False,
        verbose=True,
    )

    agent = Agent(config=config)
    agent.initialize()

    print(f"  ✅ Agent '{agent.name}' 就绪!")
    print(f"  工具: {len(agent.list_tools())} 个")
    print(f"  Skill: {len(agent.list_skills())} 个")
    print(f"  引擎模式: {agent.engine._mode}")

    # 测试命令处理
    print("\n  /help 命令:")
    if agent.command_system:
        print(f"  {agent.command_system.execute('/help')[:120]}...")

    print("\n  /version 命令:")
    if agent.command_system:
        print(f"  {agent.command_system.execute('/version')}")

    print("\n  ✅ 所有系统正常运作！")


# ============================================================
# 演示 6: 架构全景图
# ============================================================

def demo_architecture():
    section("6️⃣ xyz-agent v1.0 架构全景")

    arch = """
╔═════════════════════════════════════════════════════════╗
║              xyz-agent v1.0 架构全景                      ║
╠═════════════════════════════════════════════════════════╣
║                                                         ║
║  User ──▶ Agent (统一入口)                               ║
║              │                                           ║
║              ├── CommandSystem ─── /help /tools /skills  ║
║              │    (slash 命令解析)                        ║
║              │                                           ║
║              ├── ReActEngine v2 ─── 推理循环              ║
║              │    ├── ReAct 模式 (文本解析)               ║
║              │    └── Function Calling 模式 (原生格式)     ║
║              │                                           ║
║              ├── ToolRegistry ─── 工具管理                ║
║              │    ├── @tool 装饰器                       ║
║              │    ├── 手动注册 + MCP 格式                ║
║              │    └── 自动 OpenAI Schema 生成             ║
║              │                                           ║
║              ├── SkillManager ─── Skill 系统              ║
║              │    ├── SKILL.md 目录加载                  ║
║              │    ├── Hermes Agent 兼容格式               ║
║              │    └── System Prompt 自动融合              ║
║              │                                           ║
║              ├── MCPManager ─── MCP 客户端                ║
║              │    ├── stdio 传输 (本地子进程)              ║
║              │    ├── HTTP 传输 (远程服务器)              ║
║              │    └── 自动工具发现 + 注册                 ║
║              │                                           ║
║              ├── ExtensionLoader ─── 扩展自动发现          ║
║              │    ├── YAML/JSON 配置加载                  ║
║              │    ├── 目录扫描 + Python 插件              ║
║              │    └── 自动应用到各管理器                   ║
║              │                                           ║
║              └── LLMProvider ─── 多种后端                 ║
║                   ├── OpenAI (Function Calling)           ║
║                   ├── OpenRouter                          ║
║                   └── Mock (测试)                         ║
║                                                         ║
║  外部生态适配:                                           ║
║    ├── Hermes Agent SKILL.md (skills/)                  ║
║    ├── MCP 服务器 (mcp:)                                 ║
║    ├── OpenAI Function Calling                           ║
║    └── 自定义 Python 插件 (.plugin.py)                   ║
║                                                         ║
╚═════════════════════════════════════════════════════════╝
"""
    print(arch)


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║     xyz-agent v1.0 — 生产级架构完整演示        ║")
    print("║     7 大子系统 · Skill/MCP/Commands/FC          ║")
    print("╚══════════════════════════════════════════════════╝")
    print()
    print(f"框架版本: {__import__('xyz_agent').__version__}")
    print(f"Python: {sys.version.split()[0]}")
    print()

    demo_architecture()
    demo_skill_system()
    demo_command_system()
    demo_extension_loader()
    demo_agent_integration()
    demo_full_integration()

    print()
    print("=" * 70)
    print("  ✅ xyz-agent v1.0 架构升级全部演示完成！")
    print()
    print("  新模块:")
    print("    📦 skill.py      — Skill 系统")
    print("    🔌 mcp_client.py — MCP 客户端")
    print("    ⌨️  command.py    — 命令系统")
    print("    📂 loader.py     — 扩展加载器")
    print("    🚀 providers.py  — LLM Provider")
    print("    ⚙️  engine.py     — 引擎 v2（Function Calling）")
    print("    🎯 agent.py      — Agent v2（集成所有子系统）")
    print()
    print("  外部生态适配:")
    print("    ✅ Hermes Agent SKILL.md 格式")
    print("    ✅ MCP 服务器协议（stdio/HTTP）")
    print("    ✅ OpenAI Function Calling")
    print("    ✅ YAML/JSON 配置驱动的扩展加载")
    print("=" * 70)
    print()
