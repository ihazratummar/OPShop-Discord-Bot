import discord
from discord import app_commands
from discord.ext import commands
from modules.redeem.services import RedeemService
from core.logger import setup_logger

logger = setup_logger("redeem_cog")

class RedeemCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    redeem_group = app_commands.Group(name="redeem", description="Redeem your Shop Tokens for perks")

    @redeem_group.command(name="list", description="List available redemption options")
    async def redeem_list(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🎟️ Redemption Store", description="Spend your **Shop Tokens** on these perks!", color=discord.Color.purple())
        
        embed.add_field(
            name="💱 Currency Exchange", 
            value="Convert **100 Token** → **$10 💰**\nCommand: `/redeem credits <amount>`",
            inline=False
        )
        
        embed.add_field(
            name="🏷️ Change Nickname", 
            value="Cost: **5 Tokens**\nCommand: `/redeem nickname <new_name>`", 
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)

    @redeem_group.command(name="credits", description="Exchange Tokens for Credits (1 Token = 1000 Credits)")
    async def redeem_credits(self, interaction: discord.Interaction, token_amount: int):
        if token_amount < 10:
            await interaction.response.send_message("Must redeem at least 10 Shop Token.", ephemeral=True)
            return

        try:
            credits_received = await RedeemService.exchange_tokens_for_credits(interaction.user.id, token_amount)
            await interaction.response.send_message(f"✅ Exchanged **{token_amount}** Tokens for **{credits_received:,.0f}** Credits!")
        except Exception as e:
            await interaction.response.send_message(f"❌ Redemption failed: {e}", ephemeral=True)

    @redeem_group.command(name="nickname", description="Change your server nickname (Cost: 5 Tokens)")
    async def redeem_nickname(self, interaction: discord.Interaction, new_nickname: str):
        cost = 5
        try:
            await RedeemService.redeem_nickname(interaction.user, new_nickname, cost)
            await interaction.response.send_message(f"✅ Nickname changed to **{new_nickname}** for {cost} tokens!")
        except PermissionError:
             await interaction.response.send_message("❌ I don't have permission to change your nickname (You might be the owner or have a higher role).", ephemeral=True)
        except ValueError as e:
             await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
        except Exception as e:
             logger.error(f"Redeem nick error: {e}")
             await interaction.response.send_message("❌ Insufficient tokens or error occurred.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(RedeemCog(bot))
