#!/usr/bin/env python3
"""xyz_agent.system_tools — 内置系统工具集（Toolset）

参考 Hermes Agent 的 file / terminal toolsets 设计：
  内置了 Agent 无需依赖任何 Skill 即可使用的通用真实能力，
  Skill 通过「引用」这些全局工具来完成任务（而不是各自声明假的占位工具）。

功能：
  - 文件读取 / 写入 / 追加
  - 目录浏览（列出目录内容）
  - 命令执行（带超时与安全约束）
  - 支持按 Toolset 分组（file / terminal / shell）
  - 注册到默认 ToolRegistry，Agent 自动构建 Function Calling Schema

设计原则（对齐 Hermes）：
  - 系统工具是一等公民，独立于 Skill
  - Skill 只用 Prompt 指导 LLM「怎么用」这些工具
  - 命令执行默认 shell=False（防注入），仅白名单命令走 shell=True
"""

import os
import glob
import logging
import subprocess
from typing import Any, Dict, List, Optional

from .tool import ToolRegistry, _default_registry

logger = logging.getLogger(__name__)

# ============================================================
# 安全配置
# ============================================================

# 命令执行超时（秒）
DEFAULT_TIMEOUT = 30

# 允许走 shell=True 的白名单命令（显式沙箱外执行）
# 其它命令一律 shell=False，以列表参数方式执行，避免 shell 注入
SHELL_ALLOWLIST = {
    "git",
    "python",
    "python3",
    "pip",
    "pip3",
    "ls",
    "cat",
    "echo",
    "mkdir",
    "touch",
}

# 默认禁止读取/写入的敏感路径
BLOCKED_PATHS = (
    "/etc/shadow",
    "/etc/passwd",
    "/root/.ssh",
    "/root/.aws",
    "/root/.hermes",
)

# 目录浏览返回的最大条目数
MAX_LIST_ITEMS = 200


# ============================================================
# 路径安全检查
# ============================================================

def _resolve_path(path: str) -> str:
    """展开 ~ 并转为绝对路径"""
    return os.path.abspath(os.path.expanduser(path))


def _check_safe_path(path: str) -> str:
    """检查并返回安全路径，禁止访问敏感位置"""
    resolved = _resolve_path(path)
    for blocked in BLOCKED_PATHS:
        if resolved.startswith(blocked):
            raise PermissionError(f"禁止访问敏感路径: {blocked}")
    return resolved


# ============================================================
# 文件工具
# ============================================================

def read_file(path: str, max_chars: int = 100000) -> str:
    """读取一个文本文件的内容。

    参数:
      path: 文件绝对路径或相对路径
      max_chars: 最多返回的字符数（避免输出过大撑爆上下文）

    返回:
      文件内容（UTF-8 编码）
    """
    resolved = _check_safe_path(path)
    if not os.path.isfile(resolved):
        raise FileNotFoundError(f"文件不存在: {resolved}")
    with open(resolved, "r", encoding="utf-8") as f:
        content = f.read()
    if len(content) > max_chars:
        return content[:max_chars] + f"\n\n... [已截断, 共 {len(content)} 字符]"
    return content


def write_file(path: str, content: str, mode: str = "overwrite") -> str:
    """写入或追加内容到文本文件。

    参数:
      path: 文件路径
      content: 要写入的内容
      mode: overwrite=覆盖 | append=追加

    返回:
      执行结果描述
    """
    resolved = _check_safe_path(path)
    file_mode = "a" if mode == "append" else "w"
    with open(resolved, file_mode, encoding="utf-8") as f:
        f.write(content)
    action = "追加到" if mode == "append" else "写入"
    return f"已{action} {resolved}（{len(content)} 字符）"


