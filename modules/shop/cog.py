import discord
from discord import app_commands
from discord.ext import commands

from loguru import logger
from modules.tickets.ui import CustomTicketView


class ShopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """Register persistent views for all shop panels on startup."""
        from modules.shop.services_panels import ShopPanelService
        from modules.shop.ui import OrderNowView, ItemOrderView
        
        panels = await ShopPanelService.get_all_panels()
        category_count = 0
        item_count = 0
        custom_panel = 0
        
        from modules.shop.services import ItemService
        
        # Pre-fetch items for directory views
        # optimize: fetch once instead of per directory panel?
        # Yes, directory shows all active items.
        all_active_items = await ItemService.get_all_items(active_only=True)
        # Sort as we do in creation
        all_active_items.sort(key=lambda x: x.id, reverse=True)
        
        for panel in panels:
            # Check if this is an item panel (category_id starts with "item:")
            if panel.type == "item":
                # Some legacy panels might not have type set correctly but usually they do
                # If category_id starts with item:, it's an item panel
                if panel.category_id and panel.category_id.startswith("item:"):
                     item_id = panel.category_id.replace("item:", "")
                     view = ItemOrderView(item_id=item_id)
                     item_count += 1
                else:
                    # Fallback or error?
                    logger.warning(f"Panel {panel.id} has type 'item' but invalid category_id: {panel.category_id}")
                    continue

            elif panel.type == "custom":
                view = CustomTicketView(custom_id=panel.custom_id)
                custom_panel += 1

            elif panel.type == "directory":
                # Register with REAL data extracted from DB
                from modules.shop.ui import ItemDirectoryView
                if all_active_items:
                    view = ItemDirectoryView(directory_items=all_active_items)
                else:
                    # Fallback if no items found
                    from types import SimpleNamespace
                    dummy_item = SimpleNamespace(name="No active items", id="0")
                    view = ItemDirectoryView(directory_items=[dummy_item])
                
            else:
                view = OrderNowView(category_id=panel.category_id)
                category_count += 1

            self.bot.add_view(view, message_id=panel.message_id)
        
        logger.info(f"Registered {category_count} category panel(s) and {item_count} item panel(s) and {custom_panel} custom panel(s).")

    @app_commands.command(name="shop", description="Open the shop")
    async def shop_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            from modules.shop.ui import ShopRootView, get_root_embed
            from modules.shop.services import CategoryService
            
            view = ShopRootView(interaction.user.id)
            await view.init_view()
            
            categories = await CategoryService.get_active_categories()
            embed = await get_root_embed(categories)
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"Shop command error: {e}", exc_info=True)
            await interaction.followup.send("Failed to open shop.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ShopCog(bot))
