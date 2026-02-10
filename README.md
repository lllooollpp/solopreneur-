<div align="center">
  <img src="nanobot_logo.png" alt="nanobot" width="420">
  <h1>nanobot：轻量级 AI Agent 框架</h1>
  <p>
    <a href="https://pypi.org/project/nanobot-ai/"><img src="https://img.shields.io/pypi/v/nanobot-ai" alt="PyPI"></a>
    <a href="https://pepy.tech/project/nanobot-ai"><img src="https://static.pepy.tech/badge/nanobot-ai" alt="Downloads"></a>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <a href="./COMMUNICATION.md"><img src="https://img.shields.io/badge/Feishu-Group-E9DBFC?style=flat&logo=feishu&logoColor=white" alt="Feishu"></a>
    <a href="./COMMUNICATION.md"><img src="https://img.shields.io/badge/WeChat-Group-C5EAB4?style=flat&logo=wechat&logoColor=white" alt="WeChat"></a>
  </p>
</div>

🐈 **nanobot** 是一个轻量级 AI Agent 框架，基于 Python 构建，支持多 LLM 提供商、多聊天渠道、工具调用和软件工程角色协作。核心代码约 4,000 行，易于理解、修改和部署。

## 核心特性

- **Agent 循环**：支持工具调用（最多 20 次迭代）、上下文三层压缩、Token 限制和超时控制（30 分钟）
- **多 LLM 支持**：通过 LiteLLM 支持 OpenRouter、Anthropic、OpenAI、Gemini、Groq、vLLM/本地模型，以及 GitHub Copilot（多账号 Token 池）
- **工具系统**：文件操作、Shell 执行、Web 搜索/获取、消息发送、子 Agent 衍生、角色委派、工作流执行
- **角色系统**：6 个软件工程角色（产品经理、架构师、开发工程师、代码审查员、测试工程师、DevOps）
- **工作流引擎**：预定义功能开发、Bug 修复、代码审查、部署上线流水线，支持自动和分步交互模式
- **聊天渠道**：WhatsApp、Telegram、企业微信（WeCom），支持白名单权限控制
- **记忆系统**：每日笔记（YYYY-MM-DD.md）+ 长期记忆（MEMORY.md）
- **定时任务**：支持 interval、cron 表达式、一次性任务，可交付到聊天渠道
- **心跳服务**：定期自动执行预设 Prompt

## 架构

<p align="center">
  <img src="nanobot_arch.png" alt="nanobot architecture" width="800">
</p>

```
nanobot/
├── agent/          # Agent 核心
│   ├── loop.py     # Agent 循环（工具调用、上下文压缩、超时控制）
│   ├── memory.py   # 记忆系统（每日笔记 + 长期记忆）
│   ├── context.py  # 上下文构建
│   ├── compaction.py  # 三层上下文压缩引擎
│   ├── subagent.py    # 子 Agent 管理
│   └── tools/      # 工具实现
│       ├── filesystem.py   # read_file, write_file, edit_file, list_dir
│       ├── shell.py        # exec
│       ├── web.py          # web_search, web_fetch
│       ├── message.py      # message
│       ├── spawn.py        # spawn (子 Agent)
│       ├── delegate.py     # delegate (角色委派)
│       └── ...
├── providers/      # LLM 提供商
│   ├── litellm_provider.py  # LiteLLM 统一接口
│   ├── github_copilot.py    # GitHub Copilot 特殊处理
│   └── token_pool.py        # 多账号 Token 池管理
├── channels/       # 聊天渠道
│   ├── whatsapp.py   # WhatsApp (通过 Bridge)
│   ├── telegram.py   # Telegram Bot
│   └── wecom.py      # 企业微信
├── roles/          # 软件工程角色
│   └── definitions.py  # 6 个预定义角色
├── workflow/       # 工作流引擎
│   └── engine.py   # 功能开发/Bug修复/代码审查/部署上线
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
pip install nanobot-ai
```

或从源码安装：
```bash
git clone https://github.com/HKUDS/nanobot.git
cd nanobot
pip install -e .
```

**环境要求**：Python ≥ 3.11，Node.js ≥ 18（用于 WhatsApp Bridge）

## 快速开始

1. 初始化配置和工作区：
```bash
nanobot onboard
```

