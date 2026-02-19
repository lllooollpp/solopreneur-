# API 接口规范

## 基础信息

- **Base URL**: `http://localhost:18790`
- **认证方式**: 无（本地开发）/ Bearer Token（生产环境）

---

## 项目管理 API

### 创建项目

**POST /api/projects**

请求体：
```json
{
  "name": "用户权限系统",
  "description": "基于 RBAC 的权限管理系统",
  "source": "local",
  "local_path": "D:\\projects\\rbac",
  "env_vars": [
    {
      "key": "DB_HOST",
      "value": "192.168.1.100",
      "category": "database",
      "description": "MySQL 主库地址"
    },
    {
      "key": "DB_PORT",
      "value": "3306",
      "category": "database"
    },
    {
      "key": "DB_NAME",
      "value": "rbac_db",
      "category": "database"
    },
    {
      "key": "REDIS_URL",
      "value": "redis://192.168.1.101:6379",
      "category": "middleware",
      "description": "Redis 缓存"
    },
    {
      "key": "NEXUS_URL",
      "value": "https://nexus.company.com",
      "category": "registry",
      "description": "私服地址"
    },
    {
      "key": "DB_PASSWORD",
      "value": "secret123",
      "category": "credential",
      "sensitive": true
    }
  ]
}
```

响应：
```json
{
  "success": true,
  "project": {
    "id": "proj_abc123",
    "name": "用户权限系统",
    "path": "D:\\projects\\rbac",
    "env_vars": [...],
    "status": "active",
    "created_at": "2026-02-15T10:00:00"
  }
}
```

### 获取项目环境变量

**GET /api/projects/{project_id}/env**

响应：
```json
{
  "project_id": "proj_abc123",
  "project_name": "用户权限系统",
  "total": 6,
  "env_vars": [
    {
      "key": "DB_HOST",
      "value": "192.168.1.100",
      "category": "database",
      "description": "MySQL 主库地址",
      "sensitive": false
    },
    {
      "key": "DB_PASSWORD",
      "value": "******",
      "category": "credential",
      "description": "",
      "sensitive": true
    }
  ]
}
```

### 更新项目环境变量

**PUT /api/projects/{project_id}/env**

请求体：
```json
{
  "env_vars": [
    {
      "key": "DB_HOST",
      "value": "192.168.1.200",
      "category": "database",
      "description": "MySQL 主库地址（已迁移）"
    },
    {
      "key": "NEW_VAR",
      "value": "new_value",
      "category": "general"
    }
  ]
}
```

响应：
```json
{
  "success": true,
  "project_id": "proj_abc123",
  "total": 7,
  "message": "Updated env vars in project '用户权限系统'"
}
```

---

## Agent API

### 发送消息

**POST /api/v1/chat**

请求体：
```json
{
  "message": "帮我创建一个用户登录接口",
  "project_id": "proj_abc123",
  "session_id": "session_xyz"
}
```

响应（流式）：
```json
{"type": "chunk", "content": "我将为你创建用户登录接口..."}
{"type": "trace", "event": "tool_start", "tool": "get_project_env"}
{"type": "trace", "event": "tool_end", "result": "获取到项目配置..."}
{"type": "chunk", "content": "根据项目配置，数据库地址是 192.168.1.100..."}
{"type": "done"}
```

### WebSocket 聊天

**WS /ws/chat**

连接后发送：
```json
{
  "type": "message",
  "content": "帮我创建用户注册接口",
  "project_id": "proj_abc123"
}
```

接收事件：
```json
{"type": "chunk", "content": "..."}
{"type": "activity", "action": "reading_file", "detail": "main.py"}
{"type": "trace", "event": "llm_start"}
{"type": "trace", "event": "tool_start", "tool": "write_file"}
{"type": "done", "tokens": {"input": 2500, "output": 1800}}
```

---

## 环境变量分类

| 分类 | 值 | 说明 | 示例变量 |
|------|-----|------|---------|
| `database` | database | 数据库连接 | DB_HOST, DATABASE_URL |
| `registry` | registry | 私服/镜像源 | NEXUS_URL, NPM_REGISTRY |
| `server` | server | 业务服务地址 | API_BASE, GATEWAY_URL |
| `middleware` | middleware | 中间件 | REDIS_URL, RABBITMQ_HOST |
| `credential` | credential | 敏感凭证 | DB_PASSWORD, API_SECRET |
| `general` | general | 通用配置 | APP_ENV, LOG_LEVEL |

---

## 工具调用 API

### get_project_env

Agent 可通过工具获取项目环境变量：

```json
{
  "tool": "get_project_env",
  "arguments": {
    "key": "DB_HOST"  // 可选，不传则返回全部
  }
}
```

响应：
```json
{
  "project_id": "proj_abc123",
  "project_name": "用户权限系统",
  "total": 6,
  "env_vars": [...]
}
```

### set_project_env

Agent 可通过工具设置项目环境变量：

```json
{
  "tool": "set_project_env",
  "arguments": {
    "env_vars": [
      {
        "key": "NEW_CONFIG",
        "value": "value",
        "category": "general",
        "description": "新配置项"
      }
    ]
  }
}
```

---

## 认证接口（示例）

**POST /api/auth/login**

请求体：
```json
{
  "username": "admin",
  "password": "secret"
}
```

响应：
```json
{
  "code": 0,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expiresIn": 3600
  }
}
```

---

## 错误响应

所有 API 错误返回统一格式：

```json
{
  "detail": "错误描述信息"
}
```

HTTP 状态码：
- `400` - 请求参数错误
- `404` - 资源不存在
- `500` - 服务器内部错误
