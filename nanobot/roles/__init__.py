"""软件工程角色系统。

提供产品经理、架构师、开发工程师、代码审查员、测试工程师、DevOps 工程师等角色定义，
支持通过 delegate 工具将任务委派给特定角色执行。
"""

from nanobot.roles.definitions import Role, ROLES, get_role, list_roles
from nanobot.roles.manager import RoleManager

__all__ = ["Role", "ROLES", "get_role", "list_roles", "RoleManager"]
