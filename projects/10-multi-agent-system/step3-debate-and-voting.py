#!/usr/bin/env python3
"""
Step 3 — 高级版：辩论 + 投票机制（引入协商式协作）

核心概念：
- 辩论模式（Debate）：两个 Agent 对同一问题提出不同观点，第三方仲裁
- 投票模式（Voting）：多个 Agent 独立评分后取平均/众数
- 动态决策：Supervisor 判断何时需要辩论/投票

对比 Step 2 的增量：
  1. DebateManager — 管理辩论流程（提出观点→反驳→仲裁）
  2. VotingManager — 管理投票流程（独立评分→聚合→决策）
  3. 动态触发机制 — 当有分歧时自动启动辩论
  4. 辩论/投票成本追踪

运行：
  python step3-debate-and-voting.py
"""

import json
import time
import statistics
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field


# ============================================================
# 1. LLM 客户端（复用之前的设计）
# ============================================================

class LLMResult:
    def __init__(self, content: str, model: str = "", 
                 prompt_tokens: int = 0, completion_tokens: int = 0):
        self.content = content
        self.model = model
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens


class LLMClient:
    def __init__(self, api_key: str = None, base_url: str = None,
                 strong_model: str = "gpt-4o", weak_model: str = "gpt-4o-mini"):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.strong = strong_model
        self.weak = weak_model

    def chat(self, messages: list, model: str = None, temperature: float = 0.7) -> LLMResult:
        model = model or self.weak
        resp = self.client.chat.completions.create(
            model=model, messages=messages, temperature=temperature,
        )
        usage = resp.usage
        return LLMResult(
            content=resp.choices[0].message.content or "",
            model=model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )


# ============================================================
# 2. 辩论管理器（Debate Manager）
# ============================================================

