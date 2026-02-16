<div align="center">
  <img src="solopreneur_logo.png" alt="solopreneur" width="420">
  <h1>solopreneur：可配置的多领域 AI Agent 框架</h1>
  <p>
    <a href="https://pypi.org/project/solopreneur-ai/"><img src="https://img.shields.io/pypi/v/solopreneur-ai" alt="PyPI"></a>
    <a href="https://pepy.tech/project/solopreneur-ai"><img src="https://static.pepy.tech/badge/solopreneur-ai" alt="Downloads"></a>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <a href="./COMMUNICATION.md"><img src="https://img.shields.io/badge/Feishu-Group-E9DBFC?style=flat&logo=feishu&logoColor=white" alt="Feishu"></a>
    <a href="./COMMUNICATION.md"><img src="https://img.shields.io/badge/WeChat-Group-C5EAB4?style=flat&logo=wechat&logoColor=white" alt="WeChat"></a>
  </p>
</div>

🐈 **solopreneur** 是一个轻量级、可配置的多领域 AI Agent 框架。通过 YAML/JSON 配置即可定义任意领域的 Agent（软件工程、医疗、法律、教育等），支持多 LLM 提供商、多聊天渠道、工具调用和 Agent 协作。核心代码约 4,000 行，易于理解、修改和部署。

## 核心特性

- **完全可配置的 Agent 系统**：通过 YAML/JSON 定义 Agent，支持任意领域
- **Agent 循环**：支持工具调用（最多 20 次迭代）、上下文三层压缩、Token 限制和超时控制（30 分钟）
- **多 LLM 支持**：通过 LiteLLM 支持 OpenRouter、Anthropic、OpenAI、Gemini、Groq、火山引擎（智谱）、vLLM/本地模型，以及 GitHub Copilot（多账号 Token 池）
- **Provider 优先级控制**：可配置 Copilot 优先或使用其他 Provider
- **Web UI 界面**：支持项目管理、实时对话、调用链路监控、Wiki 文档生成
- **工具系统**：文件操作、Shell 执行、Web 搜索/获取、消息发送、子 Agent 衍生、Agent 委派、工作流执行
- **项目环境变量**：每个项目可配置专属环境变量（数据库、私服、中间件等），AI 自动感知使用
- **多领域预设 Agent**：软件工程、医疗、法律、通用等领域预设 Agent
- **工作流引擎**：预定义流水线（功能开发、Bug 修复等），支持自动和分步交互模式
- **聊天渠道**：WhatsApp、Telegram、企业微信（WeCom），支持白名单权限控制
- **记忆系统**：每日笔记（YYYY-MM-DD.md）+ 长期记忆（MEMORY.md）
- **定时任务**：支持 interval、cron 表达式、一次性任务，可交付到聊天渠道
- **心跳服务**：定期自动执行预设 Prompt
- **Token 统计与监控**：实时显示输入/输出 tokens、工具调用次数、调用链路时间线

## 架构

<p align="center">
  <img src="solopreneur_arch.png" alt="solopreneur architecture" width="800">
</p>

