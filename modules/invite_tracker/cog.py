import discord
from discord.ext import commands
from discord import app_commands
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
        inviter_member = guild.get_member(inviter.id)

        await InviteTrackerService.process_join(
            member= member,
            inviter= inviter_member,
            guild= guild
        )

    @app_commands.command(name="set_invite_logs_channel", description="Set a logs channel for invite tracker")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def set_invite_logs_channel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        await interaction.response.defer(ephemeral=True)
        if channel is None:
            channel = interaction.channel

        await Database.guild_settings().update_one(
            {
                "guild_id": interaction.guild.id
            },
            {"$set":{"invite_logs_channel_id":channel.id}},
            upsert= True
        )
        await interaction.followup.send(f"{channel.mention} has been set as invite logs channel", ephemeral=True)



async def setup(bot):
    await bot.add_cog(InviteTrackerCog(bot))