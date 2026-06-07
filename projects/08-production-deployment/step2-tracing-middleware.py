"""
Step 2: 链路追踪中间件
======================
核心功能：装饰器自动追踪 Agent 步骤 → Span 树 → OpenTelemetry 导出

关键设计：
- @trace_step 装饰器包装 LLM / Tool 调用，自动记录 span
- Context manager 管理 span 生命周期
- span 结构：name, start_time, duration_ms, input, output, status, children
- 支持导出为 JSON 和 OpenTelemetry 格式
"""

import time
import json
import uuid
import functools
from datetime import datetime
from typing import Optional, Callable


# ============================================================
#  1. Span 定义
# ============================================================

class Span:
    """单个追踪单元"""

    def __init__(self, name: str, span_type: str, parent: Optional["Span"] = None):
        self.span_id = str(uuid.uuid4())[:8]
        self.name = name
        self.type = span_type  # "llm" | "tool" | "think" | "agent"
        self.parent = parent
        self.children: list[Span] = []
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.duration_ms: Optional[float] = None
        self.input: Optional[str] = None
        self.output: Optional[str] = None
        self.status = "ok"  # "ok" | "error"
        self.error: Optional[str] = None
        self.metadata: dict = {}

    def finish(self, output: str = "", status: str = "ok", error: str = None):
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        self.output = output[:500] if output else ""
        self.status = status
        if error:
            self.error = str(error)[:300]

    def to_dict(self) -> dict:
        return {
            "span_id": self.span_id,
            "name": self.name,
            "type": self.type,
            "start_time": datetime.utcfromtimestamp(self.start_time).isoformat() + "Z",
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error": self.error,
            "input_preview": (self.input or "")[:200],
            "output_preview": (self.output or "")[:200],
            "children": [c.to_dict() for c in self.children],
        }


# ============================================================
#  2. Trace 上下文管理
# ============================================================

class TraceContext:
    """线程级追踪上下文"""

    _context = {}

    @classmethod
    def get(cls, trace_id: str = None) -> Optional[Span]:
        if trace_id:
            return cls._context.get(trace_id)
        # 返回最近的活跃 trace
        return next(reversed(cls._context.values())) if cls._context else None

    @classmethod
    def set(cls, trace_id: str, trace: 'Trace'):
        cls._context[trace_id] = trace

    @classmethod
    def clear(cls, trace_id: str):
        cls._context.pop(trace_id, None)


# ============================================================
#  3. 追踪装饰器
# ============================================================

class Trace:
    """链路追踪管理器"""

    def __init__(self, name: str = "agent_trace"):
        self.trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        self.name = name
        self.root = Span(name, "agent")
        self.root.input = name
        self.spans: list[Span] = [self.root]
        TraceContext.set(self.trace_id, self)

    def add_child(self, name: str, span_type: str,
                  parent: Span = None) -> Span:
        parent = parent or TraceContext.get(self.trace_id).root if hasattr(TraceContext.get(self.trace_id), 'root') else parent
        span = Span(name, span_type, parent)
        if parent:
            parent.children.append(span)
        self.spans.append(span)
        return span

    def finish(self, output: str = ""):
        self.root.finish(output)
        TraceContext.clear(self.trace_id)

    def summary(self) -> dict:
        """汇总追踪信息"""
        total_duration = self.root.duration_ms or 0
        llm_calls = [s for s in self._flatten(self.root) if s.type == "llm"]
        tool_calls = [s for s in self._flatten(self.root) if s.type == "tool"]
        errors = [s for s in self._flatten(self.root) if s.status == "error"]

        return {
            "trace_id": self.trace_id,
            "total_duration_ms": total_duration,
            "total_steps": self.root.duration_ms is not None,  # 至少 1 步
            "llm_call_count": len(llm_calls),
            "tool_call_count": len(tool_calls),
            "error_count": len(errors),
            "has_error": len(errors) > 0,
            "waterfall": [
                {
                    "name": s.name,
                    "type": s.type,
                    "duration_ms": s.duration_ms,
                    "status": s.status,
                }
                for s in self._flatten(self.root)
            ],
        }

    def pretty_print(self) -> str:
        """格式化输出追踪树"""
        s = self.summary()
        lines = [
            f"🔍 Trace: {s['trace_id']}",
            f"   总耗时: {s['total_duration_ms']:.0f}ms",
            f"   LLM 调用: {s['llm_call_count']} 次",
            f"   工具调用: {s['tool_call_count']} 次",
            f"   错误: {s['error_count']} 个",
            "",
            "   调用瀑布:",
        ]
        for i, w in enumerate(s["waterfall"], 1):
            indent = "  " * (0 if w["type"] == "agent" else 1)
            status_icon = "✅" if w["status"] == "ok" else "❌"
            duration_str = f"{w['duration_ms']:.0f}ms" if w["duration_ms"] else "N/A"
            lines.append(
                f"   {indent}{i}. {status_icon} [{w['type']}] {w['name']} — {duration_str}"
            )
        return "\n".join(lines)

    def to_otel_json(self) -> dict:
        """导出为 OpenTelemetry 格式的 JSON"""
        spans_otel = []

        def flatten_to_otel(span: Span, parent_id: str = ""):
            span_otel = {
                "trace_id": self.trace_id,
                "span_id": span.span_id,
                "parent_span_id": parent_id,
                "name": span.name,
                "kind": "INTERNAL",
                "start_time": span.start_time,
                "end_time": span.end_time or time.time(),
                "attributes": {
                    "span.type": span.type,
                    "status": span.status,
                    "input": span.input or "",
                    "output": span.output or "",
                },
            }
            if span.error:
                span_otel["attributes"]["error"] = span.error
            spans_otel.append(span_otel)
            for child in span.children:
                flatten_to_otel(child, span.span_id)

        flatten_to_otel(self.root)
        return {"resource_spans": [{"scope_spans": [{"spans": spans_otel}]}]}

    @staticmethod
    def _flatten(span: Span) -> list[Span]:
        result = [span]
        for child in span.children:
            result.extend(Trace._flatten(child))
        return result


