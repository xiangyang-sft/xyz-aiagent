#!/usr/bin/env python3
"""
xyz_agent.loader — 插件加载器

支持从多种来源动态加载扩展：
  - 本地目录（扫描 skill/mcp/command 配置）
  - YAML 配置文件
  - 外部 URL（HTTP 下载）
  - Python 包

用法:
    loader = ExtensionLoader()

    # 从目录自动发现
    loader.load_directory("~/.xyz-agent/extensions/")

    # 从 YAML 配置加载
    loader.load_config("extensions.yaml")

    # 将发现的扩展应用到各个管理器
    loader.apply_to(skill_manager, mcp_manager, command_system)
"""

import os
import json
import yaml
import logging
import glob
import importlib.util
import sys
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path

from .skill import SkillManager
from .mcp_client import MCPManager
from .command import CommandSystem

logger = logging.getLogger(__name__)


# ============================================================
# 扩展配置
# ============================================================

@dataclass
class ExtensionConfig:
    """单个扩展的配置"""
    name: str
    enabled: bool = True
    type: str = "skill"  # skill | mcp | command | python
    source: str = ""     # 本地路径 | URL | pip 包名
    config: Dict = field(default_factory=dict)


# ============================================================
# 示例扩展配置
# ============================================================

SAMPLE_CONFIG = """# xyz-agent 扩展配置
# 将本文件放到 ~/.xyz-agent/extensions.yaml 即可生效

# ---- Skill 扩展 ----
skills:
  - name: research
    source: ~/.hermes/skills/research/
    description: "研究技能"
    enabled: true

  - name: coding
    source: https://example.com/skills/coding/
    description: "编程技能"
    enabled: false

# ---- MCP 服务器 ----
mcp_servers:
  - name: filesystem
    command: npx
    args:
      - -y
      - "@modelcontextprotocol/server-filesystem"
      - /tmp
    enabled: false  # 需要 Node.js + npx

  - name: github
    command: npx
    args:
      - -y
      - "@modelcontextprotocol/server-github"
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"
    enabled: false

# ---- 外部命令 ----
commands:
  - name: hello
    description: "自定义打招呼命令"
    source: inline
    code: |
      def handler(args, ctx):
          return f"你好，{args or '世界'}！"
    enabled: true

# ---- Python 插件 ----
plugins:
  - name: my_plugin
    source: ~/.xyz-agent/plugins/my_plugin.py
    enabled: false
"""


# ============================================================
# 扩展加载器
# ============================================================

