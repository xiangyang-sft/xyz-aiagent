# 动手：开发一个多 Agent 协作系统

> 第三阶段 · 第 4 节（最后一节）
>
> 目标：从零动手搭建一个完整的、可运行的多 Agent 协作系统，集成编排式 + 协商式 + 层级式三种协作模式，加入监控、安全和评估组件
>
> 前置知识：notes-09 多 Agent 协作（理论篇）、notes-11 Agent 评估、notes-12 Agent 安全、notes-13 生产化部署

---

## Step 1：基础知识 — 从理论到实战的桥梁

### 1.1 我们已经知道什么？

前面的课程已经覆盖了多 Agent 的**全部理论知识**（notes-09）：
- 为什么需要多 Agent（单 Agent 天花板）
- 三种协作模式：编排式、协商式、层级式
- 通信协议：消息传递 vs 黑板模式
- 主流框架对比：AutoGen、CrewAI、LangGraph、MetaGPT 等
- 设计模式：Handoff、Supervisor、Pipeline、Voting

**本节课的目标不是再讲一遍理论，而是动手实现一个真实的多 Agent 协作系统。**

### 1.2 我们要实现什么？

一个**智能开发团队模拟器**（AI Development Team），包含：

```
┌──────────────────────────────────────────────────────┐
│                 🧠 协调者 (Supervisor)                │
│             分解任务 · 分配 · 质量控制 · 汇总          │
└────────────────┬─────────────────────┬───────────────┘
                 │                     │
     ┌───────────┴───────────┐   ┌────┴────┐
     │      Agent 团队        │   │ 评估模块 │
     │  👨‍💻 架构师 Agent       │   │ 代码评审  │
     │  👩‍💻 开发者 Agent       │   │ 测试评估  │
     │  🧪 测试工程师 Agent    │   │ 安全审计  │
     │  🔒 安全审查 Agent      │   └─────────┘
     └───────────┬───────────┘
                 │
     ┌───────────┴───────────┐
     │    监控 & 追踪模块     │
     │  Metrics · Traces · Logs │
     └───────────────────────┘
```

### 1.3 技术选型

| 组件 | 选型 | 原因 |
|------|------|------|
| **LLM API** | OpenAI API (兼容) | 最通用，可替换为 Anthropic/本地 |
| **协作模式** | Supervisor + Pipeline | 兼顾灵活性和可读性 |
| **通信协议** | 结构化消息 + 黑板 | 解耦 Agent 依赖 |
| **评估** | LLM-as-Judge | 之前学过的评估方法 |
| **安全** | 输入/输出过滤 | 之前学过的安全策略 |
| **监控** | JSON 结构化日志 | 之前学过的可观测性 |
| **框架风格** | 纯 Python，不依赖特定框架 | 理解底层原理 |

---

## Step 2：核心概念深入

### 2.1 系统架构全景

#### 分层架构

```
┌──────────────────────────────────────────────────┐
│                  应用层                            │
│  CLI 交互 · 任务输入 · 结果展示                    │
├──────────────────────────────────────────────────┤
│                  编排层                            │
│  Supervisor · 任务分解 · Agent 调度 · 结果聚合    │
├──────────────────────────────────────────────────┤
│                  Agent 层                          │
│  架构师 Agent · 开发者 Agent · 测试 Agent · 安全 Agent │
├──────────────────────────────────────────────────┤
│                  基础设施层                        │
│  消息总线 · 黑板存储 · LLM 调用器 · 缓存          │
├──────────────────────────────────────────────────┤
│                  支撑层                            │
│  评估系统 · 安全过滤 · 监控日志 · 成本追踪        │
└──────────────────────────────────────────────────┘
```

#### 核心数据流

