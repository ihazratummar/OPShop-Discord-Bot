from datetime import datetime
from enum import Enum
from typing import Optional, List

from pydantic import Field
from discord.utils import utcnow

from core.models.base import MongoModel


class StickyType(str, Enum):
    PLAIN = "PLAIN"
    EMBED = "EMBED"


class StickyStatus(str, Enum):
    active = "active"
    paused = "paused"
    removed = "removed"


class EmbedSnapshot(MongoModel):
    title: Optional[str] = None
    description: Optional[str] = None
    color: Optional[int] = None
    url: Optional[str] = None


class MessageSnapshot(MongoModel):
    content: Optional[str] = None
    embeds: Optional[List[EmbedSnapshot]] = None
    attachments: Optional[List[str]] = None
    author_id: Optional[int] = None
    author_name: Optional[str] = None


class StickyMessage(MongoModel):
    guild_id: int
    channel_id: int
    message_id: int
    bot_message_id: Optional[int] = None

    type: StickyType
    status: StickyStatus = StickyStatus.active

    added_by: int
    snapshot: Optional[MessageSnapshot] = None


class StickyCreateDTO(MongoModel):
    guild_id: int
    channel_id: int
    message_id: int
    bot_msg_id: int
    type: StickyType
    added_by: int
    snapshot: Optional[MessageSnapshot] = None


class StickyUpdateBotMsg(MongoModel):
    bot_msg_id: int
    updated_at: datetime = Field(default_factory=utcnow)


class StickyUpdateStatus(MongoModel):
    status: StickyStatus
    updated_at: datetime = Field(default_factory=utcnow)