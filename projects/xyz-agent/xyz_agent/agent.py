#!/usr/bin/env python3
"""
xyz_agent.agent — 高级 Agent 封装

提供更易用的 Agent 类，包含：
  - 默认配置
  - 会话管理
  - 组件注入（工具系统、记忆系统）
  - 流式输出支持
"""

import json
import time
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field

from .engine import ReActEngine, ReActConfig


@dataclass
class AgentConfig:
    """Agent 配置"""
    name: str = "default-agent"
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 4096
    max_steps: int = 15
    verbose: bool = False
    system_prompt: Optional[str] = None


class Agent:
    """
    高级 Agent 封装

    用法:
        agent = Agent(
            llm_provider=my_llm_function,
            tools=[my_tool_schema],
            config=AgentConfig(name="my-agent")
        )
        result = agent.run("请问北京的天气")
    """

    def __init__(
        self,
        llm_provider: Callable,
        tools: Optional[List[Dict]] = None,
        config: Optional[AgentConfig] = None,
        system_prompt: Optional[str] = None,
    ):
        self.config = config or AgentConfig()
        self.tools = tools or []

        # 构建 ReAct 配置
        react_config = ReActConfig(
            max_steps=self.config.max_steps,
            verbose=self.config.verbose,
        )

        # 构建系统提示词（包含工具描述）
        tool_descriptions = self._build_tool_descriptions()
        full_system_prompt = (system_prompt or self.config.system_prompt
                              or self._default_system_prompt())
        full_system_prompt = full_system_prompt.replace(
            "{tool_descriptions}", tool_descriptions
        )

        # 创建引擎
        def tool_executor(name: str, args: Dict) -> str:
            for t in self.tools:
                if t.get("name") == name:
                    fn = t.get("fn")
                    if fn:
                        return str(fn(**args))
                    return f"工具 '{name}' 未绑定函数"
            return f"未知工具: {name}"

        self.engine = ReActEngine(
            llm_call=self._wrap_llm(llm_provider),
            tool_executor=tool_executor,
            config=react_config,
            system_prompt=full_system_prompt,
        )

        self.session_id: Optional[str] = None

    def run(self, question: str) -> str:
        """运行 Agent"""
        return self.engine.run(question)

    def step(self, question: str) -> str:
        """单步执行（手动控制模式）"""
        if not self.engine.messages:
            self.engine.reset(question)
        self.engine.step()
        return self._format_step_output()

    def chat(self, message: str) -> str:
        """多轮对话模式（保留上下文）"""
        if not self.engine.messages:
            self.engine.reset(message)
        else:
            self.engine.messages.append({"role": "user", "content": message})
        return self.engine.run(message)

    def reset(self):
        """重置 Agent 状态"""
        self.engine = None

    def get_stats(self) -> Dict:
        if self.engine:
            return self.engine.get_stats()
        return {}

    def _wrap_llm(self, provider: Callable) -> Callable:
        """包装 LLM 提供函数为引擎需要的签名"""
        def wrapper(prompt: str, messages: Optional[List[Dict]] = None) -> tuple:
            # 对于引擎内部调用，使用原始 provider
            return provider(prompt, messages)
        return wrapper

    def _build_tool_descriptions(self) -> str:
        if not self.tools:
            return "（当前没有可用工具）"
        lines = []
        for t in self.tools:
            name = t.get("name", "unknown")
            desc = t.get("description", "")
            params = t.get("parameters", {})
            lines.append(f"  - {name}: {desc}")
            if params:
                for pname, pinfo in params.get("properties", {}).items():
                    required = "（必填）" if pname in params.get("required", []) else "（可选）"
                    lines.append(f"      参数 {pname}: {pinfo.get('description', '')} {required}")
        return "\n".join(lines)

    def _default_system_prompt(self) -> str:
        return """你是一个 AI Agent，使用 ReAct 模式工作。

工作流程：
1. 思考 (Thought) — 分析问题，决定下一步
2. 动作 (Action) — 调用工具获取信息
3. 观察 (Observation) — 查看工具返回结果
4. 重复直到可以给出最终答案

可用工具:
{tool_descriptions}

格式要求：
- 如果需要工具：输出「动作: 工具名\n参数: {...}」
- 如果有答案：输出「最终答案: <你的回答>」
"""

    def _format_step_output(self) -> str:
        if not self.engine.steps:
            return "尚未开始"
        step = self.engine.steps[-1]
        lines = [f"[{step.type.value}]"]
        lines.append(f"  内容: {step.content[:200]}")
        if step.tool_name:
            lines.append(f"  工具: {step.tool_name}")
        if step.tool_result:
            lines.append(f"  结果: {step.tool_result[:200]}")
        return "\n".join(lines)
