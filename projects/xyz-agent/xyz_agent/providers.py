#!/usr/bin/env python3
"""
xyz_agent.providers — LLM Provider 封装

提供各种 LLM 后端的统一接口，支持：
  - OpenAI API（Function Calling 原生支持）
  - 模拟 LLM（用于测试）
  - 自定义 LLM（用户提供函数）
  - 流式输出
  - Token 计数

用法:
    provider = OpenAIProvider(api_key="...", model="gpt-4o")
    response, tokens = provider.chat(messages, tools=[...])
"""

import json
import time
import logging
import os
from typing import Callable, Dict, List, Optional, Any, Generator, Union
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============================================================
# LLM Provider 接口
# ============================================================

class LLMProvider:
    """LLM Provider 基类"""

    def __init__(self, model: str = "gpt-4o", **kwargs):
        self.model = model
        self.config = kwargs

    def chat(self, messages: List[Dict],
             tools: Optional[List[Dict]] = None,
             temperature: float = 0.7,
             max_tokens: Optional[int] = None,
             stream: bool = False) -> tuple:
        """
        聊天补全

        参数:
          messages: 消息列表 [{"role": "...", "content": "..."}]
          tools: OpenAI Function Calling 格式工具列表
          temperature: 采样温度
          max_tokens: 最大 tokens
          stream: 是否流式

        返回:
          (response_text, token_count, optional_tool_calls)
          response_text: LLM 返回文本
          token_count: 消耗的 tokens
          optional_tool_calls: Optional[List[Dict]] — Function Calling 调用
        """
        raise NotImplementedError

    def count_tokens(self, text: str) -> int:
        """估算 token 数量"""
        # 简单估算：英文 1 token/4 chars，中文 1 token/2 chars
        char_count = len(text)
        ascii_count = sum(1 for c in text if ord(c) < 128)
        cn_count = char_count - ascii_count
        return ascii_count // 4 + cn_count // 2 + 10


# ============================================================
# OpenAI Provider
# ============================================================

class OpenAIProvider(LLMProvider):
    """
    OpenAI API Provider

    支持 Function Calling 原生格式，LLM 输出直接解析为工具调用。

    用法:
        provider = OpenAIProvider(model="gpt-4o")
        text, tokens = provider.chat(
            messages=[{"role": "user", "content": "你好"}],
            tools=[{
                "type": "function",
                "function": {"name": "get_weather", ...}
            }]
        )
    """

    def __init__(self, api_key: Optional[str] = None,
                 model: str = "gpt-4o",
                 base_url: Optional[str] = None,
                 **kwargs):
        super().__init__(model=model, **kwargs)
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

        if not self.api_key:
            logger.warning("OPENAI_API_KEY 未设置。请通过环境变量或参数设置。")

    def chat(self, messages: List[Dict],
             tools: Optional[List[Dict]] = None,
             temperature: float = 0.7,
             max_tokens: Optional[int] = None,
             stream: bool = False) -> tuple:
        """调用 OpenAI Chat Completion API"""
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        if tools:
            body["tools"] = tools
        if max_tokens:
            body["max_tokens"] = max_tokens
        if stream:
            body["stream"] = True

        start = time.time()
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=body,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()

            choice = data["choices"][0]
            msg = choice.get("message", {})

            # 提取内容
            content = msg.get("content", "")

            # 提取工具调用
            tool_calls = None
            if "tool_calls" in msg:
                tool_calls = []
                for tc in msg["tool_calls"]:
                    fn_info = tc.get("function", {})
                    try:
                        arguments = json.loads(fn_info.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        arguments = {}
                    tool_calls.append({
                        "id": tc.get("id"),
                        "type": tc.get("type", "function"),
                        "function": {
                            "name": fn_info.get("name", ""),
                            "arguments": arguments,
                        },
                    })

            token_count = data.get("usage", {}).get("total_tokens", 0)
            duration = time.time() - start

            logger.debug(f"OpenAI API 调用完成: {token_count} tokens, {duration:.1f}s")

            return content, token_count, tool_calls

        except Exception as e:
            logger.error(f"OpenAI API 调用失败: {e}")
            raise


class OpenRouterProvider(OpenAIProvider):
    """
    OpenRouter Provider（兼容 OpenAI API）

    Usage:
        provider = OpenRouterProvider(api_key="sk-or-...")
    """

    def __init__(self, api_key: Optional[str] = None,
                 model: str = "openai/gpt-4o",
                 **kwargs):
        super().__init__(
            api_key=api_key or os.environ.get("OPENROUTER_API_KEY", ""),
            model=model,
            base_url="https://openrouter.ai/api/v1",
            **kwargs,
        )


# ============================================================
# Mock Provider（测试用）
# ============================================================

class MockProvider(LLMProvider):
    """
    模拟 LLM Provider（用于测试）

    支持预设响应和交互模式

    用法:
        provider = MockProvider(default_response="最终答案: 42")
        text, tokens = provider.chat(messages=[])
    """

    def __init__(self, default_response: str = "最终答案: 测试响应",
                 token_count: int = 100,
                 custom_responses: Optional[Dict[str, str]] = None,
                 interactive: bool = False,
                 **kwargs):
        super().__init__(model="mock", **kwargs)
        self.default_response = default_response
        self.token_count = token_count
        self.custom_responses = custom_responses or {}
        self.interactive = interactive
        self.call_history: List[Dict] = []

    def chat(self, messages: List[Dict],
             tools: Optional[List[Dict]] = None,
             temperature: float = 0.7,
             max_tokens: Optional[int] = None,
             stream: bool = False) -> tuple:
        self.call_history.append({
            "messages": messages,
            "tools": tools,
            "timestamp": time.time(),
        })

        # 检查是否有预设响应
        last_msg = messages[-1]["content"] if messages else ""
        for pattern, response in self.custom_responses.items():
            if pattern in last_msg:
                return response, self.token_count, None

        if self.interactive:
            # 交互模式：从命令行输入响应
            print(f"\n[LLM 模拟器] 收到消息 (最后一条: {last_msg[:50]}...)")
            user_input = input("[请输入 LLM 响应]: ").strip()
            return user_input, len(user_input), None

        return self.default_response, self.token_count, None


# ============================================================
# 构建 Tool Schema（从 ToolRegistry 转换为 OpenAI 格式）
# ============================================================

def build_tool_schemas(tools: List[Dict]) -> List[Dict]:
    """将框架工具列表转为 OpenAI Function Calling 格式"""
    schemas = []
    for t in tools:
        schema = {
            "type": "function",
            "function": {
                "name": t.get("name", "unknown"),
                "description": t.get("description", ""),
                "parameters": t.get("parameters", {
                    "type": "object",
                    "properties": {},
                }),
            },
        }
        schemas.append(schema)
    return schemas