```
用户输入
    │
    ▼
┌─────────────┐    ┌───────────────────┐    ┌────────────────┐
│ 安全过滤     │───▶│ Supervisor 分解任务 │───▶│ 黑板: Task Queue│
└─────────────┘    └───────────────────┘    └───────┬────────┘
                                                    │
            ┌────────────────────────────────────────┘
            ▼
    ┌───────────────┐  返回结果   ┌──────────────────┐
    │ 架构师 Agent   │───────────▶│ 黑板: Results     │
    │ - 系统设计    │            └──────────────────┘
    │ - API 设计    │                       │
    └───────────────┘                       ▼
    ┌───────────────┐            ┌──────────────────┐
    │ 开发者 Agent   │───────────▶│ 质量评估(LLM-as-Judge)│
    │ - 实现代码    │            └──────────────────┘
    │ - 单元测试    │                       │
    └───────────────┘                       ▼
    ┌───────────────┐            ┌──────────────────┐
    │ 测试工程师    │───────────▶│ 安全审计         │
    │ - 集成测试   │            │ - 输入输出检查   │
    │ - 边界条件   │            └──────────────────┘
    └───────────────┘                       │
    ┌───────────────┐                       ▼
    │ 安全审查      │            ┌──────────────────┐
    │ - 安全分析    │───────────▶│ 结果汇总 + 展示  │
    └───────────────┘            └──────────────────┘
                                           │
                                           ▼
                                      ┌─────────────┐
                                      │ 结构化日志    │
                                      │ (监控追踪)    │
                                      └─────────────┘
```

### 2.2 协作模式实现策略

#### 主模式：编排式（Supervisor + Pipeline）

这是系统的主要运作方式：

```
阶段1 (Pipeline 串联):
   架构师 → 开发者 → 测试 → 安全

阶段2 (Supervisor 汇总):
   Supervisor 收集所有输出 → 质量判断 → 要求重做或汇总输出
```

| 阶段 | 触发条件 | 描述 |
|------|---------|------|
| **Planning** | 任务到达 | Supervisor 分析需求，分解为子任务 |
| **Architecture** | Planning 完成 | 架构师 Agent 输出设计文档 |
| **Development** | Design 就绪 | 开发者 Agent 实现代码 |
| **Testing** | Code 完成 | 测试 Agent 运行测试、报告覆盖 |
| **Security** | Test 通过 | 安全 Agent 审查代码安全 |
| **Review** | 全部完成 | Supervisor 审查质量，决定是否重做 |

#### 辅助模式：协商式（Debate）

当出现分歧或需要决策时，触发多 Agent 讨论：

```
问题: "架构选型有争议"
    → 架构师: "建议微服务"
    → 开发者: "单体更简单"
    → 测试: "微服务测试更复杂"
    → 投票/共识 → 最终决策
```

#### 辅助模式：投票式（Voting）

代码评审阶段，多个 Agent 独立评分后取平均：

```
Agent A: 7.5分   Agent B: 8.0分   Agent C: 7.0分
              ↓ 平均
          最终: 7.5分
```

### 2.3 结构化消息协议

```python
@dataclass
class Message:
    msg_id: str          # msg_001, msg_002
    sender: str          # supervisor, architect, developer, tester, security
    receiver: str        # 目标 Agent 名称
    msg_type: str        # task, result, review, debate, vote
    content: dict        # 消息主体
    timestamp: float     # 时间戳
    metadata: dict       # 元信息（成本、Token 数等）
```

### 2.4 黑板数据结构

```python
class Blackboard:
    # 任务队列
    task_queue: List[Task]
    
    # 各 Agent 的工作输出
    artifacts: Dict[str, Any]  # {architect: {...}, developer: {...}, ...}
    
    # 共享上下文
    context: Dict[str, Any]    # 全局信息
```

### 2.5 与之前学过的知识融合

| 之前学过的知识 | 本节的集成方式 |
|---------------|--------------|
| **评估系统 (notes-11)** | LLM-as-Judge 评估代码质量，生成评分报告 |
| **安全过滤 (notes-12)** | 输入 prompt 注入检测 + 输出 PII 过滤 |
| **结构化日志 (notes-13)** | JSON 日志记录每次 Agent 交互和 Token 消耗 |
| **成本追踪 (notes-13)** | 每个步骤记录 Token 消耗，统计总成本 |
| **模型路由 (notes-13)** | 简单任务用小模型，复杂架构设计用强模型 |

---

## Step 3：代码实战

### 项目结构

```
projects/10-multi-agent-system/
├── step1-basic-multi-agent.py       # 基础版：Controller + 3 个 Worker
├── step2-supervisor-pipeline.py     # 进阶版：Supervisor + Pipeline 串联
├── step3-debate-and-voting.py       # 高级版：引入辩论和投票机制
├── step4-full-system.py             # 完整版：集成评估+安全+监控
├── requirements.txt                 # 依赖
└── README.md                        # 项目说明
```

### 通用依赖

```python
# requirements.txt
openai>=1.0.0
python-dotenv>=1.0.0
```

### Step 3.1：基础版 — Controller + Worker

