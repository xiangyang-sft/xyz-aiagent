# 什么是 AI Agent —— 定义、分类与应用场景

> 学习日期：2026-05-29
> 前置知识：LLM 基础、Prompt Engineering

---

## 1. 什么是 AI Agent？

### 1.1 定义

**AI Agent（人工智能智能体）** 是指能够**自主感知环境、做出决策并采取行动**来实现目标的智能系统。

```
感知（Perception）→ 推理（Reasoning）→ 行动（Action）
      ↑                                    │
      └──────── 反馈循环（Feedback Loop）────┘
```

与传统 LLM 的关键区别：

| 维度 | 传统 LLM | AI Agent |
|------|----------|----------|
| **输出** | 一次性生成文本 | 能执行多步行动、调用工具 |
| **记忆** | 无状态（除非提供上下文） | 有状态，能记住和规划 |
| **自主性** | 被动回应用户 | 主动决策、规划、行动 |
| **工具使用** | 不能调用外部工具 | 可调用 API、数据库、网页等 |
| **反馈闭环** | 无 | 观察行动结果并调整后续行为 |

### 1.2 核心能力

一个完整的 AI Agent 通常具备三大核心能力：

```
┌───────────────────────────────────────┐
│              AI Agent                  │
├───────────────────────────────────────┤
│  🧠 推理引擎（LLM / VLM）            │
│     - 理解任务、制定计划              │
│     - 推理、决策                      │
├───────────────────────────────────────┤
│  🛠️ 工具集（Tool Use）               │
│     - 调用 API、执行代码              │
│     - 搜索、计算、读写文件            │
├───────────────────────────────────────┤
│  💾 记忆系统（Memory）               │
│     - 短期记忆（上下文窗口）          │
│     - 长期记忆（外部存储）            │
└───────────────────────────────────────┘
```

---

## 2. Agent 的三大核心组件

### 2.1 🤖 大脑：LLM 推理引擎

这是 Agent 的"思考中枢"，负责：

- **理解目标**：解析用户指令
- **制定计划**：分解为子任务
- **选择行动**：决定下一步做什么
- **评估结果**：判断行动是否成功

当前主流方案：
- GPT-4o / Claude Sonnet 作为高能力推理核心
- 小模型（如 GPT-4o-mini）做简单子任务
- 分层的"主 Agent + 子 Agent"架构

### 2.2 🛠️ 工具：Agent 的"手脚"

工具是 Agent 与外部世界交互的接口。

**常见工具类型**：

| 工具类型 | 示例 | 用途 |
|----------|------|------|
| 搜索 | Web Search、Wikipedia | 获取实时信息 |
| 代码执行 | Python REPL、Jupyter | 计算、数据处理 |
| API 调用 | OpenAPI / REST | 操作外部系统 |
| 数据库 | SQL Query | 查询结构化数据 |
| 文件系统 | 读写文件 | 持久化数据 |
| 浏览器 | 网页导航、截图 | 访问 Web 应用 |
| 通讯 | 发邮件、发消息 | 与人交互 |

**工具调用的标准模式**：

```
Agent 思考：我需要查一下今天的天气
Agent 调用：get_weather(city="北京")
系统返回：{"temperature": 28, "condition": "晴"}
Agent 推理：天气很好，适合出行
Agent 行动：给用户推荐行程
```

### 2.3 💾 记忆：Agent 的"日记本"

记忆分为三个层次：

```
短期记忆（Ephemeral）
  └── 当前对话上下文（就是 LLM 的 context window）
      └── 限制：窗口有限（4K~200K tokens），超出被截断

工作记忆（Working Memory）
  └── 任务进行中的中间状态
      └── 已完成哪些步骤、收集了哪些信息

长期记忆（Persistent Memory）
  └── 跨会话的知识
      └── RAG（向量检索 + 外部存储）
      └── 数据库 / 文件
```

**记忆管理的关键挑战**：
- **遗忘**：上下文窗口满时，哪些信息应该保留？
- **检索**：如何从海量长期记忆中快速找到相关信息？
- **更新**：记忆内容发生变化时如何及时更新？

---

## 3. Agent 的分类

### 3.1 按复杂度分

