"""
红墨 (RedInk) 模块

提供红墨 API 集成，支持一键生成小红书图文内容
"""

from .client import RedInkClient
from .models import RedInkPage, RedInkOutline, RedInkTaskState, RedInkGenerateResult

__all__ = [
    "RedInkClient",
    "RedInkPage",
    "RedInkOutline",
    "RedInkTaskState",
    "RedInkGenerateResult"
]
