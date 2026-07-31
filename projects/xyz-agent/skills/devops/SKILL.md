---
name: devops
description: "DevOps 运维 Skill — 通过引用内置 file/terminal 系统工具，执行项目查看、文件操作、命令执行等运维任务。"
version: 1.0.0
author: xyz-agent
license: MIT
metadata:
  hermes:
    tags: [devops, file, terminal, automation]
    related_skills: []
---

# DevOps Skill

提供项目文件浏览、代码阅读、命令执行等运维能力。

## 使用场景
- 查看项目目录结构和文件内容
- 读取/写入配置文件
- 执行 git、python 等命令
- 排查运行时问题

## 提供的工具

本 skill 不独立实现工具，而是**引用内置系统工具集**（Hermes 风格），
LLM 直接调用以下全局注册的真实能力：

```json
[
  {
    "name": "read_file",
    "description": "读取文本文件内容",
    "parameters": {
      "type": "object",
      "properties": {
        "path": { "type": "string", "description": "文件路径" },
        "max_chars": { "type": "integer", "description": "最大字符数", "default": 100000 }
      },
      "required": ["path"]
    }
  },
  {
    "name": "write_file",
    "description": "写入或追加文本文件"
  },
  {
    "name": "list_dir",
    "description": "列出目录内容"
  },
  {
    "name": "run_command",
    "description": "执行 shell 命令"
  }
]
```

## 使用示例

当用户要求查看项目结构时，使用 list_dir 列出目录。
当用户要求读取某个代码文件时，使用 read_file 读取内容。
当用户要求运行测试时，使用 run_command 执行 `pytest` 或 `python -m pytest`。
