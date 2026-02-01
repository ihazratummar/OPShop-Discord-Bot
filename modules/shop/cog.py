import discord
from discord import app_commands
from discord.ext import commands
from modules.shop.services import CategoryService

from core.logger import setup_logger

logger = setup_logger("shop_cog")

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
        
        for panel in panels:
            # Check if this is an item panel (category_id starts with "item:")
            if panel.category_id.startswith("item:"):
                item_id = panel.category_id.replace("item:", "")
                view = ItemOrderView(item_id=item_id)
                item_count += 1
            else:
                view = OrderNowView(category_id=panel.category_id)
                category_count += 1
            
            self.bot.add_view(view, message_id=panel.message_id)
        
        logger.info(f"Registered {category_count} category panel(s) and {item_count} item panel(s).")

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
