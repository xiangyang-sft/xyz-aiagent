# 动手：完整单 Agent 应用

> 第二阶段 · 第五课 · 项目代码

## 项目结构

```
projects/06-single-agent-app/
├── step1-minimal-agent.py        # 极简版（~80 行）
├── step2-reasoning-agent.py      # 推理增强版（带记忆+反思）
├── step3-personal-assistant.py   # 完整个人助手（CLI 交互式）
├── step4-summary.py              # 第二阶段总结回顾
└── README.md
```

## 三方案对比

| 方案 | 行数 | 核心能力 | 记忆 | 工具数 |
|------|------|----------|------|--------|
| step1 极简版 | ~80 | ReAct 循环 | 无 | 3 |
| step2 推理版 | ~200 | ReAct + 记忆 + 反思 | JSON 持久化 | 6 |
| step3 完整版 | ~350 | CLI 交互 + RAG + 配置 | SQLite + RAG | 8 |

## 运行方式

```bash
# 设置 API Key
export OPENAI_API_KEY=sk-xxx

# 极简版 — 自动运行示例
python step1-minimal-agent.py

# 推理增强版 — 自动运行示例
python step2-reasoning-agent.py

# 完整个人助手 — 交互式 CLI
python step3-personal-assistant.py
# 或单次问答
python step3-personal-assistant.py "帮我算一下 2^10"

# 查看总结
python step4-summary.py
```

## 数据文件

运行后会在 `agent_data/` 目录生成：
- `memory.json` — 长期记忆
- `config.json` — 用户配置
- `notes/` — 保存的笔记
- `history/` — 对话历史
- `knowledge/` — RAG 知识库
