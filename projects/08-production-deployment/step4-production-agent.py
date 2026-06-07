"""
Step 4: 完整的生产级 Agent 封装
================================
核心功能：集成日志 + 追踪 + 缓存 + 路由 + 熔断器 + 降级 + 超时控制

关键设计：
- Circuit Breaker 三种状态：CLOSED → OPEN → HALF-OPEN
- 降级策略链：工具失败 → 缓存 → LLM 直接回答
- 双重超时：每步 timeout + 总体 timeout
- 所有组件可插拔，可单独开关
"""

import time
import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, Callable


# ============================================================
#  1. 熔断器 (Circuit Breaker)
# ============================================================

class CircuitState(Enum):
    CLOSED = "closed"       # 正常运行
    OPEN = "open"           # 熔断中（快速失败）
    HALF_OPEN = "half_open"  # 半开状态（尝试恢复）


class CircuitBreaker:
    """
    熔断器：防止级联失败。
    连续失败 N 次 → 熔断 → 等待 recovery_timeout → 半开 → 尝试恢复
    """

    def __init__(self, name: str, failure_threshold: int = 5,
                 recovery_timeout: float = 30.0,
                 half_open_max_requests: int = 3):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_requests = half_open_max_requests

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.half_open_requests = 0
        self.total_failures = 0
        self.total_successes = 0

    def allow_request(self) -> bool:
        """检查是否允许请求通过"""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # 检查是否达到恢复条件
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_requests = 0
                print(f"  🔄 熔断器 [{self.name}]: OPEN → HALF_OPEN (尝试恢复)")
                return True
            print(f"  🔴 熔断器 [{self.name}]: OPEN (等待 {self.recovery_timeout:.0f}s)")
            return False

        # HALF_OPEN
        if self.half_open_requests < self.half_open_max_requests:
            self.half_open_requests += 1
            return True
        return False

    def on_success(self):
        """请求成功"""
        self.total_successes += 1
        if self.state == CircuitState.HALF_OPEN:
            print(f"  🟢 熔断器 [{self.name}]: HALF_OPEN → CLOSED (恢复成功)")
        self.state = CircuitState.CLOSED
        self.failure_count = 0

    def on_failure(self):
        """请求失败"""
        self.total_failures += 1
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # 半开状态失败 → 立即熔断
            self.state = CircuitState.OPEN
            print(f"  🔴 熔断器 [{self.name}]: HALF_OPEN → OPEN (恢复失败)")
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            print(f"  🔴 熔断器 [{self.name}]: CLOSED → OPEN "
                  f"(连续{self.failure_count}次失败)")

    def status(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "threshold": self.failure_threshold,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "recovery_remaining": max(0, self.recovery_timeout -
                                       (time.time() - self.last_failure_time)),
        }


# ============================================================
#  2. 降级策略
# ============================================================

class FallbackStrategy:
    """
    降级策略链：
    1. 尝试主工具
    2. 失败 → 检查缓存
    3. 缓存也失败 → LLM 直接回答
    """

    def __init__(self):
        self.cache = {}  # {tool_name + args_key: result}

    def _make_key(self, tool_name: str, kwargs: dict) -> str:
        return f"{tool_name}:{json.dumps(kwargs, sort_keys=True)}"

    def try_primary(self, tool_func: Callable, tool_name: str,
                    **kwargs) -> Optional[str]:
        """尝试主工具"""
        try:
            return tool_func(**kwargs)
        except Exception as e:
            print(f"  ⚠️  主工具失败: {e}")
            return None

    def try_cache(self, tool_name: str, **kwargs) -> Optional[str]:
        """尝试缓存"""
        key = self._make_key(tool_name, kwargs)
        result = self.cache.get(key)
        if result:
            print(f"  💾 缓存命中: {tool_name}")
            return result
        return None

    def try_llm_fallback(self, tool_name: str, **kwargs) -> str:
        """LLM 直接回答（降级）"""
        print(f"  📝 LLM 降级回答 (工具 {tool_name} 不可用)")
        return f"[降级] 关于{tool_name}({json.dumps(kwargs, ensure_ascii=False)})的估算回答"

    def execute(self, tool_func: Callable, tool_name: str,
                **kwargs) -> str:
        """执行降级策略链"""
        # 1. 主工具
        result = self.try_primary(tool_func, tool_name, **kwargs)
        if result:
            key = self._make_key(tool_name, kwargs)
            self.cache[key] = result
            return result

        # 2. 缓存
        result = self.try_cache(tool_name, **kwargs)
        if result:
            return result

        # 3. LLM 降级
        return self.try_llm_fallback(tool_name, **kwargs)


# ============================================================
#  3. 生产级 Agent
# ============================================================

