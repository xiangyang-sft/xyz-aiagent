"""
长期记忆实现 —— JSON 文件存储 + CRUD 操作
Step 2 - 跨会话持久化记忆
"""

import json
import os
from datetime import datetime


class LongTermMemory:
    """
    基于 JSON 文件的长期记忆系统
    支持 CRUD、关键词搜索、过期管理
    """

    def __init__(self, path="long_term_memory.json"):
        self.path = path
        self.data = self._load()

    def _load(self):
        """从文件加载数据"""
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "users": {},
            "conversations": [],
            "facts": [],
            "preferences": {},
        }

    def save(self):
        """保存到文件"""
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    # ── 用户记忆 ─────────────────────────────────────────

    def remember_user(self, user_id, key, value, confidence=1.0):
        """
        记住用户的某个信息
        - 如果已存在，合并更新
        - confidence: 置信度（0-1），用户明确说的=1.0，推理得到的=0.5-0.8
        """
        if user_id not in self.data["users"]:
            self.data["users"][user_id] = {}

        now = datetime.now().isoformat()
        entry = {
            "value": value,
            "confidence": confidence,
            "updated_at": now,
            "created_at": self.data["users"][user_id].get(key, {}).get("created_at", now),
        }

        # 合并逻辑：置信度更高的覆盖
        existing = self.data["users"][user_id].get(key)
        if existing and existing["confidence"] > confidence:
            # 已有更高置信度的记忆，保留旧的但追加新信息
            if isinstance(value, dict) and isinstance(existing["value"], dict):
                existing["value"].update(value)
                existing["updated_at"] = now
            return

        self.data["users"][user_id][key] = entry
        self.save()

    def recall_user(self, user_id, key):
        """回忆用户的某个信息"""
        user_data = self.data["users"].get(user_id, {})
        entry = user_data.get(key)
        if entry:
            return entry["value"]
        return None

    def recall_all(self, user_id):
        """回忆用户的所有信息"""
        return self.data["users"].get(user_id, {})

    def forget_user(self, user_id, key):
        """忘记某个信息"""
        if user_id in self.data["users"] and key in self.data["users"][user_id]:
            del self.data["users"][user_id][key]
            self.save()
            return True
        return False

    # ── 对话记忆 ─────────────────────────────────────────

    def remember_conversation(self, user_id, title, summary, messages_count):
        """记录一次对话"""
        self.data["conversations"].append({
            "user_id": user_id,
            "title": title,
            "summary": summary,
            "messages_count": messages_count,
            "timestamp": datetime.now().isoformat(),
        })
        # 限制保留最近的 100 条对话记录
        if len(self.data["conversations"]) > 100:
            self.data["conversations"] = self.data["conversations"][-100:]
        self.save()

    def search_conversations(self, user_id=None, keyword=None, limit=5):
        """搜索历史对话"""
        results = self.data["conversations"]

        if user_id:
            results = [c for c in results if c["user_id"] == user_id]

        if keyword:
            keyword = keyword.lower()
            results = [
                c for c in results
                if keyword in c["title"].lower() or keyword in c["summary"].lower()
            ]

        # 按时间倒序排列
        results.sort(key=lambda x: x["timestamp"], reverse=True)
        return results[:limit]

    # ── 事实记忆 ─────────────────────────────────────────

    def remember_fact(self, fact_text, tags=None, source="agent"):
        """记录一个事实/知识"""
        self.data["facts"].append({
            "text": fact_text,
            "tags": tags or [],
            "source": source,
            "timestamp": datetime.now().isoformat(),
        })
        if len(self.data["facts"]) > 1000:
            self.data["facts"] = self.data["facts"][-1000:]
        self.save()

    def search_facts(self, keyword=None, tags=None, limit=10):
        """搜索事实"""
        results = self.data["facts"]

        if keyword:
            keyword = keyword.lower()
            results = [
                f for f in results
                if keyword in f["text"].lower()
            ]

        if tags:
            results = [
                f for f in results
                if any(t in f["tags"] for t in tags)
            ]

        results.sort(key=lambda x: x["timestamp"], reverse=True)
        return results[:limit]

    # ── 偏好记忆 ─────────────────────────────────────────

    def remember_preference(self, user_id, category, preference):
        """记录用户偏好"""
        if user_id not in self.data["preferences"]:
            self.data["preferences"][user_id] = {}

        if category not in self.data["preferences"][user_id]:
            self.data["preferences"][user_id][category] = []

        self.data["preferences"][user_id][category].append({
            "value": preference,
            "timestamp": datetime.now().isoformat(),
        })

        # 保留最近 20 条偏好
        if len(self.data["preferences"][user_id][category]) > 20:
            self.data["preferences"][user_id][category] = \
                self.data["preferences"][user_id][category][-20:]

        self.save()

    def get_preferences(self, user_id, category=None):
        """获取用户偏好"""
        user_prefs = self.data["preferences"].get(user_id, {})
        if category:
            return user_prefs.get(category, [])
        return user_prefs

    # ── 维护 ─────────────────────────────────────────────

    def cleanup(self, max_age_days=90):
        """清理超过指定天数的记忆"""
        now = datetime.now()
        cutoff = now.timestamp() - max_age_days * 86400

        # 清理对话记录
        self.data["conversations"] = [
            c for c in self.data["conversations"]
            if datetime.fromisoformat(c["timestamp"]).timestamp() > cutoff
        ]

        # 清理事实
        self.data["facts"] = [
            f for f in self.data["facts"]
            if datetime.fromisoformat(f["timestamp"]).timestamp() > cutoff
        ]

        self.save()

    def stats(self):
        """统计信息"""
        return {
            "users": len(self.data["users"]),
            "conversations": len(self.data["conversations"]),
            "facts": len(self.data["facts"]),
            "preference_categories": sum(
                len(prefs) for prefs in self.data["preferences"].values()
            ),
        }

    def clear(self):
        """清空所有记忆"""
        self.data = {
            "users": {},
            "conversations": [],
            "facts": [],
            "preferences": {},
        }
        self.save()


