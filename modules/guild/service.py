import discord
import re
from core.database import Database
from modules.guild.model import GuildSettings


CUSTOM_EMOJI_REGEX = re.compile(r'^<a?:\w{2,32}:(\d{17,20})>$')

class GuildSettingService:

    @staticmethod
    async def get_guild_settings(guild: discord.Guild) -> GuildSettings:
        doc = await Database.guild_settings().find_one({"guild_id": guild.id})

        if doc:
            return GuildSettings(**doc)

        # return default settings object
        return GuildSettings(guild_id=guild.id)

    @staticmethod
    async def get_seller_roles(guild: discord.Guild) -> list[discord.Role]:
        guild_settings = await GuildSettingService.get_guild_settings(guild)
        seller_roles = []
        if guild_settings and guild_settings.seller_role_ids:
            for role_id in guild_settings.seller_role_ids:
                role = guild.get_role(role_id)
                if role:
                    seller_roles.append(role)
        return seller_roles


    @staticmethod
    def is_custom_emoji_format(value: str) -> bool:
        return bool(CUSTOM_EMOJI_REGEX.match(value))


    @staticmethod
    def is_custom_discord_emoji(value: str, guild: discord.Guild) -> bool:
        match = CUSTOM_EMOJI_REGEX.match(value)
        if not match:
            # It might be a standard unicode emoji which doesn't match this regex
            # But the logic below assumes custom emoji validation.
            # If standard emoji, this returns False? 
            # If it's a standard emoji, guild.get_emoji won't work anyway. 
            # Logic seems to mandate Custom Emoji?
            return False
            
        emoji_id = int(match.group(1))
        return guild.get_emoji(emoji_id) is not None


    @staticmethod
    def get_server_emoji(emoji_id: int, guild: discord.Guild) -> discord.Emoji | None:
        emoji = guild.get_emoji(emoji_id)
        if emoji:
            return emoji
        return None




