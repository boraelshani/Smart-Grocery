"""
QUANTITY DISCOUNTS MODEL — PostgreSQL / SQLAlchemy
No promotion_type column exists in Neon — returns empty lists safely.
"""
from __future__ import annotations
from typing import List, Optional, Dict


class QuantityDiscountsModel:

    def list_active_discounts(self) -> List[dict]:
        return []

    def get_latest_discounts(self, limit: int = 3) -> List[dict]:
        return []

    def get_discount_by_id(self, discount_id: str) -> Optional[dict]:
        return None

    def get_discount_by_product(self, product_id: str) -> Optional[dict]:
        return None

    def attach_discounts_to_products(self, products: List[dict]):
        pass

    def calculate_price_with_quantity_tiers(self, base_price: float, quantity: int,
                                           discount_tiers: List[Dict]) -> Dict:
        return {
            'total_price': round(base_price * quantity, 2),
            'effective_unit_price': base_price,
            'applied_tier': None, 'savings': 0.0, 'discount_percent': 0
        }


quantity_discounts_model = QuantityDiscountsModel()
