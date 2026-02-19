# solopreneur 长期运行 Agent 整改方案

> 基于 Anthropic "Effective harnesses for long-running agents" 文章

## 一、问题分析

### 当前问题
1. **缺少进度持久化** - Agent 无法跨会话记住进度
2. **缺少功能清单** - 没有结构化的功能状态跟踪
3. **缺少初始化流程** - 每次会话都从零开始
4. **缺少自验证机制** - Agent 可能过早标记任务完成
5. **缺少会话切换协议** - 新会话无法快速理解项目状态

### 文章核心思想
```
┌─────────────────────────────────────────────────────────────┐
│                    长期运行 Agent 架构                        │
├─────────────────────────────────────────────────────────────┤
│  首次运行                                                    │
│  ┌─────────────────┐                                        │
│  │ Initializer     │ → 创建 feature_list.json               │
│  │ Agent           │ → 创建 solopreneur-progress.md             │
│  │                 │ → 创建 init.sh                         │
│  │                 │ → 初始 git commit                      │
│  └─────────────────┘                                        │
│                                                              │
│  后续运行                                                    │
│  ┌─────────────────┐                                        │
│  │ Coding Agent    │ → 读取进度文件                         │
│  │ (每次会话)       │ → 选择一个未完成功能                   │
│  │                 │ → 实现功能 + 测试                       │
│  │                 │ → git commit + 更新进度                │
│  └─────────────────┘                                        │
└─────────────────────────────────────────────────────────────┘
```

## 二、整改方案

### 2.1 新增核心文件

```
solopreneur/
├── .agent/                      # Agent 状态目录（新增）
│   ├── feature_list.json        # 功能清单（JSON 格式）
│   ├── progress.md              # 进度记录
│   ├── session_state.json       # 会话状态
│   └── test_results/            # 测试结果
│
├── scripts/
│   └── init.sh                  # 初始化脚本（新增）
│
├── solopreneur/
│   └── agent/
│       └── core/
│           ├── harness.py       # 长期运行框架（新增）
│           └── initializer.py   # 初始化 Agent（新增）
```

### 2.2 功能清单格式 (feature_list.json)

```json
{
  "project": "solopreneur",
  "version": "0.2.0",
  "last_updated": "2026-02-13T16:30:00Z",
  "features": [
    {
      "id": "FEAT-001",
      "category": "frontend",
      "priority": "P0",
      "description": "Web UI 基础框架",
      "steps": [
        "Vue3 + TypeScript 项目初始化",
        "路由配置（Dashboard/Chat/Config）",
        "基础布局组件"
      ],
      "test_criteria": "访问 http://localhost:5173 显示正常布局",
      "status": "completed",
      "completed_at": "2026-02-10"
    },
    {
      "id": "FEAT-002",
      "category": "frontend",
      "priority": "P0",
      "description": "聊天界面 WebSocket 连接",
      "steps": [
        "WebSocket 客户端实现",
        "消息发送/接收",
        "流式响应展示"
      ],
      "test_criteria": "发送消息后能收到 AI 响应",
      "status": "completed",
      "completed_at": "2026-02-12"
    },
    {
      "id": "FEAT-003",
      "category": "frontend",
      "priority": "P1",
      "description": "Token 统计面板",
      "steps": [
        "TracePanel 组件",
        "调用链路可视化",
        "实时 Token 统计"
      ],
      "test_criteria": "聊天后面板显示 Token 数量和调用链",
      "status": "in_progress",
      "assigned_to": null
    },
    {
      "id": "FEAT-004",
      "category": "provider",
      "priority": "P0",
      "description": "本地模型代理问题修复",
      "steps": [
        "检测本地 endpoint",
        "清除代理环境变量",
        "添加日志"
      ],
      "test_criteria": "本地 vLLM 模型可正常连接",
      "status": "completed",
      "completed_at": "2026-02-13"
    }
  ],
  "statistics": {
    "total": 4,
    "completed": 3,
    "in_progress": 1,
    "pending": 0
  }
}
```

### 2.3 进度文件格式 (progress.md)

