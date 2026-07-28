#!/usr/bin/env python3
"""
xyz_agent.cli — 命令行接口（v2 — 业界通用设计）

提供业界标准的 Agent CLI 体验，支持：

  全局命令:
    xyz run <问题>              — 单次运行 Agent
    xyz chat                    — 交互式对话（slash 命令模式）
    xyz shell                   — Agent Shell（高级互动）

  资源管理:
    xyz tool list               — 列出所有工具
    xyz tool add <name> <code>  — 注册新工具
    xyz skill list              — 列出所有 Skill
    xyz skill load <path>       — 加载 Skill 目录
    xyz mcp list                — 查看 MCP 服务器
    xyz mcp connect <name> <cmd> — 连接 MCP 服务器
    xyz config get/set          — 配置管理

  交互模式 (/slash 命令):
    /help                       — 帮助
    /tool list                  — 列出工具
    /tool add ...               — 添加工具
    /skill list                 — 列出 Skill
    /skill load <path>          — 加载 Skill
    /mcp list                   — 列出 MCP 服务器
    /mcp connect <name> <cmd>   — 连接 MCP
    /config get/set             — 配置
    /clear                      — 清屏
    /exit                       — 退出
    /reset                      — 重置对话
"""

import sys
import os
import json
import shlex
import logging
from typing import Dict, List, Optional, Any

from . import __version__
from .agent import Agent, AgentConfig
from .tool import ToolRegistry, tool as tool_decorator, _default_registry
from .skill import SkillManager, load_skills, list_skills as _list_skills
from .mcp_client import MCPManager
from .providers import OpenAIProvider, MockProvider
from .loader import ExtensionLoader, generate_sample_config

logger = logging.getLogger(__name__)


# ============================================================
# 彩色输出
# ============================================================

class Style:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def _color(text: str, color: str) -> str:
    if os.name == "nt":  # Windows
        return text
    return f"{color}{text}{Style.RESET}"


def _print_banner():
    """打印启动 Banner"""
    banner = f"""
{Style.CYAN}╭{'─' * 56}╮
│{' ' * 18}xyz-agent v{__version__}{' ' * 20}│
│{' ' * 12}{Style.DIM}生产级 AI Agent 框架{Style.RESET}{Style.CYAN}{' ' * 14}│
│{' ' * 12}{Style.DIM}Skill · MCP · Tool · FC{Style.RESET}{Style.CYAN}{' ' * 12}│
╰{'─' * 56}╯{Style.RESET}
"""
    print(banner)


# ============================================================
# 全局 Agent 实例
# ============================================================

_agent: Optional[Agent] = None


def _get_agent() -> Agent:
    """获取或创建全局 Agent 实例"""
    global _agent
    if _agent is None:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if api_key:
            _agent = Agent.from_openai(api_key=api_key)
            # 扩展配置：启用所有子系统
            _agent.config.enable_skills = True
            _agent.config.enable_commands = True
            _agent.config.auto_load_skills = True
        else:
            _agent = Agent(
                llm_provider=MockProvider(),
                config=AgentConfig(name="cli-agent",
                                   enable_skills=True,
                                   enable_commands=True,
                                   auto_load_skills=True),
            )
        _agent.initialize()
        # 强制加载 Hermes Agent 的 Skills
        hermes_skills = os.path.expanduser("~/.hermes/skills/")
        if _agent.skill_manager is not None and os.path.isdir(hermes_skills):
            count = _agent.skill_manager.load_directory(hermes_skills)
            if count > 0:
                _agent.rebuild_engine()
                logger.info(f"已加载 {count} 个 Hermes Agent Skill")
        logger.info(f"Agent 已初始化 ({_agent.config.model})")
    return _agent


# ============================================================
# 1. 交互式 Shell（最核心功能）
# ============================================================

