#!/usr/bin/env python3
"""Step 3: 监督者模式 + 流水线协作

核心模式：
- 监督者模式：一个 Supervisor 管理多个 Worker
- 流水线模式：Agent 按顺序处理，前一个输出是后一个输入

学习目标：
- 理解 Supervisor-Worker 架构
- 掌握流水线编排（Pipeline）
- 体会任务调度与质量校验
"""

import json
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "YOUR_API_KEY_HERE"),
)


# ═══════════════════════════════════════════════════════════════
# 基类
# ═══════════════════════════════════════════════════════════════

def call_llm(system: str, user: str, model: str = "gpt-4o-mini", temp: float = 0.3) -> str:
    """通用 LLM 调用"""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temp,
    )
    return response.choices[0].message.content


# ═══════════════════════════════════════════════════════════════
# 模式 A：监督者模式（Supervisor Pattern）
# ═══════════════════════════════════════════════════════════════

SUPERVISOR_PROMPT = """你是 AI 团队的项目监督者（Supervisor）。

你的职责：
1. 接收用户需求，分解为多个子任务
2. 将子任务分配给以下 Worker Agent：
   - 【需求分析师】负责分析需求、产出 PRD
   - 【架构师】负责技术设计
   - 【开发者】负责编码实现
3. 检查每个 Worker 的产出质量
4. 如果质量不达标，要求 Worker 修改
5. 在所有子任务完成后，整合最终输出

质量检查标准：
- 完整性：是否覆盖了所有需求
- 一致性：是否有内部矛盾
- 可行性：方案是否可执行
- 清晰度：是否表达明确"""

WORKER_PROMPTS = {
    "需求分析师": """你是需求分析师。擅长将模糊的需求转化为清晰的 PRD。

输出格式：
## 需求分析
- 核心目标
- 用户角色
- 功能列表
- 业务规则
- 验收标准""",
    
    "架构师": """你是系统架构师。擅长根据 PRD 设计技术架构。

输出格式：
## 技术设计
- 整体架构图（文字描述）
- 技术选型
- 核心模块
- 数据流
- 关键接口
- 非功能性需求设计""",
    
    "开发者": """你是资深开发者。擅长根据技术设计编写高质量代码。

输出说明：
- 用 Python 实现核心功能
- 包含完整代码和必要注释
- 提供使用示例
- 考虑边界情况和错误处理""",
}


class Supervisor:
    """监督者"""
    
    def __init__(self):
        self.max_retries = 2  # 每个 Worker 最多改几次
    
    def run(self, task: str, verbose: bool = True) -> dict:
        """执行监督者工作流"""
        
        # Step 1: 需求分析
        if verbose:
            print(f"\n{'='*60}")
            print("🔄 监督者模式启动")
            print(f"{'='*60}")
            print(f"任务: {task}\n")
        
        outputs = {}
        
        # Step 2-4: 依次分配给 Worker
        workers = ["需求分析师", "架构师", "开发者"]
        
        for worker_name in workers:
            if verbose:
                print(f"\n── Worker: {worker_name} ──")
            
            success = False
            for attempt in range(1, self.max_retries + 2):
                # 准备上下文
                context = f"原始任务：{task}\n\n"
                for name, out in outputs.items():
                    context += f"\n=== {name} 的输出 ===\n{out}\n"
                
                # Worker 执行
                result = call_llm(
                    system=WORKER_PROMPTS[worker_name],
                    user=f"{context}\n\n请完成你的工作：",
                    temp=0.3,
                )
                
                if verbose:
                    print(f"  → 第 {attempt} 次完成" + 
                          (f" (正在检查质量...)" if attempt <= self.max_retries else ""))
                
                # Supervisor 质量检查
                if attempt <= self.max_retries:
                    check = call_llm(
                        system=SUPERVISOR_PROMPT,
                        user=f"""请检查以下工作的质量：
                        
Worker: {worker_name}
任务: {task}
产出: {result}

质量检查标准：
1. 完整性：是否覆盖了所有需求？
2. 一致性：是否有内部矛盾？
3. 可行性：方案是否可执行？
4. 清晰度：是否表达明确？

回复格式：
通过/需要修改
理由：...
改进建议：...""",
                        temp=0.2,
                    )
                    
                    if "通过" in check[:50]:
                        success = True
                        if verbose:
                            print(f"  ✓ 质量检查通过")
                        break
                    else:
                        if verbose:
                            print(f"  ⚠ 质量检查不通过，修改中...")
                            print(f"    反馈: {check[:200]}...")
                else:
                    success = True
                    if verbose:
                        print(f"  → 达到最大重试次数，接受当前产出")
            
            outputs[worker_name] = result
        
        # Step 5: 整合最终输出
        if verbose:
            print(f"\n── Supervisor 整合最终报告 ──")
        
        final = call_llm(
            system=SUPERVISOR_PROMPT,
            user=f"""请整合以下所有 Worker 的产出，生成最终报告：

原始任务：{task}

需求分析：
{outputs['需求分析师']}

技术设计：
{outputs['架构师']}

实现代码：
{outputs['开发者']}

请输出简洁完整的最终报告，突出关键内容。""",
            temp=0.3,
        )
        
        outputs["final"] = final
        
        if verbose:
            print(f"✅ 监督者模式完成！")
            print(f"\n最终报告：\n{final[:800]}...")
        
        return outputs