```markdown
# solopreneur 开发进度

## 最新会话 (2026-02-13)

### 完成的工作
- [x] 修复本地模型代理问题 (#FEAT-004)
  - 在 `litellm_provider.py` 中添加本地 endpoint 检测
  - 自动清除 HTTP_PROXY 环境变量
- [x] 添加多端访问支持
  - 后端绑定 0.0.0.0
  - 前端 vite 配置 host: '0.0.0.0'
  - 启动脚本显示本机 IP

### 进行中的工作
- [ ] Token 统计面板优化 (#FEAT-003)
  - 已实现基础 UI
  - 待解决: vLLM 流式响应无 usage 数据

### 下一步计划
1. 完善 Token 估算逻辑
2. 添加企业微信渠道测试

---

## 历史记录

### 2026-02-12
- 完成聊天界面 WebSocket (#FEAT-002)
- 修复 trace 事件转发问题

### 2026-02-10
- 项目初始化 (#FEAT-001)
- 创建前端项目结构
```

### 2.4 初始化脚本 (init.sh)

```bash
#!/bin/bash
# solopreneur 开发环境初始化脚本

set -e

echo "🚀 Initializing solopreneur development environment..."

# 1. 检查 Python 环境
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python -m venv .venv
fi

# 2. 激活环境并安装依赖
if [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate  # Windows Git Bash
else
    source .venv/bin/activate      # Linux/Mac
fi

pip install -e .

# 3. 检查前端依赖
if [ ! -d "ui/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd ui && npm install && cd ..
fi

# 4. 启动开发服务器
echo "Starting development servers..."
python start.py
```

## 三、代码实现

### 3.1 长期运行框架 (harness.py)

