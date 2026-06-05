"""
step3-structured-logging.py — 结构化日志 + 日志级别 + 事件分类

功能：
1. 结构化日志格式（JSON 输出）
2. 日志级别控制（DEBUG/INFO/WARN/ERROR）
3. Agent 专用日志事件分类
4. 日志分析和报告生成

运行：python step3-structured-logging.py
"""

import time
import json
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ============================================================
# 日志级别
# ============================================================

class LogLevel:
    DEBUG = 10
    INFO = 20
    WARN = 30
    ERROR = 40
    CRITICAL = 50

    NAMES = {
        10: "DEBUG",
        20: "INFO",
        30: "WARN",
        40: "ERROR",
        50: "CRITICAL",
    }


# ============================================================
# 结构化日志记录器
# ============================================================

@dataclass
class LogEvent:
    """一个结构化日志事件"""
    timestamp: str
    level: int
    logger: str
    message: str
    trace_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    event_type: Optional[str] = None
    duration_ms: Optional[float] = None
    extra: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "timestamp": self.timestamp,
            "level": LogLevel.NAMES.get(self.level, "UNKNOWN"),
            "logger": self.logger,
            "message": self.message,
            "trace_id": self.trace_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "event_type": self.event_type,
            "duration_ms": self.duration_ms,
            **self.extra,
        }, ensure_ascii=False)

    def __str__(self):
        level_name = LogLevel.NAMES.get(self.level, "UNKNOWN").ljust(8)
        return f"[{self.timestamp}] {level_name} {self.logger}: {self.message}"


