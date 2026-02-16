# 技术调研报告：TauriSidecar、GitHub Copilot OAuth 与企业微信

**日期**：2026-02-05  
**状态**：完成  

## 1. Tauri Sidecar 与 Python 后端集成

### 决策：PyInstaller + FastAPI Sidecar
- **选择了什么**：使用 `PyInstaller` (x86_64-pc-windows-msvc) 将 Python FastAPI 打包为外部二进制文件，由 Tauri 在启动时拉起。
- **理由**：
    - **隔离性**：用户无需安装 Python 环境即可运行。
    - **通信性能**：REST API + WebSocket 在 localhost 通信延迟极低 (<5ms)。
    - **生命周期管理**：Tauri Rust 层可以确保前端关闭时自动杀掉 Sidecar 进程，避免进程遗留。
- **备选方案**：
    - *嵌入式 Python*: 库支持不完善，容易导致 C 扩展依赖冲突。
    - *全局 Python 安装*: 部署门槛过高（需手动安装 Python）。

## 2. GitHub Copilot API 认证

### 决策：GitHub Device OAuth 流
- **选择了什么**：通过 `solopreneur login` 触发 GitHub 设备码流。
    1. 请求 `github.com/login/device/code`。
    2. 用户在浏览器输入验证码。
    3. 轮询 `github.com/login/oauth/access_token` 获取 Access Token。
    4. **关键步骤**：访问 `api.github.com/copilot_internal/v2/token` 获取真正的 Copilot 运行令牌。
- **理由**：
    - **安全性**：令牌保存在本地，不走中心化服务。
    - **合规性**：符合 GitHub 官方模型访问的最佳实践。
- **备选方案**：
    - *环境变量注入*: 令牌获取困难，用户体验差。

## 3. 企业微信集成

### 决策：企业自建应用机器人 + 回调服务器
- **选择了什么**：在后端实现支持 `GET (验证)` 和 `POST (消息接收)` 的 API 端点，处理加密的微信请求。
- **理由**：
    - **双向交互**：普通群机器人 Webhook 只能发，不能通过 Web UI 监控收到的消息。自建应用模式支持完整的对话流控制。
    - **安全性**：支持消息解密 (EncodingAESKey)，确保数据安全。
- **备选方案**：
    - *简单 Webhook*: 无法由 AI 主动响应群聊中的 @ 消息，仅能用于通知推送。

## 4. 前端状态管理

### 决策：Pinia + WebSocket
- **选择了什么**：前端使用 Pinia 管理当前 Agent 状态 (思考中、就绪、错误)。后端通过 WebSocket `/ws/status` 实时推送总线上的 Event。
- **理由**：
    - **实时性**：用户能实时看到 Agent 的思考过程和子任务进度。
    - **响应式架构**：Vue 3 与 Pinia 结合可以非常清晰地同步工作流状态。
- **备选方案**：
    - *轮询*: 产生过多后端负载，且 UI 有延迟。
