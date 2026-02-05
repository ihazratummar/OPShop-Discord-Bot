from pydantic import Field
from core.models.base import MongoModel
from typing import Optional, Literal

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

class EconomyConfig(MongoModel):
    tax_rate: float = Field(default=0.0, description="Tax rate for transfers (0.0 - 1.0)")
    xp_multiplier: float = Field(default=1.0, description="Global XP multiplier")
    currency_name: str = Field(default="Credits", description="Name of the main currency")
