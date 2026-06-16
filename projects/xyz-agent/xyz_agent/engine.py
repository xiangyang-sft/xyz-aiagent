#!/usr/bin/env python3
"""
xyz_agent.engine — ReAct 循环引擎（最小可用版本）

核心思想：
  思考 (Thought) → 行动 (Action) → 观察 (Observation)
  重复直到输出最终答案。

设计原则：
  - 无外部依赖（仅 Python 标准库 + 用户提供的 LLM 调用函数）
  - 纯函数式核心，易于测试
  - 可中断、可恢复（通过 step() 单步执行）
"""

import json
import re
import time
from typing import Callable, Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum


# ============================================================
# 类型定义
# ============================================================

class ActionType(Enum):
    """ReAct 循环中的动作类型"""
    THINK = "think"          # 思考步骤
    TOOL = "tool"            # 工具调用
    OBSERVE = "observe"      # 工具观察
    ANSWER = "answer"        # 最终答案
    ERROR = "error"          # 错误状态


@dataclass
class Step:
    """ReAct 循环中的单个步骤"""
    type: ActionType
    content: str
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_result: Optional[str] = None
    duration: float = 0.0
    token_count: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class ReActConfig:
    """ReAct 引擎配置"""
    max_steps: int = 15
    max_tool_calls: int = 10
    timeout_per_step: float = 30.0
    stop_tokens: List[str] = field(default_factory=lambda: ["<|end|>", "FINAL ANSWER:"])
    verbose: bool = False


# ============================================================
# 核心引擎
# ============================================================

