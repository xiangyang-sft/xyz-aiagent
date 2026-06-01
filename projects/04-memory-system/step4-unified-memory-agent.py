"""
三层统一记忆 Agent —— 短期 + 长期 + RAG 综合应用
Step 4 - 完整的记忆增强 Agent
"""

import json
import os
import sys

# 将当前目录加入路径
# 动态导入各模块（文件名含短横线，需用 importlib）
import importlib.util

def _import_step(module_name):
    """从带短横线的文件名导入模块"""
    filepath = os.path.join(os.path.dirname(__file__), f"{module_name}.py")
    if not os.path.exists(filepath):
        return None
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

# 导入各模块（实际独立运行时各 step 可直接运行）
try:
    step1 = _import_step("step1-short-term-memory")
    SlidingWindowMemory = step1.SlidingWindowMemory
    SummaryCompressionMemory = step1.SummaryCompressionMemory
except Exception:
    from step1_short_term_memory import SlidingWindowMemory, SummaryCompressionMemory

try:
    step2 = _import_step("step2-long-term-memory")
    LongTermMemory = step2.LongTermMemory
except Exception:
    from step2_long_term_memory import LongTermMemory

try:
    step3 = _import_step("step3-rag-basics")
    SimpleRAG = step3.SimpleRAG
except Exception:
    from step3_rag_basics import SimpleRAG


class UnifiedMemoryAgent:
    """
    三层统一记忆 Agent
    整合短期、长期记忆和 RAG 检索
    """

    def __init__(self, user_id="default", memory_path="/tmp/unified_memory.json"):
        self.user_id = user_id

        # 短期记忆
        self.short_term = SlidingWindowMemory(max_rounds=20, max_tokens=8000)

        # 长期记忆
        self.long_term = LongTermMemory(path=memory_path)

        # RAG
        self.rag = SimpleRAG()

        # 系统提示
        self.system_prompt = """你是一个智能 AI 助手，拥有三层记忆系统。
- 你能记住当前对话中的信息（短期记忆）
- 你能回忆用户的偏好和历史（长期记忆）
- 你可以在知识库中搜索相关信息（RAG）

请友好、准确地回答用户的问题。"""

    def process_query(self, query):
        """处理一次用户查询"""
        print(f"\n{'='*60}")
        print(f"🧑 用户: {query}")
        print(f"{'='*60}")

        # Step 1: 短期记忆检索
        print(f"\n📋 Step 1: 短期记忆检索")
        short_context = self.short_term.get_context()
        print(f"   当前上下文 {len(short_context)} 条消息")

        # Step 2: 长期记忆检索
        print(f"\n💾 Step 2: 长期记忆检索")
        long_term_info = []

        # 检查用户偏好
        prefs = self.long_term.recall_all(self.user_id)
        if prefs:
            pref_text = "; ".join(f"{k}={v['value']}" for k, v in prefs.items())
            long_term_info.append(f"用户信息: {pref_text}")
            print(f"   找到用户信息: {len(prefs)} 条")

        # 搜索相关历史对话
        convos = self.long_term.search_conversations(
            user_id=self.user_id, keyword=query
        )
        if convos:
            for c in convos:
                long_term_info.append(f"历史对话: {c['title']} — {c['summary']}")
            print(f"   找到相关对话: {len(convos)} 条")

        # 搜索相关事实
        facts = self.long_term.search_facts(keyword=query)
        if facts:
            for f in facts:
                long_term_info.append(f"知识: {f['text']}")
            print(f"   找到相关事实: {len(facts)} 条")

        # Step 3: RAG 检索
        print(f"\n📚 Step 3: RAG 知识库检索")
        rag_docs = self.rag.retrieve(query, top_k=2)
        if rag_docs:
            rag_info = "\n".join(
                f"[资料 {i+1}] {doc['text']}"
                for i, doc in enumerate(rag_docs)
            )
            print(f"   找到 {len(rag_docs)} 个相关文档")

        # Step 4: 构建最终上下文
        print(f"\n🧠 Step 4: 构建 LLM 上下文")

        # 系统提示 + 长期记忆信息
        system_content = self.system_prompt
        if long_term_info:
            system_content += "\n\n## 用户信息\n" + "\n".join(long_term_info)
        if rag_docs:
            system_content += "\n\n## 参考资料\n" + rag_info

        messages = [{"role": "system", "content": system_content}]
        messages.extend(short_context)
        messages.append({"role": "user", "content": query})

        print(f"   上下文共 {len(messages)} 条消息")
        print(f"   系统提示约 {len(system_content)} 字符")
        print(f"   总 Token 估算: {sum(len(m['content']) for m in messages) // 4}")

        # Step 5: 模拟 LLM 回答
        print(f"\n💬 Step 5: LLM 生成回答")
        response = self._simulate_answer(query, long_term_info, rag_docs)
        print(f"   {response}")

        # 更新记忆
        self.short_term.add_message("user", query)
        self.short_term.add_message("assistant", response)

        # 自动保存重要信息到长期记忆
        self._maybe_remember(query, response)

        return response

    def _simulate_answer(self, query, long_term_info, rag_docs):
        """模拟 LLM 回答（实际场景用真实 LLM）"""
        # 模拟：根据记忆层的情况生成不同的回答风格
        has_long_term = len(long_term_info) > 0
        has_rag = len(rag_docs) > 0

        if has_long_term and has_rag:
            return (
                f"你好！我记得你之前的一些信息，并且在知识库中找到了相关的内容。"
                f"关于「{query}」，"
                f"根据资料：{rag_docs[0]['text'][:100]}..."
            )
        elif has_long_term:
            return (
                f"我记得你！根据之前的了解，{long_term_info[0]}。"
                f"关于「{query}」，让我来回答..."
            )
        elif has_rag:
            return (
                f"我在知识库中找到了相关信息。"
                f"关于「{query}」，{rag_docs[0]['text'][:150]}..."
            )
        else:
            return (
                f"这是我们的第一次对话！关于「{query}」，"
                f"我的回答是..."
            )

    def _maybe_remember(self, query, response):
        """根据对话内容自动记忆重要信息"""
        # 简单规则：包含特定关键词时做记忆
        memory_rules = {
            "我听说": "mention",
            "我不": "preference",
            "我喜欢": "preference",
            "我经常": "habit",
            "我的项目": "project",
            "我叫": "name",
            "我是": "identity",
        }

        for keyword, category in memory_rules.items():
            if keyword in query:
                self.long_term.remember_user(self.user_id, f"auto_{category}", query)
                print(f"   📝 自动记忆 [{category}]: {query[:50]}...")
                break

    def start_new_session(self):
        """开始新会话（保留长期记忆，清空短期记忆）"""
        # 保存当前对话摘要
        current_context = self.short_term.get_context()
        if len(current_context) > 2:
            self.long_term.remember_conversation(
                user_id=self.user_id,
                title=f"对话 {len(self.long_term.data['conversations']) + 1}",
                summary=f"{len(current_context)} 条消息",
                messages_count=len(current_context),
            )

        self.short_term.clear()
        print("🔄 已切换到新会话（短期记忆已清空，长期记忆保留）")

    def stats(self):
        """系统状态"""
        return {
            "短期记忆": self.short_term.stats(),
            "长期记忆": self.long_term.stats(),
            "RAG 文档数": self.rag.vector_store.stats()["total_documents"],
        }


