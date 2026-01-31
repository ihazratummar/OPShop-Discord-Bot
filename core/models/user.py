from pydantic import Field
from core.models.base import MongoModel
from typing import List

class User(MongoModel):
    discord_id: int = Field(..., description="Discord User ID")
    username: str = Field(..., description="Discord Username")
    
    # Economy
    tokens: int = Field(default=0, ge=0)
    credits: float = Field(default=0.0, ge=0)
    
    # XP & Trust
    xp: int = Field(default=0, ge=0)
    level: int = Field(default=1, ge=1)
    trust_score: float = Field(default=1.0, ge=0.0) # Multiplier, starts at 1.0 (100%)
    
    # Check
    is_blacklisted: bool = Field(default=False)
    joined_at_timestamp: int = Field(default=0, description="Unix timestamp of when they first joined DB")

