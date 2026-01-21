"""
═══════════════════════════════════════════════════════════════════════════
FAVORITES MODEL - User Wishlist Management
═══════════════════════════════════════════════════════════════════════════
Purpose: Manages the 'favorites' collection where users save products.
Database Collection: 'favorites' in MongoDB

Schema Design:
- Uses a normalized reference to products (storing snapshots of product data).
- Key Fields: `user_email`, `product_id`, `product_name`, `added_at`.

Data Integrity:
- `upsert=True` prevents duplicate entries for the same user/product pair.
- Includes snapshot data (name, image) to display favorites even if the
  original product is temporarily unavailable or slow to fetch.

Performance:
- Indexed by `user_email` for fast retrieval of a user's list.
- Indexed by Compound `(user_email, product_id)` for O(1) existence checks.
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime
from typing import List, Optional, Dict
from bson import ObjectId


class FavoritesModel:
    def __init__(self):
        # Database dependency injection
        from utils.db import get_db
        self.db = get_db()

    def add_favorite(self, user_email: str, product_id: str, product_data: dict) -> bool:
        """
        Add a product to user's favorites list.
        
        Mechanism:
        - Uses update_one with upsert=True.
        - Why? It's atomic. It either inserts a new doc or updates an existing one (no-op).
        - Prevents "Duplicate Key" errors if the user clicks 'Heart' twice quickly.
        """
        if not user_email or not product_id or self.db is None:
            return False
        
        try:
            # Create a snapshot of the product data
            # This allows rendering the favorites page quickly without joining the products collection
            favorite_doc = {
                'user_email': user_email,
                'product_id': str(product_id),
                'product_name': product_data.get('name', ''),
                'product_image': product_data.get('image', ''),
                'category': product_data.get('category', ''),
                'added_at': datetime.utcnow(),
                'best_price': product_data.get('best_price'),
                'store': product_data.get('store', ''),
                'discount_tiers': product_data.get('discount_tiers'),
                'offer': product_data.get('offer')
            }
            
            # The filter defines uniqueness: A user can favor a product only once
            result = self.db.favorites.update_one(
                {'user_email': user_email, 'product_id': str(product_id)},
                {'$setOnInsert': favorite_doc}, # Only set fields if inserting new
                upsert=True
            )
            
            return result.upserted_id is not None or result.matched_count > 0
            
        except Exception as e:
            print(f'ERROR adding favorite: {e}')
            return False

    def remove_favorite(self, user_email: str, product_id: str) -> bool:
        """Remove a product from favorites."""
        if not user_email or not product_id or self.db is None:
            return False
        
        try:
            result = self.db.favorites.delete_one({
                'user_email': user_email,
                'product_id': str(product_id)
            })
            return result.deleted_count > 0
        except Exception as e:
            print(f'ERROR removing favorite: {e}')
            return False

    def is_favorited(self, user_email: str, product_id: str) -> bool:
        """
        Check existence of a favorite.
        Returns: True/False directly for UI toggles.
        """
        if not user_email or not product_id or self.db is None:
            return False
        
        try:
            # count_documents is efficient with an index
            count = self.db.favorites.count_documents({
                'user_email': user_email,
                'product_id': str(product_id)
            })
            return count > 0
        except Exception as e:
            print(f'ERROR checking favorite: {e}')
            return False

    def get_user_favorites(self, user_email: str, category: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """
        Retrieve a user's favorite products.
        
        Args:
            category: Optional filter to show only specific types of favorites (e.g., 'Dairy').
        """
        if not user_email or self.db is None:
            return []
        
        try:
            query = {'user_email': user_email}
            if category:
                query['category'] = category
            
            # Sort by most recently added
            cursor = self.db.favorites.find(query).sort('added_at', -1).limit(limit)
            favorites = list(cursor)
            
            # Post-processing for frontend consumption
            for fav in favorites:
                # normalize ID field
                if '_id' in fav:
                    fav['id'] = fav.get('product_id', str(fav['_id']))
                    del fav['_id']
                
                # normalize duplicate fields for template compatibility
                if not fav.get('name') and fav.get('product_name'):
                    fav['name'] = fav.get('product_name')
                if not fav.get('image') and fav.get('product_image'):
                    fav['image'] = fav.get('product_image')
            
            return favorites
            
        except Exception as e:
            print(f'ERROR getting favorites: {e}')
            return []

    def get_favorites_count(self, user_email: str) -> int:
        """Quick count for badge numbers (e.g., "Favorites (5)")."""
        if not user_email or self.db is None:
            return 0
        try:
            return self.db.favorites.count_documents({'user_email': user_email})
        except Exception as e:
            print(f'ERROR counting favorites: {e}')
            return 0

    def get_favorite_product_ids(self, user_email: str) -> List[str]:
        """
        Get only IDs.
        
        Why: Useful for "Mark as Favorited" logic in product listings.
        We fetch 1000s of product IDs efficiently using a projection `{'product_id': 1}`
        to avoid transferring full documents.
        """
        if not user_email or not self.db:
            return []
        
        try:
            cursor = self.db.favorites.find(
                {'user_email': user_email},
                {'product_id': 1} # Projection: ONLY return product_id field
            )
            return [fav['product_id'] for fav in cursor if 'product_id' in fav]
        except Exception as e:
            print(f'ERROR getting favorite IDs: {e}')
            return []

    def clear_user_favorites(self, user_email: str) -> bool:
        """Delete ALL favorites for a user (e.g. Account reset)."""
        if not user_email or not self.db:
            return False
        try:
            result = self.db.favorites.delete_many({'user_email': user_email})
            return True
        except Exception as e:
            print(f'ERROR clearing favorites: {e}')
            return False


# Singleton Instance
favorites_model = FavoritesModel()

# ════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS (Wrapper for backward compatibility)
# ════════════════════════════════════════════════════════════════════════════
# These ensure that `from models.favorites_model import add_favorite` still works.

def add_favorite(user_email: str, product_id: str, product_data: dict) -> bool:
    return favorites_model.add_favorite(user_email, product_id, product_data)

def remove_favorite(user_email: str, product_id: str) -> bool:
    return favorites_model.remove_favorite(user_email, product_id)

def is_favorited(user_email: str, product_id: str) -> bool:
    return favorites_model.is_favorited(user_email, product_id)

def get_user_favorites(user_email: str, category: Optional[str] = None, limit: int = 100) -> List[Dict]:
    return favorites_model.get_user_favorites(user_email, category, limit)

def get_favorites_count(user_email: str) -> int:
    return favorites_model.get_favorites_count(user_email)

def get_favorite_product_ids(user_email: str) -> List[str]:
    return favorites_model.get_favorite_product_ids(user_email)

def clear_user_favorites(user_email: str) -> bool:
    return favorites_model.clear_user_favorites(user_email)
