<div align="center">
  <img src="nanobot_logo.png" alt="nanobot" width="420">
  <h1>nanobot：轻量级 AI 代理框架</h1>
  <p>
    <a href="https://pypi.org/project/nanobot-ai/"><img src="https://img.shields.io/pypi/v/nanobot-ai" alt="PyPI"></a>
    <a href="https://pepy.tech/project/nanobot-ai"><img src="https://static.pepy.tech/badge/nanobot-ai" alt="Downloads"></a>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <a href="./COMMUNICATION.md"><img src="https://img.shields.io/badge/Feishu-Group-E9DBFC?style=flat&logo=feishu&logoColor=white" alt="Feishu"></a>
    <a href="./COMMUNICATION.md"><img src="https://img.shields.io/badge/WeChat-Group-C5EAB4?style=flat&logo=wechat&logoColor=white" alt="WeChat"></a>
  </p>
</div>

🐈 **nanobot** 是一个专为软件公司设计的 AI 代理集群框架，基于 Python 构建，支持多种 LLM 提供者、聊天渠道和技能扩展。核心代码约 4,000 行，易于理解、修改和部署。

## 核心特性

- **AI 代理集群**：专为软件公司设计，支持多代理协作、任务分配和集群管理。
- **多 LLM 提供者支持**：集成 GitHub Copilot、LiteLLM、OpenRouter 等，支持 token 池管理。
- **聊天渠道**：Telegram、WhatsApp、WeCom（企业微信）等。
- **技能系统**：内置 GitHub、天气、TMUX 等技能，可扩展。
- **Web UI**：Vue 3 + TypeScript 前端，支持实时聊天和配置。
- **Agent 循环**：支持工具调用、记忆和上下文管理。
- **轻量高效**：低资源占用，快速启动。

## 架构

<p align="center">
  <img src="nanobot_arch.png" alt="nanobot architecture" width="800">
</p>

项目结构：
```
nanobot/
├── agent/          # 代理核心（loop, context, memory, subagent）
├── providers/      # LLM 提供者（github_copilot, litellm_provider）
├── api/            # FastAPI 后端（REST + WebSocket）
├── channels/       # 聊天渠道（telegram, whatsapp, wecom）
├── skills/         # 技能模块（github, weather, tmux）
├── ui/             # 前端（Vue 3 + Tauri）
├── cli/            # 命令行工具
├── config/         # 配置管理
└── utils/          # 工具函数
```

## 安装

```bash
pip install nanobot-ai
```

或从源码安装：
```bash
git clone https://github.com/lllooollpp/solopreneur-.git
cd nanobot
pip install -e .
```

## 快速开始

1. 初始化配置：
```bash
nanobot onboard
```

2. 配置 `~/.nanobot/config.json`：
```json
{
  "providers": {
    "github_copilot": { "enabled": true },
    "litellm": { "apiKey": "your_key" }
  },
  "agents": {
    "defaults": { "model": "gpt-4" }
  },
  "channels": {
    "telegram": { "enabled": true, "token": "your_token" }
  }
}
```

3. 启动聊天：
```bash
nanobot agent -m "Hello!"
```

## 配置

配置文件：`~/.nanobot/config.json`

- `providers`：LLM 提供者配置，如 GitHub Copilot（OAuth 设备流）、LiteLLM。
- `agents`：代理默认设置，包括模型选择。
- `channels`：渠道配置，如 Telegram token、WhatsApp 绑定。
- `skills`：启用/禁用技能。

## 命令行

| 命令 | 说明 |
|------|------|
| `nanobot onboard` | 初始化配置 |
| `nanobot agent` | 启动代理聊天 |
| `nanobot gateway` | 启动网关服务器 |
| `nanobot status` | 查看状态 |
| `nanobot channels login` | 绑定渠道 |

## Web UI

前端基于 Vue 3 + TypeScript，支持：
- 实时聊天
- 配置管理
- 技能启用
- GitHub Copilot 认证

开发：
```bash
cd ui
npm install
npm run dev
```

## 技能扩展

技能位于 `nanobot/skills/`，支持：
- GitHub 操作
- 天气查询
- TMUX 会话管理

自定义技能：继承 `BaseSkill` 类，实现 `execute` 方法。

## 贡献

欢迎 PR！项目保持小巧，易于贡献。

路线图：
- 改进记忆系统
- 添加更多渠道
- 增强工具调用

---

<p align="center">🐈 nanobot - 轻量级 AI 代理框架</p>