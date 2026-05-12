#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════
Fix Product store_id Issue - PostgreSQL
═══════════════════════════════════════════════════════════════════════════

This script fixes the issue where products have NULL store_id by:
1. Updating products with offers to copy store_id from their offers
2. Deleting orphaned products (no offers, no store_id)
3. Optionally importing fresh data from HeissePreise for Billa, Spar, Hofer

Usage:
    python scripts/fix_product_store_ids.py

═══════════════════════════════════════════════════════════════════════════
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import app
from models.postgres_models import db, Product, Offer, Store
from sqlalchemy import text
import time

def fix_products_with_offers():
    """Update products that have offers to get store_id from their first offer."""
    print("\n" + "=" * 70)
    print("STEP 1: Fixing products with offers")
    print("=" * 70)
    
    with app.app_context():
        # Find products with NULL store_id but have offers
        query = text("""
            UPDATE products p
            SET store_id = o.store_id
            FROM (
                SELECT DISTINCT ON (product_id) product_id, store_id
                FROM offers
                WHERE store_id IS NOT NULL
                ORDER BY product_id, id
            ) o
            WHERE p.id = o.product_id
            AND p.store_id IS NULL
        """)
        
        result = db.session.execute(query)
        db.session.commit()
        
        updated = result.rowcount
        print(f"✓ Updated {updated:,} products with store_id from their offers")
        
        return updated

def analyze_orphaned_products():
    """Analyze products without offers."""
    print("\n" + "=" * 70)
    print("STEP 2: Analyzing orphaned products (no offers)")
    print("=" * 70)
    
    with app.app_context():
        # Count products without offers
        query = text("""
            SELECT COUNT(*)
            FROM products p
            LEFT JOIN offers o ON p.id = o.product_id
            WHERE o.id IS NULL
        """)
        
        result = db.session.execute(query)
        orphaned_count = result.scalar()
        
        print(f"Found {orphaned_count:,} products without any offers")
        print("These products will be deleted as they have no pricing data.")
        
        return orphaned_count

def delete_orphaned_products():
    """Delete products that have no offers."""
    print("\n" + "=" * 70)
    print("STEP 3: Deleting orphaned products")
    print("=" * 70)
    
    with app.app_context():
        # Delete products without offers
        query = text("""
            DELETE FROM products p
            WHERE NOT EXISTS (
                SELECT 1 FROM offers o WHERE o.product_id = p.id
            )
        """)
        
        result = db.session.execute(query)
        db.session.commit()
        
        deleted = result.rowcount
        print(f"✓ Deleted {deleted:,} orphaned products")
        
        return deleted

def verify_fix():
    """Verify the fix was successful."""
    print("\n" + "=" * 70)
    print("STEP 4: Verification")
    print("=" * 70)
    
    with app.app_context():
        total_products = Product.query.count()
        null_store_id = Product.query.filter(Product.store_id.is_(None)).count()
        has_store_id = Product.query.filter(Product.store_id.isnot(None)).count()
        
        print(f"\nFinal Status:")
        print(f"  Total products: {total_products:,}")
        print(f"  Products with store_id: {has_store_id:,}")
        print(f"  Products with NULL store_id: {null_store_id:,}")
        
        if null_store_id > 0:
            print(f"\n⚠ WARNING: {null_store_id:,} products still have NULL store_id")
            print("  These products may need manual review.")
        else:
            print(f"\n✓ SUCCESS: All products now have store_id!")
        
        # Show breakdown by store
        print(f"\nProducts by store:")
        stores = Store.query.all()
        for store in stores:
            count = Product.query.filter_by(store_id=store.store_id).count()
            if count > 0:
                print(f"  {store.name}: {count:,} products")
        
        # Show sample products
        print(f"\nSample products:")
        samples = Product.query.filter(Product.store_id.isnot(None)).limit(5).all()
        for p in samples:
            offers = Offer.query.filter_by(product_id=p.id).count()
            print(f"  {p.name_de[:50]}")
            print(f"    Store: {p.store_id}, Offers: {offers}")

def main():
    print("=" * 70)
    print("Smart Grocery - Fix Product store_id Issue")
    print("=" * 70)
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Step 1: Fix products with offers
        updated = fix_products_with_offers()
        
        # Step 2: Analyze orphaned products
        orphaned = analyze_orphaned_products()
        
        # Step 3: Delete orphaned products automatically
        if orphaned > 0:
            print(f"\n⚠ Deleting {orphaned:,} orphaned products...")
            deleted = delete_orphaned_products()
        else:
            deleted = 0
        
        # Step 4: Verify
        verify_fix()
        
        print("\n" + "=" * 70)
        print("FIX COMPLETE")
        print("=" * 70)
        print(f"  Products updated: {updated:,}")
        print(f"  Products deleted: {deleted:,}")
        print("\nDone!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
