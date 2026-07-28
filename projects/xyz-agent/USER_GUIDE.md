# 🧭 xyz-agent 用户手册

> 版本 3.0 — 基于重构后的架构（借鉴 Hermes Agent 设计）
>
> 核心理念：**安装 → 启动 → 交互式操作**

---

## 目录

1. [架构概览](#1-架构概览)
2. [快速安装](#2-快速安装)
3. [配置 LLM 模型源](#3-配置-llm-模型源)
4. [CLI 启动与常用命令](#4-cli-启动与常用命令)
5. [Shell 交互式命令](#5-shell-交互式命令)
6. [管理 Skill](#6-管理-skill)
7. [连接 MCP 服务](#7-连接-mcp-服务)
8. [注册工具](#8-注册工具)
9. [Python SDK 使用](#9-python-sdk-使用)
10. [扩展配置](#10-扩展配置)
11. [快速问题排查](#11-快速问题排查)

---

## 1. 架构概览

```
xyz-agent/
├── xyz_agent/
│   ├── agent.py         # 高层 Agent 封装（集成所有子系统）
│   ├── engine.py        # ReAct 推理循环（思考→行动→观察）
│   ├── providers.py     # LLM 提供者（OpenAI / OpenRouter / DeepSeek）
│   ├── tool.py          # 工具注册与执行
│   ├── skill.py         # Skill（可复用能力单元）加载与管理
│   ├── command.py       # 内置命令系统（/help /tools /skills 等）
│   ├── memory.py        # 长期记忆 + RAG 检索增强记忆
│   ├── mcp_client.py    # MCP（Model Context Protocol）客户端
│   ├── loader.py        # 扩展加载器（YAML 配置 / 自动发现）
│   ├── orchestrator.py  # 多 Agent 编排引擎
│   ├── cli.py           # 命令行入口
│   └── cli_selector.py  # 交互式选择器（方向键选择）
├── setup.py             # pip 安装配置
├── USER_GUIDE.md        # ← 你正在看的就是
└── README.md            # 项目介绍
```

**各层的协作关系：**

```
你（用户）
  │
  ▼
CLI (cli.py) ───→ CommandSystem (command.py) — /help /tools /skills ...
  │
  ▼
Agent (agent.py) — 统一入口，组装所有子系统
  ├── ReActEngine (engine.py)  — 核心推理循环
  ├── ToolRegistry (tool.py)   — 工具注册与执行
  ├── SkillManager (skill.py)  — Skill 加载和 system prompt 注入
  ├── MCPManager (mcp_client.py) — 外部 MCP 工具
  ├── MemorySystem (memory.py) — 长期/RAG 记忆
  └── LLMProvider (providers.py) — 调用 LLM API
```

---

## 2. 快速安装

```bash
# 1. 进入项目目录
cd projects/xyz-agent

# 2. 源码安装
pip install -e .

# 3. 安装 pyyaml（SKILL.md 解析必需）
pip install pyyaml

# 4. 可选：LLM API 支持
pip install httpx              # 调用 OpenAI / OpenRouter / DeepSeek

# 5. 验证
xyz-agent --version
# 输出: xyz-agent v1.0.0
```

> 💡 `pip install -e .` 让修改源码后即时生效，不用每次重装。

---

## 3. 配置 LLM 模型源

### 3.1 环境变量设置（推荐）

设置一次，永久生效。Agent 启动时自动读取。

**macOS / Linux：**

```bash
# 编辑 Shell 配置文件
echo 'export OPENAI_API_KEY="sk-xxx...xxxx"' >> ~/.bashrc
source ~/.bashrc
```

**Windows：**

```cmd
setx OPENAI_API_KEY "sk-xxx...xxxx"
:: 需重启终端
```

### 3.2 同时配置多个 API Key

CLI 中可用 `/model` 命令实时切换：

```bash
# ~/.bashrc 中配置多个 Key
export OPENAI_API_KEY="sk-xxx"          # OpenAI / 兼容 API
export DEEPSEEK_API_KEY="sk-xxx"        # DeepSeek
export OPENROUTER_API_KEY="sk-or-xxx"   # OpenRouter（可路由到 Claude / Llama）
export ANTHROPIC_API_KEY="sk-ant-xxx"   # Anthropic Claude
export GOOGLE_API_KEY="xxx"             # Google Gemini
export QWEN_API_KEY="sk-xxx"            # 通义千问
```

**API Key 与环境变量对照表：**

| 服务 | 环境变量 | 获取地址 |
|:-----|:---------|:---------|
| **OpenAI** | `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| **OpenRouter** | `OPENROUTER_API_KEY` | https://openrouter.ai/keys |
| **DeepSeek** | `DEEPSEEK_API_KEY` | https://platform.deepseek.com/ |
| **Anthropic** | `ANTHROPIC_API_KEY` | https://console.anthropic.com/ |
| **Google Gemini** | `GOOGLE_API_KEY` | https://aistudio.google.com/ |
| **通义千问** | `QWEN_API_KEY` | https://dashscope.aliyun.com/ |

### 3.3 CLI 中交互式切换模型

启动 Shell 后输入 `/model`，用方向键选择：

```
🤖 选择模型（当前: gpt-4o）
────────────────────────────────────────────────
  ● gpt-4o                          OpenAI 旗舰模型                     [openai]  ← 当前
    gpt-4o-mini                     OpenAI 轻量版                       [openai]
    claude-sonnet-4                 Claude Sonnet 4                     [anthropic]
    deepseek/deepseek-chat          DeepSeek V3/Chat                    [deepseek]
    ...
  ✏️  自定义模型                    手动输入模型名称                     [custom]
────────────────────────────────────────────────
↑↓ 选择  |  回车确认  |  / 过滤  |  ESC 取消
```

- **↑↓** 浏览 / **回车** 切换
- **`/`** 输入关键词过滤（比如 `/deepseek`）
- **自定义模型** 选最后一项，可手动输入任意模型名

---

## 4. CLI 启动与常用命令

### 4.1 启动交互式 Shell（推荐）

```bash
xyz-agent chat
# 或
xyz-agent shell
```

启动后：

```
╭────────────────────────────────────────────────────────╮
│                  xyz-agent v1.0.0                      │
│            生产级 AI Agent 框架                         │
│            Skill · MCP · Tool · FC · Selector          │
╰────────────────────────────────────────────────────────╯
  模型: gpt-4o  工具: 0  Skill: 95
  输入 /help 查看命令，/exit 退出

│ 󰚩 
```

### 4.2 非交互式命令

```bash
# 单次运行
xyz-agent run "北京今天天气怎么样？"

# 查看 Skill
xyz-agent skill list

# 查看工具
xyz-agent tool list

# 查看配置
xyz-agent config

# 生成示例扩展配置
xyz-agent init

# 查看版本
xyz-agent --version
```

### 4.3 Mock 模式（无 API Key）

不设置 API Key 时，自动使用 MockProvider 模拟 LLM 响应，适合测试工具和 Skill。

```bash
xyz-agent chat
# Agent 自动使用 Mock 模式，可直接体验完整功能
```

---

## 5. Shell 交互式命令

Shell 中输入 `/` 开头的命令。部分命令支持**交互式选择器**（方向键 + 回车）。

### 5.1 系统命令

| 命令 | 功能 | 说明 |
|:-----|:-----|:-----|
| `/help` | 显示所有命令 | 列出 CommandSystem 中注册的所有命令 |
| `/exit` 或 `/quit` | 退出 Shell | 也可按 Ctrl+C |
| `/clear` | 清屏 | 保留对话历史 |
| `/reset` | 重置 Agent 状态 | 清空对话上下文 |
| `/version` | 显示版本 | `xyz-agent v1.0.0` |
| `/config` | 查看当前配置 | 显示 AgentConfig 全部字段 |

### 5.2 交互式选择命令（核心功能）

| 命令 | 功能 | 操作 |
|:-----|:-----|:-----|
| `/skill` | **交互选择 Skill** | ↑↓ 选择 → 回车加载 |
| `/model` | **交互切换模型** | ↑↓ 选择 → 回车切换 |
| `/mcp` | **管理 MCP 服务器** | 菜单式操作 |
| `/commands` | **浏览所有命令** | 选中查看详情 |

### 5.3 传统列表命令

| 命令 | 功能 |
|:-----|:-----|
| `/tool list` | 列出所有注册的工具 |
| `/tool add <name> <desc>` | 快速注册桩工具 |
| `/skill list` | 列出所有 Skill（文本方式） |
| `/skill load <path>` | 从目录加载 Skill |
| `/skill refresh` | 刷新所有 Skill |
| `/skill generate [path]` | 生成示例 SKILL.md |
| `/mcp list` | 列出 MCP 服务器 |
| `/mcp connect <name> <cmd> [args]` | 手动连接 MCP |
| `/mcp disconnect <name>` | 断开 MCP |
| `/mcp discover` | 同步 MCP 工具 |
| `/stats` | 运行统计 |
| `/trace` | 步骤追踪 |

### 5.4 调试命令

| 命令 | 功能 |
|:-----|:-----|
| `/stats` | 查看运行统计（步骤数 / Token / 耗时） |
| `/trace` | 查看详细步骤追踪 |

---

## 6. 管理 Skill

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

```markdown
---
name: my-skill
description: "这个 skill 做什么的"
version: 1.0.0
author: 你的名字
license: MIT
metadata:
  hermes:
    tags: [关键词1, 关键词2]
---

# My Skill

## 使用场景
- 什么情况下会用到这个 Skill

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

以下是这个 Skill 的系统指令，Agent 启动时自动融合到提示词中。
```

### 6.2 加载 Skill 的 3 种方式

**方式 A：CLI 交互式选择（推荐）**

```bash
xyz-agent chat
/skill   # ↑↓ 选择 → 回车加载
```

**方式 B：从目录加载**

```bash
xyz-agent skill load ~/.hermes/skills/
# 或在 Shell 中：
/skill load ~/.hermes/skills/
```

**方式 C：生成 Skill 模板**

```bash
# 在 Shell 中：
/skill generate ./skills/my-new-skill/SKILL.md
```

### 6.3 本机自带的 Skill

`~/.hermes/skills/` 下包含 **95+ 个**现成 Skill（来自 Hermes Agent）：

| 分类 | 代表 Skill |
|:-----|:-----------|
| 开发 | `code-review`, `test-driven-development`, `systematic-debugging`, `writing-plans` |
| AI/ML | `llama-cpp`, `serving-llms-vllm`, `huggingface-hub`, `dspy` |
| 文档 | `obsidian`, `arxiv`, `youtube-content` |
| 创意 | `ascii-art`, `excalidraw`, `sketch` |
| DevOps | `kanban-orchestrator`, `webhook-subscriptions` |

---

## 7. 连接 MCP 服务

MCP (Model Context Protocol) 让你连接外部工具服务器，自动发现并注册工具。

### 7.1 CLI 交互式连接

```bash
xyz-agent chat
/mcp
# 选择「连接新服务器（预设模板）」
# ↑↓ 选择模板 → 回车确认 → 自动发现工具
```

### 7.2 预设 MCP 模板

| 模板 | 功能 | 依赖 |
|:-----|:-----|:-----|
| `filesystem` | 文件系统读写 | Node.js |
| `github` | GitHub API 集成 | Node.js + GITHUB_TOKEN |
| `playwright` | 浏览器自动化 | Node.js |
| `sqlite` | SQLite 数据库查询 | uvx |
| `fetch` | 网页内容抓取 | uvx |
| `sequential-thinking` | 分步推理思考 | Node.js |

### 7.3 CLI 命令行连接

```bash
# Shell 中手动连接
/mcp connect filesystem npx -y @modelcontextprotocol/server-filesystem /tmp
/mcp discover

# 断开
/mcp disconnect filesystem

# 查看状态
/mcp list
```

### 7.4 Python 代码连接

```python
from xyz_agent import Agent, AgentConfig

agent = Agent(config=AgentConfig(enable_mcp=True))
agent.initialize()

# 连接 MCP 服务器
agent.setup_mcp(
    name="fs",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
)

# 发现并注册工具
agent.discover_mcp_tools()

# 使用 MCP 工具（命名格式: mcp:服务器名:工具名）
result = agent.run("帮我看看 /tmp 目录下有什么文件")
```

---

## 8. 注册工具

### 8.1 @tool 装饰器（推荐）

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

函数签名、类型注解、docstring 自动转为 LLM Function Calling Schema。

### 8.2 注册回调函数

```python
from xyz_agent import ToolRegistry

reg = ToolRegistry()
reg.register_fn(
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

### 8.3 工具命名规则

```
普通工具:     tool_name
Skill 工具:   skill_name:tool_name
MCP 工具:     mcp:server_name:tool_name
```

### 8.4 在 CLI 中管理工具

```bash
# 列出所有工具
/tool list

# 快速注册桩工具（用于测试）
/tool add my_tool "这是一个测试工具"
```

---

## 9. Python SDK 使用

在 Python 代码中直接使用 xyz-agent：

### 9.1 基础用法

```python
from xyz_agent import Agent

# 一行创建
agent = Agent.from_openai(api_key="sk-xxx", model="gpt-4o")

# 单次运行
result = agent.run("北京的天气怎么样？")
print(result)

# 多轮对话（自动保留上下文）
agent.chat("你好，我叫向阳")
agent.chat("你还记得我叫什么吗？")  # 记得！
```

### 9.2 注册自定义工具

```python
from xyz_agent import Agent, AgentConfig, tool

# 在 Agent 创建前注册工具
@tool
def get_time() -> str:
    """获取当前时间"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

agent = Agent.from_openai(api_key="sk-xxx")
agent.initialize()  # 工具已自动注册
agent.chat("现在几点了？")
```

### 9.3 使用多个模型

```python
from xyz_agent import Agent
from xyz_agent.providers import OpenAIProvider

agent = Agent.from_openai(api_key="sk-xxx", model="gpt-4o")

# 运行时切换为 DeepSeek
agent.provider = OpenAIProvider(
    api_key="sk-xxx",
    model="deepseek/deepseek-chat",
    base_url="https://api.deepseek.com/v1",
)
agent.rebuild_engine()

# 再切换为 OpenRouter（可路由到 Claude）
agent.provider = OpenAIProvider(
    api_key="sk-or-xxx",
    model="anthropic/claude-sonnet-4",
    base_url="https://openrouter.ai/api/v1",
)
agent.rebuild_engine()
```

### 9.4 自定义兼容 API

任何兼容 OpenAI API 格式的服务都可用：

```python
agent.provider = OpenAIProvider(
    api_key="你的 Key",
    model="模型名称",
    base_url="https://你的API地址/v1",
)
agent.rebuild_engine()
```

### 9.5 单步手动控制

```python
agent = Agent.from_openai(api_key="sk-xxx")
agent.initialize()

# 手动逐步执行
agent.engine.reset("写一首关于春天的诗")
while not agent.engine.done:
    agent.engine.step()
    print(agent.engine.steps[-1])
```

### 9.6 多 Agent 编排

使用 Orchestrator 进行流水线式多 Agent 协作：

```python
from xyz_agent import Agent, AgentConfig
from xyz_agent.orchestrator import Orchestrator, OrchestratorConfig, CollabMode
from xyz_agent.providers import OpenAIProvider

def create_agent(name, role):
    return Agent(
        llm_provider=OpenAIProvider(api_key="sk-xxx"),
        config=AgentConfig(name=name, max_steps=5),
    )

orch = Orchestrator(create_agent_fn=create_agent)
result = orch.run(
    goal="写一篇关于 AI Agent 的文章",
    agents=["researcher", "writer", "reviewer"],
    mode=CollabMode.PIPELINE,
)
print(result["final_output"])
```

### 9.7 长短期记忆

```python
from xyz_agent.memory import LongTermMemory, RAGMemory

# 长期记忆（文件持久化）
mem = LongTermMemory(file_path="my_memory.json")
mem.add("用户喜欢 Python", importance=0.8)
results = mem.search("Python")

# RAG 记忆（TF-IDF 检索）
rag = RAGMemory()
rag.add("Agent 框架的核心是 ReAct 循环", chunk=False)
results = rag.search("ReAct")
```

---

## 10. 扩展配置

通过 YAML 文件批量配置 Skill 和 MCP 服务：

```bash
# 生成示例配置
xyz-agent init
# 生成 ~/.xyz-agent/extensions.yaml
```

配置示例：

```yaml
# ~/.xyz-agent/extensions.yaml

# ---- Skill 扩展 ----
skills:
  - name: my-custom-skill
    source: ~/.hermes/skills/research/
    enabled: true

# ---- MCP 服务器 ----
mcp_servers:
  - name: filesystem
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    enabled: false        # 需要 Node.js

  - name: github
    command: npx
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"
    enabled: false

# ---- 自定义命令 ----
commands:
  - name: hello
    description: "打招呼"
    source: inline
    code: |
      def handler(args, ctx):
          return f"你好，{args or '世界'}！"
    enabled: true
```

---

## 11. 快速问题排查

| 现象 | 原因 | 解决 |
|:-----|:-----|:-----|
| 回答是模拟数据 | 没设置 API Key | `export OPENAI_API_KEY=sk-xxx` |
| `/mcp connect` 失败 | 缺少 Node.js | `brew install node` / `apt install nodejs` |
| `/skill` 列表为空 | Skill 目录不存在 | `/skill load ~/.hermes/skills/` |
| 切换模型后没变 | 需要重建引擎 | `/model` 已自动调用 `rebuild_engine()` |
| 方向键不工作 | 某些终端限制 | 试试 `j` / `k` 键代替 ↑↓ |
| 对话到了最大步数 | LLM 陷入循环 | 增加 `max_steps` 或 `/reset` |
