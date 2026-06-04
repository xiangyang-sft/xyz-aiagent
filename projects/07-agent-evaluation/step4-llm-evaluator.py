"""
Step 4: LLM-as-Judge 自动评估
===============================
功能：用 LLM 评估 Agent 输出、多维度打分、校准机制、失败案例分析
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple


# ============================================================
# 1. LLM Judge 客户端接口
# ============================================================

class LLMClient:
    """LLM API 客户端（适配不同模型）"""

    def __init__(self, provider: str = "openai", model: str = "gpt-3.5-turbo",
                 api_key: Optional[str] = None):
        self.provider = provider
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "sk-demo")
        # 注意：实际使用请配置真实 API Key

    def chat(self, messages: List[dict], temperature: float = 0.0) -> str:
        """
        调用 LLM API
        生产环境请使用 OpenAI / Anthropic / 本地模型 API
        """
        # ============ 模拟实现（演示用）============
        last_message = messages[-1]["content"] if messages else ""

        if "准确性" in last_message and "完整性" in last_message:
            # 模拟评估打分
            return json.dumps({
                "accuracy": 4,
                "completeness": 3,
                "tool_usage": 4,
                "efficiency": 3,
                "overall_score": 3.5,
                "strengths": "回答结构清晰，信息完整",
                "weaknesses": "可以更简洁",
                "suggestions": "精简不必要的描述",
            }, ensure_ascii=False)
        elif "是否包含" in last_message:
            return json.dumps({
                "contains_info": True,
                "confidence": 0.85,
            })
        elif "谁更好" in last_message:
            return json.dumps({
                "winner": "A",
                "reason": "Agent A 的回答更准确、更简洁",
                "scores": {"A": 4.5, "B": 3.0},
            })
        else:
            return "模拟评估结果：输出质量较好。"


# ============================================================
# 2. 评估维度定义
# ============================================================

@dataclass
class EvalDimension:
    """评估维度"""
    name: str           # 维度名称
    description: str    # 维度描述
    weight: float = 1.0  # 权重
    min_score: int = 1
    max_score: int = 5


DEFAULT_DIMENSIONS = [
    EvalDimension(
        name="accuracy",
        description="回答的准确性：信息是否正确，是否有事实错误或幻觉",
        weight=1.5,
    ),
    EvalDimension(
        name="completeness",
        description="回答的完整性：是否覆盖了用户所有需求",
        weight=1.2,
    ),
    EvalDimension(
        name="tool_usage",
        description="工具使用：是否正确选择和使用工具",
        weight=1.0,
    ),
    EvalDimension(
        name="efficiency",
        description="效率：是否用最少的步骤完成，是否简洁",
        weight=0.8,
    ),
    EvalDimension(
        name="helpfulness",
        description="有帮助性：回答是否对用户有用",
        weight=1.0,
    ),
]


# ============================================================
# 3. LLM-as-Judge 评估器
# ============================================================

class LLMJudge:
    """
    LLM-as-Judge 评估器
    使用 LLM 来评估 LLM 的输出质量
    """

    def __init__(self, client: Optional[LLMClient] = None,
                 dimensions: Optional[List[EvalDimension]] = None,
                 judge_model: str = "gpt-4"):
        self.client = client or LLMClient(model=judge_model)
        self.dimensions = dimensions or DEFAULT_DIMENSIONS
        self.judge_model = judge_model
        self.judge_count = 0
        self.total_cost = 0.0

    def _build_eval_prompt(self, user_input: str, agent_output: str,
                           reference: str = "") -> str:
        """构建评估 Prompt"""

        dims_text = "\n".join([
            f"{i+1}. {d.name}（{d.description}，评分范围 {d.min_score}-{d.max_score}）"
            for i, d in enumerate(self.dimensions)
        ])

        dimension_names = [d.name for d in self.dimensions]
        score_keys = ", ".join([f'"{n}"' for n in dimension_names])

        prompt = f"""你是一个专业的 AI Agent 评估专家。请评估以下 Agent 的输出质量。

## 用户请求
{user_input}

## Agent 输出
{agent_output}
"""
        if reference:
            prompt += f"""
## 参考回答（期望输出）
{reference}
"""

        prompt += f"""
## 评估维度
{dims_text}

## 评分标准
- {self.dimensions[0].max_score} 分：完美 —— 完全正确，无任何问题
- 4 分：良好 —— 基本正确，有小瑕疵
- 3 分：一般 —— 部分正确，有改进空间
- 2 分：较差 —— 存在明显问题
- 1 分：很差 —— 几乎完全错误

