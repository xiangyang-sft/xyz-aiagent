"""
xyz-agent — 轻量级 AI Agent 框架

渐进式构建，模块化设计，从最小可用到生产就绪。

模块：
  engine    — ReAct 循环引擎（思考→行动→观察）
  agent     — 高级 Agent 封装（配置+会话+追踪）
  tool      — 工具系统（注册/执行/MCP）
  memory    — 记忆系统（短期/长期/RAG）
  orchestrator — 多 Agent 编排引擎
  cli       — 命令行接口
"""

__version__ = "0.1.0"

from .agent import Agent, AgentConfig
from .engine import ReActEngine, ReActConfig, Step, ActionType
from .tool import (
    ToolRegistry, tool, get_all_tools,
    get_openai_tool_defs, execute_tool,
)
from .memory import (
    ShortTermMemory, LongTermMemory, RAGMemory, MemorySystem,
)
