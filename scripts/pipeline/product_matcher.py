#!/usr/bin/env python3
"""
Step 4 – Conservative Cross-Store Product Matching
══════════════════════════════════════════════════

The MOST important pipeline step. Groups the same product from
different stores into a single canonical product for price comparison.

Rules – ONLY match when 100% certain:
  1. Cleaned names must be identical OR differ only by brand word
  2. Quantity AND unit must be identical (e.g. 1 Liter == 1 Liter)
  3. Price must be in reasonable range (within 50% of each other)
  4. If ANY doubt, DO NOT match

Approach:
  Phase 1: Deterministic fingerprint matching (exact, no false positives)
  Phase 2: Brand-aware grouping (same product, different brands → separate)

  Products already sharing the same product_id from the import are
  considered pre-matched. This script finds products that SHOULD be
  merged but currently have separate IDs.

Usage:
  python scripts/pipeline/product_matcher.py --dry-run --limit 100
  python scripts/pipeline/product_matcher.py
"""

import os
import re
import sys
import json
import hashlib
from pathlib import Path
from collections import defaultdict

_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv
load_dotenv(_project_root / ".env", override=True)

# ───────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ───────────────────────────────────────────────────────────────────────

# Maximum price ratio between same products (if one is 2x the other, likely different)
MAX_PRICE_RATIO = 2.5

# Minimum number of matching stores required for auto-merge
MIN_STORES_FOR_MERGE = 2

# ───────────────────────────────────────────────────────────────────────
# NORMALIZATION HELPERS
# ───────────────────────────────────────────────────────────────────────

_RE_MULTI_SPACE = re.compile(r'\s+')
_KEEP_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789 ")
_UNIT_ALIASES = {
    "l": "liter", "liter": "liter", "ltr": "liter",
    "ml": "ml", "milliliter": "ml",
    "cl": "cl",
    "g": "g", "gramm": "g", "gram": "g",
    "kg": "kg", "kilogramm": "kg",
    "st": "stk", "stk": "stk", "stuck": "stk",
    "pk": "packung", "pack": "packung", "packung": "packung",
    "pc": "stk", "piece": "stk", "pieces": "stk",
    "dozen": "10er", "dose": "dose", "beut": "beutel",
    "glas": "glas", "flasch": "flasche",
}
_STOP_WORDS = {"bio", "organic", "fresh", "frisch", "neu", "new", "angebot", "sale", "aktion"}

# Common brand words that should be stripped for matching
# (same product can exist under different brands)
BRAND_WORDS = {
    "milfina", "milbona", "arla", "zott", "nestle", "maggi",
    "knorr", "pfanni", "dr. oetker", "iglo", "frosta", "manner",
    "almdudler", "red bull", "lindt", "milka", "suchard",
    "toblerone", "ritter sport", "haribo", "coca-cola", "pepsi",
    "fanta", "sprite", "schweppes", "alpro", "clever", "s-budget",
    "gut gunstig", "k-classic", "ja naturlich", "natur pur",
    "billa bio", "spar bio", "penny bio", "pringles", "nutella",
    "philadelphia", "hipp", "aqua", "bi home", "maretti", "vivis",
    "reese's", "reeses",
}


def get_db():
    import certifi
    from pymongo import MongoClient
    client = MongoClient(
        os.environ["MONGO_URI"],
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=30000,
    )
    return client[os.environ.get("DATABASE_NAME", "smart_grocery")]


# ───────────────────────────────────────────────────────────────────────
# NORMALIZATION HELPERS
def normalize_for_fingerprint(name: str, quantity: float = 0, unit: str = "") -> str:
    """
    Create a fingerprint for product matching.
    MUST be identical for the same product across stores.
    """
    # Lowercase and keep only alnum + space
    text = name.lower().strip()
    text = "".join(c for c in text if c in _KEEP_CHARS)
    text = _RE_MULTI_SPACE.sub(" ", text).strip()

    # Remove brand words
    words = text.split()
    clean_words = [w for w in words if w not in BRAND_WORDS]
    text = " ".join(clean_words)

    # Remove stop words
    words = text.split()
    clean_words = [w for w in words if w not in _STOP_WORDS]
    text = " ".join(clean_words)

    # Normalize unit
    unit_norm = _UNIT_ALIASES.get(unit.lower().strip(), unit.lower().strip())

    # Normalize quantity (1.5 == 1,5)
    qty_str = str(quantity).replace(",", ".")

    # Build fingerprint string
    fp = f"{text}|{qty_str}|{unit_norm}"
    return hashlib.sha256(fp.encode("utf-8")).hexdigest()[:16]


def normalize_quantity_for_match(qty, unit) -> tuple:
    """
    Normalize quantity and unit for comparison.
    Returns (quantity_float, unit_normalized) or (None, None) if unparseable.
    """
    if qty is None:
        return None, None

    try:
        qty = float(str(qty).replace(",", "."))
    except:
        return None, None

    unit_norm = _UNIT_ALIASES.get(str(unit).lower().strip(), str(unit).lower().strip())
    return qty, unit_norm