```
                      ┌──────────────────────┐
                      │  自主学习型 Agent     │
                      │  (Self-Improving)     │
                      └──────────────────────┘
                                 ↑
                      ┌──────────────────────┐
                      │  多 Agent 协作系统     │
                      │  (Multi-Agent)        │
                      └──────────────────────┘
                                 ↑
                      ┌──────────────────────┐
                      │  基于工具的 Agent      │
                      │  (Tool-Using Agent)   │
                      └──────────────────────┘
                                 ↑
                      ┌──────────────────────┐
                      │  简单反应式 Agent      │
                      │  (Simple Reflex)      │
                      └──────────────────────┘
```

**L0 —— 简单反应式 Agent**
- 基于规则或简单 LLM 调用
- 没有记忆、没有规划
- 典型：简单的聊天机器人、IFTTT 式自动化

**L1 —— 基于工具的 Agent**
- 能使用外部工具（搜索、计算、代码）
- 有简单的记忆
- 典型：ChatGPT with Plugins、Claude with Tools

**L2 —— 多 Agent 协作系统**
- 多个 Agent 分工协作
- 有角色分工、任务分配
- 典型：CrewAI、AutoGen、MetaGPT

**L3 —— 自主学习型 Agent**
- 能从经验中学习改进
- 自动迭代优化策略
- 前沿研究阶段

### 3.2 按应用场景分

| 类型 | 描述 | 代表项目 |
|------|------|----------|
| **编程 Agent** | 写代码、修 bug、做 Code Review | GitHub Copilot, Cursor, Devin |
| **研究 Agent** | 收集资料、阅读论文、写报告 | Elicit, Perplexity, 论文 Agent |
| **客服 Agent** | 回答用户问题、处理售后 | 各类客服 Chatbot |
| **自动化 Agent** | 执行重复性工作流 | Zapier, Make, n8n |
| **数据分析 Agent** | 分析数据、做可视化 | ChatGPT Advanced Data Analysis |
| **游戏 Agent** | 玩游戏、游戏 NPC | Voyager（Minecraft） |
| **个人助理 Agent** | 日程管理、邮件处理 | Google Assistant, Siri |

### 3.3 按架构模式分

| 模式 | 描述 | 适用场景 |
|------|------|----------|
| **ReAct** | 推理→行动→观察循环 | 需要多步推理和工具调用的场景 |
| **Plan-Execute** | 先规划再执行 | 复杂任务，需要明确计划 |
| **Reflection** | 自我评估和改进 | 质量敏感场景（代码、写作） |
| **Tool-Use Only** | 仅工具调用，无推理循环 | 简单指令任务 |
| **Multi-Agent** | 多个 Agent 协作 | 复杂项目分工 |

---

## 4. Agent 的典型架构模式

### 4.1 ReAct（Reasoning + Acting）

这是目前最主流的 Agent 模式。

```
循环：
  Step 1: Thought（思考当前状态和下一步）
  Step 2: Action（选择并执行一个行动）
  Step 3: Observation（观察行动结果）
  Step 4: 回到 Step 1，直到任务完成

示例：
  Thought: 我需要知道北京当前的天气
  Action: search("北京天气 2026-05-29")
  Observation: 北京，晴，28°C

  Thought: 找到了天气信息，准备回复用户
  Action: 回复用户
```

**优势**：灵活、可解释、可以处理不确定场景
**劣势**：可能陷入思考循环、token 消耗大

### 4.2 Plan-Execute

先制定完整计划，然后按计划执行。

```
Phase 1: 规划
  → 将任务分解为子任务
  → 确定子任务依赖关系
  → 输出：一个执行计划

Phase 2: 执行
  → 按计划依次执行
  → 出现问题回到 Phase 1 调整计划
  → 输出：最终结果

示例：
  用户：分析公司今年的财务数据

  计划：
  1. 读取财务数据 CSV 文件
  2. 计算关键财务指标（营收、利润、增长率）
  3. 生成可视化图表
  4. 撰写分析报告

  执行 → 第 1 步完成 → 第 2 步完成 → ...
```

**优势**：可预测、适合长期任务
**劣势**：灵活性不如 ReAct、计划可能不完美

### 4.3 Reflection

Agent 对自己的输出做自我评估和修正。

