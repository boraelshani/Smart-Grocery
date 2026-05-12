#!/usr/bin/env python3
"""
Simple HeissePreise import using raw SQL with ON CONFLICT
"""

import hashlib
import sys
import time
import urllib.parse
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
    normalized = name.lower().strip()
    fp_str = f"{normalized}|{quantity}|{unit}"
    return hashlib.sha256(fp_str.encode("utf-8")).hexdigest()

def main():
    print("=" * 70)
    print("HeissePreise Import (Simple SQL)")
    print("=" * 70)
    
    # Download data
    print("\nDownloading data...")
    resp = requests.get(HEISSE_PREISE_URL, timeout=120)
    data = resp.json()
    print(f"✓ Downloaded {len(data):,} items")
    
    # Filter
    filtered = {s: [] for s in TARGET_STORES}
    for item in data:
        store = item.get("store", "").lower()
        if store in filtered:
            filtered[store].append(item)
    
    for store_key, items in filtered.items():
        print(f"  {STORE_DISPLAY_NAMES[store_key]}: {len(items):,} items")
    
    # Connect to database
    print("\nConnecting to database...")
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
    
    print(f"Using category ID: {default_category_id}")
    
    now = datetime.now(timezone.utc)
    
    total_products = 0
    total_offers = 0
    
    # Process each store
    for store_key in sorted(TARGET_STORES):
        items = filtered[store_key]
        print(f"\nProcessing {STORE_DISPLAY_NAMES[store_key]}: {len(items):,} items")
        
        products_data = []
        offers_data = []
        
        for idx, item in enumerate(items):
            if (idx + 1) % 5000 == 0:
                print(f"  Preparing: {idx + 1:,}/{len(items):,}")
            
            name = (item.get("name") or "").strip()
            price = item.get("price")
            if not name or not price:
                continue
            
            quantity = item.get("quantity", 0)
            unit = (item.get("unit") or "stk").lower().strip()
            is_unavailable = item.get("unavailable", False)
            
            fingerprint = create_fingerprint(name, quantity, unit)
            
            # Build URL
            url_slug = item.get("url", "").strip()
            if store_key == "billa" and url_slug:
                product_url = f"https://shop.billa.at/p/{url_slug}"
            elif store_key == "hofer" and url_slug:
                product_url = f"https://www.roksh.at/hofer/produkte/{url_slug}"
            elif store_key == "spar" and name:
                product_url = f"https://www.interspar.at/shop/lebensmittel/search?q={urllib.parse.quote(name[:80])}"
            else:
                product_url = None
            
            products_data.append((
                fingerprint,
                name,
                default_category_id,
                store_key,
                unit,
                quantity if quantity else None,
                now,
                now
            ))
            
            offers_data.append((
                fingerprint,  # We'll use this to join with products
                store_key,
                price,
                product_url,
                not is_unavailable,
                now,
                now,
                now
            ))
        
        # Insert products with ON CONFLICT
        print(f"  Inserting {len(products_data):,} products...")
        
        # Deduplicate products_data by fingerprint (keep last occurrence)
        seen_fingerprints = {}
        for item in products_data:
            seen_fingerprints[item[0]] = item  # fingerprint is first element
        
        unique_products = list(seen_fingerprints.values())
        print(f"  After deduplication: {len(unique_products):,} unique products")
        
        execute_values(
            cur,
            """
            INSERT INTO products (fingerprint, name_de, category_id, store_id, unit_normalized, size_normalized, created_at, updated_at)
            VALUES %s
            ON CONFLICT (fingerprint) DO UPDATE SET
                updated_at = EXCLUDED.updated_at
            """,
            unique_products,
            page_size=1000
        )
        conn.commit()
        total_products += len(unique_products)
        print(f"  ✓ Products inserted")
        
        # Insert offers with ON CONFLICT
        # First we need to get product IDs
        print(f"  Inserting {len(offers_data):,} offers...")
        
        # Deduplicate offers by (fingerprint, store_id)
        seen_offers = {}
        for item in offers_data:
            key = (item[0], item[1])  # fingerprint, store_id
            seen_offers[key] = item
        
        unique_offers = list(seen_offers.values())
        print(f"  After deduplication: {len(unique_offers):,} unique offers")
        
        # Build a temporary table approach
        cur.execute("CREATE TEMP TABLE temp_offers (fingerprint TEXT, store_id TEXT, price NUMERIC, product_url TEXT, is_available BOOLEAN, last_seen TIMESTAMP, created_at TIMESTAMP, updated_at TIMESTAMP)")
        execute_values(
            cur,
            "INSERT INTO temp_offers VALUES %s",
            unique_offers,
            page_size=1000
        )
        
        # Insert offers by joining with products
        cur.execute("""
            INSERT INTO offers (product_id, store_id, price, product_url, is_available, last_seen, created_at, updated_at)
            SELECT p.id, t.store_id, t.price, t.product_url, t.is_available, t.last_seen, t.created_at, t.updated_at
            FROM temp_offers t
            JOIN products p ON p.fingerprint = t.fingerprint
            ON CONFLICT (product_id, store_id) DO UPDATE SET
                price = EXCLUDED.price,
                product_url = EXCLUDED.product_url,
                is_available = EXCLUDED.is_available,
                last_seen = EXCLUDED.last_seen,
                updated_at = EXCLUDED.updated_at
        """)
        conn.commit()
        total_offers += len(unique_offers)
        
        cur.execute("DROP TABLE temp_offers")
        conn.commit()
        
        print(f"  ✓ Offers inserted")
    
    # Final stats
    cur.execute("SELECT COUNT(*) FROM products")
    final_products = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM offers")
    final_offers = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM products WHERE store_id IS NULL")
    null_store = cur.fetchone()[0]
    
    print("\n" + "=" * 70)
    print("IMPORT COMPLETE")
    print("=" * 70)
    print(f"  Total products in DB: {final_products:,}")
    print(f"  Total offers in DB: {final_offers:,}")
    print(f"  Products with NULL store_id: {null_store:,}")
    
    print(f"\nBy Store:")
    for store_key in sorted(TARGET_STORES):
        cur.execute("SELECT COUNT(*) FROM products WHERE store_id = %s", (store_key,))
        p_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM offers WHERE store_id = %s", (store_key,))
        o_count = cur.fetchone()[0]
        print(f"  {STORE_DISPLAY_NAMES[store_key]}: {p_count:,} products, {o_count:,} offers")
    
    cur.close()
    conn.close()
    
    print("\nDone!")

if __name__ == "__main__":
    main()
