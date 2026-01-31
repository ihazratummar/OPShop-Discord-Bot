import discord
from discord.ui import View, Modal, TextInput, Button
from modules.economy.services import EconomyConfigService

class EconomyRulesModal(Modal):
    def __init__(self, config):
        super().__init__(title="Edit Economy Rules")
        self.config = config
        
        self.tax_input = TextInput(
            label="Transfer Tax Rate (0.0 - 1.0)", 
            default=str(config.tax_rate),
            placeholder="e.g. 0.05 for 5%"
        )
        self.xp_input = TextInput(
            label="Global XP Multiplier", 
            default=str(config.xp_multiplier),
            placeholder="e.g. 1.0, 2.0"
        )
        self.currency_input = TextInput(
            label="Currency Name", 
            default=config.currency_name,
            max_length=20
        )
        
        self.add_item(self.tax_input)
        self.add_item(self.xp_input)
        self.add_item(self.currency_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            tax = float(self.tax_input.value)
            if not (0 <= tax <= 1.0):
                raise ValueError("Tax must be between 0 and 1.")
                
            xp = float(self.xp_input.value)
            if xp < 0:
                raise ValueError("XP Multiplier must be positive.")
                
        except ValueError as e:
            await interaction.response.send_message(f"Invalid input: {str(e)}", ephemeral=True)
            return

        updates = {
            "tax_rate": tax,
            "xp_multiplier": xp,
            "currency_name": self.currency_input.value
        }
        
        await EconomyConfigService.update_config(updates)
        
        # Refresh the view
        new_config = await EconomyConfigService.get_config()
        view = EconomyRulesView()
        embed = view.get_embed(new_config)
        await interaction.response.edit_message(embed=embed, view=view)

class EconomyRulesView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @staticmethod
    def get_embed(config) -> discord.Embed:
        embed = discord.Embed(
            title="⚙️ Economy Configuration",
            description="Global settings for the economy and XP system.",
            color=discord.Color.dark_teal()
        )
        
        embed.add_field(name="💸 Tax Rate", value=f"{config.tax_rate * 100:.1f}%", inline=True)
        embed.add_field(name="⚡ XP Multiplier", value=f"{config.xp_multiplier}x", inline=True)
        embed.add_field(name="💰 Currency Name", value=config.currency_name, inline=True)
        
        return embed

    @discord.ui.button(label="Edit Rules", style=discord.ButtonStyle.primary, emoji="📝")
    async def edit_rules(self, interaction: discord.Interaction, button: Button):
        config = await EconomyConfigService.get_config()
        await interaction.response.send_modal(EconomyRulesModal(config))
