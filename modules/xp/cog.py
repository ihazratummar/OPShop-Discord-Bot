import discord
from discord import app_commands
from discord.ext import commands
from modules.economy.services import EconomyService
from modules.xp.services import XPService
from loguru import logger


class XPCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="profile", description="View your shop profile and stats")
    async def profile_command(self, interaction: discord.Interaction, user: discord.User = None):
        target = user or interaction.user
        
        # Ensure user exists in DB first
        db_user = await EconomyService.get_user(target.id, target.name)
        
        # Calculate progress
        next_level_xp = XPService.calculate_xp_for_level(db_user.level + 1)
        current_level_xp = XPService.calculate_xp_for_level(db_user.level)
        
        # Avoid division by zero for Level 1
        xp_needed = next_level_xp - current_level_xp
        xp_progress = db_user.xp - current_level_xp
        percentage = (xp_progress / xp_needed) * 100 if xp_needed > 0 else 0

        embed = discord.Embed(title=f"🛡️ Shop Profile: {target.display_name}", color=discord.Color.blue())
        embed.set_thumbnail(url=target.avatar.url if target.avatar else None)
        
        embed.add_field(name="Level", value=f"**{db_user.level}**", inline=True)
        embed.add_field(name="XP", value=f"{db_user.xp:,} / {next_level_xp:,} ({percentage:.1f}%)", inline=True)
        embed.add_field(name="Reputation Score", value=f"**{db_user.reputations}**", inline=True)

        embed.add_field(name="Tokens", value=f"{db_user.tokens:,}", inline=True)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="View top users")
    async def leaderboard_command(self, interaction: discord.Interaction):
        users = await XPService.get_leaderboard(10)
        
        desc = ""
        for idx, u in enumerate(users, 1):
            desc += f"**{idx}.** <@{u.discord_id}> - Lvl {u.level} ({u.xp:,} XP) | {u.reputations}x +rep\n"
            
        embed = discord.Embed(title="🏆 Shop Leaderboard", description=desc, color=discord.Color.gold())
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(XPCog(bot))