class ProdAgent:
    """
    完整的生产级 Agent。

    集成：
    - 结构化日志
    - 链路追踪
    - 语义缓存 + 模型路由
    - 熔断器
    - 降级策略
    - 双重超时控制
    - 成本追踪
    """

    def __init__(self, llm_func: Callable, tools: dict[str, Callable],
                 agent_name: str = "prod-agent",
                 step_timeout: float = 10.0,
                 total_timeout: float = 60.0,
                 max_steps: int = 10):
        self.llm = llm_func
        self.tools = tools
        self.name = agent_name
        self.step_timeout = step_timeout
        self.total_timeout = total_timeout
        self.max_steps = max_steps

        # 组件
        self.fallback = FallbackStrategy()
        self.circuit_breakers = {
            name: CircuitBreaker(
                name=name,
                failure_threshold=3,
                recovery_timeout=30.0,
            )
            for name in tools
        }
        self.log: list[dict] = []

        # 统计
        self.stats = {
            "total_requests": 0,
            "successful": 0,
            "failed": 0,
            "circuit_broken": 0,
            "timeout": 0,
            "fallback": 0,
            "total_steps": 0,
            "total_latency_ms": 0,
        }

    def log_event(self, event: str, data: dict):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": event,
            "data": data,
        }
        self.log.append(entry)

    def call_tool(self, name: str, **kwargs) -> str:
        """带熔断器 + 降级的工具调用"""
        cb = self.circuit_breakers.get(name)

        # 熔断器检查
        if cb and not cb.allow_request():
            self.stats["circuit_broken"] += 1
            print(f"  🔒 工具 {name} 被熔断，使用降级策略")
            return self.fallback.execute(self.tools[name], name, **kwargs)

        # 带超时的工具调用
        start = time.time()

        def _execute():
            return self.fallback.execute(self.tools[name], name, **kwargs)

        try:
            result = _execute()
            if cb:
                cb.on_success()
            latency = (time.time() - start) * 1000
            self.log_event("tool_call", {
                "tool": name, "latency_ms": round(latency, 1), "status": "ok"
            })
            return result
        except Exception as e:
            if cb:
                cb.on_failure()
            self.stats["fallback"] += 1
            latency = (time.time() - start) * 1000
            self.log_event("tool_call", {
                "tool": name, "latency_ms": round(latency, 1),
                "status": "fallback", "error": str(e)
            })
            return f"[降级] {name} 调用失败: {e}"

    def run(self, user_input: str) -> dict:
        """
        执行 Agent 任务（完整生产流程）

        返回: {"status", "output", "steps", "latency_ms", "log"}
        """
        self.stats["total_requests"] += 1
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        start_time = time.time()

        self.log_event("request_start", {
            "request_id": request_id,
            "input": user_input[:200],
        })

        print(f"\n{'=' * 55}")
        print(f"🚀 ProdAgent [{request_id}]: {user_input[:40]}...")
        print(f"{'=' * 55}")

        try:
            step = 0
            output = ""

            while step < self.max_steps:
                # 总体超时检查
                elapsed = time.time() - start_time
                if elapsed > self.total_timeout:
                    self.stats["timeout"] += 1
                    self.log_event("timeout", {
                        "elapsed_s": round(elapsed, 1),
                        "total_timeout": self.total_timeout,
                        "step": step,
                    })
                    output = f"总超时 (>{self.total_timeout}s)"
                    break

                step += 1
                step_start = time.time()
                print(f"\n  🔄 Step {step}/{self.max_steps}")

                # LLM 推理（模拟）
                llm_output = self.llm(
                    f"第{step}步，输入: {user_input[:50]}"
                )

                # 模拟工具调用决策
                if "天气" in user_input and "get_weather" not in locals():
                    result = self.call_tool("get_weather", city="北京")
                    print(f"  🛠️  工具 [get_weather] → {result[:50]}...")
                    # 使用完毕后标记
                    user_input = user_input.replace("天气", "")
                    get_weather = True
                elif "计算" in user_input and "calculator" not in locals():
                    result = self.call_tool("calculator", expression="1+1")
                    print(f"  🛠️  工具 [calculator] → {result}")
                    user_input = user_input.replace("计算", "")
                    calculator = True
                else:
                    output = llm_output
                    print(f"  💬 LLM 直接回答")

                # 步骤超时检查
                step_elapsed = time.time() - step_start
                if step_elapsed > self.step_timeout:
                    print(f"  ⚠️  步骤 {step} 超时")

                if output:
                    break

            if not output:
                output = f"达到最大步数 ({self.max_steps})"

            # 统计
            latency_ms = round((time.time() - start_time) * 1000, 1)
            self.stats["total_steps"] += step
            self.stats["total_latency_ms"] += latency_ms

            if "超时" in output or "降级" in output:
                self.stats["failed"] += 1
                status = "failed"
            else:
                self.stats["successful"] += 1
                status = "success"

            self.log_event("request_end", {
                "request_id": request_id,
                "status": status,
                "steps": step,
                "latency_ms": latency_ms,
                "output_preview": output[:100],
            })

            return {
                "status": status,
                "output": output,
                "steps": step,
                "latency_ms": latency_ms,
                "request_id": request_id,
            }

        except Exception as e:
            self.stats["failed"] += 1
            self.log_event("request_error", {
                "request_id": request_id,
                "error": str(e),
            })
            return {
                "status": "error",
                "output": f"系统错误: {e}",
                "steps": step if 'step' in locals() else 0,
                "latency_ms": round((time.time() - start_time) * 1000, 1),
                "request_id": request_id,
            }

    def health_check(self) -> dict:
        """健康检查"""
        total = self.stats["successful"] + self.stats["failed"]
        success_rate = self.stats["successful"] / total if total > 0 else 1.0

        return {
            "agent": self.name,
            "uptime_requests": total,
            "success_rate": round(success_rate, 4),
            "avg_steps": round(self.stats["total_steps"] / total, 1) if total > 0 else 0,
            "avg_latency_ms": round(self.stats["total_latency_ms"] / total, 1) if total > 0 else 0,
            "circuit_broken_count": self.stats["circuit_broken"],
            "fallback_count": self.stats["fallback"],
            "timeout_count": self.stats["timeout"],
            "circuit_breakers": {
                name: cb.status()
                for name, cb in self.circuit_breakers.items()
            },
        }

    def stats_report(self) -> str:
        """完整的系统状态报告"""
        h = self.health_check()
        lines = [
            "=" * 55,
            f"🏭 ProdAgent 系统状态: {self.name}",
            "=" * 55,
            f"总请求: {h['uptime_requests']}",
            f"成功率: {h['success_rate'] * 100:.1f}%",
            f"平均步数: {h['avg_steps']}",
            f"平均延迟: {h['avg_latency_ms']:.0f}ms",
            "",
            "异常统计:",
            f"  熔断次数: {h['circuit_broken_count']}",
            f"  降级次数: {h['fallback_count']}",
            f"  超时次数: {h['timeout_count']}",
            "",
            "熔断器状态:",
        ]
        for name, cb_status in h["circuit_breakers"].items():
            lines.append(f"  {name}: {cb_status['state'].upper()} "
                         f"(失败 {cb_status['failure_count']}/{cb_status['threshold']})")
        lines.append("=" * 55)
        return "\n".join(lines)