```
过程：
  1. 生成初始输出
  2. 评估输出质量
  3. 如果不够好，修改后重新生成
  4. 重复直到达到标准

示例：
  轮次 1: LLM 生成了一段代码
  评估：这段代码没有处理边界情况
  轮次 2: 修改代码，加入边界检查
  评估：代码完整了，但性能可以优化
  轮次 3: 加入缓存优化
  评估：符合标准 → 输出最终结果
```

**优势**：质量高、适合质量敏感场景
**劣势**：多次 LLM 调用、延迟高

### 4.4 Multi-Agent 协作

多个 Agent 各司其职，像一个团队一样协作。

```
┌───────────────────────────────────────┐
│          Orchestrator Agent            │
│      (任务分配 + 结果整合)             │
└───────────────────────────────────────┘
       │          │           │
       ▼          ▼           ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│ Coding  │ │ Review  │ │ Testing │
│ Agent   │ │ Agent   │ │ Agent   │
└─────────┘ └─────────┘ └─────────┘
```

**常见框架**：
- **CrewAI**：角色化 Agent 团队
- **AutoGen**：可对话的多 Agent 系统
- **MetaGPT**：模拟软件公司的角色分工
- **OpenAI Swarm**：轻量级多 Agent 编排

---

## 5. Agent 的关键挑战

### 5.1 可靠性

| 问题 | 说明 | 缓解方案 |
|------|------|----------|
| **幻觉** | Agent 编造不存在的工具或数据 | 严格的工具定义、输出校验 |
| **循环** | Agent 在思考-行动之间死循环 | 设置最大步骤数、超时机制 |
| **工具误用** | 调用错误的工具或传入错误参数 | 工具 Schema 验证、参数校验 |

### 5.2 安全

- **Prompt Injection**：恶意输入导致 Agent 行为被劫持
- **工具滥用**：Agent 执行危险操作（删文件、改配置）
- **数据泄露**：Agent 将敏感信息写入外部系统

### 5.3 成本与性能

- **Token 消耗**：推理过程消耗大量 tokens
- **延迟**：多步 Agent 的响应时间可能很长
- **LLM 调用次数**：每个步骤都可能调用一次 LLM

---

## 6. 主流 Agent 框架对比

| 框架 | 定位 | 语言 | 亮点 |
|------|------|------|------|
| **LangChain** | 通用 Agent 框架 | Python | 生态最大、工具最多 |
| **AutoGen** | 多 Agent 对话 | Python | 微软出品、Agent 间对话能力 |
| **CrewAI** | 角色化团队 | Python | 简单易用、角色分工清晰 |
| **MetaGPT** | 软件公司模拟 | Python | 模拟真实开发流程 |
| **Dify** | 可视化 Agent | Web UI | 低代码、可视化编排 |
| **OpenAI Agents SDK** | 轻量 Agent | Python | OpenAI 官方、简洁 |
| **Semantic Kernel** | 企业级 Agent | C#/Python | 微软、企业集成 |
| **Coze** | 零代码 Agent | Web UI | 字节跳动、无需编码 |

---

## 7. 实际应用场景

### 场景 1：代码开发助手

```
Dev Agent 的能力：
1. 理解需求 → 生成代码
2. 调用终端 → 运行测试
3. 发现问题 → 修复 bug
4. 提交 PR → Code Review
5. 部署上线 → 监控告警

典型工具：Copilot、Cursor、Devin
```

### 场景 2：客户服务

```
客服 Agent 的能力：
1. 理解用户问题
2. 检索知识库（RAG）
3. 查询订单系统
4. 执行退款/改签操作
5. 升级给人工客服

关键要求：高准确率、可解释性
```

### 场景 3：自动化报告生成

```
报告 Agent 的能力：
1. 连接数据源（DB、API）
2. 分析数据趋势
3. 生成可视化图表
4. 撰写分析报告
5. 发送邮件/推送到群

关键能力：工具调用链 + 代码执行
```

---

## 8. 面试题与参考答案

### 面试题 1：AI Agent 和传统 RPA（机器人流程自动化）有什么区别？

答：两者都是自动化，但核心区别在**智能程度和适应性**：

