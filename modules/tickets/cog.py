import discord
from discord.ext import commands
from modules.tickets.services import TicketService
from core.logger import setup_logger

logger = setup_logger("tickets_cog")

class TicketsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
            
        # Log message if it's in a ticket channel
        # Optimization: We should cache ticket channel IDs to avoid DB hit every msg
        # keeping it simple for now as per "Core Foundation"
        if isinstance(message.channel, discord.TextChannel) and message.channel.name.startswith("ticket-"):
             await TicketService.log_message(message.channel.id, message)

async def setup(bot):
    await bot.add_cog(TicketsCog(bot))
