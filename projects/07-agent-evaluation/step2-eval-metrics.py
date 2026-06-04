"""
Step 2: 多维度评估指标
=========================
功能：分层指标体系、可插拔指标注册器、加权汇总
概念：组件级 → 任务级 → 系统级
"""

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


# ============================================================
# 1. 指标注册器（可插拔设计）
# ============================================================

class MetricRegistry:
    """指标注册器 — 支持动态注册和查询"""

    def __init__(self):
        self._metrics: Dict[str, Callable] = {}

    def register(self, name: str, fn: Callable):
        """注册一个指标计算函数"""
        self._metrics[name] = fn

    def unregister(self, name: str):
        """注销指标"""
        self._metrics.pop(name, None)

    def compute(self, name: str, **kwargs) -> float:
        """计算指定指标"""
        if name not in self._metrics:
            raise ValueError(f"未知指标: {name}")
        return self._metrics[name](**kwargs)

    def compute_all(self, **kwargs) -> Dict[str, float]:
        """计算所有注册的指标"""
        return {
            name: fn(**kwargs)
            for name, fn in self._metrics.items()
        }

    def list_metrics(self) -> List[str]:
        """列出所有已注册的指标"""
        return list(self._metrics.keys())


# ============================================================
# 2. 核心指标函数
# ============================================================

# ---- 组件级指标 ----

def tool_selection_accuracy(true_positives: int, false_positives: int,
                            false_negatives: int) -> float:
    """工具选择准确率（精确率）"""
    total = true_positives + false_positives
    return true_positives / max(total, 1)


def tool_param_accuracy(correct_params: int, total_params: int) -> float:
    """工具参数填充准确率"""
    return correct_params / max(total_params, 1)


def retrieval_recall(relevant_retrieved: int, total_relevant: int) -> float:
    """检索召回率 - 相关文档被检索到的比例"""
    return relevant_retrieved / max(total_relevant, 1)


def retrieval_precision(relevant_retrieved: int, total_retrieved: int) -> float:
    """检索精确率 - 检索结果中相关文档的比例"""
    return relevant_retrieved / max(total_retrieved, 1)


# ---- 任务级指标 ----

def task_success_rate(success_count: int, total_count: int) -> float:
    """任务成功率"""
    return success_count / max(total_count, 1)


def average_steps(total_steps: int, task_count: int) -> float:
    """平均步数（效率指标 — 越少越好）"""
    return total_steps / max(task_count, 1)


def average_cost(total_tokens: int, task_count: int) -> float:
    """平均 Token 消耗（成本指标）"""
    return total_tokens / max(task_count, 1)


def f1_score(precision: float, recall: float) -> float:
    """F1 分数"""
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def hallucination_rate(hallucinated_statements: int,
                       total_statements: int) -> float:
    """幻觉率（越低越好）"""
    return hallucinated_statements / max(total_statements, 1)


def error_recovery_rate(recovered_errors: int, total_errors: int) -> float:
    """错误恢复率"""
    return recovered_errors / max(total_errors, 1)


# ---- 系统级指标 ----

def throughput(tasks_completed: int, total_time_seconds: float) -> float:
    """吞吐量 — 每秒完成任务数"""
    return tasks_completed / max(total_time_seconds, 0.001)


def avg_response_time(total_time_seconds: float,
                      task_count: int) -> float:
    """平均响应时间（秒）"""
    return total_time_seconds / max(task_count, 1)


def cost_per_task(total_cost: float, task_count: int) -> float:
    """每任务成本（美元或积分）"""
    return total_cost / max(task_count, 1)


# ============================================================
# 3. 评估上下文（跟踪评估过程中产生的数据）
# ============================================================

@dataclass
class EvalContext:
    """评估上下文 — 收集评估过程中所有数据"""
    # 组件级
    tool_calls: List[dict] = field(default_factory=list)        # [{tool, params, success}]
    retrieval_results: List[dict] = field(default_factory=list)  # [{query, docs, relevant}]

    # 任务级
    tasks: List[dict] = field(default_factory=list)              # [{input, output, steps, tokens, success}]

    # 系统级
    start_time: float = 0.0
    end_time: float = 0.0
    total_cost: float = 0.0

    def add_tool_call(self, tool_name: str, params: dict,
                      success: bool, correct_tool: bool = True,
                      correct_params: bool = True):
        self.tool_calls.append({
            "tool": tool_name,
            "params": params,
            "success": success,
            "correct_tool": correct_tool,
            "correct_params": correct_params,
        })

    def add_retrieval(self, query: str, retrieved_docs: List[str],
                      relevant_docs: List[str]):
        self.retrieval_results.append({
            "query": query,
            "retrieved_docs": retrieved_docs,
            "relevant_docs": relevant_docs,
            "num_relevant_retrieved": len(
                set(retrieved_docs) & set(relevant_docs)
            ),
        })

    def add_task(self, input_text: str, output_text: str,
                 success: bool, steps: int = 1, tokens: int = 0):
        self.tasks.append({
            "input": input_text,
            "output": output_text,
            "success": success,
            "steps": steps,
            "tokens": tokens,
        })

    def start(self):
        self.start_time = time.time()

    def stop(self):
        self.end_time = time.time()

    @property
    def elapsed(self) -> float:
        if self.end_time > 0:
            return self.end_time - self.start_time
        return time.time() - self.start_time


