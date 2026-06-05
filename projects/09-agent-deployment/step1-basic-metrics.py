"""
step1-basic-metrics.py — Metrics 埋点 + Prometheus 格式

功能：
1. 核心 Metrics 定义（Counter、Histogram、Gauge）
2. Agent 请求的 Metrics 打点
3. 生成 Prometheus 格式输出
4. 可视化 Metrics 报告

运行：python step1-basic-metrics.py
"""

import time
import random
import json
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# Metrics 基础设施
# ============================================================

@dataclass
class Counter:
    """计数指标：只增不减"""
    name: str
    description: str
    value: int = 0

    def inc(self, amount: int = 1):
        self.value += amount

    def prometheus_format(self, labels: dict = None) -> str:
        help_line = f"# HELP {self.name} {self.description}"
        type_line = f"# TYPE {self.name} counter"
        labels_str = ""
        if labels:
            label_pairs = ",".join(f'{k}="{v}"' for k, v in labels.items())
            labels_str = f"{{{label_pairs}}}"
        value_line = f"{self.name}{labels_str} {self.value}"
        return f"{help_line}\n{type_line}\n{value_line}"


@dataclass
class Histogram:
    """直方图指标：延迟等分布数据"""
    name: str
    description: str
    buckets: list = field(default_factory=lambda: [10, 50, 100, 500, 1000, 5000])
    values: list = field(default_factory=list)

    def observe(self, value: float):
        self.values.append(value)

    def report_stats(self) -> dict:
        if not self.values:
            return {"count": 0, "min": 0, "max": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}
        sorted_vals = sorted(self.values)
        n = len(sorted_vals)
        return {
            "count": n,
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "avg": sum(sorted_vals) / n,
            "p50": sorted_vals[int(n * 0.5)],
            "p95": sorted_vals[int(n * 0.95)],
            "p99": sorted_vals[int(n * 0.99)],
        }

    def prometheus_format(self, labels: dict = None) -> list[str]:
        lines = []
        help_line = f"# HELP {self.name} {self.description}"
        type_line = f"# TYPE {self.name} histogram"
        lines.append(help_line)
        lines.append(type_line)

        labels_str = ""
        if labels:
            label_pairs = ",".join(f'{k}="{v}"' for k, v in labels.items())
            labels_str = f"{{{label_pairs}}}"

        # 每个 bucket 一行
        sorted_vals = sorted(self.values)
        bucket_counts = {}
        for b in self.buckets:
            bucket_counts[b] = sum(1 for v in sorted_vals if v <= b)

        for bucket, count in bucket_counts.items():
            lines.append(f'{self.name}_bucket{{le="{bucket}"{"," if labels else ""}{labels_str[1:-1] if labels_str else ""}}} {count}')

        lines.append(f'{self.name}_count{labels_str} {len(self.values)}')
        lines.append(f'{self.name}_sum{labels_str} {sum(self.values)}')
        return lines


@dataclass
class Gauge:
    """仪表指标：可增可减（当前值）"""
    name: str
    description: str
    value: float = 0.0

    def set(self, value: float):
        self.value = value

    def inc(self, amount: float = 1.0):
        self.value += amount

    def dec(self, amount: float = 1.0):
        self.value -= amount

    def prometheus_format(self, labels: dict = None) -> str:
        help_line = f"# HELP {self.name} {self.description}"
        type_line = f"# TYPE {self.name} gauge"
        labels_str = ""
        if labels:
            label_pairs = ",".join(f'{k}="{v}"' for k, v in labels.items())
            labels_str = f"{{{label_pairs}}}"
        value_line = f"{self.name}{labels_str} {self.value}"
        return f"{help_line}\n{type_line}\n{value_line}"


# ============================================================
# Agent Metrics 注册器
# ============================================================

