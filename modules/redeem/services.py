import discord
from modules.economy.services import EconomyService
from core.logger import setup_logger

logger = setup_logger("redeem_service")

class RedeemService:
    @staticmethod
    async def exchange_tokens_for_credits(user_id: int, token_amount: int, rate: float = 1000.0) -> float:
        """
        Exchange tokens for credits.
        Rate: 1 Token = {rate} Credits
        """
        if token_amount <= 0:
            raise ValueError("Amount must be positive.")

        # 1. Deduct Tokens
        await EconomyService.modify_tokens(user_id, -token_amount, "Exchange for Credits", user_id)
        
        # 2. Add Credits
        credit_amount = token_amount * rate
        await EconomyService.modify_credits(user_id, credit_amount, f"Exchanged {token_amount} Tokens", user_id)
        
        logger.info(f"User {user_id} exchanged {token_amount} tokens for {credit_amount} credits.")
        return credit_amount

    @staticmethod
    async def redeem_nickname(member: discord.Member, new_nickname: str, cost: int = 5) -> bool:
        """
        Change user nickname for a token cost.
        """
        if not new_nickname:
            raise ValueError("Nickname cannot be empty.")
            
        # 1. Deduct Tokens
        await EconomyService.modify_tokens(member.id, -cost, f"Nickname Change: {new_nickname}", member.id)
        
        # 2. Change Nickname via Discord API
        try:
            await member.edit(nick=new_nickname)
            logger.info(f"User {member.id} changed nickname to {new_nickname}")
            return True
        except discord.Forbidden:
             # Refund if failed permissions
             await EconomyService.modify_tokens(member.id, cost, "Refund: Failed Nickname Change", member.id)
             raise PermissionError("Bot does not have permission to change your nickname (Hierarchy issue?).")
        except Exception as e:
             await EconomyService.modify_tokens(member.id, cost, "Refund: Failed Nickname Change", member.id)
             raise e
