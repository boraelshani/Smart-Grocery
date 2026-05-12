#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════
Smart Grocery – Heisse Preise Import for PostgreSQL
═══════════════════════════════════════════════════════════════════════════

Downloads the latest product data from heisse-preise.io and imports it
into the Smart Grocery PostgreSQL database for BILLA, SPAR, and HOFER.

Usage:
    python scripts/import_heissepreise_postgres.py

This script will:
1. Download latest data from heisse-preise.io
2. Filter for Billa, Spar, and Hofer products
3. Import products and offers into PostgreSQL
4. Update price history

═══════════════════════════════════════════════════════════════════════════
"""

import hashlib
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import app
from models.postgres_models import db, Product, Offer, Store, Category, PriceHistory

# ───────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ───────────────────────────────────────────────────────────────────────────

HEISSE_PREISE_URL = "https://heisse-preise.io/data/latest-canonical.json"
TARGET_STORES = {"billa", "spar", "hofer"}
STORE_DISPLAY_NAMES = {"billa": "Billa", "spar": "Spar", "hofer": "Hofer"}
BATCH_SIZE = 500

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

def import_to_postgres(filtered_data):
    """Import data into PostgreSQL"""
    print("\n" + "=" * 70)
    print("STEP 3: Importing to PostgreSQL")
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
            'price_history': 0,
        }
        
        for store_key in sorted(TARGET_STORES):
            items = filtered_data[store_key]
            display_name = STORE_DISPLAY_NAMES[store_key]
            print(f"\n  Processing {display_name}: {len(items):,} items")
            
            if store_key not in stores:
                print(f"  ⚠ WARNING: Store '{store_key}' not found in database, skipping")
                continue
            
            for idx, item in enumerate(items):
                if (idx + 1) % 1000 == 0:
                    print(f"    Progress: {idx + 1:,}/{len(items):,}")
                
                stats['total_items'] += 1
                
                # Extract item data
                name = (item.get("name") or "").strip()
                price = item.get("price")
                if not name or not price:
                    continue
                
                quantity = item.get("quantity", 0)
                unit = (item.get("unit") or "stk").lower().strip()
                is_unavailable = item.get("unavailable", False)
                is_bio = item.get("bio", False)
                
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
                
                # Find or create product
                product = Product.query.filter_by(fingerprint=fingerprint).first()
                
                if not product:
                    # Create new product
                    product = Product(
                        fingerprint=fingerprint,
                        name_de=name,
                        brand=None,
                        category_id=default_category.id if default_category else None,
                        store_id=store_key,
                        unit_normalized=unit,
                        size_normalized=quantity if quantity else None,
                        default_image_url=None,
                        barcode=None,
                        created_at=now,
                        updated_at=now
                    )
                    db.session.add(product)
                    db.session.flush()  # Get the ID
                    stats['products_created'] += 1
                else:
                    # Update existing product
                    product.updated_at = now
                    if not product.store_id:
                        product.store_id = store_key
                    stats['products_updated'] += 1
                
                # Find or create offer
                offer = Offer.query.filter_by(
                    product_id=product.id,
                    store_id=store_key
                ).first()
                
                if not offer:
                    # Create new offer
                    offer = Offer(
                        product_id=product.id,
                        store_id=store_key,
                        price=price,
                        product_url=product_url,
                        is_available=not is_unavailable,
                        last_seen=now,
                        created_at=now,
                        updated_at=now
                    )
                    db.session.add(offer)
                    stats['offers_created'] += 1
                else:
                    # Update existing offer
                    old_price = offer.price
                    offer.price = price
                    offer.product_url = product_url
                    offer.is_available = not is_unavailable
                    offer.last_seen = now
                    offer.updated_at = now
                    stats['offers_updated'] += 1
                    
                    # Record price change
                    if old_price and old_price != price:
                        price_hist = PriceHistory(
                            offer_id=offer.id,
                            old_price=old_price,
                            new_price=price,
                            changed_at=now,
                            source='heissepreise',
                            price=price,
                            recorded_at=now
                        )
                        db.session.add(price_hist)
                        stats['price_history'] += 1
                
                # Commit in batches
                if stats['total_items'] % BATCH_SIZE == 0:
                    db.session.commit()
            
            # Final commit for this store
            db.session.commit()
            print(f"    ✓ Completed {display_name}")
        
        return stats

def verify_import(stats):
    """Verify the import was successful"""
    print("\n" + "=" * 70)
    print("STEP 4: Verification")
    print("=" * 70)
    
    with app.app_context():
        total_products = Product.query.count()
        total_offers = Offer.query.count()
        total_price_history = PriceHistory.query.count()
        
        print(f"\nDatabase Status:")
        print(f"  Total products: {total_products:,}")
        print(f"  Total offers: {total_offers:,}")
        print(f"  Total price history: {total_price_history:,}")
        
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
            print(f"\n✓ All products have store_id assigned")
        
        # Sample products
        print(f"\nSample products:")
        samples = Product.query.filter(Product.store_id.isnot(None)).limit(5).all()
        for p in samples:
            offers = Offer.query.filter_by(product_id=p.id).all()
            print(f"  {p.name_de[:50]}")
            print(f"    Store: {p.store_id}, Offers: {len(offers)}")
            for o in offers[:2]:
                print(f"      - {o.store_id}: €{o.price}")

def main():
    print("=" * 70)
    print("Smart Grocery – Heisse Preise PostgreSQL Import")
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
        stats = import_to_postgres(filtered)
        
        # Verify
        verify_import(stats)
        
        elapsed = time.time() - t0
        
        print("\n" + "=" * 70)
        print("IMPORT COMPLETE")
        print("=" * 70)
        print(f"  Time: {elapsed:.1f}s")
        print(f"  Items processed: {stats['total_items']:,}")
        print(f"  Products created: {stats['products_created']:,}")
        print(f"  Products updated: {stats['products_updated']:,}")
        print(f"  Offers created: {stats['offers_created']:,}")
        print(f"  Offers updated: {stats['offers_updated']:,}")
        print(f"  Price history entries: {stats['price_history']:,}")
        print("\nDone!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
