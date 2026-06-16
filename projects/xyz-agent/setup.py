#!/usr/bin/env python3
"""
xyz-agent — 轻量级 AI Agent 框架

从最小可用到生产就绪，渐进式构建你自己的 Agent 框架。
"""

from setuptools import setup, find_packages

setup(
    name="xyz-agent",
    version="0.1.0",
    description="轻量级 AI Agent 框架 — 从最小可用到生产就绪",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="向阳",
    author_email="",
    url="https://github.com/xiangyang-sft/xyz-aiagent",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        # 核心引擎零依赖（仅标准库）
        # 可选依赖：
        # openai — 真实 LLM 调用
        # chromadb — 向量检索
        # click — CLI 工具
    ],
    extras_require={
        "cli": ["click>=8.0"],
        "llm": ["openai>=1.0"],
        "rag": ["chromadb>=0.4"],
        "all": ["click>=8.0", "openai>=1.0", "chromadb>=0.4"],
    },
    entry_points={
        "console_scripts": [
            "xyz-agent=xyz_agent.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "License :: Free for non-commercial use",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords="ai, agent, llm, react, framework, education",
    project_urls={
        "Source": "https://github.com/xiangyang-sft/xyz-aiagent",
        "Documentation": "https://github.com/xiangyang-sft/xyz-aiagent/tree/main/projects/xyz-agent",
    },
)
