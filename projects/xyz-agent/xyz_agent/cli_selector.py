#!/usr/bin/env python3
"""
xyz_agent.cli_selector — 交互式选择器（方向键上下选择 + 回车确认）

纯标准库实现，无第三方依赖。
支持：方向键 ↑↓、Vim 键 j/k、首页/末页、搜索过滤、彩色显示。
跨平台兼容：Linux/macOS (termios) + Windows (msvcrt)。
"""

import sys
import os
import re

# ── 平台检测 ──

_IS_WINDOWS = os.name == "nt"

if _IS_WINDOWS:
    import msvcrt
else:
    import termios
    import tty


# ── 颜色（Windows 10+ 支持 ANSI，低版本 fallback） ──

class Style:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    REVERSE = "\033[7m"
    RESET = "\033[0m"


def _color(text: str, color: str) -> str:
    """给文本上色（Windows 不支持 ANSI 时返回原文本）"""
    if _IS_WINDOWS:
        # Windows 10 1511+ 支持 ANSI，尝试启用
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            return f"{color}{text}{Style.RESET}"
        except Exception:
            return text
    return f"{color}{text}{Style.RESET}"


# ── 终端控制 ──

def _getch() -> str:
    """
    读取一个按键（阻塞）。

    POSIX:   termios raw mode + sys.stdin.read(1)
    Windows: msvcrt.getch()
    """
    if _IS_WINDOWS:
        ch = msvcrt.getch()
        # 方向键等扩展键 — getch 返回 \xe0 或 \x00，需要再读一次
        if ch in (b'\xe0', b'\x00'):
            ch2 = msvcrt.getch()
            # 映射 Windows 扫描码 → ANSI 转义序列
            mapping = {
                b'H': '\x1b[A',   # ↑
                b'P': '\x1b[B',   # ↓
                b'M': '\x1b[C',   # →
                b'K': '\x1b[D',   # ←
                b'G': '\x1b[H',   # Home
                b'O': '\x1b[F',   # End
                b'I': '\x1b[5~',  # PageUp
                b'Q': '\x1b[6~',  # PageDown
            }
            return mapping.get(ch2, '\x1b')
        try:
            result = ch.decode('utf-8')
        except UnicodeDecodeError:
            result = chr(ch[0]) if isinstance(ch, bytes) and len(ch) == 1 else ''
        # 处理回车（Windows 下是 \r）
        if result == '\r':
            return '\n'
        return result

    # POSIX 实现
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        # 处理转义序列
        if ch == '\x1b':
            more = sys.stdin.read(2)
            return ch + more
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _clear_lines(n: int):
    """清除 n 行输出（ANSI 转义码，Windows 10+ 和 POSIX 均支持）"""
    for _ in range(n):
        sys.stdout.write("\033[2K\033[1A")  # 清除当前行 + 上移一行
    sys.stdout.write("\033[2K")  # 最后也清除
    sys.stdout.flush()


# ── 条目格式化 ──

def _format_item(item) -> str:
    """将任意类型的条目转为显示的字符串"""
    if isinstance(item, dict):
        name = item.get("name", str(item))
        desc = item.get("description", "")
        if desc:
            return f"{_color(name, Style.BOLD)}  {_color(desc[:60], Style.DIM)}"
        return name
    return str(item)


def _format_item_compact(item) -> str:
    """紧凑显示的字符串（选择器用）"""
    if isinstance(item, dict):
        name = item.get("name", str(item))
        desc = item.get("description", "")
        tags = item.get("tags", [])
        extras = []
        if tags:
            extras.append(_color(",".join(tags[:3]), Style.CYAN))
        if desc:
            label = f"{name}: {desc[:50]}"
        else:
            label = name
        if extras:
            return f"{label}  [{', '.join(extras)}]"
        return label
    return str(item)


def _get_item_name(item) -> str:
    """获取条目的名称（用于匹配）"""
    if isinstance(item, dict):
        return str(item.get("name", ""))
    return str(item).split(":")[0].strip()


# ── 搜索提示行 ──

def _print_search_prompt(query: str, total: int, filtered: int):
    """打印搜索过滤行"""
    if query:
        status = f"{_color(f'{filtered}/{total}', Style.YELLOW)} 匹配"
    else:
        status = _color(f"{total} 项", Style.DIM)
    search_text = query or _color('(输入过滤)', Style.DIM)
    sys.stdout.write(f" {_color('🔍', Style.DIM)} 搜索: {search_text}  {status}")
    sys.stdout.flush()


# ── 核心选择器 ──

