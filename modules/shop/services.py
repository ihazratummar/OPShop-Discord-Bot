from typing import List, Optional
from bson import ObjectId
from core.database import Database
from modules.shop.models import Category, Item
from core.logger import setup_logger

logger = setup_logger("shop_service")

class CategoryService:
    @staticmethod
    async def create_category(category: Category) -> Category:
        """Create a new category in the database."""
        result = await Database.categories().insert_one(category.to_mongo())
        category.id = result.inserted_id
        logger.info(f"Created category: {category.name} ({category.id})")
        return category

    @staticmethod
    async def get_active_categories(parent_id: Optional[str] = None) -> List[Category]:
        """Fetch active categories, optionally filtered by parent_id."""
        query = {"is_active": True, "parent_id": parent_id}
        cursor = Database.categories().find(query).sort("rank", 1)
        categories = []
        async for doc in cursor:
            categories.append(Category(**doc))
        return categories

    @staticmethod
    async def get_category(category_id: str) -> Optional[Category]:
        """Get a category by ID."""
        try:
            doc = await Database.categories().find_one({"_id": ObjectId(category_id)})
            if doc:
                return Category(**doc)
        except Exception:
            pass
        return None

    @staticmethod
    async def get_all_categories(parent_id: Optional[str] = None) -> List[Category]:
        """Fetch all categories (including inactive), optionally filters by parent_id."""
        query = {"parent_id": parent_id}
        cursor = Database.categories().find(query).sort("rank", 1)
        categories = []
        async for doc in cursor:
            categories.append(Category(**doc))
        return categories

    @staticmethod
    async def update_category(category_id: str, updates: dict) -> bool:
        """Update a category."""
        result = await Database.categories().update_one(
            {"_id": ObjectId(category_id)},
            {"$set": updates}
        )
        return result.modified_count > 0

    @staticmethod
    async def get_subcategory_count(parent_id: str) -> int:
        """Get number of subcategories for a given parent."""
        return await Database.categories().count_documents({"parent_id": parent_id})

    @staticmethod
    async def get_category_stats_batch(category_ids: List[str]) -> dict:
        """
        Fetch item and subcategory counts for a list of categories efficiently.
        Returns: {category_id: {'items': count, 'subcats': count}}
        """
        if not category_ids:
            return {}

        stats = {cid: {'items': 0, 'subcats': 0} for cid in category_ids}
        
        # 1. Count Items
        item_pipeline = [
            {"$match": {"category_id": {"$in": category_ids}}},
            {"$group": {"_id": "$category_id", "count": {"$sum": 1}}}
        ]
        async for doc in Database.items().aggregate(item_pipeline):
            if doc["_id"] in stats:
                stats[doc["_id"]]["items"] = doc["count"]

        # 2. Count Subcategories
        subcat_pipeline = [
            {"$match": {"parent_id": {"$in": category_ids}}},
            {"$group": {"_id": "$parent_id", "count": {"$sum": 1}}}
        ]
        async for doc in Database.categories().aggregate(subcat_pipeline):
            if doc["_id"] in stats:
                stats[doc["_id"]]["subcats"] = doc["count"]
                
        return stats

    @staticmethod
    async def delete_category(category_id: str) -> bool:
        """Delete a category."""
        # Check for existing items
        count = await ItemService.get_item_count(category_id)
        if count > 0:
            raise ValueError(f"Cannot delete category: Contains {count} items. Delete items first.")

        # Check for subcategories
        sub_count = await CategoryService.get_subcategory_count(category_id)
        if sub_count > 0:
            raise ValueError(f"Cannot delete category: Contains {sub_count} subcategories. Delete them first.")
        
        result = await Database.categories().delete_one({"_id": ObjectId(category_id)})
        return result.deleted_count > 0

class ItemService:
    @staticmethod
    async def get_item_count(category_id: str) -> int:
        """Get number of items in a category."""
        return await Database.items().count_documents({"category_id": category_id})

    @staticmethod
    async def create_item(item: Item) -> Item:
        """Create a new item in the database."""
        result = await Database.items().insert_one(item.to_mongo())
        item.id = result.inserted_id
        logger.info(f"Created item: {item.name} ({item.id})")
        return item

    @staticmethod
    async def get_items_by_category(category_id: str, active_only: bool = True) -> List[Item]:
        """Fetch items in a specific category."""
        query = {"category_id": category_id}
        if active_only:
            query["is_active"] = True
            
        cursor = Database.items().find(query)
        items = []
        async for doc in cursor:
            items.append(Item(**doc))
        return items

    @staticmethod
    async def get_item(item_id: str) -> Optional[Item]:
        """Get an item by ID."""
        try:
            doc = await Database.items().find_one({"_id": ObjectId(item_id)})
            if doc:
                return Item(**doc)
        except Exception:
            pass
        return None

    @staticmethod
    async def update_item(item_id: str, updates: dict) -> bool:
        """Update an item."""
        result = await Database.items().update_one(
            {"_id": ObjectId(item_id)},
            {"$set": updates}
        )
        return result.modified_count > 0

    @staticmethod
    async def delete_item(item_id: str) -> bool:
        """Delete an item."""
        result = await Database.items().delete_one({"_id": ObjectId(item_id)})
        return result.deleted_count > 0
