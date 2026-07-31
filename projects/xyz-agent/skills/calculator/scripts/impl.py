#!/usr/bin/env python3
"""calculator skill 的真实工具实现（scripts/impl.py）"""
import ast
import operator
import math


_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node):
    """安全地递归求值 AST，只允许算术节点"""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("仅支持数字常量")
    if isinstance(node, ast.BinOp):
        op = _ALLOWED_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"不支持的运算符: {type(node.op).__name__}")
        return op(_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        op = _ALLOWED_OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"不支持的运算符: {type(node.op).__name__}")
        return op(_safe_eval(node.operand))
    raise ValueError(f"不支持的表达式节点: {type(node).__name__}")


def calc(expression: str) -> str:
    """安全地计算一个数学表达式并返回结果。

    参数:
      expression: 数学表达式字符串（仅支持基本算术运算）

    返回:
      计算结果
    """
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _safe_eval(tree)
        # 结果若是整数值则转 int 展示更友好
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return f"{expression.strip()} = {result}"
    except Exception as e:
        return f"[计算错误] {e}。仅支持 + - * / % ** // ( ) 和数字。"
