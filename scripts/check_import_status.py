#!/usr/bin/env python3
"""Quick script to check import status"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import app
from models.postgres_models import Product, Offer

with app.app_context():
    print("\n" + "=" * 60)
    print("DATABASE STATUS")
    print("=" * 60)
    
    total_products = Product.query.count()
    total_offers = Offer.query.count()
    null_store = Product.query.filter(Product.store_id.is_(None)).count()
    
    print(f"\nOverall:")
    print(f"  Products: {total_products:,}")
    print(f"  Offers: {total_offers:,}")
    print(f"  NULL store_id: {null_store:,}")
    
    if null_store == 0:
        print(f"  ✅ All products have store_id!")
    else:
        print(f"  ⚠ {null_store:,} products missing store_id")
    
    print(f"\nBy Store:")
    for store in ['billa', 'spar', 'hofer']:
        p_count = Product.query.filter_by(store_id=store).count()
        o_count = Offer.query.filter_by(store_id=store).count()
        print(f"  {store.capitalize():6s}: {p_count:6,} products, {o_count:6,} offers")
    
    print("\n" + "=" * 60)
