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





