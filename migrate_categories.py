import os
import sys
from app import app
from utils.db import get_db
from bson import ObjectId

with app.app_context():
    db = get_db()
    cats = list(db.categories.find({}))
    updated = 0
    for c in cats:
        updates = {}
        if not c.get("categoryId"):
            updates["categoryId"] = str(c["_id"])
        
        if c.get("parentId") and not isinstance(c["parentId"], str):
            updates["parentId"] = str(c["parentId"])
            
        if c.get("imageUrl") and not c.get("image_url"):
            updates["image_url"] = c["imageUrl"]
            
        if updates:
            db.categories.update_one({"_id": c["_id"]}, {"$set": updates})
            updated += 1
            
    print(f"Migrated {updated} categories.")
