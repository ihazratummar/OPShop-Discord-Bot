import discord
from discord.ext import commands
from discord import app_commands

class EmbedModal(discord.ui.Modal):
    json_input = discord.ui.TextInput(
        label="Discohook JSON",
        style=discord.ui.TextStyle.paragraph,
        placeholder="Paste your JSON here...",
        required=True,
        max_length=4000
    )

    def __init__(self, channel: discord.TextChannel):
        super().__init__(title="Post Embed")
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        import json
        await interaction.response.defer(ephemeral=True)
        
        try:
            data = json.loads(self.json_input.value)
        except json.JSONDecodeError:
            await interaction.followup.send("❌ Invalid JSON.", ephemeral=True)
            return

        embeds = []
        content = None

        if isinstance(data, dict):
            content = data.get("content")
            if "embeds" in data and isinstance(data["embeds"], list):
                for emp_data in data["embeds"]:
                    try:
                        embeds.append(discord.Embed.from_dict(emp_data))
                    except:
                        pass
            elif "title" in data or "description" in data:
                embeds.append(discord.Embed.from_dict(data))
        elif isinstance(data, list):
            for emp_data in data:
                if isinstance(emp_data, dict):
                    try:
                        embeds.append(discord.Embed.from_dict(emp_data))
                    except:
                        pass

        if not embeds and not content:
            await interaction.followup.send("❌ No valid content or embeds found.", ephemeral=True)
            return
            
        if len(embeds) > 10:
            embeds = embeds[:10]

        try:
            await self.channel.send(content=content, embeds=embeds)
            await interaction.followup.send(f"✅ Posted to {self.channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to post: {e}", ephemeral=True)


class GeneralCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="post_embed", description="Post a JSON embed to a specific channel")
    @app_commands.describe(channel="The channel to post the embed in")
    @app_commands.default_permissions(administrator=True) 
    async def post_embed(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.send_modal(EmbedModal(channel))

    @app_commands.command(name="emojis", description="Displays all the emojis")
    @app_commands.guild_only()
    async def emojis(self, interaction: discord.Interaction):
        emojis= interaction.guild.emojis
        if not emojis:
            await interaction.response.send_message("There are no emojis in the server")
            return

        emoji_list = " ".join(f"{str(emoji)} -- {emoji.name} -- {emoji.animated} -- {emoji.id}\n" for emoji in emojis)
        # Split into chunks if too long
        if len(emoji_list) > 4000:
             emoji_list = emoji_list[:4000] + "..."
             
        embed = discord.Embed(title=f"Emojis in {interaction.guild.name}", description= emoji_list)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(GeneralCog(bot))