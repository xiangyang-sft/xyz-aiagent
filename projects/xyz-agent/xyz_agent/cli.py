#!/usr/bin/env python3
"""
xyz_agent.cli — 命令行接口

将 slash 命令委托给 command.py 的 CommandSystem 处理。
保留 CLI 独有功能：/model /skill /mcp 交互式选择器、/trace /stats 调试。
模型配置支持从 models.yaml 配置文件加载。
"""

import sys
import os
import shlex
import yaml
import logging
from typing import Dict, List, Optional

# ── 包路径兼容 ──
if __name__ == "__main__" and __package__ is None:
    d = os.path.dirname
    project_dir = d(d(os.path.abspath(__file__)))
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)
    os.chdir(project_dir)

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "xyz_agent.cli", __file__, submodule_search_locations=[]
    )
    if spec:
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = "xyz_agent"
        sys.modules["xyz_agent.cli"] = mod
    __package__ = "xyz_agent"

from . import __version__
from .agent import Agent, AgentConfig
from .providers import OpenAIProvider, MockProvider
from .cli_selector import interactive_select, Style, input_text, confirm

logger = logging.getLogger(__name__)

# ============================================================
# 彩色输出
# ============================================================

S = Style


def _color(text: str, color: str) -> str:
    if os.name == "nt":
        return text
    return f"{color}{text}{S.RESET}"


def _print_banner():
    """打印启动 Banner"""
    banner = f"""
{S.CYAN}╭{'─' * 56}╮
│{' ' * 18}xyz-agent v{__version__}{' ' * 20}│
│{' ' * 12}{S.DIM}生产级 AI Agent 框架{S.RESET}{S.CYAN}{' ' * 14}│
│{' ' * 12}{S.DIM}Skill · MCP · Tool · FC · Selector{S.RESET}{S.CYAN}{' ' * 12}│
╰{'─' * 56}╯{S.RESET}"""
    print(banner)


# ============================================================
# 模型配置加载
# ============================================================

_MODEL_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "models.yaml")

# 硬编码模型列表（兼容旧版本，无 models.yaml 时使用）
_FALLBACK_MODELS = [
    # OpenAI
    ("gpt-4o",             "OpenAI 旗舰模型",           "openai"),
    ("gpt-4o-mini",        "OpenAI 轻量版",             "openai"),
    ("gpt-4-turbo",        "OpenAI GPT-4 Turbo",        "openai"),
    ("gpt-3.5-turbo",      "OpenAI 低成本",             "openai"),
    # DeepSeek
    ("deepseek-v4-flash",  "DeepSeek V4 Flash（已验证）","deepseek"),
    ("deepseek/deepseek-chat",     "DeepSeek V3/Chat",  "deepseek"),
    ("deepseek/deepseek-reasoner", "DeepSeek R1 推理",  "deepseek"),
    # OpenRouter
    ("openai/gpt-4o",              "OpenRouter: GPT-4o",  "openrouter"),
    ("anthropic/claude-sonnet-4",  "OpenRouter: Sonnet 4","openrouter"),
    ("meta-llama/llama-3.3-70b",   "OpenRouter: Llama 3.3 70B", "openrouter"),
]

