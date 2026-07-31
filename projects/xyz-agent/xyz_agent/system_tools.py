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
  - 命令执行跨平台：根据 OS 选择正确的 shell 与安全策略
      - POSIX: 白名单命令走 shell=True，其余走 shell=False（防注入）
      - Windows: 由 cmd.exe 解释（shell=True），安全靠超时 + 输出截断
"""

import os
import sys
import glob
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .tool import ToolRegistry, _default_registry

logger = logging.getLogger(__name__)

# ============================================================
# 平台检测
# ============================================================

# 当前运行平台："windows" 或 "posix"
IS_WINDOWS = os.name == "nt"
_PLATFORM = "windows" if IS_WINDOWS else "posix"

# Windows 下 cmd.exe 的启动器（/d 忽略自动运行键, /c 执行后退出, /s /q 简化引号处理）
WINDOWS_SHELL = "cmd.exe"
WINDOWS_SHELL_ARGS = ["/d", "/s", "/c"]

# POSIX 默认 shell
POSIX_SHELL = "/bin/sh"
POSIX_SHELL_ARGS = ["-c"]


# ============================================================
# 安全配置
# ============================================================

# 命令执行超时（秒）
DEFAULT_TIMEOUT = 30

# POSIX 允许走 shell=True 的白名单命令（支持管道/重定向/参数）
# 其余 POSIX 命令一律 shell=False，以列表参数方式执行，避免 shell 注入
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

# 默认禁止读取/写入的敏感路径（POSIX 与 Windows 各一套）
BLOCKED_PATHS = (
    "/etc/shadow",
    "/etc/passwd",
    "/root/.ssh",
    "/root/.aws",
    "/root/.hermes",
)

# Windows 下禁止访问的敏感目录（引导/系统目录，防止误操作）
WINDOWS_BLOCKED_PATHS = (
    "C:/Windows/System32/config",
    "C:/Program Files",
    "C:/Users/Public",
)

# 目录浏览返回的最大条目数
MAX_LIST_ITEMS = 200

# 单个命令输出返回的最大字符数（防止模型输出大到撑爆上下文）
MAX_CMD_OUTPUT = 5000


# ============================================================
# 路径安全检查
# ============================================================

def _resolve_path(path: str) -> str:
    """展开 ~ 并转为平台识别出的绝对路径。

    跨平台：Windows 下保留盘符与反斜杠（用 os.path.abspath），
    POSIX 下用 Path.resolve 规范化。这样敏感路径匹配在不同平台都一致。
    """
    expanded = Path(path).expanduser()
    if IS_WINDOWS:
        # Windows: 用 abspath 保留盘符（如 C:\\...），不追逐符号链接
        return os.path.abspath(str(expanded))
    return str(expanded.resolve())


def _check_safe_path(path: str) -> str:
    """检查并返回安全路径，禁止访问敏感位置（平台感知）"""
    resolved = _resolve_path(path)

    # 平台相关的敏感路径
    blocked_list: List[str] = list(BLOCKED_PATHS)
    if IS_WINDOWS:
        blocked_list.extend(WINDOWS_BLOCKED_PATHS)

    if _matches_blocked(resolved, blocked_list, IS_WINDOWS):
        raise PermissionError(f"禁止访问敏感路径: {path}")
    return resolved


def _matches_blocked(path: str, blocked_list: Sequence[str], is_windows: bool) -> bool:
    """纯路径匹配：判断 path 是否命中任一敏感前缀（与平台路径解析解耦，便于测试）。

    is_windows=True 时做大小写不敏感 + 反斜杠归一化匹配。
    """
    norm_path = path.replace("\\", "/").lower() if is_windows else path
    for blocked in blocked_list:
        norm_blocked = blocked.replace("\\", "/").lower() if is_windows else blocked
        if norm_path.startswith(norm_blocked.rstrip("/")):
            return True
    return False


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
    """在系统 shell 中执行一条命令并返回输出（跨平台）。

    参数:
      command: 要执行的命令（字符串）
      timeout: 超时秒数（默认 30）

    返回:
      命令的 stdout + stderr 合并输出（超长自动截断）

    安全与平台策略（对齐 Hermes）:
      - POSIX:   白名单命令走 shell=True（支持管道/重定向），
                 其余以参数列表 shell=False 执行，避免 shell 注入
      - Windows: 交给 cmd.exe 解释（shell=True），正确支持 dir/type/echo
                 等内置命令；安全靠超时 + 输出截断
      - 两者均显式处理编码（errors=replace），避免 GBK 等崩溃
    """
    if not command or not command.strip():
        return "[错误: 命令为空]"

    try:
        if _PLATFORM == "windows":
            result = _run_windows(command, timeout)
        else:
            result = _run_posix(command, timeout)
    except subprocess.TimeoutExpired:
        return f"[错误] 命令超时（>{timeout}s）: {command}"
    except FileNotFoundError as e:
        return f"[错误] 命令或 shell 不存在: {e}"
    except Exception as e:
        return f"[错误] 命令执行失败: {e}"

    return _format_result(command, result)


def _run_posix(command: str, timeout: int) -> "subprocess.CompletedProcess[str]":
    """POSIX 平台命令执行：白名单走 shell，其余走参数列表"""
    use_shell = _should_use_shell_posix(command)
    if use_shell:
        return subprocess.run(
            [POSIX_SHELL, *POSIX_SHELL_ARGS, command],
            shell=False, capture_output=True,
            text=True, timeout=timeout,
        )
    # 非白名单：以参数列表执行，避免 shell 注入
    cmd_list = _split_command_posix(command)
    return subprocess.run(
        cmd_list, shell=False, capture_output=True,
        text=True, timeout=timeout,
    )


def _run_windows(command: str, timeout: int) -> "subprocess.CompletedProcess[str]":
    """Windows 平台命令执行：交给 cmd.exe 解释，
    正确处理 dir/type/echo/cd/copy 等内置命令与管道。
    """
    return subprocess.run(
        [WINDOWS_SHELL, *WINDOWS_SHELL_ARGS, command],
        shell=False, capture_output=True,
        text=True, encoding=_win_encoding(), errors="replace",
        timeout=timeout,
    )


def _format_result(command: str, result) -> str:
    """统一格式化命令输出（含超长截断与退出码标注）"""
    output = (result.stdout or "") + (result.stderr or "")
    output = output.replace("\r\n", "\n").strip()
    if len(output) > MAX_CMD_OUTPUT:
        output = output[:MAX_CMD_OUTPUT] + f"\n... [输出已截断，共 {len(output)} 字符]"
    if result.returncode != 0:
        return f"[退出码 {result.returncode}]\n{output}"
    return output or "[命令执行成功, 无输出]"


def _should_use_shell_posix(command: str) -> bool:
    """POSIX 下判断命令是否命中白名单（需走 shell 支持管道/重定向/参数）"""
    first = command.strip().split()[0] if command.strip() else ""
    return first in SHELL_ALLOWLIST


def _split_command_posix(command: str) -> List[str]:
    """POSIX 非白名单命令：拆成参数列表（尽力处理引号）"""
    return _shlex_split(command)


def _shlex_split(command: str) -> List[str]:
    """按 shell 规则拆分命令字符串为参数列表，保留带引号的参数"""
    import shlex
    try:
        return shlex.split(command)
    except ValueError:
        # 引号不完整时回退到简单空格拆分
        return command.split()


def _win_encoding() -> str:
    """Windows 下的命令编码：优先 UTF-8，检测失败回退系统代码页"""
    try:
        if sys.stdout and hasattr(sys.stdout, "encoding") and sys.stdout.encoding:
            return sys.stdout.encoding or "utf-8"
    except Exception:
        pass
    return "utf-8"


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
        "description": "跨平台执行系统命令（POSIX 用 /bin/sh，Windows 用 cmd.exe），获取输出与退出状态",
        "tools": [
            (run_command, "执行一条系统命令（自动适配当前 OS 的 shell）"),
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
