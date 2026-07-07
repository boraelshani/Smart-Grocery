#!/usr/bin/env python3
"""
Hofer (ALDI Austria) product scraper
======================================
Strategy:
  1. Load all product URLs from sitemap_products.xml (≈12,175 URLs)
  2. Fetch each page concurrently with ThreadPoolExecutor
  3. Parse server-rendered HTML for: name, price, unit price, size, image, category, offers
  4. Upsert into products / product_store / offers / promotions / promotion_targets

Offer types detected from server-rendered HTML:
  - Percentage discount  → discount_type='percentage'
  - BOGO / N+M gratis   → discount_type='bogo'
  - Multi-buy % saving  → discount_type='multibuy'
  - Fixed price saving  → discount_type='fixed'
  - Generic Aktion      → discount_type='percentage' with placeholder value

Run:
    python3 scripts/hofer_sitemap_to_postgres.py
    python3 scripts/hofer_sitemap_to_postgres.py --limit 10    # test mode
    python3 scripts/hofer_sitemap_to_postgres.py --workers 8   # custom concurrency
"""

import argparse
import hashlib
import logging
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import requests
from psycopg2.extras import execute_values

# ── Project root ───────────────────────────────────────────────────────────────
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / '.env')

import psycopg2

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
SITEMAP_URL  = 'https://www.hofer.at/sitemap_products.xml'
STORE_ID     = 'hofer'
STORE_NAME   = 'Hofer'
SCENE7_BASE  = 'https://s7g10.scene7.com/is/image/aldi'
WORKERS      = 10
BATCH_SIZE   = 200
COOLDOWN     = 0.3   # seconds between batches

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'de-AT,de;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

