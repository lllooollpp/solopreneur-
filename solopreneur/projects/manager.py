"""项目管理器：项目与凭证均使用 SQLite 持久化。"""

import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse, urlunparse
from loguru import logger

from solopreneur.storage import GitCredentialPersistence, ProjectPersistence
from .models import Project, ProjectCreate, ProjectUpdate, ProjectSource, ProjectStatus, GitInfo, ProjectEnvVar


class ProjectManager:
    """
    项目管理器
    
    管理项目配置存储在 SQLite
    项目代码存储在各自指定的 path 中
    Git 凭证存储在 SQLite git_credentials 表
    """
    
    def __init__(self, data_dir: Optional[Path] = None):
        """
        初始化项目管理器
        
        Args:
            data_dir: 数据存储目录，默认为 ~/.solopreneur
        """
        if data_dir is None:
            data_dir = Path.home() / ".solopreneur"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.storage = ProjectPersistence(db_path=self.data_dir / "solopreneur.db")
        self.credential_store = GitCredentialPersistence(db_path=self.data_dir / "solopreneur.db")
        self._projects: dict[str, Project] = {}
        self._load_projects()
    
    def _load_projects(self):
        """从 SQLite 加载项目列表。"""
        self._projects = {}

        # 优先从 SQLite 加载
        try:
            rows = self.storage.load_all()
            for item in rows:
                try:
                    project = Project.from_dict(item)
                    self._projects[project.id] = project
                except Exception as e:
                    logger.warning(f"Failed to load project from SQLite: {e}")
        except Exception as e:
            logger.error(f"Failed to load projects from SQLite: {e}")

        if not self._projects:
            # 创建默认项目
            self._create_default_project()
        else:
            logger.info(f"Loaded {len(self._projects)} projects")
    
    def _save_projects(self):
        """保存项目列表到 SQLite。"""
        try:
            for project in self._projects.values():
                self.storage.save(project.to_dict())
        except Exception as e:
            logger.error(f"Failed to save projects to SQLite: {e}")
            raise
    
    def _create_default_project(self):
        """创建默认项目"""
        default_workspace = self.data_dir / "workspace"
        default_workspace.mkdir(parents=True, exist_ok=True)
        
        project = Project(
            id="default",
            name="默认项目",
            description="系统默认项目，用于一般性对话",
            source=ProjectSource.LOCAL,
            path=str(default_workspace),
            session_id="default",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        self._projects[project.id] = project
        self._save_projects()
        logger.info("Created default project")
    
    def _generate_id(self) -> str:
        """生成唯一项目ID"""
        return f"proj_{uuid.uuid4().hex[:8]}"
    
    def _generate_session_id(self) -> str:
        """生成会话ID"""
        return f"session_{uuid.uuid4().hex[:8]}"
    
    # ==================== Git 凭证管理 ====================
    
    def _save_git_credentials(self, project_id: str, username: Optional[str], token: Optional[str]):
        """保存 Git 凭证到 SQLite。"""
        try:
            if username or token:
                self.credential_store.set(project_id, username, token)
            else:
                self.credential_store.delete(project_id)
        except Exception as e:
            logger.error(f"Failed to save git credentials: {e}")
    
    def _get_git_credentials(self, project_id: str) -> tuple[Optional[str], Optional[str]]:
        """
        获取 Git 凭证
        
        Returns:
            (username, token) 元组
        """
        try:
            return self.credential_store.get(project_id)
        except Exception as e:
            logger.error(f"Failed to get git credentials: {e}")
            return None, None
    
    def _build_authenticated_url(self, url: str, username: Optional[str], token: Optional[str]) -> str:
        """
        构建带认证信息的 Git URL
        
        将 https://github.com/user/repo.git
        转换为 https://username:token@github.com/user/repo.git
        """
        if not token:
            return url
        
        try:
            parsed = urlparse(url)
            if parsed.scheme in ('http', 'https'):
                # 构建新的 netloc
                auth_part = f"{username or 'token'}:{token}@"
                new_netloc = auth_part + parsed.netloc
                
                # 重新组装 URL
                authenticated_url = urlunparse((
                    parsed.scheme,
                    new_netloc,
                    parsed.path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment
                ))
                return authenticated_url
        except Exception as e:
            logger.warning(f"Failed to build authenticated URL: {e}")
        
        return url
    
    def _mask_url(self, url: str) -> str:
        """
        脱敏 URL，移除认证信息
        
        https://username:token@github.com/repo -> https://github.com/repo
        """
        try:
            parsed = urlparse(url)
            if parsed.username or parsed.password:
                return urlunparse((
                    parsed.scheme,
                    parsed.netloc.split('@')[-1],  # 移除认证部分
                    parsed.path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment
                ))
        except Exception:
            pass
        return url

    # ==================== CRUD 操作 ====================
    
    def list_projects(self) -> List[Project]:
        """获取所有项目列表"""
        return sorted(self._projects.values(), key=lambda p: p.created_at, reverse=True)
    
    def get_project(self, project_id: str) -> Optional[Project]:
        """获取指定项目"""
        return self._projects.get(project_id)

    def get_project_by_path(self, project_path: str | Path) -> Optional[Project]:
        """按路径获取项目（用于基于工作目录的上下文工具）。"""
        try:
            target = Path(project_path).expanduser().resolve()
        except Exception:
            return None

        for project in self._projects.values():
            try:
                p = Path(project.path).expanduser().resolve()
                if p == target:
                    return project
            except Exception:
                continue
        return None
    
    def create_project(self, data: ProjectCreate) -> Project:
        """
        创建新项目
        
        Args:
            data: 项目创建数据
            
        Returns:
            创建的项目对象
            
        Raises:
            ValueError: 参数验证失败
            RuntimeError: Git 操作失败
        """
        project_id = self._generate_id()
        session_id = self._generate_session_id()
        
        # 确定项目路径
        if data.source == ProjectSource.LOCAL:
            if not data.local_path:
                raise ValueError("本地项目必须提供路径")
            project_path = Path(data.local_path).resolve()
            project_path.mkdir(parents=True, exist_ok=True)
            git_info = None
            
        else:
            # Git 项目，需要克隆
            if not data.git_url:
                raise ValueError("Git 项目必须提供仓库 URL")
            
            # 在项目目录下创建子目录
            projects_dir = self.data_dir / "projects"
            projects_dir.mkdir(parents=True, exist_ok=True)
            project_path = projects_dir / project_id
            
            # 保存 Git 凭证
            if data.git_token:
                self._save_git_credentials(project_id, data.git_username, data.git_token)
            
            # 构建带认证的 URL
            auth_url = self._build_authenticated_url(
                data.git_url, 
                data.git_username, 
                data.git_token
            )
            
            # 克隆仓库（带代理）
            proxy = data.proxy_url if data.use_proxy else None
            self._clone_repository(auth_url, data.git_branch, project_path, proxy)
            
            # 保存脱敏后的 URL
            masked_url = self._mask_url(data.git_url)
            
            git_info = GitInfo(
                url=masked_url,
                original_url=data.git_url if data.git_token else None,
                branch=data.git_branch,
                last_sync=datetime.now(),
                username=data.git_username,
                use_proxy=data.use_proxy,
                proxy_url=data.proxy_url if data.use_proxy else None
            )
        
        project = Project(
            id=project_id,
            name=data.name,
            description=data.description,
            source=data.source,
            path=str(project_path),
            git_info=git_info,
            session_id=session_id,
            env_vars=data.env_vars,
            status=ProjectStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        
        self._projects[project_id] = project
        self._save_projects()
        
        logger.info(f"Created project: {project.name} ({project.id})")
        return project
    
    def update_project(self, project_id: str, data: ProjectUpdate) -> Optional[Project]:
        """
        更新项目
        
        Args:
            project_id: 项目ID
            data: 更新数据
            
        Returns:
            更新后的项目对象，如果不存在返回 None
        """
        project = self._projects.get(project_id)
        if not project:
            return None
        
        if data.name is not None:
            project.name = data.name
        if data.description is not None:
            project.description = data.description
        if data.status is not None:
            project.status = data.status
        if data.env_vars is not None:
            project.env_vars = data.env_vars
        
        project.updated_at = datetime.now()
        self._save_projects()
        
        logger.info(f"Updated project: {project.name} ({project.id})")
        return project

    def set_project_env_vars(self, project_id: str, env_vars: list[ProjectEnvVar]) -> Optional[Project]:
        """覆盖设置项目环境变量。"""
        project = self._projects.get(project_id)
        if not project:
            return None

        project.env_vars = env_vars
        project.updated_at = datetime.now()
        self._save_projects()
        logger.info(f"Updated env vars for project: {project.name} ({project.id}), count={len(env_vars)}")
        return project

    def get_project_env_vars(self, project_id: str) -> Optional[list[ProjectEnvVar]]:
        """获取项目环境变量列表。"""
        project = self._projects.get(project_id)
        if not project:
            return None
        return project.env_vars

    def delete_project_env_var(self, project_id: str, key: str) -> tuple[bool, Optional[Project]]:
        """
        删除项目中的单个环境变量。

        Returns:
            (是否删除成功, 项目对象或None)
        """
        project = self._projects.get(project_id)
        if not project:
            return False, None

        before = len(project.env_vars)
        project.env_vars = [item for item in project.env_vars if item.key != key]
        if len(project.env_vars) == before:
            return False, project

        project.updated_at = datetime.now()
        self._save_projects()
        logger.info(f"Deleted env var '{key}' from project: {project.name} ({project.id})")
        return True, project
    
    def delete_project(self, project_id: str, delete_files: bool = False) -> bool:
        """
        删除项目
        
        Args:
            project_id: 项目ID
            delete_files: 是否同时删除项目文件（仅对Git克隆的项目有效）
            
        Returns:
            是否成功删除
        """
        project = self._projects.get(project_id)
        if not project:
            return False
        
        # 不能删除默认项目
        if project_id == "default":
            raise ValueError("不能删除默认项目")
        
        # 删除项目文件（如果是Git克隆的且指定了删除）
        if delete_files and project.source != ProjectSource.LOCAL:
            try:
                project_path = Path(project.path)
                if project_path.exists():
                    shutil.rmtree(project_path)
                    logger.info(f"Deleted project files: {project_path}")
            except Exception as e:
                logger.error(f"Failed to delete project files: {e}")
        
        # 删除 Git 凭证
        self._save_git_credentials(project_id, None, None)
        
        del self._projects[project_id]
        self.storage.delete(project_id)
        self._save_projects()
        
        logger.info(f"Deleted project: {project.name} ({project.id})")
        return True
    
    # ==================== Git 操作 ====================
    
    def _clone_repository(self, url: str, branch: str, target_path: Path, proxy: Optional[str] = None):
        """
        克隆 Git 仓库
        
        Args:
            url: 仓库 URL（可能包含认证信息）
            branch: 分支名称
            target_path: 目标路径
            proxy: 代理地址，如 http://127.0.0.1:7890
            
        Raises:
            RuntimeError: 克隆失败
        """
        try:
            # 脱敏后的 URL 用于日志
            masked_url = self._mask_url(url)
            logger.info(f"Cloning repository: {masked_url} (branch: {branch}, proxy: {proxy or 'None'})")
            
            # 准备环境变量
            env = None
            if proxy:
                env = {
                    **dict(subprocess.os.environ),
                    "HTTP_PROXY": proxy,
                    "HTTPS_PROXY": proxy,
                    "http_proxy": proxy,
                    "https_proxy": proxy,
                }
            
            # 使用 git 命令克隆
            cmd = [
                "git", "clone",
                "--branch", branch,
                "--single-branch",
                "--depth", "1",
                url,
                str(target_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
                env=env
            )
            
            if result.returncode != 0:
                # 检查是否是认证失败
                if "Authentication failed" in result.stderr or "403" in result.stderr:
                    raise RuntimeError(f"Git 认证失败，请检查 Token/密码是否正确: {result.stderr}")
                # 检查是否是代理问题
                if "proxy" in result.stderr.lower() or "timed out" in result.stderr.lower():
                    raise RuntimeError(f"网络连接失败，请检查代理设置: {result.stderr}")
                raise RuntimeError(f"Git clone failed: {result.stderr}")
            
            logger.info(f"Successfully cloned to: {target_path}")
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("Git clone timeout (5 minutes)")
        except FileNotFoundError:
            raise RuntimeError("Git command not found. Please install Git.")
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Git clone failed: {e}")
    
    def pull_repository(self, project_id: str) -> dict:
        """
        拉取 Git 仓库更新
        
        Args:
            project_id: 项目ID
            
        Returns:
            操作结果信息
        """
        project = self._projects.get(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")
        
        if project.source == ProjectSource.LOCAL:
            raise ValueError("本地项目不支持拉取操作")
        
        if not project.git_info:
            raise ValueError("项目没有Git信息")
        
        try:
            logger.info(f"Pulling repository for project: {project.name}")
            # 确保项目目录存在（避免在不存在时意外创建或克隆）
            project_path = Path(project.path)
            if not project_path.exists():
                raise ValueError(f"Project path does not exist on disk: {project.path}")

            # 获取凭证
            username, token = self._get_git_credentials(project_id)
            
            # 构建远程 URL（带认证）
            remote_url = project.git_info.original_url or project.git_info.url
            if token:
                remote_url = self._build_authenticated_url(remote_url, username, token)
                # 临时设置远程 URL（带认证）
                subprocess.run(
                    ["git", "-C", project.path, "remote", "set-url", "origin", remote_url],
                    capture_output=True,
                    timeout=10
                )
            
            # 准备代理环境
            env = None
            if project.git_info and project.git_info.use_proxy and project.git_info.proxy_url:
                proxy = project.git_info.proxy_url
                env = {
                    **dict(subprocess.os.environ),
                    "HTTP_PROXY": proxy,
                    "HTTPS_PROXY": proxy,
                    "http_proxy": proxy,
                    "https_proxy": proxy,
                }
                logger.info(f"Using proxy for pull: {proxy}")
            
            try:
                cmd = ["git", "-C", project.path, "pull", "origin", project.git_info.branch]
                logger.debug(f"Running git pull: {cmd}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)

                if result.returncode != 0:
                    stderr = (result.stderr or '').strip()
                    logger.error(f"Git pull failed for {project_id}: {stderr}")
                    if "proxy" in stderr.lower() or "timed out" in stderr.lower():
                        raise RuntimeError(f"网络连接失败，请检查代理设置: {stderr}")
                    raise RuntimeError(f"Git pull failed: {stderr}")

                # 更新最后同步时间
                project.git_info.last_sync = datetime.now()

                # 获取最新提交
                cmd = ["git", "-C", project.path, "rev-parse", "HEAD"]
                commit_result = subprocess.run(cmd, capture_output=True, text=True)
                if commit_result.returncode == 0:
                    project.git_info.last_commit = commit_result.stdout.strip()

                project.updated_at = datetime.now()
                self._save_projects()

                logger.info(f"Successfully pulled updates for: {project.name}")
                return {
                    "success": True,
                    "message": result.stdout or "Already up to date",
                    "project_id": project_id
                }
            finally:
                # 恢复远程 URL（脱敏）
                if token:
                    subprocess.run(
                        ["git", "-C", project.path, "remote", "set-url", "origin", project.git_info.url],
                        capture_output=True,
                        timeout=10
                    )
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("Git pull timeout (2 minutes)")
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Git pull failed: {e}")
    
    def get_project_status(self, project_id: str) -> dict:
        """
        获取项目状态（包括Git状态）
        
        Args:
            project_id: 项目ID
            
        Returns:
            状态信息字典
        """
        project = self._projects.get(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")
        
        status = {
            "project_id": project_id,
            "exists": Path(project.path).exists(),
            "is_git_repo": False,
            "git_status": None,
            "uncommitted_changes": False,
            "has_credentials": False,
        }
        
        # 检查是否有凭证
        username, token = self._get_git_credentials(project_id)
        status["has_credentials"] = bool(token)
        
        # 检查 Git 状态
        if (Path(project.path) / ".git").exists():
            status["is_git_repo"] = True
            try:
                # 获取状态
                result = subprocess.run(
                    ["git", "-C", project.path, "status", "--porcelain"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    status["git_status"] = result.stdout.strip()
                    status["uncommitted_changes"] = bool(result.stdout.strip())
            except Exception as e:
                logger.warning(f"Failed to get git status: {e}")
        
        return status
