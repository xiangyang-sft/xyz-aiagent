#!/usr/bin/env python3
"""translator skill 的真实工具实现（scripts/impl.py）—— 演示用词典式辅助"""
import json

# 极简演示词典（真实场景可对接翻译 API）
_DICT = {
    "hello": "你好",
    "world": "世界",
    "agent": "智能体",
    "skill": "技能",
    "的": "的",
}


def translate(text: str, target_lang: str = "zh") -> str:
    """翻译辅助：对已知词汇给出翻译，其余保留原文。

    参数:
      text: 要翻译的文本
      target_lang: 目标语言，如 zh/en/ja

    返回:
      逐词对照（演示用）
    """
    words = [w.strip().lower().strip(".,!? ") for w in text.split()]
    entries = []
    for w in words:
        if w in _DICT and target_lang == "zh":
            entries.append(f"{w} → {_DICT[w]}")
        else:
            entries.append(f"{w} → (保留, 请 LLM 组织译文)")
    return "\n".join(entries)