# ── Offer label patterns (order matters — most specific first) ─────────────────
# Each entry: (regex_pattern, discount_type, value_group, min_qty_group)
_OFFER_PATTERNS = [
    # N+M gratis  e.g. "2+1 GRATIS", "3+2 Gratis", "1+1 gratis"
    (re.compile(r'(\d+)\s*\+\s*(\d+)\s*(gratis|free|geschenkt)', re.IGNORECASE),
     'bogo', 2, 1),
    # N für M    e.g. "3 für 2", "2 für 1"
    (re.compile(r'(\d+)\s*f[uü]r\s*(\d+)', re.IGNORECASE),
     'bogo_fuer', None, None),
    # buy N save X%  e.g. "2 kaufen 20% sparen", "ab 2 Stück 15% Rabatt"
    (re.compile(r'(\d+(?:\.\d+)?)\s*%.*?(?:ab|kaufen?|stück|pack)', re.IGNORECASE),
     'multibuy_pct_first', None, None),
    (re.compile(r'(?:ab\s*|bei\s*kauf\s*von\s*|kaufen?\s*)(\d+).*?(\d+(?:\.\d+)?)\s*%', re.IGNORECASE),
     'multibuy', 2, 1),
    # X% Rabatt / Aktionspreis
    (re.compile(r'(\d+(?:\.\d+)?)\s*%\s*(?:rabatt|erm[äa]ssigung|billiger|g[üu]nstiger)', re.IGNORECASE),
     'percentage', 1, None),
    # -X% or X% off
    (re.compile(r'-\s*(\d+(?:\.\d+)?)\s*%', re.IGNORECASE),
     'percentage', 1, None),
    # Fixed saving  e.g. "€0.50 günstiger", "spare €1"
    (re.compile(r'(?:spare|günstiger|billiger|reduziert\s+um)\s*€?\s*(\d+(?:[.,]\d+)?)', re.IGNORECASE),
     'fixed', 1, None),
    # Generic Aktion / Angebot (no value — placeholder)
    (re.compile(r'\b(?:aktion|angebot|aktionspreis|sonderangebot|deal)\b', re.IGNORECASE),
     'aktion', None, None),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return date.today()


# ── Sitemap ────────────────────────────────────────────────────────────────────
def _load_sitemap_urls(session: requests.Session) -> List[str]:
    resp = session.get(SITEMAP_URL, headers=HEADERS, timeout=120, stream=True)
    resp.raise_for_status()
    content = b''
    for chunk in resp.iter_content(chunk_size=65536):
        content += chunk
    locs = re.findall(rb'<loc>(.*?)</loc>', content)
    seen: set = set()
    urls = []
    for loc_b in locs:
        loc = loc_b.decode('utf-8')
        if '/de/p.' not in loc or loc in seen:
            continue
        seen.add(loc)
        urls.append(loc)
    return urls


# ── HTML parsing ───────────────────────────────────────────────────────────────
def _parse_price(text: str) -> Optional[float]:
    """Convert '€ 2,79' or '2.79' to float."""
    if not text:
        return None
    clean = re.sub(r'[^\d,.]', '', text.strip())
    clean = clean.replace(',', '.')
    try:
        return float(clean) if clean else None
    except ValueError:
        return None


def _parse_unit_price(text: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Parse unit price string like '(100 per Gramm = € 1,98)' or '(1 per Kilogramm = € 5,37)'.
    Returns (unit_price_per_100, unit_string) e.g. (1.98, '100g') or (5.37, 'kg').
    """
    if not text:
        return None, None
    m = re.search(r'\(\s*(\d+(?:[.,]\d+)?)\s*per\s*(\w+)\s*=\s*€?\s*(\d+[.,]\d+)\s*\)', text, re.IGNORECASE)
    if m:
        qty_str  = m.group(1).replace(',', '.')
        unit     = m.group(2).lower()
        val_str  = m.group(3).replace(',', '.')
        try:
            val = float(val_str)
            qty = float(qty_str)
            unit_label = f'{int(qty)}{unit}' if qty != 1 else unit
            return val, unit_label
        except ValueError:
            pass
    return None, None


def _parse_size(text: str) -> Tuple[Optional[float], Optional[str]]:
    """Parse '175 g', '1,5 l', '6x0,5l', '500 ml' → (175.0, 'g')."""
    if not text:
        return None, None
    text = text.strip().lower()
    # Multi-pack: 6x0,5l
    multi = re.match(r'^(\d+)\s*x\s*(\d+[.,]?\d*)\s*(g|kg|ml|l|cl|dl|stk|stück)$', text)
    if multi:
        try:
            total = int(multi.group(1)) * float(multi.group(2).replace(',', '.'))
            return total, multi.group(3)
        except ValueError:
            pass
    m = re.match(r'^(\d+[.,]?\d*)\s*(g|kg|mg|ml|l|cl|dl|stk|stück|stueck)$', text)
    if m:
        try:
            return float(m.group(1).replace(',', '.')), m.group(2)
        except ValueError:
            pass
    return None, None


def _detect_offers(texts: List[str]) -> Dict[str, Any]:
    """
    Given a list of text snippets (badge labels, promo texts, description),
    return offer dict: {discount_type, discount_value, min_quantity, offer_label}
    or empty dict if no offer detected.
    """
    combined = ' '.join(t for t in texts if t)
    if not combined.strip():
        return {}

    for pattern, dtype, val_group, qty_group in _OFFER_PATTERNS:
        m = pattern.search(combined)
        if not m:
            continue

        if dtype == 'bogo':
            # N+M gratis
            try:
                min_qty    = int(m.group(1))
                free_qty   = int(m.group(2))
                return {'discount_type': 'bogo', 'discount_value': free_qty,
                        'min_quantity': min_qty, 'offer_label': m.group(0).strip()}
            except (IndexError, ValueError):
                pass

        elif dtype == 'bogo_fuer':
            # N für M  (e.g. 3 für 2 → buy 2 get 1 free)
            try:
                get_qty = int(m.group(1))
                pay_qty = int(m.group(2))
                if get_qty > pay_qty:
                    return {'discount_type': 'bogo', 'discount_value': get_qty - pay_qty,
                            'min_quantity': pay_qty, 'offer_label': m.group(0).strip()}
            except (IndexError, ValueError):
                pass

        elif dtype == 'multibuy':
            try:
                min_qty   = int(m.group(1))
                disc_pct  = float(m.group(2).replace(',', '.'))
                return {'discount_type': 'multibuy', 'discount_value': disc_pct,
                        'min_quantity': min_qty, 'offer_label': m.group(0).strip()}
            except (IndexError, ValueError):
                pass

        elif dtype == 'multibuy_pct_first':
            # "20% ab 2 Stück"
            pct_m = re.search(r'(\d+(?:\.\d+)?)\s*%', combined)
            qty_m = re.search(r'ab\s*(\d+)', combined, re.IGNORECASE)
            if pct_m and qty_m:
                try:
                    return {'discount_type': 'multibuy',
                            'discount_value': float(pct_m.group(1)),
                            'min_quantity': int(qty_m.group(1)),
                            'offer_label': combined[:80].strip()}
                except ValueError:
                    pass

        elif dtype == 'percentage':
            try:
                disc = float(m.group(1).replace(',', '.'))
                return {'discount_type': 'percentage', 'discount_value': disc,
                        'min_quantity': 1, 'offer_label': m.group(0).strip()}
            except (IndexError, ValueError):
                pass

        elif dtype == 'fixed':
            try:
                saving = float(m.group(1).replace(',', '.'))
                return {'discount_type': 'fixed', 'discount_value': saving,
                        'min_quantity': 1, 'offer_label': m.group(0).strip()}
            except (IndexError, ValueError):
                pass

        elif dtype == 'aktion':
            return {'discount_type': 'percentage', 'discount_value': 5.0,
                    'min_quantity': 1, 'offer_label': m.group(0).strip()}

    return {}


def _parse_product_page(url: str, html: str) -> Optional[Dict[str, Any]]:
    """Extract product data from Hofer product page HTML."""
    # Product code from URL (the long number at the end before .html)
    code_m = re.search(r'\.(\d{9,}(?:-\d+)?)\.html', url)
    product_code = code_m.group(1) if code_m else None

    # Name from h1 — strip template/script fragments
    h1 = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
    if not h1:
        return None
    name = re.sub(r'\{[^}]+\}|<[^>]+>', '', h1.group(1)).strip()
    name = re.sub(r'\s+', ' ', name).strip()
    if not name:
        return None

    # Price — server-rendered in data-price attribute
    price_m = re.search(r'class="[^"]*pdp_price__now at-productprice_lbl[^"]*"\s+data-price="([^"]+)"', html)
    if not price_m:
        # fallback: first data-price in base_price section
        price_m = re.search(r'base_price.*?data-price="([^"]+)"', html, re.DOTALL)
    if not price_m:
        return None
    price = _parse_price(price_m.group(1))
    if not price:
        return None

    # Was-price (statt-preis) — check for rendered crossed-out price in PDP (not cart templates)
    # Hofer renders this in .pdp_price__was when product is on sale
    was_price = None
    was_m = re.search(
        r'class="[^"]*pdp_price__was[^"]*"[^>]*>\s*(?:Statt\s*)?€?\s*([\d,\.]+)',
        html, re.IGNORECASE
    )
    if was_m and '{{' not in was_m.group(0):
        was_price = _parse_price(was_m.group(1))

    # Also check for Aktionspreis section where was-price is shown as crossed
    if not was_price:
        statt_m = re.search(
            r'<s[^>]*>\s*€?\s*([\d,\.]+)\s*</s>',
            html
        )
        if statt_m:
            # Only use if it's in the PDP area, not in the cart template (which uses {{...}})
            ctx = html[max(0, statt_m.start()-200):statt_m.start()]
            if '{{' not in ctx and 'cartEntry' not in ctx:
                was_price = _parse_price(statt_m.group(1))

    # Unit price string e.g. "(100 per Gramm = € 1,98)"
    unit_note = re.search(r'additional-notes-price[^>]*>\s*(per\s+\w+[^<]*)</span>', html, re.IGNORECASE)
    unit_price, unit_price_unit = _parse_unit_price(unit_note.group(1) if unit_note else None)

    # Size from data-description attribute
    size_m = re.search(r'product-description"[^>]*data-description="([^"]+)"', html)
    size_text = size_m.group(1).strip() if size_m else None
    size_normalized, unit_normalized = _parse_size(size_text)

    # Image — numeric scene7 image IDs belong to products
    # The product image ID is a date-like number: YYYYMMDDNNNN
    img_ids = re.findall(r'scene7\.com/is/image/aldi/(\d{9,})', html)
    image_url = None
    if img_ids:
        # First numeric-only ID is usually the product image
        image_url = f'{SCENE7_BASE}/{img_ids[0]}?$PDP-M$'

    # Category from meta data-targetcategory  e.g. "Dairy:Joghurts/Quark:Joghurt, Frucht"
    cat_m = re.search(r'data-targetcategory="([^"]+)"', html)
    category_raw = cat_m.group(1) if cat_m else None

    # Badges / promo labels — server-rendered in badges_items_list
    badge_alts = re.findall(
        r'badges_items_list[^>]*>.*?</ul>',
        html, re.DOTALL
    )
    badge_texts = []
    if badge_alts:
        badge_texts = re.findall(r'alt="([^"]+)"', badge_alts[0])
        # Filter out non-offer badges like "Vegan", "Bio" etc.
        badge_texts = [b for b in badge_texts if any(
            kw in b.lower() for kw in ['aktion', 'gratis', 'rabatt', 'angebot', '%', 'für', 'bonus', 'promo']
        )]

    # Promo text block — look for dedicated promo/sale text in PDP (not cart)
    promo_texts = []
    promo_m = re.search(r'class="[^"]*(?:promo|aktion|angebot|sale|discount)[^"]*"[^>]*>([^<]{3,})<', html, re.IGNORECASE)
    if promo_m and '{{' not in promo_m.group(1):
        promo_texts.append(promo_m.group(1).strip())

    # Detect offer from all collected texts
    offer = _detect_offers(badge_texts + promo_texts)

    # If we have a was-price but no detected offer → compute percentage discount
    if was_price and was_price > price and not offer:
        disc_pct = round((was_price - price) / was_price * 100, 1)
        offer = {
            'discount_type': 'percentage',
            'discount_value': disc_pct,
            'min_quantity': 1,
            'offer_label': f'Statt €{was_price:.2f}',
        }

    # Fingerprint — use product code if available, else name+size hash
    if product_code:
        fingerprint = f'hofer_{product_code}'
    else:
        slug = re.sub(r'[^a-z0-9]', '_', name.lower())
        fingerprint = f'hofer_{hashlib.md5(slug.encode()).hexdigest()[:12]}'

    return {
        'name':             name,
        'fingerprint':      fingerprint,
        'product_code':     product_code,
        'price':            price,
        'was_price':        was_price,
        'unit_price':       unit_price,
        'unit_price_unit':  unit_price_unit,
        'size_text':        size_text,
        'size_normalized':  size_normalized,
        'unit_normalized':  unit_normalized,
        'image_url':        image_url,
        'category_raw':     category_raw,
        'product_url':      url,
        'offer':            offer,   # dict or {}
    }


# ── Fetcher ───────────────────────────────────────────────────────────────────
def _fetch_one(session: requests.Session, url: str) -> Optional[Dict[str, Any]]:
    try:
        r = session.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return _parse_product_page(url, r.text)
    except Exception as e:
        log.debug('Fetch error %s: %s', url, e)
        return None


# ── DB helpers ────────────────────────────────────────────────────────────────
def _ensure_store(cursor) -> None:
    cursor.execute("""
        INSERT INTO stores (store_id, name, website)
        VALUES (%s, %s, %s)
        ON CONFLICT (store_id) DO NOTHING
    """, (STORE_ID, STORE_NAME, 'https://www.hofer.at'))


def _upsert_products(cursor, rows: List[Dict]) -> Dict[str, int]:
    """Upsert into products table. Returns fingerprint→id map."""
    if not rows:
        return {}

    data = []
    for r in rows:
        data.append((
            r['name'], r['name'],       # name, name_de
            r['fingerprint'],
            r['image_url'],
            r['size_normalized'],
            r['unit_normalized'],
            _now(), _now(),
        ))

    execute_values(cursor, """
        INSERT INTO products (name, name_de, fingerprint, default_image_url,
                              size_normalized, unit_normalized, created_at, updated_at)
        VALUES %s
        ON CONFLICT (fingerprint) DO UPDATE SET
            name             = EXCLUDED.name,
            name_de          = EXCLUDED.name_de,
            default_image_url = COALESCE(EXCLUDED.default_image_url, products.default_image_url),
            size_normalized  = COALESCE(EXCLUDED.size_normalized, products.size_normalized),
            unit_normalized  = COALESCE(EXCLUDED.unit_normalized, products.unit_normalized),
            updated_at       = EXCLUDED.updated_at
        RETURNING id, fingerprint
    """, data, page_size=500, fetch=True)

    # Re-query to get all ids (RETURNING from execute_values is unreliable cross-pg versions)
    fps = [r['fingerprint'] for r in rows]
    cursor.execute(
        "SELECT id, fingerprint FROM products WHERE fingerprint = ANY(%s)", (fps,)
    )
    return {fp: pid for pid, fp in cursor.fetchall()}


def _upsert_product_store(cursor, rows: List[Dict], fp_to_id: Dict[str, int]) -> None:
    if not rows:
        return

    data = []
    for r in rows:
        pid = fp_to_id.get(r['fingerprint'])
        if not pid:
            continue
        # If was_price is higher → product is on sale; store was_price as base, current as effective
        # Schema uses base_price for the current selling price
        base_price = r['price']
        on_sale    = bool(r['was_price'] and r['was_price'] > r['price'])

        data.append((
            pid,
            STORE_ID,
            base_price,
            r['unit_price'],
            r['unit_price_unit'],
            on_sale,    # is_preis_gesenkt
            r['product_url'],
            True,       # is_available
            _now(),     # last_seen
            _now(),     # created_at
        ))

    if not data:
        return

    execute_values(cursor, """
        INSERT INTO product_store (product_id, store_id, base_price,
                                   unit_price, unit_price_unit, is_preis_gesenkt,
                                   product_url, is_available, last_seen, created_at)
        VALUES %s
        ON CONFLICT (product_id, store_id) DO UPDATE SET
            base_price       = EXCLUDED.base_price,
            unit_price       = COALESCE(EXCLUDED.unit_price, product_store.unit_price),
            unit_price_unit  = COALESCE(EXCLUDED.unit_price_unit, product_store.unit_price_unit),
            is_preis_gesenkt = EXCLUDED.is_preis_gesenkt,
            product_url      = EXCLUDED.product_url,
            is_available     = TRUE,
            last_seen        = EXCLUDED.last_seen
    """, data, page_size=500)


def _record_price_history(cursor, rows: List[Dict], fp_to_id: Dict[str, int],
                          old_prices: Dict[int, float]) -> None:
    data = []
    for r in rows:
        pid = fp_to_id.get(r['fingerprint'])
        if not pid:
            continue
        new_price = float(r['price'])
        old_price = old_prices.get(pid)
        if old_price is not None and abs(old_price - new_price) > 0.001:
            data.append((pid, STORE_ID, old_price, new_price, _now()))

    if data:
        execute_values(cursor, """
            INSERT INTO price_history (product_id, store_id, old_price, new_price, changed_at)
            VALUES %s
        """, data, page_size=500)


def _setup_promotion(cursor) -> int:
    """Create or find today's Hofer promotion campaign. Returns promotion id."""
    today     = _today()
    promo_name = f'Hofer Aktionen {today.isoformat()}'

    # Deactivate old Hofer campaigns
    cursor.execute(
        "UPDATE promotions SET is_active = FALSE WHERE name LIKE %s AND name != %s AND is_active = TRUE",
        ('Hofer Aktionen %', promo_name)
    )

    cursor.execute("""
        INSERT INTO promotions (name, description, start_date, is_active, created_at)
        VALUES (%s, %s, %s, TRUE, %s)
        ON CONFLICT DO NOTHING
        RETURNING id
    """, (promo_name, f'Hofer scrape {today.isoformat()}', today, _now()))
    row = cursor.fetchone()
    if not row:
        cursor.execute("SELECT id FROM promotions WHERE name = %s LIMIT 1", (promo_name,))
        row = cursor.fetchone()
    return row[0]


def _upsert_promotions(cursor, rows: List[Dict], fp_to_id: Dict[str, int],
                       promo_id: int) -> None:
    """For every row with a detected offer, create/find an Offer and add a PromotionTarget."""
    offer_cache: Dict[str, int] = {}
    targets = []

    for r in rows:
        if not r.get('offer'):
            continue
        pid = fp_to_id.get(r['fingerprint'])
        if not pid:
            continue

        offer = r['offer']
        dtype  = offer['discount_type']
        dval   = offer['discount_value']
        min_q  = offer.get('min_quantity', 1)
        label  = offer.get('offer_label', '')

        if dtype == 'bogo':
            name = f"Hofer {min_q}+{dval} Gratis"
        elif dtype == 'multibuy':
            name = f"Hofer {dval}% ab {min_q} Stück"
        elif dtype == 'percentage':
            name = f"Hofer -{round(dval)}% Rabatt"
        elif dtype == 'fixed':
            name = f"Hofer €{dval:.2f} günstiger"
        else:
            name = f"Hofer Aktion"

        cache_key = f"{dtype}_{dval}_{min_q}"
        if cache_key not in offer_cache:
            cursor.execute("""
                INSERT INTO offers (name, description, discount_type, discount_value,
                                    min_quantity, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, TRUE, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING id
            """, (name, label, dtype, dval, min_q, _now(), _now()))
            row = cursor.fetchone()
            if not row:
                cursor.execute("SELECT id FROM offers WHERE name = %s LIMIT 1", (name,))
                row = cursor.fetchone()
            if not row:
                continue
            offer_cache[cache_key] = row[0]

        offer_id = offer_cache[cache_key]
        # Link promo → offer
        cursor.execute(
            "UPDATE promotions SET offer_id = %s WHERE id = %s AND offer_id IS NULL",
            (offer_id, promo_id)
        )
        targets.append((promo_id, pid, STORE_ID, _now()))

    if not targets:
        return

    execute_values(cursor, """
        INSERT INTO promotion_targets (promotion_id, product_id, store_id, created_at)
        VALUES %s
        ON CONFLICT (promotion_id, product_id, store_id) DO NOTHING
    """, targets, page_size=500)


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='Hofer product scraper')
    parser.add_argument('--limit',   type=int, default=None, help='Max products (test mode)')
    parser.add_argument('--workers', type=int, default=WORKERS)
    parser.add_argument('--batch',   type=int, default=BATCH_SIZE)
    args = parser.parse_args()

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print('[!] DATABASE_URL not set'); sys.exit(1)

    conn   = psycopg2.connect(db_url)
    cursor = conn.cursor()

    print('[HOFER] Fetching sitemap…')
    session = requests.Session()
    urls = _load_sitemap_urls(session)
    print(f'[HOFER] {len(urls):,} product URLs found')

    if args.limit:
        urls = urls[:args.limit]
        print(f'[HOFER] Limiting to {args.limit} products (test mode)')

    _ensure_store(cursor)
    conn.commit()

    # Setup today's promotion campaign
    promo_id = _setup_promotion(cursor)
    conn.commit()

    # Load existing prices for price-history tracking
    cursor.execute(
        "SELECT product_id, base_price FROM product_store WHERE store_id = %s", (STORE_ID,)
    )
    old_prices = {pid: float(p) for pid, p in cursor.fetchall()}

    total    = len(urls)
    batches  = [urls[i:i+args.batch] for i in range(0, total, args.batch)]
    inserted = updated = skipped = failed = 0

    print(f'[HOFER] Processing {total:,} products in {len(batches)} batches '
          f'({args.workers} workers, batch={args.batch})')

    for batch_num, batch_urls in enumerate(batches, 1):
        rows: List[Dict] = []

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(_fetch_one, session, u): u for u in batch_urls}
            for fut in as_completed(futures):
                result = fut.result()
                if result is None:
                    failed += 1
                else:
                    rows.append(result)

        if not rows:
            print(f'[HOFER] Batch {batch_num}/{len(batches)}: no results')
            continue

        try:
            fp_to_id = _upsert_products(cursor, rows)

            # Count inserts vs updates
            for r in rows:
                pid = fp_to_id.get(r['fingerprint'])
                if pid and pid not in old_prices:
                    inserted += 1
                elif pid:
                    updated += 1
                else:
                    skipped += 1

            _upsert_product_store(cursor, rows, fp_to_id)
            _record_price_history(cursor, rows, fp_to_id, old_prices)
            _upsert_promotions(cursor, rows, fp_to_id, promo_id)
            conn.commit()

            offer_count = sum(1 for r in rows if r.get('offer'))
            print(f'[HOFER] Batch {batch_num}/{len(batches)}: '
                  f'inserted={inserted}  updated={updated}  '
                  f'skipped={skipped}  failed={failed}  '
                  f'offers={offer_count}')

        except Exception as e:
            conn.rollback()
            print(f'[HOFER] Batch {batch_num} DB error: {e}')
            failed += len(batch_urls)

        if batch_num < len(batches):
            time.sleep(COOLDOWN)

    print(f'\n[HOFER] DONE — processed={inserted+updated}  '
          f'inserted={inserted}  updated={updated}  '
          f'skipped={skipped}  failed={failed}')

    cursor.close()
    conn.close()


if __name__ == '__main__':
    main()
