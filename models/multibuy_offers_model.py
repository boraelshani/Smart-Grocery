"""
MULTI-BUY OFFERS MODEL — PostgreSQL / SQLAlchemy
No promotion_type column exists in Neon — returns empty lists safely.
"""
from __future__ import annotations
from typing import List, Optional


class MultibuyOffersModel:

    def list_active_offers(self) -> List[dict]:
        return []

    def get_offers_count(self) -> int:
        return 0

    def get_latest_offers(self, limit: int = 5) -> List[dict]:
        return []

    def get_offer_by_id(self, offer_id: str) -> Optional[dict]:
        return None

    def get_offers_by_product(self, product_id: str) -> List[dict]:
        return []

    def attach_offers_to_products(self, products: List[dict]) -> List[dict]:
        return products


multibuy_offers_model = MultibuyOffersModel()
