#!/usr/bin/env python3
"""Step 1: 编排式协作 — Controller + Specialists

核心模式：一个 Controller Agent 将任务拆解，分发给多个 Specialist Agent，最后汇总结果。

学习目标：
- 理解 Controller-Worker 架构
- 掌握任务分解与结果汇总
- 体验编排式协作的价值
"""

import json
import os
from datetime import datetime

# 尝试加载 .env 文件
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
# Agent 基类
# ═══════════════════════════════════════════════════════════════

class Agent:
    """通用 Agent 基类"""
    
    def __init__(self, name: str, role: str, system_prompt: str, model: str = "gpt-4o-mini"):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.model = model
    
    def run(self, message: str, context: list | None = None) -> str:
        """运行 Agent 并返回回复"""
        messages = [{"role": "system", "content": self.system_prompt}]
        if context:
            messages.extend(context)
        messages.append({"role": "user", "content": message})
        
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
        )
        return response.choices[0].message.content


# ═══════════════════════════════════════════════════════════════
# Controller Agent (编排者)
# ═══════════════════════════════════════════════════════════════

CONTROLLER_PROMPT = """你是一个 AI 团队的项目协调者（Controller）。

你的职责：
1. 分析用户请求，将其拆解为明确的子任务
2. 将子任务分配给最合适的 Specialist Agent
3. 收集 Specialist 的结果，整合成完整输出
4. 确保最终结果完整、准确、条理清晰

子任务分配策略（选择最合适的）：
- 如果任务包含技术问题 → 分配给 Tech Specialist
- 如果任务包含创意/文案内容 → 分配给 Creative Specialist  
- 如果任务包含数据分析 → 分配给 Data Specialist
- 如果需要多角度分析 → 拆成多个子任务并行分配

回复格式：先拆分任务，然后调用对应 Specialist，最后汇总。"""


# ═══════════════════════════════════════════════════════════════
# Specialist Agents (专业 Agent)
# ═══════════════════════════════════════════════════════════════

SPECIALISTS = {
    "tech": Agent(
        name="Tech",
        role="技术专家",
        system_prompt="""你是一位资深技术专家。擅长：
- 系统架构设计与评估
- 技术方案比较与选型
- 代码审查与优化建议
- 技术风险评估

回答专业、简洁、有深度。尽量用结构化格式（列表、对比表）呈现。""",
    ),
    "creative": Agent(
        name="Creative",
        role="创意专家",
        system_prompt="""你是一位创意总监。擅长：
- 文案策划与写作
- 品牌定位与创意策略
- 内容运营方案
- 产品命名与营销创意

回答富有创造力和感染力，同时保持商业可行性。""",
    ),
    "data": Agent(
        name="Data",
        role="数据分析师",
        system_prompt="""你是一位数据分析专家。擅长：
- 数据分析方法设计
- 指标体系建设
- 数据可视化方案
- 数据驱动决策建议

回答基于数据思维，结构清晰，给出可操作的洞察。""",
    ),
}


# ═══════════════════════════════════════════════════════════════
# 手动编排 — Controller 自己判断并调用 Specialist
# ═══════════════════════════════════════════════════════════════

def orchestrate(task: str) -> str:
    """编排式协作主流程"""
    
    controller = Agent(
        name="Controller",
        role="项目协调者",
        system_prompt=CONTROLLER_PROMPT,
    )
    
    # Step 1: Controller 分析任务
    print(f"\n{'='*60}")
    print(f"📋 任务分析阶段")
    print(f"{'='*60}")
    print(f"任务: {task}\n")
    
    analysis_prompt = f"""分析以下任务并制定执行计划：

任务：{task}

请按以下格式回复：
1. 任务拆解：[列出 2-4 个子任务]
2. 分配方案：[每个子任务分配给哪个 Specialist]
3. 依赖关系：[哪些子任务有前后依赖]
"""
    analysis = controller.run(analysis_prompt)
    print(f"[Controller 分析]\n{analysis}\n")
    
    # Step 2: 手动指定 specialists 并执行
    # 在实际工程中，这里应该让 LLM 自动判断如何拆分
    # 为了教学清晰，我们预设几种常见模式
    
    print(f"\n{'='*60}")
    print(f"🚀 执行阶段")
    print(f"{'='*60}\n")
    
    results = {}
    
    # 根据任务关键词判断需要哪些 Specialist
    task_lower = task.lower()
    needed = set()
    
    if any(w in task_lower for w in ["技术", "架构", "代码", "开发", "技术方案", "系统"]):
        needed.add("tech")
    if any(w in task_lower for w in ["创意", "文案", "品牌", "营销", "内容", "设计"]):
        needed.add("creative")
    if any(w in task_lower for w in ["数据", "分析", "指标", "统计", "报告"]):
        needed.add("data")
    
    # 如果没匹配到，默认让所有 Specialist 从各自角度分析
    if not needed:
        needed = {"tech", "creative", "data"}
    
    for key in needed:
        agent = SPECIALISTS[key]
        subtask_prompt = f"请从 {agent.role} 的角度分析以下任务：\n\n{task}\n\n请给出专业建议。"
        print(f"  → 分配给 [{agent.role}]...")
        result = agent.run(subtask_prompt)
        results[agent.role] = result
        print(f"  ✓ [{agent.role}] 完成\n")
    
    # Step 3: Controller 汇总
    print(f"{'='*60}")
    print(f"📝 汇总阶段")
    print(f"{'='*60}\n")
    
    summary_prompt = f"""请汇总以下各 Specialist 的意见，生成一份完整的综合报告：

原始任务：{task}

各专家意见：
"""
    for role, result in results.items():
        summary_prompt += f"\n【{role}】\n{result}\n"
    
    summary_prompt += "\n请整合以上内容，输出最终报告。注意去重、突出核心观点。"
    
    final = controller.run(summary_prompt)
    print("[Controller 汇总]")
    print(final)
    
    return final


# ═══════════════════════════════════════════════════════════════
# 主程序入口
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("🧭 编排式多 Agent 协作演示")
    print("=" * 60)
    
    # 示例任务
    tasks = [
        "我们想开发一个 AI 学习助手 App，请从技术、创意和数据角度分析可行性",
    ]
    
    task = tasks[0]
    result = orchestrate(task)
    
    print(f"\n{'='*60}")
    print("✅ 编排式协作完成！")
    print(f"{'='*60}")
