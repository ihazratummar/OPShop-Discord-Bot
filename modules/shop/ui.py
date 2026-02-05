import discord
from discord.ui import View, Select, Button
from typing import List

from core.database import Database
from modules.guild.service import GuildSettingService
from modules.shop.models import Category, Item
from modules.shop.services import CategoryService, ItemService
from modules.tickets.models import Ticket
from modules.tickets.services import TicketService
from modules.tickets.ui import TicketControlView

PAGE_SIZE = 20


# --- Helper Methods ---
async def get_root_embed(categories: list, page: int = 0) -> discord.Embed:
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    visible_cats = categories[start:end]
    total = len(categories)

    embed = discord.Embed(
        title="🛒 OP Shop",
        description=f"Browse our categories below.\nPage {page + 1}/{(total // PAGE_SIZE) + 1}",
        color=discord.Color.blue()
    )

    desc_list = ""
    if not categories:
        desc_list = "No categories available."
    else:
        # Optimization: Fetch all counts in one go
        cat_ids = [str(c.id) for c in visible_cats]
        stats = await CategoryService.get_category_stats_batch(cat_ids)

        for cat in visible_cats:
            cat_stat = stats.get(str(cat.id), {'items': 0, 'subcats': 0})
            count = cat_stat['items']
            sub_count = cat_stat['subcats']

            desc = f"• **{cat.name}**"
            if sub_count > 0:
                desc += f" ({sub_count} subcats, {count} items)"
            else:
                desc += f" ({count} items)"
            desc_list += desc + "\n"

    embed.add_field(name="Categories", value=desc_list, inline=False)
    embed.set_footer(text="Select a category to view items.")
    return embed


