# 🚀 Agent 生产化部署

> **第三阶段第 3 节** | 难度：🟠 进阶 | 预计阅读：60 分钟

---

## 全景速览

| 维度 | 说明 |
|------|------|
| **为什么重要** | Agent 教学演示和产品级部署之间隔着很大的工程鸿沟 |
| **核心挑战** | 监控不可见 → 追踪不连续 → 优化无依据 → 告警不及时 |
| **解决思路** | OpenTelemetry 追踪 → 结构化日志 → 性能监控 → 告警体系 |
| **关键工具** | OpenTelemetry / Prometheus / Grafana / LangFuse |
| **工程要点** | 容器化、Metrics 埋点、Trace Span、成本追踪、自动扩缩 |

---

## Step 1 — 基础：为什么 Agent 需要工程化部署？

### 1.1 从原型到生产的鸿沟

```python
# 教学演示：跑一次就完事
def demo_agent(user_input):
    result = llm_call(user_input)
    return result

# 生产部署：需要考虑 10 倍以上的复杂度
def production_agent(user_input):
    # 1. 监控埋点
    start_time = time.time()
    trace_id = start_trace()
    
    # 2. 追踪每一步
    with tracer.start_span("llm_call") as span:
        result = llm_call(user_input)
        span.set_attribute("tokens", count_tokens(result))
        span.set_attribute("latency_ms", (time.time() - start_time) * 1000)
    
    # 3. 记录成本
    track_cost(model="gpt-4o", input_tokens=150, output_tokens=300)
    
    # 4. 健康检查
    if is_degraded():
        alert_team("Agent latency spike")
    
    # 5. 结构化日志
    logger.info("agent_response", extra={
        "trace_id": trace_id,
        "latency": time.time() - start_time,
        "tokens": total_tokens,
    })
    
    return result
```

**生产部署 vs 原型的关键差异：**

| 维度 | 原型/教学 | 生产部署 |
|------|----------|---------|
| 运行 | 手动执行 | 服务化（API/异步/流式） |
| 监控 | print() 调试 | Metrics + Traces + Logs |
| 错误处理 | 崩溃就修复 | 重试、降级、熔断 |
| 成本 | 不在意 | 每笔交易都核算 |
| 可观测性 | 黑盒 | 全链路追踪 |
| 扩展性 | 单用户 | 多租户、高并发 |
| 可靠性 | 99% | 99.9%+ |

### 1.2 可观测性的三大支柱

```
┌──────────────────────────────────────────────────┐
│                  可观测性                         │
│                                                    │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐      │
│  │ Metrics  │   │  Traces  │   │   Logs   │      │
│  │ (指标)    │   │ (追踪)   │   │ (日志)    │      │
│  ├──────────┤   ├──────────┤   ├──────────┤      │
│  │ 请求数   │   │ Span 树  │   │ 结构化   │      │
│  │ 延迟     │   │ 调用链   │   | 日志     │      │
│  │ 错误率   │   │ 耗时分解  │   │ 审计     │      │
│  │ 成本/秒  │   │ LLM 调用 │   │ 异常     │      │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘      │
│       │              │              │             │
│       ▼              ▼              ▼             │
│  ┌─────────────────────────────────────┐          │
│  │          Grafana UI                  │          │
│  │  Prometheus → 指标看板              │          │
│  │  Tempo → 追踪详情                   │          │
│  │  Loki → 日志搜索                    │          │
│  └─────────────────────────────────────┘          │
└──────────────────────────────────────────────────┘
```

**Agent 场景下三大支柱的具体含义：**

- **Metrics**：QPS、P50/P95/P99 延迟、Token 消耗速率、工具调用成功率
- **Traces**：一次 Agent 请求内部的完整调用链（LLM → Tool1 → LLM → Tool2 → LLM → 回答）
- **Logs**：每次 LLM 调用的完整输入输出、错误堆栈、安全决策记录

---

## Step 2 — 核心概念深入

### 2.1 全链路追踪（Distributed Tracing）

Agent 的一个请求往往涉及多次 LLM 调用和工具执行，需要追踪完整路径：

```
用户请求 "帮我查销售数据并分析"
    │
    ├─ [root span] handle_request
    │   ├─ [child span] llm_call_1  (推理是否需要工具)
    │   │   ├─ attribute: model="gpt-4o"
    │   │   ├─ attribute: tokens=857
    │   │   └─ attribute: latency_ms=1200
    │   ├─ [child span] tool_call: query_database
    │   │   ├─ attribute: tool="query_sales"
    │   │   ├─ attribute: rows_returned=42
    │   │   └─ attribute: latency_ms=350
    │   ├─ [child span] llm_call_2  (基于数据生成分析)
    │   │   ├─ attribute: tokens=1204
    │   │   └─ attribute: latency_ms=2100
    │   └─ [child span] format_response
    │       └─ attribute: output_length=850
    │
    └─ root span 属性:
        ├─ total_tokens=2061
        ├─ total_cost=$0.041
        └─ total_latency=4250ms
```

