"""
MCP (Model Context Protocol) 风格工具系统
展示标准化的工具注册、发现和调用机制
"""

import json
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── MCP 风格的 Tool Schema ──────────────────────────────
# MCP 定义了标准化的工具接口：name, description, input_schema
# 这里用兼容 OpenAI 格式的方式实现

class MCPServer:
    """
    模拟 MCP 工具服务器
    
    MCP 核心概念：
    - Tool: 一个可调用的函数，有名称、描述、参数 schema
    - Server: 提供一组 Tool 的服务端
    - Client: 通过 MCP 协议发现和调用 Tool
    """
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._tools = {}
    
    def register(self, func, name: str = None, description: str = "",
                 parameters: dict = None):
        """
        注册一个工具
        
        参数：
            func: 工具函数
            name: 工具名（默认用函数名）
            description: 工具描述
            parameters: JSON Schema 格式的参数定义
        """
        tool_name = name or func.__name__
        
        # 自动推断参数 schema（如果没提供）
        if parameters is None:
            import inspect
            sig = inspect.signature(func)
            properties = {}
            required = []
            for p_name, p_param in sig.parameters.items():
                p_type = "string"
                if p_param.annotation is int or p_param.annotation is float:
                    p_type = "number"
                properties[p_name] = {
                    "type": p_type,
                    "description": f"参数 {p_name}"
                }
                if p_param.default is inspect.Parameter.empty:
                    required.append(p_name)
            parameters = {
                "type": "object",
                "properties": properties,
                "required": required
            }
        
        self._tools[tool_name] = {
            "func": func,
            "schema": {
                "name": tool_name,
                "description": description or func.__doc__ or "",
                "input_schema": parameters
            }
        }
        
        return self
    
    def get_openai_tools(self):
        """转换为 OpenAI tools 格式"""
        tools = []
        for name, tool in self._tools.items():
            schema = tool["schema"]
            tools.append({
                "type": "function",
                "function": {
                    "name": schema["name"],
                    "description": schema["description"],
                    "parameters": schema["input_schema"]
                }
            })
        return tools
    
    def execute(self, tool_name: str, arguments: dict):
        """执行一个工具"""
        tool = self._tools.get(tool_name)
        if not tool:
            return {"status": "error", "error": f"未知工具: {tool_name}"}
        
        try:
            result = tool["func"](**arguments)
            return {"status": "success", "data": result}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def list_tools(self):
        """列出所有已注册的工具（MCP 的 tools/list 方法）"""
        return {name: tool["schema"] for name, tool in self._tools.items()}


# ── 工具注册 ──────────────────────────────────────────

def search_web(query: str) -> str:
    """搜索网络获取实时信息"""
    results = {
        "Python asyncio": "asyncio 是 Python 的异步I/O库，用于编写并发代码",
        "MCP协议": "MCP (Model Context Protocol) 是 Anthropic 推出的开放标准协议",
        "OpenAI": "OpenAI 是人工智能研究公司，开发了 GPT 系列模型",
    }
    return results.get(query, f"关于「{query}」的搜索结果")


