import asyncio
import json
import random
import uuid
from uuid import UUID

import discord
from discord import TextStyle, Interaction
from discord.ui import View, Button, TextInput, Modal
from typing_extensions import override

from core.config import settings
from core.constant import Emoji
from core.database import Database, logger
from modules.economy.models import Transaction
from modules.economy.services import TransactionService, EconomyService
from modules.guild.service import GuildSettingService
from modules.reputation.service import ReputationService
from modules.shop.services import ItemService
from modules.tickets.models import TicketSettingsModel, Ticket
from modules.tickets.services import TicketService
from modules.xp.services import XPService


async def get_ticket_settings_embed(guild_id: int) -> discord.Embed:
    data = await TicketService.get_ticket_settings(guild_id)

    if not data:
        raise RuntimeError("Ticket settings not found!")

    def channel_or_placeholder(channel_id, text):
        return f"<#{channel_id}>" if channel_id else f"⚠ {text}"

    def role_or_placeholder(role_id, text):
        return f"<@&{role_id}>" if role_id else f"⚠ {text}"

    embed = discord.Embed(
        title="🎟 Ticket System Settings",
        description=(
            "Configure how purchase tickets are created, managed, and archived.\n"
            "Only administrators should modify these settings."
        ),
        color=discord.Color.green()
    )

    embed.add_field(
        name="📂 Ticket Settings",
        value="────────────────────────────────────",
        inline=False
    )

    embed.add_field(
        name="Open Category",
        value=channel_or_placeholder(data.open_ticket_category_id, "Not configured"),
        inline=True
    )

    embed.add_field(
        name="Closed Category",
        value=channel_or_placeholder(data.close_ticket_category_id, "Not configured"),
        inline=True
    )

    embed.add_field(
        name="Log Channel",
        value=channel_or_placeholder(data.ticket_logs_channel_id, "Not configured"),
        inline=True
    )

    embed.add_field(
        name="Transcript Channel",
        value=channel_or_placeholder(data.ticket_transcript_channel_id, "Not configured"),
        inline=True
    )

    embed.add_field(
        name="👥 Staff Role",
        value=role_or_placeholder(data.ticket_manager_role_id, "Manager role not set"),
        inline=True
    )

    embed.set_footer(text="Ticket System • OPShop")

    return embed


