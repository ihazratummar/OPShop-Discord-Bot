import discord
from discord import app_commands
from discord.ext import commands

from core.database import Database
from modules.guild.service import GuildSettingService
from modules.reputation.service import ReputationService


class Reputation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener(name="on_message")
    async def on_message(self, message: discord.Message):
        await ReputationService.reputation(message=message)

    @app_commands.command(name="add_rep", description="Add reputation to a user")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(member="Mention a seller to add reputation")
    async def add_rep(self, interaction: discord.Interaction, member: discord.Member, reputation: int):
        await interaction.response.defer(ephemeral=True)

        if reputation <= 0 or type(reputation) != int:
            await interaction.followup.send("Please enter a valid reputation value!", )
            return

        if interaction.user.id == member.id:
            await interaction.followup.send("Are you trying to increase your reputation? 😏")
            return

        guild_settings = await GuildSettingService.get_guild_settings(guild=interaction.guild)
        seller_role = interaction.guild.get_role(guild_settings.seller_role_id)
        if not seller_role:
            await interaction.followup.send(f"Seller role not configured!", ephemeral=True)

        if seller_role not in member.roles:
            await interaction.followup.send(f"User do not have {seller_role.name} role.", ephemeral=True)
            return

        await ReputationService.add_reputation(
            from_user_id=interaction.user.id,
            target_user_id=member.id,
            guild=interaction.guild,
            reputation_amount=reputation,
            is_admin=True
        )
        await interaction.followup.send(
            f"⭐️ +{reputation} rep added to {member.name}'s profile!", ephemeral=True
        )

    rep_role = app_commands.Group(
        name="rep_role",
        description="Reputation role",
        guild_only=True,
        default_permissions= discord.Permissions(administrator=True)
    )

    @app_commands.command(name="rep_channel", description="Add reputation command channel")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(channel="Mention a channel where you want the reputation to work")
    async def rep_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        result = await Database.guild_settings().update_one(
            {"guild_id": interaction.guild.id},
            {"$set": {"rep_channel": channel.id}},
            upsert=True
        )

        if result.acknowledged:
            await interaction.followup.send(f"{channel.mention} reputation channel updated.", ephemeral=True)
            return

        await interaction.followup.send(f"Failed to add reputation to {channel.mention}", ephemeral=True)


    @rep_role.command(name="add", description="Add reputation to a user")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_rep_role_command(self, interaction: discord.Interaction, role: discord.Role, reputation_threshold: app_commands.Range[int, 1, 10000]):
        await interaction.response.defer(ephemeral=True)

        result = await ReputationService.save_reputation_tier(role_id= role.id, reputation_amount= reputation_threshold, guild_id= interaction.guild_id)
        if result:
            await interaction.followup.send(f"**{role.name}** Role added for +rep level", ephemeral=True)
            return
        await interaction.followup.send(f"Failed to add reputation to {role.name}", ephemeral=True)


    @rep_role.command(name="set_logs_channel", description="Set the reputation logs channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_rep_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        result = await Database.guild_settings().update_one(
            {"guild_id": interaction.guild.id},
            {"$set": {"rep_log_channel": channel.id}},
            upsert=True
        )
        if result.acknowledged:
            await interaction.followup.send(f"{channel.mention} reputation logs channel updated.", ephemeral=True)


 ## TODO : Add panel for levels

async def setup(bot):
    await bot.add_cog(Reputation(bot))
