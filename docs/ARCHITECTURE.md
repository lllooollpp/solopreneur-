# solopreneur 架构设计文档

## 产品定位

solopreneur 的目标不是做“通用聊天机器人”，而是做一个服务**一人软件公司**的 AI 执行平台：

- 面向个人开发者/小团队，从需求分析到开发、测试、部署、文档产出的一体化执行。
- 以项目为中心（Project-Centric），通过项目上下文、项目环境变量、工具调用实现真实代码交付。
- 以可配置为核心（Config-Driven），支持多模型、多入口、多角色协作，并可私有化运行。

## 1. 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户交互层                                │
├─────────────┬─────────────┬─────────────┬─────────────────────┤
│   CLI       │   Web UI    │  Chat API   │   Channel Adapters  │
│  (命令行)    │  (前端界面)  │  (REST/WS)  │ (WhatsApp/Telegram) │
└──────┬──────┴──────┬──────┴──────┬──────┴──────────┬──────────┘
       │             │             │                 │
       └─────────────┴──────┬──────┴─────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────┐
│                      Agent 核心层                              │
├───────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  │ Agent Loop  │  │   Context   │  │    Compaction       │   │
│  │ (执行循环)   │  │  (上下文)    │  │   (三层压缩)         │   │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘   │
│         │                │                    │               │
│         └────────────────▼────────────────────┘               │
│                          │                                     │
│  ┌───────────────────────▼───────────────────────────────┐   │
│  │                    Tool Registry                       │   │
│  │  (工具注册表: filesystem, shell, web, delegate...)     │   │
│  └───────────────────────────────────────────────────────┘   │
└───────────────────────────┬───────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────┐
│                      业务逻辑层                                │
├─────────────┬─────────────┬─────────────┬───────────────────┤
│  Project    │   Skills    │   Agents    │     Workflow      │
│  (项目管理)  │  (技能系统)  │ (Agent定义) │    (工作流引擎)    │
└──────┬──────┴──────┬──────┴──────┬──────┴─────────┬─────────┘
       │             │             │                │
       │             │             │                │
┌──────▼─────────────▼─────────────▼────────────────▼─────────┐
│                      存储层                                   │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   SQLite    │  │   Memory    │  │   File Storage      │ │
│  │ (项目/凭证)  │  │  (记忆系统)  │  │   (工作区文件)       │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────┐
│                    LLM Provider 层                            │
├───────────┬───────────┬───────────┬───────────┬─────────────┤
│ Anthropic │  OpenAI   │ Gemini    │   Zhipu   │   Copilot   │
│           │ OpenRouter│           │ (智谱)    │  (Token池)  │
└───────────┴───────────┴───────────┴───────────┴─────────────┘
```

## 2. 核心模块

### 2.1 Agent Loop (`solopreneur/agent/core/loop.py`)

Agent 执行的核心循环：

```python
async def run():
    while iterations < max_iterations:
        # 1. 构建上下文
        messages = context_builder.build_messages(history, message)
        
        # 2. 调用 LLM
        response = await llm_client.chat(messages, tools)
        
        # 3. 处理响应
        if response.tool_calls:
            for tool_call in response.tool_calls:
                result = await execute_tool(tool_call)
                messages.append(tool_result)
        else:
            return response.content
        
        # 4. 上下文压缩（如果超过阈值）
        if token_count > max_tokens_per_session:
            messages = compaction.compress(messages)
```

**关键特性**：
- 最大 20 次工具迭代
- 30 分钟超时控制
- 50 万 token/session 限制
- 三层上下文压缩

### 2.2 Context Builder (`solopreneur/agent/core/context.py`)

构建 Agent 系统提示：

```
System Prompt 结构：
├── 核心身份（Identity）
├── 当前项目上下文（Project Context）
│   ├── 项目基本信息
│   └── 项目环境变量（env_vars）← 新增
├── Bootstrap 文件（AGENTS.md, SOUL.md, USER.md）
├── 记忆上下文（Memory）
├── Skills 摘要
└── Agent 团队信息
```

### 2.3 Tool Registry (`solopreneur/agent/core/tools/`)

工具注册机制：

```python
class ToolRegistry:
    def register(self, tool: Tool):
        self._tools[tool.name] = tool
        
    def get_schemas(self) -> list[dict]:
        # 返回 OpenAI 工具调用格式
        return [tool.schema for tool in self._tools.values()]
```

**工具列表**：

| 工具 | 文件 | 功能 |
|------|------|------|
| `read_file` | filesystem.py | 读取文件 |
| `write_file` | filesystem.py | 写入文件 |
| `edit_file` | filesystem.py | 编辑文件 |
| `list_dir` | filesystem.py | 目录列表 |
| `exec` | shell.py | Shell 命令 |
| `web_search` | web.py | 网页搜索 |
| `web_fetch` | web.py | 获取网页 |
| `delegate` | delegate.py | Agent 委派 |
| `get_project_env` | project_env.py | 获取项目环境变量 |
| `set_project_env` | project_env.py | 设置项目环境变量 |

### 2.4 Project Manager (`solopreneur/projects/manager.py`)

项目与配置管理：

```python
class ProjectManager:
    def create_project(self, data: ProjectCreate) -> Project
    def get_project(self, project_id: str) -> Project
    def set_project_env_vars(self, project_id: str, env_vars: list)
    def get_project_env_vars(self, project_id: str) -> list
