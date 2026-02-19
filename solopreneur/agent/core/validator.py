"""
任务完成验证器

在 LLM 声称"完成"时，进行二次验证确保任务真正完成。
使用 AI 驱动的智能判断，而非硬编码关键词。
"""

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from solopreneur.agent.core.harness import LongRunningHarness
    from solopreneur.providers.base import LLMProvider


# AI 验证提示词模板
VALIDATION_PROMPT = """你是一个任务完成度评估器。请严格评估以下任务是否真正完成。

## 用户原始请求
{user_request}

## 当前工作进展
{work_summary}

## 当前 Feature 状态
{feature_status}

## 关键检查点

请仔细检查以下情况，如果存在任意一项，任务就【未完成】：

1. **明确的下一步计划**：工作进展中包含"下一步"、"待办"、"将要做"、"接下来"等计划性内容
2. **功能不完整**：原始请求中的功能尚未全部实现（如请求开发完整系统，但只有骨架代码）
3. **缺少关键产出**：
   - 请求数据库 → 需要实际的建表 SQL 或迁移脚本
   - 请求登录注册 → 需要完整的前端表单和后端接口
   - 请求前端页面 → 需要 HTML/模板/Vue 组件，不能只有空壳
4. **Feature 未完成**：有 Feature 状态为 pending 或 in_progress
5. **测试未通过**：如果提到需要测试但未执行或失败

## 请判断

任务是否真正完成？请以 JSON 格式回答：
```json
{{
    "is_complete": true/false,
    "completion_score": 0-100,
    "reasons": ["未完成的原因1", "未完成的原因2"],
    "suggestions": ["建议操作1", "建议操作2"]
}}
```

**重要**：
- 只有 100% 确认所有请求内容都已实现时，才能设置 is_complete=true
- 宁可继续工作也不要过早结束
- 看到"下一步计划"必须判定为未完成"""


@dataclass
class ValidationResult:
    """验证结果"""
    is_complete: bool
    reasons: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    completion_score: int = 0
    
    def get_continuation_prompt(self) -> str:
        """生成继续工作的提示"""
        if self.is_complete:
            return ""
        
        parts = ["任务尚未完成，请继续工作。\n"]
        
        if self.reasons:
            parts.append("未完成项：")
            for r in self.reasons:
                parts.append(f"  - {r}")
            parts.append("")
        
        if self.suggestions:
            parts.append("建议操作：")
            for s in self.suggestions:
                parts.append(f"  - {s}")
            parts.append("")
        
        parts.append(
            "⚠️ 严禁输出纯文本总结或计划。你 **必须** 立即调用工具执行操作。\n"
            "可选工具：`run_workflow`、`delegate`、`delegate_auto`、`exec`、`write_file`。\n"
            "如果有 Feature 需要开发 → 调用 `run_workflow(workflow='feature', description='...')`\n"
            "如果需要修改代码 → 调用 `write_file` 或 `edit_file`\n"
            "如果需要执行命令 → 调用 `exec`\n"
            "不要输出'下一步计划'、'总结'、'建议'，直接调用工具。"
        )
        
        return "\n".join(parts)


@dataclass
class ValidatorConfig:
    """验证器配置"""
    enabled: bool = True
    min_iterations: int = 2  # 最小迭代次数
    check_feature_status: bool = True  # 检查 feature_list 状态
    check_git_clean: bool = True  # 检查 working tree
    check_tests_passed: bool = False  # 检查测试通过（可选，较耗时）
    max_continuation_prompts: int = 5  # 最大继续提示次数（增量循环需要更多空间）
    # AI 验证配置
    use_ai_validation: bool = True  # 是否使用 AI 验证
    ai_validation_threshold: int = 80  # AI 认为完成的阈值分数
    validator_model: str = ""  # 验证器使用的模型（空字符串=使用 provider 默认模型）


