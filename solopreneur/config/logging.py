"""
日志配置模块

配置 loguru 将日志输出到控制台和文件
"""

import sys
from pathlib import Path
from loguru import logger

from solopreneur.utils.helpers import get_data_path


def setup_logging(
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_dir: Path | None = None,
    retention: str = "7 days"
):
    """
    配置 nanobot 日志系统
    
    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        log_to_file: 是否输出到文�?
        log_dir: 日志目录，默认为 ~/.nanobot/logs
        retention: 日志保留时间
    """
    # 移除默认处理�?
    logger.remove()
    
    # 添加控制台处理器
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
    )
    
    # 添加文件处理�?
    if log_to_file:
        if log_dir is None:
            log_dir = get_data_path() / "logs"
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 主日志文�?
        logger.add(
            log_dir / "nanobot_{time:YYYY-MM-DD}.log",
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation="00:00",  # 每天轮换
            retention=retention,
            encoding="utf-8",
        )
        
        # Agent 交互专用日志
        logger.add(
            log_dir / "agent_interactions_{time:YYYY-MM-DD}.log",
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
            rotation="00:00",
            retention=retention,
            encoding="utf-8",
            filter=lambda record: record["function"] in [
                "run_with_agent",
                "spawn",
                "delegate",
                "execute",
                "run",
                "next_step",
            ] or "agent" in record["message"].lower() or "Agent" in record["message"],
        )
        
        logger.info(f"日志已配置，输出目录: {log_dir}")


def get_logger(name: str | None = None):
    """
    获取一个配置了上下文的 logger
    
    Args:
        name: logger 名称
        
    Returns:
        logger 实例
    """
    if name:
        return logger.bind(name=name)
    return logger
