#!/usr/bin/env python3
"""Migrate legacy product/store documents into production catalog collections.

Idempotent enough for repeated runs; it upserts by generated stable IDs.
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

import certifi
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()


def slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "unknown"


def now_utc():
    return datetime.now(timezone.utc)


def normalize_dt(value):
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def parse_price(raw):
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    txt = str(raw)
    txt = re.sub(r"[^0-9,.-]", "", txt).replace(",", ".")
    try:
        return float(txt)
    except Exception:
        return None


def get_db():
    uri = os.environ.get("MONGO_URI") or os.environ.get("MONGODB_URI") or "mongodb://localhost:27017/smart_grocery"
    db_name = os.environ.get("DATABASE_NAME")
    if not db_name:
        db_name = urlparse(uri).path.lstrip("/") or "smart_grocery"
    client = MongoClient(uri, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=8000)
    client.admin.command("ping")
    return client[db_name]


def ensure_store_id(db, store_name):
    if not store_name:
        return None
    existing = db.stores.find_one({"name": {"$regex": f"^{re.escape(store_name)}$", "$options": "i"}})
    if existing:
        if existing.get("storeId"):
            return existing.get("storeId")
        sid = f"store_{slugify(store_name)}"
        db.stores.update_one({"_id": existing["_id"]}, {"$set": {"storeId": sid, "updatedAt": now_utc()}}, upsert=False)
        return sid

    sid = f"store_{slugify(store_name)}"
    db.stores.update_one(
        {"storeId": sid},
        {
            "$setOnInsert": {
                "storeId": sid,
                "name": store_name,
                "logoUrl": None,
                "website": None,
                "country": "AT",
                "languages_available": ["en", "de"],
                "apiAvailable": False,
                "scrapingRequired": True,
                "createdAt": now_utc(),
            },
            "$set": {"updatedAt": now_utc()},
        },
        upsert=True,
    )
    return sid


def ensure_category(db, category_name):
    if not category_name:
        category_name = "Uncategorized"

    slug = slugify(category_name)
    cid = f"cat_{slug}"
    db.categories.update_one(
        {"categoryId": cid},
        {
            "$setOnInsert": {
                "categoryId": cid,
                "name_en": category_name,
                "name_de": category_name,
                "slug": slug,
                "parentId": None,
                "path": [cid],
                "fullPathNames": [
                    {
                        "categoryId": cid,
                        "name_en": category_name,
                        "name_de": category_name,
                        "slug": slug,
                    }
                ],
                "createdAt": now_utc(),
            },
            "$set": {"updatedAt": now_utc()},
        },
        upsert=True,
    )
    return cid


def ensure_brand(db, brand_name):
    if not brand_name:
        brand_name = "Generic"
    bid = f"brand_{slugify(brand_name)}"
    db.brands.update_one(
        {"brandId": bid},
        {
            "$setOnInsert": {
                "brandId": bid,
                "name": brand_name,
                "logoUrl": None,
                "website": None,
                "createdAt": now_utc(),
            },
            "$set": {"updatedAt": now_utc()},
        },
        upsert=True,
    )
    return bid


def detect_brand_from_name(name):
    if not name:
        return "Generic"
    pieces = re.split(r"\s+", str(name).strip())
    return pieces[0] if pieces else "Generic"


def migrate(db):
    legacy_products = list(db.products.find({"productId": {"$exists": False}}))
    migrated_products = 0
    migrated_store_products = 0

    for row in legacy_products:
        name = (row.get("name") or row.get("title") or "Unnamed Product").strip()
        category = row.get("category") or "Uncategorized"
        brand_name = row.get("brand") or detect_brand_from_name(name)

        brand_id = ensure_brand(db, brand_name)
        category_id = ensure_category(db, category)

        pid = f"prod_{slugify(name)}_{str(row.get('_id'))[-6:]}"
        labels = set(row.get("labels") or [])

        created_at = row.get("created_at") if isinstance(row.get("created_at"), datetime) else now_utc()

        db.products.update_one(
            {"productId": pid},
            {
                "$set": {
                    "productId": pid,
                    "name_en": name,
                    "name_de": name,
                    "brandId": brand_id,
                    "categoryId": category_id,
                    "categoryPath": [category_id],
                    "unitSize": row.get("unit") or row.get("unitSize"),
                    "barcode": row.get("barcode"),
                    "defaultImageUrl": row.get("image") or row.get("defaultImageUrl"),
                    "legalImageStatus": row.get("legalImageStatus") or "placeholder",
                    "labels": sorted(labels),
                    "description_en": row.get("description") or row.get("description_en"),
                    "description_de": row.get("description_de") or row.get("description") or row.get("description_en"),
                    "updatedAt": now_utc(),
                },
                "$setOnInsert": {"createdAt": created_at},
            },
            upsert=True,
        )

        migrated_products += 1

        stores = row.get("stores") if isinstance(row.get("stores"), list) else []
        if not stores and row.get("store"):
            stores = [{"store": row.get("store"), "price": row.get("price")}]

        for s in stores:
            store_name = s.get("store") or s.get("name")
            store_id = ensure_store_id(db, store_name)
            if not store_id:
                continue

            price = parse_price(s.get("price"))
            if price is None:
                price = parse_price(row.get("price_val") or row.get("price"))
            if price is None:
                price = 0.0

            spid = f"sp_{pid}_{store_id}"
            db.store_products.update_one(
                {"storeProductId": spid},
                {
                    "$set": {
                        "storeProductId": spid,
                        "productId": pid,
                        "storeId": store_id,
                        "productPageUrl": s.get("url") or row.get("url") or "",
                        "extractedImageUrl": s.get("image") or row.get("image"),
                        "basePrice": float(price),
                        "promoPrice": None,
                        "multiBuy": {"type": "none", "details": {}},
                        "isAvailable": True,
                        "lastScrapeStatus": "ok",
                        "offerStart": None,
                        "offerEnd": None,
                        "lastPriceUpdate": now_utc(),
                        "stockStatus": "unknown",
                        "unitPriceComparison": {"value": None, "unit": None},
                        "updatedAt": now_utc(),
                    },
                    "$setOnInsert": {"createdAt": now_utc()},
                },
                upsert=True,
            )
            migrated_store_products += 1

        # Mark legacy row with migration marker for traceability.
        db.products.update_one({"_id": row["_id"]}, {"$set": {"legacyMigrated": True, "legacyProductId": pid}})

    # Compute cheapest fields and sale labels from store_products.
    for product in db.products.find({"productId": {"$exists": True}}, {"productId": 1, "createdAt": 1, "labels": 1}):
        pid = product.get("productId")
        offers = list(db.store_products.find({"productId": pid, "isAvailable": True}))
        cheapest = None
        on_sale = False
        for offer in offers:
            price = offer.get("promoPrice") if offer.get("promoPrice") is not None else offer.get("basePrice")
            if offer.get("promoPrice") is not None:
                on_sale = True
            if price is not None and (cheapest is None or float(price) < float(cheapest.get("price"))):
                cheapest = {"price": float(price), "storeProductId": offer.get("storeProductId")}

        labels = set(product.get("labels") or [])
        if on_sale:
            labels.add("on_sale")
        else:
            labels.discard("on_sale")

        created_at = normalize_dt(product.get("createdAt"))
        if created_at and created_at >= (now_utc() - __import__("datetime").timedelta(days=30)):
            labels.add("new")

        db.products.update_one(
            {"productId": pid},
            {
                "$set": {
                    "cheapestPrice": cheapest.get("price") if cheapest else None,
                    "cheapestStoreProductId": cheapest.get("storeProductId") if cheapest else None,
                    "labels": sorted(labels),
                    "updatedAt": now_utc(),
                }
            },
        )

    db.schema_migrations.update_one(
        {"key": "legacy_to_catalog_v1"},
        {
            "$set": {
                "key": "legacy_to_catalog_v1",
                "appliedAt": now_utc(),
                "migratedProducts": migrated_products,
                "migratedStoreProducts": migrated_store_products,
            }
        },
        upsert=True,
    )

    return migrated_products, migrated_store_products


def main():
    db = get_db()
    p, sp = migrate(db)
    print("Legacy migration completed")
    print(f"Products migrated/upserted: {p}")
    print(f"StoreProducts migrated/upserted: {sp}")


if __name__ == "__main__":
    main()
