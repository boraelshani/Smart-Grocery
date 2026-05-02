#!/usr/bin/env python3
"""
Step 3 – Price Freshness Check & URL Discovery
══════════════════════════════════════════════

Checks which products have stale prices (older than N days) and
discovers missing product URLs for stores that only have homepage links.

URL Discovery:
  - BILLA: Scrape product URLs from shop.billa.at using product names
  - SPAR: Already has product-specific URLs (from heissepreise)
  - HOFER: Scrape product URLs from roksh.at/hofer using product names

Price Freshness:
  - Check price_history timestamps against cutoff date
  - Flag stale prices on store_products
  - Mark products as unavailable if missing from consecutive imports

Usage:
  python scripts/pipeline/price_freshness.py --dry-run
  python scripts/pipeline/price_freshness.py --check-urls  # discover URLs
"""

import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote

_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv
load_dotenv(_project_root / ".env", override=True)

# ───────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ───────────────────────────────────────────────────────────────────────

MAX_STALE_DAYS = 3
MAX_MISSING_RUNS = 2

# URL discovery endpoints
BILLA_SEARCH_URL = "https://shop.billa.at/search?q={query}"
HOFER_SEARCH_URL = "https://www.roksh.at/hofer/produkte/{query}"


def get_db():
    import certifi
    from pymongo import MongoClient
    client = MongoClient(
        os.environ["MONGO_URI"],
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=30000,
    )
    return client[os.environ.get("DATABASE_NAME", "smart_grocery")]


# ───────────────────────────────────────────────────────────────────────
# STALENESS DETECTION (using aggregation pipeline for speed)
# ───────────────────────────────────────────────────────────────────────

def find_stale_prices(db=None, max_stale_days=MAX_STALE_DAYS, dry_run=False):
    """
    Find all store_products whose latest price is older than max_stale_days.
    Uses aggregation pipeline for speed (avoids N+1 queries).
    """
    if db is None:
        db = get_db()

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_stale_days)

    # Step 1: Get latest price_history timestamp per storeProductId
    print("  Computing latest price history timestamps...")
    pipeline = [
        {"$group": {
            "_id": "$storeProductId",
            "latestTimestamp": {"$max": "$timestamp"},
        }},
    ]
    latest_map = {}
    for row in db.price_history.aggregate(pipeline):
        ts = row["latestTimestamp"]
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except:
                ts = None
        if ts and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        latest_map[row["_id"]] = ts

    print(f"  Found {len(latest_map):,} store products with price history")

    # Step 2: Load all store_products
    print("  Loading store products...")
    store_products = list(db.store_products.find({}, {
        "storeProductId": 1, "storeId": 1, "productId": 1,
        "basePrice": 1, "promoPrice": 1, "isAvailable": 1,
        "lastPriceUpdate": 1,
    }))
    print(f"  Loaded {len(store_products):,} store products")

    stale_by_store = {}
    fresh_count = 0
    stale_count = 0
    no_history_count = 0
    stale_samples = []

    for sp in store_products:
        sp_id = sp.get("storeProductId")
        store_id = sp.get("storeId", "unknown")
        hist_ts = latest_map.get(sp_id)

        if not hist_ts:
            no_history_count += 1
            last_update = sp.get("lastPriceUpdate")
            if last_update:
                if isinstance(last_update, str):
                    try:
                        last_update = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
                    except:
                        last_update = None
                if isinstance(last_update, datetime):
                    if last_update.tzinfo is None:
                        last_update = last_update.replace(tzinfo=timezone.utc)
                    if last_update > cutoff:
                        fresh_count += 1
                        continue

            stale_count += 1
            stale_by_store[store_id] = stale_by_store.get(store_id, 0) + 1
            if len(stale_samples) < 20:
                stale_samples.append({
                    "storeProductId": sp_id[:50],
                    "storeId": store_id,
                    "lastPriceUpdate": str(last_update) if last_update else "never",
                })
            continue

        if hist_ts < cutoff:
            stale_count += 1
            stale_by_store[store_id] = stale_by_store.get(store_id, 0) + 1
            if len(stale_samples) < 20:
                stale_samples.append({
                    "storeProductId": sp_id[:50],
                    "storeId": store_id,
                    "lastSeen": str(hist_ts),
                })
        else:
            fresh_count += 1

    result = {
        "total_store_products": len(store_products),
        "fresh_count": fresh_count,
        "stale_count": stale_count,
        "no_history": no_history_count,
        "stale_by_store": stale_by_store,
        "cutoff_date": cutoff.isoformat(),
        "max_stale_days": max_stale_days,
    }

    if dry_run:
        result["stale_samples"] = stale_samples

    return result


