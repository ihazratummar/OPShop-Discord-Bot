import discord
from discord import app_commands
from discord.ext import commands
from modules.shop.services import CategoryService

from core.logger import setup_logger

logger = setup_logger("shop_cog")

class ShopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
