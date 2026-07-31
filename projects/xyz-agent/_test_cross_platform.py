#!/usr/bin/env python3
"""验证跨平台命令执行优化（本地，不调用 LLM）。

在 POSIX 主机上：
  - 真实验证 POSIX 命令执行（shell / 非 shell / 带引号参数 / 超长截断）
  - 通过 monkeypatch 模拟 Windows 分支，验证:
      1. cmd.exe 命令构造参数正确（[cmd.exe, /d, /s, /c, command]）
      2. _format_result 对 CRLF (\r\n) 归一化为 LF
      3. _win_encoding 不崩溃、返回合理编码
      4. _check_safe_path 的 Windows 敏感路径分支生效
      5. 平台检测逻辑：os.name=="nt" → windows，否则 posix
"""
import os
import sys
from typing import List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import xyz_agent.system_tools as st

passed = 0
failed = 0


def check(label, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✅ {label}")
    else:
        failed += 1
        print(f"  ❌ {label}  {detail}")


print("=" * 60)
print("验证 1: 平台检测逻辑")
print("=" * 60)
check("  IS_WINDOWS 与 os.name 一致", st.IS_WINDOWS == (os.name == "nt"))
check("  _PLATFORM 取值正确", st._PLATFORM in ("windows", "posix"))
_current_platform = "windows" if os.name == "nt" else "posix"
check(
    f"  当前主机平台判定: {st._PLATFORM}",
    st._PLATFORM == _current_platform,
)

print()
print("=" * 60)
print("验证 2: POSIX 命令执行（白名单走 shell）")
print("=" * 60)
out = st.run_command("echo xyz-cross-platform")
check("  echo 输出正确", "xyz-cross-platform" in out)
check("  echo 无 CRLF 残留（已归一化）", "\r" not in out)
out2 = st.run_command("git --version", timeout=10)
check("  git --version （白名单 shell）可执行", "git" in out2.lower())

print()
print("=" * 60)
print("验证 3: POSIX 非白名单命令（参数列表 + 带引号路径）")
print("=" * 60)
# 用 python 作为非白名单测试，带引号参数
out3 = st.run_command('python -c "print(1+1)"', timeout=10)
check("  非白名单命令(参数列表)执行", "2" in out3)
out4 = st.run_command('python -c "import sys; print(sys.platform)"', timeout=10)
check("  带引号参数被正确保留", out4.strip() == sys.platform)

print()
print("=" * 60)
print("验证 4: 空命令与超长输出处理")
print("=" * 60)
out5 = st.run_command("   ")
check("  空命令返回错误提示", "命令为空" in out5)

# 超长输出截断：用 python 打印大量内容
long_cmd = 'python -c "print(\'x\'*6000)"' if st._PLATFORM == "posix" else f'python -c "print(\'x\'*6000)"'
out6 = st.run_command(long_cmd, timeout=15)
check("  超长输出被截断", "截断" in out6 or len(out6) < 6000)

print()
print("=" * 60)
print("验证 5: 模拟 Windows —— cmd.exe 命令构造")
print("=" * 60)
# 不真跑 cmd.exe（本机无），只校验子进程调用参数构造路径
lst = [st.WINDOWS_SHELL, *st.WINDOWS_SHELL_ARGS, "echo hi"]
check("  Windows 命令参数 = [cmd.exe, /d, /s, /c, 命令]",
      lst == ["cmd.exe", "/d", "/s", "/c", "echo hi"])

# 验证 _run_windows 实际调用使用 shell=False + 正确的 cmd 列表（通过捕获 subprocess.run）
import subprocess
orig_run = subprocess.run
captured = {}


def fake_run(cmd_list, **kwargs):
    captured["cmd_list"] = list(cmd_list)
    captured["kwargs"] = kwargs
    # 返回一个伪装的成功结果
    class Fake:
        returncode = 0
        stdout = "dir ok\r\n\r\n"
        stderr = ""
    return Fake()


subprocess.run = fake_run
try:
    got = st._run_windows("dir", 5)
finally:
    subprocess.run = orig_run
check("  走 cmd.exe 构造 (shell=False)", captured.get("cmd_list", [])[:2] == ["cmd.exe", "/d"])
check("  显式传入 encoding/errors", "encoding" in captured.get("kwargs", {}) and captured["kwargs"].get("errors") == "replace")

print()
print("=" * 60)
print("验证 6: 模拟 Windows —— CRLF 归一化 + 编码 + 路径安全")
print("=" * 60)
# _format_result 处理 CRLF（用模拟的 Windows 输出）
class FakeRes:
    returncode = 0
    stdout = "line1\r\nline2\r\n"
    stderr = ""
fmt = st._format_result("dir", FakeRes())
check("  CRLF 归一化为 LF", fmt == "line1\nline2")

# _win_encoding 不崩溃
enc = st._win_encoding()
check("  _win_encoding 返回非空", isinstance(enc, str) and enc != "")

# Windows 敏感路径匹配（用纯函数，不受 POSIX 主机的路径解析影响）
win_blocked = list(st.BLOCKED_PATHS) + list(st.WINDOWS_BLOCKED_PATHS)
check(
    "  Windows 敏感路径被识别 (SAM)",
    st._matches_blocked("c:/windows/system32/config/SAM", win_blocked, True),
)
check(
    "  Windows 敏感路径大小写不敏感",
    st._matches_blocked("C:\\Windows\\System32\\Config\\SAM", win_blocked, True),
)
check(
    "  Windows 普通路径放行",
    not st._matches_blocked("c:/users/myname/notes", win_blocked, True),
)
check(
    "  POSIX 敏感路径匹配不受影响",
    st._matches_blocked("/etc/shadow", list(st.BLOCKED_PATHS), False),
)

print()
print("=" * 60)
print(f"结果: {passed} 通过, {failed} 失败")
print("=" * 60)
sys.exit(1 if failed else 0)
