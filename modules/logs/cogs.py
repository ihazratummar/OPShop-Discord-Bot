import traceback

import discord
from discord.ext import commands

from core.bot import logger
from core.embed_builder import embed_builder
from modules.logs.service import ServerLogsService


class ServerLogsCogs(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    async def _send_logs(guild: discord.Guild, embed: discord.Embed):
        """Safe send to logs channel"""

        if guild is None:
            return
        channel = await ServerLogsService.log_channel(guild=guild)
        if not channel:
            logger.warning(f"Failed to send logs to {guild.name}")
            return
        logger.info(f"Sending logs to {channel}")
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send logs to {guild.name}", e)
            pass

    # -------------------------------------------------
    # MESSAGE EVENTS
    # -------------------------------------------------

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.guild is None or before.author.bot or before.content == after.content:
            return
        fields = [
            ("Author", f"{before.author.mention} ({before.author.id})", True),
            ("Channel", before.channel.mention, True),
            ("Jump", f"[Jump to Message]({after.jump_url})", True),
            ("Before", before.content[:1000] or "*empty*", False),
            ("After", after.content[:1000] or "*empty*", False),
        ]
        e = embed_builder(
            title="Message Edited",
            description="",
            color=discord.Color.orange(),
            thumbnail=before.author.display_avatar.url if before.author.display_avatar else None,
            fields=fields,
        )
        await ServerLogsCogs._send_logs(guild= before.guild, embed= e)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.guild is None or (message.author and message.author.bot):
            return
        fields = [
            ("Author", f"{getattr(message.author, 'mention', 'Unknown')} ({getattr(message.author, 'id', 'N/A')})",
             True),
            ("Channel", getattr(message.channel, "mention", "Unknown"), True),
            ("Content", (message.content or "*empty*")[:1000], False),
        ]
        e = embed_builder("Message Deleted", "", discord.Color.red(), fields=fields)
        await ServerLogsCogs._send_logs(message.guild, e)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[discord.Message]):
        if not messages:
            return
        guild = messages[0].guild
        if guild is None:
            return
        channel = messages[0].channel
        fields = [
            ("Channel", getattr(channel, "mention", "Unknown"), True),
            ("Count", str(len(messages)), True),
        ]
        e = embed_builder("Bulk Message Delete", "", discord.Color.red(), fields=fields)
        await ServerLogsCogs._send_logs(guild, e)

    # -------------------------------------------------
    # MEMBER / BAN EVENTS
    # -------------------------------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        fields = [
            ("Member", f"{member.mention} ({member.id})", True),
            ("Created", discord.utils.format_dt(member.created_at, style='R'), True),
        ]
        e = embed_builder("Member Joined", "", discord.Color.green(), thumbnail=member.display_avatar.url,
                      fields=fields)
        await ServerLogsCogs._send_logs(member.guild, e)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        fields = [("Member", f"{member} ({member.id})", True)]
        e = embed_builder("Member Left", "", discord.Color.dark_grey(), fields=fields)
        await ServerLogsCogs._send_logs(member.guild, e)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        fields = [("User", f"{user} ({user.id})", True)]
        e = embed_builder("Member Banned", "", discord.Color.dark_red(), thumbnail=user.display_avatar.url,
                      fields=fields)
        await ServerLogsCogs._send_logs(guild, e)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        fields = [("User", f"{user} ({user.id})", True)]
        e = embed_builder("Member Unbanned", "", discord.Color.dark_green(), thumbnail=user.display_avatar.url,
                      fields=fields)
        await ServerLogsCogs._send_logs(guild, e)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.guild is None:
            return
        delta_fields = []
        if before.nick != after.nick:
            delta_fields.append(("Nickname", f"`{before.nick}` → `{after.nick}`", False))

        added = [r for r in after.roles if r not in before.roles]
        removed = [r for r in before.roles if r not in after.roles]
        if added:
            delta_fields.append(("Roles Added", ", ".join(r.mention for r in added), False))
        if removed:
            delta_fields.append(("Roles Removed", ", ".join(r.mention for r in removed), False))

        if delta_fields:
            fields = [("Member", f"{after.mention} ({after.id})", True)] + delta_fields
            e = embed_builder("Member Updated", "", discord.Color.teal(), thumbnail=after.display_avatar.url,
                          fields=fields)
            await ServerLogsCogs._send_logs(after.guild, e)

    # -------------------------------------------------
    # CHANNEL EVENTS
    # -------------------------------------------------
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        fields = [("Channel", getattr(channel, "mention", channel.name), True),
                  ("Type", channel.__class__.__name__, True)]
        e = embed_builder("Channel Created", "", discord.Color.green(), fields=fields)
        await ServerLogsCogs._send_logs(channel.guild, e)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        fields = [("Channel", channel.name, True), ("Type", channel.__class__.__name__, True)]
        e = embed_builder("Channel Deleted", "", discord.Color.red(), fields=fields)
        await ServerLogsCogs._send_logs(channel.guild, e)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        changes = []
        if hasattr(before, "name") and before.name != after.name:
            changes.append(("Name", f"`{before.name}` → `{after.name}`", False))
        if hasattr(before, "topic") and getattr(before, "topic", None) != getattr(after, "topic", None):
            changes.append(("Topic", "Updated", False))
        if changes:
            fields = [("Channel", getattr(after, "mention", after.name), True)] + changes
            e = embed_builder("Channel Updated", "", discord.Color.orange(), fields=fields)
            await ServerLogsCogs._send_logs(after.guild, e)

    # -------------------------------------------------
    # VOICE (concise)
    # -------------------------------------------------
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState,
                                    after: discord.VoiceState):
        if member.guild is None:
            return
        title = None
        fields = []
        color = discord.Color.blurple()

        if before.channel != after.channel:
            if before.channel is None and after.channel is not None:
                title = "Joined Voice"
                fields = [("Member", f"{member.mention} ({member.id})", True),
                          ("Channel", after.channel.mention, True)]
                color = discord.Color.green()
            elif before.channel is not None and after.channel is None:
                title = "Left Voice"
                fields = [("Member", f"{member.mention} ({member.id})", True),
                          ("Channel", before.channel.mention, True)]
                color = discord.Color.red()
            else:
                title = "Switched Voice"
                fields = [
                    ("Member", f"{member.mention} ({member.id})", True),
                    ("From", before.channel.mention, True),
                    ("To", after.channel.mention, True),
                ]
                color = discord.Color.orange()

        if title:
            e = embed_builder(title, "", color, thumbnail=member.display_avatar.url, fields=fields)
            await ServerLogsCogs._send_logs(member.guild, e)

    # -------------------------------------------------
    # COMMAND EVENTS (optional but useful)
    # -------------------------------------------------
    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context):
        if ctx.guild is None:
            return
        args_str = " ".join([str(a) for a in ctx.args[2:]])[:512] if len(ctx.args) > 2 else "-"
        fields = [
            ("User", f"{ctx.author} ({ctx.author.id})", True),
            ("Channel", ctx.channel.mention if hasattr(ctx.channel, 'mention') else str(ctx.channel), True),
            ("Command", ctx.command.qualified_name if ctx.command else "unknown", True),
            ("Args", args_str, False),
        ]
        e = embed_builder("Command Executed", "", discord.Color.light_grey(), fields=fields)
        await ServerLogsCogs._send_logs(ctx.guild, e)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if ctx.guild is None:
            return
        tb = "".join(traceback.format_exception_only(type(error), error)).strip()
        fields = [
            ("User", f"{ctx.author} ({ctx.author.id})", True),
            ("Command", ctx.command.qualified_name if ctx.command else "unknown", True),
            ("Error", f"```{tb[:1000]}```", False),
        ]
        e = embed_builder("Command Error", "", discord.Color.red(), fields=fields)
        await ServerLogsCogs._send_logs(ctx.guild, e)




async def setup(bot: commands.Bot):
    await bot.add_cog(ServerLogsCogs(bot=bot))

