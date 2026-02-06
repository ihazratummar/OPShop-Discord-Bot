import datetime

import discord

from core.constant import Emoji
from core.database import Database, logger
from modules.economy.models import Transaction
from modules.economy.services import EconomyService, TransactionService
from modules.guild.service import GuildSettingService
from modules.invite_tracker.models import InviteJoins
from modules.reputation.service import ReputationService
from modules.xp.services import XPService


class InviteTrackerService:
    cache = {}

    @staticmethod
    async def cache_guild(guild: discord.Guild):

        """
        :param guild:
        :return:
        {guild_id :{code: uses}}
        """

        invites = await guild.invites()

        InviteTrackerService.cache[guild.id] = {}

        for invite in invites:
            InviteTrackerService.cache[guild.id][invite.code] = invite.uses

            await Database.invites().update_one(
                {
                    "guild_id": guild.id,
                    "code": invite.code
                },
                {
                    "$set": {
                        "uses": invite.uses,
                        "inviter_id": invite.inviter.id if invite.inviter else None
                    }
                },
                upsert=True
            )

        InviteTrackerService.cache[guild.id] = {
            invite.code: invite.uses
            for invite in invites
        }

    @staticmethod
    async def process_join(member: discord.Member, inviter: discord.Member, guild: discord.Guild):

        # prevent self-invite wired case
        if member.id == inviter.id:
            return

        # prevent rejoin farming

        existing = await  Database.invite_joins().find_one(
            {
                "user_id": member.id,
                "guild_id": guild.id
            }
        )
        if existing:
            return

        invite_join = InviteJoins(
            user_id=member.id,
            inviter_id=inviter.id,
            guild_id=guild.id,
            timestamp=datetime.datetime.now()
        )
        await Database.invite_joins().insert_one(invite_join.to_mongo())

        seller_role = await GuildSettingService.get_seller_role(guild=guild)

        if seller_role in inviter.roles:
            emoji = GuildSettingService.get_server_emoji(emoji_id=int(Emoji.BLUE_STAR.value), guild=guild)
            reward_message = f"{emoji if emoji else "🔮"} +1 reputation!"
            await  ReputationService.add_rep(user_id=inviter.id, guild_id=guild.id)
        else:
            emoji = GuildSettingService.get_server_emoji(emoji_id=int(Emoji.SHOP_TOKEN.value), guild=guild)
            reward_message = f"{emoji if emoji else "🪙"} 10 Shop Tokens"
            await EconomyService.modify_tokens(user_id=inviter.id, amount=10, reason="Invite Reward",
                                               actor_id=inviter.id)

        await XPService.add_xp(user_id=inviter.id, amount=50, source="Invite reward")

        logger.warning("Reached invite log section")

        # Count total invites
        count = await Database.invite_joins().count_documents(
            {"guild_id": guild.id, "inviter_id": inviter.id}
        )

        logger.warning(f"Invite Join {inviter.mention}'s invite! {count}")

        guild_settings = await GuildSettingService.get_guild_settings(guild=guild)
        logger.warning(f"Guild settings: {guild_settings}")
        if not guild_settings:
            logger.warning("Guild settings missing")
            return

        log_channel_id = guild_settings.invite_logs_channel_id
        logger.warning(f"log_channel_id raw: {guild_settings.invite_logs_channel_id}")

        if not log_channel_id:
            logger.warning("Invite log channel not configured")
            return

        log_channel = guild.get_channel(int(log_channel_id))
        logger.warning(f"Resolved channel: {log_channel}")
        if not log_channel:
            logger.warning(f"Log channel {log_channel_id} not found in guild")
            return

        embed = discord.Embed(
            title="🎉 New Invite Join",
            description=f"{member.mention} joined using {inviter.mention}'s invite!",
            color=discord.Color.green()
        )

        embed.add_field(
            name="Inviter Total",
            value=f"Total **{count}** invites",
            inline=True
        )

        if reward_message:
            embed.add_field(
                name="Invite Reward",
                value=reward_message,
                inline=True
            )

        await log_channel.send(embed=embed)
