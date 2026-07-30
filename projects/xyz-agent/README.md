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
│  ├─ SkillManager   — Skill 加载         │
│  ├─ MCPManager     — MCP 协议客户端     │
│  ├─ MemorySystem   — 长期/RAG 记忆      │
│  └─ LLMProvider    — 多种 LLM 后端      │
└─────────────────────────────────────────┘
```

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
│   ├── skill.py         # Skill 加载管理
│   ├── command.py       # 内置命令系统
│   ├── memory.py        # 长期/RAG 记忆
│   ├── mcp_client.py    # MCP 协议客户端
│   ├── loader.py        # 扩展加载器
│   ├── orchestrator.py  # 多 Agent 编排
│   ├── cli.py           # 命令行入口
│   └── cli_selector.py  # 交互式选择器
├── skills/              # 示例 Skill
│   └── weather/SKILL.md
├── setup.py
├── USER_GUIDE.md        # 完整用户手册
└── README.md
```
