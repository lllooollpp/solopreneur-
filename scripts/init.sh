#!/bin/bash
# Solopreneur 开发环境初始化脚本
# 用于快速启动开发环境并进行基本测试
#
# 基于 Anthropic "Effective harnesses for long-running agents"
# 强制流程：环境检查 -> 冒烟测试 -> 单任务约束验证

set -e

echo "🚀 Initializing Solopreneur development environment..."
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. 检查 Python 环境
echo "📋 Step 1: Checking Python environment..."
if command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version 2>&1)
    echo "   ${GREEN}✓${NC} Found $PYTHON_VERSION"
else
    echo "   ${RED}✗${NC} Python not found!"
    exit 1
fi

# 2. 创建/激活虚拟环境
echo ""
echo "📋 Step 2: Setting up virtual environment..."
if [ ! -d ".venv" ]; then
    echo "   Creating Python virtual environment..."
    python -m venv .venv
    echo "   ${GREEN}✓${NC} Virtual environment created"
else
    echo "   ${GREEN}✓${NC} Virtual environment exists"
fi

# 激活环境
if [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate  # Windows Git Bash
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate      # Linux/Mac
else
    echo "   ${RED}✗${NC} Could not find activate script"
    exit 1
fi
echo "   ${GREEN}✓${NC} Virtual environment activated"

# 3. 安装 Python 依赖
echo ""
echo "📋 Step 3: Installing Python dependencies..."
pip install -e . -q
echo "   ${GREEN}✓${NC} Python dependencies installed"

# 4. 检查前端依赖
echo ""
echo "📋 Step 4: Checking frontend dependencies..."
if [ ! -d "ui/node_modules" ]; then
    echo "   Installing frontend dependencies..."
    cd ui && npm install && cd ..
    echo "   ${GREEN}✓${NC} Frontend dependencies installed"
else
    echo "   ${GREEN}✓${NC} Frontend dependencies exist"
fi

# 5. 🔥 强制运行冒烟测试 (新增)
echo ""
echo "🔥 Step 5: Running mandatory smoke tests..."
echo "   (This validates core functionality before any work)"
python scripts/smoke_test.py
SMOKE_EXIT=$?
if [ $SMOKE_EXIT -ne 0 ]; then
    echo ""
    echo "   ${RED}✗${NC} Smoke tests FAILED! Fix issues before continuing."
    echo "   Run 'python scripts/smoke_test.py' for details."
    exit 1
fi

# 6. 验证单任务约束 (新增)
echo ""
echo "📋 Step 6: Verifying single-task constraint..."
IN_PROGRESS_COUNT=$(python -c "
import json
from pathlib import Path
fl = Path('.agent/feature_list.json')
if fl.exists():
    d = json.load(open(fl))
    print(sum(1 for f in d.get('features', []) if f.get('status') == 'in_progress'))
else:
    print(0)
")

if [ "$IN_PROGRESS_COUNT" -gt 1 ]; then
    echo "   ${YELLOW}⚠${NC} Multiple in_progress features detected: $IN_PROGRESS_COUNT"
    echo "   ${YELLOW}⚠${NC} This violates single-task constraint!"
    echo "   Run harness to fix: python -c \"from solopreneur.agent.core.harness import LongRunningHarness; h = LongRunningHarness(Path('.')); h.get_enforced_current_feature()\""
else
    echo "   ${GREEN}✓${NC} Single-task constraint satisfied (in_progress: $IN_PROGRESS_COUNT)"
fi

# 7. 检查长期运行框架状态
echo ""
echo "📋 Step 7: Checking long-running harness..."
if [ -f ".agent/feature_list.json" ]; then
    echo "   ${GREEN}✓${NC} Feature list exists"
    FEATURES_COUNT=$(python -c "import json; print(len(json.load(open('.agent/feature_list.json'))['features']))")
    COMPLETED=$(python -c "import json; d=json.load(open('.agent/feature_list.json')); print(sum(1 for f in d['features'] if f['status']=='completed'))")
    IN_PROGRESS=$(python -c "import json; d=json.load(open('.agent/feature_list.json')); print(sum(1 for f in d['features'] if f['status']=='in_progress'))")
    echo "   📊 Features: $FEATURES_COUNT total, $COMPLETED completed, $IN_PROGRESS in_progress"
else
    echo "   ${YELLOW}!${NC} Feature list not initialized. Run: python -c \"from solopreneur.agent.core.harness import LongRunningHarness; LongRunningHarness('.').initialize('solopreneur', [])\""
fi

# 8. Git 状态检查 (新增)
echo ""
echo "📋 Step 8: Checking git working tree..."
GIT_STATUS=$(git status --porcelain 2>/dev/null || echo "")
if [ -n "$GIT_STATUS" ]; then
    CHANGES=$(echo "$GIT_STATUS" | wc -l)
    echo "   ${YELLOW}⚠${NC} Working tree has $CHANGES uncommitted changes"
    echo "   ${YELLOW}⚠${NC} Consider committing before starting new feature"
else
    echo "   ${GREEN}✓${NC} Working tree is clean"
fi

# 9. 显示启动信息
echo ""
echo "=========================================="
echo "${GREEN}✅ Environment ready!${NC}"
echo "=========================================="
echo ""
echo "To start development servers:"
echo "  python start.py"
echo ""
echo "To start backend only:"
echo "  python -m uvicorn solopreneur.api.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "To start frontend only:"
echo "  cd ui && npm run dev"
echo ""
echo "Access points:"
echo "  Frontend:  http://localhost:5173"
echo "  Backend:   http://localhost:8000"
echo "  API Docs:  http://localhost:8000/docs"
echo ""
echo "Harness API:"
echo "  Status:    GET /api/v1/harness/status"
echo "  Context:   GET /api/v1/harness/context"
echo "  Features:  GET /api/v1/features"
echo ""