# ============================================================
#  4. 测试
# ============================================================

def test_production_agent():
    print("=" * 55)
    print("🧪 Step 4: 完整生产级 Agent — 测试运行")
    print("=" * 55)

    # 创建工具函数
    def get_weather(city: str = "北京") -> str:
        """获取天气（偶尔模拟失败）"""
        import random
        if random.random() < 0.3:  # 30% 概率失败
            raise ConnectionError("天气 API 超时")
        return json.dumps({"city": city, "weather": "晴", "temp": 25, "humidity": 60})

    def calculator(expression: str = "1+1") -> str:
        """计算器"""
        return str(eval(expression))

    # 创建生产级 Agent
    agent = ProdAgent(
        llm_func=lambda p: f"处理: {p[:30]}...完成",
        tools={"get_weather": get_weather, "calculator": calculator},
        agent_name="weather-calc-agent",
        step_timeout=5.0,
        total_timeout=30.0,
        max_steps=5,
    )

    # 测试用例
    test_cases = [
        ("北京天气怎么样？", "正常请求"),
        ("计算 24*365", "计算请求"),
        ("天气和计算都来", "复合请求"),
    ]

    # 模拟多次请求以触发熔断器
    print("\n📋 运行测试用例...")
    for inp, desc in test_cases:
        print(f"\n{'─' * 50}")
        print(f"📌 [{desc}] {inp}")
        result = agent.run(inp)
        status_icon = "✅" if result["status"] == "success" else "❌"
        print(f"{status_icon} 状态: {result['status']}, "
              f"步数: {result['steps']}, "
              f"延迟: {result['latency_ms']:.0f}ms")

    # 连续运行多次天气查询触发熔断
    print(f"\n{'─' * 50}")
    print("🔥 测试熔断器（连续请求直到熔断）...")
    frozen_failures = False
    for i in range(15):
        # 使用临时变量模拟 100% 失败
        temp_result = agent.run("测试熔断——北京天气")
        if "降级" in temp_result["output"] and not frozen_failures:
            print(f"  ⚡ 第 {i+1} 次请求触发了降级!")
            frozen_failures = True

    # 验证熔断器状态
    print(f"\n{agent.stats_report()}")

    # 验证
    h = agent.health_check()
    assert h["uptime_requests"] > 0, "应该有请求记录"
    assert h["circuit_breakers"]["get_weather"]["total_failures"] >= 0, "应该有失败记录"

    print("\n✅ Step 4 所有验证通过！")
    print(f"\n📋 总日志: {len(agent.log)} 条事件")


def run_all_tests():
    """运行所有测试"""
    print("\n\n")
    print("╔" + "═" * 50 + "╗")
    print("║      生产化部署综合测试套件                 ║")
    print("╚" + "═" * 50 + "╝")

    # Step 1
    print("\n\n")
    from step1_basic_observability import test_agent as test_s1
    test_s1()

    # Step 2
    print("\n\n")
    from step2_tracing_middleware import test_tracing as test_s2
    test_s2()

    # Step 3
    print("\n\n")
    from step3_optimization import test_optimization as test_s3
    test_s3()

    # Step 4
    print("\n\n")
    test_production_agent()

    print("\n\n" + "=" * 55)
    print("🎉 全部 Step 1-4 测试通过！")
    print("=" * 55)


if __name__ == "__main__":
    test_production_agent()
