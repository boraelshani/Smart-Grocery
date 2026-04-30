#!/usr/bin/env python3
"""
Sync script to download latest prices from heisse-preise.io
and upsert them to the local MongoDB using the New Catalog Schema.
"""

import os
import re
from datetime import datetime, timezone
import requests
from pymongo import MongoClient

def now_utc():
    return datetime.now(timezone.utc)

def slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "unknown"

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

def ensure_store_id(db, store_name):
    if not store_name:
        return None
    
    slug = slugify(store_name)
    sid = f"store_{slug}"
    
    db.stores.update_one(
        {"storeId": sid},
        {
            "$setOnInsert": {
                "storeId": sid,
                "name": store_name.capitalize(),
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
        category_name = "HeissePrices"

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

def sync_data():
    uri = os.environ.get("MONGO_URI") or "mongodb://localhost:27017/"
    client = MongoClient(uri)
    db = client.get_database("smart_grocery")
    
    print("Fetching data from heisse-preise...")
    r = requests.get('https://heisse-preise.io/data/latest-canonical.json', timeout=30)
    data = r.json()
    
    allowed_stores = {"hofer", "spar", "billa"}
    target_data = [d for d in data if d.get('store', '').lower() in allowed_stores]
    print(f"Found {len(target_data)} items from {allowed_stores}.")
    
    # Group items by product name
    products_map = {}
    for item in target_data:
        name = item.get("name", "").strip()
        store_name = item.get("store", "").lower()
        price = item.get("price", 0.0)
        
        url = item.get("url", "")
        if not url and item.get("id"):
            if store_name == "spar":
                url = f"https://www.interspar.at/shop/lebensmittel/{item['id']}/p/{item['id']}"
            elif store_name == "billa":
                url = f"https://shop.billa.at/produkte/{item['id']}"
            elif store_name == "hofer":
                url = f"https://www.roksh.at/hofer/produkte/{item['id']}"
        
        if not name:
            continue
            
        if name not in products_map:
            products_map[name] = []
            
        products_map[name].append({
            "store": store_name,
            "price": price,
            "url": url,
            "unit": item.get('unit'),
            "quantity": item.get('quantity'),
            "description": item.get("description", ""),
        })
        
    print(f"Grouped into {len(products_map)} unique products. Preparing for catalog upsert...")

    category_id = ensure_category(db, "HeissePrices")

    migrated_products = 0
    migrated_store_products = 0
    
    for name, stores in products_map.items():
        base_slug = slugify(name)
        # Unique and deterministic Product ID based on name slug
        pid = f"prod_{base_slug}_hp"
        
        unit = stores[0].get("unit", "")
        qty = stores[0].get("quantity", "")
        desc = stores[0].get("description", "")
        unit_size = f"{qty} {unit}".strip() if qty and unit else ""

        # Upsert the main product in `products`
        db.products.update_one(
            {"productId": pid},
            {
                "$set": {
                    "productId": pid,
                    "name_en": name,
                    "name_de": name,
                    "brandId": "brand_generic", # defaults to Generic
                    "categoryId": category_id,
                    "categoryPath": [category_id],
                    "unitSize": unit_size,
                    "defaultImageUrl": "",
                    "legalImageStatus": "placeholder",
                    "labels": ["heisse_preise"],
                    "description_en": desc,
                    "description_de": desc,
                    "updatedAt": now_utc(),
                },
                "$setOnInsert": {
                    "createdAt": now_utc()
                },
            },
            upsert=True,
        )
        migrated_products += 1

        cheapest_price_val = None
        cheapest_spid = None

        # Build `store_products` representing nested mapping configurations relations
        for s in stores:
            store_name = s["store"]
            store_id = ensure_store_id(db, store_name)
            
            if not store_id:
                continue

            spid = f"sp_{pid}_{store_id}"
            price = parse_price(s.get("price")) or 0.0

            db.store_products.update_one(
                {"storeProductId": spid},
                {
                    "$set": {
                        "storeProductId": spid,
                        "productId": pid,
                        "storeId": store_id,
                        "productPageUrl": s.get("url", ""),
                        "extractedImageUrl": "",
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
                    "$setOnInsert": {
                        "createdAt": now_utc()
                    },
                },
                upsert=True,
            )
            migrated_store_products += 1

            if cheapest_price_val is None or price < cheapest_price_val:
                cheapest_price_val = price
                cheapest_spid = spid

        # Update the parent product with the derived cheapest metadata 
        if cheapest_price_val is not None:
            db.products.update_one(
                {"productId": pid},
                {
                    "$set": {
                        "cheapestPrice": float(cheapest_price_val),
                        "cheapestStoreProductId": cheapest_spid,
                        "updatedAt": now_utc(),
                    }
                }
            )

    print("Success!")
    print(f"Products upserted: {migrated_products}")
    print(f"Store-Products upserted: {migrated_store_products}")

if __name__ == "__main__":
    sync_data()
