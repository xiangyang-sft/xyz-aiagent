"""
Plan-Execute 模式实现：先全局规划，再逐步执行
Step 2 - 包含规划器 + 执行器 + 综合器
"""

import json
import re
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── 工具定义 ──────────────────────────────────────────

def search_web(query):
    """模拟搜索工具"""
    results = {
        "Python 列表推导式": "列表推导式是 Python 创建列表的简洁语法：[expr for item in iterable if condition]。例如 [x**2 for x in range(10)] 生成 0,1,4,9,...,81",
        "Lambda 函数": "Lambda 函数是 Python 的匿名函数，格式：lambda 参数: 表达式。例如 lambda x: x * 2 等价于 def double(x): return x * 2",
        "Map": "map(func, iterable) 对可迭代对象每个元素应用函数。例如 list(map(str, [1,2,3])) → ['1','2','3']",
        "Filter": "filter(func, iterable) 过滤元素，只保留使函数返回 True 的元素。例如 list(filter(lambda x: x > 0, [-1, 0, 1])) → [1]",
        "Reduce": "reduce(func, iterable) 累积计算。例如 reduce(lambda a,b: a+b, [1,2,3]) = 1+2+3 = 6。需要 from functools import reduce",
    }
    return results.get(query, f"关于「{query}」暂无具体信息")

def calculator(expr):
    try:
        allowed = set("0123456789+-*/(). ")
        if not all(c in allowed for c in expr):
            return "非法字符"
        return str(eval(expr))
    except Exception as e:
        return f"计算错误：{e}"

TOOLS = {
    "search_web": {"func": search_web, "desc": "搜索获取信息"},
    "calculator": {"func": calculator, "desc": "数学计算"},
}

# ── Prompt 定义 ───────────────────────────────────────

PLANNER_PROMPT = """你是一个任务规划师。将用户的任务分解为可执行的步骤。

每个步骤必须包含：
- step_id: 整数编号
- description: 步骤描述
- tool: 使用的工具（{tools}）
- depends_on: 依赖的步骤编号列表（无依赖则 []）

输出格式（纯 JSON 数组，不要其他内容）：
[
  {{"step_id": 1, "description": "搜索XX信息", "tool": "search_web", "depends_on": []}},
  ...
]

规则：
1. 步骤按依赖关系排序，被依赖的步骤在前面
2. 不需要工具的步骤（如分析、总结）用 tool: "none"
3. 可并行的步骤不要互相依赖
4. 最后一步通常是综合总结"""

EXECUTOR_PROMPT = """你是任务执行者。

当前上下文：
{context}

执行步骤 {step_id}：{desc}
使用工具：{tool}

输出格式（只输出需要的部分）：
如果使用工具 → Action: 工具名 | Action Input: {{"参数名": "值"}}
如果无需工具 → Result: 直接输出结果"""

SUMMARIZER_PROMPT = """你是一个总结助手。

原始任务：{task}

各步骤执行结果：
{results}

请综合所有结果，给出完整、清晰的最终答案。"""

# ── 核心逻辑 ──────────────────────────────────────────

def extract_plan(text):
    """从 LLM 输出提取计划 JSON"""
    # 尝试直接解析
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except:
        pass
    # 尝试从代码块提取
    match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass
    # 尝试从文本中提取
    match = re.search(r"(\[[\s\S]*?\])", text)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass
    return None

def plan_task(task):
    """阶段 1：规划 — 将任务分解为执行计划"""
    print("\n" + "=" * 50)
    print("📋 阶段 1：规划（Planner）")
    print("=" * 50)

    tool_names = ", ".join(TOOLS.keys())
    messages = [
        {"role": "system", "content": PLANNER_PROMPT.format(tools=tool_names)},
        {"role": "user", "content": task}
    ]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.2
    )
    plan_text = response.choices[0].message.content.strip()
    print(f"\n💭 Planer 输出:\n{plan_text}\n")

    plan = extract_plan(plan_text)
    if plan:
        print(f"✅ 计划生成，共 {len(plan)} 步")
        for s in plan:
            deps = s.get("depends_on", [])
            dep_str = f"（依赖: {deps}）" if deps else ""
            print(f"   Step {s['step_id']}: {s['description']} [{s['tool']}] {dep_str}")
    else:
        print("❌ 无法解析计划")

    return plan