# ============================================================
# 4. 分层评估器
# ============================================================

class AgentEvaluator:
    """
    分层评估器 — 组件级 → 任务级 → 系统级
    支持自定义权重和指标扩展
    """

    def __init__(self):
        self.registry = MetricRegistry()
        self._setup_default_metrics()
        # 分层权重配置
        self.weights = {
            "component": 0.3,  # 组件级权重
            "task": 0.4,       # 任务级权重
            "system": 0.3,     # 系统级权重
        }

    def _setup_default_metrics(self):
        """注册默认指标"""
        # 组件级
        self.registry.register("tool_selection_accuracy", tool_selection_accuracy)
        self.registry.register("tool_param_accuracy", tool_param_accuracy)
        self.registry.register("retrieval_recall", retrieval_recall)
        self.registry.register("retrieval_precision", retrieval_precision)

        # 任务级
        self.registry.register("task_success_rate", task_success_rate)
        self.registry.register("average_steps", average_steps)
        self.registry.register("average_cost", average_cost)
        self.registry.register("f1_score", f1_score)
        self.registry.register("hallucination_rate", hallucination_rate)
        self.registry.register("error_recovery_rate", error_recovery_rate)

        # 系统级
        self.registry.register("throughput", throughput)
        self.registry.register("avg_response_time", avg_response_time)
        self.registry.register("cost_per_task", cost_per_task)

    def evaluate_component_level(self, ctx: EvalContext) -> Dict[str, float]:
        """评估组件级指标"""
        metrics = {}

        # 工具使用
        if ctx.tool_calls:
            correct_tools = sum(
                1 for tc in ctx.tool_calls if tc["correct_tool"]
            )
            correct_params = sum(
                1 for tc in ctx.tool_calls if tc["correct_params"]
            )
            total = len(ctx.tool_calls)

            metrics["tool_selection_accuracy"] = self.registry.compute(
                "tool_selection_accuracy",
                true_positives=correct_tools,
                false_positives=total - correct_tools,
                false_negatives=0,
            )
            metrics["tool_param_accuracy"] = self.registry.compute(
                "tool_param_accuracy",
                correct_params=correct_params,
                total_params=total,
            )

        # 检索质量
        if ctx.retrieval_results:
            total_relevant_retrieved = sum(
                r["num_relevant_retrieved"] for r in ctx.retrieval_results
            )
            total_retrieved = sum(
                len(r["retrieved_docs"]) for r in ctx.retrieval_results
            )
            total_relevant = sum(
                len(r["relevant_docs"]) for r in ctx.retrieval_results
            )

            metrics["retrieval_recall"] = self.registry.compute(
                "retrieval_recall",
                relevant_retrieved=total_relevant_retrieved,
                total_relevant=total_relevant,
            )
            metrics["retrieval_precision"] = self.registry.compute(
                "retrieval_precision",
                relevant_retrieved=total_relevant_retrieved,
                total_retrieved=total_retrieved,
            )

        return metrics

    def evaluate_task_level(self, ctx: EvalContext) -> Dict[str, float]:
        """评估任务级指标"""
        metrics = {}
        tasks = ctx.tasks

        if not tasks:
            return metrics

        success_count = sum(1 for t in tasks if t["success"])
        total_count = len(tasks)
        total_steps = sum(t["steps"] for t in tasks)
        total_tokens = sum(t["tokens"] for t in tasks)

        metrics["task_success_rate"] = self.registry.compute(
            "task_success_rate",
            success_count=success_count,
            total_count=total_count,
        )
        metrics["average_steps"] = self.registry.compute(
            "average_steps",
            total_steps=total_steps,
            task_count=total_count,
        )
        metrics["average_cost"] = self.registry.compute(
            "average_cost",
            total_tokens=total_tokens,
            task_count=total_count,
        )

        # 效率评分：步数越少越好（假设最坏 20 步）
        max_steps = 20
        metrics["efficiency_score"] = max(
            0, 1 - (metrics["average_steps"] / max_steps)
        )

        return metrics

    def evaluate_system_level(self, ctx: EvalContext) -> Dict[str, float]:
        """评估系统级指标"""
        metrics = {}

        tasks = ctx.tasks
        if not tasks:
            return metrics

        elapsed = ctx.elapsed
        task_count = len(tasks)

        metrics["throughput"] = self.registry.compute(
            "throughput",
            tasks_completed=task_count,
            total_time_seconds=elapsed,
        )
        metrics["avg_response_time"] = self.registry.compute(
            "avg_response_time",
            total_time_seconds=elapsed,
            task_count=task_count,
        )
        metrics["cost_per_task"] = self.registry.compute(
            "cost_per_task",
            total_cost=ctx.total_cost,
            task_count=task_count,
        )

        # 综合系统效率评分（归一化）
        # 假设 1 秒/任务的基准
        baseline_time = 1.0
        metrics["system_efficiency"] = max(
            0, 1 - (metrics["avg_response_time"] / baseline_time * 0.5)
        )

        return metrics

    def compute_overall_score(self, component: Dict[str, float],
                               task: Dict[str, float],
                               system: Dict[str, float]) -> float:
        """计算综合评分"""
        # 取各层指标均值
        comp_avg = sum(component.values()) / max(len(component), 1)
        task_avg = sum(task.values()) / max(len(task), 1)
        sys_avg = sum(system.values()) / max(len(system), 1)

        # 加权汇总
        overall = (
            comp_avg * self.weights["component"]
            + task_avg * self.weights["task"]
            + sys_avg * self.weights["system"]
        )
        return overall