def interactive_select(
    items,
    title: str = "",
    prompt: str = "上下键选择，回车确认，/搜索过滤",
    width: int = 80,
    page_size: int = 15,
    enable_search: bool = True,
    return_index: bool = False,
):
    """
    交互式选择器 — 方向键上下选择，回车确认

    参数:
        items: 可选列表（元素可以是字符串或 dict）
        title: 标题文本
        prompt: 底部提示
        width: 显示宽度（默认自动）
        page_size: 每页显示条数
        enable_search: 是否启用 / 搜索过滤
        return_index: True 返回索引，False 返回元素

    返回:
        选中的条目（或索引），按 ESC/Ctrl+C 返回 None
    """
    if not items:
        print(f"{Style.YELLOW}(列表为空){Style.RESET}")
        return None

    # 非 TTY 环境（管道/重定向/远程 shell）：退化为打印列表，避免 termios 崩溃
    if not sys.stdin.isatty():
        if title:
            print(f"\n {_color(title, Style.BOLD)}")
        for item in items:
            print(f"  {_format_item(item)}")
        if prompt:
            print(f" {_color(prompt, Style.DIM)}")
        return None

    # 自动获取终端宽度
    try:
        width = os.get_terminal_size().columns
    except Exception:
        width = width or 80

    # 初始显示
    filtered = list(items)
    query = ""
    selected = 0

    # 计算每页显示数（留出标题+提示+搜索行空间）
    try:
        _, term_height = os.get_terminal_size()
        page_size = min(page_size, term_height - 6)
    except Exception:
        page_size = min(page_size, 15)

    def _display():
        """刷新显示"""
        # 计算当前页
        total_filtered = len(filtered)
        page_start = (selected // page_size) * page_size
        page_end = min(page_start + page_size, total_filtered)
        visible = range(page_start, page_end)

        lines = []

        # 标题
        if title:
            lines.append(f"\n {_color(title, Style.BOLD)}")

        # 搜索行
        if enable_search and query:
            search_info = _color(f'{total_filtered}/{len(items)}', Style.DIM)
            lines.append(f" {_color('🔍', Style.YELLOW)} 搜索: {query}  {search_info}")
        elif enable_search:
            lines.append(f" {_color('🔍', Style.DIM)} 输入 / 过滤")

        # 分隔线
        sep = _color("─" * min(width - 4, 60), Style.DIM)
        lines.append(f" {sep}")

        # 条目列表
        for i in visible:
            item = filtered[i]
            is_sel = (i == selected)
            label = _format_item_compact(item)

            if is_sel:
                prefix = _color("▸", Style.CYAN)
                text = f" {prefix} {label}"
                text = _color(text, Style.REVERSE)
            else:
                prefix = " "
                text = f" {prefix}  {label}"

            lines.append(f"  {text}")

        # 补空白
        for _ in range(page_start + page_size - page_end):
            lines.append("")

        # 底部提示
        lines.append(f" {_color(prompt, Style.DIM)}")

        # 输出
        sys.stdout.write("\n".join(lines))
        sys.stdout.flush()

    # 显示
    _display()

    display_lines = page_size + 5  # title + sep + items + padding + prompt

    while True:
        ch = _getch()

        # 清除显示
        _clear_lines(display_lines)

        if ch == "\x1b[A" or ch == "k":  # ↑ 或 k
            selected = (selected - 1) % len(filtered)

        elif ch == "\x1b[B" or ch == "j":  # ↓ 或 j
            selected = (selected + 1) % len(filtered)

        elif ch == "\x1b[H" or ch == "g":  # Home 或 g
            selected = 0

        elif ch == "\x1b[F" or ch == "G":  # End 或 G
            selected = len(filtered) - 1

        elif ch == "\x1b[5~" or ch == "\x1b[6~":  # PageUp / PageDown
            if ch == "\x1b[5~":
                selected = max(0, selected - page_size)
            else:
                selected = min(len(filtered) - 1, selected + page_size)

        elif ch == "\r" or ch == "\n":  # 回车确认
            result = filtered[selected]
            print()
            if return_index:
                for idx, item in enumerate(items):
                    if item is filtered[selected]:
                        return idx
            return result

        elif ch == "\x1b" or ch == "\x03":  # ESC 或 Ctrl+C
            print(f" {_color('已取消', Style.YELLOW)}")
            return None

        elif ch == "/":  # 进入搜索模式
            if not enable_search:
                _display()
                continue
            query = ""
            while True:
                sys.stdout.write(f" {_color('🔍', Style.YELLOW)} 搜索: {query}")
                sys.stdout.flush()
                sc = _getch()
                sys.stdout.write("\033[2K\r")
                sys.stdout.flush()

                if sc == "\r" or sc == "\n":
                    break
                elif sc == "\x1b" or sc == "\x03":
                    query = ""
                    break
                elif sc == "\x7f" or sc == "\b":  # Backspace
                    query = query[:-1]
                elif sc.isprintable():
                    query += sc

                # 实时过滤
                q = query.lower()
                filtered = [
                    item for item in items
                    if q in _get_item_name(item).lower()
                    or q in _format_item(item).lower()
                ]
                if not filtered:
                    filtered = items
                    query = ""
                    break
                selected = 0

            if query == "":
                filtered = items

        elif ch == "\t":  # Tab — 重置搜索
            query = ""
            filtered = items
            selected = 0

        elif ch.isprintable() and enable_search:
            # 直接输入字符开始搜索
            query = ch
            q = query.lower()
            filtered = [
                item for item in items
                if q in _get_item_name(item).lower()
                or q in _format_item(item).lower()
            ]
            if not filtered:
                filtered = items
                query = ""
            selected = 0

        # 重新显示
        _display()

    return None


def confirm(prompt_text: str = "确认?") -> bool:
    """简单的 Y/n 确认"""
    sys.stdout.write(f" {prompt_text} [{_color('Y', Style.GREEN)}/n] ")
    sys.stdout.flush()
    ch = _getch()
    print(ch if ch != "\r" else "y")
    return ch == "\r" or ch.lower() == "y" or ch == " "


def input_text(prompt_text: str, default: str = "") -> str:
    """
    带提示的文本输入。

    POSIX:   恢复终端行缓冲，用 sys.stdin.readline()
    Windows: 标准 input() 即可（msvcrt 模式不需要特殊处理）
    """
    if default:
        sys.stdout.write(f" {prompt_text} [{_color(default, Style.DIM)}]: ")
    else:
        sys.stdout.write(f" {prompt_text}: ")
    sys.stdout.flush()

    if _IS_WINDOWS:
        # Windows 下直接用标准 input
        text = input().strip()
    else:
        # POSIX: 临时恢复终端设置读取一行
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
            text = sys.stdin.readline().strip()
        finally:
            pass

    return text or default
