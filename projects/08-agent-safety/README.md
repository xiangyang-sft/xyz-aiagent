# 08-agent-safety — Agent 安全与对齐

> 第三阶段第 2 节：从 Prompt Injection 防御到完整的安全 Agent

## 文件结构

| 文件 | 内容 | 学到什么 |
|------|------|----------|
| `step1-prompt-injection.py` | Prompt Injection 演示 + 防御过滤器 | 直接/间接注入的原理与防御 |
| `step2-tool-security.py` | 工具安全三层模型 + 权限控制 | 最小权限、速率限制、审计追踪 |
| `step3-output-filter.py` | 输出审核 Pipeline + 敏感信息检测 | 规则过滤 + 语义审核 + PII 脱敏 |
| `step4-robust-agent.py` | 完整的安全 Agent | 注入 + 权限 + 审核 + 审计一体 |

## 快速运行

```bash
# 逐一演示
python step1-prompt-injection.py
python step2-tool-security.py
python step3-output-filter.py
python step4-robust-agent.py
```

## 核心架构

```
用户输入
    │
    ▼
┌──────────────────────┐
│ 输入层               │
│ · Prompt Injection   │
│ · 指令隔离           │
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│ 决策层               │
│ · 工具权限检查       │
│ · 参数校验           │
│ · 速率限制           │
│ · 人工确认(危险)     │
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│ 执行层               │
│ · 工具执行           │
└──────┬───────────────┘
       ▼
┌──────────────────────┐
│ 输出层               │
│ · 规则过滤           │
│ · PII 脱敏           │
│ · 语义审核           │
└──────────────────────┘

📋 审计日志（全程记录）
```
