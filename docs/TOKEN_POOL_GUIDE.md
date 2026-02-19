p# 账号池 Token 控制配置指南

## 概述

solopreneur 支持多账号池（Token Pool），你可以为每个账号配置独立的 Token 使用限制，实现精细化的资源控制和成本管理。

---

## 功能特性

- **多账号负载均衡**：Round-Robin 轮询调度
- **独立 Token 限制**：每个账号可配置不同的限制
- **使用统计追踪**：实时监控每个账号的 Token 消耗
- **自动冷却机制**：触发 429 后自动冷却，避免账号被封
- **持久化存储**：账号配置和使用统计自动保存

---

## API 接口

### 1. 设置账号 Token 限制

```bash
PUT /api/auth/pool/{slot_id}/limits
```

**请求参数**：
```json
{
  "max_tokens_per_day": 100000,
  "max_requests_per_day": 1000,
  "max_requests_per_hour": 100
}
```

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `max_tokens_per_day` | int | 每日最大 Token 数 | 0 (无限制) |
| `max_requests_per_day` | int | 每日最大请求次数 | 0 (无限制) |
| `max_requests_per_hour` | int | 每小时最大请求次数 | 0 (无限制) |

**示例**：
```bash
curl -X PUT http://localhost:8000/api/auth/pool/1/limits \
  -H "Content-Type: application/json" \
  -d '{
    "max_tokens_per_day": 200000,
    "max_requests_per_day": 500,
    "max_requests_per_hour": 50
  }'
```

**响应**：
```json
{
  "success": true,
  "message": "Slot 1 的 Token 限制已更新",
  "limits": {
    "max_tokens_per_day": 200000,
    "max_requests_per_day": 500,
    "max_requests_per_hour": 50
  }
}
```

---

### 2. 查看账号使用统计

```bash
GET /api/auth/pool/{slot_id}/usage
```

**示例**：
```bash
curl http://localhost:8000/api/auth/pool/1/usage
```

**响应**：
```json
{
  "slot_id": 1,
  "label": "主账号",
  "state": "active",
  "usage": {
    "tokens_used_today": 15234,
    "requests_today": 45,
    "requests_hour": 8,
    "tokens_limit": 200000,
    "requests_day_limit": 500,
    "requests_hour_limit": 50
  }
}
```

---

### 3. 查看所有账号状态

```bash
GET /api/auth/pool/status
```

**响应**：
```json
{
  "authenticated": true,
  "slots": [
    {
      "slot_id": 1,
      "label": "主账号",
      "state": "active",
      "cooling_remaining": "",
      "total_requests": 234,
      "total_429s": 2,
      "token_expires": "2024-02-11T10:30:00",
      "limits": {
        "max_tokens_per_day": 200000,
        "max_requests_per_day": 500,
        "max_requests_per_hour": 50
      },
      "usage": {
        "tokens_used_today": 15234,
        "requests_today": 45,
        "requests_hour": 8,
        "tokens_limit": 200000,
        "requests_day_limit": 500,
        "requests_hour_limit": 50
      }
    },
    {
      "slot_id": 2,
      "label": "备用账号",
      "state": "cooling",
      "cooling_remaining": "120s",
      "total_requests": 156,
      "total_429s": 5,
      "token_expires": "2024-02-12T08:00:00",
      "limits": {
        "max_tokens_per_day": "无限制",
        "max_requests_per_day": "无限制",
        "max_requests_per_hour": "无限制"
      },
      "usage": {
        "tokens_used_today": 0,
        "requests_today": 0,
        "requests_hour": 0,
        "tokens_limit": "无限制",
        "requests_day_limit": "无限制",
        "requests_hour_limit": "无限制"
      }
    }
  ],
  "active_count": 1,
  "total_count": 2
}
```

---

### 4. 重置账号使用统计

```bash
POST /api/auth/pool/{slot_id}/reset-usage
```

**示例**：
```bash
curl -X POST http://localhost:8000/api/auth/pool/1/reset-usage
```

**响应**：
```json
{
  "success": true,
  "message": "Slot 1 的使用统计已重置"
}
```

---

## 配置场景示例

### 场景 1：多账号成本控制

为每个账号设置不同的 Token 额度，控制整体成本：

```json
{
  "账号1（生产）": {
    "max_tokens_per_day": 500000,
    "max_requests_per_day": 1000,
    "max_requests_per_hour": 100
  },
  "账号2（开发）": {
    "max_tokens_per_day": 100000,
    "max_requests_per_day": 500,
    "max_requests_per_hour": 50
  },
  "账号3（测试）": {
    "max_tokens_per_day": 50000,
    "max_requests_per_day": 200,
    "max_requests_per_hour": 20
  }
}
```

**实现方式**：
```bash
# 设置账号 1（生产）
curl -X PUT http://localhost:8000/api/auth/pool/1/limits \
  -d '{"max_tokens_per_day": 500000, "max_requests_per_day": 1000, "max_requests_per_hour": 100}'

# 设置账号 2（开发）
curl -X PUT http://localhost:8000/api/auth/pool/2/limits \
  -d '{"max_tokens_per_day": 100000, "max_requests_per_day": 500, "max_requests_per_hour": 50}'

# 设置账号 3（测试）
curl -X PUT http://localhost:8000/api/auth/pool/3/limits \
  -d '{"max_tokens_per_day": 50000, "max_requests_per_day": 200, "max_requests_per_hour": 20}'
```

---

### 场景 2：防止账号被限流

