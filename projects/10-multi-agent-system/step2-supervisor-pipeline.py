#!/usr/bin/env python3
"""
Step 2 — 进阶版：Supervisor + Pipeline 串联（结构图驱动）

核心概念：
- Supervisor（监督者）：负责任务分解、质量控制和最终汇总
- Pipeline 串联：每个 Agent 的输入是前一个 Agent 的输出
  架构师 → 开发者 → 测试工程师（有序传递上下文）
- 黑板模式（Blackboard）：所有 Agent 通过共享存储交换信息
- 结构化日志：记录每次 Agent 交互

对比 Step 1 的增量：
  1. Supervisor 做精细任务分解（含依赖关系和验收标准）
  2. Agent 按依赖顺序执行（Pipeline）
  3. Supervisor 做质量控制（验证完整性，要求重做）
  4. 引入黑板（Blackboard）存储中间结果
  5. 使用结构化 JSON 日志记录每次交互

运行：
  python step2-supervisor-pipeline.py
"""

import json
import time
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import deque


# ============================================================
# 1. LLM 客户端
# ============================================================

class LLMClient:
    def __init__(self, api_key: str = None, base_url: str = None, 
                 smart_model: str = "gpt-4o", fast_model: str = "gpt-4o-mini"):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.smart_model = smart_model    # 强模型：Supervisor 使用
        self.fast_model = fast_model      # 轻量模型：Worker 使用

    def chat(self, messages: list, model: str = None, temperature: float = 0.3) -> str:
        model = model or self.fast_model
        resp = self.client.chat.completions.create(
            model=model, messages=messages, temperature=temperature,
        )
        usage = resp.usage
        return {
            "content": resp.choices[0].message.content or "",
            "model": model,
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
        }


# ============================================================
# 2. 黑板模式 — 共享存储
# ============================================================

class Blackboard:
    """
    黑板模式：所有 Agent 通过黑板共享信息，而不是直接通信。
    
    三个区域：
    - task_queue: 待处理的任务队列
    - artifacts: 各 Agent 的工作产出
    - context: 全局上下文信息
    """

    def __init__(self):
        self.task_queue: deque = deque()
        self.artifacts: Dict[str, Any] = {}
        self.context: Dict[str, Any] = {
            "created_at": time.time(),
        }
        self._history: List[dict] = []

    def add_task(self, task: dict):
        """添加任务到队列"""
        self.task_queue.append(task)
        self._history.append({"action": "add_task", "task": task, "time": time.time()})

    def get_task(self) -> Optional[dict]:
        """从队列取出一个任务"""
        return self.task_queue.popleft() if self.task_queue else None

    def publish(self, agent_name: str, key: str, value: Any):
        """Agent 发布产出到黑板"""
        if agent_name not in self.artifacts:
            self.artifacts[agent_name] = {}
        self.artifacts[agent_name][key] = value
        self._history.append({
            "action": "publish", "agent": agent_name, "key": key, "time": time.time()
        })

    def read(self, agent_name: str, key: str = None) -> Any:
        """从黑板读取数据"""
        if agent_name not in self.artifacts:
            return None
        if key:
            return self.artifacts[agent_name].get(key)
        return self.artifacts[agent_name]

    def get_all_artifacts(self) -> str:
        """获取所有黑板内容（用于 Supervisor 做汇总）"""
        parts = []
        for agent_name, artifacts in self.artifacts.items():
            for key, value in artifacts.items():
                parts.append(f"【{agent_name} - {key}】\n{value}")
        return "\n\n".join(parts)

    def snapshot(self) -> dict:
        """黑板快照"""
        return {
            "queue_size": len(self.task_queue),
            "agents_with_output": list(self.artifacts.keys()),
            "context_keys": list(self.context.keys()),
        }


# ============================================================
# 3. 结构化日志
# ============================================================

class StructuredLogger:
    """JSON 结构化日志（可观测性三大支柱之一）"""

    def __init__(self):
        self.logs: List[dict] = []

    def log(self, event_type: str, data: dict):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            **data,
        }
        self.logs.append(entry)
        # 同时打印到控制台
        print(f"  📝 [{event_type}] {data.get('agent', 'system')}: "
              f"{data.get('message', '')}")

    def get_traces(self, agent_name: str = None) -> List[dict]:
        """按 Agent 过滤追踪日志"""
        if agent_name:
            return [l for l in self.logs if l.get("agent") == agent_name]
        return self.logs

    def summary(self) -> dict:
        """日志概要"""
        return {
            "total_events": len(self.logs),
            "agents_involved": list(set(
                l.get("agent") for l in self.logs if l.get("agent")
            )),
            "total_tokens": sum(
                l.get("tokens", 0) for l in self.logs
            ),
        }


# ============================================================
# 4. Agent 定义（每个 Agent 可读取黑板）
# ============================================================

