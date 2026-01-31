import asyncio
from core.database import Database
from core.config import settings

async def debug_db():
    print(f"Connecting to DB: {settings.db_name} at {settings.mongo_uri}...")
    await Database.connect()
    
    # List collections
    collections = await Database.get_db().list_collection_names()
    print(f"Collections: {collections}")
    
    # Count categories
    cat_count = await Database.categories().count_documents({})
    active_cat_count = await Database.categories().count_documents({"is_active": True})
    print(f"Total Categories: {cat_count}")
    print(f"Active Categories: {active_cat_count}")
    
    cursor = Database.categories().find({})
    async for doc in cursor:
          print(f"Category: {doc.get('name')}, Active: {doc.get('is_active')}, ID: {doc.get('_id')}")

    await Database.close()

if __name__ == "__main__":
    asyncio.run(debug_db())
