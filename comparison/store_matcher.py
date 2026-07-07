from __future__ import annotations

import re
from typing import Any, Dict, Iterable

from .price_normalizer import to_float


def normalize_store_name(entry: Dict[str, Any]) -> str:
    return str(entry.get('store') or entry.get('name') or entry.get('store_name') or '').strip()


def canonical_store_key(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', (name or '').strip().lower())


def normalize_store_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(entry, dict):
        return {}

    name = normalize_store_name(entry)
    unit_price = to_float(
        entry.get('normalized_unit_price')
        or entry.get('unit_price')
        or entry.get('price_per_unit')
    )

    out = {
        'store': name,
        'name': name,
        'price': to_float(entry.get('price')),
        'raw_price': entry.get('price'),
        'url': entry.get('url'),
        'image': entry.get('image'),
        'logo': entry.get('logo'),
        'store_image': entry.get('store_image') or entry.get('store_display_image'),
        'offer': entry.get('offer'),
        'has_deal': entry.get('has_deal'),
        'original_price': entry.get('original_price'),
        'discount_percent': entry.get('discount_percent'),
        'discount_label': entry.get('discount_label'),
        'store_product_name': entry.get('store_product_name'),
        'store_size': entry.get('store_size'),
        'valid_until': entry.get('valid_until'),
        'deal_info': entry.get('deal_info'),
        'unit_price': unit_price,
        'unit_price_unit': entry.get('unit_price_unit') or entry.get('normalized_unit_label') or entry.get('unit_label'),
        'last_seen': entry.get('last_seen'),
    }
    if unit_price is not None:
        out['normalized_unit_price'] = unit_price
    if entry.get('normalized_unit_label') or entry.get('unit_label'):
        out['normalized_unit_label'] = entry.get('normalized_unit_label') or entry.get('unit_label')
    return out


def build_store_meta_map(stores: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for s in stores or []:
        if not isinstance(s, dict):
            continue
        names = [
            str(s.get('name') or '').strip(),
            str(s.get('store') or '').strip(),
        ]
        names = [n for n in names if n]
        if not names:
            continue
        meta = {
            'logo': s.get('logo'),
            'image': s.get('image') or s.get('store_image'),
            'store_image': s.get('store_image'),
        }
        for name in names:
            out[name.lower()] = meta
            canonical = canonical_store_key(name)
            if canonical:
                out[canonical] = meta
    return out


def resolve_store_meta(store_meta_map: Dict[str, Dict[str, Any]], store_name: str) -> Dict[str, Any]:
    if not store_meta_map:
        return {}

    raw = (store_name or '').strip()
    if not raw:
        return {}

    direct = store_meta_map.get(raw.lower())
    if direct:
        return direct

    canonical = canonical_store_key(raw)
    if canonical and canonical in store_meta_map:
        return store_meta_map[canonical]

    # Last resort: fuzzy canonical overlap for minor naming variants.
    if canonical:
        for key, meta in store_meta_map.items():
            c_key = canonical_store_key(key)
            if not c_key:
                continue
            if canonical == c_key or canonical in c_key or c_key in canonical:
                return meta

    return {}
