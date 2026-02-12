import json

import discord
from discord import TextStyle, Interaction
from discord.ui import View, Button, TextInput, Modal

from core.config import settings
from core.database import Database, logger
from modules.guild.service import GuildSettingService
from modules.tickets.models import TicketSettingsModel


async def get_ticket_settings_embed(guild_id: int) -> discord.Embed:
    from modules.tickets.services import TicketService
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
        from modules.tickets.services import TicketService
        ticket_settings = await TicketService.get_ticket_settings(self.guild_id)
        modal = TicketPanelModal(root_view=self, ticket_data=ticket_settings)
        await interaction.response.send_modal(modal)


class TicketControlView(View):
    def __init__(self, ticket_id: str, is_custom_ticket: bool = False, is_item_ticket: bool = False,
                 claimed_by: int = None):
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

        # Create claim button based on current state
        if claimed_by:
            # Ticket is already claimed - show Unclaim button
            claim_ticket_button = discord.ui.Button(
                label="Unclaim Ticket",
                style=discord.ButtonStyle.grey,
                emoji="📍",
                custom_id=f"unclaim_ticket_{ticket_id}",
            )
            claim_ticket_button.callback = self.unclaim_ticket_btn
        else:
            # Ticket not claimed - show Claim button
            claim_ticket_button = discord.ui.Button(
                label="Claim Ticket",
                style=discord.ButtonStyle.green,
                emoji="📌",
                custom_id=f"claim_ticket_{ticket_id}",
            )
            claim_ticket_button.callback = self.claim_ticket_btn

        self.add_item(complete_button)
        self.add_item(claim_ticket_button)
        self.add_item(close_button)

    async def complete_order(self, interaction: discord.Interaction):
        from modules.tickets.services import TicketService
        await TicketService.complete_order(interaction= interaction, root_view= self)

    async def close_ticket_btn(self, interaction: discord.Interaction):
        from modules.tickets.services import TicketService
        await TicketService.close_ticket_btn(interaction= interaction, root_view= self)

    async def claim_ticket_btn(self, interaction: discord.Interaction):
        from modules.tickets.services import TicketService
        await TicketService.claim_ticket_func(interaction= interaction, ticket_id= self.ticket_id, root_view= self)


    async def unclaim_ticket_btn(self, interaction: discord.Interaction):
        from modules.tickets.services import TicketService
        await TicketService.unclaim_ticket_btn(interaction= interaction, root_view= self)


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
        from modules.tickets.services import TicketService
        await TicketService.delete_ticket_btn(interaction=interaction)


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

        embeds = []
        content = None

        if isinstance(data, dict):
            content = data.get("content")
            if "embeds" in data and isinstance(data["embeds"], list):
                for emp_data in data["embeds"]:
                    try:
                        embeds.append(discord.Embed.from_dict(emp_data))
                    except Exception:
                        pass  # Ignore invalid embeds
            elif "title" in data or "description" in data:
                # Single embed object at root
                embeds.append(discord.Embed.from_dict(data))
        elif isinstance(data, list):
            # List of embeds?
            for emp_data in data:
                if isinstance(emp_data, dict):
                    try:
                        embeds.append(discord.Embed.from_dict(emp_data))
                    except Exception:
                        pass

        if not embeds and not content:
            await interaction.followup.send(
                "❌ No valid content or embeds found in JSON.",
                ephemeral=True
            )
            return

        # Limit to 10 embeds (Discord limit)
        if len(embeds) > 10:
            embeds = embeds[:10]

        try:
            # Updated signature: embeds (list), content (str)
            await self.on_success(embeds, content, interaction, self.channel, self.button_name, self.button_emoji,
                                  raw_json)
        except Exception:
            logger.exception("Embed modal callback failed")
            await interaction.followup.send(
                "❌ Failed while processing embed callback.",
                ephemeral=True
            )


class CustomTicketView(View):
    def __init__(self, custom_id: str, button_emoji: str = "🎟️", button_name: str = "Create Ticket", ):
        super().__init__(timeout=None)
        self.button_name = button_name
        self.custom_id = custom_id
        self.button_emoji = button_emoji
        self.add_item(
            CustomTicketButton(label=self.button_name, custom_id=self.custom_id, button_emoji=self.button_emoji))


class CustomTicketButton(Button):
    def __init__(self, label: str, custom_id: str, button_emoji: str):
        super().__init__(
            label=label,
            emoji=button_emoji,
            custom_id=f"custom_button_{custom_id}"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            ### Create ticket
            from modules.tickets.services import TicketService
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
            guild_settings = await GuildSettingService.get_guild_settings(guild=interaction.guild)
            seller_role_id = guild_settings.seller_role_id
            seller_role = None
            if seller_role_id:
                seller_role = interaction.guild.get_role(seller_role_id)

            embed = discord.Embed(
                title="Ticket Created",
                description=f"{interaction.user.mention} has created a ticket.",
            )
            embed.add_field(
                name="Status",
                value=f"{ticket.status}",
                inline=True
            )
            embed.add_field(
                name="Ticket ID",
                value=f"{ticket.id}",
            )

            message = await channel.send(
                content=f"{interaction.user.mention}, {ticket_manager.mention} {seller_role.mention if seller_role else ""}",
                embed=embed, view=view)
            await Database.tickets().update_one(
                {"_id": ticket.id},
                {"$set": {"message_id": message.id}},
                upsert=True
            )
            await interaction.followup.send(f"✅ Ticket Created in {channel.mention}!", ephemeral=True)



        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)


# ========================================
# Shop Panel Components (Persistent)
# ========================================

class ShopPanelView(View):
    """Persistent view with a button to open the Shop."""

    def __init__(self, button_label: str = "Open Shop", button_emoji: str = None):
        super().__init__(timeout=None)
        self.add_item(ShopPanelButton(label=button_label, emoji=button_emoji))


class ShopPanelButton(Button):
    """Persistent button that opens the shop browser."""

    def __init__(self, label: str, emoji: str = None):
        super().__init__(
            label=label,
            style=discord.ButtonStyle.green,
            emoji=emoji,
            custom_id="shop_panel_open"  # Static ID for persistence
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            from modules.shop.ui import ShopRootView, get_root_embed
            from modules.shop.services import CategoryService

            view = ShopRootView(interaction.user.id)
            await view.init_view()

            categories = await CategoryService.get_active_categories()
            embed = await get_root_embed(categories= categories)

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to open shop: {e}", ephemeral=True)
