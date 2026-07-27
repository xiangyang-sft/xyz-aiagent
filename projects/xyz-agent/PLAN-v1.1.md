# xyz-agent v1.1 架构升级计划

## 目标
将 xyz-agent 从 "学习用 demo" 升级为 "生产可商用级别" 的 Agent 框架，
做到能够自然适配通用的外部 skill、MCP、commands 等生态。

## 核心设计原则
1. **接口标准化** — 所有扩展点遵循公开标准协议（MCP、OpenAI Function Calling）
2. **可插拔** — Skill/工具/MCP/命令都可以从外部动态加载，无需修改框架代码
3. **渐进式发现** — 自动发现并注册外部扩展
4. **安全沙箱** — 外部代码执行有安全边界

## 新增模块

### 1. Skill 系统 (`skill.py`)
- Skill = 可复用的能力单元（Prompt + Tools + Workflow）
- 支持从目录加载、远程加载
- Hermes Agent 兼容的 SKILL.md 格式

### 2. MCP 客户端 (`mcp_client.py`)
- 实现 Model Context Protocol 客户端
- 支持 stdio/HTTP 传输
- 自动发现并注册 MCP server 提供的工具

### 3. 命令系统 (`command.py`)
- 内置命令（/help, /tools, /clear, /config）
- 可扩展的外部命令
- 支持 slash 命令解析

### 4. 插件加载器 (`loader.py`)
- 从目录、包、URL 动态加载扩展
- 支持 YAML/JSON 配置
- 热加载支持

### 5. 架构升级
- 升级 engine.py 支持 Function Calling 原生格式
- 添加 OpenAI API 原生 provider
- 添加流式输出支持
- 添加追踪/日志系统
