#!/usr/bin/env python3
"""Fast update of Billa offers without re-scraping product pages.

This script updates ONLY the offer data (prices, promotions, unit prices) for
existing products by fetching the product page and extracting just the price info.
Much faster than full scraping since it doesn't re-insert product data.

Use this for regular price updates after initial full scrape.
"""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Optional

import psycopg2
from psycopg2.extras import execute_values
import requests
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from scripts.billa_sitemap_to_postgres import (
    _connect_db,
    _extract_resolved_product,
    _extract_price_data,
    _load_database_uri,
    _now,
    HEADERS,
    STORE_ID,
)


def _load_existing_products_for_update(cursor) -> List[Dict[str, any]]:
    """Load existing products that need offer updates."""
    cursor.execute("""
        SELECT 
            p.id,
            p.fingerprint,
            p.name_de,
            o.id as offer_id,
            o.base_price,
            o.promo_price,
            o.unit_price,
            o.offer_details,
            o.min_quantity,
            o.product_url
        FROM products p
        LEFT JOIN offers o ON p.id = o.product_id AND o.store_id = %s
        WHERE p.store_id = %s
        ORDER BY p.id
    """, (STORE_ID, STORE_ID))
    
    products = []
    for row in cursor.fetchall():
        prod_id, fingerprint, name, offer_id, base_price, promo_price, unit_price, offer_details, min_qty, url = row
        products.append({
            'id': prod_id,
            'fingerprint': fingerprint,
            'name': name,
            'offer_id': offer_id,
            'current_base_price': float(base_price) if base_price else None,
            'current_promo_price': float(promo_price) if promo_price else None,
            'current_unit_price': unit_price,
            'current_offer_details': offer_details,
            'current_min_quantity': min_qty,
            'url': url,
        })
    return products


def _fetch_product_price_data(session: requests.Session, url: str, fingerprint: str) -> Optional[Dict[str, any]]:
    """Fetch only price/offer data from product page."""
    slug = fingerprint.replace("billa:", "")
    
    try:
        response = session.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        response.raise_for_status()
        product = _extract_resolved_product(response.text, slug)
        
        if not product:
            return None
        
        # Extract only price data
        price_data = _extract_price_data(product)
        return price_data
        
    except requests.exceptions.HTTPError as exc:
        if exc.response.status_code in (404, 410):
            # Product no longer available
            return {'unavailable': True}
        return None
    except Exception:
        return None


def _update_offer(cursor, product_id: int, offer_id: Optional[int], price_data: Dict[str, any], url: str) -> bool:
    """Update or insert offer data."""
    ts = _now()
    
    if price_data.get('unavailable'):
        # Mark as unavailable
        if offer_id:
            cursor.execute("""
                UPDATE offers 
                SET is_available = FALSE, last_seen = %s, updated_at = %s
                WHERE id = %s
            """, (ts, ts, offer_id))
        return False
    
    base_price = price_data.get('base_price')
    promo_price = price_data.get('promo_price')
    unit_price = price_data.get('unit_price')
    offer_details = price_data.get('offer_details')
    min_quantity = price_data.get('min_quantity')
    
    if not base_price:
        return False
    
    if offer_id:
        # Update existing offer
        cursor.execute("""
            UPDATE offers 
            SET 
                price = %s,
                base_price = %s,
                promo_price = %s,
                unit_price = %s,
                offer_details = %s,
                min_quantity = %s,
                is_available = TRUE,
                last_seen = %s,
                updated_at = %s
            WHERE id = %s
        """, (base_price, base_price, promo_price, unit_price, offer_details, min_quantity, ts, ts, offer_id))
    else:
        # Insert new offer
        cursor.execute("""
            INSERT INTO offers 
            (product_id, store_id, price, base_price, promo_price, unit_price, offer_details, min_quantity, product_url, is_available, last_seen, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s, %s, %s)
        """, (product_id, STORE_ID, base_price, base_price, promo_price, unit_price, offer_details, min_quantity, url, ts, ts, ts))
    
    return True


def update_offers_only(workers: int = 12, batch_size: int = 100) -> None:
    """Update only offer data for existing products."""
    database_uri = _load_database_uri()
    conn = _connect_db(database_uri)
    conn.autocommit = False
    
    try:
        with conn.cursor() as cursor:
            print("[BILLA] Loading existing products...")
            products = _load_existing_products_for_update(cursor)
            print(f"[BILLA] Found {len(products):,} products to check for offer updates")
        
        session = requests.Session()
        session.headers.update(HEADERS)
        
        total = len(products)
        processed = 0
        updated = 0
        unchanged = 0
        failed = 0
        unavailable = 0
        
        print(f"[BILLA] Updating offers with {workers} workers...")
        
        # Process in batches
        for batch_start in range(0, total, batch_size):
            batch = products[batch_start:batch_start + batch_size]
            updates = []
            
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {
                    executor.submit(_fetch_product_price_data, session, p['url'], p['fingerprint']): p 
                    for p in batch if p['url']
                }
                
                for future in as_completed(future_map):
                    product = future_map[future]
                    processed += 1
                    
                    try:
                        price_data = future.result()
                    except Exception as exc:
                        print(f"[BILLA] Error fetching {product['name']}: {exc}")
                        failed += 1
                        continue
                    
                    if not price_data:
                        failed += 1
                        continue
                    
                    if price_data.get('unavailable'):
                        unavailable += 1
                        updates.append((product, price_data))
                        continue
                    
                    # Check if anything changed
                    changed = False
                    new_base = price_data.get('base_price')
                    new_promo = price_data.get('promo_price')
                    
                    if new_base != product['current_base_price']:
                        changed = True
                    if new_promo != product['current_promo_price']:
                        changed = True
                    if price_data.get('unit_price') != product['current_unit_price']:
                        changed = True
                    if price_data.get('offer_details') != product['current_offer_details']:
                        changed = True
                    if price_data.get('min_quantity') != product['current_min_quantity']:
                        changed = True
                    
                    if changed:
                        updates.append((product, price_data))
                    else:
                        unchanged += 1
                    
                    if processed % 500 == 0:
                        print(f"[BILLA] Progress: {processed}/{total} | Updated: {updated} | Unchanged: {unchanged} | Failed: {failed} | Unavailable: {unavailable}")
            
            # Apply updates in batch
            if updates:
                with conn.cursor() as cursor:
                    for product, price_data in updates:
                        if _update_offer(cursor, product['id'], product['offer_id'], price_data, product['url']):
                            updated += 1
                    conn.commit()
                
                print(f"[BILLA] Batch complete: {processed}/{total} | Updated: {updated} | Unchanged: {unchanged}")
        
        print(f"\n[BILLA] Offer update complete!")
        print(f"  Total products: {total:,}")
        print(f"  Updated: {updated:,}")
        print(f"  Unchanged: {unchanged:,}")
        print(f"  Failed: {failed:,}")
        print(f"  Unavailable: {unavailable:,}")
        
    finally:
        conn.close()


def main() -> None:
    import argparse
    
    parser = argparse.ArgumentParser(description="Fast update of Billa offers without full product scraping.")
    parser.add_argument("--workers", type=int, default=12, help="Concurrent workers for fetching prices.")
    parser.add_argument("--batch-size", type=int, default=100, help="Products per batch before commit.")
    args = parser.parse_args()
    
    update_offers_only(workers=args.workers, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
