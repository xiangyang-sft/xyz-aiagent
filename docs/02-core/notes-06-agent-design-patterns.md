# Agent 核心设计模式：ReAct、Plan-Execute、Reflection

> 第 2 阶段 · 第 1 课
>
> 目标：掌握三种核心 Agent 设计模式的原理、实现与取舍

---

## Step 1：基础知识 — 为什么需要设计模式？

### 1.1 从简单 LLM 到 Agent 的跃迁

在 Phase 1 的动手实践中，我们实现了一个极简 ReAct 循环：

```
用户输入 → LLM 推理 → 行动（调用工具）→ 观察结果 → 继续推理 → 最终回答
```

但「推理→行动→观察」只是最基础的循环。**真正的 Agent 需要更复杂的决策结构**，就像软件工程需要设计模式一样，Agent 也需要成熟的架构模式来应对不同的场景。

### 1.2 三大核心模式总览

| 模式 | 核心思想 | 适用场景 | 复杂度 |
|------|----------|----------|--------|
| **ReAct** | 推理+行动交替循环 | 客服、任务执行、代码生成 | ⭐⭐ |
| **Plan-Execute** | 先规划再执行 | 复杂多步任务、项目拆分 | ⭐⭐⭐ |
| **Reflection** | 自我评估与修正 | 代码调试、写作、决策改进 | ⭐⭐⭐ |

### 1.3 它们的关系

```
        单步 → ReAct → Plan-Execute
                          ↓
                     Reflection（横切，可以叠加在任何模式上）
```

- **ReAct** 是最基础的模式，也是另外两种的基础
- **Plan-Execute** 可以看作是 ReAct 的升级版（先规划再执行）
- **Reflection** 是一个横切关注点，可以叠加在任何模式上

---

## Step 2：核心概念 — 三种模式深度解析

### 2.1 ReAct（Reasoning + Acting）

#### 2.1.1 什么是 ReAct？

