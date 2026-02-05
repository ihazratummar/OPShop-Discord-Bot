from pydantic import Field, field_validator
from core.models.base import MongoModel
from typing import List, Optional, Literal
from datetime import datetime

class TicketMessage(MongoModel):
    user_id: int = Field(..., description="Discord ID of the sender")
    content: str = Field(...)
    is_staff: bool = False
    
class Ticket(MongoModel):
    user_id: int = Field(..., description="Discord ID of the ticket owner")
    guild_id: int = Field(..., description="Discord ID of the guild")
    channel_id: Optional[int] = Field(None, description="Discord Channel ID")
    status: Literal['open', 'closed', 'archived', 'deleted'] = Field(default='open')
    topic: str = Field(default="Support")
    message_id: Optional[int] = Field(None, description="Discord Message ID")
    claimed_by: Optional[int] = Field(None, description="Discord ID of the claimed user")
    claimed_at: Optional[datetime] = datetime.utcnow()
    
    # Context
    related_item_id: Optional[str] = Field(None, description="If this ticket is for an item purchase")
    
    messages: List[TicketMessage] = Field(default_factory=list)
    closed_at: Optional[datetime] = None
    closed_by: Optional[int] = None

    @field_validator('status')
    def validate_status(cls, v):
        if v not in ['open', 'closed', 'archived', 'deleted']:
            raise ValueError('Invalid status')
        return v

class TicketSettingsModel(MongoModel):
    guild_id: int = Field(..., description="Discord ID of the guild")
    open_ticket_category_id: Optional[int] = Field(None, description="Discord ID of the ticket category")
    close_ticket_category_id: Optional[int] = Field(None, description="Discord ID of the ticket category")
    ticket_logs_channel_id: Optional[int] = Field(None, description="Discord ID of the ticket logs channel")
    ticket_transcript_channel_id: Optional[int] = Field(None, description="Discord ID of the ticket transcript channel")
    ticket_manager_role_id: Optional[int] = Field(None, description="Discord ID of the ticket manager role")
