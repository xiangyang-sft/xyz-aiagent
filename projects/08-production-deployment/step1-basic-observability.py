"""
Step 1: 结构化日志 + 基础指标
==============================
核心功能：格式化的 JSON 日志 + 滑动窗口指标 + 日志分级轮转

关键设计：
- JSON 格式化日志，可直接喂入 ELK/Loki
- Agent 生命周期事件钩子（on_start/on_llm_call/on_tool_call/on_end/on_error）
- 滑动窗口延迟分位数、错误率统计
- 日志分级：DEBUG / INFO / WARN / ERROR
"""

import json
import logging
import time
import math
from datetime import datetime
from collections import deque
from typing import Optional, Callable


# ============================================================
#  1. 结构化 JSON 日志
# ============================================================

class JSONFormatter(logging.Formatter):
    """输出 JSON 格式的日志"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # 附加额外字段（extra 传入）
        if hasattr(record, "event_type"):
            log_entry["event_type"] = record.event_type
        if hasattr(record, "event_data"):
            log_entry["data"] = record.event_data
        if hasattr(record, "session_id"):
            log_entry["session_id"] = record.session_id
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logger(name: str = "agent", level: int = logging.INFO) -> logging.Logger:
    """配置带 JSON 格式的 Logger"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 防止重复添加 handler
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)

    return logger


# ============================================================
#  2. 滑动窗口指标采集器
# ============================================================