由 Google 在 2022 年提出的框架（[论文《ReAct: Synergizing Reasoning and Acting in Language Models》](https://arxiv.org/abs/2210.03629)）。

**核心思想：** 将推理链（Reasoning）和行动（Acting）交织在一起，让 LLM 在思考的同时使用工具获取最新信息。

#### 2.1.2 循环流程

```
输入问题
  ↓
Thought（思考当前状态）
  ↓
Action（选择一个工具 + 参数）
  ↓
Observation（观察工具返回结果）
  ↓
循环直到可回答 → Final Answer
```

#### 2.1.3 关键特点

- **思维链融合工具调用**：每一步推理都基于前一步的观察
- **可解释性强**：每一步的 Thought 都可以被追踪
- **灵活应对动态环境**：每次观察都是最新信息

#### 2.1.4 局限

- **没有全局规划**：每一步只看到当前状态，像"贪心算法"
- **可能陷入死循环**：需要 max_iters、停止词等保护机制
- **Token 消耗大**：每一步都输出完整的 Thought

### 2.2 Plan-Execute

#### 2.2.1 什么是 Plan-Execute？

**核心思想：** 先将复杂任务分解为一个可执行的计划（Plan），然后逐步执行（Execute）。类比：先画好蓝图再施工。

#### 2.2.2 流程

```
输入复杂任务
  ↓
📋 Plan（规划阶段）
├── 分析任务需求
├── 分解为子步骤
└── 确定依赖关系

  ↓
🚀 Execute（执行阶段）
├── 按顺序/并行执行子步骤
├── 每个步骤可能使用工具
└── 动态调整：遇到问题可重新规划

  ↓
✅ Final Answer（综合各步骤结果）
```

#### 2.2.3 Plan 的几种形式

| 形式 | 描述 | 示例 |
|------|------|------|
| **线性计划** | 顺序执行步骤 | 1.搜索 → 2.总结 → 3.输出 |
| **DAG 计划** | 有向无环图，可并行 | 1.A+B 并行 → 2.合并结果 |
| **分层计划** | 子任务再分解 | 项目 → 阶段 → 任务 → 步骤 |
| **动态计划** | 执行中可修改计划 | 遇到障碍重新规划 |

#### 2.2.4 Plan-Execute vs ReAct

| 对比维度 | ReAct | Plan-Execute |
|----------|-------|--------------|
| 规划时机 | 边想边做 | 先想后做 |
| 全局视角 | ❌ 只有局部 | ✅ 有全局计划 |
| 灵活性 | 高（随时调整） | 中（可重新规划） |
| 适用任务 | 简单到中等 | 中等到复杂 |
| Token 效率 | 低（每步都要想） | 高（计划一次，执行多步） |

### 2.3 Reflection

#### 2.3.1 什么是 Reflection？

**核心思想：** Agent 在执行过程中或执行后，对自己的输出进行评估、发现错误、改进。本质是「元认知」（meta-cognition）。

#### 2.3.2 三种 Reflection 模式

**① 自省型（Self-Reflection）**

```
生成输出
  ↓
自我评估：这个回答正确吗？是否有遗漏？
  ↓
发现问题 → 修正输出
  ↓
再次评估 → 循环直到满意
```

**② 评估器型（Critic-Actor）**

```
Actor（生成方案）
  ↓
Critic（评估方案，给出反馈）
  ↓
Actor（根据反馈改进）
  ↓
重复直到 Critic 认可
```

**③ 类型化场景（Language Feedback）**
- **代码场景**：编译错误 → 修复 → 重新编译
- **写作场景**：检查逻辑性 → 修改 → 检查一致性
- **决策场景**：列出正反两面 → 权衡 → 改进决策

#### 2.3.3 Reflection 的作用

| 作用 | 描述 |
|------|------|
| **自我纠错** | 发现并修正自己的错误 |
| **质量提升** | 通过多轮迭代提高输出质量 |
| **学习能力** | 从错误中学习，下次做得更好 |
| **安全性** | 检查输出是否安全、合规 |

#### 2.3.4 注意事项

- **过度反思**：可能导致无限循环或降低效率
- **每次反思需要新 Token**：成本与迭代次数成正比
- **Critic 的质量**：如果评判标准不对，反思反而有害

---

## Step 3：完整实现 — 三种模式代码实战

实战代码位于 [`projects/02-agent-patterns/`](/root/xyz-aiagent/projects/02-agent-patterns/)：

| 文件 | 模式 | 关键点 |
|------|------|--------|
| `step1-react.py` | ReAct | Thought-Action-Observation 循环、文本解析 |
| `step2-plan-execute.py` | Plan-Execute | PLAN 解析、依赖管理、分阶段执行 |
| `step3-reflection.py` | Reflection | Actor-Critic 循环、迭代改进 |
| `step4-comparison.py` | 对比总结 | 三种模式对比表格 |

### ReAct 实现：step1-react.py

```python
# projects/02-agent-patterns/step1-react.py
"""ReAct 模式实现：带人工验证的搜索助手"""

import json
import re
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def search_web(query):
    """模拟搜索工具"""
    results = {
        "Agent 设计模式有哪些": "常见的 Agent 设计模式包括：ReAct（推理+行动）、Plan-Execute（规划-执行）、Reflection（反思）、Multi-Agent（多智能体协作）",
        "ReAct": "ReAct 是 Google 2022 年提出的框架，将推理（Reasoning）和行动（Acting）结合，让 LLM 边思考边使用工具",
    }
    return results.get(query, f"关于「{query}」的搜索结果")

def calculator(expr):
    """计算器工具"""
    try:
        return str(eval(expr))
    except:
        return "计算错误"

TOOLS = {
    "search_web": {
        "func": search_web,
        "description": "搜索网络获取信息",
        "params": {"query": "搜索关键词"}
    },
    "calculator": {
        "func": calculator,
        "description": "执行数学计算",
        "params": {"expr": "数学表达式"}
    }
}

TOOL_DESC = """你是一个智能助手，可以调用以下工具来回答问题。

可用工具：
{0}

响应格式：
- 如果需要使用工具，输出：
  Thought: （你的思考过程）
  Action: 工具名称
  Action Input: {{"参数名": "参数值"}}

- 如果已获得足够信息，输出：
  Thought: （最终思考）
  Final Answer: （最终答案）
"""

def build_tool_desc():
    desc_parts = []
    for name, tool in TOOLS.items():
        params = ", ".join(f"{k}: {v}" for k, v in tool["params"].items())
        desc_parts.append(f"- {name}: {tool['description']}，参数：{params}")
    return "\n".join(desc_parts)

def extract_action(text):
    """从 LLM 输出中提取行动"""
    action_match = re.search(r"Action:\s*(\w+)", text)
    input_match = re.search(r"Action Input:\s*(\{.*?\})", text, re.DOTALL)
    if action_match and input_match:
        return action_match.group(1), json.loads(input_match.group(1))
    return None, None

def react_loop(query, max_steps=5):
    messages = [
        {"role": "system", "content": TOOL_DESC.format(build_tool_desc())},
        {"role": "user", "content": query}
    ]

    for step in range(max_steps):
        print(f"\n{'='*40}")
        print(f"Step {step + 1}/{max_steps}")
        print(f"{'='*40}")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0
        )
        content = response.choices[0].message.content
        print(f"LLM: {content}")

        # 检查是否已给出最终答案
        if "Final Answer:" in content:
            final = content.split("Final Answer:")[-1].strip()
            return final

        # 提取工具调用
        action_name, params = extract_action(content)
        if action_name and params:
            tool = TOOLS.get(action_name)
            if tool:
                result = tool["func"](**params)
                print(f"🛠️  {action_name}({params}) = {result}")

                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": f"Observation: {result}"})
            else:
                print(f"❌ 未知工具: {action_name}")
                break
        else:
            print("❌ 无法解析工具调用")
            break

    return "达到最大步数，未得到完整答案"

if __name__ == "__main__":
    result = react_loop("什么是 ReAct 模式？它和 Calculator 有什么区别？请算出 2+3 的值")
    print(f"\n{'='*40}")
    print(f"最终答案: {result}")
```

### Plan-Execute 实现：step2-plan-execute.py

```python
# projects/02-agent-patterns/step2-plan-execute.py
"""Plan-Execute 模式实现：先规划再执行"""

import json
import re
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """你是一个任务规划助手。用户会给你一个复杂任务。

**规划阶段**：将任务分解为可执行的步骤，每个步骤包括：
- step_id: 步骤编号
- description: 步骤描述
- tool: 该步骤使用的工具
- depends_on: 依赖的步骤编号（若无则为[]）

**执行阶段**：按计划逐步执行，每一步完成后观察结果。

请严格按照以下格式规划：

PLAN:
[
  {"step_id": 1, "description": "...", "tool": "...", "depends_on": []},
  ...
]

执行步骤输出格式：
Thought: （思考）
Step: 步骤编号
Action: 工具名称
Action Input: {}
"""

def search_web(query):
    results = {
        "Python 列表推导式": "列表推导式是 Python 中创建列表的简洁语法：[x**2 for x in range(10)]",
        "Lambda 函数": "Lambda 函数是匿名函数：lambda x: x * 2",
        "Map Filter Reduce": "map() 对每个元素应用函数，filter() 过滤元素，reduce() 累积计算",
    }
    return results.get(query, f"关于「{query}」的信息")

def calculator(expr):
    try:
        return str(eval(expr))
    except:
        return "计算错误"

TOOLS = {
    "search_web": {"func": search_web, "description": "搜索信息"},
    "calculator": {"func": calculator, "description": "数学计算"},
}

def extract_plan(text):
    """从输出中提取计划"""
    match = re.search(r"PLAN:\s*(\[[\s\S]*?\])", text)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            return None
    return None

def execute_step(step, context, max_retries=2):
    """执行单个步骤"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"""当前上下文：{json.dumps(context, ensure_ascii=False)}

现在执行步骤 {step['step_id']}：{step['description']}
使用工具：{step['tool']}
返回格式：
Thought: （你的思考）
Action: 工具名称
Action Input: {{"参数名": "参数值"}}"""}
    ]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0
    )
    content = response.choices[0].message.content
    print(f"\n>>> 执行步骤 {step['step_id']}: {step['description']}")
    print(f"LLM: {content}")

    # 提取工具调用
    action_match = re.search(r"Action:\s*(\w+)", content)
    input_match = re.search(r"Action Input:\s*(\{.*?\})", content, re.DOTALL)

    if action_match and input_match:
        action_name = action_match.group(1)
        params = json.loads(input_match.group(1))
        tool = TOOLS.get(action_name)
        if tool:
            result = tool["func"](**params)
            print(f"🛠️  → {result}")
            context[f"step_{step['step_id']}_result"] = result
            return result
    return None

def plan_execute_loop(query):
    print("=" * 50)
    print("📋 阶段 1：规划")
    print("=" * 50)

    # 1. 生成计划
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"请为以下任务制定详细的执行计划：\n\n{query}"}
    ]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.2
    )
    plan_text = response.choices[0].message.content
    print(plan_text)

    plan = extract_plan(plan_text)
    if not plan:
        return "无法生成有效的计划"

    print(f"\n✅ 计划生成，共 {len(plan)} 步")

    # 2. 执行计划
    print("\n" + "=" * 50)
    print("🚀 阶段 2：执行")
    print("=" * 50)

    context = {}
    for step in plan:
        # 检查依赖是否完成
        deps = step.get("depends_on", [])
        for dep in deps:
            if f"step_{dep}_result" not in context:
                print(f"⏳ 等待步骤 {dep} 完成...")
                break

        result = execute_step(step, context)
        if result is None:
            print(f"⚠️  步骤 {step['step_id']} 执行失败")

    # 3. 综合结果
    print("\n" + "=" * 50)
    print("📝 阶段 3：综合回答")
    print("=" * 50)

    summary_messages = [
        {"role": "system", "content": "你是一个分析助手"},
        {"role": "user", "content": f"""原始任务：{query}

各步骤执行结果：
{json.dumps(context, ensure_ascii=False, indent=2)}

请综合所有结果，给出完整的最终答案。"""}
    ]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=summary_messages,
        temperature=0
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    result = plan_execute_loop(
        "请解释 Python 中的列表推导式、Lambda 函数、以及 Map/Filter/Reduce 的用法"
    )
    print(f"\n最终答案:\n{result}")
```

### Reflection 实现：step3-reflection.py

```python
# projects/02-agent-patterns/step3-reflection.py
"""Reflection 模式实现：Actor-Critic 循环"""

from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ACTOR_SYSTEM = """你是一个代码助手。根据用户需求生成 Python 代码。
只输出代码，不要额外解释。"""

CRITIC_SYSTEM = """你是一个代码审查员。检查代码中的问题并给出改进建议。
检查项：
1. 语法正确性
2. 逻辑正确性
3. 边缘情况处理
4. 代码风格
5. 安全性
6. 性能

如果代码没有问题，请输出：✅ 代码通过审查
如果有问题，请描述具体问题和改进建议。"""

REFINER_SYSTEM = """你是一个代码改进助手。根据审查员的反馈，改进之前的代码。
只输出改进后的代码，不要额外解释。"""

def generate_code(prompt):
    """Actor：生成代码"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": ACTOR_SYSTEM},
            {"role": "user", "content": f"生成 Python 代码：{prompt}"}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content

def review_code(code):
    """Critic：审查代码"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": CRITIC_SYSTEM},
            {"role": "user", "content": f"请审查以下代码：\n\n```\n{code}\n```"}
        ],
        temperature=0
    )
    return response.choices[0].message.content

def refine_code(code, review, prompt):
    """Refiner：根据反馈改进代码"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": REFINER_SYSTEM},
            {"role": "user", "content": f"""原始需求：{prompt}

原始代码：
```
{code}
```

审查反馈：
{review}

请输出改进后的代码："""}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content

def reflection_loop(prompt, max_iterations=3):
    print("=" * 50)
    print("🎭 Reflection 模式：Actor-Critic 循环")
    print("=" * 50)

    print(f"\n📝 需求：{prompt}")

    current_code = generate_code(prompt)
    print(f"\n{'='*40}")
    print(f"✏️  第 1 轮 - 初始代码（Actor）")
    print(f"{'='*40}")
    print(f"\n```\n{current_code}\n```")

    for i in range(max_iterations - 1):
        # 审查
        print(f"\n{'='*40}")
        print(f"🔍 第 {i+1} 轮审查（Critic）")
        print(f"{'='*40}")

        review = review_code(current_code)

        # 检查是否通过
        if "✅ 代码通过审查" in review:
            print(f"\n{review}")
            print(f"\n🎉 代码已通过审查！")
            break

        print(f"\n{review}")

        # 改进
        print(f"\n{'='*40}")
        print(f"✏️  第 {i+2} 轮改进（Refiner）")
        print(f"{'='*40}")

        current_code = refine_code(current_code, review, prompt)
        print(f"\n```\n{current_code}\n```")

    print(f"\n{'='*50}")
    print(f"✅ 最终代码（{max_iterations} 轮迭代）")
    print(f"{'='*50}")
    print(f"\n```\n{current_code}\n```")

    return current_code

if __name__ == "__main__":
    result = reflection_loop(
        "写一个函数，输入一个整数列表，返回所有偶数的平方。要求处理空列表和 None 的情况。"
    )
```

### 对比总结：step4-comparison.py

```python
# projects/02-agent-patterns/step4-comparison.py
"""三种模式对比运行脚本"""

print("""
┌─────────────────────────────────────────────────────────────┐
│               Agent 核心设计模式对比总结                     │
├──────────────┬──────────────┬──────────────┬───────────────┤
│   维度       │   ReAct      │ Plan-Execute │  Reflection   │
├──────────────┼──────────────┼──────────────┼───────────────┤
│ 规划方式     │ 逐步推理     │ 先全局规划   │ 迭代改进      │
│ 灵活性       │ 高           │ 中           │ 中            │
│ 可解释性     │ 高           │ 高           │ 中            │
│ 复杂任务     │ 一般         │ 优秀         │ 良好          │
│ Token 消耗   │ 高           │ 中           │ 高            │
│ 执行效率     │ 中           │ 高           │ 低（多次迭代）│
│ 自我改进     │ 无           │ 有限         │ 核心机制      │
│ 适用场景     │ 客服/搜索    │ 研究/开发    │ 代码/写作     │
└──────────────┴──────────────┴──────────────┴───────────────┘

组合使用示例：
  1. Plan-Execute + Reflection = 制定计划后每一步都反思
  2. ReAct + Reflection = 每步推理后自检再行动
  3. 三者叠加 = 复杂任务的终极方案
""")
```

---

## 🎯 面试题（10 道 — 覆盖原理、实现到架构设计）

### Q1：ReAct 和 Chain-of-Thought（CoT）有什么区别？

**要点：**
- **CoT**：只做推理（Think），不行动，LLM 在内部逐步推理出答案
- **ReAct**：推理（Think）+ 行动（Act）交替，每一步推理后可能调用外部工具获取新信息
- 公式：`ReAct = CoT + Tool Use`

**选择依据：**
- 任务**信息完整**（如数学题、逻辑推理）→ CoT 即可
- 任务**需要外部信息**（如搜索、查数据库）→ ReAct

### Q2：Plan-Execute 在什么情况下需要重新规划（Re-plan）？

**常见触发条件：**
1. **执行结果与预期严重不符** — 比如搜索"Python 3.13 新特性"得到空结果，需要调整搜索词
2. **依赖的子任务失败** — 上一步出错了，后续步骤依赖其结果
3. **发现计划有遗漏** — 执行中意识到还需要一个步骤
4. **环境状态改变** — 如 API 限流、工具不可用

**实现策略：**
```python
if result_is_unexpected(step_result):
    plan = replan(query, context)  # 重新生成计划
```

### Q3：Reflection 如何防止过度循环（Over-reflection）？

**解决策略：**

| 方案 | 实现方式 | 适用场景 |
|------|----------|----------|
| **最大迭代次数** | `for i in range(max_iters)` | 所有场景，最基础 |
| **阈值判断** | Critic 给出分数，>80 分通过 | 代码生成、写作 |
| **改进量检测** | 连续 N 轮改进量 < 阈值则退出 | 写作润色 |
| **Token 预算** | 总消耗超过 X token 时终止 | 高成本场景 |
| **时间限制** | 超过 T 秒后强制输出 | 实时交互场景 |

**经验值：** Reflection 迭代一般 2-3 轮效果最好，超过 5 轮边际收益急剧下降。

### Q4：这三种模式可以组合使用吗？给出一个实际例子。

**可以，且在实际产品中几乎是必然的组合。**

**实际案例 — 智能编程助手：**
1. **Plan-Execute**：用户说"开发一个天气查询网页"，Agent 先规划：分析需求 → 设计前端 → 实现后端 → 联调测试
2. **ReAct**：每个子步骤内部，比如"实现后端"时，需要查文档 API、写代码、查错误信息
3. **Reflection**：全部完成后，整体审查代码质量，发现 bug 并修复

```python
# 三层叠加伪代码
plan = planner.plan("开发天气查询网页")        # Plan
for step in plan:
    while not step_complete:
        action = react_step(step)                # ReAct
        observation = execute(action)
        step_complete = check_complete(observation)
    reflection.review(step_result)               # Reflection（每步反思）
reflection.review_final(product)                 # Reflection（最终审查）
```

### Q5：ReAct 模式下，如果 LLM 连续输出无效的 Action 格式，怎么办？

**分层容错策略：**

```
第 1 层 — 重试（Retry）
  重新调用 LLM，加上格式示例（few-shot）

第 2 层 — 修复（Repair）
  用正则/规则自动修复常见格式错误（如缺少冒号、JSON 格式错误）

第 3 层 — 降级（Fallback）
  放弃当前轮，返回错误消息给用户，或改用 simpler 的提示词

第 4 层 — 回退（Rollback）
  回到前一步，换一种方式重新开始
```

**关键原则：** 不要无限重试，每层都有次数上限。

### Q6：Plan-Execute 的 PLAN 格式设计有哪些要点？

**设计原则：**

| 要点 | 为什么 | 反例 |
|------|--------|------|
| **每个步骤一个工具** | 避免一个步骤做太多事导致 LLM 难以生成正确参数 | `step1: 查数据并处理并输出` |
| **明确的依赖关系** | 支持并行执行和顺序保障 | 不声明 `depends_on` |
| **适中的步骤粒度** | 太粗（3 步）= 失去规划意义，太细（30 步）= 计划本身成本高 | 10-15 步最佳 |
| **可重新规划的接口** | 计划不可能完美，必须支持执行中修改 | 硬编码的固定计划 |

### Q7：Reflection 中 Critic 的质量如何保证？

**Critic 本身就是 LLM 调用，有同样的问题。** 保证 Critic 质量的策略：

1. **结构化检查清单** — 给 Critic 明确的检查项（语法、逻辑、安全、性能）
2. **多 Critic 投票** — 多个 LLM 实例审查，取共识（高成本但高质量）
3. **规则引擎辅助** — 对于可自动化的检查（语法错误、拼写错误），先用规则工具
4. **Critic 的 Prompt 工程** — Critic 的 prompt 比 Actor 的 prompt 更关键
5. **Critic 回测** — 定期用已知错误样本测试 Critic 的识别能力

### Q8：ReAct 中 Thought 步骤是否必要？可以跳过吗？

**不推荐跳过。** Thought 步骤有 4 个关键作用：

1. **推理锚点**：让 LLM 在行动前整理思路，减少"乱调工具"
2. **可解释性**：用户/开发者可以看到 Agent 的决策过程
3. **错误追踪**：当结果不对时，可以回溯到哪一步思考错了
4. **上下文保持**：多轮交互中，Thought 帮助 LLM 保持对任务的聚焦

**有损优化：** 在确定性的简单任务中（如"查询天气"），可以压缩 Thought，使用 `tool_choice="required"` + Function Calling 直接跳到 Action。

### Q9：三种模式的 Token 消耗如何量化比较？

| 模式 | N 步 Token 消耗公式 | 示例（5 步任务） |
|------|---------------------|------------------|
| ReAct | `N × (Thought + Action + Observation)` | 5 × 500 = 2500 |
| Plan-Execute | `Plan + N × (Action + Observation)` | 500 + 5 × 300 = 2000 |
| Reflection | `M × (Generate + Review)` | 3 × (500 + 400) = 2700 |
| 组合 | Plan + N × ReAct + M × Reflection | 500 + 5×400 + 2×600 = 3700 |

**优化建议：**
- Plan-Execute 在确定性高、步骤多的任务中最省 Token
- Reflection 的 Token 成本与迭代次数线性增长，控制 M 是关键
- 尽量将 Observation（工具结果）做摘要，而不是原样送入上下文

### Q10：如何测试 Agent 设计模式的正确性？用什么指标？

**测试方法：**

| 层级 | 方法 | 验证什么 |
|------|------|----------|
| **单元测试** | Mock 工具，固定输入验证输出格式 | 模式循环是否正确 |
| **集成测试** | 真实 LLM + 模拟工具 | 端到端流程是否跑通 |
| **E2E 测试** | 完整真实环境 | 真实场景下的表现 |
| **回归测试** | 预定义的 50-100 个用例 | 修改后是否引入退化 |

**关键指标：**

| 指标 | 定义 | 目标值 |
|------|------|--------|
| **任务完成率** | 是否成功完成任务 | >90% |
| **平均步数** | 完成任务的 ReAct 循环次数 | 理想 <5 |
| **无效工具调用率** | 调用了不存在或不合理的工具 | <10% |
| **死循环发生率** | 触发 max_iters 超时的比例 | <5% |
| **重新规划率** | Plan-Execute 中触发 re-plan 的比例 | <20% |
| **Reflection 提升率** | 反思后质量评分提升的比例 | >60% |

---

## 核心认识

1. **三种模式互补，不是替代关系** — 实际产品往往是组合使用
2. **ReAct 是地基** — Plan-Execute 和 Reflection 都建立在 ReAct 之上
3. **Plan-Execute 节省 Token** — 对于确定性高、步骤多的任务，先规划再执行效率最高
4. **Reflection 提升质量有代价** — 迭代收益递减，控制在 2-3 轮最佳
5. **工具设计决定模式成败** — 模式再好，工具不准也没用

---

## 第二阶段进度

| # | 内容 | 状态 |
|---|------|------|
| 1 | **Agent 核心设计模式（ReAct、Plan-Execute、Reflection）** | **✅ 本课** |
| 2 | 工具调用（Function Calling、Tool Use） | ✅ |
| 3 | 记忆系统（短期/长期记忆、RAG） | ⏳ 下一课 |
| 4 | 多 Agent 协作 | 待学习 |
| 5 | 动手：完整单 Agent 应用 | 待学习 |
