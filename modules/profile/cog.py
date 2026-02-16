import discord
from discord import app_commands
from discord.ext import commands
from loguru import logger

from modules.economy.services import EconomyService
from modules.profile.services import ProfileService


class ProfileCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="profile", description="View your shop profile and stats")
    async def profile_command(self, interaction: discord.Interaction, user: discord.User = None):
        target = user or interaction.user
        
        # Ensure user exists in DB first
        db_user = await EconomyService.get_user(target.id, target.name)

        embed = discord.Embed(title=f"🛡️ Shop Profile: {target.display_name}", color=discord.Color.blue())
        embed.set_thumbnail(url=target.avatar.url if target.avatar else None)
        embed.add_field(name="Reputation Score", value=f"**{db_user.reputations}**", inline=True)
        embed.add_field(name="Shop Tokens", value=f"{db_user.tokens:,}", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="View top users")
    async def leaderboard_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            users = await ProfileService.get_leaderboard(10)
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}")
        desc = ""
        for idx, u in enumerate(users, 1):
            desc += f"> **{idx}.** <@{u.discord_id}> - **{u.reputations}**x +Reputation\n"
        embed = discord.Embed(title="🏆 Shop Leaderboard", description=desc, color=discord.Color.gold())
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ProfileCog(bot))
