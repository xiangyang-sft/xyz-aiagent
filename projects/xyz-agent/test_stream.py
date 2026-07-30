#!/usr/bin/env python3
"""流式功能测试"""
import sys, os
sys.path.insert(0, ".")
os.chdir("/root/xyz-aiagent/projects/xyz-agent")

api_key = open("/tmp/deepseek_key.txt").read().strip()
model = "deepseek-v4-flash"
base_url = "https://api.deepseek.com/v1"

from xyz_agent.providers import OpenAIProvider
from xyz_agent.agent import Agent, AgentConfig
from xyz_agent import tool

results = []

def test(name, fn):
    try:
        fn()
        results.append((name, True))
        print(f"  ✅ {name}")
    except Exception as e:
        import traceback
        results.append((name, False))
        print(f"  ❌ {name}: {e}")
        traceback.print_exc()

print("=" * 60)
print("🧪 流式功能测试")
print("=" * 60)

# 1. 基础流式对话
print("\n📋 [1/5] chat_stream 基础对话")
def t_basic_stream():
    provider = OpenAIProvider(api_key=api_key, model=model, base_url=base_url)
    chunks = list(provider.chat_stream(
        messages=[{"role": "user", "content": "用一句话介绍 DeepSeek"}],
    ))
    text = "".join(chunks)
    assert len(chunks) > 1, f"流式应该产出多个 chunk, 实际 {len(chunks)}"
    assert len(text) > 10, f"文本太短: {text[:50]}"
    assert "DeepSeek" in text or "深度求索" in text
test("t_basic_stream", t_basic_stream)

# 2. Agent.run_stream() 流式运行
print("\n📋 [2/5] Agent.run_stream()")
def t_agent_run_stream():
    agent = Agent(
        llm_provider=OpenAIProvider(api_key=api_key, model=model, base_url=base_url),
        config=AgentConfig(model=model, max_steps=5,
                           react_mode="function_calling",
                           enable_skills=False, auto_load_skills=False,
                           auto_load_extensions=False, enable_commands=False),
    )
    agent.initialize()
    chunks = list(agent.run_stream("中国的首都是什么？"))
    text = "".join(chunks)
    assert len(chunks) > 0
    assert "北京" in text, f"回答不含北京: {text[:100]}"
test("t_agent_run_stream", t_agent_run_stream)

# 3. Agent.chat_stream() 流式多轮对话
print("\n📋 [3/5] Agent.chat_stream()")
def t_chat_stream():
    agent = Agent(
        llm_provider=OpenAIProvider(api_key=api_key, model=model, base_url=base_url),
        config=AgentConfig(model=model, max_steps=5,
                           react_mode="function_calling",
                           enable_skills=False, auto_load_skills=False,
                           auto_load_extensions=False, enable_commands=False),
    )
    agent.initialize()
    r1 = list(agent.chat_stream("你好，我叫向阳"))
    t1 = "".join(r1)
    assert len(t1) > 5
    r2 = list(agent.chat_stream("我叫什么名字？"))
    t2 = "".join(r2)
    assert "向阳" in t2 or "xiang" in t2.lower(), f"上下文丢失: {t2[:100]}"
test("t_chat_stream", t_chat_stream)

# 4. 流式 + Function Calling 工具调用
print("\n📋 [4/5] 流式 + Function Calling")
def t_stream_fc():
    @tool
    def get_capital(country: str) -> str:
        """查询国家首都"""
        data = {"中国":"北京","美国":"华盛顿","日本":"东京"}
        return data.get(country, f"未知: {country}")

    agent = Agent(
        llm_provider=OpenAIProvider(api_key=api_key, model=model, base_url=base_url),
        config=AgentConfig(model=model, max_steps=10,
                           react_mode="function_calling",
                           enable_skills=False, auto_load_skills=False,
                           auto_load_extensions=False, enable_commands=False),
    )
    agent.setup_tools(get_capital)
    agent.initialize()
    chunks = list(agent.run_stream("中国的首都是什么？"))
    text = "".join(chunks)
    assert "北京" in text, f"回答不含北京: {text[:200]}"
    stats = agent.get_stats()
    assert stats["tool_calls"] >= 1, f"工具未调用: {stats}"
test("t_stream_fc", t_stream_fc)

# 5. CLI 流式 run 命令
print("\n📋 [5/5] CLI xyz run 流式")
def t_cli_stream():
    import subprocess
    env = {**os.environ, "OPENAI_API_KEY": api_key, "OPENAI_BASE_URL": base_url,
           "OPENAI_MODEL": model}
    r = subprocess.run(
        [sys.executable, "-m", "xyz_agent.cli", "run", "用一句话介绍AI Agent"],
        capture_output=True, text=True, cwd=".", env=env, timeout=60,
    )
    out = r.stdout.strip()
    assert len(out) > 10, f"输出太短: {out[:50]}"
test("t_cli_stream", t_cli_stream)

# 汇总
total = len(results)
passed = sum(1 for _, ok in results if ok)
print("\n" + "=" * 60)
print(f"📊 结果: {passed}/{total} 通过 ({passed/total*100:.0f}%)")
for name, ok in results:
    icon = "✅" if ok else "❌"
    print(f"  {icon} {name}")
if passed == total:
    print("🎉 全部通过!")
else:
    print(f"⚠️ {total - passed} 项失败")
