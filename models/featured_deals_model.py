"""
FEATURED DEALS MODEL — PostgreSQL / SQLAlchemy (matches Neon schema)
"""
from models.postgres_models import db, FeaturedDeal
from sqlalchemy import desc


class FeaturedDealsModel:

    def list_featured_deals(self, limit=200):
        rows = FeaturedDeal.query.filter(
            FeaturedDeal.active == True
        ).order_by(desc(FeaturedDeal.id)).limit(limit).all()
        return [r.to_dict() for r in rows]

    def get_deals_count(self):
        return FeaturedDeal.query.filter_by(active=True).count()

    def get_deal_by_id(self, deal_id):
        if not deal_id:
            return None
        try:
            row = db.session.get(FeaturedDeal, int(deal_id))
            return row.to_dict() if row else None
        except (ValueError, TypeError):
            return None

    def get_latest_deals(self, limit=10):
        rows = FeaturedDeal.query.filter_by(
            active=True
        ).order_by(desc(FeaturedDeal.id)).limit(limit).all()
        return [r.to_dict() for r in rows]


featured_deals_model = FeaturedDealsModel()