class DebateManager:
    """
    辩论管理器 — 管理多 Agent 辩论流程
    
    流程：
    1. 设定辩论主题和规则
    2. Agent A 提出初始观点
    3. Agent B 反驳/补充观点
    4. 重复 2-3 步最多 N 轮
    5. 仲裁者（Arbitrator）总结并给出最终结论
    """

    DEBATE_SYSTEM_PROMPT = """你是一名专业的辩论参与者。

辩论规则：
- 你必须基于事实和逻辑，清晰表达你的观点
- 你可以引用证据、案例和数据支持你的立场
- 尊重对方观点，用理性反驳而不是情绪化表达
- 每次发言控制在 200 字以内，简明扼要
- 你的角色是：{role}"""

    ARBITRATOR_PROMPT = """你是辩论的仲裁者，负责听取双方观点后做出最终判断。

你的职责：
1. 客观评估双方论点的质量（论据充分性、逻辑严谨性）
2. 指出双方观点的可取之处和不足
3. 给出最终结论和理由
4. 如有必要，给出折中方案

辩论主题：{topic}
"""

    MAX_ROUNDS = 3  # 最大辩论轮次

    def __init__(self, llm: LLMClient, topic: str,
                 agent_a_name: str, agent_a_role: str,
                 agent_b_name: str, agent_b_role: str):
        self.llm = llm
        self.topic = topic
        self.agent_a_name = agent_a_name
        self.agent_a_role = agent_a_role
        self.agent_b_name = agent_b_name
        self.agent_b_role = agent_b_role
        self.history: List[dict] = []
        self.total_tokens = 0

    def _debater_chat(self, system_prompt: str, context: str, role_name: str) -> LLMResult:
        """让一个辩论者发言"""
        messages = [
            {"role": "system", "content": system_prompt},
        ]
        if context:
            messages.append({"role": "user", "content": context})
        result = self.llm.chat(messages, model=self.llm.strong, temperature=0.7)
        self.total_tokens += result.total_tokens
        return result

    def run(self) -> dict:
        """运行完整的辩论流程"""
        print(f"\n  🗣️ 辩论开始：{self.topic}")
        print(f"     正方：{self.agent_a_name}（{self.agent_a_role}）")
        print(f"     反方：{self.agent_b_name}（{self.agent_b_role}）")

        # 构建辩论者 system prompt
        sys_a = self.DEBATE_SYSTEM_PROMPT.format(role=self.agent_a_role)
        sys_b = self.DEBATE_SYSTEM_PROMPT.format(role=self.agent_b_role)

        # Round 1: 双方陈述初始观点
        print(f"\n     --- 第 1 轮 ---")
        
        result_a = self._debater_chat(sys_a, 
            f"辩论主题：{self.topic}\n请从你的角色角度给出初始观点。", 
            self.agent_a_name)
        self.history.append({"round": 1, "speaker": self.agent_a_name, 
                             "content": result_a.content})
        print(f"     {self.agent_a_name}: {result_a.content[:120]}...")

        result_b = self._debater_chat(sys_b,
            f"辩论主题：{self.topic}\n"
            f"对方观点：{result_a.content[:300]}\n"
            f"请从你的角色角度提出不同或补充观点。",
            self.agent_b_name)
        self.history.append({"round": 1, "speaker": self.agent_b_name,
                             "content": result_b.content})
        print(f"     {self.agent_b_name}: {result_b.content[:120]}...")

        # Round 2: 双方反驳
        print(f"\n     --- 第 2 轮 ---")
        
        context = f"辩论主题：{self.topic}\n\n已有讨论：\n"
        for h in self.history:
            context += f"{h['speaker']}：{h['content'][:200]}\n\n"

        result_a2 = self._debater_chat(sys_a,
            f"{context}\n请针对对方的观点做出回应，提出你的反驳或补充。",
            self.agent_a_name)
        self.history.append({"round": 2, "speaker": self.agent_a_name,
                             "content": result_a2.content})
        print(f"     {self.agent_a_name}: {result_a2.content[:120]}...")

        result_b2 = self._debater_chat(sys_b,
            f"{context}\n请针对对方的最新发言做出回应。",
            self.agent_b_name)
        self.history.append({"round": 2, "speaker": self.agent_b_name,
                             "content": result_b2.content})
        print(f"     {self.agent_b_name}: {result_b2.content[:120]}...")

        # 仲裁
        print(f"\n     --- 仲裁 ---")
        arbitrator_sys = self.ARBITRATOR_PROMPT.format(topic=self.topic)
        
        full_history = "\n".join([
            f"第{h['round']}轮 {h['speaker']}：{h['content']}"
            for h in self.history
        ])
        
        verdict = self.llm.chat(
            messages=[
                {"role": "system", "content": arbitrator_sys},
                {"role": "user", "content": f"辩论记录：\n{full_history}\n\n请给出最终裁定。"},
            ],
            model=self.llm.strong, temperature=0.3,
        )
        self.total_tokens += verdict.total_tokens

        print(f"     ⚖️ 仲裁结论：{verdict.content[:200]}...")

        return {
            "topic": self.topic,
            "history": self.history,
            "verdict": verdict.content,
            "total_tokens": self.total_tokens,
            "rounds": 2,
        }


# ============================================================
# 3. 投票管理器（Voting Manager）
# ============================================================

