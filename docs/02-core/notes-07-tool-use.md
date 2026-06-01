# 工具调用：Function Calling 与 Tool Use

> 第 2 阶段 · 第 2 课
>
> 目标：理解工具调用的原理、API 使用方式，以及如何设计高效的工具系统

---

## Step 1：基础知识 — 为什么 Agent 需要工具？

### 1.1 LLM 的固有局限

LLM（大语言模型）再强，也只是个"大脑"，天然有缺陷：

| 局限 | 表现 | 解决方案（工具） |
|------|------|------------------|
| **知识截止** | 训练数据有截止日期，不知道最新信息 | 搜索工具、新闻 API |
| **无法计算** | 复杂数学计算不可靠 | 计算器、代码解释器 |
| **无法感知** | 不知道实时天气、股价、位置 | 天气 API、股票 API、地理编码 |
| **无法行动** | 只能输出文本，不能操作外部系统 | 数据库、API、文件系统 |
| **缺乏记忆** | 上下文窗口有限 | 搜索/读写文件、RAG 检索 |

**一句话：LLM 是大脑，工具是手和眼睛。**

### 1.2 什么是 Function Calling？

Function Calling（函数调用）是 LLM API 提供的一种能力：**让 LLM 决定何时调用哪个函数，并生成调用参数，而不是直接生成最终回答。**

```
用户: "上海现在气温多少度？"
  ↓
LLM 理解意图 → 决定调用 get_weather(city="上海")
  ↓
返回工具调用请求（不是最终回答）
  ↓
开发者执行函数 → 拿到结果 "25°C"
  ↓
将结果送回 LLM → LLM 综合回答
  ↓
"上海当前气温 25°C，天气晴朗 ☀️"
```

### 1.3 核心两阶段

```
┌─ 阶段 1：工具选择 ─────────────────────┐
│ LLM 根据用户输入和工具描述，决定：       │
│ 1. 是否需要调用工具                    │
│ 2. 调用哪个/哪些工具                   │
│ 3. 传递什么参数                        │
└─────────────────────────────────────────┘
          ↓ 返回函数名 + 参数（JSON）
┌─ 阶段 2：工具执行 ─────────────────────┐
│ 开发者（不是 LLM）实际执行函数：         │
│ 1. 解析 LLM 返回的函数调用请求          │
│ 2. 调用本地/远程函数                   │
│ 3. 将结果返回给 LLM                    │
└─────────────────────────────────────────┘
          ↓ 返回结果 observation
┌─ 阶段 3：综合回答 ─────────────────────┐
│ LLM 结合用户问题 + 工具结果，生成回答    │
└─────────────────────────────────────────┘
```

**关键认识：LLM 不执行函数，只决定调用哪个函数和传什么参数。函数由开发者执行。**

---

## Step 2：核心概念 — 重点深入

### 2.1 OpenAI Function Calling API 详解

#### 2.1.1 基本用法

OpenAI 的 `chat.completions.create` 支持 `tools` 参数：

```python
from openai import OpenAI
client = OpenAI()

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "上海天气怎么样？"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的天气信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，如北京、上海"
                    }
                },
                "required": ["city"]
            }
        }
    }],
    tool_choice="auto"  # auto / required / none / {"type":"function","function":{"name":"xxx"}}
)
```

返回结果中：
- `response.choices[0].message.content` — 如果没调用工具，这里就是回答
- `response.choices[0].message.tool_calls` — 如果要调用工具，这里有调用信息

#### 2.1.2 tool_choice 四种模式

| 模式 | 行为 | 适用场景 |
|------|------|----------|
| `"auto"` | LLM 自行决定是否调用工具 | 通用场景 |
| `"required"` | **必须**调用一个工具 | 测试、强制工具调用 |
| `"none"` | 禁止调用工具 | 纯对话场景 |
| `{"type":"function","function":{"name":"xxx"}}` | **强制**调用指定工具 | 路由、分类任务 |

#### 2.1.3 Tool Call 的数据结构

```python
# LLM 返回的 tool_calls
response.choices[0].message.tool_calls = [
    {
        "id": "call_abc123",        # 唯一标识，用于关联结果
        "type": "function",
        "function": {
            "name": "get_weather",
            "arguments": '{"city": "上海"}'
        }
    },
    # 可以同时有多个 tool_calls（并行调用）
]
```

#### 2.1.4 完整交互流程

