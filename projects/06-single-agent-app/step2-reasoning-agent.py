#!/usr/bin/env python3
"""
Step 2: 推理增强 Agent — 带记忆和反思

在 step1 基础上增加：
- 长期记忆（JSON 文件持久化）
- 反思机制（自我检查输出质量）
- 更多工具（笔记管理、文件操作）
- 死循环检测

学习目标：
- 掌握记忆持久化的工程实现
- 理解反思机制如何提升输出质量
- 学习死循环检测和错误处理
"""

import json
import os
import math
import datetime
import hashlib
import re

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "your-api-key"),
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "agent_data")
os.makedirs(DATA_DIR, exist_ok=True)
MEMORY_FILE = os.path.join(DATA_DIR, "memory.json")


# ═══════════════════════════════════════════════════════════════
# 1. 长期记忆系统
# ═══════════════════════════════════════════════════════════════

class LongTermMemory:
    """基于 JSON 文件的长期记忆"""

    def __init__(self, filepath: str = MEMORY_FILE):
        self.filepath = filepath
        self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, "r") as f:
                self.data = json.load(f)
        else:
            self.data = {
                "facts": [],        # 用户信息/偏好
                "conversations": [], # 对话摘要
                "notes": [],        # 保存的笔记
            }
            self._save()

    def _save(self):
        with open(self.filepath, "w") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def remember(self, category: str, content: str, tags: list = None):
        """记住一条信息"""
        entry = {
            "id": hashlib.md5(content.encode()).hexdigest()[:8],
            "content": content,
            "tags": tags or [],
            "timestamp": datetime.datetime.now().isoformat(),
        }
        if category in self.data:
            # 去重：相同内容不重复存储
            for existing in self.data[category]:
                if existing["content"] == content:
                    return
            self.data[category].append(entry)
            self._save()

    def recall(self, query: str, category: str = None, limit: int = 5) -> list:
        """检索记忆（基于关键词匹配）"""
        query_lower = query.lower()
        results = []

        categories = [category] if category else self.data.keys()
        for cat in categories:
            for entry in self.data.get(cat, []):
                if query_lower in entry["content"].lower():
                    results.append({**entry, "category": cat})
                else:
                    for tag in entry.get("tags", []):
                        if query_lower in tag.lower():
                            results.append({**entry, "category": cat})
                            break

        return results[:limit]

    def get_context(self, query: str) -> str:
        """获取格式化的记忆上下文"""
        results = self.recall(query)
        if not results:
            return ""

        lines = ["📖 相关信息："]
        for r in results:
            lines.append(f"  [{r['category']}] {r['content']}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 2. 工具定义（增加笔记管理和文件操作）
# ═══════════════════════════════════════════════════════════════

NOTES_DIR = os.path.join(DATA_DIR, "notes")
os.makedirs(NOTES_DIR, exist_ok=True)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "执行数学计算，支持 + - * / ** sqrt sin cos pi e",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式"},
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "获取当前日期和时间",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_note",
            "description": "创建一条笔记",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "笔记标题"},
                    "content": {"type": "string", "description": "笔记内容"},
                },
                "required": ["title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_notes",
            "description": "搜索已保存的笔记",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "搜索关键词"},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_notes",
            "description": "列出所有笔记标题",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取指定文件的内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                },
                "required": ["path"],
            },
        },
    },
]

# 安全路径白名单
ALLOWED_PATHS = [
    os.path.expanduser("~"),
    DATA_DIR,
]


def is_safe_path(path: str) -> bool:
    """检查路径是否在白名单内"""
    abs_path = os.path.abspath(os.path.expanduser(path))
    return any(abs_path.startswith(allowed) for allowed in ALLOWED_PATHS)


def execute_tool(name: str, args: dict) -> str:
    """执行工具并返回结果"""
    try:
        if name == "calculate":
            expr = args["expression"]
            allowed = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
                      "pi": math.pi, "e": math.e, "abs": abs, "round": round}
            result = eval(expr, {"__builtins__": {}}, allowed)
            return json.dumps({"success": True, "result": result}, ensure_ascii=False)

        elif name == "get_time":
            now = datetime.datetime.now()
            return json.dumps({
                "success": True,
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "weekday": now.strftime("%A"),
            }, ensure_ascii=False)

        elif name == "create_note":
            title = args["title"]
            content = args["content"]
            safe_name = re.sub(r'[^\w\-]', '_', title)[:50]
            filepath = os.path.join(NOTES_DIR, f"{safe_name}.md")
            with open(filepath, "w") as f:
                f.write(f"# {title}\n\n{content}\n")
            return json.dumps({"success": True, "path": filepath}, ensure_ascii=False)

        elif name == "search_notes":
            keyword = args["keyword"].lower()
            results = []
            for fname in os.listdir(NOTES_DIR):
                if fname.endswith(".md"):
                    fpath = os.path.join(NOTES_DIR, fname)
                    with open(fpath) as f:
                        content = f.read()
                    if keyword in content.lower():
                        results.append({"file": fname, "title": fname.replace(".md", "").replace("_", " ")})
            return json.dumps({"success": True, "results": results}, ensure_ascii=False)

        elif name == "list_notes":
            notes = []
            for fname in os.listdir(NOTES_DIR):
                if fname.endswith(".md"):
                    fpath = os.path.join(NOTES_DIR, fname)
                    size = os.path.getsize(fpath)
                    notes.append({"title": fname.replace(".md", "").replace("_", " "), "size": size})
            return json.dumps({"success": True, "notes": notes}, ensure_ascii=False)

        elif name == "read_file":
            path = args["path"]
            if not is_safe_path(path):
                return json.dumps({"success": False, "error": "路径不在白名单中"}, ensure_ascii=False)
            if not os.path.exists(path):
                return json.dumps({"success": False, "error": "文件不存在"}, ensure_ascii=False)
            with open(path) as f:
                content = f.read()
            return json.dumps({"success": True, "content": content[:2000], "truncated": len(content) > 2000},
                           ensure_ascii=False)

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# 3. ReAct 循环 + 记忆 + 反思
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """你是一个智能 AI 助手，具备记忆和反思能力。

【工作流程】
1. 思考（Thought）：理解用户需求，规划执行步骤
2. 行动（Action）：选择合适的工具并调用
3. 观察（Observation）：分析工具返回结果
4. 反思（Reflection）：检查结果是否合理，是否需要补充
5. 回答（Answer）：给出最终回答

【工具使用原则】
- 数学计算 → calculate
- 时间日期 → get_time
- 保存信息 → create_note
- 查找笔记 → search_notes
- 列出笔记 → list_notes
- 读取文件 → read_file

【反思规则】
- 每次回答前检查：我的回答是否完整回答了用户问题？
- 如果工具返回错误，尝试用其他方式解决
- 如果信息不足，向用户说明

【回答风格】
- 简洁清晰，用表格/列表呈现结构化信息
- 计算题给出计算过程和结果
- 信息查询给出来源和关键点"""


