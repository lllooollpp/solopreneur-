---
name: config-extract
description: "从已有项目配置中提取环境信息（数据库、私服、服务地址、中间件）并写回项目环境变量。"
metadata: {"nanobot":{"emoji":"🔍","always":false}}
---

# 配置提取技能（Config Extract）

当用户希望“从已有项目提取服务器地址、私服地址、数据库地址等配置”时使用本技能。

## 目标

1. 扫描项目中的配置文件与部署文件
2. 提取可结构化的环境变量（key/value/category/description）
3. 调用 `set_project_env` 工具写回项目级配置
4. 给出提取结果与置信度说明

## 提取规则

### 1) Java / Spring
优先扫描：
- `application.yml`
- `application.yaml`
- `application.properties`
- `bootstrap.yml`
- `bootstrap.yaml`

重点字段：
- `spring.datasource.url/username/password`
- `spring.redis.*`
- `spring.cloud.nacos.*`
- `server.port`

### 2) Node.js / 前端
优先扫描：
- `.env`
- `.env.*`
- `config/*.json`
- `package.json`

重点字段：
- `API_BASE_URL`
- `NPM_REGISTRY`
- `REDIS_URL`
- `DATABASE_URL`

### 3) Python
优先扫描：
- `.env`
- `settings.py`
- `config.py`
- `pyproject.toml`

重点字段：
- `DATABASE_URL`
- `REDIS_URL`
- `API_SERVER`

### 4) Docker / DevOps
优先扫描：
- `docker-compose.yml`
- `Dockerfile`
- `.github/workflows/*.yml`
- `.gitlab-ci.yml`

重点字段：
- 各类 `environment` 段中的地址与账号
- 镜像仓库地址（registry）

## 分类映射

- 数据库相关 → `database`
- 私服/镜像源相关 → `registry`
- 业务服务域名/网关地址 → `server`
- Redis/MQ/Nacos/Consul/ES 等 → `middleware`
- 密码/密钥/Token → `credential`（`sensitive=true`）
- 其他 → `general`

## 执行流程

1. 用 `list_dir` 和 `read_file` 逐步定位并读取配置文件
2. 归一化为结构：

```json
{
  "key": "DB_HOST",
  "value": "10.0.1.10",
  "category": "database",
  "description": "主数据库地址",
  "sensitive": false
}
```

3. 调用 `set_project_env` 批量写入
4. 回报：
   - 新增/更新了多少项
   - 哪些值可能不准确（例如占位符 `${...}`）

## 注意事项

- 若读取到占位符（如 `${DB_HOST}`、`<to-be-filled>`），仍可写入，但需在结果中标记“待人工确认”。
- 对明显敏感信息（password/secret/token）必须 `sensitive=true`。
- 不要修改原始业务代码，只做提取与回填。
