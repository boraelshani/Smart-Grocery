#!/usr/bin/env python3
"""
Remove all BILLA store entries so we can re-run the improved linker cleanly.
Only removes BILLA entries — SPAR and other stores are preserved.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from utils.db import mongo

DRY_RUN = "--dry" in sys.argv

with app.app_context():
    result = mongo.db.products.find({"stores.store": "BILLA"})
    products = list(result)
    print(f"Products with BILLA entries: {len(products)}")

    if DRY_RUN:
        print("DRY RUN — no changes made.")
        sys.exit(0)

    removed = 0
    for p in products:
        r = mongo.db.products.update_one(
            {"_id": p["_id"]},
            {"$pull": {"stores": {"store": "BILLA"}}}
        )
        if r.modified_count:
            removed += 1

    print(f"Removed BILLA entries from {removed} products.")

    # Verify
    remaining = mongo.db.products.count_documents({"stores.store": "BILLA"})
    print(f"Remaining BILLA entries: {remaining}")