def mark_stale_prices(db=None, max_stale_days=MAX_STALE_DAYS, dry_run=False):
    """Mark stale prices on store_products."""
    if dry_run:
        return find_stale_prices(db=db, max_stale_days=max_stale_days, dry_run=True)

    if db is None:
        db = get_db()

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_stale_days)

    # Get latest price history per storeProductId
    print("  Computing latest price history timestamps...")
    pipeline = [
        {"$group": {
            "_id": "$storeProductId",
            "latestTimestamp": {"$max": "$timestamp"},
        }},
    ]
    stale_sp_ids = set()
    for row in db.price_history.aggregate(pipeline):
        ts = row["latestTimestamp"]
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except:
                ts = None
        if ts and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts and ts < cutoff:
            stale_sp_ids.add(row["_id"])

    print(f"  Found {len(stale_sp_ids):,} stale store products")

    # Update in chunks using $in (faster than individual UpdateOne ops)
    now = datetime.now(timezone.utc).isoformat()
    ids_list = list(stale_sp_ids)
    flagged = 0
    chunk_size = 2000
    for i in range(0, len(ids_list), chunk_size):
        chunk = ids_list[i:i + chunk_size]
        result = db.store_products.update_many(
            {"storeProductId": {"$in": chunk}},
            {"$set": {"priceStale": True, "priceStaleSince": now, "updatedAt": now}}
        )
        flagged += result.modified_count
        print(f"  Chunk {i // chunk_size + 1}: modified {result.modified_count}")

    print(f"Total flagged stale: {flagged:,}")
    return {"flagged_stale": flagged, "total_store_products": len(ids_list)}


# ───────────────────────────────────────────────────────────────────────
# URL DISCOVERY
# ───────────────────────────────────────────────────────────────────────

def discover_billa_urls(db=None, dry_run=False, limit=0):
    """
    Discover BILLA product URLs by searching shop.billa.at.
    The pattern is: https://shop.billa.at/produkte/{product-name-slug}-{id}
    """
    if db is None:
        db = get_db()

    # Find store_products for BILLA without a real URL
    store_id = "store_billa"
    query = {
        "storeId": store_id,
        "$or": [
            {"productPageUrl": {"$in": [None, "", "https://shop.billa.at"]}},
            {"productPageUrl": {"$exists": False}},
        ]
    }

    cursor = db.store_products.find(query).limit(limit) if limit > 0 else db.store_products.find(query)
    sp_list = list(cursor)
    print(f"Found {len(sp_list):,} BILLA store products needing URLs")

    if dry_run:
        # Just show sample - don't actually scrape
        print("\n  DRY RUN: Would search shop.billa.at for these products:")
        for sp in sp_list[:10]:
            product = db.products.find_one({"productId": sp.get("productId")}, {"name_de": 1})
            name = product.get("name_de", "Unknown") if product else "Unknown"
            print(f"    '{name}' → {BILLA_SEARCH_URL.format(query=quote(name[:50]))}")
        return {"would_process": len(sp_list)}

    import requests
    updated = 0

    for sp in sp_list:
        product = db.products.find_one({"productId": sp.get("productId")}, {"name_de": 1, "name_en": 1})
        if not product:
            continue

        name = product.get("name_de") or product.get("name_en", "")
        if not name:
            continue

        # Try to construct URL from product name
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower().strip()).strip('-')
        # BILLA URLs pattern: /produkte/{slug}-{7-digit-id}
        # We can't know the ID without scraping, so use search URL as fallback
        search_url = f"https://shop.billa.at/search?q={quote(name[:80])}"

        # Try to find the actual product page via search
        try:
            resp = requests.get(search_url, timeout=5, headers={
                "User-Agent": "Mozilla/5.0 (compatible; SmartGrocery/1.0)"
            })
            # Check if response redirects to a product page or contains product links
            if resp.status_code == 200:
                # Look for product links in response
                product_links = re.findall(r'/produkte/([a-z0-9-]+\d+)', resp.text)
                if product_links:
                    # Take the first product link that matches our name
                    for link in product_links:
                        link_slug = re.sub(r'-\d+$', '', link)
                        if link_slug in slug[:20]:
                            db.store_products.update_one(
                                {"storeProductId": sp["storeProductId"]},
                                {"$set": {
                                    "productPageUrl": f"https://shop.billa.at/produkte/{link}",
                                    "updatedAt": datetime.now(timezone.utc),
                                }}
                            )
                            updated += 1
                            break

                    if updated > 0 and updated % 50 == 0:
                        print(f"  Updated: {updated}")
        except Exception:
            pass

        # Fallback: use search URL
        if not sp.get("productPageUrl") or sp.get("productPageUrl") in [None, ""]:
            db.store_products.update_one(
                {"storeProductId": sp["storeProductId"]},
                {"$set": {
                    "productPageUrl": search_url,
                    "updatedAt": datetime.now(timezone.utc),
                }}
            )

        time.sleep(0.5)  # Rate limit

    print(f"Updated BILLA URLs: {updated}")
    return {"updated_billa_urls": updated}


