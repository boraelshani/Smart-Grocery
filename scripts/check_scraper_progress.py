#!/usr/bin/env python3
"""Quick script to check Billa scraper progress."""

import os
import psycopg2
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

print("=" * 70)
print(f"BILLA SCRAPER PROGRESS - {datetime.now().strftime('%H:%M:%S')}")
print("=" * 70)
print()

# Total products for Billa (using new schema)
cur.execute("""
    SELECT COUNT(DISTINCT ps.product_id) 
    FROM product_store ps 
    WHERE ps.store_id = 'billa'
""")
total = cur.fetchone()[0]
print(f"✓ Total Billa Products: {total:,}")

# Products with offer data in _old_offers
cur.execute("""
    SELECT COUNT(DISTINCT o.product_id)
    FROM _old_offers o
    WHERE o.store_id = 'billa' AND o.base_price IS NOT NULL
""")
with_base = cur.fetchone()[0]
print(f"✓ Products with Base Price: {with_base:,} ({with_base/total*100:.1f}%)")

# Promotional offers
cur.execute("""
    SELECT COUNT(*)
    FROM _old_offers o
    WHERE o.store_id = 'billa' AND o.promo_price IS NOT NULL
""")
with_promo = cur.fetchone()[0]
print(f"✓ Promotional Offers: {with_promo:,} ({with_promo/total*100:.1f}%)")

# Unit prices
cur.execute("""
    SELECT COUNT(*)
    FROM _old_offers o
    WHERE o.store_id = 'billa' AND o.unit_price IS NOT NULL
""")
with_unit = cur.fetchone()[0]
print(f"✓ Unit Prices: {with_unit:,} ({with_unit/total*100:.1f}%)")

# Offer details
cur.execute("""
    SELECT COUNT(*)
    FROM _old_offers o
    WHERE o.store_id = 'billa' AND o.offer_details IS NOT NULL
""")
with_details = cur.fetchone()[0]
print(f"✓ Offer Details: {with_details:,} ({with_details/total*100:.1f}%)")

# Active promotions in new schema
cur.execute("""
    SELECT COUNT(DISTINCT pt.product_id)
    FROM promotion_targets pt
    WHERE pt.store_id = 'billa'
""")
in_promotions = cur.fetchone()[0]
print(f"✓ Products in Active Promotions: {in_promotions:,}")

print()
print("Target: ~15,000 products with full offer data")
print(f"Progress: {total:,} / 15,000 ({total/15000*100:.1f}%)")

if total >= 14000:
    print("✅ Scraper appears to be complete!")
elif total >= 10000:
    print("⏳ Scraper is making good progress...")
else:
    print("🔄 Scraper is still running...")

conn.close()