# ── 演示 ──────────────────────────────────────────────

def demo_long_term_memory():
    print("=" * 60)
    print("💾 长期记忆系统演示")
    print("=" * 60)

    # 使用临时文件，避免污染
    mem = LongTermMemory(path="/tmp/demo_long_term_memory.json")

    # 1. 存储用户信息
    print("\n📝 1. 记忆用户信息")
    mem.remember_user("向阳", "name", "向阳", confidence=1.0)
    mem.remember_user("向阳", "preferred_style", "简洁回答", confidence=0.9)
    mem.remember_user("向阳", "tech_stack", ["Python", "AI Agent"], confidence=0.8)
    print("   ✓ 已存储: name, preferred_style, tech_stack")

    # 2. 存储对话摘要
    print("\n📝 2. 记忆对话摘要")
    mem.remember_conversation(
        "向阳", "第二阶段第二节：工具调用",
        "学习了 Function Calling、MCP 协议、tool_choice 四种模式",
        15
    )
    mem.remember_conversation(
        "向阳", "第二阶段第一节：Agent 设计模式",
        "学习了 ReAct、Plan-Execute、Reflection 三种核心模式",
        12
    )
    print("   ✓ 已存储 2 条对话摘要")

    # 3. 记录事实
    print("\n📝 3. 记录事实")
    mem.remember_fact("ReAct = Reasoning + Acting，由 Google 2022 年提出", ["ReAct", "Agent模式"])
    mem.remember_fact("MCP = Model Context Protocol，Anthropic 推出的开放标准", ["MCP", "工具协议"])
    print("   ✓ 已存储 2 条事实")

    # 4. 记录偏好
    print("\n📝 4. 记录偏好")
    mem.remember_preference("向阳", "response_style", "喜欢用表格和代码示例")
    mem.remember_preference("向阳", "learning_pace", "每天一节课")
    print("   ✓ 已存储 2 条偏好")

    # 5. 检索测试
    print("\n🔍 5. 检索测试")

    name = mem.recall_user("向阳", "name")
    print(f"   回忆用户信息 - name: {name}")

    convos = mem.search_conversations(keyword="工具调用")
    print(f"   搜索对话 - 关键词「工具调用」: 找到 {len(convos)} 条")

    facts = mem.search_facts(keyword="ReAct")
    print(f"   搜索事实 - 关键词「ReAct」: 找到 {len(facts)} 条")
    for fact in facts:
        print(f"     → {fact['text'][:60]}...")

    prefs = mem.get_preferences("向阳", "response_style")
    print(f"   获取偏好 - response_style: {prefs}")

    # 6. 统计
    print(f"\n📊 6. 统计")
    stats = mem.stats()
    for k, v in stats.items():
        print(f"   {k}: {v}")

    # 7. 跨会话模拟
    print("\n🔄 7. 跨会话模拟（第二次对话回忆之前的信息）")
    mem2 = LongTermMemory(path="/tmp/demo_long_term_memory.json")
    remembered = mem2.recall_user("向阳", "preferred_style")
    print(f"   新会话成功回忆: preferred_style = {remembered}")
    print(f"   新对话数: {mem2.stats()['conversations']}")

    # 清理临时文件
    if os.path.exists("/tmp/demo_long_term_memory.json"):
        os.remove("/tmp/demo_long_term_memory.json")
    print("\n✅ 演示完成，已清理临时文件")


if __name__ == "__main__":
    demo_long_term_memory()
