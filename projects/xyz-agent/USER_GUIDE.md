# 🧭 xyz-agent 用户手册

> 版本 2.0 — 从安装到精通，一站式实操指南
>
> 核心原则：**先装好 → 启动 CLI → 交互式操作**

---

## 目录

1. [快速安装](#1-快速安装)
2. [CLI 启动与常用命令](#2-cli-启动与常用命令)
3. [配置 LLM 模型源](#3-配置-llm-模型源)
   - [方案 A：设置环境变量（Windows）](#windows-系统)
   - [方案 A：设置环境变量（macOS / Linux）](#macos--linux-系统)
   - [多 API Key 同时配置](#所有平台通用多-api-key-同时配置需要哪个用哪个)
   - [方案 B：CLI 交互式切换](#方案-b在-cli-中交互式切换模型)
   - [方案 C：Python 代码配置](#方案-c配置多个模型源python-代码)
   - [方案 D：自定义兼容 API](#方案-d自定义兼容-api)
4. [运行 Agent 的 4 种方式](#4-运行-agent-的-4-种方式)
5. [交互式命令（Shell 模式）](#5-交互式命令shell-模式)
6. [管理 Skill](#6-管理-skill)
7. [连接 MCP 服务](#7-连接-mcp-服务)
8. [注册工具](#8-注册工具)
9. [扩展配置（YAML）](#9-扩展配置yaml)

---

## 1. 快速安装

```bash
# 1. 进入到项目目录
cd projects/xyz-agent

# 2. 安装 xyz-agent（源码模式）
pip install -e .

# 3. 安装必需依赖
pip install pyyaml          # SKILL.md 解析

# 4. 可选：安装 LLM 调用支持
pip install openai httpx    # 调用 OpenAI/OpenRouter/DeepSeek 等 API

# 5. 验证安装
xyz-agent --version
# 输出: xyz-agent v1.0.0
```

---

## 2. CLI 启动与常用命令

### 启动交互式 Shell（推荐）

```bash
# 最常用方式 — 进入交互式命令行
xyz-agent chat

# 或
xyz-agent shell
```

启动后你会看到：

```
╭────────────────────────────────────────────────────────╮
│               xyz-agent v1.0.0                         │
│       生产级 AI Agent 框架                              │
│       Skill · MCP · Tool · FC · Selector               │
╰────────────────────────────────────────────────────────╯
  模型: gpt-4o  工具: 3  Skill: 94
  输入 /help 查看命令，/exit 退出

│ 
```

### 常用 CLI 命令（非交互式）

```bash
# 单次运行（不进入 Shell）
xyz-agent run "北京今天天气怎么样？"

# 查看已加载的 Skill
xyz-agent skill list

# 列出工具
xyz-agent tool list

# 查看当前配置
xyz-agent config

# 查看帮助
xyz-agent --help
```

### 退出 CLI

```bash
# 在 Shell 中输入：
/exit          # 退出
/quit          # 同上
# 或按 Ctrl+C
```

---

## 3. 配置 LLM 模型源

使用 Agent 的第一件事是配置 API Key。以下是 4 种配置方式。

### 方案 A：设置环境变量（推荐，一劳永逸）

设置一次，后续打开终端或启动 CLI 自动生效。

#### Windows 系统

**方式 1：临时设置（当前终端窗口有效）**

```cmd
:: CMD 环境
set OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

:: PowerShell 环境
$env:OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

**方式 2：永久设置（推荐）**

通过系统设置：
```
Windows 搜索 → "环境变量"
   → 系统属性 → 环境变量(N)...
   → 用户变量 → 新建(N)
     → 变量名(N): OPENAI_API_KEY
     → 变量值(V): sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   → 确定
```
设置后**需要重启终端**生效。

或通过命令行永久设置（需要管理员权限）：
```cmd
:: CMD（管理员运行）
setx OPENAI_API_KEY "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

:: PowerShell（管理员运行）
[System.Environment]::SetEnvironmentVariable('OPENAI_API_KEY','sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx','User')
```

**方式 3：每次启动 CLI 前自动设置**

创建启动脚本 `start-agent.bat`：
```bat
@echo off
set OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xyz-agent chat
pause
```
双击运行即可。

#### macOS / Linux 系统

**方式 1：临时设置（当前终端窗口有效）**

```bash
export OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

**方式 2：永久设置（推荐）**

编辑 Shell 配置文件，追加一行：

```bash
# 编辑你的 Shell 配置
# bash 用户: ~/.bashrc 或 ~/.bash_profile
# zsh 用户:  ~/.zshrc
# 通用:     ~/.profile

echo 'export OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"' >> ~/.bashrc

# 然后重新加载
source ~/.bashrc
```

验证是否生效：
```bash
echo $OPENAI_API_KEY
# 应输出: sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**方式 3：项目本地 .env 文件**

项目根目录下创建 `.env` 文件：
```bash
cd projects/xyz-agent
echo 'OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' >> .env
```

**所有平台通用：多 API Key 同时配置（需要哪个用哪个）**

你可以在环境变量中同时配置多个 API Key：

```bash
# Linux/macOS: ~/.bashrc
export OPENAI_API_KEY="sk-xxx"          # OpenAI / 兼容 API
export DEEPSEEK_API_KEY="sk-xxx"        # DeepSeek
export OPENROUTER_API_KEY="sk-or-xxx"   # OpenRouter
export ANTHROPIC_API_KEY="sk-ant-xxx"   # Anthropic Claude
export GOOGLE_API_KEY="xxx"             # Google Gemini
export QWEN_API_KEY="sk-xxx"            # 通义千问
```

之后在 CLI 中用 `/model` 切换模型时，Agent 会自动读取对应的 API Key。

**支持的模型源与环境变量对应表：**

| 服务 / 模型源 | 环境变量 | API Key 获取地址 |
|:-------------|:---------|:-----------------|
| **OpenAI**（GPT-4o、GPT-4o-mini 等） | `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| **OpenRouter**（多模型路由，支持 Claude / Llama 等） | `OPENROUTER_API_KEY` | https://openrouter.ai/keys |
| **DeepSeek**（DeepSeek Chat / Reasoner） | `DEEPSEEK_API_KEY` | https://platform.deepseek.com/ |
| **Anthropic**（Claude Sonnet / Haiku） | `ANTHROPIC_API_KEY` | https://console.anthropic.com/ |
| **Google Gemini**（Gemini Flash / Pro） | `GOOGLE_API_KEY` | https://aistudio.google.com/ |
| **通义千问**（Qwen 2.5） | `QWEN_API_KEY` | https://dashscope.aliyun.com/ |

配置好环境变量后，启动 CLI：

```bash
# 启动交互式 Shell
xyz-agent chat
```

Agent 启动时会自动读取 `OPENAI_API_KEY` 并初始化 LLM Provider。
之后你可以随时在 Shell 中执行 `/model` 切换到其他模型（如 DeepSeek 或 Claude），
Agent 会自动读取对应环境变量中的 Key。

### 方案 B：在 CLI 中交互式切换模型

进入 Shell 后，输入 `/model`：

```
🤖 选择模型（当前: gpt-4o）
────────────────────────────────────────────────
  ● gpt-4o                          OpenAI 旗舰模型，支持 Function Calling  [openai]  ← 当前
    gpt-4o-mini                     OpenAI 轻量版，低成本高速度            [openai]
    claude-sonnet-4                 Anthropic Claude Sonnet 4              [anthropic]
    deepseek/deepseek-chat          DeepSeek V3/Chat                       [deepseek]
    gemini/gemini-2.0-flash         Google Gemini 2.0 Flash（快速）        [gemini]
    qwen/qwen-2.5-72b               通义千问 Qwen 2.5 72B                  [qwen]
    openai/gpt-4o                   OpenRouter 路由: OpenAI GPT-4o          [openrouter]
  ✏️  输入自定义模型                  手动输入模型名称
────────────────────────────────────────────────
↑↓ 选择  |  回车确认  |  / 过滤  |  ESC 取消
```

**操作方式：**
- **↑↓ 方向键** — 上下浏览
- **回车** — 选中并切换
- **`/` 搜索关键词** — 例如输入 `/deepseek` 只显示 DeepSeek 模型
- **选「输入自定义模型」** — 手动输入任意模型名

切换后自动重建引擎，后续对话立即使用新模型。

### 方案 C：配置多个模型源（Python 代码）

```python
from xyz_agent import Agent
from xyz_agent.providers import OpenAIProvider

agent = Agent.from_openai(api_key="sk-xxx", model="gpt-4o")

# 运行时切换为 DeepSeek
agent.provider = OpenAIProvider(
    api_key="sk-xxx",               # 从 DEEPSEEK_API_KEY 读取
    model="deepseek/deepseek-chat",
    base_url="https://api.deepseek.com/v1",
)
agent.rebuild_engine()

# 再切换为 OpenRouter
agent.provider = OpenAIProvider(
    api_key="sk-or-xxx",
    model="anthropic/claude-sonnet-4",
    base_url="https://openrouter.ai/api/v1",
)
agent.rebuild_engine()
```

### 方案 D：自定义兼容 API

任何兼容 OpenAI API 格式的服务都可以用：

```python
agent.provider = OpenAIProvider(
    api_key="你的 Key",
    model="模型名称",
    base_url="https://你的API地址/v1",
)
agent.rebuild_engine()
```

---

## 4. 运行 Agent 的 4 种方式

### 方式 1：CLI 交互式 Shell（推荐）

```bash
xyz-agent chat
```

进入后就是命令行对话，支持完整的 slash 命令系统。这是最推荐的使用方式。

### 方式 2：单次运行

```bash
xyz-agent run "帮我查一下 ReAct 模式是什么"
```

适合脚本调用、自动化集成。

### 方式 3：Python 代码调用

```python
from xyz_agent import Agent

# 一行启动
agent = Agent.from_openai(api_key="sk-xxx", model="gpt-4o")

# 单次运行
result = agent.run("北京的天气怎么样？")
print(result)

# 多轮对话（自动保留上下文）
agent.chat("你好，我叫向阳")
agent.chat("你还记得我叫什么吗？")  # 记得！
```

### 方式 4：Mock 模式（无 API Key 也能跑）

```bash
# 没设置 API Key 时启动 CLI，自动进入 Mock 模式
xyz-agent chat
# ⚠️ 未检测到 OPENAI_API_KEY，使用 Mock 模式演示
```

Mock 模式使用预设响应模拟 LLM，适合测试工具系统和 Skill 集成。

---

## 5. 交互式命令（Shell 模式）

Shell 中输入 `/` 开头的命令，支持 **交互式选择器**（方向键上下选择 + 回车确认）。

### 系统命令

| 命令 | 功能 | 示例 |
|:-----|:-----|:-----|
| `/help` | 显示所有可用命令 | `/help` |
| `/exit` | 退出 Shell | `/exit` |
| `/clear` | 清屏 | `/clear` |
| `/reset` | 重置 Agent 状态 | `/reset` |

### 交互式选择命令（核心功能）

| 命令 | 功能 | 操作方式 |
|:-----|:-----|:---------|
| `/skill` | **交互选择 Skill 并加载** | ↑↓选择 → 回车加载 |
| `/model` | **交互切换模型** | ↑↓选择 → 回车切换 |
| `/mcp` | **交互管理 MCP 服务器** | 菜单导航，多步操作 |
| `/commands` | **浏览所有注册命令** | ↑↓选择 → 回车查看详情 |

#### `/skill` — 选择加载 Skill

```
📦 已加载 Skill (94 个) — 上下键选择，回车加载
─────────────────────────────────────────────────────
    code-review                     代码审查       [software-development]
    test-driven-development         TDD 工作流     [software-development]
  ▸ systematic-debugging            系统调试        [software-development]
    writing-plans                   编写实现计划    [software-development]
    llama-cpp                       本地模型推理    [mlops]
    obsidian                        笔记管理        [note-taking]
    ...
─────────────────────────────────────────────────────
↑↓ 选择  |  回车加载  |  / 过滤  |  ESC 取消
```

- 直接回车选中 → 加载该 Skill 的全部工具和 system prompt
- 输入 `/research` 过滤 → 只看 research 类 Skill

#### `/model` — 切换模型

见 [方案 B](#方案-b在-cli-中交互式切换模型)

#### `/mcp` — 管理 MCP 服务器

输入 `/mcp` 后，弹出操作菜单：

```
🔌 MCP 管理
──────────────────────────────────
  📋  查看已连接的服务器
  🔌  连接新服务器（预设模板）
  🔌  连接新服务器（自定义）
  📡  发现并注册 MCP 工具
──────────────────────────────────
↑↓ 选择  |  回车确认  |  ESC 取消
```

**预设模板**（选第二个选项后可见）：

| 模板 | 功能 | 需要 |
|:-----|:-----|:----|
| `filesystem` | 文件系统读写 | Node.js |
| `github` | GitHub API 集成 | Node.js + GITHUB_TOKEN |
| `playwright` | 浏览器自动化 | Node.js |
| `sqlite` | SQLite 数据库查询 | uvx |
| `fetch` | 网页内容抓取 | uvx |
| `sequential-thinking` | 分步推理思考 | Node.js |

选择模板后自动连接，并询问是否同步发现工具。

#### `/commands` — 浏览命令

```
📋 已注册命令（共 8 个）— 选中查看详情
──────────────────────────────────
    help                          显示帮助信息        [system]
    tools                         列出所有工具        [system]
  ▸ skills                        列出所有 Skill      [system]
    mcp                           查看 MCP 状态       [system]
    clear                         重置对话            [system]
    config                        查看配置            [system]
    version                       显示版本            [system]
    hello                         打招呼              [general]
──────────────────────────────────
↑↓ 选择  |  回车查看  |  / 过滤  |  ESC 取消
```

选中后显示该命令的详细用法。

### 传统列表命令

| 命令 | 功能 |
|:-----|:-----|
| `/tool list` | 列出所有注册的工具 |
| `/tool add <name> <desc>` | 快速注册桩工具 |
| `/skill list` | 列出所有 Skill（文本方式） |
| `/skill load <path>` | 从目录加载 Skill |
| `/skill refresh` | 刷新所有 Skill |
| `/mcp list` | 列出 MCP 服务器 |
| `/mcp connect <name> <cmd> [args]` | 手动连接 MCP |
| `/mcp disconnect <name>` | 断开 MCP |
| `/mcp discover` | 同步 MCP 工具 |
| `/config` | 查看当前配置 |
| `/config set <key> <value>` | 修改配置 |
| `/stats` | 运行统计 |
| `/trace` | 步骤追踪 |

---

## 6. 管理 Skill

Skill = **知识 + 工具 + 工作流** 的可复用封装。每个 Skill 是一个目录下的 `SKILL.md` 文件。

### SKILL.md 格式

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

### 加载 Skill 的 3 种方式

**方式 A：CLI 交互式选择（推荐）**

启动 Shell，输入 `/skill`，上下选择后回车即可：

```bash
xyz-agent chat
/skill
# ↑↓ 选择 → 回车加载
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

### 已有的 Skill 模板

本机 `~/.hermes/skills/` 下包含 **95+ 个** 现成 Skill（来自 Hermes Agent）：

| 分类 | 代表 Skill |
|:-----|:-----------|
| 开发 | `code-review`, `test-driven-development`, `systematic-debugging`, `writing-plans`, `spike` |
| AI/ML | `llama-cpp`, `serving-llms-vllm`, `huggingface-hub`, `dspy` |
| 文档 | `obsidian`, `arxiv`, `youtube-content` |
| 创意 | `ascii-art`, `excalidraw`, `sketch` |

每个 Skill 包含 system prompt 和工具定义，加载后自动生效。

---

## 7. 连接 MCP 服务

MCP (Model Context Protocol) 让你连接外部工具服务器，自动发现并注册工具。

### 方式 A：CLI 交互式连接

```bash
xyz-agent chat
/mcp
# 选择「连接新服务器（预设模板）」
# ↑↓ 选择模板 → 回车确认 → 自动发现工具
```

### 方式 B：CLI 命令行连接

```bash
# Shell 中手动连接
/mcp connect filesystem npx -y @modelcontextprotocol/server-filesystem /tmp
/mcp discover

# 断开
/mcp disconnect filesystem
```

### 方式 C：Python 代码

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

### 更多 MCP 示例

```python
# GitHub
agent.setup_mcp("github", "npx", ["-y", "@modelcontextprotocol/server-github"])

# SQLite
agent.setup_mcp("db", "uvx", ["mcp-server-sqlite", "--db-path", "/tmp/test.db"])

# 抓取网页
agent.setup_mcp("fetch", "uvx", ["mcp-server-fetch"])

# 自定义 Python 脚本
agent.setup_mcp("custom", "python", ["my_mcp_server.py"])
```

---

## 8. 注册工具

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

> 函数签名、类型注解、docstring 自动转为 LLM Function Calling Schema。

### 方式 B：注册回调函数

```python
from xyz_agent import ToolRegistry
from xyz_agent import _default_registry

reg = _default_registry
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

### 工具命名规则

```
普通工具:     tool_name
Skill 工具:   skill_name:tool_name
MCP 工具:     mcp:server_name:tool_name
```

---

## 9. 扩展配置（YAML）

### 生成示例配置

```bash
xyz-agent init
# 生成 ~/.xyz-agent/extensions.yaml
```

### 完整配置示例

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
    args:
      - -y
      - "@modelcontextprotocol/server-filesystem"
      - /tmp
    enabled: false    # 需要 Node.js

  - name: github
    command: npx
    args:
      - -y
      - "@modelcontextprotocol/server-github"
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

编辑后重启 Shell 生效。

---

## 快速问题排查

| 现象 | 原因 | 解决 |
|:-----|:-----|:-----|
| `Agent 已初始化 (gpt-4o)` 但回答是模拟数据 | 未设置 API Key | `export OPENAI_API_KEY=sk-xxx` |
| `/mcp connect` 失败 | 缺少 Node.js 或 npx | 安装 Node.js: `brew install node` |
| `/skill` 列表为空 | Skill 目录不存在 | `/skill load ~/.hermes/skills/` |
| 切换模型后不生效 | 需要重建引擎 | 已在 `/model` 中自动调用 |
| 中文乱码 | open() 缺 encoding | 已修复，`encoding="utf-8"` |
| 方向键不工作 | 某些终端限制 | 试试 j/k 键代替 |
