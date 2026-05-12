#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════
FINAL HeissePreise Import - Complete & Robust
═══════════════════════════════════════════════════════════════════════════

This script will:
1. Clear existing products and offers
2. Download HeissePreise data with retries
3. Import ALL products from Billa, Spar, and Hofer
4. Ensure no duplicates
5. Ensure every product has offers
6. Use proper database structure

═══════════════════════════════════════════════════════════════════════════
"""

import hashlib
import sys
import time
import urllib.parse
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
import psycopg2
from psycopg2.extras import execute_values

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
from dotenv import load_dotenv

load_dotenv()

HEISSE_PREISE_URL = "https://heisse-preise.io/data/latest-canonical.json"
TARGET_STORES = {"billa", "spar", "hofer"}
STORE_DISPLAY_NAMES = {"billa": "Billa", "spar": "Spar", "hofer": "Hofer"}

def create_fingerprint(name, quantity, unit):
    """Create unique fingerprint for a product"""
    normalized = name.lower().strip()
    fp_str = f"{normalized}|{quantity}|{unit}"
    return hashlib.sha256(fp_str.encode("utf-8")).hexdigest()

def download_with_retry(url, max_retries=3):
    """Download data with retries"""
    for attempt in range(max_retries):
        try:
            print(f"  Attempt {attempt + 1}/{max_retries}...")
            resp = requests.get(url, timeout=180, stream=True)
            resp.raise_for_status()
            
            # Download in chunks to avoid timeout
            content = b''
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    content += chunk
            
            data = json.loads(content)
            return data
        except Exception as e:
            print(f"  ❌ Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 10
                print(f"  Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                raise

def main():
    print("=" * 70)
    print("FINAL HeissePreise Import - Complete Solution")
    print("=" * 70)
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Load data from local file
    print("\n" + "=" * 70)
    print("STEP 1: Loading HeissePreise Data from Local File")
    print("=" * 70)
    
    local_file = "/tmp/heissepreise.json"
    
    if not os.path.exists(local_file):
        print(f"❌ Local file not found: {local_file}")
        print(f"Downloading from {HEISSE_PREISE_URL}...")
        try:
            data = download_with_retry(HEISSE_PREISE_URL)
            print(f"✓ Downloaded {len(data):,} total items")
        except Exception as e:
            print(f"❌ Download failed after all retries: {e}")
            sys.exit(1)
    else:
        print(f"✓ Loading from {local_file}...")
        try:
            with open(local_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"✓ Loaded {len(data):,} total items")
        except Exception as e:
            print(f"❌ Failed to load local file: {e}")
            sys.exit(1)
    
    # Step 2: Filter and organize data
    print("\n" + "=" * 70)
    print("STEP 2: Filtering and Organizing Data")
    print("=" * 70)
    
    # Organize by store
    store_items = {s: [] for s in TARGET_STORES}
    for item in data:
        store = item.get("store", "").lower()
        if store in store_items:
            store_items[store].append(item)
    
    for store_key, items in store_items.items():
        print(f"  {STORE_DISPLAY_NAMES[store_key]}: {len(items):,} items")
    
    # Step 3: Connect to database
    print("\n" + "=" * 70)
    print("STEP 3: Connecting to Database")
    print("=" * 70)
    
    db_url = os.environ.get('DATABASE_URL')
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    # Get default category
    cur.execute("SELECT id FROM categories WHERE slug = 'uncategorized' LIMIT 1")
    row = cur.fetchone()
    default_category_id = row[0] if row else None
    
    if not default_category_id:
        cur.execute("SELECT id FROM categories LIMIT 1")
        row = cur.fetchone()
        default_category_id = row[0] if row else None
    
    print(f"✓ Connected to database")
    print(f"✓ Using category ID: {default_category_id}")
    
    # Step 4: Clear existing data
    print("\n" + "=" * 70)
    print("STEP 4: Clearing Existing Products and Offers")
    print("=" * 70)
    
    cur.execute("SELECT COUNT(*) FROM products")
    old_products = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM offers")
    old_offers = cur.fetchone()[0]
    
    print(f"  Current: {old_products:,} products, {old_offers:,} offers")
    print(f"  Deleting all products and offers...")
    
    # Delete in correct order (offers first due to foreign key)
    cur.execute("DELETE FROM offers")
    cur.execute("DELETE FROM products")
    conn.commit()
    
    print(f"  ✓ Database cleared")
    
    # Step 5: Process and import data
    print("\n" + "=" * 70)
    print("STEP 5: Processing and Importing Data")
    print("=" * 70)
    
    now = datetime.now(timezone.utc)
    
    # We'll collect all products and offers first, then deduplicate
    all_products = {}  # fingerprint -> product_data
    all_offers = {}    # (fingerprint, store_id) -> offer_data
    
    for store_key in sorted(TARGET_STORES):
        items = store_items[store_key]
        print(f"\n  Processing {STORE_DISPLAY_NAMES[store_key]}: {len(items):,} items")
        
        processed = 0
        skipped = 0
        
        for idx, item in enumerate(items):
            if (idx + 1) % 5000 == 0:
                print(f"    Progress: {idx + 1:,}/{len(items):,}")
            
            name = (item.get("name") or "").strip()
            price = item.get("price")
            
            # Skip items without name or price
            if not name or not price:
                skipped += 1
                continue
            
            quantity = item.get("quantity", 0)
            unit = (item.get("unit") or "stk").lower().strip()
            is_unavailable = item.get("unavailable", False)
            
            # Create fingerprint
            fingerprint = create_fingerprint(name, quantity, unit)
            
            # Build product URL
            url_slug = item.get("url", "").strip()
            if store_key == "billa" and url_slug:
                product_url = f"https://shop.billa.at/p/{url_slug}"
            elif store_key == "hofer" and url_slug:
                product_url = f"https://www.roksh.at/hofer/produkte/{url_slug}"
            elif store_key == "spar" and name:
                product_url = f"https://www.interspar.at/shop/lebensmittel/search?q={urllib.parse.quote(name[:80])}"
            else:
                product_url = None
            
            # Add product (will be deduplicated by fingerprint)
            if fingerprint not in all_products:
                all_products[fingerprint] = {
                    'fingerprint': fingerprint,
                    'name_de': name,
                    'category_id': default_category_id,
                    'store_id': store_key,  # Primary store
                    'unit_normalized': unit,
                    'size_normalized': quantity if quantity else None,
                    'created_at': now,
                    'updated_at': now
                }
            
            # Add offer (one per store per product)
            offer_key = (fingerprint, store_key)
            if offer_key not in all_offers:
                all_offers[offer_key] = {
                    'fingerprint': fingerprint,
                    'store_id': store_key,
                    'price': price,
                    'product_url': product_url,
                    'is_available': not is_unavailable,
                    'last_seen': now,
                    'created_at': now,
                    'updated_at': now
                }
            
            processed += 1
        
        print(f"    ✓ Processed: {processed:,}, Skipped: {skipped:,}")
    
    print(f"\n  Total unique products: {len(all_products):,}")
    print(f"  Total unique offers: {len(all_offers):,}")
    
    # Step 6: Insert products
    print("\n" + "=" * 70)
    print("STEP 6: Inserting Products")
    print("=" * 70)
    
    products_list = list(all_products.values())
    products_tuples = [
        (
            p['fingerprint'],
            p['name_de'],
            p['category_id'],
            p['store_id'],
            p['unit_normalized'],
            p['size_normalized'],
            p['created_at'],
            p['updated_at']
        )
        for p in products_list
    ]
    
    print(f"  Inserting {len(products_tuples):,} products...")
    batch_size = 1000
    for i in range(0, len(products_tuples), batch_size):
        batch = products_tuples[i:i + batch_size]
        execute_values(
            cur,
            """
            INSERT INTO products (fingerprint, name_de, category_id, store_id, unit_normalized, size_normalized, created_at, updated_at)
            VALUES %s
            """,
            batch
        )
        conn.commit()
        print(f"    Inserted: {min(i + batch_size, len(products_tuples)):,}/{len(products_tuples):,}")
    
    print(f"  ✓ All products inserted")
    
    # Step 7: Insert offers
    print("\n" + "=" * 70)
    print("STEP 7: Inserting Offers")
    print("=" * 70)
    
    # First, get product IDs
    print(f"  Loading product IDs...")
    cur.execute("SELECT id, fingerprint FROM products")
    fingerprint_to_id = {row[1]: row[0] for row in cur.fetchall()}
    print(f"  ✓ Loaded {len(fingerprint_to_id):,} product IDs")
    
    # Prepare offers with product IDs
    offers_list = []
    for offer in all_offers.values():
        product_id = fingerprint_to_id.get(offer['fingerprint'])
        if product_id:
            offers_list.append((
                product_id,
                offer['store_id'],
                offer['price'],
                offer['product_url'],
                offer['is_available'],
                offer['last_seen'],
                offer['created_at'],
                offer['updated_at']
            ))
    
    print(f"  Inserting {len(offers_list):,} offers...")
    for i in range(0, len(offers_list), batch_size):
        batch = offers_list[i:i + batch_size]
        execute_values(
            cur,
            """
            INSERT INTO offers (product_id, store_id, price, product_url, is_available, last_seen, created_at, updated_at)
            VALUES %s
            """,
            batch
        )
        conn.commit()
        print(f"    Inserted: {min(i + batch_size, len(offers_list)):,}/{len(offers_list):,}")
    
    print(f"  ✓ All offers inserted")
    
    # Step 8: Verification
    print("\n" + "=" * 70)
    print("STEP 8: Verification")
    print("=" * 70)
    
    cur.execute("SELECT COUNT(*) FROM products")
    final_products = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM offers")
    final_offers = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM products WHERE store_id IS NULL")
    null_store = cur.fetchone()[0]
    
    cur.execute("""
        SELECT COUNT(*)
        FROM products p
        LEFT JOIN offers o ON p.id = o.product_id
        WHERE o.id IS NULL
    """)
    products_without_offers = cur.fetchone()[0]
    
    print(f"\n  Final Database Status:")
    print(f"    Total products: {final_products:,}")
    print(f"    Total offers: {final_offers:,}")
    print(f"    Products with NULL store_id: {null_store:,}")
    print(f"    Products without offers: {products_without_offers:,}")
    
    print(f"\n  By Store:")
    for store_key in sorted(TARGET_STORES):
        cur.execute("SELECT COUNT(*) FROM products WHERE store_id = %s", (store_key,))
        p_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM offers WHERE store_id = %s", (store_key,))
        o_count = cur.fetchone()[0]
        print(f"    {STORE_DISPLAY_NAMES[store_key]}: {p_count:,} products, {o_count:,} offers")
    
    # Check for issues
    if null_store > 0:
        print(f"\n  ⚠️ WARNING: {null_store:,} products have NULL store_id")
    else:
        print(f"\n  ✅ All products have store_id")
    
    if products_without_offers > 0:
        print(f"  ⚠️ WARNING: {products_without_offers:,} products have no offers")
    else:
        print(f"  ✅ All products have offers")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 70)
    print("IMPORT COMPLETE!")
    print("=" * 70)
    print(f"  Products: {final_products:,}")
    print(f"  Offers: {final_offers:,}")
    print(f"  Success: {'✅' if null_store == 0 and products_without_offers == 0 else '⚠️'}")
    print("\nDone!")

if __name__ == "__main__":
    main()
