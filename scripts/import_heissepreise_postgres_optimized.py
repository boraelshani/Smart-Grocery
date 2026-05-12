#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════
Smart Grocery – Heisse Preise Import for PostgreSQL (OPTIMIZED)
═══════════════════════════════════════════════════════════════════════════

Optimized version that uses bulk operations to avoid connection issues.

Usage:
    python scripts/import_heissepreise_postgres_optimized.py

═══════════════════════════════════════════════════════════════════════════
"""

import hashlib
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

import requests

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import app
from models.postgres_models import db, Product, Offer, Store, Category
from sqlalchemy import text

# ───────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ───────────────────────────────────────────────────────────────────────────

HEISSE_PREISE_URL = "https://heisse-preise.io/data/latest-canonical.json"
TARGET_STORES = {"billa", "spar", "hofer"}
STORE_DISPLAY_NAMES = {"billa": "Billa", "spar": "Spar", "hofer": "Hofer"}
BATCH_SIZE = 1000

def download_data():
    """Download data from heisse-preise.io"""
    print("\n" + "=" * 70)
    print("STEP 1: Downloading data from heisse-preise.io")
    print("=" * 70)
    try:
        print(f"Fetching: {HEISSE_PREISE_URL}")
        resp = requests.get(HEISSE_PREISE_URL, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        print(f"✓ Downloaded {len(data):,} total items")
        return data
    except Exception as e:
        print(f"❌ ERROR: Download failed: {e}")
        sys.exit(1)

def filter_stores(data):
    """Filter for target stores"""
    print("\n" + "=" * 70)
    print("STEP 2: Filtering for Billa, Spar, Hofer")
    print("=" * 70)
    filtered = {s: [] for s in TARGET_STORES}
    for item in data:
        store = item.get("store", "").lower()
        if store in filtered:
            filtered[store].append(item)
    
    for store_key, items in filtered.items():
        print(f"  {STORE_DISPLAY_NAMES[store_key]}: {len(items):,} items")
    
    return filtered

def create_fingerprint(name, quantity, unit):
    """Create a unique fingerprint for a product"""
    normalized = name.lower().strip()
    fp_str = f"{normalized}|{quantity}|{unit}"
    return hashlib.sha256(fp_str.encode("utf-8")).hexdigest()

def import_to_postgres_bulk(filtered_data):
    """Import data into PostgreSQL using bulk operations"""
    print("\n" + "=" * 70)
    print("STEP 3: Importing to PostgreSQL (BULK MODE)")
    print("=" * 70)
    
    with app.app_context():
        now = datetime.now(timezone.utc)
        
        # Get store mappings
        stores = {s.store_id: s for s in Store.query.all()}
        
        # Get default category
        default_category = Category.query.filter_by(slug='uncategorized').first()
        if not default_category:
            default_category = Category.query.first()
        
        stats = {
            'total_items': 0,
            'products_created': 0,
            'products_updated': 0,
            'offers_created': 0,
            'offers_updated': 0,
        }
        
        # Load ALL existing fingerprints into memory (much faster than querying one by one)
        print("\n  Loading existing products into memory...")
        existing_products = {}
        for p in Product.query.all():
            existing_products[p.fingerprint] = p.id
        print(f"  ✓ Loaded {len(existing_products):,} existing products")
        
        # Load ALL existing offers into memory
        print("  Loading existing offers into memory...")
        existing_offers = {}
        for o in Offer.query.all():
            key = (o.product_id, o.store_id)
            existing_offers[key] = o
        print(f"  ✓ Loaded {len(existing_offers):,} existing offers")
        
        # Process each store
        for store_key in sorted(TARGET_STORES):
            items = filtered_data[store_key]
            display_name = STORE_DISPLAY_NAMES[store_key]
            print(f"\n  Processing {display_name}: {len(items):,} items")
            
            if store_key not in stores:
                print(f"  ⚠ WARNING: Store '{store_key}' not found in database, skipping")
                continue
            
            # Prepare bulk data
            products_to_insert = []
            offers_to_insert = []
            offers_to_update = []
            
            for idx, item in enumerate(items):
                if (idx + 1) % 5000 == 0:
                    print(f"    Preparing: {idx + 1:,}/{len(items):,}")
                
                stats['total_items'] += 1
                
                # Extract item data
                name = (item.get("name") or "").strip()
                price = item.get("price")
                if not name or not price:
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
                
                # Check if product exists
                product_id = existing_products.get(fingerprint)
                
                if not product_id:
                    # New product - prepare for bulk insert
                    # But only if we haven't already added it in this batch
                    if fingerprint not in {p['fingerprint'] for p in products_to_insert}:
                        product_data = {
                            'fingerprint': fingerprint,
                            'name_de': name,
                            'brand': None,
                            'category_id': default_category.id if default_category else None,
                            'store_id': store_key,
                            'unit_normalized': unit,
                            'size_normalized': quantity if quantity else None,
                            'default_image_url': None,
                            'barcode': None,
                            'created_at': now,
                            'updated_at': now
                        }
                        products_to_insert.append(product_data)
                        stats['products_created'] += 1
                    
                    # We'll need to insert products first, then get their IDs for offers
                    # So we'll mark this for later processing
                    product_id = None
                else:
                    stats['products_updated'] += 1
                
                # Prepare offer data
                if product_id:
                    offer_key = (product_id, store_key)
                    offer_data = {
                        'product_id': product_id,
                        'store_id': store_key,
                        'price': price,
                        'product_url': product_url,
                        'is_available': not is_unavailable,
                        'last_seen': now,
                        'updated_at': now
                    }
                    
                    if offer_key in existing_offers:
                        # Update existing offer
                        offer_data['id'] = existing_offers[offer_key].id
                        offers_to_update.append(offer_data)
                        stats['offers_updated'] += 1
                    else:
                        # New offer
                        offer_data['created_at'] = now
                        offers_to_insert.append(offer_data)
                        stats['offers_created'] += 1
            
            # Bulk insert products
            if products_to_insert:
                print(f"\n  Bulk inserting {len(products_to_insert):,} new products...")
                for i in range(0, len(products_to_insert), BATCH_SIZE):
                    batch = products_to_insert[i:i + BATCH_SIZE]
                    db.session.bulk_insert_mappings(Product, batch)
                    db.session.commit()
                    print(f"    Inserted: {min(i + BATCH_SIZE, len(products_to_insert)):,}/{len(products_to_insert):,}")
                
                # Reload product IDs for new products
                print(f"  Reloading product IDs...")
                new_fingerprints = {p['fingerprint'] for p in products_to_insert}
                new_products = Product.query.filter(Product.fingerprint.in_(new_fingerprints)).all()
                for p in new_products:
                    existing_products[p.fingerprint] = p.id
                print(f"  ✓ Reloaded {len(new_products):,} new product IDs")
                
                # Now create offers for new products
                print(f"  Creating offers for new products...")
                new_offers = []
                for item in items:
                    name = (item.get("name") or "").strip()
                    price = item.get("price")
                    if not name or not price:
                        continue
                    
                    quantity = item.get("quantity", 0)
                    unit = (item.get("unit") or "stk").lower().strip()
                    fingerprint = create_fingerprint(name, quantity, unit)
                    
                    product_id = existing_products.get(fingerprint)
                    if not product_id:
                        continue
                    
                    offer_key = (product_id, store_key)
                    if offer_key not in existing_offers:
                        is_unavailable = item.get("unavailable", False)
                        url_slug = item.get("url", "").strip()
                        if store_key == "billa" and url_slug:
                            product_url = f"https://shop.billa.at/p/{url_slug}"
                        elif store_key == "hofer" and url_slug:
                            product_url = f"https://www.roksh.at/hofer/produkte/{url_slug}"
                        elif store_key == "spar" and name:
                            product_url = f"https://www.interspar.at/shop/lebensmittel/search?q={urllib.parse.quote(name[:80])}"
                        else:
                            product_url = None
                        
                        new_offers.append({
                            'product_id': product_id,
                            'store_id': store_key,
                            'price': price,
                            'product_url': product_url,
                            'is_available': not is_unavailable,
                            'last_seen': now,
                            'created_at': now,
                            'updated_at': now
                        })
                
                if new_offers:
                    print(f"  Bulk inserting {len(new_offers):,} new offers...")
                    for i in range(0, len(new_offers), BATCH_SIZE):
                        batch = new_offers[i:i + BATCH_SIZE]
                        db.session.bulk_insert_mappings(Offer, batch)
                        db.session.commit()
                        print(f"    Inserted: {min(i + BATCH_SIZE, len(new_offers)):,}/{len(new_offers):,}")
            
            # Bulk insert offers for existing products
            if offers_to_insert:
                print(f"\n  Bulk inserting {len(offers_to_insert):,} offers...")
                for i in range(0, len(offers_to_insert), BATCH_SIZE):
                    batch = offers_to_insert[i:i + BATCH_SIZE]
                    db.session.bulk_insert_mappings(Offer, batch)
                    db.session.commit()
                    print(f"    Inserted: {min(i + BATCH_SIZE, len(offers_to_insert)):,}/{len(offers_to_insert):,}")
            
            # Bulk update offers
            if offers_to_update:
                print(f"\n  Bulk updating {len(offers_to_update):,} offers...")
                for i in range(0, len(offers_to_update), BATCH_SIZE):
                    batch = offers_to_update[i:i + BATCH_SIZE]
                    db.session.bulk_update_mappings(Offer, batch)
                    db.session.commit()
                    print(f"    Updated: {min(i + BATCH_SIZE, len(offers_to_update)):,}/{len(offers_to_update):,}")
            
            print(f"  ✓ Completed {display_name}")
        
        return stats

def verify_import(stats):
    """Verify the import was successful"""
    print("\n" + "=" * 70)
    print("STEP 4: Verification")
    print("=" * 70)
    
    with app.app_context():
        total_products = Product.query.count()
        total_offers = Offer.query.count()
        
        print(f"\nDatabase Status:")
        print(f"  Total products: {total_products:,}")
        print(f"  Total offers: {total_offers:,}")
        
        print(f"\nProducts by store:")
        for store_key in sorted(TARGET_STORES):
            count = Product.query.filter_by(store_id=store_key).count()
            offers_count = Offer.query.filter_by(store_id=store_key).count()
            print(f"  {STORE_DISPLAY_NAMES[store_key]}:")
            print(f"    Products: {count:,}")
            print(f"    Offers: {offers_count:,}")
        
        # Check for NULL store_id
        null_store_id = Product.query.filter(Product.store_id.is_(None)).count()
        if null_store_id > 0:
            print(f"\n⚠ WARNING: {null_store_id:,} products still have NULL store_id")
        else:
            print(f"\n✅ All products have store_id assigned")

def main():
    print("=" * 70)
    print("Smart Grocery – Heisse Preise PostgreSQL Import (OPTIMIZED)")
    print("=" * 70)
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Stores: {', '.join(STORE_DISPLAY_NAMES[s] for s in sorted(TARGET_STORES))}")
    
    t0 = time.time()
    
    try:
        # Download data
        data = download_data()
        
        # Filter for target stores
        filtered = filter_stores(data)
        del data  # Free memory
        
        # Import to PostgreSQL
        stats = import_to_postgres_bulk(filtered)
        
        # Verify
        verify_import(stats)
        
        elapsed = time.time() - t0
        
        print("\n" + "=" * 70)
        print("IMPORT COMPLETE")
        print("=" * 70)
        print(f"  Time: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
        print(f"  Items processed: {stats['total_items']:,}")
        print(f"  Products created: {stats['products_created']:,}")
        print(f"  Products updated: {stats['products_updated']:,}")
        print(f"  Offers created: {stats['offers_created']:,}")
        print(f"  Offers updated: {stats['offers_updated']:,}")
        print("\nDone!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
