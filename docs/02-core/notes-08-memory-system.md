# 记忆系统：短期/长期记忆与 RAG

> 第 2 阶段 · 第 3 课
>
> 目标：理解 Agent 记忆系统的三大层次（短期记忆、长期记忆、RAG），掌握实现原理与工程选型

---

## Step 1：基础知识 — 为什么 Agent 需要记忆？

### 1.1 LLM 的"过目就忘"困境

Transformer 架构天然有一个限制：**上下文窗口有限且每次对话都是独立的。**

| 问题 | 表现 | 业务影响 |
|------|------|----------|
| **上下文窗口限制** | GPT-4o 约 128K tokens，超长对话会被截断 | 复杂任务中途丢失信息 |
| **跨会话无记忆** | 每次新对话都是"第一次见面" | 不能记住用户偏好、历史操作 |
| **知识截止** | 训练数据有截止日期 | 无法知道训练后发生的事件 |
| **注意力分散** | 长上下文中关键信息被噪声淹没 | 检索准确率下降 |

**一句话：LLM 像一个博学但健忘的天才——需要外挂记忆系统。**

### 1.2 记忆的三层架构

借鉴人类记忆机制，Agent 记忆系统也分三层：

```
                    ┌──────────────────────────┐
                    │    用户交互层            │
                    └──────────────────────────┘
                               │
                    ┌──────────────────────────┐
                    │  短期记忆 (Working Mem)  │  ← 当前对话上下文
                    │   • 本轮对话的内容         │
                    │   • 工具调用的结果          │
                    │   • 中间推理状态            │
                    └──────────────────────────┘
                               │
          ┌──────────────────────────────────────────┐
          │    长期记忆 (Long-term Mem)              │
          │   • 用户偏好、历史记录                    │
          │   • 任务状态、学习笔记                    │
          │   • 外部存储（DB、文件、KV）               │
          └──────────────────────────────────────────┘
                               │
          ┌──────────────────────────────────────────┐
          │    检索增强 (RAG)                        │
          │   • 外部知识库                            │
          │   • 向量数据库（语义搜索）                 │
          │   • 在线数据源（实时检索）                 │
          └──────────────────────────────────────────┘
```

| 层次 | 存储介质 | 生命周期 | 读写频率 | 容量 |
|------|----------|----------|----------|------|
| **短期记忆** | LLM 上下文窗口 | 单次对话 | 极高 | 有限（~128K tokens） |
| **长期记忆** | SQL/Redis/文件 | 跨会话（天/周/月） | 中 | 大（GB 级） |
| **RAG** | 向量数据库/搜索引擎 | 持久（知识库） | 低（按需检索） | 极大（TB 级） |

### 1.3 三种记忆的关系

```
用户说："帮我查一下上次那个项目的进展"

  ↓ 短期记忆：解析意图

  → 需要回忆历史信息
     ↓
  → 长期记忆：查找 "上次那个项目" → 找到 project_id=42
     ↓
  → 需要更详细的背景信息
     ↓
  → RAG：从知识库检索该项目的最新文档
     ↓
  → 结果返回短期记忆 → LLM 综合回答
```

---

## Step 2：核心概念 — 重点深入

### 2.1 短期记忆（Working Memory）

#### 2.1.1 什么是短期记忆？

短期记忆 = **当前 LLM 上下文窗口中的全部信息**。

它不是一个独立的存储系统，而是对话进行中的"工作台"。

#### 2.1.2 短期记忆的管理策略

| 策略 | 描述 | 适用场景 |
|------|------|----------|
| **滑动窗口** | 只保留最近 N 轮对话 | 简单对话，节省 Token |
| **摘要压缩** | 对早期对话做摘要，替代原始内容 | 长对话，保留关键信息 |
| **重要性排序** | 保留关键消息，丢弃噪声 | 复杂任务，关键信息优先 |
| **结构化裁剪** | 按角色/类型选择性保留 | 多角色对话 |

**滑动窗口实现：**

```python
MAX_HISTORY = 10  # 保留最近 10 轮

def trim_messages(messages):
    """保留系统提示 + 最近 N 轮消息"""
    system_msgs = [m for m in messages if m["role"] == "system"]
    history_msgs = [m for m in messages if m["role"] != "system"]
    recent = history_msgs[-MAX_HISTORY * 2:]  # user + assistant 算一轮
    return system_msgs + recent
```

**摘要压缩实现：**

