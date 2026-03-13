from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .cheapest_finder import get_cheapest_from_product
from .price_normalizer import to_float
from .store_matcher import normalize_store_entry, resolve_store_meta


def _confidence_from_product(product: Dict[str, Any]) -> Dict[str, Any]:
    confidence = product.get('confidence') if isinstance(product.get('confidence'), dict) else {}
    if confidence:
        return {
            'score': confidence.get('score', 0),
            'label': confidence.get('label', 'Unknown'),
            'tone': confidence.get('tone', 'secondary'),
            'freshness_text': confidence.get('freshness_text', 'Estimated'),
        }

    confirmed_at = product.get('price_confirmed_at') or product.get('updated_at')
    freshness = 'Estimated'
    try:
        if isinstance(confirmed_at, datetime):
            age = datetime.now(timezone.utc) - confirmed_at.astimezone(timezone.utc)
            hours = age.total_seconds() / 3600
            if hours <= 24:
                freshness = 'Confirmed today'
            elif hours <= 24 * 7:
                freshness = 'Confirmed this week'
    except Exception:
        pass

    return {'score': 0, 'label': 'Unknown', 'tone': 'secondary', 'freshness_text': freshness}


def build_compare_product_payload(
    product: Dict[str, Any],
    store_meta_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if not isinstance(product, dict):
        return {}

    product_id = str(product.get('id') or product.get('_id') or '')
    stores_raw = product.get('stores') if isinstance(product.get('stores'), list) else []
    stores = [normalize_store_entry(s) for s in stores_raw]

    for node in stores:
        meta = resolve_store_meta(store_meta_map or {}, node.get('store') or node.get('name') or '')
        meta_image = meta.get('image') or meta.get('store_image')
        meta_logo = meta.get('logo')

        # Prefer stores collection visuals to avoid random/broken per-product assets.
        if meta_image:
            node['store_image'] = meta_image
            node['logo'] = meta_image
        elif meta_logo and not node.get('logo'):
            node['logo'] = meta_logo

    stores = [s for s in stores if s.get('store')]
    stores.sort(key=lambda s: s.get('price') if s.get('price') is not None else float('inf'))

    cheapest = get_cheapest_from_product({**product, 'stores': stores})
    normalized_unit_price = to_float(product.get('normalized_unit_price'))
    normalized_unit_label = product.get('normalized_unit_label')
    if normalized_unit_price is None:
        normalized_unit_price = cheapest.get('normalized_unit_price')
    if not normalized_unit_label:
        normalized_unit_label = cheapest.get('normalized_unit_label')

    # Ensure fast reads can consume a complete cheapest node directly.
    cheapest_node = {
        'store': cheapest.get('store', ''),
        'price': cheapest.get('price'),
        'updated': cheapest.get('updated') or product.get('updated_at') or product.get('price_confirmed_at'),
    }

    payload = {
        'id': product_id,
        'name': product.get('name') or product.get('title') or 'Product',
        'category': product.get('category'),
        'image': product.get('image') or (product.get('images') or [None])[0],
        'stores': stores,
        'cheapest': cheapest_node,
        'price': cheapest.get('price') if cheapest else to_float(product.get('price')),
        'normalized_unit_price': normalized_unit_price,
        'normalized_unit_label': normalized_unit_label,
        'confidence': _confidence_from_product(product),
        'community_report_count': int(product.get('community_report_count') or 0),
        'combo_deal': bool(product.get('combo_deal')),
        'combo_deal_label': product.get('combo_deal_label'),
    }
    return payload


def build_best_price_summary(compare_payload: Dict[str, Any]) -> Tuple[Optional[str], List[str]]:
    stores = compare_payload.get('stores') or []
    cheapest_price = (compare_payload.get('cheapest') or {}).get('price')
    if cheapest_price is None and stores:
        cheapest_price = min((s.get('price') for s in stores if s.get('price') is not None), default=None)
    if cheapest_price is None:
        return None, []

    best_stores: List[str] = []
    for s in stores:
        if s.get('price') == cheapest_price:
            name = s.get('store') or s.get('name')
            if name:
                best_stores.append(name)
    return f"{float(cheapest_price):.2f}", best_stores
