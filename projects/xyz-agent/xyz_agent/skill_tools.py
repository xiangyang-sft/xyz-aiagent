#!/usr/bin/env python3
"""xyz_agent.skill_tools — Skill 按需加载工具（对齐 Hermes 的 skill_view 机制）

背景：
  当 agent 加载了大量 skill 时，把所有 skill 的完整 system prompt 塞进主上下文
  会撑爆 token。Hermes 的做法是「先列目录，LLM 点菜，再上菜」：
    - 主 system prompt 只注入所有 skill 的「名字 + 一句话描述」（目录）
    - 当 LLM 判断用户诉求命中某 skill 时，调用 skill_view(name) 主动加载详情

本模块提供两个 Function Calling 工具：
  - skill_list()     列出所有已加载 skill 的目录（名字 + 描述 + 标签）
  - skill_view(name) 加载并返回指定 skill 的完整内容（知识 + 工具声名）

通过 set_active_skill_manager() 把当前 Agent 的 SkillManager 挂进来，
使这些工具始终操作本 Agent 加载的 skill。
"""

import logging
from typing import Dict, List, Optional

from .tool import ToolRegistry, _default_registry

logger = logging.getLogger(__name__)

# 当前激活的 SkillManager（由 Agent 初始化时挂载）
_active_skill_manager = None


# ============================================================
# 当前 SkillManager 管理
# ============================================================

def set_active_skill_manager(skill_manager) -> None:
    """设置当前激活的 SkillManager（Agent 初始化时调用）"""
    global _active_skill_manager
    _active_skill_manager = skill_manager


def _get_manager():
    """获取当前激活的 SkillManager，未设置时回退到全局默认"""
    if _active_skill_manager is not None:
        return _active_skill_manager
    from .skill import get_default_skill_manager
    return get_default_skill_manager()


# ============================================================
# 工具实现
# ============================================================

def skill_list(max_items: int = 100) -> str:
    """列出所有已加载 skill 的目录。

    参数:
      max_items: 最多返回的 skill 条目数

    返回:
      每个 skill 一行：名字、标签、一句话描述。
      LLM 据此判断某个 skill 是否与用户问题相关，再用 skill_view 加载详情。
    """
    mgr = _get_manager()
    skills = mgr.list_skills() if mgr is not None else []
    if not skills:
        return "[当前没有已加载的 skill]"

    lines = [f"共 {len(skills)} 个已加载 skill:"]
    for s in skills[:max_items]:
        tags = f" [{', '.join(s.tags)}]" if s.tags else ""
        lines.append(f"  - {s.name}{tags}: {s.description}")
    return "\n".join(lines)


def skill_view(name: str) -> str:
    """加载并返回指定 skill 的完整内容。

    参数:
      name: skill 名称（必须先通过 skill_list 查看有哪些可用）

    返回:
      该 skill 的完整 system prompt（知识 + 使用说明），
      也可能包含其声明的工具清单。LLM 据此按该 skill 的流程完成用户任务。
    """
    mgr = _get_manager()
    if mgr is None:
        return "[错误: 未加载 SkillManager]"

    skill = mgr.get(name)
    if skill is None:
        available = ", ".join(s.name for s in mgr) if len(mgr) else "(无)"
        return f"[错误: 未找到 skill '{name}'。可用 skill: {available}]"

    parts = [f"--- {skill.name} skill (v{skill.version}) ---"]
    if skill.description:
        parts.append(f"描述: {skill.description}")
    if skill.tags:
        parts.append(f"标签: {', '.join(skill.tags)}")
    if skill.system_prompt:
        parts.append("")
        parts.append(skill.system_prompt)

    declared_tools = [str(t.get("name")) for t in skill.tools if t.get("name")]
    if declared_tools:
        parts.append("")
        parts.append(f"本 skill 声明的工具: {', '.join(declared_tools)}")

    return "\n".join(parts)


# ============================================================
# 注册
# ============================================================

def register_skill_tools(registry: Optional[ToolRegistry] = None) -> int:
    """将 skill 加载工具注册到指定注册表（默认全局）"""
    reg = registry if registry is not None else _default_registry
    count = 0
    for name, fn, desc in (
        ("skill_list", skill_list, "列出所有已加载 skill 的目录（名字+描述），用于发现可用能力"),
        ("skill_view", skill_view, "加载指定 skill 的完整内容，按需获取详细知识"),
    ):
        if name in reg:
            continue
        reg.register_fn(name=name, fn=fn, description=desc)
        count += 1
    logger.info(f"已注册 {count} 个 skill 加载工具")
    return count


# 模块导入即注册
register_skill_tools()
