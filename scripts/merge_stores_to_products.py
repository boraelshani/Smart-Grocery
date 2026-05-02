#!/usr/bin/env python3
"""
Merge store_products data into products collection.

The main import script populates store_products and price_history collections.
This script reads store_products and merges the store entries into the products
collection's 'stores' array.

Run after import_heissepreise.py completes.
"""

import os
import time
from datetime import datetime, timezone
from pathlib import Path

import certifi
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

BATCH_SIZE = 500

def main():
    mongo_uri = os.environ.get("MONGO_URI")
    db_name = os.environ.get("DATABASE_NAME", "smart_grocery")
    client = MongoClient(mongo_uri, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=30000)
    db = client[db_name]

    print("Merging store_products → products collection...")
    t0 = time.time()

    # Read all store_products and group by productId
    print("Reading store_products...")
    store_map = {}  # productId -> [store_entries]
    count = 0
    for sp in db.store_products.find({"isAvailable": True}):
        pid = sp["productId"]
        entry = {
            "store": sp["storeId"].replace("store_", "").upper(),
            "price": sp["basePrice"],
            "url": sp.get("productPageUrl", ""),
            "is_available": True,
            "is_on_offer": sp.get("isOnOffer", False),
            "offer_previous_price": sp.get("basePrice") if sp.get("isOnOffer") else None,
            "unit_price_comparison": sp.get("unitPriceComparison", {}),
        }
        if pid not in store_map:
            store_map[pid] = []
        store_map[pid].append(entry)
        count += 1

    print(f"  {count:,} available store products grouped into {len(store_map):,} products")

    # Update products in batches
    update_ops = []
    for pid, stores in store_map.items():
        # Compute cheapest
        cheapest = min(stores, key=lambda s: s["price"])
        cheapest_price = cheapest["price"]
        cheapest_stores = sorted(set(s["store"] for s in stores if s["price"] == cheapest_price))

        update_ops.append(UpdateOne(
            {"productId": pid},
            {"$set": {
                "stores": stores,
                "cheapestPrice": cheapest_price,
                "cheapest": {"price": cheapest_price, "store": ", ".join(cheapest_stores)},
                "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            }},
        ))

    print(f"\nUpdating {len(update_ops):,} products...")
    for i in range(0, len(update_ops), BATCH_SIZE):
        db.products.bulk_write(update_ops[i:i + BATCH_SIZE], ordered=False)
        done = min(i + BATCH_SIZE, len(update_ops))
        print(f"  Updated: {done:,}/{len(update_ops):,}")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s")

    # Verification
    print("\nVerification:")
    total = db.products.count_documents({})
    with_stores = db.products.count_documents({"stores": {"$exists": True, "$ne": []}})
    print(f"  Total products: {total:,}")
    print(f"  Products with stores: {with_stores:,}")

    for store_name in ["BILLA", "SPAR", "HOFER"]:
        c = db.products.count_documents({"stores.store": store_name})
        print(f"  Products with {store_name}: {c:,}")

    # Sample
    sample = db.products.find_one({"stores": {"$size": 3}})
    if sample:
        print(f"\n  Sample (3 stores): {sample['name'][:60]}")
        for s in sample["stores"]:
            tag = " [OFFER]" if s.get("is_on_offer") else ""
            print(f"    {s['store']}: €{s['price']:.2f}{tag}")

    client.close()

if __name__ == "__main__":
    main()
