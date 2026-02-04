import discord
from discord.ui import View, Modal, TextInput, Select, Button
from modules.shop.services import CategoryService, ItemService, logger
from modules.shop.models import Category, Item
import json

PAGE_SIZE = 20

# --- Helper Methods ---
async def get_root_embed(categories: list, page: int = 0) -> discord.Embed:
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    visible_cats = categories[start:end]
    total = len(categories)
    
    if not categories:
        embed = discord.Embed(
            title="🛠️ Shop Admin Panel", 
            description="No categories found. Start by creating one!", 
            color=discord.Color.dark_gray()
        )
    else:
        embed = discord.Embed(
            title="🛠️ Shop Admin Panel (Root)", 
            description=f"**{total} Categories** found. (Page {page+1}/{(total // PAGE_SIZE) + 1})", 
            color=discord.Color.blue()
        )
        
        desc_list = ""
        # Optimization: Batch fetch
        cat_ids = [str(c.id) for c in visible_cats]
        stats = await CategoryService.get_category_stats_batch(cat_ids)
        
        for cat in visible_cats:
            # Count includes direct items and subcategories
            cat_stat = stats.get(str(cat.id), {'items': 0, 'subcats': 0})
            item_count = cat_stat['items']
            sub_count = cat_stat['subcats']
            desc_list += f"• **{cat.name}** - {sub_count} Subcats, {item_count} Items\n"
        
        embed.add_field(name="Root Categories", value=desc_list, inline=False)
    return embed

