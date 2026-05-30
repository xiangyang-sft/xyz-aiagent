# 主流 Agent 框架概览

> 学习日期：2026-05-30
> 前置知识：AI Agent 定义与架构模式（notes-03-agent-intro.md）

---

## 1. 为什么需要 Agent 框架？

如果只用 LLM API 写 Agent，你得自己处理：
- 工具注册与调用（Function Calling 解析）
- 记忆管理（对话历史、总结、检索）
- 多步推理循环（ReAct、Plan-Execute 等模式）
- 多 Agent 通信与协调
- 可观测性（Logging、Tracing、评估）

**Agent 框架** 就是把这些通用能力封装好，让你专注于业务逻辑。

---

## 2. 框架全景图

当前最主流的 Agent 框架（2026）：

```
单 Agent 场景             多 Agent 场景
│                          │
├─ LangChain ──────────────┼─ LangGraph（LangChain 生态）
├─ Vercel AI SDK           ├─ CrewAI
├─ Coze（字节）             ├─ AutoGen（微软）
├─ Dify（开源低代码）        ├─ Semantic Kernel（微软）
├─ haystack（deepset）      ├─ Agno（前 Phidata）
├─ smolagents（HuggingFace）├─ OpenAI Agents SDK
                           ├─ CAMEL
                           ├─ MetaGPT
                           └─ AutoGPT（经典但已边缘化）
```

> ⚠️ 框架生态变化极快，截至 2026 年中，**LangChain、OpenAI Agents SDK、Coze** 是国内外使用最广泛的三个方向。

---

## 3. LangChain / LangGraph

### 3.1 定位
- **LangChain**：最早上岸的 Agent 框架，提供 Chain、Tool、Memory、Agent 等抽象
- **LangGraph**：LangChain 的续作，基于**有向图（Graph）** 定义 Agent 流程，支持复杂状态机、循环、条件分支

### 3.2 核心概念

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  StateGraph  │ ──→ │    Node      │ ──→ │  Edge/Cond  │
│  (定义状态)   │     │  (执行步骤)   │     │  (路由逻辑)   │
└──────────────┘     └──────────────┘     └──────────────┘
```

**关键抽象：**
| 概念 | 说明 |
|------|------|
| **StateGraph** | 定义整个 Agent 的状态 Schema |
| **Node** | 一个执行步骤（LLM 调用 / 工具执行 / 人类审批） |
| **Edge** | 节点间跳转（条件跳转 / 直接跳转） |
| **ToolNode** | 专门执行工具的节点，自带错误处理 |
| **Checkpointer** | 断点续传、人机交互暂停 |

### 3.3 基本示例（LangGraph）

```python
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI

# 1. 定义图
builder = StateGraph(MessagesState)

# 2. 添加节点
builder.add_node("llm", ChatOpenAI(model="gpt-4").bind_tools(tools))
builder.add_node("tools", ToolNode(tools))

# 3. 定义路由
def should_continue(state):
    if state["messages"][-1].tool_calls:
        return "tools"
    return END

# 4. 连接
builder.add_edge(START, "llm")
builder.add_conditional_edges("llm", should_continue)
builder.add_edge("tools", "llm")

# 5. 编译运行
app = builder.compile()
result = app.invoke({"messages": [("user", "帮我查一下天气")]})
```

### 3.4 优缺点

| 优势 | 劣势 |
|------|------|
| 生态最大，社区最活跃 | 学习曲线陡峭 |
| LangSmith 提供 Tracing/评测 | 抽象多，容易 OOP 过度 |
| 支持复杂流（循环、并行、子图） | 版本变动频繁（v0.1 → v0.3 变化很大） |
| 企业级支持 | Debug 困难（多层抽象堆叠） |

### 3.5 适用场景
- 需要复杂工作流控制的场景
- 团队规模大、需要生产化能力
- 已有 LangChain 技术栈的团队

---

## 4. OpenAI Agents SDK

### 4.1 定位
OpenAI 官方推出的轻量级 Agent 框架，2025 年发布。强调**极简设计**，用三个核心原语覆盖大部分 Agent 需求。

### 4.2 核心概念

```
Agent（一个 LLM + 工具 + 指令）
  │
  ├── Handoffs → 把任务转交给另一个 Agent
  ├── Guardrails → 输入/输出安全检查
  └── Tracing → 内置可观测性