class PipelineAgent:
    """Pipeline 中的 Agent，可以读黑板中前序 Agent 的输出"""

    def __init__(self, name: str, role_desc: str, llm: LLMClient, 
                 blackboard: Blackboard, logger: StructuredLogger,
                 model: str = None):
        self.name = name
        self.role_desc = role_desc
        self.llm = llm
        self.blackboard = blackboard
        self.logger = logger
        self.model = model or llm.fast_model

    def execute(self, task: str) -> str:
        """执行任务，从黑板读取上下文，结果写入黑板"""
        # 读取前序 Agent 的输出作为上下文
        all_artifacts = self.blackboard.get_all_artifacts()
        
        system = (
            f"{self.role_desc}\n\n"
            f"请基于以下已有工作成果继续完成任务：\n{all_artifacts or '（尚无前置成果）'}"
        )
        
        result = self.llm.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": task},
            ],
            model=self.model,
        )

        # 记录日志
        self.logger.log("agent_execute", {
            "agent": self.name,
            "task": task[:80],
            "tokens": result["total_tokens"],
            "message": f"执行完成，输出 {len(result['content'])} 字符",
            "model": result["model"],
        })

        # 写入黑板
        self.blackboard.publish(self.name, "output", result["content"])
        self.blackboard.publish(self.name, "tokens", result["total_tokens"])

        return result["content"]


# ============================================================
# 5. Supervisor（监督者）
# ============================================================

class Supervisor:
    """
    监督者（Supervisor）—— 多 Agent 系统的"大脑"
    
    职责：
    1. 分析并分解任务（含依赖关系和验收标准）
    2. 按 Pipeline 顺序安排 Agent 执行
    3. 做质量检查（验证完整性）
    4. 最终汇总输出
    """

    SUPERVISOR_PROMPT = """你是一个经验丰富的技术项目经理（Supervisor），管理一个由 AI 专家组成的团队。

团队包括：
1. **架构师** — 系统设计、技术选型、API 设计
2. **开发者** — 代码实现、性能优化
3. **测试工程师** — 测试策略、测试用例、质量保障

你的工作流程：
1. 分析用户需求，分解为按顺序执行的子任务（Pipeline）
2. 每个子任务指定责任人、输入和验收标准
3. 任务按依赖关系串联：架构师 → 开发者 → 测试
4. 执行完毕后做质量检查，输出最终报告

任务分解格式（严格 JSON）：
{
    "analysis": "需求分析",
    "pipeline": [
        {
            "agent": "architect",
            "task": "具体任务描述",
            "acceptance_criteria": ["标准1", "标准2"]
        },
        {
            "agent": "developer",
            "task": "具体任务描述",
            "acceptance_criteria": ["标准1", "标准2"]
        },
        {
            "agent": "tester",
            "task": "具体任务描述",
            "acceptance_criteria": ["标准1", "标准2"]
        }
    ]
}
"""

    QUALITY_CHECK_PROMPT = """你是质量检查官，审查一个 AI 团队的工作成果。

请检查以下方面：
1. 架构设计是否合理、是否满足需求
2. 代码实现是否正确、是否有明显 bug
3. 测试方案是否完备、覆盖边界条件
4. 整体输出是否完整

如果发现问题，明确指出哪些部分需要改进。
"""

    def __init__(self, llm: LLMClient, blackboard: Blackboard, 
                 logger: StructuredLogger, agents: Dict[str, PipelineAgent]):
        self.llm = llm
        self.blackboard = blackboard
        self.logger = logger
        self.agents = agents

    def decompose(self, user_request: str) -> list:
        """分解任务为 Pipeline"""
        result = self.llm.chat(
            messages=[
                {"role": "system", "content": self.SUPERVISOR_PROMPT},
                {"role": "user", "content": f"请分解以下任务：\n{user_request}"},
            ],
            model=self.llm.smart_model,
        )
        
        self.logger.log("task_decompose", {
            "agent": "supervisor", "tokens": result["total_tokens"],
            "message": f"模型 {result['model']}，任务分解完成",
        })

        # 提取 JSON
        try:
            plan = json.loads(result["content"][result["content"].index("{"):result["content"].rindex("}")+1])
            return plan.get("pipeline", [])
        except (ValueError, json.JSONDecodeError):
            # 回退默认 Pipeline
            return [
                {"agent": "architect", "task": f"请分析需求并设计架构方案：{user_request}",
                 "acceptance_criteria": ["方案完整", "技术选型合理"]},
                {"agent": "developer", "task": f"请根据架构方案实现代码：{user_request}",
                 "acceptance_criteria": ["代码可运行", "符合规范"]},
                {"agent": "tester", "task": f"请设计测试方案：{user_request}",
                 "acceptance_criteria": ["覆盖正常/异常场景", "边界条件"]},
            ]

    def quality_check(self, artifacts: str) -> str:
        """质量检查"""
        result = self.llm.chat(
            messages=[
                {"role": "system", "content": self.QUALITY_CHECK_PROMPT},
                {"role": "user", "content": f"请审查以下工作成果：\n\n{artifacts}"},
            ],
            model=self.llm.smart_model,
            temperature=0.2,
        )
        return result["content"]

    def final_summary(self, request: str, quality_report: str) -> str:
        """最终汇总"""
        artifacts = self.blackboard.get_all_artifacts()
        result = self.llm.chat(
            messages=[
                {"role": "system", "content": "你是一个技术项目的总负责人。"
                 "基于所有 Agent 的工作成果和质量报告，生成一份完整的最终总结。"},
                {"role": "user", "content": 
                 f"原始需求：{request}\n\n"
                 f"工作成果：\n{artifacts}\n\n"
                 f"质量报告：\n{quality_report}\n\n"
                 f"请生成最终总结，包括核心方案、实现结果和质量评价。"},
            ],
            model=self.llm.smart_model,
        )
        return result["content"]


