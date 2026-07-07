#!/usr/bin/env python3
"""
Cross-Store Product Linker
===========================
After scraping SPAR products, this script finds SPAR products that closely
match existing BILLA products by normalized name and links them together:

  - If a SPAR "Coca-Cola 0,33L" matches BILLA "Coca-Cola 330ml",
    a ProductStore row is created for SPAR on the BILLA Product row.
  - The standalone SPAR Product row is then removed (BILLA's row becomes
    the canonical product with two store entries).

Run after every SPAR scrape:
    python scripts/link_cross_store_products.py

Optional args:
    --dry-run       Print matches without writing to DB
    --threshold 0.6 Minimum name similarity (default 0.6)
    --store1 spar   Source store to link FROM (default: spar)
    --store2 billa  Target store to link TO   (default: billa)
"""

import argparse
import re
import sys
from pathlib import Path
from collections import defaultdict

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import app
from models.postgres_models import db, Product, ProductStore


# ── Text normalisation ────────────────────────────────────────────────────────

_STOP_WORDS = frozenset({
    'g', 'kg', 'ml', 'l', 'cl', 'dl', 'stk', 'stuck', 'stuck',
    'x', 'und', 'mit', 'von', 'der', 'die', 'das', 'bio', 'at',
    'de', 'pack', 'set', 'je', 'pro', 'im', 'in', 'aus', 'fur',
    'ohne', 'mit', 'zum', 'zur', 'natural', 'natur',
})

_SIZE_PATTERN = re.compile(
    r'\d+[\.,]?\d*\s*'
    r'(g|kg|mg|ml|l|cl|dl|stk|stück|stueck|x|\b\d+er\b)',
    re.IGNORECASE,
)


def normalise(name: str) -> frozenset:
    """Return a frozenset of significant lower-case words from *name*."""
    n = name.lower()
    # German umlauts
    for src, tgt in (('ä','ae'),('ö','oe'),('ü','ue'),('ß','ss')):
        n = n.replace(src, tgt)
    # Remove size info (e.g. "330ml", "1,5 l", "6x0,5l")
    n = _SIZE_PATTERN.sub(' ', n)
    # Remove non-word chars
    n = re.sub(r'[^\w\s]', ' ', n)
    words = {w for w in n.split() if len(w) >= 3 and w not in _STOP_WORDS}
    return frozenset(words)


def similarity(ws1: frozenset, ws2: frozenset) -> float:
    if not ws1 or not ws2:
        return 0.0
    inter = len(ws1 & ws2)
    return inter / max(len(ws1), len(ws2))


# ── Matching logic ────────────────────────────────────────────────────────────

def build_inverted_index(products):
    """
    products: list of (product_id, name)
    Returns:  word → set of product_ids
    """
    index = defaultdict(set)
    for pid, name in products:
        for word in normalise(name):
            index[word].add(pid)
    return index


def sizes_compatible(spar_size, spar_unit, billa_size, billa_unit) -> bool:
    """Return True if both products have the same size, or if either has no size data."""
    if spar_size is None or billa_size is None:
        return True  # can't compare — don't disqualify
    # Normalise units to a common form
    unit_map = {'l': 'l', 'ml': 'ml', 'cl': 'ml', 'dl': 'ml',
                'kg': 'kg', 'g': 'g', 'mg': 'g',
                'stk': 'stk', 'stück': 'stk', 'stueck': 'stk'}
    su = unit_map.get((spar_unit or '').lower(), (spar_unit or '').lower())
    bu = unit_map.get((billa_unit or '').lower(), (billa_unit or '').lower())
    # Convert to a common base unit for comparison
    to_base = {'ml': 0.001, 'cl': 0.01, 'dl': 0.1, 'l': 1.0,
               'g': 0.001, 'kg': 1.0, 'mg': 0.000001}
    try:
        sv = float(spar_size) * to_base.get(su, 1.0)
        bv = float(billa_size) * to_base.get(bu, 1.0)
        # Allow 5% tolerance for rounding differences (e.g. 500g vs 0.5kg)
        return abs(sv - bv) / max(sv, bv) < 0.05
    except (TypeError, ValueError, ZeroDivisionError):
        return True


def find_best_match(spar_name: str, spar_size, spar_unit,
                    billa_index: dict, billa_word_sets: dict,
                    billa_sizes: dict, threshold: float):
    """
    Given a SPAR product, find the best matching BILLA product id.
    Returns (billa_product_id, score) or (None, 0).
    Size must match (within tolerance) if both products have size data.
    """
    spar_words = normalise(spar_name)
    if not spar_words:
        return None, 0.0

    # Candidate BILLA products — those sharing at least one word
    candidates = set()
    for word in spar_words:
        candidates.update(billa_index.get(word, set()))

    best_id, best_score = None, 0.0
    for bpid in candidates:
        score = similarity(spar_words, billa_word_sets[bpid])
        if score <= best_score:
            continue
        # Reject if sizes are known and don't match
        bsize, bunit = billa_sizes.get(bpid, (None, None))
        if not sizes_compatible(spar_size, spar_unit, bsize, bunit):
            continue
        best_score = score
        best_id = bpid

    if best_score >= threshold:
        return best_id, best_score
    return None, 0.0


# ── Main ──────────────────────────────────────────────────────────────────────

