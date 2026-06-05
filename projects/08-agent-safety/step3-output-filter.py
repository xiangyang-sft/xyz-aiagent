"""
step3-output-filter.py — 输出审核 Pipeline + 敏感信息检测

功能：
1. 规则过滤（敏感词、正则、Pattern 匹配）
2. LLM 语义审核（用规则模拟 LLM-as-Judge）
3. PII 检测（手机号、邮箱、身份证、API Key）
4. 三层输出审核 Pipeline

运行：python step3-output-filter.py
"""

import re
import json
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# 第 1 层：规则过滤器
# ============================================================

@dataclass
class FilterResult:
    passed: bool
    layer: str
    issues: list[str] = field(default_factory=list)
    redacted_text: Optional[str] = None


class RuleFilter:
    """
    第 1 层：快速规则过滤
    基于正则和关键词的高速检测
    """

    # PII 正则模式
    PII_PATTERNS = {
        "手机号": (r"1[3-9]\d{9}", "替换为 [手机号已脱敏]"),
        "邮箱": (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "替换为 [邮箱已脱敏]"),
        "身份证号": (r"\d{17}[\dXx]", "替换为 [身份证已脱敏]"),
        "银行卡号": (r"\d{16,19}", "替换为 [银行卡已脱敏]"),
        "IP 地址": (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "替换为 [IP已脱敏]"),
    }

    # API Key / Token 模式
    SECRET_PATTERNS = {
        "API Key": (r"(?i)(api[_-]?key|apikey|secret|token)[\s:=]+['\"]?[a-zA-Z0-9_\-]{16,}",
                    "替换为 [密钥已脱敏]"),
        "SSH Key": (r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
                    "替换为 [SSH密钥已脱敏]"),
    }

    # 有害内容关键词
    HARMFUL_KEYWORDS = [
        "自杀", "自残", "制作武器", "毒品", "暴力",
        "suicide", "self-harm", "weapon", "bomb",
    ]

    def __init__(self):
        self._compiled_patterns = {}
        for name, (pattern, _) in {**self.PII_PATTERNS, **self.SECRET_PATTERNS}.items():
            self._compiled_patterns[name] = re.compile(pattern)

    def filter(self, text: str) -> FilterResult:
        """对输出文本进行规则过滤"""
        issues = []

        # 1. 检查有害内容
        for kw in self.HARMFUL_KEYWORDS:
            if kw.lower() in text.lower():
                issues.append(f"检测到潜在有害关键词：'{kw}'")

        # 2. 检查并脱敏 PII
        redacted = text
        for name, (pattern, replacement) in self.PII_PATTERNS.items():
            matches = re.findall(pattern, redacted)
            if matches:
                issues.append(f"检测到 {len(matches)} 处{name}")
                redacted = re.sub(pattern, replacement, redacted)

        # 3. 检查密钥
        for name, (pattern, replacement) in self.SECRET_PATTERNS.items():
            if re.search(pattern, redacted):
                issues.append(f"检测到{name}")
                redacted = re.sub(pattern, replacement, redacted)

        return FilterResult(
            passed=len(issues) == 0,
            layer="rule_filter",
            issues=issues,
            redacted_text=redacted if issues else None,
        )


# ============================================================
# 第 2 层：语义审核器（LLM-as-Judge 模拟）
# ============================================================

class SemanticGuard:
    """
    第 2 层：语义审核
    用 LLM 检测更深层次的危害
    这里用规则模拟 LLM 审核行为
    """

    # 需要 LLM 判断的隐式危害
    IMPLICIT_HARMFUL_PATTERNS = [
        {
            "name": "诱导信息泄露",
            "pattern": r"(密码|passwd|密码是|密码为|我的密码)",
            "risk": "Agent 不应输出密码或敏感凭据信息",
        },
        {
            "name": "系统配置泄露",
            "pattern": r"(服务器地址|数据库连接|connection[_\s]string|jdbc:|mongodb://|redis://)",
            "risk": "Agent 不应暴露系统内部配置",
        },
        {
            "name": "编造引文",
            "pattern": r"(据研究|研究表明|论文指出)[^。]{50,}(未找到|无法验证)",
            "risk": "Agent 可能编造了不存在的引用来源",
        },
        {
            "name": "越权承诺",
            "pattern": r"(保证|承诺|100%|绝对|肯定)[^。]{0,20}(成功|有效|安全)",
            "risk": "Agent 不应做出无法保证的绝对承诺",
        },
    ]

    def review(self, text: str) -> FilterResult:
        """语义审核"""
        issues = []

        for pattern in self.IMPLICIT_HARMFUL_PATTERNS:
            if re.search(pattern["pattern"], text, re.IGNORECASE):
                issues.append(f"潜在风险：{pattern['name']} — {pattern['risk']}")

        return FilterResult(
            passed=len(issues) == 0,
            layer="semantic_guard",
            issues=issues,
        )


# ============================================================
# 完整输出审核 Pipeline
# ============================================================

