# 01-minimal-agent — 极简 Agent 实战

从零实现一个 LLM + Tool Use 的 Agent，三个步骤逐步递进。

## 快速开始

```bash
# 1. 复制环境变量文件
cp .env.example .env
# 编辑 .env 填入你的 API Key

# 2. 安装依赖
pip install openai python-dotenv

# 3. 一步步运行
python step1-basic-llm.py      # 基础 LLM 调用
python step2-function-calling.py  # Function Calling + 工具
python step3-react-loop.py       # 完整 ReAct 循环
```

## 三步骤说明

| 步骤 | 文件 | 学到什么 |
|------|------|----------|
| 1 | step1-basic-llm.py | 最基础的 LLM API 调用 |
| 2 | step2-function-calling.py | Function Calling 注册工具、解析工具调用 |
| 3 | step3-react-loop.py | 完整的 ReAct 循环：多轮推理 + 工具执行 + 综合回答 |

## 核心流程

```
用户输入 → LLM 推理
              │
     ┌────────┴────────┐
     ▼                 ▼
  需要工具？         不需要→直接回答
     │
     ▼
  执行工具
     │
     ▼
  观察结果 → 继续推理...
     │
     ▼
  综合回答用户 ✅
```
