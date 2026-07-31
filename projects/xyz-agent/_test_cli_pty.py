# -*- coding: utf-8 -*-
"""
真实 TTY 下 interactive_select 交互验证
=====================================
用 os.openpty + 子进程在伪终端里运行选择器，
喂入"↓ + 回车"，验证真 TTY 下能正确移动选择并返回第二项。
"""
import os
import pty
import sys
import time
import select

CHILD_CODE = r"""
import sys
sys.dont_write_bytecode = True
from xyz_agent.cli_selector import interactive_select
items = [
    {"name": "alpha", "description": "第一个"},
    {"name": "beta",  "description": "第二个"},
    {"name": "gamma", "description": "第三个"},
]
sel = interactive_select(items, title="TTY测试列表")
# 输出选中结果（去 ANSI）到 stdout
import re
print("SELECTED:" + sel["name"], flush=True)
"""

def run_in_pty(code, keys, timeout=8):
    """在伪终端运行 code，写入 keys，返回 stdout"""
    pid, fd = pty.fork()
    if pid == 0:
        # 子进程
        os.chdir("/root/xyz-aiagent/projects/xyz-agent")
        exec(compile(code, "<child>", "exec"), {"__name__": "__main__"})
        os._exit(0)

    output = b""
    # 先等选择器出现
    time.sleep(1.0)
    try:
        os.write(fd, keys)
    except OSError:
        pass
    deadline = time.time() + timeout
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 0.5)
        if r:
            try:
                data = os.read(fd, 4096)
            except OSError:
                break
            if not data:
                break
            output += data
            if b"SELECTED:" in output:
                break
        else:
            # 子进程可能已退出
            try:
                wpid, status = os.waitpid(pid, os.WNOHANG)
                if wpid == pid:
                    break
            except ChildProcessError:
                break
    try:
        os.waitpid(pid, 0)
    except ChildProcessError:
        pass
    os.close(fd)
    return output.decode("utf-8", "replace")


def main():
    fails = 0

    # 场景 1：默认选中第一项，直接回车 → alpha
    print("场景1: 直接回车选中第一项")
    out = run_in_pty(CHILD_CODE, b"\r")
    if "SELECTED:alpha" in out:
        print("  PASS: 回车选中 alpha")
    else:
        print(f"  FAIL: 输出={out!r}")
        fails += 1

    # 场景 2：按一次 ↓ 再回车 → beta
    print("场景2: ↓+回车选中第二项")
    out = run_in_pty(CHILD_CODE, b"\x1b[B\r")
    if "SELECTED:beta" in out:
        print("  PASS: ↓ 后回车选中 beta")
    else:
        print(f"  FAIL: 输出={out!r}")
        fails += 1

    print(f"\n{'='*40}\n结果: {2-fails}/{2} 通过, {fails} 失败")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
