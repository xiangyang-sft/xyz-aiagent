---
name: git-helper
description: "Git 操作助手 Skill — 当用户要求执行 git 相关操作（提交、推送、分支、查看状态、日志、回退等）时激活。通过引用内置 run_command 工具执行真实 git 命令。"
version: 1.0.0
author: xyz-agent
license: MIT
metadata:
  hermes:
    tags: [git, devops, version-control, terminal]
    related_skills: [devops]
---

# Git Helper Skill

协助完成 git 版本控制操作。

## 使用场景
- git status / git log 查看状态与历史
- git add / git commit / git push 提交与推送
- git branch / git checkout 分支管理
- 回滚与撤销

## 提供的工具

本 skill **引用内置系统工具** run_command 执行 git 命令（不重复造轮子）：

```json
[
  {
    "name": "run_command",
    "description": "执行 git 命令，如'git status'、'git log --oneline'",
    "parameters": {
      "type": "object",
      "properties": {
        "command": { "type": "string", "description": "要执行的 git 命令" },
        "timeout": { "type": "integer", "description": "超时秒数", "default": 30 }
      },
      "required": ["command"]
    }
  }
]
```

## 使用示例

当用户要求提交代码时：
1. 先运行 run_command("git status") 查看改动
2. 再运行 run_command('git add .')、run_command('git commit -m "..."')
3. 最后运行 run_command("git push origin main")
