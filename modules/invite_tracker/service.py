import asyncio
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
    _cache: dict[int, dict[str, int]] = {}
    _locks: dict[int, asyncio.Lock] = {}


    @classmethod
    def _get_lock(cls, guild_id: int)-> asyncio.Lock:
        """Return a per-guild lock, creating it if needed"""
        if guild_id not in cls._locks:
            cls._locks[guild_id] = asyncio.Lock()
        return cls._locks[guild_id]



    @classmethod
    async def cache_guild(cls, guild: discord.Guild):

        """
        Snapshot all current invite uses for a guild.
        Structure: { guild_id: { code: uses } }
        """

        async with cls._get_lock(guild_id=guild.id):
            try:
                invites = await guild.invites()
            except discord.Forbidden:
                logger.warning(f"[InviteTracker] Missing 'Manage Guild' permissions")
                return

            snapshot = {invite.code: invite.uses for invite in invites}
            cls._cache[guild.id] = snapshot

            for invite in invites:
                await Database.invites().update_one(
                    {"guild_id": guild.id, "code": invite.code},
                    {
                        "$set": {
                            "uses": invite.uses,
                            "inviter_id": invite.inviter.id if invite.inviter else None
                        }
                    },
                    upsert=True
                )

    @classmethod
    async def detect_used_invite(cls, guild: discord.Guild) -> discord.Invite | None:
        """
        Diff the cache snapshot against current invites to find which
        invite was just used. Must be called under the guild lock.
        Return the used Invite or None
        :param guild:
        :return:
        """

        try:
            new_invites = await guild.invites()
        except discord.Forbidden:
            logger.warning(f"[InviteTracker] can not fetch invites for guild {guild.id}")
            return None

        old = cls._cache.get(guild.id, {})
        used_invite = None

        for invite in new_invites:
            if invite.uses > old.get(invite.code, 0):
                used_invite = invite
                break

        # Always refresh cahe after diffing so the next join is accurate
        cls._cache[guild.id] = { inv.code: inv.uses for inv in new_invites}

        # Persist updated snapshot

        for invite in new_invites:
            await  Database.invites().update_one(
                {"guild_id": guild.id, "code": invite.code},
                {
                    "$set": {
                        "uses": invite.uses,
                        "inviter_id": invite.inviter.id if invite.inviter else None
                    }
                },
                upsert= True
            )

        return used_invite

    @classmethod
    async def process_join(
            cls,
            member: discord.Member,
            inviter: discord.Member | discord.User,
            guild: discord.Guild,
    ) -> None:
        # Prevent self-invite edge case
        if member.id == inviter.id:
            return

        # Atomic upsert: only insert if this (user, guild) pair doesn't exist yet.
        # This eliminates the TOCTOU race between find_one + insert_one.
        result = await Database.invite_joins().update_one(
            {"user_id": member.id, "guild_id": guild.id},
            {
                "$setOnInsert": {
                    "user_id": member.id,
                    "inviter_id": inviter.id,
                    "guild_id": guild.id,
                    "timestamp": datetime.datetime.utcnow(),
                }
            },
            upsert=True,
        )

        # If no document was inserted, this is a rejoin — skip rewards
        if result.upserted_id is None:
            logger.info(f"[InviteTracker] Rejoin detected for {member.id} in {guild.id}, skipping.")
            return

        # --- Rewards ---
        reward_message: str | None = None

        seller_role = await GuildSettingService.get_seller_role(guild=guild)
        # guild.get_member() only works if the inviter is still in the guild.
        # inviter may be a plain discord.User when fetched from invite.inviter.
        inviter_member = guild.get_member(inviter.id)
        has_seller_role = inviter_member and seller_role in inviter_member.roles

        if has_seller_role:
            emoji = GuildSettingService.get_server_emoji(emoji_id=int(Emoji.BLUE_STAR.value), guild=guild)
            reward_message = f"{emoji or '🔮'} +1 reputation!"
            await ReputationService.add_rep(user_id=inviter.id, guild=guild)
        else:
            emoji = GuildSettingService.get_server_emoji(emoji_id=int(Emoji.SHOP_TOKEN.value), guild=guild)
            reward_message = f"{emoji or '🪙'} 10 Shop Tokens"
            await EconomyService.modify_tokens(
                user_id=inviter.id, amount=10, reason="Invite Reward", actor_id=inviter.id
            )

        await XPService.add_xp(user_id=inviter.id, amount=50, source="Invite reward")

        # --- Logging ---
        guild_settings = await GuildSettingService.get_guild_settings(guild=guild)
        if not guild_settings:
            logger.warning(f"[InviteTracker] No guild settings for {guild.id}")
            return

        log_channel_id = guild_settings.invite_logs_channel_id
        if not log_channel_id:
            return

        log_channel = guild.get_channel(int(log_channel_id))
        if not log_channel:
            logger.warning(f"[InviteTracker] Log channel {log_channel_id} not found in {guild.id}")
            return

        count = await Database.invite_joins().count_documents(
            {"guild_id": guild.id, "inviter_id": inviter.id}
        )

        embed = discord.Embed(
            title="🎉 New Invite Join",
            description=f"{member.mention} joined using {inviter.mention}'s invite!",
            color=discord.Color.green(),
        )
        embed.add_field(name="Inviter Total", value=f"**{count}** total invites", inline=True)
        if reward_message:
            embed.add_field(name="Invite Reward", value=reward_message, inline=True)

        await log_channel.send(embed=embed)
