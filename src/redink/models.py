"""
红墨 (RedInk) 数据模型

定义与红墨 API 交互的数据结构
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class RedInkPage:
    """红墨页面数据"""
    index: int
    type: str  # "cover" | "content"
    content: str
    image_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "index": self.index,
            "type": self.type,
            "content": self.content
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RedInkPage":
        """从字典创建"""
        return cls(
            index=data.get("index", 0),
            type=data.get("type", "content"),
            content=data.get("content", ""),
            image_url=data.get("image_url")
        )


@dataclass
class RedInkOutline:
    """红墨大纲数据"""
    outline: str
    pages: List[RedInkPage]
    has_images: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RedInkOutline":
        """从 API 响应创建"""
        pages = [RedInkPage.from_dict(p) for p in data.get("pages", [])]
        return cls(
            outline=data.get("outline", ""),
            pages=pages,
            has_images=data.get("has_images", False)
        )


@dataclass
class RedInkTaskState:
    """红墨任务状态"""
    generated: Dict[str, str] = field(default_factory=dict)  # {index: filename}
    failed: Dict[str, str] = field(default_factory=dict)  # {index: error_message}
    has_cover: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RedInkTaskState":
        """从 API 响应创建"""
        return cls(
            generated=data.get("generated", {}),
            failed=data.get("failed", {}),
            has_cover=data.get("has_cover", False)
        )
    
    @property
    def total_generated(self) -> int:
        """已生成数量"""
        return len(self.generated)
    
    @property
    def total_failed(self) -> int:
        """失败数量"""
        return len(self.failed)
    
    @property
    def is_complete(self) -> bool:
        """是否全部完成（无失败）"""
        return self.total_failed == 0


@dataclass
class RedInkGenerateResult:
    """红墨生成结果"""
    success: bool
    task_id: str
    topic: str
    outline: str
    pages: List[RedInkPage]
    stats: Dict[str, Any]
    download_url: Optional[str] = None
    local_images: List[str] = field(default_factory=list)
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "task_id": self.task_id,
            "topic": self.topic,
            "outline": self.outline,
            "pages": [
                {
                    "index": p.index,
                    "type": p.type,
                    "content": p.content,
                    "image_url": p.image_url
                }
                for p in self.pages
            ],
            "stats": self.stats,
            "download_url": self.download_url,
            "local_images": self.local_images,
            "error": self.error
        }