```python
"""
长期运行 Agent 框架
基于 Anthropic "Effective harnesses for long-running agents"
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field, asdict
from enum import Enum

from loguru import logger


class FeatureStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass
class Feature:
    """功能项"""
    id: str
    category: str
    priority: str  # P0, P1, P2
    description: str
    steps: list[str]
    test_criteria: str
    status: str = "pending"
    completed_at: str | None = None
    assigned_to: str | None = None
    notes: str | None = None


@dataclass
class FeatureList:
    """功能清单"""
    project: str
    version: str
    last_updated: str
    features: list[dict]
    
    def get_next_pending(self, priority: str | None = None) -> Feature | None:
        """获取下一个待处理的功能"""
        for f in self.features:
            if f["status"] == "pending":
                if priority is None or f["priority"] == priority:
                    return Feature(**f)
        return None
    
    def get_in_progress(self) -> Feature | None:
        """获取正在进行的功能"""
        for f in self.features:
            if f["status"] == "in_progress":
                return Feature(**f)
        return None


class LongRunningHarness:
    """
    长期运行 Agent 框架
    
    负责：
    1. 管理 feature_list.json
    2. 记录进度到 progress.md
    3. 提供会话上下文恢复
    """
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.agent_dir = workspace / ".agent"
        self.agent_dir.mkdir(exist_ok=True)
        
        self.feature_list_path = self.agent_dir / "feature_list.json"
        self.progress_path = self.agent_dir / "progress.md"
        self.session_state_path = self.agent_dir / "session_state.json"
    
    def initialize(self, project_name: str, initial_features: list[dict]) -> None:
        """
        初始化环境（首次运行时调用）
        
        类似文章中的 Initializer Agent
        """
        # 创建功能清单
        feature_list = {
            "project": project_name,
            "version": "0.1.0",
            "last_updated": datetime.now().isoformat(),
            "features": initial_features,
            "statistics": self._calc_statistics(initial_features)
        }
        
        with open(self.feature_list_path, "w", encoding="utf-8") as f:
            json.dump(feature_list, f, indent=2, ensure_ascii=False)
        
        # 创建进度文件
        self._init_progress_file(project_name)
        
        # 创建 init.sh
        self._create_init_script()
        
        logger.info(f"Initialized long-running harness for {project_name}")
    
    def get_session_context(self) -> dict[str, Any]:
        """
        获取会话上下文（每次新会话开始时调用）
        
        类似文章中的 "Getting up to speed" 流程
        """
        context = {
            "feature_list": self._load_feature_list(),
            "recent_progress": self._load_recent_progress(),
            "git_log": self._get_recent_commits(),
            "current_feature": None,
            "next_steps": []
        }
        
        # 检查是否有进行中的功能
        in_progress = context["feature_list"].get_in_progress()
        if in_progress:
            context["current_feature"] = in_progress
            context["next_steps"] = ["Continue working on: " + in_progress.description]
        else:
            # 获取下一个待处理功能
            next_feature = context["feature_list"].get_next_pending()
            if next_feature:
                context["current_feature"] = next_feature
                context["next_steps"] = ["Start working on: " + next_feature.description]
        
        return context
    
    def start_feature(self, feature_id: str) -> None:
        """标记功能为进行中"""
        features = self._load_feature_list()
        for f in features.features:
            if f["id"] == feature_id:
                f["status"] = "in_progress"
                self._save_feature_list(features)
                self._append_progress(f"Started working on #{feature_id}")
                break
    
    def complete_feature(self, feature_id: str, notes: str = "") -> None:
        """标记功能为已完成"""
        features = self._load_feature_list()
        for f in features.features:
            if f["id"] == feature_id:
                f["status"] = "completed"
                f["completed_at"] = datetime.now().isoformat()
                f["notes"] = notes
                self._save_feature_list(features)
                self._append_progress(f"Completed #{feature_id}: {notes}")
                break
    
    def record_progress(self, message: str) -> None:
        """记录进度"""
        self._append_progress(message)
    
    def _load_feature_list(self) -> FeatureList:
        """加载功能清单"""
        if not self.feature_list_path.exists():
            raise FileNotFoundError("Feature list not initialized. Run initialize() first.")
        
        with open(self.feature_list_path, encoding="utf-8") as f:
            data = json.load(f)
        
        return FeatureList(**data)
    
    def _save_feature_list(self, feature_list: FeatureList) -> None:
        """保存功能清单"""
        feature_list.last_updated = datetime.now().isoformat()
        
        data = asdict(feature_list)
        data["statistics"] = self._calc_statistics(data["features"])
        
        with open(self.feature_list_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _init_progress_file(self, project_name: str) -> None:
        """初始化进度文件"""
        content = f"""# {project_name} 开发进度

## 最新会话 ({datetime.now().strftime("%Y-%m-%d")})

### 进行中的工作
- [ ] 待开始

### 下一步计划
1. 运行 `init.sh` 启动开发环境
2. 查看 feature_list.json 了解功能列表

---

## 历史记录

### {datetime.now().strftime("%Y-%m-%d")}
- 项目初始化
- 创建长期运行框架
"""
        with open(self.progress_path, "w", encoding="utf-8") as f:
            f.write(content)
    
    def _append_progress(self, message: str) -> None:
        """追加进度记录"""
        timestamp = datetime.now().strftime("%H:%M")
        entry = f"- [{timestamp}] {message}\n"
        
        # 读取现有内容
        if self.progress_path.exists():
            content = self.progress_path.read_text(encoding="utf-8")
        else:
            content = ""
        
        # 在 "### 进行中的工作" 后插入
        lines = content.split("\n")
        insert_idx = 0
        for i, line in enumerate(lines):
            if "### 进行中的工作" in line or "### 完成的工作" in line:
                insert_idx = i + 1
        
        lines.insert(insert_idx, entry)
        
        with open(self.progress_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    
    def _load_recent_progress(self) -> str:
        """加载最近的进度"""
        if not self.progress_path.exists():
            return "No progress recorded yet."
        
        content = self.progress_path.read_text(encoding="utf-8")
        # 返回最新会话部分
        if "## 最新会话" in content:
            return content.split("## 历史记录")[0]
        return content[:1000]  # 限制长度
    
    def _get_recent_commits(self, count: int = 10) -> list[str]:
        """获取最近的 git 提交"""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", f"-{count}"],
                capture_output=True,
                text=True,
                cwd=self.workspace
            )
            return result.stdout.strip().split("\n")
        except Exception:
            return []
    
    def _calc_statistics(self, features: list) -> dict:
        """计算统计信息"""
        status_count = {"pending": 0, "in_progress": 0, "completed": 0, "blocked": 0}
        for f in features:
            status = f.get("status", "pending")
            status_count[status] = status_count.get(status, 0) + 1
        
        return {
            "total": len(features),
            **status_count
        }
    
    def _create_init_script(self) -> None:
        """创建初始化脚本"""
        init_script = self.workspace / "scripts" / "init.sh"
        init_script.parent.mkdir(exist_ok=True)
        
        content = '''#!/bin/bash
# solopreneur 开发环境初始化脚本

set -e

echo "🚀 Initializing solopreneur development environment..."

# 检查 Python 环境
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python -m venv .venv
fi

# 激活环境
if [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi

# 安装依赖
pip install -e .

# 检查前端依赖
if [ ! -d "ui/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd ui && npm install && cd ..
fi

# 运行基本测试
echo "Running basic tests..."
python -c "from solopreneur.api.main import app; print('✅ Backend OK')"

echo "Environment ready! Run 'python start.py' to start."
'''
        init_script.write_text(content)
```

