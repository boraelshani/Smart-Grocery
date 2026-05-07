"""
═══════════════════════════════════════════════════════════════════════════
FAVORITES MODEL — PostgreSQL / SQLAlchemy
═══════════════════════════════════════════════════════════════════════════
"""

from models.postgres_models import db, Favorite
from sqlalchemy import desc


class FavoritesModel:

    def add_favorite(self, email: str, product_id: str, details: dict = None) -> bool:
        if not email or not product_id:
            return False
        existing = Favorite.query.filter_by(user_email=email, product_id=str(product_id)).first()
        if existing:
            return True  # Already favorited

        details = details or {}
        fav = Favorite(
            user_email=email,
            product_id=str(product_id),
            product_name=details.get('name') or details.get('product_name'),
            product_image=details.get('image') or details.get('product_image'),
            category=details.get('category'),
            best_price=details.get('best_price') or details.get('price'),
            store=details.get('store'),
            discount_tiers=details.get('discount_tiers'),
            offer=details.get('offer'),
        )
        db.session.add(fav)
        db.session.commit()
        return True

    def remove_favorite(self, email: str, product_id: str) -> bool:
        fav = Favorite.query.filter_by(user_email=email, product_id=str(product_id)).first()
        if not fav:
            return False
        db.session.delete(fav)
        db.session.commit()
        return True

    def is_favorited(self, email: str, product_id: str) -> bool:
        if not email or not product_id:
            return False
        return Favorite.query.filter_by(user_email=email, product_id=str(product_id)).first() is not None

    def get_user_favorites(self, email: str, limit=100):
        rows = Favorite.query.filter_by(user_email=email).order_by(desc(Favorite.added_at)).limit(limit).all()
        return [f.to_dict() for f in rows]

    def count_favorites(self, email: str) -> int:
        return Favorite.query.filter_by(user_email=email).count()


favorites_model = FavoritesModel()
