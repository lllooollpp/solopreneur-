---
name: devops
description: "DevOps 与部署运维。当需要创建 CI/CD 流水线、编写 Dockerfile、配置 docker-compose、编写部署脚本、设置监控告警时使用此技能。"
metadata: {"nanobot":{"emoji":"🚀","always":false}}
---

# DevOps 技能

## CI/CD (GitHub Actions)

### 基础 CI 流水线
```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install ruff
      - run: ruff check .
      - run: ruff format --check .

  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: ${{ matrix.python-version }} }
      - run: pip install -e ".[dev]"
      - run: pytest --cov --cov-report=xml
      - uses: codecov/codecov-action@v4

  build:
    needs: [lint, test]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/build-push-action@v5
        with:
          push: false
          tags: app:${{ github.sha }}
```

### Release 流水线
```yaml
name: Release
on:
  push:
    tags: ["v*"]

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v5
        with:
          push: true
          tags: ghcr.io/${{ github.repository }}:${{ github.ref_name }}
```

## Docker

### 多阶段构建 (Python)
```dockerfile
# Build stage
FROM python:3.11-slim AS builder
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir build && \
    pip install --no-cache-dir -e .

# Runtime stage
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .
USER nobody
HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1
CMD ["python", "-m", "app"]
```

### docker-compose 模板
```yaml
version: "3.8"
services:
  app:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: app
      POSTGRES_USER: app
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 5s
      retries: 5

volumes:
  pgdata:
```

## Makefile 模板

```makefile
.PHONY: dev test lint build deploy

dev:
	python -m nanobot serve

test:
	pytest --cov --cov-report=term-missing

lint:
	ruff check . && ruff format --check .

fix:
	ruff check --fix . && ruff format .

build:
	docker build -t nanobot .

deploy:
	docker compose up -d
```

## 部署检查清单

### 上线前
- [ ] 所有测试通过
- [ ] 代码审查已完成
- [ ] 环境变量已配置
- [ ] 数据库迁移已就绪
- [ ] 回滚方案已准备
- [ ] 监控告警已配置

### 上线后
- [ ] 健康检查通过
- [ ] 日志输出正常
- [ ] 核心功能冒烟测试
- [ ] 性能指标正常
- [ ] 错误率未上升
