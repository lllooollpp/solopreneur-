"""配置加载实用程序。"""

import json
from pathlib import Path
from typing import Any

from nanobot.config.schema import Config


def get_config_path() -> Path:
    """获取默认配置文件路径。"""
    return Path.home() / ".nanobot" / "config.json"


def get_data_dir() -> Path:
    """获取 nanobot 数据目录。"""
    from nanobot.utils.helpers import get_data_path
    return get_data_path()


def load_config(config_path: Path | None = None) -> Config:
    """
    从文件加载配置或创建默认配置。
    
    参数:
        config_path: 可选的配置文件路径。如果不提供，则使用默认路径。
    
    返回:
        加载的配置对象。
    """
    path = config_path or get_config_path()
    
    if path.exists():
        try:
            with open(path) as f:
                data = json.load(f)
            return Config.model_validate(convert_keys(data))
        except (json.JSONDecodeError, ValueError) as e:
            print(f"警告：无法从 {path} 加载配置: {e}")
            print("正在使用默认配置。")
    
    return Config()


def save_config(config: Config, config_path: Path | None = None) -> None:
    """
    将配置保存到文件。
    
    参数:
        config: 要保存的配置。
        config_path: 可选的保存路径。如果不提供，则使用默认路径。
    """
    path = config_path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # 转换为 camelCase 格式
    data = config.model_dump()
    data = convert_to_camel(data)
    
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def convert_keys(data: Any) -> Any:
    """将 camelCase 键转换为蛇形命名法 (snake_case)，以便 Pydantic 使用。"""
    if isinstance(data, dict):
        return {camel_to_snake(k): convert_keys(v) for k, v in data.items()}
    if isinstance(data, list):
        return [convert_keys(item) for item in data]
    return data


def convert_to_camel(data: Any) -> Any:
    """将蛇形命名法 (snake_case) 键转换为 camelCase。"""
    if isinstance(data, dict):
        return {snake_to_camel(k): convert_to_camel(v) for k, v in data.items()}
    if isinstance(data, list):
        return [convert_to_camel(item) for item in data]
    return data


def camel_to_snake(name: str) -> str:
    """将 camelCase 转换为蛇形命名法 (snake_case)。"""
    result = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            result.append("_")
        result.append(char.lower())
    return "".join(result)


def snake_to_camel(name: str) -> str:
    """将蛇形命名法 (snake_case) 转换为 camelCase。"""
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])
