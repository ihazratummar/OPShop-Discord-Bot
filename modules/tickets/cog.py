import discord
from discord.ext import commands
from discord import app_commands
from loguru import logger
from modules.tickets.ui import get_ticket_settings_embed, TicketSettingsView, TicketControlView, TicketClosedView, \
    EmbedJsonModal, ShopPanelView


class TicketsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self) -> None:
        logger.info(f"Loading {TicketsCog.__name__}")
        from modules.tickets.services import TicketService
        tickets = await TicketService.get_all_tickets()
        count = 0
        for ticket in tickets:
            if not ticket.status == "deleted":
                view = TicketControlView(ticket_id=str(ticket.id), claimed_by=ticket.claimed_by)
                count += 1
                closed_view = TicketClosedView(ticket_id=str(ticket.id), root_view=view)
                self.bot.add_view(view)
                self.bot.add_view(closed_view)

        # Register persistent ShopPanelView
        self.bot.add_view(ShopPanelView())
        
        logger.info(f"Loaded {count} tickets")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Log message if it's in a ticket channel
        # Optimization: We should cache ticket channel IDs to avoid DB hit every msg
        # keeping it simple for now as per "Core Foundation"
        if isinstance(message.channel, discord.TextChannel) and message.channel.name.startswith("ticket-"):
            from modules.tickets.services import TicketService
            await TicketService.log_message(message.channel.id, message)

    @app_commands.command(name="ticket_panel", description="Manager ticket settings")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_panel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed = await get_ticket_settings_embed(guild_id=interaction.guild_id)
        view = TicketSettingsView(guild_id=interaction.guild_id)
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="create_ticket", description="Create a new ticket")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(channel="Mention a channel where to post ticket", button_name="Button name of the ticket")
    async def create_ticket(self, interaction: discord.Interaction, channel: discord.TextChannel, button_name: str, emoji: str):
        from modules.tickets.services import TicketService
        modal = EmbedJsonModal(
            title="Ticket Creation",
            channel=channel,
            button_name=button_name,
            button_emoji = emoji,
            on_success=TicketService.embed_json_modal_callback
        )
        await interaction.response.send_modal(modal)

    @app_commands.command(name="create_directory", description="Create a directory of items")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(channel="Mention a channel where to post directory")
    async def create_directory(self, interaction: discord.Interaction, channel: discord.TextChannel):
        from modules.tickets.services import TicketService
        modal = EmbedJsonModal(
            title="Directory Creation",
            channel=channel,
            button_name="Directory", # Dummy
            button_emoji="📍", # Dummy
            on_success=TicketService.directory_modal_callback
        )
        await interaction.response.send_modal(modal)

    @app_commands.command(name="create_shop_panel", description="Create a Shop panel with Open Shop button")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(channel="Channel to post the shop panel")
    async def create_shop_panel(self, interaction: discord.Interaction, channel: discord.TextChannel, button_name: str = "Open Shop",emoji: str ="🛒"):
        from modules.tickets.services import TicketService
        modal = EmbedJsonModal(
            title="Shop Panel Creation",
            channel=channel,
            button_name= button_name,
            button_emoji=emoji,
            on_success=TicketService.shop_panel_modal_callback
        )
        await interaction.response.send_modal(modal)


    @app_commands.command(name="ticket_complete", description="Mark the ticket as completed")
    @app_commands.guild_only()
    async def ticket_complete(self, interaction: discord.Interaction):
        from modules.tickets.services import TicketService
        from modules.tickets.ui import TicketControlView
        ticket = await TicketService.get_ticket_by_channel(interaction.channel_id)

        view = TicketControlView(ticket_id= str(ticket.id))
        await TicketService.complete_order(interaction=interaction, root_view= view)

    @app_commands.command(name="ticket_close", description="Close a ticket")
    @app_commands.guild_only()
    async def ticket_close(self, interaction: discord.Interaction):
        from modules.tickets.services import TicketService
        from modules.tickets.ui import TicketControlView
        ticket = await TicketService.get_ticket_by_channel(interaction.channel_id)

        view = TicketControlView(ticket_id=str(ticket.id))
        await TicketService.close_ticket_btn(interaction=interaction, root_view=view)

    @app_commands.command(name="ticket_claim", description="Claim a ticket")
    @app_commands.guild_only()
    async def ticket_claim(self, interaction: discord.Interaction):
        from modules.tickets.services import TicketService
        from modules.tickets.ui import TicketControlView
        ticket = await TicketService.get_ticket_by_channel(interaction.channel_id)

        view = TicketControlView(ticket_id=str(ticket.id))
        await TicketService.claim_ticket_func(interaction=interaction, root_view=view, ticket_id=str(ticket.id))

    @app_commands.command(name="ticket_unclaim", description="Unclaim a ticket")
    @app_commands.guild_only()
    async def ticket_unclaim(self, interaction: discord.Interaction):
        from modules.tickets.services import TicketService
        from modules.tickets.ui import TicketControlView
        ticket = await TicketService.get_ticket_by_channel(interaction.channel_id)

        view = TicketControlView(ticket_id=str(ticket.id))
        await TicketService.unclaim_ticket_btn(interaction=interaction, root_view=view)

    @app_commands.command(name="ticket_delete", description="Delete a ticket")
    @app_commands.guild_only()
    async def ticket_unclaim(self, interaction: discord.Interaction):
        from modules.tickets.services import TicketService
        await TicketService.delete_ticket_btn(interaction=interaction)

async def setup(bot):
    await bot.add_cog(TicketsCog(bot))

