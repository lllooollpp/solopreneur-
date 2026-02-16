"""配置加载实用程序�?""

import json
from pathlib import Path
from typing import Any

from solopreneur.config.schema import Config


def get_config_path() -> Path:
    """获取默认配置文件路径�?""
    from solopreneur.utils.helpers import get_data_path
    return get_data_path() / "config.json"


def get_data_dir() -> Path:
    """获取 solopreneur 数据目录�?""
    from solopreneur.utils.helpers import get_data_path
    return get_data_path()


# 全局配置缓存（单例模式）
_config_cache: Config | None = None
_config_path_cache: Path | None = None


def load_config(config_path: Path | None = None, force_reload: bool = False) -> Config:
    """
    从文件加载配置或创建默认配置（支持缓存）�?

    参数:
        config_path: 可选的配置文件路径。如果不提供，则使用默认路径�?
        force_reload: 强制重新加载配置，忽略缓存�?

    返回:
        加载的配置对象�?
    """
    global _config_cache, _config_path_cache

    path = config_path or get_config_path()

    # 检查缓�?
    if not force_reload and _config_cache is not None:
        if _config_path_cache == path:
            # 检查文件是否被修改
            if path.exists():
                try:
                    current_mtime = path.stat().st_mtime
                    cached_mtime = getattr(_config_cache, "_mtime", 0)
                    if current_mtime <= cached_mtime:
                        return _config_cache
                except Exception:
                    pass  # 文件检查失败，继续加载

    if path.exists():
        try:
            with open(path) as f:
                data = json.load(f)
            config = Config.model_validate(convert_keys(data))
            # 缓存配置和文件修改时�?
            _config_cache = config
            _config_path_cache = path
            try:
                _config_cache._mtime = path.stat().st_mtime
            except Exception:
                _config_cache._mtime = 0
            return config
        except (json.JSONDecodeError, ValueError) as e:
            print(f"警告：无法从 {path} 加载配置: {e}")
            print("正在使用默认配置�?)

    # 使用默认配置
    config = Config()
    _config_cache = config
    _config_path_cache = path
    _config_cache._mtime = 0
    return config


def invalidate_config_cache():
    """使配置缓存失效，下次调用 load_config 时会重新加载�?""
    global _config_cache, _config_path_cache
    _config_cache = None
    _config_path_cache = None


def save_config(config: Config, config_path: Path | None = None) -> None:
    """
    将配置保存到文件�?
    
    参数:
        config: 要保存的配置�?
        config_path: 可选的保存路径。如果不提供，则使用默认路径�?
    """
    path = config_path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # 转换�?camelCase 格式
    data = config.model_dump()
    data = convert_to_camel(data)
    
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def convert_keys(data: Any) -> Any:
    """�?camelCase 键转换为蛇形命名�?(snake_case)，以�?Pydantic 使用�?""
    if isinstance(data, dict):
        return {camel_to_snake(k): convert_keys(v) for k, v in data.items()}
    if isinstance(data, list):
        return [convert_keys(item) for item in data]
    return data


def convert_to_camel(data: Any) -> Any:
    """将蛇形命名法 (snake_case) 键转换为 camelCase�?""
    if isinstance(data, dict):
        return {snake_to_camel(k): convert_to_camel(v) for k, v in data.items()}
    if isinstance(data, list):
        return [convert_to_camel(item) for item in data]
    return data


def camel_to_snake(name: str) -> str:
    """�?camelCase 转换为蛇形命名法 (snake_case)�?""
    result = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            result.append("_")
        result.append(char.lower())
    return "".join(result)


def snake_to_camel(name: str) -> str:
    """将蛇形命名法 (snake_case) 转换�?camelCase�?""
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])
