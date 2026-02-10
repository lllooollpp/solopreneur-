# 任务清单：前端管理界面、Copilot 模型与企业微信集成

**功能分支**：`001-frontend-copilot-wecom`  
**生成时间**：2026-02-05  
**状态**：待执行

---

## 依赖关系图

```
阶段1 (设置) ──┬──> 阶段2 (基础) ──┬──> 阶段3 [US1] 前端界面
              │                   │
              │                   ├──> 阶段4 [US3] 企业微信 (可与US1部分并行)
              │                   │
              │                   └──> 阶段5 [US2] Copilot模型 (依赖基础后端)
              │
              └──> 阶段6 (完善)
```

**并行机会**：
- 阶段1 中 T002-T004 可并行（独立目录/文件）
- 阶段3 中前端组件 T012-T015 可并行（不同页面模块）
- 阶段4 与阶段5 可在阶段3完成后同时进行

---

## 阶段1：设置（项目初始化）

**目标**：创建前端项目结构，配置 Tauri 打包环境

- [X] T001 使用 Vite + Vue3 + TypeScript 在 `ui/` 目录初始化前端项目
- [X] T002 [P] 在 `ui/src-tauri/` 目录初始化 Tauri 配置 (`tauri.conf.json`)
- [X] T003 [P] 在 `ui/package.json` 添加 Pinia、Vue Router、Axios 等依赖
- [X] T004 [P] 在 `ui/src/api/` 目录创建 API 客户端基类 (`client.ts`)
- [X] T005 创建 `ui/src/stores/` 目录结构并初始化 Pinia store (`agent.ts`, `skills.ts`)

---

## 阶段2：基础（阻塞前提条件）

**目标**：实现后端 API 框架和遗留代码清理，所有用户故事依赖此阶段

- [X] T006 在 `nanobot/api/` 目录创建 FastAPI 应用入口 (`main.py`, `routes/`)
- [X] T007 [P] 在 `nanobot/api/routes/status.py` 实现 `GET /api/status` 端点
- [X] T008 [P] 在 `nanobot/api/websocket.py` 实现 WebSocket `/ws/events` 推送服务
- [X] T009 删除 `nanobot/channels/telegram.py` 文件
- [X] T010 [P] 删除 `nanobot/channels/whatsapp.py` 文件
- [X] T011 [P] 删除整个 `bridge/` 目录及其所有内容

---

## 阶段3：用户故事1 - 通过 Web 界面管理 Nanobot [P1]

**故事目标**：用户可以通过美观的 Web 前端配置 Agent、查看状态并进行对话  
**独立测试标准**：启动 `npm run dev`，访问 `http://localhost:5173`，可导航至 Dashboard、Config、Chat、Flow 页面

### 模型层
- [X] T012 [P] [US1] 在 `ui/src/types/` 目录定义 TypeScript 类型 (`agent.ts`, `skill.ts`, `message.ts`)

### 视图层
- [X] T013 [P] [US1] 在 `ui/src/views/DashboardView.vue` 实现仪表盘页面（状态卡片、统计图表）
- [X] T014 [P] [US1] 在 `ui/src/views/ConfigView.vue` 实现配置管理页面（技能列表、Agent 编辑器）
- [X] T015 [P] [US1] 在 `ui/src/views/ChatView.vue` 实现聊天界面（消息列表、输入框、审批卡片）
- [X] T016 [P] [US1] 在 `ui/src/views/FlowView.vue` 实现工作流展示页面（任务追踪面板）

### 组件层
- [X] T017 [US1] 在 `ui/src/components/SkillCard.vue` 实现技能配置卡片组件（开关、参数表单）
- [X] T018 [P] [US1] 在 `ui/src/components/AgentEditor.vue` 实现 Markdown 编辑器组件（编辑 SOUL.md）
- [X] T019 [P] [US1] 在 `ui/src/components/TaskStack.vue` 实现侧边栏任务追踪面板组件
- [X] T020 [P] [US1] 在 `ui/src/components/ApprovalCard.vue` 实现工具调用审批弹窗组件

### 服务层
- [X] T021 [US1] 在 `ui/src/api/skills.ts` 实现技能 CRUD API 调用
- [X] T022 [US1] 在 `ui/src/api/chat.ts` 实现聊天消息发送 API 调用
- [X] T023 [US1] 在 `ui/src/composables/useWebSocket.ts` 实现 WebSocket 事件订阅 composable

### 集成
- [X] T024 [US1] 在 `ui/src/router/index.ts` 配置 Vue Router 路由表
- [X] T025 [US1] 在 `ui/src/App.vue` 集成导航栏和主布局

---

## 阶段4：用户故事3 - 企业微信渠道交互 [P1]

**故事目标**：用户可以在企业微信中接收通知并与 Agent 沟通  
**独立测试标准**：使用 ngrok 暴露本地端口，在企业微信后台配置回调，发送消息后观察控制台日志

