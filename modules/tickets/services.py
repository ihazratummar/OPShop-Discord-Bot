import asyncio
import time
import uuid
from typing import List

import discord
from modules.tickets.models import Ticket, TicketMessage, TicketSettingsModel
from modules.shop.models import Item
from core.database import Database
from core.logger import setup_logger
from datetime import datetime

logger = setup_logger("ticket_service")


class TicketService:
    @staticmethod
    async def create_ticket(user: discord.User, guild: discord.Guild, item: Item = None,
                            category_path: str = None) -> Ticket:
        """
        Create a new ticket in the DB and a private channel in Discord.
        """

        ticket_manager_role = await TicketService.get_ticket_manager_role(guild=guild)
        open_ticket_category = await TicketService.create_or_get_ticket_category(guild=guild,
                                                                                 category_name="Open Ticket",
                                                                                 category_type="open")

        # 1. Create Channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            ticket_manager_role: discord.PermissionOverwrite(read_messages=True, manage_messages=True)
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

        channel = await open_ticket_category.create_text_channel(
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
        await TicketService.send_logs_to_channel(
            guild=guild,
            title="Ticket Created",
            description=f"Ticket created for user {user.mention} in channel {channel.id}",
            color=discord.Color.green()
        )
        return ticket

    @staticmethod
    async def get_ticket_by_channel(channel_id: int) -> Ticket:
        doc = await Database.tickets().find_one({"channel_id": channel_id})
        if doc:
            return Ticket(**doc)
        return None

    @staticmethod
    async def send_ticket_transcribe(channel: discord.TextChannel):
        import chat_exporter
        import io

        ticket_settings = await TicketService.get_ticket_settings(guild_id=channel.guild.id)
        channel_id = None
        try:
            transcript_html = await chat_exporter.export(channel)
            if transcript_html:
                transcript_file = discord.File(
                    io.BytesIO(transcript_html.encode("utf-8")),
                    filename=f"transcript-{channel.name}.html"
                )

                if ticket_settings and ticket_settings.ticket_transcript_channel_id:
                    channel_id = int(ticket_settings.ticket_transcript_channel_id)

                transcript_channel = channel.guild.get_channel(channel_id) if channel_id else None
                if not transcript_channel:
                    transcript_channel = await channel.guild.create_text_channel(
                        name="ticket-transcript",
                        overwrites={
                            channel.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                            channel.guild.me: discord.PermissionOverwrite(read_messages=True, manage_messages=True)
                        }
                    )

                    await Database.ticket_settings().update_one(
                        {"guild_id": channel.guild.id},
                        {"$set": {"ticket_transcript_channel_id": transcript_channel.id}},
                        upsert=True
                    )

                await transcript_channel.send(file=transcript_file)
        except Exception as e:
            logger.error(f"Failed to generate transcript: {e}")

    @staticmethod
    async def close_ticket(ticket: Ticket, closed_by_user_id: int, bot: discord.Client, guild: discord.Guild) -> bool:
        """Mark ticket as closed in DB and generate transcript."""

        # 1. Generate Transcript
        channel = bot.get_channel(ticket.channel_id)
        if channel:
            await TicketService.send_ticket_transcribe(channel=channel)
            await TicketService.send_logs_to_channel(
                guild=guild,
                title="Ticket Closed",
                description=f"Ticket closed for user <@{closed_by_user_id}> in channel {channel.name}",
                color=discord.Color.dark_red()
            )

        updates = {
            "status": "closed",
            "closed_at": datetime.utcnow(),
            "closed_by": closed_by_user_id
        }
        await Database.tickets().update_one(
            {"_id": ticket.id},
            {"$set": updates}
        )

        await TicketService.move_channel_to_close(channel=channel, ticket_owner=ticket.user_id)

        return True

    @staticmethod
    async def delete_ticket(ticket: Ticket, delete_by_user: int, guild: discord.Guild) -> bool:
        logger.info("Enter delete ticket function.....")
        try:
            logger.info(f"Enter Ticket Try BLock Ticket ID: {ticket.id}")
            if ticket:
                await TicketService.send_logs_to_channel(
                    guild=guild,
                    title="Ticket Deleted",
                    description=f"Ticket **{ticket.id}** has been deleted! by <@{delete_by_user}>",
                    color=discord.Color.red()
                )

                updates = {
                    "status": "deleted",
                    "closed_at": datetime.utcnow(),
                    "closed_by": delete_by_user
                }
                await Database.tickets().update_one(
                    {"_id": ticket.id},
                    {"$set": updates}
                )
            return True
        except Exception as e:
            logger.error(f"Failed to delete ticket: {e}")
            return False

    @staticmethod
    async def move_channel_to_close(channel: discord.TextChannel, ticket_owner: int):
        guild = channel.guild
        ticket_manager_role = await TicketService.get_ticket_manager_role(guild=guild)
        close_category = await TicketService.create_or_get_ticket_category(guild=guild, category_name="Close Ticket",
                                                                           category_type="close")
        ticket_owner = guild.get_member(ticket_owner)
        overrides = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False, view_channel=False),
            ticket_manager_role: discord.PermissionOverwrite(read_messages=True, manage_messages=True,
                                                             send_messages=True, view_channel=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, manage_messages=True, send_messages=True),
            ticket_owner: discord.PermissionOverwrite(read_messages=True, manage_messages=False, send_messages=False),
        }
        await channel.edit(category=close_category, overwrites=overrides)

    @staticmethod
    async def get_ticket_manager_role(guild: discord.Guild) -> discord.Role:
        ticket_settings = await TicketService.get_ticket_settings(guild_id=guild.id)

        role_id = None
        if ticket_settings and ticket_settings.ticket_manager_role_id:
            role_id = int(ticket_settings.ticket_manager_role_id)

        ticket_manager_role = guild.get_role(role_id) if role_id else None

        if not ticket_manager_role:
            ticket_manager_role = await guild.create_role(name="Ticket Manager")

        await Database.ticket_settings().update_one(
            {"guild_id": guild.id},
            {"$set": {"ticket_manager_role_id": ticket_manager_role.id}},
            upsert=True
        )
        return ticket_manager_role

    @staticmethod
    async def create_or_get_ticket_category(
            guild: discord.Guild,
            category_name: str,
            category_type: str
    ) -> discord.CategoryChannel:

        ticket_settings = await TicketService.get_ticket_settings(guild_id=guild.id)
        ticket_manager_role = await TicketService.get_ticket_manager_role(guild=guild)

        category_id = None
        mongo_key = None

        if ticket_settings:
            if category_type == "open":
                mongo_key = "open_ticket_category_id"
                if ticket_settings.open_ticket_category_id:
                    category_id = int(ticket_settings.open_ticket_category_id)
            else:
                mongo_key = "close_ticket_category_id"
                if ticket_settings.close_ticket_category_id:
                    category_id = int(ticket_settings.close_ticket_category_id)

        ticket_category = guild.get_channel(category_id) if category_id else None

        if not ticket_category:
            ticket_category = await guild.create_category(
                name=category_name,
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    guild.me: discord.PermissionOverwrite(view_channel=True, manage_messages=True),
                    ticket_manager_role: discord.PermissionOverwrite(view_channel=True, manage_messages=True),
                }
            )

            await Database.ticket_settings().update_one(
                {"guild_id": guild.id},
                {"$set": {mongo_key: ticket_category.id}},
                upsert=True
            )

        return ticket_category

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

    @staticmethod
    async def send_logs_to_channel(guild: discord.Guild, title: str, description: str, color: discord.Color):
        ticket_settings = await TicketService.get_ticket_settings(guild_id=guild.id)

        channel_id = None
        if ticket_settings and ticket_settings.ticket_logs_channel_id:
            channel_id = int(ticket_settings.ticket_logs_channel_id)
        ticket_logs_channel = guild.get_channel(channel_id) if channel_id else None

        if not ticket_logs_channel:
            ticket_logs_channel = await guild.create_text_channel(
                name="ticket-logs",
                overwrites={
                    guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True),
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                }
            )

        await Database.ticket_settings().update_one(
            {"guild_id": guild.id},
            {"$set": {"ticket_logs_channel_id": ticket_logs_channel.id}},
            upsert=True
        )

        t = time.localtime()
        formatted_time = time.strftime("%y-%m-%d %H:%M:%S", t)
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        embed.add_field(name="Time", value=formatted_time)
        if guild.me.avatar.url:
            embed.set_thumbnail(url=guild.me.avatar.url)
        await ticket_logs_channel.send(embed=embed)

    @staticmethod
    async def get_ticket_settings(guild_id: int) -> TicketSettingsModel:
        doc = await Database.ticket_settings().find_one({"guild_id": guild_id})
        if doc:
            return TicketSettingsModel(**doc)

        ## Create default settings
        default = TicketSettingsModel(guild_id=guild_id)
        await Database.ticket_settings().insert_one(default.model_dump())
        return default

    @staticmethod
    async def get_all_tickets() -> List[Ticket]:
        cursor = Database.tickets().find({})
        tickets = []
        async for doc in cursor:
            tickets.append(Ticket(**doc))
        return tickets

    @staticmethod
    async def embed_json_modal_callback(
            embed: discord.Embed,
            interaction: discord.Interaction,
            channel: discord.TextChannel,
            button_name: str,
            raw_json
    ):
        from modules.tickets.ui import CustomTicketView
        from modules.shop.services_panels import ShopPanelService
        import secrets
        custom_id = secrets.token_hex(4)

        view = CustomTicketView(button_name = button_name, custom_id = custom_id)
        message = await channel.send(embed=embed, view=view)
        asyncio.create_task(
            ShopPanelService.create_panel(
                guild_id=interaction.guild.id,
                channel_id=channel.id,
                message_id=message.id,
                embed_json=raw_json,
                _type="custom",
                custom_id= custom_id
            )
        )

        await interaction.followup.send("Ticket Created!", ephemeral=True)
