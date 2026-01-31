import asyncio
from core.database import Database
from core.config import settings

async def repair():
    print("Repairing DB...")
    await Database.connect()
    
    # Update all categories to have is_active=True if missing
    result = await Database.categories().update_many(
        {"is_active": {"$exists": False}},
        {"$set": {"is_active": True}}
    )
    print(f"Updated {result.modified_count} categories.")
    
    # Update all items to have is_active=True if missing
    result_items = await Database.items().update_many(
        {"is_active": {"$exists": False}},
        {"$set": {"is_active": True}}
    )
    print(f"Updated {result_items.modified_count} items.")

    await Database.close()

if __name__ == "__main__":
    asyncio.run(repair())
