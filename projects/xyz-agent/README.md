# xyz-agent — 生产级 AI Agent 框架

> 从学习到生产就绪，一站式 Agent 框架。
> 支持 Skill、MCP、Commands、Function Calling、OpenAI 原生集成。

## 架构全景

```
User ──▶ Agent (统一入口)
              │
              ├── CommandSystem ─── /help /tools /skills
              │    (slash 命令解析)
              │
              ├── ReActEngine v2 ─── 推理循环
              │    ├── ReAct 模式 (文本解析)
              │    └── Function Calling 模式 (原生格式)
              │
              ├── ToolRegistry ─── 工具管理
              │    ├── @tool 装饰器
              │    ├── 手动注册 + MCP 格式
              │    └── 自动 OpenAI Schema 生成
              │
              ├── SkillManager ─── Skill 系统
              │    ├── SKILL.md 目录加载 (Hermes Agent 兼容)
              │    ├── YAML frontmatter + markdown body
              │    └── System Prompt 自动融合
              │
              ├── MCPManager ─── MCP 客户端
              │    ├── stdio 传输 (本地子进程)
              │    ├── HTTP 传输 (远程服务器)
              │    └── 自动工具发现 + 注册到 ToolRegistry
              │
              ├── ExtensionLoader ─── 扩展自动发现
              │    ├── YAML/JSON 配置加载
              │    ├── 目录扫描 (*.skill.yaml, *.mcp.yaml 等)
              │    └── Python 插件动态加载
              │
              └── LLMProvider ─── 多种后端
                   ├── OpenAI (Function Calling)
                   ├── OpenRouter
                   └── Mock (测试)
```

## 快速开始

### 安装

```bash
cd projects/xyz-agent
pip install -e .
pip install pyyaml  # SKILL.md 解析
```

### 最小示例

```python
from xyz_agent import Agent

# 从 OpenAI 创建（自动启用 Function Calling）
agent = Agent.from_openai(api_key="sk-...")
result = agent.run("北京和上海哪个城市更大？")
print(result)
```

### 完整功能示例

```python
from xyz_agent import Agent, AgentConfig, ToolRegistry, tool

# 注册工具
@tool
def get_weather(city: str) -> str:
    """查询城市天气"""
    return f"{city}：晴，25°C"

# 创建 Agent（自动集成所有子系统）
agent = Agent(config=AgentConfig(name="my-agent"))
agent.initialize()

# 运行
result = agent.run("北京的天气怎么样？")
print(result)

# 使用命令
result = agent.chat("/help")    # 查看所有命令
result = agent.chat("/tools")   # 查看工具
result = agent.chat("/skills")  # 查看 Skill
```

### 加载 Skill

```python
from xyz_agent import SkillManager

# 从目录加载 Hermes Agent 兼容的 SKILL.md
skill_mgr = SkillManager()
skill_mgr.load_directory("~/.hermes/skills/")

# 或者从默认位置自动加载
load_skills()
print(list_skills())
```

### 连接 MCP 服务器

```python
from xyz_agent import MCPManager

# stdio 连接
mcp = MCPManager()
mcp.connect_stdio("fs", "npx", ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"])

# 发现并注册工具
counts = mcp.discover_all_tools_sync()
print(f"发现工具: {counts}")

# 调用工具
result = mcp.call_tool_sync("fs", "read", {"path": "/tmp/test.txt"})
print(result)
```

## 新模块（v1.0）

| 模块 | 文件 | 功能 |
|:----|:-----|:-----|
| Skill 系统 | `skill.py` | SKILL.md 加载、Hermes Agent 兼容、system prompt 注入 |
| MCP 客户端 | `mcp_client.py` | MCP 协议 stdio/HTTP、自动工具发现、连接池 |
| 命令系统 | `command.py` | 内建命令(/help/tools/skills) + 外部命令 + slash 解析 |
| 扩展加载器 | `loader.py` | 目录扫描、YAML/JSON 配置、Python 插件动态加载 |
| LLM Provider | `providers.py` | OpenAI、OpenRouter、Mock、Function Calling 原生支持 |
| 引擎 v2 | `engine.py` | 支持 Function Calling 原生格式、消息驱动、双模式 |
| Agent v2 | `agent.py` | 集成所有子系统、工厂方法、命令自动路由 |

## 外部生态适配

- ✅ **Hermes Agent SKILL.md** — YAML frontmatter + Markdown body 格式
- ✅ **MCP 协议** — stdio 和 HTTP 传输，自动工具发现和注册
- ✅ **OpenAI Function Calling** — 原生格式，自动 Schema 生成
- ✅ **OpenAI / OpenRouter API** — 即开即用的 LLM Provider
- ✅ **Python 插件** — `.plugin.py` 文件动态加载
- ✅ **YAML/JSON 配置** — 声明式扩展配置

## 项目结构

```
xyz-agent/
├── xyz_agent/
│   ├── __init__.py      # 导出所有模块
│   ├── agent.py         # Agent v2 — 集成所有子系统
│   ├── engine.py        # ReActEngine v2 — Function Calling 原生支持
│   ├── tool.py          # ToolRegistry — 工具注册/验证/执行
│   ├── skill.py         # SkillManager — 技能加载/管理
│   ├── mcp_client.py    # MCPManager — MCP 客户端
│   ├── command.py       # CommandSystem — 命令解析/执行
│   ├── loader.py        # ExtensionLoader — 扩展发现/加载
│   ├── providers.py     # LLMProvider — 多后端支持
│   ├── memory.py        # 记忆系统（短期/长期/RAG）
│   └── orchestrator.py  # 多 Agent 编排
├── skills/
│   └── weather/
│       └── SKILL.md     # 示例 Skill
├── step4-production-demo.py  # 全功能演示
├── setup.py
└── README.md
```
