# 🚀 nanobot UI 快速启动指南

## 前置要求

- **Node.js** 18+ ([下载](https://nodejs.org/))
- **Rust** (可选，仅用于 Tauri 桌面构建) ([下载](https://www.rust-lang.org/))
- **Python** 3.11+ (后端 API 服务器)

## 开发模式

### 1. 启动后端 API

```bash
# 在项目根目录
nanobot gateway --api

# 或者直接用 Python 启动
python -m uvicorn nanobot.api.main:app --host 127.0.0.1 --port 8000
```

API 将运行在 `http://localhost:8000`

### 2. 启动前端开发服务器

```bash
cd ui
npm install
npm run dev
```

前端将运行在 `http://localhost:5173`

### 3. 访问 Web UI

在浏览器中打开 [http://localhost:5173](http://localhost:5173)

## Tauri 桌面应用 (可选)

### 开发模式

```bash
cd ui
npm run tauri:dev
```

这会启动一个原生窗口，集成前端和后端。

### 生产构建

```bash
cd ui
npm run tauri:build
```

构建产物位于 `ui/src-tauri/target/release/bundle/`

支持的平台：
- Windows: `.exe`, `.msi`
- macOS: `.dmg`, `.app`
- Linux: `.deb`, `.AppImage`

## 功能测试

### 1. Dashboard (仪表板)

- ✅ 查看 Agent 状态 (IDLE/THINKING/ERROR/OFFLINE)
- ✅ 显示运行时间和消息计数
- ✅ 错误信息展示

### 2. Config (配置)

- ✅ 技能列表展示和启用/禁用切换
- ✅ Agent 定义编辑 (SOUL.md)
- ✅ GitHub Copilot 认证
  - 点击"开始认证" → 按照提示在浏览器中授权
  - 认证成功后显示过期时间

### 3. Chat (对话)

- ✅ 消息列表展示 (用户/Agent/系统/工具)
- ✅ 发送消息
- ✅ 消息角色徽章和时间戳
- ⏳ TODO: 连接后端 API

### 4. Flow (工作流)

- ✅ 任务栈展示
- ✅ 任务状态 (pending/running/completed/failed)
- ✅ 快照历史
- ⏳ TODO: 连接后端 API

## API 端点

### REST API

- `GET /api/status` - 获取 Agent 状态
- `GET /api/skills` - 获取技能列表
- `POST /api/skills/{name}/toggle` - 切换技能启用状态
- `POST /api/auth/github/device` - 启动 GitHub Copilot 设备流程
- `POST /api/auth/github/token` - 轮询 Copilot token
- `GET /api/auth/github/status` - 检查认证状态
- `POST /api/wecom/callback` - 企业微信消息回调
- `GET /api/wecom/callback` - 企业微信 URL 验证

### WebSocket

- `WS /ws/events` - 实时事件流
  - Agent 状态变更
  - 任务执行进度
  - 工具调用事件

## 常见问题

### 前端无法连接后端

1. 确认后端运行在 `http://localhost:8000`
2. 检查浏览器控制台是否有 CORS 错误
3. 确认 `nanobot/api/main.py` 中 CORS 配置正确

### Tauri 构建失败

1. 确认安装了 Rust: `rustc --version`
2. 确认安装了系统依赖 (Linux 需要 `libgtk-3-dev`, `libwebkit2gtk-4.0-dev` 等)
3. 查看详细错误日志: `npm run tauri:build -- --verbose`

### GitHub Copilot 认证失败

1. 使用 CLI 先测试: `nanobot login --provider github-copilot`
2. 检查是否有有效的 GitHub 账号
3. 确认设备代码未过期 (15 分钟有效期)

## 开发技巧

### 热重载

- **前端**: Vite 自动热重载 (保存文件即生效)
- **后端**: 使用 `--reload` 标志启动 uvicorn
  ```bash
  uvicorn nanobot.api.main:app --reload --host 127.0.0.1 --port 8000
  ```

### 调试

- **前端**: 浏览器开发者工具 (F12)
- **后端**: FastAPI 自动文档 http://localhost:8000/docs
- **WebSocket**: 使用 WebSocket 客户端工具或浏览器控制台

### 代码风格

- **前端**: ESLint + Prettier (配置在 `.eslintrc.js`)
- **后端**: Ruff (配置在 `pyproject.toml`)

运行格式化:
```bash
# 前端
npm run lint
npm run format

# 后端
ruff check nanobot/
ruff format nanobot/
```

## 下一步

- 📖 阅读 [MVP_TEST.md](MVP_TEST.md) 了解测试用例
- 🎯 查看 [tasks.md](../docs/spec/001-frontend-copilot-wecom/tasks.md) 了解开发进度
- 🤝 贡献代码: [CONTRIBUTING.md](../CONTRIBUTING.md) (如果有)

---

**有问题？** 请在 GitHub Issues 中提问或加入我们的社区。
