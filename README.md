# Java代码关联MCP工具

基于Python的fastmcp框架构建的Java代码分析工具，用于扫描Git仓库、解析Java堆栈和分析代码依赖关系。

## 特性

- Git仓库克隆和扫描 (支持GitHub、GitLab、Gitee)
- Java错误堆栈解析
- Java代码AST分析和方法调用关系图构建
- MCP协议适配，提供标准接口
- 支持OAuth2鉴权流程
- 智能上下文权重分析

## 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/mcp-java-analyzer.git
cd mcp-java-analyzer

# 安装依赖
pip install -r requirements.txt
```

## 配置

编辑 `mcp_tools/java_analyzer/config.yaml` 文件，添加你的Git平台访问令牌：

```yaml
git:
  github:
    token: "your-github-token"  # GitHub个人访问令牌
  gitlab:
    token: "your-gitlab-token"  # GitLab个人访问令牌
  gitee:
    token: "your-gitee-token"   # Gitee个人访问令牌
```

如果未提供令牌，工具将在运行时通过浏览器提示你进行授权。

## 使用方法

### 分析Java异常堆栈

```python
from mcp_tools.java_analyzer import JavaAnalysisTool

# 创建工具实例
tool = JavaAnalysisTool()

# 准备请求参数
payload = {
    "repo_url": "https://github.com/example-org/java-parser-tool",
    "stacktrace": "java.lang.NullPointerException: Cannot invoke \"String.trim()\" because \"input\" is null\n    at com.example.parser.JsonParser.parse(JsonParser.java:42)"
}

# 调用分析接口
result = tool.analyze_error(payload)

# 处理结果
print(result)
```

### 构建方法调用关系图

```python
from mcp_tools.java_analyzer import JavaAnalysisTool

# 创建工具实例
tool = JavaAnalysisTool()

# 准备请求参数
payload = {
    "repo_url": "https://github.com/example-org/java-parser-tool",
    "class_name": "com.example.parser.JsonParser"
}

# 调用分析接口
result = tool.build_call_graph(payload)

# 处理结果
print(result)
```

## 命令行示例

```bash
# 分析Java异常堆栈
python examples/analyze_java_error.py [optional-github-token]
```

## 智能分析算法

当发现多个潜在关联方法时，工具使用上下文权重分析，优先选择：

1. 近期有变更记录的方法
2. 包含异常处理代码的方法
3. 被多个调用方引用的工具方法

## 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_java_analyzer.py::TestJavaAnalyzer

# 运行集成测试（需要GitHub令牌）
GITHUB_TOKEN=your-token pytest tests/test_java_analyzer.py::TestIntegration
```

## 架构

```
/mcp_tools/java_analyzer/
  ├── git_client.py    # Git操作层
  ├── code_parser.py   # AST分析层
  ├── mcp_adapter.py   # 协议适配层
  └── config.yaml      # 配置文件
```

## 许可证

MIT