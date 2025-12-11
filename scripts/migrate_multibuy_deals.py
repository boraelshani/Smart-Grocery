"""
═══════════════════════════════════════════════════════════════════════════
MIGRATION SCRIPT - Migrate Multi-Buy Deals from featured_deals to multibuy_offers
═══════════════════════════════════════════════════════════════════════════
Purpose: Copy existing 2+1, BOGO, and multi-buy deals from featured_deals
to the new multibuy_offers collection

Usage:
    python scripts/migrate_multibuy_deals.py

This script:
1. Finds all deals with multibuy_buy/multibuy_free fields in featured_deals
2. Creates corresponding documents in multibuy_offers collection
3. Keeps originals in featured_deals (safe, non-destructive)
═══════════════════════════════════════════════════════════════════════════
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from bson import ObjectId

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

def migrate_multibuy_deals():
    """Migrate multi-buy deals from featured_deals to multibuy_offers"""
    
    try:
        from pymongo import MongoClient
        import certifi
        
        mongo_uri = os.getenv('MONGO_URI') or 'mongodb://localhost:27017/smart_grocery'
        
        # Remove any angle brackets if present
        if '<' in mongo_uri or '>' in mongo_uri:
            mongo_uri = mongo_uri.replace('<', '').replace('>', '')
        
        try:
            client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
        except TypeError:
            client = MongoClient(mongo_uri)
        
        db = client.get_default_database()
        if db is None:
            db = client['smart_grocery']
        
        print("✓ Connected to MongoDB")
    except Exception as e:
        print(f"✗ Failed to connect to MongoDB: {e}")
        print("  Make sure MONGO_URI is set in .env")
        return False
    
    # Check if collections exist
    if 'featured_deals' not in db.list_collection_names():
        print("✗ featured_deals collection not found")
        return False
    
    # Find all deals with multi-buy offers (stored as objects in 'offer' field)
    multibuy_deals = list(db.featured_deals.find({
        'offer': {
            '$type': 'object'
        }
    }))
    
    # Also check for legacy multibuy fields
    legacy_deals = list(db.featured_deals.find({
        '$or': [
            {'multibuy_buy': {'$exists': True, '$ne': None}},
            {'multibuy_free': {'$exists': True, '$ne': None}}
        ]
    }))
    
    # Combine and deduplicate
    all_multibuy = {str(d['_id']): d for d in (multibuy_deals + legacy_deals)}.values()
    all_multibuy = list(all_multibuy)
    
    if not all_multibuy:
        print("ℹ No multi-buy deals found in featured_deals")
        return True
    
    print(f"Found {len(all_multibuy)} multi-buy deals to migrate")
    
    migrated = 0
    skipped = 0
    
    for deal in all_multibuy:
        try:
            # Handle two offer formats: 
            # 1. New format: offer = {'type': 'buyXgetY', 'x': 2, 'y': 1}
            # 2. Legacy format: multibuy_buy and multibuy_free fields
            
            offer = deal.get('offer')
            buy_qty = None
            free_qty = None
            
            if isinstance(offer, dict) and offer.get('type') == 'buyXgetY':
                buy_qty = offer.get('x')
                free_qty = offer.get('y')
            else:
                # Try legacy format
                buy_qty = deal.get('multibuy_buy')
                free_qty = deal.get('multibuy_free')
            
            # Validate
            if not buy_qty or not free_qty:
                print(f"  ⊘ Skipped: {deal.get('title')} (invalid offer data)")
                skipped += 1
                continue
            
            # Create multibuy_offers document
            multibuy_doc = {
                'title': deal.get('title', 'Multi-Buy Deal'),
                'description': deal.get('description', ''),
                'store': deal.get('store', ''),
                'category': deal.get('category', ''),
                'image': deal.get('image', ''),
                'price': deal.get('price', 0),
                'original_price': deal.get('original_price', 0),
                'buy_quantity': int(buy_qty),
                'free_quantity': int(free_qty),
                'offer_type': f"buy{buy_qty}get{free_qty}",
                'discount_label': deal.get('discount_label', f"Buy {buy_qty} Get {free_qty} Free"),
                'active': True,
                'valid_until': deal.get('valid_until'),
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'migrated_from': str(deal.get('_id', 'unknown')),
                'source_deal': deal.get('title', '')
            }
            
            # Insert into multibuy_offers
            result = db.multibuy_offers.insert_one(multibuy_doc)
            print(f"  ✓ Migrated: {deal.get('title', 'Unknown')} (ID: {result.inserted_id})")
            migrated += 1
            
        except Exception as e:
            print(f"  ✗ Error migrating {deal.get('title', 'Unknown')}: {e}")
            skipped += 1
    
    print(f"\n{'='*70}")
    print(f"Migration Complete!")
    print(f"  ✓ Migrated: {migrated} deals")
    print(f"  ⊘ Skipped: {skipped} deals")
    print(f"{'='*70}\n")
    
    if migrated > 0:
        print("Next steps:")
        print("1. Test the multi-buy deals in your shopping list")
        print("2. Update your featured_deals page to use multibuy_offers collection")
        print("3. Optional: Remove old multi-buy deals from featured_deals")
        print("\nTo verify the migration, check MongoDB:")
        print("  db.multibuy_offers.find()")
        return True
    
    return False


if __name__ == '__main__':
    success = migrate_multibuy_deals()
    sys.exit(0 if success else 1)