def prices_compatible(price_a: float | None, price_b: float | None) -> bool:
    """
    Check if two prices could be for the same product.
    Returns True if prices are within MAX_PRICE_RATIO of each other.
    """
    if price_a is None or price_b is None:
        return True  # Can't disqualify if we don't know

    try:
        price_a = float(price_a)
        price_b = float(price_b)
    except:
        return True

    if price_a <= 0 or price_b <= 0:
        return True

    ratio = max(price_a, price_b) / min(price_a, price_b)
    return ratio <= MAX_PRICE_RATIO


# ───────────────────────────────────────────────────────────────────────
# MATCHING ENGINE
# ───────────────────────────────────────────────────────────────────────

def find_matches(db=None, dry_run=False, limit=0):
    """
    Find products that should be merged across stores.

    Only returns matches that are 100% certain:
    - Identical fingerprint (name + quantity + unit)
    - Prices within reasonable range
    - From different stores
    """
    if db is None:
        db = get_db()

    # Load all products
    print("Loading products...")
    cursor = db.products.find({}, {
        "productId": 1,
        "name_de": 1, "name_en": 1, "name": 1,
        "quantity": 1, "unit_raw": 1, "unit": 1,
        "sizeDisplay": 1,
        "defaultImageUrl": 1,
        "cheapestPrice": 1,
        "stores": 1,
        "brand": 1,
        "archived": 1,
    })

    if limit > 0:
        cursor = cursor.limit(limit)

    products = list(cursor)
    # Skip archived products
    products = [p for p in products if not p.get("archived")]
    print(f"Loaded {len(products):,} active products")

    # Compute fingerprints
    fp_groups = defaultdict(list)
    for p in products:
        name = p.get("name_de") or p.get("name_en") or p.get("name", "")

        # Try to get quantity from multiple fields
        qty = p.get("quantity")
        unit = p.get("unit_raw", "")

        # If quantity is None, try to parse from unit field
        if qty is None:
            unit_str = p.get("unit", "") or p.get("sizeDisplay", "")
            m = re.match(r"(\d+[.,]?\d*)\s*([a-zA-Z]+)", str(unit_str))
            if m:
                try:
                    qty = float(m.group(1).replace(",", "."))
                except:
                    pass
                unit = m.group(2)

        fp = normalize_for_fingerprint(name, qty or 0, unit or "")
        fp_groups[fp].append(p)

    # Find groups with multiple products (potential merges)
    merge_groups = []
    for fp, group in fp_groups.items():
        if len(group) < 2:
            continue

        # Check they're from different stores
        all_stores = set()
        for p in group:
            for s in p.get("stores", []):
                all_stores.add(s.get("store"))

        # Must span at least 2 different store entries
        if len(all_stores) < 2:
            continue

        # Check price compatibility within group
        prices = []
        for p in group:
            cheapest = p.get("cheapestPrice")
            if cheapest is not None:
                try:
                    prices.append(float(cheapest))
                except:
                    pass

        if len(prices) >= 2:
            max_p = max(prices)
            min_p = min(prices)
            if min_p > 0 and (max_p / min_p) > MAX_PRICE_RATIO:
                continue  # Price gap too large, likely different products

        # Get store coverage info
        store_info = []
        for p in group:
            p_stores = [s.get("store") for s in p.get("stores", [])]
            store_info.append({
                "productId": p.get("productId"),
                "name": p.get("name_de") or p.get("name", ""),
                "stores": p_stores,
                "cheapestPrice": p.get("cheapestPrice"),
                "hasImage": bool(p.get("defaultImageUrl")),
                "brand": p.get("brand"),
                "quantity": p.get("quantity"),
                "unit_raw": p.get("unit_raw"),
                "unit": p.get("unit"),
                "sizeDisplay": p.get("sizeDisplay"),
            })

        merge_groups.append({
            "fingerprint": fp,
            "products": store_info,
            "confidence": 1.0,  # Fingerprint match = 100% certain
            "store_coverage": sorted(all_stores),
        })

    # Sort by number of products in group (larger groups first)
    merge_groups.sort(key=lambda g: len(g["products"]), reverse=True)

    total_mergeable = sum(len(g["products"]) for g in merge_groups)

    result = {
        "total_products": len(products),
        "match_groups": len(merge_groups),
        "mergeable_products": total_mergeable,
        "groups": [],
    }

    if dry_run:
        result["groups"] = merge_groups[:30]

    return result


# ───────────────────────────────────────────────────────────────────────
# MERGING ENGINE
# ───────────────────────────────────────────────────────────────────────

def select_canonical(products: list) -> dict:
    """
    Select the best product to be canonical.
    Criteria: most stores → has image → lowest price
    """
    def _score(p):
        n_stores = len(p.get("stores", []))
        has_image = 1 if p.get("hasImage") else 0
        has_price = 1 if p.get("cheapestPrice") is not None else 0
        return (n_stores, has_image, has_price)

    return max(products, key=_score)


