import re
import logging
import os
from typing import Dict, List, Set, Tuple, Optional
import javalang
from javalang.tree import ClassDeclaration, MethodDeclaration, MethodInvocation

logger = logging.getLogger(__name__)

class JavaAnalyzer:
    """Java代码分析器，用于解析堆栈和分析代码依赖关系"""
    
    def __init__(self):
        self.class_map = {}  # 类名到文件路径的映射
        self.method_map = {}  # 方法名到类名的映射
        self.call_graph = {}  # 方法调用关系图
    
    def parse_stacktrace(self, stacktrace: str) -> Dict:
        """解析Java错误堆栈，提取类/方法/行号
        
        Args:
            stacktrace: Java错误堆栈
            
        Returns:
            包含异常信息的字典
        """
        result = {
            "exception_type": "",
            "message": "",
            "frames": []
        }
        
        # 提取异常类型和消息
        exception_pattern = r'^([\w\.]+(?:Exception|Error|Throwable)): (.+)'
        exception_match = re.search(exception_pattern, stacktrace, re.MULTILINE)
        
        if exception_match:
            result["exception_type"] = exception_match.group(1)
            result["message"] = exception_match.group(2)
        else:
            # 尝试只匹配异常类型
            simple_pattern = r'^([\w\.]+(?:Exception|Error|Throwable))'
            simple_match = re.search(simple_pattern, stacktrace, re.MULTILINE)
            if simple_match:
                result["exception_type"] = simple_match.group(1)
        
        # 提取堆栈帧
        frame_pattern = r'at\s+([\w\.]+)\.(\w+)\(([\w\.]+):(\d+)\)'
        frames = re.findall(frame_pattern, stacktrace)
        
        for frame in frames:
            class_name, method_name, file_name, line_number = frame
            result["frames"].append({
                "class_name": class_name,
                "method_name": method_name,
                "file_name": file_name,
                "line_number": int(line_number)
            })
        
        return result
    
    def process_java_files(self, file_paths: List[str]) -> None:
        """处理Java文件列表，建立类映射和方法映射
        
        Args:
            file_paths: Java文件路径列表
        """
        for file_path in file_paths:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                self._process_java_content(content, file_path)
                
            except UnicodeDecodeError:
                # 尝试其他编码
                try:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        content = f.read()
                    
                    self._process_java_content(content, file_path)
                    
                except Exception as e:
                    logger.error(f"处理文件失败: {file_path}, 错误: {str(e)}")
            
            except Exception as e:
                logger.error(f"处理文件失败: {file_path}, 错误: {str(e)}")
    
    def _process_java_content(self, content: str, file_path: str) -> None:
        """处理Java文件内容，提取类和方法信息
        
        Args:
            content: Java文件内容
            file_path: 文件路径
        """
        try:
            tree = javalang.parse.parse(content)
            
            # 提取包名
            package_name = tree.package.name if tree.package else ""
            
            # 处理类声明
            for type_decl in tree.types:
                if isinstance(type_decl, ClassDeclaration):
                    class_name = type_decl.name
                    
                    # 完整的类名（带包名）
                    full_class_name = f"{package_name}.{class_name}" if package_name else class_name
                    
                    # 添加到类映射
                    self.class_map[full_class_name] = file_path
                    
                    # 处理方法声明
                    for method_decl in type_decl.methods:
                        method_name = method_decl.name
                        
                        # 添加到方法映射
                        key = f"{full_class_name}.{method_name}"
                        self.method_map[key] = {
                            "class_name": full_class_name,
                            "method_name": method_name,
                            "file_path": file_path
                        }
                        
                        # 处理方法调用
                        self._process_method_calls(full_class_name, method_name, method_decl)
            
        except Exception as e:
            logger.error(f"解析Java文件失败: {file_path}, 错误: {str(e)}")
    
    def _process_method_calls(self, class_name: str, method_name: str, method_decl: MethodDeclaration) -> None:
        """处理方法中的调用关系
        
        Args:
            class_name: 类名
            method_name: 方法名
            method_decl: 方法声明
        """
        method_key = f"{class_name}.{method_name}"
        
        # 初始化调用关系
        if method_key not in self.call_graph:
            self.call_graph[method_key] = set()
        
        # 使用访问者模式来遍历方法声明中的所有方法调用
        method_calls = []
        
        def extract_method_calls(node):
            if isinstance(node, MethodInvocation):
                method_calls.append(node)
            
            # 递归处理子节点
            for child in node.children:
                if isinstance(child, list):
                    for item in child:
                        if hasattr(item, 'children'):
                            extract_method_calls(item)
                elif hasattr(child, 'children'):
                    extract_method_calls(child)
        
        # 从方法体开始遍历
        if hasattr(method_decl, 'body') and method_decl.body:
            for statement in method_decl.body:
                extract_method_calls(statement)
        
        # 处理收集到的方法调用
        for call in method_calls:
            if hasattr(call, 'qualifier') and call.qualifier:
                # 记录方法调用
                called_method = f"{call.qualifier}.{call.member}"
                self.call_graph[method_key].add(called_method)
    
    def build_call_graph(self, java_code: str) -> Dict:
        """通过AST分析建立方法调用关系图
        
        Args:
            java_code: Java代码
            
        Returns:
            方法调用关系图
        """
        call_graph = {}
        
        try:
            tree = javalang.parse.parse(java_code)
            
            # 提取包名
            package_name = tree.package.name if tree.package else ""
            
            # 处理类声明
            for type_decl in tree.types:
                if isinstance(type_decl, ClassDeclaration):
                    class_name = type_decl.name
                    
                    # 完整的类名（带包名）
                    full_class_name = f"{package_name}.{class_name}" if package_name else class_name
                    
                    # 初始化类的调用图
                    call_graph[full_class_name] = {}
                    
                    # 处理方法声明
                    for method_decl in type_decl.methods:
                        method_name = method_decl.name
                        
                        # 初始化方法的调用列表
                        call_graph[full_class_name][method_name] = []
                        
                        # 收集方法调用
                        method_calls = []
                        
                        def extract_method_calls(node):
                            if isinstance(node, MethodInvocation):
                                method_calls.append(node)
                            
                            # 递归处理子节点
                            for child in node.children:
                                if isinstance(child, list):
                                    for item in child:
                                        if hasattr(item, 'children'):
                                            extract_method_calls(item)
                                elif hasattr(child, 'children'):
                                    extract_method_calls(child)
                        
                        # 从方法体开始遍历
                        if hasattr(method_decl, 'body') and method_decl.body:
                            for statement in method_decl.body:
                                extract_method_calls(statement)
                        
                        # 处理收集到的方法调用
                        for call in method_calls:
                            if hasattr(call, 'qualifier') and call.qualifier:
                                qualified_name = call.qualifier
                                
                                # 尝试将限定符映射到完整类名
                                # 这里简化处理，实际代码中可能需要处理导入语句和嵌套类
                                called_class = qualified_name
                                called_method = call.member
                                
                                # 添加到调用图
                                call_graph[full_class_name][method_name].append(f"{called_class}.{called_method}")
        
        except Exception as e:
            logger.error(f"构建调用图失败: {str(e)}")
        
        return call_graph
    
    def find_related_methods(self, class_name: str, method_name: str, depth: int = 2) -> Dict:
        """找出与指定方法相关的所有方法
        
        Args:
            class_name: 类名
            method_name: 方法名
            depth: 搜索深度
            
        Returns:
            相关方法的字典
        """
        method_key = f"{class_name}.{method_name}"
        visited = set()
        related = {}
        
        def dfs(current_key, current_depth):
            if current_depth > depth or current_key in visited:
                return
            
            visited.add(current_key)
            
            if current_key in self.method_map:
                method_info = self.method_map[current_key]
                related[current_key] = method_info
            
            # 处理该方法调用的其他方法
            if current_key in self.call_graph:
                for called in self.call_graph[current_key]:
                    dfs(called, current_depth + 1)
            
            # 处理调用该方法的其他方法
            for caller, callees in self.call_graph.items():
                if current_key in callees:
                    dfs(caller, current_depth + 1)
        
        dfs(method_key, 0)
        
        return related
    
    def find_exception_handlers(self, class_name: str, exception_type: str) -> List[Dict]:
        """查找可能处理指定异常的方法
        
        Args:
            class_name: 类名
            exception_type: 异常类型
            
        Returns:
            可能处理异常的方法列表
        """
        handlers = []
        
        # 如果类不在映射中，返回空列表
        if class_name not in self.class_map:
            return handlers
        
        file_path = self.class_map[class_name]
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 使用正则表达式查找catch块
            # 这是一个简化的实现，可能不够精确
            catch_pattern = fr'catch\s*\(\s*{exception_type}\s+\w+\s*\)'
            catch_blocks = re.findall(catch_pattern, content)
            
            # 如果找到catch块，添加到处理器列表
            if catch_blocks:
                # 查找包含catch块的方法
                tree = javalang.parse.parse(content)
                
                # 提取包名
                package_name = tree.package.name if tree.package else ""
                
                # 遍历类和方法
                for type_decl in tree.types:
                    if isinstance(type_decl, ClassDeclaration) and type_decl.name == class_name.split('.')[-1]:
                        for method_decl in type_decl.methods:
                            method_name = method_decl.name
                            
                            # 检查方法体是否包含异常处理
                            if hasattr(method_decl, 'body') and method_decl.body:
                                method_body = str(method_decl.body)
                                if exception_type in method_body and 'catch' in method_body:
                                    handlers.append({
                                        "class_name": class_name,
                                        "method_name": method_name,
                                        "file_path": file_path
                                    })
        
        except Exception as e:
            logger.error(f"查找异常处理器失败: {str(e)}")
        
        return handlers
    
    def has_exception_handling(self, java_code: str) -> bool:
        """检查代码是否包含异常处理逻辑
        
        Args:
            java_code: Java代码
            
        Returns:
            是否包含异常处理
        """
        # 检查try-catch块
        try_pattern = r'try\s*\{'
        catch_pattern = r'catch\s*\('
        
        if re.search(try_pattern, java_code) and re.search(catch_pattern, java_code):
            return True
        
        # 检查throws声明
        throws_pattern = r'throws\s+[\w\.,\s]+'
        if re.search(throws_pattern, java_code):
            return True
        
        return False
    
    def check_null_handling(self, java_code: str) -> bool:
        """检查代码是否包含空值检查
        
        Args:
            java_code: Java代码
            
        Returns:
            是否包含空值检查
        """
        patterns = [
            r'if\s*\(\s*\w+\s*==\s*null\s*\)',  # if (var == null)
            r'if\s*\(\s*null\s*==\s*\w+\s*\)',  # if (null == var)
            r'if\s*\(\s*\w+\s*!=\s*null\s*\)',  # if (var != null)
            r'if\s*\(\s*null\s*!=\s*\w+\s*\)',  # if (null != var)
            r'Objects\.requireNonNull',  # Objects.requireNonNull
            r'Optional\.'  # Optional API
        ]
        
        for pattern in patterns:
            if re.search(pattern, java_code):
                return True
        
        return False 