```
solopreneur/
├── agent/          # Agent 核心
│   ├── loop.py     # Agent 循环（工具调用、上下文压缩、超时控制）
│   ├── memory.py   # 记忆系统（每日笔记 + 长期记忆）
│   ├── context.py  # 上下文构建（含项目环境变量注入）
│   ├── compaction.py  # 三层上下文压缩引擎
│   ├── subagent.py    # 子 Agent 管理
│   └── tools/      # 工具实现
│       ├── filesystem.py   # read_file, write_file, edit_file, list_dir
│       ├── shell.py        # exec
│       ├── web.py          # web_search, web_fetch
│       ├── message.py      # message
│       ├── spawn.py        # spawn (子 Agent)
│       ├── delegate.py     # delegate (Agent 委派)
│       ├── project_env.py  # get_project_env, set_project_env
│       └── ...
├── projects/       # 项目管理
│   ├── models.py   # 项目模型（含环境变量定义）
│   └── manager.py  # 项目管理器
├── agents/         # 可配置 Agent 系统
│   ├── definition.py      # Agent 定义模型
│   ├── loader.py          # YAML/JSON 配置加载
│   ├── registry.py        # Agent 注册表
│   ├── manager.py         # Agent 管理器
│   └── presets/           # 预设 Agent（按领域组织）
│       ├── software/      # 软件工程领域
│       ├── medical/       # 医疗领域
│       ├── legal/         # 法律领域
│       └── general/       # 通用领域
├── skills/         # 技能系统
│   └── config-extract/    # 配置提取技能
├── providers/      # LLM 提供商
│   ├── litellm_provider.py  # LiteLLM 统一接口
│   ├── github_copilot.py    # GitHub Copilot 特殊处理
│   └── token_pool.py        # 多账号 Token 池管理
├── channels/       # 聊天渠道
│   ├── whatsapp.py   # WhatsApp (通过 Bridge)
│   ├── telegram.py   # Telegram Bot
│   └── wecom.py      # 企业微信
├── workflow/       # 工作流引擎
│   └── engine.py   # 多 Agent 协作流水线
├── cron/           # 定时任务服务
├── heartbeat/      # 心跳服务
├── session/        # 会话管理
├── bus/            # 消息总线
├── api/            # FastAPI 后端
│   └── routes/     # REST API 端点
├── cli/            # 命令行工具
└── config/         # 配置管理
```

## 安装

```bash
pip install solopreneur-ai
```

或从源码安装：
```bash
git clone https://github.com/HKUDS/solopreneur.git
cd solopreneur
pip install -e .
```

**环境要求**：Python ≥ 3.11，Node.js ≥ 18（用于 WhatsApp Bridge）

## 快速开始

1. 初始化配置和工作区：
```bash
solopreneur onboard
```

2. 配置 LLM（`~/.solopreneur/config.json`）：
```json
{
  "providers": {
    "copilot_priority": false,
    "openrouter": { "apiKey": "sk-or-xxx" },
    "anthropic": { "apiKey": "sk-ant-xxx" },
    "openai": { "apiKey": "sk-xxx" },
    "zhipu": { "apiKey": "xxx" },
    "vllm": { "apiKey": "xxx", "api_base": "http://localhost:8000/v1" }
  },
  "agents": {
    "defaults": { "model": "anthropic/claude-sonnet-4" }
  }
}
```

**Provider 说明**：
- `copilot_priority`: 设置为 `true` 优先使用 GitHub Copilot
- `zhipu`: 火山引擎（智谱 AI），支持 glm-4 系列
- `vllm`: 本地 OpenAI 兼容接口（如 vLLM、Ollama）

3. 命令行聊天：
```bash
solopreneur agent -m "你好"
```

4. 启动网关（支持聊天渠道）：
```bash
solopreneur gateway
```

## 配置

### 全局配置

配置文件：`~/.solopreneur/config.json`

```json
{
  "agents": {
    "defaults": {
      "workspace": "~/.solopreneur/workspace",
      "model": "claude-sonnet-4",
      "max_tokens": 8192,
      "temperature": 0.7,
      "max_tool_iterations": 20,
      "max_subagents": 5,
      "agent_timeout": 1800,
      "max_tokens_per_session": 500000
    }
  },
  "providers": {
    "copilot_priority": false,
    "openrouter": { "apiKey": "", "apiBase": "" },
    "anthropic": { "apiKey": "", "apiBase": "" },
    "openai": { "apiKey": "", "apiBase": "" },
    "gemini": { "apiKey": "", "apiBase": "" },
    "groq": { "apiKey": "", "apiBase": "" },
    "zhipu": { "apiKey": "", "apiBase": "" },
    "vllm": { "apiKey": "", "apiBase": "" }
  },
  "channels": {
    "whatsapp": { "enabled": false, "bridge_url": "ws://localhost:3001" },
    "telegram": { "enabled": false, "token": "" },
    "wecom": { "enabled": false, "corp_id": "", "agent_id": "", "secret": "", "token": "", "aes_key": "" }
  },
  "tools": {
    "web": { "search": { "apiKey": "" } },
    "exec": { "timeout": 60, "restrict_to_workspace": false }
  }
}
```

支持环境变量：`solopreneur_PROVIDERS__OPENROUTER__API_KEY`

### 自定义 Agent

在工作区 `~/.solopreneur/workspace/agents/` 创建 YAML 文件：