| 维度 | RPA | AI Agent |
|------|-----|----------|
| **逻辑来源** | 预定义的规则和脚本 | LLM 动态推理 |
| **适应性** | 只能处理"标准流程" | 能处理异常和变化 |
| **输入理解** | 固定格式输入 | 自然语言理解 |
| **学习能力** | 需要人工修改规则 | 可以从经验中学习 |
| **工具使用** | 固定的软件操作 | 动态选择和使用工具 |
| **典型场景** | 数据录入、表单处理 | 智能问答、代码生成 |

简单说：RPA 是"自动化操作手"，Agent 是"有脑子的执行者"。

### 面试题 2：Agent 的"工具使用"是如何实现的？底层原理是什么？

答：工具使用（Function Calling / Tool Use）的实现原理如下：

**1. 工具描述阶段**：
- 每个工具用 JSON Schema 描述：名称、参数、返回值
- 描述和 Prompt 一起被发给 LLM

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的天气信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称"}
                },
                "required": ["city"]
            }
        }
    }
]
```

**2. LLM 选择工具阶段**：
- LLM 输出特殊的结构化响应（不是自然语言）
- 响应格式：`{"tool": "get_weather", "args": {"city": "北京"}}`
- 这被称为"Tool Call"模式

**3. 执行阶段**：
- Agent 框架解析 LLM 的 tool call
- 调用对应的函数/API
- 将结果作为"Observation"返回给 LLM

**4. 推理阶段**：
- LLM 基于工具返回的结果继续推理
- 决定下一步行动或给出最终答案

**底层原理**：
LLM 在训练时被专门训练过产生结构化输出。通过 RLHF 和指令微调，模型学会了在检测到工具定义时，输出格式化的函数调用（而不是自然语言）。这与普通的文本生成共享相同的注意力机制——工具定义在 context 中激活了 model 的"工具调用"行为模式。

### 面试题 3：什么是 ReAct 模式？为什么它比单纯的 Chain-of-Thought 更适合 Agent？

答：ReAct = Reasoning + Acting，由 Yao et al.（ICLR 2023）提出。

**ReAct 的模式**：
```
Thought: 分析当前状态
Action: 执行一个步骤
Observation: 观察结果
Thought: 基于新信息推理...
→ 循环直到任务完成
```

**为什么 ReAct 比纯 CoT 更适合 Agent？**

| 维度 | 纯 Chain-of-Thought | ReAct |
|------|---------------------|-------|
| 信息源 | 仅依赖模型内部知识 | 可以查询外部信息 |
| 幻觉控制 | 容易产生幻觉 | 有外部验证 |
| 行动能力 | 不能执行操作 | 能调用工具 |
| 反馈循环 | 无 | 有 Observation 反馈 |
| 适应性 | 一次性输出 | 动态调整策略 |

**关键差异**：
纯 CoT 是**思考→回答**的单向过程。
ReAct 是**思考→行动→观察→再思考**的闭环过程。

Agent 需要与环境交互——查询数据库、搜索网页、执行代码。CoT 只能"想"，ReAct 能"想"完再"做"。

### 面试题 4：Agent 的"记忆"是如何实现的？短期记忆和长期记忆分别用什么技术？

答：Agent 的记忆系统是分层实现的：

**短期记忆（Short-term Memory）**
- **实现方式**：直接放在 LLM 的 context window 中
- **技术**：
  - 对话历史拼接（Message History）
  - Context Window Management（滑动窗口、token 计数截断）
  - 近期优先：保留最近的 N 轮对话
- **容量**：受模型 context window 限制（4K~200K tokens）

**长期记忆（Long-term Memory）**
- **实现方式**：外部存储 + 检索
- **核心技术**：
  1. **RAG（Retrieval-Augmented Generation）**
     - 文档 → 切分 → Embedding → 向量数据库
     - 检索：用当前 query 的 embedding 做相似度搜索
     - 常见向量库：Chroma, Pinecone, Qdrant, Milvus
     
  2. **结构化存储**
     - SQLite / PostgreSQL 存储结构化记忆
     - 按时间、类别、标签组织
     
  3. **摘要记忆**
     - 定期将历史对话压缩为摘要
     - 存摘要而非原始对话，节省空间

**工作记忆（Working Memory）**
- 正在进行的任务状态
- 模块间的共享数据
- 技术：简单 JSON 对象，每次迭代时读写

```python
# 一个简化的记忆系统示例
class AgentMemory:
    def __init__(self):
        self.short_term = []        # 最近的对话历史
        self.working_memory = {}    # 当前任务状态
        self.vector_store = Chroma()  # 长期记忆
    
    def add_to_short_term(self, message):
        self.short_term.append(message)
        # 超出窗口时，移除最老的消息
        if token_count(self.short_term) > MAX_TOKENS:
            self.summarize_oldest()
    
    def retrieve_long_term(self, query, k=3):
        return self.vector_store.similarity_search(query, k=k)
