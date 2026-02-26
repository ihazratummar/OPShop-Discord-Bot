from datetime import datetime, timezone
from typing import List, Optional

import discord
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorCollection
from bson import ObjectId

from core.database import Database
from modules.giveaway.model import GiveawaysModel


class GiveawayService:

    @classmethod
    def giveaways_collection(cls) -> AsyncIOMotorCollection:
        return Database.giveaways()

    @classmethod
    def giveaway_entry_collection(cls) -> AsyncIOMotorCollection:
        return Database.giveaway_entries()

    @classmethod
    def giveaway_logs_collection(cls) -> AsyncIOMotorCollection:
        return Database.giveaway_logs()

    @classmethod
    async def save_giveaways(
            cls,
            guild_id: int,
            host_id: int,
            channel_id: int,
            message_id: int,
            giveaway_data: dict
    ) -> GiveawaysModel | None:
        try:
            # Derive a title for dashboard display from the first embed or content
            title = giveaway_data.get("title", "Giveaway")

            giveaway = GiveawaysModel(
                guild_id = guild_id,
                host_id = host_id,
                channel_id = channel_id,
                message_id = message_id,
                title = title,
                embed_json = giveaway_data.get("embed_json"),
                winner_count=giveaway_data["winner_count"],
                min_account_age=giveaway_data.get("min_account_age"),
                required_roles=giveaway_data.get("required_roles"),
                blacklisted_roles=giveaway_data.get("blacklisted_roles"),
                start_at= datetime.now(timezone.utc),
                end_at= giveaway_data["ends_at"],
                ended=False,
                total_entries=0,
             )
            save = await cls.giveaways_collection().insert_one(giveaway.to_mongo())
            if save.acknowledged:
                giveaway.id = save.inserted_id
                return giveaway
            else:
                return None
        except Exception as e:
            logger.error(f"Failed to save giveaway {e}")
            return None

    @classmethod
    async def get_active_giveaways(cls, guild_id: int) -> List[GiveawaysModel]:
        docs = await cls.giveaways_collection().find({
            "guild_id": guild_id,
            "ended": False
        }).to_list(length=None)
        result = []
        for doc in docs:
            g = GiveawaysModel(**doc)
            g.id = doc["_id"]
            result.append(g)
        return result

    @classmethod
    async def get_all_giveaways(cls, guild_id: int) -> List[GiveawaysModel]:
        docs = await cls.giveaways_collection().find({
            "guild_id": guild_id
        }).sort("start_at", -1).to_list(length=None)
        result = []
        for doc in docs:
            g = GiveawaysModel(**doc)
            g.id = doc["_id"]
            result.append(g)
        return result

    @classmethod
    async def get_giveaway_by_id(cls, giveaway_id: str) -> GiveawaysModel | None:
        doc = await cls.giveaways_collection().find_one({"_id": ObjectId(giveaway_id)})
        if doc:
            g = GiveawaysModel(**doc)
            g.id = doc["_id"]
            return g
        return None

    @classmethod
    async def handle_join(cls, interaction: discord.Interaction, giveaway_id: str):
        from modules.giveaway.model import GiveawayEntryModel
        
        giveaway_doc = await cls.giveaways_collection().find_one({"_id": ObjectId(giveaway_id)})
        if not giveaway_doc:
            await interaction.followup.send("❌ Giveaway not found.", ephemeral=True)
            return
            
        giveaway = GiveawaysModel(**giveaway_doc)
        
        if giveaway.ended:
            await interaction.followup.send("❌ This giveaway has already ended.", ephemeral=True)
            return

        # Check Required Roles
        if giveaway.required_roles:
            member_role_ids = [role.id for role in interaction.user.roles]
            has_required = any(r in member_role_ids for r in giveaway.required_roles)
            if not has_required:
                role_mentions = ", ".join([f"<@&{r}>" for r in giveaway.required_roles])
                await interaction.followup.send(f"❌ You need one of these roles to enter: {role_mentions}", ephemeral=True)
                return

        # Check Blacklisted Roles
        if giveaway.blacklisted_roles:
            member_role_ids = [role.id for role in interaction.user.roles]
            has_blacklisted = any(r in member_role_ids for r in giveaway.blacklisted_roles)
            if has_blacklisted:
                await interaction.followup.send("❌ You have a blacklisted role and cannot enter this giveaway.", ephemeral=True)
                return

        # Check Account Age
        if giveaway.min_account_age:
            age_required = giveaway.min_account_age
            account_age = datetime.now(timezone.utc) - interaction.user.created_at
            if account_age.total_seconds() < age_required:
                days_required = int(age_required / 86400)
                await interaction.followup.send(f"❌ Your account must be at least {days_required} days old to enter.", ephemeral=True)
                return
                
        # Check existing entry
        existing_entry = await cls.giveaway_entry_collection().find_one({
            "giveaway_id": ObjectId(giveaway_id),
            "user_id": interaction.user.id
        })
        
        if existing_entry:
            await interaction.followup.send("❌ You have already joined this giveaway!", ephemeral=True)
            return
            
        # Insert entry
        entry = GiveawayEntryModel(
            giveaway_id=ObjectId(giveaway_id),
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            valid=True,
            entered_at=datetime.now(timezone.utc)
        )
        
        await cls.giveaway_entry_collection().insert_one(entry.to_mongo())
        
        # Increment total entries
        result = await cls.giveaways_collection().find_one_and_update(
            {"_id": ObjectId(giveaway_id)},
            {"$inc": {"total_entries": 1}},
            return_document=True
        )
        new_count = result.get("total_entries", 0) if result else 0
        
        # Real-time embed update
        try:
            channel = interaction.guild.get_channel(giveaway.channel_id)
            if channel:
                message = await channel.fetch_message(giveaway.message_id)
                if message and message.embeds:
                    all_embeds = list(message.embeds)
                    # Update or add the Entries field on the LAST embed
                    target_embed = all_embeds[-1]
                    updated = False
                    for i, field in enumerate(target_embed.fields):
                        if field.name == "Entries":
                            target_embed.set_field_at(i, name="Entries", value=str(new_count), inline=True)
                            updated = True
                            break
                    if not updated:
                        target_embed.add_field(name="Entries", value=str(new_count), inline=True)
                    await message.edit(embeds=all_embeds)
        except Exception as e:
            logger.warning(f"Failed to update giveaway embed entry count: {e}")
        
        await interaction.followup.send("🎉 You have successfully joined the giveaway!", ephemeral=True)

    @classmethod
    def schedule_giveaway_end(cls, bot, giveaway: GiveawaysModel):
        logger.info(f"Scheduling giveaway {giveaway.id} to end at {giveaway.end_at}")
        bot.scheduler.add_job(
            cls.end_giveaway_task,
            'date',
            run_date=giveaway.end_at,
            args=[bot, str(giveaway.id)],
            id=f"end_giveaway_{giveaway.id}",
            replace_existing=True
        )

    @classmethod
    async def end_giveaway_task(cls, bot, giveaway_id: str):
        import random
        logger.info(f"Ending giveaway: {giveaway_id}")
        
        giveaway_doc = await cls.giveaways_collection().find_one({"_id": ObjectId(giveaway_id)})
        if not giveaway_doc:
            logger.error(f"Giveaway {giveaway_id} not found during end task.")
            return
            
        giveaway = GiveawaysModel(**giveaway_doc)
        
        if giveaway.ended:
            return
            
        # Fetch entries
        entries = await cls.giveaway_entry_collection().find({
            "giveaway_id": ObjectId(giveaway_id),
            "valid": True
        }).to_list(length=None)
        
        winners = []
        if len(entries) > 0:
            winner_count = min(giveaway.winner_count or 1, len(entries))
            winner_entries = random.sample(entries, winner_count)
            winners = [entry["user_id"] for entry in winner_entries]
            
        # Update Giveaway Document
        await cls.giveaways_collection().update_one(
            {"_id": ObjectId(giveaway_id)},
            {"$set": {
                "ended": True,
                "winners": winners
            }}
        )
        
        # Discord Actions
        try:
            guild = bot.get_guild(giveaway.guild_id)
            if guild:
                channel = guild.get_channel(giveaway.channel_id)
                if channel:
                    # Update Original Message
                    try:
                        message = await channel.fetch_message(giveaway.message_id)
                        
                        # Edit all existing embeds to show ended state
                        edited_embeds = []
                        for embed in message.embeds:
                            embed.color = discord.Color.red()
                            edited_embeds.append(embed)

                        # Add a result embed at the end
                        result_embed = discord.Embed(color=discord.Color.red())
                        result_embed.set_footer(text="🔴 Giveaway Ended")
                        if winners:
                            winner_mentions = ", ".join([f"<@{w}>" for w in winners])
                            result_embed.add_field(name="🏆 Winners", value=winner_mentions, inline=False)
                        else:
                            result_embed.add_field(name="🏆 Winners", value="No valid entries.", inline=False)
                        edited_embeds.append(result_embed)

                        # Disable Join button
                        from modules.giveaway.ui import GiveawayJoinView
                        view = GiveawayJoinView(giveaway_id=str(giveaway.id))
                        for child in view.children:
                            child.disabled = True
                        
                        await message.edit(embeds=edited_embeds, view=view)
                    except discord.NotFound:
                        logger.warning(f"Giveaway message {giveaway.message_id} not found.")

                    # Announce Winners
                    title = giveaway.title or "Giveaway"
                    if winners:
                        winner_mentions = ", ".join([f"<@{w}>" for w in winners])
                        await channel.send(f"🎉 Congratulations {winner_mentions}! You won **{title}**!")
                    else:
                        await channel.send(f"😢 Giveaway for **{title}** ended. No one entered!")
        except Exception as e:
            logger.error(f"Error executing discord actions for ended giveaway {giveaway_id}: {e}")
