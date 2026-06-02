#!/usr/bin/env python3
"""
Step 3: 完整个人助手 Agent — CLI 交互式应用

在 step2 基础上增加：
- 交互式 CLI（持续对话）
- RAG 知识库检索（基于本地文件）
- 更好的错误处理与降级
- 用户配置管理
- 对话历史保存/恢复

学习目标：
- 理解生产级 Agent 的完整架构
- 掌握 CLI 交互式应用的开发
- 学习 RAG 与 Agent 的整合
"""

import json
import os
import math
import datetime
import hashlib
import re
import sys
import glob

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "your-api-key"),
)

# ═══════════════════════════════════════════════════════════════
# 数据目录和配置
# ═══════════════════════════════════════════════════════════════

APP_DIR = os.path.join(os.path.dirname(__file__), "agent_data")
os.makedirs(APP_DIR, exist_ok=True)

MEMORY_FILE = os.path.join(APP_DIR, "memory.json")
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
HISTORY_DIR = os.path.join(APP_DIR, "history")
KNOWLEDGE_DIR = os.path.join(APP_DIR, "knowledge")
NOTES_DIR = os.path.join(APP_DIR, "notes")
os.makedirs(HISTORY_DIR, exist_ok=True)
os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
os.makedirs(NOTES_DIR, exist_ok=True)

# 安全路径白名单
ALLOWED_PATHS = [
    os.path.expanduser("~"),
    APP_DIR,
    os.path.expanduser("~/xyz-aiagent"),
]


# ═══════════════════════════════════════════════════════════════
# 1. 配置管理
# ═══════════════════════════════════════════════════════════════

DEFAULT_CONFIG = {
    "user_name": "",
    "model": "gpt-4o-mini",
    "max_steps": 15,
    "max_tool_retries": 2,
    "enable_rag": True,
    "verbose": True,
    "temperature": 0.3,
}


