from typing import Optional

from pydantic import Field

from core.models.base import MongoModel


class ReputationLogs(MongoModel):
    from_user_id: Optional[int] = None
    to_user_id: int = Field(...)
    message: Optional[str] = None
    timestamp: Optional[int] = Field(None, description="Timestamp")
    guild_id: int = Field(...)