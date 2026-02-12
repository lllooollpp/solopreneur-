---
name: testing
description: "测试策略与自动化测试。当需要制定测试计划、编写单元/集成/E2E 测试、分析测试覆盖率、设计测试用例时使用此技能。"
metadata: {"nanobot":{"emoji":"🧪","always":false}}
---

# 测试技能

## ⚠️ 重要：检测现有测试

**在开始编写测试前，必须先检查项目是否已有测试文件！**

### 步骤 1：检测现有测试结构
1. 使用 `list_dir` 查看项目目录，检查是否存在：
   - `tests/` 目录
   - `test_*.py` 或 `*_test.py` 文件
   - `__tests__/` 目录（JavaScript/TypeScript）
   - `*.spec.ts` 或 `*.test.ts` 文件

2. 使用 `read_file` 读取现有测试文件，了解：
   - 使用的测试框架（pytest、unittest、vitest、jest 等）
   - 测试命名规范和风格
   - 已覆盖的测试场景

### 步骤 2：增量补充策略
- ✅ **保留现有测试**：不要删除或覆盖已有测试
- ✅ **补充缺失测试**：仅添加未覆盖的测试场景
- ✅ **保持风格一致**：新测试应与现有测试保持相同的框架和风格
- ✅ **合并而非替换**：如需更新测试，应在现有基础上扩展

### 步骤 3：按需生成
根据检测结果：
- 如果项目无测试 → 创建完整测试结构
- 如果项目有部分测试 → 仅补充缺失的测试场景
- 如果用户指定更新 → 读取现有测试后增量修改

## 测试策略制定

### 测试金字塔
```
        /  E2E  \          10% - 完整业务流
       /  集成测试  \        20% - 模块间交互
      /  单元测试     \      70% - 函数/类级别
```

### 选择测试类型

| 场景 | 推荐测试类型 |
|------|-------------|
| 纯函数/工具函数 | 单元测试 |
| 数据库操作 | 集成测试 (用 testcontainers 或 SQLite) |
| API 端点 | 集成测试 (用 TestClient) |
| 多服务协作 | E2E 测试 |
| 用户交互流程 | E2E 测试 |

## Python 测试 (pytest)

### 基本结构
```python
import pytest

class TestUserService:
    """用户服务测试"""

    def test_create_user_success(self):
        """正常创建用户"""
        # Arrange
        service = UserService()
        data = {"name": "Alice", "email": "alice@example.com"}

        # Act
        user = service.create(data)

        # Assert
        assert user.name == "Alice"
        assert user.email == "alice@example.com"
        assert user.id is not None

    def test_create_user_duplicate_email(self):
        """重复邮箱应抛异常"""
        service = UserService()
        service.create({"name": "A", "email": "a@b.com"})

        with pytest.raises(DuplicateError, match="email already exists"):
            service.create({"name": "B", "email": "a@b.com"})
```

### 常用 Fixtures
```python
@pytest.fixture
def temp_workspace(tmp_path):
    """创建临时工作空间"""
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws

@pytest.fixture
def mock_provider():
    """Mock LLM Provider"""
    from unittest.mock import AsyncMock
    provider = AsyncMock()
    provider.chat.return_value = MockResponse(content="test")
    return provider

@pytest.fixture
async def client(app):
    """FastAPI 测试客户端"""
    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

### 参数化测试
```python
@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
    ("", ""),
    ("123", "123"),
])
def test_to_upper(input, expected):
    assert to_upper(input) == expected
```

### 异步测试
```python
@pytest.mark.asyncio
async def test_async_operation():
    result = await some_async_function()
    assert result == expected
```

## 测试用例设计

### 等价类划分
```
有效输入:
  - 正常值: "hello@example.com"
  - 边界值: "a@b.co" (最短有效)

无效输入:
  - 空字符串: ""
  - 无 @: "hello"
  - 无域名: "hello@"
  - 特殊字符: "hello@exa!mple.com"
```

### 测试命名规范
```
test_[被测方法]_[场景]_[预期结果]

示例:
test_login_valid_credentials_returns_token
test_login_wrong_password_returns_401
test_login_locked_account_returns_403
test_login_empty_password_raises_validation_error
```

## 测试覆盖率

运行覆盖率:
```bash
pytest --cov=nanobot --cov-report=term-missing
pytest --cov=nanobot --cov-report=html  # HTML 报告
```

覆盖率目标:
- **核心业务逻辑**: > 90%
- **工具/辅助函数**: > 80%
- **API 层**: > 70%
- **总体**: > 80%

## 运行测试

```bash
# 运行所有测试
pytest

# 运行特定文件
pytest tests/test_agent_loop.py

# 运行特定测试
pytest tests/test_agent_loop.py::TestAgentLoop::test_process_message

# 显示详细输出
pytest -v

# 失败时停止
pytest -x

# 只运行上次失败的
pytest --lf
```
