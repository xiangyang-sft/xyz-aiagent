#!/usr/bin/env python3
"""Step 4: 框架风格实现对比 — CrewAI 风格 vs LangGraph 风格

核心模式：用纯 Python 实现两种主流框架的"核心思想"：
- CrewAI 风格：声明式配置，Agent + Task + Crew
- LangGraph 风格：图编排，Node + Edge + State

学习目标：
- 理解不同框架的设计哲学
- 掌握"框架无魔法"的本质
- 为后续学习真实框架打下基础
"""

import json
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "YOUR_API_KEY_HERE"),
)


# ═══════════════════════════════════════════════════════════════
# 风格 A：CrewAI 风格（声明式编排）
# ═══════════════════════════════════════════════════════════════
# CrewAI 的核心思想：
#   定义 Agent（角色/目标/能力）→ 定义 Task（描述/分配/期望输出）
#   → 组成 Crew（顺序/层级/流程）→ 启动执行

class CrewStyleAgent:
    """CrewAI 风格的 Agent"""
    
    def __init__(self, role: str, goal: str, backstory: str):
        self.role = role
        self.goal = goal
        self.backstory = backstory
    
    def _build_prompt(self) -> str:
        return f"""角色：{self.role}
目标：{self.goal}
背景：{self.backstory}

请以这个角色身份，完成分配给你的任务。"""
    
    def execute(self, task_description: str, context: str = "") -> str:
        prompt = self._build_prompt()
        full_input = f"{context}\n\n任务：{task_description}" if context else f"任务：{task_description}"
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": full_input},
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content


class CrewStyleTask:
    """CrewAI 风格的 Task"""
    
    def __init__(self, description: str, expected_output: str, agent: CrewStyleAgent):
        self.description = description
        self.expected_output = expected_output
        self.agent = agent
        self.output = None
    
    def run(self, context: str = "") -> str:
        full_desc = f"{self.description}\n\n期望输出：{self.expected_output}"
        self.output = self.agent.execute(full_desc, context)
        return self.output


class CrewStyleCrew:
    """CrewAI 风格的 Crew（团队编排器）"""
    
    def __init__(self, name: str, process: str = "sequential"):
        """
        process: "sequential"（顺序执行）或 "hierarchical"（层级式）
        """
        self.name = name
        self.process = process
        self.tasks: list[CrewStyleTask] = []
        self.results: dict[str, str] = {}
    
    def add_task(self, task: CrewStyleTask):
        """添加任务（按添加顺序执行）"""
        self.tasks.append(task)
    
    def kickoff(self, verbose: bool = True) -> dict[str, str]:
        """启动 Crew"""
        if verbose:
            print(f"\n{'='*60}")
            print(f"🚀 CrewAI 风格 — {self.name}")
            print(f"流程模式: {self.process}")
            print(f"任务数: {len(self.tasks)}")
            print(f"{'='*60}")
        
        if self.process == "sequential":
            return self._run_sequential(verbose)
        else:
            return self._run_hierarchical(verbose)
    
    def _run_sequential(self, verbose: bool) -> dict[str, str]:
        """顺序执行"""
        context = ""
        for i, task in enumerate(self.tasks):
            if verbose:
                agent_name = task.agent.role
                print(f"\n  [{i+1}/{len(self.tasks)}] {agent_name}")
                print(f"    任务: {task.description[:80]}...")
            
            result = task.run(context)
            self.results[f"task_{i+1}_{task.agent.role}"] = result
            context = f"前序任务结果：\n{result}"
            
            if verbose:
                print(f"  ✓ 完成 ({len(result)} 字符)")
        
        return self.results
    
    def _run_hierarchical(self, verbose: bool) -> dict[str, str]:
        """层级式：管理者分配任务给下属"""
        if len(self.tasks) < 2:
            return self._run_sequential(verbose)
        
        # 第一个 Agent 作为管理者
        manager = self.tasks[0].agent
        workers = self.tasks[1:]
        
        if verbose:
            print(f"\n  [管理者] {manager.role} 分配任务...")
        
        for i, task in enumerate(workers):
            assign_prompt = f"""作为 {manager.role}，请将以下任务分配给 {task.agent.role}：

任务：{task.description[:200]}

请给出任务分配指令（明确告诉 {task.agent.role} 需要做什么、怎么做、输出什么）："""
            
            instruction = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"你是 {manager.role}，擅长任务分配和项目管理。"},
                    {"role": "user", "content": assign_prompt},
                ],
                temperature=0.3,
            ).choices[0].message.content
            
            if verbose:
                print(f"\n    → 分配 {task.agent.role}")
            
            result = task.agent.execute(
                task_description=f"{instruction}\n\n原始任务：{task.description}",
                context=f"期望输出：{task.expected_output}",
            )
            self.results[f"task_{i+1}_{task.agent.role}"] = result
            
            if verbose:
                print(f"    ✓ 完成")
        
        return self.results


