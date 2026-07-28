#!/usr/bin/env python3
"""xyz_agent.cli — 精简 CLI (~390 行)，slash 命令委托 command.py CommandSystem"""

import sys, os, shlex, logging
from typing import Dict, List, Optional

if __name__ == "__main__" and __package__ is None:
    d = os.path.dirname
    project_dir = d(d(os.path.abspath(__file__)))
    if project_dir not in sys.path: sys.path.insert(0, project_dir)
    os.chdir(project_dir)
    import importlib.util
    spec = importlib.util.spec_from_file_location("xyz_agent.cli", __file__, submodule_search_locations=[])
    if spec:
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = "xyz_agent"
        sys.modules["xyz_agent.cli"] = mod
    __package__ = "xyz_agent"

from . import __version__
from .agent import Agent, AgentConfig
from .providers import OpenAIProvider, MockProvider
from .cli_selector import interactive_select, Style

logger = logging.getLogger(__name__)
S = Style


def _color(t, c): return f"{c}{t}{S.RESET}" if os.name != "nt" else t

def _print_banner():
    print(f"""
{S.CYAN}╭{'─'*56}╮
│{' '*18}xyz-agent v{__version__}{' '*20}│
│{' '*12}{S.DIM}生产级 AI Agent 框架{S.RESET}{S.CYAN}{' '*14}│
│{' '*12}{S.DIM}Skill · MCP · Tool · FC · Selector{S.RESET}{S.CYAN}{' '*12}│
╰{'─'*56}╯{S.RESET}""")


_agent: Optional[Agent] = None

def _get_agent() -> Agent:
    global _agent
    if _agent is None:
        ak = os.environ.get("OPENAI_API_KEY", "")
        if ak:
            _agent = Agent.from_openai(api_key=ak)
            _agent.config.enable_skills = True
            _agent.config.enable_commands = True
            _agent.config.auto_load_skills = True
        else:
            _agent = Agent(llm_provider=MockProvider(),
                           config=AgentConfig(name="cli-agent", enable_skills=True, enable_commands=True, auto_load_skills=True))
        _agent.initialize()
        hs = os.path.expanduser("~/.hermes/skills/")
        if _agent.skill_manager and os.path.isdir(hs):
            c = _agent.skill_manager.load_directory(hs)
            if c > 0: _agent.rebuild_engine(); logger.info(f"已加载 {c} 个 Hermes Agent Skill")
        logger.info(f"Agent 已初始化 ({_agent.config.model})")
    return _agent


def cmd_shell():
    agent = _get_agent()
    _print_banner()
    info = agent.get_info()
    print(f"  {S.GREEN}模型:{S.RESET} {info['model']}  {S.GREEN}工具:{S.RESET} {info['tools']}  {S.GREEN}Skill:{S.RESET} {info['skills']}")
    print(f"  输入 {S.YELLOW}/help{S.RESET} 查看命令，{S.YELLOW}/exit{S.RESET} 退出\n")
    while True:
        try:
            inp = input(f"{S.BOLD}│ {S.CYAN}󰚩{S.RESET} ").strip()
        except (EOFError, KeyboardInterrupt): print(); break
        if not inp: continue
        if inp in ("/exit", "/quit", ":q", "exit", "quit"): print(f"{S.YELLOW}再见！👋{S.RESET}"); break
        if inp.startswith("/"): _handle_slash(inp, agent); continue
        try:
            r = agent.chat(inp); print(f"{S.GREEN}│{S.RESET} {r}")
        except Exception as e: print(f"{S.RED}✗ 错误: {e}{S.RESET}")


