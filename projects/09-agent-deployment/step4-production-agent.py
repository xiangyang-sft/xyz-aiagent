"""
step4-production-agent.py — 完整的可观测 Agent

集成本节所有生产化部署要素：
1. Metrics 埋点（Counter + Histogram + Gauge）
2. 全链路追踪（Span 树）
3. 结构化日志（JSON + 事件分类）
4. 成本追踪与优化
5. 健康检查

运行：python step4-production-agent.py
"""

import time
import json
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ============================================================
# 1. Metrics 基础设施
# ============================================================

class Counter:
    def __init__(self, name: str):
        self.name = name
        self.value = 0
    def inc(self, n: int = 1): self.value += n

class Histogram:
    def __init__(self, name: str, buckets: list = None):
        self.name = name
        self.buckets = buckets or [10, 50, 100, 500, 1000, 5000, 10000]
        self.values = []
    def observe(self, v: float): self.values.append(v)
    def stats(self) -> dict:
        if not self.values: return {}
        s = sorted(self.values)
        n = len(s)
        return {"count": n, "avg": sum(s)/n, "p50": s[int(n*.5)], "p95": s[int(n*.95)], "p99": s[int(n*.99)]}

class Gauge:
    def __init__(self, name: str): self.name = name; self.value = 0.0
    def set(self, v): self.value = v
    def inc(self, v=1.0): self.value += v
    def dec(self, v=1.0): self.value -= v


# ============================================================
# 2. 追踪基础设施
# ============================================================

@dataclass
class Span:
    name: str
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    start: float
    end: Optional[float] = None
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)
    status: str = "OK"

    @property
    def duration_ms(self) -> float:
        return (self.end - self.start) * 1000 if self.end else 0

    def finish(self, status: str = "OK"):
        self.end = time.time()
        self.status = status


class Tracer:
    def __init__(self):
        self._traces: list[Span] = []

    def start_trace(self, name: str = "agent_request") -> Span:
        tid = uuid.uuid4().hex[:12]
        root = Span(name=name, span_id=tid, trace_id=tid, parent_span_id=None, start=time.time())
        self._traces.append(root)
        return root

    def start_span(self, parent: Span, name: str) -> Span:
        span = Span(name=name, span_id=uuid.uuid4().hex[:8],
                    trace_id=parent.trace_id, parent_span_id=parent.span_id,
                    start=time.time())
        parent.children.append(span)
        return span


# ============================================================
# 3. 结构化日志
# ============================================================

class AgentLogger:
    def __init__(self):
        self._logs: list[dict] = []

    def _log(self, level: str, msg: str, **kw):
        entry = {"t": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                 "lvl": level, "msg": msg, **kw}
        self._logs.append(entry)
        # 控制台输出（生产环境应该发到 Loki/Splunk）
        preview = json.dumps({k: v for k, v in entry.items()
                              if k != "input_raw" and k != "output_raw"}, ensure_ascii=False, default=str)
        if level in ("WARN", "ERROR"):
            print(f"  ⚠️  LOG {level}: {preview[:150]}...")
        elif level == "DEBUG":
            print(f"  · DEBUG: {msg}")
        return entry

    def info(self, msg, **kw): return self._log("INFO", msg, **kw)
    def warn(self, msg, **kw): return self._log("WARN", msg, **kw)
    def error(self, msg, **kw): return self._log("ERROR", msg, **kw)
    def debug(self, msg, **kw): return self._log("DEBUG", msg, **kw)


# ============================================================
# 4. Agent 可观测性封装
# ============================================================

# 模型定价（每 1K Token，美元）
MODEL_PRICING = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "claude-sonnet-4": {"input": 0.003, "output": 0.015},
}


