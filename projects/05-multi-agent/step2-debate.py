#!/usr/bin/env python3
"""Step 2: 协商式协作 — 多 Agent 辩论

核心模式：多个 Agent 从不同角度分析同一问题，通过多轮讨论达成共识。

学习目标：
- 理解辩论式协作的工作机制
- 掌握多轮次讨论的流程控制
- 体验多 Agent 相互校验的价值
"""

import json
import os
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "YOUR_API_KEY_HERE"),
)


# ═══════════════════════════════════════════════════════════════
# 辩论 Agent 定义
# ═══════════════════════════════════════════════════════════════

class DebateAgent:
    """辩论参与 Agent"""
    
    def __init__(self, name: str, stance: str, personality: str, model: str = "gpt-4o-mini"):
        self.name = name
        self.stance = stance
        self.model = model
        self.system_prompt = f"""你是一个辩论参与者，名叫 {name}。

你的立场：{stance}
你的风格：{personality}

规则：
1. 每次辩论围绕当前话题给出你的观点
2. 你可以引用前一位发言者的论点
3. 请用 2-3 句话清晰表达，不要过长
4. 如果对方提出有力的反驳，可以适当调整立场
5. 最终要给出一个建设性的结论
    
注意：辩论的目的是寻找最佳方案，不是争输赢。"""
    
    def speak(self, topic: str, context: list[str] | None = None) -> str:
        """发言"""
        messages = [{"role": "system", "content": self.system_prompt}]
        
        if context:
            history = "\n".join(context[-6:])  # 保留最近 6 轮
            messages.append({
                "role": "user",
                "content": f"辩论话题：{topic}\n\n截至目前讨论历史：\n{history}\n\n请发表你的观点："
            })
        else:
            messages.append({
                "role": "user",
                "content": f"辩论话题：{topic}\n\n请从你的角度发表开场观点："
            })
        
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
        )
        return response.choices[0].message.content


class Moderator:
    """辩论主持人 — 控制流程、总结共识"""
    
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.system_prompt = """你是辩论主持人，职责：
1. 宣布辩论开始和规则
2. 在辩论中适时引导话题
3. 在辩论结束时总结各方观点
4. 提炼共识点和分歧点
5. 输出最终的"综合结论"

保持中立客观，不偏袒任何一方。"""
    
    def summarize(self, topic: str, transcript: list[str]) -> str:
        """总结辩论结果"""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"""辩论话题：{topic}

完整辩论记录：
{chr(10).join(transcript)}

请总结：
1. 各方核心观点
2. 已达成共识的点
3. 仍然存在的分歧
4. 综合结论与建议"""}
        ]
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
        )
        return response.choices[0].message.content


# ═══════════════════════════════════════════════════════════════
# 辩论流程
# ═══════════════════════════════════════════════════════════════

def hold_debate(
    topic: str,
    agents: list[DebateAgent],
    rounds: int = 3,
    moderator: Moderator | None = None,
) -> tuple[list[str], str]:
    """举行多 Agent 辩论
    
    参数：
        topic: 辩论话题
        agents: 参与的 Agent 列表
        rounds: 辩论轮次（每轮每个 Agent 发言一次）
        moderator: 主持人（可选）
    
    返回：
        (transcript, summary)
    """
    transcript = []
    
    print(f"\n{'='*60}")
    print(f"🎤 辩论开始！")
    print(f"话题：{topic}")
    print(f"参与者：{', '.join(a.name for a in agents)}")
    print(f"轮次：{rounds}")
    print(f"{'='*60}\n")
    
    # 开场（每个 Agent 第一轮）
    print("── 开场陈述 ──\n")
    for agent in agents:
        speech = agent.speak(topic)
        print(f"【{agent.name} (立场: {agent.stance})】")
        print(f"  {speech}\n")
        transcript.append(f"【{agent.name}】{speech}")
    
    # 多轮辩论
    for round_num in range(2, rounds + 1):
        print(f"\n── 第 {round_num} 轮讨论 ──\n")
        for agent in agents:
            speech = agent.speak(topic, transcript)
            print(f"【{agent.name}】")
            print(f"  {speech}\n")
            transcript.append(f"【{agent.name}】{speech}")
    
    # 主持人总结
    if moderator:
        print(f"\n── 主持人总结 ──\n")
        summary = moderator.summarize(topic, transcript)
        print(summary)
    else:
        # 没有主持人时，让最后一个 Agent 总结
        summary = agents[-1].speak(
            topic,
            transcript + ["请综合所有观点，给出最终结论："]
        )
        print(f"\n── 最终结论 ──\n")
        print(f"【{agents[-1].name}】{summary}")
    
    print(f"\n{'='*60}")
    print(f"✅ 辩论结束！")
    print(f"{'='*60}")
    
    return transcript, summary


