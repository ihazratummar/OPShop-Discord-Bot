from typing import Tuple, Optional
from core.database import Database
from core.models.user import User
from modules.economy.models import Transaction
from loguru import logger


class TransactionService:
    @staticmethod
    async def log_transaction(transaction: Transaction) -> Transaction:
        """Log a new transaction."""
        result = await Database.transactions().insert_one(transaction.to_mongo())
        transaction.id = result.inserted_id
        logger.info(f"Logged transaction: {transaction.type} for {transaction.user_id}")
        return transaction

class EconomyService:
    @staticmethod
    async def get_user(user_id: int, username: str = "Unknown") -> User:
        """Get or create a user."""
        doc = await Database.users().find_one({"discord_id": user_id})
        if doc:
            return User(**doc)
        
        # Create new user
        new_user = User(discord_id=user_id, username=username, tokens=0, reputations=0, rep_given_counter=0)
        await Database.users().insert_one(new_user.to_mongo())
        return new_user

    @staticmethod
    async def get_balances(user_id: int) -> int:
        """Return (credits, tokens)."""
        user = await EconomyService.get_user(user_id)
        return user.tokens


    @staticmethod
    async def modify_tokens(user_id: int, amount: int, reason: str, actor_id: int) -> int:
        """Add/remove tokens and log transaction."""
        user = await EconomyService.get_user(user_id)
        new_balance = user.tokens + amount
        if new_balance < 0:
            raise ValueError("Insufficient tokens")

        await Database.users().update_one(
            {"discord_id": user_id},
            {"$set": {"tokens": new_balance}}
        )

        txn = Transaction(
            user_id=user_id,
            type='reward' if amount > 0 else 'redeem',
            amount_tokens=amount,
            description=reason,
            performed_by=actor_id,
        )
        await TransactionService.log_transaction(txn)

        return new_balance

    @staticmethod
    async def transfer_tokens(from_id: int, to_id: int, amount: int) -> bool:
        """Transfer credits between users with optional tax."""
        if amount <= 0:
            raise ValueError("Amount must be positive")

        # Check sender balance
        sender = await EconomyService.get_user(from_id)
        if sender.tokens < amount:
            raise ValueError("Insufficient funds")

        # Updates
        await EconomyService.modify_tokens(from_id, -amount, f"Transfer to {to_id}", from_id)
        await EconomyService.modify_tokens(to_id, int(amount), f"Transfer from {from_id} ", from_id)
        
        return True
