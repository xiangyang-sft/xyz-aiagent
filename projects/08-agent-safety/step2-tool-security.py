"""
step2-tool-security.py — 工具安全三层模型 + 权限控制

功能：
1. 三层权限模型（静态配置 → 运行时检查 → 人工确认）
2. 工具安全注册器
3. 参数校验与速率限制
4. 审计追踪

运行：python step2-tool-security.py
"""

import time
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


# ============================================================
# 基础类型定义
# ============================================================

class ToolDangerLevel(Enum):
    """工具危险等级"""
    SAFE = 0       # 读操作，无副作用，自动执行
    CAUTION = 1    # 写操作，有副作用，需校验
    DANGEROUS = 2  # 危险操作，需人工确认


@dataclass
class ToolSpec:
    """工具规格定义"""
    name: str
    description: str
    danger_level: ToolDangerLevel
    parameters: dict  # JSON Schema
    rate_limit_calls: int = 0      # 每 session 最多调用次数
    rate_limit_window: int = 0     # 时间窗口（秒）
    allowed_operations: list = field(default_factory=list)  # 操作白名单
    allowed_targets: list = field(default_factory=list)     # 目标白名单
    requires_confirmation: bool = False  # 需要人工确认


# ============================================================
# Layer 1: 静态权限配置
# ============================================================

class PermissionRegistry:
    """
    第 1 层防御：静态权限配置
    定义哪些工具可用、每个工具的操作范围
    """

    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec):
        """注册工具"""
        self._tools[spec.name] = spec
        print(f"  📋 注册工具：{spec.name} "
              f"[{'🟢 安全' if spec.danger_level == ToolDangerLevel.SAFE else '🟡 谨慎' if spec.danger_level == ToolDangerLevel.CAUTION else '🔴 危险'}]")

    def get_spec(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def list_tools(self) -> dict:
        return {n: s for n, s in self._tools.items()}

    def get_available_names(self, danger_limit: ToolDangerLevel) -> list[str]:
        """获取不高于指定危险等级的工具列表"""
        return [
            name for name, spec in self._tools.items()
            if spec.danger_level.value <= danger_limit.value
        ]


# ============================================================
# Layer 2: 运行时执行控制
# ============================================================

class ExecutionController:
    """
    第 2 层防御：运行时检查
    参数校验、速率限制、操作白名单
    """

    def __init__(self, registry: PermissionRegistry):
        self.registry = registry
        self._call_count: dict[str, list[float]] = {}
        self._audit_log: list[dict] = []

    def check_and_execute(self, tool_name: str, params: dict, user_context: str) -> dict:
        """检查权限并执行（如果通过检查）"""
        spec = self.registry.get_spec(tool_name)
        if not spec:
            return {"success": False, "error": f"未知工具：{tool_name}"}

        # Step 1: 参数校验
        param_check = self._validate_params(spec, params)
        if not param_check["valid"]:
            self._log_audit("参数校验失败", tool_name, params, user_context,
                            reason=param_check["error"])
            return {"success": False, "error": param_check["error"]}

        # Step 2: 速率限制
        rate_check = self._check_rate_limit(spec)
        if not rate_check["allowed"]:
            self._log_audit("速率限制", tool_name, params, user_context,
                            reason=rate_check["reason"])
            return {"success": False, "error": rate_check["reason"]}

        # Step 3: 操作和目标白名单检查
        access_check = self._check_access(spec, params)
        if not access_check["allowed"]:
            self._log_audit("权限不足", tool_name, params, user_context,
                            reason=access_check["reason"])
            return {"success": False, "error": access_check["reason"]}

        # 通过检查，标记执行
        self._record_call(tool_name)
        self._log_audit("允许执行", tool_name, params, user_context)

        return {
            "success": True,
            "danger_level": spec.danger_level,
            "needs_confirmation": spec.requires_confirmation,
            "message": f"✅ 通过安全检查，可以执行 {tool_name}",
        }

    def _validate_params(self, spec: ToolSpec, params: dict) -> dict:
        """参数校验"""
        for param_name, param_schema in spec.parameters.get("properties", {}).items():
            if param_name in params:
                value = params[param_name]

                # 类型检查
                expected_type = param_schema.get("type", "string")
                if expected_type == "integer" and not isinstance(value, int):
                    return {"valid": False, "error": f"参数 {param_name} 应为整数"}
                if expected_type == "number" and not isinstance(value, (int, float)):
                    return {"valid": False, "error": f"参数 {param_name} 应为数字"}
                if expected_type == "string" and not isinstance(value, str):
                    return {"valid": False, "error": f"参数 {param_name} 应为字符串"}

                # 长度/范围检查
                if spec.name == "read_file" and param_name == "filepath":
                    if len(value) > 500:
                        return {"valid": False, "error": "文件路径过长"}
                    if ".." in value:
                        return {"valid": False, "error": "路径不能包含 '..'"}

                if spec.name == "send_email" and param_name == "body":
                    if len(value) > 10000:
                        return {"valid": False, "error": "邮件正文过长"}

        # 检查必需参数
        required = spec.parameters.get("required", [])
        for req in required:
            if req not in params:
                return {"valid": False, "error": f"缺少必需参数：{req}"}

        return {"valid": True}

    def _check_rate_limit(self, spec: ToolSpec) -> dict:
        """速率限制检查"""
        if spec.rate_limit_calls <= 0:
            return {"allowed": True}

        now = time.time()
        if spec.name not in self._call_count:
            return {"allowed": True}

        calls = self._call_count[spec.name]
        window_start = now - spec.rate_limit_window

        # 清除窗口外的记录
        recent_calls = [t for t in calls if t > window_start]

        if len(recent_calls) >= spec.rate_limit_calls:
            return {
                "allowed": False,
                "reason": f"达到速率限制：{spec.name} 每 {spec.rate_limit_window}秒最多 {spec.rate_limit_calls} 次",
            }

        return {"allowed": True}

    def _check_access(self, spec: ToolSpec, params: dict) -> dict:
        """操作和白名单检查"""
        # 操作白名单检查
        if spec.allowed_operations:
            op = params.get("operation", params.get("action", ""))
            if op and op not in spec.allowed_operations:
                return {
                    "allowed": False,
                    "reason": f"操作 '{op}' 不在白名单中，允许：{spec.allowed_operations}",
                }

        # 目标白名单检查
        if spec.allowed_targets:
            target = params.get("target", params.get("filepath", params.get("to", "")))
            if not any(target.startswith(t) for t in spec.allowed_targets):
                return {
                    "allowed": False,
                    "reason": f"目标 '{target}' 不在白名单中，允许路径以：{spec.allowed_targets} 开头",
                }

        return {"allowed": True}

    def _record_call(self, tool_name: str):
        """记录调用"""
        if tool_name not in self._call_count:
            self._call_count[tool_name] = []
        self._call_count[tool_name].append(time.time())

    def _log_audit(self, action: str, tool_name: str, params: dict,
                   user_context: str, reason: str = ""):
        """记录审计日志"""
        self._audit_log.append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "tool": tool_name,
            "params": params,
            "user_context": user_context[:50],
            "reason": reason,
        })

    def get_audit_log(self) -> list[dict]:
        return self._audit_log


