"""
═══════════════════════════════════════════════════════════════════════════
STORES MODEL - Database Operations for Store Information
═══════════════════════════════════════════════════════════════════════════
Purpose: Handle all store database queries and operations
Database Collection: 'stores' in MongoDB

Functionality:
- Retrieve store details (name, location, hours)
- List all available stores
- Store management (CRUD for Admins)
═══════════════════════════════════════════════════════════════════════════
"""
from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv
from typing import List, Optional
import certifi

load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY: INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════

class StoresModel:
    def __init__(self):
        """
        Initialize the StoresModel.
        
        Connection Strategy:
        We lazy-load the 'get_db' import inside method calls or init to avoid 
        circular dependency issues if 'utils.db' imports models elsewhere.
        """
        # Use centralized database connection logic
        from utils.db import get_db
        self.db = get_db()
        self._client = None


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: LIST OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    def list_stores(self) -> List[dict]:
        """
        Get a list of all stores in the database.
        
        Usage:
        - Populating the "All Stores" page.
        - Dropdown menus for filtering by store.
        - Comparison logic to see where products are sold.
        
        Returns:
            List[dict]: List of store documents, with '_id' converted to string 'id'.
        """
        # 1. QUERY DATABASE
        # Fetch all documents from the 'stores' collection
        docs = list(self.db.stores.find({}))
        
        # 2. DATA NORMALIZATION
        # Iterating over results to make them JSON-friendly
        for d in docs:
            # Convert ObjectId to string for URLs/Frontend (e.g. /store/<id>)
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs

    def get_store_count(self) -> int:
        """
        Count total stores.
        
        Performance:
        Uses count_documents({}) which is optimized in MongoDB to just read logic metadata 
        rather than scanning every document (exact count).
        """
        return self.db.stores.count_documents({})


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: READ OPERATIONS (SINGLE STORE)
    # ═══════════════════════════════════════════════════════════════════════════

    def get_store_by_name(self, name: str) -> Optional[dict]:
        """
        Lookup a store by its exact name.
        
        Case Sensitivity:
        This performs an exact match. If you need "Costco" to match "costco",
        use a regex query or normalized search elsewhere.
        """
        if not name:
            return None
            
        # Find single document where 'name' field equals argument
        doc = self.db.stores.find_one({'name': name})
        
        if not doc:
            return None
            
        # Add friendly ID
        if '_id' in doc:
            doc['id'] = str(doc['_id'])
        return doc

    def get_store_by_id(self, id_str: str) -> Optional[dict]:
        """
        Get a single store by its MongoDB ObjectId.
        
        Error Handling:
        Catches invalid ID strings (e.g. "abc") which would crash ObjectId() constructor.
        """
        try:
            # Look up by primary key (_id)
            doc = self.db.stores.find_one({'_id': ObjectId(id_str)})
            if not doc:
                return None
                
            # Normalize
            doc['id'] = str(doc['_id'])
            return doc
        except Exception:
            # Return None if ID format is invalid or DB error occurs
            return None


    # ═══════════════════════════════════════════════════════════════════════════
    # CATEGORY: ADMIN OPERATIONS (C.U.D)
    # ═══════════════════════════════════════════════════════════════════════════

    def insert_store(self, doc: dict) -> str:
        """
        Create a new store document in the database.
        
        Access Control:
        Routes calling this should ensure the user is an Admin.
        
        Returns:
            str: The auto-generated ObjectId of the new store.
        """
        # insert_one() returns an InsertOneResult object
        res = self.db.stores.insert_one(doc)
        return str(res.inserted_id)

    def update_store(self, id_str: str, update_doc: dict) -> bool:
        """
        Update existing store details (name, location, logo).
        
        Args:
            id_str: The ID of store to update.
            update_doc: Dictionary of fields to change.
            
        Returns:
            bool: True if modification was successful.
        """
        try:
            # Safety Check: Prevent accidental overwriting of the immutable _id
            # if passed by mistake in the form data.
            update_doc.pop('_id', None)
            
            # Use $set operator to only update specified fields, leaving others touched
            res = self.db.stores.update_one({'_id': ObjectId(id_str)}, {'$set': update_doc})
            
            # Check modified_count to confirm a change actually happened
            return getattr(res, 'modified_count', 0) > 0
        except Exception:
            return False

    def delete_store(self, id_str: str) -> bool:
        """
        Delete a store permanently from the system.
        
        Warning: 
        This does NOT cascade delete products associated with this store!
        Products referring to this store might have broken links.
        """
        try:
            res = self.db.stores.delete_one({'_id': ObjectId(id_str)})
            return getattr(res, 'deleted_count', 0) > 0
        except Exception:
            return False

    def close_connection(self):
        if self._client:
            self._client.close()


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY: MODULE EXPORTS (SINGLETON & HELPERS)
# ═══════════════════════════════════════════════════════════════════════════

# Singleton Instance to be imported by routes
stores_model = StoresModel()

# Wrapper functions for older code references
# These provide backwards compatibility if older routes import functions directly
def list_stores() -> List[dict]:
    return stores_model.list_stores()

def get_store_by_name(name: str) -> Optional[dict]:
    return stores_model.get_store_by_name(name)

def get_store_count() -> int:
    return stores_model.get_store_count()

def insert_store(doc: dict):
    return stores_model.insert_store(doc)
