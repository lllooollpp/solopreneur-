#!/usr/bin/env python3
"""
冒烟测试脚本
每次会话启动时运行，验证核心功能可用�?
基于 Anthropic "Effective harnesses for long-running agents" 文章�?- 强制端到端冒烟测�?- 验证核心路径可复现运�?"""
import sys
import subprocess
from pathlib import Path

# 颜色定义
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
NC = '\033[0m'  # No Color


def run_test(name: str, command: str, expected: str = "") -> tuple[bool, str]:
    """运行单个测试"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        output = (result.stdout + result.stderr).strip()
        passed = expected.lower() in output.lower() if expected else result.returncode == 0
        return passed, output[:200]
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)


def main():
    """运行所有冒烟测�?""
    workspace = Path(__file__).parent.parent
    
    print("=" * 60)
    print("🔥 solopreneur Smoke Tests")
    print("=" * 60)
    print()
    
    tests = [
        # 1. 核心导入测试
        ("Backend API imports", 
         "python -c \"from solopreneur.api.main import app; print('OK')\"",
         "OK"),
        
        ("Agent core imports",
         "python -c \"from solopreneur.agent.core.loop import AgentLoop; print('OK')\"",
         "OK"),
        
        ("Provider imports",
         "python -c \"from solopreneur.providers.litellm_provider import LiteLLMProvider; print('OK')\"",
         "OK"),
        
        ("Harness imports",
         "python -c \"from solopreneur.agent.core.harness import LongRunningHarness; print('OK')\"",
         "OK"),
        
        # 2. 配置文件测试
        ("Config file exists",
         f"python -c \"from pathlib import Path; p = Path.home() / '.solopreneur' / 'config.json'; print('EXISTS' if p.exists() else 'NOT_FOUND')\"",
         ""),
        
        # 3. 长期运行框架测试
        ("Feature list valid",
         f"python -c \"import json; f = open('{workspace / \".agent\" / \"feature_list.json\"}'); d = json.load(f); print('VALID' if 'features' in d else 'INVALID')\"",
         "VALID"),
        
        ("Progress file exists",
         f"python -c \"from pathlib import Path; p = Path('{workspace / \".agent\" / \"progress.md\"}'); print('EXISTS' if p.exists() else 'NOT_FOUND')\"",
         "EXISTS"),
        
        # 4. 单任务约束验�?        ("Single in_progress constraint",
         f"python -c \"import json; d = json.load(open('{workspace / \".agent\" / \"feature_list.json\"}')); ip = [f for f in d['features'] if f['status'] == 'in_progress']; print('PASS' if len(ip) <= 1 else 'FAIL: ' + str(len(ip)) + ' in_progress')\"",
         "PASS"),
        
        # 5. Git 状态检�?        ("Git repository valid",
         "git rev-parse --is-inside-work-tree",
         "true"),
        
        # 6. 前端测试（可选）
        ("Frontend node_modules exists",
         f"python -c \"from pathlib import Path; p = Path('{workspace / \"ui\" / \"node_modules\"}'); print('EXISTS' if p.exists() else 'NOT_FOUND')\"",
         ""),
    ]
    
    passed = 0
    failed = 0
    results = []
    
    for name, command, expected in tests:
        success, output = run_test(name, command, expected)
        results.append((name, success, output))
        
        if success:
            print(f"  {GREEN}✓{NC} {name}")
            passed += 1
        else:
            print(f"  {RED}✗{NC} {name}")
            print(f"      {YELLOW}Output: {output}{NC}")
            failed += 1
    
    print()
    print("=" * 60)
    
    if failed == 0:
        print(f"{GREEN}�?All smoke tests passed ({passed}/{len(tests)}){NC}")
        print("=" * 60)
        return 0
    else:
        print(f"{RED}�?Smoke tests failed: {passed}/{len(tests)} passed{NC}")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
