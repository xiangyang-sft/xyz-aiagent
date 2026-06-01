"""
短期记忆实现 —— 滑动窗口 + 摘要压缩
Step 1 - 管理对话上下文的 Token 预算
"""

import json
from datetime import datetime


# ── 滑动窗口管理 ──────────────────────────────────────

class SlidingWindowMemory:
    """
    滑动窗口短期记忆
    只保留最近的 N 轮对话，超出的部分丢弃
    """

    def __init__(self, max_rounds=10, max_tokens=8000):
        self.max_rounds = max_rounds
        self.max_tokens = max_tokens
        self.messages = []

    def add_message(self, role, content):
        """添加一条消息"""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        self._trim()

    def _trim(self):
        """裁剪超出部分"""
        # 按轮数裁剪
        system_msgs = [m for m in self.messages if m["role"] == "system"]
        non_system = [m for m in self.messages if m["role"] != "system"]

        while len(non_system) > self.max_rounds * 2:
            non_system.pop(0)

        self.messages = system_msgs + non_system

        # 按 Token 数裁剪（粗略估算：1 token ≈ 4 字符）
        total_chars = sum(len(m["content"]) for m in self.messages)
        max_chars = self.max_tokens * 4

        while total_chars > max_chars and len(non_system) > 2:
            removed = non_system.pop(0)
            total_chars -= len(removed["content"])
            self.messages = system_msgs + non_system

    def get_context(self):
        """获取当前上下文"""
        return [{"role": m["role"], "content": m["content"]} for m in self.messages]

    def clear(self):
        """清空短期记忆"""
        self.messages = []

    def stats(self):
        """统计信息"""
        return {
            "total_messages": len(self.messages),
            "total_chars": sum(len(m["content"]) for m in self.messages),
            "estimated_tokens": sum(len(m["content"]) for m in self.messages) // 4,
            "max_rounds": self.max_rounds,
        }


# ── 摘要压缩管理 ─────────────────────────────────────

class SummaryCompressionMemory:
    """
    摘要压缩短期记忆
    当对话过长时，对早期内容做摘要，压缩 Token 占用
    """

    def __init__(self, max_tokens=8000, llm_client=None):
        self.max_tokens = max_tokens
        self.llm_client = llm_client
        self.summary = ""  # 压缩后的历史摘要
        self.recent_messages = []  # 最近未压缩的消息
        self.summary_threshold = max_tokens * 0.6  # 超过 60% 触发压缩

    def add_message(self, role, content):
        """添加一条消息"""
        self.recent_messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        self._maybe_compress()

    def _maybe_compress(self):
        """检查是否需要压缩"""
        total_chars = sum(len(m["content"]) for m in self.recent_messages)
        if total_chars > self.summary_threshold * 4:
            self._compress()

    def _compress(self):
        """压缩早期的消息成为摘要"""
        if not self.recent_messages:
            return

        # 保留最近 3 轮不压缩
        keep_count = min(6, len(self.recent_messages))
        to_compress = self.recent_messages[:-keep_count]
        self.recent_messages = self.recent_messages[-keep_count:]

        if self.llm_client:
            # 用 LLM 做摘要（模拟实现）
            text = "\n".join(
                f"{m['role']}: {m['content'][:200]}"
                for m in to_compress
            )
            new_summary = f"[压缩摘要] 从 {len(to_compress)} 条消息中提取: {text[:300]}..."
            self.summary = new_summary if not self.summary else f"{self.summary}\n{new_summary}"
        else:
            # 没有 LLM 时的简单摘要策略
            key_points = []
            for m in to_compress:
                if m["role"] == "assistant" and len(m["content"]) > 50:
                    key_points.append(m["content"][:100])
            self.summary = (
                (self.summary + "\n" if self.summary else "") +
                f"[压缩摘要] 省略 {len(to_compress)} 条消息。关键内容：{' | '.join(key_points[:3])}"
            )

    def get_context(self):
        """获取完整上下文（摘要 + 最近消息）"""
        context = []
        if self.summary:
            context.append({
                "role": "system",
                "content": f"以下是历史对话摘要：\n{self.summary}"
            })
        context.extend(
            {"role": m["role"], "content": m["content"]}
            for m in self.recent_messages
        )
        return context

    def stats(self):
        """统计信息"""
        total_chars = sum(len(m["content"]) for m in self.recent_messages)
        return {
            "summary_length": len(self.summary),
            "recent_messages": len(self.recent_messages),
            "recent_chars": total_chars,
            "estimated_tokens": total_chars // 4,
            "compression_ratio": (
                self.summary_threshold * 4 / total_chars
                if total_chars > 0 else 1
            )
        }


# ── 演示 ──────────────────────────────────────────────

def demo_sliding_window():
    """演示滑动窗口保存最近 N 轮"""
    print("=" * 60)
    print("📋 滑动窗口短期记忆演示")
    print("=" * 60)

    mem = SlidingWindowMemory(max_rounds=3, max_tokens=4000)

    # 模拟 6 轮对话
    dialogues = [
        ("user", "你好，今天天气怎么样？"),
        ("assistant", "你好！今天天气晴朗，气温 25°C。"),
        ("user", "帮我查一下 Python 列表推导式的用法"),
        ("assistant", "列表推导式是 Python 创建列表的简洁语法：[x**2 for x in range(10)]"),
        ("user", "那 Lambda 函数呢？"),
        ("assistant", "Lambda 是匿名函数，如 lambda x: x * 2"),
        ("user", "我记得之前问过天气，现在还想知道"),
        ("assistant", "刚才说了今天天气晴朗，25°C。"),
    ]

    for i, (role, content) in enumerate(dialogues, 1):
        mem.add_message(role, content)
        print(f"\n📝 第 {i} 轮 [{role}]: {content[:50]}...")

    print(f"\n{'='*40}")
    print("📊 记忆状态:")
    stats = mem.stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")

    print(f"\n📋 当前上下文中的消息数: {len(mem.get_context())}")
    print("（最早的消息已经被裁剪掉）")


def demo_summary_compression():
    """演示摘要压缩"""
    print("\n" + "=" * 60)
    print("📋 摘要压缩短期记忆演示")
    print("=" * 60)

    mem = SummaryCompressionMemory(max_tokens=2000)

    # 模拟一个长对话
    for i in range(8):
        mem.add_message("user", f"这是第 {i+1} 个问题：今天的学习内容是什么？")
        mem.add_message(
            "assistant",
            f"今天我们学习了记忆系统的第 {i+1} 部分。"
            f"这部分内容涵盖了关于 Agent 记忆的重要概念。"
            f"我们深入讨论了多层记忆架构的设计思路..."
        )

    print(f"\n📊 压缩后状态:")
    stats = mem.stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")

    context = mem.get_context()
    print(f"\n📋 返回给 LLM 的上下文包含 {len(context)} 条消息")
    for msg in context:
        content_preview = msg["content"][:100]
        print(f"  [{msg['role']}] {content_preview}...")


if __name__ == "__main__":
    demo_sliding_window()
    demo_summary_compression()
