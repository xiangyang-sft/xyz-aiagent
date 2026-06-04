"""
Step 3: 完整评估 Pipeline
==========================
功能：批量评估、自动重试、JSON+Markdown 报告、对比实验（A/B）
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


# ============================================================
# 1. 测试用例集
# ============================================================

@dataclass
class TestCase:
    """测试用例"""
    input: str
    expected: str = ""
    checkpoints: List[str] = field(default_factory=list)
    category: str = "general"
    id: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = f"tc_{abs(hash(self.input)) % 100000:05d}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict):
        return cls(**d)


def load_test_cases(path: str) -> List[TestCase]:
    """从 JSON 文件加载测试用例"""
    path = Path(path)
    if not path.exists():
        print(f"⚠️ 文件不存在: {path}，使用默认测试用例")
        return get_default_cases()

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [TestCase.from_dict(item) for item in data]


def get_default_cases() -> List[TestCase]:
    """默认测试用例"""
    cases = [
        {"input": "今天北京的天气怎么样？",
         "expected": "北京天气晴朗，气温适宜",
         "checkpoints": ["天气", "北京"],
         "category": "weather"},
        {"input": "帮我计算 15 + 27 等于多少？",
         "expected": "42",
         "checkpoints": ["42"],
         "category": "math"},
        {"input": "搜索一下 AI Agent 的定义",
         "expected": "AI Agent 是自主智能系统",
         "checkpoints": ["AI Agent", "智能"],
         "category": "search"},
        {"input": "帮我翻译 'Hello World' 成中文",
         "expected": "你好世界",
         "checkpoints": ["你好", "世界"],
         "category": "translation"},
        {"input": "写一首关于春天的诗",
         "expected": "一首关于春天的诗",
         "checkpoints": ["春"],
         "category": "creative"},
        {"input": "推荐一个学习编程的网站",
         "expected": "推荐学习网站",
         "checkpoints": ["推荐", "编程", "学习"],
         "category": "recommendation"},
        {"input": "Python 中如何读取文件？",
         "expected": "使用 open() 函数读取文件",
         "checkpoints": ["open", "文件"],
         "category": "coding"},
        {"input": "解释一下什么是 RAG",
         "expected": "RAG 是检索增强生成",
         "checkpoints": ["RAG", "检索", "生成"],
         "category": "tech"},
    ]
    return [TestCase(**c) for c in cases]


# ============================================================
# 2. Agent 接口
# ============================================================

class AgentInterface:
    """Agent 抽象接口"""

    def run(self, user_input: str) -> str:
        raise NotImplementedError

    def get_info(self) -> dict:
        return {"name": self.__class__.__name__}


class MockAgent(AgentInterface):
    """模拟 Agent"""

    def __init__(self, name: str = "MockAgent-v1", error_rate: float = 0.0):
        self.name = name
        self.error_rate = error_rate

    def run(self, user_input: str) -> str:
        # 模拟随机失败
        if self.error_rate > 0 and hash(user_input) % 100 < self.error_rate * 100:
            return "抱歉，我遇到了错误。"
        return f"对于「{user_input}」的回答：这是一个模拟输出。"

    def get_info(self) -> dict:
        return {"name": self.name, "error_rate": self.error_rate}


class BetterMockAgent(AgentInterface):
    """更好的模拟 Agent（更高精度）"""

    def __init__(self, name: str = "MockAgent-v2"):
        self.name = name

    def run(self, user_input: str) -> str:
        responses = {
            "天气": "根据天气预报，今天北京天气晴朗，气温25°C，适合出行。",
            "计算": "计算结果：15 + 27 = 42。",
            "AI Agent": "AI Agent 是一种使用LLM作为大脑，结合工具和记忆的自主智能系统。",
            "翻译": '"Hello World" 的中文翻译是 "你好，世界"。',
            "春天": "春风拂面，百花盛开，燕子归来。春天是一年中最美的季节。",
            "编程": "推荐学习编程的网站：Codecademy、freeCodeCamp、LeetCode。",
            "RAG": "RAG (Retrieval-Augmented Generation) 是一种结合检索和生成的AI技术。",
        }
        for key, response in responses.items():
            if key in user_input:
                return response
        return f"收到：{user_input}"

    def get_info(self) -> dict:
        return {"name": self.name, "type": "better_mock"}


# ============================================================
# 3. 评估器
# ============================================================

@dataclass
class EvalResult:
    """单用例评估结果"""
    test_case_id: str
    passed: bool
    score: float
    steps: int = 1
    tokens: int = 0
    checkpoint_pass: int = 0
    checkpoint_total: int = 0
    details: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class CheckpointEvaluator:
    """检查点评估器"""

    def evaluate(self, test_case: TestCase, output: str,
                 steps: int = 1, tokens: int = 0) -> EvalResult:
        """评估单个用例"""
        checkpoints = test_case.checkpoints
        passed_kws = []
        failed_kws = []

        for kw in checkpoints:
            if kw.lower() in output.lower():
                passed_kws.append(kw)
            else:
                failed_kws.append(kw)

        total = len(checkpoints)
        passed_count = len(passed_kws)

        # 基础分 = 检查点通过率
        if total == 0:
            score = 1.0  # 无检查点默认满分
        else:
            score = passed_count / total

        passed = score >= 0.5
        details = f"通过关键词: {passed_kws} | 失败: {failed_kws}"

        return EvalResult(
            test_case_id=test_case.id,
            passed=passed,
            score=score,
            steps=steps,
            tokens=tokens,
            checkpoint_pass=passed_count,
            checkpoint_total=total,
            details=details,
        )


# ============================================================
# 4. 评估 Pipeline
# ============================================================

class EvalPipeline:
    """完整评估 Pipeline"""

    def __init__(self, agent: AgentInterface, test_cases: List[TestCase],
                 evaluator: Optional[CheckpointEvaluator] = None,
                 cache_dir: Optional[str] = None):
        self.agent = agent
        self.test_cases = test_cases
        self.evaluator = evaluator or CheckpointEvaluator()
        self.cache_dir = cache_dir
        self.results: List[EvalResult] = []
        self.metadata: dict = {}

    def _get_cache_key(self, agent_name: str, test_case: TestCase) -> str:
        """生成缓存 key"""
        content = f"{agent_name}::{test_case.input}"
        return hashlib.md5(content.encode()).hexdigest()

    def _load_cache(self, cache_key: str) -> Optional[str]:
        """从缓存加载 Agent 输出"""
        if not self.cache_dir:
            return None
        cache_path = Path(self.cache_dir) / f"{cache_key}.txt"
        if cache_path.exists():
            return cache_path.read_text(encoding="utf-8")
        return None

    def _save_cache(self, cache_key: str, output: str):
        """保存 Agent 输出到缓存"""
        if not self.cache_dir:
            return
        cache_dir = Path(self.cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"{cache_key}.txt"
        cache_path.write_text(output, encoding="utf-8")

    def run(self, max_retries: int = 2, use_cache: bool = True,
            verbose: bool = True) -> "EvalPipeline":
        """执行评估 Pipeline"""
        agent_info = self.agent.get_info()
        self.metadata = {
            "agent": agent_info,
            "total_cases": len(self.test_cases),
            "started_at": datetime.now().isoformat(),
            "cache_enabled": use_cache and bool(self.cache_dir),
        }

        if verbose:
            print(f"🚀 评估 Pipeline 启动")
            print(f"   Agent: {agent_info.get('name', 'unknown')}")
            print(f"   测试用例: {len(self.test_cases)} 个")
            print(f"   缓存: {'开启' if self.metadata['cache_enabled'] else '关闭'}")
            print()

        for i, tc in enumerate(self.test_cases, 1):
            if verbose:
                print(f"  [{i}/{len(self.test_cases)}] {tc.id}: {tc.input[:40]}...",
                      end=" ")

            # 尝试缓存
            agent_name = agent_info.get("name", "unknown")
            cache_key = self._get_cache_key(agent_name, tc)
            cached_output = self._load_cache(cache_key) if use_cache else None

            if cached_output is not None:
                if verbose:
                    print("📦 缓存命中")
                output = cached_output
                steps, tokens = 0, 0
                error = None
            else:
                # 执行 Agent
                output = ""
                steps, tokens = 1, 0
                error = None

                for attempt in range(1 + max_retries):
                    try:
                        output = self.agent.run(tc.input)
                        if use_cache and self.cache_dir:
                            self._save_cache(cache_key, output)
                        break
                    except Exception as e:
                        error = str(e)
                        if attempt < max_retries:
                            if verbose:
                                print(f"(重试 {attempt+1}/{max_retries}) ", end="")
                            time.sleep(1)
                        else:
                            if verbose:
                                print("❌ 失败")
                            continue

            # 评估
            result = self.evaluator.evaluate(tc, output, steps=steps,
                                              tokens=tokens)
            if error:
                result.error = error
                result.passed = False
                result.score = 0.0
                result.details = f"执行错误: {error}"

            self.results.append(result)
            status = "✅" if result.passed else "❌"
            if verbose and not cached_output:
                print(f"{status} 得分: {result.score:.2f}")

        self.metadata["finished_at"] = datetime.now().isoformat()
        self.metadata["duration"] = (
            datetime.fromisoformat(self.metadata["finished_at"])
            - datetime.fromisoformat(self.metadata["started_at"])
        ).total_seconds()

        return self

    # ============================================================
    # 5. 报告生成
    # ============================================================

    def generate_report(self, format: str = "console"):
        """生成评估报告"""
        if format == "json":
            return self._json_report()
        elif format == "markdown":
            return self._markdown_report()
        else:
            return self._console_report()

    def _compute_stats(self) -> dict:
        """计算统计数据"""
        total = len(self.results)
        if total == 0:
            return {"error": "无评估结果"}

        passed = sum(1 for r in self.results if r.passed)
        scores = [r.score for r in self.results]

        # 按类别统计
        tc_map = {tc.id: tc for tc in self.test_cases}
        categories = {}
        for r in self.results:
            tc = tc_map.get(r.test_case_id)
            cat = tc.category if tc else "unknown"
            if cat not in categories:
                categories[cat] = {"total": 0, "passed": 0, "scores": []}
            categories[cat]["total"] += 1
            if r.passed:
                categories[cat]["passed"] += 1
            categories[cat]["scores"].append(r.score)

        category_stats = {}
        for cat, stats in categories.items():
            avg = sum(stats["scores"]) / max(len(stats["scores"]), 1)
            category_stats[cat] = {
                "total": stats["total"],
                "passed": stats["passed"],
                "pass_rate": stats["passed"] / max(stats["total"], 1),
                "avg_score": avg,
            }

        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / max(total, 1),
            "avg_score": sum(scores) / max(len(scores), 1),
            "max_score": max(scores) if scores else 0,
            "min_score": min(scores) if scores else 0,
            "by_category": category_stats,
        }

    def _console_report(self):
        """控制台报告"""
        stats = self._compute_stats()
        print("=" * 60)
        print(f"📊 评估报告 — {self.metadata.get('agent', {}).get('name', 'unknown')}")
        print("=" * 60)
        print(f"测试时间: {self.metadata.get('started_at', '')[:19]}")
        print(f"执行耗时: {self.metadata.get('duration', 0):.1f}s")
        print()
        print(f"总用例数:    {stats['total']}")
        print(f"通过:        {stats['passed']} ✅")
        print(f"失败:        {stats['failed']} ❌")
        print(f"通过率:      {stats['pass_rate']:.1%}")
        print(f"平均得分:    {stats['avg_score']:.2f}")
        print(f"最高得分:    {stats['max_score']:.2f}")
        print(f"最低得分:    {stats['min_score']:.2f}")
        print()
        print("📂 按类别：")
        for cat, s in sorted(stats["by_category"].items()):
            bar = "█" * int(s["pass_rate"] * 20) + "░" * (20 - int(s["pass_rate"] * 20))
            print(f"  {cat:16s} [{bar}] {s['passed']}/{s['total']} ({s['pass_rate']:.0%})")

        print()
        failures = [r for r in self.results if not r.passed]
        if failures:
            print(f"❌ 失败详情 ({len(failures)} 个)：")
            tc_map = {tc.id: tc for tc in self.test_cases}
            for r in failures[:5]:
                tc = tc_map.get(r.test_case_id)
                print(f"  [{r.test_case_id}] {tc.input if tc else '?'} → 得分: {r.score:.2f}")
                if r.error:
                    print(f"    错误: {r.error}")
            if len(failures) > 5:
                print(f"  ... 还有 {len(failures) - 5} 个失败")

        print("=" * 60)

    def _json_report(self) -> str:
        """JSON 报告"""
        stats = self._compute_stats()
        report = {
            "metadata": self.metadata,
            "stats": stats,
            "results": [r.to_dict() for r in self.results],
        }
        return json.dumps(report, ensure_ascii=False, indent=2)

    def _markdown_report(self) -> str:
        """Markdown 报告"""
        stats = self._compute_stats()
        agent_name = self.metadata.get("agent", {}).get("name", "unknown")
        lines = [
            f"# 📊 评估报告: {agent_name}",
            f"",
            f"- **时间**: {self.metadata.get('started_at', '')[:19]}",
            f"- **耗时**: {self.metadata.get('duration', 0):.1f}s",
            f"- **用例数**: {stats['total']}",
            f"",
            f"## 总体统计",
            f"",
            f"| 指标 | 值 |",
            f"|------|-----|",
            f"| 通过率 | {stats['pass_rate']:.1%} |",
            f"| 平均分 | {stats['avg_score']:.2f} |",
            f"| 最高分 | {stats['max_score']:.2f} |",
            f"| 最低分 | {stats['min_score']:.2f} |",
            f"",
            f"## 按类别",
            f"",
            f"| 类别 | 通过率 | 平均分 |",
            f"|------|--------|--------|",
        ]
        for cat, s in sorted(stats["by_category"].items()):
            lines.append(f"| {cat} | {s['pass_rate']:.0%} | {s['avg_score']:.2f} |")

        lines.extend([
            f"",
            f"## 详细信息",
            f"",
            f"| 用例 | 结果 | 得分 | 详情 |",
            f"|------|------|------|------|",
        ])
        tc_map = {tc.id: tc for tc in self.test_cases}
        for r in self.results:
            tc = tc_map.get(r.test_case_id)
            status = "✅" if r.passed else "❌"
            inp = tc.input[:30] if tc else r.test_case_id
            lines.append(f"| {inp} | {status} | {r.score:.2f} | {r.details[:40]} |")

        lines.append("")
        return "\n".join(lines)

    # ============================================================
    # 6. 对比实验（A/B Testing）
    # ============================================================

    @staticmethod
    def compare(pipeline_a: "EvalPipeline", pipeline_b: "EvalPipeline",
                verbose: bool = True) -> dict:
        """对比两个 Agent 版本的评估结果"""
        stats_a = pipeline_a._compute_stats()
        stats_b = pipeline_b._compute_stats()

        comparison = {
            "agent_a": pipeline_a.metadata.get("agent", {}),
            "agent_b": pipeline_b.metadata.get("agent", {}),
            "a": stats_a,
            "b": stats_b,
            "diff": {
                "pass_rate": stats_b["pass_rate"] - stats_a["pass_rate"],
                "avg_score": stats_b["avg_score"] - stats_a["avg_score"],
            },
            "winner": "A" if stats_a["pass_rate"] >= stats_b["pass_rate"] else "B",
        }

        if verbose:
            name_a = comparison["agent_a"].get("name", "A")
            name_b = comparison["agent_b"].get("name", "B")
            print(f"\n📊 A/B 对比: {name_a} vs {name_b}")
            print("=" * 60)
            print(f"{'指标':20s} {name_a:15s} {name_b:15s} {'变化':10s}")
            print("-" * 60)
            print(f"{'通过率':20s} {stats_a['pass_rate']:10.1%}  {stats_b['pass_rate']:10.1%}  "
                  f"{comparison['diff']['pass_rate']:+7.1%}")
            print(f"{'平均分':20s} {stats_a['avg_score']:10.2f}  {stats_b['avg_score']:10.2f}  "
                  f"{comparison['diff']['avg_score']:+7.2f}")
            print(f"{'总用例':20s} {stats_a['total']:>10d}  {stats_b['total']:>10d}")
            print("-" * 60)
            winner = comparison['winner']
            print(f"🏆 胜出: {name_a if winner == 'A' else name_b}")
            print("=" * 60)

        return comparison


# ============================================================
# 7. 演示运行
# ============================================================

def main():
    print("🧪 Agent 评估系统 — Step 3: 完整评估 Pipeline\n")

    # 加载测试用例
    test_cases = load_test_cases("test_cases.json")

    # ---- 测试 v1 ----
    print("=" * 60)
    print("🔵 Agent v1 评估")
    print("=" * 60)
    agent_v1 = MockAgent(name="MockAgent-v1", error_rate=0.2)
    pipeline_v1 = EvalPipeline(
        agent=agent_v1,
        test_cases=test_cases,
        cache_dir=".eval_cache",
    ).run(verbose=True)
    pipeline_v1.generate_report(format="console")

    # ---- 测试 v2 ----
    print("\n" + "=" * 60)
    print("🟢 Agent v2 评估")
    print("=" * 60)
    agent_v2 = BetterMockAgent(name="MockAgent-v2")
    pipeline_v2 = EvalPipeline(
        agent=agent_v2,
        test_cases=test_cases,
        cache_dir=".eval_cache",
    ).run(verbose=True)
    pipeline_v2.generate_report(format="console")

    # ---- 对比 ----
    EvalPipeline.compare(pipeline_v1, pipeline_v2)

    # ---- 导出 Markdown 报告 ----
    md_report = pipeline_v2.generate_report(format="markdown")
    report_path = "eval_report_results.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"\n📄 Markdown 报告已保存: {report_path}")


if __name__ == "__main__":
    main()
