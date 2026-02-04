import discord
from discord import app_commands
from discord.ext import commands

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

        seller_role = discord.utils.get(member.guild.roles, name="Seller")
        if not seller_role:
            seller_role = await interaction.guild.create_role(name="Seller")

        if seller_role not in member.roles:
            await interaction.followup.send("Please mention a seller to add reputation.")
            return

        await ReputationService.add_reputation(
            from_user_id=interaction.user.id,
            target_user_id=member.id,
            guild_id=interaction.guild.id,
            reputation_amount= reputation,
            is_admin=True
        )
        await interaction.followup.send(
            f"⭐️ +{reputation} rep added to {member.name}'s profile!", ephemeral=True
        )

## TODO : Add Rep roles


async def setup(bot):
    await bot.add_cog(Reputation(bot))