def run(dry_run: bool, threshold: float, store1: str, store2: str):
    with app.app_context():
        # ── Load store-1 (SPAR) products ─────────────────────────────────────
        store1_rows = (
            db.session.query(Product.id, Product.name, Product.name_de,
                             Product.default_image_url,
                             Product.size_normalized, Product.unit_normalized)
            .join(ProductStore, ProductStore.product_id == Product.id)
            .filter(ProductStore.store_id == store1)
            .all()
        )
        if not store1_rows:
            print(f"[!] No products found for store '{store1}'. Run the scraper first.")
            return

        print(f"[*] {store1.upper()}: {len(store1_rows):,} products to process")

        # ── Load store-2 (BILLA) products ────────────────────────────────────
        store2_rows = (
            db.session.query(Product.id, Product.name, Product.name_de,
                             Product.size_normalized, Product.unit_normalized)
            .join(ProductStore, ProductStore.product_id == Product.id)
            .filter(ProductStore.store_id == store2)
            .all()
        )
        print(f"[*] {store2.upper()}: {len(store2_rows):,} products in index")

        # Build name index for store-2
        billa_products = []
        for row in store2_rows:
            name = row.name or row.name_de or ''
            billa_products.append((row.id, name))

        billa_word_sets = {pid: normalise(name) for pid, name in billa_products}
        billa_sizes = {row.id: (row.size_normalized, row.unit_normalized) for row in store2_rows}
        billa_index = build_inverted_index(billa_products)

        # ── Load existing store-1 ProductStore prices ─────────────────────────
        store1_ps = {
            ps.product_id: ps
            for ps in ProductStore.query.filter_by(store_id=store1).all()
        }

        # ── Match ─────────────────────────────────────────────────────────────
        matched = 0
        skipped_already_linked = 0
        skipped_no_match = 0
        errors = 0

        for row in store1_rows:
            spar_pid = row.id
            spar_name = row.name or row.name_de or ''
            spar_image = row.default_image_url

            billa_pid, score = find_best_match(
                spar_name, row.size_normalized, row.unit_normalized,
                billa_index, billa_word_sets, billa_sizes, threshold
            )

            if billa_pid is None:
                skipped_no_match += 1
                continue

            if dry_run:
                billa_name = next(n for pid, n in billa_products if pid == billa_pid)
                print(f"  MATCH ({score:.2f})  {spar_name[:45]!r:<47}  ->  {billa_name[:45]!r}")
                matched += 1
                continue

            try:
                # Check if SPAR already has a ProductStore on the BILLA product
                existing = ProductStore.query.filter_by(
                    product_id=billa_pid,
                    store_id=store1,
                ).first()

                if existing:
                    skipped_already_linked += 1
                    continue

                # Get SPAR's price for this product
                spar_ps = store1_ps.get(spar_pid)
                if not spar_ps:
                    skipped_no_match += 1
                    continue

                # Price-ratio sanity check — reject if prices differ by more than 2.5x
                billa_product_check = db.session.get(Product, billa_pid)
                billa_ps = ProductStore.query.filter_by(product_id=billa_pid, store_id=store2).first()
                if billa_ps and billa_ps.base_price and spar_ps.base_price:
                    ratio = float(spar_ps.base_price) / float(billa_ps.base_price)
                    if ratio < 0.4 or ratio > 2.5:
                        skipped_no_match += 1
                        continue

                # Create a new ProductStore for SPAR on the BILLA product row
                new_ps = ProductStore(
                    product_id=billa_pid,
                    store_id=store1,
                    base_price=spar_ps.base_price,
                    is_available=True,
                    product_url=spar_ps.product_url,
                    last_seen=spar_ps.last_seen,
                    created_at=spar_ps.created_at,
                    store_product_name=spar_name,
                    store_size_normalized=row.size_normalized,
                    store_unit_normalized=row.unit_normalized,
                )
                db.session.add(new_ps)

                # Backfill image on BILLA product if it has none
                billa_product = db.session.get(Product, billa_pid)
                if billa_product and not billa_product.default_image_url and spar_image:
                    billa_product.default_image_url = spar_image

                # Remove the source product's own store entry so it doesn't duplicate
                # (the store is now represented via the canonical product's product_store)
                # We do NOT delete the source product row — it stays as a stub in case
                # the link needs to be reversed.
                old_ps = ProductStore.query.filter_by(
                    product_id=spar_pid, store_id=store1
                ).first()
                if old_ps:
                    db.session.delete(old_ps)

                matched += 1

                if matched % 100 == 0:
                    db.session.commit()
                    print(f"[*] Linked {matched} products so far…")

            except Exception as e:
                errors += 1
                db.session.rollback()
                print(f"[!] Error linking spar:{spar_pid} → billa:{billa_pid}: {e}")

        if not dry_run:
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"[!] Final commit error: {e}")

        # ── Summary ───────────────────────────────────────────────────────────
        print(f"\n{'='*60}")
        print(f"Cross-store linking complete")
        print(f"  Linked (new cross-store entries) : {matched:,}")
        print(f"  Already linked (skipped)         : {skipped_already_linked:,}")
        print(f"  No BILLA match found             : {skipped_no_match:,}")
        print(f"  Errors                           : {errors:,}")
        if dry_run:
            print(f"\n  *** DRY RUN — nothing was written to the database ***")
        print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cross-store product linker")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print matches without writing to DB")
    parser.add_argument("--threshold", type=float, default=0.6,
                        help="Minimum name similarity score (default: 0.6)")
    parser.add_argument("--store1", default="spar",
                        help="Store to link FROM (default: spar)")
    parser.add_argument("--store2", default="billa",
                        help="Store to link TO   (default: billa)")
    args = parser.parse_args()

    run(
        dry_run=args.dry_run,
        threshold=args.threshold,
        store1=args.store1,
        store2=args.store2,
    )
