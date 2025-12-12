"""
═══════════════════════════════════════════════════════════════════════════
VERIFY MONGODB COLLECTIONS
═══════════════════════════════════════════════════════════════════════════
Check which collections exist and their document counts.
Also creates missing collections with sample data if needed.
"""

from pymongo import MongoClient
import os
from dotenv import load_dotenv
import certifi
from datetime import datetime

load_dotenv()

def verify_collections():
    # Connect to MongoDB
    mongo_uri = os.environ.get('MONGO_URI')
    if not mongo_uri:
        print('ERROR: MONGO_URI not found')
        return
    
    try:
        if mongo_uri.startswith('mongodb+srv://'):
            client = MongoClient(mongo_uri, tls=True, tlsCAFile=certifi.where())
        else:
            client = MongoClient(mongo_uri)
        
        db_name = os.environ.get('MONGO_DBNAME', 'smart_grocery')
        db = client[db_name]
        
        print('═' * 75)
        print(f'MONGODB COLLECTIONS - Database: {db_name}')
        print('═' * 75)
        
        collections = db.list_collection_names()
        print(f'\nTotal collections: {len(collections)}\n')
        
        required_collections = [
            'users',
            'products', 
            'stores',
            'featured_deals',
            'multibuy_offers',
            'quantity_discounts',
            'favorites',
            'notifications'
        ]
        
        for col in required_collections:
            if col in collections:
                count = db[col].count_documents({})
                status = '✓' if count > 0 else '○'
                print(f'{status} {col:20s} - {count} documents')
            else:
                print(f'✗ {col:20s} - MISSING')
        
        # Check for extra collections
        extra = set(collections) - set(required_collections)
        if extra:
            print(f'\nExtra collections:')
            for col in extra:
                count = db[col].count_documents({})
                print(f'  • {col} - {count} documents')
        
        # Offer to create missing collections
        missing = set(required_collections) - set(collections)
        if missing:
            print(f'\n⚠ Missing collections: {", ".join(missing)}')
            response = input('\nCreate missing collections with sample data? (yes/no): ')
            
            if response.lower() == 'yes':
                for col in missing:
                    if col == 'multibuy_offers':
                        # Create sample multibuy offer
                        db.multibuy_offers.insert_one({
                            'title': '3 for €5 Deal',
                            'store': 'SuperValu',
                            'description': 'Buy 3 get special price',
                            'quantity': 3,
                            'price': '€5.00',
                            'category': 'Beverages',
                            'created_at': datetime.utcnow()
                        })
                        print(f'✓ Created {col} with sample data')
                    
                    elif col == 'quantity_discounts':
                        # Create sample quantity discount
                        db.quantity_discounts.insert_one({
                            'title': 'Bulk Discount - Rice',
                            'store': 'Lidl',
                            'description': 'Save 20% on 5kg+ rice',
                            'min_quantity': 5,
                            'discount_percent': 20,
                            'category': 'Pantry',
                            'created_at': datetime.utcnow()
                        })
                        print(f'✓ Created {col} with sample data')
                    
                    else:
                        # Create empty collection with a dummy document then delete it
                        dummy_id = db[col].insert_one({'_temp': True}).inserted_id
                        db[col].delete_one({'_id': dummy_id})
                        print(f'✓ Created empty {col} collection')
        
        print(f'\n✓ Total collections now: {len(db.list_collection_names())}')
        
        client.close()
        
    except Exception as e:
        print(f'✗ ERROR: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    verify_collections()
