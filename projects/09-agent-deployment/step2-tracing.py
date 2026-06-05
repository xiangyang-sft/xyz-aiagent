"""
step2-tracing.py — OpenTelemetry 风格的 Span 树追踪

功能：
1. 模拟 OpenTelemetry 的 Span 树结构
2. 完整的 Agent 请求追踪（root → llm → tool → llm → 回答）
3. 追踪可视化（树形图 + 火焰图格式）
4. 依赖图生成

注意：这是一个纯 Python 模拟的追踪演示
实际生产使用 opentelemetry-sdk 包

运行：python step2-tracing.py
"""

import time
import json
import random
import uuid
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# 追踪核心数据结构
# ============================================================

@dataclass
class Span:
    """
    一个追踪单元（类似 OpenTelemetry 的 Span）
    """
    name: str
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    start_time: float
    end_time: Optional[float] = None
    attributes: dict = field(default_factory=dict)
    status: str = "OK"  # OK / ERROR
    children: list = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0

    def end(self, status: str = "OK"):
        self.end_time = time.time()
        self.status = status

    def set_attribute(self, key: str, value):
        self.attributes[key] = value


@dataclass
class Trace:
    """
    完整的一次追踪（一次 Agent 请求）
    """
    trace_id: str
    root_span: Span
    all_spans: list = field(default_factory=list)

    def add_span(self, span: Span):
        self.all_spans.append(span)

    @property
    def total_duration_ms(self) -> float:
        return self.root_span.duration_ms


# ============================================================
# Tracer（类似 OpenTelemetry TracerProvider）
# ============================================================

class Tracer:
    """追踪器——创建和管理 Span"""

    def __init__(self, service_name: str = "agent-service"):
        self.service_name = service_name
        self.traces: list[Trace] = []

    def start_trace(self, name: str = "agent_request") -> Trace:
        """开始一个新追踪"""
        trace_id = self._gen_id()
        span_id = self._gen_id()
        root_span = Span(
            name=name,
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=None,
            start_time=time.time(),
        )
        trace = Trace(trace_id=trace_id, root_span=root_span)
        trace.add_span(root_span)
        self.traces.append(trace)
        return trace

    def start_span(self, trace: Trace, name: str, parent_span: Span) -> Span:
        """在追踪中创建子 Span"""
        span = Span(
            name=name,
            span_id=self._gen_id(),
            trace_id=trace.trace_id,
            parent_span_id=parent_span.span_id,
            start_time=time.time(),
        )
        parent_span.children.append(span)
        trace.add_span(span)
        return span

    def _gen_id(self) -> str:
        return uuid.uuid4().hex[:16]

    def trace_to_dict(self, trace: Trace) -> dict:
        """将追踪转为字典（类似实际 Opentelemetry 的导出格式）"""
        spans_data = []
        for span in trace.all_spans:
            spans_data.append({
                "trace_id": span.trace_id,
                "span_id": span.span_id,
                "parent_span_id": span.parent_span_id or "",
                "name": span.name,
                "start_time": span.start_time,
                "end_time": span.end_time or time.time(),
                "duration_ms": round(span.duration_ms, 2),
                "attributes": span.attributes,
                "status": span.status,
            })
        return {
            "trace_id": trace.trace_id,
            "service": self.service_name,
            "root_duration_ms": round(trace.total_duration_ms, 2),
            "total_spans": len(trace.all_spans),
            "spans": spans_data,
        }


# ============================================================
# Span 树可视化
# ============================================================