```python
# 1. 用户提问
messages = [{"role": "user", "content": "上海和北京的天气分别怎么样？"}]

# 2. LLM 返回工具调用（可以并行调用多个）
# tool_calls: [{name: "get_weather", args: {"city":"上海"}},
#              {name: "get_weather", args: {"city":"北京"}}]

# 3. 开发者执行函数
results = [
    {"city": "上海", "temp": "25°C"},
    {"city": "北京", "temp": "22°C"}
]

# 4. 将工具结果传回 LLM
messages.append(response.choices[0].message)  # assistant 消息（含 tool_calls）
for call, result in zip(tool_calls, results):
    messages.append({
        "role": "tool",
        "tool_call_id": call.id,    # 关联到具体的调用
        "content": json.dumps(result)
    })

# 5. LLM 综合回答
final_response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages
)
# "上海当前25°C，北京22°C，两地温差不大"
```

### 2.2 工具设计最佳实践

#### 2.2.1 工具描述的 Prompt Engineering

**工具描述越精确，LLM 调用越准确。**

| 要素 | 差的描述 | 好的描述 |
|------|----------|----------|
| name | `func1` | `get_current_weather` |
| description | 获取天气 | 获取指定城市的实时天气数据，包括温度、湿度、风力等 |
| parameters | 一个 `city` 字段 | `city` + `unit`（celsius/fahrenheit）+ 可选参数 |
| param desc | 无 | "城市名称，支持中文城市名和拼音" |

**描述中的关键技巧：**
- 描述**何时使用**这个工具："当用户询问天气时使用"
- 描述**参数格式**："日期格式为 YYYY-MM-DD"
- 描述**返回值**："返回包含温度、湿度、风力的 JSON"
- 使用**示例**："例如 city='北京' 返回北京天气"

#### 2.2.2 错误处理

```python
def safe_tool_call(tool_func, **kwargs):
    """安全调用工具，统一错误处理"""
    try:
        result = tool_func(**kwargs)
        return {"status": "success", "data": result}
    except ValueError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"未知错误: {e}"}
```

#### 2.2.3 工具粒度设计

| 粒度 | 示例 | 优点 | 缺点 |
|------|------|------|------|
| **粗粒度** | 一个 `execute_sql` 涵盖所有数据库操作 | 工具数量少 | LLM 难以正确传参 |
| **细粒度** | `search_users`, `create_order`, `delete_record` 分开 | 调用精准 | 工具列表太长 |
| **适中** | 按领域分组 | 平衡 | 需要好分类 |

**推荐：** 每个工具做一件事，且做好。遵循"单一职责原则"。

### 2.3 并行调用（Parallel Tool Call）

OpenAI 支持在一次请求中同时调用多个工具：

```
用户: "帮我查一下北京天气、计算 2+3，再搜一下 AI 新闻"
  ↓
LLM 同时决定调三个工具：
  ├─ get_weather(city="北京")
  ├─ calculator(expr="2+3")
  └─ search_web(query="2025 AI news")
  ↓
开发者并行执行三个函数
  ↓
同时传回结果 → LLM 综合回答
```

**并行调用的好处：**
- 减少 API 往返次数（一次返回，三个结果一起处理）
- 提高响应速度

**注意事项：**
- 工具之间不能有依赖关系（必须独立）
- 返回时需要正确关联每个 `tool_call_id`
- 某些模型（如 GPT-4）支持，但更早期的模型不支持

### 2.4 其他模型的工具调用

| 模型/提供商 | API 名称 | 特点 |
|-------------|----------|------|
| OpenAI | `tools` / `tool_choice` | 最成熟，支持并行 |
| Anthropic Claude | `tools` | 支持，格式略有不同 |
| Google Gemini | `tools` / `function_declarations` | 支持 |
| 本地模型（通过 vLLM） | `tools` | 兼容 OpenAI 格式 |
| DeepSeek | `tools` | 兼容 OpenAI 格式 |

选择建议：**优先使用 OpenAI 格式**，因为大多数开源或兼容服务都支持。

### 2.5 MCP（Model Context Protocol）

Anthropic 推出的开放标准协议，用于**标准化工具调用**。

```
传统方式：每个框架/应用自己定义工具格式
  ┌─────┐    ┌──────────┐
  │ LLM │───→│ 自定义工具 │   ← 不通用，每套系统重新实现
  └─────┘    └──────────┘

MCP 方式：标准化协议
  ┌─────┐    ┌─────┐    ┌──────────┐
  │ LLM │───→│ MCP │───→│ 工具服务器│
  └─────┘    └─────┘    └──────────┘
                │
                └───────→ 数据库、API、文件系统...
```

