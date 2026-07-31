# -*- coding: utf-8 -*-
"""
CLI skill 交互能力测试
======================
参照 Hermes 优化 CLI 的 /skill 能力：
1. /skill（无参数）自动回显当前 skills 列表（非 TTY 也不崩）
2. /skill <name> 按名称直接加载（模糊匹配）
3. interactive_select 在非 TTY 下退化为打印列表，不抛 termios 错误

本测试纯本地、不调用真实 LLM。
"""
import io
import sys
import contextlib

# 保证能 import cli_selector / cli（非 TTY 环境）
sys.dont_write_bytecode = True

from xyz_agent.cli_selector import interactive_select
from xyz_agent.cli import _skill_select, _skill_load
from xyz_agent.skill import SkillDef, SkillManager


class _FakeSkillManager:
    """轻量 fake，复用真实 SkillDef 列表"""

    def __init__(self, skills):
        self._skills = skills

    def list_skills(self):
        return list(self._skills)


class _FakeAgent:
    """CLI 依赖的 agent 最小接口"""

    def __init__(self, skills):
        self.skill_manager = _FakeSkillManager(skills)
        self.rebuilt = 0

    def rebuild_engine(self):
        self.rebuilt += 1


def _make_skills():
    return [
        SkillDef(
            name="calculator",
            description="安全执行数学表达式求值",
            version="1.0.0",
            tags=["math"],
            tools=[{"name": "calculator_calc"}],
            source_path="/tmp/skills/calculator/SKILL.md",
        ),
        SkillDef(
            name="git-helper",
            description="常用 Git 操作辅助",
            version="2.1.0",
            tags=["dev"],
            tools=[{"name": "run_command"}],
            source_path="/tmp/skills/git-helper/SKILL.md",
        ),
        SkillDef(
            name="weather",
            description="查询天气预报",
            version="0.5.0",
            tags=["api"],
            tools=[{"name": "weather_get_current_weather"}],
            source_path="/tmp/skills/weather/SKILL.md",
        ),
    ]


