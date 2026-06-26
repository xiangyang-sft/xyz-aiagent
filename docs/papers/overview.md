# 📖 LLM Agent 研究全景概览

> **第四阶段·第2节 | Step 1：论文全景概览**
>
> 本文是 Agent 论文精读的纲领性文档，梳理了 LLM Agent 领域的研究版图、分类体系、8篇精读论文的定位与关联，以及学习方法论。

---

## 一、为什么需要看论文？

经过前三阶段的学习，你已经掌握了：

- LLM 原理（Transformer、Prompt Engineering、Function Calling）
- Agent 核心范式（ReAct、CoT、工具调用、记忆系统、多 Agent 协作）
- 实践能力（最小 Agent、单 Agent 应用、框架对比、评测、安全、部署）
- **自己构建了一个 Agent 框架**（xyz-agent v0.1.0）

**现在看论文，不是为了学怎么用，而是为了学怎么想。**

论文（而不是博客教程）能带来的是：

1. **第一手理解** — 看到原作者的真实动机、实验设计、失败尝试
2. **批判性思维** — 每个方案都有 trade-off，再看现有框架时就知道它做了哪些取舍
3. **研究品味** — 知道什么问题是好问题，什么答案是漂亮答案
4. **面试硬通货** — 大厂面试中，"你读过哪些 Agent 论文？你怎么看？" 是高频题

---

## 二、LLM Agent 研究版图

### 2.1 全景框架

```
┌─────────────────────────────────────────────────────────────────┐
│                    LLM Agent 研究版图                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────┐   ┌──────────────────────────────┐   │
│  │   🧠 推理与规划       │   │   🔧 工具使用与 API          │   │
│  │  ReAct (2022) ★      │   │  Toolformer (2023) ★        │   │
│  │  Tree of Thoughts ★  │   │  Gorilla (2023) ★           │   │
│  │  CoT / Self-Consist  │   │  HuggingGPT (2023)           │   │
│  │  DFSDT / GoT         │   │  API-Bank / ToolBench       │   │
│  └──────────────────────┘   └──────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────┐   ┌──────────────────────────────┐   │
│  │   🔄 反思与自我改进   │   │   🧠 记忆与长期上下文        │   │
│  │  Reflexion (2023) ★  │   │  MemGPT (2023) ★            │   │
│  │  Self-Refine (2023)  │   │  RAG / RALM                 │   │
│  │  CRITIC / RCI        │   │  MemoryBank / ∞-Bench      │   │
│  │  ExpertPrompting     │   │  Recall-Augmented Agents    │   │
│  └──────────────────────┘   └──────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────┐   ┌──────────────────────────────┐   │
│  │   👥 多 Agent 系统    │   │   🌍 具身与持续学习          │   │
│  │  Generative Agents★  │   │  Voyager (2023) ★           │   │
│  │  AutoGen / ChatDev   │   │  SayCan / PaLM-E            │   │
│  │  AgentVerse / CAMEL  │   │  RT-2 / Code as Policies    │   │
│  │  AgentGym / MetaGPT  │   │  GROUND / MineDojo         │   │
│  └──────────────────────┘   └──────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────┐   ┌──────────────────────────────┐   │
│  │   📋 综述与框架       │   │   ⚙️ 评测与基准              │   │
│  │  Lilian Weng·Survey  │   │  AgentBench (2023)          │   │
│  │  Wang et al. Survey  │   │  WebArena (2023)            │   │
│  │  Xi et al. Survey    │   │  SWE-Bench (2024)           │   │
│  │  CoALA (Sumers 2023) │   │  τ-bench / VisualWebArena  │   │
│  └──────────────────────┘   └──────────────────────────────┘   │
│                                                                 │
│              ★ = 本次精读的 8 篇核心论文                          │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 研究演进的脉络

LLM Agent 研究有一条清晰的演进线：

```
2022 ──── 奠基之年
│
├─ ReAct（姚顺宇 等）──── 推理+行动协同，Agent 设计最基本的范式
├─ Chain-of-Thought（魏约翰 等）── 思维链推理的开端
├─ SayCan（Ahn 等）─── LLM 作为机器人任务规划器的先驱
│
2023 ──── 爆发之年
│
├─ 🧠 推理进化
│  └─ Tree of Thoughts（姚顺宇 等）── 树状搜索式推理，打破线性思维
│
├─ 🔧 工具使用
│  ├─ Toolformer（Schick 等）── 自学使用工具，无需人工标注
│  └─ Gorilla（Patil 等）── 大规模 API 调用 + 检索增强
│
├─ 🔄 反思与自我纠错
│  └─ Reflexion（Shinn 等）── Agent 自己评价自己、自己改进自己
│
├─ 🧠 记忆管理
│  └─ MemGPT（Packer 等）── 操作系统级虚拟内存，突破上下文窗口
│
├─ 👥 多 Agent 社会模拟
│  ├─ Generative Agents（Park 等）── 斯坦福小镇，25 个 Agent 的社会生活
│  └─ AutoGen / ChatDev / MetaGPT ── 多 Agent 协作编程
│
├─ 🌍 具身 Agent
│  └─ Voyager（Wang 等）── Minecraft 中终身学习探索
│
└─ 📋 综述井喷
   └─ 多篇系统性综述论文面世，研究版图基本确立

