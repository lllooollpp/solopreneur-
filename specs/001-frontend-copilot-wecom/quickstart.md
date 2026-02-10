# 前端与 Copilot 集成开发快速上手

## 1. 环境准备

- **Node.js**: 18.x+
- **Rust**: 1.70+ (用于 Tauri 调试)
- **Python**: 3.11+
- **Tauri CLI**: `npm install -g @tauri-apps/cli`

## 2. 后端开发调试 (Python Sidecar)

在根目录下运行后端 API 服务：
```bash
# 激活环境并运行 API 模式
nanobot gateway --dev --port 8080
```

## 3. 前端开发调试 (Vue3)

进入 `ui` 目录：
```bash
cd ui
npm install
npm run dev
```

## 4. 模拟完整 Tauri 应用

```bash
# 在根目录运行 (需先配置好 Python 解释器路径)
npm run tauri dev
```

## 5. GitHub Copilot 认证流程测试

1. 运行 `nanobot login --provider github-copilot`。
2. 按照 CLI 指示在浏览器完成授权。
3. 检查 `~/.nanobot/credentials.json` 是否生成了正确的 Token。

## 6. 企业微信测试建议

1. 使用 [NPS](https://github.com/ehang-io/nps) 或 [ngrok] 进行本地内网穿透。
2. 将穿透后的 URL (例如 `https://xyz.ngrok.io/api/wecom/callback`) 填入企业微信后台。
3. 查看本地控制台的解密日志。
