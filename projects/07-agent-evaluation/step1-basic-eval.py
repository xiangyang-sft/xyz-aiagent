"""
Step 1: 基础评估框架（最简版）
============================
功能：定义测试用例、基础评估器、生成评估报告
概念：测试用例 = (输入, 期望输出, 检查点)
"""

import json
from dataclasses import dataclass, field
from typing import Callable, List, Optional


# ============================================================
# 1. 测试用例定义
# ============================================================

@dataclass
class TestCase:
    """一个测试用例"""
    input: str                              # 用户输入
    expected_output: str                    # 期望输出（参考）
    checkpoints: List[str] = field(default_factory=list)  # 必须包含的关键词
    category: str = "general"               # 测试类别
    id: str = ""                            # 用例 ID

    def __post_init__(self):
        if not self.id:
            self.id = f"tc_{hash(self.input) % 10000}"


@dataclass
class TestResult:
    """一个测试用例的评估结果"""
    test_case: TestCase
    agent_output: str
    passed: bool
    checkpoints_passed: int = 0
    checkpoints_total: int = 0
    score: float = 0.0
    details: str = ""


# ============================================================
# 2. 检查器
# ============================================================

def keyword_check(output: str, keywords: List[str]) -> tuple:
    """检查输出是否包含所有关键词"""
    passed = []
    failed = []
    for kw in keywords:
        if kw.lower() in output.lower():
            passed.append(kw)
        else:
            failed.append(kw)
    return passed, failed


def semantic_similarity_check(output: str, expected: str) -> float:
    """
    简单的语义相似度检查（基于词重叠）
    生产环境应该用 Embedding 相似度或 LLM-as-Judge
    """
    output_words = set(output.lower().split())
    expected_words = set(expected.lower().split())
    if not expected_words:
        return 0.0
    intersection = output_words & expected_words
    return len(intersection) / len(expected_words)


# ============================================================
# 3. 模拟 Agent
# ============================================================

class MockAgent:
    """
    模拟 Agent（用于演示评估系统）
    实际使用中替换为真实 Agent
    """

    def __init__(self, name: str = "MockAgent"):
        self.name = name
        self.steps_taken = 0

    def run(self, user_input: str) -> str:
        self.steps_taken += 1
        # 模拟不同表现
        if "天气" in user_input:
            return "我查询了天气预报，今天北京天气晴朗，气温 25°C，适合外出活动。"
        elif "计算" in user_input:
            return "计算结果如下：15 + 27 = 42。"
        elif "搜索" in user_input or "查询" in user_input:
            return (
                "我搜索到了以下信息：\n"
                "1. AI Agent 是一种能够自主执行任务的智能系统\n"
                "2. 它使用 LLM 作为大脑，结合工具和记忆\n"
                "3. 常见的架构包括 ReAct、Plan-Execute、Reflection"
            )
        elif "推荐" in user_input or "建议" in user_input:
            return "根据你的需求，我推荐以下方案：方案A价格实惠，方案B功能全面。"
        else:
            return f"收到你的消息：{user_input}。我能帮你做什么？"


# ============================================================
# 4. 基础评估器
# ============================================================

class BasicEvaluator:
    """基础评估器：关键词检查 + 语义相似度"""

    def evaluate(self, test_case: TestCase, agent_output: str) -> TestResult:
        checkpoints_passed, checkpoints_failed = keyword_check(
            agent_output, test_case.checkpoints
        )
        total = len(test_case.checkpoints)

        # 检查点通过率
        checkpoint_score = len(checkpoints_passed) / max(total, 1)

        # 与期望输出的语义相似度
        similarity = semantic_similarity_check(
            agent_output, test_case.expected_output
        )

        # 综合得分：检查点 60% + 语义相似度 40%
        score = checkpoint_score * 0.6 + similarity * 0.4

        passed = score >= 0.5  # 阈值

        details = (
            f"检查点通过: {len(checkpoints_passed)}/{total}\n"
            f"语义相似度: {similarity:.2f}\n"
            f"综合得分: {score:.2f}"
        )

        return TestResult(
            test_case=test_case,
            agent_output=agent_output,
            passed=passed,
            checkpoints_passed=len(checkpoints_passed),
            checkpoints_total=total,
            score=score,
            details=details,
        )