2024 ──── 工程化之年
├─ SWE-Agent / Devin ── 软件开发全流程自动化的 Agent
├─ 评测基准成熟（AgentBench, WebArena, SWE-Bench）
├─ Agent 安全与对齐开始受到重视
└─ 多 Agent 系统走向产品化（GPTs, Copilot, Claude Code）

2025 ──── 融合与增长
├─ Multi-Agent 框架日趋成熟（MCP, ACP, Hermes Agent）
├─ Agent 自我改进循环（Self-Play, Iterative Refinement）
├─ Agent 与工具融合（WebSocket, 实时交互）
└─ Agent 安全性/可靠性成为研究热点
```

### 2.3 论文之间的关联图

```
                    ┌───────────────────┐
                    │    LLM 基础能力    │
                    └────────┬──────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
      ┌────────────┐ ┌────────────┐ ┌────────────┐
      │  CoT 推理   │ │ 指令遵循   │ │ 上下文学习  │
      └──────┬─────┘ └────────────┘ └────────────┘
             │
    ┌────────┼──────────────────────────────────────┐
    │        │                                      │
    ▼        ▼                                      ▼
┌────────┐ ┌────────────────┐              ┌────────────────┐
│  ToT   │ │    ReAct ★     │──────────────│  Toolformer ★  │
└────────┘ │  推理+行动协同  │              └───────┬────────┘
           └───────┬────────┘                      │
                   │                               ▼
                   │                       ┌────────────────┐
                   │                       │   Gorilla ★    │
                   │                       │  API 调用+检索  │
                   │                       └────────────────┘
                   │
     ┌─────────────┼──────────────────────────────┐
     │             │                              │
     ▼             ▼                              ▼
┌──────────┐ ┌────────────┐              ┌────────────────┐
│Reflexion★│ │  MemGPT ★  │              │ Voyager ★      │
│自我反思   │ │ 记忆管理    │              │ Minecraft 探索  │
└──────────┘ └────────────┘              └────────────────┘
                                              │
                                              │
                                              ▼
                                  ┌────────────────────┐
                                  │ Generative Agents★ │
                                  │ 斯坦福小镇·多Agent │
                                  └────────────────────┘
