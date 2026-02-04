import discord
from discord.ext import commands
from discord import app_commands

class GeneralCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="emojis", description="Displays all the emojis")
    @app_commands.guild_only()
    async def emojis(self, interaction: discord.Interaction):
        emojis= interaction.guild.emojis
        if not emojis:
            await interaction.response.send_message("There are no emojis in the server")
            return

        emoji_list = " ".join(f"{str(emoji)} -- {emoji.name} -- {emoji.animated} -- {emoji.id}\n" for emoji in emojis)
        embed = discord.Embed(title=f"Emojis in {interaction.guild.name}", description= emoji_list)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(GeneralCog(bot))