MCP 的好处：一次实现工具，任何支持 MCP 的 Agent 框架都能用。

---

## Step 3：完整实现 — 多级工具调用实战

实战代码位于 [`projects/03-tool-use/`](/root/xyz-aiagent/projects/03-tool-use/)：

| 文件 | 内容 | 关键点 |
|------|------|--------|
| `step1-basic-function-calling.py` | OpenAI 原生 tools API | 工具定义、分发器、三步流程 |
| `step2-tool-design-patterns.py` | 四种 tool_choice 模式 | 强制调用、并行调用、错误处理、路由 |
| `step3-mcp-style-tools.py` | MCP 风格服务注册 | MCPServer 类、多服务协作、工具发现 |
| `step4-summary.py` | 演进路线 + 面试题 | 最佳实践总结，5 道面试题 |

### 运行方式

```bash
cd /root/xyz-aiagent/projects/03-tool-use
export OPENAI_API_KEY="your-key"
python step1-basic-function-calling.py
python step2-tool-design-patterns.py
python step3-mcp-style-tools.py
python step4-summary.py
```

---

## 🎯 面试题（10 道 — 覆盖基础到架构设计）

### Q1：Function Calling 和纯文本 ReAct 的核心区别是什么？

**要点：**
- **ReAct 文本解析**：LLM 输出自然语言 Action + Action Input，开发者用正则提取，**通用但脆弱**
- **Function Calling**：API 原生返回结构化 JSON（`tool_calls`），**稳定、支持并行、支持 tool_choice 控制**
- FC 是 ReAct 的**工程升级版**：两者逻辑相同（推理→行动→观察），但 FC 将协议层从文本契约升级为 API 契约

**一句话：ReAct 是思想，Function Calling 是其工程落地的最佳实践。**

### Q2：tool_choice 的四种模式分别什么时候用？

| 模式 | 典型场景 |
|------|----------|
| `"auto"` | 绝大多数通用对话场景 |
| `"required"` | 需要每轮都调用工具（如日志审计、路由前置） |
| `"none"` | 纯问答、安全审核阶段 |
| 强制指定 | 确定下一步必须走某个工具（如分类器入口） |

**坑：** `"required"` 会让 LLM 调用一个它觉得最"接近"的工具，如果工具列表中没有合适工具，可能调用一个完全不相关的工具。强制指定则完全由开发者控制。

### Q3：如何实现并行工具调用？有什么限制？

**实现：** 在一次 API 调用中，LLM 返回多个 `tool_calls`，每个有自己的 `id`，开发者并行执行后通过 `tool_call_id` 回传结果。

**限制：**
1. 工具之间**不能有依赖关系**（必须独立）
2. 模型需支持并行调用（GPT-4/GPT-4o 支持，部分旧模型不支持）
3. **部分模型有并行调用数量上限**（如 5-10 个）
4. 并行调用过多可能导致 LLM 搞混参数（测试过 5 个以上时准确率下降）

### Q4：工具描述如何影响调用准确率？怎么优化？

**影响巨大。** 工具描述本质上是**工具的 Prompt Engineering**。

**优化技巧：**
1. **名称**：动词开头 + 名词，如 `search_users` 而非 `func1`
2. **描述**：说清楚"何时用"+"参数怎么填"+"返回什么"，提供示例
3. **参数**：字段名清晰、`description` 写全、用 `enum` 约束可选值
4. **冗余信息**：如果两个工具描述相似，LLM 可能调错，要突出区别

**实验数据（OpenAI 官方研究）：**
- 描述从 1 句改为 3 句 → 准确率提升约 15-20%
- 增加 `enum` 约束 → 参数生成错误减少 30%

### Q5：工具返回错误时，应该直接抛异常还是返回错误消息？

**应该返回结构化错误消息，不要抛异常。**

```python
# ❌ 错误做法：抛异常
def get_weather(city):
    if city not in cities:
        raise ValueError("未知城市")

# ✅ 正确做法：返回错误消息
def get_weather(city):
    if city not in cities:
        return {"status": "error", "error": f"未知城市: {city}"}
    return {"status": "success", "data": ...}
```

**原因：** LLM 需要看到错误内容来决定下一步（重试、换个参数、告诉用户）。抛异常会导致流程中断，LLM 不知道发生了什么。

### Q6：工具粒度应该怎么设计？粗粒度 vs 细粒度的权衡？

