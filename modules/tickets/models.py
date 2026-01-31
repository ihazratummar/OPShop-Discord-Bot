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
    channel_id: Optional[int] = Field(None, description="Discord Channel ID")
    status: Literal['open', 'closed', 'archived'] = Field(default='open')
    topic: str = Field(default="Support")
    
    # Context
    related_item_id: Optional[str] = Field(None, description="If this ticket is for an item purchase")
    
    messages: List[TicketMessage] = Field(default_factory=list)
    closed_at: Optional[datetime] = None
    closed_by: Optional[int] = None

    @field_validator('status')
    def validate_status(cls, v):
        if v not in ['open', 'closed', 'archived']:
            raise ValueError('Invalid status')
        return v