### 3.2 集成到现有系统

修改 `solopreneur/agent/core/loop.py`:

```python
# 在 AgentLoop 类中添加

def __init__(self, ...):
    # ... existing code ...
    
    # 添加长期运行框架
    self.harness = LongRunningHarness(workspace)
    
    # 检查是否首次运行
    if not (workspace / ".agent" / "feature_list.json").exists():
        logger.info("First run detected, running initializer...")
        self._run_initializer()

async def process_message(self, msg: InboundMessage) -> None:
    """处理消息（带长期运行支持）"""
    
    # 1. 获取会话上下文
    context = self.harness.get_session_context()
    
    # 2. 构建系统提示（包含上下文）
    system_prompt = self._build_system_prompt_with_context(context)
    
    # 3. 执行 agent 循环
    # ... existing processing logic ...
    
    # 4. 记录进度
    self.harness.record_progress(f"Processed message from {msg.channel}")
```

## 四、实施步骤

### Phase 1: 基础设施搭建 (1-2 天)

1. **创建 `.agent/` 目录结构**
   ```bash
   mkdir -p .agent/test_results
   ```

2. **创建功能清单**
   - 基于 `specs/001-frontend-copilot-wecom/spec.md` 提取功能
   - 转换为 JSON 格式

3. **创建进度文件**
   - 初始化 `progress.md`
   - 记录当前已完成的工作

### Phase 2: 框架集成 (2-3 天)

1. **实现 `LongRunningHarness` 类**
2. **集成到 `AgentLoop`**
3. **添加 API 端点**
   - `GET /api/harness/context` - 获取会话上下文
   - `POST /api/harness/feature/{id}/start` - 开始功能
   - `POST /api/harness/feature/{id}/complete` - 完成功能

### Phase 3: 前端支持 (1-2 天)

1. **添加功能列表组件**
2. **添加进度面板**
3. **添加会话状态指示器**

### Phase 4: 测试和文档 (1 天)

1. **编写单元测试**
2. **更新 README**
3. **创建使用指南**

## 五、使用示例

### 5.1 首次初始化

```python
from pathlib import Path
from solopreneur.agent.core.harness import LongRunningHarness

# 初始化
harness = LongRunningHarness(Path("/path/to/solopreneur"))

# 定义初始功能列表
features = [
    {
        "id": "FEAT-001",
        "category": "frontend",
        "priority": "P0",
        "description": "Web UI 基础框架",
        "steps": ["Vue3 项目初始化", "路由配置", "基础布局"],
        "test_criteria": "访问 localhost:5173 正常显示",
        "status": "pending"
    },
    # ... 更多功能
]

harness.initialize("solopreneur", features)
```

### 5.2 每次会话开始

```python
# 获取上下文
context = harness.get_session_context()

print("=== Session Context ===")
print(f"Current Feature: {context['current_feature']}")
print(f"Recent Progress:\n{context['recent_progress']}")
print(f"Recent Commits: {context['git_log'][:5]}")
print(f"Next Steps: {context['next_steps']}")
```

### 5.3 功能开发流程

```python
# 1. 开始功能
harness.start_feature("FEAT-003")

# 2. 记录进度
harness.record_progress("实现了 TracePanel 基础组件")

# 3. 完成功能
harness.complete_feature("FEAT-003", "Token 统计面板完成，支持实时显示")
```

## 六、预期效果

1. **跨会话一致性** - Agent 能记住之前的进度
2. **增量开发** - 每次只处理一个功能
3. **自验证** - 功能完成前必须通过测试
4. **可追溯** - 所有进度都有记录
5. **可恢复** - 中断后能快速恢复状态

## 七、与现有系统的整合点

| 现有组件 | 整合方式 |
|---------|---------|
| `specs/` | 作为功能清单的数据源 |
| `memory/` | 与 `.agent/` 并行，存储用户记忆 |
| `SessionManager` | 使用 `.agent/session_state.json` |
| `CompactionEngine` | 压缩时保留功能状态 |
| `GitInspectTool` | 自动获取 commit 历史 |

---

*方案制定时间: 2026-02-13*
*参考文档: Anthropic "Effective harnesses for long-running agents"*