| 粒度 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **粗粒度**（一个工具包打天下） | 工具数量少，上下文节省 | 参数复杂，LLM 容易传错 | 内部系统，参数高度可预测 |
| **细粒度**（一个动作一个工具） | 调用精准，每个工具参数简单 | 列表太长，消耗上下文 token | 公开 API，需要高准确率 |
| **适中**（按领域分组） | 平衡 | 需要合理分类 | **推荐大多数场景** |

**经验法则：** 每个工具 3-5 个参数，工具总数控制在 20-30 个以内。

### Q7：MCP 协议解决了什么问题？和普通 Function Calling 什么关系？

**MCP = Model Context Protocol**，由 Anthropic 推出的开放标准。

**解决的问题：**
- **碎片化**：每个框架（LangChain、CrewAI）自定义工具格式
- **不可移植**：为 ReAct 写的工具换个框架不能用
- **动态发现**：传统 FC 需要预定义所有工具，MCP 支持运行时发现

**关系：** MCP 是 Function Calling 的**上层协议标准化**，它不替代 FC，而是在 FC 之上定义了统一的工具发现、调用、错误处理接口。

简单类比：FC 是 HTTP（传输层），MCP 是 REST API（应用层规范）。

### Q8：LLM 如何避免工具调用的死循环？

**工具调用死循环**：LLM 不断调用工具，无限循环下去。

**常见解决方案：**
1. **最大迭代次数限制**（最常用）
   ```python
   MAX_ITERATIONS = 10
   for i in range(MAX_ITERATIONS):
       response = call_llm(...)
       if not response.tool_calls:
           break
   ```
2. **Token 预算控制**：消耗超过一定 token 就终止
3. **结果去重检测**：连续 N 次返回相同/类似结果，判定为循环
4. **任务完成判断**：让 LLM 在每轮输出一个 `is_complete` flag
5. **分阶段设计**：规划阶段和执行阶段分离，不混在一起

### Q9：在多轮对话中，工具调用的结果应该如何管理上下文？

**最佳实践：**
1. **不要保留全部历史** — 工具结果通常很长，历史过多会超上下文
2. **只保留最终结果** — 对于同一工具调用链，只保留最近一次成功调用的结果
3. **摘要压缩** — 用 LLM 对多次工具调用结果做摘要
4. **按时间衰减** — 早于 N 轮的 tool 结果可以丢弃
5. **结构化存储** — 重要的工具结果存入数据库/向量存储，而非硬塞进上下文

**代码示意：**
```python
# 只保留最近 N 轮的工具结果
MAX_TOOL_HISTORY = 3
messages = messages[-MAX_TOOL_HISTORY*2:]  # 保留最近的助手+工具消息
```

### Q10：如何测试和评估工具调用的质量？有哪些指标？

**核心测试方法：**

1. **Unit Test（单元测试）** — 固定输入验证调用结果
   ```python
   # 验证 LLM 在"北京天气"时调用 get_weather(city="北京")
   assert response.tool_calls[0].function.name == "get_weather"
   assert json.loads(response.tool_calls[0].function.arguments)["city"] == "北京"
   ```

2. **E2E 测试** — 完整流程验证（输入→工具调用→执行→回答）

**量化指标：**
| 指标 | 定义 | 目标值 |
|------|------|--------|
| **工具选择准确率** | 该调用时是否调了，不该调时是否没调 | >95% |
| **参数生成准确率** | 生成参数是否完全正确 | >90% |
| **响应速度** | 从输入到完成调用的总耗时 | <3s |
| **无效调用率** | 调用了不存在或不合适的工具 | <5% |
| **重试率** | 首次调用失败需要重试的比例 | <10% |

**工具：** 可用 `langfuse`、`helicone`、`langsmith` 做监控和追踪。

---

## 核心认识

1. **工具描述就是工具的 Prompt Engineering** — 写得好，LLM 调用就准
2. **LLM 只决定"调用什么"，不负责执行** — 函数由开发者实现
3. **tool_choice 是精细控制工具行为的开关** — 四种模式覆盖所有场景
4. **MCP 解决了工具格式碎片化问题** — 一次实现，到处可用
5. **错误处理必须让 LLM 能理解** — 统一格式、不抛异常

---

## 第二阶段进度

| # | 内容 | 状态 |
|---|------|------|
| 1 | Agent 核心设计模式（ReAct、Plan-Execute、Reflection） | ✅ |
| 2 | **工具调用（Function Calling、Tool Use）** | **✅ 本课** |
| 3 | 记忆系统（短期/长期记忆、RAG） | ⏳ 下一课 |
| 4 | 多 Agent 协作 | 待学习 |
| 5 | 动手：完整单 Agent 应用 | 待学习 |
