import discord
from discord import app_commands
from discord.ext import commands

from core.logger import setup_logger
from modules.audit.services import AuditLogService
from modules.economy.services import EconomyService

logger = setup_logger("economy_cog")

class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- User Commands ---

    @app_commands.command(name="balance", description="Check your credit and token balance")
    async def balance_command(self, interaction: discord.Interaction, user: discord.User = None):
        target = user or interaction.user
        try:
            credits, tokens = await EconomyService.get_balances(target.id)
            
            embed = discord.Embed(title=f"💰 Balance: {target.display_name}", color=discord.Color.green())
            embed.add_field(name="Credits", value=f"{credits:,.2f}", inline=True)
            embed.add_field(name="Shop Tokens", value=f"{tokens:,}", inline=True)
            if target.avatar:
                embed.set_thumbnail(url=target.avatar.url)
            
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logger.error(f"Error in /balance: {e}")
            await interaction.response.send_message("Failed to fetch balance.", ephemeral=True)

    @app_commands.command(name="pay", description="Transfer credits to another user")
    async def pay_command(self, interaction: discord.Interaction, user: discord.User, amount: int):
        if user.id == interaction.user.id:
            await interaction.response.send_message("You cannot pay yourself.", ephemeral=True)
            return

        try:
            await EconomyService.transfer_tokens(interaction.user.id, user.id, amount)
            await interaction.response.send_message(f"✅ Successfully sent **{amount:,.2f}** credits to {user.mention}!")
        except ValueError as e:
            await interaction.response.send_message(f"Transfer failed: {str(e)}", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in /pay: {e}")
            await interaction.response.send_message("An unexpected error occurred.", ephemeral=True)

    # --- Admin Commands ---
    
    from modules.audit.services import AuditLogService


    # ... User Commands omitted for brevity ...

    # --- Admin Commands ---
    
    admin_group = app_commands.Group(name="admin-economy", description="Manage user balances")


    @admin_group.command(name="give-tokens", description="Add tokens to a user")
    @app_commands.checks.has_permissions(administrator=True)
    async def give_tokens(self, interaction: discord.Interaction, user: discord.User, amount: int, reason: str = "Admin Grant"):
        await EconomyService.modify_tokens(user.id, amount, reason, interaction.user.id)
        await interaction.response.send_message(f"Added **{amount}** tokens to {user.mention}.", ephemeral=True)

        await AuditLogService.log_action(
            "Economy: Give Tokens", 
            interaction.user, 
            f"Gave **{amount}** tokens to {user.mention}\n**Reason:** {reason}", 
            interaction.guild
        )

    @admin_group.command(name="remove-credits", description="Remove credits from a user")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_credits(self, interaction: discord.Interaction, user: discord.User, amount: float, reason: str = "Admin Fine"):
        try:
            await EconomyService.modify_credits(user.id, -amount, reason, interaction.user.id)
            await interaction.response.send_message(f"Removed **{amount}** credits from {user.mention}.", ephemeral=True)

            await AuditLogService.log_action(
                "Economy: Remove Credits", 
                interaction.user, 
                f"Removed **{amount}** credits from {user.mention}\n**Reason:** {reason}", 
                interaction.guild
            )
        except ValueError as e:
            await interaction.response.send_message(f"Failed: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