```

### 面试题 5：如何解决 Agent 陷入死循环的问题？

答：死循环是 Agent 系统中非常常见的 bug，有几种通用解法：

**方案 1：硬限制（必备）**
```python
MAX_STEPS = 20      # 最大执行步数
MAX_TOOL_CALLS = 10  # 最大工具调用次数
TIMEOUT = 300       # 最大执行时间（秒）
```

当达到限制时：终止执行，返回"任务超时"或"已达到最大步数"。

**方案 2：状态去重（Detect Loops）**
- 记录每次 Action 的输入和输出
- 在每次 Action 前检查是否已经执行过相同的（Action, Input）对
- 如果检测到重复，终止或切换策略

**方案 3：多样化策略（Break Symmetry）**
- 当检测到循环时，在 Prompt 中加入"你似乎陷入了循环，请尝试不同的方法"
- 或者切换推理模式（CoT → ReAct → Plain）

**方案 4：人工介入（Human-in-the-Loop）**
- 达到 N 步后，暂停等待用户确认
- 用户可以手动终止或引导

```python
# 检测循环的实用方法
def detect_loop(action_history, threshold=3):
    """检测是否重复执行了相同的操作"""
    recent = action_history[-threshold:]
    if len(recent) < threshold:
        return False
    # 检查最近的几个 action 是否相同
    return all(a == recent[0] for a in recent)
```

### 面试题 6：多 Agent 协作有哪些经典模式？各有什么优劣势？

答：有几种经典的多 Agent 协作模式：

**模式 1：主从式（Orchestrator-Worker）**
```
Orchestrator Agent（分配任务、整合结果）
  ├── Worker Agent 1（子任务 A）
  ├── Worker Agent 2（子任务 B）
  └── Worker Agent 3（子任务 C）
```
✅ 优点：结构清晰、分工明确
❌ 缺点：Orchestrator 是单点瓶颈

**模式 2：辩论式（Debate / Multi-Perspective）**
```
Agent A: 提出方案 → Agent B: 挑战/质疑 → Agent A: 反驳/改进
```
✅ 优点：提升决策质量、减少偏见
❌ 缺点：效率低、成本高

**模式 3：流水线式（Pipeline）**
```
Agent A（输入处理）→ Agent B（分析）→ Agent C（输出格式化）
```
✅ 优点：每个 Agent 任务单一、效果好
❌ 缺点：延迟叠加、错误传播

**模式 4：竞争式（Competition）**
```
多个 Agent 并行独立完成任务
一次投票或评分选最优
```
✅ 优点：可并行、质量有保障
❌ 缺点：成本为 N 倍

**模式 5：市场式（Market / Auction）**
```
任务发布 → Agent 竞标 → 最优 Agent 中标执行
```
✅ 优点：资源利用效率高
❌ 缺点：实现复杂、协调成本高

**实际项目中的建议**：
- 2~3 个 Agent 时用主从式最稳定
- 需要创新时加辩论式
- 流水线式适合处理流程明确的任务

### 面试题 7：如何评估一个 Agent 系统的性能？有哪些指标？

答：Agent 评估是多维度的，需要从不同角度衡量：

**一、任务完成度**
| 指标 | 说明 |
|------|------|
| **成功率** | 任务是否最终完成（Success Rate） |
| **完成质量** | 结果是否符合预期标准 |
| **步骤效率比** | 实际步数 / 最优步数越接近 1 越好 |
| **鲁棒性** | 输入变化时是否仍能完成任务 |

**二、效率**
| 指标 | 说明 |
|------|------|
| **平均步数** | 完成任务平均需要多少步 |
| **平均延迟** | 从开始到完成的总时间 |
| **Token 消耗** | 总输入 + 输出 tokens 数 |
| **LLM 调用次数** | 每次任务调用了多少次 LLM |

**三、可靠性**
| 指标 | 说明 |
|------|------|
| **循环率** | 陷入死循环的比例 |
| **工具错误率** | 工具调用失败的次数 |
| **幻觉率** | 输出中包含虚构信息的比例 |
| **回退率** | 需要人工介入的比例 |

**四、评估方法**

```
单元测试 → 用固定测试集验证每个工具调用
端到端测试 → 完整流程测试
对抗测试 → 故意给模糊或恶意输入
压力测试 → 并发、长任务、大文件
人工评估 → 抽样人工检查结果质量
```

### 面试题 8：Agent 如何决定使用哪个工具？在几十个工具中如何保证选择的准确性？

答：这是生产环境中面临的真实挑战。

**现状**：工具越多，选择准确性越低。经验规律：
```
工具数量与选择准确率的关系：
  3~5 个工具 → 准确率 > 95%
  10~15 个工具 → 准确率 ~ 85%
  30+ 个工具 → 准确率可能低于 70%