async def get_category_embed(category: Category, subcategories: list, items: list, page: int = 0) -> discord.Embed:
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    visible_items = items[start:end]
    total_items = len(items)

    embed = discord.Embed(
        title=f"📂 {category.name}",
        description=category.description or "No description.",
        color=discord.Color.gold()
    )
    if category.image_url:
        embed.set_thumbnail(url=category.image_url)

    # Subcategories
    if subcategories:
        sub_list = ""
        # Optimization: Fetch counts for subcategories
        sub_ids = [str(s.id) for s in subcategories]
        stats = await CategoryService.get_category_stats_batch(sub_ids)

        for sub in subcategories:
            sub_stat = stats.get(str(sub.id), {'items': 0})
            sub_item_count = sub_stat['items']
            sub_list += f"• 📁 **{sub.name}** ({sub_item_count} items)\n"
        embed.add_field(name=f"Subcategories ({len(subcategories)})", value=sub_list, inline=False)

    # Items
    item_list = ""
    if not items:
        item_list = "*No items available.*"
    else:
        for item in visible_items:
            item_list += f"• **{item.name}** - {item.price:,.0f} {item.currency}\n"

        page_count = (total_items // PAGE_SIZE) + 1
        embed.set_footer(text=f"Page {page + 1}/{page_count} | Select an item to buy.")

    embed.add_field(name=f"Items ({total_items})", value=item_list, inline=False)
    return embed


async def get_item_embed(item: Item) -> discord.Embed:
    embed = discord.Embed(
        title=item.name,
        description=item.description,
        color=discord.Color.green()
    )
    if item.image_url:
        embed.set_image(url=item.image_url)

    embed.add_field(name="Price", value=f"{item.price:,.0f} {item.currency.title()}", inline=True)

    rewards = []
    if item.xp_reward > 0: rewards.append(f"+{item.xp_reward} XP")
    if item.token_reward > 0: rewards.append(f"+{item.token_reward} Tokens")
    if rewards:
        embed.add_field(name="Rewards", value=" | ".join(rewards), inline=True)

    return embed


# --- Views ---

class ShopRootView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.page = 0
        self.total_pages = 1

    async def init_view(self):
        await self.refresh(None, initial_setup=True)

    async def refresh(self, interaction: discord.Interaction, initial_setup: bool = False):
        self.clear_items()
        categories = await CategoryService.get_active_categories(parent_id=None)

        total = len(categories)
        self.total_pages = (total // PAGE_SIZE) + (1 if total % PAGE_SIZE > 0 else 0)
        self.total_pages = max(1, self.total_pages)
        if self.page >= self.total_pages: self.page = self.total_pages - 1

        start = self.page * PAGE_SIZE
        end = start + PAGE_SIZE
        visible_cats = categories[start:end]

        if visible_cats:
            self.add_item(ShopCategorySelect(visible_cats, self.user_id))

        # Navigation Buttons
        self.prev_btn.disabled = (self.page == 0)
        self.next_btn.disabled = (self.page >= self.total_pages - 1)

        self.add_item(self.prev_btn)
        self.add_item(self.next_btn)

        embed = await get_root_embed(categories, self.page)

        if initial_setup: return

        if interaction:
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="<", style=discord.ButtonStyle.secondary, row=1)
    async def prev_btn(self, interaction: discord.Interaction, button: Button):
        if self.page > 0:
            self.page -= 1
            await self.refresh(interaction)

    @discord.ui.button(label=">", style=discord.ButtonStyle.secondary, row=1)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if self.page < self.total_pages - 1:
            self.page += 1
            await self.refresh(interaction)


class ShopCategorySelect(Select):
    def __init__(self, categories, user_id, placeholder="Select Category..."):
        self.user_id = user_id
        options = [discord.SelectOption(label=c.name, value=str(c.id), emoji="📁") for c in categories]
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        cat_id = self.values[0]
        category = await CategoryService.get_category(cat_id)
        if category:
            view = ShopCategoryView(category, self.user_id)
            await view.refresh(interaction, initial=True)
        else:
            await interaction.response.send_message("Category not found.", ephemeral=True)


class ShopCategoryView(View):
    def __init__(self, category: Category, user_id: int):
        super().__init__(timeout=None)
        self.category = category
        self.user_id = user_id
        self.page = 0
        self.total_pages = 1

    async def refresh(self, interaction: discord.Interaction, initial: bool = False):
        self.clear_items()

        # 1. Subcategories
        subcategories = await CategoryService.get_active_categories(parent_id=str(self.category.id))
        if subcategories:
            self.add_item(ShopCategorySelect(subcategories, self.user_id, placeholder="Open Subcategory..."))

        # 2. Items
        items = await ItemService.get_items_by_category(str(self.category.id), active_only=True)

        # Pagination Items
        total = len(items)
        self.total_pages = (total // PAGE_SIZE) + (1 if total % PAGE_SIZE > 0 else 0)
        self.total_pages = max(1, self.total_pages)
        if self.page >= self.total_pages: self.page = self.total_pages - 1

        start = self.page * PAGE_SIZE
        end = start + PAGE_SIZE
        visible_items = items[start:end]

        if visible_items:
            self.add_item(ShopItemSelect(visible_items, self.user_id))

        self.prev_btn.disabled = (self.page == 0)
        self.next_btn.disabled = (self.page >= self.total_pages - 1)

        self.add_item(self.prev_btn)
        self.add_item(self.next_btn)
        self.add_item(self.back_btn)

        embed = await get_category_embed(self.category, subcategories, items, self.page)

        if interaction:
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="<", style=discord.ButtonStyle.secondary, row=2)
    async def prev_btn(self, interaction: discord.Interaction, button: Button):
        if self.page > 0:
            self.page -= 1
            await self.refresh(interaction)

    @discord.ui.button(label=">", style=discord.ButtonStyle.secondary, row=2)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if self.page < self.total_pages - 1:
            self.page += 1
            await self.refresh(interaction)

    @discord.ui.button(label="Up/Back", style=discord.ButtonStyle.secondary, row=3, emoji="⬆️")
    async def back_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()

        if self.category.parent_id:
            # Go to parent
            parent = await CategoryService.get_category(self.category.parent_id)
            if parent:
                view = ShopCategoryView(parent, self.user_id)
                await view.refresh(interaction, initial=True)
                return

        # Go to Root
        view = ShopRootView(self.user_id)
        await view.refresh(interaction)


class ShopItemSelect(Select):
    def __init__(self, items, user_id):
        self.user_id = user_id
        options = [discord.SelectOption(label=i.name, value=str(i.id), emoji="📦") for i in items]
        super().__init__(placeholder="View Item Details...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        item_id = self.values[0]
        item = await ItemService.get_item(item_id)
        if item:
            view = ShopItemView(item, self.user_id)
            embed = await get_item_embed(item)
            await interaction.response.edit_message(embed=embed, view=view)


class ShopItemView(View):
    def __init__(self, item: Item, user_id: int):
        super().__init__(timeout=None)
        self.item = item
        self.user_id = user_id

    @discord.ui.button(label="Buy Now", style=discord.ButtonStyle.green, emoji="🛒")
    async def buy_now(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Opening ticket...", ephemeral=True)
        try:
            ticket, status = await TicketService.create_ticket(
                interaction.user,
                interaction.guild,
                self.item
            )

            if status == "exists":
                channel = interaction.guild.get_channel(ticket.channel_id)
                await interaction.followup.send(
                    f"You already have an open ticket: {channel.mention}",
                    ephemeral=True
                )
                return

            channel = interaction.guild.get_channel(ticket.channel_id)

            if channel:
                embed = discord.Embed(
                    title=f"New Order: {self.item.name}",
                    description=f"Hello {interaction.user.mention}, please answer the questions below to complete your order.",
                    color=discord.Color.green()
                )
                if self.item.image_url:
                    embed.set_thumbnail(url=self.item.image_url)

                view = TicketControlView(str(ticket.id))
                message = await channel.send(content=f"{interaction.user.mention}", embed=embed, view=view)

                await Database.tickets().update_one(
                    {
                        "_id": ticket.id
                    },
                    {
                        "$set": {"message_id": message.id}
                    },
                    upsert=True
                )

                await interaction.followup.send(f"Ticket created: {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Failed to create ticket: {e}", ephemeral=True)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back_btn(self, interaction: discord.Interaction, button: Button):
        cat = await CategoryService.get_category(str(self.item.category_id))
        if cat:
            view = ShopCategoryView(cat, self.user_id)
            await view.refresh(interaction, initial=True)


# ========================================
# Enhanced Panel Components (Ephemeral Flow)
# ========================================

class OrderNowButton(Button):
    """Persistent Order Now button for shop panels."""

    def __init__(self, category_id: str):
        super().__init__(
            label="🛒 Order Now",
            style=discord.ButtonStyle.green,
            custom_id=f"order_now:{category_id}"
        )
        self.category_id = category_id

    async def callback(self, interaction: discord.Interaction):
        """Opens ephemeral shop UI locked to this category."""
        category = await CategoryService.get_category(self.category_id)
        if not category:
            await interaction.response.send_message("❌ Category not found.", ephemeral=True)
            return

        # Create ephemeral view locked to this category tree
        view = EphemeralShopView(
            root_category_id=self.category_id,
            current_category=category,
            category_path=[category.name]
        )
        await view.refresh(interaction)


class OrderNowView(View):
    """Persistent view with Order Now button for shop panels."""

    def __init__(self, category_id: str):
        super().__init__(timeout=None)
        self.category_id = category_id
        self.add_item(OrderNowButton(category_id))


class ItemOrderView(View):
    """Persistent view with Order button for item-specific panels."""

    def __init__(self, item_id: str):
        super().__init__(timeout=None)
        self.item_id = item_id
        self.add_item(ItemOrderButton(item_id))


class ItemOrderButton(Button):
    """Persistent Order button for item-specific panels - creates ticket directly."""

    def __init__(self, item_id: str):
        super().__init__(
            label="🛒 Order Now",
            style=discord.ButtonStyle.green,
            custom_id=f"item_order:{item_id}"
        )
        self.item_id = item_id

    async def callback(self, interaction: discord.Interaction):
        """Directly creates a ticket for this item."""
        await interaction.response.defer(ephemeral=True)

        try:
            item = await ItemService.get_item(self.item_id)
            if not item:
                await interaction.followup.send("❌ Item not found.", ephemeral=True)
                return

            # Get category name for context
            category = await CategoryService.get_category(item.category_id)
            category_path = category.name if category else "Unknown"

            # Create ticket directly
            ticket, status = await TicketService.create_ticket(
                interaction.user,
                interaction.guild,
                item,
                category_path=f"{category_path} > {item.name}",
                message_id=interaction.message.id
            )
            if status == "exists":
                channel = interaction.guild.get_channel(ticket.channel_id)
                await interaction.followup.send(
                    f"You already have an open ticket: {channel.mention}",
                    ephemeral=True
                )
                return

            channel = interaction.guild.get_channel(ticket.channel_id)

            if channel:
                embed = discord.Embed(
                    title=f"🎫 New Order: {item.name}",
                    description=f"**Customer:** {interaction.user.mention}",
                    color=discord.Color.green()
                )
                if item.image_url:
                    embed.set_thumbnail(url=item.image_url)
                embed.add_field(name="Price", value=f"{item.price:,.0f} {item.currency}", inline=True)
                embed.add_field(name="Category", value=category_path, inline=True)

                guild_setting = await GuildSettingService.get_guild_settings(interaction.guild)
                seller_role = None
                if guild_setting:
                    seller_role_id = guild_setting.seller_role_id
                    if seller_role_id:
                        seller_role = interaction.guild.get_role(seller_role_id)

                view = TicketControlView(str(ticket.id), is_item_ticket=True)
                message = await channel.send(content=f"{interaction.user.mention} {seller_role.mention if seller_role else ""}", embed=embed, view=view)
                await Database.tickets().update_one(
                    {"_id": ticket.id},
                    {"$set": {"message_id": message.id}},
                    upsert=True
                )
                await interaction.followup.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)


class EphemeralCategorySelect(Select):
    """Dropdown for subcategories in ephemeral flow."""

    def __init__(self, subcategories: list, view_ref: 'EphemeralShopView'):
        self.view_ref = view_ref
        options = [
            discord.SelectOption(label=c.name, value=str(c.id), emoji="📁")
            for c in subcategories
        ]
        super().__init__(placeholder="Select Subcategory...", options=options)

    async def callback(self, interaction: discord.Interaction):
        cat_id = self.values[0]
        category = await CategoryService.get_category(cat_id)
        if category:
            new_path = self.view_ref.category_path + [category.name]
            view = EphemeralShopView(
                root_category_id=self.view_ref.root_category_id,
                current_category=category,
                category_path=new_path
            )
            await view.refresh(interaction)


class EphemeralItemSelect(Select):
    """Dropdown for items in ephemeral flow."""

    def __init__(self, items: list, view_ref: 'EphemeralShopView'):
        self.view_ref = view_ref
        self.items = items
        options = [
            discord.SelectOption(label=i.name, value=str(i.id), emoji="📦")
            for i in items
        ]
        super().__init__(placeholder="Select Item...", options=options)

    async def callback(self, interaction: discord.Interaction):
        item_id = self.values[0]
        item = await ItemService.get_item(item_id)
        if item:
            view = EphemeralItemView(
                item=item,
                root_category_id=self.view_ref.root_category_id,
                category_path=self.view_ref.category_path
            )
            embed = await get_item_embed(item)
            embed.add_field(name="Category", value=" > ".join(self.view_ref.category_path), inline=False)
            await interaction.response.edit_message(embed=embed, view=view)


class EphemeralShopView(View):
    """Ephemeral shop browser locked to a category tree."""

    def __init__(self, root_category_id: str, current_category: Category, category_path: list):
        super().__init__(timeout=300)  # 5 min timeout for ephemeral
        self.root_category_id = root_category_id
        self.current_category = current_category
        self.category_path = category_path
        self.page = 0
        self.total_pages = 1

    async def refresh(self, interaction: discord.Interaction):
        self.clear_items()

        # Fetch subcategories and items
        subcategories = await CategoryService.get_active_categories(parent_id=str(self.current_category.id))
        items = await ItemService.get_items_by_category(str(self.current_category.id), active_only=True)

        # Add subcategory dropdown if any
        if subcategories:
            self.add_item(EphemeralCategorySelect(subcategories, self))

        # Add item dropdown if any
        if items:
            self.add_item(EphemeralItemSelect(items, self))

        # Back button (only if not at root of this panel's tree)
        if str(self.current_category.id) != self.root_category_id:
            self.add_item(EphemeralBackButton(self))

        # Build embed
        embed = await get_category_embed(self.current_category, subcategories, items, self.page)
        embed.set_footer(text=f"Path: {' > '.join(self.category_path)}")

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)


class EphemeralBackButton(Button):
    """Back button for ephemeral shop navigation."""

    def __init__(self, view_ref: EphemeralShopView):
        super().__init__(label="⬅️ Back", style=discord.ButtonStyle.secondary, row=4)
        self.view_ref = view_ref

    async def callback(self, interaction: discord.Interaction):
        # Go to parent category
        parent = await CategoryService.get_category(self.view_ref.current_category.parent_id)
        if parent:
            new_path = self.view_ref.category_path[:-1]  # Remove current from path
            view = EphemeralShopView(
                root_category_id=self.view_ref.root_category_id,
                current_category=parent,
                category_path=new_path if new_path else [parent.name]
            )
            await view.refresh(interaction)


class EphemeralItemView(View):
    """Ephemeral item details with Buy Now button."""

    def __init__(self, item: Item, root_category_id: str, category_path: list):
        super().__init__(timeout=300)
        self.item = item
        self.root_category_id = root_category_id
        self.category_path = category_path

    @discord.ui.button(label="🛒 Buy Now", style=discord.ButtonStyle.green)
    async def buy_now(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("🎫 Creating your order...", ephemeral=True)
        try:
            # Create ticket with category path context
            category_context = " > ".join(self.category_path + [self.item.name])
            ticket, status = await TicketService.create_ticket(
                interaction.user,
                interaction.guild,
                self.item,
                category_path=category_context
            )
            if status == "exists":
                channel = interaction.guild.get_channel(ticket.channel_id)
                await interaction.followup.send(
                    f"You already have an open ticket: {channel.mention}",
                    ephemeral=True
                )
                return

            channel = interaction.guild.get_channel(ticket.channel_id)

            if channel:
                embed = discord.Embed(
                    title=f"🎫 New Order: {self.item.name}",
                    description=f"**Customer:** {interaction.user.mention}\n**Category Path:** {category_context}",
                    color=discord.Color.green()
                )
                if self.item.image_url:
                    embed.set_thumbnail(url=self.item.image_url)
                embed.add_field(name="Price", value=f"{self.item.price:,.0f} {self.item.currency}", inline=True)

                view = TicketControlView(str(ticket.id))
                message = await channel.send(content=f"{interaction.user.mention}", embed=embed, view=view)
                await Database.tickets().update_one(
                    {"_id": ticket.id},
                    {"$set": {"message_id": message.id}},
                    upsert=True
                )
                await interaction.followup.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    @discord.ui.button(label="⬅️ Back", style=discord.ButtonStyle.secondary)
    async def back_btn(self, interaction: discord.Interaction, button: Button):
        # Go back to category view
        cat = await CategoryService.get_category(str(self.item.category_id))
        if cat:
            view = EphemeralShopView(
                root_category_id=self.root_category_id,
                current_category=cat,
                category_path=self.category_path
            )
            await view.refresh(interaction)
