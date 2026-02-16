"""Configuration module for solopreneur."""

from solopreneur.config.loader import load_config, get_config_path
from solopreneur.config.schema import Config

__all__ = ["Config", "load_config", "get_config_path"]