```

**数据模型**：

```python
class Project(BaseModel):
    id: str
    name: str
    path: str
    env_vars: list[ProjectEnvVar]  # 项目环境变量
    git_info: GitInfo | None
    session_id: str
    status: ProjectStatus
```

## 3. 项目环境变量系统

### 3.1 数据流

```
┌─────────────────┐
│  配置来源        │
├─────────────────┤
│ 1. 创建时传入    │
│ 2. API 更新     │
│ 3. Skill 提取   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Project.env_vars│
│   (SQLite)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Context Builder │
│ (注入 System    │
│  Prompt)        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    AI Agent     │
│  (自动感知配置)  │
└─────────────────┘
```

### 3.2 分类体系

```python
class ProjectEnvCategory(str, Enum):
    DATABASE = "database"      # MySQL, PostgreSQL, MongoDB...
    REGISTRY = "registry"      # NPM, Maven, Docker...
    SERVER = "server"          # API 网关, 微服务...
    MIDDLEWARE = "middleware"  # Redis, MQ, Nacos...
    CREDENTIAL = "credential"  # 密码, Token, 密钥
    GENERAL = "general"        # 其他
```

### 3.3 敏感信息处理

```python
class ProjectEnvVar(BaseModel):
    key: str
    value: str
    sensitive: bool = False  # 标记敏感
    
# Context 注入时自动脱敏
if var.sensitive:
    display_value = "******"
```

## 4. Skills 技能系统

### 4.1 目录结构

```
solopreneur/skills/
├── config-extract/
│   └── SKILL.md      # 配置提取技能
├── devops/
│   └── SKILL.md      # DevOps 技能
├── testing/
│   └── SKILL.md      # 测试技能
└── ...
```

### 4.2 SKILL.md 格式

```markdown
---
name: config-extract
description: "从已有项目配置中提取环境信息"
metadata: {"solopreneur":{"emoji":"🔍","always":false}}
---

# 配置提取技能

## 目标
1. 扫描项目中的配置文件
2. 提取可结构化的环境变量
3. 调用 set_project_env 工具写回
```

### 4.3 加载机制

```python
class SkillsLoader:
    def get_always_skills(self) -> list[str]:
        # 返回 always=true 的技能
        
    def build_skills_summary(self) -> str:
        # 构建摘要 XML
```

## 5. Agent 定义系统

### 5.1 预设 Agent

```
solopreneur/agent/definitions/presets/
├── software/
│   ├── product_manager.yaml
│   ├── architect.yaml
│   ├── developer.yaml
│   ├── code_reviewer.yaml
│   ├── tester.yaml
│   └── devops.yaml
├── medical/
│   ├── pediatrician.yaml
│   └── nutritionist.yaml
└── legal/
    └── legal_advisor.yaml
```

### 5.2 Agent 定义格式

```yaml
name: developer
title: 开发工程师
emoji: 💻
description: 负责代码编写和功能实现
tools:
  - read_file
  - write_file
  - edit_file
  - exec
  - get_project_env  # 可访问项目环境变量
  - set_project_env
system_prompt: |
  你是一位经验丰富的开发工程师...
```

## 6. 存储层

### 6.1 SQLite 表结构

```sql
-- 项目表
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT,
    path TEXT,
    env_vars TEXT,  -- JSON 存储
    session_id TEXT,
    status TEXT,
    created_at TEXT,
    updated_at TEXT
);

-- Git 凭证表
CREATE TABLE git_credentials (
    project_id TEXT PRIMARY KEY,
    username TEXT,
    token TEXT
);
```

### 6.2 文件存储

```
~/.solopreneur/
├── config.json        # 全局配置
├── solopreneur.db         # SQLite 数据库
└── workspace/
    ├── AGENTS.md
    ├── SOUL.md
    ├── USER.md
    ├── memory/
    │   ├── MEMORY.md
    │   └── YYYY-MM-DD.md
    └── skills/
        └── custom-skill/
            └── SKILL.md
```

## 7. API 层

### 7.1 项目管理 API

```
GET    /api/projects              # 列出项目
POST   /api/projects              # 创建项目
GET    /api/projects/{id}         # 获取项目
PUT    /api/projects/{id}         # 更新项目
DELETE /api/projects/{id}         # 删除项目
GET    /api/projects/{id}/env     # 获取环境变量
PUT    /api/projects/{id}/env     # 更新环境变量
```

### 7.2 WebSocket 事件

```json
// chunk 事件
{"type": "chunk", "content": "文本片段"}

// trace 事件
{"type": "trace", "event": "tool_start", "tool": "read_file"}

// done 事件
{"type": "done", "tokens": {"input": 1000, "output": 500}}
```

## 8. 安全考虑

1. **敏感信息**：
   - `sensitive=true` 的变量在日志、API 响应中脱敏
   - Git Token 单独存储在 `git_credentials` 表

2. **权限控制**：
   - Shell 命令可限制在 workspace 内
   - 文件操作路径验证

3. **超时控制**：
   - Agent 总超时 30 分钟
   - Shell 命令默认 60 秒超时

---

*更多信息请参考：*
- [SKILLS_AND_CONFIG.md](SKILLS_AND_CONFIG.md) - 技能与配置指南
- [SUBAGENT_SYSTEM.md](SUBAGENT_SYSTEM.md) - 子 Agent 系统
- [effc.md](effc.md) - Feature 驱动工作流
- [AGENT_CATALOG.md](AGENT_CATALOG.md) - Agent 目录与映射
- [SKILL_CATALOG.md](SKILL_CATALOG.md) - Skill 目录与映射
- [index.md](index.md) - 文档总索引