def _run(fn):
    """捕获 stdout 运行函数"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn()
    return buf.getvalue()


def _strip_ansi(s):
    """去除 ANSI 颜色转义码，使断言不依赖颜色包裹"""
    import re
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


def _skill_select_py(agent):  # type: ignore[no-untyped-def]
    """薄封装：测试用鸭子类型 agent 调用生产 _skill_select"""
    return _skill_select(agent)  # type: ignore[arg-type]


def _skill_load_py(agent, name):  # type: ignore[no-untyped-def]
    """薄封装：测试用鸭子类型 agent 调用生产 _skill_load"""
    return _skill_load(agent, name)  # type: ignore[arg-type]


# ─────────────────────────────────────────────
# 测试：interactive_select 非 TTY 容错
# ─────────────────────────────────────────────

def test_nontty_interactive_select_fallback():
    """非 TTY 下选择器退化为打印列表并返回 None，不抛 termios 错误"""
    items = [
        {"name": "calculator", "description": "数学求值"},
        {"name": "git-helper", "description": "Git 操作"},
    ]
    out = _run(lambda: interactive_select(items, title="测试列表"))
    assert "测试列表" in out
    assert "calculator" in out
    assert "git-helper" in out
    # 非 TTY 下返回 None
    assert interactive_select(items, title="测试列表") is None
    print("PASS test_nontty_interactive_select_fallback")


def test_nontty_empty_items():
    """空列表非 TTY 打印 (列表为空) 并返回 None"""
    assert interactive_select([]) is None
    print("PASS test_nontty_empty_items")


# ─────────────────────────────────────────────
# 测试：/skill 自动回显列表
# ─────────────────────────────────────────────

def test_skill_select_echoes_list():
    """/skill 无参数：自动回显当前 skills 完整列表（含 名称/版本/描述/工具数/分类）"""
    agent = _FakeAgent(_make_skills())
    out = _run(lambda: _skill_select_py(agent))
    # 标题 + 数量
    assert "已加载 Skill (3 个)" in out
    # 每个 skill 名称都出现
    assert "calculator" in out
    assert "git-helper" in out
    assert "weather" in out
    # 版本号
    assert "v1.0.0" in out
    assert "v2.1.0" in out
    # 工具数
    assert "1 个工具" in out
    # 非 TTY 下不会 rebuild（sel is None 提前 return）
    assert agent.rebuilt == 0
    print("PASS test_skill_select_echoes_list")


# ─────────────────────────────────────────────
# 测试：/skill <name> 直接加载
# ─────────────────────────────────────────────

def test_skill_load_by_exact_name():
    """/skill calculator：精确匹配加载"""
    agent = _FakeAgent(_make_skills())
    out = _strip_ansi(_run(lambda: _skill_load_py(agent, "calculator")))
    assert "已加载 calculator" in out
    assert agent.rebuilt == 1
    print("PASS test_skill_load_by_exact_name")


def test_skill_load_by_prefix():
    """/skill git：前缀匹配加载"""
    agent = _FakeAgent(_make_skills())
    out = _strip_ansi(_run(lambda: _skill_load_py(agent, "git")))
    assert "已加载 git-helper" in out
    assert agent.rebuilt == 1
    print("PASS test_skill_load_by_prefix")


def test_skill_load_by_fuzzy():
    """/skill weather：包含匹配加载"""
    agent = _FakeAgent(_make_skills())
    out = _strip_ansi(_run(lambda: _skill_load_py(agent, "weather")))
    assert "已加载 weather" in out
    assert agent.rebuilt == 1
    print("PASS test_skill_load_by_fuzzy")


def test_skill_load_case_insensitive():
    """/skill CALCULATOR：大小写不敏感"""
    agent = _FakeAgent(_make_skills())
    out = _strip_ansi(_run(lambda: _skill_load_py(agent, "CALCULATOR")))
    assert "已加载 calculator" in out
    print("PASS test_skill_load_case_insensitive")


def test_skill_load_not_found():
    """/skill nope：未找到时列出当前可用 skills，不崩"""
    agent = _FakeAgent(_make_skills())
    out = _run(lambda: _skill_load_py(agent, "nope"))
    assert "未找到 Skill" in out
    assert "calculator" in out   # 提示当前可用
    assert agent.rebuilt == 0    # 未加载，不 rebuild
    print("PASS test_skill_load_not_found")


def test_skill_load_empty_pool():
    """没有任何 skills 时提示"""
    agent = _FakeAgent([])
    out = _run(lambda: _skill_load_py(agent, "calc"))
    assert "未找到 Skill" in out
    assert "（无）" in out
    print("PASS test_skill_load_empty_pool")


# ─────────────────────────────────────────────
# 测试：真实 SkillManager 集成
# ─────────────────────────────────────────────

def test_real_skill_manager_load():
    """用真实 SkillManager 加载项目 skills 目录后，/skill 能回显真实技能"""
    sm = SkillManager()
    # 项目内的示例 skills
    loaded = sm.load_directory("/root/xyz-aiagent/projects/xyz-agent/skills")
    assert loaded >= 1

    agent = _FakeAgent(sm.list_skills())
    out = _run(lambda: _skill_select_py(agent))
    assert "已加载 Skill" in out
    for s in sm.list_skills():
        assert s.name in out
    # 按名直接加载真实 skill
    first = sm.list_skills()[0].name
    out2 = _strip_ansi(_run(lambda: _skill_load_py(agent, first)))
    assert f"已加载 {first}" in out2
    print(f"PASS test_real_skill_manager_load ({loaded} skills)")


if __name__ == "__main__":
    import traceback
    fails = 0
    tests = [
        test_nontty_interactive_select_fallback,
        test_nontty_empty_items,
        test_skill_select_echoes_list,
        test_skill_load_by_exact_name,
        test_skill_load_by_prefix,
        test_skill_load_by_fuzzy,
        test_skill_load_case_insensitive,
        test_skill_load_not_found,
        test_skill_load_empty_pool,
        test_real_skill_manager_load,
    ]
    for t in tests:
        try:
            t()
        except Exception:
            fails += 1
            print(f"FAIL {t.__name__}")
            traceback.print_exc()
    print(f"\n{'='*40}\n结果: {len(tests)-fails}/{len(tests)} 通过, {fails} 失败")
    sys.exit(1 if fails else 0)
