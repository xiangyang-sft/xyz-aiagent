#!/usr/bin/env python3
"""
Step 2 — 工具系统 + 记忆系统演示

展示 xyz-agent 框架的工具注册和记忆管理功能：
  1a. @tool 装饰器注册
  1b. 手动注册 + 参数校验
  1c. 默认注册表快捷方式
  2a. 短期记忆（对话上下文）
  2b. 长期记忆（持久化存储）
  2c. RAG 记忆（TF-IDF 检索）
  2d. 混合记忆系统（整合使用）

运行:
  python step2-tool-memory-demo.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from xyz_agent.tool import ToolRegistry, tool, get_all_tools, execute_tool
from xyz_agent.memory import (
    ShortTermMemory, LongTermMemory, RAGMemory, MemorySystem,
)


# ============================================================
# 第 1 部分：工具系统
# ============================================================

def demo_tool_decorator():
    """演示 @tool 装饰器注册方式"""
    print("=" * 60)
    print("📌 演示 1a：@tool 装饰器注册")
    print("=" * 60)

    # 创建独立注册表
    registry = ToolRegistry()

    @registry.register
    def get_weather(city: str) -> str:
        """查询城市天气"""
        data = {
            "北京": "晴，25°C，湿度45%",
            "上海": "多云，28°C，湿度60%",
            "深圳": "雷阵雨，30°C，湿度80%",
        }
        return data.get(city, f"{city}：暂无天气数据")

    @registry.register
    def calculator(expr: str) -> str:
        """计算数学表达式"""
        allowed = set("0123456789+-*/(). ")
        if not all(c in allowed for c in expr):
            return "错误：表达式包含非法字符"
        try:
            return f"{expr} = {eval(expr)}"
        except Exception as e:
            return f"计算错误: {e}"

    @registry.register
    def get_current_time() -> str:
        """获取当前时间"""
        import datetime
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("已注册工具:")
    for t in registry.list_tools():
        print(f"  🔧 {t['name']}: {t['description']}")
        for pname, pinfo in t['parameters'].get('properties', {}).items():
            required = "（必填）" if pname in t['required'] else "（可选）"
            print(f"      参数 {pname}: {pinfo.get('type')} {required}")
    print()

    # 执行工具
    results = [
        registry.execute("get_weather", {"city": "北京"}),
        registry.execute("calculator", {"expr": "3+5*2"}),
        registry.execute("get_current_time", {}),
    ]
    for r in results:
        print(f"  执行结果: {r}")

    # 错误处理
    try:
        registry.execute("calculator", {})  # 缺少必填参数
    except TypeError as e:
        print(f"  参数校验: {e}")

    print()


def demo_manual_register():
    """演示手动注册方式"""
    print("=" * 60)
    print("📌 演示 1b：手动注册 + MCP 格式")
    print("=" * 60)

    registry = ToolRegistry()

    # 手动注册（带自定义参数描述）
    registry.register_fn(
        name="translate",
        fn=lambda text, target_lang: f"[{text} 翻译成 {target_lang}]",
        description="将文本翻译到目标语言",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要翻译的文本"},
                "target_lang": {
                    "type": "string",
                    "description": "目标语言代码 (zh/en/ja)",
                    "enum": ["zh", "en", "ja"],
                },
            },
            "required": ["text", "target_lang"],
        },
    )

    # MCP 格式注册
    registry.register_mcp(
        name="search_web",
        fn=lambda query: f"[搜索 '{query}' 的结果...]",
        schema={
            "description": "搜索网络信息",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                },
                "required": ["query"],
            },
        },
    )

    print("已注册工具:")
    for t in registry.list_tools():
        print(f"  🔧 {t['name']}: {t['description']}")
    print()

    # OpenAI 格式输出
    print("OpenAI Function Calling 格式:")
    for t in registry.get_openai_tools():
        print(f"  - {json.dumps(t, ensure_ascii=False, indent=2)}")
    print()


def demo_default_registry():
    """演示默认注册表（@tool 快捷方式）"""
    print("=" * 60)
    print("📌 演示 1c：默认注册表快捷方式")
    print("=" * 60)

    # 使用 @tool 装饰器注册到默认注册表
    @tool
    def greet(name: str, greeting: str = "你好") -> str:
        """向某人打招呼"""
        return f"{greeting}，{name}！"

    @tool
    def add(a: int, b: int) -> int:
        """计算两数之和"""
        return a + b

    all_tools = get_all_tools()
    print(f"默认注册表中的工具:")
    for t in all_tools:
        print(f"  🔧 {t['name']}: {t['description']}")

    print()
    print("执行工具:")
    print(f"  greet('向阳') => {execute_tool('greet', {'name': '向阳'})}")
    print(f"  add(3, 5) => {execute_tool('add', {'a': 3, 'b': 5})}")
    print()


# ============================================================
# 第 2 部分：记忆系统
# ============================================================

def demo_short_term_memory():
    """演示短期记忆"""
    print("=" * 60)
    print("📌 演示 2a：短期记忆（对话上下文）")
    print("=" * 60)

    mem = ShortTermMemory(max_messages=10)

    # 模拟对话
    messages = [
        ("user", "你好！"),
        ("assistant", "你好！我是 AI 助手，有什么可以帮助你的？"),
        ("user", "今天天气怎么样？"),
        ("assistant", "请问你在哪个城市？"),
        ("user", "北京"),
        ("assistant", "北京今天晴，25°C"),
    ]

    for role, content in messages:
        mem.add_message(role, content)

    print(f"记忆条目数: {len(mem)}")
    print()

    # 检索
    print("搜索 '天气':")
    for r in mem.search("天气"):
        print(f"  [{r['metadata'].get('role')}]: {r['content'][:60]}")

    print("\n最近 3 条:")
    for r in mem.get_recent(3):
        print(f"  [{r['metadata'].get('role')}]: {r['content'][:60]}")

    # 上下文构建
    print("\n上下文输出:")
    print(mem.get_context())
    print()


def demo_long_term_memory():
    """演示长期记忆"""
    print("=" * 60)
    print("📌 演示 2b：长期记忆（持久化）")
    print("=" * 60)

    mem = LongTermMemory(file_path="/tmp/xyz_memory_demo.json")

    # 添加重要信息
    facts = [
        ("用户叫向阳", 0.9),
        ("向阳喜欢 AI Agent 学习", 0.8),
        ("向阳的框架叫 xyz-agent", 0.7),
        ("今天是 2026-06-16", 0.3),  # 低重要性，会被忽略
    ]

    for content, importance in facts:
        mid = mem.add(content, importance=importance)
        if mid:
            print(f"  ✅ 已保存 [{importance}]: {content[:40]}")
        else:
            print(f"  ⬜ 忽略（重要性 {importance} < 阈值）: {content[:40]}")

    # 搜索
    print("\n搜索 '向阳':")
    for r in mem.search("向阳"):
        print(f"  [{r['importance']}] {r['content']}")

    # 重要记忆
    print("\n最重要的记忆:")
    for r in mem.get_important(3):
        print(f"  [{r['importance']}] {r['content']}")

    # 清理
    mem.clear()
    import os
    if os.path.exists("/tmp/xyz_memory_demo.json"):
        os.remove("/tmp/xyz_memory_demo.json")
    print()


def demo_rag_memory():
    """演示 RAG 记忆"""
    print("=" * 60)
    print("📌 演示 2c：RAG 记忆（TF-IDF 检索）")
    print("=" * 60)

    rag = RAGMemory(chunk_size=200)

    # 添加文档知识
    docs = [
        "人工智能（AI）是计算机科学的一个分支，旨在创建能够模拟人类智能的系统。"
        "AI 包括机器学习、深度学习、自然语言处理等多个子领域。",

        "AI Agent 是能够自主感知环境、制定计划并采取行动的智能体。"
        "Agent 架构通常包括感知、推理、行动三个核心模块。",

        "ReAct 模式是一种结合推理（Reasoning）和行动（Acting）的 Agent 设计模式。"
        "Agent 通过「思考→行动→观察」的循环来完成复杂任务。",

        "向量数据库（如 ChromaDB、Pinecone）专门用于存储和检索向量嵌入，"
        "是实现 RAG（检索增强生成）的关键基础设施。",

        "MCP（Model Context Protocol）是一种标准化的工具调用协议，"
        "允许 AI 模型与外部工具和服务进行交互。",
    ]

    for doc in docs:
        rag.add(doc)

    print(f"文档块数: {len(rag)}")

    # 检索测试
    queries = ["什么是 AI Agent", "ReAct 模式", "向量数据库"]
    for q in queries:
        print(f"\n搜索 '{q}':")
        for r in rag.search(q, limit=2):
            print(f"  相关度 {r['relevance']:.3f}: {r['content'][:60]}...")

    # 上下文构建
    print("\n为 'Agent 设计模式' 构建上下文:")
    print(rag.get_context("Agent 设计模式"))
    print()


def demo_memory_system():
    """演示混合记忆系统"""
    print("=" * 60)
    print("📌 演示 2d：混合记忆系统")
    print("=" * 60)

    ms = MemorySystem()

    # 模拟一个 Agent 会话
    print("🌐 模拟 Agent 会话...")

    # 对话
    ms.add_conversation("user", "帮我查一下ReAct模式是什么")
    ms.add_conversation("assistant", "ReAct是一种结合推理和行动的Agent设计模式...")
    ms.add_conversation("user", "那在Python里怎么实现？")
    ms.add_conversation("assistant", "可以通过循环调用LLM来实现...")

    # 知识
    ms.add_knowledge("用户对Agent实现细节很感兴趣", importance=0.8)
    ms.add_knowledge("用户偏好Python实现", importance=0.7)

    # 文档
    ms.add_document("ReAct模式由Google和普林斯顿大学提出，"
                     "全称是Reasoning + Acting，"
                     "通过Thought→Action→Observation循环来实现复杂推理。")

    print(f"\n记忆统计:")
    print(f"  短期记忆: {len(ms.short_term)} 条消息")
    print(f"  长期记忆: {len(ms.long_term)} 条")
    print(f"  RAG 文档块: {len(ms.rag)} 块")

    # 跨记忆搜索
    print("\n搜索 'ReAct':")
    results = ms.search("ReAct")
    for mem_type, items in results.items():
        if items:
            print(f"  来自 {mem_type}:")
            for item in items:
                print(f"    - {item.get('content', '')[:80]}")

    # 构建上下文
    print("\n完整上下文:")
    ctx = ms.get_context("ReAct实现")
    print(ctx[:300] + "...")
    print()


if __name__ == "__main__":
    import json

    print()
    print("╔══════════════════════════════════════════════╗")
    print("║   xyz-agent 框架 — Step 2 演示             ║")
    print("║   工具系统 + 记忆系统                       ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print(f"框架版本: {__import__('xyz_agent').__version__}")
    print()

    demo_tool_decorator()
    demo_manual_register()
    demo_default_registry()
    demo_short_term_memory()
    demo_long_term_memory()
    demo_rag_memory()
    demo_memory_system()

    print("=" * 60)
    print("✅ Step 2 全部演示完成！")
    print("=" * 60)