```python
def summarize_history(messages, llm_client):
    """对历史对话做摘要"""
    text = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in messages)
    summary = llm_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "请对以下对话做简洁摘要，保留关键信息、决定和用户偏好。"},
            {"role": "user", "content": text}
        ]
    )
    return summary.choices[0].message.content
```

#### 2.1.3 Token 预算管理

短期记忆的核心约束是 Token。**黄金法则：保留 80% 的关键，裁剪 20% 的冗余。**

常见经验值：
- **系统提示**：通常 500-2000 tokens
- **最近对话**：保留 10-20 轮（约 3000-6000 tokens）
- **工具结果**：做摘要，保留 2000-4000 tokens
- **预留空间**：为 LLM 的输出预留 2000-4000 tokens

```python
def estimate_token_budget(messages, max_total=32000):
    """估算 token 消耗并裁剪"""
    total = count_tokens(messages)  # 粗略估算
    if total <= max_total:
        return messages
    
    # 从最早的非 system 消息开始裁剪
    system_parts = [m for m in messages if m["role"] == "system"]
    non_system = [m for m in messages if m["role"] != "system"]
    
    while count_tokens(system_parts + non_system) > max_total and len(non_system) > 2:
        non_system.pop(0)  # 丢弃最旧的消息
    
    return system_parts + non_system
```

### 2.2 长期记忆（Long-term Memory）

#### 2.2.1 什么是长期记忆？

长期记忆是**跨会话持久化的信息存储**。它让 Agent 在多次对话中记住用户、任务和环境。

#### 2.2.2 长期记忆的实现方式

| 方式 | 存储介质 | 适合什么 | 缺点 |
|------|----------|----------|------|
| **KV 存储** | Redis / JSON 文件 | 用户偏好、简单配置 | 不适合复杂查询 |
| **关系型数据库** | SQLite / PostgreSQL | 结构化数据、历史记录 | 语义搜索弱 |
| **向量数据库** | Chroma / Pinecone / Qdrant | 语义检索 | 部署成本高 |
| **文件系统** | Markdown / JSON / SQLite 文件 | 本地轻量场景 | 并发能力弱 |

#### 2.2.3 长期记忆的核心操作

```
CRUD 原则：
CREATE    — 创建新的记忆条目
READ      — 根据关键词/语义查询记忆
UPDATE    — 更新现有记忆（合并新信息）
DELETE    — 删除过期/错误记忆
```

**简单的 JSON 文件实现：**

```python
import json
import os
from datetime import datetime

class SimpleMemory:
    """基于 JSON 文件的简单长期记忆"""
    
    def __init__(self, path="memory_store.json"):
        self.path = path
        self.data = self._load()
    
    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                return json.load(f)
        return {"users": {}, "conversations": [], "facts": []}
    
    def save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def add_fact(self, key, value, user_id="default"):
        """存储一个事实（用户偏好、配置等）"""
        if user_id not in self.data["users"]:
            self.data["users"][user_id] = {}
        self.data["users"][user_id][key] = {
            "value": value,
            "updated_at": datetime.now().isoformat()
        }
        self.save()
    
    def get_fact(self, key, user_id="default"):
        """读取一个事实"""
        user_data = self.data["users"].get(user_id, {})
        return user_data.get(key)
    
    def search_facts(self, keyword):
        """关键词搜索记忆"""
        results = []
        for uid, facts in self.data["users"].items():
            for key, val in facts.items():
                if keyword.lower() in key.lower() or keyword.lower() in str(val).lower():
                    results.append({"user": uid, "key": key, **val})
        return results
```

#### 2.2.4 记忆合并与更新

长期记忆的一个重要挑战是**信息更新**：

```python
def merge_memory(old, new):
    """
    合并新旧记忆，新信息覆盖旧信息
    策略：逐字段合并，新值覆盖旧值
    """
    if old is None:
        return new
    if isinstance(old, dict) and isinstance(new, dict):
        merged = old.copy()
        for k, v in new.items():
            merged[k] = merge_memory(old.get(k), v)
        return merged
    return new  # 新值覆盖
```

### 2.3 RAG（Retrieval-Augmented Generation）

#### 2.3.1 什么是 RAG？

**检索增强生成**：在 LLM 生成回答之前，先从外部知识库检索相关信息，作为上下文提供给 LLM。

