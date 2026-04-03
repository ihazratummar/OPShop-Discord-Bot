import asyncio
import time
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands
from loguru import logger

from modules.sticky_message.model import (
    MessageSnapshot, EmbedSnapshot,
    StickyCreateDTO, StickyType, StickyMessage
)
from modules.sticky_message.service import StickyMessageService


class StickyMessageCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self._locks: dict[int, asyncio.Lock] = {}
        self._sticky_cache: dict[int, list[StickyMessage]] = {}
        self._cooldowns: dict[int, float] = {}
        self._message_counts: dict[int, int] = {}

    # ─── CACHE ─────────────────────────────────────────

    async def load_channel(self, channel_id: int):
        self._sticky_cache[channel_id] = await StickyMessageService.get_active_by_channel(channel_id)

    # ─── HELPERS ───────────────────────────────────────

    def _get_lock(self, channel_id: int) -> asyncio.Lock:
        if channel_id not in self._locks:
            self._locks[channel_id] = asyncio.Lock()
        return self._locks[channel_id]

    async def _clone(self, channel: discord.TextChannel, msg: discord.Message):
        files = [await a.to_file() for a in msg.attachments]

        return await channel.send(
            content=msg.content or None,
            embeds=msg.embeds or None,
            files=files or None
        )

    async def _delete(self, channel, msg_id: Optional[int]):
        if not msg_id:
            return
        try:
            msg = channel.get_partial_message(msg_id)
            await msg.delete()
        except:
            pass

    def _snapshot(self, msg: discord.Message):
        return MessageSnapshot(
            content=msg.content,
            embeds=[
                EmbedSnapshot(
                    title=e.title,
                    description=e.description,
                    color=e.color.value if e.color else None,
                    url=e.url
                ) for e in msg.embeds
            ],
            attachments=[a.url for a in msg.attachments],
            author_id=msg.author.id,
            author_name=msg.author.name
        )

    # ─── COMMAND ───────────────────────────────────────

    @app_commands.command(name="sticky_add")
    async def sticky_add(self, interaction: discord.Interaction, msg_id: str):
        await interaction.response.defer(ephemeral=True)

        try:
            message_id = int(msg_id)
        except:
            return await interaction.followup.send("Invalid ID")

        channel = interaction.channel

        original = await channel.fetch_message(message_id)

        clone = await self._clone(channel, original)

        dto = StickyCreateDTO(
            guild_id=interaction.guild_id,
            channel_id=channel.id,
            message_id=message_id,
            bot_msg_id=clone.id,
            type=StickyType.EMBED if original.embeds else StickyType.PLAIN,
            added_by=interaction.user.id,
            snapshot=self._snapshot(original)
        )

        try:
            await StickyMessageService.create(dto)
        except ValueError:
            await clone.delete()
            return await interaction.followup.send("Already exists")

        await self.load_channel(channel.id)

        await interaction.followup.send("✅ Sticky added")

    # ─── LISTENER ──────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        channel_id = message.channel.id
        if channel_id not in self._sticky_cache:
            await self.load_channel(channel_id)
            
        stickies = self._sticky_cache.get(channel_id)

        if not stickies:
            return

        # track message count to prevent spam in busy channels
        self._message_counts[channel_id] = self._message_counts.get(channel_id, 0) + 1
        if self._message_counts[channel_id] < 5:
            return

        # cooldown
        now = time.time()
        if now - self._cooldowns.get(channel_id, 0) < 15:
            return
        self._cooldowns[channel_id] = now

        async with self._get_lock(channel_id):
            # Reset message count since we are dropping sticky
            self._message_counts[channel_id] = 0
            
            for sticky in stickies:

                # skip if already last message
                if message.channel.last_message and \
                        message.channel.last_message.id == sticky.bot_message_id:
                    continue

                try:
                    original = await message.channel.fetch_message(sticky.message_id)
                except:
                    continue

                await self._delete(message.channel, sticky.bot_message_id)

                new_msg = await self._clone(message.channel, original)

                await StickyMessageService.update_bot_msg_id(
                    channel_id, sticky.message_id, new_msg.id
                )
                sticky.bot_message_id = new_msg.id


async def setup(bot):
    await bot.add_cog(StickyMessageCog(bot))