def trace_step(name: str, step_type: str = "think"):
    """装饰器：自动追踪 Agent 步骤"""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 获取当前 trace
            trace_ctx = TraceContext.get()
            if not trace_ctx:
                return func(*args, **kwargs)

            # 创建子 span
            span = trace_ctx.add_child(name, step_type)
            span.input = f"args={args}, kwargs={kwargs}" if args or kwargs else ""

            try:
                start = time.time()
                result = func(*args, **kwargs)
                span.finish(str(result)[:500], "ok")
                return result
            except Exception as e:
                span.finish(str(e), "error", str(e))
                raise
        return wrapper
    return decorator


# ============================================================
#  4. 使用示例
# ============================================================

class TracedAgent:
    """带链路追踪的 Agent"""

    def __init__(self):
        self.trace: Optional[Trace] = None

    @trace_step("LLM推理", "llm")
    def think(self, prompt: str) -> str:
        """LLM 推理"""
        time.sleep(0.05)  # 模拟延迟
        if "天气" in prompt:
            return '{"action": "get_weather", "city": "北京"}'
        elif "计算" in prompt:
            return '{"action": "calculator", "expression": "1+1"}'
        return "直接回答"

    @trace_step("工具调用", "tool")
    def call_tool(self, name: str, **kwargs) -> str:
        """调用工具"""
        time.sleep(0.03)  # 模拟延迟
        if name == "get_weather":
            return json.dumps({"city": kwargs.get("city"), "weather": "晴", "temp": 25})
        elif name == "calculator":
            return str(eval(kwargs.get("expression", "0")))
        raise ValueError(f"未知工具: {name}")

    def run(self, user_input: str) -> str:
        """运行 Agent，返回完整 trace"""
        self.trace = Trace(f"Agent: {user_input[:30]}...")
        self.trace.root.input = user_input

        try:
            step = 0
            while step < 5:
                step += 1
                thought = self.think(f"Step {step}: {user_input}")

                # 解析是否要调工具
                import re
                tool_match = re.search(r'get_weather|calculator', thought)
                if tool_match:
                    name = tool_match.group()
                    args = {"city": "北京"} if name == "get_weather" else {"expression": "1+1"}
                    self.call_tool(name, **args)
                else:
                    self.trace.finish(f"完成: {thought}")
                    return thought

            self.trace.finish("达到最大步数")
            return "达到最大步数"
        except Exception as e:
            self.trace.finish(f"错误: {e}")
            return f"错误: {e}"


# ============================================================
#  运行演示
# ============================================================

def test_tracing():
    print("=" * 55)
    print("🧪 Step 2: 链路追踪中间件 — 测试运行")
    print("=" * 55)

    agent = TracedAgent()

    test_inputs = [
        "北京天气怎么样？",
        "计算 1+1",
        "你好，帮我查查天气",
    ]

    for inp in test_inputs:
        print(f"\n{'─' * 50}")
        print(f"▶ 用户: {inp}")
        result = agent.run(inp)
        print(f"◀ Agent: {result[:60]}")
        print()
        print(agent.trace.pretty_print() if agent.trace else "No trace")

        # 验证 span 结构
        assert agent.trace is not None, "应该有 trace"
        summary = agent.trace.summary()
        assert summary["total_duration_ms"] > 0, "应该有耗时"
        assert summary["llm_call_count"] > 0, "应该有 LLM 调用"
        print(f"  (JSON: {json.dumps(summary, ensure_ascii=False)[:100]}...)")

    # 导出 OTEL 格式
    print(f"\n{'─' * 50}")
    print("📤 OpenTelemetry 导出示例:")
    otel_json = agent.trace.to_otel_json() if agent.trace else {}
    otel_spans = otel_json.get("resource_spans", [{}])[0].get("scope_spans", [{}])[0].get("spans", [])
    print(f"   导出了 {len(otel_spans)} 个 spans")
    for s in otel_spans:
        print(f"   - [{s['span_id']}] {s['name']} ({s['kind']})")

    print("\n✅ Step 2 所有验证通过！")


if __name__ == "__main__":
    test_tracing()
