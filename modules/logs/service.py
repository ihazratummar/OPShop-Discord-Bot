from typing import Optional

import discord

from modules.guild.service import GuildSettingService


class ServerLogsService:

    @staticmethod
    async def log_channel(guild: discord.Guild)-> Optional[discord.TextChannel]:
        guild_settings = await GuildSettingService.get_guild_settings(guild=guild)

        if guild and guild_settings is None:
            return None

        log_channel_id = guild_settings.server_logs_channel_id
        if log_channel_id is None:
            return None
        log_channel = guild.get_channel(log_channel_id)
        if log_channel is None:
            return None

        if isinstance(log_channel, discord.TextChannel):
            return log_channel

        return None