## 输出格式
请严格以 JSON 格式输出评估结果，不要包含其他内容：
{{
    {score_keys},
    "overall_score": <综合评分>,
    "strengths": "<主要优点>",
    "weaknesses": "<主要缺点>",
    "suggestions": "<改进建议>"
}}

每个维度和综合评分使用 1-5 分制。"""
        return prompt

    def evaluate(self, user_input: str, agent_output: str,
                 reference: str = "", temperature: float = 0.0,
                 num_samples: int = 1) -> dict:
        """
        对单个 Agent 输出进行评估

        Args:
            user_input: 用户输入
            agent_output: Agent 输出
            reference: 参考回答（可选）
            temperature: 评估温度（0=确定性）
            num_samples: 采样次数（用于取平均，减少随机性）

        Returns:
            评估结果字典
        """
        prompt = self._build_eval_prompt(user_input, agent_output, reference)

        scores = []
        for _ in range(num_samples):
            try:
                response = self.client.chat(
                    messages=[
                        {"role": "system", "content": "你是一个客观的 AI 评估专家。"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=temperature,
                )
                result = self._parse_response(response)
                scores.append(result)
                self.judge_count += 1
            except Exception as e:
                print(f"  ⚠️ LLM Judge 评估失败: {e}")
                continue

        if not scores:
            return {"error": "全部评估失败", "overall_score": 0}

        # 多次评估取平均
        return self._aggregate_scores(scores)

    def _parse_response(self, response: str) -> dict:
        """解析 LLM 的 JSON 响应"""
        # 尝试提取 JSON
        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            try:
                result = json.loads(json_str)
                # 确保所有维度都存在
                dim_names = [d.name for d in self.dimensions]
                for name in dim_names:
                    if name not in result:
                        result[name] = 3  # 默认中等分
                if "overall_score" not in result:
                    vals = [result.get(n, 3) for n in dim_names]
                    result["overall_score"] = sum(vals) / len(vals)
                return result
            except json.JSONDecodeError:
                pass

        # 失败时返回默认值
        return {
            **{d.name: 3 for d in self.dimensions},
            "overall_score": 3.0,
            "strengths": "解析失败",
            "weaknesses": "解析失败",
            "suggestions": "无法解析评估结果",
        }

    def _aggregate_scores(self, scores: List[dict]) -> dict:
        """汇总多次评估结果"""
        dim_names = [d.name for d in self.dimensions]
        aggregated = {}

        # 各维度取平均
        for name in dim_names:
            vals = [s.get(name, 3) for s in scores]
            aggregated[name] = sum(vals) / len(vals)

        # 综合评分取平均
        overalls = [s.get("overall_score", 3) for s in scores]
        aggregated["overall_score"] = sum(overalls) / len(overalls)

        # 加权评分
        total_weight = sum(d.weight for d in self.dimensions)
        weighted = sum(
            aggregated[d.name] * d.weight for d in self.dimensions
        ) / total_weight
        aggregated["weighted_score"] = weighted

        # 取最常见的优缺点
        strengths = [s.get("strengths", "") for s in scores if s.get("strengths")]
        weaknesses = [s.get("weaknesses", "") for s in scores if s.get("weaknesses")]
        aggregated["strengths"] = max(set(strengths), key=strengths.count) if strengths else ""
        aggregated["weaknesses"] = max(set(weaknesses), key=weaknesses.count) if weaknesses else ""
        aggregated["samples"] = len(scores)

        return aggregated

    def batch_evaluate(self, cases: List[dict]) -> List[dict]:
        """批量评估"""
        results = []
        for i, case in enumerate(cases):
            print(f"  [{i+1}/{len(cases)}] 评估中...", end=" ")
            result = self.evaluate(
                user_input=case["input"],
                agent_output=case["output"],
                reference=case.get("reference", ""),
            )
            result["input"] = case["input"]
            result["output"] = case["output"]
            results.append(result)
            print(f"得分: {result.get('overall_score', 0):.1f}")
        return results


# ============================================================
# 4. 校准机制
# ============================================================

class JudgeCalibrator:
    """
    LLM Judge 校准器
    将 LLM Judge 的评分对齐到人工评分标准
    """

    def __init__(self):
        self.calibration_data: List[dict] = []
        self.bias: float = 0.0
        self.scale_factor: float = 1.0

    def add_calibration_point(self, llm_score: float, human_score: float):
        """添加校准点（LLM评分, 人工评分）"""
        self.calibration_data.append({
            "llm_score": llm_score,
            "human_score": human_score,
        })
        self._recalibrate()

    def _recalibrate(self):
        """计算校准参数（线性回归）"""
        if len(self.calibration_data) < 2:
            return

        llm_scores = [d["llm_score"] for d in self.calibration_data]
        human_scores = [d["human_score"] for d in self.calibration_data]

        n = len(llm_scores)
        sum_x = sum(llm_scores)
        sum_y = sum(human_scores)
        sum_xy = sum(x * y for x, y in zip(llm_scores, human_scores))
        sum_xx = sum(x ** 2 for x in llm_scores)

        # y = ax + b
        denominator = n * sum_xx - sum_x ** 2
        if denominator == 0:
            return

        self.scale_factor = (n * sum_xy - sum_x * sum_y) / denominator
        self.bias = (sum_y - self.scale_factor * sum_x) / n

    def calibrate(self, llm_score: float) -> float:
        """校准 LLM 评分"""
        calibrated = self.scale_factor * llm_score + self.bias
        return max(1.0, min(5.0, calibrated))  # 限制在 1-5 分

    def report(self) -> dict:
        """校准报告"""
        if not self.calibration_data:
            return {"status": "无校准数据"}

        mae_before = sum(
            abs(d["llm_score"] - d["human_score"])
            for d in self.calibration_data
        ) / len(self.calibration_data)

        mae_after = sum(
            abs(self.calibrate(d["llm_score"]) - d["human_score"])
            for d in self.calibration_data
        ) / len(self.calibration_data)

        return {
            "校准点数": len(self.calibration_data),
            "校准前 MAE": f"{mae_before:.3f}",
            "校准后 MAE": f"{mae_after:.3f}",
            "scale_factor": f"{self.scale_factor:.3f}",
            "bias": f"{self.bias:.3f}",
        }


# ============================================================
# 5. 失败案例分类器
# ============================================================

class FailureClassifier:
    """失败案例自动分类"""

    def __init__(self):
        self.categories = {
            "hallucination": "幻觉",
            "incomplete": "不完整",
            "wrong_tool": "工具选择错误",
            "incorrect": "回答错误",
            "refusal": "不合理拒绝",
            "verbose": "过于冗长",
            "off_topic": "偏离主题",
            "other": "其他",
        }

    def classify(self, user_input: str, agent_output: str,
                 eval_result: dict) -> str:
        """自动分类失败原因"""
        output_lower = agent_output.lower()
        score = eval_result.get("accuracy", 3)

        # 精确率低的可能原因
        if score <= 2 and len(agent_output) < 20:
            return "refusal"
        elif score <= 2 and len(agent_output) > 500:
            return "verbose"
        elif eval_result.get("completeness", 3) <= 2:
            return "incomplete"
        elif eval_result.get("helpfulness", 3) <= 2:
            return "off_topic"
        elif score <= 2:
            return "incorrect"

        return "other"

    def get_report(self, classifications: List[Tuple[str, str, str]]) -> dict:
        """生成分类统计报告"""
        cat_counts = {v: 0 for v in self.categories.values()}
        total = len(classifications)

        for _, _, cat in classifications:
            if cat in cat_counts:
                cat_counts[cat] += 1

        return {
            "total": total,
            "distribution": {
                cat: {"count": count, "ratio": count / max(total, 1)}
                for cat, count in sorted(
                    cat_counts.items(), key=lambda x: -x[1]
                )
            },
        }


# ============================================================
# 6. 评估日志与可视化
# ============================================================

class EvalLogger:
    """评估日志记录器"""

    def __init__(self, log_dir: str = "eval_logs"):
        self.log_dir = log_dir
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.logs: List[dict] = []

    def log(self, entry: dict):
        """记录一条评估日志"""
        entry["timestamp"] = datetime.now().isoformat()
        self.logs.append(entry)

    def save(self):
        """保存日志到文件"""
        import os
        os.makedirs(self.log_dir, exist_ok=True)
        path = os.path.join(self.log_dir, f"eval_{self.session_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "session_id": self.session_id,
                "entries": self.logs,
            }, f, ensure_ascii=False, indent=2)
        print(f"📝 日志已保存: {path}")
        return path

    def summary(self) -> dict:
        """生成日志摘要"""
        if not self.logs:
            return {}
        scores = [e.get("overall_score", 0) for e in self.logs
                  if "overall_score" in e]
        return {
            "总评估次数": len(self.logs),
            "平均分": sum(scores) / max(len(scores), 1),
            "最高分": max(scores) if scores else 0,
            "最低分": min(scores) if scores else 0,
        }


# ============================================================
# 7. 演示运行
# ============================================================

def main():
    print("🧪 Agent 评估系统 — Step 4: LLM-as-Judge 自动评估\n")

    # 初始化
    judge = LLMJudge(judge_model="gpt-4")
    calibrator = JudgeCalibrator()
    classifier = FailureClassifier()
    logger = EvalLogger()

    # 测试用例
    test_cases = [
        {
            "input": "今天北京的天气怎么样？",
            "output": "根据天气预报，今天北京天气晴朗，气温25°C，空气质量良好，适合外出活动。",
            "reference": "北京天气晴朗，25°C",
        },
        {
            "input": "帮我计算 15 + 27 等于多少？",
            "output": "15 + 27 = 42。这是一个简单的加法运算。",
            "reference": "42",
        },
        {
            "input": "解释一下什么是 RAG？",
            "output": "RAG 是检索增强生成（Retrieval-Augmented Generation）的缩写。\n"
                     "它是一种结合信息检索和文本生成的技术。\n"
                     "流程：用户查询→检索相关文档→将文档作为上下文→LLM生成回答",
            "reference": "RAG 是检索增强生成，结合检索和生成",
        },
        {
            "input": "帮我写一封辞职信",
            "output": "抱歉，我无法帮你写辞职信。",
            "reference": "尊敬的领导，感谢您这段时间的栽培...",
        },
        {
            "input": "Python 中如何读取 JSON 文件？",
            "output": "使用 json.load() 或 json.loads()。\n"
                     "Python 有非常长的历史，最初由 Guido van Rossum 在 1989 年创建，\n"
                     "Python 被广泛用于 Web 开发、数据科学、AI 等领域。\n"
                     "它不仅语法简洁，还有丰富的标准库和第三方库支持。",
            "reference": "import json; with open('file.json') as f: data = json.load(f)",
        },
    ]

    # 运行评估
    print("📝 开始 LLM-as-Judge 评估\n")

    for i, case in enumerate(test_cases, 1):
        print(f"[{i}/{len(test_cases)}] 输入: {case['input'][:30]}...")

        result = judge.evaluate(
            user_input=case["input"],
            agent_output=case["output"],
            reference=case.get("reference", ""),
        )

        if "error" in result:
            print(f"  ❌ 评估失败: {result['error']}\n")
            continue

        overall = result["overall_score"]
        weighted = result.get("weighted_score", overall)
        status = "✅" if overall >= 3.5 else "⚠️" if overall >= 2.5 else "❌"

        print(f"  {status} 综合: {overall:.1f} | 加权: {weighted:.1f}")
        for dim in [d.name for d in judge.dimensions]:
            bar = "█" * int(result.get(dim, 3)) + "░" * (5 - int(result.get(dim, 3)))
            print(f"    {dim:15s} [{bar}] {result.get(dim, 3):.1f}")
        if result.get("weaknesses"):
            print(f"    💡 缺点: {result['weaknesses']}")
        if result.get("strengths"):
            print(f"    ⭐ 优点: {result['strengths']}")

        # 失败分类
        cat = classifier.classify(case["input"], case["output"], result)
        cat_name = classifier.categories.get(cat, "其他")
        print(f"    🏷️ 分类: {cat_name}")

        # 校准演示
        if overall < 3.5:
            calibrator.add_calibration_point(overall, overall + 0.5)
            calibrated = calibrator.calibrate(overall)
            print(f"    🔄 校准后: {calibrated:.1f}")

        # 记录日志
        logger.log({
            "input": case["input"],
            "output": case["output"],
            **result,
            "category": cat,
        })
        print()

    # 校准报告
    print("=" * 60)
    print("📊 校准报告")
    print("=" * 60)
    cal_report = calibrator.report()
    if cal_report.get("status") != "无校准数据":
        for k, v in cal_report.items():
            print(f"  {k}: {v}")
    print()

    # 失败分类统计
    class_data = [
        (c["input"], c["output"], c.get("category", "other"))
        for c in logger.logs
    ]
    class_report = classifier.get_report(class_data)
    print("📂 失败分类分布：")
    for cat, stats in class_report["distribution"].items():
        bar = "█" * int(stats["ratio"] * 20)
        print(f"  {cat:12s}: {bar} {stats['count']} ({stats['ratio']:.0%})")
    print()

    # 日志摘要
    print("📋 本次评估会话摘要：")
    for k, v in logger.summary().items():
        print(f"  {k}: {v}")

    # 保存日志
    logger.save()
    print(f"\n  LLM Judge 调用次数: {judge.judge_count}")


if __name__ == "__main__":
    main()
