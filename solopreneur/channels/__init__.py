"""Chat channels module with plugin architecture."""

from solopreneur.channels.base import BaseChannel
from solopreneur.channels.manager import ChannelManager

__all__ = ["BaseChannel", "ChannelManager"]
