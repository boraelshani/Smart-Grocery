"""
FEATURED DEALS MODEL — Compatibility wrapper for new normalized schema
Uses the deals_compat layer to provide the same interface as before
"""
from models.deals_compat import list_active_promotions, get_promotion_by_id


class FeaturedDealsModel:

    def list_featured_deals(self, limit=200):
        """Get all active promotional deals"""
        deals = list_active_promotions()
        return deals[:limit] if limit else deals

    def get_deals_count(self):
        """Count active promotional deals"""
        return len(list_active_promotions())

    def get_deal_by_id(self, deal_id):
        """Get a single deal by ID"""
        return get_promotion_by_id(deal_id)

    def get_latest_deals(self, limit=10):
        """Get latest promotional deals"""
        deals = list_active_promotions()
        # Sort by discount percentage (highest first)
        deals.sort(key=lambda d: d.get('discount_percent', 0), reverse=True)
        return deals[:limit] if limit else deals


featured_deals_model = FeaturedDealsModel()
