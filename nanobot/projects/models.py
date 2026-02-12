"""
项目数据模型
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ProjectSource(str, Enum):
    """项目来源类型"""
    LOCAL = "local"           # 本地项目
    GITHUB = "github"         # GitHub 仓库
    GITLAB = "gitlab"         # GitLab 仓库
    GIT = "git"               # 其他 Git 仓库


class ProjectStatus(str, Enum):
    """项目状态"""
    ACTIVE = "active"         # 活跃
    ARCHIVED = "archived"     # 已归档
    ERROR = "error"           # 错误状态


class GitInfo(BaseModel):
    """Git 仓库信息"""
    url: str = Field(..., description="Git 仓库 URL（已脱敏，不包含 token）")
    original_url: Optional[str] = Field(default=None, description="原始 URL（包含 token，仅内部使用）")
    branch: str = Field(default="main", description="分支名称")
    last_commit: Optional[str] = Field(default=None, description="最后提交 SHA")
    last_sync: Optional[datetime] = Field(default=None, description="最后同步时间")
    # 认证信息（可选）
    username: Optional[str] = Field(default=None, description="Git 用户名")
    # 代理配置（可选）
    use_proxy: bool = Field(default=False, description="是否使用代理")
    proxy_url: Optional[str] = Field(default=None, description="代理地址，如 http://127.0.0.1:7890")
    # 注意: token 保存在独立位置，不直接存储在此模型中


class Project(BaseModel):
    """
    项目模型
    
    每个项目对应一个工作目录和独立的会话存储
    """
    id: str = Field(..., description="项目唯一ID")
    name: str = Field(..., min_length=1, max_length=100, description="项目名称")
    description: Optional[str] = Field(default=None, max_length=500, description="项目描述")
    source: ProjectSource = Field(default=ProjectSource.LOCAL, description="项目来源")
    
    # 路径信息
    path: str = Field(..., description="项目本地路径（绝对路径）")
    
    # Git 信息（如果是从仓库克隆的）
    git_info: Optional[GitInfo] = Field(default=None, description="Git 仓库信息")
    
    # 会话关联
    session_id: str = Field(..., description="关联的聊天会话ID")
    
    # 状态
    status: ProjectStatus = Field(default=ProjectStatus.ACTIVE)
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    @field_validator('path')
    @classmethod
    def validate_path(cls, v: str) -> str:
        """验证路径"""
        path = Path(v)
        if not path.is_absolute():
            raise ValueError("项目路径必须是绝对路径")
        return str(path.resolve())
    
    def to_dict(self) -> dict:
        """转换为字典（用于JSON序列化）"""
        # 手动处理 git_info 中的 datetime 字段
        git_info_dict = None
        if self.git_info:
            git_info_dict = {
                "url": self.git_info.url,
                "original_url": self.git_info.original_url,
                "branch": self.git_info.branch,
                "last_commit": self.git_info.last_commit,
                "last_sync": self.git_info.last_sync.isoformat() if self.git_info.last_sync else None,
                "username": self.git_info.username,
                "use_proxy": self.git_info.use_proxy,
                "proxy_url": self.git_info.proxy_url,
            }
        
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "source": self.source.value,
            "path": self.path,
            "git_info": git_info_dict,
            "session_id": self.session_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        """从字典创建实例"""
        git_info = None
        if data.get("git_info"):
            git_info = GitInfo(**data["git_info"])
        
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            source=ProjectSource(data.get("source", "local")),
            path=data["path"],
            git_info=git_info,
            session_id=data["session_id"],
            status=ProjectStatus(data.get("status", "active")),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


class ProjectCreate(BaseModel):
    """创建项目请求"""
    name: str = Field(..., min_length=1, max_length=100, description="项目名称")
    description: Optional[str] = Field(default=None, max_length=500)
    source: ProjectSource = Field(default=ProjectSource.LOCAL)
    
    # 本地项目
    local_path: Optional[str] = Field(default=None, description="本地项目路径")
    
    # Git 项目
    git_url: Optional[str] = Field(default=None, description="Git 仓库 URL")
    git_branch: str = Field(default="main", description="Git 分支")
    
    # Git 认证（可选）
    git_username: Optional[str] = Field(default=None, description="Git 用户名（可选）")
    git_token: Optional[str] = Field(default=None, description="Git Token/密码（可选，会安全存储）")
    
    # Git 代理（可选）
    use_proxy: bool = Field(default=False, description="是否使用代理")
    proxy_url: Optional[str] = Field(default=None, description="代理地址，如 http://127.0.0.1:7890")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """验证项目名称"""
        v = v.strip()
        if not v:
            raise ValueError("项目名称不能为空")
        # 检查非法字符
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            if char in v:
                raise ValueError(f"项目名称不能包含字符: {char}")
        return v


class ProjectUpdate(BaseModel):
    """更新项目请求"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    status: Optional[ProjectStatus] = None