class ReasoningAgent:
    """推理增强 Agent"""

    def __init__(self):
        self.memory = LongTermMemory()
        self.step_count = 0

    def _check_loop(self, history: list) -> bool:
        """检测死循环：连续 3 次相同工具调用"""
        calls = [m for m in history
                if isinstance(m, dict) and m.get("role") == "assistant"
                and hasattr(m, "tool_calls") and m.tool_calls]
        if len(calls) >= 3:
            last_three = [c.tool_calls[0].function.name for c in calls[-3:]]
            if len(set(last_three)) == 1:
                return True
        return False

    def run(self, user_input: str, max_steps: int = 15) -> str:
        """运行 Agent"""
        self.step_count = 0

        # 加载记忆上下文
        memory_context = self.memory.get_context(user_input)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]

        if memory_context:
            messages.append({"role": "system", "content": f"## 相关记忆\n{memory_context}"})

        messages.append({"role": "user", "content": user_input})

        print(f"\n  📖 加载记忆: {len(memory_context)} 字符")

        for step in range(max_steps):
            self.step_count = step + 1
            print(f"  [Step {step + 1}] 推理中...")

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.3,
            )

            msg = response.choices[0].message

            # 死循环检测
            messages.append(msg)
            if self._check_loop(messages):
                print("  ⚠ 检测到死循环，强制停止")
                messages.append({
                    "role": "user",
                    "content": "你已经连续三次调用同一个工具，请直接给出回答，不要再调用工具。",
                })
                continue

            if msg.tool_calls:
                for tc in msg.tool_calls:
                    func_name = tc.function.name
                    func_args = json.loads(tc.function.arguments)
                    print(f"  → 工具: {func_name}({json.dumps(func_args, ensure_ascii=False)[:60]})")

                    result = execute_tool(func_name, func_args)
                    print(f"  ← {result[:80]}...")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })

                    # 将重要信息存入长期记忆
                    if func_name == "create_note":
                        self.memory.remember("notes", f"创建了笔记: {func_args.get('title', '')}")
                    elif func_name == "calculate":
                        self.memory.remember("facts", f"计算: {func_args.get('expression', '')} = {result[:50]}")
            else:
                # 最终回答
                answer = msg.content

                # 反思：检查回答质量
                reflection = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "你是质量审查员。检查以下回答是否完整、准确、清晰。"
                         "如果满意回答 OK，否则说明问题。"},
                        {"role": "user", "content": f"用户问题: {user_input}\n\nAgent 回答: {answer}"},
                    ],
                    temperature=0.2,
                )
                reflection_result = reflection.choices[0].message.content

                if "OK" in reflection_result or "满意" in reflection_result:
                    print(f"  ✓ 反思通过")
                else:
                    print(f"  ⚠ 反思建议改进: {reflection_result[:100]}...")

                # 保存对话摘要到长期记忆
                summary = f"用户问了: {user_input[:50]}... Agent 回答并完成了请求"
                self.memory.remember("conversations", summary)

                return answer

        return "⚠️ 已达到最大步骤限制，请简化问题或重试。"


# ═══════════════════════════════════════════════════════════════
# 4. 主程序
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 55)
    print("  🧠 推理增强 Agent（带记忆 + 反思）")
    print("=" * 55)

    agent = ReasoningAgent()

    # 初始化一些笔记
    print("\n📝 初始化示例笔记...")
    agent.memory.remember("facts", "用户向阳是一名 AI Agent 学习者", ["用户", "向阳"])
    agent.memory.remember("notes", "今天学习了多 Agent 协作", ["学习", "Agent"])

    test_questions = [
        "帮我算一下 2^10 等于多少？记住这个结果",
        "我之前说过我喜欢学什么？",
        "帮我创建一条笔记，标题是「计算器用法」，内容是支持加减乘除和幂运算",
        "列出我所有的笔记",
        "今天星期几？",
    ]

    for q in test_questions:
        print(f"\n{'─' * 55}")
        print(f"🧑 用户: {q}")
        answer = agent.run(q)
        print(f"\n🤖 Agent: {answer}")
        print(f"   (共 {agent.step_count} 步)")

    print(f"\n{'=' * 55}")
    print("  ✅ 推理增强 Agent 演示完成")
    print("=" * 55)