def demo_crewai_style():
    """演示 CrewAI 风格"""
    
    # 定义 Agent
    researcher = CrewStyleAgent(
        role="研究员",
        goal="全面收集和分析信息",
        backstory="你是一名经验丰富的研究员，擅长从多个角度深入分析问题。",
    )
    
    writer = CrewStyleAgent(
        role="写作者",
        goal="将研究结果转化为清晰易读的内容",
        backstory="你是一名专业的技术写作者，能将复杂概念用通俗语言表达。",
    )
    
    reviewer = CrewStyleAgent(
        role="审查员",
        goal="检查输出质量，确保准确性和完整性",
        backstory="你是一名苛刻的审查员，善于发现错误和改进空间。",
    )
    
    # 定义 Task
    tasks = [
        CrewStyleTask(
            description="分析 RAG（检索增强生成）技术的最新进展和核心原理",
            expected_output="结构化的研究报告，包含技术原理、架构组件、最新进展",
            agent=researcher,
        ),
        CrewStyleTask(
            description="将研究报告转化为一篇通俗易懂的技术博客",
            expected_output="格式规范的技术博客文章，适合开发者阅读",
            agent=writer,
        ),
        CrewStyleTask(
            description="审查博客内容，检查技术准确性、表达清晰度和完整性",
            expected_output="审查意见和改进建议",
            agent=reviewer,
        ),
    ]
    
    # 创建 Crew
    crew = CrewStyleCrew(
        name="RAG 技术博客生产流水线",
        process="sequential",
    )
    
    for task in tasks:
        crew.add_task(task)
    
    return crew.kickoff()


# ═══════════════════════════════════════════════════════════════
# 风格 B：LangGraph 风格（图编排）
# ═══════════════════════════════════════════════════════════════
# LangGraph 的核心思想：
#   定义 State（全局状态）→ 定义 Node（处理节点）→ 定义 Edge（流转条件）
#   → 编译为图 → 执行直到终止

class GraphState:
    """图的全局状态"""
    
    def __init__(self, initial_data: dict = None):
        self.data = initial_data or {}
        self.history = []
    
    def update(self, key: str, value):
        self.data[key] = value
        self.history.append({"key": key, "value": value})
    
    def get(self, key: str, default=None):
        return self.data.get(key, default)


class GraphNode:
    """图中的处理节点"""
    
    def __init__(self, name: str, system_prompt: str, router: bool = False):
        self.name = name
        self.system_prompt = system_prompt
        self.is_router = router  # 是否为路由节点（决定下一步走向）
    
    def process(self, state: GraphState) -> str:
        """处理当前状态，返回输出"""
        context = json.dumps(state.data, ensure_ascii=False, indent=2)
        
        if self.is_router:
            prompt = f"""当前全局状态：
{context}

作为 {self.name}，请分析当前状态并决定下一步操作。
回复格式：{"next": "下一步节点名", "reason": "理由"}
可选的下一步节点：需要根据状态判断"""
        else:
            prompt = f"""当前全局状态：
{context}

作为 {self.name}，请根据你的职责处理当前任务。
如果需要路由到其他节点，请在回复末尾标注 ROUTE: 节点名。"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content


class LangGraphStyleGraph:
    """LangGraph 风格的图编排器"""
    
    def __init__(self):
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[tuple[str, str, str | None]] = []  # (from, to, condition)
        self.entry_point: str = None
        self.max_steps = 20
    
    def add_node(self, name: str, node: GraphNode):
        """添加节点"""
        self.nodes[name] = node
    
    def set_entry_point(self, name: str):
        """设置入口节点"""
        self.entry_point = name
    
    def add_edge(self, from_node: str, to_node: str, condition: str | None = None):
        """添加边（流转条件）"""
        self.edges.append((from_node, to_node, condition))
    
    def compile(self) -> callable:
        """编译图，返回可执行函数"""
        
        def execute(input_data: dict, verbose: bool = True) -> GraphState:
            state = GraphState(input_data)
            current = self.entry_point
            step = 0
            
            if verbose:
                print(f"\n{'='*60}")
                print(f"🔗 LangGraph 风格 — 图编排执行")
                print(f"节点数: {len(self.nodes)}, 最大步数: {self.max_steps}")
                print(f"{'='*60}\n")
            
            while current and step < self.max_steps:
                node = self.nodes.get(current)
                if not node:
                    break
                
                step += 1
                if verbose:
                    print(f"  [{step}] ▶️ 运行节点: {current}")
                
                output = node.process(state)
                state.update(f"{current}_output", output)
                
                if verbose:
                    preview = output[:150].replace('\n', ' ')
                    print(f"     输出: {preview}...\n")
                
                # 路由逻辑
                next_node = None
                if node.is_router:
                    # 路由节点的输出决定下一步
                    try:
                        import re
                        match = re.search(r'"next":\s*"([^"]+)"', output)
                        if match:
                            next_node = match.group(1)
                    except:
                        pass
                else:
                    # 普通节点：检查是否有 ROUTE 标记
                    if "ROUTE:" in output:
                        next_node = output.split("ROUTE:")[-1].strip().split("\n")[0].strip()
                    else:
                        # 查找匹配的边条件
                        for from_n, to_n, cond in self.edges:
                            if from_n == current:
                                if cond is None or cond in output:
                                    next_node = to_n
                                    break
                
                if next_node and next_node in self.nodes:
                    current = next_node
                else:
                    # 没有更多流转，结束
                    if verbose and next_node and next_node not in self.nodes:
                        print(f"  ⚠ 目标节点 '{next_node}' 不存在，终止")
                    current = None
            
            if verbose:
                print(f"{'='*60}")
                print(f"✅ 图执行完成！共 {step} 步")
                print(f"{'='*60}")
            
            return state
        
        return execute


def demo_langgraph_style():
    """演示 LangGraph 风格"""
    
    # 定义节点
    nodes = {
        "analyzer": GraphNode(
            name="问题分析器",
            system_prompt="""你是一个问题分析器。分析用户输入的问题：
