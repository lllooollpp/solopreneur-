# 技能加载与 Agent 配置指南

本文档介绍 solopreneur 如何加载工具（Tools）与技能（Skills），以及用户如何配置 Agent 的人格与行为。

## 1. 能力加载机制

solopreneur 的设计理念是"按需加载"，以节省 Token 消耗并保持 Agent 的专注度。

### 1.1 工具 (Tools)
- **定义**: 位于 `solopreneur/agent/tools/`，是用 Python 编写的硬编码函数。
- **加载策略**: 全量注册元数据。Agent 在启动时知道所有工具的存在，但只有在 LLM 明确发出指令时才执行具体的 Python 代码。

### 1.2 技能 (Skills)
- **定义**: 位于 `solopreneur/skills/` 或工作空间的 `skills/` 目录，是以 `SKILL.md` 命名的 Markdown 文件。
- **分级加载**:
    1. **摘要 (Summary)**: 系统会自动提取所有技能的描述生成一份 XML 摘要注入到 Prompt 中。
    2. **静态加载 (`always: true`)**: 在 `SKILL.md` 头部设置此属性的技能，其全文会随 Agent 启动直接加载。
    3. **动态加载**: Agent 在阅读摘要后，若发现任务需要某项技能，会主动调用 `read_file` 工具读取该技能的详细说明。

## 2. Agent 配置方式

solopreneur 的配置主要基于工作空间（Workspace）中的 Markdown 文件，这使得配置逻辑对人类非常友好。

### 2.1 人格设定 (`SOUL.md`)
- **路径**: `workspace/SOUL.md`
- **说明**: 这是 Agent 的核心指令集。你可以在这里定义：
    - **身份**: "你是一个资深的 Python 开发者。"
    - **性格**: "回答问题简洁有力，带一点幽默。"
    - **规则**: "严禁修改根目录下的配置文件。"

### 2.2 角色定义 (`AGENTS.md`)
- **路径**: `workspace/AGENTS.md`
- **说明**: 用于定义 Agent 能够切换或派生的各种专家角色。

### 2.3 自定义技能
你可以通过以下步骤添加新技能：
1. 在 `workspace/skills/` 下创建一个目录（如 `my-tool/`）。
2. 创建 `SKILL.md` 并编写其功能描述及操作指南。
3. Agent 在下次启动或刷新时将自动识别该技能。

## 3. 系统级配置 (`config.json`)

系统参数控制着 solopreneur 的运行环境：
- **模型选择**: 在 `provider` 字段设置使用的 LLM 模型（如 `gpt-4o`, `claude-3-5-sonnet`）。
- **凭证管理**: 存储 API Key、Telegram Token 等敏感信息。
- **环境要求**: 技能可以通过 `requires` 字段声明其运行所需的二进制文件（如 `bins: ["git"]`）或环境变量。

## 4. 项目环境变量

每个项目可以配置专属的环境变量，AI 在执行任务时会自动感知这些配置。

### 4.1 变量模型

```python
class ProjectEnvVar(BaseModel):
    key: str          # 变量名，如 DB_HOST
    value: str        # 变量值
    category: str     # 分类: database, registry, server, middleware, credential, general
    description: str  # 说明
    sensitive: bool   # 是否敏感信息
```

### 4.2 变量分类

| 分类 | 说明 | 示例 |
|------|------|------|
| `database` | 数据库连接信息 | DB_HOST, DB_PORT, DATABASE_URL |
| `registry` | 私服/镜像源地址 | NEXUS_URL, NPM_REGISTRY, MAVEN_REPO |
| `server` | 业务服务地址 | API_BASE, GATEWAY_URL |
| `middleware` | 中间件 | REDIS_URL, RABBITMQ_HOST, NACOS_SERVER |
| `credential` | 敏感凭证 | DB_PASSWORD, API_SECRET, JWT_KEY |
| `general` | 通用配置 | APP_ENV, LOG_LEVEL |

### 4.3 配置方式