```
用户提问
  ↓
┌─ 检索阶段 ─────────────────────┐
│ 1. 将问题转为向量（Embedding）  │
│ 2. 在向量数据库中语义搜索       │
│ 3. 返回最相似的 Top-K 文档      │
└───────────────────────────────────┘
  ↓
┌─ 增强阶段 ─────────────────────┐
│ 将检索到的文档拼接到 Prompt 中  │
└───────────────────────────────────┘
  ↓
┌─ 生成阶段 ─────────────────────┐
│ LLM 基于"用户问题 + 检索结果"  │
│ 生成最终回答                   │
└───────────────────────────────────┘
```

#### 2.3.2 RAG 的三大步骤详解

**Step 1：索引（Indexing）**

```
文档
  ↓
分割（Chunking）—— 将长文档切成固定大小的块
  ↓
向量化（Embedding）—— 每个块转为向量
  ↓
存储（Indexing）—— 存入向量数据库
```

**Step 2：检索（Retrieval）**

```
用户问题
  ↓
向量化（同样的 Embedding 模型）
  ↓
语义搜索（向量相似度计算）
  ↓
返回 Top-K 最相关文档块
```

**Step 3：生成（Generation）**

```
系统：你是一个 AI 助手，基于以下资料回答问题。
如果资料中找不到答案，请说明不知道。

资料：
{检索到的文档块}

问题：{用户问题}
回答：
```

#### 2.3.3 分块策略（Chunking Strategy）

分块是 RAG 中最关键的调优点之一。

| 策略 | 方法 | 优点 | 缺点 |
|------|------|------|------|
| **固定大小** | 按字符数切块（如 512 chars） | 简单直接 | 可能切断语义 |
| **递归分割** | 按段落 → 句子 → 字符逐级切 | 保留语义完整性 | 块大小不均 |
| **语义分割** | 按话题/主题边界切 | 语义最完整 | 需要 NLP 模型 |
| **文档结构** | 按 Markdown 标题/HTML 标签切 | 结构保留好 | 依赖文档格式 |

**推荐的递归分割实现：**

```python
def recursive_chunk(text, max_chunk_size=500, overlap=50):
    """
    递归分割：优先按段落切，再按句子切
    overlap 让相邻块有重叠，避免丢失上下文
    """
    if len(text) <= max_chunk_size:
        return [text]
    
    # 尝试按段落切
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""
    
    for para in paragraphs:
        if len(current) + len(para) < max_chunk_size:
            current += para + "\n\n"
        else:
            if current:
                chunks.append(current.strip())
            # 保留 overlap 个字符作为重叠
            overlap_text = current[-overlap:] if overlap > 0 else ""
            current = overlap_text + para + "\n\n"
    
    if current:
        chunks.append(current.strip())
    
    return chunks
```

#### 2.3.4 Embedding 模型选型

| 模型 | 维度 | 语言支持 | 适用场景 | 备注 |
|------|------|----------|----------|------|
| `text-embedding-3-small` | 1536 | 多语言 | 通用场景 | OpenAI，性价比高 |
| `text-embedding-3-large` | 3072 | 多语言 | 高精度需求 | OpenAI，成本高 |
| `BAAI/bge-large-zh-v1.5` | 1024 | 中文优秀 | 中文场景 | 开源免费 |
| `intfloat/e5-mistral-7b-instruct` | 4096 | 英文强 | 英文高精度 | 大模型效果好 |
| `sentence-transformers/all-MiniLM-L6-v2` | 384 | 英文 | 轻量快速 | 适合本地部署 |

**选型经验：**
- 中文场景首选 `bge-large-zh-v1.5`
- 多语言场景用 OpenAI `text-embedding-3-small`
- 本地部署用 `all-MiniLM-L6-v2`（速度优先）或 `bge-small-zh-v1.5`（中文）

#### 2.3.5 检索优化

| 技术 | 效果 | 实现难度 |
|------|------|----------|
| **Hybrid Search（混合搜索）** | 语义+关键词结合，效果提升 20-30% | 中 |
| **Rerank（重排序）** | 先用向量粗筛 Top-100，再用模型精排 Top-5 | 中 |
| **Query Rewrite（查询改写）** | 把用户问题改写成更适合检索的形式 | 低 |
| **HyDE（假设文档嵌入）** | 先生成假设答案，再用它检索 | 中 |
| **Multi-Query（多查询）** | 同一个问题生成多个角度去检索 | 高（更多 API 调用） |

**Hybrid Search 示例：**

