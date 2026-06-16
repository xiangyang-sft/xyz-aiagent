#!/usr/bin/env python3
"""
xyz_agent.orchestrator — 多 Agent 编排引擎

支持三种协作模式：
  1. 编排式 (Orchestrated) — Supervisor 分配任务给 Workers
  2. 协商式 (Debate) — 多个 Agent 辩论达成共识
  3. Pipeline — 流水线串联执行
"""

import json
import time
import hashlib
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .agent import Agent, AgentConfig


class CollabMode(Enum):
    """协作模式"""
    ORCHESTRATED = "orchestrated"   # 编排式：Supervisor + Workers
    DEBATE = "debate"               # 协商式：多 Agent 辩论
    PIPELINE = "pipeline"           # 流水线：链式执行


@dataclass
class Task:
    """编排任务"""
    id: str
    goal: str
    context: Optional[str] = None
    assigned_to: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


@dataclass
class OrchestratorConfig:
    """编排引擎配置"""
    max_rounds: int = 3
    parallel_workers: bool = False
    require_consensus: bool = False
    verbose: bool = True


class Orchestrator:
    """
    多 Agent 编排引擎

    用法:
        orch = Orchestrator(create_agent_fn)
        result = orch.run(
            goal="写一篇关于 AI Agent 的文章",
            agents=["researcher", "writer", "reviewer"],
            mode=CollabMode.PIPELINE,
        )
    """

    def __init__(
        self,
        create_agent_fn: Callable[[str, str], Agent],
        config: Optional[OrchestratorConfig] = None,
    ):
        """
        参数:
          create_agent_fn: (agent_name, role_description) -> Agent
          config: 运行配置
        """
        self.create_agent = create_agent_fn
        self.config = config or OrchestratorConfig()
        self.agents: Dict[str, Agent] = {}
        self.tasks: List[Task] = []
        self.results: Dict[str, Any] = {}
        self.blackboard: Dict[str, Any] = {}  # 共享黑板

    def run(
        self,
        goal: str,
        agents: List[str],
        mode: CollabMode = CollabMode.ORCHESTRATED,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        运行多 Agent 协作

        参数:
          goal: 目标任务
          agents: Agent 名称列表
          mode: 协作模式
          context: 额外上下文

        返回:
          结果 dict
        """
        self.tasks = []
        self.results = {}
        self.blackboard = {"goal": goal, "context": context or ""}

        if mode == CollabMode.ORCHESTRATED:
            return self._run_orchestrated(goal, agents, context)
        elif mode == CollabMode.DEBATE:
            return self._run_debate(goal, agents, context)
        elif mode == CollabMode.PIPELINE:
            return self._run_pipeline(goal, agents, context)

    # ---- 编排式（Supervisor + Workers） ----

    def _run_orchestrated(
        self, goal: str, agents: List[str], context: Optional[str]
    ) -> Dict[str, Any]:
        """编排式协作"""

        # 1. Supervisor 分解任务
        self._log("📋 Supervisor 分析任务...")
        plan = self._decompose_task(goal, agents)

        # 2. 分配并执行任务
        for item in plan:
            agent_name = item["agent"]
            subgoal = item["subgoal"]

            task = Task(
                id=hashlib.md5(subgoal.encode()).hexdigest()[:8],
                goal=subgoal,
                assigned_to=agent_name,
            )
            self.tasks.append(task)

            self._log(f"  → {agent_name}: {subgoal}")

            agent = self._get_agent(agent_name, item.get("role", agent_name))
            task.status = "running"

            # 添加黑板上下文
            prompt = subgoal
            if self.blackboard:
                prompt += f"\n\n黑板信息:\n{json.dumps(self.blackboard, ensure_ascii=False)[:500]}"

            result = agent.run(prompt)
            task.status = "completed"
            task.result = result
            task.completed_at = time.time()

            # 写入黑板
            self.blackboard[f"{agent_name}_result"] = result[:200]
            self.results[agent_name] = result

        # 3. 汇总结果
        summary = self._summarize_results(goal)
        return {
            "mode": "orchestrated",
            "plan": plan,
            "results": self.results,
            "summary": summary,
            "tasks": [{"id": t.id, "goal": t.goal,
                       "assigned_to": t.assigned_to,
                       "status": t.status} for t in self.tasks],
        }

    # ---- 协商式（Debate） ----

    def _run_debate(
        self, goal: str, agents: List[str], context: Optional[str]
    ) -> Dict[str, Any]:
        """协商式协作（多 Agent 辩论）"""

        self._log("🗣️ 开始辩论...")

        round_num = 0
        debate_results = []

        while round_num < self.config.max_rounds:
            self._log(f"  第 {round_num + 1} 轮辩论")
            round_outputs = {}

            for agent_name in agents:
                agent = self._get_agent(agent_name, f"参与辩论的{agent_name}")

                # 构建辩论提示
                prompt = f"议题: {goal}\n"
                if round_num > 0 and debate_results:
                    prompt += "\n前面辩论摘要:\n"
                    for prev in debate_results[-1].values():
                        prompt += f"  - {prev[:200]}\n"
                prompt += f"\n请给出你的第 {round_num + 1} 轮观点："

                result = agent.run(prompt)
                round_outputs[agent_name] = result

            debate_results.append(round_outputs)

            # 检查是否达成共识
            if self.config.require_consensus and round_num >= 1:
                consensus = self._check_consensus(debate_results)
                if consensus:
                    self._log("  ✅ 达成共识！")
                    break

            round_num += 1

        return {
            "mode": "debate",
            "rounds": round_num + 1,
            "debate_history": debate_results,
            "results": {a: debate_results[-1][a] for a in agents},
        }

    # ---- 流水线式（Pipeline） ----

    def _run_pipeline(
        self, goal: str, agents: List[str], context: Optional[str]
    ) -> Dict[str, Any]:
        """流水线式协作"""
        self._log("🔗 开始流水线...")

        pipeline_input = goal
        pipeline_results = {}

        for i, agent_name in enumerate(agents):
            self._log(f"  步骤 {i+1}: {agent_name}")
            agent = self._get_agent(agent_name, f"流水线第{i+1}步: {agent_name}")

            prompt = f"上一步输入:\n{pipeline_input}\n\n请基于以上内容继续处理。"
            if i == 0:
                prompt = f"原始任务: {goal}\n\n请开始处理第一步。"

            result = agent.run(prompt)
            pipeline_results[agent_name] = result
            pipeline_input = result  # 输出作为下一步输入

            self.blackboard[f"pipeline_step_{i}"] = result[:200]

        return {
            "mode": "pipeline",
            "steps": agents,
            "results": pipeline_results,
            "final_output": pipeline_input,
        }

    # ---- 内部方法 ----

    def _get_agent(self, name: str, role: str) -> Agent:
        """获取或创建 Agent"""
        if name not in self.agents:
            self.agents[name] = self.create_agent(name, role)
        return self.agents[name]

    def _decompose_task(self, goal: str, agents: List[str]) -> List[Dict]:
        """分解任务并分配给 Agent"""
        # 简单分配：每个 Agent 负责一个子任务
        if len(agents) == 1:
            return [{"agent": agents[0], "subgoal": goal, "role": "通用助手"}]

        # 默认分解：按 Agent 数量拆分
        return [
            {
                "agent": agents[i],
                "subgoal": f"作为团队第{i+1}个成员，为任务「{goal}」贡献你的专业能力",
                "role": f"专家{i+1}",
            }
            for i in range(len(agents))
        ]

    def _summarize_results(self, goal: str) -> str:
        """汇总所有 Agent 的结果"""
        summary_parts = [f"任务: {goal}\n"]
        for agent_name, result in self.results.items():
            summary_parts.append(f"\n[{agent_name} 输出]:\n{result[:200]}...")
        return "\n".join(summary_parts)

    def _check_consensus(self, debate_results: List[Dict]) -> bool:
        """检查是否达成共识"""
        if len(debate_results) < 2:
            return False
        # 简单检查：上一轮和当前轮的主要观点是否一致
        prev = set(debate_results[-2].values())
        curr = set(debate_results[-1].values())
        return len(prev & curr) > 0

    def _log(self, msg: str):
        """日志输出"""
        if self.config.verbose:
            print(f"[Orchestrator] {msg}")


# ============================================================
# 快捷函数
# ============================================================

def create_pipeline_agent(name: str, role: str, llm_fn: Callable) -> Agent:
    """快速创建流水线 Agent"""
    return Agent(
        llm_provider=llm_fn,
        config=AgentConfig(
            name=name,
            system_prompt=f"你是一个{role}。请在流水线中完成你的专业任务。",
        ),
    )