def _handle_slash(raw: str, agent: Agent):
    parts = shlex.split(raw[1:])
    if not parts: return
    cmd, args = parts[0].lower(), parts[1:]

    if cmd in ("help", "?"):
        if agent.command_system: print(agent.command_system.execute(raw))
        return
    if cmd == "clear": os.system("clear" if os.name == "posix" else "cls"); _print_banner(); return
    if cmd == "reset": agent.reset(); print(f"{S.GREEN}✓ Agent 已重置{S.RESET}"); return
    if cmd == "model": _model_select(agent); return
    if cmd == "skill" and not args: _skill_select(agent); return
    if cmd == "skill" and args and args[0] == "generate":
        p = os.path.expanduser(args[1] if len(args) >= 2 else "./skills/my-skill/SKILL.md")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        _gen_skill(p); print(f"{S.GREEN}✓ 示例 Skill 已生成: {p}{S.RESET}"); return
    if cmd == "mcp" and not args: _mcp_select(agent); return
    if cmd in ("commands", "cmds"): _commands_list(agent); return
    if cmd == "stats":
        print(f"{S.CYAN}运行统计:{S.RESET}")
        for k, v in agent.get_stats().items(): print(f"  {k}: {v}")
        return
    if cmd == "trace" and agent.engine:
        print(f"{S.CYAN}步骤追踪:{S.RESET}")
        for t in agent.engine.get_trace(detail="full"):
            print(f"  Step {t['step']} [{t['type']}]: {t.get('content', '')[:80]}")
            if t.get("tool_result"): print(f"    结果: {str(t['tool_result'])[:80]}")
        return
    if agent.command_system:
        r = agent.command_system.execute(raw)
        if r: print(r)
    else:
        print(f"{S.YELLOW}未知命令: /{cmd}  输入 /help 查看可用命令{S.RESET}")


_MODELS = [
    ("gpt-4o","OpenAI 旗舰","openai"), ("gpt-4o-mini","OpenAI 轻量版","openai"), ("gpt-4-turbo","OpenAI GPT-4 Turbo","openai"), ("gpt-3.5-turbo","OpenAI 低成本","openai"),
    ("claude-sonnet-4","Claude Sonnet 4","anthropic"), ("claude-3.5-sonnet","Claude 3.5 Sonnet","anthropic"), ("claude-3-haiku","Claude 3 Haiku","anthropic"),
    ("deepseek/deepseek-chat","DeepSeek V3/Chat","deepseek"), ("deepseek/deepseek-reasoner","DeepSeek R1 推理","deepseek"),
    ("gemini/gemini-2.0-flash","Gemini 2.0 Flash","gemini"), ("gemini/gemini-2.0-pro","Gemini 2.0 Pro","gemini"),
    ("qwen/qwen-2.5-72b","通义千问 Qwen 2.5 72B","qwen"),
    ("openai/gpt-4o","OpenRouter: GPT-4o","openrouter"), ("anthropic/claude-sonnet-4","OpenRouter: Sonnet 4","openrouter"), ("meta-llama/llama-3.3-70b","OpenRouter: Llama 3.3 70B","openrouter"),
]

_PROV_CFG = {"openai":{"k":"OPENAI_API_KEY","u":None},"deepseek":{"k":"DEEPSEEK_API_KEY","u":"https://api.deepseek.com/v1"},"openrouter":{"k":"OPENROUTER_API_KEY","u":"https://openrouter.ai/api/v1"},"anthropic":{"k":"ANTHROPIC_API_KEY","u":"https://api.anthropic.com/v1"},"gemini":{"k":"GOOGLE_API_KEY","u":"https://generativelanguage.googleapis.com/v1beta/openai/"},"qwen":{"k":"QWEN_API_KEY","u":"https://dashscope.aliyuncs.com/compatible-mode/v1"}}

_MCP_TPL = [
    ("filesystem","文件系统操作","npx",["-y","@modelcontextprotocol/server-filesystem","/tmp"]), ("github","GitHub API","npx",["-y","@modelcontextprotocol/server-github"]),
    ("playwright","浏览器自动化","npx",["-y","@playwright/mcp"]), ("sqlite","SQLite 查询","uvx",["mcp-server-sqlite","--db-path","/tmp/test.db"]),
    ("fetch","网页抓取","uvx",["mcp-server-fetch"]), ("sequential-thinking","分步推理","npx",["-y","@modelcontextprotocol/server-sequential-thinking"]),
]


