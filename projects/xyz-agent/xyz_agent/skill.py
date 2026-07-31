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
        """将 skill 中的工具注册到注册表（对齐 Hermes：skill 引用全局真实能力）

        解析规则（按优先级）：
          1. 工具定义带真实 fn → 注册为 skill 真实工具
          2. 工具名在全局 ToolRegistry 已有同名内置工具（file/terminal）→ 直接复用全局真实能力
          3. 都没有 → 记录警告，不注册假占位工具（避免 LLM 误以为能力真实可用）
        """
        for tool_def in skill.tools:
            name = tool_def.get("name", f"{skill.name}_tool")
            description = tool_def.get("description", f"{skill.name} 提供的工具")

            # 规则 1：工具定义自带 fn → 注册为 skill 真实工具
            #   fn 可为可调用对象，或字符串路径（"module:function" / "scripts/xx.py:function"）
            fn = tool_def.get("fn")
            if fn:
                resolved_fn = self._resolve_tool_fn(skill, fn)
                if resolved_fn is None:
                    logger.warning(
                        f"Skill '{skill.name}' 工具 '{name}' 的 fn 无法解析: {fn}"
                    )
                    continue
                self._tool_registry.register_fn(
                    name=f"{skill.name}_{name}",
                    fn=resolved_fn,
                    description=description,
                    parameters=tool_def.get("parameters", {}),
                )
                continue

            # 规则 2：引用全局内置工具（file/terminal 等系统工具集）
            referenced = self._resolve_global_tool(name)
            if referenced is not None:
                # 复用全局真实函数，名称保持统一，方便 LLM 直接调用
                if referenced.name not in self._tool_registry:
                    self._tool_registry.register_fn(
                        name=referenced.name,
                        fn=referenced.fn,
                        description=description or referenced.description,
                        parameters=tool_def.get("parameters") or referenced.parameters,
                    )
                continue

            # 规则 3：既无真实实现也无全局能力 → 明确告警，不静默注册占位
            logger.warning(
                f"Skill '{skill.name}' 声明工具 '{name}' 但未提供 fn，"
                f"且全局注册表中无同名内置工具可用。该工具将无法执行。"
            )

    def _resolve_tool_fn(self, skill: SkillDef, fn) -> Optional[Callable]:
        """解析 skill 工具的真实实现函数

        fn 支持三种形式:
          1. 可调用对象 → 直接返回
          2. "module:function" → 从已安装模块导入（如 "xyz_agent.system_tools:read_file"）
          3. "scripts/xxx.py:function" → 从 skill 目录下的脚本文件加载
        """
        # 可调用对象
        if callable(fn):
            return fn

        if not isinstance(fn, str):
            return None

        # "scripts/xxx.py:func" 相对 skill 目录（source_path = 该 skill 的 SKILL.md）
        if fn.startswith("scripts/") and skill.source_path:
            script_rel, _, func_name = fn.partition(":")
            skill_dir = os.path.dirname(skill.source_path)
            return self._load_fn_from_file(os.path.join(skill_dir, script_rel), func_name)

        # "module:func"
        if ":" in fn:
            module_name, _, func_name = fn.partition(":")
            try:
                mod = __import__(module_name, fromlist=[func_name])
                return getattr(mod, func_name, None)
            except (ImportError, AttributeError):
                return None

        return None

    @staticmethod
    def _load_fn_from_file(filepath: str, func_name: str) -> Optional[Callable]:
        """从 Python 脚本文件加载指定函数"""
        if not os.path.isfile(filepath):
            return None
        try:
            import importlib.util
            mod_name = f"_skill_mod_{os.path.basename(filepath)}_{func_name}"
            spec = importlib.util.spec_from_file_location(mod_name, filepath)
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            import sys as _sys
            _sys.modules[mod_name] = module
            spec.loader.exec_module(module)
            return getattr(module, func_name, None)
        except Exception:
            return None

    def _resolve_global_tool(self, name: str):
        """在全局工具注册表中查找与 skill 声明同名的内置工具

        回溯顺序:
          1. 当前 SkillManager 关联的注册表
          2. 全局默认注册表 _default_registry（内置 file/terminal 工具所在）
        如果命中，说明 skill 是引用系统能力而非独立实现。
        """
        # 本地注册表精确匹配
        local = self._tool_registry.get_tool(name)
        if local is not None:
            return local

        # 回溯到全局默认注册表（内置系统工具）
        global_tool = None
        try:
            from .tool import _default_registry
            global_tool = _default_registry.get_tool(name)
        except Exception:
            global_tool = None
        if global_tool is not None:
            return global_tool

        # 去前缀匹配（file_/terminal_/system_ → 裸名）
        for prefix in ("file_", "terminal_", "system_"):
            if name.startswith(prefix):
                bare = name[len(prefix):]
                match = self._tool_registry.get_tool(bare)
                if match is None:
                    try:
                        from .tool import _default_registry
                        match = _default_registry.get_tool(bare)
                    except Exception:
                        match = None
                if match is not None:
                    return match

        return None


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
