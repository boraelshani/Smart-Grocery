from app import app
from utils.db import get_db
import re
from datetime import datetime, timezone
from collections import Counter

# Let's read TAXONOMY and ROOTS straight from expand_category_taxonomy
from scripts.expand_category_taxonomy import TAXONOMY, _build_lookup

def main():
    db = get_db()
    lookup = _build_lookup()
    
    leaf_nodes = [node for node in TAXONOMY if node.get("parent") and node.get("keywords")]
    
    print("Categories mapped. Searching products...")
    
    products = list(db.products.find({
        'is_placeholder': {'$ne': True}, 
        '$or': [
            {'category': 'HeissePrices'}, 
            {'categoryId': 'cat_heisseprices'}, 
            {'category': None}, 
            {'category': ''},
            {'category': {'$exists': False}}
        ]
    }))
    print(f"Found {len(products)} products that need better categorization.")
    
    updated = 0
    assigned = Counter()
    
    for p in products:
        name = str(p.get('name') or p.get('title') or '').lower()
        parts = re.split(r'[^a-zäöüß0-9]+', name)
        
        best_match = None
        best_score = 0
        
        for leaf in leaf_nodes:
            score = 0
            for kw in leaf.get('keywords', []):
                kw = kw.lower()
                if kw in parts:
                    score += 2 # word start/exact match
                elif kw in name:
                    score += 1 # sub-string match
            
            if score > best_score:
                best_score = score
                best_match = leaf
                
        if best_match:
            cat_id = best_match['id']
            full_path = [cat_id] # Default to simple path if no complex taxonomy builder rebuilds it
            curr = best_match
            while curr.get('parent') and curr['parent'] in lookup:
                curr = lookup[curr['parent']]
                full_path.insert(0, curr['id'])
            
            # Since old UI relies on simple 'category' string, we should set both 'category' and 'categoryId'
            # (And maybe fallback 'category_path' which is what ui_routes used: 'category_path')
            db.products.update_one(
                {'_id': p['_id']}, 
                {'$set': {
                    'category': best_match['name_en'],
                    'categoryId': cat_id,
                    'category_path': full_path,
                }}
            )
            updated += 1
            assigned[cat_id] += 1
            
    print(f"Updated {updated} products!")
    for k, v in assigned.most_common(20):
        print(f" - {lookup[k]['name_en']} ({k}): {v}")

if __name__ == '__main__':
    main()