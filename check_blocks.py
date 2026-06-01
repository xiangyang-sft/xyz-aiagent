text = open('/root/xyz-aiagent/docs/02-core/notes-06-agent-design-patterns.md').read()
lines = text.split('\n')
in_block = False
open_count = 0
close_count = 0
for i, line in enumerate(lines, 1):
    stripped = line.strip()
    if stripped == '```python' or stripped == '```' or stripped == '```bash':
        if in_block:
            close_count += 1
            in_block = False
        else:
            open_count += 1
            in_block = True
if in_block:
    close_count += 1
print(f'代码块打开: {open_count}, 关闭: {close_count}')
print(f'平衡: {"YES" if open_count == close_count else "NO"}')

# 确认修复后的代码中不再有嵌套问题
for i, line in enumerate(lines, 1):
    stripped = line.strip()
    if '```python' in stripped and 'f\"' in line:
        print(f'  WARN L{i}: ```python inside f-string: {stripped[:60]}')
