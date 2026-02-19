<div align="center">
  <img src="solopreneur_logo.png" alt="solopreneur" width="420">
  <h1>solopreneur：一人软件公司的 AI 执行平台</h1>
  <p>
    <a href="https://pypi.org/project/solopreneur-ai/"><img src="https://img.shields.io/pypi/v/solopreneur-ai" alt="PyPI"></a>
    <a href="https://pepy.tech/project/solopreneur-ai"><img src="https://static.pepy.tech/badge/solopreneur-ai" alt="Downloads"></a>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <a href="./COMMUNICATION.md"><img src="https://img.shields.io/badge/Feishu-Group-E9DBFC?style=flat&logo=feishu&logoColor=white" alt="Feishu"></a>
    <a href="./COMMUNICATION.md"><img src="https://img.shields.io/badge/WeChat-Group-C5EAB4?style=flat&logo=wechat&logoColor=white" alt="WeChat"></a>
  </p>
</div>

🐈 **solopreneur** 是一个面向“一人软件公司”的轻量级 AI 执行平台，基于 Python 构建，支持多模型、项目上下文、工具执行和多 Agent 协作，帮助个人开发者从需求到上线完成完整交付。

## 核心特性

- **多 LLM 提供者支持**：集成 GitHub Copilot、LiteLLM、OpenRouter 等，支持 token 池管理。
- **聊天渠道**：Telegram、WhatsApp、WeCom（企业微信）等。
- **技能系统**：内置工程研发相关技能（代码、测试、发布、运维等），可扩展。
- **Web UI**：Vue 3 + TypeScript 前端，支持实时聊天和配置。
- **Agent 循环**：支持工具调用、记忆和上下文管理。
- **轻量高效**：低资源占用，快速启动。

## 架构

<p align="center">
  <img src="solopreneur_arch.png" alt="solopreneur architecture" width="800">
</p>

项目结构：
```
solopreneur/
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
pip install solopreneur-ai
```

或从源码安装：
```bash
git clone https://github.com/lllooollpp/solopreneur-.git
cd solopreneur
pip install -e .
```

## 快速开始

1. 初始化配置：
```bash
solopreneur onboard
```

2. 配置 `~/.solopreneur/config.json`：
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
solopreneur agent -m "Hello!"
```

## 配置

配置文件：`~/.solopreneur/config.json`

- `providers`：LLM 提供者配置，如 GitHub Copilot（OAuth 设备流）、LiteLLM。
- `agents`：代理默认设置，包括模型选择。
- `channels`：渠道配置，如 Telegram token、WhatsApp 绑定。
- `skills`：启用/禁用技能。

## 命令行

| 命令 | 说明 |
|------|------|
| `solopreneur onboard` | 初始化配置 |
| `solopreneur agent` | 启动代理聊天 |
| `solopreneur gateway` | 启动网关服务器 |
| `solopreneur status` | 查看状态 |
| `solopreneur channels login` | 绑定渠道 |

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

技能位于 `solopreneur/skills/`，支持：
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

<p align="center">🐈 solopreneur - 一人软件公司的 AI 执行平台</p>