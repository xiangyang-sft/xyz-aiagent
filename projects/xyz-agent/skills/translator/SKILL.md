---
name: translator
description: "翻译 Skill — 当用户要求翻译文本（中英或其他语言互译）、解释某段英文含义、润色或改写句子时激活。支持中英互译与多语言。"
version: 1.0.0
author: xyz-agent
license: MIT
metadata:
  hermes:
    tags: [translation, language, utility]
    related_skills: []
---

# Translator Skill

提供文本翻译能力。

## 使用场景
- 中英互译
- 其它语言翻译
- 解释外文段落含义

## 提供的工具

本 skill 自带真实实现（scripts/impl.py），提供词级翻译辅助：

```json
[
  {
    "name": "translate",
    "description": "进行文本翻译（当前为词典式辅助，最终由 LLM 组织自然译文）",
    "fn": "scripts/impl.py:translate",
    "parameters": {
      "type": "object",
      "properties": {
        "text": { "type": "string", "description": "要翻译的文本" },
        "target_lang": { "type": "string", "description": "目标语言，如 zh/en/ja", "default": "zh" }
      },
      "required": ["text"]
    }
  }
]
```

## 使用示例

当用户要求翻译时，先调用 translate 获取辅助，再由 LLM 给出通顺译文。
