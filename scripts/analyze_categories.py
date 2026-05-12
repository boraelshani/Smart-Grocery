#!/usr/bin/env python3
"""
Analyze category hierarchy in the database
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.postgres_models import Category, db

def analyze_categories():
    with app.app_context():
        # Get all categories
        all_cats = Category.query.all()
        print(f"Total categories: {len(all_cats)}")
        
        # Group by level
        by_level = {}
        for cat in all_cats:
            level = cat.level if cat.level is not None else 'None'
            by_level.setdefault(level, []).append(cat)
        
        print(f"\nCategories by level:")
        for level in sorted(by_level.keys(), key=lambda x: x if isinstance(x, int) else -1):
            print(f"  Level {level}: {len(by_level[level])} categories")
        
        # Root categories (parent_id is NULL)
        root_cats = Category.query.filter(Category.parent_id.is_(None)).order_by(Category.name_de).all()
        print(f"\nRoot categories (parent_id is NULL): {len(root_cats)}")
        
        # Show hierarchy for first few root categories
        print(f"\nCategory Hierarchy (first 5 root categories):")
        for root in root_cats[:5]:
            print(f"\n{root.name_de or root.name_en} (ID: {root.id}, Level: {root.level})")
            print(f"  Image: {root.image_url[:50] if root.image_url else 'None'}...")
            
            # Get children (level 2)
            children = Category.query.filter_by(parent_id=root.id).order_by(Category.name_de).all()
            print(f"  Children: {len(children)}")
            
            for child in children[:3]:
                print(f"    - {child.name_de or child.name_en} (ID: {child.id}, Level: {child.level})")
                
                # Get grandchildren (level 3)
                grandchildren = Category.query.filter_by(parent_id=child.id).all()
                if grandchildren:
                    print(f"      Grandchildren: {len(grandchildren)}")
                    for gc in grandchildren[:2]:
                        print(f"        * {gc.name_de or gc.name_en}")
            
            if len(children) > 3:
                print(f"    ... and {len(children) - 3} more")
        
        # Check for categories with images
        cats_with_images = Category.query.filter(
            Category.image_url.isnot(None),
            Category.image_url != ''
        ).count()
        print(f"\nCategories with images: {cats_with_images}")
        
        # Check for orphaned categories (parent_id points to non-existent parent)
        all_ids = {cat.id for cat in all_cats}
        orphaned = []
        for cat in all_cats:
            if cat.parent_id is not None and cat.parent_id not in all_ids:
                orphaned.append(cat)
        
        if orphaned:
            print(f"\nOrphaned categories (parent_id points to non-existent parent): {len(orphaned)}")
            for cat in orphaned[:5]:
                print(f"  - {cat.name_de or cat.name_en} (parent_id: {cat.parent_id})")

if __name__ == '__main__':
    analyze_categories()
