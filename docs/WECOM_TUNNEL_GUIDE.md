# 企业微信内网穿透配置指南

企业微信回调地址必须是公网可访问的 HTTPS 地址。本地开发时需要使用内网穿透工具。

## 方案一：使用 ngrok（推荐新手）

### 1. 安装 ngrok

访问 https://ngrok.com/download 下载对应系统版本

### 2. 注册并获取 Token

1. 访问 https://dashboard.ngrok.com/signup 注册账号
2. 在 https://dashboard.ngrok.com/get-started/your-authtoken 获取 Authtoken

### 3. 配置并启动

```bash
# 配置 authtoken
ngrok config add-authtoken YOUR_TOKEN

# 启动穿透（假设后端运行在 8000 端口）
ngrok http 8000
```

### 4. 获取公网地址

启动后会显示类似：

```
Session Status                online
Forwarding                    https://abc123.ngrok.io -> http://localhost:8000
```

使用 `https://abc123.ngrok.io` 作为你的公网地址。

### 5. 配置企业微信回调

在企业微信管理后台设置：
- 回调 URL: `https://abc123.ngrok.io/api/wecom/callback`

---

## 方案二：使用 Cloudflare Tunnel（免费、稳定）

### 1. 安装 cloudflared

```bash
# Windows (使用 winget)
winget install Cloudflare.cloudflared

# macOS
brew install cloudflare/cloudflare/cloudflared

# Linux
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
```

### 2. 登录 Cloudflare

```bash
cloudflared tunnel login
```

### 3. 创建隧道

```bash
cloudflared tunnel create solopreneur
```

### 4. 配置隧道

创建 `~/.cloudflared/config.yml`:

```yaml
tunnel: YOUR_TUNNEL_ID
credentials-file: /root/.cloudflared/YOUR_TUNNEL_ID.json

ingress:
  - hostname: your-domain.com
    service: http://localhost:8000
  - service: http_status:404
```

### 5. 启动隧道

```bash
cloudflared tunnel run solopreneur
```

### 6. 配置 DNS

在 Cloudflare 控制台将域名指向隧道。

---

## 方案三：使用 NPS（自建服务）

适合有自己的服务器的场景。

### 1. 服务端配置

在公网服务器上安装 NPS：

```bash
# 下载
wget https://github.com/ehang-io/nps/releases/download/v0.26.10/linux_amd64_server.tar.gz
tar -xzf linux_amd64_server.tar.gz

# 安装
./nps install

# 启动
nps start
```

访问 `http://服务器IP:8080` 管理界面（默认账号 admin/123）

### 2. 客户端配置

本地安装 NPC：

```bash
# 下载
wget https://github.com/ehang-io/nps/releases/download/v0.26.10/linux_amd64_client.tar.gz
tar -xzf linux_amd64_client.tar.gz

# 运行（在管理界面创建隧道后获取命令）
./npc -server=服务器IP:8024 -vkey=客户端密钥
```

---

## 企业微信配置步骤

### 1. 登录企业微信管理后台

访问 https://work.weixin.qq.com/wework_admin/frame

### 2. 创建自建应用

1. 应用管理 → 自建 → 创建应用
2. 填写应用信息（名称、Logo、描述）

### 3. 配置接收消息

1. 进入应用 → 接收消息
2. 设置 API 接收：
   - **URL**: `https://你的穿透域名/api/wecom/callback`
   - **Token**: 自定义一个字符串（如 `solopreneur2024`）
   - **EncodingAESKey**: 点击随机生成

### 4. 配置 solopreneur

编辑 `~/.solopreneur/config.json`:

```json
{
  "channels": {
    "wecom": {
      "enabled": true,
      "corp_id": "你的企业ID",
      "agent_id": "应用AgentId",
      "secret": "应用Secret",
      "token": "你设置的Token",
      "aes_key": "生成的EncodingAESKey"
    }
  }
}
```

### 5. 获取企业信息

- **企业 ID**: 管理工具 → 企业信息 → 企业ID
- **AgentId**: 应用详情页可见
- **Secret**: 应用详情页查看

---

## 测试验证

### 1. 验证回调地址

配置保存后，企业微信会发送验证请求。查看后端日志：

```
收到企业微信验证请求: timestamp=xxx, nonce=xxx
企业微信验证成功
```

### 2. 发送测试消息

在企业微信中打开应用，发送消息。查看日志：

```
收到企业微信消息: timestamp=xxx, nonce=xxx
解析消息成功: from=UserID, type=text, content=你好
消息发送成功: UserID
```

---

## 常见问题

### Q: 验证失败？

1. 检查 Token 和 EncodingAESKey 是否正确
2. 确保内网穿透正常运行
3. 检查 URL 是否正确（注意 /api/wecom/callback 路径）

### Q: 收不到消息？

1. 确认应用已启用"接收消息"功能
2. 检查是否在企业微信客户端发送消息
3. 查看后端日志是否有错误

### Q: 消息发送失败？

1. 检查 Secret 是否正确
2. 确认应用有发送消息权限
3. 检查 access_token 是否获取成功

### Q: ngrok 域名变化？

免费版 ngrok 每次重启域名会变化。解决方案：
1. 升级付费版获取固定域名
2. 使用 Cloudflare Tunnel
3. 每次重启后更新企业微信配置

---

## 安全建议

1. **不要在公网暴露管理端口**：内网穿透只穿透 API 端口
2. **定期更新 Token**：定期更换 Token 和 EncodingAESKey
3. **限制 IP 访问**：企业微信有固定 IP 范围，可配置防火墙
4. **监控异常请求**：记录所有回调请求，及时发现异常

---

*文档更新时间: 2026-02-13*