```yaml
# pediatrician.yaml
name: pediatrician
type: subagent
title: 儿科医生
emoji: 👶
description: 专注于儿童健康的医疗顾问
tools:
  - web_search
  - read_file
max_iterations: 8
temperature: 0.3

system_prompt: |
  你是一位经验丰富的儿科医生，擅长儿童常见病的诊断和健康咨询。
  
  ## 职责范围
  - 儿童常见症状分析和建议
  - 生长发育评估
  - 疫苗接种咨询
  
  ## 重要限制
  - 遇到急重症必须建议立即就医
  - 不提供处方，仅提供健康建议

metadata:
  domain: medical
  category: clinical
```

创建后自动生效，可通过 API 或前端管理。

## 命令行

### 基础命令

| 命令 | 说明 |
|------|------|
| `solopreneur onboard` | 初始化配置和工作区 |
| `solopreneur status` | 查看配置状态和 API 密钥 |
| `solopreneur --version` | 显示版本 |

### Agent 命令

| 命令 | 说明 |
|------|------|
| `solopreneur agent -m "消息"` | 发送单条消息 |
| `solopreneur agent` | 交互模式 |
| `solopreneur agent -s session_id` | 指定会话 ID |

### 网关命令

| 命令 | 说明 |
|------|------|
| `solopreneur gateway` | 启动网关（默认端口 18790） |
| `solopreneur gateway -p 8080 -v` | 指定端口和详细日志 |

### GitHub Copilot 登录（多账号）

| 命令 | 说明 |
|------|------|
| `solopreneur login --slot 1` | 登录第 1 个账号 |
| `solopreneur login --slot 2 --label "工作号"` | 登录并打标签 |
| `solopreneur pool status` | 查看 Token 池状态 |
| `solopreneur pool remove 2` | 移除指定槽位 |
| `solopreneur pool refresh` | 刷新过期 Token |

Token 池特性：
- 最多 10 个 slot
- 轮询负载均衡
- 429 自动熔断（指数退避：30s → 60s → 120s... 最大 300s）
- 连续 10 次错误标记为 DEAD

### 定时任务

| 命令 | 说明 |
|------|------|
| `solopreneur cron list` | 列出任务 |
| `solopreneur cron add -n "早安" -m "早上好" --every 3600` | 每隔 N 秒执行 |
| `solopreneur cron add -n "日报" -m "日报" --cron "0 9 * * *"` | Cron 表达式 |
| `solopreneur cron remove <id>` | 移除任务 |
| `solopreneur cron enable/disable <id>` | 启用/禁用 |
| `solopreneur cron run <id>` | 手动执行 |

### 通道命令

| 命令 | 说明 |
|------|------|
| `solopreneur channels status` | 查看通道状态 |
| `solopreneur channels login` | 扫码登录 WhatsApp |

## 工作区

初始化后创建以下文件（`~/.solopreneur/workspace/`）：

| 文件 | 说明 |
|------|------|
| `AGENTS.md` | Agent 指令和准则 |
| `SOUL.md` | Agent 性格和价值观 |
| `USER.md` | 用户信息和偏好 |
| `agents/` | 自定义 Agent 配置目录 |
| `memory/MEMORY.md` | 长期记忆 |
| `memory/YYYY-MM-DD.md` | 每日笔记（自动创建） |

## 工具

Agent 可用的工具：

| 工具 | 功能 |
|------|------|
| `read_file` | 读取文件内容 |
| `write_file` | 创建/覆盖文件 |
| `edit_file` | 编辑文件（搜索替换） |
| `list_dir` | 列出目录内容 |
| `exec` | 执行 Shell 命令 |
| `web_search` | Brave Search 搜索 |
| `web_fetch` | 获取网页内容 |
| `message` | 发送消息给用户 |
| `spawn` | 创建子 Agent 处理子任务 |
| `delegate` | 委派给指定 Agent |
| `run_workflow` | 执行工作流 |
| `workflow_control` | 控制工作流（next/skip/inject/status/abort） |
| `get_project_env` | 获取项目环境变量配置 |
| `set_project_env` | 设置项目环境变量配置 |

### 项目环境变量

每个项目可配置专属的环境变量（数据库地址、私服地址、API 端点等），AI 执行任务时自动感知并使用：

