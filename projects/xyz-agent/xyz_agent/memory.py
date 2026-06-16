#!/usr/bin/env python3
"""
xyz_agent.memory — 记忆系统

提供统一的记忆接口，三种记忆类型：
  1. 短期记忆（ShortTermMemory） — 会话内的消息历史
  2. 长期记忆（LongTermMemory） — 持久化存储的关键信息
  3. RAG 记忆（RAGMemory） — 向量检索增强

设计原则：
  - 统一接口：add / search / clear
  - 可插拔后端（内存、文件、向量数据库）
  - 混合记忆：自动管理短期→长期转移
"""

import json
import time
import os
import re
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
import hashlib


# ============================================================
# 抽象基类
# ============================================================

class BaseMemory:
    """记忆存储的抽象基类"""

    def add(self, content: str, metadata: Optional[Dict] = None) -> str:
        """添加记忆，返回记忆 ID"""
        raise NotImplementedError

    def search(self, query: str, limit: int = 5) -> List[Dict]:
        """搜索记忆"""
        raise NotImplementedError

    def get_recent(self, limit: int = 5) -> List[Dict]:
        """获取最近记忆"""
        raise NotImplementedError

    def clear(self):
        """清空记忆"""
        raise NotImplementedError

    def __len__(self) -> int:
        raise NotImplementedError


# ============================================================
# 1. 短期记忆（环形缓冲区）
# ============================================================

@dataclass
class ShortTermMemory(BaseMemory):
    """
    短期记忆 — 基于环形缓冲区的会话消息历史

    特点:
      - 固定容量，自动淘汰旧消息
      - 支持自动摘要压缩（当超过容量时）
      - 支持按角色过滤
    """
    max_messages: int = 50
    summarize_fn: Optional[Callable[[List[Dict]], str]] = None

    _messages: deque = field(default_factory=lambda: deque(maxlen=50))
    _summaries: List[str] = field(default_factory=list)

    def __post_init__(self):
        self._messages = deque(maxlen=self.max_messages)

    def add(self, content: str, metadata: Optional[Dict] = None) -> str:
        """添加消息到短期记忆"""
        msg_id = hashlib.md5(
            f"{content}{time.time()}".encode()
        ).hexdigest()[:8]

        msg = {
            "id": msg_id,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {},
        }

        # 检查是否需要压缩
        if len(self._messages) >= self.max_messages - 1:
            self._maybe_summarize()

        self._messages.append(msg)
        return msg_id

    def add_message(self, role: str, content: str) -> str:
        """添加上下文消息（role + content）"""
        return self.add(content, {"role": role})

    def search(self, query: str, limit: int = 5) -> List[Dict]:
        """关键词搜索短期记忆"""
        query_lower = query.lower()
        results = []
        for msg in reversed(self._messages):
            if query_lower in msg["content"].lower():
                results.append(msg)
                if len(results) >= limit:
                    break
        return results

    def get_recent(self, limit: int = 5) -> List[Dict]:
        """获取最近 N 条消息"""
        return list(self._messages)[-limit:]

    def get_messages(self, role: Optional[str] = None) -> List[Dict]:
        """获取所有消息，可选按角色过滤"""
        if role:
            return [
                m for m in self._messages
                if m.get("metadata", {}).get("role") == role
            ]
        return list(self._messages)

    def clear(self):
        self._messages.clear()
        self._summaries.clear()

    def __len__(self) -> int:
        return len(self._messages)

    def _maybe_summarize(self):
        """当短期记忆到达容量时，自动压缩"""
        if self.summarize_fn and len(self._messages) >= 10:
            # 合并最早的一半消息进行摘要
            half = len(self._messages) // 2
            early_msgs = list(self._messages)[:half]
            summary = self.summarize_fn(early_msgs)
            self._summaries.append(f"[摘要 {len(self._summaries) + 1}]: {summary}")
            # 移除已摘要的部分
            for _ in range(half):
                self._messages.popleft()

    def get_context(self, max_tokens: int = 4000) -> str:
        """构建上下文字符串（用于 LLM 提示）"""
        parts = []
        if self._summaries:
            parts.append("【之前对话摘要】\n" + "\n".join(self._summaries[-3:]))
        if self._messages:
            parts.append("【最近对话】")
            for m in self.get_recent(10):
                role = m.get("metadata", {}).get("role", "user")
                content = m["content"][:200]
                parts.append(f"  [{role}]: {content}")
        return "\n".join(parts)


# ============================================================
# 2. 长期记忆（文件持久化）
# ============================================================

