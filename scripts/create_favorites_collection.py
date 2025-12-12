"""
═══════════════════════════════════════════════════════════════════════════
CREATE FAVORITES COLLECTION
═══════════════════════════════════════════════════════════════════════════
Purpose: Create a normalized favorites collection and migrate existing data
from users.favorites to the new collection.

Schema:
{
    user_email: string,
    product_id: string,
    product_name: string,
    product_image: string,
    category: string,
    added_at: datetime,
    store_id: string (optional, for store-specific favorites)
}

Indexes:
- (user_email, product_id) - unique compound index for fast lookups
- (user_email, added_at) - for chronological queries
- (category) - for filtering by category

Usage:
    python scripts/create_favorites_collection.py
    
Options:
    --migrate-data    Migrate existing favorites from users collection
    --dry-run        Preview changes without applying them
═══════════════════════════════════════════════════════════════════════════
"""

from pymongo import MongoClient
from datetime import datetime
import os
import sys
from dotenv import load_dotenv
import certifi

load_dotenv()


def create_favorites_collection(migrate_data=False, dry_run=False):
    """
    Create the favorites collection with proper schema and indexes.
    
    Args:
        migrate_data: If True, migrate existing favorites from users collection
        dry_run: If True, print what would happen without making changes
    """
    
    # Connect to MongoDB
    mongo_uri = os.environ.get('MONGO_URI')
    if not mongo_uri:
        print('ERROR: MONGO_URI not found in environment variables')
        return False
    
    try:
        if mongo_uri.startswith('mongodb+srv://'):
            client = MongoClient(mongo_uri, tls=True, tlsCAFile=certifi.where())
        else:
            client = MongoClient(mongo_uri)
        
        db_name = os.environ.get('MONGO_DBNAME', 'smart_grocery')
        db = client[db_name]
        
        print(f'✓ Connected to MongoDB database: {db_name}')
        
        # Check if collection already exists
        existing_collections = db.list_collection_names()
        if 'favorites' in existing_collections:
            print('⚠ WARNING: favorites collection already exists')
            response = input('Do you want to recreate it? This will delete all existing data. (yes/no): ')
            if response.lower() != 'yes':
                print('Aborted.')
                return False
            if not dry_run:
                db.favorites.drop()
                print('✓ Dropped existing favorites collection')
        
        # Create collection (implicitly created on first insert)
        if not dry_run:
            db.create_collection('favorites')
            print('✓ Created favorites collection')
        else:
            print('[DRY RUN] Would create favorites collection')
        
        # Create indexes
        indexes = [
            {
                'keys': [('user_email', 1), ('product_id', 1)],
                'unique': True,
                'name': 'user_product_unique'
            },
            {
                'keys': [('user_email', 1), ('added_at', -1)],
                'name': 'user_chronological'
            },
            {
                'keys': [('category', 1)],
                'name': 'category_index'
            }
        ]
        
        for idx in indexes:
            if not dry_run:
                db.favorites.create_index(idx['keys'], unique=idx.get('unique', False), name=idx['name'])
                print(f'✓ Created index: {idx["name"]}')
            else:
                print(f'[DRY RUN] Would create index: {idx["name"]}')
        
        # Migrate data from users collection
        if migrate_data:
            print('\n--- Starting data migration ---')
            users = db.users.find({'favorites': {'$exists': True, '$ne': []}})
            migrated_count = 0
            skipped_count = 0
            
            for user in users:
                user_email = user.get('email')
                favorites = user.get('favorites', [])
                
                if not user_email or not favorites:
                    continue
                
                print(f'\nMigrating favorites for user: {user_email} ({len(favorites)} items)')
                
                for fav in favorites:
                    if not isinstance(fav, dict):
                        skipped_count += 1
                        continue
                    
                    product_id = fav.get('id')
                    if not product_id:
                        skipped_count += 1
                        continue
                    
                    favorite_doc = {
                        'user_email': user_email,
                        'product_id': str(product_id),
                        'product_name': fav.get('name', ''),
                        'product_image': fav.get('image', ''),
                        'category': fav.get('category', ''),
                        'added_at': datetime.utcnow(),  # No original timestamp, use current
                        'best_price': fav.get('best_price')
                    }
                    
                    if not dry_run:
                        try:
                            db.favorites.update_one(
                                {'user_email': user_email, 'product_id': str(product_id)},
                                {'$setOnInsert': favorite_doc},
                                upsert=True
                            )
                            migrated_count += 1
                        except Exception as e:
                            print(f'  ✗ Error migrating favorite {product_id}: {e}')
                            skipped_count += 1
                    else:
                        print(f'  [DRY RUN] Would migrate: {fav.get("name", "Unknown")}')
                        migrated_count += 1
            
            print(f'\n✓ Migration complete: {migrated_count} favorites migrated, {skipped_count} skipped')
            
            if not dry_run:
                print('\nNote: Old favorites data still exists in users collection.')
                print('To remove it, run: db.users.update_many({}, {$unset: {"favorites": ""}})')
        
        print('\n✓ Favorites collection setup complete!')
        return True
        
    except Exception as e:
        print(f'✗ ERROR: {e}')
        import traceback
        traceback.print_exc()
        return False
    finally:
        if 'client' in locals():
            client.close()


if __name__ == '__main__':
    # Parse command-line arguments
    migrate = '--migrate-data' in sys.argv
    dry_run = '--dry-run' in sys.argv
    
    print('═' * 75)
    print('FAVORITES COLLECTION SETUP')
    print('═' * 75)
    
    if dry_run:
        print('⚠ DRY RUN MODE - No changes will be made\n')
    
    success = create_favorites_collection(migrate_data=migrate, dry_run=dry_run)
    
    if success:
        print('\n✓ Script completed successfully')
        if not migrate and not dry_run:
            print('\nTo migrate existing data, run:')
            print('  python scripts/create_favorites_collection.py --migrate-data')
    else:
        print('\n✗ Script failed')
        sys.exit(1)
