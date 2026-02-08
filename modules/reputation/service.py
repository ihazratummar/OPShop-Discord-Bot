import time
import discord
import asyncio
import re

from core.constant import Emoji
from core.database import Database
from core.logger import setup_logger
from modules.economy.services import EconomyService
from modules.guild.service import GuildSettingService
from modules.reputation.models import ReputationLogs, ReputationTier
from modules.xp.services import XPService

logger = setup_logger("reputation")
class ReputationService:
    COOLDOWN_SECONDS = 60 * 60 * 24

    @staticmethod
    async def reputation(message: discord.Message):

        guild = message.guild

        if message.author.bot:
            return

        content = message.content.lower()

        if not re.search(r"\+\s*rep\b", content, re.IGNORECASE):
            return

        guild_settings = await GuildSettingService.get_guild_settings(guild=guild)

        if not guild_settings.rep_channel or message.channel.id != guild_settings.rep_channel:
            return

        mentions = message.mentions
        if len(mentions) != 1:
            await message.reply("You must mention exactly one user!")
            return

        target = mentions[0]
        if target.id == message.author.id:
            await message.reply("You can not rep yourself!")
            return

        guild_settings = await GuildSettingService.get_guild_settings(guild=guild)
        logger.debug(f"Guild settings: {guild_settings}")
        seller_role = guild.get_role(guild_settings.seller_role_id)
        logger.debug(f"Seller role: {seller_role}")
        if not seller_role:
            await message.reply(f"Seller role not configured!")
            return

        if not seller_role or seller_role not in target.roles:
            await message.reply(f"Only user with the {seller_role.name} role can receive reputation!")
            return

        review_text = message.content.replace("+rep", "")
        review_text = review_text.replace(target.mention, "").strip()
        # normalize empty → None
        if review_text == "":
            review_text = None

        # --- ALWAYS send confirmation messages, even if bonus logic fails ---
        try:
            rep_given_result = await Database.users().find_one_and_update(
                {"discord_id": message.author.id},
                {"$inc": {"rep_given_counter": 1}},
                upsert=True,
                return_document=True
            )
            counter = rep_given_result.get("rep_given_counter", 1)

            # Give buyer 10 tokens
            await EconomyService.modify_tokens(
                user_id=message.author.id,
                amount=10,
                reason="Reputation added",
                actor_id=message.author.id,
            )

            # Every 3rd rep, buyer gets bonus +1 rep
            if counter >= 3:
                await Database.users().update_one(
                    {"discord_id": message.author.id},
                    {"$set": {"rep_given_counter": 0}}
                )

                asyncio.create_task(
                    ReputationService.add_rep(
                        user_id=message.author.id,
                        guild=guild,
                        reputation_amount=1
                    )
                )

                await EconomyService.modify_tokens(
                    user_id=message.author.id,
                    amount=10,
                    reason="Reputation bonus for 3rd rep",
                    actor_id=message.author.id,
                )

                await message.reply(f"<a:arrow:1468247068240777238> {message.author.mention} has earned +1 rep <a:bluestar:1468261614200422471> for participating in a smooth trade and crediting the merchant")

        except Exception as e:
            logger.error(f"Error in bonus logic: {e}")

        # --- Add reputation to seller (always) ---
        asyncio.create_task(
            ReputationService.add_reputation(
                from_user_id=message.author.id,
                target_user_id=target.id,
                guild=message.guild,
                message=review_text
            )
        )

        # --- Send confirmation messages (ALWAYS) ---
        try:
            emoji = GuildSettingService.get_server_emoji(guild=guild, emoji_id=Emoji.SHOP_TOKEN.value)
            await message.channel.send(f"{message.author.mention} has earned {emoji if emoji else '🪙'} 10 Shop Tokens")
            await message.channel.send(f"{target.mention} has earned +1 <a:bluestar:1468261614200422471>.")
        except Exception as e:
            logger.error(f"Failed to send rep confirmation: {e}")

    @staticmethod
    async def add_reputation(from_user_id: int, target_user_id: int, guild: discord.Guild, message: str = None,
                             reputation_amount: int = 1, is_admin: bool = False):
        rep = ReputationLogs(
            from_user_id=from_user_id,
            to_user_id=target_user_id,
            guild_id=guild.id,
            timestamp=int(time.time()),
            message=message
        )
        await Database.reputations_logs().insert_one(rep.to_mongo())
        await XPService.add_xp(user_id=target_user_id, amount=reputation_amount * 10, source="reputation")
        if not is_admin:
            await XPService.add_xp(user_id=from_user_id, amount=10, source="reputation")

        await Database.users().update_one(
            {"discord_id": target_user_id},
            {"$inc": {"reputations": reputation_amount}},
            upsert=True
        )
        
        # 🤖 AUTOMATION START: Check if user unlocked a new shiny role!
        # We assume the bot has the guild object cached or we fetch it.
        # Since this is usually called from an interaction/message, we might not have guild handy passed in explicitly as object,
        # but we have guild_id. We need to fetch the guild to edit roles.
        if guild:
             await ReputationService.check_and_update_roles(user_id=target_user_id, guild=guild)
        # 🤖 AUTOMATION END

        await EconomyService.modify_tokens(
            user_id=from_user_id,
            amount=1,
            reason="Reputation added",
            actor_id=from_user_id,
        )

    @staticmethod
    async def check_and_update_roles(user_id: int, guild: discord.Guild):
        """
        🚀 Checks a user's reputation and updates their roles based on configured tiers.
        """
        # 1. Get current reputation
        user_doc = await Database.users().find_one({"discord_id": user_id})
        current_rep = user_doc.get("reputations", 0) if user_doc else 0

        # 2. Get member object (needed to add/remove roles)
        member = guild.get_member(user_id)
        if not member:
            return # User not in guild anymore? Ghost! 👻

        # 3. Get all configured tiers for this guild
        cursor = Database.reputations_tier().find({"guild_id": guild.id}).sort("threshold", 1)
        tiers = await cursor.to_list(length=None)

        # 4. Iterate and Award/Revoke
        for tier_doc in tiers:
            tier = ReputationTier(**tier_doc)
            role = guild.get_role(tier.role_id)
            
            if not role:
                continue # Role deleted? Skip it.

            # ✨ Unlock Logic
            if current_rep >= tier.threshold:
                if role not in member.roles:
                    try:
                        await member.add_roles(role, reason=f"Reached {current_rep} Reputation! 🎉")
                        # Use $addToSet to prevent duplicates
                        await Database.users().update_one(
                            {"discord_id": user_id},
                            {"$addToSet": {"reputation_tier_role": role.id}},
                            upsert=True
                        )
                        log_channel = await ReputationService.get_rep_log_channel(guild=guild)
                        if log_channel:
                            await log_channel.send(f"{member.mention} earned **{role.name}** for reaching {tier.threshold} reputation points!")
                        logger.info(f"Awarded role {role.name} to {member.name}")
                    except discord.Forbidden:
                        logger.warning(f"Missing permissions to add role {role.name}")
            
            # 🔒 Revoke Logic (If they lost rep or threshold changed)
            else:
                if role in member.roles:
                    try:
                        await member.remove_roles(role, reason=f"Reputation {current_rep} below threshold {tier.threshold}")

                        # Correctly remove the specific role ID
                        await Database.users().update_one(
                            {"discord_id": user_id},
                            {"$pull": {"reputation_tier_role": role.id}},
                            upsert=True
                        )

                        logger.info(f"Removed role {role.name} from {member.name}")
                    except discord.Forbidden:
                        logger.warning(f"Missing permissions to remove role {role.name}")

    @staticmethod
    async def add_rep(user_id: int, guild: discord.Guild, reputation_amount: int = 1):
        # ... (Same logic as above, just simplified)
        # We can probably deprecate this or merge logic, but sticking to update
        rep = ReputationLogs(
            to_user_id=user_id,
            guild_id= guild.id,
            timestamp=int(time.time()),
        )
        await Database.reputations_logs().insert_one(rep.to_mongo())
        await Database.users().update_one(
            {"discord_id": user_id},
            {"$inc": {"reputations": reputation_amount}},
            upsert=True
        )

        if guild:
             await ReputationService.check_and_update_roles(user_id=user_id, guild=guild)

        # Trigger check here too if needed, but add_rep seems unused in main flow.

    @staticmethod
    async def save_reputation_tier(role_id: int, guild_id: int, reputation_amount: int = 1) -> bool:
        rep = ReputationTier(
            role_id= role_id,
            guild_id= guild_id,
            threshold= reputation_amount
        )
        result = await Database.reputations_tier().update_one(
            {"guild_id": guild_id, "role_id": role_id},
            {"$set": rep.to_mongo() },
            upsert=True
        )
        return result.acknowledged

    @staticmethod
    async def remove_reputation_tier(role_id: int, guild_id: int) -> bool:
        result = await Database.reputations_tier().delete_one({"guild_id": guild_id, "role_id": role_id})
        return result.deleted_count > 0


    @staticmethod
    async def get_rep_log_channel(guild: discord.Guild) -> discord.TextChannel | None:
        guild_settings = await GuildSettingService.get_guild_settings(guild=guild)
        logs_channel = guild_settings.rep_log_channel
        if logs_channel:
            return guild.get_channel(logs_channel)
        return None