```

**优化方案**：

**1. 工具分类 + 路由**
```python
# 将工具分组，先选类别再选工具
tools = {
    "搜索类": [search_web, search_wiki, search_news],
    "数据处理": [read_csv, query_db, run_sql],
    "通讯": [send_email, send_msg, post_slack],
}
# Agent 先决定类别，再选具体工具
```

**2. 工具描述优化**
```
❌ 差：search(query) — 搜索
✅ 好：search_news(keywords, date_from, date_to) — 搜索新闻文章，支持按日期过滤
```

**3. 上下文相关性**
- 将最可能用到的工具排在前面
- 在 Prompt 中加入工具选择提示

**4. 层级过滤**
```
Level 0: 所有工具（比如 50 个）
Level 1: 基于当前任务筛选（如与"搜索"相关的 10 个）
Level 2: 基于当前上下文推荐最合适的 3~5 个
```

**5. 回退机制**
- 如果首次工具选择错误，Agent 可以重试其他工具
- 设置最大重试次数（通常 2-3 次足够）

### 面试题 9：手写一个极简的 Agent 框架（伪代码或 Python）

答：

```python
"""
一个最小化的 Agent 框架实现
"""

import json
from typing import Dict, Any, Callable

class SimpleAgent:
    def __init__(self, llm, tools: Dict[str, Callable]):
        self.llm = llm
        self.tools = tools
        self.messages = []
        self.max_steps = 10
    
    def run(self, task: str) -> str:
        """运行 Agent 完成任务"""
        self.messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": task}
        ]
        
        for step in range(self.max_steps):
            # Step 1: LLM 推理
            response = self.llm.chat(self.messages)
            
            # Step 2: 检查是否已完成
            if response.get("type") == "final_answer":
                return response["answer"]
            
            # Step 3: 执行工具调用
            if response.get("type") == "tool_call":
                tool_name = response["tool"]
                tool_args = response["args"]
                
                if tool_name not in self.tools:
                    result = f"错误：工具 {tool_name} 不存在"
                else:
                    try:
                        result = self.tools[tool_name](**tool_args)
                    except Exception as e:
                        result = f"工具执行错误：{str(e)}"
                
                # Step 4: 将观察结果加入上下文
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": response.get("id"),
                    "content": json.dumps(result)
                })
        
        return "任务超时：已达到最大步数限制"
    
    def _build_system_prompt(self) -> str:
        """构建系统 Prompt"""
        tool_desc = "\n".join([
            f"- {name}: {func.__doc__}"
            for name, func in self.tools.items()
        ])
        
        return f"""你是一个 AI 助手，可以使用以下工具：

{tool_desc}

你的思考过程应遵循以下格式：
1. 需要工具时：{{"type": "tool_call", "tool": "工具名", "args": {{...}}}}
2. 直接回复时：{{"type": "final_answer", "answer": "你的回答"}}

注意：
- 如果工具调用失败，尝试其他方法
- 最多 {self.max_steps} 步完成
- 完成后给出最终答案
"""