# ============================================================
# Layer 3: 人工确认
# ============================================================

class HumanConfirmationGate:
    """
    第 3 层防御：人工确认
    危险操作必须经过用户确认才能执行
    """

    def __init__(self, controller: ExecutionController):
        self.controller = controller

    def execute_with_confirmation(self, tool_name: str, params: dict,
                                  user_context: str, auto_confirm: bool = False) -> dict:
        """带人工确认的执行流程"""
        check = self.controller.check_and_execute(tool_name, params, user_context)

        if not check["success"]:
            return check

        spec = self.controller.registry.get_spec(tool_name)

        # 如果需要人工确认
        if spec.requires_confirmation or check.get("needs_confirmation"):
            print(f"\n  🛑 需要人工确认：{tool_name}")
            print(f"     参数：{json.dumps(params, ensure_ascii=False)}")
            print(f"     用户请求：{user_context[:60]}...")

            if auto_confirm:
                print(f"  ✅ 已自动确认（演示模式）")
                return {"success": True, "result": f"执行 {tool_name} 成功", "confirmed": True}
            else:
                return {
                    "success": False,
                    "needs_confirmation": True,
                    "message": f"等待用户确认：{tool_name}({params})",
                }

        return {"success": True, "result": f"自动执行 {tool_name} 成功"}


# ============================================================
# 定义工具
# ============================================================

