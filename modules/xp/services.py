import math
from core.database import Database
from core.models.user import User
from core.logger import setup_logger
from modules.economy.services import EconomyService

logger = setup_logger("xp_service")

class XPService:
    @staticmethod
    def calculate_level(xp: int) -> int:
        """
        Calculate level based on XP.
        Formula: Level = floor(sqrt(XP / 100)) + 1
        Examples:
        - 0 XP -> Lvl 1
        - 100 XP -> Lvl 2
        - 400 XP -> Lvl 3
        - 2500 XP -> Lvl 6
        """
        if xp < 100:
            return 1
        return math.floor(math.sqrt(xp / 100)) + 1

    @staticmethod
    def calculate_xp_for_level(level: int) -> int:
        """Calculate minimum XP required for a level."""
        if level <= 1:
            return 0
        return (level - 1) ** 2 * 100

    @staticmethod
    async def add_xp(user_id: int, amount: int, source: str) -> dict:
        """
        Add XP to a user. Returns dict with 'leveled_up': bool, 'new_level': int.
        """
        user = await EconomyService.get_user(user_id)
        
        # Apply Global Multiplier
        from modules.economy.services import EconomyConfigService
        config = await EconomyConfigService.get_config()
        effective_amount = int(amount * config.xp_multiplier)

        new_xp = user.xp + effective_amount
        new_level = XPService.calculate_level(new_xp)
        
        leveled_up = new_level > user.level
        
        updates = {"xp": new_xp}
        if leveled_up:
            updates["level"] = new_level

        await Database.users().update_one(
            {"discord_id": user_id},
            {"$set": updates}
        )
        
        if leveled_up:
            logger.info(f"User {user_id} leveled up to {new_level}!")

        return {
            "leveled_up": leveled_up,
            "new_level": new_level,
            "xp_added": effective_amount
        }

    @staticmethod
    async def get_leaderboard(limit: int = 10):
        """Get top users by Level/XP."""
        cursor = Database.users().find({}).sort([("level", -1), ("xp", -1)]).limit(limit)
        users = []
        async for doc in cursor:
            users.append(User(**doc))
        return users
