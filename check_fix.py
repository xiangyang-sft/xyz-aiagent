# check step3
src = open('/root/xyz-aiagent/projects/02-agent-patterns/step3-reflection.py').read()
print('step3.py 中 ```python 出现次数:', src.count('```python'))

# check note
md = open('/root/xyz-aiagent/docs/02-core/notes-06-agent-design-patterns.md').read()
lines = md.split('\n')
in_block = False
oc = 0
cc = 0
for line in lines:
    s = line.strip()
    if s in ('```python', '```', '```bash'):
        if in_block:
            cc += 1
            in_block = False
        else:
            oc += 1
            in_block = True
if in_block:
    cc += 1
print(f'笔记文档: 打开={oc}, 关闭={cc}, 平衡={"YES" if oc==cc else "NO"}')