def setup_tools(registry: PermissionRegistry):
    """注册一组示例工具"""

    # 安全工具：读操作，无副作用
    registry.register(ToolSpec(
        name="query_sales",
        description="查询销售数据",
        danger_level=ToolDangerLevel.SAFE,
        parameters={
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "日期，格式 YYYY-MM-DD"},
                "product": {"type": "string", "description": "产品名称（可选）"},
            },
            "required": ["date"],
        },
        rate_limit_calls=100,
        rate_limit_window=60,
    ))

    # 谨慎工具：写操作，有校验
    registry.register(ToolSpec(
        name="read_file",
        description="读取文件内容",
        danger_level=ToolDangerLevel.CAUTION,
        parameters={
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "文件路径"},
            },
            "required": ["filepath"],
        },
        rate_limit_calls=30,
        rate_limit_window=60,
        allowed_targets=["/home/user/data/", "/tmp/agent/"],
    ))

    # 危险工具：修改数据，需人工确认
    registry.register(ToolSpec(
        name="update_database",
        description="更新数据库记录",
        danger_level=ToolDangerLevel.DANGEROUS,
        parameters={
            "type": "object",
            "properties": {
                "table": {"type": "string", "description": "表名"},
                "operation": {"type": "string", "description": "操作类型"},
                "data": {"type": "object", "description": "更新数据"},
                "condition": {"type": "string", "description": "更新条件"},
            },
            "required": ["table", "operation", "data"],
        },
        rate_limit_calls=5,
        rate_limit_window=60,
        allowed_operations=["update", "insert"],
        requires_confirmation=True,
    ))

    # 危险工具：发送邮件
    registry.register(ToolSpec(
        name="send_email",
        description="发送电子邮件",
        danger_level=ToolDangerLevel.DANGEROUS,
        parameters={
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "收件人邮箱"},
                "subject": {"type": "string", "description": "邮件主题"},
                "body": {"type": "string", "description": "邮件正文"},
            },
            "required": ["to", "subject"],
        },
        rate_limit_calls=3,
        rate_limit_window=300,
        requires_confirmation=True,
    ))


# ============================================================
# 演示
# ============================================================

def demo():
    print("=" * 60)
    print("🛡️ 工具安全三层模型演示")
    print("=" * 60)

    # 初始化
    registry = PermissionRegistry()
    setup_tools(registry)

    controller = ExecutionController(registry)
    gate = HumanConfirmationGate(controller)

    print("\n" + "-" * 60)
    print("📌 场景 1：安全工具 — 自动执行")
    print("-" * 60)
    result = gate.execute_with_confirmation(
        "query_sales", {"date": "2026-06-05", "product": "AI Agent 课程"},
        "帮我查一下昨天的销售数据", auto_confirm=True,
    )
    print(f"  结果：{result['success']} | {result.get('result', '')}")

    print("\n" + "-" * 60)
    print("📌 场景 2：参数校验失败 — 路径穿越攻击")
    print("-" * 60)
    result = gate.execute_with_confirmation(
        "read_file", {"filepath": "../../../etc/passwd"},
        "读取系统配置文件", auto_confirm=True,
    )
    print(f"  结果：{result['success']} | {result.get('error', '')}")

    print("\n" + "-" * 60)
    print("📌 场景 3：目标白名单阻止")
    print("-" * 60)
    result = gate.execute_with_confirmation(
        "read_file", {"filepath": "/etc/shadow"},
        "读取系统影子文件", auto_confirm=True,
    )
    print(f"  结果：{result['success']} | {result.get('error', '')}")

    print("\n" + "-" * 60)
    print("📌 场景 4：操作白名单阻止")
    print("-" * 60)
    result = gate.execute_with_confirmation(
        "update_database", {"table": "users", "operation": "delete", "data": {"id": 1}},
        "删除用户 ID 为 1 的记录", auto_confirm=True,
    )
    print(f"  结果：{result['success']} | {result.get('error', '')}")

    print("\n" + "-" * 60)
    print("📌 场景 5：危险工具需人工确认")
    print("-" * 60)
    result = gate.execute_with_confirmation(
        "send_email", {"to": "user@company.com", "subject": "测试", "body": "Hello"},
        "发送一封测试邮件",
    )
    print(f"  结果：{result['success']} | {result.get('message', '')}")

    print("\n" + "-" * 60)
    print("📌 场景 6：速率限制")
    print("-" * 60)
    for i in range(4):
        result = gate.execute_with_confirmation(
            "send_email", {"to": f"user{i}@test.com", "subject": f"Email #{i}", "body": "test"},
            f"发送第 {i+1} 封邮件", auto_confirm=True,
        )
        print(f"  第 {i+1} 次：{'✅' if result['success'] else '❌'} {result.get('result', result.get('error', ''))}")

    # 打印审计日志
    print("\n" + "-" * 60)
    print("📋 审计日志")
    print("-" * 60)
    for entry in controller.get_audit_log():
        print(f"  [{entry['timestamp']}] {entry['action']} — {entry['tool']}")
        if entry.get("reason"):
            print(f"      原因：{entry['reason']}")


if __name__ == "__main__":
    demo()

    print("\n" + "=" * 60)
    print("📝 关键总结")
    print("=" * 60)
    print("""
1️⃣ 第 1 层（静态权限）：定义工具、危险等级、白名单
2️⃣ 第 2 层（运行时检查）：参数校验 + 速率限制 + 访问控制
3️⃣ 第 3 层（人工确认）：危险操作需用户二次确认

🔑 核心原则：
   - 最小权限：只给 Agent 完成任务所需的最少工具
   - 纵深防御：多层防御，单层失效还有兜底
   - 审计追踪：所有决策（允许/拒绝）都有日志
""")
