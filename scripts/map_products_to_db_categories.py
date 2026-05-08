import os
import sys
import re
from pymongo import UpdateOne

# Ensure we can import from the root of the project
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from utils.db import get_db

def build_category_tree(db):
    cats = list(db.categories.find({}))
    
    cat_by_id = {}
    cat_by_oid_str = {}
    
    for c in cats:
        cat_id = c.get('categoryId') or str(c['_id'])
        cat_by_id[cat_id] = c
        cat_by_oid_str[str(c['_id'])] = c
        
    return cats, cat_by_id, cat_by_oid_str

def get_path(cat, cat_by_id, cat_by_oid_str):
    path_ids = []
    path_names = []
    
    current = cat
    while current:
        cat_id = current.get('categoryId') or str(current['_id'])
        path_ids.insert(0, cat_id)
        path_names.insert(0, current.get('name_en') or '')
        
        parent_id = current.get('parentId')
        if not parent_id or parent_id == "None" or parent_id == current.get('categoryId') or parent_id == str(current['_id']):
            break
            
        # Try finding parent by categoryId or ObjectId string
        current = cat_by_id.get(parent_id) or cat_by_oid_str.get(parent_id)
        
    return path_ids, path_names

def map_products():
    with app.app_context():
        db = get_db()
        print("Loading categories...")
        cats, cat_by_id, cat_by_oid_str = build_category_tree(db)
        
        # Identify leaves (categories with no children)
        parent_ids = {str(c.get('parentId')) for c in cats if c.get('parentId')}
        leaves = []
        for c in cats:
            cat_id = c.get('categoryId') or str(c['_id'])
            if cat_id not in parent_ids and str(c['_id']) not in parent_ids:
                leaves.append(c)
                
        print(f"Found {len(cats)} total categories, {len(leaves)} leaf categories.")
        
        # Precompute paths and basic keywords for leaves
        leaf_data = []
        for leaf in leaves:
            p_ids, p_names = get_path(leaf, cat_by_id, cat_by_oid_str)
            name = (leaf.get('name_en') or '').lower()
            # Simple keyword stemming: "Berries" -> "berr"
            keywords = [w.strip() for w in re.split(r'[^a-z0-9]', name) if len(w) > 2]
            
            # Additional heuristic: also add parent names as fallback keywords for the leaf
            if len(p_names) > 1:
                parent_name = p_names[-2].lower()
                parent_kws = [w.strip() for w in re.split(r'[^a-z0-9]', parent_name) if len(w) > 3]
                keywords.extend(parent_kws)
                
            leaf_data.append({
                'leaf': leaf,
                'path_ids': p_ids,
                'path_names': p_names,
                'keywords': keywords,
                'full_name': name
            })
            
        # Sort leaves by length of keywords (longer full names first for exact matches)
        leaf_data.sort(key=lambda x: len(x['full_name']), reverse=True)

        print("Fetching products...")
        # Get all products without category fields, or all products to reset
        products = list(db.products.find({}, {'_id': 1, 'name': 1}))
        total_products = len(products)
        print(f"Found {total_products} products to map.")
        
        updates = []
        mapped_count = 0
        unmapped_count = 0
        
        default_leaf = leaf_data[0] if leaf_data else None

        for p in products:
            p_name = (p.get('name') or '').lower()
            
            best_match = None
            
            # 1. Try exact match on category full name
            for ld in leaf_data:
                if ld['full_name'] and ld['full_name'] in p_name:
                    best_match = ld
                    break
                    
            # 2. Try keyword match
            if not best_match:
                for ld in leaf_data:
                    for kw in ld['keywords']:
                        if kw and kw in p_name:
                            # Plural/singular loose match
                            if bool(re.search(r'\b' + re.escape(kw) + r'[a-z]*\b', p_name)):
                                best_match = ld
                                break
                    if best_match:
                        break
            
            # Fallback
            if not best_match:
                best_match = default_leaf
                unmapped_count += 1
            else:
                mapped_count += 1
                
            if best_match:
                leaf_cat = best_match['leaf']
                cat_id = leaf_cat.get('categoryId') or str(leaf_cat['_id'])
                
                updates.append(UpdateOne(
                    {'_id': p['_id']},
                    {'$set': {
                        'category': best_match['path_names'][-1],
                        'categoryId': cat_id,
                        'categoryPath': best_match['path_ids'],
                        'category_path': best_match['path_names']
                    }}
                ))
                
            # Execute in batches of 5000 to save memory
            if len(updates) >= 5000:
                print(f"Executing batch update of 5000 products... ({mapped_count + unmapped_count}/{total_products})")
                db.products.bulk_write(updates)
                updates = []
                
        if updates:
            print(f"Executing final batch update of {len(updates)} products... ({mapped_count + unmapped_count}/{total_products})")
            db.products.bulk_write(updates)
            
        print(f"\nDone! Mapped {mapped_count} products via keywords. {unmapped_count} products used fallback.")

if __name__ == '__main__':
    map_products()
