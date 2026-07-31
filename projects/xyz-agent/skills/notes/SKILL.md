---
name: notes
description: "笔记管理 Skill — 当用户要求创建、读取、整理或搜索笔记、待办、日记时激活。通过引用内置 file 工具（write_file/read_file/list_dir）读写文本笔记。"
version: 1.0.0
author: xyz-agent
license: MIT
metadata:
  hermes:
    tags: [notes, memory, organization, file]
    related_skills: [devops]
---

# Notes Skill

协助创建和管理文本笔记。

## 使用场景
- 记录待办事项、灵感、日记
- 读取 / 搜索已有笔记
- 整理笔记目录结构

## 提供的工具

本 skill **引用内置 file 系统工具**读写笔记文件：

```json
[
  {
    "name": "write_file",
    "description": "写入一条笔记（path 用笔记目录下的路径）",
    "parameters": {
      "type": "object",
      "properties": {
        "path": { "type": "string", "description": "笔记文件路径" },
        "content": { "type": "string", "description": "笔记内容" }
      },
      "required": ["path", "content"]
    }
  },
  {
    "name": "read_file",
    "description": "读取一条笔记内容"
  }
]
```

## 使用示例

当用户说"记一条待办"时，用 write_file 追加保存；
当用户说"读我的笔记"时，用 read_file 读取。
