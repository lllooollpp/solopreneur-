# MVP 前端测试指南

## ✅ 已完成的功能

### 阶段1-3 完整实现 (T001-T025)
- ✅ Vue3 + TypeScript + Vite 项目结构
- ✅ Tauri 桌面应用配置
- ✅ Pinia 状态管理
- ✅ Vue Router 路由系统
- ✅ FastAPI 后端框架
- ✅ WebSocket 实时通信
- ✅ 4个主要视图页面：Dashboard、Config、Chat、Flow
- ✅ 4个核心组件：SkillCard、AgentEditor、TaskStack、ApprovalCard
- ✅ API 客户端和服务层

## 🧪 测试步骤

### 1. 安装前端依赖

```bash
cd ui
npm install
```

### 2. 启动前端开发服务器

```bash
npm run dev
```

访问: http://localhost:5173

### 3. 启动后端 API 服务器（可选）

```bash
# 在项目根目录
python -m nanobot.api.main
```

后端 API: http://localhost:8000

### 4. 功能验证清单

- [ ] 导航栏正常显示，链接可点击
- [ ] Dashboard 页面显示状态卡片
- [ ] Config 页面显示技能配置（虽然列表为空）
- [ ] Chat 页面可以输入消息（虽然还未连接后端）
- [ ] Flow 页面显示任务追踪面板

## 📝 已知限制

由于 MVP 专注于前端框架搭建，以下功能尚未完全连通：

1. **后端集成**: API 端点返回模拟数据
2. **WebSocket**: 事件推送功能已实现但需要后端支持
3. **企业微信**: 未实现 (阶段4)
4. **GitHub Copilot**: 未实现 (阶段5)
5. **Tauri 打包**: 未完成 (阶段6)

## 🚀 下一步计划

可选方案：
1. 继续实现阶段4 (企业微信渠道)
2. 继续实现阶段5 (GitHub Copilot 模型)
3. 完善后端 API 与前端的完整对接
4. 测试 Tauri 桌面应用打包

## 🐛 故障排查

### 前端无法启动
- 检查 Node.js 版本 >= 18
- 删除 `node_modules` 重新安装
- 检查端口 5173 是否被占用

### 后端无法启动
- 检查 Python 版本 >= 3.11
- 确保已安装 FastAPI: `pip install fastapi uvicorn`
- 检查端口 8000 是否被占用

### CORS 错误
- 确保后端 CORS 配置包含 `http://localhost:5173`
- 检查 `nanobot/api/main.py` 中的 CORS 设置
