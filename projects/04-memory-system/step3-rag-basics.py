"""
RAG 基础实现 —— Chunking + Embedding + 语义搜索
Step 3 - 检索增强生成
"""

import json
import re
import os
from typing import List, Dict, Optional


# ── Step 1: Chunking（文档分块）────────────────────

class DocumentChunker:
    """
    文档分块器
    支持多种分割策略：固定大小、递归分割、Markdown 结构分割
    """

    @staticmethod
    def fixed_size(text, chunk_size=500, overlap=50):
        """
        固定大小分块
        按字符数切分，相邻块有 overlap 字符重叠
        """
        if len(text) <= chunk_size:
            return [{"text": text, "index": 0}]

        chunks = []
        start = 0
        i = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end]
            if chunk_text:
                chunks.append({"text": chunk_text.strip(), "index": i})
                i += 1
            start = end - overlap

        return chunks

    @staticmethod
    def recursive_split(text, max_chunk_size=500, overlap=50):
        """
        递归分割：先按段落切，不够再按句子切
        保留语义完整性
        """
        if len(text) <= max_chunk_size:
            return [{"text": text.strip(), "index": 0}]

        chunks = []

        # Level 1: 按双换行（段落）切
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        current_chunk = ""
        chunk_index = 0

        for para in paragraphs:
            if len(current_chunk) + len(para) < max_chunk_size:
                current_chunk += para + "\n\n"
            else:
                # 保存当前块
                if current_chunk:
                    chunks.append({
                        "text": current_chunk.strip(),
                        "index": chunk_index
                    })
                    chunk_index += 1

                # Level 2: 如果单个段落超长，按句子切
                if len(para) > max_chunk_size:
                    sentences = re.split(r"(?<=[。！？.!?])", para)
                    for sentence in sentences:
                        if not sentence.strip():
                            continue
                        if len(current_chunk) + len(sentence) < max_chunk_size:
                            current_chunk = sentence
                        else:
                            if current_chunk:
                                chunks.append({
                                    "text": current_chunk.strip(),
                                    "index": chunk_index
                                })
                                chunk_index += 1
                            # 保留 overlap
                            overlap_text = current_chunk[-overlap:] if overlap > 0 and current_chunk else ""
                            current_chunk = overlap_text + sentence
                else:
                    overlap_text = current_chunk[-overlap:] if overlap > 0 and current_chunk else ""
                    current_chunk = overlap_text + para + "\n\n"

        if current_chunk:
            chunks.append({
                "text": current_chunk.strip(),
                "index": chunk_index
            })

        return chunks

    @staticmethod
    def markdown_split(text, max_chunk_size=500):
        """
        按 Markdown 标题结构分块
        保留标题层级信息
        """
        chunks = []
        lines = text.split("\n")

        current_section = ""
        current_title = ""
        section_index = 0

        for line in lines:
            # 检测标题
            title_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if title_match:
                # 保存上一节
                if current_section:
                    chunks.append({
                        "text": current_section.strip(),
                        "title": current_title,
                        "index": section_index
                    })
                    section_index += 1
                    current_section = ""

                # 如果标题层级太深，附加到上一节
                level = len(title_match.group(1))
                if level > 3:
                    current_section = line + "\n"
                else:
                    current_title = title_match.group(2)
                    current_section = line + "\n"
            else:
                current_section += line + "\n"
                # 如果当前块太长，强制切分
                if len(current_section) > max_chunk_size:
                    chunks.append({
                        "text": current_section.strip(),
                        "title": current_title,
                        "index": section_index
                    })
                    section_index += 1
                    current_section = ""

        if current_section:
            chunks.append({
                "text": current_section.strip(),
                "title": current_title,
                "index": section_index
            })

        return chunks


# ── Step 2: Embedding + 语义搜索 ─────────────────────

