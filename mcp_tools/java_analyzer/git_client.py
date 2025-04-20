import os
import tempfile
import shutil
import logging
from typing import List, Dict, Optional
import requests
import git
from git import Repo
import yaml

logger = logging.getLogger(__name__)

class GitScanner:
    """Git仓库扫描工具，用于克隆仓库和获取Java文件"""
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化Git扫描器
        
        Args:
            config_path: Git配置文件路径，包含认证信息
        """
        self.config = {}
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        
        self.temp_dirs = []  # 跟踪创建的临时目录
    
    def __del__(self):
        """清理临时目录"""
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    logger.info(f"清理临时目录: {temp_dir}")
                except Exception as e:
                    logger.error(f"清理临时目录失败: {temp_dir}, 错误: {str(e)}")
    
    def _get_platform_info(self, repo_url: str) -> Dict:
        """从URL中提取Git平台信息
        
        Args:
            repo_url: 仓库URL
            
        Returns:
            包含平台、所有者和仓库名的字典
        """
        # 支持的平台: GitHub, GitLab, Gitee
        github_pattern = r'github\.com\/([^\/]+)\/([^\/]+)'
        gitlab_pattern = r'gitlab\.com\/([^\/]+)\/([^\/]+)'
        gitee_pattern = r'gitee\.com\/([^\/]+)\/([^\/]+)'
        
        import re
        
        if re.search(github_pattern, repo_url):
            match = re.search(github_pattern, repo_url)
            platform = "github"
        elif re.search(gitlab_pattern, repo_url):
            match = re.search(gitlab_pattern, repo_url)
            platform = "gitlab"
        elif re.search(gitee_pattern, repo_url):
            match = re.search(gitee_pattern, repo_url)
            platform = "gitee"
        else:
            raise ValueError(f"不支持的Git平台: {repo_url}")
        
        owner = match.group(1)
        repo_name = match.group(2)
        # 移除.git后缀
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]
            
        return {
            "platform": platform,
            "owner": owner,
            "repo_name": repo_name
        }
    
    def _get_auth_token(self, platform: str) -> Optional[str]:
        """从配置中获取认证令牌
        
        Args:
            platform: Git平台名称
            
        Returns:
            认证令牌或None
        """
        if not self.config or 'git' not in self.config:
            return None
        
        git_config = self.config['git']
        if platform not in git_config:
            return None
            
        return git_config[platform].get('token')
    
    def detect_browser_context(self, platform: str) -> str:
        """当需要人工登录时，触发浏览器实例提示用户授权
        
        Args:
            platform: Git平台名称
            
        Returns:
            用户输入的临时令牌
        """
        import webbrowser
        
        auth_urls = {
            "github": "https://github.com/login/oauth/authorize?client_id=YOUR_CLIENT_ID&scope=repo",
            "gitlab": "https://gitlab.com/-/profile/personal_access_tokens",
            "gitee": "https://gitee.com/oauth/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost&response_type=code"
        }
        
        if platform in auth_urls:
            webbrowser.open(auth_urls[platform])
            return input(f"请在浏览器完成{platform}授权后粘贴临时令牌：")
        else:
            return input(f"请提供{platform}的访问令牌：")
    
    def clone_repo(self, repo_url: str, token: Optional[str] = None) -> str:
        """克隆Git仓库到临时目录
        
        Args:
            repo_url: 仓库URL
            token: 认证令牌，如果为None则尝试从配置获取
            
        Returns:
            临时目录路径
        """
        # 创建临时目录
        temp_dir = tempfile.mkdtemp(prefix="git_scan_")
        self.temp_dirs.append(temp_dir)
        
        # 获取平台信息
        platform_info = self._get_platform_info(repo_url)
        platform = platform_info["platform"]
        
        # 获取认证令牌
        if not token:
            token = self._get_auth_token(platform)
            
            # 如果配置中没有令牌，则尝试通过浏览器获取
            if not token:
                token = self.detect_browser_context(platform)
        
        # 构建带认证的URL
        auth_url = repo_url
        if token and platform == "github":
            auth_url = repo_url.replace("https://", f"https://{token}@")
        elif token and platform == "gitlab":
            auth_url = repo_url.replace("https://", f"https://oauth2:{token}@")
        elif token and platform == "gitee":
            auth_url = repo_url.replace("https://", f"https://{token}@")
        
        try:
            logger.info(f"克隆仓库: {repo_url} 到 {temp_dir}")
            repo = Repo.clone_from(auth_url, temp_dir)
            return temp_dir
        except git.GitCommandError as e:
            # 清理临时目录
            if temp_dir in self.temp_dirs:
                self.temp_dirs.remove(temp_dir)
                shutil.rmtree(temp_dir, ignore_errors=True)
            
            # 尝试通过API获取
            if token:
                try:
                    return self._download_via_api(platform_info, token, temp_dir)
                except Exception as api_error:
                    logger.error(f"通过API下载失败: {str(api_error)}")
                    
            raise ValueError(f"仓库克隆失败: {str(e)}")
    
    def _download_via_api(self, platform_info: Dict, token: str, temp_dir: str) -> str:
        """通过API下载仓库内容
        
        Args:
            platform_info: 平台信息
            token: 认证令牌
            temp_dir: 临时目录
            
        Returns:
            临时目录路径
        """
        platform = platform_info["platform"]
        owner = platform_info["owner"]
        repo_name = platform_info["repo_name"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        if platform == "github":
            api_url = f"https://api.github.com/repos/{owner}/{repo_name}"
            # 使用GitHub API获取默认分支
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
            repo_data = response.json()
            default_branch = repo_data.get("default_branch", "master")
            
            # 下载ZIP归档
            zip_url = f"{api_url}/zipball/{default_branch}"
            self._download_and_extract(zip_url, headers, temp_dir)
            
        elif platform == "gitlab":
            api_url = f"https://gitlab.com/api/v4/projects/{owner}%2F{repo_name}"
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
            repo_data = response.json()
            project_id = repo_data["id"]
            
            # 下载仓库归档
            zip_url = f"https://gitlab.com/api/v4/projects/{project_id}/repository/archive.zip"
            self._download_and_extract(zip_url, headers, temp_dir)
            
        elif platform == "gitee":
            api_url = f"https://gitee.com/api/v5/repos/{owner}/{repo_name}"
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
            
            # 下载ZIP归档
            zip_url = f"{api_url}/archive/master.zip"
            self._download_and_extract(zip_url, headers, temp_dir)
        
        return temp_dir
    
    def _download_and_extract(self, zip_url: str, headers: Dict, temp_dir: str):
        """下载并解压ZIP文件
        
        Args:
            zip_url: ZIP文件URL
            headers: 请求头
            temp_dir: 目标目录
        """
        import zipfile
        import io
        
        response = requests.get(zip_url, headers=headers, stream=True)
        response.raise_for_status()
        
        # 保存到临时文件
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
            temp_file_path = temp_file.name
        
        # 解压到临时目录
        with zipfile.ZipFile(temp_file_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # 删除临时ZIP文件
        os.unlink(temp_file_path)
    
    def find_java_files(self, path: str) -> List[str]:
        """查找目录下的所有Java文件
        
        Args:
            path: 目录路径
            
        Returns:
            Java文件路径列表
        """
        java_files = []
        
        for root, _, files in os.walk(path):
            for file in files:
                if file.endswith('.java'):
                    java_files.append(os.path.join(root, file))
        
        return java_files
    
    def read_file_content(self, file_path: str) -> str:
        """读取文件内容
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件内容
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            encodings = ['latin-1', 'gbk', 'iso-8859-1']
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
            
            # 如果所有编码都失败，使用二进制模式读取
            with open(file_path, 'rb') as f:
                content = f.read()
                return content.decode('utf-8', errors='replace')
    
    def get_file_last_commit(self, repo_path: str, file_path: str) -> Dict:
        """获取文件最后一次提交信息
        
        Args:
            repo_path: 仓库路径
            file_path: 文件路径
            
        Returns:
            包含提交信息的字典
        """
        try:
            repo = Repo(repo_path)
            relative_path = os.path.relpath(file_path, repo_path)
            
            # 获取文件的最后一次提交
            commits = list(repo.iter_commits(paths=relative_path, max_count=1))
            
            if commits:
                commit = commits[0]
                return {
                    "hash": commit.hexsha,
                    "author": commit.author.name,
                    "email": commit.author.email,
                    "date": commit.authored_datetime.isoformat(),
                    "message": commit.message.strip()
                }
            else:
                return {}
        except Exception as e:
            logger.error(f"获取文件提交信息失败: {str(e)}")
            return {} 