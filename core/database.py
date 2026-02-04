from motor.motor_asyncio import AsyncIOMotorClient
from core.config import settings
from core.logger import setup_logger

logger = setup_logger("database")

class Database:
    _client: AsyncIOMotorClient = None
    _db = None

    @classmethod
    async def connect(cls):
        """Establish connection to MongoDB."""
        try:
            cls._client = AsyncIOMotorClient(settings.mongo_uri)
            cls._db = cls._client[settings.db_name]
            # Verify connection
            await cls._client.admin.command('ping')
            logger.info(f"Connected to MongoDB")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise e

    @classmethod
    async def close(cls):
        """Close connection to MongoDB."""
        if cls._client:
            cls._client.close()
            logger.info("Closed MongoDB connection")

    @classmethod
    def get_db(cls):
        """Get the database instance."""
        if cls._db is None:
            raise ConnectionError("Database not initialized. Call connect() first.")
        return cls._db

    # Helper methods for collections
    @classmethod
    def users(cls):
        return cls.get_db().users

    @classmethod
    def categories(cls):
        return cls.get_db().categories

    @classmethod
    def items(cls):
        return cls.get_db().items

    @classmethod
    def tickets(cls):
        return cls.get_db().tickets

    @classmethod
    def ticket_settings(cls):
        return cls.get_db().ticket_settings

    @classmethod
    def transactions(cls):
        return cls.get_db().transactions

    @classmethod
    def reputations_logs(cls):
        return cls.get_db().reputations_logs

    @classmethod
    def invites(cls):
        return cls.get_db().invites

    @classmethod
    def invite_joins(cls):
        return cls.get_db().invites_joins

    @classmethod
    def guild_settings(cls):
        return cls.get_db().guild_settings


