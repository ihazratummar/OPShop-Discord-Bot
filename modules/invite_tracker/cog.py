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
        
        # 1. Always ensure User exists in DB
        user = User(
            discord_id=member.id,
            username=member.display_name,
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

        # 2. Detect used invite
        # Serialize per-guild so two simultaneous joins don't race each other
        async with InviteTrackerService._get_lock(guild.id):
            used_invite = await InviteTrackerService.detect_used_invite(guild)

        inviter = None

        if used_invite:
            # We found a specific invite!
            if used_invite.inviter:
                inviter = guild.get_member(used_invite.inviter.id) or used_invite.inviter
            else:
                logger.warning(f"[InviteTracker] Invite {used_invite.code} has no inviter (vanity/server discovery?)")
        else:
            # Fallback: Invite unknown (race condition, bot restart, etc.)
            # Check if this is a rejoin to recover original inviter
            join_data = await InviteTrackerService.get_join_data(member.id, guild.id)
            if join_data:
                logger.info(f"[InviteTracker] {member.id} rejoined {guild.id} (Invite unknown/expired)")
                inviter_id = join_data.get("inviter_id")
                if inviter_id:
                    try:
                        inviter = await self.bot.fetch_user(inviter_id)
                    except discord.NotFound:
                        inviter = None
            else:
                logger.warning(f"[InviteTracker] Unknown invite for {member.id} in {guild.id}")

        # 3. Process the join (logs, rewards, etc.)
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