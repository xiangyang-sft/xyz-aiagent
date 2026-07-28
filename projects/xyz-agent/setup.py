#!/usr/bin/env python3
"""xyz-agent — Agent 框架"""
from setuptools import setup, find_packages

setup(
    name="xyz-agent",
    version="1.0.0",
    description="学习驱动的 Agent 框架 — ReAct / Skill / MCP / Function Calling",
    author="向阳",
    url="https://github.com/xiangyang-sft/xyz-aiagent",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=["pyyaml>=6.0"],
    extras_require={
        "openai": ["httpx>=0.27"],
        "full": ["httpx>=0.27", "pyyaml>=6.0"],
    },
    entry_points={
        "console_scripts": ["xyz-agent=xyz_agent.cli:main"],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
)
