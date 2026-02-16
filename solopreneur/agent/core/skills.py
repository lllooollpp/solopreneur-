"""Agent 能力的技能加载器（单一路径模式）�?""

import json
import os
import re
import shutil
from pathlib import Path

# 默认内置技能目录（相对于此文件�?
# 当前文件: nanobot/agent/core/skills.py
# 内置技�? nanobot/skills/
BUILTIN_SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"


class SkillsLoader:
    """
    Agent 技能加载器�?
    
    技能是 Markdown 文件 (SKILL.md)，用于教�?Agent 如何使用
    特定的工具或执行某些任务�?
    """
    
    def __init__(self, workspace: Path, builtin_skills_dir: Path | None = None):
        self.workspace = workspace
        self.workspace_skills = workspace / "skills"
        self.builtin_skills = builtin_skills_dir or BUILTIN_SKILLS_DIR
        self.workspace_skills.mkdir(parents=True, exist_ok=True)
        self._seed_builtin_skills()
    
    def list_skills(self, filter_unavailable: bool = True) -> list[dict[str, str]]:
        """
        列出所有可用技能�?
        
        参数:
            filter_unavailable: 如果�?True，则过滤掉未满足要求的技能�?
        
        返回:
            包含技能信息的字典列表，键包括 'name'�?path'�?source'�?
        """
        skills = []

        # 单一路径：只�?workspace/skills 加载
        if self.workspace_skills.exists():
            for skill_dir in self.workspace_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        skills.append({"name": skill_dir.name, "path": str(skill_file), "source": "workspace"})
        
        # 按要求过�?
        if filter_unavailable:
            return [s for s in skills if self._check_requirements(self._get_skill_meta(s["name"]))]
        return skills
    
    def load_skill(self, name: str) -> str | None:
        """
        通过名称加载技能�?
        
        参数:
            name: 技能名称（目录名）�?
        
        返回:
            技能内容，如果未找到则返回 None�?
        """
        # 单一路径：只检查工作区
        workspace_skill = self.workspace_skills / name / "SKILL.md"
        if workspace_skill.exists():
            return workspace_skill.read_text(encoding="utf-8")

        return None

    def _seed_builtin_skills(self):
        """Copy built-in skills into canonical workspace/skills if missing."""
        if not self.builtin_skills or not self.builtin_skills.exists():
            return

        copied = 0
        for skill_dir in self.builtin_skills.iterdir():
            if not skill_dir.is_dir():
                continue
            src_skill = skill_dir / "SKILL.md"
            if not src_skill.exists():
                continue

            dst_dir = self.workspace_skills / skill_dir.name
            dst_skill = dst_dir / "SKILL.md"
            if not dst_skill.exists():
                dst_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_skill, dst_skill)
                copied += 1

        if copied:
            pass
    
    def load_skills_for_context(self, skill_names: list[str]) -> str:
        """
        加载特定技能，以便包含�?Agent 上下文中�?
        
        参数:
            skill_names: 要加载的技能名称列表�?
        
        返回:
            格式化后的技能内容�?
        """
        parts = []
        for name in skill_names:
            content = self.load_skill(name)
            if content:
                content = self._strip_frontmatter(content)
                parts.append(f"### 技能：{name}\n\n{content}")
        
        return "\n\n---\n\n".join(parts) if parts else ""
    
    def build_skills_summary(self) -> str:
        """
        构建所有技能的摘要（名称、描述、路径、可用性）�?
        
        这用于渐进式加载——Agent 在需要时可以使用 read_file 读取完整的技能内容�?
        
        返回:
            XML 格式的技能摘要�?
        """
        all_skills = self.list_skills(filter_unavailable=False)
        if not all_skills:
            return ""
        
        def escape_xml(s: str) -> str:
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        lines = ["<skills>"]
        for s in all_skills:
            name = escape_xml(s["name"])
            path = s["path"]
            desc = escape_xml(self._get_skill_description(s["name"]))
            skill_meta = self._get_skill_meta(s["name"])
            available = self._check_requirements(skill_meta)
            
            lines.append(f"  <skill available=\"{str(available).lower()}\">")
            lines.append(f"    <name>{name}</name>")
            lines.append(f"    <description>{desc}</description>")
            lines.append(f"    <location>{path}</location>")
            
            # 显示不可用技能缺失的要求
            if not available:
                missing = self._get_missing_requirements(skill_meta)
                if missing:
                    lines.append(f"    <requires>{escape_xml(missing)}</requires>")
            
            lines.append(f"  </skill>")
        lines.append("</skills>")
        
        return "\n".join(lines)
    
    def _get_missing_requirements(self, skill_meta: dict) -> str:
        """获取缺失要求的描述�?""
        missing = []
        requires = skill_meta.get("requires", {})
        for b in requires.get("bins", []):
            if not shutil.which(b):
                missing.append(f"CLI: {b}")
        for env in requires.get("env", []):
            if not os.environ.get(env):
                missing.append(f"ENV: {env}")
        return ", ".join(missing)
    
    def _get_skill_description(self, name: str) -> str:
        """从技能的 frontmatter 中获取描述�?""
        meta = self.get_skill_metadata(name)
        if meta and meta.get("description"):
            return meta["description"]
        return name  # 回退到技能名�?
    
    def _strip_frontmatter(self, content: str) -> str:
        """�?Markdown 内容中移�?YAML frontmatter�?""
        if content.startswith("---"):
            match = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
            if match:
                return content[match.end():].strip()
        return content
    
    def _parse_nanobot_metadata(self, raw: str) -> dict:
        """�?frontmatter 中解�?nanobot 元数�?JSON�?""
        try:
            data = json.loads(raw)
            return data.get("nanobot", {}) if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def _check_requirements(self, skill_meta: dict) -> bool:
        """检查是否满足技能要求（二进制文件、环境变量）�?""
        requires = skill_meta.get("requires", {})
        for b in requires.get("bins", []):
            if not shutil.which(b):
                return False
        for env in requires.get("env", []):
            if not os.environ.get(env):
                return False
        return True
    
    def _get_skill_meta(self, name: str) -> dict:
        """获取技能的 nanobot 元数据（缓存�?frontmatter 中）�?""
        meta = self.get_skill_metadata(name) or {}
        return self._parse_nanobot_metadata(meta.get("metadata", ""))
    
    def get_always_skills(self) -> list[str]:
        """获取标记�?always=true 且满足要求的技能�?""
        result = []
        for s in self.list_skills(filter_unavailable=True):
            meta = self.get_skill_metadata(s["name"]) or {}
            skill_meta = self._parse_nanobot_metadata(meta.get("metadata", ""))
            if skill_meta.get("always") or meta.get("always"):
                result.append(s["name"])
        return result
    
    def get_skill_metadata(self, name: str) -> dict | None:
        """
        从技能的 frontmatter 中获取元数据�?
        
        参数:
            name: 技能名称�?
        
        返回:
            元数据字典，如果未找到则返回 None�?
        """
        content = self.load_skill(name)
        if not content:
            return None
        
        if content.startswith("---"):
            match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if match:
                # 简单的 YAML 解析
                metadata = {}
                for line in match.group(1).split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip()] = value.strip().strip('"\'')
                return metadata
        
        return None
