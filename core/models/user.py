from typing import Optional, List

from pydantic import Field

from core.models.base import MongoModel


class User(MongoModel):
    discord_id: int = Field(..., description="Discord User ID")
    username: str = Field(..., description="Discord Username")
    
    # Economy
    tokens: int = Field(default=0, ge=0)
    
    # XP & Trust
    xp: int = Field(default=0, ge=0)
    level: int = Field(default=1, ge=1)
    reputations: int = Field(default=0)
    rep_given_counter : int = Field(default=0, ge=0)

    ## Level
    reputation_tier_role: Optional[List[int]] = None
    
    # Check
    is_blacklisted: bool = Field(default=False)
    joined_at_timestamp: int = Field(default=0, description="Unix timestamp of when they first joined DB")