@dataclass
class LongTermMemory(BaseMemory):
    """
    长期记忆 — 持久化存储的重要信息

    特点:
      - JSON 文件持久化
      - 自动去重（内容哈希）
      - 重要性评分
      - 到期淘汰
    """
    file_path: str = "memory_store.json"
    max_items: int = 1000
    importance_threshold: float = 0.3

    _items: List[Dict] = field(default_factory=list)
    _dirty: bool = False

    def __post_init__(self):
        self.load()

    def add(
        self,
        content: str,
        metadata: Optional[Dict] = None,
        importance: float = 0.5,
    ) -> str:
        """添加长期记忆"""
        if importance < self.importance_threshold:
            return ""

        # 去重
        content_hash = hashlib.md5(content.encode()).hexdigest()
        for item in self._items:
            if item["hash"] == content_hash:
                item["access_count"] += 1
                item["last_accessed"] = time.time()
                self._dirty = True
                return item["id"]

        # 淘汰（超过上限时移除最不重要的）
        if len(self._items) >= self.max_items:
            self._items.sort(key=lambda x: x["importance"] * x["access_count"])
            self._items = self._items[len(self._items) // 4:]  # 移除后25%

        mem_id = hashlib.md5(f"{content}{time.time()}".encode()).hexdigest()[:12]
        item = {
            "id": mem_id,
            "content": content,
            "hash": content_hash,
            "importance": importance,
            "access_count": 1,
            "created_at": time.time(),
            "last_accessed": time.time(),
            "metadata": metadata or {},
        }
        self._items.append(item)
        self._dirty = True

        if self._dirty and len(self._items) % 10 == 0:
            self.save()

        return mem_id

    def search(self, query: str, limit: int = 5) -> List[Dict]:
        """关键词搜索长期记忆"""
        query_lower = query.lower()
        results = []
        for item in reversed(self._items):
            score = 0
            if query_lower in item["content"].lower():
                score += item["content"].lower().count(query_lower)
            if item.get("metadata"):
                for v in item["metadata"].values():
                    if isinstance(v, str) and query_lower in v.lower():
                        score += 1
            if score > 0:
                results.append({**item, "relevance_score": score})
        # 按相关度排序
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:limit]

    def get_recent(self, limit: int = 5) -> List[Dict]:
        return sorted(
            self._items, key=lambda x: x["created_at"], reverse=True
        )[:limit]

    def get_important(self, limit: int = 5) -> List[Dict]:
        """获取最重要的记忆"""
        return sorted(
            self._items,
            key=lambda x: x["importance"] * x["access_count"],
            reverse=True,
        )[:limit]

    def update_importance(self, mem_id: str, delta: float = 0.1):
        """增加记忆的重要性"""
        for item in self._items:
            if item["id"] == mem_id:
                item["importance"] = min(1.0, item["importance"] + delta)
                item["last_accessed"] = time.time()
                self._dirty = True
                break

    def clear(self):
        self._items.clear()
        self._dirty = True
        self.save()

    def __len__(self) -> int:
        return len(self._items)

    def load(self):
        """从文件加载记忆"""
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, "r") as f:
                    data = json.load(f)
                    self._items = data.get("items", [])
        except (json.JSONDecodeError, IOError):
            self._items = []

    def save(self):
        """保存记忆到文件"""
        try:
            with open(self.file_path, "w") as f:
                json.dump({"items": self._items, "updated_at": time.time()}, f)
            self._dirty = False
        except IOError:
            pass

    def __del__(self):
        if self._dirty:
            self.save()


# ============================================================
# 3. RAG 记忆（内嵌 TF-IDF + 可选向量后端）
# ============================================================

