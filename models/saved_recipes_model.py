"""
═══════════════════════════════════════════════════════════════════════════
SAVED RECIPES MODEL — PostgreSQL / SQLAlchemy
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime, timezone
from models.postgres_models import db, SavedRecipe


def get_saved_recipes(user_email):
    """Retrieve all saved recipes for a user."""
    try:
        recipes = SavedRecipe.query.filter_by(
            user_email=user_email
        ).order_by(SavedRecipe.created_at.desc()).all()
        return [
            {
                '_id': str(r.id),
                'id': str(r.id),
                'user_email': r.user_email,
                'title': r.title,
                'ingredients': r.ingredients or [],
                'instructions': r.instructions or [],
                'total_items': r.total_items,
                'matched_items': r.matched_items,
                'total_price': r.total_price,
                'created_at': r.created_at.isoformat() if r.created_at else None,
            }
            for r in recipes
        ]
    except Exception as e:
        print(f"Error fetching saved recipes: {e}")
        return []


def save_recipe(user_email, recipe_data):
    """Save a generated recipe for a user."""
    try:
        recipe = SavedRecipe(
            user_email=user_email,
            title=recipe_data.get('recipe', 'Untitled Recipe'),
            ingredients=recipe_data.get('results', []),
            instructions=recipe_data.get('instructions', []),
            total_items=recipe_data.get('total_items', 0),
            matched_items=recipe_data.get('matched_items', 0),
            total_price=recipe_data.get('total_price', 0),
        )
        db.session.add(recipe)
        db.session.commit()

        doc = {
            '_id': str(recipe.id),
            'id': str(recipe.id),
            'title': recipe.title,
            'created_at': recipe.created_at.isoformat() if recipe.created_at else None,
        }
        return True, doc
    except Exception as e:
        db.session.rollback()
        print(f"Error saving recipe: {e}")
        return False, str(e)


def delete_recipe(user_email, recipe_id):
    """Delete a saved recipe."""
    try:
        recipe = SavedRecipe.query.filter_by(id=int(recipe_id), user_email=user_email).first()
        if not recipe:
            return False, "Not found"
        db.session.delete(recipe)
        db.session.commit()
        return True, ""
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting recipe: {e}")
        return False, str(e)