class TaskCompletionValidator:
    """
    任务完成验证器
    
    在 LLM 返回无工具调用的响应时，验证任务是否真正完成。
    使用 AI 驱动的智能判断。
    """
    
    def __init__(
        self,
        workspace: Path,
        harness: "LongRunningHarness | None" = None,
        config: ValidatorConfig | None = None,
        provider: "LLMProvider | None" = None,
        model: str | None = None,
    ):
        self.workspace = workspace
        self.harness = harness
        self.config = config or ValidatorConfig()
        self.provider = provider
        self.model = model
        
        # 跟踪继续提示次数，防止无限循环
        self._continuation_count = 0
        
        # 保存最近的用户请求，用于 AI 验证
        self._current_user_request: str = ""
    
    def set_context(self, user_request: str, provider: "LLMProvider | None" = None, model: str | None = None):
        """设置验证上下文"""
        self._current_user_request = user_request
        if provider:
            self.provider = provider
        if model:
            self.model = model
    
    def reset(self):
        """重置状态（新会话开始时调用）"""
        self._continuation_count = 0
        self._current_user_request = ""
    
    def should_force_continue(self, iteration: int) -> tuple[bool, str]:
        """
        检查是否应该强制继续（基于最小迭代）
        
        Args:
            iteration: 当前迭代次数
            
        Returns:
            (should_continue, reason) - 是否应该继续，以及原因
        """
        if iteration < self.config.min_iterations:
            return True, f"迭代次数不足 ({iteration}/{self.config.min_iterations})，任务刚开始，请继续调用工具工作。"
        return False, ""
    
    async def validate(self, llm_response: str = "") -> ValidationResult:
        """
        验证任务是否真正完成
        
        Args:
            llm_response: LLM 的响应内容
            
        Returns:
            ValidationResult: 验证结果
        """
        if not self.config.enabled:
            return ValidationResult(is_complete=True)
        
        # 优先使用 AI 验证
        if self.config.use_ai_validation and self.provider:
            return await self._ai_validate(llm_response)
        
        # 回退到规则验证
        return await self._rule_validate(llm_response)
    
    async def _ai_validate(self, llm_response: str) -> ValidationResult:
        """
        使用 AI 进行智能验证
        
        这是主要验证方法，让 LLM 自己判断任务是否完成
        """
        try:
            # 构建 feature 状态信息
            feature_status = self._get_feature_status_summary()
            
            # 构建 AI 验证提示
            prompt = VALIDATION_PROMPT.format(
                user_request=self._current_user_request or "（未提供原始请求）",
                work_summary=llm_response[:2000] if llm_response else "（无工作进展信息）",
                feature_status=feature_status,
            )
            
            # 调用 LLM —— 使用 validator_model（若配置），否则用 provider 默认模型
            val_model = self.config.validator_model or None
            if not val_model and self.model:
                # 尝试获取 provider 支持的模型列表，用第一个兼容模型
                try:
                    supported = await self.provider.get_available_models()
                    if supported:
                        val_model = supported[0]
                except Exception:
                    val_model = None  # 让 provider 自己决定
            messages = [{'role': 'user', 'content': prompt}]
            response = await self.provider.chat(
                messages=messages,
                model=val_model,
                temperature=0.3,  # 低温度以获得更一致的判断
            )
            
            # 解析 JSON 响应
            content = response.content
            result = self._parse_ai_response(content)
            
            # 应用阈值判断
            if result.completion_score < self.config.ai_validation_threshold:
                result.is_complete = False
            
            logger.info(f"AI 验证结果: is_complete={result.is_complete}, score={result.completion_score}")
            return result
            
        except Exception as e:
            logger.warning(f"AI 验证失败，回退到规则验证: {e}")
            return await self._rule_validate(llm_response)
    
    def _parse_ai_response(self, content: str) -> ValidationResult:
        """解析 AI 响应中的 JSON"""
        try:
            # 尝试提取 JSON 块
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            elif "{" in content and "}" in content:
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                json_str = content[json_start:json_end]
            else:
                raise ValueError("未找到 JSON 响应")
            
            data = json.loads(json_str)
            
            return ValidationResult(
                is_complete=data.get("is_complete", False),
                reasons=data.get("reasons", []),
                suggestions=data.get("suggestions", []),
                completion_score=data.get("completion_score", 0),
            )
        except Exception as e:
            logger.warning(f"解析 AI 响应失败: {e}")
            return ValidationResult(
                is_complete=False,
                reasons=["AI 响应解析失败，需要人工确认"],
                suggestions=["继续执行任务"],
                completion_score=50,
            )
    
    async def _rule_validate(self, llm_response: str) -> ValidationResult:
        """
        规则验证（回退方案）
        
        当 AI 验证不可用时使用
        """
        reasons = []
        suggestions = []

        # 检查 0: 检测"下一步计划"等未完成标志
        pending_indicators = self._check_pending_indicators(llm_response)
        if pending_indicators:
            reasons.extend(pending_indicators["reasons"])
            suggestions.extend(pending_indicators.get("suggestions", []))

        # 检查 1: feature_list 中是否有未完成的 feature
        if self.config.check_feature_status and self.harness:
            in_progress = self._check_in_progress_features()
            if in_progress:
                reasons.append(in_progress["reason"])
                suggestions.extend(in_progress.get("suggestions", []))

        # 检查 2: working tree 是否 clean
        if self.config.check_git_clean:
            git_status = self._check_git_status()
            if git_status:
                reasons.append(git_status["reason"])
                suggestions.extend(git_status.get("suggestions", []))

        is_complete = len(reasons) == 0
        return ValidationResult(
            is_complete=is_complete,
            reasons=reasons,
            suggestions=suggestions,
            completion_score=100 if is_complete else 50,
        )

    def _check_pending_indicators(self, text: str) -> dict | None:
        """检测工作进展中的未完成标志"""
        if not text:
            return None

        # 未完成标志模式
        pending_patterns = [
            ("下一步", "工作进展中包含'下一步'计划"),
            ("下一步计划", "工作进展中包含'下一步计划'"),
            ("待办", "工作进展中包含'待办'事项"),
            ("接下来", "工作进展中包含'接下来'的计划"),
            ("将要做", "工作进展中包含'将要做'的计划"),
            ("待完成", "工作进展中包含'待完成'事项"),
            ("后续工作", "工作进展中包含'后续工作'计划"),
            ("下一步行动", "工作进展中包含'下一步行动'"),
        ]

        found_indicators = []
        for pattern, description in pending_patterns:
            if pattern in text:
                found_indicators.append(description)

        if found_indicators:
            return {
                "reasons": found_indicators,
                "suggestions": [
                    "继续执行上述计划中的任务",
                    "完成所有待办事项后再结束",
                ]
            }

        return None
    
    def can_send_continuation_prompt(self) -> bool:
        """检查是否还可以发送继续提示"""
        return self._continuation_count < self.config.max_continuation_prompts
    
    def increment_continuation_count(self):
        """增加继续提示计数"""
        self._continuation_count += 1
        logger.info(f"任务完成验证未通过，发送继续提示 ({self._continuation_count}/{self.config.max_continuation_prompts})")
    
    def _get_feature_status_summary(self) -> str:
        """获取 feature 状态摘要"""
        if not self.harness:
            return "（未启用 Harness，无法获取 Feature 状态）"
        
        try:
            in_progress = self.harness.list_features(status="in_progress")
            pending = self.harness.list_features(status="pending")
            completed = self.harness.list_features(status="completed")
            
            lines = []
            if in_progress:
                lines.append(f"进行中 ({len(in_progress)} 个): " + ", ".join(f.get("id", "?") for f in in_progress[:3]))
            if pending:
                lines.append(f"待处理 ({len(pending)} 个): " + ", ".join(f.get("id", "?") for f in pending[:5]))
            if completed:
                lines.append(f"已完成 ({len(completed)} 个)")
            
            if not lines:
                return "（无 Feature 记录）"
            
            return "\n".join(lines)
        except Exception as e:
            return f"（获取失败: {e}）"
    
    def _check_in_progress_features(self) -> dict | None:
        """检查是否有进行中或待处理的 feature"""
        if not self.harness:
            return None
        
        try:
            in_progress = self.harness.list_features(status="in_progress")
            pending = self.harness.list_features(status="pending")

            if in_progress:
                feature_names = [f.get("id", f.get("name", "未知")) for f in in_progress]
                return {
                    "reason": f"有 {len(in_progress)} 个 feature 处于进行中状态: {', '.join(feature_names)}",
                    "suggestions": [
                        "完成当前 feature 的实现",
                        "运行测试确保通过",
                        "使用 complete_feature 工具标记完成",
                    ]
                }

            if pending:
                next_feat = pending[0]
                feat_desc = next_feat.get('description', '')
                return {
                    "reason": f"有 {len(pending)} 个 feature 尚未开始 (下一个: {next_feat.get('id', '?')})",
                    "suggestions": [
                        f"立即调用 run_workflow 工具: workflow='feature', description='{feat_desc[:80]}'",
                        "不要总结或描述计划，直接调用工具",
                    ]
                }
        except Exception as e:
            logger.warning(f"检查 feature 状态失败: {e}")
        
        return None
    
    def _check_git_status(self) -> dict | None:
        """检查 git working tree 状态"""
        try:
            # 先检查是否是 git 仓库
            check_repo = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=10,
            )

            # 如果不是 git 仓库，跳过检查（不报错）
            if check_repo.returncode != 0 or "true" not in check_repo.stdout.lower():
                logger.debug(f"Workspace 不是 git 仓库，跳过 git 状态检查: {self.workspace}")
                return None

            # 检查 working tree 状态
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0 and result.stdout.strip():
                changes = result.stdout.strip().split("\n")
                modified = [c for c in changes if c.strip() and c.strip()[0] in "MADRC"]

                if modified:
                    return {
                        "reason": f"Git working tree 有 {len(modified)} 个已修改文件未提交",
                        "suggestions": [
                            "检查修改的文件是否应该提交",
                            "使用 git add 和 git commit 提交更改",
                        ]
                    }
        except subprocess.TimeoutExpired:
            logger.warning("Git 状态检查超时")
        except FileNotFoundError:
            logger.debug("Git 命令不可用，跳过 git 状态检查")
        except Exception as e:
            logger.warning(f"检查 git 状态失败: {e}")

        return None
