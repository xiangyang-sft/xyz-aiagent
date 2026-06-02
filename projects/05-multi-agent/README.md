# 多 Agent 协作实战项目

> 第二阶段 · 第四课 · 项目代码

## 项目结构

```
projects/05-multi-agent/
├── step1-orchestration.py    # 编排式：Controller + Specialists
├── step2-debate.py           # 协商式：多 Agent 辩论
├── step3-supervisor.py       # 监督者模式 + 流水线
├── step4-multi-framework.py  # 对比 CrewAI 风格 vs LangGraph 风格
└── README.md
```

## 速览

| 文件 | 模式 | 学到什么 |
|------|------|----------|
| step1 | 🧭 编排式 | 一个 Controller 分配任务给多个 Specialist |
| step2 | 🤝 协商式 | 多 Agent 辩论讨论，达成共识 |
| step3 | 🏛️ 监督者+流水线 | Supervisor 管理 Workers / Pipeline 顺序处理 |
| step4 | ⚡ 框架对比 | CrewAI 声明式 vs LangGraph 图编排 |

## 运行

```bash
# 先设置 API Key
export OPENAI_API_KEY=sk-xxx

# 运行各个演示
python step1-orchestration.py
python step2-debate.py
python step3-supervisor.py
python step4-multi-framework.py
```

## 核心认识

> 多 Agent 不是把多个 Agent 放在一起就能 1+1>2。
> 真正的价值在于：**角色分工 × 通信协议 × 协调机制**。
>
> 框架没有魔法，理解三种模式（编排/协商/层级），就能设计自己的多 Agent 系统。