@dataclass
class RAGMemory(BaseMemory):
    """
    RAG 记忆 — 基于检索增强的记忆系统

    特点:
      - 内嵌简单 TF-IDF 检索（零依赖）
      - 支持外部向量数据库后端（chromadb, faiss 等）
      - 文档分块管理
      - 相关性排序
    """
    chunk_size: int = 500
    chunk_overlap: int = 50
    embedding_fn: Optional[Callable[[str], List[float]]] = None

    _docs: List[Dict] = field(default_factory=list)
    _tfidf_index: Dict = field(default_factory=dict)

    def add(
        self,
        content: str,
        metadata: Optional[Dict] = None,
        chunk: bool = True,
    ) -> str:
        """添加文档到 RAG 记忆"""
        doc_id = hashlib.md5(f"{content}{time.time()}".encode()).hexdigest()[:12]

        if chunk and len(content) > self.chunk_size:
            chunks = self._chunk_text(content)
        else:
            chunks = [content]

        chunk_ids = []
        for i, chunk_text in enumerate(chunks):
            cid = f"{doc_id}_{i}"
            self._docs.append({
                "id": cid,
                "content": chunk_text,
                "doc_id": doc_id,
                "chunk_index": i,
                "metadata": metadata or {},
                "timestamp": time.time(),
            })
            chunk_ids.append(cid)

        # 重建 TF-IDF 索引
        self._build_tfidf_index()

        return doc_id

    def search(self, query: str, limit: int = 5) -> List[Dict]:
        """TF-IDF 检索"""
        query_terms = self._tokenize(query)
        if not query_terms or not self._docs:
            return []

        scores = []
        for doc in self._docs:
            score = self._tfidf_score(doc["content"], query_terms)
            if score > 0:
                scores.append({**doc, "relevance": round(score, 4)})

        scores.sort(key=lambda x: x["relevance"], reverse=True)
        return scores[:limit]

    def get_recent(self, limit: int = 5) -> List[Dict]:
        return sorted(
            self._docs, key=lambda x: x["timestamp"], reverse=True
        )[:limit]

    def clear(self):
        self._docs.clear()
        self._tfidf_index.clear()

    def __len__(self) -> int:
        return len(self._docs)

    def get_context(self, query: str, max_chunks: int = 3) -> str:
        """构建 RAG 上下文（用于 LLM 提示嵌入）"""
        results = self.search(query, limit=max_chunks)
        if not results:
            return ""
        parts = ["【相关参考信息】"]
        for i, r in enumerate(results):
            parts.append(f"\n--- 参考 {i+1} ---")
            parts.append(r["content"][:300])
        return "\n".join(parts)

    # ---- 内部方法 ----

    def _chunk_text(self, text: str) -> List[str]:
        """将长文本分块"""
        words = list(text)
        chunks = []
        start = 0
        while start < len(words):
            end = start + self.chunk_size
            chunk = words[start:end]
            chunks.append("".join(chunk))
            start += self.chunk_size - self.chunk_overlap
        return chunks

    def _tokenize(self, text: str) -> List[str]:
        """分词（中文/英文混合）"""
        # 简单分词：按非字母数字分隔
        tokens = re.findall(r'\w+', text.lower())
        # 过滤停用词
        stop_words = {"的", "了", "在", "是", "我", "有", "和", "就",
                      "不", "人", "都", "一", "一个", "上", "也", "很",
                      "到", "说", "要", "去", "你", "会", "着", "没有",
                      "看", "好", "自己", "这", "the", "a", "an", "is",
                      "are", "was", "were", "be", "been", "it", "to"}
        return [t for t in tokens if t not in stop_words and len(t) > 1]

    def _build_tfidf_index(self):
        """构建简单的 TF-IDF 索引"""
        if not self._docs:
            self._tfidf_index = {}
            return

        # 计算 DF（文档频率）
        df: Dict[str, int] = {}
        for doc in self._docs:
            terms = set(self._tokenize(doc["content"]))
            for term in terms:
                df[term] = df.get(term, 0) + 1

        n_docs = len(self._docs)
        self._tfidf_index = {
            term: n_docs / (1 + freq)
            for term, freq in df.items()
        }

    def _tfidf_score(self, text: str, query_terms: List[str]) -> float:
        """计算单个文档的 TF-IDF 分数"""
        terms = self._tokenize(text)
        if not terms:
            return 0.0

        # TF
        tf = {}
        for t in terms:
            tf[t] = tf.get(t, 0) + 1
        max_tf = max(tf.values()) if tf else 1

        score = 0.0
        for qt in query_terms:
            if qt in self._tfidf_index:
                term_tf = tf.get(qt, 0) / max_tf  # 归一化 TF
                idf = self._tfidf_index.get(qt, 1.0)
                score += term_tf * idf

        return score


# ============================================================
# 4. 混合记忆系统
# ============================================================

@dataclass
class MemorySystem:
    """
    混合记忆系统 — 统一管理三种记忆

    自动决策：
      - 短期记忆放对话上下文
      - 重要信息提取到长期记忆
      - 知识文档放入 RAG
    """
    short_term: ShortTermMemory = field(default_factory=ShortTermMemory)
    long_term: LongTermMemory = field(default_factory=LongTermMemory)
    rag: RAGMemory = field(default_factory=RAGMemory)

    def add_conversation(self, role: str, content: str):
        """添加对话消息"""
        # 短期记忆：保留上下文
        self.short_term.add_message(role, content)

    def add_knowledge(self, content: str, metadata: Optional[Dict] = None,
                      importance: float = 0.5):
        """添加知识到长期记忆"""
        self.long_term.add(content, metadata, importance)

    def add_document(self, content: str, metadata: Optional[Dict] = None):
        """添加文档到 RAG"""
        self.rag.add(content, metadata)

    def search(self, query: str, limit: int = 5) -> Dict[str, List]:
        """跨所有记忆系统搜索"""
        return {
            "short_term": self.short_term.search(query, limit),
            "long_term": self.long_term.search(query, limit),
            "rag": self.rag.search(query, limit),
        }

    def get_context(self, query: str) -> str:
        """构建完整的上下文（短期+长期+RAG）"""
        parts = []

        # 短期（最近对话）
        if len(self.short_term) > 0:
            parts.append(self.short_term.get_context())

        # 长期（相关记忆）
        long_results = self.long_term.search(query, limit=3)
        if long_results:
            parts.append("【长期记忆】")
            for r in long_results:
                parts.append(f"  - {r['content'][:200]}")

        # RAG（相关知识）
        rag_context = self.rag.get_context(query, max_chunks=2)
        if rag_context:
            parts.append(rag_context)

        return "\n\n".join(parts)

    def clear(self):
        """清空所有记忆"""
        self.short_term.clear()
        self.long_term.clear()
        self.rag.clear()
