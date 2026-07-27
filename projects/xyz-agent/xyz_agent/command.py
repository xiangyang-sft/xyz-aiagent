#!/usr/bin/env python3
"""
xyz_agent.command — 命令系统

支持 Agent 内建命令和外部扩展命令的解析与执行。

功能:
  - 内建命令: /help, /tools, /skills, /mcp, /clear, /config, /version
  - 外部命令: 通过命令注册表动态添加
  - Slash 命令解析: 统一的 /cmd [args] 语法
  - 自动补全支持（预留）

用法:
    cmd_system = CommandSystem()

    @cmd_system.register("hello", "打招呼")
    def hello_cmd(args: str, context: dict) -> str:
        return f"你好，{args or '世界'}！"

    result = cmd_system.execute("/hello 向阳")
"""

import re
import shlex
import logging
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============================================================
# 命令定义
# ============================================================

@dataclass
class CommandDef:
    """命令定义"""
    name: str
    description: str
    handler: Callable[[str, Dict], str]
    usage: str = ""
    category: str = "general"
    hidden: bool = False


CommandContext = Dict[str, Any]
"""命令执行上下文:
  {
    "agent": None | Agent,       # 当前 Agent 实例
    "engine": None | Engine,     # 当前引擎实例
    "tool_registry": None | ToolRegistry,
    "skill_manager": None | SkillManager,
    "mcp_manager": None | MCPManager,
    "session_id": str,
    "config": dict,
  }
"""


# ============================================================
# 命令系统
# ============================================================

