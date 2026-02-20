from datetime import datetime, timezone
from typing import List, Optional

import discord
from discord import Interaction
from discord.ui import Modal, TextInput, Select, View

from utils.discord_utils import MAX_PRIZE_LENGTH, MAX_WINNERS, parse_prize, ValidationError, parse_duration, \
    parse_winner_count, parse_min_account_age


class GiveawayJoinView(discord.ui.View):
    def __init__(self, giveaway_id: str):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        
        join_btn = discord.ui.Button(
            label="🎉 Join Giveaway",
            style=discord.ButtonStyle.blurple,
            custom_id=f"join_giveaway_{self.giveaway_id}"
        )
        join_btn.callback = self.join_btn_callback
        self.add_item(join_btn)

    async def join_btn_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from modules.giveaway.service import GiveawayService
        await GiveawayService.handle_join(interaction, self.giveaway_id)


class CreateGiveawayModal(Modal):
    def __init__(
        self,
        title: str = "Create Giveaway",
        required_roles: Optional[List[int]] = None,
        blacklisted_roles: Optional[List[int]] = None,
    ):
        super().__init__(title=title, timeout=600, custom_id="create_giveaway")
        self.required_roles = required_roles
        self.blacklisted_roles = blacklisted_roles

        self.prize_input = TextInput(
            label="Giveaway Prize",
            placeholder="e.g. Nitro Classic, $10 Steam Gift Card",
            required=True,
            max_length=MAX_PRIZE_LENGTH,
            style=discord.TextStyle.short,
            custom_id="price_input",
        )
        self.description = TextInput(
            label="Giveaway Description",
            placeholder="Enter a description",
            required=True,
            max_length=4000,
            min_length= 10,
            style=discord.TextStyle.paragraph,
            custom_id="description_input",
        )
        self.duration_input = TextInput(
            label="Duration (e.g. 1d, 2h30m, 90s)",
            placeholder="1d / 2h30m / 90s",
            required=True,
            max_length=20,
            style=discord.TextStyle.short,
            custom_id="duration_input",
        )
        self.winner_count_input = TextInput(
            label="Winner Count",
            placeholder=f"1 – {MAX_WINNERS}",
            required=True,
            max_length=3,
            style=discord.TextStyle.short,
            custom_id="winner_count_input",
        )
        self.min_account_age_input = TextInput(
            label="Min Account Age (optional, e.g. 30d)",
            placeholder="Leave blank to skip",
            required=False,
            max_length=20,
            style=discord.TextStyle.short,
            custom_id="min_account_age_input",
        )

        for field in [
            self.prize_input,
            self.duration_input,
            self.winner_count_input,
            self.min_account_age_input,
        ]:
            self.add_item(field)

    def validate(self) -> dict:
        errors = []
        result = {}

        try:
            result["prize"] = parse_prize(self.prize_input.value)
        except ValidationError as e:
            errors.append(f"**Prize:** {e}")

        result["description"] = self.description.value

        try:
            delta = parse_duration(self.duration_input.value)
            result["duration"] = delta
            result["ends_at"] = datetime.now(timezone.utc) + delta
        except ValidationError as e:
            errors.append(f"**Duration:** {e}")

        try:
            result["winner_count"] = parse_winner_count(self.winner_count_input.value)
        except ValidationError as e:
            errors.append(f"**Winner Count:** {e}")

        try:
            parsed_age = parse_min_account_age(self.min_account_age_input.value)
            result["min_account_age"] = int(parsed_age.total_seconds()) if parsed_age else None
        except ValidationError as e:
            errors.append(f"**Minimum Account Age:** {e}")

        if errors:
            raise ValidationError("\n".join(errors))

        # Attach roles from the command args
        result["required_roles"] = self.required_roles
        result["blacklisted_roles"] = self.blacklisted_roles

        return result

    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            data = self.validate()
        except ValidationError as e:
            await interaction.followup.send(
                f"🚨 Please fix the following: \n{e}",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"🎉 {data['prize']}",
            description=data["description"],
            colour=discord.Colour.blue(),
        )
        embed.add_field(name="Ends At", value=discord.utils.format_dt(data["ends_at"], style="R"), inline=False)
        embed.add_field(name="Winners", value=data["winner_count"], inline=True)
        embed.add_field(name="Entries", value="0", inline=True)
        if data["min_account_age"] is not None:
             days = max(1, int(data["min_account_age"] / 86400))
             embed.add_field(name="Min Account Age", value=f"{days} Days", inline=True)
        if data.get("required_roles"):
            role_mentions = ", ".join([f"<@&{r}>" for r in data["required_roles"]])
            embed.add_field(name="Required Roles", value=role_mentions, inline=False)
        if data.get("blacklisted_roles"):
            role_mentions = ", ".join([f"<@&{r}>" for r in data["blacklisted_roles"]])
            embed.add_field(name="Blacklisted Roles", value=role_mentions, inline=False)
        embed.set_footer(text=f"Hosted by: {interaction.user.name}")

        try:
            from modules.giveaway.service import GiveawayService

            msg = await interaction.channel.send(embed=embed)

            giveaway = await GiveawayService.save_giveaways(
                guild_id=interaction.guild.id,
                host_id=interaction.user.id,
                channel_id=interaction.channel.id,
                message_id=msg.id,
                giveaway_data=data,
            )
            
            if giveaway:
                view = GiveawayJoinView(giveaway_id=str(giveaway.id))
                await msg.edit(view=view)
                
                GiveawayService.schedule_giveaway_end(interaction.client, giveaway)
                
                await interaction.followup.send(f"✅ Giveaway started in {interaction.channel.mention}!", ephemeral=True)
            else:
                await msg.delete()
                await interaction.followup.send("❌ Failed to start giveaway. Database error.", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ Error starting giveaway: {e}", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        try:
            await interaction.followup.send(
                "❌ An unexpected error occurred. Please try again.",
                ephemeral=True
            )
        except Exception:
            pass
        raise error


# ──────────────────── Giveaway Dashboard View ────────────────────

GIVEAWAYS_PER_PAGE = 5

class GiveawayDashboardView(View):
    def __init__(self, giveaways: List, page: int = 0):
        super().__init__(timeout=300)
        self.all_giveaways = giveaways
        self.page = page
        self.max_pages = max(1, (len(giveaways) + GIVEAWAYS_PER_PAGE - 1) // GIVEAWAYS_PER_PAGE)
        self._build()

    def _build(self):
        self.clear_items()
        start = self.page * GIVEAWAYS_PER_PAGE
        end = start + GIVEAWAYS_PER_PAGE
        page_giveaways = self.all_giveaways[start:end]

        if page_giveaways:
            options = []
            for g in page_giveaways:
                status = "🔴 Ended" if g.ended else "🟢 Active"
                label = f"{g.title[:90]} ({status})"
                options.append(discord.SelectOption(
                    label=label,
                    value=str(g.id),
                    description=f"Entries: {g.total_entries or 0} | Winners: {g.winner_count or 1}"
                ))
            select = Select(
                placeholder="Select a giveaway to view details...",
                options=options,
                custom_id="giveaway_dashboard_select"
            )
            select.callback = self.on_select
            self.add_item(select)

        # Pagination buttons
        prev_btn = discord.ui.Button(label="◀ Previous", style=discord.ButtonStyle.secondary, disabled=self.page <= 0)
        prev_btn.callback = self.prev_page
        self.add_item(prev_btn)

        next_btn = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary, disabled=self.page >= self.max_pages - 1)
        next_btn.callback = self.next_page
        self.add_item(next_btn)

    def _build_list_embed(self) -> discord.Embed:
        start = self.page * GIVEAWAYS_PER_PAGE
        end = start + GIVEAWAYS_PER_PAGE
        page_giveaways = self.all_giveaways[start:end]

        embed = discord.Embed(
            title="🎁 Giveaway Dashboard",
            description=f"Showing page **{self.page + 1}/{self.max_pages}** ({len(self.all_giveaways)} total)",
            colour=discord.Colour.gold()
        )
        for g in page_giveaways:
            status = "🔴 Ended" if g.ended else "🟢 Active"
            end_text = discord.utils.format_dt(g.end_at, style="R") if g.end_at else "N/A"
            embed.add_field(
                name=f"{status} {g.title}",
                value=f"Entries: `{g.total_entries or 0}` | Winners: `{g.winner_count or 1}` | Ends: {end_text}",
                inline=False
            )
        return embed

    async def prev_page(self, interaction: discord.Interaction):
        self.page = max(0, self.page - 1)
        self._build()
        await interaction.response.edit_message(embed=self._build_list_embed(), view=self)

    async def next_page(self, interaction: discord.Interaction):
        self.page = min(self.max_pages - 1, self.page + 1)
        self._build()
        await interaction.response.edit_message(embed=self._build_list_embed(), view=self)

    async def on_select(self, interaction: discord.Interaction):
        from modules.giveaway.service import GiveawayService
        giveaway_id = interaction.data["values"][0]
        giveaway = await GiveawayService.get_giveaway_by_id(giveaway_id)

        if not giveaway:
            await interaction.response.send_message("❌ Giveaway not found.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🎁 {giveaway.title}",
            description=giveaway.description or "No description.",
            colour=discord.Colour.green() if not giveaway.ended else discord.Colour.red()
        )
        embed.add_field(name="Status", value="🔴 Ended" if giveaway.ended else "🟢 Active", inline=True)
        embed.add_field(name="Winners Count", value=str(giveaway.winner_count or 1), inline=True)
        embed.add_field(name="Total Entries", value=str(giveaway.total_entries or 0), inline=True)

        if giveaway.start_at:
            embed.add_field(name="Started", value=discord.utils.format_dt(giveaway.start_at, style="F"), inline=True)
        if giveaway.end_at:
            embed.add_field(name="Ends/Ended", value=discord.utils.format_dt(giveaway.end_at, style="R"), inline=True)

        host_mention = f"<@{giveaway.host_id}>"
        embed.add_field(name="Host", value=host_mention, inline=True)

        if giveaway.required_roles:
            embed.add_field(name="Required Roles", value=", ".join([f"<@&{r}>" for r in giveaway.required_roles]), inline=False)
        if giveaway.blacklisted_roles:
            embed.add_field(name="Blacklisted Roles", value=", ".join([f"<@&{r}>" for r in giveaway.blacklisted_roles]), inline=False)

        if giveaway.ended and giveaway.winners:
            winner_mentions = ", ".join([f"<@{w}>" for w in giveaway.winners])
            embed.add_field(name="🏆 Winners", value=winner_mentions, inline=False)
        elif giveaway.ended:
            embed.add_field(name="🏆 Winners", value="No winners.", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)
