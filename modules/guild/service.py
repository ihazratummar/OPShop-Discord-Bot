import discord

from core.database import Database
from modules.guild.model import GuildSettings


class GuildSettingService:

    @staticmethod
    async def get_guild_settings(guild: discord.Guild) -> GuildSettings:
        doc = await Database.guild_settings().find_one({"guild_id": guild.id})

        if doc:
            return GuildSettings(**doc)

        # return default settings object
        return GuildSettings(guild_id=guild.id)

    @staticmethod
    async def get_seller_role(guild: discord.Guild) -> discord.Role | None:
        guild_settings = await GuildSettingService.get_guild_settings(guild)
        seller_role: discord.Role
        if guild_settings:
            seller_role_id = guild_settings.seller_role_id
            if seller_role_id:
                return guild.get_role(seller_role_id)
        return None





