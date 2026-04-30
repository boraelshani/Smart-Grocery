#!/usr/bin/env python3
"""Back up the current MongoDB data and normalize it into a professional schema.

The migration is intentionally additive:
- Legacy collections stay intact.
- Canonical collections are created or enriched in place.
- A raw backup is created before any writes happen.
"""

from __future__ import annotations

import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.apply_mongodb_production_schema import apply_schema
from scripts.backup_mongodb import create_backup
from utils.db import get_db


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "unknown"


def parse_price(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = re.sub(r"[^0-9,.-]", "", str(value)).replace(",", ".")
    try:
        return float(raw)
    except Exception:
        return None


def ensure_store(db, store_name: str, store_doc: dict | None = None) -> str | None:
    if not store_name:
        return None

    existing = db.stores.find_one({"name": {"$regex": f"^{re.escape(store_name)}$", "$options": "i"}})
    if existing and existing.get("storeId"):
        return existing["storeId"]

    store_id = f"store_{slugify(store_name)}"
    payload = {
        "storeId": store_id,
        "name": store_name,
        "logoUrl": (store_doc or {}).get("logoUrl") or (store_doc or {}).get("image"),
        "website": (store_doc or {}).get("url"),
        "country": (store_doc or {}).get("country") or "AT",
        "languages_available": (store_doc or {}).get("languages_available") or ["en", "de"],
        "apiAvailable": bool((store_doc or {}).get("apiAvailable", False)),
        "scrapingRequired": bool((store_doc or {}).get("scrapingRequired", True)),
        "updatedAt": now_utc(),
    }
    db.stores.update_one(
        {"storeId": store_id},
        {"$set": payload, "$setOnInsert": {"createdAt": now_utc()}},
        upsert=True,
    )
    return store_id


def ensure_brand(db, brand_name: str | None) -> str:
    brand_name = (brand_name or "Generic").strip() or "Generic"
    brand_id = f"brand_{slugify(brand_name)}"
    db.brands.update_one(
        {"brandId": brand_id},
        {
            "$set": {
                "brandId": brand_id,
                "name": brand_name,
                "logoUrl": None,
                "website": None,
                "updatedAt": now_utc(),
            },
            "$setOnInsert": {"createdAt": now_utc()},
        },
        upsert=True,
    )
    return brand_id


def ensure_category(db, category_name: str | None) -> str:
    category_name = (category_name or "Uncategorized").strip() or "Uncategorized"
    category_id = "cat_uncategorized" if category_name.lower() == "uncategorized" else f"cat_{slugify(category_name)}"
    db.categories.update_one(
        {"categoryId": category_id},
        {
            "$set": {
                "categoryId": category_id,
                "name_en": category_name,
                "name_de": category_name,
                "slug": slugify(category_name),
                "parentId": None,
                "path": [category_id],
                "fullPathNames": [
                    {
                        "categoryId": category_id,
                        "name_en": category_name,
                        "name_de": category_name,
                        "slug": slugify(category_name),
                    }
                ],
                "updatedAt": now_utc(),
            },
            "$setOnInsert": {"createdAt": now_utc()},
        },
        upsert=True,
    )
    return category_id


def normalize_stores(db) -> dict[str, str]:
    store_id_by_name = {}
    for row in list(db.stores.find({})):
        name = row.get("name")
        if not name:
            continue
        store_id = row.get("storeId") or f"store_{slugify(name)}"
        store_id_by_name[name.lower().strip()] = store_id
        db.stores.update_one(
            {"_id": row["_id"]},
            {
                "$set": {
                    "storeId": store_id,
                    "logoUrl": row.get("logoUrl") or row.get("image"),
                    "website": row.get("website") or row.get("url"),
                    "country": row.get("country") or "AT",
                    "languages_available": row.get("languages_available") or ["en", "de"],
                    "apiAvailable": row.get("apiAvailable", False),
                    "scrapingRequired": row.get("scrapingRequired", True),
                    "updatedAt": now_utc(),
                },
                "$setOnInsert": {"createdAt": row.get("createdAt") or now_utc()},
            },
        )
    return store_id_by_name


def normalize_products(db, store_id_by_name: dict[str, str]) -> dict[str, str]:
    product_id_by_name = {}
    store_product_seed_count = 0
    price_history_seed_count = 0

    brand_id = ensure_brand(db, "Generic")
    category_id = ensure_category(db, "Uncategorized")

    for row in list(db.products.find({})):
        name = (row.get("name_en") or row.get("name_de") or row.get("name") or "Unnamed Product").strip()
        row_id = str(row.get("_id"))
        product_id = row.get("productId") or f"prod_{slugify(name)}_{row_id}"
        product_id_by_name[name.lower().strip()] = product_id

        embedded_stores = row.get("stores") if isinstance(row.get("stores"), list) else []
        cheapest_price = None
        cheapest_store_product_id = None
        store_offers = []

        for store_row in embedded_stores:
            store_name = (store_row.get("store") or store_row.get("name") or "").strip()
            if not store_name:
                continue

            store_id = ensure_store(db, store_name, store_row)
            if store_id:
                store_id_by_name[store_name.lower().strip()] = store_id

            price = parse_price(store_row.get("price"))
            if price is None:
                continue

            store_product_id = f"sp_{product_id}_{store_id or slugify(store_name)}"
            store_offers.append(
                {
                    "storeProductId": store_product_id,
                    "productId": product_id,
                    "storeId": store_id,
                    "productPageUrl": store_row.get("url") or "",
                    "extractedImageUrl": store_row.get("image") or row.get("image") or row.get("defaultImageUrl"),
                    "basePrice": float(price),
                    "promoPrice": None,
                    "multiBuy": store_row.get("multiBuy") or {"type": "none", "details": {}},
                    "isAvailable": True,
                    "lastScrapeStatus": "legacy_import",
                    "offerStart": None,
                    "offerEnd": None,
                    "lastPriceUpdate": now_utc(),
                    "stockStatus": store_row.get("stockStatus") or "unknown",
                    "unitPriceComparison": {"value": None, "unit": None},
                }
            )

            if cheapest_price is None or price < cheapest_price:
                cheapest_price = float(price)
                cheapest_store_product_id = store_product_id

        db.products.update_one(
            {"_id": row["_id"]},
            {
                "$set": {
                    "productId": product_id,
                    "name_en": name,
                    "name_de": row.get("name_de") or name,
                    "name": row.get("name") or name,
                    "brandId": row.get("brandId") or brand_id,
                    "categoryId": row.get("categoryId") or category_id,
                    "categoryPath": row.get("categoryPath") or [category_id],
                    "unitSize": row.get("unitSize") or row.get("unit"),
                    "barcode": row.get("barcode"),
                    "defaultImageUrl": row.get("defaultImageUrl") or row.get("image"),
                    "labels": row.get("labels") or [],
                    "description_en": row.get("description_en") or row.get("description"),
                    "description_de": row.get("description_de") or row.get("description") or row.get("description_en"),
                    "cheapestPrice": cheapest_price if cheapest_price is not None else row.get("cheapestPrice") or row.get("price"),
                    "cheapestStoreProductId": cheapest_store_product_id or row.get("cheapestStoreProductId"),
                    "updatedAt": now_utc(),
                },
                "$setOnInsert": {"createdAt": row.get("createdAt") or now_utc()},
            },
        )

        for offer in store_offers:
            db.store_products.update_one(
                {"storeProductId": offer["storeProductId"]},
                {
                    "$set": offer | {"updatedAt": now_utc()},
                    "$setOnInsert": {"createdAt": now_utc()},
                },
                upsert=True,
            )

            if db.price_history.count_documents({"storeProductId": offer["storeProductId"]}) == 0:
                db.price_history.insert_one(
                    {
                        "historyId": f"hist_{offer['storeProductId']}",
                        "storeProductId": offer["storeProductId"],
                        "productId": product_id,
                        "storeId": offer["storeId"],
                        "oldPrice": None,
                        "newPrice": offer["basePrice"],
                        "currency": "EUR",
                        "source": "legacy_import",
                        "reason": "seeded from legacy products.stores",
                        "timestamp": now_utc(),
                    }
                )
                price_history_seed_count += 1

        store_product_seed_count += len(store_offers)

    return {
        "product_id_by_name": product_id_by_name,
        "store_product_seed_count": store_product_seed_count,
        "price_history_seed_count": price_history_seed_count,
    }


def normalize_featured_deals(db, product_id_by_name: dict[str, str], store_id_by_name: dict[str, str]) -> int:
    upserted = 0
    for row in list(db.featured_deals.find({})):
        title = (row.get("title") or "Featured Deal").strip()
        store_name = (row.get("store") or row.get("source") or "").strip()
        store_id = store_id_by_name.get(store_name.lower().strip()) if store_name else None
        product_id = product_id_by_name.get(title.lower().strip())
        promotion_id = row.get("promotionId") or f"promo_{slugify(title)}_{str(row.get('_id'))}"

        db.promotions.update_one(
            {"promotionId": promotion_id},
            {
                "$set": {
                    "promotionId": promotion_id,
                    "promotionType": "featured_deal",
                    "sourceCollection": "featured_deals",
                    "productId": product_id,
                    "storeId": store_id,
                    "storeName": store_name,
                    "title": title,
                    "priceText": row.get("price"),
                    "imageUrl": row.get("image"),
                    "claims": row.get("claims", 0),
                    "claimedBy": row.get("claimed_by", []),
                    "status": "active",
                    "updatedAt": now_utc(),
                },
                "$setOnInsert": {"createdAt": row.get("createdAt") or now_utc()},
            },
            upsert=True,
        )
        upserted += 1

    return upserted


def normalize_legacy_offer_collections(db, product_id_by_name: dict[str, str], store_id_by_name: dict[str, str]) -> dict:
    counts = {"multibuy": 0, "quantity_discount": 0}

    for row in list(db.multibuy_offers.find({})):
        title = (row.get("title") or row.get("product_name") or "Multibuy Offer").strip()
        product_name = (row.get("product_name") or title).strip()
        store_name = (row.get("store") or row.get("storeName") or "").strip()
        store_id = store_id_by_name.get(store_name.lower().strip()) if store_name else None
        product_id = product_id_by_name.get(product_name.lower().strip()) or product_id_by_name.get(title.lower().strip())
        promotion_id = f"promo_multibuy_{str(row.get('_id'))}"

        db.promotions.update_one(
            {"promotionId": promotion_id},
            {
                "$set": {
                    "promotionId": promotion_id,
                    "promotionType": "multibuy",
                    "sourceCollection": "multibuy_offers",
                    "legacyCollection": "multibuy_offers",
                    "legacyDocId": str(row.get("_id")),
                    "productId": product_id,
                    "productName": product_name,
                    "storeId": store_id,
                    "storeName": store_name,
                    "title": title,
                    "status": "active" if row.get("active", True) else "inactive",
                    "active": bool(row.get("active", True)),
                    "buyQuantity": row.get("buy_quantity") or row.get("buyQuantity"),
                    "freeQuantity": row.get("free_quantity") or row.get("freeQuantity"),
                    "discountLabel": row.get("discount_label"),
                    "originalPrice": row.get("original_price"),
                    "priceText": row.get("price"),
                    "validUntil": row.get("valid_until") or row.get("validUntil"),
                    "imageUrl": row.get("image"),
                    "category": row.get("category"),
                    "description": row.get("description"),
                    "rawData": row,
                    "updatedAt": now_utc(),
                },
                "$setOnInsert": {"createdAt": now_utc()},
            },
            upsert=True,
        )
        counts["multibuy"] += 1

    for row in list(db.quantity_discounts.find({})):
        title = (row.get("product_name") or row.get("title") or "Quantity Discount").strip()
        store_name = (row.get("store") or row.get("storeName") or "").strip()
        store_id = store_id_by_name.get(store_name.lower().strip()) if store_name else None
        product_name = (row.get("product_name") or title).strip()
        product_id = product_id_by_name.get(product_name.lower().strip()) or product_id_by_name.get(title.lower().strip())
        promotion_id = f"promo_quantity_discount_{str(row.get('_id'))}"

        tiers = row.get("discount_tiers") or row.get("tiers") or []
        db.promotions.update_one(
            {"promotionId": promotion_id},
            {
                "$set": {
                    "promotionId": promotion_id,
                    "promotionType": "quantity_discount",
                    "sourceCollection": "quantity_discounts",
                    "legacyCollection": "quantity_discounts",
                    "legacyDocId": str(row.get("_id")),
                    "productId": product_id,
                    "productName": product_name,
                    "storeId": store_id,
                    "storeName": store_name,
                    "title": title,
                    "status": "active" if row.get("active", True) else "inactive",
                    "active": bool(row.get("active", True)),
                    "basePrice": row.get("base_price") or row.get("basePrice"),
                    "priceText": row.get("base_price") or row.get("basePrice"),
                    "discountTiers": tiers,
                    "discountLabel": row.get("discount_label"),
                    "imageUrl": row.get("image"),
                    "category": row.get("category"),
                    "description": row.get("description"),
                    "rawData": row,
                    "updatedAt": now_utc(),
                },
                "$setOnInsert": {"createdAt": now_utc()},
            },
            upsert=True,
        )
        counts["quantity_discount"] += 1

    return counts


def normalize_users_and_lists(db) -> int:
    list_seed_count = 0

    for row in list(db.users.find({})):
        email = row.get("email")
        if not email:
            continue

        user_id = row.get("userId") or f"user_{slugify(email)}"
        db.users.update_one(
            {"_id": row["_id"]},
            {
                "$set": {
                    "userId": user_id,
                    "email": email,
                    "name": row.get("name") or email,
                    "shopping_list": row.get("shopping_list") or [],
                    "total_cost": row.get("total_cost") or 0.0,
                    "updatedAt": now_utc(),
                },
                "$setOnInsert": {"createdAt": row.get("createdAt") or now_utc()},
            },
        )

        items = row.get("shopping_list") if isinstance(row.get("shopping_list"), list) else []
        if items:
            list_id = f"list_{slugify(email)}_shopping"
            normalized_items = []
            for item in items:
                if isinstance(item, dict):
                    normalized_items.append(
                        {
                            "name": item.get("name") or item.get("title"),
                            "productId": item.get("productId") or item.get("id"),
                            "price": item.get("price"),
                            "store": item.get("store") or item.get("source"),
                            "image": item.get("image"),
                        }
                    )
                else:
                    normalized_items.append({"name": str(item)})

            db.lists.update_one(
                {"listId": list_id},
                {
                    "$set": {
                        "listId": list_id,
                        "userId": user_id,
                        "name": "Shopping List",
                        "items": normalized_items,
                        "shared": False,
                        "isDefault": True,
                        "updatedAt": now_utc(),
                    },
                    "$setOnInsert": {"createdAt": row.get("createdAt") or now_utc()},
                },
                upsert=True,
            )
            list_seed_count += 1

    return list_seed_count


def record_migration(db, backup_dir: str, summary: dict) -> None:
    db.schema_migrations.update_one(
        {"key": "professional_schema_v1"},
        {
            "$set": {
                "key": "professional_schema_v1",
                "appliedAt": now_utc(),
                "backupDir": backup_dir,
                "summary": summary,
                "notes": "Normalized legacy collections into canonical product/store/history/list collections while preserving original data.",
            }
        },
        upsert=True,
    )


def migrate() -> dict:
    db = get_db()
    if db is None:
        raise RuntimeError("Database unavailable")

    backup = create_backup()
    apply_schema(db)

    store_id_by_name = normalize_stores(db)
    product_result = normalize_products(db, store_id_by_name)
    promotion_count = normalize_featured_deals(db, product_result["product_id_by_name"], store_id_by_name)
    legacy_offer_counts = normalize_legacy_offer_collections(db, product_result["product_id_by_name"], store_id_by_name)
    list_seed_count = normalize_users_and_lists(db)

    summary = {
        "backupDir": backup["backup_dir"],
        "storesNormalized": len(store_id_by_name),
        "productsNormalized": len(product_result["product_id_by_name"]),
        "storeProductsSeeded": product_result["store_product_seed_count"],
        "priceHistorySeeded": product_result["price_history_seed_count"],
        "promotionsSeeded": promotion_count + legacy_offer_counts["multibuy"] + legacy_offer_counts["quantity_discount"],
        "legacyOffersMigrated": legacy_offer_counts,
        "listsSeeded": list_seed_count,
        "collections": db.list_collection_names(),
    }
    record_migration(db, backup["backup_dir"], summary)
    return summary


def main() -> None:
    result = migrate()
    print("Professional MongoDB migration completed")
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()