class TicketPanelModal(discord.ui.Modal):
    def __init__(self, root_view: discord.ui.View, ticket_data: TicketSettingsModel):
        super().__init__(timeout=None, title="Ticket Panel Settings")
        self.root_view = root_view
        self.ticket_data = ticket_data

        self.open_ticket_category_id_input = TextInput(
            label="Open Ticket Category Id",
            style=TextStyle.short,
            custom_id="open_ticket_category_id",
            placeholder="1423254451120246944",
            default=self.ticket_data.open_ticket_category_id,
            required=True,
            min_length=15,
            max_length=20
        )
        self.close_ticket_category_id_input = TextInput(
            label="Close Ticket Category Id",
            style=TextStyle.short,
            custom_id="close_ticket_category_id",
            placeholder="1423254451120246944",
            default=self.ticket_data.close_ticket_category_id,
            required=True,
            min_length=15,
            max_length=20
        )
        self.ticket_logs_channel_id_input = TextInput(
            label="Ticket logs channel Id",
            style=TextStyle.short,
            custom_id="ticket_logs_channel_id",
            placeholder="1423254451120246944",
            default=self.ticket_data.ticket_logs_channel_id,
            required=True,
            min_length=15,
            max_length=20
        )
        self.ticket_transcript_channel_id_input = TextInput(
            label="Ticket transcript channel Id",
            style=TextStyle.short,
            custom_id="ticket_transcript_channel_id",
            placeholder="1423254451120246944",
            default=self.ticket_data.ticket_logs_channel_id,
            required=True,
            min_length=15,
            max_length=20
        )

        self.ticket_manager_role_id_input = TextInput(
            label="Ticket manager role Id",
            style=TextStyle.short,
            custom_id="ticket_manager_role_id",
            placeholder="1423254451120246944",
            default=self.ticket_data.ticket_manager_role_id,
            required=True,
            min_length=15,
            max_length=20
        )
        self.add_item(self.open_ticket_category_id_input)
        self.add_item(self.close_ticket_category_id_input)
        self.add_item(self.ticket_logs_channel_id_input)
        self.add_item(self.ticket_transcript_channel_id_input)
        self.add_item(self.ticket_manager_role_id_input)

    async def on_submit(self, interaction: Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        def is_category(cid: int) -> bool:
            ch = interaction.guild.get_channel(cid)
            return isinstance(ch, discord.CategoryChannel)

        def is_channel(cid: int) -> bool:
            return interaction.guild.get_channel(cid) is not None

        def is_role(rid: int) -> bool:
            return interaction.guild.get_role(rid) is not None

        error_messages = []

        def parse(value: str, name: str):
            try:
                return int(value)
            except ValueError:
                error_messages.append(f"{name} must be a numeric ID.")
                return None

        open_category_id = parse(self.open_ticket_category_id_input.value, "Open category")
        close_category_id = parse(self.close_ticket_category_id_input.value, "Close category")
        logs_id = parse(self.ticket_logs_channel_id_input.value, "Logs channel")
        transcript_id = parse(self.ticket_transcript_channel_id_input.value, "Transcript channel")
        role_id = parse(self.ticket_manager_role_id_input.value, "Manager role")

        if open_category_id and not is_category(open_category_id):
            error_messages.append("Open category not found.")
        if close_category_id and not is_category(close_category_id):
            error_messages.append("Close category not found.")
        if logs_id and not is_channel(logs_id):
            error_messages.append("Logs channel not found.")
        if transcript_id and not is_channel(transcript_id):
            error_messages.append("Transcript channel not found.")
        if role_id and not is_role(role_id):
            error_messages.append("Manager role not found.")

        if error_messages:
            await interaction.followup.send("\n".join(error_messages), ephemeral=True)
            return

        data = TicketSettingsModel(
            guild_id=interaction.guild_id,
            open_ticket_category_id=open_category_id,
            close_ticket_category_id=close_category_id,
            ticket_logs_channel_id=logs_id,
            ticket_transcript_channel_id=transcript_id,
            ticket_manager_role_id=role_id
        )

        await Database.ticket_settings().update_one(
            {"guild_id": interaction.guild_id},
            {"$set": data.model_dump()},
            upsert=True
        )

        embed = await get_ticket_settings_embed(interaction.guild_id)
        await interaction.edit_original_response(embed=embed, view=self.root_view)


class TicketSettingsView(View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.blurple, emoji="✏️")
    async def edit_ticket_panel(self, interaction: discord.Interaction, button: Button):
        ticket_settings = await TicketService.get_ticket_settings(self.guild_id)
        modal = TicketPanelModal(root_view=self, ticket_data=ticket_settings)
        await interaction.response.send_modal(modal)


class TicketControlView(View):
    def __init__(self, ticket_id: str, is_custom_ticket: bool = False, is_item_ticket: bool = False):
        super().__init__(timeout=None)  # Persistent view logic needs setup, for now simple
        self.ticket_id = ticket_id
        self.is_custom_ticket = is_custom_ticket
        self.is_item_ticket = is_item_ticket

        complete_button = discord.ui.Button(
            label="Complete Order",
            style=discord.ButtonStyle.green,
            emoji="✅",
            custom_id=f"complete_order_{ticket_id}",
        )
        complete_button.callback = self.complete_order

        close_button = discord.ui.Button(
            label="Close",
            style=discord.ButtonStyle.red,
            emoji="🔒",
            custom_id=f"close_order_{ticket_id}",
        )
        close_button.callback = self.close_ticket_btn

        claim_ticket_button = discord.ui.Button(
            label="Claim Ticket",
            style=discord.ButtonStyle.green,
            emoji="📌",
            custom_id=f"claim_ticket_{ticket_id}",
        )
        claim_ticket_button.callback = self.claim_ticket_btn

        if not self.is_custom_ticket:
            self.add_item(complete_button)

        if self.is_item_ticket:
            self.add_item(claim_ticket_button)

        self.add_item(close_button)

    async def complete_order(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        ## Check Access
        manager_role = await TicketService.get_ticket_manager_role(guild=interaction.guild)
        member = interaction.user
        allowed = (
                member.id == settings.owner_id
                or any(role.id == manager_role.id for role in member.roles)
                or member.guild_permissions.administrator
        )

        if not allowed:
            await interaction.followup.send("You are not allowed to do that!")
            return

        # 1. Get ticket details
        ticket = await TicketService.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            await interaction.followup.send("Ticket not found!", ephemeral=True)
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
        if item:
            # Tokens
            ticket_user = interaction.guild.get_member(ticket.user_id)
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
                emoji = GuildSettingService.get_server_emoji(emoji_id=int(Emoji.SHOP_TOKEN.value), guild= interaction.guild)
                tasks.append(
                    interaction.channel.send(
                        f"🎉 {ticket_user.mention} rewarded **{item.token_reward}** {emoji if emoji else "🪙"} Tokens!")
                )

                tasks.append(
                    ReputationService.add_rep(
                        user_id=interaction.user.id,
                        guild = interaction.guild,
                        reputation_amount=1
                    )
                )
                tasks.append(
                    interaction.channel.send(
                        f"{interaction.user.mention} has earned +1 <a:bluestar:1468261614200422471>.")
                )
                await asyncio.gather(*tasks, return_exceptions=True)


        # 4. Close Ticket
        await TicketService.close_ticket(ticket, interaction.user.id, interaction.client, interaction.guild)
        await interaction.edit_original_response(view=TicketClosedView(ticket_id=self.ticket_id, root_view=self))
        await interaction.followup.send("Order completed! formatting transcript...", ephemeral=True)

    async def close_ticket_btn(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        ticket = await TicketService.get_ticket_by_channel(interaction.channel_id)
        if ticket:
            await TicketService.close_ticket(ticket, interaction.user.id, interaction.client, interaction.guild)

        await interaction.followup.send("Closing ticket...", ephemeral=True)
        await interaction.edit_original_response(view=TicketClosedView(ticket_id=self.ticket_id, root_view=self))
        await interaction.channel.send(f"🔒 **Ticket Closed** by {interaction.user.mention}. Closing in 5 seconds.")

    async def claim_ticket_btn(self, interaction: discord.Interaction):
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
            ticket, status = await TicketService.claim_ticket(ticket, interaction.user.id, interaction.guild)
            if not status:
                await interaction.followup.send(f"Ticket already claimed by {interaction.user.mention}!",
                                                ephemeral=True)
                return

        for item in self.children:
            if item.custom_id == f"claim_ticket_{self.ticket_id}":
                item.disabled = True
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
            view=self
        )

        await channel.edit(overwrites=overwrites)


class TicketClosedView(View):
    def __init__(self, ticket_id: str, root_view: discord.ui.View):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.root_view = root_view

        delete_btn = discord.ui.Button(
            label="Delete Ticket",
            style=discord.ButtonStyle.red,
            emoji="🗑️",
            custom_id=f"close_ticket_{ticket_id}",
        )
        delete_btn.callback = self.delete_ticket_btn
        self.add_item(delete_btn)

    async def delete_ticket_btn(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        manager_role = await TicketService.get_ticket_manager_role(guild=interaction.guild)
        member = interaction.user
        allowed = (
                member.id == settings.owner_id
                or any(role.id == manager_role.id for role in member.roles)
                or member.guild_permissions.administrator
        )

        if not allowed:
            await interaction.followup.send("You are not allowed to do that!")
            return

        ticket = await TicketService.get_ticket_by_channel(interaction.channel_id)
        await TicketService.delete_ticket(ticket=ticket, delete_by_user=interaction.user.id, guild=interaction.guild)
        await interaction.channel.delete(reason="Ticket Deleted")


class EmbedJsonModal(Modal):
    """
    Reusable modal that parses Discohook JSON
    and returns a discord.Embed via callback.
    """

    def __init__(self, title: str, channel: discord.TextChannel, button_name: str, button_emoji: str, on_success):
        super().__init__(title=title)

        self.on_success = on_success  # async callback(embed, interaction, channel, button_name, raw_json)
        self.button_name = button_name
        self.channel = channel
        self.button_emoji = button_emoji

        self.json_input = TextInput(
            label="Discohook Embed JSON",
            placeholder="Paste embed JSON here",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=4000,
        )

        self.add_item(self.json_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        raw_json = self.json_input.value.strip()

        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            await interaction.followup.send(f"❌ Invalid JSON: `{e}`", ephemeral=True)
            return

        embed_data = None

        if isinstance(data, dict):
            if isinstance(data.get("embeds"), list) and data["embeds"]:
                embed_data = data["embeds"][0]
            elif "title" in data or "description" in data:
                embed_data = data
        elif isinstance(data, list) and data:
            embed_data = data[0]

        if not embed_data:
            await interaction.followup.send(
                "❌ No valid embed found.",
                ephemeral=True
            )
            return

        embed = discord.Embed.from_dict(embed_data)

        try:
            await self.on_success(embed, interaction, self.channel, self.button_name, self.button_emoji,  raw_json)
        except Exception:
            logger.exception("Embed modal callback failed")
            await interaction.followup.send(
                "❌ Failed while processing embed.",
                ephemeral=True
            )


class CustomTicketView(View):
    def __init__(self, custom_id: str, button_emoji: str = "🎟️",  button_name: str = "Create Ticket", ):
        super().__init__(timeout=None)
        self.button_name = button_name
        self.custom_id = custom_id
        self.button_emoji = button_emoji
        self.add_item(CustomTicketButton(label=self.button_name, custom_id=self.custom_id, button_emoji= self.button_emoji))


class CustomTicketButton(Button):
    def __init__(self, label: str, custom_id: str,button_emoji: str):
        super().__init__(
            label=label,
            emoji= button_emoji,
            custom_id=f"custom_button_{custom_id}"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            ### Create ticket
            ticket, status = await TicketService.create_ticket(
                user=interaction.user,
                guild=interaction.guild,
            )

            if status == "exists":
                channel = interaction.guild.get_channel(ticket.channel_id)
                await interaction.followup.send(
                    f"You already have an open ticket: {channel.mention}",
                    ephemeral=True
                )
                return

            channel = interaction.guild.get_channel(ticket.channel_id)
            view = TicketControlView(str(ticket.id), is_custom_ticket=True)
            ticket_manager = await TicketService.get_ticket_manager_role(guild=interaction.guild)
            message = await channel.send(content=f"{interaction.user.mention}, {ticket_manager.mention}", view=view)
            await Database.tickets().update_one(
                {"_id": ticket.id},
                {"$set": {"message_id": message.id}},
                upsert=True
            )
            await interaction.followup.send(f"✅ Ticket Created in {channel.mention}!", ephemeral=True)



        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)
