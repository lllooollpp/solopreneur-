<div align="center">
  <img src="nanobot_logo.png" alt="nanobot" width="420">
  <h1>nanobot：超轻量级个人 AI 助手</h1>
  <p>
    <a href="https://pypi.org/project/nanobot-ai/"><img src="https://img.shields.io/pypi/v/nanobot-ai" alt="PyPI"></a>
    <a href="https://pepy.tech/project/nanobot-ai"><img src="https://static.pepy.tech/badge/nanobot-ai" alt="Downloads"></a>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <a href="./COMMUNICATION.md"><img src="https://img.shields.io/badge/Feishu-Group-E9DBFC?style=flat&logo=feishu&logoColor=white" alt="Feishu"></a>
    <a href="./COMMUNICATION.md"><img src="https://img.shields.io/badge/WeChat-Group-C5EAB4?style=flat&logo=wechat&logoColor=white" alt="WeChat"></a>
  </p>
</div>

一款体积小、易改造、适合研究与工程验证的个人代理框架。nanobot 将核心代理能力浓缩为轻量且模块化的实现，方便快速迭代与移植。

## 快讯

- **2026-02-01** 🎉 nanobot 正式发布！欢迎试用与贡献。

## 简体中文：项目简介与快速开始

nanobot 是一个超轻量级的个人 AI 助手，目标是提供研究友好、易扩展且低成本的代理框架。此仓库包含完整的后端、前端以及若干示例技能（如 GitHub、天气、TMUX 等）。

- 适用人群：研究者、开发者、想要搭建本地/私有代理服务的工程师
- 核心优势：小巧、模块化、方便调试和二次开发

快速开始（中文）

1) 克隆仓库并进入目录：

```bash
git clone https://github.com/lllooollpp/solopreneur-.git
cd nanobot
```