class AgentMetrics:
    """Agent 的 Metrics 埋点集合"""

    def __init__(self):
        # 计数
        self.requests_total = Counter("agent_requests_total", "所有 Agent 请求总数")
        self.requests_success = Counter("agent_requests_success", "成功的 Agent 请求数")
        self.requests_failed = Counter("agent_requests_failed", "失败的 Agent 请求数")
        self.llm_calls_total = Counter("agent_llm_calls_total", "LLM 调用总数")
        self.tool_calls_total = Counter("agent_tool_calls_total", "工具调用总数")
        self.tokens_total = Counter("agent_tokens_total", "Token 消耗总数")

        # 延迟分布
        self.request_duration = Histogram(
            "agent_request_duration_ms", "请求延迟分布（毫秒）",
            buckets=[100, 500, 1000, 2000, 5000, 10000, 30000]
        )
        self.llm_duration = Histogram(
            "agent_llm_duration_ms", "LLM 调用延迟分布（毫秒）",
            buckets=[100, 500, 1000, 2000, 5000, 10000]
        )
        self.tool_duration = Histogram(
            "agent_tool_duration_ms", "工具调用延迟分布（毫秒）",
            buckets=[10, 50, 100, 500, 1000, 5000]
        )

        # 当前值
        self.concurrent_requests = Gauge("agent_concurrent_requests", "当前并发请求数")
        self.cost_total_usd = Gauge("agent_cost_total_usd", "累计 API 成本（美元）")
        self.uptime_seconds = Gauge("agent_uptime_seconds", "服务运行时长（秒）")

        self._start_time = time.time()

    def record_request(self, duration_ms: float, success: bool, cost: float = 0.0):
        """记录一次请求完成的 Metrics"""
        self.requests_total.inc()
        self.request_duration.observe(duration_ms)
        self.concurrent_requests.dec()

        if success:
            self.requests_success.inc()
        else:
            self.requests_failed.inc()

        if cost > 0:
            self.cost_total_usd.inc(cost)

    def record_llm_call(self, duration_ms: float, tokens: int, model: str):
        """记录一次 LLM 调用"""
        self.llm_calls_total.inc()
        self.llm_duration.observe(duration_ms)
        self.tokens_total.inc(tokens)

    def record_tool_call(self, duration_ms: float, tool_name: str):
        """记录一次工具调用"""
        self.tool_calls_total.inc()
        self.tool_duration.observe(duration_ms)

    def get_all_prometheus(self) -> str:
        """生成 Prometheus 格式的完整 Metrics 输出"""
        self.uptime_seconds.set(time.time() - self._start_time)

        lines = []
        for metric in [
            self.requests_total, self.requests_success, self.requests_failed,
            self.llm_calls_total, self.tool_calls_total, self.tokens_total,
        ]:
            lines.append(metric.prometheus_format())

        lines.extend(self.request_duration.prometheus_format())
        lines.extend(self.llm_duration.prometheus_format())
        lines.extend(self.tool_duration.prometheus_format())

        for gauge in [self.concurrent_requests, self.cost_total_usd, self.uptime_seconds]:
            lines.append(gauge.prometheus_format())

        return "\n".join(lines)

    def report_summary(self) -> str:
        """生成人类可读的 Metrics 摘要"""
        report = []
        report.append("=" * 50)
        report.append("📊 Agent Metrics 报告")
        report.append("=" * 50)

        report.append(f"\n📌 请求统计：")
        report.append(f"  总请求：{self.requests_total.value}")
        report.append(f"  成功：{self.requests_success.value}")
        report.append(f"  失败：{self.requests_failed.value}")
        success_rate = (self.requests_success.value / max(self.requests_total.value, 1)) * 100
        report.append(f"  成功率：{success_rate:.1f}%")

        report.append(f"\n📌 LLM 调用：")
        report.append(f"  总调用次数：{self.llm_calls_total.value}")
        report.append(f"  总 Token 消耗：{self.tokens_total.value}")
        stats = self.llm_duration.report_stats()
        report.append(f"  延迟：avg={stats['avg']:.0f}ms p50={stats['p50']:.0f}ms p95={stats['p95']:.0f}ms p99={stats['p99']:.0f}ms")

        report.append(f"\n📌 工具调用：")
        report.append(f"  总调用次数：{self.tool_calls_total.value}")
        stats = self.tool_duration.report_stats()
        report.append(f"  延迟：avg={stats['avg']:.0f}ms p50={stats['p50']:.0f}ms p95={stats['p95']:.0f}ms")

        report.append(f"\n📌 请求延迟：")
        stats = self.request_duration.report_stats()
        report.append(f"  avg={stats['avg']:.0f}ms p50={stats['p50']:.0f}ms p95={stats['p95']:.0f}ms p99={stats['p99']:.0f}ms")

        report.append(f"\n📌 成本：")
        report.append(f"  累计成本：${self.cost_total_usd.value:.4f}")
        avg_cost = self.cost_total_usd.value / max(self.requests_total.value, 1)
        report.append(f"  平均每次请求成本：${avg_cost:.4f}")

        uptime = time.time() - self._start_time
        report.append(f"\n📌 运行时间：{uptime:.0f} 秒")

        return "\n".join(report)


