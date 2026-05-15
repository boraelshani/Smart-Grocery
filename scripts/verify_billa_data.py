#!/usr/bin/env python3
"""Verify Billa data in PostgreSQL database."""

import os
import sys
from dotenv import load_dotenv
import psycopg2

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

def main():
    load_dotenv()
    database_uri = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI")
    
    if not database_uri:
        print("ERROR: DATABASE_URL or SQLALCHEMY_DATABASE_URI not set")
        return
    
    conn = psycopg2.connect(database_uri)
    cursor = conn.cursor()
    
    print("=" * 70)
    print("BILLA DATA VERIFICATION REPORT")
    print("=" * 70)
    print()
    
    # Total products
    cursor.execute("SELECT COUNT(*) FROM products WHERE store_id = 'billa'")
    total_products = cursor.fetchone()[0]
    print(f"✓ Total Billa Products: {total_products:,}")
    
    # Total offers
    cursor.execute("SELECT COUNT(*) FROM offers WHERE store_id = 'billa'")
    total_offers = cursor.fetchone()[0]
    print(f"✓ Total Billa Offers: {total_offers:,}")
    
    # Offers with base price
    cursor.execute("SELECT COUNT(*) FROM offers WHERE store_id = 'billa' AND base_price IS NOT NULL")
    with_base = cursor.fetchone()[0]
    print(f"✓ Offers with Base Price: {with_base:,}")
    
    # Offers with promo price
    cursor.execute("SELECT COUNT(*) FROM offers WHERE store_id = 'billa' AND promo_price IS NOT NULL")
    with_promo = cursor.fetchone()[0]
    print(f"✓ Offers with Promo Price: {with_promo:,} ({with_promo/total_offers*100:.1f}%)")
    
    # Offers with unit price
    cursor.execute("SELECT COUNT(*) FROM offers WHERE store_id = 'billa' AND unit_price IS NOT NULL")
    with_unit = cursor.fetchone()[0]
    print(f"✓ Offers with Unit Price: {with_unit:,} ({with_unit/total_offers*100:.1f}%)")
    
    # Offers with offer details
    cursor.execute("SELECT COUNT(*) FROM offers WHERE store_id = 'billa' AND offer_details IS NOT NULL")
    with_details = cursor.fetchone()[0]
    print(f"✓ Offers with Offer Details: {with_details:,} ({with_details/total_offers*100:.1f}%)")
    
    # Offers with min quantity
    cursor.execute("SELECT COUNT(*) FROM offers WHERE store_id = 'billa' AND min_quantity IS NOT NULL")
    with_min_qty = cursor.fetchone()[0]
    print(f"✓ Offers with Min Quantity: {with_min_qty:,} ({with_min_qty/total_offers*100:.1f}%)")
    
    print()
    print("=" * 70)
    print("SAMPLE PROMOTIONAL OFFERS")
    print("=" * 70)
    print()
    
    # Sample promotional offers
    cursor.execute("""
        SELECT 
            p.name_de,
            o.base_price,
            o.promo_price,
            o.offer_details,
            o.min_quantity,
            o.unit_price
        FROM offers o
        JOIN products p ON o.product_id = p.id
        WHERE o.store_id = 'billa' 
            AND o.promo_price IS NOT NULL
        ORDER BY (o.base_price - o.promo_price) DESC
        LIMIT 10
    """)
    
    rows = cursor.fetchall()
    if rows:
        for idx, (name, base, promo, details, min_qty, unit_price) in enumerate(rows, 1):
            savings = float(base - promo) if base and promo else 0
            savings_pct = (savings / float(base) * 100) if base and base > 0 else 0
            print(f"{idx}. {name[:50]}")
            print(f"   Base: €{base:.2f} → Promo: €{promo:.2f} (Save €{savings:.2f} / {savings_pct:.0f}%)")
            if details:
                print(f"   Details: {details}")
            if min_qty:
                print(f"   Min Quantity: {min_qty}")
            if unit_price:
                print(f"   Unit Price: {unit_price}")
            print()
    else:
        print("No promotional offers found.")
    
    print("=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    print()
    
    if total_products < 14000:
        missing = 15000 - total_products
        print(f"⚠ Missing approximately {missing:,} products")
        print(f"  Run: python3 scripts/billa_sitemap_to_postgres.py --resume")
        print()
    
    if with_promo == 0:
        print(f"⚠ No promotional offers detected")
        print(f"  The scraper may need to be run to capture current promotions")
        print(f"  Run: python3 scripts/billa_sitemap_to_postgres.py --resume")
        print()
    
    if total_products >= 14000 and with_promo > 0:
        print(f"✓ Database looks good!")
        print(f"  {total_products:,} products with {with_promo:,} promotional offers")
        print()
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