class ObservableAgent:
    """
    完整可观测的 Agent
    集成本节所有生产化要素
    """

    def __init__(self, agent_name: str = "production-agent"):
        self.name = agent_name
        self._start_time = time.time()

        # Metrics
        self.metrics = {
            "requests_total": Counter("requests_total"),
            "requests_success": Counter("requests_success"),
            "requests_failed": Counter("requests_failed"),
            "llm_calls_total": Counter("llm_calls_total"),
            "tool_calls_total": Counter("tool_calls_total"),
            "tokens_total": Counter("tokens_total"),
            "request_duration": Histogram("request_duration_ms"),
            "llm_duration": Histogram("llm_duration_ms"),
            "tool_duration": Histogram("tool_duration_ms"),
            "concurrent_requests": Gauge("concurrent_requests"),
            "cost_total": Gauge("cost_total_usd"),
        }

        # 日志
        self.logger = AgentLogger()

        # 追踪
        self.tracer = Tracer()

    def handle_request(self, user_input: str, user_id: str = "anonymous",
                       max_loops: int = 3) -> dict:
        """
        处理一次完整的 Agent 请求（全量可观测埋点）
        """
        # 开始追踪
        root_span = self.tracer.start_trace("agent_request")
        root_span.attrs["user_input"] = user_input[:50]
        root_span.attrs["user_id"] = user_id

        self.metrics["concurrent_requests"].inc()
        self.metrics["requests_total"].inc()
        request_start = time.time()

        # 日志：请求开始
        trace_id = root_span.trace_id
        self.logger.info("request_started", trace_id=trace_id,
                        user_id=user_id, input_len=len(user_input))

        total_tokens = 0
        total_cost = 0.0
        success = True
        tool_history = []

        try:
            # === Agent 循环 ===
            for loop in range(max_loops):
                # LLM 调用
                llm_span = self.tracer.start_span(root_span, f"llm_reason_{loop}")
                model = "gpt-4o-mini" if loop == 0 else "gpt-4o"

                llm_start = time.time()
                # 模拟 LLM 延迟
                llm_latency = random.uniform(300, 600)
                time.sleep(llm_latency / 1000)  # 真实的 sleep（缩短了）

                input_tokens = random.randint(200, 1000)
                output_tokens = random.randint(50, 400)
                loop_tokens = input_tokens + output_tokens
                total_tokens += loop_tokens

                # 成本计算
                pricing = MODEL_PRICING.get(model, {"input": 0.001, "output": 0.005})
                loop_cost = (input_tokens / 1000 * pricing["input"] +
                            output_tokens / 1000 * pricing["output"])
                total_cost += loop_cost

                # Metrics 埋点
                self.metrics["llm_calls_total"].inc()
                self.metrics["llm_duration"].observe(llm_latency)
                self.metrics["tokens_total"].inc(loop_tokens)
                self.metrics["cost_total"].inc(loop_cost)

                # Span 属性
                llm_span.attrs.update({
                    "model": model, "input_tokens": input_tokens,
                    "output_tokens": output_tokens, "cost_usd": round(loop_cost, 5),
                    "loop_iteration": loop,
                })
                llm_span.finish()

                # 日志
                self.logger.info(f"llm_call_{loop}", trace_id=trace_id,
                                model=model, tokens=loop_tokens,
                                latency_ms=round(llm_latency, 2),
                                cost=round(loop_cost, 5))

                # 最后一步不需要工具
                if loop == max_loops - 1:
                    break

                # 工具调用
                tool_name = random.choice(["query_database", "read_file",
                                          "search_web", "calculate"])
                tool_span = self.tracer.start_span(root_span, f"tool_{tool_name}")

                tool_start = time.time()
                tool_latency = random.uniform(50, 300)
                time.sleep(tool_latency / 1000)

                tool_success = random.random() > 0.05  # 95% 成功率
                self.metrics["tool_calls_total"].inc()
                self.metrics["tool_duration"].observe(tool_latency)

                tool_span.attrs.update({
                    "tool": tool_name, "success": tool_success,
                    "latency_ms": round(tool_latency, 2),
                })
                tool_span.finish()

                tool_history.append(tool_name)

                # 日志
                log_fn = self.logger.info if tool_success else self.logger.warn
                log_fn(f"tool_call_{tool_name}", trace_id=trace_id,
                      tool=tool_name, success=tool_success,
                      latency_ms=round(tool_latency, 2))

                if not tool_success:
                    # 工具失败重试
                    self.logger.warn(f"retry_same_tool", trace_id=trace_id,
                                    tool=tool_name, reason="transient_error")

            # 请求成功
            request_duration = (time.time() - request_start) * 1000
            self.metrics["requests_success"].inc()
            self.metrics["request_duration"].observe(request_duration)
            self.metrics["concurrent_requests"].dec()

        except Exception as e:
            request_duration = (time.time() - request_start) * 1000
            self.metrics["requests_failed"].inc()
            self.metrics["request_duration"].observe(request_duration)
            self.metrics["concurrent_requests"].dec()
            success = False
            self.logger.error("request_failed", trace_id=trace_id,
                            error=str(e), duration_ms=round(request_duration, 2))

        # Root Span 完成
        root_span.finish("OK" if success else "ERROR")
        root_span.attrs.update({
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 5),
            "total_duration_ms": round((time.time() - request_start) * 1000, 2),
            "success": success,
            "tools_used": ",".join(tool_history),
        })

        # 日志：请求完成
        self.logger.info("request_completed", trace_id=trace_id,
                        duration_ms=round((time.time() - request_start) * 1000, 2),
                        success=success, tokens=total_tokens, cost=round(total_cost, 5))

        return {
            "trace_id": trace_id,
            "success": success,
            "tokens": total_tokens,
            "cost_usd": round(total_cost, 5),
            "latency_ms": round((time.time() - request_start) * 1000, 2),
            "tools_used": tool_history,
        }

    def health_check(self) -> dict:
        """健康检查端点"""
        uptime = time.time() - self._start_time
        duration_stats = self.metrics["request_duration"].stats()
        total = self.metrics["requests_total"].value
        failed = self.metrics["requests_failed"].value
        success_rate = ((total - failed) / max(total, 1)) * 100

        return {
            "service": self.name,
            "status": "healthy" if success_rate > 95 else "degraded",
            "uptime_seconds": round(uptime),
            "uptime_human": f"{uptime/3600:.1f}h",
            "metrics_summary": {
                "total_requests": total,
                "success_rate": f"{success_rate:.1f}%",
                "p50_latency_ms": duration_stats.get("p50", 0),
                "p95_latency_ms": duration_stats.get("p95", 0),
                "total_tokens": self.metrics["tokens_total"].value,
                "total_cost": round(self.metrics["cost_total"].value, 4),
                "avg_cost_per_request": round(self.metrics["cost_total"].value / max(total, 1), 5),
            },
            "checks": {
                "llm_api": "ok",
                "tools": "ok",
                "memory_store": "ok",
                "cache": "ok",
            }
        }

    def metrics_report(self) -> str:
        """Metrics 报告"""
        lines = ["=" * 50, "📊 生产 Agent Metrics 报告", "=" * 50]

        total = self.metrics["requests_total"].value
        success = self.metrics["requests_success"].value
        failed = self.metrics["requests_failed"].value
        rate = (success / max(total, 1)) * 100

        lines.append(f"\n📌 请求统计：")
        lines.append(f"  总请求：{total} | 成功：{success} | 失败：{failed} | 成功率：{rate:.1f}%")

        lines.append(f"\n📌 LLM 调用：")
        lines.append(f"  总次数：{self.metrics['llm_calls_total'].value}")
        s = self.metrics["llm_duration"].stats()
        lines.append(f"  延迟：avg={s.get('avg',0):.0f} p50={s.get('p50',0):.0f} p95={s.get('p95',0):.0f}ms")
        lines.append(f"  总 Token：{self.metrics['tokens_total'].value}")

        lines.append(f"\n📌 工具调用：")
        lines.append(f"  总次数：{self.metrics['tool_calls_total'].value}")
        s = self.metrics["tool_duration"].stats()
        lines.append(f"  延迟：avg={s.get('avg',0):.0f} p50={s.get('p50',0):.0f}ms")

        lines.append(f"\n📌 请求延迟：")
        s = self.metrics["request_duration"].stats()
        lines.append(f"  avg={s.get('avg',0):.0f} p50={s.get('p50',0):.0f} p95={s.get('p95',0):.0f} p99={s.get('p99',0):.0f}ms")

        lines.append(f"\n💰 成本：")
        total_cost = self.metrics["cost_total"].value
        lines.append(f"  总成本：${total_cost:.4f}")
        lines.append(f"  平均/请求：${total_cost / max(total, 1):.5f}")

        return "\n".join(lines)


