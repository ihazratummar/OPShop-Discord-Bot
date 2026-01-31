import asyncio
import os
from core.bot import ShopBot
from core.config import settings

async def main():
    bot = ShopBot()
    async with bot:
        await bot.start(settings.discord_token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Critical error running bot: {e}")
