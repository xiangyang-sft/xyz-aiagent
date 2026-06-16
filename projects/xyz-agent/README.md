# xyz-agent — 轻量级 AI Agent 框架

> 从最小可用到生产就绪，渐进式构建你自己的 Agent 框架。

## 设计原则

- 🧱 **模块化** — 引擎、工具、记忆、多Agent 各自独立，可插拔
- 🔌 **接口统一** — 每个模块有清晰的抽象基类
- 🎯 **轻量无依赖** — 核心引擎仅 Python 标准库
- 📈 **渐进式复杂度** — 从最小可用版开始，逐步扩展

## 架构

```
xyz-agent/
├── xyz_agent/
│   ├── __init__.py    # 包版本
│   ├── engine.py      # ReAct 循环引擎
│   ├── agent.py       # 高级 Agent 封装
│   ├── tool.py        # 工具系统（TODO）
│   ├── memory.py      # 记忆系统（TODO）
│   ├── orchestrator.py # 多 Agent 编排（TODO）
│   └── cli.py         # CLI 接口（TODO）
├── setup.py
├── requirements.txt
└── README.md
```

## 快速开始

```python
from xyz_agent.agent import Agent, AgentConfig

# 定义工具
def greet(name: str) -> str:
    return f"你好，{name}！"

agent = Agent(
    llm_provider=my_llm_function,
    tools=[{
        "name": "greet",
        "description": "向某人打招呼",
        "parameters": {...},
        "fn": greet,
    }],
)

result = agent.run("帮我打个招呼")
print(result)
```

## 渐进式构建路线

| Step | 内容 | 状态 |
|------|------|:----:|
| 1 | ReAct 循环引擎（最小可用） | ✅ 完成 |
| 2 | 工具系统 + 记忆系统 | ⬜ 进行中 |
| 3 | 多Agent编排 + CLI 封装 + pip 安装 | ⬜ 待开始 |