# ═══════════════════════════════════════════════════════════════
# 示例辩论场景
# ═══════════════════════════════════════════════════════════════

def tech_stack_debate():
    """辩论 1：技术选型辩论"""
    print("\n" + "★" * 60)
    print("辩论 1：技术选型 — AI Agent 框架选什么？")
    print("★" * 60)
    
    agents = [
        DebateAgent(
            name="务实派",
            stance="选成熟稳定的 LangChain/LangGraph，它有最完善的生态和社区支持",
            personality="务实保守，注重稳定性和生产环境可靠性，引用实际案例。",
        ),
        DebateAgent(
            name="激进派",
            stance="选最新的轻量框架，如 OpenAI Swarm/新锐框架，简单直接，减少学习成本",
            personality="热衷于新技术，讨厌复杂臃肿的方案，注重开发效率。",
        ),
        DebateAgent(
            name="折衷派",
            stance="看具体场景，框架只是工具，应该按需选择甚至自己实现",
            personality="理性和中立，善于分析利弊，不盲目追随。",
        ),
    ]
    
    moderator = Moderator()
    
    return hold_debate(
        topic="团队要选一个 AI Agent 框架，LangChain/LangGraph, CrewAI, Swarm 还是自己写？",
        agents=agents,
        rounds=3,
        moderator=moderator,
    )


def product_strategy_debate():
    """辩论 2：产品策略辩论"""
    print("\n" + "★" * 60)
    print("辩论 2：产品策略 — AI 学习助手应该怎么做？")
    print("★" * 60)
    
    agents = [
        DebateAgent(
            name="产品经理",
            stance="先做最小可行产品（MVP），快速验证市场",
            personality="结果导向，重视用户体验和商业价值。",
        ),
        DebateAgent(
            name="技术主管",
            stance="先做好架构设计和技术底座，可扩展性最重要",
            personality="注重技术深度和长期可持续性，避免技术债。",
        ),
        DebateAgent(
            name="增长黑客",
            stance="先聚焦核心增长引擎，用数据驱动迭代",
            personality="数据驱动，关注转化率和留存，快速实验。",
        ),
    ]
    
    moderator = Moderator()
    
    return hold_debate(
        topic="开发一个 AI 学习助手 App，MVP、技术底座、增长策略哪个优先？",
        agents=agents,
        rounds=2,
        moderator=moderator,
    )


# ═══════════════════════════════════════════════════════════════
# 主程序
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("🤝 协商式多 Agent 辩论演示")
    print("=" * 60)
    
    # 运行辩论
    transcript1, summary1 = tech_stack_debate()
    
    print("\n\n")
    
    transcript2, summary2 = product_strategy_debate()
    
    print("\n" + "=" * 60)
    print("✅ 所有辩论完成！")
    print("=" * 60)
    print(f"\n辩论 1 关键结论：\n{summary1[:500]}...")
    print(f"\n辩论 2 关键结论：\n{summary2[:500]}...")
