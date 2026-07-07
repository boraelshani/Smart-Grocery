"""
Barcode enrichment via Open Food Facts.

Searches OFF by the exact product name and only stores an EAN when the returned
product name is nearly identical (word-set overlap ≥ 80%). Prefers results that
also match the brand and are sold in Austria (cc=at).

Run:
    ./venv/bin/python3 scripts/enrich_barcodes_off.py --store spar --limit 100 --dry-run
    ./venv/bin/python3 scripts/enrich_barcodes_off.py --store spar
"""
import sys, os, re, time, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from app import app
from models.postgres_models import db, Product, ProductStore

OFF_SEARCH = "https://world.openfoodfacts.org/cgi/search.pl"
OFF_HEADERS = {"User-Agent": "SmartGrocery/1.0 (price-comparison Austria; contact@smartgrocery.at)"}

# Minimum fraction of name words that must appear in OFF result name
WORD_OVERLAP_THRESHOLD = 0.80


def _words(text: str) -> set:
    """Lowercase word tokens, stripping punctuation and common noise."""
    text = re.sub(r"[^\w\s]", " ", (text or "").lower())
    stopwords = {"und", "von", "mit", "aus", "fur", "fur", "die", "der", "das"}
    return {w for w in text.split() if len(w) > 1 and w not in stopwords}


def _word_overlap(a: str, b: str) -> float:
    """Fraction of words in `a` that also appear in `b`."""
    wa, wb = _words(a), _words(b)
    if not wa:
        return 0.0
    return len(wa & wb) / len(wa)


def _search_off(name: str, brand: str = None) -> list:
    """Query OFF with the exact product name, filtered to Austria."""
    try:
        r = requests.get(
            OFF_SEARCH,
            params={
                "search_terms": name,
                "json": 1,
                "page_size": 5,
                "cc": "at",          # Austria-sold products first
                "lc": "de",
                "fields": "code,product_name,brands,quantity,stores_tags,countries_tags",
            },
            headers=OFF_HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("products", [])
    except Exception:
        return []


def _pick_barcode(product: Product, candidates: list):
    """
    Return (barcode, overlap_score) for the best candidate, or (None, 0).

    Acceptance rules (all must pass):
      1. Word overlap between our name and OFF name ≥ WORD_OVERLAP_THRESHOLD
      2. If we have a brand, the OFF brand must contain our brand (or vice versa)
      3. Barcode must be 8–14 digits (EAN-8, EAN-13, or UPC-A)
    """
    our_name  = product.name or ""
    our_brand = (product.brand or "").lower()

    best_code  = None
    best_score = 0.0

    for c in candidates:
        barcode  = (c.get("code") or "").strip()
        off_name = c.get("product_name") or ""
        off_brand = (c.get("brands") or "").lower()

        # Basic barcode validity
        if not re.match(r"^\d{8,14}$", barcode):
            continue

        # Name must overlap well
        score = _word_overlap(our_name, off_name)
        if score < WORD_OVERLAP_THRESHOLD:
            continue

        # Brand check: if we know our brand, OFF brand must contain it
        if our_brand and our_brand not in off_brand and off_brand not in our_brand:
            continue

        if score > best_score:
            best_score = score
            best_code  = barcode

    return best_code, best_score


def run(store_id: str = None, limit: int = None, dry_run: bool = False):
    with app.app_context():
        query = db.session.query(Product).filter(Product.barcode == None)

        if store_id:
            query = (
                query
                .join(ProductStore, Product.id == ProductStore.product_id)
                .filter(ProductStore.store_id == store_id, ProductStore.is_available == True)
            )

        if limit:
            query = query.limit(limit)

        products = query.all()
        total = len(products)
        print(f"[*] {total} products without barcode"
              + (f" (store={store_id})" if store_id else ""))
        print(f"[*] Word-overlap threshold: {WORD_OVERLAP_THRESHOLD:.0%}\n")

        found = skipped = errors = 0

        for i, product in enumerate(products, 1):
            try:
                candidates = _search_off(product.name, product.brand)
                barcode, score = _pick_barcode(product, candidates)

                if barcode:
                    if not dry_run:
                        product.barcode = barcode
                    found += 1
                    tag = "[DRY]" if dry_run else "[✓]"
                    print(f"  {tag} [{i}/{total}] {product.name[:55]:<55} EAN={barcode}  overlap={score:.0%}")
                else:
                    skipped += 1
                    if i <= 20 or i % 200 == 0:
                        best_name = candidates[0].get("product_name", "—") if candidates else "no results"
                        print(f"  [—] [{i}/{total}] {product.name[:45]:<45}  best_off={best_name[:40]}")

                if not dry_run and found % 200 == 0 and found > 0:
                    db.session.commit()
                    print(f"      [committed {found} barcodes so far]")

                time.sleep(0.35)

            except Exception as e:
                errors += 1
                print(f"  [!] [{i}/{total}] Error: {product.name[:40]} — {e}")
                time.sleep(1)

        if not dry_run and found > 0:
            db.session.commit()

        print(f"\n{'='*60}")
        print(f"  Found & stored:  {found}")
        print(f"  No confident match: {skipped}")
        print(f"  Errors:          {errors}")
        print(f"  Coverage:        {found/total*100:.1f}%" if total else "")
        print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich product barcodes from Open Food Facts")
    parser.add_argument("--store",   default=None, help="Filter by store (e.g. spar, billa)")
    parser.add_argument("--limit",   type=int, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    args = parser.parse_args()
    run(store_id=args.store, limit=args.limit, dry_run=args.dry_run)