def _model_select(agent):
    cur = agent.config.model
    items = [{"name": n, "description": d + ("  ← 当前" if n == cur else ""), "tags": [p], "_m": n, "_p": p} for n, d, p in _MODELS]
    items.append({"name":"✏️  自定义模型","description":"手动输入模型名称","tags":["custom"],"_m":None,"_p":None})
    sel = interactive_select(items, title=f"🤖 选择模型（当前: {cur}）", prompt="↑↓ 选择  |  回车确认  |  / 过滤  |  ESC 取消")
    if sel is None: return
    mn, pn = sel["_m"], sel["_p"]
    if mn is None:
        from .cli_selector import input_text
        mn = input_text("输入模型名称", default=cur)
        if not mn: print(f"{S.YELLOW}已取消{S.RESET}"); return
        pn = "openai"
    cfg = _PROV_CFG.get(pn, {"k":"OPENAI_API_KEY","u":None})
    agent.provider = OpenAIProvider(api_key=os.environ.get(cfg["k"],""), model=mn, base_url=cfg["u"])
    agent.config.model = mn; agent.rebuild_engine()
    print(f"{S.GREEN}✓{S.RESET} 模型已切换为 {S.BOLD}{mn}{S.RESET} ({pn})")


def _skill_select(agent):
    if not agent.skill_manager: print(f"{S.YELLOW}✗ Skill 系统未启用{S.RESET}"); return
    sk = agent.skill_manager.list_skills()
    if not sk: print(f"{S.YELLOW}暂无可选的 Skill{S.RESET}"); return
    items = [{"name":x.name,"description":f"{x.description[:50] or '暂无描述'} v{x.version}","tags":[x.tags[0] if x.tags else "未分类"],"_raw":x}
             for x in sorted(sk, key=lambda s: (s.tags[0] if s.tags else "~", s.name))]
    sel = interactive_select(items, title=f"📦 已加载 Skill ({len(items)} 个)", prompt="↑↓ 选择  |  回车加载  |  / 过滤  |  ESC 取消")
    if sel is None: return
    agent.rebuild_engine()
    s = sel["_raw"]
    parts = [f"{S.GREEN}✓{S.RESET} 已加载 {S.BOLD}{s.name}{S.RESET} v{s.version}"]
    if s.description: parts.append(f"   {S.DIM}{s.description}{S.RESET}")
    if s.tools: parts.append(f"   {S.CYAN}🔧 {len(s.tools)} 个工具{S.RESET}")
    parts.append(f"   {S.DIM}路径: {s.source_path or 'N/A'}{S.RESET}")
    print("\n".join(parts))


