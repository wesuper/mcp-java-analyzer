import os
import logging
import json
from typing import Dict, List, Any, Optional
from fastmcp import BaseMcpTool, mcp_endpoint
from .git_client import GitScanner
from .code_parser import JavaAnalyzer

logger = logging.getLogger(__name__)

class JavaAnalysisTool(BaseMcpTool):
    """Java代码分析MCP工具"""
    
    # 工具定义
    tool_name = "java_analysis_tool"
    tool_description = "Java代码分析工具，用于诊断异常和分析代码依赖关系"
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化Java分析工具
        
        Args:
            config_path: 配置文件路径
        """
        super().__init__()
        
        # 获取配置文件路径
        if config_path is None:
            # 默认配置文件路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, "config.yaml")
        
        # 初始化组件
        self.git_scanner = GitScanner(config_path)
        self.code_analyzer = JavaAnalyzer()
    
    @mcp_endpoint("/analyze_java_error")
    def analyze_error(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """MCP协议接口：关联错误与代码
        
        Args:
            payload: 请求负载，包含仓库URL和堆栈信息
            
        Returns:
            分析结果
        """
        # 验证输入
        if "repo_url" not in payload or "stacktrace" not in payload:
            return {
                "status": "error",
                "message": "缺少必要的参数：repo_url 或 stacktrace"
            }
        
        repo_url = payload["repo_url"]
        stacktrace = payload["stacktrace"]
        token = payload.get("token")  # 可选参数
        
        try:
            # 1. 解析堆栈信息
            exception_info = self.code_analyzer.parse_stacktrace(stacktrace)
            
            if not exception_info["frames"]:
                return {
                    "status": "error",
                    "message": "无法解析堆栈信息，请确保堆栈格式正确"
                }
            
            # 2. 获取根异常信息（通常是堆栈的第一帧）
            root_frame = exception_info["frames"][0]
            
            # 3. 克隆仓库
            try:
                repo_path = self.git_scanner.clone_repo(repo_url, token)
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"克隆仓库失败: {str(e)}"
                }
            
            # 4. 查找Java文件
            java_files = self.git_scanner.find_java_files(repo_path)
            
            if not java_files:
                return {
                    "status": "warning",
                    "message": "仓库中未找到Java文件",
                    "exception_info": exception_info
                }
            
            # 5. 处理Java文件，建立调用关系图
            self.code_analyzer.process_java_files(java_files)
            
            # 6. 查找与异常相关的方法
            root_class = root_frame["class_name"]
            root_method = root_frame["method_name"]
            related_methods = self.code_analyzer.find_related_methods(root_class, root_method)
            
            # 7. 查找异常处理器
            exception_type = exception_info["exception_type"]
            exception_handlers = self.code_analyzer.find_exception_handlers(root_class, exception_type.split(".")[-1])
            
            # 8. 构建文件内容映射
            file_contents = {}
            file_commits = {}
            exception_handling = {}
            
            for key, method_info in related_methods.items():
                file_path = method_info["file_path"]
                
                # 仅处理尚未读取的文件
                if file_path not in file_contents:
                    file_contents[file_path] = self.git_scanner.read_file_content(file_path)
                    file_commits[file_path] = self.git_scanner.get_file_last_commit(repo_path, file_path)
                
                # 检查方法是否包含异常处理
                method_class = method_info["class_name"]
                method_name = method_info["method_name"]
                
                # 尝试从文件内容中提取方法的代码
                try:
                    method_pattern = fr'(public|private|protected)?\s+\w+\s+{method_name}\s*\([^\)]*\)\s*\{{'
                    import re
                    method_match = re.search(method_pattern, file_contents[file_path])
                    
                    if method_match:
                        method_start = method_match.start()
                        # 简单地查找方法结束的大括号（实际中需要更复杂的解析）
                        brace_count = 0
                        method_code = ""
                        for i, char in enumerate(file_contents[file_path][method_start:]):
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    method_code = file_contents[file_path][method_start:method_start + i + 1]
                                    break
                        
                        # 检查方法代码是否包含异常处理
                        if method_code:
                            exception_handling[key] = {
                                "has_exception_handling": self.code_analyzer.has_exception_handling(method_code),
                                "has_null_check": self.code_analyzer.check_null_handling(method_code)
                            }
                except Exception as e:
                    logger.error(f"提取方法代码失败: {str(e)}")
                    exception_handling[key] = {
                        "has_exception_handling": False,
                        "has_null_check": False
                    }
            
            # 9. 使用LLM进行上下文权重分析
            weighted_methods = self._weight_methods(related_methods, file_commits, exception_handling)
            
            # 10. 构建输出
            result = {
                "status": "success",
                "exception_info": exception_info,
                "root_cause": {
                    "class": root_class,
                    "method": root_method,
                    "line": root_frame["line_number"]
                },
                "related_methods": [
                    {
                        "class": method_info["class_name"],
                        "method": method_info["method_name"],
                        "weight": weight,
                        "file_path": method_info["file_path"],
                        "has_exception_handling": exception_handling.get(key, {}).get("has_exception_handling", False),
                        "has_null_check": exception_handling.get(key, {}).get("has_null_check", False),
                        "last_commit": file_commits.get(method_info["file_path"], {})
                    }
                    for key, (method_info, weight) in weighted_methods.items()
                ],
                "exception_handlers": exception_handlers
            }
            
            return result
            
        except Exception as e:
            logger.exception(f"分析Java错误失败: {str(e)}")
            return {
                "status": "error",
                "message": f"分析过程中出错: {str(e)}"
            }
    
    @mcp_endpoint("/build_call_graph")
    def build_call_graph(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """MCP协议接口：构建方法调用关系图
        
        Args:
            payload: 请求负载，包含仓库URL和类名
            
        Returns:
            调用关系图
        """
        # 验证输入
        if "repo_url" not in payload or "class_name" not in payload:
            return {
                "status": "error",
                "message": "缺少必要的参数：repo_url 或 class_name"
            }
        
        repo_url = payload["repo_url"]
        class_name = payload["class_name"]
        token = payload.get("token")  # 可选参数
        
        try:
            # 1. 克隆仓库
            try:
                repo_path = self.git_scanner.clone_repo(repo_url, token)
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"克隆仓库失败: {str(e)}"
                }
            
            # 2. 查找Java文件
            java_files = self.git_scanner.find_java_files(repo_path)
            
            if not java_files:
                return {
                    "status": "warning",
                    "message": "仓库中未找到Java文件"
                }
            
            # 3. 处理Java文件，建立调用关系图
            self.code_analyzer.process_java_files(java_files)
            
            # 4. 提取调用关系图
            call_graph = {}
            
            # 查找类名对应的文件
            class_file = None
            for key, file_path in self.code_analyzer.class_map.items():
                if key == class_name or key.endswith("." + class_name):
                    class_file = file_path
                    break
            
            if class_file:
                # 读取文件内容
                class_code = self.git_scanner.read_file_content(class_file)
                
                # 构建该类的调用图
                call_graph = self.code_analyzer.build_call_graph(class_code)
            
            # 5. 构建输出
            result = {
                "status": "success",
                "class_name": class_name,
                "call_graph": call_graph
            }
            
            return result
            
        except Exception as e:
            logger.exception(f"构建调用图失败: {str(e)}")
            return {
                "status": "error",
                "message": f"构建调用图过程中出错: {str(e)}"
            }
    
    def _weight_methods(self, methods: Dict, commits: Dict, exception_handling: Dict) -> Dict:
        """对方法进行权重排序
        
        Args:
            methods: 方法信息字典
            commits: 提交信息字典
            exception_handling: 异常处理信息字典
            
        Returns:
            带权重的方法字典，按权重降序排序
        """
        weighted = {}
        
        # 统计方法被引用的次数
        reference_count = {}
        for key, callees in self.code_analyzer.call_graph.items():
            for callee in callees:
                if callee not in reference_count:
                    reference_count[callee] = 0
                reference_count[callee] += 1
        
        # 计算每个方法的权重
        for key, method_info in methods.items():
            weight = 0
            
            # 1. 近期有变更记录的方法
            file_path = method_info["file_path"]
            if file_path in commits and commits[file_path]:
                # 假设有日期信息
                if "date" in commits[file_path]:
                    # 简单地根据提交时间给予权重，可根据需要优化
                    import datetime
                    try:
                        commit_date = datetime.datetime.fromisoformat(commits[file_path]["date"])
                        now = datetime.datetime.now()
                        days_diff = (now - commit_date).days
                        
                        # 最近30天内的变更给予更高权重
                        if days_diff <= 30:
                            weight += 3
                        elif days_diff <= 90:
                            weight += 2
                        else:
                            weight += 1
                    except Exception:
                        weight += 1  # 如果日期解析失败，给予默认权重
            
            # 2. 包含异常处理代码的方法
            if key in exception_handling:
                if exception_handling[key]["has_exception_handling"]:
                    weight += 3
                if exception_handling[key]["has_null_check"]:
                    weight += 2
            
            # 3. 被多个调用方引用的工具方法
            if key in reference_count:
                count = reference_count[key]
                if count >= 5:
                    weight += 3
                elif count >= 2:
                    weight += 2
                else:
                    weight += 1
            
            weighted[key] = (method_info, weight)
        
        # 按权重降序排序
        sorted_weighted = dict(sorted(weighted.items(), key=lambda x: x[1][1], reverse=True))
        
        return sorted_weighted 