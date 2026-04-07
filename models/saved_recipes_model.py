from utils.db import mongo
from bson import ObjectId
from datetime import datetime
import json

def get_saved_recipes(user_email):
    """Retrieve all saved recipes for a user."""
    try:
        recipes = list(mongo.db.saved_recipes.find({"user_email": user_email}).sort("created_at", -1))
        # Convert ObjectIds to strings
        for r in recipes:
            r['_id'] = str(r['_id'])
            if 'created_at' in r and isinstance(r['created_at'], datetime):
                r['created_at'] = r['created_at'].isoformat()
        return recipes
    except Exception as e:
        print(f"Error fetching saved recipes: {e}")
        return []

def save_recipe(user_email, recipe_data):
    """Save a generated recipe for a user."""
    try:
        recipe_doc = {
            "user_email": user_email,
            "title": recipe_data.get('recipe', 'Untitled Recipe'),
            "ingredients": recipe_data.get('results', []),
            "instructions": recipe_data.get('instructions', []),
            "total_items": recipe_data.get('total_items', 0),
            "matched_items": recipe_data.get('matched_items', 0),
            "total_price": recipe_data.get('total_price', 0),
            "created_at": datetime.utcnow()
        }
        result = mongo.db.saved_recipes.insert_one(recipe_doc)
        recipe_doc['_id'] = str(result.inserted_id)
        recipe_doc['created_at'] = recipe_doc['created_at'].isoformat()
        return True, recipe_doc
    except Exception as e:
        print(f"Error saving recipe: {e}")
        return False, str(e)

def delete_recipe(user_email, recipe_id):
    """Delete a saved recipe."""
    try:
        result = mongo.db.saved_recipes.delete_one({"_id": ObjectId(recipe_id), "user_email": user_email})
        return result.deleted_count > 0, ""
    except Exception as e:
        print(f"Error deleting recipe: {e}")
        return False, str(e)
