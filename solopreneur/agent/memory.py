"""Agent 持久化记忆系统。"""

from pathlib import Path
from datetime import datetime

from solopreneur.utils.helpers import ensure_dir, today_date


class MemoryStore:
    """
    Agent 的记忆系统。
    
    支持每日笔记 (memory/YYYY-MM-DD.md) 和长期记忆 (MEMORY.md)。
    """
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory_dir = ensure_dir(workspace / "memory")
        self.memory_file = self.memory_dir / "MEMORY.md"
    
    def get_today_file(self) -> Path:
        """获取当天记忆文件的路径。"""
        return self.memory_dir / f"{today_date()}.md"
    
    def read_today(self) -> str:
        """读取当天的记忆笔记。"""
        today_file = self.get_today_file()
        if today_file.exists():
            return self._read_file_safe(today_file)
        return ""

    def _read_file_safe(self, path: Path) -> str:
        """安全读取文件，支持多种编码。"""
        encodings = ["utf-8", "utf-8-sig", "gbk", "gb2312", "latin1"]
        for enc in encodings:
            try:
                return path.read_text(encoding=enc)
            except UnicodeDecodeError:
                continue
        return ""

    def append_today(self, content: str) -> None:
        """向当天的记忆笔记追加内容。"""
        today_file = self.get_today_file()
        
        if today_file.exists():
            existing = self._read_file_safe(today_file)
            content = existing + "\n" + content
        else:
            # 为新的一天添加标题
            header = f"# {today_date()}\n\n"
            content = header + content
        
        today_file.write_text(content, encoding="utf-8")
    
    def read_long_term(self) -> str:
        """读取长期记忆 (MEMORY.md)。"""
        if self.memory_file.exists():
            return self._read_file_safe(self.memory_file)
        return ""
    
    def write_long_term(self, content: str) -> None:
        """写入长期记忆 (MEMORY.md)。"""
        self.memory_file.write_text(content, encoding="utf-8")
    
    def get_recent_memories(self, days: int = 7) -> str:
        """
        获取最近 N 天的记忆。
        
        参数:
            days: 回溯的天数。
        
        返回:
            合并后的记忆内容。
        """
        from datetime import timedelta
        
        memories = []
        today = datetime.now().date()
        
        for i in range(days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            file_path = self.memory_dir / f"{date_str}.md"
            
            if file_path.exists():
                content = self._read_file_safe(file_path)
                memories.append(content)
        
        return "\n\n---\n\n".join(memories)
    
    def list_memory_files(self) -> list[Path]:
        """列出所有记忆文件，按日期排序（最新的在前）。"""
        if not self.memory_dir.exists():
            return []
        
        files = list(self.memory_dir.glob("????-??-??.md"))
        return sorted(files, reverse=True)
    
    def get_memory_context(self) -> str:
        """
        获取 Agent 的记忆上下文。
        
        返回:
            格式化的记忆上下文，包括长期记忆和近期记忆。
        """
        parts = []
        
        # 长期记忆
        long_term = self.read_long_term()
        if long_term:
            parts.append("## 长期记忆\n" + long_term)
        
        # 今日笔记
        today = self.read_today()
        if today:
            parts.append("## 今日笔记\n" + today)
        
        return "\n\n".join(parts) if parts else ""