2) 创建并激活虚拟环境（推荐 Python 3.11+）：

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -e .
```

3) 初始化配置并运行（示例）：

```bash
nanobot onboard
nanobot agent -m "你好，帮我写个 TODO 列表。"
```

配置文件位于 `~/.nanobot/config.json`，常见项包括 LLM 提供者、默认模型与渠道（Telegram/WhatsApp）。

如果你希望我帮你把当前仓库配置为默认部署、或需要把 README 翻译为完整的中文版本，请告诉我想要的结构和内容。

## 核心特性

- 轻量：约 4,000 行核心代码，便于阅读与定制。
- 研究友好：代码结构清晰，利于实验与扩展。
- 快速迭代：低资源占用，启动快，迭代效率高。
- 易用：提供命令行与 Web 控制面板，快速上手。

## 🏗️ Architecture

<p align="center">
  <img src="nanobot_arch.png" alt="nanobot architecture" width="800">
</p>

## ✨ Features

<table align="center">
  <tr align="center">
    <th><p align="center">📈 24/7 Real-Time Market Analysis</p></th>
    <th><p align="center">🚀 Full-Stack Software Engineer</p></th>
    <th><p align="center">📅 Smart Daily Routine Manager</p></th>
    <th><p align="center">📚 Personal Knowledge Assistant</p></th>
  </tr>
  <tr>
    <td align="center"><p align="center"><img src="case/search.gif" width="180" height="400"></p></td>
    <td align="center"><p align="center"><img src="case/code.gif" width="180" height="400"></p></td>
    <td align="center"><p align="center"><img src="case/scedule.gif" width="180" height="400"></p></td>
    <td align="center"><p align="center"><img src="case/memory.gif" width="180" height="400"></p></td>
  </tr>
  <tr>
    <td align="center">Discovery • Insights • Trends</td>
    <td align="center">Develop • Deploy • Scale</td>
    <td align="center">Schedule • Automate • Organize</td>
    <td align="center">Learn • Memory • Reasoning</td>
  </tr>
</table>

## 安装（快速）

推荐用于开发：从源码安装。

```bash
git clone https://github.com/lllooollpp/solopreneur-.git
cd nanobot
python -m venv .venv
.
```

在 Windows PowerShell 下激活虚拟环境并安装：

```powershell
.venv\Scripts\Activate.ps1
pip install -e .
```

也可通过 PyPI 或包管理器安装（适合生产/稳定环境）：

```bash
pip install nanobot-ai
```

## 快速开始

1) 初始化并创建默认配置：

```bash
nanobot onboard
```

2) 编辑 `~/.nanobot/config.json`，示例：

```json
{
  "providers": {
    "openrouter": { "apiKey": "sk-or-v1-xxx" }
  },
  "agents": {
    "defaults": { "model": "anthropic/claude-opus-4-5" }
  }
}
```

3) 与 agent 聊天示例：

```bash
nanobot agent -m "你好，帮我写个总结。"
```

提示：将你的 LLM API Key 放在 `~/.nanobot/config.json` 中。若使用本地模型（vLLM 等），可把 `apiBase` 配置指向本地服务。

## 本地模型（vLLM 等）

你可以将 nanobot 连接到本地模型服务（如 vLLM、Llama 兼容服务等）：

1) 启动本地模型服务（示例）：

```bash
vllm serve meta-llama/Llama-3.1-8B-Instruct --port 8000
```

2) 在 `~/.nanobot/config.json` 中配置 provider：

```json
{
  "providers": {
    "vllm": { "apiKey": "dummy", "apiBase": "http://localhost:8000/v1" }
  },
  "agents": { "defaults": { "model": "meta-llama/Llama-3.1-8B-Instruct" } }
}
```

3) 启动并对话：

```bash
nanobot agent -m "本地模型测试"
```

提示：对于无需认证的本地服务，`apiKey` 可为任意非空字符串。

## 聊天渠道（Telegram / WhatsApp 等）

nanobot 支持多种渠道接入：目前内置对 Telegram、WeCom（企业微信）和 WhatsApp 的支持。

Telegram（推荐）示例：

1) 使用 `@BotFather` 创建 bot 并获取 token；
2) 在 `~/.nanobot/config.json` 中启用渠道并填入 token；
3) 启动 `nanobot gateway` 即可接收消息。

WhatsApp 说明：需要 Node.js 支持并进行设备绑定（扫描 QR），适用于需要手机端接入的场景。

## 配置说明

配置文件位置：`~/.nanobot/config.json`。关键配置项包括：

- `providers`：LLM 与外部服务的 API Key 与 endpoint；
- `agents.defaults.model`：默认模型；
- `channels`：启用的消息通道与访问控制（allowFrom）。

示例 provider：`openrouter`（推荐）`anthropic`，`openai`，`vllm`（本地）等均支持。


<details>
<summary><b>Full config example</b></summary>

```json
{
  "agents": {
    "defaults": {
      "model": "anthropic/claude-opus-4-5"
    }
  },
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    },
    "groq": {
      "apiKey": "gsk_xxx"
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "123456:ABC...",
      "allowFrom": ["123456789"]
    },
    "whatsapp": {
      "enabled": false
    }
  },
  "tools": {
    "web": {
      "search": {
        "apiKey": "BSA..."
      }
    }
  }
}
```

</details>

## 常用命令

| 命令 | 说明 |
|---|---|
| `nanobot onboard` | 初始化配置与工作目录 |
| `nanobot agent -m "..."` | 使用 CLI 与 agent 对话 |
| `nanobot agent` | 交互式聊天模式 |
| `nanobot gateway` | 启动网关（REST + WebSocket） |
| `nanobot status` | 显示运行状态 |
| `nanobot channels login` | 绑定 WhatsApp（扫码） |

<details>
<summary><b>Scheduled Tasks (Cron)</b></summary>

```bash
# Add a job
nanobot cron add --name "daily" --message "Good morning!" --cron "0 9 * * *"
nanobot cron add --name "hourly" --message "Check status" --every 3600

# List jobs
nanobot cron list

# Remove a job
nanobot cron remove <job_id>
```

</details>

## Docker（容器运行）

建议把本地配置目录挂载进容器以保留配置：

```bash
# 构建镜像
docker build -t nanobot .

# 初始化配置（仅第一次）
docker run -v ~/.nanobot:/root/.nanobot --rm nanobot onboard

