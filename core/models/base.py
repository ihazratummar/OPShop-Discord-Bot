from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, Any
from bson import ObjectId

class PyObjectId(ObjectId):
    """Custom type for MongoDB ObjectId to work with Pydantic."""
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, values=None, **kwargs):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        return {"type": "string"}

class MongoModel(BaseModel):
    """Base model for MongoDB documents."""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

    def to_mongo(self, **kwargs):
        """Convert to dictionary compatible with MongoDB."""
        exclude_unset = kwargs.pop('exclude_unset', False)
        by_alias = kwargs.pop('by_alias', True)
        
        parsed = self.model_dump(
            exclude_unset=exclude_unset,
            by_alias=by_alias,
            **kwargs
        )
        
        # If _id is None, remove it so Mongo generates one
        if '_id' in parsed and parsed['_id'] is None:
            del parsed['_id']
            
        return parsed