class ReActEngine:
    """
    ReAct 循环引擎

    用法:
        engine = ReActEngine(llm_call, tool_executor, config)
        result = engine.run("请帮我查询北京的天气")

    也可以单步执行:
        engine = ReActEngine(llm_call, tool_executor)
        engine.reset(question)
        while not engine.done:
            step = engine.step()
    """

    def __init__(
        self,
        llm_call: Callable[[str, Optional[List[Dict]]], Tuple[str, int]],
        tool_executor: Optional[Callable[[str, Dict], str]] = None,
        config: Optional[ReActConfig] = None,
        system_prompt: Optional[str] = None,
    ):
        """
        参数:
          llm_call:    LLM 调用函数 sign=(prompt, [messages]) -> (response, token_count)
          tool_executor: 工具执行函数 sign=(tool_name, args) -> result_str
          config:      运行配置
          system_prompt: 自定义系统提示词
        """
        self.llm_call = llm_call
        self.tool_executor = tool_executor
        self.config = config or ReActConfig()
        self.system_prompt = system_prompt or self._default_system_prompt()

        # 运行时状态
        self.steps: List[Step] = []
        self.messages: List[Dict] = []
        self.done = False
        self.final_answer: Optional[str] = None
        self.error: Optional[str] = None
        self.total_tokens = 0
        self.tool_call_count = 0

    def reset(self, question: str):
        """重置引擎状态，准备新问题"""
        self.steps = []
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self.messages.append({"role": "user", "content": question})
        self.done = False
        self.final_answer = None
        self.error = None
        self.total_tokens = 0
        self.tool_call_count = 0

    def run(self, question: str) -> str:
        """
        运行完整 ReAct 循环直到产生最终答案。

        返回:
          最终答案字符串
        """
        self.reset(question)

        step_count = 0
        while not self.done and step_count < self.config.max_steps:
            self.step()
            step_count += 1

        if not self.done and step_count >= self.config.max_steps:
            self.error = f"达到最大步骤数 ({self.config.max_steps})"

        return self.final_answer or f"[错误: {self.error}]"

    def step(self) -> Step:
        """
        执行单步 ReAct 循环。

        返回:
          当前步骤
        """
        # 1. 构建提示词（包含之前的对话和工具调用记录）
        prompt = self._build_react_prompt()

        # 2. 调用 LLM
        start_time = time.time()
        response, tokens = self.llm_call(prompt, self.messages)
        duration = time.time() - start_time
        self.total_tokens += tokens

        # 3. 解析响应
        step = self._parse_response(response, duration, tokens)
        self.steps.append(step)

        # 4. 根据步骤类型执行
        if step.type == ActionType.TOOL:
            self.tool_call_count += 1
            if self.tool_call_count > self.config.max_tool_calls:
                step.type = ActionType.ERROR
                step.content = f"达到最大工具调用次数 ({self.config.max_tool_calls})"
                self.error = step.content
                return step

            if self.tool_executor and step.tool_name:
                try:
                    tool_result = self.tool_executor(step.tool_name, step.tool_args or {})
                    step.tool_result = tool_result
                    self.messages.append({
                        "role": "user",
                        "content": f"观察: {tool_result}"
                    })
                except Exception as e:
                    step.tool_result = f"工具执行错误: {str(e)}"
                    self.messages.append({
                        "role": "user",
                        "content": f"观察错误: {str(e)}"
                    })
            else:
                step.tool_result = "未配置工具执行器"
                self.messages.append({
                    "role": "user",
                    "content": f"观察: 未配置工具执行器"
                })

        elif step.type == ActionType.ANSWER:
            self.done = True
            self.final_answer = step.content
            # 将最终答案加入消息
            self.messages.append({
                "role": "assistant",
                "content": f"最终答案: {step.content}"
            })

        elif step.type == ActionType.ERROR:
            self.error = step.content
            self.done = True

        return step

    def _build_react_prompt(self) -> str:
        """构建 ReAct 格式的提示词"""
        lines = [self.system_prompt]
        lines.append(f"\n<问题>\n{self.messages[-1]['content'] if self.messages[-1]['role'] == 'user' else ''}")

        if self.steps:
            lines.append("\n<历史步骤>")
            for i, s in enumerate(self.steps):
                lines.append(f"  步骤 {i+1} [{s.type.value}]: {s.content[:100]}")
                if s.tool_result:
                    lines.append(f"  结果: {s.tool_result[:100]}")

        lines.append(f"\n<当前步骤 ({len(self.steps) + 1}/{self.config.max_steps})>")
        lines.append("请使用以下格式响应：")
        lines.append("  思考: <你的推理过程>")
        lines.append("  动作: 工具名\n  参数: {\"key\": \"value\"}")
        lines.append("  或")
        lines.append("  最终答案: <你的回答>")

        return "\n".join(lines)

    def _parse_response(self, response: str, duration: float, tokens: int) -> Step:
        """解析 LLM 响应为结构化步骤"""

        # 检查是否是最终答案
        if "最终答案:" in response or "<|end|>" in response:
            content = response.replace("<|end|>", "").replace("最终答案:", "").strip()
            return Step(
                type=ActionType.ANSWER,
                content=content,
                duration=duration,
                token_count=tokens,
            )

        # 检查是否是工具调用
        tool_match = re.search(
            r"动作:\s*(\w[\w.-]*)\s*\n?\s*参数:\s*(\{.*?\}|\[.*?\])",
            response,
            re.DOTALL,
        )
        if tool_match:
            tool_name = tool_match.group(1).strip()
            try:
                tool_args = json.loads(tool_match.group(2))
            except json.JSONDecodeError:
                tool_args = {"raw": tool_match.group(2)}
            return Step(
                type=ActionType.TOOL,
                content=response,
                tool_name=tool_name,
                tool_args=tool_args,
                duration=duration,
                token_count=tokens,
            )

        # 默认作为思考步骤
        return Step(
            type=ActionType.THINK,
            content=response,
            duration=duration,
            token_count=tokens,
        )

    def _default_system_prompt(self) -> str:
        return """你是一个 AI Agent，使用 ReAct 模式工作。

工作流程：
1. 思考 (Thought) — 分析问题，决定下一步
2. 动作 (Action) — 调用工具获取信息
3. 观察 (Observation) — 查看工具返回结果
4. 重复直到可以给出最终答案

工具可用:
{tool_descriptions}

格式要求：
- 如果需要工具：输出「动作: 工具名\n参数: {...}」
- 如果有答案：输出「最终答案: <你的回答>」
"""

    def get_stats(self) -> Dict:
        """获取运行统计信息"""
        return {
            "total_steps": len(self.steps),
            "tool_calls": self.tool_call_count,
            "total_tokens": self.total_tokens,
            "done": self.done,
            "has_answer": self.final_answer is not None,
            "has_error": self.error is not None,
            "duration": sum(s.duration for s in self.steps),
        }

    def get_trace(self) -> List[Dict]:
        """获取步骤追踪（用于调试/监控）"""
        return [
            {
                "step": i,
                "type": s.type.value,
                "content": s.content[:200],
                "tool": s.tool_name,
                "tool_result": (s.tool_result[:200] if s.tool_result else None),
                "duration_ms": round(s.duration * 1000, 1),
                "tokens": s.token_count,
            }
            for i, s in enumerate(self.steps)
        ]