def list_dir(path: str = ".", recursive: bool = False) -> str:
    """列出目录中的内容。

    参数:
      path: 目录路径（默认当前目录）
      recursive: 是否递归列出（慎用，可能输出很多）

    返回:
      条目列表，每行一个（文件/目录/链接）
    """
    resolved = _check_safe_path(path)
    if not os.path.isdir(resolved):
        raise NotADirectoryError(f"目录不存在: {resolved}")

    if recursive:
        pattern = os.path.join(resolved, "**", "*")
        items = glob.glob(pattern, recursive=True)
    else:
        items = sorted(os.listdir(resolved))

    lines = []
    for i, item in enumerate(items):
        if i >= MAX_LIST_ITEMS:
            lines.append(f"... [已截断, 仅显示前 {MAX_LIST_ITEMS} 项]")
            break
        if recursive:
            full = item
        else:
            full = os.path.join(resolved, item)
        kind = "📁" if os.path.isdir(full) else ("🔗" if os.path.islink(full) else "📄")
        lines.append(f"{kind} {item}")
    return "\n".join(lines)


# ============================================================
# 命令工具
# ============================================================

def run_command(command: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """在 shell 中执行一条命令并返回输出。

    参数:
      command: 要执行的命令（字符串）
      timeout: 超时秒数（默认 30）

    返回:
      命令的 stdout + stderr 合并输出

    安全说明:
      - 默认以 shell=False 方式执行，避免注入
      - 白名单命令（git/python/pip/ls/cat 等）允许 shell=True
    """
    use_shell = _should_use_shell(command)
    try:
        if use_shell:
            result = subprocess.run(
                command, shell=True, capture_output=True,
                text=True, timeout=timeout,
            )
        else:
            # 将命令字符串拆成参数列表，以非 shell 方式执行
            cmd_list = command.split()
            result = subprocess.run(
                cmd_list, shell=False, capture_output=True,
                text=True, timeout=timeout,
            )
    except subprocess.TimeoutExpired:
        return f"[错误] 命令超时（>{timeout}s）: {command}"
    except FileNotFoundError as e:
        return f"[错误] 命令不存在: {e}"
    except Exception as e:
        return f"[错误] 命令执行失败: {e}"

    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        return f"[退出码 {result.returncode}]\n{output}"
    return output or "[命令执行成功, 无输出]"


def _should_use_shell(command: str) -> bool:
    """判断命令是否命中白名单（需走 shell=True 支持管道/重定向/参数）"""
    first = command.strip().split()[0] if command.strip() else ""
    return first in SHELL_ALLOWLIST


# ============================================================
# Toolset 定义 —— 按分组注册
# ============================================================

# 每个 toolset 包含该分组的工具注册函数与说明
_TOOLSETS = {
    "file": {
        "description": "文件读写、目录浏览等文件系统操作",
        "tools": [
            (read_file, "读取文本文件内容"),
            (write_file, "写入/追加文本文件内容"),
            (list_dir, "列出目录内容"),
        ],
    },
    "terminal": {
        "description": "执行 shell 命令，获取命令输出与退出状态",
        "tools": [
            (run_command, "执行一条 shell 命令"),
        ],
    },
}


def register_system_tools(registry: Optional[ToolRegistry] = None) -> int:
    """将所有内置系统工具注册到指定的工具注册表。

    参数:
      registry: 目标注册表（默认注册到全局默认注册表）

    返回:
      注册的工具数量
    """
    reg = registry if registry is not None else _default_registry
    count = 0
    for fn, desc in _iter_toolset_fns():
        # 已注册则跳过（幂等）
        if fn.__name__ in reg:
            continue
        reg.register_fn(
            name=fn.__name__,
            fn=fn,
            description=fn.__doc__ or desc,
        )
        count += 1
    logger.info(f"已注册 {count} 个内置系统工具")
    return count


def _iter_toolset_fns():
    """迭代所有 toolset 中的 (函数, 描述) 对"""
    for group in _TOOLSETS.values():
        for fn, desc in group["tools"]:
            yield fn, desc


def list_toolsets() -> Dict[str, Dict]:
    """返回所有内置 toolset 的元信息"""
    return {
        name: {
            "description": info["description"],
            "tools": [fn.__name__ for fn, _ in info["tools"]],
        }
        for name, info in _TOOLSETS.items()
    }


# ============================================================
# 快捷函数
# ============================================================

def ensure_system_tools() -> int:
    """确保内置系统工具已注册（幂等），返回本次新增数量"""
    return register_system_tools()


# 模块导入时自动注册（保证任何使用方拿到真实能力）
register_system_tools()
