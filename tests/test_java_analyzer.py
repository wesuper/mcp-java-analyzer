import os
import pytest
from mcp_tools.java_analyzer import JavaAnalyzer, GitScanner, JavaAnalysisTool

# 测试数据
SAMPLE_STACKTRACE = """java.lang.NullPointerException: Cannot invoke "String.trim()" because "input" is null
    at com.example.parser.JsonParser.parse(JsonParser.java:42)
    at com.example.api.DataController.processJson(DataController.java:78)
    at com.example.api.DataController.handleRequest(DataController.java:31)"""

SAMPLE_REPO_URL = "https://github.com/example-org/java-parser-tool"

class TestJavaAnalyzer:
    """测试Java分析器"""
    
    def test_parse_stacktrace(self):
        """测试堆栈解析"""
        analyzer = JavaAnalyzer()
        result = analyzer.parse_stacktrace(SAMPLE_STACKTRACE)
        
        assert result["exception_type"] == "java.lang.NullPointerException"
        assert "Cannot invoke" in result["message"]
        assert len(result["frames"]) == 3
        
        # 检查第一帧
        assert result["frames"][0]["class_name"] == "com.example.parser.JsonParser"
        assert result["frames"][0]["method_name"] == "parse"
        assert result["frames"][0]["file_name"] == "JsonParser.java"
        assert result["frames"][0]["line_number"] == 42
    
    def test_has_exception_handling(self):
        """测试异常处理检测"""
        analyzer = JavaAnalyzer()
        
        # 有异常处理的代码
        code_with_exception = """
        public String processData(String input) {
            try {
                return input.trim();
            } catch (NullPointerException e) {
                return "";
            }
        }
        """
        
        # 没有异常处理的代码
        code_without_exception = """
        public String processData(String input) {
            return input.trim();
        }
        """
        
        assert analyzer.has_exception_handling(code_with_exception) == True
        assert analyzer.has_exception_handling(code_without_exception) == False
    
    def test_check_null_handling(self):
        """测试空值检查检测"""
        analyzer = JavaAnalyzer()
        
        # 有空值检查的代码
        code_with_null_check = """
        public String processData(String input) {
            if (input != null) {
                return input.trim();
            }
            return "";
        }
        """
        
        # 没有空值检查的代码
        code_without_null_check = """
        public String processData(String input) {
            return input.trim();
        }
        """
        
        assert analyzer.check_null_handling(code_with_null_check) == True
        assert analyzer.check_null_handling(code_without_null_check) == False

class TestGitScanner:
    """测试Git扫描器"""
    
    @pytest.mark.skipif(not os.environ.get("GITHUB_TOKEN"), reason="需要GitHub令牌")
    def test_clone_repo(self):
        """测试仓库克隆（需要GitHub令牌）"""
        scanner = GitScanner()
        token = os.environ.get("GITHUB_TOKEN")
        
        # 使用公开仓库进行测试
        test_repo = "https://github.com/octocat/Hello-World"
        repo_path = scanner.clone_repo(test_repo, token)
        
        # 检查是否成功克隆
        assert os.path.exists(repo_path)
        assert os.path.isdir(repo_path)
    
    def test_find_java_files(self, tmp_path):
        """测试Java文件查找"""
        # 创建测试目录结构
        java_file1 = tmp_path / "src" / "main" / "java" / "Test.java"
        java_file2 = tmp_path / "src" / "test" / "java" / "TestTest.java"
        non_java_file = tmp_path / "src" / "main" / "resources" / "config.xml"
        
        # 确保目录存在
        java_file1.parent.mkdir(parents=True)
        java_file2.parent.mkdir(parents=True)
        non_java_file.parent.mkdir(parents=True)
        
        # 创建文件
        java_file1.write_text("public class Test {}")
        java_file2.write_text("public class TestTest {}")
        non_java_file.write_text("<config></config>")
        
        # 测试查找
        scanner = GitScanner()
        java_files = scanner.find_java_files(str(tmp_path))
        
        # 应该找到两个Java文件
        assert len(java_files) == 2
        assert str(java_file1) in java_files
        assert str(java_file2) in java_files

class TestJavaAnalysisTool:
    """测试Java分析MCP工具"""
    
    def test_analyze_error_validation(self):
        """测试错误分析输入验证"""
        tool = JavaAnalysisTool()
        
        # 缺少必要参数
        result = tool.analyze_error({})
        assert result["status"] == "error"
        assert "缺少必要的参数" in result["message"]
        
        # 只有仓库URL
        result = tool.analyze_error({"repo_url": SAMPLE_REPO_URL})
        assert result["status"] == "error"
        
        # 只有堆栈信息
        result = tool.analyze_error({"stacktrace": SAMPLE_STACKTRACE})
        assert result["status"] == "error"
    
    def test_build_call_graph_validation(self):
        """测试调用图构建输入验证"""
        tool = JavaAnalysisTool()
        
        # 缺少必要参数
        result = tool.build_call_graph({})
        assert result["status"] == "error"
        assert "缺少必要的参数" in result["message"]
        
        # 只有仓库URL
        result = tool.build_call_graph({"repo_url": SAMPLE_REPO_URL})
        assert result["status"] == "error"
        
        # 只有类名
        result = tool.build_call_graph({"class_name": "com.example.Test"})
        assert result["status"] == "error"

# 集成测试 - 需要实际的GitHub令牌
@pytest.mark.skipif(not os.environ.get("GITHUB_TOKEN"), reason="需要GitHub令牌")
class TestIntegration:
    """集成测试"""
    
    def test_oauth2_auth_flow(self):
        """测试GitHub的OAuth2鉴权流程"""
        # 使用环境变量中的令牌
        token = os.environ.get("GITHUB_TOKEN")
        scanner = GitScanner()
        
        # 尝试访问私有仓库
        # 注意：这需要一个实际的私有仓库和有权限的令牌
        private_repo = os.environ.get("PRIVATE_REPO", "https://github.com/octocat/private-repo")
        
        try:
            repo_path = scanner.clone_repo(private_repo, token)
            # 如果成功，检查仓库是否被克隆
            assert os.path.exists(repo_path)
            assert os.path.isdir(repo_path)
        except ValueError as e:
            # 如果失败，应该是因为令牌没有权限或仓库不存在
            assert "仓库克隆失败" in str(e) 