import asyncio
from core.database import Database
from core.models.base import MongoModel
from modules.shop.models import Category, Item
from core.config import settings

async def seed():
    print("Connecting to DB...")
    await Database.connect()
    
    # 1. Clear existing shop data (optional, be careful in prod)
    # await Database.categories().delete_many({})
    # await Database.items().delete_many({})

    # 2. check if empty
    if await Database.categories().count_documents({}) > 0:
        print("Database already has categories. Skipping seed.")
        await Database.close()
        return

    print("Seeding Categories...")
    cat_dinos = Category(name="Dinos", description="Top stat breeders and clones", rank=1, image_url="https://image.shutterstock.com/image-photo/dinosaur-park-260nw-369408086.jpg")
    cat_kits = Category(name="PvP Kits", description="Ready to fight kits", rank=2)
    
    # Save categories first to get IDs
    result_dinos = await Database.categories().insert_one(cat_dinos.to_mongo())
    cat_dinos_id = str(result_dinos.inserted_id)
    
    result_kits = await Database.categories().insert_one(cat_kits.to_mongo())
    cat_kits_id = str(result_kits.inserted_id)

    print("Seeding Items...")
    item_rex = Item(
        name="Tek Rex (High Stat)",
        description="Level 450 Tek Rex with 30k HP hatch.",
        category_id=cat_dinos_id,
        price=500,
        currency="credits",
        product_type="Dinos",
        image_url="https://static.wikia.nocookie.net/ark_gamepedia/images/c/c8/Tek_Rex.png"
    )
    
    item_fab_sniper = Item(
        name="Fab Sniper Kit",
        description="1x Ascendant Fab Sniper (298%), 500x Bullets",
        category_id=cat_kits_id,
        price=50,
        currency="tokens",
        product_type="Kits"
    )

    await Database.items().insert_one(item_rex.to_mongo())
    await Database.items().insert_one(item_fab_sniper.to_mongo())
    
    print("Seeding Complete!")
    await Database.close()

if __name__ == "__main__":
    asyncio.run(seed())