_FALLBACK_PROV_CFG = {
    "openai":    {"k": "OPENAI_API_KEY",     "u": None},
    "deepseek":  {"k": "DEEPSEEK_API_KEY",   "u": "https://api.deepseek.com/v1"},
    "openrouter":{"k": "OPENROUTER_API_KEY", "u": "https://openrouter.ai/api/v1"},
    "anthropic": {"k": "ANTHROPIC_API_KEY",  "u": "https://api.anthropic.com/v1"},
    "gemini":    {"k": "GOOGLE_API_KEY",     "u": "https://generativelanguage.googleapis.com/v1beta/openai/"},
    "qwen":      {"k": "QWEN_API_KEY",       "u": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
}


class ModelEntry:
    """单个模型配置条目"""
    def __init__(self, name: str, description: str = "",
                 provider: str = "openai", base_url: Optional[str] = None,
                 api_key_env: str = "OPENAI_API_KEY"):
        self.name = name
        self.description = description
        self.provider = provider
        self.base_url = base_url
        self.api_key_env = api_key_env

    def to_select_item(self, is_current: bool = False) -> Dict:
        label = self.description + ("  ← 当前" if is_current else "")
        return {
            "name": self.name,
            "description": label,
            "tags": [self.provider],
            "_entry": self,
        }


def _load_models_from_yaml() -> tuple:
    """
    从 models.yaml 加载模型配置

    返回:
      (model_entries, default_model_name)
    """
    if not os.path.isfile(_MODEL_CONFIG_PATH):
        return [], "gpt-4o"

    try:
        with open(_MODEL_CONFIG_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        logger.warning(f"模型配置文件 {_MODEL_CONFIG_PATH} 解析失败")
        return [], "gpt-4o"

    if not data or "models" not in data:
        return [], "gpt-4o"

    entries = []
    for m in data["models"]:
        name = m.get("name", "")
        if not name:
            continue
        entries.append(ModelEntry(
            name=name,
            description=m.get("description", ""),
            provider=m.get("provider", "openai"),
            base_url=m.get("base_url"),
            api_key_env=m.get("api_key_env", "OPENAI_API_KEY"),
        ))

    default_name = data.get("default_model", "gpt-4o")
    return entries, default_name


def _get_model_entries_and_default() -> tuple:
    """
    获取完整模型列表和默认模型名

    策略：优先加载 models.yaml，如无则使用硬编码 fallback
    """
    yaml_entries, default_name = _load_models_from_yaml()
    if yaml_entries:
        return yaml_entries, default_name

    # Fallback：从硬编码列表构建
    entries = []
    for name, desc, provider in _FALLBACK_MODELS:
        cfg = _FALLBACK_PROV_CFG.get(provider, {})
        entries.append(ModelEntry(
            name=name,
            description=desc,
            provider=provider,
            base_url=cfg.get("u"),
            api_key_env=cfg.get("k", "OPENAI_API_KEY"),
        ))
    return entries, "gpt-4o"


# ============================================================
# 全局 Agent 实例
# ============================================================

_agent: Optional[Agent] = None


def _get_agent() -> Agent:
    """获取或创建全局 Agent 实例（支持环境变量和配置文件）"""
    global _agent
    if _agent is not None:
        return _agent

    # 从配置文件读取默认模型名
    _, default_name = _get_model_entries_and_default()

    # 环境变量优先于配置文件
    model = os.environ.get("OPENAI_MODEL", default_name)
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", None)

    if api_key:
        _agent = Agent.from_openai(
            api_key=api_key,
            model=model,
            base_url=base_url,
        )
        _agent.config.enable_skills = True
        _agent.config.enable_commands = True
        _agent.config.auto_load_skills = True
    else:
        _agent = Agent(
            llm_provider=MockProvider(),
            config=AgentConfig(
                name="cli-agent",
                model=model,
                enable_skills=True,
                enable_commands=True,
                auto_load_skills=True,
            ),
        )

    _agent.initialize()

    # 加载 Hermes Agent 的 Skills
    hermes_skills = os.path.expanduser("~/.hermes/skills/")
    if _agent.skill_manager and os.path.isdir(hermes_skills):
        count = _agent.skill_manager.load_directory(hermes_skills)
        if count > 0:
            _agent.rebuild_engine()
            logger.info(f"已加载 {count} 个 Hermes Agent Skill")

    logger.info(f"Agent 已初始化 ({_agent.config.model})")
    return _agent


# ============================================================
# 交互式 Shell
# ============================================================

def cmd_shell():
    """交互式 Agent Shell"""
    agent = _get_agent()
    _print_banner()

    info = agent.get_info()
    print(
        f"  {S.GREEN}模型:{S.RESET} {info['model']}  "
        f"{S.GREEN}工具:{S.RESET} {info['tools']}  "
        f"{S.GREEN}Skill:{S.RESET} {info['skills']}"
    )
    print(f"  输入 {S.YELLOW}/help{S.RESET} 查看命令，{S.YELLOW}/exit{S.RESET} 退出\n")

    while True:
        try:
            user_input = input(f"{S.BOLD}│ {S.CYAN}󰚩{S.RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        if user_input in ("/exit", "/quit", ":q", "exit", "quit"):
            print(f"{S.YELLOW}再见！👋{S.RESET}")
            break

        if user_input.startswith("/"):
            _handle_slash(user_input, agent)
            continue

        try:
            print(f"{S.GREEN}│{S.RESET} ", end="", flush=True)
            for chunk in agent.chat_stream(user_input):
                print(chunk, end="", flush=True)
            print()
        except Exception as e:
            print(f"\n{S.RED}✗ 错误: {e}{S.RESET}")


# ============================================================
# Slash 命令处理
# ============================================================

def _handle_slash(raw: str, agent: Agent):
    """处理 slash 命令"""
    parts = shlex.split(raw[1:])
    if not parts:
        return

    cmd = parts[0].lower()
    args = parts[1:]

    # 系统命令
    if cmd in ("help", "?"):
        if agent.command_system:
            print(agent.command_system.execute(raw))
        return

    if cmd == "clear":
        os.system("clear" if os.name == "posix" else "cls")
        _print_banner()
        return

    if cmd == "reset":
        agent.reset()
        print(f"{S.GREEN}✓ Agent 已重置{S.RESET}")
        return

    # 交互式选择命令
    if cmd == "model":
        _model_select(agent)
        return

    if cmd == "skill" and not args:
        _skill_select(agent)
        return

    if cmd == "skill" and args and args[0] == "generate":
        path = os.path.expanduser(
            args[1] if len(args) >= 2 else "./skills/my-skill/SKILL.md"
        )
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _gen_skill(path)
        print(f"{S.GREEN}✓ 示例 Skill 已生成: {path}{S.RESET}")
        return

    if cmd == "mcp" and not args:
        _mcp_select(agent)
        return

    if cmd in ("commands", "cmds"):
        _commands_list(agent)
        return

    # 调试命令
    if cmd == "stats":
        print(f"{S.CYAN}运行统计:{S.RESET}")
        for k, v in agent.get_stats().items():
            print(f"  {k}: {v}")
        return

    if cmd == "trace" and agent.engine:
        print(f"{S.CYAN}步骤追踪:{S.RESET}")
        for t in agent.engine.get_trace(detail="full"):
            print(f"  Step {t['step']} [{t['type']}]: {t.get('content', '')[:80]}")
            if t.get("tool_result"):
                print(f"    结果: {str(t['tool_result'])[:80]}")
        return

    # 委托给 CommandSystem
    if agent.command_system:
        result = agent.command_system.execute(raw)
        if result:
            print(result)
    else:
        print(
            f"{S.YELLOW}未知命令: /{cmd}  "
            f"输入 /help 查看可用命令{S.RESET}"
        )


# ============================================================
# 模型选择（从 models.yaml 加载）
# ============================================================

def _model_select(agent: Agent):
    """交互式选择模型（从 models.yaml + fallback 加载列表）"""
    cur = agent.config.model
    entries, _ = _get_model_entries_and_default()

    items = [e.to_select_item(is_current=(e.name == cur)) for e in entries]

    # 添加"自定义模型"选项
    items.append({
        "name": "✏️  自定义模型",
        "description": "手动输入模型名称和 API 地址",
        "tags": ["custom"],
        "_entry": None,
    })

    sel = interactive_select(
        items,
        title=f"🤖 选择模型（当前: {cur}）",
        prompt="↑↓ 选择  |  回车确认  |  / 过滤  |  ESC 取消",
    )
    if sel is None:
        return

    entry = sel["_entry"]

    if entry is None:
        # 自定义模型
        model_name = input_text("输入模型名称", default=cur)
        if not model_name:
            print(f"{S.YELLOW}已取消{S.RESET}")
            return
        base_url = input_text(
            "API 地址",
            default="https://api.openai.com/v1",
        )
        api_key_env = input_text(
            "API Key 环境变量名",
            default="OPENAI_API_KEY",
        )
        api_key = os.environ.get(api_key_env, "")
        if not api_key:
            print(f"{S.YELLOW}⚠ 环境变量 {api_key_env} 未设置{S.RESET}")
        agent.provider = OpenAIProvider(
            api_key=api_key, model=model_name, base_url=base_url or None,
        )
        agent.config.model = model_name
        agent.rebuild_engine()
        print(f"{S.GREEN}✓{S.RESET} 模型已切换为 {S.BOLD}{model_name}{S.RESET}")
        return

    # 从配置文件加载的模型
    api_key = os.environ.get(entry.api_key_env, "")
    if not api_key and entry.api_key_env != "OPENAI_API_KEY":
        # 如果特定 Key 没设置，尝试用 OPENAI_API_KEY
        api_key = os.environ.get("OPENAI_API_KEY", "")

    if not api_key:
        print(f"{S.YELLOW}⚠ 未找到 {entry.api_key_env} 环境变量，可能无法正常使用{S.RESET}")

    agent.provider = OpenAIProvider(
        api_key=api_key or os.environ.get("OPENAI_API_KEY", ""),
        model=entry.name,
        base_url=entry.base_url,
    )
    agent.config.model = entry.name
    agent.rebuild_engine()
    print(
        f"{S.GREEN}✓{S.RESET} 模型已切换为 {S.BOLD}{entry.name}{S.RESET} "
        f"({entry.provider})"
    )
    if entry.base_url:
        print(f"  {S.DIM}API: {entry.base_url}{S.RESET}")


# ============================================================
# Skill 选择
# ============================================================

def _skill_select(agent: Agent):
    """交互式选择 Skill"""
    if not agent.skill_manager:
        print(f"{S.YELLOW}✗ Skill 系统未启用{S.RESET}")
        return

    skills = agent.skill_manager.list_skills()
    if not skills:
        print(f"{S.YELLOW}暂无可选的 Skill{S.RESET}")
        return

    items = []
    for s in sorted(skills, key=lambda x: (x.tags[0] if x.tags else "~", x.name)):
        desc = f"{s.description[:50] or '暂无描述'} v{s.version}"
        tag = s.tags[0] if s.tags else "未分类"
        items.append({
            "name": s.name,
            "description": desc,
            "tags": [tag],
            "_raw": s,
        })

    sel = interactive_select(
        items,
        title=f"📦 已加载 Skill ({len(items)} 个)",
        prompt="↑↓ 选择  |  回车加载  |  / 过滤  |  ESC 取消",
    )
    if sel is None:
        return

    agent.rebuild_engine()
    skill = sel["_raw"]
    parts = [f"{S.GREEN}✓{S.RESET} 已加载 {S.BOLD}{skill.name}{S.RESET} v{skill.version}"]
    if skill.description:
        parts.append(f"   {S.DIM}{skill.description}{S.RESET}")
    if skill.tools:
        parts.append(f"   {S.CYAN}🔧 {len(skill.tools)} 个工具{S.RESET}")
    if skill.source_path:
        parts.append(f"   {S.DIM}路径: {skill.source_path}{S.RESET}")
    print("\n".join(parts))


# ============================================================
# MCP 管理
# ============================================================

_MCP_TPL = [
    ("filesystem",           "文件系统操作",  "npx",
     ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]),
    ("github",               "GitHub API",    "npx",
     ["-y", "@modelcontextprotocol/server-github"]),
    ("playwright",           "浏览器自动化",  "npx",
     ["-y", "@playwright/mcp"]),
    ("sqlite",               "SQLite 查询",   "uvx",
     ["mcp-server-sqlite", "--db-path", "/tmp/test.db"]),
    ("fetch",                "网页抓取",      "uvx",
     ["mcp-server-fetch"]),
    ("sequential-thinking",  "分步推理",      "npx",
     ["-y", "@modelcontextprotocol/server-sequential-thinking"]),
]


def _mcp_select(agent: Agent):
    """交互式 MCP 管理"""
    acts = [
        {"name": "📋  查看已连接的服务器", "description": "列出 MCP 服务器",
         "_a": "list"},
        {"name": "🔌  连接（预设模板）",   "description": "从常用 MCP 模板中选择",
         "_a": "tpl"},
        {"name": "🔌  连接（自定义）",     "description": "手动输入命令",
         "_a": "cust"},
        {"name": "📡  发现 MCP 工具",      "description": "同步工具",
         "_a": "disc"},
    ]

    action = interactive_select(
        acts,
        title="🔌 MCP 管理",
        prompt="↑↓ 选择  |  回车确认  |  ESC 取消",
    )
    if action is None:
        return

    act = action["_a"]

    if act == "list":
        _mcp_list(agent)
        return

    if act == "tpl":
        _mcp_connect_template(agent)
        return

    if act == "cust":
        _mcp_connect_custom(agent)
        return

    if act == "disc":
        agent.discover_mcp_tools()
        print(f"{S.GREEN}✓{S.RESET} MCP 工具已同步，当前共 {len(agent.list_tools())} 个工具")


def _mcp_list(agent: Agent):
    """列出 MCP 服务器"""
    servers = agent.mcp_manager.list_servers() if agent.mcp_manager else []
    if not servers:
        print(f"{S.YELLOW}没有连接的 MCP 服务器{S.RESET}")
        return

    print(f"{S.CYAN}MCP 服务器 ({len(servers)}):{S.RESET}")
    for name in servers:
        server = agent.mcp_manager.get_server(name)
        status = f"{S.GREEN}✅{S.RESET}" if (server and server.is_connected) else f"{S.RED}❌{S.RESET}"
        tool_count = len(server.tools) if server else 0
        print(f"  {status} {S.BOLD}{name}{S.RESET} ({tool_count} 个工具)")


def _mcp_connect_template(agent: Agent):
    """从预设模板连接 MCP"""
    items = []
    for name, desc, cmd, args in _MCP_TPL:
        already = agent.mcp_manager and name in agent.mcp_manager.list_servers()
        label = desc + ("  (已连接)" if already else "")
        items.append({
            "name": name,
            "description": label,
            "tags": ["mcp"],
            "_t": (name, cmd, args),
        })

    sel = interactive_select(
        items,
        title="🔌 选择 MCP 模板",
        prompt="↑↓ 选择  |  回车连接  |  / 过滤  |  ESC 取消",
    )
    if sel is None:
        return

    name, cmd, args = sel["_t"]
    _do_mcp_connect(agent, name, cmd, args)


def _mcp_connect_custom(agent: Agent):
    """手动输入连接 MCP"""
    name = input_text("服务器名称")
    cmd = input_text("命令", default="npx")
    args_str = input_text(
        "参数",
        default="-y @modelcontextprotocol/server-filesystem /tmp",
    )
    args = args_str.split()
    _do_mcp_connect(agent, name, cmd, args)


def _do_mcp_connect(agent: Agent, name: str, cmd: str, args: List[str]):
    """执行 MCP 连接"""
    try:
        agent.setup_mcp(name, cmd, args)
        print(f"{S.GREEN}✓{S.RESET} MCP {S.BOLD}{name}{S.RESET} 已连接")

        if confirm("  同步发现工具?"):
            agent.discover_mcp_tools()
            print(f"  {S.GREEN}✓{S.RESET} 工具已同步")
    except Exception as e:
        print(f"{S.RED}✗ 连接失败: {e}{S.RESET}")


# ============================================================
# 命令列表浏览
# ============================================================

def _commands_list(agent: Agent):
    """浏览所有注册命令"""
    cs = agent.command_system
    if not cs:
        print(f"{S.YELLOW}命令系统未启用{S.RESET}")
        return

    all_cmds = []
    for category, cmds in sorted(cs.get_all_commands().items()):
        for c in sorted(cmds, key=lambda x: x.name):
            all_cmds.append({
                "name": c.name,
                "description": c.description,
                "tags": [category],
                "_d": c,
            })

    if not all_cmds:
        print(f"{S.YELLOW}当前没有注册的命令{S.RESET}")
        return

    sel = interactive_select(
        all_cmds,
        title=f"📋 已注册命令（共 {len(all_cmds)} 个）",
        prompt="↑↓ 选择  |  回车查看  |  / 过滤  |  ESC 取消",
    )
    if sel is None:
        return

    cmd_def = sel["_d"]
    print(
        f"  {S.BOLD}/{cmd_def.name}{S.RESET}"
        f"\n    分类: {S.CYAN}{sel['tags'][0]}{S.RESET}"
        f"\n    描述: {cmd_def.description}"
        f"\n    用法: {cmd_def.usage or f'/{cmd_def.name} [args]'}"
    )


# ============================================================
# 单次运行 & 工具函数
# ============================================================

def cmd_run(question: str):
    """单次运行 Agent（流式输出）"""
    agent = _get_agent()
    for chunk in agent.run_stream(question):
        print(chunk, end="", flush=True)
    print()


def cmd_chat():
    cmd_shell()


def _gen_skill(path: str):
    """生成示例 SKILL.md 文件"""
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
# 命令行入口
# ============================================================

USAGE = f"""\
{S.CYAN}xyz-agent v{__version__}{S.RESET} — 生产级 AI Agent 框架

{S.BOLD}用法:{S.RESET}
  xyz run <问题>             单次运行
  xyz chat                   交互式 Shell (推荐)
  xyz tool list              列出工具
  xyz skill list             列出 Skill
  xyz mcp list               查看 MCP 状态
  xyz config                 查看配置
  xyz --help                 显示帮助
  xyz --version              显示版本"""


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd in ("--version", "-v", "version"):
        print(f"xyz-agent v{__version__}")
        return

    if cmd in ("--help", "-h", "help"):
        print(USAGE)
        return

    if cmd in ("chat", "shell", "interactive"):
        cmd_shell()
        return

    if cmd == "run":
        if not args:
            print("请提供问题。用法: xyz run <问题>")
            return
        cmd_run(" ".join(args))
        return

    if cmd == "init":
        from .loader import generate_sample_config
        path = args[0] if args else "~/.xyz-agent/extensions.yaml"
        out = generate_sample_config(path)
        print(f"✓ 示例配置已生成: {out}")
        return

    # 委托给 CommandSystem
    agent = _get_agent()
    if cmd in ("tool", "skill", "mcp", "config") and agent.command_system:
        full_cmd = f"/{cmd} {' '.join(args)}" if args else f"/{cmd}"
        result = agent.command_system.execute(full_cmd)
        print(result)
        return

    print(f"未知命令: {cmd}")
    print(USAGE)
    sys.exit(1)


if __name__ == "__main__":
    main()
