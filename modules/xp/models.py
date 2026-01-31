from pydantic import Field
from core.models.base import MongoModel
from typing import Literal

class XPLog(MongoModel):
    user_id: int = Field(...)
    amount: int = Field(...)
    source: Literal['purchase', 'activity', 'admin_grant', 'feedback'] = Field(...)
    description: str = Field(default="")

class LevelConfig(MongoModel):
    """Configuration for a specific level."""
    level: int = Field(..., ge=1)
    xp_required: int = Field(..., ge=0)
    role_reward_id: int = Field(default=0, description="Discord Role ID given at this level")
