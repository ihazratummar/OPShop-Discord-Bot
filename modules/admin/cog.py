import time

import discord
from discord import app_commands
from discord.ext import commands

from core.logger import setup_logger
from modules.admin.ui import AdminRootView, get_root_embed, EmbedJsonModal
from modules.shop.services import CategoryService

logger = setup_logger("admin_cog")


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="shop-admin", description="Open the Shop Admin Panel")
    @app_commands.checks.has_permissions(administrator=True)  # or use custom check
    async def shop_admin_dashboard(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            view = AdminRootView()
            await view.init_view()

            categories = await CategoryService.get_all_categories()
            embed = await get_root_embed(categories)

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in /shop-admin command: {e}", exc_info=True)
            await interaction.followup.send("Failed to open admin panel.", ephemeral=True)

    @app_commands.command(name="shop-config", description="Configure Economy Rules (Tax, XP, Currency)")
    @app_commands.checks.has_permissions(administrator=True)
    async def shop_config(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            from modules.economy.services import EconomyConfigService
            from modules.economy.ui import EconomyRulesView

            config = await EconomyConfigService.get_config()
            view = EconomyRulesView()
            embed = view.get_embed(config)

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in /shop-config command: {e}", exc_info=True)
            await interaction.followup.send("Failed to open config.", ephemeral=True)

    @app_commands.command(name="shop-post-panel",
                          description="Post a persistent Shop Panel with custom embed to a channel")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(category_id="The root Category for this panel", channel="The channel to post in")
    async def shop_post_panel(self, interaction: discord.Interaction, category_id: str, channel: discord.TextChannel):
        """Opens a modal for the user to paste embed JSON."""
        start_time = time.time()
        logger.info(f"Command invoked at {start_time}")

        try:
            # ✅ Create and send modal IMMEDIATELY
            modal = EmbedJsonModal(category_id=category_id, channel=channel)

            before_send = time.time()
            logger.info(f"Modal created in {before_send - start_time:.3f}s")

            await interaction.response.send_modal(modal)

            after_send = time.time()
            logger.info(f"Modal sent in {after_send - before_send:.3f}s (total: {after_send - start_time:.3f}s)")

        except Exception as e:
            error_time = time.time()
            logger.error(f"Failed to send modal after {error_time - start_time:.3f}s: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "An error occurred while trying to open the panel editor.",
                        ephemeral=True
                    )
            except Exception as followup_e:
                logger.error(f"Failed to send error message to user: {followup_e}")

    # Autocomplete for category_id
    @shop_post_panel.autocomplete('category_id')
    async def category_autocomplete(self, interaction: discord.Interaction, current: str) -> list[
        app_commands.Choice[str]]:
        from modules.shop.services import CategoryService
        categories = await CategoryService.get_all_categories()
        return [
            app_commands.Choice(name=c.name, value=str(c.id))
            for c in categories if current.lower() in c.name.lower()
        ][:25]

    @app_commands.command(name="item-post-panel",
                          description="Post a persistent Item Panel with custom embed - direct order button")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(item_id="The Item for this panel", channel="The channel to post in")
    async def item_post_panel(self, interaction: discord.Interaction, item_id: str, channel: discord.TextChannel, button_emoji: str, button_name: str):
        """Opens a modal for the user to paste embed JSON for an item panel."""
        from modules.admin.ui import ItemEmbedJsonModal
        
        modal = ItemEmbedJsonModal(item_id=item_id, channel=channel, button_emoji= button_emoji, button_name = button_name)
        await interaction.response.send_modal(modal)

    # Autocomplete for item_id
    @item_post_panel.autocomplete('item_id')
    async def item_autocomplete(self, interaction: discord.Interaction, current: str) -> list[
        app_commands.Choice[str]]:
        from modules.shop.services import ItemService
        items = await ItemService.get_all_items()
        return [
            app_commands.Choice(name=f"{i.name} ({i.price:.0f} {i.currency})", value=str(i.id))
            for i in items if current.lower() in i.name.lower()
        ][:25]

    @shop_admin_dashboard.error
    async def shop_admin_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(AdminCog(bot))
