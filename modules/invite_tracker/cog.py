import discord
from discord.ext import commands
from discord import app_commands
from core.database import Database
from loguru import logger

from core.models.user import User
from modules.invite_tracker.service import InviteTrackerService


class InviteTrackerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener(name="on_member_join")
    async def on_member_join(self, member: discord.Member):
        guild = member.guild

        # Serialize per-guild so two simultaneous joins don't race each other
        async with InviteTrackerService._get_lock(guild.id):
            used_invite = await InviteTrackerService.detect_used_invite(guild)

        if not used_invite:
            logger.warning(f"[InviteTracker] Could not detect invite for {member.id} in {guild.id}")
            return

        if not used_invite.inviter:
            logger.warning(f"[InviteTracker] Invite {used_invite.code} has no inviter (vanity/server discovery?)")
            return

        # inviter may not be a Member (could have left the guild), fall back to User
        inviter = guild.get_member(used_invite.inviter.id) or used_invite.inviter

        user = User(
            discord_id= member.id,
            username= member.display_name,
            tokens=0,
            xp=0,
            level=1,
            reputations=0,
            rep_given_counter=0,
        )
        await Database.users().update_one(
            {"discord_id": member.id},
            {"$setOnInsert": user.to_mongo()},
            upsert=True,
        )

        await InviteTrackerService.process_join(
            member=member,
            inviter=inviter,
            guild=guild,
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