**Span 的核心字段：**

| 字段 | 说明 | 示例 |
|------|------|------|
| `name` | Span 名称 | `llm_call`, `tool_query` |
| `trace_id` | 所属 Trace | `abc123...` |
| `span_id` | 自身 ID | `sp001` |
| `parent_span_id` | 父 Span ID | `sp000`（root 则为空） |
| `start_time` | 开始时间 | `2026-06-05T12:00:00Z` |
| `end_time` | 结束时间 | `2026-06-05T12:00:05Z` |
| `attributes` | 自定义属性 | `{"model": "gpt-4o", "tokens": 857}` |
| `status` | OK / ERROR | `OK` |

### 2.2 Metrics 指标体系

**核心指标分类：**

```
┌─────────────────────────────────────────────┐
│  🔵 业务指标                                │
│  ├─ 请求数（QPS/TPM）                       │
│  ├─ 任务成功率（Task Success Rate）          │
│  ├─ 平均响应时长（Avg Latency）              │
│  └─ 用户满意度（User Satisfaction Score）     │
├─────────────────────────────────────────────┤
│  🟢 性能指标                                │
│  ├─ P50/P95/P99 延迟                        │
│  ├─ LLM 调用延迟（分模型）                   │
│  ├─ 工具调用延迟（分工具）                   │
│  └─ Token 生成速率                          │
├─────────────────────────────────────────────┤
│  🟡 资源指标                                │
│  ├─ CPU/Memory 使用率                       │
│  ├─ API 调用频率                            │
│  ├─ 并发请求数                              │
│  └─ 队列积压长度                            │
├─────────────────────────────────────────────┤
│  🔴 成本指标                                │
│  ├─ 每次请求的 API 成本                     │
│  ├─ 每日/周/月总成本                        │
│  ├─ 各模型成本占比                          │
│  └─ Token 浪费率（重试/失败）                │
└─────────────────────────────────────────────┘
```

### 2.3 结构化日志

生产环境中不应使用 `print()`，而应使用结构化日志：

```python
# ❌ 不可查询
print(f"用户输入：{user_input}，响应：{response}")

# ✅ 可查询、可聚合、可告警
import structlog
logger = structlog.get_logger()

logger.info("agent_request", 
    trace_id="abc123",
    user_id="user_42",
    input_length=len(user_input),
    model="gpt-4o",
    tokens_used=857,
    latency_ms=1200,
    tools_called=["query_database"],
    success=True,
    cost_usd=0.021,
)
```

**Agent 场景下需要记录的关键日志事件：**

| 事件 | 记录内容 |
|------|---------|
| `request_start` | 用户请求到达，trace_id 生成 |
| `llm_call` | 每次 LLM 调用：model、tokens、latency、temperature |
| `tool_call` | 每次工具调用：tool_name、params、result、latency |
| `tool_result` | 工具执行结果摘要 |
| `safety_check` | 安全决策：allowed/blocked/confirmed |
| `request_end` | 请求完成：total_tokens、total_cost、总延迟、成功/失败 |

### 2.4 监控告警体系

**告警级别与触发条件：**

| 级别 | 条件 | 响应 |
|------|------|------|
| 🔴 **P0 紧急** | Agent 完全不可用 / 错误率 > 10% | 立即通知 on-call |
| 🟠 **P1 严重** | P99 延迟 > 10s / Token 成本激增 2x | 15 分钟内响应 |
| 🟡 **P2 警告** | 工具调用成功率 < 90% / 单模型异常 | 工作时间内处理 |
| 🔵 **P3 通知** | 使用量达到预警线 / 新版本部署 | 记录即可 |

**典型告警规则：**

```
告警名: agent_high_latency
条件:   avg(agent_request_duration_ms{status="success"}[5m]) > 5000
严重性: P1
消息:   Agent 响应延迟异常 -> P99 响应时间超过 5s

告警名: agent_high_error_rate
条件:   rate(agent_errors_total[5m]) / rate(agent_requests_total[5m]) > 0.05
严重性: P0
消息:   Agent 错误率超过 5%

告警名: agent_cost_spike
条件:   agent_cost_per_minute > 1.0  # $1/分钟的消耗
严重性: P2
消息:   API 成本异常升高，当前速率 ${cost_per_min}/分钟
```

### 2.5 成本追踪与优化

LLM 调用的成本是 Agent 生产化的重要考量：

**成本构成：**