**配置方式**：
1. **创建项目时填写**：在创建项目 API 中传入 `env_vars` 参数
2. **从现有项目提取**：使用 `config-extract` Skill 自动扫描配置文件
3. **手动设置**：调用 `set_project_env` 工具或通过 API 更新

**变量分类**：

| 分类 | 说明 |
|------|------|
| `database` | 数据库连接信息（MySQL、PostgreSQL、MongoDB 等） |
| `registry` | 私服/镜像源地址（NPM、Maven、Docker Registry 等） |
| `server` | 业务服务地址（API 网关、微服务端点等） |
| `middleware` | 中间件（Redis、MQ、Nacos、Consul、ES 等） |
| `credential` | 敏感凭证（密码、Token、密钥，日志中脱敏显示） |
| `general` | 通用配置 |

**示例**：
```json
{
  "env_vars": [
    {"key": "DB_HOST", "value": "192.168.1.100", "category": "database", "description": "MySQL 主库"},
    {"key": "DB_PORT", "value": "3306", "category": "database"},
    {"key": "NEXUS_URL", "value": "https://nexus.company.com", "category": "registry", "description": "私服地址"},
    {"key": "DB_PASSWORD", "value": "secret123", "category": "credential", "sensitive": true}
  ]
}
```

## Skills 技能

除内置工具外，solopreneur 还支持 Skills（技能）扩展：

| 技能 | 说明 |
|------|------|
| `config-extract` | 从现有项目配置文件中自动提取环境变量 |
| `devops` | CI/CD 流水线、Docker、部署脚本 |
| `testing` | 测试策略、单元测试、E2E 测试 |
| `code-review` | 代码审查最佳实践 |
| `security` | 安全审计、漏洞检测 |
| `architecture` | 架构设计模式 |

**config-extract 技能**会扫描以下配置文件：
- `.env`、`.env.local`、`.env.development` 等
- `application.yml`、`application.properties`（Spring Boot）
- `settings.py`（Django/Python）
- `docker-compose.yml`、`Dockerfile`
- `config.json`、`config.yaml`

提取后的变量自动归类并写入项目环境配置。

## 预设 Agent

### 软件工程领域

| Agent | emoji | 职责 |
|-------|-------|------|
| `product_manager` | 📋 | 需求分析、PRD 撰写 |
| `architect` | 🏗️ | 架构设计、技术选型 |
| `developer` | 💻 | 编码实现 |
| `code_reviewer` | 🔍 | 代码审查 |
| `tester` | 🧪 | 测试策略、自动化测试 |
| `devops` | 🚀 | CI/CD、容器化、部署 |

### 医疗领域

| Agent | emoji | 职责 |
|-------|-------|------|
| `pediatrician` | 👶 | 儿科健康咨询 |
| `nutritionist` | 🥗 | 营养评估和饮食规划 |

### 法律领域

| Agent | emoji | 职责 |
|-------|-------|------|
| `legal_advisor` | ⚖️ | 法律咨询、合同审查 |

### 通用

| Agent | emoji | 职责 |
|-------|-------|------|
| `assistant` | 🤖 | 通用助手 |

## 工作流

4 个预定义流水线：

| 工作流 | 步骤 |
|--------|------|
| `feature` | 需求分析 → 架构设计 → 编码实现 → 代码审查 → 测试 |
| `bugfix` | 问题分析 → 修复审查 → 回归测试 |
| `review` | 代码审查 → 测试建议 |
| `deploy` | 部署前测试 → 部署配置 |

执行模式：
- `auto`：全自动执行所有步骤
- `step`：执行一步后暂停，等待人工确认

## 模型支持

通过 LiteLLM 支持：

- **OpenRouter**: `anthropic/claude-sonnet-4`, `openai/gpt-4o`
- **Anthropic**: `claude-3-5-sonnet-20241022`
- **OpenAI**: `gpt-4o`, `gpt-4o-mini`
- **Gemini**: `gemini-1.5-flash`
- **Groq**: 通过环境变量 `GROQ_API_KEY`
- **火山引擎（智谱）**: `glm-4`, `glm-4-plus`, `glm-4-flash`
- **vLLM/本地**: 自定义 `api_base`（如 `http://localhost:8000/v1`）
- **GitHub Copilot**: OAuth 设备流登录，支持多账号轮询和 429 熔断

