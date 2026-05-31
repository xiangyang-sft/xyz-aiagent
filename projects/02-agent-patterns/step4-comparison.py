"""
Step 4 - 三种模式对比运行 + 组合使用示例
"""

import subprocess
import sys

DEMOS = {
    "1": {"name": "ReAct", "file": "step1-react.py", "desc": "推理+行动交替循环"},
    "2": {"name": "Plan-Execute", "file": "step2-plan-execute.py", "desc": "先规划再执行"},
    "3": {"name": "Reflection", "file": "step3-reflection.py", "desc": "Actor-Critic 自改进"},
}

COMPARISON = """
┌─────────────────────────────────────────────────────────────────────┐
│                   Agent 核心设计模式对比总结                          │
├──────────────┬──────────────┬──────────────┬───────────────────────┤
│   维度       │   ReAct      │ Plan-Execute │  Reflection           │
├──────────────┼──────────────┼──────────────┼───────────────────────┤
│ 核心思想     │ 想一步走一步 │ 先看地图再走 │ 走一步回头看看        │
│ 规划时机     │ 边做边想     │ 先全局规划   │ 迭代改进              │
│ 灵活性       │ ⭐⭐⭐ 高    │ ⭐⭐ 中     │ ⭐⭐ 中              │
│ 可解释性     │ ⭐⭐⭐ 高    │ ⭐⭐⭐ 高   │ ⭐⭐ 中              │
│ 复杂任务     │ ⭐⭐ 一般    │ ⭐⭐⭐ 优秀 │ ⭐⭐⭐ 良好          │
│ Token 消耗   │ 高（每步想） │ 中（一次规划）│ 高（多轮迭代）       │
│ 执行效率     │ ⭐⭐ 中      │ ⭐⭐⭐ 高   │ ⭐ 低（需多次迭代）  │
│ 自我改进     │ 无           │ 有限         │ ⭐⭐⭐ 核心机制      │
│ 适用场景     │ 客服/搜索    │ 研究/开发    │ 代码/写作/决策       │
│ 典型代表     │ AutoGPT      │ BabyAGI      │ Reflexion            │
└──────────────┴──────────────┴──────────────┴───────────────────────┘

组合使用推荐:
  🔹 Plan-Execute + ReAct   = 全局规划 + 每步灵活执行
  🔹 ReAct + Reflection     = 每步推理后自检再行动
  🔹 Plan-Execute + Reflection = 规划后逐步执行并持续改进
  🔹 三者叠加               = 复杂任务的终极方案

选择指南:
  • 简单问答/搜索      → ReAct
  • 复杂多步任务/研究   → Plan-Execute + ReAct
  • 代码生成/写作      → Reflection
  • 数据分析/报告      → Plan-Execute
  • 客服/对话          → ReAct + Reflection
"""


def main():
    print("=" * 60)
    print("🧩 Agent 核心设计模式 — 演示选择")
    print("=" * 60)

    for key, demo in DEMOS.items():
        print(f"  [{key}] {demo['name']:15s} — {demo['desc']}")

    print(f"  [a] 全部运行")
    print(f"  [c] 显示对比总结")
    print(f"  [q] 退出")
    print()

    while True:
        choice = input("请选择 (1/2/3/a/c/q): ").strip().lower()
        if choice == "q":
            break
        elif choice == "c":
            print(COMPARISON)
        elif choice == "a":
            for key, demo in DEMOS.items():
                print(f"\n\n{'#'*60}")
                print(f"# 运行 {demo['name']}")
                print(f"{'#'*60}")
                run_demo(demo)
        elif choice in DEMOS:
            run_demo(DEMOS[choice])
        else:
            print("无效选择")


def run_demo(demo):
    """运行单个演示脚本"""
    script_path = __file__.rsplit("/", 1)[0] + "/" + demo["file"]
    print(f"\n▶  python {demo['file']}")
    print()

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.stdout:
            print(result.stdout[-3000:])  # 截取最后部分
        if result.stderr:
            print(f"⚠️  错误输出:\n{result.stderr[-1000:]}")
    except subprocess.TimeoutExpired:
        print("⏰ 执行超时")
    except Exception as e:
        print(f"❌ 执行失败: {e}")


if __name__ == "__main__":
    # 非交互模式，直接显示对比总结
    print(COMPARISON)