# ============================================================
# 5. 评估报告
# ============================================================

class EvalReport:
    """评估报告生成器"""

    def __init__(self, results: List[TestResult]):
        self.results = results

    def summary(self) -> dict:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        scores = [r.score for r in self.results]

        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / max(total, 1),
            "avg_score": sum(scores) / max(len(scores), 1),
            "max_score": max(scores) if scores else 0,
            "min_score": min(scores) if scores else 0,
        }

    def print_report(self):
        summary = self.summary()
        print("=" * 60)
        print("📊 评估报告")
        print("=" * 60)
        print(f"总用例数:    {summary['total']}")
        print(f"通过:        {summary['passed']} ✅")
        print(f"失败:        {summary['failed']} ❌")
        print(f"通过率:      {summary['pass_rate']:.1%}")
        print(f"平均得分:    {summary['avg_score']:.2f}")
        print(f"最高得分:    {summary['max_score']:.2f}")
        print(f"最低得分:    {summary['min_score']:.2f}")
        print("-" * 60)

        # 按类别分组统计
        categories = {}
        for r in self.results:
            cat = r.test_case.category
            if cat not in categories:
                categories[cat] = {"total": 0, "passed": 0}
            categories[cat]["total"] += 1
            if r.passed:
                categories[cat]["passed"] += 1

        print("\n📂 按类别统计：")
        for cat, stats in sorted(categories.items()):
            rate = stats["passed"] / max(stats["total"], 1)
            print(f"  {cat:12s}: {stats['passed']}/{stats['total']} ({rate:.0%})")

        print("-" * 60)

        # 失败的用例详情
        failures = [r for r in self.results if not r.passed]
        if failures:
            print(f"\n❌ 失败的用例 ({len(failures)} 个)：")
            for r in failures:
                print(f"  [{r.test_case.id}] {r.test_case.input[:40]}")
                print(f"    得分: {r.score:.2f}")
                print(f"    详情: {r.details[:80]}...")
                print()

        print("=" * 60)


# ============================================================
# 6. 演示运行
# ============================================================

def main():
    print("🧪 Agent 评估系统 — Step 1: 基础框架\n")

    # 准备测试用例
    test_cases = [
        TestCase(
            input="今天北京的天气怎么样？",
            expected_output="北京天气晴朗，气温25°C",
            checkpoints=["天气", "北京", "气温"],
            category="weather",
        ),
        TestCase(
            input="帮我计算 15 + 27 等于多少？",
            expected_output="15 + 27 = 42",
            checkpoints=["15", "27", "42"],
            category="math",
        ),
        TestCase(
            input="帮我搜索一下 AI Agent 是什么",
            expected_output="AI Agent 是自主智能系统",
            checkpoints=["AI Agent", "自主", "智能"],
            category="search",
        ),
        TestCase(
            input="给我推荐一个方案",
            expected_output="推荐方案A和方案B",
            checkpoints=["推荐", "方案"],
            category="recommendation",
        ),
        TestCase(
            input="你好",
            expected_output="问候回应",
            checkpoints=[],  # 空检查点
            category="general",
        ),
    ]

    # 初始化 Agent 和评估器
    agent = MockAgent(name="我的Agent")
    evaluator = BasicEvaluator()

    # 执行评估
    results = []
    for tc in test_cases:
        print(f"🔍 运行测试: [{tc.id}] {tc.input}")
        output = agent.run(tc.input)
        result = evaluator.evaluate(tc, output)
        results.append(result)
        status = "✅" if result.passed else "❌"
        print(f"   {status} 得分: {result.score:.2f}")
        print(f"   输出: {output[:60]}...")
        print()

    # 生成报告
    report = EvalReport(results)
    report.print_report()


if __name__ == "__main__":
    main()
