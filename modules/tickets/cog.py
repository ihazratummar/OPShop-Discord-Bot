import discord
from discord.ext import commands
from discord import app_commands
from core.logger import setup_logger
from modules.tickets.ui import get_ticket_settings_embed, TicketSettingsView, TicketControlView, TicketClosedView, \
    EmbedJsonModal

logger = setup_logger("tickets_cog")


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
                view = TicketControlView(ticket_id=str(ticket.id))
                count += 1
                closed_view = TicketClosedView(ticket_id=str(ticket.id), root_view=view)
                self.bot.add_view(view)
                self.bot.add_view(closed_view)

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
    async def create_ticket(self, interaction: discord.Interaction, channel: discord.TextChannel, button_name: str):
        from modules.tickets.services import TicketService
        modal = EmbedJsonModal(
            title="Ticket Creation",
            channel=channel,
            button_name=button_name,
            on_success=TicketService.embed_json_modal_callback
        )
        await interaction.response.send_modal(modal)





async def setup(bot):
    await bot.add_cog(TicketsCog(bot))