def read_file_content(path: str, line_count: int = 10) -> str:
    """读取文件内容"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return "".join(lines[:line_count])
    except Exception as e:
        return f"读取失败: {e}"


def get_timezone(city: str) -> dict:
    """获取城市时区信息"""
    timezones = {
        "北京": {"timezone": "Asia/Shanghai", "utc_offset": "+08:00"},
        "东京": {"timezone": "Asia/Tokyo", "utc_offset": "+09:00"},
        "伦敦": {"timezone": "Europe/London", "utc_offset": "+00:00"},
        "纽约": {"timezone": "America/New_York", "utc_offset": "-05:00"},
    }
    data = timezones.get(city, {"timezone": "Unknown", "utc_offset": "Unknown"})
    return data


# ── 创建 MCP 服务器并注册工具 ──────────────────────────

weather_server = MCPServer("天气服务", "提供天气相关工具")
weather_server.register(search_web, "search_web", 
    "搜索网络获取信息", {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"}
        },
        "required": ["query"]
    })

weather_server.register(get_timezone, "get_timezone",
    "获取城市的时区信息", {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "城市名称"}
        },
        "required": ["city"]
    })

file_server = MCPServer("文件服务", "提供文件操作工具")
file_server.register(read_file_content, "read_file",
    "读取文本文件的前 N 行内容", {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "line_count": {"type": "integer", "description": "读取行数（默认10行）"}
        },
        "required": ["path"]
    })


# ── 使用 MCP 风格工具 ──────────────────────────

def demo_mcp_concept():
    """演示 MCP 风格的工具管理"""
    print("=" * 60)
    print("MCP (Model Context Protocol) 风格工具系统")
    print("=" * 60)

    # 列出所有工具
    print(f"\n📋 天气服务 - 已注册工具:")
    for name, schema in weather_server.list_tools().items():
        print(f"  ── {name}: {schema['description']}")
        params = schema["input_schema"]
        if "properties" in params:
            print(f"      参数: {', '.join(params['properties'].keys())}")

    print(f"\n📋 文件服务 - 已注册工具:")
    for name, schema in file_server.list_tools().items():
        print(f"  ── {name}: {schema['description']}")
        params = schema["input_schema"]
        if "properties" in params:
            print(f"      参数: {', '.join(params['properties'].keys())}")

    # 合并所有工具
    all_tools = weather_server.get_openai_tools() + file_server.get_openai_tools()
    print(f"\n✅ 合并 {len(all_tools)} 个工具，可用于 OpenAI API")

    # 实际调用演示
    print(f"\n{'─'*40}")
    print("演示：查询北京时区")
    print(f"{'─'*40}")

    result = weather_server.execute("get_timezone", {"city": "北京"})
    print(f"  结果: {json.dumps(result, ensure_ascii=False)}")

    print(f"\n{'─'*40}")
    print("演示：搜索 MCP 协议")
    print(f"{'─'*40}")

    result2 = weather_server.execute("search_web", {"query": "MCP协议"})
    print(f"  结果: {json.dumps(result2, ensure_ascii=False)}")

    # 完整的 LLM 对话
    print(f"\n{'─'*40}")
    print("LLM 对话演示：使用 MCP 风格工具")
    print(f"{'─'*40}")

    query = "请问东京和纽约的时区分别是多少？"
    print(f"📝 用户: {query}")

    messages = [{"role": "user", "content": query}]
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=all_tools,
        tool_choice="auto"
    )

    msg = response.choices[0].message
    if msg.tool_calls:
        messages.append(msg)
        for tc in msg.tool_calls:
            result = weather_server.execute(
                tc.function.name,
                json.loads(tc.function.arguments)
            )
            print(f"  🛠️  {tc.function.name} → {result['data']}")
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False)
            })

        final = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=all_tools
        )
        print(f"\n💬 LLM: {final.choices[0].message.content}")


def demo_multi_server():
    """演示多个 MCP 服务器协同工作"""
    print(f"\n{'='*60}")
    print("多 MCP 服务器协作")
    print("=" * 60)

    # 不同工具服务器提供不同领域的功能
    query = "搜索一下 MCP 协议的相关信息，并告诉我北京时区"
    print(f"📝 用户: {query}")

    all_tools = weather_server.get_openai_tools()
    messages = [{"role": "user", "content": query}]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        tools=all_tools,
        tool_choice="auto"
    )

    msg = response.choices[0].message
    if msg.tool_calls:
        print(f"  需要调用 {len(msg.tool_calls)} 个工具:")
        messages.append(msg)
        for tc in msg.tool_calls:
            print(f"    ── MCP Server / {tc.function.name}")
            result = weather_server.execute(
                tc.function.name,
                json.loads(tc.function.arguments)
            )
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False)
            })
            print(f"      → {result['data']}")

        final = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=all_tools
        )
        print(f"\n💬 {final.choices[0].message.content}")


if __name__ == "__main__":
    demo_mcp_concept()
    demo_multi_server()