```

**三个核心原语：**
| 概念 | 说明 |
|------|------|
| **Agent** | 一个 LLM 实例 + 系统指令 + 可用工具 |
| **Handoffs** | Agent 之间转交任务（哪个 Agent 合适就给谁） |
| **Guardrails** | 输入验证、输出过滤、安全策略 |

### 4.3 基本示例

```python
from agents import Agent, Runner, function_tool

@function_tool
def get_weather(city: str) -> str:
    """获取城市的天气"""
    return f"{city}：晴，25°C"

agent = Agent(
    name="助手",
    instructions="你是一个友好的助手",
    tools=[get_weather],
)

result = Runner.run_sync(agent, "北京天气怎么样？")
print(result.final_output)
```

**多 Agent 协作（Handoff）：**

```python
triage_agent = Agent(
    name="路由",
    instructions="把用户分流到合适的 Agent",
    handoffs=[english_agent, chinese_agent, billing_agent],
)
```

### 4.4 优缺点

| 优势 | 劣势 |
|------|------|
| 极简 API，几分钟上手 | 生态不如 LangChain 丰富 |
| OpenAI 官方维护，兼容性好 | 依赖 OpenAI API（但可通过兼容 API 适配） |
| 内置 Tracing 非常强大 | 复杂工作流控制不如 LangGraph |
| 原生支持人机交互 | 社区规模较小 |

### 4.5 适用场景
- 快速原型和 MVP
- 简单的单 Agent 或少量 Agent 协作
- 已经使用 OpenAI API 的项目

---

## 5. CrewAI

### 5.1 定位
专注 **多 Agent 协作** 的轻量级框架。设计理念是模拟一个"AI 团队"，每个 Agent 有角色、目标和技能。

### 5.2 核心概念

```
Crew（团队）
  │
  ├── Agent → Role（角色）+ Goal（目标）+ Backstory（背景故事）
  ├── Task → 分配给特定 Agent 的任务
  └── Process → 协作流程（顺序 / 层次）
```

### 5.3 基本示例

```python
from crewai import Agent, Task, Crew, Process

# 定义 Agent
researcher = Agent(
    role="研究员",
    goal="发现关于 AI Agent 的最新趋势",
    backstory="你是一个技术洞察专家，擅长发现前沿技术",
    tools=[search_tool],
)

writer = Agent(
    role="作者",
    goal="撰写清晰的技术博客",
    backstory="你擅长把复杂概念讲得通俗易懂",
)

# 定义任务
research_task = Task(
    description="搜索 AI Agent 的最新框架",
    agent=researcher,
)

write_task = Task(
    description="基于调研结果写一篇博客",
    agent=writer,
)