**本地模型优化**：
- 从配置文件读取模型名称，避免后端 API 调用
- 锁定模型选择，防止用户误修改
- Token 估算：当本地模型不返回 usage 数据时，自动基于字符数估算 tokens

## API

启动网关后提供 REST API：

### Agent 管理
- `GET /api/v1/agents` - 列出所有 Agents
- `GET /api/v1/agents/{name}` - 获取 Agent 详情
- `POST /api/v1/agents` - 创建自定义 Agent
- `PUT /api/v1/agents/{name}` - 更新自定义 Agent
- `DELETE /api/v1/agents/{name}` - 删除自定义 Agent
- `POST /api/v1/agents/reload` - 重载所有 Agents

### 项目管理
- `GET /api/projects` - 列出所有项目
- `POST /api/projects` - 创建项目（支持传入 env_vars）
- `PUT /api/projects/{id}` - 更新项目
- `DELETE /api/projects/{id}` - 删除项目
- `GET /api/projects/{id}/docs` - 获取项目 Wiki 文档
- `GET /api/projects/{id}/env` - 获取项目环境变量
- `PUT /api/projects/{id}/env` - 更新项目环境变量

### 配置管理
- `GET /api/providers/config` - 获取 Provider 配置
- `PUT /api/providers/config` - 更新 Provider 配置
- `GET /api/auth/models` - 获取可用模型列表

### 其他
- `GET /api/v1/status` - 服务状态
- `POST /api/v1/chat` - 发送消息
- `WebSocket /ws/chat` - 实时聊天（支持流式输出和调用链路追踪）
- `WebSocket /ws/events` - 实时事件广播
- `WebSocket /ws/flow` - 工作流状态

### WebSocket 事件

**聊天事件**：
- `type: "chunk"` - 流式文本片段
- `type: "activity"` - 工具调用/LLM 调用活动
- `type: "trace"` - 调用链路追踪事件（start, llm_start, llm_end, tool_start, tool_end, end）
- `type: "done"` - 处理完成
- `type: "error"` - 错误信息

## 贡献

欢迎 PR！项目保持小巧，易于贡献。

## 最近更新

### v0.3.x - 项目环境变量与配置提取

**新增功能**：
- 🔧 **项目环境变量**：每个项目可配置专属环境变量，AI 自动感知使用
- 🔍 **config-extract Skill**：从现有项目自动提取配置（支持 .env、Spring Boot、Django、Docker 等）
- 🛠️ **环境变量工具**：`get_project_env`、`set_project_env` 工具
- 📊 **变量分类**：database、registry、server、middleware、credential、general
- 🔒 **敏感信息处理**：`sensitive` 标记，日志/API 响应中自动脱敏

**优化改进**：
- ⚡ 系统提示自动注入项目环境配置，AI 无需询问即可使用
- 📝 配置表格化展示，按分类组织

### v0.2.x - Web UI 与本地模型支持

**新增功能**：
- 🎨 **Web UI 界面**：项目管理、实时对话、调用链路监控
- 📊 **实时监控面板**：显示 tokens 统计、工具调用、调用链路时间线
- 📚 **Wiki 文档生成**：自动生成 README、安装指南、架构设计等文档
- 🔧 **本地模型支持**：vLLM、Ollama 等 OpenAI 兼容接口
- 🌋 **火山引擎集成**：支持智谱 AI GLM-4 系列
- 🎯 **Provider 优先级**：可配置 Copilot 优先或其他 Provider
- 🔒 **本地模型锁定**：从配置读取模型，防止误修改

**优化改进**：
- ⚡ Token 统计：支持本地模型的 token 估算
- 🔄 WebSocket 流式输出：实时文本推送和活动追踪
- 📦 配置持久化：localStorage 缓存 Provider 配置
- 🧰 统一 Provider 工厂：自动选择最优 Provider

**Bug 修复**：
- ✅ 修复聊天界面 trace 事件未传递到监控面板的问题
- ✅ 修复本地模型配置读取问题
- ✅ 修复 Provider 切换后系统未更新的问题

---

<p align="center">🐈 solopreneur - 轻量级 AI Agent 框架</p>
