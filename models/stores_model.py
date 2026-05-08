"""
═══════════════════════════════════════════════════════════════════════════
STORES MODEL — PostgreSQL / SQLAlchemy
═══════════════════════════════════════════════════════════════════════════
"""

from models.postgres_models import db, Store


class StoresModel:
    def list_stores(self, limit=500):
        """Return all stores as dicts."""
        rows = Store.query.order_by(Store.name).limit(limit).all()
        return [s.to_dict() for s in rows]

    def get_store_by_id(self, store_id):
        row = Store.query.filter_by(store_id=str(store_id)).first()
        return row.to_dict() if row else None

    def get_store_by_name(self, name):
        if not name:
            return None
        row = Store.query.filter(Store.name.ilike(name.strip())).first()
        return row.to_dict() if row else None

    def count_stores(self):
        return Store.query.count()


stores_model = StoresModel()
