# 🌳 Tree of Thoughts: Deliberate Problem Solving with Large Language Models

> **第四阶段·第2节 | Step 2a-2：Tree of Thoughts 论文精读**
>
> 精读日期：2026-07-27 | 论文版本：v2（最后更新 2023-12-03）

---

## 1. 📋 基本信息

| 项目 | 内容 |
|------|------|
| **全称** | Tree of Thoughts: Deliberate Problem Solving with Large Language Models |
| **发表** | NeurIPS 2023 |
| **作者** | Shunyu Yao（姚顺宇），Dian Yu，Jeffrey Zhao，Izhak Shafran，Thomas L. Griffiths，Yuan Cao，Karthik Narasimhan |
| **机构** | Princeton University，Google DeepMind |
| **链接** | [arXiv:2305.10601](https://arxiv.org/abs/2305.10601) |
| **代码** | [princeton-nlp/tree-of-thought-llm](https://github.com/princeton-nlp/tree-of-thought-llm) |
| **引用** | 1500+（截至 2026） |

---

## 2. 🎯 动机与研究问题

### 2.1 要解决什么问题？

**核心问题：** LLM 的自回归生成机制是「token 级别、从左到右」的决策过程——每一步只选一个 token，没有回溯、没有多路径探索。这种「一根筋」的推理方式在需要探索、战略预判、或初始决策至关重要的任务上会失败。

### 2.2 为什么这个问题重要？

论文从**双系统理论（Dual Process Theory）**切入（Kahneman 的 System 1 / System 2）：
- **System 1**：快、自动、无意识——LLM 的 token 级生成就是 System 1
- **System 2**：慢、深思熟虑、有意识——需要规划、搜索、回溯

LLM 当前的推理方法只用了 System 1，缺乏 System 2 的深思熟虑。ToT 的目标就是给 LLM 加上 System 2 能力。

### 2.3 现有方法的局限

| 方法 | 描述 | 局限 |
|:----|:-----|:-----|
| **IO Prompting** | 输入→输出，一步到位 | 没有中间推理步骤 |
| **Chain-of-Thought (CoT)** | 线性链式推理 | ① 只有一条路径，没有分支探索 ② 没有回溯 ③ token 级局部决策 |
| **CoT-SC (Self-Consistency)** | 多条 CoT 链取多数 | 多条链之间**彼此独立**，无法相互影响或修正 |

> 💡 **核心洞察**：CoT 虽然引入了中间步骤，但仍然是**线性**的。真正的解题过程需要像人类一样——同时考虑多条可能路径，不行就回溯。

---

## 3. 💡 核心方法

### 3.1 总体思想

ToT 将 LLM 推理从**线性链**扩展为**树状搜索**。每个节点是一个「思维」（thought）——一段有意义的中间文本。用搜索算法（BFS/DFS）在这棵思维树中导航，用 LLM 自身来评估每个状态的价值。

> **一句话概括**：ToT = **思维分解 × 思维生成 × 状态评估 × 树搜索**

### 3.2 四大核心设计问题

论文提出 ToT 的实例化需要回答 4 个问题：

```
┌────────────────────────────────────────────────────┐
│                  Tree of Thoughts                    │
│                                                      │
│  Q1: 思维分解 (Thought Decomposition)                │
│  └── 怎样将问题拆解为中间思维步骤？                   │
│                                                      │
│  Q2: 思维生成 (Thought Generation)                    │
│  └── 从一个状态出发，怎样生成候选思维？               │
│      ├─ 采样法 (Sample): 从 LM 多次采样             │
│      └─ 提议法 (Propose): 让 LM 一次提议多个候选      │
│                                                      │
│  Q3: 状态评估 (State Evaluation)                      │
│  └── 怎样评价一个状态距离目标有多近？                 │
│      ├─ 标量值法 (Value): 给 1-10 评分               │
│      └─ 投票法 (Vote): 让 LM 在多条路径中投票选最佳   │
│                                                      │
│  Q4: 搜索算法 (Search Algorithm)                      │
│  └── 用什么策略遍历思维树？                           │
│      ├─ BFS (广度优先): 每层保留 b 个最佳节点         │
│      └─ DFS (深度优先): 一条路走到黑，不行就回溯      │
└────────────────────────────────────────────────────┘
```

### 3.3 三大核心操作的深入理解

#### ① 思维分解（Thought Decomposition）

将复杂问题拆解为一系列中间思维步骤，每个思维是比 token 更高层级的语义单元：

| 任务 | 思维粒度 | 步数 |
|:----|:---------|:----:|
| Game of 24 | 一个中间等式（如 `13-9=4 (left: 4,4,10)`） | 3 步 |
| Creative Writing | 一个写作计划段落 | 1 步（2 层深度） |
| Mini Crosswords | 一个单词填词（如 `h2.motor`） | 最多 10 步 |

> **关键洞察**：思维粒度的选择直接影响搜索空间的大小——粒度太细（token 级）组合爆炸，粒度太粗（整段输出）又失去搜索意义。

#### ② 思维生成（Thought Generation）

从当前状态 `s = [x, z₁...i]` 生成下一个思维候选：

**采样法（Sample）**：
```
对当前状态 s，从 LLM 独立采样 k 个完整思维 z⁽¹⁾, z⁽²⁾, ..., z⁽ᵏ⁾
适用场景：思维空间丰富、多样化重要（如 Game of 24）
```

**提议法（Propose）**：
```
让 LLM 一次提议 k 个候选思维
提示模板："Suggest 3 different next steps: 
1. ...  2. ...  3. ..."
适用场景：思维空间受限、可以穷举（如 Mini Crosswords）
```

#### ③ 状态评估（State Evaluation）

**标量值法（Value）**：
```
给状态 s 打分 1-10
prompt: "Evaluate the progress toward solving the problem on a scale 1-10."
取 5 次评分的平均值（标准差约 ±0.56）
用途：BFS 中剪枝，保留高分节点
```

**投票法（Vote）**：
```
让 LLM 在多个候选状态中投票选最佳
prompt: "Analyze choices below, then conclude which is most promising."
采样 5 次投票，取多数
用途：Creative Writing 这种开放式任务，评分标准模糊时
```

> **这是 ToT 最具创新性的点**：用 LLM 自己来提供搜索启发式（heuristic），而不是像传统搜索算法那样硬编码或外部学习。

#### ④ 搜索算法（Search Algorithm）

**广度优先搜索（BFS）**：

```
Step 1: 从根节点（输入 x）出发
Step 2: 生成所有第一层候选思维
Step 3: 评估每个候选，保留 b 个最佳
Step 4: 对保留的 b 个节点，分别生成下一层候选
Step 5: 重复直到达到最大深度或找到解
```

参数 `b`（branching factor）控制每层保留的候选数量——`b=1` 退化为 CoT-like 搜索，`b=5` 是论文中 Game of 24 的主要配置。

**深度优先搜索（DFS）**：

```
Step 1: 从根节点出发
Step 2: 评估当前最优的下一个候选思维
Step 3: 如果无法继续（剪枝），回溯到父节点，尝试下一个候选
Step 4: 重复直到找到解或超过最大步数限制（100 步）
```

DFS 用于 Mini Crosswords，因为搜索空间大、深度可变的场景。

### 3.4 与 CoT 的直观对比

```
CoT (Chain of Thought):
┌──────────────────────────────┐
│ Input → Thought1 → Thought2 → Output  ← 只有一条线
└──────────────────────────────┘

ToT (Tree of Thoughts):
         ┌── Thought1a ──┐
         │               ├── Thought2a ──→ Output A
Input ───┼── Thought1b ──┤              ← 多路径探索
         │               ├── Thought2b ──→ Output B
         └── Thought1c ──┘
              ↑ 可回溯          ↑ 可剪枝
```

---

## 4. 🔬 实验设计

### 4.1 实验概览

论文设计了**三个全新任务**，每个任务考验 LLM 的不同推理能力：

| 任务 | 能力要求 | 搜索难度 | 评估指标 |
|:----|:---------|:--------:|:---------|
| **Game of 24** | 演绎推理、数学 | 浅（3 步） | 成功率（100 局） |
| **Creative Writing** | 常识、创意、规划 | 浅（2 步） | GPT-4 评分 + 人工评判 |
| **Mini Crosswords** | 词汇推理、约束满足 | 深（≤10 步） | 字母/单词/整局正确率 |

所有实验使用 GPT-4（Chat Completion 模式），temperature=0.7，实验时间 2023 年 5 月 5-16 日。

### 4.2 Game of 24 — 数学推理

**任务描述：** 给定 4 个数字，用四则运算（+-*/）让它们等于 24，每个数字恰好用一次。

**数据集：** 从 4nums.com 抓取 1,362 个游戏，用较难的 901-1,000 号共 100 局测试。

**ToT 配置：**
- 思维分解：3 步中间等式（每次取两个数运算）
- 思维生成：采样法，k=5
- 状态评估：标量值法（1-10）
- 搜索算法：BFS，b=1 或 b=5

**消融实验变体：**
- `+prune`（默认）：保留评分 > 某个阈值的节点
- `+backtrack`（默认）：评分低时回溯到父节点
- IO+Refine：IO 输出 + 最多 10 轮迭代纠错（使用 groundtruth 反馈）

**结果：**

| 方法 | 成功率 |
|:----|:------:|
| IO Prompting | 7.3% |
| CoT Prompting | 4.0% |
| CoT-SC (k=100) | 9.0% |
| ToT (b=1) | **45%** |
| ToT (b=5) | **74%** |
| IO + Refine (k=10) | 27% |
| IO (best of 100) | 33% |
| CoT (best of 100) | 49% |

> 🔥 **最惊艳的结果**：GPT-4 + CoT 只有 4%，而 ToT（b=5）达到了 **74%**，提升了 18.5 倍！

**消融分析：**
- `b=1`（每层只保留 1 个）就有 45%，说明即使不并行探索，ToT 的自我评估+搜索结构也能大幅提升
- IO+Refine 有 groundtruth 反馈才 27%，远低于 ToT 无反馈的 74%
- **错误分析**：ToT 的错误主要集中在数值计算错误（~60%），而 CoT 的错误更多是推理路径错误

### 4.3 Creative Writing — 创意写作

**任务描述：** 输入 4 个随机句子，输出 4 段连贯文章，每段分别以这 4 个句子结尾。

**数据集：** 从 randomwordgenerator.com 随机生成 100 组输入句子。

**评估方式（两种）：**
1. **GPT-4 自动评分**：零样本提示 GPT-4 给 1-10 分（取 5 次平均）
2. **人工评判**：盲测比较 CoT vs ToT 生成的文章对

**ToT 配置：**
- 深度 2 层（仅 1 个中间步骤）
- 第一层：生成 k=5 个写作计划，投票选最佳
- 第二层：基于最佳计划写 k=5 个段落，投票选最佳
- BFS + 投票法（因为评分标准模糊，不适合用标量值）

**结果：**

| 方法 | GPT-4 平均分（1-10） | 人类偏好 |
|:----|:-------------------:|:--------:|
| IO | 6.19 | — |
| CoT | 6.93 | 21% 偏好 |
| ToT | **7.56** | **41% 偏好** |
| IO+Refine | 7.67 | — |
| ToT+Refine | **7.91** | — |

> 人类评判中，ToT 明显优于 CoT（41% vs 21%，其余 38% 认为相当）。有趣的是，迭代纠错（Refine）在这种开放式任务中也很有效。

### 4.4 Mini Crosswords — 迷你填字游戏

**任务描述：** 5×5 填字游戏，给定 5 个横向提示和 5 个纵向提示，填入 25 个字母。

**数据集：** 从 GooBix 抓取 156 局，用 20 局测试（按 1, 6, 11, ... 等间隔抽样）。

**ToT 配置：**
- 思维分解：每次填一个单词（5 横 + 5 纵，最多 10 步）
- 思维生成：提议法 + 置信度排序，k=5
- 状态评估：检查每个未填位置是否"可能"填（不可行则剪枝）
- 搜索算法：DFS，最多 100 步

**结果：**

| 方法 | 字母正确率 | 单词正确率 | 整局通过率 |
|:----|:---------:|:---------:|:---------:|
| IO | 38.7% | 14% | 0/20 |
| CoT | 40.6% | 15.6% | 1/20 |
| ToT | **78%** | **60%** | **4/20** |
| ToT + best state | **82.4%** | **67.5%** | **7/20**（oracle） |
| ToT - prune | 65.4% | 41.5% | 1/20（但找到了 4 个解） |
| ToT - backtrack | 54.6% | 20% | 1/20 |

**消融分析：**
- `+best state`（oracle 最佳状态）：能解 7/20，说明输出策略可改进
- `-prune`（去掉剪枝）：解了 4 个，其中 3 个是 +prune 版本解不了的——剪枝虽高效但有时会误杀正确路径
- `-backtrack`（去掉回溯）：大幅退化（20% → 54.6%），证明回溯在 ToT 中的关键作用

---

## 5. 📊 关键结果

### 5.1 三个任务的统一结论

| 任务 | CoT | ToT | 提升幅度 |
|:----|:---:|:---:|:--------:|
| Game of 24（成功率） | 4% | **74%** | **18.5×** |
| Creative Writing（GPT-4 评分） | 6.93 | **7.56** | +0.63 |
| Mini Crosswords（单词正确率） | 15.6% | **60%** | **3.8×** |

### 5.2 核心发现

1. **搜索 > 采样**：ToT 的搜索策略（即使 b=1）远超多次独立采样（best of 100）
2. **自我评估有效**：LLM 自己评估自己的推理路径是一个可行且强大的启发式
3. **回溯是关键**：在 Mini Crosswords 中去掉回溯后性能大幅下降
4. **剪枝是把双刃剑**：既能大大缩小搜索空间，也可能剪掉正确路径
5. **ToT + Refine 可叠加**：在 Creative Writing 上，两种方法联用效果最好（7.91）

### 5.3 误差分析

**Game of 24 的错误分布（ToT 失败的 26%）：**
- ~60% 是数值计算错误（如 `13/2 = 6.5` 这种 LLM 不擅长的精确运算）
- ~40% 是规划/搜索错误（虽然 ToT 比 CoT 已大幅减少）

> 💡 启示：ToT 不能解决 LLM 的**基础能力缺陷**（如数值计算），但能**大幅减少推理路径错误**。

---

## 6. ⚖️ 局限与讨论

### 6.1 明显局限

| 局限 | 说明 |
|:----|:------|
| **计算成本高** | ToT 比 CoT 需要更多 API 调用（Game of 24 中约 5-20× 成本），论文在 Appendix B.3 中详细分析了成本-性能权衡 |
| **任务范围有限** | 仅验证了 3 个相对简单的任务，对 GPT-4 已擅长的任务（常识问答、翻译等）没有必要用 ToT |
| **思维分解依赖人工设计** | 每个任务的思维粒度和格式需要人工设计，不是自动的 |
| **评估器不可靠** | LLM 自我评估的准确性有限（如 Crossword 中剪枝误判 "agend" 为错误） |
| **无法修正 LLM 的基础能力缺陷** | 如果 LLM 本身算不对 13/2，搜索也救不了 |

### 6.2 对实验结果的外部有效性

- 实验使用 GPT-4（2023 年 5 月版本），当时是最先进的模型但不是最新的
- Mini Crosswords 的剪枝器误判了一些罕见单词（"agend" 被误认为拼写错误），说明 LM 知识边界会影响搜索质量

### 6.3 作者自己的反思

> "Deliberate search such as ToT might not be necessary for many existing tasks that GPT-4 already excels at."

> "This work focuses on using an off-the-shelf LM, and fine-tuning LMs using a ToT-style high-level counterfactual decision making might present opportunities to enhance the problem-solving capabilities."

**这意味着：**
- ToT 不是万能的，只适合需要规划/搜索的复杂任务
- 未来方向：把 ToT 的搜索过程**蒸馏回模型权重**，让模型在推理时自动（隐性）做树搜索

### 6.4 后续发展方向

论文结尾提出的三条路：
1. **微调 LLM**：用 ToT 生成的推理轨迹微调模型，让模型学会"隐性树搜索"
2. **降低计算成本**：利用开源模型压缩（如 LLaMA），让 ToT 变得更实用
3. **扩展到更复杂的真实场景**：编程、数据分析、机器人等需要规划的任务

---

## 7. 🔗 与 xyz-agent 的关系

### 7.1 现有对照

| xyz-agent 模块 | 相关程度 | 说明 |
|:--------------|:--------:|:-----|
| `engine.py`（ReAct 循环） | ⭐⭐⭐ | ToT 可以直接替换 ReAct 中的推理策略 |
| `orchestrator.py`（多 Agent 编排） | ⭐⭐ | 多 Agent 并行推理 = ToT 的一种实现方式 |
| `planner.py`（规划模块） | ⭐⭐⭐ | 目前是线性规划，可以升级为树状规划 |

### 7.2 如何将 ToT 融入 xyz-agent

**方案 A：ToT 作为推理模块（替换 CoT）**

当 Agent 遇到复杂推理任务时，不再走一条 CoT 路径，而是启动 ToT 搜索：
```
原始 ReAct 循环：
  Thought → Action → Observation → Thought → ...

ToT 增强的 ReAct 循环：
  [树搜索: 生成多个 Thought 候选 → 评估 → 选最佳] → Action → Observation → [再次树搜索] → ...
```

具体来说：
```python
# 思路伪代码
class ToTReasoner:
    def reason(self, state, task):
        # Step 1: 生成候选思维
        candidates = self.generate_thoughts(state)
        # Step 2: 评估候选
        scores = self.evaluate(candidates)
        # Step 3: 搜索（BFS/DFS）
        best_path = self.search(candidates, scores)
        return best_path
```

**方案 B：多 Agent 并行搜索**

每个 Agent 基于同一状态生成不同推理路径，然后汇总评估——相当于用多个 Agent 实现了 ToT 的 BFS：

```python
# 思路伪代码
agents = [Agent() for _ in range(b)]
paths = [agent.reason(state) for agent in agents]  # 并行
best_path = vote(paths)  # 投票选最佳
```

这正是 xyz-agent 的多 Agent 架构天然适合的！

**方案 C：技能库 + 思维模板**

把 ToT 的思维分解策略（不同任务的分解模式）存入 xyz-agent 的技能库，让 Agent 遇到新任务时自动选择和适配：

```
技能库中的 ToT 模板：
  - 数学推理：3 步分解，采样法，BFS
  - 创意写作：2 层分解，提议法+投票法
  - 填字游戏：变量步数，DFS+剪枝
```

### 7.3 具体改造建议

```
第一阶段（简单）：
  ├── 在 engine.py 中增加 ToT 推理模式选项
  └── Game of 24 场景中启用 BFS 搜索

第二阶段（中等）：
  ├── 状态评估器：用 LLM 自我评分替代硬编码启发式
  ├── 支持 DFS 回溯（在 Action 执行失败时回溯到之前的分支点）
  └── 实现投票法用于开放式任务

第三阶段（进阶）：
  ├── 思维分解自动适配（根据任务类型选择合适的分解策略）
  ├── ToT 生成数据 → 微调 Agent 的基础模型
  └── 搜索过程可视化（Agent 展示自己的"思考树"）
```

---

## 8. 💭 我的思考

### 8.1 为什么这篇论文重要？

**ToT 是 LLM 推理研究的里程碑**。它把三样东西巧妙地结合在了一起：

1. **经典 AI 的搜索算法**（BFS/DFS）——1950 年代 Newell & Simon 的遗产
2. **LLM 的语言能力**——用自然语言生成候选、评估状态
3. **认知科学的理论**——System 1 / System 2 双系统理论

这不是"LLM 能做搜索"，而是"LLM 自己定义搜索空间、自己生成搜索策略、自己评估搜索结果"。

### 8.2 ToT 与后续工作的关系

| 后续工作 | 与 ToT 的关系 |
|:---------|:-------------|
| **DFSDT** | ToT + 蒙特卡洛树搜索（MCTS），更复杂的搜索策略 |
| **Graph of Thoughts (GoT)** | ToT + 图结构，允许思维合并和重组 |
| **RAP** (Hao et al. 2023) | 同时期工作，用 MCTS + 内部世界模型 |
| **LLM + MCTS** (AlphaGo-style) | 用 LLM 作为策略/价值网络，在推理树上跑 MCTS |
| **Self-Refine / Reflexion** | 与 ToT 互补——ToT 是横向探索，Reflexion 是纵向反思 |

### 8.3 我的批判性观察

**1. ToT 的搜索效率其实很低**

Game of 24 的 b=5 配置需要约 5×（3 层 × 评估）+ 额外生成 ≈ 大量 API 调用。作者在 Appendix 中承认成本是 CoT 的 5-20 倍。在真实产品中，这个成本很难接受。

**2. 思维分解的人工设计是最大的瓶颈**

每个任务都要手工设计"思维粒度"——太粗失去搜索意义，太细组合爆炸。论文没有给出自动学习分解策略的方法。

**3. 自我评估的可靠性问题**

LLM 对自己推理的评估不一定准确（正如人类对自己的判断也不一定准确）。论文用 5 次评估取平均来缓解，但没有系统分析 LLM 做评估器的偏差。

**4. 最有价值的可能是"蒸馏"而不是"推理时搜索"**

我认为 ToT 的最重要贡献可能不是应用方式（推理时搜索），而是**研究方向——用搜索生成高质量训练数据，然后微调模型**。如果模型经过 ToT 数据的训练后，能在单次推理中隐式地"想到"多条路径，那就真正实现了 System 2 → System 1 的迁移。

### 8.4 面试题积累

**Q1：ToT 和 CoT 的核心区别是什么？**
> ToT 将推理从线性链扩展为树状搜索。CoT 只走一条路径，而 ToT 探索多条路径、评估每条路径的进展、在必要时回溯。ToT = CoT + 多路径探索 + 自我评估 + 搜索算法。

**Q2：ToT 的四个设计维度是什么？**
> 思维分解（粒度）、思维生成（采样/提议）、状态评估（标量/投票）、搜索算法（BFS/DFS）。这四个维度形成了 ToT 的模块化设计空间。

**Q3：ToT 在 Game of 24 上的 74% 成功率意味着什么？对比 GPT-4 CoT 的 4%？**
> 这说明任务本身的困难不在于"计算"，而在于"搜索"。GPT-4 能理解规则（能做计算），但 CoT 的线性结构限制了它探索不同运算顺序的能力。ToT 通过搜索赋予模型"试错"能力，大幅提升了解决率。

**Q4：ToT 的主要限制有哪些？**
> ① 计算成本高 ② 思维分解需要人工设计 ③ 自我评估不可靠 ④ 不能修正 LLM 的基础能力缺陷 ⑤ 对简单任务不必要（杀鸡用牛刀）。

**Q5：如果让你把 ToT 集成到一个 Agent 框架中，你会怎么做？**
> ① 在推理引擎中增加 ToT 模式，任务复杂度超过阈值时启用 ② 思维分解从技能库中按任务类型自动选择 ③ 使用多 Agent 并行实现 BFS（每个 Agent 探索一条路径）④ 将搜索结果缓存，减少重复 API 调用。

---

## 附录：原文核心图表解读

### 图 1 — 方法对比示意图

```
(a) IO Prompting:   Input ──────────────→ Output
                     （一步到位，无中间步骤）

(b) Chain-of-Thought: Input → Think1 → Think2 → ... → Output
                     （线性链条，无分支）

(c) Tree of Thoughts: 
          ┌── Think1a ──┐
          │             ├── Think2a ──→ Output A
Input ────┼── Think1b ──┤              
          │             ├── Think2b ──→ Output B
          └── Think1c ──┘
                     （树状搜索，有评估和回溯）
```

### 图 2 — Game of 24 的实际 ToT 过程

```
Input: 4 9 10 13

Step 1: 生成 5 个候选等式
  ┌─ 13-9=4 (left: 4,4,10)  评分: 8
  ├─ 10+13=23 (left: 4,9,23) 评分: 5
  ├─ 4+9=13 (left: 10,13,13) 评分: 6
  ├─ 10-4=6 (left: 4,9,6)   评分: 7
  └─ 4*9=36 (left: 10,13,36) 评分: 4

保留 Top 1（b=1）: 13-9=4 (left: 4,4,10)

Step 2: 从 (4,4,10) 生成下一个候选
  ┌─ 10-4=6 (left: 4,6)  评分: 9
  ├─ 4+4=8 (left: 8,10)  评分: 6
  └─ 4*4=16 (left: 10,16) 评分: 4

保留 Top 1: 10-4=6 (left: 4,6)

Step 3: 最终步
  4*6=24 (left: 24) ✓
```

---

> 📝 **下一步**：下一篇精读论文 #3 **Toolformer**——自学使用工具的范式。详见 [toolformer.md](./toolformer.md)（待写）