### 模型层
- [X] T026 [P] [US3] 在 `nanobot/channels/wecom.py` 定义 `WeComConfig` 和 `WeComMessage` 数据类

### 服务层
- [X] T027 [US3] 在 `nanobot/channels/wecom.py` 实现消息解密逻辑 (`decrypt_message`)
- [X] T028 [US3] 在 `nanobot/channels/wecom.py` 实现消息加密响应逻辑 (`encrypt_response`)
- [X] T029 [US3] 在 `nanobot/channels/wecom.py` 实现 `WeComCrypto` 类（加密/解密/签名）

### 端点层
- [X] T030 [US3] 在 `nanobot/api/routes/wecom.py` 实现 `GET /api/wecom/callback` 验证端点
- [X] T031 [US3] 在 `nanobot/api/routes/wecom.py` 实现 `POST /api/wecom/callback` 消息接收端点

### 集成
- [X] T032 [US3] 在 `nanobot/channels/manager.py` 注册企业微信配置初始化
- [X] T033 [US3] 在 `nanobot/config/schema.py` 添加企业微信配置项 (`wecom` section)

---

## 阶段5：用户故事2 - 使用 GitHub Copilot 模型进行对话 [P2]

**故事目标**：用户可以使用 GitHub Copilot 订阅驱动 Nanobot 进行高质量对话  
**独立测试标准**：运行 `nanobot login --provider github-copilot` 完成认证，在配置中切换模型后发送消息

### 模型层
- [X] T034 [P] [US2] 在 `nanobot/providers/github_copilot.py` 定义 `CopilotSession` 数据类

### 服务层
- [X] T035 [US2] 在 `nanobot/providers/github_copilot.py` 实现设备流认证启动 (`start_device_flow`)
- [X] T036 [US2] 在 `nanobot/providers/github_copilot.py` 实现令牌轮询与交换 (`poll_for_token`)
- [X] T037 [US2] 在 `nanobot/providers/github_copilot.py` 实现 Copilot Token 获取 (`get_copilot_token`)
- [X] T038 [US2] 在 `nanobot/providers/github_copilot.py` 实现 `GitHubCopilotProvider` 类继承 `BaseProvider`

### 端点层
- [X] T039 [US2] 在 `nanobot/api/routes/auth.py` 实现 `POST /api/auth/github/device` 端点
- [X] T040 [US2] 在 `nanobot/api/routes/auth.py` 实现 `GET /api/auth/github/token` 端点

### CLI 集成
- [X] T041 [US2] 在 `nanobot/cli/commands.py` 添加 `login` 子命令支持 `--provider github-copilot`

### 前端集成
- [X] T042 [US2] 在 `ui/src/views/ConfigView.vue` 添加 GitHub Copilot 认证按钮和状态显示
- [X] T043 [US2] 在 `ui/src/api/auth.ts` 实现设备流认证 API 调用

---

## 阶段6：完善与跨领域关注点

**目标**：优化性能、完善文档、确保代码质量

- [X] T044 在 `ui/src-tauri/tauri.conf.json` 配置 Python sidecar 启动脚本
- [X] T045 [P] 在 `nanobot/api/middleware/` 目录添加 CORS 中间件配置
- [X] T046 [P] 更新 `README.md` 添加前端开发和 Tauri 打包说明
- [X] T047 [P] 更新 `pyproject.toml` 添加 FastAPI、uvicorn、cryptography 依赖
- [X] T048 在 `ui/` 目录添加 `.gitignore` 忽略 `node_modules/` 和 `dist/`
- [X] T049 运行 `npm run build` 验证前端构建无报错
- [X] T050 运行 `npm run tauri build` 验证桌面应用打包成功（需要先构建 Python sidecar）

---

## 实现策略

### MVP 范围（建议）
仅完成 **阶段1 + 阶段2 + 阶段3 (US1)** 即可交付可用的本地 Web 管理界面。

### 增量交付顺序
1. **Sprint 1**：T001-T025 (前端基础 + Dashboard/Config/Chat 页面)
2. **Sprint 2**：T026-T033 (企业微信渠道完整集成)
3. **Sprint 3**：T034-T043 (GitHub Copilot 认证与模型切换)
4. **Sprint 4**：T044-T050 (Tauri 打包与发布准备)

### 并行执行示例

**阶段3 并行批次**：
```
批次A (可同时执行): T012, T013, T014, T015, T016
批次B (依赖批次A): T017, T018, T019, T020
批次C (依赖批次B): T021, T022, T023, T024, T025
```

---

## 宪章合规检查

| 原则 | 状态 | 验证方式 |
|------|------|----------|
| 透明记忆 | ✅ | T018 AgentEditor 直接编辑 Markdown 文件 |
| 中文本地化 | ✅ | 所有任务描述和代码注释使用中文 |
| 异步总线通信 | ✅ | T008, T023 使用 WebSocket 推送 |
| 受控子代理 | ✅ | T019 TaskStack 可视化子任务 |
| 极简配置 | ✅ | T033 仅添加必要的企业微信配置项 |