# 创建团队
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    process=Process.sequential,  # 顺序执行
)
result = crew.kickoff()
```

### 5.4 优缺点

| 优势 | 劣势 |
|------|------|
| 上手极简单，概念直观 | 控制粒度较粗 |
| 模拟"团队协作"体验好 | 复杂逻辑需要 hack |
| 内置角色定义，测试友好 | 性能开销较大 |

### 5.5 适用场景
- 内容创作流水线（研究→写作→审校）
- 多角色协作模拟
- 教育演示和原型

---

## 6. Coze（字节跳动）

### 6.1 定位
**低代码 / 无代码 Agent 平台**，面向非技术人员和快速落地场景。支持拖拽式编排 Bot，也开放 API 给开发者。

### 6.2 核心特性

| 特性 | 说明 |
|------|------|
| **Bot 商店** | 发布和发现现成 Bot |
| **插件系统** | 内置大量工具（搜索、图片、文档等） |
| **知识库** | 上传文档做 RAG，自动切片 |
| **工作流** | 可视化拖拽编排多步流程 |
| **对话记忆** | 内置短期/长期记忆 |
| **发布渠道** | 飞书、微信、网页、API |

### 6.3 优缺点

| 优势 | 劣势 |
|------|------|
| 低代码，非技术人员也能用 | 平台锁定，数据在 Coze 服务器 |
| 插件生态丰富 | 高级定制受限 |
| 国内网络友好 | 海外版（Coze.com）功能不同 |
| 快速验证想法 | 不适合复杂生产环境 |

### 6.4 适用场景
- 快速搭建客服/助手 Bot
- 非技术人员尝试 Agent
- 企业内部轻量自动化

---

## 7. 其他值得关注的框架

| 框架 | 维护方 | 特点 | 适合场景 |
|------|--------|------|----------|
| **AutoGen** | 微软 | 多 Agent 对话式协作，支持人机交互 | 学术研究、多 Agent 对话 |
| **Semantic Kernel** | 微软 | .NET 生态，企业级集成，Azure 深度绑定 | .NET 项目、Azure 用户 |
| **Dify** | 开源社区 | 低代码 LLMOps 平台，可视化，自托管 | 企业自托管 RAG/Agent |
| **Haystack** | deepset | 搜索/RAG 强，Agent 能力在增强 | 搜索增强场景 |
| **smolagents** | HuggingFace | 极简，100 行核心，Code Agent 模式 | 学习研究、小项目 |
| **Agno** (前 Phidata) | 开源社区 | 轻量，面向 Agent 即 API 的设计 | API 驱动的 Agent |
| **CAMEL** | 开源 | 学术框架，研究 Agent 社会行为 | 学术研究 |
| **Vercel AI SDK** | Vercel | 前端友好，Streaming，SSR | Web 应用集成 AI Agent |

---

## 8. 如何选择框架？

```
你的需求是什么？
│
├── 需要快速验证想法？
│   └── → OpenAI Agents SDK / Coze
│
├── 需要复杂的多步工作流？
│   └── → LangGraph
│
├── 需要模拟 AI 团队协作？
│   └── → CrewAI
│
├── 非技术人员，低代码？
│   └── → Coze / Dify
│
├── .NET 技术栈？
│   └── → Semantic Kernel
│
└── 前端应用集成 Agent？
    └── → Vercel AI SDK
