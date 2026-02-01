import discord
from discord.ui import View, Button
from modules.tickets.services import TicketService
from modules.economy.services import TransactionService, EconomyService
from modules.economy.models import Transaction
from modules.shop.services import ItemService
from modules.xp.services import XPService

class TicketControlView(View):
    def __init__(self, ticket_id: str):
        super().__init__(timeout=None) # Persistent view logic needs setup, for now simple
        self.ticket_id = ticket_id

    @discord.ui.button(label="Complete Order", style=discord.ButtonStyle.green, emoji="✅")
    async def complete_order(self, interaction: discord.Interaction, button: Button):
        # 1. Get ticket details
        ticket = await TicketService.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
             await interaction.response.send_message("Ticket not found!", ephemeral=True)
             return

        # 2. Get Item details if exists
        item = None
        if ticket.related_item_id:
            item = await ItemService.get_item(ticket.related_item_id)

        # 3. Log Transaction
        txn = Transaction(
            user_id=ticket.user_id,
            type='purchase',
            amount_credits=item.price if item and item.currency == 'credits' else 0,
            amount_tokens=item.price if item and item.currency == 'tokens' else 0,
            item_id=str(item.id) if item else None,
            item_name=item.name if item else "Custom Order",
            performed_by=interaction.user.id
        )
        await TransactionService.log_transaction(txn)

        # 3.5 Award Rewards (Tokens & XP)
        if item:
            # Tokens
            if item.token_reward > 0:
                await EconomyService.modify_tokens(
                    ticket.user_id, 
                    item.token_reward, 
                    f"Reward for purchasing {item.name}", 
                    interaction.user.id
                )
                await interaction.channel.send(f"🎉 User rewarded **{item.token_reward}** Tokens!")
            
            # XP (Price / 10)
            if item.price > 0:
                xp_amount = int(item.price / 10)
                if xp_amount > 0:
                    result = await XPService.add_xp(ticket.user_id, xp_amount, "purchase")
                    msg = f"✨ User earned **{xp_amount} XP**!"
                    if result['leveled_up']:
                        msg += f"\n🆙 **LEVEL UP!** Now Level **{result['new_level']}**!"
                    await interaction.channel.send(msg)

        # 4. Close Ticket
        await TicketService.close_ticket(ticket, interaction.user.id, interaction.client, interaction.guild)
        
        await interaction.response.send_message("Order completed! formatting transcript...", ephemeral=True)
        await interaction.channel.send(f"✅ **Order Completed** by {interaction.user.mention}. Ticket closing in 5 seconds.")
        
        import asyncio
        await asyncio.sleep(5)
        await interaction.channel.delete() 

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close_ticket_btn(self, interaction: discord.Interaction, button: Button):
        ticket = await TicketService.get_ticket_by_channel(interaction.channel_id)
        if ticket:
             await TicketService.close_ticket(ticket, interaction.user.id, interaction.client, interaction.guild)
        
        await interaction.response.send_message("Closing ticket...", ephemeral=True)
        await interaction.channel.send(f"🔒 **Ticket Closed** by {interaction.user.mention}. Closing in 5 seconds.")
        
        import asyncio
        await asyncio.sleep(5)
        # await interaction.channel.delete()
