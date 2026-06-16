#!/usr/bin/env python3
"""
Step 3 — 多 Agent 编排 + CLI 封装演示

展示 xyz-agent 框架的高级功能：
  1. 编排式协作（Supervisor + Workers）
  2. 协商式协作（Debate）
  3. 流水线协作（Pipeline）
  4. CLI 接口
  5. pip install 安装验证

运行:
  python step3-orchestrator-demo.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from xyz_agent.agent import Agent, AgentConfig
from xyz_agent.orchestrator import Orchestrator, CollabMode, OrchestratorConfig
from xyz_agent.cli import cmd_run, cmd_tools, cmd_version


# ============================================================
# 模拟 LLM 提供函数
# ============================================================

call_counts = {}

def make_mock_llm(name: str, specialty: str):
    """创建一个模拟 LLM 函数"""
    def mock_llm(prompt, messages):
        call_counts[name] = call_counts.get(name, 0) + 1
        return f"最终答案: [{name}] 关于「{specialty}」的回答：已处理任务。完成。", 100
    return mock_llm


# ============================================================
# 1. 编排式协作
# ============================================================

def demo_orchestrated():
    """编排式协作：Supervisor 分解任务 + Workers 执行"""
    print("=" * 60)
    print("📌 演示 1：编排式协作")
    print("=" * 60)

    # 创建 Agent 工厂函数
    def create_agent(name: str, role: str) -> Agent:
        return Agent(
            llm_provider=make_mock_llm(name, role),
            config=AgentConfig(name=name),
        )

    orch = Orchestrator(
        create_agent_fn=create_agent,
        config=OrchestratorConfig(verbose=True),
    )

    result = orch.run(
        goal="写一份 AI Agent 学习路线图",
        agents=["researcher", "writer", "reviewer"],
        mode=CollabMode.ORCHESTRATED,
    )

    print(f"\n结果:")
    print(f"  模式: {result['mode']}")
    print(f"  任务数: {len(result['tasks'])}")
    print(f"  各 Agent 调用次数: {call_counts}")
    print()


# ============================================================
# 2. 协商式协作
# ============================================================

def demo_debate():
    """协商式协作：多 Agent 辩论"""
    print("=" * 60)
    print("📌 演示 2：协商式协作（辩论）")
    print("=" * 60)

    call_counts.clear()

    def create_agent(name: str, role: str) -> Agent:
        return Agent(
            llm_provider=make_mock_llm(name, role),
            config=AgentConfig(name=name),
        )

    orch = Orchestrator(
        create_agent_fn=create_agent,
        config=OrchestratorConfig(max_rounds=2, verbose=True),
    )

    result = orch.run(
        goal="AI 是否应该拥有自主决策权？",
        agents=["proponent", "opponent"],
        mode=CollabMode.DEBATE,
    )

    print(f"\n结果:")
    print(f"  辩论轮数: {result['rounds']}")
    print(f"  各 Agent 调用次数: {call_counts}")
    print()


# ============================================================
# 3. 流水线式协作
# ============================================================

def demo_pipeline():
    """流水线式协作：链式执行"""
    print("=" * 60)
    print("📌 演示 3：流水线式协作")
    print("=" * 60)

    call_counts.clear()

    def create_agent(name: str, role: str) -> Agent:
        return Agent(
            llm_provider=make_mock_llm(name, role),
            config=AgentConfig(name=name),
        )

    orch = Orchestrator(
        create_agent_fn=create_agent,
        config=OrchestratorConfig(verbose=True),
    )

    result = orch.run(
        goal="从零到部署一个 AI Agent",
        agents=["planner", "developer", "tester", "deployer"],
        mode=CollabMode.PIPELINE,
    )

    print(f"\n结果:")
    print(f"  流水线步骤: {result['steps']}")
    print(f"  最终输出: {result['final_output'][:100]}...")
    print()


# ============================================================
# 4. CLI 接口演示
# ============================================================

def demo_cli():
    """CLI 接口演示"""
    print("=" * 60)
    print("📌 演示 4：CLI 接口")
    print("=" * 60)

    # 版本信息
    print(">>> xyz version:")
    cmd_version()
    print()

    # 列出工具
    print(">>> xyz tools:")
    cmd_tools()
    print()


# ============================================================
# 5. pip 安装验证
# ============================================================

def demo_pip_install():
    """验证 pip install 可用"""
    print("=" * 60)
    print("📌 演示 5：pip install 验证")
    print("=" * 60)

    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", "."],
        capture_output=True, text=True, cwd=os.path.dirname(__file__),
    )
    if result.returncode == 0:
        print("✅ pip install -e . 成功！")
    else:
        print(f"⚠️ pip install 输出: {result.stdout[-200:]}")
        print(f"   错误: {result.stderr[-200:]}")
    print()

    # 验证 import
    try:
        import xyz_agent
        print(f"✅ 导入 xyz_agent v{xyz_agent.__version__} 成功！")
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
    print()

    # 验证 CLI 入口
    result = subprocess.run(
        [sys.executable, "-m", "xyz_agent.cli", "version"],
        capture_output=True, text=True,
    )
    print(f"✅ CLI 入口: xyz-agent version => {result.stdout.strip()}")
    print()


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║   xyz-agent 框架 — Step 3 演示             ║")
    print("║   多 Agent 编排 + CLI 封装                 ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    demo_orchestrated()
    demo_debate()
    demo_pipeline()
    demo_cli()
    demo_pip_install()

    print("=" * 60)
    print("✅ Step 3 全部演示完成！")
    print("=" * 60)
    print()
    print("🎉 xyz-agent 框架 v0.1.0 构建完成！")
    print()
    print("模块概览:")
    print("  ✅ xyz_agent/__init__.py  — 包入口 + 版本")
    print("  ✅ xyz_agent/engine.py    — ReAct 循环引擎")
    print("  ✅ xyz_agent/agent.py     — Agent 封装 API")
    print("  ✅ xyz_agent/tool.py      — 工具系统（注册/执行/MCP）")
    print("  ✅ xyz_agent/memory.py    — 记忆系统（短期/长期/RAG）")
    print("  ✅ xyz_agent/orchestrator.py — 多 Agent 编排引擎")
    print("  ✅ xyz_agent/cli.py       — CLI 接口")
    print("  ✅ setup.py / README.md   — pip 安装支持")
