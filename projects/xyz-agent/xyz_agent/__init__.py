"""
xyz-agent — 学习驱动的 Agent 框架

架构分层（参考 Hermes Agent）：
  engine/       — ReAct 推理循环（核心引擎）
  provider/     — LLM 提供者（OpenAI / 自定义）
  tool/         — 工具注册与执行
  skill/        — Skill 加载与管理
  memory/       — 短期/长期记忆
  mcp/          — MCP 协议客户端
  command/      — 内置命令系统
  agent/        — 高层 Agent 封装
  cli/          — 命令行接口

用法：
    from xyz_agent import Agent
    agent = Agent.from_openai(api_key="...")
    agent.run("你好")
"""

__version__ = "1.0.0"

from .agent import Agent, AgentConfig
from .engine import ReActEngine, ReActConfig, Step, ActionType
from .tool import ToolRegistry, tool, get_all_tools, execute_tool
from .skill import SkillManager, load_skills, list_skills
from .mcp_client import MCPManager
from .command import CommandSystem, is_command
from .providers import (
    LLMProvider, OpenAIProvider, OpenRouterProvider, MockProvider,
    build_tool_schemas,
)