```

> **核心线索**：ReAct 是 Agent 设计的原点，之后的研究从不同维度扩展它——
> - **ToT** 扩展推理深度
> - **Toolformer/Gorilla** 扩展行动范围
> - **Reflexion** 增加自我纠错机制
> - **MemGPT** 扩展记忆容量
> - **Voyager/Generative Agents** 将 Agent 放到复杂环境

---

## 三、8 篇精读论文总览

### 🏆 全景速览表

| # | 论文 | 方向 | 发表 | 作者·机构 | 引用 | 代码 |
|:--|:-----|:----:|:----:|:---------|:----:|:---:|
| 1 | **ReAct** | 🧠 推理 | NeurIPS 2022 | 姚顺宇·Princeton | **2000+** | ✅ |
| 2 | **Tree of Thoughts** | 🧠 推理 | NeurIPS 2023 | 姚顺宇·Princeton | **1500+** | ✅ |
| 3 | **Toolformer** | 🔧 工具 | ICLR 2024 | Schick·Meta AI | **1800+** | ✅ |
| 4 | **Gorilla** | 🔧 工具 | NeurIPS 2023 | Patil·UC Berkeley | **1000+** | ✅ |
| 5 | **Reflexion** | 🔄 反思 | NeurIPS 2023 | Shinn·Northeastern | **1800+** | ✅ |
| 6 | **MemGPT** | 🧠 记忆 | ICLR 2024 | Packer·UC Berkeley | **800+** | ✅ |
| 7 | **Generative Agents** | 👥 多Agent | UIST 2023 | Park·Stanford | **4000+** | ✅ |
| 8 | **Voyager** | 🌍 具身 | NeurIPS 2023 | Wang·NVIDIA | **1000+** | ✅ |

> ⚡ 引用量来自 Google Scholar（截至 2026 年），仅作粗略参考

---

### 1️⃣ ReAct — 推理+行动协同 🔥 奠基之作

| 项目 | 内容 |
|------|------|
| **全称** | ReAct: Synergizing Reasoning and Acting in Language Models |
| **发表** | ICLR 2023（投稿 NeurIPS 2022） |
| **作者** | Shunyu Yao（姚顺宇），Jeffrey Zhao，Dian Yu，Nan Du，Izhak Shafran，Karthik Narasimhan，Yuan Cao |
| **机构** | Princeton University，Google Research |
| **链接** | [arXiv:2210.03629](https://arxiv.org/abs/2210.03629) |
| **代码** | [princeton-nlp/ReAct](https://github.com/princeton-nlp/ReAct) |

**核心思想：**
> 将 **推理（Reasoning）** 与 **行动（Acting）** 交织在一起，而不是分开处理。Agent 在思考的同时与外部环境交互，观察结果又反过来影响推理。

**关键贡献：**
- 提出 **思考-行动-观察**（Thought-Action-Observation）循环范式
- 在 HotpotQA（问答）和 ALFWorld（家居任务）上显著优于仅推理或仅行动的基线
- 相比 CoT，ReAct 能通过外部交互纠正推理中的幻觉
- 首次系统论证了推理链与行动轨迹的协同价值

**对后续影响：** 今天的几乎所有 Agent 框架（AutoGPT、LangChain Agent、Claude Code、Hermes Agent）都基于 ReAct 范式。它是 Agent 的"Hello World"。

---

### 2️⃣ Tree of Thoughts — 树状推理搜索 🌳

| 项目 | 内容 |
|------|------|
| **全称** | Tree of Thoughts: Deliberate Problem Solving with Large Language Models |
| **发表** | NeurIPS 2023 |
| **作者** | Shunyu Yao，Dian Yu，Jeffrey Zhao，Izhak Shafran，Thomas L. Griffiths，Yuan Cao，Karthik Narasimhan |
| **机构** | Princeton University，Google DeepMind |
| **链接** | [arXiv:2305.10601](https://arxiv.org/abs/2305.10601) |
| **代码** | [princeton-nlp/tree-of-thought-llm](https://github.com/princeton-nlp/tree-of-thought-llm) |

**核心思想：**
> CoT 只走一条思维链，ToT 则同时探索多条思维路径，用搜索算法（BFS/DFS）在推理树中导航，用 LLM 自身来评估每个状态的价值。

**关键贡献：**
- 将 LLM 推理从 **线性链** 扩展到 **树状搜索**
- 引入三个核心操作：**思维分解**（怎样拆解问题）、**思维生成**（怎样生成候选）、**状态评估**（怎样评价进展）
- 在 Game of 24、创意写作、Mini Crosswords 上大幅超越 CoT
- 让 LLM 拥有了"推演"和"回溯"能力

**对后续影响：** 开启了 LLM 结合搜索算法的方向（DSFDT、GoT、MCTS-based 推理）。

---

### 3️⃣ Toolformer — 自学使用工具 ⚒️

| 项目 | 内容 |
|------|------|
| **全称** | Toolformer: Language Models Can Teach Themselves to Use Tools |
| **发表** | ICLR 2024 |
| **作者** | Timo Schick，Jane Dwivedi-Yu，Roberto Dessì，Roberta Raileanu，Maria Lomeli，Luke Zettlemoyer，Nicolo Cancedda，Thomas Scialom |
| **机构** | Meta AI（FAIR） |
| **链接** | [arXiv:2302.04761](https://arxiv.org/abs/2302.04761) |
| **代码** | [lucidrains/toolformer-pytorch](https://github.com/lucidrains/toolformer-pytorch) |

**核心思想：**
> 不需要人工标注训练数据，让 LLM **自学** 在什么场景下调用什么工具。模型通过"补全填空"的方式生成带 API 调用的样本，然后用自监督信号筛选优质样本。

**关键贡献：**
- 提出自监督的 **工具学习范式**，无需人工标注
- 支持的 5 种工具：问答系统、计算器、日历、翻译、搜索引擎
- 模型学会了**决定何时调用工具**（不是所有情况都用）
- 保持了原模型的 zero-shot 能力（不退化）

**对后续影响：** 奠定了工具学习的"自学"范式。后续工作（ToolLLM、ToolBench、Gorilla）在此基础上升级，使用更强的方法。

---

### 4️⃣ Gorilla — 大规模 API 调用 🦍

| 项目 | 内容 |
|------|------|
| **全称** | Gorilla: Large Language Model Connected with Massive APIs |
| **发表** | NeurIPS 2023 |
| **作者** | Shishir G. Patil，Tianjun Zhang，Xin Wang，Joseph E. Gonzalez |
| **机构** | UC Berkeley |
| **链接** | [arXiv:2305.15334](https://arxiv.org/abs/2305.15334) |
| **代码** | [ShishirPatil/gorilla](https://github.com/ShishirPatil/gorilla) |

**核心思想：**
> 让 LLM 通过 **检索增强（Retrieval）** 来理解和使用海量 API（TorchHub、TensorHub、HuggingFace 上的 1600+ API），而不是把全部 API 塞进 prompt。

**关键贡献：**
- 提出 **API 检索 + 调用** 的两阶段方法
- 微调了 LLaMA-7B 作为专用模型（APIBench 数据集）
- 比 GPT-4 在 API 调用准确率上高 30%+（零样本时）
- 引入了**文档检索机制**，支持 API 库的动态更新

**对后续影响：** 奠定了"检索增强工具调用"这一范式。MCP（Model Context Protocol）的本质思路与其一脉相承。

---

### 5️⃣ Reflexion — 自我反思与纠错 🔄

| 项目 | 内容 |
|------|------|
| **全称** | Reflexion: Language Agents with Verbal Reinforcement Learning |
| **发表** | NeurIPS 2023 |
| **作者** | Noah Shinn，Federico Cassano，Ashwin Gopinath，Karthik Narasimhan，Shunyu Yao |
| **机构** | Northeastern University，Princeton University |
| **链接** | [arXiv:2303.11366](https://arxiv.org/abs/2303.11366) |
| **代码** | [noahshinn/reflexion](https://github.com/noahshinn/reflexion) |

**核心思想：**
> Agent 执行任务后，**把自己产生的错误转化为自然语言的反思**，存入记忆，下次遇到类似任务时参考。这是用**语言作为强化信号**的独特方法。

**关键贡献：**
- 提出 **Actor-Reflector** 双模块架构
- Agent 不依赖梯度更新就能"学习"—通过反思文本自我改进
- 在决策、推理、编程三类任务上显著提升
- 证明了"告诉 Agent 它哪里错了 + 怎么改"比单纯重试有效得多

**对后续影响：** 开启了"反思型 Agent"这一子方向。Self-Refine、CRITIC 等后续工作都是其变体。也是当前 Agent 框架标配的"自我纠错"功能的理论源头。

---

### 6️⃣ MemGPT — 操作系统级记忆管理 💾

| 项目 | 内容 |
|------|------|
| **全称** | MemGPT: Towards LLMs as Operating Systems |
| **发表** | ICLR 2024 |
| **作者** | Charles Packer，Sarah Wooders，Kevin Lin，Vivian Fang，Shishir G. Patil，Ion Stoica，Joseph E. Gonzalez |
| **机构** | UC Berkeley |
| **链接** | [arXiv:2310.08560](https://arxiv.org/abs/2310.08560) |
| **代码** | [cpacker/MemGPT](https://github.com/cpacker/MemGPT) |

**核心思想：**
> 借鉴操作系统的**虚拟内存**概念，LLM 有"主内存"（有限上下文窗口）+ "外部存储"（数据库），通过**上下文中断和检索**切换两级存储，实现理论上无限的记忆。

**关键贡献：**
- 将 OS 的 **分层存储**（L1 缓存→RAM→磁盘）映射到 Agent 记忆
- 提出 **中断机制**：当 Agent 需要在上下文窗口之外查找信息时，自动触发检索
- 在对话记忆和文档分析任务上超越固定上下文窗口的 GPT-4
- 在 ∞-Bench 测试中处理超过百万 token 的上下文

**对后续影响：** 突破了 LLM 上下文窗口的限制，为长期对话 Agent 和持续学习提供了架构模板。

---

### 7️⃣ Generative Agents — 斯坦福小镇 🏘️

| 项目 | 内容 |
|------|------|
| **全称** | Generative Agents: Interactive Simulacra of Human Behavior |
| **发表** | UIST 2023（Best Paper Award） |
| **作者** | Joon Sung Park，Joseph C. O'Brien，Carrie J. Cai，Meredith Ringel Morris，Percy Liang，Michael S. Bernstein |
| **机构** | Stanford University，Google Research |
| **链接** | [arXiv:2304.03442](https://arxiv.org/abs/2304.03442) |
| **代码** | [joonspk-research/generative_agents](https://arxiv.org/abs/2304.03442) |

**核心思想：**
> 在一个小镇模拟环境中，25 个 Agent 各自拥有独特的性格和记忆，独立规划日常生活，彼此社交互动，甚至自发组织活动（如情人节派对）——**所有行为都不是预设脚本，而是 Agent 自主涌现的**。

**关键贡献：**
- 提出 Agent 的核心架构：**记忆流（Memory Stream）→ 反思（Reflection）→ 规划（Planning）**
- 记忆有时间衰减和重要性评分，决定了什么被记住、什么被遗忘
- 高级反思：Agent 能从大量观察中提炼出抽象结论（"我经常去咖啡店"→"我喜欢咖啡"）
- 计划被递归分解为：日常活动 → 小时级安排 → 具体行动
- 25 个 Agent 同时运行时涌现了可验证的社会行为

**对后续影响：** 引发了 Agent 社会模拟研究热潮。这也是"多 Agent 系统"中最具影响力的论文之一。

---

### 8️⃣ Voyager — 终身学习 Minecraft Agent 🌍

| 项目 | 内容 |
|------|------|
| **全称** | Voyager: An Open-Ended Embodied Agent with Large Language Models |
| **发表** | NeurIPS 2023 |
| **作者** | Guanzhi Wang，Yuqi Xie，Yunfan Jiang，Ajay Mandlekar，Chaowei Xiao，Yuke Zhu，Linus Fan，Anima Anandkumar |
| **机构** | NVIDIA，Caltech，UT Austin，UIUC |
| **链接** | [arXiv:2305.16291](https://arxiv.org/abs/2305.16291) |
| **代码** | [MineDojo/Voyager](https://github.com/MineDojo/Voyager) |

**核心思想：**
> 在 Minecraft 中打造一个能**持续自主探索、习得新技能、永不遗忘**的 Agent。Voyager 自动发现新任务、自主编写代码技能、将技能存入永久技能库。

**关键贡献：**
- 三大模块：**自动课程（Automatic Curriculum）**+ **技能库（Skill Library）**+ **迭代反馈（Iterative Prompting）**
- Agent 自动发现自己的"最近发展区"（自动课程），不会太简单也不会太难
- 技能用 JavaScript 代码保存，可以组合和复用
- 全自动运行，无需人类干预
- 在 Minecraft 中获得了 3.3× 更多的物品、解锁了 15× 更多的科技树节点

**对后续影响：** 展示了终身学习 Agent 的完整蓝图。技能库+自动课程的设计被后续很多 Agent 框架借鉴。

---

## 四、研究方法论

### 4.1 每篇论文的精读框架

对于这 8 篇论文，每篇会按以下框架精读：

```
1. 📋 基本信息          — 作者、机构、发表、引文
2. 🎯 动机与研究问题     — 作者想解决什么痛点
3. 💡 核心方法          — 怎么做的（关键算法/架构）
4. 🔬 实验设计          — 评估了什么、怎么评估的
5. 📊 关键结果          — 数据说话、消融实验
6. ⚖️ 局限与讨论        — 哪些没做好、哪些可以改进
7. 🔗 与 xyz-agent 的关系 — 对我们自己框架的启发
8. 💭 我的思考          — 批判性分析、延伸想法
```

### 4.2 学习顺序建议

```
Step 1 ── 全景概览（本文） ← 你在这里
              │
              ▼