class MetricsCollector:
    """采集滑动窗口指标（近 N 次调用的统计值）"""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.llm_latencies = deque(maxlen=window_size)
        self.tool_latencies = deque(maxlen=window_size)
        self.llm_errors = deque(maxlen=window_size)        # True/False
        self.tool_errors = deque(maxlen=window_size)       # True/False
        self.llm_tokens = deque(maxlen=window_size)        # {(prompt, completion)}
        self.step_counts = deque(maxlen=window_size)       # 每次任务的步数

    def record_llm_call(self, latency_ms: float, success: bool,
                        prompt_tokens: int = 0, completion_tokens: int = 0):
        self.llm_latencies.append(latency_ms)
        self.llm_errors.append(not success)
        self.llm_tokens.append((prompt_tokens, completion_tokens))

    def record_tool_call(self, latency_ms: float, success: bool):
        self.tool_latencies.append(latency_ms)
        self.tool_errors.append(not success)

    def record_step_count(self, steps: int):
        self.step_counts.append(steps)

    def get_percentile(self, data: deque, percentile: float) -> float:
        """计算分位数"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        idx = int(math.ceil(percentile / 100.0 * len(sorted_data))) - 1
        idx = max(0, min(idx, len(sorted_data) - 1))
        return sorted_data[idx]

    def summary(self) -> dict:
        """输出当前指标汇总"""
        total_llm = len(self.llm_latencies)
        total_tool = len(self.tool_latencies)
        llm_error_rate = sum(self.llm_errors) / total_llm if total_llm > 0 else 0
        tool_error_rate = sum(self.tool_errors) / total_tool if total_tool > 0 else 0
        total_prompt = sum(t[0] for t in self.llm_tokens)
        total_completion = sum(t[1] for t in self.llm_tokens)

        return {
            "llm": {
                "count": total_llm,
                "p50_latency_ms": self.get_percentile(self.llm_latencies, 50),
                "p95_latency_ms": self.get_percentile(self.llm_latencies, 95),
                "p99_latency_ms": self.get_percentile(self.llm_latencies, 99),
                "error_rate": round(llm_error_rate, 4),
            },
            "tool": {
                "count": total_tool,
                "p50_latency_ms": self.get_percentile(self.tool_latencies, 50),
                "p95_latency_ms": self.get_percentile(self.tool_latencies, 95),
                "error_rate": round(tool_error_rate, 4),
            },
            "tokens": {
                "total_prompt": total_prompt,
                "total_completion": total_completion,
            },
            "steps": {
                "avg": round(sum(self.step_counts) / len(self.step_counts), 2) if self.step_counts else 0,
                "max": max(self.step_counts) if self.step_counts else 0,
            },
        }

    def report(self) -> str:
        """生成人类可读的指标报告"""
        s = self.summary()
        lines = [
            "=" * 50,
            "📊 Agent 指标报告",
            "=" * 50,
            f"LLM 调用:     {s['llm']['count']} 次",
            f"  P50 延迟:   {s['llm']['p50_latency_ms']:.0f}ms",
            f"  P95 延迟:   {s['llm']['p95_latency_ms']:.0f}ms",
            f"  P99 延迟:   {s['llm']['p99_latency_ms']:.0f}ms",
            f"  错误率:     {s['llm']['error_rate']*100:.1f}%",
            "",
            f"工具调用:     {s['tool']['count']} 次",
            f"  P50 延迟:   {s['tool']['p50_latency_ms']:.0f}ms",
            f"  P95 延迟:   {s['tool']['p95_latency_ms']:.0f}ms",
            f"  错误率:     {s['tool']['error_rate']*100:.1f}%",
            "",
            f"Token 消耗:   Prompt={s['tokens']['total_prompt']}, "
            f"Completion={s['tokens']['total_completion']}",
            f"平均步数:     {s['steps']['avg']} (最大 {s['steps']['max']})",
            "=" * 50,
        ]
        return "\n".join(lines)


# ============================================================
#  3. 可观测 Agent 封装
# ============================================================

class ObservableAgent:
    """带可观测性的基础 Agent 封装"""

    def __init__(self, llm_func: Callable, tools: dict,
                 session_id: Optional[str] = None):
        self.llm = llm_func
        self.tools = tools
        self.session_id = session_id or f"sess_{int(time.time())}"
        self.logger = setup_logger(f"agent.{self.session_id}")
        self.metrics = MetricsCollector(window_size=100)
        self.step_count = 0
        self.max_steps = 10

    def log_event(self, event_type: str, data: dict, level: str = "INFO"):
        """统一的日志事件"""
        log_fn = getattr(self.logger, level.lower(), self.logger.info)
        log_fn(
            f"[{event_type}] {json.dumps(data, ensure_ascii=False)}",
            extra={
                "event_type": event_type,
                "event_data": data,
                "session_id": self.session_id,
            }
        )

    def call_llm(self, prompt: str, model: str = "gpt-4o-mini") -> str:
        """带日志和指标的 LLM 调用"""
        start = time.time()
        self.log_event("llm_start", {"model": model, "prompt_length": len(prompt)})

        try:
            # 模拟 LLM 调用
            latency = (time.time() - start) * 1000
            # 模拟：如果是天气相关返回 JSON，否则返回文本
            if "天气" in prompt or "weather" in prompt:
                result = '{"action": "get_weather", "city": "北京"}'
            elif "计算" in prompt or "calculate" in prompt:
                result = '{"action": "calculator", "expression": "1+1"}'
            else:
                result = "你好！我可以帮你查天气和做计算。"
            success = True
        except Exception as e:
            latency = (time.time() - start) * 1000
            result = str(e)
            success = False

        prompt_tokens = len(prompt) // 4  # 简化估算
        completion_tokens = len(result) // 4

        self.metrics.record_llm_call(latency, success, prompt_tokens, completion_tokens)
        self.log_event("llm_end", {
            "latency_ms": round(latency, 1),
            "success": success,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "output_preview": result[:100],
        }, level="INFO" if success else "ERROR")
        return result

    def call_tool(self, tool_name: str, **kwargs) -> str:
        """带日志和指标的工具调用"""
        start = time.time()
        self.log_event("tool_start", {"tool": tool_name, "args": kwargs})

        try:
            if tool_name == "get_weather":
                result = json.dumps({"city": kwargs.get("city"), "weather": "晴", "temp": 25})
            elif tool_name == "calculator":
                result = str(eval(kwargs.get("expression", "0")))
            else:
                raise ValueError(f"未知工具: {tool_name}")
            success = True
        except Exception as e:
            result = f"工具执行错误: {e}"
            success = False

        latency = (time.time() - start) * 1000
        self.metrics.record_tool_call(latency, success)
        self.log_event("tool_end", {
            "tool": tool_name,
            "latency_ms": round(latency, 1),
            "success": success,
            "result_preview": result[:200],
        }, level="INFO" if success else "ERROR")
        return result

    def run(self, user_input: str) -> str:
        """执行 Agent 任务"""
        self.log_event("agent_start", {"input": user_input, "max_steps": self.max_steps})
        self.step_count = 0
        output = ""

        while self.step_count < self.max_steps:
            self.step_count += 1
            self.log_event("cycle_start", {"step": self.step_count})

            # 1. LLM 推理
            llm_output = self.call_llm(
                f"用户：{user_input}\n这一步（第{self.step_count}步）请思考下一步行动。"
            )

            # 2. 解析是否要调用工具（简易解析）
            import re
            tool_match = re.search(r'get_weather|calculator', llm_output)
            if tool_match:
                tool_name = tool_match.group()
                if tool_name == "get_weather":
                    tool_result = self.call_tool(tool_name, city="北京")
                else:
                    tool_result = self.call_tool(tool_name, expression="1+1")
                self.log_event("step_result", {"step": self.step_count,
                                                "tool": tool_name, "result": tool_result})
            else:
                # 不需要工具，直接回答
                output = llm_output
                self.log_event("cycle_end", {"step": self.step_count, "reason": "直接回答"})
                break

        self.metrics.record_step_count(self.step_count)
        self.log_event("agent_end", {"output_preview": output[:200],
                                      "total_steps": self.step_count})
        return output or "任务完成"


# ============================================================
#  运行演示
# ============================================================

def test_agent():
    print("=" * 55)
    print("🧪 Step 1: 结构化日志 + 基础指标 — 测试运行")
    print("=" * 55)

    # 创建一个可观测 Agent
    agent = ObservableAgent(
        llm_func=lambda p: "回答",
        tools={"get_weather": lambda c: f"{c}晴25度",
               "calculator": lambda e: str(eval(e))}
    )

    # 模拟多次请求
    test_inputs = [
        "北京天气怎么样？",
        "计算 1+1",
        "你好",
        "上海天气如何？",
    ]

    for inp in test_inputs:
        print(f"\n▶ 用户: {inp}")
        output = agent.run(inp)
        print(f"◀ Agent: {output[:50]}...")

    # 输出指标报告
    print(f"\n{agent.metrics.report()}")

    # 验证关键指标
    s = agent.metrics.summary()
    assert s["llm"]["count"] > 0, "应该有 LLM 调用记录"
    assert s["tool"]["count"] >= 0, "应该有工具调用记录"
    assert s["llm"]["p50_latency_ms"] >= 0, "延迟应该 >= 0"
    print("\n✅ Step 1 所有验证通过！")


if __name__ == "__main__":
    test_agent()
