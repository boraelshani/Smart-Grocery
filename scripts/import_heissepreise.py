#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════
Smart Grocery – Heisse Preise Initial Data Import
═══════════════════════════════════════════════════════════════════════════

Downloads the latest product data from heisse-preise.io and imports it
into the Smart Grocery MongoDB database for BILLA, SPAR, and HOFER.

Usage:
    python scripts/import_heissepreise.py

Environment Variables:
    MONGO_URI       – MongoDB Atlas connection string
    DATABASE_NAME   – Database name (default: smart_grocery)

Design Decisions:
─────────────────
1. PRODUCT URL HANDLING (Option A – constructed from heissepreise data):
   • BILLA:  https://shop.billa.at/p/{slug}
   • SPAR:   No URL from heissepreise → search URL fallback
   • HOFER:  https://www.roksh.at/hofer/produkte/{slug}

2. DISCOUNT DETECTION:
   Compare current price vs. previous price in priceHistory.
   If drop > 5%, mark as potential offer.

3. PRODUCT FINGERPRINTING:
   Deterministic hash of: normalized_name + quantity + unit.

4. DATABASE SCHEMA:
   Writes to: products, store_products, price_history collections.
   IDEMPOTENT – safe to run multiple times.

═══════════════════════════════════════════════════════════════════════════
"""

import hashlib
import json
import os
import re
import sys
import time
import string
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import certifi
import requests
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne, ReplaceOne

# Load .env from project root
_project_root = Path(__file__).parent.parent
_env_path = _project_root / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=True)

# ───────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ───────────────────────────────────────────────────────────────────────────

HEISSE_PREISE_URL = "https://heisse-preise.io/data/latest-canonical.json"
TARGET_STORES = {"billa", "spar", "hofer"}
STORE_DISPLAY_NAMES = {"billa": "BILLA", "spar": "SPAR", "hofer": "HOFER"}
STORE_DB_IDS = {"billa": "store_billa", "spar": "store_spar", "hofer": "store_hofer"}
OFFER_DROP_THRESHOLD = 0.05
BATCH_SIZE = 2000
SPAR_SEARCH_URL = "https://www.interspar.at/shop/lebensmittel/search?q={query}"
MAX_PRICE_HISTORY = 10  # Limit stored history entries per product to avoid bloat

# ── Pre-compiled for performance ──
_RE_MULTI_SPACE = re.compile(r"\s+")
_RE_NON_ALNUM = re.compile(r"[^a-z0-9\s]")

# Translation table to remove non-alphanumeric chars (fast alternative to regex)
_KEEP_CHARS = set(string.ascii_lowercase + string.digits + " ")
def _fast_normalize(name):
    """Fast name normalization without regex – critical for 58K items."""
    if not name:
        return ""
    name = name.lower().strip()
    # Filter to only keep lowercase letters, digits, spaces
    name = "".join(c for c in name if c in _KEEP_CHARS)
    # Collapse multiple spaces
    name = _RE_MULTI_SPACE.sub(" ", name)
    return name.strip()


# ───────────────────────────────────────────────────────────────────────────
# DATABASE CONNECTION
# ───────────────────────────────────────────────────────────────────────────

def get_mongo_client():
    mongo_uri = os.environ.get("MONGO_URI")
    if not mongo_uri:
        print("ERROR: MONGO_URI not set. Please configure .env file.")
        sys.exit(1)
    database_name = os.environ.get("DATABASE_NAME", "smart_grocery")
    print(f"Connecting to MongoDB: {mongo_uri[:30]}...")
    try:
        client = MongoClient(
            mongo_uri,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=30000,
            socketTimeoutMS=300000,
            connectTimeoutMS=30000,
        )
        client.admin.command("ping")
        db = client[database_name]
        print("MongoDB connected successfully.")
        return db
    except Exception as e:
        print(f"ERROR: MongoDB connection failed: {e}")
        sys.exit(1)


# ───────────────────────────────────────────────────────────────────────────
# DATA DOWNLOAD
# ───────────────────────────────────────────────────────────────────────────

def download_data():
    print("\n" + "=" * 60)
    print("STEP 1: Downloading data from heisse-preise.io")
    print("=" * 60)
    try:
        resp = requests.get(HEISSE_PREISE_URL, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        print(f"Downloaded {len(data):,} total items")
        return data
    except Exception as e:
        print(f"ERROR: Download failed: {e}")
        sys.exit(1)


# ───────────────────────────────────────────────────────────────────────────
# FILTERING
# ───────────────────────────────────────────────────────────────────────────

def filter_stores(data):
    print("\n" + "=" * 60)
    print("STEP 2: Filtering for BILLA, SPAR, HOFER")
    print("=" * 60)
    filtered = {s: [] for s in TARGET_STORES}
    for item in data:
        s = item.get("store", "")
        if s in filtered:
            filtered[s].append(item)
    for s, items in filtered.items():
        print(f"  {STORE_DISPLAY_NAMES[s]}: {len(items):,} items")
    return filtered


# ───────────────────────────────────────────────────────────────────────────
# TRANSFORMATION & IMPORT (optimized for bulk processing)
# ───────────────────────────────────────────────────────────────────────────

def transform_and_import(db, filtered_data):
    print("\n" + "=" * 60)
    print("STEP 3: Transforming and importing to MongoDB")
    print("=" * 60)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    # Aggregation structures
    products_agg = {}       # product_id -> {product fields, store_entries}
    store_products_list = []
    price_history_list = []

    total = 0
    offers = 0
    unavailable_count = 0

    for store_key in sorted(TARGET_STORES):
        _proc_start = time.time()
        items = filtered_data[store_key]
        display = STORE_DISPLAY_NAMES[store_key]
        store_name = display
        store_db_id = STORE_DB_IDS[store_key]
        print(f"\n  Processing {display}: {len(items):,} items")

        for idx, item in enumerate(items):
            # Progress output every 5000 items
            if (idx + 1) % 5000 == 0:
                elapsed = time.time() - _proc_start
                rate = (idx + 1) / elapsed if elapsed > 0 else 0
                print(f"    {idx + 1:,}/{len(items):,} ({rate:.0f} items/s)")

            total += 1
            name = (item.get("name") or "").strip()
            price = item.get("price", 0)
            if not name or not price:
                continue

            quantity = item.get("quantity", 0)
            unit = (item.get("unit") or "stk").lower().strip()
            price_history = item.get("priceHistory", [])
            is_unavailable = item.get("unavailable", False)
            is_bio = item.get("bio", False)

            # URL construction
            url_slug = item.get("url", "").strip()
            if store_key == "billa" and url_slug:
                product_url = f"https://shop.billa.at/p/{url_slug}"
            elif store_key == "hofer" and url_slug:
                product_url = f"https://www.roksh.at/hofer/produkte/{url_slug}"
            elif store_key == "spar" and name:
                product_url = SPAR_SEARCH_URL.format(query=urllib.parse.quote(name.strip()[:80]))
            else:
                product_url = ""

            # Discount detection
            is_on_offer = False
            prev_price = None
            drop_pct = 0.0
            if len(price_history) >= 2:
                curr = price_history[0].get("price", 0)
                prev = price_history[1].get("price", 0)
                if prev > 0:
                    drop = (prev - curr) / prev
                    if drop > OFFER_DROP_THRESHOLD:
                        is_on_offer = True
                        prev_price = prev
                        drop_pct = round(drop * 100, 1)
                        offers += 1

            if is_unavailable:
                unavailable_count += 1

            # Unit price
            unit_price_val = None
            unit_price_lbl = None
            if quantity and quantity > 0:
                u = unit
                if u in ("g", "gramm"):
                    unit_price_val = round((price / quantity) * 1000, 4)
                    unit_price_lbl = "per kg"
                elif u in ("ml", "milliliter"):
                    unit_price_val = round((price / quantity) * 1000, 4)
                    unit_price_lbl = "per L"
                elif u in ("kg", "l", "liter", "kilogramm"):
                    unit_price_val = round(price, 4)
                    unit_price_lbl = f"per {u}"
                else:
                    unit_price_val = round(price, 4)
                    unit_price_lbl = f"per {u}"

            # Fingerprint (fast)
            normalized = _fast_normalize(name)
            fp_str = f"{normalized}|{quantity}|{unit}"
            fp_hash = hashlib.sha256(fp_str.encode("utf-8")).hexdigest()[:12]

            # IDs
            slug = _RE_MULTI_SPACE.sub("-", normalized)[:60]
            product_id = f"prod_{slug}_{fp_hash}"
            store_product_id = f"sp_{product_id}_store_{store_key}"

            unit_size = f"{quantity} {unit}".strip()

            # Store entry for embedded array
            store_entry = {
                "store": store_name,
                "price": price,
                "url": product_url,
                "is_available": not is_unavailable,
                "is_on_offer": is_on_offer,
                "offer_previous_price": prev_price,
                "offer_drop_percent": drop_pct if is_on_offer else None,
                "last_seen": now,
                "heissepreise_id": str(item.get("id", "")),
                "unit_price_comparison": {"value": unit_price_val, "unit": unit_price_lbl},
            }

            # Aggregate product
            if product_id not in products_agg:
                products_agg[product_id] = {
                    "productId": product_id,
                    "fingerprint": fp_hash,
                    "name": name,
                    "name_de": name,
                    "name_en": name,
                    "description": (item.get("description") or "").strip(),
                    "description_de": (item.get("description") or "").strip(),
                    "description_en": (item.get("description") or "").strip(),
                    "unit": unit_size,
                    "unitSize": unit_size,
                    "quantity": quantity,
                    "unit_raw": unit,
                    "barcode": None,
                    "brandId": "brand_generic",
                    "categoryId": "cat_uncategorized",
                    "categoryPath": ["cat_uncategorized"],
                    "labels": ["bio"] if is_bio else [],
                    "defaultImageUrl": None,
                    "stores": [],
                    "updatedAt": now,
                }
            products_agg[product_id]["stores"].append(store_entry)

            # Store product entry (store as raw dict for efficient processing)
            store_products_list.append({
                "storeProductId": store_product_id,
                "productId": product_id,
                "storeId": store_db_id,
                "basePrice": price,
                "promoPrice": price if is_on_offer else None,
                "isAvailable": not is_unavailable,
                "isOnOffer": is_on_offer,
                "productPageUrl": product_url,
                "unitPriceComparison": {"value": unit_price_val, "unit": unit_price_lbl},
                "multiBuy": {"type": "none", "details": {}},
                "stockStatus": "unknown",
                "offerStart": None,
                "offerEnd": None,
                "lastPriceUpdate": now,
                "lastScrapeStatus": "ok",
                "extractedImageUrl": None,
                "updatedAt": now,
                "heissepreise_id": str(item.get("id", "")),
                "heissepreise_bio": is_bio,
                "heissepreise_weighted": item.get("isWeighted", False),
            })

            # Price history: LIMIT to most recent entries to avoid bloat
            limited_hist = price_history[:MAX_PRICE_HISTORY]
            for entry in limited_hist:
                hist_date = entry.get("date", "")
                hist_price = entry.get("price", 0)
                hist_id_str = f"{store_product_id}_{hist_date}_{hist_price}"
                price_history_list.append({
                    "historyId": hashlib.sha256(hist_id_str.encode()).hexdigest()[:12],
                    "storeProductId": store_product_id,
                    "productId": product_id,
                    "storeId": store_db_id,
                    "timestamp": hist_date,
                    "oldPrice": None,
                    "newPrice": hist_price,
                    "promoPrice": None,
                    "source": "heissepreise",
                })

        print(f"    {len(items):,}/{len(items):,} complete.")

    print(f"\n  Total items processed: {total:,}")
    print(f"  Unique products: {len(products_agg):,}")
    print(f"  Store product entries: {len(store_products_list):,}")
    print(f"  Price history entries: {len(price_history_list):,}")
    print(f"  Offers detected: {offers:,}")

    # ── Phase 2: Products – insert NEW, skip updating existing ──
    # Existing products already have store data from previous runs.
    # We only insert products that don't exist yet to save time.
    # The store_products collection holds the authoritative store data.
    print(f"\nPhase 2: Processing {len(products_agg):,} products...")

    existing_ids = set()
    for doc in db.products.find({}, {"productId": 1, "_id": 0}):
        existing_ids.add(doc["productId"])

    new_docs = []
    skip_count = 0
    for pid, doc in products_agg.items():
        store_entries = doc.pop("stores")
        avail = [s for s in store_entries if s.get("is_available", True)]
        if avail:
            cheapest_price = min(s["price"] for s in avail)
            cheapest_stores = sorted(set(s["store"] for s in avail if s["price"] == cheapest_price))
            cheapest_info = {"price": cheapest_price, "store": ", ".join(cheapest_stores)}
        else:
            cheapest_price = None
            cheapest_info = {"price": None, "store": ""}

        if pid in existing_ids:
            skip_count += 1
            continue  # Skip updating existing – already have data
        else:
            doc["stores"] = store_entries
            doc["cheapestPrice"] = cheapest_price
            doc["cheapest"] = cheapest_info
            doc["createdAt"] = now
            new_docs.append(doc)

    print(f"  Existing (skipped): {skip_count:,}")
    print(f"  New to insert: {len(new_docs):,}")

    if new_docs:
        for i in range(0, len(new_docs), BATCH_SIZE * 2):
            batch = new_docs[i:i + BATCH_SIZE * 2]
            try:
                db.products.insert_many(batch, ordered=False)
            except Exception:
                pass
            done = min(i + BATCH_SIZE * 2, len(new_docs))
            print(f"  Inserted: {done:,}/{len(new_docs):,}")

    # ── Phase 3: Insert store_products ──
    print(f"\nPhase 3: Inserting {len(store_products_list):,} store products...")

    # Check existing
    existing_sp_ids = set()
    for doc in db.store_products.find({}, {"storeProductId": 1, "_id": 0}):
        existing_sp_ids.add(doc["storeProductId"])

    sp_new = []
    sp_update_ops = []
    for sp_doc in store_products_list:
        sp_id = sp_doc["storeProductId"]
        if sp_id in existing_sp_ids:
            sp_update_ops.append(UpdateOne(
                {"storeProductId": sp_id},
                {"$set": sp_doc},
            ))
        else:
            new_sp = dict(sp_doc)
            new_sp["createdAt"] = now
            sp_new.append(new_sp)

    print(f"  New: {len(sp_new):,}")
    print(f"  Existing to update: {len(sp_update_ops):,}")

    # Fast insert for new
    if sp_new:
        for i in range(0, len(sp_new), BATCH_SIZE * 2):
            try:
                db.store_products.insert_many(sp_new[i:i + BATCH_SIZE * 2], ordered=False)
            except Exception:
                pass
            done = min(i + BATCH_SIZE * 2, len(sp_new))
            print(f"  Inserted: {done:,}/{len(sp_new):,}")

    # Targeted updates for existing
    if sp_update_ops:
        for i in range(0, len(sp_update_ops), BATCH_SIZE * 5):
            db.store_products.bulk_write(sp_update_ops[i:i + BATCH_SIZE * 5], ordered=False)
            done = min(i + BATCH_SIZE * 5, len(sp_update_ops))
            print(f"  Updated: {done:,}/{len(sp_update_ops):,}")

    # ── Phase 4: Insert price history (with dedup) ──
    print(f"\nPhase 4: Inserting price history...")
    seen = set()
    unique_hist = []
    for doc in price_history_list:
        key = (doc["storeProductId"], doc["timestamp"])
        if key not in seen:
            seen.add(key)
            unique_hist.append(doc)

    print(f"  Unique entries: {len(unique_hist):,}")
    if unique_hist:
        try:
            db.price_history.insert_many(unique_hist, ordered=False)
        except Exception as e:
            print(f"  Note: Some duplicates skipped (expected): {type(e).__name__}")

    # ── Phase 5: Mark missing items as unavailable ──
    print("\nPhase 5: Marking unavailable store products...")
    current_sp_ids = set(sp_doc["storeProductId"] for sp_doc in store_products_list)

    marked = 0
    for store_key in TARGET_STORES:
        store_db_id = STORE_DB_IDS[store_key]
        cursor = db.store_products.find(
            {"storeId": store_db_id, "isAvailable": True},
            {"storeProductId": 1, "_id": 0}
        )
        to_update = [d["storeProductId"] for d in cursor if d["storeProductId"] not in current_sp_ids]
        if to_update:
            db.store_products.update_many(
                {"storeProductId": {"$in": to_update}},
                {"$set": {"isAvailable": False, "stockStatus": "unavailable", "updatedAt": now}}
            )
            marked += len(to_update)

    print(f"  Marked unavailable: {marked:,}")

    return {
        "total_items": total,
        "unique_products": len(products_agg),
        "store_products": len(store_products_list),
        "price_history": len(unique_hist),
        "offers": offers,
        "marked_unavailable": marked,
    }


# ───────────────────────────────────────────────────────────────────────────
# VERIFICATION
# ───────────────────────────────────────────────────────────────────────────

def verify(db, stats):
    print("\n" + "=" * 60)
    print("STEP 4: Verification")
    print("=" * 60)

    total_products = db.products.count_documents({})
    print(f"\n  Total products: {total_products:,}")

    for store_key in sorted(TARGET_STORES):
        store_name = STORE_DISPLAY_NAMES[store_key]
        store_db_id = STORE_DB_IDS[store_key]
        sp_count = db.store_products.count_documents({"storeId": store_db_id})
        sp_avail = db.store_products.count_documents({"storeId": store_db_id, "isAvailable": True})
        print(f"  {store_name} store_products: {sp_count:,} total, {sp_avail:,} available")

    print(f"  Price history: {db.price_history.count_documents({}):,}")

    # Sample product
    sample = db.products.find_one({"stores": {"$elemMatch": {"store": "BILLA"}}})
    if sample:
        print(f"\n  Sample product:")
        print(f"    Name: {sample.get('name', 'N/A')}")
        print(f"    ID: {sample.get('productId', 'N/A')}")
        print(f"    Stores: {len(sample.get('stores', []))}")
        for s in sample.get("stores", [])[:3]:
            offer_tag = " [OFFER]" if s.get("is_on_offer") else ""
            print(f"      - {s['store']}: €{s['price']:.2f}{offer_tag}")


# ───────────────────────────────────────────────────────────────────────────
# MAIN
# ───────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Smart Grocery – Heisse Preise Data Import")
    print("=" * 60)
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Stores: {', '.join(sorted(STORE_DISPLAY_NAMES[s] for s in TARGET_STORES))}")

    t0 = time.time()
    db = get_mongo_client()
    data = download_data()
    filtered = filter_stores(data)
    del data  # free memory
    stats = transform_and_import(db, filtered)
    verify(db, stats)

    elapsed = time.time() - t0
    print("\n" + "=" * 60)
    print("IMPORT COMPLETE")
    print("=" * 60)
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Items: {stats['total_items']:,}")
    print(f"  Products: {stats['unique_products']:,}")
    print(f"  Store products: {stats['store_products']:,}")
    print(f"  Price history: {stats['price_history']:,}")
    print(f"  Offers: {stats['offers']:,}")
    print("\nDone!")


if __name__ == "__main__":
    main()
