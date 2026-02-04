from typing import Optional

from pydantic import Field

from core.models.base import MongoModel


class GuildSettings(MongoModel):
    guild_id: int = Field(..., description="Guild id")
    invite_logs_channel_id: Optional[int]  = Field(..., description="Invite logs channel id")
    seller_role_id: Optional[int] = Field(..., description="Seller role id")
