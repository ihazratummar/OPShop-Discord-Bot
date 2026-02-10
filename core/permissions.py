from discord.ext import commands
from core.config import settings
from loguru import logger


# In the future, these can be loaded from DB or config
ADMIN_ROLE_IDS = [] # Populate with ID from config/DB
STAFF_ROLE_IDS = [] # Populate with ID from config/DB

def is_owner():
    """Check if the user is the bot owner."""
    async def predicate(ctx):
        return ctx.author.id == settings.owner_id
    return commands.check(predicate)

def is_admin():
    """Check if the user has admin permissions."""
    async def predicate(ctx):
        if ctx.author.id == settings.owner_id:
            return True
        # Check against ADMIN_ROLE_IDS or Discord permissions (Administrator)
        if hasattr(ctx.author, "guild_permissions") and ctx.author.guild_permissions.administrator:
            return True
        return False
    return commands.check(predicate)

def is_staff():
    """Check if the user has staff permissions."""
    async def predicate(ctx):
        if ctx.author.id == settings.owner_id:
            return True
        if hasattr(ctx.author, "guild_permissions") and ctx.author.guild_permissions.administrator:
            return True
        # Check roles if needed
        return False
    return commands.check(predicate)
