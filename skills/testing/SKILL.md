---
name: testing
description: "测试策略与自动化测试。当需要制定测试计划、编写单元/集成/E2E 测试、分析测试覆盖率、设计测试用例时使用此技能。"
metadata: {"solopreneur":{"emoji":"🧪","always":false}}
---

# 测试技能

## ⚠️ 会话启动时的重要流程

**每次新会话开始时，你应该先运行当前项目的测试，验证上次改动没有破坏现有功能！**

### 为什么要在会话开始时运行测试？
1. **确认项目状态**：确保代码库处于可工作状态
2. **快速发现问题**：如果测试失败，优先修复再继续开发
3. **建立信心**：在已有功能验证通过的基础上进行增量开发

### 会话启动测试流程
```bash
# 1. 检测项目类型和测试框架
ls -la                    # 查看项目结构
cat package.json          # JavaScript 项目
cat pyproject.toml        # Python 项目
cat Makefile              # 可能有 test 命令

# 2. 运行测试
npm test                  # Node.js 项目
pytest                    # Python 项目
make test                 # 使用 Makefile

# 3. 如果测试失败
# - 分析失败原因
# - 优先修复失败的测试
# - 修复后再继续新的开发工作
```

---

## ⚠️ 重要：检测现有测试

**在开始编写测试前，必须先检查项目是否已有测试文件！**

### 步骤 1：检测现有测试结构
1. 使用 `list_dir` 查看项目目录，检查是否存在：
   - `tests/` 目录
   - `test_*.py` 或 `*_test.py` 文件
   - `__tests__/` 目录（JavaScript/TypeScript）
   - `*.spec.ts` 或 `*.test.ts` 文件
   - `e2e/` 或 `playwright.config.ts`（E2E 测试）

2. 使用 `read_file` 读取现有测试文件，了解：
   - 使用的测试框架（pytest、unittest、vitest、jest、playwright 等）
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

---

## 测试策略制定

### 测试金字塔
```
        /  E2E  \          10% - 完整业务流（浏览器自动化）
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
| 用户交互流程 | E2E 测试（Playwright） |
| 前端组件 | E2E 测试（Playwright） |

---

## E2E 测试（Playwright）

### 为什么使用 Playwright？
- 跨浏览器支持（Chromium、Firefox、WebKit）
- 自动等待、重试机制
- 强大的选择器和断言
- 支持 TypeScript/JavaScript/Python

### 安装配置
```bash
# 安装 Playwright（在前端目录执行）
npm install @playwright/test --save-dev

# 安装 Chromium 浏览器（必须！否则测试无法运行）
npx playwright install chromium
# 或安装全部浏览器
# npx playwright install

# 验证安装是否成功
npx playwright --version
```

### Playwright 配置文件
```typescript
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
  },
});
```

### 基础测试用例
```typescript
// e2e/chat.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Chat 功能', () => {
  test('发送消息后应收到 AI 回复', async ({ page }) => {
    await page.goto('/');
    
    // 等待页面加载
    await expect(page.locator('.chat-container')).toBeVisible();
    
    // 输入消息
    await page.fill('textarea[placeholder*="消息"]', '你好');
    await page.click('button:has-text("发送")');
    
    // 等待 AI 回复
    await expect(page.locator('.message.assistant').last()).toBeVisible({ timeout: 30000 });
    
    // 验证回复内容
    const response = await page.locator('.message.assistant').last().textContent();
    expect(response).toBeTruthy();
    expect(response!.length).toBeGreaterThan(0);
  });

  test('流式响应应逐字显示', async ({ page }) => {
    await page.goto('/');
    
    await page.fill('textarea', '请写一首短诗');
    await page.click('button:has-text("发送")');
    
    // 验证流式效果：内容逐渐增加
    let previousLength = 0;
    for (let i = 0; i < 5; i++) {
      await page.waitForTimeout(500);
      const currentContent = await page.locator('.message.assistant').last().textContent();
      const currentLength = currentContent?.length || 0;
      
      // 内容应该增加或保持（流式输出中）
      expect(currentLength).toBeGreaterThanOrEqual(previousLength);
      previousLength = currentLength;
    }
  });
});
```

### Python Playwright 测试
```python
# e2e/test_chat.py
import pytest
from playwright.sync_api import Page, expect

def test_send_message(page: Page):
    """发送消息后应收到 AI 回复"""
    page.goto("http://localhost:5173")
    
    # 等待页面加载
    expect(page.locator(".chat-container")).to_be_visible()
    
    # 输入消息
    page.fill('textarea[placeholder*="消息"]', "你好")
    page.click('button:has-text("发送")')
    
    # 等待 AI 回复
    expect(page.locator(".message.assistant").last).to_be_visible(timeout=30000)
    
    # 验证回复内容
    response = page.locator(".message.assistant").last.text_content()
    assert response is not None
    assert len(response) > 0
```

### 运行 E2E 测试前的检查清单

在运行 E2E 测试之前，确保：

1. **`@playwright/test` 已在 `package.json`** - 否则先运行 `npm install @playwright/test --save-dev`
2. **Chromium 浏览器已安装** - 运行 `npx playwright install chromium`
3. **`e2e/` 目录存在且有测试文件** - 如不存在，需先创建测试文件
4. **不要手动启动 dev server** - `playwright.config.ts` 的 `webServer` 配置会自动处理

> ⚠️ 注意：`npm run dev`、`vite`、`yarn dev` 等命令被 exec 工具屏蔽（会永久挂起）。
> Playwright 的 `webServer` 在内部管理 dev server，**直接运行 `npx playwright test` 即可**。

### 运行 E2E 测试
```bash
# 运行所有 E2E 测试
npx playwright test

# 运行特定文件
npx playwright test e2e/chat.spec.ts

# 有界面模式（调试用）
npx playwright test --ui

# 生成测试报告
npx playwright show-report
```

### 功能完成前的 E2E 验证
**在标记功能完成前，应该运行 E2E 测试验证功能确实可用！**

```bash
# 1. 确保服务运行
npm run dev &
python start.py &

# 2. 运行 E2E 测试
npx playwright test --project=chromium

# 3. 如果测试失败，修复问题后重新测试

# 4. 测试通过后再标记功能完成
```

---

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

---

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

---

## 测试覆盖率

运行覆盖率:
```bash
pytest --cov=solopreneur --cov-report=term-missing
pytest --cov=solopreneur --cov-report=html  # HTML 报告
```

覆盖率目标:
- **核心业务逻辑**: > 90%
- **工具/辅助函数**: > 80%
- **API 层**: > 70%
- **总体**: > 80%

---

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

---

## 功能完成检查清单

在标记功能完成前，请确认：

- [ ] 单元测试已编写并通过
- [ ] 集成测试已编写并通过（如适用）
- [ ] E2E 测试已编写并通过（前端功能）
- [ ] 测试覆盖率达标
- [ ] 本地运行 `npm test` 或 `pytest` 全部通过
- [ ] E2E 测试 `npx playwright test` 全部通过