async def get_category_embed(category: Category, subcategories: list, items: list, page: int = 0) -> discord.Embed:
    # We paginate items, but show subcategories at the top (usually few)
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    visible_items = items[start:end]
    total_items = len(items)

    embed = discord.Embed(
        title=f"📂 Managing: {category.name}", 
        description=category.description or "No description", 
        color=discord.Color.gold()
    )
    if category.image_url:
        embed.set_thumbnail(url=category.image_url)
    
    embed.add_field(name="Details", value=f"Rank: {category.rank}\nID: `{category.id}`", inline=True)
    
    # Subcategories list
    if subcategories:
         sub_list = ""
         sub_ids = [str(s.id) for s in subcategories]
         stats = await CategoryService.get_category_stats_batch(sub_ids)
         
         for sub in subcategories:
             sub_stat = stats.get(str(sub.id), {'items': 0})
             sub_item_count = sub_stat['items']
             sub_list += f"• 📁 **{sub.name}** ({sub_item_count} items)\n"
         embed.add_field(name=f"Subcategories ({len(subcategories)})", value=sub_list, inline=False)
    
    # Item list
    item_list = ""
    if not items:
        item_list = "*No items in this category.*"
    else:
        for item in visible_items:
            status = "🟢" if item.is_active else "🔴"
            item_list += f"{status} **{item.name}** - {item.price:,.0f} {item.currency}\n"
        
        page_count = (total_items // PAGE_SIZE) + 1
        embed.set_footer(text=f"Page {page+1}/{page_count} | Total Items: {total_items}")
            
    embed.add_field(name=f"Items ({total_items})", value=item_list, inline=False)
    return embed

async def get_item_embed(item: Item, category_name: str) -> discord.Embed:
    embed = discord.Embed(
        title=f"📦 Managing: {item.name}", 
        description=item.description,
        color=discord.Color.green() if item.is_active else discord.Color.red()
    )
    if item.image_url:
        embed.set_image(url=item.image_url)
        
    embed.add_field(name="Price", value=f"{item.price:,.0f} {item.currency.title()}", inline=True)
    embed.add_field(name="Category", value=category_name, inline=True)
    embed.add_field(name="Status", value="Active" if item.is_active else "Inactive", inline=True)
    
    if item.token_reward > 0:
        embed.add_field(name="Reward", value=f"{item.token_reward} Tokens", inline=True)
        
    return embed

# --- Modals ---
class CategoryModal(Modal):
    def __init__(self, title: str, view_origin: View, category: Category = None, parent_id: str = None):
        super().__init__(title=title)
        self.view_origin = view_origin
        self.category = category
        self.parent_id = parent_id # For creating subcategories
        
        self.name_input = TextInput(label="Name", default=category.name if category else "", max_length=50)
        self.desc_input = TextInput(label="Description", default=category.description if category else "", required=False)
        self.rank_input = TextInput(label="Rank", default=str(category.rank) if category else "0")
        self.img_input = TextInput(label="Image URL", default=category.image_url if category else "", required=False)
        
        self.add_item(self.name_input)
        self.add_item(self.desc_input)
        self.add_item(self.rank_input)
        self.add_item(self.img_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            rank = int(self.rank_input.value)
        except ValueError:
            await interaction.response.send_message("Rank must be number.", ephemeral=True)
            return

        data = {
            "name": self.name_input.value,
            "description": self.desc_input.value,
            "rank": rank,
            "image_url": self.img_input.value
        }
        
        if self.parent_id:
             data["parent_id"] = self.parent_id

        if self.category:
            await CategoryService.update_category(str(self.category.id), data)
            msg = "Updated category!"
        else:
            cat = Category(**data)
            await CategoryService.create_category(cat)
            msg = "Created category!"
        
        # Refresh Panels
        from modules.shop.services_panels import ShopPanelService
        await ShopPanelService.refresh_all_panels(interaction.client)

        await interaction.response.send_message(msg, ephemeral=True)
        if hasattr(self.view_origin, 'refresh'):
            await self.view_origin.refresh(interaction)

class ItemModal(Modal):
    def __init__(self, title: str, view_origin: View, category_id: str, item: Item = None):
        super().__init__(title=title)
        self.view_origin = view_origin
        self.category_id = category_id
        self.item = item
        self.name_input = TextInput(label="Name", default=item.name if item else "")
        self.price_input = TextInput(label="Price", default=str(item.price) if item else "0")
        self.desc_input = TextInput(label="Description", default=item.description if item else "", required=False, style=discord.TextStyle.paragraph)
        self.img_input = TextInput(label="Image URL", default=item.image_url if item else "", required=False)
        self.reward_token = TextInput(label="Reward Shop Token", default= item.token_reward if item else "10", required=False, style=discord.TextStyle.short)

        self.add_item(self.name_input)
        self.add_item(self.price_input)
        self.add_item(self.desc_input)
        self.add_item(self.img_input)
        self.add_item(self.reward_token)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            price = float(self.price_input.value)
        except ValueError:
            await interaction.response.send_message("Price must be number.", ephemeral=True)
            return
        try:
            token_reward = int(self.reward_token.value)
        except ValueError:
            await interaction.response.send_message("Reward token must be number.", ephemeral=True)
            return
            
        data = {
            "name": self.name_input.value,
            "price": price,
            "description": self.desc_input.value,
            "category_id": self.category_id,
            "image_url": self.img_input.value,
            "token_reward" : token_reward
        }


        
        if self.item:
            await ItemService.update_item(str(self.item.id), data)
            msg = "Updated item!"
        else:
            item = Item(**data)
            await ItemService.create_item(item)
            msg = "Created item!"
            
        await interaction.edit_original_response(content=msg, view= self.view_origin)
        if hasattr(self.view_origin, 'refresh'):
            await self.view_origin.refresh(interaction)

class EmbedJsonModal(Modal):
    """Modal for pasting Discohook embed JSON when creating a shop panel."""

    def __init__(self, category_id: str, channel: discord.TextChannel):
        super().__init__(title="Create Shop Panel")

        self.category_id = category_id
        self.channel = channel

        self.json_input = TextInput(
            label="Discohook Embed JSON",
            placeholder="Paste the JSON from Discohook here (embeds array or single object)",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=4000,
        )

        self.add_item(self.json_input)

    async def on_submit(self, interaction: discord.Interaction):
        # ✅ Lazy imports
        from modules.shop.services import CategoryService
        from modules.shop.services_panels import ShopPanelService
        from modules.shop.ui import OrderNowView

        # ✅ Defer immediately, ephemeral
        await interaction.response.defer(ephemeral=True)

        try:
            # Validate category
            category = await CategoryService.get_category(self.category_id)
            if not category:
                await interaction.followup.send(
                    f"❌ Category `{self.category_id}` not found.",
                    ephemeral=True
                )
                return

            raw_json = self.json_input.value.strip()

            # Parse JSON
            try:
                data = json.loads(raw_json)
            except json.JSONDecodeError as e:
                await interaction.followup.send(
                    f"❌ Invalid JSON: `{e}`",
                    ephemeral=True
                )
                return

            # Extract embed data (Discohook formats)
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
                    "❌ No valid embed found. Ensure the JSON contains an embed with `title` or `description`.",
                    ephemeral=True
                )
                return

            # Create embed
            embed = discord.Embed.from_dict(embed_data)

            # Create view
            view = OrderNowView(category_id=self.category_id)

            # Post panel
            message = await self.channel.send(embed=embed, view=view)

            # Persist panel
            await ShopPanelService.create_panel(
                guild_id=interaction.guild_id,
                channel_id=self.channel.id,
                message_id=message.id,
                category_id=self.category_id,
                embed_json=raw_json,
                _type="category"
            )

            await interaction.followup.send(
                f"✅ Shop panel created in {self.channel.mention}!",
                ephemeral=True
            )

        except Exception:
            logger.exception("Failed to create shop panel")
            await interaction.followup.send(
                "❌ An unexpected error occurred while creating the panel.",
                ephemeral=True
            )


class ItemEmbedJsonModal(Modal):
    """Modal for pasting Discohook embed JSON when creating an item-specific panel."""
    def __init__(self, item_id: str, channel: discord.TextChannel):
        super().__init__(title="Create Item Panel")
        self.item_id = item_id
        self.channel = channel
        
        self.json_input = TextInput(
            label="Discohook Embed JSON",
            placeholder='Paste the JSON from Discohook here',
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=4000
        )
        self.add_item(self.json_input)

    async def on_submit(self, interaction: discord.Interaction):
        import json
        from modules.shop.services import ItemService
        from modules.shop.services_panels import ShopPanelService
        from modules.shop.ui import ItemOrderView
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Validate item exists
            item = await ItemService.get_item(self.item_id)
            if not item:
                await interaction.followup.send(f"❌ Item `{self.item_id}` not found.", ephemeral=True)
                return
            
            raw_json = self.json_input.value.strip()
            
            # Parse JSON
            try:
                data = json.loads(raw_json)
            except json.JSONDecodeError as e:
                await interaction.followup.send(f"❌ Invalid JSON: {e}", ephemeral=True)
                return
            
            # Handle Discohook format
            embed_data = None
            if isinstance(data, dict):
                if "embeds" in data and isinstance(data["embeds"], list) and len(data["embeds"]) > 0:
                    embed_data = data["embeds"][0]
                elif "title" in data or "description" in data:
                    embed_data = data
            elif isinstance(data, list) and len(data) > 0:
                embed_data = data[0]
                
            if not embed_data:
                await interaction.followup.send("❌ Could not find valid embed in JSON.", ephemeral=True)
                return
            
            # Create embed and view
            embed = discord.Embed.from_dict(embed_data)
            view = ItemOrderView(item_id=self.item_id)
            
            # Post to channel
            message = await self.channel.send(embed=embed, view=view)
            
            # Save panel to DB (using item_id in category_id field for simplicity, or we can add item_id field)
            await ShopPanelService.create_panel(
                guild_id=interaction.guild_id,
                channel_id=self.channel.id,
                message_id=message.id,
                category_id=f"item:{self.item_id}",  # Mark as item panel
                embed_json=raw_json,
                _type="item"
            )
            
            await interaction.followup.send(f"✅ Item panel created in {self.channel.mention}!", ephemeral=True)
            
        except Exception as e:
            logger.exception("Failed to create item panel")
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

# --- Views ---

class AdminRootView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.page = 0
        self.total_pages = 1
        
    async def init_view(self):
         await self.refresh(None, initial_setup=True)
         
    @discord.ui.button(label="<", style=discord.ButtonStyle.secondary, row=1)
    async def prev_btn(self, interaction: discord.Interaction, button: Button):
        if self.page > 0:
            self.page -= 1
            await self.refresh(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label=">", style=discord.ButtonStyle.secondary, row=1)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if self.page < self.total_pages - 1:
            self.page += 1
            await self.refresh(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Create Category", style=discord.ButtonStyle.green, row=1)
    async def create_cat(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(CategoryModal("Create Root Category", self, parent_id=None))

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, row=1)
    async def refresh_btn(self, interaction: discord.Interaction, button: Button):
        await self.refresh(interaction)

    async def refresh(self, interaction: discord.Interaction, initial_setup: bool = False):
        self.clear_items()
        # Fetch Root Categories (parent_id=None)
        categories = await CategoryService.get_all_categories(parent_id=None)
        
        # Calculate Pages
        total = len(categories)
        self.total_pages = (total // PAGE_SIZE) + (1 if total % PAGE_SIZE > 0 else 0)
        self.total_pages = max(1, self.total_pages)
        if self.page >= self.total_pages: self.page = self.total_pages - 1

        # Slice
        start = self.page * PAGE_SIZE
        end = start + PAGE_SIZE
        visible_cats = categories[start:end]

        if visible_cats:
             self.add_item(CategorySelect(visible_cats))
        
        # Add buttons with smart enablement
        self.prev_btn.disabled = (self.page == 0)
        self.next_btn.disabled = (self.page >= self.total_pages - 1)
        
        self.add_item(self.prev_btn)
        self.add_item(self.create_cat)
        self.add_item(self.refresh_btn)
        self.add_item(self.next_btn)

        embed = await get_root_embed(categories, self.page)
        
        if initial_setup: return
            
        if interaction:
             if interaction.response.is_done():
                 await interaction.edit_original_response(embed=embed, view=self)
             else:
                 await interaction.response.edit_message(embed=embed, view=self)

class CategorySelect(Select):
    def __init__(self, categories, placeholder="Select Category..."):
         options = [discord.SelectOption(label=c.name, value=str(c.id), emoji="📁") for c in categories]
         super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)
         
    async def callback(self, interaction: discord.Interaction):
         cat_id = self.values[0]
         category = await CategoryService.get_category(cat_id)
         if category:
             view = AdminCategoryView(category)
             await view.refresh(interaction, initial=True)
         else:
             await interaction.response.send_message("Category not found.", ephemeral=True)

class AdminCategoryView(View):
    def __init__(self, category: Category):
        super().__init__(timeout=None)
        self.category = category
        self.page = 0
        self.total_pages = 1

    async def refresh(self, interaction: discord.Interaction, initial: bool = False):
        self.clear_items()
        
        # 1. Fetch Subcategories
        subcategories = await CategoryService.get_all_categories(parent_id=str(self.category.id))
        if subcategories:
             self.add_item(CategorySelect(subcategories, placeholder="Select Subcategory..."))

        # 2. Fetch Items
        items = await ItemService.get_items_by_category(str(self.category.id), active_only=False)
        
        # Pagination for Items
        total = len(items)
        self.total_pages = (total // PAGE_SIZE) + (1 if total % PAGE_SIZE > 0 else 0)
        self.total_pages = max(1, self.total_pages)
        if self.page >= self.total_pages: self.page = self.total_pages - 1
        
        start = self.page * PAGE_SIZE
        end = start + PAGE_SIZE
        visible_items = items[start:end]

        if visible_items:
            self.add_item(ItemSelect(visible_items))
            
        self.prev_btn.disabled = (self.page == 0)
        self.next_btn.disabled = (self.page >= self.total_pages - 1)
        
        # Control bar
        self.add_item(self.prev_btn)
        self.add_item(self.add_sub_btn) # Create Subcategory
        self.add_item(self.add_item_btn)
        self.add_item(self.next_btn)
        
        # Row 2
        self.add_item(self.edit_cat_btn)
        self.add_item(self.delete_cat_btn)
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

    @discord.ui.button(label="Add Subcat", style=discord.ButtonStyle.secondary, row=2, emoji="📂")
    async def add_sub_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(CategoryModal("Add Subcategory", self, parent_id=str(self.category.id)))

    @discord.ui.button(label="Add Item", style=discord.ButtonStyle.green, row=2, emoji="📦")
    async def add_item_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ItemModal("Add Item", self, str(self.category.id)))

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary, row=3)
    async def edit_cat_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(CategoryModal("Edit Category", self, self.category))

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, row=3)
    async def delete_cat_btn(self, interaction: discord.Interaction, button: Button):
        try:
            await interaction.response.defer()
            await CategoryService.delete_category(str(self.category.id))

            # Refresh Panels
            from modules.shop.services_panels import ShopPanelService
            await ShopPanelService.refresh_all_panels(interaction.client)
            
            # Go up one level
            if self.category.parent_id:
                parent = await CategoryService.get_category(self.category.parent_id)
                view = AdminCategoryView(parent)
                await view.refresh(interaction, initial=True)
            else:
                root = AdminRootView()
                await root.init_view()
                categories = await CategoryService.get_all_categories(None)
                embed = await get_root_embed(categories)
                await interaction.response.edit_message(content="✅ Category Deleted.", embed=embed, view=root)
                
        except ValueError as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)

    @discord.ui.button(label="Up/Back", style=discord.ButtonStyle.secondary, row=3, emoji="⬆️")
    async def back_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        
        if self.category.parent_id:
            # Go to parent
            parent = await CategoryService.get_category(self.category.parent_id)
            if parent:
                view = AdminCategoryView(parent)
                await view.refresh(interaction, initial=True)
                return

        # Go to Root
        root = AdminRootView()
        await root.refresh(interaction)

