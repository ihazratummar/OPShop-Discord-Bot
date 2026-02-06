import time
import discord
import asyncio

from core.database import Database
from core.logger import setup_logger
from modules.economy.services import EconomyService
from modules.guild.service import GuildSettingService
from modules.reputation.models import ReputationLogs
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

        if "+rep" not in content.split():
            return

        if message.channel.name.lower() != "trusted-feedback":
            await message.reply("You must be in a trusted feedback channel.")
            await message.delete(delay=5)
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
            await asyncio.sleep(3)
            await message.channel.purge(limit=2)
            return

        review_text = message.content.replace("+rep", "")
        review_text = review_text.replace(target.mention, "").strip()
        # normalize empty → None
        if review_text == "":
            review_text = None

        rep_given_result = await  Database.users().find_one_and_update(
            {"discord_id": message.author.id},
            {"$inc": {"rep_given_counter": 1}},
            upsert=True,
            return_document=True
        )
        counter = rep_given_result.get("rep_given_counter", 1)

        if counter >= 3:
            await Database.users().update_one(
                {"discord_id": message.author.id},
                {
                    "$inc": {"reputations": 1},
                    "$set": {"rep_given_counter": 0}
                }
            )

            await EconomyService.modify_tokens(
                user_id= message.author.id,
                amount= 10,
                reason="Reputation added",
                actor_id=message.author.id,
            )

            await message.reply(f"<a:arrow:1468247068240777238> {message.author.mention} has earned +1 rep <a:bluestar:1468261614200422471> for participating in a smooth trade and crediting the merchant ")

        asyncio.create_task(
            ReputationService.add_reputation(
                from_user_id=message.author.id,
                target_user_id=target.id,
                guild_id=message.guild.id,
                message=review_text
            )
        )

        await message.channel.send(f"{target.mention} has earned +1 <a:bluestar:1468261614200422471>.")

    @staticmethod
    async def add_reputation(from_user_id: int, target_user_id: int, guild_id: int, message: str = None,
                             reputation_amount: int = 1, is_admin: bool = False):
        rep = ReputationLogs(
            from_user_id=from_user_id,
            to_user_id=target_user_id,
            guild_id=guild_id,
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
        await EconomyService.modify_tokens(
            user_id=from_user_id,
            amount=1,
            reason="Reputation added",
            actor_id=from_user_id,
        )

    @staticmethod
    async def add_rep(user_id: int, guild_id: int, reputation_amount: int = 1):
        rep = ReputationLogs(
            to_user_id=user_id,
            guild_id= guild_id,
            timestamp=int(time.time()),
        )
        await Database.reputations_logs().insert_one(rep.to_mongo())
        await Database.users().update_one(
            {"discord_id": user_id},
            {"$inc": {"reputations": reputation_amount}},
            upsert=True
        )

