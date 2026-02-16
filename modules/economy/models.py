from typing import Optional, Literal
from pydantic import Field
from core.models.base import MongoModel


class Transaction(MongoModel):
    user_id: int = Field(..., description="Buyer Discord ID")
    type: Literal['purchase', 'refund', 'reward', 'admin_adjustment', 'redeem'] = Field(...)
    
    # Amounts
    amount_tokens: int = Field(default=0)
    
    # Context
    item_id: Optional[str] =None
    item_name: Optional[str] = None
    description: str = Field(default="")
    
    # Metadata
    performed_by: Optional[int] = Field(None, description="Discord ID of who executed this (e.g. staff member)")