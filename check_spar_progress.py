#!/usr/bin/env python3
"""
Check SPAR scraping progress in database
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models.postgres_models import db, Product, ProductStore, Promotion
from sqlalchemy import func


def check_progress():
    """Check current SPAR products in database."""
    print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                    SPAR SCRAPING PROGRESS CHECK                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
""")
    
    with app.app_context():
        # Count SPAR products
        spar_products = db.session.query(ProductStore).filter_by(store_id='spar').count()
        
        # Count products with images
        products_with_images = db.session.query(Product).join(ProductStore).filter(
            ProductStore.store_id == 'spar',
            Product.default_image_url.isnot(None)
        ).count()
        
        # Count placeholder images
        placeholder_images = db.session.query(Product).join(ProductStore).filter(
            ProductStore.store_id == 'spar',
            Product.default_image_url.isnot(None),
            db.or_(
                Product.default_image_url.like('%veggie%'),
                Product.default_image_url.like('%icon%'),
                Product.default_image_url.like('%placeholder%'),
                Product.default_image_url.like('%badge%'),
                Product.default_image_url.like('%label%')
            )
        ).count()
        
        # Count promotions
        spar_promotions = db.session.query(Promotion).join(
            Promotion.promotion_targets
        ).filter_by(store_id='spar').count()
        
        # Get sample products
        sample_products = db.session.query(Product).join(ProductStore).filter(
            ProductStore.store_id == 'spar'
        ).order_by(Product.created_at.desc()).limit(5).all()
        
        # Calculate percentages
        image_percentage = (products_with_images / spar_products * 100) if spar_products > 0 else 0
        placeholder_percentage = (placeholder_images / products_with_images * 100) if products_with_images > 0 else 0
        real_images = products_with_images - placeholder_images
        real_image_percentage = (real_images / spar_products * 100) if spar_products > 0 else 0
        
        # Calculate progress
        target = 37692
        progress_percentage = (spar_products / target * 100) if target > 0 else 0
        
        # Display results
        print(f"{'='*80}")
        print("OVERALL PROGRESS")
        print(f"{'='*80}")
        print(f"Target products:         37,692")
        print(f"Current products:        {spar_products:,}")
        print(f"Progress:                {progress_percentage:.1f}%")
        print(f"Remaining:               {target - spar_products:,}")
        print()
        
        print(f"{'='*80}")
        print("IMAGE QUALITY")
        print(f"{'='*80}")
        print(f"Products with images:    {products_with_images:,} ({image_percentage:.1f}%)")
        print(f"Real product images:     {real_images:,} ({real_image_percentage:.1f}%)")
        print(f"Placeholder images:      {placeholder_images:,} ({placeholder_percentage:.1f}%)")
        print()
        
        if placeholder_percentage < 5:
            print("✅ Image quality: EXCELLENT (< 5% placeholders)")
        elif placeholder_percentage < 15:
            print("⚠️  Image quality: GOOD (< 15% placeholders)")
        else:
            print("❌ Image quality: NEEDS IMPROVEMENT (> 15% placeholders)")
        print()
        
        print(f"{'='*80}")
        print("PROMOTIONS")
        print(f"{'='*80}")
        print(f"Active promotions:       {spar_promotions:,}")
        print()
        
        print(f"{'='*80}")
        print("RECENT PRODUCTS (last 5 added)")
        print(f"{'='*80}")
        for i, product in enumerate(sample_products, 1):
            print(f"{i}. {product.name[:60]}")
            print(f"   Brand: {product.brand or 'N/A'}")
            print(f"   Image: {'✅ Yes' if product.default_image_url else '❌ No'}")
            if product.default_image_url:
                is_placeholder = any(x in product.default_image_url.lower() for x in 
                                   ['veggie', 'icon', 'placeholder', 'badge', 'label'])
                print(f"   Type:  {'❌ Placeholder' if is_placeholder else '✅ Real image'}")
            print()
        
        print(f"{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}")
        
        if spar_products == 0:
            print("⚠️  No SPAR products found. Run the scraper first!")
        elif spar_products < 1000:
            print(f"🔄 Scraping in progress: {spar_products:,} products")
            print(f"   Keep the scraper running to reach 37,692 products")
        elif spar_products < target * 0.9:
            print(f"🔄 Good progress: {spar_products:,} products ({progress_percentage:.1f}%)")
            print(f"   {target - spar_products:,} products remaining")
        else:
            print(f"✅ Almost complete: {spar_products:,} products ({progress_percentage:.1f}%)")
            print(f"   Only {target - spar_products:,} products remaining!")
        
        print(f"{'='*80}\n")


if __name__ == "__main__":
    check_progress()
