# 09-agent-deployment — Agent 生产化部署

> 第三阶段第 3 节：从 Metrics 埋点到完整可观测 Agent

## 文件结构

| 文件 | 内容 | 学到什么 |
|------|------|----------|
| `step1-basic-metrics.py` | Metrics 埋点 + Prometheus 格式 | Counter/Histogram/Gauge 三种指标类型 |
| `step2-tracing.py` | OpenTelemetry 风格 Span 树追踪 | 全链路追踪 + 火焰图格式 |
| `step3-structured-logging.py` | 结构化日志 + 事件分类 | JSON 日志、Agent 专用事件类型 |
| `step4-production-agent.py` | 完整可观测 Agent | Metrics+Traces+Logs三合一+成本追踪+健康检查 |

## 快速运行

```bash
python step1-basic-metrics.py      # Metrics 演示
python step2-tracing.py            # 追踪演示
python step3-structured-logging.py # 结构化日志演示
python step4-production-agent.py   # 完整可观测 Agent（含真实 sleep，约 30s）
```

## 核心架构

```
┌────────────────────────────────────┐
│         ObservableAgent            │
│                                    │
│  ┌────────┐ ┌────────┐ ┌────────┐ │
│  │Metrics │ │Traces  │ │ Logs   │ │
│  │Counter │ │Span树  │ │JSON    │ │
│  │Histogram│ │可视化  │ │事件分类│ │
│  │Gauge   │ │火焰图  │ │级别控制│ │
│  └────────┘ └────────┘ └────────┘ │
│                                    │
│  🏥 Health Check  💰 Cost Tracking│
└────────────────────────────────────┘
```

## 生产实践

| 组件 | 推荐工具 |
|------|---------|
| Metrics 采集 | Prometheus |
| 追踪系统 | Jaeger / Grafana Tempo |
| 日志系统 | Loki / Elasticsearch |
| 可视化 | Grafana |
| LLM 专用 | LangFuse / LangSmith |
