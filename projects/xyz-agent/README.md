# xyz-agent — 学习驱动的 AI Agent 框架

> 从学习到生产就绪，模块化 Agent 框架。
> 参考 [Hermes Agent](https://hermes-agent.nousresearch.com) 架构设计。
> Skill、MCP、Command、Function Calling 全部支持。

## 快速开始

```bash
cd projects/xyz-agent
pip install -e .
pip install pyyaml httpx

# 方式一：使用环境变量启动（自动读取 OPENAI_API_KEY）
export OPENAI_API_KEY="sk-xxx"
xyz-agent chat

# 方式二：启动后交互式切换模型（/model 命令）
# 支持 DeepSeek / OpenRouter / Anthropic / Gemini 等所有兼容 OpenAI API 的服务
```

### 使用 DeepSeek（已验证）

```bash
# 设置环境变量
export DEEPSEEK_API_KEY="sk-xxx"
export OPENAI_API_KEY="$DEEPSEEK_API_KEY"  # 或用 SDK 方式

# 启动后输入 /model 选择 DeepSeek 模型
xyz-agent chat
```

```python
from xyz_agent import Agent
from xyz_agent.providers import OpenAIProvider

# 直接使用 DeepSeek（已验证 deepseek-v4-flash）
agent = Agent(
    llm_provider=OpenAIProvider(
        api_key="sk-xxx",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com/v1",
    ),
)
agent.initialize()
result = agent.run("现在几点了？帮我计算 1234 * 5678 等于多少？")
print(result)
# ✅ Agent 自动调用工具、Function Calling 和多轮对话均正常
```

[📖 完整用户手册 →](USER_GUIDE.md)

## 架构全景

```
┌─ 用户 ──────────────────────────────────┐
│  CLI (cli.py) ←→ CommandSystem          │
│  Python SDK (agent.py)                  │
└─────────────────────────────────────────┘
                      │
                      ▼
┌─ Agent ─────────────────────────────────┐
│  ├─ ReActEngine    — 推理循环           │
│  ├─ ToolRegistry   — 工具注册与执行      │
│  ├─ SystemTools    — 内置工具集 file/terminal
│  ├─ SkillManager   — Skill 加载         │
│  ├─ MCPManager     — MCP 协议客户端     │
│  ├─ MemorySystem   — 长期/RAG 记忆      │
│  └─ LLMProvider    — 多种 LLM 后端      │
└─────────────────────────────────────────┘
```

## 内置系统工具集（Toolset）

对齐 Hermes 的 `file` / `terminal` toolsets 设计，`xyz_agent` 内置了
Agent 无需任何 Skill 即可使用的通用能力，导入后自动注册到全局 `ToolRegistry`：

| Toolset | 工具 | 说明 |
|---------|------|------|
| `file` | `read_file` | 读取文本文件（UTF-8，支持截断） |
| `file` | `write_file` | 写入/追加文本文件 |
| `file` | `list_dir` | 列出目录内容（支持递归） |
| `terminal` | `run_command` | 执行 shell 命令（超时+安全白名单） |

```python
from xyz_agent import Agent, run_command

# 内置工具自动可用，无需注册
agent = Agent.from_openai(api_key="sk-...")
result = agent.run("帮我看看当前目录下有哪些文件，并读取 README.md 的开头")
```

### Skill 的两种能力来源（Hermes 风格）

1. **引用全局工具** — skill 只提供知识/编排（Prompt），工具名命中内置
   能力时直接复用（如 devops skill 引用 `read_file` / `run_command`）。
2. **自带真实实现** — skill 在声明里用 `fn: "scripts/xx.py:func"` 指向
   实现文件，加载时动态注册真实函数（如 weather skill）。

不再注册"占位假工具"——声明了但无法执行的工具会明确告警，避免 LLM 误用。

### Skill 按需加载（skill_view / skill_list）

当加载大量 skill 时，把所有详情塞进主上下文会撑爆 token。参考 Hermes 的
「先列目录，LLM 点菜，再上菜」机制：

- 主 system prompt **永远只注入所有 skill 的目录**（名字 + 一句话描述），
  无论 skill 数量多少
- 注册两个内置工具：`skill_list()` 列出目录、`skill_view(name)` 加载指定
  skill 的**完整详情**
- LLM 根据目录判断用户任务命中哪个 skill → 调用 `skill_view` 主动加载 →
  按加载到的流程执行

```python
# 6 个 skill 时：主上下文只有目录，详情按需加载
result = agent.run("帮我算 23*45+67")
# 调用链：skill_view("calculator") → calculator_calc("23 * 45 + 67") → 1102
```

这样 skill 数量不再有硬编码上限，token 成本是 O(目录) 而非 O(全部详情)。

## 最小示例

```python
from xyz_agent import Agent

agent = Agent.from_openai(api_key="sk-...")
result = agent.run("北京和上海哪个城市更大？")
print(result)
```

## 项目结构

```
xyz-agent/
├── xyz_agent/
│   ├── agent.py         # 高层 Agent 封装
│   ├── engine.py        # ReAct 推理循环
│   ├── providers.py     # LLM 提供者
│   ├── tool.py          # 工具注册与执行
│   ├── system_tools.py  # 内置工具集 file/terminal
│   ├── skill_tools.py   # skill 按需加载 (skill_view/skill_list)
│   ├── skill.py         # Skill 加载管理
│   ├── command.py       # 内置命令系统
│   ├── memory.py        # 长期/RAG 记忆
│   ├── mcp_client.py    # MCP 协议客户端
│   ├── loader.py        # 扩展加载器
│   ├── orchestrator.py  # 多 Agent 编排
│   ├── cli.py           # 命令行入口
│   └── cli_selector.py  # 交互式选择器
├── skills/              # 示例 Skill（6 个）
│   ├── weather/         # 自带真实实现（scripts/impl.py）
│   ├── calculator/      # 自带安全计算实现（scripts/impl.py）
│   ├── translator/      # 自带词典式实现（scripts/impl.py）
│   ├── devops/          # 引用内置系统工具
│   ├── git-helper/      # 引用内置 run_command
│   └── notes/           # 引用内置 file 工具
├── setup.py
├── USER_GUIDE.md        # 完整用户手册
└── README.md
```