# ═══════════════════════════════════════════════════════════════
# 模式 B：流水线模式（Pipeline Pattern）
# ═══════════════════════════════════════════════════════════════

class PipelineAgent:
    """流水线中的单个处理节点"""
    
    def __init__(self, name: str, system_prompt: str, process_func=None):
        self.name = name
        self.system_prompt = system_prompt
        self.process_func = process_func  # 可选：自定义处理函数
    
    def process(self, input_data: str) -> str:
        """处理输入并返回输出"""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"请处理以下输入：\n\n{input_data}"},
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content


class Pipeline:
    """流水线编排器"""
    
    def __init__(self, name: str):
        self.name = name
        self.stages: list[PipelineAgent] = []
    
    def add_stage(self, agent: PipelineAgent):
        """添加处理阶段"""
        self.stages.append(agent)
    
    def execute(self, input_data: str, verbose: bool = True) -> list[str]:
        """执行流水线"""
        outputs = []
        current = input_data
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"🔗 流水线模式启动: {self.name}")
            print(f"{'='*60}")
            print(f"输入: {current[:150]}...\n")
        
        for i, stage in enumerate(self.stages):
            if verbose:
                stage_name = f"[{i+1}/{len(self.stages)}] {stage.name}"
                print(f"  → {stage_name}")
            
            current = stage.process(current)
            outputs.append(current)
            
            if verbose:
                preview = current[:200].replace('\n', ' ')
                print(f"  ✓ 完成: {preview}...\n")
        
        if verbose:
            print(f"{'='*60}")
            print(f"✅ 流水线完成！最终输出长度: {len(current)} 字符")
            print(f"{'='*60}")
        
        return outputs


def build_code_review_pipeline() -> Pipeline:
    """构建代码审查流水线"""
    pipeline = Pipeline("代码审查流水线")
    
    pipeline.add_stage(PipelineAgent(
        name="静态分析",
        system_prompt="""你是代码静态分析专家。检查以下方面：
1. 语法和类型问题
2. 未使用的变量/导入
3. 潜在的空指针/异常
4. 代码风格问题

输出分析报告（JSON 格式）。""",
    ))
    
    pipeline.add_stage(PipelineAgent(
        name="安全审计",
        system_prompt="""你是安全审计专家。检查以下方面：
1. SQL 注入风险
2. XSS 风险
3. 敏感信息泄露
4. 认证/授权问题
5. 依赖安全

输出安全审计报告。""",
    ))
    
    pipeline.add_stage(PipelineAgent(
        name="性能优化",
        system_prompt="""你是性能优化专家。分析以下方面：
1. 算法复杂度
2. 不必要的计算
3. 内存使用
4. I/O 效率
5. 缓存机会

输出性能优化建议。""",
    ))
    
    pipeline.add_stage(PipelineAgent(
        name="总结报告",
        system_prompt="""你是代码审查总结员。将前面的分析结果整合为一份清晰的总报告。
按优先级排序：Critical > Major > Minor
每个问题标注影响的文件/行号。
给出整体评分和改进建议。""",
    ))
    
    return pipeline


# ═══════════════════════════════════════════════════════════════
# 主程序
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("🏛️ 监督者模式 + 流水线模式演示")
    print("=" * 60)
    
    # === 模式 A: 监督者模式 ===
    print("\n" + "★" * 60)
    print("模式 A：监督者模式 — 开发一个小功能")
    print("★" * 60)
    
    supervisor = Supervisor()
    outputs = supervisor.run("开发一个 Python 函数，计算字符串中每个字符的出现频率，忽略大小写和空格")
    
    # === 模式 B: 流水线模式 ===
    print("\n\n" + "★" * 60)
    print("模式 B：流水线模式 — 代码审查")
    print("★" * 60)
    
    sample_code = '''
def get_user(user_id):
    query = "SELECT * FROM users WHERE id = " + user_id
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute(query)
    result = cursor.fetchall()
    # 循环打印结果
    for r in result:
        print(r)
    return result
'''
    
    pipeline = build_code_review_pipeline()
    outputs = pipeline.execute(sample_code)
    
    print("\n" + "=" * 60)
    print("✅ 所有模式演示完成！")
    print("=" * 60)