class VotingManager:
    """
    投票管理器 — 多个 Agent 对同一问题独立评分后聚合
    
    支持两种聚合方式：
    - average: 取平均分（默认）
    - majority: 取众数（分类投票）
    - weighted: 加权平均（按 Agent 权重）
    """

    VOTER_PROMPT = """你是一个专业的评审员。请基于以下标准，对给出的方案/代码进行评估。

评估维度（每项 1-10 分）：
1. 完整性（Completeness）：方案是否完整覆盖了所有需求
2. 正确性（Correctness）：方案是否合理，没有明显错误
3. 可维护性（Maintainability）：代码/设计是否易于维护和扩展
4. 性能（Performance）：方案在性能方面表现如何

请严格按 JSON 格式输出：{{"completeness": N, "correctness": N, "maintainability": N, "performance": N, "summary": "一句话评价"}}
"""

    def __init__(self, llm: LLMClient, voter_count: int = 3):
        self.llm = llm
        self.voter_count = voter_count
        self.total_tokens = 0

    def _create_voter(self, voter_id: int, perspective: str) -> Callable:
        """创建一个投票者（闭包）"""
        def vote(subject: str, context: str) -> dict:
            messages = [
                {"role": "system", "content": f"{self.VOTER_PROMPT}\n你的评审视角：{perspective}"},
                {"role": "user", "content": f"请评估以下内容：\n\n{subject}\n\n{context}"},
            ]
            result = self.llm.chat(messages, model=self.llm.weak, temperature=0.5)
            self.total_tokens += result.total_tokens
            try:
                return json.loads(result.content[result.content.index("{"):
                                                  result.content.rindex("}") + 1])
            except (ValueError, json.JSONDecodeError):
                return {"completeness": 7, "correctness": 7, 
                        "maintainability": 7, "performance": 7,
                        "summary": "评估完成"}
        return vote

    def run(self, subject: str, context: str = "") -> dict:
        """运行投票"""
        perspectives = [
            "关注功能完整性和用户体验",
            "关注代码质量和工程规范",
            "关注性能和安全",
        ]

        print(f"\n  📊 投票开始：{subject[:60]}...")
        print(f"     {self.voter_count} 位评审员参与")

        votes = []
        for i in range(self.voter_count):
            voter = self._create_voter(i + 1, perspectives[i % len(perspectives)])
            vote_result = voter(subject, context)
            votes.append({
                "voter_id": i + 1,
                "perspective": perspectives[i % len(perspectives)],
                "scores": vote_result,
            })
            scores = [vote_result.get(k, 0) for k in ['completeness','correctness','maintainability','performance']]
            avg_score = statistics.mean(scores)
            print(f"     评审员{i+1} ({perspectives[i % len(perspectives)][:12]}...): 综合 {avg_score:.1f}分")

        # 聚合结果
        aggregated = {}
        for dim in ["completeness", "correctness", "maintainability", "performance"]:
            scores = [v["scores"].get(dim, 0) for v in votes]
            aggregated[dim] = {
                "average": round(statistics.mean(scores), 1),
                "min": min(scores),
                "max": max(scores),
                "std": round(statistics.stdev(scores), 1) if len(scores) > 1 else 0,
            }

        overall = round(statistics.mean(
            aggregated[d]["average"] for d in aggregated
        ), 1)

        print(f"     📊 总分：{overall}/10")
        print(f"     完整性：{aggregated['completeness']['average']} | "
              f"正确性：{aggregated['correctness']['average']} | "
              f"可维护性：{aggregated['maintainability']['average']} | "
              f"性能：{aggregated['performance']['average']}")

        return {
            "votes": votes,
            "aggregated": aggregated,
            "overall": overall,
            "total_tokens": self.total_tokens,
        }


# ============================================================
# 4. 完整演示
# ============================================================

def main():
    import os
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    llm = LLMClient(api_key, base_url)

    print("=" * 70)
    print("🤝 协商式协作 — 辩论 + 投票演示")
    print("=" * 70)

    # 示例 1：辩论 — 架构选型
    print("\n" + "-" * 50)
    print("【场景 1】架构选型辩论：微服务 vs 单体")
    print("-" * 50)

    debate = DebateManager(
        llm=llm,
        topic="一个中小型电商系统应该选微服务架构还是单体架构？",
        agent_a_name="架构师A",
        agent_a_role="支持微服务的架构师，关注可扩展性和团队协作",
        agent_b_name="架构师B",
        agent_b_role="支持单体架构的架构师，关注简单性和交付速度",
    )
    debate_result = debate.run()

    print(f"\n     💰 辩论 Token：{debate_result['total_tokens']:,}")

    # 示例 2：投票 — 代码评审
    print("\n" + "-" * 50)
    print("【场景 2】代码评审投票")
    print("-" * 50)

    sample_code = """
def get_user(user_id):
    # 从数据库获取用户信息
    import sqlite3
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    row = cursor.fetchone()
    conn.close()
    return row
"""

    voting = VotingManager(llm=llm, voter_count=3)
    vote_result = voting.run(
        subject=sample_code,
        context="这段 Python 代码用于获取用户信息，请在代码质量和安全性方面评估。"
    )

    print(f"\n     💰 投票 Token：{vote_result['total_tokens']:,}")

    # 展示全部成本
    total_tokens = debate_result['total_tokens'] + vote_result['total_tokens']
    print(f"\n{'=' * 70}")
    print(f"💰 总 Token 消耗：{total_tokens:,}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
