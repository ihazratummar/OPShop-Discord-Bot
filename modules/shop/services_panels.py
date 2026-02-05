import asyncio
from typing import List, Optional
from bson import ObjectId
from core.database import Database
from modules.shop.models import ShopPanel, Category
from modules.shop.services import CategoryService, ItemService
from modules.shop.ui import ShopCategoryView, get_category_embed
from core.logger import setup_logger
import discord

logger = setup_logger("shop_panel_service")


class ShopPanelService:
    @staticmethod
    async def create_panel(
            guild_id: int,
            channel_id: int,
            message_id: int,
            category_id: str = None,
            embed_json: str = None,
            _type: str = None,
            custom_id: str = None,
    ) -> ShopPanel:
        """Register a new persistent panel."""
        panel = ShopPanel(
            guild_id=guild_id,
            channel_id=channel_id,
            message_id=message_id,
            category_id=category_id,
            embed_json=embed_json,
            type= _type,
            custom_id = custom_id
        )
        await Database.get_db().shop_panels.insert_one(panel.to_mongo())
        logger.info(f"Created ShopPanel for category {category_id} in ch {channel_id}")
        return panel

    @staticmethod
    async def get_all_panels() -> List[ShopPanel]:
        """Fetch all panels."""
        cursor = Database.get_db().shop_panels.find({})
        panels = []
        async for doc in cursor:
            panels.append(ShopPanel(**doc))
        return panels

    @staticmethod
    async def delete_panel(message_id: int):
        """Delete a panel record."""
        await Database.get_db().shop_panels.delete_one({"message_id": message_id})

    @staticmethod
    async def refresh_panel(bot: discord.Client, panel: ShopPanel):
        """Update a specific panel's message content."""
        try:
            channel = bot.get_channel(panel.channel_id)
            if not channel:
                # Channel might be deleted, could cleanup DB here
                return

            try:
                message = await channel.fetch_message(panel.message_id)
            except discord.NotFound:
                # Message deleted
                await ShopPanelService.delete_panel(panel.message_id)
                return

            category = await CategoryService.get_category(panel.category_id)
            if not category:
                # Category deleted
                await message.delete()
                await ShopPanelService.delete_panel(panel.message_id)
                return

            # Re-generate View & Embed
            subcategories = await CategoryService.get_active_categories(parent_id=str(category.id))
            items = await ItemService.get_items_by_category(str(category.id), active_only=True)

            # Using page 0 for persistent view usually
            embed = await get_category_embed(category, subcategories, items, page=0)
            view = ShopCategoryView(category, user_id=0)  # user_id=0 or None?
            # Note: ShopCategoryView expects a user_id for filtering back buttons sometimes, 
            # but for a public panel, anybody can click. We might need to adjust View to handle "Any User"

            await message.edit(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Failed to refresh panel {panel.id}: {e}")

    @staticmethod
    async def get_panel_by_channel(channel_id: int, panel_type: str) -> Optional[ShopPanel]:
        """Fetch a panel by channel ID and type."""
        doc = await Database.get_db().shop_panels.find_one({"channel_id": channel_id, "type": panel_type})
        if doc:
            return ShopPanel(**doc)
        return None

    @staticmethod
    async def update_panel(
            panel_id: ObjectId, 
            message_id: int, 
            embed_json: str, 
            category_id: str = None, 
            custom_id: str = None
        ):
        """Update a panel record."""
        updates = {
            "message_id": message_id,
            "embed_json": embed_json,
        }
        if category_id is not None:
            updates["category_id"] = category_id
        if custom_id is not None:
            updates["custom_id"] = custom_id

        await Database.get_db().shop_panels.update_one(
            {"_id": panel_id},
            {"$set": updates}
        )
    
    # Keeping old methods as aliases or deprecating if preferred, 
    # but for this request I'll just replace the custom-specific ones we just added 
    # with these generic ones in usage, or redirect them.
    # Since I just added them in the previous step, I can just replace them entirely.

    @staticmethod
    async def get_custom_panel_by_channel(channel_id: int) -> Optional[ShopPanel]:
        return await ShopPanelService.get_panel_by_channel(channel_id, "custom")

    @staticmethod
    async def update_custom_panel(panel_id: ObjectId, message_id: int, embed_json: str, custom_id: str):
        await ShopPanelService.update_panel(panel_id, message_id, embed_json, custom_id=custom_id)

    @staticmethod
    async def refresh_all_panels(bot: discord.Client):
        """Iterate and refresh all known panels concurrently."""
        panels = await ShopPanelService.get_all_panels()
        if not panels:
            return

        # Run all updates in parallel to prevent blocking admin UI
        tasks = [ShopPanelService.refresh_panel(bot, panel) for panel in panels]
        await asyncio.gather(*tasks, return_exceptions=True)