**方式一：创建项目时传入**
```json
POST /api/projects
{
  "name": "我的项目",
  "local_path": "/path/to/project",
  "env_vars": [
    {"key": "DB_HOST", "value": "192.168.1.100", "category": "database"},
    {"key": "NEXUS_URL", "value": "https://nexus.company.com", "category": "registry"}
  ]
}
```

**方式二：使用工具更新**
```
set_project_env(env_vars=[
  {"key": "REDIS_URL", "value": "redis://localhost:6379", "category": "middleware"}
])
```

**方式三：使用 config-extract Skill 自动提取**
```
请使用 config-extract 技能从当前项目提取配置
```

## 5. 内置技能列表

| 技能 | 说明 | 触发场景 |
|------|------|---------|
| `config-extract` | 从项目配置文件提取环境变量 | 用户要求"提取配置"、"扫描环境变量" |
| `devops` | CI/CD、Docker、部署脚本 | 用户要求"创建流水线"、"编写 Dockerfile" |
| `testing` | 测试策略、自动化测试 | 用户要求"写测试"、"测试覆盖" |
| `code-review` | 代码审查最佳实践 | 用户要求"审查代码"、"代码评审" |
| `security` | 安全审计、漏洞检测 | 用户要求"安全检查"、"漏洞扫描" |
| `architecture` | 架构设计模式 | 用户要求"设计架构"、"技术选型" |

## 6. config-extract 技能详解

`config-extract` 是一个特殊的技能，用于从现有项目中自动提取环境配置。

### 6.1 支持的配置文件

| 类型 | 文件 |
|------|------|
| 环境变量 | `.env`, `.env.local`, `.env.development`, `.env.production` |
| Spring Boot | `application.yml`, `application.properties`, `bootstrap.yml` |
| Python | `settings.py`, `config.py`, `pyproject.toml` |
| Node.js | `.env`, `package.json` (scripts), `nuxt.config.js` |
| Docker | `docker-compose.yml`, `Dockerfile` (ENV 指令) |
| Kubernetes | `ConfigMap`, `Secret`, `values.yaml` |

### 6.2 提取规则

1. **数据库相关** → `database` 分类
   - `spring.datasource.*`
   - `DATABASE_URL`, `DB_HOST`, `DB_PORT`
   - `MONGO_URI`, `POSTGRES_*`

2. **私服/镜像源** → `registry` 分类
   - `NPM_REGISTRY`, `MAVEN_REPO`
   - `DOCKER_REGISTRY`, `NEXUS_URL`

3. **业务服务** → `server` 分类
   - `API_BASE_URL`, `GATEWAY_URL`
   - `SERVER_HOST`, `BACKEND_URL`

4. **中间件** → `middleware` 分类
   - `REDIS_URL`, `RABBITMQ_*`
   - `NACOS_*`, `CONSUL_*`, `ELASTICSEARCH_*`

5. **密码/密钥** → `credential` 分类（自动标记 `sensitive: true`）
   - 包含 `password`, `secret`, `token`, `key` 的变量

### 6.3 使用示例

```
用户: 帮我从这个项目提取配置信息

AI: 我将使用 config-extract 技能扫描项目配置文件...
    [调用 list_dir 和 read_file 扫描配置文件]
    [解析并分类环境变量]
    [调用 set_project_env 写入项目配置]
    
    已从项目提取以下配置：
    | 分类 | 变量 | 值 |
    |------|------|-----|
    | database | DB_HOST | 192.168.1.100 |
    | database | DB_PORT | 3306 |
    | registry | NEXUS_URL | https://nexus.company.com |
    | credential | DB_PASSWORD | ****** (sensitive) |
    
    共提取 4 项配置，已写入项目环境变量。
```

---

*更多详情请参考：*
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [SUBAGENT_SYSTEM.md](SUBAGENT_SYSTEM.md)
- [AGENT_CATALOG.md](AGENT_CATALOG.md)
- [SKILL_CATALOG.md](SKILL_CATALOG.md)
- [index.md](index.md)