class StructuredLogger:
    """
    结构化日志记录器
    所有日志输出为 JSON，便于 Logstash/Loki 等工具采集
    """

    def __init__(self, name: str = "agent", level: int = LogLevel.DEBUG):
        self.name = name
        self.level = level
        self._events: list[LogEvent] = []

    def _log(self, level: int, message: str, **kwargs):
        """内部日志方法"""
        if level < self.level:
            return

        event = LogEvent(
            timestamp=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            level=level,
            logger=self.name,
            message=message,
            trace_id=kwargs.pop("trace_id", None),
            user_id=kwargs.pop("user_id", None),
            session_id=kwargs.pop("session_id", None),
            event_type=kwargs.pop("event_type", None),
            duration_ms=kwargs.pop("duration_ms", None),
            extra=kwargs,
        )
        self._events.append(event)

        # 人类可读输出
        print(str(event))
        # JSON 输出（模拟发送到日志系统）
        if level >= LogLevel.WARN:
            print(f"  → JSON: {event.to_json()[:120]}...")

    def debug(self, message: str, **kwargs):
        self._log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        self._log(LogLevel.INFO, message, **kwargs)

    def warn(self, message: str, **kwargs):
        self._log(LogLevel.WARN, message, **kwargs)

    def error(self, message: str, **kwargs):
        self._log(LogLevel.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        self._log(LogLevel.CRITICAL, message, **kwargs)

    def get_events(self, level_min: int = LogLevel.INFO) -> list[LogEvent]:
        return [e for e in self._events if e.level >= level_min]

    def get_report(self) -> str:
        """生成日志分析报告"""
        total = len(self._events)
        by_level = {}
        by_event_type = {}

        for event in self._events:
            level_name = LogLevel.NAMES.get(event.level, "UNKNOWN")
            by_level[level_name] = by_level.get(level_name, 0) + 1
            if event.event_type:
                by_event_type[event.event_type] = by_event_type.get(event.event_type, 0) + 1

        report = []
        report.append("📋 日志分析报告")
        report.append("=" * 40)
        report.append(f"总日志数：{total}")
        report.append(f"\n按级别分布：")
        for level in ["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"]:
            count = by_level.get(level, 0)
            bar = "█" * count
            report.append(f"  {level:<10} {count:>3} {bar}")

        report.append(f"\n按事件类型：")
        for etype, count in sorted(by_event_type.items(), key=lambda x: -x[1]):
            report.append(f"  {etype:<25} {count}")

        errors = [e for e in self._events if e.level >= LogLevel.ERROR]
        if errors:
            report.append(f"\n❌ 错误日志（共 {len(errors)} 条）：")
            for e in errors[-5:]:
                report.append(f"  • {e.timestamp} {e.message}")

        return "\n".join(report)


# ============================================================
# Agent 专用日志事件
# ============================================================

class AgentLogger:
    """
    Agent 专用日志封装
    提供语义化的日志事件方法
    """

    def __init__(self, service_name: str = "agent-service"):
        self.logger = StructuredLogger(service_name)
        self._session_id = self._gen_id()
        self._trace_id: Optional[str] = None

    def _gen_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def start_trace(self):
        """开始一个新的追踪"""
        self._trace_id = self._gen_id()
        self.logger.info("trace_started",
                         trace_id=self._trace_id,
                         session_id=self._session_id,
                         event_type="request_start",
                         service_version="1.0.0")

    def request_received(self, user_input: str, user_id: str = "anonymous"):
        """收到用户请求"""
        self.logger.info("request_received",
                         trace_id=self._trace_id,
                         user_id=user_id,
                         session_id=self._session_id,
                         event_type="request_received",
                         input_length=len(user_input),
                         input_preview=user_input[:50])

    def llm_call(self, model: str, input_tokens: int, output_tokens: int,
                 latency_ms: float, loop_iter: int = 1):
        """LLM 调用日志"""
        total_tokens = input_tokens + output_tokens
        self.logger.info("llm_call",
                         trace_id=self._trace_id,
                         session_id=self._session_id,
                         event_type="llm_call",
                         model=model,
                         input_tokens=input_tokens,
                         output_tokens=output_tokens,
                         total_tokens=total_tokens,
                         duration_ms=round(latency_ms, 2),
                         loop_iteration=loop_iter)

    def tool_call(self, tool_name: str, params: dict, latency_ms: float,
                  success: bool, error: Optional[str] = None):
        """工具调用日志"""
        log_method = self.logger.info if success else self.logger.error
        log_method("tool_call",
                   trace_id=self._trace_id,
                   session_id=self._session_id,
                   event_type="tool_call",
                   tool=tool_name,
                   params_preview=str(params)[:100],
                   success=success,
                   duration_ms=round(latency_ms, 2),
                   error=error)

    def safety_check(self, action: str, threat_type: Optional[str] = None,
                     blocked: bool = False):
        """安全检查日志"""
        if blocked:
            self.logger.warn("safety_blocked",
                             trace_id=self._trace_id,
                             session_id=self._session_id,
                             event_type="safety_check",
                             action=action,
                             threat_type=threat_type,
                             blocked=True)
        else:
            self.logger.debug("safety_passed",
                              trace_id=self._trace_id,
                              session_id=self._session_id,
                              event_type="safety_check",
                              action=action,
                              blocked=False)

    def request_completed(self, total_latency_ms: float, success: bool,
                          total_tokens: int, total_cost: float):
        """请求完成日志"""
        log_method = self.logger.info if success else self.logger.error
        log_method("request_completed",
                   trace_id=self._trace_id,
                   session_id=self._session_id,
                   event_type="request_completed",
                   total_duration_ms=round(total_latency_ms, 2),
                   success=success,
                   total_tokens=total_tokens,
                   total_cost=round(total_cost, 5))

    def get_report(self) -> str:
        return self.logger.get_report()


# ============================================================
# 模拟 Agent 运行
# ============================================================

def simulate_agent_request(agent_logger: AgentLogger, user_input: str, user_id: str):
    """模拟一次 Agent 请求并记录结构化日志"""
    agent_logger.start_trace()
    agent_logger.request_received(user_input, user_id)

    request_start = time.time()
    total_tokens = 0
    total_cost = 0.0

    # 安全检查
    agent_logger.safety_check("input_filter")

    # LLM 第一次调用
    llm1_latency = random.uniform(500, 2000)
    llm1_tokens = random.randint(300, 1000)
    agent_logger.llm_call("gpt-4o-mini", llm1_tokens // 2, llm1_tokens // 2,
                          llm1_latency, loop_iter=1)
    total_tokens += llm1_tokens
    total_cost += (llm1_tokens / 1000) * 0.00075

    # 工具调用
    tool_latency = random.uniform(200, 800)
    tool_success = random.random() > 0.1  # 90% 成功率
    if tool_success:
        agent_logger.tool_call("query_database",
                              {"query": user_input, "limit": 50},
                              tool_latency, True)
    else:
        agent_logger.tool_call("query_database",
                              {"query": user_input, "limit": 50},
                              tool_latency, False,
                              error="Database timeout")

    # LLM 第二次调用
    llm2_latency = random.uniform(1000, 3000)
    llm2_tokens = random.randint(500, 2000)
    agent_logger.llm_call("gpt-4o", llm2_tokens // 3 * 2, llm2_tokens // 3,
                          llm2_latency, loop_iter=2)
    total_tokens += llm2_tokens
    total_cost += (llm2_tokens / 1000) * 0.005

    # 输出安全审核
    agent_logger.safety_check("output_filter")

    # 请求完成
    total_latency = (time.time() - request_start) * 1000
    agent_logger.request_completed(total_latency, True, total_tokens, total_cost)


# ============================================================
# 演示
# ============================================================

def demo():
    print("=" * 60)
    print("📝 结构化日志演示")
    print("=" * 60)

    logger = AgentLogger("agent-service-v2")

    # 模拟 5 个请求
    requests = [
        ("查询昨天的销售数据", "user_001"),
        ("分析用户行为趋势", "user_002"),
        ("生成周报", "user_003"),
        ("查询库存数据", "user_001"),
        ("帮我把文件发到...", "user_004"),
    ]

    for i, (query, uid) in enumerate(requests):
        print(f"\n{'─' * 50}")
        print(f"📌 请求 {i+1}: {query} (用户: {uid})")
        print(f"{'─' * 50}")
        simulate_agent_request(logger, query, uid)

    print("\n" + "=" * 60)
    print(logger.get_report())


if __name__ == "__main__":
    demo()

    print("\n" + "=" * 60)
    print("📝 关键总结")
    print("=" * 60)
    print("""
📝 结构化日志核心要点：

1️⃣ Agent 关键日志事件：
   request_start → request_received → llm_call(×N) →
   tool_call(×N) → safety_check(×N) → request_completed

2️⃣ 每行日志必须包含：
   - timestamp（标准时间格式）
   - trace_id（关联到一次请求）
   - event_type（语义化事件类型）
   - level（日志级别）

3️⃣ Agent 特殊字段：
   - model: 使用的 LLM 模型
   - tokens: Token 消耗
   - duration_ms: 耗时
   - loop_iteration: 第几次循环

4️⃣ JSON 格式的好处：
   - Logstash/Loki 自动解析
   - 按字段聚合查询
   - Grafana 可关联到 Trace
""")
