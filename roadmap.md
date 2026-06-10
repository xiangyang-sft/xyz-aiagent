# 🗺️ 详细学习路线

> 每周更新进度，打勾 ✅ 表示已完成

## 第一阶段：基础入门（第 1-3 周）

### 第 1 周：LLM 基础
- [ ] 理解 Transformer 架构（Attention is All You Need）
- [ ] 了解 Prompt Engineering 基本技巧
- [ ] 掌握 Chat Completion API 调用
- [ ] 理解 Token、Temperature、Top-p 等概念
- [ ] **练习**：用 Python 调用 OpenAI/Anthropic API

### 第 2 周：Agent 概念入门
- [ ] Agent 的定义：LLM + 工具 + 记忆 + 规划
- [ ] 了解 LLM 的局限性（幻觉、上下文窗口、算力）
- [ ] 了解 Agent 的分类：单 Agent vs 多 Agent
- [ ] 了解 Agent 的应用场景
- [ ] **练习**：用 Python 调用一个 LLM API 做简单的问答 Agent

### 第 3 周：工具调用初探
- [ ] 理解 Function Calling 原理
- [ ] 写一个带工具的 LLM 调用（如搜索、计算器）
- [ ] 了解 ReAct 循环（Reasoning + Acting）
- [ ] 搭建第一个最简单的 Agent 项目
- [ ] **项目**：`hello-agent/`——做一个能调用工具的小 Agent

---

## 第二阶段：核心深入（第 4-6 周）

### 第 4 周：Agent 设计模式
- [ ] ReAct 模式详解
- [ ] Plan-and-Execute 模式
- [ ] Reflection 模式（自我反思与纠错）
- [ ] Tree of Thoughts
- [ ] **练习**：用 LangChain 实现 ReAct Agent

### 第 5 周：记忆与工具
- [ ] 短期记忆（对话历史）
- [ ] 长期记忆（向量数据库 RAG）
- [ ] 构建自定义工具
- [ ] 使用现成工具集
- [ ] **练习**：给 Agent 添加 RAG 记忆

### 第 6 周：多 Agent 协作
- [ ] 多 Agent 架构设计
- [ ] Agent 间通信模式
- [ ] CrewAI / AutoGen 上手
- [ ] 任务分配与结果聚合
- [ ] **项目**：实现一个多 Agent 协作系统

---

## 第三阶段：进阶实战（第 7-10 周）

### 第 7 周：Agent 评估
- [ ] Agent 评测框架
- [ ] 如何衡量 Agent 效果
- [ ] 追踪与调试（LangSmith、LangFuse）
- [ ] **练习**：对已有 Agent 做评测

### 第 8 周：Agent 安全
- [ ] Prompt Injection 防御
- [ ] 工具调用安全
- [ ] 输出安全与合规
- [ ] **练习**：给 Agent 加上安全策略

### 第 9 周：生产化部署
- [ ] Agent 性能优化
- [ ] 容器化部署（Docker）
- [ ] 监控与日志
- [ ] 成本控制
- [ ] **练习**：将 Agent 部署为 API 服务

### 第 10 周：高级主题
- [ ] Agent 与微调
- [ ] Agent 与 RLHF
- [ ] 大规模 Agent 系统
- [ ] **项目**：完整的端到端 Agent 应用

---

## 第四阶段：总结与精通（第 11-12 周）

### 第 11 周：论文精读
- [ ] 精读 5 篇以上顶级 Agent 论文
- [ ] 理解前沿方向（Agent 记忆、规划、社会模拟）
- [ ] **产出**：论文笔记

### 第 12 周：开源与分享
- [ ] 对开源 Agent 项目做贡献
- [ ] 写一篇 Agent 学习总结博客
- [ ] 构建自己的 Agent 工具/库
- [ ] **产出**：开源贡献或自己写的 Agent 库

---

## 🏆 里程碑

| 时间 | 里程碑 | 产出物 |
|------|--------|--------|
| 第 3 周 | ✅ 跑通第一个 Agent | `projects/hello-agent/` |
| 第 6 周 | ✅ 多 Agent 协作 | `projects/multi-agent/` |
| 第 10 周 | ✅ 多 Agent 协作系统 | `projects/10-multi-agent-system/` |
| 第 12 周 | ✅ 精通 Agent 开发 | 博客/开源贡献 |

---

> 💪 每天进步一点点，3 个月后回头看！