def cmd_shell():
    """
    交互式 Agent Shell — 业界通用 slash 命令体验
    """
    agent = _get_agent()
    _print_banner()

    # 显示连接信息
    info = agent.get_info()
    model = info["model"]
    tools_n = info["tools"]
    skills_n = info["skills"]
    print(f"  {Style.GREEN}模型:{Style.RESET} {model}" +
          f"  {Style.GREEN}工具:{Style.RESET} {tools_n}" +
          f"  {Style.GREEN}Skill:{Style.RESET} {skills_n}")
    print(f"  输入 {Style.YELLOW}/help{Style.RESET} 查看命令，{Style.YELLOW}/exit{Style.RESET} 退出\n")

    while True:
        try:
            user_input = input(f"{Style.BOLD}│ {Style.CYAN}󰚩{Style.RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        # /exit 退出
        if user_input in ("/exit", "/quit", ":q", "exit", "quit"):
            print(f"{Style.YELLOW}再见！👋{Style.RESET}")
            break

        # 处理 slash 命令
        if user_input.startswith("/"):
            _handle_slash_command(user_input, agent)
            continue

        # 普通对话
        try:
            result = agent.chat(user_input)
            print(f"{Style.GREEN}│{Style.RESET} {result}")
        except Exception as e:
            print(f"{Style.RED}✗ 错误: {e}{Style.RESET}")


# ============================================================
# 2. Slash 命令处理器
# ============================================================

COMMAND_HELP = """
{Style.BOLD}可用命令:{Style.RESET}

{Style.CYAN}  系统命令{Style.RESET}
    /help                   显示此帮助
    /exit                   退出
    /clear                  重置对话
    /reset                  重置 Agent 状态

{Style.CYAN}  工具管理{Style.RESET}
    /tool list              列出所有注册的工具
    /tool add <name> <desc> 注册一个工具
    /tool remove <name>     移除工具

{Style.CYAN}  Skill 管理{Style.RESET}
    /skill list             列出所有已加载的 Skill
    /skill load <path>      加载一个 Skill 目录
    /skill refresh          刷新所有 Skill

{Style.CYAN}  MCP 管理{Style.RESET}
    /mcp list               查看 MCP 服务器状态
    /mcp connect <name> <cmd> [args] 连接 MCP 服务器
    /mcp discover           发现并注册 MCP 工具
    /mcp disconnect <name>  断开 MCP 服务器

{Style.CYAN}  配置管理{Style.RESET}
    /config                 查看配置
    /config set <key> <val> 设置配置项

{Style.CYAN}  调试{Style.RESET}
    /stats                  查看运行统计
    /trace                  查看步骤追踪
"""


def _handle_slash_command(cmd: str, agent: Agent):
    """处理所有 slash 命令"""
    parts = shlex.split(cmd[1:])  # 去掉前导 /
    if not parts:
        return

    command = parts[0].lower()
    args = parts[1:]

    # === 系统命令 ===
    if command in ("help", "?"):
        print(COMMAND_HELP.format(**globals()))

    elif command in ("exit", "quit", "q"):
        print(f"{Style.YELLOW}再见！👋{Style.RESET}")
        sys.exit(0)

    elif command == "clear":
        os.system("clear" if os.name == "posix" else "cls")
        _print_banner()

    elif command == "reset":
        agent.reset()
        print(f"{Style.GREEN}✓ Agent 已重置{Style.RESET}")

    # === 工具管理 ===
    elif command == "tool":
        _handle_tool_command(args, agent)

    # === Skill 管理 ===
    elif command == "skill":
        _handle_skill_command(args, agent)

    # === MCP 管理 ===
    elif command == "mcp":
        _handle_mcp_command(args, agent)

    # === 配置 ===
    elif command == "config":
        _handle_config_command(args, agent)

    # === 调试 ===
    elif command == "stats":
        stats = agent.get_stats()
        print(f"{Style.CYAN}运行统计:{Style.RESET}")
        for k, v in stats.items():
            print(f"  {k}: {v}")

    elif command == "trace":
        if agent.engine:
            trace = agent.engine.get_trace(detail="full")
            print(f"{Style.CYAN}步骤追踪:{Style.RESET}")
            for t in trace:
                print(f"  Step {t['step']} [{t['type']}]: {t.get('content', '')[:80]}")
                if t.get("tool_result"):
                    print(f"    结果: {str(t['tool_result'])[:80]}")

    else:
        print(f"{Style.YELLOW}未知命令: /{command}  输入 /help 查看可用命令{Style.RESET}")


# ============================================================
# 2a. /tool 子命令
# ============================================================

def _handle_tool_command(args: List[str], agent: Agent):
    if not args:
        print(f"{Style.YELLOW}用法: /tool list | /tool add <name> <desc> | /tool remove <name>{Style.RESET}")
        return

    sub = args[0].lower()

    if sub == "list":
        tools = agent.list_tools()
        if not tools:
            print(f"{Style.DIM}当前没有注册的工具{Style.RESET}")
            return
        print(f"{Style.CYAN}注册工具 ({len(tools)}):{Style.RESET}")
        for t in tools:
            params = t.get("parameters", {}).get("properties", {})
            param_str = ", ".join(params.keys()) if params else "无参数"
            print(f"  {Style.GREEN}🔧{Style.RESET} {Style.BOLD}{t['name']}{Style.RESET}")
            print(f"     描述: {t['description'][:80]}")
            print(f"     参数: {param_str}")

    elif sub == "add" and len(args) >= 2:
        name = args[1]
        desc = " ".join(args[2:]) if len(args) > 2 else f"工具 {name}"

        # 注册一个桩工具
        agent.tool_registry.register_fn(
            name=name,
            fn=lambda **kw: f"[工具 {name} 执行结果]",
            description=desc,
        )
        print(f"{Style.GREEN}✓ 工具 '{name}' 已注册{Style.RESET}")

    elif sub == "remove" and len(args) >= 2:
        # 注意: ToolRegistry 没有 remove 方法，需要直接操作内部 dict
        if hasattr(agent.tool_registry, '_tools') and args[1] in agent.tool_registry._tools:
            del agent.tool_registry._tools[args[1]]
            print(f"{Style.GREEN}✓ 工具 '{args[1]}' 已移除{Style.RESET}")
        else:
            print(f"{Style.YELLOW}未知工具: {args[1]}{Style.RESET}")

    else:
        print(f"{Style.YELLOW}用法: /tool list | /tool add <name> <desc>{Style.RESET}")


# ============================================================
# 2b. /skill 子命令
# ============================================================

def _handle_skill_command(args: List[str], agent: Agent):
    if not args:
        print(f"{Style.YELLOW}用法: /skill list | /skill load <path> | /skill refresh{Style.RESET}")
        return

    sub = args[0].lower()

    if sub == "list":
        if agent.skill_manager is not None:
            skills = agent.skill_manager.list_skills()
            if not skills:
                print(f"{Style.DIM}当前没有加载 Skill{Style.RESET}")
                return

            # 分类展示
            by_tag = {}
            for s in skills:
                tag = s.tags[0] if s.tags else "未分类"
                if tag not in by_tag:
                    by_tag[tag] = []
                by_tag[tag].append(s)

            print(f"{Style.CYAN}已加载 Skill ({len(skills)}):{Style.RESET}")
            for tag, items in sorted(by_tag.items()):
                print(f"  [{tag}]")
                for s in items:
                    print(f"    {Style.GREEN}📦{Style.RESET} {Style.BOLD}{s.name}{Style.RESET} v{s.version}")
                    if s.description:
                        print(f"      {s.description[:70]}")
                    if s.tools:
                        print(f"      工具: {len(s.tools)} 个")
        else:
            print(f"{Style.YELLOW}Skill 系统未启用 (config.enable_skills=True){Style.RESET}")

    elif sub == "load" and len(args) >= 2:
        path = os.path.expanduser(args[1])
        if not os.path.isdir(path):
            print(f"{Style.YELLOW}目录不存在: {path}{Style.RESET}")
            return
        if agent.skill_manager is not None:
            count = agent.skill_manager.load_directory(path)
            print(f"{Style.GREEN}✓ 已加载 {count} 个 Skill (来自 {path}){Style.RESET}")
            if count > 0:
                # 重建引擎以注入新的 system prompt
                agent.rebuild_engine()
        else:
            print(f"{Style.YELLOW}Skill 系统未启用{Style.RESET}")

    elif sub == "refresh":
        if agent.skill_manager is not None:
            count = agent.refresh_skills()
            print(f"{Style.GREEN}✓ 刷新完成，新增/更新 {count} 个 Skill{Style.RESET}")
        else:
            print(f"{Style.YELLOW}Skill 系统未启用{Style.RESET}")

    elif sub == "generate":
        # 生成示例 Skill 文件
        path = args[1] if len(args) >= 2 else "./skills/my-skill/SKILL.md"
        path = os.path.expanduser(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        generate_sample_skill(path)
        print(f"{Style.GREEN}✓ 示例 Skill 已生成: {path}{Style.RESET}")

    else:
        print(f"{Style.YELLOW}用法: /skill list | /skill load <path> | /skill refresh | /skill generate [path]{Style.RESET}")


def generate_sample_skill(path: str):
    """生成示例 Skill 模板"""
    content = """---
name: my-skill
description: "我的自定义 Skill — 简短描述这个 Skill 的功能"
version: 1.0.0
author: xyz-agent
license: MIT
metadata:
  hermes:
    tags: [custom]
    related_skills: []
---

# My Skill

## 使用场景
- 场景 1：...
- 场景 2：...

## 提供的工具

```json
[
  {
    "name": "my_tool",
    "description": "工具描述",
    "parameters": {
      "type": "object",
      "properties": {
        "param1": {"type": "string", "description": "参数说明"}
      },
      "required": ["param1"]
    }
  }
]
```

## 指令

以下是这个 Skill 的系统指令内容，Agent 启动时自动融合。
可以在这里写工作流程、规则、提示等。
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ============================================================
# 2c. /mcp 子命令
# ============================================================

def _handle_mcp_command(args: List[str], agent: Agent):
    if not args:
        print(f"{Style.YELLOW}用法: /mcp list | /mcp connect <name> <cmd> [args] | /mcp disconnect <name> | /mcp discover{Style.RESET}")
        return

    sub = args[0].lower()

    if sub == "list":
        if agent.mcp_manager is not None:
            servers = agent.mcp_manager.list_servers()
            if not servers:
                print(f"{Style.DIM}没有连接的 MCP 服务器{Style.RESET}")
                return
            print(f"{Style.CYAN}MCP 服务器 ({len(servers)}):{Style.RESET}")
            for name in servers:
                server = agent.mcp_manager.get_server(name)
                status = f"{Style.GREEN}✅{Style.RESET}" if server and server.is_connected else f"{Style.RED}❌{Style.RESET}"
                tools_n = len(server.tools) if server else 0
                print(f"  {status} {Style.BOLD}{name}{Style.RESET} ({tools_n} 个工具)")
        else:
            print(f"{Style.YELLOW}MCP 未启用 (config.enable_mcp=True){Style.RESET}")

    elif sub == "connect" and len(args) >= 3:
        name = args[1]
        cmd = args[2]
        cmd_args = args[3:] if len(args) > 3 else []
        try:
            agent.setup_mcp(name, cmd, cmd_args)
            print(f"{Style.GREEN}✓ MCP 服务器 '{name}' 已连接{Style.RESET}")
        except Exception as e:
            print(f"{Style.RED}✗ 连接失败: {e}{Style.RESET}")

    elif sub == "disconnect" and len(args) >= 2:
        if agent.mcp_manager is not None:
            server = agent.mcp_manager.get_server(args[1])
            if server:
                import asyncio
                try:
                    asyncio.run(server.disconnect())
                    print(f"{Style.GREEN}✓ MCP 服务器 '{args[1]}' 已断开{Style.RESET}")
                except Exception as e:
                    print(f"{Style.RED}✗ 断开失败: {e}{Style.RESET}")
            else:
                print(f"{Style.YELLOW}未知服务器: {args[1]}{Style.RESET}")
        else:
            print(f"{Style.YELLOW}MCP 未启用{Style.RESET}")

    elif sub == "discover":
        if agent.mcp_manager is not None:
            agent.discover_mcp_tools()
            tools_count = len(agent.list_tools())
            print(f"{Style.GREEN}✓ MCP 工具已同步，当前共 {tools_count} 个工具{Style.RESET}")
        else:
            print(f"{Style.YELLOW}MCP 未启用{Style.RESET}")

    else:
        print(f"{Style.YELLOW}用法: /mcp list | /mcp connect <name> <cmd> [args] | /mcp disconnect <name> | /mcp discover{Style.RESET}")


# ============================================================
# 2d. /config 子命令
# ============================================================

def _handle_config_command(args: List[str], agent: Agent):
    if not args or args[0] == "list":
        config = agent.config
        print(f"{Style.CYAN}当前配置:{Style.RESET}")
        for k, v in config.__dict__.items():
            if not k.startswith("_"):
                print(f"  {Style.DIM}{k}:{Style.RESET} {v}")

    elif args[0] == "get" and len(args) >= 2:
        key = args[1]
        if hasattr(agent.config, key):
            val = getattr(agent.config, key)
            print(f"{key} = {val}")
        else:
            print(f"{Style.YELLOW}未知配置项: {key}{Style.RESET}")

    elif args[0] == "set" and len(args) >= 3:
        key = args[1]
        val = " ".join(args[2:])
        if hasattr(agent.config, key):
            # 类型转换
            old_val = getattr(agent.config, key)
            if isinstance(old_val, bool):
                val = val.lower() in ("true", "1", "yes")
            elif isinstance(old_val, int):
                val = int(val)
            elif isinstance(old_val, float):
                val = float(val)
            setattr(agent.config, key, val)
            print(f"{Style.GREEN}✓ {key} = {val}{Style.RESET}")
        else:
            print(f"{Style.YELLOW}未知配置项: {key}{Style.RESET}")

    else:
        print(f"{Style.YELLOW}用法: /config [list] | /config get <key> | /config set <key> <value>{Style.RESET}")


# ============================================================
# 3. 独立命令（非交互模式）
# ============================================================

def cmd_run(question: str):
    """单次运行 Agent"""
    agent = _get_agent()
    result = agent.run(question)
    print(result)


def cmd_chat():
    """交互式对话（旧版兼容，调用 shell）"""
    cmd_shell()


# ============================================================
# 4. 资源管理命令（xyz tool / xyz skill / xyz mcp）
# ============================================================

def cmd_tool(args: List[str]):
    """CLI 工具管理"""
    agent = _get_agent()

    if not args:
        tools = agent.list_tools()
        if not tools:
            print("当前没有注册的工具。")
            return
        print(f"可用工具 ({len(tools)}):")
        for t in tools:
            print(f"  🔧 {t['name']}: {t['description'][:60]}")
        return

    # 转发到 slash 命令处理器
    _handle_tool_command(args, agent)


def cmd_skill(args: List[str]):
    """CLI Skill 管理"""
    agent = _get_agent()

    if not args:
        if agent.skill_manager is not None:
            skills = agent.skill_manager.list_skills()
            print(f"已加载 {len(skills)} 个 Skill:")
            for s in skills:
                tools_info = f" ({len(s.tools)} 工具)" if s.tools else ""
                print(f"  📦 {s.name} v{s.version}{tools_info}")
        return

    _handle_skill_command(args, agent)


def cmd_mcp(args: List[str]):
    """CLI MCP 管理"""
    agent = _get_agent()

    if not args:
        if agent.mcp_manager is not None:
            servers = agent.mcp_manager.list_servers()
            if not servers:
                print("没有连接的 MCP 服务器。")
                return
            print(f"MCP 服务器 ({len(servers)}):")
            for name in servers:
                server = agent.mcp_manager.get_server(name)
                status = "✅" if server and server.is_connected else "❌"
                print(f"  {status} {name}")
        return

    _handle_mcp_command(args, agent)


def cmd_config(args: List[str]):
    """CLI 配置管理"""
    agent = _get_agent()

    if not args:
        config = agent.config
        print("当前配置:")
        for k, v in config.__dict__.items():
            if not k.startswith("_"):
                print(f"  {k}: {v}")
        return

    _handle_config_command(args, agent)


# ============================================================
# 5. 主要入口
# ============================================================

USAGE = f"""{Style.CYAN}xyz-agent v{__version__}{Style.RESET} — 生产级 AI Agent 框架

{Style.BOLD}用法:{Style.RESET}
  xyz run <问题>             单次运行
  xyz chat                   交互式 Shell (推荐)
  xyz shell                  交互式 Shell（同 chat）

  xyz tool list              列出工具
  xyz skill list             列出 Skill
  xyz mcp list               查看 MCP 状态
  xyz config                 查看配置

  xyz skill load <path>      加载 Skill
  xyz mcp connect <name> <cmd> [args]  连接 MCP

  xyz --help                 显示帮助
  xyz --version              显示版本
"""

FLAG_HELP = """
{Style.BOLD}Slash 命令（交互模式下可用）:{Style.RESET}
  /help             此帮助
  /tool list        列出工具
  /tool add ...     添加工具
  /skill list       列出 Skill
  /skill load <path> 加载 Skill
  /mcp list         查看 MCP
  /mcp connect ...  连接 MCP
  /config get/set   配置
  /clear            清屏
  /exit             退出
  /stats            统计
"""


def print_help():
    print(USAGE)


def main():
    """CLI 主入口"""
    if len(sys.argv) < 2:
        print(USAGE)
        return

    command = sys.argv[1]
    args = sys.argv[2:]

    # 版本
    if command in ("--version", "-v", "version"):
        print(f"xyz-agent v{__version__}")
        return

    # 帮助
    if command in ("--help", "-h", "help"):
        if args and args[0] == "slash":
            print(FLAG_HELP)
        else:
            print(USAGE)
        return

    # 交互模式
    if command in ("chat", "shell", "interactive"):
        cmd_shell()
        return

    # 单次运行
    if command == "run":
        if not args:
            print("请提供问题。用法: xyz run <问题>")
            return
        cmd_run(" ".join(args))
        return

    # 工具管理
    if command == "tool":
        cmd_tool(args)
        return

    # Skill 管理
    if command == "skill":
        cmd_skill(args)
        return

    # MCP 管理
    if command == "mcp":
        cmd_mcp(args)
        return

    # 配置管理
    if command == "config":
        cmd_config(args)
        return

    # 生成示例配置
    if command == "init":
        path = args[0] if args else "~/.xyz-agent/extensions.yaml"
        path = generate_sample_config(path)
        print(f"✓ 示例配置已生成: {path}")
        print("  编辑后配置会在 Agent 启动时自动加载")
        return

    print(f"未知命令: {command}")
    print(USAGE)
    sys.exit(1)


if __name__ == "__main__":
    main()
