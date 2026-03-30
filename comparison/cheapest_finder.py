from __future__ import annotations

from typing import Any, Dict, Optional

from .price_normalizer import to_float
from .store_matcher import normalize_store_entry


def get_cheapest_from_product(product: Dict[str, Any]) -> Dict[str, Any]:
    """Prefer product.cheapest, then fallback to stores minimum, then product.price."""
    if not isinstance(product, dict):
        return {}

    cheapest = product.get('cheapest') if isinstance(product.get('cheapest'), dict) else {}
    price = to_float(cheapest.get('price')) if cheapest else None
    if price is not None:
        return {
            'store': str(cheapest.get('store') or cheapest.get('name') or '').strip(),
            'price': price,
            'raw_price': cheapest.get('price'),
            'normalized_unit_price': to_float(cheapest.get('normalized_unit_price') or cheapest.get('unit_price') or cheapest.get('price_per_unit')),
            'normalized_unit_label': cheapest.get('normalized_unit_label') or cheapest.get('unit_label'),
            'updated': cheapest.get('updated') or product.get('updated_at') or product.get('price_confirmed_at'),
        }

    stores = product.get('stores') if isinstance(product.get('stores'), list) else []
    best: Optional[Dict[str, Any]] = None
    for store_entry in stores:
        node = normalize_store_entry(store_entry)
        p = node.get('price')
        if p is None:
            continue
        if best is None or p < best.get('price', float('inf')):
            best = node

    if best:
        return {
            'store': best.get('store', ''),
            'price': best.get('price'),
            'raw_price': best.get('raw_price'),
            'normalized_unit_price': best.get('normalized_unit_price'),
            'normalized_unit_label': best.get('normalized_unit_label'),
            'updated': product.get('updated_at') or product.get('price_confirmed_at'),
        }

    fallback = to_float(product.get('price'))
    if fallback is None:
        return {}
    return {
        'store': '',
        'price': fallback,
        'raw_price': product.get('price'),
        'updated': product.get('updated_at') or product.get('price_confirmed_at'),
    }
