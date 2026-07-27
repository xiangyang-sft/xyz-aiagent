# 🧭 xyz-agent 用户手册

> 版本 1.0 — 从启动到扩展，一站式指南

---

## 目录

1. [快速安装](#1-快速安装)
2. [启动 Agent](#2-启动-agent)
3. [运行模式](#3-运行模式)
4. [命令系统](#4-命令系统)
5. [注册工具](#5-注册工具)
6. [加载 Skill](#6-加载-skill)
7. [连接 MCP](#7-连接-mcp)
8. [扩展配置（YAML 文件）](#8-扩展配置yaml-文件)
9. [Python 插件](#9-python-插件)
10. [FAQ 常见问题](#10-faq-常见问题)

---

## 1. 快速安装

```bash
# 从本地源码安装
cd projects/xyz-agent
pip install -e .
pip install pyyaml          # SKILL.md 解析必需

# 可选：安装更多功能
pip install openai httpx    # OpenAI API 调用
pip install click            # CLI 增强
```

**验证安装：**

```python
from xyz_agent import Agent, __version__
print(f"xyz-agent v{__version__}")
# 输出: xyz-agent v1.0.0
```

---

## 2. 启动 Agent

### 方式 A：一行启动（推荐）

```python
from xyz_agent import Agent

agent = Agent.from_openai(
    api_key="sk-...",    # 或设置环境变量 OPENAI_API_KEY
    model="gpt-4o",      # 支持的模型
)
result = agent.run("北京的天气怎么样？")
print(result)
```

### 方式 B：手动配置

```python
from xyz_agent import Agent, AgentConfig

agent = Agent(config=AgentConfig(
    name="my-agent",
    model="gpt-4o",
    temperature=0.7,
    max_steps=15,
    enable_skills=True,     # 自动加载 Skill
    enable_commands=True,   # 启用命令系统
    enable_mcp=False,       # MCP 可选
    auto_load_skills=True,  # 自动扫描 Skill 目录
    skill_dirs=["~/.hermes/skills/", "./skills/"],
))
agent.initialize()
```

### 方式 C：不用 API Key 也能跑（Mock 模式）

```python
from xyz_agent import Agent, MockProvider, AgentConfig

agent = Agent(
    llm_provider=MockProvider(default_response="最终答案: 模拟回复"),
    config=AgentConfig(name="test"),
)
agent.initialize()
result = agent.run("随便问什么")
print(result)  # 最终答案: 模拟回复
```

### 快速查看 Agent 状态

```python
# 基本信息
info = agent.get_info()
print(info)
# {'name': 'demo', 'version': '1.0.0', 'model': 'gpt-4o',
#  'tools': 2, 'skills': 95, 'mcp_servers': 0, ...}

# 运行统计
stats = agent.get_stats()
# {'total_steps': 3, 'tool_calls': 1, 'total_tokens': 450, ...}
```

---

## 3. 运行模式

### 单次运行

```python
result = agent.run("帮我查一下ReAct模式是什么")
```

### 多轮对话

```python
agent.chat("你好，我叫向阳")
agent.chat("你还记得我叫什么吗？")  # 保留上下文
agent.chat("帮我一件事...")         # 自动延续
```

### 手动单步控制

```python
agent.reset("写一首关于AI的诗")
while not agent.done:
    step = agent.step()
    print(f"[{step.type.value}] {step.content[:50]}...")
```

---

## 4. 命令系统

Agent 内置了 7 个命令，对话中输入 `/` 开头的命令即可使用。

### 内建命令一览

| 命令 | 功能 | 示例 |
|:-----|:-----|:-----|
| `/help` | 显示所有可用命令 | `/help` |
| `/tools` | 列出所有注册的工具 | `/tools` |
| `/skills` | 列出所有加载的 Skill | `/skills` |
| `/mcp` | 查看 MCP 服务器连接状态 | `/mcp` |
| `/clear` | 重置对话状态 | `/clear` 或 `/clear 新问题` |
| `/config` | 查看当前配置 | `/config` |
| `/version` | 查看版本号 | `/version` |

**使用示例：**

```python
agent.chat("/help")      # 📋 可用命令: ...
agent.chat("/tools")     # 🔧 可用工具 (3): ...
agent.chat("/skills")    # 📦 已加载 Skill (95): ...
```

### 添加自定义命令

```python
@agent.command_system.register("hello", "打个招呼", usage="/hello [名字]")
def hello_handler(args: str, ctx: dict) -> str:
    return f"你好，{args or '世界'}！"

# 现在可以直接用
agent.chat("/hello 向阳")  # 你好，向阳！
```

或者在创建 Agent 前：

```python
from xyz_agent import CommandSystem

cmd = CommandSystem()

@cmd.register("ping", "检查 Agent 状态")
def ping_handler(args, ctx):
    return "pong! 🏓"

# 注入到 Agent
agent.command_system = cmd
agent.initialize()
```

---

## 5. 注册工具

### 方式 A：@tool 装饰器（推荐）

```python
from xyz_agent import tool

@tool
def get_weather(city: str) -> str:
    """查询指定城市当前天气"""
    data = {"北京": "晴 25°C", "上海": "多云 28°C"}
    return data.get(city, f"暂无{city}的数据")

@tool
def calculator(expr: str) -> str:
    """计算数学表达式"""
    allowed = set("0123456789+-*/(). ")
    assert all(c in allowed for c in expr), "非法字符"
    return f"{expr} = {eval(expr)}"
```

### 方式 B：ToolRegistry 手动注册

```python
from xyz_agent import ToolRegistry

registry = ToolRegistry()

registry.register_fn(
    name="translate",
    fn=lambda text, lang: f"[{text} -> {lang}]",
    description="文本翻译",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "要翻译的文本"},
            "lang": {"type": "string", "description": "目标语言"},
        },
        "required": ["text", "lang"],
    },
)
```

### 方式 C：MCP 格式注册

```python
registry.register_mcp(
    name="search_web",
    fn=lambda query: f"[搜索: {query}]",
    schema={
        "description": "网络搜索",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
    },
)
```

### 工具命名规则

```
普通工具:     tool_name
Skill 工具:   skill_name:tool_name
MCP 工具:     mcp:server_name:tool_name
```

---

## 6. 加载 Skill

Skill = **知识 + 工具 + 工作流** 的可复用封装。每个 Skill 是一个目录下的 `SKILL.md` 文件。

### 6.1 SKILL.md 格式

```
skills/my-skill/
├── SKILL.md         # 主文件（必需）
├── references/      # 引用文档（可选）
│   └── api.md
└── templates/       # 提示模板（可选）
    └── prompt.j2
```

`SKILL.md` 结构：

```markdown
---
name: my-skill
description: "这个 skill 做什么的 — 简短清晰的一句话描述"
version: 1.0.0
author: 你的名字
license: MIT
metadata:
  hermes:
    tags: [关键词1, 关键词2]
    related_skills: [other-skill]
---

# My Skill 标题

## 使用场景
- 什么情况下会用到这个 Skill
- 解决什么问题

## 提供的工具

```json
[
  {
    "name": "tool_name",
    "description": "工具做什么",
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

以下是这个 Skill 的 system prompt 内容——
会在 Agent 启动时自动融合到系统提示词中。
可以在这里写工作流程、规则、示例等。
```

### 6.2 加载 Skill

**自动加载（推荐）：**

```python
# Agent 初始化时自动扫描 skill_dirs 目录
agent = Agent(config=AgentConfig(
    skill_dirs=["~/.hermes/skills/", "./skills/"]
))
agent.initialize()

# 查看加载结果
print(agent.chat("/skills"))
```

**手动加载：**

```python
from xyz_agent import SkillManager

skill_mgr = SkillManager()
skill_mgr.load_directory("~/.hermes/skills/")   # Hermes Agent 全部 Skill
skill_mgr.load_directory("./skills/")            # 项目自带 Skill

# 查看
for s in skill_mgr:
    print(f"  {s.name} v{s.version} — {s.description[:50]}")
```

**从字符串加载：**

```python
skill_mgr.load_skill("custom", """---
name: custom
description: 自定义 Skill
---
你是编程助手，擅长 Python 和 JavaScript。
""")
```

### 6.3 已有的 Skill 模板

你本机已经有的 Skill（来自 Hermes Agent），`/~/.hermes/skills/` 下包含 **95+ 个** 现成 Skill：

**🛠 开发类**
- `code-review` — 代码审查
- `test-driven-development` — TDD 工作流
- `systematic-debugging` — 系统调试
- `writing-plans` — 编写实现计划
- `spike` — 技术预研

**🤖 AI/ML 类**
- `llama-cpp` — 本地模型推理
- `serving-llms-vllm` — 模型服务
- `huggingface-hub` — 模型下载/上传
- `dspy` — 声明式 LM 编程

**📝 文档类**
- `obsidian` — 笔记管理
- `arxiv` — 论文搜索
- `youtube-content` — 视频转录/总结

**🎨 创意类**
- `ascii-art` — ASCII 艺术
- `excalidraw` — 手绘风格图表
- `sketch` — HTML 原型

**更多...** 运行 `ls ~/.hermes/skills/` 查看完整列表！

---

## 7. 连接 MCP

MCP (Model Context Protocol) 让你连接外部工具服务器，自动发现并注册工具。

### 7.1 连接 stdio MCP 服务器（本地）

```python
from xyz_agent import Agent, AgentConfig

# 创建支持 MCP 的 Agent
agent = Agent(config=AgentConfig(
    enable_mcp=True,
    name="mcp-agent",
))
agent.initialize()

# 连接 MCP 服务器
agent.setup_mcp(
    name="filesystem",
    command="npx",    # 需要 Node.js
    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
    auto_connect=True,
)

# 发现并注册工具
agent.discover_mcp_tools()

# 现在可以直接用 MCP 工具了
# 工具名格式: mcp:服务器名:工具名
result = agent.run("帮我看看 /tmp 目录下有什么文件")
```

### 7.2 更多 MCP 服务器示例

```python
# GitHub MCP
agent.setup_mcp("github", "npx", [
    "-y", "@modelcontextprotocol/server-github",
])

# 数据库 MCP
agent.setup_mcp("db", "npx", [
    "-y", "@modelcontextprotocol/server-postgres",
    "postgresql://user:pass@localhost/db",
])

# 自定义脚本 MCP
agent.setup_mcp("custom", "python", [
    "my_mcp_server.py",
])
```

### 7.3 直接用 MCPManager（不通过 Agent）

```python
from xyz_agent import MCPManager

mcp = MCPManager()

# 连接
mcp.connect_stdio("fs", "npx", ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"])

# 发现工具
tools = mcp.discover_all_tools_sync()
for server, count in tools.items():
    print(f"{server}: {count} 个工具")

# 调用工具
result = mcp.call_tool_sync("fs", "read", {"path": "/tmp/test.txt"})
```

---

## 8. 扩展配置（YAML 文件）

通过 YAML 配置文件声明式管理所有扩展，不用写代码。

### 8.1 配置文件位置

创建 `~/.xyz-agent/extensions.yaml` 或项目根目录的 `extensions.yaml`，Agent 启动时自动发现。

### 8.2 完整配置示例

```yaml
# ~/.xyz-agent/extensions.yaml

# ---- Skill 扩展 ----
skills:
  - name: my-custom-skill
    source: ~/.hermes/skills/research/   # 目录路径
    enabled: true

  - name: remote-skill
    source: https://example.com/skills/coding/
    enabled: false

# ---- MCP 服务器 ----
mcp_servers:
  - name: filesystem
    command: npx
    args:
      - -y
      - "@modelcontextprotocol/server-filesystem"
      - /tmp
    enabled: false   # 需要 Node.js，默认关闭

  - name: github
    command: npx
    args:
      - -y
      - "@modelcontextprotocol/server-github"
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"   # 自动读取环境变量
    enabled: false

# ---- 自定义命令 ----
commands:
  - name: hello
    description: "打招呼"
    source: inline                        # 内嵌 Python 代码
    code: |
      def handler(args, ctx):
          return f"你好，{args or '世界'}！"
    enabled: true

# ---- Python 插件 ----
plugins:
  - name: my_tools
    source: ~/.xyz-agent/plugins/my_tools.plugin.py
    enabled: true
```

### 8.3 加载配置

```python
from xyz_agent import load_extensions, generate_sample_config

# 生成示例配置
generate_sample_config("~/.xyz-agent/extensions.yaml")

# 加载默认位置的扩展
info = load_extensions()
print(info)
# {'skills': 2, 'mcp_servers': 2, 'commands': 1, 'plugins': 1}

# 或手动加载
from xyz_agent import ExtensionLoader
loader = ExtensionLoader()
loader.load_config("extensions.yaml")
loader.apply_to(
    skill_manager=agent.skill_manager,
    mcp_manager=agent.mcp_manager,
    command_system=agent.command_system,
)
```

### 8.4 独立配置文件

也可以在扩展目录放单个配置文件：

| 文件模式 | 类型 |
|:---------|:-----|
| `*.skill.yaml` / `*.skill.json` | Skill 定义 |
| `*.mcp.yaml` / `*.mcp.json` | MCP 服务器 |
| `*.command.yaml` / `*.command.json` | 自定义命令 |
| `*.plugin.py` | Python 插件 |

---

## 9. Python 插件

插件是动态加载的 Python 文件，可以注册工具、命令、监听事件。

### 9.1 创建插件

创建 `my_plugin.plugin.py`：

```python
# my_plugin.plugin.py

def setup(skill_manager=None, command_system=None,
          mcp_manager=None, tool_registry=None):
    """插件入口 — 自动被调用"""

    # 注册命令
    if command_system:
        @command_system.register("status", "查看系统状态")
        def status_handler(args, ctx):
            import psutil
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory().percent
            return f"CPU: {cpu}% | 内存: {mem}%"

    # 注册工具
    if tool_registry:
        def get_ip():
            import requests
            return requests.get("https://httpbin.org/ip").json()["origin"]

        tool_registry.register_fn(
            name="get_public_ip",
            fn=get_ip,
            description="获取本机公网 IP",
        )
```

### 9.2 加载插件

```yaml
# extensions.yaml
plugins:
  - name: my_plugin
    source: ~/.xyz-agent/plugins/my_plugin.plugin.py
    enabled: true
```

或手动加载：

```python
from xyz_agent import ExtensionLoader

loader = ExtensionLoader()
loader.load_directory("~/.xyz-agent/plugins/")
loader.apply_to(
    skill_manager=agent.skill_manager,
    command_system=agent.command_system,
    tool_registry=agent.tool_registry,
)
```

---

## 10. FAQ 常见问题

### Q1：不用 OpenAI 能用吗？

可以。你只需要提供任意 LLM 调用函数：

```python
def my_llm(messages, tools=None):
    """实现你自己的 LLM 调用"""
    response = ...  # 调用本地模型 / 其他 API
    return response_text, token_count, tool_calls

agent = Agent(llm_provider=my_llm)
```

框架还内置了 `OpenRouterProvider`、`MockProvider`。

### Q2：Agent 启动时自动加载了哪些 Skill？

默认扫描以下目录：
- `~/.hermes/skills/` — Hermes Agent 的所有 Skill
- `./skills/` — 项目本地 Skill

### Q3：如何查看当前 Agent 有哪些工具和 Skill？

```python
agent.chat("/tools")    # 查看所有工具
agent.chat("/skills")   # 查看所有 Skill
```

或在代码中：

```python
tools = agent.list_tools()
skills = agent.list_skills()
```

### Q4：Engine 的两种模式有什么区别？

| 模式 | 说明 | 适用场景 |
|:-----|:-----|:---------|
| ReAct 模式 | LLM 输出文本，框架解析工具调用 | 任何 LLM |
| Function Calling | LLM 原生返回结构化工具调用 | OpenAI / 支持 FC 的模型 |

自动检测：如果配置了 `tools`，自动启用 Function Calling 模式。

### Q5：如何不使用自动加载？

```python
agent = Agent(config=AgentConfig(
    auto_load_skills=False,
    auto_load_extensions=False,
))
```

### Q6：工具调用失败会怎么样？

Engine 会捕获异常，把错误信息作为 observation 返回给 LLM，让 LLM 决定下一步（重试或用其他方法）。最多重试 `max_retries` 次。

### Q7：可以和生产环境结合吗？

可以。框架设计时考虑了生产需求：
- 无外部依赖的核心引擎（仅 Python 标准库 + pyyaml）
- 完整的追踪/日志系统 `agent.get_trace()`
- 消息驱动的对话管理（可序列化、可恢复）
- 模块化设计，每个子系统可单独使用、单独测试

### Q8：更多示例？

```bash
# 运行全功能演示
cd projects/xyz-agent
python step4-production-demo.py
```
