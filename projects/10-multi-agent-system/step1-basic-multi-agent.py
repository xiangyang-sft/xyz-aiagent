#!/usr/bin/env python3
"""
Step 1 — 基础版：Controller + 3 个 Worker Agent 的编排式协作

核心概念：
- Controller 接收用户请求，分解任务
- 三个专业 Worker Agent（架构师、开发者、测试工程师）独立执行子任务
- Controller 汇总所有结果

演示目标：
  1. 理解最基本的"编排式"多 Agent 协作
  2. 每个 Agent 有明确的角色定义（system prompt）
  3. 看 Controller 如何做 task decomposition + result aggregation

运行：
  python step1-basic-multi-agent.py
"""

import json
import time
from typing import Dict, List
from dataclasses import dataclass, asdict


# ============================================================
# 1. LLM 客户端（兼容 OpenAI / 本地 LLM）
# ============================================================

class LLMClient:
    """轻量 LLM 调用封装，支持 OpenAI 兼容接口"""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = "gpt-4o-mini"):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def chat(self, messages: List[dict], temperature: float = 0.3) -> str:
        """发送对话请求，返回文本回复"""
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""


# ============================================================
# 2. 结构化消息协议
# ============================================================

@dataclass
class Message:
    """Agent 之间通信的结构化消息"""
    msg_id: str
    sender: str
    receiver: str
    msg_type: str          # task | result | review
    content: dict
    timestamp: float
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


# ============================================================
# 3. Agent 定义
# ============================================================

class Agent:
    """通用 Agent 基类"""

    def __init__(self, name: str, system_prompt: str, llm: LLMClient):
        self.name = name
        self.system_prompt = system_prompt
        self.llm = llm
        self.conversation_history: List[dict] = []

    def execute(self, task: str, context: str = "") -> str:
        """执行任务并返回结果"""
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]
        if context:
            messages.append({"role": "system", "content": f"上下文信息：\n{context}"})
        messages.append({"role": "user", "content": task})

        result = self.llm.chat(messages)
        self.conversation_history.append({
            "task": task, "result": result, "timestamp": time.time()
        })
        return result


# ============================================================
# 4. 基础多 Agent 协作系统
# ============================================================

