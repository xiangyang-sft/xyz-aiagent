#!/bin/bash
cd /root/xyz-aiagent
git add -A
git commit -m "fix: 修复代码块内嵌套 backtick 导致 markdown 渲染断裂"
git push