# ============================================================
# 模拟 Agent 运行
# ============================================================

def simulate_agent(metrics: AgentMetrics, num_requests: int = 10):
    """模拟多轮 Agent 请求并埋点"""
    models = ["gpt-4o-mini", "gpt-4o"]
    tools = ["query_database", "read_file", "calculate", "search_web"]

    for i in range(num_requests):
        metrics.concurrent_requests.inc()
        request_start = time.time()

        # 模拟 Agent 循环（1-3 轮 LLM 调用）
        loops = random.randint(1, 3)
        request_success = True
        total_cost = 0.0

        for loop in range(loops):
            # LLM 调用
            model = random.choice(models)
            llm_latency = random.uniform(200, 3000)
            tokens = random.randint(100, 2000)
            metrics.record_llm_call(llm_latency, tokens, model)

            # Token 成本估算
            input_tokens = tokens // 2
            output_tokens = tokens - input_tokens
            if model == "gpt-4o-mini":
                cost = (input_tokens / 1000 * 0.00015 + output_tokens / 1000 * 0.0006)
            else:
                cost = (input_tokens / 1000 * 0.0025 + output_tokens / 1000 * 0.01)
            total_cost += cost

            # 工具调用（除了最后一次循环）
            if loop < loops - 1:
                tool = random.choice(tools)
                tool_latency = random.uniform(50, 1500)
                metrics.record_tool_call(tool_latency, tool)

            # 模拟 5% 的失败率
            if random.random() < 0.05:
                request_success = False

        # 请求完成
        total_duration = (time.time() - request_start) * 1000
        metrics.record_request(total_duration, request_success, total_cost)

        print(f"  请求 {i+1:2d}: {'✅' if request_success else '❌'} "
              f"{loops} 轮 | {total_duration:.0f}ms | ${total_cost:.4f}")


# ============================================================
# 运行演示
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("📊 Agent Metrics 演示")
    print("=" * 50)

    metrics = AgentMetrics()

    print(f"\n模拟 20 个 Agent 请求...")
    print("-" * 50)
    simulate_agent(metrics, 20)

    print("\n" + metrics.report_summary())

    print("\n" + "=" * 50)
    print("📋 Prometheus 格式输出（前 15 行）")
    print("=" * 50)
    prom_output = metrics.get_all_prometheus()
    for line in prom_output.split("\n")[:15]:
        print(f"  {line}")
    print(f"  ...（共 {len(prom_output.split(chr(10)))} 行）")

    print("\n" + "=" * 50)
    print("📝 关键总结")
    print("=" * 50)
    print("""
📊 Metrics 三大类型：
  - Counter（计数器）：请求数、Token 数、错误数（只增不减）
  - Histogram（直方图）：延迟分布、大小分布（P50/P95/P99）
  - Gauge（仪表）：并发数、运行时间（可增可减）

🔑 最佳实践：
  1. 每个 LLM 调用都要埋点（模型、Token、延迟）
  2. 每个工具调用都要埋点（工具名、延迟、结果）
  3. 按标签区分（按模型、按用户、按工具）
  4. 关注 P95/P99 而不是平均值
""")
