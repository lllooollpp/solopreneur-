# 多 LLM Provider 快速上手

## 配置示例

### 示例 1: 使用本地 vLLM

假设你已经部署了 vLLM 在 `http://localhost:8000`:

```json
{
  "providers": {
    "vllm": {
      "api_key": "dummy",
      "api_base": "http://localhost:8000/v1"
    }
  },
  "agents": {
    "defaults": {
      "model": "meta-llama/Meta-Llama-3-8B-Instruct",
      "max_tokens": 8192,
      "temperature": 0.7
    }
  }
}
```

### 示例 2: 使用火山引擎

```json
{
  "providers": {
    "zhipu": {
      "api_key": "your-zhipu-api-key",
      "api_base": "https://open.bigmodel.cn/api/paas/v4/"
    }
  },
  "agents": {
    "defaults": {
      "model": "glm-4",
      "max_tokens": 8192,
      "temperature": 0.7
    }
  }
}
```

### 示例 3: 使用 OpenAI 官方 API

```json
{
  "providers": {
    "openai": {
      "api_key": "sk-your-openai-api-key",
      "api_base": "https://api.openai.com/v1"
    }
  },
  "agents": {
    "defaults": {
      "model": "gpt-4o-mini",
      "max_tokens": 8192,
      "temperature": 0.7
    }
  }
}
```

## Web UI 配置步骤

1. **启动服务**
   ```bash
   python start.py
   ```

2. **打开浏览器**
   ```
   http://localhost:18790
   ```

3. **进入配置页面**
   - 点击导航栏的 **配置管理**
   - 找到 **🌐 LLM Providers** 区域

4. **选择 Provider**
   - 点击想要配置的 Provider 标签
   - 例如点击 **🏠 本地 OpenAI 标准接口**

5. **填写配置**
   - **API Key**: 填写对应的 API Key（本地接口可填 `dummy`）
   - **API Base**: 填写 API 端点地址
   - **默认模型**: 输入模型名称，或从下拉菜单选择

6. **调整参数** (可选)
   - **Max Tokens**: 设置最大输出 token 数
   - **Temperature**: 调整输出多样性 (0-1)

7. **测试连接**
   - 点击 **🔍 测试连接** 按钮
   - 查看测试结果

8. **保存配置**
   - 点击 **💾 保存配置**
   - 配置会自动热加载

## 验证配置是否生效

在聊天界面发送一条消息，查看响应是否正常：

```
用户: 你好

助手: 你好！有什么我可以帮助你的吗？
```

## 常见本地部署方案

### vLLM

```bash
# 安装 vLLM
pip install vllm

# 启动服务
vllm serve meta-llama/Meta-Llama-3-8B-Instruct \
  --host 0.0.0.0 \
  --port 8000
```

### Ollama

```bash
# 安装 Ollama (macOS)
brew install ollama

# 下载模型
ollama pull llama3

# 启动服务
ollama serve
```

### LM Studio

1. 下载 [LM Studio](https://lmstudio.ai)
2. 在应用中启动服务器
3. 端口默认为 `1234`

配置:
```json
{
  "providers": {
    "vllm": {
      "api_key": "dummy",
      "api_base": "http://localhost:1234/v1"
    }
  },
  "agents": {
    "defaults": {
      "model": "your-model-name"
    }
  }
}
```

## 故障排除

### 问题: 测试连接失败

**检查清单:**
1. API Key 是否正确？
2. API Base 地址是否可访问？
3. 模型名称是否正确？
4. 网络连接是否正常？

### 问题: 配置后没有生效

**解决方法:**
1. 重启服务: `Ctrl+C` 然后 `python start.py`
2. 或使用 Web UI 配置（自动热加载）

### 问题: 本地接口连接超时

**解决方法:**
1. 确认本地服务已启动
2. 检查端口是否正确
3. 检查防火墙设置
