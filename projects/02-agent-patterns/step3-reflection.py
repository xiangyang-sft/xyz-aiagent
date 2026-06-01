"""
Reflection 模式实现：Actor-Critic 自我改进循环
Step 3 - 代码生成 + 审查 + 改进的多轮迭代
"""

from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── 角色 Prompt ────────────────────────────────────────

ACTOR_SYSTEM = """你是一个 Python 代码生成器。根据用户需求生成高质量代码。

要求：
1. 输出纯代码，不要额外解释
2. 包含完整的函数定义、类型注解、docstring
3. 处理边缘情况（空值、异常等）
4. 代码风格遵循 PEP 8

输出格式：
```python
# 你的代码
```"""

CRITIC_SYSTEM = """你是一个严格的高级代码审查员。检查以下方面：

1. ❌ 语法错误 — 代码能否正常运行？
2. ❌ 逻辑错误 — 算法是否正确？
3. ❌ 边界情况 — 空列表、None、0、负数等是否处理？
4. ❌ 代码风格 — 命名、缩进、类型注解？
5. ❌ 性能问题 — 是否有更高效的实现？
6. ❌ 安全性 — 是否有注入或安全问题？

输出格式：
- 如果代码完美无缺：✅ 代码通过审查
- 如果发现问题，列出所有问题，每条格式：
  [严重度: 高/中/低] 问题描述
  建议：改进建议"""

REFINER_SYSTEM = """你是一个代码改进专家。根据审查反馈改进代码。

原始需求：{prompt}

审查反馈：
{review}

输出改进后的代码，用 ```python ``` 包裹。只输出代码，不要解释。"""

# ── 核心逻辑 ──────────────────────────────────────────

def extract_code(text):
    """从 LLM 输出提取 Python 代码"""
    start = text.find("```python")
    if start >= 0:
        start += len("```python")
        end = text.find("```", start)
        if end >= 0:
            return text[start:end].strip()
    # 没有代码块标记，尝试直接取
    return text.strip()

def has_code(text):
    """检查输出是否包含代码"""
    return "```python" in text or "def " in text or "class " in text


def generate_initial(prompt):
    """Actor：生成初始代码"""
    print(f"\n{'='*40}")
    print(f"✏️  第 1 轮 — Actor 生成初始代码")
    print(f"{'='*40}")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": ACTOR_SYSTEM},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    code = extract_code(response.choices[0].message.content)
    print(f"\n```\n{code}\n```")
    return code


def review_code(code, prompt):
    """Critic：审查代码"""
    print(f"\n{'='*40}")
    print(f"🔍 Critic 审查代码")
    print(f"{'='*40}")

    review_prompt = f"""用户需求：{prompt}

代码：
```
{code}
```

请严格审查这段代码："""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": CRITIC_SYSTEM},
            {"role": "user", "content": review_prompt}
        ],
        temperature=0
    )
    review = response.choices[0].message.content.strip()
    print(f"\n{review}")
    return review


def refine_code(code, review, prompt):
    """Refiner：根据反馈改进代码"""
    print(f"\n{'='*40}")
    print(f"✏️  Refiner 改进代码")
    print(f"{'='*40}")

    messages = [
        {"role": "system", "content": REFINER_SYSTEM.format(prompt=prompt, review=review)},
        {"role": "user", "content": f"原始代码：\n```\n{code}\n```\n\n请基于审查反馈改进代码："}
    ]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3
    )
    new_code = extract_code(response.choices[0].message.content)
    print(f"\n```\n{new_code}\n```")
    return new_code


def reflection_loop(prompt, max_iterations=4):
    """
    Reflection 主循环

    流程：Actor 生成 → Critic 审查 → Refiner 改进 → Critic 再审 → ...
    直到：通过审查或达到最大迭代次数
    """
    print(f"\n{'='*60}")
    print(f"🎭 Reflection 模式：Actor-Critic 循环")
    print(f"📝 需求: {prompt}")
    print(f"🔄 最大迭代: {max_iterations} 轮")
    print(f"{'='*60}")

    # 第 1 轮：Actor 生成
    current_code = generate_initial(prompt)
    iterations = 1

    while iterations < max_iterations:
        # Critic 审查
        review = review_code(current_code, prompt)
        iterations += 1

        # 检查是否通过
        if "✅ 代码通过审查" in review:
            print(f"\n{'='*40}")
            print(f"🎉 代码在第 {iterations-1} 轮通过审查！")
            print(f"{'='*40}")
            break

        # Refiner 改进
        current_code = refine_code(current_code, review, prompt)
        iterations += 1

    print(f"\n{'='*60}")
    print(f"✅ 最终代码（经过 {iterations-1} 轮迭代）")
    print(f"{'='*60}")
    print(f"\n```\n{current_code}\n```")

    return current_code


def test_code(code):
    """尝试执行生成的代码进行验证"""
    print(f"\n{'='*40}")
    print(f"🧪 运行测试")
    print(f"{'='*40}")

    try:
        # 编译检查语法
        compile(code, "<string>", "exec")
        print("✅ 语法检查通过")

        # 尝试导入并执行
        local_ns = {}
        exec(code, local_ns)
        print("✅ 模块导入/定义成功")

        # 查找函数并测试
        for name, obj in local_ns.items():
            if callable(obj) and not name.startswith("_"):
                print(f"\n📊 测试函数: {name}")
                try:
                    # 尝试几个简单输入
                    test_cases = [
                        ([1, 2, 3, 4, 5, 6],),
                        ([],),
                        ([2, 4, 6],),
                    ]
                    for args in test_cases:
                        try:
                            result = obj(*args)
                            print(f"   {name}{args} → {result}")
                        except Exception as e:
                            print(f"   {name}{args} → ❌ {e}")
                except Exception as e:
                    print(f"   测试失败: {e}")

    except SyntaxError as e:
        print(f"❌ 语法错误: {e}")
    except Exception as e:
        print(f"⚠️  其他错误: {e}")


def interactive():
    """交互式演示"""
    print("=" * 60)
    print("Reflection 模式 — Actor-Critic 代码生成")
    print("输入需求，Agent 会多轮迭代生成高质量代码")
    print("输入 'exit' 退出")
    print("=" * 60)

    while True:
        prompt = input("\n🧑 需求: ").strip()
        if prompt.lower() in ("exit", "quit", "q"):
            print("再见！")
            break
        if not prompt:
            continue

        code = reflection_loop(prompt)
        test_code(code)


if __name__ == "__main__":
    # 演示：生成一个处理函数，要求包含边缘情况处理
    prompt = (
        "写一个 Python 函数 even_squares(nums)，输入一个整数列表，"
        "返回所有偶数的平方组成的新列表。"
        "要求：1）处理空列表 2）处理 None 输入 3）处理非整数元素 "
        "4）使用类型注解 5）包含完整 docstring"
    )
    final_code = reflection_loop(prompt)
    test_code(final_code)
