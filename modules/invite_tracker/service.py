import asyncio
import datetime

import discord

from core.constant import Emoji
from core.database import Database, logger
from modules.economy.services import EconomyService
from modules.guild.service import GuildSettingService
from modules.reputation.service import ReputationService
from modules.xp.services import XPService


class InviteTrackerService:
    # Structure: { guild_id: { code: uses } }
    _cache: dict[int, dict[str, int]] = {}
    
    # Per-guild lock to ensure serial processing of cache updates/diffs
    _locks: dict[int, asyncio.Lock] = {}
    
    # Track if a guild's cache is fully initialized
    _ready: dict[int, bool] = {}

    @classmethod
    def _get_lock(cls, guild_id: int) -> asyncio.Lock:
        """Return a per-guild lock, creating it if needed"""
        if guild_id not in cls._locks:
            cls._locks[guild_id] = asyncio.Lock()
        return cls._locks[guild_id]

    @classmethod
    def is_ready(cls, guild_id: int) -> bool:
        """Check if the cache for a guild is populated."""
        return cls._ready.get(guild_id, False)

    @classmethod
    async def cache_guild(cls, guild: discord.Guild):
        """
        Snapshot all current invite uses for a guild.
        Must be called on bot startup/guild join to populate the baseline.
        """
        async with cls._get_lock(guild_id=guild.id):
            await cls._cache_guild_unsafe(guild)

    @classmethod
    async def _cache_guild_unsafe(cls, guild: discord.Guild):
        """
        Internal method to cache invites without acquiring the lock.
        Caller MUST hold the lock before calling this.
        """
        try:
            invites = await guild.invites()
        except discord.Forbidden:
            logger.warning(f"[InviteTracker] Missing 'Manage Guild' permissions for {guild.id}")
            return
        except discord.HTTPException as e:
            logger.error(f"[InviteTracker] Failed to fetch invites for {guild.id}: {e}")
            return

        # Build the cache snapshot
        snapshot = {invite.code: invite.uses for invite in invites}
        cls._cache[guild.id] = snapshot
        cls._ready[guild.id] = True
        
        logger.info(f"[InviteTracker] Cached {len(snapshot)} invites for guild {guild.id}")

        # Persist to DB for analytics (optional, but good for history)
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
        invite was just used. Returns the used Invite or None.
        
        CRITICAL: This assumes the caller holds the guild lock!
        """
        try:
            new_invites = await guild.invites()
        except discord.Forbidden:
            logger.warning(f"[InviteTracker] Cannot fetch invites for guild {guild.id} (Permission Log)")
            return None
        except discord.HTTPException:
            return None

        # If cache IS ready, use in-memory diff (fast)
        if cls.is_ready(guild.id):
            old_snapshot = cls._cache.get(guild.id, {})
            used_invite = None
            
            for invite in new_invites:
                old_uses = old_snapshot.get(invite.code, 0)
                if invite.uses > old_uses:
                    used_invite = invite
                    break

        else:
            # Cache NOT ready (Bot restart, race condition).
            # Attempt "Smart Panic Fetch": Compare API vs DB (Last Known State)
            logger.info(f"[InviteTracker] Cache not ready for {guild.id}. comparing vs DB history...")
            
            used_invite = None
            # Fetch all stored invites for this guild
            cursor = Database.invites().find({"guild_id": guild.id})
            db_snapshot = {doc["code"]: doc["uses"] async for doc in cursor}
            
            if not db_snapshot:
                # First run ever, no history. Cannot detect.
                logger.warning(f"[InviteTracker] No DB history for {guild.id}, cannot detect invite.")
                used_invite = None
            else:
                for invite in new_invites:
                    old_uses = db_snapshot.get(invite.code, 0)
                    if invite.uses > old_uses:
                        logger.info(f"[InviteTracker] Detected used invite via DB history: {invite.code} ({old_uses} -> {invite.uses})")
                        used_invite = invite
                        break
        
        # Update cache with new state immediately
        cls._cache[guild.id] = {inv.code: inv.uses for inv in new_invites}
        cls._ready[guild.id] = True
        
        # Persist new state to DB
        if used_invite:
            await Database.invites().update_one(
                {"guild_id": guild.id, "code": used_invite.code},
                {
                    "$set": {
                        "uses": used_invite.uses,
                        "inviter_id": used_invite.inviter.id if used_invite.inviter else None
                    }
                },
                upsert=True
            )
            
        return used_invite

    @classmethod
    async def process_join(
            cls,
            member: discord.Member,
            inviter: discord.Member | discord.User | None,
            guild: discord.Guild,
    ) -> None:
        # Prevent self-invite edge case
        if inviter and member.id == inviter.id:
            return

        # Atomic upsert: only insert if this (user, guild) pair doesn't exist yet.
        update_data = {
            "user_id": member.id,
            "guild_id": guild.id,
            "timestamp": datetime.datetime.utcnow(),
        }
        if inviter:
            update_data["inviter_id"] = inviter.id

        result = await Database.invite_joins().update_one(
            {"user_id": member.id, "guild_id": guild.id},
            {
                "$setOnInsert": update_data
            },
            upsert=True,
        )

        # Check if this is a rejoin
        is_rejoin = result.upserted_id is None

        if is_rejoin:
            logger.info(f"[InviteTracker] Rejoin detected for {member.id} in {guild.id}, skipping rewards.")
        else:
            # --- Rewards (only for new joins AND if inviter known) ---
            try:
                if inviter:
                    seller_role = await GuildSettingService.get_seller_role(guild=guild)

                    # Try to get inviter as member to check roles
                    inviter_member = guild.get_member(inviter.id)
                    if not inviter_member:
                        # Try fetching if not in cache
                        try:
                            inviter_member = await guild.fetch_member(inviter.id)
                        except discord.NotFound:
                            inviter_member = None

                    has_seller_role = inviter_member and seller_role in inviter_member.roles

                    if has_seller_role:
                        await ReputationService.add_rep(user_id=inviter.id, guild=guild)
                    else:
                         await EconomyService.modify_tokens(
                            user_id=inviter.id, amount=10, reason="Invite Reward", actor_id=inviter.id
                        )

                    await XPService.add_xp(user_id=inviter.id, amount=50, source="Invite reward")
                else:
                    logger.warning(f"[InviteTracker] Unknown inviter for {member.id} in {guild.id}, skipping rewards.")
            except Exception as e:
                logger.error(f"[InviteTracker] Error giving rewards: {e}")

        # --- Logging ---
        guild_settings = await GuildSettingService.get_guild_settings(guild=guild)
        if not guild_settings:
            return

        log_channel_id = guild_settings.invite_logs_channel_id
        if not log_channel_id:
            return

        log_channel = guild.get_channel(int(log_channel_id))
        if not log_channel:
             return

        if inviter:
            count = await Database.invite_joins().count_documents(
                {"guild_id": guild.id, "inviter_id": inviter.id}
            )
        else:
            count = 0

        # Build embed
        if is_rejoin:
            desc = f"{member.mention} rejoined"
            if inviter:
                desc += f" using {inviter.mention}'s invite!"
            else:
                desc += "."

            embed = discord.Embed(
                title="🔄 Member Rejoined",
                description=desc,
                color=discord.Color.blue(),
            )
            if inviter:
                embed.add_field(name="Inviter Total", value=f"**{count}** total invites", inline=True)
            embed.add_field(name="Note", value="No rewards given for rejoins", inline=True)

        else:
            # New join
            try:
                if inviter:
                    desc = f"{member.mention} joined using {inviter.mention}'s invite!"
                    embed = discord.Embed(
                        title="🎉 New Invite Join",
                        description=desc,
                        color=discord.Color.green(),
                    )

                    # Build reward message string
                    reward_message = ""
                    inviter_member = guild.get_member(inviter.id)
                    has_seller_role = inviter_member and seller_role in inviter_member.roles

                    if has_seller_role:
                        emoji = GuildSettingService.get_server_emoji(emoji_id=int(Emoji.BLUE_STAR.value), guild=guild)
                        reward_message = f"{emoji or '🔮'} +1 reputation!"
                    else:
                        emoji = GuildSettingService.get_server_emoji(emoji_id=int(Emoji.SHOP_TOKEN.value), guild=guild)
                        reward_message = f"{emoji or '🪙'} 10 Shop Tokens"

                    # xp_emoji = GuildSettingService.get_server_emoji(emoji_id=int(Emoji.XP.value), guild=guild)
                    xp_emoji = None
                    reward_message += f"\n{xp_emoji or '⭐'} +50 XP"

                    embed.add_field(name="Inviter Total", value=f"**{count}** total invites", inline=True)
                    embed.add_field(name="Invite Reward", value=reward_message, inline=True)
                else:
                    # Unknown inviter (e.g. vanity, bot restart race condition)
                    embed = discord.Embed(
                        title="👋 New Member Joined",
                        description=f"{member.mention} joined the server.",
                        color=discord.Color.light_grey(),
                    )
                    embed.add_field(name="Invite Info", value="Unknown (Bot restart or Vanity URL)", inline=True)
            except Exception as e:
                logger.error(f"[InviteTracker] Error building log embed for new join: {e}")
                # Fallback embed
                embed = discord.Embed(title="Member Joined", description=f"{member.mention} joined.", color=discord.Color.red())
                embed.add_field(name="Error", value="Could not build full log message")

        try:
            await log_channel.send(embed=embed)
        except Exception as e:
             logger.error(f"[InviteTracker] Failed to send log: {e}")


    @staticmethod
    async def get_join_data(user_id: int, guild_id: int):
        """Check if user previously joined this guild."""
        return await Database.invite_joins().find_one(
            {"user_id": user_id, "guild_id": guild_id}
        )