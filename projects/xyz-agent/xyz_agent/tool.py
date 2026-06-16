#!/usr/bin/env python3
"""
xyz_agent.tool — 工具系统

提供统一的工具注册、验证、执行框架。

功能:
  - @tool 装饰器注册
  - 参数校验（类型、必填）
  - 自动生成 OpenAI Function Calling Schema
  - 错误处理与重试
  - MCP 集成接口（预留）
"""

import inspect
import json
from typing import (
    Any, Callable, Dict, List, Optional, Type, get_type_hints,
    get_origin, get_args, Union,
)
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps


# ============================================================
# 类型映射
# ============================================================

TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    Any: "string",
}


def _py_type_to_json_schema(py_type: Type) -> Dict:
    """将 Python 类型转换为 JSON Schema 类型描述"""
    origin = get_origin(py_type)
    if origin is Union:
        args = get_args(py_type)
        # 处理 Optional[X] -> [X, NoneType]
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            py_type = non_none[0]

    base = TYPE_MAP.get(py_type, "string")
    result = {"type": base}

    # 数组元素类型
    if base == "array":
        args = get_args(py_type)
        if args and args[0] in TYPE_MAP:
            result["items"] = {"type": TYPE_MAP[args[0]]}

    return result


# ============================================================
# 工具注册表
# ============================================================

@dataclass
class ToolDef:
    """工具定义"""
    name: str
    description: str
    fn: Callable
    parameters: Dict = field(default_factory=dict)
    required: List[str] = field(default_factory=list)
    schema: Optional[Dict] = None
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())


class ToolRegistry:
    """
    工具注册表 — 集中管理所有工具

    用法:
        registry = ToolRegistry()

        @registry.register
        def get_weather(city: str, unit: str = "celsius") -> str:
            \"\"\"查询城市天气\"\"\"
            return f"{city} 天气晴，25°{unit}"

        # 或手动注册
        registry.register_fn(name="calculator", fn=calc, description="计算器")
    """

    def __init__(self):
        self._tools: Dict[str, ToolDef] = {}

    # ---- 注册方式 ----

    def register(self, fn: Callable) -> Callable:
        """装饰器方式注册"""
        tool_def = self._build_tool_def(fn)
        self._tools[tool_def.name] = tool_def
        return fn

    def register_fn(
        self,
        name: str,
        fn: Callable,
        description: Optional[str] = None,
        parameters: Optional[Dict] = None,
    ) -> ToolDef:
        """手动注册工具"""
        if description is None:
            description = fn.__doc__ or ""
        tool_def = ToolDef(
            name=name,
            description=description.strip(),
            fn=fn,
            parameters=parameters or self._infer_params(fn),
            required=self._infer_required(fn),
        )
        tool_def.schema = self._build_openai_schema(tool_def)
        self._tools[name] = tool_def
        return tool_def

    def register_mcp(
        self,
        name: str,
        fn: Callable,
        schema: Dict,
    ) -> ToolDef:
        """注册 MCP 格式的工具"""
        tool_def = ToolDef(
            name=name,
            description=schema.get("description", ""),
            fn=fn,
            parameters=schema.get("inputSchema", schema.get("parameters", {})),
            required=list(schema.get("inputSchema", {})
                         .get("required", schema.get("required", []))),
            schema=schema,
        )
        self._tools[name] = tool_def
        return tool_def

    # ---- 执行 ----

    def execute(self, name: str, args: Dict[str, Any]) -> Any:
        """
        执行工具

        参数:
          name: 工具名称
          args: 参数 dict

        返回:
          执行结果（字符串化以便 LLM 消费）

        异常:
          KeyError: 工具不存在
          TypeError: 参数校验失败
          Exception: 执行异常
        """
        if name not in self._tools:
            raise KeyError(f"未知工具: {name}。可用工具: {list(self._tools.keys())}")

        tool = self._tools[name]

        # 参数校验
        for param_name in tool.required:
            if param_name not in args:
                raise TypeError(f"工具 '{name}' 缺少必填参数: {param_name}")

        # 执行
        try:
            result = tool.fn(**args)
            return str(result)
        except Exception as e:
            raise Exception(f"工具 '{name}' 执行失败: {str(e)}")

    def execute_safe(self, name: str, args: Dict[str, Any]) -> str:
        """安全执行工具（异常时返回错误信息）"""
        try:
            return self.execute(name, args)
        except Exception as e:
            return f"[工具错误] {str(e)}"

    # ---- 查询 ----

    def list_tools(self) -> List[Dict]:
        """获取所有工具的定义列表（用于 LLM 上下文）"""
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
                "required": t.required,
            }
            for t in self._tools.values()
        ]

    def get_openai_tools(self) -> List[Dict]:
        """获取 OpenAI Function Calling 格式的工具列表"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    def get_tool(self, name: str) -> Optional[ToolDef]:
        """获取单个工具定义"""
        return self._tools.get(name)

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    # ---- 内部方法 ----

    def _build_tool_def(self, fn: Callable) -> ToolDef:
        """从函数构建工具定义"""
        name = fn.__name__
        description = fn.__doc__ or ""
        return ToolDef(
            name=name,
            description=description.strip(),
            fn=fn,
            parameters=self._infer_params(fn),
            required=self._infer_required(fn),
        )

    def _infer_params(self, fn: Callable) -> Dict:
        """从函数签名推断参数 schema"""
        sig = inspect.signature(fn)
        hints = get_type_hints(fn)

        properties = {}
        for pname, param in sig.parameters.items():
            if pname == "self" or pname == "cls":
                continue
            py_type = hints.get(pname, str)
            prop = _py_type_to_json_schema(py_type)
            prop["description"] = f"参数 {pname}"
            properties[pname] = prop

        return {
            "type": "object",
            "properties": properties,
        }

    def _infer_required(self, fn: Callable) -> List[str]:
        """推断必需参数"""
        sig = inspect.signature(fn)
        return [
            p.name for p in sig.parameters.values()
            if p.default is inspect.Parameter.empty
            and p.name not in ("self", "cls")
        ]

    def _build_openai_schema(self, tool_def: ToolDef) -> Dict:
        """构建 OpenAI 格式的工具 schema"""
        return {
            "type": "function",
            "function": {
                "name": tool_def.name,
                "description": tool_def.description,
                "parameters": tool_def.parameters,
            },
        }


# ============================================================
# @tool 装饰器（快捷方式）
# ============================================================

_default_registry = ToolRegistry()


def tool(fn=None, *, registry: Optional[ToolRegistry] = None):
    """
    @tool 装饰器 — 快速注册工具到默认注册表

    用法:
        @tool
        def get_weather(city: str) -> str:
            \"\"\"查询天气\"\"\"
            ...

        @tool
        def add(a: int, b: int) -> int:
            \"\"\"加法计算\"\"\"
            return a + b

        # 获取注册的工具列表
        from xyz_agent.tool import get_all_tools
        tools = get_all_tools()
    """
    reg = registry or _default_registry

    if fn is not None:
        return reg.register(fn)

    def decorator(f):
        reg.register(f)
        return f

    return decorator


def get_all_tools() -> List[Dict]:
    """获取默认注册表中的所有工具"""
    return _default_registry.list_tools()


def get_openai_tool_defs() -> List[Dict]:
    """获取默认注册表的 OpenAI 格式工具定义"""
    return _default_registry.get_openai_tools()


def execute_tool(name: str, args: Dict) -> str:
    """执行默认注册表中的工具"""
    return _default_registry.execute_safe(name, args)
