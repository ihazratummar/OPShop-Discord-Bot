import discord
from discord.ext import commands
from core.config import settings
from core.database import Database
from core.logger import setup_logger
import os

logger = setup_logger("bot")

class ShopBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix="!", # Temporary prefix, moving to slash commands mostly
            intents=intents,
            help_command=None,
            owner_id=settings.owner_id
        )

    async def setup_hook(self):
        """Called when bot is logging in."""
        logger.info("Starting up...")
        
        # Connect to Database
        await Database.connect()
        
        # Load extensions/modules
        await self.load_modules()
        
        # Sync slash commands
        logger.info("Syncing commands...")
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s).")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

    async def load_modules(self):
        """Recursively load modules."""
        # Load core directory extensions if any (e.g., global listeners)
        # Load 'modules' directory
        if os.path.exists("modules"):
            for root, dirs, files in os.walk("modules"):
                for file in files:
                    if file.endswith(".py") and not file.startswith("__"):
                        # Skip common non-extension files
                        if file in ["models.py", "services.py", "ui.py", "__init__.py"]:
                            continue
                            
                        # Construct module path: modules.shop.categories
                        rel_path = os.path.relpath(os.path.join(root, file), ".")
                        module_name = rel_path.replace(os.path.sep, ".")[:-3]
                        
                        try:
                            await self.load_extension(module_name)
                            logger.info(f"Loaded extension: {module_name}")
                        except commands.NoEntryPointError:
                            # Expected for utils/helper files that aren't cogs
                            pass
                        except Exception as e:
                            logger.error(f"Failed to load extension {module_name}: {e}")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info("Bot is ready and running!")

    async def close(self):
        """Called when bot is shutting down."""
        logger.info("Shutting down...")
        await Database.close()
        await super().close()