class ExtensionLoader:
    """
    扩展加载器

    用法:
        loader = ExtensionLoader()
        loader.load_default_locations()
        loader.apply_to(skill_mgr, mcp_mgr, cmd_system)
    """

    def __init__(self):
        self._skills_config: List[Dict] = []
        self._mcp_configs: List[Dict] = []
        self._command_configs: List[Dict] = []
        self._plugin_configs: List[Dict] = []
        self._loaded_paths: set = set()

    # ---- 加载配置 ----

    def load_directory(self, directory: str, recursive: bool = True) -> int:
        """
        从目录自动发现扩展配置

        发现的配置:
          - **/*.skill.yaml / **/*.skill.json — Skill 定义
          - **/*.mcp.yaml / **/*.mcp.json — MCP 服务器定义
          - **/*.command.yaml / **/*.command.json — 命令定义
          - **/*.plugin.py — Python 插件
          - extensions.yaml / extensions.json — 合并配置

        返回: 发现的扩展数量
        """
        directory = os.path.expanduser(directory)
        if not os.path.isdir(directory):
            return 0
        if directory in self._loaded_paths:
            return 0
        self._loaded_paths.add(directory)

        count = 0

        # 扩展配置文件
        for pattern in ("extensions.yaml", "extensions.yml", "extensions.json"):
            path = os.path.join(directory, pattern)
            if os.path.isfile(path):
                count += self.load_config(path)

        # Skill 配置
        for ext in ("yaml", "yml", "json"):
            for filepath in glob.glob(os.path.join(directory, "**", f"*.skill.{ext}"), recursive=recursive):
                count += self._load_skill_config(filepath)

        # MCP 配置
        for ext in ("yaml", "yml", "json"):
            for filepath in glob.glob(os.path.join(directory, "**", f"*.mcp.{ext}"), recursive=recursive):
                count += self._load_mcp_config(filepath)

        # Command 配置
        for ext in ("yaml", "yml", "json"):
            for filepath in glob.glob(os.path.join(directory, "**", f"*.command.{ext}"), recursive=recursive):
                count += self._load_command_config(filepath)

        # Python 插件
        for filepath in glob.glob(os.path.join(directory, "**", "*.plugin.py"), recursive=recursive):
            count += 1
            self._plugin_configs.append({
                "name": os.path.splitext(os.path.basename(filepath))[0],
                "source": filepath,
                "enabled": True,
            })

        return count

    def load_config(self, path: str) -> int:
        """从 YAML/JSON 文件加载扩展配置"""
        path = os.path.expanduser(path)
        if path in self._loaded_paths:
            return 0
        self._loaded_paths.add(path)

        if not os.path.isfile(path):
            return 0

        try:
            with open(path) as f:
                if path.endswith(".json"):
                    config = json.load(f)
                else:
                    config = yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"加载扩展配置失败: {path}: {e}")
            return 0

        return self._process_config(config)

    def load_config_text(self, text: str, format: str = "yaml") -> int:
        """从字符串加载扩展配置"""
        try:
            if format == "json":
                config = json.loads(text)
            else:
                config = yaml.safe_load(text) or {}
        except Exception as e:
            logger.error(f"解析扩展配置失败: {e}")
            return 0

        return self._process_config(config)

    def load_default_locations(self) -> int:
        """加载默认位置的扩展"""
        count = 0
        for directory in [
            "~/.xyz-agent/extensions/",
            "~/.xyz-agent/",
            "./extensions/",
            "./",
        ]:
            expanded = os.path.expanduser(directory)
            if os.path.isdir(expanded):
                count += self.load_directory(expanded)
        return count

    # ---- 处理配置 ----

    def _process_config(self, config: Dict) -> int:
        """处理配置字典"""
        count = 0

        for key, entries in config.items():
            if not isinstance(entries, list):
                continue

            if key in ("skills", "skill"):
                for entry in entries:
                    if isinstance(entry, dict):
                        self._skills_config.append(entry)
                        count += 1

            elif key in ("mcp_servers", "mcp", "mcp_server"):
                for entry in entries:
                    if isinstance(entry, dict):
                        self._mcp_configs.append(entry)
                        count += 1

            elif key in ("commands", "command"):
                for entry in entries:
                    if isinstance(entry, dict):
                        self._command_configs.append(entry)
                        count += 1

            elif key in ("plugins", "plugin"):
                for entry in entries:
                    if isinstance(entry, dict):
                        self._plugin_configs.append(entry)
                        count += 1

        return count

    def _load_skill_config(self, path: str) -> bool:
        """加载单个 skill 配置"""
        try:
            with open(path) as f:
                config = json.load(f) if path.endswith(".json") else yaml.safe_load(f)
            if isinstance(config, dict) and "name" in config:
                config["_source"] = path
                self._skills_config.append(config)
                return True
        except Exception as e:
            logger.error(f"加载 skill 配置失败 {path}: {e}")
        return False

    def _load_mcp_config(self, path: str) -> bool:
        """加载单个 MCP 配置"""
        try:
            with open(path) as f:
                config = json.load(f) if path.endswith(".json") else yaml.safe_load(f)
            if isinstance(config, dict) and "command" in config:
                config["_source"] = path
                self._mcp_configs.append(config)
                return True
        except Exception as e:
            logger.error(f"加载 MCP 配置失败 {path}: {e}")
        return False

    def _load_command_config(self, path: str) -> bool:
        """加载单个命令配置"""
        try:
            with open(path) as f:
                config = json.load(f) if path.endswith(".json") else yaml.safe_load(f)
            if isinstance(config, dict) and "name" in config:
                config["_source"] = path
                self._command_configs.append(config)
                return True
        except Exception as e:
            logger.error(f"加载命令配置失败 {path}: {e}")
        return False

    # ---- 应用配置 ----

    def apply_to(self, skill_manager: Optional[SkillManager] = None,
                 mcp_manager: Optional[MCPManager] = None,
                 command_system: Optional[CommandSystem] = None,
                 tool_registry=None):
        """将加载的配置应用到各个管理器"""
        count = 0

        # 应用 Skill 配置
        if skill_manager:
            for cfg in self._skills_config:
                if not cfg.get("enabled", True):
                    continue
                source = cfg.get("source", "")
                if source and os.path.isdir(os.path.expanduser(source)):
                    n = skill_manager.load_directory(source)
                    count += n

        # 应用 MCP 配置
        if mcp_manager:
            for cfg in self._mcp_configs:
                if not cfg.get("enabled", True):
                    continue
                command = cfg.get("command", "")
                args = cfg.get("args", [])
                name = cfg.get("name", command)
                env = cfg.get("env", {})
                # 替换环境变量
                resolved_env = {}
                for k, v in env.items():
                    if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                        resolved_env[k] = os.environ.get(v[2:-1], "")
                    else:
                        resolved_env[k] = v
                try:
                    mcp_manager.connect_stdio(name, command, args, env=resolved_env, auto_connect=False)
                    count += 1
                except Exception as e:
                    logger.warning(f"连接 MCP 服务器 '{name}' 失败: {e}")

        # 应用命令配置
        if command_system:
            for cfg in self._command_configs:
                if not cfg.get("enabled", True):
                    continue
                name = cfg.get("name", "")
                description = cfg.get("description", "")
                source = cfg.get("source", "")
                code = cfg.get("code", "")

                if source == "inline" and code:
                    # 从内嵌代码创建命令
                    try:
                        local_vars = {}
                        exec(code, {"__builtins__": __builtins__}, local_vars)
                        handler = local_vars.get("handler")
                        if handler:
                            command_system.register_cmd(name, handler, description=description)
                            count += 1
                    except Exception as e:
                        logger.error(f"加载内嵌命令 '{name}' 失败: {e}")

        # 应用 Python 插件配置
        for cfg in self._plugin_configs:
            if not cfg.get("enabled", True):
                continue
            source = cfg.get("source", "")
            if source and os.path.isfile(os.path.expanduser(source)):
                try:
                    self._load_python_plugin(
                        os.path.expanduser(source),
                        skill_manager=skill_manager,
                        command_system=command_system,
                    )
                    count += 1
                except Exception as e:
                    logger.error(f"加载 Python 插件失败 {source}: {e}")

        return count

    # ---- 获取配置 ----

    @property
    def skills(self) -> List[Dict]:
        return self._skills_config

    @property
    def mcp(self) -> List[Dict]:
        return self._mcp_configs

    @property
    def commands(self) -> List[Dict]:
        return self._command_configs

    @property
    def plugins(self) -> List[Dict]:
        return self._plugin_configs

    def summary(self) -> Dict:
        """获取加载摘要"""
        return {
            "skills": len(self._skills_config),
            "mcp_servers": len(self._mcp_configs),
            "commands": len(self._command_configs),
            "plugins": len(self._plugin_configs),
            "loaded_paths": list(self._loaded_paths),
        }

    # ---- Python 插件加载 ----

    def _load_python_plugin(self, path: str, **managers):
        """从 Python 文件加载插件"""
        path = os.path.expanduser(path)
        if not os.path.isfile(path):
            return

        mod_name = f"_xyz_plugin_{os.path.basename(path)}"

        # 动态导入
        spec = importlib.util.spec_from_file_location(mod_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"无法加载插件: {path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)

        # 调用插件初始化函数
        if hasattr(module, "setup"):
            module.setup(
                skill_manager=managers.get("skill_manager"),
                command_system=managers.get("command_system"),
                mcp_manager=managers.get("mcp_manager"),
                tool_registry=managers.get("tool_registry"),
            )

        logger.info(f"Python 插件已加载: {path}")


# ============================================================
# 快捷函数
# ============================================================

_default_loader: Optional[ExtensionLoader] = None


def get_default_loader() -> ExtensionLoader:
    """获取默认加载器"""
    global _default_loader
    if _default_loader is None:
        _default_loader = ExtensionLoader()
    return _default_loader


def load_extensions() -> Dict:
    """快捷加载所有默认位置的扩展"""
    loader = get_default_loader()
    loader.load_default_locations()
    return loader.summary()


def generate_sample_config(path: str = "~/.xyz-agent/extensions.yaml"):
    """生成示例扩展配置文件"""
    path = os.path.expanduser(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(SAMPLE_CONFIG)
    return path
