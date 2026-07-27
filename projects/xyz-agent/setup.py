#!/usr/bin/env python3
"""
xyz-agent — 生产级 AI Agent 框架
"""

from setuptools import setup, find_packages

setup(
    name="xyz-agent",
    version="1.0.0",
    description="生产级 AI Agent 框架 — 支持 Skill/MCP/Commands/Function Calling",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="向阳",
    url="https://github.com/xiangyang-sft/xyz-aiagent",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        # 核心引擎零依赖（仅标准库）
        "pyyaml>=6.0",       # SKILL.md frontmatter 解析
    ],
    extras_require={
        "cli": ["click>=8.0"],
        "openai": ["openai>=1.0", "httpx>=0.27"],
        "rag": ["chromadb>=0.4"],
        "full": [
            "click>=8.0",
            "openai>=1.0",
            "httpx>=0.27",
            "pyyaml>=6.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "xyz-agent=xyz_agent.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords="ai, agent, llm, react, mcp, skill, function-calling, framework",
    project_urls={
        "Source": "https://github.com/xiangyang-sft/xyz-aiagent",
        "Documentation": "https://github.com/xiangyang-sft/xyz-aiagent/tree/main/projects/xyz-agent",
    },
)