class ItemSelect(Select):
    def __init__(self, items):
        options = [discord.SelectOption(label=i.name, value=str(i.id)) for i in items]
        super().__init__(placeholder="Select Item...", min_values=1, max_values=1, options=options)
        
    async def callback(self, interaction: discord.Interaction):
         item_id = self.values[0]
         item = await ItemService.get_item(item_id)
         if item:
             view = AdminItemView(item)
             await view.refresh(interaction, initial=True)

class AdminItemView(View):
    def __init__(self, item: Item):
        super().__init__(timeout=None)
        self.item = item
        
    async def refresh(self, interaction: discord.Interaction, initial: bool = False):
        cat = await CategoryService.get_category(str(self.item.category_id))
        embed = await get_item_embed(self.item, cat.name if cat else "Unknown")
        
        if initial:
            await interaction.response.edit_message(embed=embed, view=self)
        elif interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
             await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Edit Item", style=discord.ButtonStyle.primary)
    async def edit_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ItemModal("Edit Item", self, str(self.item.category_id), self.item))

    @discord.ui.button(label="Delete Item", style=discord.ButtonStyle.danger)
    async def delete_btn(self, interaction: discord.Interaction, button: Button):
        await ItemService.delete_item(str(self.item.id))
        
        # Go back to Category
        cat = await CategoryService.get_category(str(self.item.category_id))
        if cat:
            view = AdminCategoryView(cat)
            await view.refresh(interaction, initial=True)
        else:
             await interaction.response.send_message("Item deleted, but category not found.", ephemeral=True)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back_btn(self, interaction: discord.Interaction, button: Button):
        cat = await CategoryService.get_category(str(self.item.category_id))
        if cat:
            view = AdminCategoryView(cat)
            await view.refresh(interaction, initial=True)