```
单次 Agent 请求成本 = 
    Σ(每次 LLM 调用的 input_tokens × input_price + output_tokens × output_price)
    + Σ(每次工具调用的 API 费用)
    + 基础设施成本（服务器/GPU/带宽）
```

**优化策略：**

| 策略 | 做法 | 效果 |
|------|------|------|
| **模型分层** | 简单任务用小模型，复杂任务用大模型 | 节省 60-80% |
| **缓存** | 缓存重复的 LLM 调用结果 | 节省 20-40% |
| **Token 预算** | 限制 max_tokens，设置 Token 上限 | 避免失控 |
| **批处理** | 合并多个小请求为一个 LLM 调用 | 节省 30% |
| **语义缓存** | 语义相似查询命中缓存 | 节省 15-25% |
| **Prompt 压缩** | 精简历史消息，减少上下文长度 | 节省 10-30% |

### 2.6 容器化与部署架构

```
                        ┌─────────────┐
                        │   Nginx/LB  │
                        └──────┬──────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │ Agent    │    │ Agent    │    │ Agent    │
        │ Instance │    │ Instance │    │ Instance │
        │ 1        │    │ 2        │    │ 3        │
        └────┬─────┘    └────┬─────┘    └────┬─────┘
             │               │               │
             └───────────────┼───────────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                ▼                ▼
     ┌──────────┐     ┌──────────┐     ┌──────────┐
     │ LLM API  │     │ 工具服务  │     │ 数据库   │
     │ (外部)   │     │ (内部)   │     │ (缓存)   │
     └──────────┘     └──────────┘     └──────────┘

     可观测性基础设施：
     ┌────────────────────────────────────┐
     │ Prometheus ← Metrics               │
     │ OpenTelemetry ← Traces              │
     │ Loki/Elasticsearch ← Logs           │
     │ Grafana ← 统一面板                  │
     └────────────────────────────────────┘
```

**Docker 部署要点：**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 暴露端口
EXPOSE 8000

# 启动
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2.7 可观测性框架选型

| 工具 | 用途 | 优势 | 劣势 |
|------|------|------|------|
| **OpenTelemetry** | 通用追踪标准 | 厂商中立、生态丰富 | 配置较复杂 |
| **Prometheus** | Metrics 采集 | 成熟、社区大 | 不支持长期存储 |
| **Grafana** | 可视化 | 面板精美、数据源多 | 学习曲线 |
| **LangFuse** | LLM 专用追踪 | 原生支持 Token 追踪、评估 | 生态较小 |
| **LangSmith** | LLM 专用平台 | 调试友好、集成方便 | 闭源、成本高 |
| **ELK Stack** | 日志聚合 | 全文搜索强、成熟 | 重、维护成本高 |
| **Datadog** | 全栈可观测性 | 开箱即用 | 贵 |

---

## Step 3 — 完整代码实战

实战项目 `projects/09-agent-deployment/` 包含 4 个递进文件：

| 文件 | 核心内容 |
|------|---------|
| `step1-basic-metrics.py` | Metrics 埋点 + Prometheus 格式 |
| `step2-tracing.py` | OpenTelemetry 风格的 Span 树追踪 |
| `step3-structured-logging.py` | 结构化日志 + 日志级别 + 事件分类 |
| `step4-production-agent.py` | 完整的可观测 Agent + 成本追踪 + 健康检查 |

📍 **代码位置：** `projects/09-agent-deployment/`

---

### 🎯 面试题

#### Q1: 可观测性的三大支柱是什么？在 Agent 场景下各自关注什么？

**参考答案：**
- **Metrics（指标）**：关注整体健康状态——QPS、延迟分布、错误率、Token 消耗速率、成本/分钟
- **Traces（追踪）**：关注单次请求的内部细节——LLM 调用了多少次、每个工具花了多久、瓶颈在哪里
- **Logs（日志）**：关注事件详情——每次 LLM 调用的完整输入输出、工具执行结果、安全决策
- **Agent 特殊性**：与传统 Web 服务不同，Agent 的一次请求内部可能有 3-10 次 LLM 调用 + 多次工具调用，如果没有追踪，根本无法理解"这 5 秒都在干什么"

#### Q2: Agent 的全链路追踪中，Span 树应该怎么设计？

**参考答案：**
```
Root Span: agent_request
  ├─ Span: llm_reason (每次 Agent 循环中的 LLM 调用)
  │   ├─ attribute: model, tokens, latency, temperature
  │   └─ attribute: loop_iteration (第几次循环)
  ├─ Span: tool_exec (每次工具调用)
  │   ├─ attribute: tool_name, params, latency
  │   └─ attribute: success/failure, error_message
  ├─ Span: memory_retrieval (RAG 查询)
  │   └─ attribute: top_k, relevance_scores
  └─ Span: safety_check (安全检测)
      └─ attribute: policy, action (allow/block/confirm)
```
关键点：让 Span 树反映 Agent 的循环结构，而不是扁平化

