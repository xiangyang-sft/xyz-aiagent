#!/usr/bin/env python3
"""xyz_agent.engine — ReAct 循环引擎 (v2 生产版)

支持 ReAct 文本解析与 Function Calling 两种推理模式。
消息驱动、可中断可恢复的单步执行，零外部依赖。"""

import json
import re
import time
import logging
from typing import Callable, Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from .providers import StreamToolCall

logger = logging.getLogger(__name__)


# ============================================================
# 类型定义
# ============================================================

class ActionType(Enum):
    """ReAct 循环中的动作类型"""
    THINK = "think"          # 思考步骤
    TOOL = "tool"            # 工具调用
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
    max_tool_calls: int = 20
    verbose: bool = False
    mode: str = "auto"  # "react" | "function_calling" | "auto"
    tool_call_prefix: str = "动作"
    tool_args_prefix: str = "参数"
    think_prefix: str = "思考"
    answer_prefix: str = "最终答案"


# ============================================================
# 核心引擎
# ============================================================

class ReActEngine:
    """
    ReAct 循环引擎（v2）

    支持 Function Calling 原生格式的工具调用。

    用法:
        # 方式 1: 传统 ReAct（文本解析）
        engine = ReActEngine(llm_call=my_llm, tool_executor=my_executor)

        # 方式 2: Function Calling（原生格式）
        engine = ReActEngine(
            llm_call=my_llm_with_tools,  # 返回 (text, tokens, tool_calls)
            tools=tool_schemas,
            config=ReActConfig(mode="function_calling"),
        )

        result = engine.run("请问北京的天气")
    """

    def __init__(
        self,
        llm_call: Callable,
        tool_executor: Optional[Callable[[str, Dict], str]] = None,
        config: Optional[ReActConfig] = None,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        llm_stream: Optional[Callable] = None,
    ):
        """
        参数:
          llm_call:  LLM 调用函数
            支持两种签名:
              - 传统: (prompt, messages) -> (response, token_count)
              - FC:   (messages, tools, ...) -> (response, token_count, tool_calls)
          tool_executor: 工具执行器 (tool_name, args) -> result_str
          config: 运行配置
          system_prompt: 系统提示词
          tools: OpenAI Function Calling 格式的工具列表
          llm_stream: 流式 LLM 调用函数
            (messages, tools, ...) -> Generator[str]
            生成器逐 token 产出文本；当遇到 Function Calling 时抛出 StopIteration(tool_calls)
        """
        self.llm_call = llm_call
        self.tool_executor = tool_executor
        self.config = config or ReActConfig()
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.tools = tools or []
        self.llm_stream = llm_stream

        # 运行时状态
        self.messages: List[Dict] = []
        self.steps: List[Step] = []
        self.done = False
        self.final_answer: Optional[str] = None
        self.error: Optional[str] = None
        self.total_tokens = 0
        self.tool_call_count = 0
        self.retry_count = 0
        self._consecutive_think = 0
        self._mode = self._detect_mode()

    def _detect_mode(self) -> str:
        """自动检测模式"""
        if self.config.mode != "auto":
            return self.config.mode
        # 检查 llm_call 是否支持 Function Calling（通过 tools 参数）
        if self.tools:
            return "function_calling"
        return "react"

    # ============================================================
    # 运行
    # ============================================================

    def run(self, question: str) -> str:
        """
        运行完整 ReAct 循环直到产生最终答案。

        返回:
          最终答案字符串
        """
        # 🔧 注意：chat() 模式下外层已经 reset() 了，这里不再重复 reset
        # 只有第一次调用时才需要 reset
        if not self.messages or all(m.get("role") == "system" for m in self.messages):
            self.reset(question)

        step_count = 0
        while not self.done and step_count < self.config.max_steps:
            self.step()
            step_count += 1

        if not self.done and step_count >= self.config.max_steps:
            self.error = f"达到最大步骤数 ({self.config.max_steps})"
            self.done = True

        return self.final_answer or f"[错误: {self.error}]"

    def run_stream(self, question: str):
        """
        流式运行 ReAct 循环。

        逐 token 产出文本。在 Function Calling 模式下，每步的 LLM 输出实时流式，
        工具调用时同步执行并将结果输出。

        Yields:
            str — 文本片断（流式输出）
        """
        # reset 状态
        if not self.messages or all(m.get("role") == "system" for m in self.messages):
            self.reset(question)

        if not self.llm_stream:
            # 没配流式时，回退到非流式
            result = self.run(question)
            yield result
            return

        step_count = 0
        while not self.done and step_count < self.config.max_steps:
            step_count += 1
            start_time = time.time()
            tokens = 0
            collected_content = []

            try:
                # 流式调用 LLM
                gen = self.llm_stream(
                    self.messages,
                    tools=self.tools if self.tools else None,
                )

                for chunk in gen:
                    collected_content.append(chunk)
                    yield chunk

                # 生成器正常结束 => 无工具调用 => 最终答案
                response = "".join(collected_content)
                self.total_tokens += tokens
                if response:
                    self.messages.append({"role": "assistant", "content": response})
                self.done = True
                self.final_answer = response
                step = Step(
                    type=ActionType.ANSWER,
                    content=response,
                    duration=time.time() - start_time,
                    token_count=tokens,
                )
                self.steps.append(step)

            except StreamToolCall as si:
                # 生成器通过 StreamToolCall 携带 tool_calls
                tool_calls = si.tool_calls
                response = "".join(collected_content)
                self.total_tokens += tokens

                # 加入助手消息（含工具调用）
                if response or tool_calls:
                    assistant_msg = {"role": "assistant", "content": response or None}
                    if tool_calls:
                        assistant_msg["tool_calls"] = [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["function"]["name"],
                                    "arguments": json.dumps(tc["function"]["arguments"], ensure_ascii=False),
                                },
                            }
                            for tc in tool_calls
                        ]
                    self.messages.append(assistant_msg)

                # 执行工具
                if tool_calls:
                    for tc in tool_calls:
                        tool_name = tc["function"]["name"]
                        tool_args = tc["function"]["arguments"]
                        self.tool_call_count += 1

                        if self.tool_call_count > self.config.max_tool_calls:
                            msg = f"达到最大工具调用次数 ({self.config.max_tool_calls})"
                            self.error = msg
                            self.done = True
                            yield f"\n[⚠ {msg}]\n"
                            return

                        # 执行
                        if self.tool_executor:
                            try:
                                tool_result = self.tool_executor(tool_name, tool_args)
                            except Exception as e:
                                tool_result = f"[工具错误] {str(e)}"
                        else:
                            tool_result = "[未配置工具执行器]"

                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": tool_result,
                        })

                        # 输出工具调用信息
                        yield f"\n🔧 调用 {tool_name}({tool_args}) → {tool_result[:200]}\n"

                        step = Step(
                            type=ActionType.TOOL,
                            content=f"调用工具: {tool_name}",
                            tool_name=tool_name,
                            tool_args=tool_args,
                            tool_result=tool_result,
                            duration=time.time() - start_time,
                            token_count=tokens,
                        )
                        self.steps.append(step)

            except Exception as e:
                duration = time.time() - start_time
                error_step = Step(
                    type=ActionType.ERROR,
                    content=f"LLM 调用失败: {e}",
                    duration=duration,
                )
                self.steps.append(error_step)
                self.error = str(e)
                self.done = True
                yield f"\n[错误: {e}]\n"
                return

        if not self.done and step_count >= self.config.max_steps:
            self.error = f"达到最大步骤数 ({self.config.max_steps})"
            self.done = True
            yield f"\n[错误: {self.error}]\n"

    def reset(self, question: str):
        """重置引擎状态，准备新问题"""
        self.steps = []
        self.messages = []
        # 系统消息
        if self.system_prompt:
            self.messages.append({"role": "system", "content": self.system_prompt})
        # 用户问题
        self.messages.append({"role": "user", "content": question})
        self.done = False
        self.final_answer = None
        self.error = None
        self.total_tokens = 0
        self.tool_call_count = 0
        self.retry_count = 0
        self._consecutive_think = 0
    # ============================================================
    # 单步执行
    # ============================================================

    def step(self) -> Step:
        """
        执行单步 ReAct 循环。

        返回:
          当前步骤
        """
        if self.done:
            return Step(type=ActionType.ERROR, content="引擎已结束")

        if self._mode == "function_calling":
            return self._step_function_calling()
        else:
            return self._step_react()

    # ---- Function Calling 模式 ----

    def _step_function_calling(self) -> Step:
        """使用 Function Calling 原生格式执行单步"""
        start_time = time.time()

        try:
            # 调用 LLM（传入 tools）
            response, tokens, tool_calls = self.llm_call(
                self.messages,
                tools=self.tools if self.tools else None,
            )
        except Exception as e:
            duration = time.time() - start_time
            error_step = Step(
                type=ActionType.ERROR,
                content=f"LLM 调用失败: {e}",
                duration=duration,
            )
            self.steps.append(error_step)
            self.error = str(e)
            self.done = True
            return error_step

        self.total_tokens += tokens

        # 记录 LLM 响应（不含工具调用）
        if response:
            self.messages.append({"role": "assistant", "content": response})

        # 处理工具调用
        if tool_calls:
            # 将工具调用加入消息
            assistant_msg = {
                "role": "assistant",
                "content": response or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": json.dumps(tc["function"]["arguments"], ensure_ascii=False),
                        },
                    }
                    for tc in tool_calls
                ],
            }
            # 更新最后一条消息
            self.messages[-1] = assistant_msg

            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                tool_args = tc["function"]["arguments"]
                self.tool_call_count += 1

                # 检查限制
                if self.tool_call_count > self.config.max_tool_calls:
                    step = Step(
                        type=ActionType.ERROR,
                        content=f"达到最大工具调用次数 ({self.config.max_tool_calls})",
                        tool_name=tool_name,
                        tool_args=tool_args,
                        duration=time.time() - start_time,
                        token_count=tokens,
                    )
                    self.steps.append(step)
                    self.error = step.content
                    self.done = True
                    return step

                # 执行工具
                if self.tool_executor:
                    try:
                        tool_result = self.tool_executor(tool_name, tool_args)
                    except Exception as e:
                        tool_result = f"[工具错误] {str(e)}"
                else:
                    tool_result = "[未配置工具执行器]"

                # 工具结果加入消息
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result,
                })

                # 记录步骤
                step = Step(
                    type=ActionType.TOOL,
                    content=f"调用工具: {tool_name}",
                    tool_name=tool_name,
                    tool_args=tool_args,
                    tool_result=tool_result,
                    duration=time.time() - start_time,
                    token_count=tokens,
                )
                self.steps.append(step)

            # 返回最后一个工具调用步骤
            return self.steps[-1]

        # 无工具调用 = 最终答案
        self.done = True
        self.final_answer = response

        step = Step(
            type=ActionType.ANSWER,
            content=response,
            duration=time.time() - start_time,
            token_count=tokens,
        )
        self.steps.append(step)
        return step

    # ---- ReAct 文本解析模式 ----

    def _step_react(self) -> Step:
        """使用文本解析的传统 ReAct"""
        prompt = self._build_react_prompt()
        start_time = time.time()

        try:
            response, tokens = self.llm_call(prompt, self.messages)
        except Exception as e:
            duration = time.time() - start_time
            error_step = Step(
                type=ActionType.ERROR,
                content=f"LLM 调用失败: {e}",
                duration=duration,
            )
            self.steps.append(error_step)
            self.error = str(e)
            self.done = True
            return error_step

        duration = time.time() - start_time
        self.total_tokens += tokens

        # 解析响应
        step = self._parse_response(response, duration, tokens)
        self.steps.append(step)

        # 执行操作
        if step.type == ActionType.TOOL:
            self.tool_call_count += 1
            self._consecutive_think = 0
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
                        "content": f"观察结果: {tool_result}",
                    })
                except Exception as e:
                    step.tool_result = f"[工具错误] {str(e)}"
                    self.messages.append({
                        "role": "user",
                        "content": f"观察错误: {str(e)}",
                    })
            else:
                step.tool_result = "未配置工具执行器"
                self.messages.append({
                    "role": "user",
                    "content": "观察: 未配置工具执行器",
                })

        elif step.type == ActionType.ANSWER:
            self._consecutive_think = 0
            self.done = True
            self.final_answer = step.content
            self.messages.append({
                "role": "assistant",
                "content": f"最终答案: {step.content}",
            })

        elif step.type == ActionType.ERROR:
            self._consecutive_think = 0
            self.error = step.content
            self.done = True

        elif step.type == ActionType.THINK:
            self._consecutive_think += 1
            if self._consecutive_think >= 5:
                # 连续 5 次思考 → 强制给出答案
                self.done = True
                self.final_answer = step.content
                step.type = ActionType.ANSWER

        return step

    # ============================================================
    # 消息管理
    # ============================================================

    def add_user_message(self, content: str):
        """添加用户消息"""
        self.messages.append({"role": "user", "content": content})
        self.done = False  # 允许继续

    def add_system_message(self, content: str):
        """添加系统消息"""
        self.messages.append({"role": "system", "content": content})

    def get_messages(self) -> List[Dict]:
        """获取当前所有消息"""
        return self.messages

    def clear_messages(self):
        """清空消息（保留 system prompt）"""
        system_msgs = [m for m in self.messages if m.get("role") == "system"]
        self.messages = system_msgs
        self.steps = []
        self.done = False
        self.final_answer = None
        self.error = None

    # ============================================================
    # 提示词构建（ReAct 模式）
    # ============================================================

    def _build_react_prompt(self) -> str:
        """构建 ReAct 格式的提示词"""
        lines = [self.system_prompt]

        # 消息历史
        for msg in self.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                continue  # 已在开头
            if role == "user":
                lines.append(f"\n用户: {content[-500:]}")
            elif role == "assistant":
                lines.append(f"\n助手: {content[-500:]}")

        # 步骤历史
        if self.steps:
            lines.append("\n<最近步骤>")
            for s in self.steps[-5:]:
                lines.append(f"  [{s.type.value}]: {(s.content or '')[:100]}")
                if s.tool_result:
                    lines.append(f"  结果: {s.tool_result[:100]}")

        # 当前步骤提示
        lines.append(f"\n<当前步骤 ({len(self.steps) + 1}/{self.config.max_steps})>")
        lines.append("请使用以下格式之一响应：")
        lines.append(f"  1. 需要工具时：")
        lines.append(f"     {self.config.think_prefix}: <分析>")
        lines.append(f"     {self.config.tool_call_prefix}: 工具名")
        lines.append(f"     {self.config.tool_args_prefix}: {{json参数}}")
        lines.append(f"  2. 有答案时：")
        lines.append(f"     {self.config.answer_prefix}: <你的回答>")

        return "\n".join(lines)

    def _default_system_prompt(self) -> str:
        return """你是一个 AI Agent，通过调用工具来解决问题。

工作流程：
1. 分析问题，决定需要调用什么工具
2. 调用工具获取信息
3. 根据观察结果继续推理
4. 如果工具调用出错，尝试其他方法
5. 最终给出答案

格式要求：
- 工具调用：动作: 工具名\\n参数: {...}
- 最终答案：最终答案: <回答>
- 如果没有可用工具或不需要调用工具，直接给出最终答案"""

    # ============================================================
    # 响应解析（ReAct 模式）
    # ============================================================

    _tool_pattern = re.compile(
        r"(?:动作|工具|Action|Tool):\s*(\w[\w.-]*)\s*"
        r"\n?\s*(?:参数|Args|Arguments|args):\s*"
        r"(\{.*?\}|\[.*?\]|`[^`]+`)",
        re.DOTALL | re.IGNORECASE,
    )

    _answer_pattern = re.compile(
        r"(?:最终答案|答案|Final Answer|Answer|FINAL):\s*(.*?)$",
        re.DOTALL | re.IGNORECASE,
    )

    _think_pattern = re.compile(
        r"(?:思考|Thought|分析|让我|我需要|首先|好的)",
        re.IGNORECASE,
    )

    def _parse_response(self, response: str, duration: float, tokens: int) -> Step:
        """解析 LLM 响应为结构化步骤"""

        # 1. 检查是否是最终答案
        answer_match = self._answer_pattern.search(response)
        if answer_match:
            return Step(
                type=ActionType.ANSWER,
                content=answer_match.group(1).strip(),
                duration=duration,
                token_count=tokens,
            )

        # 2. 检查是否是工具调用
        tool_match = self._tool_pattern.search(response)
        if tool_match:
            tool_name = tool_match.group(1).strip()
            raw_args = tool_match.group(2)

            # 解析参数
            if raw_args.startswith("`") and raw_args.endswith("`"):
                raw_args = raw_args[1:-1]
            try:
                tool_args = json.loads(raw_args)
            except json.JSONDecodeError:
                tool_args = {"raw": raw_args}

            return Step(
                type=ActionType.TOOL,
                content=response,
                tool_name=tool_name,
                tool_args=tool_args,
                duration=duration,
                token_count=tokens,
            )

        # 3. 有明确思考关键词的，标记为思考
        #    同时检查是否包含工具调用关键词（如"调用""天气查询"等）
        if self._think_pattern.search(response):
            return Step(
                type=ActionType.THINK,
                content=response,
                duration=duration,
                token_count=tokens,
            )

        # 4. 默认作为最终答案
        #    兼容 DeepSeek 等不按严格格式输出的模型
        return Step(
            type=ActionType.ANSWER,
            content=response.strip(),
            duration=duration,
            token_count=tokens,
        )

    # ============================================================
    # 统计与追踪
    # ============================================================

    def get_stats(self) -> Dict:
        """获取运行统计"""
        return {
            "total_steps": len(self.steps),
            "tool_calls": self.tool_call_count,
            "total_tokens": self.total_tokens,
            "done": self.done,
            "has_answer": self.final_answer is not None,
            "has_error": self.error is not None,
            "duration": sum(s.duration for s in self.steps),
            "mode": self._mode,
        }

    def get_trace(self, detail: str = "summary") -> List[Dict]:
        """
        获取步骤追踪

        detail:
          "summary" — 简略追踪
          "full" — 完整追踪（含全部内容）
        """
        traces = []
        for i, s in enumerate(self.steps):
            entry = {
                "step": i + 1,
                "type": s.type.value,
                "tool": s.tool_name,
                "duration_ms": round(s.duration * 1000, 1),
                "tokens": s.token_count,
            }
            if detail == "full":
                entry["content"] = s.content[:500]
                entry["tool_args"] = s.tool_args
                entry["tool_result"] = (s.tool_result[:500] if s.tool_result else None)
            else:
                entry["content"] = (s.content or "")[:100]
                entry["tool_result"] = (s.tool_result[:100] if s.tool_result else None)
            traces.append(entry)
        return traces

    def export_conversation(self, format: str = "json") -> Union[str, List[Dict]]:
        """导出完整对话"""
        if format == "json":
            return json.dumps({
                "messages": self.messages,
                "steps": self.get_trace(detail="full"),
                "stats": self.get_stats(),
            }, ensure_ascii=False, indent=2)
        return self.get_trace(detail="full")