2. 配置 LLM（`~/.nanobot/config.json`）：
```json
{
  "providers": {
    "openrouter": { "apiKey": "sk-or-xxx" },
    "anthropic": { "apiKey": "sk-ant-xxx" },
    "openai": { "apiKey": "sk-xxx" }
  },
  "agents": {
    "defaults": { "model": "anthropic/claude-sonnet-4" }
  }
}
```

3. 命令行聊天：
```bash
nanobot agent -m "你好"
```

4. 启动网关（支持聊天渠道）：
```bash
nanobot gateway
```

## 配置

配置文件：`~/.nanobot/config.json`

```json
{
  "agents": {
    "defaults": {
      "workspace": "~/.nanobot/workspace",
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
    "openrouter": { "apiKey": "", "apiBase": "" },
    "anthropic": { "apiKey": "", "apiBase": "" },
    "openai": { "apiKey": "", "apiBase": "" },
    "gemini": { "apiKey": "", "apiBase": "" },
    "groq": { "apiKey": "", "apiBase": "" },
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

支持环境变量：`NANOBOT_PROVIDERS__OPENROUTER__API_KEY`

## 命令行

### 基础命令

| 命令 | 说明 |
|------|------|
| `nanobot onboard` | 初始化配置和工作区 |
| `nanobot status` | 查看配置状态和 API 密钥 |
| `nanobot --version` | 显示版本 |

### Agent 命令

| 命令 | 说明 |
|------|------|
| `nanobot agent -m "消息"` | 发送单条消息 |
| `nanobot agent` | 交互模式 |
| `nanobot agent -s session_id` | 指定会话 ID |

### 网关命令

| 命令 | 说明 |
|------|------|
| `nanobot gateway` | 启动网关（默认端口 18790） |
| `nanobot gateway -p 8080 -v` | 指定端口和详细日志 |

### GitHub Copilot 登录（多账号）

| 命令 | 说明 |
|------|------|
| `nanobot login --slot 1` | 登录第 1 个账号 |
| `nanobot login --slot 2 --label "工作号"` | 登录并打标签 |
| `nanobot pool status` | 查看 Token 池状态 |
| `nanobot pool remove 2` | 移除指定槽位 |
| `nanobot pool refresh` | 刷新过期 Token |

Token 池特性：
- 最多 10 个 slot
- 轮询负载均衡
- 429 自动熔断（指数退避：30s → 60s → 120s... 最大 300s）
- 连续 10 次错误标记为 DEAD

### 定时任务

| 命令 | 说明 |
|------|------|
| `nanobot cron list` | 列出任务 |
| `nanobot cron add -n "早安" -m "早上好" --every 3600` | 每隔 N 秒执行 |
| `nanobot cron add -n "日报" -m "日报" --cron "0 9 * * *"` | Cron 表达式 |
| `nanobot cron remove <id>` | 移除任务 |
| `nanobot cron enable/disable <id>` | 启用/禁用 |
| `nanobot cron run <id>` | 手动执行 |

### 通道命令

| 命令 | 说明 |
|------|------|
| `nanobot channels status` | 查看通道状态 |
| `nanobot channels login` | 扫码登录 WhatsApp |

## 工作区

初始化后创建以下文件（`~/.nanobot/workspace/`）：

| 文件 | 说明 |
|------|------|
| `AGENTS.md` | Agent 指令和准则 |
| `SOUL.md` | Agent 性格和价值观 |
| `USER.md` | 用户信息和偏好 |
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
| `delegate` | 委派给指定角色 |
| `run_workflow` | 执行开发工作流 |
| `workflow_control` | 控制工作流（next/skip/inject/status/abort） |

## 角色

6 个软件工程角色：

| 角色 | emoji | 职责 |
|------|-------|------|
| `product_manager` | 📋 | 需求分析、PRD 撰写 |
| `architect` | 🏗️ | 架构设计、技术选型 |
| `developer` | 💻 | 编码实现 |
| `code_reviewer` | 🔍 | 代码审查 |
| `tester` | 🧪 | 测试策略、自动化测试 |
| `devops` | 🚀 | CI/CD、容器化、部署 |

## 工作流

4 个预定义开发流水线：

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
- **vLLM/本地**: 自定义 `api_base`
- **GitHub Copilot**: OAuth 设备流登录

## API

启动网关后提供 REST API：

- `GET /api/v1/status` - 服务状态
- `POST /api/v1/chat` - 发送消息
- `WebSocket /ws` - 实时聊天

## 贡献

欢迎 PR！项目保持小巧，易于贡献。

---

<p align="center">🐈 nanobot - 轻量级 AI Agent 框架</p>
