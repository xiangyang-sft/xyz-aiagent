"""
xyz-agent — 生产级 AI Agent 框架

从学习到生产就绪的模块化 Agent 框架。
支持 Skill、MCP、Commands、Function Calling 等现代 Agent 架构。

模块：
  engine       — ReAct 循环引擎（思考→行动→观察）
  agent        — 高级 Agent 封装（集成所有子系统）
  tool         — 工具系统（注册/验证/执行/MCP）
  memory       — 记忆系统（短期/长期/RAG）
  skill        — Skill 系统（SKILL.md 加载/注册）
  mcp_client   — MCP 客户端（stdio/HTTP 传输/工具发现）
  command      — 命令系统（内建/外部/slash 命令）
  loader       — 扩展加载器（自动发现/配置加载）
  providers    — LLM Provider（OpenAI/OpenRouter/Mock）
  orchestrator — 多 Agent 编排引擎
  cli          — 命令行接口

用法:
    from xyz_agent import Agent
    agent = Agent.from_openai(api_key="...")
    result = agent.run("北京的天气怎么样？")
"""

__version__ = "1.0.0"

from .agent import Agent, AgentConfig
from .engine import ReActEngine, ReActConfig, Step, ActionType
from .tool import (
    ToolRegistry, ToolDef, tool, get_all_tools,
    get_openai_tool_defs, execute_tool,
)
from .skill import (
    SkillManager, SkillDef,
    load_skills, list_skills,
    get_default_skill_manager,
)
from .mcp_client import (
    MCPManager, MCPServerConnection, StdioMCPServer,
)
from .command import (
    CommandSystem, CommandDef, CommandContext,
    execute_command, is_command,
    get_default_command_system,
)
from .loader import (
    ExtensionLoader, ExtensionConfig,
    load_extensions, generate_sample_config,
    get_default_loader,
)
from .memory import (
    ShortTermMemory, LongTermMemory, RAGMemory, MemorySystem,
)
from .providers import (
    LLMProvider, OpenAIProvider, OpenRouterProvider, MockProvider,
    build_tool_schemas,
)
from .orchestrator import (
    Orchestrator, OrchestratorConfig, CollabMode,
)
