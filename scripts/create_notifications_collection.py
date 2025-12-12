"""
═══════════════════════════════════════════════════════════════════════════
CREATE NOTIFICATIONS COLLECTION
═══════════════════════════════════════════════════════════════════════════
Purpose: Create the notifications collection with proper schema and indexes
for storing user notifications about new deals, price drops, and system messages.

Schema:
{
    user_email: string,
    type: string,              // 'new_deal', 'deal_alert', 'price_drop', 'system'
    title: string,             // Notification title
    message: string,           // Notification message
    deal_id: string,           // Related deal ID (optional)
    product_id: ObjectId,      // Related product ID (optional)
    store_name: string,        // Store name (optional)
    action_url: string,        // Link to relevant page (optional)
    priority: string,          // 'low', 'normal', 'high'
    metadata: object,          // Additional data
    created_at: datetime,      // When notification was created
    read: boolean,             // Whether user has read it
    read_at: datetime          // When notification was read (optional)
}

Indexes:
- (user_email, read, -created_at) - fetch unread notifications efficiently
- (user_email, -created_at) - chronological queries
- (created_at) - cleanup old notifications
- (type, created_at) - filter by notification type

Usage:
    python scripts/create_notifications_collection.py
    
Options:
    --drop-existing   Drop existing collection and recreate
    --dry-run        Preview changes without applying them
═══════════════════════════════════════════════════════════════════════════
"""

from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime
import os
import sys
from dotenv import load_dotenv
import certifi

load_dotenv()


def create_notifications_collection(drop_existing=False, dry_run=False):
    """
    Create the notifications collection with proper schema and indexes.
    
    Args:
        drop_existing: If True, drop existing collection and recreate
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
        if 'notifications' in existing_collections:
            if drop_existing:
                print('⚠ WARNING: notifications collection already exists')
                response = input('Do you want to drop and recreate it? This will delete all data. (yes/no): ')
                if response.lower() != 'yes':
                    print('Aborted.')
                    return False
                if not dry_run:
                    db.notifications.drop()
                    print('✓ Dropped existing notifications collection')
                else:
                    print('[DRY RUN] Would drop existing notifications collection')
            else:
                print('ℹ Notifications collection already exists. Adding/updating indexes only.')
        
        # Create collection (implicitly created on first insert or when creating indexes)
        if 'notifications' not in existing_collections:
            if not dry_run:
                # Insert a dummy document to create collection, then remove it
                dummy_id = db.notifications.insert_one({
                    'user_email': 'dummy@example.com',
                    'type': 'system',
                    'title': 'Setup',
                    'message': 'Collection created',
                    'created_at': datetime.utcnow(),
                    'read': True
                }).inserted_id
                db.notifications.delete_one({'_id': dummy_id})
                print('✓ Created notifications collection')
            else:
                print('[DRY RUN] Would create notifications collection')
        
        # Create indexes
        indexes = [
            {
                'keys': [('user_email', ASCENDING), ('read', ASCENDING), ('created_at', DESCENDING)],
                'name': 'user_unread_chronological',
                'description': 'Efficient lookup for unread notifications'
            },
            {
                'keys': [('user_email', ASCENDING), ('created_at', DESCENDING)],
                'name': 'user_chronological',
                'description': 'All notifications for a user ordered by date'
            },
            {
                'keys': [('created_at', ASCENDING)],
                'name': 'created_at_asc',
                'description': 'Cleanup old notifications efficiently'
            },
            {
                'keys': [('type', ASCENDING), ('created_at', DESCENDING)],
                'name': 'type_chronological',
                'description': 'Filter notifications by type'
            }
        ]
        
        print('\n--- Creating Indexes ---')
        for idx in indexes:
            if not dry_run:
                try:
                    db.notifications.create_index(idx['keys'], name=idx['name'])
                    print(f'✓ Created index: {idx["name"]} - {idx["description"]}')
                except Exception as e:
                    # Index might already exist
                    if 'already exists' in str(e):
                        print(f'ℹ Index already exists: {idx["name"]}')
                    else:
                        print(f'✗ Error creating index {idx["name"]}: {e}')
            else:
                print(f'[DRY RUN] Would create index: {idx["name"]} - {idx["description"]}')
        
        # Print collection stats
        if not dry_run and 'notifications' in db.list_collection_names():
            count = db.notifications.count_documents({})
            print(f'\n✓ Notifications collection ready with {count} documents')
            
            # Show index info
            indexes_info = list(db.notifications.list_indexes())
            print(f'✓ Total indexes: {len(indexes_info)}')
            for idx in indexes_info:
                print(f'  - {idx.get("name", "unknown")}: {idx.get("key", {})}')
        
        print('\n✓ Notifications collection setup complete!')
        
        # Show example usage
        print('\n═══════════════════════════════════════════════════════════════════════')
        print('EXAMPLE USAGE')
        print('═══════════════════════════════════════════════════════════════════════')
        print('''
from models.notifications_model import create_notification

# Create a new deal notification
create_notification({
    'user_email': 'user@example.com',
    'type': 'new_deal',
    'title': 'New Deal Available!',
    'message': 'Fresh Milk 50% off at Tesco',
    'deal_id': '507f1f77bcf86cd799439011',
    'store_name': 'Tesco',
    'action_url': '/featured-deals',
    'priority': 'normal'
})

# Get unread notifications
from models.notifications_model import get_user_notifications
notifications = get_user_notifications('user@example.com', unread_only=True)

# Mark as read
from models.notifications_model import mark_as_read
mark_as_read(notification_id, 'user@example.com')
''')
        
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
    drop_existing = '--drop-existing' in sys.argv
    dry_run = '--dry-run' in sys.argv
    
    print('═' * 75)
    print('NOTIFICATIONS COLLECTION SETUP')
    print('═' * 75)
    
    if dry_run:
        print('⚠ DRY RUN MODE - No changes will be made\n')
    
    success = create_notifications_collection(drop_existing=drop_existing, dry_run=dry_run)
    
    if success:
        print('\n✓ Script completed successfully')
        print('\nNext steps:')
        print('1. Notifications collection is ready for use')
        print('2. Use models/notifications_model.py to create/manage notifications')
        print('3. Add notification fetching to your routes')
    else:
        print('\n✗ Script failed')
        sys.exit(1)