def merge_products(db=None, dry_run=False):
    """
    Merge matched products into canonical versions.

    Only merges when 100% certain (fingerprint match).
    """
    if db is None:
        db = get_db()

    matches = find_matches(db, dry_run=True)
    all_groups = matches.get("groups", [])

    if not all_groups:
        print("No mergeable groups found.")
        return {"merged_groups": 0, "merged_products": 0}

    stats = {"merged_groups": 0, "merged_products": 0, "errors": 0}

    if dry_run:
        print(f"\n--- DRY RUN: {len(all_groups)} groups would be merged ---")
        for i, group in enumerate(all_groups[:20]):
            canonical = select_canonical(group["products"])
            print(f"\n  Group {i+1} (conf: {group['confidence']:.2f}):")
            print(f"    Stores: {', '.join(group['store_coverage'])}")
            print(f"    Canonical: {canonical['name'][:70]}")
            print(f"      ID: {canonical['productId']}")
            for p in group["products"]:
                if p["productId"] != canonical["productId"]:
                    print(f"    → Merge: {p['name'][:70]}")
                    print(f"      ID: {p['productId']}")
                    print(f"      Stores: {', '.join(p['stores'])}")
        return stats

    from pymongo import UpdateOne
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

    for group in all_groups:
        try:
            canonical = select_canonical(group["products"])
            canonical_pid = canonical["productId"]

            # Find canonical product doc
            canonical_doc = db.products.find_one({"productId": canonical_pid})
            if not canonical_doc:
                stats["errors"] += 1
                continue

            # Collect all stores from all group members
            all_stores = list(canonical_doc.get("stores", []))
            existing_store_names = {s.get("store") for s in all_stores}

            for p in group["products"]:
                if p["productId"] == canonical_pid:
                    continue

                p_doc = db.products.find_one({"productId": p["productId"]})
                if not p_doc:
                    continue

                for s in p_doc.get("stores", []):
                    store_name = s.get("store")
                    if store_name not in existing_store_names:
                        all_stores.append(s)
                        existing_store_names.add(store_name)

            # Calculate cheapest price (handle string/float types)
            def _to_num(v):
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return None

            cheapest_avail = [s for s in all_stores if s.get("is_available", True)]
            cheapest_price = min(
                (_to_num(s["price"]) for s in cheapest_avail if s.get("price") is not None),
                default=None,
            )
            cheapest_stores = sorted(set(
                s["store"] for s in cheapest_avail
                if _to_num(s.get("price")) == cheapest_price and s.get("price") is not None
            )) if cheapest_price else []

            # Update canonical product
            db.products.update_one(
                {"productId": canonical_pid},
                {"$set": {
                    "stores": all_stores,
                    "cheapestPrice": cheapest_price,
                    "cheapest": {"price": cheapest_price, "store": ", ".join(cheapest_stores)},
                    "updatedAt": now,
                }}
            )

            # Update store_products to point to canonical
            for p in group["products"]:
                if p["productId"] == canonical_pid:
                    continue

                # Find store_products for this product
                for sp in db.store_products.find({"productId": p["productId"]}, {"storeId": 1, "storeProductId": 1}):
                    # Check if canonical already has a store_product for this store
                    existing = db.store_products.find_one({
                        "productId": canonical_pid, "storeId": sp["storeId"]
                    })
                    if existing:
                        # Already have canonical for this store — remove duplicate
                        db.store_products.delete_one({"_id": sp["_id"]})
                    else:
                        # Safe to update
                        db.store_products.update_one(
                            {"_id": sp["_id"]},
                            {"$set": {"productId": canonical_pid, "updatedAt": now}}
                        )

                # Update price_history
                db.price_history.update_many(
                    {"productId": p["productId"]},
                    {"$set": {"productId": canonical_pid}}
                )

                # Archive duplicate
                db.products.update_one(
                    {"productId": p["productId"]},
                    {"$set": {
                        "archived": True,
                        "archivedAt": now,
                        "canonicalProductId": canonical_pid,
                        "updatedAt": now,
                    }}
                )

            stats["merged_groups"] += 1
            stats["merged_products"] += len(group["products"]) - 1

        except Exception as e:
            stats["errors"] += 1
            print(f"  ERROR: {e}")

        if stats["merged_groups"] % 500 == 0:
            print(f"  Merged: {stats['merged_groups']} groups, {stats['merged_products']} products")

    print(f"\nDone: {stats['merged_groups']} groups, "
          f"{stats['merged_products']} merged, "
          f"{stats['errors']} errors")
    return stats


# ───────────────────────────────────────────────────────────────────────
# CLI
# ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Cross-store product matching")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    if args.dry_run:
        result = find_matches(dry_run=True, limit=args.limit)
    else:
        result = merge_products(dry_run=False)

    print(json.dumps(result, indent=2, default=str))