class Config:
    """用户配置管理"""

    def __init__(self, path: str = CONFIG_FILE):
        self.path = path
        self.data = DEFAULT_CONFIG.copy()
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path) as f:
                saved = json.load(f)
                self.data.update(saved)

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value):
        self.data[key] = value
        self.save()

    def __str__(self):
        return json.dumps(self.data, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════
# 2. 记忆系统（长期记忆 + 对话历史）
# ═══════════════════════════════════════════════════════════════

class Memory:
    """增强记忆系统"""

    def __init__(self, filepath: str = MEMORY_FILE, config: Config = None):
        self.filepath = filepath
        self.config = config or Config()
        self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            with open(self.filepath) as f:
                self.data = json.load(f)
        else:
            self.data = {
                "facts": [],
                "conversations": [],
                "user_profile": {},
            }
            self._save()

    def _save(self):
        with open(self.filepath, "w") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def add_fact(self, content: str, tags: list = None):
        """添加持久化事实"""
        entry = {
            "id": hashlib.md5(content.encode()).hexdigest()[:8],
            "content": content,
            "tags": tags or [],
            "created": datetime.datetime.now().isoformat(),
        }
        # 去重
        for e in self.data["facts"]:
            if e["content"] == content:
                e["tags"] = list(set(e["tags"] + (tags or [])))
                self._save()
                return
        self.data["facts"].append(entry)
        self._save()

    def recall(self, query: str, limit: int = 5) -> list:
        """检索事实"""
        query_lower = query.lower()
        results = []
        for entry in self.data["facts"]:
            score = 0
            if query_lower in entry["content"].lower():
                score += 2
            for tag in entry.get("tags", []):
                if query_lower in tag.lower():
                    score += 1
            if score > 0:
                results.append((score, entry))
        results.sort(key=lambda x: -x[0])
        return [r[1] for r in results[:limit]]

    def save_conversation(self, session_id: str, messages: list):
        """保存对话历史"""
        filepath = os.path.join(HISTORY_DIR, f"{session_id}.json")
        with open(filepath, "w") as f:
            json.dump({
                "session_id": session_id,
                "timestamp": datetime.datetime.now().isoformat(),
                "messages": messages,
            }, f, ensure_ascii=False, indent=2)

    def add_to_profile(self, key: str, value: str):
        """保存用户偏好"""
        self.data["user_profile"][key] = value
        self._save()

    def get_context(self, query: str) -> str:
        """获取格式化的记忆上下文"""
        facts = self.recall(query)
        profile = self.data.get("user_profile", {})

        lines = []
        if profile:
            lines.append("📋 用户信息：")
            for k, v in profile.items():
                lines.append(f"  {k}: {v}")

        if facts:
            lines.append("\n📖 相关记忆：")
            for f in facts:
                lines.append(f"  • {f['content']}")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 3. RAG 知识库（基于本地文档）
# ═══════════════════════════════════════════════════════════════

class SimpleRAG:
    """基于文件关键词检索的简单 RAG"""

    def __init__(self, knowledge_dir: str = KNOWLEDGE_DIR):
        self.knowledge_dir = knowledge_dir
        self._init_knowledge()

    def _init_knowledge(self):
        """初始化知识库（从已有笔记文件建立索引）"""
        self.documents = []
        for fpath in glob.glob(os.path.join(self.knowledge_dir, "*.md")):
            with open(fpath) as f:
                content = f.read()
            self.documents.append({
                "path": fpath,
                "title": os.path.basename(fpath).replace(".md", ""),
                "content": content,
            })

    def add_document(self, title: str, content: str):
        """添加知识文档"""
        safe_name = re.sub(r'[^\w\-]', '_', title)[:50]
        fpath = os.path.join(self.knowledge_dir, f"{safe_name}.md")
        with open(fpath, "w") as f:
            f.write(f"# {title}\n\n{content}\n")
        self.documents.append({
            "path": fpath,
            "title": title,
            "content": content,
        })

    def query(self, query: str, top_k: int = 3) -> str:
        """检索相关知识"""
        query_lower = query.lower()
        scored = []

        for doc in self.documents:
            score = 0
            content_lower = doc["content"].lower()

            # 关键词匹配
            words = query_lower.split()
            for word in words:
                if len(word) < 2:
                    continue
                count = content_lower.count(word)
                score += count

            if score > 0:
                scored.append((score, doc))

        scored.sort(key=lambda x: -x[0])

        if not scored:
            return ""

        results = []
        for score, doc in scored[:top_k]:
            # 提取相关片段
            content = doc["content"]
            idx = content.lower().find(query_lower)
            if idx > 0:
                start = max(0, idx - 100)
                end = min(len(content), idx + len(query_lower) + 200)
                snippet = content[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(content):
                    snippet = snippet + "..."
            else:
                snippet = content[:300]

            results.append(f"【{doc['title']}】\n{snippet}\n")

        return "\n---\n".join(results)


# ═══════════════════════════════════════════════════════════════
# 4. 工具定义
# ═══════════════════════════════════════════════════════════════

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "执行数学计算",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式，如 '2 + 3 * 4'"},
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
            "description": "创建/保存笔记",
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
            "description": "列出所有笔记",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_note",
            "description": "删除指定笔记（用户确认后才执行）",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "笔记标题"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文件内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "在知识库中搜索信息（知识库包含学习笔记和参考资料）",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                },
                "required": ["query"],
            },
        },
    },
]


def is_safe_path(path: str) -> bool:
    """安全路径检查"""
    abs_path = os.path.abspath(os.path.expanduser(path))
    return any(abs_path.startswith(allowed) for allowed in ALLOWED_PATHS)


