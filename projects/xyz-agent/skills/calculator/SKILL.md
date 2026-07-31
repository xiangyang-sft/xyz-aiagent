---
name: calculator
description: "数学计算 Skill — 当用户要求做算术运算（加减乘除、幂、百分比、科学计算、表达式求值）时激活。支持复杂表达式与单位换算。遵循计算精度安全提示。"
version: 1.0.0
author: xyz-agent
license: MIT
metadata:
  hermes:
    tags: [math, calculation, utility]
    related_skills: []
---

# Calculator Skill

提供可靠的数学计算能力。

## 使用场景
- 用户给出算术表达式求值（如 "23 * 45 + 67"）
- 百分比 / 幂 / 平方根等数学运算
- 需要精确结果的计算任务

## 提供的工具

本 skill 自带真实实现（scripts/impl.py）：

```json
[
  {
    "name": "calc",
    "description": "安全地计算一个数学表达式并返回结果",
    "fn": "scripts/impl.py:calc",
    "parameters": {
      "type": "object",
      "properties": {
        "expression": {
          "type": "string",
          "description": "要计算的数学表达式，如 '23 * 45 + 67'"
        }
      },
      "required": ["expression"]
    }
  }
]
```

## 使用示例

当用户问 "23 * 45 + 67 等于多少" 时，
先用 calc 工具计算表达式，再把结果告诉用户。
