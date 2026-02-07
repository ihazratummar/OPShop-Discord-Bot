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
                {"$set": {"seller_role_id": role.id}},
                upsert=True
            )
            await interaction.followup.send(f"{role.mention} has been set to your seller role.")
        except Exception as e :
            await interaction.followup.send(f"❌ Error: {e}")

    @app_commands.command(name="set_server_logs_channel", description="Set seller role")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(channel="Mention a seller role")
    async def set_server_logs_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)

        try:
            await Database.guild_settings().update_one(
                {"guild_id": interaction.guild.id},
                {"$set": {"server_logs_channel_id": channel.id}},
                upsert=True
            )
            await interaction.followup.send(f"{channel.mention} has been for server logs.")
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}")


async def setup(bot):
    await bot.add_cog(GuildCog(bot))