1. 明确核心需求
2. 识别问题类型（技术/创意/数据分析/综合）
3. 确定需要哪些专业能力

输出分析结果。如果问题需要多方面分析，在末尾标注 ROUTE: researcher""",
        ),
        "researcher": GraphNode(
            name="研究员",
            system_prompt="""你是一个研究员。深入研究所分配的问题主题。
提供技术原理、背景知识和相关案例。
输出研究报告。完成后标注 ROUTE: planner""",
        ),
        "planner": GraphNode(
            name="规划者",
            system_prompt="""你是一个规划者。基于研究结果制定执行方案。
包含步骤、方法、资源需求和里程碑。
输出执行计划。完成后标注 ROUTE: executor""",
        ),
        "executor": GraphNode(
            name="执行者",
            system_prompt="""你是一个执行者。根据执行计划产出具体成果。
如果是代码任务，写出完整代码。
如果是文档任务，输出完整文档。
完成后标注 ROUTE: reviewer""",
        ),
        "reviewer": GraphNode(
            name="审查者",
            system_prompt="""你是一个审查者。检查执行结果的质量。
检查：完整性、正确性、清晰度、可执行性。
如果质量达标，输出最终结果并标注 ROUTE: end。
如果需要改进，说明具体问题并标注 ROUTE: executor""",
        ),
    }
    
    # 构建图
    graph = LangGraphStyleGraph()
    for name, node in nodes.items():
        graph.add_node(name, node)
    
    graph.set_entry_point("analyzer")
    graph.add_edge("analyzer", "researcher")
    graph.add_edge("researcher", "planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "reviewer")
    graph.add_edge("reviewer", "executor", "需要改进")
    graph.add_edge("reviewer", "end", "最终结果")
    
    execute = graph.compile()
    
    state = execute({
        "user_input": "用 Python 写一个简单的 CLI 计算器，支持加减乘除和求幂",
    })
    
    return state


# ═══════════════════════════════════════════════════════════════
# 主程序
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("⚡ 框架风格对比：CrewAI vs LangGraph")
    print("=" * 60)
    
    # 风格 A
    results = demo_crewai_style()
    
    # 风格 B
    print("\n\n")
    state = demo_langgraph_style()
    
    print("\n" + "=" * 60)
    print("✅ 对比演示完成！")
    print("=" * 60)
    print("""
📊 CrewAI vs LangGraph 设计哲学对比：

| 维度 | CrewAI 风格 | LangGraph 风格 |
|------|------------|---------------|
| 抽象层次 | Agent + Task + Crew | Node + Edge + State |
| 编程模型 | 声明式（声明 Agent 和 Task） | 命令式（定义流转条件） |
| 流程表达 | 顺序/层级 | 有向图（支持循环） |
| 状态管理 | 隐式（上下文传递） | 显式（全局 State） |
| 学习曲线 | ⭐⭐（简单直观） | ⭐⭐⭐⭐（灵活但复杂） |
| 适合场景 | 固定流程的任务 | 复杂状态机、条件分支 |

选择建议：
- 不需要复杂分支 → 用 CrewAI 风格
- 需要条件判断和循环 → 用 LangGraph 风格
- 两者都需要 → 组合使用
    """)
