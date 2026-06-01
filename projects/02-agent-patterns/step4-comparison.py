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

┌─ 面试题 ──────────────────────────────────────────────┐
│                                                           │
│  Q1: ReAct 和 CoT 的区别？                               │
│  A1: CoT 纯推理，ReAct = CoT + Tool Use。                │
│      信息完整任务用 CoT，需外部信息用 ReAct。              │
│                                                           │
│  Q2: Plan-Execute 什么时候需要重新规划？                  │
│  A2: 执行结果不符、依赖失败、遗漏步骤、环境改变。           │
│      实现策略：if unexpected → replan()。                 │
│                                                           │
│  Q3: Reflection 如何防止过度循环？                       │
│  A3: 1.最大迭代 2.阈值 3.改进量检测 4.Token 预算 5.时限  │
│      经验：2-3 轮最优，超过 5 轮边际收益急剧下降。         │
│                                                           │
│  Q4: 三种模式如何组合？举例？                             │
│  A4: 编程助手：Plan-Execute 规划 → ReAct 执行 →           │
│      Reflection 审查。实际产品几乎必是组合。               │
│                                                           │
│  Q5: ReAct 中无效 Action 格式怎么办？                    │
│  A5: 分层容错：Retry(重试) → Repair(修复) →               │
│      Fallback(降级) → Rollback(回退)。                    │
│                                                           │
│  Q6: PLAN 格式设计要点？                                 │
│  A6: 每步一个工具、明确依赖、适中粒度(10-15步)、          │
│      支持重新规划。                                       │
│                                                           │
│  Q7: Reflection 中 Critic 质量怎么保证？                 │
│  A7: 结构化检查清单、多 Critic 投票、规则引擎辅助、       │
│      Critic Prompt 工程、定期回测。                       │
│                                                           │
│  Q8: ReAct 的 Thought 可以跳过吗？                       │
│  A8: 不推荐。Thought 有 4 个作用：推理锚点、可解释性、     │
│      错误追踪、上下文保持。简单任务可用 FC 压缩。          │
│                                                           │
│  Q9: 三种模式 Token 消耗量化对比？                       │
│  A9: Plan-Execute(2000) < ReAct(2500) < Reflection(2700) │
│      组合控制在 3700（5 步任务）。Observation 要摘要。    │
│                                                           │
│  Q10: 如何测试和评估？指标？                              │
│  A10: Unit + Integration + E2E + 回归 四层测试。          │
│      指标：完成率>90%，步数<5，无效调用<10%，循环率<5%。   │
│                                                           │
└───────────────────────────────────────────────────────────┘
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