**核心概念：** 一个 Controller 接收用户请求，分解任务，分发给多个 Worker Agent，汇总结果。

**实现要点：**
- Controller 用 LLM 分析用户请求，输出任务分解 JSON
- 每个 Worker Agent 有明确的角色描述（system prompt）
- Worker 独立执行子任务
- Controller 收集所有结果后做汇总

```python
# step1-basic-multi-agent.py 的核心逻辑
class BasicMultiAgentSystem:
    def __init__(self, llm_client, model="gpt-4o-mini"):
        self.llm = llm_client
        self.model = model
        self.agents = {
            "architect": "你是一名资深软件架构师，擅长系统设计和架构决策",
            "developer": "你是一名全栈开发者，擅长编写清晰、高效的代码",
            "tester": "你是一名软件测试工程师，专注于测试策略和质量保障",
        }
    
    def run(self, user_request: str):
        # 1. Controller 分析并分解任务
        plan = self._decompose_task(user_request)
        # 2. 按顺序或并行执行子任务
        results = {}
        for agent_name, subtask in plan["subtasks"].items():
            results[agent_name] = self._execute_agent(agent_name, subtask)
        # 3. 汇总结果
        summary = self._summarize(plan["original_request"], results)
        return summary
```

### Step 3.2：进阶版 — Supervisor + Pipeline

**核心概念：** 引入 Supervisor（监督者），Pipeline 串联各 Agent（架构师→开发者→测试），每个 Agent 的输入是前一个的输出。

**实现的增量：**
1. Supervisor 做更精细的任务分解（含依赖关系）
2. Agent 按 Pipeline 顺序执行，传递上下文
3. Supervisor 做质量控制（验证完整性）
4. 记录每次交互的结构化日志

### Step 3.3：高级版 — 辩论 + 投票机制

**核心概念：** 当任务需要决策或出现分歧时，触发多 Agent 辩论或投票。

**实现的增量：**
1. 辩论模式：两个 Agent 轮流给出观点，第三方仲裁
2. 投票模式：多个 Agent 独立评估，取平均/众数
3. 动态触发：Supervisor 判断是否需要辩论/投票

### Step 3.4：完整版 — 集成评估 + 安全 + 监控

**核心概念：** 把之前三个阶段学到的所有知识融合到这个系统中。

**完整功能清单：**
1. ✅ 多 Agent 协作（编排式 + 协商式 + 投票式）
2. ✅ Supervisor 质量控制（要求重做/改进）
3. ✅ LLM-as-Judge 评估（代码质量、设计合理性）
4. ✅ 安全过滤（输入检测 + 输出过滤）
5. ✅ 结构化 JSON 日志（追踪 + 监控）
6. ✅ 成本追踪（每步 Token + 总成本）
7. ✅ 面试题（10 道 + 参考答案）

---

## 🎯 10 道面试题（含参考答案）

### Q1：如何设计一个多 Agent 协作系统的架构？画出数据流图并解释各模块职责。

**参考答案：**

一个典型的多 Agent 协作系统应有 4 层：

1. **编排层**（Supervisor/Controller）：负责任务分解、Agent 调度、结果聚合、质量控制
2. **执行层**（Specialist Agent）：每个 Agent 有明确的角色和职责边界
3. **通信层**（黑板/消息队列）：Agent 之间不直接通信，通过结构化消息或黑板交换信息
4. **支撑层**（评估/安全/监控）：横切关注点，贯穿整个流程

数据流：用户输入 → 安全过滤 → Supervisor 分解 → 黑板写入任务 → Agent 从黑板读取并执行 → 黑板写入结果 → Supervisor 校验 → 评估打分 → 输出

### Q2：编排式、协商式、层级式三种协作模式各有什么优缺点？如何根据场景选择？

| 模式 | 优点 | 缺点 | 适合场景 |
|------|------|------|----------|
| 编排式 | 结构清晰、易调试 | Controller 可能成为瓶颈 | 有明确流程的任务 |
| 协商式 | 结果可靠、交叉验证 | Token 消耗大 | 需要决策/讨论的场景 |
| 层级式 | 可扩展性好 | 复杂度高、延迟大 | 大型复杂项目 |

**选择原则：** 优先选编排式，遇到需要多方验证的决策点用协商式，规模超大且需要多级管理用层级式。

### Q3：多 Agent 系统中的 "黑板模式" 解决了什么问题？如何实现？

