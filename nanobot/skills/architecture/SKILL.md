---
name: architecture
description: "软件架构设计。当需要设计系统架构、技术选型、API 设计、数据建模、绘制架构图时使用此技能。"
metadata: {"nanobot":{"emoji":"🏗️","always":false}}
---

# 架构设计技能

## 设计文档模板

```markdown
# [系统名称] 架构设计文档

## 1. 架构概览
[文字描述 + Mermaid 组件图]

## 2. 技术选型
| 领域 | 选型 | 理由 | 替代方案 |
|------|------|------|---------|
| 语言 | Python 3.11+ | ... | Go, Node.js |

## 3. 模块设计
### 模块A
- 职责:
- 接口:
- 依赖:

## 4. API 设计
### POST /api/v1/resource
- Request Body: { ... }
- Response 200: { ... }
- Response 400: { ... }

## 5. 数据模型
[ER 图 / 字段定义]

## 6. 部署架构
[部署拓扑图]

## 7. 技术风险
| 风险 | 影响 | 缓解措施 |
|------|------|---------|
```

## 架构图 (Mermaid 语法)

### 分层架构
```
graph TB
    UI[前端层] --> API[API 网关]
    API --> BIZ[业务逻辑层]
    BIZ --> DAL[数据访问层]
    DAL --> DB[(数据库)]
```

### 微服务架构
```
graph LR
    GW[API Gateway] --> S1[用户服务]
    GW --> S2[订单服务]
    GW --> S3[支付服务]
    S1 --> DB1[(UserDB)]
    S2 --> DB2[(OrderDB)]
    S2 --> MQ[消息队列]
    MQ --> S3
```

### 序列图
```
sequenceDiagram
    Client->>API: POST /login
    API->>AuthService: validate(credentials)
    AuthService->>DB: query user
    DB-->>AuthService: user record
    AuthService-->>API: JWT token
    API-->>Client: 200 { token }
```

## API 设计规范

### RESTful 约定
- `GET /resources` - 列表
- `POST /resources` - 创建
- `GET /resources/{id}` - 详情
- `PUT /resources/{id}` - 全量更新
- `PATCH /resources/{id}` - 部分更新
- `DELETE /resources/{id}` - 删除

### 响应格式
```json
{
  "code": 0,
  "message": "success",
  "data": { ... },
  "meta": { "page": 1, "total": 100 }
}
```

### 错误响应
```json
{
  "code": 40001,
  "message": "参数校验失败",
  "details": [
    { "field": "email", "message": "格式不正确" }
  ]
}
```

## 设计原则速查

| 原则 | 含义 | 应用场景 |
|------|------|---------|
| SRP | 单一职责 | 每个模块/类只做一件事 |
| OCP | 开闭原则 | 扩展开放，修改关闭 |
| DIP | 依赖倒置 | 依赖抽象不依赖具体 |
| ISP | 接口隔离 | 细粒度接口 |
| LSP | 里氏替换 | 子类可替换父类 |

## 读取现有代码

**分析项目架构时，必须先检测现有结构！**

### 步骤 1：检测现有架构文档
1. 使用 `list_dir` 查看项目目录，检查是否存在：
   - `docs/` / `wiki/` 目录
   - `ARCHITECTURE.md` / `architecture.md`
   - `design/` 目录

2. 使用 `read_file` 读取现有架构文档，了解：
   - 已有的架构设计
   - 文档风格和格式
   - 已覆盖的模块

### 步骤 2：增量更新策略
- ✅ **保留现有文档**：不要删除或覆盖已有架构文档
- ✅ **补充缺失内容**：仅添加未覆盖的模块设计
- ✅ **保持风格一致**：新文档应与现有文档保持相同格式
- ✅ **合并而非替换**：如需更新，应在现有基础上扩展

### 步骤 3：代码分析
分析现有代码结构:
1. `list_dir` 了解目录结构
2. `read_file` 读取 `pyproject.toml` / `package.json` 了解依赖
3. `read_file` 读取入口文件和配置
4. `exec` 运行 `find . -name "*.py" | head -50` 了解代码规模
