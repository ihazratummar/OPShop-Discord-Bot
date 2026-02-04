import discord
from discord.app_commands import user_install
from discord.ext import commands

from core.database import Database
from modules.invite_tracker.service import InviteTrackerService


class InviteTrackerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener(name="on_member_join")
    async def on_member_join(self, member: discord.Member):
        guild = member.guild

        old = InviteTrackerService.cache.get(guild.id, {})
        new_invites = await guild.invites()

        used_invite = None

        for invite in new_invites:
            if invite.uses > old.get(invite.code, 0):
                used_invite = invite
                break

        # update cache + DB snapshot
        InviteTrackerService.cache[guild.id] = {}

        for invite in new_invites:
            InviteTrackerService.cache[guild.id][invite.code] = invite.uses

            await  Database.invites().update_one(
                {"guild_id": guild.id},
                {"$set":{
                    "uses": invite.uses,
                    "inviter_id": invite.inviter.id if invite.inviter else None,
                }},
                upsert= True
            )

        if not used_invite:
            return

        inviter = used_invite.inviter

        await InviteTrackerService.process_join(
            member= member,
            inviter= inviter,
            guild= guild
        )


async def setup(bot):
    await bot.add_cog(InviteTrackerCog(bot))