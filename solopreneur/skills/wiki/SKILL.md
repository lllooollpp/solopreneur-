---
name: wiki
description: "项目 Wiki 文档生成与管理。自动生成项目文档、API 文档、架构说明、部署指南等，并支持 Wiki 站点的构建与部署。"
metadata: {"solopreneur":{"emoji":"📚","always":false}}
---

# Wiki 文档生成技能

## 功能概述

本技能用于为软件项目生成完整的 Wiki 文档体系，包括：
- 项目概述与介绍
- 安装与部署指南
- 架构设计文档
- API 文档
- 开发流程与规范
- 贡献指南
- CI/CD 配置参考
- FAQ 常见问题

## 触发条件

当用户提出以下需求时使用此技能：
- "生成项目 Wiki"
- "创建项目文档"
- "生成 API 文档"
- "搭建文档站点"
- "写项目 README"
- "生成部署文档"
- "更新 Wiki"
- "补充文档"

## 现有 Wiki 处理策略

当项目已存在 `docs/` 或 `wiki/` 目录时，应遵循以下原则：

### 1. 检测现有结构
- 首先使用 `list_dir` 查看项目目录结构
- 识别现有的文档目录（docs/、wiki/、documentation/）
- 使用 `read_file` 读取现有文档内容，了解文档风格和格式

### 2. 增量更新原则
- **保留现有内容**：不删除或覆盖已有文档，除非用户明确要求
- **补充缺失文档**：仅创建不存在的文档文件
- **保持风格一致**：新文档应与现有文档保持相同的格式、风格和术语
- **合并而非替换**：如需更新，应在现有内容基础上补充，而非完全重写

### 3. 文档状态识别
在生成新文档前，先检查以下文件是否存在：
```
docs/README.md 或 README.md
docs/getting-started/installation.md
docs/getting-started/quickstart.md
docs/development/architecture.md
docs/deployment/docker.md
...
```
仅创建缺失的文档，或用户明确要求更新的文档。

### 4. 更新模式
- **首次生成**：项目无文档时，按完整结构生成
- **增量补充**：项目有部分文档时，仅补充缺失部分
- **按需更新**：用户指定更新特定文档时，读取现有内容后增量修改

## Wiki 结构规范

```
wiki/
├── README.md              # 首页/项目概述
├── getting-started/       # 入门指南
│   ├── installation.md   # 安装指南
│   ├── quickstart.md     # 快速开始
│   └── configuration.md  # 配置说明
├── development/          # 开发文档
│   ├── architecture.md   # 架构设计
│   ├── api-reference.md  # API 文档
│   ├── code-style.md     # 代码规范
│   └── testing.md        # 测试指南
├── deployment/           # 部署文档
│   ├── docker.md         # Docker 部署
│   ├── kubernetes.md     # K8s 部署
│   └── ci-cd.md          # CI/CD 配置
├── contributing/         # 贡献指南
│   ├── guidelines.md     # 贡献规范
│   └── code-of-conduct.md # 行为准则
└── faq.md                # 常见问题
```

## 文档生成原则

### 1. 项目概述 (README.md)
- 项目一句话简介
- 核心功能特性
- 技术栈说明
- 快速开始示例
- 项目徽章 (可选)

### 2. 安装指南
- 系统要求
- 依赖安装步骤
- 环境变量配置
- 验证安装

### 3. 架构文档
- 系统架构图 (Mermaid)
- 核心模块说明
- 数据流图
- 技术选型理由

### 4. API 文档
- 接口概览
- 认证方式
- 请求/响应格式
- 错误码说明
- 示例代码

### 5. 代码规范
- 命名规范
- 目录结构
- 提交信息规范
- 代码审查清单

## 工具使用

- `read_file` - 读取项目代码分析结构
- `list_dir` - 查看项目目录结构
- `write_file` - 生成 Wiki 文档
- `exec` - 执行文档构建命令

## 输出格式

所有文档使用 Markdown 格式，支持：
- 代码块高亮
- 表格
- Mermaid 图表
- 表情符号增强可读性

## MkDocs 配置示例

```yaml
# mkdocs.yml
site_name: 项目名称 Wiki
theme:
  name: material
  features:
    - navigation.tabs
    - navigation.sections
    - search.highlight
plugins:
  - search
  - minify
markdown_extensions:
  - pymdownx.highlight
  - pymdownx.superfences
  - tables
nav:
  - 首页: index.md
  - 入门:
    - 安装: getting-started/installation.md
    - 快速开始: getting-started/quickstart.md
  - 开发:
    - 架构: development/architecture.md
    - API: development/api-reference.md
```