class TraceVisualizer:
    """将 Span 树结构可视化为文本"""

    @staticmethod
    def tree_view(trace: Trace) -> str:
        """树形图"""
        lines = [f"Trace: {trace.trace_id[:12]}... | 总耗时: {trace.total_duration_ms:.0f}ms"]
        lines.append("-" * 60)
        TraceVisualizer._render_span(trace.root_span, "", True, lines)
        return "\n".join(lines)

    @staticmethod
    def _render_span(span: Span, prefix: str, is_last: bool, lines: list):
        """递归渲染 Span 和它的子节点"""
        connector = "└── " if is_last else "├── "
        duration = f"{span.duration_ms:.0f}ms" if span.duration_ms > 0 else "running"

        # 主行
        attr_str = ""
        if span.attributes:
            key_attrs = {k: v for k, v in span.attributes.items()
                        if k in ("model", "tool", "tokens")}
            if key_attrs:
                attr_str = " " + str(key_attrs)

        icon = "✅" if span.status == "OK" else "❌"
        lines.append(f"{prefix}{connector}{icon} {span.name} [{duration}]{attr_str}")

        # 属性详情（如果有额外属性）
        extra_attrs = {k: v for k, v in span.attributes.items()
                      if k not in ("model", "tool", "tokens")}
        if extra_attrs:
            child_prefix = prefix + ("    " if is_last else "│   ")
            for k, v in extra_attrs.items():
                lines.append(f"{child_prefix}  • {k}: {v}")

        # 递归子节点
        children = span.children
        for i, child in enumerate(children):
            child_is_last = (i == len(children) - 1)
            child_prefix = prefix + ("    " if is_last else "│   ")
            TraceVisualizer._render_span(child, child_prefix, child_is_last, lines)

    @staticmethod
    def flamegraph_data(trace: Trace) -> str:
        """生成火焰图格式数据（兼容 Brendan Gregg 格式）"""
        lines = []
        TraceVisualizer._flame_span(trace.root_span, "", lines)
        return "\n".join(lines)

    @staticmethod
    def _flame_span(span: Span, prefix: str, lines: list):
        """递归生成火焰图数据"""
        name = f"{prefix};{span.name}"
        duration_us = int(span.duration_ms * 1000)
        if duration_us > 0:
            lines.append(f"{name} {duration_us}")
        for child in span.children:
            TraceVisualizer._flame_span(child, name, lines)


# ============================================================
# 模拟 Agent 追踪
# ============================================================

def simulate_agent_trace(tracer: Tracer, query_type: str = "查询") -> Trace:
    """模拟一个完整的 Agent 请求追踪"""

    # 开始追踪
    trace = tracer.start_trace("agent_request")
    request_start = trace.root_span
    request_start.set_attribute("query_type", query_type)
    request_start.set_attribute("user_id", f"user_{random.randint(1, 100)}")

    # Step 1: LLM 推理（判断是否需要工具）
    llm_span_1 = tracer.start_span(trace, "llm_reason", request_start)
    time.sleep(random.uniform(0.1, 0.3))
    llm_span_1.set_attribute("model", "gpt-4o")
    llm_span_1.set_attribute("input_tokens", random.randint(200, 800))
    llm_span_1.set_attribute("output_tokens", random.randint(50, 150))
    llm_span_1.set_attribute("loop_iteration", 1)
    llm_span_1.end()

    # Step 2: 安全检测
    safety_span = tracer.start_span(trace, "safety_check", request_start)
    time.sleep(0.05)
    safety_span.set_attribute("injection_detected", False)
    safety_span.set_attribute("policy", "allow")
    safety_span.end()

    # Step 3: 工具调用
    tool_span = tracer.start_span(trace, "tool_exec", request_start)
    tool_name = "query_database" if "查询" in query_type else "read_file"
    tool_span.set_attribute("tool", tool_name)
    tool_span.set_attribute("params", json.dumps({"query": query_type}))
    time.sleep(random.uniform(0.2, 0.5))
    tool_span.set_attribute("rows_returned", random.randint(5, 50))
    tool_span.set_attribute("success", True)
    tool_span.end()

    # Step 4: LLM 分析工具结果
    llm_span_2 = tracer.start_span(trace, "llm_analyze", request_start)
    time.sleep(random.uniform(0.3, 0.8))
    llm_span_2.set_attribute("model", "gpt-4o")
    llm_span_2.set_attribute("input_tokens", random.randint(800, 2000))
    llm_span_2.set_attribute("output_tokens", random.randint(200, 500))
    llm_span_2.set_attribute("loop_iteration", 2)
    llm_span_2.end()

    # Step 5: 安全输出审核
    output_span = tracer.start_span(trace, "output_filter", request_start)
    time.sleep(0.03)
    output_span.set_attribute("pii_detected", False)
    output_span.set_attribute("filtered", False)
    output_span.end()

    # 完成根 Span
    request_start.end()
    total_tokens = (
        llm_span_1.attributes.get("input_tokens", 0) +
        llm_span_1.attributes.get("output_tokens", 0) +
        llm_span_2.attributes.get("input_tokens", 0) +
        llm_span_2.attributes.get("output_tokens", 0)
    )
    request_start.set_attribute("total_tokens", total_tokens)
    request_start.set_attribute("total_spans", len(trace.all_spans))

    # 估算成本
    cost = (total_tokens / 1000) * 0.005
    request_start.set_attribute("estimated_cost_usd", round(cost, 5))

    return trace


