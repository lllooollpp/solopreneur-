---
name: code-review
description: "代码审查与质量评估。当需要审查代码变更、检查代码质量、发现 Bug 和安全漏洞、评估代码可维护性时使用此技能。"
metadata: {"solopreneur":{"emoji":"🔍","always":false}}
---

# 代码审查技能

## 审查流程

1. **通读变更** - `read_file` 阅读所有相关文件
2. **理解意图** - 这段代码要解决什么问题
3. **逐项检查** - 按审查清单逐一检查
4. **输出报告** - 按严重程度分类报告

## 审查清单

### 🔴 严重 (Blocker)
- [ ] SQL 注入 / XSS / CSRF
- [ ] 硬编码密码或密钥
- [ ] 未授权的数据访问
- [ ] 空指针 / 未处理的异常导致崩溃
- [ ] 死锁 / 竞态条件
- [ ] 数据丢失风险
- [ ] 无限循环 / 递归

### 🟡 重要 (Major)
- [ ] 缺少输入验证
- [ ] 过宽的异常捕获 (`except Exception`)
- [ ] 资源泄漏（未关闭的文件/连接）
- [ ] N+1 查询问题
- [ ] 缺少事务控制
- [ ] 不安全的反序列化
- [ ] 日志中泄露敏感信息

### 🟢 建议 (Minor)
- [ ] 命名不清晰
- [ ] 重复代码可提取
- [ ] 缺少类型标注
- [ ] 魔法数字（应提取为常量）
- [ ] 注释过时或缺失
- [ ] 函数过长（>50行）
- [ ] 参数过多（>5个）

## 审查报告模板

```markdown
# 代码审查报告

## 总体评价: [A/B/C/D]

[一句话总结]

## 🔴 严重问题 (X 个)

### Issue-1: [标题]
- **文件**: `path/to/file.py:42`
- **问题**: [描述]
- **建议**: [修改方案]
```python
# 修改前
...
# 修改后
...
```

## 🟡 重要问题 (X 个)
...

## 🟢 改进建议 (X 个)
...

## ✨ 亮点
- [好的做法1]
- [好的做法2]

## 安全审查
- [ ] 无 SQL 注入风险
- [ ] 无 XSS 风险
- [ ] 无硬编码敏感信息
- [ ] 认证/授权正确
```

## 评分标准

| 等级 | 标准 |
|------|------|
| A | 无严重/重要问题，代码质量优秀 |
| B | 无严重问题，少量重要问题 |
| C | 有多个重要问题需要修改 |
| D | 有严重问题，需要重写 |

## Python 常见问题速查

```python
# ❌ 可变默认参数
def bad(items=[]):
    items.append(1)

# ✅ 正确方式
def good(items=None):
    items = items or []

# ❌ 过宽异常
try: do_something()
except: pass

# ✅ 精确捕获
try: do_something()
except ValueError as e:
    logger.error(f"Invalid value: {e}")

# ❌ 字符串拼接构建 SQL
query = f"SELECT * FROM users WHERE name = '{name}'"

# ✅ 参数化查询
query = "SELECT * FROM users WHERE name = %s"
cursor.execute(query, (name,))
```