#### Q3: 如何计算每个 Agent 请求的成本？

**参考答案：**
```python
def calculate_request_cost(traces: list) -> dict:
    total_cost = 0
    break downs=["input_price": 0.00001/1K tokens, "output_price": 0.00003/1K tokens}])
    for span in traces:
        if span.name == "llm_call":
            input_tokens = span.attributes.get("input_tokens", 0)
            output_tokens = span.attributes.get("output_tokens", 0)
            model = span.attributes.get("model", "gpt-4o-mini")
            pricing = MODEL_PRICING[model]
            total_cost += (input_tokens * pricing["input"] / 1000 +
                         output_tokens * pricing["output"] / 1000)
    return {"total_cost": total_cost, "detail": spans_by_cost}
```

#### Q4: 怎么设计 Agent 的监控告警规则？

**参考答案：**
按严重性分层：
- **P0（立即）**：错误率 > 10%、P99 延迟 > 10s、Agent 完全不可用
- **P1（紧急）**：错误率 > 5%、P99 > 5s、工具调用成功率 < 80%
- **P2（警告）**：成本突增 2x+、单模型延迟异常、QPS 陡降
- **P3（通知）**：达到日预算 80%、新版本部署、模型更新

避免告警风暴的技巧：为每个 Agent 角色/类型设置独立告警，使用聚合规则合并同类告警

#### Q5: 模型分层策略具体怎么做？

**参考答案：**
```python
ROUTING_RULES = {
    # 规则：(条件, 模型)
    "greeting": (lambda ctx: "你好" in ctx.user_input or "hello" in ctx.user_input, "gpt-4o-mini"),
    "simple_query": (lambda ctx: len(ctx.tools_needed) == 0, "gpt-4o-mini"),
    "reasoning": (lambda ctx: len(ctx.complexity) > 5, "gpt-4o"),
    "coding": (lambda ctx: any(kw in ctx.user_input for kw in ["代码", "debug", "编程"]), "claude-sonnet-4"),
    "default": (None, "gpt-4o-mini"),
}
```
先尝试小模型，如果小模型失败或置信度低，fallback 到大模型（cascade 策略）

#### Q6: 结构化日志和普通 print 的关键区别是什么？

**参考答案：**
1. **可查询**：结构化日志按 key-value 查询，print 只能全文搜索
2. **可聚合**：可以按 model、user_id 等字段聚合统计
3. **标准格式**：JSON 格式可以被 Logstash/Loki 等工具自动解析
4. **级别控制**：DEBUG/INFO/WARN/ERROR 可以动态调整
5. **上下文关联**：trace_id 可以将多个日志关联到同一个请求
6. **性能**：结构化日志往往异步写入，不影响主流程

#### Q7: Agent 部署中，健康检查（Health Check）应该检查什么？

**参考答案：**
```python
@app.get("/health")
def health_check():
    checks = {
        "llm_api": check_llm_api(),          # LLM API 是否可达
        "tool_services": check_all_tools(),   # 所有工具服务是否正常
        "memory_store": check_db(),           # 记忆存储是否可用
        "cache": check_cache(),               # 缓存是否正常
        "latency": check_recent_latency(),    # 近期延迟是否在正常范围
    }
    all_healthy = all(c["status"] == "ok" for c in checks.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks,
    }
```

#### Q8: 如何追踪 Agent 的 Token 消耗并优化成本？

**参考答案：**
**追踪方案：**
- 每次 LLM 调用记录 input_tokens, output_tokens, model
- Prometheus Counter + Histogram 聚合
- 按 user_id、session、tool 分类统计

**优化策略：**
1. **语义缓存**：相同语义的查询命中缓存（如 "今天天气" 和 "今日天气"）
2. **上下文裁剪**：超出窗口的历史消息用摘要替换
3. **模型分级**：简单问题用小模型
4. **重试优化**：失败时不要重试相同 prompt（加 instruction 再试）
5. **监控告警**：设置日/周预算，接近时自动降级

---

## 总结

| 维度 | 关键要点 |
|------|---------|
| **可观测性** | 三大支柱缺一不可：Metrics 看宏观、Traces 看微观、Logs 看详情 |
| **追踪设计** | Span 树要反映 Agent 的循环结构，而非扁平化 |
| **成本** | Token 是核心计费单位，模型分层可省 60-80% |
| **告警** | 按 P0-P3 分层，避免告警风暴 |
| **健康检查** | LLM API + 工具 + 存储 + 缓存四方面 |
| **部署** | 容器化 + 水平扩展 + 多实例 |

---

> 下一节预告：**动手：开发一个多 Agent 协作系统** 🏗️