# ============================================================
# 演示
# ============================================================

def demo():
    print("=" * 60)
    print("🔍 Agent 全链路追踪演示")
    print("=" * 60)

    tracer = Tracer(service_name="agent-service-v1")

    # 模拟 5 个不同请求
    queries = ["查询销售数据", "分析用户行为", "生成周报", "查询库存", "分析竞品"]
    traces = []

    for i, query in enumerate(queries):
        print(f"\n📌 请求 {i+1}: {query}")
        trace = simulate_agent_trace(tracer, query)
        traces.append(trace)
        print(f"   追踪 ID: {trace.trace_id[:12]}... | 耗时: {trace.total_duration_ms:.0f}ms | "
              f"{len(trace.all_spans)} 个 Span")

    # 显示第一个追踪的树形图
    print("\n" + "=" * 60)
    print("📊 Span 树形图（请求 1）")
    print("=" * 60)
    print(TraceVisualizer.tree_view(traces[0]))

    # 火焰图数据
    print("\n" + "=" * 60)
    print("🔥 火焰图格式数据")
    print("=" * 60)
    print(TraceVisualizer.flamegraph_data(traces[0]))

    # 追踪摘要对比
    print("\n" + "=" * 60)
    print("📋 5 个请求对比")
    print("=" * 60)
    print(f"{'请求':<12} {'Trace ID':<14} {'耗时(ms)':<10} {'Span数':<8} {'Token':<8} {'成本':<10}")
    print("-" * 62)
    for trace in traces:
        rs = trace.root_span
        dur = f"{trace.total_duration_ms:.0f}"
        tokens = rs.attributes.get("total_tokens", 0)
        cost = f"${rs.attributes.get('estimated_cost_usd', 0):.5f}"
        tid = trace.trace_id[:10]
        nspans = len(trace.all_spans)
        print(f"{rs.attributes.get('query_type', '?'):<12} {tid:<14} {dur:<10} {nspans:<8} {tokens:<8} {cost:<10}")

    # 单个追踪的 JSON 导出
    print("\n" + "=" * 60)
    print("📄 追踪 JSON 导出格式（类似 OTLP）")
    print("=" * 60)
    export_data = tracer.trace_to_dict(traces[0])
    # 简化展示
    for span in export_data["spans"][:3]:
        print(f'  Span: {span["name"]} | {span["duration_ms"]:.0f}ms | '
              f'parent={span["parent_span_id"][:6] if span["parent_span_id"] else "root"}')


if __name__ == "__main__":
    demo()

    print("\n" + "=" * 60)
    print("📝 关键总结")
    print("=" * 60)
    print("""
🔍 Agent 全链路追踪要点：

1️⃣ Span 树结构：
   Root: agent_request（整个请求周期）
   ├─ llm_reason（LLM 推理——是否需要工具）
   ├─ safety_check（安全检测）
   ├─ tool_exec（工具调用）
   ├─ llm_analyze（LLM 分析工具结果）
   └─ output_filter（输出审核）

2️⃣ 关键属性指标：
   - 每次 LLM 调用：model, tokens, latency, loop_iteration
   - 每次工具调用：tool_name, params, latency, success
   - Root：total_tokens, total_cost, user_id

3️⃣ 可视化方式：
   - 树形图：展示父子关系
   - 火焰图：展示时间占比（定位瓶颈）

4️⃣ 实际生产使用 opentelemetry-sdk + Jaeger/Tempo！
""")