class CommandSystem:
    """
    命令系统

    用法:
        cmd = CommandSystem()
        cmd.register("help", "显示帮助", help_handler)

        # 执行命令
        result = cmd.execute("/help")
        result = cmd.execute("/tools")

        # 检查是否是命令
        if cmd.is_command("/help"):
            ...
    """

    def __init__(self):
        self._commands: Dict[str, CommandDef] = {}
        self._context: CommandContext = {}

        # 注册内建命令
        self._register_builtins()

    def set_context(self, **kwargs):
        """设置命令执行上下文"""
        self._context.update(kwargs)

    def update_context(self, **kwargs):
        """更新上下文"""
        self._context.update(kwargs)

    def get_context(self) -> CommandContext:
        return self._context

    # ---- 注册 ----

    def register(self, name: str, description: str,
                 usage: str = "", category: str = "general",
                 hidden: bool = False):
        """装饰器方式注册命令"""
        def decorator(handler: Callable[[str, Dict], str]):
            self._commands[name] = CommandDef(
                name=name,
                description=description,
                handler=handler,
                usage=usage or f"/{name} [args]",
                category=category,
                hidden=hidden,
            )
            return handler
        return decorator

    def register_cmd(self, name: str, handler: Callable[[str, Dict], str],
                     description: str = "", usage: str = "",
                     category: str = "general", hidden: bool = False) -> CommandDef:
        """直接注册命令"""
        cmd_def = CommandDef(
            name=name,
            description=description or f"/{name} 命令",
            handler=handler,
            usage=usage or f"/{name} [args]",
            category=category,
            hidden=hidden,
        )
        self._commands[name] = cmd_def
        return cmd_def

    def unregister(self, name: str):
        """注销命令"""
        self._commands.pop(name, None)

    # ---- 执行 ----

    def is_command(self, text: str) -> bool:
        """判断文本是否为命令"""
        return text.strip().startswith("/")

    def parse_command(self, text: str) -> Optional[tuple]:
        """
        解析命令文本

        返回:
          (command_name, args_str) 或 None
        """
        text = text.strip()
        if not text.startswith("/"):
            return None

        # /cmd arg1 arg2 "arg with spaces"
        try:
            parts = shlex.split(text[1:])
        except ValueError:
            parts = text[1:].split()

        if not parts:
            return None

        cmd_name = parts[0].lower()
        args_str = " ".join(parts[1:]) if len(parts) > 1 else ""

        return (cmd_name, args_str)

    def execute(self, text: str) -> str:
        """执行命令"""
        parsed = self.parse_command(text)
        if not parsed:
            return f"无效命令: {text}"

        cmd_name, args_str = parsed

        if cmd_name not in self._commands:
            similar = self._find_similar(cmd_name)
            hint = f"，你是不是想用: {'/'.join(similar)}" if similar else ""
            return f"未知命令: /{cmd_name}{hint}。输入 /help 查看可用命令"

        cmd_def = self._commands[cmd_name]
        try:
            return cmd_def.handler(args_str, self._context)
        except Exception as e:
            logger.error(f"命令 '{cmd_name}' 执行失败: {e}")
            return f"命令 /{cmd_name} 执行错误: {e}"

    def execute_from_text(self, text: str) -> Optional[str]:
        """
        从文本中检测并执行命令

        如果文本是命令则执行并返回结果，否则返回 None。
        """
        if self.is_command(text):
            return self.execute(text)
        return None

    def get_all_commands(self, include_hidden: bool = False) -> Dict[str, List[CommandDef]]:
        """按分类获取所有命令"""
        grouped: Dict[str, List[CommandDef]] = {}
        for cmd in self._commands.values():
            if cmd.hidden and not include_hidden:
                continue
            if cmd.category not in grouped:
                grouped[cmd.category] = []
            grouped[cmd.category].append(cmd)
        return grouped

    # ---- 内建命令 ----

    def _register_builtins(self):
        """注册内建命令"""

        # /help — 显示帮助
        def help_handler(args: str, ctx: CommandContext) -> str:
            grouped = self.get_all_commands()
            lines = ["📋 可用命令:", ""]
            for category, cmds in grouped.items():
                lines.append(f"  [{category}]")
                for cmd in cmds:
                    lines.append(f"    /{cmd.name:<12} {cmd.description}")
                lines.append("")
            return "\n".join(lines)

        self.register_cmd(
            "help", help_handler,
            description="显示帮助信息",
            usage="/help [命令名]",
            category="system",
        )

        # /tools — 列出工具
        def tools_handler(args: str, ctx: CommandContext) -> str:
            registry = ctx.get("tool_registry")
            if not registry:
                return "工具注册表未配置"

            tools = registry.list_tools()
            if not tools:
                return "当前没有注册的工具。"

            lines = [f"🔧 可用工具 ({len(tools)}):"]
            for t in tools:
                lines.append(f"  • {t['name']}: {t['description']}")
            return "\n".join(lines)

        self.register_cmd(
            "tools", tools_handler,
            description="列出所有工具",
            usage="/tools",
            category="system",
        )

        # /skills — 列出 Skill
        def skills_handler(args: str, ctx: CommandContext) -> str:
            skill_mgr = ctx.get("skill_manager")
            if not skill_mgr:
                return "Skill 管理器未配置"

            skills = skill_mgr.list_skills()
            if not skills:
                return "当前没有加载任何 Skill。"

            lines = [f"📦 已加载 Skill ({len(skills)}):"]
            for s in skills:
                tags = f" [{', '.join(s.tags[:3])}]" if s.tags else ""
                lines.append(f"  • {s.name} v{s.version}{tags}")
                if s.description:
                    lines.append(f"    描述: {s.description[:80]}")
                if s.tools:
                    lines.append(f"    工具: {len(s.tools)} 个")
            return "\n".join(lines)

        self.register_cmd(
            "skills", skills_handler,
            description="列出所有加载的 Skill",
            usage="/skills",
            category="system",
        )

        # /mcp — MCP 状态
        def mcp_handler(args: str, ctx: CommandContext) -> str:
            mcp_mgr = ctx.get("mcp_manager")
            if not mcp_mgr:
                return "MCP 管理器未配置"

            servers = mcp_mgr.list_servers()
            if not servers:
                return "没有连接的 MCP 服务器。"

            lines = ["🔌 MCP 服务器:"]
            for server_name in servers:
                server = mcp_mgr.get_server(server_name)
                status = "✅" if server and server.is_connected else "❌"
                lines.append(f"  {status} {server_name}")
            lines.append("")
            lines.append("提示: 使用 tool 工具调用 MCP 工具 (mcp:<server>:<tool>)")
            return "\n".join(lines)

        self.register_cmd(
            "mcp", mcp_handler,
            description="查看 MCP 服务器状态",
            usage="/mcp",
            category="system",
        )

        # /clear — 清屏/重置
        def clear_handler(args: str, ctx: CommandContext) -> str:
            engine = ctx.get("engine")
            if engine:
                engine.reset(args or "")
            return "🔄 已重置对话。\n" + (f"新问题: {args}" if args else "")

        self.register_cmd(
            "clear", clear_handler,
            description="重置 Agent 状态",
            usage="/clear [新问题]",
            category="system",
        )

        # /config — 查看配置
        def config_handler(args: str, ctx: CommandContext) -> str:
            config = ctx.get("config", {})
            if not config:
                return "当前配置为空"

            import json
            return f"📋 当前配置:\n{json.dumps(config, indent=2, ensure_ascii=False)}"

        self.register_cmd(
            "config", config_handler,
            description="查看当前配置",
            usage="/config",
            category="system",
        )

        # /version — 显示版本
        def version_handler(args: str, ctx: CommandContext) -> str:
            from . import __version__
            return f"xyz-agent v{__version__}"

        self.register_cmd(
            "version", version_handler,
            description="显示版本",
            usage="/version",
            category="system",
        )

    # ---- 辅助 ----

    def _find_similar(self, name: str) -> List[str]:
        """查找相似命令名"""
        import difflib
        all_names = list(self._commands.keys())
        matches = difflib.get_close_matches(name, all_names, n=3, cutoff=0.4)
        return matches


# ============================================================
# 快捷方式
# ============================================================

_default_command_system: Optional[CommandSystem] = None


def get_default_command_system() -> CommandSystem:
    """获取默认命令系统"""
    global _default_command_system
    if _default_command_system is None:
        _default_command_system = CommandSystem()
    return _default_command_system


def execute_command(text: str) -> Optional[str]:
    """快捷执行命令"""
    cmd = get_default_command_system()
    return cmd.execute_from_text(text)


def is_command(text: str) -> bool:
    """检查是否为命令"""
    return get_default_command_system().is_command(text)