# 启动网关（映射 18790 端口）
docker run -v ~/.nanobot:/root/.nanobot -p 18790:18790 nanobot gateway
```

## 项目结构（简要）

```
nanobot/
├── agent/        # 核心 Agent 实现（loop, context, memory, subagent）
├── providers/    # 各类 LLM 提供者实现（OpenRouter, Copilot, vLLM 等）
├── api/          # FastAPI 后端（REST + WebSocket）
├── channels/     # 聊天渠道适配（Telegram, WhatsApp, WeCom）
├── skills/       # 内置技能（GitHub、天气、测试等）
├── ui/           # 前端（Vue 3 + TypeScript）
└── scripts/      # 小工具与示例脚本
```

## 🎨 Web UI (Frontend)

nanobot includes a modern web-based control panel built with Vue 3, TypeScript, and Tauri.

### Features

- 📊 **Dashboard** — Real-time agent status, uptime, message count
- ⚙️ **Config** — Enable/disable skills, edit Agent definition
- 💬 **Chat** — Interactive conversation with your agent
- 📈 **Flow** — Visualize task execution and workflow
- 🔐 **GitHub Copilot** — Authenticate and use Copilot models

### Development

**Prerequisites**: Node.js 18+ and Rust (for Tauri)

```bash
# Navigate to the UI directory
cd ui

# Install dependencies
npm install

# Start dev server (frontend only, connects to localhost:8000 API)
npm run dev

# Start Tauri dev (includes frontend + desktop wrapper)
npm run tauri:dev

# Build for production
npm run tauri:build
```

**Architecture**:
- **Frontend**: Vue 3 + TypeScript + Vite (runs on port 5173 in dev)
- **Backend**: FastAPI (runs on port 8000 via `nanobot gateway --api`)
- **Desktop**: Tauri (Rust wrapper for native app distribution)

**API Connection**:
The frontend connects to the backend via:
- REST API: `http://localhost:8000/api/*`
- WebSocket: `ws://localhost:8000/ws/events`

### GitHub Copilot Integration

1. **CLI Authentication** (first time):
   ```bash
   nanobot login --provider github-copilot
   # Follow the instructions to authorize in browser
   ```

2. **Web UI Authentication**:
   - Open the Config page
   - Click "开始认证" (Start Authentication) in GitHub Copilot section
   - Follow the OAuth device flow in browser

3. **Use Copilot**:
   ```json
   {
     "agents": {
       "defaults": {
         "model": "gpt-4"
       }
     },
     "providers": {
       "github_copilot": {
         "enabled": true
       }
     }
   }
   ```

### Enterprise WeChat (WeCom) Channel

nanobot supports Enterprise WeChat group robot webhooks with message encryption.

**1. Create a group robot in Enterprise WeChat**:
   - Open your group → Manage → Add Group Robot
   - Copy the webhook URL and get corp_id, agent_id, secret, token, aes_key

**2. Configure** (`~/.nanobot/config.json`):
```json
{
  "channels": {
    "wecom": {
      "enabled": true,
      "corp_id": "wx1234567890abcdef",
      "agent_id": "1000001",
      "secret": "your_secret",
      "token": "your_token",
      "aes_key": "your_aes_key_43_chars_base64"
    }
  }
}
```

**3. Run the API server**:
```bash
nanobot gateway --api
# API server runs on http://localhost:8000
# WeChat callback URL: http://your-domain.com/api/wecom/callback
```

**4. Configure webhook in Enterprise WeChat**:
   - URL: `http://your-domain.com/api/wecom/callback`
   - The system will handle URL verification and encrypted message receiving

### Building Desktop App

```bash
cd ui
npm run tauri:build
```

The executable will be in `ui/src-tauri/target/release/bundle/`.

**Supported platforms**:
- 🪟 Windows (.exe, .msi)
- 🍎 macOS (.dmg, .app)
- 🐧 Linux (.deb, .AppImage)



## 参与贡献与路线图

欢迎提交 PR！项目刻意保持小巧以便快速阅读与改造。

计划（示例）：

- 已完成：语音转录（Groq Whisper）
- 进行中：多模态、长期记忆与更强推理能力
- 待办：更多渠道整合（Discord、Slack）、改进自学习能力

如果你希望我帮助将 README 再细化（增加部署、CI、示例配置），回复我想要的章节，我会继续完善。

---

谢谢使用 nanobot！