def _mcp_select(agent):
    from .cli_selector import confirm, input_text
    acts = [{"name":"📋  查看已连接的服务器","description":"列出 MCP 服务器","_a":"list"},{"name":"🔌  连接（预设模板）","description":"从常用 MCP 模板中选择","_a":"tpl"},{"name":"🔌  连接（自定义）","description":"手动输入命令","_a":"cust"},{"name":"📡  发现 MCP 工具","description":"同步工具","_a":"disc"}]
    a = interactive_select(acts, title="🔌 MCP 管理", prompt="↑↓ 选择  |  回车确认  |  ESC 取消")
    if a is None: return
    act = a["_a"]

    if act == "list":
        sv = agent.mcp_manager.list_servers() if agent.mcp_manager else []
        if not sv: print(f"{S.YELLOW}没有连接的 MCP 服务器{S.RESET}"); return
        print(f"{S.CYAN}MCP 服务器 ({len(sv)}):{S.RESET}")
        for n in sv:
            s = agent.mcp_manager.get_server(n)
            st = f"{S.GREEN}✅{S.RESET}" if s and s.is_connected else f"{S.RED}❌{S.RESET}"
            print(f"  {st} {S.BOLD}{n}{S.RESET} ({len(s.tools) if s else 0} 个工具)")
        return

    if act == "tpl":
        items = [{"name":n,"description":d+("  (已连接)" if agent.mcp_manager and n in agent.mcp_manager.list_servers() else ""),"tags":["mcp"],"_t":(n,c,a)} for n,d,c,a in _MCP_TPL]
        sel = interactive_select(items, title="🔌 选择 MCP 模板", prompt="↑↓ 选择  |  回车连接  |  / 过滤  |  ESC 取消")
        if sel is None: return
        n, c, a = sel["_t"]
        try:
            agent.setup_mcp(n, c, a); print(f"{S.GREEN}✓{S.RESET} MCP {S.BOLD}{n}{S.RESET} 已连接")
            if confirm("  同步发现工具?"): agent.discover_mcp_tools(); print(f"  {S.GREEN}✓{S.RESET} 工具已同步")
        except Exception as e: print(f"{S.RED}✗ 连接失败: {e}{S.RESET}")
        return

    if act == "cust":
        n = input_text("服务器名称"); c = input_text("命令", default="npx")
        a = input_text("参数", default="-y @modelcontextprotocol/server-filesystem /tmp").split()
        try:
            agent.setup_mcp(n, c, a); print(f"{S.GREEN}✓{S.RESET} MCP {S.BOLD}{n}{S.RESET} 已连接")
            if confirm("  同步发现工具?"): agent.discover_mcp_tools(); print(f"  {S.GREEN}✓{S.RESET} 工具已同步")
        except Exception as e: print(f"{S.RED}✗ 连接失败: {e}{S.RESET}")
        return

    if act == "disc":
        agent.discover_mcp_tools()
        print(f"{S.GREEN}✓{S.RESET} MCP 工具已同步，当前共 {len(agent.list_tools())} 个工具")


def _commands_list(agent):
    cs = agent.command_system
    if not cs: print(f"{S.YELLOW}命令系统未启用{S.RESET}"); return
    all_c = [{"name":d.name,"description":d.description,"tags":[c],"_d":d} for c,ds in sorted(cs.get_all_commands().items()) for d in sorted(ds, key=lambda x:x.name)]
    if not all_c: print(f"{S.YELLOW}当前没有注册的命令{S.RESET}"); return
    sel = interactive_select(all_c, title=f"📋 已注册命令（共 {len(all_c)} 个）", prompt="↑↓ 选择  |  回车查看  |  / 过滤  |  ESC 取消")
    if sel is None: return
    d = sel["_d"]
    print(f"  {S.BOLD}/{d.name}{S.RESET}\n    分类: {S.CYAN}{sel['tags'][0]}{S.RESET}\n    描述: {d.description}\n    用法: {d.usage or f'/{d.name} [args]'}")


def cmd_run(q: str): print(_get_agent().run(q))
def cmd_chat(): cmd_shell()


def _gen_skill(path: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write("""---
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
""")


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
  xyz --version              显示版本
"""


def main():
    if len(sys.argv) < 2: print(USAGE); return
    c, a = sys.argv[1], sys.argv[2:]

    if c in ("--version", "-v", "version"): print(f"xyz-agent v{__version__}"); return
    if c in ("--help", "-h", "help"): print(USAGE); return
    if c in ("chat", "shell", "interactive"): cmd_shell(); return

    if c == "run":
        if not a: print("请提供问题。用法: xyz run <问题>"); return
        cmd_run(" ".join(a)); return

    if c == "init":
        from .loader import generate_sample_config
        p = generate_sample_config(a[0] if a else "~/.xyz-agent/extensions.yaml")
        print(f"✓ 示例配置已生成: {p}"); return

    agent = _get_agent()
    if c in ("tool", "skill", "mcp", "config") and agent.command_system:
        r = agent.command_system.execute(f"/{c} {' '.join(a)}" if a else f"/{c}")
        print(r); return

    print(f"未知命令: {c}"); print(USAGE); sys.exit(1)


if __name__ == "__main__":
    main()