# ============================================================
# 演示
# ============================================================

def demo():
    print("=" * 60)
    print("🚀 生产级可观测 Agent 演示")
    print("=" * 60)
    print()

    agent = ObservableAgent("agent-prod-v1")

    # 模拟 15 个请求
    queries = [
        "查询昨天的销售数据",
        "帮我分析用户留存率变化",
        "生成上周的运营报告",
        "搜索最新的 AI Agent 论文",
        "这个数据源有点可疑...",
        "计算 Q2 平均客单价",
        "读取市场调研文档",
        "对比 A/B 测试结果",
        "帮我发一封邮件给团队",
        "查询竞品价格变动",
        "分析用户评论情感倾向",
        "用 R 语言画个数据图",
        "翻译这个技术文档",
        "帮我检查一下代码格式",
        "总结今天的待办事项",
    ]

    print(f"模拟 {len(queries)} 个完整 Agent 请求...\n")
    print(f"{'#':<4} {'用户请求':<30} {'结果':<5} {'Token':<7} {'成本':<10} {'延迟(ms)':<10} {'工具':<20}")
    print("-" * 90)

    for i, query in enumerate(queries):
        result = agent.handle_request(query, user_id=f"user_{(i % 5) + 1:03d}")
        status = "✅" if result["success"] else "❌"
        tools = ", ".join(result["tools_used"]) if result["tools_used"] else "-"
        print(f" {i+1:<3} {query:<28} {status:<5} "
              f"{result['tokens']:<7} ${result['cost_usd']:<8.5f} "
              f"{result['latency_ms']:<10.0f} {tools:<20}")

    # 健康检查
    print("\n" + "=" * 60)
    print("🏥 健康检查")
    print("=" * 60)
    health = agent.health_check()
    print(f"\n状态：{'🟢' if health['status'] == 'healthy' else '🟡'} {health['status']}")
    print(f"运行时间：{health['uptime_human']}")
    print(f"成功率：{health['metrics_summary']['success_rate']}")
    print(f"总成本：${health['metrics_summary']['total_cost']}")
    for name, status in health["checks"].items():
        print(f"  • {name}: {'✅' if status == 'ok' else '❌'} {status}")

    # Metrics 报告
    print("\n" + agent.metrics_report())

    # 追踪树
    print("\n" + "=" * 60)
    print("🔍 最后一个请求的追踪树")
    print("=" * 60)
    last_trace = agent.tracer._traces[-1]
    duration = last_trace.duration_ms

    def print_tree(span, indent="", is_last=True):
        icon = "└── " if is_last else "├── "
        attrs = ", ".join(f"{k}={v}" for k, v in span.attrs.items()
                         if k in ("model", "tool", "success"))
        attrs_str = f" [{attrs}]" if attrs else ""
        print(f"{indent}{icon}{span.name} ({span.duration_ms:.0f}ms){attrs_str}")
        child_indent = indent + ("    " if is_last else "│   ")
        children = span.children
        for i, child in enumerate(children):
            print_tree(child, child_indent, i == len(children) - 1)

    print_tree(last_trace)
    print(f"总耗时：{duration:.0f}ms | {len(last_trace.children)} 个子 Span")


if __name__ == "__main__":
    demo()

    print("\n" + "=" * 60)
    print("🏆 生产化部署总结")
    print("=" * 60)
    print("""
✅ 本节课 4 个递进步骤全部实现：

Step 1 (step1-basic-metrics.py)
  → Counter + Histogram + Gauge 三种 Metrics 类型
  → Prometheus 格式输出
  → 延迟分布（P50/P95/P99）

Step 2 (step2-tracing.py)
  → Span 树结构（Root → LLM → Tool → LLM → 回答）
  → 火焰图格式数据
  → 追踪 JSON 导出

Step 3 (step3-structured-logging.py)
  → JSON 结构化日志
  → Agent 专用事件类型
  → 日志分析报告

Step 4 (step4-production-agent.py)
  → 完整可观测 Agent
  → Metrics + Traces + Logs 三合一
  → 成本追踪 + 健康检查

🔑 核心启示：
  可观测性不是监控工具的问题，是代码设计的问题。
  从一开始就埋点，比事后加可观测性容易 10 倍。
""")
