#!/usr/bin/env python
"""
示例脚本：分析Java异常堆栈

该脚本演示如何使用Java代码分析工具分析异常堆栈。
"""

import os
import sys
import json
import asyncio

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mcp_tools.java_analyzer import JavaAnalysisTool

# 示例堆栈
SAMPLE_STACKTRACE = """java.lang.NullPointerException: Cannot invoke "String.trim()" because "input" is null
    at com.example.parser.JsonParser.parse(JsonParser.java:42)
    at com.example.api.DataController.processJson(DataController.java:78)
    at com.example.api.DataController.handleRequest(DataController.java:31)"""

# 示例仓库URL
SAMPLE_REPO_URL = "https://github.com/example-org/java-parser-tool"

async def main():
    # 创建分析工具实例
    tool = JavaAnalysisTool()
    
    # 如果命令行提供了GitHub令牌，使用它
    github_token = None
    if len(sys.argv) > 1:
        github_token = sys.argv[1]
    
    # 准备请求负载
    payload = {
        "repo_url": SAMPLE_REPO_URL,
        "stacktrace": SAMPLE_STACKTRACE
    }
    
    if github_token:
        payload["token"] = github_token
    
    # 调用分析接口
    print(f"分析Java异常堆栈...")
    print(f"仓库: {SAMPLE_REPO_URL}")
    print(f"堆栈: {SAMPLE_STACKTRACE[:50]}...")
    
    result = tool.analyze_error(payload)
    
    # 打印结果
    print("\n分析结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    # 在Python 3.7+中，可以直接使用asyncio.run()
    asyncio.run(main()) 