```

**通用建议：**
- **学习顺序**：OpenAI Agents SDK → LangGraph → CrewAI（由简入繁）
- **生产选型**：LangGraph（综合最强生态）+ Vercel AI SDK（前端场景）
- **快速落地**：Coze / Dify（国内场景）

---

## 9. Hermes Agent 的定位

我（Hermes Agent）本身也是一个 Agent 框架，但定位不同：

| 对比维度 | LangChain / CrewAI | Hermes Agent |
|---------|-------------------|-------------|
| 使用方式 | Python SDK 集成 | 聊天界面 + 配置文件 |
| 目标用户 | 开发者构建 Agent | 用户使用 Agent |
| 扩展方式 | 写代码 | 写配置 / Skills / 插件 |
| 运行模式 | 程序内运行 | 常驻后台 + 消息驱动 |
| 记忆系统 | 开发者自己实现 | 自带持久化记忆 |
| 工具系统 | 开发者注册 | 配置文件声明 |

Hermes 更像是**框架之上的用户体验层** — 它用 LangGraph 等框架的思想，但不需要用户写代码。

---

## 10. 🎯 面试题

### Q1: 你用过哪些 Agent 框架？对比一下它们的适用场景

**参考答案：**
- **LangGraph**：复杂工作流，比如需要多步推理、条件分支、人机交互的 Agent，用 StateGraph 可以精确控制每一步
- **OpenAI Agents SDK**：快速原型，简单的单 Agent 或 Handoff 协作，API 极其简洁
- **CrewAI**：模拟多角色团队协作的内容生产流水线，概念直观但控制粒度较粗
- **Coze/Dify**：非技术人员或快速验证，拖拽编排
选择依据：**复杂度和控制精度需求** — 越复杂越偏向 LangGraph，越简单越偏向 OpenAI Agents SDK

### Q2: LangGraph 和 LangChain 是什么关系？为什么要学 LangGraph 而不是 LangChain？

**参考答案：**
- LangChain 是最初的框架，提供 Chain、Tool、Agent、Memory 等抽象，但它的 Chain 是线性执行的，**不支持循环和条件分支**
- LangGraph 是 LangChain 团队开发的第二代架构，用**有向图（Graph）** 替代了 Chain，Node 可以自循环（Agent 的 ReAct 循环天然就是图结构），Edge 支持条件跳转
- 结论：**新项目直接用 LangGraph**，LangChain 的 Chain 和 Agent 已被标记为 Legacy

### Q3: 如果让你设计一个自己的 Agent 框架，核心组件有哪些？

**参考答案：**
最少核心组件：
1. **LLM Wrapper** — 统一调用接口（补全、流式、Function Calling）
2. **Tool Registry** — 工具注册、Schema 生成、执行
3. **Memory Store** — 短期（上下文窗口）+ 长期（持久化 + 检索）
4. **Orchestrator** — 推理循环（ReAct / 图执行 / 规划器）
5. **Tracing** — 每一步的输入输出、延迟、Token 消耗

扩展到生产环境再加：
6. **Guardrails** — 输入输出安全过滤
7. **Rate Limiter** — API 限流
8. **Observer** — Metrics，Alerts，Dashboard
9. **Human-in-the-loop** — 关键步骤暂停等待人工确认

### Q4: CrewAI 的多 Agent 和 OpenAI Agents SDK 的 Handoff 有什么区别？

**参考答案：**
- **CrewAI**：所有 Agent 共享同一个上下文，知道彼此的存在，是**协作团队**。流程由 Process 定义（顺序/层次），更像**工作流编排**
- **OpenAI Agents SDK**：Handoff 是**任务转交**，父 Agent 判断当前任务不适合自己时，把 context 转给更专业的子 Agent。子 Agent 完成后再把结果返回。更像是**路由转发**
- 本质区别：共享上下文 vs 上下文隔离；团队协作 vs 路由转发

### Q5: 如果你要在中文互联网环境下选择一个 Agent 平台用于企业落地，你会推荐什么？

**参考答案：**
分场景：
- **已有技术团队**：自托管 LangGraph + 私有化 LLM（DeepSeek / Qwen），数据不出域
- **没有技术团队**：Coze 国内版，低门槛快速上线
- **需要高可定制**：Dify 自托管，开源可控，支持 RAG + Workflow + Agent
- **合规优先**（金融/医疗）：私有化部署，推荐 vLLM + LangGraph，或者使用 Azure OpenAI + Semantic Kernel
关键考量：**数据安全 > 功能丰富度 > 开发成本 > 维护成本**

### Q6: Vercel AI SDK 在 Agent 开发中的定位是什么？和 LangChain 有什么不同？

**参考答案：**
- Vercel AI SDK 定位在**前端集成层**，它关注的是：流式渲染（Streaming）、Server Actions、前后端通信协议（AIStream）
- LangChain 定位在**后端编排层**，关注的是：工具调度、记忆管理、多步推理
- 两者可以互补：Vercel AI SDK 做前端，LangChain 做后端
- 趋势是框架融合，Vercel AI SDK 也开始加入简单的 Tool Use 和 Agent 能力

---

## 11. 📚 延伸阅读

- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [OpenAI Agents SDK 文档](https://openai.github.io/openai-agents-python/)
- [CrewAI 文档](https://docs.crewai.com/)
- [Coze 官方](https://www.coze.cn/)
- [Hermes Agent 文档](https://hermes-agent.nousresearch.com/docs)

---

> 下一节预告：**动手：写一个最简单的 LLM 调用 + 工具使用** 🛠️
