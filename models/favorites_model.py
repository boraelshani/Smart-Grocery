"""
═══════════════════════════════════════════════════════════════════════════
FAVORITES MODEL
═══════════════════════════════════════════════════════════════════════════
Purpose: Handle all favorites-related database operations using the 
normalized favorites collection.

Schema:
{
    user_email: string,
    product_id: string,
    product_name: string,
    product_image: string,
    category: string,
    added_at: datetime,
    store_id: string (optional),
    best_price: mixed (optional)
}

Indexes:
- (user_email, product_id) - unique
- (user_email, added_at) - chronological queries
- (category) - category filtering
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime
from typing import List, Optional, Dict
from bson import ObjectId

try:
    from utils.db import mongo as flask_mongo
except Exception:
    flask_mongo = None


def add_favorite(user_email: str, product_id: str, product_data: dict) -> bool:
    """
    Add a product to user's favorites.
    
    Args:
        user_email: User's email address
        product_id: Product ID to favorite
        product_data: Dict with product info (name, image, category, etc.)
    
    Returns:
        True if added successfully, False otherwise
    """
    if not user_email or not product_id:
        return False
    
    if flask_mongo is None or getattr(flask_mongo, 'db', None) is None:
        return False
    
    try:
        favorite_doc = {
            'user_email': user_email,
            'product_id': str(product_id),
            'product_name': product_data.get('name', ''),
            'product_image': product_data.get('image', ''),
            'category': product_data.get('category', ''),
            'added_at': datetime.utcnow(),
            'best_price': product_data.get('best_price')
        }
        
        # Use upsert to avoid duplicates (relies on unique index)
        result = flask_mongo.db.favorites.update_one(
            {'user_email': user_email, 'product_id': str(product_id)},
            {'$setOnInsert': favorite_doc},
            upsert=True
        )
        
        return result.upserted_id is not None or result.matched_count > 0
        
    except Exception as e:
        print(f'ERROR adding favorite: {e}')
        return False


def remove_favorite(user_email: str, product_id: str) -> bool:
    """
    Remove a product from user's favorites.
    
    Args:
        user_email: User's email address
        product_id: Product ID to unfavorite
    
    Returns:
        True if removed successfully, False otherwise
    """
    if not user_email or not product_id:
        return False
    
    if flask_mongo is None or getattr(flask_mongo, 'db', None) is None:
        return False
    
    try:
        result = flask_mongo.db.favorites.delete_one({
            'user_email': user_email,
            'product_id': str(product_id)
        })
        
        return result.deleted_count > 0
        
    except Exception as e:
        print(f'ERROR removing favorite: {e}')
        return False


def is_favorited(user_email: str, product_id: str) -> bool:
    """
    Check if a product is in user's favorites.
    
    Args:
        user_email: User's email address
        product_id: Product ID to check
    
    Returns:
        True if favorited, False otherwise
    """
    if not user_email or not product_id:
        return False
    
    if flask_mongo is None or getattr(flask_mongo, 'db', None) is None:
        return False
    
    try:
        count = flask_mongo.db.favorites.count_documents({
            'user_email': user_email,
            'product_id': str(product_id)
        })
        
        return count > 0
        
    except Exception as e:
        print(f'ERROR checking favorite: {e}')
        return False


def get_user_favorites(user_email: str, category: Optional[str] = None, limit: int = 100) -> List[Dict]:
    """
    Get all favorites for a user.
    
    Args:
        user_email: User's email address
        category: Optional category filter
        limit: Maximum number of favorites to return
    
    Returns:
        List of favorite documents
    """
    if not user_email:
        return []
    
    if flask_mongo is None or getattr(flask_mongo, 'db', None) is None:
        return []
    
    try:
        query = {'user_email': user_email}
        if category:
            query['category'] = category
        
        cursor = flask_mongo.db.favorites.find(query).sort('added_at', -1).limit(limit)
        favorites = list(cursor)
        
        # Convert ObjectId to string for JSON serialization
        for fav in favorites:
            if '_id' in fav:
                fav['id'] = str(fav['_id'])
                del fav['_id']
        
        return favorites
        
    except Exception as e:
        print(f'ERROR getting favorites: {e}')
        return []


def get_favorites_count(user_email: str) -> int:
    """
    Get the count of favorites for a user.
    
    Args:
        user_email: User's email address
    
    Returns:
        Number of favorites
    """
    if not user_email:
        return 0
    
    if flask_mongo is None or getattr(flask_mongo, 'db', None) is None:
        return 0
    
    try:
        return flask_mongo.db.favorites.count_documents({'user_email': user_email})
        
    except Exception as e:
        print(f'ERROR counting favorites: {e}')
        return 0


def get_favorite_product_ids(user_email: str) -> List[str]:
    """
    Get list of product IDs that user has favorited.
    Useful for bulk operations and filtering.
    
    Args:
        user_email: User's email address
    
    Returns:
        List of product ID strings
    """
    if not user_email:
        return []
    
    if flask_mongo is None or getattr(flask_mongo, 'db', None) is None:
        return []
    
    try:
        cursor = flask_mongo.db.favorites.find(
            {'user_email': user_email},
            {'product_id': 1}
        )
        
        return [fav['product_id'] for fav in cursor if 'product_id' in fav]
        
    except Exception as e:
        print(f'ERROR getting favorite IDs: {e}')
        return []


def clear_user_favorites(user_email: str) -> bool:
    """
    Remove all favorites for a user.
    
    Args:
        user_email: User's email address
    
    Returns:
        True if cleared successfully, False otherwise
    """
    if not user_email:
        return False
    
    if flask_mongo is None or getattr(flask_mongo, 'db', None) is None:
        return False
    
    try:
        result = flask_mongo.db.favorites.delete_many({'user_email': user_email})
        print(f'Cleared {result.deleted_count} favorites for user {user_email}')
        return True
        
    except Exception as e:
        print(f'ERROR clearing favorites: {e}')
        return False