```python
def hybrid_search(query, top_k=5, alpha=0.5):
    """
    混合搜索：向量相似度 + 关键词匹配
    alpha: 向量搜索权重（0=纯关键词，1=纯语义）
    """
    vector_results = vector_search(query, top_k * 2)       # 语义
    keyword_results = keyword_search(query, top_k * 2)      # 关键词
    
    # 融合打分
    combined = {}
    for doc, score in vector_results:
        combined[doc.id] = {"doc": doc, "vector_score": score, "keyword_score": 0}
    for doc, score in keyword_results:
        if doc.id in combined:
            combined[doc.id]["keyword_score"] = score
        else:
            combined[doc.id] = {"doc": doc, "vector_score": 0, "keyword_score": score}
    
    # 归一化后加权融合
    for item in combined.values():
        item["final_score"] = alpha * item["vector_score"] + (1 - alpha) * item["keyword_score"]
    
    sorted_results = sorted(combined.values(), key=lambda x: x["final_score"], reverse=True)
    return [item["doc"] for item in sorted_results[:top_k]]
```

### 2.4 记忆系统的架构演进

```
Stage 1: 无记忆
  LLM ←→ 用户（每次对话独立）

Stage 2: 短期记忆
  LLM ←上下文窗口→ 用户（单次对话有记忆）

Stage 3: 长期记忆
  LLM ←→ 长期存储（SQLite/Redis/文件）
       ↕
    用户（跨会话记忆）

Stage 4: RAG 增强
  LLM ←→ 向量数据库（外部知识）
       ↕
    长期存储
       ↕
    用户

Stage 5: 多层记忆系统
  ┌──────────┐    ┌────────────┐
  │ Agent    │───→│ 短期工作记忆 │
  └──────────┘    └────────────┘
       │                  │
       ↓                  ↓
  ┌──────────┐    ┌────────────┐
  │ 个人记忆  │    │ 知识库(RAG) │   ← 本文重点
  └──────────┘    └────────────┘
```

---

## Step 3：完整实现 — 多层记忆系统实战

实战代码位于 [`projects/04-memory-system/`](/root/xyz-aiagent/projects/04-memory-system/)：

| 文件 | 内容 | 关键点 |
|------|------|--------|
| `step1-short-term-memory.py` | 短期记忆（滑动窗口 + 摘要压缩） | Token 预算裁剪、摘要策略 |
| `step2-long-term-memory.py` | JSON 文件长期记忆 | CRUD 操作、跨会话记忆 |
| `step3-rag-basics.py` | RAG 基础实现 | Chunking + Embedding + 语义搜索 |
| `step4-unified-memory-agent.py` | 三层统一 Agent | 短期+长期+RAG 综合应用 |

### 运行方式

```bash
cd /root/xyz-aiagent/projects/04-memory-system/
pip install openai chromadb sentence-transformers
export OPENAI_API_KEY="your-key"
python step1-short-term-memory.py
python step2-long-term-memory.py
python step3-rag-basics.py
python step4-unified-memory-agent.py
```

---

## 🎯 面试题（10 道 — 覆盖原理、实现到架构设计）

### Q1：短期记忆和长期记忆的本质区别是什么？

**要点：**
- **短期记忆** = LLM 上下文窗口中的临时信息，**对话结束后就消失**
- **长期记忆** = 持久化到外部存储（DB/文件/向量库），**跨会话保留**

**类比：** 短期记忆是你手上的便签纸，用完就丢；长期记忆是你的笔记本，下次还能翻到。

**工程上的关键区别：** 短期记忆是**隐式的**（不需要额外存储操作），长期记忆需要**显式的读写接口**。

### Q2：滑动窗口和摘要压缩两种短期记忆策略怎么选？

| 场景 | 推荐策略 | 原因 |
|------|----------|------|
| 简单问答 | 滑动窗口 | 实现简单，Token 可控 |
| 长对话（10+ 轮） | 滑动窗口 + 摘要 | 保留关键信息 |
| 复杂推理任务 | 重要性排序 | 关键细节不能丢 |
| 客服对话 | 摘要压缩 | 保留意图和决定即可 |

**经验规则：** 如果对话超过 20 轮或消耗超过 60% 的上下文窗口，就应该做摘要压缩。

### Q3：长期记忆的 CRUD 操作中，Update 有什么特殊挑战？

**三个核心挑战：**