class BasicMultiAgentSystem:
    """最简多 Agent 协作系统：Controller 分发 + Workers 执行 + 汇总"""

    # Controller 专属 system prompt
    CONTROLLER_PROMPT = """你是一个智能项目经理（Controller），负责协调多个 AI 专家的协作。

你的工作流程：
1. 分析用户的请求，将其分解成 2-3 个明确的子任务
2. 将子任务分派给对应的专家 Agent
3. 收集各专家的结果，做最终汇总输出

输出格式（严格 JSON）：
{
    "analysis": "对用户请求的简要分析",
    "subtasks": {
        "architect": "分配给架构师的具体任务描述",
        "developer": "分配给开发者的具体任务描述",
        "tester": "分配给测试工程师的具体任务描述"
    }
}

注意：
- 每个子任务必须独立且可执行
- 子任务之间不能有重叠
- 如果某角色不适合当前任务，设为 "无需参与"
"""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = "gpt-4o-mini"):
        self.llm = LLMClient(api_key, base_url, model)
        self.model = model
        
        # 创建三个专业 Agent
        self.agents = {
            "architect": Agent(
                "架构师",
                "你是一名资深软件架构师，擅长系统设计、技术选型和架构决策。\n"
                "输出要清晰、结构化，包含设计理由、技术栈建议和架构图描述。\n",
                self.llm
            ),
            "developer": Agent(
                "开发者",
                "你是一名全栈开发者，擅长编写高质量、可维护的代码。\n"
                "注重代码规范、错误处理和性能优化。给出具体的代码实现。\n",
                self.llm
            ),
            "tester": Agent(
                "测试工程师",
                "你是一名软件测试工程师，擅长测试策略、测试用例编写和质量保障。\n"
                "关注边界条件、异常场景和测试覆盖率的完整性。\n",
                self.llm
            ),
        }

    def _decompose_task(self, user_request: str) -> dict:
        """Controller 分析并分解任务"""
        messages = [
            {"role": "system", "content": self.CONTROLLER_PROMPT},
            {"role": "user", "content": f"请分析并分解以下任务：\n\n{user_request}"},
        ]
        response = self.llm.chat(messages, temperature=0.2)
        
        # 从回复中提取 JSON
        try:
            # 找第一个 { 和最后一个 }
            start = response.index("{")
            end = response.rindex("}") + 1
            return json.loads(response[start:end])
        except (ValueError, json.JSONDecodeError):
            # 如果解析失败，返回默认结构
            return {
                "analysis": "自动分解",
                "subtasks": {
                    "architect": f"请分析任务并提供架构设计方案：{user_request}",
                    "developer": f"请实现上述架构方案的核心代码：{user_request}",
                    "tester": f"请为上述实现设计测试方案：{user_request}",
                }
            }

    def _summarize(self, request: str, results: Dict[str, str]) -> str:
        """Controller 汇总所有 Agent 的输出"""
        results_text = "\n\n".join([
            f"=== {name.upper()} 输出 ===\n{content}"
            for name, content in results.items()
        ])
        messages = [
            {"role": "system", "content": "你是一个项目经理，负责汇总多个专家的工作成果。"
                                          "将各专家的输出整合成一个完整的、有逻辑的最终报告。"},
            {"role": "user", "content": f"原始需求：{request}\n\n各专家输出：\n{results_text}\n\n"
                                        f"请汇总成一个完整的最终报告。"},
        ]
        return self.llm.chat(messages)

    def run(self, user_request: str, verbose: bool = True) -> dict:
        """运行多 Agent 协作流程"""
        if verbose:
            print("\n" + "=" * 70)
            print(f"🤖 收到任务：{user_request}")
            print("=" * 70)

        # 步骤 1：Controller 分解任务
        if verbose:
            print("\n🔄 Controller 正在分析并分解任务...")
        plan = self._decompose_task(user_request)

        if verbose:
            print(f"   分析：{plan.get('analysis', '')}")
            print(f"   子任务数：{sum(1 for v in plan.get('subtasks', {}).values() if v != '无需参与')}")
            print()

        # 步骤 2：并行分配任务给各 Agent
        results = {}
        for agent_name, subtask in plan.get("subtasks", {}).items():
            if subtask == "无需参与":
                continue
            agent = self.agents.get(agent_name)
            if not agent:
                continue

            if verbose:
                print(f"  👤 {agent.name} 收到子任务...")
                print(f"     📝 任务：{subtask[:100]}...")

            context = f"原始需求：{user_request}\nController 分析：{plan.get('analysis', '')}"
            result = agent.execute(subtask, context)
            results[agent_name] = result

            if verbose:
                lines = result.strip().split("\n")
                print(f"     ✅ 输出：{lines[0][:80]}...（共 {len(lines)} 行）")
                print()

        # 步骤 3：汇总结果
        if verbose:
            print("🔄 Controller 正在汇总所有结果...")
        summary = self._summarize(user_request, results)

        return {
            "request": user_request,
            "plan": plan,
            "results": results,
            "summary": summary,
            "stats": self._compute_stats(results),
        }

    def _compute_stats(self, results: dict) -> dict:
        """统计 Token 消耗等指标（估算版）"""
        total_chars = sum(len(v) for v in results.values())
        return {
            "agent_count": len(results),
            "total_output_chars": total_chars,
            "estimated_tokens": total_chars // 4,
        }

    def print_report(self, output: dict):
        """打印最终报告"""
        print("\n" + "=" * 70)
        print(f"📋 最终报告")
        print("=" * 70)
        print(output["summary"])
        print()
        print("-" * 70)
        print(f"📊 统计：{output['stats']['agent_count']} 个 Agent 参与，"
              f"约 {output['stats']['estimated_tokens']:,} tokens")
        print("=" * 70)


# ============================================================
# 5. 运行示例
# ============================================================

def main():
    import os
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")

    system = BasicMultiAgentSystem(api_key=api_key, base_url=base_url)

    # 示例 1：开发一个小功能
    result = system.run(
        "帮我设计并实现一个 Python 函数，可以从文本中提取所有邮箱地址和 URL，"
        "支持去重和排序。"
    )
    system.print_report(result)

    # 可以取消注释测试更多场景
    # result2 = system.run("设计一个简单的 REST API 用于用户注册和登录")


if __name__ == "__main__":
    main()
