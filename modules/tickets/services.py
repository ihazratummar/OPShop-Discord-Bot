import asyncio
import time
from datetime import datetime
from typing import List

import discord
from loguru import logger
from pymongo.asynchronous.collection import ReturnDocument

from core.config import settings
from core.constant import Emoji
from core.database import Database
from modules.economy.models import Transaction
from modules.economy.services import TransactionService, EconomyService
from modules.guild.service import GuildSettingService
from modules.reputation.service import ReputationService
from modules.shop.models import Item
from modules.shop.services import ItemService
from modules.tickets.models import Ticket, TicketMessage, TicketSettingsModel
from modules.tickets.ui import TicketClosedView
from utils.discord_utils import safe_channel_edit


class TicketService:
    @staticmethod
    async def create_ticket(
            user: discord.User,
            guild: discord.Guild,
            item: Item = None,
            category_path: str = None,
            message_id: int = None,
    ) -> tuple[Ticket | None, str]:
        """
        Create a new ticket in the DB and a private channel in Discord.
        """

        try:
            # 1. Run all DB fetches concurrently instead of sequentially

            doc, ticket_manager_role, guild_settings = await asyncio.gather(
                Database.tickets().find_one({"user_id": user.id, "status": "open", "guild_id": guild.id}),
                TicketService.get_ticket_manager_role(guild=guild),
                GuildSettingService.get_guild_settings(guild=guild),
                return_exceptions=True
            )

            if doc and not isinstance(doc, Exception):
                existing_ticket = Ticket(**doc)
                channel = guild.get_channel(existing_ticket.channel_id)
                if channel:
                    return existing_ticket, "exists"

            if isinstance(ticket_manager_role, Exception):
                logger.error(f"Failed to get ticket manager role {ticket_manager_role}")
                ticket_manager_role = None

            if isinstance(guild_settings, Exception):
                logger.error(f"Failed to get guild settings {guild_settings}")
                guild_settings = None

            # 2. Seller Role
            seller_role = None
            if guild_settings and guild_settings.seller_role_id:
                seller_role = guild.get_role(guild_settings.seller_role_id)

            # 3. Build overwrites
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                user: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True),
            }
            if seller_role:
                overwrites[seller_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True,
                                                                      read_message_history=True, manage_messages=True)

            if ticket_manager_role:
                overwrites[ticket_manager_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True,
                                                                              read_message_history=True,
                                                                              manage_messages=True)

            # 4. Determine topic

            if category_path:
                topic = f"Order: {category_path}"
            elif item:
                topic = f"Order: {item.name}"
            else:
                topic = "Support Ticket"

            # 5. Get to Create category
            open_ticket_category = await  TicketService.create_or_get_ticket_category(guild=guild,
                                                                                      category_name="Open Ticket",
                                                                                      category_type="open")

            if not open_ticket_category:
                logger.info(f"Failed to get open ticket category {open_ticket_category.name}")
                return None, "error"

            # 6. Create channel (rate limited: 10 per 10 minutes per guild)
            channel_name = f"ticket-{item.name if item else "support"}-{user.name[:10]}-{str(user.id)[-4:]}"
            try:
                channel = await open_ticket_category.create_text_channel(
                    name=channel_name,
                    overwrites=overwrites,
                    topic=topic
                )
            except discord.HTTPException as e:
                if e.status == 429:
                    logger.error(f"Rate limited on channel creation for guild {guild.name}{guild.id}")
                    return None, "error"
                logger.error(f"Failed to create channel for guild {guild.name}{guild.id}: {e}")
                return None, "error"

            ticket = Ticket(
                user_id=user.id,
                channel_id=channel.id,
                guild_id=guild.id,
                status="open",
                topic=topic,
                related_item_id=str(item.id) if item else None,
                message_id=message_id
            )

            try:
                result = await Database.tickets().insert_one(ticket.to_mongo())
                ticket.id = result.inserted_id
            except Exception as e:
                # DB failed - clean up the created Discord channel
                logger.error(f"Failed to insert ticket {ticket.id}: {e}")
                await channel.delete(reason=f"Ticket database insert failed")
                return None, "error"

            logger.info(f"Create ticket {ticket.id} for user {user.id} in channel {channel.name}")

            # 8. Send logs in background (non- blocking)
            asyncio.create_task(
                TicketService.send_logs_to_channel(
                    guild=guild,
                    title=f"Create ticket",
                    description=f"Ticket created for user {user.mention} in {channel.mention}",
                    color=discord.Color.blurple()
                )
            )

            return ticket, "created"
        except Exception as e:
            logger.error(f"Unexpected error creating ticket for user {user.mention}: {e}")
            return None, "error"

        # doc = await Database.tickets().find_one({"user_id": user.id, "status": "open", "guild_id": guild.id})
        # existing_ticket = Ticket(**doc) if doc else None
        # if existing_ticket:
        #     channel = guild.get_channel(existing_ticket.channel_id)
        #     if channel:
        #         return existing_ticket, "exists"
        #
        # ticket_manager_role = await TicketService.get_ticket_manager_role(guild=guild)
        # open_ticket_category = await TicketService.create_or_get_ticket_category(guild=guild,category_name="Open Ticket", category_type="open")
        #
        # guild_settings = await GuildSettingService.get_guild_settings(guild=guild)
        # seller_role_id = guild_settings.seller_role_id
        # seller_role = None
        # if seller_role_id:
        #     seller_role = guild.get_role(seller_role_id)
        #
        # # 1. Create Channel
        # overwrites = {
        #     guild.default_role: discord.PermissionOverwrite(read_messages=False),
        #     user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        #     guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True),
        #     ticket_manager_role: discord.PermissionOverwrite(read_messages=True, manage_messages=True, read_message_history=True, send_messages=True),
        # }
        #
        # if seller_role:
        #     overwrites[seller_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True, manage_messages=True)
        #
        # # Determine topic
        # if category_path:
        #     topic = f"Order: {category_path}"
        # elif item:
        #     topic = f"Order: {item.name}"
        # else:
        #     topic = "Support Ticket"
        #
        # # Find or create category for tickets (simple implementation)
        # # category = discord.utils.get(guild.categories, name="Tickets")
        # # if not category: ...
        #
        # channel = await open_ticket_category.create_text_channel(
        #     name=f"ticket-{user.name[:10]}-{str(user.id)[-4:]}",
        #     overwrites=overwrites,
        #     topic=topic
        # )
        #
        # # 2. Create DB Entry
        # ticket = Ticket(
        #     user_id=user.id,
        #     channel_id=channel.id,
        #     guild_id=guild.id,
        #     status="open",
        #     topic=topic,
        #     related_item_id=str(item.id) if item else None,
        #     message_id= message_id
        # )
        #
        # result = await Database.tickets().insert_one(ticket.to_mongo())
        # ticket.id = result.inserted_id
        #
        # logger.info(f"Created ticket {ticket.id} for user {user.id} in channel {channel.id}")
        # await TicketService.send_logs_to_channel(
        #     guild=guild,
        #     title="Ticket Created",
        #     description=f"Ticket created for user {user.mention} in channel {channel.id}",
        #     color=discord.Color.green()
        # )
        # return ticket, "created"

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
    async def claim_ticket(ticket: Ticket, claimed_by: int, guild: discord.Guild) -> tuple[Ticket, bool]:
        """Claim a ticket"""
        try:
            doc = await Database.tickets().find_one_and_update(
                {
                    "_id": ticket.id,
                    "claimed_by": None
                },
                {
                    "$set": {"claimed_by": claimed_by}
                },
                return_document=ReturnDocument.AFTER,
            )

            if doc is None:
                # Someone already claimed it
                existing = await Database.tickets().find_one({"_id": ticket.id})
                return Ticket(**existing), False

            logger.info(f"Ticket claimed by {claimed_by} in channel {ticket.channel_id}")

            asyncio.create_task(
                TicketService.send_logs_to_channel(
                    guild=guild,
                    title=f"Ticket Claimed",
                    description=f"{ticket.id} was claimed by <@{claimed_by}>!",
                    color=discord.Color.blurple()
                )
            )

            return Ticket(**doc), True

        except Exception as e:
            logger.error(f"Failed to claim ticket: {e}")
            return ticket, False

    @staticmethod
    async def unclaim_ticket(ticket: Ticket, guild: discord.Guild):
        """Unclaim a ticket"""
        try:
            doc = await Database.tickets().find_one_and_update(
                {
                    "_id": ticket.id
                },
                {
                    "$set": {"claimed_by": None}
                },
                return_document=ReturnDocument.AFTER,
            )
            if doc is None:
                existing = await Database.tickets().find_one({"_id": ticket.id})
                return Ticket(**existing) if existing else None

            updated_ticket = Ticket(**doc)

            logger.info(f"Ticket {ticket.id} unclaimed in channel {ticket.channel_id}")

            asyncio.create_task(
                TicketService.send_logs_to_channel(
                    guild=guild,
                    title=f"Ticket Unclaimed",
                    description=f"Ticket {ticket.id} was unclaimed!",
                    color=discord.Color.yellow()
                )
            )

            return updated_ticket

        except Exception as e:
            logger.error(f"Failed to unclaim ticket: {e}")
            return None

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
            embeds: List[discord.Embed],
            content: str,
            interaction: discord.Interaction,
            channel: discord.TextChannel,
            button_name: str,
            button_emoji: str,
            raw_json
    ):
        from modules.tickets.ui import CustomTicketView
        from modules.shop.services_panels import ShopPanelService
        import secrets
        custom_id = secrets.token_hex(4)

        view = CustomTicketView(button_name=button_name, custom_id=custom_id, button_emoji=button_emoji)

        # check if there is an existing ticket panel in this channel
        # Use generic get_panel_by_channel with type="custom"
        existing_panel = await ShopPanelService.get_panel_by_channel(channel.id, "custom")

        if existing_panel:
            try:
                message = await channel.fetch_message(existing_panel.message_id)
                await message.edit(content=content, embeds=embeds, view=view)

                # Use generic update_panel
                await ShopPanelService.update_panel(
                    panel_id=existing_panel.id,
                    message_id=message.id,
                    embed_json=raw_json,
                    custom_id=custom_id
                )
                await interaction.followup.send("Ticket Panel Updated!", ephemeral=True)
                return
            except discord.NotFound:
                # Message was deleted, proceed to create new one
                await ShopPanelService.delete_panel(existing_panel.message_id)

        message = await channel.send(content=content, embeds=embeds, view=view)
        asyncio.create_task(
            ShopPanelService.create_panel(
                guild_id=interaction.guild.id,
                channel_id=channel.id,
                message_id=message.id,
                embed_json=raw_json,
                _type="custom",
                custom_id=custom_id
            )
        )

        await interaction.followup.send("Ticket Created!", ephemeral=True)

    @staticmethod
    async def directory_modal_callback(
            embeds: List[discord.Embed],
            content: str,
            interaction: discord.Interaction,
            channel: discord.TextChannel,
            button_name: str,  # unused
            button_emoji: str,  # unused
            raw_json
    ):
        from modules.shop.ui import ItemDirectoryView
        from modules.shop.services_panels import ShopPanelService
        from modules.shop.services import ItemService

        # Fetch active items directly from Item collection
        items = await ItemService.get_all_items(active_only=True)
        # Sort by newest (id desc) or name? User didn't specify, but newest is usually better for "directory" updates
        # MongoDB _id is time-ordered.
        items.sort(key=lambda x: x.id, reverse=True)

        if not items:
            await interaction.followup.send("❌ Cannot create directory: No active items found in database.",
                                            ephemeral=True)
            return

        view = ItemDirectoryView(items)

        # Check for existing directory panel
        existing_panel = await ShopPanelService.get_panel_by_channel(channel.id, "directory")

        if existing_panel:
            try:
                message = await channel.fetch_message(existing_panel.message_id)
                await message.edit(content=content, embeds=embeds, view=view)

                await ShopPanelService.update_panel(
                    panel_id=existing_panel.id,
                    message_id=message.id,
                    embed_json=raw_json
                )
                await interaction.followup.send("✅ Directory Panel Updated!", ephemeral=True)
                return
            except (discord.NotFound, discord.HTTPException):
                # Message deleted
                await ShopPanelService.delete_panel(existing_panel.message_id)

        message = await channel.send(content=content, embeds=embeds, view=view)
        asyncio.create_task(
            ShopPanelService.create_panel(
                guild_id=interaction.guild.id,
                channel_id=channel.id,
                message_id=message.id,
                embed_json=raw_json,
                _type="directory",
                custom_id="directory"
            )
        )

        await interaction.followup.send("✅ Directory Panel Created!", ephemeral=True)

    @staticmethod
    async def shop_panel_modal_callback(
            embeds: List[discord.Embed],
            content: str,
            interaction: discord.Interaction,
            channel: discord.TextChannel,
            button_name: str,
            button_emoji: str,
            raw_json
    ):
        """Callback for creating/updating a Shop Panel with Open Shop button."""
        from modules.tickets.ui import ShopPanelView
        from modules.shop.services_panels import ShopPanelService

        view = ShopPanelView(button_label=button_name, button_emoji=button_emoji)

        # Check for existing shop panel in this channel
        existing_panel = await ShopPanelService.get_panel_by_channel(channel.id, "shop")

        if existing_panel:
            try:
                message = await channel.fetch_message(existing_panel.message_id)
                await message.edit(content=content, embeds=embeds, view=view)

                await ShopPanelService.update_panel(
                    panel_id=existing_panel.id,
                    message_id=message.id,
                    embed_json=raw_json
                )
                await interaction.followup.send("✅ Shop Panel Updated!", ephemeral=True)
                return
            except (discord.NotFound, discord.HTTPException):
                await ShopPanelService.delete_panel(existing_panel.message_id)

        message = await channel.send(content=content, embeds=embeds, view=view)
        asyncio.create_task(
            ShopPanelService.create_panel(
                guild_id=interaction.guild.id,
                channel_id=channel.id,
                message_id=message.id,
                embed_json=raw_json,
                _type="shop",
                custom_id="shop_panel_open"
            )
        )

        await interaction.followup.send("✅ Shop Panel Created!", ephemeral=True)

    @staticmethod
    async def complete_order(interaction: discord.Interaction, root_view):
        await interaction.response.defer(ephemeral=True)
        ## Check Access
        manager_role = await TicketService.get_ticket_manager_role(guild=interaction.guild)
        seller_role = await GuildSettingService.get_seller_role(guild=interaction.guild)
        member = interaction.user
        member_role_ids = {role.id for role in member.roles}
        allowed = (
                member.id == settings.owner_id
                or member.guild_permissions.administrator
                or (manager_role and manager_role.id in member_role_ids)
                or (seller_role and seller_role.id in member_role_ids)
        )

        if not allowed:
            await interaction.followup.send("You are not allowed to do that!")
            return

        # 1. Get ticket details
        ticket = await TicketService.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            await interaction.followup.send("Ticket not found!", ephemeral=True)
            return

        if ticket.status != "open":
            await interaction.followup.send(f"The ticket status is not open!", ephemeral=True)
            return

        # 2. Get Item details if exists
        item = None
        if ticket.related_item_id:
            item = await ItemService.get_item(ticket.related_item_id)

        # 3. Log Transaction
        txn = Transaction(
            user_id=ticket.user_id,
            type='purchase',
            amount_tokens=item.price if item and item.currency == 'tokens' else 0,
            item_id=str(item.id) if item else None,
            item_name=item.name if item else "Custom Order",
            performed_by=interaction.user.id
        )
        asyncio.create_task(TransactionService.log_transaction(txn))

        # 3.5 Award Rewards (Tokens & XP)
        # Tokens
        ticket_user = interaction.guild.get_member(ticket.user_id)

        if item:
            tasks = []
            if item.token_reward > 0:
                tasks.append(
                    EconomyService.modify_tokens(
                        ticket.user_id,
                        item.token_reward,
                        f"Reward for purchasing {item.name}",
                        interaction.user.id
                    )
                )
                emoji = GuildSettingService.get_server_emoji(emoji_id=int(Emoji.SHOP_TOKEN.value),
                                                             guild=interaction.guild)
                tasks.append(
                    interaction.channel.send(
                        f"🎉 {ticket_user.mention} rewarded **{item.token_reward}** {emoji if emoji else "🪙"} Tokens!")
                )

                tasks.append(
                    ReputationService.add_rep(
                        user_id=interaction.user.id,
                        guild=interaction.guild,
                        reputation_amount=1
                    )
                )
                tasks.append(
                    interaction.channel.send(
                        f"{interaction.user.mention} has earned +1 Reputation <a:bluestar:1468261614200422471>.")
                )
                await asyncio.gather(*tasks, return_exceptions=True)
        else:
            await EconomyService.modify_tokens(
                ticket.user_id,
                10,
                f"Reward for purchasing",
                interaction.user.id
            )
            emoji = GuildSettingService.get_server_emoji(emoji_id=int(Emoji.SHOP_TOKEN.value), guild=interaction.guild)
            await interaction.channel.send(f"🎉 {ticket_user.mention} rewarded **10** {emoji if emoji else "🪙"} Tokens!")

            await ReputationService.add_rep(
                user_id=interaction.user.id,
                guild=interaction.guild,
                reputation_amount=1
            )
            await interaction.channel.send(
                f"{interaction.user.mention} has earned +1 Reputation <a:bluestar:1468261614200422471>.")

        # 4. Close Ticket

        channel_id = ticket.channel_id
        channel = interaction.guild.get_channel(channel_id)
        message = await channel.fetch_message(ticket.message_id)
        if not message or not message.embeds:
            logger.warning(f"No embeds found in message {ticket.message_id}")
            embed = None
        else:
            embed = message.embeds[0]

        await TicketService.close_ticket(ticket, interaction.user.id, interaction.client, interaction.guild)
        await message.edit(view=TicketClosedView(ticket_id=str(ticket.id), root_view=root_view), embed=embed)
        await interaction.followup.send("Order completed! formatting transcript...", ephemeral=True)

    @staticmethod
    async def close_ticket_btn(interaction: discord.Interaction, root_view):
        await interaction.response.defer(ephemeral=True)

        ticket_manager_role = await TicketService.get_ticket_manager_role(guild=interaction.guild)

        allowed = (
                interaction.user.guild_permissions.administrator or
                ticket_manager_role in interaction.user.roles
        )

        if not allowed:
            await interaction.followup.send(
                "You are not allowed to do that! Only admin and ticket manager can close ticket!", ephemeral=True)
            return

        ticket = await TicketService.get_ticket_by_channel(interaction.channel_id)
        if ticket:
            if ticket.status != "open":
                await interaction.followup.send(f"This ticket has already been closed!", ephemeral=True)
                return
            await TicketService.close_ticket(ticket, interaction.user.id, interaction.client, interaction.guild)
        else:
            await interaction.followup.send(f"Ticket not found!", ephemeral=True)
            return

        channel_id = ticket.channel_id
        channel = interaction.guild.get_channel(channel_id)
        message = await channel.fetch_message(ticket.message_id)
        if not message or not message.embeds:
            logger.warning(f"No embeds found in message {ticket.message_id}")
            embed = None
        else:
            embed = message.embeds[0]

        await interaction.followup.send("Closing ticket...", ephemeral=True)
        await message.edit(view=TicketClosedView(ticket_id=str(ticket.id), root_view= root_view), embed= embed)
        await interaction.channel.send(f"🔒 **Ticket Closed** by {interaction.user.mention}. Closing in 5 seconds.")

    @staticmethod
    async def claim_ticket_func(interaction: discord.Interaction, ticket_id, root_view):
        await interaction.response.defer(ephemeral=True)
        seller_role = await GuildSettingService.get_seller_role(interaction.guild)
        # 1. Check the claimer is a seller or admin or not
        if not seller_role:
            await interaction.followup.send("Seller role not configured", ephemeral=True)
            return

        allowed = (
                interaction.user.guild_permissions.administrator or
                seller_role in interaction.user.roles
        )
        if not allowed:
            await interaction.followup.send("To claim a ticket you must be an admin or a seller!", ephemeral=True)
            return

        ticket = await TicketService.get_ticket_by_channel(interaction.channel_id)

        if interaction.user.id == ticket.user_id:
            await interaction.followup.send("You cannot claim a ticket!", ephemeral=True)
            return

        if ticket:
            if ticket.status != "open":
                await interaction.followup.send("You can not claim this ticket!", ephemeral=True)
                return
            ticket, status = await TicketService.claim_ticket(ticket, interaction.user.id, interaction.guild)
            if not status:
                await interaction.followup.send(f"Ticket already claimed by {interaction.user.mention}!", ephemeral=True)
                return
        else:
            await interaction.followup.send(f"Ticket not found!", ephemeral=True)
            return

        for item in root_view.children:
            if item.custom_id == f"claim_ticket_{ticket_id}":
                item.label = "Unclaim Ticket"
                item.emoji = "📍"
                item.style = discord.ButtonStyle.grey
                item.custom_id = f"unclaim_ticket_{ticket_id}"
                item.callback = root_view.unclaim_ticket_btn
                break

        channel: discord.TextChannel = interaction.channel
        msg = await channel.fetch_message(ticket.message_id)

        embed = msg.embeds[0]
        embed.add_field(
            name="📌 Claimed By",
            value=interaction.user.mention,
            inline=False
        )

        ticket_owner_id = ticket.user_id
        ticket_owner = interaction.guild.get_member(ticket_owner_id)
        overwrites = {}

        if ticket_owner:
            overwrites[ticket_owner] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

        overwrites[interaction.guild.default_role] = discord.PermissionOverwrite(
            view_channel=False,
        )

        overwrites[interaction.user] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_messages=True
        )

        overwrites[interaction.guild.me] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_messages=True
        )

        await msg.edit(
            content=f"{interaction.user.mention} {ticket_owner.mention}",
            embed=embed,
            view=root_view
        )

        item = None
        if ticket.related_item_id:
            item = await ItemService.get_item(ticket.related_item_id)

        channel_new_name = f"ticket-{interaction.user.name[:10]}-{item.name if item else ""}-{ticket_owner.name[:10]}-{str(ticket_owner.id)[-4:]}"

        await safe_channel_edit(channel=channel, overwrites=overwrites)
        asyncio.create_task(
            safe_channel_edit(channel=channel, name=channel_new_name, wait_for_cooldown=True)
        )
        await interaction.followup.send("Ticket claimed successfully!", ephemeral=True)

    @staticmethod
    async def unclaim_ticket_btn(interaction: discord.Interaction, root_view):
        await interaction.response.defer(ephemeral=True)

        seller_role = await GuildSettingService.get_seller_role(guild=interaction.guild)

        ticket = await TicketService.get_ticket_by_channel(channel_id=interaction.channel_id)
        if not ticket:
            await interaction.followup.send("Ticket not configured", ephemeral=True)
            return

        if ticket.status != "open":
            await interaction.followup.send("You can not unclaim this ticket!", ephemeral=True)
            return

        ticket_claimer_id = ticket.claimed_by

        ## Check permission

        allowed = (
                interaction.user.guild_permissions.administrator or
                interaction.user.id == ticket_claimer_id
        )

        if not allowed:
            await interaction.followup.send(f"You did not claimed this ticket and you are not an administrator!",
                                            ephemeral=True)
            return

        un_claimed_ticket = await TicketService.unclaim_ticket(ticket=ticket, guild=interaction.guild)

        for item in root_view.children:
            if item.custom_id == f"unclaim_ticket_{root_view.ticket_id}":
                item.label = "Claim Ticket"
                item.emoji = "📍"
                item.style = discord.ButtonStyle.green
                item.custom_id = f"claim_ticket_{root_view.ticket_id}"
                item.callback = root_view.claim_ticket_btn
                break

        channel: discord.TextChannel = interaction.channel
        msg = await channel.fetch_message(un_claimed_ticket.message_id)
        embed = msg.embeds[0]
        embed.remove_field(-1)

        ticket_owner_id = un_claimed_ticket.user_id
        ticket_owner = interaction.guild.get_member(ticket_owner_id)

        overwrites = {}
        if ticket_owner:
            overwrites[ticket_owner] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

        overwrites[interaction.guild.me] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_messages=True
        )
        if seller_role:
            overwrites[seller_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_messages=True
            )
        overwrites[interaction.guild.default_role] = discord.PermissionOverwrite(view_channel=False)

        await msg.edit(
            content=f"{ticket_owner.mention} {seller_role.mention if seller_role else ""}",
            embed=embed,
            view=root_view
        )

        item = None
        if ticket.related_item_id:
            item = await ItemService.get_item(ticket.related_item_id)

        # Reset channel name
        channel_new_name = f"ticket-{item.name if item else 'custom'}-{ticket_owner.name[:10]}-{str(ticket_owner.id)[-4:]}"

        await safe_channel_edit(channel=channel, overwrites=overwrites)
        asyncio.create_task(
            safe_channel_edit(channel=channel, name=channel_new_name, wait_for_cooldown=True)
        )

        await interaction.followup.send("Ticket unclaimed successfully!", ephemeral=True)


    @staticmethod
    async def delete_ticket_btn(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from modules.tickets.services import TicketService
        manager_role = await TicketService.get_ticket_manager_role(guild=interaction.guild)
        member = interaction.user
        allowed = (
                member.id == settings.owner_id
                or any(role.id == manager_role.id for role in member.roles)
                or member.guild_permissions.administrator
        )

        if not allowed:
            await interaction.followup.send("You are not allowed to do delete a ticket! Only administrators and ticket managers are allowed!", ephemeral=True)
            return

        ticket = await TicketService.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            await interaction.followup.send(f"Ticket not found!", ephemeral=True)
            return

        await TicketService.delete_ticket(ticket=ticket, delete_by_user=interaction.user.id, guild=interaction.guild)
        await interaction.channel.delete(reason="Ticket Deleted")
