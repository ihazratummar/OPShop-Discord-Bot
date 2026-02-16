from typing import Optional, List

from pydantic import Field

from core.models.base import MongoModel


class User(MongoModel):
    discord_id: int = Field(..., description="Discord User ID")
    username: Optional[str] = Field(None, description="Discord Username")
    
    # Economy
    tokens: Optional[int] = Field(default=0, ge=0)

    # XP & Trust
    reputations: Optional[int] = Field(default=0)
    rep_given_counter : Optional[int] = Field(default=0, ge=0)

    ## Level
    reputation_tier_role: Optional[List[int]] = None
    
    # Check
    is_blacklisted: Optional[bool] = Field(default=False)
    joined_at_timestamp: Optional[int] = Field(default=0, description="Unix timestamp of when they first joined DB")

