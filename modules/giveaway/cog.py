from typing import List, Optional

import discord
from discord.ext import commands
from discord import app_commands


class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self) -> None:
        from loguru import logger
        from datetime import datetime, timezone
        from modules.giveaway.service import GiveawayService
        from modules.giveaway.model import GiveawaysModel
        from modules.giveaway.ui import GiveawayJoinView
        
        logger.info("Loading active giveaways...")
        
        try:
            active_giveaways = await GiveawayService.giveaways_collection().find({"ended": False}).to_list(length=None)
            for raw_giveaway in active_giveaways:
                giveaway = GiveawaysModel(**raw_giveaway)
                giveaway.id = raw_giveaway["_id"]
                
                # Register persistent view
                view = GiveawayJoinView(giveaway_id=str(giveaway.id))
                self.bot.add_view(view)
                
                # Check if it should have ended already
                if giveaway.end_at and datetime.utcnow() >= giveaway.end_at:
                    logger.info(f"Giveaway {giveaway.id} end time passed during downtime. Ending now.")
                    self.bot.loop.create_task(GiveawayService.end_giveaway_task(self.bot, str(giveaway.id)))
                else:
                    GiveawayService.schedule_giveaway_end(self.bot, giveaway)
                    
            logger.info(f"Successfully loaded {len(active_giveaways)} active giveaways.")
        except Exception as e:
            logger.error(f"Error loading active giveaways on startup: {e}")

    # ────────────────────── /gcreate ──────────────────────

    @app_commands.command(name="gcreate", description="Create a new Giveaway")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        required_role="Role required to enter the giveaway",
        blacklisted_role="Role blacklisted from entering the giveaway",
    )
    async def gcreate_command(
        self,
        interaction: discord.Interaction,
        required_role: str = None,
        blacklisted_role: str = None,
    ):
        from modules.giveaway.ui import CreateGiveawayModal
        
        required_roles = [int(required_role)] if required_role else None
        blacklisted_roles = [int(blacklisted_role)] if blacklisted_role else None
        
        await interaction.response.send_modal(
            CreateGiveawayModal(
                required_roles=required_roles,
                blacklisted_roles=blacklisted_roles,
            )
        )

    @app_commands.command(name="create_giveaway", description="Create a new Giveaway")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        required_role="Role required to enter the giveaway",
        blacklisted_role="Role blacklisted from entering the giveaway",
    )
    async def create_giveaway_command(self, interaction: discord.Interaction, required_role: str = None, blacklisted_role: str = None):
        from modules.giveaway.ui import DefaultGiveawayModal
        
        required_roles = [int(required_role)] if required_role else None
        blacklisted_roles = [int(blacklisted_role)] if blacklisted_role else None
        
        await interaction.response.send_modal(
            DefaultGiveawayModal(
                required_roles=required_roles,
                blacklisted_roles=blacklisted_roles,
            )
        )



    @create_giveaway_command.autocomplete("required_role")
    @gcreate_command.autocomplete("required_role")
    async def gcreate_required_role_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        return self._role_autocomplete(interaction, current)

    @create_giveaway_command.autocomplete("blacklisted_role")
    @gcreate_command.autocomplete("blacklisted_role")
    async def gcreate_blacklisted_role_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        return self._role_autocomplete(interaction, current)

    @staticmethod
    def _role_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        roles = interaction.guild.roles
        # Exclude @everyone and bot-managed roles
        filtered = [
            r for r in roles
            if r.name != "@everyone"
            and not r.managed
            and current.lower() in r.name.lower()
        ]
        return [
            app_commands.Choice(name=r.name, value=str(r.id))
            for r in filtered[:25]
        ]

    # ────────────────────── /gend ──────────────────────

    @app_commands.command(name="gend", description="End a giveaway early")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(giveaway_id="Select the giveaway to end")
    async def gend_command(self, interaction: discord.Interaction, giveaway_id: str):
        from modules.giveaway.service import GiveawayService
        await interaction.response.defer(ephemeral=True)

        giveaway = await GiveawayService.get_giveaway_by_id(giveaway_id)
        if not giveaway:
            await interaction.followup.send("❌ Giveaway not found.", ephemeral=True)
            return

        if giveaway.ended:
            await interaction.followup.send("❌ This giveaway has already ended.", ephemeral=True)
            return

        # Cancel APScheduler job if exists
        job_id = f"end_giveaway_{giveaway.id}"
        try:
            self.bot.scheduler.remove_job(job_id)
        except Exception:
            pass

        await GiveawayService.end_giveaway_task(self.bot, str(giveaway.id))
        await interaction.followup.send(f"✅ Giveaway **{giveaway.title}** has been ended.", ephemeral=True)

    @gend_command.autocomplete("giveaway_id")
    async def gend_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        from modules.giveaway.service import GiveawayService
        active = await GiveawayService.get_active_giveaways(interaction.guild.id)
        filtered = [
            g for g in active
            if current.lower() in g.title.lower() or current.lower() in str(g.id).lower()
        ]
        return [
            app_commands.Choice(
                name=f"{g.title[:80]} (Ends {g.end_at.strftime('%m/%d %H:%M') if g.end_at else 'N/A'})",
                value=str(g.id)
            )
            for g in filtered[:25]
        ]

    # ────────────────────── /giveaways ──────────────────────

    @app_commands.command(name="giveaways", description="View all giveaways in a paginated dashboard")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def giveaways_command(self, interaction: discord.Interaction):
        from modules.giveaway.service import GiveawayService
        from modules.giveaway.ui import GiveawayDashboardView
        
        await interaction.response.defer(ephemeral=True)
        
        all_giveaways = await GiveawayService.get_all_giveaways(interaction.guild.id)
        
        if not all_giveaways:
            await interaction.followup.send("📭 No giveaways found for this server.", ephemeral=True)
            return
        
        view = GiveawayDashboardView(giveaways=all_giveaways)
        embed = view._build_list_embed()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Giveaway(bot))
