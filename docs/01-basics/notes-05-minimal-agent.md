# 动手：写一个最简单的 LLM 调用 + 工具使用

> 学习日期：2026-05-30
> 前置知识：主流 Agent 框架概览（notes-04-agent-frameworks.md）
> 实战项目：`projects/01-minimal-agent/`

---

## 1. 学习目标

亲手实现一个极简 Agent 的核心流程——**ReAct 模式的最小实现**：

```
用户输入 → LLM 推理（决定是否调用工具）
               │
        ┌──────┴──────┐
        ▼              ▼
     调用工具        直接回答
        │
        ▼
     观察结果 → 继续推理 → 最终回答
```

---

## 2. 三步递进法

### Step 1：最基础的 LLM 调用

```python
from openai import OpenAI

client = OpenAI(api_key="...")
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "北京天气怎么样？"}],
)
print(response.choices[0].message.content)
```

**问题：** LLM 只能"说"，不能"做"。它回答天气时只能根据训练数据瞎猜，没法实时查询。

### Step 2：Function Calling + 工具执行

给 LLM 注册工具 Schema，让它知道"你可以调用这些函数"：

```python
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的当前天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称"},
                },
                "required": ["city"],
            },
        },
    },
]
```

**流程：**

```
用户: "北京天气怎么样？"
  │
  ▼
LLM 分析 → 决定调用 get_weather(city="北京") → 返回 tool_calls
  │
  ▼
开发者代码→ 执行 get_weather("北京") → 返回 "晴，25°C"
  │
  ▼
把 tool 结果加入对话 → LLM 综合生成回答 → "北京今天晴，25°C"
```

#### 关键概念：tool_choice

| 参数值 | 行为 |
|--------|------|
| `"auto"` | LLM 自主决定是否调用工具（推荐） |
| `"required"` | 强制 LLM 调用至少一个工具 |
| `{"type": "function", "function": {"name": "xxx"}}` | 强制调用指定工具 |

### Step 3：完整的 ReAct 循环

实际问题往往需要**多步推理**。例如：

```
用户: "算一下人均销售额（销售额÷用户数）"

第1轮:
  LLM 推理 → "我需要先查销售额和用户数"
          → 调用 search_database("销售额") → ¥12,800,000
          → 调用 search_database("用户数") → 85,000

第2轮:
  LLM 推理 → "现在我有数据了，计算 12800000 / 85000"
          → 调用 calculate("12800000 / 85000") → 150.59

第3轮:
  LLM 综合回答 → "4月人均销售额约为¥150.59"
```

**核心代码模式：**

```python
while step < MAX_ITERATIONS:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=TOOLS,
    )

    if not response.choices[0].message.tool_calls:
        # LLM 准备好回答了
        break

    for tool_call in response.choices[0].message.tool_calls:
        result = execute_tool(tool_call)  # 执行工具
        messages.append({"role": "tool", "content": result})

    # 继续循环，让 LLM 基于观察结果推理
```

---

## 3. 完整代码（3 个文件）

| 文件 | 说明 |
|------|------|
| `step1-basic-llm.py` | 基础 LLM 调用 |
| `step2-function-calling.py` | Function Calling + 工具注册与执行 |
| `step3-react-loop.py` | 完整的 ReAct 循环 |

📍 代码位置：`projects/01-minimal-agent/`

---

## 4. 从极简到框架

写完这个极简 Agent，再回头看框架，就明白它们在做什么了：

| 我们自己实现的 | 框架帮我们做的 |
|---------------|---------------|
| 手动解析 tool_calls | LangChain `ToolNode` 自动执行 |
| 手动管理 messages 列表 | LangGraph `StateGraph` 管理状态 |
| 手写 while 循环 | LangGraph Edge 自动路由 |
| 手动拼接历史 | Memory 模块自动管理 |
| 手写 tool 注册 | `@tool` 装饰器自动生成 Schema |

**核心认识：框架没有魔法，只是把我们的手动工作封装起来了。**

---

## 5. 🎯 面试题

### Q1: 手写一个极简 ReAct Agent 的核心循环（伪代码）

**参考答案：**
```python
messages = [system_prompt, user_message]

while not done and step < max_steps:
    response = llm(messages, tools=available_tools)

    if not response.has_tool_calls:
        return response.content  # 最终回答
    else:
        for call in response.tool_calls:
            result = execute(call.function.name, call.function.args)
            messages.append(ToolMessage(content=result, tool_call_id=call.id))
```

关键点：循环条件、工具结果追加到对话、最大步数防死循环

### Q2: Function Calling 的工作原理是什么？LLM 是真正"调用"了函数吗？

**参考答案：**
- LLM **没有真正调用函数**。它只是输出了特殊的 JSON 格式（tool_calls），包含函数名和参数
- 真正的函数执行由**开发者代码**完成
- LLM 根据工具 Schema（名称+描述+参数）决定什么时候调用、传什么参数
- 工具结果以 system/tool 角色的消息注入回 LLM，LLM 据此生成最终回答
- 关键：LLM 是"建议调用"，开发者是"实际执行"

### Q3: 如何防止 Agent 陷入死循环？

**参考答案：**
1. **最大迭代次数**（MAX_ITERATIONS），到达后强制结束
2. **Token 预算**（max_tokens），防止无限生成
3. **时间超时**（timeout），单步超时自动终止
4. **检测重复** — 连续 N 步调用相同工具且相同参数，判定循环
5. **人类介入**（Human-in-the-loop）— 关键步骤暂停等待审核
6. **工具副作用限制** — 只读工具不限次，写操作工具限制调用次数

### Q4: `tool_choice="auto"` 和 `tool_choice="required"` 有什么区别？什么时候用后者？

**参考答案：**
- `auto`：LLM 自主判断是否需要调用工具，不需要时直接文本回复
- `required`：强制 LLM 调用至少一个工具，不会直接回复纯文本
- 用 `required` 的场景：路由 Agent（必须决定转给哪个子 Agent）、数据提取（必须调用解析工具）、分类任务（必须调用分类工具以输出结构化结果）

### Q5: 工具描述的 prompt 工程——工具描述写得好坏对 Agent 行为有什么影响？

**参考答案：**
影响巨大。实践要点：
1. **描述要精确**：`获取指定城市当前天气` vs `查询信息` — 前者让 LLM 更准确判断何时使用
2. **参数说明要完整**：包括格式要求、有效值范围、示例值
3. **错误处理说明**：工具什么时候可能失败，LLM 应该怎么处理
4. **副作用说明**：这个工具是否修改数据？是否消耗资源？
5. **性能提示**：如果工具很慢，提示 LLM 只在必要时调用

---

## 6. 📚 延伸阅读

- [OpenAI Function Calling 文档](https://platform.openai.com/docs/guides/function-calling)
- [LangGraph Quick Start](https://langchain-ai.github.io/langgraph/tutorials/introduction/)
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- 项目代码：`projects/01-minimal-agent/`

---

> 下一节预告：**Agent 核心设计模式（ReAct、Plan-Execute、Reflection）** 🧠