# ── 演示 ──────────────────────────────────────────────

def demo_unified_memory():
    print("=" * 60)
    print("🧠 三层统一记忆 Agent 演示")
    print("=" * 60)

    agent = UnifiedMemoryAgent(
        user_id="向阳",
        memory_path="/tmp/demo_unified_agent_memory.json"
    )

    # 预先存入一些用户信息
    agent.long_term.remember_user("向阳", "name", "向阳", confidence=1.0)
    agent.long_term.remember_user("向阳", "preferred_style", "简洁回答，喜欢代码示例")
    agent.long_term.remember_fact("ReAct 是 Google 2022 年提出的 Agent 设计模式")

    # 会话 1：第一次对话
    print(f"\n{'#'*60}")
    print("# 会话 1：第一次对话")
    print(f"{'#'*60}")

    agent.process_query("短期记忆和长期记忆有什么区别？")
    agent.process_query("我喜欢用 Python 和 JavaScript")
    agent.process_query("RAG 中的 Chunking 策略有哪些？")

    # 切换到新会话
    print(f"\n{'#'*60}")
    print("# 切换会话...")
    print(f"{'#'*60}")
    agent.start_new_session()

    # 会话 2：第二次对话，回忆之前的记忆
    print(f"\n{'#'*60}")
    print("# 会话 2：第二次对话（应能回忆上次的信息）")
    print(f"{'#'*60}")

    agent.process_query("你还记得我吗？我之前喜欢用什么语言？")
    agent.process_query("给我讲讲 Chunking 的策略")

    # 统计
    print(f"\n{'='*60}")
    print("📊 记忆系统统计")
    print(f"{'='*60}")
    stats = agent.stats()
    for layer, info in stats.items():
        print(f"\n{layer}:")
        if isinstance(info, dict):
            for k, v in info.items():
                print(f"  {k}: {v}")
        else:
            print(f"  {info}")

    # 清理临时文件
    if os.path.exists("/tmp/demo_unified_agent_memory.json"):
        os.remove("/tmp/demo_unified_agent_memory.json")
    print("\n✅ 演示完成，已清理临时文件")


if __name__ == "__main__":
    demo_unified_memory()
