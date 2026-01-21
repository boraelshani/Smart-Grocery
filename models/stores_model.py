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


class StoresModel:
    def __init__(self):
        # Use centralized database connection logic
        from utils.db import get_db
        self.db = get_db()
        self._client = None


    def list_stores(self) -> List[dict]:
        """
        Get a list of all stores in the database.
        
        Returns:
            List[dict]: List of store documents with 'id' field added.
        """
        # GET ALL STORES: Return all stores (for /stores page)
        docs = list(self.db.stores.find({}))
        # Normalization: Add 'id' string field for easier frontend usage
        for d in docs:
            if '_id' in d:
                d['id'] = str(d['_id'])
        return docs

    def get_store_count(self) -> int:
        """Count total stores (used for stats/admin dashboard)."""
        return self.db.stores.count_documents({})

    def get_store_by_name(self, name: str) -> Optional[dict]:
        """
        Lookup a store by its exact name.
        Used for mapping product prices to store details.
        """
        if not name:
            return None
        doc = self.db.stores.find_one({'name': name})
        if not doc:
            return None
        if '_id' in doc:
            doc['id'] = str(doc['_id'])
        return doc

    def get_store_by_id(self, id_str: str) -> Optional[dict]:
        """
        Get a single store by its MongoDB ObjectId.
        """
        try:
            doc = self.db.stores.find_one({'_id': ObjectId(id_str)})
            if not doc:
                return None
            doc['id'] = str(doc['_id'])
            return doc
        except Exception:
            return None

    def insert_store(self, doc: dict) -> str:
        """Create a new store (Admin Only)."""
        res = self.db.stores.insert_one(doc)
        return str(res.inserted_id)

    def update_store(self, id_str: str, update_doc: dict) -> bool:
        """Update existing store details (Admin Only)."""
        try:
            # Safety: Prevent accidental overwriting of the immutable _id
            update_doc.pop('_id', None)
            res = self.db.stores.update_one({'_id': ObjectId(id_str)}, {'$set': update_doc})
            return getattr(res, 'modified_count', 0) > 0
        except Exception:
            return False

    def delete_store(self, id_str: str) -> bool:
        """Delete a store permanently."""
        try:
            res = self.db.stores.delete_one({'_id': ObjectId(id_str)})
            return getattr(res, 'deleted_count', 0) > 0
        except Exception:
            return False

    def close_connection(self):
        if self._client:
            self._client.close()


# Singleton Instance to be imported by routes
stores_model = StoresModel()

# Wrapper functions for older code references
def list_stores() -> List[dict]:
    return stores_model.list_stores()

def get_store_by_name(name: str) -> Optional[dict]:
    return stores_model.get_store_by_name(name)

def get_store_count() -> int:
    return stores_model.get_store_count()

def insert_store(doc: dict):
    return stores_model.insert_store(doc)

