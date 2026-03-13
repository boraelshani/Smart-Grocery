"""Backward-compatible exports for comparison helpers.

Canonical implementation lives in the `comparison/` package.
"""

from comparison.cheapest_finder import get_cheapest_from_product
from comparison.comparison_engine import build_best_price_summary, build_compare_product_payload
from comparison.store_matcher import build_store_meta_map, normalize_store_entry

__all__ = [
    'build_best_price_summary',
    'build_compare_product_payload',
    'build_store_meta_map',
    'get_cheapest_from_product',
    'normalize_store_entry',
]
