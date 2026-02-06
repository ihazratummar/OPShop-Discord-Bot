import discord
import re
from core.database import Database
from modules.guild.model import GuildSettings


CUSTOM_EMOJI_REGEX = re.compile(r'^<a?:\w{2,32}:\d{17,20}>$')

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


    @staticmethod
    def is_custom_emoji_format(value: str) -> bool:
        return bool(CUSTOM_EMOJI_REGEX.match(value))


    @staticmethod
    def is_custom_discord_emoji(value: str, guild: discord.Guild) -> bool:
        match = CUSTOM_EMOJI_REGEX.match(value)
        if not match:
            return False
        emoji_id = int(match.group(1))
        return guild.get_emoji(emoji_id) is not None


    @staticmethod
    def get_server_emoji(emoji_id: int, guild: discord.Guild) -> discord.Emoji | None:
        emoji = guild.get_emoji(emoji_id)
        if emoji:
            return emoji
        return None