Step 2a ── ReAct → ToT → Toolformer → Gorilla
          (推理奠基) (推理扩展)  (工具自学)  (大规模API)
              │
              ▼
Step 2b ── Reflexion → MemGPT → Generative Agents → Voyager
          (自我反思)  (记忆管理)   (多Agent社会)      (终身学习)
              │
              ▼
Step 3 ── 深度对比与转化
          (对比表 + 关联图 + 面试题 + 与xyz-agent对照)
```

### 4.3 阅读建议

- **先看原文**，再看解读（包括本文的解读也建议作为辅助）
- **带着问题读**：这篇论文解决什么问题？我有没有遇到过类似问题？
- **做结构化笔记**：使用上面的框架
- **代码也看看**：有条件的话运行一下官方 demo
- **与现实对照**：读完后看看你平时用的 Agent 框架中哪些设计来自这篇论文

---

## 五、与 xyz-agent 的对照

你构建的 xyz-agent v0.1.0 已经具备了多项论文中的核心思想：

| xyz-agent 模块 | 对应的论文 | 设计灵感 |
|:--------------|:----------|:---------|
| `engine.py`（ReAct 循环） | **ReAct** | 思考→行动→观察的三大步循环 |
| `orchestrator.py`（多 Agent 编排） | **Generative Agents** | 多 Agent 社会协作 |
| `memory.py`（短期+长期→RAG） | **MemGPT** | 分层记忆管理 |
| `tool.py`（工具注册表 → MCP） | **Toolformer + Gorilla** | 工具注册+检索调用 |
| 可扩展的反思/纠错 | **Reflexion** | 未来可以加 |

> 精读完后，你将能**有理有据地改造 xyz-agent**，比如：
> - 加入 Tree of Thoughts 式的多路径推理
> - 实现 Reflexion 式的自我反思循环
> - 加入 Voyager 式的技能库 + 自动课程

---

## 六、参考文献

1. Yao et al. *ReAct: Synergizing Reasoning and Acting in Language Models*. ICLR 2023. [arXiv:2210.03629](https://arxiv.org/abs/2210.03629)
2. Yao et al. *Tree of Thoughts: Deliberate Problem Solving with Large Language Models*. NeurIPS 2023. [arXiv:2305.10601](https://arxiv.org/abs/2305.10601)
3. Schick et al. *Toolformer: Language Models Can Teach Themselves to Use Tools*. ICLR 2024. [arXiv:2302.04761](https://arxiv.org/abs/2302.04761)
4. Patil et al. *Gorilla: Large Language Model Connected with Massive APIs*. NeurIPS 2023. [arXiv:2305.15334](https://arxiv.org/abs/2305.15334)
5. Shinn et al. *Reflexion: Language Agents with Verbal Reinforcement Learning*. NeurIPS 2023. [arXiv:2303.11366](https://arxiv.org/abs/2303.11366)
6. Packer et al. *MemGPT: Towards LLMs as Operating Systems*. ICLR 2024. [arXiv:2310.08560](https://arxiv.org/abs/2310.08560)
7. Park et al. *Generative Agents: Interactive Simulacra of Human Behavior*. UIST 2023. [arXiv:2304.03442](https://arxiv.org/abs/2304.03442)
8. Wang et al. *Voyager: An Open-Ended Embodied Agent with Large Language Models*. NeurIPS 2023. [arXiv:2305.16291](https://arxiv.org/abs/2305.16291)

**综述类：**
- Weng, Lilian. *LLM-powered Autonomous Agents*. 2023. [lilianweng.github.io](https://lilianweng.github.io/posts/2023-06-23-agent/)
- Wang et al. *A Survey on Large Language Model based Autonomous Agents*. arXiv:2308.11432
- Xi et al. *The Rise and Potential of Large Language Model Based Agents: A Survey*. arXiv:2309.07864
- Sumers et al. *Cognitive Architectures for Language Agents*. arXiv:2309.02427 (CoALA)

---

> 📝 **下一步**：Step 2a — 精读论文 #1 **ReAct**，深入研究推理+行动协同的经典范式！
