import discord
from discord.ext import  commands
from discord import app_commands

from core.database import Database


class GuildCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="set_seller_role", description="Set seller role")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(role="Mention a seller role")
    async def set_seller_role(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(ephemeral=True)

        try:
            await Database.guild_settings().update_one(
                {"guild_id": interaction.guild.id},
                {"$set": {"seller_role": role.id}},
                upsert=True
            )
            await interaction.followup.send(f"{role.mention} has been set to your seller role.")
        except Exception as e :
            await interaction.followup.send(f"❌ Error: {e}")


async def setup(bot):
    await bot.add_cog(GuildCog(bot))