#!/usr/bin/env python3
"""Apply production MongoDB schema indexes/collections for Smart Grocery.

This script is idempotent: re-running it updates/ensures indexes safely.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from urllib.parse import urlparse

import certifi
from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import CollectionInvalid

load_dotenv()


def _get_mongo_uri() -> str:
    return (
        os.environ.get("MONGO_URI")
        or os.environ.get("MONGODB_URI")
        or "mongodb://localhost:27017/smart_grocery"
    )


def _get_database_name(uri: str) -> str:
    explicit = os.environ.get("DATABASE_NAME")
    if explicit:
        return explicit

    parsed = urlparse(uri)
    path_db = (parsed.path or "").lstrip("/")
    return path_db or "smart_grocery"


def _connect(uri: str) -> MongoClient:
    try:
        return MongoClient(uri, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=8000)
    except Exception:
        return MongoClient(uri, serverSelectionTimeoutMS=8000)


def _ensure_collection(db, name: str):
    if name in db.list_collection_names():
        return db[name], False
    try:
        db.create_collection(name)
        return db[name], True
    except CollectionInvalid:
        return db[name], False


def apply_schema(db) -> dict:
    created_collections = []
    created_indexes = []

    partial_unique_str = {"$type": "string"}

    defs = {
        "stores": [
            ([ ("storeId", ASCENDING) ], {"name": "idx_store_storeId", "unique": True, "partialFilterExpression": {"storeId": partial_unique_str}}),
            ([ ("name", ASCENDING) ], {"name": "idx_store_name"}),
        ],
        "brands": [
            ([ ("brandId", ASCENDING) ], {"name": "idx_brand_brandId", "unique": True, "partialFilterExpression": {"brandId": partial_unique_str}}),
            ([ ("name", ASCENDING) ], {"name": "idx_brand_name"}),
        ],
        "categories": [
            ([ ("categoryId", ASCENDING) ], {"name": "idx_category_categoryId", "unique": True, "partialFilterExpression": {"categoryId": partial_unique_str}}),
            ([ ("slug", ASCENDING) ], {"name": "idx_category_slug", "unique": True, "partialFilterExpression": {"slug": partial_unique_str}}),
            ([ ("parentId", ASCENDING) ], {"name": "idx_category_parentId"}),
            ([ ("path", ASCENDING) ], {"name": "idx_category_path"}),
        ],
        "products": [
            ([ ("productId", ASCENDING) ], {"name": "idx_product_productId", "unique": True, "partialFilterExpression": {"productId": partial_unique_str}}),
            ([ ("barcode", ASCENDING) ], {"name": "idx_product_barcode", "sparse": True}),
            ([ ("categoryId", ASCENDING) ], {"name": "idx_product_categoryId"}),
            ([ ("labels", ASCENDING) ], {"name": "idx_product_labels"}),
            ([ ("brandId", ASCENDING) ], {"name": "idx_product_brandId"}),
            ([ ("createdAt", DESCENDING) ], {"name": "idx_product_createdAt"}),
        ],
        "store_products": [
            ([ ("storeProductId", ASCENDING) ], {"name": "idx_store_product_id", "unique": True, "partialFilterExpression": {"storeProductId": partial_unique_str}}),
            ([ ("productId", ASCENDING) ], {"name": "idx_store_product_productId"}),
            ([ ("storeId", ASCENDING) ], {"name": "idx_store_product_storeId"}),
            ([ ("productId", ASCENDING), ("storeId", ASCENDING) ], {"name": "idx_store_product_product_store", "unique": True, "partialFilterExpression": {"productId": partial_unique_str, "storeId": partial_unique_str}}),
            ([ ("isAvailable", ASCENDING), ("lastPriceUpdate", DESCENDING) ], {"name": "idx_store_product_availability_update"}),
            ([ ("promoPrice", ASCENDING), ("basePrice", ASCENDING) ], {"name": "idx_store_product_prices"}),
        ],
        "price_history": [
            ([ ("historyId", ASCENDING) ], {"name": "idx_price_history_id", "unique": True, "partialFilterExpression": {"historyId": partial_unique_str}}),
            ([ ("storeProductId", ASCENDING), ("timestamp", DESCENDING) ], {"name": "idx_price_history_spid_timestamp"}),
        ],
        "users": [
            ([ ("userId", ASCENDING) ], {"name": "idx_user_userId", "unique": True, "partialFilterExpression": {"userId": partial_unique_str}}),
            ([ ("email", ASCENDING) ], {"name": "idx_user_email", "unique": True, "partialFilterExpression": {"email": partial_unique_str}}),
        ],
        "lists": [
            ([ ("listId", ASCENDING) ], {"name": "idx_list_listId", "unique": True, "partialFilterExpression": {"listId": partial_unique_str}}),
            ([ ("userId", ASCENDING) ], {"name": "idx_list_userId"}),
            ([ ("shareCode", ASCENDING) ], {"name": "idx_list_shareCode", "sparse": True}),
            ([ ("items.productId", ASCENDING) ], {"name": "idx_list_items_productId"}),
        ],
        "public_lists": [
            ([ ("id", ASCENDING) ], {"name": "idx_public_list_id", "unique": True, "partialFilterExpression": {"id": partial_unique_str}}),
            ([ ("type", ASCENDING), ("popularityScore", DESCENDING) ], {"name": "idx_public_list_type_popularity"}),
        ],
        "feedback": [
            ([ ("feedbackId", ASCENDING) ], {"name": "idx_feedback_id", "unique": True, "partialFilterExpression": {"feedbackId": partial_unique_str}}),
            ([ ("type", ASCENDING) ], {"name": "idx_feedback_type"}),
            ([ ("status", ASCENDING) ], {"name": "idx_feedback_status"}),
            ([ ("type", ASCENDING), ("status", ASCENDING) ], {"name": "idx_feedback_type_status"}),
            ([ ("createdAt", DESCENDING) ], {"name": "idx_feedback_createdAt"}),
        ],
        "scraper_rules": [
            ([ ("storeId", ASCENDING) ], {"name": "idx_scraper_rule_storeId", "unique": True, "partialFilterExpression": {"storeId": partial_unique_str}}),
            ([ ("updatedAt", DESCENDING) ], {"name": "idx_scraper_rule_updatedAt"}),
        ],
        "product_metrics": [
            ([ ("productId", ASCENDING) ], {"name": "idx_product_metrics_productId", "unique": True, "partialFilterExpression": {"productId": partial_unique_str}}),
            ([ ("popularityScore", DESCENDING) ], {"name": "idx_product_metrics_popularity"}),
            ([ ("trendScore", DESCENDING) ], {"name": "idx_product_metrics_trend"}),
        ],
        "schema_migrations": [
            ([ ("key", ASCENDING) ], {"name": "idx_schema_migrations_key", "unique": True, "partialFilterExpression": {"key": partial_unique_str}}),
        ],
    }

    for coll_name, indexes in defs.items():
        collection, created = _ensure_collection(db, coll_name)
        if created:
            created_collections.append(coll_name)

        for keys, options in indexes:
            collection.create_index(keys, **options)
            created_indexes.append(f"{coll_name}.{options['name']}")

    db["schema_migrations"].update_one(
        {"key": "production_schema_v1"},
        {
            "$set": {
                "key": "production_schema_v1",
                "appliedAt": datetime.now(timezone.utc),
                "description": "Core production schema collections and indexes",
            }
        },
        upsert=True,
    )

    return {
        "created_collections": created_collections,
        "indexes_ensured": len(created_indexes),
        "migration_key": "production_schema_v1",
    }


def main() -> None:
    uri = _get_mongo_uri()
    db_name = _get_database_name(uri)

    client = _connect(uri)
    client.admin.command("ping")

    db = client[db_name]
    result = apply_schema(db)

    print("MongoDB schema migration completed")
    print(f"Database: {db_name}")
    print(f"Created collections: {result['created_collections']}")
    print(f"Indexes ensured: {result['indexes_ensured']}")
    print(f"Migration key: {result['migration_key']}")


if __name__ == "__main__":
    main()