class OutputFilterPipeline:
    """
    三层输出审核 Pipeline
    Layer 1: 规则过滤（快速）
    Layer 2: 语义审核（深入）
    Layer 3: 人工审核（高风险）（模拟）
    """

    def __init__(self):
        self.rule_filter = RuleFilter()
        self.semantic_guard = SemanticGuard()
        self.stats = {"total": 0, "blocked": 0, "warned": 0, "passed": 0}

    def review(self, text: str, context: Optional[dict] = None) -> dict:
        """
        执行完整审核流程
        返回审核结果和脱敏版本
        """
        self.stats["total"] += 1
        warnings = []

        # Layer 1: 规则过滤
        layer1_result = self.rule_filter.filter(text)
        if not layer1_result.passed:
            warnings.extend(layer1_result.issues)

        # 获取脱敏后的文本（如果有）
        safe_text = layer1_result.redacted_text or text

        # Layer 2: 语义审核
        layer2_result = self.semantic_guard.review(safe_text)
        if not layer2_result.passed:
            warnings.extend(layer2_result.issues)

        # 决策
        result = {
            "original_length": len(text),
            "safe_length": len(safe_text),
            "warnings": warnings,
            "safe_text": safe_text,
            "redacted": layer1_result.redacted_text is not None,
        }

        if len(warnings) >= 2:
            result["verdict"] = "blocked"
            result["message"] = "⛔ 输出被拦截：检测到多个安全问题"
            self.stats["blocked"] += 1
        elif len(warnings) > 0:
            result["verdict"] = "warning"
            result["message"] = "⚠️ 输出含警告（已脱敏处理）"
            self.stats["warned"] += 1
        else:
            result["verdict"] = "passed"
            result["message"] = "✅ 输出审核通过"
            self.stats["passed"] += 1

        return result


# ============================================================
# 演示
# ============================================================

def demo():
    print("=" * 60)
    print("🔍 输出审核 Pipeline 演示")
    print("=" * 60)

    pipeline = OutputFilterPipeline()

    test_cases = [
        {
            "name": "正常输出",
            "text": "昨天的销售额为 ¥128,000，较上周增长 5.2%。建议继续关注 A 产品的销售表现。",
        },
        {
            "name": "含手机号（需脱敏）",
            "text": "用户信息已查找到，手机号是 13812345678，请联系该用户。",
        },
        {
            "name": "含邮箱 + API Key（严重）",
            "text": "请将报告发送到 admin@company.com。数据库连接信息：api_key=sk-proj-abcdef1234567890abcdef1234567890abcdef12",
        },
        {
            "name": "有害内容",
            "text": "制作简易武器的方法如下：第一步...（这里省略具体内容）",
        },
        {
            "name": "系统配置泄露",
            "text": "数据库连接信息：jdbc:mysql://internal-db:3306/production?user=admin&password=secret123",
        },
        {
            "name": "诱导弹出（安全）",
            "text": "推荐你设置一个强密码，建议包含大小写字母和特殊字符。",
        },
    ]

    for case in test_cases:
        print(f"\n{'─' * 60}")
        print(f"📌 场景：{case['name']}")
        print(f"  原始文本：{case['text'][:70]}...")
        print()

        result = pipeline.review(case["text"])

        print(f"  裁定：{result['message']}")
        if result["warnings"]:
            print(f"  警告详情：")
            for w in result["warnings"]:
                print(f"    • {w}")
        if result["redacted"]:
            print(f"  脱敏版本：{result['safe_text'][:80]}...")
        print()

    # 统计
    print("=" * 60)
    print("📊 审核统计")
    print("=" * 60)
    print(f"  审核总数：{pipeline.stats['total']}")
    print(f"  ✅ 通过：{pipeline.stats['passed']}")
    print(f"  ⚠️ 警告（已脱敏）：{pipeline.stats['warned']}")
    print(f"  ⛔ 拦截：{pipeline.stats['blocked']}")


def demo_pii_detector():
    """PII 检测器专项演示"""
    print("\n" + "=" * 60)
    print("📌 专项演示：PII 检测与脱敏")
    print("=" * 60)

    filter = RuleFilter()

    test_texts = [
        "我的手机是 13912345678",
        "邮箱 contact@example.com",
        "身份证 110101199001011234",
        "API 密钥是 sk-proj-abc123def456",
        "服务器 IP 是 192.168.1.1",
        "SSH 私钥：-----BEGIN RSA PRIVATE KEY-----",
    ]

    for text in test_texts:
        result = filter.filter(text)
        if result.passed:
            print(f"  ✅ 通过：{text}")
        else:
            redacted = result.redacted_text or text
            print(f"  ⚠️ 含敏感信息：{text}")
            for issue in result.issues:
                print(f"       → {issue}")


if __name__ == "__main__":
    demo()
    demo_pii_detector()

    print("\n" + "=" * 60)
    print("📝 关键总结")
    print("=" * 60)
    print("""
1️⃣ Layer 1（规则过滤）：快速检测 PII、密钥、有害关键词
   优点：高速、低误报   缺点：无法检测隐式危害

2️⃣ Layer 2（语义审核）：检测隐式风险
   优点：能发现深层危害   缺点：慢、有误报

3️⃣ 输出安全策略：
   - 能脱敏的不要拦截（手机号、邮箱 → 替换为占位符）
   - 多个问题同时出现时拦截（可能是有意攻击）
   - 所有审核决策都记录到审计日志
""")