通过 `max_requests_per_hour` 限制每个账号的请求频率：

```json
{
  "max_requests_per_hour": 60,
  "max_requests_per_day": 500
}
```

这样可以确保：
- 每分钟最多 1 个请求
- 避免触发 GitHub Copilot 的速率限制
- 即使多账号轮询，也不会过度消耗

---

### 场景 3：按使用量分级

根据账号级别设置不同的额度：

| 级别 | 每日 Token | 每日请求 | 每小时请求 |
|--------|------------|-----------|-----------|
| 基础账号 | 50,000 | 100 | 10 |
| 标准账号 | 200,000 | 500 | 50 |
| 高级账号 | 1,000,000 | 2000 | 200 |

---

## 监控和告警

### 查看实时使用情况

```bash
# 查看所有账号
curl http://localhost:8000/api/auth/pool/status

# 查看特定账号
curl http://localhost:8000/api/auth/pool/1/usage
```

### 使用率计算

```javascript
// 计算账号 1 的 Token 使用率
const usage = {
  tokens_used_today: 15234,
  tokens_limit: 200000
};

const usage_rate = (usage.tokens_used_today / usage.tokens_limit * 100).toFixed(2);
console.log(`Token 使用率: ${usage_rate}%`);
// 输出: Token 使用率: 7.62%
```

---

## Token 跟踪机制

### 自动记录

系统会自动记录每次 API 调用的 Token 消耗，包括：

1. **输入 Token**：提示词 + 上下文
2. **输出 Token**：模型响应
3. **总 Token**：输入 + 输出

### 计数器重置

- **每日重置**：`tokens_used_today`、`requests_today` 在每天 00:00 自动重置
- **每小时重置**：`requests_hour` 在每小时开始时自动重置

### 历史记录

每个账号保留最近 7 天的 Token 使用历史：

```json
{
  "tokens_used_history": [
    {"timestamp": "2024-02-10T08:30:00", "tokens": 2500},
    {"timestamp": "2024-02-10T09:15:00", "tokens": 1800},
    {"timestamp": "2024-02-10T10:00:00", "tokens": 3200}
  ]
}
```

---

## 故障排查

### 问题 1：账号被跳过

**现象**：日志显示某个账号被跳过

```
[TokenPool] Slot 2 跳过: 达到每小时请求限制 (60/60)
```

**解决方案**：
1. 等待下一小时自动重置
2. 或手动重置使用统计：
   ```bash
   curl -X POST http://localhost:8000/api/auth/pool/2/reset-usage
   ```
3. 或调整限制配置：
   ```bash
   curl -X PUT http://localhost:8000/api/auth/pool/2/limits \
     -d '{"max_requests_per_hour": 100}'
   ```

---

### 问题 2：所有账号都不可用

**现象**：`active_count: 0`

**原因**：
1. 所有账号都触发 429 冷却中
2. 所有账号都达到自定义限制

**解决方案**：
1. 检查冷却状态：`GET /api/auth/pool/status`
2. 等待冷却结束
3. 添加更多账号分担负载

---

### 问题 3：Token 统计不准确

**现象**：`tokens_used_today` 与实际不符

**可能原因**：
1. API 返回的 Token 数统计不包含系统提示词
2. 部分请求未正确记录

**解决方案**：
1. 手动重置统计：`POST /api/auth/pool/{slot_id}/reset-usage`
2. 检查日志确认 Token 统计是否正常记录

---

## 最佳实践

### 1. 合理分配额度

根据实际使用量和预算分配：
- **生产环境**：预留 20% 缓冲空间
- **开发环境**：限制较低，避免过度消耗
- **测试环境**：使用最小额度

### 2. 监控使用趋势

定期查看使用统计，调整限制：
```bash
# 每日检查
curl http://localhost:8000/api/auth/pool/status
```

### 3. 设置告警

建议设置 80% 使用率告警：
```javascript
if (usage.tokens_used_today / usage.tokens_limit > 0.8) {
  sendAlert(`账号 ${slot_id} Token 使用率超过 80%`);
}
```

### 4. 多账号负载均衡

添加多个账号并设置不同限制：
- 高频请求：使用限制较高的账号
- 低频请求：使用限制较低的账号
- 备用账号：仅在其他账号冷却时使用

---

## 配置文件示例

虽然账号池主要通过 API 管理，但你可以在配置文件中设置默认限制：

```json
{
  "providers": {
    "token_pool": {
      "default_limits": {
        "max_tokens_per_day": 100000,
        "max_requests_per_day": 500,
        "max_requests_per_hour": 50
      },
      "slots": {
        "1": {
          "label": "主账号",
          "max_tokens_per_day": 200000
        },
        "2": {
          "label": "备用账号",
          "max_tokens_per_day": 50000
        }
      }
    }
  }
}
```

---

## 总结

通过账号池 Token 控制，你可以：

1. ✅ 精确控制每个账号的 Token 消耗
2. ✅ 实现成本管理和预算控制
3. ✅ 避免账号触发速率限制
4. ✅ 监控使用情况，优化资源配置
5. ✅ 多账号负载均衡，提高可用性

开始使用：
```bash
# 1. 添加账号
curl -X POST http://localhost:8000/api/auth/pool/login -d '{"label": "生产账号"}'

# 2. 设置限制
curl -X PUT http://localhost:8000/api/auth/pool/1/limits \
  -d '{"max_tokens_per_day": 500000}'

# 3. 监控使用
curl http://localhost:8000/api/auth/pool/1/usage
```