黑板模式解决了 Agent 之间**耦合依赖**的问题。传统点对点通信需要每个 Agent 知道其他 Agent 的地址和接口，黑板模式让所有 Agent 只读写一个共享存储。

**实现方式：**
```python
class Blackboard:
    def __init__(self):
        self.task_queue = deque()
        self.results = {}
        self.context = {}
    
    def add_task(self, task):
        self.task_queue.append(task)
    
    def claim_task(self, agent_name):
        return self.task_queue.popleft() if self.task_queue else None
    
    def publish_result(self, task_id, agent_name, result):
        self.results[task_id] = {"agent": agent_name, "result": result}
```

### Q4：如何处理多 Agent 之间的冲突或不一致？

**四种策略：**

1. **投票机制**：多个 Agent 独立评估，取平均或众数
2. **仲裁者模式**：一个专门的仲裁 Agent 听取双方观点后做决定
3. **分层决策**：冲突升级到更高层级的 Supervisor 处理
4. **辩论迭代**：限制最大轮次，最后一轮强制决策

### Q5：什么是 Agent Handoff？在设计上要注意什么？

Agent Handoff 是一个 Agent 将任务转移给另一个更适合的 Agent。设计要点：

1. **上下文传递**：Handoff 时必须携带完整的上下文，避免信息丢失
2. **回退机制**：目标 Agent 处理失败时能回退给原 Agent 或 Supervisor
3. **循环检测**：防止 A→B→A→B 无限循环
4. **权限控制**：某些 Agent 只能 Handoff 给特定 Agent

### Q6：如何设计多 Agent 系统的消息协议？为什么不能用自然语言直接通信？

自然语言通信的问题：模糊、不结构化、难以自动化处理。

**建议的协议设计：**
```json
{
  "msg_id": "唯一ID",
  "sender": "来源Agent",
  "receiver": "目标Agent",
  "msg_type": "task|result|review|debate|vote|error",
  "content": {},
  "timestamp": "",
  "metadata": {"token_cost": 123, "latency_ms": 500}
}
```

### Q7：多 Agent 系统的 Token 消耗比单 Agent 高出多少？如何优化？

**典型对比：**
- 单 Agent：简单任务的 1x Token
- 多 Agent（3-4个）：3-10x Token（取决于讨论轮次）

**优化策略：**
1. 模型路由：简单子任务用小模型
2. 消息压缩：只传递关键信息，不传递完整历史
3. 缓存复用：相同子任务的结果缓存
4. 并行执行：无依赖的子任务同时执行
5. 限制辩论轮次：最多 2-3 轮

### Q8：如何做多 Agent 系统的质量评估？有哪些维度和指标？

| 维度 | 指标 | 评估方法 |
|------|------|----------|
| 任务完成度 | 子任务完成率 | 检查清单 |
| 输出质量 | 代码质量、设计合理性 | LLM-as-Judge |
| 协作效率 | 交互轮次、Token 消耗 | 日志分析 |
| 一致性 | 多个 Agent 结果是否矛盾 | 冲突检测 |
| 安全性 | 是否包含敏感信息 | 安全过滤器 |

### Q9：如何确保多 Agent 系统不会陷入死循环或无限讨论？

**必备机制：**
1. **最大轮次限制**：任何讨论/辩论不超过 N 轮
2. **超时机制**：每个 Agent 执行有超时
3. **断路器**：连续失败 N 次后触发降级
4. **仲裁突破**：达到最大轮次时强制仲裁
5. **心跳检测**：Agent 无响应时 Supervisor 重新分配

### Q10：在多 Agent 系统中加入安全机制，需要注意哪些事情？

**安全层级：**

1. **输入层**：检测 prompt 注入、恶意指令（notes-12 内容）
2. **通信层**：Agent 之间的消息不暴露敏感信息
3. **输出层**：过滤 PII、敏感代码、安全漏洞（notes-12 内容）
4. **权限层**：不同 Agent 有不同权限，架构师可以看全局，测试只能看代码
5. **审计层**：所有 Agent 交互记录日志，可追溯（notes-13 内容）

---

## 📚 扩展阅读

1. [AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation](https://arxiv.org/abs/2308.08155)
2. [MetaGPT: Meta Programming for Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352)
3. [ChatDev: Communicative Agents for Software Development](https://arxiv.org/abs/2307.07924)
4. [CAMEL: Communicative Agents for "Mind" Exploration](https://arxiv.org/abs/2303.17760)
5. [CrewAI 官方文档](https://docs.crewai.com/)
6. [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