# ============================================================
# 5. 演示运行
# ============================================================

def main():
    print("🧪 Agent 评估系统 — Step 2: 多维度评估指标\n")

    # 初始化
    ctx = EvalContext()
    ctx.start()

    evaluator = AgentEvaluator()

    # 模拟评估数据
    print("📝 收集评估数据...")

    # 工具调用数据
    ctx.add_tool_call("search", {"query": "北京天气"}, success=True,
                      correct_tool=True, correct_params=True)
    ctx.add_tool_call("calculator", {"a": 15, "b": 27}, success=True,
                      correct_tool=True, correct_params=True)
    ctx.add_tool_call("email", {"to": "user"}, success=True,
                      correct_tool=False, correct_params=False)
    ctx.add_tool_call("search", {"query": "AI Agent"}, success=False,
                      correct_tool=True, correct_params=True)

    print(f"  工具调用: {len(ctx.tool_calls)} 次")

    # 检索数据
    ctx.add_retrieval(
        query="AI Agent 是什么",
        retrieved_docs=["doc1_agent_intro", "doc2_architecture", "doc3_prompt"],
        relevant_docs=["doc1_agent_intro", "doc2_architecture", "doc5_examples"],
    )
    ctx.add_retrieval(
        query="北京明天天气",
        retrieved_docs=["doc4_weather_beijing", "doc6_weather_shanghai"],
        relevant_docs=["doc4_weather_beijing"],
    )

    print(f"  检索查询: {len(ctx.retrieval_results)} 次")

    # 任务数据
    ctx.add_task("查询天气", "北京天气晴朗 25°C", success=True, steps=2, tokens=500)
    ctx.add_task("计算 15+27", "42", success=True, steps=1, tokens=300)
    ctx.add_task("搜索 AI Agent 信息", "AI Agent 是...", success=True, steps=3, tokens=800)
    ctx.add_task("发送邮件给", "发送失败：参数错误", success=False, steps=2, tokens=400)

    print(f"  任务执行: {len(ctx.tasks)} 个 (成功: {sum(1 for t in ctx.tasks if t['success'])}/4)")

    ctx.stop()

    # 分层评估
    print("\n📊 分层评估结果")
    print("=" * 60)

    component_metrics = evaluator.evaluate_component_level(ctx)
    print("\n🟢 组件级指标:")
    for name, value in sorted(component_metrics.items()):
        print(f"  {name:30s} = {value:.2%}" if isinstance(value, float) and value <= 1
              else f"  {name:30s} = {value:.2f}")

    task_metrics = evaluator.evaluate_task_level(ctx)
    print("\n🔵 任务级指标:")
    for name, value in sorted(task_metrics.items()):
        print(f"  {name:30s} = {value:.2%}" if isinstance(value, float) and value <= 1
              else f"  {name:30s} = {value:.2f}")

    system_metrics = evaluator.evaluate_system_level(ctx)
    print("\n🟣 系统级指标:")
    for name, value in sorted(system_metrics.items()):
        print(f"  {name:30s} = {value:.2f}")

    # 综合评分
    overall = evaluator.compute_overall_score(
        component_metrics, task_metrics, system_metrics
    )

    print("\n" + "=" * 60)
    print(f"🏆 加权综合评分: {overall:.2%}")
    print(f"   组件级权重: {evaluator.weights['component']:.0%} "
          f"| 任务级权重: {evaluator.weights['task']:.0%} "
          f"| 系统级权重: {evaluator.weights['system']:.0%}")
    print(f"   运行时间: {ctx.elapsed:.2f}s")
    print("=" * 60)

    # 列出可用指标
    print(f"\n📋 已注册指标 ({len(evaluator.registry.list_metrics())} 个):")
    for m in evaluator.registry.list_metrics():
        print(f"  • {m}")


if __name__ == "__main__":
    main()
