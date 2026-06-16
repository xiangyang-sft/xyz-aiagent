#!/usr/bin/env python3
"""
xyz_agent.cli — 命令行接口

提供 xyz-agent 的 CLI 工具，支持：
  - xyz run "你的问题"  : 运行 Agent
  - xyz chat             : 交互式对话
  - xyz tools            : 列出可用工具
  - xyz config           : 查看/修改配置

依赖: 需要安装 click (pip install click)
"""

import sys
import json
import os
from typing import Optional

from .agent import Agent, AgentConfig
from .tool import ToolRegistry, get_all_tools
from . import __version__


def create_cli_agent(llm_fn=None, tools=None):
    """创建 CLI 用的 Agent 实例"""
    if llm_fn is None:
        # 默认使用 mock（提示用户配置真实 LLM）
        def default_llm(prompt, messages):
            print("⚠️  未配置真实 LLM 提供者，使用模拟回答")
            return "最终答案: 这是模拟回答。请设置真实的 LLM 提供函数。", 50
        llm_fn = default_llm

    return Agent(
        llm_provider=llm_fn,
        tools=tools or get_all_tools(),
        config=AgentConfig(
            name="cli-agent",
            verbose=False,
        ),
    )


def cmd_run(question: str, llm_fn=None, tools=None):
    """执行单次 Agent 运行"""
    agent = create_cli_agent(llm_fn, tools)
    result = agent.run(question)
    print(result)
    return result


def cmd_chat(llm_fn=None, tools=None):
    """启动交互式对话"""
    agent = create_cli_agent(llm_fn, tools)
    print(f"xyz-agent v{__version__} — 交互式对话")
    print("输入 'exit' 或 'quit' 退出")
    print("-" * 40)

    while True:
        try:
            question = input("\n🧑 > ").strip()
            if question.lower() in ("exit", "quit", "/exit"):
                print("再见！👋")
                break
            if not question:
                continue

            result = agent.chat(question)
            print(f"\n🤖 > {result}")

        except KeyboardInterrupt:
            print("\n再见！👋")
            break
        except EOFError:
            print("\n再见！👋")
            break


def cmd_tools():
    """列出所有注册的工具"""
    tools = get_all_tools()
    if not tools:
        print("当前没有注册的工具。")
        return

    print(f"可用工具 ({len(tools)}):")
    print()
    for t in tools:
        print(f"  🔧 {t['name']}")
        print(f"     描述: {t['description']}")
        params = t.get("parameters", {}).get("properties", {})
        if params:
            print(f"     参数:")
            for pname, pinfo in params.items():
                required = "（必填）" if pname in t.get("required", []) else "（可选）"
                print(f"       {pname}: {pinfo.get('type', 'any')} {required}")
        print()


def cmd_config(args: list):
    """查看或修改配置"""
    config_path = os.path.expanduser("~/.xyz-agent/config.json")

    if not args:
        # 显示配置
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
            print("当前配置:")
            print(json.dumps(config, indent=2, ensure_ascii=False))
        else:
            print("配置文件不存在: %s" % config_path)
            print("使用默认配置运行。")
    elif args[0] == "set" and len(args) >= 3:
        # 设置配置
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        config = {}
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
        config[args[1]] = args[2]
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        print(f"已设置 {args[1]} = {args[2]}")
    else:
        print("用法: xyz config [set <key> <value>]")


def cmd_version():
    """显示版本"""
    print(f"xyz-agent v{__version__}")


def main():
    """CLI 入口"""
    if len(sys.argv) < 2:
        print(f"xyz-agent v{__version__}")
        print()
        print("用法:")
        print("  xyz run <问题>    运行 Agent")
        print("  xyz chat          交互式对话")
        print("  xyz tools         列出工具")
        print("  xyz config        查看配置")
        print("  xyz version       显示版本")
        return

    command = sys.argv[1]
    args = sys.argv[2:]

    if command == "run":
        cmd_run(" ".join(args))
    elif command == "chat":
        cmd_chat()
    elif command == "tools":
        cmd_tools()
    elif command == "config":
        cmd_config(args)
    elif command in ("version", "--version", "-v"):
        cmd_version()
    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