# 示例使用
def search_web(query: str) -> str:
    """搜索网络信息"""
    return f"搜索 '{query}' 的结果：...（模拟结果）"

def calculator(expr: str) -> float:
    """执行数学计算"""
    return eval(expr)

agent = SimpleAgent(
    llm=my_llm,
    tools={
        "search": search_web,
        "calculate": calculator
    }
)

result = agent.run("2024 年诺贝尔物理学奖得主是谁？他多大年龄？")
print(result)
```

### 面试题 10：在实际项目中启动一个 Agent 项目，你会如何设计架构？需要考虑哪些因素？

答：启动一个 Agent 项目，我会从以下几个层面思考：

**1. 需求分析**
- 任务类型：单步还是多步？需要多少工具？
- 质量要求：容错率多高？是否需要 100% 准确？
- 实时性：响应时间要求？（毫秒级？秒级？分钟级？）

**2. 技术选型**

| 决策 | 选项 | 选择依据 |
|------|------|----------|
| LLM | GPT-4o / Claude / 开源模型 | 成本 vs 能力 |
| 框架 | LangChain / CrewAI / 自研 | 复杂度 vs 灵活性 |
| 部署 | API / 自部署 vLLM | 延迟与隐私要求 |
| 存储 | 向量库 / 关系型 / 文件 | 记忆需求类型 |
| 监控 | LangSmith / 自建 | 调试与可观测性 |

**3. 架构设计**

```
用户输入
    ↓
[输入预处理] → 提取意图、格式化输入
    ↓
[Agent Core] → 推理循环（ReAct）
    ↓
[工具层] → Search / DB / API / Code
    ↓
[输出处理] → 格式化、校验、安全过滤
    ↓
输出给用户
```

**4. 关键设计决策**

- **错误处理策略**：重试几次？是否降级到人工？
- **记忆管理**：长期记忆的存储结构？检索策略？
- **安全性**：哪些操作需要人工确认？
- **成本控制**：每个任务的 budget 限制？
- **扩展性**：如何添加新的工具和功能？

**5. 分阶段实施**

```
Phase 1 (MVP)：
  → 单 Agent + 3~5 个核心工具
  → 简单 ReAct 循环
  → 无长期记忆

Phase 2 (改进)：
  → 加入 RAG 长期记忆
  → 增加工具数量到 10~15 个
  → 加入错误处理和重试

Phase 3 (成熟)：
  → 多 Agent 协作
  → 监控和评估系统
  → 自动优化和迭代
```

---

## 9. 关键挑战与未来方向

### 当前挑战

1. **可靠性**：Agent 仍然不够可靠，容易出现各种意外
2. **成本**：复杂的推理循环消耗大量 tokens
3. **评估困难**：Agent 的评估比传统 NLP 任务复杂得多
4. **安全性**：Agent 有自主行动能力，风险更大
5. **人机协作**：何时需要人工介入，何时让 Agent 自主

### 未来方向

- **更强大的模型**：更大的 context window、更好的推理能力
- **标准化工具协议**：MCP（Model Context Protocol）统一工具接口
- **Agent 即服务**：Agent 像 API 一样被消费
- **多模态 Agent**：不仅能读文本，还能看、听、说
- **自主学习**：Agent 能持续从经验中改进

---

## 10. 进阶阅读

- [ ] **Paper**: Yao et al., "ReAct: Synergizing Reasoning and Acting in Language Models" (ICLR 2023)
- [ ] **Paper**: Wang et al., "Plan-and-Solve Prompting: Improving Zero-Shot Chain-of-Thought Reasoning by Large Language Models" (2023)
- [ ] **OpenAI Function Calling**: https://platform.openai.com/docs/guides/function-calling
- [ ] **Anthropic Tool Use**: https://docs.anthropic.com/en/docs/build-with-claude/tool-use
- [ ] **MCP 协议**: https://modelcontextprotocol.io/
- [ ] **LangChain Agent 文档**: https://python.langchain.com/docs/modules/agents/
- [ ] **OpenAI Agents SDK**: https://github.com/openai/openai-agents-python

---

> 💡 **下节预告**：学习笔记 04 —— **主流 Agent 框架概览（LangChain、AutoGPT、CrewAI 等）**