def execute_tool(name: str, args: dict) -> str:
    """执行工具"""
    try:
        if name == "calculate":
            expr = args["expression"]
            allowed = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
                      "pi": math.pi, "e": math.e, "abs": abs, "round": round}
            result = eval(expr, {"__builtins__": {}}, allowed)
            return json.dumps({"success": True, "result": result})

        elif name == "get_time":
            now = datetime.datetime.now()
            return json.dumps({"success": True, "date": now.strftime("%Y-%m-%d"),
                               "time": now.strftime("%H:%M:%S"), "weekday": now.strftime("%A")})

        elif name == "create_note":
            safe_name = re.sub(r'[^\w\-]', '_', args["title"])[:50]
            fpath = os.path.join(NOTES_DIR, f"{safe_name}.md")
            with open(fpath, "w") as f:
                f.write(f"# {args['title']}\n\n{args['content']}\n")
            return json.dumps({"success": True, "path": fpath})

        elif name == "search_notes":
            keyword = args["keyword"].lower()
            results = []
            for fname in os.listdir(NOTES_DIR):
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(NOTES_DIR, fname)
                with open(fpath) as f:
                    content = f.read()
                if keyword in content.lower():
                    results.append({"file": fname, "title": fname.replace(".md", "").replace("_", " ")})
            return json.dumps({"success": True, "results": results})

        elif name == "list_notes":
            notes = []
            for fname in sorted(os.listdir(NOTES_DIR)):
                if fname.endswith(".md"):
                    fpath = os.path.join(NOTES_DIR, fname)
                    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M")
                    notes.append({"title": fname.replace(".md", "").replace("_", " "), "updated": mtime})
            return json.dumps({"success": True, "notes": notes})

        elif name == "delete_note":
            title = args["title"]
            for fname in os.listdir(NOTES_DIR):
                if fname.endswith(".md") and fname.startswith(re.sub(r'[^\w\-]', '_', title)[:50]):
                    os.remove(os.path.join(NOTES_DIR, fname))
                    return json.dumps({"success": True, "deleted": title})
            return json.dumps({"success": False, "error": f"未找到笔记: {title}"})

        elif name == "read_file":
            path = args["path"]
            if not is_safe_path(path):
                return json.dumps({"success": False, "error": "路径不在白名单中"})
            if not os.path.exists(path):
                return json.dumps({"success": False, "error": "文件不存在"})
            with open(path) as f:
                content = f.read()
            truncated = len(content) > 2000
            return json.dumps({"success": True, "content": content[:2000], "truncated": truncated})

        elif name == "search_knowledge":
            return json.dumps({"success": True, "results": "请在 Agent 中通过系统提示使用 rag.query() 方法调用知识库"})

    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)

    return json.dumps({"success": False, "error": f"未知工具: {name}"})


# ═══════════════════════════════════════════════════════════════
# 5. Agent 主类
# ═══════════════════════════════════════════════════════════════

