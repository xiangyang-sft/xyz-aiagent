import sys
data = open(sys.argv[1], 'r').read()
data = data.replace('```python\n{code}\n```', '```\n{code}\n```')
data = data.replace('f"\n```python\n{code}\n```"', 'f"\n```\n{code}\n```"')
data = data.replace('f"\n```python\n{new_code}\n```"', 'f"\n```\n{new_code}\n```"')
data = data.replace('f"\n```python\n{current_code}\n```"', 'f"\n```\n{current_code}\n```"')
open(sys.argv[1], 'w').write(data)
print('Done')
