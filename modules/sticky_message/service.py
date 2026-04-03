from typing import Optional, List

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection

from core.database import Database
from modules.sticky_message.model import StickyCreateDTO, StickyMessage, StickyStatus, StickyUpdateBotMsg, \
    StickyUpdateStatus


class StickyMessageService:


    @classmethod
    def get_sticky_message_collection(cls) -> AsyncIOMotorCollection:
        return Database.sticky_message_collection()

    @classmethod
    async def create(cls, dto: StickyCreateDTO) -> StickyMessage:
        """ Insert a new sticky message. Raise ValueError if sticky message already exists """
        collection = cls.get_sticky_message_collection()

        existing = await  collection.find_one(
            {"guild_id": dto.guild_id, "message_id": dto.message_id, "channel_id": dto.channel_id}
        )
        if existing:
            raise ValueError("sticky message already exists")

        doc = StickyMessage(
            guild_id= dto.guild_id,
            message_id= dto.message_id,
            channel_id= dto.channel_id,
            bot_message_id= dto.bot_msg_id,
            type= dto.type,
            added_by= dto.added_by,
            snapshot= dto.snapshot
        )

        result = await collection.insert_one(doc.model_dump())
        doc.id = result.inserted_id
        return doc

    @classmethod
    async def get_by_id(cls, sticky_id: str) -> Optional[StickyMessage]:
        collection = cls.get_sticky_message_collection()
        doc = await collection.find_one({"_id": ObjectId(sticky_id)})
        return StickyMessage(**doc) if doc else None

    @classmethod
    async def get_by_message(cls, message_id: int, channel_id: int) -> Optional[StickyMessage]:
        collection = cls.get_sticky_message_collection()
        doc = await collection.find_one({"message_id": message_id, "channel_id": channel_id})
        return StickyMessage(**doc) if doc else None

    @classmethod
    async def get_active_by_channel(cls, channel_id: int) -> List[StickyMessage]:
        collection = cls.get_sticky_message_collection()
        cursor = collection.find({"channel_id": channel_id, "status": StickyStatus.active.value})
        return [StickyMessage(**item) async for item in cursor]

    @classmethod
    async def get_active_by_guild_id(cls, guild_id: int) -> List[StickyMessage]:
        """Resturn all active sticky messages for a guild"""
        collection = cls.get_sticky_message_collection()
        cursor = collection.find({"guild_id": guild_id, "status": StickyStatus.active.value})
        return [StickyMessage(**item) async for item in cursor]

    # ─── Update ───────────────────────────────────────────────────────────────

    @classmethod
    async def update_bot_msg_id(cls, channel_id: int, message_id: int, new_bot_msg_id: int)-> bool:
        collection = cls.get_sticky_message_collection()
        payload = StickyUpdateBotMsg(bot_msg_id=new_bot_msg_id)
        result = await collection.update_one(
            {"channel_id": channel_id, "message_id": message_id},
            {
                "$set": payload.model_dump(mode="json")
            }
        )
        return result.modified_count == 1


    @classmethod
    async def set_status(cls, channel_id: int, message_id: int, status: StickyStatus) -> bool:
        """Pause, resume or mark as removed"""
        collection = cls.get_sticky_message_collection()
        payload = StickyUpdateStatus(status=status)
        result = await collection.update_one(
            {"channel_id": channel_id, "message_id": message_id},
            {
                "$set": payload.model_dump(mode="json")
            }
        )
        return result.modified_count == 1

    # ─── Convenience wrappers ─────────────────────────────────────────────────

    @classmethod
    async def pause(cls, channel_id: int, message_id) -> bool:
        return await cls.set_status(channel_id, message_id, StickyStatus.paused)

    @classmethod
    async def resume(cls, channel_id: int, message_id: int) -> bool:
        return await cls.set_status(channel_id=channel_id, message_id= message_id, status= StickyStatus.active)

    # ─── Delete ───────────────────────────────────────────────────────────────

    @classmethod
    async def delete(cls, channel_id: int, message_id: int) -> bool:
        """Hard delete — removes the document from the collection entirely."""
        collection = cls.get_sticky_message_collection()
        result = await collection.delete_one({
            "channel_id": channel_id,
            "message_id": message_id,
        })
        return result.deleted_count == 1

    @classmethod
    async def soft_delete(cls, channel_id: int, message_id: int) -> bool:
        """Soft delete — keeps the document but marks it as removed."""
        return await cls.set_status(channel_id, message_id, StickyStatus.removed)

