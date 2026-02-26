from datetime import datetime
from typing import Optional, List, Literal

from bson import ObjectId
from discord import Object
from pydantic import Field

from core.models.base import MongoModel


class GiveawaysModel(MongoModel):
    guild_id: int = Field(..., description="Guild ID")
    channel_id: int = Field(..., description="Channel ID")
    message_id: Optional[int] = Field(None, description="Message ID")

    title: Optional[str] = Field(None, description="Title")
    description: Optional[str] = Field(None, description="Description")
    embed_json: Optional[str] = Field(None, description="Raw Discohook JSON for embeds")
    host_id: int = Field(..., description="Host ID")

    winner_count: Optional[int] = Field(None, description="Winner Count")
    required_roles : Optional[List[int]] = Field(None, description="Required Roles")

    blacklisted_roles: Optional[List[int]] = Field(None, description="Blacklist")
    min_account_age: Optional[int] = Field(None, description="Minimum Account Age")

    start_at: Optional[datetime] = Field(None, description="Start Time")
    end_at: Optional[datetime] = Field(None, description="End Time")
    ended: Optional[bool] = Field(None, description="Ended")

    total_entries: Optional[int] = Field(None, description="Total Entries")
    winners : Optional[List[int]] = Field(None, description="Winners")

    reroll_count: Optional[int] = Field(None, description="Reroll Count")

class GiveawayEntryModel(MongoModel):
    giveaway_id: ObjectId = Field(..., description="Giveaway ID")
    guild_id: int = Field(..., description="Guild ID")

    user_id: int = Field(..., description="User ID")

    valid: bool = Field(..., description="Valid Status")
    invalid_reason: Optional[str] = Field(None, description="Invalid Reason")

    entered_at: Optional[datetime] = Field(None, description="Entered Time")


class GiveawayLogsModel(MongoModel):
    giveaway_id: ObjectId = Field(..., description="Giveaway ID")
    action: Optional[Literal['CREATE','END','REROLL', 'DELETE']] = Field(default='CREATE', description="Action")
    performed_by: int = Field(..., description="Performed By")
    timestamp: datetime = Field(..., description="Timestamp")

