from typing import Optional

from pydantic import Field

from core.models.base import MongoModel


class ReputationLogs(MongoModel):
    from_user_id: int = Field(...)
    to_user_id: int = Field(...)
    message: Optional[str] = Field(...)
    timestamp: int = Field(...)
    guild_id: int = Field(...)