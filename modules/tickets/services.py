import discord
from modules.tickets.models import Ticket, TicketMessage
from modules.shop.models import Item
from core.database import Database
from core.logger import setup_logger
from datetime import datetime

logger = setup_logger("ticket_service")

class TicketService:
    @staticmethod
    async def create_ticket(user: discord.User, guild: discord.Guild, item: Item = None, category_path: str = None) -> Ticket:
        """
        Create a new ticket in the DB and a private channel in Discord.
        """
        # 1. Create Channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Determine topic
        if category_path:
            topic = f"Order: {category_path}"
        elif item:
            topic = f"Order: {item.name}"
        else:
            topic = "Support Ticket"
        
        # Find or create category for tickets (simple implementation)
        # category = discord.utils.get(guild.categories, name="Tickets")
        # if not category: ...
        
        channel = await guild.create_text_channel(
            name=f"ticket-{user.name[:10]}-{str(user.id)[-4:]}",
            overwrites=overwrites,
            topic=topic
        )

        # 2. Create DB Entry
        ticket = Ticket(
            user_id=user.id,
            channel_id=channel.id,
            status="open",
            topic=topic,
            related_item_id=str(item.id) if item else None
        )
        
        result = await Database.tickets().insert_one(ticket.to_mongo())
        ticket.id = result.inserted_id
        
        logger.info(f"Created ticket {ticket.id} for user {user.id} in channel {channel.id}")
        return ticket

    @staticmethod
    async def get_ticket_by_channel(channel_id: int) -> Ticket:
        doc = await Database.tickets().find_one({"channel_id": channel_id})
        if doc:
            return Ticket(**doc)
        return None

    @staticmethod
    async def close_ticket(ticket: Ticket, closed_by_user_id: int, bot: discord.Client, guild: discord.Guild) -> bool:
        """Mark ticket as closed in DB and generate transcript."""
        import chat_exporter
        import io
        
        # 1. Generate Transcript
        channel = bot.get_channel(ticket.channel_id)
        if channel:
            try:
                transcript_html = await chat_exporter.export(channel)
                if transcript_html:
                    transcript_file = discord.File(
                        io.BytesIO(transcript_html.encode("utf-8")),
                        filename=f"transcript-{channel.name}.html"
                    )
                    
                    # 2. Send to Log Channel
                    # Ideally, Config.TICKET_LOG_CHANNEL_ID. For now, look for a channel named 'ticket-logs'
                    log_channel = discord.utils.get(guild.text_channels, name="ticket-logs")
                    if log_channel:
                         await log_channel.send(
                             content=f"Ticket {channel.name} closed by <@{closed_by_user_id}>.",
                             file=transcript_file
                         )
            except Exception as e:
                logger.error(f"Failed to generate transcript: {e}")

        updates = {
            "status": "closed",
            "closed_at": datetime.utcnow(),
            "closed_by": closed_by_user_id
        }
        await Database.tickets().update_one(
            {"_id": ticket.id},
            {"$set": updates}
        )
        return True

    @staticmethod
    async def log_message(channel_id: int, message: discord.Message):
        """Append a message to the ticket transcript."""
        # Check if this channel is a ticket
        ticket = await TicketService.get_ticket_by_channel(channel_id)
        if not ticket:
            return

        msg_entry = TicketMessage(
            user_id=message.author.id,
            content=message.content,
            is_staff=message.author.bot  # Simple check, assumes bot = system/staff context often
        )
        
        await Database.tickets().update_one(
            {"_id": ticket.id},
            {"$push": {"messages": msg_entry.to_mongo()}}
        )
