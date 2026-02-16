from core.database import Database
from core.models.user import User


class ProfileService:
    @staticmethod
    async def get_leaderboard(limit: int = 10):
        """Get top users by Level/XP."""
        cursor = Database.users().find({}).sort([("reputations", -1)]).limit(limit)
        users = []
        async for doc in cursor:
            users.append(User(**doc))
        return users