# ============================================================
# 6. 完整 Pipeline 系统
# ============================================================

class SupervisorPipelineSystem:
    """Supervisor + Pipeline 多 Agent 协作系统"""

    def __init__(self, api_key: str = None, base_url: str = None):
        self.llm = LLMClient(api_key, base_url)
        self.blackboard = Blackboard()
        self.logger = StructuredLogger()

        # 角色定义
        self.agent_configs = {
            "architect": {
                "role": "你是一名资深软件架构师，擅长系统设计与技术选型。"
                        "输出应包括：架构图(文字描述)、核心组件、数据流、技术栈建议。",
                "model": self.llm.smart_model,
            },
            "developer": {
                "role": "你是一名全栈开发者，擅长编写高质量代码。"
                        "注重代码规范、错误处理、类型注解和文档注释。",
                "model": self.llm.fast_model,
            },
            "tester": {
                "role": "你是一名测试工程师，擅长测试策略和质量保障。"
                        "包括单元测试、集成测试和端到端测试的设计。",
                "model": self.llm.fast_model,
            },
        }

        # 创建 Agent 实例
        self.agents: Dict[str, PipelineAgent] = {}
        for name, cfg in self.agent_configs.items():
            self.agents[name] = PipelineAgent(
                name=name, role_desc=cfg["role"], llm=self.llm,
                blackboard=self.blackboard, logger=self.logger,
                model=cfg["model"],
            )

        self.supervisor = Supervisor(self.llm, self.blackboard, self.logger, self.agents)

    def run(self, user_request: str, verbose: bool = True) -> dict:
        """运行 Supervisor + Pipeline 协作"""
        if verbose:
            print("\n" + "=" * 70)
            print(f"📋 任务：{user_request}")
            print("=" * 70)

        # Phase 1: Supervisor 分解任务
        if verbose:
            print("\n🧠 Supervisor 正在分析并分解任务...")
        pipeline = self.supervisor.decompose(user_request)
        if verbose:
            print(f"   共 {len(pipeline)} 个 Pipeline 阶段")

        # Phase 2: 按 Pipeline 顺序执行
        total_tokens = 0
        for i, stage in enumerate(pipeline, 1):
            agent_name = stage["agent"]
            task = stage["task"]
            criteria = stage.get("acceptance_criteria", [])

            if verbose:
                print(f"\n  ▶️ 阶段 {i}/{len(pipeline)}：{agent_name}")
                print(f"     任务：{task[:80]}...")
                if criteria:
                    print(f"     验收标准：{' / '.join(criteria)}")

            agent = self.agents.get(agent_name)
            if not agent:
                print(f"    ⚠️ 未知 Agent: {agent_name}，跳过")
                continue

            result = agent.execute(task)
            total_tokens += self.blackboard.read(agent_name, "tokens") or 0

            if verbose:
                lines = result.strip().split("\n")
                preview = "\n".join(lines[:3])
                print(f"     ✅ 输出预览（前 {min(3, len(lines))} 行）：\n{preview}")

        # Phase 3: 质量检查
        if verbose:
            print("\n🔍 Supervisor 正在进行质量检查...")
        artifacts = self.blackboard.get_all_artifacts()
        quality_report = self.supervisor.quality_check(artifacts)
        if verbose:
            print(f"    📋 质量报告：\n{quality_report[:200]}...")

        # Phase 4: 最终汇总
        if verbose:
            print("\n📝 Supervisor 正在生成最终总结...")
        summary = self.supervisor.final_summary(user_request, quality_report)

        if verbose:
            print("\n" + "=" * 70)
            print("📋 最终输出")
            print("=" * 70)
            print(summary)
            print()
            print(f"📊 Token 总计：约 {total_tokens:,}")
            print(f"📊 事件总数：{self.logger.summary()['total_events']}")
            print("=" * 70)

        return {
            "request": user_request,
            "pipeline": pipeline,
            "summary": summary,
            "quality_report": quality_report,
            "stats": {
                "total_tokens": total_tokens,
                "stages": len(pipeline),
                "blackboard": self.blackboard.snapshot(),
            },
            "logs": self.logger.logs,
        }


def main():
    import os
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")

    system = SupervisorPipelineSystem(api_key=api_key, base_url=base_url)

    system.run(
        "设计一个 Python 用户认证系统，支持邮箱注册、登录、JWT Token 签发和密码重置。"
    )


if __name__ == "__main__":
    main()
