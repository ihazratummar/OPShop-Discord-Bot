from pydantic import Field, HttpUrl
from core.models.base import MongoModel
from typing import List, Optional, Dict, Literal

ProductType = Literal[
    'Dinos', 'Kits', 'Boss Fights', 'Blueprints', 
    'Bases', 'Services', 'Characters', 'Materials', 'Other'
]

class Question(MongoModel):
    """A question to ask the user when purchasing this item."""
    id: str = Field(..., description="Unique identifier for the question answer")
    text: str = Field(..., description="The question text")
    type: Literal['text', 'number', 'selection'] = Field(default='text')
    options: List[str] = Field(default_factory=list, description="Options if type is selection")
    required: bool = True

class Item(MongoModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="")
    category_id: str = Field(...)
    
    # Pricing
    price: float = Field(default=0.0, ge=0)
    currency: Literal['credits', 'tokens'] = Field(default='tokens')
    
    # Visuals
    image_url: Optional[str] = Field(default=None, description="Optional image to show in embed")
    
    # Configuration
    questions: List[Question] = Field(default_factory=list)
    
    is_active: bool = True
    requires_ticket: bool = True
    
    # Rewards
    xp_reward: int = Field(default=10, ge=0)
    token_reward: int = Field(default=10, ge=0)

class Category(MongoModel):
    name: str = Field(min_length=1, max_length=50)
    description: str = Field(default="")
    rank: int = Field(default=0, description="For sorting order")
    is_active: bool = True
    image_url: Optional[str] = Field(default=None, description="Optional image for the category embed")
    parent_id: Optional[str] = Field(default=None, description="ID of parent category if this is a subcategory")

class ShopPanel(MongoModel):
    """A persistent message displaying a specific shop category."""
    channel_id: int = Field(..., description="Discord Channel ID")
    message_id: int = Field(..., description="Discord Message ID")
    category_id: Optional[str] = Field(..., description="Root category ID for this panel")
    guild_id: int = Field(..., description="Discord Guild ID")
    embed_json: Optional[str] = Field(default=None, description="Custom Discohook embed JSON")
    type: Optional[str] = Field(default=None, description="Shop type")
    custom_id: Optional[str] = Field(default=None, description="Button name")