1. **版本冲突** — 用户上次说"喜欢简洁回答"，这次说"详细一点"，以哪个为准？
   - 解决方案：**总是以最新为准**，但保留旧版本用于分析偏好变化

2. **信息合并** — 用户在不同时间提到多个偏好，如何合并？
   - 解决方案：逐字段合并，新值覆盖旧值

3. **记忆衰减** — 一年前的信息现在还有效吗？
   - 解决方案：给记忆加时间戳和置信度，定期清理

```python
memory_entry = {
    "value": "喜欢简洁回答",
    "updated_at": "2026-06-01T10:00:00",
    "confidence": 0.9,        # 置信度（0-1）
    "source": "user_said",     # 来源：用户明确说 / 推理得出
    "expires_at": None         # 过期时间，None=永不过期
}
```

### Q4：RAG 中的 Chunking 策略如何影响检索质量？

**关键认识：块的大小和切割方式直接决定检索质量。**

| 块大小 | 优点 | 缺点 |
|--------|------|------|
| **太小（<200 chars）** | 检索精度高 | 缺乏上下文，难以理解 |
| **合适（300-800 chars）** | 平衡 | 推荐大多数场景 |
| **太大（>2000 chars）** | 上下文完整 | 噪声多，精确度低 |

**最佳实践：**
- 技术文档：按 Markdown 标题切块（结构完整）
- 对话记录：按话题边界切块（语义完整）
- 代码：按函数/类切块（逻辑完整）
- 通用策略：递归分割，块大小 500-800 chars，overlap 50-100 chars

### Q5：Embedding 模型怎么选？必须用和 LLM 相同的模型吗？

**不需要。** Embedding 模型和 LLM 是独立的。

**选型三原则：**

1. **语言匹配** — 中文文档用中文 Embedding 模型（如 `bge-large-zh-v1.5`）
2. **维度匹配** — 向量的维度影响存储成本和检索速度
3. **精度匹配** — 不是越贵越好，够用就行

**经验建议：**
- 个人项目/原型 → `text-embedding-3-small`（便宜又好用）
- 中文生产环境 → `bge-large-zh-v1.5`（开源免费）
- 英文高精度 → `intfloat/e5-mistral-7b-instruct`
- 本地离线 → `all-MiniLM-L6-v2` 或 `bge-small-zh-v1.5`

### Q6：RAG 检索回来的文档块太多或太少怎么办？

**检索太多（高召回低精度）：**
- 原因：Top-K 太大，或 Embedding 模型区分度不够
- 方案：加入 **Rerank** 重排序，先召回 Top-50 再精排到 Top-3

**检索太少（低召回）：**
- 原因：Chunk 太小、Embedding 不够好、查询不精确
- 方案：1. 放大 Chunk Size 2. 用 Hybrid Search 3. **Query Rewrite**

**Query Rewrite 示例：**
```python
def rewrite_query(user_query, llm_client):
    """把用户口语化问题改写成适合检索的形式"""
    response = llm_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "将用户问题改写成适合知识库检索的关键词查询。"},
            {"role": "user", "content": user_query}
        ]
    )
    return response.choices[0].message.content
```

### Q7：RAG 中怎么防止"检索噪音"污染 LLM 的回答？

**检索噪音 = 不相关或部分相关的文档被送入上下文，导致 LLM 被误导。**

**防治策略：**

| 策略 | 做法 | 效果 |
|------|------|------|
| **相似度阈值** | 低于 0.7 分的文档丢弃 | 最基础，效果好 |
| **Rerank 精排** | 用专门的模型重排序 | 效果最好但成本高 |
| **Prompt 约束** | 告诉 LLM"只在有明确证据时引用" | 零成本，必做 |
| **多轮验证** | 检索结果让另一个 LLM 验证相关性 | 高成本，关键场景用 |

**Prompt 约束示例：**
```
你是一个 AI 助手。请基于以下资料回答问题。

重要规则：
1. 如果资料中有明确答案，请引用回答
2. 如果资料中只有部分相关信息，说明"根据资料，..."
3. 如果资料中找不到答案，请说"资料中没有相关信息"
4. 不要编造答案，不要使用资料外的信息

资料：
{检索到的文档}

问题：{用户问题}
```

### Q8：多层记忆系统中，Agent 如何决定用哪一层记忆？

**决策流程：**