def discover_hofer_urls(db=None, dry_run=False, limit=0):
    """
    Discover HOFER product URLs from roksh.at.
    Pattern: https://www.roksh.at/hofer/produkte/{slug}
    """
    if db is None:
        db = get_db()

    store_id = "store_hofer"
    query = {
        "storeId": store_id,
        "$or": [
            {"productPageUrl": {"$in": [None, "", "https://www.hofer.at"]}},
            {"productPageUrl": {"$exists": False}},
        ]
    }

    cursor = db.store_products.find(query).limit(limit) if limit > 0 else db.store_products.find(query)
    sp_list = list(cursor)
    print(f"Found {len(sp_list):,} HOFER store products needing URLs")

    if dry_run:
        print("\n  DRY RUN: Would construct URLs like:")
        for sp in sp_list[:10]:
            product = db.products.find_one({"productId": sp.get("productId")}, {"name_de": 1})
            name = product.get("name_de", "Unknown") if product else "Unknown"
            slug = re.sub(r'[^a-z0-9]+', '-', name.lower().strip()).strip('-')[:60]
            print(f"    '{name}' → https://www.roksh.at/hofer/produkte/{slug}")
        return {"would_process": len(sp_list)}

    updated = 0

    for sp in sp_list:
        product = db.products.find_one({"productId": sp.get("productId")}, {"name_de": 1, "name_en": 1})
        if not product:
            continue

        name = product.get("name_de") or product.get("name_en", "")
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower().strip()).strip('-')[:60]
        url = f"https://www.roksh.at/hofer/produkte/{slug}"

        db.store_products.update_one(
            {"storeProductId": sp["storeProductId"]},
            {"$set": {
                "productPageUrl": url,
                "updatedAt": datetime.now(timezone.utc),
            }}
        )
        updated += 1

    print(f"Updated HOFER URLs: {updated}")
    return {"updated_hofer_urls": updated}


def discover_urls(db=None, dry_run=False, limit=0):
    """Discover URLs for all stores that need them."""
    if db is None:
        db = get_db()

    billa_result = discover_billa_urls(db, dry_run=dry_run, limit=limit)
    hofer_result = discover_hofer_urls(db, dry_run=dry_run, limit=limit)

    return {"billa": billa_result, "hofer": hofer_result}


# ───────────────────────────────────────────────────────────────────────
# MARK UNAVAILABLE (missing from consecutive imports)
# ───────────────────────────────────────────────────────────────────────

def mark_unavailable_missing(db=None, current_sp_ids: set = None, max_missing_runs=MAX_MISSING_RUNS):
    """Mark store_products as unavailable if missing from import."""
    if db is None:
        db = get_db()
    if current_sp_ids is None:
        print("ERROR: current_sp_ids required. Get from import script.")
        return

    now = datetime.now(timezone.utc).isoformat()
    marked = 0

    for store_id in ["store_billa", "store_spar", "store_hofer"]:
        cursor = db.store_products.find(
            {"storeId": store_id, "isAvailable": True, "storeProductId": {"$nin": list(current_sp_ids)}},
            {"storeProductId": 1, "missingCount": 1}
        )

        for sp in cursor:
            missing_count = sp.get("missingCount", 0) + 1
            if missing_count >= max_missing_runs:
                db.store_products.update_one(
                    {"storeProductId": sp["storeProductId"]},
                    {"$set": {
                        "isAvailable": False,
                        "stockStatus": "unavailable",
                        "unavailableSince": now,
                        "updatedAt": now,
                    }}
                )
                marked += 1
            else:
                db.store_products.update_one(
                    {"storeProductId": sp["storeProductId"]},
                    {"$set": {"missingCount": missing_count, "updatedAt": now}}
                )

    print(f"Marked unavailable: {marked:,}")
    return {"marked_unavailable": marked}


# ───────────────────────────────────────────────────────────────────────
# CLI
# ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Price freshness & URL discovery")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-stale-days", type=int, default=MAX_STALE_DAYS)
    parser.add_argument("--check-urls", action="store_true", help="Discover missing URLs")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    if args.check_urls:
        result = discover_urls(dry_run=args.dry_run, limit=args.limit)
    else:
        if args.dry_run:
            result = find_stale_prices(max_stale_days=args.max_stale_days, dry_run=True)
        else:
            result = mark_stale_prices(max_stale_days=args.max_stale_days)

    print(json.dumps(result, indent=2, default=str))