class PersonalAssistant:
    """完整个人助手 Agent"""

    def __init__(self, verbose: bool = True):
        self.config = Config()
        self.memory = Memory()
        self.rag = SimpleRAG()
        self.verbose = verbose
        self.session_messages = []

    def _build_system_prompt(self, user_query: str) -> str:
        """构建动态 System Prompt"""
        # 记忆上下文
        memory_ctx = self.memory.get_context(user_query)

        # RAG 知识检索
        rag_ctx = ""
        if self.config.get("enable_rag", True):
            rag_results = self.rag.query(user_query)
            if rag_results:
                rag_ctx = f"\n\n## 知识库相关结果\n{rag_results}"

        return f"""你是 AI 个人助手，一个功能完整的个人助理 Agent。

【身份】
- 你能帮你管理笔记、查询知识、执行计算、读取文件
- 你具备跨会话记忆能力，能记住用户信息和偏好

【工具集】
- calculate: 数学计算
- get_time: 日期时间
- create_note: 保存笔记
- search_notes: 搜索笔记
- list_notes: 列出笔记
- delete_note: 删除笔记（需要用户明确确认）
- read_file: 读取文件（在白名单路径内）
- search_knowledge: 搜索知识库

【工作原则】
1. 先理解，再行动 — 确保理解用户意图才调用工具
2. 最简路径 — 能用一步完成的不用两步
3. 错误友好 — 工具出错时告知用户并提供替代
4. 确认敏感操作 — 删除等操作前需要用户确认
5. 结构化输出 — 用表格、列表呈现信息

【记忆信息】
{memory_ctx or "暂无相关记忆"}{rag_ctx}

【用户配置】
模型: {self.config.get("model")}
最大步数: {self.config.get("max_steps")}"""

    def _check_loop(self, assistant_messages: list) -> bool:
        """检测死循环"""
        calls = []
        for m in assistant_messages:
            if isinstance(m, dict) and m.get("role") == "assistant":
                tc = m.get("tool_calls")
                if tc:
                    calls.append(tc[0].function.name if tc else None)
        if len(calls) >= 3:
            if len(set(calls[-3:])) == 1:
                return True
        return False

    def process(self, user_input: str) -> str:
        """处理用户输入并返回回答"""
        system_prompt = self._build_system_prompt(user_input)

        messages = [
            {"role": "system", "content": system_prompt},
        ]

        # 带上历史消息（短期记忆，最近 10 条）
        history = [m for m in self.session_messages[-20:]]
        messages.extend(history)
        messages.append({"role": "user", "content": user_input})

        max_steps = self.config.get("max_steps", 15)
        assistant_tool_calls = []

        for step in range(max_steps):
            if self.verbose and step > 0:
                print(f"\r  [Step {step + 1}] 推理中...", end="")

            response = client.chat.completions.create(
                model=self.config.get("model"),
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=self.config.get("temperature", 0.3),
            )

            msg = response.choices[0].message
            messages.append(msg)
            assistant_tool_calls.append(msg)

            # 死循环检测
            if self._check_loop(assistant_tool_calls):
                if self.verbose:
                    print(f"\n  ⚠ 检测到死循环")
                messages.append({
                    "role": "user",
                    "content": "你好像陷入了循环。请直接回答用户的问题，不要再调用工具了。",
                })
                continue

            if msg.tool_calls:
                for tc in msg.tool_calls:
                    func_name = tc.function.name
                    func_args = json.loads(tc.function.arguments)

                    # 敏感操作确认
                    if func_name == "delete_note":
                        messages.append({
                            "role": "user",
                            "content": f"⚠️ 确认要删除笔记 '{func_args.get('title')}' 吗？如果确认，请重新调用 delete_note.",
                        })
                        continue

                    result = execute_tool(func_name, func_args)

                    if self.verbose:
                        result_preview = result[:60].replace('\n', ' ')
                        print(f"\n  → {func_name}() → {result_preview}")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
            else:
                # 完成
                if self.verbose and step > 0:
                    print()
                answer = msg.content
                self.session_messages.append({"role": "user", "content": user_input})
                self.session_messages.append({"role": "assistant", "content": answer})
                return answer

        return "⚠️ 步骤超限，请简化问题。"

    def chat(self):
        """交互式聊天循环"""
        print(f"\n{'=' * 55}")
        print(f"  🤖 AI 个人助手 Agent (CLI)")
        print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"  提示: 输入 /help 看帮助, /exit 退出")
        print(f"{'=' * 55}")

        while True:
            try:
                user_input = input(f"\n  🧑> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not user_input:
                continue

            if user_input == "/exit":
                # 保存对话历史
                session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                self.memory.save_conversation(session_id, self.session_messages[-50:])
                print("  👋 再见！")
                break

            elif user_input == "/help":
                print("""
  📋 可用命令:
    /exit     — 退出
    /help     — 显示帮助
    /memory   — 查看记忆
    /config   — 查看配置
    /clear    — 清空当前对话
                """)
                continue

            elif user_input == "/memory":
                print(f"\n  📖 记忆内容:\n{json.dumps(self.memory.data, ensure_ascii=False, indent=2)[:500]}")
                continue

            elif user_input == "/config":
                print(f"\n  ⚙️ 配置:\n{self.config}")
                continue

            elif user_input == "/clear":
                self.session_messages = []
                print("  ✅ 对话已清除")
                continue

            # 处理用户输入
            print(f"\r  ⏳ 处理中...", end="")
            answer = self.process(user_input)
            print(f"\n  🤖 {answer}")

            # 从对话中提取用户信息（简单的模式匹配）
            name_match = re.search(r"(?:我叫|我是|称呼我)(\S+)", user_input)
            if name_match:
                self.memory.add_to_profile("name", name_match.group(1))
            if "记住" in user_input or "我喜欢" in user_input:
                self.memory.add_fact(user_input, ["user_preference"])


# ═══════════════════════════════════════════════════════════════
# 6. 主程序
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    assistant = PersonalAssistant(verbose=True)

    # 检查是否在交互模式
    if len(sys.argv) > 1:
        # 单次问答模式
        answer = assistant.process(" ".join(sys.argv[1:]))
        print(answer)
    else:
        # 交互模式
        assistant.chat()
