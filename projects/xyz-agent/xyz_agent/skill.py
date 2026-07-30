#!/usr/bin/env python3
"""
xyz_agent.skill — Skill 能力系统

Skill = 可复用的能力单元（Prompt + Tools + Workflow）。

功能：
  - 从本地目录加载 SKILL.md 格式的 skill
  - Hermes Agent SKILL.md 兼容（YAML frontmatter + markdown body）
  - 自动解析 skill 中的工具定义
  - Skill 注册到 ToolRegistry
  - 支持目录热扫描
  - System prompt 自动注入

设计原则：
  - Skill 是「知识 + 工具」的封装，不是独立 Agent
  - 一个 Skill 可以注册多个工具
  - Skill 的 system prompt 自动合入 Agent 的 system prompt
"""

import os
import re
import json
import yaml
import glob
import time
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .tool import ToolRegistry, ToolDef

logger = logging.getLogger(__name__)


# ============================================================
# Skill 定义
# ============================================================

@dataclass
class SkillDef:
    """Skill 定义"""
    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    license: str = "MIT"
    tags: List[str] = field(default_factory=list)
    related_skills: List[str] = field(default_factory=list)
    system_prompt: str = ""
    tools: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    source_path: Optional[str] = None
    loaded_at: float = field(default_factory=time.time)


