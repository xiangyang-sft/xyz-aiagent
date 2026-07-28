#!/usr/bin/env python3
"""
xyz_agent.agent — 高级 Agent 封装（v2 — 生产版）

提供完整的 Agent 使用体验，集成了：
  - ToolRegistry（工具注册/执行）
  - SkillManager（技能加载/使用）
  - MCPManager（MCP 服务器连接/工具发现）
  - CommandSystem（命令解析/执行）
  - ExtensionLoader（外部扩展自动发现）
  - ReActEngine v2（支持 Function Calling）
  - LLMProvider（多种 LLM 后端）

用法:
    # 快速创建
    agent = Agent.from_openai(api_key="...")
    result = agent.run("北京的天气怎么样？")

    # 完整配置
    agent = Agent(config=AgentConfig(...))
    agent.setup_tools(...)
    agent.setup_skills("~/.hermes/skills/")
    result = agent.run("帮我查资料")
"""

import json
import time
import logging
import os
from typing import Callable, Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime

from .engine import ReActEngine, ReActConfig, Step, ActionType
from .tool import ToolRegistry, ToolDef, _default_registry, get_all_tools, execute_tool
from .skill import SkillManager, get_default_skill_manager
from .mcp_client import MCPManager
from .command import CommandSystem, get_default_command_system, is_command
from .loader import ExtensionLoader, get_default_loader
from .providers import (
    LLMProvider, OpenAIProvider, OpenRouterProvider,
    build_tool_schemas,
)
from . import __version__

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Agent 完整配置"""
    name: str = "xyz-agent"
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 4096
    max_steps: int = 15
    verbose: bool = False
    system_prompt: Optional[str] = None
    auto_load_skills: bool = True
    auto_load_extensions: bool = True
    skill_dirs: List[str] = field(default_factory=lambda: [
        "~/.hermes/skills/",
        "./skills/",
    ])
    extension_dirs: List[str] = field(default_factory=lambda: [
        "~/.xyz-agent/",
        "./extensions/",
    ])
    enable_commands: bool = True
    enable_mcp: bool = False
    enable_skills: bool = True
    react_mode: str = "auto"  # "react" | "function_calling" | "auto"


class Agent:
    """
    高级 Agent 封装（v2 — 生产版）

    集成了所有子系统，提供统一的使用体验。

    用法:
        # 快速启动
        agent = Agent.from_openai(api_key=...)
        result = agent.run("帮我查资料")

        # 多轮对话
        agent.chat("你好")
        agent.chat("天气怎么样？")

        # 手动控制
        agent.reset("写首诗")
        while not agent.done:
            agent.step()
            print(agent.last_output)
    """

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        config: Optional[AgentConfig] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ):
        self.config = config or AgentConfig()
        self.name = self.config.name

        # 核心组件
        self.tool_registry = tool_registry or _default_registry
        self.skill_manager = SkillManager(tool_registry=self.tool_registry) if self.config.enable_skills else None
        self.mcp_manager = MCPManager() if self.config.enable_mcp else None
        self.command_system = CommandSystem() if self.config.enable_commands else None
        self.loader = ExtensionLoader()
        self.provider = llm_provider
        self.engine: Optional[ReActEngine] = None

        # 状态
        self._initialized = False
        self.last_output = ""
        self.session_id = f"{self.name}_{int(time.time())}"
        self.created_at = time.time()
        self._tool_schemas: List[Dict] = []
        self._last_step: Optional[Step] = None

    # ============================================================
    # 工厂方法
    # ============================================================

    @classmethod
    def from_openai(cls, api_key: Optional[str] = None,
                    model: str = "gpt-4o",
                    **kwargs) -> "Agent":
        """从 OpenAI API 创建 Agent"""
        provider = OpenAIProvider(api_key=api_key, model=model)
        config = AgentConfig(model=model, **kwargs)
        return cls(llm_provider=provider, config=config)

    @classmethod
    def from_openrouter(cls, api_key: Optional[str] = None,
                        model: str = "openai/gpt-4o",
                        **kwargs) -> "Agent":
        """从 OpenRouter 创建 Agent"""
        provider = OpenRouterProvider(api_key=api_key, model=model)
        config = AgentConfig(model=model, **kwargs)
        return cls(llm_provider=provider, config=config)

    # ============================================================
    # 初始化
    # ============================================================

    def initialize(self):
        """初始化 Agent（自动发现扩展、构建引擎）"""
        if self._initialized:
            return

        # 1. 自动加载扩展
        if self.config.auto_load_extensions:
            self._discover_extensions()

        # 2. 自动加载 Skills
        if self.config.enable_skills and self.config.auto_load_skills:
            self._load_default_skills()

        # 3. 构建工具 schema（用于 Function Calling）
        self._tool_schemas = self._build_tool_schemas()

        # 4. 设置命令系统上下文
        if self.command_system is not None:
            self.command_system.set_context(
                agent=self,
                tool_registry=self.tool_registry,
                skill_manager=self.skill_manager,
                mcp_manager=self.mcp_manager,
                config=self.config.__dict__,
                session_id=self.session_id,
            )

        # 5. 构建引擎
        self._build_engine()

        self._initialized = True
        logger.info(f"Agent '{self.name}' 初始化完成 (v{__version__})")
        return self

    def _discover_extensions(self):
        """自动发现外部扩展"""
        for directory in self.config.extension_dirs:
            expanded = os.path.expanduser(directory)
            if os.path.isdir(expanded):
                self.loader.load_directory(expanded)

        # 应用发现的扩展
        self.loader.apply_to(
            skill_manager=self.skill_manager,
            mcp_manager=self.mcp_manager,
            command_system=self.command_system,
            tool_registry=self.tool_registry,
        )

    def _load_default_skills(self):
        """加载默认位置的 Skills"""
        if not self.skill_manager:
            return
        for directory in self.config.skill_dirs:
            self.skill_manager.load_directory(directory)

    def _build_tool_schemas(self) -> List[Dict]:
        """构建 OpenAI Function Calling 格式的工具 schema"""
        tools = self.tool_registry.list_tools()

        # 添加 MCP 工具的 schema
        if self.mcp_manager is not None:
            for server_name in self.mcp_manager.list_servers():
                server = self.mcp_manager.get_server(server_name)
                if server and server.is_connected:
                    for tool in server.tools:
                        tools.append({
                            "name": f"mcp:{server_name}:{tool.get('name')}",
                            "description": tool.get("description", ""),
                            "parameters": tool.get("inputSchema", tool.get("parameters", {})),
                        })

        return build_tool_schemas(tools)

    def rebuild_engine(self):
        """重建引擎（加载新工具/Skill/MCP 后调用）"""
        self._build_engine()
        return self

    def _build_engine(self):
        """构建 ReAct 引擎"""
        # 构建系统提示词
        system_prompt = self._build_system_prompt()

        # 构建 LLM 调用包装
        if self.provider:
            def llm_call_with_tools(prompt_or_messages, tools_or_messages=None):
                """兼容两种调用签名：
                   - 传统模式: (prompt: str, messages: list) -> (response, tokens)
                   - FC 模式:  (messages: list, tools: list|None) -> (response, tokens, tool_calls)
                """
                result = (
                    self.provider.chat(
                        messages=tools_or_messages or [],
                        temperature=self.config.temperature,
                        max_tokens=self.config.max_tokens,
                    )
                    if isinstance(prompt_or_messages, str)
                    else self.provider.chat(
                        messages=prompt_or_messages,
                        tools=tools_or_messages,
                        temperature=self.config.temperature,
                        max_tokens=self.config.max_tokens,
                    )
                )
                # Provider 统一返回三元组 (response, tokens, tool_calls)
                # 传统模式只取前两个
                if isinstance(prompt_or_messages, str):
                    return result[0], result[1]
                return result
            llm_fn = llm_call_with_tools
        else:
            llm_fn = self._default_llm

        # 构建工具执行器
        def tool_executor(name: str, args: Dict) -> str:
            return self.tool_registry.execute_safe(name, args)

        # 构建引擎配置
        react_config = ReActConfig(
            max_steps=self.config.max_steps,
            verbose=self.config.verbose,
            mode=self.config.react_mode,
        )

        self.engine = ReActEngine(
            llm_call=llm_fn,
            tool_executor=tool_executor,
            config=react_config,
            system_prompt=system_prompt,
            tools=self._tool_schemas,
        )

    def _build_system_prompt(self) -> str:
        """构建完整的系统提示词"""
        parts = [self.config.system_prompt or self._default_system_prompt()]

        # 注入 Skill system prompts
        if self.skill_manager is not None:
            skill_prompts = self.skill_manager.get_system_prompts()
            if skill_prompts:
                parts.append("\n\n[已加载的 Skill]")
                parts.extend(skill_prompts)

        # 工具列表
        tools = self.tool_registry.list_tools()
        if tools:
            parts.append("\n\n[可用工具]")
            for t in tools:
                parts.append(f"  - {t['name']}: {t['description']}")

        # 命令说明
        if self.command_system is not None:
            parts.append("\n\n[命令]")
            parts.append("  输入 /help 查看可用命令")
            parts.append("  输入 /tools 查看所有工具")
            parts.append("  输入 /skills 查看所有 Skill")

        return "\n".join(parts)

    # ============================================================
    # 核心运行
    # ============================================================

    def run(self, question: str) -> str:
        """
        运行 Agent 处理问题

        自动处理：
          - 命令解析
          - Skill 注入
          - 工具调用
          - MCP 工具发现

        返回:
          最终答案
        """
        if not self._initialized:
            self.initialize()

        # 检查是否是命令
        if self.command_system and is_command(question):
            result = self.command_system.execute(question)
            self.last_output = result
            return result

        # 运行引擎
        result = self.engine.run(question)
        self.last_output = result
        return result

    def chat(self, message: str) -> str:
        """
        多轮对话

        保留上下文，支持连续对话。
        """
        if not self._initialized:
            self.initialize()

        # 检查是否是命令
        if self.command_system and is_command(message):
            result = self.command_system.execute(message)
            self.last_output = result
            return result

        # 如果是新对话，reset
        if not self.engine or self.engine.done:
            self.engine.reset(message)
        else:
            self.engine.add_user_message(message)
            self.engine.done = False

        # 运行
        result = self.engine.run(message)
        self.last_output = result
        return result

    # ============================================================
    # 手动控制
    # ============================================================

    def reset(self, question: str = ""):
        """重置 Agent 状态"""
        if self.engine:
            if question:
                self.engine.reset(question)
            else:
                self.engine.clear_messages()
        self.last_output = ""

    def step(self) -> Optional[Step]:
        """单步执行"""
        if not self._initialized:
            self.initialize()
        if not self.engine:
            return None
        step = self.engine.step()
        self._last_step = step
        return step

    @property
    def done(self) -> bool:
        return self.engine is not None and self.engine.done

    @property
    def messages(self) -> List[Dict]:
        return self.engine.messages if self.engine else []

    # ============================================================
    # 工具管理与发现
    # ============================================================

    def setup_tools(self, *tools: Callable):
        """设置工具（注册可调用函数）"""
        for tool_fn in tools:
            self.tool_registry.register(tool_fn)

    def setup_mcp(self, name: str, command: str, args: Optional[List[str]] = None,
                  auto_connect: bool = True) -> bool:
        """连接 MCP 服务器"""
        if not self.mcp_manager:
            raise RuntimeError("MCP 未启用 (config.enable_mcp=True)")
        try:
            self.mcp_manager.connect_stdio(name, command, args, auto_connect=auto_connect)
            # 重新构建引擎（新的工具）
            self._build_engine()
            return True
        except Exception as e:
            logger.error(f"MCP 连接失败: {e}")
            return False

    def discover_mcp_tools(self):
        """发现 MCP 工具并注册到注册表"""
        if self.mcp_manager is not None:
            self.mcp_manager.discover_all_tools_sync(registry=self.tool_registry)
            # 重建引擎同步工具
            self._tool_schemas = self._build_tool_schemas()
            self._build_engine()

    def refresh_skills(self):
        """刷新所有 Skill"""
        if self.skill_manager is not None:
            count = self.skill_manager.refresh()
            if count > 0:
                self.rebuild_engine()
            return count
        return 0

    # ============================================================
    # 信息查询
    # ============================================================

    def get_info(self) -> Dict:
        """获取 Agent 完整信息"""
        tools = self.tool_registry.list_tools()
        skills = self.skill_manager.list_skills() if self.skill_manager else []
        mcp_servers = self.mcp_manager.list_servers() if self.mcp_manager else []

        return {
            "name": self.name,
            "version": __version__,
            "model": self.config.model,
            "initialized": self._initialized,
            "tools": len(tools),
            "skills": len(skills),
            "mcp_servers": len(mcp_servers),
            "engine_mode": self.engine._mode if self.engine else "N/A",
            "session_id": self.session_id,
            "uptime_seconds": int(time.time() - self.created_at),
        }

    def list_tools(self) -> List[Dict]:
        """列出所有工具"""
        return self.tool_registry.list_tools()

    def list_skills(self) -> List[Dict]:
        """列出所有 Skill"""
        if self.skill_manager is not None:
            from .skill import list_skills
            return list_skills()
        return []

    def get_stats(self) -> Dict:
        """获取运行统计"""
        if self.engine:
            return self.engine.get_stats()
        return {}

    # ============================================================
    # 默认值
    # ============================================================

    def _default_llm(self, prompt_or_messages, tools=None):
        """默认 LLM 调用（提示用户配置）"""
        logger.warning("未配置 LLM Provider，使用模拟响应")
        if isinstance(prompt_or_messages, str):
            # 传统模式: 返回 (response, tokens)
            return "最终答案: 这是一个模拟响应。请通过 Agent.from_openai(api_key=...) 配置真实的 LLM。", 50
        # FC 模式: 返回 (response, tokens, tool_calls)
        return "最终答案: 这是一个模拟响应。请通过 Agent.from_openai(api_key=...) 配置真实的 LLM。", 50, None

    def _default_system_prompt(self) -> str:
        return f"""你是一个 AI Agent（{self.name} v{__version__}），通过调用工具来解决问题。

你的工作流程：
1. 分析用户的问题
2. 如需信息，调用工具获取
3. 根据观察结果推理
4. 重复直到可以给出答案
5. 给出清晰、有用的最终回答

核心原则：
- 每次调用一个工具
- 如果工具出错，尝试其他方法
- 当你有足够信息时给出答案
- 使用中文回答"""

    def __repr__(self) -> str:
        return f"Agent(name='{self.name}', model={self.config.model})"