class SimpleVectorStore:
    """
    简单的内存向量存储
    用字符匹配模拟语义搜索（实际应使用 embeddings）
    """

    def __init__(self):
        self.documents = []  # [{id, text, metadata, vector}]

    def add_document(self, text, metadata=None):
        """添加文档"""
        doc = {
            "id": len(self.documents),
            "text": text,
            "metadata": metadata or {},
        }
        self.documents.append(doc)
        return doc["id"]

    def add_chunks(self, chunks, source="knowledge_base"):
        """批量添加分块结果"""
        for chunk in chunks:
            self.add_document(
                text=chunk["text"],
                metadata={
                    "source": source,
                    "index": chunk["index"],
                    "title": chunk.get("title", ""),
                }
            )

    def _keyword_score(self, query, text):
        """
        关键词匹配得分
        实际场景会用向量相似度（cosine similarity）
        """
        query_lower = query.lower()
        text_lower = text.lower()

        # 完全匹配
        if query_lower in text_lower:
            base_score = 1.0
        else:
            base_score = 0.0

        # 部分匹配（词级别）
        query_words = set(re.findall(r"\w+", query_lower))
        text_words = set(re.findall(r"\w+", text_lower))

        if len(query_words) > 0:
            overlap = len(query_words & text_words)
            word_score = overlap / len(query_words)
        else:
            word_score = 0.0

        return max(base_score, word_score * 0.8)

    def search(self, query, top_k=3):
        """
        搜索最相关的文档块
        返回: [{id, text, metadata, score}]
        """
        scored = []
        for doc in self.documents:
            score = self._keyword_score(query, doc["text"])
            if score > 0:
                scored.append({
                    "id": doc["id"],
                    "text": doc["text"],
                    "metadata": doc["metadata"],
                    "score": round(score, 3)
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def search_with_hybrid(self, query, top_k=3, alpha=0.5):
        """
        混合搜索（语义 + 关键词）
        alpha=1 纯语义，alpha=0 纯关键词
        """
        # 关键词搜索
        keyword_results = self.search(query, top_k * 2)

        # 融合打分（这里用关键词分数模拟，实际应该 + 向量分数）
        combined = {}
        for r in keyword_results:
            combined[r["id"]] = {
                **r,
                "keyword_score": r["score"],
                "semantic_score": r["score"] * 0.9,  # 模拟语义分数
            }

        for item in combined.values():
            item["final_score"] = (
                alpha * item["semantic_score"] +
                (1 - alpha) * item["keyword_score"]
            )

        sorted_results = sorted(
            combined.values(),
            key=lambda x: x["final_score"],
            reverse=True
        )
        return sorted_results[:top_k]

    def stats(self):
        return {
            "total_documents": len(self.documents),
        }


# ── Step 3: 生成（RAG 完整流程）────────────────────

class SimpleRAG:
    """
    简化版 RAG 系统（演示流程，无需实际 LLM/Embedding 调用）
    """

    def __init__(self):
        self.chunker = DocumentChunker()
        self.vector_store = SimpleVectorStore()
        self._load_knowledge_base()

    def _load_knowledge_base(self):
        """加载内置知识库"""
        knowledge_text = """
# Agent 记忆系统

## 短期记忆
短期记忆（Working Memory）是当前 LLM 上下文窗口中的全部信息。
它不是独立存储，而是对话进行的「工作台」。
管理策略包括：滑动窗口、摘要压缩、重要性排序。

## 长期记忆
长期记忆是跨会话持久化的信息存储。
实现方式包括：KV 存储、关系型数据库、向量数据库、文件系统。
核心操作是 CRUD（创建、读取、更新、删除）。

## RAG（检索增强生成）
RAG 包含三个步骤：索引（Chunking + Embedding）→ 检索（语义搜索）→ 生成（LLM + 上下文）。
分块策略有：固定大小、递归分割、语义分割、文档结构分割。
Embedding 模型选型要看语言支持和精度需求。

## 记忆系统架构
记忆分为三层：短期记忆（对话上下文）→ 长期记忆（个人历史）→ RAG（外部知识库）。
三层协同工作，层与层之间通过检索和传递信息。
"""
        chunks = self.chunker.recursive_split(knowledge_text, max_chunk_size=400)
        self.vector_store.add_chunks(chunks, source="memory_system_knowledge")

    def retrieve(self, query, top_k=3):
        """检索相关文档"""
        return self.vector_store.search(query, top_k=top_k)

    def generate_prompt(self, query, retrieved_docs):
        """构造 RAG 提示词"""
        context = "\n\n".join([
            f"[文档 {i+1}] {doc['text']}"
            for i, doc in enumerate(retrieved_docs)
        ])

        prompt = f"""你是一个 AI 助手。请基于以下参考资料回答问题。

参考资料：
{context}

用户问题：{query}

请注意：
1. 如果资料中有明确答案，请引用回答
2. 如果资料中只有部分相关信息，请说明
3. 如果资料中找不到答案，请明确说"资料中没有相关信息"
4. 不要编造答案
"""
        return prompt

    def answer(self, query):
        """完整的 RAG 回答流程（模拟）"""
        print(f"\n📝 用户问题: {query}")
        print(f"{'='*50}")

        # 检索
        docs = self.retrieve(query, top_k=3)
        print(f"\n🔍 检索到 {len(docs)} 个相关文档:")
        for doc in docs:
            print(f"   [{doc['score']}] {doc['text'][:80]}...")

        # 构造 Prompt
        prompt = self.generate_prompt(query, docs)
        print(f"\n📋 构造 Prompt ({len(prompt)} chars)")
        print(f"{'='*40}")
        print(prompt[:500] + "...")

        # 模拟 LLM 回答
        print(f"\n💬 模拟 LLM 回答:")
        if docs:
            # 根据检索结果模拟回答
            best_doc = docs[0]
            print(f"   根据资料，{best_doc['text'][:200]}")
        else:
            print(f"   资料中没有相关信息")

        return prompt


# ── 演示 ──────────────────────────────────────────────

def demo_rag():
    print("=" * 60)
    print("📚 RAG 检索增强生成演示")
    print("=" * 60)

    rag = SimpleRAG()

    # 1. 文档分块演示
    print("\n📦 1. 文档分块演示")
    sample_text = """
# Python 基础

## 列表
列表是 Python 中最常用的数据结构。
可以包含任意类型的元素。
用方括号创建：my_list = [1, 2, 3]

## 字典
字典是键值对集合。
用花括号创建：my_dict = {"name": "Alice"}
通过键访问值：my_dict["name"]

## 元组
元组是不可变的序列。
用小括号创建：my_tuple = (1, 2, 3)
"""
    chunks = rag.chunker.recursive_split(sample_text, max_chunk_size=200)
    print(f"   原文 {len(sample_text)} 字符 → {len(chunks)} 个块")
    for i, c in enumerate(chunks):
        print(f"   块 {i}: {c['text'][:60]}...")

    # 2. 语义搜索演示
    print("\n🔍 2. 语义搜索演示")
    queries = [
        "什么是短期记忆？",
        "长期记忆怎么实现？",
        "RAG 的三个步骤是什么？",
    ]

    for query in queries:
        docs = rag.retrieve(query)
        print(f"\n   Q: {query}")
        if docs:
            print(f"   最佳匹配: {docs[0]['text'][:80]}... (得分: {docs[0]['score']})")
        else:
            print(f"   无匹配结果")

    # 3. 完整 RAG 流程
    print(f"\n{'='*50}")
    print("📋 3. 完整 RAG 流程")
    rag.answer("短期记忆有哪些管理策略？")
    rag.answer("什么是向量数据库？")


if __name__ == "__main__":
    demo_rag()