```
用户输入
  ↓
Step 1: 短期记忆检索（当前上下文）
  → 如果能在已有上下文找到答案 → 直接回答
  ↓ 找不到
Step 2: 长期记忆检索（用户历史、偏好）
  → 如果找到相关历史记录 → 带回上下文
  ↓ 需要更多信息
Step 3: RAG 检索（外部知识库）
  → 如果找到 → 带回上下文
  ↓ 找不到
Step 4: 在线搜索（实时信息）
  → 作为最后手段
```

**实现示例：**
```python
def agent_with_memory(query, short_term, long_term, rag):
    """多层记忆检索的 Agent"""
    
    # Step 1: 检查短期记忆
    context = short_term.get_current_context()
    
    # Step 2: 检查长期记忆
    user_prefs = long_term.query(query)
    if user_prefs:
        context.append({"role": "system", "content": f"用户偏好：{user_prefs}"})
    
    # Step 3: RAG 检索
    if needs_external_knowledge(query):
        docs = rag.retrieve(query)
        if docs:
            context.append({"role": "system", "content": f"参考资料：{docs}"})
    
    # Step 4: LLM 生成
    return llm.generate(context)
```

### Q9：向量数据库的选型建议？Chroma vs Pinecone vs Qdrant？

| 数据库 | 部署方式 | 适合场景 | 优点 | 缺点 |
|--------|----------|----------|------|------|
| **Chroma** | 本地/嵌入 | 原型、个人项目 | 零配置，Python 原生 | 生产规模有限 |
| **Pinecone** | 云托管 | 生产环境 | 稳定、可扩展、免运维 | 付费、成本高 |
| **Qdrant** | 本地/Docker/云 | 中小到生产均可 | Rust 实现，性能好 | 需要运维 |
| **Milvus** | 分布式 | 大规模生产（亿级） | 可扩展性强 | 部署复杂 |
| **pgvector** | PostgreSQL 插件 | 已有 PG 的场景 | 不需要额外 DB | 性能中等 |

**推荐：**
- 学习/原型 → **Chroma**
- 个人生产 → **Qdrant**（Docker 一键部署）
- 公司生产 → **Pinecone**（省心）或 **Milvus**（大规模自建）

### Q10：如何测试和评估记忆系统的效果？

**三层测试法：**

| 层级 | 测试内容 | 方法 | 指标 |
|------|----------|------|------|
| **短期记忆** | Token 管控、信息保留率 | 模拟长对话，验证关键信息是否保留 | 信息保留率 >95%，Token 节约 >30% |
| **长期记忆** | CRUD 正确性、跨会话一致性 | 跨多轮对话存储和检索 | 读写延迟 <50ms，数据一致率 100% |
| **RAG** | 检索质量、端到端回答质量 | 预标注测试集，计算指标 | 见下方详细指标 |

**RAG 评估指标：**

| 指标 | 定义 | 目标值 |
|------|------|--------|
| **检索命中率** | 正确文档是否在 Top-K 中 | Top-5 >90% |
| **MRR（平均倒数排名）** | 正确文档排名的倒数均值 | >0.8 |
| **NDCG（归一化折损累计增益）** | 考虑排名的相关性 | >0.85 |
| **回答准确率** | LLM 最终回答是否正确 | >85% |
| **幻觉率** | 回答是否基于检索到的内容 | <5% |

**常用工具：** `RAGAS`、`LangSmith`、`TruLens`

---

## 核心认识

1. **记忆是 Agent 从"对话机器人"升级为"智能助手"的关键** — 没有记忆的 Agent 每次都是第一次见面
2. **不要过度设计** — 大部分场景先做短期记忆就够，长期再用 JSON 文件，最后才上向量库
3. **RAG 的瓶颈往往不在模型，而在 Chunking 和检索策略** — 先优化分块和检索再换模型
4. **记忆系统需要持续维护** — 过期记忆比没有记忆更糟（会误导 Agent）
5. **Token 是成本，记忆是功能** — 在成本和功能之间找到平衡

---

## 第二阶段进度

| # | 内容 | 状态 |
|---|------|------|
| 1 | Agent 核心设计模式（ReAct、Plan-Execute、Reflection） | ✅ |
| 2 | 工具调用（Function Calling、Tool Use） | ✅ |
| 3 | **记忆系统（短期/长期记忆、RAG）** | **✅ 本课** |
| 4 | 多 Agent 协作 | ⏳ 下一课 |
| 5 | 动手：完整单 Agent 应用 | 待学习 |