def execute_plan(plan):
    """阶段 2：执行 — 按计划逐步执行"""
    print("\n" + "=" * 50)
    print("🚀 阶段 2：执行（Executor）")
    print("=" * 50)

    if not plan:
        return {}

    context = {}
    completed = set()

    while len(completed) < len(plan):
        for step in plan:
            sid = step["step_id"]
            if sid in completed:
                continue

            # 检查依赖是否就绪
            deps = set(step.get("depends_on", []))
            if not deps.issubset(completed):
                continue

            # 执行此步骤
            print(f"\n{'─'*40}")
            print(f"▶  执行 Step {sid}: {step['description']}")
            print(f"{'─'*40}")

            tool = step.get("tool", "none")
            if tool == "none":
                # 不需要工具，直接让 LLM 分析
                context_str = json.dumps(context, ensure_ascii=False, indent=2)
                prompt = EXECUTOR_PROMPT.format(
                    context=context_str,
                    step_id=sid,
                    desc=step["description"],
                    tool="none"
                )
                messages = [
                    {"role": "system", "content": "你是任务执行者。根据上下文直接输出结果。"},
                    {"role": "user", "content": prompt}
                ]
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0
                )
                result = response.choices[0].message.content.strip()
                print(f"💭 {result}")
                context[f"step_{sid}"] = result
            else:
                # 需要工具，由 LLM 决定如何调用
                context_str = json.dumps(context, ensure_ascii=False, indent=2)
                prompt = EXECUTOR_PROMPT.format(
                    context=context_str,
                    step_id=sid,
                    desc=step["description"],
                    tool=tool
                )
                messages = [
                    {"role": "system", "content": f"可用工具：{', '.join(TOOLS.keys())}"},
                    {"role": "user", "content": prompt}
                ]
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0
                )
                content = response.choices[0].message.content.strip()
                print(f"💭 {content}")

                # 提取工具调用
                action_match = re.search(r"Action:\s*(\w+)", content)
                input_match = re.search(r"Action Input:\s*\{(.*?)\}", content, re.DOTALL)
                if action_match:
                    tool_name = action_match.group(1)
                    if tool_name in TOOLS:
                        params_text = "{" + input_match.group(1) + "}" if input_match else "{}"
                        try:
                            params = json.loads(params_text)
                            result = TOOLS[tool_name]["func"](**params)
                            print(f"🛠️  → {result}")
                            context[f"step_{sid}"] = result
                        except Exception as e:
                            print(f"❌ 工具调用失败: {e}")
                            context[f"step_{sid}"] = f"执行失败: {e}"
                    else:
                        print(f"❌ 未知工具: {tool_name}")
                        context[f"step_{sid}"] = f"未知工具: {tool_name}"
                else:
                    context[f"step_{sid}"] = content

            completed.add(sid)

    return context

def summarize(task, results):
    """阶段 3：总结 — 综合所有结果"""
    print("\n" + "=" * 50)
    print("📝 阶段 3：总结（Summarizer）")
    print("=" * 50)

    result_str = json.dumps(results, ensure_ascii=False, indent=2)
    messages = [
        {"role": "system", "content": "你是一个总结助手。"},
        {"role": "user", "content": SUMMARIZER_PROMPT.format(task=task, results=result_str)}
    ]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0
    )
    summary = response.choices[0].message.content.strip()
    print(f"\n💭 {summary}")
    return summary


def plan_execute_loop(task):
    """Plan-Execute 主流程"""
    print(f"\n{'='*60}")
    print(f"📋 Plan-Execute 模式")
    print(f"📝 任务: {task}")
    print(f"{'='*60}")

    # 阶段 1：规划
    plan = plan_task(task)
    if not plan:
        return "无法生成执行计划"

    # 阶段 2：执行
    results = execute_plan(plan)

    # 阶段 3：总结
    summary = summarize(task, results)

    print(f"\n{'='*60}")
    print(f"✅ 最终结果")
    print(f"{'='*60}")
    print(summary)
    return summary


def interactive():
    """交互式 Plan-Execute 演示"""
    print("=" * 60)
    print("Plan-Execute 模式 — 交互式演示")
    print("输入复杂任务，Agent 会先规划再执行")
    print("输入 'exit' 退出")
    print("=" * 60)

    while True:
        task = input("\n🧑 任务: ").strip()
        if task.lower() in ("exit", "quit", "q"):
            print("再见！")
            break
        if not task:
            continue
        plan_execute_loop(task)


if __name__ == "__main__":
    # 演示
    task = "请解释 Python 中的列表推导式、Lambda 函数、以及 Map/Filter/Reduce 的用法，并给出代码示例"
    plan_execute_loop(task)
