# LLM Provider 连接测试指南

## 🚀 快速开始

### 1. 诊断配置问题

```bash
python diagnose_provider.py
```

这个脚本会：
- ✅ 检查配置文件位置
- ✅ 分析当前配置内容
- ✅ 识别将被使用的 Provider
- ✅ 分析错误日志
- ✅ 给出解决方案建议

---

## 📋 测试脚本说明

### 1. `diagnose_provider.py` - 配置诊断

**用途**: 诊断 Provider 配置问题

**运行**:
```bash
python diagnose_provider.py
```

**输出**:
- 配置文件位置
- 所有 Provider 配置状态
- Copilot 优先级设置
- 错误分析
- 解决方案建议

---

### 2. `test_llm_connection.py` - 完整测试

**用途**: 测试配置文件中的 Provider

**运行**:
```bash
# 测试配置文件中的 Provider
python test_llm_connection.py

# 测试自定义配置
python test_llm_connection.py --custom <provider_type> <api_key> <api_base> <model>

# 示例：测试本地 vLLM
python test_llm_connection.py --custom vllm dummy http://localhost:8000/v1 llama-3-8b

# 示例：测试火山引擎
python test_llm_connection.py --custom zhipu your-api-key https://open.bigmodel.cn/api/paas/v4/ glm-4
```

**测试流程**:
1. 加载配置
2. 检查 Provider 优先级
3. 创建 Provider 实例
4. 获取默认模型
5. 发送测试消息
6. 显示响应结果

---

### 3. `quick_test.py` - 快速测试

**用途**: 快速测试一个 API 端点

**运行**:
```bash
# 使用命令行参数
python quick_test.py <api_base> <api_key> <model>

# 示例
python quick_test.py http://localhost:8000/v1 dummy llama-3-8b
python quick_test.py http://10.104.6.197:38099/v1 dummy llama-3-8b
```

**输出**:
- 连接状态（成功/失败）
- 模型响应内容

---

## 🔍 常见问题排查

### 问题 1: 连接被拒绝

**错误信息**:
```
Cannot connect to host 10.104.6.197:38099
```

**排查步骤**:

1. **检查服务器是否运行**
   ```bash
   # 在服务器机器上检查
   curl http://10.104.6.197:38099/v1/models

   # 或检查端口监听
   netstat -tuln | grep 38099
   ```

2. **检查配置是否正确**
   ```bash
   python diagnose_provider.py
   ```

3. **测试连接**
   ```bash
   python quick_test.py http://10.104.6.197:38099/v1 dummy llama-3-8b
   ```

---

### 问题 2: 认证失败

**错误信息**:
```
Authentication failed
Unauthorized
Invalid API key
```

**解决方案**:

1. 检查 API Key 是否正确
2. 确认 API Key 是否有效
3. 检查 API Key 是否过期

---

### 问题 3: 模型不存在

**错误信息**:
```
Model not found
Invalid model name
```

**解决方案**:

1. 检查模型名称拼写
2. 确认模型在 Provider 中可用
3. 查看可用模型列表:
   ```bash
   curl http://your-api-base/v1/models
   ```

---

### 问题 4: 速率限制

**错误信息**:
```
Rate limit exceeded
429 Too Many Requests
```

**解决方案**:

1. 等待一段时间后重试
2. 检查 API 使用额度
3. 考虑升级 API 计划

---

## 📊 测试示例

### 示例 1: 测试本地 vLLM

```bash
# 1. 启动本地 vLLM
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Meta-Llama-3-8B-Instruct \
  --port 8000

# 2. 测试连接
python quick_test.py http://localhost:8000/v1 dummy llama-3-8b

# 3. 完整测试
python test_llm_connection.py
```

### 示例 2: 测试远程 vLLM

```bash
# 1. 测试连接
python quick_test.py http://10.104.6.197:38099/v1 dummy llama-3-8b

# 2. 如果失败，检查服务器状态
curl http://10.104.6.197:38099/v1/models

# 3. 诊断配置
python diagnose_provider.py
```

### 示例 3: 测试火山引擎

```bash
# 1. 测试连接
python quick_test.py \
  https://open.bigmodel.cn/api/paas/v4/ \
  your-zhipu-api-key \
  glm-4

# 2. 完整测试
python test_llm_connection.py --custom \
  zhipu \
  your-zhipu-api-key \
  https://open.bigmodel.cn/api/paas/v4/ \
  glm-4
```

---

## 🛠️ 调试技巧

### 1. 查看详细日志

修改日志级别：
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 2. 测试 API 端点

使用 `curl` 测试 API：
```bash
# 列出模型
curl http://localhost:8000/v1/models

# 发送请求
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama-3-8b",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 10
  }'
```

### 3. 使用 Python 直接测试

```python
import httpx

async def test_api():
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/v1/models")
        print(response.json())

asyncio.run(test_api())
```

---

## 📝 配置文件示例

### 使用本地 vLLM

```json
{
  "providers": {
    "copilot_priority": false,
    "vllm": {
      "api_base": "http://localhost:8000/v1",
      "api_key": "dummy"
    }
  },
  "agents": {
    "defaults": {
      "model": "llama-3-8b",
      "max_tokens": 8192,
      "temperature": 0.7
    }
  }
}
```

### 使用远程 vLLM

```json
{
  "providers": {
    "copilot_priority": false,
    "vllm": {
      "api_base": "http://10.104.6.197:38099/v1",
      "api_key": "your-secret-key"
    }
  },
  "agents": {
    "defaults": {
      "model": "llama-3-8b"
    }
  }
}
```

### 使用火山引擎

```json
{
  "providers": {
    "copilot_priority": false,
    "zhipu": {
      "api_key": "your-zhipu-api-key",
      "api_base": "https://open.bigmodel.cn/api/paas/v4/"
    }
  },
  "agents": {
    "defaults": {
      "model": "glm-4"
    }
  }
}
```

---

## ✅ 验证成功的标志

### 1. 快速测试成功
```
✅ 连接成功！
响应: Hello! Connection successful.
```

### 2. 完整测试成功
```
✅ 调用成功！

📝 模型响应:
──────────────────────────────────────────
你好！我是 solopreneur，一个 AI 助手。
──────────────────────────────────────────
```

### 3. 诊断无问题
```
✅ 找到配置文件
✅ 配置文件加载成功
✅ 配置的 Provider 已识别
```

---

## 🆘 获取帮助

如果问题仍未解决：

1. 查看日志文件
2. 运行诊断脚本
3. 检查网络连接
4. 确认服务器状态

常见日志位置：
- 服务日志: `logs/solopreneur.log`
- 控制台输出: 启动服务的终端
