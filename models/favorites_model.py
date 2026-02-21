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


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY: INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════

class FavoritesModel:
    def __init__(self):
        """
        Initialize the Favorites Model.
        
        Dependency Injection:
        We import 'get_db' inside the method or init to avoid circular imports.
        This function returns the active PyMongo database instance.
        """
        # Load the database connection helper
        from utils.db import get_db
        # Store the database instance for methods to use
        self.db = get_db()


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: CREATE OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    def add_favorite(self, user_email: str, product_id: str, product_data: dict) -> bool:
        """
        Add a product to user's favorites list.
        
        Mechanism:
        - Uses update_one with upsert=True.
        - Why? It's atomic. It either inserts a new doc or updates an existing one (no-op).
        - Prevents "Duplicate Key" errors if the user clicks 'Heart' twice quickly.
        """
        # 1. Validation Check: Ensure we have necessary identifiers
        if not user_email or not product_id or self.db is None:
            return False
        
        try:
            # 2. Prepare Snapshot Data
            # We copy key product details into the favorite record.
            # This allows us to show the favorites list WITHOUT joining the Products table.
            favorite_doc = {
                'user_email': user_email,                # The owner of the favorite
                'product_id': str(product_id),           # Link to original product
                'product_name': product_data.get('name', ''), # Snapshot name
                'product_image': product_data.get('image', ''), # Snapshot image
                'category': product_data.get('category', ''),   # Snapshot category
                'added_at': datetime.utcnow(),           # Timestamp for sorting
                'best_price': product_data.get('best_price'), # Last known price
                'store': product_data.get('store', ''),  # Store info
                'discount_tiers': product_data.get('discount_tiers'), # Discount info
                'offer': product_data.get('offer')       # Offer info
            }
            
            # 3. Perform Database Upsert
            # Filter: Find doc with matching user AND product
            # Update: If inserting, set the favorite_doc. If existing, do nothing (atomic).
            result = self.db.favorites.update_one(
                {'user_email': user_email, 'product_id': str(product_id)},
                {'$setOnInsert': favorite_doc}, # '$setOnInsert' only writes on creation
                upsert=True # Create if not exists
            )
            
            # 4. Return Success Status
            # Success if we created a new doc OR found an existing one
            return result.upserted_id is not None or result.matched_count > 0
            
        except Exception as e:
            # Log error if database operation fails
            print(f'ERROR adding favorite: {e}')
            return False


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: DELETE OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    def remove_favorite(self, user_email: str, product_id: str) -> bool:
        """Remove a product from favorites."""
        # 1. Validation Check
        if not user_email or not product_id or self.db is None:
            return False
        
        try:
            # 2. Execute Delete
            # Remove the document that matches BOTH user and product
            result = self.db.favorites.delete_one({
                'user_email': user_email,
                'product_id': str(product_id)
            })
            
            # 3. Check Result
            # True if at least one document was actually deleted
            return result.deleted_count > 0
        except Exception as e:
            print(f'ERROR removing favorite: {e}')
            return False


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: READ/QUERY OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    def is_favorited(self, user_email: str, product_id: str) -> bool:
        """
        Check if a specific product is in the user's favorites.
        Returns: True/False directly for UI toggles (e.g. Red/Grey heart).
        """
        if not user_email or not product_id or self.db is None:
            return False
        
        try:
            # 1. Count Documents
            # Efficient check: 'count_documents' is faster than fetching the whole doc.
            count = self.db.favorites.count_documents({
                'user_email': user_email,
                'product_id': str(product_id)
            })
            
            # 2. Return Boolean
            return count > 0
        except Exception:
            return False

    def get_user_favorites(self, user_email: str) -> List[dict]:
        """
        Retrieve all favorites for a specific user.
        Sorts by most recently added.
        """
        if not user_email or self.db is None:
            return []
            
        try:
            # 1. Fetch from Database
            # Find all docs for this email, sorted by time (descending)
            cursor = self.db.favorites.find({'user_email': user_email}).sort('added_at', -1)
            
            # 2. Convert to List
            favorites = list(cursor)
            
            # 3. Normalize Data
            for fav in favorites:
                # Ensure '_id' is converted to a string 'id' for JSON serialization
                if '_id' in fav:
                    fav['id'] = str(fav['_id'])
            
            return favorites
        except Exception as e:
            print(f'ERROR fetching favorites: {e}')
            return []


    def is_favorited(self, user_email: str, product_id: str) -> bool:
        """
        Check if a product is in the user's favorites list.
        """
        if not user_email or not product_id or self.db is None:
            return False
            
        try:
            count = self.db.favorites.count_documents({
                'user_email': user_email,
                'product_id': str(product_id)
            })
            return count > 0
        except Exception as e:
            print(f'ERROR checking is_favorited: {e}')
            return False


# Initialize the singleton instance
favorites_model = FavoritesModel()

# Module-level aliases for backward compatibility
def get_user_favorites(user_email):
    return favorites_model.get_user_favorites(user_email)

def is_favorited(user_email, product_id):
    return favorites_model.is_favorited(user_email, product_id)

def add_favorite(user_email, product_id, product_data):
    return favorites_model.add_favorite(user_email, product_id, product_data)