class SkillManager:
    """
    Skill 管理器

    用法:
        mgr = SkillManager()
        mgr.load_directory("~/.hermes/skills/")
        skill = mgr.get("my-skill")
        prompts = mgr.get_system_prompts()  # 所有 skill 的 system prompt
    """

    def __init__(self, tool_registry: Optional[ToolRegistry] = None):
        self._skills: Dict[str, SkillDef] = {}
        self._tool_registry = tool_registry if tool_registry is not None else ToolRegistry()
        self._watch_dirs: List[str] = []

    # ---- 加载 ----

    def load_directory(self, directory: str, recursive: bool = True) -> int:
        """
        从目录加载所有 SKILL.md 文件

        目录结构:
          skills/
            ├── my-skill/
            │   ├── SKILL.md          # 主文件（必需）
            │   ├── references/       # 引用文件（可选）
            │   │   └── api.md
            │   ├── templates/        # 模板（可选）
            │   │   └── prompt.j2
            │   └── scripts/          # 脚本（可选）
            │       └── validate.py
            └── another-skill/
                └── SKILL.md

        返回: 成功加载的 skill 数量
        """
        directory = os.path.expanduser(directory)
        if not os.path.isdir(directory):
            logger.warning(f"Skill 目录不存在: {directory}")
            return 0

        if recursive:
            pattern = os.path.join(directory, "**", "SKILL.md")
        else:
            pattern = os.path.join(directory, "SKILL.md")

        files = glob.glob(pattern, recursive=True)
        count = 0
        for filepath in files:
            try:
                skill = self._load_skill_file(filepath)
                if skill:
                    self._skills[skill.name] = skill
                    self._register_skill_tools(skill)
                    count += 1
            except Exception as e:
                logger.error(f"加载 skill 失败 {filepath}: {e}")

        self._watch_dirs.append(directory)
        return count

    def load_skill(
        self, name: str, content: str,
        source_path: Optional[str] = None,
    ) -> SkillDef:
        """从字符串内容加载 skill（用于内存中创建）"""
        skill = self._parse_skill_content(content, source_path)
        skill.name = name
        self._skills[name] = skill
        self._register_skill_tools(skill)
        return skill

    # ---- 查询 ----

    def list_skills(self) -> List[SkillDef]:
        """列出所有 Skill"""
        return list(self._skills.values())

    def get(self, name: str) -> Optional[SkillDef]:
        """获取指定 Skill"""
        return self._skills.get(name)

    def has(self, name: str) -> bool:
        return name in self._skills

    def __contains__(self, name: str) -> bool:
        return name in self._skills

    def __len__(self) -> int:
        return len(self._skills)

    def __iter__(self):
        return iter(self._skills.values())

    def get_system_prompts(self, skill_names: Optional[List[str]] = None) -> List[str]:
        """
        获取指定（或所有）skill 的 system prompt 列表

        这些提示会自动合入 Agent 的 system prompt。
        """
        prompts = []
        skills = (
            [self._skills[n] for n in skill_names if n in self._skills]
            if skill_names
            else self._skills.values()
        )
        for skill in skills:
            if skill.system_prompt:
                prompts.append(
                    f"--- {skill.name} skill ---\n{skill.system_prompt}"
                )
        return prompts

    def get_tool_registry(self) -> ToolRegistry:
        """获取关联的工具注册表"""
        return self._tool_registry

    # ---- 刷新 ----

    def refresh(self) -> int:
        """重新扫描所有已加载的目录，返回新增/更新的 skill 数"""
        count = 0
        for directory in self._watch_dirs:
            count += self.load_directory(directory)
        return count

    # ---- 内部 ----

    def _load_skill_file(self, filepath: str) -> Optional[SkillDef]:
        """从 SKILL.md 文件加载"""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return self._parse_skill_content(content, filepath)

    def _parse_skill_content(self, content: str, source_path: Optional[str] = None) -> SkillDef:
        """解析 SKILL.md 内容"""
        # 分割 frontmatter 和 body
        fm_end = None
        if content.startswith("---"):
            # 找到 closing ---
            second = content.find("---", 3)
            if second > 3 and second < 5000:
                fm_end = second + 3

        frontmatter = {}
        body = content

        if fm_end:
            fm_text = content[3:fm_end - 3].strip()
            body = content[fm_end:].strip()
            try:
                frontmatter = yaml.safe_load(fm_text) or {}
            except yaml.YAMLError as e:
                logger.warning(f"SKILL.md frontmatter 解析失败: {e}")

        name = frontmatter.get("name", "")
        if not name and source_path:
            # 从路径推断名称
            name = os.path.basename(os.path.dirname(source_path))

        # 从 body 中提取工具定义（如果有）
        tools = self._extract_tools_from_body(body)
        if frontmatter.get("tools"):
            tools.extend(frontmatter["tools"])

        metadata = frontmatter.get("metadata", {})
        hermes_meta = metadata.get("hermes", {})

        return SkillDef(
            name=name,
            description=frontmatter.get("description", ""),
            version=frontmatter.get("version", "1.0.0"),
            author=frontmatter.get("author", ""),
            license=frontmatter.get("license", "MIT"),
            tags=hermes_meta.get("tags", []),
            related_skills=hermes_meta.get("related_skills", []),
            system_prompt=body,
            tools=tools,
            metadata=frontmatter.get("metadata", {}),
            source_path=source_path,
        )

    def _extract_tools_from_body(self, body: str) -> List[Dict]:
        """从 markdown body 中提取工具定义"""
        # 解析代码块中的工具定义
        tools = []

        # 查找 JSON/YAML 格式的工具定义代码块
        json_pattern = r"```(?:json|yaml)\s*\n(.*?)\n```"
        for match in re.finditer(json_pattern, body, re.DOTALL):
            try:
                data = json.loads(match.group(1))
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "name" in item:
                            tools.append(item)
                elif isinstance(data, dict) and "name" in data:
                    tools.append(data)
            except (json.JSONDecodeError, yaml.YAMLError):
                pass

        return tools

    def _register_skill_tools(self, skill: SkillDef):
        """将 skill 中的工具注册到注册表"""
        for tool_def in skill.tools:
            name = tool_def.get("name", f"{skill.name}_tool")
            description = tool_def.get("description", f"{skill.name} 提供的工具")

            # 如果有 fn，注册为真实工具
            fn = tool_def.get("fn")
            if fn:
                self._tool_registry.register_fn(
                    name=f"{skill.name}:{name}",
                    fn=fn,
                    description=description,
                    parameters=tool_def.get("parameters", {}),
                )
                continue

            # 否则注册为 "描述性" 工具（LLM 会知道它，但由 Skill 的实现处理）
            self._tool_registry.register_fn(
                name=f"{skill.name}:{name}",
                fn=lambda **kwargs: f"[Skill '{skill.name}' 工具 '{name}' 执行，参数: {kwargs}]",
                description=description,
                parameters=tool_def.get("parameters", {}),
            )


# ============================================================
# 快捷函数
# ============================================================

_default_skill_manager = None


def get_default_skill_manager() -> SkillManager:
    """获取默认 Skill 管理器"""
    global _default_skill_manager
    if _default_skill_manager is None:
        from .tool import _default_registry
        _default_skill_manager = SkillManager(tool_registry=_default_registry)
    return _default_skill_manager


def load_skills(directory: Optional[str] = None) -> int:
    """快捷加载 skill"""
    mgr = get_default_skill_manager()
    if directory:
        return mgr.load_directory(directory)
    # 尝试加载默认位置
    count = 0
    for d in [
        "~/.hermes/skills/",
        "./skills/",
        "./xyz-agent/skills/",
    ]:
        count += mgr.load_directory(d)
    return count


def list_skills() -> List[Dict]:
    """列出所有已加载的 skill"""
    mgr = get_default_skill_manager()
    return [
        {
            "name": s.name,
            "description": s.description,
            "version": s.version,
            "tags": s.tags,
            "tools_count": len(s.tools),
        }
        for s in mgr
    ]
